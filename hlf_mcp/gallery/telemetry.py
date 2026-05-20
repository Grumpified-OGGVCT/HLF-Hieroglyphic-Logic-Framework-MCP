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
import statistics
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Callable, Generator, Iterator


# ── Data Classes ──────────────────────────────────────────────────────────────────


@dataclasses.dataclass
class AlertFeedback:
    """A single feedback event recorded by an operator on a specific alert.

    Attributes:
        feedback_id: Unique identifier for this feedback event.
        alert_id: The alert this feedback applies to.
        feedback_type: One of 'ack', 'resolve', 'dismiss', 'escalate', 'snooze'.
        timestamp: ISO 8601 UTC timestamp of this feedback event.
        operator_id: Identifier of the operator who submitted the feedback.
        details: Optional free-form details about the feedback action.
        meta: Optional arbitrary metadata (e.g., snooze duration, escalation tier).
    """

    feedback_id: str
    alert_id: str
    feedback_type: str  # 'ack' | 'resolve' | 'dismiss' | 'escalate' | 'snooze'
    timestamp: str
    operator_id: str
    details: str = ""
    meta: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize feedback event to a JSON-compatible dictionary."""
        return {
            "feedback_id": self.feedback_id,
            "alert_id": self.alert_id,
            "feedback_type": self.feedback_type,
            "timestamp": self.timestamp,
            "operator_id": self.operator_id,
            "details": self.details,
            "meta": self.meta,
        }


@dataclasses.dataclass
class FeedbackStatistics:
    """Aggregated statistics computed from a FeedbackCollector's event history.

    Attributes:
        total_alerts: Total number of distinct alerts recorded.
        acknowledged: Number of alerts that received at least one ack.
        resolved: Number of alerts that received a resolve event.
        dismissed: Number of alerts dismissed (likely false positives).
        escalated: Number of alerts escalated beyond normal tier.
        snoozed: Number of alerts with snooze events.
        orphaned: Alerts with no follow-up after firing.
        resolution_rate_pct: Percentage of alerts resolved within SLA window.
        false_positive_rate_pct: Percentage of alerts dismissed without action.
        escalation_rate_pct: Percentage of alerts escalated.
        mttr_seconds: Mean time to resolve (rolling window average).
        mtta_seconds: Mean time to acknowledge.
        deduplication_rate_pct: Rate of duplicate alerts within the dedup window.
        snooze_repeat_rate_pct: Alerts snoozed more than once / total snoozed.
        signal_to_noise_ratio: Actionable alerts / total alerts.
        alert_volume_trend_slope: Linear regression slope on daily alert counts.
        operator_saturation_score: Composite 0-100 score from severity, volume, and fp rate.
        sla_window_seconds: The SLA window used for resolution rate computation.
    """

    total_alerts: int = 0
    acknowledged: int = 0
    resolved: int = 0
    dismissed: int = 0
    escalated: int = 0
    snoozed: int = 0
    orphaned: int = 0
    resolution_rate_pct: float = 0.0
    false_positive_rate_pct: float = 0.0
    escalation_rate_pct: float = 0.0
    mttr_seconds: float = 0.0
    mtta_seconds: float = 0.0
    deduplication_rate_pct: float = 0.0
    snooze_repeat_rate_pct: float = 0.0
    signal_to_noise_ratio: float = 0.0
    alert_volume_trend_slope: float = 0.0
    operator_saturation_score: float = 0.0
    sla_window_seconds: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize statistics to a JSON-compatible dictionary."""
        return dataclasses.asdict(self)


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


# ── FeedbackCollector ───────────────────────────────────────────────────────────


