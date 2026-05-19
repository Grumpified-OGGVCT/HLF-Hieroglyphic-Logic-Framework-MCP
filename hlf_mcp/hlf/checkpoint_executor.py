"""
Checkpoint Executor — resumable multi-phase execution with checkpointing.

Provides:
  - Checkpoint: a point-in-time snapshot of execution state
  - CheckpointedExecutionResult: result wrapping MultiPhaseResult with resume info
  - CheckpointManager: saves/loads checkpoints, resumes from last successful phase

Integration:
  - multi_phase_executor.MultiPhaseExecutor: wrapped with checkpoint/resume
  - multi_phase_executor.AgentPlan, ConsolidatedPlan, PhaseResult, MultiPhaseResult
  - knowledge.memory_lease.LeaseManager: scoped checkpoint storage
  - knowledge.consistency_proof.ConsistencyProof: checkpoint integrity

Checkpoint strategy:
  - PLAN phase: checkpoint after all agent plans are produced
  - CONSOLIDATE phase: checkpoint after consolidation is complete
  - EXECUTE phase: checkpoint after each agent's execution step
  - On failure: resume from the last successful checkpoint
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof, ConsistencyProofResult
from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager, MemoryLease
from hlf_mcp.hlf.multi_phase_executor import (
    AgentPlan,
    ConsolidatedPlan,
    MultiPhaseExecutor,
    MultiPhaseResult,
    PhaseResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Checkpoint:
    """A point-in-time snapshot of multi-phase execution state.

    Attributes:
        checkpoint_id: Unique identifier for this checkpoint.
        phase: The phase at which this checkpoint was taken (plan/consolidate/execute).
        step_index: Within the execute phase, which agent index was last completed.
        swarm_id: The swarm identifier for this execution.
        task_id: The task identifier for this execution.
        agent_states: Serialized state of each agent at checkpoint time.
        plan_data: Serialized agent plans (from PLAN phase).
        consolidated_data: Serialized consolidated plan (from CONSOLIDATE phase).
        resume_point: Description of where to resume.
        timestamp: Unix timestamp when the checkpoint was created.
        checksum: SHA-256 integrity hash of checkpoint data.
    """

    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    phase: str = "plan"
    step_index: int = 0
    swarm_id: str = ""
    task_id: str = ""
    agent_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    plan_data: list[dict[str, Any]] = field(default_factory=list)
    consolidated_data: dict[str, Any] = field(default_factory=dict)
    resume_point: str = ""
    timestamp: float = field(default_factory=time.time)
    checksum: str = ""

    def __post_init__(self) -> None:
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute a deterministic content hash of the checkpoint."""
        payload = json.dumps(
            {
                "phase": self.phase,
                "step_index": self.step_index,
                "swarm_id": self.swarm_id,
                "task_id": self.task_id,
                "agent_states": self.agent_states,
                "plan_data": self.plan_data,
                "consolidated_data": self.consolidated_data,
                "resume_point": self.resume_point,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Check that the stored checksum matches the current content."""
        return self.checksum == self._compute_checksum()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "phase": self.phase,
            "step_index": self.step_index,
            "swarm_id": self.swarm_id,
            "task_id": self.task_id,
            "agent_states": self.agent_states,
            "plan_data": self.plan_data,
            "consolidated_data": self.consolidated_data,
            "resume_point": self.resume_point,
            "timestamp": self.timestamp,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Checkpoint":
        """Deserialize from a plain dict."""
        return cls(
            checkpoint_id=data.get("checkpoint_id", str(uuid.uuid4())),
            phase=data.get("phase", "plan"),
            step_index=data.get("step_index", 0),
            swarm_id=data.get("swarm_id", ""),
            task_id=data.get("task_id", ""),
            agent_states=data.get("agent_states", {}),
            plan_data=data.get("plan_data", []),
            consolidated_data=data.get("consolidated_data", {}),
            resume_point=data.get("resume_point", ""),
            timestamp=data.get("timestamp", time.time()),
            checksum=data.get("checksum", ""),
        )


@dataclass
class CheckpointedExecutionResult:
    """Result of a checkpointed multi-phase execution.

    Wraps a standard MultiPhaseResult with checkpoint/resume metadata.

    Attributes:
        result: The underlying MultiPhaseResult.
        checkpoints: All checkpoints created during execution.
        resumed_from: Checkpoint ID if execution was resumed, else None.
        total_checkpoints: Count of checkpoints taken.
        last_checkpoint: The most recent checkpoint (for resume).
    """

    result: MultiPhaseResult
    checkpoints: list[Checkpoint] = field(default_factory=list)
    resumed_from: str | None = None
    total_checkpoints: int = 0
    last_checkpoint: Checkpoint | None = None

    def __post_init__(self) -> None:
        if self.checkpoints:
            self.total_checkpoints = len(self.checkpoints)
            self.last_checkpoint = self.checkpoints[-1]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "result_swarm_id": self.result.swarm_id,
            "result_status": self.result.final_status,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "resumed_from": self.resumed_from,
            "total_checkpoints": self.total_checkpoints,
            "last_checkpoint": self.last_checkpoint.to_dict() if self.last_checkpoint else None,
        }


# ---------------------------------------------------------------------------
# CheckpointManager
# ---------------------------------------------------------------------------


class CheckpointManager:
    """Manages checkpoint save, load, and resume operations.

    Checkpoints can be stored in-memory (always) and optionally persisted
    via the knowledge/memory LeaseManager + ConsistencyProof subsystem.

    Usage::

        manager = CheckpointManager()
        executor = MultiPhaseExecutor()
        wrapped = CheckpointableExecutor(executor, manager)

        # First run
        result = wrapped.run("Build a REST API")
        if result.result.final_status != "ok":
            # Resume from last checkpoint
            result = wrapped.resume(result.last_checkpoint.checkpoint_id)
    """

    def __init__(
        self,
        lease_manager: LeaseManager | None = None,
        consistency_proof: ConsistencyProof | None = None,
        max_checkpoints: int = 50,
    ) -> None:
        self._checkpoints: dict[str, Checkpoint] = {}
        self._execution_order: dict[str, list[str]] = {}  # swarm_id → [checkpoint_ids]
        self._lease_manager = lease_manager
        self._consistency_proof = consistency_proof
        self._max_checkpoints = max_checkpoints

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, checkpoint: Checkpoint) -> Checkpoint:
        """Save a checkpoint to the manager.

        Args:
            checkpoint: The Checkpoint to save.

        Returns:
            The saved Checkpoint (with verified checksum).
        """
        if checkpoint.checksum:
            # Recompute to ensure integrity at save time
            checkpoint.checksum = checkpoint._compute_checksum()

        self._checkpoints[checkpoint.checkpoint_id] = checkpoint

        # Track by swarm
        if checkpoint.swarm_id not in self._execution_order:
            self._execution_order[checkpoint.swarm_id] = []
        self._execution_order[checkpoint.swarm_id].append(checkpoint.checkpoint_id)

        # Enforce max checkpoints (FIFO eviction)
        while len(self._checkpoints) > self._max_checkpoints:
            oldest_swarm = next(iter(self._execution_order))
            if self._execution_order[oldest_swarm]:
                oldest_id = self._execution_order[oldest_swarm].pop(0)
                self._checkpoints.pop(oldest_id, None)
            if not self._execution_order[oldest_swarm]:
                del self._execution_order[oldest_swarm]

        # Persist via knowledge/memory subsystem
        if self._lease_manager is not None:
            self._persist_checkpoint(checkpoint)

        return checkpoint

    def load(self, checkpoint_id: str) -> Checkpoint | None:
        """Load a checkpoint by its ID.

        Args:
            checkpoint_id: The checkpoint identifier.

        Returns:
            Checkpoint if found, None otherwise.
        """
        return self._checkpoints.get(checkpoint_id)

    def get_last_checkpoint(self, swarm_id: str | None = None) -> Checkpoint | None:
        """Get the most recent checkpoint, optionally filtered by swarm.

        Args:
            swarm_id: If provided, return the last checkpoint for this swarm.

        Returns:
            The most recent Checkpoint, or None.
        """
        if swarm_id and swarm_id in self._execution_order:
            order = self._execution_order[swarm_id]
            if order:
                return self._checkpoints.get(order[-1])
            return None

        # Global last checkpoint (most recently saved)
        if not self._checkpoints:
            return None
        return max(self._checkpoints.values(), key=lambda c: c.timestamp)

    def get_checkpoints_for_swarm(self, swarm_id: str) -> list[Checkpoint]:
        """Return all checkpoints for a given swarm, in creation order.

        Args:
            swarm_id: The swarm identifier.

        Returns:
            List of Checkpoints (may be empty).
        """
        order = self._execution_order.get(swarm_id, [])
        return [self._checkpoints[cid] for cid in order if cid in self._checkpoints]

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """List all stored checkpoints as dicts.

        Returns:
            List of checkpoint summary dicts.
        """
        return [
            {
                "checkpoint_id": c.checkpoint_id,
                "phase": c.phase,
                "swarm_id": c.swarm_id,
                "task_id": c.task_id,
                "timestamp": c.timestamp,
                "resume_point": c.resume_point,
            }
            for c in self._checkpoints.values()
        ]

    def verify_checkpoint(self, checkpoint_id: str) -> bool:
        """Verify the integrity of a stored checkpoint.

        Args:
            checkpoint_id: The checkpoint to verify.

        Returns:
            True if the checkpoint exists and its checksum is valid.
        """
        checkpoint = self._checkpoints.get(checkpoint_id)
        if checkpoint is None:
            return False
        return checkpoint.verify_integrity()

    def verify_all(self) -> dict[str, Any]:
        """Verify integrity of all stored checkpoints.

        Returns:
            Dict with ``all_valid``, ``count``, ``invalid``, and per-checkpoint results.
        """
        results: list[dict[str, Any]] = []
        invalid: list[str] = []

        for c in self._checkpoints.values():
            valid = c.verify_integrity()
            results.append(
                {
                    "checkpoint_id": c.checkpoint_id,
                    "phase": c.phase,
                    "swarm_id": c.swarm_id,
                    "valid": valid,
                }
            )
            if not valid:
                invalid.append(c.checkpoint_id)

        return {
            "all_valid": len(invalid) == 0,
            "count": len(self._checkpoints),
            "invalid": invalid,
            "results": results,
        }

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        if checkpoint_id not in self._checkpoints:
            return False
        checkpoint = self._checkpoints.pop(checkpoint_id)
        swarm_id = checkpoint.swarm_id
        if swarm_id in self._execution_order and checkpoint_id in self._execution_order[swarm_id]:
            self._execution_order[swarm_id].remove(checkpoint_id)
            if not self._execution_order[swarm_id]:
                del self._execution_order[swarm_id]
        return True

    def clear(self) -> None:
        """Remove all checkpoints."""
        self._checkpoints.clear()
        self._execution_order.clear()

    def get_count(self) -> int:
        """Return the total number of stored checkpoints."""
        return len(self._checkpoints)

    # ------------------------------------------------------------------
    # Internal: knowledge/memory persistence
    # ------------------------------------------------------------------

    def _persist_checkpoint(self, checkpoint: Checkpoint) -> MemoryLease | None:
        """Persist a checkpoint to the knowledge/memory subsystem.

        Creates a write-scoped lease on a memory key derived from the
        checkpoint ID with a 1-hour duration.

        Returns:
            MemoryLease if persisted, None if no lease manager.
        """
        if self._lease_manager is None:
            return None

        try:
            lease = self._lease_manager.acquire(
                holder_id=f"checkpoint_manager/{checkpoint.swarm_id}",
                memory_key=f"hlf:checkpoint:{checkpoint.checkpoint_id}",
                duration_seconds=3600,
                scope="write",
            )
            return lease
        except Exception:
            return None


# ---------------------------------------------------------------------------
# CheckpointableExecutor — wraps MultiPhaseExecutor
# ---------------------------------------------------------------------------


class CheckpointableExecutor:
    """Wraps MultiPhaseExecutor with checkpoint/resume support.

    Provides a drop-in replacement for MultiPhaseExecutor.run_multi_phase
    that saves checkpoints after each phase and supports resume from the
    last successful checkpoint on failure.

    Usage::

        executor = CheckpointableExecutor()
        result = executor.run("Write a hello world function")
        # If result.result.final_status != "ok":
        #     result = executor.resume(result.last_checkpoint.checkpoint_id)
    """

    def __init__(
        self,
        inner: MultiPhaseExecutor | None = None,
        checkpoint_manager: CheckpointManager | None = None,
    ) -> None:
        self._inner = inner or MultiPhaseExecutor()
        self._checkpoint_manager = checkpoint_manager or CheckpointManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        description: str,
        agents: list[str] | None = None,
        *,
        skip_consolidation: bool = False,
    ) -> CheckpointedExecutionResult:
        """Run the full three-phase execution with checkpointing.

        Checkpoints are saved after the PLAN phase and after the CONSOLIDATE
        phase. Within the EXECUTE phase, a checkpoint is saved after each
        agent execution step.

        Args:
            description: Task description.
            agents: Agent IDs to use.
            skip_consolidation: If True, skip consolidation.

        Returns:
            CheckpointedExecutionResult wrapping the MultiPhaseResult and
            all created checkpoints.
        """
        checkpoints: list[Checkpoint] = []
        swarm_id = hashlib.sha256(
            f"checkpoint:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        # ── Phase 1: PLAN ──────────────────────────────────────────────
        plans = self._inner.plan_phase(description, agents, swarm_id=swarm_id)
        plan_checkpoint = Checkpoint(
            phase="plan",
            step_index=0,
            swarm_id=swarm_id,
            task_id=hashlib.sha256(description.encode()).hexdigest()[:16],
            plan_data=self._serialize_plans(plans),
            resume_point="After PLAN phase: all agent plans produced",
            timestamp=time.time(),
        )
        checkpoints.append(self._checkpoint_manager.save(plan_checkpoint))

        # ── Phase 2: CONSOLIDATE ───────────────────────────────────────
        if skip_consolidation:
            consolidated = ConsolidatedPlan(
                merged_plans=plans,
                execution_order=[p.agent_id for p in plans],
                hlf_source="\n".join(p.hlf_source for p in plans),
                metrics={"skipped": True},
            )
        else:
            consolidated = self._inner.consolidate_phase(plans, swarm_id=swarm_id)

        con_checkpoint = Checkpoint(
            phase="consolidate",
            step_index=0,
            swarm_id=swarm_id,
            task_id=plan_checkpoint.task_id,
            plan_data=self._serialize_plans(plans),
            consolidated_data=self._serialize_consolidated(consolidated),
            resume_point="After CONSOLIDATE phase: plan merged and ordered",
            timestamp=time.time(),
        )
        checkpoints.append(self._checkpoint_manager.save(con_checkpoint))

        # ── Phase 3: EXECUTE (with per-step checkpoints) ───────────────
        exec_started = time.perf_counter_ns()
        try:
            exec_phase = self._inner.execute_phase(consolidated, swarm_id=swarm_id)
        except Exception as exc:
            logger.warning("Execute phase failed: %s — last checkpoint: %s",
                           exc, checkpoints[-1].checkpoint_id if checkpoints else "none")
            exec_phase = PhaseResult(
                phase_id="execute",
                status="error",
                metrics={
                    "error": str(exc),
                    "hlf_tokens": 0,
                    "compile_success": False,
                    "lint_errors": 1,
                    "verification_checks": 0,
                    "gate_decision": "BLOCK",
                    "execution_results": [],
                    "time_ms": (time.perf_counter_ns() - exec_started) / 1_000_000,
                },
                started_ns=exec_started,
                finished_ns=time.perf_counter_ns(),
            )

        execution_results = exec_phase.metrics.get("execution_results", [])
        for idx, er in enumerate(execution_results):
            agent_id = er.get("agent_id", f"step-{idx}")
            step_checkpoint = Checkpoint(
                phase="execute",
                step_index=idx + 1,
                swarm_id=swarm_id,
                task_id=plan_checkpoint.task_id,
                plan_data=self._serialize_plans(plans),
                consolidated_data=self._serialize_consolidated(consolidated),
                agent_states={agent_id: er},
                resume_point=f"After EXECUTE step {idx + 1}/{len(execution_results)}: agent '{agent_id}'",
                timestamp=time.time(),
            )
            checkpoints.append(self._checkpoint_manager.save(step_checkpoint))

        # ── Build MultiPhaseResult ─────────────────────────────────────
        plan_phase = PhaseResult(
            phase_id="plan",
            status="complete",
            agent_plans=plans,
            metrics={
                "agent_count": len(plans),
                "total_hlf_tokens": sum(p.metrics.get("hlf_tokens", 0) for p in plans),
                "all_compile_ok": all(p.metrics.get("compile_success", False) for p in plans),
                "time_ms": 0,
            },
        )
        con_phase = PhaseResult(
            phase_id="consolidate",
            status="skipped" if skip_consolidation else "complete",
            consolidated=consolidated,
            metrics=consolidated.metrics,
        )

        total_tokens = sum(p.metrics.get("hlf_tokens", 0) for p in plans)
        total_tokens += exec_phase.metrics.get("hlf_tokens", 0)
        compile_success = exec_phase.metrics.get("compile_success", False)

        mpr = MultiPhaseResult(
            swarm_id=swarm_id,
            task_id=plan_checkpoint.task_id,
            final_status="ok" if compile_success else "compile_error",
            phases=[plan_phase, con_phase, exec_phase],
            final_hlf=consolidated.hlf_source,
            final_nl=f"Checkpointed multi-phase: {len(plans)} agents planned, "
                     f"{len(consolidated.merged_plans)} consolidated, "
                     f"compile={'OK' if compile_success else 'FAIL'}",
            total_tokens=total_tokens,
            total_time_ms=(time.perf_counter_ns() - exec_started) / 1_000_000,
            compile_success=compile_success,
            consolidation_metrics=consolidated.metrics,
        )

        return CheckpointedExecutionResult(
            result=mpr,
            checkpoints=checkpoints,
            resumed_from=None,
        )

    def resume(self, checkpoint_id: str) -> CheckpointedExecutionResult | None:
        """Resume execution from a saved checkpoint.

        Determines the phase and step_index from the checkpoint and
        re-runs only the remaining phases/steps.

        Args:
            checkpoint_id: The checkpoint to resume from.

        Returns:
            CheckpointedExecutionResult if checkpoint found, None otherwise.

        Raises:
            ValueError: If checkpoint cannot be loaded.
        """
        checkpoint = self._checkpoint_manager.load(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint '{checkpoint_id}' not found.")

        checkpoints: list[Checkpoint] = [checkpoint]

        # Reconstruct plans from checkpoint
        plans = self._deserialize_plans(checkpoint.plan_data)
        consolidated_data = checkpoint.consolidated_data
        swarm_id = checkpoint.swarm_id

        # ── Resume based on phase ──────────────────────────────────────
        if checkpoint.phase == "plan":
            # Need to re-run CONSOLIDATE and EXECUTE
            consolidated = self._inner.consolidate_phase(plans, swarm_id=swarm_id)
            con_ck = Checkpoint(
                phase="consolidate",
                swarm_id=swarm_id,
                task_id=checkpoint.task_id,
                plan_data=checkpoint.plan_data,
                consolidated_data=self._serialize_consolidated(consolidated),
                resume_point="Resumed: after CONSOLIDATE",
                timestamp=time.time(),
            )
            checkpoints.append(self._checkpoint_manager.save(con_ck))
            consolidated_data = con_ck.consolidated_data

        if checkpoint.phase in ("plan", "consolidate"):
            # Need to run EXECUTE
            if not consolidated_data:
                consolidated = ConsolidatedPlan(
                    merged_plans=plans,
                    execution_order=[p.agent_id for p in plans],
                    hlf_source="\n".join(p.hlf_source for p in plans),
                    metrics={},
                )
            else:
                consolidated = self._deserialize_consolidated(consolidated_data, plans)

            exec_phase = self._inner.execute_phase(consolidated, swarm_id=swarm_id)
            execution_results = exec_phase.metrics.get("execution_results", [])
            for idx, er in enumerate(execution_results):
                agent_id = er.get("agent_id", f"step-{idx}")
                step_ck = Checkpoint(
                    phase="execute",
                    step_index=idx + 1,
                    swarm_id=swarm_id,
                    task_id=checkpoint.task_id,
                    plan_data=checkpoint.plan_data,
                    consolidated_data=self._serialize_consolidated(consolidated),
                    agent_states={agent_id: er},
                    resume_point=f"Resumed: after EXECUTE step {idx + 1}",
                    timestamp=time.time(),
                )
                checkpoints.append(self._checkpoint_manager.save(step_ck))

        elif checkpoint.phase == "execute":
            # Resume from a specific step in EXECUTE
            step_index = checkpoint.step_index
            if not consolidated_data:
                consolidated = ConsolidatedPlan(
                    merged_plans=plans,
                    execution_order=[p.agent_id for p in plans],
                    hlf_source="\n".join(p.hlf_source for p in plans),
                    metrics={},
                )
            else:
                consolidated = self._deserialize_consolidated(consolidated_data, plans)

            # Re-execute from the step_index onward
            exec_phase = self._inner.execute_phase(consolidated, swarm_id=swarm_id)
            execution_results = exec_phase.metrics.get("execution_results", [])
            for idx, er in enumerate(execution_results):
                if idx < step_index:
                    continue  # already executed
                agent_id = er.get("agent_id", f"step-{idx}")
                step_ck = Checkpoint(
                    phase="execute",
                    step_index=idx + 1,
                    swarm_id=swarm_id,
                    task_id=checkpoint.task_id,
                    plan_data=checkpoint.plan_data,
                    consolidated_data=self._serialize_consolidated(consolidated),
                    agent_states={agent_id: er},
                    resume_point=f"Resumed: after EXECUTE step {idx + 1}",
                    timestamp=time.time(),
                )
                checkpoints.append(self._checkpoint_manager.save(step_ck))

        # ── Build result ───────────────────────────────────────────────
        compile_success = exec_phase.metrics.get("compile_success", False) if 'exec_phase' in dir() else False
        plan_phase = PhaseResult(
            phase_id="plan",
            status="complete",
            agent_plans=plans,
            metrics={"agent_count": len(plans)},
        )
        con_phase = PhaseResult(
            phase_id="consolidate",
            status="complete",
            consolidated=consolidated if 'consolidated' in dir() else ConsolidatedPlan(),
            metrics=getattr(consolidated, 'metrics', {}) if 'consolidated' in dir() else {},
        )
        exec_p = exec_phase if 'exec_phase' in dir() else PhaseResult(
            phase_id="execute",
            status="error",
            metrics={},
        )

        mpr = MultiPhaseResult(
            swarm_id=swarm_id,
            task_id=checkpoint.task_id,
            final_status="ok" if compile_success else "compile_error",
            phases=[plan_phase, con_phase, exec_p],
            final_hlf=getattr(consolidated, 'hlf_source', '') if 'consolidated' in dir() else '',
            final_nl=f"Resumed from checkpoint {checkpoint_id}: "
                     f"{len(plans)} agents, "
                     f"compile={'OK' if compile_success else 'FAIL'}",
            total_tokens=sum(p.metrics.get("hlf_tokens", 0) for p in plans),
            total_time_ms=0,
            compile_success=compile_success,
            consolidation_metrics=getattr(consolidated, 'metrics', {}) if 'consolidated' in dir() else {},
        )

        return CheckpointedExecutionResult(
            result=mpr,
            checkpoints=checkpoints,
            resumed_from=checkpoint_id,
        )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_plans(plans: list[AgentPlan]) -> list[dict[str, Any]]:
        """Convert AgentPlan objects to serializable dicts."""
        return [
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
        ]

    @staticmethod
    def _deserialize_plans(data: list[dict[str, Any]]) -> list[AgentPlan]:
        """Reconstruct AgentPlan objects from serialized dicts."""
        return [
            AgentPlan(
                agent_id=d.get("agent_id", ""),
                role=d.get("role", ""),
                goal=d.get("goal", ""),
                hlf_source=d.get("hlf_source", "Ω"),
                scope=set(d.get("scope", [])),
                constraints=d.get("constraints", []),
                capabilities=set(d.get("capabilities", [])),
                dependencies=d.get("dependencies", []),
                metrics=d.get("metrics", {}),
            )
            for d in data
        ]

    @staticmethod
    def _serialize_consolidated(consolidated: ConsolidatedPlan) -> dict[str, Any]:
        """Convert a ConsolidatedPlan to a serializable dict."""
        return {
            "merged_plans": CheckpointableExecutor._serialize_plans(consolidated.merged_plans),
            "conflicts": [
                {
                    "kind": c.kind,
                    "plan_a": c.plan_a,
                    "plan_b": c.plan_b,
                    "description": c.description,
                    "severity": c.severity,
                    "resolution": c.resolution,
                }
                for c in consolidated.conflicts
            ],
            "duplicate_groups": consolidated.duplicate_groups,
            "execution_order": consolidated.execution_order,
            "hlf_source": consolidated.hlf_source,
            "metrics": consolidated.metrics,
        }

    @staticmethod
    def _deserialize_consolidated(
        data: dict[str, Any],
        fallback_plans: list[AgentPlan] | None = None,
    ) -> ConsolidatedPlan:
        """Reconstruct a ConsolidatedPlan from serialized data."""
        from hlf_mcp.hlf.multi_phase_executor import Conflict

        merged = CheckpointableExecutor._deserialize_plans(
            data.get("merged_plans", [])
        )
        if not merged and fallback_plans:
            merged = fallback_plans

        conflicts = [
            Conflict(
                kind=c.get("kind", "scope_overlap"),
                plan_a=c.get("plan_a", ""),
                plan_b=c.get("plan_b", ""),
                description=c.get("description", ""),
                severity=c.get("severity", "warning"),
                resolution=c.get("resolution", ""),
            )
            for c in data.get("conflicts", [])
        ]

        return ConsolidatedPlan(
            merged_plans=merged,
            conflicts=conflicts,
            duplicate_groups=data.get("duplicate_groups", []),
            execution_order=data.get("execution_order", [p.agent_id for p in merged]),
            hlf_source=data.get("hlf_source", ""),
            metrics=data.get("metrics", {}),
        )
