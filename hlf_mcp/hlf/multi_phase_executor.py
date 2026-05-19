"""
Multi-Phase Execution with Consolidation for HLF Swarms.

Extends the swarm orchestrator with a three-phase execution model:
  Phase 1: PLAN — agents produce individual plans
  Phase 2: CONSOLIDATE — merge redundant plans, detect conflicts
  Phase 3: EXECUTE — execute consolidated plan

Consolidation logic:
  - Detect duplicate work items (same goal, same agent scope)
  - Merge compatible plans (non-overlapping scope, shared resources)
  - Flag conflicts (conflicting constraints, overlapping mutable scope)
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf import HLFCompiler, language_to_hlf
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.formal_verifier import FormalVerifier, GateDecision
from hlf_mcp.hlf.swarm_observer import SwarmObserver
from hlf_mcp.hlf.witness_governance import WitnessGovernance, WitnessObservation

logger = logging.getLogger(__name__)


@dataclass
class AgentPlan:
    """An individual agent's plan produced during the PLAN phase."""

    agent_id: str
    role: str
    goal: str
    hlf_source: str
    scope: set[str] = field(default_factory=set)  # e.g., files, resources
    constraints: list[str] = field(default_factory=list)
    capabilities: set[str] = field(default_factory=set)
    dependencies: list[str] = field(default_factory=list)  # other agent_ids
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conflict:
    """A conflict detected between two plans."""

    kind: str  # "duplicate", "scope_overlap", "constraint_conflict", "dependency_cycle"
    plan_a: str  # agent_id
    plan_b: str  # agent_id
    description: str
    severity: str = "warning"  # warning | error | info
    resolution: str = ""  # suggested resolution


@dataclass
class ConsolidatedPlan:
    """Result of the consolidation phase."""

    merged_plans: list[AgentPlan] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)  # lists of agent_ids that are duplicates
    execution_order: list[str] = field(default_factory=list)  # ordered agent_ids
    hlf_source: str = ""  # consolidated HLF source
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseResult:
    """Result of a single phase in the multi-phase execution."""

    phase_id: str
    status: str  # pending | running | complete | error
    agent_plans: list[AgentPlan] = field(default_factory=list)
    consolidated: ConsolidatedPlan | None = None
    hlf_output: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    started_ns: int = 0
    finished_ns: int = 0


@dataclass
class MultiPhaseResult:
    """Full result of a multi-phase swarm execution."""

    swarm_id: str
    task_id: str
    final_status: str
    phases: list[PhaseResult]
    final_hlf: str
    final_nl: str
    total_tokens: int
    total_time_ms: float
    compile_success: bool
    consolidation_metrics: dict[str, Any] = field(default_factory=dict)


