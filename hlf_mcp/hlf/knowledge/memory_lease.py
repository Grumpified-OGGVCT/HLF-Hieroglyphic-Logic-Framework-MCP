"""MemoryLease — lease system for temporary memory ownership.

Provides scoped (read / write / exclusive) leases with expiration,
renewal, and strict conflict detection.  Thread-safe via threading.Lock.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

LeaseScope = Literal["read", "write", "exclusive"]


class LeaseViolationError(Exception):
    """Raised when a lease acquisition conflicts with an existing lease."""

    def __init__(self, message: str, existing_lease: "MemoryLease | None" = None) -> None:
        super().__init__(message)
        self.existing_lease = existing_lease


@dataclass(slots=True)
class MemoryLease:
    """A time-bounded lease on a memory key held by a specific agent.

    Attributes:
        lease_id: Unique identifier for this lease.
        holder_id: The agent or entity holding the lease.
        memory_key: The memory resource being leased.
        granted_at: Unix timestamp when the lease was granted.
        expires_at: Unix timestamp when the lease expires.
        renewal_count: Number of times this lease has been renewed.
        active: Whether the lease is currently active.
        scope: The access scope — "read", "write", or "exclusive".
    """

    lease_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    holder_id: str = ""
    memory_key: str = ""
    granted_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    renewal_count: int = 0
    active: bool = True
    scope: LeaseScope = "write"

    def __post_init__(self) -> None:
        if self.expires_at <= 0.0:
            self.expires_at = self.granted_at + 300.0  # default 5 minutes

    def is_expired(self, now_ts: float | None = None) -> bool:
        """Check whether the lease has expired.

        Args:
            now_ts: Current time; defaults to time.time().

        Returns:
            True if the lease has passed its expiry.
        """
        now = now_ts if now_ts is not None else time.time()
        return now >= self.expires_at

    def remaining_seconds(self, now_ts: float | None = None) -> float:
        """Return the number of seconds remaining before expiry (may be negative)."""
        now = now_ts if now_ts is not None else time.time()
        return max(0.0, self.expires_at - now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "holder_id": self.holder_id,
            "memory_key": self.memory_key,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "renewal_count": self.renewal_count,
            "active": self.active,
            "scope": self.scope,
            "remaining_seconds": self.remaining_seconds(),
        }


class LeaseManager:
    """Manages scoped memory leases with thread-safe operations.

    Provides acquire / release / renew / check / expire lifecycle with
    conflict detection.  Exclusive leases block all others; write leases
    block other write/exclusive leases; read leases only block exclusive.
    """

    def __init__(self) -> None:
        self._leases: dict[str, MemoryLease] = {}
        self._key_index: dict[str, list[str]] = {}  # memory_key → [lease_id, ...]
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(
        self,
        holder_id: str,
        memory_key: str,
        duration_seconds: int = 300,
        scope: LeaseScope = "write",
    ) -> MemoryLease:
        """Acquire a lease on a memory key.

        Args:
            holder_id: The agent or entity requesting the lease.
            memory_key: The memory resource to lease.
            duration_seconds: Lease duration in seconds (default 300).
            scope: Access scope — "read", "write", or "exclusive".

        Returns:
            The newly created MemoryLease.

        Raises:
            LeaseViolationError: If the key is already exclusively held, or
                the requested scope conflicts with an existing lease.
        """
        with self._lock:
            self._expire_internal()

            existing_ids = self._key_index.get(memory_key, [])
            existing_active = [
                self._leases[lid]
                for lid in existing_ids
                if lid in self._leases and self._leases[lid].active
            ]

            # Check for exclusive conflicts
            for existing in existing_active:
                if existing.scope == "exclusive":
                    raise LeaseViolationError(
                        f"Memory key '{memory_key}' is exclusively held by "
                        f"'{existing.holder_id}' (lease {existing.lease_id}).",
                        existing_lease=existing,
                    )

            # Check scope conflicts:
            #  - exclusive requestor: any active lease is a conflict
            #  - write requestor: clashes with write or exclusive
            #  - read requestor: clashes only with exclusive (already handled)
            if scope == "exclusive" and existing_active:
                holder = existing_active[0].holder_id
                raise LeaseViolationError(
                    f"Cannot acquire exclusive lease on '{memory_key}' — "
                    f"held by '{holder}'.",
                    existing_lease=existing_active[0],
                )
            if scope == "write":
                for existing in existing_active:
                    if existing.scope in ("write", "exclusive"):
                        raise LeaseViolationError(
                            f"Cannot acquire write lease on '{memory_key}' — "
                            f"held by '{existing.holder_id}' as '{existing.scope}'.",
                            existing_lease=existing,
                        )

            # Same holder acquiring another read lease on the same key: allow
            # Same holder upgrading read → write: allow (replace old)
            if scope != "read":
                same_holder = [
                    e for e in existing_active if e.holder_id == holder_id
                ]
                for old in same_holder:
                    old.active = False

            # Refresh the active list after deactivating same-holder
            existing_active = [
                e for e in existing_active if e.active and e.holder_id != holder_id
            ]

            now = time.time()
            lease = MemoryLease(
                lease_id=str(uuid.uuid4()),
                holder_id=holder_id,
                memory_key=memory_key,
                granted_at=now,
                expires_at=now + duration_seconds,
                active=True,
                scope=scope,
            )

            self._leases[lease.lease_id] = lease
            if memory_key not in self._key_index:
                self._key_index[memory_key] = []
            self._key_index[memory_key].append(lease.lease_id)

            return lease

    def release(self, lease_id: str) -> bool:
        """Release a lease by its ID.

        Args:
            lease_id: The lease identifier to release.

        Returns:
            True if the lease was found and deactivated, False otherwise.
        """
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                return False
            was_active = lease.active
            lease.active = False
            return was_active

    def renew(self, lease_id: str, duration_seconds: int | None = None) -> MemoryLease:
        """Extend a lease's duration.

        The lease expiration is set to ``now + duration_seconds``.  If
        ``duration_seconds`` is None, the original duration (expires_at -
        granted_at) is re-used.

        Args:
            lease_id: The lease to renew.
            duration_seconds: New duration; if None, uses original duration.

        Returns:
            The updated MemoryLease.

        Raises:
            ValueError: If the lease is not found or is not active.
        """
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                raise ValueError(f"Lease '{lease_id}' not found.")
            if not lease.active:
                raise ValueError(f"Lease '{lease_id}' is not active.")

            if duration_seconds is None:
                duration_seconds = int(lease.expires_at - lease.granted_at)

            now = time.time()
            lease.expires_at = now + max(duration_seconds, 1)
            lease.renewal_count += 1
            lease.active = True

            return lease

    def check(self, lease_id: str) -> MemoryLease | None:
        """Check the status of a lease.

        Returns the lease if found, or None.  If the lease has expired it
        is marked inactive and None is returned.

        Args:
            lease_id: The lease identifier to check.

        Returns:
            MemoryLease if active, None otherwise.
        """
        with self._lock:
            lease = self._leases.get(lease_id)
            if lease is None:
                return None
            if lease.is_expired():
                lease.active = False
                return None
            return lease

    def expire_stale(self) -> list[MemoryLease]:
        """Expire all stale (past-expiry) leases.

        Returns:
            List of leases that were deactivated.
        """
        with self._lock:
            return self._expire_internal()

    def is_held(self, memory_key: str) -> bool:
        """Check whether a memory key has any active leases.

        Args:
            memory_key: The memory resource key.

        Returns:
            True if at least one active lease exists for the key.
        """
        with self._lock:
            self._expire_internal()  # clean up expired first
            lease_ids = self._key_index.get(memory_key, [])
            return any(
                lid in self._leases and self._leases[lid].active
                for lid in lease_ids
            )

    def get_holder(self, memory_key: str) -> str | None:
        """Get the current holder of a memory key.

        If multiple active leases exist, returns the holder of the most
        restrictive lease (exclusive > write > read).

        Args:
            memory_key: The memory resource key.

        Returns:
            Holder ID string, or None if no active lease exists.
        """
        with self._lock:
            self._expire_internal()
            lease_ids = self._key_index.get(memory_key, [])
            active = [
                self._leases[lid]
                for lid in lease_ids
                if lid in self._leases and self._leases[lid].active
            ]
            if not active:
                return None

            # Return the most restrictive holder
            scope_rank = {"exclusive": 3, "write": 2, "read": 1}
            active.sort(key=lambda l: scope_rank.get(l.scope, 0), reverse=True)
            return active[0].holder_id

    def list_active(self, holder_id: str | None = None) -> list[dict[str, Any]]:
        """List all active leases, optionally filtered by holder.

        Args:
            holder_id: If provided, only return leases held by this entity.

        Returns:
            List of lease dicts.
        """
        with self._lock:
            self._expire_internal()
            leases = self._leases.values()
            if holder_id:
                leases = [l for l in leases if l.holder_id == holder_id]
            return [l.to_dict() for l in leases if l.active]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _expire_internal(self) -> list[MemoryLease]:
        """Expire all stale leases.  Must be called under lock."""
        now = time.time()
        expired: list[MemoryLease] = []
        for lease in self._leases.values():
            if lease.active and lease.is_expired(now_ts=now):
                lease.active = False
                expired.append(lease)
        return expired
