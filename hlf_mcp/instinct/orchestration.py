from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.persona_runtime import resolve_persona_runtime_metadata


_DENIED_VERIFICATION_STATUSES = {"blocked", "counterexample", "denied", "error", "failed"}
_ALLOWED_VERIFICATION_STATUSES = {"allowed", "approved", "ok", "passed", "proven", "success"}


@dataclass(slots=True)
class PlanStepContract:
    node_id: str
    task_type: str
    title: str = ""
    depends_on: list[str] = field(default_factory=list)
    assigned_role: str = ""
    assigned_persona: dict[str, Any] | None = None
    delegated_to: str = ""
    delegated_persona: dict[str, Any] | None = None
    escalation_role: str = ""
    escalation_persona: dict[str, Any] | None = None
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
            "assigned_persona": dict(self.assigned_persona) if self.assigned_persona else None,
            "delegated_to": self.delegated_to,
            "delegated_persona": dict(self.delegated_persona) if self.delegated_persona else None,
            "escalation_role": self.escalation_role,
            "escalation_persona": dict(self.escalation_persona)
            if self.escalation_persona
            else None,
            "dissent_state": self.dissent_state,
            "verification_required": self.verification_required,
            "payload": dict(self.payload),
        }


@dataclass(slots=True)
class ExecutionTraceEntry:
    node_id: str
    task_type: str
    assigned_role: str = ""
    assigned_persona: dict[str, Any] | None = None
    success: bool = False
    duration_ms: float = 0.0
    affected_files: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    delegated_to: str = ""
    delegated_persona: dict[str, Any] | None = None
    escalation_role: str = ""
    escalation_persona: dict[str, Any] | None = None
    dissent_state: str = "none"
    verification_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "task_type": self.task_type,
            "assigned_role": self.assigned_role,
            "assigned_persona": dict(self.assigned_persona) if self.assigned_persona else None,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "affected_files": list(self.affected_files),
            "outputs": list(self.outputs),
            "delegated_to": self.delegated_to,
            "delegated_persona": dict(self.delegated_persona) if self.delegated_persona else None,
            "escalation_role": self.escalation_role,
            "escalation_persona": dict(self.escalation_persona)
            if self.escalation_persona
            else None,
            "dissent_state": self.dissent_state,
            "verification_status": self.verification_status,
        }


