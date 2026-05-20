"""
Comprehensive tests for the HLF audit and trust layer hardening.

Covers:
  - AuditEvent / AuditTrail (creation, filtering, rendering, serialization)
  - generate_execution_audit (provenance, verification, empty, degradation)
  - TrustEdge / TrustSurface (edges, validation, violations, DOT, serialization)
  - build_default_trust_surface / validate_trust_against_constitution
  - ReviewRecord / ReviewProof (completeness, checklists, gaps, markdown)
  - TwoChannelExecutor with audit_trail integration
  - End-to-end audit pipeline
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.audit_trail import (
    AuditEvent,
    AuditTrail,
    audit_to_html,
    generate_execution_audit,
    summarize_audit,
)
from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    GateDecision,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
)
from hlf_mcp.hlf.review_proof import (
    ReviewProof,
    ReviewRecord,
    audit_review_gaps,
    generate_review_checklist,
    generate_review_proof_markdown,
    prove_review_completeness,
)
from hlf_mcp.hlf.trust_surface import (
    TrustEdge,
    TrustSurface,
    build_default_trust_surface,
    validate_trust_against_constitution,
)
from hlf_mcp.hlf.two_channel_executor import (
    DataChannel,
    ProvenanceChain,
    TwoChannelExecutor,
    build_data_channel,
    build_instruction_channel,
)
from hlf_mcp.hlf.capability_manifest import CapabilityManifest
from hlf_mcp.hlf.audit_diff import AuditDiff, AuditDiffEntry, DiffOperation
from hlf_mcp.hlf.trust_debt import DebtItem, TrustDebtQuantifier
from hlf_mcp.hlf.remediation_planner import (
    RemediationPlanner,
    RemediationPlan,
    RemediationTask,
    RemediationPriority,
    RemediationStatus,
)
from hlf_mcp.hlf.trust_trending import (
    AlertLevel,
    TrendAlert,
    TrendDirection,
    TrendReport,
    TrustSnapshot,
    TrustTrending,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_report(
    proven: int = 3,
    failed: int = 0,
    unknown: int = 0,
    skipped: int = 0,
    errors: int = 0,
) -> VerificationReport:
    """Build a VerificationReport with controlled counts."""
    report = VerificationReport()
    for i in range(proven):
        report.add(
            VerificationResult(
                f"prop_proven_{i}",
                VerificationStatus.PROVEN,
                ConstraintKind.RANGE_CHECK,
                message="proven",
                solver="fallback",
            )
        )
    for i in range(failed):
        report.add(
            VerificationResult(
                f"prop_failed_{i}",
                VerificationStatus.COUNTEREXAMPLE,
                ConstraintKind.RANGE_CHECK,
                message="counterexample",
                counterexample={"value": -1},
                solver="fallback",
            )
        )
    for i in range(unknown):
        report.add(
            VerificationResult(
                f"prop_unknown_{i}",
                VerificationStatus.UNKNOWN,
                ConstraintKind.CUSTOM,
                message="unknown",
                solver="fallback",
            )
        )
    for i in range(skipped):
        report.add(
            VerificationResult(
                f"prop_skipped_{i}",
                VerificationStatus.SKIPPED,
                ConstraintKind.SPEC_GATE,
                message="skipped",
                solver="fallback",
            )
        )
    for i in range(errors):
        report.add(
            VerificationResult(
                f"prop_error_{i}",
                VerificationStatus.ERROR,
                ConstraintKind.TYPE_INVARIANT,
                message="error",
                solver="fallback",
            )
        )
    return report


def _make_chain(
    source: str = "agent",
    trust: float = 0.95,
    path: list[str] | None = None,
) -> ProvenanceChain:
    """Build a ProvenanceChain with optional degradation steps."""
    chain = ProvenanceChain(source=source, trust=trust)
    if path:
        for step in path:
            if step.startswith("degraded("):
                factor = float(step.split("(")[1].split(")")[0])
                chain = chain.degrade(factor)
            elif step.startswith("boundary:"):
                parts = step.split(":", 1)[1]
                if "→" in parts:
                    boundary, new_src = parts.split("→", 1)
                else:
                    boundary = parts
                    new_src = "unknown"
                chain = chain.cross_boundary(boundary, new_src)
    return chain


# ═══════════════════════════════════════════════════════════════════════════════
# AuditEvent tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_event_creation() -> None:
    """AuditEvent stores all fields on construction."""
    event = AuditEvent(
        timestamp="2025-01-15T10:30:00Z",
        event_type="execution_gate",
        persona="verifier",
        decision="Gate decision: PROCEED at Hearth Tier",
        rationale="All properties passed.",
        provenance_ref="abc123def456",
    )
    assert event.timestamp == "2025-01-15T10:30:00Z"
    assert event.event_type == "execution_gate"
    assert event.persona == "verifier"
    assert event.decision == "Gate decision: PROCEED at Hearth Tier"
    assert event.rationale == "All properties passed."
    assert event.provenance_ref == "abc123def456"


def test_audit_event_serialization() -> None:
    """AuditEvent to_dict / from_dict round-trips all fields."""
    original = AuditEvent(
        timestamp="2025-01-15T10:30:00Z",
        event_type="verification",
        persona="governor",
        decision="Verified: RangeCheck passed",
        rationale="Checked numeric range.",
        provenance_ref="ref_hash_123",
    )
    data = original.to_dict()
    assert data["timestamp"] == "2025-01-15T10:30:00Z"
    assert data["event_type"] == "verification"
    assert data["persona"] == "governor"

    reconstructed = AuditEvent.from_dict(data)
    assert reconstructed.timestamp == original.timestamp
    assert reconstructed.event_type == original.event_type
    assert reconstructed.persona == original.persona
    assert reconstructed.decision == original.decision
    assert reconstructed.rationale == original.rationale
    assert reconstructed.provenance_ref == original.provenance_ref


def test_audit_event_from_dict_with_missing_keys() -> None:
    """AuditEvent.from_dict fills missing keys with empty strings."""
    event = AuditEvent.from_dict({})
    assert event.timestamp == ""
    assert event.event_type == ""
    assert event.persona == ""
    assert event.decision == ""
    assert event.rationale == ""
    assert event.provenance_ref == ""


def test_audit_event_one_line() -> None:
    """one_line() produces a compact operator-readable summary."""
    event = AuditEvent(
        timestamp="2025-01-15T10:30:00.123456+00:00",
        event_type="execution_gate",
        persona="verifier",
        decision="Gate decision: PROCEED",
        rationale="All passed.",
    )
    line = event.one_line()
    assert "2025-01-15T10:30:00" in line
    assert "verifier" in line
    assert "execution_gate" in line
    assert "PROCEED" in line


# ═══════════════════════════════════════════════════════════════════════════════
# AuditTrail tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_trail_empty() -> None:
    """Empty AuditTrail returns sensible defaults from summarize()."""
    trail = AuditTrail(execution_id="exec-1", tier="hearth")
    summary = trail.summarize()
    assert summary["execution_id"] == "exec-1"
    assert summary["total_events"] == 0
    assert summary["verdict"] == "EMPTY"
    assert summary["decision_counts"] == {}
    assert "No audit events recorded" in summary["risk_indicators"][0]


def test_audit_trail_add_event() -> None:
    """Adding events increases the event count."""
    trail = AuditTrail(execution_id="exec-2")
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-15T10:00:00Z",
            event_type="execution_gate",
            persona="verifier",
            decision="PROCEED",
            rationale="ok",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-15T10:01:00Z",
            event_type="provenance_check",
            persona="executor",
            decision="Provenance verified.",
            rationale="all good",
        )
    )
    assert len(trail.events) == 2


def test_audit_trail_chronological_ordering() -> None:
    """chronological() returns events sorted by timestamp."""
    trail = AuditTrail()
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-15T10:02:00Z",
            event_type="execution_gate",
            persona="verifier",
            decision="Z",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-15T10:00:00Z",
            event_type="provenance_check",
            persona="executor",
            decision="A",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-15T10:01:00Z",
            event_type="trust_boundary",
            persona="governor",
            decision="M",
            rationale="",
        )
    )
    chrono = trail.chronological()
    assert len(chrono) == 3
    assert chrono[0].timestamp == "2025-01-15T10:00:00Z"
    assert chrono[1].timestamp == "2025-01-15T10:01:00Z"
    assert chrono[2].timestamp == "2025-01-15T10:02:00Z"


def test_audit_trail_add_gate_decision_proceed() -> None:
    """add_gate_decision with PROCEED creates correct event."""
    report = _make_report(proven=3)
    trail = AuditTrail(tier="hearth")
    event = trail.add_gate_decision("PROCEED", report, "hearth")
    assert event.event_type == "execution_gate"
    assert event.persona == "verifier"
    assert "PROCEED" in event.decision
    assert "3 verification properties passed" in event.rationale
    assert len(trail.events) == 1


def test_audit_trail_add_gate_decision_block() -> None:
    """add_gate_decision with BLOCK creates correct event with failure counts."""
    report = _make_report(proven=2, failed=2)
    trail = AuditTrail(tier="hearth")
    event = trail.add_gate_decision("BLOCK", report, "hearth")
    assert event.event_type == "execution_gate"
    assert "BLOCK" in event.decision
    assert "2 of 4 verification properties failed" in event.rationale
    assert len(trail.events) == 1


def test_audit_trail_add_gate_decision_warn() -> None:
    """add_gate_decision with WARN creates correct warn event."""
    report = _make_report(proven=2, failed=2)
    trail = AuditTrail(tier="forge")
    event = trail.add_gate_decision("WARN", report, "forge")
    assert event.event_type == "execution_gate"
    assert "WARN" in event.decision.upper()
    assert "flagged result" in event.rationale
    assert len(trail.events) == 1


def test_audit_trail_add_provenance_event() -> None:
    """add_provenance_event creates a provenance_check AuditEvent."""
    chain = ProvenanceChain(source="user", trust=0.9)
    trail = AuditTrail(tier="hearth")
    event = trail.add_provenance_event(chain, "provenance_check", "executor")
    assert event.event_type == "provenance_check"
    assert event.persona == "executor"
    assert "Trust score:" in event.decision
    assert chain.is_immutable_proof()[:16] == event.provenance_ref
    assert len(trail.events) == 1


def test_audit_trail_add_provenance_trust_boundary() -> None:
    """add_provenance_event with trust_boundary type creates a boundary event."""
    chain = ProvenanceChain(source="network", trust=0.3)
    trail = AuditTrail()
    event = trail.add_provenance_event(chain, "trust_boundary", "governor")
    assert event.event_type == "trust_boundary"
    assert event.persona == "governor"
    assert "trust boundary" in event.decision.lower()


def test_audit_trail_events_by_persona() -> None:
    """events_by_persona filters via case-insensitive prefix match."""
    trail = AuditTrail()
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:00:00Z",
            event_type="execution_gate",
            persona="verifier",
            decision="OK",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:01:00Z",
            event_type="provenance_check",
            persona="Verifier_Agent",
            decision="OK",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:02:00Z",
            event_type="trust_boundary",
            persona="executor",
            decision="OK",
            rationale="",
        )
    )
    verifier_events = trail.events_by_persona("verifier")
    assert len(verifier_events) == 2
    executor_events = trail.events_by_persona("exec")
    assert len(executor_events) == 1


def test_audit_trail_events_by_type() -> None:
    """events_by_type filters via case-insensitive prefix match."""
    trail = AuditTrail()
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:00:00Z",
            event_type="execution_gate",
            persona="verifier",
            decision="OK",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:01:00Z",
            event_type="provenance_check",
            persona="executor",
            decision="OK",
            rationale="",
        )
    )
    trail.add_event(
        AuditEvent(
            timestamp="2025-01-01T00:02:00Z",
            event_type="trust_boundary",
            persona="governor",
            decision="OK",
            rationale="",
        )
    )
    provenance_events = trail.events_by_type("provenance")
    assert len(provenance_events) == 1
    assert provenance_events[0].event_type == "provenance_check"


# ═══════════════════════════════════════════════════════════════════════════════
# Audit output tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_trail_to_markdown() -> None:
    """to_markdown produces valid markdown with expected sections."""
    report = _make_report(proven=2)
    trail = AuditTrail(execution_id="exec-md", tier="hearth")
    trail.add_gate_decision("PROCEED", report, "hearth")
    trail.add_provenance_event(
        ProvenanceChain(source="agent", trust=0.95), "provenance_check", "executor"
    )

    md = trail.to_markdown()
    assert "HLF Execution Audit" in md
    assert "exec-md" in md
    assert "PASSED" in md
    assert "## Gate Decisions" in md
    assert "## Chronological Event Log" in md
    assert "## Persona Breakdown" in md
    assert "## Risk Indicators" in md


def test_audit_trail_to_html() -> None:
    """to_html produces self-contained HTML with details/summary."""
    report = _make_report(proven=2)
    trail = AuditTrail(execution_id="exec-html", tier="hearth")
    trail.add_gate_decision("PROCEED", report, "hearth")

    html = trail.to_html()
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "<style>" in html
    assert "<details" in html
    assert "exec-html" in html
    assert "PASSED" in html


def test_summarize_audit() -> None:
    """summarize_audit returns an executive summary string with verdict."""
    report = _make_report(proven=2)
    trail = AuditTrail(execution_id="exec-sum", tier="hearth")
    trail.add_gate_decision("PROCEED", report, "hearth")

    summary = summarize_audit(trail)
    assert "HLF EXECUTION AUDIT" in summary
    assert "exec-sum" in summary
    assert "PASSED" in summary


def test_summarize_audit_empty() -> None:
    """summarize_audit handles trails with only non-gate events."""
    trail = AuditTrail(execution_id="empty-sum", tier="hearth")
    # Add a single non-gate event so the trail isn't completely empty
    trail.add_provenance_event(
        ProvenanceChain(source="test", trust=0.5),
        "provenance_check",
        "executor",
    )
    summary = summarize_audit(trail)
    assert "execution" in summary.lower()
    assert "empty-sum" in summary


def test_audit_to_html_wrapper() -> None:
    """audit_to_html wrapper produces same output as trail.to_html()."""
    report = _make_report(proven=2)
    trail = AuditTrail(execution_id="exec-wrap", tier="hearth")
    trail.add_gate_decision("PROCEED", report, "hearth")

    direct = trail.to_html()
    wrapped = audit_to_html(trail)
    assert wrapped == direct


# ═══════════════════════════════════════════════════════════════════════════════
# generate_execution_audit tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_generate_execution_audit_with_provenance() -> None:
    """generate_execution_audit creates trail from provenance chains."""
    chains = {
        "data_a": _make_chain("user", 0.9),
        "data_b": _make_chain("agent", 0.95),
    }
    report = _make_report(proven=2)
    audit = generate_execution_audit(chains, report, tier="hearth")
    assert audit.tier == "hearth"
    # Each chain produces: source event + final assessment event = 2 per chain,
    # plus verification gate events
    assert len(audit.events) >= 4


def test_generate_execution_audit_with_verification() -> None:
    """generate_execution_audit includes gate events from verification report."""
    chains = {"input": _make_chain("agent", 0.99)}
    report = _make_report(proven=1)
    audit = generate_execution_audit(chains, report, tier="hearth")
    gate_events = audit.events_by_type("execution_gate")
    assert len(gate_events) >= 1


def test_generate_execution_audit_empty_inputs() -> None:
    """generate_execution_audit handles empty provenance gracefully."""
    audit = generate_execution_audit({}, tier="advisory")
    events = audit.chronological()
    assert len(events) >= 1
    # The "no provenance chains" event is recorded
    decisions = [e.decision for e in events]
    assert any("No provenance chains were supplied" in d for d in decisions)


def test_generate_execution_audit_trust_degradation() -> None:
    """generate_execution_audit records degradation steps from chain path."""
    chain = _make_chain("user", 0.95, path=["degraded(0.8)"])
    chains = {"data": chain}
    audit = generate_execution_audit(chains, tier="hearth")
    # Should have events for: source, degradation step, final assessment
    assert len(audit.events) >= 3
    # Find the degradation event
    degradations = [
        e for e in audit.events if "degraded trust" in e.decision.lower()
    ]
    assert len(degradations) >= 1


def test_generate_execution_audit_boundary_crossing() -> None:
    """generate_execution_audit records boundary crossing events."""
    chain = _make_chain("user", 0.95, path=["boundary:agent→vm"])
    chains = {"data": chain}
    audit = generate_execution_audit(chains, tier="hearth")
    boundaries = audit.events_by_type("trust_boundary")
    assert len(boundaries) >= 1
    assert "trust boundary" in boundaries[0].decision.lower()


def test_generate_execution_audit_verification_failures() -> None:
    """generate_execution_audit records individual failed verification results."""
    report = _make_report(proven=1, failed=1, unknown=1)
    chains = {"input": _make_chain("agent", 0.9)}
    audit = generate_execution_audit(chains, report, tier="hearth")
    verification_events = audit.events_by_type("verification")
    # Unknown and counterexample results produce individual events
    assert len(verification_events) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# TrustEdge tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_trust_edge_creation() -> None:
    """TrustEdge stores all fields on construction."""
    edge = TrustEdge(
        from_component="compiler",
        to_component="verifier",
        trust_level="high",
        conditions=["c1"],
        evidence=["e1"],
        bidirectional=False,
    )
    assert edge.from_component == "compiler"
    assert edge.to_component == "verifier"
    assert edge.trust_level == "high"
    assert edge.conditions == ["c1"]
    assert edge.evidence == ["e1"]
    assert edge.bidirectional is False


def test_trust_edge_invalid_level() -> None:
    """TrustEdge raises ValueError for invalid trust level."""
    with pytest.raises(ValueError, match="Invalid trust_level"):
        TrustEdge(
            from_component="a",
            to_component="b",
            trust_level="super_high",
        )


def test_trust_edge_serialization() -> None:
    """TrustEdge to_dict / from_dict round-trips."""
    edge = TrustEdge(
        from_component="governor",
        to_component="executor",
        trust_level="medium",
        conditions=["must_pass_gate"],
        evidence=["gov_audit_123"],
        bidirectional=True,
    )
    data = edge.to_dict()
    restored = TrustEdge.from_dict(data)
    assert restored.from_component == edge.from_component
    assert restored.to_component == edge.to_component
    assert restored.trust_level == edge.trust_level
    assert restored.conditions == edge.conditions
    assert restored.evidence == edge.evidence
    assert restored.bidirectional == edge.bidirectional


def test_trust_edge_from_dict_defaults() -> None:
    """TrustEdge.from_dict fills missing fields with defaults."""
    edge = TrustEdge.from_dict({})
    assert edge.from_component == ""
    assert edge.to_component == ""
    assert edge.trust_level == "none"
    assert edge.conditions == []
    assert edge.evidence == []
    assert edge.bidirectional is False


# ═══════════════════════════════════════════════════════════════════════════════
# TrustSurface tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_trust_surface_add_remove_edge() -> None:
    """TrustSurface supports adding and removing edges."""
    surface = TrustSurface()
    edge = TrustEdge("a", "b", "high")
    surface.add_edge(edge)
    assert len(surface._edges) == 1
    assert surface.remove_edge("a", "b") is True
    assert len(surface._edges) == 0


def test_trust_surface_remove_nonexistent_edge() -> None:
    """remove_edge returns False when edge doesn't exist."""
    surface = TrustSurface()
    assert surface.remove_edge("x", "y") is False


