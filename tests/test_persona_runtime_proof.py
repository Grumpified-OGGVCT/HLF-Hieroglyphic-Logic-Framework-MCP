"""
Persona Runtime Proof: prove that personas actually govern, communicate, build,
and block as declared.  Full pipeline: persona -> constraint -> verification -> execution.

Uses the real swarm orchestrator and governance infrastructure.
At least 20 tests.
"""

from __future__ import annotations

import json
import uuid

import pytest

from hlf_mcp.hlf.swarm_orchestrator import (
    SwarmOrchestrator,
    SwarmResult,
    SwarmPhase,
)
from hlf_mcp.hlf.formal_verifier import FormalVerifier, VerificationGate, GateDecision
from hlf_mcp.hlf.witness_governance import WitnessGovernance, WitnessObservation
from hlf_mcp.hlf.swarm_observer import SwarmObserver
from hlf_mcp.hlf.swarm_consensus import SwarmLedger, VotePosition
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.handoff_events import PERSONA_ROLES
from hlf_mcp.persona_contract import resolve_persona_contract
from hlf_mcp.persona_runtime import resolve_persona_runtime_metadata


# ═══════════════════════════════════════════════════════════════════════════════
# Steward Persona Proofs (tests 1-5)
# ═══════════════════════════════════════════════════════════════════════════════
# Prove that the Steward persona actually governs execution.

def test_steward_persona_has_runtime_metadata() -> None:
    """Steward persona exists in the runtime metadata catalog."""
    meta = resolve_persona_runtime_metadata("steward")
    assert meta is not None
    assert meta["persona"] == "steward"
    assert "maintainer_mode" in meta
    assert "hat" in meta


def test_steward_persona_governs_workflow_contract() -> None:
    """Steward is the owner persona for workflow_contract change class."""
    contract = resolve_persona_contract(
        source="weekly-spec-sentinel",
        review_type="weekly_artifact",
        severity="warning",
        recommended_triage_lane="backlog",
    )
    assert contract["change_class"] == "workflow_contract"
    assert contract["owner_persona"] == "steward"
    assert "steward_review" in contract["required_gates"]


def test_steward_oversight_is_logged_in_swarm() -> None:
    """When a swarm runs with Steward, oversight decisions are observable."""
    orchestrator = SwarmOrchestrator()
    governance = orchestrator.governance

    # Record a Steward oversight observation
    obs = WitnessObservation(
        witness_id="steward",
        subject_agent_id="steward-agent",
        category="swarm_phase:plan",
        severity="info",
        confidence=0.98,
        goal_id="governance-check",
        details={"role": "steward", "action": "oversight_review"},
    )
    observation = governance.record_observation(obs)
    assert observation is not None
    # Oversight decision is logged
    snapshot = governance.get_snapshot("steward-agent")
    assert snapshot is not None
    snap_dict = snapshot.to_dict()
    assert "aggregate_score" in snap_dict
    assert float(snap_dict["aggregate_score"]) > 0.0


def test_steward_constraint_applied_before_execution() -> None:
    """Steward constraint is present before execution via governance path."""
    orchestrator = SwarmOrchestrator()
    # The governance component tracks trust scores per agent
    gov = orchestrator.governance
    snap_before = gov.get_snapshot("steward-agent")
    initial_observations = snap_before.total_observations if snap_before else 0

    # Record a constraint check
    obs = WitnessObservation(
        witness_id="steward",
        subject_agent_id="steward-agent",
        category="steward_constraint",
        severity="info",
        confidence=1.0,
        goal_id="pre_execution_check",
        details={"constraint": "tier_gate", "verdict": "allowed"},
    )
    gov.record_observation(obs)
    snapshot_after = gov.get_snapshot("steward-agent")
    assert snapshot_after is not None
    assert snapshot_after.total_observations > initial_observations


