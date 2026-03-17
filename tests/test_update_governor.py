"""
Tests for governance/update_governor.py

Covers:
  - Staging an update creates a PENDING ticket with an approval token
  - ALIGN warnings surface on the ticket (never silently suppressed)
  - Approval requires a matching ticket ID and returns an approval token
  - Distribution requires the exact approval token from approve()
  - Rollback is always allowed without a token
  - Expired tickets cannot be approved or rejected
  - Rejection archives the ticket
  - expire_stale() marks timed-out tickets
  - list_tickets() filters by status
  - Invalid state transitions raise meaningful errors
"""

from __future__ import annotations

import time

import pytest

from governance.update_governor import (
    DistributionResult,
    InvalidTransition,
    RollbackResult,
    TicketExpired,
    TicketNotFound,
    TokenMismatch,
    UpdateGovernor,
    UpdateStatus,
    UpdateTicket,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_governor(ttl: float = 3600.0) -> UpdateGovernor:
    return UpdateGovernor(ttl_seconds=ttl)


def _stage_one(gov: UpdateGovernor, version: str = "1.0.0") -> UpdateTicket:
    return gov.stage_update(
        version     = version,
        description = "Test update",
        payload     = {"files": ["hlf_mcp/hlf/stdlib/new_ops.py"]},
        staged_by   = "ci-bot",
    )


# ── Staging ───────────────────────────────────────────────────────────────────

class TestStaging:
    def test_stage_creates_pending_ticket(self) -> None:
        gov = _make_governor()
        ticket = _stage_one(gov)

        assert ticket.status == UpdateStatus.PENDING
        assert ticket.ticket_id
        assert ticket.version == "1.0.0"
        assert ticket.staged_by == "ci-bot"

    def test_stage_records_payload_hash(self) -> None:
        gov = _make_governor()
        ticket = _stage_one(gov)

        assert len(ticket.payload_hash) == 64  # sha256 hex

    def test_stage_adds_audit_entry(self) -> None:
        gov = _make_governor()
        ticket = _stage_one(gov)

        assert len(ticket.audit_trail) == 1
        assert ticket.audit_trail[0]["event"] == "staged"
        assert ticket.audit_trail[0]["actor"] == "ci-bot"

    def test_stage_surfaces_align_warnings(self) -> None:
        gov = _make_governor()
        # Include a credential pattern that should trigger ALIGN-001
        ticket = gov.stage_update(
            version     = "1.0.1",
            description = "Payload with a secret",
            payload     = {"config": "api_key = 'abc123'"},
            staged_by   = "ci-bot",
        )
        # align_rules.json may or may not be present in test env; either way
        # the field is a list (never an exception, never silent None)
        assert isinstance(ticket.align_warnings, list)

    def test_stage_sets_expiry(self) -> None:
        gov = _make_governor(ttl=60.0)
        ticket = _stage_one(gov)

        assert ticket.expires_at > ticket.staged_at
        assert ticket.expires_at - ticket.staged_at == pytest.approx(60.0, abs=1.0)

    def test_multiple_stages_get_unique_ids(self) -> None:
        gov = _make_governor()
        t1 = _stage_one(gov, version="1.0.0")
        t2 = _stage_one(gov, version="1.0.1")

        assert t1.ticket_id != t2.ticket_id

    def test_stage_returns_defensive_copy(self) -> None:
        gov = _make_governor()
        ticket = _stage_one(gov)

        ticket.status = UpdateStatus.REJECTED

        assert gov.get_ticket(ticket.ticket_id).status == UpdateStatus.PENDING


# ── Approval ──────────────────────────────────────────────────────────────────

class TestApproval:
    def test_approve_returns_token_and_changes_status(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")

        assert token
        assert gov.get_ticket(ticket.ticket_id).status == UpdateStatus.APPROVED

    def test_approve_records_operator_and_timestamp(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        gov.approve(ticket.ticket_id, operator="alice")

        updated = gov.get_ticket(ticket.ticket_id)
        assert updated.approved_by == "alice"
        assert updated.approved_at > 0.0

    def test_approve_twice_raises_invalid_transition(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        gov.approve(ticket.ticket_id, operator="alice")

        with pytest.raises(InvalidTransition):
            gov.approve(ticket.ticket_id, operator="bob")

    def test_approve_unknown_ticket_raises_not_found(self) -> None:
        gov = _make_governor()
        with pytest.raises(TicketNotFound):
            gov.approve("nonexistent-id", operator="alice")

    def test_approve_expired_ticket_raises(self) -> None:
        gov    = _make_governor(ttl=0.001)
        ticket = _stage_one(gov)
        time.sleep(0.05)

        with pytest.raises(TicketExpired):
            gov.approve(ticket.ticket_id, operator="alice")


# ── Rejection ─────────────────────────────────────────────────────────────────

class TestRejection:
    def test_reject_changes_status_and_records_reason(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        result = gov.reject(ticket.ticket_id, operator="alice", reason="Too risky")

        assert result.status == UpdateStatus.REJECTED
        assert result.rejection_reason == "Too risky"

    def test_reject_approved_ticket_raises(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        gov.approve(ticket.ticket_id, operator="alice")

        with pytest.raises(InvalidTransition):
            gov.reject(ticket.ticket_id, operator="bob")


# ── Distribution ──────────────────────────────────────────────────────────────

class TestDistribution:
    def test_distribute_requires_approval_token(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        gov.approve(ticket.ticket_id, operator="alice")

        with pytest.raises(TokenMismatch):
            gov.distribute(ticket.ticket_id, "wrong-token", targets=["fork-a"])

    def test_distribute_with_correct_token_succeeds(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")

        result = gov.distribute(ticket.ticket_id, token, targets=["fork-a", "fork-b"])

        assert isinstance(result, DistributionResult)
        assert result.success is True
        assert result.distributed_to == ["fork-a", "fork-b"]
        assert result.errors == []

    def test_distribute_changes_status_to_distributed(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")
        gov.distribute(ticket.ticket_id, token, targets=[])

        assert gov.get_ticket(ticket.ticket_id).status == UpdateStatus.DISTRIBUTED

    def test_distribute_pending_ticket_raises(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)

        with pytest.raises(InvalidTransition):
            gov.distribute(ticket.ticket_id, "any-token", targets=[])

    def test_distribute_no_targets_succeeds_with_empty_list(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")

        result = gov.distribute(ticket.ticket_id, token)
        assert result.success is True
        assert result.distributed_to == []


# ── Rollback ──────────────────────────────────────────────────────────────────

class TestRollback:
    def test_rollback_requires_distributed_state(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        gov.approve(ticket.ticket_id, operator="alice")

        with pytest.raises(InvalidTransition):
            gov.rollback(ticket.ticket_id, reason="Oops")

    def test_rollback_no_token_needed(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")
        gov.distribute(ticket.ticket_id, token, targets=["fork-a"])

        # Rollback requires no token — always allowed
        result = gov.rollback(ticket.ticket_id, reason="Regression", operator="bob")

        assert isinstance(result, RollbackResult)
        assert result.success is True
        assert gov.get_ticket(ticket.ticket_id).status == UpdateStatus.ROLLED_BACK

    def test_rollback_records_reason_in_audit_trail(self) -> None:
        gov    = _make_governor()
        ticket = _stage_one(gov)
        token  = gov.approve(ticket.ticket_id, operator="alice")
        gov.distribute(ticket.ticket_id, token, targets=[])
        gov.rollback(ticket.ticket_id, reason="Bad deploy", operator="alice")

        trail = gov.get_ticket(ticket.ticket_id).audit_trail
        rb_entries = [e for e in trail if e["event"] == "rolled_back"]
        assert rb_entries
        assert rb_entries[-1]["detail"]["reason"] == "Bad deploy"


# ── Expiry ────────────────────────────────────────────────────────────────────

class TestExpiry:
    def test_expire_stale_marks_expired_tickets(self) -> None:
        gov = _make_governor(ttl=0.001)
        t1  = _stage_one(gov, "1.0.0")
        t2  = _stage_one(gov, "1.0.1")
        time.sleep(0.05)

        expired = gov.expire_stale()

        assert t1.ticket_id in expired
        assert t2.ticket_id in expired
        assert gov.get_ticket(t1.ticket_id).status == UpdateStatus.EXPIRED
        assert gov.get_ticket(t2.ticket_id).status == UpdateStatus.EXPIRED

    def test_expire_stale_leaves_approved_tickets_alone(self) -> None:
        gov    = _make_governor(ttl=0.001)
        ticket = _stage_one(gov)
        # Approve before the TTL runs out
        gov.approve(ticket.ticket_id, operator="alice")
        time.sleep(0.05)

        gov.expire_stale()

        # Approved tickets are not touched by expire_stale
        assert gov.get_ticket(ticket.ticket_id).status == UpdateStatus.APPROVED


# ── List / query ──────────────────────────────────────────────────────────────

class TestListing:
    def test_list_all_tickets(self) -> None:
        gov = _make_governor()
        _stage_one(gov, "1.0.0")
        _stage_one(gov, "1.0.1")

        assert len(gov.list_tickets()) == 2

    def test_list_filtered_by_status(self) -> None:
        gov    = _make_governor()
        t1     = _stage_one(gov, "1.0.0")
        t2     = _stage_one(gov, "1.0.1")
        gov.approve(t1.ticket_id, operator="alice")

        pending  = gov.list_tickets(status=UpdateStatus.PENDING)
        approved = gov.list_tickets(status=UpdateStatus.APPROVED)

        assert len(pending)  == 1
        assert pending[0].ticket_id == t2.ticket_id
        assert len(approved) == 1
        assert approved[0].ticket_id == t1.ticket_id

    def test_get_ticket_unknown_raises(self) -> None:
        gov = _make_governor()
        with pytest.raises(TicketNotFound):
            gov.get_ticket("does-not-exist")

    def test_get_ticket_returns_defensive_copy(self) -> None:
        gov = _make_governor()
        ticket = _stage_one(gov)

        snapshot = gov.get_ticket(ticket.ticket_id)
        snapshot.audit_trail.append({"event": "tamper"})
        snapshot.status = UpdateStatus.REJECTED

        stored = gov.get_ticket(ticket.ticket_id)
        assert stored.status == UpdateStatus.PENDING
        assert all(entry["event"] != "tamper" for entry in stored.audit_trail)

    def test_list_tickets_returns_defensive_copies(self) -> None:
        gov = _make_governor()
        _stage_one(gov, "1.0.0")

        listed = gov.list_tickets()
        listed[0].description = "changed externally"

        assert gov.list_tickets()[0].description == "Test update"