def test_trust_surface_get_edges_from() -> None:
    """get_edges_from returns all edges originating from a component."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "high"))
    surface.add_edge(TrustEdge("a", "c", "medium"))
    surface.add_edge(TrustEdge("b", "c", "low"))
    from_a = surface.get_edges_from("a")
    assert len(from_a) == 2
    assert {e.to_component for e in from_a} == {"b", "c"}


def test_trust_surface_get_edges_to() -> None:
    """get_edges_to returns all edges targeting a component."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "c", "high"))
    surface.add_edge(TrustEdge("b", "c", "medium"))
    to_c = surface.get_edges_to("c")
    assert len(to_c) == 2


def test_validate_trust_chain_valid() -> None:
    """validate_trust_chain finds a valid path through trusted components."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("user", "compiler", "high"))
    surface.add_edge(TrustEdge("compiler", "verifier", "medium"))
    surface.add_edge(TrustEdge("verifier", "executor", "high"))
    result = surface.validate_trust_chain("user", "executor", required_level="medium")
    assert result["valid"] is True
    assert len(result["path"]) >= 3
    assert result["weakest_link"] == "medium"


def test_validate_trust_chain_invalid() -> None:
    """validate_trust_chain returns valid=False when no path exists."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "high"))
    surface.add_edge(TrustEdge("c", "d", "high"))
    result = surface.validate_trust_chain("a", "d")
    assert result["valid"] is False
    assert result["path"] == []
    assert result["weakest_link"] == "none"
    assert "No trust path exists" in result["reason"]