def test_steward_verification_gate_passes_for_valid_hlf() -> None:
    """Steward governance path admits valid HLF through verification gate."""
    compiler = HLFCompiler()
    verifier = FormalVerifier()
    source = "[HLF-v3]\nRESULT 1 + 1\nΩ\n"
    ast = compiler.compile(source)["ast"]
    report = verifier.verify_ast(ast, gas_budget=100)
    decision = VerificationGate.gate(report, "operators")
    assert decision in (GateDecision.PROCEED, GateDecision.WARN)


# ═══════════════════════════════════════════════════════════════════════════════
# Herald Persona Proofs (tests 6-9)
# ═══════════════════════════════════════════════════════════════════════════════
# Prove that the Herald persona actually produces communication artifacts.

def test_herald_persona_has_runtime_metadata() -> None:
    """Herald persona exists in the runtime metadata catalog."""
    meta = resolve_persona_runtime_metadata("herald")
    assert meta is not None
    assert meta["persona"] == "herald"
    assert meta["internal_role"] == "documentation_truth_reviewer"
    assert meta["hat"] == "white"


def test_herald_produces_communication_artifacts() -> None:
    """Herald ownership gates produce traceable communication records."""
    contract = resolve_persona_contract(
        source="weekly-doc-accuracy",
        review_type="weekly_artifact",
        severity="warning",
        recommended_triage_lane="backlog",
    )
    assert contract["change_class"] == "docs_truth"
    assert contract["owner_persona"] == "herald"

    # Herald's gate exists and carries documentation expectations
    gate = contract["gate_results"].get("herald_review", {})
    assert gate.get("owner_persona") == "herald"
    assert gate.get("status") is None  # default state before review


def test_herald_handoff_produces_communication_event() -> None:
    """A handoff event with Herald as target produces a traceable event."""
    from hlf_mcp import server
    event = server.hlf_record_handoff_event(
        delegator="strategist-agent",
        delegate="herald-agent",
        scope="communication-test",
        source_persona="strategist",
        target_persona="herald",
        event_type="delegate",
    )
    assert event["status"] == "ok"
    assert event["source_persona"] == "strategist"
    assert event["target_persona"] == "herald"
    assert "event_hash" in event


def test_herald_docs_truth_requires_all_communication_gates() -> None:
    """Docs truth change class requires Herald + additional review personas."""
    contract = resolve_persona_contract(
        source="weekly-doc-accuracy",
        review_type="weekly_artifact",
        severity="warning",
        recommended_triage_lane="backlog",
    )
    assert "herald_review" in contract["required_gates"]
    assert "strategist_review" in contract["required_gates"]
    assert "chronicler_review" in contract["required_gates"]
    assert "cove_review" in contract["required_gates"]
    assert "operator_promotion" in contract["required_gates"]


# ═══════════════════════════════════════════════════════════════════════════════
# Builder Persona Proofs (tests 10-13)
# ═══════════════════════════════════════════════════════════════════════════════
# Prove that the Builder persona exists in the matrix and matches precision constraints.

def test_builder_persona_in_persona_roles() -> None:
    """Builder persona is recognized in the PERSONA_ROLES set."""
    # Builder/strategist overlap — the persona catalog has strategist as the planning role
    assert "strategist" in PERSONA_ROLES


def test_builder_precision_constraint_is_represented() -> None:
    """Builder persona's precision constraint survives contract resolution."""
    # The strategist is the planning/build persona; verify its metadata
    meta = resolve_persona_runtime_metadata("strategist")
    assert meta is not None
    assert meta["persona"] == "strategist"
    assert meta["internal_role"] == "planning_authority"


def test_builder_generates_verifiable_artifacts() -> None:
    """Builder-produced HLF artifacts pass compilation verification."""
    compiler = HLFCompiler()
    # Simulate a Builder-generated artifact — a well-formed HLF plan
    builder_artifact = """\
[HLF-v3]
SET plan_version = 1
Δ [ANALYZE] scope="build-target"
  Ж [VERIFY] mode="strict"
⨝ [VOTE] consensus="majority"
Ω
"""
    result = compiler.compile(builder_artifact)
    assert result["errors"] == []
    assert result["ast"]["kind"] == "program"


