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
    """
    orchestration: OrchestrationResult
    verdict: GovernedRouteVerdict
    task_envelope: TaskEnvelope
    advisory_mode: bool = False
    governance_warning: str = ""
    latency_s: float = 0.0

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

    return GovernedCompletionResult(
        orchestration=result,
        verdict=verdict,
        task_envelope=envelope,
        advisory_mode=advisory_mode,
        governance_warning=governance_warning,
        latency_s=round(time.monotonic() - t0, 3),
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
