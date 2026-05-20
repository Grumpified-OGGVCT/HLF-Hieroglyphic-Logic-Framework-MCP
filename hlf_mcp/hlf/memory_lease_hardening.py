"""Memory Lease Hardening — negotiation, auditing, pressure handling, and tier migration.

Extends the basic memory lease system with:
- LeaseNegotiator: priority-based preemption for lease acquisition
- LeaseAuditor: TTL enforcement, idle detection, utilization tracking
- MemoryPressureHandler: eviction under memory pressure with pinned lease protection
- LeaseMigration: hot/warm/cold tier movement based on access patterns
"""

from __future__ import annotations

import heapq
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from hlf_mcp.hlf.knowledge.memory_lease import (
    LeaseManager,
    LeaseScope,
    LeaseViolationError,
    MemoryLease,
)


# ---------------------------------------------------------------------------
# Lease Priority & Tier
# ---------------------------------------------------------------------------

class LeasePriority(Enum):
    """Priority levels for lease negotiation and preemption."""
    CRITICAL = 0    # pinned — never evicted
    HIGH = 1        # important operational knowledge
    MEDIUM = 2      # normal knowledge
    LOW = 3         # ephemeral / speculative knowledge
    IDLE = 4        # scheduled for eviction

    def can_preempt(self, other: "LeasePriority") -> bool:
        """Check if this priority can preempt another."""
        return self.value < other.value


class MemoryTier(Enum):
    """Memory tiers for lease migration based on access patterns."""
    HOT = auto()     # frequently accessed, lowest latency
    WARM = auto()    # moderately accessed
    COLD = auto()    # rarely accessed, may be archived


# ---------------------------------------------------------------------------
# Lease Negotiator
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NegotiatedLease:
    """A lease acquired through priority-based negotiation.

    Extends MemoryLease with priority and preemption metadata.
    """

    lease: MemoryLease
    priority: LeasePriority = LeasePriority.MEDIUM
    pinned: bool = False
    preempted_lease_id: str | None = None
    negotiation_rounds: int = 0
    tier: MemoryTier = MemoryTier.WARM

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.lease.to_dict(),
            "priority": self.priority.name,
            "pinned": self.pinned,
            "preempted_lease_id": self.preempted_lease_id,
            "negotiation_rounds": self.negotiation_rounds,
            "tier": self.tier.name,
        }


