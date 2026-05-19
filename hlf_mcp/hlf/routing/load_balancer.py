"""
LoadBalancer — distributes work across available nodes using configurable strategies.

Supports round-robin and least-loaded strategies.  Tracks active task counts
per node and delegates capability matching to CapabilityRouter.
"""

from __future__ import annotations

import itertools
import threading
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)


class LoadBalancer:
    """Distributes work across capable nodes using a pluggable strategy.

    Strategies:
      - "round_robin": Simple counter-based rotation across capable nodes.
      - "least_loaded": Select node with the lowest active_task_count.

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
        self._rr_counters: dict[str, int] = {}  # capability → next index
        self._lock = threading.Lock()

    # ── Strategy management ───────────────────────────────────────────────

    @property
    def strategy(self) -> str:
        return self._strategy

    def set_strategy(self, strategy: str) -> None:
        """Switch the load-balancing strategy.

        Args:
            strategy: One of "round_robin" or "least_loaded".
        """
        if strategy not in ("round_robin", "least_loaded"):
            raise ValueError(
                f"Unknown strategy '{strategy}'; expected 'round_robin' or 'least_loaded'"
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

    # ── Distribution ──────────────────────────────────────────────────────

    def distribute(self, request: WorkRequest) -> RouteMatch:
        """Distribute *request* to the best node using the configured strategy.

        First finds all capable nodes via CapabilityRouter, then applies
        the strategy to select one.  Returns an unmatched RouteMatch if
        no capable nodes are available.
        """
        matches = self._router.route_with_constraints(
            request,
            max_nodes=100,
            require_healthy=True,
        )
        if not matches:
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale="No capable healthy nodes available for distribution.",
            )

        capable_nodes = [
            m.matched_node for m in matches if m.matched_node is not None
        ]
        if not capable_nodes:
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale="No capable healthy nodes available for distribution.",
            )

        if self._strategy == "least_loaded":
            selected = self._select_least_loaded(capable_nodes)
        else:
            selected = self._select_round_robin(request.capability, capable_nodes)

        # Re-fetch the full match info from the router for confidence/rationale
        for match in matches:
            if match.matched_node and match.matched_node.node_id == selected.node_id:
                self.increment_active(selected.node_id)
                return match

        # Fallback: build a fresh match
        proficiency = selected.capabilities.get(request.capability, 0)
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

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return a snapshot of active task distribution."""
        with self._lock:
            return {
                "strategy": self._strategy,
                "active_tasks": dict(self._active_tasks),
                "round_robin_counters": dict(self._rr_counters),
            }