class ConsolidationEngine:
    """Engine for merging plans and detecting conflicts."""

    @staticmethod
    def detect_duplicates(plans: list[AgentPlan]) -> list[list[str]]:
        """Group agents whose plans are functionally identical."""
        groups: list[list[str]] = []
        assigned: set[str] = set()

        for i, plan_a in enumerate(plans):
            if plan_a.agent_id in assigned:
                continue
            group = [plan_a.agent_id]
            for j, plan_b in enumerate(plans):
                if i >= j or plan_b.agent_id in assigned:
                    continue
                # Same goal and same scope = duplicate
                if (plan_a.goal == plan_b.goal
                        and plan_a.scope == plan_b.scope
                        and plan_a.role == plan_b.role):
                    group.append(plan_b.agent_id)
                    assigned.add(plan_b.agent_id)
            if len(group) > 1:
                assigned.add(plan_a.agent_id)
                groups.append(group)

        return groups

    @staticmethod
    def detect_conflicts(plans: list[AgentPlan]) -> list[Conflict]:
        """Detect conflicts between agent plans."""
        conflicts: list[Conflict] = []

        for i, plan_a in enumerate(plans):
            for j, plan_b in enumerate(plans):
                if i >= j:
                    continue

                # Scope overlap conflict: two agents writing to the same scope
                write_overlap = plan_a.scope & plan_b.scope
                if write_overlap:
                    conflicts.append(Conflict(
                        kind="scope_overlap",
                        plan_a=plan_a.agent_id,
                        plan_b=plan_b.agent_id,
                        description=f"Both agents claim scope: {write_overlap}",
                        severity="warning",
                        resolution="Assign exclusive scope or establish write ordering.",
                    ))

                # Constraint conflicts
                for ca in plan_a.constraints:
                    for cb in plan_b.constraints:
                        if _constraints_conflict(ca, cb):
                            conflicts.append(Conflict(
                                kind="constraint_conflict",
                                plan_a=plan_a.agent_id,
                                plan_b=plan_b.agent_id,
                                description=f"Constraint conflict: '{ca}' vs '{cb}'",
                                severity="error",
                                resolution="Resolve conflicting constraints before execution.",
                            ))

                # Dependency cycle detection
                if (plan_b.agent_id in plan_a.dependencies
                        and plan_a.agent_id in plan_b.dependencies):
                    conflicts.append(Conflict(
                        kind="dependency_cycle",
                        plan_a=plan_a.agent_id,
                        plan_b=plan_b.agent_id,
                        description="Circular dependency detected",
                        severity="error",
                        resolution="Break the cycle by removing one dependency.",
                    ))

        return conflicts

    @staticmethod
    def merge_compatible(plans: list[AgentPlan]) -> list[AgentPlan]:
        """Merge compatible plans (non-overlapping scope, shared goal)."""
        merged: list[AgentPlan] = []
        consumed: set[str] = set()

        for i, plan_a in enumerate(plans):
            if plan_a.agent_id in consumed:
                continue

            merged_plan = AgentPlan(
                agent_id=plan_a.agent_id,
                role=plan_a.role,
                goal=plan_a.goal,
                hlf_source=plan_a.hlf_source,
                scope=set(plan_a.scope),
                constraints=list(plan_a.constraints),
                capabilities=set(plan_a.capabilities),
                dependencies=list(plan_a.dependencies),
                metrics=dict(plan_a.metrics),
            )

            for j, plan_b in enumerate(plans):
                if i >= j or plan_b.agent_id in consumed:
                    continue
                # Merge if same goal, no scope overlap, roles are compatible
                if (plan_a.goal == plan_b.goal
                        and not (plan_a.scope & plan_b.scope)
                        and _roles_compatible(plan_a.role, plan_b.role)):
                    merged_plan.scope |= plan_b.scope
                    merged_plan.constraints.extend(plan_b.constraints)
                    merged_plan.capabilities |= plan_b.capabilities
                    merged_plan.hlf_source += "\n" + plan_b.hlf_source
                    merged_plan.metrics["merged_from"] = (
                        merged_plan.metrics.get("merged_from", []) + [plan_b.agent_id]
                    )
                    consumed.add(plan_b.agent_id)

            merged.append(merged_plan)
            consumed.add(plan_a.agent_id)

        return merged

    @staticmethod
    def build_execution_order(plans: list[AgentPlan]) -> list[str]:
        """Topological sort of agents by dependencies."""
        in_degree: dict[str, int] = {p.agent_id: 0 for p in plans}
        adj: dict[str, list[str]] = {p.agent_id: [] for p in plans}
        agent_ids = {p.agent_id for p in plans}

        for plan in plans:
            for dep in plan.dependencies:
                if dep in agent_ids:
                    adj[dep].append(plan.agent_id)
                    in_degree[plan.agent_id] += 1

        queue = [aid for aid, deg in in_degree.items() if deg == 0]
        order: list[str] = []

        while queue:
            n = queue.pop(0)
            order.append(n)
            for neighbor in adj[n]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any remaining (cycle members)
        for p in plans:
            if p.agent_id not in order:
                order.append(p.agent_id)

        return order


