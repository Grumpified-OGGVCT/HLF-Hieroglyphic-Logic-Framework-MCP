"""
Tests for orchestration lifecycle — faithful port validation.

Covers:
  - Lifecycle transitions (full specify→plan→execute→verify→merge)
  - Plan DAG ordering and dependency resolution
  - Role boundaries and persona assignment
  - Delegation lineage tracking
  - Task classification integration
  - Execution pipeline dispatch
  - CoVE gate verification
  - Realignment events
"""

from __future__ import annotations

import time

import pytest

from hlf_mcp.instinct.classification import (
    FAST_PATH_TYPES,
    TASK_TYPE_REGISTRY,
    TaskCategory,
    TaskEnvelope,
    TaskLauncher,
    TaskSize,
    classify_intent,
    classify_task,
    get_all_categories,
    get_task_types_for_category,
    get_vocabulary_summary,
)
from hlf_mcp.instinct.execution import (
    NodeStatus,
    PlanExecutionResult,
    PlanExecutor,
    PlanStep,
    PlanTaskType,
    SpindleDAG,
    SpindleNode,
)
from hlf_mcp.instinct.lifecycle import (
    InstinctLifecycle,
    SDDRealignmentEvent,
)

from hlf_mcp.hlf.orchestration_failure_recovery import (
    CacheEntry,
    CrashRecovery,
    RecoveryResult,
    SplitBrainDetector,
    SplitBrainReport,
    StalePlanCache,
    SwarmLeaderElection,
    VectorClock,
)
from hlf_mcp.hlf.plan_rebalancing import (
    PlanRebalancer,
    RebalanceResult,
    TaskAffinityMap,
)
from hlf_mcp.hlf.swarm_handoff import (
    CapabilityAttestation,
    HandoffReceipt,
    HandoffStatus,
    SwarmHandoffContract,
    SwarmHandoffManager,
)