class LeaseNegotiator:
    """Negotiates memory leases with priority-based preemption.

    When a high-priority agent needs a memory key already held by a lower-
    priority agent, the negotiator can preempt the existing lease (with
    appropriate notification).

    Thread-safe via internal lock.
    """

    def __init__(self, lease_manager: LeaseManager | None = None) -> None:
        """Initialize the negotiator.

        Args:
            lease_manager: Optional shared LeaseManager. Creates one if None.
        """
        self._lease_mgr = lease_manager or LeaseManager()
        self._negotiated: dict[str, NegotiatedLease] = {}  # lease_id → NegotiatedLease
        self._lock = threading.Lock()

    def negotiate(
        self,
        holder_id: str,
        memory_key: str,
        priority: LeasePriority = LeasePriority.MEDIUM,
        duration_seconds: int = 300,
        scope: LeaseScope = "write",
        pinned: bool = False,
        max_rounds: int = 3,
    ) -> NegotiatedLease:
        """Negotiate a lease, preempting lower-priority holders if needed.

        Args:
            holder_id: The agent requesting the lease.
            memory_key: The memory resource key.
            priority: Requested priority level.
            duration_seconds: Lease duration in seconds.
            scope: Access scope.
            pinned: Whether the lease is pinned (never evicted under pressure).
            max_rounds: Maximum negotiation rounds before giving up.

        Returns:
            NegotiatedLease with the acquired lease and metadata.

        Raises:
            LeaseViolationError: If negotiation fails after max_rounds.
        """
        with self._lock:
            rounds = 0
            while rounds < max_rounds:
                rounds += 1

                # Check if key is held
                existing_holder = self._lease_mgr.get_holder(memory_key)

                if existing_holder is None:
                    # Key is free — acquire directly
                    lease = self._lease_mgr.acquire(
                        holder_id, memory_key, duration_seconds, scope
                    )
                    neg = NegotiatedLease(
                        lease=lease,
                        priority=priority,
                        pinned=pinned,
                        negotiation_rounds=rounds,
                    )
                    self._negotiated[lease.lease_id] = neg
                    return neg

                if existing_holder == holder_id:
                    # Already held by this agent — renew
                    existing = self._find_negotiated_for_key(memory_key)
                    if existing:
                        renewed = self._lease_mgr.renew(
                            existing.lease.lease_id, duration_seconds
                        )
                        existing.lease = renewed
                        existing.priority = priority
                        existing.negotiation_rounds += rounds
                        return existing

                # Check if we can preempt
                existing_neg = self._find_negotiated_for_key(memory_key)
                if existing_neg and priority.can_preempt(existing_neg.priority):
                    # Preempt!
                    preempted_id = existing_neg.lease.lease_id
                    self._lease_mgr.release(preempted_id)
                    lease = self._lease_mgr.acquire(
                        holder_id, memory_key, duration_seconds, scope
                    )
                    neg = NegotiatedLease(
                        lease=lease,
                        priority=priority,
                        pinned=pinned,
                        preempted_lease_id=preempted_id,
                        negotiation_rounds=rounds,
                    )
                    self._negotiated[lease.lease_id] = neg
                    return neg

                # Cannot preempt — wait and retry
                time.sleep(0.05)

            # Exhausted negotiation rounds
            raise LeaseViolationError(
                f"Negotiation failed for '{memory_key}' after {max_rounds} rounds. "
                f"Held by '{existing_holder}' with higher or equal priority.",
            )

    def release_negotiated(self, lease_id: str) -> bool:
        """Release a negotiated lease.

        Args:
            lease_id: The lease ID to release.

        Returns:
            True if released successfully.
        """
        with self._lock:
            self._negotiated.pop(lease_id, None)
            return self._lease_mgr.release(lease_id)

    def get_negotiated(self, lease_id: str) -> NegotiatedLease | None:
        """Get negotiated lease metadata by lease ID.

        Args:
            lease_id: The lease ID.

        Returns:
            NegotiatedLease if found, None otherwise.
        """
        with self._lock:
            return self._negotiated.get(lease_id)

    def list_by_priority(self) -> dict[str, list[str]]:
        """List active leases grouped by priority level.

        Returns:
            Dict mapping priority name to list of lease IDs.
        """
        with self._lock:
            result: dict[str, list[str]] = {p.name: [] for p in LeasePriority}
            for lid, neg in self._negotiated.items():
                if neg.lease.active and not neg.lease.is_expired():
                    result[neg.priority.name].append(lid)
            return result

    def preempt_lowest(self, memory_key: str) -> str | None:
        """Preempt the lowest-priority lease on a key, if any.

        Args:
            memory_key: The memory key to check.

        Returns:
            The lease ID that was preempted, or None.
        """
        with self._lock:
            active = [
                n for n in self._negotiated.values()
                if n.lease.memory_key == memory_key
                and n.lease.active
                and not n.lease.is_expired()
                and not n.pinned
            ]
            if not active:
                return None

            # Find lowest priority (highest enum value)
            lowest = max(active, key=lambda n: n.priority.value)
            self._lease_mgr.release(lowest.lease.lease_id)
            self._negotiated.pop(lowest.lease.lease_id, None)
            return lowest.lease.lease_id

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_negotiated_for_key(self, memory_key: str) -> NegotiatedLease | None:
        """Find the NegotiatedLease for an active lease on a key."""
        holder = self._lease_mgr.get_holder(memory_key)
        if holder is None:
            return None
        active = self._lease_mgr.list_active(holder_id=holder)
        for lease_dict in active:
            lid = lease_dict["lease_id"]
            if lid in self._negotiated:
                return self._negotiated[lid]
        return None