class FeedbackCollector:
    """Collects operator feedback on alerts and computes fatigue/loop metrics.

    Records alert lifecycle events (fire, acknowledge, resolve, dismiss, escalate,
    snooze) and computes operator feedback loop metrics including response time,
    resolution rate, false positive rate, signal-to-noise ratio, deduplication
    rate, alert volume trend, and operator saturation score.

    Thread-safe: all state mutations are protected by a lock.

    Args:
        dedup_window_seconds: Time window for detecting duplicate alerts.
        sla_window_seconds: SLA window for resolution rate computation.
        saturation_severity_weight: Weight of severity in saturation score (0-1).
        saturation_volume_weight: Weight of volume trend in saturation score (0-1).
        saturation_fp_weight: Weight of false-positive rate in saturation score (0-1).
    """

    def __init__(
        self,
        dedup_window_seconds: float = 60.0,
        sla_window_seconds: float = 300.0,
        saturation_severity_weight: float = 0.4,
        saturation_volume_weight: float = 0.3,
        saturation_fp_weight: float = 0.3,
    ) -> None:
        """Initialize the feedback collector.

        Args:
            dedup_window_seconds: Window for duplicate alert detection.
            sla_window_seconds: SLA window for resolution timing.
            saturation_severity_weight: Weight for severity component.
            saturation_volume_weight: Weight for volume component.
            saturation_fp_weight: Weight for false-positive component.
        """
        self._dedup_window = dedup_window_seconds
        self._sla_window = sla_window_seconds
        self._sat_sev_w = saturation_severity_weight
        self._sat_vol_w = saturation_volume_weight
        self._sat_fp_w = saturation_fp_weight

        self._lock = threading.Lock()
        # alert_id → list of AlertFeedback events (ordered by timestamp)
        self._alert_events: dict[str, list[AlertFeedback]] = defaultdict(list)
        # alert_id → fire timestamp (ISO) and severity
        self._alert_fires: dict[str, dict[str, Any]] = {}
        # Flat list of all feedback events for replay
        self._feedback_log: deque[AlertFeedback] = deque()
        # Listeners notified on each feedback event
        self._listeners: list[Callable[[AlertFeedback], None]] = []

    # ── Public API: Alert Lifecycle ─────────────────────────────────────────

    def record_alert(
        self,
        alert_id: str,
        alert_type: str = "generic",
        severity: int = 50,
        fingerprint: str | None = None,
    ) -> None:
        """Record a new alert firing.

        Args:
            alert_id: Unique identifier for this alert.
            alert_type: Category of the alert (e.g., 'readiness', 'violation').
            severity: Severity score 0-100 (higher = more severe).
            fingerprint: Optional dedup fingerprint. If None, uses alert_type.
        """
        ts = _now_iso()
        with self._lock:
            self._alert_fires[alert_id] = {
                "alert_type": alert_type,
                "severity": severity,
                "fingerprint": fingerprint or alert_type,
                "fire_timestamp": ts,
            }

    def acknowledge(self, alert_id: str, operator_id: str, details: str = "") -> AlertFeedback:
        """Record operator acknowledgement of an alert.

        Args:
            alert_id: The alert being acknowledged.
            operator_id: Identifier of the acknowledging operator.
            details: Optional acknowledgement notes.

        Returns:
            The recorded AlertFeedback event.
        """
        return self._record_feedback(alert_id, "ack", operator_id, details)

    def resolve(
        self,
        alert_id: str,
        operator_id: str,
        details: str = "",
        resolution_note: str = "",
    ) -> AlertFeedback:
        """Record operator resolution of an alert.

        Args:
            alert_id: The alert being resolved.
            operator_id: Identifier of the resolving operator.
            details: Optional resolution summary.
            resolution_note: Additional resolution context.

        Returns:
            The recorded AlertFeedback event.
        """
        return self._record_feedback(
            alert_id, "resolve", operator_id, details,
            meta={"resolution_note": resolution_note},
        )

    def dismiss(
        self,
        alert_id: str,
        operator_id: str,
        reason: str = "",
    ) -> AlertFeedback:
        """Dismiss an alert as a false positive or noise.

        Args:
            alert_id: The alert being dismissed.
            operator_id: Identifier of the dismissing operator.
            reason: Why the alert was dismissed.

        Returns:
            The recorded AlertFeedback event.
        """
        return self._record_feedback(
            alert_id, "dismiss", operator_id, reason,
            meta={"is_false_positive": True},
        )

    def escalate(
        self,
        alert_id: str,
        operator_id: str,
        target_tier: str = "sovereign",
        details: str = "",
    ) -> AlertFeedback:
        """Escalate an alert to a higher tier.

        Args:
            alert_id: The alert being escalated.
            operator_id: Identifier of the escalating operator.
            target_tier: The tier to escalate to (e.g., 'sovereign', 'field').
            details: Optional escalation notes.

        Returns:
            The recorded AlertFeedback event.
        """
        return self._record_feedback(
            alert_id, "escalate", operator_id, details,
            meta={"target_tier": target_tier},
        )

    def snooze(
        self,
        alert_id: str,
        operator_id: str,
        duration_seconds: float = 300.0,
        details: str = "",
    ) -> AlertFeedback:
        """Snooze an alert for a given duration.

        Args:
            alert_id: The alert being snoozed.
            operator_id: Identifier of the snoozing operator.
            duration_seconds: How long to snooze (default 5 min).
            details: Optional snooze notes.

        Returns:
            The recorded AlertFeedback event.
        """
        return self._record_feedback(
            alert_id, "snooze", operator_id, details,
            meta={"snooze_duration_seconds": duration_seconds},
        )

    # ── Public API: Statistics ──────────────────────────────────────────────

    def get_statistics(self) -> FeedbackStatistics:
        """Compute and return aggregated feedback loop metrics.

        Returns:
            A FeedbackStatistics dataclass with all computed metrics.
        """
        with self._lock:
            alerts = dict(self._alert_fires)
            events = dict(self._alert_events)

        stats = FeedbackStatistics()
        stats.total_alerts = len(alerts)
        stats.sla_window_seconds = self._sla_window

        if stats.total_alerts == 0:
            return stats

        # Count feedback types per alert
        for alert_id, evts in events.items():
            types = [e.feedback_type for e in evts]
            if "ack" in types:
                stats.acknowledged += 1
            if "resolve" in types:
                stats.resolved += 1
            if "dismiss" in types:
                stats.dismissed += 1
            if "escalate" in types:
                stats.escalated += 1
            if "snooze" in types:
                stats.snoozed += 1

        # Orphaned: alerts with no follow-up events
        stats.orphaned = sum(
            1 for aid in alerts if aid not in events or len(events[aid]) == 0
        )

        # Resolution rate: resolved within SLA / total resolved+open
        stats.resolution_rate_pct = self._compute_resolution_rate(alerts, events)
        stats.false_positive_rate_pct = self._compute_false_positive_rate()
        stats.escalation_rate_pct = self._compute_escalation_rate()

        # MTTR / MTTA
        stats.mttr_seconds = self._compute_mttr(alerts, events)
        stats.mtta_seconds = self._compute_mtta(alerts, events)

        # Deduplication
        stats.deduplication_rate_pct = self._compute_deduplication_rate(alerts)

        # Snooze repeat rate
        stats.snooze_repeat_rate_pct = self._compute_snooze_repeat_rate(events)

        # Signal-to-noise
        stats.signal_to_noise_ratio = self._compute_signal_to_noise(alerts, events)

        # Alert volume trend
        stats.alert_volume_trend_slope = self._compute_alert_volume_trend(alerts)

        # Operator saturation
        stats.operator_saturation_score = self._compute_operator_saturation(
            alerts,
            stats.false_positive_rate_pct,
            stats.alert_volume_trend_slope,
        )

        return stats

    def get_alert_events(self, alert_id: str) -> list[AlertFeedback]:
        """Return all feedback events for a specific alert, ordered by time.

        Args:
            alert_id: The alert to retrieve events for.

        Returns:
            List of AlertFeedback objects (may be empty).
        """
        with self._lock:
            return list(self._alert_events.get(alert_id, []))

    def get_feedback_log(self) -> list[AlertFeedback]:
        """Return a copy of the full feedback event log.

        Returns:
            List of all AlertFeedback events in insertion order.
        """
        with self._lock:
            return list(self._feedback_log)

    def on_feedback(self, callback: Callable[[AlertFeedback], None]) -> None:
        """Register a listener to be called on each feedback event.

        Args:
            callback: Callable that receives each new AlertFeedback.
        """
        self._listeners.append(callback)

    def clear(self) -> None:
        """Clear all alert fires, events, and feedback log."""
        with self._lock:
            self._alert_fires.clear()
            self._alert_events.clear()
            self._feedback_log.clear()

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _record_feedback(
        self,
        alert_id: str,
        feedback_type: str,
        operator_id: str,
        details: str = "",
        meta: dict[str, Any] | None = None,
    ) -> AlertFeedback:
        """Record a feedback event with thread safety."""
        fb = AlertFeedback(
            feedback_id=f"fb-{uuid.uuid4().hex[:12]}",
            alert_id=alert_id,
            feedback_type=feedback_type,
            timestamp=_now_iso(),
            operator_id=operator_id,
            details=details,
            meta=meta or {},
        )
        with self._lock:
            self._alert_events[alert_id].append(fb)
            self._feedback_log.append(fb)
        self._notify_feedback_listeners(fb)
        return fb

    def _notify_feedback_listeners(self, fb: AlertFeedback) -> None:
        """Broadcast feedback event to all registered listeners."""
        for listener in self._listeners[:]:
            try:
                listener(fb)
            except Exception:
                pass

    # ── Metric Computations ─────────────────────────────────────────────────

    @staticmethod
    def _parse_iso(ts: str) -> float:
        """Parse an ISO 8601 timestamp into epoch seconds (best effort)."""
        import calendar as _cal
        try:
            # Format: "2026-04-14T12:00:00Z"
            t = time.strptime(ts.replace("Z", "GMT"), "%Y-%m-%dT%H:%M:%S%Z")
            return _cal.timegm(t)
        except (ValueError, OverflowError):
            return 0.0

    def _compute_resolution_rate(
        self,
        alerts: dict[str, dict[str, Any]],
        events: dict[str, list[AlertFeedback]],
    ) -> float:
        """Compute percentage of alerts resolved within SLA window."""
        resolved_in_sla = 0
        total_resolved = 0
        for alert_id, evts in events.items():
            if alert_id not in alerts:
                continue
            fire_ts = self._parse_iso(alerts[alert_id]["fire_timestamp"])
            if fire_ts == 0:
                continue
            resolve_event = next((e for e in evts if e.feedback_type == "resolve"), None)
            if resolve_event:
                total_resolved += 1
                resolve_ts = self._parse_iso(resolve_event.timestamp)
                if resolve_ts > 0 and (resolve_ts - fire_ts) <= self._sla_window:
                    resolved_in_sla += 1
        if total_resolved == 0:
            return 0.0
        return round(resolved_in_sla / total_resolved * 100.0, 1)

    def _compute_false_positive_rate(self) -> float:
        """Compute percentage of alerts dismissed as false positives."""
        with self._lock:
            total = len(self._alert_fires)
            if total == 0:
                return 0.0
            dismissed = sum(
                1 for evts in self._alert_events.values()
                if any(e.feedback_type == "dismiss" for e in evts)
            )
        return round(dismissed / total * 100.0, 1)

    def _compute_escalation_rate(self) -> float:
        """Compute percentage of alerts escalated."""
        with self._lock:
            total = len(self._alert_fires)
            if total == 0:
                return 0.0
            escalated = sum(
                1 for evts in self._alert_events.values()
                if any(e.feedback_type == "escalate" for e in evts)
            )
        return round(escalated / total * 100.0, 1)

    def _compute_mttr(
        self,
        alerts: dict[str, dict[str, Any]],
        events: dict[str, list[AlertFeedback]],
    ) -> float:
        """Compute mean time to resolve across all resolved alerts."""
        resolve_times: list[float] = []
        for alert_id, evts in events.items():
            if alert_id not in alerts:
                continue
            fire_ts = self._parse_iso(alerts[alert_id]["fire_timestamp"])
            if fire_ts == 0:
                continue
            resolve_event = next((e for e in evts if e.feedback_type == "resolve"), None)
            if resolve_event:
                resolve_ts = self._parse_iso(resolve_event.timestamp)
                if resolve_ts > 0:
                    resolve_times.append(resolve_ts - fire_ts)
        if not resolve_times:
            return 0.0
        return round(statistics.mean(resolve_times), 1)

    def _compute_mtta(
        self,
        alerts: dict[str, dict[str, Any]],
        events: dict[str, list[AlertFeedback]],
    ) -> float:
        """Compute mean time to acknowledge across all acknowledged alerts."""
        ack_times: list[float] = []
        for alert_id, evts in events.items():
            if alert_id not in alerts:
                continue
            fire_ts = self._parse_iso(alerts[alert_id]["fire_timestamp"])
            if fire_ts == 0:
                continue
            ack_event = next((e for e in evts if e.feedback_type == "ack"), None)
            if ack_event:
                ack_ts = self._parse_iso(ack_event.timestamp)
                if ack_ts > 0:
                    ack_times.append(ack_ts - fire_ts)
        if not ack_times:
            return 0.0
        return round(statistics.mean(ack_times), 1)

    def _compute_deduplication_rate(
        self,
        alerts: dict[str, dict[str, Any]],
    ) -> float:
        """Compute percentage of alerts that are likely duplicates.

        Two alerts with the same fingerprint within dedup_window_seconds are
        considered duplicates.
        """
        if len(alerts) < 2:
            return 0.0
        # Group by fingerprint
        by_fingerprint: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for alert_id, info in alerts.items():
            fp = info.get("fingerprint", alert_id)
            ts = self._parse_iso(info["fire_timestamp"])
            if ts > 0:
                by_fingerprint[fp].append((alert_id, ts))

        duplicate_count = 0
        for fp, entries in by_fingerprint.items():
            entries.sort(key=lambda x: x[1])
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    if entries[j][1] - entries[i][1] <= self._dedup_window:
                        duplicate_count += 1
                        break  # count each alert at most once as duplicate

        total = len(alerts)
        return round(duplicate_count / total * 100.0, 1)

    def _compute_snooze_repeat_rate(
        self,
        events: dict[str, list[AlertFeedback]],
    ) -> float:
        """Compute percentage of snoozed alerts that were snoozed >1 time."""
        total_snoozed = 0
        repeat_snoozed = 0
        for evts in events.values():
            snooze_count = sum(1 for e in evts if e.feedback_type == "snooze")
            if snooze_count >= 1:
                total_snoozed += 1
            if snooze_count >= 2:
                repeat_snoozed += 1
        if total_snoozed == 0:
            return 0.0
        return round(repeat_snoozed / total_snoozed * 100.0, 1)

    def _compute_signal_to_noise(
        self,
        alerts: dict[str, dict[str, Any]],
        events: dict[str, list[AlertFeedback]],
    ) -> float:
        """Compute signal-to-noise ratio: actionable alerts / total alerts.

        An alert is 'actionable' if it was resolved (not dismissed) and was
        acknowledged at least once.
        """
        if not alerts:
            return 0.0
        actionable = 0
        for alert_id in alerts:
            evts = events.get(alert_id, [])
            types = {e.feedback_type for e in evts}
            # Actionable: resolved and not dismissed
            if "resolve" in types and "dismiss" not in types:
                actionable += 1
        return round(actionable / len(alerts), 3)

    def _compute_alert_volume_trend(
        self,
        alerts: dict[str, dict[str, Any]],
    ) -> float:
        """Compute linear regression slope on daily alert counts.

        Returns the slope (alerts per day). Positive = growing volume.
        """
        if len(alerts) < 2:
            return 0.0

        # Bucket alerts by day
        day_counts: dict[str, int] = defaultdict(int)
        for info in alerts.values():
            ts = info["fire_timestamp"]
            day = ts[:10]  # "YYYY-MM-DD"
            day_counts[day] += 1

        if len(day_counts) < 2:
            return 0.0

        # Sort days and assign x indices
        sorted_days = sorted(day_counts.keys())
        xs = list(range(len(sorted_days)))
        ys = [day_counts[d] for d in sorted_days]

        # Linear regression slope
        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return round(slope, 3)

    def _compute_operator_saturation(
        self,
        alerts: dict[str, dict[str, Any]],
        false_positive_rate: float,
        volume_trend_slope: float,
    ) -> float:
        """Compute composite operator saturation score (0-100).

        Higher score = more saturated (worse). Scoring components:
          - Severity score: mean severity across all alerts (scaled to 0-100)
          - Volume trend: normalized slope contribution
          - False positive rate: directly used

        All clamped to 0-100 range.
        """
        if not alerts:
            return 0.0

        # Mean severity
        severities = [info.get("severity", 50) for info in alerts.values()]
        mean_severity = statistics.mean(severities)

        # Volume trend contribution: map slope to 0-100
        # slope of 5 alerts/day → 100, slope of 0 → 0
        vol_component = min(100.0, max(0.0, volume_trend_slope * 20.0))

        # False positive contribution: fp rate IS the component
        fp_component = min(100.0, false_positive_rate)

        score = (
            self._sat_sev_w * mean_severity
            + self._sat_vol_w * vol_component
            + self._sat_fp_w * fp_component
        )
        return round(min(100.0, max(0.0, score)), 1)


# ── Convenience Factory ──────────────────────────────────────────────────────────


def create_default_collector(interval: float = 2.0) -> TelemetryCollector:
    """Create a TelemetryCollector with default collector functions.

    Args:
        interval: Polling interval in seconds.

    Returns:
        A ready-to-use TelemetryCollector instance.
    """
    return TelemetryCollector(interval=interval)


def create_default_feedback_collector(
    dedup_window_seconds: float = 60.0,
    sla_window_seconds: float = 300.0,
) -> FeedbackCollector:
    """Create a FeedbackCollector with default settings.

    Args:
        dedup_window_seconds: Window for duplicate alert detection.
        sla_window_seconds: SLA window for resolution timing.

    Returns:
        A ready-to-use FeedbackCollector instance.
    """
    return FeedbackCollector(
        dedup_window_seconds=dedup_window_seconds,
        sla_window_seconds=sla_window_seconds,
    )