# ═══════════════════════════════════════════════════════════════════════════
# Classification tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskClassification:
    """Validates task_classifier port works correctly."""

    def test_classify_registered_code_task(self) -> None:
        envelope = classify_task({"type": "modify_file", "path": "src/app.py"})
        assert envelope.task_type == "modify_file"
        assert envelope.category == TaskCategory.CODE
        assert envelope.size == TaskSize.SMALL
        assert envelope.agent_target == "code-agent"
        assert envelope.fast_path is False
        assert envelope.confidence == 1.0

    def test_classify_micro_task_fast_path(self) -> None:
        envelope = classify_task({"type": "quick_fix", "path": "src/app.py"})
        assert envelope.task_type == "quick_fix"
        assert envelope.category == TaskCategory.CODE
        assert envelope.size == TaskSize.MICRO
        assert envelope.fast_path is True
        assert envelope.agent_target == "code-agent"

    def test_classify_build_task(self) -> None:
        envelope = classify_task({"type": "run_tests", "path": "tests/"})
        assert envelope.task_type == "run_tests"
        assert envelope.category == TaskCategory.BUILD
        assert envelope.agent_target == "build-agent"
        assert envelope.fast_path is False

    def test_classify_with_size_escalation_from_content(self) -> None:
        envelope = classify_task({
            "type": "modify_file",
            "path": "src/large.py",
            "content": "line\n" * 80,
        })
        assert envelope.size == TaskSize.MEDIUM

    def test_classify_unknown_type_defaults_to_code_agent(self) -> None:
        envelope = classify_task({"type": "mysterious_ritual", "desc": "do things"})
        assert envelope.category == TaskCategory.CODE
        assert envelope.agent_target == "code-agent"
        assert envelope.confidence <= 0.6

    def test_classify_intent_pattern_match(self) -> None:
        envelope = classify_intent("Fix the bug in auth module")
        assert envelope.task_type == "quick_fix"
        assert envelope.confidence == 0.7

    def test_classify_intent_deploy(self) -> None:
        envelope = classify_intent("Deploy to production now")
        assert envelope.task_type == "deploy_prod"
        assert envelope.category == TaskCategory.DEPLOY

    def test_classify_intent_research(self) -> None:
        envelope = classify_intent("Research the best approach for caching")
        assert envelope.task_type == "analyze"
        assert envelope.category == TaskCategory.RESEARCH

    def test_classify_intent_fallback(self) -> None:
        envelope = classify_intent("xyzzy frobnicate the transmogrifier")
        assert envelope.task_type == "unknown"
        assert envelope.confidence == 0.3
        assert envelope.category == TaskCategory.CODE

    def test_vocabulary_summary_structure(self) -> None:
        summary = get_vocabulary_summary()
        assert "total_types" in summary
        assert "categories" in summary
        assert "fast_path_types" in summary
        assert "by_category" in summary
        assert summary["categories"] >= 8

    def test_get_categories(self) -> None:
        cats = get_all_categories()
        assert "code" in cats
        assert "build" in cats
        assert "deploy" in cats

    def test_get_task_types_for_category(self) -> None:
        types = get_task_types_for_category(TaskCategory.GOVERNANCE)
        assert "align_check" in types
        assert "policy_check" in types

    def test_launcher_is_provenance_only(self) -> None:
        e1 = classify_task({"type": "quick_fix"}, launcher=TaskLauncher.GATEWAY)
        e2 = classify_task({"type": "quick_fix"}, launcher=TaskLauncher.MANUAL)
        assert e1.category == e2.category
        assert e1.agent_target == e2.agent_target
        assert e1.size == e2.size
        assert e1.launcher == TaskLauncher.GATEWAY
        assert e2.launcher == TaskLauncher.MANUAL

    def test_fast_path_types_includes_only_micro(self) -> None:
        for task_type in FAST_PATH_TYPES:
            entry = TASK_TYPE_REGISTRY.get(task_type, {})
            assert entry.get("default_size") == TaskSize.MICRO, (
                f"'{task_type}' in FAST_PATH_TYPES but not MICRO size"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Execution / DAG tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSpindleDAG:
    """Validates SpindleDAG operations."""

    def test_dag_topological_order_simple(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("a", depends_on=[]))
        dag.add_node(SpindleNode("b", depends_on=["a"]))
        dag.add_node(SpindleNode("c", depends_on=["b"]))
        assert dag.topological_order() == ["a", "b", "c"]

    def test_dag_topological_order_parallel(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("a", depends_on=[]))
        dag.add_node(SpindleNode("b", depends_on=["a"]))
        dag.add_node(SpindleNode("c", depends_on=["a"]))
        order = dag.topological_order()
        assert order[0] == "a"
        assert order[1] in ("b", "c")
        assert order[2] in ("b", "c")

    def test_dag_cycle_detection(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("a", depends_on=["b"]))
        dag.add_node(SpindleNode("b", depends_on=["a"]))
        with pytest.raises(ValueError, match="cycle"):
            dag.topological_order()

    def test_dag_unknown_dependency(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("a", depends_on=["nonexistent"]))
        with pytest.raises(ValueError, match="unknown"):
            dag.topological_order()

    def test_dag_duplicate_node_id(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("dup"))
        with pytest.raises(ValueError, match="Duplicate"):
            dag.add_node(SpindleNode("dup"))

    def test_dag_order_is_cached(self) -> None:
        dag = SpindleDAG()
        dag.add_node(SpindleNode("a"))
        dag.add_node(SpindleNode("b", depends_on=["a"]))
        first = dag.topological_order()
        second = dag.topological_order()
        assert first == second


class TestPlanExecutor:
    """Validates PlanExecutor faithfully ports plan_executor.py."""

    def test_plan_to_dag_creates_code_and_build_nodes(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/new.py"},
            {"type": "modify_file", "path": "src/existing.py"},
            {"type": "run_tests", "path": "tests/"},
        ]
        dag = executor.plan_to_dag(tasks)
        assert len(dag.nodes) == 3

    def test_plan_to_dag_code_nodes_sequential(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/a.py"},
            {"type": "create_file", "path": "src/b.py"},
        ]
        dag = executor.plan_to_dag(tasks)
        order = dag.topological_order()
        # b depends on a
        b_node = dag.nodes[order[1]]
        assert order[0] in b_node.depends_on

    def test_plan_to_dag_build_depends_on_last_code(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/a.py"},
            {"type": "run_tests", "path": "tests/"},
        ]
        dag = executor.plan_to_dag(tasks)
        build_ids = [nid for nid, n in dag.nodes.items() if n.agent_id == "build-agent"]
        code_ids = [nid for nid, n in dag.nodes.items() if n.agent_id == "code-agent"]
        for bid in build_ids:
            assert code_ids[-1] in dag.nodes[bid].depends_on

    def test_execute_plan_empty_tasks(self) -> None:
        executor = PlanExecutor()
        result = executor.execute_plan([])
        assert result.success is False
        assert result.error == "No tasks to execute"

    def test_execute_plan_successful(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/a.py"},
            {"type": "modify_file", "path": "src/b.py"},
        ]
        result = executor.execute_plan(tasks)
        assert result.success is True
        assert len(result.steps) == 2
        assert "src/a.py" in result.files_modified

    def test_execute_plan_fail_fast(self) -> None:
        executor = PlanExecutor()

        def failing_dispatch(task: dict, agent_type: str) -> dict:
            if task.get("path") == "src/b.py":
                return {"success": False, "error": "simulated failure"}
            return {"success": True, "files_modified": [task.get("path", "")]}

        executor.set_dispatch_fn(failing_dispatch)
        tasks = [
            {"type": "create_file", "path": "src/a.py"},
            {"type": "modify_file", "path": "src/b.py"},
            {"type": "create_file", "path": "src/c.py"},
        ]
        result = executor.execute_plan(tasks)
        assert result.success is False
        assert len(result.steps) == 2  # stopped after failure
        assert result.steps[0].success is True
        assert result.steps[1].success is False

    def test_execute_plan_with_dispatch_fn(self) -> None:
        executor = PlanExecutor()

        def dispatch(task: dict, agent_type: str) -> dict:
            return {
                "success": True,
                "files_modified": [task.get("path", "")],
                "outputs": ["ok"],
            }

        executor.set_dispatch_fn(dispatch)
        tasks = [
            {"type": "create_file", "path": "src/x.py"},
            {"type": "run_tests", "path": "tests/"},
        ]
        result = executor.execute_plan(tasks)
        assert result.success is True
        assert len(result.steps) == 2
        assert result.test_results["passed"] == 1

    def test_plan_to_dag_unknown_type_defaults_to_code(self) -> None:
        executor = PlanExecutor()
        tasks = [{"type": "unknown_ritual"}]
        dag = executor.plan_to_dag(tasks)
        assert len(dag.nodes) == 1
        node = list(dag.nodes.values())[0]
        assert node.agent_id == "code-agent"

    def test_execution_trace_populated(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/a.py"},
            {"type": "run_tests", "path": "tests/"},
        ]
        result = executor.execute_plan(tasks)
        assert len(result.execution_trace) == 2
        assert result.execution_trace[0]["success"] is True
        assert result.execution_trace[0]["node_id"].startswith("step-")

    def test_result_to_dict(self) -> None:
        executor = PlanExecutor()
        tasks = [{"type": "create_file", "path": "src/a.py"}]
        result = executor.execute_plan(tasks)
        d = result.to_dict()
        assert d["success"] is True
        assert "steps" in d
        assert "files_modified" in d


# ═══════════════════════════════════════════════════════════════════════════
# Lifecycle state machine tests
# ═══════════════════════════════════════════════════════════════════════════


class TestLifecycleTransitions:
    """Full lifecycle transition validation."""

    def test_full_specify_to_merge_pipeline(self) -> None:
        lc = InstinctLifecycle()

        # Specify
        r = lc.step("pipeline-1", "specify", {"topic": "add auth module"})
        assert r["status"] == "ok"
        assert r["current_phase"] == "specify"

        # Plan
        r = lc.step("pipeline-1", "plan", {
            "task_dag": [
                {"node_id": "impl", "task_type": "create_file", "assigned_role": "scribe"},
                {"node_id": "test", "task_type": "run_tests", "depends_on": ["impl"], "assigned_role": "cove"},
            ]
        })
        assert r["status"] == "ok"
        assert r["current_phase"] == "plan"
        assert len(r["task_dag"]) == 2

        # Execute
        r = lc.step("pipeline-1", "execute", {
            "execution_trace": [
                {"node_id": "impl", "success": True, "duration_ms": 10.0},
                {"node_id": "test", "success": True, "duration_ms": 20.0},
            ]
        })
        assert r["status"] == "ok"
        assert r["current_phase"] == "execute"
        assert r["execution_summary"]["all_nodes_succeeded"] is True

        # Verify
        r = lc.step("pipeline-1", "verify", {"all_proven": True})
        assert r["status"] == "ok"
        assert r["current_phase"] == "verify"

        # Merge
        r = lc.step("pipeline-1", "merge", {})
        assert r["status"] == "ok"
        assert r["current_phase"] == "merge"
        assert r["sealed"] is True

    def test_phase_skip_blocked(self) -> None:
        lc = InstinctLifecycle()
        lc.step("skip-test", "specify", {"topic": "test"})
        r = lc.step("skip-test", "execute", {})
        assert r["status"] == "error"
        assert "skip" in r["error"].lower() or "plan" in r["error"].lower()

    def test_backward_transition_blocked(self) -> None:
        lc = InstinctLifecycle()
        lc.step("back-test", "specify", {"topic": "test"})
        lc.step("back-test", "plan", {"task_dag": [{"node_id": "x"}]})
        r = lc.step("back-test", "specify", {})
        assert r["status"] == "error"
        assert "backward" in r["error"].lower()

    def test_backward_transition_allowed_with_override(self) -> None:
        lc = InstinctLifecycle()
        lc.step("back-override", "specify", {"topic": "test"})
        lc.step("back-override", "plan", {"task_dag": [{"node_id": "x"}]})
        r = lc.step("back-override", "specify", {}, override=True)
        assert r["status"] == "ok"

    def test_new_mission_must_start_at_specify(self) -> None:
        lc = InstinctLifecycle()
        r = lc.step("new-test", "plan", {})
        assert r["status"] == "error"

    def test_merge_blocked_without_cove_pass(self) -> None:
        lc = InstinctLifecycle()
        lc.step("cove-block", "specify", {"topic": "test"})
        lc.step("cove-block", "plan", {"task_dag": [{"node_id": "x"}]})
        lc.step("cove-block", "execute", {
            "execution_trace": [{"node_id": "x", "success": True}]
        })
        lc.step("cove-block", "verify", {"all_proven": False})
        r = lc.step("cove-block", "merge", {})
        assert r["status"] == "blocked"
        assert "cove" in r["error"].lower()

    def test_merge_allowed_with_override_and_cove_result(self) -> None:
        lc = InstinctLifecycle()
        lc.step("cove-ok", "specify", {"topic": "test"})
        lc.step("cove-ok", "plan", {"task_dag": [{"node_id": "x"}]})
        lc.step("cove-ok", "execute", {
            "execution_trace": [{"node_id": "x", "success": True}]
        })
        lc.step("cove-ok", "verify", {"all_proven": True})
        r = lc.step("cove-ok", "merge", {}, cove_result={"passed": True})
        assert r["status"] == "ok"
        assert r["sealed"] is True

    def test_verify_blocked_with_incomplete_trace(self) -> None:
        lc = InstinctLifecycle()
        lc.step("inc-trace", "specify", {"topic": "test"})
        lc.step("inc-trace", "plan", {
            "task_dag": [
                {"node_id": "a"},
                {"node_id": "b", "depends_on": ["a"]},
            ]
        })
        lc.step("inc-trace", "execute", {
            "execution_trace": [{"node_id": "a", "success": True}]
        })
        r = lc.step("inc-trace", "verify", {})
        assert r["status"] == "blocked"
        assert r["execution_summary"]["all_nodes_recorded"] is False

    def test_already_at_phase_returns_ok_with_note(self) -> None:
        lc = InstinctLifecycle()
        lc.step("same", "specify", {"topic": "t"})
        r = lc.step("same", "specify", {})
        assert r["status"] == "ok"
        assert r.get("note") == "already_at_phase"


class TestClassificationIntegration:
    """Tests classify_and_plan integration."""

    def test_classify_and_plan_creates_mission_with_dag(self) -> None:
        lc = InstinctLifecycle()
        r = lc.classify_and_plan("cap-1", "Fix the authentication bug in login.py")
        assert r["status"] == "ok"
        assert r["current_phase"] == "plan"
        assert len(r["task_dag"]) >= 1
        assert "classification" in r.get("spec", {})

    def test_classify_and_plan_fast_path_reduces_dag(self) -> None:
        lc = InstinctLifecycle()
        r = lc.classify_and_plan("fast-1", "toggle flag off")
        assert r["status"] == "ok"
        assert len(r["task_dag"]) == 1
        assert r["task_dag"][0]["node_id"] == "quick_execute"


class TestRoleBoundaries:
    """Validates role/persona boundaries in DAG construction."""

    def test_dag_roles_preserved_through_normalization(self) -> None:
        lc = InstinctLifecycle()
        lc.step("roles-1", "specify", {"topic": "role test"})
        r = lc.step("roles-1", "plan", {
            "task_dag": [
                {
                    "node_id": "write",
                    "task_type": "create_file",
                    "assigned_role": "scribe",
                },
                {
                    "node_id": "check",
                    "task_type": "run_tests",
                    "depends_on": ["write"],
                    "escalation_role": "sentinel",
                },
            ]
        })
        assert r["task_dag"][0]["assigned_role"] == "scribe"
        assert r["task_dag"][1]["escalation_role"] == "sentinel"
        assert r["task_dag"][1]["assigned_role"] == "sentinel"

    def test_verification_required_flag(self) -> None:
        lc = InstinctLifecycle()
        r = lc.classify_and_plan("verify-flag", "Create a new API endpoint")
        # Should have at least one node with verification_required
        any_verify = any(
            n.get("verification_required") for n in r["task_dag"]
        )
        assert any_verify


class TestDelegationLineage:
    """Validates delegation/dissent/escalation lineage tracking."""

    def test_delegation_trace_preserved(self) -> None:
        lc = InstinctLifecycle()
        lc.step("deleg-1", "specify", {"topic": "delegation test"})
        lc.step("deleg-1", "plan", {
            "task_dag": [
                {
                    "node_id": "task_a",
                    "task_type": "modify_file",
                    "delegated_to": "scribe",
                    "escalation_role": "steward",
                }
            ]
        })
        lc.step("deleg-1", "execute", {
            "execution_trace": [
                {
                    "node_id": "task_a",
                    "success": True,
                    "delegated_to": "scribe",
                    "escalation_role": "steward",
                    "verification_status": "passed",
                }
            ]
        })
        mission = lc.get_mission("deleg-1")
        assert mission is not None
        contract = mission["orchestration_contract"]
        assert contract["summary"]["delegated_nodes"] == 1
        assert contract["summary"]["escalated_nodes"] == 1

    def test_dissent_tracked_in_orchestration_contract(self) -> None:
        lc = InstinctLifecycle()
        lc.step("dissent-1", "specify", {"topic": "dissent test"})
        lc.step("dissent-1", "plan", {
            "task_dag": [
                {
                    "node_id": "contested",
                    "task_type": "refactor",
                    "dissent_state": "soft_veto",
                }
            ]
        })
        lc.step("dissent-1", "execute", {
            "execution_trace": [
                {
                    "node_id": "contested",
                    "success": True,
                    "dissent_state": "soft_veto",
                    "verification_status": "blocked",
                }
            ]
        })
        mission = lc.get_mission("dissent-1")
        contract = mission["orchestration_contract"]
        assert contract["summary"]["dissenting_nodes"] == 1
        assert contract["nodes"][0]["dissenting"] is True

    def test_handoff_lineage_multiple_hops(self) -> None:
        lc = InstinctLifecycle()
        lc.step("handoff-1", "specify", {"topic": "multi-hop handoff"})
        lc.step("handoff-1", "plan", {
            "task_dag": [
                {"node_id": "a", "task_type": "modify_file", "delegated_to": "scribe"},
                {"node_id": "b", "task_type": "run_tests", "depends_on": ["a"], "escalation_role": "sentinel"},
                {"node_id": "c", "task_type": "summarize", "depends_on": ["b"], "delegated_to": "consolidator"},
            ]
        })
        lc.step("handoff-1", "execute", {
            "execution_trace": [
                {"node_id": "a", "success": True, "delegated_to": "scribe"},
                {"node_id": "b", "success": True, "escalation_role": "sentinel"},
                {"node_id": "c", "success": True, "delegated_to": "consolidator"},
            ]
        })
        mission = lc.get_mission("handoff-1")
        contract = mission["orchestration_contract"]
        assert contract["summary"]["handoff_nodes"] == 3
        assert contract["summary"]["delegated_nodes"] == 2
        assert contract["summary"]["escalated_nodes"] == 1


class TestRealignment:
    """Validates SDD realignment events."""

    def test_realignment_adds_to_history(self) -> None:
        lc = InstinctLifecycle()
        lc.step("realign-1", "specify", {"topic": "realign test"})
        lc.step("realign-1", "plan", {"task_dag": [{"node_id": "x"}]})

        event = SDDRealignmentEvent(
            triggered_by="steward",
            change_type="deprecated_api",
            change_description="Old endpoint deprecated",
            affected_nodes=["x"],
        )
        r = lc.realign("realign-1", event)
        assert r["status"] == "ok"
        assert len(r["realignment_events"]) == 1

    def test_cannot_realign_sealed_mission(self) -> None:
        lc = InstinctLifecycle()
        lc.step("sealed-1", "specify", {"topic": "sealed"})
        lc.step("sealed-1", "plan", {"task_dag": [{"node_id": "x"}]})
        lc.step("sealed-1", "execute", {"execution_trace": [{"node_id": "x", "success": True}]})
        lc.step("sealed-1", "verify", {"all_proven": True})
        lc.step("sealed-1", "merge", {})

        event = SDDRealignmentEvent(
            triggered_by="scribe",
            change_type="new_constraint",
            change_description="Cannot modify sealed",
        )
        r = lc.realign("sealed-1", event)
        assert r["status"] == "error"
        assert "sealed" in r["error"].lower()

    def test_realignment_nonexistent_mission(self) -> None:
        lc = InstinctLifecycle()
        event = SDDRealignmentEvent(
            triggered_by="scribe",
            change_type="test",
            change_description="n/a",
        )
        r = lc.realign("nonexistent", event)
        assert r["status"] == "error"


class TestExecuteWithRouting:
    """Tests the execute_plan_with_routing integration."""

    def test_execute_with_routing_populates_trace(self) -> None:
        lc = InstinctLifecycle()
        lc.step("route-exec", "specify", {"topic": "routing test"})
        lc.step("route-exec", "plan", {
            "task_dag": [
                {"node_id": "impl", "task_type": "modify_file", "assigned_role": "scribe"},
                {"node_id": "verify", "task_type": "run_tests", "depends_on": ["impl"], "assigned_role": "cove"},
            ]
        })

        def mock_route(node: dict) -> dict:
            return {"agent": node.get("assigned_role", "scribe"), "tier": "A"}

        r = lc.execute_plan_with_routing("route-exec", routing_fn=mock_route)
        assert r["status"] == "ok"
        assert r["current_phase"] == "execute"
        assert len(r["execution_trace"]) == 2
        assert r["execution_summary"]["all_nodes_succeeded"] is True

    def test_execute_without_plan_fails(self) -> None:
        lc = InstinctLifecycle()
        lc.step("no-plan", "specify", {"topic": "no plan yet"})
        r = lc.execute_plan_with_routing("no-plan")
        assert r["status"] == "error"

    def test_execute_nonexistent_mission(self) -> None:
        lc = InstinctLifecycle()
        r = lc.execute_plan_with_routing("ghost")
        assert r["status"] == "error"


class TestCoVEGateIntegration:
    """Tests CoVE verification gate integration."""

    def test_run_cove_verification_passes(self) -> None:
        lc = InstinctLifecycle()
        lc.step("cove-int", "specify", {"topic": "cove test"})
        lc.step("cove-int", "plan", {
            "task_dag": [
                {"node_id": "impl", "task_type": "modify_file"},
                {"node_id": "test", "task_type": "run_tests", "depends_on": ["impl"]},
            ]
        })
        lc.step("cove-int", "execute", {
            "execution_trace": [
                {"node_id": "impl", "success": True},
                {"node_id": "test", "success": True},
            ]
        })
        r = lc.run_cove_verification("cove-int")
        assert r["status"] == "ok"
        assert r["current_phase"] == "verify"

    def test_get_mission_returns_none_for_unknown(self) -> None:
        lc = InstinctLifecycle()
        assert lc.get_mission("ghost") is None

    def test_list_missions_empty_initially(self) -> None:
        lc = InstinctLifecycle()
        assert lc.list_missions() == []

    def test_list_missions_after_creation(self) -> None:
        lc = InstinctLifecycle()
        lc.step("m1", "specify", {"topic": "mission one"})
        lc.step("m2", "specify", {"topic": "mission two"})
        missions = lc.list_missions()
        assert len(missions) == 2

    def test_get_vocabulary(self) -> None:
        lc = InstinctLifecycle()
        vocab = lc.get_vocabulary()
        assert vocab["total_types"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_mission_with_zero_dag_nodes(self) -> None:
        lc = InstinctLifecycle()
        lc.step("zero-dag", "specify", {"topic": "empty dag"})
        r = lc.step("zero-dag", "plan", {"task_dag": []})
        assert r["status"] == "ok"

    def test_execution_with_failed_node_blocks_verify(self) -> None:
        lc = InstinctLifecycle()
        lc.step("fail-exec", "specify", {"topic": "fail"})
        lc.step("fail-exec", "plan", {
            "task_dag": [
                {"node_id": "a", "task_type": "modify_file"},
                {"node_id": "b", "task_type": "run_tests", "depends_on": ["a"]},
            ]
        })
        lc.step("fail-exec", "execute", {
            "execution_trace": [
                {"node_id": "a", "success": True},
                {"node_id": "b", "success": False, "verification_status": "failed"},
            ]
        })
        r = lc.step("fail-exec", "verify", {})
        assert r["status"] == "blocked"

    def test_ledger_records_transitions(self) -> None:
        lc = InstinctLifecycle()
        lc.step("ledger", "specify", {"topic": "ledger test"})
        lc.step("ledger", "plan", {"task_dag": [{"node_id": "x"}]})
        ledger = lc.get_ledger("ledger")
        assert len(ledger) >= 2

    def test_thread_safe_missions(self) -> None:
        import threading

        lc = InstinctLifecycle()
        errors: list[str] = []

        def create_mission(idx: int) -> None:
            try:
                lc.step(f"thread-{idx}", "specify", {"topic": f"thread {idx}"})
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=create_mission, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(lc.list_missions()) == 10


# ═══════════════════════════════════════════════════════════════════════════
# Plan DAG ordering
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanDAGOrdering:
    def test_topological_sort_respects_dependencies(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "create_file", "path": "src/base.py"},
            {"type": "create_file", "path": "src/derived.py"},
            {"type": "run_tests", "path": "tests/"},
        ]
        dag = executor.plan_to_dag(tasks)
        order = dag.topological_order()
        code_steps = [nid for nid in order if "create_file" in nid]
        build_steps = [nid for nid in order if "run_tests" in nid]
        # All code steps before all build steps
        if code_steps and build_steps:
            last_code_idx = max(order.index(c) for c in code_steps)
            first_build_idx = min(order.index(b) for b in build_steps)
            assert last_code_idx < first_build_idx

    def test_dag_with_only_build_tasks(self) -> None:
        executor = PlanExecutor()
        tasks = [
            {"type": "run_tests", "path": "tests/unit/"},
            {"type": "run_lint", "path": "src/"},
        ]
        dag = executor.plan_to_dag(tasks)
        assert len(dag.nodes) == 2
        # All build tasks depend on each other
        order = dag.topological_order()
        assert len(order) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Task type registry consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskTypeRegistryConsistency:
    def test_all_registered_types_have_valid_category(self) -> None:
        from hlf_mcp.instinct.classification import TASK_TYPE_REGISTRY as reg
        valid = set(TaskCategory)
        for name, entry in reg.items():
            assert entry["category"] in valid, f"{name} has invalid category"

    def test_all_registered_types_have_positive_gas(self) -> None:
        from hlf_mcp.instinct.classification import TASK_TYPE_REGISTRY as reg
        for name, entry in reg.items():
            assert entry["gas"] > 0, f"{name} has non-positive gas"

    def test_all_registered_types_have_valid_agent(self) -> None:
        from hlf_mcp.instinct.classification import TASK_TYPE_REGISTRY as reg
        for name, entry in reg.items():
            assert "-agent" in entry["agent"] or entry["agent"] == "plan-executor", (
                f"{name} has unexpected agent: {entry['agent']}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8: Plan Versioning — PlanVersion / PlanHistory
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanVersioningCreateAndChain:
    """test_plan_versioning_create_and_chain (5 tests)"""

    def test_create_single_version(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanVersion

        v = PlanVersion(
            plan_data=[{"agent_id": "planner", "goal": "Test"}],
            metadata={"task_id": "abc"},
        )
        assert v.version_number == 1
        assert v.checksum
        assert v.active is True
        assert v.parent_version is None
        assert v.verify_integrity()

    def test_create_version_chain(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit(
            [{"agent_id": "planner", "goal": "v1"}],
            {"task_id": "task-1"},
        )
        v2 = history.commit(
            [{"agent_id": "planner", "goal": "v2"}],
            {"task_id": "task-1", "revised": True},
        )
        v3 = history.commit(
            [{"agent_id": "executor", "goal": "v3"}],
            {"task_id": "task-1", "revised": True},
        )

        assert v1.version_number == 1
        assert v2.version_number == 2
        assert v3.version_number == 3
        assert v2.parent_version == v1.version_id
        assert v3.parent_version == v2.version_id
        assert history.get_version_count() == 3

    def test_version_chain_integrity(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        history.commit([{"agent_id": "a", "goal": "g"}])
        history.commit([{"agent_id": "a", "goal": "g", "scope": ["x.py"]}])
        history.commit([{"agent_id": "a", "goal": "g", "scope": ["x.py", "y.py"]}])

        result = history.verify_chain_integrity()
        assert result["all_valid"] is True
        assert result["version_count"] == 3
        assert len(result["invalid_versions"]) == 0

    def test_get_version_by_number(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        history.commit([{"agent_id": "a"}])
        history.commit([{"agent_id": "b"}])
        history.commit([{"agent_id": "c"}])

        v2 = history.get_version_by_number(2)
        assert v2 is not None
        assert v2.version_number == 2
        assert v2.plan_data[0]["agent_id"] == "b"

        assert history.get_version_by_number(99) is None

    def test_version_to_dict_and_from_dict_roundtrip(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanVersion

        original = PlanVersion(
            version_number=5,
            plan_data=[{"agent_id": "planner", "role": "scribe"}],
            metadata={"swarm_id": "sw1", "task_id": "t1"},
            parent_version="parent-uuid-123",
        )
        d = original.to_dict()
        restored = PlanVersion.from_dict(d)
        assert restored.version_number == original.version_number
        assert restored.version_id == original.version_id
        assert restored.checksum == original.checksum
        assert restored.plan_data == original.plan_data
        assert restored.metadata == original.metadata
        assert restored.parent_version == original.parent_version


class TestPlanVersioningRollback:
    """test_plan_versioning_rollback (4 tests)"""

    def test_rollback_to_parent(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit([{"agent_id": "a", "goal": "original"}])
        v2 = history.commit([{"agent_id": "a", "goal": "modified"}])

        rolled = history.rollback()
        assert rolled.version_number == 3
        assert rolled.plan_data[0]["goal"] == "original"
        assert rolled.metadata.get("rollback") is True
        assert rolled.metadata.get("rolled_back_from") == v2.version_id
        current = history.get_current()
        assert current is not None
        assert current.version_id == rolled.version_id

    def test_rollback_to_specific_version(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit([{"agent_id": "a", "goal": "v1"}])
        history.commit([{"agent_id": "a", "goal": "v2"}])
        history.commit([{"agent_id": "a", "goal": "v3"}])

        rolled = history.rollback(v1.version_id)
        assert rolled.plan_data[0]["goal"] == "v1"
        assert rolled.parent_version == v1.version_id
        assert history.get_version_count() == 4

    def test_rollback_fails_on_single_version(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        history.commit([{"agent_id": "a"}])

        import pytest
        with pytest.raises(ValueError, match="no parent|least two versions|Cannot roll back"):
            history.rollback()

    def test_rollback_non_existent_target(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        history.commit([{"agent_id": "a"}])

        import pytest
        with pytest.raises(ValueError, match="not found"):
            history.rollback("nonexistent-uuid")


class TestPlanVersioningDiff:
    """test_plan_versioning_diff (3 tests)"""

    def test_diff_detects_added_removed(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit([
            {"agent_id": "a", "goal": "X"},
            {"agent_id": "b", "goal": "Y"},
        ])
        v2 = history.commit([
            {"agent_id": "a", "goal": "X"},
            {"agent_id": "c", "goal": "Z"},
        ])

        diff = history.diff(v1, v2)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["agent_id"] == "c"
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["agent_id"] == "b"

    def test_diff_detects_changes(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit([
            {"agent_id": "a", "goal": "Old goal", "role": "planner"},
        ])
        v2 = history.commit([
            {"agent_id": "a", "goal": "New goal", "role": "executor"},
        ])

        diff = history.diff(v1, v2)
        assert len(diff["changed"]) == 1
        assert diff["changed"][0]["agent_id"] == "a"
        assert diff["changed"][0]["before"]["goal"] == "Old goal"
        assert diff["changed"][0]["after"]["goal"] == "New goal"

    def test_diff_metadata_changes(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        v1 = history.commit(
            [{"agent_id": "a"}],
            metadata={"revision": 1, "author": "scribe"},
        )
        v2 = history.commit(
            [{"agent_id": "a"}],
            metadata={"revision": 2, "author": "cove"},
        )

        diff = history.diff(v1, v2)
        assert "revision" in diff["metadata_changes"]
        assert "author" in diff["metadata_changes"]


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8: Checkpoint Executor — Checkpoint / CheckpointManager
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckpointSaveAndResume:
    """test_checkpoint_save_and_resume (5 tests)"""

    def test_save_checkpoint(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager()
        ck = Checkpoint(
            phase="plan",
            swarm_id="swarm-1",
            task_id="task-1",
            plan_data=[{"agent_id": "planner"}],
            resume_point="After PLAN",
        )
        saved = mgr.save(ck)
        assert saved.checkpoint_id == ck.checkpoint_id
        assert mgr.get_count() == 1

    def test_load_checkpoint(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager()
        ck = Checkpoint(
            phase="consolidate",
            swarm_id="swarm-2",
            task_id="task-2",
            consolidated_data={"merged_count": 3},
            resume_point="After CONSOLIDATE",
        )
        mgr.save(ck)
        loaded = mgr.load(ck.checkpoint_id)
        assert loaded is not None
        assert loaded.phase == "consolidate"
        assert loaded.consolidated_data["merged_count"] == 3
        assert loaded.verify_integrity()

    def test_get_last_checkpoint_by_swarm(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager()
        mgr.save(Checkpoint(phase="plan", swarm_id="sw-A", task_id="t1"))
        mgr.save(Checkpoint(phase="consolidate", swarm_id="sw-A", task_id="t1"))
        mgr.save(Checkpoint(phase="plan", swarm_id="sw-B", task_id="t2"))

        last_a = mgr.get_last_checkpoint(swarm_id="sw-A")
        assert last_a is not None
        assert last_a.phase == "consolidate"
        assert last_a.swarm_id == "sw-A"

    def test_checkpoint_integrity_verification(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager()
        ck = Checkpoint(
            phase="execute",
            step_index=3,
            swarm_id="sw-3",
            agent_states={"agent-1": {"status": "ok"}},
            resume_point="After step 3",
        )
        mgr.save(ck)
        assert mgr.verify_checkpoint(ck.checkpoint_id) is True

        result = mgr.verify_all()
        assert result["all_valid"] is True
        assert result["count"] == 1

    def test_checkpoint_to_dict_and_from_dict_roundtrip(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint

        original = Checkpoint(
            phase="execute",
            step_index=2,
            swarm_id="sw-rt",
            task_id="task-rt",
            agent_states={"a1": {"status": "ok"}},
            plan_data=[{"agent_id": "a1"}],
            consolidated_data={"order": ["a1"]},
            resume_point="After step 2",
        )
        d = original.to_dict()
        restored = Checkpoint.from_dict(d)
        assert restored.phase == original.phase
        assert restored.step_index == original.step_index
        assert restored.swarm_id == original.swarm_id
        assert restored.checksum == original.checksum
        assert restored.agent_states == original.agent_states


class TestCheckpointMultiPhaseIntegration:
    """test_checkpoint_multi_phase_integration (5 tests)"""

    def test_checkpointable_executor_creates_checkpoints(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import CheckpointableExecutor

        executor = CheckpointableExecutor()
        result = executor.run("Write a hello world function")

        assert result.result is not None
        assert result.result.swarm_id
        assert result.result.phases
        phase_ids = [p.phase_id for p in result.result.phases]
        assert "plan" in phase_ids
        assert "consolidate" in phase_ids
        assert "execute" in phase_ids

        # Should have at least 2 checkpoints (plan + consolidate)
        assert result.total_checkpoints >= 2

        # First checkpoint is from plan phase
        assert result.checkpoints[0].phase == "plan"

        # Last checkpoint should be from execute phase
        assert result.checkpoints[-1].phase == "execute"

    def test_checkpointable_result_to_dict(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import CheckpointableExecutor

        executor = CheckpointableExecutor()
        result = executor.run("Sort a list")

        d = result.to_dict()
        assert "result_swarm_id" in d
        assert "result_status" in d
        assert "checkpoints" in d
        assert "total_checkpoints" in d
        assert d["total_checkpoints"] >= 2

    def test_resume_from_plan_checkpoint(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import (
            CheckpointableExecutor,
            Checkpoint,
            CheckpointManager,
        )

        mgr = CheckpointManager()
        executor = CheckpointableExecutor(checkpoint_manager=mgr)

        # Pre-seed a PLAN checkpoint
        ck = Checkpoint(
            phase="plan",
            swarm_id="resume-swarm",
            task_id="resume-task",
            plan_data=[
                {
                    "agent_id": "planner",
                    "role": "planner",
                    "goal": "Resume test",
                    "hlf_source": "[HLF-v3]\nΔ [ANALYZE] query=\"test\"\nΩ\n",
                    "scope": [],
                    "constraints": [],
                    "capabilities": ["network", "model"],
                    "dependencies": [],
                    "metrics": {"hlf_tokens": 3, "compile_success": True},
                },
            ],
            resume_point="After PLAN",
        )
        mgr.save(ck)

        resumed = executor.resume(ck.checkpoint_id)
        assert resumed is not None
        assert resumed.resumed_from == ck.checkpoint_id
        assert resumed.result.swarm_id == "resume-swarm"
        assert resumed.total_checkpoints >= 1

    def test_resume_from_checkpoint_multiple_phases(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import (
            CheckpointableExecutor,
            Checkpoint,
            CheckpointManager,
        )

        mgr = CheckpointManager()
        executor = CheckpointableExecutor(checkpoint_manager=mgr)

        ck = Checkpoint(
            phase="plan",
            swarm_id="multi-resume",
            task_id="multi-task",
            plan_data=[
                {
                    "agent_id": "executor",
                    "role": "executor",
                    "goal": "Multi-phase resume",
                    "hlf_source": "[HLF-v3]\nΔ [EXECUTE] task=\"run\"\nΩ\n",
                    "scope": [],
                    "constraints": [],
                    "capabilities": ["network"],
                    "dependencies": [],
                    "metrics": {"hlf_tokens": 3, "compile_success": True},
                },
            ],
            resume_point="After PLAN",
        )
        mgr.save(ck)

        resumed = executor.resume(ck.checkpoint_id)
        assert resumed is not None
        # Should have created CONSOLIDATE + EXECUTE checkpoints
        phases_seen = {c.phase for c in resumed.checkpoints}
        assert "consolidate" in phases_seen

    def test_checkpoint_manager_lifecycle(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager()
        assert mgr.get_count() == 0

        ck = mgr.save(Checkpoint(phase="plan", swarm_id="lc", task_id="t"))
        assert mgr.get_count() == 1

        ck2 = mgr.save(Checkpoint(phase="execute", swarm_id="lc", task_id="t"))
        assert mgr.get_count() == 2

        # List checkpoints
        listing = mgr.list_checkpoints()
        assert len(listing) == 2
        assert all("checkpoint_id" in c for c in listing)

        # Delete one
        assert mgr.delete_checkpoint(ck.checkpoint_id) is True
        assert mgr.get_count() == 1
        assert mgr.load(ck.checkpoint_id) is None

        # Delete non-existent
        assert mgr.delete_checkpoint("ghost") is False

        # Clear
        mgr.clear()
        assert mgr.get_count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8: End-to-end PLAN→CONSOLIDATE→EXECUTE proof loop
# ═══════════════════════════════════════════════════════════════════════════


class TestEndToEndPlanConsolidateExecute:
    """test_end_to_end_plan_consolidate_execute (3 tests)"""

    def test_e2e_full_pipeline_produces_valid_result(self) -> None:
        from hlf_mcp.hlf.multi_phase_executor import MultiPhaseExecutor

        executor = MultiPhaseExecutor()
        result = executor.run_multi_phase("Write a function to add two numbers")

        assert result.swarm_id
        assert result.task_id
        assert result.final_status in ("ok", "compile_error")
        assert len(result.phases) == 3

        plan_phase = result.phases[0]
        assert plan_phase.phase_id == "plan"
        assert plan_phase.status == "complete"
        assert len(plan_phase.agent_plans) >= 1

        con_phase = result.phases[1]
        assert con_phase.phase_id == "consolidate"
        assert con_phase.status in ("complete", "skipped")

        exec_phase = result.phases[2]
        assert exec_phase.phase_id == "execute"
        assert exec_phase.status in ("complete", "error")

    def test_e2e_pipeline_with_plan_versioning_integration(self) -> None:
        from hlf_mcp.hlf.multi_phase_executor import MultiPhaseExecutor
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        executor = MultiPhaseExecutor()

        # Run first plan
        plans = executor.plan_phase("Calculate factorial")
        history.commit(
            [
                {
                    "agent_id": p.agent_id,
                    "role": p.role,
                    "goal": p.goal,
                    "hlf_source": p.hlf_source,
                    "scope": list(p.scope),
                    "constraints": p.constraints,
                    "capabilities": list(p.capabilities),
                    "dependencies": p.dependencies,
                    "metrics": p.metrics,
                }
                for p in plans
            ],
            metadata={"task": "Calculate factorial", "version": 1},
        )

        # Consolidate
        consolidated = executor.consolidate_phase(plans)
        assert consolidated.merged_plans

        # Execute
        result = executor.execute_phase(consolidated)
        assert result.status in ("complete", "error")

        # Commit a revised plan
        history.commit(
            [
                {
                    "agent_id": "verifier",
                    "role": "verifier",
                    "goal": "Verify factorial",
                    "hlf_source": "[HLF-v3]\nΔ [VERIFY]\nΩ\n",
                }
            ],
            metadata={"task": "Calculate factorial", "version": 2, "revised": True},
        )

        assert history.get_version_count() == 2
        v1 = history.get_version_by_number(1)
        v2 = history.get_version_by_number(2)
        assert v1 is not None and v2 is not None

        diff = history.diff(v1, v2)
        assert "added" in diff

    def test_e2e_with_checkpoint_and_resume_loop(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import (
            Checkpoint,
            CheckpointManager,
            CheckpointableExecutor,
        )

        mgr = CheckpointManager()
        executor = CheckpointableExecutor(checkpoint_manager=mgr)

        # Full run
        result = executor.run("Reverse a string")
        assert result.result.swarm_id
        assert result.total_checkpoints >= 2

        # Simulate resume from first checkpoint
        first_ck_id = result.checkpoints[0].checkpoint_id
        resumed = executor.resume(first_ck_id)
        assert resumed is not None
        assert resumed.resumed_from == first_ck_id
        assert resumed.result.swarm_id == result.result.swarm_id


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8: Orchestration lifecycle integration tests
# ═══════════════════════════════════════════════════════════════════════════


class TestOrchestrationLifecycleIntegration:
    """test_orchestration_lifecycle_integration (5 tests)"""

    def test_plan_history_integrates_with_multi_phase(self) -> None:
        from hlf_mcp.hlf.multi_phase_executor import MultiPhaseExecutor
        from hlf_mcp.hlf.plan_versioning import PlanHistory

        history = PlanHistory()
        executor = MultiPhaseExecutor()

        plans = executor.plan_phase("Validate email format")
        history.commit(
            [
                {"agent_id": p.agent_id, "goal": p.goal, "hlf_source": p.hlf_source}
                for p in plans
            ],
            metadata={"task": "Validate email format"},
        )

        assert history.get_current() is not None
        chain = history.get_chain()
        assert len(chain) >= 1

        # Verify the chain is internally consistent
        integrity = history.verify_chain_integrity()
        assert integrity["all_valid"] is True

    def test_checkpoint_manager_with_lease_integration(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager
        from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager

        lease_mgr = LeaseManager()
        ck_mgr = CheckpointManager(lease_manager=lease_mgr)

        ck = Checkpoint(
            phase="plan",
            swarm_id="lease-swarm",
            task_id="lease-task",
            plan_data=[{"agent_id": "test"}],
        )
        ck_mgr.save(ck)

        # Verify checkpoint was stored
        loaded = ck_mgr.load(ck.checkpoint_id)
        assert loaded is not None
        assert loaded.swarm_id == "lease-swarm"

        # The lease manager should have a lease for this checkpoint
        assert lease_mgr.is_held(f"hlf:checkpoint:{ck.checkpoint_id}")

    def test_plan_history_with_consistency_proof_integration(self) -> None:
        from hlf_mcp.hlf.plan_versioning import PlanHistory
        from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof

        proof = ConsistencyProof()
        history = PlanHistory(consistency_proof=proof)

        history.commit([{"agent_id": "a", "goal": "test"}])
        history.commit([{"agent_id": "b", "goal": "test"}])
        history.commit([{"agent_id": "c", "goal": "test"}])

        result = history.build_consistency_proof()
        assert result is not None
        assert result.witness_count == 0  # Internal check, no external witnesses
        assert result.consistent is True

    def test_checkpoint_eviction_on_max_checkpoints(self) -> None:
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint, CheckpointManager

        mgr = CheckpointManager(max_checkpoints=3)

        ck1 = mgr.save(Checkpoint(phase="plan", swarm_id="s1", task_id="t1"))
        mgr.save(Checkpoint(phase="plan", swarm_id="s2", task_id="t2"))
        mgr.save(Checkpoint(phase="plan", swarm_id="s3", task_id="t3"))
        # This should trigger eviction
        mgr.save(Checkpoint(phase="plan", swarm_id="s4", task_id="t4"))

        assert mgr.get_count() <= 3
        # ck1 may have been evicted
        # The last 3 should be s2, s3, s4 (or similar)
        assert mgr.get_last_checkpoint() is not None

    def test_full_orchestration_stack_end_to_end(self) -> None:
        """Integration test: PlanVersioning + CheckpointManager + MultiPhaseExecutor."""
        from hlf_mcp.hlf.plan_versioning import PlanHistory
        from hlf_mcp.hlf.checkpoint_executor import (
            Checkpoint,
            CheckpointManager,
            CheckpointableExecutor,
        )
        from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof
        from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager

        # Knowledge/memory infrastructure
        lease_mgr = LeaseManager()
        proof = ConsistencyProof()

        # Versioning
        history = PlanHistory(lease_manager=lease_mgr, consistency_proof=proof)

        # Checkpointing
        ck_mgr = CheckpointManager(lease_manager=lease_mgr, consistency_proof=proof)

        # Execution
        executor = CheckpointableExecutor(checkpoint_manager=ck_mgr)

        # Run the full pipeline
        result = executor.run("Check if a number is prime")

        # Record in plan history
        if result.result and result.result.phases:
            plan_phase = result.result.phases[0]
            history.commit(
                [
                    {
                        "agent_id": p.agent_id,
                        "role": p.role,
                        "goal": p.goal,
                        "hlf_source": p.hlf_source,
                        "scope": list(p.scope),
                        "constraints": p.constraints,
                        "capabilities": list(p.capabilities),
                        "dependencies": p.dependencies,
                        "metrics": p.metrics,
                    }
                    for p in plan_phase.agent_plans
                ],
                metadata={
                    "task": "Check if prime",
                    "swarm_id": result.result.swarm_id,
                    "task_id": result.result.task_id,
                    "compile_success": result.result.compile_success,
                },
            )

        # Validate the full stack
        assert history.get_version_count() >= 1
        assert ck_mgr.get_count() >= 2
        chain_integrity = history.verify_chain_integrity()
        assert chain_integrity["all_valid"] is True
        ck_integrity = ck_mgr.verify_all()
        assert ck_integrity["all_valid"] is True


# ═══════════════════════════════════════════════════════════════════════════
# VectorClock tests
# ═══════════════════════════════════════════════════════════════════════════


class TestVectorClock:
    """Validates VectorClock causal ordering primitives."""

    def test_vector_clock_tick_increments_own_counter(self) -> None:
        """Tick should increment the owning node's counter and update timestamp."""
        vc = VectorClock(node_id="node-a")
        old_ts = vc.timestamp
        vc.tick()
        assert vc.counters["node-a"] == 1
        assert vc.timestamp >= old_ts

    def test_vector_clock_merge_takes_elementwise_max(self) -> None:
        """Merge should take the element-wise maximum of all counters."""
        vc1 = VectorClock(node_id="node-a")
        vc1.counters = {"node-a": 3, "node-b": 1, "node-c": 0}
        vc2 = VectorClock(node_id="node-b")
        vc2.counters = {"node-a": 2, "node-b": 5, "node-d": 7}
        vc1.merge(vc2)
        assert vc1.counters["node-a"] == 3
        assert vc1.counters["node-b"] == 5
        assert vc1.counters["node-c"] == 0
        assert vc1.counters["node-d"] == 7

    def test_vector_clock_happened_before_true(self) -> None:
        """A clock with all counters <= and at least one < should be happened-before."""
        vc1 = VectorClock(node_id="node-a")
        vc1.counters = {"node-a": 1, "node-b": 2}
        vc2 = VectorClock(node_id="node-b")
        vc2.counters = {"node-a": 2, "node-b": 3}
        assert vc1.happened_before(vc2) is True
        assert vc2.happened_before(vc1) is False

    def test_vector_clock_happened_before_false_when_concurrent(self) -> None:
        """Neither clock should be happened-before when updates are interleaved."""
        vc1 = VectorClock(node_id="node-a")
        vc1.counters = {"node-a": 3, "node-b": 1}
        vc2 = VectorClock(node_id="node-b")
        vc2.counters = {"node-a": 1, "node-b": 4}
        assert vc1.happened_before(vc2) is False
        assert vc2.happened_before(vc1) is False

    def test_vector_clock_is_concurrent(self) -> None:
        """is_concurrent should return True when neither clock happened-before the other."""
        vc1 = VectorClock(node_id="node-a")
        vc1.counters = {"node-a": 5, "node-b": 0}
        vc2 = VectorClock(node_id="node-b")
        vc2.counters = {"node-a": 0, "node-b": 5}
        assert vc1.is_concurrent(vc2) is True

    def test_vector_clock_roundtrip_to_dict_and_back(self) -> None:
        """VectorClock should survive a to_dict → from_dict round-trip."""
        vc = VectorClock(node_id="node-x")
        vc.counters = {"node-x": 42, "node-y": 7}
        vc.timestamp = 1700000000.0
        d = vc.to_dict()
        restored = VectorClock.from_dict(d)
        assert restored.node_id == "node-x"
        assert restored.counters == {"node-x": 42, "node-y": 7}
        assert restored.timestamp == 1700000000.0
        assert restored.equals(vc)


# ═══════════════════════════════════════════════════════════════════════════
# SwarmLeaderElection tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSwarmLeaderElection:
    """Validates bully-algorithm leader election with vector clocks."""

    def test_leader_election_elects_highest_priority_node(self) -> None:
        """The highest-priority active node should be elected leader."""
        election = SwarmLeaderElection(swarm_id="swarm-1", quorum_size=2)
        election.register_node("node-a", priority=1)
        election.register_node("node-b", priority=10)
        election.register_node("node-c", priority=5)
        result = election.elect()
        assert result.leader_id == "node-b"
        assert result.quorum_reached is True
        assert election.get_current_leader() == "node-b"

    def test_leader_election_quorum_not_reached_with_few_nodes(self) -> None:
        """Quorum should not be reached when fewer active nodes than quorum_size."""
        election = SwarmLeaderElection(swarm_id="swarm-2", quorum_size=5)
        election.register_node("node-a", priority=3)
        election.register_node("node-b", priority=7)
        result = election.elect()
        assert result.quorum_reached is False
        assert result.leader_id == "node-b"  # still elected, but no quorum
        assert election.get_current_leader() is None  # leader not set without quorum

    def test_leader_election_respects_inactive_nodes(self) -> None:
        """Inactive nodes should be excluded from election."""
        election = SwarmLeaderElection(swarm_id="swarm-3", quorum_size=1)
        election.register_node("node-a", priority=100)
        election.register_node("node-b", priority=50)
        election.mark_node_unreachable("node-a")
        result = election.elect()
        assert result.leader_id == "node-b"
        assert "node-a" not in result.participants

    def test_leader_election_deregister_removes_node(self) -> None:
        """Deregistering a node should remove it from the pool and clear leader if it was leader."""
        election = SwarmLeaderElection(swarm_id="swarm-4", quorum_size=1)
        election.register_node("node-a", priority=10)
        election.register_node("node-b", priority=5)
        election.elect()
        assert election.get_current_leader() == "node-a"
        election.deregister_node("node-a")
        assert election.get_current_leader() is None
        assert election.get_node_count() == 1

    def test_leader_election_force_leader_overrides_election(self) -> None:
        """force_leader should override the elected leader and increment the term."""
        election = SwarmLeaderElection(swarm_id="swarm-5", quorum_size=1)
        election.register_node("node-a", priority=10)
        election.register_node("node-b", priority=1)
        election.elect()
        assert election.get_current_leader() == "node-a"
        old_term = election.get_term()
        election.force_leader("node-b")
        assert election.get_current_leader() == "node-b"
        assert election.get_term() == old_term + 1

    def test_leader_election_term_increments(self) -> None:
        """Each election should increment the term number."""
        election = SwarmLeaderElection(swarm_id="swarm-6", quorum_size=1)
        election.register_node("node-a", priority=5)
        r1 = election.elect()
        r2 = election.elect()
        assert r2.term == r1.term + 1

    def test_leader_election_tick_clock_advances_vector(self) -> None:
        """tick_clock should advance the vector clock for a node."""
        election = SwarmLeaderElection(swarm_id="swarm-7", quorum_size=1)
        election.register_node("node-a", priority=5)
        clock = election.tick_clock("node-a")
        assert clock.counters["node-a"] == 1
        clock = election.tick_clock("node-a")
        assert clock.counters["node-a"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# SplitBrainDetector tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSplitBrainDetector:
    """Validates split-brain detection using vector clock divergence."""

    def test_split_brain_no_partition_with_single_node(self) -> None:
        """A single active node should never trigger split-brain detection."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-1", quorum_size=1)
        election.register_node("node-a", priority=5)
        detector = SplitBrainDetector(election)
        report = detector.detect()
        assert report.detected is False
        assert report.recommended_action == "insufficient_nodes_for_partition"

    def test_split_brain_detects_divergent_clocks(self) -> None:
        """Nodes with divergent vector clock hashes should be detected as partitions."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-2", quorum_size=1)
        election.register_node("node-a", priority=5)
        election.register_node("node-b", priority=3)
        # Advance node-a's clock to create divergence
        election.tick_clock("node-a")
        election.tick_clock("node-a")
        election.tick_clock("node-a")
        detector = SplitBrainDetector(election, clock_divergence_threshold=1)
        report = detector.detect()
        assert report.detected is True
        assert len(report.partitions) > 1

    def test_split_brain_stale_leader_in_minority_partition(self) -> None:
        """Leader in a minority partition should be flagged as stale."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-3", quorum_size=1)
        election.register_node("node-a", priority=5)
        election.register_node("node-b", priority=3)
        election.register_node("node-c", priority=2)
        election.elect()  # node-a becomes leader
        # Simulate a partition: node-b and node-c share identical clock state
        # (same causal history = same partition), while node-a is isolated
        shared_counters = {"node-b": 5, "node-c": 5}
        clock_b = VectorClock(node_id="node-b", counters=dict(shared_counters))
        clock_c = VectorClock(node_id="node-c", counters=dict(shared_counters))
        election._vector_clocks["node-b"] = clock_b
        election._vector_clocks["node-c"] = clock_c
        detector = SplitBrainDetector(election, clock_divergence_threshold=1)
        report = detector.detect()
        assert report.stale_leader is True
        assert "re_elect" in report.recommended_action

    def test_split_brain_heal_partition_merges_clocks(self) -> None:
        """Healing a partition should merge all clocks and return True."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-4", quorum_size=1)
        election.register_node("node-a", priority=5)
        election.register_node("node-b", priority=3)
        election.tick_clock("node-a")
        election.tick_clock("node-a")
        election.tick_clock("node-a")
        detector = SplitBrainDetector(election, clock_divergence_threshold=1)
        report = detector.detect()
        assert report.detected is True
        healed = detector.heal_partition(report)
        assert healed is True
        # After healing, both clocks should be merged (node-a's counters propagated)
        clock_b = election.get_clock("node-b")
        assert clock_b is not None
        assert clock_b.counters.get("node-a", 0) >= 3

    def test_split_brain_heartbeat_timeout_triggers_detection(self) -> None:
        """A node with an expired heartbeat should trigger split-brain detection."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-5", quorum_size=1)
        election.register_node("node-a", priority=5)
        election.register_node("node-b", priority=3)
        detector = SplitBrainDetector(election, heartbeat_timeout_seconds=0.0)
        detector.record_heartbeat("node-a")
        # node-b has no heartbeat → timed out immediately with timeout=0
        report = detector.detect()
        assert report.detected is True

    def test_split_brain_record_heartbeat_updates_status(self) -> None:
        """Recording a heartbeat should update the heartbeat status map."""
        election = SwarmLeaderElection(swarm_id="swarm-sb-6", quorum_size=1)
        election.register_node("node-a", priority=5)
        detector = SplitBrainDetector(election)
        detector.record_heartbeat("node-a")
        status = detector.get_heartbeat_status()
        assert "node-a" in status
        assert status["node-a"]["timed_out"] is False


# ═══════════════════════════════════════════════════════════════════════════
# StalePlanCache tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStalePlanCache:
    """Validates version-stamped plan cache with TTL invalidation."""

    def test_stale_plan_cache_put_and_get(self) -> None:
        """Putting an entry and getting it back should return the same data."""
        cache = StalePlanCache(default_ttl=9999.0)
        cache.put("plan-1", {"tasks": ["a", "b"]}, version_stamp=5, node_id="node-a")
        entry = cache.get("plan-1")
        assert entry is not None
        assert entry.plan_data == {"tasks": ["a", "b"]}
        assert entry.version_stamp == 5
        assert entry.node_id == "node-a"

    def test_stale_plan_cache_get_returns_none_for_expired(self) -> None:
        """A TTL-expired entry should return None on get()."""
        cache = StalePlanCache(default_ttl=0.0)
        entry = cache.put("plan-ep", {"x": 1}, version_stamp=1, node_id="node-x")
        # Force the entry to appear expired by back-dating cached_at
        entry.cached_at = 0.0
        result = cache.get("plan-ep")
        assert result is None

    def test_stale_plan_cache_invalidate_stale_removes_old_versions(self) -> None:
        """invalidate_stale should remove entries below the master version."""
        cache = StalePlanCache()
        cache.put("plan-a", {"v": 1}, version_stamp=1, node_id="n1")
        cache.put("plan-b", {"v": 2}, version_stamp=3, node_id="n2")
        cache.put("plan-c", {"v": 3}, version_stamp=5, node_id="n3")
        removed = cache.invalidate_stale(4)
        assert removed == 2  # plan-a (stamp 1) and plan-b (stamp 3) removed
        assert cache.get("plan-a") is None
        assert cache.get("plan-b") is None
        assert cache.get("plan-c") is not None

    def test_stale_plan_cache_invalidate_node_removes_node_entries(self) -> None:
        """invalidate_node should remove all entries from a specific node."""
        cache = StalePlanCache()
        cache.put("plan-1", {"a": 1}, version_stamp=10, node_id="node-x")
        cache.put("plan-2", {"b": 2}, version_stamp=10, node_id="node-y")
        cache.put("plan-3", {"c": 3}, version_stamp=10, node_id="node-x")
        removed = cache.invalidate_node("node-x")
        assert removed == 2
        assert cache.get("plan-1") is None
        assert cache.get("plan-3") is None
        assert cache.get("plan-2") is not None

    def test_stale_plan_cache_expire_ttl_removes_expired(self) -> None:
        """expire_ttl_entries should remove all TTL-expired entries."""
        cache = StalePlanCache(default_ttl=0.0)
        e1 = cache.put("plan-e1", {"d": 1}, version_stamp=10, node_id="n1")
        e2 = cache.put("plan-e2", {"d": 2}, version_stamp=10, node_id="n2")
        e3 = cache.put("plan-e3", {"d": 3}, version_stamp=10, node_id="n3",
                       ttl_seconds=99999.0)
        # Force e1 and e2 to appear expired by back-dating
        e1.cached_at = 0.0
        e2.cached_at = 0.0
        removed = cache.expire_ttl_entries()
        assert removed == 2
        assert cache.get("plan-e3") is not None

    def test_stale_plan_cache_stats_reflect_state(self) -> None:
        """get_stats should accurately reflect cache state."""
        cache = StalePlanCache()
        cache.put("plan-s1", {"x": 1}, version_stamp=1, node_id="n1")
        cache.put("plan-s2", {"x": 2}, version_stamp=3, node_id="n2")
        cache.invalidate_stale(2)
        stats = cache.get_stats()
        assert stats["total_entries"] == 1
        assert stats["total_invalidations"] == 1
        assert stats["master_version"] == 3

    def test_stale_plan_cache_master_version_tracks_highest_stamp(self) -> None:
        """The cache should track the highest version_stamp seen as master version."""
        cache = StalePlanCache()
        cache.put("plan-m1", {"a": 1}, version_stamp=7, node_id="n1")
        assert cache.get_master_version() == 7
        cache.put("plan-m2", {"b": 2}, version_stamp=15, node_id="n2")
        assert cache.get_master_version() == 15
        cache.put("plan-m3", {"c": 3}, version_stamp=3, node_id="n3")
        assert cache.get_master_version() == 15  # should not decrease


# ═══════════════════════════════════════════════════════════════════════════
# CrashRecovery tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCrashRecovery:
    """Validates crash recovery with plan replay from checkpoint."""

    def test_crash_recovery_no_checkpoint_manager_returns_failure(self) -> None:
        """Recovery without a checkpoint manager should return a failure result."""
        recovery = CrashRecovery(checkpoint_manager=None)
        result = recovery.recover_node("node-crash", swarm_id="swarm-1")
        assert result.success is False
        assert "No checkpoint manager" in result.errors[0]
        assert result.node_id == "node-crash"

    def test_crash_recovery_no_checkpoint_returns_failure(self) -> None:
        """Recovery with a manager that has no checkpoint should fail."""
        from unittest.mock import MagicMock
        mock_mgr = MagicMock()
        mock_mgr.get_last_checkpoint.return_value = None
        recovery = CrashRecovery(checkpoint_manager=mock_mgr)
        result = recovery.recover_node("node-crash", swarm_id="swarm-empty")
        assert result.success is False
        assert "No checkpoint found" in result.errors[0]

    def test_crash_recovery_replays_from_checkpoint(self) -> None:
        """A valid checkpoint should allow recovery to replay remaining steps."""
        from unittest.mock import MagicMock
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint
        ck = Checkpoint(
            swarm_id="swarm-rp",
            phase="execute",
            plan_data=[
                {"node_id": "step-1", "task_type": "create_file"},
                {"node_id": "step-2", "task_type": "modify_file"},
                {"node_id": "step-3", "task_type": "run_tests"},
            ],
            agent_states={
                "agent-1": {"completed_steps": ["step-1"]},
            },
        )
        mock_mgr = MagicMock()
        mock_mgr.get_last_checkpoint.return_value = ck
        recovery = CrashRecovery(checkpoint_manager=mock_mgr)
        result = recovery.recover_node("node-a", swarm_id="swarm-rp")
        assert result.success is True
        assert result.checkpoint_id == ck.checkpoint_id
        assert result.replayed_steps == 2  # step-2, step-3 still uncompleted

    def test_crash_recovery_recover_swarm_handles_multiple_nodes(self) -> None:
        """recover_swarm should attempt recovery for each crashed node."""
        from unittest.mock import MagicMock
        from hlf_mcp.hlf.checkpoint_executor import Checkpoint
        ck = Checkpoint(
            swarm_id="swarm-multi",
            plan_data=[{"node_id": "step-1"}],
            agent_states={},
        )
        mock_mgr = MagicMock()
        mock_mgr.get_last_checkpoint.return_value = ck
        recovery = CrashRecovery(checkpoint_manager=mock_mgr)
        results = recovery.recover_swarm(
            "swarm-multi", ["node-a", "node-b", "node-c"]
        )
        assert len(results) == 3
        assert all(r.success for r in results.values())
        assert results["node-a"].node_id == "node-a"

    def test_crash_recovery_replay_plan_empty_returns_failure(self) -> None:
        """Replaying an empty plan should return success=False."""
        recovery = CrashRecovery()
        result = recovery.replay_plan([])
        assert result["success"] is False
        assert result["replayed"] == 0
        assert "Empty plan data" in result["error"]


# ═══════════════════════════════════════════════════════════════════════════
# PlanRebalancer tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanRebalancer:
    """Validates plan rebalancing after node failure."""

    def test_plan_rebalancer_reassigns_orphaned_tasks(self) -> None:
        """Tasks assigned to a failed node should be reassigned to survivors."""
        rebalancer = PlanRebalancer()
        plan = [
            {"node_id": "task-1", "assigned_node": "node-fail"},
            {"node_id": "task-2", "assigned_node": "node-ok"},
            {"node_id": "task-3", "assigned_node": "node-fail"},
        ]
        result = rebalancer.rebalance(
            swarm_id="swarm-rb-1",
            failed_node="node-fail",
            plan_data=plan,
            completed_tasks=set(),
            surviving_nodes=["node-ok", "node-extra"],
        )
        assert len(result.tasks_reassigned) == 2
        assert "task-1" in result.tasks_reassigned
        assert "task-3" in result.tasks_reassigned
        assert len(result.tasks_lost) == 0

    def test_plan_rebalancer_preserves_completed_tasks(self) -> None:
        """Already-completed tasks should not be reassigned."""
        rebalancer = PlanRebalancer()
        plan = [
            {"node_id": "task-1", "assigned_node": "node-fail"},
            {"node_id": "task-2", "assigned_node": "node-fail"},
            {"node_id": "task-3", "assigned_node": "node-fail"},
        ]
        result = rebalancer.rebalance(
            swarm_id="swarm-rb-2",
            failed_node="node-fail",
            plan_data=plan,
            completed_tasks={"task-1", "task-3"},
            surviving_nodes=["node-survivor"],
        )
        assert "task-2" in result.tasks_reassigned
        # Completed tasks appear in preserved (both from initial list and from
        # the orphan loop, which can double-count if the task was on failed node)
        assert "task-1" in result.tasks_preserved
        assert "task-3" in result.tasks_preserved
        assert len(result.tasks_lost) == 0

    def test_plan_rebalancer_tasks_lost_when_no_survivors(self) -> None:
        """Tasks should be lost when there are no surviving nodes available."""
        rebalancer = PlanRebalancer()
        plan = [
            {"node_id": "task-1", "assigned_node": "node-fail"},
            {"node_id": "task-2", "assigned_node": "node-fail"},
        ]
        result = rebalancer.rebalance(
            swarm_id="swarm-rb-3",
            failed_node="node-fail",
            plan_data=plan,
            completed_tasks=set(),
            surviving_nodes=[],
        )
        assert len(result.tasks_lost) == 2
        assert len(result.tasks_reassigned) == 0

    def test_plan_rebalancer_affinity_map_prefers_best_node(self) -> None:
        """When an affinity map exists, the best node should be chosen."""
        affinity = TaskAffinityMap(
            task_id="task-1",
            preferred_nodes=["node-specialized", "node-general"],
            capability_match_scores={"node-specialized": 0.95, "node-general": 0.4},
        )
        rebalancer = PlanRebalancer()
        rebalancer.register_affinity(affinity)
        plan = [{"node_id": "task-1", "assigned_node": "node-fail"}]
        result = rebalancer.rebalance(
            swarm_id="swarm-rb-4",
            failed_node="node-fail",
            plan_data=plan,
            completed_tasks=set(),
            surviving_nodes=["node-general", "node-specialized"],
        )
        assert result.new_node_assignments.get("task-1") == "node-specialized"

    def test_plan_rebalancer_build_rebalanced_plan_updates_assignments(self) -> None:
        """build_rebalanced_plan should update node assignments in plan data."""
        rebalancer = PlanRebalancer()
        plan = [
            {"node_id": "task-a", "assigned_node": "node-old"},
            {"node_id": "task-b", "assigned_node": "node-ok"},
        ]
        rebalanced = rebalancer.build_rebalanced_plan(
            plan, {"task-a": "node-new"}
        )
        assert rebalanced[0]["assigned_node"] == "node-new"
        assert rebalanced[0]["rebalanced"] is True
        assert rebalanced[1]["assigned_node"] == "node-ok"
        assert "rebalanced" not in rebalanced[1]

    def test_plan_rebalancer_validate_integrity_checksum_matches(self) -> None:
        """A freshly created RebalanceResult should validate with matching checksum."""
        rebalancer = PlanRebalancer()
        plan = [{"node_id": "task-1", "assigned_node": "node-fail"}]
        result = rebalancer.rebalance(
            swarm_id="swarm-rb-6",
            failed_node="node-fail",
            plan_data=plan,
            completed_tasks=set(),
            surviving_nodes=["node-survivor"],
        )
        assert rebalancer.validate_rebalance_integrity(result) is True


# ═══════════════════════════════════════════════════════════════════════════
# SwarmHandoff tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSwarmHandoff:
    """Validates swarm-to-swarm handoff lifecycle."""

    def test_swarm_handoff_negotiate_creates_contract(self) -> None:
        """Negotiating a handoff should create a valid contract in NEGOTIATING state."""
        manager = SwarmHandoffManager()
        contract = manager.negotiate(
            source_swarm="swarm-alpha",
            target_swarm="swarm-beta",
            required_capabilities=["code_generation", "test_execution"],
        )
        assert contract.source_swarm == "swarm-alpha"
        assert contract.target_swarm == "swarm-beta"
        assert contract.required_gates == ["cove_review"]
        status = manager.get_status(contract.contract_id)
        assert status["status"] == HandoffStatus.NEGOTIATING.value

    def test_swarm_handoff_provide_attestation_satisfies_requirements(self) -> None:
        """A valid attestation that meets requirements should be accepted."""
        manager = SwarmHandoffManager()
        contract = manager.negotiate(
            source_swarm="swarm-a",
            target_swarm="swarm-b",
            required_capabilities=["code_gen", "testing"],
        )
        attestation = CapabilityAttestation(
            swarm_id="swarm-b",
            capabilities={"code_gen": 0.9, "testing": 0.8, "deploy": 0.3},
            attested_by="cove-gate",
        )
        result = manager.provide_attestation(contract.contract_id, attestation)
        assert result is True
        status = manager.get_status(contract.contract_id)
        assert status["attestation_provided"] is True

    def test_swarm_handoff_complete_handoff_issues_receipt(self) -> None:
        """Completing an accepted handoff should issue a HandoffReceipt."""
        manager = SwarmHandoffManager()
        contract = manager.negotiate(
            source_swarm="swarm-src",
            target_swarm="swarm-tgt",
            required_capabilities=["build"],
        )
        attestation = CapabilityAttestation(
            swarm_id="swarm-tgt",
            capabilities={"build": 0.7},
            attested_by="gateway",
        )
        manager.provide_attestation(contract.contract_id, attestation)
        manager.validate_gate(contract.contract_id, "cove_review", True)
        receipt = manager.complete_handoff(
            contract.contract_id,
            payload={"tasks": ["migrate_db", "update_config"]},
            issuer="operator",
        )
        assert receipt is not None
        assert receipt.status == HandoffStatus.COMPLETED.value
        assert receipt.source_swarm == "swarm-src"
        assert receipt.target_swarm == "swarm-tgt"
        assert receipt.issuer == "operator"
        assert receipt.payload_hash != ""

    def test_swarm_handoff_abort_handoff_issues_abort_receipt(self) -> None:
        """Aborting a handoff should issue a receipt with ABORTED status."""
        manager = SwarmHandoffManager()
        contract = manager.negotiate(
            source_swarm="swarm-x",
            target_swarm="swarm-y",
            required_capabilities=["analyze"],
        )
        receipt = manager.abort_handoff(
            contract.contract_id,
            reason="target_swarm_unreachable",
            issuer="scheduler",
        )
        assert receipt is not None
        assert receipt.status == HandoffStatus.ABORTED.value
        assert receipt.issuer == "scheduler"
        assert len(receipt.gate_results) == 1
        assert receipt.gate_results[0]["gate"] == "abort"

    def test_swarm_handoff_receipt_verify_signature(self) -> None:
        """A HandoffReceipt should self-verify its signature."""
        receipt = HandoffReceipt(
            contract_id="contract-verify",
            source_swarm="swarm-1",
            target_swarm="swarm-2",
            status=HandoffStatus.COMPLETED.value,
            payload_hash="abc123",
            attestation_hash="def456",
            gate_results=[{"gate": "cove_review", "passed": True, "detail": "ok"}],
            issuer="gateway",
        )
        assert receipt.verify() is True

    def test_swarm_handoff_check_timeouts_expires_overdue(self) -> None:
        """Overdue handoffs should be detected and timed out."""
        manager = SwarmHandoffManager(default_timeout=0.0)
        contract = manager.negotiate(
            source_swarm="swarm-p",
            target_swarm="swarm-q",
            required_capabilities=["scan"],
            timeout_seconds=0.0,
        )
        # Force the contract to appear expired by back-dating created_at
        contract.created_at = 0.0
        timed_out = manager.check_timeouts()
        assert contract.contract_id in timed_out
        status = manager.get_status(contract.contract_id)
        assert status["status"] == HandoffStatus.TIMED_OUT.value

    def test_swarm_handoff_capability_attestation_is_valid(self) -> None:
        """A CapabilityAttestation within its validity window should be valid."""
        now = time.time()
        attestation = CapabilityAttestation(
            swarm_id="swarm-v",
            capabilities={"code_gen": 0.95, "review": 0.88},
            attested_by="cove",
            valid_from=now - 100,
            valid_until=now + 86400,
        )
        assert attestation.is_valid(now) is True
        assert attestation.is_valid(now - 200) is False  # before valid_from
        assert attestation.verify_integrity() is True

    def test_swarm_handoff_status_enum_values(self) -> None:
        """HandoffStatus enum should contain all expected lifecycle values."""
        assert HandoffStatus.PENDING.value == "pending"
        assert HandoffStatus.NEGOTIATING.value == "negotiating"
        assert HandoffStatus.ATTESTING.value == "attesting"
        assert HandoffStatus.ACCEPTED.value == "accepted"
        assert HandoffStatus.REJECTED.value == "rejected"
        assert HandoffStatus.TIMED_OUT.value == "timed_out"
        assert HandoffStatus.ABORTED.value == "aborted"
        assert HandoffStatus.COMPLETED.value == "completed"

