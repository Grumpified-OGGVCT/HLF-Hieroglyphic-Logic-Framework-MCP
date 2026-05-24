"""OVERWATCH Metrics — bridge between OverwatchSentinel and the governance telemetry system.

Exposes overwatch sentinel health data as structured metrics that can be consumed
by the TelemetryCollector in ``hlf_mcp.gallery.telemetry``, making process health
queryable through the governance layer.
"""

from __future__ import annotations

import time
from typing import Any

from hlf_mcp.hlf.overwatch import OverwatchSentinel, WatchdogStatus


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class OverwatchMetrics:
    """Wraps an OverwatchSentinel to produce governance-telemetry-compatible metrics.

    Usage::

        sentinel = build_overwatch_from_config("overwatch_config.json")
        metrics = OverwatchMetrics(sentinel)
        data = metrics.collect_metrics()      # structured dict
        event = metrics.to_telemetry_event()  # TelemetryCollector-compatible
    """

    def __init__(self, sentinel: OverwatchSentinel) -> None:
        self._sentinel = sentinel

    # ── Metrics collection ──────────────────────────────────────────────────

    def collect_metrics(self) -> dict[str, Any]:
        """Run a scan across all registered targets and return structured metrics.

        Returns a dict with the following keys:

        * ``timestamp`` — ISO 8601 UTC timestamp of the scan
        * ``target_count`` — total number of registered watchdog targets
        * ``healthy_count`` — targets in HEALTHY status
        * ``degraded_count`` — targets in DEGRADED status
        * ``unresponsive_count`` — targets in UNRESPONSIVE status
        * ``terminated_count`` — targets in TERMINATED status
        * ``total_alerts`` — sum of unresponsive + terminated targets
        * ``status_map`` — per-target status dict (target_id → status string)
        * ``target_details`` — per-target detail dict with process_name, pid,
          restart_count, last_heartbeat
        """
        statuses = self._sentinel.scan()

        healthy = 0
        degraded = 0
        unresponsive = 0
        terminated = 0

        for s in statuses.values():
            if s == WatchdogStatus.HEALTHY:
                healthy += 1
            elif s == WatchdogStatus.DEGRADED:
                degraded += 1
            elif s == WatchdogStatus.UNRESPONSIVE:
                unresponsive += 1
            elif s == WatchdogStatus.TERMINATED:
                terminated += 1

        target_details: dict[str, dict[str, Any]] = {}
        for tid, target in self._sentinel.targets.items():
            target_details[tid] = {
                "process_name": target.process_name,
                "pid": target.pid,
                "status": target.status.value,
                "restart_count": target.restart_count,
                "max_restarts": target.max_restarts,
                "last_heartbeat": target.last_heartbeat,
            }

        return {
            "timestamp": _now_iso(),
            "target_count": len(statuses),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "unresponsive_count": unresponsive,
            "terminated_count": terminated,
            "total_alerts": unresponsive + terminated,
            "status_map": {tid: s.value for tid, s in statuses.items()},
            "target_details": target_details,
        }

    # ── Telemetry integration ───────────────────────────────────────────────

    def to_telemetry_event(self) -> dict[str, Any]:
        """Format current overwatch metrics as a TelemetryCollector-compatible event.

        The returned dict follows the pattern used by the built-in collector
        functions in ``hlf_mcp.gallery.telemetry`` (e.g. ``_collect_swarm_health``)
        and can be used directly as a custom collector or as input to
        ``TelemetryCollector.snapshot()``.

        Returns:
            Dict with ``source`` set to ``"overwatch"`` and ``overwatch_health``
            containing the full metrics payload.
        """
        metrics = self.collect_metrics()
        return {
            "source": "overwatch",
            "overwatch_health": metrics,
        }

    # ── Accessors ───────────────────────────────────────────────────────────

    @property
    def sentinel(self) -> OverwatchSentinel:
        """The wrapped OverwatchSentinel instance."""
        return self._sentinel
