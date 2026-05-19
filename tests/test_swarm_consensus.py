"""Tests for swarm_consensus.py — delegation, dissent, and consensus primitives."""
import sys
sys.path.insert(0, ".")
from hlf_mcp.hlf.swarm_consensus import (
    SwarmLedger, VotePosition, QuorumType, DelegationStatus,
    Proposal, Vote, Delegation, DissentRecord,
)


def test_propose_and_vote():
    """Propose, vote, and resolve with simple majority."""
    ledger = SwarmLedger("test-swarm-1")

    # Propose
    prop = ledger.propose("Use PostgreSQL", "Switch DB from SQLite to PostgreSQL",
                          proposed_by="Architect", quorum=QuorumType.SIMPLE_MAJORITY)
    assert prop.status == "open"
    assert prop.proposed_by == "Architect"

    # Three agents vote
    ledger.vote(prop.proposal_id, "Architect", VotePosition.APPROVE, "Better for scale")
    ledger.vote(prop.proposal_id, "DBA", VotePosition.APPROVE, "Agreed")
    ledger.vote(prop.proposal_id, "SecurityEngineer", VotePosition.REJECT, "Attack surface")

    # Resolve — 2/3 = majority
    resolution, reason = ledger.resolve(prop.proposal_id)
    assert resolution == "approved", f"Expected approved, got {resolution}: {reason}"
    assert "2/3" in reason

    # Tally
    tally = ledger.get_tally(prop.proposal_id)
    assert tally["approve"] == 2
    assert tally["reject"] == 1

    print("✓ test_propose_and_vote PASSED")


def test_supermajority():
    """Supermajority requires >= 67%."""
    ledger = SwarmLedger()

    prop = ledger.propose("Deploy to prod", "Deploy v2.0",
                          proposed_by="DevOps", quorum=QuorumType.SUPERMAJORITY)

    # 4 approve, 2 reject = 66.7% — should NOT pass
    for i in range(4):
        ledger.vote(prop.proposal_id, f"Agent{i}", VotePosition.APPROVE)
    for i in range(4, 6):
        ledger.vote(prop.proposal_id, f"Agent{i}", VotePosition.REJECT)

    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "pending", f"Expected pending at 4/6, got {resolution}"

    # Add one more approve — 5/7 = 71.4%
    ledger.vote(prop.proposal_id, "Agent6", VotePosition.APPROVE)
    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "approved", f"Expected approved at 5/7, got {resolution}"

    print("✓ test_supermajority PASSED")


def test_unanimous():
    """Unanimous requires 100% approval."""
    ledger = SwarmLedger()

    prop = ledger.propose("Emergency stop", "Halt all operations",
                          proposed_by="SafetyMonitor", quorum=QuorumType.UNANIMOUS)

    ledger.vote(prop.proposal_id, "SafetyMonitor", VotePosition.APPROVE)
    ledger.vote(prop.proposal_id, "OperatorA", VotePosition.APPROVE)
    ledger.vote(prop.proposal_id, "OperatorB", VotePosition.REJECT)

    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "rejected", f"Expected rejected, got {resolution}"

    # Replace OperatorB's vote
    ledger.vote(prop.proposal_id, "OperatorB", VotePosition.APPROVE)
    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "approved", f"Expected approved (unanimous), got {resolution}"

    print("✓ test_unanimous PASSED")


def test_designated_approver():
    """Only the designated approver's vote counts."""
    ledger = SwarmLedger()

    prop = ledger.propose("Grant admin access", "Give root to new hire",
                          proposed_by="HR", quorum=QuorumType.DESIGNATED_APPROVER,
                          designated_approver="SecurityLead")

    ledger.vote(prop.proposal_id, "HR", VotePosition.APPROVE)
    ledger.vote(prop.proposal_id, "Manager", VotePosition.APPROVE)
    # SecurityLead hasn't voted yet — deadlocked
    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "deadlocked", f"Expected deadlocked, got {resolution}"

    ledger.vote(prop.proposal_id, "SecurityLead", VotePosition.REJECT, "Too risky")
    resolution, reason = ledger.resolve(prop.proposal_id)
    assert resolution == "rejected"
    assert "SecurityLead" in reason

    print("✓ test_designated_approver PASSED")


