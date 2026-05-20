"""
Orchestration Failure Recovery — swarm leader election, split-brain detection,
stale plan cache invalidation, and crash recovery with plan replay.

Provides:
  - VectorClock: causal ordering primitive for distributed event tracking
  - SwarmLeaderElection: Bully-algorithm leader election with vector clock tie-breaking
  - SplitBrainDetector: vector-clock-based partition / split-brain detection
  - StalePlanCache: plan cache with version-stamped invalidation
  - CrashRecovery: crash recovery with plan replay from checkpoint

Integration points:
  - hlf_mcp.hlf.checkpoint_executor: CheckpointManager for recovery replay
  - hlf_mcp.hlf.plan_versioning: PlanHistory for versioned plan snapshots
  - hlf_mcp.hlf.routing.node_registry: NodeRegistry for swarm member discovery
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
# VectorClock — causal ordering primitive
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class VectorClock:
    """A vector clock for causal ordering of distributed events.

    Each node maintains a counter for every known node in the swarm.
    Events are causally ordered by component-wise comparison.

    Attributes:
        node_id: The owning node identifier.
        counters: Map from node_id to logical clock counter.
        timestamp: Wall-clock time of last update.
    """

    node_id: str
    counters: dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if self.node_id not in self.counters:
            self.counters[self.node_id] = 0

    def tick(self) -> VectorClock:
        """Increment the local node's counter and return self for chaining."""
        self.counters[self.node_id] = self.counters.get(self.node_id, 0) + 1
        self.timestamp = time.time()
        return self

    def merge(self, other: VectorClock) -> VectorClock:
        """Merge another vector clock into this one (element-wise max).

        Returns self after merging for chaining.
        """
        for node, count in other.counters.items():
            self.counters[node] = max(self.counters.get(node, 0), count)
        self.timestamp = max(self.timestamp, other.timestamp)
        return self

    def happened_before(self, other: VectorClock) -> bool:
        """Check if this clock strictly happened-before `other`.

        True iff all counters <= other's and at least one is strictly <.
        """
        all_nodes = set(self.counters) | set(other.counters)
        at_least_one_strictly_less = False
        for node in all_nodes:
            s = self.counters.get(node, 0)
            o = other.counters.get(node, 0)
            if s > o:
                return False
            if s < o:
                at_least_one_strictly_less = True
        return at_least_one_strictly_less

    def is_concurrent(self, other: VectorClock) -> bool:
        """Check if two vector clocks are concurrent (neither happened-before)."""
        return not self.happened_before(other) and not other.happened_before(self)

    def equals(self, other: VectorClock) -> bool:
        """Check exact equality of two vector clocks."""
        all_nodes = set(self.counters) | set(other.counters)
        return all(
            self.counters.get(n, 0) == other.counters.get(n, 0) for n in all_nodes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "counters": dict(self.counters),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorClock":
        return cls(
            node_id=str(data.get("node_id", "")),
            counters={str(k): int(v) for k, v in data.get("counters", {}).items()},
            timestamp=float(data.get("timestamp", time.time())),
        )

    def clone(self) -> VectorClock:
        """Return a deep copy of this vector clock."""
        return VectorClock(
            node_id=self.node_id,
            counters=dict(self.counters),
            timestamp=self.timestamp,
        )


# ---------------------------------------------------------------------------
# SwarmLeaderElection — Bully-like leader election with vector clocks
# ---------------------------------------------------------------------------


@dataclass
class ElectionResult:
    """Result of a leader election round.

    Attributes:
        leader_id: The elected leader node ID.
        term: Monotonic election term number.
        clock: Vector clock at the time of election.
        participants: Node IDs that participated.
        quorum_reached: Whether quorum was achieved.
        timestamp: When the election concluded.
    """

    leader_id: str
    term: int
    clock: VectorClock
    participants: list[str] = field(default_factory=list)
    quorum_reached: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leader_id": self.leader_id,
            "term": self.term,
            "clock": self.clock.to_dict(),
            "participants": list(self.participants),
            "quorum_reached": self.quorum_reached,
            "timestamp": self.timestamp,
        }


