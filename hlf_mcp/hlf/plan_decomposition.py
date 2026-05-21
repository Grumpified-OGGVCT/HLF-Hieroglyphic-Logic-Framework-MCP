"""
Plan Decomposition — dependency-DAG-based plan decomposition with role-boundary
detection and parallel-step grouping for multi-agent orchestration.

Provides:
  - PlanStep: a single step in a decomposed plan
  - DecomposedPlan: the full decomposition with execution groups and role boundaries
  - decompose_plan: convert a list of step dicts into a DecomposedPlan
  - validate_step_ordering: detect dependency and role-boundary violations

Integration points:
  - hlf_mcp.instinct.orchestration: PlanStepContract, topological sort
  - hlf_mcp.hlf.orchestration_contracts: DelegationContract, HandoffContract
  - hlf_mcp.hlf.swarm_handoff: SwarmHandoffContract for swarm-level handoffs
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# PlanStep — a single step in a decomposed plan
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlanStep:
    """A single step in a decomposed multi-agent plan.

    Attributes:
        step_id: Unique identifier for this step.
        agent_role: The role responsible for executing this step.
        dependencies: step_ids that must complete before this step.
        is_parallel: Whether this step can run in parallel with siblings.
    """

    step_id: str
    agent_role: str = ""
    dependencies: list[str] = field(default_factory=list)
    is_parallel: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "agent_role": self.agent_role,
            "dependencies": list(self.dependencies),
            "is_parallel": self.is_parallel,
        }


# ---------------------------------------------------------------------------
# DecomposedPlan — full decomposition result
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DecomposedPlan:
    """The result of decomposing a plan into ordered execution groups.

    Attributes:
        steps: All PlanStep objects in the plan.
        execution_order: Groups of step_ids that can execute in parallel.
            Each inner list represents one parallel wave; waves execute
            sequentially.
        role_boundaries: Handoff points where agent_role changes between
            a step and its dependency. Each entry is a dict with:
            - "from_role": the role of the dependency
            - "to_role": the role of the dependent step
            - "at_step": the step_id where the role transition occurs
    """

    steps: list[PlanStep] = field(default_factory=list)
    execution_order: list[list[str]] = field(default_factory=list)
    role_boundaries: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "execution_order": [list(group) for group in self.execution_order],
            "role_boundaries": [dict(boundary) for boundary in self.role_boundaries],
        }


# ---------------------------------------------------------------------------
# decompose_plan — convert raw step dicts into a DecomposedPlan
# ---------------------------------------------------------------------------


def decompose_plan(steps: list[dict[str, Any]]) -> DecomposedPlan:
    """Decompose a list of step dicts into an ordered, grouped DecomposedPlan.

    Steps are topologically sorted by their dependency DAG, then grouped
    into parallel execution waves. Role boundaries are identified wherever
    a step has a different agent_role than one of its dependencies.

    Args:
        steps: List of dicts, each with keys:
            - step_id (str): unique step identifier
            - agent_role (str, optional): role responsible for the step
            - dependencies (list[str], optional): step_ids this step depends on
            - is_parallel (bool, optional): whether this step can run in parallel

    Returns:
        A DecomposedPlan with sorted execution_order groups and role_boundaries.
    """
    if not steps:
        return DecomposedPlan()

    # Parse into PlanStep objects
    parsed_steps: list[PlanStep] = []
    for raw in steps:
        parsed_steps.append(
            PlanStep(
                step_id=str(raw.get("step_id", "")),
                agent_role=str(raw.get("agent_role", "")),
                dependencies=[
                    str(d) for d in (raw.get("dependencies") or [])
                ],
                is_parallel=bool(raw.get("is_parallel", False)),
            )
        )

    step_map: dict[str, PlanStep] = {s.step_id: s for s in parsed_steps}

    # Validate dependencies reference known steps
    known_ids = set(step_map.keys())
    for step in parsed_steps:
        for dep in step.dependencies:
            if dep not in known_ids:
                raise ValueError(
                    f"Step '{step.step_id}' depends on unknown step '{dep}'."
                )

    # Kahn's algorithm for topological sort with parallel grouping
    indegree: dict[str, int] = {s.step_id: len(s.dependencies) for s in parsed_steps}
    dependents: dict[str, list[str]] = defaultdict(list)
    for step in parsed_steps:
        for dep in step.dependencies:
            dependents[dep].append(step.step_id)

    # Initial wave: all steps with indegree 0
    wave: list[str] = sorted(
        [s.step_id for s in parsed_steps if indegree[s.step_id] == 0]
    )
    execution_order: list[list[str]] = []

    while wave:
        execution_order.append(list(wave))
        next_wave: list[str] = []
        for node_id in wave:
            for dependent in dependents[node_id]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    next_wave.append(dependent)
        wave = sorted(next_wave)

    # Check for cycles
    total_ordered = sum(len(group) for group in execution_order)
    if total_ordered != len(parsed_steps):
        raise ValueError("Plan contains a dependency cycle.")

    # Identify role boundaries: where a step's agent_role differs from a
    # dependency's agent_role, that is a handoff/role-boundary point.
    role_boundaries: list[dict[str, str]] = []
    for step in parsed_steps:
        for dep_id in step.dependencies:
            dep_step = step_map.get(dep_id)
            if dep_step and dep_step.agent_role and step.agent_role:
                if dep_step.agent_role != step.agent_role:
                    role_boundaries.append(
                        {
                            "from_role": dep_step.agent_role,
                            "to_role": step.agent_role,
                            "at_step": step.step_id,
                        }
                    )

    return DecomposedPlan(
        steps=parsed_steps,
        execution_order=execution_order,
        role_boundaries=role_boundaries,
    )


# ---------------------------------------------------------------------------
# validate_step_ordering — detect ordering violations
# ---------------------------------------------------------------------------


def validate_step_ordering(plan: DecomposedPlan) -> list[str]:
    """Validate the execution ordering of a DecomposedPlan.

    Checks:
      1. No step depends on a step that appears in a later (or same) wave
         (dependency must be in an earlier wave).
      2. No duplicate step_ids in the execution order.
      3. Every step in the plan appears in the execution order.

    Args:
        plan: The DecomposedPlan to validate.

    Returns:
        A list of violation strings. Empty list means the plan is valid.
    """
    violations: list[str] = []

    if not plan.steps:
        return violations

    # Build a map of step_id → wave index
    step_wave: dict[str, int] = {}
    all_ordered: set[str] = set()
    for wave_idx, group in enumerate(plan.execution_order):
        for step_id in group:
            if step_id in step_wave:
                violations.append(
                    f"Duplicate step_id '{step_id}' in execution order "
                    f"(waves {step_wave[step_id]} and {wave_idx})."
                )
            step_wave[step_id] = wave_idx
            all_ordered.add(step_id)

    # Check all plan steps appear in execution order
    for step in plan.steps:
        if step.step_id not in all_ordered:
            violations.append(
                f"Step '{step.step_id}' is missing from execution_order."
            )

    # Check dependency ordering: each dependency must be in an earlier wave
    for step in plan.steps:
        if step.step_id not in step_wave:
            continue  # already reported as missing
        current_wave = step_wave[step.step_id]
        for dep_id in step.dependencies:
            if dep_id not in step_wave:
                violations.append(
                    f"Step '{step.step_id}' depends on '{dep_id}' which is "
                    f"missing from execution_order."
                )
                continue
            dep_wave = step_wave[dep_id]
            if dep_wave >= current_wave:
                violations.append(
                    f"Step '{step.step_id}' (wave {current_wave}) depends on "
                    f"'{dep_id}' (wave {dep_wave}) which is not in an earlier wave."
                )

    return violations
