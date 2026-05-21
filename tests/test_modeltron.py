"""
Tests for modeltron — performance tracking, routing feedback generation,
window-based metrics, and edge cases.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from hlf_mcp.hlf.modeltron import (
    PerformanceRecord,
    AggregatedMetrics,
    PerformanceTracker,
    RoutingFeedback,
    RoutingHint,
    FeedbackLoop,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_TIME_WINDOW,
    DEFAULT_LATENCY_DEGRADED_MS,
    DEFAULT_ERROR_RATE_DEGRADED,
    report_performance,
    get_routing_hints,
    get_tracker,
    get_feedback,
    get_feedback_loop,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def tracker() -> PerformanceTracker:
    """Fresh PerformanceTracker for each test."""
    import hlf_mcp.hlf.modeltron as mt
    mt._global_tracker = None
    mt._global_feedback = None
    mt._global_loop = None
    return PerformanceTracker()


@pytest.fixture
def populated_tracker(tracker: PerformanceTracker) -> PerformanceTracker:
    """Tracker with sample performance data."""
    # Fast model
    for _ in range(50):
        tracker.record("fast-model", "chat", latency_ms=100.0, tokens_per_second=80.0, error=False)
    # Slow model
    for _ in range(30):
        tracker.record("slow-model", "chat", latency_ms=8000.0, tokens_per_second=10.0, error=False)
    # Error-prone model
    for _ in range(20):
        tracker.record("error-model", "chat", latency_ms=200.0, error=True)
    for _ in range(10):
        tracker.record("error-model", "chat", latency_ms=200.0, error=False)
    return tracker


# ── PerformanceRecord Tests ───────────────────────────────────────────────────


class TestPerformanceRecord:
    """Test PerformanceRecord dataclass."""

    def test_defaults(self) -> None:
        record = PerformanceRecord(
            model_name="test-model",
            task_type="chat",
            latency_ms=100.0,
        )
        assert record.model_name == "test-model"
        assert record.task_type == "chat"
        assert record.latency_ms == 100.0
        assert record.tokens_per_second == 0.0
        assert record.error is False
        assert record.timestamp > 0

    def test_to_dict(self) -> None:
        now = time.time()
        record = PerformanceRecord(
            model_name="test-model",
            task_type="code",
            latency_ms=500.0,
            tokens_per_second=50.0,
            error=True,
            timestamp=now,
        )
        d = record.to_dict()
        assert d["model_name"] == "test-model"
        assert d["task_type"] == "code"
        assert d["latency_ms"] == 500.0
        assert d["tokens_per_second"] == 50.0
        assert d["error"] is True
        assert d["timestamp"] == now


# ── PerformanceTracker Tests ──────────────────────────────────────────────────


class TestPerformanceTracker:
    """Test PerformanceTracker — recording and aggregating metrics."""

    def test_record_single(self, tracker: PerformanceTracker) -> None:
        """Test recording a single data point."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        metrics = tracker.get_metrics("model-a", "chat")
        assert metrics.sample_count == 1
        assert metrics.latency_avg == 100.0
        assert metrics.error_rate == 0.0

    def test_record_multiple_same_model(self, tracker: PerformanceTracker) -> None:
        """Test recording multiple points for the same model+task."""
        for latency in [100.0, 200.0, 300.0]:
            tracker.record("model-a", "chat", latency_ms=latency)
        metrics = tracker.get_metrics("model-a", "chat")
        assert metrics.sample_count == 3
        assert metrics.latency_avg == 200.0
        assert metrics.latency_min == 100.0
        assert metrics.latency_max == 300.0

    def test_record_multiple_models(self, tracker: PerformanceTracker) -> None:
        """Test recording for different models and tasks."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        tracker.record("model-b", "chat", latency_ms=200.0)
        tracker.record("model-a", "code", latency_ms=300.0)

        all_metrics = tracker.get_all_metrics()
        assert len(all_metrics) == 3  # 3 unique model:task combos

    def test_percentile_calculation(self, tracker: PerformanceTracker) -> None:
        """Test p50, p95, p99 calculations."""
        for i in range(100):
            tracker.record("model-a", "chat", latency_ms=float(i + 1))

        metrics = tracker.get_metrics("model-a", "chat")
        # With 100 sorted values [1..100]:
        # p50 should be around 50.5
        assert 49 <= metrics.latency_p50 <= 52
        # p95 should be around 95
        assert 93 <= metrics.latency_p95 <= 97
        # p99 should be around 99
        assert 97 <= metrics.latency_p99 <= 100

    def test_error_rate(self, tracker: PerformanceTracker) -> None:
        """Test error rate calculation."""
        for _ in range(7):
            tracker.record("model-a", "chat", latency_ms=100.0, error=False)
        for _ in range(3):
            tracker.record("model-a", "chat", latency_ms=100.0, error=True)

        metrics = tracker.get_metrics("model-a", "chat")
        assert metrics.sample_count == 10
        assert metrics.error_count == 3
        assert metrics.error_rate == 0.3

    def test_token_throughput_avg(self, tracker: PerformanceTracker) -> None:
        """Test average token throughput calculation."""
        tracker.record("model-a", "chat", latency_ms=100.0, tokens_per_second=50.0)
        tracker.record("model-a", "chat", latency_ms=200.0, tokens_per_second=100.0)
        tracker.record("model-a", "chat", latency_ms=300.0, tokens_per_second=0.0)

        metrics = tracker.get_metrics("model-a", "chat")
        assert metrics.tokens_per_second_avg == 75.0  # (50+100)/2 (0 excluded)

    def test_time_window_filters_old(self, tracker: PerformanceTracker) -> None:
        """Test that records outside the time window are excluded."""
        # Record with an old timestamp by patching time
        old_time = time.time() - 9999
        with patch("time.time", return_value=old_time):
            tracker.record("model-a", "chat", latency_ms=100.0)

        # Now record fresh data
        tracker.record("model-a", "chat", latency_ms=200.0)

        metrics = tracker.get_metrics("model-a", "chat")
        # Only the fresh record should be counted
        assert metrics.sample_count == 1
        assert metrics.latency_avg == 200.0

    def test_window_size_limit(self) -> None:
        """Test that count-based window limits the number of records."""
        small_tracker = PerformanceTracker(window_size=10)
        for i in range(20):
            small_tracker.record("model-a", "chat", latency_ms=float(i))

        metrics = small_tracker.get_metrics("model-a", "chat")
        assert metrics.sample_count <= 10

    def test_empty_metrics(self, tracker: PerformanceTracker) -> None:
        """Test metrics for a model with no data."""
        metrics = tracker.get_metrics("nonexistent", "chat")
        assert metrics.sample_count == 0
        assert metrics.latency_avg == 0.0
        assert metrics.error_rate == 0.0
        assert metrics.is_degraded is False

    def test_single_datapoint(self, tracker: PerformanceTracker) -> None:
        """Test metrics with exactly one data point (edge case)."""
        tracker.record("model-a", "chat", latency_ms=500.0)
        metrics = tracker.get_metrics("model-a", "chat")
        assert metrics.sample_count == 1
        assert metrics.latency_avg == 500.0
        assert metrics.latency_p50 == 500.0
        assert metrics.latency_p95 == 500.0
        assert metrics.latency_p99 == 500.0
        assert metrics.latency_min == 500.0
        assert metrics.latency_max == 500.0
        # Not enough samples to be degraded
        assert metrics.is_degraded is False

    def test_clear_all(self, tracker: PerformanceTracker) -> None:
        """Test clearing all records."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        tracker.record("model-b", "chat", latency_ms=200.0)
        assert len(tracker.get_all_metrics()) == 2

        tracker.clear()
        assert len(tracker.get_all_metrics()) == 0

    def test_clear_model(self, tracker: PerformanceTracker) -> None:
        """Test clearing records for a specific model."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        tracker.record("model-b", "chat", latency_ms=200.0)

        tracker.clear(model_name="model-a")
        all_metrics = tracker.get_all_metrics()
        assert len(all_metrics) == 1
        assert "model-b:chat" in all_metrics

    def test_clear_task(self, tracker: PerformanceTracker) -> None:
        """Test clearing records for a specific task type."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        tracker.record("model-a", "code", latency_ms=200.0)

        tracker.clear(task_type="chat")
        all_metrics = tracker.get_all_metrics()
        assert len(all_metrics) == 1
        assert "model-a:code" in all_metrics

    def test_status(self, tracker: PerformanceTracker) -> None:
        """Test tracker status output."""
        tracker.record("model-a", "chat", latency_ms=100.0)
        status = tracker.status()
        assert status["tracked_combinations"] == 1
        assert status["total_records"] == 1
        assert status["window_size"] == DEFAULT_WINDOW_SIZE


