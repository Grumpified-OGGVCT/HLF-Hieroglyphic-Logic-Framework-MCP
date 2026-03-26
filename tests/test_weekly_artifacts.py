from __future__ import annotations

import json
from pathlib import Path


def _minimal_governed_review(source: str) -> dict[str, object]:
    from hlf_mcp.governed_review import default_governed_review

    return default_governed_review(source=source)


def test_collect_governance_manifest_snapshot_reports_clean_manifest(tmp_path: Path) -> None:
    from hlf_mcp.weekly_artifacts import collect_governance_manifest_snapshot

    repo_root = tmp_path / "repo"
    governance_dir = repo_root / "governance"
    governance_dir.mkdir(parents=True)
    target = governance_dir / "align_rules.json"
    target.write_text('{"rules": []}', encoding="utf-8")

    import hashlib

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (governance_dir / "MANIFEST.sha256").write_text(
        f"{digest} align_rules.json\n", encoding="utf-8"
    )

    snapshot = collect_governance_manifest_snapshot(repo_root)

    assert snapshot["manifest_present"] is True
    assert snapshot["entry_count"] == 1
    assert snapshot["drift"] == []


def test_build_weekly_artifact_uses_latest_suite_summary(monkeypatch, tmp_path: Path) -> None:
    from hlf_mcp import weekly_artifacts

    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    (metrics_dir / "pytest_last_run.json").write_text(
        json.dumps({"passed": True, "counts": {"passed": 8}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {"branch": "integrate-sovereign", "commit_sha": "abc123"},
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {"manifest_present": True, "drift": [], "entry_count": 6},
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 34,
            "registered_resource_count": 9,
            "exported_callable_count": 34,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "run_toolkit_command",
        lambda repo_root, command: {"attempted": True, "command": command, "exit_code": 0},
    )

    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=metrics_dir,
        source="local-scheduled",
        workflow_run_url="https://example.test/run/1",
        toolkit_command="status",
    )

    assert artifact["source"] == "local-scheduled"
    assert artifact["workflow_run_url"] == "https://example.test/run/1"
    assert artifact["latest_suite_summary"]["counts"]["passed"] == 8
    assert artifact["server_surface"]["registered_tool_count"] == 34
    assert artifact["toolkit"]["command"] == "status"
    assert artifact["schema_version"] == "1.3"
    assert artifact["collector"]["version"] == "2026-03-19"
    assert artifact["provenance"]["source_type"] == "scheduled_pipeline"
    assert artifact["evidence_contract"]["intake_state"] == "advisory"
    assert artifact["artifact_status"] == "advisory"
    assert artifact["distribution_contract"]["eligible_for_governed_distribution"] is False
    assert artifact["security_findings"]["collection_state"] == "not_collected"
    assert artifact["security_findings"]["tool"] == "CodeQL"
    assert artifact["governed_review"]["contract_version"] == "1.0"
    assert artifact["governed_review"]["change_class"] == "workflow_contract"
    assert artifact["governed_review"]["owner_persona"] == "steward"
    assert (
        artifact["governed_review"]["handoff_template_ref"]
        == "governance/templates/persona_review_handoff.md"
    )


def test_build_weekly_artifact_normalizes_security_findings_from_workflow_payload(
    monkeypatch, tmp_path: Path
) -> None:
    from hlf_mcp import weekly_artifacts

    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {
            "branch": "main",
            "commit_sha": "abc123",
            "commit_short_sha": "abc",
            "status_porcelain": [],
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {
            "manifest_present": True,
            "manifest_sha256": "deadbeef",
            "drift": [],
            "entry_count": 4,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 35,
            "registered_resource_count": 9,
            "exported_callable_count": 35,
        },
    )

    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=tmp_path,
        source="weekly-code-quality",
        latest_suite_summary={"passed": True, "counts": {"passed": 1}},
        workflow_payload={
            "code_quality": {"codeql_category": "python-security"},
            "security_findings": {
                "tool": "CodeQL",
                "collection_state": "summary_collected",
                "alerts_available": True,
                "summary": {
                    "total_alerts": 3,
                    "open_alerts": 2,
                    "closed_alerts": 1,
                    "severity_counts": {"high": 1, "medium": 2},
                    "state_counts": {"open": 2, "closed": 1},
                },
                "evidence_refs": ["sarif:codeql-python.sarif"],
            },
        },
    )

    security_findings = artifact["security_findings"]
    assert security_findings["collection_state"] == "summary_collected"
    assert security_findings["alerts_available"] is True
    assert security_findings["codeql_category"] == "python-security"
    assert security_findings["summary"]["total_alerts"] == 3
    assert security_findings["summary"]["severity_counts"]["high"] == 1
    assert security_findings["evidence_refs"] == ["sarif:codeql-python.sarif"]