def _constraints_conflict(a: str, b: str) -> bool:
    """Check if two constraint strings conflict."""
    a_lower, b_lower = a.lower(), b.lower()
    # Simple heuristic: detect contradictory keywords
    contradictory_pairs = [
        ("read", "write"),
        ("allow", "deny"),
        ("include", "exclude"),
        ("open", "closed"),
        ("high", "low"),
    ]
    for w1, w2 in contradictory_pairs:
        if w1 in a_lower and w2 in b_lower:
            return True
        if w2 in a_lower and w1 in b_lower:
            return True
    return False


def _roles_compatible(a: str, b: str) -> bool:
    """Check if two roles are compatible for merging."""
    compatible_pairs = {
        ("planner", "researcher"),
        ("executor", "builder"),
        ("reviewer", "verifier"),
        ("planner", "planner"),
        ("executor", "executor"),
    }
    return (a, b) in compatible_pairs or (b, a) in compatible_pairs


class MultiPhaseExecutor:
    """Three-phase execution engine with consolidation.

    Phase 1: PLAN — agents produce individual plans via HLF translation.
    Phase 2: CONSOLIDATE — merge redundant plans, detect conflicts, build order.
    Phase 3: EXECUTE — execute the consolidated plan with verification.

    Builds on SwarmOrchestrator infrastructure: same compiler, verifier,
    governance, and observer patterns.
    """

    def __init__(
        self,
        observer: SwarmObserver | None = None,
        governance: WitnessGovernance | None = None,
        verifier: FormalVerifier | None = None,
        default_capabilities: set[str] | None = None,
        session_tier: str = "hearth",
    ) -> None:
        self.compiler = HLFCompiler(strict_align=True)
        self.governance = governance or WitnessGovernance()
        self.verifier = verifier or FormalVerifier()
        self.observer = observer or SwarmObserver()
        self.consolidation_engine = ConsolidationEngine()
        self.default_capabilities = default_capabilities or {
            "network", "model", "filesystem", "memory", "local"
        }
        self.session_tier = session_tier

    def plan_phase(
        self,
        description: str,
        agents: list[str] | None = None,
        *,
        swarm_id: str = "",
    ) -> list[AgentPlan]:
        """Phase 1: Each agent produces an individual HLF plan.

        Args:
            description: Task description.
            agents: List of agent IDs to plan. Defaults to planner/executor/verifier.
            swarm_id: Optional swarm identifier for event emission.

        Returns:
            List of AgentPlan objects, one per agent.
        """
        if agents is None:
            agents = ["planner", "executor", "verifier"]

        plans: list[AgentPlan] = []
        for agent_id in agents:
            role = agent_id
            prompt = f"Plan this task as {agent_id}:\n\n{description}"

            self.observer.emit(
                swarm_id=swarm_id,
                phase_id="plan",
                agent_id=agent_id,
                role=role,
                event_type="started",
                message=f"{agent_id} producing plan",
            )

            try:
                hlf_source = language_to_hlf(prompt, language="en", version="3")
                compile_ok = True
            except Exception as exc:
                hlf_source = f"; {agent_id} plan error: {exc}\nΩ"
                compile_ok = False

            # Attempt compile for validation
            try:
                ast_result = self.compiler.compile(hlf_source)
                compile_ast = ast_result.get("ast", {}) if ast_result else {}
            except CompileError:
                compile_ast = {}
                compile_ok = False

            # Extract scope from compiled AST
            scope: set[str] = set()
            constraints: list[str] = []
            capabilities: set[str] = set()
            if compile_ast:
                scope = _extract_scope(compile_ast)
                constraints = _extract_constraints(compile_ast)
                capabilities = _extract_capabilities(compile_ast)

            plan = AgentPlan(
                agent_id=agent_id,
                role=role,
                goal=description,
                hlf_source=hlf_source,
                scope=scope,
                constraints=constraints,
                capabilities=capabilities or self.default_capabilities,
                dependencies=[],
                metrics={
                    "hlf_tokens": len(hlf_source.split()),
                    "compile_success": compile_ok,
                },
            )
            plans.append(plan)

            self.observer.emit(
                swarm_id=swarm_id,
                phase_id="plan",
                agent_id=agent_id,
                role=role,
                event_type="complete",
                message=f"{agent_id} plan: {plan.metrics['hlf_tokens']} tokens, "
                        f"compile={'OK' if compile_ok else 'FAIL'}",
            )

        return plans

    def consolidate_phase(
        self,
        plans: list[AgentPlan],
        *,
        swarm_id: str = "",
    ) -> ConsolidatedPlan:
        """Phase 2: Merge redundant plans and detect conflicts.

        Args:
            plans: Agent plans from the PLAN phase.
            swarm_id: Optional swarm identifier.

        Returns:
            ConsolidatedPlan with merged plans, conflicts, and execution order.
        """
        self.observer.emit(
            swarm_id=swarm_id,
            phase_id="consolidate",
            agent_id="consolidator",
            role="consolidator",
            event_type="started",
            message=f"Consolidating {len(plans)} agent plans",
        )

        # Detect duplicates
        duplicates = self.consolidation_engine.detect_duplicates(plans)

        # Merge compatible plans
        merged = self.consolidation_engine.merge_compatible(plans)

        # Detect conflicts
        conflicts = self.consolidation_engine.detect_conflicts(merged)

        # Build execution order
        execution_order = self.consolidation_engine.build_execution_order(merged)

        # Assemble consolidated HLF source
        hlf_lines = ["[HLF-v3]", f"# Consolidated plan — {len(merged)} agents"]
        for plan in merged:
            hlf_lines.append(f"# Agent: {plan.agent_id} ({plan.role}) — scope: {plan.scope}")
            # Extract body from plan HLF (skip header and terminator)
            for line in plan.hlf_source.split("\n"):
                stripped = line.strip()
                if stripped and stripped != "Ω" and not stripped.startswith("[HLF-v3]"):
                    hlf_lines.append(f"; [{plan.agent_id}] {stripped}")
        hlf_lines.append("Ω")
        consolidated_hlf = "\n".join(hlf_lines)

        error_count = sum(1 for c in conflicts if c.severity == "error")
        warning_count = sum(1 for c in conflicts if c.severity == "warning")

        result = ConsolidatedPlan(
            merged_plans=merged,
            conflicts=conflicts,
            duplicate_groups=duplicates,
            execution_order=execution_order,
            hlf_source=consolidated_hlf,
            metrics={
                "plan_count": len(plans),
                "merged_count": len(merged),
                "duplicate_groups": len(duplicates),
                "conflict_count": len(conflicts),
                "error_count": error_count,
                "warning_count": warning_count,
                "execution_order": execution_order,
            },
        )

        self.observer.emit(
            swarm_id=swarm_id,
            phase_id="consolidate",
            agent_id="consolidator",
            role="consolidator",
            event_type="complete",
            message=f"Consolidated: {len(merged)} plans, {len(conflicts)} conflicts "
                    f"({error_count} errors, {warning_count} warnings), "
                    f"{len(duplicates)} duplicate groups",
            payload=result.metrics,
        )

        return result

    def execute_phase(
        self,
        consolidated: ConsolidatedPlan,
        *,
        swarm_id: str = "",
    ) -> PhaseResult:
        """Phase 3: Execute the consolidated plan with verification.

        Args:
            consolidated: The consolidated plan from Phase 2.
            swarm_id: Optional swarm identifier.

        Returns:
            PhaseResult with execution details.
        """
        started = time.perf_counter_ns()

        self.observer.emit(
            swarm_id=swarm_id,
            phase_id="execute",
            agent_id="executor",
            role="executor",
            event_type="started",
            message=f"Executing consolidated plan with {len(consolidated.merged_plans)} agents",
        )

        compile_ok = False
        ver_results: list[dict[str, Any]] = []
        gate_decision = GateDecision.BLOCK
        execution_results: list[dict[str, Any]] = []

        try:
            compile_result = self.compiler.compile(consolidated.hlf_source)
            compile_ok = compile_result is not None and compile_result.get("status") in (None, "ok")
            compile_ast = compile_result.get("ast", {}) if compile_result else {}

            if compile_ast:
                report = self.verifier.verify_ast(compile_ast)
                ver_results = report.to_dict().get("results", [])
                gate_decision = VerificationGate.gate(report, self.session_tier)
        except CompileError as exc:
            compile_ok = False
            ver_results = [{"error": str(exc)}]

        # Execute plans in order
        for agent_id in consolidated.execution_order:
            plan = next((p for p in consolidated.merged_plans if p.agent_id == agent_id), None)
            if plan is None:
                continue
            try:
                plan_compile = self.compiler.compile(plan.hlf_source)
                execution_results.append({
                    "agent_id": agent_id,
                    "status": "ok" if plan_compile else "compile_error",
                    "gas_estimate": plan_compile.get("gas_estimate", 0) if plan_compile else 0,
                })
            except Exception as exc:
                execution_results.append({
                    "agent_id": agent_id,
                    "status": "error",
                    "error": str(exc),
                })

        finished = time.perf_counter_ns()

        # Record governance
        for plan in consolidated.merged_plans:
            observation = WitnessObservation(
                witness_id="multi_phase_executor",
                subject_agent_id=plan.agent_id,
                category="multi_phase_execution",
                severity="info" if compile_ok else "warning",
                confidence=0.95,
                goal_id="execute",
                details={"compile_success": compile_ok},
            )
            self.governance.record_observation(observation)

        self.observer.emit(
            swarm_id=swarm_id,
            phase_id="execute",
            agent_id="executor",
            role="executor",
            event_type="complete",
            message=f"Execute: compile={'OK' if compile_ok else 'FAIL'}, "
                    f"{len(ver_results)} verification checks, "
                    f"{len(execution_results)} agents executed",
        )

        return PhaseResult(
            phase_id="execute",
            status="complete",
            hlf_output=consolidated.hlf_source,
            metrics={
                "hlf_tokens": len(consolidated.hlf_source.split()),
                "compile_success": compile_ok,
                "lint_errors": len([r for r in ver_results if r.get("severity") == "error"]),
                "verification_checks": len(ver_results),
                "gate_decision": gate_decision,
                "execution_results": execution_results,
                "time_ms": (finished - started) / 1_000_000,
            },
            started_ns=started,
            finished_ns=finished,
        )

    def run_multi_phase(
        self,
        description: str,
        agents: list[str] | None = None,
        *,
        skip_consolidation: bool = False,
    ) -> MultiPhaseResult:
        """Run the full three-phase execution: PLAN → CONSOLIDATE → EXECUTE.

        Args:
            description: Task description.
            agents: Agent IDs to use. Defaults to planner/executor/verifier.
            skip_consolidation: If True, skip the consolidation phase.

        Returns:
            MultiPhaseResult with all phase details.
        """
        if agents is None:
            agents = ["planner", "executor", "verifier"]

        swarm_id = hashlib.sha256(
            f"multi-phase:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        overall_start = time.perf_counter_ns()
        phases: list[PhaseResult] = []
        total_tokens = 0

        # ── Phase 1: PLAN ─────────────────────────────────────────────────
        plan_start = time.perf_counter_ns()
        plans = self.plan_phase(description, agents, swarm_id=swarm_id)
        plan_tokens = sum(p.metrics.get("hlf_tokens", 0) for p in plans)
        total_tokens += plan_tokens

        phases.append(PhaseResult(
            phase_id="plan",
            status="complete",
            agent_plans=plans,
            metrics={
                "agent_count": len(plans),
                "total_hlf_tokens": plan_tokens,
                "all_compile_ok": all(p.metrics.get("compile_success", False) for p in plans),
                "time_ms": (time.perf_counter_ns() - plan_start) / 1_000_000,
            },
            started_ns=plan_start,
            finished_ns=time.perf_counter_ns(),
        ))

        # ── Phase 2: CONSOLIDATE ──────────────────────────────────────────
        if skip_consolidation:
            consolidated = ConsolidatedPlan(
                merged_plans=plans,
                execution_order=[p.agent_id for p in plans],
                hlf_source="\n".join(p.hlf_source for p in plans),
                metrics={"skipped": True},
            )
            phases.append(PhaseResult(
                phase_id="consolidate",
                status="skipped",
                consolidated=consolidated,
                metrics={"skipped": True},
            ))
        else:
            con_start = time.perf_counter_ns()
            consolidated = self.consolidate_phase(plans, swarm_id=swarm_id)
            phases.append(PhaseResult(
                phase_id="consolidate",
                status="complete",
                consolidated=consolidated,
                metrics={
                    **consolidated.metrics,
                    "time_ms": (time.perf_counter_ns() - con_start) / 1_000_000,
                },
                started_ns=con_start,
                finished_ns=time.perf_counter_ns(),
            ))

        # ── Phase 3: EXECUTE ──────────────────────────────────────────────
        exec_phase = self.execute_phase(consolidated, swarm_id=swarm_id)
        total_tokens += exec_phase.metrics.get("hlf_tokens", 0)
        phases.append(exec_phase)

        # ── Build final result ────────────────────────────────────────────
        total_time_ns = time.perf_counter_ns() - overall_start
        compile_success = exec_phase.metrics.get("compile_success", False)

        return MultiPhaseResult(
            swarm_id=swarm_id,
            task_id=hashlib.sha256(description.encode()).hexdigest()[:16],
            final_status="ok" if compile_success else "compile_error",
            phases=phases,
            final_hlf=consolidated.hlf_source,
            final_nl=f"Multi-phase execution: {len(plans)} agents planned, "
                     f"{len(consolidated.merged_plans)} consolidated, "
                     f"compile={'OK' if compile_success else 'FAIL'}",
            total_tokens=total_tokens,
            total_time_ms=total_time_ns / 1_000_000,
            compile_success=compile_success,
            consolidation_metrics=consolidated.metrics,
        )


def _extract_scope(ast: dict[str, Any]) -> set[str]:
    """Extract declared scope from an HLF AST."""
    scope: set[str] = set()
    statements = ast.get("statements", []) if isinstance(ast, dict) else []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        args = stmt.get("arguments", {})
        if isinstance(args, dict):
            for key in ("scope", "file", "path", "resource"):
                val = args.get(key)
                if val and isinstance(val, str):
                    scope.add(val)
    return scope


def _extract_constraints(ast: dict[str, Any]) -> list[str]:
    """Extract constraint declarations from an HLF AST."""
    constraints: list[str] = []
    statements = ast.get("statements", []) if isinstance(ast, dict) else []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        tag = stmt.get("tag", "")
        if tag in ("CONSTRAINT", "ASSERT", "REQUIRE"):
            args = stmt.get("arguments", {})
            if isinstance(args, dict):
                for val in args.values():
                    if val and isinstance(val, str):
                        constraints.append(str(val))
    return constraints


def _extract_capabilities(ast: dict[str, Any]) -> set[str]:
    """Extract required capabilities from an HLF AST."""
    capabilities: set[str] = set()
    statements = ast.get("statements", []) if isinstance(ast, dict) else []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        args = stmt.get("arguments", {})
        if isinstance(args, dict):
            caps = args.get("capabilities") or args.get("effects") or args.get("permissions")
            if isinstance(caps, list):
                capabilities.update(str(c) for c in caps if c)
            elif isinstance(caps, str) and caps:
                capabilities.add(caps)
    return capabilities
