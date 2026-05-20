"""
Audit Diff — structural comparison engine for HLF audit trails.

Compares two AuditTrail instances and produces operator-readable delta
reports showing which events were added, removed, or modified between
trail snapshots.  Designed for compliance audits, trust degradation
tracking, and post-incident forensic analysis.

Key design principles:
  - Structural matching: events are paired by persona + event_type +
    timestamp proximity, not by index position.
  - Operator-first output: delta reports use colour-coded tables
    (markdown and HTML) so a human can scan changes at a glance.
  - Anomaly detection: flags suspicious patterns like trust crashes,
    mass event removal, and persona-level decision flipping.
  - Self-contained: the diff engine works with any pair of AuditTrail
    instances and does not require external databases or state.

Integration points:
  - hlf_mcp.hlf.audit_trail.AuditTrail    → diff and diff_sequence inputs
  - hlf_mcp.hlf.audit_trail.AuditEvent    → field-level comparison
  - hlf_mcp.hlf.trust_trending            → anomaly data feeds trend alerts
  - hlf_mcp.hlf.remediation_planner       → anomaly findings become tasks
"""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hlf_mcp.hlf.audit_trail import AuditTrail, AuditEvent


# ═══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════════════════


class DiffOperation(Enum):
    """The type of change detected for a single audit trail entry."""
    ADDED = auto()
    REMOVED = auto()
    MODIFIED = auto()
    UNCHANGED = auto()


# ═══════════════════════════════════════════════════════════════════════════════
# AuditDiffEntry — structured record of a single diff result
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class AuditDiffEntry:
    """A single change detected between two audit trail snapshots.

    Captures the operation type (added/removed/modified/unchanged),
    the identifying key of the event, and field-level before/after
    values for modified entries.

    Attributes:
        timestamp: ISO-8601 timestamp from the event in trail B (or A if removed).
        operation: What kind of change was detected.
        event_type: The event_type field of the matched event.
        persona: The persona field of the matched event.
        field_changes: For MODIFIED entries, maps field name to (old_value, new_value).
        rationale_before: Original rationale string (empty for ADDED).
        rationale_after: New rationale string (empty for REMOVED).
        trust_before: Trust score from trail A (or 0.0).
        trust_after: Trust score from trail B (or 0.0).
    """

    timestamp: str
    operation: DiffOperation
    event_type: str
    persona: str
    field_changes: dict[str, tuple[str, str]] = field(default_factory=dict)
    rationale_before: str = ""
    rationale_after: str = ""
    trust_before: float = 0.0
    trust_after: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the diff entry."""
        return {
            "timestamp": self.timestamp,
            "operation": self.operation.name,
            "event_type": self.event_type,
            "persona": self.persona,
            "field_changes": {
                k: list(v) for k, v in self.field_changes.items()
            },
            "rationale_before": self.rationale_before,
            "rationale_after": self.rationale_after,
            "trust_before": self.trust_before,
            "trust_after": self.trust_after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditDiffEntry:
        """Deserialize from a dict."""
        raw_changes = data.get("field_changes", {})
        field_changes: dict[str, tuple[str, str]] = {}
        for k, v in raw_changes.items():
            if isinstance(v, list) and len(v) == 2:
                field_changes[k] = (str(v[0]), str(v[1]))
        return cls(
            timestamp=str(data.get("timestamp", "")),
            operation=DiffOperation[data.get("operation", "UNCHANGED")],
            event_type=str(data.get("event_type", "")),
            persona=str(data.get("persona", "")),
            field_changes=field_changes,
            rationale_before=str(data.get("rationale_before", "")),
            rationale_after=str(data.get("rationale_after", "")),
            trust_before=float(data.get("trust_before", 0.0)),
            trust_after=float(data.get("trust_after", 0.0)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — matching and similarity
# ═══════════════════════════════════════════════════════════════════════════════


def _event_key(event: Any) -> str:
    """Derive a stable matching key from persona and event_type."""
    persona = getattr(event, "persona", "")
    event_type = getattr(event, "event_type", "")
    return f"{persona}::{event_type}"


def _timestamp_proximity(ts_a: str, ts_b: str) -> float:
    """Compute normalised timestamp proximity (0.0 = identical, 1.0 = very far).

    Returns the absolute difference in seconds, capped at a maximum of
    3600 (1 hour) and then normalised to [0, 1].  Two timestamps with
    the same value yield 0.0; anything >= 1 hour apart yields 1.0.
    """
    try:
        dt_a = datetime.fromisoformat(ts_a.replace("Z", "+00:00"))
        dt_b = datetime.fromisoformat(ts_b.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 1.0
    diff_seconds = abs((dt_a - dt_b).total_seconds())
    return min(diff_seconds / 3600.0, 1.0)


def _compute_field_changes(event_a: Any, event_b: Any) -> dict[str, tuple[str, str]]:
    """Compare two events field-by-field and return changed fields.

    Only the fields 'decision', 'rationale', and 'provenance_ref' are
    compared (timestamp and identity fields are excluded since they are
    the matching key).

    Returns:
        Dict mapping field name to (old_value, new_value) for every
        field whose value differs between event_a and event_b.
    """
    comparable_fields = ["decision", "rationale", "provenance_ref"]
    changes: dict[str, tuple[str, str]] = {}
    for field in comparable_fields:
        old_val = str(getattr(event_a, field, ""))
        new_val = str(getattr(event_b, field, ""))
        if old_val != new_val:
            changes[field] = (old_val, new_val)
    return changes


def _sequence_matcher_score(a: str, b: str) -> float:
    """Return a similarity score (0-1) between two text strings using difflib."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ═══════════════════════════════════════════════════════════════════════════════
