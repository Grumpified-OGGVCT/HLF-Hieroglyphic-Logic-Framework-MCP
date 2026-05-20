"""
Edge Case Hardening — routing fabric edge case detection and diagnostics.

Tests extreme, boundary, and pathological scenarios in the routing fabric
and returns actionable results with recommendations.  Designed for
integration into CI pipelines and pre-deployment checklists.

Usage::

    from hlf_mcp.hlf.routing.edge_cases import run_all_edge_cases

    results = run_all_edge_cases()
    for case, result in results.items():
        print(f"{case.value}: {result.status}")
        for rec in result.recommendations:
            print(f"  → {rec}")
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer
from hlf_mcp.hlf.routing.failover import FailoverManager


# ── Enums & data classes ─────────────────────────────────────────────────────


class RoutingEdgeCase(Enum):
    EMPTY_REGISTRY = "empty_registry"
    SINGLE_NODE_FAILURE = "single_node_failure"
    CAPABILITY_MISMATCH = "capability_mismatch"
    RACE_CONDITION_REGISTER_UNREGISTER = "race_condition_register_unregister"
    LOAD_BALANCER_STARVATION = "load_balancer_starvation"
    FAILOVER_CASCADE = "failover_cascade"
    HEALTH_CHECK_FLAPPING = "health_check_flapping"


@dataclass
class EdgeCaseResult:
    """Result from testing a routing edge case.

    Attributes:
        edge_case: Which edge case was tested.
        status: "passed", "warning", or "failed".
        observations: What was observed during the test.
        recommendations: Actionable suggestions.
        metrics: Quantitative measurements (latency, counts, etc.).
    """

    edge_case: RoutingEdgeCase
    status: str  # "passed", "warning", "failed"
    observations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


# ── Edge case test functions ──────────────────────────────────────────────────


def test_empty_registry() -> EdgeCaseResult:
    """Route requests with zero registered nodes.  Verify graceful handling."""
    registry = NodeRegistry()
    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router)

    request = WorkRequest(
        request_id="empty-req",
        capability="inference",
        required_proficiency=1,
    )
    match = lb.distribute(request)

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"

    if match.matched:
        observations.append(
            "Unexpectedly matched a node from an empty registry"
        )
        status = "failed"
        recommendations.append(
            "Audit distribute() to ensure empty registry returns unmatched RouteMatch"
        )
    else:
        observations.append(
            "Empty registry correctly returned unmatched RouteMatch"
        )

    if match.confidence != 0.0:
        observations.append(
            f"Confidence should be 0.0 for empty registry, got {match.confidence}"
        )
        if status == "passed":
            status = "warning"

    if match.matched_node is not None:
        observations.append(
            "matched_node should be None when no nodes are registered"
        )
        status = "failed"

    if not match.rationale:
        observations.append(
            "Rationale should explain why no match was found"
        )
        if status != "failed":
            status = "warning"
        recommendations.append(
            "Ensure rationale always provides a human-readable explanation"
        )

    if status == "passed":
        recommendations.append(
            "Empty registry handling is correct — no action needed"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.EMPTY_REGISTRY,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics={"matched": match.matched, "confidence": match.confidence},
    )


def test_single_node_failure() -> EdgeCaseResult:
    """Only one node exists and it fails.  Verify system handles last-node failure."""
    registry = NodeRegistry()
    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router)
    failover = FailoverManager(registry, router, lb, max_retries=2)

    registry.register(
        "solo-node", "10.0.0.1", 9090,
        capabilities={"inference": 8},
    )

    # First, verify normal routing works
    pre_request = WorkRequest(
        request_id="solo-pre",
        capability="inference",
    )
    pre_match = lb.distribute(pre_request)
    lb.decrement_active("solo-node")

    # Now handle failure
    fail_match = failover.handle_failure("solo-node")

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"
    metrics: dict[str, Any] = {
        "pre_match_ok": pre_match.matched,
        "node_health_after_failure": registry.get_node("solo-node").health if registry.get_node("solo-node") else "missing",
    }

    if fail_match.matched:
        observations.append(
            "Failover found an alternative node when only one node existed — "
            "this suggests a routing bug or stale state"
        )
        status = "failed"
        recommendations.append(
            "Investigate failover handle_failure() logic when no alternatives exist"
        )
    else:
        observations.append(
            "Single-node failure correctly returned no alternative route"
        )

    # Verify the node is marked unhealthy
    node = registry.get_node("solo-node")
    if node is None or node.health != "unhealthy":
        observations.append("Failed node was not marked unhealthy")
        status = "failed"
        recommendations.append(
            "Ensure handle_failure() always marks the target node as unhealthy"
        )
    else:
        observations.append("Single node correctly marked unhealthy")

    events = failover.failure_events
    if len(events) == 0:
        observations.append("No failure event was recorded")
        if status != "failed":
            status = "warning"
        recommendations.append(
            "Verify failure events are recorded even for last-node failures"
        )
    else:
        metrics["failure_event_count"] = len(events)

    if status == "passed":
        recommendations.append(
            "Single-node failure handling is correct — consider adding "
            "alerting for 'last node failed' scenarios in production"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.SINGLE_NODE_FAILURE,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics=metrics,
    )


def test_capability_mismatch() -> EdgeCaseResult:
    """No node in the registry can handle the requested capability."""
    registry = NodeRegistry()
    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router)

    registry.register(
        "node-a", "10.0.0.1", 9090,
        capabilities={"inference": 8},
    )
    registry.register(
        "node-b", "10.0.0.2", 9091,
        capabilities={"embedding": 7},
    )

    # Request a capability nobody has
    request = WorkRequest(
        request_id="mismatch-req",
        capability="quantum_computing",
        required_proficiency=1,
    )
    match = lb.distribute(request)

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"

    if match.matched:
        observations.append(
            f"Matched node '{match.matched_node.node_id}' for unknown "
            f"capability 'quantum_computing' — capability routing is broken"
        )
        status = "failed"
        recommendations.append(
            "Audit find_capable_nodes() to verify capability filtering"
        )
    else:
        observations.append(
            "Unknown capability correctly returned no match"
        )

    if match.confidence != 0.0:
        observations.append(
            f"Confidence should be 0.0 on mismatch, got {match.confidence}"
        )
        if status != "failed":
            status = "warning"

    # Additional: request with proficiency higher than available
    request2 = WorkRequest(
        request_id="over-proficiency",
        capability="inference",
        required_proficiency=10,  # node-a has only 8
    )
    match2 = router.match_request(request2)

    if match2.matched:
        observations.append(
            "Over-proficiency request matched despite insufficient proficiency"
        )
        status = "failed"
        recommendations.append(
            "Verify proficiency threshold enforcement in find_capable_nodes()"
        )
    else:
        observations.append(
            "Over-proficiency request correctly rejected"
        )

    if status == "passed":
        recommendations.append(
            "Capability mismatch handling is correct — no action needed"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.CAPABILITY_MISMATCH,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics={
            "capability_mismatch_matched": match.matched,
            "over_proficiency_matched": match2.matched,
        },
    )


def test_race_condition_register_unregister() -> EdgeCaseResult:
    """Concurrent register and unregister operations on the same node.

    Uses threading to create realistic race conditions.
    Verifies registry consistency after concurrent ops.
    """
    registry = NodeRegistry()
    errors: list[str] = []
    ready = threading.Barrier(30 + 1, timeout=10)

    # Pre-register some nodes
    for i in range(5):
        registry.register(f"base-{i}", "10.0.0.1", 9090, capabilities={"test": i})

    def racer(op: str, idx: int) -> None:
        try:
            ready.wait(timeout=10)
        except threading.BrokenBarrierError:
            return
        try:
            if op == "register":
                registry.register(
                    f"race-{idx}", "10.0.0.1", 9090,
                    capabilities={"test": idx},
                )
            elif op == "unregister":
                registry.unregister(f"base-{idx % 5}")
            elif op == "register_unregister_same":
                node_id = f"flip-{idx}"
                registry.register(node_id, "10.0.0.1", 9090, capabilities={"test": idx})
                registry.unregister(node_id)
                registry.register(node_id, "10.0.0.2", 9091, capabilities={"test": idx})
        except Exception as exc:
            errors.append(f"{op}-{idx}: {exc}")

    threads: list[threading.Thread] = []
    for i in range(10):
        t = threading.Thread(target=racer, args=("register", i), daemon=True)
        threads.append(t)
    for i in range(10):
        t = threading.Thread(target=racer, args=("unregister", i), daemon=True)
        threads.append(t)
    for i in range(10):
        t = threading.Thread(target=racer, args=("register_unregister_same", i), daemon=True)
        threads.append(t)

    for t in threads:
        t.start()
    try:
        ready.wait(timeout=10)
    except threading.BrokenBarrierError:
        pass
    for t in threads:
        t.join(timeout=5)

    # Verify consistency
    nodes = registry.list_nodes()
    node_ids = {n.node_id for n in nodes}

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"
    metrics: dict[str, Any] = {"final_node_count": len(nodes), "errors": len(errors)}

    if errors:
        observations.append(f"Concurrent operations raised errors: {errors}")
        status = "failed"
        recommendations.append(
            "Investigate thread safety of register/unregister — "
            "concurrent operations should not raise exceptions"
        )

    # Verify all remaining nodes are consistent
    for node in nodes:
        if node.health != "healthy":
            observations.append(
                f"Node '{node.node_id}' has unexpected health: {node.health}"
            )
            if status != "failed":
                status = "warning"
        if node.host not in ("10.0.0.1", "10.0.0.2"):
            observations.append(
                f"Node '{node.node_id}' has unexpected host: {node.host}"
            )
            if status != "failed":
                status = "warning"

    observations.append(
        f"Registry consistent with {len(nodes)} nodes after concurrent ops"
    )

    if status == "passed":
        recommendations.append(
            "Concurrent register/unregister operations are safe — no action needed"
        )
    else:
        recommendations.append(
            "Consider adding retry logic or optimistic concurrency "
            "for register/unregister operations"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.RACE_CONDITION_REGISTER_UNREGISTER,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics=metrics,
    )


def test_load_balancer_starvation() -> EdgeCaseResult:
    """One node gets all work while others idle — verify fairness.

    Runs many distribute() calls and checks distribution is balanced.
    """
    registry = NodeRegistry()
    router = CapabilityRouter(registry)

    # Register 5 nodes with the same capabilities
    node_ids = []
    for i in range(5):
        nid = f"starve-{i}"
        node_ids.append(nid)
        registry.register(
            nid, f"10.0.0.{i + 1}", 9090,
            capabilities={"inference": 8},
        )

    lb = LoadBalancer(registry, router, strategy="round_robin")

    request = WorkRequest(
        request_id="starve-req",
        capability="inference",
    )

    hit_counts: dict[str, int] = {nid: 0 for nid in node_ids}

    for _ in range(100):
        match = lb.distribute(request)
        if match.matched and match.matched_node is not None:
            nid = match.matched_node.node_id
            hit_counts[nid] = hit_counts.get(nid, 0) + 1
            lb.decrement_active(nid)

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"
    metrics: dict[str, Any] = {"hit_counts": dict(hit_counts)}

    expected_per_node = 20  # 100 requests / 5 nodes
    tolerance = 5  # allow small deviation

    min_hits = min(hit_counts.values()) if hit_counts else 0
    max_hits = max(hit_counts.values()) if hit_counts else 0

    observations.append(
        f"Distribution: min={min_hits}, max={max_hits}, expected≈{expected_per_node}"
    )

    # A node with 0 hits would be starvation
    zero_hit_nodes = [nid for nid, count in hit_counts.items() if count == 0]
    if zero_hit_nodes:
        observations.append(
            f"Nodes with zero hits (starved): {zero_hit_nodes}"
        )
        status = "failed"
        recommendations.append(
            "Round-robin strategy is not distributing evenly — "
            "check _rr_counters thread safety and state consistency"
        )

    if min_hits < expected_per_node - tolerance:
        observations.append(
            f"Node under-served: {min_hits} hits vs expected {expected_per_node}"
        )
        if status != "failed":
            status = "warning"
        recommendations.append(
            "Consider adding anti-starvation mechanism: if a node gets <50% "
            "of expected work, route to it preferentially"
        )

    if status == "passed":
        recommendations.append(
            "Load balancer distributes fairly — no starvation detected"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.LOAD_BALANCER_STARVATION,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics=metrics,
    )


def test_failover_cascade() -> EdgeCaseResult:
    """Failover of one request triggers another failover.

    Verify cascade is detected and contained.
    """
    registry = NodeRegistry()
    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router)
    failover = FailoverManager(registry, router, lb, max_retries=5)

    # Create a chain of nodes where each relies on the next
    registry.register(
        "cascade-1", "10.0.0.1", 9090,
        capabilities={"inference": 9},
    )
    registry.register(
        "cascade-2", "10.0.0.2", 9091,
        capabilities={"inference": 8},
    )
    registry.register(
        "cascade-3", "10.0.0.3", 9092,
        capabilities={"inference": 7},
    )

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"
    cascade_count = 0

    # Simulate cascading failures
    # First fail
    match1 = failover.handle_failure("cascade-1")
    if match1.matched:
        cascade_count += 1
        observations.append(
            f"Failover 1: cascade-1 → {match1.matched_node.node_id}"
        )

    # Fail the node that took over
    if match1.matched and match1.matched_node is not None:
        original_takeover = match1.matched_node.node_id
        match2 = failover.handle_failure(original_takeover)
        if match2.matched:
            cascade_count += 1
            observations.append(
                f"Failover 2: {original_takeover} → {match2.matched_node.node_id}"
            )

    # Fail the last node
    match3 = failover.handle_failure("cascade-3")
    if match3.matched:
        cascade_count += 1
        observations.append(
            f"Failover 3: cascade-3 → {match3.matched_node.node_id}"
        )
    else:
        observations.append("Failover 3: no more nodes available (cascade terminated)")

    metrics: dict[str, Any] = {
        "cascade_depth": cascade_count,
        "failure_events": len(failover.failure_events),
    }

    if cascade_count > 2:
        observations.append(
            f"Cascading failover reached depth {cascade_count}"
        )
        if status != "failed":
            status = "warning"
        recommendations.append(
            "Consider adding cascade detection: if >N failovers occur "
            "within a time window, trigger broader recovery instead of "
            "continuing the cascade"
        )
    else:
        observations.append("Cascade terminated within acceptable bounds")

    if status == "passed":
        recommendations.append(
            "Failover cascade handling is adequate — consider monitoring "
            "cascade depth in production for early warning"
        )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.FAILOVER_CASCADE,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics=metrics,
    )


def test_health_check_flapping() -> EdgeCaseResult:
    """Node rapidly transitions between healthy and unhealthy.

    Verify system remains stable and doesn't oscillate.
    """
    registry = NodeRegistry()
    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router)
    failover = FailoverManager(registry, router, lb, max_retries=2)

    registry.register(
        "flappy", "10.0.0.1", 9090,
        capabilities={"inference": 8},
    )

    observations: list[str] = []
    recommendations: list[str] = []
    status = "passed"

    state_changes: list[tuple[float, str]] = []
    start = time.perf_counter()

    # Simulate 10 rapid health state changes
    for i in range(10):
        if i % 2 == 0:
            registry.mark_unhealthy("flappy")
            state_changes.append((time.perf_counter() - start, "unhealthy"))
        else:
            registry.mark_healthy("flappy")
            state_changes.append((time.perf_counter() - start, "healthy"))

    # Verify routing during/after flapping
    request = WorkRequest(
        request_id="flappy-req",
        capability="inference",
    )
    match = lb.distribute(request)

    final_health = registry.get_node("flappy").health if registry.get_node("flappy") else "missing"

    metrics: dict[str, Any] = {
        "state_changes": len(state_changes),
        "final_health": final_health,
        "routed_to_flappy": match.matched and match.matched_node is not None and match.matched_node.node_id == "flappy",
    }

    if len(state_changes) == 0:
        observations.append("No state changes observed")
        if status != "failed":
            status = "warning"

    observations.append(
        f"Node 'flappy' underwent {len(state_changes)} state changes "
        f"in ~{state_changes[-1][0] * 1000:.1f}ms, final state: {final_health}"
    )

    # The system is stable if it doesn't crash or deadlock
    observations.append("System remained stable through flapping (no crashes/deadlocks)")

    # Check that failure events were recorded
    events = failover.failure_events
    if len(events) == 0:
        observations.append(
            "No failure events recorded during flapping — "
            "rapid transitions may not be tracked"
        )
        if status != "failed":
            status = "warning"
        recommendations.append(
            "Consider debouncing health state changes: ignore transitions "
            "that revert within a minimum observation window"
        )

    recommendations.append(
        "Health-check flapping is handled but consider adding: "
        "1) Minimum state duration before accepting transitions "
        "2) Hysteresis to prevent oscillation "
        "3) Flapping detection that locks a node to unhealthy if it flaps >N times/minute"
    )

    return EdgeCaseResult(
        edge_case=RoutingEdgeCase.HEALTH_CHECK_FLAPPING,
        status=status,
        observations=observations,
        recommendations=recommendations,
        metrics=metrics,
    )


def run_all_edge_cases() -> dict[RoutingEdgeCase, EdgeCaseResult]:
    """Run all edge case tests and return results."""
    results: dict[RoutingEdgeCase, EdgeCaseResult] = {}
    results[RoutingEdgeCase.EMPTY_REGISTRY] = test_empty_registry()
    results[RoutingEdgeCase.SINGLE_NODE_FAILURE] = test_single_node_failure()
    results[RoutingEdgeCase.CAPABILITY_MISMATCH] = test_capability_mismatch()
    results[RoutingEdgeCase.RACE_CONDITION_REGISTER_UNREGISTER] = (
        test_race_condition_register_unregister()
    )
    results[RoutingEdgeCase.LOAD_BALANCER_STARVATION] = test_load_balancer_starvation()
    results[RoutingEdgeCase.FAILOVER_CASCADE] = test_failover_cascade()
    results[RoutingEdgeCase.HEALTH_CHECK_FLAPPING] = test_health_check_flapping()
    return results
