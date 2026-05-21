"""
Tests for HLF Routing Contracts, Fail-Closed Behavior, and Fallback Evidence.

Failing-first test suite covering:
  1. Valid trace passes contract validation (0 violations)
  2. Trace with missing benchmark_evidence returns violation
  3. Trace with missing policy_basis returns violation
  4. Fail-closed verdict when evidence required but absent
  5. Fail-closed verdict when policy required but absent
  6. fallback_evidence builds correctly with policy basis
  7. route_rationale is human-readable string
  8. build_fail_closed_verdict returns allowed=False with deny decision
  9. Existing governed routing still works (backward compat)
 10. Route trace with fail_closed=True serializes correctly
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the hlf_mcp package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.governed_routing import (  # noqa: E402
    GovernedRouteVerdict,
    build_fail_closed_verdict,
    build_governed_route,
)
from hlf_mcp.hlf.routing_contracts import (  # noqa: E402
    RouteTraceContract,
    build_fallback_evidence,
    build_route_rationale,
    validate_route_trace,
)
from hlf_mcp.hlf.routing_trace import (  # noqa: E402
    RouteDecisionRecord,
    RouteTraceRecord,
    build_operator_route_summary,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_route_decision(**overrides) -> RouteDecisionRecord:
    defaults = {
        "decision": "governed_cloud_completion",
        "governance_mode": "governed_completion",
        "review_required": False,
        "selected_lane": "completion",
        "primary_model": "qwen3.5:cloud",
        "fallback_model": "openrouter/gpt-4o",
    }
    defaults.update(overrides)
    return RouteDecisionRecord(**defaults)


def _make_trace(**overrides) -> RouteTraceRecord:
    defaults: dict = {
        "request_context": {"workload": "reasoning_query", "agent_id": "test-agent"},
        "route_decision": _make_route_decision(),
        "benchmark_evidence": {"mmlu": 0.85, "humaneval": 0.72},
        "policy_basis": {"trust_state": "trusted", "align_status": "clean"},
    }
    defaults.update(overrides)
    return RouteTraceRecord(**defaults)


def _make_hardware_summary(**overrides) -> dict:
    defaults = {
        "cpu_only": False,
        "gpu_vram_gb": 24.0,
        "gpu_count": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_runtime_status(**overrides) -> dict:
    defaults = {
        "ollama_available": True,
        "openrouter_available": True,
    }
    defaults.update(overrides)
    return defaults


# ── RouteTraceContract shape ─────────────────────────────────────────────────


class TestRouteTraceContractShape:
    """The contract dataclass defines the required shape."""

    def test_contract_defaults(self):
        """RouteTraceContract has expected defaults."""
        contract = RouteTraceContract()
        assert "route_decision" in contract.required_fields
        assert "benchmark_evidence" in contract.required_fields
        assert "policy_basis" in contract.required_fields
        assert len(contract.validation_rules) == 5
        assert contract.contract_version == "1.0.0"
        assert contract.fail_closed_on_violation is True

    def test_contract_can_override_rules(self):
        """RouteTraceContract allows custom validation rules."""
        contract = RouteTraceContract(
            validation_rules=["custom_rule_only"],
            fail_closed_on_violation=False,
        )
        assert contract.validation_rules == ["custom_rule_only"]
        assert contract.fail_closed_on_violation is False


# ── validate_route_trace ─────────────────────────────────────────────────────


class TestValidateRouteTrace:
    """Contract validation against RouteTraceRecord instances."""

    def test_valid_trace_passes_with_zero_violations(self):
        """A fully-populated trace returns no violations."""
        trace = _make_trace()
        violations = validate_route_trace(trace)
        assert violations == [], f"Expected 0 violations, got: {violations}"

    def test_missing_benchmark_evidence_returns_violation(self):
        """Empty benchmark_evidence produces a violation."""
        trace = _make_trace(benchmark_evidence={})
        violations = validate_route_trace(trace)
        assert any("benchmark" in v.lower() for v in violations), (
            f"Expected benchmark violation, got: {violations}"
        )

    def test_missing_policy_basis_returns_violation(self):
        """Empty policy_basis produces a violation."""
        trace = _make_trace(policy_basis={})
        violations = validate_route_trace(trace)
        assert any("policy" in v.lower() for v in violations), (
            f"Expected policy violation, got: {violations}"
        )

    def test_empty_lane_returns_violation(self):
        """Empty selected_lane produces a violation."""
        decision = _make_route_decision(selected_lane="")
        trace = _make_trace(route_decision=decision)
        violations = validate_route_trace(trace)
        assert any("lane" in v.lower() for v in violations), (
            f"Expected lane violation, got: {violations}"
        )

    def test_empty_governance_mode_returns_violation(self):
        """Empty governance_mode produces a violation."""
        decision = _make_route_decision(governance_mode="")
        trace = _make_trace(route_decision=decision)
        violations = validate_route_trace(trace)
        assert any("governance" in v.lower() for v in violations), (
            f"Expected governance violation, got: {violations}"
        )

    def test_same_primary_and_fallback_returns_violation(self):
        """Primary == fallback model produces a violation."""
        decision = _make_route_decision(
            primary_model="same-model",
            fallback_model="same-model",
        )
        trace = _make_trace(route_decision=decision)
        violations = validate_route_trace(trace)
        assert any("differ" in v.lower() for v in violations), (
            f"Expected model-differ violation, got: {violations}"
        )

    def test_empty_primary_and_fallback_no_violation(self):
        """Empty primary and fallback (denial trace) does NOT trigger
        the 'must differ' rule because both-empty is not same-model."""
        decision = _make_route_decision(primary_model="", fallback_model="")
        trace = _make_trace(route_decision=decision)
        violations = validate_route_trace(trace)
        # Should have lane violation (empty) but NOT the "must differ" violation
        differ_violations = [v for v in violations if "differ" in v.lower()]
        assert len(differ_violations) == 0, (
            f"Should not have differ violation when both empty, got: {differ_violations}"
        )

    def test_multiple_violations_returned_together(self):
        """Multiple issues produce multiple violation strings."""
        decision = _make_route_decision(selected_lane="", governance_mode="")
        trace = _make_trace(
            route_decision=decision,
            benchmark_evidence={},
            policy_basis={},
        )
        violations = validate_route_trace(trace)
        assert len(violations) >= 4, (
            f"Expected at least 4 violations, got {len(violations)}: {violations}"
        )


# ── Fail-closed verdict ──────────────────────────────────────────────────────


class TestBuildFailClosedVerdict:
    """build_fail_closed_verdict returns a deny verdict."""

    def test_returns_deny_verdict(self):
        """Fail-closed verdict has allowed=False and decision='deny'."""
        verdict = build_fail_closed_verdict()
        assert verdict.allowed is False
        assert verdict.decision == "deny"

    def test_custom_reason_appears_in_rationale(self):
        """Custom reason string appears in the rationale list."""
        verdict = build_fail_closed_verdict(reason="missing_benchmark_scores")
        assert any("missing_benchmark_scores" in r for r in verdict.rationale)

    def test_governance_mode_is_fail_closed(self):
        """Fail-closed verdict uses 'fail_closed' governance mode."""
        verdict = build_fail_closed_verdict()
        assert verdict.governance_mode == "fail_closed"

    def test_review_required_is_true(self):
        """Fail-closed verdict always requires review."""
        verdict = build_fail_closed_verdict()
        assert verdict.review_required is True

    def test_default_reason_mentions_policy_or_evidence(self):
        """Default reason references policy or evidence."""
        verdict = build_fail_closed_verdict()
        combined = " ".join(verdict.rationale)
        assert "policy_or_evidence_missing" in combined

    def test_policy_constraints_populated(self):
        """Fail-closed verdict includes policy constraints."""
        verdict = build_fail_closed_verdict()
        assert len(verdict.policy_constraints) > 0
        assert any("fail-closed" in c.lower() for c in verdict.policy_constraints)


# ── Fail-closed in build_governed_route ──────────────────────────────────────


class TestGovernedRouteFailClosed:
    """build_governed_route fail-closed gating."""

    def test_fail_closed_when_evidence_required_but_absent(self):
        """require_evidence=True + empty benchmark_evidence → fail-closed."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_evidence=True,
            benchmark_evidence={},
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"
        assert verdict.governance_mode == "fail_closed"

    def test_fail_closed_when_evidence_required_and_none(self):
        """require_evidence=True + benchmark_evidence=None → fail-closed."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_evidence=True,
            benchmark_evidence=None,
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"

    def test_fail_closed_when_policy_basis_required_but_absent(self):
        """require_policy_basis=True + empty policy_basis → fail-closed."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_policy_basis=True,
            policy_basis={},
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"
        assert verdict.governance_mode == "fail_closed"

    def test_fail_closed_when_policy_basis_required_and_none(self):
        """require_policy_basis=True + policy_basis=None → fail-closed."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_policy_basis=True,
            policy_basis=None,
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"

    def test_evidence_present_succeeds_past_gate(self):
        """require_evidence=True + non-empty benchmark_evidence → proceeds normally."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_evidence=True,
            benchmark_evidence={"mmlu": 0.85},
        )
        assert verdict.allowed is True
        assert verdict.governance_mode != "fail_closed"

    def test_policy_basis_present_succeeds_past_gate(self):
        """require_policy_basis=True + non-empty policy_basis → proceeds normally."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_policy_basis=True,
            policy_basis={"trust_state": "trusted"},
        )
        assert verdict.allowed is True
        assert verdict.governance_mode != "fail_closed"


# ── Backward compatibility ───────────────────────────────────────────────────


class TestGovernedRouteBackwardCompat:
    """Existing governed routing still works with defaults."""

    def test_trusted_reasoning_query_routes_normally(self):
        """Default params (require_evidence=False, require_policy_basis=False)
        produce a valid governed route for a completion workload."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        assert verdict.allowed is True
        assert verdict.decision == "governed_cloud_completion"
        assert verdict.governance_mode == "governed_completion"

    def test_blocked_align_still_denies(self):
        """ALIGN blocked status still denies regardless of new params."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="blocked",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_evidence=True,
            benchmark_evidence={"mmlu": 0.85},
            require_policy_basis=True,
            policy_basis={"trust_state": "trusted"},
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"

    def test_restricted_trust_still_denies(self):
        """Restricted trust state still denies regardless of new params."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="restricted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
            require_evidence=True,
            benchmark_evidence={"mmlu": 0.85},
            require_policy_basis=True,
            policy_basis={"trust_state": "trusted"},
        )
        assert verdict.allowed is False
        assert verdict.decision == "deny"
        assert verdict.governance_mode == "trust_restricted"

    def test_cpu_only_routes_deterministic_local(self):
        """CPU-only hardware still routes to deterministic_local_only."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(cpu_only=True),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        assert verdict.allowed is True
        assert verdict.decision == "deterministic_local_only"

    def test_new_params_are_optional(self):
        """build_governed_route works without benchmark_evidence or policy_basis."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        assert verdict.allowed is True
        # No fail-closed — defaults are False
        assert verdict.governance_mode != "fail_closed"


