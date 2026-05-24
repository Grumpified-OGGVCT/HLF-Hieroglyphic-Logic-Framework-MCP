"""OVERWATCH Health MCP Tool — exposes sentinel health metrics to governance agents.

Provides ``sg_overwatch_health``, a standalone tool function that loads the
OverwatchSentinel from config, collects structured health metrics via
``OverwatchMetrics``, and returns a status-count report with any active alerts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hlf_mcp.governance.overwatch_metrics import OverwatchMetrics
from hlf_mcp.hlf.overwatch import OverwatchSentinel, build_overwatch_from_config


def _resolve_config_path(config_path: str | None = None) -> str:
    """Resolve the overwatch config path.

    If *config_path* is provided and non-empty, it is returned as-is.
    Otherwise, defaults to ``hlf_mcp/hlf/overwatch_config.json`` relative
    to the repository root.
    """
    if config_path:
        return config_path
    repo_root = Path(__file__).resolve().parent.parent
    return str(repo_root / "hlf" / "overwatch_config.json")


def _build_sentinel(config_path: str) -> OverwatchSentinel:
    """Build an OverwatchSentinel from a config file, falling back to an empty sentinel."""
    try:
        return build_overwatch_from_config(config_path)
    except FileNotFoundError:
        return OverwatchSentinel()


def sg_overwatch_health(config_path: str = "") -> dict[str, Any]:
    """Collect overwatch sentinel health metrics and return a structured report.

    Loads the OverwatchSentinel from the overwatch JSON config, runs a full
    scan, and returns health counts plus any active alerts.  Designed to be
    registered as an MCP tool via ``server_overwatch.py``.

    Args:
        config_path: Optional path to an overwatch JSON config file.
                     Defaults to ``hlf_mcp/hlf/overwatch_config.json``.

    Returns:
        A dict with keys:

        * ``status`` — ``"ok"`` or ``"error"``
        * ``timestamp`` — ISO 8601 UTC timestamp of the scan
        * ``target_count`` — total registered watchdog targets
        * ``healthy_count`` — targets in HEALTHY status
        * ``degraded_count`` — targets in DEGRADED status
        * ``unresponsive_count`` — targets in UNRESPONSIVE status
        * ``terminated_count`` — targets in TERMINATED status
        * ``total_alerts`` — unresponsive + terminated targets
        * ``alerts`` — list of target IDs currently in alerting status
        * ``target_details`` — per-target status, pid, restart info
    """
    effective_path = _resolve_config_path(config_path or None)
    sentinel = _build_sentinel(effective_path)
    metrics = OverwatchMetrics(sentinel)
    data = metrics.collect_metrics()

    alerts = [
        tid for tid, s in data["status_map"].items()
        if s in ("unresponsive", "terminated")
    ]

    return {
        "status": "ok",
        "timestamp": data["timestamp"],
        "target_count": data["target_count"],
        "healthy_count": data["healthy_count"],
        "degraded_count": data["degraded_count"],
        "unresponsive_count": data["unresponsive_count"],
        "terminated_count": data["terminated_count"],
        "total_alerts": data["total_alerts"],
        "alerts": alerts,
        "target_details": data["target_details"],
    }
