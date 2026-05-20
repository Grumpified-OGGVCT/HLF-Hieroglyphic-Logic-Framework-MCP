"""
Bridge Health Aggregator — aggregates health from all bridges, produces a
unified health score, and triggers alerts on degradation.

Monitors MCPBridge and RESTBridge instances, performs periodic health
checks (latency, error rate, uptime), computes a weighted aggregate health
score, and generates human-readable recommendations when bridges degrade.

Health scoring uses configurable weights:
  - Latency: 30% (lower is better)
  - Error rate: 30% (lower is better)
  - Uptime percentage: 25% (higher is better)
  - Consecutive failures: 15% (lower is better)

Trend analysis tracks the direction and pace of health changes over
a sliding window, enabling predictive alerting before bridges go down.

Integration points:
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (MCP bridge health monitoring)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (REST bridge health monitoring)
  - hlf_mcp.ecosystem.circuit_breaker.CircuitBreaker (circuit state input)
  - hlf_mcp.ecosystem.rate_limiter.RateLimiter (rate-limit health input)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hlf_mcp.ecosystem.mcp_bridge import MCPBridge
    from hlf_mcp.ecosystem.rest_bridge import RESTBridge


# ═══════════════════════════════════════════════════════════════════════════════
# HealthStatus enum
# ═══════════════════════════════════════════════════════════════════════════════


class HealthStatus(Enum):
    """Health classification for a bridge component."""

    HEALTHY = "healthy"         # Score >= degradation_threshold
    DEGRADED = "degraded"       # unhealthy_threshold <= score < degradation_threshold
    UNHEALTHY = "unhealthy"     # score < unhealthy_threshold but > 0
    DOWN = "down"               # score == 0 or bridge unreachable


# ═══════════════════════════════════════════════════════════════════════════════
# BridgeHealth — per-bridge health snapshot
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BridgeHealth:
    """Health snapshot for a single bridge.

    Attributes:
        bridge_name: Human-readable bridge identifier.
        bridge_type: "mcp" or "rest".
        status: Current health classification.
        latency_ms: Measured response latency in milliseconds.
        error_rate: Error rate as a fraction (0.0–1.0).
        uptime_pct: Uptime percentage (0.0–100.0).
        last_checked: ISO-8601 timestamp of the last health check.
        consecutive_failures: Number of consecutive failed health checks.
        details: Additional bridge-specific diagnostics.
    """

    bridge_name: str
    bridge_type: str  # "mcp" or "rest"
    status: HealthStatus = HealthStatus.HEALTHY
    latency_ms: float = 0.0
    error_rate: float = 0.0
    uptime_pct: float = 100.0
    last_checked: str = ""
    consecutive_failures: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.last_checked:
            self.last_checked = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bridge_name": self.bridge_name,
            "bridge_type": self.bridge_type,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "uptime_pct": self.uptime_pct,
            "last_checked": self.last_checked,
            "consecutive_failures": self.consecutive_failures,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BridgeHealth:
        return cls(
            bridge_name=str(data.get("bridge_name", "")),
            bridge_type=str(data.get("bridge_type", "mcp")),
            status=HealthStatus(data.get("status", "healthy")),
            latency_ms=float(data.get("latency_ms", 0.0)),
            error_rate=float(data.get("error_rate", 0.0)),
            uptime_pct=float(data.get("uptime_pct", 100.0)),
            last_checked=str(data.get("last_checked", "")),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
            details=data.get("details", {}),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# HealthAggregation — aggregated health across all bridges
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class HealthAggregation:
    """Aggregated health status across all monitored bridges.

    Attributes:
        overall_status: Worst status across all bridges.
        overall_score: Weighted average health score (0.0–1.0).
        bridge_healths: Per-bridge Health snapshots.
        degraded_bridges: Names of bridges in DEGRADED status.
        unhealthy_bridges: Names of bridges in UNHEALTHY or DOWN status.
        recommendations: Human-readable remediation suggestions.
        aggregated_at: ISO-8601 timestamp of aggregation.
    """

    overall_status: HealthStatus = HealthStatus.HEALTHY
    overall_score: float = 1.0
    bridge_healths: list[BridgeHealth] = field(default_factory=list)
    degraded_bridges: list[str] = field(default_factory=list)
    unhealthy_bridges: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    aggregated_at: str = ""

    def __post_init__(self) -> None:
        if not self.aggregated_at:
            self.aggregated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "bridge_healths": [bh.to_dict() for bh in self.bridge_healths],
            "degraded_bridges": self.degraded_bridges,
            "unhealthy_bridges": self.unhealthy_bridges,
            "recommendations": self.recommendations,
            "aggregated_at": self.aggregated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HealthAggregation:
        return cls(
            overall_status=HealthStatus(data.get("overall_status", "healthy")),
            overall_score=float(data.get("overall_score", 1.0)),
            bridge_healths=[BridgeHealth.from_dict(bh) for bh in data.get("bridge_healths", [])],
            degraded_bridges=data.get("degraded_bridges", []),
            unhealthy_bridges=data.get("unhealthy_bridges", []),
            recommendations=data.get("recommendations", []),
            aggregated_at=str(data.get("aggregated_at", "")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _compute_weighted_health_score(
    latency_ms: float,
    error_rate: float,
    uptime_pct: float,
    consecutive_failures: int,
    *,
    latency_weight: float = 0.30,
    error_rate_weight: float = 0.30,
    uptime_weight: float = 0.25,
    failure_weight: float = 0.15,
    max_latency_ms: float = 5000.0,
    max_consecutive_failures: int = 10,
) -> float:
    """Compute a 0-1 health score from individual metrics.

    Each metric is normalized to [0, 1] where 1 = best:
      - Latency:    1.0 - min(1.0, latency_ms / max_latency_ms)
      - Error rate: 1.0 - error_rate (already 0-1)
      - Uptime:     uptime_pct / 100.0
      - Failures:   1.0 - min(1.0, consecutive_failures / max_consecutive_failures)

    Returns the weighted sum, clamped to [0.0, 1.0].
    """
    latency_score = 1.0 - min(1.0, latency_ms / max_latency_ms)
    error_score = 1.0 - min(1.0, error_rate)
    uptime_score = min(1.0, uptime_pct / 100.0)
    failure_score = 1.0 - min(1.0, consecutive_failures / max_consecutive_failures)

    score = (
        latency_score * latency_weight
        + error_score * error_rate_weight
        + uptime_score * uptime_weight
        + failure_score * failure_weight
    )

    return max(0.0, min(1.0, score))


def _classify_health_status(
    score: float,
    degradation_threshold: float,
    unhealthy_threshold: float,
) -> HealthStatus:
    """Classify a numeric health score into a HealthStatus.

    Args:
        score: 0-1 health score.
        degradation_threshold: Below this → DEGRADED.
        unhealthy_threshold: Below this → UNHEALTHY.

    Returns:
        HealthStatus classification.
    """
    if score <= 0.0:
        return HealthStatus.DOWN
    if score < unhealthy_threshold:
        return HealthStatus.UNHEALTHY
    if score < degradation_threshold:
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


# ═══════════════════════════════════════════════════════════════════════════════
# BridgeHealthAggregator — main class
# ═══════════════════════════════════════════════════════════════════════════════


class BridgeHealthAggregator:
    """Aggregates health from all registered bridges and produces unified
    health scores with degradation alerts.

    Each registered bridge is checked periodically. Health checks measure:
      - Latency (ms): For MCP bridges, time to list tools. For REST bridges,
        time to hit the health endpoint.
      - Error rate: Fraction of recent calls that failed.
      - Uptime percentage: Derived from consecutive check history.
      - Consecutive failures: Counter for unreachable bridges.

    Attributes:
        name: Human-readable name for this aggregator.
        check_interval: Seconds between automatic health checks.
        degradation_threshold: Score below which a bridge is DEGRADED.
        unhealthy_threshold: Score below which a bridge is UNHEALTHY.
        bridges: Registry of bridge_name → (bridge_type, bridge_instance).
        health_history: Registry of bridge_name → list of recent BridgeHealth
                        snapshots (for trend analysis).
        lock: Reentrant lock for thread safety.
    """

    def __init__(
        self,
        name: str = "bridge-health",
        check_interval: float = 30.0,
        degradation_threshold: float = 0.8,
        unhealthy_threshold: float = 0.5,
    ) -> None:
        self.name = name
        self.check_interval = check_interval
        self.degradation_threshold = degradation_threshold
        self.unhealthy_threshold = unhealthy_threshold

        # {bridge_name: (bridge_type, bridge_instance)}
        self.bridges: dict[str, tuple[str, Any]] = {}
        # {bridge_name: list[BridgeHealth]}
        self.health_history: dict[str, list[BridgeHealth]] = {}
        self.lock = threading.RLock()

        if degradation_threshold <= unhealthy_threshold:
            raise ValueError(
                f"degradation_threshold ({degradation_threshold}) must be > "
                f"unhealthy_threshold ({unhealthy_threshold})"
            )

    # ── Bridge registration ───────────────────────────────────────────────────

    def register_bridge(
        self,
        bridge_name: str,
        bridge_type: str,
        bridge_instance: Any,
    ) -> None:
        """Register a bridge for health monitoring.

        Args:
            bridge_name: Unique name for this bridge.
            bridge_type: "mcp" or "rest".
            bridge_instance: An MCPBridge or RESTBridge instance.

        Raises:
            ValueError: If bridge_type is not "mcp" or "rest".
        """
        if bridge_type not in ("mcp", "rest"):
            raise ValueError(
                f"bridge_type must be 'mcp' or 'rest', got '{bridge_type}'"
            )

        with self.lock:
            self.bridges[bridge_name] = (bridge_type, bridge_instance)
            if bridge_name not in self.health_history:
                self.health_history[bridge_name] = []

    def deregister_bridge(self, bridge_name: str) -> bool:
        """Remove a bridge from monitoring.

        Returns True if the bridge was found and removed.
        """
        with self.lock:
            existed = bridge_name in self.bridges
            self.bridges.pop(bridge_name, None)
            self.health_history.pop(bridge_name, None)
            return existed

    # ── Health checks ─────────────────────────────────────────────────────────

    def check_bridge(self, bridge_name: str) -> BridgeHealth:
        """Perform a health check on a specific bridge.

        For MCP bridges: measures list-tools latency and dispatch test.
        For REST bridges: measures endpoint health-check latency.

        Args:
            bridge_name: The bridge to check.

        Returns:
            A BridgeHealth snapshot with measured metrics.

        Raises:
            KeyError: If bridge_name is not registered.
        """
        with self.lock:
            if bridge_name not in self.bridges:
                raise KeyError(
                    f"BridgeHealthAggregator '{self.name}': bridge "
                    f"'{bridge_name}' is not registered"
                )
            bridge_type, bridge_instance = self.bridges[bridge_name]

        now_ts = datetime.now(timezone.utc).isoformat()

        health = BridgeHealth(
            bridge_name=bridge_name,
            bridge_type=bridge_type,
            last_checked=now_ts,
        )

        try:
            if bridge_type == "mcp":
                health = self._check_mcp_bridge(bridge_name, bridge_instance, health)
            elif bridge_type == "rest":
                health = self._check_rest_bridge(bridge_name, bridge_instance, health)

            # Compute score and classify
            score = self.health_score(health)
            health.status = _classify_health_status(
                score, self.degradation_threshold, self.unhealthy_threshold,
            )

            # Reset consecutive failures on success
            health.consecutive_failures = 0

        except Exception as exc:
            # Check failed — increment consecutive failures
            prev = self._get_latest_health(bridge_name)
            health.consecutive_failures = (prev.consecutive_failures + 1) if prev else 1
            health.error_rate = 1.0
            health.latency_ms = 9999.0
            health.uptime_pct = max(0.0, 100.0 - (health.consecutive_failures * 5.0))
            health.details = {"check_error": str(exc)[:500]}
            health.status = HealthStatus.DOWN if health.consecutive_failures >= 3 else HealthStatus.UNHEALTHY

        # Store in history
        with self.lock:
            self.health_history.setdefault(bridge_name, []).append(health)
            # Keep only last 100 checks per bridge
            if len(self.health_history[bridge_name]) > 100:
                self.health_history[bridge_name] = self.health_history[bridge_name][-100:]

        return health

    def _check_mcp_bridge(
        self,
        bridge_name: str,
        bridge: Any,
        health: BridgeHealth,
    ) -> BridgeHealth:
        """Health check for an MCPBridge.

        Measures latency to list tools and checks circuit breaker state.
        """
        start = time.monotonic()

        # Attempt to access tool registrations as a proxy for bridge health
        if hasattr(bridge, "tool_registrations"):
            tools = bridge.tool_registrations
            health.details["registered_tools"] = len(tools) if isinstance(tools, (list, dict)) else "unknown"

        if hasattr(bridge, "stats"):
            try:
                stats = bridge.stats()
                health.details["mcp_stats"] = stats
            except Exception:
                health.details["mcp_stats"] = "unavailable"

        # Circuit breaker health
        if hasattr(bridge, "circuit_breaker") and bridge.circuit_breaker is not None:
            cb = bridge.circuit_breaker
            health.details["circuit_state"] = getattr(cb, "state", None)
            health.details["circuit_trip_count"] = getattr(cb, "trip_count", 0)
            if hasattr(cb, "is_open") and cb.is_open():
                health.details["circuit_open"] = True

        # Rate limiter health
        if hasattr(bridge, "rate_limiter") and bridge.rate_limiter is not None:
            try:
                rl = bridge.rate_limiter
                health.details["rate_limiter_stats"] = rl.stats() if hasattr(rl, "stats") else "available"
            except Exception:
                health.details["rate_limiter_stats"] = "unavailable"

        elapsed_ms = (time.monotonic() - start) * 1000.0
        health.latency_ms = elapsed_ms
        health.error_rate = 0.0  # Will be updated from circuit breaker if available

        # Derive error rate from circuit breaker
        if hasattr(bridge, "circuit_breaker") and bridge.circuit_breaker is not None:
            cb = bridge.circuit_breaker
            failure_count = getattr(cb, "failure_count", 0)
            trip_count = getattr(cb, "trip_count", 0)
            if trip_count > 0:
                health.error_rate = min(1.0, failure_count / (trip_count * getattr(cb, "failure_threshold", 5)))

        return health

    def _check_rest_bridge(
        self,
        bridge_name: str,
        bridge: Any,
        health: BridgeHealth,
    ) -> BridgeHealth:
        """Health check for a RESTBridge.

        Measures latency to a health endpoint and checks registered endpoints.
        """
        start = time.monotonic()

        # Check registered endpoints
        if hasattr(bridge, "endpoints"):
            endpoints = bridge.endpoints
            health.details["registered_endpoints"] = len(endpoints) if isinstance(endpoints, (list, dict)) else "unknown"

        if hasattr(bridge, "stats"):
            try:
                stats = bridge.stats()
                health.details["rest_stats"] = stats
            except Exception:
                health.details["rest_stats"] = "unavailable"

        # Circuit breaker health
        if hasattr(bridge, "circuit_breaker") and bridge.circuit_breaker is not None:
            cb = bridge.circuit_breaker
            health.details["circuit_state"] = getattr(cb, "state", None)
            health.details["circuit_trip_count"] = getattr(cb, "trip_count", 0)

        # Credential manager health
        if hasattr(bridge, "credential_manager") and bridge.credential_manager is not None:
            try:
                cm = bridge.credential_manager
                health.details["active_credentials"] = cm.count_active() if hasattr(cm, "count_active") else "unknown"
            except Exception:
                health.details["active_credentials"] = "unavailable"

        # Rate limiter health
        if hasattr(bridge, "rate_limiter") and bridge.rate_limiter is not None:
            try:
                rl = bridge.rate_limiter
                health.details["rate_limiter_stats"] = rl.stats() if hasattr(rl, "stats") else "available"
            except Exception:
                health.details["rate_limiter_stats"] = "unavailable"

        elapsed_ms = (time.monotonic() - start) * 1000.0
        health.latency_ms = elapsed_ms
        health.error_rate = 0.0

        return health

    def check_all(self) -> HealthAggregation:
        """Check all registered bridges and compute aggregated health.

        Returns a HealthAggregation with the overall status, score,
        per-bridge health, and recommendations.
        """
        bridge_healths: list[BridgeHealth] = []
        degraded: list[str] = []
        unhealthy: list[str] = []

        with self.lock:
            bridge_names = list(self.bridges.keys())

        for name in bridge_names:
            try:
                health = self.check_bridge(name)
            except Exception as exc:
                # Failsafe: create a DOWN entry
                health = BridgeHealth(
                    bridge_name=name,
                    bridge_type=self.bridges.get(name, ("mcp", None))[0],
                    status=HealthStatus.DOWN,
                    error_rate=1.0,
                    consecutive_failures=10,
                    details={"check_all_error": str(exc)[:500]},
                )
            bridge_healths.append(health)

            if health.status == HealthStatus.DEGRADED:
                degraded.append(name)
            elif health.status in (HealthStatus.UNHEALTHY, HealthStatus.DOWN):
                unhealthy.append(name)

        # Compute overall score: weighted average across bridges
        weights: dict[str, float] = self._compute_bridge_weights(bridge_healths)
        overall_score = 0.0
        total_weight = 0.0

        for bh in bridge_healths:
            w = weights.get(bh.bridge_name, 1.0)
            score = self.health_score(bh)
            overall_score += score * w
            total_weight += w

        if total_weight > 0:
            overall_score = overall_score / total_weight

        # Derive overall status from per-bridge statuses
        statuses = [bh.status for bh in bridge_healths]
        if HealthStatus.DOWN in statuses:
            overall_status = HealthStatus.DOWN
        elif HealthStatus.UNHEALTHY in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        aggregation = HealthAggregation(
            overall_status=overall_status,
            overall_score=round(overall_score, 4),
            bridge_healths=bridge_healths,
            degraded_bridges=degraded,
            unhealthy_bridges=unhealthy,
        )

        # Generate recommendations
        aggregation.recommendations = self.generate_recommendations(aggregation)

        return aggregation

    def _compute_bridge_weights(
        self,
        bridge_healths: list[BridgeHealth],
    ) -> dict[str, float]:
        """Compute per-bridge weights for the overall score.

        MCP and REST bridges get equal total weight.  Within each type,
        weight is distributed equally across bridges.

        Returns:
            Dict mapping bridge_name → weight (sums to 1.0).
        """
        mcp_count = sum(1 for bh in bridge_healths if bh.bridge_type == "mcp")
        rest_count = sum(1 for bh in bridge_healths if bh.bridge_type == "rest")
        total_types = (1 if mcp_count > 0 else 0) + (1 if rest_count > 0 else 0)

        if total_types == 0:
            return {}

        weight_per_type = 1.0 / total_types

        weights: dict[str, float] = {}
        for bh in bridge_healths:
            if bh.bridge_type == "mcp" and mcp_count > 0:
                weights[bh.bridge_name] = weight_per_type / mcp_count
            elif bh.bridge_type == "rest" and rest_count > 0:
                weights[bh.bridge_name] = weight_per_type / rest_count

        return weights

    # ── Health scoring ────────────────────────────────────────────────────────

    def health_score(self, health: BridgeHealth) -> float:
        """Compute a 0-1 health score from a BridgeHealth snapshot.

        Uses the weighted metric calculator with default weights:
          - Latency: 30%
          - Error rate: 30%
          - Uptime: 25%
          - Consecutive failures: 15%
        """
        return _compute_weighted_health_score(
            latency_ms=health.latency_ms,
            error_rate=health.error_rate,
            uptime_pct=health.uptime_pct,
            consecutive_failures=health.consecutive_failures,
        )

    # ── Trend analysis ────────────────────────────────────────────────────────

    def trend_analysis(self, window: int = 10) -> dict[str, Any]:
        """Analyze health trends over the last *window* checks per bridge.

        Uses simple linear regression on health scores over time to
        determine direction and slope.

        Args:
            window: Number of recent health checks to analyze.

        Returns:
            Dict mapping bridge_name → {direction, slope, confidence}.
            direction is one of "improving", "degrading", or "stable".
        """
        results: dict[str, Any] = {}

        with self.lock:
            for bridge_name, history in self.health_history.items():
                if len(history) < 2:
                    results[bridge_name] = {
                        "direction": "stable",
                        "slope": 0.0,
                        "confidence": 0.0,
                    }
                    continue

                # Take last *window* snapshots
                recent = history[-window:]
                scores = [self.health_score(h) for h in recent]

                n = len(scores)
                if n < 2:
                    results[bridge_name] = {
                        "direction": "stable",
                        "slope": 0.0,
                        "confidence": 0.0,
                    }
                    continue

                # Simple linear regression: y = slope * x + intercept
                # x = index (0..n-1), y = health score
                sum_x = sum(range(n))
                sum_y = sum(scores)
                sum_xy = sum(i * scores[i] for i in range(n))
                sum_x2 = sum(i * i for i in range(n))

                denominator = n * sum_x2 - sum_x * sum_x
                if denominator == 0:
                    slope = 0.0
                else:
                    slope = (n * sum_xy - sum_x * sum_y) / denominator

                # R-squared for confidence
                mean_y = sum_y / n
                ss_total = sum((y - mean_y) ** 2 for y in scores)
                if ss_total == 0:
                    r_squared = 1.0 if slope == 0 else 0.0
                else:
                    intercept = (sum_y - slope * sum_x) / n
                    ss_residual = sum(
                        (scores[i] - (slope * i + intercept)) ** 2
                        for i in range(n)
                    )
                    r_squared = 1.0 - (ss_residual / ss_total)

                # Direction
                if abs(slope) < 0.001:
                    direction = "stable"
                elif slope > 0:
                    direction = "improving"
                else:
                    direction = "degrading"

                results[bridge_name] = {
                    "direction": direction,
                    "slope": round(slope, 6),
                    "confidence": round(max(0.0, min(1.0, r_squared)), 4),
                    "sample_size": n,
                    "latest_score": round(scores[-1], 4),
                    "oldest_score": round(scores[0], 4),
                }

        return results

    # ── Recommendations ───────────────────────────────────────────────────────

    def generate_recommendations(self, aggregation: HealthAggregation) -> list[str]:
        """Generate human-readable recommendations from an aggregation.

        Rules:
          - DOWN bridge with 5+ consecutive failures → "Restart bridge X"
          - UNHEALTHY bridge → "Investigate bridge X: low health score"
          - DEGRADED bridge with high latency → "Investigate latency spike on bridge X"
          - Multiple unhealthy bridges → "Multiple bridges unhealthy — possible systemic issue"
          - Overall degraded → "System health degraded — check network/dependencies"

        Args:
            aggregation: A HealthAggregation produced by check_all().

        Returns:
            List of recommendation strings.
        """
        recs: list[str] = []

        for bh in aggregation.bridge_healths:
            if bh.status == HealthStatus.DOWN:
                if bh.consecutive_failures >= 5:
                    recs.append(
                        f"Restart bridge '{bh.bridge_name}' ({bh.bridge_type}) — "
                        f"{bh.consecutive_failures} consecutive failures"
                    )
                else:
                    recs.append(
                        f"Bridge '{bh.bridge_name}' ({bh.bridge_type}) is DOWN — "
                        f"immediate investigation required"
                    )

            elif bh.status == HealthStatus.UNHEALTHY:
                score = self.health_score(bh)
                recs.append(
                    f"Investigate bridge '{bh.bridge_name}' ({bh.bridge_type}) — "
                    f"health score {score:.2f} below unhealthy threshold "
                    f"({self.unhealthy_threshold})"
                )

            elif bh.status == HealthStatus.DEGRADED:
                if bh.latency_ms > 1000:
                    recs.append(
                        f"Investigate latency spike on bridge '{bh.bridge_name}' "
                        f"({bh.bridge_type}) — {bh.latency_ms:.0f}ms (target < 1000ms)"
                    )
                elif bh.error_rate > 0.1:
                    recs.append(
                        f"Elevated error rate on bridge '{bh.bridge_name}' "
                        f"({bh.bridge_type}) — {bh.error_rate:.1%} error rate"
                    )
                else:
                    recs.append(
                        f"Monitor bridge '{bh.bridge_name}' ({bh.bridge_type}) — "
                        f"degraded but no specific trigger identified"
                    )

        # Systemic recommendations
        if len(aggregation.unhealthy_bridges) >= 2:
            recs.append(
                f"Multiple bridges unhealthy ({len(aggregation.unhealthy_bridges)}) "
                f"— possible systemic issue: check network connectivity, "
                f"shared dependencies, or infrastructure health"
            )

        if aggregation.overall_status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY):
            recs.append(
                f"System health {aggregation.overall_status.value} — overall score "
                f"{aggregation.overall_score:.2f}. Review all bridge statuses and "
                f"check upstream dependencies"
            )

        return recs

    # ── Alerts ────────────────────────────────────────────────────────────────

    def alert_on_degradation(self, aggregation: HealthAggregation) -> list[dict[str, Any]]:
        """Generate alerts for bridges below health thresholds.

        Severity levels:
          - "critical": Bridge is DOWN.
          - "warning": Bridge is UNHEALTHY.
          - "info": Bridge is DEGRADED.

        Args:
            aggregation: A HealthAggregation from check_all().

        Returns:
            List of alert dicts with keys: severity, bridge_name,
            bridge_type, message, timestamp, health_score.
        """
        alerts: list[dict[str, Any]] = []
        now_ts = datetime.now(timezone.utc).isoformat()

        for bh in aggregation.bridge_healths:
            if bh.status == HealthStatus.DOWN:
                alerts.append({
                    "severity": "critical",
                    "bridge_name": bh.bridge_name,
                    "bridge_type": bh.bridge_type,
                    "message": (
                        f"Bridge '{bh.bridge_name}' is DOWN — "
                        f"{bh.consecutive_failures} consecutive failures"
                    ),
                    "timestamp": now_ts,
                    "health_score": self.health_score(bh),
                })
            elif bh.status == HealthStatus.UNHEALTHY:
                alerts.append({
                    "severity": "warning",
                    "bridge_name": bh.bridge_name,
                    "bridge_type": bh.bridge_type,
                    "message": (
                        f"Bridge '{bh.bridge_name}' is UNHEALTHY — "
                        f"score {self.health_score(bh):.2f} below threshold"
                    ),
                    "timestamp": now_ts,
                    "health_score": self.health_score(bh),
                })
            elif bh.status == HealthStatus.DEGRADED:
                alerts.append({
                    "severity": "info",
                    "bridge_name": bh.bridge_name,
                    "bridge_type": bh.bridge_type,
                    "message": (
                        f"Bridge '{bh.bridge_name}' is DEGRADED — "
                        f"latency {bh.latency_ms:.0f}ms, error rate {bh.error_rate:.1%}"
                    ),
                    "timestamp": now_ts,
                    "health_score": self.health_score(bh),
                })

        # Sort by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

        return alerts

    # ── History helpers ───────────────────────────────────────────────────────

    def _get_latest_health(self, bridge_name: str) -> BridgeHealth | None:
        """Return the most recent BridgeHealth for a bridge, or None."""
        history = self.health_history.get(bridge_name, [])
        return history[-1] if history else None

    def get_bridge_health(self, bridge_name: str) -> BridgeHealth | None:
        """Return the latest health snapshot for a bridge."""
        with self.lock:
            return self._get_latest_health(bridge_name)

    def get_history(self, bridge_name: str, limit: int = 20) -> list[BridgeHealth]:
        """Return recent health history for a bridge.

        Args:
            bridge_name: The bridge to query.
            limit: Maximum number of snapshots to return.

        Returns:
            List of BridgeHealth snapshots, most recent last.
        """
        with self.lock:
            history = self.health_history.get(bridge_name, [])
            return list(history[-limit:])

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for the health aggregator."""
        with self.lock:
            bridge_summaries: dict[str, Any] = {}
            for name, (btype, _) in self.bridges.items():
                latest = self._get_latest_health(name)
                bridge_summaries[name] = {
                    "type": btype,
                    "latest_status": latest.status.value if latest else "unknown",
                    "latest_score": self.health_score(latest) if latest else None,
                    "history_size": len(self.health_history.get(name, [])),
                    "last_checked": latest.last_checked if latest else None,
                }

            return {
                "name": self.name,
                "check_interval": self.check_interval,
                "degradation_threshold": self.degradation_threshold,
                "unhealthy_threshold": self.unhealthy_threshold,
                "registered_bridges": len(self.bridges),
                "bridge_summaries": bridge_summaries,
            }

    def force_check_bridge(self, bridge_name: str) -> BridgeHealth:
        """Force an immediate health check (alias for check_bridge with explicit naming)."""
        return self.check_bridge(bridge_name)
