from __future__ import annotations

import json
import uuid

from hlf_mcp import server


def test_record_delegate_handoff_event_exposes_required_hashes_and_bounds() -> None:
    event = server.hlf_record_handoff_event(
        delegator="agent-a",
        delegate="agent-b",
        scope="proof-surface/orchestration",
        constraints={"preserve_scope": True, "no_dsl": True},
        delegation_gas_ceiling=250,
        deadline="2026-05-09T00:00:00Z",
        epoch="epoch-1",
        event_type="delegate",
        claim_lane="implementation",
        proof_boundary={"claim": "handoff primitive only"},
        payload={"task": "implement primitive"},
        vm_gas_limit=999,
    )

    assert event["status"] == "ok"
    assert event["event_type"] == "delegate"
    assert event["delegator"] == "agent-a"
    assert event["delegate"] == "agent-b"
    assert event["scope"] == "proof-surface/orchestration"
    assert event["parent_event_hash"] == ""
    assert event["event_hash"]
    assert event["payload_hash"]
    assert event["lineage_hash"]
    assert event["gas_bounds"]["delegation_gas_ceiling"] == 250
    assert event["gas_bounds"]["vm_gas_limit"] == 999
    assert event["gas_bounds"]["separate_delegation_gas_from_vm_gas"] is True
    assert event["proof_boundary"]["framework_or_dsl"] is False
    assert event["proof_boundary"]["bft_consensus"] is False


def test_handoff_chain_accepts_vote_dissent_progress_variants_without_new_grammar() -> None:
    root = server.hlf_record_handoff_event(
        delegator="agent-a",
        delegate="agent-b",
        scope="scope-vote-chain",
        constraints={"review": "required"},
        delegation_gas_ceiling=50,
        event_type="delegate",
        payload={"proposal": "do-work"},
    )
    vote = server.hlf_record_handoff_event(
        delegator="agent-b",
        delegate="agent-a",
        scope="scope-vote-chain",
        constraints={"review": "payload-variant"},
        delegation_gas_ceiling=10,
        event_type="vote",
        claim_lane="review",
        payload={"vote": "approve"},
        parent_event_hash=root["event_hash"],
    )
    dissent = server.hlf_record_handoff_event(
        delegator="agent-c",
        delegate="agent-a",
        scope="scope-vote-chain",
        constraints={"review": "payload-variant"},
        delegation_gas_ceiling=10,
        event_type="dissent",
        claim_lane="review",
        payload={"dissent": "scope risk", "attestation": "signed"},
        parent_event_hash=vote["event_hash"],
    )
    progress = server.hlf_record_handoff_event(
        delegator="agent-b",
        delegate="agent-a",
        scope="scope-vote-chain",
        constraints={"progress": "payload-variant"},
        delegation_gas_ceiling=5,
        event_type="progress",
        claim_lane="status",
        payload={"percent": 40},
        parent_event_hash=dissent["event_hash"],
    )

    chain = server.hlf_handoff_chain(progress["event_hash"])

    assert chain["status"] == "ok"
    assert chain["verification_summary"]["verified"] is True
    assert chain["verification_summary"]["event_type_counts"]["vote"] >= 1
    assert chain["verification_summary"]["event_type_counts"]["dissent"] >= 1
    assert chain["verification_summary"]["event_type_counts"]["progress"] >= 1
    assert chain["verification_summary"]["attestable_disagreement_events"] >= 2
    assert chain["verification_summary"]["bft_consensus"] is False
    assert all(event["proof_boundary"]["grammar_extension"] is False for event in chain["handoff_chain"])


