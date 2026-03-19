from __future__ import annotations

import uuid

from hlf_mcp import server
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.formal_verifier import ConstraintKind, VerificationReport, VerificationResult, VerificationStatus
from hlf_mcp.hlf.memory_node import HLFPointer, build_pointer_ref, verify_pointer_ref
from hlf_mcp.hlf.runtime import _dispatch_host


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
    assert any(item["request_id"] == request["request_id"] for item in queue["requests"])

    decided = server.hlf_capsule_review_decide(
        request_id=request["request_id"],
        decision="approve",
        operator="operator",
        approval_token=request["approval_token"],
    )

    assert decided["status"] == "ok"
    assert decided["request"]["status"] == "approved"

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
    pending = server.hlf_capsule_run(
        source,
        tier="hearth",
        requested_tier="forge",
        capsule_id=capsule_id,
    )

    rejected = server.hlf_capsule_review_decide(
        request_id=pending["approval_request"]["request_id"],
        decision="approve",
        operator="operator",
        approval_token="wrong-token",
    )

    assert rejected["status"] == "error"
    assert "mismatch" in rejected["error"]


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
    result = server.hlf_capsule_run(source, tier="hearth", capsule_id=_unique_capsule_id("capsule-proof-deny"))

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
    result = server.hlf_capsule_run(source, tier="hearth", capsule_id=_unique_capsule_id("capsule-proof-allow"))

    assert result["status"] == "ok"
    assert result["verification"]["admitted"] is True
    assert result["verification"]["report"]["proven"] >= 1


def test_memory_store_returns_audit_chain_entry() -> None:
    result = server.hlf_memory_store("audited fact", topic="audit-test", confidence=0.8)

    assert result["audit"]["event"] == "hlf_memory_store"
    assert result["audit"]["trace_id"]
