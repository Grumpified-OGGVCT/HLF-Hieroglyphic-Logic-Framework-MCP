from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hlf_mcp.rag.memory import HKSProvenance, HKSTestEvidence, HKSValidatedExemplar
from hlf_mcp.test_runner import DEFAULT_METRICS_DIR, LATEST_SUMMARY_FILE


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _git_output(repo_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def collect_git_context(repo_root: Path) -> dict[str, Any]:
    return {
        "branch": _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "commit_sha": _git_output(repo_root, "rev-parse", "HEAD"),
        "commit_short_sha": _git_output(repo_root, "rev-parse", "--short", "HEAD"),
        "status_porcelain": (_git_output(repo_root, "status", "--short") or "").splitlines(),
    }


def _parse_manifest_entries(manifest_path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            expected[parts[1]] = parts[0]
    return expected


def collect_governance_manifest_snapshot(repo_root: Path) -> dict[str, Any]:
    governance_dir = repo_root / "governance"
    manifest_path = governance_dir / "MANIFEST.sha256"
    if not manifest_path.exists():
        return {
            "manifest_present": False,
            "manifest_path": str(manifest_path),
            "manifest_sha256": None,
            "entry_count": 0,
            "drift": ["MANIFEST.sha256 missing"],
        }

    manifest_entries = _parse_manifest_entries(manifest_path)
    drift: list[str] = []
    for relative_path, expected_hash in manifest_entries.items():
        target_path = governance_dir / relative_path
        if not target_path.exists():
            drift.append(f"{relative_path}: missing")
            continue
        actual_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            drift.append(f"{relative_path}: hash mismatch")

    return {
        "manifest_present": True,
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "entry_count": len(manifest_entries),
        "drift": drift,
    }


def collect_server_surface() -> dict[str, Any]:
    from hlf_mcp import server

    exported = sorted(
        name for name in dir(server) if name.startswith("hlf_") and callable(getattr(server, name))
    )
    instructions = server.mcp.instructions or ""
    return {
        "registered_tool_count": len(server.REGISTERED_TOOLS),
        "registered_resource_count": len(server.REGISTERED_RESOURCES),
        "exported_callable_count": len(exported),
        "registered_tools": sorted(server.REGISTERED_TOOLS),
        "registered_resources": sorted(server.REGISTERED_RESOURCES),
        "exported_callables": exported,
        "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
    }


def read_latest_suite_summary(metrics_dir: Path | None = None) -> dict[str, Any] | None:
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    summary_path = effective_metrics_dir / LATEST_SUMMARY_FILE
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def run_toolkit_command(repo_root: Path, command: str = "status") -> dict[str, Any]:
    toolkit_path = repo_root / "_toolkit.py"
    if not toolkit_path.exists():
        return {
            "attempted": False,
            "command": command,
            "reason": "_toolkit.py not present",
        }

    completed = subprocess.run(
        [sys.executable, str(toolkit_path), command],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "attempted": True,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def build_weekly_artifact(
    *,
    repo_root: Path,
    metrics_dir: Path | None = None,
    source: str,
    workflow_run_url: str | None = None,
    toolkit_command: str | None = None,
    latest_suite_summary: dict[str, Any] | None = None,
    workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    artifact = {
        "schema_version": "1.0",
        "generated_at": _utc_now(),
        "source": source,
        "workflow_run_url": workflow_run_url,
        "collector": {
            "name": "hlf_mcp.weekly_artifacts",
            "python": sys.version.split()[0],
        },
        "repo_root": str(repo_root),
        "metrics_dir": str(effective_metrics_dir),
        "git": collect_git_context(repo_root),
        "governance": collect_governance_manifest_snapshot(repo_root),
        "server_surface": collect_server_surface(),
        "latest_suite_summary": latest_suite_summary
        if latest_suite_summary is not None
        else read_latest_suite_summary(effective_metrics_dir),
    }
    if toolkit_command:
        artifact["toolkit"] = run_toolkit_command(repo_root, toolkit_command)
    if workflow_payload is not None:
        artifact["workflow_payload"] = workflow_payload
    return artifact


def build_hks_exemplar_from_weekly_artifact(
    artifact: dict[str, Any],
    *,
    artifact_path: Path | None = None,
) -> HKSValidatedExemplar | None:
    latest_suite_summary = artifact.get("latest_suite_summary") or {}
    if not latest_suite_summary or not latest_suite_summary.get("passed"):
        return None

    git = artifact.get("git") or {}
    scheduled_pipeline = artifact.get("scheduled_pipeline") or {}
    server_surface = artifact.get("server_surface") or {}
    governance = artifact.get("governance") or {}
    counts = latest_suite_summary.get("counts") or {}
    toolkit_command = scheduled_pipeline.get("toolkit_command")
    validated_solution = json.dumps(
        {
            "suite_passed": True,
            "counts": counts,
            "registered_tool_count": server_surface.get("registered_tool_count"),
            "registered_resource_count": server_surface.get("registered_resource_count"),
            "governance_drift": governance.get("drift", []),
            "toolkit_command": toolkit_command,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    summary = (
        f"Weekly pipeline passed with {counts.get('passed', 0)} passing tests, "
        f"{server_surface.get('registered_tool_count', 0)} registered tools, and "
        f"{len(governance.get('drift', []))} governance drift findings."
    )
    return HKSValidatedExemplar(
        problem="How to validate and persist the local HLF weekly pipeline state.",
        validated_solution=validated_solution,
        domain="hlf-specific",
        solution_kind="weekly-pipeline",
        provenance=HKSProvenance(
            source_type="scheduled_pipeline",
            source=str(artifact.get("source") or "local-scheduled"),
            collector="scripts.run_pipeline_scheduled",
            collected_at=str(artifact.get("generated_at") or _utc_now()),
            workflow_run_url=artifact.get("workflow_run_url"),
            branch=git.get("branch"),
            commit_sha=git.get("commit_sha"),
            artifact_path=str(artifact_path) if artifact_path else None,
            confidence=1.0,
        ),
        tests=[
            HKSTestEvidence(
                name="pytest_default_suite",
                passed=True,
                exit_code=int(latest_suite_summary.get("exit_code", 0)),
                counts=counts,
                details={
                    "duration_ms": latest_suite_summary.get("duration_ms"),
                    "toolkit_command": toolkit_command,
                },
            )
        ],
        topic="hlf_weekly_validated_runs",
        tags=["weekly", "pipeline", "validated", "hks"],
        summary=summary,
        confidence=1.0,
    )
