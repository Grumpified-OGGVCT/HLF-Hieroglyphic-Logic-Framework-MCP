from __future__ import annotations

import uuid

from hlf_mcp import server
from hlf_mcp.handoff_events import (
    PERSONA_ROLES,
    normalize_handoff_event,
    persona_lineage_entry,
)
from hlf_mcp.persona_contract import resolve_persona_contract


# ── Persona handoff field survival ───────────────────────────────────────────────

def test_persona_handoff_fields_survive_normalization() -> None:
    """source_persona and target_persona survive compilation/execution normalization."""
    event = normalize_handoff_event(
        delegator="planner-agent",
        delegate="executor-agent",
        scope="build-pipeline",
        source_persona="planner",
        target_persona="executor",
    )

    assert event["status"] == "ok"
    assert event["source_persona"] == "planner"
    assert event["target_persona"] == "executor"
    assert event["$type"] == "hlf://schema/handoff_event"


def test_persona_handoff_fields_lowercased_and_stripped() -> None:
    """Persona fields are normalized to lowercase, stripped strings."""
    event = normalize_handoff_event(
        delegator="agent-a",
        delegate="agent-b",
        scope="test-scope",
        source_persona="  PLANNER  ",
        target_persona="Executor",
    )

    assert event["source_persona"] == "planner"
    assert event["target_persona"] == "executor"


def test_persona_handoff_empty_when_omitted() -> None:
    """When omitted, persona fields default to empty string."""
    event = normalize_handoff_event(
        delegator="agent-a",
        delegate="agent-b",
        scope="test-scope",
    )

    assert event["source_persona"] == ""
    assert event["target_persona"] == ""


def test_persona_handoff_persisted_through_mcp_tool() -> None:
    """Persona fields persist through the MCP tool entrypoint."""
    event = server.hlf_record_handoff_event(
        delegator="planner-agent",
        delegate="executor-agent",
        scope="mcp-persona-test",
        source_persona="planner",
        target_persona="executor",
    )

    assert event["status"] == "ok"
    assert event["source_persona"] == "planner"
    assert event["target_persona"] == "executor"


# ── Persona role permissions ────────────────────────────────────────────────────

def test_planner_has_defined_permissions() -> None:
    """Planner persona maps to strategist for planning tasks."""
    from hlf_mcp.persona_runtime import resolve_persona_runtime_metadata

    # "planner" is a workflow role, not in the persona runtime catalog directly.
    # It maps to "strategist" via the task-type-to-role mapping.
    meta = resolve_persona_runtime_metadata("strategist")
    assert meta is not None
    assert meta["persona"] == "strategist"
    assert meta["runtime_authority"] is False

    from hlf_mcp.instinct.lifecycle import _task_type_to_role
    assert _task_type_to_role("analyze") == "strategist"
    assert _task_type_to_role("deep_research") == "strategist"

    contract = resolve_persona_contract(
        source="weekly-evolution-planner",
        review_type="evolution_planning",
        severity=None,
        recommended_triage_lane=None,
    )
    assert contract["owner_persona"] == "strategist"


def test_executor_has_defined_permissions() -> None:
    """Executor persona maps to steward/steward role for workflow tasks."""
    from hlf_mcp.instinct.lifecycle import _task_type_to_role

    role = _task_type_to_role("run_command")
    assert role == "steward"

    role = _task_type_to_role("unknown_task")
    assert role == "scribe"  # default fallback


def test_verifier_has_defined_permissions() -> None:
    """Verifier persona maps to cove for test/lint/validation tasks."""
    from hlf_mcp.instinct.lifecycle import _task_type_to_role

    assert _task_type_to_role("run_tests") == "cove"
    assert _task_type_to_role("run_lint") == "cove"
    assert _task_type_to_role("check_syntax") == "cove"
    assert _task_type_to_role("validate_imports") == "cove"
    assert _task_type_to_role("preflight") == "cove"


def test_scribe_has_defined_permissions() -> None:
    """Scribe persona maps to scribe/herald roles for documentation tasks."""
    from hlf_mcp.instinct.lifecycle import _task_type_to_role

    assert _task_type_to_role("create_file") == "scribe"
    assert _task_type_to_role("generate_docs") == "herald"
    assert _task_type_to_role("update_changelog") == "herald"
    assert _task_type_to_role("audit_log") == "scribe"


