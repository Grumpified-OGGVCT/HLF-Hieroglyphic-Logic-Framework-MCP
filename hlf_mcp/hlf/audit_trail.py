"""
Human-Readable Audit Trail — chronological, narrative execution record for HLF.

Every compiled program execution in HLF generates provenance chains (data lineage)
and verification reports (proof results).  This module synthesises both into a
single, operator-friendly audit trail that reads like a person wrote it — not
like a log dump.

Key design principles:
  - Human-readable first: every AuditEvent tells a story in plain English.
  - Self-contained outputs: to_markdown() and to_html() produce complete
    documents with no external dependencies.
  - Integrates with InsAIts: if a verification report carries an AST
    reference, decompile() is used to enrich explanations.
  - Immutability-friendly: AuditTrail is append-only; AuditEvent fields
    are never mutated after construction.

Integration points:
  - hlf_mcp.hlf.two_channel_executor.ProvenanceChain → data lineage events
  - hlf_mcp.hlf.formal_verifier.VerificationReport → proof gate events
  - hlf_mcp.hlf.insaits → human-readable decompilation
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hlf_mcp.hlf.formal_verifier import VerificationReport
from hlf_mcp.hlf.insaits import decompile, similarity_gate
from hlf_mcp.hlf.two_channel_executor import ProvenanceChain


# ═══════════════════════════════════════════════════════════════════════════════
# Trust tier → human-friendly label mapping
# ═══════════════════════════════════════════════════════════════════════════════

_TIER_LABELS: dict[str, str] = {
    "hearth": "Hearth (Maximum Trust)",
    "trusted": "Trusted",
    "forge": "Forge (Approved)",
    "approved": "Approved",
    "watched": "Watched",
    "advisory": "Advisory",
    "untrusted": "Untrusted",
    "sovereign": "Sovereign (No Gate)",
}

_TRUST_COLOR: dict[str, str] = {
    "hearth": "#1a7a1a",
    "trusted": "#2d8f2d",
    "forge": "#d4a017",
    "approved": "#d4a017",
    "watched": "#c97100",
    "advisory": "#b85c00",
    "untrusted": "#c0392b",
    "sovereign": "#7f8c8d",
}

_TRUST_BADGE: dict[str, str] = {
    "hearth": "🛡️ HEARTH",
    "trusted": "✅ TRUSTED",
    "forge": "🔨 FORGE",
    "approved": "👍 APPROVED",
    "watched": "👁️ WATCHED",
    "advisory": "⚠️ ADVISORY",
    "untrusted": "🚫 UNTRUSTED",
    "sovereign": "🌐 SOVEREIGN",
}


def _iso_now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _trust_descriptor(trust: float) -> str:
    """Return a human-readable trust-level adjective for a numeric score."""
    if trust >= 0.95:
        return "excellent"
    if trust >= 0.85:
        return "high"
    if trust >= 0.70:
        return "good"
    if trust >= 0.50:
        return "moderate"
    if trust >= 0.30:
        return "low"
    if trust > 0.0:
        return "very low"
    return "zero"


def _hash_ref(data: str) -> str:
    """Produce a short (16-char) SHA-256 reference for a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


