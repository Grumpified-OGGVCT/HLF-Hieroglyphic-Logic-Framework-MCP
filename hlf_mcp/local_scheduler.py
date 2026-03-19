from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hlf_mcp.test_runner import DEFAULT_METRICS_DIR


DEFAULT_LOCAL_SCHEDULER_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "interval_hours": 168,
    "run_tests": True,
    "toolkit_command": "status",
    "fail_on_test_failure": False,
}


def load_local_scheduler_settings(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or (Path.cwd() / "local_pipeline_scheduler.json")
    if not path.exists():
        return {**DEFAULT_LOCAL_SCHEDULER_SETTINGS, "config_path": str(path), "config_present": False}

    data = json.loads(path.read_text(encoding="utf-8"))
    scheduler_data = data.get("local_pipeline_scheduler", data)
    return {
        **DEFAULT_LOCAL_SCHEDULER_SETTINGS,
        **scheduler_data,
        "config_path": str(path),
        "config_present": True,
    }


def get_local_scheduler_status(
    *,
    metrics_dir: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    latest_path = effective_metrics_dir / "weekly_pipeline_latest.json"
    settings = load_local_scheduler_settings(config_path)
    latest_artifact = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None

    return {
        "enabled": bool(settings.get("enabled", False)),
        "interval_hours": int(settings.get("interval_hours", 168)),
        "run_tests": bool(settings.get("run_tests", True)),
        "toolkit_command": settings.get("toolkit_command"),
        "fail_on_test_failure": bool(settings.get("fail_on_test_failure", False)),
        "config_present": bool(settings.get("config_present", False)),
        "config_path": settings.get("config_path"),
        "last_artifact_path": str(latest_path),
        "last_run_at": latest_artifact.get("generated_at") if latest_artifact else None,
        "last_run_branch": latest_artifact.get("git", {}).get("branch") if latest_artifact else None,
    }