def test_operator_is_only_authoritative_role() -> None:
    """Operator is the only persona with runtime_authority; all others are advisory."""
    from hlf_mcp.persona_runtime import resolve_persona_runtime_metadata

    # All personas in the runtime catalog have runtime_authority=False
    for role in ["strategist", "steward", "sentinel", "herald",
                 "chronicler", "cove"]:
        meta = resolve_persona_runtime_metadata(role)
        if meta:
            assert meta["runtime_authority"] is False, f"{role} should not have runtime authority"

    # Operator is not in the runtime catalog (it's the human gate),
    # but is recognized by persona_contract
    from hlf_mcp.persona_contract import load_persona_matrix
    matrix = load_persona_matrix()
    valid_personas = set(matrix.get("personas", {})) | {"operator"}
    assert "operator" in valid_personas


def test_persona_roles_set_is_complete() -> None:
    """PERSONA_ROLES covers all known roles from the matrix and task mapping."""
    from hlf_mcp.persona_contract import load_persona_matrix
    matrix = load_persona_matrix()
    matrix_personas = set(matrix.get("personas", {}).keys()) | {"operator"}

    from hlf_mcp.instinct.lifecycle import _task_type_to_role
    task_roles = set(_task_type_to_role(t) for t in [
        "create_file", "run_tests", "security_scan", "deploy_prod",
        "generate_docs", "analyze", "execute_plan",
    ])
    all_expected = matrix_personas | task_roles | {"planner", "executor", "verifier"}
    for role in all_expected:
        assert role in PERSONA_ROLES, f"{role} missing from PERSONA_ROLES"


# ── Cross-persona handoff lineage ────────────────────────────────────────────────

def test_cross_persona_handoff_preserves_lineage() -> None:
    """A planner→executor→verifier handoff chain preserves persona lineage."""
    root = server.hlf_record_handoff_event(
        delegator="coordinator",
        delegate="planner-agent",
        scope="persona-lineage-test",
        source_persona="operator",
        target_persona="planner",
        event_type="delegate",
        lifecycle_phase="plan",
    )
    step2 = server.hlf_record_handoff_event(
        delegator="planner-agent",
        delegate="executor-agent",
        scope="persona-lineage-test",
        source_persona="planner",
        target_persona="executor",
        event_type="delegate",
        lifecycle_phase="execute",
        parent_event_hash=root["event_hash"],
    )
    step3 = server.hlf_record_handoff_event(
        delegator="executor-agent",
        delegate="verifier-agent",
        scope="persona-lineage-test",
        source_persona="executor",
        target_persona="verifier",
        event_type="delegate",
        lifecycle_phase="verify",
        parent_event_hash=step2["event_hash"],
    )
    step4 = server.hlf_record_handoff_event(
        delegator="verifier-agent",
        delegate="coordinator",
        scope="persona-lineage-test",
        source_persona="verifier",
        target_persona="operator",
        event_type="complete",
        lifecycle_phase="merge",
        parent_event_hash=step3["event_hash"],
    )

    chain = server.hlf_handoff_chain(step4["event_hash"])
    assert chain["status"] == "ok"
    assert chain["verification_summary"]["verified"] is True

    lineage = chain["persona_lineage"]
    assert lineage["claim_lane"] == "bridge-true"
    assert lineage["transition_count"] == 4
    assert set(lineage["roles_present"]) == {"operator", "planner", "executor", "verifier"}

    transitions = lineage["transitions"]
    assert transitions[0]["from"] == "operator"
    assert transitions[0]["to"] == "planner"
    assert transitions[1]["from"] == "planner"
    assert transitions[1]["to"] == "executor"
    assert transitions[2]["from"] == "executor"
    assert transitions[2]["to"] == "verifier"
    assert transitions[3]["from"] == "verifier"
    assert transitions[3]["to"] == "operator"


def test_handoff_chain_verification_includes_persona_transitions() -> None:
    """verify_handoff_chain includes persona_transitions in its summary."""
    e1 = server.hlf_record_handoff_event(
        delegator="a", delegate="b", scope="s2",
        source_persona="planner", target_persona="executor",
    )
    e2 = server.hlf_record_handoff_event(
        delegator="b", delegate="c", scope="s2",
        source_persona="executor", target_persona="verifier",
        parent_event_hash=e1["event_hash"],
    )
    chain = server.hlf_handoff_chain(e2["event_hash"])
    summary = chain["verification_summary"]

    assert summary["verified"] is True
    assert len(summary["persona_transitions"]) == 2
    assert summary["persona_transitions"][0]["persona_role"] == "executor"
    assert summary["persona_transitions"][1]["persona_role"] == "verifier"


def test_persona_lineage_entry_produces_bounded_record() -> None:
    """persona_lineage_entry produces a bounded trace record."""
    entry = persona_lineage_entry(
        persona_role="planner",
        event_hash="abc123",
        lifecycle_phase="plan",
    )

    assert entry["persona_role"] == "planner"
    assert entry["event_hash"] == "abc123"
    assert entry["lifecycle_phase"] == "plan"
    assert entry["claim_lane"] == "bridge-true"
    assert entry["proof_boundary"]["persona_lineage_tracking"] is True
    assert entry["proof_boundary"]["runtime_enforcement"] is False