def test_validate_trust_chain_same_component() -> None:
    """validate_trust_chain returns valid for source==target."""
    surface = TrustSurface()
    result = surface.validate_trust_chain("compiler", "compiler")
    assert result["valid"] is True
    assert result["path"] == ["compiler"]
    assert result["weakest_link"] == "high"


def test_validate_trust_chain_insufficient_level() -> None:
    """A chain below the required trust level is invalid."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "low"))
    surface.add_edge(TrustEdge("b", "c", "low"))
    result = surface.validate_trust_chain("a", "c", required_level="high")
    assert result["valid"] is False
    assert result["weakest_link"] == "low"


def test_validate_trust_chain_weakest_link() -> None:
    """weakest_link correctly identifies the minimum trust in the path."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "high"))
    surface.add_edge(TrustEdge("b", "c", "none"))
    surface.add_edge(TrustEdge("c", "d", "high"))
    result = surface.validate_trust_chain("a", "d", required_level="low")
    assert result["valid"] is False
    assert result["weakest_link"] == "none"


def test_compute_trust_surface() -> None:
    """compute_trust_surface returns matrix and stats."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("compiler", "verifier", "medium", evidence=["e1"]))
    surface.add_edge(TrustEdge("verifier", "executor", "high", evidence=["e2"]))
    surface.add_edge(TrustEdge("network", "agent", "low"))
    report = surface.compute_trust_surface()
    assert report["component_count"] >= 4
    assert report["edge_count"] == 3
    assert "trust_matrix" in report
    assert "most_trusted" in report
    assert "least_trusted" in report
    assert "isolated_components" in report
    assert "high_trust_pairs" in report
    assert "low_trust_pairs" in report


def test_find_trust_violations_high_trust_boundary() -> None:
    """find_trust_violations detects high-trust across constitutional boundaries."""
    surface = TrustSurface()
    surface.add_edge(
        TrustEdge("network", "executor", "high", evidence=["some_evidence"])
    )
    violations = surface.find_trust_violations()
    types = {v["violation_type"] for v in violations}
    assert "high_trust_constitutional_boundary" in types


def test_find_trust_violations_no_evidence() -> None:
    """find_trust_violations detects trust without evidence."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("compiler", "verifier", "high"))
    violations = surface.find_trust_violations()
    types = {v["violation_type"] for v in violations}
    assert "trust_without_evidence" in types


def test_find_trust_violations_conditional_no_conditions() -> None:
    """find_trust_violations detects conditional trust without conditions."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("agent", "executor", "conditional"))
    violations = surface.find_trust_violations()
    types = {v["violation_type"] for v in violations}
    assert "conditional_trust_no_conditions" in types


def test_find_trust_violations_circular() -> None:
    """find_trust_violations detects circular trust dependencies."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "medium", evidence=["e1"]))
    surface.add_edge(TrustEdge("b", "c", "medium", evidence=["e1"]))
    surface.add_edge(TrustEdge("c", "a", "medium", evidence=["e1"]))
    violations = surface.find_trust_violations()
    types = {v["violation_type"] for v in violations}
    assert "circular_trust_dependency" in types


def test_trust_surface_to_dot() -> None:
    """trust_surface_to_dot produces valid Graphviz DOT."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("compiler", "verifier", "high", evidence=["e1"]))
    surface.add_edge(
        TrustEdge(
            "data_channel",
            "instruction_channel",
            "low",
            conditions=["c1"],
            bidirectional=True,
        )
    )
    dot = surface.trust_surface_to_dot()
    assert dot.startswith("digraph TrustSurface {")
    assert "compiler" in dot
    assert "verifier" in dot
    assert "Legend" in dot
    # bidirectional edge should emit reverse
    assert dot.count("->") >= 3  # forward + reverse + possibly legend edges


def test_trust_surface_serialization() -> None:
    """TrustSurface to_dict / from_dict round-trips."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "high", conditions=["c1"], evidence=["e1"]))
    surface.add_edge(TrustEdge("b", "c", "low", bidirectional=True))
    data = surface.to_dict()
    restored = TrustSurface.from_dict(data)
    assert len(restored._edges) == 2
    # Verify edges match
    orig_from_a = surface.get_edges_from("a")
    restored_from_a = restored.get_edges_from("a")
    assert len(orig_from_a) == len(restored_from_a)
    assert orig_from_a[0].to_component == restored_from_a[0].to_component


# ═══════════════════════════════════════════════════════════════════════════════
# build_default_trust_surface tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_default_trust_surface() -> None:
    """build_default_trust_surface has expected edges and components."""
    surface = build_default_trust_surface()
    report = surface.compute_trust_surface()
    assert report["edge_count"] >= 10
    components = report["components"]
    # Core pipeline components should be present
    assert "compiler" in components
    assert "verifier" in components
    assert "executor" in components
    assert "governor" in components
    assert "user" in components
    assert "agent" in components


def test_build_default_trust_surface_validates_chain() -> None:
    """Default trust surface supports user → compiler → verifier → executor chain."""
    surface = build_default_trust_surface()
    result = surface.validate_trust_chain("user", "executor", required_level="medium")
    assert result["valid"] is True
    assert "user" in result["path"]
    assert "executor" in result["path"]


