from __future__ import annotations

import json
from pathlib import Path

import pytest


def _write_history(metrics_dir: Path, artifacts: list[dict]) -> None:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    history_path = metrics_dir / "weekly_pipeline_history.jsonl"
    history_path.write_text(
        "\n".join(json.dumps(artifact) for artifact in artifacts) + "\n",
        encoding="utf-8",
    )


def test_operator_cli_do_uses_packaged_helper(monkeypatch, capsys) -> None:
    from hlf_mcp import operator_cli

    monkeypatch.setattr(operator_cli, "build_server_context", object)
    monkeypatch.setattr(
        operator_cli,
        "run_hlf_do",
        lambda ctx, **kwargs: {
            "success": True,
            "tier": kwargs["tier"],
            "you_said": kwargs["intent"],
        },
    )

    exit_code = operator_cli.main(["do", "--intent", "summarize logs", "--tier", "forge", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is True
    assert payload["you_said"] == "summarize logs"


def test_operator_cli_test_summary_uses_shared_loader(monkeypatch, capsys) -> None:
    from hlf_mcp import operator_cli

    monkeypatch.setattr(
        operator_cli,
        "load_test_suite_summary",
        lambda metrics_dir, include_output=False: {
            "status": "ok",
            "summary": {"counts": {"passed": 7}},
        },
    )

    exit_code = operator_cli.main(["test-summary", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["counts"]["passed"] == 7


def test_operator_cli_weekly_evidence_summary_reports_counts(capsys, tmp_path: Path) -> None:
    from hlf_mcp import operator_cli

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

    exit_code = operator_cli.main(
        ["weekly-evidence-summary", "--metrics-dir", str(metrics_dir), "--json"]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["artifact_count"] == 2
    assert payload["distribution_eligible_count"] == 1


def test_operator_cli_provenance_summary_uses_server_context(monkeypatch, capsys) -> None:
    from hlf_mcp import operator_cli

    class MockContext:
        def summarize_provenance_contract(self, *, metrics_dir=None):
            return {
                "contract_version": "1.0",
                "summary": {"memory_fact_count": 3, "active_pointer_count": 2},
            }

    monkeypatch.setattr(operator_cli, "build_server_context", lambda: MockContext())

    exit_code = operator_cli.main(["provenance-summary", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["provenance_contract"]["summary"]["memory_fact_count"] == 3


def test_operator_cli_memory_govern_uses_shared_helper(monkeypatch, capsys) -> None:
    from hlf_mcp import operator_cli

    monkeypatch.setattr(operator_cli, "build_server_context", lambda: object())
    monkeypatch.setattr(
        operator_cli,
        "apply_memory_governance",
        lambda ctx, **kwargs: {
            "status": "ok",
            "action": kwargs["action"],
            "fact": {"id": kwargs["fact_id"], "governance_status": "revoked"},
            "operator_identity": {
                "operator_id": kwargs["operator_id"],
                "operator_display_name": kwargs["operator_display_name"],
                "operator_channel": kwargs["operator_channel"],
            },
        },
    )

    exit_code = operator_cli.main(
        [
            "memory-govern",
            "--action",
            "revoke",
            "--fact-id",
            "41",
            "--operator-summary",
            "Revoked via CLI",
            "--operator-id",
            "alice",
            "--operator-display-name",
            "Alice Example",
            "--operator-channel",
            "operator_cli.memory_govern",
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["action"] == "revoke"
    assert payload["fact"]["id"] == 41
    assert payload["operator_identity"]["operator_id"] == "alice"


def test_operator_cli_memory_govern_requires_fact_id_or_sha256(capsys) -> None:
    from hlf_mcp import operator_cli

    with pytest.raises(SystemExit) as excinfo:
        operator_cli.main(["memory-govern", "--action", "revoke"])

    assert excinfo.value.code == 2
    assert "memory-govern requires --fact-id or --sha256" in capsys.readouterr().err


def test_operator_cli_resource_uses_packaged_renderer(monkeypatch, capsys) -> None:
    from hlf_mcp import operator_cli

    monkeypatch.setattr(operator_cli, "build_server_context", object)
    monkeypatch.setattr(
        operator_cli,
        "render_resource_uri",
        lambda ctx, resource_uri: json.dumps({"status": "ok", "resource_uri": resource_uri}),
    )

    exit_code = operator_cli.main(["resource", "--uri", "hlf://status/formal_verifier", "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["resource_uri"] == "hlf://status/formal_verifier"
