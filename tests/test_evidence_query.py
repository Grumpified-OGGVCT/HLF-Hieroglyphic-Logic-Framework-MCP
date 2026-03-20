from __future__ import annotations

import json
from pathlib import Path


def _minimal_governed_review(source: str) -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "review_type": "weekly_artifact",
        "summary": f"No governed review contract was attached for {source}.",
        "severity": "info",
        "automation_status": "not_collected",
        "operator_gate_required": True,
        "recommended_triage_lane": None,
        "backend": {
            "provider": None,
            "access_mode": None,
            "model": None,
            "tier_index": None,
            "fallback_chain": [],
        },
        "pillar_assessments": [],
        "recommended_actions": [],
        "evidence_refs": [],
        "escalation_triggers": [],
        "review_metadata": {"source": source},
    }


def _write_history(metrics_dir: Path, artifacts: list[dict]) -> None:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    history_path = metrics_dir / "weekly_pipeline_history.jsonl"
    history_path.write_text(
        "\n".join(json.dumps(artifact) for artifact in artifacts) + "\n",
        encoding="utf-8",
    )


def test_load_verified_weekly_artifacts_filters_status_and_decision(tmp_path: Path) -> None:
    from hlf_mcp.weekly_artifacts import load_verified_weekly_artifacts

    metrics_dir = tmp_path / "metrics"
    _write_history(
        metrics_dir,
        [
            {
                "artifact_id": "weekly_a",
                "artifact_status": "advisory",
                "source": "local-scheduled",
                "decision_records": [],
                "verification": {"verified": True},
            },
            {
                "artifact_id": "weekly_b",
                "artifact_status": "promoted",
                "source": "weekly-code-quality",
                "decision_records": [{"decision": "promoted"}],
                "verification": {"verified": True},
            },
        ],
    )

    promoted = load_verified_weekly_artifacts(metrics_dir, status="promoted")
    assert [artifact["artifact_id"] for artifact in promoted] == ["weekly_b"]

    by_decision = load_verified_weekly_artifacts(metrics_dir, decision="promoted")
    assert [artifact["artifact_id"] for artifact in by_decision] == ["weekly_b"]


def test_evidence_query_list_and_show_commands(capsys, tmp_path: Path) -> None:
    from hlf_mcp import evidence_query

    metrics_dir = tmp_path / "metrics"
    artifact = {
        "artifact_id": "weekly_demo",
        "artifact_status": "promoted",
        "source": "weekly-code-quality",
        "generated_at": "2026-03-19T00:00:00+00:00",
        "decision_records": [{"decision": "promoted"}],
        "verification": {"verified": True},
        "distribution_contract": {"eligible_for_governed_distribution": True},
    }
    _write_history(metrics_dir, [artifact])

    exit_code = evidence_query.main(["--metrics-dir", str(metrics_dir), "list", "--status", "promoted"])
    assert exit_code == 0
    assert "weekly_demo" in capsys.readouterr().out

    exit_code = evidence_query.main(["--metrics-dir", str(metrics_dir), "show", "weekly_demo", "--json"])
    assert exit_code == 0
    assert '"artifact_id": "weekly_demo"' in capsys.readouterr().out


