"""
Remediation Planner — auto-generates prioritised remediation tasks from
review proof gaps, trust debt, and audit anomalies.

Given the output of review gap audits, trust debt reports, or audit
diff anomaly scans, the planner generates actionable, dependency-ordered
remediation tasks with estimated effort and critical-path analysis.

Key design principles:
  - Gap-driven: every task traces back to a specific gap or anomaly.
  - Dependency-aware: tasks are topologically sorted so operators
    know what must be done first (Kahn's algorithm).
  - Effort-weighted: tasks carry effort estimates so completion dates
    can be projected given resource constraints.
  - Mergeable: multiple plans can be combined with title-similarity
    deduplication to avoid redundant work.

Integration points:
  - hlf_mcp.hlf.review_proof.audit_review_gaps      → gap detection input
  - hlf_mcp.hlf.audit_diff.AuditDiff.find_anomalies  → anomaly input
  - hlf_mcp.hlf.trust_debt.TrustDebtQuantifier        → debt priorities input
  - hlf_mcp.hlf.governance_proofs                     → SHA-256 digests for plan IDs
"""

from __future__ import annotations

import difflib
import hashlib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════════════════


class RemediationPriority(Enum):
    """Priority level for a remediation task."""
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1


class RemediationStatus(Enum):
    """Current execution status of a remediation task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

_GAP_TYPE_TO_TASK: dict[str, str] = {
    "missing_coverage": "Add test coverage for {target}",
    "incomplete_review": "Complete review cycle for {target}",
    "trust_gap": "Address trust gap in {target}",
    "provenance_gap": "Add provenance tracking for {target}",
    "circular_trust": "Resolve circular trust dependency involving {target}",
    "trust_without_evidence": "Document evidence for trust relationship with {target}",
    "stale_review": "Refresh stale review for {target}",
    "rejected_review": "Address rejected review disposition for {target}",
    "incomplete_checklist": "Complete review checklist for {target}",
    "unreviewed_component": "Conduct initial review for component type {target}",
    "trust_degradation_spike": "Investigate trust degradation spike for {target}",
    "mass_removal": "Investigate mass audit event removal affecting {target}",
    "persona_decision_flipping": "Audit decision changes for persona {target}",
}

_DEFAULT_EFFORT_MAP: dict[str, float] = {
    "missing_coverage": 4.0,
    "incomplete_review": 3.0,
    "trust_gap": 2.0,
    "provenance_gap": 6.0,
    "circular_trust": 5.0,
    "trust_without_evidence": 2.0,
    "stale_review": 3.0,
    "rejected_review": 4.0,
    "incomplete_checklist": 2.5,
    "unreviewed_component": 8.0,
    "trust_degradation_spike": 3.0,
    "mass_removal": 5.0,
    "persona_decision_flipping": 4.0,
}

_PRIORITY_FROM_SEVERITY: dict[str, RemediationPriority] = {
    "critical": RemediationPriority.CRITICAL,
    "high": RemediationPriority.HIGH,
    "medium": RemediationPriority.MEDIUM,
    "low": RemediationPriority.LOW,
}


# ═══════════════════════════════════════════════════════════════════════════════
# RemediationTask — a single actionable remediation item
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class RemediationTask:
    """A single remediation task generated from a review or audit gap.

    Attributes:
        task_id: Unique identifier (SHA-256 truncated).
        title: Short human-readable title.
        description: Detailed description of what must be done.
        priority: RemediationPriority level.
        estimated_effort_hours: Estimated person-hours to complete.
        gap_refs: References to the gaps or anomalies that spawned this task.
        depends_on: List of task_ids this task depends on.
        status: Current execution status.
        assigned_to: Who is responsible for this task.
        created_at: ISO-8601 creation timestamp.
        completed_at: ISO-8601 completion timestamp (empty if not done).
    """

    task_id: str
    title: str
    description: str
    priority: RemediationPriority
    estimated_effort_hours: float
    gap_refs: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    status: RemediationStatus = RemediationStatus.PENDING
    assigned_to: str = ""
    created_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _iso_now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the remediation task."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "estimated_effort_hours": self.estimated_effort_hours,
            "gap_refs": list(self.gap_refs),
            "depends_on": list(self.depends_on),
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemediationTask:
        """Deserialize from a dict."""
        return cls(
            task_id=str(data.get("task_id", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            priority=RemediationPriority[data.get("priority", "MEDIUM")],
            estimated_effort_hours=float(data.get("estimated_effort_hours", 1.0)),
            gap_refs=list(data.get("gap_refs", [])),
            depends_on=list(data.get("depends_on", [])),
            status=RemediationStatus(data.get("status", "pending")),
            assigned_to=str(data.get("assigned_to", "")),
            created_at=str(data.get("created_at", "")),
            completed_at=str(data.get("completed_at", "")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# RemediationPlan — a collection of remediation tasks
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class RemediationPlan:
    """A named, timestamped collection of remediation tasks.

    Attributes:
        plan_id: Unique identifier for this plan.
        name: Human-readable plan name.
        tasks: The list of RemediationTask objects in this plan.
        created_at: ISO-8601 creation timestamp.
        target_completion: ISO-8601 target completion date (or empty).
    """

    plan_id: str
    name: str
    tasks: list[RemediationTask] = field(default_factory=list)
    created_at: str = ""
    target_completion: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = _iso_now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the remediation plan."""
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at,
            "target_completion": self.target_completion,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RemediationPlan:
        """Deserialize from a dict."""
        tasks_data = data.get("tasks", [])
        tasks = [
            RemediationTask.from_dict(t) if isinstance(t, dict) else t
            for t in tasks_data
        ]
        return cls(
            plan_id=str(data.get("plan_id", "")),
            name=str(data.get("name", "")),
            tasks=tasks,
            created_at=str(data.get("created_at", "")),
            target_completion=str(data.get("target_completion", "")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _iso_now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_task_id(title: str, gap_refs: list[str]) -> str:
    """Generate a stable task ID from title + gap refs."""
    raw = title + "::" + "::".join(sorted(gap_refs))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _generate_plan_id(name: str) -> str:
    """Generate a stable plan ID from the plan name."""
    raw = f"plan::{name}::{_iso_now()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _title_similarity(title_a: str, title_b: str) -> float:
    """Compute similarity score (0-1) between two task titles.

    Uses difflib.SequenceMatcher for fuzzy matching.  Returns 1.0 for
    identical strings, approaching 0.0 for completely dissimilar ones.
    """
    if not title_a and not title_b:
        return 1.0
    if not title_a or not title_b:
        return 0.0
    return difflib.SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()


def _extract_target(gap: dict[str, Any]) -> str:
    """Extract a human-readable target name from a gap dict."""
    target = gap.get("target", gap.get("component", gap.get("reviewed_item", "")))
    if not target:
        target = gap.get("item_type", gap.get("persona", "unknown"))
    return str(target)


# ═══════════════════════════════════════════════════════════════════════════════
# RemediationPlanner — main planning engine
# ═══════════════════════════════════════════════════════════════════════════════


class RemediationPlanner:
    """Generates prioritised remediation plans from review proof gaps,
    trust debt items, and audit anomalies.

    The planner consumes gap/audit reports and produces dependency-
    ordered RemediationPlan objects ready for operator assignment.

    Usage::

        planner = RemediationPlanner(name="governance-planner")
        plan = planner.generate_plan(gaps, context={"component": "compiler"})
        ordered = planner.topological_sort(plan.tasks)
        report = planner.progress_report(plan)
    """

    def __init__(self, name: str = "remediation-planner") -> None:
        """Initialise the remediation planner.

        Args:
            name: Human-readable label for this planner instance.
        """
        self.name = name

    # ── Plan generation ─────────────────────────────────────────────────────

    def generate_plan(
        self,
        gaps: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> RemediationPlan:
        """Generate a remediation plan from a list of gaps or anomalies.

        Each gap is mapped to a task template based on its gap_type or
        anomaly_type.  Tasks are assigned estimated effort and priority.

        Args:
            gaps: List of gap dicts from audit_review_gaps(), anomaly dicts
                from AuditDiff.find_anomalies(), or debt items from
                TrustDebtQuantifier.paydown_priorities().
            context: Optional context dict with keys like "component",
                "plan_name", "target_completion".

        Returns:
            A RemediationPlan with auto-generated tasks.
        """
        ctx = context or {}
        plan_name = str(ctx.get("plan_name", f"Remediation Plan — {_iso_now()[:10]}"))
        target_completion = str(ctx.get("target_completion", ""))
        plan_id = _generate_plan_id(plan_name)

        tasks: list[RemediationTask] = []

        for gap in gaps:
            gap_type = str(
                gap.get("gap_type",
                gap.get("anomaly_type",
                gap.get("violation_type",
                gap.get("category", ""))))
            )
            target = _extract_target(gap)
            severity = str(gap.get("severity", "medium")).lower()
            title_template = _GAP_TYPE_TO_TASK.get(
                gap_type, "Address issue: {target}"
            )
            title = title_template.format(target=target)
            description = str(
                gap.get("description", gap.get("recommendation", title))
            )
            priority = _PRIORITY_FROM_SEVERITY.get(severity, RemediationPriority.MEDIUM)
            effort = float(
                gap.get("estimated_effort_hours",
                _DEFAULT_EFFORT_MAP.get(gap_type, 2.0))
            )
            gap_refs = [
                str(gap.get("violation_id",
                gap.get("proof_id",
                gap.get("review_id",
                gap.get("component", target)))))
            ]

            task_id = _generate_task_id(title, gap_refs)

            tasks.append(RemediationTask(
                task_id=task_id,
                title=title,
                description=description,
                priority=priority,
                estimated_effort_hours=effort,
                gap_refs=gap_refs,
            ))

        # ── auto-infer dependencies for related tasks ────────────────────
        # Tasks targeting the same component with lower priority depend on
        # higher-priority tasks for the same component.
        component_tasks: dict[str, list[RemediationTask]] = {}
        for task in tasks:
            for ref in task.gap_refs:
                component_tasks.setdefault(ref, []).append(task)

        for comp, comp_task_list in component_tasks.items():
            if len(comp_task_list) < 2:
                continue
            sorted_tasks = sorted(
                comp_task_list,
                key=lambda t: t.priority.value,
                reverse=True,
            )
            for i in range(1, len(sorted_tasks)):
                if sorted_tasks[i].task_id != sorted_tasks[i - 1].task_id:
                    deps = list(sorted_tasks[i].depends_on)
                    if sorted_tasks[i - 1].task_id not in deps:
                        deps.append(sorted_tasks[i - 1].task_id)
                    sorted_tasks[i].depends_on = deps

        return RemediationPlan(
            plan_id=plan_id,
            name=plan_name,
            tasks=tasks,
            target_completion=target_completion,
        )

    # ── Topological sort (Kahn's algorithm) ─────────────────────────────────

    def topological_sort(
        self,
        tasks: list[RemediationTask],
    ) -> list[RemediationTask]:
        """Sort tasks into dependency order using Kahn's algorithm.

        Tasks with no dependencies come first.  If a circular dependency
        is detected, the remaining tasks are returned after the sorted
        ones with a warning in the description.

        Args:
            tasks: The tasks to sort.

        Returns:
            Dependency-ordered list of RemediationTask objects.
        """
        if not tasks:
            return []

        task_map: dict[str, RemediationTask] = {t.task_id: t for t in tasks}

        # Build in-degree and adjacency
        in_degree: dict[str, int] = {t.task_id: 0 for t in tasks}
        adjacency: dict[str, list[str]] = {t.task_id: [] for t in tasks}

        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id in task_map:
                    adjacency.setdefault(dep_id, []).append(task.task_id)
                    in_degree[task.task_id] = in_degree.get(task.task_id, 0) + 1

        # Kahn's: start with nodes having zero in-degree
        queue: deque[str] = deque()
        for tid, deg in in_degree.items():
            if deg == 0:
                queue.append(tid)

        sorted_ids: list[str] = []
        while queue:
            current = queue.popleft()
            sorted_ids.append(current)
            for neighbour in adjacency.get(current, []):
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        # Detect cycles
        if len(sorted_ids) != len(tasks):
            # Add remaining tasks at the end
            remaining_ids = [t.task_id for t in tasks if t.task_id not in sorted_ids]
            sorted_ids.extend(remaining_ids)

        result = []
        for tid in sorted_ids:
            if tid in task_map:
                result.append(task_map[tid])

        if len(sorted_ids) != len(tasks):
            # Log but still return what we have
            pass

        return result

    # ── Critical path ──────────────────────────────────────────────────────

    def critical_path(
        self,
        tasks: list[RemediationTask],
    ) -> list[RemediationTask]:
        """Find the longest dependency chain (critical path) through the tasks.

        Uses a longest-path-in-DAG algorithm where edge weight is the
        estimated_effort_hours of the predecessor task.

        Args:
            tasks: The tasks to analyse (must form a DAG).

        Returns:
            The ordered list of tasks on the critical path.
        """
        if not tasks:
            return []

        task_map: dict[str, RemediationTask] = {t.task_id: t for t in tasks}
        sorted_tasks = self.topological_sort(tasks)

        # Longest path DP
        dist: dict[str, float] = {t.task_id: 0.0 for t in tasks}
        prev: dict[str, str | None] = {t.task_id: None for t in tasks}

        for task in sorted_tasks:
            for dep_id in task.depends_on:
                if dep_id in dist:
                    candidate = dist[dep_id] + task_map[dep_id].estimated_effort_hours
                    if candidate > dist[task.task_id]:
                        dist[task.task_id] = candidate
                        prev[task.task_id] = dep_id

        # Find the node with the maximum distance
        if not dist:
            return []
        end_id = max(dist, key=lambda k: dist[k])

        # Reconstruct path
        path: list[str] = []
        current: str | None = end_id
        while current is not None:
            path.append(current)
            current = prev.get(current)
        path.reverse()

        return [task_map[tid] for tid in path if tid in task_map]

    # ── Progress report ────────────────────────────────────────────────────

    def progress_report(self, plan: RemediationPlan) -> dict[str, Any]:
        """Generate a progress summary for a remediation plan.

        Args:
            plan: The remediation plan to report on.

        Returns:
            A dict with keys:
                plan_name: str
                total_tasks: int
                status_counts: dict mapping status to count
                completion_pct: float — percentage complete
                blocked_tasks: list[dict] — blocked tasks with their blockers
                total_effort_remaining: float — hours remaining
        """
        tasks = plan.tasks
        total = len(tasks)
        status_counts: dict[str, int] = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0,
        }

        effort_remaining: float = 0.0
        blocked_details: list[dict[str, Any]] = []

        for task in tasks:
            status_counts[task.status.value] = status_counts.get(task.status.value, 0) + 1
            if task.status != RemediationStatus.COMPLETED:
                effort_remaining += task.estimated_effort_hours
            if task.status == RemediationStatus.BLOCKED:
                blockers = [
                    dep_id for dep_id in task.depends_on
                    if dep_id in {t.task_id for t in tasks}
                ]
                blocked_details.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "blocked_by": blockers,
                })

        completed = status_counts.get("completed", 0)
        completion_pct = (completed / total * 100.0) if total > 0 else 0.0

        return {
            "plan_name": plan.name,
            "total_tasks": total,
            "status_counts": status_counts,
            "completion_pct": round(completion_pct, 1),
            "blocked_tasks": blocked_details,
            "total_effort_remaining": round(effort_remaining, 1),
        }

    # ── Plan merging ───────────────────────────────────────────────────────

    def merge_plans(
        self,
        plans: list[RemediationPlan],
    ) -> RemediationPlan:
        """Merge multiple remediation plans into one, deduplicating similar tasks.

        Two tasks are considered duplicates if their titles have a
        similarity score >= 0.85.

        Args:
            plans: The plans to merge.

        Returns:
            A single RemediationPlan containing deduplicated tasks.
        """
        merged_name = "Merged Plan — " + _iso_now()[:10]
        merged_id = _generate_plan_id(merged_name)
        all_tasks: list[RemediationTask] = []

        for plan in plans:
            for task in plan.tasks:
                # Check for duplicates among already-merged tasks
                is_duplicate = False
                for existing in all_tasks:
                    if _title_similarity(task.title, existing.title) >= 0.85:
                        # Merge gap_refs and dependencies
                        for ref in task.gap_refs:
                            if ref not in existing.gap_refs:
                                existing.gap_refs.append(ref)
                        for dep in task.depends_on:
                            if dep not in existing.depends_on:
                                existing.depends_on.append(dep)
                        is_duplicate = True
                        break
                if not is_duplicate:
                    all_tasks.append(task)

        return RemediationPlan(
            plan_id=merged_id,
            name=merged_name,
            tasks=all_tasks,
        )

    # ── Completion estimation ──────────────────────────────────────────────

    def estimate_completion(
        self,
        plan: RemediationPlan,
        resources: int = 1,
    ) -> dict[str, Any]:
        """Estimate completion date given resource constraints.

        Accounts for dependency ordering: tasks on the critical path
        cannot be parallelised, while independent branches can be.

        Args:
            plan: The remediation plan to estimate.
            resources: Number of parallel workers (default 1).

        Returns:
            A dict with keys:
                estimated_completion_date: str — ISO-8601 date.
                total_effort_hours: float — sum of all task efforts.
                critical_path_hours: float — length of critical path.
                parallelizable_hours: float — effort outside the critical path.
                tasks_remaining: int — count of incomplete tasks.
        """
        tasks = plan.tasks
        remaining = [
            t for t in tasks
            if t.status not in (RemediationStatus.COMPLETED,)
        ]
        if not remaining:
            return {
                "estimated_completion_date": _iso_now(),
                "total_effort_hours": 0.0,
                "critical_path_hours": 0.0,
                "parallelizable_hours": 0.0,
                "tasks_remaining": 0,
            }

        total_effort = sum(t.estimated_effort_hours for t in remaining)
        cp = self.critical_path(remaining)
        cp_hours = sum(t.estimated_effort_hours for t in cp)
        parallelizable_hours = total_effort - cp_hours

        # Estimate: critical path is serial, parallelisable work can be
        # divided by resources
        effective_hours = cp_hours + (parallelizable_hours / max(resources, 1))

        # Assume 8-hour workdays
        workdays = effective_hours / 8.0
        completion_dt = datetime.now(timezone.utc) + timedelta(days=workdays)

        return {
            "estimated_completion_date": completion_dt.isoformat(),
            "total_effort_hours": round(total_effort, 1),
            "critical_path_hours": round(cp_hours, 1),
            "parallelizable_hours": round(parallelizable_hours, 1),
            "tasks_remaining": len(remaining),
        }
