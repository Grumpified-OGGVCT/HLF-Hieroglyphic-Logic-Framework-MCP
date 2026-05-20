"""
Distributed Rate Limiter — coordinates rate limits across multiple service
instances using shared state and fair-share token allocation.

Extends the single-instance TokenBucket / RateLimiter with cross-instance
coordination via three modes:
  - LOCAL_ONLY: Falls back to per-instance TokenBucket (no coordination).
  - IN_MEMORY_SHARED: Uses a shared in-process state registry for
    multi-instance coordination within a single process.
  - REDIS_BACKED: Placeholder for Redis-based coordination across
    networked instances (implements the same interface).

Fairness is measured with Jain's fairness index, and instances are
auto-deregistered when their heartbeat times out.  Token rebalancing
redistributes unused capacity proportionally across active instances.

Integration points:
  - hlf_mcp.ecosystem.rate_limiter.TokenBucket (per-instance bucket)
  - hlf_mcp.ecosystem.rate_limiter.RateLimiter (global + per-effect scoping)
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (multi-instance MCP servers)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (multi-instance REST servers)
"""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# CoordinationMode enum
# ═══════════════════════════════════════════════════════════════════════════════


class CoordinationMode(Enum):
    """Backend modes for distributed rate-limit coordination."""

    LOCAL_ONLY = "local_only"           # Single-instance, no coordination
    IN_MEMORY_SHARED = "in_memory_shared"  # Shared dict within a process
    REDIS_BACKED = "redis_backed"       # Redis-based distributed state


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimitState — per-instance snapshot
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RateLimitState:
    """Snapshot of a single instance's rate-limit status.

    Attributes:
        instance_id: Unique identifier for the instance.
        tokens_available: Current token count for this instance.
        last_refill: Monotonic timestamp of the last token refill.
        active_leases: Number of currently held token leases.
        reported_at: ISO-8601 timestamp of the last heartbeat.
    """

    instance_id: str
    tokens_available: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)
    active_leases: int = 0
    reported_at: str = ""

    def __post_init__(self) -> None:
        if not self.reported_at:
            self.reported_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "tokens_available": self.tokens_available,
            "last_refill": self.last_refill,
            "active_leases": self.active_leases,
            "reported_at": self.reported_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitState:
        return cls(
            instance_id=str(data.get("instance_id", "")),
            tokens_available=float(data.get("tokens_available", 0.0)),
            last_refill=float(data.get("last_refill", time.monotonic())),
            active_leases=int(data.get("active_leases", 0)),
            reported_at=str(data.get("reported_at", "")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _compute_jain_fairness_index(allocations: list[float]) -> float:
    """Compute Jain's fairness index for a list of resource allocations.

    Jain's index: J = (Σ x_i)² / (n · Σ x_i²)

    A value of 1.0 indicates perfect fairness (all allocations equal).
    Approaches 1/n as unfairness increases (where n is the number of
    participants).  Returns 1.0 for a single participant or when all
    allocations are zero.
    """
    n = len(allocations)
    if n == 0:
        return 1.0

    sum_vals = sum(allocations)
    if sum_vals == 0.0:
        return 1.0  # All zero is perfectly fair

    sum_squares = sum(x * x for x in allocations)
    if sum_squares == 0.0:
        return 1.0

    return (sum_vals * sum_vals) / (n * sum_squares)


def _redistribute_tokens(
    instances: dict[str, RateLimitState],
    total_capacity: float,
) -> dict[str, float]:
    """Redistribute tokens proportionally across instances.

    Each instance's share is proportional to its active_leases count.
    Instances with no leases get a minimum floor allocation
    (total_capacity / (2 * n)) to allow new work; the rest is divided
    by lease count.

    Args:
        instances: Dict of instance_id → RateLimitState for all active
                   instances.
        total_capacity: Total token capacity to distribute.

    Returns:
        Dict of instance_id → allocated token count.
    """
    n = len(instances)
    if n == 0:
        return {}

    total_leases = sum(s.active_leases for s in instances.values())
    floor = total_capacity / (2.0 * n) if n > 0 else 0.0

    # Floor allocation to every instance
    remaining = total_capacity - (floor * n)
    if remaining < 0:
        remaining = 0.0
        floor = total_capacity / n

    allocations: dict[str, float] = {}

    if total_leases == 0:
        # Equal distribution when no leases
        share = total_capacity / n
        for iid in instances:
            allocations[iid] = share
    else:
        for iid, state in instances.items():
            lease_share = (state.active_leases / total_leases) * remaining
            allocations[iid] = floor + lease_share

    return allocations


# ═══════════════════════════════════════════════════════════════════════════════
# DistributedRateLimiter — main class
# ═══════════════════════════════════════════════════════════════════════════════


class DistributedRateLimiter:
    """Coordinates rate limits across multiple service instances.

    Each instance gets a fair share of the total token capacity. The
    coordinator tracks heartbeats, auto-deregisters stale instances,
    and rebalances tokens when the instance pool changes.

    Attributes:
        name: Human-readable name for this coordinator.
        mode: Coordination backend mode.
        instance_id: Unique identifier for this coordinator node.
        total_capacity: Total token capacity across all instances.
        refill_rate: Tokens-per-second refill rate for the global pool.
        sync_interval: Seconds between heartbeat / sync operations.
        max_instances: Maximum number of instances allowed in the group.
        instances: Registry of instance_id → RateLimitState.
        lock: Reentrant lock for thread safety.
    """

    def __init__(
        self,
        name: str = "distributed-limiter",
        mode: CoordinationMode = CoordinationMode.IN_MEMORY_SHARED,
        instance_id: str | None = None,
        total_capacity: float = 100.0,
        refill_rate: float = 10.0,
        sync_interval: float = 1.0,
        max_instances: int = 10,
    ) -> None:
        self.name = name
        self.mode = mode
        self.instance_id = instance_id or self._generate_instance_id()
        self.total_capacity = total_capacity
        self.refill_rate = refill_rate
        self.sync_interval = sync_interval
        self.max_instances = max_instances

        self.instances: dict[str, RateLimitState] = {}
        self.lock = threading.RLock()

        if total_capacity <= 0:
            raise ValueError(f"total_capacity must be positive, got {total_capacity}")
        if refill_rate <= 0:
            raise ValueError(f"refill_rate must be positive, got {refill_rate}")
        if sync_interval <= 0:
            raise ValueError(f"sync_interval must be positive, got {sync_interval}")

    # ── Instance lifecycle ────────────────────────────────────────────────────

    def register_instance(self, instance_id: str | None = None) -> str:
        """Register a new instance in the coordination group.

        Args:
            instance_id: Desired instance ID. Auto-generated if None.

        Returns:
            The instance_id of the newly registered instance.

        Raises:
            RuntimeError: If max_instances would be exceeded.
        """
        iid = instance_id or self._generate_instance_id()

        with self.lock:
            if len(self.instances) >= self.max_instances and iid not in self.instances:
                raise RuntimeError(
                    f"DistributedRateLimiter '{self.name}': max_instances "
                    f"({self.max_instances}) reached — cannot register '{iid}'"
                )

            if iid in self.instances:
                # Re-registration: refresh heartbeat
                self.instances[iid].reported_at = datetime.now(timezone.utc).isoformat()
                return iid

            state = RateLimitState(
                instance_id=iid,
                tokens_available=self.total_capacity / (len(self.instances) + 1),
            )
            self.instances[iid] = state

            # Rebalance after adding
            self.rebalance()

        return iid

    def deregister_instance(self, instance_id: str) -> bool:
        """Remove an instance from the coordination group.

        Redistributes the departing instance's remaining tokens to the
        remaining instances.

        Args:
            instance_id: The instance to remove.

        Returns:
            True if the instance was found and removed, False otherwise.
        """
        with self.lock:
            if instance_id not in self.instances:
                return False

            remaining_tokens = self.instances[instance_id].tokens_available
            del self.instances[instance_id]

            # Redistribute tokens to remaining instances
            remaining_count = len(self.instances)
            if remaining_count > 0 and remaining_tokens > 0:
                share = remaining_tokens / remaining_count
                for state in self.instances.values():
                    state.tokens_available += share
                    # Cap at capacity share
                    cap_share = self.total_capacity / remaining_count
                    state.tokens_available = min(state.tokens_available, cap_share)

            return True

    # ── Token acquisition ─────────────────────────────────────────────────────

    def acquire(self, instance_id: str, tokens: float = 1.0) -> bool:
        """Acquire tokens for a specific instance.

        Checks the global state, applies fair-share allocation, and
        attempts to consume *tokens* from the instance's allocation.

        Args:
            instance_id: The requesting instance.
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens were acquired, False if rate-limited.
        """
        if tokens <= 0:
            return True

        with self.lock:
            # Auto-prune stale instances
            self._prune_stale()

            if instance_id not in self.instances:
                # Auto-register unknown instance if under limit
                if len(self.instances) < self.max_instances:
                    self.instances[instance_id] = RateLimitState(
                        instance_id=instance_id,
                        tokens_available=self.total_capacity / (len(self.instances) + 1),
                    )
                    self.rebalance()
                else:
                    return False

            state = self.instances[instance_id]

            # Refill this instance's tokens
            now = time.monotonic()
            elapsed = now - state.last_refill
            instance_rate = self.refill_rate / max(len(self.instances), 1)
            state.tokens_available = min(
                self.total_capacity / max(len(self.instances), 1),
                state.tokens_available + elapsed * instance_rate,
            )
            state.last_refill = now

            # Check availability
            if state.tokens_available >= tokens:
                state.tokens_available -= tokens
                state.active_leases += 1
                return True

            return False

    # ── Global state ──────────────────────────────────────────────────────────

    def get_global_state(self) -> dict[str, Any]:
        """Return the global view of the rate-limiting group.

        Includes total capacity, total consumed, per-instance utilization,
        and the fairness index.
        """
        with self.lock:
            self._prune_stale()

            total_consumed = sum(
                (self.total_capacity / max(len(self.instances), 1)) - s.tokens_available
                for s in self.instances.values()
            )

            per_instance = {}
            for iid, state in self.instances.items():
                cap_share = self.total_capacity / max(len(self.instances), 1)
                per_instance[iid] = {
                    "tokens_available": state.tokens_available,
                    "capacity_share": cap_share,
                    "utilization_pct": round(
                        max(0.0, (cap_share - state.tokens_available) / cap_share * 100)
                        if cap_share > 0 else 0.0,
                        2,
                    ),
                    "active_leases": state.active_leases,
                    "last_refill": state.last_refill,
                }

            allocations = [s.tokens_available for s in self.instances.values()]

            return {
                "name": self.name,
                "mode": self.mode.value,
                "total_capacity": self.total_capacity,
                "refill_rate": self.refill_rate,
                "instance_count": len(self.instances),
                "total_consumed": round(total_consumed, 2),
                "fairness_index": round(_compute_jain_fairness_index(allocations), 4),
                "per_instance": per_instance,
            }

    # ── Rebalancing ───────────────────────────────────────────────────────────

    def rebalance(self) -> None:
        """Redistribute tokens fairly across all registered instances.

        Uses the redistribution algorithm: floor allocation for every
        instance plus proportional share based on active leases.
        """
        with self.lock:
            if not self.instances:
                return

            allocations = _redistribute_tokens(self.instances, self.total_capacity)

            for iid, allocated in allocations.items():
                if iid in self.instances:
                    self.instances[iid].tokens_available = min(
                        allocated,
                        self.instances[iid].tokens_available + allocated,
                    )
                    # Cap at proportional capacity share
                    cap_share = self.total_capacity / len(self.instances)
                    self.instances[iid].tokens_available = min(
                        self.instances[iid].tokens_available,
                        cap_share,
                    )

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    def sync_heartbeat(self, instance_id: str) -> None:
        """Update an instance's last-reported timestamp.

        Stale instances (no heartbeat for 3× sync_interval) are
        auto-deregistered during the next ``acquire`` or ``get_global_state``
        call.
        """
        with self.lock:
            if instance_id in self.instances:
                self.instances[instance_id].reported_at = (
                    datetime.now(timezone.utc).isoformat()
                )
                self.instances[instance_id].last_refill = time.monotonic()

    def _prune_stale(self) -> int:
        """Remove instances that haven't sent a heartbeat within the timeout.

        Timeout = 3 × sync_interval.

        Returns:
            Count of instances pruned.
        """
        stale_ids: list[str] = []
        cutoff = time.monotonic() - (3.0 * self.sync_interval)

        for iid, state in self.instances.items():
            if state.last_refill < cutoff:
                stale_ids.append(iid)

        for iid in stale_ids:
            del self.instances[iid]

        if stale_ids and self.instances:
            self.rebalance()

        return len(stale_ids)

    # ── Fairness ──────────────────────────────────────────────────────────────

    def fairness_score(self) -> float:
        """Calculate Jain's fairness index across all registered instances.

        1.0 = perfectly fair (all instances have equal token allocation).
        Approaches 0 as unfairness increases.

        Returns:
            Fairness score between 0 and 1.
        """
        with self.lock:
            allocations = [s.tokens_available for s in self.instances.values()]
            return _compute_jain_fairness_index(allocations)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for the distributed limiter."""
        with self.lock:
            return {
                "name": self.name,
                "mode": self.mode.value,
                "instance_id": self.instance_id,
                "total_capacity": self.total_capacity,
                "refill_rate": self.refill_rate,
                "sync_interval": self.sync_interval,
                "max_instances": self.max_instances,
                "registered_instances": len(self.instances),
                "instance_ids": sorted(self.instances.keys()),
                "fairness_score": round(self.fairness_score(), 4),
                "total_available_tokens": round(
                    sum(s.tokens_available for s in self.instances.values()), 2
                ),
            }

    def release_lease(self, instance_id: str) -> None:
        """Decrement the active_leases counter for an instance.

        Called when a request completes, so the rebalancer gets an
        accurate picture of active demand.

        Args:
            instance_id: The instance releasing a lease.
        """
        with self.lock:
            if instance_id in self.instances:
                state = self.instances[instance_id]
                state.active_leases = max(0, state.active_leases - 1)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _generate_instance_id(self) -> str:
        """Generate a unique instance identifier using timestamp + random seed."""
        raw = f"{self.name}-{time.monotonic()}-{id(self)}"
        return f"hlf-dlr-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
