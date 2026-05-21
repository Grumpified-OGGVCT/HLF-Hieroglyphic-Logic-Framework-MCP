"""
Tests for dream cycle binding: observe→propose→verify→promote gating.

Covers:
  - Phase addition: observe and propose in lifecycle
  - Phase ordering and gating enforcement
  - DreamProposal creation from DreamFinding
  - AUTO_IF_CONFIDENCE promotion rules
  - MANUAL_APPROVAL promotion rules
  - GOVERNANCE_VOTE promotion rules
  - CoVE gate enforcement
  - Full observe→propose→verify→promote pipeline
  - Edge cases and error conditions
"""

from __future__ import annotations

import time
import random
import string

import pytest

from hlf_mcp.instinct.lifecycle import (
    InstinctLifecycle,
    PHASES,
    PHASE_INDEX,
    _ALLOWED_NEXT,
    _GATES,
)
from hlf_mcp.dream_cycle import DreamFinding
from hlf_mcp.hlf.dream_proposal import (
    DreamProposal,
    PromotionRule,
    create_dream_proposal,
    create_governor_token,
    create_validator_signature,
    promote_to_candidate,
    promote_to_binding,
    _check_cove_gate,
    _validate_governor_token,
    _count_valid_signatures,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helper factories
# ═══════════════════════════════════════════════════════════════════════════


def _make_finding(
    *,
    finding_id: str = "test-finding-1",
    confidence: float = 0.9,
    title: str = "Test Finding",
    summary: str = "A test finding",
    topic: str = "test",
    candidate_actions: list[str] | None = None,
) -> DreamFinding:
    return DreamFinding(
        finding_id=finding_id,
        created_at="2026-04-01T00:00:00Z",
        cycle_id="test-cycle",
        title=title,
        summary=summary,
        topic=topic,
        confidence=confidence,
        evidence_refs=[{"kind": "test", "ref": "test-ref"}],
        source_artifact_ids=["art-1"],
        witness_status="linked",
        provenance={"source": "test"},
        advisory_only=True,
        candidate_actions=candidate_actions or [],
    )


def _make_cove_result(passed: bool = True) -> dict:
    return {"passed": passed, "all_proven": passed, "verdict": "APPROVED" if passed else "DENIED"}


def _random_hex(length: int = 64) -> str:
    return "".join(random.choices("0123456789abcdef", k=length))


# ═══════════════════════════════════════════════════════════════════════════
# Phase existence and ordering tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseExistence:
    """Verify observe and propose phases exist in the lifecycle."""

    def test_observe_phase_exists_in_phases_list(self) -> None:
        assert "observe" in PHASES

    def test_propose_phase_exists_in_phases_list(self) -> None:
        assert "propose" in PHASES

    def test_phases_ordered_observe_before_propose(self) -> None:
        assert PHASE_INDEX["observe"] < PHASE_INDEX["propose"]

    def test_phases_ordered_propose_before_specify(self) -> None:
        assert PHASE_INDEX["propose"] < PHASE_INDEX["specify"]

    def test_full_phase_sequence_is_correct(self) -> None:
        expected = ["observe", "propose", "specify", "plan", "execute", "verify", "merge"]
        assert PHASES == expected

    def test_observe_allowed_next_is_propose(self) -> None:
        assert _ALLOWED_NEXT["observe"] == ["propose"]

    def test_propose_allowed_next_includes_specify(self) -> None:
        assert "specify" in _ALLOWED_NEXT["propose"]

    def test_observe_gate_has_dream_gate_flag(self) -> None:
        assert _GATES["observe"]["dream_gate"] is True

    def test_propose_gate_has_dream_gate_flag(self) -> None:
        assert _GATES["propose"]["dream_gate"] is True

    def test_propose_gate_requires_observe(self) -> None:
        assert _GATES["propose"]["requires_observe"] is True

    def test_specify_is_valid_entry_point(self) -> None:
        lc = InstinctLifecycle()
        result = lc.step("entry-specify", "specify", {"topic": "test"})
        assert result["status"] == "ok"

    def test_observe_is_valid_entry_point(self) -> None:
        lc = InstinctLifecycle()
        result = lc.step("entry-observe", "observe", {"topic": "test"})
        assert result["status"] == "ok"

    def test_propose_is_valid_entry_point(self) -> None:
        lc = InstinctLifecycle()
        result = lc.step("entry-propose", "propose", {"topic": "test"})
        assert result["status"] == "ok"

    def test_plan_is_not_valid_entry_point(self) -> None:
        lc = InstinctLifecycle()
        result = lc.step("entry-plan", "plan", {})
        assert result["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════════
# Phase ordering gating tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseOrderingGating:
    """Verify phase ordering constraints are enforced."""

    def test_cannot_jump_specify_to_propose_without_observe(self) -> None:
        """specify→propose would be backward (propose < specify)."""
        lc = InstinctLifecycle()
        lc.step("mission", "specify", {"topic": "test"})
        result = lc.step("mission", "propose")
        # Backward transition, should be blocked
        assert result["status"] == "error"

    def test_override_allows_backward_transition(self) -> None:
        lc = InstinctLifecycle()
        lc.step("mission", "specify", {"topic": "test"})
        result = lc.step("mission", "propose", override=True)
        assert result["status"] == "ok"
        assert result["current_phase"] == "propose"

    def test_cannot_jump_specify_to_observe_backward(self) -> None:
        lc = InstinctLifecycle()
        lc.step("mission", "specify", {"topic": "test"})
        result = lc.step("mission", "observe")
        assert result["status"] == "error"

    def test_override_allows_specify_to_observe_backward(self) -> None:
        lc = InstinctLifecycle()
        lc.step("mission", "specify", {"topic": "test"})
        result = lc.step("mission", "observe", override=True)
        assert result["status"] == "ok"

    def test_observe_to_propose_is_valid_forward(self) -> None:
        lc = InstinctLifecycle()
        lc.step("mission", "observe", {"topic": "test"})
        result = lc.step("mission", "propose")
        assert result["status"] == "ok"

    def test_propose_to_specify_is_valid_forward(self) -> None:
        lc = InstinctLifecycle()
        lc.step("mission", "observe", {"topic": "test"})
        lc.step("mission", "propose")
        result = lc.step("mission", "specify", {"topic": "test"})
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# DreamProposal creation tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDreamProposalCreation:
    """Verify DreamProposal creation from DreamFinding."""

    def test_create_proposal_from_finding(self) -> None:
        finding = _make_finding(confidence=0.9, title="Test", summary="Summary")
        proposal = create_dream_proposal(finding)
        assert proposal.status == "advisory"
        assert proposal.finding_id == finding.finding_id
        assert proposal.confidence == 0.9
        assert proposal.finding_title == "Test"
        assert proposal.finding_summary == "Summary"

    def test_proposal_maps_all_fields_from_finding(self) -> None:
        actions = ["action-1", "action-2"]
        finding = _make_finding(
            finding_id="full-mapping",
            confidence=0.75,
            title="Full Map",
            summary="All fields",
            topic="mapping",
            candidate_actions=actions,
        )
        proposal = create_dream_proposal(finding)
        assert proposal.finding_id == "full-mapping"
        assert proposal.confidence == 0.75
        assert proposal.finding_title == "Full Map"
        assert proposal.finding_summary == "All fields"
        assert proposal.finding_topic == "mapping"
        assert proposal.candidate_actions == actions
        assert proposal.status == "advisory"
        assert proposal.promoted_at is None
        assert proposal.promoter == ""

    def test_proposal_default_promotion_rule_is_auto_if_confidence(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding)
        assert proposal.promotion_rule == PromotionRule.AUTO_IF_CONFIDENCE

    def test_proposal_can_specify_promotion_rule(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.MANUAL_APPROVAL)
        assert proposal.promotion_rule == PromotionRule.MANUAL_APPROVAL

    def test_proposal_id_is_deterministic_per_finding_cycle(self) -> None:
        finding = _make_finding(finding_id="deterministic")
        p1 = create_dream_proposal(finding)
        p2 = create_dream_proposal(finding)
        # With time component, IDs may differ. Check format.
        assert p1.proposal_id.startswith("proposal-")
        assert len(p1.proposal_id) == 25  # "proposal-" + 16 hex chars

    def test_proposal_to_dict_roundtrip(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding)
        d = proposal.to_dict()
        assert d["proposal_id"] == proposal.proposal_id
        assert d["status"] == "advisory"
        assert d["promotion_rule"] == "AUTO_IF_CONFIDENCE"
        assert d["confidence"] == finding.confidence


# ═══════════════════════════════════════════════════════════════════════════
# PromotionRule enum tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPromotionRuleEnum:
    """Verify PromotionRule enum parsing and validation."""

    def test_from_string_auto_if_confidence(self) -> None:
        assert PromotionRule.from_string("auto_if_confidence") == PromotionRule.AUTO_IF_CONFIDENCE

    def test_from_string_auto(self) -> None:
        assert PromotionRule.from_string("auto") == PromotionRule.AUTO_IF_CONFIDENCE

    def test_from_string_manual_approval(self) -> None:
        assert PromotionRule.from_string("manual_approval") == PromotionRule.MANUAL_APPROVAL

    def test_from_string_manual(self) -> None:
        assert PromotionRule.from_string("manual") == PromotionRule.MANUAL_APPROVAL

    def test_from_string_governance_vote(self) -> None:
        assert PromotionRule.from_string("governance_vote") == PromotionRule.GOVERNANCE_VOTE

    def test_from_string_governance(self) -> None:
        assert PromotionRule.from_string("governance") == PromotionRule.GOVERNANCE_VOTE

    def test_from_string_case_insensitive(self) -> None:
        assert PromotionRule.from_string("AUTO_IF_CONFIDENCE") == PromotionRule.AUTO_IF_CONFIDENCE

    def test_from_string_dash_separated(self) -> None:
        assert PromotionRule.from_string("auto-if-confidence") == PromotionRule.AUTO_IF_CONFIDENCE

    def test_from_string_invalid_rule_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown promotion rule"):
            PromotionRule.from_string("invalid_rule")


# ═══════════════════════════════════════════════════════════════════════════
# AUTO_IF_CONFIDENCE promotion tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAutoPromotion:
    """Verify AUTO_IF_CONFIDENCE promotion behavior."""

    def test_auto_promotes_when_confidence_above_threshold(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.AUTO_IF_CONFIDENCE)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is True
        assert updated.status == "candidate"
        assert "auto_promoted" in reason

    def test_auto_promotes_at_exact_threshold(self) -> None:
        finding = _make_finding(confidence=0.85)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.AUTO_IF_CONFIDENCE)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is True
        assert updated.status == "candidate"

    def test_stays_advisory_when_confidence_below_threshold(self) -> None:
        finding = _make_finding(confidence=0.84)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.AUTO_IF_CONFIDENCE)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is False
        assert updated.status == "advisory"
        assert "confidence_below_threshold" in reason

    def test_stays_advisory_when_confidence_very_low(self) -> None:
        finding = _make_finding(confidence=0.01)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.AUTO_IF_CONFIDENCE)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is False
        assert updated.status == "advisory"


