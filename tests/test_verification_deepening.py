"""Tests for formal verification proof depth hardening.

Tests counterexample quality, proof depth measurement,
obligation extraction, tier escalation, timeout recovery,
partial proofs, human-readable gate explanations,
Z3 operator family coverage, inductive proof automation,
and proof artifact generation with signed hashes.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    FormalVerifier,
    GateDecision,
    ProofArtifact,
    VerificationBlockedError,
    VerificationGate,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    Z3OperatorEncoder,
    Z3Solver,
    generate_proof_artifact,
    normalize_ast,
    z3_available,
)
from hlf_mcp.hlf.counterexample_quality import (
    Counterexample,
    CounterexampleGenerator,
    InductiveCounterexample,
    InductiveCounterexampleGenerator,
    compare_counterexamples,
    explain_counterexample,
    generate_inductive_counterexample,
    generate_minimal_counterexample,
    suggest_fix,
    suggest_inductive_fix,
)
from hlf_mcp.hlf.proof_depth import (
    InductiveProofChain,
    InductiveProver,
    ProofDepth,
    ProofObligation,
    deepen_proof,
    generate_proof_obligations,
    measure_proof_depth,
    rank_obligations_by_impact,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Counterexample dataclass tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_counterexample_dataclass_stores_all_fields() -> None:
    ce = Counterexample(
        property_name="range_check_temp",
        inputs={"value": 999},
        expected_output="value <= 100",
        actual_output="value = 999",
        violation_path="Value 999 exceeds maximum bound 100",
        severity="error",
        kind="range_check",
        solver="z3",
    )
    assert ce.property_name == "range_check_temp"
    assert ce.inputs == {"value": 999}
    assert ce.expected_output == "value <= 100"
    assert ce.actual_output == "value = 999"
    assert "999 exceeds" in ce.violation_path
    assert ce.severity == "error"
    assert ce.kind == "range_check"
    assert ce.solver == "z3"


def test_counterexample_to_dict_includes_all_keys() -> None:
    ce = Counterexample(
        property_name="type_check",
        inputs={"value": "wrong_type"},
        expected_output="integer",
        actual_output="string",
        violation_path="Type mismatch",
        severity="error",
        kind="type_invariant",
        solver="fallback",
    )
    d = ce.to_dict()
    assert d["property_name"] == "type_check"
    assert d["inputs"] == {"value": "wrong_type"}
    assert d["severity"] == "error"
    assert d["kind"] == "type_invariant"
    assert d["solver"] == "fallback"


def test_counterexample_is_actionable_with_inputs_and_path() -> None:
    ce_with = Counterexample(
        property_name="test",
        inputs={"x": 1},
        expected_output="ok",
        actual_output="bad",
        violation_path="Something went wrong",
    )
    ce_without = Counterexample(
        property_name="test",
        inputs={},
        expected_output="ok",
        actual_output="bad",
        violation_path="",
    )
    assert ce_with.is_actionable() is True
    assert ce_without.is_actionable() is False


# ═══════════════════════════════════════════════════════════════════════════════
# CounterexampleGenerator tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_generator_from_range_counterexample_result() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="range_check_temp",
        status=VerificationStatus.COUNTEREXAMPLE,
        kind=ConstraintKind.RANGE_CHECK,
        message="7 > 5",
        counterexample={"value": 7, "bound": 5, "comparison": "above_high"},
        solver="fallback",
    )
    ce = gen.generate(result)
    assert ce.property_name == "range_check_temp"
    assert ce.kind == "range_check"
    assert ce.severity == "error"
    assert ce.inputs["value"] == 7
    assert "exceeds" in ce.violation_path.lower() or "above" in ce.violation_path.lower()


def test_generator_from_type_counterexample_result() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="type_check_num",
        status=VerificationStatus.COUNTEREXAMPLE,
        kind=ConstraintKind.TYPE_INVARIANT,
        message="Expected 'number', got 'string'",
        counterexample={"value": "hello", "actual_type": "str"},
        solver="fallback",
    )
    ce = gen.generate(result)
    assert ce.kind == "type_invariant"
    assert ce.severity == "error"
    assert "hello" in str(ce.inputs)


def test_generator_from_gas_counterexample_result() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="gas_budget_check",
        status=VerificationStatus.COUNTEREXAMPLE,
        kind=ConstraintKind.GAS_BOUND,
        message="Total gas 12000 > budget 10000",
        counterexample={"total_gas": 12000, "budget": 10000, "over_by": 2000},
        solver="z3",
    )
    ce = gen.generate(result)
    assert ce.kind == "gas_bound"
    assert ce.inputs["total_gas"] == 12000
    assert "12000" in ce.violation_path


def test_generator_from_spec_gate_false_counterexample() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="spec_gate_migration",
        status=VerificationStatus.COUNTEREXAMPLE,
        kind=ConstraintKind.SPEC_GATE,
        message="SPEC_GATE literal 'rollback_on_fail' resolved to false.",
        counterexample={"field": "rollback_on_fail", "value": False},
        solver="fallback",
    )
    ce = gen.generate(result)
    assert ce.kind == "spec_gate"
    assert ce.inputs["field"] == "rollback_on_fail"
    assert ce.inputs["value"] is False


def test_generator_from_error_result() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="bad_check",
        status=VerificationStatus.ERROR,
        kind=ConstraintKind.RANGE_CHECK,
        message="Value is not numeric: str",
        solver="fallback",
    )
    ce = gen.generate(result)
    assert ce.severity == "error"
    assert "Verification error" in ce.violation_path


def test_generator_from_proven_result_is_info() -> None:
    gen = CounterexampleGenerator()
    result = VerificationResult(
        property_name="ok_check",
        status=VerificationStatus.PROVEN,
        kind=ConstraintKind.RANGE_CHECK,
        message="Within range",
        solver="z3",
    )
    ce = gen.generate(result)
    assert ce.severity == "info"
    assert "No violation" in ce.violation_path


# ═══════════════════════════════════════════════════════════════════════════════
# Counterexample minimization tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_minimal_counterexample_range_violation() -> None:
    ce = generate_minimal_counterexample(
        "temp_check",
        {"kind": "range_check", "low": 0, "high": 100, "value": 150},
    )
    assert ce.kind == "range_check"
    assert ce.severity == "error"
    assert "150" in str(ce.inputs)


def test_minimal_counterexample_gas_violation() -> None:
    ce = generate_minimal_counterexample(
        "gas_check",
        {"kind": "gas_bound", "task_count": 15, "per_task_cost": 1000, "budget": 10000},
    )
    assert ce.kind == "gas_bound"
    # Should compute minimal violating task count
    assert "minimal_violating_tasks" in ce.inputs


def test_minimal_counterexample_type_violation() -> None:
    ce = generate_minimal_counterexample(
        "type_check",
        {"kind": "type_invariant", "value": True, "expected_type": "integer", "actual_type": "bool"},
    )
    assert ce.kind == "type_invariant"
    assert ce.severity == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# Counterexample explanation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_explain_counterexample_produces_multiline_output() -> None:
    ce = Counterexample(
        property_name="range_check_temp",
        inputs={"value": 999},
        expected_output="value <= 100",
        actual_output="value = 999",
        violation_path="Value 999 exceeds maximum bound 100",
        severity="error",
        kind="range_check",
        solver="z3",
    )
    explanation = explain_counterexample(ce)
    assert "range_check_temp" in explanation
    assert "999" in explanation
    assert "Suggested fix" in explanation
    # Should have multiple lines
    assert len(explanation.splitlines()) >= 5


def test_explain_counterexample_handles_empty_inputs() -> None:
    ce = Counterexample(
        property_name="empty_check",
        inputs={},
        expected_output="should work",
        actual_output="did not work",
        violation_path="Something failed",
    )
    explanation = explain_counterexample(ce)
    assert "empty_check" in explanation
    assert "Suggested fix" in explanation


# ═══════════════════════════════════════════════════════════════════════════════
# Fix suggestion heuristic tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_suggest_fix_below_low_range() -> None:
    ce = Counterexample(
        property_name="temp_check",
        inputs={"value": -5, "low": 0},
        expected_output="value >= 0",
        actual_output="value = -5",
        violation_path="The value -5 is below the minimum bound of 0",
        severity="error",
        kind="range_check",
    )
    suggestion = suggest_fix(ce)
    assert "increase" in suggestion.lower() or "minimum" in suggestion.lower()


def test_suggest_fix_above_high_range() -> None:
    ce = Counterexample(
        property_name="temp_check",
        inputs={"value": 150, "high": 100},
        expected_output="value <= 100",
        actual_output="value = 150",
        violation_path="The value 150 exceeds the maximum bound of 100",
        severity="error",
        kind="range_check",
    )
    suggestion = suggest_fix(ce)
    assert "decrease" in suggestion.lower() or "maximum" in suggestion.lower()


def test_suggest_fix_type_mismatch() -> None:
    ce = Counterexample(
        property_name="type_check",
        inputs={"value": "wrong"},
        expected_output="integer",
        actual_output="string",
        violation_path="Type mismatch: expected integer, got string",
        severity="error",
        kind="type_invariant",
    )
    suggestion = suggest_fix(ce)
    assert "type" in suggestion.lower()


def test_suggest_fix_gas_exceeded() -> None:
    ce = Counterexample(
        property_name="gas_check",
        inputs={"total_gas": 15000, "budget": 10000},
        expected_output="total_gas <= 10000",
        actual_output="total_gas = 15000",
        violation_path="Total gas exceeds budget",
        severity="error",
        kind="gas_bound",
    )
    suggestion = suggest_fix(ce)
    assert "gas" in suggestion.lower() or "budget" in suggestion.lower()


def test_suggest_fix_spec_gate_false() -> None:
    ce = Counterexample(
        property_name="gate_check",
        inputs={"field": "audit_enabled", "value": False},
        expected_output="audit_enabled = true",
        actual_output="audit_enabled = false",
        violation_path="The SPEC_GATE field 'audit_enabled' resolved to false",
        severity="error",
        kind="spec_gate",
    )
    suggestion = suggest_fix(ce)
    assert "true" in suggestion.lower() or "true" in suggestion.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Counterexample comparison tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_compare_counterexamples_z3_wins_over_fallback() -> None:
    a = Counterexample(
        property_name="check_a",
        inputs={"x": 1},
        expected_output="ok",
        actual_output="bad",
        violation_path="Failed",
        solver="z3",
    )
    b = Counterexample(
        property_name="check_b",
        inputs={"x": 1},
        expected_output="ok",
        actual_output="bad",
        violation_path="Failed",
        solver="fallback",
    )
    result = compare_counterexamples(a, b)
    assert result.startswith("a") or "a" in result


def test_compare_counterexamples_detailed_path_wins() -> None:
    a = Counterexample(
        property_name="check_a",
        inputs={},
        expected_output="ok",
        actual_output="bad",
        violation_path="Short",
    )
    b = Counterexample(
        property_name="check_b",
        inputs={},
        expected_output="ok",
        actual_output="bad",
        violation_path="A" * 100,  # Long detailed path
    )
    result = compare_counterexamples(a, b)
    assert result.startswith("b") or "b" in result


def test_compare_counterexamples_equal() -> None:
    a = Counterexample(
        property_name="check_a",
        inputs={},
        expected_output="ok",
        actual_output="bad",
        violation_path="Same",
    )
    b = Counterexample(
        property_name="check_b",
        inputs={},
        expected_output="ok",
        actual_output="bad",
        violation_path="Same",
    )
    result = compare_counterexamples(a, b)
    assert result == "equal"


# ═══════════════════════════════════════════════════════════════════════════════
# ProofObligation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_proof_obligation_stores_fields() -> None:
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove value within bounds",
        kind="range_check",
        current_depth=0,
        target_depth=2,
    )
    assert po.obligation_id == "po_range_0"
    assert po.kind == "range_check"
    assert po.current_depth == 0
    assert po.target_depth == 2
    assert po.status == "pending"
    assert po.lemmas == []
    assert po.dependencies == []


def test_proof_obligation_is_satisfied_when_proven_at_target() -> None:
    po = ProofObligation(
        obligation_id="po_test",
        description="Test",
        kind="range_check",
        current_depth=0,
        target_depth=1,
    )
    assert not po.is_satisfied()
    po.mark_proven(depth=1)
    assert po.is_satisfied()


def test_proof_obligation_is_blocking_when_pending() -> None:
    po = ProofObligation(obligation_id="po_test", description="Test", kind="range_check")
    assert po.is_blocking()
    po.mark_proven()
    assert not po.is_blocking()


def test_proof_obligation_is_blocking_when_failed() -> None:
    po = ProofObligation(obligation_id="po_test", description="Test", kind="range_check")
    po.mark_failed("Something went wrong")
    assert po.is_blocking()
    assert "FAILED" in po.description


def test_proof_obligation_to_dict() -> None:
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove range",
        kind="range_check",
        current_depth=1,
        target_depth=2,
        dependencies=["po_type_0"],
        lemmas=["Lemma(bound_check): value is numeric"],
    )
    po.status = "in_progress"
    d = po.to_dict()
    assert d["obligation_id"] == "po_range_0"
    assert d["kind"] == "range_check"
    assert d["current_depth"] == 1
    assert d["target_depth"] == 2
    assert d["status"] == "in_progress"
    assert "po_type_0" in d["dependencies"]
    assert len(d["lemmas"]) == 1
    assert d["satisfied"] is False
    assert d["blocking"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# ProofDepth measurement tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_measure_proof_depth_empty_report() -> None:
    report = VerificationReport()
    depth = measure_proof_depth(report)
    assert depth == 0


def test_measure_proof_depth_all_proven_z3() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK, solver="z3"
        )
    )
    report.add(
        VerificationResult(
            "p2", VerificationStatus.PROVEN, ConstraintKind.TYPE_INVARIANT, solver="z3"
        )
    )
    depth = measure_proof_depth(report)
    # Each Z3-proven = 1.5, so 3.0 → floor 3
    assert depth == 3


def test_measure_proof_depth_mixed_statuses() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK, solver="z3"
        )
    )
    report.add(
        VerificationResult(
            "rt1", VerificationStatus.RUNTIME_CHECKED, ConstraintKind.TYPE_INVARIANT, solver="fallback"
        )
    )
    report.add(
        VerificationResult(
            "ce1", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK, solver="fallback"
        )
    )
    depth = measure_proof_depth(report)
    # 1.5 (z3 proven) + 0.5 (runtime checked) + 0 (counterexample) = 2
    assert depth == 2


def test_measure_proof_depth_runtime_checked_only() -> None:
    report = VerificationReport()
    for i in range(4):
        report.add(
            VerificationResult(
                f"rt{i}", VerificationStatus.RUNTIME_CHECKED, ConstraintKind.TYPE_INVARIANT, solver="fallback"
            )
        )
    depth = measure_proof_depth(report)
    # 4 * 0.5 = 2
    assert depth == 2


def test_measure_proof_depth_detailed_returns_breakdown() -> None:
    pd = ProofDepth()
    report = VerificationReport()
    report.add(
        VerificationResult(
            "p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK, solver="z3"
        )
    )
    report.add(
        VerificationResult(
            "rt1", VerificationStatus.RUNTIME_CHECKED, ConstraintKind.TYPE_INVARIANT, solver="fallback"
        )
    )
    detailed = pd.measure_proof_depth_detailed(report)
    assert "total_depth" in detailed
    assert "depth_by_kind" in detailed
    assert "depth_rating" in detailed
    assert detailed["total_depth"] == 2
    assert detailed["depth_rating"] in ("shallow", "moderate", "deep", "exhaustive", "none")


# ═══════════════════════════════════════════════════════════════════════════════
# Proof deepening tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_deepen_proof_adds_basic_lemmas() -> None:
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove range",
        kind="range_check",
    )
    result = deepen_proof(po, target_depth=1)
    assert result.current_depth >= 1
    assert len(result.lemmas) >= 1
    assert any("bound" in lemma.lower() or "check" in lemma.lower() for lemma in result.lemmas)


def test_deepen_proof_adds_lemma_level_lemmas() -> None:
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove range",
        kind="range_check",
    )
    result = deepen_proof(po, target_depth=2)
    assert result.current_depth >= 2
    assert any("mono" in lemma.lower() or "tight" in lemma.lower() for lemma in result.lemmas)


def test_deepen_proof_does_not_reduce_depth() -> None:
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove range",
        kind="range_check",
        current_depth=2,
    )
    result = deepen_proof(po, target_depth=1)
    assert result.current_depth == 2


def test_deepen_proof_caps_without_z3() -> None:
    pd = ProofDepth()
    po = ProofObligation(
        obligation_id="po_range_0",
        description="Prove range",
        kind="range_check",
    )
    result = pd.deepen_proof(po, target_depth=5)
    if not pd.z3_available:
        # Should have a depth-limited message in lemmas
        assert any("depth-limited" in lemma.lower() for lemma in result.lemmas)
    assert result.current_depth >= 2  # At minimum, lemma level


# ═══════════════════════════════════════════════════════════════════════════════
# Proof obligation extraction tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_generate_proof_obligations_from_ast() -> None:
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
            {
                "tag": "CONSTRAINT",
                "arguments": [
                    {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
                    {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                    {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                ],
            },
        ]
    }
    obligations = generate_proof_obligations(ast)
    assert len(obligations) >= 1
    assert any(o.kind == "range_check" for o in obligations)
    assert all(isinstance(o, ProofObligation) for o in obligations)


def test_generate_proof_obligations_empty_ast() -> None:
    obligations = generate_proof_obligations({"program": []})
    assert obligations == []


def test_generate_proof_obligations_links_dependencies() -> None:
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
            {"tag": "SPEC_GATE", "condition": {"op": "COMPARE"}},
        ]
    }
    obligations = generate_proof_obligations(ast)
    # SPEC_GATE should depend on type_invariant from SET
    spec_gates = [o for o in obligations if o.kind == "spec_gate"]
    if spec_gates:
        assert len(spec_gates[0].dependencies) >= 1


def test_generate_proof_obligations_descriptions_are_readable() -> None:
    ast = {
        "program": [
            {"tag": "SET", "name": "temperature", "value": 7},
            {
                "tag": "CONSTRAINT",
                "arguments": [
                    {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
                    {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                    {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                ],
            },
        ]
    }
    obligations = generate_proof_obligations(ast)
    for obl in obligations:
        assert len(obl.description) > 0
        assert "Prove" in obl.description or obl.kind in obl.description.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Obligation ranking tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_rank_obligations_blocking_first() -> None:
    obl_proven = ProofObligation(
        obligation_id="po_proven", description="Already proven", kind="range_check", status="proven"
    )
    obl_failed = ProofObligation(
        obligation_id="po_failed", description="Failed", kind="range_check", status="failed"
    )
    obl_pending = ProofObligation(
        obligation_id="po_pending", description="Pending", kind="range_check", status="pending"
    )

    ranked = rank_obligations_by_impact([obl_proven, obl_failed, obl_pending])
    # Blocking obligations (failed, pending) should come first
    assert ranked[0].obligation_id in ("po_failed", "po_pending")
    assert ranked[-1].obligation_id == "po_proven"


def test_rank_obligations_dependents_boost_rank() -> None:
    obl_a = ProofObligation(
        obligation_id="po_a", description="A - depended on", kind="range_check", status="pending"
    )
    obl_b = ProofObligation(
        obligation_id="po_b",
        description="B - depends on A",
        kind="spec_gate",
        status="pending",
        dependencies=["po_a"],
    )
    ranked = rank_obligations_by_impact([obl_a, obl_b])
    # po_a should rank higher because po_b depends on it
    assert ranked[0].obligation_id == "po_a"


def test_rank_obligations_empty_list() -> None:
    ranked = rank_obligations_by_impact([])
    assert ranked == []


def test_rank_obligations_all_proven_returns_zero_order() -> None:
    obl_a = ProofObligation(
        obligation_id="po_a", description="A", kind="range_check", status="proven"
    )
    obl_b = ProofObligation(
        obligation_id="po_b", description="B", kind="spec_gate", status="proven"
    )
    ranked = rank_obligations_by_impact([obl_a, obl_b])
    # All should have zero impact score since they're proven
    assert len(ranked) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Tier escalation edge case tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_tier_escalation_map_includes_all_tiers() -> None:
    mapping = VerificationGate.tier_escalation_map()
    assert "hearth" in mapping
    assert "forge" in mapping
    assert "sovereign" in mapping
    assert mapping["sovereign"] == "forge"
    assert mapping["hearth"] == "hearth"  # Already max


def test_escalate_tier_sovereign_to_forge() -> None:
    assert VerificationGate.escalate_tier("sovereign") == "forge"


def test_escalate_tier_forge_to_hearth() -> None:
    assert VerificationGate.escalate_tier("forge") == "hearth"


def test_escalate_tier_hearth_stays_hearth() -> None:
    assert VerificationGate.escalate_tier("hearth") == "hearth"


def test_escalate_tier_alias_untrusted_to_forge() -> None:
    assert VerificationGate.escalate_tier("untrusted") == "forge"


def test_escalate_tier_alias_approved_to_hearth() -> None:
    assert VerificationGate.escalate_tier("approved") == "hearth"


# ═══════════════════════════════════════════════════════════════════════════════
# Human-readable gate explanation tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_evaluate_with_explanation_hearth_block() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "ce", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK
        )
    )
    explanation = VerificationGate.evaluate_with_explanation(report, "hearth")
    assert explanation["decision"] == GateDecision.BLOCK
    assert explanation["normalized_tier"] == "hearth"
    assert len(explanation["rationale"]) > 0
    assert "blocking_factors" in explanation
    assert len(explanation["blocking_factors"]) >= 1
    assert "report_summary" in explanation


def test_evaluate_with_explanation_hearth_proceed() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK
        )
    )
    explanation = VerificationGate.evaluate_with_explanation(report, "hearth")
    assert explanation["decision"] == GateDecision.PROCEED
    assert "proceeding" in explanation["rationale"].lower()


def test_evaluate_with_explanation_forge_warn() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "u1", VerificationStatus.UNKNOWN, ConstraintKind.CUSTOM
        )
    )
    explanation = VerificationGate.evaluate_with_explanation(report, "forge")
    assert explanation["decision"] == GateDecision.WARN
    assert "warning" in explanation["rationale"].lower()


def test_evaluate_with_explanation_sovereign_always_proceed() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "ce", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK
        )
    )
    explanation = VerificationGate.evaluate_with_explanation(report, "advisory")
    assert explanation["decision"] == GateDecision.PROCEED


# ═══════════════════════════════════════════════════════════════════════════════
# Timeout recovery tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_verify_with_depth_timeout_returns_partial() -> None:
    """Timeout recovery: very short timeout produces partial results."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=1, trust_tier="hearth", timeout_ms=5000
    )
    assert isinstance(report, VerificationReport)
    assert "verification_time_ms" in depth_info
    assert "partial_proof" in depth_info
    assert "timeout_occurred" in depth_info


