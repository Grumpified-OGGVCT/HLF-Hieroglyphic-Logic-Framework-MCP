"""
FailoverManager — handles node failures with automatic re-routing.

Detects stale heartbeats, marks nodes unhealthy, and re-routes work
to healthy alternatives.  Works with the LoadBalancer and CapabilityRouter
to maintain availability in distributed deployments.

Includes a circuit breaker to prevent routing to repeatedly-failing nodes,
configurable exponential backoff for failover retries, and route-trace
contracts with evidence snapshots, policy-backed fallback rationale,
and fail-closed enforcement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer

logger = logging.getLogger(__name__)


# ── Route Evidence Threshold ───────────────────────────────────────────────────


class RouteEvidenceThreshold(Enum):
    """Evidence threshold for route decision enforcement.

    - NONE: No evidence required — route even with no supporting data.
    - MINIMAL: At least route_id and selected_node must be present.
    - STANDARD: route_id, selected_node, selection_reason, and policy_basis required.
    - STRICT: All evidence fields required including health check, capability match,
      and circuit breaker state snapshots.
    """

    NONE = auto()
    MINIMAL = auto()
    STANDARD = auto()
    STRICT = auto()

    @classmethod
    def from_string(cls, value: str) -> "RouteEvidenceThreshold":
        """Parse a threshold from a case-insensitive string."""
        mapping = {
            "none": cls.NONE,
            "minimal": cls.MINIMAL,
            "standard": cls.STANDARD,
            "strict": cls.STRICT,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(
                f"Unknown threshold '{value}'; expected one of {list(mapping)}"
            )
        return mapping[key]


# ── Route Evidence ─────────────────────────────────────────────────────────────


@dataclass
class RouteEvidence:
    """Immutable evidence snapshot produced for every route decision.

    Attributes:
        route_id: Unique decision identifier (UUID).
        selected_node: Which node was chosen (node_id or None if unmatched).
        candidates_considered: List of node IDs evaluated during the decision.
        selection_reason: Why this node was selected (weight, health, capability
            match, latency, governance constraint, etc.).
        policy_basis: Which policy rule authorised this choice (e.g. "round_robin",
            "least_loaded", "weighted_round_robin", "resource_aware",
            "governance_allowlist", "failover_cascade").
        evidence_hash: SHA-256 hex digest of all above fields (tamper-detection).
        timestamp_ns: Nanosecond-resolution timestamp of the decision.
        health_check_evidence: Per-candidate health status at decision time.
        circuit_breaker_snapshot: Per-candidate circuit breaker state snapshots.
        capability_match_scores: Proficiency scores for each candidate evaluated.
        governance_trust_states: Trust states from governance (if applicable).
    """

    route_id: str = ""
    selected_node: str | None = None
    candidates_considered: list[str] = field(default_factory=list)
    selection_reason: str = ""
    policy_basis: str = ""
    evidence_hash: str = ""
    timestamp_ns: int = 0
    health_check_evidence: dict[str, str] = field(default_factory=dict)
    circuit_breaker_snapshot: dict[str, str] = field(default_factory=dict)
    capability_match_scores: dict[str, int] = field(default_factory=dict)
    governance_trust_states: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp_ns:
            self.timestamp_ns = time.time_ns()
        if not self.route_id:
            self.route_id = str(uuid.uuid4())
        if not self.evidence_hash:
            self.evidence_hash = self.compute_hash()

    def _canonical_dict(self) -> dict[str, Any]:
        """Return a deterministically-ordered dict of hashable fields."""
        return {
            "route_id": self.route_id,
            "selected_node": self.selected_node,
            "candidates_considered": sorted(self.candidates_considered),
            "selection_reason": self.selection_reason,
            "policy_basis": self.policy_basis,
            "timestamp_ns": self.timestamp_ns,
            "health_check_evidence": dict(sorted(self.health_check_evidence.items())),
            "circuit_breaker_snapshot": dict(sorted(self.circuit_breaker_snapshot.items())),
            "capability_match_scores": dict(sorted(self.capability_match_scores.items())),
            "governance_trust_states": dict(sorted(self.governance_trust_states.items())),
        }

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of all evidence fields (deterministic)."""
        canonical = self._canonical_dict()
        serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verify that the stored evidence_hash matches the computed hash."""
        return self.evidence_hash == self.compute_hash()

    def evidence_level(self) -> RouteEvidenceThreshold:
        """Determine the evidence level of this snapshot.

        STRICT: all fields present including health evidence for all candidates.
        STANDARD: route_id, selected_node, selection_reason, policy_basis.
        MINIMAL: at least route_id and selected_node.
        NONE: no route_id or no selected_node.
        """
        has_route = bool(self.route_id)
        has_selected = self.selected_node is not None
        has_reason = bool(self.selection_reason)
        has_policy = bool(self.policy_basis)
        has_health = bool(self.health_check_evidence)
        has_scores = bool(self.capability_match_scores)

        if not has_route or not has_selected:
            return RouteEvidenceThreshold.NONE
        if has_health and has_scores and has_reason and has_policy:
            return RouteEvidenceThreshold.STRICT
        if has_reason and has_policy:
            return RouteEvidenceThreshold.STANDARD
        return RouteEvidenceThreshold.MINIMAL

    def meets_threshold(self, threshold: RouteEvidenceThreshold) -> bool:
        """Check if this evidence meets or exceeds *threshold*."""
        level = self.evidence_level()
        levels = list(RouteEvidenceThreshold)
        return levels.index(level) >= levels.index(threshold)

    def missing_for_threshold(self, threshold: RouteEvidenceThreshold) -> list[str]:
        """Return list of missing evidence fields for *threshold*."""
        missing: list[str] = []
        if threshold.value >= RouteEvidenceThreshold.MINIMAL.value:
            if not self.route_id:
                missing.append("route_id")
            if self.selected_node is None:
                missing.append("selected_node")
        if threshold.value >= RouteEvidenceThreshold.STANDARD.value:
            if not self.selection_reason:
                missing.append("selection_reason")
            if not self.policy_basis:
                missing.append("policy_basis")
        if threshold.value >= RouteEvidenceThreshold.STRICT.value:
            if not self.health_check_evidence:
                missing.append("health_check_evidence")
            if not self.capability_match_scores:
                missing.append("capability_match_scores")
        return missing

    def to_dict(self) -> dict[str, Any]:
        return self._canonical_dict()


# ── Fallback Decision ──────────────────────────────────────────────────────────


@dataclass
class FallbackHop:
    """A single step in a fallback chain.

    Attributes:
        step: 1-indexed position in the fallback chain.
        node_id: The node selected at this fallback step.
        reason: Why this node was chosen over alternatives.
        health_status: Health status of this node at decision time.
        circuit_state: Circuit breaker state at decision time.
        attempt_number: Which retry attempt this was (1-indexed).
    """

    step: int
    node_id: str
    reason: str = ""
    health_status: str = ""
    circuit_state: str = ""
    attempt_number: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "node_id": self.node_id,
            "reason": self.reason,
            "health_status": self.health_status,
            "circuit_state": self.circuit_state,
            "attempt_number": self.attempt_number,
        }


@dataclass
class FallbackDecision:
    """Records the full rationale behind a failover routing decision.

    Captures the complete chain from primary → fallback1 → fallback2 ...
    with per-hop reasoning, health check evidence, and circuit breaker
    state at the time of each decision.

    Attributes:
        primary_node: The originally preferred node (that failed).
        fallback_chain: Ordered list of fallback hops attempted.
        final_node: The node ultimately chosen, or None if exhausted.
        total_attempts: Total number of routing attempts made.
        exhausted: True if all fallback options were exhausted.
        primary_failure_reason: Why the primary node was unavailable.
        timestamp_ns: Nanosecond-resolution timestamp.
        evidence_hash: SHA-256 of the fallback decision for tamper detection.
    """

    primary_node: str
    fallback_chain: list[FallbackHop] = field(default_factory=list)
    final_node: str | None = None
    total_attempts: int = 0
    exhausted: bool = False
    primary_failure_reason: str = ""
    timestamp_ns: int = 0
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp_ns:
            self.timestamp_ns = time.time_ns()
        if not self.evidence_hash:
            self.evidence_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute SHA-256 of the fallback decision (deterministic)."""
        canonical = {
            "primary_node": self.primary_node,
            "final_node": self.final_node,
            "total_attempts": self.total_attempts,
            "exhausted": self.exhausted,
            "primary_failure_reason": self.primary_failure_reason,
            "timestamp_ns": self.timestamp_ns,
            "fallback_chain": [hop.to_dict() for hop in self.fallback_chain],
        }
        serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_hash(self) -> bool:
        """Verify the stored hash matches the computed hash."""
        return self.evidence_hash == self.compute_hash()

    def add_hop(
        self,
        node_id: str,
        reason: str = "",
        health_status: str = "",
        circuit_state: str = "",
        attempt_number: int = 1,
    ) -> None:
        """Add a fallback hop to the chain."""
        step = len(self.fallback_chain) + 1
        self.fallback_chain.append(
            FallbackHop(
                step=step,
                node_id=node_id,
                reason=reason,
                health_status=health_status,
                circuit_state=circuit_state,
                attempt_number=attempt_number,
            )
        )
        self.total_attempts = attempt_number
        self.evidence_hash = ""  # invalidate
        self.evidence_hash = self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_node": self.primary_node,
            "fallback_chain": [hop.to_dict() for hop in self.fallback_chain],
            "final_node": self.final_node,
            "total_attempts": self.total_attempts,
            "exhausted": self.exhausted,
            "primary_failure_reason": self.primary_failure_reason,
            "timestamp_ns": self.timestamp_ns,
            "evidence_hash": self.evidence_hash,
        }


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
    Includes circuit breaker per node, configurable exponential backoff,
    and route-trace contracts with evidence snapshots.

    Usage:
        manager = FailoverManager(registry, router, lb, max_retries=3)
        manager.start_health_check_loop(interval=15.0)

        # On detected failure:
        match = manager.handle_failure("node-3")

        # Evidence-aware failover:
        match, evidence = manager.failover_with_evidence(request, "node-3")
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
        route_evidence_threshold: RouteEvidenceThreshold = RouteEvidenceThreshold.STANDARD,
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

        # Evidence threshold for fail-closed enforcement
        self._route_evidence_threshold = route_evidence_threshold

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

    # ── Evidence threshold ─────────────────────────────────────────────────

    @property
    def route_evidence_threshold(self) -> RouteEvidenceThreshold:
        return self._route_evidence_threshold

    def set_route_evidence_threshold(self, threshold: RouteEvidenceThreshold) -> None:
        """Set the evidence threshold for fail-closed enforcement."""
        self._route_evidence_threshold = threshold

    def enforce_evidence(self, evidence: RouteEvidence) -> tuple[bool, str]:
        """Check if *evidence* meets the configured threshold.

        Returns (True, "") if evidence is sufficient, or
        (False, error_message) if evidence is insufficient (fail-closed).

        When evidence fails the threshold check:
          - The route is denied (fail-closed)
          - A descriptive error message lists which evidence was missing
        """
        if evidence.meets_threshold(self._route_evidence_threshold):
            return True, ""
        missing = evidence.missing_for_threshold(self._route_evidence_threshold)
        msg = (
            f"Fail-closed: route evidence below threshold "
            f"'{self._route_evidence_threshold.name}'. "
            f"Missing evidence: {', '.join(missing)}."
        )
        return False, msg

    # ── Evidence capture helpers ────────────────────────────────────────────

    def _capture_candidate_evidence(
        self, candidates: list[RegisteredNode]
    ) -> tuple[dict[str, str], dict[str, str], dict[str, int]]:
        """Capture health, circuit breaker, and proficiency data for all candidates."""
        health_evidence: dict[str, str] = {}
        circuit_snapshot: dict[str, str] = {}
        match_scores: dict[str, int] = {}

        for node in candidates:
            nid = node.node_id
            health_evidence[nid] = node.health
            match_scores[nid] = (
                node.capabilities.get("__last_capability_used__", 0)
            )
            cb = self._circuit_breakers.get(nid)
            circuit_snapshot[nid] = cb.circuit_state() if cb else "closed"

        return health_evidence, circuit_snapshot, match_scores

    def _build_route_evidence(
        self,
        selected_node: RegisteredNode | None,
        candidates: list[RegisteredNode],
        selection_reason: str,
        policy_basis: str,
        capability: str = "",
    ) -> RouteEvidence:
        """Build a RouteEvidence snapshot from routing context."""
        candidate_ids = [n.node_id for n in candidates]
        health_evidence, circuit_snapshot, match_scores = (
            self._capture_candidate_evidence(candidates)
        )

        # Override match scores with actual proficiency for the capability
        if capability:
            for node in candidates:
                match_scores[node.node_id] = node.capabilities.get(capability, 0)

        return RouteEvidence(
            selected_node=selected_node.node_id if selected_node else None,
            candidates_considered=candidate_ids,
            selection_reason=selection_reason,
            policy_basis=policy_basis,
            health_check_evidence=health_evidence,
            circuit_breaker_snapshot=circuit_snapshot,
            capability_match_scores=match_scores,
        )

    # ── Evidence-aware failover ─────────────────────────────────────────────

    def failover_with_evidence(
        self, request: WorkRequest, failed_node_id: str
    ) -> tuple[RouteMatch, RouteEvidence | None, FallbackDecision | None]:
        """Evidence-aware failover with full traceability.

        Returns:
            (match, evidence, fallback_decision) — evidence and fallback_decision
            are None if no routing was attempted.
        """
        node = self._registry.get_node(failed_node_id)
        primary_failure_reason = (
            f"Node '{failed_node_id}' health={node.health if node else 'unknown'}"
        )

        fallback = FallbackDecision(
            primary_node=failed_node_id,
            primary_failure_reason=primary_failure_reason,
        )

        excluded = set(request.exclude_nodes)
        excluded.add(failed_node_id)

        # Also exclude nodes with open circuits
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

        last_evidence: RouteEvidence | None = None

        for attempt in range(1, self._max_retries + 1):
            match = self._load_balancer.distribute(retry_request)
            if match.matched and match.matched_node is not None:
                matched_nid = match.matched_node.node_id
                # Record hop in fallback chain
                cb = self._circuit_breakers.get(matched_nid)
                cb_state = cb.circuit_state() if cb else "closed"
                node = self._registry.get_node(matched_nid)
                health = node.health if node else "unknown"

                fallback.add_hop(
                    node_id=matched_nid,
                    reason=f"Attempt {attempt}/{self._max_retries}: matched via {self._load_balancer.strategy}",
                    health_status=health,
                    circuit_state=cb_state,
                    attempt_number=attempt,
                )

                # Build evidence
                candidates = self._router.find_capable_nodes(
                    request.capability,
                    min_proficiency=request.required_proficiency,
                )
                evidence = self._build_route_evidence(
                    selected_node=match.matched_node,
                    candidates=candidates,
                    selection_reason=(
                        f"Failover attempt {attempt}: routed to '{matched_nid}' "
                        f"after failure of '{failed_node_id}'"
                    ),
                    policy_basis=f"failover_from_{failed_node_id}",
                    capability=request.capability,
                )

                fallback.final_node = matched_nid
                fallback.exhausted = False
                fallback.evidence_hash = ""  # refresh
                fallback.evidence_hash = fallback.compute_hash()

                cb_record = self._get_or_create_breaker(matched_nid)
                cb_record.record_success()

                logger.info(
                    "Failover route with evidence attempt %d/%d succeeded: %s → %s",
                    attempt, self._max_retries, failed_node_id, matched_nid,
                )
                return match, evidence, fallback

            # Record failed attempt
            delay = self._compute_backoff(attempt)
            logger.debug(
                "Failover route attempt %d/%d failed, retrying in %.1fs",
                attempt, self._max_retries, delay,
            )
            time.sleep(delay)

        # Exhausted
        fallback.exhausted = True
        fallback.evidence_hash = ""  # refresh
        fallback.evidence_hash = fallback.compute_hash()

        unmatched = RouteMatch(
            matched_node=None,
            confidence=0.0,
            rationale=(
                f"All {self._max_retries} failover attempts exhausted "
                f"for request '{request.request_id}' after failure of '{failed_node_id}'."
            ),
        )
        return unmatched, last_evidence, fallback

    def handle_failure_with_evidence(
        self, node_id: str
    ) -> tuple[RouteMatch, RouteEvidence | None]:
        """Handle failure with evidence capture.

        Like handle_failure() but also produces a RouteEvidence snapshot.
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
                    reason="Explicit failure handling triggered (with evidence).",
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
                candidates = self._router.find_capable_nodes(
                    capability,
                    min_proficiency=max(1, proficiency),
                )
                candidates = [
                    n for n in candidates
                    if n.node_id != node_id
                ]
                alt_match = self._router.match_request(alt_request)
                if alt_match.matched and alt_match.matched_node is not None:
                    evidence = self._build_route_evidence(
                        selected_node=alt_match.matched_node,
                        candidates=candidates,
                        selection_reason=(
                            f"Failover from '{node_id}' to "
                            f"'{alt_match.matched_node.node_id}' for capability '{capability}'"
                        ),
                        policy_basis=f"failover_from_{node_id}",
                        capability=capability,
                    )
                    logger.info(
                        "Failover with evidence: %s → %s for capability '%s'",
                        node_id,
                        alt_match.matched_node.node_id,
                        capability,
                    )
                    return alt_match, evidence

        # No alternative
        evidence = RouteEvidence(
            selected_node=None,
            candidates_considered=[],
            selection_reason=f"No alternative node available after failure of '{node_id}'.",
            policy_basis=f"failover_from_{node_id}",
        )
        logger.warning(
            "Failover: no alternative node found for failed node '%s'", node_id
        )
        return (
            RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale=f"No alternative node available after failure of '{node_id}'.",
            ),
            evidence,
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