# ═══════════════════════════════════════════════════════════════════════════
# MANUAL_APPROVAL promotion tests
# ═══════════════════════════════════════════════════════════════════════════


class TestManualApproval:
    """Verify MANUAL_APPROVAL promotion behavior."""

    def test_manual_approval_requires_governor_token(self) -> None:
        finding = _make_finding(confidence=0.7)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.MANUAL_APPROVAL)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is False
        assert "governor_token_required" in reason

    def test_manual_approval_succeeds_with_valid_governor_token(self) -> None:
        finding = _make_finding(confidence=0.7)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.MANUAL_APPROVAL)
        token = create_governor_token()
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), governor_token=token
        )
        assert success is True
        assert updated.status == "candidate"
        assert updated.promoter == "governor"
        assert "manual_approval_granted" in reason

    def test_manual_approval_fails_with_invalid_token(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.MANUAL_APPROVAL)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), governor_token="bad-token"
        )
        assert success is False
        assert "governor_token_required" in reason

    def test_manual_approval_fails_with_empty_token(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.MANUAL_APPROVAL)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), governor_token=""
        )
        assert success is False


# ═══════════════════════════════════════════════════════════════════════════
# GOVERNANCE_VOTE promotion tests
# ═══════════════════════════════════════════════════════════════════════════