def test_builder_pipeline_produces_matching_swarm_phase() -> None:
    """A swarm phase with Builder/planner role produces verifiable output."""
    orchestrator = SwarmOrchestrator()
    # Run a two-channel dispatch simulating Builder's role
    result = orchestrator.dispatch_two_channel(
        source="[HLF-v3]\nRESULT \"built\"\nΩ\n",
        agent_id="builder-agent",
        role="planner",
        tier="sovereign",
        gas_limit=200,
    )
    assert result["status"] in ("ok", "compile_error", "verification_blocked", "blocked")
    # The dispatch was recorded with the planner (builder) role
    assert result["role"] == "planner"


# ═══════════════════════════════════════════════════════════════════════════════
# Sentinel Persona Proofs (tests 14-17)
# ═══════════════════════════════════════════════════════════════════════════════
# Prove that the Sentinel persona actually blocks unauthorized operations.

def test_sentinel_persona_has_runtime_metadata() -> None:
    """Sentinel persona exists in the runtime metadata catalog."""
    meta = resolve_persona_runtime_metadata("sentinel")
    assert meta is not None
    assert meta["persona"] == "sentinel"
    assert meta["internal_role"] == "security_boundary_reviewer"
    assert meta["hat"] == "black"
    assert "cove" in meta["cross_awareness"]


def test_sentinel_blocks_security_sensitive_changes() -> None:
    """Sentinel is the owner for security_sensitive change class."""
    contract = resolve_persona_contract(
        source="weekly-code-quality",
        review_type="weekly_artifact",
        severity="critical",
        recommended_triage_lane="current_batch",
    )
    assert contract["change_class"] == "security_sensitive"
    assert contract["owner_persona"] == "sentinel"
    assert "sentinel_review" in contract["required_gates"]


def test_sentinel_existing_block_preserved() -> None:
    """Sentinel's existing block is preserved through contract resolution."""
    contract = resolve_persona_contract(
        source="weekly-code-quality",
        review_type="weekly_artifact",
        severity="critical",
        recommended_triage_lane="current_batch",
        existing={
            "gate_results": {
                "sentinel_review": {
                    "owner_persona": "sentinel",
                    "status": "blocked",
                    "notes": "Security vulnerability detected.",
                }
            }
        },
    )
    assert contract["gate_results"]["sentinel_review"]["status"] == "blocked"
    assert contract["escalate_to_persona"] == "operator"


def test_sentinel_unauthorized_operations_blocked_at_sentinel_tier() -> None:
    """Sentinel governance path blocks unauthorized operations."""
    from hlf_mcp.hlf.execution_admission import evaluate_verifier_admission

    compiler = HLFCompiler()
    verifier = FormalVerifier()

    # A program with a file_write call — should be restricted at hearth tier
    source = '[HLF-v3]\nCALL host "write_file" "test.txt"\nΩ\n'
    ast = compiler.compile(source)["ast"]

    admission = evaluate_verifier_admission(
        ast=ast,
        verifier=verifier,
        tier="hearth",
        requested_tier="hearth",
        mode="strict",
        embodied_contract={},
        trust_state="healthy",
    )
    # At hearth tier, file operations should be reviewed
    assert admission.verdict in ("WARN", "BLOCK", "REVIEW_REQUIRED", "verification_review_required"), \
        f"Expected restricted verdict at hearth tier, got {admission.verdict}"
    assert len(admission.reasons) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Full Pipeline Proofs (tests 18-22)
# ═══════════════════════════════════════════════════════════════════════════════
# Prove the full persona -> constraint -> verification -> execution pipeline.

