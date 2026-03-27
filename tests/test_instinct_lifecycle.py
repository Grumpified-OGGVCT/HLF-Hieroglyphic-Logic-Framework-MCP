from __future__ import annotations

from hlf_mcp.instinct.lifecycle import InstinctLifecycle


def test_plan_phase_normalizes_task_dag_and_preserves_dependencies() -> None:
    lifecycle = InstinctLifecycle()

    lifecycle.step("mission-dag", "specify", {"topic": "recover orchestration"})
    result = lifecycle.step(
        "mission-dag",
        "plan",
        {
            "task_dag": [
                {
                    "node_id": "verify",
                    "task_type": "run_tests",
                    "depends_on": ["implement"],
                    "escalation_role": "steward",
                },
                {
                    "node_id": "implement",
                    "task_type": "modify_file",
                    "delegated_to": "scribe",
                },
            ]
        },
    )

    assert [step["node_id"] for step in result["task_dag"]] == ["implement", "verify"]
    assert result["task_dag"][0]["delegated_to"] == "scribe"
    assert result["task_dag"][0]["assigned_role"] == "scribe"
    assert result["task_dag"][0]["assigned_persona"]["persona"] == "scribe"
    assert result["task_dag"][1]["escalation_role"] == "steward"
    assert result["task_dag"][1]["assigned_role"] == "steward"
    assert result["task_dag"][1]["assigned_persona"]["persona"] == "steward"


def test_specify_initializes_normalized_task_dag_and_contract() -> None:
    lifecycle = InstinctLifecycle()

    result = lifecycle.step(
        "mission-specify-dag",
        "specify",
        {
            "topic": "normalize at mission creation",
            "task_dag": [
                {
                    "node_id": "implement",
                    "task_type": "modify_file",
                    "delegated_to": "scribe",
                },
                {
                    "node_id": "verify",
                    "task_type": "run_tests",
                    "depends_on": ["implement"],
                    "escalation_role": "sentinel",
                },
            ],
        },
    )

    assert result["status"] == "ok"
    assert result["task_dag"][0]["assigned_role"] == "scribe"
    assert result["task_dag"][1]["assigned_role"] == "sentinel"
    assert result["orchestration_contract"]["summary"]["persona_bindings"] == {
        "scribe": 2,
        "sentinel": 2,
    }


def test_verify_is_blocked_when_execution_trace_is_incomplete() -> None:
    lifecycle = InstinctLifecycle()

    lifecycle.step("mission-blocked", "specify", {"topic": "recover orchestration"})
    lifecycle.step(
        "mission-blocked",
        "plan",
        {
            "task_dag": [
                {"node_id": "implement", "task_type": "modify_file"},
                {"node_id": "verify", "task_type": "run_tests", "depends_on": ["implement"]},
            ]
        },
    )
    lifecycle.step(
        "mission-blocked",
        "execute",
        {
            "execution_trace": [
                {
                    "node_id": "implement",
                    "task_type": "modify_file",
                    "assigned_role": "coder",
                    "success": True,
                    "duration_ms": 12.0,
                }
            ]
        },
    )

    result = lifecycle.step("mission-blocked", "verify", {"all_proven": True})

    assert result["status"] == "blocked"
    assert result["execution_summary"]["all_nodes_recorded"] is False


def test_execution_trace_serialization_surfaces_summary_counts() -> None:
    lifecycle = InstinctLifecycle()

    lifecycle.step("mission-execute", "specify", {"topic": "recover orchestration"})
    lifecycle.step(
        "mission-execute",
        "plan",
        {
            "task_dag": [
                {"node_id": "spec", "task_type": "modify_file", "assigned_role": "steward"},
                {
                    "node_id": "tests",
                    "task_type": "run_tests",
                    "depends_on": ["spec"],
                    "assigned_role": "verifier",
                    "delegated_to": "cove",
                    "escalation_role": "sentinel",
                },
            ]
        },
    )
    result = lifecycle.step(
        "mission-execute",
        "execute",
        {
            "execution_trace": [
                {
                    "node_id": "spec",
                    "success": True,
                    "duration_ms": 8.0,
                    "affected_files": ["docs/spec.md"],
                },
                {
                    "node_id": "tests",
                    "success": True,
                    "duration_ms": 15.0,
                    "outputs": ["2 passed"],
                    "delegated_to": "cove",
                    "escalation_role": "sentinel",
                    "verification_status": "passed",
                },
            ]
        },
    )

    assert result["execution_summary"]["all_nodes_succeeded"] is True
    assert result["execution_summary"]["delegated_nodes"] == 1
    assert result["execution_summary"]["escalated_nodes"] == 1
    assert result["orchestration_contract"]["summary"]["handoff_nodes"] == 1
    assert result["orchestration_contract"]["summary"]["persona_bound_nodes"] == 2
    assert result["orchestration_contract"]["summary"]["persona_bindings"]["cove"] == 1
    assert result["orchestration_contract"]["summary"]["persona_bindings"]["sentinel"] == 1
    assert result["task_dag"][0]["assigned_persona"]["persona"] == "steward"
    assert result["execution_trace"][1]["delegated_persona"]["persona"] == "cove"
    assert result["execution_trace"][1]["escalation_persona"]["persona"] == "sentinel"
    assert result["execution_trace"][1]["verification_status"] == "passed"


def test_verify_is_blocked_when_orchestration_contract_contains_denied_step() -> None:
    lifecycle = InstinctLifecycle()

    lifecycle.step("mission-contract-blocked", "specify", {"topic": "contract-denial"})
    lifecycle.step(
        "mission-contract-blocked",
        "plan",
        {
            "task_dag": [
                {
                    "node_id": "delegate",
                    "task_type": "delegate_task",
                    "delegated_to": "scribe",
                    "dissent_state": "soft_veto",
                }
            ]
        },
    )
    lifecycle.step(
        "mission-contract-blocked",
        "execute",
        {
            "execution_trace": [
                {
                    "node_id": "delegate",
                    "success": True,
                    "delegated_to": "scribe",
                    "dissent_state": "soft_veto",
                    "verification_status": "blocked",
                }
            ]
        },
    )

    result = lifecycle.step("mission-contract-blocked", "verify", {"all_proven": True})

    assert result["status"] == "blocked"
    assert result["error"] == "Execution trace is incomplete or contains failed nodes. Mission halted before verify."
    assert result["execution_summary"]["denied_nodes"] == 1
    assert result["execution_summary"]["dissenting_nodes"] == 1
    assert result["orchestration_contract"]["nodes"][0]["decision_state"] == "denied"
    assert result["orchestration_contract"]["nodes"][0]["dissenting"] is True


def test_merge_is_blocked_when_verification_report_is_not_proven() -> None:
    lifecycle = InstinctLifecycle()

    lifecycle.step("mission-merge", "specify", {"topic": "recover orchestration"})
    lifecycle.step(
        "mission-merge",
        "plan",
        {"task_dag": [{"node_id": "implement", "task_type": "modify_file"}]},
    )
    lifecycle.step(
        "mission-merge",
        "execute",
        {
            "execution_trace": [
                {
                    "node_id": "implement",
                    "task_type": "modify_file",
                    "success": True,
                    "duration_ms": 5.0,
                }
            ]
        },
    )
    lifecycle.step(
        "mission-merge",
        "verify",
        {"all_proven": False, "failed": 1, "results": [{"status": "counterexample"}]},
    )

    result = lifecycle.step("mission-merge", "merge", {})

    assert result["status"] == "blocked"
    assert result["error"] == "CoVE verification gate failed. Mission halted before merge."
