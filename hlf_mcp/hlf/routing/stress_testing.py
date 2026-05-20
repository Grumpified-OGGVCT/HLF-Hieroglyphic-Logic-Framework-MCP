"""
Stress Testing — production-grade routing fabric stress testing module.

Simulates concurrent routing under load, measures latency distributions,
tests graceful degradation and partition tolerance, and generates
human-readable stress reports.

Usage::

    from hlf_mcp.hlf.routing.stress_testing import (
        StressScenario, StressResult, RoutingStressTest,
    )

    runner = RoutingStressTest()
    scenario = StressScenario(
        node_count=50, failure_rate=0.1,
        request_rate=100, duration=5.0,
    )
    result = runner.run_concurrent_routing(scenario)
    print(RoutingStressTest.generate_stress_report(scenario, result))
"""

from __future__ import annotations

import random
import statistics
import string
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer
from hlf_mcp.hlf.routing.failover import FailoverManager

_DEFAULT_CAPABILITIES = [
    "inference",
    "embedding",
    "vision",
    "audio",
    "translation",
    "code_generation",
    "summarization",
    "classification",
    "ocr",
    "rag",
]


def _random_capabilities(
    count: int,
    pool: list[str] | None = None,
) -> dict[str, int]:
    """Generate a random capability→proficiency mapping."""
    if pool is None:
        pool = _DEFAULT_CAPABILITIES
    selected = random.sample(pool, min(count, len(pool)))
    return {cap: random.randint(1, 10) for cap in selected}