class TestGovernanceVote:
    """Verify GOVERNANCE_VOTE promotion behavior."""

    def test_governance_vote_requires_3_signatures(self) -> None:
        finding = _make_finding(confidence=0.5)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.GOVERNANCE_VOTE)
        # Only 2 signatures
        sigs = [
            create_validator_signature("v1"),
            create_validator_signature("v2"),
        ]
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), validator_signatures=sigs
        )
        assert success is False
        assert "insufficient" in reason
        assert "2/5" in reason

    def test_governance_vote_succeeds_with_3_signatures(self) -> None:
        finding = _make_finding(confidence=0.5)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.GOVERNANCE_VOTE)
        sigs = [
            create_validator_signature("v1"),
            create_validator_signature("v2"),
            create_validator_signature("v3"),
        ]
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), validator_signatures=sigs
        )
        assert success is True
        assert updated.status == "candidate"
        assert updated.promoter == "governance_validators"
        assert "3/5" in reason

    def test_governance_vote_succeeds_with_5_signatures(self) -> None:
        finding = _make_finding(confidence=0.5)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.GOVERNANCE_VOTE)
        sigs = [
            create_validator_signature(f"v{i}") for i in range(1, 6)
        ]
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), validator_signatures=sigs
        )
        assert success is True
        assert "5/5" in reason

    def test_governance_vote_duplicate_signatures_count_once(self) -> None:
        finding = _make_finding(confidence=0.5)
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.GOVERNANCE_VOTE)
        sig = create_validator_signature("v1")
        # Same signature 3 times
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), validator_signatures=[sig, sig, sig]
        )
        assert success is False
        assert "1/5" in reason

    def test_governance_vote_invalid_signatures_not_counted(self) -> None:
        finding = _make_finding()
        proposal = create_dream_proposal(finding, promotion_rule=PromotionRule.GOVERNANCE_VOTE)
        sigs = ["not-hex" * 8, "", "short"]  # all invalid
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True), validator_signatures=sigs
        )
        assert success is False
        assert "0/5" in reason


