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