# ═══════════════════════════════════════════════════════════════════════════════
# AuditEvent
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class AuditEvent:
    """A single event in the human-readable audit trail.

    Every event is a self-contained narrative: what happened, who decided it,
    why they decided it, and which provenance entry backs it up.

    The ``decision`` and ``rationale`` fields are deliberately written in
    plain English so that an operator can skim the audit trail and understand
    the full execution story without decoding machine-level artefacts.
    """

    timestamp: str
    event_type: str          # "execution_gate", "verification", "provenance_check", "trust_boundary"
    persona: str             # "compiler", "verifier", "executor", "governor"
    decision: str            # human-readable decision description
    rationale: str           # why this decision was made
    provenance_ref: str = "" # reference to provenance chain entry (hash or index)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the audit event for transport or storage."""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "persona": self.persona,
            "decision": self.decision,
            "rationale": self.rationale,
            "provenance_ref": self.provenance_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditEvent:
        """Deserialize from a dict."""
        return cls(
            timestamp=str(data.get("timestamp", "")),
            event_type=str(data.get("event_type", "")),
            persona=str(data.get("persona", "")),
            decision=str(data.get("decision", "")),
            rationale=str(data.get("rationale", "")),
            provenance_ref=str(data.get("provenance_ref", "")),
        )

    def one_line(self) -> str:
        """Return a single-line operator summary of this event."""
        return (
            f"[{self.timestamp[:19]}] {self.persona:12} | {self.event_type:20} "
            f"| {self.decision}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AuditTrail
# ═══════════════════════════════════════════════════════════════════════════════


class AuditTrail:
    """Human-readable chronological audit trail for HLF executions.

    Aggregates AuditEvents into a coherent narrative.  Supports filtering by
    persona or event type, sorting chronologically, and rendering as both
    Markdown and self-contained HTML.

    Typical usage::

        trail = AuditTrail(execution_id="exec-42", tier="hearth")
        trail.add_gate_decision("PROCEED", report, "hearth")
        trail.add_provenance_event(chain, "trust_boundary", "governor")
        print(trail.to_markdown())
    """

    def __init__(
        self,
        events: list[AuditEvent] | None = None,
        execution_id: str = "",
        tier: str = "hearth",
    ) -> None:
        self.events: list[AuditEvent] = list(events) if events else []
        self.execution_id = execution_id or _hash_ref(_iso_now())
        self.tier = tier

    # ── Append helpers ──────────────────────────────────────────────────────

    def add_event(self, event: AuditEvent) -> None:
        """Add an audit event to the trail."""
        self.events.append(event)

    def add_gate_decision(
        self,
        decision: str,
        report: VerificationReport,
        tier: str,
    ) -> AuditEvent:
        """Record a verification gate decision as a human-readable event.

        Produces an AuditEvent that explains *what* the gate decided, *why*
        (citing specific proof counts), and what it means for the operator.

        Args:
            decision: Gate decision string (e.g. "PROCEED", "BLOCK", "WARN").
            report: The VerificationReport that informed the decision.
            tier: The trust tier at which the gate operated.

        Returns:
            The newly created AuditEvent (already appended to the trail).
        """
        tier_label = _TIER_LABELS.get(tier, tier.title())
        proven = report.proven_count
        failed = report.failed_count
        total = report.total_count

        if decision.upper() == "PROCEED":
            rationale = (
                f"All {total} verification properties passed at the {tier_label} tier. "
                f"The verifier confirmed {proven} proof(s) with zero failures. "
                f"Execution is permitted to continue under normal trust assumptions."
            )
        elif decision.upper() == "BLOCK":
            blocking = report.failed_count
            rationale = (
                f"{blocking} of {total} verification properties failed at the "
                f"{tier_label} tier.  This tier requires all properties to be proven "
                f"before execution can proceed.  The gate has blocked execution to "
                f"prevent unverified code from running."
            )
        elif decision.upper() == "WARN":
            rationale = (
                f"{failed} verification issue(s) detected out of {total} properties "
                f"at the {tier_label} tier.  This tier permits execution with warnings. "
                f"The operator should review the {failed} flagged result(s) before "
                f"trusting the output."
            )
        else:
            rationale = (
                f"Gate decision '{decision}' was recorded at the {tier_label} tier "
                f"with {proven}/{total} properties proven.  See the attached "
                f"verification report for full details."
            )

        event = AuditEvent(
            timestamp=_iso_now(),
            event_type="execution_gate",
            persona="verifier",
            decision=f"Gate decision: {decision} at {tier_label}",
            rationale=rationale,
            provenance_ref=report.summary()[:80],
        )
        self.events.append(event)
        return event

    def add_provenance_event(
        self,
        chain: ProvenanceChain,
        event_type: str,
        persona: str,
    ) -> AuditEvent:
        """Record a provenance-related event with a human-readable narrative.

        Converts the machine provenance chain into an operator-friendly
        description of where data came from, what trust it carries, and what
        transformations it has undergone.

        Args:
            chain: The ProvenanceChain to narrate.
            event_type: Category label (e.g. "trust_boundary", "provenance_check").
            persona: Who is recording this event (e.g. "governor", "executor").

        Returns:
            The newly created AuditEvent (already appended to the trail).
        """
        trust = chain.trust
        descriptor = _trust_descriptor(trust)
        source = chain.source or "unknown"
        path_len = len(chain.path)
        proof_hash = chain.is_immutable_proof()[:16]

        if event_type == "trust_boundary":
            decision = (
                f"Data crossed a trust boundary into domain '{source}'. "
                f"Trust reset to baseline ({trust:.2f})."
            )
            rationale = (
                f"When data moves between trust domains its previous trust score "
                f"is no longer valid.  The provenance chain records {path_len} "
                f"transformation step(s) before this crossing.  The new source "
                f"'{source}' starts with a default baseline trust of {trust:.2f}, "
                f"which is considered {descriptor}.  "
                f"Immutable proof: {proof_hash}."
            )
        elif event_type == "provenance_check":
            trust_pct = int(trust * 100)
            decision = (
                f"Provenance verified for source '{source}'. "
                f"Trust score: {trust_pct}% ({descriptor})."
            )
            rationale = (
                f"The provenance chain traces data origin to '{source}' through "
                f"{path_len} recorded transformation(s).  The current trust score "
                f"of {trust:.4f} is rated '{descriptor}'.  "
                f"The full path is available for audit: "
                f"{' → '.join(chain.path) if chain.path else '(direct — no transformations)'}.  "
                f"Immutable proof: {proof_hash}."
            )
        else:
            decision = (
                f"Provenance event '{event_type}' recorded for source '{source}'. "
                f"Trust: {trust:.2f} ({descriptor})."
            )
            rationale = (
                f"Data originating from '{source}' has been tracked through "
                f"{path_len} transformation step(s) with a final trust score of "
                f"{trust:.4f}.  See the provenance chain for full lineage.  "
                f"Immutable proof: {proof_hash}."
            )

        event = AuditEvent(
            timestamp=_iso_now(),
            event_type=event_type,
            persona=persona,
            decision=decision,
            rationale=rationale,
            provenance_ref=proof_hash,
        )
        self.events.append(event)
        return event

    # ── Queries ─────────────────────────────────────────────────────────────

    def chronological(self) -> list[AuditEvent]:
        """Return events sorted by timestamp (earliest first)."""
        return sorted(self.events, key=lambda e: e.timestamp)

    def events_by_persona(self, persona: str) -> list[AuditEvent]:
        """Filter events by persona (case-insensitive prefix match)."""
        target = persona.lower()
        return [e for e in self.events if e.persona.lower().startswith(target)]

    def events_by_type(self, event_type: str) -> list[AuditEvent]:
        """Filter events by event_type (case-insensitive prefix match)."""
        target = event_type.lower()
        return [e for e in self.events if e.event_type.lower().startswith(target)]

    def summarize(self) -> dict[str, Any]:
        """Executive summary with key decisions and metrics.

        Returns a dict suitable for programmatic consumption or for rendering
        as part of a larger dashboard.  All values are JSON-serialisable.
        """
        if not self.events:
            return {
                "execution_id": self.execution_id,
                "tier": self.tier,
                "total_events": 0,
                "verdict": "EMPTY",
                "decision_counts": {},
                "persona_counts": {},
                "trust_boundaries_crossed": 0,
                "risk_indicators": ["No audit events recorded."],
            }

        chrono = self.chronological()
        decision_counts: dict[str, int] = {}
        persona_counts: dict[str, int] = {}
        event_type_counts: dict[str, int] = {}
        gate_decisions: list[str] = []
        trust_boundaries = 0
        min_trust = 1.0
        max_trust = 0.0

        for e in chrono:
            persona_counts[e.persona] = persona_counts.get(e.persona, 0) + 1
            event_type_counts[e.event_type] = event_type_counts.get(e.event_type, 0) + 1

            if e.event_type == "execution_gate":
                gate_decisions.append(e.decision)
                dec = e.decision.upper()
                for keyword in ("PROCEED", "BLOCK", "WARN"):
                    if keyword in dec:
                        decision_counts[keyword] = decision_counts.get(keyword, 0) + 1
                        break

            if e.event_type == "trust_boundary":
                trust_boundaries += 1

            # Extract trust scores from decision text where available
            if "Trust score:" in e.decision:
                try:
                    pct_str = e.decision.split("Trust score:")[1].split("%")[0].strip()
                    score = float(pct_str) / 100.0
                    min_trust = min(min_trust, score)
                    max_trust = max(max_trust, score)
                except (ValueError, IndexError):
                    pass

        # Determine overall verdict
        if "BLOCK" in decision_counts:
            verdict = "BLOCKED"
        elif "WARN" in decision_counts:
            verdict = "WARNING"
        elif "PROCEED" in decision_counts and "BLOCK" not in decision_counts:
            verdict = "PASSED"
        elif not gate_decisions:
            verdict = "NO_GATE"
        else:
            verdict = "UNDETERMINED"

        risk_indicators: list[str] = []
        if trust_boundaries > 3:
            risk_indicators.append(
                f"High number of trust boundaries crossed ({trust_boundaries}). "
                f"Review data lineage carefully."
            )
        if max_trust < 0.7:
            risk_indicators.append(
                f"Maximum trust score is only {max_trust:.2f}. "
                f"All data sources carry significant uncertainty."
            )
        if verdict == "WARNING":
            risk_indicators.append(
                f"Execution proceeded with warnings.  "
                f"Review the {decision_counts.get('WARN', 0)} flagged gate event(s)."
            )

        return {
            "execution_id": self.execution_id,
            "tier": self.tier,
            "tier_label": _TIER_LABELS.get(self.tier, self.tier),
            "total_events": len(chrono),
            "verdict": verdict,
            "decision_counts": decision_counts,
            "persona_counts": persona_counts,
            "event_type_counts": event_type_counts,
            "trust_boundaries_crossed": trust_boundaries,
            "trust_range": (
                {"min": round(min_trust, 4), "max": round(max_trust, 4)}
                if max_trust >= min_trust
                else None
            ),
            "risk_indicators": risk_indicators or ["No elevated risks detected."],
            "first_event": chrono[0].timestamp if chrono else "",
            "last_event": chrono[-1].timestamp if chrono else "",
        }

    # ── Rendering ───────────────────────────────────────────────────────────

    def to_markdown(self) -> str:
        """Generate a full markdown audit report.

        Produces a document with:
        - Executive summary section (verdict, counts, risk indicators)
        - Chronological event table
        - Per-event detail sections with full rationale
        - Provenance reference annotations
        """
        summary = self.summarize()
        lines: list[str] = []

        # ── Title & metadata ─────────────────────────────────────────────
        verdict_emoji = {"PASSED": "✅", "BLOCKED": "🛑", "WARNING": "⚠️",
                         "NO_GATE": "ℹ️", "UNDETERMINED": "❓", "EMPTY": "📭"}
        emoji = verdict_emoji.get(summary["verdict"], "❓")

        lines.append(f"# {emoji} HLF Execution Audit — {summary['verdict']}")
        lines.append("")
        lines.append(f"- **Execution ID:** `{summary['execution_id']}`")
        lines.append(f"- **Tier:** {summary['tier_label']}")
        lines.append(f"- **Events:** {summary['total_events']}")
        lines.append(f"- **First event:** {summary['first_event'][:19] if summary['first_event'] else '—'}")
        lines.append(f"- **Last event:** {summary['last_event'][:19] if summary['last_event'] else '—'}")
        lines.append("")

        # ── Gate decisions ──────────────────────────────────────────────
        dc = summary["decision_counts"]
        if dc:
            lines.append("## Gate Decisions")
            lines.append("")
            lines.append("| Decision | Count |")
            lines.append("|----------|------:|")
            for decision, count in sorted(dc.items()):
                lines.append(f"| {decision} | {count} |")
            lines.append("")

        # ── Persona breakdown ───────────────────────────────────────────
        pc = summary["persona_counts"]
        if pc:
            lines.append("## Persona Breakdown")
            lines.append("")
            lines.append("| Persona | Events |")
            lines.append("|---------|-------:|")
            for persona, count in sorted(pc.items(), key=lambda x: -x[1]):
                lines.append(f"| {persona} | {count} |")
            lines.append("")

        # ── Risk indicators ─────────────────────────────────────────────
        risks = summary.get("risk_indicators", [])
        if risks:
            lines.append("## Risk Indicators")
            lines.append("")
            for risk in risks:
                lines.append(f"- {risk}")
            lines.append("")

        # ── Trust range ─────────────────────────────────────────────────
        tr = summary.get("trust_range")
        if tr:
            lines.append(f"- **Trust range:** {tr['min']:.4f} – {tr['max']:.4f}")
            lines.append(f"- **Trust boundaries crossed:** {summary.get('trust_boundaries_crossed', 0)}")
            lines.append("")

        # ── Chronological event log ─────────────────────────────────────
        lines.append("---")
        lines.append("")
        lines.append("## Chronological Event Log")
        lines.append("")

        chrono = self.chronological()
        for i, event in enumerate(chrono, 1):
            ts = event.timestamp[:19]
            badge = _TRUST_BADGE.get(self.tier, "")
            lines.append(f"### {i}. {event.event_type.replace('_', ' ').title()} — {ts}")
            lines.append("")
            lines.append(f"**Persona:** {event.persona}  ")
            lines.append(f"**Decision:** {event.decision}  ")
            lines.append(f"**Tier badge:** {badge}  ")
            if event.provenance_ref:
                lines.append(f"**Provenance ref:** `{event.provenance_ref}`  ")
            lines.append("")
            lines.append(f"> {event.rationale}")
            lines.append("")

        # ── Footer ──────────────────────────────────────────────────────
        lines.append("---")
        lines.append("")
        lines.append(
            f"*Audit trail generated by HLF_MCP AuditTrail | "
            f"Execution `{summary['execution_id']}` | "
            f"{_iso_now()[:19]}*"
        )
        lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        """Generate rich HTML with collapsible sections.

        Produces a self-contained HTML document with:
        - Inline CSS for styling (no external stylesheets)
        - Color-coded trust levels
        - Decision badges (PASS/FAIL/WARN)
        - Collapsible `<details>` sections for each event
        - Timeline visualisation
        """
        summary = self.summarize()
        chrono = self.chronological()

        # ── CSS ─────────────────────────────────────────────────────────
        css = """
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 860px;
                margin: 2rem auto;
                padding: 0 1rem;
                color: #1a1a1a;
                background: #fafafa;
                line-height: 1.6;
            }
            h1 { border-bottom: 3px solid #333; padding-bottom: 0.5rem; }
            h2 { margin-top: 2rem; border-bottom: 2px solid #ccc; padding-bottom: 0.25rem; }
            h3 { margin-top: 1.5rem; font-size: 1.1rem; }
            .meta { background: #eee; padding: 1rem; border-radius: 6px; margin: 1rem 0; }
            .meta dt { font-weight: bold; float: left; width: 9em; }
            .meta dd { margin-left: 9.5em; }
            .meta::after { content: ""; display: table; clear: both; }
            table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
            th, td { border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }
            th { background: #e0e0e0; }
            .verdict { font-size: 1.4rem; font-weight: bold; padding: 0.5rem 1rem;
                       border-radius: 6px; display: inline-block; margin: 0.5rem 0; }
            .verdict-passed { background: #d4edda; color: #155724; }
            .verdict-blocked { background: #f8d7da; color: #721c24; }
            .verdict-warning { background: #fff3cd; color: #856404; }
            .verdict-other  { background: #d6d8db; color: #383d41; }
            .badge { display: inline-block; padding: 0.15em 0.5em; border-radius: 4px;
                     font-size: 0.85em; font-weight: bold; margin: 0 0.3em; }
            .badge-proceed { background: #d4edda; color: #155724; }
            .badge-block  { background: #f8d7da; color: #721c24; }
            .badge-warn   { background: #fff3cd; color: #856404; }
            .badge-info   { background: #cce5ff; color: #004085; }
            .event-details { margin: 0.75rem 0; border-left: 4px solid #999;
                             padding: 0.5rem 1rem; background: #fff;
                             border-radius: 0 6px 6px 0; }
            .event-details summary {
                cursor: pointer; font-weight: 600; padding: 0.3rem 0;
                outline: none;
            }
            .event-details summary:hover { color: #0056b3; }
            .rationale { font-style: italic; color: #555; margin-top: 0.5rem; }
            .ref { font-family: monospace; font-size: 0.85em; color: #777; }
            .risk { background: #fff3cd; padding: 0.3rem 0.8rem; border-left: 4px solid #ffc107;
                    margin: 0.4rem 0; border-radius: 0 4px 4px 0; }
            .risk-ok { background: #d4edda; border-left-color: #28a745; }
            .timeline { position: relative; padding-left: 2rem; margin: 1rem 0; }
            .timeline::before {
                content: ""; position: absolute; left: 0.55rem; top: 0; bottom: 0;
                width: 3px; background: #ccc;
            }
            .tl-dot {
                position: absolute; left: 0.15rem; width: 0.9rem; height: 0.9rem;
                border-radius: 50%; background: #666; margin-top: 0.4rem;
            }
            .tl-dot-gate   { background: #007bff; }
            .tl-dot-prov   { background: #28a745; }
            .tl-dot-bound  { background: #ffc107; }
            .tl-item { margin-left: 0.5rem; padding-bottom: 1rem; }
            footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #ccc;
                     font-size: 0.85em; color: #888; }
        </style>
        """

        # ── Verdict class ───────────────────────────────────────────────
        verdict_class = {
            "PASSED": "verdict-passed", "BLOCKED": "verdict-blocked",
            "WARNING": "verdict-warning",
        }.get(summary["verdict"], "verdict-other")

        # ── Badge helper ────────────────────────────────────────────────
        def _decision_badge(decision_text: str) -> str:
            upper = decision_text.upper()
            if "PROCEED" in upper:
                return '<span class="badge badge-proceed">PROCEED</span>'
            if "BLOCK" in upper:
                return '<span class="badge badge-block">BLOCK</span>'
            if "WARN" in upper:
                return '<span class="badge badge-warn">WARN</span>'
            return '<span class="badge badge-info">INFO</span>'

        # ── Build HTML ──────────────────────────────────────────────────
        parts: list[str] = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>HLF Audit — {summary['execution_id']}</title>",
            css,
            "</head>",
            "<body>",
            "",
            f"<h1>HLF Execution Audit</h1>",
            f'<div class="verdict {verdict_class}">{summary["verdict"]}</div>',
            "",
            '<dl class="meta">',
            f"<dt>Execution ID</dt><dd><code>{summary['execution_id']}</code></dd>",
            f"<dt>Tier</dt><dd>{summary['tier_label']}</dd>",
            f"<dt>Total Events</dt><dd>{summary['total_events']}</dd>",
            f"<dt>First Event</dt><dd>{summary['first_event'][:19] if summary['first_event'] else '—'}</dd>",
            f"<dt>Last Event</dt><dd>{summary['last_event'][:19] if summary['last_event'] else '—'}</dd>",
            "</dl>",
            "",
        ]

        # ── Gate decisions table ────────────────────────────────────────
        dc = summary.get("decision_counts", {})
        if dc:
            parts.append("<h2>Gate Decisions</h2>")
            parts.append("<table><tr><th>Decision</th><th>Count</th></tr>")
            for decision, count in sorted(dc.items()):
                parts.append(f"<tr><td>{decision}</td><td>{count}</td></tr>")
            parts.append("</table>")

        # ── Persona breakdown ───────────────────────────────────────────
        pc = summary.get("persona_counts", {})
        if pc:
            parts.append("<h2>Persona Breakdown</h2>")
            parts.append("<table><tr><th>Persona</th><th>Events</th></tr>")
            for persona, count in sorted(pc.items(), key=lambda x: -x[1]):
                parts.append(f"<tr><td>{persona}</td><td>{count}</td></tr>")
            parts.append("</table>")

        # ── Trust stats ─────────────────────────────────────────────────
        tr = summary.get("trust_range")
        if tr:
            parts.append("<h2>Trust Metrics</h2>")
            parts.append(f"<p>Trust range: <strong>{tr['min']:.4f} – {tr['max']:.4f}</strong></p>")
            parts.append(
                f"<p>Trust boundaries crossed: "
                f"<strong>{summary.get('trust_boundaries_crossed', 0)}</strong></p>"
            )

        # ── Risk indicators ─────────────────────────────────────────────
        risks = summary.get("risk_indicators", [])
        parts.append("<h2>Risk Assessment</h2>")
        if not risks:
            parts.append('<p class="risk risk-ok">✅ No elevated risks detected.</p>')
        else:
            for risk in risks:
                parts.append(f'<p class="risk">{risk}</p>')

        # ── Timeline ────────────────────────────────────────────────────
        if chrono:
            parts.append("<h2>Event Timeline</h2>")
            parts.append('<div class="timeline">')
            for i, event in enumerate(chrono):
                dot_class = {
                    "execution_gate": "tl-dot-gate",
                    "verification": "tl-dot-gate",
                    "provenance_check": "tl-dot-prov",
                    "trust_boundary": "tl-dot-bound",
                }.get(event.event_type, "tl-dot")
                badge = _decision_badge(event.decision)
                parts.append(f'<div class="tl-dot {dot_class}"></div>')
                parts.append('<div class="tl-item">')
                parts.append(
                    f"<strong>{i + 1}. {event.event_type.replace('_', ' ').title()}</strong> "
                    f"— {event.timestamp[:19]}<br>"
                )
                parts.append(
                    f"<em>{event.persona}</em> {badge}<br>"
                )
                parts.append(f"{event.decision}")
                if event.provenance_ref:
                    parts.append(
                        f' <span class="ref">ref:{event.provenance_ref}</span>'
                    )
                parts.append("</div>")
            parts.append("</div>")

        # ── Detailed events (collapsible) ───────────────────────────────
        parts.append("<h2>Detailed Event Log</h2>")
        for i, event in enumerate(chrono, 1):
            parts.append(f'<details class="event-details">')
            parts.append(
                f"<summary>{i}. [{event.timestamp[:19]}] "
                f"{event.event_type.replace('_', ' ').title()} — "
                f"{event.persona}</summary>"
            )
            parts.append(f"<p><strong>Decision:</strong> {event.decision}</p>")
            if event.provenance_ref:
                parts.append(
                    f'<p><strong>Provenance ref:</strong> '
                    f'<code>{event.provenance_ref}</code></p>'
                )
            parts.append(f'<p class="rationale">{event.rationale}</p>')
            parts.append("</details>")

        # ── Footer ──────────────────────────────────────────────────────
        parts.append("<footer>")
        parts.append(
            f"Audit trail generated by HLF_MCP AuditTrail — "
            f"Execution <code>{summary['execution_id']}</code> — "
            f"{_iso_now()[:19]}"
        )
        parts.append("</footer>")
        parts.append("</body></html>")

        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level convenience functions
