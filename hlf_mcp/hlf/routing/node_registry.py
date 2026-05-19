"""
NodeRegistry — distributed node discovery and registration.

Thread-safe registry that tracks nodes by ID, host, port, capabilities,
and health status.  Integrates with the existing witness-governance trust
model via trust-state-aware health classification.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisteredNode:
    """A node registered in the distributed routing fabric.

    Each node declares its capabilities (capability → proficiency mapping)
    and tracks its health independently.  The registry enforces no constraints
    on capability names — those are validated upstream by CapabilityRouter.
    """

    node_id: str
    host: str
    port: int
    capabilities: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    health: str = "healthy"  # "healthy" | "degraded" | "unhealthy"
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "capabilities": dict(self.capabilities),
            "metadata": dict(self.metadata),
            "health": self.health,
            "last_heartbeat": self.last_heartbeat,
        }


class NodeRegistry:
    """Thread-safe registry of distributed nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, RegisteredNode] = {}
        self._lock = threading.Lock()

    # ── Registration ─────────────────────────────────────────────────────

    def register(
        self,
        node_id: str,
        host: str,
        port: int,
        capabilities: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredNode:
        """Register a new node or update an existing one.

        If *node_id* already exists, its host, port, capabilities, and
        metadata are overwritten and the heartbeat timestamp is refreshed.
        """
        node = RegisteredNode(
            node_id=node_id,
            host=host,
            port=port,
            capabilities=dict(capabilities or {}),
            metadata=dict(metadata or {}),
            health="healthy",
            last_heartbeat=time.time(),
        )
        with self._lock:
            self._nodes[node_id] = node
        return node

    def unregister(self, node_id: str) -> bool:
        """Remove a node from the registry.  Returns True if it was present."""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                return True
            return False

    # ── Lookup ────────────────────────────────────────────────────────────

    def get_node(self, node_id: str) -> RegisteredNode | None:
        """Return the registered node or None."""
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self) -> list[RegisteredNode]:
        """Return a snapshot of all registered nodes."""
        with self._lock:
            return list(self._nodes.values())

    def list_by_capability(self, capability: str) -> list[RegisteredNode]:
        """Return all nodes that declare *capability* (at any proficiency)."""
        with self._lock:
            return [
                node
                for node in self._nodes.values()
                if capability in node.capabilities
            ]

    # ── Heartbeat & health ────────────────────────────────────────────────

    def heartbeat(self, node_id: str) -> bool:
        """Update the heartbeat timestamp for *node_id*.

        Returns True if the node was found, False otherwise.
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.last_heartbeat = time.time()
            # A heartbeat from a degraded node does not auto-promote it
            # back to healthy — that requires an explicit recover_node() call.
            return True

    def mark_unhealthy(self, node_id: str) -> bool:
        """Mark a node as unhealthy.  Returns False if not found."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.health = "unhealthy"
            return True

    def mark_degraded(self, node_id: str) -> bool:
        """Mark a node as degraded (still usable but under-performing)."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.health = "degraded"
            return True

    def mark_healthy(self, node_id: str) -> bool:
        """Explicitly restore a node to healthy status."""
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.health = "healthy"
            node.last_heartbeat = time.time()
            return True

    # ── Trust-state integration ───────────────────────────────────────────

    def apply_trust_snapshot(
        self,
        node_id: str,
        trust_state: str,
    ) -> bool:
        """Apply a governance trust state to a node's health classification.

        Maps TrustState values from witness_governance to node health:
          - "healthy"   → no change
          - "watched"   → degraded (still usable)
          - "probation" → degraded
          - "restricted" → unhealthy (routing denied)
        """
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            if trust_state == "restricted":
                node.health = "unhealthy"
            elif trust_state in ("watched", "probation"):
                node.health = "degraded"
            # "healthy" → leave as-is
            return True

    # ── Bulk queries ──────────────────────────────────────────────────────

    def healthy_nodes(self) -> list[RegisteredNode]:
        """Return all nodes currently marked healthy."""
        with self._lock:
            return [n for n in self._nodes.values() if n.health == "healthy"]

    def operational_nodes(self) -> list[RegisteredNode]:
        """Return nodes that are healthy or degraded (not unhealthy)."""
        with self._lock:
            return [
                n for n in self._nodes.values()
                if n.health in ("healthy", "degraded")
            ]

    def stale_nodes(self, max_age_seconds: float = 30.0) -> list[RegisteredNode]:
        """Return nodes whose last heartbeat is older than *max_age_seconds*."""
        threshold = time.time() - max_age_seconds
        with self._lock:
            return [
                n for n in self._nodes.values()
                if n.last_heartbeat < threshold
            ]
