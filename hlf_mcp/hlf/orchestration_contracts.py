"""
Orchestration Contracts — explicit delegation, dissent, escalation, and handoff
contracts for multi-agent orchestration.

Provides:
  - DelegationContract: validates and records delegation of scope to a delegate
  - DissentRecord: captures agent dissent with configurable escalation levels
  - EscalationPath: defines escalation routing with severity-based auto-escalation
  - HandoffContract: formalises context transfer between agents with lineage tracking

Integration points:
  - hlf_mcp.instinct.orchestration: PlanStepContract, ExecutionTraceEntry
  - hlf_mcp.hlf.swarm_handoff: SwarmHandoffContract for swarm-level handoffs
  - hlf_mcp.hlf.orchestration_failure_recovery: VectorClock for causal ordering
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# DelegationContract — scope delegation with constraint validation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DelegationContract:
    """A validated delegation of scope from a delegator to a delegate.

    Enforces Ж constraints: delegate must differ from delegator, scope must be
    non-empty, and at least one constraint must be specified.

    Attributes:
        delegator: The agent or role delegating authority.
        delegate: The agent or role receiving the delegated scope.
        scope: A description of what is being delegated.
        constraints: Ж-constraint strings that bound the delegation.
        handoff_lineage: Ordered chain of delegations leading to this one.
        is_valid: Whether the delegation passed all validation checks.
        failures: Human-readable descriptions of validation failures.
    """

    delegator: str
    delegate: str
    scope: str
    constraints: list[str] = field(default_factory=list)
    handoff_lineage: list[str] = field(default_factory=list)
    is_valid: bool = True
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "delegator": self.delegator,
            "delegate": self.delegate,
            "scope": self.scope,
            "constraints": list(self.constraints),
            "handoff_lineage": list(self.handoff_lineage),
            "is_valid": self.is_valid,
            "failures": list(self.failures),
        }


# ---------------------------------------------------------------------------
# DissentRecord — agent dissent with escalation levels
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DissentRecord:
    """A formal record of agent dissent against an orchestration decision.

    Escalation levels:
      0 — note: informational, no action required
      1 — flag: attention requested, but execution may proceed
      2 — block: execution MUST halt; auto-escalates to escalation path

    Attributes:
        agent: The dissenting agent identifier.
        reason: Human-readable reason for the dissent.
        evidence: Supporting evidence (logs, metrics, counterexamples).
        proposed_alternative: Optional alternative course of action.
        escalation_level: 0=note, 1=flag, 2=block.
        is_resolved: Whether the dissent has been addressed and closed.
    """

    agent: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    proposed_alternative: str | None = None
    escalation_level: int = 0
    is_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "proposed_alternative": self.proposed_alternative,
            "escalation_level": self.escalation_level,
            "is_resolved": self.is_resolved,
        }


# ---------------------------------------------------------------------------
# EscalationPath — routing for escalations
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class EscalationPath:
    """Defines how an escalation flows from source to target.

    Severity levels:
      - "info": logged but not routed
      - "warning": routed with manual acknowledgement expected
      - "critical": auto-escalated immediately (auto_escalate=True)

    Attributes:
        source: The agent or node initiating the escalation.
        target: The agent or role to escalate to.
        reason: Human-readable reason for escalation.
        severity: One of "info", "warning", "critical".
        auto_escalate: If True, escalation happens without human approval.
        timeout_seconds: Optional timeout after which escalation auto-fires.
    """

    source: str
    target: str
    reason: str
    severity: str = "warning"
    auto_escalate: bool = False
    timeout_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
            "severity": self.severity,
            "auto_escalate": self.auto_escalate,
            "timeout_seconds": self.timeout_seconds,
        }


# ---------------------------------------------------------------------------
# HandoffContract — formal context transfer between agents
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HandoffContract:
    """A formal contract for transferring context from one agent to another.

    Includes a context snapshot, any open decisions that need resolution,
    and a full lineage chain. Self-handoff (where from_agent appears in
    lineage) is rejected.

    Attributes:
        from_agent: The agent handing off.
        to_agent: The agent receiving the handoff.
        context_snapshot: Serialisable snapshot of current state.
        open_decisions: Decisions still pending at handoff time.
        lineage: Full handoff chain (ordered list of agent ids).
        accepted: Whether the receiving agent accepted the handoff.
        acceptance_evidence: Optional proof of acceptance.
    """

    from_agent: str
    to_agent: str
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    open_decisions: list[str] = field(default_factory=list)
    lineage: list[str] = field(default_factory=list)
    accepted: bool = False
    acceptance_evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "context_snapshot": dict(self.context_snapshot),
            "open_decisions": list(self.open_decisions),
            "lineage": list(self.lineage),
            "accepted": self.accepted,
            "acceptance_evidence": (
                dict(self.acceptance_evidence) if self.acceptance_evidence else None
            ),
        }


# ---------------------------------------------------------------------------
# Builder: validate_delegation
# ---------------------------------------------------------------------------


def validate_delegation(
    delegator: str,
    delegate: str,
    scope: str,
    constraints: list[str],
    *,
    handoff_lineage: list[str] | None = None,
) -> DelegationContract:
    """Validate and construct a DelegationContract.

    Validation rules:
      1. delegate must differ from delegator (no self-delegation)
      2. scope must be non-empty
      3. constraints must be non-empty

    Args:
        delegator: The agent delegating authority.
        delegate: The agent receiving the delegation.
        scope: Description of what is being delegated.
        constraints: Ж-constraint strings bounding the delegation.
        handoff_lineage: Optional chain of prior delegations.

    Returns:
        A DelegationContract with is_valid=True and empty failures on success,
        or is_valid=False with descriptive failures on validation error.
    """
    failures: list[str] = []

    if not delegator or not delegate:
        failures.append("Delegator and delegate must both be non-empty.")
    elif delegate == delegator:
        failures.append(
            f"Self-delegation rejected: delegator '{delegator}' cannot delegate to itself."
        )

    if not scope or not scope.strip():
        failures.append("Delegation scope must be non-empty.")

    if not constraints or len(constraints) == 0:
        failures.append("At least one constraint is required for delegation.")

    return DelegationContract(
        delegator=delegator,
        delegate=delegate,
        scope=scope,
        constraints=list(constraints),
        handoff_lineage=list(handoff_lineage) if handoff_lineage else [],
        is_valid=len(failures) == 0,
        failures=failures,
    )


# ---------------------------------------------------------------------------
# Builder: record_dissent
# ---------------------------------------------------------------------------


def record_dissent(
    agent: str,
    reason: str,
    evidence: dict[str, Any] | None = None,
    *,
    level: int = 0,
    proposed_alternative: str | None = None,
) -> DissentRecord:
    """Record a formal dissent from an agent.

    Level 2 (block) dissent indicates execution MUST halt and the dissent
    auto-escalates to the configured escalation path.

    Args:
        agent: The dissenting agent identifier.
        reason: Human-readable reason for dissent.
        evidence: Supporting evidence dict.
        level: Escalation level — 0=note, 1=flag, 2=block.
        proposed_alternative: Optional alternative course of action.

    Returns:
        A DissentRecord with the dissent details.
    """
    return DissentRecord(
        agent=agent,
        reason=reason,
        evidence=dict(evidence) if evidence else {},
        proposed_alternative=proposed_alternative,
        escalation_level=level,
        is_resolved=False,
    )


# ---------------------------------------------------------------------------
# Builder: build_escalation_path
# ---------------------------------------------------------------------------


def build_escalation_path(
    source: str,
    target: str,
    reason: str,
    severity: str = "warning",
    *,
    timeout_seconds: int | None = None,
) -> EscalationPath:
    """Build an escalation path from source to target.

    Severity determines auto-escalation behaviour:
      - "critical": auto_escalate=True (immediate escalation)
      - "warning": auto_escalate=False (manual acknowledgement expected)
      - "info": auto_escalate=False (logged but not routed)

    Args:
        source: The agent or node initiating the escalation.
        target: The agent or role to escalate to.
        reason: Human-readable reason for escalation.
        severity: One of "info", "warning", "critical".
        timeout_seconds: Optional timeout for auto-escalation.

    Returns:
        An EscalationPath configured with appropriate auto_escalate flag.
    """
    auto_escalate = severity == "critical"
    return EscalationPath(
        source=source,
        target=target,
        reason=reason,
        severity=severity,
        auto_escalate=auto_escalate,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------------
# Builder: build_handoff
# ---------------------------------------------------------------------------


def build_handoff(
    from_agent: str,
    to_agent: str,
    context: dict[str, Any] | None = None,
    lineage: list[str] | None = None,
    *,
    open_decisions: list[str] | None = None,
) -> HandoffContract:
    """Build a HandoffContract with lineage validation.

    Self-handoff is rejected: if from_agent appears anywhere in the lineage
    chain, the contract is created with accepted=False.

    Args:
        from_agent: The agent handing off.
        to_agent: The agent receiving the handoff.
        context: Serialisable snapshot of current state.
        lineage: Full handoff chain (ordered list of agent ids).
        open_decisions: Decisions still pending at handoff time.

    Returns:
        A HandoffContract. accepted=False if self-handoff is detected.
    """
    resolved_lineage = list(lineage) if lineage else []
    resolved_context = dict(context) if context else {}
    resolved_decisions = list(open_decisions) if open_decisions else []

    # Validate: no self-handoff (from_agent must not appear in lineage)
    accepted = True
    if from_agent in resolved_lineage:
        accepted = False

    # Also reject if from_agent == to_agent
    if from_agent == to_agent:
        accepted = False

    return HandoffContract(
        from_agent=from_agent,
        to_agent=to_agent,
        context_snapshot=resolved_context,
        open_decisions=resolved_decisions,
        lineage=resolved_lineage,
        accepted=accepted,
        acceptance_evidence=None,
    )


# ---------------------------------------------------------------------------
# Builder: resolve_dissent
# ---------------------------------------------------------------------------


def resolve_dissent(record: DissentRecord, resolution: str) -> DissentRecord:
    """Resolve a dissent record, marking it as resolved.

    The resolution string is stored in the evidence dict under the
    'resolution' key so the full record remains traceable.

    Args:
        record: The DissentRecord to resolve.
        resolution: Description of how the dissent was resolved.

    Returns:
        A new DissentRecord with is_resolved=True and resolution in evidence.
    """
    resolved_evidence = deepcopy(dict(record.evidence))
    resolved_evidence["resolution"] = resolution
    return DissentRecord(
        agent=record.agent,
        reason=record.reason,
        evidence=resolved_evidence,
        proposed_alternative=record.proposed_alternative,
        escalation_level=record.escalation_level,
        is_resolved=True,
    )
