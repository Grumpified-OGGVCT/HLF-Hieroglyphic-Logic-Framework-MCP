from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

RoutingDecision = Literal[
    "deny",
    "deterministic_local_only",
    "advisory_local_retrieval",
    "governed_multilingual_gpu",
    "governed_long_context_gpu",
]


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
    rationale: list[str] = field(default_factory=list)
    policy_constraints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
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
            "rationale": self.rationale,
            "policy_constraints": self.policy_constraints,
        }


def build_governed_route(
    *,
    workload: str,
    align_status: str,
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
        return GovernedRouteVerdict(
            allowed=False,
            decision="deny",
            governance_mode="deterministic_containment",
            review_required=True,
            selected_lane=selected_lane,
            primary_model=primary_model,
            fallback_model=fallback_model,
            primary_access_mode=primary_access_mode,
            fallback_access_mode=fallback_access_mode,
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
        rationale=rationale,
        policy_constraints=constraints,
    )