# ── Fallback evidence ────────────────────────────────────────────────────────


class TestBuildFallbackEvidence:
    """build_fallback_evidence produces structured evidence dicts."""

    def test_evidence_includes_policy_basis(self):
        """Fallback evidence includes the policy_basis dictionary."""
        trace = _make_trace(policy_basis={"trust_state": "trusted", "align_status": "clean"})
        evidence = build_fallback_evidence(trace)
        assert evidence["policy_basis"] == {"trust_state": "trusted", "align_status": "clean"}
        assert evidence["policy_basis_entry_count"] == 2

    def test_evidence_includes_benchmark_evidence(self):
        """Fallback evidence includes benchmark scores."""
        trace = _make_trace(benchmark_evidence={"mmlu": 0.85, "humaneval": 0.72})
        evidence = build_fallback_evidence(trace)
        assert evidence["benchmark_evidence"] == {"mmlu": 0.85, "humaneval": 0.72}
        assert evidence["benchmark_evidence_entry_count"] == 2

    def test_evidence_includes_fallback_chain(self):
        """Fallback evidence includes the fallback chain."""
        trace = _make_trace(
            fallback_chain=[
                {"step": 1, "model": "backup-a", "reason": "primary unreachable"},
                {"step": 2, "model": "backup-b", "reason": "backup-a exhausted"},
            ]
        )
        evidence = build_fallback_evidence(trace)
        assert evidence["fallback_chain_depth"] == 2
        assert len(evidence["fallback_chain"]) == 2

    def test_evidence_compliant_when_no_violations(self):
        """Contract-compliant trace shows compliant=True."""
        trace = _make_trace()
        evidence = build_fallback_evidence(trace)
        assert evidence["contract_compliant"] is True
        assert evidence["contract_violations"] == []

    def test_evidence_non_compliant_when_violations(self):
        """Trace with violations shows compliant=False."""
        trace = _make_trace(benchmark_evidence={}, policy_basis={})
        evidence = build_fallback_evidence(trace)
        assert evidence["contract_compliant"] is False
        assert len(evidence["contract_violations"]) >= 2

    def test_evidence_sufficient_with_all_data(self):
        """Fully populated trace shows evidence_sufficient=True."""
        trace = _make_trace()
        evidence = build_fallback_evidence(trace)
        assert evidence["evidence_sufficient"] is True

    def test_evidence_insufficient_when_missing(self):
        """Missing benchmark or policy shows evidence_sufficient=False."""
        trace = _make_trace(benchmark_evidence={})
        evidence = build_fallback_evidence(trace)
        assert evidence["evidence_sufficient"] is False

    def test_evidence_includes_contract_version(self):
        """Evidence dict includes the contract version."""
        trace = _make_trace()
        evidence = build_fallback_evidence(trace)
        assert evidence["contract_version"] == RouteTraceContract.contract_version

    def test_evidence_includes_fail_closed_flag(self):
        """Evidence dict reflects fail_closed from the trace."""
        trace = _make_trace(fail_closed=True)
        evidence = build_fallback_evidence(trace)
        assert evidence["fail_closed"] is True

    def test_evidence_sufficiency_flags_reflect_state(self):
        """Sufficiency flags correctly report present/missing state."""
        trace = _make_trace(benchmark_evidence={}, policy_basis={"trust": "trusted"})
        evidence = build_fallback_evidence(trace)
        flags = evidence["evidence_sufficiency_flags"]
        assert "benchmark_evidence_missing" in flags
        assert "policy_basis_present" in flags


