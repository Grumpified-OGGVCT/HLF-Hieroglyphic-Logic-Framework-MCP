from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_emit_weekly_artifact_writes_normalized_schema(monkeypatch, tmp_path: Path) -> None:
    module = _load_module(REPO_ROOT / ".github" / "scripts" / "emit_weekly_artifact.py", "emit_weekly_artifact")

    extra_path = tmp_path / "extra.json"
    extra_path.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    output_path = tmp_path / "artifact.json"

    monkeypatch.setattr(
        module,
        "build_weekly_artifact",
        lambda **kwargs: {
            "schema_version": "1.0",
            "source": kwargs["source"],
            "workflow_payload": kwargs["workflow_payload"],
        },
    )

    exit_code = module.main([
        "--source", "weekly-spec-sentinel",
        "--output", str(output_path),
        "--extra-json", f"{extra_path}:spec",
    ])

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["source"] == "weekly-spec-sentinel"
    assert payload["workflow_payload"]["spec"]["status"] == "ok"


def test_create_github_issue_skips_when_conflicting_pr_found(monkeypatch) -> None:
    module = _load_module(REPO_ROOT / ".github" / "scripts" / "create_github_issue.py", "create_github_issue")

    monkeypatch.setattr(
        module,
        "find_conflicting_pull_request",
        lambda **kwargs: {"number": 17, "html_url": "https://example.test/pr/17", "title": "Spec drift fix", "_conflict_reasons": ["labels=spec-drift"]},
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