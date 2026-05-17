"""
ALIGN Live Ledger — Real-Time Safety Rule Management.

Provides a live, auditable ledger of ALIGN safety rules that can be
viewed, proposed for edit, and approved by humans in real time.

Architecture:
  Rule → Proposal (human-initiated) → Approval → Active Rule
                                     ↓ Rejection → Archived

Features:
  1. Rule CRUD with versioning (every change is tracked)
  2. Proposal workflow — edits require human approval before activation
  3. Audit trail — every rule change is logged with timestamp and author
  4. Rule evaluation — check inputs against active rules
  5. Severity levels and enforcement modes (BLOCK, WARN, LOG)

This implements the "human-in-the-loop" mandate from the ALIGN framework:
no safety rule can be silently changed by an AI agent.

Usage:
    ledger = AlignLedger()
    ledger.add_rule("no_exec", "Block direct code execution", AlignSeverity.CRITICAL)
    result = ledger.evaluate("exec(user_input)")
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── Enums ──────────────────────────────────────────────────────────────────

class AlignSeverity(Enum):
    """Severity of an ALIGN rule."""
    CRITICAL = "critical"    # Must block immediately
    HIGH = "high"            # Should block, can warn
    MEDIUM = "medium"        # Warn by default
    LOW = "low"              # Log only
    ADVISORY = "advisory"    # Informational


class EnforcementMode(Enum):
    """How a rule is enforced."""
    BLOCK = "block"     # Hard block — action is prevented
    WARN = "warn"       # Warning issued but action proceeds
    LOG = "log"         # Logged silently
    DISABLED = "disabled"  # Rule is not enforced


class ProposalStatus(Enum):
    """Status of a rule change proposal."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ─── Rule ───────────────────────────────────────────────────────────────────

@dataclass
class AlignRule:
    """A single ALIGN safety rule."""

    rule_id: str
    name: str
    description: str
    severity: AlignSeverity
    enforcement: EnforcementMode = EnforcementMode.BLOCK
    pattern: str = ""           # Regex/keyword pattern to match
    category: str = "general"
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "system"
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "enforcement": self.enforcement.value,
            "pattern": self.pattern,
            "category": self.category,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "active": self.active,
        }


# ─── Proposal ──────────────────────────────────────────────────────────────

@dataclass
class RuleProposal:
    """A proposed change to an ALIGN rule (requires human approval)."""

    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    action: str = ""            # "create", "update", "delete", "disable"
    proposed_by: str = ""
    proposed_at: float = field(default_factory=time.time)
    status: ProposalStatus = ProposalStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: float = 0.0
    changes: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    rejection_reason: str = ""

    def is_pending(self) -> bool:
        return self.status == ProposalStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "rule_id": self.rule_id,
            "action": self.action,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status.value,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "changes": self.changes,
            "reason": self.reason,
            "rejection_reason": self.rejection_reason,
        }


# ─── Audit Entry ───────────────────────────────────────────────────────────

@dataclass
class LedgerAuditEntry:
    """Audit trail entry for rule changes."""

    timestamp: float = field(default_factory=time.time)
    action: str = ""
    rule_id: str = ""
    actor: str = ""
    details: str = ""
    proposal_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "rule_id": self.rule_id,
            "actor": self.actor,
            "details": self.details,
            "proposal_id": self.proposal_id,
        }


# ─── Evaluation Result ──────────────────────────────────────────────────────

@dataclass
class EvaluationResult:
    """Result from evaluating input against ALIGN rules."""

    passed: bool
    triggered_rules: list[dict[str, Any]] = field(default_factory=list)
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blocked": self.blocked,
            "triggered_rules": self.triggered_rules,
            "warnings": self.warnings,
        }


# ─── ALIGN Ledger ──────────────────────────────────────────────────────────