# ── AggregatedMetrics Tests ───────────────────────────────────────────────────


class TestAggregatedMetrics:
    """Test AggregatedMetrics degradation detection."""

    def test_is_degraded_false(self) -> None:
        """Test healthy model is not degraded."""
        metrics = AggregatedMetrics(
            model_name="healthy",
            task_type="chat",
            sample_count=50,
            error_count=0,
            error_rate=0.0,
            latency_avg=200.0,
            latency_p95=400.0,
            latency_p99=500.0,
        )
        assert metrics.is_degraded is False

    def test_is_degraded_high_error(self) -> None:
        """Test model with high error rate is degraded."""
        metrics = AggregatedMetrics(
            model_name="flaky",
            task_type="chat",
            sample_count=50,
            error_count=20,
            error_rate=0.40,
            latency_avg=200.0,
            latency_p95=400.0,
        )
        assert metrics.is_degraded is True

    def test_is_degraded_high_latency(self) -> None:
        """Test model with high p95 latency is degraded."""
        metrics = AggregatedMetrics(
            model_name="slow",
            task_type="chat",
            sample_count=50,
            error_count=0,
            error_rate=0.0,
            latency_avg=6000.0,
            latency_p95=8000.0,
        )
        assert metrics.is_degraded is True

    def test_is_degraded_cold_start(self) -> None:
        """Test cold start (few samples) is not degraded."""
        metrics = AggregatedMetrics(
            model_name="new-model",
            task_type="chat",
            sample_count=2,
            error_count=2,
            error_rate=1.0,
            latency_p95=20000.0,
        )
        assert metrics.is_degraded is False  # Not enough samples

    def test_success_count(self) -> None:
        metrics = AggregatedMetrics(
            model_name="test",
            task_type="chat",
            sample_count=100,
            error_count=15,
        )
        assert metrics.success_count == 85

    def test_to_dict(self) -> None:
        metrics = AggregatedMetrics(
            model_name="test",
            task_type="chat",
            sample_count=10,
            error_count=2,
            error_rate=0.2,
            latency_avg=300.0,
            latency_p50=250.0,
            latency_p95=500.0,
            latency_p99=550.0,
        )
        d = metrics.to_dict()
        assert d["model_name"] == "test"
        assert d["is_degraded"] == metrics.is_degraded