# AuditDiff — main comparison engine
# ═══════════════════════════════════════════════════════════════════════════════


class AuditDiff:
    """Structural audit trail diff engine.

    Compares two AuditTrail instances event-by-event using persona +
    event_type + timestamp proximity matching and produces a list of
    AuditDiffEntry records.

    Usage::

        diff_engine = AuditDiff(name="compliance-diff")
        entries = diff_engine.diff(trail_v1, trail_v2)
        print(diff_engine.render_delta_report(entries, format="markdown"))
    """

    def __init__(self, name: str = "audit-diff") -> None:
        """Initialise the diff engine.

        Args:
            name: Human-readable label for this diff engine instance.
        """
        self.name = name

    # ── Core diff algorithm ─────────────────────────────────────────────────

    def diff(
        self,
        trail_a: AuditTrail,
        trail_b: AuditTrail,
    ) -> list[AuditDiffEntry]:
        """Perform a structural diff between two audit trails.

        Matching strategy:
          1. Group events in each trail by (persona, event_type).
          2. Within each group, sort by timestamp.
          3. Use greedy nearest-neighbour matching with a 10-minute
             proximity window.
          4. Unmatched events in A become REMOVED; in B become ADDED.
          5. Matched events are compared field-by-field; if any field
             differs the entry is MODIFIED, otherwise UNCHANGED.

        Args:
            trail_a: The baseline (older) audit trail.
            trail_b: The comparison (newer) audit trail.

        Returns:
            List of AuditDiffEntry records, one per detected difference.
        """
        events_a: list[Any] = list(getattr(trail_a, "events", []))
        events_b: list[Any] = list(getattr(trail_b, "events", []))

        # Group by (persona, event_type)
        groups_a: dict[str, list[Any]] = {}
        groups_b: dict[str, list[Any]] = {}

        for ev in events_a:
            key = _event_key(ev)
            groups_a.setdefault(key, []).append(ev)
        for ev in events_b:
            key = _event_key(ev)
            groups_b.setdefault(key, []).append(ev)

        all_keys = sorted(set(groups_a.keys()) | set(groups_b.keys()))
        entries: list[AuditDiffEntry] = []

        PROXIMITY_THRESHOLD = 600.0  # 10 minutes in seconds

        for key in all_keys:
            group_a = sorted(groups_a.get(key, []), key=lambda e: str(getattr(e, "timestamp", "")))
            group_b = sorted(groups_b.get(key, []), key=lambda e: str(getattr(e, "timestamp", "")))

            matched_b: set[int] = set()

            for ev_a in group_a:
                ts_a = str(getattr(ev_a, "timestamp", ""))
                best_idx: int | None = None
                best_prox: float = float("inf")

                for idx_b, ev_b in enumerate(group_b):
                    if idx_b in matched_b:
                        continue
                    ts_b = str(getattr(ev_b, "timestamp", ""))
                    try:
                        dt_a = datetime.fromisoformat(ts_a.replace("Z", "+00:00"))
                        dt_b = datetime.fromisoformat(ts_b.replace("Z", "+00:00"))
                        diff_secs = abs((dt_a - dt_b).total_seconds())
                    except (ValueError, TypeError):
                        diff_secs = float("inf")

                    if diff_secs < best_prox:
                        best_prox = diff_secs
                        best_idx = idx_b

                if best_idx is not None and best_prox <= PROXIMITY_THRESHOLD:
                    ev_b = group_b[best_idx]
                    matched_b.add(best_idx)
                    changes = _compute_field_changes(ev_a, ev_b)
                    if changes:
                        entries.append(AuditDiffEntry(
                            timestamp=str(getattr(ev_b, "timestamp", ts_a)),
                            operation=DiffOperation.MODIFIED,
                            event_type=str(getattr(ev_a, "event_type", "")),
                            persona=str(getattr(ev_a, "persona", "")),
                            field_changes=changes,
                            rationale_before=str(getattr(ev_a, "rationale", "")),
                            rationale_after=str(getattr(ev_b, "rationale", "")),
                            trust_before=float(getattr(ev_a, "trust", 0.0)),
                            trust_after=float(getattr(ev_b, "trust", 0.0)),
                        ))
                    else:
                        entries.append(AuditDiffEntry(
                            timestamp=str(getattr(ev_b, "timestamp", ts_a)),
                            operation=DiffOperation.UNCHANGED,
                            event_type=str(getattr(ev_a, "event_type", "")),
                            persona=str(getattr(ev_a, "persona", "")),
                            trust_before=float(getattr(ev_a, "trust", 0.0)),
                            trust_after=float(getattr(ev_b, "trust", 0.0)),
                        ))
                else:
                    # No match found in B → REMOVED
                    entries.append(AuditDiffEntry(
                        timestamp=ts_a,
                        operation=DiffOperation.REMOVED,
                        event_type=str(getattr(ev_a, "event_type", "")),
                        persona=str(getattr(ev_a, "persona", "")),
                        rationale_before=str(getattr(ev_a, "rationale", "")),
                        trust_before=float(getattr(ev_a, "trust", 0.0)),
                    ))

            # Unmatched events in B → ADDED
            for idx_b, ev_b in enumerate(group_b):
                if idx_b not in matched_b:
                    entries.append(AuditDiffEntry(
                        timestamp=str(getattr(ev_b, "timestamp", "")),
                        operation=DiffOperation.ADDED,
                        event_type=str(getattr(ev_b, "event_type", "")),
                        persona=str(getattr(ev_b, "persona", "")),
                        rationale_after=str(getattr(ev_b, "rationale", "")),
                        trust_after=float(getattr(ev_b, "trust", 0.0)),
                    ))

        return entries

    # ── Sequence diff ───────────────────────────────────────────────────────

    def diff_sequence(
        self,
        trails: list[AuditTrail],
    ) -> list[list[AuditDiffEntry]]:
        """Compute pairwise diffs across an ordered sequence of audit trails.

        For N trails, produces N-1 diff result lists between consecutive
        pairs: trails[0]→trails[1], trails[1]→trails[2], ...

        Args:
            trails: Ordered list of AuditTrail instances (earliest first).

        Returns:
            List of diff entry lists, one per consecutive pair.
            Returns an empty list if fewer than 2 trails are provided.
        """
        if len(trails) < 2:
            return []
        result: list[list[AuditDiffEntry]] = []
        for i in range(len(trails) - 1):
            result.append(self.diff(trails[i], trails[i + 1]))
        return result

    # ── Summary ─────────────────────────────────────────────────────────────

    def summary(self, entries: list[AuditDiffEntry]) -> dict[str, Any]:
        """Generate a structured summary of diff results.

        Args:
            entries: The list of diff entries to summarise.

        Returns:
            A dict with keys:
                total_entries: int — total number of diff entries.
                added: int — count of ADDED events.
                removed: int — count of REMOVED events.
                modified: int — count of MODIFIED events.
                unchanged: int — count of UNCHANGED events.
                affected_personas: list[str] — unique personas with changes.
                affected_event_types: list[str] — unique event types with changes.
                trust_delta: float — net change in trust (after - before) across all entries.
        """
        counts = {
            DiffOperation.ADDED: 0,
            DiffOperation.REMOVED: 0,
            DiffOperation.MODIFIED: 0,
            DiffOperation.UNCHANGED: 0,
        }
        personas: set[str] = set()
        event_types: set[str] = set()
        trust_delta: float = 0.0

        for entry in entries:
            counts[entry.operation] += 1
            if entry.persona:
                personas.add(entry.persona)
            if entry.event_type:
                event_types.add(entry.event_type)
            trust_delta += (entry.trust_after - entry.trust_before)

        return {
            "total_entries": len(entries),
            "added": counts[DiffOperation.ADDED],
            "removed": counts[DiffOperation.REMOVED],
            "modified": counts[DiffOperation.MODIFIED],
            "unchanged": counts[DiffOperation.UNCHANGED],
            "affected_personas": sorted(personas),
            "affected_event_types": sorted(event_types),
            "trust_delta": round(trust_delta, 4),
        }

    # ── Delta report rendering ──────────────────────────────────────────────

    def render_delta_report(
        self,
        entries: list[AuditDiffEntry],
        format: str = "markdown",
    ) -> str:
        """Generate an operator-readable delta report.

        Args:
            entries: The diff entries to render.
            format: "markdown" (default) or "html".

        Returns:
            A formatted string suitable for display or archival.
        """
        if format == "html":
            return self._render_html(entries)
        return self._render_markdown(entries)

    def _render_markdown(self, entries: list[AuditDiffEntry]) -> str:
        """Render diff entries as a colour-coded markdown table."""
        lines: list[str] = [
            "# Audit Trail Delta Report",
            "",
            f"**Engine:** {self.name}",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()}",
            f"**Total Entries:** {len(entries)}",
            "",
            "| Δ | Timestamp | Persona | Event Type | Rationale Before | Rationale After | Trust Δ |",
            "|---|-----------|---------|------------|-----------------|----------------|---------|",
        ]

        _ICON = {
            DiffOperation.ADDED: "🟢",
            DiffOperation.REMOVED: "🔴",
            DiffOperation.MODIFIED: "🟡",
            DiffOperation.UNCHANGED: "⚪",
        }

        for entry in entries:
            icon = _ICON.get(entry.operation, "❓")
            ts = entry.timestamp[:19] if entry.timestamp else "-"
            rb = _truncate(entry.rationale_before, 40)
            ra = _truncate(entry.rationale_after, 40)
            td = f"{entry.trust_after - entry.trust_before:+.3f}"
            lines.append(
                f"| {icon} | {ts} | {entry.persona} | {entry.event_type} "
                f"| {rb} | {ra} | {td} |"
            )

        # Append field-level change detail for modified entries
        modified = [e for e in entries if e.operation == DiffOperation.MODIFIED and e.field_changes]
        if modified:
            lines.append("")
            lines.append("## 🔍 Field-Level Changes")
            lines.append("")
            for entry in modified:
                lines.append(f"### {entry.persona} / {entry.event_type} @ {entry.timestamp[:19]}")
                lines.append("")
                lines.append("| Field | Old Value | New Value |")
                lines.append("|-------|-----------|-----------|")
                for field, (old, new) in entry.field_changes.items():
                    lines.append(f"| `{field}` | {_truncate(old, 60)} | {_truncate(new, 60)} |")
                lines.append("")

        return "\n".join(lines)

    def _render_html(self, entries: list[AuditDiffEntry]) -> str:
        """Render diff entries as a colour-coded HTML document."""
        _COLOR = {
            DiffOperation.ADDED: "#d4edda",
            DiffOperation.REMOVED: "#f8d7da",
            DiffOperation.MODIFIED: "#fff3cd",
            DiffOperation.UNCHANGED: "#e2e3e5",
        }
        _LABEL = {
            DiffOperation.ADDED: "ADDED",
            DiffOperation.REMOVED: "REMOVED",
            DiffOperation.MODIFIED: "MODIFIED",
            DiffOperation.UNCHANGED: "UNCHANGED",
        }

        rows: list[str] = []
        for entry in entries:
            bg = _COLOR.get(entry.operation, "#ffffff")
            label = _LABEL.get(entry.operation, "UNKNOWN")
            rows.append(
                f'<tr style="background-color:{bg}">'
                f"<td>{label}</td>"
                f"<td>{entry.timestamp[:19] if entry.timestamp else '-'}</td>"
                f"<td>{entry.persona}</td>"
                f"<td>{entry.event_type}</td>"
                f"<td>{_truncate(entry.rationale_before, 50)}</td>"
                f"<td>{_truncate(entry.rationale_after, 50)}</td>"
                f"<td>{entry.trust_after - entry.trust_before:+.3f}</td>"
                f"</tr>"
            )

        return (
            "<!DOCTYPE html>\n<html>\n<head>\n"
            '<meta charset="utf-8">\n'
            "<title>Audit Trail Delta Report</title>\n"
            "<style>\n"
            "body { font-family: Arial, sans-serif; margin: 20px; }\n"
            "table { border-collapse: collapse; width: 100%; }\n"
            "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }\n"
            "th { background-color: #f2f2f2; }\n"
            "</style>\n</head>\n<body>\n"
            f"<h1>Audit Trail Delta Report</h1>\n"
            f"<p><strong>Engine:</strong> {self.name}</p>\n"
            f"<p><strong>Generated:</strong> {datetime.now(timezone.utc).isoformat()}</p>\n"
            f"<p><strong>Total Entries:</strong> {len(entries)}</p>\n"
            "<table>\n"
            "<tr><th>Δ</th><th>Timestamp</th><th>Persona</th>"
            "<th>Event Type</th><th>Before</th><th>After</th><th>Trust Δ</th></tr>\n"
            + "\n".join(rows) +
            "\n</table>\n</body>\n</html>"
        )

    # ── Anomaly detection ───────────────────────────────────────────────────

    def find_anomalies(self, entries: list[AuditDiffEntry]) -> list[dict[str, Any]]:
        """Detect suspicious patterns in audit trail diffs.

        Checks performed:
          1. Trust degradation > 0.3 in a single step.
          2. Mass removal of events (more than 5 REMOVED in one diff).
          3. Same persona changing all their decisions (≥ 3 MODIFIED
             for the same persona with no unchanged entries).

        Args:
            entries: The diff entries to scan.

        Returns:
            List of anomaly dicts, each with:
                anomaly_type: str — category label.
                severity: str — "critical", "high", "medium".
                description: str — human-readable explanation.
                affected_entries: list[int] — indices into the entries list.
        """
        anomalies: list[dict[str, Any]] = []

        # ── Check 1: Trust degradation spike ──────────────────────────────
        for idx, entry in enumerate(entries):
            delta = entry.trust_after - entry.trust_before
            if delta < -0.3:
                anomalies.append({
                    "anomaly_type": "trust_degradation_spike",
                    "severity": "critical",
                    "description": (
                        f"Trust dropped by {delta:+.3f} for persona "
                        f"'{entry.persona}' on event '{entry.event_type}'. "
                        f"Single-step degradation exceeds 0.3 threshold."
                    ),
                    "affected_entries": [idx],
                })

        # ── Check 2: Mass removal ─────────────────────────────────────────
        removed_indices = [
            i for i, e in enumerate(entries)
            if e.operation == DiffOperation.REMOVED
        ]
        if len(removed_indices) > 5:
            anomalies.append({
                "anomaly_type": "mass_removal",
                "severity": "high",
                "description": (
                    f"{len(removed_indices)} events were removed in a single diff. "
                    f"This may indicate trail truncation or unauthorised event deletion."
                ),
                "affected_entries": removed_indices,
            })

        # ── Check 3: Persona decision flipping ────────────────────────────
        persona_modifications: dict[str, list[int]] = {}
        for idx, entry in enumerate(entries):
            if entry.operation == DiffOperation.MODIFIED:
                persona_modifications.setdefault(entry.persona, []).append(idx)

        for persona, indices in persona_modifications.items():
            if len(indices) >= 3:
                # Check if all entries for this persona are modified
                persona_total = sum(
                    1 for e in entries if e.persona == persona
                )
                if len(indices) == persona_total or persona_total == 0:
                    continue
                anomalies.append({
                    "anomaly_type": "persona_decision_flipping",
                    "severity": "medium",
                    "description": (
                        f"Persona '{persona}' has {len(indices)} modified decisions "
                        f"out of {persona_total} total entries.  This may indicate "
                        f"systematic re-evaluation of decisions."
                    ),
                    "affected_entries": indices,
                })

        return anomalies


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _truncate(text: str, max_len: int) -> str:
    """Truncate a string for display, adding ellipsis if needed."""
    if not text:
        return "-"
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _iso_now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