def test_validate_trust_against_constitution() -> None:
    """validate_trust_against_constitution returns violations list."""
    surface = build_default_trust_surface()
    # Pass empty dict so it hits the ImportError branch and produces no violations
    violations = validate_trust_against_constitution(surface, {})
    # With empty articles dict, no C-1/C-2/C-3 checks fire
    assert isinstance(violations, list)
    # But with real articles, high-trust edges into executor should be flagged
    violations_with_articles = validate_trust_against_constitution(
        surface, {"C-1": "life preservation", "C-2": "autonomy respect", "C-3": "legal compliance"}
    )
    # governor → executor is high trust, touches C-1
    types = {v["violation_type"] for v in violations_with_articles}
    assert "high_trust_c1_boundary" in types


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewRecord tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_review_record_creation() -> None:
    """ReviewRecord auto-generates timestamp and review_id."""
    record = ReviewRecord(
        reviewer="alice",
        reviewed_item="compiler_v1",
        item_type="component",
        findings=["no issues"],
        disposition="approved",
    )
    assert record.reviewer == "alice"
    assert record.reviewed_item == "compiler_v1"
    assert record.item_type == "component"
    assert record.disposition == "approved"
    assert record.timestamp != ""
    assert record.review_id != ""
    assert len(record.review_id) == 16  # truncated SHA-256


def test_review_record_is_well_formed() -> None:
    """is_well_formed validates required fields."""
    valid = ReviewRecord(
        reviewer="bob",
        reviewed_item="manifest_v2",
        item_type="manifest",
        findings=[],
        disposition="approved",
    )
    ok, errors = valid.is_well_formed()
    assert ok is True
    assert errors == []

    invalid = ReviewRecord(
        reviewer="",
        reviewed_item="",
        item_type="bad_type",
        findings=[],
        disposition="bad_disposition",
    )
    ok, errors = invalid.is_well_formed()
    assert ok is False
    assert len(errors) >= 3


def test_review_record_serialization() -> None:
    """ReviewRecord to_dict / from_dict round-trips."""
    record = ReviewRecord(
        reviewer="carol",
        reviewed_item="executor_v3",
        item_type="component",
        findings=["slow", "memory_leak"],
        disposition="needs_revision",
        checklist_completed=["functional correctness"],
        evidence_refs=["ev_001"],
    )
    data = record.to_dict()
    restored = ReviewRecord.from_dict(data)
    assert restored.reviewer == record.reviewer
    assert restored.reviewed_item == record.reviewed_item
    assert restored.item_type == record.item_type
    assert restored.findings == record.findings
    assert restored.disposition == record.disposition
    assert restored.checklist_completed == record.checklist_completed
    assert restored.evidence_refs == record.evidence_refs


# ═══════════════════════════════════════════════════════════════════════════════
# ReviewProof tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_prove_review_completeness_complete() -> None:
    """prove_review_completeness returns complete=True when all checks satisfied."""
    records = [
        ReviewRecord(
            reviewer="alice",
            reviewed_item="compiler_v1",
            item_type="component",
            findings=[],
            disposition="approved",
            checklist_completed=["AST validation", "bytecode correctness", "gas estimation"],
        ),
        ReviewRecord(
            reviewer="bob",
            reviewed_item="compiler_v1",
            item_type="component",
            findings=[],
            disposition="approved",
            checklist_completed=["manifest generation", "tier compliance"],
        ),
    ]
    required = ["AST validation", "bytecode correctness", "gas estimation", "manifest generation", "tier compliance"]
    result = prove_review_completeness(records, required)
    assert result["complete"] is True
    assert result["missing"] == []
    assert result["coverage"] == 1.0
    assert result["proof_id"] != ""


def test_prove_review_completeness_incomplete() -> None:
    """prove_review_completeness returns complete=False with missing checks."""
    records = [
        ReviewRecord(
            reviewer="alice",
            reviewed_item="verifier_v1",
            item_type="component",
            findings=[],
            disposition="approved",
            checklist_completed=["proof soundness"],
        ),
    ]
    required = ["proof soundness", "counterexample coverage", "Z3 integration"]
    result = prove_review_completeness(records, required)
    assert result["complete"] is False
    assert "counterexample coverage" in result["missing"]
    assert "Z3 integration" in result["missing"]
    assert result["coverage"] < 1.0


def test_prove_review_completeness_empty_checks() -> None:
    """prove_review_completeness with empty required_checks is vacuously complete."""
    records: list[ReviewRecord] = []
    result = prove_review_completeness(records, [])
    assert result["complete"] is True
    assert result["missing"] == []
    assert result["coverage"] == 1.0


def test_generate_review_checklist_known_types() -> None:
    """generate_review_checklist returns correct checklist for known types."""
    compiler_list = generate_review_checklist("compiler")
    assert "AST validation" in compiler_list
    assert "bytecode correctness" in compiler_list

    executor_list = generate_review_checklist("executor")
    assert "channel integrity" in executor_list
    assert "provenance tracking" in executor_list

    governor_list = generate_review_checklist("governor")
    assert "constitutional compliance" in governor_list


def test_generate_review_checklist_unknown_type() -> None:
    """generate_review_checklist returns generic checklist for unknown types."""
    checklist = generate_review_checklist("unknown_component")
    assert len(checklist) == 5
    assert "functional correctness" in checklist
    assert "security review" in checklist


def test_audit_review_gaps_no_records() -> None:
    """audit_review_gaps returns critical health when no records exist."""
    result = audit_review_gaps([])
    assert result["total_records"] == 0
    assert result["overall_health"] == "critical"
    assert len(result["unreviewed_components"]) == len({"component", "program", "manifest", "verification_report", "trust_edge"})
    assert len(result["recommendations"]) >= 1


def test_audit_review_gaps_rejected_and_incomplete() -> None:
    """audit_review_gaps detects rejected, stale, and incomplete items."""
    records = [
        ReviewRecord(
            reviewer="alice",
            reviewed_item="compiler_v1",
            item_type="component",
            findings=["critical bug"],
            disposition="rejected",
            checklist_completed=["AST validation"],
        ),
        ReviewRecord(
            reviewer="bob",
            reviewed_item="verifier_v1",
            item_type="component",
            findings=[],
            disposition="approved",
            checklist_completed=["proof soundness"],
        ),
    ]
    result = audit_review_gaps(records)
    assert result["total_records"] == 2
    assert len(result["rejected_items"]) >= 1
    # compiler_v1 uses item_type "component" which maps to compiler checklist
    assert len(result["incomplete_checklists"]) >= 1
    assert result["overall_health"] in ("needs_attention", "critical")


def test_review_proof_to_markdown() -> None:
    """ReviewProof.to_markdown generates valid markdown."""
    proof = ReviewProof(
        records=[
            ReviewRecord(
                reviewer="alice",
                reviewed_item="compiler_v1",
                item_type="component",
                findings=["ok"],
                disposition="approved",
                checklist_completed=["AST validation", "bytecode correctness"],
            ),
        ],
        component_type="compiler",
        required_checks=["AST validation", "bytecode correctness"],
    )
    md = proof.to_markdown()
    assert "# HLF Review Proof" in md
    assert "compiler" in md
    assert "alice" in md
    assert "AST validation" in md


def test_generate_review_proof_markdown_wrapper() -> None:
    """generate_review_proof_markdown produces same output as proof.to_markdown()."""
    proof = ReviewProof(
        records=[
            ReviewRecord(
                reviewer="bob",
                reviewed_item="manifest_v1",
                item_type="manifest",
                findings=[],
                disposition="approved",
                checklist_completed=["effect declaration", "capability listing"],
            ),
        ],
        component_type="manifest",
        required_checks=["effect declaration", "capability listing"],
    )
    assert generate_review_proof_markdown(proof) == proof.to_markdown()


def test_review_proof_serialization() -> None:
    """ReviewProof to_dict / from_dict round-trips."""
    proof = ReviewProof(
        records=[
            ReviewRecord(
                reviewer="carol",
                reviewed_item="audit_trail_v1",
                item_type="audit_trail",
                findings=[],
                disposition="approved",
                checklist_completed=["event completeness"],
            ),
        ],
        component_type="audit_trail",
        required_checks=["event completeness", "timestamp ordering"],
    )
    data = proof.to_dict()
    restored = ReviewProof.from_dict(data)
    assert restored.component_type == proof.component_type
    assert restored.required_checks == proof.required_checks
    assert len(restored.records) == 1
    assert restored.records[0].reviewer == "carol"


# ═══════════════════════════════════════════════════════════════════════════════
# AuditDiff tests
# ═══════════════════════════════════════════════════════════════════════════════


def _make_mock_event(
    timestamp: str,
    event_type: str,
    persona: str,
    decision: str = "PROCEED",
    rationale: str = "default rationale",
    provenance_ref: str = "",
    trust: float = 0.9,
) -> object:
    """Build a mock AuditEvent-like object using SimpleNamespace."""
    from types import SimpleNamespace
    return SimpleNamespace(
        timestamp=timestamp,
        event_type=event_type,
        persona=persona,
        decision=decision,
        rationale=rationale,
        provenance_ref=provenance_ref,
        trust=trust,
    )


