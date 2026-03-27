from __future__ import annotations

import json
import uuid

from hlf_mcp import server
from hlf_mcp.hlf import build_embodied_action_envelope
from hlf_mcp.hlf.memory_node import build_pointer_ref
from hlf_mcp.hlf.runtime import _dispatch_host


def _capsule_id(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex}"


def test_host_functions_surface_embodied_contract_metadata() -> None:
    result = server.hlf_host_functions(tier="forge")

    entry = next(item for item in result["functions"] if item["name"] == "GUARDED_ACTUATE")

    assert entry["effect_class"] == "guarded_actuation"
    assert entry["safety_class"] == "critical"
    assert entry["review_posture"] == "operator_review"
    assert entry["execution_mode"] == "simulation_only"
    assert entry["supervisory_only"] is True


def test_guarded_actuate_requires_embodied_review_and_simulation_contract() -> None:
    evidence_ref = build_pointer_ref("sim-camera", "frame-001")
    agent_id = f"embodied-review-agent-{uuid.uuid4().hex}"
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_a",
        bounds={"workspace": "tray-a", "max_delta_mm": 25},
        timeout_ms=1500,
        operator_intent="simulate a bounded pick-and-place",
        execution_mode="simulation",
        evidence_refs=[evidence_ref],
    )

    pending = server.hlf_host_call(
        "GUARDED_ACTUATE",
        args_json=json.dumps([envelope, [evidence_ref], "simulate a bounded pick-and-place"]),
        tier="forge",
        agent_id=agent_id,
        capsule_id=_capsule_id("embodied-review"),
    )

    assert pending["status"] == "approval_required"
    assert pending["policy_trace"]["review_posture"] == "operator_review"
    assert pending["embodied_contract"]["simulation_only"] is True
    assert {item["type"] for item in pending["approval_requirements"]} == {"embodied_review"}
    assert pending["execution_admission"]["embodied_effect"]["function_name"] == "GUARDED_ACTUATE"
    assert pending["execution_admission"]["verification"]["embodied_summary"]["bounded_spatial_envelope"] is True
    categories = {
        item["observation"]["category"]
        for item in pending["execution_admission"].get("witness_observations", [])
    }
    assert "embodied_review_required" in categories
    witness_status = server._ctx.get_witness_status(subject_agent_id=agent_id)
    assert witness_status is not None
    assert witness_status["subject"]["subject_agent_id"] == agent_id


def test_guarded_actuate_rejects_missing_pointer_evidence() -> None:
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_a",
        bounds={"workspace": "tray-a", "max_delta_mm": 25},
        timeout_ms=1500,
        operator_intent="simulate a bounded pick-and-place",
        execution_mode="simulation",
    )

    rejected = server.hlf_host_call(
        "GUARDED_ACTUATE",
        args_json=json.dumps([envelope, [], "simulate a bounded pick-and-place"]),
        tier="forge",
    )

    assert rejected["status"] == "embodied_contract_violation"
    assert any("evidence_refs" in reason for reason in rejected["violations"])


def test_runtime_dispatch_returns_simulation_only_embodied_result() -> None:
    evidence_ref = build_pointer_ref("sim-camera", "frame-002")
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_b",
        bounds={"workspace": "tray-b", "max_delta_mm": 15},
        timeout_ms=1200,
        operator_intent="simulate a constrained move",
        execution_mode="simulation",
        evidence_refs=[evidence_ref],
    )

    side_effects: list[dict[str, object]] = []
    result = _dispatch_host(
        "GUARDED_ACTUATE",
        [envelope, [evidence_ref], "simulate a constrained move"],
        {"_tier": "forge"},
        side_effects,
    )

    assert result["status"] == "simulation_only"
    assert result["host_fn"] == "GUARDED_ACTUATE"
    assert result["operator_review_required"] is True
    assert any(event["type"] == "embodied_simulation" for event in side_effects)


def test_runtime_dispatch_denies_embodied_function_below_forge_tier() -> None:
    evidence_ref = build_pointer_ref("sim-camera", "frame-003")
    envelope = build_embodied_action_envelope(
        requested_action="move_sample",
        target_frame="tray_c",
        bounds={"workspace": "tray-c", "max_delta_mm": 10},
        timeout_ms=900,
        operator_intent="attempt a constrained move from hearth",
        execution_mode="simulation",
        evidence_refs=[evidence_ref],
    )

    side_effects: list[dict[str, object]] = []
    result = _dispatch_host(
        "GUARDED_ACTUATE",
        [envelope, [evidence_ref], "attempt a constrained move from hearth"],
        {"_tier": "hearth"},
        side_effects,
    )

    assert result["status"] == "error"
    assert "hearth" in result["error"]
    assert any(event["type"] == "host_error" for event in side_effects)


def test_capsule_denied_tools_blocks_dispatch() -> None:
    """Capsule denied_tools enforcement at runtime rejects blocked functions."""
    capsule_dict = {
        "capsule_id": _capsule_id("deny-test"),
        "denied_tools": ["hash_sha256"],
        "allowed_tools": [],
    }
    side_effects: list[dict[str, object]] = []
    result = _dispatch_host(
        "hash_sha256",
        ["test-data"],
        {"_capsule": capsule_dict},
        side_effects,
    )

    assert result["status"] == "error"
    assert "denies" in result["error"].lower()
    assert any(event["type"] == "host_error" for event in side_effects)


def test_capsule_denied_tools_allows_non_denied_function() -> None:
    """Functions NOT in denied_tools proceed normally even with capsule active."""
    capsule_dict = {
        "capsule_id": _capsule_id("allow-test"),
        "denied_tools": ["spawn_agent"],
        "allowed_tools": [],
    }
    side_effects: list[dict[str, object]] = []
    result = _dispatch_host(
        "hash_sha256",
        ["test-data"],
        {"_capsule": capsule_dict},
        side_effects,
    )

    # hash_sha256 is not denied, so it should succeed
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest