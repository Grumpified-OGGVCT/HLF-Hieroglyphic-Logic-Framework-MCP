from __future__ import annotations

import json
import uuid

from hlf_mcp import server
from hlf_mcp.hlf.align_governor import AlignVerdict
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
)
from hlf_mcp.hlf.memory_node import HLFPointer, build_pointer_ref, verify_pointer_ref
from hlf_mcp.hlf.runtime import _dispatch_host
from hlf_mcp.server_capsule import _build_execution_admission_record


def _unique_capsule_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def test_pointer_helper_round_trip_with_content_binding() -> None:
    pointer = HLFPointer.from_content(alias="design-doc", content="trusted payload")

    result = verify_pointer_ref(
        pointer.pointer,
        registry_entry=pointer.to_registry_entry(),
    )

    assert result["status"] == "ok"
    assert result["alias"] == "design-doc"
    assert result["resolved_value"] == "trusted payload"


def test_capsule_validate_ast_blocks_untrusted_pointer_literal() -> None:
    capsule = capsule_for_tier("forge")
    ast = [{"kind": "value", "tag": "SOURCE", "target": build_pointer_ref("spec", "payload")}]

    violations = capsule.validate_ast(ast)

    assert violations
    assert "Untrusted pointer" in violations[0]


def test_runtime_analyze_rejects_untrusted_pointer_when_enforced() -> None:
    pointer = build_pointer_ref("ops-log", "sensitive-content")
    side_effects: list[dict[str, object]] = []

    result = _dispatch_host(
        "analyze",
        [pointer],
        {"_pointer_trust_mode": "enforce", "_trusted_pointers": {}},
        side_effects,
    )

    assert result["status"] == "error"
    assert "Pointer trust failed" in result["error"]
    assert any(event.get("type") == "pointer_validation" for event in side_effects)


def test_runtime_analyze_accepts_registered_pointer_and_uses_content() -> None:
    pointer = HLFPointer.from_content(alias="ops-log", content="error: disk full")
    side_effects: list[dict[str, object]] = []

    result = _dispatch_host(
        "analyze",
        [pointer.pointer],
        {
            "_pointer_trust_mode": "enforce",
            "_trusted_pointers": {pointer.pointer: pointer.to_registry_entry()},
        },
        side_effects,
    )

    assert result["analyzed"] == "error: disk full"
    assert result["content_preview"].startswith("error: disk full")
    ok_event = next(event for event in side_effects if event.get("type") == "pointer_validation")
    assert ok_event["status"] == "ok"


def test_runtime_analyze_rejects_pointer_for_routing_evidence_without_provenance() -> None:
    pointer = HLFPointer.from_content(alias="routing-hint", content="prefer cloud")
    side_effects: list[dict[str, object]] = []

    def resolver(value: str, **_: object) -> dict[str, object]:
        return {
            "status": "blocked",
            "admitted": False,
            "pointer": value,
            "purpose": "routing_evidence",
            "trust_tier": "local",
            "governance_status": "active",
            "freshness_status": "fresh",
            "reason": "evidence_backed_provenance_required",
            "resolved_value": "prefer cloud",
            "resolution": {"verification": {"alias": "routing-hint"}},
        }

    result = _dispatch_host(
        "analyze",
        [pointer.pointer],
        {
            "_pointer_trust_mode": "enforce",
            "_pointer_resolution_purpose": "routing_evidence",
            "_pointer_resolver": resolver,
        },
        side_effects,
    )

    assert result["status"] == "error"
    assert "evidence_backed_provenance_required" in result["error"]
    failed_event = next(event for event in side_effects if event.get("type") == "pointer_validation")
    assert failed_event["purpose"] == "routing_evidence"
    assert failed_event["reason"] == "evidence_backed_provenance_required"


def test_memory_store_returns_pointer_contract() -> None:
    result = server.hlf_memory_store("trusted fact", topic="routing", confidence=0.9)

    assert result["stored"] is True
    assert result["pointer"].startswith("&routing-")
    assert result["pointer_entry"]["content_hash"] == result["sha256"]


def test_pointer_validate_tool_reports_hash_mismatch() -> None:
    pointer = build_pointer_ref("policy", "expected content")

    result = server.hlf_pointer_validate(pointer, content="different content")

    assert result["status"] == "hash_mismatch"
    assert result["reason"] == "content_hash_mismatch"