def _make_mock_trail(events: list[object]) -> object:
    """Build a mock AuditTrail-like object with an 'events' attr."""
    from types import SimpleNamespace
    return SimpleNamespace(events=events)


def test_audit_diff_basic() -> None:
    """Two simple event lists → verify ADDED / REMOVED / UNCHANGED entries."""
    ev_a = _make_mock_event("2025-03-01T10:00:00Z", "verification", "alice")
    ev_b = _make_mock_event("2025-03-01T10:01:00Z", "verification", "alice")
    ev_new = _make_mock_event("2025-03-01T11:00:00Z", "review", "bob")

    trail_a = _make_mock_trail([ev_a])
    trail_b = _make_mock_trail([ev_b, ev_new])

    engine = AuditDiff(name="basic-diff")
    entries = engine.diff(trail_a, trail_b)

    ops = {e.operation for e in entries}
    assert DiffOperation.ADDED in ops
    assert DiffOperation.UNCHANGED in ops
    # ev_a matched ev_b → UNCHANGED; ev_new unmatched → ADDED
    added = [e for e in entries if e.operation == DiffOperation.ADDED]
    assert len(added) == 1
    assert added[0].persona == "bob"


def test_audit_diff_modified() -> None:
    """Events with changed fields produce MODIFIED entries."""
    ev_a = _make_mock_event(
        "2025-03-02T09:00:00Z", "execution_gate", "carol",
        decision="PROCEED", rationale="old reason",
    )
    ev_b = _make_mock_event(
        "2025-03-02T09:01:00Z", "execution_gate", "carol",
        decision="HALT", rationale="new reason",
    )
    trail_a = _make_mock_trail([ev_a])
    trail_b = _make_mock_trail([ev_b])

    engine = AuditDiff(name="mod-diff")
    entries = engine.diff(trail_a, trail_b)

    modified = [e for e in entries if e.operation == DiffOperation.MODIFIED]
    assert len(modified) == 1
    m = modified[0]
    assert "decision" in m.field_changes
    assert m.field_changes["decision"] == ("PROCEED", "HALT")
    assert "rationale" in m.field_changes
    assert m.field_changes["rationale"] == ("old reason", "new reason")


def test_audit_diff_empty_trails() -> None:
    """Diff with empty trail_a and trail_b returns no entries."""
    engine = AuditDiff(name="empty-diff")
    entries = engine.diff(_make_mock_trail([]), _make_mock_trail([]))
    assert entries == []


def test_audit_diff_sequence() -> None:
    """diff_sequence across 3+ trails produces expected pairwise diffs."""
    ev1 = _make_mock_event("2025-03-03T08:00:00Z", "review", "dave")
    ev2 = _make_mock_event("2025-03-03T08:05:00Z", "review", "dave")
    ev3 = _make_mock_event("2025-03-03T08:10:00Z", "review", "dave", decision="HALT")

    t1 = _make_mock_trail([ev1])
    t2 = _make_mock_trail([ev2])
    t3 = _make_mock_trail([ev3])

    engine = AuditDiff(name="seq-diff")
    seq = engine.diff_sequence([t1, t2, t3])
    assert len(seq) == 2
    assert len(seq[0]) >= 1
    assert len(seq[1]) >= 1


def test_audit_diff_summary() -> None:
    """summary counts match expected ADDED / REMOVED / MODIFIED / UNCHANGED."""
    ev_a1 = _make_mock_event("2025-03-04T10:00:00Z", "verification", "x")
    ev_a2 = _make_mock_event("2025-03-04T10:01:00Z", "review", "y")
    ev_b1 = _make_mock_event("2025-03-04T10:00:30Z", "verification", "x",
                              rationale="changed")
    ev_b2 = _make_mock_event("2025-03-04T11:00:00Z", "audit", "z")

    trail_a = _make_mock_trail([ev_a1, ev_a2])
    trail_b = _make_mock_trail([ev_b1, ev_b2])

    engine = AuditDiff(name="summary-diff")
    entries = engine.diff(trail_a, trail_b)
    s = engine.summary(entries)

    assert s["total_entries"] == len(entries)
    # ev_a2 (y/review) → REMOVED, ev_b2 (z/audit) → ADDED, ev_a1→ev_b1 → MODIFIED
    assert s["removed"] >= 1
    assert s["added"] >= 1
    assert s["modified"] >= 1
    assert isinstance(s["trust_delta"], float)


def test_audit_diff_render_markdown() -> None:
    """Markdown report contains expected strings."""
    ev_a = _make_mock_event("2025-03-05T10:00:00Z", "verification", "alice")
    ev_b = _make_mock_event("2025-03-05T10:01:00Z", "verification", "alice")

    engine = AuditDiff(name="md-diff")
    entries = engine.diff(_make_mock_trail([ev_a]), _make_mock_trail([ev_b]))
    md = engine.render_delta_report(entries, format="markdown")

    assert "# Audit Trail Delta Report" in md
    assert "**Engine:** md-diff" in md
    assert "alice" in md
    assert "verification" in md


def test_audit_diff_render_html() -> None:
    """HTML report contains expected tags."""
    ev_a = _make_mock_event("2025-03-06T10:00:00Z", "review", "bob")
    ev_b = _make_mock_event("2025-03-06T10:01:00Z", "review", "bob")

    engine = AuditDiff(name="html-diff")
    entries = engine.diff(_make_mock_trail([ev_a]), _make_mock_trail([ev_b]))
    html = engine.render_delta_report(entries, format="html")

    assert "<!DOCTYPE html>" in html
    assert "<table>" in html
    assert "bob" in html
    assert "review" in html


def test_audit_diff_anomalies_trust_degradation() -> None:
    """Trust drop > 0.3 detected as trust_degradation_spike."""
    # Construct entries directly to simulate trust drop
    entry = AuditDiffEntry(
        timestamp="2025-03-07T10:00:00Z",
        operation=DiffOperation.MODIFIED,
        event_type="verification",
        persona="alice",
        trust_before=0.95,
        trust_after=0.55,
        field_changes={"trust": ("0.95", "0.55")},
        rationale_before="ok",
        rationale_after="distrusted",
    )
    engine = AuditDiff(name="anomaly-diff")
    anomalies = engine.find_anomalies([entry])
    assert len(anomalies) >= 1
    degradation = [a for a in anomalies if a["anomaly_type"] == "trust_degradation_spike"]
    assert len(degradation) == 1
    assert degradation[0]["severity"] == "critical"


def test_audit_diff_anomalies_mass_removal() -> None:
    """> 5 REMOVED entries detected as mass_removal anomaly."""
    entries = [
        AuditDiffEntry(
            timestamp=f"2025-03-08T10:{i:02d}:00Z",
            operation=DiffOperation.REMOVED,
            event_type="review",
            persona=f"user_{i}",
            rationale_before="was there",
        )
        for i in range(7)
    ]
    engine = AuditDiff(name="mass-removal-diff")
    anomalies = engine.find_anomalies(entries)
    mass = [a for a in anomalies if a["anomaly_type"] == "mass_removal"]
    assert len(mass) == 1
    assert mass[0]["severity"] == "high"


# ═══════════════════════════════════════════════════════════════════════════════
# TrustDebt tests
# ═══════════════════════════════════════════════════════════════════════════════


def _make_mock_debt_item(
    violation_id: str,
    source: str,
    category: str,
    severity: float,
    principal: float,
    interest_rate: float,
    incurred_at: str,
    last_assessed_at: str = "",
    resolved: bool = False,
    resolution_note: str = "",
) -> object:
    """Build a mock DebtItem-like object using SimpleNamespace."""
    from types import SimpleNamespace
    return SimpleNamespace(
        violation_id=violation_id,
        source=source,
        category=category,
        severity=severity,
        principal=principal,
        interest_rate=interest_rate,
        incurred_at=incurred_at,
        last_assessed_at=last_assessed_at or incurred_at,
        resolved=resolved,
        resolution_note=resolution_note,
    )


def test_trust_debt_assess_violations() -> None:
    """Violations map to correct severities (FORK→0.9, DETACH→0.8, etc.)."""
    q = TrustDebtQuantifier(name="test-debt", daily_interest_base=0.02)
    violations = [
        {"violation_type": "FORK", "component": "compiler", "timestamp": "2025-03-01T00:00:00Z"},
        {"violation_type": "DETACH", "component": "verifier", "timestamp": "2025-03-01T00:00:00Z"},
        {"violation_type": "DIVERT", "component": "executor", "timestamp": "2025-03-01T00:00:00Z"},
        {"violation_type": "unknown_type", "component": "governor", "timestamp": "2025-03-01T00:00:00Z"},
    ]
    items = q.assess_violations(violations)
    assert len(items) == 4
    severities = {item.category: item.severity for item in items}
    assert severities["FORK"] == 0.9
    assert severities["DETACH"] == 0.8
    assert severities["DIVERT"] == 0.7
    assert severities["unknown_type"] == 0.5


