"""
ModelTron — Performance feedback loop for model routing decisions.

Tracks model performance metrics (latency, error rate, token throughput) and
generates routing feedback hints that the model gateway can use to re-route
requests away from degraded models.

Architecture:
    PerformanceTracker → sliding-window metrics per model+task
    RoutingFeedback    → generates hints: "model X slow for task Y, prefer Z"
    FeedbackLoop       → integrates with routing/load_balancer to adjust weights

Window-based metrics: tracks last N requests and time-based sliding window.
Thread-safe with lock.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Default window size (number of requests)
DEFAULT_WINDOW_SIZE = 100
# Default time window (seconds)
DEFAULT_TIME_WINDOW = 300.0  # 5 minutes
# Degradation thresholds
DEFAULT_LATENCY_DEGRADED_MS = 5000.0  # p95 > 5s → degraded
DEFAULT_ERROR_RATE_DEGRADED = 0.10    # > 10% errors → degraded
DEFAULT_MIN_SAMPLES_FOR_HINT = 5       # need at least 5 samples for reliable hint


# ── PerformanceRecord Dataclass ────────────────────────────────────────────────


@dataclass
class PerformanceRecord:
    """A single performance data point for a model+task combination."""

    model_name: str
    task_type: str
    latency_ms: float
    tokens_per_second: float = 0.0
    error: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "task_type": self.task_type,
            "latency_ms": self.latency_ms,
            "tokens_per_second": self.tokens_per_second,
            "error": self.error,
            "timestamp": self.timestamp,
        }


# ── AggregatedMetrics ──────────────────────────────────────────────────────────


@dataclass
class AggregatedMetrics:
    """Aggregated performance metrics for a model+task combination."""

    model_name: str
    task_type: str
    sample_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0

    # Latency (ms)
    latency_avg: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_min: float = 0.0
    latency_max: float = 0.0

    # Throughput
    tokens_per_second_avg: float = 0.0

    # Time range
    first_seen: float = 0.0
    last_updated: float = 0.0

    @property
    def success_count(self) -> int:
        return self.sample_count - self.error_count

    @property
    def is_degraded(self) -> bool:
        """A model is degraded if latency or error rate exceed thresholds."""
        if self.sample_count < DEFAULT_MIN_SAMPLES_FOR_HINT:
            return False
        if self.error_rate > DEFAULT_ERROR_RATE_DEGRADED:
            return True
        if self.latency_p95 > DEFAULT_LATENCY_DEGRADED_MS:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "task_type": self.task_type,
            "sample_count": self.sample_count,
            "error_count": self.error_count,
            "error_rate": self.error_rate,
            "latency_avg": self.latency_avg,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "latency_p99": self.latency_p99,
            "latency_min": self.latency_min,
            "latency_max": self.latency_max,
            "tokens_per_second_avg": self.tokens_per_second_avg,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
            "is_degraded": self.is_degraded,
        }


# ── PerformanceTracker ─────────────────────────────────────────────────────────


class PerformanceTracker:
    """Tracks model performance metrics using sliding windows.

    Maintains both count-based (last N requests) and time-based (last T
    seconds) sliding windows per model+task combination.

    Thread-safe via internal lock.
    """

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        time_window: float = DEFAULT_TIME_WINDOW,
    ) -> None:
        self._window_size = window_size
        self._time_window = time_window
        self._lock = threading.Lock()
        # model_name:task_type → deque of PerformanceRecord
        self._records: dict[str, deque[PerformanceRecord]] = {}

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def time_window(self) -> float:
        return self._time_window

    def _key(self, model_name: str, task_type: str) -> str:
        return f"{model_name}:{task_type}"

    def record(
        self,
        model_name: str,
        task_type: str,
        latency_ms: float,
        tokens_per_second: float = 0.0,
        error: bool = False,
    ) -> None:
        """Record a single performance data point.

        Args:
            model_name: The model used (e.g., "kimi-k2.6:cloud").
            task_type: The task category (e.g., "chat", "code", "reasoning").
            latency_ms: Request latency in milliseconds.
            tokens_per_second: Token throughput (tokens/sec).
            error: Whether the request resulted in an error.
        """
        record = PerformanceRecord(
            model_name=model_name,
            task_type=task_type,
            latency_ms=latency_ms,
            tokens_per_second=tokens_per_second,
            error=error,
            timestamp=time.time(),
        )
        key = self._key(model_name, task_type)
        with self._lock:
            if key not in self._records:
                self._records[key] = deque(maxlen=self._window_size)
            self._records[key].append(record)

    def get_metrics(
        self, model_name: str, task_type: str
    ) -> AggregatedMetrics:
        """Get aggregated performance metrics for a model+task.

        Uses the time-window to only consider recent samples.

        Args:
            model_name: The model name.
            task_type: The task type.

        Returns:
            AggregatedMetrics with computed statistics.
        """
        key = self._key(model_name, task_type)
        with self._lock:
            records = self._records.get(key, deque())

        # Filter to time window
        cutoff = time.time() - self._time_window
        windowed = [r for r in records if r.timestamp >= cutoff]

        return self._compute_metrics(model_name, task_type, windowed)

    def get_all_metrics(self) -> dict[str, AggregatedMetrics]:
        """Get aggregated metrics for all model+task combinations.

        Returns:
            Dict mapping "model:task" → AggregatedMetrics.
        """
        cutoff = time.time() - self._time_window
        result: dict[str, AggregatedMetrics] = {}
        with self._lock:
            for key, records in self._records.items():
                windowed = [r for r in records if r.timestamp >= cutoff]
                if windowed:
                    parts = key.split(":", 1)
                    model_name = parts[0]
                    task_type = parts[1] if len(parts) > 1 else "default"
                    result[key] = self._compute_metrics(
                        model_name, task_type, windowed
                    )
        return result

    @staticmethod
    def _compute_metrics(
        model_name: str,
        task_type: str,
        records: list[PerformanceRecord],
    ) -> AggregatedMetrics:
        """Compute aggregated statistics from a list of records."""
        if not records:
            return AggregatedMetrics(
                model_name=model_name,
                task_type=task_type,
            )

        latencies = sorted([r.latency_ms for r in records])
        errors = sum(1 for r in records if r.error)
        tps_values = [r.tokens_per_second for r in records if r.tokens_per_second > 0]
        timestamps = [r.timestamp for r in records]

        n = len(latencies)

        def percentile(sorted_vals: list[float], p: float) -> float:
            if not sorted_vals:
                return 0.0
            idx = int(p * (n - 1) / 100.0)
            # Linear interpolation for non-integer index
            k = p * (n - 1) / 100.0
            f = k - idx
            if idx + 1 < n:
                return sorted_vals[idx] * (1 - f) + sorted_vals[idx + 1] * f
            return sorted_vals[idx]

        return AggregatedMetrics(
            model_name=model_name,
            task_type=task_type,
            sample_count=n,
            error_count=errors,
            error_rate=errors / n if n > 0 else 0.0,
            latency_avg=sum(latencies) / n,
            latency_p50=percentile(latencies, 50.0),
            latency_p95=percentile(latencies, 95.0),
            latency_p99=percentile(latencies, 99.0),
            latency_min=latencies[0],
            latency_max=latencies[-1],
            tokens_per_second_avg=sum(tps_values) / len(tps_values) if tps_values else 0.0,
            first_seen=min(timestamps),
            last_updated=max(timestamps),
        )

    def clear(self, model_name: str | None = None, task_type: str | None = None) -> None:
        """Clear performance records.

        Args:
            model_name: If provided, clear only records for this model.
            task_type: If provided, clear only records for this task type.
        """
        with self._lock:
            if model_name is None and task_type is None:
                self._records.clear()
            else:
                to_remove = []
                for key in self._records:
                    parts = key.split(":", 1)
                    key_model = parts[0]
                    key_task = parts[1] if len(parts) > 1 else "default"
                    if model_name and key_model != model_name:
                        continue
                    if task_type and key_task != task_type:
                        continue
                    to_remove.append(key)
                for key in to_remove:
                    del self._records[key]

    def status(self) -> dict[str, Any]:
        """Return tracker status summary."""
        with self._lock:
            total_records = sum(len(v) for v in self._records.values())
            return {
                "tracked_combinations": len(self._records),
                "total_records": total_records,
                "window_size": self._window_size,
                "time_window": self._time_window,
            }


# ── RoutingHint ────────────────────────────────────────────────────────────────


@dataclass
class RoutingHint:
    """A routing recommendation based on performance data."""

    task_type: str
    degraded_models: list[str] = field(default_factory=list)
    preferred_models: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "degraded_models": self.degraded_models,
            "preferred_models": self.preferred_models,
            "reason": self.reason,
            "confidence": self.confidence,
        }


# ── RoutingFeedback ────────────────────────────────────────────────────────────


class RoutingFeedback:
    """Generates routing hints based on performance data from PerformanceTracker.

    Analyses aggregated metrics for a given task type and produces
    recommendations like "model X is slow for task Y, prefer model Z".
    """

    def __init__(
        self,
        tracker: PerformanceTracker,
        latency_degraded_ms: float = DEFAULT_LATENCY_DEGRADED_MS,
        error_rate_degraded: float = DEFAULT_ERROR_RATE_DEGRADED,
        min_samples: int = DEFAULT_MIN_SAMPLES_FOR_HINT,
    ) -> None:
        self._tracker = tracker
        self._latency_degraded_ms = latency_degraded_ms
        self._error_rate_degraded = error_rate_degraded
        self._min_samples = min_samples

    def get_hints(self, task_type: str) -> list[RoutingHint]:
        """Generate routing hints for a specific task type.

        Args:
            task_type: The task category to get hints for.

        Returns:
            List of RoutingHint objects with degradation and preference info.
        """
        all_metrics = self._tracker.get_all_metrics()

        # Filter to this task type
        task_metrics: dict[str, AggregatedMetrics] = {}
        for key, metrics in all_metrics.items():
            if metrics.task_type == task_type:
                task_metrics[metrics.model_name] = metrics

        if not task_metrics:
            return []

        degraded: list[str] = []
        healthy: list[tuple[str, AggregatedMetrics]] = []

        for model_name, metrics in task_metrics.items():
            if metrics.sample_count < self._min_samples:
                continue  # not enough data
            is_degraded = (
                metrics.error_rate > self._error_rate_degraded
                or metrics.latency_p95 > self._latency_degraded_ms
            )
            if is_degraded:
                degraded.append(model_name)
            else:
                healthy.append((model_name, metrics))

        hints: list[RoutingHint] = []

        if degraded and healthy:
            # Sort healthy by latency (fastest first)
            healthy_sorted = sorted(healthy, key=lambda x: x[1].latency_avg)
            preferred = [name for name, _ in healthy_sorted[:3]]

            # Build reason
            degraded_details = []
            for name in degraded:
                m = task_metrics[name]
                parts = []
                if m.error_rate > self._error_rate_degraded:
                    parts.append(f"{m.error_rate:.1%} errors")
                if m.latency_p95 > self._latency_degraded_ms:
                    parts.append(f"p95={m.latency_p95:.0f}ms")
                degraded_details.append(f"{name} ({', '.join(parts)})")

            reason = (
                f"Degraded: {'; '.join(degraded_details)}. "
                f"Prefer: {', '.join(preferred)}"
            )

            # Confidence based on sample counts
            total_samples = sum(
                task_metrics[n].sample_count for n in degraded + preferred
            )
            confidence = min(0.95, 0.5 + total_samples / 50.0)

            hints.append(
                RoutingHint(
                    task_type=task_type,
                    degraded_models=degraded,
                    preferred_models=preferred,
                    reason=reason,
                    confidence=confidence,
                )
            )
        elif degraded and not healthy:
            # All models degraded — report which is least degraded
            least_degraded_name = min(
                degraded,
                key=lambda n: (
                    task_metrics[n].error_rate,
                    task_metrics[n].latency_p95,
                ),
            )
            hints.append(
                RoutingHint(
                    task_type=task_type,
                    degraded_models=degraded,
                    preferred_models=[least_degraded_name],
                    reason=(
                        f"All models degraded for '{task_type}'. "
                        f"Least degraded: {least_degraded_name}"
                    ),
                    confidence=0.3,
                )
            )

        return hints

    def get_all_hints(self) -> dict[str, list[RoutingHint]]:
        """Get routing hints for all task types.

        Returns:
            Dict mapping task_type → list of RoutingHint.
        """
        all_metrics = self._tracker.get_all_metrics()
        task_types = {m.task_type for m in all_metrics.values()}
        return {tt: self.get_hints(tt) for tt in sorted(task_types)}


# ── FeedbackLoop ───────────────────────────────────────────────────────────────


class FeedbackLoop:
    """Integrates ModelTron feedback with the routing/load_balancer.

    Applies performance feedback to adjust routing weights:
      - Marks degraded models with reduced weight
      - Boosts healthy/fast alternatives
      - Tracks weight adjustments per model+task

    Thread-safe.
    """

    def __init__(
        self,
        tracker: PerformanceTracker,
        feedback: RoutingFeedback,
        load_balancer: Any = None,
    ) -> None:
        self._tracker = tracker
        self._feedback = feedback
        self._load_balancer = load_balancer
        self._lock = threading.Lock()
        # model_name:task_type → adjusted weight multiplier
        self._weight_adjustments: dict[str, float] = {}
        # model_name:task_type → degradation state
        self._degraded_models: set[str] = set()

    @property
    def tracker(self) -> PerformanceTracker:
        return self._tracker

    @property
    def feedback(self) -> RoutingFeedback:
        return self._feedback

    @property
    def degraded_models(self) -> set[str]:
        with self._lock:
            return set(self._degraded_models)

    def _key(self, model_name: str, task_type: str) -> str:
        return f"{model_name}:{task_type}"

    def get_adjusted_weight(
        self, model_name: str, task_type: str, base_weight: float = 1.0
    ) -> float:
        """Get the performance-adjusted weight for a model+task.

        Args:
            model_name: The model name.
            task_type: The task type.
            base_weight: The base weight before adjustment.

        Returns:
            Adjusted weight (0.0 to base_weight * 2.0).
        """
        key = self._key(model_name, task_type)
        with self._lock:
            adjustment = self._weight_adjustments.get(key, 1.0)
        return base_weight * adjustment

    def refresh(self) -> dict[str, Any]:
        """Refresh feedback loop state from latest performance data.

        Re-evaluates degradation states and weight adjustments based on
        current PerformanceTracker data.

        Returns:
            Status dict with changes applied.
        """
        hints = self._feedback.get_all_hints()
        changes: dict[str, Any] = {"degraded": [], "boosted": [], "restored": []}

        with self._lock:
            new_degraded: set[str] = set()

            for task_type, task_hints in hints.items():
                for hint in task_hints:
                    for model_name in hint.degraded_models:
                        key = self._key(model_name, task_type)
                        new_degraded.add(key)
                        # Reduce weight for degraded models
                        if key not in self._degraded_models:
                            # Newly degraded — halve weight
                            old = self._weight_adjustments.get(key, 1.0)
                            self._weight_adjustments[key] = max(0.1, old * 0.5)
                            changes["degraded"].append(
                                {"model": model_name, "task": task_type, "weight": self._weight_adjustments[key]}
                            )

                    for model_name in hint.preferred_models:
                        key = self._key(model_name, task_type)
                        # Boost weight for preferred models
                        if key not in self._degraded_models:
                            old = self._weight_adjustments.get(key, 1.0)
                            self._weight_adjustments[key] = min(2.0, old * 1.2)
                            changes["boosted"].append(
                                {"model": model_name, "task": task_type, "weight": self._weight_adjustments[key]}
                            )

            # Restore models that are no longer degraded
            restored = self._degraded_models - new_degraded
            for key in restored:
                self._weight_adjustments[key] = 1.0
                parts = key.split(":", 1)
                changes["restored"].append(
                    {"model": parts[0], "task": parts[1] if len(parts) > 1 else "default"}
                )

            self._degraded_models = new_degraded

        return changes

    def is_model_degraded(self, model_name: str, task_type: str) -> bool:
        """Check if a model is currently marked as degraded for a task."""
        key = self._key(model_name, task_type)
        with self._lock:
            return key in self._degraded_models

    def apply_to_load_balancer(self, task_type: str) -> None:
        """Apply current weight adjustments to the load balancer.

        If a load_balancer is configured, updates its node weights based
        on ModelTron performance data.
        """
        if self._load_balancer is None:
            return

        with self._lock:
            for key, weight in self._weight_adjustments.items():
                parts = key.split(":", 1)
                model = parts[0]
                task = parts[1] if len(parts) > 1 else "default"
                if task == task_type:
                    try:
                        if hasattr(self._load_balancer, "set_node_weight"):
                            self._load_balancer.set_node_weight(model, weight)
                    except Exception as exc:
                        logger.debug("Failed to set load balancer weight: %s", exc)

    def status(self) -> dict[str, Any]:
        """Return feedback loop status."""
        with self._lock:
            return {
                "degraded_count": len(self._degraded_models),
                "degraded_models": sorted(self._degraded_models),
                "weight_adjustments": dict(self._weight_adjustments),
                "tracker": self._tracker.status(),
            }


# ── Module-level convenience ───────────────────────────────────────────────────


# Global instances (lazily initialized)
_global_tracker: PerformanceTracker | None = None
_global_feedback: RoutingFeedback | None = None
_global_loop: FeedbackLoop | None = None
_global_lock = threading.RLock()


def get_tracker() -> PerformanceTracker:
    """Get or create the global PerformanceTracker."""
    global _global_tracker
    if _global_tracker is None:
        with _global_lock:
            if _global_tracker is None:
                _global_tracker = PerformanceTracker()
    return _global_tracker


def get_feedback() -> RoutingFeedback:
    """Get or create the global RoutingFeedback."""
    global _global_feedback
    if _global_feedback is None:
        with _global_lock:
            if _global_feedback is None:
                _global_feedback = RoutingFeedback(get_tracker())
    return _global_feedback


def get_feedback_loop(load_balancer: Any = None) -> FeedbackLoop:
    """Get or create the global FeedbackLoop."""
    global _global_loop
    if _global_loop is None:
        with _global_lock:
            if _global_loop is None:
                _global_loop = FeedbackLoop(
                    get_tracker(), get_feedback(), load_balancer
                )
    elif load_balancer is not None and _global_loop._load_balancer is None:
        _global_loop._load_balancer = load_balancer
    return _global_loop


def report_performance(
    model_name: str,
    task_type: str,
    latency_ms: float,
    tokens_per_second: float = 0.0,
    error: bool = False,
) -> None:
    """Convenience function: record a performance data point globally."""
    get_tracker().record(model_name, task_type, latency_ms, tokens_per_second, error)


def get_routing_hints(task_type: str) -> list[dict[str, Any]]:
    """Convenience function: get routing hints for a task type."""
    hints = get_feedback().get_hints(task_type)
    return [h.to_dict() for h in hints]
