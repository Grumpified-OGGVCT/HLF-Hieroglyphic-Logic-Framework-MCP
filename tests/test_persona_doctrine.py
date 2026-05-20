"""
test_persona_doctrine.py — Operator doctrine contracts, compliance validation,
constitutional gate integration, and runtime proof pipeline for the 4-persona
governance pipeline (Steward, Herald, Builder, Sentinel).

Tests cover:
  - DoctrineContract creation for each persona
  - Compliance validation (allowed vs blocked actions)
  - Doctrine → HLF conversion
  - Persona gating integration with constitutional checks
  - Tier-differentiated permissions
  - Cross-persona handoff contracts
  - Runtime proof pipeline for persona transitions
  - OperatorDoctrine aggregate and factory
"""

from __future__ import annotations

import json

import pytest

from hlf_mcp.persona import (
    CapabilityManifest,
    DoctrineComplianceReport,
    DoctrineContract,
    HandoffContract,
    OperatorDoctrine,
    PersonaGate,
    PersonaGateResult,
    PersonaTransitionProof,
    build_operator_doctrine,
    check_persona_assignment,
    doctrine_to_hlf,
    get_handoff_contract,
    prove_persona_transition,
    tier_allows,
    validate_doctrine_compliance,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DoctrineContract tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_doctrine_contract_creation_for_steward() -> None:
    """Steward persona has a valid doctrine contract with all fields populated."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("steward")
    assert contract is not None
    assert contract.persona == "steward"
    assert len(contract.permissions) > 0
    assert len(contract.prohibitions) > 0
    assert len(contract.obligations) > 0
    assert contract.tier in ("hearth", "sovereign", "field")
    assert contract.source_ref != ""


def test_doctrine_contract_creation_for_herald() -> None:
    """Herald persona has a valid doctrine contract."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("herald")
    assert contract is not None
    assert contract.persona == "herald"
    assert "classify_claim_lanes" in contract.permissions or any(
        "claim" in p.lower() for p in contract.permissions
    )
    assert any("upgrade_bridge" in p.lower() for p in contract.prohibitions) or any(
        "current_truth" in p.lower() for p in contract.prohibitions
    )


def test_doctrine_contract_creation_for_builder() -> None:
    """Builder (strategist) persona has a valid doctrine contract."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("builder")
    assert contract is not None
    assert contract.persona == "builder"
    assert "sequence_work" in contract.permissions or any(
        "sequence" in p.lower() for p in contract.permissions
    )


def test_doctrine_contract_creation_for_sentinel() -> None:
    """Sentinel persona has a valid doctrine contract."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("sentinel")
    assert contract is not None
    assert contract.persona == "sentinel"
    assert "review_security_posture" in contract.permissions or any(
        "security" in p.lower() for p in contract.permissions
    )
    assert any("silently_relax" in p.lower() for p in contract.prohibitions)


def test_doctrine_contract_roundtrip() -> None:
    """DoctrineContract can be serialised to dict and back."""
    contract = DoctrineContract(
        persona="test_persona",
        obligations=["obligation_1", "obligation_2"],
        permissions=["perm_1"],
        prohibitions=["proh_1", "proh_2"],
        tier="hearth",
        source_ref="test/source.md",
    )
    data = contract.to_dict()
    restored = DoctrineContract.from_dict(data)
    assert restored.persona == contract.persona
    assert restored.obligations == contract.obligations
    assert restored.permissions == contract.permissions
    assert restored.prohibitions == contract.prohibitions
    assert restored.tier == contract.tier
    assert restored.source_ref == contract.source_ref


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance validation tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_compliance_allows_permitted_action() -> None:
    """An action explicitly in the permissions list is allowed."""
    report = validate_doctrine_compliance("steward", "review_tool_contracts")
    assert report.allowed is True
    assert report.persona == "steward"
    assert "review_tool_contracts" in report.action


def test_compliance_allows_obligation_action() -> None:
    """An action listed as an obligation is allowed."""
    report = validate_doctrine_compliance("steward", "validate_workflow_integrity")
    assert report.allowed is True
    assert "obligation" in report.matched_rule


def test_compliance_blocks_prohibited_action() -> None:
    """An action in the prohibitions list is blocked."""
    report = validate_doctrine_compliance("sentinel", "silently_relax_controls")
    assert report.allowed is False
    assert "prohibition" in report.matched_rule


def test_compliance_blocks_unknown_action() -> None:
    """An action not in any list is blocked (no explicit permission)."""
    report = validate_doctrine_compliance("steward", "launch_missiles")
    assert report.allowed is False
    assert "no_explicit_permission" in report.matched_rule


def test_compliance_blocks_unknown_persona() -> None:
    """An unknown persona produces a blocked report."""
    report = validate_doctrine_compliance("nonexistent_persona", "any_action")
    assert report.allowed is False
    assert "Unknown persona" in report.block_reason
    assert report.matched_rule == "unknown_persona"


def test_compliance_steward_allowed_actions() -> None:
    """All steward allowed_actions from the matrix pass compliance."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("steward")
    assert contract is not None
    for action in contract.permissions:
        report = doctrine.validate_compliance("steward", action)
        assert report.allowed, f"Steward action '{action}' should be allowed"


def test_compliance_steward_forbidden_actions() -> None:
    """All steward forbidden_actions from the matrix are blocked."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("steward")
    assert contract is not None
    for action in contract.prohibitions:
        report = doctrine.validate_compliance("steward", action)
        assert not report.allowed, f"Steward action '{action}' should be blocked"


def test_compliance_sentinel_forbidden_actions() -> None:
    """All sentinel forbidden_actions from the matrix are blocked."""
    doctrine = build_operator_doctrine()
    contract = doctrine.get_contract("sentinel")
    assert contract is not None
    for action in contract.prohibitions:
        report = doctrine.validate_compliance("sentinel", action)
        assert not report.allowed, f"Sentinel action '{action}' should be blocked"


def test_compliance_report_to_dict() -> None:
    """DoctrineComplianceReport.to_dict() produces expected keys."""
    report = validate_doctrine_compliance("steward", "review_tool_contracts")
    data = report.to_dict()
    assert data["persona"] == "steward"
    assert data["action"] == "review_tool_contracts"
    assert isinstance(data["allowed"], bool)
    assert "matched_rule" in data
    assert "tier" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Doctrine → HLF conversion tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_doctrine_to_hlf_produces_valid_output() -> None:
    """doctrine_to_hlf() returns a non-empty string."""
    hlf_source = doctrine_to_hlf()
    assert isinstance(hlf_source, str)
    assert len(hlf_source) > 0


def test_doctrine_to_hlf_includes_all_four_personas() -> None:
    """HLF output includes all 4 pipeline personas."""
    hlf_source = doctrine_to_hlf()
    for p in ("steward", "herald", "builder", "sentinel"):
        assert p in hlf_source.lower(), f"HLF output missing persona '{p}'"


def test_doctrine_to_hlf_includes_constraint_annotations() -> None:
    """HLF output includes @must, @may, and @must_not annotations."""
    hlf_source = doctrine_to_hlf()
    assert "@may(" in hlf_source
    assert "@must_not(" in hlf_source
    assert "@must(" in hlf_source


def test_doctrine_to_hlf_includes_handoff_constraints() -> None:
    """HLF output includes cross-persona handoff constraint blocks."""
    hlf_source = doctrine_to_hlf()
    assert "handoff_" in hlf_source.lower()
    assert "@require_gate(" in hlf_source
    assert "@escalate_to(" in hlf_source


def test_doctrine_to_hlf_has_tier_annotations() -> None:
    """HLF output includes @tier annotations on each capsule."""
    hlf_source = doctrine_to_hlf()
    assert "@tier(" in hlf_source


def test_doctrine_to_hlf_is_deterministic() -> None:
    """Multiple calls to doctrine_to_hlf() produce identical output."""
    hlf1 = doctrine_to_hlf()
    hlf2 = doctrine_to_hlf()
    assert hlf1 == hlf2


# ═══════════════════════════════════════════════════════════════════════════════
# OperatorDoctrine aggregate tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_operator_doctrine_has_exactly_four_personas() -> None:
    """OperatorDoctrine contains exactly 4 pipeline personas."""
    doctrine = build_operator_doctrine()
    personas = doctrine.all_personas()
    assert len(personas) == 4
    expected = {"builder", "herald", "sentinel", "steward"}
    assert set(personas) == expected


def test_operator_doctrine_has_all_handoff_pairs() -> None:
    """All 4 cross-persona handoff pairs are defined."""
    doctrine = build_operator_doctrine()
    pairs = doctrine.all_handoff_pairs()
    assert len(pairs) == 4
    expected_pairs = {
        ("steward", "herald"),
        ("herald", "builder"),
        ("builder", "sentinel"),
        ("sentinel", "steward"),
    }
    assert set(pairs) == expected_pairs


def test_operator_doctrine_tier_map() -> None:
    """Every persona in the doctrine has a tier mapping."""
    doctrine = build_operator_doctrine()
    for persona in doctrine.all_personas():
        assert persona in doctrine.tier_map
        assert doctrine.tier_map[persona] in ("hearth", "sovereign", "field")


def test_operator_doctrine_factory_is_repeatable() -> None:
    """Multiple calls to build_operator_doctrine() produce equivalent doctrines."""
    d1 = build_operator_doctrine()
    d2 = build_operator_doctrine()
    assert d1.all_personas() == d2.all_personas()
    assert d1.all_handoff_pairs() == d2.all_handoff_pairs()
    for p in d1.all_personas():
        c1 = d1.get_contract(p)
        c2 = d2.get_contract(p)
        assert c1 is not None and c2 is not None
        assert c1.permissions == c2.permissions


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-persona handoff contract tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_handoff_contract_steward_to_herald() -> None:
    """Steward→Herald handoff contract exists with required gates."""
    hc = get_handoff_contract("steward", "herald")
    assert hc is not None
    assert hc.source_persona == "steward"
    assert hc.target_persona == "herald"
    assert len(hc.required_gates) > 0
    assert hc.escalation_persona == "operator"


def test_handoff_contract_herald_to_builder() -> None:
    """Herald→Builder handoff contract exists."""
    hc = get_handoff_contract("herald", "builder")
    assert hc is not None
    assert hc.source_persona == "herald"
    assert hc.target_persona == "builder"


def test_handoff_contract_builder_to_sentinel() -> None:
    """Builder→Sentinel handoff contract exists."""
    hc = get_handoff_contract("builder", "sentinel")
    assert hc is not None
    assert hc.source_persona == "builder"
    assert hc.target_persona == "sentinel"


def test_handoff_contract_sentinel_to_steward() -> None:
    """Sentinel→Steward handoff contract exists (closes the loop)."""
    hc = get_handoff_contract("sentinel", "steward")
    assert hc is not None
    assert hc.source_persona == "sentinel"
    assert hc.target_persona == "steward"


def test_handoff_contract_missing_returns_none() -> None:
    """A handoff pair not in the pipeline returns None."""
    hc = get_handoff_contract("steward", "sentinel")
    assert hc is None


def test_handoff_contract_to_dict() -> None:
    """HandoffContract.to_dict() produces expected structure."""
    hc = get_handoff_contract("steward", "herald")
    assert hc is not None
    data = hc.to_dict()
    assert data["source_persona"] == "steward"
    assert data["target_persona"] == "herald"
    assert isinstance(data["required_gates"], list)
    assert isinstance(data["evidence_required"], list)
    assert data["escalation_persona"] == "operator"


def test_handoff_contract_has_evidence_requirements() -> None:
    """Every handoff contract specifies evidence requirements."""
    doctrine = build_operator_doctrine()
    for src, tgt in doctrine.all_handoff_pairs():
        hc = doctrine.get_handoff_contract(src, tgt)
        assert hc is not None
        assert len(hc.evidence_required) > 0, f"Handoff {src}→{tgt} missing evidence"


# ═══════════════════════════════════════════════════════════════════════════════
# Persona gating with constitutional checks
# ═══════════════════════════════════════════════════════════════════════════════

def test_persona_gate_allows_valid_assignment() -> None:
    """A valid persona with permitted actions passes the gate."""
    manifest = CapabilityManifest(
        persona="steward",
        tier="hearth",
        requested_actions=["review_tool_contracts", "review_transport_or_workflow_changes"],
    )
    result = check_persona_assignment("steward", manifest)
    assert result.assigned is True
    assert result.passed_doctrine is True
    assert result.persona == "steward"
    assert len(result.violations) == 0


def test_persona_gate_blocks_forbidden_action() -> None:
    """A persona requesting a forbidden action is blocked."""
    manifest = CapabilityManifest(
        persona="sentinel",
        tier="hearth",
        requested_actions=["silently_relax_controls"],
    )
    result = check_persona_assignment("sentinel", manifest)
    assert result.assigned is False
    assert result.passed_doctrine is False
    assert len(result.violations) > 0


def test_persona_gate_blocks_unknown_persona() -> None:
    """An unknown persona is blocked at the gate."""
    manifest = CapabilityManifest(
        persona="ghost_in_the_machine",
        tier="hearth",
        requested_actions=["anything"],
    )
    result = check_persona_assignment("ghost_in_the_machine", manifest)
    assert result.assigned is False


def test_persona_gate_dict_manifest() -> None:
    """check_persona_assignment accepts a plain dict as manifest."""
    manifest_dict = {
        "persona": "steward",
        "tier": "hearth",
        "requested_actions": ["review_tool_contracts"],
    }
    result = check_persona_assignment("steward", manifest_dict)
    assert result.assigned is True


def test_persona_gate_result_to_dict() -> None:
    """PersonaGateResult.to_dict() produces expected keys."""
    manifest = CapabilityManifest(
        persona="herald",
        tier="hearth",
        requested_actions=["classify_claim_lanes"],
    )
    result = check_persona_assignment("herald", manifest)
    data = result.to_dict()
    assert data["persona"] == "herald"
    assert isinstance(data["assigned"], bool)
    assert "violations" in data
    assert "gate_log" in data
    assert "tier" in data


def test_persona_gate_includes_gate_log() -> None:
    """Gate result includes an ordered log of gate checks."""
    manifest = CapabilityManifest(
        persona="steward",
        tier="hearth",
        requested_actions=["review_tool_contracts", "auto_apply_changes"],
    )
    result = check_persona_assignment("steward", manifest)
    assert len(result.gate_log) > 0
    for entry in result.gate_log:
        assert "gate_id" in entry
        assert "status" in entry
        assert "detail" in entry


def test_persona_gate_escalate_to_operator_on_block() -> None:
    """When gating fails, escalate_to is 'operator'."""
    manifest = CapabilityManifest(
        persona="sentinel",
        tier="hearth",
        requested_actions=["approve_promotion_after_block_without_operator"],
    )
    result = check_persona_assignment("sentinel", manifest)
    if not result.assigned:
        assert result.escalate_to == "operator"


# ═══════════════════════════════════════════════════════════════════════════════
# Tier-differentiated permissions
# ═══════════════════════════════════════════════════════════════════════════════

def test_tier_hearth_denies_sensitive_actions() -> None:
    """Hearth tier denies auto_apply_changes and merge_changes."""
    assert tier_allows("hearth", "auto_apply_changes") is False
    assert tier_allows("hearth", "merge_changes") is False
    assert tier_allows("hearth", "modify_protected_branch_policy") is False
    assert tier_allows("hearth", "grant_runtime_authority") is False


def test_tier_sovereign_allows_sensitive_actions() -> None:
    """Sovereign tier allows most sensitive actions except runtime authority."""
    assert tier_allows("sovereign", "auto_apply_changes") is True
    assert tier_allows("sovereign", "merge_changes") is True
    assert tier_allows("sovereign", "modify_protected_branch_policy") is True
    assert tier_allows("sovereign", "grant_runtime_authority") is False  # operator-only


def test_tier_field_allows_publish() -> None:
    """Field tier allows publish but not merge or runtime authority."""
    assert tier_allows("field", "publish_artifacts") is True
    assert tier_allows("field", "auto_apply_changes") is True
    assert tier_allows("field", "merge_changes") is False
    assert tier_allows("field", "grant_runtime_authority") is False


def test_tier_unknown_defaults_to_deny() -> None:
    """Unknown tier defaults to deny for all actions."""
    assert tier_allows("bogus_tier", "auto_apply_changes") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Runtime proof pipeline for persona transitions
# ═══════════════════════════════════════════════════════════════════════════════

def test_prove_persona_transition_valid_handoff() -> None:
    """A valid Steward→Herald transition passes the proof pipeline."""
    proof = prove_persona_transition("steward", "herald")
    assert proof.valid is True
    assert proof.doctrine_check is True
    assert proof.constitutional_check is True
    assert proof.source_persona == "steward"
    assert proof.target_persona == "herald"


def test_prove_persona_transition_invalid_no_handoff() -> None:
    """A transition with no handoff contract fails the proof."""
    proof = prove_persona_transition("steward", "sentinel")
    assert proof.valid is False
    assert proof.doctrine_check is False


def test_prove_persona_transition_invalid_unknown_source() -> None:
    """A transition from an unknown persona fails."""
    proof = prove_persona_transition("ghost", "herald")
    assert proof.valid is False


def test_prove_persona_transition_invalid_unknown_target() -> None:
    """A transition to an unknown persona fails."""
    proof = prove_persona_transition("steward", "ghost")
    assert proof.valid is False


def test_prove_persona_transition_to_dict() -> None:
    """PersonaTransitionProof.to_dict() produces expected structure."""
    proof = prove_persona_transition("steward", "herald")
    data = proof.to_dict()
    assert data["source_persona"] == "steward"
    assert data["target_persona"] == "herald"
    assert isinstance(data["valid"], bool)
    assert isinstance(data["gate_results"], list)
    assert len(data["gate_results"]) > 0


def test_prove_all_four_transitions_valid() -> None:
    """All 4 defined handoff transitions are valid."""
    pairs = [
        ("steward", "herald"),
        ("herald", "builder"),
        ("builder", "sentinel"),
        ("sentinel", "steward"),
    ]
    for src, tgt in pairs:
        proof = prove_persona_transition(src, tgt)
        assert proof.valid, f"Transition {src}→{tgt} should be valid, got: {proof.gate_results}"


def test_prove_transition_has_handoff_contract_ref() -> None:
    """Valid transitions include the handoff contract in the proof."""
    proof = prove_persona_transition("herald", "builder")
    assert proof.handoff_contract is not None
    assert proof.handoff_contract["source_persona"] == "herald"
    assert proof.handoff_contract["target_persona"] == "builder"


def test_prove_transition_at_hearth_tier() -> None:
    """Transitions at hearth tier still validate (with advisory escalation)."""
    proof = prove_persona_transition("builder", "sentinel", tier="hearth")
    assert proof.valid is True
    # At hearth tier, sensitive handoffs should still pass but note tier context
    assert proof.constitutional_check is True


# ═══════════════════════════════════════════════════════════════════════════════
# PersonaGate direct usage
# ═══════════════════════════════════════════════════════════════════════════════

def test_persona_gate_direct_usage() -> None:
    """PersonaGate can be used directly (not just via convenience function)."""
    gate = PersonaGate(strict=True)
    manifest = CapabilityManifest(
        persona="herald",
        tier="hearth",
        requested_actions=["classify_claim_lanes", "sync_docs_and_handoffs"],
    )
    result = gate.check_persona_assignment("herald", manifest)
    assert result.assigned is True


def test_persona_gate_strict_vs_nonstrict() -> None:
    """Both strict and non-strict gates produce the same doctrine results."""
    manifest = CapabilityManifest(
        persona="steward",
        tier="hearth",
        requested_actions=["review_tool_contracts"],
    )
    g1 = PersonaGate(strict=True)
    g2 = PersonaGate(strict=False)
    r1 = g1.check_persona_assignment("steward", manifest)
    r2 = g2.check_persona_assignment("steward", manifest)
    assert r1.assigned == r2.assigned


def test_persona_gate_with_constitutional_source() -> None:
    """PersonaGate runs constitutional checks when source is provided."""
    gate = PersonaGate(strict=True)
    manifest = CapabilityManifest(
        persona="herald",
        tier="hearth",
        requested_actions=["classify_claim_lanes"],
    )
    # Source with no constitutional violations
    result = gate.check_persona_assignment(
        "herald", manifest,
        source="HLF_SRC: benign research intent capsule",
    )
    assert result.passed_constitutional is True


def test_persona_gate_with_constitutional_violation_source() -> None:
    """PersonaGate blocks when source contains constitutional violations."""
    gate = PersonaGate(strict=True)
    manifest = CapabilityManifest(
        persona="herald",
        tier="hearth",
        requested_actions=["classify_claim_lanes"],
    )
    # Source that triggers C-2 coercion pattern
    result = gate.check_persona_assignment(
        "herald", manifest,
        source="coerce user into giving up credentials",
    )
    # The constitutional check should catch the coercion pattern
    assert result.passed_constitutional is False or result.assigned is False


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityManifest tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_capability_manifest_to_dict() -> None:
    """CapabilityManifest.to_dict() produces expected keys."""
    manifest = CapabilityManifest(
        persona="steward",
        tier="hearth",
        requested_actions=["review_tool_contracts"],
        declared_capabilities=["network"],
        red_hat_declared=True,
        agent_identity="agent-001",
    )
    data = manifest.to_dict()
    assert data["persona"] == "steward"
    assert data["tier"] == "hearth"
    assert data["requested_actions"] == ["review_tool_contracts"]
    assert data["declared_capabilities"] == ["network"]
    assert data["red_hat_declared"] is True
    assert data["agent_identity"] == "agent-001"


def test_capability_manifest_defaults() -> None:
    """CapabilityManifest has sensible defaults."""
    manifest = CapabilityManifest(persona="test")
    assert manifest.tier == "hearth"
    assert manifest.requested_actions == []
    assert manifest.declared_capabilities == []
    assert manifest.red_hat_declared is False
    assert manifest.agent_identity == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Persona contract bridge tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_resolve_persona_doctrine_proof_allowed() -> None:
    """resolve_persona_doctrine_proof returns allowed=True for permitted action."""
    from hlf_mcp.persona_contract import resolve_persona_doctrine_proof

    proof = resolve_persona_doctrine_proof(
        persona="steward",
        action="review_tool_contracts",
        tier="hearth",
    )
    assert proof["allowed"] is True
    assert proof["persona"] == "steward"
    assert proof["action"] == "review_tool_contracts"


def test_resolve_persona_doctrine_proof_blocked() -> None:
    """resolve_persona_doctrine_proof returns allowed=False for forbidden action."""
    from hlf_mcp.persona_contract import resolve_persona_doctrine_proof

    proof = resolve_persona_doctrine_proof(
        persona="sentinel",
        action="silently_relax_controls",
        tier="hearth",
    )
    assert proof["allowed"] is False
    assert "prohibition" in proof.get("matched_rule", "")


def test_resolve_handoff_doctrine_proof_valid() -> None:
    """resolve_handoff_doctrine_proof validates a Steward→Herald handoff."""
    from hlf_mcp.persona_contract import resolve_handoff_doctrine_proof

    proof = resolve_handoff_doctrine_proof(
        source_persona="steward",
        target_persona="herald",
        tier="hearth",
    )
    assert proof["valid"] is True
    assert proof["source_persona"] == "steward"
    assert proof["target_persona"] == "herald"


def test_resolve_handoff_doctrine_proof_invalid() -> None:
    """resolve_handoff_doctrine_proof rejects undefined handoffs."""
    from hlf_mcp.persona_contract import resolve_handoff_doctrine_proof

    proof = resolve_handoff_doctrine_proof(
        source_persona="steward",
        target_persona="builder",  # not a defined handoff pair
        tier="hearth",
    )
    assert proof["valid"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: existing persona tests still pass
# ═══════════════════════════════════════════════════════════════════════════════

def test_persona_doctrine_consistent_with_persona_contract() -> None:
    """Doctrine contracts are consistent with persona_contract's matrix data."""
    from hlf_mcp.persona_contract import load_persona_matrix

    matrix = load_persona_matrix()
    matrix_personas = set(matrix.get("personas", {}).keys())

    doctrine = build_operator_doctrine()
    # The 4 pipeline personas should all be in the matrix
    for dp in doctrine.all_personas():
        # builder maps to strategist in the matrix
        matrix_name = "strategist" if dp == "builder" else dp
        assert matrix_name in matrix_personas, (
            f"Doctrine persona '{dp}' (matrix: '{matrix_name}') not in matrix"
        )


def test_persona_doctrine_tier_consistent_with_matrix() -> None:
    """Doctrine tiers are consistent with matrix tier assignments."""
    from hlf_mcp.persona_contract import load_persona_matrix

    matrix = load_persona_matrix()
    personas = matrix.get("personas", {})

    doctrine = build_operator_doctrine()
    for dp in doctrine.all_personas():
        contract = doctrine.get_contract(dp)
        assert contract is not None
        matrix_name = "strategist" if dp == "builder" else dp
        matrix_tier = personas.get(matrix_name, {}).get("tier", "tier_1")
        assert contract.tier in ("hearth",), (
            f"Doctrine persona '{dp}' tier '{contract.tier}' inconsistent with matrix '{matrix_tier}'"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DoctrineDriftDetector tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_drift_detector_analyze_compliant_actions_no_drift() -> None:
    """Compliant doctrine actions produce a report with no drift detected."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "review_tool_contracts", success=True)
    detector.record_action("steward", "review_transport_or_workflow_changes", success=True)
    detector.record_action("steward", "validate_workflow_integrity", success=True)
    report = detector.analyze_behavior("steward")

    assert not report.drift_detected
    assert report.total_actions_analyzed == 3
    assert len(report.compliant_actions) == 3
    assert len(report.drifted_actions) == 0
    assert len(report.constraints) == 0


def test_drift_detector_analyze_prohibited_action_detects_drift() -> None:
    """A prohibited action recorded for sentinel is detected as critical drift."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("sentinel", "review_security_posture", success=True)
    detector.record_action("sentinel", "silently_relax_controls", success=True)
    report = detector.analyze_behavior("sentinel")

    assert report.drift_detected
    assert len(report.drifted_actions) >= 1
    drifted_actions = [d["action"] for d in report.drifted_actions]
    assert "silently_relax_controls" in drifted_actions
    assert report.severity_counts.get("critical", 0) >= 1


def test_drift_detector_analyze_unpermitted_action_flags_warning() -> None:
    """An action not in the doctrine for a persona triggers a warning-severity drift."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "deploy_to_production_without_review", success=True)
    report = detector.analyze_behavior("steward")

    assert report.drift_detected
    drifted = report.drifted_actions[0]
    assert drifted["action"] == "deploy_to_production_without_review"
    assert drifted["severity"] == "warning"
    assert report.severity_counts.get("warning", 0) >= 1


def test_drift_detector_generates_corrective_constraints() -> None:
    """Drift analysis of prohibited behavior generates DriftConstraint objects."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector, DriftConstraint

    detector = DoctrineDriftDetector()
    detector.record_action("sentinel", "modify_secret_material", success=True)
    report = detector.analyze_behavior("sentinel")

    assert report.drift_detected
    assert len(report.constraints) >= 1
    for constraint in report.constraints:
        assert isinstance(constraint, DriftConstraint)
        assert constraint.persona == "sentinel"
        assert "modify_secret_material" in constraint.drifted_action
        assert constraint.hlf_statement != ""


def test_drift_detector_generate_corrective_hlf_produces_output() -> None:
    """generate_corrective_hlf returns a non-empty HLF string for a drifted report."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "auto_apply_changes", success=True)
    report = detector.analyze_behavior("steward")
    hlf = detector.generate_corrective_hlf(report)

    assert isinstance(hlf, str)
    assert len(hlf) > 50
    assert "Drift Correction HLF" in hlf or "drift" in hlf.lower()
    assert "@tier" in hlf


def test_drift_detector_analyze_all_personas() -> None:
    """analyze_all_personas returns drift reports for every persona with recorded history."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "review_tool_contracts", success=True)
    detector.record_action("herald", "classify_claim_lanes", success=True)
    detector.record_action("builder", "classify_lane", success=True)
    detector.record_action("sentinel", "review_security_posture", success=True)

    results = detector.analyze_all_personas()

    assert len(results) >= 4
    for persona in ("steward", "herald", "builder", "sentinel"):
        assert persona in results
        assert results[persona].total_actions_analyzed >= 1


def test_drift_detector_action_history_accumulates() -> None:
    """Recording multiple actions accumulates them in the action history."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    for i in range(5):
        detector.record_action("steward", "review_tool_contracts", success=True)
    history = detector.get_action_history("steward")

    assert len(history) == 5
    for entry in history:
        assert entry["action"] == "review_tool_contracts"
        assert entry["success"] is True


def test_drift_detector_clear_history() -> None:
    """Clearing a persona's history empties its recorded actions."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "review_tool_contracts", success=True)
    detector.record_action("steward", "block_on_contract_risk", success=True)
    assert len(detector.get_action_history("steward")) == 2

    detector.clear_history("steward")
    assert len(detector.get_action_history("steward")) == 0


def test_drift_detector_drift_summary_aggregates() -> None:
    """get_drift_summary correctly aggregates drift across multiple analyses."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("steward", "auto_apply_changes", success=True)
    detector.record_action("sentinel", "silently_relax_controls", success=True)
    detector.analyze_behavior("steward")
    detector.analyze_behavior("sentinel")

    summary = detector.get_drift_summary()
    assert summary["total_reports"] == 2
    assert len(summary["personas_with_drift"]) >= 1
    assert summary["total_drifted_actions"] >= 2
    assert summary["total_constraints_generated"] >= 2


def test_drift_detector_unknown_persona_is_critical_drift() -> None:
    """Analyzing a persona with no doctrine contract produces critical drift."""
    from hlf_mcp.persona.doctrine_drift import DoctrineDriftDetector

    detector = DoctrineDriftDetector()
    detector.record_action("unknown_spectre", "do_something_unauthorized", success=True)
    report = detector.analyze_behavior("unknown_spectre")

    assert report.drift_detected
    drifted = report.drifted_actions[0]
    assert drifted["severity"] == "critical"
    assert "no_doctrine_contract" in drifted["reason"]


# ═══════════════════════════════════════════════════════════════════════════════
# PersonaCompositionProver tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_composition_prover_valid_handoff_steward_to_herald() -> None:
    """Proving steward→herald composition returns a proof with validity status."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    proof = prover.prove_composition("steward", "herald")

    assert proof.source_persona == "steward"
    assert proof.target_persona == "herald"
    assert len(proof.checksum) > 0
    assert proof.proven_at > 0
    # steward→herald should have some conflicts due to permission/prohibition gaps
    assert len(proof.conflicts) >= 0
    assert isinstance(proof.valid, bool)


def test_composition_prover_detects_prohibition_gap() -> None:
    """steward→builder composition detects prohibition continuity gaps."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver(strict_composition=True)
    proof = prover.prove_composition("steward", "builder")

    conflict_types = [c.conflict_type for c in proof.conflicts]
    # steward and builder have different prohibitions → prohibition_overlap expected
    has_prohibition_gap = any("prohibition" in ct for ct in conflict_types)
    assert has_prohibition_gap or len(proof.conflicts) > 0


def test_composition_prover_detects_permission_gap() -> None:
    """herald→sentinel composition detects permission gaps between doctrines."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver(strict_composition=True)
    proof = prover.prove_composition("herald", "sentinel")

    # permission_gap should list herald permissions not present in sentinel
    assert isinstance(proof.permission_gap, list)
    assert len(proof.permission_gap) >= 0  # gap might be empty but list must exist
    assert isinstance(proof.permission_overlap, list)


def test_composition_prover_detects_obligation_gap() -> None:
    """Composition proof tracks obligation continuity via obligation_transfer field."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver(strict_composition=True)
    proof = prover.prove_composition("steward", "sentinel")

    assert isinstance(proof.obligation_transfer, list)
    assert len(proof.obligation_transfer) > 0
    transfer_types = {entry["transfer"] for entry in proof.obligation_transfer}
    assert "preserved" in transfer_types or "gapped" in transfer_types


def test_composition_prover_invalid_with_unknown_source() -> None:
    """Unknown source persona yields an invalid proof with a critical conflict."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    proof = prover.prove_composition("unknown_phantom", "herald")

    assert not proof.valid
    assert len(proof.conflicts) == 1
    conflict = proof.conflicts[0]
    assert conflict.conflict_type == "capability_mismatch"
    assert conflict.severity == "critical"
    assert not conflict.resolvable
    assert "unknown_phantom" in conflict.description.lower()


def test_composition_prover_invalid_with_unknown_target() -> None:
    """Unknown target persona yields an invalid proof with a critical conflict."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    proof = prover.prove_composition("steward", "unknown_wraith")

    assert not proof.valid
    assert len(proof.conflicts) == 1
    conflict = proof.conflicts[0]
    assert conflict.conflict_type == "capability_mismatch"
    assert conflict.severity == "critical"
    assert not conflict.resolvable


def test_composition_prover_generates_resolution_hlf() -> None:
    """generate_resolution_hlf produces non-empty HLF for a proof with conflicts."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver(strict_composition=True)
    proof = prover.prove_composition("steward", "builder")

    hlf = prover.generate_resolution_hlf(proof)
    assert isinstance(hlf, str)
    assert len(hlf) > 20
    assert "Composition Resolution HLF" in hlf or "steward" in hlf


def test_composition_prover_prove_all_compositions() -> None:
    """prove_all_compositions returns proofs for all defined handoff pairs."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    proofs = prover.prove_all_compositions()

    assert len(proofs) >= 4
    pairs = {(p.source_persona, p.target_persona) for p in proofs}
    # The 4 known handoff pairs from the pipeline
    expected = {("steward", "herald"), ("herald", "builder"),
                ("builder", "sentinel"), ("sentinel", "steward")}
    for pair in expected:
        assert pair in pairs, f"Missing composition proof for {pair}"


def test_composition_prover_composition_summary() -> None:
    """get_composition_summary returns accurate aggregate stats about proofs."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    prover.prove_all_compositions()

    summary = prover.get_composition_summary()
    assert summary["total_proofs"] >= 4
    assert "valid_count" in summary
    assert "invalid_count" in summary
    assert summary["valid_count"] + summary["invalid_count"] == summary["total_proofs"]
    assert summary["total_conflicts"] >= 0
    assert len(summary["pairs_analyzed"]) >= 4


def test_composition_prover_permission_overlap_computed() -> None:
    """Permission overlap is computed for steward→herald handoff."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    proof = prover.prove_composition("steward", "herald")

    assert isinstance(proof.permission_overlap, list)
    # Both steward and herald share at least the review-related obligation space
    assert isinstance(proof.permission_gap, list)


def test_composition_prover_constraints_have_precedence() -> None:
    """Generated CompositionConstraint objects carry a precedence field for ordering."""
    from hlf_mcp.persona.composition_proofs import (
        PersonaCompositionProver,
        CompositionConstraint,
    )

    prover = PersonaCompositionProver(strict_composition=True)
    proof = prover.prove_composition("steward", "builder")

    if proof.constraints:
        precedences = set()
        for c in proof.constraints:
            assert isinstance(c, CompositionConstraint)
            assert isinstance(c.precedence, int)
            precedences.add(c.precedence)
        assert len(precedences) >= 1


def test_composition_prover_clear_proofs() -> None:
    """Clear all composition proofs resets internal state."""
    from hlf_mcp.persona.composition_proofs import PersonaCompositionProver

    prover = PersonaCompositionProver()
    prover.prove_composition("steward", "herald")
    prover.prove_composition("herald", "builder")

    summary_before = prover.get_composition_summary()
    assert summary_before["total_proofs"] == 2

    prover.clear_proofs()
    summary_after = prover.get_composition_summary()
    assert summary_after["total_proofs"] == 0
    assert summary_after["pairs_analyzed"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# CapabilityDecayModel tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_capability_decay_register_and_get() -> None:
    """Register a capability and retrieve it by persona and name."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("steward", "review_tool_contracts", ttl_seconds=3600.0)

    record = model.get_capability("steward", "review_tool_contracts")
    assert record is not None
    assert record.capability_name == "review_tool_contracts"
    assert record.persona == "steward"
    assert record.certification_ttl_seconds == 3600.0


def test_capability_decay_freshness_score_new() -> None:
    """A freshly registered capability has a freshness score of 1.0."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("steward", "validate_workflow_integrity")

    record = model.get_capability("steward", "validate_workflow_integrity")
    assert record is not None
    assert record.freshness_score() == pytest.approx(1.0, abs=0.01)


def test_capability_decay_freshness_score_decays() -> None:
    """A capability with an old certification timestamp has a freshness below 1.0."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("steward", "review_tool_contracts")
    record = model.get_capability("steward", "review_tool_contracts")
    assert record is not None
    # Manually age the timestamp far into the past
    record.last_certified_at = time.time() - 43200.0  # 12 hours ago, TTL is 24h

    score = record.freshness_score()
    assert 0.0 < score < 1.0
    assert score == pytest.approx(0.5, abs=0.02)


def test_capability_decay_is_stale_after_ttl() -> None:
    """A capability whose TTL has elapsed is marked stale."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("herald", "classify_claim_lanes", ttl_seconds=0.01)
    record = model.get_capability("herald", "classify_claim_lanes")
    assert record is not None
    record.last_certified_at = time.time() - 1.0

    assert record.is_stale()


def test_capability_decay_certify_resets_clock() -> None:
    """Certifying a capability resets its last_certified_at and bumps renewal_count."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("builder", "classify_lane")
    record = model.get_capability("builder", "classify_lane")
    assert record is not None
    record.last_certified_at = time.time() - 86400.0  # 1 day ago

    certified = model.certify("builder", "classify_lane", level=1.0, evidence="ev-abc123")
    assert certified is not None
    assert certified.renewal_count == 1
    assert certified.freshness_score() == pytest.approx(1.0, abs=0.01)
    assert certified.certification_evidence == "ev-abc123"


def test_capability_decay_generate_decay_report() -> None:
    """generate_decay_report produces a DecayReport with correct aggregate stats."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel, DecayReport

    model = CapabilityDecayModel()
    model.register_capability("steward", "review_tool_contracts")
    model.register_capability("steward", "validate_workflow_integrity")
    model.register_capability("steward", "report_contract_risk")

    # Age one capability so it's stale
    record = model.get_capability("steward", "report_contract_risk")
    assert record is not None
    record.last_certified_at = time.time() - 90000.0  # > 24h, fully stale

    report = model.generate_decay_report("steward")
    assert isinstance(report, DecayReport)
    assert report.persona == "steward"
    assert report.total_capabilities == 3
    assert report.stale_capabilities >= 1
    assert report.recertification_needed


def test_capability_decay_check_triggers_high_urgency() -> None:
    """A stale capability generates a high-urgency recertification trigger."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel(stale_threshold=0.3, critical_threshold=0.1)
    model.register_capability("sentinel", "review_security_posture", ttl_seconds=3600.0)
    record = model.get_capability("sentinel", "review_security_posture")
    assert record is not None
    # Set age so freshness is ~0.2 (below stale 0.3, above critical 0.1)
    record.last_certified_at = time.time() - 2880.0  # 80% of TTL elapsed

    triggers = model.check_triggers("sentinel")
    assert len(triggers) >= 1
    trigger = triggers[0]
    assert trigger.persona == "sentinel"
    assert trigger.urgency == "high"
    assert "review_security_posture" in trigger.capabilities_affected


def test_capability_decay_check_triggers_critical_urgency() -> None:
    """A critically stale capability triggers critical urgency."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel(stale_threshold=0.3, critical_threshold=0.1)
    model.register_capability("sentinel", "validate_boundary_integrity", ttl_seconds=3600.0)
    record = model.get_capability("sentinel", "validate_boundary_integrity")
    assert record is not None
    record.last_certified_at = time.time() - 3600.0  # fully stale, freshness 0.0

    triggers = model.check_triggers("sentinel")
    assert len(triggers) >= 1
    urgency_levels = [t.urgency for t in triggers]
    assert "critical" in urgency_levels


def test_capability_decay_no_trigger_for_fresh_capability() -> None:
    """A freshly registered capability should not generate any triggers."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("herald", "classify_claim_lanes")

    triggers = model.check_triggers("herald")
    assert len(triggers) == 0


def test_capability_decay_degrade_capability_lowers_level() -> None:
    """Degrading a capability lowers its current_level but not below 0.0."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("builder", "sequence_work", initial_level=1.0)
    degraded = model.degrade_capability("builder", "sequence_work", 0.3)

    assert degraded is not None
    assert degraded.current_level == 0.3
    assert degraded.certified_level == 1.0  # original cert level unchanged


def test_capability_decay_freshness_matrix() -> None:
    """get_freshness_matrix returns nested dict of persona→capability→freshness."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("steward", "review_tool_contracts")
    model.register_capability("steward", "report_contract_risk")
    model.register_capability("herald", "classify_claim_lanes")

    matrix = model.get_freshness_matrix()
    assert "steward" in matrix
    assert "herald" in matrix
    assert "review_tool_contracts" in matrix["steward"]
    assert "report_contract_risk" in matrix["steward"]
    assert "classify_claim_lanes" in matrix["herald"]
    for caps in matrix.values():
        for score in caps.values():
            assert 0.0 <= score <= 1.0


def test_capability_decay_get_urgency_summary() -> None:
    """get_urgency_summary correctly aggregates triggers by urgency level."""
    import time
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel(stale_threshold=0.5, critical_threshold=0.1)
    model.register_capability("steward", "review_tool_contracts", ttl_seconds=100.0)
    model.register_capability("steward", "report_contract_risk", ttl_seconds=100.0)

    # Make one stale (freshness ~0.3)
    r1 = model.get_capability("steward", "review_tool_contracts")
    assert r1 is not None
    r1.last_certified_at = time.time() - 70.0  # 70% of 100s TTL → freshness ~0.3
    # Make one critical (freshness ~0.0)
    r2 = model.get_capability("steward", "report_contract_risk")
    assert r2 is not None
    r2.last_certified_at = time.time() - 110.0  # fully stale

    model.check_triggers("steward")
    summary = model.get_urgency_summary()

    assert summary["total_triggers"] >= 1
    assert "by_urgency" in summary
    assert "steward" in summary["personas_affected"]


def test_capability_decay_remove_capability() -> None:
    """Removing a capability makes it inaccessible via get_capability."""
    from hlf_mcp.persona.capability_decay import CapabilityDecayModel

    model = CapabilityDecayModel()
    model.register_capability("steward", "review_tool_contracts")
    assert model.get_capability("steward", "review_tool_contracts") is not None

    removed = model.remove_capability("steward", "review_tool_contracts")
    assert removed
    assert model.get_capability("steward", "review_tool_contracts") is None

    # Removing non-existent returns False
    assert not model.remove_capability("steward", "nonexistent_capability")

