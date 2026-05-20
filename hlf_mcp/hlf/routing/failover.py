"""
FailoverManager — handles node failures with automatic re-routing.

Detects stale heartbeats, marks nodes unhealthy, and re-routes work
to healthy alternatives.  Works with the LoadBalancer and CapabilityRouter
to maintain availability in distributed deployments.

Includes a circuit breaker to prevent routing to repeatedly-failing nodes
and configurable exponential backoff for failover retries.
"""

from __future__ import annotations

import logging
import random
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


# ── Circuit Breaker ──────────────────────────────────────────────────────────


@dataclass
class CircuitBreaker:
    """Circuit breaker for a single node.

    Tracks consecutive failures.  When failures exceed
    *failure_threshold*, the circuit "opens" — routing stops to that
    node for a *cooldown_seconds* period.  After cooldown, one request
    is allowed through ("half-open"); if it succeeds the circuit closes,
    if it fails it opens again with a longer cooldown.

    Attributes:
        node_id: The node this breaker protects.
        failure_threshold: Consecutive failures before opening.
        cooldown_seconds: How long to wait before trying again.
        half_open_max_requests: How many requests to allow in half-open state.
    """

    node_id: str
    failure_threshold: int = 5
    cooldown_seconds: float = 30.0
    half_open_max_requests: int = 1

    _consecutive_failures: int = field(default=0, repr=False)
    _state: str = field(default="closed", repr=False)  # "closed" | "open" | "half_open"
    _opened_at: float = field(default=0.0, repr=False)
    _half_open_requests: int = field(default=0, repr=False)
    _cooldown_multiplier: float = field(default=1.0, repr=False)

    # ── Failure / success recording ──────────────────────────────────────

    def record_failure(self) -> str:
        """Record a failure against this node and return the new state."""
        self._consecutive_failures += 1
        if self._state == "half_open":
            # Half-open failure → open again with longer cooldown
            self._state = "open"
            self._opened_at = time.time()
            self._cooldown_multiplier *= 2.0
            self._half_open_requests = 0
        elif self._state == "closed" and self._consecutive_failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.time()
        return self._state

    def record_success(self) -> str:
        """Record a success against this node and return the new state."""
        if self._state == "half_open":
            self._state = "closed"
            self._consecutive_failures = 0
            self._cooldown_multiplier = 1.0
            self._half_open_requests = 0
        elif self._state == "closed":
            self._consecutive_failures = 0
        return self._state

    # ── State queries ────────────────────────────────────────────────────

    def is_circuit_open(self) -> bool:
        """Return True if the circuit is currently open (node should be skipped).

        An open circuit transitions to half-open after *cooldown_seconds*
        times the current cooldown multiplier.
        """
        if self._state == "open":
            effective_cooldown = self.cooldown_seconds * self._cooldown_multiplier
            if time.time() - self._opened_at >= effective_cooldown:
                self._state = "half_open"
                self._half_open_requests = 0
                return False
            return True
        if self._state == "half_open":
            # In half-open, allow up to half_open_max_requests
            if self._half_open_requests < self.half_open_max_requests:
                return False
            return True
        return False  # closed → not open

    def circuit_state(self) -> str:
        """Return the current circuit state: "closed", "open", or "half_open"."""
        # Refresh state in case cooldown has elapsed
        self.is_circuit_open()
        return self._state

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        self._consecutive_failures = 0
        self._state = "closed"
        self._opened_at = 0.0
        self._cooldown_multiplier = 1.0
        self._half_open_requests = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialise circuit breaker state for inspection."""
        return {
            "node_id": self.node_id,
            "state": self.circuit_state(),
            "consecutive_failures": self._consecutive_failures,
            "cooldown_multiplier": self._cooldown_multiplier,
            "is_open": self.is_circuit_open(),
        }


class FailoverManager:
    """Handles node failure detection and automatic re-routing.

    Integrates with NodeRegistry for health tracking, CapabilityRouter for
    finding alternatives, and LoadBalancer for distribution strategy.
    Includes circuit breaker per node and configurable exponential backoff.

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
        backoff_base: float = 0.5,
        backoff_multiplier: float = 2.0,
        backoff_max: float = 30.0,
        backoff_jitter: bool = True,
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

        # Backoff configuration
        self._backoff_base = backoff_base
        self._backoff_multiplier = backoff_multiplier
        self._backoff_max = backoff_max
        self._backoff_jitter = backoff_jitter

        # Circuit breaker registry (per-node)
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    # ── Failure handling ──────────────────────────────────────────────────

    def handle_failure(self, node_id: str) -> RouteMatch:
        """Handle a node failure: mark unhealthy, decrement tasks, find alternative.

        The failed node's active tasks are cleared from the load balancer,
        and the router is used to find a best alternative for the capability
        most commonly served by the failed node.

        Records the failure in the circuit breaker for *node_id*.

        Returns a RouteMatch to the alternative node, or an unmatched match
        if no alternative is available.
        """
        node = self._registry.get_node(node_id)
        previous_health = node.health if node else "unknown"
        self._registry.mark_unhealthy(node_id)

        # Record to circuit breaker
        cb = self._get_or_create_breaker(node_id)
        cb.record_failure()

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
        """Explicitly recover a node to healthy status.

        Also resets the circuit breaker for this node and records a
        success to close an open/half-open circuit.
        """
        cb = self._get_or_create_breaker(node_id)
        cb.record_success()
        return self._registry.mark_healthy(node_id)

    # ── Re-routing ────────────────────────────────────────────────────────

    def failover_route(self, request: WorkRequest, failed_node_id: str) -> RouteMatch:
        """Route *request* to a different node after *failed_node_id* fails.

        Excludes the failed node from consideration and skips any nodes
        whose circuit breaker is open.  Retries up to *max_retries* with
        configurable exponential backoff.

        Returns a match to an alternative, or unmatched if exhausted.
        """
        excluded = set(request.exclude_nodes)
        excluded.add(failed_node_id)

        # Also exclude any nodes with open circuits
        for nid, cb in self._circuit_breakers.items():
            if cb.is_circuit_open() and nid not in excluded:
                excluded.add(nid)

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
                # Record success in circuit breaker for the matched node
                cb = self._get_or_create_breaker(match.matched_node.node_id)
                cb.record_success()
                return match

            delay = self._compute_backoff(attempt)
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

    def _compute_backoff(self, attempt: int) -> float:
        """Compute exponential backoff delay for *attempt* (1-indexed).

        Formula: base * (multiplier ** (attempt - 1)), capped at *backoff_max*.
        If *backoff_jitter* is enabled, adds ±25% random jitter.
        """
        delay = self._backoff_base * (self._backoff_multiplier ** (attempt - 1))
        if delay > self._backoff_max:
            delay = self._backoff_max
        if self._backoff_jitter:
            jitter = delay * 0.25 * (2.0 * random.random() - 1.0)
            delay = max(0.0, delay + jitter)
        return delay

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

    # ── Circuit breaker management ────────────────────────────────────────

    def _get_or_create_breaker(self, node_id: str) -> CircuitBreaker:
        """Get or create a circuit breaker for *node_id*."""
        with self._lock:
            if node_id not in self._circuit_breakers:
                self._circuit_breakers[node_id] = CircuitBreaker(node_id=node_id)
            return self._circuit_breakers[node_id]

    def record_failure(self, node_id: str) -> str:
        """Record a failure in the circuit breaker; return new state."""
        cb = self._get_or_create_breaker(node_id)
        return cb.record_failure()

    def record_success(self, node_id: str) -> str:
        """Record a success in the circuit breaker; return new state."""
        cb = self._get_or_create_breaker(node_id)
        return cb.record_success()

    def is_circuit_open(self, node_id: str) -> bool:
        """Return True if the circuit for *node_id* is currently open."""
        cb = self._circuit_breakers.get(node_id)
        if cb is None:
            return False
        return cb.is_circuit_open()

    def circuit_state(self, node_id: str) -> str:
        """Return the circuit state for *node_id* ("closed"|"open"|"half_open")."""
        cb = self._circuit_breakers.get(node_id)
        if cb is None:
            return "closed"
        return cb.circuit_state()

    def reset_circuit_breaker(self, node_id: str) -> None:
        """Reset the circuit breaker for *node_id* to closed."""
        cb = self._circuit_breakers.get(node_id)
        if cb is not None:
            cb.reset()

    def circuit_breaker_status(self) -> dict[str, dict[str, Any]]:
        """Return a snapshot of all circuit breaker states."""
        with self._lock:
            return {
                nid: cb.to_dict()
                for nid, cb in self._circuit_breakers.items()
            }