# ---------------------------------------------------------------------------
# Lease Auditor
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class LeaseAuditRecord:
    """Audit record for a single lease.

    Attributes:
        lease_id: The lease identifier.
        holder_id: The agent holding the lease.
        memory_key: The memory resource.
        utilization_pct: Estimated utilization (0-100) based on access recency.
        idle_seconds: Seconds since last access.
        ttl_remaining: Seconds until lease expiry.
        is_idle: Whether the lease is considered idle.
        should_evict: Whether the auditor recommends eviction.
        recommendation: Human-readable recommendation.
    """

    lease_id: str
    holder_id: str
    memory_key: str
    utilization_pct: float
    idle_seconds: float
    ttl_remaining: float
    is_idle: bool
    should_evict: bool
    recommendation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "holder_id": self.holder_id,
            "memory_key": self.memory_key,
            "utilization_pct": self.utilization_pct,
            "idle_seconds": self.idle_seconds,
            "ttl_remaining": self.ttl_remaining,
            "is_idle": self.is_idle,
            "should_evict": self.should_evict,
            "recommendation": self.recommendation,
        }


class LeaseAuditor:
    """Tracks lease utilization, detects idle leases, and enforces TTL.

    Maintains access timestamps for each lease and periodically audits
    for idle leases, approaching TTL expiry, and utilization patterns.
    """

    def __init__(
        self,
        idle_threshold_seconds: int = 120,
        ttl_warning_seconds: int = 60,
        leash_manager: LeaseManager | None = None,
    ) -> None:
        """Initialize the lease auditor.

        Args:
            idle_threshold_seconds: Mark a lease idle after this many seconds
                without access.
            ttl_warning_seconds: Warn when TTL is within this many seconds.
            leash_manager: Optional shared LeaseManager.
        """
        self._idle_threshold = idle_threshold_seconds
        self._ttl_warning = ttl_warning_seconds
        self._lease_mgr = leash_manager or LeaseManager()
        self._access_log: dict[str, list[float]] = {}  # lease_id → [timestamps]
        self._lock = threading.Lock()

    def record_access(self, lease_id: str) -> None:
        """Record an access to a lease.

        Args:
            lease_id: The lease being accessed.
        """
        with self._lock:
            if lease_id not in self._access_log:
                self._access_log[lease_id] = []
            self._access_log[lease_id].append(time.time())

    def audit(self) -> list[LeaseAuditRecord]:
        """Audit all active leases for utilization and TTL.

        Returns:
            List of LeaseAuditRecords, one per active lease.
        """
        with self._lock:
            now = time.time()
            active = self._lease_mgr.list_active()
            records: list[LeaseAuditRecord] = []

            for lease_dict in active:
                lid = lease_dict["lease_id"]
                holder = lease_dict["holder_id"]
                key = lease_dict["memory_key"]
                ttl_remaining = max(0.0, lease_dict.get("expires_at", now) - now)

                access_times = self._access_log.get(lid, [])
                # Remove stale access records (older than idle threshold * 2)
                recent = [t for t in access_times if now - t < self._idle_threshold * 2]
                self._access_log[lid] = recent

                if recent:
                    idle_seconds = now - max(recent)
                    # Utilization: more recent + frequent access = higher %
                    freq = len(recent) / max(self._idle_threshold, 1)
                    recency = max(0.0, 1.0 - idle_seconds / self._idle_threshold)
                    util_pct = round(min(100.0, (0.6 * recency + 0.4 * min(freq, 1.0)) * 100), 1)
                else:
                    idle_seconds = ttl_remaining or self._idle_threshold
                    util_pct = 0.0

                is_idle = idle_seconds >= self._idle_threshold
                should_evict = is_idle and ttl_remaining < self._ttl_warning

                if should_evict:
                    rec = "EVICT: lease idle and approaching TTL expiry."
                elif is_idle:
                    rec = "WARN: lease idle — consider release if not needed."
                elif ttl_remaining < self._ttl_warning:
                    rec = "WARN: lease TTL approaching — renew if still needed."
                else:
                    rec = "OK: lease active and utilized."

                records.append(LeaseAuditRecord(
                    lease_id=lid,
                    holder_id=holder,
                    memory_key=key,
                    utilization_pct=util_pct,
                    idle_seconds=round(idle_seconds, 1),
                    ttl_remaining=round(ttl_remaining, 1),
                    is_idle=is_idle,
                    should_evict=should_evict,
                    recommendation=rec,
                ))

            return records

    def audit_summary(self) -> dict[str, Any]:
        """Generate a summary of the current lease audit.

        Returns:
            Dict with counts by status and recommendations.
        """
        records = self.audit()
        if not records:
            return {
                "total_leases": 0,
                "idle_count": 0,
                "eviction_candidates": 0,
                "average_utilization_pct": 0.0,
                "recommendations": [],
            }

        idle_count = sum(1 for r in records if r.is_idle)
        evict_count = sum(1 for r in records if r.should_evict)
        avg_util = sum(r.utilization_pct for r in records) / len(records)

        return {
            "total_leases": len(records),
            "idle_count": idle_count,
            "eviction_candidates": evict_count,
            "average_utilization_pct": round(avg_util, 1),
            "recommendations": [
                {"lease_id": r.lease_id, "recommendation": r.recommendation}
                for r in records
                if r.should_evict or r.is_idle
            ],
        }

    def get_access_pattern(self, lease_id: str) -> dict[str, Any]:
        """Get access pattern analysis for a specific lease.

        Args:
            lease_id: The lease ID to analyze.

        Returns:
            Dict with access count, frequency, and pattern classification.
        """
        with self._lock:
            access_times = self._access_log.get(lease_id, [])
            if not access_times:
                return {
                    "lease_id": lease_id,
                    "access_count": 0,
                    "access_frequency_hz": 0.0,
                    "pattern": "never_accessed",
                }

            now = time.time()
            recent = [t for t in access_times if now - t < 3600]
            count = len(recent)

            if count < 2:
                freq = 0.0
                pattern = "sporadic"
            else:
                intervals = [
                    recent[i] - recent[i - 1]
                    for i in range(1, len(recent))
                ]
                avg_interval = sum(intervals) / len(intervals)
                freq = 1.0 / max(avg_interval, 0.001)
                if freq > 1.0:
                    pattern = "hot"
                elif freq > 0.1:
                    pattern = "warm"
                else:
                    pattern = "cold"

            return {
                "lease_id": lease_id,
                "access_count": count,
                "access_frequency_hz": round(freq, 4),
                "pattern": pattern,
                "window_seconds": 3600,
            }