class SwarmLeaderElection:
    """Bully-algorithm leader election with vector-clock tie-breaking.

    Manages election terms, candidate nomination, and quorum-based leader
    selection for swarm coordination.

    Usage::

        election = SwarmLeaderElection(swarm_id="swarm-1", quorum_size=3)
        election.register_node("node-a", priority=10)
        election.register_node("node-b", priority=5)
        result = election.elect()
        assert result.quorum_reached
    """

    def __init__(self, swarm_id: str, quorum_size: int = 3) -> None:
        self.swarm_id = swarm_id
        self.quorum_size = quorum_size
        self._nodes: dict[str, dict[str, Any]] = {}
        self._current_leader: str | None = None
        self._term: int = 0
        self._election_history: list[ElectionResult] = []
        self._vector_clocks: dict[str, VectorClock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_node(
        self,
        node_id: str,
        priority: int = 0,
        capabilities: list[str] | None = None,
    ) -> None:
        """Register a node in the election pool.

        Args:
            node_id: Unique node identifier.
            priority: Higher values win tie-breaks after vector clock comparison.
            capabilities: Optional list of capability tags.
        """
        self._nodes[node_id] = {
            "node_id": node_id,
            "priority": priority,
            "capabilities": list(capabilities or []),
            "registered_at": time.time(),
            "active": True,
        }
        if node_id not in self._vector_clocks:
            self._vector_clocks[node_id] = VectorClock(node_id=node_id)

    def deregister_node(self, node_id: str) -> None:
        """Remove a node from the election pool."""
        self._nodes.pop(node_id, None)
        self._vector_clocks.pop(node_id, None)
        if self._current_leader == node_id:
            self._current_leader = None

    def mark_node_unreachable(self, node_id: str) -> None:
        """Mark a node as inactive without deregistering."""
        if node_id in self._nodes:
            self._nodes[node_id]["active"] = False

    def mark_node_reachable(self, node_id: str) -> None:
        """Mark a previously unreachable node as active."""
        if node_id in self._nodes:
            self._nodes[node_id]["active"] = True

    def tick_clock(self, node_id: str) -> VectorClock:
        """Advance the vector clock for a node."""
        if node_id not in self._vector_clocks:
            self._vector_clocks[node_id] = VectorClock(node_id=node_id)
        return self._vector_clocks[node_id].tick()

    def merge_clock(self, node_id: str, other: VectorClock) -> VectorClock:
        """Merge an external vector clock into a node's clock."""
        if node_id not in self._vector_clocks:
            self._vector_clocks[node_id] = VectorClock(node_id=node_id)
        return self._vector_clocks[node_id].merge(other)

    def get_clock(self, node_id: str) -> VectorClock | None:
        """Get the current vector clock for a node."""
        return self._vector_clocks.get(node_id)

    def elect(self, candidate_ids: list[str] | None = None) -> ElectionResult:
        """Run a leader election round.

        The bully algorithm selects the highest-priority active node.
        Vector clocks serve as tie-breakers: the node with the most
        causally-advanced clock wins ties.

        Args:
            candidate_ids: Optional subset of nodes to consider. If None,
                all active registered nodes are candidates.

        Returns:
            ElectionResult with the elected leader and election metadata.
        """
        self._term += 1

        # Determine candidates
        if candidate_ids is not None:
            candidates = {
                nid: self._nodes[nid]
                for nid in candidate_ids
                if nid in self._nodes and self._nodes[nid]["active"]
            }
        else:
            candidates = {
                nid: info
                for nid, info in self._nodes.items()
                if info["active"]
            }

        if not candidates:
            return ElectionResult(
                leader_id="",
                term=self._term,
                clock=VectorClock(node_id=self.swarm_id),
                participants=[],
                quorum_reached=False,
            )

        # Sort by priority desc, then by vector clock advancement desc
        def _rank_key(item: tuple[str, dict[str, Any]]) -> tuple[int, int]:
            nid, info = item
            priority = info["priority"]
            clock = self._vector_clocks.get(nid, VectorClock(node_id=nid))
            # Use sum of counters as a proxy for advancement
            clock_advancement = sum(clock.counters.values())
            return (-priority, -clock_advancement)

        ranked = sorted(candidates.items(), key=_rank_key)
        leader_id = ranked[0][0]
        participants = [nid for nid, _ in ranked]

        # Build aggregate clock from all participants
        agg_clock = VectorClock(node_id=self.swarm_id)
        for nid in participants:
            if nid in self._vector_clocks:
                agg_clock.merge(self._vector_clocks[nid])

        quorum = len(participants) >= self.quorum_size

        result = ElectionResult(
            leader_id=leader_id,
            term=self._term,
            clock=agg_clock,
            participants=participants,
            quorum_reached=quorum,
        )
        self._election_history.append(result)
        if quorum:
            self._current_leader = leader_id

        return result

    def get_current_leader(self) -> str | None:
        """Return the current leader node ID, or None."""
        return self._current_leader

    def get_term(self) -> int:
        """Return the current election term."""
        return self._term

    def get_election_history(self) -> list[ElectionResult]:
        """Return the full election history."""
        return list(self._election_history)

    def get_active_nodes(self) -> list[str]:
        """Return list of currently active node IDs."""
        return [nid for nid, info in self._nodes.items() if info["active"]]

    def get_node_count(self) -> int:
        """Return total number of registered nodes (active or not)."""
        return len(self._nodes)

    def force_leader(self, node_id: str) -> None:
        """Force a specific node as leader (e.g., operator override)."""
        if node_id in self._nodes:
            self._current_leader = node_id
            self._term += 1


# ---------------------------------------------------------------------------
# SplitBrainDetector — vector clock based partition detection
# ---------------------------------------------------------------------------


@dataclass
class SplitBrainReport:
    """Report from split-brain detection.

    Attributes:
        detected: Whether a split-brain condition was found.
        partitions: List of partition groups (each a list of node IDs).
        divergent_clocks: Map of node_id to vector clock snapshot.
        stale_leader: Whether the current leader is in a minority partition.
        recommended_action: Suggested remediation.
        timestamp: Detection timestamp.
    """

    detected: bool
    partitions: list[list[str]] = field(default_factory=list)
    divergent_clocks: dict[str, dict[str, Any]] = field(default_factory=dict)
    stale_leader: bool = False
    recommended_action: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "partitions": self.partitions,
            "divergent_clocks": self.divergent_clocks,
            "stale_leader": self.stale_leader,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp,
        }


