"""
CapabilityRouter — routes work to nodes based on declared capability manifests.

Bridges the CapabilityManifest model (from capability_manifest.py) with
the NodeRegistry to find the best-fitting node for each work request.
Integrates with witness-governance trust states and governed_routing.py
decision types to honour governance constraints during routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode


@dataclass
class WorkRequest:
    """A unit of work to be routed to a capable node.

    Attributes:
        request_id: Unique identifier for tracing.
        capability: The capability required to handle this request.
        payload: Arbitrary payload data.
        priority: Higher = more urgent (default 0).
        required_proficiency: Minimum proficiency level required.
        exclude_nodes: Node IDs to exclude from consideration.
    """

    request_id: str
    capability: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    required_proficiency: int = 1
    exclude_nodes: set[str] = field(default_factory=set)


@dataclass
class RouteMatch:
    """Result of matching a work request to a capable node.

    Attributes:
        matched_node: The selected node, or None if no match.
        confidence: 0.0–1.0 confidence in the match quality.
        rationale: Human-readable explanation of the match.
    """

    matched_node: RegisteredNode | None
    confidence: float = 0.0
    rationale: str = ""

    @property
    def matched(self) -> bool:
        return self.matched_node is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "node_id": self.matched_node.node_id if self.matched_node else None,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


class CapabilityRouter:
    """Routes work requests to nodes based on declared capabilities.

    Integrates governance constraints from the existing witness / governed
    routing stack:
      - Nodes marked "restricted" by trust governance are excluded
      - Probation / watched nodes get reduced confidence
    """

    def __init__(self, registry: NodeRegistry) -> None:
        self._registry = registry

    # ── Capability lookup ─────────────────────────────────────────────────

    def find_capable_nodes(
        self,
        capability: str,
        min_proficiency: int = 1,
    ) -> list[RegisteredNode]:
        """Return all nodes that declare *capability* at or above *min_proficiency*.

        Only operational nodes (healthy + degraded) are considered.
        Unhealthy nodes are always excluded.
        """
        candidates = self._registry.list_by_capability(capability)
        return [
            node
            for node in candidates
            if node.health != "unhealthy"
            and node.capabilities.get(capability, 0) >= min_proficiency
        ]

    # ── Primary matching ──────────────────────────────────────────────────

    def match_request(self, request: WorkRequest) -> RouteMatch:
        """Match a work request to the single best-fitting node.

        Selection priority:
          1. Highest proficiency for the requested capability
          2. Healthy nodes before degraded nodes
          3. Alphabetical by node_id as stable tie-break

        Returns a RouteMatch, which may have matched_node=None.
        """
        candidates = self.find_capable_nodes(
            request.capability,
            min_proficiency=request.required_proficiency,
        )

        # Filter out explicitly excluded nodes
        if request.exclude_nodes:
            candidates = [
                n for n in candidates
                if n.node_id not in request.exclude_nodes
            ]

        if not candidates:
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale=(
                    f"No operational node found for capability "
                    f"'{request.capability}' at proficiency >= "
                    f"{request.required_proficiency}"
                ),
            )

        # Sort: highest proficiency first, healthy before degraded,
        # then alphabetically.
        def _sort_key(node: RegisteredNode) -> tuple:
            prof = node.capabilities.get(request.capability, 0)
            health_rank = 0 if node.health == "healthy" else 1
            return (-prof, health_rank, node.node_id)

        candidates.sort(key=_sort_key)
        best = candidates[0]

        proficiency = best.capabilities.get(request.capability, 0)
        if best.health == "degraded":
            confidence = min(0.7, proficiency / 10.0)
            rationale = (
                f"Matched degraded node '{best.node_id}' (proficiency={proficiency}); "
                f"confidence reduced due to health state."
            )
        else:
            confidence = min(0.95, 0.5 + proficiency / 10.0)
            rationale = (
                f"Matched healthy node '{best.node_id}' with proficiency={proficiency} "
                f"for capability '{request.capability}'."
            )

        return RouteMatch(matched_node=best, confidence=confidence, rationale=rationale)

    # ── Constrained routing ───────────────────────────────────────────────

    def route_with_constraints(
        self,
        request: WorkRequest,
        max_nodes: int = 1,
        require_healthy: bool = True,
    ) -> list[RouteMatch]:
        """Return up to *max_nodes* matches for *request*.

        If *require_healthy* is True, degraded nodes are excluded.
        Otherwise, degraded nodes are included but ranked below healthy ones.

        Returns an empty list if no nodes satisfy the constraints.
        """
        candidates = self.find_capable_nodes(
            request.capability,
            min_proficiency=request.required_proficiency,
        )

        if request.exclude_nodes:
            candidates = [
                n for n in candidates
                if n.node_id not in request.exclude_nodes
            ]

        if require_healthy:
            candidates = [n for n in candidates if n.health == "healthy"]

        if not candidates:
            return []

        # Sort: highest proficiency, healthy before degraded, alphabetical
        def _sort_key(node: RegisteredNode) -> tuple:
            prof = node.capabilities.get(request.capability, 0)
            health_rank = 0 if node.health == "healthy" else 1
            return (-prof, health_rank, node.node_id)

        candidates.sort(key=_sort_key)

        if max_nodes < 1:
            max_nodes = 1

        results: list[RouteMatch] = []
        for node in candidates[:max_nodes]:
            proficiency = node.capabilities.get(request.capability, 0)
            if node.health == "degraded":
                conf = min(0.7, proficiency / 10.0)
                rationale = (
                    f"Degraded node '{node.node_id}' (proficiency={proficiency}) "
                    f"for capability '{request.capability}'."
                )
            else:
                conf = min(0.95, 0.5 + proficiency / 10.0)
                rationale = (
                    f"Healthy node '{node.node_id}' with proficiency={proficiency} "
                    f"for capability '{request.capability}'."
                )
            results.append(
                RouteMatch(matched_node=node, confidence=conf, rationale=rationale)
            )

        return results

    # ── Governance-integrated routing ─────────────────────────────────────

    def route_governed(
        self,
        request: WorkRequest,
        trust_snapshots: dict[str, str],
        allowlist_decision: str | None = None,
    ) -> RouteMatch:
        """Route with full governance integration.

        *trust_snapshots* maps node_id → trust_state (from witness_governance).
        Nodes with trust_state="restricted" are excluded.
        Nodes with trust_state in ("probation", "watched") are degraded.

        *allowlist_decision* follows governed_routing.RoutingDecision semantics:
          - "deny" → no routing allowed
          - "deterministic_local_only" → only local nodes
          - "governed_cloud_completion" → cloud-capable nodes preferred
          - None → no allowlist constraint
        """
        if allowlist_decision == "deny":
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale="Routing denied by allowlist governance decision.",
            )

        candidates = self.find_capable_nodes(
            request.capability,
            min_proficiency=request.required_proficiency,
        )

        if request.exclude_nodes:
            candidates = [
                n for n in candidates
                if n.node_id not in request.exclude_nodes
            ]

        # Apply trust state constraints
        filtered: list[RegisteredNode] = []
        for node in candidates:
            trust = trust_snapshots.get(node.node_id)
            if trust is None:
                filtered.append(node)
            elif trust == "restricted":
                continue  # excluded entirely
            elif trust in ("probation", "watched"):
                # Mark as degraded for routing purposes
                filtered.append(node)
            else:
                filtered.append(node)

        # If allowlist says local-only, prefer nodes without cloud metadata
        if allowlist_decision == "deterministic_local_only":
            filtered = [
                n for n in filtered
                if not n.metadata.get("cloud", False)
            ] or filtered  # fall back to all filtered if none local

        if not filtered:
            return RouteMatch(
                matched_node=None,
                confidence=0.0,
                rationale=(
                    "No nodes satisfy governance constraints "
                    "(trust state, allowlist) for the requested capability."
                ),
            )

        # Sort and pick best
        def _sort_key(node: RegisteredNode) -> tuple:
            prof = node.capabilities.get(request.capability, 0)
            health_rank = 0 if node.health == "healthy" else 1
            return (-prof, health_rank, node.node_id)

        filtered.sort(key=_sort_key)
        best = filtered[0]
        proficiency = best.capabilities.get(request.capability, 0)
        confidence = min(0.95, 0.5 + proficiency / 10.0)
        if best.health == "degraded":
            confidence = min(0.7, proficiency / 10.0)

        return RouteMatch(
            matched_node=best,
            confidence=confidence,
            rationale=(
                f"Governed match: '{best.node_id}' (proficiency={proficiency}) "
                f"with trust and allowlist constraints applied."
            ),
        )
