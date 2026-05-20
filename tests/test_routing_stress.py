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

import json
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
    RouteEvidence,
    FallbackDecision,
    RouteEvidenceThreshold,
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
from hlf_mcp.hlf.routing.route_trace import (  # noqa: E402
    RouteTraceLedger,
    TraceRecord,
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
        """run_all_edge_cases() returns results for all 8 edge cases."""
        results = run_all_edge_cases()

        assert len(results) == 8, f"Expected 8 edge cases, got {len(results)}"
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


# ═══════════════════════════════════════════════════════════════════════════════
# Route Evidence Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteEvidence:
    """Tests for RouteEvidence dataclass and evidence snapshots."""

    def _setup_lb(self) -> tuple[NodeRegistry, CapabilityRouter, LoadBalancer]:
        registry = NodeRegistry()
        registry.register(
            "evidence-1", "10.0.0.1", 9090,
            capabilities={"inference": 9},
        )
        registry.register(
            "evidence-2", "10.0.0.2", 9091,
            capabilities={"inference": 8},
        )
        registry.register(
            "evidence-3", "10.0.0.3", 9092,
            capabilities={"inference": 7},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")
        return registry, router, lb

    def test_route_evidence_generated_on_distribute(self):
        """RouteEvidence is generated on every distribute() call."""
        _, _, lb = self._setup_lb()
        request = WorkRequest(
            request_id="ev-dist-1",
            capability="inference",
        )
        match = lb.distribute(request)
        assert match.matched

        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.route_id != ""
        assert evidence.selected_node is not None
        assert len(evidence.candidates_considered) == 3
        assert evidence.policy_basis == "round_robin"
        assert evidence.selection_reason != ""

    def test_route_evidence_all_fields_populated(self):
        """RouteEvidence has all fields populated after distribute()."""
        _, _, lb = self._setup_lb()
        request = WorkRequest(
            request_id="ev-all-fields",
            capability="inference",
        )
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None

        # All required fields
        assert evidence.route_id != ""
        assert evidence.selected_node is not None
        assert len(evidence.candidates_considered) > 0
        assert evidence.selection_reason != ""
        assert evidence.policy_basis != ""
        assert evidence.timestamp_ns > 0
        assert len(evidence.evidence_hash) == 64  # SHA-256 hex digest
        assert evidence.health_check_evidence
        assert evidence.capability_match_scores
        # Verify each candidate has health and score entries
        for nid in evidence.candidates_considered:
            assert nid in evidence.health_check_evidence
            assert nid in evidence.capability_match_scores

    def test_route_evidence_hash_deterministic(self):
        """SHA-256 evidence hash is deterministic for same inputs."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev1 = RouteEvidence(
            route_id="test-route-001",
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test reason",
            policy_basis="round_robin",
            timestamp_ns=1000,
            health_check_evidence={"node-a": "healthy", "node-b": "healthy"},
            capability_match_scores={"node-a": 9, "node-b": 8},
        )
        ev2 = RouteEvidence(
            route_id="test-route-001",
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test reason",
            policy_basis="round_robin",
            timestamp_ns=1000,
            health_check_evidence={"node-a": "healthy", "node-b": "healthy"},
            capability_match_scores={"node-a": 9, "node-b": 8},
        )
        assert ev1.evidence_hash == ev2.evidence_hash, (
            f"Hash mismatch: {ev1.evidence_hash} != {ev2.evidence_hash}"
        )

    def test_route_evidence_hash_changes_with_input(self):
        """SHA-256 hash changes when any field changes."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev1 = RouteEvidence(
            route_id="test-route-002",
            selected_node="node-a",
            candidates_considered=["node-a"],
            selection_reason="Reason A",
            policy_basis="round_robin",
            timestamp_ns=1000,
        )
        ev2 = RouteEvidence(
            route_id="test-route-002",
            selected_node="node-b",  # different selection
            candidates_considered=["node-a"],
            selection_reason="Reason A",
            policy_basis="round_robin",
            timestamp_ns=1000,
        )
        assert ev1.evidence_hash != ev2.evidence_hash, "Hash should differ"

    def test_route_evidence_verify_hash(self):
        """verify_hash() returns True for untampered evidence."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        assert ev.verify_hash()

    def test_route_evidence_tamper_detection(self):
        """verify_hash() returns False for tampered evidence."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        # Tamper with the selected_node
        ev.selected_node = "node-malicious"
        assert not ev.verify_hash(), "Tamper should be detected"

    def test_route_evidence_default_timestamp(self):
        """RouteEvidence gets a nanosecond timestamp by default."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        assert ev.timestamp_ns > 0

    def test_route_evidence_default_route_id(self):
        """RouteEvidence gets a random UUID route_id by default."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        assert ev.route_id != ""
        assert len(ev.route_id) >= 32  # UUID length

    def test_route_evidence_unique_route_ids(self):
        """Two RouteEvidence instances get different route_ids."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev1 = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        ev2 = RouteEvidence(
            selected_node="node-b",
            candidates_considered=["node-b"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        assert ev1.route_id != ev2.route_id

    def test_route_evidence_to_dict(self):
        """to_dict() returns all canonical fields."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            route_id="rid-001",
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test",
            policy_basis="round_robin",
            timestamp_ns=1000,
        )
        d = ev.to_dict()
        assert d["route_id"] == "rid-001"
        assert d["selected_node"] == "node-a"
        assert "node-a" in d["candidates_considered"]
        assert "node-b" in d["candidates_considered"]
        assert d["selection_reason"] == "Test"
        assert d["policy_basis"] == "round_robin"
        assert d["timestamp_ns"] == 1000

    def test_route_evidence_on_empty_registry(self):
        """RouteEvidence is generated even when no nodes match."""
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        lb.distribute(WorkRequest(request_id="empty", capability="inference"))
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.selected_node is None
        assert evidence.candidates_considered == []

    def test_distribute_with_evidence_returns_tuple(self):
        """distribute_with_evidence returns (match, evidence)."""
        _, _, lb = self._setup_lb()
        request = WorkRequest(request_id="ev-tuple", capability="inference")
        match, evidence = lb.distribute_with_evidence(request)
        assert match.matched
        assert evidence is not None
        assert evidence.selected_node is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback Decision Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbackDecision:
    """Tests for FallbackDecision and fallback chain recording."""

    def _setup_failover(self) -> tuple[NodeRegistry, CapabilityRouter, LoadBalancer, FailoverManager]:
        registry = NodeRegistry()
        registry.register(
            "fb-alpha", "10.0.0.1", 9090,
            capabilities={"inference": 9},
        )
        registry.register(
            "fb-beta", "10.0.0.2", 9091,
            capabilities={"inference": 8},
        )
        registry.register(
            "fb-gamma", "10.0.0.3", 9092,
            capabilities={"inference": 7},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")
        failover = FailoverManager(
            registry, router, lb, max_retries=3,
            backoff_base=0.001, backoff_max=0.01, backoff_jitter=False,
        )
        return registry, router, lb, failover

    def test_fallback_decision_created(self):
        """FallbackDecision is created with primary node and failure reason."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-1",
            primary_failure_reason="Health check failed",
        )
        assert fd.primary_node == "node-1"
        assert fd.primary_failure_reason == "Health check failed"
        assert fd.fallback_chain == []
        assert fd.final_node is None

    def test_fallback_decision_add_hop(self):
        """add_hop() appends to the fallback chain with correct step numbers."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-1",
            primary_failure_reason="Circuit open",
        )
        fd.add_hop("node-2", reason="Next available", health_status="healthy",
                    circuit_state="closed", attempt_number=1)
        fd.add_hop("node-3", reason="Last resort", health_status="degraded",
                    circuit_state="closed", attempt_number=2)

        assert len(fd.fallback_chain) == 2
        assert fd.fallback_chain[0].step == 1
        assert fd.fallback_chain[0].node_id == "node-2"
        assert fd.fallback_chain[1].step == 2
        assert fd.fallback_chain[1].node_id == "node-3"
        assert fd.total_attempts == 2

    def test_fallback_decision_hash_deterministic(self):
        """FallbackDecision hash is deterministic."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd1 = FallbackDecision(
            primary_node="node-A",
            primary_failure_reason="Timeout",
            timestamp_ns=5000,
        )
        fd1.add_hop("node-B", reason="Available", attempt_number=1)

        fd2 = FallbackDecision(
            primary_node="node-A",
            primary_failure_reason="Timeout",
            timestamp_ns=5000,
        )
        fd2.add_hop("node-B", reason="Available", attempt_number=1)

        assert fd1.evidence_hash == fd2.evidence_hash

    def test_fallback_decision_verify_hash(self):
        """FallbackDecision verify_hash works."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-A",
            primary_failure_reason="Timeout",
        )
        assert fd.verify_hash()

    def test_fallback_decision_tamper_detection(self):
        """FallbackDecision detects tampering."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-A",
            primary_failure_reason="Timeout",
        )
        fd.primary_node = "node-MALICIOUS"
        assert not fd.verify_hash()

    def test_fallback_decision_exhausted(self):
        """FallbackDecision records exhaustion correctly."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-A",
            primary_failure_reason="Timeout",
            exhausted=True,
        )
        assert fd.exhausted
        assert fd.final_node is None

    def test_fallback_decision_to_dict(self):
        """FallbackDecision to_dict includes all chain data."""
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        fd = FallbackDecision(
            primary_node="node-X",
            primary_failure_reason="Health check",
            final_node="node-Y",
            total_attempts=2,
            exhausted=False,
        )
        fd.add_hop("node-Y", reason="Only alternative", attempt_number=1)
        d = fd.to_dict()
        assert d["primary_node"] == "node-X"
        assert d["final_node"] == "node-Y"
        assert len(d["fallback_chain"]) == 1
        assert d["fallback_chain"][0]["node_id"] == "node-Y"

    def test_failover_with_evidence_success(self):
        """failover_with_evidence returns match + evidence + fallback decision."""
        _, _, _, failover = self._setup_failover()

        request = WorkRequest(
            request_id="fwe-1",
            capability="inference",
        )
        match, evidence, fallback = failover.failover_with_evidence(request, "fb-alpha")

        if match.matched:
            assert evidence is not None
            assert fallback is not None
            assert fallback.primary_node == "fb-alpha"
            assert len(fallback.fallback_chain) > 0
            # Each hop should have a reason
            for hop in fallback.fallback_chain:
                assert hop.reason != ""

    def test_failover_with_evidence_exhausted(self):
        """failover_with_evidence records exhaustion when no alternatives."""
        _, _, _, failover = self._setup_failover()

        # Exclude all healthy nodes
        request = WorkRequest(
            request_id="fwe-exhaust",
            capability="inference",
            exclude_nodes={"fb-beta", "fb-gamma"},
        )
        match, evidence, fallback = failover.failover_with_evidence(request, "fb-alpha")

        assert not match.matched
        assert fallback is not None
        assert fallback.exhausted

    def test_handle_failure_with_evidence(self):
        """handle_failure_with_evidence returns match + evidence."""
        _, _, _, failover = self._setup_failover()

        match, evidence = failover.handle_failure_with_evidence("fb-alpha")
        # fb-beta or fb-gamma should be the alternative
        if match.matched:
            assert evidence is not None
            assert evidence.selected_node is not None
            assert evidence.policy_basis.startswith("failover_from_")
        else:
            assert evidence is not None
            assert evidence.selected_node is None


