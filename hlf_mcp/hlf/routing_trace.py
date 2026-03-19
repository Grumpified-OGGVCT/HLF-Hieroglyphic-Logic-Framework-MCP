from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RouteDecisionRecord:
    decision: str
    governance_mode: str
    review_required: bool
    selected_lane: str
    primary_model: str
    fallback_model: str
    primary_access_mode: str = ""
    fallback_access_mode: str = ""
    qualification_profile: str | None = None
    applied_qualification_profiles: list[str] = field(default_factory=list)
    preferred_model_tier: str | None = None
    benchmark_scores: dict[str, float] = field(default_factory=dict)
    align_status: str | None = None
    align_rule_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "governance_mode": self.governance_mode,
            "review_required": self.review_required,
            "selected_lane": self.selected_lane,
            "primary_model": self.primary_model,
            "fallback_model": self.fallback_model,
            "primary_access_mode": self.primary_access_mode,
            "fallback_access_mode": self.fallback_access_mode,
            "qualification_profile": self.qualification_profile,
            "applied_qualification_profiles": list(self.applied_qualification_profiles),
            "preferred_model_tier": self.preferred_model_tier,
            "benchmark_scores": dict(self.benchmark_scores),
            "align_status": self.align_status,
            "align_rule_id": self.align_rule_id,
        }


@dataclass(slots=True)
class RouteTraceRecord:
    request_context: dict[str, Any]
    route_decision: RouteDecisionRecord
    selection_profiles: list[str] = field(default_factory=list)
    profile_evaluations: dict[str, dict[str, Any]] = field(default_factory=dict)
    benchmark_evidence: dict[str, Any] = field(default_factory=dict)
    policy_basis: dict[str, Any] = field(default_factory=dict)
    fallback_chain: list[dict[str, Any]] = field(default_factory=list)
    lane_candidate_summary: dict[str, Any] = field(default_factory=dict)
    operator_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_context": dict(self.request_context),
            "route_decision": self.route_decision.to_dict(),
            "selection_profiles": list(self.selection_profiles),
            "profile_evaluations": dict(self.profile_evaluations),
            "benchmark_evidence": dict(self.benchmark_evidence),
            "policy_basis": dict(self.policy_basis),
            "fallback_chain": list(self.fallback_chain),
            "lane_candidate_summary": dict(self.lane_candidate_summary),
            "operator_summary": self.operator_summary,
        }


def build_operator_route_summary(trace: RouteTraceRecord) -> str:
    decision = trace.route_decision
    review_text = "review required" if decision.review_required else "review not required"
    model_text = decision.primary_model or "unresolved-model"
    tier_text = decision.preferred_model_tier or "unqualified"
    return (
        f"Lane '{decision.selected_lane}' routed to '{model_text}' under mode "
        f"'{decision.governance_mode}' with qualification tier '{tier_text}' and {review_text}."
    )
