from __future__ import annotations

import json
import uuid

from hlf_mcp import server


def _subject(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def test_low_confidence_negative_observation_stays_healthy() -> None:
    subject_agent_id = _subject("low-confidence")

    result = server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="entropy_drift",
        severity="critical",
        confidence=0.2,
        witness_id="sentinel",
        evidence_text="weak signal only",
    )

    assert result["status"] == "ok"
    assert result["trust_state"]["trust_state"] == "healthy"
    assert result["trust_state"]["negative_observation_count"] == 0


def test_repeated_negative_observations_transition_to_probation() -> None:
    subject_agent_id = _subject("probation")

    first = server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="entropy_drift",
        severity="warning",
        confidence=0.9,
        witness_id="sentinel",
        evidence_text="semantic drift observed",
    )
    second = server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="verification_failure",
        severity="warning",
        confidence=0.85,
        witness_id="scribe",
        evidence_text="counterexample not resolved",
    )
    status = server.REGISTERED_TOOLS["hlf_witness_status"](subject_agent_id)

    assert first["trust_state"]["trust_state"] == "watched"
    assert second["trust_state"]["trust_state"] == "probation"
    assert status["status"] == "ok"
    assert status["witness_status"]["subject"]["trust_state"] == "probation"


def test_multi_witness_correlated_evidence_can_reach_restricted() -> None:
    subject_agent_id = _subject("restricted")

    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="align_violation",
        severity="critical",
        confidence=0.95,
        witness_id="sentinel",
        evidence_text="blocked ALIGN payload",
    )
    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="entropy_drift",
        severity="warning",
        confidence=0.9,
        witness_id="scribe",
        evidence_text="meaning drift exceeded threshold",
    )
    third = server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="verification_failure",
        severity="critical",
        confidence=0.8,
        witness_id="sentinel",
        evidence_text="formal proof failed repeatedly",
    )
    listing = server.REGISTERED_TOOLS["hlf_witness_list"](trust_state="restricted")

    assert third["trust_state"]["trust_state"] == "restricted"
    assert listing["status"] == "ok"
    assert any(subject["subject_agent_id"] == subject_agent_id for subject in listing["subjects"])


def test_witness_resource_and_tool_contracts_are_operator_legible() -> None:
    subject_agent_id = _subject("resource")

    recorded = server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="routing_anomaly",
        severity="warning",
        confidence=0.88,
        witness_id="router",
        evidence_text="fallback lane selected unexpectedly",
        event_ref={"kind": "routing_decision", "event_id": "route-1", "trace_id": "trace-1"},
    )
    resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/witness_governance/{subject_agent_id}"](
            subject_agent_id
        )
    )

    assert recorded["observation"]["evidence_hash"]
    assert recorded["governance_event"]["event"]["kind"] == "witness_observation"
    assert recorded["memory_record"]["entry_kind"] == "witness_observation"
    assert resource["status"] == "ok"
    assert resource["persona_review_summary"]["pending_gate_count"] >= 0
    assert resource["witness_status"]["subject"]["subject_agent_id"] == subject_agent_id
    assert (
        resource["witness_status"]["recent_observations"][0]["event_ref"]["event_id"] == "route-1"
    )