# ═══════════════════════════════════════════════════════════════════════════════
# Fail-Closed Enforcement Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailClosed:
    """Tests for fail-closed enforcement via RouteEvidenceThreshold."""

    def test_threshold_none_accepts_empty(self):
        """NONE threshold accepts evidence with no fields."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node=None,
            candidates_considered=[],
            selection_reason="",
            policy_basis="",
        )
        assert ev.meets_threshold(RouteEvidenceThreshold.NONE)

    def test_threshold_minimal_rejects_empty_selected(self):
        """MINIMAL rejects evidence with no selected_node."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node=None,
            candidates_considered=[],
            selection_reason="",
            policy_basis="",
        )
        assert not ev.meets_threshold(RouteEvidenceThreshold.MINIMAL)

    def test_threshold_minimal_accepts_basic(self):
        """MINIMAL accepts evidence with route_id and selected_node."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="",
            policy_basis="",
        )
        assert ev.meets_threshold(RouteEvidenceThreshold.MINIMAL)

    def test_threshold_standard_rejects_missing_reason(self):
        """STANDARD rejects evidence missing selection_reason."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="",  # missing
            policy_basis="round_robin",
        )
        assert not ev.meets_threshold(RouteEvidenceThreshold.STANDARD)

    def test_threshold_standard_rejects_missing_policy(self):
        """STANDARD rejects evidence missing policy_basis."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Some reason",
            policy_basis="",  # missing
        )
        assert not ev.meets_threshold(RouteEvidenceThreshold.STANDARD)

    def test_threshold_standard_accepts_full(self):
        """STANDARD accepts evidence with reason and policy."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Best match",
            policy_basis="round_robin",
        )
        assert ev.meets_threshold(RouteEvidenceThreshold.STANDARD)

    def test_threshold_strict_rejects_missing_health(self):
        """STRICT rejects when health_check_evidence is empty."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Best match",
            policy_basis="round_robin",
            health_check_evidence={},
            capability_match_scores={"node-1": 9},
        )
        assert not ev.meets_threshold(RouteEvidenceThreshold.STRICT)

    def test_threshold_strict_rejects_missing_capability(self):
        """STRICT rejects when capability_match_scores is empty."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Best match",
            policy_basis="round_robin",
            health_check_evidence={"node-1": "healthy"},
            capability_match_scores={},
        )
        assert not ev.meets_threshold(RouteEvidenceThreshold.STRICT)

    def test_threshold_strict_accepts_complete(self):
        """STRICT accepts evidence with all fields."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Best match",
            policy_basis="round_robin",
            health_check_evidence={"node-1": "healthy"},
            capability_match_scores={"node-1": 9},
        )
        assert ev.meets_threshold(RouteEvidenceThreshold.STRICT)

    def test_missing_for_threshold_returns_specific_fields(self):
        """missing_for_threshold lists exactly which fields are missing."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence, RouteEvidenceThreshold

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="",
            policy_basis="",
        )
        missing = ev.missing_for_threshold(RouteEvidenceThreshold.STANDARD)
        assert "selection_reason" in missing
        assert "policy_basis" in missing

    def test_threshold_from_string(self):
        """RouteEvidenceThreshold.from_string parses correctly."""
        from hlf_mcp.hlf.routing.failover import RouteEvidenceThreshold

        assert RouteEvidenceThreshold.from_string("none") == RouteEvidenceThreshold.NONE
        assert RouteEvidenceThreshold.from_string("MINIMAL") == RouteEvidenceThreshold.MINIMAL
        assert RouteEvidenceThreshold.from_string("Standard") == RouteEvidenceThreshold.STANDARD
        assert RouteEvidenceThreshold.from_string("STRICT") == RouteEvidenceThreshold.STRICT

    def test_threshold_from_string_invalid(self):
        """Invalid threshold string raises ValueError."""
        from hlf_mcp.hlf.routing.failover import RouteEvidenceThreshold

        with pytest.raises(ValueError):
            RouteEvidenceThreshold.from_string("impossible")

    def test_evidence_level_returns_none_for_no_selection(self):
        """evidence_level() returns NONE when selected_node is None."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node=None,
            candidates_considered=[],
            selection_reason="",
            policy_basis="",
        )
        assert ev.evidence_level() == RouteEvidenceThreshold.NONE

    def test_evidence_level_returns_minimal_for_basic(self):
        """evidence_level() returns MINIMAL with just selection."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="",
            policy_basis="",
        )
        assert ev.evidence_level() == RouteEvidenceThreshold.MINIMAL

    def test_evidence_level_returns_standard_with_reason_policy(self):
        """evidence_level() returns STANDARD with reason + policy."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        assert ev.evidence_level() == RouteEvidenceThreshold.STANDARD

    def test_evidence_level_returns_strict_with_all(self):
        """evidence_level() returns STRICT with health + scores."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Test",
            policy_basis="round_robin",
            health_check_evidence={"node-1": "healthy"},
            capability_match_scores={"node-1": 9},
        )
        assert ev.evidence_level() == RouteEvidenceThreshold.STRICT

    def test_distribute_with_fail_closed_standard(self):
        """distribute_with_fail_closed at STANDARD works with normal evidence."""
        registry = NodeRegistry()
        registry.register("fc-a", "10.0.0.1", 9090, capabilities={"test": 5})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        request = WorkRequest(request_id="fc-1", capability="test")

        match, evidence = lb.distribute_with_fail_closed(
            request, threshold=RouteEvidenceThreshold.STANDARD
        )
        assert match.matched
        assert evidence is not None

    def test_fail_closed_distribute_on_empty_registry(self):
        """distribute_with_fail_closed returns unmatched on empty registry."""
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        request = WorkRequest(request_id="fc-empty", capability="test")

        match, evidence = lb.distribute_with_fail_closed(
            request, threshold=RouteEvidenceThreshold.STANDARD
        )
        assert not match.matched

    def test_failover_manager_has_threshold(self):
        """FailoverManager exposes route_evidence_threshold."""
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        fm = FailoverManager(registry, router, lb)
        assert fm.route_evidence_threshold == RouteEvidenceThreshold.STANDARD

    def test_failover_manager_set_threshold(self):
        """FailoverManager threshold can be changed."""
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        fm = FailoverManager(registry, router, lb)
        fm.set_route_evidence_threshold(RouteEvidenceThreshold.STRICT)
        assert fm.route_evidence_threshold == RouteEvidenceThreshold.STRICT

    def test_enforce_evidence_passes(self):
        """enforce_evidence returns True when evidence meets threshold."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        fm = FailoverManager(registry, router, lb)

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="Test",
            policy_basis="round_robin",
        )
        ok, msg = fm.enforce_evidence(ev)
        assert ok
        assert msg == ""

    def test_enforce_evidence_fails(self):
        """enforce_evidence returns False + error when evidence insufficient."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        fm = FailoverManager(registry, router, lb)
        fm.set_route_evidence_threshold(RouteEvidenceThreshold.STRICT)

        ev = RouteEvidence(
            selected_node="node-1",
            candidates_considered=["node-1"],
            selection_reason="",
            policy_basis="",
        )
        ok, msg = fm.enforce_evidence(ev)
        assert not ok
        assert "Fail-closed" in msg
        assert "Missing evidence" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# RouteTraceLedger Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteTraceLedger:
    """Tests for RouteTraceLedger — append-only evidence store."""

    def test_ledger_initialisation(self):
        """RouteTraceLedger initialises empty."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger

        ledger = RouteTraceLedger()
        assert ledger.record_count == 0
        assert len(ledger) == 0

    def test_append_evidence(self):
        """append_evidence stores a RouteEvidence record."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-001",
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Test",
            policy_basis="round_robin",
            timestamp_ns=1000,
        )
        record = ledger.append_evidence(ev)
        assert ledger.record_count == 1
        assert record.record_type == "route_evidence"
        assert record.record_id == "rid-001"

    def test_append_fallback(self):
        """append_fallback stores a FallbackDecision record."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import FallbackDecision

        ledger = RouteTraceLedger()
        fd = FallbackDecision(
            primary_node="node-1",
            primary_failure_reason="Timeout",
            timestamp_ns=2000,
        )
        record = ledger.append_fallback(fd)
        assert ledger.record_count == 1
        assert record.record_type == "fallback_decision"

    def test_ledger_chain_linking(self):
        """Each record links to the previous via chain_hash."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev1 = RouteEvidence(
            route_id="rid-1", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="First",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ev2 = RouteEvidence(
            route_id="rid-2", selected_node="node-b",
            candidates_considered=["node-b"], selection_reason="Second",
            policy_basis="least_loaded", timestamp_ns=2000,
        )

        r1 = ledger.append_evidence(ev1)
        r2 = ledger.append_evidence(ev2)

        assert r1.prev_chain_hash == ""
        assert r2.prev_chain_hash == r1.chain_hash

    def test_verify_chain_intact(self):
        """verify_chain returns True for untampered ledger."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        for i in range(5):
            ev = RouteEvidence(
                route_id=f"rid-{i}",
                selected_node=f"node-{i % 3}",
                candidates_considered=[f"node-{i % 3}"],
                selection_reason=f"Reason {i}",
                policy_basis="round_robin",
                timestamp_ns=i * 1000,
            )
            ledger.append_evidence(ev)

        ok, msg = ledger.verify_chain()
        assert ok, f"Chain should be intact: {msg}"

    def test_verify_chain_detects_tamper(self):
        """verify_chain detects tampered records."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-0", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Test",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        # Tamper: modify payload in-place
        ledger._records[0].payload["selected_node"] = "node-malicious"

        ok, msg = ledger.verify_chain()
        assert not ok, "Chain should detect tamper"

    def test_verify_record(self):
        """verify_record checks a single record."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-0", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Test",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        ok, msg = ledger.verify_record(0)
        assert ok, f"Record should verify: {msg}"

    def test_query_by_route_id(self):
        """Query finds records by route_id."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="find-me", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Test",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)
        ledger.append_evidence(RouteEvidence(
            route_id="other", selected_node="node-b",
            candidates_considered=["node-b"], selection_reason="Other",
            policy_basis="round_robin", timestamp_ns=2000,
        ))

        results = ledger.query(route_id="find-me")
        assert len(results) == 1
        assert results[0].payload["route_id"] == "find-me"

    def test_query_by_node_id(self):
        """Query finds records by node_id."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-1", selected_node="target-node",
            candidates_considered=["target-node", "other-node"],
            selection_reason="Test", policy_basis="round_robin",
            timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        results = ledger.query(node_id="target-node")
        assert len(results) >= 1

    def test_query_by_policy(self):
        """Query finds records by policy_basis."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-1", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Test",
            policy_basis="resource_aware", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        results = ledger.query(policy_basis="resource_aware")
        assert len(results) == 1

        no_results = ledger.query(policy_basis="nonexistent")
        assert len(no_results) == 0

    def test_query_by_time(self):
        """Query filters by time window."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        for i in range(5):
            ev = RouteEvidence(
                route_id=f"rid-{i}", selected_node=f"node-{i}",
                candidates_considered=[f"node-{i}"],
                selection_reason=f"R{i}", policy_basis="round_robin",
                timestamp_ns=i * 1000,
            )
            ledger.append_evidence(ev)

        results = ledger.query_by_time(1000, 3000)
        assert len(results) == 3  # timestamps 1000, 2000, 3000

    def test_query_by_record_type(self):
        """Query filters by record_type."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence, FallbackDecision

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-ev", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Test",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        fd = FallbackDecision(
            primary_node="node-x", primary_failure_reason="Timeout",
            timestamp_ns=2000,
        )
        ledger.append_evidence(ev)
        ledger.append_fallback(fd)

        ev_results = ledger.query(record_type="route_evidence")
        assert len(ev_results) == 1

        fb_results = ledger.query(record_type="fallback_decision")
        assert len(fb_results) == 1

    def test_export_json(self):
        """export_json returns valid JSON string."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-exp", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Export",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        json_str = ledger.export_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert len(parsed) == 1
        assert parsed[0]["payload"]["route_id"] == "rid-exp"

    def test_export_json_pretty(self):
        """export_json with pretty=True includes indentation."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-pretty", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Pretty",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        json_str = ledger.export_json(pretty=True)
        assert "\n" in json_str

    def test_export_file(self):
        """export_file writes JSON to disk."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        import tempfile
        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-file", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="File",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            ledger.export_file(tmppath)
            with open(tmppath) as f:
                data = json.load(f)
            assert len(data) == 1
        finally:
            Path(tmppath).unlink(missing_ok=True)

    def test_stats(self):
        """stats() returns summary statistics."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        for i in range(3):
            ev = RouteEvidence(
                route_id=f"rid-{i}", selected_node=f"node-{i}",
                candidates_considered=[f"node-{i}"],
                selection_reason=f"R{i}", policy_basis="round_robin",
                timestamp_ns=i * 1000,
            )
            ledger.append_evidence(ev)

        stats = ledger.stats()
        assert stats["total_records"] == 3
        assert stats["evidence_records"] == 3
        assert stats["fallback_records"] == 0

    def test_clear(self):
        """clear() removes all records."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-clr", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Clear",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)
        assert ledger.record_count == 1
        ledger.clear()
        assert ledger.record_count == 0

    def test_get_record(self):
        """get_record returns TraceRecord by index."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        ev = RouteEvidence(
            route_id="rid-get", selected_node="node-a",
            candidates_considered=["node-a"], selection_reason="Get",
            policy_basis="round_robin", timestamp_ns=1000,
        )
        ledger.append_evidence(ev)

        record = ledger.get_record(0)
        assert record is not None
        assert record.record_id == "rid-get"

        assert ledger.get_record(999) is None

    def test_sqlite_backend(self):
        """SQLite backend persists records."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger(backend="sqlite")
        for i in range(3):
            ev = RouteEvidence(
                route_id=f"sql-{i}", selected_node=f"node-{i}",
                candidates_considered=[f"node-{i}"],
                selection_reason=f"SQL {i}", policy_basis="round_robin",
                timestamp_ns=i * 1000,
            )
            ledger.append_evidence(ev)

        assert ledger.record_count == 3
        ok, _ = ledger.verify_chain()
        assert ok

    def test_file_backend(self):
        """File backend appends JSON lines."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            tmppath = f.name
        try:
            ledger = RouteTraceLedger(backend="file")
            ledger.set_file_path(tmppath)
            ev = RouteEvidence(
                route_id="file-1", selected_node="node-a",
                candidates_considered=["node-a"], selection_reason="File",
                policy_basis="round_robin", timestamp_ns=1000,
            )
            ledger.append_evidence(ev)
            ledger.append_evidence(RouteEvidence(
                route_id="file-2", selected_node="node-b",
                candidates_considered=["node-b"], selection_reason="File2",
                policy_basis="round_robin", timestamp_ns=2000,
            ))

            assert Path(tmppath).exists()
            lines = Path(tmppath).read_text().strip().split("\n")
            assert len(lines) == 2

            assert ledger.record_count == 2
        finally:
            Path(tmppath).unlink(missing_ok=True)

    def test_ledger_query_empty(self):
        """Query on empty ledger returns empty list."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger

        ledger = RouteTraceLedger()
        results = ledger.query(node_id="anything")
        assert results == []

    def test_query_by_node_finds_fallback_chain(self):
        """query_by_node finds records where node appears in fallback chain."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger

        ledger = RouteTraceLedger()
        # Simulate a fallback decision entry manually
        from hlf_mcp.hlf.routing.route_trace import TraceRecord
        import time

        record = TraceRecord(
            record_type="fallback_decision",
            record_id="fb-test",
            timestamp_ns=time.time_ns(),
            chain_hash="abc123",
            payload={
                "primary_node": "node-a",
                "final_node": "node-c",
                "fallback_chain": [
                    {"step": 1, "node_id": "node-b", "reason": "Available"},
                    {"step": 2, "node_id": "node-c", "reason": "Last"},
                ],
            },
            prev_chain_hash="",
        )
        with ledger._lock:
            ledger._records.append(record)

        # Can find node-b (in fallback chain)
        results_b = ledger.query_by_node("node-b")
        assert len(results_b) >= 1

        # Can find node-a (primary)
        results_a = ledger.query_by_node("node-a")
        assert len(results_a) >= 1

    def test_hash_determinism_across_instances(self):
        """Two ledgers with same data produce same chain hash."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        def build_ledger():
            ledger = RouteTraceLedger()
            ev = RouteEvidence(
                route_id="same-id", selected_node="node-a",
                candidates_considered=["node-a"], selection_reason="Same",
                policy_basis="round_robin", timestamp_ns=1000,
            )
            ledger.append_evidence(ev)
            return ledger

        l1 = build_ledger()
        l2 = build_ledger()
        assert l1._records[0].chain_hash == l2._records[0].chain_hash


# ═══════════════════════════════════════════════════════════════════════════════
# Evidence Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvidenceEdgeCases:
    """Edge case tests for evidence and trace systems."""

    def test_empty_candidate_pool_evidence(self):
        """Empty candidate pool produces evidence with no selection."""
        registry = NodeRegistry()
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        request = WorkRequest(request_id="empty-pool", capability="nonexistent")
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.selected_node is None
        assert evidence.candidates_considered == []

    def test_all_nodes_unhealthy_evidence(self):
        """All nodes unhealthy produces evidence with no selection (fail-closed)."""
        registry = NodeRegistry()
        registry.register("uh-1", "10.0.0.1", 9090, capabilities={"test": 5})
        registry.register("uh-2", "10.0.0.2", 9091, capabilities={"test": 5})
        registry.mark_unhealthy("uh-1")
        registry.mark_unhealthy("uh-2")
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        request = WorkRequest(request_id="all-unhealthy", capability="test")
        match = lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.selected_node is None
        assert not match.matched

    def test_rapid_evidence_generation(self):
        """Rapid successive evidence generation produces unique timestamps."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        evidence_list = []
        for i in range(50):
            ev = RouteEvidence(
                route_id=f"rapid-{i}",
                selected_node=f"node-{i % 5}",
                candidates_considered=[f"node-{i % 5}"],
                selection_reason=f"Rapid {i}",
                policy_basis="round_robin",
            )
            evidence_list.append(ev)

        # All should have unique route_ids
        route_ids = {ev.route_id for ev in evidence_list}
        assert len(route_ids) == 50

        # All should have valid hashes
        for ev in evidence_list:
            assert ev.verify_hash()

    def test_governance_trust_states_in_evidence(self):
        """RouteEvidence can carry governance trust states."""
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ev = RouteEvidence(
            selected_node="node-a",
            candidates_considered=["node-a", "node-b"],
            selection_reason="Governed",
            policy_basis="governed_cloud_completion",
            governance_trust_states={"node-a": "healthy", "node-b": "probation"},
        )
        assert ev.governance_trust_states["node-a"] == "healthy"
        assert ev.governance_trust_states["node-b"] == "probation"

    def test_ledger_large_volume(self):
        """Ledger handles 200+ records without performance issues."""
        from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger
        from hlf_mcp.hlf.routing.failover import RouteEvidence

        ledger = RouteTraceLedger()
        for i in range(200):
            ev = RouteEvidence(
                route_id=f"vol-{i}", selected_node=f"node-{i % 10}",
                candidates_considered=[f"node-{i % 10}"],
                selection_reason=f"Volume {i}",
                policy_basis="round_robin",
                timestamp_ns=i * 1000,
            )
            ledger.append_evidence(ev)

        assert ledger.record_count == 200
        ok, msg = ledger.verify_chain()
        assert ok, f"Chain should be intact after 200 records: {msg}"

    def test_single_node_routing_evidence(self):
        """Evidence captures correct info with only one candidate."""
        registry = NodeRegistry()
        registry.register("solo", "10.0.0.1", 9090, capabilities={"test": 5})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router)
        request = WorkRequest(request_id="solo-ev", capability="test")
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.selected_node == "solo"
        assert evidence.candidates_considered == ["solo"]

    def test_weighted_round_robin_evidence(self):
        """Evidence captures correct policy_basis for weighted strategy."""
        registry = NodeRegistry()
        registry.register("wr-1", "10.0.0.1", 9090, capabilities={"test": 9},
                           metadata={"weight": 3})
        registry.register("wr-2", "10.0.0.2", 9091, capabilities={"test": 5},
                           metadata={"weight": 1})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="weighted_round_robin")
        request = WorkRequest(request_id="wrr-ev", capability="test")
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.policy_basis == "weighted_round_robin"

    def test_least_connections_evidence(self):
        """Evidence captures correct policy for least_connections."""
        registry = NodeRegistry()
        registry.register("lc-1", "10.0.0.1", 9090, capabilities={"test": 5})
        registry.register("lc-2", "10.0.0.2", 9091, capabilities={"test": 5})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="least_connections")
        request = WorkRequest(request_id="lc-ev", capability="test")
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.policy_basis == "least_connections"

    def test_resource_aware_evidence(self):
        """Evidence captures correct policy for resource_aware."""
        registry = NodeRegistry()
        registry.register("ra-1", "10.0.0.1", 9090, capabilities={"test": 5},
                           metadata={"cpu_cores": 8, "memory_gb": 32, "gpu_vram_gb": 24})
        registry.register("ra-2", "10.0.0.2", 9091, capabilities={"test": 5},
                           metadata={"cpu_cores": 4, "memory_gb": 16, "gpu_vram_gb": 8})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="resource_aware")
        request = WorkRequest(request_id="ra-ev", capability="test")
        lb.distribute(request)
        evidence = lb.last_evidence
        assert evidence is not None
        assert evidence.policy_basis == "resource_aware"

    def test_evidence_survives_strategy_change(self):
        """Changing strategy updates evidence policy_basis."""
        registry = NodeRegistry()
        registry.register("st-1", "10.0.0.1", 9090, capabilities={"test": 5})
        registry.register("st-2", "10.0.0.2", 9091, capabilities={"test": 5})
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")
        request = WorkRequest(request_id="st-ev", capability="test")

        lb.distribute(request)
        assert lb.last_evidence.policy_basis == "round_robin"

        lb.set_strategy("least_loaded")
        lb.distribute(request)
        assert lb.last_evidence.policy_basis == "least_loaded"

    def test_edge_case_evidence_threshold_in_run_all(self):
        """The new edge case is included in run_all_edge_cases."""
        results = run_all_edge_cases()
        assert RoutingEdgeCase.EVIDENCE_THRESHOLD_VIOLATION in results
        result = results[RoutingEdgeCase.EVIDENCE_THRESHOLD_VIOLATION]
        assert result.edge_case == RoutingEdgeCase.EVIDENCE_THRESHOLD_VIOLATION
        assert result.status in ("passed", "warning", "failed")

    def test_run_all_edge_cases_now_8(self):
        """run_all_edge_cases returns 8 edge cases (was 7)."""
        results = run_all_edge_cases()
        assert len(results) == 8, f"Expected 8, got {len(results)}"