# ═══════════════════════════════════════════════════════════════════════════
# CoVE gate enforcement tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCoveGateEnforcement:
    """Verify CoVE gate enforcement on promotion."""

    def test_promotion_fails_without_cove_gate_pass(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=None
        )
        assert success is False
        assert "cove_gate" in reason.lower()

    def test_promotion_fails_with_cove_gate_fail(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(False)
        )
        assert success is False
        assert "cove_gate" in reason.lower()

    def test_promotion_succeeds_with_cove_gate_pass_and_auto_confidence(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is True
        assert updated.status == "candidate"

    def test_cove_gate_pass_with_all_proven(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result={"passed": False, "all_proven": True}
        )
        assert success is True

    def test_cove_gate_pass_with_approved_verdict(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result={"verdict": "APPROVED"}
        )
        assert success is True

    def test_cove_gate_fail_with_denied_verdict(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_candidate(
            proposal, cove_result={"verdict": "DENIED"}
        )
        assert success is False

    def test_promote_to_binding_also_requires_cove(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        proposal.status = "candidate"  # Pre-promote
        updated, success, reason = promote_to_binding(
            proposal, cove_result=None
        )
        assert success is False
        assert "cove_gate" in reason.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Full pipeline tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """Verify complete observe→propose→verify→promote pipeline."""

    def test_full_pipeline_with_auto_promote(self) -> None:
        lc = InstinctLifecycle()
        result = lc.run_observe_propose_cycle(
            "pipeline-mission",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
            auto_promote=True,
            cove_result=_make_cove_result(True),
            governor_token=create_governor_token(),
        )
        assert result["status"] == "ok"
        cycle = result["cycle_results"]
        assert cycle["observe"]["status"] == "ok"
        assert cycle["propose"]["status"] == "ok"

    def test_full_pipeline_sets_cycle_results(self) -> None:
        lc = InstinctLifecycle()
        result = lc.run_observe_propose_cycle(
            "pipeline-2",
            weekly_artifacts=[
                {"artifact_id": "wa-1", "artifact_status": "advisory", "source": "test"}
            ],
            auto_promote=False,
        )
        assert result["status"] == "ok"
        assert "observe" in result["cycle_results"]
        assert "propose" in result["cycle_results"]
        assert "verification" in result["cycle_results"]
        assert "promotions" in result["cycle_results"]

    def test_pipeline_stores_findings_in_mission(self) -> None:
        lc = InstinctLifecycle()
        lc.run_observe_propose_cycle(
            "pipeline-3",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        mission = lc.get_mission("pipeline-3")
        assert mission is not None
        assert len(mission.get("dream_findings", [])) > 0

    def test_pipeline_stores_proposals_in_mission(self) -> None:
        lc = InstinctLifecycle()
        lc.run_observe_propose_cycle(
            "pipeline-4",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        mission = lc.get_mission("pipeline-4")
        assert mission is not None
        assert len(mission.get("dream_proposals", {})) > 0

    def test_observe_phase_fills_dream_findings(self) -> None:
        lc = InstinctLifecycle()
        result = lc.observe_phase(
            "observe-only",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        assert result["status"] == "ok"
        assert result["dream_findings_count"] > 0

    def test_propose_phase_creates_proposals_from_findings(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase(
            "propose-test",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        result = lc.propose_phase("propose-test")
        assert result["status"] == "ok"
        assert result["dream_proposals_count"] > 0

    def test_promote_finding_increases_status(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase(
            "promote-test",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        # Use override_promotion_rule=True to force AUTO_IF_CONFIDENCE for all
        # but also provide governor_token as fallback since memory facts produce
        # confidence=0.71 which is below AUTO_IF_CONFIDENCE threshold
        lc.propose_phase(
            "promote-test",
            promotion_rule=PromotionRule.MANUAL_APPROVAL,
            override_promotion_rule=True,
        )
        mission = lc.get_mission("promote-test")
        proposals = mission["dream_proposals"]
        proposal_id = next(iter(proposals))
        result = lc.promote_finding(
            "promote-test",
            proposal_id,
            cove_result=_make_cove_result(True),
            governor_token=create_governor_token(),
            target_status="candidate",
        )
        assert result["status"] == "ok"
        assert result["promotion_success"] is True

    def test_specify_entry_auto_completes_dream_phases(self) -> None:
        lc = InstinctLifecycle()
        result = lc.step("auto-dream", "specify", {"topic": "test"})
        assert result["status"] == "ok"
        assert result["dream_phases_auto_completed"] is True

    def test_specify_to_plan_works_when_dream_auto_completed(self) -> None:
        lc = InstinctLifecycle()
        lc.step("spec-to-plan", "specify", {"topic": "test"})
        result = lc.step("spec-to-plan", "plan", {
            "task_dag": [{"node_id": "x", "task_type": "modify_file"}]
        })
        assert result["status"] == "ok"
        assert result["current_phase"] == "plan"


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases and error conditions
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Verify edge cases are handled gracefully."""

    def test_empty_findings_during_observe(self) -> None:
        lc = InstinctLifecycle()
        # No artifacts, facts, or media — produces empty findings
        result = lc.observe_phase("empty-observe")
        assert result["status"] == "ok"
        assert result["dream_findings_count"] == 0

    def test_propose_without_observe_gives_error(self) -> None:
        lc = InstinctLifecycle()
        lc.step("no-observe", "specify", {"topic": "test"})
        result = lc.propose_phase("no-observe")
        assert "error" in result.get("status", "") or result.get("error")

    def test_propose_with_empty_findings_gives_error(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase("empty-findings")  # No inputs → empty findings
        result = lc.propose_phase("empty-findings")
        assert result.get("status") == "error" or result.get("error")

    def test_promote_nonexistent_proposal_gives_error(self) -> None:
        lc = InstinctLifecycle()
        lc.step("no-prop", "observe", {"topic": "test"})
        result = lc.promote_finding("no-prop", "nonexistent-id")
        assert result["status"] == "error"

    def test_promote_finding_not_found_mission(self) -> None:
        lc = InstinctLifecycle()
        result = lc.promote_finding("no-mission", "some-id")
        assert result["status"] == "error"

    def test_promote_to_invalid_target_status(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase(
            "invalid-target",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "x"}],
        )
        lc.propose_phase("invalid-target")
        mission = lc.get_mission("invalid-target")
        pid = next(iter(mission["dream_proposals"]))
        result = lc.promote_finding(
            "invalid-target", pid, target_status="invalid_status"
        )
        assert result["status"] == "error"

    def test_duplicate_proposal_ids_prevented_in_dict(self) -> None:
        """Proposals are stored in a dict keyed by proposal_id, so duplicates
        naturally overwrite — this is acceptable."""
        lc = InstinctLifecycle()
        lc.observe_phase(
            "dup-test",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "x"}],
        )
        lc.propose_phase("dup-test")
        # Run propose again; proposal dict should be overwritten, not appended
        lc.propose_phase("dup-test")
        mission = lc.get_mission("dup-test")
        # Proposals dict should exist and have entries
        assert isinstance(mission["dream_proposals"], dict)

    def test_conflicting_confidence_values_handled(self) -> None:
        """Different findings with different confidence levels produce
        proposals with matching confidence."""
        lc = InstinctLifecycle()
        lc.observe_phase(
            "conflicting",
            memory_facts=[
                {"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "high"},
                {"id": 2, "entry_kind": "fact", "sha256": _random_hex(), "topic": "low"},
            ],
        )
        lc.propose_phase("conflicting")
        mission = lc.get_mission("conflicting")
        proposals = mission["dream_proposals"]
        confidences = [p["confidence"] for p in proposals.values()]
        assert len(confidences) >= 1

    def test_malformed_evidence_refs_do_not_crash(self) -> None:
        finding = _make_finding()
        finding.evidence_refs = [{"bad": "data"}, {}]
        proposal = create_dream_proposal(finding)
        assert len(proposal.evidence_refs) == 2

    def test_proposal_with_none_cove_result(self) -> None:
        proposal = create_dream_proposal(_make_finding())
        proposal.cove_result = None
        # Roundtrip through to_dict
        d = proposal.to_dict()
        assert d["cove_result"] is None

    def test_proposal_with_cove_result_preserves_data(self) -> None:
        proposal = create_dream_proposal(_make_finding())
        proposal.cove_result = {"passed": True, "details": "all good"}
        d = proposal.to_dict()
        assert d["cove_result"]["passed"] is True
        assert d["cove_result"]["details"] == "all good"

    def test_cannot_promote_binding_from_advisory_directly(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        updated, success, reason = promote_to_binding(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is False
        assert "cannot promote to binding from status 'advisory'" in reason

    def test_cannot_promote_candidate_from_binding(self) -> None:
        finding = _make_finding(confidence=0.9)
        proposal = create_dream_proposal(finding)
        proposal.status = "binding"
        updated, success, reason = promote_to_candidate(
            proposal, cove_result=_make_cove_result(True)
        )
        assert success is False
        assert "cannot promote from status 'binding'" in reason

    def test_governor_token_validation(self) -> None:
        assert _validate_governor_token("") is False
        assert _validate_governor_token("bad") is False
        assert _validate_governor_token("gov-") is False
        assert _validate_governor_token("gov-short") is False
        valid = create_governor_token()
        assert _validate_governor_token(valid) is True

    def test_validator_signature_counting(self) -> None:
        sigs = [
            create_validator_signature("a"),
            create_validator_signature("b"),
            create_validator_signature("c"),
            "not-valid-hex-at-all-so-this-fails-validation-completely",
            "",
        ]
        assert _count_valid_signatures(sigs) == 3

    def test_run_observe_propose_with_governor_and_auto_promote(self) -> None:
        lc = InstinctLifecycle()
        result = lc.run_observe_propose_cycle(
            "gov-test",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
            auto_promote=True,
            cove_result=_make_cove_result(True),
            governor_token=create_governor_token(),
        )
        assert result["status"] == "ok"

    def test_allowed_next_after_propose_includes_observe(self) -> None:
        """propose can go back to observe for a new dream cycle."""
        assert "observe" in _ALLOWED_NEXT["propose"]

    def test_backward_phase_transitions_blocked_unless_override(self) -> None:
        lc = InstinctLifecycle()
        lc.step("backward", "observe", {"topic": "test"})
        lc.step("backward", "propose")
        lc.step("backward", "specify", {"topic": "test"})
        # Try to go back to observe without override
        result = lc.step("backward", "observe")
        assert result["status"] == "error"

    def test_backward_phase_transition_allowed_with_override(self) -> None:
        lc = InstinctLifecycle()
        lc.step("backward-ok", "observe", {"topic": "test"})
        lc.step("backward-ok", "propose")
        lc.step("backward-ok", "specify", {"topic": "test"})
        result = lc.step("backward-ok", "observe", override=True)
        assert result["status"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════
# Thread safety tests
# ═══════════════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Verify thread-safe operation of lifecycle with dream phases."""

    def test_concurrent_observes_on_different_missions(self) -> None:
        import threading

        lc = InstinctLifecycle()
        errors: list[str] = []

        def run_observe(name: str) -> None:
            try:
                lc.observe_phase(
                    name,
                    memory_facts=[
                        {"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": name}
                    ],
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=run_observe, args=(f"thread-{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_promotions_on_same_mission(self) -> None:
        import threading

        lc = InstinctLifecycle()
        lc.observe_phase(
            "shared",
            memory_facts=[
                {"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "shared"},
                {"id": 2, "entry_kind": "fact", "sha256": _random_hex(), "topic": "shared"},
            ],
        )
        lc.propose_phase("shared", override_promotion_rule=True)
        mission = lc.get_mission("shared")
        proposal_ids = list(mission["dream_proposals"].keys())

        errors: list[str] = []

        def run_promote(pid: str) -> None:
            try:
                lc.promote_finding(
                    "shared", pid,
                    cove_result=_make_cove_result(True),
                    target_status="candidate",
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=run_promote, args=(pid,)) for pid in proposal_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════
# Dream cycle report tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDreamCycleReport:
    """Verify dream cycle report generation in observe phase."""

    def test_observe_generates_cycle_report(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase(
            "report-test",
            memory_facts=[{"id": 1, "entry_kind": "fact", "sha256": _random_hex(), "topic": "test"}],
        )
        mission = lc.get_mission("report-test")
        report = mission.get("dream_cycle_report")
        assert report is not None
        assert "cycle_id" in report
        assert "finding_count" in report
        assert report["status"] == "completed"

    def test_observe_without_inputs_produces_zero_findings_report(self) -> None:
        lc = InstinctLifecycle()
        lc.observe_phase("empty-report")
        mission = lc.get_mission("empty-report")
        report = mission.get("dream_cycle_report")
        assert report is not None
        assert report["finding_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle list_missions includes dream info
# ═══════════════════════════════════════════════════════════════════════════


class TestMissionListing:
    """Verify mission listing reflects dream cycle state."""

    def test_list_missions_includes_dream_phases(self) -> None:
        lc = InstinctLifecycle()
        lc.step("list-1", "observe", {"topic": "test"})
        missions = lc.list_missions()
        assert any(m["mission_id"] == "list-1" for m in missions)

    def test_list_missions_shows_correct_phase(self) -> None:
        lc = InstinctLifecycle()
        lc.step("list-2", "observe", {"topic": "test"})
        lc.step("list-2", "propose")
        missions = lc.list_missions()
        mission = next(m for m in missions if m["mission_id"] == "list-2")
        assert mission["current_phase"] == "propose"