def test_validate_weekly_artifact_accepts_built_payload(monkeypatch, tmp_path: Path) -> None:
    from hlf_mcp import weekly_artifacts

    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {
            "branch": "main",
            "commit_sha": "abc123",
            "commit_short_sha": "abc",
            "status_porcelain": [],
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {
            "manifest_present": True,
            "manifest_sha256": "deadbeef",
            "drift": [],
            "entry_count": 4,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 35,
            "registered_resource_count": 9,
            "exported_callable_count": 35,
        },
    )

    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=tmp_path,
        source="weekly-code-quality",
        workflow_run_url="https://example.test/run/99",
        latest_suite_summary={"passed": True, "counts": {"passed": 1}},
    )

    report = weekly_artifacts.validate_weekly_artifact(artifact)

    assert report["verified"] is True
    assert report["errors"] == []


def test_validate_weekly_artifact_rejects_cross_field_mismatch() -> None:
    from hlf_mcp.weekly_artifacts import validate_weekly_artifact

    artifact = {
        "artifact_id": "weekly_demo",
        "artifact_status": "triaged",
        "schema_version": "1.3",
        "generated_at": "2026-03-19T00:00:00+00:00",
        "source": "weekly-test-health",
        "collector": {
            "name": "hlf_mcp.weekly_artifacts",
            "python": "3.12.0",
            "version": "2026-03-19",
        },
        "git": {"branch": "main", "commit_sha": "abc123"},
        "governance": {"manifest_present": True, "manifest_sha256": "aaa", "drift": []},
        "server_surface": {"registered_tool_count": 35, "registered_resource_count": 9},
        "provenance": {
            "source_type": "workflow_weekly",
            "source": "weekly-test-health",
            "collector": "hlf_mcp.weekly_artifacts",
            "collected_at": "2026-03-19T00:00:00+00:00",
            "workflow_run_url": "https://example.test/run/1",
            "branch": "wrong-branch",
            "commit_sha": "abc123",
            "artifact_path": None,
            "confidence": 1.0,
        },
        "evidence_contract": {
            "intake_state": "advisory",
            "promotion_state": "requires_verification",
            "requires_operator_or_policy_gate": True,
            "confidence": 1.0,
            "manifest_sha256": "aaa",
            "collector_version": "2026-03-19",
            "current_status": "triaged",
            "triage_lane": "current_batch",
            "decision_count": 1,
            "supersedes": None,
        },
        "decision_records": [
            {
                "decision_id": "abc12345",
                "decision": "triaged",
                "status_after": "triaged",
                "decided_at": "2026-03-19T00:10:00+00:00",
                "actor": "operator",
                "rationale": "Move into current batch",
                "triage_lane": "current_batch",
                "evidence_refs": [],
                "policy_basis": [],
                "supersedes": None,
            }
        ],
        "distribution_contract": {
            "requires_source_compliance": True,
            "eligible_for_governed_distribution": False,
            "target_class": "source_compliant_forks_and_mcp_consumers",
            "governor_surface": "governance.update_governor.UpdateGovernor",
            "compliance_surface": "scripts.fork_compliance_check.run_compliance_check",
            "eligibility_reason": "awaiting_promotion_or_operator_gate",
        },
        "security_findings": {
            "collection_state": "metadata_only",
            "source": "workflow_payload.code_quality",
            "tool": "CodeQL",
            "codeql_category": "python-security",
            "alerts_available": False,
            "summary": {
                "total_alerts": None,
                "open_alerts": None,
                "closed_alerts": None,
                "severity_counts": {},
                "state_counts": {},
            },
            "evidence_refs": ["github-security-tab"],
        },
        "governed_review": _minimal_governed_review("weekly-test-health"),
    }

    report = validate_weekly_artifact(artifact)

    assert report["verified"] is False
    assert "provenance_branch_mismatch" in report["errors"]


def test_append_weekly_artifact_decision_promotes_distribution_eligibility(
    monkeypatch, tmp_path: Path
) -> None:
    from hlf_mcp import weekly_artifacts

    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {
            "branch": "main",
            "commit_sha": "abc123",
            "commit_short_sha": "abc",
            "status_porcelain": [],
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {
            "manifest_present": True,
            "manifest_sha256": "deadbeef",
            "drift": [],
            "entry_count": 4,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 35,
            "registered_resource_count": 9,
            "exported_callable_count": 35,
        },
    )

    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=tmp_path,
        source="weekly-code-quality",
        latest_suite_summary={"passed": True, "counts": {"passed": 1}},
    )
    weekly_artifacts.append_weekly_artifact_decision(
        artifact,
        decision="promoted",
        actor="operator",
        rationale="Approved for governed rollout",
        triage_lane="current_batch",
        evidence_refs=[artifact["artifact_id"]],
        policy_basis=["source_compliance_required"],
    )

    assert artifact["artifact_status"] == "promoted"
    assert artifact["evidence_contract"]["promotion_state"] == "approved_for_distribution"
    assert artifact["distribution_contract"]["eligible_for_governed_distribution"] is True
    assert artifact["decision_records"][0]["decision"] == "promoted"
    assert artifact["decision_records"][0]["persona_gate_status"]["owner_persona"]
    assert artifact["decision_records"][0]["persona_gate_status"]["pending_gate_count"] >= 1
    assert artifact["evidence_contract"]["persona_gate_status"]["required_gate_count"] >= 1


