from __future__ import annotations

from hlf_mcp import server
from hlf_mcp.hlf.approval_ledger import ApprovalLedger
from hlf_mcp.server_context import build_server_context


def test_server_context_emits_governance_event_with_traceable_ref() -> None:
    ctx = build_server_context()

    emitted = ctx.emit_governance_event(
        kind="memory_store",
        source="test.governance",
        action="unit_test_emit",
        subject_id="subject-1",
        goal_id="goal-1",
        details={"example": True},
    )

    assert emitted["event"]["kind"] == "memory_store"
    assert emitted["event"]["event_ref"]["event_id"]
    assert emitted["event"]["event_ref"]["trace_id"] == emitted["audit"]["trace_id"]
    assert ctx.recent_governance_events(1)[0]["action"] == "unit_test_emit"


def test_capture_validated_solution_returns_governance_event() -> None:
    ctx = build_server_context()

    result = ctx.capture_validated_solution(
        problem="broken route",
        validated_solution="use governed routing",
        domain="hlf-specific",
        solution_kind="repair-pattern",
        provenance="unit-test",
        tests=[{"name": "smoke", "passed": True}],
    )

    assert result["governance_event"]["event"]["kind"] == "validated_solution_capture"
    assert result["governance_event"]["event"]["details"]["test_count"] == 1


def test_hlf_memory_store_returns_governance_event() -> None:
    result = server.hlf_memory_store("governed fact", topic="governance-test", confidence=0.9)

    assert result["governance_event"]["event"]["kind"] == "memory_store"
    assert result["governance_event"]["event"]["details"]["pointer"] == result["pointer"]
    assert result["governance_event"]["event"]["details"]["audit_trace_id"] == result["audit"]["trace_id"]


def test_hlf_entropy_anchor_returns_governance_event() -> None:
    source = '[HLF-v3]\nSET target = "/app"\nRESULT 0 "ok"\nΩ\n'

    result = server.hlf_entropy_anchor(
        source,
        expected_intent="physically destroy the production cluster",
        threshold=0.2,
        policy_mode="high_risk_enforce",
    )

    assert result["governance_event"]["event"]["kind"] == "entropy_anchor"
    assert result["governance_event"]["event"]["status"] == "warning"
    assert result["governance_event"]["event"]["event_ref"]["trace_id"]


def test_approval_ledger_returns_governance_compatible_event_refs() -> None:
    ledger = ApprovalLedger(":memory:")

    request = ledger.ensure_request(
        capsule_id="capsule-governance-1",
        agent_id="agent-1",
        base_tier="hearth",
        requested_tier="forge",
        requirements=[{"type": "tier", "scope": "capsule", "value": "hearth->forge"}],
        approval_token="token-1",
    )

    assert request.latest_event_type == "approval_requested"
    assert request.latest_event_ref is not None
    assert request.latest_event_ref["kind"] == "approval_transition"
    assert request.latest_event_ref["trace_id"] == request.latest_trace_id
    assert request.approval_event_count == 1

    approved = ledger.decide(
        request_id=request.request_id,
        decision="approve",
        operator="operator-1",
        approval_token="token-1",
    )
    events = ledger.list_events(request.request_id)

    assert approved.latest_event_type == "approval_approved"
    assert approved.latest_event_ref is not None
    assert approved.latest_event_ref["kind"] == "approval_transition"
    assert approved.latest_event_ref["trace_id"] == approved.latest_trace_id
    assert approved.approval_event_count == 2
    assert len(events) == 2
    assert events[0]["event_type"] == "approval_requested"
    assert events[1]["event_type"] == "approval_approved"
    assert events[1]["event_ref"]["trace_id"] == events[1]["trace_id"]
