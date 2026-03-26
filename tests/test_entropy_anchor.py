from __future__ import annotations

import uuid

from hlf_mcp import server
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.entropy_anchor import evaluate_entropy_anchor

COMPILER = HLFCompiler()


def _program(body: str) -> str:
    return f"[HLF-v3]\n{body}\nΩ\n"


def test_entropy_anchor_passes_with_packaged_human_readable_baseline() -> None:
    source = _program('SET target = "/app"\nRESULT 0 "ok"')
    ast = COMPILER.compile(source)["ast"]

    result = evaluate_entropy_anchor(source=source, ast=ast)

    assert result.status == "ok"
    assert result.baseline_source == "compiler_human_readable"
    assert result.drift_detected is False
    assert result.policy_action == "allow"
    assert result.similarity_score >= result.threshold


def test_entropy_anchor_flags_mismatch_for_explicit_intent() -> None:
    source = _program('SET target = "/app"\nRESULT 0 "ok"')
    ast = COMPILER.compile(source)["ast"]

    result = evaluate_entropy_anchor(
        source=source,
        ast=ast,
        expected_intent="physically destroy the production cluster",
        threshold=0.2,
        policy_mode="high_risk_enforce",
    )

    assert result.drift_detected is True
    assert result.policy_action == "halt_branch"
    assert result.similarity_score < result.threshold


def test_hlf_entropy_anchor_tool_returns_audited_structured_result() -> None:
    source = _program('SET target = "/app"\nRESULT 0 "ok"')

    result = server.hlf_entropy_anchor(
        source,
        expected_intent="physically destroy the production cluster",
        threshold=0.2,
        policy_mode="high_risk_enforce",
    )

    assert result["status"] == "ok"
    assert result["anchor"]["drift_detected"] is True
    assert result["anchor"]["policy_action"] == "halt_branch"
    assert result["audit"]["event"] == "entropy_anchor_evaluated"
    assert any(
        entry["event"] == "entropy_anchor_evaluated"
        and entry["data"]["source_hash"] == result["anchor"]["source_hash"]
        for entry in server._ctx.audit_chain.recent(10)
    )


def test_hlf_entropy_anchor_can_emit_witness_observation_for_subject() -> None:
    source = _program('SET target = "/app"\nRESULT 0 "ok"')
    subject_agent_id = f"entropy-subject-{uuid.uuid4().hex}"

    result = server.hlf_entropy_anchor(
        source,
        expected_intent="physically destroy the production cluster",
        threshold=0.2,
        policy_mode="high_risk_enforce",
        subject_agent_id=subject_agent_id,
    )

    assert result["status"] == "ok"
    assert result["subject_agent_id"] == subject_agent_id
    assert result["witness_observation"] is not None
    assert result["witness_observation"]["status"] == "ok"
    assert result["witness_observation"]["observation"]["category"] == "entropy_drift"
    assert result["witness_observation"]["observation"]["event_ref"]["kind"] == "entropy_anchor"
    assert result["witness_observation"]["trust_state"]["trust_state"] == "watched"
