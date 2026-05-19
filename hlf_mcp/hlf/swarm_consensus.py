"""
HLF Swarm Consensus — delegation, dissent, and consensus primitives.

Provides structured, append-only governance primitives that plug into
SwarmOrchestrator and agent_spawner. Every decision is tracked, every
delegation is followed through to completion, every dissent is recorded
with a reason.

Design principles:
- Append-only: once recorded, a delegation/vote/dissent is immutable
- Merkle-chained: each entry extends the previous hash, enabling audit
- Quorum-aware: consensus thresholds are configurable per proposal type
- Lane-aware: leverages the governance lane classifier from agent_spawner
"""

from __future__ import annotations

import hashlib
import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Enums ─────────────────────────────────────────────────────────────────

class VotePosition(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"
    RECUSE = "recuse"


class QuorumType(str, Enum):
    SIMPLE_MAJORITY = "simple_majority"        # > 50%
    SUPERMAJORITY = "supermajority"            # >= 67%
    UNANIMOUS = "unanimous"                    # 100%
    ANY_APPROVAL = "any_approval"              # any single approve wins
    DESIGNATED_APPROVER = "designated_approver"  # specific agent must approve


class DelegationStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass
class Delegation:
    """A formal delegation of work from one agent to another."""
    delegation_id: str
    from_agent: str
    to_agent: str
    task: str
    constraints: list[str] = field(default_factory=list)
    priority: int = 0  # higher = more urgent
    status: DelegationStatus = DelegationStatus.PROPOSED
    result: str = ""
    proposed_at_ns: int = 0
    accepted_at_ns: int = 0
    completed_at_ns: int = 0
    parent_chain_hash: str = ""

    def __post_init__(self):
        self.proposed_at_ns = self.proposed_at_ns or time.time_ns()


@dataclass
class Vote:
    """A single agent's vote on a proposal."""
    vote_id: str
    proposal_id: str
    voter_agent: str
    position: VotePosition
    reason: str = ""
    confidence: float = 1.0  # 0.0-1.0
    voted_at_ns: int = 0

    def __post_init__(self):
        self.voted_at_ns = self.voted_at_ns or time.time_ns()


@dataclass
class DissentRecord:
    """A formal record of disagreement with a proposal or decision."""
    dissent_id: str
    proposal_id: str
    dissenter_agent: str
    reason: str
    counter_proposal: str = ""  # what the dissenter proposes instead
    severity: str = "standard"  # standard | blocking | safety
    recorded_at_ns: int = 0

    def __post_init__(self):
        self.recorded_at_ns = self.recorded_at_ns or time.time_ns()


@dataclass
class Proposal:
    """A decision point in the swarm."""
    proposal_id: str
    title: str
    description: str
    proposed_by: str
    quorum: QuorumType = QuorumType.SIMPLE_MAJORITY
    designated_approver: str = ""  # for DESIGNATED_APPROVER quorum
    status: str = "open"  # open | resolved | deadlocked | superseded
    resolution: str = ""  # "approved" | "rejected"
    resolution_reason: str = ""
    proposed_at_ns: int = 0
    resolved_at_ns: int = 0

    def __post_init__(self):
        self.proposed_at_ns = self.proposed_at_ns or time.time_ns()


# ── Core consensus ledger ─────────────────────────────────────────────────

class SwarmLedger:
    """Append-only decision log with Merkle chaining.

    Every proposal, vote, delegation, and dissent is recorded in sequence.
    Each entry extends the chain hash, enabling full audit trails.
    """

    def __init__(self, swarm_id: str = "") -> None:
        self.swarm_id = swarm_id or hashlib.sha256(
            f"swarm:{time.time_ns()}".encode()
        ).hexdigest()[:16]
        self.chain_hash = _genesis_hash(self.swarm_id)
        self.proposals: dict[str, Proposal] = {}
        self.votes: dict[str, list[Vote]] = {}  # proposal_id → votes
        self.delegations: dict[str, Delegation] = {}
        self.dissents: dict[str, list[DissentRecord]] = {}  # proposal_id → dissents
        self.events: list[dict[str, Any]] = []

    def _extend_chain(self, entry_type: str, entry_id: str, data: dict[str, Any]) -> str:
        """Record an entry in the Merkle chain, returning the new chain hash."""
        record = json.dumps({
            "type": entry_type,
            "id": entry_id,
            "data": data,
            "parent": self.chain_hash,
            "ts_ns": time.time_ns(),
        }, sort_keys=True)
        self.chain_hash = hashlib.sha256(record.encode()).hexdigest()
        self.events.append({
            "type": entry_type,
            "id": entry_id,
            "chain_hash": self.chain_hash,
            "ts_ns": time.time_ns(),
        })
        return self.chain_hash

    # ── Proposals ─────────────────────────────────────────────────────────

    def propose(
        self,
        title: str,
        description: str,
        proposed_by: str,
        quorum: QuorumType = QuorumType.SIMPLE_MAJORITY,
        designated_approver: str = "",
    ) -> Proposal:
        """Create a new proposal and record it in the ledger."""
        proposal_id = _short_hash(f"prop:{title}:{proposed_by}:{time.time_ns()}")
        proposal = Proposal(
            proposal_id=proposal_id,
            title=title,
            description=description,
            proposed_by=proposed_by,
            quorum=quorum,
            designated_approver=designated_approver,
        )
        self.proposals[proposal_id] = proposal
        self._extend_chain("proposal", proposal_id, {
            "title": title,
            "proposed_by": proposed_by,
            "quorum": quorum.value,
        })
        return proposal

    # ── Voting ─────────────────────────────────────────────────────────────

    def vote(
        self,
        proposal_id: str,
        voter_agent: str,
        position: VotePosition,
        reason: str = "",
        confidence: float = 1.0,
    ) -> Vote:
        """Record a vote on a proposal."""
        if proposal_id not in self.proposals:
            raise KeyError(f"Unknown proposal: {proposal_id}")

        vote_id = _short_hash(f"vote:{proposal_id}:{voter_agent}:{time.time_ns()}")
        vote = Vote(
            vote_id=vote_id,
            proposal_id=proposal_id,
            voter_agent=voter_agent,
            position=position,
            reason=reason,
            confidence=confidence,
        )

        if proposal_id not in self.votes:
            self.votes[proposal_id] = []
        # Replace any existing vote from same agent
        self.votes[proposal_id] = [
            v for v in self.votes[proposal_id] if v.voter_agent != voter_agent
        ]
        self.votes[proposal_id].append(vote)

        self._extend_chain("vote", vote_id, {
            "proposal_id": proposal_id,
            "voter": voter_agent,
            "position": position.value,
        })
        return vote

    def resolve(self, proposal_id: str) -> tuple[str, str]:
        """Attempt to resolve a proposal based on votes and quorum.

        Returns (resolution, reason).
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise KeyError(f"Unknown proposal: {proposal_id}")

        votes = self.votes.get(proposal_id, [])
        if not votes:
            proposal.status = "deadlocked"
            proposal.resolution = "deadlocked"
            proposal.resolution_reason = "No votes cast"
            proposal.resolved_at_ns = time.time_ns()
            return ("deadlocked", "No votes cast")

        approved = sum(1 for v in votes if v.position == VotePosition.APPROVE)
        rejected = sum(1 for v in votes if v.position == VotePosition.REJECT)
        total = len(votes)

        quorum = proposal.quorum
        resolution = "deadlocked"
        reason = ""

        if quorum == QuorumType.DESIGNATED_APPROVER:
            da_votes = [v for v in votes if v.voter_agent == proposal.designated_approver]
            if da_votes and da_votes[0].position == VotePosition.APPROVE:
                resolution, reason = "approved", f"Designated approver {proposal.designated_approver} approved"
            elif da_votes and da_votes[0].position == VotePosition.REJECT:
                resolution, reason = "rejected", f"Designated approver {proposal.designated_approver} rejected"
            else:
                resolution, reason = "deadlocked", "Designated approver has not voted"

        elif quorum == QuorumType.ANY_APPROVAL:
            if approved > 0:
                resolution, reason = "approved", "At least one approval received"
            else:
                resolution, reason = "deadlocked", "No approvals received"

        elif quorum == QuorumType.UNANIMOUS:
            if approved == total:
                resolution, reason = "approved", "Unanimous approval"
            elif rejected > 0:
                resolution, reason = "rejected", f"Rejected by {rejected} voter(s); unanimity required"
            else:
                resolution, reason = "pending", "Awaiting all votes"

        elif quorum == QuorumType.SUPERMAJORITY:
            ratio = approved / total if total > 0 else 0
            if ratio >= 0.67:
                resolution, reason = "approved", f"Supermajority ({approved}/{total} = {ratio:.0%})"
            elif rejected / total >= 0.34:
                resolution, reason = "rejected", f"Blocking minority ({rejected}/{total})"
            else:
                resolution, reason = "pending", "No supermajority yet"

        else:  # SIMPLE_MAJORITY
            if approved > total / 2:
                resolution, reason = "approved", f"Majority ({approved}/{total})"
            elif rejected >= total / 2:
                resolution, reason = "rejected", f"Majority rejected ({rejected}/{total})"
            else:
                resolution, reason = "pending", "Tied or no majority"

        if resolution in ("approved", "rejected"):
            proposal.status = "resolved"
            proposal.resolution = resolution
            proposal.resolution_reason = reason
            proposal.resolved_at_ns = time.time_ns()
            self._extend_chain("resolution", proposal_id, {
                "resolution": resolution,
                "reason": reason,
                "vote_count": total,
                "approved": approved,
                "rejected": rejected,
            })

        return (resolution, reason)

    # ── Delegations ───────────────────────────────────────────────────────

    def delegate(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        constraints: list[str] | None = None,
        priority: int = 0,
    ) -> Delegation:
        """Create a formal delegation from one agent to another."""
        delegation_id = _short_hash(f"delegate:{from_agent}→{to_agent}:{time.time_ns()}")
        delegation = Delegation(
            delegation_id=delegation_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task=task,
            constraints=constraints or [],
            priority=priority,
        )
        self.delegations[delegation_id] = delegation
        self._extend_chain("delegation", delegation_id, {
            "from": from_agent,
            "to": to_agent,
            "task": task[:120],
        })
        return delegation

    def accept_delegation(self, delegation_id: str) -> Delegation:
        """Accept a delegation (called by the receiving agent)."""
        d = self.delegations.get(delegation_id)
        if not d:
            raise KeyError(f"Unknown delegation: {delegation_id}")
        d.status = DelegationStatus.ACCEPTED
        d.accepted_at_ns = time.time_ns()
        self._extend_chain("delegation_accept", delegation_id, {})
        return d

    def complete_delegation(self, delegation_id: str, result: str) -> Delegation:
        """Mark a delegation as complete with results."""
        d = self.delegations.get(delegation_id)
        if not d:
            raise KeyError(f"Unknown delegation: {delegation_id}")
        d.status = DelegationStatus.COMPLETED
        d.result = result
        d.completed_at_ns = time.time_ns()
        self._extend_chain("delegation_complete", delegation_id, {
            "result_len": len(result),
        })
        return d

    def decline_delegation(self, delegation_id: str, reason: str = "") -> Delegation:
        """Decline a delegation."""
        d = self.delegations.get(delegation_id)
        if not d:
            raise KeyError(f"Unknown delegation: {delegation_id}")
        d.status = DelegationStatus.DECLINED
        d.result = reason
        d.completed_at_ns = time.time_ns()
        self._extend_chain("delegation_decline", delegation_id, {"reason": reason[:200]})
        return d

    # ── Dissent ───────────────────────────────────────────────────────────

    def dissent(
        self,
        proposal_id: str,
        dissenter_agent: str,
        reason: str,
        counter_proposal: str = "",
        severity: str = "standard",
    ) -> DissentRecord:
        """Record a formal dissent against a proposal."""
        dissent_id = _short_hash(f"dissent:{proposal_id}:{dissenter_agent}:{time.time_ns()}")
        record = DissentRecord(
            dissent_id=dissent_id,
            proposal_id=proposal_id,
            dissenter_agent=dissenter_agent,
            reason=reason,
            counter_proposal=counter_proposal,
            severity=severity,
        )

        if proposal_id not in self.dissents:
            self.dissents[proposal_id] = []
        self.dissents[proposal_id].append(record)

        self._extend_chain("dissent", dissent_id, {
            "proposal_id": proposal_id,
            "dissenter": dissenter_agent,
            "severity": severity,
        })
        return record

    # ── Queries ───────────────────────────────────────────────────────────

    def get_tally(self, proposal_id: str) -> dict[str, int]:
        """Get vote tally for a proposal."""
        votes = self.votes.get(proposal_id, [])
        return {
            "approve": sum(1 for v in votes if v.position == VotePosition.APPROVE),
            "reject": sum(1 for v in votes if v.position == VotePosition.REJECT),
            "abstain": sum(1 for v in votes if v.position == VotePosition.ABSTAIN),
            "recuse": sum(1 for v in votes if v.position == VotePosition.RECUSE),
            "total": len(votes),
        }

    def pending_delegations(self) -> list[Delegation]:
        """Return all delegations awaiting action."""
        return [d for d in self.delegations.values()
                if d.status in (DelegationStatus.PROPOSED, DelegationStatus.IN_PROGRESS)]

    def blocking_dissents(self, proposal_id: str) -> list[DissentRecord]:
        """Return dissents with blocking or safety severity."""
        return [d for d in self.dissents.get(proposal_id, [])
                if d.severity in ("blocking", "safety")]

    def summary(self) -> dict[str, Any]:
        """Return a summary of the ledger state."""
        open_proposals = sum(1 for p in self.proposals.values() if p.status == "open")
        resolved = sum(1 for p in self.proposals.values() if p.status == "resolved")
        pending_dels = len(self.pending_delegations())
        return {
            "swarm_id": self.swarm_id,
            "chain_hash": self.chain_hash[:16],
            "events": len(self.events),
            "proposals": len(self.proposals),
            "open_proposals": open_proposals,
            "resolved_proposals": resolved,
            "total_votes": sum(len(v) for v in self.votes.values()),
            "delegations": len(self.delegations),
            "pending_delegations": pending_dels,
            "total_dissents": sum(len(d) for d in self.dissents.values()),
        }


# ── Helpers ───────────────────────────────────────────────────────────────

def _genesis_hash(swarm_id: str) -> str:
    return hashlib.sha256(f"genesis:{swarm_id}:{time.time_ns()}".encode()).hexdigest()


def _short_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]