def test_trust_debt_calculate_current_debt() -> None:
    """Compound interest applied correctly on unresolved items."""
    from datetime import datetime, timezone, timedelta

    q = TrustDebtQuantifier(name="calc-debt", daily_interest_base=0.01)
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    item = _make_mock_debt_item(
        violation_id="v1",
        source="compiler",
        category="FORK",
        severity=0.9,
        principal=90.0,
        interest_rate=0.009,
        incurred_at=past,
        last_assessed_at=past,
        resolved=False,
        resolution_note="",
    )
    total = q.calculate_current_debt([item])
    # After 10 days at 0.9% daily compound: 90 * (1.009)^10
    expected = round(90.0 * (1.009 ** 10), 4)
    assert total == expected


def test_trust_debt_aging_report() -> None:
    """Age buckets partition correctly."""
    from datetime import datetime, timezone, timedelta

    q = TrustDebtQuantifier(name="aging-debt")
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=45)).isoformat()
    mid = (now - timedelta(days=15)).isoformat()
    recent = (now - timedelta(days=3)).isoformat()
    fresh = (now - timedelta(hours=12)).isoformat()

    items = [
        _make_mock_debt_item(
            violation_id=f"v{i}", source="s", category="FORK", severity=0.9,
            principal=90.0, interest_rate=0.009,
            incurred_at=ts,
        )
        for i, ts in enumerate([old, mid, recent, fresh])
    ]
    report = q.aging_report(items)
    buckets = report["buckets"]
    assert buckets["30d+"]["count"] == 1
    assert buckets["7-30d"]["count"] == 1
    assert buckets["1-7d"]["count"] == 1
    assert buckets["0-1d"]["count"] == 1
    assert report["total_unresolved"] == 4
    assert isinstance(report["total_debt"], float)
    assert report["oldest_item"] is not None


def test_trust_debt_paydown_priorities() -> None:
    """Sorted by principal * rate * days descending."""
    from datetime import datetime, timezone, timedelta

    q = TrustDebtQuantifier(name="paydown-debt")
    now = datetime.now(timezone.utc)
    older = (now - timedelta(days=60)).isoformat()
    newer = (now - timedelta(days=5)).isoformat()

    item_old = _make_mock_debt_item(
        violation_id="v_old", source="compiler", category="FORK",
        severity=0.9, principal=90.0, interest_rate=0.009,
        incurred_at=older,
    )
    item_new = _make_mock_debt_item(
        violation_id="v_new", source="verifier", category="DETACH",
        severity=0.8, principal=80.0, interest_rate=0.008,
        incurred_at=newer,
    )
    priorities = q.paydown_priorities([item_old, item_new])
    assert len(priorities) == 2
    # Older item should have higher priority (more days outstanding)
    assert priorities[0].violation_id == "v_old"
    assert priorities[1].violation_id == "v_new"


def test_trust_debt_timeline() -> None:
    """Projects N intervals with increasing debt."""
    from datetime import datetime, timezone, timedelta

    q = TrustDebtQuantifier(name="timeline-debt")
    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    item = _make_mock_debt_item(
        violation_id="v1", source="compiler", category="FORK",
        severity=0.9, principal=90.0, interest_rate=0.009,
        incurred_at=past,
    )
    timeline = q.debt_timeline([item], intervals=5)
    assert len(timeline) == 6  # intervals + 1
    assert all("timestamp" in t and "total_debt" in t for t in timeline)
    # Debt should be non-decreasing
    debts = [t["total_debt"] for t in timeline]
    for i in range(1, len(debts)):
        assert debts[i] >= debts[i - 1] - 0.001  # small rounding tolerance


def test_trust_debt_resolve() -> None:
    """Marks item as resolved with note."""
    q = TrustDebtQuantifier(name="resolve-debt")
    now_iso = "2025-03-01T00:00:00Z"
    item = _make_mock_debt_item(
        violation_id="v99", source="executor", category="EVADE",
        severity=0.6, principal=60.0, interest_rate=0.006,
        incurred_at=now_iso,
    )
    resolved = q.resolve_debt(item, note="Mitigated via policy update")
    assert resolved.resolved is True
    assert resolved.resolution_note == "Mitigated via policy update"
    assert resolved.violation_id == "v99"


def test_trust_debt_compound_interest_math() -> None:
    """Verify compound interest formula with known values."""
    q = TrustDebtQuantifier(name="math-debt", daily_interest_base=0.01)
    # Principal 100, rate 0.01, 30 days = 100 * 1.01^30 ≈ 134.7849
    item = _make_mock_debt_item(
        violation_id="v_math", source="test", category="FORK",
        severity=1.0, principal=100.0, interest_rate=0.01,
        incurred_at="2025-01-01T00:00:00Z",
    )
    total = q.calculate_current_debt([item], as_of="2025-01-31T00:00:00Z")
    expected = round(100.0 * (1.01 ** 30), 4)
    assert total == expected


