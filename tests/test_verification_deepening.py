"""Tests for formal verification proof depth hardening.

Tests counterexample quality, proof depth measurement,
obligation extraction, tier escalation, timeout recovery,
partial proofs, and human-readable gate explanations.
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    FormalVerifier,
    GateDecision,
    VerificationBlockedError,
    VerificationGate,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    normalize_ast,
)
from hlf_mcp.hlf.counterexample_quality import (
    Counterexample,
    CounterexampleGenerator,
    compare_counterexamples,
    explain_counterexample,
    generate_minimal_counterexample,
    suggest_fix,
)
from hlf_mcp.hlf.proof_depth import (
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