# ---------------------------------------------------------------------------
# Memory Pressure Handler
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class EvictionResult:
    """Result of a memory pressure eviction operation.

    Attributes:
        evicted_count: Number of leases evicted.
        freed_keys: List of memory keys that were freed.
        failed_evictions: List of lease IDs that could not be evicted (pinned).
        pressure_level: The pressure level that triggered eviction.
        before_count: Total active leases before eviction.
        after_count: Total active leases after eviction.
    """

    evicted_count: int
    freed_keys: list[str]
    failed_evictions: list[str]
    pressure_level: str
    before_count: int
    after_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "evicted_count": self.evicted_count,
            "freed_keys": self.freed_keys,
            "failed_evictions": self.failed_evictions,
            "pressure_level": self.pressure_level,
            "before_count": self.before_count,
            "after_count": self.after_count,
        }


class MemoryPressureHandler:
    """Handles memory pressure by evicting low-priority leases.

    Under memory pressure, evicts the lowest-priority non-pinned leases
    to free resources while preserving critical knowledge.
    """

    def __init__(
        self,
        lease_manager: LeaseManager | None = None,
        negotiator: LeaseNegotiator | None = None,
        max_leases: int = 1000,
        warning_threshold: float = 0.7,
        critical_threshold: float = 0.9,
    ) -> None:
        """Initialize the memory pressure handler.

        Args:
            lease_manager: Optional shared LeaseManager.
            negotiator: Optional shared LeaseNegotiator for priority info.
            max_leases: Soft maximum number of active leases.
            warning_threshold: Pressure ratio (0-1) to trigger warning eviction.
            critical_threshold: Pressure ratio (0-1) to trigger aggressive eviction.
        """
        self._lease_mgr = lease_manager or LeaseManager()
        self._negotiator = negotiator
        self._max_leases = max_leases
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold

    def assess_pressure(self) -> dict[str, Any]:
        """Assess current memory pressure level.

        Returns:
            Dict with pressure level, active count, and thresholds.
        """
        active = self._lease_mgr.list_active()
        count = len(active)
        ratio = count / max(self._max_leases, 1)

        if ratio >= self._critical_threshold:
            level = "critical"
        elif ratio >= self._warning_threshold:
            level = "warning"
        else:
            level = "normal"

        return {
            "pressure_level": level,
            "active_lease_count": count,
            "max_leases": self._max_leases,
            "utilization_ratio": round(ratio, 4),
            "warning_threshold": self._warning_threshold,
            "critical_threshold": self._critical_threshold,
        }

    def evict_under_pressure(
        self,
        target_count: int | None = None,
    ) -> EvictionResult:
        """Evict lowest-priority leases to relieve memory pressure.

        Preserves pinned (CRITICAL priority) leases. Evicts in order:
        IDLE → LOW → MEDIUM (only under critical pressure).

        Args:
            target_count: Target number of active leases after eviction.
                If None, evicts down to warning_threshold * max_leases.

        Returns:
            EvictionResult with eviction details.
        """
        if target_count is None:
            target_count = int(self._max_leases * self._warning_threshold * 0.8)

        active = self._lease_mgr.list_active()
        before_count = len(active)

        if before_count <= target_count:
            return EvictionResult(
                evicted_count=0,
                freed_keys=[],
                failed_evictions=[],
                pressure_level="normal",
                before_count=before_count,
                after_count=before_count,
            )

        # Build eviction candidates sorted by priority (lowest first)
        candidates: list[tuple[int, dict[str, Any]]] = []
        for lease_dict in active:
            lid = lease_dict["lease_id"]
            neg = self._negotiator.get_negotiated(lid) if self._negotiator else None
            prio_val = neg.priority.value if neg else LeasePriority.MEDIUM.value
            if neg and neg.pinned:
                continue  # never evict pinned
            candidates.append((prio_val, lease_dict))

        # Sort by priority value descending (lowest priority first)
        candidates.sort(key=lambda x: -x[0])

        to_evict = before_count - target_count
        evicted = 0
        freed_keys: list[str] = []
        failed: list[str] = []

        for _, lease_dict in candidates:
            if evicted >= to_evict:
                break

            lid = lease_dict["lease_id"]
            key = lease_dict["memory_key"]

            # Check if pinned via negotiator
            neg = self._negotiator.get_negotiated(lid) if self._negotiator else None
            if neg and neg.pinned:
                failed.append(lid)
                continue

            if self._lease_mgr.release(lid):
                evicted += 1
                freed_keys.append(key)
            else:
                failed.append(lid)

        after_active = self._lease_mgr.list_active()

        return EvictionResult(
            evicted_count=evicted,
            freed_keys=freed_keys,
            failed_evictions=failed,
            pressure_level=self.assess_pressure()["pressure_level"],
            before_count=before_count,
            after_count=len(after_active),
        )

    def protect_critical(self, lease_ids: list[str]) -> int:
        """Mark specific leases as pinned (critical, never evicted).

        Args:
            lease_ids: List of lease IDs to protect.

        Returns:
            Number of leases successfully protected.
        """
        if not self._negotiator:
            return 0

        protected = 0
        for lid in lease_ids:
            neg = self._negotiator.get_negotiated(lid)
            if neg:
                neg.pinned = True
                neg.priority = LeasePriority.CRITICAL
                protected += 1
        return protected

    def pressure_report(self) -> dict[str, Any]:
        """Generate a comprehensive pressure report.

        Returns:
            Dict with pressure assessment and eviction plan.
        """
        assessment = self.assess_pressure()
        active = self._lease_mgr.list_active()

        pinned_count = 0
        priority_counts = {p.name: 0 for p in LeasePriority}

        for lease_dict in active:
            lid = lease_dict["lease_id"]
            neg = self._negotiator.get_negotiated(lid) if self._negotiator else None
            if neg and neg.pinned:
                pinned_count += 1
            prio = neg.priority if neg else LeasePriority.MEDIUM
            priority_counts[prio.name] += 1

        return {
            **assessment,
            "pinned_leases": pinned_count,
            "evictable_leases": len(active) - pinned_count,
            "by_priority": priority_counts,
            "warning_active": len(active) > self._max_leases * self._warning_threshold,
            "critical_active": len(active) > self._max_leases * self._critical_threshold,
        }


