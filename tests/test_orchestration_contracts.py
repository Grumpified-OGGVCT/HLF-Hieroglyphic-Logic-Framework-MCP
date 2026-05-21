"""
Tests for orchestration contracts — delegation, dissent, escalation, handoff,
and plan decomposition.

Covers:
  - DelegationContract validation (valid, self-delegation, empty scope)
  - DissentRecord creation and resolution
  - EscalationPath severity-based auto-escalation
  - HandoffContract lineage validation and self-handoff rejection
  - Plan decomposition with DAG ordering, parallel grouping, role boundaries
  - Step ordering validation (violations and valid plans)
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.orchestration_contracts import (
    DelegationContract,
    DissentRecord,
    EscalationPath,
    HandoffContract,
    build_escalation_path,
    build_handoff,
    record_dissent,
    resolve_dissent,
    validate_delegation,
)
from hlf_mcp.hlf.plan_decomposition import (
    DecomposedPlan,
    PlanStep,
    decompose_plan,
    validate_step_ordering,
)


# ═══════════════════════════════════════════════════════════════════════════
# DelegationContract tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDelegationContract:
    """Validates DelegationContract construction and validation rules."""

    def test_valid_delegation_contract(self) -> None:
        """A valid delegation with different agents, scope, and constraints."""
        contract = validate_delegation(
            delegator="planner",
            delegate="executor",
            scope="Build the authentication module",
            constraints=["no_prod_changes", "review_required"],
        )
        assert contract.is_valid is True
        assert contract.failures == []
        assert contract.delegator == "planner"
        assert contract.delegate == "executor"
        assert contract.scope == "Build the authentication module"
        assert "no_prod_changes" in contract.constraints
        assert "review_required" in contract.constraints

    def test_self_delegation_rejected(self) -> None:
        """A delegator cannot delegate to itself."""
        contract = validate_delegation(
            delegator="planner",
            delegate="planner",
            scope="Plan the next sprint",
            constraints=["timebox_2h"],
        )
        assert contract.is_valid is False
        assert len(contract.failures) > 0
        assert any("self-delegation" in f.lower() or "cannot delegate to itself" in f.lower()
                   for f in contract.failures)

    def test_empty_scope_delegation_rejected(self) -> None:
        """Delegation with an empty scope must be rejected."""
        contract = validate_delegation(
            delegator="planner",
            delegate="executor",
            scope="",
            constraints=["timebox_2h"],
        )
        assert contract.is_valid is False
        assert any("scope" in f.lower() for f in contract.failures)

    def test_empty_constraints_delegation_rejected(self) -> None:
        """Delegation with no constraints must be rejected."""
        contract = validate_delegation(
            delegator="planner",
            delegate="executor",
            scope="Do something",
            constraints=[],
        )
        assert contract.is_valid is False
        assert any("constraint" in f.lower() for f in contract.failures)

    def test_delegation_with_handoff_lineage_chain(self) -> None:
        """Delegation preserves the full handoff lineage chain."""
        contract = validate_delegation(
            delegator="executor",
            delegate="cove",
            scope="Verify deployment",
            constraints=["all_tests_pass"],
            handoff_lineage=["planner", "strategist", "executor"],
        )
        assert contract.is_valid is True
        assert contract.handoff_lineage == ["planner", "strategist", "executor"]
        assert contract.delegator == "executor"
        assert contract.delegate == "cove"

    def test_delegation_to_dict_roundtrip(self) -> None:
        """to_dict preserves all fields."""
        contract = validate_delegation(
            delegator="herald",
            delegate="scribe",
            scope="Document the API",
            constraints=["must_be_markdown"],
            handoff_lineage=["planner"],
        )
        d = contract.to_dict()
        assert d["delegator"] == "herald"
        assert d["delegate"] == "scribe"
        assert d["scope"] == "Document the API"
        assert d["constraints"] == ["must_be_markdown"]
        assert d["handoff_lineage"] == ["planner"]
        assert d["is_valid"] is True
        assert d["failures"] == []


# ═══════════════════════════════════════════════════════════════════════════
# DissentRecord tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDissentRecord:
    """Validates DissentRecord creation, levels, and resolution."""

    def test_dissent_record_created_with_correct_level(self) -> None:
        """A dissent record captures the correct escalation level."""
        record = record_dissent(
            agent="cove",
            reason="Test coverage below threshold",
            evidence={"coverage_pct": 72, "threshold": 80},
            level=1,
        )
        assert record.agent == "cove"
        assert record.escalation_level == 1
        assert record.is_resolved is False
        assert record.evidence["coverage_pct"] == 72
        assert record.evidence["threshold"] == 80

    def test_level_2_dissent_has_is_resolved_false_initially(self) -> None:
        """A level-2 (block) dissent starts unresolved."""
        record = record_dissent(
            agent="sentinel",
            reason="Security vulnerability detected",
            evidence={"cve": "CVE-2024-0001"},
            level=2,
            proposed_alternative="Rollback to v2.3.1",
        )
        assert record.escalation_level == 2
        assert record.is_resolved is False
        assert record.proposed_alternative == "Rollback to v2.3.1"

    def test_level_0_dissent_is_note(self) -> None:
        """Level 0 is informational only."""
        record = record_dissent(
            agent="scribe",
            reason="Typo in documentation",
            evidence={"file": "README.md", "line": 42},
            level=0,
        )
        assert record.escalation_level == 0
        assert record.is_resolved is False

    def test_resolve_dissent_marks_resolved(self) -> None:
        """resolve_dissent sets is_resolved=True and records resolution."""
        record = record_dissent(
            agent="cove",
            reason="Missing edge case test",
            evidence={"test_file": "test_auth.py"},
            level=1,
        )
        assert record.is_resolved is False

        resolved = resolve_dissent(record, "Added test_auth.py::test_edge_case_empty_token")
        assert resolved.is_resolved is True
        assert resolved.agent == record.agent
        assert resolved.reason == record.reason
        assert resolved.escalation_level == record.escalation_level
        assert resolved.evidence.get("resolution") == "Added test_auth.py::test_edge_case_empty_token"
        # Original record is unchanged
        assert record.is_resolved is False

    def test_dissent_record_to_dict(self) -> None:
        """to_dict preserves all fields including proposed_alternative."""
        record = record_dissent(
            agent="strategist",
            reason="Plan exceeds budget",
            evidence={"budget": 100, "estimated": 150},
            level=1,
            proposed_alternative="Split into two sprints",
        )
        d = record.to_dict()
        assert d["agent"] == "strategist"
        assert d["reason"] == "Plan exceeds budget"
        assert d["escalation_level"] == 1
        assert d["proposed_alternative"] == "Split into two sprints"
        assert d["is_resolved"] is False


# ═══════════════════════════════════════════════════════════════════════════
# EscalationPath tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEscalationPath:
    """Validates EscalationPath severity-based auto-escalation behaviour."""

    def test_escalation_path_critical_severity_auto_escalates(self) -> None:
        """Critical severity sets auto_escalate=True."""
        path = build_escalation_path(
            source="executor",
            target="operator",
            reason="Production deployment failed",
            severity="critical",
        )
        assert path.severity == "critical"
        assert path.auto_escalate is True
        assert path.source == "executor"
        assert path.target == "operator"

    def test_escalation_path_info_severity_does_not_auto_escalate(self) -> None:
        """Info severity does NOT auto-escalate."""
        path = build_escalation_path(
            source="scribe",
            target="herald",
            reason="Documentation build warning",
            severity="info",
        )
        assert path.severity == "info"
        assert path.auto_escalate is False

    def test_escalation_path_warning_severity_does_not_auto_escalate(self) -> None:
        """Warning severity does NOT auto-escalate (manual ack expected)."""
        path = build_escalation_path(
            source="cove",
            target="sentinel",
            reason="Test flakiness detected",
            severity="warning",
        )
        assert path.severity == "warning"
        assert path.auto_escalate is False

    def test_escalation_path_with_timeout(self) -> None:
        """Timeout can be set on escalation path."""
        path = build_escalation_path(
            source="executor",
            target="operator",
            reason="Stuck build",
            severity="warning",
            timeout_seconds=300,
        )
        assert path.timeout_seconds == 300
        assert path.auto_escalate is False

    def test_escalation_path_to_dict(self) -> None:
        """to_dict preserves all fields."""
        path = build_escalation_path(
            source="sentinel",
            target="operator",
            reason="Intrusion detected",
            severity="critical",
            timeout_seconds=60,
        )
        d = path.to_dict()
        assert d["source"] == "sentinel"
        assert d["target"] == "operator"
        assert d["severity"] == "critical"
        assert d["auto_escalate"] is True
        assert d["timeout_seconds"] == 60


# ═══════════════════════════════════════════════════════════════════════════
# HandoffContract tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHandoffContract:
    """Validates HandoffContract lineage validation and self-handoff rejection."""

    def test_handoff_contract_validates_no_self_handoff(self) -> None:
        """A handoff where from_agent appears in lineage is rejected."""
        contract = build_handoff(
            from_agent="executor",
            to_agent="cove",
            context={"task_id": "task-1", "status": "complete"},
            lineage=["planner", "executor", "scribe"],
        )
        assert contract.accepted is False
        assert contract.from_agent == "executor"
        assert contract.to_agent == "cove"
        assert "executor" in contract.lineage

    def test_handoff_direct_self_handoff_rejected(self) -> None:
        """from_agent == to_agent is rejected."""
        contract = build_handoff(
            from_agent="planner",
            to_agent="planner",
            context={"task_id": "task-2"},
            lineage=[],
        )
        assert contract.accepted is False

    def test_handoff_lineage_preserved(self) -> None:
        """Lineage chain is preserved in the contract."""
        lineage = ["planner", "strategist", "scribe"]
        contract = build_handoff(
            from_agent="executor",
            to_agent="cove",
            context={"task_id": "task-3"},
            lineage=lineage,
        )
        assert contract.lineage == lineage
        assert contract.accepted is True  # executor not in lineage
        assert len(contract.lineage) == 3

    def test_handoff_with_non_empty_context_snapshot(self) -> None:
        """Context snapshot is preserved in the handoff contract."""
        context = {
            "task_id": "task-42",
            "status": "in_progress",
            "files_modified": ["src/auth.py", "tests/test_auth.py"],
            "decisions_made": 3,
        }
        contract = build_handoff(
            from_agent="executor",
            to_agent="cove",
            context=context,
            lineage=["planner"],
            open_decisions=["Should we use JWT or sessions?"],
        )
        assert contract.accepted is True
        assert contract.context_snapshot == context
        assert contract.open_decisions == ["Should we use JWT or sessions?"]
        assert contract.acceptance_evidence is None

    def test_handoff_accepted_when_lineage_clean(self) -> None:
        """A clean handoff with no self-reference is accepted."""
        contract = build_handoff(
            from_agent="scribe",
            to_agent="herald",
            context={"doc": "spec.md"},
            lineage=["planner", "strategist", "executor", "cove"],
        )
        assert contract.accepted is True
        assert contract.from_agent == "scribe"
        assert contract.to_agent == "herald"

    def test_handoff_to_dict(self) -> None:
        """to_dict preserves all fields."""
        contract = build_handoff(
            from_agent="cove",
            to_agent="herald",
            context={"verified": True},
            lineage=["planner", "executor", "cove"],
            open_decisions=["version bump required"],
        )
        d = contract.to_dict()
        assert d["from_agent"] == "cove"
        assert d["to_agent"] == "herald"
        assert d["accepted"] is False  # cove in lineage
        assert d["lineage"] == ["planner", "executor", "cove"]
        assert d["open_decisions"] == ["version bump required"]
        assert d["context_snapshot"] == {"verified": True}


# ═══════════════════════════════════════════════════════════════════════════
# Plan Decomposition tests
# ═══════════════════════════════════════════════════════════════════════════


class TestPlanDecomposition:
    """Validates plan decomposition with DAG ordering, parallel grouping,
    and role boundary detection."""

    def test_plan_decomposition_orders_steps_simple_dag(self) -> None:
        """Simple DAG: A → B, A → C. Execution order: [A], [B, C]."""
        steps: list[dict] = [
            {"step_id": "A", "agent_role": "planner", "dependencies": []},
            {"step_id": "B", "agent_role": "executor", "dependencies": ["A"]},
            {"step_id": "C", "agent_role": "scribe", "dependencies": ["A"]},
        ]
        plan = decompose_plan(steps)
        assert len(plan.execution_order) == 2
        # First wave: A
        assert plan.execution_order[0] == ["A"]
        # Second wave: B and C (parallel)
        assert set(plan.execution_order[1]) == {"B", "C"}

    def test_plan_decomposition_groups_parallel_steps(self) -> None:
        """Steps with no interdependencies at same depth are grouped."""
        steps: list[dict] = [
            {"step_id": "root", "agent_role": "planner", "dependencies": []},
            {"step_id": "left", "agent_role": "executor", "dependencies": ["root"]},
            {"step_id": "right", "agent_role": "executor", "dependencies": ["root"]},
            {"step_id": "merge", "agent_role": "cove", "dependencies": ["left", "right"]},
        ]
        plan = decompose_plan(steps)
        assert plan.execution_order[0] == ["root"]
        assert set(plan.execution_order[1]) == {"left", "right"}
        assert plan.execution_order[2] == ["merge"]

    def test_role_boundaries_detected_correctly(self) -> None:
        """Role boundaries are detected when agent_role differs across deps."""
        steps: list[dict] = [
            {"step_id": "plan", "agent_role": "planner", "dependencies": []},
            {"step_id": "build", "agent_role": "executor", "dependencies": ["plan"]},
            {"step_id": "verify", "agent_role": "cove", "dependencies": ["build"]},
        ]
        plan = decompose_plan(steps)
        # planner→executor at "build", executor→cove at "verify"
        assert len(plan.role_boundaries) == 2
        boundaries_by_step = {b["at_step"]: b for b in plan.role_boundaries}
        assert boundaries_by_step["build"] == {
            "from_role": "planner",
            "to_role": "executor",
            "at_step": "build",
        }
        assert boundaries_by_step["verify"] == {
            "from_role": "executor",
            "to_role": "cove",
            "at_step": "verify",
        }

    def test_role_boundaries_not_detected_same_role(self) -> None:
        """No role boundaries when all steps have the same role."""
        steps: list[dict] = [
            {"step_id": "A", "agent_role": "executor", "dependencies": []},
            {"step_id": "B", "agent_role": "executor", "dependencies": ["A"]},
            {"step_id": "C", "agent_role": "executor", "dependencies": ["B"]},
        ]
        plan = decompose_plan(steps)
        assert len(plan.role_boundaries) == 0

    def test_step_ordering_validation_passes_for_valid_plan(self) -> None:
        """validate_step_ordering returns empty list for a valid plan."""
        steps: list[dict] = [
            {"step_id": "X", "agent_role": "planner", "dependencies": []},
            {"step_id": "Y", "agent_role": "executor", "dependencies": ["X"]},
            {"step_id": "Z", "agent_role": "cove", "dependencies": ["Y"]},
        ]
        plan = decompose_plan(steps)
        violations = validate_step_ordering(plan)
        assert violations == []

    def test_step_ordering_validation_catches_dependency_violation(self) -> None:
        """validate_step_ordering catches a step depending on a later step."""
        # Create a DecomposedPlan with a deliberately bad execution order:
        # Y depends on X but X appears after Y
        plan = DecomposedPlan(
            steps=[
                PlanStep(step_id="X", agent_role="planner", dependencies=[]),
                PlanStep(step_id="Y", agent_role="executor", dependencies=["X"]),
            ],
            execution_order=[["Y"], ["X"]],  # BAD: Y before X
            role_boundaries=[],
        )
        violations = validate_step_ordering(plan)
        assert len(violations) > 0
        assert any(
            "depends on" in v.lower() and "not in an earlier wave" in v.lower()
            for v in violations
        )

    def test_plan_decomposition_empty_steps(self) -> None:
        """Empty step list produces empty plan."""
        plan = decompose_plan([])
        assert plan.steps == []
        assert plan.execution_order == []
        assert plan.role_boundaries == []

    def test_plan_decomposition_cycle_detection(self) -> None:
        """Dependency cycle raises ValueError."""
        steps: list[dict] = [
            {"step_id": "A", "agent_role": "planner", "dependencies": ["B"]},
            {"step_id": "B", "agent_role": "executor", "dependencies": ["A"]},
        ]
        with pytest.raises(ValueError, match="cycle"):
            decompose_plan(steps)

    def test_plan_decomposition_unknown_dependency_raises(self) -> None:
        """Depending on a non-existent step raises ValueError."""
        steps: list[dict] = [
            {"step_id": "A", "agent_role": "planner", "dependencies": ["NONEXISTENT"]},
        ]
        with pytest.raises(ValueError, match="unknown step"):
            decompose_plan(steps)

    def test_decomposed_plan_to_dict(self) -> None:
        """to_dict produces correct structure."""
        steps: list[dict] = [
            {"step_id": "P", "agent_role": "planner", "dependencies": []},
            {"step_id": "E", "agent_role": "executor", "dependencies": ["P"]},
        ]
        plan = decompose_plan(steps)
        d = plan.to_dict()
        assert len(d["steps"]) == 2
        assert d["execution_order"] == [["P"], ["E"]]
        assert len(d["role_boundaries"]) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Integration-style tests
# ═══════════════════════════════════════════════════════════════════════════


class TestContractIntegration:
    """End-to-end contract flows combining multiple contract types."""

    def test_full_delegation_to_handoff_flow(self) -> None:
        """Delegation → handoff chain works end to end."""
        # Planner delegates to executor
        delegation = validate_delegation(
            delegator="planner",
            delegate="executor",
            scope="Implement auth module",
            constraints=["test_coverage_80pct", "no_prod_secrets"],
        )
        assert delegation.is_valid is True

        # Executor hands off to CoVE for verification
        # Lineage contains only PRIOR agents (planner), not the current from_agent
        handoff = build_handoff(
            from_agent="executor",
            to_agent="cove",
            context={"task_id": "auth-1", "files": ["src/auth.py"]},
            lineage=["planner"],
            open_decisions=["JWT expiry duration"],
        )
        assert handoff.accepted is True
        assert handoff.from_agent not in handoff.lineage

    def test_dissent_escalation_to_resolution_flow(self) -> None:
        """Dissent → escalation path → resolution."""
        # CoVE dissents at level 2 (block)
        dissent = record_dissent(
            agent="cove",
            reason="Auth module missing rate limiting",
            evidence={"requirement": "SEC-004", "status": "missing"},
            level=2,
            proposed_alternative="Add rate limiting before merge",
        )
        assert dissent.escalation_level == 2
        assert dissent.is_resolved is False

        # Build escalation path for this dissent
        escalation = build_escalation_path(
            source="cove",
            target="sentinel",
            reason=dissent.reason,
            severity="critical",
            timeout_seconds=120,
        )
        assert escalation.auto_escalate is True
        assert escalation.target == "sentinel"

        # Resolve the dissent
        resolved = resolve_dissent(dissent, "Rate limiting added in PR #42")
        assert resolved.is_resolved is True

    def test_complex_dag_with_role_boundaries(self) -> None:
        """A realistic multi-role DAG with proper ordering and boundaries."""
        steps: list[dict] = [
            {"step_id": "spec", "agent_role": "planner", "dependencies": []},
            {"step_id": "design", "agent_role": "strategist", "dependencies": ["spec"]},
            {"step_id": "impl_a", "agent_role": "executor", "dependencies": ["design"]},
            {"step_id": "impl_b", "agent_role": "executor", "dependencies": ["design"]},
            {"step_id": "test_a", "agent_role": "cove", "dependencies": ["impl_a"]},
            {"step_id": "test_b", "agent_role": "cove", "dependencies": ["impl_b"]},
            {"step_id": "merge", "agent_role": "consolidator", "dependencies": ["test_a", "test_b"]},
            {"step_id": "release", "agent_role": "herald", "dependencies": ["merge"]},
        ]
        plan = decompose_plan(steps)

        # Validate ordering
        violations = validate_step_ordering(plan)
        assert violations == []

        # Check waves: spec → design → (impl_a, impl_b) → (test_a, test_b) → merge → release
        assert len(plan.execution_order) == 6
        assert plan.execution_order[0] == ["spec"]
        assert plan.execution_order[1] == ["design"]
        assert set(plan.execution_order[2]) == {"impl_a", "impl_b"}
        assert set(plan.execution_order[3]) == {"test_a", "test_b"}
        assert plan.execution_order[4] == ["merge"]
        assert plan.execution_order[5] == ["release"]

        # Role boundaries: planner→strategist, strategist→executor (×2), executor→cove (×2), cove→consolidator, consolidator→herald
        assert len(plan.role_boundaries) >= 6