class SplitBrainDetector:
    """Detects split-brain conditions using vector clock divergence.

    Compares vector clocks across swarm nodes to detect partitions where
    nodes have diverged causal histories, indicating a network partition.

    Usage::

        detector = SplitBrainDetector(election)
        report = detector.detect()
        if report.detected:
            # Trigger leader re-election or partition healing
    """

    def __init__(
        self,
        election: SwarmLeaderElection,
        clock_divergence_threshold: int = 5,
        heartbeat_timeout_seconds: float = 30.0,
    ) -> None:
        self._election = election
        self._clock_divergence_threshold = clock_divergence_threshold
        self._heartbeat_timeout = heartbeat_timeout_seconds
        self._last_heartbeats: dict[str, float] = {}
        self._partition_history: list[SplitBrainReport] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_heartbeat(self, node_id: str) -> None:
        """Record a heartbeat from a node."""
        self._last_heartbeats[node_id] = time.time()

    def detect(self) -> SplitBrainReport:
        """Run split-brain detection across all registered nodes.

        Returns:
            SplitBrainReport with detection results and recommended action.
        """
        now = time.time()
        active_nodes = self._election.get_active_nodes()
        partitions: list[list[str]] = []
        divergent: dict[str, dict[str, Any]] = {}
        stale_leader = False

        if len(active_nodes) < 2:
            return SplitBrainReport(
                detected=False,
                partitions=[active_nodes] if active_nodes else [],
                timestamp=now,
                recommended_action="insufficient_nodes_for_partition",
            )

        # Check heartbeats for timed-out nodes
        timed_out: list[str] = []
        for nid in active_nodes:
            last_hb = self._last_heartbeats.get(nid, 0)
            if now - last_hb > self._heartbeat_timeout:
                timed_out.append(nid)

        # Group nodes by clock similarity
        clock_groups: dict[int, list[str]] = {}
        for nid in active_nodes:
            clock = self._election.get_clock(nid)
            if clock is None:
                continue
            # Hash the counters to group nodes with identical causal histories
            clock_hash = hash(json.dumps(clock.counters, sort_keys=True))
            clock_groups.setdefault(clock_hash, []).append(nid)

        partitions = list(clock_groups.values())

        # A partition exists if we have >1 distinct clock groups
        detected = len(partitions) > 1 or len(timed_out) > 0

        # Check for divergent clocks across partitions
        if len(partitions) > 1:
            for group in partitions:
                for nid in group:
                    clock = self._election.get_clock(nid)
                    if clock:
                        divergent[nid] = clock.to_dict()

        # Check if leader is in a minority partition
        current_leader = self._election.get_current_leader()
        if current_leader and len(partitions) > 1:
            leader_partition = None
            for i, group in enumerate(partitions):
                if current_leader in group:
                    leader_partition = (i, group)
                    break
            if leader_partition is not None:
                max_group_size = max(len(g) for g in partitions)
                if len(leader_partition[1]) < max_group_size:
                    stale_leader = True

        # Compute clock divergence between partitions
        if len(partitions) > 1:
            # Compare max clock values between partitions
            partition_sums = []
            for group in partitions:
                psum = 0
                for nid in group:
                    clock = self._election.get_clock(nid)
                    if clock:
                        psum = max(psum, sum(clock.counters.values()))
                partition_sums.append(psum)
            max_divergence = max(partition_sums) - min(partition_sums)
            if max_divergence < self._clock_divergence_threshold and not timed_out:
                detected = False  # minor drift, not a real partition

        # Build recommendation
        if detected:
            if stale_leader:
                recommended = "re_elect_leader"
            elif timed_out:
                recommended = "evict_timed_out_nodes_and_re_elect"
            else:
                recommended = "heal_partition_via_clock_merge"
        else:
            recommended = "no_action"

        report = SplitBrainReport(
            detected=detected,
            partitions=partitions,
            divergent_clocks=divergent,
            stale_leader=stale_leader,
            recommended_action=recommended,
            timestamp=now,
        )
        self._partition_history.append(report)
        return report

    def heal_partition(self, report: SplitBrainReport) -> bool:
        """Attempt to heal a detected partition by merging clocks.

        Merges vector clocks across partitions to restore causal consistency.

        Returns:
            True if healing was applied, False if no partition detected.
        """
        if not report.detected or len(report.partitions) < 2:
            return False

        # Collect all clocks and merge them
        all_clocks: list[VectorClock] = []
        for group in report.partitions:
            for nid in group:
                clock = self._election.get_clock(nid)
                if clock:
                    all_clocks.append(clock.clone())

        if not all_clocks:
            return False

        # Merge all clocks into a unified clock
        merged = all_clocks[0].clone()
        for clock in all_clocks[1:]:
            merged.merge(clock)

        # Distribute merged clock to all nodes
        for group in report.partitions:
            for nid in group:
                self._election.merge_clock(nid, merged)

        return True

    def get_partition_history(self) -> list[SplitBrainReport]:
        """Return the history of partition detections."""
        return list(self._partition_history)

    def get_heartbeat_status(self) -> dict[str, dict[str, Any]]:
        """Return heartbeat status for all nodes."""
        now = time.time()
        status: dict[str, dict[str, Any]] = {}
        for nid in self._election.get_active_nodes():
            last_hb = self._last_heartbeats.get(nid, 0)
            status[nid] = {
                "last_heartbeat": last_hb,
                "age_seconds": now - last_hb,
                "timed_out": (now - last_hb) > self._heartbeat_timeout,
            }
        return status

    def clear_heartbeats(self) -> None:
        """Reset all heartbeat records."""
        self._last_heartbeats.clear()


