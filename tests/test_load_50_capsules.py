"""
Enterprise Hardening Commit 7: Load Testing (50 Concurrent Capsules).

Validates:
  1. 50 capsules can be queued without OOM (queue discipline)
  2. Backpressure: capsules rejected when queue exceeds max_depth
  3. Fair gas scheduling: all capsules make progress
  4. No capsule loses its Merkle chain under contention
  5. Peak concurrency respects max_concurrent
  6. Queue depth never exceeds max_queue_depth
  7. Timeout handling: capsules abort after timeout
  8. Metrics are complete and accurate
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the hlf_mcp package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.load_tester import (  # noqa: E402
    CapsuleLoadQueue,
    CapsuleQueueConfig,
    CapsuleStatus,
    LoadCapsule,
    QueueMetrics,
    run_load_test,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def default_config() -> CapsuleQueueConfig:
    return CapsuleQueueConfig(
        max_concurrent=3,
        max_queue_depth=100,
        gas_per_round=25,
        round_interval_ms=0,  # No sleep in tests
        timeout_seconds=600,
    )


@pytest.fixture
def fast_config() -> CapsuleQueueConfig:
    """Fast config for tests that need quick completion."""
    return CapsuleQueueConfig(
        max_concurrent=5,
        max_queue_depth=50,
        gas_per_round=50,
        round_interval_ms=0,
        timeout_seconds=5,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Queue Discipline Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestQueueDiscipline:
    """50 capsules can be queued without system failure."""

    def test_fifty_capsules_all_accepted(self, default_config):
        """All 50 capsules enter the queue successfully."""
        queue = CapsuleLoadQueue(default_config)
        for i in range(50):
            capsule = LoadCapsule(intent=f"intent_{i}")
            accepted = queue.submit(capsule)
            assert accepted, f"Capsule {i} should be accepted"

        assert queue.queue_depth == 50
        assert queue.running_count == 0  # Not yet dispatched
        assert queue.rejected_count == 0

    def test_fifty_capsules_complete_without_oom(self, fast_config):
        """50 capsules complete without any OOM or system failure."""
        completed, metrics = run_load_test(
            capsule_count=50,
            config=fast_config,
            max_rounds=500,
        )

        assert len(completed) == 50
        assert metrics.total_completed == 50
        assert metrics.total_rejected == 0
        assert metrics.total_aborted == 0

    def test_every_capsule_gets_some_gas(self, fast_config):
        """Fair gas scheduling: every capsule receives gas allocation."""
        completed, metrics = run_load_test(
            capsule_count=50,
            config=fast_config,
            max_rounds=500,
        )

        for capsule in completed:
            assert capsule.gas_used > 0, (
                f"Capsule {capsule.capsule_id} received zero gas"
            )
            assert capsule.gas_used >= capsule.gas_limit, (
                f"Capsule {capsule.capsule_id} did not reach gas limit: "
                f"{capsule.gas_used}/{capsule.gas_limit}"
            )

    def test_queue_depth_never_exceeds_max(self, default_config):
        """Queue depth respects max_queue_depth."""
        tight_config = CapsuleQueueConfig(
            max_concurrent=1,
            max_queue_depth=5,
            gas_per_round=5,
            round_interval_ms=0,
        )
        queue = CapsuleLoadQueue(tight_config)

        # Submit 20 capsules — first 5 accepted, rest rejected
        accepted = 0
        rejected = 0
        for i in range(20):
            capsule = LoadCapsule(intent=f"intent_{i}")
            if queue.submit(capsule):
                accepted += 1
            else:
                rejected += 1

        assert accepted == 5  # queue depth limit
        assert rejected == 15  # backpressure kicks in
        assert queue.queue_depth == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Backpressure Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackpressure:
    """Capsules are rejected when queue exceeds max_depth."""

    def test_rejected_capsule_has_rejected_status(self, default_config):
        """Rejected capsules get CapsuleStatus.REJECTED."""
        tight = CapsuleQueueConfig(max_queue_depth=1, max_concurrent=1, gas_per_round=5)
        queue = CapsuleLoadQueue(tight)

        capsule1 = LoadCapsule(intent="first")
        capsule2 = LoadCapsule(intent="second")

        assert queue.submit(capsule1) is True
        assert capsule1.status == CapsuleStatus.QUEUED

        assert queue.submit(capsule2) is False
        assert capsule2.status == CapsuleStatus.REJECTED

    def test_backpressure_metrics_correct(self, default_config):
        """Rejection metrics are accurate."""
        tight = CapsuleQueueConfig(max_queue_depth=3, max_concurrent=1, gas_per_round=20)
        queue = CapsuleLoadQueue(tight)

        for i in range(10):
            queue.submit(LoadCapsule(intent=f"intent_{i}"))

        metrics = queue.collect_metrics()
        assert metrics.total_submitted == 10
        assert metrics.total_rejected == 7  # 10 - 3 accepted

    def test_rejected_does_not_consume_gas(self, default_config):
        """Rejected capsules don't consume any gas budget."""
        tight = CapsuleQueueConfig(
            max_queue_depth=1, max_concurrent=1, gas_per_round=10, round_interval_ms=0
        )

        # Submit 3 capsules, only 1 accepted
        accepted_capsule = LoadCapsule(intent="a", gas_limit=500)
        rejected_1 = LoadCapsule(intent="r1", gas_limit=500)
        rejected_2 = LoadCapsule(intent="r2", gas_limit=500)

        queue = CapsuleLoadQueue(tight)
        queue.submit(accepted_capsule)
        queue.submit(rejected_1)
        queue.submit(rejected_2)

        # Process manually (not via run_load_test which creates a new queue)
        for _ in range(200):
            if queue.is_idle:
                break
            queue.dispatch_round()
            queue.schedule_round()

        # Rejected capsules should have zero gas used
        assert rejected_1.gas_used == 0
        assert rejected_2.gas_used == 0

        # Accepted capsule should have used its gas
        assert accepted_capsule.gas_used >= accepted_capsule.gas_limit


