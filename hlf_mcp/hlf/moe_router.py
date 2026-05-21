"""
MoE Router — Mixture-of-Experts routing layer for the HLF model gateway.

Provides:
  - ExpertRouter: dataclass-based router config (strategy, weights, fallback chain)
  - MoeRoutingDecision: serializable routing decision with confidence and trace
  - route_to_expert: confidence-based routing with heuristic gating
  - ensemble_route: multi-router ensemble aggregation
  - build_fallback_graph: adjacency graph with circular-dependency detection
  - validate_gating_decision: integrity check for routing decisions
  - MoeModelGateway: lightweight integration wrapper for model_gateway.ModelGateway

References:
  - model_catalog.py: nomic-embed-text-v2-moe, embeddinggemma, qwen3-embedding:4b
  - server_profiles.py: MoE embedding model profiles with VRAM thresholds
  - model_gateway.py (hlf_source/agents/core): ModelGateway, RequestRouter, ModelRegistry

Phase 3 of UNIFIED_ECOSYSTEM_ROADMAP.md: MoE routing merge.
"""

from __future__ import annotations

import hashlib
import itertools
import logging
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Heuristic task-type → keyword mapping (used when gating model unavailable) ──

_TASK_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "code", "program", "function", "class", "debug", "refactor",
        "python", "javascript", "typescript", "rust", "java", "go",
        "api", "endpoint", "database", "sql", "query",
    ],
    "reasoning": [
        "reason", "analyse", "analyze", "logic", "proof", "verify",
        "compare", "evaluate", "assess", "plan", "strategy", "architecture",
    ],
    "creative": [
        "write", "story", "poem", "creative", "imagine", "design",
        "generate", "brainstorm", "idea", "narrative",
    ],
    "embedding": [
        "embed", "vector", "similarity", "search", "retrieve",
        "semantic", "index", "document", "corpus",
    ],
    "multilingual": [
        "translate", "french", "spanish", "german", "chinese", "japanese",
        "arabic", "multilingual", "language", "localization",
    ],
    "instruction": [
        "instruct", "follow", "instruction", "command", "task",
        "execute", "run", "do", "perform",
    ],
    "chat": [
        "chat", "converse", "talk", "discuss", "explain",
        "help", "assist", "question",
    ],
}

# ── Model-name → capability heuristics ──────────────────────────────────────

_MODEL_CAPABILITY_HINTS: dict[str, list[str]] = {
    "qwen3-coder": ["coding"],
    "devstral": ["coding", "reasoning"],
    "deepseek-coder": ["coding"],
    "codestral": ["coding"],
    "starcoder": ["coding"],
    "qwen3": ["reasoning", "instruction", "multilingual"],
    "qwen3.5": ["reasoning", "instruction"],
    "gemma": ["instruction", "chat", "reasoning"],
    "llama": ["chat", "instruction"],
    "mistral": ["chat", "reasoning"],
    "phi": ["reasoning", "instruction"],
    "embeddinggemma": ["embedding"],
    "nomic-embed-text": ["embedding", "multilingual"],
    "bge-m3": ["embedding", "multilingual"],
    "mxbai-embed-large": ["embedding", "coding"],
    "all-minilm": ["embedding"],
    "granite-embedding": ["embedding"],
    "glm": ["reasoning", "multilingual", "chat"],
    "kimi": ["reasoning", "multilingual"],
    "minimax": ["reasoning", "multilingual"],
    "dolphin": ["chat", "creative"],
    "yi": ["reasoning", "chat"],
    "command-r": ["chat", "instruction"],
    "hermes": ["chat", "instruction"],
    "wizard": ["chat", "instruction"],
}


def _detect_task_type(prompt: str) -> dict[str, float]:
    """Score prompt against known task types using keyword heuristics.

    Returns a dict of task_type → confidence in [0, 1].
    """
    prompt_lower = prompt.lower()
    scores: dict[str, float] = {}
    for task, keywords in _TASK_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in prompt_lower)
        scores[task] = min(hits / max(len(keywords) * 0.25, 1), 1.0)
    return scores