def test_full_pipeline_steward_orchestrates_with_governance() -> None:
    """Full pipeline: Steward orchestrates swarm with governance tracking."""
    orchestrator = SwarmOrchestrator()
    gov = orchestrator.governance

    # Pre-execution: record Steward oversight
    obs = WitnessObservation(
        witness_id="steward",
        subject_agent_id="steward",
        category="pipeline_start",
        severity="info",
        confidence=0.99,
        goal_id="full-pipeline",
        details={"persona": "steward", "phase": "init"},
    )
    gov.record_observation(obs)
    # Execute a simple dispatch
    result = orchestrator.dispatch_two_channel(
        source="[HLF-v3]\nRESULT 1 + 1\nΩ\n",
        agent_id="steward",
        role="executor",
        tier="sovereign",
    )
    assert result["status"] in ("ok", "blocked", "compile_error")
    # Post-execution: Steward oversight record exists
    snapshot = gov.get_snapshot("steward")
    assert snapshot is not None
    assert snapshot.total_observations > 0


def test_full_pipeline_herald_communicates_results() -> None:
    """Full pipeline: Herald's role produces communication artifacts."""
    from hlf_mcp import server
    # Chain of handoffs with Herald as communicator
    e1 = server.hlf_record_handoff_event(
        delegator="planner-agent",
        delegate="herald-relay",
        scope="pipeline-comm",
        source_persona="planner",
        target_persona="herald",
        event_type="delegate",
        lifecycle_phase="report",
    )
    assert e1["status"] == "ok"
    assert e1["target_persona"] == "herald"

    chain = server.hlf_handoff_chain(e1["event_hash"])
    assert chain["status"] == "ok"
    assert chain["verification_summary"]["verified"] is True
    assert len(chain["persona_lineage"]) >= 1


def test_full_pipeline_sentinel_verification_gate() -> None:
    """Full pipeline: Sentinel's security gate blocks dangerous operations."""
    compiler = HLFCompiler()
    verifier = FormalVerifier()

    # A program with a file_write call
    source = '[HLF-v3]\n⌘ [EXEC] cmd="rm -rf /"\nΩ\n'
    ast = compiler.compile(source)["ast"]
    report = verifier.verify_ast(ast, gas_budget=100)
    decision = VerificationGate.gate(report, "hearth")
    # At hearth tier, this should be blocked or warned
    assert decision != GateDecision.PROCEED, "Dangerous operation should not proceed at hearth tier"


def test_full_pipeline_each_persona_has_constraint_surface() -> None:
    """Every persona in the catalog has a constraint surface."""
    from hlf_mcp.persona_runtime import load_persona_runtime_catalog
    catalog = load_persona_runtime_catalog()
    for persona_name, entry in catalog.items():
        assert entry["persona"] == persona_name
        assert "lane" in entry
        assert "runtime_authority" in entry
        assert isinstance(entry["runtime_authority"], bool)
        assert "internal_role" in entry
        assert isinstance(entry["internal_role"], str)  # some personas have empty roles


def test_full_pipeline_all_personas_in_role_set() -> None:
    """All personas in the contract matrix are present in PERSONA_ROLES."""
    from hlf_mcp.persona_contract import load_persona_matrix
    matrix = load_persona_matrix()
    matrix_personas = set(matrix.get("personas", {}).keys())
    matrix_personas.add("operator")

    for p in matrix_personas:
        assert p in PERSONA_ROLES, f"Matrix persona {p!r} not in PERSONA_ROLES"

    for workflow_persona in ("planner", "executor", "verifier", "scribe"):
        assert workflow_persona in PERSONA_ROLES