class AlignLedger:
    """Live ledger for ALIGN safety rules.

    All rule changes go through a proposal→approval workflow to ensure
    human oversight. Rules cannot be silently modified by AI agents.

    Args:
        auto_approve_system: If True, system-created rules are auto-approved.
    """

    def __init__(self, *, auto_approve_system: bool = True) -> None:
        self._rules: dict[str, AlignRule] = {}
        self._proposals: dict[str, RuleProposal] = {}
        self._audit_trail: list[LedgerAuditEntry] = []
        self._auto_approve = auto_approve_system

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def active_rule_count(self) -> int:
        return sum(1 for r in self._rules.values() if r.active)

    # ── Rule Management ─────────────────────────────────────────────────

    def add_rule(
        self,
        name: str,
        description: str,
        severity: AlignSeverity,
        *,
        enforcement: EnforcementMode = EnforcementMode.BLOCK,
        pattern: str = "",
        category: str = "general",
        created_by: str = "system",
    ) -> AlignRule:
        """Add a new ALIGN rule directly (system bootstrap or approved proposal)."""
        rule_id = str(uuid.uuid4())[:8]
        rule = AlignRule(
            rule_id=rule_id,
            name=name,
            description=description,
            severity=severity,
            enforcement=enforcement,
            pattern=pattern,
            category=category,
            created_by=created_by,
        )
        self._rules[rule_id] = rule
        self._audit(
            action="rule_created",
            rule_id=rule_id,
            actor=created_by,
            details=f"Rule '{name}' created ({severity.value})",
        )
        return rule

    def get_rule(self, rule_id: str) -> AlignRule | None:
        return self._rules.get(rule_id)

    def list_rules(
        self,
        *,
        active_only: bool = False,
        category: str | None = None,
        severity: AlignSeverity | None = None,
    ) -> list[AlignRule]:
        """List rules with optional filters."""
        rules = list(self._rules.values())
        if active_only:
            rules = [r for r in rules if r.active]
        if category:
            rules = [r for r in rules if r.category == category]
        if severity:
            rules = [r for r in rules if r.severity == severity]
        return rules

    def disable_rule(self, rule_id: str, *, actor: str = "system") -> None:
        """Disable a rule (soft delete)."""
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ValueError(f"Rule not found: {rule_id}")
        rule.active = False
        rule.enforcement = EnforcementMode.DISABLED
        rule.updated_at = time.time()
        self._audit("rule_disabled", rule_id, actor, f"Rule '{rule.name}' disabled")

    def enable_rule(self, rule_id: str, *, actor: str = "system") -> None:
        """Re-enable a disabled rule."""
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ValueError(f"Rule not found: {rule_id}")
        rule.active = True
        rule.enforcement = EnforcementMode.BLOCK
        rule.updated_at = time.time()
        self._audit("rule_enabled", rule_id, actor, f"Rule '{rule.name}' re-enabled")

    # ── Proposal Workflow ────────────────────────────────────────────────

    def propose_change(
        self,
        rule_id: str,
        action: str,
        changes: dict[str, Any],
        *,
        proposed_by: str = "agent",
        reason: str = "",
    ) -> RuleProposal:
        """Propose a change to a rule (requires human approval).

        Args:
            rule_id: The rule to change.
            action: "update", "delete", "disable".
            changes: Dict of field→new_value changes.
            proposed_by: Who proposed this change.
            reason: Why this change is needed.

        Returns:
            RuleProposal in PENDING status.
        """
        if action not in ("update", "delete", "disable", "create"):
            raise ValueError(f"Invalid action: {action}")

        if action != "create" and rule_id not in self._rules:
            raise ValueError(f"Rule not found: {rule_id}")

        proposal = RuleProposal(
            rule_id=rule_id,
            action=action,
            proposed_by=proposed_by,
            changes=changes,
            reason=reason,
        )
        self._proposals[proposal.proposal_id] = proposal
        self._audit(
            "proposal_created",
            rule_id,
            proposed_by,
            f"Proposed {action} on rule '{rule_id}': {reason}",
            proposal_id=proposal.proposal_id,
        )
        return proposal

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        approved_by: str = "human",
    ) -> AlignRule | None:
        """Approve a pending proposal (human action).

        Returns the modified rule, or None if the proposal was a delete.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if not proposal.is_pending():
            raise ValueError(f"Proposal not pending: {proposal.status.value}")

        proposal.status = ProposalStatus.APPROVED
        proposal.reviewed_by = approved_by
        proposal.reviewed_at = time.time()

        rule = self._apply_proposal(proposal)

        self._audit(
            "proposal_approved",
            proposal.rule_id,
            approved_by,
            f"Approved {proposal.action} on rule '{proposal.rule_id}'",
            proposal_id=proposal_id,
        )

        return rule

    def reject_proposal(
        self,
        proposal_id: str,
        *,
        rejected_by: str = "human",
        reason: str = "",
    ) -> None:
        """Reject a pending proposal."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal not found: {proposal_id}")
        if not proposal.is_pending():
            raise ValueError(f"Proposal not pending: {proposal.status.value}")

        proposal.status = ProposalStatus.REJECTED
        proposal.reviewed_by = rejected_by
        proposal.reviewed_at = time.time()
        proposal.rejection_reason = reason

        self._audit(
            "proposal_rejected",
            proposal.rule_id,
            rejected_by,
            f"Rejected: {reason}",
            proposal_id=proposal_id,
        )

    def list_proposals(
        self,
        *,
        status: ProposalStatus | None = None,
    ) -> list[RuleProposal]:
        """List proposals, optionally filtered by status."""
        proposals = list(self._proposals.values())
        if status is not None:
            proposals = [p for p in proposals if p.status == status]
        return proposals

    def _apply_proposal(self, proposal: RuleProposal) -> AlignRule | None:
        """Apply an approved proposal to the rule set."""
        if proposal.action == "update":
            rule = self._rules[proposal.rule_id]
            for key, value in proposal.changes.items():
                if key == "severity":
                    rule.severity = AlignSeverity(value)
                elif key == "enforcement":
                    rule.enforcement = EnforcementMode(value)
                elif hasattr(rule, key):
                    setattr(rule, key, value)
            rule.version += 1
            rule.updated_at = time.time()
            return rule

        if proposal.action == "disable":
            self.disable_rule(proposal.rule_id, actor=proposal.proposed_by)
            return self._rules.get(proposal.rule_id)

        if proposal.action == "delete":
            self._rules.pop(proposal.rule_id, None)
            return None

        return None

    # ── Evaluation ──────────────────────────────────────────────────────

    def evaluate(self, input_text: str) -> EvaluationResult:
        """Evaluate input against all active ALIGN rules.

        Args:
            input_text: Text to check against rules.

        Returns:
            EvaluationResult with triggered rules and warnings.
        """
        triggered: list[dict[str, Any]] = []
        warnings: list[str] = []
        blocked = False

        for rule in self._rules.values():
            if not rule.active:
                continue
            if rule.enforcement == EnforcementMode.DISABLED:
                continue

            # Check pattern match
            if rule.pattern and rule.pattern.lower() in input_text.lower():
                triggered.append(rule.to_dict())

                if rule.enforcement == EnforcementMode.BLOCK:
                    blocked = True
                elif rule.enforcement == EnforcementMode.WARN:
                    warnings.append(f"WARN: Rule '{rule.name}' triggered")

        return EvaluationResult(
            passed=not blocked,
            triggered_rules=triggered,
            blocked=blocked,
            warnings=warnings,
        )

    # ── Audit ───────────────────────────────────────────────────────────

    def _audit(
        self,
        action: str,
        rule_id: str,
        actor: str,
        details: str,
        proposal_id: str = "",
    ) -> None:
        self._audit_trail.append(LedgerAuditEntry(
            action=action,
            rule_id=rule_id,
            actor=actor,
            details=details,
            proposal_id=proposal_id,
        ))

    def get_audit_trail(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent audit entries (newest first)."""
        entries = list(reversed(self._audit_trail))
        return [e.to_dict() for e in entries[:limit]]

    # ── Report ──────────────────────────────────────────────────────────

    def get_report(self) -> dict[str, Any]:
        by_severity: dict[str, int] = {}
        for rule in self._rules.values():
            s = rule.severity.value
            by_severity[s] = by_severity.get(s, 0) + 1

        return {
            "total_rules": self.rule_count,
            "active_rules": self.active_rule_count,
            "pending_proposals": len(self.list_proposals(status=ProposalStatus.PENDING)),
            "audit_entries": len(self._audit_trail),
            "by_severity": by_severity,
        }

    # ── Persistence ─────────────────────────────────────────────────────

    def save(self, path: Path | str) -> None:
        data = {
            "rules": {k: v.to_dict() for k, v in self._rules.items()},
            "proposals": {k: v.to_dict() for k, v in self._proposals.items()},
            "audit_trail": [e.to_dict() for e in self._audit_trail],
        }
        Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> AlignLedger:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        ledger = cls()
        for rule_id, rd in data.get("rules", {}).items():
            rule = AlignRule(
                rule_id=rd["rule_id"],
                name=rd["name"],
                description=rd["description"],
                severity=AlignSeverity(rd["severity"]),
                enforcement=EnforcementMode(rd["enforcement"]),
                pattern=rd.get("pattern", ""),
                category=rd.get("category", "general"),
                version=rd.get("version", 1),
                created_at=rd.get("created_at", 0),
                updated_at=rd.get("updated_at", 0),
                created_by=rd.get("created_by", "system"),
                active=rd.get("active", True),
            )
            ledger._rules[rule_id] = rule
        return ledger
