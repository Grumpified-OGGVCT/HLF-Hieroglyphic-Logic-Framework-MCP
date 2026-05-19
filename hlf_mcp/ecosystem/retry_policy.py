"""
Retry Policy — exponential backoff with jitter, per-effect-class configuration,
and retry-budget tracking for HLF ecosystem bridges.

Design:
  - Exponential backoff: delay = base_delay * (2 ^ (attempt - 1)), capped.
  - Full jitter: actual_delay = random(0, delay) to avoid thundering herd.
  - Per-effect-class retry config: READ effects retry more aggressively;
    WRITE/MUTATING effects retry fewer times to avoid double-execution.
  - Retry budget: tracks total retries across a time window to prevent
    retry storms during widespread outages.

Integration points:
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (retry around tool calls)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (retry around endpoint handlers)
  - hlf_mcp.hlf.typed_contracts.EffectClass.is_mutating() (READ vs WRITE config)
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# RetryDecision — the outcome of a single retry evaluation
# ═══════════════════════════════════════════════════════════════════════════════


class RetryDecision(Enum):
    """Possible outcomes when evaluating whether to retry."""

    RETRY = auto()             # Proceed with retry after backoff
    MAX_RETRIES = auto()       # Exhausted maximum retry count
    BUDGET_EXHAUSTED = auto()  # Retry budget depleted
    NON_RETRYABLE = auto()     # Error is not retryable


# ═══════════════════════════════════════════════════════════════════════════════
# RetryPolicy — the core retry logic
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RetryPolicy:
    """Configurable retry policy with exponential backoff and jitter.

    Attributes:
        max_retries: Maximum number of retry attempts allowed per call.
        base_delay: Initial backoff delay in seconds.
        max_delay: Ceiling on backoff delay in seconds.
        jitter: If True, apply full jitter (random between 0 and computed delay).
                If False, use fixed exponential delay.
        retryable_exceptions: Tuple of exception types considered retryable.
                               If None, all exceptions are retryable.
        budget_window: Time window in seconds for retry budget tracking.
        max_budget: Maximum number of retries allowed within the budget window.
        budget_retries: List of monotonic timestamps for recent retries.
        lock: Reentrant lock for thread safety.
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = field(default_factory=tuple)
    budget_window: float = 60.0  # 1 minute
    max_budget: int = 100

    # ── Internal state ────────────────────────────────────────────────────────

    budget_retries: list[float] = field(default_factory=list, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")
        if self.base_delay <= 0:
            raise ValueError(f"base_delay must be positive, got {self.base_delay}")
        if self.max_delay < self.base_delay:
            raise ValueError(
                f"max_delay ({self.max_delay}) must be >= base_delay ({self.base_delay})"
            )

    # ── Core API ──────────────────────────────────────────────────────────────

    def should_retry(self, attempt: int, exception: Exception | None = None) -> RetryDecision:
        """Determine whether a retry should be attempted.

        Args:
            attempt: The current attempt number (1-based; attempt 1 is the
                     first retry after the initial call).
            exception: The exception that triggered the retry evaluation.
                       If provided, checked against retryable_exceptions.
        """
        # Check exception retryability
        if exception is not None and self.retryable_exceptions:
            if not isinstance(exception, self.retryable_exceptions):
                return RetryDecision.NON_RETRYABLE

        # Check max retries
        if attempt > self.max_retries:
            return RetryDecision.MAX_RETRIES

        # Check budget
        if not self._consume_budget():
            return RetryDecision.BUDGET_EXHAUSTED

        return RetryDecision.RETRY

    def backoff_delay(self, attempt: int) -> float:
        """Calculate the backoff delay for a given retry attempt.

        Uses exponential backoff: base_delay * 2^(attempt-1), capped at max_delay.
        When jitter is enabled, returns a random value between 0 and the
        computed delay (full jitter).

        Args:
            attempt: The current attempt number (1-based).
        """
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        if self.jitter and delay > 0:
            delay = random.uniform(0, delay)
        return delay

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute ``func`` with retry logic applied.

        Calls ``func(*args, **kwargs)``.  On exception, evaluates whether
        to retry based on the policy, waits for the backoff delay, and
        retries.  Re-raises the last exception if retries are exhausted.

        Args:
            func: The callable to execute with retries.
            *args: Positional arguments forwarded to func.
            **kwargs: Keyword arguments forwarded to func.

        Returns:
            The return value of ``func`` on success.

        Raises:
            Exception: The last exception raised by ``func`` after all
                       retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):  # 0 = initial call, 1+ = retries
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    break
                decision = self.should_retry(attempt + 1, exc)
                if decision == RetryDecision.RETRY:
                    delay = self.backoff_delay(attempt + 1)
                    time.sleep(delay)
                elif decision == RetryDecision.NON_RETRYABLE:
                    raise
                elif decision == RetryDecision.BUDGET_EXHAUSTED:
                    break
                elif decision == RetryDecision.MAX_RETRIES:
                    break

        # Exhausted all retries
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("RetryPolicy.execute: no result and no exception")  # defensive

    # ── Budget tracking ───────────────────────────────────────────────────────

    def _consume_budget(self) -> bool:
        """Attempt to consume one retry from the budget window.

        Returns True if budget allows another retry, False if exhausted.
        Must be called under lock.
        """
        with self.lock:
            self._prune_budget()
            if len(self.budget_retries) >= self.max_budget:
                return False
            self.budget_retries.append(time.monotonic())
            return True

    def _prune_budget(self) -> None:
        """Remove retry timestamps older than the budget window."""
        now = time.monotonic()
        cutoff = now - self.budget_window
        self.budget_retries = [t for t in self.budget_retries if t > cutoff]

    def remaining_budget(self) -> int:
        """Return the number of retries remaining in the budget window."""
        with self.lock:
            self._prune_budget()
            return max(0, self.max_budget - len(self.budget_retries))

    def reset_budget(self) -> None:
        """Clear the retry budget."""
        with self.lock:
            self.budget_retries.clear()

    # ── State queries ─────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics."""
        with self.lock:
            self._prune_budget()
            return {
                "max_retries": self.max_retries,
                "base_delay": self.base_delay,
                "max_delay": self.max_delay,
                "jitter": self.jitter,
                "budget_used": len(self.budget_retries),
                "budget_max": self.max_budget,
                "budget_remaining": self.max_budget - len(self.budget_retries),
                "budget_window": self.budget_window,
            }