def _model_capability_match(model_name: str, task_scores: dict[str, float]) -> float:
    """Score how well a model name matches the detected task profile."""
    model_lower = model_name.lower()
    matched_caps: set[str] = set()
    for prefix, caps in _MODEL_CAPABILITY_HINTS.items():
        if prefix in model_lower:
            matched_caps.update(caps)

    if not matched_caps:
        # Generic fallback: any model can handle basic chat
        matched_caps = {"chat"}

    total = 0.0
    count = 0
    for cap in matched_caps:
        if cap in task_scores:
            total += task_scores[cap]
            count += 1
    # If model capabilities don't overlap at all with task, low base score
    if count == 0:
        return 0.05
    return total / count


def _prompt_hash(prompt: str) -> str:
    """Stable SHA-256 hash of the prompt for determinism tracking."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


# ── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass(slots=True)
class ExpertRouter:
    """Configuration for an MoE expert routing layer.

    Attributes:
        name: Human-readable router identifier.
        experts: Ordered list of model IDs representing expert models.
        gating_model: Model ID used for routing decisions (may be same as an expert).
        routing_strategy: Strategy for expert selection.
            - "confidence": score each expert against prompt, pick highest.
            - "round_robin": cycle through experts sequentially.
            - "weighted": probabilistic selection using `weights`.
            - "fallback": try experts in `fallback_order`; cascade on failure.
        weights: Per-expert weights for "weighted" strategy (must sum to 1.0).
        fallback_order: Ordered fallback chain for "fallback" strategy.
        context_window: Max tokens considered when making routing decisions.
        max_retries: Max attempts per expert before moving to fallback.
    """

    name: str
    experts: list[str]
    gating_model: str
    routing_strategy: str = "confidence"
    weights: dict[str, float] = field(default_factory=dict)
    fallback_order: list[str] = field(default_factory=list)
    context_window: int = 2048
    max_retries: int = 3

    def __post_init__(self) -> None:
        if self.routing_strategy not in ("confidence", "round_robin", "weighted", "fallback"):
            raise ValueError(
                f"Invalid routing_strategy '{self.routing_strategy}'. "
                "Must be one of: confidence, round_robin, weighted, fallback"
            )
        if not self.experts:
            raise ValueError("ExpertRouter.experts must not be empty")
        if not self.gating_model:
            raise ValueError("ExpertRouter.gating_model must not be empty")
        if self.routing_strategy == "weighted":
            if not self.weights:
                raise ValueError("Weighted routing strategy requires non-empty weights dict")
            # Normalize weights
            total = sum(self.weights.values())
            if total <= 0:
                raise ValueError("Sum of weights must be positive")
            self.weights = {k: v / total for k, v in self.weights.items()}
        if self.routing_strategy == "fallback" and not self.fallback_order:
            self.fallback_order = list(self.experts)
        if self.context_window < 1:
            raise ValueError("context_window must be >= 1")
        if self.max_retries < 1:
            raise ValueError("max_retries must be >= 1")


@dataclass(slots=True)
class MoeRoutingDecision:
    """Result of an MoE routing decision.

    Attributes:
        decision_id: Unique identifier for this decision.
        input_hash: SHA-256 hash of the input prompt (for determinism).
        selected_expert: Model ID of the chosen expert.
        confidence: Routing confidence in [0, 1].
        alternatives: Other experts considered, ordered by confidence.
        routing_reason: Human-readable explanation of the decision.
        fallback_chain: Ordered list of experts to try on failure.
        latency_ms: Wall-clock time spent making the routing decision.
    """

    decision_id: str
    input_hash: str
    selected_expert: str
    confidence: float = 0.5
    alternatives: list[str] = field(default_factory=list)
    routing_reason: str = ""
    fallback_chain: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "decision_id": self.decision_id,
            "input_hash": self.input_hash,
            "selected_expert": self.selected_expert,
            "confidence": self.confidence,
            "alternatives": list(self.alternatives),
            "routing_reason": self.routing_reason,
            "fallback_chain": list(self.fallback_chain),
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MoeRoutingDecision:
        """Deserialize from a dict."""
        return cls(
            decision_id=data["decision_id"],
            input_hash=data["input_hash"],
            selected_expert=data["selected_expert"],
            confidence=data["confidence"],
            alternatives=data.get("alternatives", []),
            routing_reason=data.get("routing_reason", ""),
            fallback_chain=data.get("fallback_chain", []),
            latency_ms=data.get("latency_ms", 0.0),
        )


# ── Routing Functions ──────────────────────────────────────────────────────

# Module-level round-robin state (keyed by router name)
_round_robin_index: dict[str, int] = {}


def route_to_expert(
    prompt: str,
    router: ExpertRouter,
    context: dict[str, Any] | None = None,
) -> MoeRoutingDecision:
    """Route a prompt to the best expert using the router's strategy.

    Args:
        prompt: The user prompt to route.
        router: ExpertRouter configuration.
        context: Optional context dict (e.g., prior decisions, session state).

    Returns:
        MoeRoutingDecision with selected expert, confidence, and trace.
    """
    t_start = time.perf_counter()
    input_hash = _prompt_hash(prompt)
    ctx = context or {}

    if router.routing_strategy == "round_robin":
        decision = _route_round_robin(prompt, router, input_hash)
    elif router.routing_strategy == "weighted":
        decision = _route_weighted(prompt, router, input_hash)
    elif router.routing_strategy == "fallback":
        decision = _route_fallback(prompt, router, input_hash, ctx)
    else:
        decision = _route_confidence(prompt, router, input_hash)

    decision.latency_ms = (time.perf_counter() - t_start) * 1000
    return decision


def _route_confidence(
    prompt: str,
    router: ExpertRouter,
    input_hash: str,
) -> MoeRoutingDecision:
    """Confidence-based routing: score each expert against the prompt."""
    task_scores = _detect_task_type(prompt)
    expert_scores: list[tuple[str, float]] = []
    for expert in router.experts:
        score = _model_capability_match(expert, task_scores)
        expert_scores.append((expert, score))

    # Sort by score descending
    expert_scores.sort(key=lambda x: x[1], reverse=True)
    selected_expert, confidence = expert_scores[0]
    alternatives = [e for e, _ in expert_scores[1:]]

    # Build fallback chain: remaining experts in score order
    fallback_chain = alternatives[:]

    return MoeRoutingDecision(
        decision_id=f"moe-{router.name}-{input_hash[:8]}",
        input_hash=input_hash,
        selected_expert=selected_expert,
        confidence=confidence,
        alternatives=alternatives,
        routing_reason=(
            f"Confidence routing for router '{router.name}': "
            f"selected '{selected_expert}' (score={confidence:.3f}) "
            f"over {alternatives}"
        ),
        fallback_chain=fallback_chain,
    )


def _route_round_robin(
    prompt: str,
    router: ExpertRouter,
    input_hash: str,
) -> MoeRoutingDecision:
    """Round-robin routing: cycle through experts sequentially."""
    idx = _round_robin_index.get(router.name, 0)
    selected_expert = router.experts[idx % len(router.experts)]
    _round_robin_index[router.name] = idx + 1

    # Build fallback: remaining experts in order
    fallback_start = (idx + 1) % len(router.experts)
    fallback_chain = (
        router.experts[fallback_start:] + router.experts[:fallback_start]
    )

    return MoeRoutingDecision(
        decision_id=f"moe-{router.name}-{input_hash[:8]}",
        input_hash=input_hash,
        selected_expert=selected_expert,
        confidence=0.5,  # Round-robin is neutral
        alternatives=[e for e in router.experts if e != selected_expert],
        routing_reason=(
            f"Round-robin routing for router '{router.name}': "
            f"selected '{selected_expert}' (index={idx})"
        ),
        fallback_chain=fallback_chain,
    )


def _route_weighted(
    prompt: str,
    router: ExpertRouter,
    input_hash: str,
) -> MoeRoutingDecision:
    """Weighted probabilistic routing using router.weights."""
    experts = list(router.weights.keys())
    weights = [router.weights[e] for e in experts]

    # Seed from input hash for deterministic weighted selection
    hash_int = int(input_hash, 16)
    rng = random.Random(hash_int)
    selected_expert = rng.choices(experts, weights=weights, k=1)[0]

    # Sort alternatives by weight
    alternatives = sorted(
        [e for e in experts if e != selected_expert],
        key=lambda e: router.weights.get(e, 0),
        reverse=True,
    )

    return MoeRoutingDecision(
        decision_id=f"moe-{router.name}-{input_hash[:8]}",
        input_hash=input_hash,
        selected_expert=selected_expert,
        confidence=router.weights.get(selected_expert, 0.0),
        alternatives=alternatives,
        routing_reason=(
            f"Weighted routing for router '{router.name}': "
            f"selected '{selected_expert}' (weight={router.weights.get(selected_expert, 0):.3f})"
        ),
        fallback_chain=alternatives[:],
    )


def _route_fallback(
    prompt: str,
    router: ExpertRouter,
    input_hash: str,
    context: dict[str, Any],
) -> MoeRoutingDecision:
    """Fallback routing: select primary from fallback_order, cascade on failure."""
    fallback_order = router.fallback_order if router.fallback_order else list(router.experts)

    # Check if context indicates prior failures
    failed_experts: set[str] = set(context.get("failed_experts", []))

    # Pick first non-failed expert from fallback order
    selected_expert = fallback_order[0]
    for expert in fallback_order:
        if expert not in failed_experts:
            selected_expert = expert
            break

    # Build remaining fallback chain excluding failed and selected
    fallback_chain = [
        e for e in fallback_order
        if e != selected_expert and e not in failed_experts
    ]

    return MoeRoutingDecision(
        decision_id=f"moe-{router.name}-{input_hash[:8]}",
        input_hash=input_hash,
        selected_expert=selected_expert,
        confidence=0.5 if selected_expert == fallback_order[0] else 0.3,
        alternatives=[e for e in fallback_order if e != selected_expert],
        routing_reason=(
            f"Fallback routing for router '{router.name}': "
            f"selected '{selected_expert}' (chain={fallback_order}, "
            f"failed={sorted(failed_experts)})"
        ),
        fallback_chain=fallback_chain,
    )


# ── Ensemble Routing ────────────────────────────────────────────────────────

def ensemble_route(
    prompt: str,
    routers: list[ExpertRouter],
    context: dict[str, Any] | None = None,
) -> list[MoeRoutingDecision]:
    """Route a prompt through multiple routers and aggregate results.

    Each router produces its own decision; the caller can resolve conflicts
    via majority vote, highest confidence, or custom aggregation.

    Args:
        prompt: The user prompt to route.
        routers: List of ExpertRouter configurations.
        context: Optional context dict.

    Returns:
        List of MoeRoutingDecision, one per router.
    """
    ctx = context or {}
    decisions: list[MoeRoutingDecision] = []
    for router in routers:
        decision = route_to_expert(prompt, router, ctx)
        decisions.append(decision)
    return decisions


# ── Fallback Graph ──────────────────────────────────────────────────────────

def build_fallback_graph(
    routers: list[ExpertRouter],
) -> dict[str, list[str]]:
    """Build an adjacency graph of fallback dependencies across routers.

    Each router contributes edges from its primary expert to each fallback
    expert.  Circular dependencies are detected and reported as a ValueError.

    Args:
        routers: List of ExpertRouter configurations.

    Returns:
        Adjacency dict mapping each expert → list of fallback experts.

    Raises:
        ValueError: If a circular dependency is detected in the fallback graph.
    """
    graph: dict[str, list[str]] = defaultdict(list)
    all_experts: set[str] = set()

    for router in routers:
        all_experts.update(router.experts)
        experts = router.experts
        fallback = router.fallback_order if router.fallback_order else experts
        for i, src in enumerate(fallback):
            for dst in fallback[i + 1:]:
                if dst not in graph.get(src, []):
                    graph[src].append(dst)

    # Detect cycles via DFS
    _detect_cycles(graph)

    # Ensure all experts appear as keys (even with no outgoing edges)
    for expert in all_experts:
        if expert not in graph:
            graph[expert] = []

    return dict(graph)


def _detect_cycles(graph: dict[str, list[str]]) -> None:
    """Raise ValueError if the directed graph contains any cycle."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}

    def _dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in color:
                color[neighbor] = WHITE
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                cycle = " → ".join(path[cycle_start:] + [neighbor])
                raise ValueError(f"Circular fallback dependency detected: {cycle}")
            if color[neighbor] == WHITE:
                _dfs(neighbor, path)
        path.pop()
        color[node] = BLACK

    for node in list(graph.keys()):
        if color.get(node) == WHITE:
            _dfs(node, [])