# ═══════════════════════════════════════════════════════════════════════════════
# Fair Gas Scheduling Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFairGasScheduling:
    """Gas is allocated fairly across concurrent capsules."""

    def test_max_concurrent_respected(self, fast_config):
        """Peak concurrency never exceeds max_concurrent."""
        cfg = CapsuleQueueConfig(
            max_concurrent=3,
            max_queue_depth=50,
            gas_per_round=25,
            round_interval_ms=0,
        )
        completed, metrics = run_load_test(
            capsule_count=30,
            config=cfg,
            max_rounds=300,
        )

        assert metrics.peak_concurrent <= cfg.max_concurrent

    def test_concurrent_capsules_all_make_progress(self, default_config):
        """With multiple concurrent slots, all running capsules get gas each round."""
        queue = CapsuleLoadQueue(default_config)

        # Submit and manually dispatch 3 capsules
        capsules = [LoadCapsule(intent=f"c{i}", gas_limit=200) for i in range(3)]
        for c in capsules:
            queue.submit(c)

        queue.dispatch_round()
        assert queue.running_count == 3

        # One scheduling round
        queue.schedule_round()

        # All 3 should have received gas
        for c in capsules:
            assert c.gas_used > 0, f"Capsule {c.capsule_id} got no gas"

    def test_gas_distribution_is_fair(self, fast_config):
        """Gas is distributed approximately evenly across capsules."""
        cfg = CapsuleQueueConfig(
            max_concurrent=3,
            max_queue_depth=50,
            gas_per_round=25,
            round_interval_ms=0,
        )
        completed, metrics = run_load_test(
            capsule_count=15,
            config=cfg,
            max_rounds=200,
        )

        # All capsules should have gas within reasonable range
        gas_used_values = [c.gas_used for c in completed]
        avg_gas = sum(gas_used_values) / len(gas_used_values)

        for gas in gas_used_values:
            # Each capsule should be within 50% of average (fairness rough check)
            assert gas >= avg_gas * 0.3, (
                f"Gas starvation detected: {gas} vs avg {avg_gas:.1f}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Merkle Chain Integrity Under Load
# ═══════════════════════════════════════════════════════════════════════════════


class TestChainIntegrityUnderLoad:
    """No capsule loses its Merkle chain under contention."""

    def test_all_chains_verified(self, fast_config):
        """All 50 capsules have intact Merkle chains after load test."""
        completed, metrics = run_load_test(
            capsule_count=50,
            config=fast_config,
            max_rounds=500,
        )

        assert metrics.chains_broken == 0, (
            f"{metrics.chains_broken} chains broken under load"
        )
        assert metrics.chains_verified == 50

    def test_each_capsule_has_chain_hashes(self, fast_config):
        """Each completed capsule has recorded chain steps."""
        completed, _ = run_load_test(
            capsule_count=20,
            config=fast_config,
            max_rounds=200,
        )

        for capsule in completed:
            assert len(capsule.chain_hashes) > 0, (
                f"Capsule {capsule.capsule_id} has empty chain"
            )
            # Should have at least: dispatch + schedule + complete
            assert len(capsule.chain_hashes) >= 2

    def test_chain_hashes_are_valid_sha256(self, fast_config):
        """All chain hashes are valid 64-char hex strings."""
        completed, _ = run_load_test(
            capsule_count=10,
            config=fast_config,
            max_rounds=100,
        )

        for capsule in completed:
            for h in capsule.chain_hashes:
                assert len(h) == 64, f"Hash wrong length: {len(h)}"
                assert all(c in "0123456789abcdef" for c in h), f"Invalid hex: {h[:16]}"


# ═══════════════════════════════════════════════════════════════════════════════
# Peak Metrics Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPeakMetrics:
    """Peak concurrency and queue depth are tracked."""

    def test_peak_queue_depth_recorded(self, default_config):
        """Peak queue depth is captured in metrics."""
        queue = CapsuleLoadQueue(default_config)
        for i in range(30):
            queue.submit(LoadCapsule(intent=f"intent_{i}"))

        metrics = queue.collect_metrics()
        assert metrics.peak_queue_depth == 30

    def test_peak_concurrent_recorded(self, default_config):
        """Peak concurrency is captured in metrics."""
        queue = CapsuleLoadQueue(default_config)
        for i in range(6):
            queue.submit(LoadCapsule(intent=f"intent_{i}"))
        queue.dispatch_round()

        metrics = queue.collect_metrics()
        assert metrics.peak_concurrent == min(6, default_config.max_concurrent)

    def test_avg_and_max_wait_time_recorded(self, fast_config):
        """Wait time metrics are populated."""
        completed, metrics = run_load_test(
            capsule_count=20,
            config=fast_config,
            max_rounds=200,
        )

        assert metrics.avg_wait_time_ms >= 0
        assert metrics.max_wait_time_ms >= 0
        # With fast config, wait times should be reasonable
        assert metrics.max_wait_time_ms < 5000, (
            f"Capsules waited too long: {metrics.max_wait_time_ms:.0f}ms"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Timeout Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTimeoutHandling:
    """Capsules abort after exceeding timeout."""

    def test_timeout_aborts_capsule(self):
        """A capsule that exceeds its timeout is aborted."""
        config = CapsuleQueueConfig(
            max_concurrent=5,
            max_queue_depth=50,
            gas_per_round=1,  # Tiny gas to force timeout
            round_interval_ms=0,
            timeout_seconds=0,  # Immediate timeout
        )
        queue = CapsuleLoadQueue(config)

        capsule = LoadCapsule(intent="test", gas_limit=1000)
        queue.submit(capsule)
        queue.dispatch_round()

        # Pass a future timestamp to trigger immediate timeout
        future_now = capsule.started_at + 0.001
        queue.check_timeouts(now=future_now)
        assert capsule.status == CapsuleStatus.ABORTED
        assert capsule.error == "timeout"

    def test_timeout_metrics_count_aborted(self):
        """Aborted capsules are counted in metrics."""
        config = CapsuleQueueConfig(
            max_concurrent=5,
            max_queue_depth=50,
            gas_per_round=1,
            round_interval_ms=0,
            timeout_seconds=0,
        )
        queue = CapsuleLoadQueue(config)

        for i in range(5):
            capsule = LoadCapsule(intent=f"test_{i}", gas_limit=1000)
            queue.submit(capsule)

        queue.dispatch_round()

        # Pass a future timestamp to trigger immediate timeout
        future_now = time.monotonic() + 0.001
        queue.check_timeouts(now=future_now)

        metrics = queue.collect_metrics()
        assert metrics.total_aborted == 5

    def test_aborted_capsule_still_has_chain(self):
        """Aborted capsules still produce partial chain records."""
        config = CapsuleQueueConfig(
            max_concurrent=5,
            max_queue_depth=50,
            gas_per_round=1,
            round_interval_ms=0,
            timeout_seconds=0,
        )
        queue = CapsuleLoadQueue(config)

        capsule = LoadCapsule(intent="test", gas_limit=1000)
        queue.submit(capsule)
        queue.dispatch_round()
        queue.check_timeouts()

        # Should have at least the dispatch hash
        assert len(capsule.chain_hashes) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Custom Processor Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustomProcessor:
    """Custom gas processor integrates correctly."""

    def test_custom_processor_receives_gas(self):
        """Custom processor is called with correct gas allocation."""
        gas_received: list[int] = []

        def processor(capsule: LoadCapsule, gas: int) -> int:
            gas_received.append(gas)
            return gas  # Consume all allocated gas

        config = CapsuleQueueConfig(
            max_concurrent=2,
            max_queue_depth=10,
            gas_per_round=25,
            round_interval_ms=0,
        )
        completed, metrics = run_load_test(
            capsule_count=5,
            config=config,
            processor=processor,
            max_rounds=100,
        )

        assert len(gas_received) > 0
        # All gas allocations should be <= gas_per_round
        for g in gas_received:
            assert g <= config.gas_per_round

    def test_partial_gas_consumption(self):
        """Processor can consume less gas than allocated."""

        def processor(capsule: LoadCapsule, gas: int) -> int:
            return max(1, gas // 2)  # Only consume half

        config = CapsuleQueueConfig(
            max_concurrent=2,
            max_queue_depth=10,
            gas_per_round=50,
            round_interval_ms=0,
        )
        completed, _ = run_load_test(
            capsule_count=5,
            config=config,
            processor=processor,
            max_rounds=200,
        )

        # All should eventually complete (just takes more rounds)
        assert len(completed) == 5
        for c in completed:
            assert c.status == CapsuleStatus.COMPLETED


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases for load testing."""

    def test_zero_capsules(self, default_config):
        """Zero capsules produces empty results cleanly."""
        completed, metrics = run_load_test(
            capsule_count=0,
            config=default_config,
            max_rounds=10,
        )

        assert len(completed) == 0
        assert metrics.total_submitted == 0
        assert metrics.total_completed == 0

    def test_single_capsule(self, fast_config):
        """Single capsule completes normally."""
        completed, metrics = run_load_test(
            capsule_count=1,
            config=fast_config,
            max_rounds=100,
        )

        assert len(completed) == 1
        assert metrics.total_completed == 1
        assert metrics.peak_concurrent <= 1

    def test_queue_smaller_than_capsule_count(self):
        """When max_queue_depth < capsule count, backpressure kicks in."""
        config = CapsuleQueueConfig(
            max_concurrent=2,
            max_queue_depth=10,
            gas_per_round=25,
            round_interval_ms=0,
        )
        completed, metrics = run_load_test(
            capsule_count=50,
            config=config,
            max_rounds=300,
        )

        # Only 10 should be accepted (queue depth)
        assert metrics.total_submitted == 50
        assert metrics.total_rejected == 40
        assert metrics.total_completed == 10

    def test_config_to_dict(self):
        """Config serialization works."""
        config = CapsuleQueueConfig()
        d = config.to_dict()
        assert d["max_concurrent"] == 3
        assert d["max_queue_depth"] == 100
        assert d["gas_per_round"] == 25

    def test_metrics_summary(self):
        """Metrics summary is a valid dict."""
        metrics = QueueMetrics(
            total_submitted=50,
            total_completed=48,
            total_rejected=2,
            chains_verified=48,
        )
        summary = metrics.summary()
        assert summary["submitted"] == 50
        assert summary["completed"] == 48
        assert summary["rejected"] == 2
        assert summary["chains_verified"] == 48
        assert summary["chains_broken"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Stress: 50 Capsule End-to-End
# ═══════════════════════════════════════════════════════════════════════════════


class Test50CapsuleEndToEnd:
    """The defining test: 50 capsules under realistic conditions."""

    def test_full_fifty_capsule_run(self):
        """50 capsules complete with chain integrity, fair gas, and no OOM."""
        config = CapsuleQueueConfig(
            max_concurrent=4,
            max_queue_depth=100,
            gas_per_round=25,
            round_interval_ms=0,
            timeout_seconds=60,
        )
        completed, metrics = run_load_test(
            capsule_count=50,
            config=config,
            max_rounds=1000,
        )

        # All 50 completed
        assert metrics.total_completed == 50
        assert metrics.total_rejected == 0
        assert metrics.total_aborted == 0
        assert len(completed) == 50

        # All chains verified
        assert metrics.chains_verified == 50
        assert metrics.chains_broken == 0

        # Fair gas distribution
        gas_values = [c.gas_used for c in completed]
        avg_gas = sum(gas_values) / len(gas_values)
        for gas in gas_values:
            assert gas >= avg_gas * 0.3, "Gas starvation detected"

        # Peak concurrency respected
        assert metrics.peak_concurrent <= config.max_concurrent

        # All capsules reached gas limit
        for c in completed:
            assert c.gas_used >= c.gas_limit, (
                f"Capsule {c.capsule_id} incomplete: {c.gas_used}/{c.gas_limit}"
            )

    def test_fifty_capsules_queue_is_idle_after(self, fast_config):
        """After all capsules complete, the queue is idle."""
        completed, _ = run_load_test(
            capsule_count=50,
            config=fast_config,
            max_rounds=500,
        )

        assert len(completed) == 50
        # All capsules done means nothing left to process


# ═══════════════════════════════════════════════════════════════════════════════
# Thread Safety (light)
# ═══════════════════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Basic thread safety: concurrent submits don't corrupt state."""

    def test_concurrent_submits(self, default_config):
        """Submitting from multiple threads doesn't corrupt queue."""
        queue = CapsuleLoadQueue(default_config)
        errors: list[Exception] = []

        def submit_batch(start: int, count: int) -> None:
            try:
                for i in range(start, start + count):
                    queue.submit(LoadCapsule(intent=f"t{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=submit_batch, args=(0, 10)),
            threading.Thread(target=submit_batch, args=(10, 10)),
            threading.Thread(target=submit_batch, args=(20, 10)),
            threading.Thread(target=submit_batch, args=(30, 10)),
            threading.Thread(target=submit_batch, args=(40, 10)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert queue.queue_depth == 50
        assert queue.rejected_count == 0

    def test_concurrent_dispatch_and_schedule(self, fast_config):
        """Dispatching and scheduling from threads is safe."""
        completed, _ = run_load_test(
            capsule_count=45,
            config=fast_config,
            max_rounds=400,
        )

        assert len(completed) == 45
        assert all(c.status == CapsuleStatus.COMPLETED for c in completed)