# ═══════════════════════════════════════════════════════════════════════════════
# Per-effect-class retry configuration
# ═══════════════════════════════════════════════════════════════════════════════


# Retryable error types considered transient/recoverable
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# READ effects: safe to retry aggressively (no side effects)
READ_RETRY_POLICY = RetryPolicy(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
    jitter=True,
    retryable_exceptions=_RETRYABLE_EXCEPTIONS,
    budget_window=60.0,
    max_budget=200,
)

# WRITE/MUTATING effects: retry cautiously (risk of double-execution)
WRITE_RETRY_POLICY = RetryPolicy(
    max_retries=2,
    base_delay=1.0,
    max_delay=10.0,
    jitter=True,
    retryable_exceptions=_RETRYABLE_EXCEPTIONS,
    budget_window=60.0,
    max_budget=50,
)

# DEFAULT: balanced retry for effects with unclear category
DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    jitter=True,
    retryable_exceptions=_RETRYABLE_EXCEPTIONS,
    budget_window=60.0,
    max_budget=100,
)


def retry_policy_for_effect(effect_class_name: str) -> RetryPolicy:
    """Return the appropriate RetryPolicy for a given effect class.

    READ effects (file_read, network_read, memory_read, web_search,
    sensor_read, environment_read, world_state_read) get the READ policy
    with more aggressive retries.

    WRITE/MUTATING effects (file_write, network_write, memory_write,
    process_spawn, agent_delegation, guarded_actuation, safety_stop)
    get the WRITE policy with conservative retries.

    Args:
        effect_class_name: The effect class value string (e.g., "file_read").

    Returns:
        A RetryPolicy instance suitable for the effect class.
    """
    _read_effects: frozenset[str] = frozenset({
        "file_read", "network_read", "memory_read", "web_search",
        "sensor_read", "environment_read", "world_state_read",
        "embedding_generation", "model_inference",
        "multimodal_audio", "multimodal_ocr", "multimodal_video",
        "multimodal_vision", "local_analysis", "similarity_math",
        "token_transform", "cryptographic_hash", "verification",
        "formal_verification", "assertion", "timing", "route_selection",
    })
    _write_effects: frozenset[str] = frozenset({
        "file_write", "network_write", "memory_write",
        "process_spawn", "agent_delegation", "governance_vote",
        "merkle_append", "audit_log", "guarded_actuation",
        "trajectory_plan", "safety_stop",
    })

    if effect_class_name in _read_effects:
        return READ_RETRY_POLICY
    elif effect_class_name in _write_effects:
        return WRITE_RETRY_POLICY
    return DEFAULT_RETRY_POLICY
