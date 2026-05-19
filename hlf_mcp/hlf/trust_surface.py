"""
Trust Surface — maps which HLF components trust which, under what conditions.

The trust surface is a directed graph of TrustEdge relationships between
components in the HLF pipeline. Each edge captures:
  - Who trusts whom (directed)
  - At what level (high / medium / low / none / conditional)
  - Under what conditions (gating predicates)
  - With what evidence (provenance backing)

Built from the component registry and checked against constitutional rules,
the trust surface enables:
  - Trust chain validation (can A reach B via a trusted path?)
  - Violation detection (high trust across constitutional boundaries)
  - Full graph reporting and DOT visualization
  - Constitution-aware trust auditing

Integration points:
  - hlf_mcp.hlf.two_channel_executor.ProvenanceChain — trust provenance
  - hlf_mcp.hlf.ethics.constitution  — ARTICLES, evaluate_constitution
  - hlf_mcp.hlf.ethics.governor      — EthicalGovernor, GovernorResult
  - hlf_mcp.hlf.registry             — component registry for edge building
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# TrustEdge
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TrustEdge:
    """A directed trust relationship between two components.

    Each edge represents a declaration that `from_component` trusts
    `to_component` at a specified level, gated by optional conditions
    and backed by evidence.

    Attributes:
        from_component: The component extending trust.
        to_component:   The component receiving trust.
        trust_level:    One of "high", "medium", "low", "none", "conditional".
        conditions:     Predicates that must be satisfied for the trust to hold.
        evidence:       Supporting provenance or audit records.
        bidirectional:  If True, trust flows both ways equally.
    """

    from_component: str
    to_component: str
    trust_level: str  # "high" | "medium" | "low" | "none" | "conditional"
    conditions: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    bidirectional: bool = False

    def __post_init__(self) -> None:
        valid_levels = {"high", "medium", "low", "none", "conditional"}
        if self.trust_level not in valid_levels:
            raise ValueError(
                f"Invalid trust_level '{self.trust_level}'. "
                f"Must be one of: {', '.join(sorted(valid_levels))}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trust edge."""
        return {
            "from_component": self.from_component,
            "to_component": self.to_component,
            "trust_level": self.trust_level,
            "conditions": list(self.conditions),
            "evidence": list(self.evidence),
            "bidirectional": self.bidirectional,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrustEdge:
        """Deserialize from a dict."""
        return cls(
            from_component=str(data.get("from_component", "")),
            to_component=str(data.get("to_component", "")),
            trust_level=str(data.get("trust_level", "none")),
            conditions=list(data.get("conditions", [])),
            evidence=list(data.get("evidence", [])),
            bidirectional=bool(data.get("bidirectional", False)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Trust level order (for weakest-link computation)
# ═══════════════════════════════════════════════════════════════════════════════

_TRUST_ORDER: dict[str, int] = {
    "none": 0,
    "low": 1,
    "conditional": 2,
    "medium": 3,
    "high": 4,
}

_TRUST_REVERSE: dict[int, str] = {v: k for k, v in _TRUST_ORDER.items()}


def _weakest(level_a: str, level_b: str) -> str:
    """Return the weaker (lower ordinal) of two trust levels."""
    return level_a if _TRUST_ORDER[level_a] <= _TRUST_ORDER[level_b] else level_b


# ═══════════════════════════════════════════════════════════════════════════════
# DOT colour map
# ═══════════════════════════════════════════════════════════════════════════════

_DOT_STYLE: dict[str, dict[str, str]] = {
    "high":        {"color": "green",  "style": "solid"},
    "medium":      {"color": "blue",   "style": "solid"},
    "low":         {"color": "orange", "style": "solid"},
    "none":        {"color": "red",    "style": "dashed"},
    "conditional": {"color": "purple", "style": "dotted"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# TrustSurface
# ═══════════════════════════════════════════════════════════════════════════════


class TrustSurface:
    """Maps which components trust which, under what conditions.

    Built from a component registry and constitutional rules.
    Supports validation of trust chains and detection of violations.

    Usage::

        surface = TrustSurface()
        surface.add_edge(TrustEdge(
            from_component="governor",
            to_component="compiler",
            trust_level="high",
            evidence=["governor blocks compilation — constitution C-5"],
        ))
        result = surface.validate_trust_chain("governor", "executor")
    """

    def __init__(self, edges: list[TrustEdge] | None = None) -> None:
        """
        Args:
            edges: Optional initial list of TrustEdge objects.
        """
        self._edges: list[TrustEdge] = list(edges) if edges else []
        self._adjacency: dict[str, list[TrustEdge]] = {}
        self._build_index()

    # ── Index management ───────────────────────────────────────────────────

    def _build_index(self) -> None:
        """Rebuild the adjacency index from the current edge list."""
        self._adjacency.clear()
        for edge in self._edges:
            self._adjacency.setdefault(edge.from_component, []).append(edge)
            if edge.bidirectional:
                reverse_edge = TrustEdge(
                    from_component=edge.to_component,
                    to_component=edge.from_component,
                    trust_level=edge.trust_level,
                    conditions=list(edge.conditions),
                    evidence=list(edge.evidence),
                    bidirectional=False,
                )
                self._adjacency.setdefault(reverse_edge.from_component, []).append(reverse_edge)

    # ── Edge CRUD ──────────────────────────────────────────────────────────

    def add_edge(self, edge: TrustEdge) -> None:
        """Add a trust edge and rebuild the index."""
        self._edges.append(edge)
        self._build_index()

    def remove_edge(self, from_comp: str, to_comp: str) -> bool:
        """Remove a trust edge.

        Args:
            from_comp: Source component name.
            to_comp:   Target component name.

        Returns:
            True if an edge was found and removed, False otherwise.
        """
        for i, edge in enumerate(self._edges):
            if edge.from_component == from_comp and edge.to_component == to_comp:
                self._edges.pop(i)
                self._build_index()
                return True
        return False

    # ── Lookup ─────────────────────────────────────────────────────────────

    def get_edges_from(self, component: str) -> list[TrustEdge]:
        """Get all trust edges originating from a component."""
        return list(self._adjacency.get(component, []))

    def get_edges_to(self, component: str) -> list[TrustEdge]:
        """Get all trust edges targeting a component."""
        return [edge for edge in self._edges if edge.to_component == component]

    # ── Trust chain validation ─────────────────────────────────────────────

    def validate_trust_chain(
        self,
        source: str,
        target: str,
        required_level: str = "medium",
    ) -> dict[str, Any]:
        """Check if a trust path exists from source to target.

        Uses BFS to find the shortest path whose weakest trust link meets
        or exceeds the required level.  Handles cycles safely via visited
        tracking.

        Args:
            source:         Starting component.
            target:         Destination component.
            required_level: Minimum trust level required for the chain.

        Returns:
            A dict with keys:
                valid:               bool — whether a qualifying path exists
                path:                list[str] — component names along the path
                trust_path:          list[str] — trust levels along the path
                weakest_link:        str — lowest trust level encountered
                conditions_required: list[str] — all conditions that must be met
                reason:              str — human-readable explanation
        """
        required_ordinal = _TRUST_ORDER.get(required_level, 3)

        if source == target:
            return {
                "valid": True,
                "path": [source],
                "trust_path": [],
                "weakest_link": "high",
                "conditions_required": [],
                "reason": f"Source and target are the same component ('{source}').",
            }

        # BFS: queue holds (current_node, path, trust_levels, conditions, weakest_ordinal)
        queue: deque[tuple[str, list[str], list[str], list[str], int]] = deque()
        queue.append((source, [source], [], [], _TRUST_ORDER["high"]))
        visited: set[str] = {source}

        while queue:
            current, path, trust_levels, conditions, weakest_ordinal = queue.popleft()

            for edge in self._adjacency.get(current, []):
                neighbour = edge.to_component

                edge_ordinal = _TRUST_ORDER.get(edge.trust_level, 0)
                new_weakest = min(weakest_ordinal, edge_ordinal)
                new_path = path + [neighbour]
                new_trust_levels = trust_levels + [edge.trust_level]
                new_conditions = conditions + list(edge.conditions)

                if neighbour == target:
                    weakest_link = _TRUST_REVERSE.get(new_weakest, "none")
                    valid = new_weakest >= required_ordinal
                    reason = (
                        f"Trust chain from '{source}' to '{target}' "
                        f"{'is valid' if valid else 'is insufficient'} "
                        f"(weakest link: '{weakest_link}', "
                        f"required: '{required_level}'). "
                        f"Path: {' → '.join(new_path)}."
                    )
                    return {
                        "valid": valid,
                        "path": new_path,
                        "trust_path": new_trust_levels,
                        "weakest_link": weakest_link,
                        "conditions_required": list(dict.fromkeys(new_conditions)),
                        "reason": reason,
                    }

                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(
                        (neighbour, new_path, new_trust_levels, new_conditions, new_weakest)
                    )

        return {
            "valid": False,
            "path": [],
            "trust_path": [],
            "weakest_link": "none",
            "conditions_required": [],
            "reason": (
                f"No trust path exists from '{source}' to '{target}'."
            ),
        }

    # ── Full surface report ────────────────────────────────────────────────

    def compute_trust_surface(self) -> dict[str, Any]:
        """Compute the full trust graph as a structured report.

        Returns:
            A dict with keys:
                component_count:     int
                edge_count:          int
                components:          list[str]
                trust_matrix:        dict[str, dict[str, str]]
                most_trusted:        list[str]
                least_trusted:       list[str]
                isolated_components: list[str]
                high_trust_pairs:    list[dict]
                low_trust_pairs:     list[dict]
        """
        # Collect all unique components
        components_set: set[str] = set()
        for edge in self._edges:
            components_set.add(edge.from_component)
            components_set.add(edge.to_component)
        components = sorted(components_set)

        # Build trust matrix: from -> {to: trust_level}
        trust_matrix: dict[str, dict[str, str]] = {}
        for comp in components:
            trust_matrix[comp] = {}
        for edge in self._edges:
            trust_matrix.setdefault(edge.from_component, {})[edge.to_component] = edge.trust_level

        # Compute inbound trust scores (weighted by ordinal)
        inbound_scores: dict[str, float] = {c: 0.0 for c in components}
        inbound_counts: dict[str, int] = {c: 0 for c in components}
        for edge in self._edges:
            score = _TRUST_ORDER.get(edge.trust_level, 0)
            inbound_scores[edge.to_component] += score
            inbound_counts[edge.to_component] += 1

        # Most trusted: highest total inbound trust score
        sorted_by_trust = sorted(components, key=lambda c: inbound_scores[c], reverse=True)
        most_trusted = sorted_by_trust[:3] if len(sorted_by_trust) >= 3 else sorted_by_trust

        # Least trusted: lowest total inbound trust score among those with edges
        with_edges = [c for c in components if inbound_counts[c] > 0]
        sorted_least = sorted(with_edges, key=lambda c: inbound_scores[c])
        least_trusted = sorted_least[:3] if len(sorted_least) >= 3 else sorted_least

        # Isolated: no inbound or outbound edges
        isolated: list[str] = []
        for comp in components:
            has_out = bool(self._adjacency.get(comp))
            has_in = any(e.to_component == comp for e in self._edges)
            if not has_out and not has_in:
                isolated.append(comp)

        # High-trust pairs
        high_trust_pairs: list[dict[str, Any]] = []
        for edge in self._edges:
            if edge.trust_level == "high":
                high_trust_pairs.append({
                    "from": edge.from_component,
                    "to": edge.to_component,
                    "evidence": list(edge.evidence),
                })

        # Low/none trust pairs
        low_trust_pairs: list[dict[str, Any]] = []
        for edge in self._edges:
            if edge.trust_level in ("low", "none"):
                low_trust_pairs.append({
                    "from": edge.from_component,
                    "to": edge.to_component,
                    "trust_level": edge.trust_level,
                    "conditions": list(edge.conditions),
                })

        return {
            "component_count": len(components),
            "edge_count": len(self._edges),
            "components": components,
            "trust_matrix": trust_matrix,
            "most_trusted": most_trusted,
            "least_trusted": least_trusted,
            "isolated_components": isolated,
            "high_trust_pairs": high_trust_pairs,
            "low_trust_pairs": low_trust_pairs,
        }

    # ── Violation detection ────────────────────────────────────────────────

    def find_trust_violations(self) -> list[dict[str, Any]]:
        """Find trust paths that violate constitutional rules.

        Checks performed:
          1. High-trust paths that cross constitutional boundaries
             (C-1 life preservation, C-2 autonomy, C-3 legal compliance).
          2. Components trusted without evidence.
          3. Conditional trust without specified conditions.
          4. Circular trust dependencies.

        Returns:
            List of violation dicts, each with:
                component:       str — affected component
                violation_type:  str — category of violation
                description:     str — human-readable explanation
                severity:        str — "critical", "high", "medium", "low"
                related_article: str — constitutional article reference
        """
        violations: list[dict[str, Any]] = []

        # ── Check 1: High-trust across constitutional boundaries ──────────
        constitutional_boundaries = {
            "executor": {"C-1", "C-2", "C-3"},
            "runtime": {"C-1", "C-2"},
            "agent": {"C-1", "C-2", "C-3"},
        }

        for edge in self._edges:
            if edge.trust_level != "high":
                continue
            if edge.to_component in constitutional_boundaries:
                articles = constitutional_boundaries[edge.to_component]
                violations.append({
                    "component": edge.to_component,
                    "violation_type": "high_trust_constitutional_boundary",
                    "description": (
                        f"Component '{edge.from_component}' has high trust in "
                        f"'{edge.to_component}', which touches constitutional "
                        f"articles {', '.join(sorted(articles))}. "
                        f"High trust across this boundary must be explicitly gated."
                    ),
                    "severity": "high",
                    "related_article": ", ".join(sorted(articles)),
                })

        # ── Check 2: Trust without evidence ───────────────────────────────
        for edge in self._edges:
            if edge.trust_level in ("high", "medium") and not edge.evidence:
                violations.append({
                    "component": edge.to_component,
                    "violation_type": "trust_without_evidence",
                    "description": (
                        f"Component '{edge.from_component}' trusts "
                        f"'{edge.to_component}' at level '{edge.trust_level}' "
                        f"without documented evidence. C-5 requires transparent "
                        f"constraints and documented rationale."
                    ),
                    "severity": "medium",
                    "related_article": "C-5",
                })

        # ── Check 3: Conditional trust without conditions ─────────────────
        for edge in self._edges:
            if edge.trust_level == "conditional" and not edge.conditions:
                violations.append({
                    "component": edge.to_component,
                    "violation_type": "conditional_trust_no_conditions",
                    "description": (
                        f"Component '{edge.from_component}' has conditional trust in "
                        f"'{edge.to_component}' but no conditions are specified. "
                        f"Conditional trust without conditions is equivalent to "
                        f"unconstrained trust."
                    ),
                    "severity": "medium",
                    "related_article": "C-5",
                })

        # ── Check 4: Circular trust dependencies ──────────────────────────
        visited_global: set[str] = set()
        for component in self._adjacency:
            if component in visited_global:
                continue
            stack: list[tuple[str, list[str]]] = [(component, [component])]
            while stack:
                current, path = stack.pop()
                if current in visited_global and current != component:
                    continue
                for edge in self._adjacency.get(current, []):
                    neighbour = edge.to_component
                    if neighbour in path:
                        cycle = path[path.index(neighbour):] + [neighbour]
                        violations.append({
                            "component": neighbour,
                            "violation_type": "circular_trust_dependency",
                            "description": (
                                f"Circular trust detected: "
                                f"{' → '.join(cycle)}. "
                                f"Circular trust can mask transitive violations "
                                f"and undermine constitutional gating."
                            ),
                            "severity": "low",
                            "related_article": "C-5",
                        })
                    elif neighbour not in visited_global:
                        stack.append((neighbour, path + [neighbour]))
            visited_global.add(component)

        return violations

    # ── DOT visualization ──────────────────────────────────────────────────

    def trust_surface_to_dot(self) -> str:
        """Generate a Graphviz DOT format string for visualization.

        Edge colour-coding by trust level:
          - high:        green solid
          - medium:      blue solid
          - low:         orange solid
          - none:        red dashed
          - conditional: purple dotted

        Returns:
            A complete, valid DOT graph as a string.
        """
        lines: list[str] = []
        lines.append("digraph TrustSurface {")
        lines.append("    rankdir=LR;")
        lines.append("    fontname=\"Helvetica\";")
        lines.append("    node [fontname=\"Helvetica\", shape=box, style=rounded];")
        lines.append("    edge [fontname=\"Helvetica\", fontsize=10];")
        lines.append("")

        # Collect all unique components to declare nodes
        components: set[str] = set()
        for edge in self._edges:
            components.add(edge.from_component)
            components.add(edge.to_component)

        for comp in sorted(components):
            safe_name = comp.replace("-", "_").replace(" ", "_")
            lines.append(f'    {safe_name} [label="{comp}"];')

        lines.append("")

        # Emit edges
        emitted: set[tuple[str, str]] = set()
        for edge in self._edges:
            pair = (edge.from_component, edge.to_component)
            if pair in emitted:
                continue
            emitted.add(pair)

            from_safe = edge.from_component.replace("-", "_").replace(" ", "_")
            to_safe = edge.to_component.replace("-", "_").replace(" ", "_")
            style = _DOT_STYLE.get(edge.trust_level, _DOT_STYLE["none"])

            label_parts = [edge.trust_level]
            if edge.conditions:
                label_parts.append("\\n" + "\\n".join(edge.conditions))

            label = "".join(label_parts)

            lines.append(
                f'    {from_safe} -> {to_safe} '
                f'[color="{style["color"]}", style="{style["style"]}", '
                f'label="{label}"];'
            )

            if edge.bidirectional:
                lines.append(
                    f'    {to_safe} -> {from_safe} '
                    f'[color="{style["color"]}", style="{style["style"]}", '
                    f'label="{edge.trust_level} (bidirectional)"];'
                )

        lines.append("")
        lines.append("    // Legend")
        lines.append("    subgraph cluster_legend {")
        lines.append("        label=\"Trust Level Legend\";")
        lines.append("        fontname=\"Helvetica\";")
        lines.append("        legend_high    [label=\"high\",      color=green,  style=solid,  shape=plaintext];")
        lines.append("        legend_medium  [label=\"medium\",    color=blue,   style=solid,  shape=plaintext];")
        lines.append("        legend_low     [label=\"low\",       color=orange, style=solid,  shape=plaintext];")
        lines.append("        legend_none    [label=\"none\",      color=red,    style=dashed, shape=plaintext];")
        lines.append("        legend_cond    [label=\"conditional\", color=purple, style=dotted, shape=plaintext];")
        lines.append("    }")
        lines.append("}")

        return "\n".join(lines) + "\n"

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trust surface."""
        return {
            "edges": [edge.to_dict() for edge in self._edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrustSurface:
        """Deserialize from a dict."""
        edges_data = data.get("edges", [])
        edges = [TrustEdge.from_dict(e) for e in edges_data]
        return cls(edges=edges)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level builders and validators
# ═══════════════════════════════════════════════════════════════════════════════


def build_default_trust_surface() -> TrustSurface:
    """Build a default trust surface from known HLF components.

    Encodes the trust relationships that define the HLF pipeline:
      - Compiler → Verifier, Formatter, Linter (medium)
      - Verifier → Executor (high — gating execution)
      - Executor → Runtime (high — invocation)
      - Governor → Compiler, Executor (high — blocking)
      - Agent → Executor (conditional — delegation)
      - Data channel → Instruction channel (low — boundary crossing)
      - User → Compiler (high — source provision)
      - Memory → Agent (medium — read)
      - Network → Agent (low — external input)

    Returns:
        A TrustSurface pre-populated with standard HLF edges.
    """
    edges: list[TrustEdge] = [
        # ── Core pipeline ──────────────────────────────────────────────────
        TrustEdge(
            from_component="compiler",
            to_component="verifier",
            trust_level="medium",
            evidence=["compiler produces verified bytecode"],
        ),
        TrustEdge(
            from_component="verifier",
            to_component="executor",
            trust_level="high",
            evidence=["verifier gates execution — Phase 3 guarantee"],
        ),
        TrustEdge(
            from_component="executor",
            to_component="runtime",
            trust_level="high",
            evidence=["executor invokes runtime for two-channel execution"],
        ),
        # ── Governor gating ────────────────────────────────────────────────
        TrustEdge(
            from_component="governor",
            to_component="compiler",
            trust_level="high",
            evidence=["governor blocks compilation on ethical violation"],
        ),
        TrustEdge(
            from_component="governor",
            to_component="executor",
            trust_level="high",
            evidence=["governor blocks execution via governor gate"],
        ),
        # ── Compiler tooling ───────────────────────────────────────────────
        TrustEdge(
            from_component="compiler",
            to_component="formatter",
            trust_level="medium",
            evidence=["compiler uses formatter for canonical output"],
        ),
        TrustEdge(
            from_component="compiler",
            to_component="linter",
            trust_level="medium",
            evidence=["compiler uses linter for static analysis"],
        ),
        # ── Channel boundary ───────────────────────────────────────────────
        TrustEdge(
            from_component="data_channel",
            to_component="instruction_channel",
            trust_level="low",
            conditions=[
                "data must pass provenance verification",
                "capability manifest must authorise crossing",
            ],
            evidence=["data crosses channels — provenance degrades"],
        ),
        # ── Agent delegation ───────────────────────────────────────────────
        TrustEdge(
            from_component="agent",
            to_component="executor",
            trust_level="conditional",
            conditions=[
                "governor check must pass",
                "agent must hold valid capability manifest",
                "provenance chain must trace to authorised source",
            ],
            evidence=["agent delegates to executor under governance"],
        ),
        # ── User source ────────────────────────────────────────────────────
        TrustEdge(
            from_component="user",
            to_component="compiler",
            trust_level="high",
            evidence=["user provides source code for compilation"],
        ),
        # ── Memory and network ─────────────────────────────────────────────
        TrustEdge(
            from_component="memory",
            to_component="agent",
            trust_level="medium",
            evidence=["agent reads from memory for context and history"],
        ),
        TrustEdge(
            from_component="network",
            to_component="agent",
            trust_level="low",
            conditions=[
                "network input must be provenance-tracked",
                "PII guard must inspect before agent consumption",
            ],
            evidence=["agent receives network input — untrusted source"],
        ),
    ]

    return TrustSurface(edges=edges)


def validate_trust_against_constitution(
    surface: TrustSurface,
    constitutional_articles: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Validate trust surface edges against constitutional rules.

    Checks each high-trust edge against:
      - C-1 (Human life preservation): executor/runtime edges must be gated.
      - C-2 (Human autonomy respect): agent edges must not bypass consent.
      - C-3 (Legal compliance): network-sourced trust must be minimal.

    Args:
        surface:                 The TrustSurface to validate.
        constitutional_articles: Optional dict of articles. Defaults to the
                                 constitution.ARTICLES if not provided.

    Returns:
        List of violation dicts, each with:
            component:       str
            violation_type:  str
            description:     str
            severity:        str
            related_article: str
    """
    if constitutional_articles is None:
        try:
            from hlf_mcp.hlf.ethics.constitution import ARTICLES
            constitutional_articles = ARTICLES
        except ImportError:
            constitutional_articles = {}

    violations: list[dict[str, Any]] = []

    # C-1 boundary components: high trust into these is concerning
    c1_sensitive = {"executor", "runtime"}
    # C-2 boundary components: autonomy-respecting gates required
    c2_sensitive = {"agent"}
    # C-3 boundary components: legality must be verifiable
    c3_sensitive = {"network", "agent"}

    for edge in surface._edges:
        if edge.trust_level != "high":
            continue

        # C-1: high trust into executor/runtime must be gated
        if edge.to_component in c1_sensitive and "C-1" in (constitutional_articles or {}):
            violations.append({
                "component": edge.to_component,
                "violation_type": "high_trust_c1_boundary",
                "description": (
                    f"High trust from '{edge.from_component}' into "
                    f"'{edge.to_component}' touches C-1 (life preservation). "
                    f"Trust at this boundary must be explicitly gated with a "
                    f"governor check."
                ),
                "severity": "critical",
                "related_article": "C-1",
            })

        # C-2: high trust into agent must respect autonomy
        if edge.to_component in c2_sensitive and "C-2" in (constitutional_articles or {}):
            violations.append({
                "component": edge.to_component,
                "violation_type": "high_trust_c2_boundary",
                "description": (
                    f"High trust from '{edge.from_component}' into "
                    f"'{edge.to_component}' touches C-2 (autonomy respect). "
                    f"Ensure agent actions are consent-gated."
                ),
                "severity": "high",
                "related_article": "C-2",
            })

        # C-3: high trust sourced from network is problematic
        if edge.from_component in c3_sensitive and "C-3" in (constitutional_articles or {}):
            if edge.to_component not in c3_sensitive:
                violations.append({
                    "component": edge.to_component,
                    "violation_type": "high_trust_c3_boundary",
                    "description": (
                        f"High trust from '{edge.from_component}' to "
                        f"'{edge.to_component}' touches C-3 (legal compliance). "
                        f"Network-sourced trust should be low or conditional."
                    ),
                    "severity": "high",
                    "related_article": "C-3",
                })

    return violations


# ═══════════════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "TrustEdge",
    "TrustSurface",
    "build_default_trust_surface",
    "validate_trust_against_constitution",
]