def test_handoff_hash_chain_continuity_and_resources_report_latest_chain() -> None:
    first = server.hlf_record_handoff_event(
        delegator="chain-a",
        delegate="chain-b",
        scope="scope-continuity",
        constraints={},
        delegation_gas_ceiling=100,
        event_type="delegate",
        payload={"step": 1},
    )
    second = server.hlf_record_handoff_event(
        delegator="chain-b",
        delegate="chain-c",
        scope="scope-continuity",
        constraints={},
        delegation_gas_ceiling=100,
        event_type="complete",
        payload={"step": 2},
        parent_event_hash=first["event_hash"],
    )

    chain = server.hlf_handoff_chain(second["event_hash"])
    status_resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/handoff_chain"]())
    report_resource = server.REGISTERED_RESOURCES["hlf://reports/handoff_chain"]()
    schema_resource = json.loads(server.REGISTERED_RESOURCES["hlf://schema/handoff_event"]())

    assert chain["verification_summary"]["verified"] is True
    assert chain["handoff_chain"][0]["event_hash"] == first["event_hash"]
    assert chain["handoff_chain"][1]["parent_event_hash"] == first["event_hash"]
    assert status_resource["verification_summary"]["lineage_model"] == "linear_handoff_chain_v1"
    assert "Merkle" in status_resource["lineage_model"]["merkle_upgrade_path"]
    assert "not a choreography DSL" in report_resource
    assert schema_resource["$id"] == "hlf-handoff-event-v1"
    assert "event_hash" in schema_resource["required"]


def test_non_hlf_json_payload_is_accepted_as_conformant_event_schema() -> None:
    event = server.hlf_record_handoff_event(
        delegator="external-agent",
        delegate="hlf-agent",
        scope="json-interop",
        constraints={"schema": "json"},
        delegation_gas_ceiling=25,
        event_type="progress",
        payload_json='{"external": true, "status": "working"}',
        source_agent_kind="non_hlf",
    )

    assert event["status"] == "ok"
    assert event["payload"] == {"external": True, "status": "working"}
    assert event["external_agent_conformance"]["schema"] == "hlf-handoff-event-v1"
    assert event["external_agent_conformance"]["json_conformant"] is True
    assert event["external_agent_conformance"]["hlf_native"] is False
    assert event["external_agent_conformance"]["payload_acceptance"]["source"] == "payload_json"


def test_orchestration_contract_preserves_plan_order_dependencies_and_merge_gate() -> None:
    mission_id = f"orchestration-{uuid.uuid4().hex}"
    contract = server.hlf_orchestration_contract(
        task_dag=[
            {"node_id": "verify", "task_type": "verify", "depends_on": ["plan"]},
            {"node_id": "spec", "task_type": "specify"},
            {"node_id": "plan", "task_type": "plan", "depends_on": ["spec"]},
        ],
        execution_trace=[
            {"node_id": "spec", "success": True, "verification_status": "passed"},
            {"node_id": "plan", "success": True, "verification_status": "passed"},
            {"node_id": "verify", "success": True, "verification_status": "passed"},
        ],
    )
    skip = server.hlf_instinct_step(
        mission_id=mission_id,
        phase="execute",
        payload={},
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="specify",
        payload={"topic": "orchestration contract"},
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="plan",
        payload={"task_dag": contract["task_dag"]},
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="execute",
        payload={"execution_trace": contract["execution_trace"]},
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="verify",
        payload={"verdict": "FAILED"},
    )
    merge_block = server.hlf_instinct_step(
        mission_id=mission_id,
        phase="merge",
        payload={},
    )
    orchestration_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/orchestration/{mission_id}"](mission_id)
    )

    assert contract["status"] == "ok"
    assert [step["node_id"] for step in contract["task_dag"]] == ["spec", "plan", "verify"]
    assert contract["task_dag"][2]["depends_on"] == ["plan"]
    assert contract["execution_summary"]["all_nodes_recorded"] is True
    assert skip["status"] == "error"
    assert "New mission must start" in skip["error"]
    assert merge_block["status"] == "blocked"
    assert orchestration_resource["status"] == "ok"
    assert orchestration_resource["contract_surfaces"]["merge_gate"] == "verify→merge remains CoVE-gated"