# ── Validation ─────────────────────────────────────────────────────────────

def validate_gating_decision(decision: MoeRoutingDecision) -> bool:
    """Validate a routing decision has a valid expert in its router's expert list.

    This is a lightweight integrity check. For full validation (including
    verifying the selected expert was defined in the router's experts),
    the caller must pass the router explicitly. This function validates:
      - decision_id is non-empty
      - input_hash is non-empty
      - selected_expert is non-empty
      - confidence is in [0, 1]
      - latency_ms is non-negative

    Args:
        decision: The MoeRoutingDecision to validate.

    Returns:
        True if the decision passes all integrity checks.
    """
    if not decision.decision_id:
        logger.warning("MoeRoutingDecision has empty decision_id")
        return False
    if not decision.input_hash:
        logger.warning("MoeRoutingDecision has empty input_hash")
        return False
    if not decision.selected_expert:
        logger.warning("MoeRoutingDecision has empty selected_expert")
        return False
    if not (0.0 <= decision.confidence <= 1.0):
        logger.warning(
            "MoeRoutingDecision confidence %s out of [0,1] range",
            decision.confidence,
        )
        return False
    if decision.latency_ms < 0:
        logger.warning(
            "MoeRoutingDecision latency_ms %s is negative",
            decision.latency_ms,
        )
        return False
    return True


