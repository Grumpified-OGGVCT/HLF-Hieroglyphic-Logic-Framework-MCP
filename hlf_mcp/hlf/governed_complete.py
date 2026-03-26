"""
Governed Completion Pipeline.

Provides a governed_complete() entry point that runs the full
classify → route → orchestrate pipeline in a single call:

  1. Classifies natural-language intent → TaskEnvelope (task_classifier)
  2. Maps TaskEnvelope → Workload string (workload bridge)
  3. Probes hardware and runtime posture
  4. Builds a GovernedRouteVerdict (governed_routing)
  5. Dispatches to ModelOrchestrator.complete_with_verdict()

This is the Option C bridge: hlf_route_governed_request provides the
lane-selection authority; ModelOrchestrator executes with full
Ollama-primary / OpenRouter-fallback escalation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.governed_routing import GovernedRouteVerdict, build_governed_route
from hlf_mcp.hlf.model_orchestrator import (
    ModelOrchestrationError,
    ModelOrchestrator,
    OrchestrationResult,
)
from hlf_mcp.hlf.task_classifier import (
    TaskEnvelope,
    classify_intent,
    task_envelope_to_workload,
)


logger = logging.getLogger(__name__)

# ── Workload → catalog lane mapping ─────────────────────────────────────────
# Kept in sync with _workload_to_catalog_lane() in server_profiles.py.
_WORKLOAD_TO_LANE: dict[str, str] = {
    # Embedding / retrieval
    "translation_memory":          "retrieval",
    "repair_pattern_recall":       "retrieval",
    "governance_policy_retrieval": "retrieval",
    "code_pattern_retrieval":      "code-generation",
    "agent_routing_context":       "explainer",
    "long_form_standards_ingestion": "standards-ingestion",
    # Completion / generation
    "reasoning_query":   "reasoning",
    "code_completion":   "coding",
    "planning_task":     "planning",
    "analysis_task":     "analysis",
    "doer_task":         "doer",
    "universal_query":   "universal",
    "multimodal_query":  "multimodal",
    "verification_task": "verifier",
    "ethics_review":     "ethics",
}


@dataclass(slots=True)
class GovernedCompletionResult:
    """Result of a governed_complete() call.

    Attributes:
        orchestration: Full OrchestrationResult including content and audit.
        verdict: The GovernedRouteVerdict that authorised the call.
        task_envelope: TaskEnvelope from classify_intent().
        advisory_mode: True when completion proceeded despite a denied verdict.
        governance_warning: Human-readable warning when advisory mode engaged.
        latency_s: Wall-clock time from entry to completion.
        evidence_lineage: Trace linking routing decision → execution → evidence.
    """
    orchestration: OrchestrationResult
    verdict: GovernedRouteVerdict
    task_envelope: TaskEnvelope
    advisory_mode: bool = False
    governance_warning: str = ""
    latency_s: float = 0.0
    evidence_lineage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        workload = task_envelope_to_workload(self.task_envelope)
        return {
            "content": self.orchestration.content,
            "model_used": self.orchestration.model_used,
            "provider_used": self.orchestration.provider_used,
            "lane": self.orchestration.lane,
            "workload": workload,
            "task_type": self.task_envelope.task_type,
            "task_category": self.task_envelope.category,
            "task_size": self.task_envelope.size,
            "advisory_mode": self.advisory_mode,
            "governance_warning": self.governance_warning,
            "verdict": self.verdict.to_dict() if hasattr(self.verdict, "to_dict") else {},
            "escalation_depth": self.orchestration.escalation_depth,
            "latency_s": round(self.latency_s, 3),
            "audit_trail": self.orchestration.audit_trail,
            "evidence_lineage": self.evidence_lineage,
        }


# ---------------------------------------------------------------------------


async def governed_complete(
    intent: str,
    messages: list[dict[str, Any]],
    orchestrator: ModelOrchestrator,
    *,
    system: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
    tools: list[dict[str, Any]] | None = None,
    trust_state: str = "trusted",
    hardware_summary: dict[str, Any] | None = None,
    runtime_status: dict[str, Any] | None = None,
    advisory_fallback: bool = True,
) -> GovernedCompletionResult:
    """Full governed completion pipeline: classify → route → orchestrate.

    Parameters
    ----------
    intent : str
        Natural-language description of what to accomplish.
    messages : list[dict]
        OpenAI-format messages list.
    orchestrator : ModelOrchestrator
        Pre-built orchestrator instance (caller owns lifecycle / close()).
    system : str
        Optional system message to prepend.
    temperature : float | None
        Sampling temperature override.
    max_tokens : int | None
        Maximum tokens override.
    tools : list | None
        OpenAI tool definitions.
    trust_state : str
        Governance trust posture: "trusted", "approved", "watched", etc.
    hardware_summary : dict | None
        Optional hardware context; probed automatically if omitted.
    runtime_status : dict | None
        Optional runtime context; defaults to safe-open posture if omitted.
    advisory_fallback : bool
        When True, continues in advisory mode if routing is denied due to
        missing benchmark evidence. When False, raises on any denial.

    Returns
    -------
    GovernedCompletionResult containing the model response, routing verdict,
    and task classification metadata.
    """
    t0 = time.monotonic()

    # 1. Classify intent → TaskEnvelope → Workload → lane
    envelope = classify_intent(intent)
    workload = task_envelope_to_workload(envelope)
    selected_lane = _WORKLOAD_TO_LANE.get(workload, "universal")

    # 2. Resolve hardware / runtime context
    hw = dict(hardware_summary or {})
    rt = dict(runtime_status or {})
    if not hw:
        hw = {"cpu_only": False, "gpu_vram_gb": 0.0}
    if not rt:
        rt = {"ollama_available": True}

    # 3. Resolve best-effort primary / fallback model names from the
    #    orchestrator's config for the chosen lane.
    primary_model, fallback_model = _pick_models_for_lane(orchestrator, selected_lane)

    # 4. Build routing verdict (lightweight — no full catalog sync here)
    verdict = build_governed_route(
        workload=workload,
        align_status="ok",      # Full ALIGN happens in the MCP tool layer
        align_action="ALLOW",
        trust_state=trust_state,
        hardware_summary=hw,
        runtime_status=rt,
        embedding_recommendation={"model": primary_model, "access_mode": ""},
        fallback_recommendation={"model": fallback_model, "access_mode": ""},
        selected_lane=selected_lane,
    )

    # 5. Orchestrate
    advisory_mode = not verdict.allowed
    governance_warning = ""

    if advisory_mode:
        governance_warning = (
            f"Routing verdict denied ({verdict.governance_mode}); "
            f"attempting advisory completion for lane '{selected_lane}'."
        )
        if not advisory_fallback:
            raise ModelOrchestrationError(
                f"Routing verdict denied: {verdict.decision}",
                lane=selected_lane,
                audit_trail=[],
            )

    result = await orchestrator.complete_with_verdict(
        verdict,
        messages,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        advisory_fallback=advisory_fallback,
    )

    # Build evidence lineage: links routing decision → execution → outcome
    evidence_lineage = _build_evidence_lineage(
        task_envelope=envelope,
        verdict=verdict,
        result=result,
        workload=workload,
        selected_lane=selected_lane,
        advisory_mode=advisory_mode,
    )

    # Persist evidence fact to governed metrics substrate
    latency_s = round(time.monotonic() - t0, 3)
    try:
        from hlf.mcp_metrics import get_metrics
        get_metrics().record_evidence_fact(
            task_type=envelope.task_type,
            task_category=envelope.category,
            task_size=envelope.size,
            workload_string=workload,
            selected_lane=selected_lane,
            routing_decision=verdict.decision,
            routing_allowed=verdict.allowed,
            predicted_primary_model=verdict.primary_model,
            actual_model_used=result.model_used,
            actual_provider_used=result.provider_used,
            predicted_primary_matched=(result.model_used == verdict.primary_model),
            escalation_depth=result.escalation_depth,
            escalation_attempts=len(result.audit_trail),
            advisory_mode=advisory_mode,
            governance_mode=verdict.governance_mode,
            deployment_tier=verdict.deployment_tier,
            latency_s=latency_s,
            rationale="; ".join(verdict.rationale) if isinstance(verdict.rationale, list) else verdict.rationale,
            policy_constraints="; ".join(verdict.policy_constraints) if isinstance(verdict.policy_constraints, list) else verdict.policy_constraints,
        )
    except Exception as exc:
        logger.debug("Evidence fact recording skipped: %s", exc)

    return GovernedCompletionResult(
        orchestration=result,
        verdict=verdict,
        task_envelope=envelope,
        advisory_mode=advisory_mode,
        governance_warning=governance_warning,
        latency_s=round(time.monotonic() - t0, 3),
        evidence_lineage=evidence_lineage,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pick_models_for_lane(
    orchestrator: ModelOrchestrator, lane: str
) -> tuple[str, str]:
    """Return (primary, fallback) model names from the orchestrator config."""
    try:
        from hlf_mcp.hlf.model_config import escalation_chain_for_lane
        chain = escalation_chain_for_lane(orchestrator._config, lane)
        if not chain:
            return "", ""
        primary = chain[0].name
        fallback = chain[1].name if len(chain) > 1 else primary
        return primary, fallback
    except Exception:
        return "", ""


def _build_evidence_lineage(
    *,
    task_envelope: TaskEnvelope,
    verdict: GovernedRouteVerdict,
    result: OrchestrationResult,
    workload: str,
    selected_lane: str,
    advisory_mode: bool,
) -> dict[str, Any]:
    """Build evidence lineage connecting routing decision → execution → outcome.
    
    This lineage is used to:
    1. Prove the path from intent classification to final result
    2. Track whether execution matched routing predictions
    3. Support governed evidence facts with full audit trail
    4. Enable promotion/demotion of HKS exemplars based on fidelity
    """
    from hlf_mcp.hlf.task_classifier import TASK_TYPE_REGISTRY

    task_type = task_envelope.task_type
    task_metadata = TASK_TYPE_REGISTRY.get(task_type, {})

    return {
        # Classification layer (intent → task type)
        "task_type": task_type,
        "task_category": task_envelope.category,
        "task_size": task_envelope.size,
        "estimated_gas": task_envelope.estimated_gas,
        "fast_path": task_envelope.fast_path,
        "task_agent": task_metadata.get("agent", "unknown"),

        # Routing layer (task type → lane decision)
        "routing_decision": verdict.decision,
        "selected_lane": selected_lane,
        "workload_string": workload,
        "governance_mode": verdict.governance_mode,
        "align_action": verdict.align_action,
        "deployment_tier": verdict.deployment_tier,
        "routing_allowed": verdict.allowed,
        "review_required": verdict.review_required,

        # Decision rationale (why this lane?)
        "rationale": verdict.rationale,
        "policy_constraints": verdict.policy_constraints,

        # Model selection (which models authorized?)
        "predicted_primary_model": verdict.primary_model,
        "predicted_fallback_model": verdict.fallback_model,
        "predicted_primary_access": verdict.primary_access_mode,
        "predicted_fallback_access": verdict.fallback_access_mode,

        # Execution layer (what actually happened?)
        "actual_model_used": result.model_used,
        "actual_provider_used": result.provider_used,
        "actual_lane_used": result.lane,
        "escalation_depth": result.escalation_depth,
        "escalation_attempts": len(result.audit_trail),

        # Advisory tracking (did we bypass governance?)
        "advisory_mode": advisory_mode,

        # Matching prediction to execution
        "predicted_primary_matched": result.model_used == verdict.primary_model,
        "used_primary_model": result.escalation_depth <= 1,
        "used_fallback_model": result.escalation_depth > 1,
    }
