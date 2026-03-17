"""
HLF Update Governor — HIL-gated update staging and distribution.

Every pending update is staged, inspected against ALIGN rules, and held until
a human operator explicitly approves it.  Nothing is pushed silently.

Design guarantees (same as the Ethical Governor):
  • WARN-FIRST   — advisories surface before hard blocks.
  • TRANSPARENT  — every block names the rule that triggered it.
  • HUMAN-FIRST  — no update ships without an explicit approval token.
  • NON-SILENT   — status is always inspectable; nothing happens in the dark.
  • REVERSIBLE   — approved updates can be rolled back; rollback is audited too.

This is NOT Anthropic/Google/OpenAI-style invisible gating.
Every action is logged, every reason is cited, every decision is yours.

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ── Optional integration with existing governance assets ─────────────────────
# Imported lazily so this module is usable standalone (e.g. in tests / scripts)
# without requiring the full hlf_mcp package to be installed.

_ALIGN_JSON = Path(__file__).resolve().parent / "align_rules.json"


# ── Status enum ──────────────────────────────────────────────────────────────

class UpdateStatus(str, Enum):
    PENDING    = "pending_hil"       # staged, awaiting human approval
    APPROVED   = "approved"          # human approved, ready to distribute
    REJECTED   = "rejected"          # human rejected
    DISTRIBUTED = "distributed"      # shipped to consumers/forks
    ROLLED_BACK = "rolled_back"      # reversed after distribution
    EXPIRED    = "expired"           # approval window elapsed without decision


# ── Data types ───────────────────────────────────────────────────────────────

@dataclass
class UpdateTicket:
    """Immutable record of a staged update waiting for HIL approval."""
    ticket_id: str
    version: str
    description: str
    payload_hash: str          # sha256 of the serialised payload
    status: UpdateStatus
    staged_at: float           # Unix timestamp
    expires_at: float          # Unix timestamp — approval deadline
    staged_by: str
    payload: dict[str, Any]    # the actual update data
    align_warnings: list[str] = field(default_factory=list)
    approval_token: str = ""   # set on approval; must be presented for distribution
    approved_by: str = ""
    approved_at: float = 0.0
    rejection_reason: str = ""
    audit_trail: list[dict[str, Any]] = field(default_factory=list)

    def is_expired(self) -> bool:
        return time.time() > self.expires_at and self.status == UpdateStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id":       self.ticket_id,
            "version":         self.version,
            "description":     self.description,
            "payload_hash":    self.payload_hash,
            "status":          self.status.value,
            "staged_at":       self.staged_at,
            "expires_at":      self.expires_at,
            "staged_by":       self.staged_by,
            "align_warnings":  self.align_warnings,
            "approval_token":  self.approval_token,
            "approved_by":     self.approved_by,
            "approved_at":     self.approved_at,
            "rejection_reason": self.rejection_reason,
            "audit_trail":     self.audit_trail,
        }


@dataclass
class DistributionResult:
    """Result of distributing an approved update."""
    success: bool
    ticket_id: str
    distributed_to: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    message: str = ""


@dataclass
class RollbackResult:
    """Result of rolling back a distributed update."""
    success: bool
    ticket_id: str
    rolled_back_from: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reason: str = ""


# ── Exceptions ───────────────────────────────────────────────────────────────

class UpdateGovernorError(Exception):
    """Base error for all UpdateGovernor failures."""


class TicketNotFound(UpdateGovernorError):
    pass


class TokenMismatch(UpdateGovernorError):
    pass


class TicketExpired(UpdateGovernorError):
    pass


class InvalidTransition(UpdateGovernorError):
    pass


# ── ALIGN rule checker (lightweight, no external deps) ───────────────────────

def _load_align_rules() -> list[dict[str, Any]]:
    """Load ALIGN rules from governance/align_rules.json."""
    if not _ALIGN_JSON.exists():
        return []
    try:
        data = json.loads(_ALIGN_JSON.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("rules", [])
    except Exception:  # noqa: BLE001
        return []


def _check_align(payload: dict[str, Any]) -> list[str]:
    """
    Run ALIGN rules against the serialised payload text.

    Returns a list of warning strings (never raises; rule violations surface as
    warnings, not hard blocks, so the human operator can make the final call).
    """
    import re

    text = json.dumps(payload)
    warnings: list[str] = []
    for rule in _load_align_rules():
        pattern = rule.get("pattern", "")
        if not pattern:
            continue
        try:
            if re.search(pattern, text):
                rule_id = rule.get("id", "?")
                name    = rule.get("name", "")
                desc    = rule.get("description", "")
                action  = rule.get("action", "warn")
                prefix  = "⚠ WARN" if action == "warn" else "✗ BLOCK"
                warnings.append(f"{prefix} [{rule_id}] {name}: {desc}")
        except re.error:
            pass
    return warnings


# ── Update Governor ───────────────────────────────────────────────────────────

class UpdateGovernor:
    """
    Human-in-the-Loop gated update manager.

    Usage::

        gov = UpdateGovernor()

        # Stage an update (returns a ticket — human must approve before it ships)
        ticket = gov.stage_update(
            version="1.2.3",
            description="Add new hieroglyph bytecodes",
            payload={"files": ["hlf_mcp/hlf/stdlib/new_ops.py"]},
            staged_by="ci-bot",
        )
        print(ticket.ticket_id)   # share with approver

        # Human approves (returns approval_token needed for distribution)
        approval_token = gov.approve(ticket.ticket_id, operator="alice")

        # Distribute to consumers
        result = gov.distribute(ticket.ticket_id, approval_token, targets=["fork-a", "fork-b"])

        # Roll back if needed (no token needed — rollbacks are always allowed)
        gov.rollback(ticket.ticket_id, reason="Regression found in fork-a")
    """

    # Default approval window: 24 hours
    DEFAULT_TTL_SECONDS: float = 86_400.0

    def __init__(self, ttl_seconds: float | None = None) -> None:
        self._tickets: dict[str, UpdateTicket] = {}
        self._ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS

    # ── Staging ───────────────────────────────────────────────────────────────

    def stage_update(
        self,
        version: str,
        description: str,
        payload: dict[str, Any],
        staged_by: str = "system",
        ttl_seconds: float | None = None,
    ) -> UpdateTicket:
        """
        Stage an update for HIL approval.

        The payload is checked against ALIGN rules.  Any matches are surfaced as
        warnings on the ticket so the approver can see them — they are never
        silently suppressed, and they do not automatically block the update.

        Returns the UpdateTicket.  The ticket stays in PENDING state until a
        human calls approve() or reject().
        """
        now     = time.time()
        ttl     = ttl_seconds if ttl_seconds is not None else self._ttl
        tid     = str(uuid.uuid4())
        payload_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()

        warnings = _check_align(payload)

        ticket = UpdateTicket(
            ticket_id    = tid,
            version      = version,
            description  = description,
            payload_hash = payload_hash,
            status       = UpdateStatus.PENDING,
            staged_at    = now,
            expires_at   = now + ttl,
            staged_by    = staged_by,
            payload      = payload,
            align_warnings = warnings,
            audit_trail  = [_audit_entry("staged", staged_by, {"version": version})],
        )
        self._tickets[tid] = ticket
        return ticket

    # ── Approval / rejection ──────────────────────────────────────────────────

    def approve(self, ticket_id: str, operator: str) -> str:
        """
        Human approves a pending update.

        Returns the approval_token that must be presented to distribute().
        This decouples approval from distribution — an operator can approve
        without immediately shipping, and distribution requires presenting the
        same token they received here.
        """
        ticket = self._get_ticket(ticket_id)
        self._assert_pending(ticket)

        token = str(uuid.uuid4())
        ticket.status         = UpdateStatus.APPROVED
        ticket.approval_token = token
        ticket.approved_by    = operator
        ticket.approved_at    = time.time()
        ticket.audit_trail.append(
            _audit_entry("approved", operator, {"ticket_id": ticket_id})
        )
        return token

    def reject(self, ticket_id: str, operator: str, reason: str = "") -> UpdateTicket:
        """Human rejects a pending update.  The ticket is archived, not deleted."""
        ticket = self._get_ticket(ticket_id)
        self._assert_pending(ticket)

        ticket.status           = UpdateStatus.REJECTED
        ticket.rejection_reason = reason
        ticket.audit_trail.append(
            _audit_entry("rejected", operator, {"reason": reason})
        )
        return ticket

    # ── Distribution ─────────────────────────────────────────────────────────

    def distribute(
        self,
        ticket_id: str,
        approval_token: str,
        targets: list[str] | None = None,
    ) -> DistributionResult:
        """
        Distribute an approved update to the given targets.

        ``targets`` is a list of consumer names / fork identifiers (strings).
        If None or empty, the call succeeds with an empty distributed_to list —
        the caller is responsible for knowing their target audience.

        Raises TokenMismatch if the approval_token doesn't match what was issued
        by approve().  This ensures only the operator who approved can trigger
        distribution (or someone they explicitly gave the token to).
        """
        ticket = self._get_ticket(ticket_id)

        if ticket.status != UpdateStatus.APPROVED:
            raise InvalidTransition(
                f"Ticket {ticket_id} is in '{ticket.status.value}' state; "
                "only 'approved' tickets can be distributed."
            )
        if ticket.approval_token != approval_token:
            raise TokenMismatch(
                f"Approval token mismatch for ticket {ticket_id}. "
                "Distribution requires the token returned by approve()."
            )

        targets = targets or []
        distributed: list[str] = []
        errors: list[str] = []

        for target in targets:
            try:
                # Hook: subclasses can override _push_to_target for real delivery
                self._push_to_target(target, ticket)
                distributed.append(target)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{target}: {exc}")

        ticket.status = UpdateStatus.DISTRIBUTED
        ticket.audit_trail.append(
            _audit_entry(
                "distributed",
                ticket.approved_by,
                {"targets": distributed, "errors": errors},
            )
        )

        return DistributionResult(
            success      = len(errors) == 0,
            ticket_id    = ticket_id,
            distributed_to = distributed,
            skipped      = [],
            errors       = errors,
            message      = (
                f"Distributed v{ticket.version} to {len(distributed)} target(s)."
                + (f"  {len(errors)} error(s)." if errors else "")
            ),
        )

    # ── Rollback ─────────────────────────────────────────────────────────────

    def rollback(
        self,
        ticket_id: str,
        reason: str = "",
        operator: str = "system",
    ) -> RollbackResult:
        """
        Roll back a distributed update.

        Rollbacks are always permitted — no approval token required.
        Any operator can roll back because safety > process.
        The rollback is audited (reason + operator recorded).
        """
        ticket = self._get_ticket(ticket_id)

        if ticket.status != UpdateStatus.DISTRIBUTED:
            raise InvalidTransition(
                f"Ticket {ticket_id} is in '{ticket.status.value}' state; "
                "only 'distributed' tickets can be rolled back."
            )

        rolled_back: list[str] = []
        errors: list[str] = []

        distributed_to = [
            e["detail"].get("targets", [])
            for e in ticket.audit_trail
            if e.get("event") == "distributed"
        ]
        all_targets = [t for group in distributed_to for t in group]

        for target in all_targets:
            try:
                self._pull_from_target(target, ticket, reason)
                rolled_back.append(target)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{target}: {exc}")

        ticket.status = UpdateStatus.ROLLED_BACK
        ticket.audit_trail.append(
            _audit_entry(
                "rolled_back",
                operator,
                {"reason": reason, "targets": rolled_back, "errors": errors},
            )
        )

        return RollbackResult(
            success           = len(errors) == 0,
            ticket_id         = ticket_id,
            rolled_back_from  = rolled_back,
            errors            = errors,
            reason            = reason,
        )

    # ── Inspection ───────────────────────────────────────────────────────────

    def get_ticket(self, ticket_id: str) -> UpdateTicket:
        """Return a ticket by ID (public, read-only view)."""
        return self._get_ticket(ticket_id)

    def list_tickets(self, status: UpdateStatus | None = None) -> list[UpdateTicket]:
        """List all tickets, optionally filtered by status."""
        tickets = list(self._tickets.values())
        if status is not None:
            tickets = [t for t in tickets if t.status == status]
        return sorted(tickets, key=lambda t: t.staged_at)

    def expire_stale(self) -> list[str]:
        """
        Mark timed-out PENDING tickets as EXPIRED.

        Returns the list of ticket IDs that were expired.
        Call this periodically (e.g. from a scheduler) to keep the queue clean.
        """
        expired_ids: list[str] = []
        for ticket in self._tickets.values():
            if ticket.is_expired():
                ticket.status = UpdateStatus.EXPIRED
                ticket.audit_trail.append(
                    _audit_entry("expired", "system", {"ttl": self._ttl})
                )
                expired_ids.append(ticket.ticket_id)
        return expired_ids

    # ── Hooks (override in subclasses for real delivery) ─────────────────────

    def _push_to_target(self, target: str, ticket: UpdateTicket) -> None:
        """
        Push the approved update to a single target.

        Default implementation is a no-op (dry-run).  Override to integrate
        with your actual delivery mechanism (GitHub PR, package registry, etc.)
        """

    def _pull_from_target(self, target: str, ticket: UpdateTicket, reason: str) -> None:
        """
        Revert the update from a single target.

        Default implementation is a no-op.  Override to integrate with your
        actual rollback mechanism.
        """

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_ticket(self, ticket_id: str) -> UpdateTicket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise TicketNotFound(f"No ticket with ID '{ticket_id}'.")
        return ticket

    def _assert_pending(self, ticket: UpdateTicket) -> None:
        if ticket.is_expired():
            ticket.status = UpdateStatus.EXPIRED
            raise TicketExpired(
                f"Ticket {ticket.ticket_id} has expired "
                f"(TTL was {self._ttl}s).  Stage a new update."
            )
        if ticket.status != UpdateStatus.PENDING:
            raise InvalidTransition(
                f"Ticket {ticket.ticket_id} is already in '{ticket.status.value}' state."
            )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _audit_entry(
    event: str,
    actor: str,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event":     event,
        "actor":     actor,
        "timestamp": time.time(),
        "detail":    detail or {},
    }
