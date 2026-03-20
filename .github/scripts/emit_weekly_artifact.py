from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_METRICS_DIR: Path | None = None
build_weekly_artifact: Any | None = None
attach_weekly_artifact_verification: Any | None = None
validate_weekly_artifact: Any | None = None


def _load_artifact_dependencies() -> tuple[Path, Any, Any, Any]:
    global DEFAULT_METRICS_DIR, build_weekly_artifact, attach_weekly_artifact_verification, validate_weekly_artifact

    if (
        DEFAULT_METRICS_DIR is None
        or build_weekly_artifact is None
        or attach_weekly_artifact_verification is None
        or validate_weekly_artifact is None
    ):
        from hlf_mcp.test_runner import DEFAULT_METRICS_DIR as default_metrics_dir
        from hlf_mcp.weekly_artifacts import (
            attach_weekly_artifact_verification as verification_attacher,
            build_weekly_artifact as artifact_builder,
            validate_weekly_artifact as artifact_validator,
        )

        DEFAULT_METRICS_DIR = default_metrics_dir
        build_weekly_artifact = artifact_builder
        attach_weekly_artifact_verification = verification_attacher
        validate_weekly_artifact = artifact_validator

    return DEFAULT_METRICS_DIR, build_weekly_artifact, attach_weekly_artifact_verification, validate_weekly_artifact


def _workflow_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL")
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server_url and repository and run_id:
        return f"{server_url}/{repository}/actions/runs/{run_id}"
    return None


def _load_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _split_extra_entry(entry: str) -> tuple[Path, str]:
    direct_path = Path(entry)
    if direct_path.exists():
        return direct_path, direct_path.stem

    if ":" in entry:
        file_part, key = entry.rsplit(":", 1)
        candidate = Path(file_part)
        if candidate.exists():
            return candidate, key

    fallback = Path(entry)
    return fallback, fallback.stem


def _load_extra_payload(entries: list[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for entry in entries:
        path, key = _split_extra_entry(entry)
        payload[key] = _load_json_file(path)
    return payload


def build_parser() -> argparse.ArgumentParser:
    default_metrics_dir, _, _, _ = _load_artifact_dependencies()
    parser = argparse.ArgumentParser(
        description="Emit a normalized weekly artifact for GitHub workflows."
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metrics-dir", type=Path, default=default_metrics_dir)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--workflow-run-url", default=None)
    parser.add_argument("--suite-summary-file", type=Path, default=None)
    parser.add_argument("--extra-json", action="append", default=[])
    return parser


def main(argv: list[str] | None = None) -> int:
    _, build_weekly_artifact, attach_weekly_artifact_verification, validate_weekly_artifact = _load_artifact_dependencies()
    args = build_parser().parse_args(argv)
    suite_summary = _load_json_file(args.suite_summary_file)
    workflow_payload = _load_extra_payload(args.extra_json)

    artifact = build_weekly_artifact(
        repo_root=args.repo_root,
        metrics_dir=args.metrics_dir,
        source=args.source,
        workflow_run_url=args.workflow_run_url or _workflow_run_url(),
        latest_suite_summary=suite_summary,
        workflow_payload=workflow_payload or None,
    )
    args.output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    verified_payload = json.loads(args.output.read_text(encoding="utf-8"))
    verification_report = validate_weekly_artifact(verified_payload)
    if not verification_report.get("verified"):
        print(json.dumps({"artifact_path": str(args.output), "verification": verification_report}, indent=2), file=sys.stderr)
        return 2
    verified_payload = attach_weekly_artifact_verification(verified_payload, verification_report)
    args.output.write_text(json.dumps(verified_payload, indent=2), encoding="utf-8")
    print(json.dumps({"artifact_path": str(args.output), "source": artifact["source"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
