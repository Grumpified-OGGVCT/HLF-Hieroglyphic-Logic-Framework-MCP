"""
Circuit Breaker — prevents cascading failures in HLF ecosystem bridges.

Implements the standard CLOSED → OPEN → HALF_OPEN state machine with
configurable failure thresholds, recovery timeouts, and per-bridge isolation.
Each bridge instance gets its own circuit, so MCP bridge failures do not
affect the REST bridge and vice versa.

States:
  CLOSED    — Normal operation, requests flow through.  Failures increment
              a counter; exceeding the threshold trips the circuit to OPEN.
  OPEN      — All requests are immediately rejected (fast-fail). After a
              configurable timeout, the circuit transitions to HALF_OPEN.
  HALF_OPEN — A limited number of probe requests are allowed through.  If
              they succeed, the circuit resets to CLOSED.  If any fail,
              the circuit re-opens.

Integration points:
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (tool call circuit isolation)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (endpoint circuit isolation)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# CircuitState enum
# ═══════════════════════════════════════════════════════════════════════════════


class CircuitState(Enum):
    """The three canonical circuit-breaker states."""

    CLOSED = auto()       # Normal — requests pass through
    OPEN = auto()         # Tripped — requests fast-fail
    HALF_OPEN = auto()    # Recovery — limited probing


# ═══════════════════════════════════════════════════════════════════════════════
# CircuitOpenError — raised when a request is rejected by an open circuit
# ═══════════════════════════════════════════════════════════════════════════════


class CircuitOpenError(Exception):
    """Raised when a request is rejected because the circuit is OPEN."""

    def __init__(self, circuit_name: str, opened_at: float, retry_after: float):
        self.circuit_name = circuit_name
        self.opened_at = opened_at
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. "
            f"Opened at {opened_at:.1f}, retry after {retry_after:.1f}s"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CircuitBreaker — the core state machine
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CircuitBreaker:
    """Thread-safe circuit breaker with exponential backoff recovery.

    Attributes:
        name: Human-readable name for this circuit (e.g., "mcp_bridge",
              "rest_bridge").  Used for per-bridge isolation and error messages.
        failure_threshold: Number of consecutive failures in CLOSED state
                           before tripping to OPEN.
        recovery_timeout: Seconds to wait in OPEN state before transitioning
                          to HALF_OPEN.
        half_open_probe_count: Maximum number of probe requests allowed in
                               HALF_OPEN state before deciding success/failure.
        backoff_multiplier: Exponential backoff multiplier for recovery_timeout
                            after repeated trips (timeout * multiplier^n).
        max_recovery_timeout: Ceiling on exponential-backoff recovery timeouts.
        state: Current circuit state.
        failure_count: Consecutive failure counter (CLOSED state).
        probe_successes: Successful probe counter (HALF_OPEN state).
        probe_failures: Failed probe counter (HALF_OPEN state).
        last_failure_time: Monotonic timestamp of the most recent failure.
        last_success_time: Monotonic timestamp of the most recent success.
        trip_count: Total number of times the circuit has tripped to OPEN.
        open_since: Monotonic timestamp when circuit last opened.
        lock: Reentrant lock for thread safety.
    """

    name: str = "default"
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_probe_count: int = 3
    backoff_multiplier: float = 2.0
    max_recovery_timeout: float = 300.0  # 5 minutes

    # ── Internal state ────────────────────────────────────────────────────────

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = field(default=0, repr=False)
    probe_successes: int = field(default=0, repr=False)
    probe_failures: int = field(default=0, repr=False)
    last_failure_time: float = field(default=0.0, repr=False)
    last_success_time: float = field(default=0.0, repr=False)
    trip_count: int = field(default=0, repr=False)
    open_since: float = field(default=0.0, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be >= 1, got {self.failure_threshold}"
            )
        if self.recovery_timeout <= 0:
            raise ValueError(
                f"recovery_timeout must be positive, got {self.recovery_timeout}"
            )

    # ── Core API ──────────────────────────────────────────────────────────────

    def allow_request(self) -> bool:
        """Check whether a request should be allowed through.

        Returns True if the request can proceed, False if it should be
        rejected (circuit is OPEN or HALF_OPEN probe quota exhausted).
        """
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                timeout = self._current_recovery_timeout()
                if time.monotonic() - self.open_since >= timeout:
                    self._transition_to_half_open()
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                total_probes = self.probe_successes + self.probe_failures
                return total_probes < self.half_open_probe_count

            return False  # unreachable, defensive

    def record_success(self) -> None:
        """Record a successful request.

        In CLOSED state, resets the failure counter.
        In HALF_OPEN state, increments probe success counter and possibly
        transitions back to CLOSED.
        """
        with self.lock:
            self.last_success_time = time.monotonic()

            if self.state == CircuitState.CLOSED:
                self.failure_count = 0

            elif self.state == CircuitState.HALF_OPEN:
                self.probe_successes += 1
                if self.probe_successes >= self.half_open_probe_count:
                    self._transition_to_closed()

    def record_failure(self) -> None:
        """Record a failed request.

        In CLOSED state, increments the failure counter and may trip to OPEN.
        In HALF_OPEN state, records a probe failure and re-opens the circuit.
        """
        with self.lock:
            self.last_failure_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                self.probe_failures += 1
                self._transition_to_open()

            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    self._transition_to_open()

    # ── Call wrapper ──────────────────────────────────────────────────────────

    def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute ``func(*args, **kwargs)`` protected by the circuit breaker.

        If the circuit is OPEN, raises CircuitOpenError immediately.
        Otherwise, calls ``func``.  On success, records it.  On exception,
        records failure and re-raises.

        Args:
            func: The callable to protect.
            *args: Positional arguments forwarded to func.
            **kwargs: Keyword arguments forwarded to func.

        Returns:
            The return value of ``func``.

        Raises:
            CircuitOpenError: If the circuit is OPEN.
            Exception: Any exception raised by ``func`` (re-raised after
                       recording the failure).
        """
        if not self.allow_request():
            timeout = self._current_recovery_timeout()
            raise CircuitOpenError(
                circuit_name=self.name,
                opened_at=self.open_since,
                retry_after=timeout,
            )

        try:
            result = func(*args, **kwargs)
        except Exception:
            self.record_failure()
            raise
        else:
            self.record_success()
            return result

    # ── State queries ─────────────────────────────────────────────────────────

    def is_open(self) -> bool:
        """Return True if the circuit is currently OPEN (fast-failing)."""
        with self.lock:
            if self.state != CircuitState.OPEN:
                return False
            timeout = self._current_recovery_timeout()
            return (time.monotonic() - self.open_since) < timeout

    def is_closed(self) -> bool:
        """Return True if the circuit is CLOSED (normal operation)."""
        return self.state == CircuitState.CLOSED

    def is_half_open(self) -> bool:
        """Return True if the circuit is in HALF_OPEN (probing)."""
        return self.state == CircuitState.HALF_OPEN

    def retry_after(self) -> float:
        """Seconds until the circuit will transition to HALF_OPEN (0 if not OPEN)."""
        with self.lock:
            if self.state != CircuitState.OPEN:
                return 0.0
            elapsed = time.monotonic() - self.open_since
            timeout = self._current_recovery_timeout()
            return max(0.0, timeout - elapsed)

    # ── Manual control ────────────────────────────────────────────────────────

    def trip(self) -> None:
        """Manually trip the circuit to OPEN."""
        with self.lock:
            self._transition_to_open()

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED and clear all counters."""
        with self.lock:
            self._transition_to_closed()

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for this circuit."""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.name,
                "failure_count": self.failure_count,
                "trip_count": self.trip_count,
                "last_failure_time": self.last_failure_time,
                "last_success_time": self.last_success_time,
                "open_since": self.open_since,
                "retry_after": self.retry_after(),
                "probe_successes": self.probe_successes,
                "probe_failures": self.probe_failures,
            }

    # ── State transitions (must be called under lock) ─────────────────────────

    def _transition_to_open(self) -> None:
        """Transition to OPEN, incrementing the trip counter."""
        self.state = CircuitState.OPEN
        self.open_since = time.monotonic()
        self.trip_count += 1
        self.failure_count = 0
        self.probe_successes = 0
        self.probe_failures = 0

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN, resetting probe counters."""
        self.state = CircuitState.HALF_OPEN
        self.probe_successes = 0
        self.probe_failures = 0

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED, resetting all counters."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.probe_successes = 0
        self.probe_failures = 0

    def _current_recovery_timeout(self) -> float:
        """Calculate recovery timeout with exponential backoff.

        After ``trip_count`` trips, the timeout is:
            recovery_timeout * (backoff_multiplier ^ (trip_count - 1))

        Capped at ``max_recovery_timeout``.
        """
        if self.trip_count <= 1:
            return self.recovery_timeout
        backoff = self.recovery_timeout * (self.backoff_multiplier ** (self.trip_count - 1))
        return min(backoff, self.max_recovery_timeout)