def test_evidence_query_summary_reports_distribution_eligibility(capsys, tmp_path: Path) -> None:
    from hlf_mcp import evidence_query

    metrics_dir = tmp_path / "metrics"
    _write_history(
        metrics_dir,
        [
            {
                "artifact_id": "weekly_1",
                "artifact_status": "advisory",
                "source": "local-scheduled",
                "decision_records": [],
                "verification": {"verified": True},
                "distribution_contract": {"eligible_for_governed_distribution": False},
            },
            {
                "artifact_id": "weekly_2",
                "artifact_status": "promoted",
                "source": "weekly-code-quality",
                "decision_records": [{"decision": "promoted"}],
                "verification": {"verified": True},
                "distribution_contract": {"eligible_for_governed_distribution": True},
            },
        ],
    )

    exit_code = evidence_query.main(["--metrics-dir", str(metrics_dir), "summary"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Artifacts: 2" in output
    assert "Distribution eligible: 1" in output


def test_evidence_query_decide_appends_decision_and_updates_latest(capsys, tmp_path: Path) -> None:
    from hlf_mcp import evidence_query

    metrics_dir = tmp_path / "metrics"
    artifact = {
        "artifact_id": "weekly_demo",
        "artifact_status": "advisory",
        "schema_version": "1.3",
        "generated_at": "2026-03-19T00:00:00+00:00",
        "source": "weekly-code-quality",
        "collector": {
            "name": "hlf_mcp.weekly_artifacts",
            "python": "3.12.0",
            "version": "2026-03-19",
        },
        "git": {"branch": "main", "commit_sha": "abc123"},
        "governance": {"manifest_present": True, "manifest_sha256": "abc", "drift": []},
        "server_surface": {"registered_tool_count": 35, "registered_resource_count": 9},
        "provenance": {
            "source_type": "workflow_weekly",
            "source": "weekly-code-quality",
            "collector": "hlf_mcp.weekly_artifacts",
            "collected_at": "2026-03-19T00:00:00+00:00",
            "workflow_run_url": "https://example.test/run/1",
            "branch": "main",
            "commit_sha": "abc123",
            "artifact_path": None,
            "confidence": 1.0,
        },
        "evidence_contract": {
            "intake_state": "advisory",
            "promotion_state": "requires_verification",
            "requires_operator_or_policy_gate": True,
            "confidence": 1.0,
            "manifest_sha256": "abc",
            "collector_version": "2026-03-19",
            "current_status": "advisory",
            "triage_lane": None,
            "decision_count": 0,
            "supersedes": None,
        },
        "decision_records": [],
        "distribution_contract": {
            "requires_source_compliance": True,
            "eligible_for_governed_distribution": False,
            "target_class": "source_compliant_forks_and_mcp_consumers",
            "governor_surface": "governance.update_governor.UpdateGovernor",
            "compliance_surface": "scripts.fork_compliance_check.run_compliance_check",
            "eligibility_reason": "awaiting_promotion_or_operator_gate",
        },
        "security_findings": {
            "collection_state": "summary_collected",
            "source": "workflow_payload.security_findings",
            "tool": "CodeQL",
            "codeql_category": "python-security",
            "alerts_available": True,
            "summary": {
                "total_alerts": 1,
                "open_alerts": 1,
                "closed_alerts": 0,
                "severity_counts": {"high": 1},
                "state_counts": {"open": 1},
            },
            "evidence_refs": ["github-api:code-scanning-alerts"],
        },
        "governed_review": _minimal_governed_review("weekly-code-quality"),
        "verification": {
            "verified": True,
            "checked_at": "2026-03-19T00:00:00+00:00",
            "errors": [],
            "warnings": [],
            "checked_schema_version": "1.3",
        },
    }

    _write_history(metrics_dir, [artifact])
    (metrics_dir / "weekly_pipeline_latest.json").write_text(
        json.dumps(artifact, indent=2), encoding="utf-8"
    )

    exit_code = evidence_query.main(
        [
            "--metrics-dir",
            str(metrics_dir),
            "decide",
            "weekly_demo",
            "--decision",
            "promoted",
            "--actor",
            "operator",
            "--rationale",
            "Approved for governed rollout",
            "--triage-lane",
            "current_batch",
            "--evidence-ref",
            "weekly_demo",
            "--policy-basis",
            "source_compliance_required",
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["artifact_status"] == "promoted"
    assert output["distribution_contract"]["eligible_for_governed_distribution"] is True
    assert output["decision_records"][-1]["decision"] == "promoted"

    latest_payload = json.loads((metrics_dir / "weekly_pipeline_latest.json").read_text(encoding="utf-8"))
    assert latest_payload["artifact_status"] == "promoted"

    history_lines = (metrics_dir / "weekly_pipeline_history.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 2