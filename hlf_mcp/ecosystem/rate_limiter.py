"""
Token-Bucket Rate Limiter — production-grade request throttling for HLF ecosystem bridges.

Provides configurable rate and burst limits with per-effect and global scoping,
thread-safe token consumption, and standard X-RateLimit-* response headers.

Integration points:
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (pre-tool-call throttling)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (middleware rate enforcement)
  - hlf_mcp.hlf.typed_contracts.EffectClass (per-effect rate limiting)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# TokenBucket — single-bucket rate limiter
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TokenBucket:
    """Thread-safe token-bucket rate limiter.

    Tokens refill at a constant ``rate`` (tokens/second) up to a maximum
    ``burst`` capacity.  Each ``consume()`` call drains ``cost`` tokens
    and returns whether the request is allowed.

    Attributes:
        rate: Sustained token refill rate in tokens/second.
        burst: Maximum token capacity (bucket size, also the burst limit).
        tokens: Current token count in the bucket.
        last_refill: Monotonic timestamp of the last refill operation.
        total_consumed: Lifetime tokens consumed (for monitoring).
        total_rejected: Lifetime requests rejected (for monitoring).
        lock: Reentrant lock for thread safety.
    """

    rate: float
    burst: float
    tokens: float = field(init=False)
    last_refill: float = field(default_factory=time.monotonic)
    total_consumed: int = field(default=0)
    total_rejected: int = field(default=0)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        """Start with a full bucket."""
        self.tokens = float(self.burst)
        if self.rate <= 0:
            raise ValueError(f"rate must be positive, got {self.rate}")
        if self.burst <= 0:
            raise ValueError(f"burst must be positive, got {self.burst}")

    # ── Core API ──────────────────────────────────────────────────────────────

    def consume(self, cost: float = 1.0) -> bool:
        """Attempt to consume ``cost`` tokens.

        Returns True if the request is allowed (enough tokens available),
        False if rate-limited.

        Side effect: refills tokens based on elapsed time before checking.
        """
        with self.lock:
            self._refill()
            if self.tokens >= cost:
                self.tokens -= cost
                self.total_consumed += 1
                return True
            self.total_rejected += 1
            return False

    def try_consume(self, cost: float = 1.0, timeout: float = 0.0) -> bool:
        """Attempt to consume tokens, optionally waiting up to ``timeout`` seconds.

        If ``timeout`` is 0, behaves identically to ``consume()``.
        If ``timeout`` > 0, blocks until tokens are available or timeout expires.
        """
        if timeout <= 0:
            return self.consume(cost)

        deadline = time.monotonic() + timeout
        while True:
            with self.lock:
                self._refill()
                if self.tokens >= cost:
                    self.tokens -= cost
                    self.total_consumed += 1
                    return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self.lock:
                    self.total_rejected += 1
                return False
            # Sleep a fraction of the time needed to accumulate cost tokens
            sleep_time = min(remaining, max(0.01, cost / self.rate * 0.5))
            time.sleep(sleep_time)

    # ── State queries ─────────────────────────────────────────────────────────

    def available_tokens(self) -> float:
        """Return the current token count (approximate, non-blocking)."""
        with self.lock:
            self._refill()
            return self.tokens

    def is_available(self, cost: float = 1.0) -> bool:
        """Check whether ``cost`` tokens are available without consuming."""
        with self.lock:
            self._refill()
            return self.tokens >= cost

    def reset(self) -> None:
        """Refill the bucket to full capacity and reset counters."""
        with self.lock:
            self.tokens = float(self.burst)
            self.last_refill = time.monotonic()
            self.total_consumed = 0
            self.total_rejected = 0

    # ── Rate-limit headers ────────────────────────────────────────────────────

    def rate_limit_headers(self, cost: float = 1.0) -> dict[str, str]:
        """Produce standard X-RateLimit-* response headers."""
        with self.lock:
            self._refill()
            remaining = int(self.tokens)
            reset_at = int(self.last_refill + (self.burst - self.tokens) / self.rate) if self.rate > 0 else 0
        return {
            "X-RateLimit-Limit": str(int(self.burst)),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(reset_at),
            "X-RateLimit-Cost": str(int(cost)),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill.

        Must be called under lock.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        if elapsed > 0:
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter — multi-scope rate limiter (global + per-effect)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RateLimiter:
    """Composite rate limiter with global and per-effect scoping.

    A global bucket enforces overall throughput, while per-effect buckets
    (keyed by EffectClass value strings) enforce per-operation limits.

    Usage:
        rl = RateLimiter(global_rate=100, global_burst=200)
        rl.add_effect_limit("file_read", rate=20, burst=50)
        if rl.consume("file_read", cost=1.0):
            ...  # proceed
        headers = rl.headers("file_read")  # for response

    Attributes:
        global_bucket: The global TokenBucket instance.
        effect_buckets: Per-effect TokenBucket instances keyed by name.
    """

    global_bucket: TokenBucket
    effect_buckets: dict[str, TokenBucket] = field(default_factory=dict)

    def __init__(
        self,
        global_rate: float = 100.0,
        global_burst: float = 200.0,
        effect_buckets: dict[str, TokenBucket] | None = None,
    ) -> None:
        """Initialize with global limits and optional per-effect buckets."""
        self.global_bucket = TokenBucket(rate=global_rate, burst=global_burst)
        self.effect_buckets = effect_buckets or {}

    # ── Management ────────────────────────────────────────────────────────────

    def add_effect_limit(self, name: str, rate: float, burst: float) -> TokenBucket:
        """Register a per-effect rate limit.

        Args:
            name: Effect name (e.g., "file_read", "web_search").
            rate: Sustained token refill rate for this effect.
            burst: Burst capacity for this effect.

        Returns:
            The newly created TokenBucket.
        """
        bucket = TokenBucket(rate=rate, burst=burst)
        self.effect_buckets[name] = bucket
        return bucket

    def remove_effect_limit(self, name: str) -> None:
        """Remove a per-effect rate limit."""
        self.effect_buckets.pop(name, None)

    # ── Consumption ───────────────────────────────────────────────────────────

    def consume(self, effect: str, cost: float = 1.0) -> bool:
        """Attempt to consume tokens from both global and per-effect buckets.

        Returns True only if BOTH the global bucket AND the effect bucket
        (if registered) have sufficient tokens.

        Args:
            effect: Effect name (e.g., "file_read", "web_search").
            cost: Token cost for this request.
        """
        # Check per-effect bucket first (faster rejection)
        effect_bucket = self.effect_buckets.get(effect)
        if effect_bucket is not None and not effect_bucket.is_available(cost):
            effect_bucket.total_rejected += 1
            self.global_bucket.total_rejected += 1
            return False

        # Check global bucket
        if not self.global_bucket.is_available(cost):
            self.global_bucket.total_rejected += 1
            return False

        # Consume from both
        self.global_bucket.consume(cost)
        if effect_bucket is not None:
            effect_bucket.consume(cost)
        return True

    # ── Headers ───────────────────────────────────────────────────────────────

    def headers(self, effect: str | None = None, cost: float = 1.0) -> dict[str, str]:
        """Produce combined rate-limit headers for a response.

        Merges global headers with per-effect headers when an effect is specified.
        """
        hdrs: dict[str, str] = {}
        # Global headers
        gh = self.global_bucket.rate_limit_headers(cost)
        hdrs.update(gh)
        # Per-effect headers
        if effect is not None:
            eb = self.effect_buckets.get(effect)
            if eb is not None:
                eh = eb.rate_limit_headers(cost)
                for k, v in eh.items():
                    hdrs[f"{k}-PerEffect"] = v
        return hdrs

    # ── State ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset all buckets to full capacity."""
        self.global_bucket.reset()
        for bucket in self.effect_buckets.values():
            bucket.reset()

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for all buckets."""
        result: dict[str, Any] = {
            "global": {
                "rate": self.global_bucket.rate,
                "burst": self.global_bucket.burst,
                "tokens": self.global_bucket.available_tokens(),
                "consumed": self.global_bucket.total_consumed,
                "rejected": self.global_bucket.total_rejected,
            },
        }
        for name, bucket in self.effect_buckets.items():
            result[name] = {
                "rate": bucket.rate,
                "burst": bucket.burst,
                "tokens": bucket.available_tokens(),
                "consumed": bucket.total_consumed,
                "rejected": bucket.total_rejected,
            }
        return result