# ═══════════════════════════════════════════════════════════════════════════════


def generate_execution_audit(
    provenance_chains: dict[str, ProvenanceChain],
    verification_report: VerificationReport | None = None,
    tier: str = "hearth",
    execution_id: str = "",
) -> AuditTrail:
    """Generate a complete audit trail from provenance chains and verification report.

    Walks through every provenance chain entry and generates AuditEvents for:
    - The initial data source (trust level, origin)
    - Each degradation step recorded in the chain path
    - Each boundary crossing recorded in the chain path
    - Trust score changes between steps
    - Verification gate decisions (if *verification_report* is provided)

    Args:
        provenance_chains: Mapping of data names to their ProvenanceChain objects.
        verification_report: Optional VerificationReport for gate-decision events.
        tier: Trust tier name (``"hearth"``, ``"forge"``, etc.).
        execution_id: Stable identifier for this execution; auto-generated if empty.

    Returns:
        A fully populated AuditTrail ready for ``to_markdown()`` / ``to_html()``.
    """
    trail = AuditTrail(execution_id=execution_id, tier=tier)

    if not provenance_chains:
        # Record that we have no provenance data at all
        trail.add_event(AuditEvent(
            timestamp=_iso_now(),
            event_type="provenance_check",
            persona="governor",
            decision="No provenance chains were supplied for this execution.",
            rationale=(
                "Without provenance chains the audit trail cannot verify data "
                "lineage, trust scores, or boundary crossings.  The execution "
                "proceeded with no provenance guarantees.  This is acceptable "
                "only at advisory/sovereign tiers."
            ),
        ))
        # Still process verification if available
        if verification_report is not None:
            _add_verification_events(trail, verification_report, tier)
        return trail

    # ── Walk every provenance chain ─────────────────────────────────────
    for data_name, chain in provenance_chains.items():
        if chain is None:
            continue

        source = chain.source or "unknown"
        trust = chain.trust

        # 1. Record the initial data source
        trail.add_event(AuditEvent(
            timestamp=chain.timestamp or _iso_now(),
            event_type="provenance_check",
            persona="executor",
            decision=(
                f"Data source '{data_name}' registered with origin '{source}' "
                f"at trust level {trust:.4f} ({_trust_descriptor(trust)})."
            ),
            rationale=(
                f"The provenance chain for '{data_name}' establishes that this "
                f"data originated from '{source}'.  The starting trust score is "
                f"{trust:.4f}, rated '{_trust_descriptor(trust)}'.  "
                f"All subsequent transformations and boundary crossings will be "
                f"recorded against this baseline."
            ),
            provenance_ref=chain.is_immutable_proof()[:16],
        ))

        # 2. Walk the path for degradation steps and boundary crossings
        previous_trust = trust
        for step_idx, step in enumerate(chain.path):
            step_ts = _iso_now()  # path entries carry their own timestamps but we use now for audit

            if step.startswith("degraded("):
                # Extract degradation factor for the narrative
                try:
                    factor_str = step.split("(")[1].split(")")[0]
                    factor = float(factor_str)
                except (ValueError, IndexError):
                    factor = 0.0

                current_trust = previous_trust * max(0.0, min(1.0, factor))
                trail.add_event(AuditEvent(
                    timestamp=step_ts,
                    event_type="provenance_check",
                    persona="executor",
                    decision=(
                        f"Transformation step {step_idx + 1} on '{data_name}' "
                        f"degraded trust by factor {factor:.4f} "
                        f"(now {current_trust:.4f})."
                    ),
                    rationale=(
                        f"Data '{data_name}' underwent a transformation recorded "
                        f"as step {step_idx + 1} in its provenance path.  The "
                        f"degradation factor of {factor:.4f} reduced trust from "
                        f"{previous_trust:.4f} to {current_trust:.4f}.  This is "
                        f"a normal consequence of data processing — each "
                        f"operation carries a small trust penalty."
                    ),
                    provenance_ref=chain.is_immutable_proof()[:16],
                ))
                previous_trust = current_trust

            elif step.startswith("boundary:"):
                # Parse the boundary description
                try:
                    boundary_part = step.split(":", 1)[1].split("@")[0]
                    if "→" in boundary_part:
                        boundary_name, new_source = boundary_part.split("→", 1)
                    else:
                        boundary_name = boundary_part
                        new_source = "unknown"
                except (ValueError, IndexError):
                    boundary_name = step
                    new_source = "unknown"

                trail.add_event(AuditEvent(
                    timestamp=step_ts,
                    event_type="trust_boundary",
                    persona="governor",
                    decision=(
                        f"Data '{data_name}' crossed trust boundary "
                        f"'{boundary_name.strip()}' into domain '{new_source.strip()}'. "
                        f"Trust reset to baseline (0.50)."
                    ),
                    rationale=(
                        f"When '{data_name}' moved from one trust domain to another "
                        f"(boundary: '{boundary_name.strip()}'), its accumulated trust "
                        f"of {previous_trust:.4f} was discarded.  The new source "
                        f"'{new_source.strip()}' starts with a baseline trust of 0.50.  "
                        f"Boundary crossings are significant events because they reset "
                        f"the trust model — the new domain's guarantees may differ from "
                        f"the previous one."
                    ),
                    provenance_ref=chain.is_immutable_proof()[:16],
                ))
                previous_trust = 0.50  # baseline after boundary crossing

        # 3. Record the final trust state for this chain
        trail.add_event(AuditEvent(
            timestamp=_iso_now(),
            event_type="provenance_check",
            persona="governor",
            decision=(
                f"Final provenance assessment for '{data_name}': "
                f"trust = {previous_trust:.4f} ({_trust_descriptor(previous_trust)}), "
                f"{len(chain.path)} transformation(s) recorded."
            ),
            rationale=(
                f"After processing all recorded transformations and boundary crossings "
                f"for '{data_name}', the final trust score is {previous_trust:.4f}.  "
                f"The full provenance path contains {len(chain.path)} entries.  "
                f"Source: '{chain.source}'.  The immutable proof hash for this chain "
                f"is {chain.is_immutable_proof()[:16]}."
            ),
            provenance_ref=chain.is_immutable_proof()[:16],
        ))

    # ── Verification gate events ────────────────────────────────────────
    if verification_report is not None:
        _add_verification_events(trail, verification_report, tier)

    return trail