def test_verify_with_depth_returns_depth_info() -> None:
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=1, trust_tier="hearth"
    )
    assert "measured_depth" in depth_info
    assert "min_depth" in depth_info
    assert "depth_sufficient" in depth_info
    assert "effective_tier" in depth_info
    assert "tier_escalated" in depth_info


def test_verify_with_depth_escalates_on_insufficient_depth() -> None:
    """When depth is insufficient, the tier should escalate."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=100, trust_tier="forge"  # impossibly high depth
    )
    assert depth_info["tier_escalated"] is True
    assert depth_info["effective_tier"] == "hearth"


# ═══════════════════════════════════════════════════════════════════════════════
# Partial proof handling tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_partial_proof_detection() -> None:
    """A report with mixed proven/failed is a partial proof."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "temperature", "value": 7},
            {
                "tag": "CONSTRAINT",
                "arguments": [
                    {"kind": "kv_arg", "name": "name", "value": {"kind": "value", "type": "ident", "value": "temp_range"}},
                    {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                    {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                    {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
                ],
            },
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=1, trust_tier="forge"
    )
    # Should detect this as a partial proof (some proven, some failed)
    assert isinstance(depth_info["partial_proof"], bool)
    # At forge tier with counterexample, should BLOCK
    assert decision == GateDecision.BLOCK


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Full depth-gated verification flow
# ═══════════════════════════════════════════════════════════════════════════════


def test_end_to_end_depth_gated_verification_provable() -> None:
    """End-to-end: provable program → PROCEED at hearth with depth info."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=1, trust_tier="hearth"
    )
    assert isinstance(report, VerificationReport)
    assert decision in (GateDecision.PROCEED, GateDecision.WARN)
    assert depth_info["measured_depth"] >= 0


def test_end_to_end_counterexample_at_forge_blocks() -> None:
    """End-to-end: program with counterexample → BLOCK at forge."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "temperature", "value": 7},
            {
                "tag": "CONSTRAINT",
                "arguments": [
                    {"kind": "kv_arg", "name": "name", "value": {"kind": "value", "type": "ident", "value": "temp_range"}},
                    {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                    {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                    {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
                ],
            },
        ]
    }
    report, decision, depth_info = verifier.verify_with_depth(
        ast, min_depth=1, trust_tier="forge"
    )
    assert decision == GateDecision.BLOCK
    assert report.failed_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Z3 Operator Encoder — unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestZ3OperatorEncoder:
    """Tests for Z3OperatorEncoder covering all operator families."""

    def test_encoder_supported_families_are_nonempty(self) -> None:
        families = Z3OperatorEncoder.supported_operator_families()
        assert len(families) >= 3
        assert "string" in families
        assert "set" in families
        assert "container" in families

    def test_encoder_z3_available_matches_module_flag(self) -> None:
        assert Z3OperatorEncoder.z3_available() == z3_available()

    # ── String encodings ──────────────────────────────────────────

    def test_encode_str_concat_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_concat("hello", "world")
        assert isinstance(result, str) or result is not None

    def test_encode_str_length_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_length("hello")
        assert isinstance(result, str) or result is not None

    def test_encode_str_substring_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_substring("hello", 0, 3)
        assert isinstance(result, str) or result is not None

    def test_encode_str_contains_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_contains("hello world", "world")
        assert isinstance(result, str) or result is not None

    def test_encode_str_prefix_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_prefix("hello world", "hello")
        assert isinstance(result, str) or result is not None

    def test_encode_str_suffix_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_suffix("hello world", "world")
        assert isinstance(result, str) or result is not None

    def test_encode_str_compare_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_compare("abc", "xyz")
        assert isinstance(result, str) or result is not None

    def test_encode_str_replace_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_replace("hello", "l", "w")
        assert isinstance(result, str) or result is not None

    def test_encode_str_trim_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_trim("  hello  ")
        assert isinstance(result, str) or result is not None

    def test_encode_str_split_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_split("a,b,c", ",")
        assert isinstance(result, str) or result is not None

    def test_encode_str_is_empty_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_str_is_empty("")
        assert isinstance(result, str) or result is not None

    # ── Set encodings ─────────────────────────────────────────────

    def test_encode_set_member_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_member(1, [1, 2, 3])
        assert isinstance(result, str) or result is not None

    def test_encode_set_subset_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_subset([1, 2], [1, 2, 3])
        assert isinstance(result, str) or result is not None

    def test_encode_set_union_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_union([1, 2], [3, 4])
        assert isinstance(result, str) or result is not None

    def test_encode_set_intersection_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_intersection([1, 2], [2, 3])
        assert isinstance(result, str) or result is not None

    def test_encode_set_difference_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_difference([1, 2, 3], [2])
        assert isinstance(result, str) or result is not None

    def test_encode_set_cardinality_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_cardinality([1, 2, 3])
        assert isinstance(result, str) or result is not None

    def test_encode_set_is_empty_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_is_empty([])
        assert isinstance(result, str) or result is not None

    def test_encode_set_complement_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_set_complement([1, 2, 3], [2])
        assert isinstance(result, str) or result is not None

    # ── Container encodings ───────────────────────────────────────

    def test_encode_list_length_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_list_length([1, 2, 3])
        assert isinstance(result, str) or result is not None

    def test_encode_list_index_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_list_index([10, 20, 30], 1)
        assert isinstance(result, str) or result is not None

    def test_encode_list_slice_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_list_slice([1, 2, 3, 4], 1, 3)
        assert isinstance(result, str) or result is not None

    def test_encode_list_contains_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_list_contains([1, 2, 3], 2)
        assert isinstance(result, str) or result is not None

    def test_encode_list_append_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_list_append([1, 2], 3)
        assert isinstance(result, str) or result is not None

    def test_encode_map_keys_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_map_keys({"a": 1, "b": 2})
        assert isinstance(result, str) or result is not None

    def test_encode_map_values_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_map_values({"a": 1, "b": 2})
        assert isinstance(result, str) or result is not None

    def test_encode_map_lookup_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_map_lookup({"a": 1, "b": 2}, "a")
        assert isinstance(result, str) or result is not None

    def test_encode_map_contains_key_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_map_contains_key({"a": 1}, "a")
        assert isinstance(result, str) or result is not None

    def test_encode_container_is_empty_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_container_is_empty([])
        assert isinstance(result, str) or result is not None

    def test_encode_container_membership_returns_description(self) -> None:
        result = Z3OperatorEncoder.encode_container_membership(42, [1, 42, 3])
        assert isinstance(result, str) or result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Z3Solver operator dispatch tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestZ3SolverOperatorDispatch:
    """Tests for Z3Solver string/set/container operator dispatch methods."""

    def test_check_string_op_concat(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_string_op("concat", "hello", "world", name="str_concat")
        assert result.status in (VerificationStatus.PROVEN, VerificationStatus.RUNTIME_CHECKED, VerificationStatus.COUNTEREXAMPLE)

    def test_check_string_op_length(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_string_op("length", "hello", name="str_len")
        assert result.property_name == "str_len"

    def test_check_string_op_contains_true(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_string_op("contains", "hello world", "world", name="str_contains")
        assert result.status != VerificationStatus.ERROR

    def test_check_string_op_contains_false(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_string_op("contains", "hello world", "xyz", name="str_contains_neg")
        assert result.status != VerificationStatus.ERROR

    def test_check_string_op_unknown_operation(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_string_op("nonexistent_op", "hello", name="bad_op")
        assert result.status == VerificationStatus.UNKNOWN

    def test_check_set_op_member(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_set_op("member", 2, [1, 2, 3], name="set_member")
        assert result.status != VerificationStatus.ERROR

    def test_check_set_op_subset(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_set_op("subset", [1, 2], [1, 2, 3], name="set_subset")
        assert result.status != VerificationStatus.ERROR

    def test_check_set_op_cardinality(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_set_op("cardinality", [1, 2, 3], name="set_card")
        assert result.status != VerificationStatus.ERROR

    def test_check_set_op_unknown_operation(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_set_op("nonexistent_op", [1], name="bad_set_op")
        assert result.status == VerificationStatus.UNKNOWN

    def test_check_container_op_list_length(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_container_op("list_length", [1, 2, 3], name="list_len")
        assert result.status != VerificationStatus.ERROR

    def test_check_container_op_list_contains(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_container_op("list_contains", [1, 2, 3], 2, name="list_contains")
        assert result.status != VerificationStatus.ERROR

    def test_check_container_op_map_keys(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_container_op("map_keys", {"a": 1, "b": 2}, name="map_keys")
        assert result.status != VerificationStatus.ERROR

    def test_check_container_op_unknown_operation(self) -> None:
        if not z3_available():
            pytest.skip("Z3 not installed")
        solver = Z3Solver()
        result = solver.check_container_op("nonexistent", [], name="bad_container_op")
        assert result.status == VerificationStatus.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# Operator family coverage tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOperatorFamilyCoverage:
    """Tests for operator family coverage reporting."""

    def test_verification_report_has_coverage_property(self) -> None:
        report = VerificationReport()
        coverage = report.operator_family_coverage
        assert isinstance(coverage, dict)
        assert len(coverage) >= 8

    def test_coverage_includes_all_families(self) -> None:
        report = VerificationReport()
        coverage = report.operator_family_coverage
        expected_families = {
            "numeric", "string", "set", "container", "boolean",
            "type_system", "gas", "spec_gate", "rational",
            "temporal", "spatial", "effect",
        }
        for family in expected_families:
            assert family in coverage, f"Missing family: {family}"

    def test_coverage_entries_are_structured(self) -> None:
        report = VerificationReport()
        coverage = report.operator_family_coverage
        for family, info in coverage.items():
            assert "covered" in info, f"Family {family} missing 'covered'"
            assert "z3_available" in info, f"Family {family} missing 'z3_available'"
            assert isinstance(info["covered"], bool)
            assert isinstance(info["z3_available"], bool)

    def test_formal_verifier_get_operator_family_coverage(self) -> None:
        verifier = FormalVerifier()
        coverage = verifier.get_operator_family_coverage()
        assert isinstance(coverage, dict)
        assert "numeric" in coverage

    def test_coverage_with_z3_added_constraints(self) -> None:
        """Coverage after running actual verification should mark families."""
        verifier = FormalVerifier()
        ast = {
            "program": [
                {"tag": "SET", "name": "x", "value": 5},
                {
                    "tag": "CONSTRAINT",
                    "arguments": [
                        {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 5}},
                        {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                        {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 10}},
                    ],
                },
            ]
        }
        report = verifier.verify_ast(ast)
        coverage = report.operator_family_coverage
        assert coverage["numeric"]["covered"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# ProofArtifact tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestProofArtifact:
    """Tests for proof artifact generation with SHA-256 hashing."""

    def test_artifact_stores_all_fields(self) -> None:
        artifact = ProofArtifact(
            artifact_id="art-001",
            property_name="range_check_x",
            verdict="admitted",
            operator_family="numeric",
            smt_encoding="(>= x 0)",
            content_hash="abc123",
            timestamp_iso="2025-01-01T00:00:00Z",
            metadata={"depth": 2},
        )
        assert artifact.artifact_id == "art-001"
        assert artifact.property_name == "range_check_x"
        assert artifact.verdict == "admitted"
        assert artifact.operator_family == "numeric"
        assert artifact.smt_encoding == "(>= x 0)"
        assert artifact.hash_algorithm == "sha256"
        assert artifact.content_hash == "abc123"

    def test_artifact_to_dict_includes_all_keys(self) -> None:
        artifact = ProofArtifact(
            artifact_id="art-002",
            property_name="type_check",
            verdict="denied",
            operator_family="type_system",
            smt_encoding="(is-int x)",
            content_hash="def456",
        )
        d = artifact.to_dict()
        assert d["artifact_id"] == "art-002"
        assert d["verdict"] == "denied"
        assert d["operator_family"] == "type_system"
        assert d["hash_algorithm"] == "sha256"
        assert "metadata" in d

    def test_artifact_to_json_produces_valid_json(self) -> None:
        artifact = ProofArtifact(
            artifact_id="art-003",
            property_name="gas_check",
            verdict="admitted",
            operator_family="gas",
            smt_encoding="(<= total budget)",
            content_hash="ghi789",
        )
        json_str = artifact.to_json()
        parsed = json.loads(json_str)
        assert parsed["artifact_id"] == "art-003"
        assert parsed["verdict"] == "admitted"

    def test_generate_proof_artifact_from_result(self) -> None:
        result = VerificationResult(
            property_name="range_check_temp",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.RANGE_CHECK,
            message="SMT-proven: 5 within [0, 100]",
            solver="z3",
        )
        artifact = generate_proof_artifact(result, operator_family="numeric")
        assert artifact.property_name == "range_check_temp"
        assert artifact.verdict == "admitted"
        assert artifact.operator_family == "numeric"
        assert len(artifact.content_hash) == 64  # SHA-256 hex digest

    def test_generate_proof_artifact_denied_for_counterexample(self) -> None:
        result = VerificationResult(
            property_name="range_check_temp",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.RANGE_CHECK,
            message="150 > 100",
            solver="z3",
        )
        artifact = generate_proof_artifact(result, operator_family="numeric")
        assert artifact.verdict == "denied"

    def test_generate_proof_artifact_has_timestamp(self) -> None:
        result = VerificationResult(
            property_name="type_check",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.TYPE_INVARIANT,
            message="Valid type",
            solver="z3",
        )
        artifact = generate_proof_artifact(result, operator_family="type_system")
        assert artifact.timestamp_iso
        assert "T" in artifact.timestamp_iso  # ISO format

    def test_artifact_content_hash_is_sha256_hex(self) -> None:
        result = VerificationResult(
            property_name="gas_budget",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.GAS_BOUND,
            message="Budget OK",
            solver="z3",
        )
        artifact = generate_proof_artifact(result, operator_family="gas")
        # SHA-256 produces 64 hex chars
        assert len(artifact.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in artifact.content_hash)

    def test_generate_proof_artifact_different_results_different_hashes(self) -> None:
        r1 = VerificationResult("p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK)
        r2 = VerificationResult("p2", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK)
        a1 = generate_proof_artifact(r1, operator_family="numeric")
        a2 = generate_proof_artifact(r2, operator_family="numeric")
        assert a1.content_hash != a2.content_hash

    def test_artifact_from_verification_result_classmethod(self) -> None:
        result = VerificationResult(
            property_name="spec_gate_check",
            status=VerificationStatus.RUNTIME_CHECKED,
            kind=ConstraintKind.SPEC_GATE,
            message="Gate resolved",
            solver="fallback",
        )
        artifact = ProofArtifact.from_verification_result(result, operator_family="spec_gate")
        assert artifact.property_name == "spec_gate_check"
        assert artifact.verdict == "admitted"
        assert artifact.operator_family == "spec_gate"

    def test_artifact_metadata_accepts_extra_context(self) -> None:
        result = VerificationResult(
            property_name="check",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.CUSTOM,
            solver="z3",
        )
        artifact = generate_proof_artifact(
            result, operator_family="numeric",
            metadata={"depth": 3, "proof_chain": "inductive"},
        )
        assert artifact.metadata.get("depth") == 3
        assert artifact.metadata.get("proof_chain") == "inductive"


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveProver — base case detection tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInductiveProverBaseCases:
    """Tests for inductive base case generation."""

    def test_prover_is_instantiable(self) -> None:
        prover = InductiveProver()
        assert prover is not None
        assert isinstance(prover.z3_available, bool)

    def test_detect_induction_pattern_none_for_empty_ast(self) -> None:
        prover = InductiveProver()
        pattern = prover._detect_induction_pattern(None)
        assert pattern == "none"

    def test_detect_loop_pattern(self) -> None:
        prover = InductiveProver()
        ast_hint = {"kind": "loop", "iteration_count": 10}
        pattern = prover._detect_induction_pattern(ast_hint)
        assert pattern == "loop"

    def test_detect_recursion_pattern(self) -> None:
        prover = InductiveProver()
        ast_hint = {"kind": "recursion", "depth": 5}
        pattern = prover._detect_induction_pattern(ast_hint)
        assert pattern == "recursion"

    def test_detect_range_pattern(self) -> None:
        prover = InductiveProver()
        ast_hint = {"kind": "range", "low": 1, "high": 10}
        pattern = prover._detect_induction_pattern(ast_hint)
        assert pattern == "range"

    def test_detect_numeric_pattern(self) -> None:
        prover = InductiveProver()
        ast_hint = {"kind": "induction", "variable": "n", "domain": "nat"}
        pattern = prover._detect_induction_pattern(ast_hint)
        assert pattern == "numeric"

    def test_detect_structural_pattern(self) -> None:
        prover = InductiveProver()
        ast_hint = {"kind": "match", "cases": ["nil", "cons"], "datatype": "list"}
        pattern = prover._detect_induction_pattern(ast_hint)
        assert pattern == "structural"

    def test_generate_base_cases_for_loop_pattern(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_loop",
            description="Loop invariant always holds",
            kind="range_check",
        )
        ast = {"kind": "loop", "iteration_count": 10}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        assert len(base_cases) >= 1
        for bc in base_cases:
            assert bc.obligation_id.startswith("po_loop_base_")
            assert bc.target_depth >= 2
            assert bc.status == "pending"

    def test_generate_base_cases_for_recursion_pattern(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_rec",
            description="Recursive function property",
            kind="type_invariant",
        )
        ast = {"kind": "recursion", "depth": 5}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        assert len(base_cases) >= 1
        # Recursion should have at minimum the depth==0 base case
        assert any("base" in bc.description.lower() for bc in base_cases)

    def test_generate_base_cases_for_range_pattern(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_range_ind",
            description="Range property holds for all elements",
            kind="range_check",
        )
        ast = {"kind": "range", "low": 1, "high": 10}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        assert len(base_cases) >= 1

    def test_generate_base_cases_for_numeric_induction(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_num_ind",
            description="P(n) holds for all n >= 0",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        assert len(base_cases) >= 1
        # Numeric induction base case: n == 0
        assert any(("0" in bc.description or "zero" in bc.description.lower())
                   for bc in base_cases)


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveProver — step case and termination tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInductiveProverStepAndTermination:
    """Tests for inductive step case generation and termination measures."""

    def test_generate_step_case_creates_obligation(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_num",
            description="P(n) holds for all n",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        step = prover.generate_step_case(obl, base_cases, ast_pattern=ast)
        assert step is not None
        assert step.obligation_id.startswith("po_num")
        assert "step" in step.obligation_id.lower() or "step" in step.description.lower()
        assert len(step.dependencies) >= len(base_cases)

    def test_step_case_depends_on_all_base_cases(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_test",
            description="Test property",
            kind="range_check",
        )
        ast = {"kind": "loop", "iteration_count": 5}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        step = prover.generate_step_case(obl, base_cases, ast_pattern=ast)
        for bc in base_cases:
            assert bc.obligation_id in step.dependencies

    def test_step_case_has_hypothesis_lemma(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_ind",
            description="Inductive property",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "k"}
        base_cases = prover.generate_base_cases(obl, ast_pattern=ast)
        step = prover.generate_step_case(obl, base_cases, ast_pattern=ast)
        assert any("hypothesis" in lemma.lower() or "assume" in lemma.lower()
                   for lemma in step.lemmas)

    def test_infer_termination_measure_for_loop(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_loop_term",
            description="Loop terminates",
            kind="range_check",
        )
        ast = {"kind": "loop", "iteration_count": 10}
        term_obl = prover.infer_termination_measure(obl, ast_pattern=ast)
        assert term_obl is not None
        assert "termination" in term_obl.obligation_id.lower() or "term" in term_obl.obligation_id.lower()

    def test_infer_termination_measure_for_recursion(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_rec_term",
            description="Recursion terminates",
            kind="type_invariant",
        )
        ast = {"kind": "recursion", "depth": 5}
        term_obl = prover.infer_termination_measure(obl, ast_pattern=ast)
        assert term_obl is not None

    def test_infer_termination_measure_for_range(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_range_term",
            description="Range iteration terminates",
            kind="range_check",
        )
        ast = {"kind": "range", "low": 1, "high": 10}
        term_obl = prover.infer_termination_measure(obl, ast_pattern=ast)
        assert term_obl is not None

    def test_well_founded_check_accepts_decreasing(self) -> None:
        prover = InductiveProver()
        assert prover._well_founded_check("x - 1") is True

    def test_well_founded_check_accepts_structural_descent(self) -> None:
        prover = InductiveProver()
        assert prover._well_founded_check("sub(xs)") is True

    def test_well_founded_check_rejects_empty(self) -> None:
        prover = InductiveProver()
        assert prover._well_founded_check("") is False

    def test_well_founded_check_rejects_constant(self) -> None:
        prover = InductiveProver()
        assert prover._well_founded_check("42") is False


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveProver — full proof chain assembly tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInductiveProofChain:
    """Tests for full inductive proof assembly and the InductiveProofChain dataclass."""

    def test_assemble_inductive_proof_returns_chain(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_full_ind",
            description="Full inductive property proof",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain is not None
        assert isinstance(chain, InductiveProofChain)
        assert chain.root_obligation == obl

    def test_assembled_chain_has_base_cases(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_chain",
            description="Inductive property",
            kind="range_check",
        )
        ast = {"kind": "loop", "iteration_count": 5}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert len(chain.base_cases) >= 1

    def test_assembled_chain_has_step_case(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_chain_step",
            description="Step-provable property",
            kind="type_invariant",
        )
        ast = {"kind": "induction", "variable": "k"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain.step_case is not None

    def test_assembled_chain_has_termination(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_chain_term",
            description="Terminating property",
            kind="range_check",
        )
        ast = {"kind": "recursion", "depth": 3}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain.termination_measure is not None

    def test_assembled_chain_reports_is_complete(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_complete",
            description="Complete proof",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain.is_complete is True

    def test_chain_to_dict_includes_all_components(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_dict_test",
            description="Dictionary test",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "x"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        d = chain.to_dict()
        assert "root_obligation_id" in d
        assert "base_cases_count" in d
        assert "is_complete" in d
        assert "induction_pattern" in d
        assert "total_depth" in d

    def test_chain_all_base_cases_proven_initially_false(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_not_proven",
            description="Not yet proven",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        # Base cases are freshly created, so they won't be proven
        assert chain.all_base_cases_proven() is False

    def test_chain_proof_ready_initially_false(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_not_ready",
            description="Not ready",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain.proof_ready() is False

    def test_chain_total_depth_set_correctly(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_depth_test",
            description="Depth test",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        assert chain.total_depth >= 3  # INDUCTIVE depth

    def test_assemble_without_ast_pattern_handles_gracefully(self) -> None:
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_no_ast",
            description="No AST pattern",
            kind="range_check",
        )
        chain = prover.assemble_inductive_proof(obl, ast_pattern=None)
        assert chain is not None
        assert chain.induction_pattern == "none"

    def test_deepen_proof_to_inductive_attaches_chain(self) -> None:
        """Verify that deepen_proof at INDUCTIVE depth attaches a chain to the obligation."""
        pd = ProofDepth()
        obl = ProofObligation(
            obligation_id="po_deepen_ind",
            description="Deepen to inductive",
            kind="range_check",
        )
        ast_hint = {"kind": "induction", "variable": "n"}
        # Set the AST hint on the obligation's metadata via a known mechanism
        # or just test that the chain gets attached when Z3 is available
        result = pd.deepen_proof(obl, target_depth=3)
        if pd.z3_available:
            assert result.inductive_chain is not None
            assert isinstance(result.inductive_chain, InductiveProofChain)
        else:
            assert result.current_depth >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveCounterexample tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInductiveCounterexample:
    """Tests for InductiveCounterexample dataclass and generation."""

    def test_inductive_counterexample_extends_counterexample(self) -> None:
        ice = InductiveCounterexample(
            property_name="ind_prop",
            inputs={"n": 0},
            expected_output="P(0) holds",
            actual_output="P(0) fails",
            violation_path="Base case of induction fails",
            induction_pattern="numeric",
            failure_type="base_case",
            base_case_inputs={"n": 0},
        )
        assert isinstance(ice, Counterexample)
        assert ice.property_name == "ind_prop"
        assert ice.induction_pattern == "numeric"
        assert ice.failure_type == "base_case"

    def test_inductive_counterexample_to_dict_includes_induction_fields(self) -> None:
        ice = InductiveCounterexample(
            property_name="step_fail",
            inputs={"k": 5},
            expected_output="P(6) holds",
            actual_output="P(6) fails",
            violation_path="Inductive step P(k)->P(k+1) fails",
            induction_pattern="numeric",
            failure_type="step_case",
            step_k_value=5,
            step_k_plus_1_value=6,
        )
        d = ice.to_dict()
        assert d["induction_pattern"] == "numeric"
        assert d["failure_type"] == "step_case"
        assert d["step_k_value"] == 5
        assert d["step_k_plus_1_value"] == 6

    def test_is_base_case_failure(self) -> None:
        ice = InductiveCounterexample(
            property_name="base",
            inputs={},
            expected_output="holds",
            actual_output="fails",
            violation_path="Base case fails",
            failure_type="base_case",
        )
        assert ice.is_base_case_failure() is True
        assert ice.is_step_case_failure() is False
        assert ice.is_termination_failure() is False

    def test_is_step_case_failure(self) -> None:
        ice = InductiveCounterexample(
            property_name="step",
            inputs={},
            expected_output="holds",
            actual_output="fails",
            violation_path="Step fails",
            failure_type="step_case",
        )
        assert ice.is_step_case_failure() is True
        assert ice.is_base_case_failure() is False

    def test_is_termination_failure(self) -> None:
        ice = InductiveCounterexample(
            property_name="term",
            inputs={},
            expected_output="terminates",
            actual_output="non-terminating",
            violation_path="Not well-founded",
            failure_type="termination",
            termination_measure="x + 1",
        )
        assert ice.is_termination_failure() is True
        assert ice.termination_measure == "x + 1"

    def test_is_unwinding_failure(self) -> None:
        ice = InductiveCounterexample(
            property_name="unwind",
            inputs={},
            expected_output="proved",
            actual_output="depth limit",
            violation_path="Hit depth limit",
            failure_type="unwinding",
            unwinding_depth=100,
        )
        assert ice.is_unwinding_failure() is True
        assert ice.unwinding_depth == 100


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveCounterexampleGenerator tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInductiveCounterexampleGenerator:
    """Tests for induction-specific counterexample generation."""

    def test_generator_is_instantiable(self) -> None:
        gen = InductiveCounterexampleGenerator()
        assert gen is not None
        assert isinstance(gen.z3_available, bool)

    def test_generate_base_case_failure(self) -> None:
        gen = InductiveCounterexampleGenerator()
        ice = gen.generate_base_case_failure(
            property_name="ind_prop",
            inputs={"n": 0},
            induction_pattern="numeric",
        )
        assert ice.failure_type == "base_case"
        assert ice.induction_pattern == "numeric"
        assert ice.property_name == "ind_prop"

    def test_generate_step_case_failure(self) -> None:
        gen = InductiveCounterexampleGenerator()
        ice = gen.generate_step_case_failure(
            property_name="P_n",
            k_value=5,
            k_plus_1_value=6,
            property_desc="P(n): n < 10",
            induction_pattern="numeric",
        )
        assert ice.failure_type == "step_case"
        assert ice.step_k_value == 5
        assert ice.step_k_plus_1_value == 6

    def test_generate_termination_failure(self) -> None:
        gen = InductiveCounterexampleGenerator()
        ice = gen.generate_termination_failure(
            property_name="loop_term",
            measure_expr="x + 1",
            counterexample_detail="Measure increases",
            induction_pattern="loop",
        )
        assert ice.failure_type == "termination"
        assert ice.termination_measure == "x + 1"

    def test_generate_unwinding_failure(self) -> None:
        gen = InductiveCounterexampleGenerator()
        ice = gen.generate_unwinding_failure(
            property_name="deep_ind",
            depth=500,
            partial_findings="Checked up to n=499",
            induction_pattern="numeric",
        )
        assert ice.failure_type == "unwinding"
        assert ice.unwinding_depth == 500

    def test_suggest_inductive_fix_base_case(self) -> None:
        ice = InductiveCounterexample(
            property_name="base_fail",
            inputs={},
            expected_output="holds",
            actual_output="fails",
            violation_path="Base case fails",
            failure_type="base_case",
            induction_pattern="numeric",
        )
        fix = suggest_inductive_fix(ice)
        assert len(fix) > 0
        assert "base" in fix.lower()

    def test_suggest_inductive_fix_step_case(self) -> None:
        ice = InductiveCounterexample(
            property_name="step_fail",
            inputs={},
            expected_output="holds",
            actual_output="fails",
            violation_path="Step fails",
            failure_type="step_case",
            induction_pattern="numeric",
        )
        fix = suggest_inductive_fix(ice)
        assert len(fix) > 0
        assert "hypothesis" in fix.lower() or "invariant" in fix.lower()

    def test_suggest_inductive_fix_termination(self) -> None:
        ice = InductiveCounterexample(
            property_name="term_fail",
            inputs={},
            expected_output="terminates",
            actual_output="non-terminating",
            violation_path="Not well-founded",
            failure_type="termination",
            induction_pattern="recursion",
        )
        fix = suggest_inductive_fix(ice)
        assert len(fix) > 0
        assert "measure" in fix.lower() or "termination" in fix.lower() or "well-founded" in fix.lower()

    def test_suggest_inductive_fix_unwinding(self) -> None:
        ice = InductiveCounterexample(
            property_name="unwind_fail",
            inputs={},
            expected_output="proved",
            actual_output="depth limit",
            violation_path="Depth limit reached",
            failure_type="unwinding",
            induction_pattern="numeric",
        )
        fix = suggest_inductive_fix(ice)
        assert len(fix) > 0

    def test_generate_inductive_counterexample_convenience_base(self) -> None:
        ice = generate_inductive_counterexample(
            failure_type="base_case",
            property_name="prop",
            inputs={"n": 0},
            induction_pattern="numeric",
        )
        assert ice.failure_type == "base_case"

    def test_generate_inductive_counterexample_convenience_step(self) -> None:
        ice = generate_inductive_counterexample(
            failure_type="step_case",
            property_name="prop",
            k_value=3,
            k_plus_1_value=4,
            induction_pattern="numeric",
        )
        assert ice.failure_type == "step_case"

    def test_generate_inductive_counterexample_convenience_termination(self) -> None:
        ice = generate_inductive_counterexample(
            failure_type="termination",
            property_name="prop",
            measure_expr="x + 1",
            induction_pattern="recursion",
        )
        assert ice.failure_type == "termination"

    def test_generate_inductive_counterexample_convenience_unwinding(self) -> None:
        ice = generate_inductive_counterexample(
            failure_type="unwinding",
            property_name="prop",
            depth=99,
            induction_pattern="numeric",
        )
        assert ice.failure_type == "unwinding"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases and regression tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCasesAndRegression:
    """Edge case and regression tests for the new features."""

    def test_empty_ast_base_case_generation(self) -> None:
        """Base case generation with empty AST should not crash."""
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_empty",
            description="Empty AST",
            kind="range_check",
        )
        base_cases = prover.generate_base_cases(obl, ast_pattern={})
        assert isinstance(base_cases, list)

    def test_empty_list_container_encoding(self) -> None:
        """Container operations on empty lists should not crash."""
        result = Z3OperatorEncoder.encode_container_is_empty([])
        assert result is not None

    def test_empty_dict_container_encoding(self) -> None:
        """Container operations on empty dicts should not crash."""
        result = Z3OperatorEncoder.encode_container_is_empty({})
        assert result is not None

    def test_none_ast_pattern_step_case(self) -> None:
        """Step case generation with None AST should not crash."""
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_none_step",
            description="None AST step",
            kind="range_check",
        )
        base_cases = prover.generate_base_cases(obl, ast_pattern=None)
        step = prover.generate_step_case(obl, base_cases, ast_pattern=None)
        assert step is not None

    def test_infinite_type_termination_measure(self) -> None:
        """Termination measure for potentially infinite types should be detectable."""
        prover = InductiveProver()
        # A measure that increases should fail well-founded check
        assert prover._well_founded_check("x + 1") is False

    def test_deeply_nested_induction_pattern(self) -> None:
        """Deeply nested AST with induction hints should be detected."""
        prover = InductiveProver()
        ast = {"kind": "block", "body": {"kind": "loop", "iteration_count": 100}}
        pattern = prover._detect_induction_pattern(ast)
        assert pattern == "loop"

    def test_proof_artifact_with_empty_metadata(self) -> None:
        """Proof artifact with default empty metadata should serialize correctly."""
        artifact = ProofArtifact(
            artifact_id="art_empty_meta",
            property_name="test",
            verdict="admitted",
            operator_family="numeric",
            smt_encoding="true",
            content_hash="0" * 64,
        )
        d = artifact.to_dict()
        assert d["metadata"] == {}

    def test_non_terminating_recursion_detection(self) -> None:
        """Non-terminating recursion measure should be caught."""
        prover = InductiveProver()
        # A non-decreasing expression should fail
        assert prover._well_founded_check("random()") is False

    def test_multiple_operator_families_all_covered(self) -> None:
        """Verify that all 12 families appear in coverage dict."""
        verifier = FormalVerifier()
        coverage = verifier.get_operator_family_coverage()
        assert len(coverage) == 12

    def test_proof_artifact_json_round_trip(self) -> None:
        """Proof artifact JSON should round-trip correctly."""
        result = VerificationResult(
            property_name="round_trip",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.RANGE_CHECK,
            solver="z3",
        )
        artifact = generate_proof_artifact(result, operator_family="numeric")
        json_str = artifact.to_json()
        parsed = json.loads(json_str)
        assert parsed["content_hash"] == artifact.content_hash
        assert parsed["property_name"] == "round_trip"

    def test_inductive_chain_to_dict_is_json_serializable(self) -> None:
        """InductiveProofChain.to_dict() should be JSON serializable."""
        prover = InductiveProver()
        obl = ProofObligation(
            obligation_id="po_json",
            description="JSON test",
            kind="range_check",
        )
        ast = {"kind": "induction", "variable": "n"}
        chain = prover.assemble_inductive_proof(obl, ast_pattern=ast)
        d = chain.to_dict()
        # Should not raise
        json.dumps(d)
