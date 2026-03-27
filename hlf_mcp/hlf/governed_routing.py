from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RoutingDecision = Literal[
    "deny",
    "deterministic_local_only",
    "advisory_local_retrieval",
    "governed_multilingual_gpu",
    "governed_long_context_gpu",
    "governed_cloud_completion",  # completion / generation workloads via Ollama Cloud
]

# Workloads that drive LLM completion rather than embedding/retrieval.
# Kept in sync with _COMPLETION_WORKLOADS in server_profiles.py.
_COMPLETION_WORKLOAD_KEYS: frozenset[str] = frozenset({
    "reasoning_query",
    "code_completion",
    "planning_task",
    "analysis_task",
    "doer_task",
    "universal_query",
    "multimodal_query",
    "verification_task",
    "ethics_review",
})


@dataclass(slots=True)
class GovernedRouteVerdict:
    allowed: bool
    decision: RoutingDecision
    governance_mode: str
    review_required: bool
    selected_lane: str
    primary_model: str
    fallback_model: str
    primary_access_mode: str = ""
    fallback_access_mode: str = ""
    align_action: str = "ALLOW"
    deployment_tier: str = ""
    allowlist_policy: dict[str, Any] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    policy_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        justification = {
            "allowance_state": "allowed" if self.allowed else "denied",
            "decision": self.decision,
            "selected_lane": self.selected_lane,
            "governance_mode": self.governance_mode,
            "review_required": self.review_required,
            "align_action": self.align_action,
            "deployment_tier": self.deployment_tier,
            "rationale_count": len(self.rationale),
            "constraint_count": len(self.policy_constraints),
            "primary_reason": self.rationale[0] if self.rationale else "",
            "primary_constraint": self.policy_constraints[0] if self.policy_constraints else "",
        }
        return {
            "allowed": self.allowed,
            "decision": self.decision,
            "governance_mode": self.governance_mode,
            "review_required": self.review_required,
            "selected_lane": self.selected_lane,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "primary_access_mode": self.primary_access_mode,
            "fallback_access_mode": self.fallback_access_mode,
            "align_action": self.align_action,
            "deployment_tier": self.deployment_tier,
            "allowlist_policy": dict(self.allowlist_policy),
            "rationale": self.rationale,
            "policy_constraints": self.policy_constraints,
            "justification": justification,
        }