def validate_gating_decision_against_router(
    decision: MoeRoutingDecision,
    router: ExpertRouter,
) -> bool:
    """Validate that the decision's selected_expert is in the router's expert list.

    Args:
        decision: The MoeRoutingDecision to validate.
        router: The ExpertRouter that produced it.

    Returns:
        True if selected_expert is in router.experts.
    """
    if not validate_gating_decision(decision):
        return False
    if decision.selected_expert not in router.experts:
        logger.warning(
            "MoeRoutingDecision selected_expert '%s' not in router.experts %s",
            decision.selected_expert,
            router.experts,
        )
        return False
    return True


# ── Model Gateway Integration ───────────────────────────────────────────────

class MoeModelGateway:
    """Lightweight MoE routing wrapper for model_gateway.ModelGateway.

    Wraps an existing ModelGateway instance and adds expert routing
    decisions before dispatching to the underlying gateway.

    Usage:
        from hlf_source.agents.core.model_gateway import ModelGateway
        base_gateway = ModelGateway.from_config()
        router = ExpertRouter(
            name="coding",
            experts=["devstral-2:123b", "qwen3-coder:480b", "qwen3:8b"],
            gating_model="qwen3:8b",
        )
        moe_gateway = MoeModelGateway(base_gateway, router)
        result = moe_gateway.route_and_execute(
            "Write a Python function to sort a list",
        )
    """

    def __init__(
        self,
        base_gateway: Any,  # model_gateway.ModelGateway
        expert_router: ExpertRouter,
    ) -> None:
        self._base = base_gateway
        self._router = expert_router
        self._decision_log: list[MoeRoutingDecision] = []

    @property
    def router(self) -> ExpertRouter:
        return self._router

    @property
    def decision_log(self) -> list[MoeRoutingDecision]:
        return list(self._decision_log)

    def route_and_execute(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Route the prompt to the best expert and execute through base gateway.

        Args:
            prompt: The user prompt.
            context: Optional routing context (failed experts, session state).
            **kwargs: Forwarded to the base gateway's chat handler.

        Returns:
            Dict with 'decision', 'model', and 'response' keys.
              - 'decision': MoeRoutingDecision dict
              - 'model': selected expert model ID
              - 'response': raw response from base gateway
        """
        decision = route_to_expert(prompt, self._router, context)
        self._decision_log.append(decision)

        # Attempt execution through base gateway, with fallback
        last_error: Exception | None = None
        experts_to_try = [decision.selected_expert] + decision.fallback_chain

        for attempt_idx, expert in enumerate(experts_to_try[:self._router.max_retries + 1]):
            try:
                # Try to dispatch through base gateway's chat handler
                if hasattr(self._base, "handle_chat_completion"):
                    response = self._base.handle_chat_completion({
                        "model": expert,
                        "messages": [{"role": "user", "content": prompt}],
                        **kwargs,
                    })
                elif hasattr(self._base, "route"):
                    routing = self._base._router.route(expert)
                    response = {"model": expert, "routing": routing}
                else:
                    # Minimal fallback: just return the decision
                    response = {"model": expert, "note": "base gateway has no chat handler"}

                return {
                    "decision": decision.to_dict(),
                    "model": expert,
                    "response": response,
                }
            except Exception as exc:
                last_error = exc
                logger.debug(
                    "MoE fallback: expert '%s' failed (attempt %d/%d): %s",
                    expert, attempt_idx + 1, self._router.max_retries + 1, exc,
                )
                continue

        raise RuntimeError(
            f"MoE routing exhausted all experts for router '{self._router.name}'. "
            f"Last error: {last_error}"
        )
