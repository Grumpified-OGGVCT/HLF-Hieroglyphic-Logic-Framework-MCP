from __future__ import annotations

import json
from pathlib import Path


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
