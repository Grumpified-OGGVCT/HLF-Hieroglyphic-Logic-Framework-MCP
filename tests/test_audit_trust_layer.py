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
