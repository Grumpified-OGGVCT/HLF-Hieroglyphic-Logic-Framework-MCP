"""
Plan Rebalancing — redistributes tasks when a swarm node fails mid-execution,
preserving completed work and maintaining plan DAG integrity.

Provides:
  - PlanRebalancer: redistributes uncompleted tasks across surviving nodes
  - RebalanceResult: detailed report of what was moved, preserved, and lost
  - TaskAffinityMap: tracks which nodes are best suited for which tasks

Integration points:
  - hlf_mcp.hlf.routing.node_registry: NodeRegistry for capability lookup
  - hlf_mcp.hlf.routing.capability_router: CapabilityRouter for task routing
  - hlf_mcp.hlf.checkpoint_executor: CheckpointManager for completed-work tracking
  - hlf_mcp.hlf.orchestration_failure_recovery: CrashRecovery for node state replay
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# TaskAffinityMap — node-to-task suitability scoring
# ---------------------------------------------------------------------------


@dataclass
class TaskAffinityMap:
    """Maps tasks to the nodes best suited to execute them.

    Attributes:
        task_id: The task identifier.
        preferred_nodes: Ordered list of node IDs (best first).
        capability_match_scores: Per-node match scores (0.0 to 1.0).
        fallback_nodes: Nodes that can handle the task in degraded mode.
    """

    task_id: str
    preferred_nodes: list[str] = field(default_factory=list)
    capability_match_scores: dict[str, float] = field(default_factory=dict)
    fallback_nodes: list[str] = field(default_factory=list)

    def best_node(self, available_nodes: set[str]) -> str | None:
        """Find the best available node for this task.

        Args:
            available_nodes: Set of currently available node IDs.

        Returns:
            The best available node ID, or None if no node can handle it.
        """
        for node in self.preferred_nodes:
            if node in available_nodes:
                return node
        for node in self.fallback_nodes:
            if node in available_nodes:
                return node
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "preferred_nodes": list(self.preferred_nodes),
            "capability_match_scores": dict(self.capability_match_scores),
            "fallback_nodes": list(self.fallback_nodes),
        }


# ---------------------------------------------------------------------------
# RebalanceResult — detailed rebalancing report
# ---------------------------------------------------------------------------


@dataclass
class RebalanceResult:
    """Detailed report of a plan rebalancing operation.

    Attributes:
        swarm_id: The swarm that was rebalanced.
        failed_node: The node that failed.
        tasks_preserved: Tasks that were already completed and kept.
        tasks_reassigned: Tasks that were reassigned to new nodes.
        tasks_lost: Tasks that could not be reassigned (no suitable node).
        new_node_assignments: Mapping of task_id → new_node_id.
        rebalance_time_seconds: How long rebalancing took.
        plan_version: Version stamp after rebalancing.
        integrity_checksum: SHA-256 of the rebalanced plan for verification.
    """

    swarm_id: str
    failed_node: str
    tasks_preserved: list[str] = field(default_factory=list)
    tasks_reassigned: list[str] = field(default_factory=list)
    tasks_lost: list[str] = field(default_factory=list)
    new_node_assignments: dict[str, str] = field(default_factory=dict)
    rebalance_time_seconds: float = 0.0
    plan_version: int = 0
    integrity_checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "swarm_id": self.swarm_id,
            "failed_node": self.failed_node,
            "tasks_preserved": list(self.tasks_preserved),
            "tasks_reassigned": list(self.tasks_reassigned),
            "tasks_lost": list(self.tasks_lost),
            "new_node_assignments": dict(self.new_node_assignments),
            "rebalance_time_seconds": self.rebalance_time_seconds,
            "plan_version": self.plan_version,
            "integrity_checksum": self.integrity_checksum,
        }


# ---------------------------------------------------------------------------
# PlanRebalancer — redistributes tasks on node failure
# ---------------------------------------------------------------------------


class PlanRebalancer:
    """Redistributes uncompleted tasks across surviving nodes when one fails.

    Preserves all completed work.  Uses capability-based affinity scoring
    to assign each orphaned task to the best-fit surviving node.  Falls
    back to any available node if no capability match exists.

    Usage::

        rebalancer = PlanRebalancer(affinity_map, node_registry)
        result = rebalancer.rebalance(
            swarm_id="swarm-1",
            failed_node="node-b",
            plan_data=[...],
            completed_tasks={"task-1", "task-2"},
        )
        print(f"Reassigned {len(result.tasks_reassigned)} tasks")
    """

    def __init__(
        self,
        affinity_map: dict[str, TaskAffinityMap] | None = None,
        node_registry: Any = None,  # NodeRegistry (lazy import)
        capability_router: Any = None,  # CapabilityRouter (lazy import)
        max_rebalance_attempts: int = 3,
    ) -> None:
        self._affinity_map: dict[str, TaskAffinityMap] = dict(affinity_map or {})
        self._node_registry = node_registry
        self._capability_router = capability_router
        self._max_rebalance_attempts = max_rebalance_attempts
        self._rebalance_history: list[RebalanceResult] = []
        self._plan_version: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_affinity(self, affinity: TaskAffinityMap) -> None:
        """Register a task-to-node affinity mapping.

        Args:
            affinity: The task affinity map to register.
        """
        self._affinity_map[affinity.task_id] = affinity

    def remove_affinity(self, task_id: str) -> None:
        """Remove a task affinity mapping."""
        self._affinity_map.pop(task_id, None)

    def get_affinity(self, task_id: str) -> TaskAffinityMap | None:
        """Get the affinity map for a specific task."""
        return self._affinity_map.get(task_id)

    def rebalance(
        self,
        swarm_id: str,
        failed_node: str,
        plan_data: list[dict[str, Any]],
        completed_tasks: set[str],
        surviving_nodes: list[str] | None = None,
    ) -> RebalanceResult:
        """Rebalance a plan after a node failure.

        Args:
            swarm_id: The swarm experiencing failure.
            failed_node: The node that failed.
            plan_data: The full plan with all task assignments.
            completed_tasks: Set of task IDs already completed.
            surviving_nodes: Optional explicit list of surviving node IDs.
                If None, discovered from node_registry.

        Returns:
            RebalanceResult with detailed reassignment report.
        """
        start_time = time.time()

        # Determine surviving nodes
        if surviving_nodes is not None:
            available = set(surviving_nodes)
        elif self._node_registry is not None:
            try:
                all_nodes = self._node_registry.list_nodes()
                available = {
                    n.node_id for n in all_nodes
                    if n.node_id != failed_node and n.status == "active"
                }
            except Exception:
                available = set()
        else:
            available = set()

        # Build task index from plan
        task_assignments: dict[str, str] = {}
        for step in plan_data:
            tid = step.get("node_id", step.get("task_id", ""))
            assigned = step.get("assigned_node", step.get("agent_id", ""))
            if tid:
                task_assignments[tid] = assigned

        # Identify tasks that need reassignment
        orphaned_tasks = {
            tid for tid, node in task_assignments.items()
            if node == failed_node
        }

        preserved = list(completed_tasks)
        reassigned: list[str] = []
        lost: list[str] = []
        new_assignments: dict[str, str] = {}

        for task_id in orphaned_tasks:
            if task_id in completed_tasks:
                preserved.append(task_id)
                continue

            best_node = self._find_best_node(task_id, available)
            if best_node is not None:
                reassigned.append(task_id)
                new_assignments[task_id] = best_node
            else:
                lost.append(task_id)

        self._plan_version += 1

        # Build integrity checksum of the rebalanced plan
        checksum = self._compute_rebalance_checksum(
            swarm_id, failed_node, reassigned, lost, new_assignments
        )

        result = RebalanceResult(
            swarm_id=swarm_id,
            failed_node=failed_node,
            tasks_preserved=preserved,
            tasks_reassigned=reassigned,
            tasks_lost=lost,
            new_node_assignments=new_assignments,
            rebalance_time_seconds=time.time() - start_time,
            plan_version=self._plan_version,
            integrity_checksum=checksum,
        )
        self._rebalance_history.append(result)
        return result

    def rebalance_multi_failure(
        self,
        swarm_id: str,
        failed_nodes: list[str],
        plan_data: list[dict[str, Any]],
        completed_tasks: set[str],
    ) -> list[RebalanceResult]:
        """Rebalance after multiple nodes fail simultaneously.

        Rebalances iteratively, one failed node at a time, so that each
        subsequent rebalance sees the updated assignments.

        Args:
            swarm_id: The swarm experiencing failures.
            failed_nodes: List of nodes that failed.
            plan_data: The full plan with all task assignments.
            completed_tasks: Set of task IDs already completed.

        Returns:
            List of RebalanceResults, one per failed node.
        """
        results: list[RebalanceResult] = []
        survivors: set[str] = set()

        if self._node_registry is not None:
            try:
                all_nodes = self._node_registry.list_nodes()
                survivors = {
                    n.node_id for n in all_nodes
                    if n.node_id not in failed_nodes and n.status == "active"
                }
            except Exception:
                pass

        cumulative_completed = set(completed_tasks)

        for failed_node in failed_nodes:
            result = self.rebalance(
                swarm_id=swarm_id,
                failed_node=failed_node,
                plan_data=plan_data,
                completed_tasks=cumulative_completed,
                surviving_nodes=list(survivors),
            )
            results.append(result)
            # Tasks reassigned are now considered "in progress" on new nodes
            cumulative_completed.update(result.tasks_reassigned)
            survivors.discard(failed_node)

        return results

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate rebalancing statistics."""
        if not self._rebalance_history:
            return {
                "total_rebalances": 0,
                "total_tasks_reassigned": 0,
                "total_tasks_lost": 0,
                "total_tasks_preserved": 0,
                "average_rebalance_time": 0.0,
            }

        total = len(self._rebalance_history)
        reassigned = sum(len(r.tasks_reassigned) for r in self._rebalance_history)
        lost = sum(len(r.tasks_lost) for r in self._rebalance_history)
        preserved = sum(len(r.tasks_preserved) for r in self._rebalance_history)
        avg_time = sum(r.rebalance_time_seconds for r in self._rebalance_history) / total

        return {
            "total_rebalances": total,
            "total_tasks_reassigned": reassigned,
            "total_tasks_lost": lost,
            "total_tasks_preserved": preserved,
            "average_rebalance_time": round(avg_time, 4),
            "plan_version": self._plan_version,
        }

    def get_history(self) -> list[RebalanceResult]:
        """Return full rebalance history."""
        return list(self._rebalance_history)

    def clear_history(self) -> None:
        """Clear rebalance history."""
        self._rebalance_history.clear()
        self._plan_version = 0

    def build_rebalanced_plan(
        self,
        plan_data: list[dict[str, Any]],
        new_assignments: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Apply new task assignments to produce a rebalanced plan.

        Args:
            plan_data: Original plan data.
            new_assignments: Mapping of task_id → new_node_id.

        Returns:
            Rebalanced plan with updated node assignments.
        """
        rebalanced = deepcopy(plan_data)
        for step in rebalanced:
            tid = step.get("node_id", step.get("task_id", ""))
            if tid in new_assignments:
                if "assigned_node" in step:
                    step["assigned_node"] = new_assignments[tid]
                if "agent_id" in step:
                    step["agent_id"] = new_assignments[tid]
                step["rebalanced"] = True
                step["original_node"] = step.get(
                    "original_node", step.get("assigned_node", step.get("agent_id", ""))
                )
        return rebalanced

    def validate_rebalance_integrity(
        self, result: RebalanceResult
    ) -> bool:
        """Validate the integrity of a rebalance result.

        Args:
            result: The rebalance result to validate.

        Returns:
            True if the checksum matches.
        """
        expected = self._compute_rebalance_checksum(
            result.swarm_id,
            result.failed_node,
            result.tasks_reassigned,
            result.tasks_lost,
            result.new_node_assignments,
        )
        return result.integrity_checksum == expected

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_best_node(self, task_id: str, available: set[str]) -> str | None:
        """Find the best available node for a given task.

        Checks affinity map first, then falls back to capability routing.
        """
        # Check affinity map
        affinity = self._affinity_map.get(task_id)
        if affinity is not None:
            best = affinity.best_node(available)
            if best is not None:
                return best

        # Fall back to capability router
        if self._capability_router is not None and available:
            try:
                match = self._capability_router.find_best_node(
                    task_id=task_id, available_nodes=list(available)
                )
                if match is not None:
                    return match.node_id
            except Exception:
                pass

        # Last resort: any available node
        if available:
            return next(iter(sorted(available)))

        return None

    @staticmethod
    def _compute_rebalance_checksum(
        swarm_id: str,
        failed_node: str,
        reassigned: list[str],
        lost: list[str],
        assignments: dict[str, str],
    ) -> str:
        """Compute a deterministic SHA-256 checksum of rebalance data."""
        payload = json.dumps(
            {
                "swarm_id": swarm_id,
                "failed_node": failed_node,
                "reassigned": sorted(reassigned),
                "lost": sorted(lost),
                "assignments": dict(sorted(assignments.items())),
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
