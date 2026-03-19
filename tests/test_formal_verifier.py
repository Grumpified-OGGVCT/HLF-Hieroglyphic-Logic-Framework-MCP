from __future__ import annotations

from hlf_mcp.hlf.formal_verifier import ConstraintKind, FormalVerifier, VerificationReport, VerificationResult, VerificationStatus, normalize_ast


def test_verification_report_tracks_all_status_counts() -> None:
    report = VerificationReport()
    report.add(VerificationResult("proven", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK))
    report.add(VerificationResult("failed", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK))
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

    assert normalized == {"program": [{"tag": "SET", "name": "x", "value": 1}]}


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

    assert "proven" in statuses
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

    result = verifier.verify_gas_budget([4000, 4000, 4000], 10000, property_name="mission_gas_budget")

    assert result.status == VerificationStatus.COUNTEREXAMPLE
    assert result.counterexample == {"total_gas": 12000, "budget": 10000, "over_by": 2000}