# ── Route rationale ──────────────────────────────────────────────────────────


class TestBuildRouteRationale:
    """build_route_rationale produces human-readable strings."""

    def test_rationale_is_non_empty_string(self):
        """Rationale is a non-empty human-readable string."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert isinstance(rationale, str)
        assert len(rationale) > 0

    def test_rationale_includes_verdict_rationale(self):
        """Rationale string includes lines from verdict.rationale."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert "Verdict rationale:" in rationale

    def test_rationale_includes_policy_constraints(self):
        """Rationale includes policy constraints section."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert "Policy constraints:" in rationale

    def test_rationale_includes_operator_summary(self):
        """Rationale includes the operator summary from the trace."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert "Operator summary:" in rationale

    def test_rationale_notes_compliance_when_valid(self):
        """Rationale includes contract compliance note when valid."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert "Contract compliance:" in rationale

    def test_rationale_notes_violations_when_present(self):
        """Rationale includes contract violations when present."""
        verdict = build_fail_closed_verdict("test_violation")
        trace = _make_trace(benchmark_evidence={}, policy_basis={})
        rationale = build_route_rationale(verdict, trace)
        assert "Contract violations:" in rationale

    def test_rationale_shows_denied_for_fail_closed(self):
        """Rationale shows ROUTE DENIED for fail-closed verdict."""
        verdict = build_fail_closed_verdict("test")
        trace = _make_trace()
        rationale = build_route_rationale(verdict, trace)
        assert "ROUTE DENIED" in rationale


# ── RouteTraceRecord fail_closed serialization ───────────────────────────────


class TestRouteTraceFailClosed:
    """RouteTraceRecord fail_closed field and serialization."""

    def test_fail_closed_defaults_to_false(self):
        """fail_closed defaults to False on new records."""
        trace = _make_trace()
        assert trace.fail_closed is False

    def test_fail_closed_can_be_set_true(self):
        """fail_closed can be explicitly set to True."""
        trace = _make_trace(fail_closed=True)
        assert trace.fail_closed is True

    def test_to_dict_includes_fail_closed_false(self):
        """to_dict() includes fail_closed=False by default."""
        trace = _make_trace()
        d = trace.to_dict()
        assert "fail_closed" in d
        assert d["fail_closed"] is False

    def test_to_dict_includes_fail_closed_true(self):
        """to_dict() includes fail_closed=True when set."""
        trace = _make_trace(fail_closed=True)
        d = trace.to_dict()
        assert d["fail_closed"] is True

    def test_fail_closed_survives_round_trip(self):
        """fail_closed flag survives to_dict round-trip inspection."""
        trace = _make_trace(fail_closed=True)
        d = trace.to_dict()
        assert d["fail_closed"] is True
        # Other fields are intact
        assert d["request_context"]["agent_id"] == "test-agent"
        assert d["route_decision"]["primary_model"] == "qwen3.5:cloud"


# ── Validate route trace with verdict integration ────────────────────────────


class TestValidateTraceWithVerdict:
    """Integration: validate route trace + governed verdict together."""

    def test_valid_governed_route_produces_valid_trace(self):
        """A successfully governed route produces a trace that validates."""
        verdict = build_governed_route(
            workload="reasoning_query",
            align_status="clean",
            trust_state="trusted",
            hardware_summary=_make_hardware_summary(),
            runtime_status=_make_runtime_status(),
            embedding_recommendation={"model": "qwen3.5:cloud", "access_mode": "remote-direct"},
            fallback_recommendation={"model": "openrouter/gpt-4o", "access_mode": "remote-direct"},
        )
        decision = RouteDecisionRecord(
            decision=verdict.decision,
            governance_mode=verdict.governance_mode,
            review_required=verdict.review_required,
            selected_lane=verdict.selected_lane,
            primary_model=verdict.primary_model,
            fallback_model=verdict.fallback_model,
        )
        trace = RouteTraceRecord(
            request_context={"workload": "reasoning_query"},
            route_decision=decision,
            benchmark_evidence={"mmlu": 0.85},
            policy_basis={"trust_state": "trusted"},
        )
        violations = validate_route_trace(trace)
        assert violations == [], f"Expected 0 violations, got: {violations}"

    def test_fail_closed_verdict_trace_shows_violations(self):
        """A fail-closed verdict's trace correctly shows violations due to
        empty lane and governance mode."""
        verdict = build_fail_closed_verdict()
        decision = RouteDecisionRecord(
            decision=verdict.decision,
            governance_mode=verdict.governance_mode,
            review_required=verdict.review_required,
            selected_lane=verdict.selected_lane,
            primary_model=verdict.primary_model,
            fallback_model=verdict.fallback_model,
        )
        trace = RouteTraceRecord(
            request_context={"workload": "reasoning_query"},
            route_decision=decision,
            benchmark_evidence={},
            policy_basis={},
        )
        violations = validate_route_trace(trace)
        # Fail-closed has empty lane, empty governance_mode (well, "fail_closed"),
        # empty benchmark_evidence, and empty policy_basis
        assert len(violations) >= 3, (
            f"Expected at least 3 violations for fail-closed trace, got {len(violations)}: {violations}"
        )


# ── RouteDecisionRecord backward compat ──────────────────────────────────────


class TestRouteDecisionRecordCompat:
    """RouteDecisionRecord remains backward compatible."""

    def test_to_dict_still_works(self):
        """RouteDecisionRecord.to_dict() still returns expected keys."""
        decision = _make_route_decision()
        d = decision.to_dict()
        assert d["decision"] == "governed_cloud_completion"
        assert d["governance_mode"] == "governed_completion"
        assert "primary_model" in d
        assert "fallback_model" in d
        assert "selected_lane" in d

    def test_operator_summary_still_works(self):
        """build_operator_route_summary still produces expected format."""
        decision = _make_route_decision()
        trace = RouteTraceRecord(
            request_context={"workload": "test"},
            route_decision=decision,
            benchmark_evidence={"mmlu": 0.85},
            policy_basis={"trust": "trusted"},
        )
        summary = build_operator_route_summary(trace)
        assert "Lane '" in summary
        assert "completion" in summary
        assert "qwen3.5:cloud" in summary
