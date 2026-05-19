"""Tests for MultiPhaseExecutor: three-phase execution with consolidation."""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.multi_phase_executor import (
    MultiPhaseExecutor,
    MultiPhaseResult,
    AgentPlan,
    ConsolidationEngine,
    Conflict,
    ConsolidatedPlan,
    PhaseResult,
)


@pytest.fixture
def executor() -> MultiPhaseExecutor:
    return MultiPhaseExecutor()


@pytest.fixture
def engine() -> ConsolidationEngine:
    return ConsolidationEngine()


class TestPlanPhase:
    """Phase 1: PLAN — agents produce individual plans."""

    def test_plan_phase_produces_plans(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Write a hello world function")
        assert len(plans) == 3
        for plan in plans:
            assert isinstance(plan, AgentPlan)
            assert plan.agent_id
            assert plan.hlf_source
            assert "Ω" in plan.hlf_source

    def test_plan_phase_custom_agents(self, executor: MultiPhaseExecutor) -> None:
        agents = ["builder", "tester"]
        plans = executor.plan_phase("Build a REST API", agents=agents)
        assert len(plans) == 2
        assert {p.agent_id for p in plans} == {"builder", "tester"}

    def test_plan_phase_has_metrics(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Sort a list")
        for plan in plans:
            assert "hlf_tokens" in plan.metrics
            assert "compile_success" in plan.metrics
            assert plan.metrics["hlf_tokens"] > 0


class TestConsolidatePhase:
    """Phase 2: CONSOLIDATE — merge and detect conflicts."""

    def test_consolidate_produces_result(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Calculate factorial")
        result = executor.consolidate_phase(plans)
        assert isinstance(result, ConsolidatedPlan)
        assert len(result.merged_plans) > 0
        assert result.hlf_source

    def test_consolidate_has_execution_order(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Parse JSON")
        result = executor.consolidate_phase(plans)
        assert len(result.execution_order) > 0
        assert all(aid in {p.agent_id for p in plans} for aid in result.execution_order)

    def test_consolidate_metrics(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Validate email")
        result = executor.consolidate_phase(plans)
        assert "plan_count" in result.metrics
        assert "merged_count" in result.metrics
        assert "conflict_count" in result.metrics
        assert result.metrics["plan_count"] == len(plans)


class TestExecutePhase:
    """Phase 3: EXECUTE — execute consolidated plan."""

    def test_execute_phase_succeeds(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Reverse a string")
        consolidated = executor.consolidate_phase(plans)
        result = executor.execute_phase(consolidated)
        assert isinstance(result, PhaseResult)
        assert result.status == "complete"
        assert result.metrics.get("verification_checks", -1) >= 0

    def test_execute_phase_gate_decision(self, executor: MultiPhaseExecutor) -> None:
        plans = executor.plan_phase("Find max in array")
        consolidated = executor.consolidate_phase(plans)
        result = executor.execute_phase(consolidated)
        assert "gate_decision" in result.metrics


class TestMultiPhaseRun:
    """Full three-phase execution."""

    def test_run_multi_phase_returns_result(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Check if prime")
        assert isinstance(result, MultiPhaseResult)
        assert result.swarm_id
        assert result.task_id

    def test_run_has_three_phases(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Count words")
        phase_ids = [p.phase_id for p in result.phases]
        assert phase_ids == ["plan", "consolidate", "execute"]

    def test_total_tokens_positive(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Parse CSV")
        assert result.total_tokens > 0

    def test_total_time_positive(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Sort names")
        assert result.total_time_ms > 0

    def test_skip_consolidation(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Hello world", skip_consolidation=True)
        con_phase = next(p for p in result.phases if p.phase_id == "consolidate")
        assert con_phase.status == "skipped"
        assert con_phase.metrics.get("skipped") is True

    def test_consolidation_metrics_present(self, executor: MultiPhaseExecutor) -> None:
        result = executor.run_multi_phase("Validate URL")
        assert "plan_count" in result.consolidation_metrics


class TestConsolidationEngine:
    """Unit tests for ConsolidationEngine."""

    def test_detect_duplicates_empty(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="planner", goal="X", hlf_source="Ω", scope={"a.txt"}),
        ]
        groups = engine.detect_duplicates(plans)
        assert groups == []

    def test_detect_duplicates_finds_match(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="planner", goal="Build API", hlf_source="Ω", scope={"api.py"}),
            AgentPlan(agent_id="b", role="planner", goal="Build API", hlf_source="Ω", scope={"api.py"}),
        ]
        groups = engine.detect_duplicates(plans)
        assert len(groups) >= 1
        assert "a" in groups[0] and "b" in groups[0]

    def test_detect_conflicts_scope_overlap(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="executor", goal="Write", hlf_source="Ω", scope={"file.py"}),
            AgentPlan(agent_id="b", role="executor", goal="Other", hlf_source="Ω", scope={"file.py"}),
        ]
        conflicts = engine.detect_conflicts(plans)
        scope_conflicts = [c for c in conflicts if c.kind == "scope_overlap"]
        assert len(scope_conflicts) >= 1

    def test_detect_conflicts_dependency_cycle(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="planner", goal="X", hlf_source="Ω", dependencies=["b"]),
            AgentPlan(agent_id="b", role="executor", goal="X", hlf_source="Ω", dependencies=["a"]),
        ]
        conflicts = engine.detect_conflicts(plans)
        cycle_conflicts = [c for c in conflicts if c.kind == "dependency_cycle"]
        assert len(cycle_conflicts) >= 1

    def test_merge_compatible_non_overlapping(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="planner", goal="Build", hlf_source="Ω", scope={"a.py"}),
            AgentPlan(agent_id="b", role="researcher", goal="Build", hlf_source="Ω", scope={"b.py"}),
        ]
        merged = engine.merge_compatible(plans)
        assert len(merged) <= 2

    def test_build_execution_order_respects_deps(self, engine: ConsolidationEngine) -> None:
        plans = [
            AgentPlan(agent_id="a", role="planner", goal="X", hlf_source="Ω", dependencies=[]),
            AgentPlan(agent_id="b", role="executor", goal="X", hlf_source="Ω", dependencies=["a"]),
        ]
        order = engine.build_execution_order(plans)
        assert order.index("a") < order.index("b")


class TestConflict:
    """Conflict dataclass tests."""

    def test_conflict_fields(self) -> None:
        c = Conflict(
            kind="scope_overlap",
            plan_a="agent1",
            plan_b="agent2",
            description="Both write to shared.txt",
        )
        assert c.kind == "scope_overlap"
        assert c.severity == "warning"
        assert c.plan_a == "agent1"
        assert c.plan_b == "agent2"


class TestAgentPlan:
    """AgentPlan dataclass tests."""

    def test_agent_plan_defaults(self) -> None:
        plan = AgentPlan(agent_id="test", role="tester", goal="test", hlf_source="Ω")
        assert plan.scope == set()
        assert plan.constraints == []
        assert plan.capabilities == set()
        assert plan.dependencies == []