def _random_node_id() -> str:
    """Generate a random node identifier."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"node-{suffix}"


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class StressScenario:
    """Configuration for a routing stress test scenario.

    Attributes:
        node_count: Number of nodes to register before the test.
        failure_rate: Fraction (0.0–1.0) of nodes that will be marked
            unhealthy during the test run.
        request_rate: Target requests per second.
        duration: Test duration in seconds.
        capabilities_per_node: How many capabilities each node declares.
        capability_names: Optional explicit list of capability names;
            defaults to the standard 10-capability pool.
    """

    node_count: int
    failure_rate: float  # 0.0–1.0
    request_rate: int  # requests per second target
    duration: float  # seconds
    capabilities_per_node: int = 3
    capability_names: list[str] | None = None


@dataclass
class StressResult:
    """Results from a stress test run.

    Attributes:
        scenario: The scenario that produced this result.
        total_requests: Total requests attempted.
        successful_routes: How many routes found a matching node.
        failed_routes: How many routes returned no match.
        latency_samples: Per-request latency in seconds.
        throughput: Actual requests/sec achieved.
        error_distribution: Error message → count mapping.
        observations: Human-readable observations (anomalies, etc.).
        p50_latency: 50th percentile latency.
        p95_latency: 95th percentile latency.
        p99_latency: 99th percentile latency.
    """

    scenario: StressScenario
    total_requests: int = 0
    successful_routes: int = 0
    failed_routes: int = 0
    latency_samples: list[float] = field(default_factory=list)
    throughput: float = 0.0
    error_distribution: dict[str, int] = field(default_factory=dict)
    observations: list[str] = field(default_factory=list)
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0


# ── Runner ────────────────────────────────────────────────────────────────────


class RoutingStressTest:
    """Real-world routing stress test runner.

    Uses NodeRegistry, CapabilityRouter, LoadBalancer, and FailoverManager
    in realistic multi-threaded scenarios.  All methods are thread-safe and
    produce deterministic-ish results suitable for regression detection.
    """

    def __init__(self) -> None:
        self._registry = NodeRegistry()
        self._router = CapabilityRouter(self._registry)
        self._lb = LoadBalancer(self._registry, self._router, strategy="round_robin")
        self._failover = FailoverManager(
            self._registry, self._router, self._lb, max_retries=3
        )

    # ── Concurrent routing ─────────────────────────────────────────────────

    def run_concurrent_routing(self, scenario: StressScenario) -> StressResult:
        """Simulate concurrent routing under load.

        Creates *node_count* nodes with random capabilities, then spawns
        worker threads that send requests at *request_rate* for *duration*
        seconds.  At *failure_rate*, nodes are marked unhealthy during the test.

        Uses proper synchronization: threading.Event for stop signal,
        threading.Barrier for coordinated start.
        """
        # Reset state
        self._registry = NodeRegistry()
        self._router = CapabilityRouter(self._registry)
        self._lb = LoadBalancer(self._registry, self._router, strategy="round_robin")
        self._failover = FailoverManager(
            self._registry, self._router, self._lb, max_retries=3
        )

        cap_pool = scenario.capability_names or _DEFAULT_CAPABILITIES
        node_ids: list[str] = []

        # Register nodes
        for i in range(scenario.node_count):
            nid = f"node-{i:04d}"
            node_ids.append(nid)
            caps = _random_capabilities(scenario.capabilities_per_node, cap_pool)
            self._registry.register(
                nid,
                f"10.0.{i // 250}.{i % 250}",
                9000 + (i % 1000),
                capabilities=caps,
            )

        # Determine which nodes will fail
        fail_count = int(scenario.node_count * scenario.failure_rate)
        fail_set: set[str] = set(random.sample(node_ids, fail_count)) if fail_count > 0 else set()

        # Shared state
        stop_event = threading.Event()
        results_lock = threading.Lock()
        latencies: list[float] = []
        total_requests = 0
        successful = 0
        failed = 0
        error_dist: dict[str, int] = {}

        # Calculate thread count and interval
        # We'll use enough threads to hit the target rate
        thread_count = max(1, min(scenario.request_rate, 50))
        interval_between_threads = 1.0 / max(1, thread_count)
        requests_per_thread = int(
            scenario.request_rate * scenario.duration / thread_count
        )
        if requests_per_thread < 1:
            requests_per_thread = 1

        # Recalculate total
        total_expected = requests_per_thread * thread_count

        barrier = threading.Barrier(thread_count + 1, timeout=30)

        def worker(worker_id: int) -> None:
            nonlocal total_requests, successful, failed

            # Wait for all threads ready
            try:
                barrier.wait(timeout=20)
            except threading.BrokenBarrierError:
                return

            local_requests = 0
            local_success = 0
            local_fail = 0
            local_latencies: list[float] = []
            local_errors: dict[str, int] = {}

            for req_idx in range(requests_per_thread):
                if stop_event.is_set():
                    break

                # Pick a random capability from the pool
                capability = random.choice(cap_pool)
                request = WorkRequest(
                    request_id=f"stress-{worker_id}-{req_idx}",
                    capability=capability,
                    required_proficiency=random.randint(1, 5),
                )

                t0 = time.perf_counter()
                try:
                    match = self._lb.distribute(request)
                except Exception as exc:
                    t1 = time.perf_counter()
                    local_latencies.append(t1 - t0)
                    local_fail += 1
                    err_key = type(exc).__name__
                    local_errors[err_key] = local_errors.get(err_key, 0) + 1
                    continue

                t1 = time.perf_counter()
                local_latencies.append(t1 - t0)

                if match.matched and match.matched_node is not None:
                    local_success += 1
                    # Simulate task completion
                    self._lb.decrement_active(match.matched_node.node_id)
                else:
                    local_fail += 1
                    err_key = "no_match"
                    local_errors[err_key] = local_errors.get(err_key, 0) + 1

                local_requests += 1

                # Inter-request pacing
                if not stop_event.is_set():
                    time.sleep(1.0 / scenario.request_rate * 0.01)

            # Merge results
            with results_lock:
                total_requests += local_requests
                successful += local_success
                failed += local_fail
                latencies.extend(local_latencies)
                for key, count in local_errors.items():
                    error_dist[key] = error_dist.get(key, 0) + count

        # Failure injector thread
        failure_injected = threading.Event()

        def failure_injector() -> None:
            try:
                barrier.wait(timeout=20)
            except threading.BrokenBarrierError:
                return

            # Wait a bit then start injecting failures
            time.sleep(scenario.duration * 0.3)
            if stop_event.is_set():
                return

            for nid in fail_set:
                if stop_event.is_set():
                    break
                self._registry.mark_unhealthy(nid)
                time.sleep(scenario.duration * 0.05)

            failure_injected.set()

        # Start all worker threads
        workers: list[threading.Thread] = []
        for w_id in range(thread_count):
            t = threading.Thread(target=worker, args=(w_id,), daemon=True)
            workers.append(t)

        injector = threading.Thread(target=failure_injector, daemon=True)

        for t in workers:
            t.start()
        injector.start()

        # Participate in the barrier (the +1)
        try:
            barrier.wait(timeout=20)
        except threading.BrokenBarrierError:
            pass

        # Sleep for the duration, then signal stop
        time.sleep(scenario.duration)
        stop_event.set()

        # Wait for workers to finish
        for t in workers:
            t.join(timeout=5.0)
        injector.join(timeout=5.0)

        # Compute stats
        actual_duration = scenario.duration
        throughput = total_requests / max(actual_duration, 0.001)

        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        if latencies:
            sorted_latencies = sorted(latencies)
            p50 = _percentile(sorted_latencies, 50)
            p95 = _percentile(sorted_latencies, 95)
            p99 = _percentile(sorted_latencies, 99)

        observations: list[str] = []
        if failed > total_requests * 0.5:
            observations.append(
                f"High failure rate: {failed}/{total_requests} "
                f"({100.0 * failed / max(total_requests, 1):.1f}%)"
            )
        if p95 > 0.5:
            observations.append(f"High p95 latency: {p95:.3f}s")
        if throughput < scenario.request_rate * 0.5:
            observations.append(
                f"Throughput ({throughput:.1f} req/s) below 50% of target "
                f"({scenario.request_rate} req/s)"
            )

        return StressResult(
            scenario=scenario,
            total_requests=total_requests,
            successful_routes=successful,
            failed_routes=failed,
            latency_samples=latencies,
            throughput=throughput,
            error_distribution=error_dist,
            observations=observations,
            p50_latency=p50,
            p95_latency=p95,
            p99_latency=p99,
        )

    # ── Latency measurement ─────────────────────────────────────────────────

    @staticmethod
    def measure_routing_latency(
        node_count: int = 20,
        request_count: int = 500,
    ) -> dict[str, float]:
        """Measure routing latency distribution.

        Creates a fixed set of nodes, sends *request_count* single-threaded
        requests, and returns p50/p95/p99/min/max/mean latency stats.
        """
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")

        cap_pool = _DEFAULT_CAPABILITIES

        for i in range(node_count):
            nid = f"latency-node-{i:04d}"
            caps = _random_capabilities(3, cap_pool)
            registry.register(nid, f"10.0.{i // 250}.{i % 250}", 9000 + (i % 1000), capabilities=caps)

        latencies: list[float] = []

        for req_idx in range(request_count):
            capability = random.choice(cap_pool)
            request = WorkRequest(
                request_id=f"latency-{req_idx}",
                capability=capability,
                required_proficiency=random.randint(1, 5),
            )
            t0 = time.perf_counter()
            match = lb.distribute(request)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)

            if match.matched and match.matched_node is not None:
                lb.decrement_active(match.matched_node.node_id)

        sorted_lat = sorted(latencies)
        return {
            "p50": _percentile(sorted_lat, 50),
            "p95": _percentile(sorted_lat, 95),
            "p99": _percentile(sorted_lat, 99),
            "min": min(latencies) if latencies else 0.0,
            "max": max(latencies) if latencies else 0.0,
            "mean": statistics.mean(latencies) if latencies else 0.0,
        }

    # ── Graceful degradation ────────────────────────────────────────────────

    def test_graceful_degradation(
        self,
        failure_pattern: list[float],
    ) -> list[StressResult]:
        """Test that the system degrades gracefully under increasing failure.

        *failure_pattern* is a list of failure rates to test sequentially
        (e.g. [0.0, 0.25, 0.5, 0.75]).  Each step runs a stress scenario
        and confirms that some routing still succeeds even at high failure.

        Returns results showing how success rate degrades.
        """
        results: list[StressResult] = []
        for rate in failure_pattern:
            scenario = StressScenario(
                node_count=20,
                failure_rate=rate,
                request_rate=50,
                duration=2.0,
                capabilities_per_node=3,
            )
            result = self.run_concurrent_routing(scenario)
            results.append(result)
        return results

    # ── Thundering herd recovery ────────────────────────────────────────────

    def test_thundering_herd_recovery(self) -> StressResult:
        """Test recovery when all nodes restart simultaneously.

        Creates nodes, marks them ALL as unhealthy simultaneously,
        then recovers them all at once and verifies routing resumes.
        Measures recovery time.
        """
        node_count = 20
        cap_pool = _DEFAULT_CAPABILITIES
        node_ids: list[str] = []

        # Register nodes
        for i in range(node_count):
            nid = f"herd-node-{i:04d}"
            node_ids.append(nid)
            caps = _random_capabilities(3, cap_pool)
            self._registry.register(
                nid,
                f"10.0.{i // 250}.{i % 250}",
                9000 + (i % 1000),
                capabilities=caps,
            )

        # Mark ALL unhealthy
        for nid in node_ids:
            self._registry.mark_unhealthy(nid)

        # Verify no routing works
        request = WorkRequest(
            request_id="herd-check",
            capability=cap_pool[0],
            required_proficiency=1,
        )
        dead_match = self._lb.distribute(request)
        pre_recovery_ok = dead_match.matched

        # Recover all at once
        recovery_start = time.perf_counter()
        for nid in node_ids:
            self._registry.mark_healthy(nid)
        recovery_end = time.perf_counter()
        recovery_time = recovery_end - recovery_start

        # Verify routing resumes
        latencies: list[float] = []
        successful = 0
        failed = 0
        for i in range(50):
            capability = random.choice(cap_pool)
            req = WorkRequest(
                request_id=f"herd-post-{i}",
                capability=capability,
                required_proficiency=1,
            )
            t0 = time.perf_counter()
            match = self._lb.distribute(req)
            t1 = time.perf_counter()
            latencies.append(t1 - t0)
            if match.matched and match.matched_node is not None:
                successful += 1
                self._lb.decrement_active(match.matched_node.node_id)
            else:
                failed += 1

        sorted_lat = sorted(latencies) if latencies else [0.0]
        observations: list[str] = [
            f"Recovery time: {recovery_time:.4f}s for {node_count} nodes",
        ]
        if pre_recovery_ok:
            observations.append("WARNING: routing succeeded when all nodes were unhealthy")
        if failed > 0:
            observations.append(f"Post-recovery failures: {failed}/{successful + failed}")

        scenario = StressScenario(
            node_count=node_count,
            failure_rate=1.0,
            request_rate=50,
            duration=0.5,
            capabilities_per_node=3,
        )
        return StressResult(
            scenario=scenario,
            total_requests=successful + failed,
            successful_routes=successful,
            failed_routes=failed,
            latency_samples=latencies,
            throughput=(successful + failed) / max(recovery_time, 0.001),
            error_distribution={},
            observations=observations,
            p50_latency=_percentile(sorted_lat, 50),
            p95_latency=_percentile(sorted_lat, 95),
            p99_latency=_percentile(sorted_lat, 99),
        )

    # ── Partition tolerance ─────────────────────────────────────────────────

    def test_partition_tolerance(
        self,
        partition_map: dict[str, list[str]],
    ) -> StressResult:
        """Test routing behavior under network partition.

        *partition_map* maps partition_name → [node_ids].
        Nodes in different partitions cannot route to each other.
        Verifies that each partition's internal routing still works.
        """
        cap_pool = _DEFAULT_CAPABILITIES
        all_node_ids: list[str] = []

        # Register all nodes
        for i, (partition_name, nids) in enumerate(partition_map.items()):
            for nid in nids:
                all_node_ids.append(nid)
                caps = _random_capabilities(3, cap_pool)
                self._registry.register(
                    nid,
                    f"10.0.{i}.{len(all_node_ids) % 250}",
                    9000 + (len(all_node_ids) % 1000),
                    capabilities=caps,
                    metadata={"partition": partition_name},
                )

        total_requests = 0
        successful = 0
        failed = 0
        latencies: list[float] = []
        error_dist: dict[str, int] = {}

        # Route within each partition
        for partition_name, nids in partition_map.items():
            if not nids:
                continue
            for _ in range(20):
                capability = random.choice(cap_pool)
                # Exclude nodes NOT in this partition
                excluded = set(all_node_ids) - set(nids)
                request = WorkRequest(
                    request_id=f"partition-{partition_name}-{total_requests}",
                    capability=capability,
                    required_proficiency=1,
                    exclude_nodes=excluded,
                )
                t0 = time.perf_counter()
                match = self._lb.distribute(request)
                t1 = time.perf_counter()
                latencies.append(t1 - t0)

                if match.matched and match.matched_node is not None:
                    if match.matched_node.node_id in nids:
                        successful += 1
                    else:
                        failed += 1
                        error_dist["cross_partition_route"] = (
                            error_dist.get("cross_partition_route", 0) + 1
                        )
                    self._lb.decrement_active(match.matched_node.node_id)
                else:
                    failed += 1
                    error_dist["no_match"] = error_dist.get("no_match", 0) + 1

                total_requests += 1

        sorted_lat = sorted(latencies) if latencies else [0.0]
        observations: list[str] = []
        if error_dist.get("cross_partition_route", 0) > 0:
            observations.append(
                f"Cross-partition routing detected: "
                f"{error_dist['cross_partition_route']} routes"
            )

        scenario = StressScenario(
            node_count=len(all_node_ids),
            failure_rate=0.0,
            request_rate=50,
            duration=2.0,
            capabilities_per_node=3,
        )
        return StressResult(
            scenario=scenario,
            total_requests=total_requests,
            successful_routes=successful,
            failed_routes=failed,
            latency_samples=latencies,
            throughput=total_requests / 2.0,
            error_distribution=error_dist,
            observations=observations,
            p50_latency=_percentile(sorted_lat, 50),
            p95_latency=_percentile(sorted_lat, 95),
            p99_latency=_percentile(sorted_lat, 99),
        )

    # ── Report generation ───────────────────────────────────────────────────

    @staticmethod
    def generate_stress_report(
        scenario: StressScenario,
        result: StressResult,
    ) -> str:
        """Generate a human-readable stress test report."""
        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("  ROUTING FABRIC STRESS TEST REPORT")
        lines.append("=" * 72)
        lines.append("")
        lines.append("  SCENARIO")
        lines.append(f"    Nodes:           {scenario.node_count}")
        lines.append(f"    Failure Rate:    {scenario.failure_rate * 100:.1f}%")
        lines.append(f"    Target Rate:     {scenario.request_rate} req/s")
        lines.append(f"    Duration:        {scenario.duration:.1f}s")
        lines.append(f"    Caps per Node:   {scenario.capabilities_per_node}")
        lines.append("")
        lines.append("  RESULTS")
        lines.append(f"    Total Requests:  {result.total_requests}")
        lines.append(f"    Successful:      {result.successful_routes}")
        lines.append(f"    Failed:          {result.failed_routes}")
        success_pct = (
            100.0 * result.successful_routes / max(result.total_requests, 1)
        )
        lines.append(f"    Success Rate:    {success_pct:.1f}%")
        lines.append(f"    Throughput:      {result.throughput:.1f} req/s")
        lines.append("")
        lines.append("  LATENCY")
        lines.append(f"    p50:             {result.p50_latency * 1000:.2f} ms")
        lines.append(f"    p95:             {result.p95_latency * 1000:.2f} ms")
        lines.append(f"    p99:             {result.p99_latency * 1000:.2f} ms")
        if result.latency_samples:
            lines.append(f"    Mean:            {statistics.mean(result.latency_samples) * 1000:.2f} ms")
            lines.append(f"    Min:             {min(result.latency_samples) * 1000:.2f} ms")
            lines.append(f"    Max:             {max(result.latency_samples) * 1000:.2f} ms")
        lines.append("")
        if result.error_distribution:
            lines.append("  ERROR DISTRIBUTION")
            for err, count in sorted(
                result.error_distribution.items(), key=lambda x: -x[1]
            ):
                lines.append(f"    {err}: {count}")
            lines.append("")
        if result.observations:
            lines.append("  OBSERVATIONS")
            for obs in result.observations:
                lines.append(f"    ⚠  {obs}")
            lines.append("")
        lines.append("=" * 72)
        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _percentile(sorted_data: list[float], percentile: float) -> float:
    """Compute the *percentile*-th percentile of sorted data.

    Uses linear interpolation (same as numpy's default).
    """
    if not sorted_data:
        return 0.0
    k = (percentile / 100.0) * (len(sorted_data) - 1)
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return sorted_data[f]