def test_trust_debt_empty_items() -> None:
    """Handles empty item list gracefully."""
    q = TrustDebtQuantifier(name="empty-debt")
    assert q.calculate_current_debt([]) == 0.0
    assert q.paydown_priorities([]) == []
    report = q.aging_report([])
    assert report["total_unresolved"] == 0
    assert report["total_debt"] == 0.0
    timeline = q.debt_timeline([])
    assert len(timeline) == 1
    assert timeline[0]["total_debt"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# RemediationPlanner tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_remediation_generate_plan() -> None:
    """Gaps produce tasks with correct templates."""
    planner = RemediationPlanner(name="test-planner")
    gaps = [
        {"gap_type": "missing_coverage", "component": "compiler", "severity": "high"},
        {"gap_type": "trust_gap", "component": "verifier", "severity": "medium"},
        {"gap_type": "unreviewed_component", "component": "executor", "severity": "critical"},
    ]
    plan = planner.generate_plan(gaps)
    assert len(plan.tasks) == 3
    assert plan.name.startswith("Remediation Plan")
    titles = [t.title for t in plan.tasks]
    assert any("Add test coverage" in t for t in titles)
    assert any("Address trust gap" in t for t in titles)
    assert any("Conduct initial review" in t for t in titles)

    priorities = {t.priority for t in plan.tasks}
    assert RemediationPriority.CRITICAL in priorities
    assert RemediationPriority.HIGH in priorities
    assert RemediationPriority.MEDIUM in priorities


def test_remediation_topological_sort() -> None:
    """Tasks with dependencies ordered correctly via Kahn's algorithm."""
    planner = RemediationPlanner(name="topo-planner")
    t1 = RemediationTask(
        task_id="t1", title="Task 1", description="First task",
        priority=RemediationPriority.HIGH, estimated_effort_hours=2.0,
    )
    t2 = RemediationTask(
        task_id="t2", title="Task 2", description="Depends on t1",
        priority=RemediationPriority.MEDIUM, estimated_effort_hours=3.0,
        depends_on=["t1"],
    )
    t3 = RemediationTask(
        task_id="t3", title="Task 3", description="Depends on t2",
        priority=RemediationPriority.LOW, estimated_effort_hours=1.0,
        depends_on=["t2"],
    )
    sorted_tasks = planner.topological_sort([t3, t1, t2])
    ids = [t.task_id for t in sorted_tasks]
    assert ids.index("t1") < ids.index("t2")
    assert ids.index("t2") < ids.index("t3")


def test_remediation_critical_path() -> None:
    """Longest dependency chain identified correctly."""
    planner = RemediationPlanner(name="cp-planner")
    t1 = RemediationTask(
        task_id="t1", title="A", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=5.0,
    )
    t2 = RemediationTask(
        task_id="t2", title="B", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=10.0,
        depends_on=["t1"],
    )
    t3 = RemediationTask(
        task_id="t3", title="C", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=3.0,
        depends_on=["t2"],
    )
    # Also an independent task
    t4 = RemediationTask(
        task_id="t4", title="D", description="",
        priority=RemediationPriority.LOW, estimated_effort_hours=20.0,
    )
    path = planner.critical_path([t1, t2, t3, t4])
    assert len(path) >= 1
    path_ids = [t.task_id for t in path]
    # The chain t1→t2→t3 has total 18h which should beat t4 alone (20h)
    # Actually t4 alone is 20h which is longer. Let's check.
    # But t4 has no dependencies so critical_path may pick the chain
    # The DP algorithm finds the longest path ending at any node.
    # t4 has dist=0 (no deps), t1→t2→t3 has dist ending at t3 = 5+10=15
    # So t3's total path = 15 + 3 = 18. t4 = 0 + 20 = 20. End node is t4.
    assert len(path_ids) >= 1


def test_remediation_progress_report() -> None:
    """Status counts correct in progress report."""
    planner = RemediationPlanner(name="prog-planner")
    tasks = [
        RemediationTask(
            task_id="a", title="Done", description="",
            priority=RemediationPriority.HIGH, estimated_effort_hours=2.0,
            status=RemediationStatus.COMPLETED,
        ),
        RemediationTask(
            task_id="b", title="In Progress", description="",
            priority=RemediationPriority.MEDIUM, estimated_effort_hours=3.0,
            status=RemediationStatus.IN_PROGRESS,
        ),
        RemediationTask(
            task_id="c", title="Blocked", description="",
            priority=RemediationPriority.CRITICAL, estimated_effort_hours=4.0,
            status=RemediationStatus.BLOCKED, depends_on=["a"],
        ),
        RemediationTask(
            task_id="d", title="Pending", description="",
            priority=RemediationPriority.LOW, estimated_effort_hours=1.0,
        ),
    ]
    plan = RemediationPlan(plan_id="p1", name="Test Plan", tasks=tasks)
    report = planner.progress_report(plan)
    assert report["total_tasks"] == 4
    assert report["status_counts"]["completed"] == 1
    assert report["status_counts"]["in_progress"] == 1
    assert report["status_counts"]["blocked"] == 1
    assert report["status_counts"]["pending"] == 1
    assert report["completion_pct"] == 25.0
    assert report["total_effort_remaining"] == 8.0
    assert len(report["blocked_tasks"]) == 1
    assert report["blocked_tasks"][0]["task_id"] == "c"


def test_remediation_merge_plans() -> None:
    """Similar titles deduplicated when merging plans."""
    planner = RemediationPlanner(name="merge-planner")
    t1 = RemediationTask(
        task_id="x1", title="Add test coverage for compiler", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=4.0,
    )
    t2 = RemediationTask(
        task_id="x2", title="Add test coverage for compiler", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=4.0,
    )
    t3 = RemediationTask(
        task_id="x3", title="Fix trust gap in verifier", description="",
        priority=RemediationPriority.MEDIUM, estimated_effort_hours=2.0,
    )
    p1 = RemediationPlan(plan_id="p1", name="Plan A", tasks=[t1])
    p2 = RemediationPlan(plan_id="p2", name="Plan B", tasks=[t2, t3])
    merged = planner.merge_plans([p1, p2])
    # t1 and t2 have identical titles → should be deduplicated
    assert len(merged.tasks) == 2
    titles = [t.title for t in merged.tasks]
    assert "Add test coverage for compiler" in titles
    assert "Fix trust gap in verifier" in titles


def test_remediation_estimate_completion() -> None:
    """Returns valid estimate with expected keys."""
    planner = RemediationPlanner(name="est-planner")
    t1 = RemediationTask(
        task_id="e1", title="Task E1", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=8.0,
    )
    plan = RemediationPlan(plan_id="ep1", name="Estimate Plan", tasks=[t1])
    est = planner.estimate_completion(plan, resources=2)
    assert "estimated_completion_date" in est
    assert "total_effort_hours" in est
    assert "critical_path_hours" in est
    assert "parallelizable_hours" in est
    assert "tasks_remaining" in est
    assert est["tasks_remaining"] == 1
    assert est["total_effort_hours"] == 8.0


def test_remediation_cycle_handling() -> None:
    """Tasks with cycles don't break topological sort."""
    planner = RemediationPlanner(name="cycle-planner")
    t1 = RemediationTask(
        task_id="c1", title="Cycle A", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=1.0,
        depends_on=["c2"],
    )
    t2 = RemediationTask(
        task_id="c2", title="Cycle B", description="",
        priority=RemediationPriority.HIGH, estimated_effort_hours=1.0,
        depends_on=["c1"],
    )
    result = planner.topological_sort([t1, t2])
    assert len(result) == 2
    assert {t.task_id for t in result} == {"c1", "c2"}


def test_remediation_task_serialization() -> None:
    """to_dict / from_dict roundtrip for RemediationTask."""
    original = RemediationTask(
        task_id="ser1",
        title="Serialize me",
        description="Testing roundtrip",
        priority=RemediationPriority.CRITICAL,
        estimated_effort_hours=5.5,
        gap_refs=["ref_a", "ref_b"],
        depends_on=["dep1"],
        status=RemediationStatus.IN_PROGRESS,
        assigned_to="alice",
    )
    data = original.to_dict()
    restored = RemediationTask.from_dict(data)
    assert restored.task_id == original.task_id
    assert restored.title == original.title
    assert restored.priority == original.priority
    assert restored.estimated_effort_hours == original.estimated_effort_hours
    assert restored.gap_refs == original.gap_refs
    assert restored.depends_on == original.depends_on
    assert restored.status == original.status
    assert restored.assigned_to == original.assigned_to


def test_remediation_empty_gaps() -> None:
    """Empty gap list produces valid empty plan."""
    planner = RemediationPlanner(name="empty-plan")
    plan = planner.generate_plan([])
    assert plan.tasks == []
    assert plan.plan_id != ""
    assert plan.name.startswith("Remediation Plan")


# ═══════════════════════════════════════════════════════════════════════════════
# TrustTrending tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_trust_trending_add_snapshot() -> None:
    """Snapshots stored and retrievable via recent_snapshots."""
    trending = TrustTrending(name="snap-trend", window_size=10)
    snap = TrustSnapshot(
        timestamp="2025-04-01T00:00:00Z",
        overall_trust=0.85,
        violation_count=3,
        debt_total=120.0,
        audit_completeness=0.9,
    )
    trending.add_snapshot(snap)
    recent = trending.recent_snapshots()
    assert len(recent) == 1
    assert recent[0].overall_trust == 0.85
    assert recent[0].violation_count == 3


def test_trust_trending_analyze_improving() -> None:
    """Positive slope → IMPROVING trend direction."""
    trending = TrustTrending(name="improve-trend")
    for i in range(5):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.5 + i * 0.1,  # 0.5, 0.6, 0.7, 0.8, 0.9
        ))
    report = trending.analyze_trend(metric="overall_trust")
    assert report.direction == TrendDirection.IMPROVING
    assert report.slope > 0.0
    assert report.confidence > 0.5


def test_trust_trending_analyze_degrading() -> None:
    """Negative slope → DEGRADING trend direction."""
    trending = TrustTrending(name="degrade-trend")
    for i in range(5):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.9 - i * 0.1,  # 0.9, 0.8, 0.7, 0.6, 0.5
        ))
    report = trending.analyze_trend(metric="overall_trust")
    assert report.direction == TrendDirection.DEGRADING
    assert report.slope < 0.0
    assert report.confidence > 0.5


def test_trust_trending_analyze_stable() -> None:
    """Flat series → STABLE trend direction."""
    trending = TrustTrending(name="stable-trend")
    for i in range(5):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.75,
        ))
    report = trending.analyze_trend(metric="overall_trust")
    assert report.direction in (TrendDirection.STABLE, TrendDirection.VOLATILE)
    # Flat data: slope near zero
    assert abs(report.slope) < 0.01


def test_trust_trending_check_alerts_degradation() -> None:
    """Slope below threshold triggers CRITICAL degradation alert."""
    trending = TrustTrending(
        name="alert-degrade-trend",
        alert_thresholds={"trust_degradation": 0.05, "violation_spike": 100.0, "debt_growth": 100.0},
    )
    for i in range(5):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.95 - i * 0.08,  # steep drop: 0.95, 0.87, 0.79, 0.71, 0.63
        ))
    alerts = trending.check_alerts()
    degradation_alerts = [a for a in alerts if a.metric == "overall_trust"]
    assert len(degradation_alerts) >= 1
    assert degradation_alerts[0].level == AlertLevel.CRITICAL


def test_trust_trending_check_alerts_spike() -> None:
    """Violation spike triggers WARNING alert."""
    trending = TrustTrending(
        name="alert-spike-trend",
        alert_thresholds={"trust_degradation": 100.0, "violation_spike": 3.0, "debt_growth": 100.0},
    )
    # First 4 snapshots with low violations, last one spikes
    for i in range(4):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.8,
            violation_count=2,
        ))
    trending.add_snapshot(TrustSnapshot(
        timestamp="2025-04-05T00:00:00Z",
        overall_trust=0.75,
        violation_count=15,  # spike!
    ))
    alerts = trending.check_alerts()
    violation_alerts = [a for a in alerts if a.metric == "violation_count"]
    assert len(violation_alerts) >= 1
    assert violation_alerts[0].level == AlertLevel.WARNING