def _add_verification_events(
    trail: AuditTrail,
    report: VerificationReport,
    tier: str,
) -> None:
    """Internal: append verification-related AuditEvents to an AuditTrail.

    Examines the VerificationReport and produces events for:
    - Overall gate decision
    - Each individual verification result (if there are notable failures)
    - InsAIts decompilation enrichment (if an AST is referenced)
    """
    # Determine the gate decision based on tier and report
    from hlf_mcp.hlf.formal_verifier import GateDecision

    try:
        if tier in ("hearth", "trusted"):
            if report.failed_count > 0 or report.unknown_count > 0:
                gate_decision = GateDecision.BLOCK
            else:
                gate_decision = GateDecision.PROCEED
        elif tier in ("forge", "approved", "watched"):
            if report.failed_count > 0:
                gate_decision = GateDecision.BLOCK
            elif report.unknown_count > 0 or report.skipped_count > 0:
                gate_decision = GateDecision.WARN
            else:
                gate_decision = GateDecision.PROCEED
        else:
            gate_decision = GateDecision.PROCEED
    except Exception:
        gate_decision = "PROCEED"

    trail.add_gate_decision(gate_decision, report, tier)

    # Record individual notable results
    for result in report.results:
        status_val = result.status.value if hasattr(result.status, "value") else str(result.status)
        if status_val in ("counterexample", "unknown", "error"):
            trail.add_event(AuditEvent(
                timestamp=_iso_now(),
                event_type="verification",
                persona="verifier",
                decision=(
                    f"Verification result: {result.property_name} — "
                    f"{status_val.upper()}"
                ),
                rationale=(
                    f"The property '{result.property_name}' ({result.kind.value if hasattr(result.kind, 'value') else result.kind}) "
                    f"returned status '{status_val}'.  "
                    f"{result.message or 'No additional message provided.'}  "
                    f"Solver: {result.solver or 'unspecified'}.  "
                    f"Duration: {result.duration_ms:.2f} ms."
                ),
            ))


