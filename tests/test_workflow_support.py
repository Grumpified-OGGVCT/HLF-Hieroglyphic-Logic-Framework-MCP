from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _minimal_governed_review(source: str) -> dict[str, object]:
    from hlf_mcp.governed_review import default_governed_review

    return default_governed_review(source=source)


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_emit_weekly_artifact_writes_normalized_schema(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(
        REPO_ROOT / ".github" / "scripts" / "emit_weekly_artifact.py", "emit_weekly_artifact"
    )

    extra_path = tmp_path / "extra.json"
    extra_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    output_path = tmp_path / "artifact.json"

    monkeypatch.setattr(
        module,
        "build_weekly_artifact",
        lambda **kwargs: {
            "artifact_id": "weekly_workflow_demo",
            "artifact_status": "advisory",
            "schema_version": "1.3",
            "source": kwargs["source"],
            "generated_at": "2026-03-19T00:00:00+00:00",
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
                "source": kwargs["source"],
                "collector": "hlf_mcp.weekly_artifacts",
                "collected_at": "2026-03-19T00:00:00+00:00",
                "workflow_run_url": None,
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
                "collection_state": "not_collected",
                "source": None,
                "tool": "CodeQL",
                "codeql_category": None,
                "alerts_available": False,
                "summary": {
                    "total_alerts": None,
                    "open_alerts": None,
                    "closed_alerts": None,
                    "severity_counts": {},
                    "state_counts": {},
                },
                "evidence_refs": [],
            },
            "governed_review": _minimal_governed_review(kwargs["source"]),
            "workflow_payload": kwargs["workflow_payload"],
        },
    )
    monkeypatch.setattr(
        module,
        "validate_weekly_artifact",
        lambda payload: {
            "verified": True,
            "errors": [],
            "warnings": [],
            "checked_schema_version": "1.3",
        },
    )
    monkeypatch.setattr(
        module,
        "attach_weekly_artifact_verification",
        lambda payload, report: payload | {"verification": report},
    )

    exit_code = module.main(
        [
            "--source",
            "weekly-spec-sentinel",
            "--output",
            str(output_path),
            "--extra-json",
            f"{extra_path}:spec",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["source"] == "weekly-spec-sentinel"
    assert payload["workflow_payload"]["spec"]["status"] == "ok"
    assert payload["verification"]["verified"] is True


def test_create_github_issue_skips_when_conflicting_pr_found(monkeypatch) -> None:
    module = _load_module(
        REPO_ROOT / ".github" / "scripts" / "create_github_issue.py", "create_github_issue"
    )

    monkeypatch.setattr(
        module,
        "find_conflicting_pull_request",
        lambda **kwargs: {
            "number": 17,
            "html_url": "https://example.test/pr/17",
            "title": "Spec drift fix",
            "_conflict_reasons": ["labels=spec-drift"],
        },
    )

    result = module.create_or_update_issue(
        title="Spec drift",
        body="body",
        labels=["spec-drift"],
        conflict_labels=["spec-drift"],
    )

    assert result["skipped"] is True
    assert result["reason"] == "conflicting_open_pr"
    assert result["conflicting_pr_number"] == 17


def test_fetch_code_scanning_summary_writes_real_counts(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(
        REPO_ROOT / ".github" / "scripts" / "fetch_code_scanning_summary.py",
        "fetch_code_scanning_summary",
    )

    monkeypatch.setattr(
        module,
        "fetch_code_scanning_alerts",
        lambda tool_name="CodeQL": [
            {"state": "open", "rule": {"security_severity_level": "high"}},
            {"state": "dismissed", "rule": {"security_severity_level": "medium"}},
            {"state": "open", "rule": {"severity": "warning"}},
        ],
    )

    output_path = tmp_path / "security.json"
    exit_code = module.main(["--output", str(output_path)])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["collection_state"] == "summary_collected"
    assert payload["summary"]["total_alerts"] == 3
    assert payload["summary"]["open_alerts"] == 2
    assert payload["summary"]["closed_alerts"] == 1
    assert payload["summary"]["severity_counts"]["high"] == 1
    assert payload["summary"]["severity_counts"]["warning"] == 1


def test_fetch_code_scanning_summary_falls_back_when_api_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module(
        REPO_ROOT / ".github" / "scripts" / "fetch_code_scanning_summary.py",
        "fetch_code_scanning_summary",
    )

    def _boom(tool_name: str = "CodeQL") -> list[dict]:
        raise RuntimeError("api down")

    monkeypatch.setattr(module, "fetch_code_scanning_alerts", _boom)

    output_path = tmp_path / "security.json"
    exit_code = module.main(["--output", str(output_path)])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["collection_state"] == "metadata_only"
    assert payload["summary"]["total_alerts"] is None


def test_monitor_model_drift_normalizes_fenced_json_response() -> None:
    module = _load_module(REPO_ROOT / "scripts" / "monitor_model_drift.py", "monitor_model_drift")

    parsed, metadata = module._normalize_probe_response(
        """```json
        {"answer": "IMMUTABLE", "confidence": "0.8", "reasoning": "SET binds immutably."}
        ```"""
    )

    assert parsed is not None
    assert parsed["answer"] == "IMMUTABLE"
    assert parsed["confidence"] == 0.8
    assert parsed["reasoning"] == "SET binds immutably."
    assert metadata["normalization"] == "fenced_json"


def test_monitor_model_drift_normalizes_nested_fenced_json_response() -> None:
    module = _load_module(
        REPO_ROOT / "scripts" / "monitor_model_drift.py", "monitor_model_drift_nested"
    )

    candidate, source = module._extract_json_candidate(
        """```json
        {
            "answer": "MUTABLE",
            "confidence": "0.95",
            "reasoning": "Map supports updates {even with braces}.",
            "meta": {
                "a": 1,
                "b": {
                    "c": 2
                }
            }
        }
        ```"""
    )
    parsed, metadata = module._normalize_probe_response(
        """```json
        {
            "answer": "MUTABLE",
            "confidence": "0.95",
            "reasoning": "Map supports updates {even with braces}.",
            "meta": {
                "a": 1,
                "b": {
                    "c": 2
                }
            }
        }
        ```"""
    )

    assert candidate is not None
    assert '"meta": {' in candidate
    assert '"c": 2' in candidate
    assert source == "fenced_json"
    assert parsed is not None
    assert parsed["answer"] == "MUTABLE"
    assert parsed["confidence"] == 0.95
    assert parsed["reasoning"] == "Map supports updates {even with braces}."
    assert metadata["normalization"] == "fenced_json"


def test_run_drift_probes_disables_search_and_classifies_outcomes(monkeypatch) -> None:
    module = _load_module(
        REPO_ROOT / "scripts" / "monitor_model_drift.py", "monitor_model_drift_cases"
    )

    monkeypatch.setattr(module, "_CLIENT_AVAILABLE", True)
    monkeypatch.setattr(
        module,
        "PROBES",
        [
            {"id": "P1", "category": "grammar", "weight": 1.0, "prompt": "a", "expected": "RIGHT"},
            {"id": "P2", "category": "grammar", "weight": 1.0, "prompt": "b", "expected": "RIGHT"},
            {"id": "P3", "category": "grammar", "weight": 1.0, "prompt": "c", "expected": "RIGHT"},
            {"id": "P4", "category": "grammar", "weight": 1.0, "prompt": "d", "expected": "RIGHT"},
        ],
    )

    captured: dict[str, object] = {}

    class _FakeResult:
        def __init__(self, content: str, tool_calls: list[dict[str, object]] | None = None) -> None:
            self.content = content
            self.model_used = "fake-model"
            self.tier_index = 0
            self.thinking = ""
            self.tool_calls = tool_calls or []
            self.latency_s = 0.01

    class _FakeOrchestrator:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self._results = [
                _FakeResult('{"answer": "RIGHT", "confidence": 1.0, "reasoning": "ok"}'),
                _FakeResult('{"answer": "WRONG", "confidence": 1.0, "reasoning": "wrong"}'),
                _FakeResult("not json at all"),
                _FakeResult(
                    '{"answer": "RIGHT", "confidence": 1.0, "reasoning": "tool"}',
                    tool_calls=[{"name": "web_search"}],
                ),
            ]

        def complete(self, system: str, prompt: str):
            return self._results.pop(0)

    monkeypatch.setattr(module, "FallbackOrchestrator", _FakeOrchestrator)

    result = module.run_drift_probes(api_key="test-key")

    assert captured["web_search"] is False
    assert captured["use_streaming"] is False
    assert result["correct"] == 1
    assert result["total"] == 4
    assert result["driftScore"] == 0.75
    assert result["outcomeCounts"] == {
        "correct": 1,
        "semantic_wrong_answer": 1,
        "protocol_shape_failure": 1,
        "tool_call_behavior_failure": 1,
    }
    assert [probe["outcomeClass"] for probe in result["probes"]] == [
        "correct",
        "semantic_wrong_answer",
        "protocol_shape_failure",
        "tool_call_behavior_failure",
    ]
