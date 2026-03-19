from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PlanStepContract:
    node_id: str
    task_type: str
    title: str = ""
    depends_on: list[str] = field(default_factory=list)
    assigned_role: str = ""
    delegated_to: str = ""
    escalation_role: str = ""
    dissent_state: str = "none"
    verification_required: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "task_type": self.task_type,
            "title": self.title,
            "depends_on": list(self.depends_on),
            "assigned_role": self.assigned_role,
            "delegated_to": self.delegated_to,
            "escalation_role": self.escalation_role,
            "dissent_state": self.dissent_state,
            "verification_required": self.verification_required,
            "payload": dict(self.payload),
        }


@dataclass(slots=True)
class ExecutionTraceEntry:
    node_id: str
    task_type: str
    assigned_role: str = ""
    success: bool = False
    duration_ms: float = 0.0
    affected_files: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    delegated_to: str = ""
    escalation_role: str = ""
    dissent_state: str = "none"
    verification_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "task_type": self.task_type,
            "assigned_role": self.assigned_role,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "affected_files": list(self.affected_files),
            "outputs": list(self.outputs),
            "delegated_to": self.delegated_to,
            "escalation_role": self.escalation_role,
            "dissent_state": self.dissent_state,
            "verification_status": self.verification_status,
        }


def normalize_task_dag(raw_task_dag: list[dict[str, Any]]) -> list[dict[str, Any]]:
    steps = [_normalize_plan_step(step, index=index) for index, step in enumerate(raw_task_dag)]
    step_ids = [step.node_id for step in steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("Task DAG contains duplicate node_id values.")

    known_ids = set(step_ids)
    for step in steps:
        missing = [dep for dep in step.depends_on if dep not in known_ids]
        if missing:
            raise ValueError(
                f"Task DAG node '{step.node_id}' depends on unknown nodes: {', '.join(missing)}"
            )

    return [_step.to_dict() for _step in _topological_sort(steps)]


def normalize_execution_trace(
    raw_execution_trace: list[dict[str, Any]],
    *,
    task_dag: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    step_map = {str(step.get("node_id")): step for step in task_dag}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_execution_trace:
        node_id = str(item.get("node_id") or "").strip()
        if not node_id:
            raise ValueError("Execution trace entries require node_id.")
        if node_id not in step_map:
            raise ValueError(f"Execution trace references unknown node_id '{node_id}'.")
        if node_id in seen:
            raise ValueError(f"Execution trace contains duplicate node_id '{node_id}'.")
        seen.add(node_id)
        plan_step = step_map[node_id]
        entry = ExecutionTraceEntry(
            node_id=node_id,
            task_type=str(item.get("task_type") or plan_step.get("task_type") or "unknown"),
            assigned_role=str(item.get("assigned_role") or plan_step.get("assigned_role") or ""),
            success=bool(item.get("success", False)),
            duration_ms=float(item.get("duration_ms") or 0.0),
            affected_files=[str(value) for value in item.get("affected_files", [])],
            outputs=[str(value) for value in item.get("outputs", [])],
            delegated_to=str(item.get("delegated_to") or plan_step.get("delegated_to") or ""),
            escalation_role=str(
                item.get("escalation_role") or plan_step.get("escalation_role") or ""
            ),
            dissent_state=str(
                item.get("dissent_state") or plan_step.get("dissent_state") or "none"
            ),
            verification_status=str(
                item.get("verification_status")
                or ("passed" if item.get("success", False) else "pending")
            ),
        )
        normalized.append(entry.to_dict())
    return normalized


def summarize_execution_trace(
    execution_trace: list[dict[str, Any]], *, task_dag: list[dict[str, Any]]
) -> dict[str, Any]:
    total_nodes = len(task_dag)
    completed = sum(1 for entry in execution_trace if bool(entry.get("success", False)))
    failed = sum(1 for entry in execution_trace if not bool(entry.get("success", False)))
    escalated = sum(
        1 for entry in execution_trace if str(entry.get("escalation_role") or "").strip()
    )
    delegated = sum(1 for entry in execution_trace if str(entry.get("delegated_to") or "").strip())
    return {
        "total_nodes": total_nodes,
        "recorded_nodes": len(execution_trace),
        "completed_nodes": completed,
        "failed_nodes": failed,
        "delegated_nodes": delegated,
        "escalated_nodes": escalated,
        "all_nodes_recorded": len(execution_trace) == total_nodes,
        "all_nodes_succeeded": total_nodes > 0 and completed == total_nodes,
    }


def execution_ready_for_verification(
    task_dag: list[dict[str, Any]], execution_trace: list[dict[str, Any]]
) -> bool:
    if not task_dag:
        return False
    summary = summarize_execution_trace(execution_trace, task_dag=task_dag)
    return bool(summary["all_nodes_recorded"] and summary["all_nodes_succeeded"])


def _normalize_plan_step(raw_step: dict[str, Any], *, index: int) -> PlanStepContract:
    node_id = str(raw_step.get("node_id") or raw_step.get("id") or f"step-{index:03d}").strip()
    return PlanStepContract(
        node_id=node_id,
        task_type=str(raw_step.get("task_type") or raw_step.get("type") or "unknown"),
        title=str(raw_step.get("title") or raw_step.get("task") or ""),
        depends_on=[
            str(value) for value in raw_step.get("depends_on") or raw_step.get("deps") or []
        ],
        assigned_role=str(raw_step.get("assigned_role") or raw_step.get("role") or ""),
        delegated_to=str(raw_step.get("delegated_to") or ""),
        escalation_role=str(raw_step.get("escalation_role") or ""),
        dissent_state=str(raw_step.get("dissent_state") or "none"),
        verification_required=bool(raw_step.get("verification_required", False)),
        payload=dict(raw_step.get("payload") or {}),
    )


def _topological_sort(steps: list[PlanStepContract]) -> list[PlanStepContract]:
    dependents: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {step.node_id: len(step.depends_on) for step in steps}
    step_map = {step.node_id: step for step in steps}
    order_index = {step.node_id: index for index, step in enumerate(steps)}

    for step in steps:
        for dependency in step.depends_on:
            dependents[dependency].append(step.node_id)

    queue = deque(
        sorted(
            (step.node_id for step in steps if indegree[step.node_id] == 0),
            key=lambda node_id: order_index[node_id],
        )
    )
    ordered: list[PlanStepContract] = []

    while queue:
        node_id = queue.popleft()
        ordered.append(step_map[node_id])
        for dependent in sorted(dependents[node_id], key=lambda child: order_index[child]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(steps):
        raise ValueError("Task DAG contains a dependency cycle.")
    return ordered