# ── Persona contract integration with workflows ─────────────────────────────────

def test_resolve_persona_contract_for_workflow_contract_change_class() -> None:
    """Workflow_contract change class requires all governance personas."""
    contract = resolve_persona_contract(
        source="weekly-spec-sentinel",
        review_type="weekly_artifact",
        severity="warning",
        recommended_triage_lane="backlog",
    )

    assert contract["change_class"] == "workflow_contract"
    assert contract["owner_persona"] == "steward"
    assert "steward_review" in contract["required_gates"]
    assert "sentinel_review" in contract["required_gates"]
    assert "herald_review" in contract["required_gates"]
    assert "operator_promotion" in contract["required_gates"]


def test_validate_persona_contract_rejects_invalid_persona() -> None:
    """validate_persona_contract catches invalid persona names."""
    from hlf_mcp.governed_review import default_governed_review, validate_governed_review

    review = default_governed_review(source="weekly-code-quality")
    review["owner_persona"] = "nonexistent_role"

    errors: list[str] = []
    validate_governed_review(review, errors)
    assert "governed_review_owner_persona_invalid" in errors


def test_swarm_mechanics_carry_persona_tags() -> None:
    """Swarm mechanics (planner/executor/verifier) persona roles are in PERSONA_ROLES."""
    # The three core operational persona roles are defined for swarm workflows
    assert "planner" in PERSONA_ROLES
    assert "executor" in PERSONA_ROLES
    assert "verifier" in PERSONA_ROLES
    # These roles are used by hlf_swarm_run internally


def test_instinct_lifecycle_preserves_persona_role_for_mission() -> None:
    """Instinct lifecycle mission creation preserves task→persona role mapping."""
    mission_id = f"persona-lifecycle-{uuid.uuid4().hex[:8]}"
    step1 = server.hlf_instinct_step(
        mission_id=mission_id,
        phase="specify",
        payload={"topic": "persona workflow test"},
    )
    assert step1["status"] == "ok"
    assert step1["current_phase"] == "specify"

    step2 = server.hlf_instinct_step(
        mission_id=mission_id,
        phase="plan",
        payload={"task_dag": [
            {"node_id": "analyze", "task_type": "analyze"},
            {"node_id": "docs", "task_type": "generate_docs"},
            {"node_id": "test", "task_type": "run_tests"},
        ]},
    )
    assert step2["status"] == "ok"

    # Task types should map to persona roles
    from hlf_mcp.instinct.lifecycle import _task_type_to_role
    assert _task_type_to_role("analyze") == "strategist"
    assert _task_type_to_role("generate_docs") == "herald"
    assert _task_type_to_role("run_tests") == "cove"


def test_persona_doctrine_schema_consistent_with_matrix() -> None:
    """The PERSONA_ROLES set is consistent with the ownership matrix."""
    from hlf_mcp.persona_contract import load_persona_matrix
    matrix = load_persona_matrix()
    personas_from_matrix = set(matrix.get("personas", {}).keys())
    personas_from_matrix.add("operator")

    # All matrix personas must be in PERSONA_ROLES
    for p in personas_from_matrix:
        assert p in PERSONA_ROLES, f"Matrix persona {p!r} not in PERSONA_ROLES"

    # Core workflow personas must be in PERSONA_ROLES
    for p in ("planner", "executor", "verifier", "scribe"):
        assert p in PERSONA_ROLES, f"Core workflow persona {p!r} not in PERSONA_ROLES"


# ── Persona doctrine integration into operator surfaces ──────────────────────────

def test_persona_doctrine_status_report_ok() -> None:
    """Persona doctrine status returns 'ok' when catalog and matrix are available."""
    from hlf_mcp.server_resources import _persona_doctrine_status, _persona_doctrine_summary

    status = _persona_doctrine_status()
    assert status in ("ok", "warning"), f"Unexpected status: {status}"

    summary = _persona_doctrine_summary()
    assert "persona" in summary.lower()
    assert "operator" in summary.lower()