def test_capsule_validate_requires_approval_for_tier_escalation() -> None:
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="execute"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-bridge-1")

    result = server.hlf_capsule_validate(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    assert result["passed"] is False
    assert result["approval_required"] is True
    assert result["approval_requirements"][0]["type"] == "tier_escalation"
    assert result["approval_token"]


def test_capsule_validate_accepts_matching_approval_for_tier_escalation() -> None:
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="execute"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-bridge-2")
    pending = server.hlf_capsule_validate(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    approved = server.hlf_capsule_validate(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
        approved_by="operator",
        approval_token=pending["approval_token"],
    )

    assert approved["passed"] is True
    assert approved["approval_granted"] is True
    assert approved["capsule"]["requested_tier"] == "forge"


def test_capsule_run_returns_structured_approval_required_status() -> None:
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="execute"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-bridge-3")

    result = server.hlf_capsule_run(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    assert result["status"] == "approval_required"
    assert result["requested_tier"] == "forge"
    assert result["approval_requirements"][0]["value"] == "hearth->forge"
    assert result["approval_request"]["status"] == "pending"


def test_capsule_review_queue_persists_and_approves_request() -> None:
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="execute"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-review-queue-1")

    pending = server.hlf_capsule_run(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    request = pending["approval_request"]
    queue = server.hlf_capsule_review_queue(status="pending", capsule_id=capsule_id)

    assert queue["status"] == "ok"
    assert queue["count"] >= 1
    assert request["latest_event_ref"]["kind"] == "approval_transition"
    assert any(item["request_id"] == request["request_id"] for item in queue["requests"])

    decided = server.hlf_capsule_review_decide(
        request_id=request["request_id"],
        decision="approve",
        operator="operator",
        approval_token=request["approval_token"],
    )

    assert decided["status"] == "ok"
    assert decided["request"]["status"] == "approved"
    assert decided["request"]["latest_event_type"] == "approval_approved"
    assert decided["request"]["latest_event_ref"]["kind"] == "approval_transition"

    rerun = server.hlf_capsule_run(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    assert rerun["status"] == "ok"
    assert rerun["approval_request"]["status"] == "approved"


def test_capsule_review_decide_rejects_bad_token() -> None:
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="execute"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-review-queue-2")
    agent_id = f"approval-bypass-{uuid.uuid4().hex}"
    pending = server.hlf_capsule_run(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
        agent_id=agent_id,
    )

    rejected = server.hlf_capsule_review_decide(
        request_id=pending["approval_request"]["request_id"],
        decision="approve",
        operator="operator",
        approval_token="wrong-token",
    )

    witness_status = server.REGISTERED_TOOLS["hlf_witness_status"](agent_id)

    assert rejected["status"] == "error"
    assert "mismatch" in rejected["error"]
    assert rejected["error_details"]["reason_code"] == "approval_token_mismatch"
    assert rejected["bypass_record"] is not None
    assert (
        rejected["bypass_record"]["witness_observation"]["observation"]["category"]
        == "approval_bypass_attempt"
    )
    assert witness_status["witness_status"]["subject"]["trust_state"] == "watched"


def test_host_call_requires_and_accepts_tier_escalation_approval() -> None:
    capsule_id = _unique_capsule_id("capsule-bridge-4")
    pending = server.hlf_host_call(
        "HTTP_GET",
        args_json='["https://example.com"]',
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    assert pending["status"] == "approval_required"
    assert pending["policy_trace"]["effect_class"] == "network_read"
    assert pending["policy_trace"]["failure_type"] == "network_error"

    approved = server.hlf_host_call(
        "HTTP_GET",
        args_json='["https://example.com"]',
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
        approved_by="operator",
        approval_token=pending["approval_token"],
    )

    assert approved["status"] == "ok"
    assert approved["result"]["tier"] == "forge"
    assert approved["policy_trace"]["audit_requirement"] == "standard"


def test_runtime_execution_returns_audit_chain_entries() -> None:
    source = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\nЖ [ASSERT] status="ok"\n∇ [RESULT] message="sealed"\nΩ\n'
    capsule_id = _unique_capsule_id("capsule-audit-run-1")

    result = server.hlf_capsule_run(
        source,
        tier="hearth",
        capsule_id=capsule_id,
    )

    assert result["status"] == "ok"
    assert result["audit"]["execution"] is not None
    assert result["audit"]["execution"]["trace_id"]


def test_persist_execution_admission_records_pointer_trust_failure() -> None:
    agent_id = f"pointer-witness-{uuid.uuid4().hex}"
    pointer = build_pointer_ref("ops-log", "sensitive-content")
    capsule = capsule_for_tier(
        "hearth",
        agent_id=agent_id,
        capsule_id=_unique_capsule_id("capsule-pointer-witness"),
        pointer_trust_mode="enforce",
    )
    verification = {
        "verdict": "verification_ok",
        "admitted": True,
        "requires_operator_review": False,
        "reasons": [],
        "effect_summary": {
            "effectful": True,
            "node_count": 1,
            "effectful_tags": [],
            "tools": ["analyze"],
        },
    }
    side_effects: list[dict[str, object]] = []
    dispatch_result = _dispatch_host(
        "analyze",
        [pointer],
        {"_pointer_trust_mode": "enforce", "_trusted_pointers": {}},
        side_effects,
    )
    result = server._ctx.persist_execution_admission(
        agent_id=agent_id,
        admission_record=_build_execution_admission_record(
            server._ctx,
            agent_id=agent_id,
            capsule=capsule,
            verification=verification,
            execution_status="error",
            approval_requirements=[],
            approval_request=None,
            execution_audit=None,
            side_effects=side_effects,
            runtime_variables=None,
        ),
    )
    witness_status = server.REGISTERED_TOOLS["hlf_witness_status"](agent_id)

    assert dispatch_result["status"] == "error"
    assert "Pointer trust failed" in dispatch_result["error"]
    assert result["pointer_evidence"]["failure_count"] == 1
    assert result["pointer_evidence"]["failures"][0]["status"] == "untrusted"
    assert any(
        observation["observation"]["category"] == "pointer_trust_failure"
        for observation in result["witness_observations"]
    )
    assert witness_status["witness_status"]["subject"]["trust_state"] == "watched"


def test_capsule_run_persists_execution_admission_into_governed_route() -> None:
    server.hlf_hks_capture(
        problem="Explain route and proof posture.",
        validated_solution="Use admitted governed routing evidence for the final capsule execution.",
        domain="hlf-specific",
        solution_kind="repair-pattern",
        tags=["route-proof-join"],
        tests=[{"name": "pytest", "passed": True, "exit_code": 0, "counts": {"passed": 1}}],
        source="tests.test_capsule_pointer_trust",
        artifact_path="artifact:route-proof-join",
    )
    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_english",
        benchmark_scores={"routing_quality": 0.82},
        topic="execution-admission-route",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.9},
        topic="execution-admission-sidecar",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.92},
        topic="execution-admission-verifier",
        languages=["en"],
    )
    server.hlf_sync_model_catalog(
        agent_id="execution-admission-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    server.hlf_route_governed_request(
        payload="Explain route and proof posture.",
        workload="agent_routing_context",
        agent_id="execution-admission-agent",
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    result = server.hlf_capsule_run(
        '[HLF-v3]\nΔ [INTENT] goal="route-proof-join"\n∇ [RESULT] message="joined"\nΩ\n',
        tier="hearth",
        agent_id="execution-admission-agent",
        capsule_id=_unique_capsule_id("capsule-route-join"),
    )

    assert result["status"] == "ok"
    assert result["execution_admission"]["route_evidence"]["available"] is True
    assert result["execution_admission"]["route_evidence"]["selected_lane"]
    assert result["execution_admission"]["audit_refs"]["execution_trace_id"]
    assert (
        result["execution_admission"]["governance_event"]["event"]["kind"] == "verification_result"
    )


def test_capsule_run_denies_elevated_execution_without_admitted_hks_contract() -> None:
    unique = uuid.uuid4().hex[:8]
    agent_id = f"knowledge-gate-agent-{unique}"

    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_english",
        benchmark_scores={"routing_quality": 0.82},
        topic=f"knowledge-gate-route-{unique}",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.9},
        topic=f"knowledge-gate-sidecar-{unique}",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.92},
        topic=f"knowledge-gate-verifier-{unique}",
        languages=["en"],
    )
    server.hlf_sync_model_catalog(
        agent_id=agent_id,
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    route = server.hlf_route_governed_request(
        payload=f"Elevated execution without admitted HKS contract {unique}",
        workload="agent_routing_context",
        agent_id=agent_id,
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    result = server.hlf_capsule_run(
        '[HLF-v3]\nRESULT "joined"\nΩ\n',
        tier="hearth",
        requested_tier="forge",
        agent_id=agent_id,
        capsule_id=_unique_capsule_id("capsule-knowledge-gate"),
    )

    assert route["knowledge_contract"]["admitted"] is False
    assert result["status"] == "knowledge_denied"
    assert result["execution_admission"]["knowledge_gate"]["decision"] == "deny"
    assert result["execution_admission"]["verification"]["verdict"] == "knowledge_denied"


def test_capsule_run_persists_delegation_and_handoff_lineage() -> None:
    mission_id = f"mission-{uuid.uuid4().hex}"
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="specify",
        payload={"topic": "delegate execution lineage"},
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="plan",
        payload={
            "task_dag": [
                {
                    "node_id": "delegate",
                    "task_type": "delegate_task",
                    "assigned_role": "orchestrator",
                    "delegated_to": "scribe",
                },
                {
                    "node_id": "verify",
                    "task_type": "run_tests",
                    "depends_on": ["delegate"],
                    "assigned_role": "verifier",
                    "escalation_role": "sentinel",
                },
            ]
        },
    )
    server.hlf_instinct_step(
        mission_id=mission_id,
        phase="execute",
        payload={
            "execution_trace": [
                {
                    "node_id": "delegate",
                    "success": True,
                    "duration_ms": 9.0,
                    "delegated_to": "scribe",
                    "verification_status": "passed",
                },
                {
                    "node_id": "verify",
                    "success": True,
                    "duration_ms": 12.0,
                    "escalation_role": "sentinel",
                    "verification_status": "passed",
                },
            ]
        },
    )

    result = server.hlf_capsule_run(
        '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="summarize release notes"\nΩ\n',
        tier="hearth",
        requested_tier="forge",
        agent_id="lineage-agent",
        capsule_id=_unique_capsule_id("capsule-lineage"),
        variables_json=f'{{"MISSION_ID": "{mission_id}"}}',
    )

    assert result["status"] == "approval_required"

    approved = server.hlf_capsule_review_decide(
        request_id=result["approval_request"]["request_id"],
        decision="approve",
        operator="operator",
        approval_token=result["approval_request"]["approval_token"],
    )

    assert approved["status"] == "ok"

    result = server.hlf_capsule_run(
        '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="summarize release notes"\nΩ\n',
        tier="hearth",
        requested_tier="forge",
        agent_id="lineage-agent",
        capsule_id=result["capsule"]["capsule_id"],
        variables_json=f'{{"MISSION_ID": "{mission_id}"}}',
    )

    lineage = result["execution_admission"]["orchestration_lineage"]

    assert result["status"] == "ok"
    assert lineage["contract_version"] == "1.0"
    assert lineage["delegation_events"][0]["agent"] == "scribe"
    assert lineage["delegation_events"][0]["task_id"]
    assert lineage["mission"]["mission_id"] == mission_id
    assert lineage["mission"]["execution_summary"]["delegated_nodes"] == 1
    assert lineage["mission"]["execution_summary"]["escalated_nodes"] == 1
    assert lineage["mission"]["orchestration_contract"]["summary"]["all_nodes_allowed"] is True
    assert lineage["mission"]["orchestration_contract"]["summary"]["handoff_nodes"] == 2
    assert lineage["mission"]["orchestration_contract"]["summary"]["persona_bound_nodes"] == 2
    assert lineage["mission"]["orchestration_contract"]["summary"]["persona_bindings"]["scribe"] == 1
    assert lineage["mission"]["orchestration_contract"]["summary"]["persona_bindings"]["sentinel"] == 1
    assert len(lineage["mission"]["handoff_trace"]) == 2
    assert lineage["mission"]["handoff_plan"][0]["delegated_persona"]["persona"] == "scribe"
    assert lineage["mission"]["handoff_trace"][0]["delegated_persona"]["persona"] == "scribe"
    assert lineage["mission"]["handoff_trace"][1]["escalation_persona"]["persona"] == "sentinel"


def test_capsule_run_denies_when_verifier_finds_counterexample(monkeypatch) -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="bad_window",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.RANGE_CHECK,
            message="window escaped permitted range",
        )
    )
    monkeypatch.setattr(server._ctx.formal_verifier, "verify_constraints", lambda ast: report)

    source = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\n∇ [RESULT] message="sealed"\nΩ\n'
    result = server.hlf_capsule_run(
        source, tier="hearth", capsule_id=_unique_capsule_id("capsule-proof-deny")
    )

    assert result["status"] == "verification_denied"
    assert result["verification"]["verdict"] == "verification_denied"
    assert result["verification"]["report"]["failed"] == 1


