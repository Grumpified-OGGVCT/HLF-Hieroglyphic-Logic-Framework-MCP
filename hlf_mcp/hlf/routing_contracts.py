"""
HLF Routing Contracts — formalized route-trace contracts.

Defines the shape a route trace MUST satisfy, validates RouteTraceRecord
instances against required fields and evidence rules, and produces structured
fallback evidence and human-readable rationales from GovernedRouteVerdict +
RouteTraceRecord pairs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.governed_routing import GovernedRouteVerdict
from hlf_mcp.hlf.routing_trace import RouteTraceRecord

logger = logging.getLogger(__name__)


# ── Contract shape ───────────────────────────────────────────────────────────

@dataclass(slots=True)
class RouteTraceContract:
    """Formalized shape that a route trace MUST satisfy.

    Defines required fields, validation rules, and the policy basis
    required for audit-ready fallback evidence.
    """

    required_fields: tuple[str, ...] = (
        "route_decision",
        "benchmark_evidence",
        "policy_basis",
    )
    validation_rules: list[str] = field(default_factory=lambda: [
        "primary_model_must_differ_from_fallback",
        "lane_must_exist",
        "governance_mode_must_be_specified",
        "benchmark_evidence_must_be_present",
        "policy_basis_must_be_non_empty",
    ])
    contract_version: str = "1.0.0"
    fail_closed_on_violation: bool = True


# ── Validation ───────────────────────────────────────────────────────────────


def validate_route_trace(trace: RouteTraceRecord) -> list[str]:
    """Validate a RouteTraceRecord against the route-trace contract.

    Returns a list of violation strings.  An empty list means the trace
    is contract-compliant.

    Contract rules:
      1. primary_model != fallback_model (when both are set)
      2. selected_lane (lane) is non-empty
      3. governance_mode is specified (non-empty)
      4. benchmark_evidence dict is non-empty
      5. policy_basis dict is non-empty
    """
    violations: list[str] = []

    decision = trace.route_decision

    # ── Rule 1: primary model must differ from fallback ──────────────────
    primary = (decision.primary_model or "").strip()
    fallback = (decision.fallback_model or "").strip()
    if primary and fallback and primary == fallback:
        violations.append(
            f"Primary model '{primary}' must differ from fallback model '{fallback}'"
        )

    # ── Rule 2: lane must exist ──────────────────────────────────────────
    if not (decision.selected_lane or "").strip():
        violations.append("Selected lane is empty or missing")

    # ── Rule 3: governance mode specified ────────────────────────────────
    if not (decision.governance_mode or "").strip():
        violations.append("Governance mode is empty or missing")

    # ── Rule 4: benchmark evidence present ───────────────────────────────
    if not trace.benchmark_evidence:
        violations.append("Benchmark evidence is empty or missing")

    # ── Rule 5: policy basis non-empty ───────────────────────────────────
    if not trace.policy_basis:
        violations.append("Policy basis is empty or missing")

    return violations


# ── Rationale builder ────────────────────────────────────────────────────────


def build_route_rationale(
    verdict: GovernedRouteVerdict,
    trace: RouteTraceRecord,
) -> str:
    """Build a human-readable route rationale from a verdict and trace.

    Combines the verdict's own rationale list with the operator summary
    from the trace, producing a single prose string suitable for audit
    logs, operator dashboards, and handoff evidence.
    """
    from hlf_mcp.hlf.routing_trace import build_operator_route_summary

    parts: list[str] = []

    # ── Verdict-level rationale ──────────────────────────────────────────
    if verdict.rationale:
        parts.append("Verdict rationale:")
        for i, line in enumerate(verdict.rationale, 1):
            parts.append(f"  {i}. {line}")

    # ── Policy constraints ───────────────────────────────────────────────
    if verdict.policy_constraints:
        parts.append("Policy constraints:")
        for i, constraint in enumerate(verdict.policy_constraints, 1):
            parts.append(f"  {i}. {constraint}")

    # ── Operator summary from trace ──────────────────────────────────────
    operator_summary = build_operator_route_summary(trace)
    parts.append(f"Operator summary: {operator_summary}")

    # ── Failure mode ─────────────────────────────────────────────────────
    if not verdict.allowed:
        parts.append(
            f"ROUTE DENIED — decision='{verdict.decision}', "
            f"governance_mode='{verdict.governance_mode}', "
            f"align_action='{verdict.align_action}'"
        )

    # ── Contract compliance ──────────────────────────────────────────────
    violations = validate_route_trace(trace)
    if violations:
        parts.append("Contract violations:")
        for v in violations:
            parts.append(f"  - {v}")
    else:
        parts.append("Contract compliance: route trace passes all contract validations.")

    return "\n".join(parts)


# ── Fallback evidence ────────────────────────────────────────────────────────


def build_fallback_evidence(trace: RouteTraceRecord) -> dict[str, Any]:
    """Build structured fallback evidence from a route trace.

    Returns a dictionary with policy basis, benchmark evidence,
    fallback chain, contract compliance status, and an evidence
    sufficiency score suitable for operator review and automated
    failover decisions.
    """
    violations = validate_route_trace(trace)

    # ── Evidence sufficiency ─────────────────────────────────────────────
    evidence_count = len(trace.benchmark_evidence)
    policy_count = len(trace.policy_basis)
    fallback_steps = len(trace.fallback_chain)

    sufficiency_flags: list[str] = []
    if evidence_count > 0:
        sufficiency_flags.append("benchmark_evidence_present")
    else:
        sufficiency_flags.append("benchmark_evidence_missing")
    if policy_count > 0:
        sufficiency_flags.append("policy_basis_present")
    else:
        sufficiency_flags.append("policy_basis_missing")
    if fallback_steps > 0:
        sufficiency_flags.append("fallback_chain_populated")

    evidence = {
        "contract_version": RouteTraceContract.contract_version,
        "contract_compliant": len(violations) == 0,
        "contract_violations": violations,
        "policy_basis": dict(trace.policy_basis),
        "policy_basis_entry_count": policy_count,
        "benchmark_evidence": dict(trace.benchmark_evidence),
        "benchmark_evidence_entry_count": evidence_count,
        "fallback_chain": list(trace.fallback_chain),
        "fallback_chain_depth": fallback_steps,
        "selected_lane": trace.route_decision.selected_lane,
        "governance_mode": trace.route_decision.governance_mode,
        "primary_model": trace.route_decision.primary_model,
        "fallback_model": trace.route_decision.fallback_model,
        "review_required": trace.route_decision.review_required,
        "evidence_sufficiency_flags": sufficiency_flags,
        "evidence_sufficient": (
            evidence_count > 0
            and policy_count > 0
            and len(violations) == 0
        ),
        "fail_closed": getattr(trace, "fail_closed", False),
    }

    return evidence