def test_record_weekly_artifact_decision_persists_verified_update(
    monkeypatch, tmp_path: Path
) -> None:
    from hlf_mcp import weekly_artifacts

    monkeypatch.setattr(
        weekly_artifacts,
        "collect_git_context",
        lambda repo_root: {
            "branch": "main",
            "commit_sha": "abc123",
            "commit_short_sha": "abc",
            "status_porcelain": [],
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_governance_manifest_snapshot",
        lambda repo_root: {
            "manifest_present": True,
            "manifest_sha256": "deadbeef",
            "drift": [],
            "entry_count": 4,
        },
    )
    monkeypatch.setattr(
        weekly_artifacts,
        "collect_server_surface",
        lambda: {
            "registered_tool_count": 35,
            "registered_resource_count": 9,
            "exported_callable_count": 35,
        },
    )

    metrics_dir = tmp_path / "metrics"
    artifact = weekly_artifacts.build_weekly_artifact(
        repo_root=tmp_path,
        metrics_dir=metrics_dir,
        source="weekly-code-quality",
        workflow_run_url="https://example.test/run/99",
        latest_suite_summary={"passed": True, "counts": {"passed": 1}},
    )
    weekly_artifacts.persist_weekly_artifact(artifact, metrics_dir)

    updated = weekly_artifacts.record_weekly_artifact_decision(
        artifact_id=artifact["artifact_id"],
        metrics_dir=metrics_dir,
        decision="triaged",
        actor="operator",
        rationale="Move to current batch",
        triage_lane="current_batch",
        evidence_refs=[artifact["artifact_id"]],
        policy_basis=["operator_review"],
    )

    assert updated["artifact_status"] == "triaged"
    assert updated["verification"]["verified"] is True
    assert updated["decision_records"][-1]["triage_lane"] == "current_batch"
    assert updated["decision_records"][-1]["persona_gate_status"]["owner_persona"]
    assert updated["evidence_contract"]["persona_gate_status"]["pending_gate_count"] >= 1


def test_build_hks_exemplar_from_weekly_artifact_returns_validated_entry(tmp_path: Path) -> None:
    from hlf_mcp.weekly_artifacts import build_hks_exemplar_from_weekly_artifact

    artifact = {
        "generated_at": "2026-03-18T00:00:00+00:00",
        "source": "local-scheduled",
        "workflow_run_url": "https://example.test/run/2",
        "git": {"branch": "integrate-sovereign", "commit_sha": "abc123"},
        "server_surface": {"registered_tool_count": 39, "registered_resource_count": 9},
        "governance": {"drift": []},
        "latest_suite_summary": {
            "passed": True,
            "exit_code": 0,
            "duration_ms": 101.0,
            "counts": {
                "passed": 12,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "xfailed": 0,
                "xpassed": 0,
            },
        },
        "scheduled_pipeline": {"toolkit_command": "status"},
    }

    exemplar = build_hks_exemplar_from_weekly_artifact(
        artifact, artifact_path=tmp_path / "weekly_pipeline_latest.json"
    )

    assert exemplar is not None
    assert exemplar.domain == "hlf-specific"
    assert exemplar.solution_kind == "weekly-pipeline"
    assert exemplar.tests[0].passed is True


def test_build_hks_exemplar_from_weekly_artifact_skips_failed_suite() -> None:
    from hlf_mcp.weekly_artifacts import build_hks_exemplar_from_weekly_artifact

    artifact = {"latest_suite_summary": {"passed": False}}

    assert build_hks_exemplar_from_weekly_artifact(artifact) is None


def test_local_scheduler_status_reads_config_and_latest_artifact(tmp_path: Path) -> None:
    from hlf_mcp.local_scheduler import get_local_scheduler_status

    config_path = tmp_path / "local_pipeline_scheduler.json"
    config_path.write_text(
        json.dumps(
            {
                "local_pipeline_scheduler": {
                    "enabled": True,
                    "interval_hours": 24,
                    "run_tests": False,
                    "toolkit_command": "security",
                }
            }
        ),
        encoding="utf-8",
    )

    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    (metrics_dir / "weekly_pipeline_latest.json").write_text(
        json.dumps({"generated_at": "2026-03-17T00:00:00+00:00", "git": {"branch": "main"}}),
        encoding="utf-8",
    )

    status = get_local_scheduler_status(metrics_dir=metrics_dir, config_path=config_path)

    assert status["enabled"] is True
    assert status["interval_hours"] == 24
    assert status["run_tests"] is False
    assert status["toolkit_command"] == "security"
    assert status["last_run_branch"] == "main"
