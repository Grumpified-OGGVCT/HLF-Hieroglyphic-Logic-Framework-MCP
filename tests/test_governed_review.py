from __future__ import annotations


def test_build_spec_sentinel_governed_review_warns_on_drift() -> None:
    from hlf_mcp.governed_review import build_spec_sentinel_governed_review

    review = build_spec_sentinel_governed_review(
        {
            "drift_detected": True,
            "findings": [
                {"check": "bytecode_spec_vs_op_enum", "drift": True},
                {"check": "readme_count_accuracy", "drift": False},
            ],
        },
        ai_analysis_payload={"model": "nemotron-3-super", "audit_trail": [{"model": "nemotron-3-super"}]},
    )

    assert review["automation_status"] == "generated"
    assert review["severity"] == "warning"
    assert review["recommended_triage_lane"] == "current_batch"


def test_build_test_health_governed_review_escalates_low_coverage() -> None:
    from hlf_mcp.governed_review import build_test_health_governed_review

    review = build_test_health_governed_review(
        {"totals": {"percent_covered": 52.5}},
        test_suggestions_payload={
            "model": "devstral:24b",
            "audit_trail": [{"model": "devstral:24b"}],
            "existing_test_context": {"matched_test_files": ["tests/test_security.py"]},
        },
    )

    assert review["severity"] == "critical"
    assert review["recommended_triage_lane"] == "current_batch"
    assert review["backend"]["model"] == "devstral:24b"
    assert review["review_metadata"]["ai_suggestions_advisory_only"] is True
    assert review["review_metadata"]["requires_deduplication_against_existing_tests"] is True
    assert review["review_metadata"]["preferred_integration_strategy"] == "extend_existing_test_suites"
    assert review["review_metadata"]["existing_test_context_present"] is True
    assert "advisory only" in review["summary"]


def test_build_ethics_review_governed_review_ignores_no_actionable_findings() -> None:
    from hlf_mcp.governed_review import build_ethics_review_governed_review

    review = build_ethics_review_governed_review(
        {"summary_text": "Ethics surfaces checked."},
        ethics_review_payload={"content": "NO_ACTIONABLE_FINDINGS"},
    )

    assert review["severity"] == "info"
    assert review["recommended_triage_lane"] == "ignore"


def test_build_code_quality_governed_review_warns_on_open_alerts() -> None:
    from hlf_mcp.governed_review import build_code_quality_governed_review

    review = build_code_quality_governed_review(
        {"coverage_xml_present": True},
        security_findings_payload={
            "summary": {
                "open_alerts": 2,
                "severity_counts": {"high": 0},
            }
        },
    )

    assert review["severity"] == "warning"
    assert review["recommended_triage_lane"] == "backlog"


def test_build_doc_accuracy_governed_review_marks_drift_as_backlog() -> None:
    from hlf_mcp.governed_review import build_doc_accuracy_governed_review

    review = build_doc_accuracy_governed_review(
        {
            "drift_detected": True,
            "findings": [
                {"check": "readme_count_accuracy", "drift": True},
                {"check": "bytecode_spec_vs_op_enum", "drift": False},
            ],
        }
    )

    assert review["severity"] == "warning"
    assert review["recommended_triage_lane"] == "backlog"


def test_build_security_patterns_governed_review_escalates_actionable_findings() -> None:
    from hlf_mcp.governed_review import build_security_patterns_governed_review

    review = build_security_patterns_governed_review(
        {
            "model": "deepseek-r1:14b",
            "audit_trail": [{"model": "deepseek-r1:14b"}],
            "content": "1. ALIGN gap\n2. EVIDENCE: compiler path\n3. ATTACK_PATH\n4. IMPACT\n5. FIX",
        }
    )

    assert review["severity"] == "critical"
    assert review["recommended_triage_lane"] == "current_batch"
    assert review["backend"]["model"] == "deepseek-r1:14b"