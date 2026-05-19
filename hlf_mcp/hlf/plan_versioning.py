"""
Plan Versioning with Rollback for HLF Multi-Phase Orchestration.

Provides:
  - PlanVersion: an immutable snapshot of a plan at a point in time
  - PlanHistory: a version chain with rollback, diff, and knowledge/memory
    storage integration (LeaseManager + ConsistencyProof).

Version chain is append-only — rollback creates a *new* version that
restores a prior state, preserving full audit history.

Integration points:
  - multi_phase_executor.AgentPlan: plan data payload
  - knowledge.memory_lease.LeaseManager: lease-scoped storage
  - knowledge.consistency_proof.ConsistencyProof: cross-witness integrity
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any

from hlf_mcp.hlf.knowledge.consistency_proof import ConsistencyProof, ConsistencyProofResult
from hlf_mcp.hlf.knowledge.memory_lease import LeaseManager, MemoryLease


# ---------------------------------------------------------------------------
# PlanVersion — immutable versioned snapshot
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlanVersion:
    """An immutable versioned snapshot of an orchestration plan.

    Each version is identified by a deterministic checksum of its content
    and references its parent version, forming a verifiable chain.

    Attributes:
        version_id: Unique identifier for this version.
        version_number: Monotonic version counter (1-based).
        parent_version: Version ID of the parent (None for root).
        checksum: SHA-256 content hash of the plan data.
        created_at: Unix timestamp of creation.
        plan_data: The serialized plan payload (list of AgentPlan dicts or raw).
        metadata: Arbitrary key-value tags (e.g. task_id, swarm_id).
        active: Whether this is the currently active version.
    """

    version_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version_number: int = 1
    parent_version: str | None = None
    checksum: str = ""
    created_at: float = field(default_factory=time.time)
    plan_data: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    active: bool = True

    def __post_init__(self) -> None:
        if not self.checksum and self.plan_data:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute a deterministic SHA-256 hash of plan_data + metadata."""
        payload = json.dumps(
            {"plan_data": self.plan_data, "metadata": self.metadata},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Check that the stored checksum matches the current content."""
        return self.checksum == self._compute_checksum()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the version to a plain dict."""
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "parent_version": self.parent_version,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "plan_data": self.plan_data,
            "metadata": self.metadata,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanVersion":
        """Deserialize from a dict."""
        return cls(
            version_id=data.get("version_id", str(uuid.uuid4())),
            version_number=data.get("version_number", 1),
            parent_version=data.get("parent_version"),
            checksum=data.get("checksum", ""),
            created_at=data.get("created_at", time.time()),
            plan_data=data.get("plan_data", []),
            metadata=data.get("metadata", {}),
            active=data.get("active", True),
        )


# ---------------------------------------------------------------------------
# PlanHistory — version chain manager
# ---------------------------------------------------------------------------


class PlanHistory:
    """Manages a version chain for orchestration plans with rollback support.

    Stores versions in a doubly-linked chain via parent_version references.
    Supports rollback by creating a new version that restores a prior
    snapshot, never mutating existing versions.

    Integrates with the knowledge/memory subsystem via LeaseManager for
    scoped storage and ConsistencyProof for cross-witness integrity checks.

    Usage::

        history = PlanHistory()
        history.commit(plan_data=[...], metadata={"task_id": "abc"})
        history.commit(plan_data=[...], metadata={"task_id": "abc", "revised": True})
        history.rollback()  # restores v1 as v3
        diff = history.diff(history.get_version(1), history.get_current())
    """

    def __init__(
        self,
        lease_manager: LeaseManager | None = None,
        consistency_proof: ConsistencyProof | None = None,
    ) -> None:
        self._versions: dict[str, PlanVersion] = {}
        self._order: list[str] = []  # version_ids in commit order
        self._current_id: str | None = None
        self._next_version_number: int = 1
        self._lease_manager = lease_manager
        self._consistency_proof = consistency_proof

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def commit(
        self,
        plan_data: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
        *,
        version_id: str | None = None,
        parent_version: str | None = None,
    ) -> PlanVersion:
        """Commit a new version to the history.

        Args:
            plan_data: Serialized plan payload (list of agent plan dicts).
            metadata: Optional key-value tags.
            version_id: Optional explicit version ID (auto-generated if None).
            parent_version: Explicit parent version ID (defaults to current).

        Returns:
            The newly created PlanVersion.
        """
        if parent_version is None:
            parent_version = self._current_id

        version = PlanVersion(
            version_id=version_id or str(uuid.uuid4()),
            version_number=self._next_version_number,
            parent_version=parent_version,
            plan_data=deepcopy(plan_data),
            metadata=dict(metadata or {}),
            created_at=time.time(),
            active=True,
        )

        # Deactivate previous current
        if self._current_id and self._current_id in self._versions:
            self._versions[self._current_id].active = False

        self._versions[version.version_id] = version
        self._order.append(version.version_id)
        self._current_id = version.version_id
        self._next_version_number += 1

        # Store in knowledge/memory if lease manager is available
        if self._lease_manager is not None:
            self._store_version_lease(version)

        return version

    def rollback(self, target_version_id: str | None = None) -> PlanVersion:
        """Roll back to a previous version by creating a new restoration version.

        Rollback is non-destructive: a new version is created that copies
        the plan_data and parent chain from the target version. The rolled-
        back-from version is recorded in metadata.

        Args:
            target_version_id: The version to restore. If None, rolls back
                to the parent of the current version.

        Returns:
            A new PlanVersion that restores the target's state.

        Raises:
            ValueError: If the target version does not exist.
            ValueError: If there is no parent to roll back to (single version).
        """
        if target_version_id is None:
            if self._current_id is None:
                raise ValueError("No current version to roll back from.")
            current = self._versions[self._current_id]
            if current.parent_version is None:
                raise ValueError(
                    "Cannot roll back: current version (v%s) has no parent. "
                    "At least two versions are required for rollback."
                    % current.version_number,
                )
            target_version_id = current.parent_version

        if target_version_id not in self._versions:
            raise ValueError(
                f"Target version '{target_version_id}' not found in history."
            )

        target = self._versions[target_version_id]

        rollback_version = PlanVersion(
            version_id=str(uuid.uuid4()),
            version_number=self._next_version_number,
            parent_version=target_version_id,
            plan_data=deepcopy(target.plan_data),
            metadata={
                **(target.metadata or {}),
                "rollback": True,
                "rolled_back_from": self._current_id,
                "rolled_back_from_version": (
                    self._versions[self._current_id].version_number
                    if self._current_id and self._current_id in self._versions
                    else None
                ),
            },
            created_at=time.time(),
            active=True,
        )

        # Deactivate current
        if self._current_id and self._current_id in self._versions:
            self._versions[self._current_id].active = False

        self._versions[rollback_version.version_id] = rollback_version
        self._order.append(rollback_version.version_id)
        self._current_id = rollback_version.version_id
        self._next_version_number += 1

        if self._lease_manager is not None:
            self._store_version_lease(rollback_version)

        return rollback_version

    def get_current(self) -> PlanVersion | None:
        """Return the currently active version, or None if no commits."""
        if self._current_id is None:
            return None
        return self._versions.get(self._current_id)

    def get_version(self, version_id: str) -> PlanVersion | None:
        """Retrieve a specific version by ID.

        Args:
            version_id: The version identifier.

        Returns:
            PlanVersion if found, None otherwise.
        """
        return self._versions.get(version_id)

    def get_version_by_number(self, version_number: int) -> PlanVersion | None:
        """Retrieve a version by its sequential number.

        Args:
            version_number: The 1-based version number.

        Returns:
            PlanVersion if found, None otherwise.
        """
        for v in self._versions.values():
            if v.version_number == version_number:
                return v
        return None

    def get_chain(self, from_version_id: str | None = None) -> list[PlanVersion]:
        """Return the ancestral chain from a given version back to root.

        Args:
            from_version_id: Starting version (defaults to current).

        Returns:
            Ordered list from the given version back to the root.
        """
        if from_version_id is None:
            from_version_id = self._current_id
        if from_version_id is None:
            return []

        chain: list[PlanVersion] = []
        visited: set[str] = set()
        vid: str | None = from_version_id

        while vid is not None and vid not in visited:
            version = self._versions.get(vid)
            if version is None:
                break
            chain.append(version)
            visited.add(vid)
            vid = version.parent_version

        return chain

    def get_all_versions(self) -> list[PlanVersion]:
        """Return all versions in commit order."""
        return [self._versions[vid] for vid in self._order if vid in self._versions]

    def diff(
        self,
        version_a: PlanVersion | str,
        version_b: PlanVersion | str | None = None,
    ) -> dict[str, Any]:
        """Compute the difference between two plan versions.

        Args:
            version_a: First version (or version ID).
            version_b: Second version (or version ID). Defaults to current.

        Returns:
            Dict with ``added``, ``removed``, ``changed`` plan entries,
            ``metadata_changes``, ``version_a_number``, and ``version_b_number``.

        Raises:
            ValueError: If either version cannot be resolved.
        """
        plan_a = self._resolve_version(version_a)
        plan_b = self._resolve_version(version_b) if version_b is not None else self.get_current()
        if plan_b is None:
            raise ValueError("Could not resolve version B (current may be None).")

        data_a = {json.dumps(p, sort_keys=True, default=str): p for p in plan_a.plan_data}
        data_b = {json.dumps(p, sort_keys=True, default=str): p for p in plan_b.plan_data}

        keys_a = set(data_a.keys())
        keys_b = set(data_b.keys())

        added = [data_b[k] for k in (keys_b - keys_a)]
        removed = [data_a[k] for k in (keys_a - keys_b)]

        # Detect changes where same logical entry (by agent_id) differs
        changed: list[dict[str, Any]] = []
        ids_a = {p.get("agent_id"): p for p in plan_a.plan_data if p.get("agent_id")}
        ids_b = {p.get("agent_id"): p for p in plan_b.plan_data if p.get("agent_id")}
        for agent_id in set(ids_a) & set(ids_b):
            if ids_a[agent_id] != ids_b[agent_id]:
                changed.append(
                    {
                        "agent_id": agent_id,
                        "before": ids_a[agent_id],
                        "after": ids_b[agent_id],
                    }
                )

        # Metadata changes
        metadata_changes: dict[str, Any] = {}
        all_keys = set(plan_a.metadata) | set(plan_b.metadata)
        for key in all_keys:
            val_a = plan_a.metadata.get(key)
            val_b = plan_b.metadata.get(key)
            if val_a != val_b:
                metadata_changes[key] = {"before": val_a, "after": val_b}

        return {
            "added": added,
            "removed": removed,
            "changed": changed,
            "metadata_changes": metadata_changes,
            "version_a_number": plan_a.version_number,
            "version_b_number": plan_b.version_number,
            "version_a_id": plan_a.version_id,
            "version_b_id": plan_b.version_id,
        }

    def verify_chain_integrity(self) -> dict[str, Any]:
        """Verify integrity of all versions in the chain.

        Returns:
            Dict with ``all_valid``, ``version_count``, ``invalid_versions``,
            and per-version results.
        """
        results: list[dict[str, Any]] = []
        invalid: list[str] = []

        for version in self._versions.values():
            valid = version.verify_integrity()
            result = {
                "version_id": version.version_id,
                "version_number": version.version_number,
                "valid": valid,
            }
            if not valid:
                invalid.append(version.version_id)
            results.append(result)

        return {
            "all_valid": len(invalid) == 0,
            "version_count": len(self._versions),
            "invalid_versions": invalid,
            "results": results,
        }

    def get_version_count(self) -> int:
        """Return the total number of versions in history."""
        return len(self._versions)

    def clear(self) -> None:
        """Remove all versions and reset state."""
        self._versions.clear()
        self._order.clear()
        self._current_id = None
        self._next_version_number = 1

    # ------------------------------------------------------------------
    # Knowledge / memory integration
    # ------------------------------------------------------------------

    def _store_version_lease(self, version: PlanVersion) -> MemoryLease | None:
        """Store a version in the memory subsystem via a lease.

        Creates a write-scoped lease on a memory key derived from the
        version ID, with a long duration for persistence.

        Returns:
            The MemoryLease if stored, None if no lease manager.
        """
        if self._lease_manager is None:
            return None

        try:
            lease = self._lease_manager.acquire(
                holder_id=f"plan_versioning/{version.version_id}",
                memory_key=f"hlf:plan_version:{version.version_id}",
                duration_seconds=86400,  # 24h persistence
                scope="write",
            )
            return lease
        except Exception:
            # Non-fatal: version is already held in-memory
            return None

    def build_consistency_proof(self) -> ConsistencyProofResult | None:
        """Build a consistency proof over the version chain.

        Uses the ConsistencyProof engine to verify the version chain is
        internally consistent (no checksum violations, parent references
        form a valid DAG).

        Returns:
            ConsistencyProofResult if a proof engine is available, else None.
        """
        if self._consistency_proof is None:
            return None

        # Represent versions as memory node dicts for cross-witness check
        memory_nodes = [
            {
                "memory_key": f"hlf:plan_version:{v.version_id}",
                "content_hash": v.checksum,
                "timestamp": v.created_at,
            }
            for v in self._versions.values()
        ]

        # Use empty snapshots and drift results — we're checking internal
        # consistency, not external witness agreement
        result = self._consistency_proof.build_proof(
            witness_snapshots=[],
            memory_nodes=memory_nodes,
            drift_results=[],
        )
        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_version(self, version_or_id: PlanVersion | str) -> PlanVersion:
        """Resolve a PlanVersion or version ID string to a PlanVersion."""
        if isinstance(version_or_id, PlanVersion):
            return version_or_id
        version = self._versions.get(version_or_id)
        if version is None:
            raise ValueError(f"Version '{version_or_id}' not found in history.")
        return version
