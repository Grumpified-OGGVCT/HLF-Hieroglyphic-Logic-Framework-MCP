"""
FailoverManager — handles node failures with automatic re-routing.

Detects stale heartbeats, marks nodes unhealthy, and re-routes work
to healthy alternatives.  Works with the LoadBalancer and CapabilityRouter
to maintain availability in distributed deployments.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer

logger = logging.getLogger(__name__)


@dataclass
class NodeFailureEvent:
    """Records a node failure for audit and diagnostics.

    Attributes:
        node_id: The failed node.
        timestamp: When the failure was detected.
        reason: Why the node was marked unhealthy.
        previous_health: Health state before failure.
    """

    node_id: str
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    previous_health: str = "healthy"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "previous_health": self.previous_health,
        }


class FailoverManager:
    """Handles node failure detection and automatic re-routing.

    Integrates with NodeRegistry for health tracking, CapabilityRouter for
    finding alternatives, and LoadBalancer for distribution strategy.

    Usage:
        manager = FailoverManager(registry, router, lb, max_retries=3)
        manager.start_health_check_loop(interval=15.0)

        # On detected failure:
        match = manager.handle_failure("node-3")
    """

    def __init__(
        self,
        registry: NodeRegistry,
        router: CapabilityRouter,
        load_balancer: LoadBalancer,
        max_retries: int = 3,
        heartbeat_timeout: float = 30.0,
    ) -> None:
        self._registry = registry
        self._router = router
        self._load_balancer = load_balancer
        self._max_retries = max_retries
        self._heartbeat_timeout = heartbeat_timeout
        self._failure_history: list[NodeFailureEvent] = []
        self._lock = threading.Lock()
        self._running = False
        self._health_thread: threading.Thread | None = None

    # ── Failure handling ──────────────────────────────────────────────────

    def handle_failure(self, node_id: str) -> RouteMatch:
        """Handle a node failure: mark unhealthy, decrement tasks, find alternative.

        The failed node's active tasks are cleared from the load balancer,
        and the router is used to find a best alternative for the capability
        most commonly served by the failed node.

        Returns a RouteMatch to the alternative node, or an unmatched match
        if no alternative is available.
        """
        node = self._registry.get_node(node_id)
        previous_health = node.health if node else "unknown"
        self._registry.mark_unhealthy(node_id)

        # Clear active tasks for the failed node
        active_count = self._load_balancer.active_count(node_id)
        for _ in range(active_count):
            self._load_balancer.decrement_active(node_id)

        # Record the failure
        with self._lock:
            self._failure_history.append(
                NodeFailureEvent(
                    node_id=node_id,
                    reason="Explicit failure handling triggered.",
                    previous_health=previous_health,
                )
            )

        # Attempt to find an alternative for each capability the node had
        if node and node.capabilities:
            for capability, proficiency in sorted(
                node.capabilities.items(),
                key=lambda item: -item[1],
            ):
                alt_request = WorkRequest(
                    request_id=f"failover-{node_id}-{int(time.time())}",
                    capability=capability,
                    required_proficiency=max(1, proficiency),
                    exclude_nodes={node_id},
                )
                alt_match = self._router.match_request(alt_request)
                if alt_match.matched:
                    logger.info(
                        "Failover: %s → %s for capability '%s'",
                        node_id,
                        alt_match.matched_node.node_id,
                        capability,
                    )
                    return alt_match

        logger.warning(
            "Failover: no alternative node found for failed node '%s'", node_id
        )
        return RouteMatch(
            matched_node=None,
            confidence=0.0,
            rationale=f"No alternative node available after failure of '{node_id}'.",
        )

    def recover_node(self, node_id: str) -> bool:
        """Explicitly recover a node to healthy status."""
        return self._registry.mark_healthy(node_id)

    # ── Re-routing ────────────────────────────────────────────────────────

    def failover_route(self, request: WorkRequest, failed_node_id: str) -> RouteMatch:
        """Route *request* to a different node after *failed_node_id* fails.

        Excludes the failed node from consideration and retries up to
        *max_retries* with exponential backoff.

        Returns a match to an alternative, or unmatched if exhausted.
        """
        excluded = set(request.exclude_nodes)
        excluded.add(failed_node_id)

        retry_request = WorkRequest(
            request_id=request.request_id,
            capability=request.capability,
            payload=request.payload,
            priority=request.priority,
            required_proficiency=request.required_proficiency,
            exclude_nodes=excluded,
        )

        for attempt in range(1, self._max_retries + 1):
            match = self._load_balancer.distribute(retry_request)
            if match.matched:
                logger.info(
                    "Failover route attempt %d/%d succeeded: %s → %s",
                    attempt,
                    self._max_retries,
                    failed_node_id,
                    match.matched_node.node_id,
                )
                return match

            delay = 0.5 * (2 ** (attempt - 1))
            logger.debug(
                "Failover route attempt %d/%d failed, retrying in %.1fs",
                attempt,
                self._max_retries,
                delay,
            )
            time.sleep(delay)

        return RouteMatch(
            matched_node=None,
            confidence=0.0,
            rationale=(
                f"All {self._max_retries} failover attempts exhausted "
                f"for request '{request.request_id}' after failure of '{failed_node_id}'."
            ),
        )

    # ── Health check loop ─────────────────────────────────────────────────

    def health_check_loop(self, interval: float = 15.0) -> None:
        """Run a single health-check pass: detect stale nodes and trigger failover.

        Does NOT start a background thread — call this periodically.
        Use start_health_check_loop() for a background daemon thread.

        Nodes whose last heartbeat exceeds *heartbeat_timeout* are marked
        unhealthy, and a failure event is recorded.
        """
        stale = self._registry.stale_nodes(
            max_age_seconds=self._heartbeat_timeout,
        )
        for node in stale:
            if node.health != "unhealthy":
                previous = node.health
                self._registry.mark_unhealthy(node.node_id)
                with self._lock:
                    self._failure_history.append(
                        NodeFailureEvent(
                            node_id=node.node_id,
                            reason=f"Stale heartbeat (last: {node.last_heartbeat:.0f}, timeout: {self._heartbeat_timeout}s)",
                            previous_health=previous,
                        )
                    )
                logger.warning(
                    "Health check: marked '%s' unhealthy (stale heartbeat: %.0fs ago)",
                    node.node_id,
                    time.time() - node.last_heartbeat,
                )

    def start_health_check_loop(self, interval: float = 15.0) -> None:
        """Start a background daemon thread that runs periodic health checks.

        Args:
            interval: Seconds between health-check passes.
        """
        if self._running:
            return
        self._running = True

        def _loop() -> None:
            while self._running:
                try:
                    self.health_check_loop(interval=interval)
                except Exception:
                    logger.exception("Health check loop error")
                time.sleep(interval)

        self._health_thread = threading.Thread(target=_loop, daemon=True)
        self._health_thread.start()

    def stop_health_check_loop(self) -> None:
        """Stop the background health-check thread."""
        self._running = False
        if self._health_thread is not None:
            self._health_thread.join(timeout=5.0)
            self._health_thread = None

    # ── Failure history ───────────────────────────────────────────────────

    @property
    def failure_events(self) -> list[NodeFailureEvent]:
        """Return a copy of the failure event history."""
        with self._lock:
            return list(self._failure_history)

    def clear_failure_history(self) -> None:
        """Clear all recorded failure events."""
        with self._lock:
            self._failure_history.clear()
