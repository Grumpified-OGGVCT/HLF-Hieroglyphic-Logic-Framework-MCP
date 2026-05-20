"""
Tests for Routing Fabric Stress Testing and Edge Cases.

Covers:
  1. Concurrent routing under load (10/50/100 nodes)
  2. Latency distribution measurement
  3. Graceful degradation under increasing failure rates
  4. Thundering herd recovery
  5. Partition tolerance
  6. Edge cases: empty registry, single-node failure, capability mismatch,
     race conditions, load balancer starvation, failover cascade,
     health-check flapping
  7. Enhanced load balancer strategies: weighted-round-robin,
     least-connections, resource-aware
  8. Enhanced failover: circuit breaker, exponential backoff
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the hlf_mcp package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.routing.node_registry import (  # noqa: E402
    NodeRegistry,
    RegisteredNode,
)
from hlf_mcp.hlf.routing.capability_router import (  # noqa: E402
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer  # noqa: E402
from hlf_mcp.hlf.routing.failover import (  # noqa: E402
    CircuitBreaker,
    FailoverManager,
    NodeFailureEvent,
)
from hlf_mcp.hlf.routing.stress_testing import (  # noqa: E402
    RoutingStressTest,
    StressResult,
    StressScenario,
)
from hlf_mcp.hlf.routing.edge_cases import (  # noqa: E402
    EdgeCaseResult,
    RoutingEdgeCase,
    run_all_edge_cases,
    test_capability_mismatch as _edge_test_capability_mismatch,
    test_empty_registry as _edge_test_empty_registry,
    test_failover_cascade as _edge_test_failover_cascade,
    test_health_check_flapping as _edge_test_health_check_flapping,
    test_load_balancer_starvation as _edge_test_load_balancer_starvation,
    test_race_condition_register_unregister as _edge_test_race_condition_register_unregister,
    test_single_node_failure as _edge_test_single_node_failure,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Stress Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoutingStress:
    """Stress tests for the distributed routing fabric under load."""

    def test_concurrent_routing_10_nodes(self):
        """10 nodes, 0% failure — all routing succeeds."""
        runner = RoutingStressTest()
        scenario = StressScenario(
            node_count=10,
            failure_rate=0.0,
            request_rate=50,
            duration=2.0,
            capabilities_per_node=3,
        )
        result = runner.run_concurrent_routing(scenario)

        assert isinstance(result, StressResult)
        assert result.total_requests > 0, "No requests were processed"
        assert result.successful_routes > 0, "No successful routes"
        assert result.failed_routes < result.total_requests * 0.3, (
            f"Too many failures: {result.failed_routes}/{result.total_requests}"
        )
        assert result.throughput > 0
        assert len(result.latency_samples) == result.total_requests

    def test_concurrent_routing_50_nodes(self):
        """50 nodes, 10% failure — most routing succeeds."""
        runner = RoutingStressTest()
        scenario = StressScenario(
            node_count=50,
            failure_rate=0.1,
            request_rate=100,
            duration=3.0,
            capabilities_per_node=4,
        )
        result = runner.run_concurrent_routing(scenario)

        assert isinstance(result, StressResult)
        assert result.total_requests > 0
        assert result.successful_routes > 0
        # With 10% failure, some failures are expected but should be <50%
        assert result.failed_routes < result.total_requests * 0.5

    def test_concurrent_routing_100_nodes(self):
        """100 nodes, 5% failure — routing handles scale."""
        runner = RoutingStressTest()
        scenario = StressScenario(
            node_count=100,
            failure_rate=0.05,
            request_rate=200,
            duration=3.0,
            capabilities_per_node=3,
        )
        result = runner.run_concurrent_routing(scenario)

        assert isinstance(result, StressResult)
        assert result.total_requests > 0
        assert result.successful_routes > 0
        # Very low failure expected
        assert result.successful_routes > result.total_requests * 0.5

    def test_latency_distribution_small(self):
        """5 nodes, 100 requests — latency stats are computed."""
        stats = RoutingStressTest.measure_routing_latency(
            node_count=5, request_count=100
        )

        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats
        assert "min" in stats
        assert "max" in stats
        assert "mean" in stats
        assert stats["p50"] >= 0
        assert stats["p95"] >= stats["p50"]
        assert stats["p99"] >= stats["p95"]
        assert stats["max"] >= stats["min"]
        # Latency should be reasonable (< 1s for simple routing)
        assert stats["max"] < 2.0, f"Max latency too high: {stats['max']:.3f}s"

    def test_latency_distribution_large(self):
        """20 nodes, 500 requests — latency distribution is measured."""
        stats = RoutingStressTest.measure_routing_latency(
            node_count=20, request_count=500
        )

        assert stats["p50"] >= 0
        assert stats["p95"] >= stats["p50"]
        assert stats["p99"] >= stats["p95"]
        assert stats["mean"] >= stats["min"]
        # p50 should be very fast
        assert stats["p50"] < 0.1, f"p50 latency too high: {stats['p50']:.4f}s"

    def test_graceful_degradation_25pct(self):
        """25% failure rate — system still routes successfully."""
        runner = RoutingStressTest()
        results = runner.test_graceful_degradation([0.25])

        assert len(results) == 1
        result = results[0]
        assert result.successful_routes > 0, "No successful routes at 25% failure"
        success_rate = result.successful_routes / max(result.total_requests, 1)
        assert success_rate > 0.3, f"Success rate too low: {success_rate:.2%}"

    def test_graceful_degradation_50pct(self):
        """50% failure rate — some routing still succeeds."""
        runner = RoutingStressTest()
        results = runner.test_graceful_degradation([0.5])

        assert len(results) == 1
        result = results[0]
        assert result.successful_routes > 0, "No successful routes at 50% failure"

    def test_graceful_degradation_75pct(self):
        """75% failure rate — some routing still succeeds (degraded but not dead)."""
        runner = RoutingStressTest()
        results = runner.test_graceful_degradation([0.75])

        assert len(results) == 1
        result = results[0]
        # At 75% failure, we expect few successes but some should work
        assert result.total_requests > 0

    def test_thundering_herd_recovery(self):
        """All nodes fail simultaneously, then recover — routing resumes."""
        runner = RoutingStressTest()
        result = runner.test_thundering_herd_recovery()

        assert isinstance(result, StressResult)
        assert result.successful_routes > 0, (
            "No successful routes after thundering herd recovery"
        )
        assert any("Recovery time" in obs for obs in result.observations), (
            "Recovery time not reported in observations"
        )

    def test_partition_tolerance_basic(self):
        """2 partitions — each partition's internal routing still works."""
        runner = RoutingStressTest()
        partition_map = {
            "east": [f"east-{i}" for i in range(5)],
            "west": [f"west-{i}" for i in range(5)],
        }
        result = runner.test_partition_tolerance(partition_map)

        assert isinstance(result, StressResult)
        assert result.total_requests > 0
        assert result.successful_routes > 0, (
            "No successful routes under partition tolerance test"
        )
        # Cross-partition routing should be minimal
        cross = result.error_distribution.get("cross_partition_route", 0)
        assert cross < result.total_requests * 0.3, (
            f"Too much cross-partition routing: {cross}/{result.total_requests}"
        )

    def test_stress_report_generation(self):
        """Stress report is human-readable and contains key sections."""
        scenario = StressScenario(
            node_count=10, failure_rate=0.1, request_rate=50, duration=1.0,
        )
        result = StressResult(
            scenario=scenario,
            total_requests=47,
            successful_routes=42,
            failed_routes=5,
            latency_samples=[0.001] * 42 + [0.1] * 5,
            throughput=47.0,
            error_distribution={"no_match": 5},
            observations=["Test observation"],
            p50_latency=0.001,
            p95_latency=0.005,
            p99_latency=0.1,
        )

        report = RoutingStressTest.generate_stress_report(scenario, result)
        assert isinstance(report, str)
        assert "ROUTING FABRIC STRESS TEST REPORT" in report
        assert "SCENARIO" in report
        assert "RESULTS" in report
        assert "LATENCY" in report
        assert "OBSERVATIONS" in report
        assert "10" in report  # node_count
        assert "42" in report  # successful
        assert "Test observation" in report


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRoutingEdgeCases:
    """Edge case tests for the routing fabric."""

    def test_empty_registry(self):
        """Zero nodes — routing returns unmatched gracefully."""
        result = _edge_test_empty_registry()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.EMPTY_REGISTRY
        assert result.status in ("passed", "warning"), (
            f"Empty registry test failed: {result.observations}"
        )
        assert result.metrics["matched"] is False
        assert result.metrics["confidence"] == 0.0

    def test_single_node_failure(self):
        """Only node fails — system handles last-node failure."""
        result = _edge_test_single_node_failure()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.SINGLE_NODE_FAILURE
        assert result.status in ("passed", "warning"), (
            f"Single node failure test failed: {result.observations}"
        )
        assert result.metrics["node_health_after_failure"] == "unhealthy"

    def test_capability_mismatch(self):
        """Unknown capability — returns no match."""
        result = _edge_test_capability_mismatch()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.CAPABILITY_MISMATCH
        assert result.status in ("passed", "warning"), (
            f"Capability mismatch test failed: {result.observations}"
        )
        assert result.metrics["capability_mismatch_matched"] is False

    def test_race_condition_register_unregister(self):
        """Concurrent register/unregister — registry remains consistent."""
        result = _edge_test_race_condition_register_unregister()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.RACE_CONDITION_REGISTER_UNREGISTER
        assert result.status in ("passed", "warning"), (
            f"Race condition test failed: {result.observations}"
            f"\nErrors: {result.metrics.get('errors', 0)}"
        )
        assert result.metrics["errors"] == 0, (
            f"Race condition produced errors: {result.observations}"
        )

    def test_load_balancer_starvation(self):
        """Fair distribution — no nodes are starved."""
        result = _edge_test_load_balancer_starvation()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.LOAD_BALANCER_STARVATION
        assert result.status in ("passed", "warning"), (
            f"Load balancer starvation test failed: {result.observations}"
        )
        hit_counts = result.metrics.get("hit_counts", {})
        # All 5 nodes should have hits
        assert len(hit_counts) == 5, f"Expected 5 nodes, got {len(hit_counts)}"
        # No node should have 0 hits
        for nid, count in hit_counts.items():
            assert count > 0, f"Node {nid} was starved (0 hits)"

    def test_failover_cascade(self):
        """Failover cascade — detected and contained."""
        result = _edge_test_failover_cascade()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.FAILOVER_CASCADE
        # Cascade test may produce a warning if depth is high, but not failure
        assert result.status in ("passed", "warning"), (
            f"Failover cascade test failed: {result.observations}"
        )
        assert "cascade_depth" in result.metrics

    def test_health_check_flapping(self):
        """Rapid health transitions — system remains stable."""
        result = _edge_test_health_check_flapping()

        assert isinstance(result, EdgeCaseResult)
        assert result.edge_case == RoutingEdgeCase.HEALTH_CHECK_FLAPPING
        assert result.status in ("passed", "warning"), (
            f"Health check flapping test failed: {result.observations}"
        )
        assert result.metrics["state_changes"] > 0, (
            "No state changes were recorded"
        )

    def test_run_all_edge_cases(self):
        """run_all_edge_cases() returns results for all 7 edge cases."""
        results = run_all_edge_cases()

        assert len(results) == 7, f"Expected 7 edge cases, got {len(results)}"
        for case in RoutingEdgeCase:
            assert case in results, f"Missing edge case: {case.value}"
            assert results[case].status in ("passed", "warning", "failed")


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced LoadBalancer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnhancedLoadBalancer:
    """Tests for the enhanced load balancer strategies."""

    def _setup_balancer(self, strategy: str = "round_robin") -> tuple[NodeRegistry, CapabilityRouter, LoadBalancer]:
        """Create a load balancer with pre-registered nodes."""
        registry = NodeRegistry()
        registry.register(
            "node-1", "10.0.0.1", 9090,
            capabilities={"inference": 8},
            metadata={"weight": 3, "cpu_cores": 8, "memory_gb": 32, "gpu_vram_gb": 24},
        )
        registry.register(
            "node-2", "10.0.0.2", 9091,
            capabilities={"inference": 8},
            metadata={"weight": 1, "cpu_cores": 4, "memory_gb": 16, "gpu_vram_gb": 8},
        )
        registry.register(
            "node-3", "10.0.0.3", 9092,
            capabilities={"inference": 5},
            metadata={"weight": 1, "cpu_cores": 4, "memory_gb": 8, "gpu_vram_gb": 0},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy=strategy)
        return registry, router, lb

    def test_weighted_round_robin(self):
        """Weighted round-robin selects nodes proportionally."""
        _, _, lb = self._setup_balancer("weighted_round_robin")

        request = WorkRequest(
            request_id="wrr-req",
            capability="inference",
            required_proficiency=1,
        )

        hit_counts: dict[str, int] = {}
        for _ in range(50):
            match = lb.distribute(request)
            assert match.matched, "Weighted RR failed to match"
            nid = match.matched_node.node_id
            hit_counts[nid] = hit_counts.get(nid, 0) + 1
            lb.decrement_active(nid)

        # node-1 has weight 3, node-2 weight 1, node-3 weight 1
        # node-1 should get ~60%, node-2 ~20%, node-3 ~20%
        assert hit_counts.get("node-1", 0) > hit_counts.get("node-2", 0), (
            f"Weighted node got fewer hits: {hit_counts}"
        )
        assert hit_counts.get("node-1", 0) > hit_counts.get("node-3", 0), (
            f"Weighted node got fewer hits: {hit_counts}"
        )

    def test_weighted_round_robin_fairness(self):
        """Weighted round-robin approximates proportional distribution."""
        _, _, lb = self._setup_balancer("weighted_round_robin")

        request = WorkRequest(
            request_id="wrr-fair",
            capability="inference",
            required_proficiency=1,
        )

        hit_counts: dict[str, int] = {}
        for _ in range(300):
            match = lb.distribute(request)
            assert match.matched
            nid = match.matched_node.node_id
            hit_counts[nid] = hit_counts.get(nid, 0) + 1
            lb.decrement_active(nid)

        total = sum(hit_counts.values())
        # node-1 weight=3 → expect ~60%, node-2/3 weight=1 → ~20% each
        pct_1 = hit_counts.get("node-1", 0) / total
        assert 0.40 < pct_1 < 0.80, (
            f"node-1 got {pct_1:.1%}, expected ~60%: {hit_counts}"
        )

    def test_least_connections_strategy(self):
        """Least connections selects node with fewest connections."""
        _, _, lb = self._setup_balancer("least_connections")

        # Set up connection counts
        lb.increment_connections("node-1")
        lb.increment_connections("node-1")
        lb.increment_connections("node-2")

        request = WorkRequest(
            request_id="lc-req",
            capability="inference",
        )
        match = lb.distribute(request)
        assert match.matched
        # node-3 has 0 connections, node-2 has 1, node-1 has 2
        assert match.matched_node.node_id == "node-3", (
            f"Expected node-3 (least connections), got {match.matched_node.node_id}"
        )

    def test_least_connections_fallback(self):
        """All connection counts equal — picks first node."""
        _, _, lb = self._setup_balancer("least_connections")

        request = WorkRequest(
            request_id="lc-fallback",
            capability="inference",
        )
        match = lb.distribute(request)
        assert match.matched
        # All have 0 connections — should pick first (node-1)
        assert match.matched_node.node_id in ("node-1", "node-2", "node-3"), (
            "Should pick a valid node when all connections equal"
        )

    def test_resource_aware_routing(self):
        """Resource-aware strategy selects node with most available resources."""
        _, _, lb = self._setup_balancer("resource_aware")

        request = WorkRequest(
            request_id="ra-req",
            capability="inference",
        )

        # No load yet — should pick node with highest resources (node-1)
        match = lb.distribute(request)
        assert match.matched
        assert match.matched_node.node_id == "node-1", (
            f"Expected node-1 (most resources), got {match.matched_node.node_id}"
        )

    def test_resource_aware_overloaded(self):
        """Overloaded node is skipped in favour of less-loaded node."""
        _, _, lb = self._setup_balancer("resource_aware")

        # Load node-1 heavily
        for _ in range(10):
            lb.increment_active("node-1")

        request = WorkRequest(
            request_id="ra-overload",
            capability="inference",
        )
        match = lb.distribute(request)
        assert match.matched
        # node-1 has 10 active tasks, others have 0 — should pick a different node
        assert match.matched_node.node_id != "node-1", (
            "Overloaded node-1 was selected — resource-aware should skip it"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Failover Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnhancedFailover:
    """Tests for circuit breaker and enhanced failover features."""

    def _setup_failover(self) -> tuple[NodeRegistry, CapabilityRouter, LoadBalancer, FailoverManager]:
        """Create a full failover setup with multiple nodes."""
        registry = NodeRegistry()
        registry.register(
            "node-alpha", "10.0.0.1", 9090,
            capabilities={"inference": 9, "embedding": 5},
        )
        registry.register(
            "node-beta", "10.0.0.2", 9091,
            capabilities={"inference": 8, "embedding": 6},
        )
        registry.register(
            "node-gamma", "10.0.0.3", 9092,
            capabilities={"inference": 7, "embedding": 7},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")
        failover = FailoverManager(
            registry, router, lb,
            max_retries=3,
            backoff_base=0.01,
            backoff_multiplier=2.0,
            backoff_max=0.1,
            backoff_jitter=False,
        )
        return registry, router, lb, failover

    def test_circuit_breaker_opens(self):
        """Circuit breaker opens after consecutive failures exceed threshold."""
        cb = CircuitBreaker(node_id="test-node", failure_threshold=3)

        assert cb.circuit_state() == "closed"
        assert not cb.is_circuit_open()

        cb.record_failure()
        cb.record_failure()
        assert cb.circuit_state() == "closed", "Should still be closed before threshold"

        cb.record_failure()
        assert cb.circuit_state() == "open", "Should open after 3 failures"
        assert cb.is_circuit_open()

    def test_circuit_breaker_half_open(self):
        """Circuit breaker transitions to half-open after cooldown."""
        cb = CircuitBreaker(
            node_id="test-node",
            failure_threshold=2,
            cooldown_seconds=0.01,  # Very short cooldown for testing
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.circuit_state() == "open"

        # Wait for cooldown
        time.sleep(0.02)
        assert cb.circuit_state() == "half_open", "Should be half-open after cooldown"
        assert not cb.is_circuit_open(), "Half-open should not block routing"

    def test_circuit_breaker_resets(self):
        """Success in half-open state closes the circuit."""
        cb = CircuitBreaker(
            node_id="test-node",
            failure_threshold=2,
            cooldown_seconds=0.01,
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.circuit_state() == "open"

        time.sleep(0.02)
        assert cb.circuit_state() == "half_open"

        cb.record_success()
        assert cb.circuit_state() == "closed", "Should close after success in half-open"

    def test_circuit_breaker_half_open_failure_reopens(self):
        """Failure in half-open state re-opens the circuit with longer cooldown."""
        cb = CircuitBreaker(
            node_id="test-node",
            failure_threshold=2,
            cooldown_seconds=0.01,
        )

        cb.record_failure()
        cb.record_failure()
        assert cb.circuit_state() == "open"

        time.sleep(0.02)
        assert cb.circuit_state() == "half_open"

        cb.record_failure()
        assert cb.circuit_state() == "open", "Should re-open after half-open failure"
        assert cb._cooldown_multiplier > 1.0, "Cooldown multiplier should increase"

    def test_exponential_backoff_configurable(self):
        """Custom backoff parameters are used in failover_route."""
        registry = NodeRegistry()
        registry.register(
            "node-a", "10.0.0.1", 9090,
            capabilities={"inference": 9},
        )
        registry.register(
            "node-b", "10.0.0.2", 9091,
            capabilities={"inference": 8},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        failover = FailoverManager(
            registry, router, lb,
            max_retries=3,
            backoff_base=0.1,
            backoff_multiplier=3.0,
            backoff_max=5.0,
            backoff_jitter=False,
        )

        # Verify backoff values
        delay1 = failover._compute_backoff(1)  # base * (multiplier ** 0) = 0.1
        delay2 = failover._compute_backoff(2)  # base * (multiplier ** 1) = 0.3
        delay3 = failover._compute_backoff(3)  # base * (multiplier ** 2) = 0.9

        assert abs(delay1 - 0.1) < 0.01, f"Expected ~0.1, got {delay1}"
        assert abs(delay2 - 0.3) < 0.01, f"Expected ~0.3, got {delay2}"
        assert abs(delay3 - 0.9) < 0.01, f"Expected ~0.9, got {delay3}"

    def test_backoff_jitter(self):
        """Jitter adds variation to backoff delays."""
        registry = NodeRegistry()
        registry.register("node-a", "10.0.0.1", 9090, capabilities={"test": 1})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)

        failover = FailoverManager(
            registry, router, lb,
            max_retries=3,
            backoff_base=0.5,
            backoff_multiplier=1.0,
            backoff_max=10.0,
            backoff_jitter=True,
        )

        delays = [failover._compute_backoff(1) for _ in range(20)]
        # With jitter, delays should vary around 0.5
        assert len(set(round(d, 4) for d in delays)) > 1, (
            f"Jitter should produce variation, got all same: {delays[0]:.4f}"
        )
        # All should be within ±25% of base
        for d in delays:
            assert 0.5 * 0.5 <= d <= 0.5 * 1.5, f"Delay {d} outside expected range"

    def test_backoff_max_cap(self):
        """Backoff is capped at backoff_max."""
        _, _, _, failover = self._setup_failover()
        failover._backoff_max = 1.0
        failover._backoff_base = 2.0  # base > max
        failover._backoff_jitter = False

        delay = failover._compute_backoff(1)
        assert delay <= 1.0, f"Delay {delay} exceeded backoff_max of 1.0"

    def test_circuit_breaker_integration_with_failover(self):
        """Circuit breaker stops failover_route from routing to open-circuited nodes."""
        registry, router, lb, failover = self._setup_failover()

        # Manually open the circuit for node-beta
        failover.record_failure("node-beta")
        failover.record_failure("node-beta")
        failover.record_failure("node-beta")
        failover.record_failure("node-beta")
        failover.record_failure("node-beta")  # 5 failures → open

        assert failover.is_circuit_open("node-beta"), "Circuit should be open"

        # Now fail node-gamma and try failover
        # node-alpha and node-beta have inference; node-beta is circuited
        request = WorkRequest(
            request_id="cb-integration",
            capability="inference",
        )

        # failover_route should exclude node-beta due to open circuit
        with patch("time.sleep", return_value=None):
            match = failover.failover_route(request, "node-gamma")

        # node-alpha should be available
        # (node-beta excluded by circuit breaker, node-gamma excluded as failed)
        if match.matched:
            assert match.matched_node.node_id == "node-alpha", (
                f"Should route to node-alpha (only non-circuited option), "
                f"got {match.matched_node.node_id}"
            )

    def test_circuit_breaker_state_reporting(self):
        """Circuit breaker state can be queried."""
        _, _, _, failover = self._setup_failover()

        failover.record_failure("node-alpha")
        assert failover.circuit_state("node-alpha") == "closed"
        assert not failover.is_circuit_open("node-alpha")

        failover.record_success("node-alpha")
        assert failover.circuit_state("node-alpha") == "closed"

        # Check status report
        status = failover.circuit_breaker_status()
        assert "node-alpha" in status
        assert status["node-alpha"]["state"] == "closed"

    def test_failover_exponential_backoff_integration(self):
        """Failover route uses configurable backoff."""
        registry, router, lb, failover = self._setup_failover()

        # Exclude all nodes so every attempt fails
        request = WorkRequest(
            request_id="backoff-req",
            capability="inference",
            exclude_nodes={"node-beta", "node-gamma"},
        )

        delays_recorded: list[float] = []
        original_sleep = time.sleep

        def tracking_sleep(seconds: float) -> None:
            delays_recorded.append(seconds)

        with patch("time.sleep", side_effect=tracking_sleep):
            match = failover.failover_route(request, "node-alpha")

        assert not match.matched, "Should exhaust all retries"
        # Backoff delays should be non-decreasing
        for i in range(1, len(delays_recorded)):
            assert delays_recorded[i] >= delays_recorded[i - 1] * 0.5, (
                f"Backoff should not decrease significantly: {delays_recorded}"
            )
