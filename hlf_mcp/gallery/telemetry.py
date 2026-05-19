"""
HLF Gallery Telemetry — Live readiness telemetry for the operator dashboard.

Provides a TelemetryCollector that streams real-time readiness scores as ndjson,
consumable by the operator dashboard and CLI tools. Collects swarm health,
verification gate status, constitutional violations, and manifest audit data
on a configurable polling interval.

Architecture:
    TelemetryCollector
        ├── start()  → begins polling collectors
        ├── stop()   → stops polling, flushes buffers
        ├── snapshot() → one-shot readiness snapshot
        ├── stream()  → yields ndjson lines as they arrive
        └── history() → trend data buffer (last N snapshots)

Usage:
    from hlf_mcp.gallery.telemetry import TelemetryCollector

    collector = TelemetryCollector(interval=2.0)
    collector.start()
    snap = collector.snapshot()
    collector.stop()
"""

from __future__ import annotations

import dataclasses
import json
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Generator, Iterator


# ── Data Classes ──────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class TelemetrySnapshot:
    """A single readiness snapshot captured at a point in time."""

    snapshot_id: str
    timestamp: str
    swarm_health: dict[str, Any]
    verification_gate: dict[str, Any]
    constitutional_violations: dict[str, Any]
    manifest_audit: dict[str, Any]
    overall_readiness_pct: float
    alert_thresholds: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot to a JSON-compatible dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "swarm_health": self.swarm_health,
            "verification_gate": self.verification_gate,
            "constitutional_violations": self.constitutional_violations,
            "manifest_audit": self.manifest_audit,
            "overall_readiness_pct": self.overall_readiness_pct,
            "alert_thresholds": self.alert_thresholds,
        }

    def to_ndjson(self) -> str:
        """Serialize snapshot as a single ndjson line."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


# ── Collector Functions ───────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _generate_snapshot_id() -> str:
    """Generate a unique snapshot identifier."""
    return f"snap-{uuid.uuid4().hex[:12]}"


def _collect_swarm_health() -> dict[str, Any]:
    """Collect simulated swarm health metrics.

    In production, this would connect to a live SwarmObserver.
    """
    return {
        "source": "telemetry",
        "active_agents": 3,
        "queued_events": 7,
        "healthy_phases": 4,
        "degraded_phases": 0,
        "failed_phases": 0,
        "last_event_timestamp": _now_iso(),
        "uptime_seconds": 3600.0,
    }


def _collect_verification_gate() -> dict[str, Any]:
    """Collect simulated verification gate status.

    In production, this would query live gate decisions.
    """
    return {
        "source": "telemetry",
        "programs_verified": 12,
        "programs_passed": 8,
        "programs_warned": 3,
        "programs_blocked": 1,
        "pass_rate_pct": 66.7,
        "last_verification_timestamp": _now_iso(),
    }


def _collect_constitutional_violations() -> dict[str, Any]:
    """Collect simulated constitutional violation counts.

    In production, this would query the governance layer.
    """
    return {
        "source": "telemetry",
        "total_violations": 2,
        "high_severity": 1,
        "medium_severity": 1,
        "low_severity": 0,
        "blocked_actions": 1,
        "rules_breached": ["R-3", "R-2"],
        "last_violation_timestamp": _now_iso(),
    }


def _collect_manifest_audit() -> dict[str, Any]:
    """Collect simulated manifest audit metrics.

    In production, this would query the manifest registry.
    """
    return {
        "source": "telemetry",
        "total_deployments": 15,
        "approved_deployments": 12,
        "rejected_deployments": 3,
        "approval_rate_pct": 80.0,
        "tiers": {"hearth": 10, "sovereign": 3, "field": 2},
        "last_audit_timestamp": _now_iso(),
    }


def _compute_overall_readiness(snapshot_data: dict[str, Any]) -> float:
    """Compute overall readiness percentage from snapshot data.

    Weights each pillar equally; the dashboard can apply its own weighting.
    """
    ver = snapshot_data["verification_gate"]
    man = snapshot_data["manifest_audit"]
    const = snapshot_data["constitutional_violations"]
    swarm = snapshot_data["swarm_health"]

    ver_score = ver.get("pass_rate_pct", 50.0)
    man_score = man.get("approval_rate_pct", 50.0)

    # Violations reduce score
    high_violations = const.get("high_severity", 0)
    medium_violations = const.get("medium_severity", 0)
    violation_penalty = (high_violations * 15.0) + (medium_violations * 5.0)
    const_score = max(0.0, 100.0 - violation_penalty)

    # Swarm health: degrade if any failed phases
    failed = swarm.get("failed_phases", 0)
    degraded = swarm.get("degraded_phases", 0)
    swarm_score = max(0.0, 100.0 - (failed * 25.0) - (degraded * 10.0))

    overall = (ver_score + man_score + const_score + swarm_score) / 4.0
    return round(overall, 1)


def _compute_alert_thresholds(overall_readiness: float) -> dict[str, str]:
    """Compute alert status for each pillar based on readiness thresholds.

    Thresholds:
        - Below 50%: red (critical)
        - 50-65%: yellow (degraded)
        - Above 65%: green (healthy)
    """
    def _threshold_label(score: float) -> str:
        if score < 50.0:
            return "critical"
        elif score < 65.0:
            return "degraded"
        else:
            return "healthy"

    return {
        "overall": _threshold_label(overall_readiness),
    }


# ── TelemetryCollector ───────────────────────────────────────────────────────────


class TelemetryCollector:
    """Polls and streams live readiness telemetry.

    The collector periodically gathers swarm health, verification gate status,
    constitutional violations, and manifest audit data. Snapshots are buffered
    in a trend history deque and can be streamed as ndjson lines.

    Args:
        interval: Polling interval in seconds between snapshots.
        history_size: Maximum number of snapshots to retain in the trend buffer.
        collectors: Optional dict of custom collector callables keyed by name.
    """

    def __init__(
        self,
        interval: float = 2.0,
        history_size: int = 100,
        collectors: dict[str, Callable[[], dict[str, Any]]] | None = None,
    ) -> None:
        """Initialize the telemetry collector.

        Args:
            interval: Seconds between automatic snapshots when running.
            history_size: Max number of snapshots retained for trend analysis.
            collectors: Optional custom collector functions. Keys must be:
                'swarm_health', 'verification_gate', 'constitutional_violations',
                'manifest_audit'.
        """
        self._interval = interval
        self._history_size = history_size
        self._history: deque[TelemetrySnapshot] = deque(maxlen=history_size)
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._listeners: list[Callable[[TelemetrySnapshot], None]] = []

        # Wire collectors — use defaults if not provided
        self._collectors = collectors or {
            "swarm_health": _collect_swarm_health,
            "verification_gate": _collect_verification_gate,
            "constitutional_violations": _collect_constitutional_violations,
            "manifest_audit": _collect_manifest_audit,
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background polling thread.

        Begins collecting snapshots at the configured interval. Snapshots are
        appended to the trend history buffer and broadcast to listeners.

        Raises:
            RuntimeError: If the collector is already running.
        """
        if self._running:
            raise RuntimeError("TelemetryCollector is already running")
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread and wait for it to finish.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=self._interval * 2)
        self._thread = None

    def snapshot(self) -> TelemetrySnapshot:
        """Take a single one-shot readiness snapshot immediately.

        Does not require the collector to be running. The snapshot is appended
        to the trend history buffer.

        Returns:
            A new TelemetrySnapshot with current collector data.
        """
        snap = self._collect_once()
        with self._lock:
            self._history.append(snap)
        self._notify_listeners(snap)
        return snap

    def stream(self) -> Iterator[str]:
        """Yield ndjson lines from the history buffer as they arrive.

        Starts yielding existing history, then yields new snapshots as they
        are collected. This is a blocking generator — call stop() to interrupt.

        Yields:
            ndjson-encoded strings, one per snapshot.
        """
        # Yield existing history first
        with self._lock:
            last_seen = len(self._history)

        for snap in list(self._history):
            yield snap.to_ndjson() + "\n"

        # Listen for new snapshots
        queue: list[TelemetrySnapshot] = []
        event = threading.Event()

        def listener(snap: TelemetrySnapshot) -> None:
            queue.append(snap)
            event.set()

        self._listeners.append(listener)
        try:
            while self._running:
                event.wait(timeout=0.5)
                event.clear()
                while queue:
                    snap = queue.pop(0)
                    yield snap.to_ndjson() + "\n"
        finally:
            self._listeners.remove(listener)

    def history(self) -> list[TelemetrySnapshot]:
        """Return a copy of the trend history buffer.

        Returns:
            List of snapshots, oldest first.
        """
        with self._lock:
            return list(self._history)

    def on_snapshot(self, callback: Callable[[TelemetrySnapshot], None]) -> None:
        """Register a listener to be called on each new snapshot.

        Args:
            callback: Callable that receives each new TelemetrySnapshot.
        """
        self._listeners.append(callback)

    @property
    def is_running(self) -> bool:
        """Whether the collector's background thread is active."""
        return self._running

    # ── Internal ──────────────────────────────────────────────────────────────

    def _collect_once(self) -> TelemetrySnapshot:
        """Gather all collector data and assemble a snapshot."""
        data: dict[str, dict[str, Any]] = {}
        for name, collector_fn in self._collectors.items():
            try:
                data[name] = collector_fn()
            except Exception:
                data[name] = {"source": "error", "error": f"collector '{name}' failed"}

        snapshot_data = {
            "swarm_health": data.get("swarm_health", {}),
            "verification_gate": data.get("verification_gate", {}),
            "constitutional_violations": data.get("constitutional_violations", {}),
            "manifest_audit": data.get("manifest_audit", {}),
        }

        overall = _compute_overall_readiness(snapshot_data)
        alerts = _compute_alert_thresholds(overall)

        return TelemetrySnapshot(
            snapshot_id=_generate_snapshot_id(),
            timestamp=_now_iso(),
            swarm_health=snapshot_data["swarm_health"],
            verification_gate=snapshot_data["verification_gate"],
            constitutional_violations=snapshot_data["constitutional_violations"],
            manifest_audit=snapshot_data["manifest_audit"],
            overall_readiness_pct=overall,
            alert_thresholds=alerts,
        )

    def _poll_loop(self) -> None:
        """Background thread loop: collect snapshots at intervals."""
        while self._running:
            snap = self._collect_once()
            with self._lock:
                self._history.append(snap)
            self._notify_listeners(snap)
            # Sleep in small increments to respond to stop() promptly
            deadline = time.monotonic() + self._interval
            while self._running and time.monotonic() < deadline:
                time.sleep(0.1)

    def _notify_listeners(self, snap: TelemetrySnapshot) -> None:
        """Broadcast a snapshot to all registered listeners."""
        for listener in self._listeners[:]:
            try:
                listener(snap)
            except Exception:
                pass


# ── Convenience Factory ──────────────────────────────────────────────────────────


def create_default_collector(interval: float = 2.0) -> TelemetryCollector:
    """Create a TelemetryCollector with default collector functions.

    Args:
        interval: Polling interval in seconds.

    Returns:
        A ready-to-use TelemetryCollector instance.
    """
    return TelemetryCollector(interval=interval)
