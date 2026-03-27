from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from hlf_mcp.local_scheduler import get_local_scheduler_status, load_local_scheduler_settings
from hlf_mcp.rag.memory import RAGMemory
from hlf_mcp.test_runner import DEFAULT_METRICS_DIR, run_pytest_suite
from hlf_mcp.weekly_artifacts import (
    attach_weekly_artifact_verification,
    build_hks_exemplar_from_weekly_artifact,
    build_weekly_artifact_memory_record,
    build_weekly_artifact,
    validate_weekly_artifact,
)


LATEST_ARTIFACT = "weekly_pipeline_latest.json"
HISTORY_ARTIFACT = "weekly_pipeline_history.jsonl"


def _write_artifacts(payload: dict[str, Any], metrics_dir: Path, output_path: Path | None) -> Path:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    target = output_path or (metrics_dir / LATEST_ARTIFACT)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    history_path = metrics_dir / HISTORY_ARTIFACT
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return target


def _write_verified_artifacts(payload: dict[str, Any], metrics_dir: Path, output_path: Path | None) -> tuple[dict[str, Any], Path]:
    metrics_dir.mkdir(parents=True, exist_ok=True)
    target = output_path or (metrics_dir / LATEST_ARTIFACT)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    serialized_payload = json.loads(target.read_text(encoding="utf-8"))
    verification_report = validate_weekly_artifact(serialized_payload)
    if not verification_report.get("verified"):
        raise ValueError(f"weekly artifact verification failed: {verification_report['errors']}")

    verified_payload = attach_weekly_artifact_verification(serialized_payload, verification_report)
    target.write_text(json.dumps(verified_payload, indent=2), encoding="utf-8")

    history_path = metrics_dir / HISTORY_ARTIFACT
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(verified_payload) + "\n")
    return verified_payload, target


def run_pipeline(
    *,
    repo_root: Path,
    metrics_dir: Path,
    run_tests: bool,
    toolkit_command: str | None,
    workflow_run_url: str | None,
    output_path: Path | None,
) -> tuple[int, dict[str, Any], Path]:
    suite_exit_code = 0
    if run_tests:
        suite_summary = run_pytest_suite(metrics_dir=metrics_dir, cwd=repo_root)
        suite_exit_code = suite_summary.exit_code

    target_path = output_path or (metrics_dir / LATEST_ARTIFACT)

    payload = build_weekly_artifact(
        repo_root=repo_root,
        metrics_dir=metrics_dir,
        source="local-scheduled",
        workflow_run_url=workflow_run_url,
        toolkit_command=toolkit_command,
    )
    payload["scheduled_pipeline"] = {
        "tests_triggered": run_tests,
        "toolkit_command": toolkit_command,
    }
    payload, written_path = _write_verified_artifacts(payload, metrics_dir, target_path)
    memory_db_path = os.environ.get("HLF_MEMORY_DB")
    weekly_memory_record = build_weekly_artifact_memory_record(payload, artifact_path=written_path)
    exemplar = build_hks_exemplar_from_weekly_artifact(payload, artifact_path=written_path)
    if not memory_db_path:
        payload["memory_capture"] = {
            "attempted": False,
            "stored": False,
            "reason": "HLF_MEMORY_DB not configured",
        }
    elif weekly_memory_record is None:
        payload["memory_capture"] = {
            "attempted": False,
            "stored": False,
            "reason": "verified_weekly_artifact_required",
        }
    else:
        weekly_store_result = RAGMemory(db_path=memory_db_path).store(
            weekly_memory_record["content"],
            topic=str(weekly_memory_record["topic"]),
            confidence=float(weekly_memory_record["confidence"]),
            provenance=str(weekly_memory_record["provenance"]),
            tags=list(weekly_memory_record["tags"]),
            entry_kind=str(weekly_memory_record["entry_kind"]),
            metadata=dict(weekly_memory_record["metadata"]),
        )
        payload["memory_capture"] = {
            "attempted": True,
            "stored": bool(weekly_store_result.get("stored")),
            "fact_id": weekly_store_result.get("id"),
            "sha256": weekly_store_result.get("sha256"),
            "db_path": memory_db_path,
        }

    if exemplar is None:
        payload["hks_capture"] = {"attempted": False, "stored": False, "reason": "latest_suite_summary_not_passed"}
    elif not memory_db_path:
        payload["hks_capture"] = {
            "attempted": False,
            "stored": False,
            "reason": "HLF_MEMORY_DB not configured",
            "topic": exemplar.topic,
            "domain": exemplar.domain,
            "solution_kind": exemplar.solution_kind,
        }
    else:
        store_result = RAGMemory(db_path=memory_db_path).store_exemplar(exemplar)
        payload["hks_capture"] = {
            "attempted": True,
            "stored": bool(store_result.get("stored")),
            "topic": exemplar.topic,
            "domain": exemplar.domain,
            "solution_kind": exemplar.solution_kind,
            "fact_id": store_result.get("id"),
            "sha256": store_result.get("sha256"),
            "duplicate_reason": store_result.get("duplicate_reason"),
            "db_path": memory_db_path,
        }
    return suite_exit_code, payload, written_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local scheduled HLF pipeline and persist a weekly artifact.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS_DIR)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--toolkit-command", default="status")
    parser.add_argument("--skip-toolkit", action="store_true")
    parser.add_argument("--workflow-run-url", default=None)
    parser.add_argument("--fail-on-test-failure", action="store_true")
    parser.add_argument("--use-config", action="store_true")
    parser.add_argument("--print-status", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.print_status:
        print(json.dumps(get_local_scheduler_status(metrics_dir=args.metrics_dir, config_path=args.config), indent=2))
        return 0

    if args.use_config:
        settings = load_local_scheduler_settings(args.config)
        if not settings.get("enabled", False):
            print(json.dumps({"skipped": True, "reason": "local_scheduler_disabled", "config_path": settings.get("config_path")}, indent=2))
            return 0
        if not args.skip_tests:
            args.skip_tests = not bool(settings.get("run_tests", True))
        if not args.skip_toolkit:
            configured_command = settings.get("toolkit_command")
            if configured_command:
                args.toolkit_command = str(configured_command)
            else:
                args.skip_toolkit = True
        if not args.fail_on_test_failure:
            args.fail_on_test_failure = bool(settings.get("fail_on_test_failure", False))

    suite_exit_code, payload, written_path = run_pipeline(
        repo_root=args.repo_root,
        metrics_dir=args.metrics_dir,
        run_tests=not args.skip_tests,
        toolkit_command=None if args.skip_toolkit else args.toolkit_command,
        workflow_run_url=args.workflow_run_url,
        output_path=args.output,
    )

    print(json.dumps({
        "artifact_path": str(written_path),
        "suite_passed": payload.get("latest_suite_summary", {}).get("passed") if payload.get("latest_suite_summary") else None,
        "registered_tool_count": payload["server_surface"]["registered_tool_count"],
        "registered_resource_count": payload["server_surface"]["registered_resource_count"],
        "governance_drift": payload["governance"]["drift"],
    }, indent=2))

    if args.fail_on_test_failure and suite_exit_code != 0:
        return suite_exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())