def test_capsule_run_allows_when_verifier_proves_packaged_constraints(monkeypatch) -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="typed_value",
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.TYPE_INVARIANT,
            message="typed value proven",
        )
    )
    monkeypatch.setattr(server._ctx.formal_verifier, "verify_constraints", lambda ast: report)

    source = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\n∇ [RESULT] message="sealed"\nΩ\n'
    result = server.hlf_capsule_run(
        source, tier="hearth", capsule_id=_unique_capsule_id("capsule-proof-allow")
    )

    assert result["status"] == "ok"
    assert result["verification"]["admitted"] is True
    assert result["verification"]["report"]["proven"] >= 1


def test_capsule_run_routes_verifier_review_into_approval_and_witness_status(monkeypatch) -> None:
    agent_id = f"governed-flow-{uuid.uuid4().hex}"
    capsule_id = _unique_capsule_id("capsule-governed-flow")

    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_english",
        benchmark_scores={"routing_quality": 0.82},
        topic="governed-flow-route",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.9},
        topic="governed-flow-sidecar",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.92},
        topic="governed-flow-verifier",
        languages=["en"],
    )

    monkeypatch.setattr(
        server._ctx.align_governor,
        "evaluate",
        lambda payload: AlignVerdict(
            allowed=True,
            status="warning",
            action="ROUTE_TO_HUMAN_APPROVAL",
            subject_hash="sentinel-review",
            decisive_rule_id="align-human-review",
            decisive_rule_name="Human Review Required",
            decisive_rule_action="ROUTE_TO_HUMAN_APPROVAL",
            matches=[],
            loaded_rule_count=1,
        ),
    )

    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="proof_gap",
            status=VerificationStatus.UNKNOWN,
            kind=ConstraintKind.CUSTOM,
            message="proof coverage incomplete",
        )
    )
    monkeypatch.setattr(server._ctx.formal_verifier, "verify_constraints", lambda ast: report)

    server.hlf_sync_model_catalog(
        agent_id=agent_id,
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    route = server.hlf_route_governed_request(
        payload="Explain route, proof, and approval posture.",
        workload="agent_routing_context",
        agent_id=agent_id,
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )

    result = server.hlf_capsule_run(
        '[HLF-v3]\nΔ [INTENT] goal="governed-flow"\n∇ [RESULT] message="pending review"\nΩ\n',
        tier="hearth",
        agent_id=agent_id,
        capsule_id=capsule_id,
    )
    approval_detail = json.loads(
        server.REGISTERED_RESOURCES["hlf://status/approval_queue/{request_id}"](
            result["approval_request"]["request_id"]
        )
    )
    witness_status = server.REGISTERED_TOOLS["hlf_witness_status"](agent_id)

    requirement_types = {
        requirement["type"]
        for requirement in result["approval_requirements"]
        if isinstance(requirement, dict)
    }

    assert route["routing_verdict"]["review_required"] is True
    assert route["routing_verdict"]["governance_mode"] == "human_approval_required"
    assert result["status"] == "approval_required"
    assert result["execution_admission"]["route_evidence"]["review_required"] is True
    assert result["execution_admission"]["verification"]["verdict"] == "verification_review_required"
    assert requirement_types == {"route_review", "verification_review"}
    assert len(result["execution_admission"]["witness_observations"]) == 2
    assert witness_status["witness_status"]["subject"]["trust_state"] in {"probation", "restricted"}
    assert approval_detail["approval_request"]["request_id"] == result["approval_request"]["request_id"]
    assert {
        requirement["type"]
        for requirement in approval_detail["approval_request"]["requirements"]
    } == {"route_review", "verification_review"}


def test_capsule_run_denies_when_restricted_witness_state_blocks_routing() -> None:
    agent_id = f"capsule-restricted-{uuid.uuid4().hex}"
    capsule_id = _unique_capsule_id("capsule-restricted")

    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=agent_id,
        category="align_violation",
        severity="critical",
        confidence=0.95,
        witness_id="sentinel",
        evidence_text="blocked ALIGN payload",
    )
    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=agent_id,
        category="entropy_drift",
        severity="warning",
        confidence=0.9,
        witness_id="scribe",
        evidence_text="meaning drift exceeded threshold",
    )
    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=agent_id,
        category="verification_failure",
        severity="critical",
        confidence=0.8,
        witness_id="sentinel",
        evidence_text="formal proof failed repeatedly",
    )

    server.hlf_record_benchmark_artifact(
        profile_name="agent_routing_context_english",
        benchmark_scores={"routing_quality": 0.82},
        topic="capsule-restricted-route",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="sidecar_quality_explainer",
        benchmark_scores={"sidecar_quality": 0.9},
        topic="capsule-restricted-sidecar",
        languages=["en"],
    )
    server.hlf_record_benchmark_artifact(
        profile_name="verifier_accuracy_multilingual",
        benchmark_scores={"verifier_accuracy": 0.92},
        topic="capsule-restricted-verifier",
        languages=["en"],
    )

    route = server.hlf_route_governed_request(
        payload="Explain the governed routing posture for a restricted capsule run.",
        workload="agent_routing_context",
        agent_id=agent_id,
        agent_role="researcher",
        runtime_status={
            "ollama_available": True,
            "installed_models": ["qwen3:8b"],
            "recommended_model_runnable": True,
            "fallback_model_runnable": False,
        },
        hardware_summary={"cpu_only": False, "gpu_vram_gb": 16.0},
    )
    result = server.hlf_capsule_run(
        '[HLF-v3]\nΔ [INTENT] goal="restricted-route"\n∇ [RESULT] message="blocked"\nΩ\n',
        tier="hearth",
        agent_id=agent_id,
        capsule_id=capsule_id,
    )

    assert route["routing_verdict"]["governance_mode"] == "trust_restricted"
    assert result["status"] == "route_denied"
    assert result["verification"]["verdict"] == "route_denied"
    assert any("restricted trust states" in reason.lower() for reason in result["reasons"])
    assert result["execution_admission"]["route_evidence"]["decision"] == "deny"


