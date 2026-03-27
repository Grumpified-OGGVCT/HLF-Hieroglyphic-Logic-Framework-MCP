from __future__ import annotations

from hlf_mcp.hlf import build_embodied_action_envelope
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    FormalVerifier,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    normalize_ast,
)
from hlf_mcp.hlf.memory_node import build_pointer_ref


def test_verification_report_tracks_all_status_counts() -> None:
    report = VerificationReport()
    report.add(VerificationResult("proven", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK))
    report.add(
        VerificationResult("failed", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK)
    )
    report.add(VerificationResult("unknown", VerificationStatus.UNKNOWN, ConstraintKind.CUSTOM))
    report.add(VerificationResult("skipped", VerificationStatus.SKIPPED, ConstraintKind.SPEC_GATE))
    report.add(VerificationResult("error", VerificationStatus.ERROR, ConstraintKind.TYPE_INVARIANT))

    payload = report.to_dict()

    assert payload["total"] == 5
    assert payload["proven"] == 1
    assert payload["failed"] == 1
    assert payload["unknown"] == 1
    assert payload["skipped"] == 1
    assert payload["errors"] == 1
    assert payload["operator_summary"]


def test_normalize_ast_accepts_nested_compiler_payload() -> None:
    normalized = normalize_ast({"ast": {"program": [{"tag": "SET", "name": "x", "value": 1}]}})

    assert normalized == {"program": [{"tag": "SET", "name": "x", "value": 1}], "env": {}}


def test_verify_ast_emits_proven_and_skipped_results_from_packaged_ast() -> None:
    verifier = FormalVerifier()

    report = verifier.verify_ast(
        {
            "ast": {
                "program": [
                    {"tag": "SET", "name": "x", "value": 1},
                    {"tag": "SPEC_GATE", "condition": {"op": "COMPARE"}},
                ]
            }
        }
    )
    statuses = {result["status"] for result in report.to_dict()["results"]}

    assert "proven" in statuses or "runtime_checked" in statuses
    assert "skipped" in statuses


def test_verify_ast_returns_skipped_when_no_constraints_are_extracted() -> None:
    verifier = FormalVerifier()

    report = verifier.verify_ast({"program": []})

    assert report.to_dict()["results"][0]["status"] == "skipped"


def test_normalize_ast_accepts_packaged_statements_payload() -> None:
    verifier = FormalVerifier()

    report = verifier.verify_constraints(
        {
            "statements": [
                {"tag": "SET", "name": "temperature", "value": 7},
            ]
        }
    )

    assert report.proven_count == 1
    assert report.all_proven is True


def test_verify_type_returns_counterexample_for_invalid_invariant() -> None:
    verifier = FormalVerifier()

    result = verifier.verify_type("not-a-number", "number", property_name="numeric_contract")

    assert result.status == VerificationStatus.COUNTEREXAMPLE
    assert result.counterexample is not None


def test_verify_gas_budget_returns_counterexample_when_budget_is_exceeded() -> None:
    verifier = FormalVerifier()

    result = verifier.verify_gas_budget(
        [4000, 4000, 4000], 10000, property_name="mission_gas_budget"
    )

    assert result.status == VerificationStatus.COUNTEREXAMPLE
    assert result.counterexample == {"total_gas": 12000, "budget": 10000, "over_by": 2000}


def test_verify_ast_interprets_compiler_constraint_fields() -> None:
    compiler = HLFCompiler()
    verifier = FormalVerifier()

    compiled = compiler.compile(
        '[HLF-v3]\nΔ [INTENT] goal="bounded"\nЖ [CONSTRAINT] value=7 min=1 max=5\nΩ\n'
    )

    report = verifier.verify_ast(compiled["ast"])
    results = report.to_dict()["results"]
    range_result = next(result for result in results if result["kind"] == "range_check")

    assert range_result["status"] == "counterexample"
    assert range_result["counterexample"] == {
        "value": 7,
        "bound": 5.0,
        "comparison": "above_high",
    }


def test_verify_ast_proves_compiler_spec_gate_literals() -> None:
    compiler = HLFCompiler()
    verifier = FormalVerifier()

    compiled = compiler.compile(
        '[HLF-v3]\nSPEC_GATE [MIGRATION] rollback_on_fail=true quorum=2\nΩ\n'
    )

    report = verifier.verify_ast(compiled["ast"])
    results = report.to_dict()["results"]
    spec_gate = next(result for result in results if result["kind"] == "spec_gate")

    assert spec_gate["status"] in ("proven", "runtime_checked")
    assert "rollback_on_fail" in spec_gate["message"]


def test_verify_ast_returns_counterexample_for_false_spec_gate_literal() -> None:
    compiler = HLFCompiler()
    verifier = FormalVerifier()

    compiled = compiler.compile(
        '[HLF-v3]\nSPEC_GATE [MIGRATION] rollback_on_fail=false\nΩ\n'
    )

    report = verifier.verify_ast(compiled["ast"])
    results = report.to_dict()["results"]
    spec_gate = next(result for result in results if result["kind"] == "spec_gate")

    assert spec_gate["status"] == "counterexample"
    assert spec_gate["counterexample"] == {"field": "rollback_on_fail", "value": False}


def test_verify_embodied_contract_accepts_bounded_simulation_contract() -> None:
    verifier = FormalVerifier()
    evidence_ref = build_pointer_ref("sim-camera", "frame-proof-001")
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_a",
        bounds={"workspace": "tray-a", "max_delta_mm": 25},
        timeout_ms=1500,
        operator_intent="simulate a bounded move",
        execution_mode="simulation",
        evidence_refs=[evidence_ref],
    )

    report = verifier.verify_embodied_contract(
        {
            "embodied": True,
            "function_name": "GUARDED_ACTUATE",
            "simulation_only": True,
            "bounded_spatial_envelope": True,
            "action_envelope": envelope,
            "spatial_bounds": {"max_delta_mm": 25},
            "evidence_refs": [evidence_ref],
            "world_state_ref": "",
        }
    )

    payload = report.to_dict()

    assert payload["failed"] == 0
    assert payload["proven"] >= 4


def test_verify_embodied_contract_rejects_unbounded_guarded_actuate() -> None:
    verifier = FormalVerifier()
    evidence_ref = build_pointer_ref("sim-camera", "frame-proof-002")
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_a",
        bounds={"workspace": "tray-a"},
        timeout_ms=1500,
        operator_intent="simulate an unbounded move",
        execution_mode="simulation",
        evidence_refs=[evidence_ref],
    )

    report = verifier.verify_embodied_contract(
        {
            "embodied": True,
            "function_name": "GUARDED_ACTUATE",
            "simulation_only": True,
            "bounded_spatial_envelope": False,
            "action_envelope": envelope,
            "spatial_bounds": {},
            "evidence_refs": [evidence_ref],
            "world_state_ref": "",
        }
    )

    payload = report.to_dict()
    spatial_result = next(
        result for result in payload["results"] if result["property"] == "guarded_actuate_spatial_envelope"
    )

    assert payload["failed"] >= 1
    assert spatial_result["status"] == "counterexample"