def test_handoff_progress_vote_dissent_templates_and_semantic_drift_resources() -> None:
    root = server.hlf_record_handoff_event(
        delegator="planner",
        delegate="executor",
        scope="review-board-scope",
        constraints={"must_preserve": ["bounded coordination substrate"]},
        delegation_gas_ceiling=100,
        event_type="delegate",
        lifecycle_phase="plan",
        payload={"intent": "Implement bounded coordination substrate without deleting JSON interop"},
    )
    vote = server.hlf_record_handoff_event(
        delegator="reviewer-a",
        delegate="planner",
        scope="review-board-scope",
        constraints={"review_board": "rb-1"},
        delegation_gas_ceiling=10,
        event_type="vote",
        lifecycle_phase="verify",
        parent_event_hash=root["event_hash"],
        payload={"vote": "approve", "rationale": "bounded contract preserved"},
    )
    progress = server.hlf_record_handoff_event(
        delegator="executor",
        delegate="planner",
        scope="review-board-scope",
        constraints={"progress": True},
        delegation_gas_ceiling=10,
        event_type="progress",
        lifecycle_phase="execute",
        parent_event_hash=vote["event_hash"],
        payload={"percent": 60},
    )
    complete = server.hlf_record_handoff_event(
        delegator="executor",
        delegate="planner",
        scope="review-board-scope",
        constraints={"result": True},
        delegation_gas_ceiling=10,
        event_type="complete",
        lifecycle_phase="merge",
        parent_event_hash=progress["event_hash"],
        original_intent="Implement bounded coordination substrate without deleting JSON interop",
        delegate_result="Deleted JSON interop and replaced the coordination substrate with a new swarm DSL",
        payload={"result": "new swarm DSL"},
    )
    template = server.hlf_handoff_contract_template(
        template="review_board",
        scope="review-board-scope",
        participants=["planner", "executor", "reviewer-a"],
    )
    drift = server.hlf_handoff_semantic_drift_check(
        original_intent="Preserve JSON handoff interop",
        delegate_result="Replace interop with a new DSL",
    )
    progress_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/handoff_progress/{event_hash}"](
            complete["event_hash"]
        )
    )
    schema = json.loads(server.REGISTERED_RESOURCES["hlf://schema/handoff_event"]())
    templates = json.loads(
        server.REGISTERED_RESOURCES["hlf://schema/handoff_contract_templates"]()
    )

    assert root["$type"] == "hlf://schema/handoff_event"
    assert vote["proof_boundary"]["attestable_disagreement"] is True
    assert template["status"] == "ok"
    assert template["event_contract"]["requires_hlf_compilation"] is False
    assert "review_board" in templates["templates"]
    assert drift["semantic_drift"]["drift_detected"] is True
    assert complete["semantic_drift"]["drift_detected"] is True
    assert progress_resource["status"] == "ok"
    assert len(progress_resource["progress_events"]) == 1
    assert progress_resource["verification_summary"]["lifecycle_phase_counts"]["merge"] >= 1
    assert progress_resource["verification_summary"]["semantic_drift_events"] >= 1
    assert "$type" in schema["required"]


def test_route_handoff_linkage_resource_joins_route_profile_and_handoff_lineage() -> None:
    agent_id = f"route-link-{uuid.uuid4().hex[:8]}"
    server._ctx.persist_governed_route(
        {
            "request_context": {"agent_id": agent_id},
            "operator_summary": "test route linkage",
            "route_decision": {
                "decision": "allow",
                "selected_lane": "explainer",
                "primary_model": "qwen3:8b",
                "fallback_model": "all-minilm",
                "denial_reasons": [],
            },
            "policy_basis": {"policy_basis_present": True, "policy_constraints": ["allowlist"]},
        }
    )
    event = server.hlf_record_handoff_event(
        delegator=agent_id,
        delegate="worker",
        scope="route-linkage",
        constraints={"route_required": True},
        delegation_gas_ceiling=20,
        event_type="delegate",
        lifecycle_phase="execute",
        route_trace_ref={"agent_id": agent_id, "resource": f"hlf://status/governed_route/{agent_id}"},
        payload={"intent": "link route to handoff"},
    )
    linkage = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/route_handoff_linkage/{agent_id}"](agent_id)
    )

    assert event["route_trace_ref"]["agent_id"] == agent_id
    assert linkage["status"] == "ok"
    assert linkage["route_selection"]["selected_lane"] == "explainer"
    assert linkage["handoff_lineage"]["verification_summary"]["verified"] is True
    assert linkage["proof_boundary"]["new_router_runtime"] is False