def test_memory_store_returns_audit_chain_entry() -> None:
    result = server.hlf_memory_store("audited fact", topic="audit-test", confidence=0.8)

    assert result["audit"]["event"] == "hlf_memory_store"
    assert result["audit"]["trace_id"]


def test_governed_recall_pointer_resolution_and_capsule_trust_interact_deterministically() -> None:
    unique = uuid.uuid4().hex
    stored = server.hlf_hks_capture(
        problem=f"How to stabilize governed recall {unique}",
        validated_solution="Use the validated exemplar contract.",
        domain="hlf-specific",
        solution_kind="repair-pattern",
        tags=[unique],
        tests=[{"name": "pytest", "passed": True, "exit_code": 0, "counts": {"passed": 1}}],
        source="tests.test_capsule_pointer_trust",
        artifact_path=f"artifact:{unique}",
    )
    pointer = f"&hlf_validated_exemplars-{stored['id']}:SHA256:{stored['sha256']}"

    recalled = server.hlf_governed_recall(
        unique,
        top_k=5,
        domain="hlf-specific",
        solution_kind="repair-pattern",
        include_weekly_artifacts=False,
    )
    resolved = server.hlf_memory_resolve(pointer, purpose="execution")
    capsule = capsule_for_tier(
        "forge",
        pointer_trust_mode="enforce",
        trusted_pointers={
            pointer: {
                "content_hash": stored["sha256"],
                "content": resolved["resolved_value"],
                "trust_tier": "validated",
            }
        },
    )
    side_effects: list[dict[str, object]] = []
    dispatch = _dispatch_host(
        "analyze",
        [pointer],
        {
            "_pointer_trust_mode": capsule.pointer_trust_mode,
            "_trusted_pointers": capsule.trusted_pointers,
            "_pointer_resolver": server._ctx.resolve_memory_pointer,
            "_pointer_resolution_purpose": "execution",
        },
        side_effects,
    )

    assert recalled["count"] >= 1
    assert any(result["sha256"] == stored["sha256"] for result in recalled["results"])
    assert resolved["status"] == "ok"
    assert resolved["admitted"] is True
    assert capsule.validate_ast([{"kind": "value", "tag": "SOURCE", "target": pointer}]) == []
    assert "validated exemplar contract" in dispatch["analyzed"]
    ok_event = next(event for event in side_effects if event.get("type") == "pointer_validation")
    assert ok_event["status"] == "ok"
