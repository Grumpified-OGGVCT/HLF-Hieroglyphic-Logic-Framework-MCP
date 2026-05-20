"""
LoadBalancer — distributes work across available nodes using configurable strategies.

Supports round-robin, least-loaded, weighted-round-robin, least-connections,
and resource-aware strategies.  Tracks active task counts, connection counts,
and resource utilisation per node.  Delegates capability matching to
CapabilityRouter.

Now includes route-trace evidence generation on every route choice,
with fail-closed enforcement when evidence is insufficient.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)

_VALID_STRATEGIES = frozenset({
    "round_robin",
    "least_loaded",
    "weighted_round_robin",
    "least_connections",
    "resource_aware",
})


class LoadBalancer:
    """Distributes work across capable nodes using a pluggable strategy.

    Strategies:
      - "round_robin": Simple counter-based rotation across capable nodes.
      - "least_loaded": Select node with the lowest active_task_count.
      - "weighted_round_robin": Uses node proficiency or explicit weights
        from node metadata (``metadata["weight"]``) to weight selection.
        Higher weight = picked more often.
      - "least_connections": Like least_loaded but tracks persistent
        connections separately from in-flight tasks.
      - "resource_aware": Considers node metadata (``cpu_cores``,
        ``memory_gb``, ``gpu_vram_gb``) to compute available capacity.
        Selects node with most available resources relative to current load.

    Each distribute() call now produces a RouteEvidence snapshot for
    audit trail and traceability.  Evidence can be retrieved via
    ``last_evidence`` property.

    Thread-safe: the internal counters are guarded by a lock.
    """

    def __init__(
        self,
        registry: NodeRegistry,
        router: CapabilityRouter,
        strategy: str = "round_robin",
    ) -> None:
        self._registry = registry
        self._router = router
        self._strategy = strategy
        self._active_tasks: dict[str, int] = {}
        self._connections: dict[str, int] = {}  # for least_connections
        self._rr_counters: dict[str, int] = {}  # capability → next index
        self._weighted_counters: dict[str, float] = {}  # capability → fractional index
        self._lock = threading.Lock()

        # Evidence tracking
        self._last_evidence: Any = None  # RouteEvidence — lazy import to avoid circular

    # ── Strategy management ───────────────────────────────────────────────

    @property
    def strategy(self) -> str:
        return self._strategy

    def set_strategy(self, strategy: str) -> None:
        """Switch the load-balancing strategy.

        Args:
            strategy: One of "round_robin", "least_loaded",
                "weighted_round_robin", "least_connections", or
                "resource_aware".
        """
        if strategy not in _VALID_STRATEGIES:
            raise ValueError(
                f"Unknown strategy '{strategy}'; expected one of "
                f"{sorted(_VALID_STRATEGIES)}"
            )
        with self._lock:
            self._strategy = strategy

    # ── Task tracking ─────────────────────────────────────────────────────

    def increment_active(self, node_id: str) -> None:
        """Increment the active task count for *node_id*."""
        with self._lock:
            self._active_tasks[node_id] = self._active_tasks.get(node_id, 0) + 1

    def decrement_active(self, node_id: str) -> None:
        """Decrement the active task count for *node_id* (floor at 0)."""
        with self._lock:
            current = self._active_tasks.get(node_id, 0)
            if current > 0:
                self._active_tasks[node_id] = current - 1

    def active_count(self, node_id: str) -> int:
        """Return the current active task count for *node_id*."""
        with self._lock:
            return self._active_tasks.get(node_id, 0)

    # ── Connection tracking (least_connections strategy) ──────────────────

    def increment_connections(self, node_id: str) -> None:
        """Increment the persistent connection count for *node_id*."""
        with self._lock:
            self._connections[node_id] = self._connections.get(node_id, 0) + 1

    def decrement_connections(self, node_id: str) -> None:
        """Decrement the persistent connection count for *node_id* (floor at 0)."""
        with self._lock:
            current = self._connections.get(node_id, 0)
            if current > 0:
                self._connections[node_id] = current - 1

    def connection_count(self, node_id: str) -> int:
        """Return the current connection count for *node_id*."""
        with self._lock:
            return self._connections.get(node_id, 0)

    # ── Distribution ──────────────────────────────────────────────────────

    @property
    def last_evidence(self) -> Any:
        """Return the most recent RouteEvidence snapshot (or None)."""
        return self._last_evidence

    def distribute(self, request: WorkRequest) -> RouteMatch:
        """Distribute *request* to the best node using the configured strategy.

        First finds all capable nodes via CapabilityRouter, then applies
        the strategy to select one.  Returns an unmatched RouteMatch if
        no capable nodes are available.

        Generates a RouteEvidence snapshot on every call for audit trail.
        """
        from hlf_mcp.hlf.routing.failover import RouteEvidence  # lazy import

        matches = self._router.route_with_constraints(
            request,
            max_nodes=100,
            require_healthy=True,
        )
        if not matches:
            evidence = RouteEvidence(
                selected_node=None,
                candidates_considered=[],
                selection_reason="No capable healthy nodes available for distribution.",
                policy_basis=self._strategy,
            )
            self._last_evidence = evidence
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale="No capable healthy nodes available for distribution.",
            )

        capable_nodes = [
            m.matched_node for m in matches if m.matched_node is not None
        ]
        if not capable_nodes:
            evidence = RouteEvidence(
                selected_node=None,
                candidates_considered=[],
                selection_reason="No capable healthy nodes available for distribution.",
                policy_basis=self._strategy,
            )
            self._last_evidence = evidence
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale="No capable healthy nodes available for distribution.",
            )

        if self._strategy == "least_loaded":
            selected = self._select_least_loaded(capable_nodes)
        elif self._strategy == "weighted_round_robin":
            selected = self._select_weighted_round_robin(
                request.capability, capable_nodes
            )
        elif self._strategy == "least_connections":
            selected = self._select_least_connections(capable_nodes)
        elif self._strategy == "resource_aware":
            selected = self._select_resource_aware(capable_nodes)
        else:
            selected = self._select_round_robin(request.capability, capable_nodes)

        # Build evidence snapshot
        candidate_ids = [n.node_id for n in capable_nodes]
        health_evidence: dict[str, str] = {}
        match_scores: dict[str, int] = {}
        for node in capable_nodes:
            health_evidence[node.node_id] = node.health
            match_scores[node.node_id] = node.capabilities.get(request.capability, 0)

        proficiency = selected.capabilities.get(request.capability, 0)

        evidence = RouteEvidence(
            selected_node=selected.node_id,
            candidates_considered=candidate_ids,
            selection_reason=(
                f"Selected '{selected.node_id}' via {self._strategy} "
                f"(proficiency={proficiency}) from {len(capable_nodes)} candidates"
            ),
            policy_basis=self._strategy,
            health_check_evidence=health_evidence,
            capability_match_scores=match_scores,
        )
        self._last_evidence = evidence

        # Re-fetch the full match info from the router for confidence/rationale
        for match in matches:
            if match.matched_node and match.matched_node.node_id == selected.node_id:
                self.increment_active(selected.node_id)
                return match

        # Fallback: build a fresh match
        conf = min(0.95, 0.5 + proficiency / 10.0)
        self.increment_active(selected.node_id)
        return RouteMatch(
            matched_node=selected,
            confidence=conf,
            rationale=(
                f"Distributed via {self._strategy} to '{selected.node_id}' "
                f"(proficiency={proficiency})."
            ),
        )

    def distribute_with_evidence(
        self, request: WorkRequest
    ) -> tuple[RouteMatch, Any]:
        """Distribute *request* and return (match, evidence) tuple.

        The evidence includes full candidate snapshots with health checks
        and capability match scores for audit trail.
        """
        match = self.distribute(request)
        return match, self._last_evidence

    def distribute_with_fail_closed(
        self, request: WorkRequest, threshold: Any = None
    ) -> tuple[RouteMatch, Any]:
        """Distribute with fail-closed enforcement.

        If *threshold* is None, defaults to STANDARD.
        Returns (match, evidence).  If evidence is insufficient,
        returns an unmatched RouteMatch with rationale explaining
        which evidence was missing (fail-closed).

        Args:
            request: The work request to route.
            threshold: Evidence threshold to enforce (RouteEvidenceThreshold).
        """
        from hlf_mcp.hlf.routing.failover import (
            RouteEvidence,
            RouteEvidenceThreshold,
        )

        if threshold is None:
            threshold = RouteEvidenceThreshold.STANDARD

        match = self.distribute(request)
        evidence = self._last_evidence

        if evidence is not None and not evidence.meets_threshold(threshold):
            missing = evidence.missing_for_threshold(threshold)
            return (
                RouteMatch(
                    matched_node=None,
                    confidence=0.0,
                    rationale=(
                        f"Fail-closed: route evidence below threshold "
                        f"'{threshold.name}'. Missing: {', '.join(missing)}."
                    ),
                ),
                evidence,
            )

        return match, evidence

    # ── Internal selection helpers ────────────────────────────────────────

    def _select_round_robin(
        self,
        capability: str,
        nodes: list[RegisteredNode],
    ) -> RegisteredNode:
        """Select the next node in round-robin order for *capability*."""
        with self._lock:
            idx = self._rr_counters.get(capability, 0)
            selected = nodes[idx % len(nodes)]
            self._rr_counters[capability] = (idx + 1) % len(nodes)
        return selected

    def _select_least_loaded(
        self,
        nodes: list[RegisteredNode],
    ) -> RegisteredNode:
        """Select the node with the lowest active task count."""
        with self._lock:
            best = nodes[0]
            best_count = self._active_tasks.get(best.node_id, 0)
            for node in nodes[1:]:
                count = self._active_tasks.get(node.node_id, 0)
                if count < best_count:
                    best = node
                    best_count = count
        return best

    def _select_weighted_round_robin(
        self,
        capability: str,
        nodes: list[RegisteredNode],
    ) -> RegisteredNode:
        """Select a node using weighted round-robin.

        Weights are derived from node proficiency for *capability* or
        from explicit ``metadata["weight"]`` on the node.  Higher
        weight = picked more often.  Uses a fractional counter
        to track per-capability progress.
        """
        with self._lock:
            # Determine weights
            weights: list[float] = []
            for node in nodes:
                explicit = node.metadata.get("weight")
                if explicit is not None and isinstance(explicit, (int, float)):
                    weights.append(float(explicit))
                else:
                    # Use proficiency as implicit weight
                    prof = node.capabilities.get(capability, 1)
                    weights.append(float(max(1, prof)))

            total_weight = sum(weights)
            if total_weight <= 0:
                return nodes[0]

            # Normalise weights for step calculation
            norm = [w / total_weight for w in weights]

            # Get fractional counter for this capability
            frac = self._weighted_counters.get(capability, 0.0)

            # Walk through weights to find selected index
            cumulative = 0.0
            selected_idx = 0
            for idx, w in enumerate(norm):
                cumulative += w
                if frac < cumulative:
                    selected_idx = idx
                    break

            selected = nodes[selected_idx]

            # Advance counter by average step
            self._weighted_counters[capability] = (
                frac + 1.0 / len(nodes)
            ) % 1.0

        return selected

    def _select_least_connections(
        self,
        nodes: list[RegisteredNode],
    ) -> RegisteredNode:
        """Select the node with the lowest connection count.

        Falls back to first node if all connection counts are equal.
        """
        with self._lock:
            best = nodes[0]
            best_count = self._connections.get(best.node_id, 0)
            for node in nodes[1:]:
                count = self._connections.get(node.node_id, 0)
                if count < best_count:
                    best = node
                    best_count = count
        return best

    def _select_resource_aware(
        self,
        nodes: list[RegisteredNode],
    ) -> RegisteredNode:
        """Select the node with the most available resources.

        Considers node metadata:
          - ``cpu_cores`` (default 1)
          - ``memory_gb`` (default 1)
          - ``gpu_vram_gb`` (default 0)

        Available capacity is computed as:
            (resource * weight_cpu + resource * weight_mem + resource * weight_gpu)
            / (active_tasks + 1)

        Higher score = better candidate.
        """
        with self._lock:
            def _capacity(node: RegisteredNode) -> float:
                cpu = float(node.metadata.get("cpu_cores", 1))
                mem = float(node.metadata.get("memory_gb", 1))
                gpu = float(node.metadata.get("gpu_vram_gb", 0))
                active = self._active_tasks.get(node.node_id, 0)
                # Composite resource score divided by load
                raw = cpu * 1.0 + mem * 0.5 + gpu * 2.0
                return raw / max(active + 1, 1)

            best = max(nodes, key=_capacity)
        return best

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return a snapshot of active task distribution and connection state."""
        with self._lock:
            return {
                "strategy": self._strategy,
                "active_tasks": dict(self._active_tasks),
                "connections": dict(self._connections),
                "round_robin_counters": dict(self._rr_counters),
                "weighted_counters": dict(self._weighted_counters),
            }