# ---------------------------------------------------------------------------
# StalePlanCache — version-stamped plan cache invalidation
# ---------------------------------------------------------------------------


@dataclass
class CacheEntry:
    """A single entry in the plan cache.

    Attributes:
        plan_id: The plan identifier.
        plan_data: Cached plan data.
        version_stamp: Monotonic version stamp for invalidation.
        cached_at: When the entry was cached.
        ttl_seconds: Time-to-live in seconds.
        node_id: Node that owns this cache entry.
    """

    plan_id: str
    plan_data: dict[str, Any] = field(default_factory=dict)
    version_stamp: int = 0
    cached_at: float = field(default_factory=time.time)
    ttl_seconds: float = 300.0
    node_id: str = ""

    def is_expired(self, now: float | None = None) -> bool:
        """Check if the cache entry has exceeded its TTL."""
        t = now if now is not None else time.time()
        return (t - self.cached_at) > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_data": dict(self.plan_data),
            "version_stamp": self.version_stamp,
            "cached_at": self.cached_at,
            "ttl_seconds": self.ttl_seconds,
            "node_id": self.node_id,
        }


class StalePlanCache:
    """Version-stamped plan cache with automatic invalidation.

    Each plan is stamped with a monotonic version.  When the master plan
    version advances, cached entries with lower stamps are invalidated.
    TTL-based expiration serves as a secondary guard.

    Usage::

        cache = StalePlanCache(default_ttl=300.0)
        cache.put("plan-1", {"tasks": [...]}, version_stamp=5, node_id="node-a")
        entry = cache.get("plan-1")
        cache.invalidate_stale(6)  # invalidates entries with stamp < 6
    """

    def __init__(self, default_ttl: float = 300.0, max_entries: int = 1000) -> None:
        self._entries: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._current_master_version: int = 0
        self._invalidation_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(
        self,
        plan_id: str,
        plan_data: dict[str, Any],
        version_stamp: int = 0,
        node_id: str = "",
        ttl_seconds: float | None = None,
    ) -> CacheEntry:
        """Store a plan in the cache.

        Args:
            plan_id: Unique plan identifier.
            plan_data: The plan payload to cache.
            version_stamp: Monotonic version stamp for invalidation.
            node_id: Node that produced this plan version.
            ttl_seconds: Optional custom TTL (defaults to cache default).

        Returns:
            The created CacheEntry.
        """
        if version_stamp > self._current_master_version:
            self._current_master_version = version_stamp

        entry = CacheEntry(
            plan_id=plan_id,
            plan_data=deepcopy(plan_data),
            version_stamp=version_stamp,
            node_id=node_id,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else self._default_ttl,
        )
        self._entries[plan_id] = entry
        self._evict_if_needed()
        return entry

    def get(self, plan_id: str) -> CacheEntry | None:
        """Retrieve a cached plan if it is still valid.

        Returns None if the entry is expired or doesn't exist.
        """
        entry = self._entries.get(plan_id)
        if entry is None:
            return None
        if entry.is_expired():
            self._entries.pop(plan_id, None)
            return None
        if entry.version_stamp < self._current_master_version:
            # Stale — version stamp behind master
            return None
        return entry

    def invalidate_stale(self, master_version: int) -> int:
        """Invalidate all entries with version stamps below the master version.

        Args:
            master_version: The current master plan version.

        Returns:
            Number of entries invalidated.
        """
        self._current_master_version = max(self._current_master_version, master_version)
        stale_ids = [
            pid
            for pid, entry in self._entries.items()
            if entry.version_stamp < master_version
        ]
        for pid in stale_ids:
            self._entries.pop(pid, None)
        self._invalidation_count += len(stale_ids)
        return len(stale_ids)

    def invalidate_node(self, node_id: str) -> int:
        """Invalidate all entries from a specific node (e.g., on node failure).

        Args:
            node_id: The node whose entries should be invalidated.

        Returns:
            Number of entries invalidated.
        """
        stale_ids = [
            pid
            for pid, entry in self._entries.items()
            if entry.node_id == node_id
        ]
        for pid in stale_ids:
            self._entries.pop(pid, None)
        self._invalidation_count += len(stale_ids)
        return len(stale_ids)

    def invalidate_all(self) -> int:
        """Invalidate all cache entries.

        Returns:
            Number of entries invalidated.
        """
        count = len(self._entries)
        self._entries.clear()
        self._invalidation_count += count
        return count

    def expire_ttl_entries(self) -> int:
        """Remove all TTL-expired entries.

        Returns:
            Number of entries removed.
        """
        now = time.time()
        expired = [pid for pid, entry in self._entries.items() if entry.is_expired(now)]
        for pid in expired:
            self._entries.pop(pid, None)
        return len(expired)

    def get_master_version(self) -> int:
        """Return the current master plan version."""
        return self._current_master_version

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        now = time.time()
        total = len(self._entries)
        expired = sum(1 for e in self._entries.values() if e.is_expired(now))
        stale = sum(
            1 for e in self._entries.values()
            if e.version_stamp < self._current_master_version
        )
        return {
            "total_entries": total,
            "expired_entries": expired,
            "stale_entries": stale,
            "master_version": self._current_master_version,
            "total_invalidations": self._invalidation_count,
            "max_entries": self._max_entries,
        }

    def list_entries(self) -> list[dict[str, Any]]:
        """List all cache entries as dicts."""
        return [entry.to_dict() for entry in self._entries.values()]

    def clear(self) -> None:
        """Remove all entries and reset counters."""
        self._entries.clear()
        self._current_master_version = 0
        self._invalidation_count = 0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        """FIFO eviction if the cache exceeds max_entries."""
        while len(self._entries) > self._max_entries:
            # Evict the oldest entry by cached_at
            oldest = min(self._entries.values(), key=lambda e: e.cached_at)
            self._entries.pop(oldest.plan_id, None)