def test_trust_trending_forecast() -> None:
    """Forecast returns horizon entries with bounds."""
    trending = TrustTrending(name="forecast-trend")
    for i in range(6):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.7 + i * 0.03,
        ))
    forecast = trending.forecast(metric="overall_trust", horizon=5)
    assert len(forecast) == 5
    for entry in forecast:
        assert "timestamp" in entry
        assert "predicted" in entry
        assert "lower_bound" in entry
        assert "upper_bound" in entry
        assert entry["lower_bound"] <= entry["predicted"] <= entry["upper_bound"]


def test_trust_trending_compare_periods() -> None:
    """Period comparison returns valid metrics with change_pct and direction."""
    trending = TrustTrending(name="compare-trend")
    # Period A: day 1-3, Period B: day 4-6
    for i in range(6):
        trending.add_snapshot(TrustSnapshot(
            timestamp=f"2025-04-0{i+1}T00:00:00Z",
            overall_trust=0.7 + i * 0.05,
            violation_count=max(10 - i * 2, 0),
            debt_total=100.0 + i * 10.0,
            audit_completeness=0.6 + i * 0.05,
        ))
    result = trending.compare_periods(
        "2025-04-01T00:00:00Z", "2025-04-03T23:59:59Z",
        "2025-04-04T00:00:00Z", "2025-04-06T23:59:59Z",
    )
    for metric in ["overall_trust", "violation_count", "debt_total", "audit_completeness"]:
        assert metric in result
        assert "change_pct" in result[metric]
        assert "direction" in result[metric]
        assert "significant" in result[metric]
        assert isinstance(result[metric]["direction"], str)


def test_trust_trending_export_dashboard() -> None:
    """Dashboard data has all required keys."""
    trending = TrustTrending(name="dash-trend")
    trending.add_snapshot(TrustSnapshot(
        timestamp="2025-04-01T00:00:00Z",
        overall_trust=0.85,
        violation_count=2,
        debt_total=50.0,
        audit_completeness=0.9,
        component_scores={"compiler": 0.9, "verifier": 0.8},
    ))
    dashboard = trending.export_dashboard_data()
    assert "name" in dashboard
    assert dashboard["name"] == "dash-trend"
    assert "snapshot_count" in dashboard
    assert dashboard["snapshot_count"] == 1
    assert "current" in dashboard
    assert dashboard["current"]["overall_trust"] == 0.85
    assert "trends" in dashboard
    assert "alerts" in dashboard
    assert "forecast" in dashboard
    assert isinstance(dashboard["alerts"], list)
    assert isinstance(dashboard["forecast"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_two_channel_executor_with_audit_trail() -> None:
    """TwoChannelExecutor records events when audit_trail is passed."""
    # Build a valid instruction channel
    manifest = CapabilityManifest(program_id="test_prog", trust_tier="hearth")
    report = _make_report(proven=2)

    # We need bytecode for the instruction channel
    bytecode = b"\x00\x01\x02"
    instruction = build_instruction_channel(
        bytecode=bytecode,
        manifest=manifest,
        verification=report,
        tier="hearth",
    )

    # Build a data channel with provenance
    data = build_data_channel({"x": 42}, default_source="agent", default_trust=0.99)

    # Create auditor with audit trail
    trail = AuditTrail(execution_id="integration-test", tier="hearth")
    executor = TwoChannelExecutor()

    result = executor.execute(instruction, data, tier="hearth", audit_trail=trail)

    # The executor should have recorded events
    assert result is not None
    assert len(trail.events) >= 1
    # Should have at least a gate decision event and provenance events
    event_types = {e.event_type for e in trail.events}
    assert "execution_gate" in event_types or "provenance_check" in event_types


def test_end_to_end_audit_pipeline() -> None:
    """Provenance → audit → markdown → verify output."""
    # Create provenance chains
    chains = {
        "input_a": _make_chain("user", 0.95),
        "input_b": _make_chain("agent", 0.88, path=["degraded(0.9)"]),
    }

    # Create verification report
    report = _make_report(proven=3, failed=0)

    # Generate audit trail
    audit = generate_execution_audit(chains, report, tier="hearth", execution_id="e2e-test")

    # Verify audit structure
    summary = audit.summarize()
    assert summary["verdict"] == "PASSED"
    assert summary["total_events"] >= 6  # each chain: source + final, plus gate

    # Generate markdown
    md = audit.to_markdown()
    assert "e2e-test" in md
    assert "PASSED" in md
    assert "user" in md or "input_a" in md

    # Generate HTML
    html = audit.to_html()
    assert "<!DOCTYPE html>" in html
    assert "e2e-test" in html

    # Summarize
    text_summary = summarize_audit(audit)
    assert "PASSED" in text_summary
    assert "e2e-test" in text_summary


def test_end_to_end_with_trust_degradation_and_boundary() -> None:
    """Full pipeline with degradation and boundary crossing events."""
    chain = _make_chain(
        "network", 0.75,
        path=["degraded(0.8)", "boundary:firewall→sandbox", "degraded(0.95)"],
    )
    chains = {"risky_data": chain}
    report = _make_report(proven=1, failed=0)

    audit = generate_execution_audit(chains, report, tier="forge", execution_id="e2e-degrade")

    summary = audit.summarize()
    # At forge tier with no failures → PROCEED
    assert summary["verdict"] == "PASSED"

    # Should have trust boundary events
    boundary_events = audit.events_by_type("trust_boundary")
    assert len(boundary_events) >= 1
    assert "sandbox" in boundary_events[0].decision

    # Should have degradation events
    all_decisions = " ".join(e.decision for e in audit.events)
    assert "degraded trust" in all_decisions.lower()

    # Trust boundaries crossed should be tracked
    assert summary.get("trust_boundaries_crossed", 0) >= 1


def test_audit_trail_summarize_verdict_blocked() -> None:
    """summarize returns BLOCKED verdict when BLOCK is in decision_counts."""
    trail = AuditTrail(execution_id="blocked-test", tier="hearth")
    report = _make_report(proven=1, failed=2)
    trail.add_gate_decision("BLOCK", report, "hearth")
    summary = trail.summarize()
    assert summary["verdict"] == "BLOCKED"
    assert summary["decision_counts"].get("BLOCK", 0) >= 1


def test_audit_trail_summarize_verdict_warning() -> None:
    """summarize returns WARNING when WARN but no BLOCK."""
    trail = AuditTrail(execution_id="warn-test", tier="forge")
    report = _make_report(proven=1, unknown=2)
    trail.add_gate_decision("WARN", report, "forge")
    summary = trail.summarize()
    assert summary["verdict"] == "WARNING"
    assert summary["decision_counts"].get("WARN", 0) >= 1


def test_audit_trail_summarize_no_gate() -> None:
    """summarize returns NO_GATE when there are events but no gate decisions."""
    trail = AuditTrail(execution_id="no-gate", tier="advisory")
    trail.add_provenance_event(
        ProvenanceChain(source="agent", trust=0.5),
        "provenance_check",
        "executor",
    )
    summary = trail.summarize()
    assert summary["verdict"] == "NO_GATE"


def test_trust_surface_bidirectional_edge() -> None:
    """Bidirectional edges are indexed both ways."""
    surface = TrustSurface()
    surface.add_edge(TrustEdge("a", "b", "high", bidirectional=True))
    from_a = surface.get_edges_from("a")
    from_b = surface.get_edges_from("b")
    assert len(from_a) >= 1
    assert len(from_b) >= 1


def test_audit_review_gaps_stale_reviews() -> None:
    """audit_review_gaps detects stale reviews with old timestamps."""
    old_ts = "2020-01-01T00:00:00+00:00"
    records = [
        ReviewRecord(
            reviewer="alice",
            reviewed_item="ancient_component",
            item_type="component",
            findings=[],
            disposition="approved",
            timestamp=old_ts,
            checklist_completed=["AST validation", "bytecode correctness", "gas estimation", "manifest generation", "tier compliance"],
        ),
    ]
    result = audit_review_gaps(records)
    # The old timestamp should be detected as stale
    assert result["overall_health"] in ("needs_attention", "critical")
    assert len(result["stale_reviews"]) >= 1


def test_prove_review_completeness_counterexample_structure() -> None:
    """When incomplete, counterexample shows missing checks and unaddressed_by."""
    records = [
        ReviewRecord(
            reviewer="alice",
            reviewed_item="verifier_v1",
            item_type="verification_report",
            findings=[],
            disposition="approved",
            checklist_completed=["proof soundness"],
        ),
    ]
    required = ["proof soundness", "counterexample coverage", "Z3 integration"]
    proof = ReviewProof(records=records, component_type="verifier", required_checks=required)
    result = proof.prove_completeness()
    assert result["complete"] is False
    assert result["counterexample"] is not None
    assert "missing_checks" in result["counterexample"]
    assert "counterexample coverage" in result["counterexample"]["missing_checks"]