def build_governed_route(
    *,
    workload: str,
    align_status: str,
    align_action: str = "ALLOW",
    trust_state: str,
    hardware_summary: dict[str, Any],
    runtime_status: dict[str, Any],
    embedding_recommendation: dict[str, Any],
    fallback_recommendation: dict[str, Any],
    selected_lane: str = "retrieval",
    lane_candidate_summary: dict[str, Any] | None = None,
) -> GovernedRouteVerdict:
    primary_model = str(embedding_recommendation.get("model", ""))
    fallback_model = str(fallback_recommendation.get("model", ""))
    primary_access_mode = str(embedding_recommendation.get("access_mode", ""))
    fallback_access_mode = str(fallback_recommendation.get("access_mode", ""))
    cpu_only = bool(hardware_summary.get("cpu_only", False))
    gpu_vram_gb = float(hardware_summary.get("gpu_vram_gb") or 0.0)
    ollama_available = bool(runtime_status.get("ollama_available", False))
    normalized_trust_state = trust_state.strip().lower() or "trusted"

    rationale: list[str] = [
        "Routing stays deterministic-first and audit-bound even when semantic retrieval is available.",
    ]
    constraints: list[str] = [
        "Governed routing cannot override an ALIGN block verdict.",
        "Embedding selection remains subordinate to policy, audit, and operator review requirements.",
    ]
    if lane_candidate_summary:
        preferred = lane_candidate_summary.get("preferred") or {}
        preferred_access_mode = str(preferred.get("access_mode", primary_access_mode))
        rationale.append(
            f"Routing selected the {selected_lane} lane from the synced model catalog and preferred {preferred_access_mode or 'packaged'} candidates over profile-only heuristics."
        )

    if align_status == "blocked":
        rationale.append(
            "ALIGN produced a blocking verdict, so routing is denied before any profile expansion."
        )
        if align_action == "DROP_AND_QUARANTINE":
            rationale.append(
                "The decisive sentinel action requires quarantine semantics instead of reviewable execution."
            )
        return GovernedRouteVerdict(
            allowed=False,
            decision="deny",
            governance_mode="deterministic_quarantine"
            if align_action == "DROP_AND_QUARANTINE"
            else "deterministic_containment",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if align_action == "ROUTE_TO_HUMAN_APPROVAL":
        rationale.append(
            "Sentinel policy explicitly routes this request to human approval before any broader execution lane is used."
        )
        constraints.append(
            "Human-approval sentinel actions must remain review-required even when the route is otherwise locally admissible."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="human_approval_required",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if normalized_trust_state == "restricted":
        rationale.append(
            "Witness governance has restricted this subject, so execution routing is denied pending operator recovery."
        )
        constraints.append(
            "Restricted trust states must fail closed before any broader execution lane or fallback model is considered."
        )
        return GovernedRouteVerdict(
            allowed=False,
            decision="deny",
            governance_mode="trust_restricted",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if normalized_trust_state == "probation":
        rationale.append(
            "Witness governance placed this subject on probation, so routing is constrained to a reviewable deterministic local lane."
        )
        constraints.append(
            "Probation trust states require operator review before execution can proceed beyond the smallest deterministic lane."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="trust_probation",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if normalized_trust_state == "watched":
        rationale.append(
            "Witness governance is actively watching this subject, so routing stays in a reviewable deterministic local lane until stronger evidence clears it."
        )
        constraints.append(
            "Watched trust states remain review-required and should not silently promote into heavier routing lanes."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="trust_watched",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if normalized_trust_state not in {"trusted", "healthy", "approved"}:
        rationale.append(
            "Non-healthy trust posture forces deterministic local routing until witness governance is attached."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="trust_constrained",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if align_status == "warning":
        rationale.append(
            "ALIGN warnings require reviewable local routing instead of silent promotion into broader execution lanes."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="warning_constrained",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if cpu_only or (not ollama_available and primary_access_mode != "remote-direct"):
        rationale.append(
            "Local runtime or hardware constraints keep routing inside the smallest deterministic lane."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="deterministic_local_only",
            governance_mode="deterministic_first",
            review_required=False,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if primary_access_mode == "remote-direct":
        rationale.append(
            "An explicit remote-direct operator path is configured for this lane, so routing can proceed even when the local Ollama runtime is unavailable."
        )

    if workload == "translation_memory" and gpu_vram_gb >= 10:
        rationale.append(
            "Multilingual translation memory can use the stronger governed GPU lane once policy is clean and local runtime is healthy."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="governed_multilingual_gpu",
            governance_mode="governed_semantic_retrieval",
            review_required=False,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    if workload == "long_form_standards_ingestion" and gpu_vram_gb >= 12:
        rationale.append(
            "Long-form standards ingestion can escalate to the governed long-context lane when hardware is sufficient."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="governed_long_context_gpu",
            governance_mode="governed_long_context",
            review_required=False,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    # ── Completion workloads ──────────────────────────────────────────────────
    # When ALIGN, trust, and hardware gates are all clear and the workload is
    # a completion/generation type, route to the governed cloud completion lane
    # (Ollama Cloud primary, OpenRouter fallback via ModelOrchestrator).
    if workload in _COMPLETION_WORKLOAD_KEYS:
        rationale.append(
            f"Completion workload '{workload}' maps to the '{selected_lane}' lane; "
            "routing to governed cloud completion with Ollama-primary orchestration."
        )
        return GovernedRouteVerdict(
            allowed=True,
            decision="governed_cloud_completion",
            governance_mode="governed_completion",
            review_required=False,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
            align_action=align_action,
            rationale=rationale,
            policy_constraints=constraints,
        )

    rationale.append(
        "The request is safe but does not justify a heavier routing lane, so the advisory retrieval lane remains sufficient."
    )
    return GovernedRouteVerdict(
        allowed=True,
        decision="advisory_local_retrieval",
        governance_mode="deterministic_first",
        review_required=False,
        selected_lane=selected_lane,
        primary_model=primary_model,
        fallback_model=fallback_model,
        primary_access_mode=primary_access_mode,
        fallback_access_mode=fallback_access_mode,
        align_action=align_action,
        rationale=rationale,
        policy_constraints=constraints,
    )