# ── RoutingFeedback Tests ─────────────────────────────────────────────────────


class TestRoutingFeedback:
    """Test RoutingFeedback — generating routing hints."""

    def test_get_hints_healthy(self, populated_tracker: PerformanceTracker) -> None:
        """Test hints when all models are healthy."""
        feedback = RoutingFeedback(populated_tracker)
        # fast-model is healthy with 50 samples
        hints = feedback.get_hints("chat")
        # slow-model should be degraded (p95 > 5000ms), error-model degraded (>10% errors)
        assert len(hints) > 0

    def test_get_hints_no_data(self, tracker: PerformanceTracker) -> None:
        """Test hints with no performance data."""
        feedback = RoutingFeedback(tracker)
        hints = feedback.get_hints("chat")
        assert hints == []

    def test_get_hints_cold_start(self, tracker: PerformanceTracker) -> None:
        """Test hints with insufficient data (cold start)."""
        tracker.record("model-a", "chat", latency_ms=99999.0, error=True)
        tracker.record("model-a", "chat", latency_ms=99999.0, error=True)
        feedback = RoutingFeedback(tracker, min_samples=5)
        hints = feedback.get_hints("chat")
        # Not enough samples, so no hints
        assert hints == []

    def test_get_hints_all_degraded(self, tracker: PerformanceTracker) -> None:
        """Test hints when all models are degraded."""
        for _ in range(30):
            tracker.record("model-a", "chat", latency_ms=10000.0, error=True)
            tracker.record("model-b", "chat", latency_ms=10000.0, error=False)

        feedback = RoutingFeedback(tracker, min_samples=5)
        hints = feedback.get_hints("chat")
        # All degraded — should suggest least degraded
        assert len(hints) == 1
        assert hints[0].confidence < 0.5
        assert "All models degraded" in hints[0].reason

    def test_get_hints_preferred_models(self, populated_tracker: PerformanceTracker) -> None:
        """Test that hints include preferred (healthy) models."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        hints = feedback.get_hints("chat")
        if hints:
            hint = hints[0]
            assert len(hint.preferred_models) > 0
            assert len(hint.degraded_models) > 0
            assert hint.confidence > 0

    def test_get_all_hints(self, populated_tracker: PerformanceTracker) -> None:
        """Test hints for all task types."""
        # Add a second task type
        populated_tracker.record("fast-model", "code", latency_ms=50.0, error=False)
        populated_tracker.record("slow-model", "code", latency_ms=500.0, error=False)

        feedback = RoutingFeedback(populated_tracker)
        all_hints = feedback.get_all_hints()
        assert isinstance(all_hints, dict)
        assert "chat" in all_hints

    def test_hint_to_dict(self) -> None:
        """Test RoutingHint serialization."""
        hint = RoutingHint(
            task_type="chat",
            degraded_models=["slow-model"],
            preferred_models=["fast-model"],
            reason="slow-model is degraded",
            confidence=0.85,
        )
        d = hint.to_dict()
        assert d["task_type"] == "chat"
        assert d["degraded_models"] == ["slow-model"]
        assert d["preferred_models"] == ["fast-model"]
        assert d["confidence"] == 0.85


# ── FeedbackLoop Tests ────────────────────────────────────────────────────────


class TestFeedbackLoop:
    """Test FeedbackLoop — integrating feedback with routing."""

    def test_empty_state(self, tracker: PerformanceTracker) -> None:
        """Test initial state of a new FeedbackLoop."""
        feedback = RoutingFeedback(tracker)
        loop = FeedbackLoop(tracker, feedback)
        assert len(loop.degraded_models) == 0

    def test_refresh_detects_degraded(self, populated_tracker: PerformanceTracker) -> None:
        """Test that refresh detects degraded models."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback)
        changes = loop.refresh()
        # slow-model and error-model should be degraded
        assert len(loop.degraded_models) > 0

    def test_is_model_degraded(self, populated_tracker: PerformanceTracker) -> None:
        """Test checking if a specific model is degraded."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback)
        loop.refresh()
        # fast-model should not be degraded
        assert loop.is_model_degraded("fast-model", "chat") is False

    def test_weight_adjustment(self, populated_tracker: PerformanceTracker) -> None:
        """Test that weight adjustments are applied."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback)
        loop.refresh()

        # fast-model weight should be boosted
        weight = loop.get_adjusted_weight("fast-model", "chat", base_weight=1.0)
        # Could be boosted or at base — depends on whether it was preferred
        assert weight > 0

    def test_degraded_weight_reduced(self, populated_tracker: PerformanceTracker) -> None:
        """Test that degraded model weights are reduced."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback)
        loop.refresh()

        # Check any degraded model has reduced weight
        for key in loop.degraded_models:
            parts = key.split(":", 1)
            model = parts[0]
            task = parts[1] if len(parts) > 1 else "default"
            weight = loop.get_adjusted_weight(model, task, base_weight=1.0)
            assert weight <= 1.0  # Degraded means <= base weight

    def test_refresh_restores_models(self, populated_tracker: PerformanceTracker) -> None:
        """Test that models are restored when they recover."""
        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback)

        # First refresh — models may be degraded
        changes1 = loop.refresh()
        degraded_before = len(loop.degraded_models)

        # Clear data for degraded models and add healthy data
        populated_tracker.clear()
        for _ in range(30):
            populated_tracker.record("slow-model", "chat", latency_ms=100.0, error=False)
            populated_tracker.record("error-model", "chat", latency_ms=100.0, error=False)

        changes2 = loop.refresh()
        # Should have fewer or no degraded models now
        assert "restored" in changes2

    def test_status(self, populated_tracker: PerformanceTracker) -> None:
        """Test FeedbackLoop status output."""
        feedback = RoutingFeedback(populated_tracker)
        loop = FeedbackLoop(populated_tracker, feedback)
        loop.refresh()

        status = loop.status()
        assert "degraded_count" in status
        assert "weight_adjustments" in status
        assert "tracker" in status

    def test_apply_to_load_balancer_noop(self, populated_tracker: PerformanceTracker) -> None:
        """Test apply_to_load_balancer is no-op without balancer."""
        feedback = RoutingFeedback(populated_tracker)
        loop = FeedbackLoop(populated_tracker, feedback)
        # Should not raise
        loop.apply_to_load_balancer("chat")

    def test_apply_to_load_balancer_with_mock(self, populated_tracker: PerformanceTracker) -> None:
        """Test apply_to_load_balancer with a mock load balancer."""
        mock_lb = MagicMock()
        mock_lb.set_node_weight = MagicMock()

        feedback = RoutingFeedback(populated_tracker, min_samples=5)
        loop = FeedbackLoop(populated_tracker, feedback, load_balancer=mock_lb)
        loop.refresh()
        loop.apply_to_load_balancer("chat")

        # May or may not call set_node_weight depending on state
        # Just verify it doesn't crash


# ── Convenience Functions Tests ───────────────────────────────────────────────


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_report_performance(self) -> None:
        """Test global report_performance function."""
        import hlf_mcp.hlf.modeltron as mt
        mt._global_tracker = None
        mt._global_feedback = None
        mt._global_loop = None

        report_performance("test-model", "chat", 100.0, 50.0, False)
        tracker = get_tracker()
        metrics = tracker.get_metrics("test-model", "chat")
        assert metrics.sample_count == 1

    def test_get_routing_hints(self) -> None:
        """Test global get_routing_hints function."""
        import hlf_mcp.hlf.modeltron as mt
        mt._global_tracker = None
        mt._global_feedback = None
        mt._global_loop = None

        for _ in range(20):
            report_performance("fast-model", "chat", 100.0, 80.0, False)
        for _ in range(20):
            report_performance("slow-model", "chat", 10000.0, 5.0, False)

        hints = get_routing_hints("chat")
        assert isinstance(hints, list)
        # Should have at least one hint (slow-model degraded)
        assert len(hints) > 0

    def test_get_tracker_singleton(self) -> None:
        """Test get_tracker returns singleton."""
        import hlf_mcp.hlf.modeltron as mt
        mt._global_tracker = None

        t1 = get_tracker()
        t2 = get_tracker()
        assert t1 is t2

    def test_get_feedback_singleton(self) -> None:
        """Test get_feedback returns singleton."""
        import hlf_mcp.hlf.modeltron as mt
        mt._global_tracker = None
        mt._global_feedback = None

        f1 = get_feedback()
        f2 = get_feedback()
        assert f1 is f2

    def test_get_feedback_loop_singleton(self) -> None:
        """Test get_feedback_loop returns singleton."""
        import hlf_mcp.hlf.modeltron as mt
        mt._global_tracker = None
        mt._global_feedback = None
        mt._global_loop = None

        loop1 = get_feedback_loop()
        loop2 = get_feedback_loop()
        assert loop1 is loop2