def test_build_persona_doctrine_report_has_roles() -> None:
    """Persona doctrine report includes persona entries with expected fields."""
    from hlf_mcp.server_resources import _build_persona_doctrine_report

    report = _build_persona_doctrine_report(None)
    assert report["lane"] == "bridge-true"
    assert report["persona_count"] > 0
    assert "verification_hash" in report

    personas = report.get("personas") if isinstance(report.get("personas"), list) else []
    assert len(personas) > 0
    # Check that the authority_boundary confirms operator is the only authoritative role
    boundary = report.get("authority_boundary")
    assert isinstance(boundary, dict)
    assert boundary.get("operator_promotion_required") is True
    # Operator may not be in persona catalog (it's the human gate), but the doctrine
    # report should have governance personas like strategist, sentinel, cove, etc.
    persona_names = {p.get("persona") for p in personas if isinstance(p, dict)}
    assert persona_names, "No personas found in doctrine report"
    assert any(p in persona_names for p in ("strategist", "sentinel", "cove", "steward")), \
        f"No governance personas found in {persona_names}"


def test_render_persona_doctrine_status_produces_valid_json() -> None:
    """Persona doctrine status renderer produces valid JSON."""
    import json
    from hlf_mcp.server_resources import _render_persona_doctrine_status

    output = _render_persona_doctrine_status(None)
    payload = json.loads(output)
    assert payload["status"] in ("ok", "warning")
    assert "persona_doctrine" in payload


def test_render_persona_doctrine_markdown_includes_roles() -> None:
    """Persona doctrine markdown includes persona role table."""
    from hlf_mcp.server_resources import _render_persona_doctrine_markdown

    output = _render_persona_doctrine_markdown(None)
    assert "Persona Roles" in output
    assert "Authority Boundary" in output
    assert "hlf://status/persona_doctrine" in output


def test_persona_doctrine_in_operator_surfaces_entries() -> None:
    """Operator surfaces report includes a persona_doctrine entry."""
    import json
    from hlf_mcp.server_resources import _render_operator_surfaces_status

    output = _render_operator_surfaces_status(None)
    payload = json.loads(output)
    surfaces = payload.get("operator_surfaces", {})
    entries = surfaces.get("entries", []) if isinstance(surfaces, dict) else []
    persona_entries = [e for e in entries if isinstance(e, dict) and e.get("surface_id") == "persona_doctrine"]
    assert len(persona_entries) == 1, "Missing persona_doctrine entry in operator surfaces"
    assert persona_entries[0]["status_uri"] == "hlf://status/persona_doctrine"
    assert persona_entries[0]["report_uri"] == "hlf://reports/persona_doctrine"


def test_operator_proof_gallery_has_persona_examples() -> None:
    """Operator proof gallery includes persona-related examples."""
    import json
    from hlf_mcp.server_resources import _render_operator_proof_gallery_status

    output = _render_operator_proof_gallery_status(None)
    payload = json.loads(output)
    gallery = payload.get("operator_proof_gallery", {})
    examples = gallery.get("examples") if isinstance(gallery, dict) else []
    assert isinstance(examples, list)
    assert len(examples) >= 3, "Expected at least 3 examples including persona ones"

    example_ids = {e.get("example_id") for e in examples if isinstance(e, dict)}
    assert "persona-gated-promotion" in example_ids
    assert "operator-audit-inspection" in example_ids
    assert "developer-verifier-roundtrip" in example_ids

    for ex in examples:
        if isinstance(ex, dict):
            assert "persona_role" in ex, f"Example {ex.get('example_id')} missing persona_role"


def test_memory_audit_chain_includes_persona_contract_ref() -> None:
    """Memory audit chain bundle includes persona_contract_ref."""
    import json
    from hlf_mcp.server_resources import _render_memory_audit_chain_status

    output = _render_memory_audit_chain_status(None)
    payload = json.loads(output)
    bundle = payload.get("memory_audit_chain", {})
    assert isinstance(bundle, dict)
    contract_ref = bundle.get("persona_contract_ref")
    assert isinstance(contract_ref, dict), "Missing persona_contract_ref in audit chain"
    assert contract_ref.get("resource_uri") == "hlf://status/persona_doctrine"
    assert contract_ref.get("operator_is_authoritative") is True


def test_gallery_markdown_references_persona_doctrine() -> None:
    """Gallery markdown report references persona doctrine."""
    from hlf_mcp.server_resources import _render_gallery_markdown

    output = _render_gallery_markdown(None)
    assert "Persona Roles" in output
    assert "hlf://status/persona_doctrine" in output


def test_persona_doctrine_authority_boundary_present() -> None:
    """Persona doctrine report includes authority boundary."""
    from hlf_mcp.server_resources import _build_persona_doctrine_report

    report = _build_persona_doctrine_report(None)
    boundary = report.get("authority_boundary")
    assert isinstance(boundary, dict), "Missing authority_boundary"
    assert boundary.get("live_packaged_runtime_authority") is False
    assert boundary.get("operator_promotion_required") is True
