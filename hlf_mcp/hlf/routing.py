"""
HLF Routing Fabric — deterministic model-route selection engine.

Faithful port of the MoMA Router (hlf_source/agents/gateway/router.py) into
the hlf_mcp package boundary.  Preserves the original semantics:

  * Deterministic route selection via tier-walk and complexity short-circuit
  * Evidence-backed fallback: Cloud Tier Walk → Local Inventory → OpenRouter → ultimate
  * Fail-closed on insufficient evidence (allowlist denial, trust restriction)
  * Lane-family routing with specialization pattern matching
  * Route rationale exposure through trace records and confidence scoring

This module is the *model-level* routing surface.  Governance-level routing
(trust states, ALIGN, hardware constraints → lane decisions) lives in
governed_routing.py.  Trace record keeping lives in routing_trace.py.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Tier walk order — Cloud-First isolation invariant ──────────────────────
# Highest-capability tier first; selection stops at the first tier that yields
# a reachable, allow-listed candidate.
_TIER_WALK_ORDER: tuple[str, ...] = ("S", "A+", "A", "A-", "B+", "B", "C", "D")

# ── Specialization patterns ────────────────────────────────────────────────
# Intent keywords that trigger a specialization override *before* the tier walk.
_SPECIALIZATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "coding": (
        "code", "debug", "refactor", "compile", "ast", "symbol", "lint",
        "patch", "implement", "fix", "review",
    ),
    "visual": (
        "image", "ocr", "visual", "screenshot", "photo", "diagram",
        "chart", "graph", "plot",
    ),
    "reasoning": (
        "reason", "plan", "analyse", "analyze", "decompose", "strategy",
        "architecture", "design",
    ),
    "execution": (
        "run", "execute", "deploy", "build", "test", "apply",
    ),
}

# ── VRAM check cache ───────────────────────────────────────────────────────
_vram_cache: dict[str, Any] = {"result": True, "expires": 0.0}
_VRAM_CACHE_TTL: float = 30.0


# ── Route profile ──────────────────────────────────────────────────────────

@dataclass
class RouteProfile:
    """Deterministic route selection result.

    Replaces the bare model-name string with a rich profile that includes
    the full selection trace, confidence score, and evidence references.
    """

    model: str
    provider: str = "ollama"
    tier: str = "D"
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    restrictions: dict[str, Any] = field(default_factory=dict)
    routing_trace: list[dict[str, Any]] = field(default_factory=list)
    gas_remaining: int = -1
    confidence: float = 0.5

    @property
    def rationale(self) -> list[str]:
        """Reconstruct human-readable rationale from the routing trace."""
        lines: list[str] = []
        for step in self.routing_trace:
            step_name = step.get("step", "")
            if step_name == "specialization":
                lines.append(
                    f"Specialization '{step.get('match')}' matched keywords: "
                    f"{step.get('keywords', [])}"
                )
            elif step_name == "complexity_shortcircuit":
                lines.append(
                    f"Complexity short-circuit: score={step.get('score')}, "
                    f"target={step.get('target')}"
                )
            elif step_name == "tier_walk":
                lines.append(
                    f"Tier '{step.get('tier')}' had {step.get('candidates', 0)} candidates"
                )
            elif step_name == "selected":
                lines.append(
                    f"Selected '{step.get('model')}' via {step.get('phase', 'unknown')} "
                    f"(tier {step.get('tier', '?')})"
                )
            elif step_name == "fallback":
                lines.append(
                    f"Fallback to '{step.get('model')}': {step.get('reason')}"
                )
            elif step_name == "allowlist_blocked":
                lines.append(
                    f"Model '{step.get('model')}' blocked by allowlist for tier "
                    f"'{step.get('tier')}'"
                )
            elif step_name == "allowlist_fallback":
                lines.append(
                    f"Allowlist fallback to '{step.get('model')}'"
                )
            elif step_name == "allowlist_deterministic":
                lines.append(
                    f"Deterministic allowlist selection: '{step.get('model')}'"
                )
            elif step_name == "evidence_required_denial":
                lines.append(
                    f"Evidence-required denial: {step.get('reason')}"
                )
            else:
                lines.append(f"{step_name}: {step}")
        return lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "provider": self.provider,
            "tier": self.tier,
            "system_prompt": self.system_prompt,
            "tools": list(self.tools),
            "restrictions": dict(self.restrictions),
            "routing_trace": list(self.routing_trace),
            "gas_remaining": self.gas_remaining,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


# ── Cloud detection ────────────────────────────────────────────────────────

def _is_cloud(model: str) -> bool:
    """Return True if *model* is a cloud-hosted Ollama model."""
    return model.endswith(":cloud") or model.endswith("-cloud")


# ── Model allowlist ────────────────────────────────────────────────────────

def _normalize_model_name(name: str) -> str:
    """Normalize a model name to canonical form for exact comparison."""
    name = name.lower()
    for suffix in (":cloud", "-cloud", ":latest"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.replace(":", "-")


def is_model_allowed(
    model: str,
    tier: str,
    *,
    allowed_models: set[str] | None = None,
    settings_path: Path | None = None,
) -> bool:
    """Check if *model* is in the allowlist for *tier*.

    Normalizes model names before comparing:
      - Strips ':cloud' / '-cloud' suffix
      - Strips ':latest' tag suffix
      - Replaces ':' with '-' for consistent comparison
      - Uses EXACT match on normalized canonical form

    Args:
        model: Model name to check.
        tier: Deployment tier (e.g. "hearth", "forge", "sovereign").
        allowed_models: Pre-loaded allowed set; loaded from settings if None.
        settings_path: Path to settings.json; defaults to repo config.

    Returns:
        True if the model is allowed or the allowlist is empty (fail-open).
    """
    if allowed_models is None:
        allowed_models = _load_allowed_models(tier, settings_path=settings_path)
    if not allowed_models:
        return True  # fail-open

    norm_model = _normalize_model_name(model)
    return any(
        _normalize_model_name(allowed) == norm_model
        for allowed in allowed_models
    )


def _load_allowed_models(
    tier: str,
    *,
    settings_path: Path | None = None,
) -> set[str]:
    """Load the ollama_allowed_models for *tier* from settings.json."""
    if settings_path is None:
        settings_path = (
            Path(__file__).resolve().parents[2] / "config" / "settings.json"
        )
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        allowed = data.get("ollama_allowed_models", {})
        models = allowed.get(tier, [])
        return {m.lower() for m in models}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def _pick_deterministic_from_allowlist(
    tier: str,
    *,
    settings_path: Path | None = None,
) -> str | None:
    """Return the first sorted model from the allowlist for *tier*."""
    allowed = _load_allowed_models(tier, settings_path=settings_path)
    if not allowed:
        return None
    return sorted(allowed)[0]


# ── VRAM threshold ─────────────────────────────────────────────────────────

def check_vram_threshold(
    model: str,
    *,
    client: httpx.Client | None = None,
    ollama_host: str = "http://localhost:11434",
    ollama_host_secondary: str = "",
) -> bool:
    """Return True if *model* can be loaded (VRAM < 80% or model is cloud).

    Cloud models skip VRAM check entirely.  Results are cached for 30s.
    """
    if _is_cloud(model):
        return True

    global _vram_cache
    if time.time() < _vram_cache["expires"]:
        return bool(_vram_cache["result"])

    hosts = [ollama_host]
    if ollama_host_secondary:
        hosts.append(ollama_host_secondary)

    result = True  # fail-open default
    for host in hosts:
        try:
            c = client or httpx.Client(timeout=12.0)
            resp = c.get(f"{host}/api/ps")
            if resp.status_code != 200:
                continue
            data = resp.json()
            models = data.get("models", [])
            if not models:
                result = True
                break
            total_vram = sum(m.get("size_vram", 0) for m in models)
            multiplier = int(os.environ.get("VRAM_CAPACITY_MULTIPLIER", "5"))
            max_vram = max(m.get("size_vram", 0) for m in models) * multiplier
            if max_vram == 0:
                result = True
                break
            result = (total_vram / max_vram) < 0.80
            break
        except Exception:
            continue

    _vram_cache["result"] = result
    _vram_cache["expires"] = time.time() + _VRAM_CACHE_TTL
    return bool(result)


# ── Complexity scoring ─────────────────────────────────────────────────────

def complexity_score(hlf_payload: str, ast: dict | None = None) -> float:
    """Compute a rough complexity score 𝕔 ∈ [0, 1] for routing decisions.

    Simple heuristic based on:
      - AST node count (normalized to [0, 0.5])
      - Keyword density for reasoning/planning terms (normalized to [0, 0.3])
      - Program length in characters (normalized to [0, 0.2])

    Returns a float in [0.0, 1.0].
    """
    score = 0.0

    # AST node count contribution
    program = (ast or {}).get("program", [])
    node_count = len(program) if isinstance(program, list) else 0
    score += min(node_count / 40.0, 0.5)

    # Reasoning keyword density
    reasoning_keywords = (
        "reason", "plan", "analyse", "analyze", "prove", "verify",
        "decompose", "strategy", "architecture", "design", "optimize",
        "refactor", "implement",
    )
    text_lower = hlf_payload.lower()
    keyword_hits = sum(1 for kw in reasoning_keywords if kw in text_lower)
    score += min(keyword_hits * 0.05, 0.3)

    # Length contribution
    score += min(len(hlf_payload) / 10000.0, 0.2)

    return round(min(score, 1.0), 3)


# ── Legacy intent-based routing ────────────────────────────────────────────

def route_intent(
    intent_text: str,
    ast: dict | None = None,
    *,
    primary_model: str = "qwen3.5:cloud",
    reasoning_model: str = "glm-5:cloud",
    summarization_model: str = "qwen3:8b",
) -> str:
    """Return the model name appropriate for this intent.

    Simple keyword-based fallback router used when the registry/catalog
    is unavailable.
    """
    text_lower = intent_text.lower()

    # Visual / multimodal intents → primary (strongest model)
    if any(
        kw in text_lower
        for kw in ("image", "ocr", "visual", "screenshot", "photo", "diagram")
    ):
        return primary_model

    # Reasoning / planning intents → reasoning model
    if any(
        kw in text_lower
        for kw in (
            "reason", "plan", "analyse", "analyze", "strategy",
            "architecture", "design", "decompose",
        )
    ):
        return reasoning_model

    # Coding / engineering intents
    if any(
        kw in text_lower
        for kw in ("code", "debug", "symbol", "compile", "ast", "lint", "refactor")
    ):
        return reasoning_model

    # Default to summarization / lightweight model
    return summarization_model


# ── Deterministic route selection ──────────────────────────────────────────

def select_model_by_tier(
    candidates: list[dict[str, Any]],
    *,
    prefer_cloud: bool = True,
    ollama_host: str = "http://localhost:11434",
    ollama_host_secondary: str = "",
) -> dict[str, Any] | None:
    """Select the best reachable model from *candidates*.

    If *prefer_cloud* is True, skips local-only models that don't pass
    VRAM threshold.  Returns the first reachable candidate or None.
    """
    for candidate in candidates:
        model_id = candidate.get("model_id", candidate.get("name", ""))
        if not model_id:
            continue
        if prefer_cloud and not _is_cloud(model_id):
            if not check_vram_threshold(
                model_id,
                ollama_host=ollama_host,
                ollama_host_secondary=ollama_host_secondary,
            ):
                continue
        return {"model_id": model_id, **candidate}
    return None


def route_request(
    intent_text: str,
    ast: dict | None = None,
    *,
    metadata: dict[str, Any] | None = None,
    complexity: float | None = None,
    # ── Configuration injection points ──────────────────────────────────
    tier: str = "hearth",
    primary_model: str = "qwen3.5:cloud",
    reasoning_model: str = "glm-5:cloud",
    summarization_model: str = "qwen3:8b",
    ollama_host: str = "http://localhost:11434",
    ollama_host_secondary: str = "",
    settings_path: Path | None = None,
    # ── Catalog / registry injection ────────────────────────────────────
    catalog: dict[str, Any] | None = None,
    get_models_by_tier: Any = None,
    get_local_inventory: Any = None,
    get_equivalents: Any = None,
) -> RouteProfile:
    """Deterministic 3-Phase Tier Walk router.

    Returns a full :class:`RouteProfile` with model, provider, tier,
    routing trace, and confidence.

    Phase 0: Complexity Short-Circuit — 𝕔 < 0.3 → SLM, 𝕔 > 0.7 → frontier
    Phase 1: Cloud Tier Walk — walk tier ordering, select first reachable
    Phase 2: Local Inventory Fallback — if cloud walk exhausted
    Phase 3: OpenRouter / ultimate fallback — if both cloud and local fail

    Falls back to :func:`route_intent` if catalog data is unavailable.
    """
    trace: list[dict[str, Any]] = []
    text_lower = intent_text.lower()
    _ = metadata  # reserved for future context injection

    # ── Compute complexity if not provided ──────────────────────────────
    if complexity is None:
        complexity = complexity_score(intent_text, ast)

    # ── Specialization pre-routing ──────────────────────────────────────
    specialization: str | None = None
    for spec_name, keywords in _SPECIALIZATION_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            specialization = spec_name
            trace.append({
                "step": "specialization",
                "match": spec_name,
                "keywords": list(keywords),
            })
            break

    # ── Phase 0: Complexity Short-Circuit ───────────────────────────────
    if specialization is None:
        if complexity < 0.3:
            trace.append({
                "step": "complexity_shortcircuit",
                "score": complexity,
                "target": "slm",
            })
            model = summarization_model
            if is_model_allowed(model, tier, settings_path=settings_path):
                return RouteProfile(
                    model=model,
                    provider="cloud" if _is_cloud(model) else "ollama",
                    tier="slm",
                    routing_trace=trace,
                    confidence=0.85,
                )
            # Fall through to full routing if SLM is allowlist-blocked
            trace.append({
                "step": "allowlist_blocked",
                "model": model,
                "tier": tier,
            })
        elif complexity > 0.7:
            trace.append({
                "step": "complexity_shortcircuit",
                "score": complexity,
                "target": "frontier",
            })
            model = primary_model
            if is_model_allowed(model, tier, settings_path=settings_path):
                return RouteProfile(
                    model=model,
                    provider="cloud" if _is_cloud(model) else "ollama",
                    tier="S",
                    routing_trace=trace,
                    confidence=0.9,
                )
            trace.append({
                "step": "allowlist_blocked",
                "model": model,
                "tier": tier,
            })
        else:
            trace.append({
                "step": "complexity_midrange",
                "score": complexity,
            })

    # ── Phase 1: Tier Walk ──────────────────────────────────────────────
    selected_model: str | None = None
    selected_tier: str | None = None

    if get_models_by_tier is not None:
        for walk_tier in _TIER_WALK_ORDER:
            try:
                candidates = get_models_by_tier(walk_tier)
            except Exception:
                candidates = []
            trace.append({
                "step": "tier_walk",
                "tier": walk_tier,
                "candidates": len(candidates),
            })

            selected = select_model_by_tier(
                candidates,
                prefer_cloud=True,
                ollama_host=ollama_host,
                ollama_host_secondary=ollama_host_secondary,
            )
            if selected is not None:
                selected_model = selected["model_id"]
                selected_tier = walk_tier
                trace.append({
                    "step": "selected",
                    "phase": "cloud",
                    "model": selected_model,
                    "tier": walk_tier,
                })
                break

    # ── Phase 2: Local Inventory Fallback ───────────────────────────────
    if selected_model is None and get_local_inventory is not None:
        try:
            local_models = get_local_inventory()
        except Exception:
            local_models = []
        trace.append({
            "step": "local_fallback",
            "available": len(local_models),
        })
        if local_models:
            selected_model = local_models[0].get(
                "model_id", local_models[0].get("name", "")
            )
            selected_tier = "local"
            trace.append({
                "step": "selected",
                "phase": "local",
                "model": selected_model,
            })

    # ── Phase 3: OpenRouter / ultimate fallback ─────────────────────────
    if selected_model is None and get_equivalents is not None:
        try:
            equivs = get_equivalents(primary_model)
        except Exception:
            equivs = []
        or_hit = next(
            (e for e in equivs if e.get("provider") == "openrouter"), None
        )
        if or_hit:
            selected_model = or_hit.get("provider_model_id", "")
            selected_tier = "openrouter"
            trace.append({
                "step": "selected",
                "phase": "openrouter",
                "model": selected_model,
            })

    # ── Ultimate fallback ───────────────────────────────────────────────
    if selected_model is None:
        selected_model = route_intent(
            intent_text,
            ast,
            primary_model=primary_model,
            reasoning_model=reasoning_model,
            summarization_model=summarization_model,
        )
        selected_tier = "fallback"
        trace.append({
            "step": "fallback",
            "reason": "all_phases_exhausted",
            "model": selected_model,
        })

    # ── Specialization override ─────────────────────────────────────────
    if specialization == "coding":
        coding_model = reasoning_model
        if get_local_inventory is not None:
            try:
                local = get_local_inventory()
                coding_candidates = [
                    m.get("model_id", m.get("name", ""))
                    for m in local
                    if "devstral" in m.get("model_id", m.get("name", "")).lower()
                ]
                if coding_candidates:
                    coding_model = coding_candidates[0]
            except Exception:
                pass
        selected_model = coding_model
        trace.append({
            "step": "override",
            "specialization": "coding",
            "model": selected_model,
        })
        selected_tier = "coding-specialist"
    elif specialization == "visual":
        selected_model = primary_model
        trace.append({
            "step": "override",
            "specialization": "visual",
            "model": selected_model,
        })
        selected_tier = "visual-specialist"
    elif specialization == "reasoning":
        selected_model = reasoning_model
        trace.append({
            "step": "override",
            "specialization": "reasoning",
            "model": selected_model,
        })
        selected_tier = "reasoning-specialist"

    # ── Model allowlist gate ────────────────────────────────────────────
    if not is_model_allowed(selected_model, tier, settings_path=settings_path):
        trace.append({
            "step": "allowlist_blocked",
            "model": selected_model,
            "tier": tier,
        })
        fallback = summarization_model
        if is_model_allowed(fallback, tier, settings_path=settings_path):
            selected_model = fallback
            selected_tier = "allowlist_fallback"
            trace.append({
                "step": "allowlist_fallback",
                "model": selected_model,
            })
        else:
            deterministic = _pick_deterministic_from_allowlist(
                tier, settings_path=settings_path
            )
            if deterministic:
                selected_model = deterministic
                selected_tier = "allowlist_deterministic"
                trace.append({
                    "step": "allowlist_deterministic",
                    "model": selected_model,
                })
            else:
                trace.append({
                    "step": "allowlist_empty_failopen",
                })

    # ── Determine provider ──────────────────────────────────────────────
    provider = "ollama"
    if _is_cloud(selected_model):
        provider = "cloud"
    elif selected_tier == "openrouter":
        provider = "openrouter"

    # ── Confidence scoring ──────────────────────────────────────────────
    if selected_tier in ("S", "A+", "A"):
        confidence = 0.9
    elif selected_tier in ("A-", "B+"):
        confidence = 0.7
    elif selected_tier in ("B", "C"):
        confidence = 0.6
    elif selected_tier == "fallback":
        confidence = 0.3
    elif selected_tier in (
        "allowlist_fallback",
        "allowlist_deterministic",
    ):
        confidence = 0.4
    else:
        confidence = 0.5

    return RouteProfile(
        model=selected_model,
        provider=provider,
        tier=selected_tier or "D",
        routing_trace=trace,
        confidence=confidence,
    )


# ── Evidence-required denial ───────────────────────────────────────────────

def require_evidence_gate(
    profile: RouteProfile,
    *,
    require_benchmark_evidence: bool = False,
    require_catalog_entry: bool = False,
    available_benchmark_scores: dict[str, float] | None = None,
    minimum_benchmark_scores: dict[str, float] | None = None,
) -> RouteProfile:
    """Post-process a RouteProfile with an evidence-required gate.

    If evidence requirements are not met, the profile is replaced with
    a denial profile that exposes the missing evidence in the trace.

    Args:
        profile: The route profile to gate.
        require_benchmark_evidence: If True, benchmark scores must satisfy minimums.
        require_catalog_entry: If True, the model must have a catalog entry.
        available_benchmark_scores: Actual benchmark scores for the model.
        minimum_benchmark_scores: Required minimum benchmark scores.

    Returns:
        The original profile if evidence is sufficient, or a denial profile.
    """
    if not require_benchmark_evidence and not require_catalog_entry:
        return profile

    denial_reasons: list[str] = []

    if require_catalog_entry and profile.tier == "fallback":
        denial_reasons.append(
            "Catalog entry required but model was resolved via ultimate fallback"
        )

    if require_benchmark_evidence and minimum_benchmark_scores:
        scores = available_benchmark_scores or {}
        for bench_name, min_score in minimum_benchmark_scores.items():
            actual = scores.get(bench_name)
            if actual is None:
                denial_reasons.append(
                    f"Missing benchmark '{bench_name}' (required minimum: {min_score})"
                )
            elif actual < min_score:
                denial_reasons.append(
                    f"Benchmark '{bench_name}' score {actual} below minimum {min_score}"
                )

    if denial_reasons:
        denial_trace = list(profile.routing_trace)
        denial_trace.append({
            "step": "evidence_required_denial",
            "reason": "; ".join(denial_reasons),
            "required_benchmarks": (
                dict(minimum_benchmark_scores)
                if minimum_benchmark_scores
                else None
            ),
            "available_benchmarks": (
                dict(available_benchmark_scores)
                if available_benchmark_scores
                else None
            ),
        })
        return RouteProfile(
            model="",
            provider="",
            tier="denied",
            routing_trace=denial_trace,
            confidence=0.0,
        )

    return profile


# ── Convenience: full routing pipeline ─────────────────────────────────────

def route_with_fallback(
    intent_text: str,
    ast: dict | None = None,
    *,
    complexity: float | None = None,
    tier: str = "hearth",
    primary_model: str = "qwen3.5:cloud",
    reasoning_model: str = "glm-5:cloud",
    summarization_model: str = "qwen3:8b",
    ollama_host: str = "http://localhost:11434",
    ollama_host_secondary: str = "",
    settings_path: Path | None = None,
    require_benchmark_evidence: bool = False,
    minimum_benchmark_scores: dict[str, float] | None = None,
    available_benchmark_scores: dict[str, float] | None = None,
    # ── Catalog callbacks ───────────────────────────────────────────────
    get_models_by_tier: Any = None,
    get_local_inventory: Any = None,
    get_equivalents: Any = None,
) -> RouteProfile:
    """Run the full routing pipeline: tier-walk selection + evidence gate.

    This is the primary entry point for consumers that need a governed,
    evidence-backed route decision with fallback paths.
    """
    profile = route_request(
        intent_text,
        ast,
        complexity=complexity,
        tier=tier,
        primary_model=primary_model,
        reasoning_model=reasoning_model,
        summarization_model=summarization_model,
        ollama_host=ollama_host,
        ollama_host_secondary=ollama_host_secondary,
        settings_path=settings_path,
        get_models_by_tier=get_models_by_tier,
        get_local_inventory=get_local_inventory,
        get_equivalents=get_equivalents,
    )

    # Apply evidence gate if configured
    if require_benchmark_evidence or minimum_benchmark_scores:
        profile = require_evidence_gate(
            profile,
            require_benchmark_evidence=require_benchmark_evidence,
            require_catalog_entry=require_benchmark_evidence,
            available_benchmark_scores=available_benchmark_scores,
            minimum_benchmark_scores=minimum_benchmark_scores,
        )

    return profile