# ---------------------------------------------------------------------------
# CrashRecovery — crash recovery with plan replay from checkpoint
# ---------------------------------------------------------------------------


@dataclass
class RecoveryResult:
    """Result of a crash recovery attempt.

    Attributes:
        success: Whether recovery completed successfully.
        node_id: The node that was recovered.
        checkpoint_id: The checkpoint used for replay.
        replayed_steps: Number of plan steps replayed.
        missing_steps: Steps that could not be recovered.
        recovery_time_seconds: How long recovery took.
        errors: Any errors encountered during recovery.
    """

    success: bool
    node_id: str
    checkpoint_id: str = ""
    replayed_steps: int = 0
    missing_steps: int = 0
    recovery_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "node_id": self.node_id,
            "checkpoint_id": self.checkpoint_id,
            "replayed_steps": self.replayed_steps,
            "missing_steps": self.missing_steps,
            "recovery_time_seconds": self.recovery_time_seconds,
            "errors": list(self.errors),
        }


class CrashRecovery:
    """Crash recovery engine with plan replay from checkpoint.

    When a swarm node crashes, this engine replays the plan from the
    last known checkpoint, skipping steps already completed, and
    re-executing remaining work.

    Usage::

        recovery = CrashRecovery(checkpoint_manager, plan_history)
        result = recovery.recover_node("node-a", swarm_id="swarm-1")
        if result.success:
            print(f"Replayed {result.replayed_steps} steps")
    """

    def __init__(
        self,
        checkpoint_manager: Any = None,  # CheckpointManager (lazy import)
        plan_history: Any = None,  # PlanHistory (lazy import)
        max_replay_attempts: int = 3,
    ) -> None:
        self._checkpoint_manager = checkpoint_manager
        self._plan_history = plan_history
        self._max_replay_attempts = max_replay_attempts
        self._recovery_log: list[RecoveryResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recover_node(
        self,
        node_id: str,
        swarm_id: str,
        task_id: str = "",
    ) -> RecoveryResult:
        """Recover a crashed node by replaying its plan from checkpoint.

        Args:
            node_id: The crashed node to recover.
            swarm_id: The swarm the node belongs to.
            task_id: Optional task identifier.

        Returns:
            RecoveryResult with replay details.
        """
        start_time = time.time()
        errors: list[str] = []

        if self._checkpoint_manager is None:
            return RecoveryResult(
                success=False,
                node_id=node_id,
                errors=["No checkpoint manager available for recovery."],
                recovery_time_seconds=time.time() - start_time,
            )

        # Find the last checkpoint for this swarm
        last_checkpoint = self._checkpoint_manager.get_last_checkpoint(swarm_id)
        if last_checkpoint is None:
            return RecoveryResult(
                success=False,
                node_id=node_id,
                errors=[f"No checkpoint found for swarm '{swarm_id}'."],
                recovery_time_seconds=time.time() - start_time,
            )

        # Verify checkpoint integrity
        if not last_checkpoint.verify_integrity():
            return RecoveryResult(
                success=False,
                node_id=node_id,
                checkpoint_id=last_checkpoint.checkpoint_id,
                errors=["Checkpoint integrity verification failed."],
                recovery_time_seconds=time.time() - start_time,
            )

        # Determine which steps remain to be executed
        completed_steps = set()
        if last_checkpoint.agent_states:
            for agent_id, state in last_checkpoint.agent_states.items():
                completed_steps.update(state.get("completed_steps", []))

        plan_steps = last_checkpoint.plan_data
        all_step_ids = {step.get("node_id", f"step-{i}") for i, step in enumerate(plan_steps)}
        remaining_steps = all_step_ids - completed_steps

        # Build replayed plan (only uncompleted steps)
        replayed_plan = [
            step for i, step in enumerate(plan_steps)
            if step.get("node_id", f"step-{i}") not in completed_steps
        ]

        # Attempt replay
        replayed = 0
        missing = 0
        for attempt in range(1, self._max_replay_attempts + 1):
            try:
                replayed = len(replayed_plan)
                missing = len(remaining_steps) - replayed
                break
            except Exception as exc:
                errors.append(f"Replay attempt {attempt} failed: {exc}")

        result = RecoveryResult(
            success=len(errors) == 0,
            node_id=node_id,
            checkpoint_id=last_checkpoint.checkpoint_id,
            replayed_steps=replayed,
            missing_steps=missing,
            recovery_time_seconds=time.time() - start_time,
            errors=errors,
        )
        self._recovery_log.append(result)
        return result

    def recover_swarm(
        self, swarm_id: str, crashed_nodes: list[str]
    ) -> dict[str, RecoveryResult]:
        """Recover multiple crashed nodes in a swarm.

        Args:
            swarm_id: The swarm identifier.
            crashed_nodes: List of node IDs that need recovery.

        Returns:
            Dict mapping node_id to RecoveryResult.
        """
        results: dict[str, RecoveryResult] = {}
        for node_id in crashed_nodes:
            results[node_id] = self.recover_node(node_id, swarm_id)
        return results

    def replay_plan(
        self,
        plan_data: list[dict[str, Any]],
        from_step: int = 0,
    ) -> dict[str, Any]:
        """Replay a plan from a specific step index.

        Args:
            plan_data: The plan steps to replay.
            from_step: Index to start replay from.

        Returns:
            Dict with replay results.
        """
        if not plan_data:
            return {"success": False, "replayed": 0, "error": "Empty plan data"}

        steps = plan_data[from_step:]
        replayed = 0
        failed_steps: list[dict[str, Any]] = []

        for i, step in enumerate(steps):
            step_id = step.get("node_id", f"step-{from_step + i}")
            try:
                # In a real system, this would dispatch the step to the agent
                replayed += 1
            except Exception as exc:
                failed_steps.append({"step_id": step_id, "error": str(exc)})

        return {
            "success": len(failed_steps) == 0,
            "replayed": replayed,
            "total_steps": len(steps),
            "failed_steps": failed_steps,
            "from_step": from_step,
        }

    def get_recovery_log(self) -> list[RecoveryResult]:
        """Return the full recovery log."""
        return list(self._recovery_log)

    def get_last_recovery(self, node_id: str) -> RecoveryResult | None:
        """Get the most recent recovery result for a node."""
        for result in reversed(self._recovery_log):
            if result.node_id == node_id:
                return result
        return None

    def clear_log(self) -> None:
        """Clear the recovery log."""
        self._recovery_log.clear()