def summarize_audit(audit: AuditTrail) -> str:
    """Generate a human-readable executive summary from an audit trail.

    Returns a multi-line string with:
    - Overall execution verdict (PASSED/BLOCKED/WARNING)
    - Key decisions count
    - Trust score range
    - Notable events
    - Risk indicators
    """
    summary = audit.summarize()

    if summary["total_events"] == 0:
        return (
            f"=== HLF Execution Audit Summary ===\n"
            f"Execution ID: {summary['execution_id']}\n"
            f"Tier:         {summary['tier_label']}\n"
            f"Verdict:      EMPTY — No audit events were recorded.\n"
            f"Risk:         Unable to assess (no data).\n"
        )

    lines = [
        "=" * 60,
        "  HLF EXECUTION AUDIT — EXECUTIVE SUMMARY",
        "=" * 60,
        "",
        f"  Execution ID:  {summary['execution_id']}",
        f"  Tier:          {summary['tier_label']}",
        f"  Verdict:       {summary['verdict']}",
        f"  Total Events:  {summary['total_events']}",
        "",
    ]

    tr = summary.get("trust_range")
    if tr:
        lines.append(f"  Trust Range:   {tr['min']:.4f} – {tr['max']:.4f}")
        lines.append(f"  Boundaries:    {summary.get('trust_boundaries_crossed', 0)} crossed")
        lines.append("")

    dc = summary.get("decision_counts", {})
    if dc:
        lines.append("  Gate Decisions:")
        for decision, count in sorted(dc.items()):
            lines.append(f"    {decision:12} {count}")
        lines.append("")

    lines.append("  Risk Assessment:")
    for risk in summary.get("risk_indicators", ["No risks identified."]):
        lines.append(f"    • {risk}")
    lines.append("")

    # Notable events
    chrono = audit.chronological()
    gate_events = [e for e in chrono if e.event_type == "execution_gate"]
    boundary_events = [e for e in chrono if e.event_type == "trust_boundary"]

    if gate_events:
        lines.append("  Notable Gate Events:")
        for e in gate_events[-3:]:  # last 3
            lines.append(f"    [{e.timestamp[:19]}] {e.decision}")
        lines.append("")

    if boundary_events:
        lines.append("  Trust Boundaries Crossed:")
        for e in boundary_events[-3:]:
            lines.append(f"    [{e.timestamp[:19]}] {e.decision}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def audit_to_html(audit: AuditTrail) -> str:
    """Convert an audit trail to a rich, self-contained HTML document.

    Convenience wrapper around ``AuditTrail.to_html()``.  Includes:
    - Inline CSS for styling
    - Collapsible sections for each event
    - Color-coded trust levels
    - Decision badges (PASS/FAIL/WARN)
    - Timeline visualisation
    """
    return audit.to_html()