def build_orchestration_contract(
    task_dag: list[dict[str, Any]],
    execution_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    step_map = {str(step.get("node_id") or ""): step for step in task_dag}
    trace_map = {str(entry.get("node_id") or ""): entry for entry in execution_trace}
    nodes: list[dict[str, Any]] = []

    delegated_nodes = 0
    escalated_nodes = 0
    dissenting_nodes = 0
    allowed_nodes = 0
    denied_nodes = 0
    pending_nodes = 0
    handoff_nodes = 0
    verification_required_nodes = 0
    persona_bound_nodes = 0
    persona_bindings: dict[str, int] = {}

    for step in task_dag:
        node_id = str(step.get("node_id") or "")
        trace = trace_map.get(node_id, {})
        recorded = bool(trace)
        delegated_to = str(trace.get("delegated_to") or step.get("delegated_to") or "")
        escalation_role = str(trace.get("escalation_role") or step.get("escalation_role") or "")
        dissent_state = str(trace.get("dissent_state") or step.get("dissent_state") or "none")
        verification_required = bool(step.get("verification_required", False))
        verification_status = str(
            trace.get("verification_status")
            or ("passed" if trace.get("success") is True else "pending")
            if recorded
            else "pending"
        )
        assigned_persona = _coerce_persona_metadata(
            trace.get("assigned_persona") or step.get("assigned_persona")
        )
        delegated_persona = _coerce_persona_metadata(
            trace.get("delegated_persona") or step.get("delegated_persona")
        )
        escalation_persona = _coerce_persona_metadata(
            trace.get("escalation_persona") or step.get("escalation_persona")
        )
        decision_state = _classify_orchestration_decision(
            recorded=recorded,
            success=trace.get("success") if recorded else None,
            verification_status=verification_status,
        )
        delegated = bool(delegated_to)
        escalated = bool(escalation_role)
        dissenting = dissent_state != "none"
        handoff_required = delegated or escalated or dissenting

        if verification_required:
            verification_required_nodes += 1
        if delegated:
            delegated_nodes += 1
        if escalated:
            escalated_nodes += 1
        if dissenting:
            dissenting_nodes += 1
        if handoff_required:
            handoff_nodes += 1
        if assigned_persona or delegated_persona or escalation_persona:
            persona_bound_nodes += 1
        for persona_metadata in (assigned_persona, delegated_persona, escalation_persona):
            if isinstance(persona_metadata, dict):
                persona_name = str(persona_metadata.get("persona") or "")
                if persona_name:
                    persona_bindings[persona_name] = persona_bindings.get(persona_name, 0) + 1
        if decision_state == "allowed":
            allowed_nodes += 1
        elif decision_state == "denied":
            denied_nodes += 1
        else:
            pending_nodes += 1

        nodes.append(
            {
                "node_id": node_id,
                "task_type": str(step.get("task_type") or "unknown"),
                "title": str(step.get("title") or ""),
                "depends_on": [str(value) for value in step.get("depends_on") or []],
                "assigned_role": str(trace.get("assigned_role") or step.get("assigned_role") or ""),
                "assigned_persona": assigned_persona,
                "delegated": delegated,
                "delegated_to": delegated_to,
                "delegated_persona": delegated_persona,
                "escalated": escalated,
                "escalation_role": escalation_role,
                "escalation_persona": escalation_persona,
                "dissenting": dissenting,
                "dissent_state": dissent_state,
                "handoff_required": handoff_required,
                "verification_required": verification_required,
                "verification_status": verification_status,
                "recorded": recorded,
                "success": trace.get("success") if recorded else None,
                "duration_ms": float(trace.get("duration_ms") or 0.0) if recorded else 0.0,
                "affected_files": [str(value) for value in trace.get("affected_files", [])],
                "outputs": [str(value) for value in trace.get("outputs", [])],
                "decision_state": decision_state,
            }
        )

    total_nodes = len(task_dag)
    recorded_nodes = len(trace_map)
    return {
        "contract_version": "1.0",
        "summary": {
            "total_nodes": total_nodes,
            "recorded_nodes": recorded_nodes,
            "planned_nodes": max(total_nodes - recorded_nodes, 0),
            "allowed_nodes": allowed_nodes,
            "denied_nodes": denied_nodes,
            "pending_nodes": pending_nodes,
            "delegated_nodes": delegated_nodes,
            "escalated_nodes": escalated_nodes,
            "dissenting_nodes": dissenting_nodes,
            "handoff_nodes": handoff_nodes,
            "verification_required_nodes": verification_required_nodes,
            "persona_bound_nodes": persona_bound_nodes,
            "persona_bindings": dict(sorted(persona_bindings.items())),
            "all_nodes_recorded": recorded_nodes == total_nodes,
            "all_nodes_allowed": total_nodes > 0 and allowed_nodes == total_nodes,
            "all_decisions_resolved": recorded_nodes == total_nodes and pending_nodes == 0,
        },
        "nodes": nodes,
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
            assigned_persona=_coerce_persona_metadata(
                item.get("assigned_persona") or plan_step.get("assigned_persona")
            ),
            success=bool(item.get("success", False)),
            duration_ms=float(item.get("duration_ms") or 0.0),
            affected_files=[str(value) for value in item.get("affected_files", [])],
            outputs=[str(value) for value in item.get("outputs", [])],
            delegated_to=str(item.get("delegated_to") or plan_step.get("delegated_to") or ""),
            delegated_persona=_coerce_persona_metadata(
                item.get("delegated_persona") or plan_step.get("delegated_persona")
            ),
            escalation_role=str(
                item.get("escalation_role") or plan_step.get("escalation_role") or ""
            ),
            escalation_persona=_coerce_persona_metadata(
                item.get("escalation_persona") or plan_step.get("escalation_persona")
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
    orchestration_contract = build_orchestration_contract(task_dag, execution_trace)
    contract_summary = orchestration_contract["summary"]
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
        "dissenting_nodes": contract_summary["dissenting_nodes"],
        "allowed_nodes": contract_summary["allowed_nodes"],
        "denied_nodes": contract_summary["denied_nodes"],
        "pending_nodes": contract_summary["pending_nodes"],
        "handoff_nodes": contract_summary["handoff_nodes"],
        "all_nodes_recorded": contract_summary["all_nodes_recorded"],
        "all_nodes_succeeded": total_nodes > 0 and completed == total_nodes,
        "all_nodes_allowed": contract_summary["all_nodes_allowed"],
        "all_decisions_resolved": contract_summary["all_decisions_resolved"],
    }


def execution_ready_for_verification(
    task_dag: list[dict[str, Any]], execution_trace: list[dict[str, Any]]
) -> bool:
    if not task_dag:
        return False
    contract_summary = build_orchestration_contract(task_dag, execution_trace)["summary"]
    return bool(
        contract_summary["all_nodes_recorded"]
        and contract_summary["denied_nodes"] == 0
        and contract_summary["pending_nodes"] == 0
    )


def _classify_orchestration_decision(
    *,
    recorded: bool,
    success: bool | None,
    verification_status: str,
) -> str:
    if not recorded:
        return "planned"
    normalized_status = verification_status.strip().lower()
    if success is False or normalized_status in _DENIED_VERIFICATION_STATUSES:
        return "denied"
    if success is True or normalized_status in _ALLOWED_VERIFICATION_STATUSES:
        return "allowed"
    return "pending"


def _normalize_plan_step(raw_step: dict[str, Any], *, index: int) -> PlanStepContract:
    node_id = str(raw_step.get("node_id") or raw_step.get("id") or f"step-{index:03d}").strip()
    task_type = str(raw_step.get("task_type") or raw_step.get("type") or "unknown")
    title = str(raw_step.get("title") or raw_step.get("task") or "")
    assigned_role = str(
        raw_step.get("assigned_role")
        or raw_step.get("role")
        or _infer_assigned_role(raw_step, task_type=task_type, title=title)
        or ""
    )
    return PlanStepContract(
        node_id=node_id,
        task_type=task_type,
        title=title,
        depends_on=[
            str(value) for value in raw_step.get("depends_on") or raw_step.get("deps") or []
        ],
        assigned_role=assigned_role,
        assigned_persona=_coerce_persona_metadata(raw_step.get("assigned_persona"))
        or resolve_persona_runtime_metadata(assigned_role),
        delegated_to=str(raw_step.get("delegated_to") or ""),
        delegated_persona=_coerce_persona_metadata(raw_step.get("delegated_persona"))
        or resolve_persona_runtime_metadata(raw_step.get("delegated_to")),
        escalation_role=str(raw_step.get("escalation_role") or ""),
        escalation_persona=_coerce_persona_metadata(raw_step.get("escalation_persona"))
        or resolve_persona_runtime_metadata(raw_step.get("escalation_role")),
        dissent_state=str(raw_step.get("dissent_state") or "none"),
        verification_required=bool(raw_step.get("verification_required", False)),
        payload=dict(raw_step.get("payload") or {}),
    )


def _coerce_persona_metadata(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    persona_name = value.get("persona")
    if not isinstance(persona_name, str) or not persona_name.strip():
        return None
    return resolve_persona_runtime_metadata(persona_name) or {
        "persona": persona_name.strip().lower(),
        "lane": str(value.get("lane") or "bridge-true"),
        "runtime_authority": bool(value.get("runtime_authority", False)),
        "internal_role": str(value.get("internal_role") or ""),
        "maintainer_mode": str(value.get("maintainer_mode") or ""),
        "hat": str(value.get("hat") or ""),
        "role": str(value.get("role") or ""),
        "upstream_source": str(value.get("upstream_source") or ""),
        "cross_awareness": [
            str(item)
            for item in value.get("cross_awareness") or []
            if isinstance(item, str) and item
        ],
    }


def _infer_assigned_role(raw_step: dict[str, Any], *, task_type: str, title: str) -> str:
    delegated_to = str(raw_step.get("delegated_to") or "").strip().lower()
    escalation_role = str(raw_step.get("escalation_role") or "").strip().lower()
    if delegated_to:
        return delegated_to
    if escalation_role:
        return escalation_role

    normalized_task_type = task_type.strip().lower()
    normalized_title = title.strip().lower()
    combined = f"{normalized_task_type} {normalized_title}".strip()

    if any(token in combined for token in ("verify", "proof", "validator", "test", "cove")):
        return "cove"
    if any(token in combined for token in ("security", "guard", "policy", "threat", "sentinel")):
        return "sentinel"
    if any(token in combined for token in ("doc", "readme", "spec", "summary", "announce", "herald")):
        return "herald"
    if any(token in combined for token in ("plan", "roadmap", "priority", "triage", "strategy")):
        return "strategist"
    if any(token in combined for token in ("audit", "ledger", "trace", "memory", "scribe")):
        return "scribe"
    if any(token in combined for token in ("workflow", "transport", "schema", "mcp", "steward")):
        return "steward"
    if any(token in combined for token in ("synth", "consolid", "merge", "reconcile")):
        return "consolidator"
    return ""


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
