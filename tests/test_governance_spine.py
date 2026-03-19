from __future__ import annotations

from hlf_mcp.server_context import build_server_context
from hlf_mcp import server


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