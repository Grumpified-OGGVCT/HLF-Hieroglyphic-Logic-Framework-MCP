"""
Plan Execution — Faithful port of hlf_source/agents/core/plan_executor.py.

Translates task specs into dependency-ordered DAG pipelines and executes them
through agent dispatch.  Preserves the original plan_to_dag → execute_plan flow
with fail-fast semantics and per-step trace collection.

Usage::

    from hlf_mcp.instinct.execution import PlanExecutor, PlanTaskType

    executor = PlanExecutor()
    tasks = [
        {"type": "create_file", "path": "src/new.py", "content": "..."},
        {"type": "run_tests", "path": "tests/"},
    ]
    result = executor.execute_plan(tasks)
    print(result.success, result.files_modified)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Plan Task Types
# --------------------------------------------------------------------------- #


class PlanTaskType(StrEnum):
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    REFACTOR = "refactor"
    DELETE_FILE = "delete_file"
    RUN_TESTS = "run_tests"
    RUN_LINT = "run_lint"
    CHECK_SYNTAX = "check_syntax"
    VALIDATE_IMPORTS = "validate_imports"

    @property
    def agent_type(self) -> str:
        code_types = {
            PlanTaskType.CREATE_FILE,
            PlanTaskType.MODIFY_FILE,
            PlanTaskType.REFACTOR,
            PlanTaskType.DELETE_FILE,
        }
        return "code-agent" if self in code_types else "build-agent"


# Task types that are execution-only (need a real dispatch target)
_EXECUTABLE_TASK_TYPES: set[str] = {
    PlanTaskType.CREATE_FILE, PlanTaskType.MODIFY_FILE, PlanTaskType.REFACTOR,
    PlanTaskType.DELETE_FILE, PlanTaskType.RUN_TESTS, PlanTaskType.RUN_LINT,
    PlanTaskType.CHECK_SYNTAX, PlanTaskType.VALIDATE_IMPORTS,
}


# --------------------------------------------------------------------------- #
# Spindle DAG (minimal, faithful to source)
# --------------------------------------------------------------------------- #


class NodeStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SpindleNode:
    node_id: str
    agent_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)


class SpindleDAG:
    """Minimal directed acyclic graph for plan node ordering."""

    def __init__(self) -> None:
        self.nodes: dict[str, SpindleNode] = {}
        self._order: list[str] | None = None

    def add_node(self, node: SpindleNode) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"Duplicate node_id '{node.node_id}'")
        self.nodes[node.node_id] = node
        self._order = None

    def topological_order(self) -> list[str]:
        if self._order is not None:
            return list(self._order)

        indegree: dict[str, int] = {nid: 0 for nid in self.nodes}
        dependents: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for nid, node in self.nodes.items():
            for dep in node.depends_on:
                if dep not in self.nodes:
                    raise ValueError(f"Node '{nid}' depends on unknown node '{dep}'")
                indegree[nid] += 1
                dependents[dep].append(nid)

        queue = [nid for nid, deg in indegree.items() if deg == 0]
        ordered: list[str] = []

        while queue:
            nid = queue.pop(0)
            ordered.append(nid)
            for dep_nid in dependents[nid]:
                indegree[dep_nid] -= 1
                if indegree[dep_nid] == 0:
                    queue.append(dep_nid)

        if len(ordered) != len(self.nodes):
            raise ValueError("DAG contains a dependency cycle")

        self._order = ordered
        return list(ordered)


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #


@dataclass
class PlanStep:
    node_id: str
    task_type: str
    agent_type: str
    success: bool
    result: Any = None
    duration: float = 0.0
    error: str | None = None
    delegated_to: str = ""
    escalation_role: str = ""
    dissent_state: str = "none"


@dataclass
class PlanExecutionResult:
    success: bool
    steps: list[PlanStep] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    test_results: dict[str, int] = field(default_factory=dict)
    total_duration: float = 0.0
    error: str | None = None
    execution_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "steps": [
                {
                    "node_id": s.node_id,
                    "task_type": s.task_type,
                    "agent_type": s.agent_type,
                    "success": s.success,
                    "duration": round(s.duration, 3),
                    "error": s.error,
                    "delegated_to": s.delegated_to,
                    "escalation_role": s.escalation_role,
                    "dissent_state": s.dissent_state,
                }
                for s in self.steps
            ],
            "files_modified": list(self.files_modified),
            "test_results": dict(self.test_results),
            "total_duration": round(self.total_duration, 3),
            "error": self.error,
        }


# --------------------------------------------------------------------------- #
# Plan Executor
# --------------------------------------------------------------------------- #


class PlanExecutor:
    """Translates task specs into DAGs and executes them.

    Flow::

        tasks → plan_to_dag()  → SpindleDAG
              → execute_plan() → PlanExecutionResult
    """

    def __init__(self) -> None:
        self._task_registry: dict[str, dict[str, Any]] = {}
        self._dispatch_fn: Any = None

    def set_dispatch_fn(self, fn: Any) -> None:
        """Inject a dispatch function for executing individual tasks.

        The function receives (task_dict, agent_type) and returns a dict
        with 'success', 'files_modified', 'outputs', 'error' keys.
        """
        self._dispatch_fn = fn

    def plan_to_dag(self, tasks: list[dict[str, Any]]) -> SpindleDAG:
        """Convert a list of task specs into a SpindleDAG.

        Each task dict must have a 'type' field.  Code tasks are linked
        sequentially; build tasks depend on the last code task.
        """
        self._task_registry.clear()

        if not tasks:
            raise ValueError("Cannot create DAG from empty task list")

        dag = SpindleDAG()
        code_node_ids: list[str] = []
        build_node_ids: list[str] = []

        task_entries: list[tuple[str, str, dict[str, Any]]] = []

        for i, task in enumerate(tasks):
            task_type = task.get("type", "unknown")
            node_id = f"step-{i:03d}-{task_type}"

            try:
                pt = PlanTaskType(task_type)
                agent_id = pt.agent_type
            except ValueError:
                # Unknown type — classify as code-agent by default
                agent_id = "code-agent"

            task_entries.append((node_id, agent_id, task))
            if agent_id == "code-agent":
                code_node_ids.append(node_id)
            else:
                build_node_ids.append(node_id)

        # Precompute code dependencies
        code_prev_map: dict[str, str] = {}
        prev_code_id: str | None = None
        for code_id in code_node_ids:
            if prev_code_id is not None:
                code_prev_map[code_id] = prev_code_id
            prev_code_id = code_id

        for node_id, agent_id, task in task_entries:
            deps: list[str] = []
            if agent_id == "code-agent":
                prev_dep = code_prev_map.get(node_id)
                if prev_dep is not None:
                    deps.append(prev_dep)
            elif agent_id == "build-agent" and code_node_ids:
                deps.append(code_node_ids[-1])

            node = SpindleNode(
                node_id=node_id,
                agent_id=agent_id,
                depends_on=deps,
            )
            dag.add_node(node)
            self._task_registry[node_id] = task

        return dag

    def execute_plan(self, tasks: list[dict[str, Any]]) -> PlanExecutionResult:
        """Execute a complete plan: DAG → topological order → dispatch.

        Stops on first failure (fail-fast).
        """
        start = time.time()

        if not tasks:
            return PlanExecutionResult(
                success=False,
                error="No tasks to execute",
                total_duration=time.time() - start,
            )

        try:
            dag = self.plan_to_dag(tasks)
        except ValueError as e:
            return PlanExecutionResult(
                success=False,
                error=str(e),
                total_duration=time.time() - start,
            )

        steps: list[PlanStep] = []
        all_files_modified: list[str] = []
        total_passed = 0
        total_failed = 0
        total_errors = 0
        overall_success = True
        execution_trace: list[dict[str, Any]] = []

        execution_order = dag.topological_order()

        for node_id in execution_order:
            node = dag.nodes[node_id]
            task = self._task_registry.get(node_id, {})
            task_type = task.get("type", "unknown")
            agent_type = node.agent_id or "unknown"

            step_start = time.time()
            node.status = NodeStatus.RUNNING

            try:
                if self._dispatch_fn is not None:
                    result = self._dispatch_fn(task, agent_type)
                    step_success = bool(result.get("success", False))
                    step = PlanStep(
                        node_id=node_id,
                        task_type=task_type,
                        agent_type=agent_type,
                        success=step_success,
                        result=result,
                        duration=time.time() - step_start,
                        error=result.get("error") if not step_success else None,
                    )
                    if step_success:
                        all_files_modified.extend(result.get("files_modified", []))
                        if agent_type == "build-agent":
                            total_passed += 1
                    else:
                        overall_success = False
                elif agent_type == "code-agent":
                    step = PlanStep(
                        node_id=node_id,
                        task_type=task_type,
                        agent_type=agent_type,
                        success=True,
                        duration=time.time() - step_start,
                    )
                    all_files_modified.append(task.get("path", task.get("file", "unknown")))
                elif agent_type == "build-agent":
                    step = PlanStep(
                        node_id=node_id,
                        task_type=task_type,
                        agent_type=agent_type,
                        success=True,
                        duration=time.time() - step_start,
                    )
                    total_passed += 1
                else:
                    step = PlanStep(
                        node_id=node_id,
                        task_type=task_type,
                        agent_type=agent_type,
                        success=False,
                        duration=time.time() - step_start,
                        error=f"Unknown agent type '{agent_type}'",
                    )
                    overall_success = False

                node.status = NodeStatus.COMPLETED if step.success else NodeStatus.FAILED

            except Exception as e:
                step = PlanStep(
                    node_id=node_id,
                    task_type=task_type,
                    agent_type=agent_type,
                    success=False,
                    duration=time.time() - step_start,
                    error=str(e),
                )
                node.status = NodeStatus.FAILED
                overall_success = False
                logger.exception("Plan step %s failed: %s", node_id, e)

            steps.append(step)
            execution_trace.append({
                "node_id": node_id,
                "task_type": task_type,
                "success": step.success,
                "duration_ms": step.duration * 1000,
                "error": step.error,
                "delegated_to": step.delegated_to,
                "escalation_role": step.escalation_role,
                "dissent_state": step.dissent_state,
            })

            # Fail-fast
            if not step.success:
                break

        result_error = None
        if not overall_success:
            for s in reversed(steps):
                if not s.success and s.error:
                    result_error = s.error
                    break

        return PlanExecutionResult(
            success=overall_success,
            steps=steps,
            files_modified=list(dict.fromkeys(all_files_modified)),
            test_results={
                "passed": total_passed,
                "failed": total_failed,
                "errors": total_errors,
            },
            total_duration=time.time() - start,
            error=result_error,
            execution_trace=execution_trace,
        )