# ---------------------------------------------------------------------------
# Lease Migration
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class MigrationPlan:
    """A plan for migrating leases between memory tiers.

    Attributes:
        migrations: List of (lease_id, from_tier, to_tier) tuples.
        rationale: Dict of lease_id → reason for migration.
        estimated_impact: Human-readable impact description.
    """

    migrations: list[tuple[str, str, str]] = field(default_factory=list)
    rationale: dict[str, str] = field(default_factory=dict)
    estimated_impact: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "migrations": [
                {"lease_id": lid, "from_tier": fr, "to_tier": to}
                for lid, fr, to in self.migrations
            ],
            "rationale": self.rationale,
            "estimated_impact": self.estimated_impact,
            "total_migrations": len(self.migrations),
        }


class LeaseMigration:
    """Migrates leased knowledge between hot/warm/cold memory tiers.

    Analyzes access patterns from a LeaseAuditor to determine optimal
    tier placement for each lease, then produces a migration plan.
    """

    def __init__(
        self,
        auditor: LeaseAuditor | None = None,
        negotiator: LeaseNegotiator | None = None,
        lease_manager: LeaseManager | None = None,
    ) -> None:
        """Initialize the migration engine.

        Args:
            auditor: LeaseAuditor for access pattern analysis.
            negotiator: LeaseNegotiator for priority-aware migration.
            lease_manager: Optional shared LeaseManager.
        """
        self._auditor = auditor or LeaseAuditor()
        self._negotiator = negotiator
        self._lease_mgr = lease_manager or (
            negotiator._lease_mgr if negotiator else
            (auditor._lease_mgr if auditor else LeaseManager())
        )

    def classify_tier(self, lease_id: str) -> MemoryTier:
        """Classify the appropriate memory tier for a lease.

        Uses access frequency and recency from the auditor.

        Args:
            lease_id: The lease ID to classify.

        Returns:
            Recommended MemoryTier.
        """
        pattern = self._auditor.get_access_pattern(lease_id)
        pat = pattern.get("pattern", "sporadic")
        freq = pattern.get("access_frequency_hz", 0.0)

        if pat == "hot" or freq > 1.0:
            return MemoryTier.HOT
        elif pat == "warm" or freq > 0.05:
            return MemoryTier.WARM
        else:
            return MemoryTier.COLD

    def plan_migration(self) -> MigrationPlan:
        """Generate a migration plan for all active leases.

        Returns:
            MigrationPlan with tier assignments.
        """
        active = self._lease_mgr.list_active()
        plan = MigrationPlan()

        hot_count = 0
        warm_count = 0
        cold_count = 0

        for lease_dict in active:
            lid = lease_dict["lease_id"]
            recommended_tier = self.classify_tier(lid)

            current_tier = MemoryTier.WARM  # default
            if self._negotiator:
                neg = self._negotiator.get_negotiated(lid)
                if neg:
                    current_tier = neg.tier

            if recommended_tier != current_tier:
                plan.migrations.append((
                    lid,
                    current_tier.name,
                    recommended_tier.name,
                ))
                plan.rationale[lid] = (
                    f"Access pattern suggests {recommended_tier.name} tier "
                    f"(currently {current_tier.name})"
                )

            if recommended_tier == MemoryTier.HOT:
                hot_count += 1
            elif recommended_tier == MemoryTier.WARM:
                warm_count += 1
            else:
                cold_count += 1

        plan.estimated_impact = (
            f"After migration: {hot_count} hot, {warm_count} warm, "
            f"{cold_count} cold — {len(plan.migrations)} tier changes."
        )

        return plan

    def execute_migration(self, plan: MigrationPlan) -> dict[str, Any]:
        """Execute a migration plan, updating tier assignments.

        Args:
            plan: The MigrationPlan to execute.

        Returns:
            Dict with execution results.
        """
        if not self._negotiator:
            return {
                "executed": False,
                "reason": "No LeaseNegotiator available for tier assignment.",
                "planned_migrations": len(plan.migrations),
            }

        executed = 0
        failed: list[str] = []

        for lid, from_tier_name, to_tier_name in plan.migrations:
            neg = self._negotiator.get_negotiated(lid)
            if neg is None:
                failed.append(lid)
                continue

            try:
                neg.tier = MemoryTier[to_tier_name]
                executed += 1
            except KeyError:
                failed.append(lid)

        return {
            "executed": True,
            "migrated_count": executed,
            "failed_count": len(failed),
            "failed_ids": failed,
            "total_planned": len(plan.migrations),
        }

    def tier_distribution(self) -> dict[str, int]:
        """Get current distribution of leases across tiers.

        Returns:
            Dict mapping tier name to count.
        """
        dist: dict[str, int] = {t.name: 0 for t in MemoryTier}
        active = self._lease_mgr.list_active()

        for lease_dict in active:
            lid = lease_dict["lease_id"]
            tier = MemoryTier.WARM
            if self._negotiator:
                neg = self._negotiator.get_negotiated(lid)
                if neg:
                    tier = neg.tier
            dist[tier.name] += 1

        return dist

    def demote_cold(self, max_cold: int = 100) -> list[str]:
        """Demote cold-tier leases that exceed the cold capacity.

        Args:
            max_cold: Maximum number of leases allowed in cold tier.

        Returns:
            List of lease IDs that were evicted from cold tier.
        """
        active = self._lease_mgr.list_active()
        cold_leases: list[tuple[float, str]] = []  # (last_access, lease_id)

        for lease_dict in active:
            lid = lease_dict["lease_id"]
            if self.classify_tier(lid) == MemoryTier.COLD:
                pattern = self._auditor.get_access_pattern(lid)
                access_count = pattern.get("access_count", 0)
                cold_leases.append((access_count, lid))

        if len(cold_leases) <= max_cold:
            return []

        # Evict the least-accessed cold leases
        cold_leases.sort(key=lambda x: x[0])
        to_evict = len(cold_leases) - max_cold
        evicted: list[str] = []

        for _, lid in cold_leases[:to_evict]:
            if self._lease_mgr.release(lid):
                evicted.append(lid)

        return evicted