def test_delegation_lifecycle():
    """Full delegation lifecycle: propose → accept → complete."""
    ledger = SwarmLedger()

    d = ledger.delegate(
        from_agent="Orchestrator",
        to_agent="DBA",
        task="Create migration scripts for users table",
        constraints=["COMMONJS", "NO-INSTALL"],
        priority=1,
    )
    assert d.status == DelegationStatus.PROPOSED

    # Accept
    d = ledger.accept_delegation(d.delegation_id)
    assert d.status == DelegationStatus.ACCEPTED

    # Complete
    d = ledger.complete_delegation(d.delegation_id, "Migration created at migrations/001_users.sql")
    assert d.status == DelegationStatus.COMPLETED
    assert "migrations/001_users.sql" in d.result

    # Pending delegations = 0
    assert len(ledger.pending_delegations()) == 0

    # Another delegation that stays proposed
    d2 = ledger.delegate("Orchestrator", "FrontendDev", "Build login page")
    assert len(ledger.pending_delegations()) == 1

    # Decline
    d2 = ledger.decline_delegation(d2.delegation_id, "Not my domain")
    assert d2.status == DelegationStatus.DECLINED
    assert "Not my domain" in d2.result

    print("✓ test_delegation_lifecycle PASSED")


def test_dissent_recording():
    """Record and query dissents."""
    ledger = SwarmLedger()

    prop = ledger.propose("Use MongoDB", "Switch to document store",
                          proposed_by="Architect")

    # Record a standard dissent
    dissent = ledger.dissent(
        prop.proposal_id,
        dissenter_agent="DBA",
        reason="Schema-less design risks data integrity",
        counter_proposal="Use PostgreSQL with JSONB columns",
        severity="standard",
    )
    assert dissent.severity == "standard"
    assert dissent.proposal_id == prop.proposal_id

    # Record a blocking dissent
    bd = ledger.dissent(
        prop.proposal_id,
        dissenter_agent="SecurityEngineer",
        reason="MongoDB lacks encryption-at-rest by default",
        severity="blocking",
    )

    blocking = ledger.blocking_dissents(prop.proposal_id)
    assert len(blocking) == 1
    assert blocking[0].dissenter_agent == "SecurityEngineer"

    print("✓ test_dissent_recording PASSED")


def test_ledger_summary():
    """Ledger summary provides accurate state."""
    ledger = SwarmLedger("summary-test")

    prop1 = ledger.propose("P1", "First proposal", proposed_by="A1")
    prop2 = ledger.propose("P2", "Second proposal", proposed_by="A2")

    ledger.vote(prop1.proposal_id, "A1", VotePosition.APPROVE)
    ledger.vote(prop1.proposal_id, "A2", VotePosition.REJECT)

    ledger.delegate("A1", "A2", "Task 1")
    ledger.dissent(prop2.proposal_id, "A3", "Disagree")

    summary = ledger.summary()
    assert summary["proposals"] == 2
    assert summary["open_proposals"] == 2
    assert summary["total_votes"] == 2
    assert summary["delegations"] == 1
    assert summary["pending_delegations"] == 1
    assert summary["total_dissents"] == 1
    assert len(ledger.events) > 0
    assert summary["chain_hash"] == ledger.chain_hash[:16]

    print("✓ test_ledger_summary PASSED")


def test_merkle_chain_integrity():
    """Each operation extends the Merkle chain."""
    ledger = SwarmLedger("chain-test")
    h0 = ledger.chain_hash

    ledger.propose("Test", "Chain integrity test", proposed_by="Agent1")
    h1 = ledger.chain_hash
    assert h1 != h0, "Chain hash should change after proposal"

    ledger.vote(list(ledger.proposals.values())[0].proposal_id,
                "Agent1", VotePosition.APPROVE)
    h2 = ledger.chain_hash
    assert h2 != h1, "Chain hash should change after vote"

    print("✓ test_merkle_chain_integrity PASSED")


def test_vote_replacement():
    """An agent changing their vote replaces the previous vote."""
    ledger = SwarmLedger()

    prop = ledger.propose("Switch to Rust", "Rewrite in Rust",
                          proposed_by="Dev1", quorum=QuorumType.SIMPLE_MAJORITY)

    ledger.vote(prop.proposal_id, "Dev1", VotePosition.APPROVE)
    ledger.vote(prop.proposal_id, "Dev2", VotePosition.ABSTAIN)
    assert ledger.get_tally(prop.proposal_id)["approve"] == 1
    assert ledger.get_tally(prop.proposal_id)["abstain"] == 1

    # Dev2 changes vote
    ledger.vote(prop.proposal_id, "Dev2", VotePosition.APPROVE, "Changed my mind")
    tally = ledger.get_tally(prop.proposal_id)
    assert tally["approve"] == 2
    assert tally["abstain"] == 0
    assert tally["total"] == 2

    resolution, _ = ledger.resolve(prop.proposal_id)
    assert resolution == "approved"

    print("✓ test_vote_replacement PASSED")


# ── Run ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_propose_and_vote()
    test_supermajority()
    test_unanimous()
    test_designated_approver()
    test_delegation_lifecycle()
    test_dissent_recording()
    test_ledger_summary()
    test_merkle_chain_integrity()
    test_vote_replacement()
    print("\n🎉 ALL SWARM CONSENSUS TESTS PASSED")