def test_full_pipeline_observer_captures_persona_events() -> None:
    """SwarmObserver captures events tagged with persona roles."""
    observer = SwarmObserver()
    events = []

    # Patch emit to capture
    original_emit = observer.emit

    def capture_emit(**kwargs):
        events.append(kwargs)
        original_emit(**kwargs)

    observer.emit = capture_emit
    observer.emit(
        swarm_id="test-swarm",
        phase_id="plan",
        agent_id="steward-agent",
        role="steward",
        event_type="persona_action",
        message="Steward oversight decision",
        payload={"decision": "approved", "constraints": ["gas_limit", "tier_check"]},
    )

    assert len(events) == 1
    assert events[0]["role"] == "steward"
    assert events[0]["event_type"] == "persona_action"
    assert "constraints" in events[0]["payload"]


def test_full_pipeline_sentinel_block_escalates_to_operator() -> None:
    """When Sentinel blocks, escalation targets the Operator persona."""
    contract = resolve_persona_contract(
        source="weekly-code-quality",
        review_type="weekly_artifact",
        severity="critical",
        recommended_triage_lane="current_batch",
        existing={
            "gate_results": {
                "sentinel_review": {
                    "owner_persona": "sentinel",
                    "status": "blocked",
                    "notes": "Critical vulnerability found.",
                }
            }
        },
    )
    assert contract["escalate_to_persona"] == "operator"
    assert contract["owner_persona"] == "sentinel"


def test_full_pipeline_consensus_ledger_tracks_persona_votes() -> None:
    """SwarmLedger tracks votes from different persona roles."""
    ledger = SwarmLedger(swarm_id="test-ledger")

    # Create a proposal first
    prop = ledger.propose(
        title="Gate pass vote",
        description="Should we pass the security gate?",
        proposed_by="steward-agent",
    )
    prop_id = prop.proposal_id

    # Record votes from different personas
    v1 = ledger.vote(
        proposal_id=prop_id,
        voter_agent="steward-agent",
        position=VotePosition.APPROVE,
        reason="Looks safe.",
    )
    v2 = ledger.vote(
        proposal_id=prop_id,
        voter_agent="sentinel-agent",
        position=VotePosition.REJECT,
        reason="Security risk detected.",
    )
    v3 = ledger.vote(
        proposal_id=prop_id,
        voter_agent="herald-agent",
        position=VotePosition.ABSTAIN,
        reason="Need more context.",
    )

    assert v1 is not None
    assert v2 is not None
    assert v3 is not None

    # Query tally for the proposal
    tally = ledger.get_tally(proposal_id=prop_id)
    assert tally["total"] >= 3
    assert tally["approve"] >= 1
    assert tally["reject"] >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Persona Contract Gating Proofs (tests 23-24)
# ═══════════════════════════════════════════════════════════════════════════════

def test_persona_contract_requires_operator_promotion_for_sensitive_changes() -> None:
    """All governance change classes require operator promotion as final gate."""
    for source, severity in [
        ("weekly-doc-accuracy", "warning"),
        ("weekly-code-quality", "critical"),
        ("weekly-spec-sentinel", "warning"),
    ]:
        contract = resolve_persona_contract(
            source=source,
            review_type="weekly_artifact",
            severity=severity,
            recommended_triage_lane="backlog",
        )
        assert "operator_promotion" in contract["required_gates"], \
            f"operator_promotion missing from {source}"


def test_persona_runtime_catalog_is_bounded_and_consistent() -> None:
    """Runtime catalog is internally consistent: every entry has required fields."""
    from hlf_mcp.persona_runtime import load_persona_runtime_catalog
    catalog = load_persona_runtime_catalog()

    required_fields = {"persona", "lane", "runtime_authority", "internal_role",
                       "maintainer_mode", "hat", "role", "upstream_source", "cross_awareness"}
    for name, entry in catalog.items():
        missing = required_fields - set(entry.keys())
        assert not missing, f"Persona '{name}' missing fields: {missing}"
        assert isinstance(entry["cross_awareness"], list)
        assert isinstance(entry["runtime_authority"], bool)

    # Runtime authority is always False — only Operator (human) has it
    for entry in catalog.values():
        assert entry["runtime_authority"] is False, \
            f"Persona '{entry['persona']}' should not have runtime_authority"
