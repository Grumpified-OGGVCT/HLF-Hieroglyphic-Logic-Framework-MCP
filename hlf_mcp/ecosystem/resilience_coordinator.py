"""
Resilience Coordinator — coordinates circuit breaker, credential rotation,
and retry policy into a unified resilience cascade.

When a failure occurs, the coordinator classifies it, then executes a
cascading response:
  - Auth failure → increment auth failure counter → if threshold exceeded
    → open circuit + rotate credentials (if policy allows)
  - Timeout → open circuit immediately
  - Rate limit → escalate retry policy (increase backoff, reduce attempts)
  - Server error → increment failure counter, may open circuit
  - Unknown → log and escalate to admin notification threshold

The cascade is deterministic and configurable via a ResiliencePolicy.
All actions are recorded as ResilienceEvents for audit and trend analysis.

Integration points:
  - hlf_mcp.ecosystem.circuit_breaker.CircuitBreaker (circuit state machine)
  - hlf_mcp.ecosystem.circuit_breaker.CircuitState (CLOSED/OPEN/HALF_OPEN)
  - hlf_mcp.ecosystem.circuit_breaker.CircuitOpenError (fast-fail rejection)
  - hlf_mcp.ecosystem.credential_manager.CredentialManager (credential rotation)
  - hlf_mcp.ecosystem.retry_policy.RetryPolicy (retry escalation)
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (MCP service registration)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (REST service registration)
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hlf_mcp.ecosystem.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
    from hlf_mcp.ecosystem.credential_manager import CredentialManager
    from hlf_mcp.ecosystem.retry_policy import RetryPolicy


# ═══════════════════════════════════════════════════════════════════════════════
# ResilienceAction enum
# ═══════════════════════════════════════════════════════════════════════════════


class ResilienceAction(Enum):
    """Actions the resilience coordinator can take in response to failures."""

    OPEN_CIRCUIT = "open_circuit"           # Trip circuit breaker to OPEN
    ROTATE_CREDENTIALS = "rotate_credentials"  # Rotate compromised credentials
    ESCALATE_RETRY = "escalate_retry"       # Increase retry backoff/reduce attempts
    HALF_OPEN_PROBE = "half_open_probe"     # Allow probe through HALF_OPEN circuit
    CLOSE_CIRCUIT = "close_circuit"         # Reset circuit to CLOSED
    NOTIFY_ADMIN = "notify_admin"           # Trigger admin notification
    RESET_FAILURE_COUNT = "reset_failure_count"  # Reset failure counter on success


# ═══════════════════════════════════════════════════════════════════════════════
# ResilienceEvent — a single resilience action taken
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResilienceEvent:
    """Record of a resilience action taken by the coordinator.

    Attributes:
        timestamp: ISO-8601 timestamp when the action was taken.
        action: The ResilienceAction executed.
        trigger: What caused this action (e.g., "auth_failure",
                 "timeout_error", "rate_limit").
        context: Additional diagnostic context (service name, error
                 details, threshold values).
        outcome: Human-readable outcome of the action.
        success: Whether the action succeeded.
    """

    timestamp: str
    action: ResilienceAction
    trigger: str
    context: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "action": self.action.value,
            "trigger": self.trigger,
            "context": dict(self.context),
            "outcome": self.outcome,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResilienceEvent:
        return cls(
            timestamp=str(data.get("timestamp", "")),
            action=ResilienceAction(data.get("action", "notify_admin")),
            trigger=str(data.get("trigger", "")),
            context=data.get("context", {}),
            outcome=str(data.get("outcome", "")),
            success=bool(data.get("success", True)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ResiliencePolicy — configures cascade thresholds
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResiliencePolicy:
    """Configuration for the resilience cascade.

    Attributes:
        name: Human-readable policy name.
        auth_failure_threshold: Number of auth failures before triggering
                                circuit open + credential rotation.
        circuit_open_duration: Seconds to keep circuit OPEN before
                               transitioning to HALF_OPEN.
        credential_rotation_on_open: Whether to rotate credentials when
                                     the circuit opens.
        escalate_retry_after_failures: Number of total failures before
                                       escalating the retry policy.
        admin_notification_threshold: Total failure count across all error
                                      types that triggers admin notification.
    """

    name: str = "default-resilience"
    auth_failure_threshold: int = 3
    circuit_open_duration: float = 30.0
    credential_rotation_on_open: bool = True
    escalate_retry_after_failures: int = 5
    admin_notification_threshold: int = 10

    def __post_init__(self) -> None:
        if self.auth_failure_threshold < 1:
            raise ValueError(
                f"auth_failure_threshold must be >= 1, got {self.auth_failure_threshold}"
            )
        if self.circuit_open_duration <= 0:
            raise ValueError(
                f"circuit_open_duration must be positive, got {self.circuit_open_duration}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "auth_failure_threshold": self.auth_failure_threshold,
            "circuit_open_duration": self.circuit_open_duration,
            "credential_rotation_on_open": self.credential_rotation_on_open,
            "escalate_retry_after_failures": self.escalate_retry_after_failures,
            "admin_notification_threshold": self.admin_notification_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResiliencePolicy:
        return cls(
            name=str(data.get("name", "default-resilience")),
            auth_failure_threshold=int(data.get("auth_failure_threshold", 3)),
            circuit_open_duration=float(data.get("circuit_open_duration", 30.0)),
            credential_rotation_on_open=bool(data.get("credential_rotation_on_open", True)),
            escalate_retry_after_failures=int(data.get("escalate_retry_after_failures", 5)),
            admin_notification_threshold=int(data.get("admin_notification_threshold", 10)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _classify_error(error: Exception) -> str:
    """Classify an exception into a resilience category.

    Categories:
      - "auth": Authentication/authorization failures (PermissionError,
                any exception mentioning "auth", "credential", "key",
                "token", "unauthorized", "forbidden").
      - "timeout": TimeoutError or exceptions mentioning "timeout", "timed out".
      - "rate_limit": Exceptions mentioning "rate", "throttle", "limit",
                      "quota", "capacity".
      - "server_error": ConnectionError, OSError, RuntimeError, or
                        exceptions mentioning "server", "5xx", "internal".
      - "unknown": Everything else.

    Args:
        error: The exception to classify.

    Returns:
        One of "auth", "timeout", "rate_limit", "server_error", "unknown".
    """
    msg = str(error).lower()
    type_name = type(error).__name__.lower()

    # Auth patterns
    auth_keywords = (
        "auth", "credential", "key", "token", "unauthorized",
        "forbidden", "permission", "access denied", "401", "403",
    )
    if any(kw in msg for kw in auth_keywords) or any(kw in type_name for kw in auth_keywords):
        return "auth"
    if isinstance(error, PermissionError):
        return "auth"

    # Timeout patterns
    timeout_keywords = ("timeout", "timed out", "deadline exceeded", "408")
    if any(kw in msg for kw in timeout_keywords) or "timeout" in type_name:
        return "timeout"
    if isinstance(error, TimeoutError):
        return "timeout"

    # Rate limit patterns
    rate_keywords = (
        "rate", "throttle", "limit", "quota", "capacity",
        "too many requests", "429", "retry after",
    )
    if any(kw in msg for kw in rate_keywords):
        return "rate_limit"

    # Server error patterns
    server_keywords = ("server", "5xx", "internal", "unavailable", "503", "502")
    if any(kw in msg for kw in server_keywords) or any(kw in type_name for kw in server_keywords):
        return "server_error"
    if isinstance(error, (ConnectionError, OSError, RuntimeError)):
        return "server_error"

    return "unknown"


def _track_failure_counters(
    counters: dict[str, int],
    error_category: str,
    total_failures: int,
) -> dict[str, int]:
    """Update per-category failure counters.

    Increments the counter for *error_category* and the total counter.
    Returns the mutated counters dict (also mutated in place).

    Args:
        counters: Dict with keys like "auth", "timeout", "rate_limit",
                  "server_error", "unknown", "total".
        error_category: The category to increment.
        total_failures: Current total (used to set the total key).

    Returns:
        The updated counters dict.
    """
    counters[error_category] = counters.get(error_category, 0) + 1
    counters["total"] = total_failures + 1
    return counters


# ═══════════════════════════════════════════════════════════════════════════════
# ResilienceCoordinator — main class
# ═══════════════════════════════════════════════════════════════════════════════


class ResilienceCoordinator:
    """Coordinates circuit breaker, credential manager, and retry policy
    into a unified resilience cascade.

    Each registered service gets:
      - A circuit breaker for fast-fail isolation.
      - A credential manager for auth rotation.
      - A retry policy for backoff escalation.
      - Per-category failure counters.

    When ``handle_failure`` is called, the coordinator classifies the error,
    updates counters, and executes the cascade defined by the ResiliencePolicy.

    Attributes:
        name: Human-readable name for this coordinator.
        circuit_breakers: Dict of service_name → CircuitBreaker.
        credential_managers: Dict of service_name → CredentialManager.
        retry_policies: Dict of service_name → RetryPolicy.
        policy: The ResiliencePolicy governing cascades.
        failure_counters: Dict of service_name → per-category counters dict.
        events: Ordered list of ResilienceEvent records.
        lock: Reentrant lock for thread safety.
    """

    def __init__(
        self,
        name: str = "resilience-coordinator",
        circuit_breakers: dict[str, Any] | None = None,
        credential_managers: dict[str, Any] | None = None,
        retry_policies: dict[str, Any] | None = None,
        policy: ResiliencePolicy | None = None,
    ) -> None:
        self.name = name
        self.circuit_breakers: dict[str, Any] = circuit_breakers or {}
        self.credential_managers: dict[str, Any] = credential_managers or {}
        self.retry_policies: dict[str, Any] = retry_policies or {}
        self.policy = policy or ResiliencePolicy()

        # Per-service failure counters: {service_name: {category: count, "total": N}}
        self.failure_counters: dict[str, dict[str, int]] = {}

        # Event history (most recent first)
        self.events: list[ResilienceEvent] = []
        self.lock = threading.RLock()

    # ── Service registration ──────────────────────────────────────────────────

    def register_service(
        self,
        service_name: str,
        circuit_breaker: Any,
        credential_manager: Any,
        retry_policy: Any,
    ) -> None:
        """Register a service's resilience components.

        Args:
            service_name: Unique name for the service (e.g., "mcp_bridge",
                          "rest_bridge").
            circuit_breaker: A CircuitBreaker instance for this service.
            credential_manager: A CredentialManager instance for this service.
            retry_policy: A RetryPolicy instance for this service.
        """
        with self.lock:
            self.circuit_breakers[service_name] = circuit_breaker
            self.credential_managers[service_name] = credential_manager
            self.retry_policies[service_name] = retry_policy

            # Initialize failure counters
            if service_name not in self.failure_counters:
                self.failure_counters[service_name] = {
                    "auth": 0,
                    "timeout": 0,
                    "rate_limit": 0,
                    "server_error": 0,
                    "unknown": 0,
                    "total": 0,
                }

    # ── Failure handling ──────────────────────────────────────────────────────

    def handle_failure(
        self,
        service_name: str,
        error: Exception,
        context: dict[str, Any] | None = None,
    ) -> list[ResilienceEvent]:
        """Main entry point: classify error and execute resilience cascade.

        Cascade logic:
          1. Classify error type.
          2. Update per-category failure counters.
          3. Execute category-specific actions:
             - auth: if auth threshold exceeded → open circuit +
               (optionally) rotate credentials.
             - timeout: open circuit immediately.
             - rate_limit: escalate retry policy.
             - server_error: increment counter; open circuit if total
               failures exceed admin threshold.
             - unknown: log; escalate if total exceeds admin threshold.
          4. Check admin notification threshold.
          5. Return list of ResilienceEvent records for actions taken.

        Args:
            service_name: The affected service.
            error: The exception that triggered the cascade.
            context: Additional diagnostic context.

        Returns:
            List of ResilienceEvent records for actions executed.
        """
        ctx = context or {}
        ctx["error_type"] = type(error).__name__
        ctx["error_message"] = str(error)[:500]

        category = _classify_error(error)
        ctx["error_category"] = category

        events: list[ResilienceEvent] = []
        now_ts = datetime.now(timezone.utc).isoformat()

        with self.lock:
            # Initialize counters if needed
            if service_name not in self.failure_counters:
                self.failure_counters[service_name] = {
                    "auth": 0, "timeout": 0, "rate_limit": 0,
                    "server_error": 0, "unknown": 0, "total": 0,
                }

            counters = self.failure_counters[service_name]
            _track_failure_counters(counters, category, counters["total"])
            total = counters["total"]

            cb = self.circuit_breakers.get(service_name)
            cm = self.credential_managers.get(service_name)
            rp = self.retry_policies.get(service_name)

            # ── Category-specific cascade ──────────────────────────────────

            if category == "auth":
                auth_count = counters["auth"]
                if auth_count >= self.policy.auth_failure_threshold:
                    # Open circuit
                    if cb is not None:
                        try:
                            cb.trip()
                            evt = ResilienceEvent(
                                timestamp=now_ts,
                                action=ResilienceAction.OPEN_CIRCUIT,
                                trigger=f"auth_failure_threshold ({auth_count}/{self.policy.auth_failure_threshold})",
                                context={**ctx, "service": service_name, "failure_count": auth_count},
                                outcome=f"Circuit OPEN for '{service_name}' — auth failure threshold exceeded",
                                success=True,
                            )
                            events.append(evt)
                        except Exception as exc:
                            events.append(ResilienceEvent(
                                timestamp=now_ts,
                                action=ResilienceAction.OPEN_CIRCUIT,
                                trigger=f"auth_failure_threshold ({auth_count})",
                                context={**ctx, "service": service_name},
                                outcome=f"Failed to open circuit: {exc}",
                                success=False,
                            ))

                    # Rotate credentials if policy allows
                    if self.policy.credential_rotation_on_open and cm is not None:
                        try:
                            # Rotate all active credentials for this service
                            active_creds = cm.list_active()
                            rotated_count = 0
                            for cred in active_creds:
                                new_cred = cm.rotate_credential(cred["key_id"])
                                if new_cred is not None:
                                    rotated_count += 1

                            evt = ResilienceEvent(
                                timestamp=now_ts,
                                action=ResilienceAction.ROTATE_CREDENTIALS,
                                trigger=f"auth_failure_threshold ({auth_count})",
                                context={**ctx, "service": service_name, "rotated_count": rotated_count},
                                outcome=f"Rotated {rotated_count} credentials for '{service_name}'",
                                success=rotated_count > 0,
                            )
                            events.append(evt)
                        except Exception as exc:
                            events.append(ResilienceEvent(
                                timestamp=now_ts,
                                action=ResilienceAction.ROTATE_CREDENTIALS,
                                trigger=f"auth_failure_threshold ({auth_count})",
                                context={**ctx, "service": service_name},
                                outcome=f"Failed to rotate credentials: {exc}",
                                success=False,
                            ))

            elif category == "timeout":
                # Open circuit immediately on timeout
                if cb is not None:
                    try:
                        cb.trip()
                        evt = ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.OPEN_CIRCUIT,
                            trigger=f"timeout_error: {str(error)[:200]}",
                            context={**ctx, "service": service_name},
                            outcome=f"Circuit OPEN for '{service_name}' — timeout detected",
                            success=True,
                        )
                        events.append(evt)
                    except Exception as exc:
                        events.append(ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.OPEN_CIRCUIT,
                            trigger="timeout_error",
                            context={**ctx, "service": service_name},
                            outcome=f"Failed to open circuit: {exc}",
                            success=False,
                        ))

            elif category == "rate_limit":
                # Escalate retry policy
                if rp is not None:
                    try:
                        # Increase base delay and reduce max retries
                        original_base = rp.base_delay
                        original_max = rp.max_retries
                        rp.base_delay = min(rp.base_delay * 2.0, rp.max_delay)
                        rp.max_retries = max(1, rp.max_retries - 1)

                        evt = ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.ESCALATE_RETRY,
                            trigger=f"rate_limit (total failures: {total})",
                            context={
                                **ctx,
                                "service": service_name,
                                "old_base_delay": original_base,
                                "new_base_delay": rp.base_delay,
                                "old_max_retries": original_max,
                                "new_max_retries": rp.max_retries,
                            },
                            outcome=(
                                f"Escalated retry for '{service_name}': "
                                f"base_delay {original_base:.1f}→{rp.base_delay:.1f}s, "
                                f"max_retries {original_max}→{rp.max_retries}"
                            ),
                            success=True,
                        )
                        events.append(evt)
                    except Exception as exc:
                        events.append(ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.ESCALATE_RETRY,
                            trigger="rate_limit",
                            context={**ctx, "service": service_name},
                            outcome=f"Failed to escalate retry: {exc}",
                            success=False,
                        ))

            elif category == "server_error":
                # Open circuit if total failures exceed escalate threshold
                if total >= self.policy.escalate_retry_after_failures and cb is not None:
                    try:
                        cb.trip()
                        evt = ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.OPEN_CIRCUIT,
                            trigger=f"server_error cascade (total: {total}/{self.policy.escalate_retry_after_failures})",
                            context={**ctx, "service": service_name, "total_failures": total},
                            outcome=f"Circuit OPEN for '{service_name}' — server error cascade threshold reached",
                            success=True,
                        )
                        events.append(evt)
                    except Exception as exc:
                        events.append(ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.OPEN_CIRCUIT,
                            trigger="server_error cascade",
                            context={**ctx, "service": service_name},
                            outcome=f"Failed to open circuit: {exc}",
                            success=False,
                        ))

            # ── Admin notification threshold ────────────────────────────────

            if total >= self.policy.admin_notification_threshold:
                evt = ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.NOTIFY_ADMIN,
                    trigger=(
                        f"admin_notification_threshold "
                        f"({total}/{self.policy.admin_notification_threshold})"
                    ),
                    context={
                        **ctx,
                        "service": service_name,
                        "total_failures": total,
                        "counters": dict(counters),
                    },
                    outcome=(
                        f"Admin notification triggered for '{service_name}' — "
                        f"{total} total failures"
                    ),
                    success=True,
                )
                events.append(evt)

            # Store events
            self.events = events + self.events  # most recent first

        return events

    # ── Success handling ──────────────────────────────────────────────────────

    def handle_success(self, service_name: str) -> list[ResilienceEvent]:
        """Handle a successful request.

        Resets the failure counter for the service. If the circuit is
        HALF_OPEN, records a success probe — which may close the circuit.

        Args:
            service_name: The service that succeeded.

        Returns:
            List of ResilienceEvents for actions taken.
        """
        events: list[ResilienceEvent] = []
        now_ts = datetime.now(timezone.utc).isoformat()

        with self.lock:
            # Reset failure counters
            if service_name in self.failure_counters:
                old_total = self.failure_counters[service_name]["total"]
                self.failure_counters[service_name] = {
                    "auth": 0, "timeout": 0, "rate_limit": 0,
                    "server_error": 0, "unknown": 0, "total": 0,
                }
                events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.RESET_FAILURE_COUNT,
                    trigger="success",
                    context={"service": service_name, "old_total": old_total},
                    outcome=f"Reset failure counters for '{service_name}' (was {old_total})",
                    success=True,
                ))

            cb = self.circuit_breakers.get(service_name)
            if cb is not None:
                from hlf_mcp.ecosystem.circuit_breaker import CircuitState

                if cb.state == CircuitState.HALF_OPEN:
                    # Record probe success
                    cb.record_success()
                    events.append(ResilienceEvent(
                        timestamp=now_ts,
                        action=ResilienceAction.HALF_OPEN_PROBE,
                        trigger="success_in_half_open",
                        context={"service": service_name},
                        outcome=f"HALF_OPEN probe succeeded for '{service_name}'",
                        success=True,
                    ))

                    if cb.state == CircuitState.CLOSED:
                        events.append(ResilienceEvent(
                            timestamp=now_ts,
                            action=ResilienceAction.CLOSE_CIRCUIT,
                            trigger="probe_success_threshold",
                            context={"service": service_name},
                            outcome=f"Circuit CLOSED for '{service_name}' — probe threshold met",
                            success=True,
                        ))
                elif cb.state == CircuitState.CLOSED:
                    cb.record_success()

            # Store events
            self.events = events + self.events

        return events

    # ── Service status ────────────────────────────────────────────────────────

    def get_service_status(self, service_name: str) -> dict[str, Any]:
        """Return the current resilience status for a service.

        Includes: circuit state, failure counts, credential age,
        and retry policy state.
        """
        with self.lock:
            cb = self.circuit_breakers.get(service_name)
            cm = self.credential_managers.get(service_name)
            rp = self.retry_policies.get(service_name)
            counters = self.failure_counters.get(
                service_name,
                {"auth": 0, "timeout": 0, "rate_limit": 0,
                 "server_error": 0, "unknown": 0, "total": 0},
            )

            result: dict[str, Any] = {
                "service_name": service_name,
                "registered": (
                    service_name in self.circuit_breakers
                    or service_name in self.credential_managers
                    or service_name in self.retry_policies
                ),
                "failure_counters": dict(counters),
            }

            # Circuit breaker status
            if cb is not None:
                result["circuit"] = {
                    "state": cb.state.name if hasattr(cb, "state") else "unknown",
                    "is_open": cb.is_open() if hasattr(cb, "is_open") else None,
                    "trip_count": getattr(cb, "trip_count", 0),
                    "failure_count": getattr(cb, "failure_count", 0),
                }
            else:
                result["circuit"] = None

            # Credential manager status
            if cm is not None:
                result["credentials"] = cm.stats() if hasattr(cm, "stats") else {"active": cm.count_active()}
            else:
                result["credentials"] = None

            # Retry policy status
            if rp is not None:
                result["retry"] = rp.stats() if hasattr(rp, "stats") else {
                    "max_retries": getattr(rp, "max_retries", 3),
                    "base_delay": getattr(rp, "base_delay", 1.0),
                }
            else:
                result["retry"] = None

            return result

    def global_status(self) -> dict[str, Any]:
        """Return status for all registered services with aggregated health score.

        Health score (0-1): weighted average across services of:
          - Circuit health: 0.0 if OPEN, 0.5 if HALF_OPEN, 1.0 if CLOSED.
          - Failure ratio: 1.0 - min(1.0, total_failures / admin_threshold).
          - Credential health: 1.0 if active credentials > 0, else 0.0.

        Returns:
            Dict with per-service status and global health score.
        """
        with self.lock:
            services: dict[str, Any] = {}
            health_scores: list[float] = []

            all_services = set(self.circuit_breakers.keys()) | set(self.credential_managers.keys()) | set(self.retry_policies.keys())

            for svc in sorted(all_services):
                status = self.get_service_status(svc)

                # Compute per-service health
                circuit_score = 1.0
                if status.get("circuit") and status["circuit"].get("state") == "OPEN":
                    circuit_score = 0.0
                elif status.get("circuit") and status["circuit"].get("state") == "HALF_OPEN":
                    circuit_score = 0.5

                total_fail = status.get("failure_counters", {}).get("total", 0)
                failure_ratio = min(1.0, total_fail / max(1, self.policy.admin_notification_threshold))
                failure_score = 1.0 - failure_ratio

                cred_score = 1.0
                if status.get("credentials") is not None:
                    active = status["credentials"].get("active", 0)
                    cred_score = 1.0 if active > 0 else 0.5

                svc_health = (circuit_score * 0.4 + failure_score * 0.3 + cred_score * 0.3)
                health_scores.append(svc_health)
                status["health_score"] = round(svc_health, 3)
                services[svc] = status

            global_health = sum(health_scores) / len(health_scores) if health_scores else 1.0

            return {
                "coordinator": self.name,
                "policy": self.policy.name,
                "services": services,
                "service_count": len(services),
                "global_health_score": round(global_health, 3),
                "health_interpretation": (
                    "healthy" if global_health >= 0.8
                    else "degraded" if global_health >= 0.5
                    else "critical"
                ),
            }

    # ── Event history ─────────────────────────────────────────────────────────

    def event_history(
        self,
        service_name: str | None = None,
        limit: int = 100,
    ) -> list[ResilienceEvent]:
        """Get recent resilience events, optionally filtered by service.

        Args:
            service_name: Filter to events for this service only.
                          If None, returns all events.
            limit: Maximum number of events to return.

        Returns:
            List of ResilienceEvent records, most recent first.
        """
        with self.lock:
            filtered = self.events
            if service_name:
                filtered = [
                    e for e in filtered
                    if e.context.get("service") == service_name
                ]
            return list(filtered[:limit])

    # ── Simulation ────────────────────────────────────────────────────────────

    def simulate_cascade(
        self,
        service_name: str,
        failure_sequence: list[str],
    ) -> list[list[ResilienceEvent]]:
        """Simulate a sequence of failures without executing actual actions.

        Returns the cascade of events that *would* occur. Uses a deep copy
        of the current state so simulation does not mutate real counters.

        Args:
            service_name: The service to simulate against.
            failure_sequence: List of error category strings
                              (e.g., ["auth", "auth", "auth", "timeout"]).

        Returns:
            List of lists: one list of ResilienceEvents per failure step.
        """
        # Deep-copy current counters for simulation
        import copy

        sim_counters = copy.deepcopy(
            self.failure_counters.get(service_name, {
                "auth": 0, "timeout": 0, "rate_limit": 0,
                "server_error": 0, "unknown": 0, "total": 0,
            })
        )
        results: list[list[ResilienceEvent]] = []

        for category in failure_sequence:
            step_events: list[ResilienceEvent] = []
            now_ts = datetime.now(timezone.utc).isoformat()

            # Update simulated counters
            sim_counters = _track_failure_counters(sim_counters, category, sim_counters["total"])
            total = sim_counters["total"]
            auth_count = sim_counters.get("auth", 0)

            # Simulate auth cascade
            if category == "auth" and auth_count >= self.policy.auth_failure_threshold:
                step_events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.OPEN_CIRCUIT,
                    trigger=f"simulated: auth_failure_threshold ({auth_count}/{self.policy.auth_failure_threshold})",
                    context={"service": service_name, "simulated": True, "failure_count": auth_count},
                    outcome=f"[SIM] Circuit OPEN for '{service_name}'",
                    success=True,
                ))
                if self.policy.credential_rotation_on_open:
                    step_events.append(ResilienceEvent(
                        timestamp=now_ts,
                        action=ResilienceAction.ROTATE_CREDENTIALS,
                        trigger=f"simulated: auth_failure_threshold ({auth_count})",
                        context={"service": service_name, "simulated": True},
                        outcome=f"[SIM] Credentials rotated for '{service_name}'",
                        success=True,
                    ))

            # Simulate timeout → open circuit
            if category == "timeout":
                step_events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.OPEN_CIRCUIT,
                    trigger="simulated: timeout_error",
                    context={"service": service_name, "simulated": True},
                    outcome=f"[SIM] Circuit OPEN for '{service_name}' — timeout",
                    success=True,
                ))

            # Simulate rate limit → escalate retry
            if category == "rate_limit":
                step_events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.ESCALATE_RETRY,
                    trigger="simulated: rate_limit",
                    context={"service": service_name, "simulated": True},
                    outcome=f"[SIM] Retry escalated for '{service_name}'",
                    success=True,
                ))

            # Simulate server_error cascade
            if category == "server_error" and total >= self.policy.escalate_retry_after_failures:
                step_events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.OPEN_CIRCUIT,
                    trigger=f"simulated: server_error cascade (total: {total}/{self.policy.escalate_retry_after_failures})",
                    context={"service": service_name, "simulated": True, "total_failures": total},
                    outcome=f"[SIM] Circuit OPEN for '{service_name}' — server error cascade",
                    success=True,
                ))

            # Simulate admin notification
            if total >= self.policy.admin_notification_threshold:
                step_events.append(ResilienceEvent(
                    timestamp=now_ts,
                    action=ResilienceAction.NOTIFY_ADMIN,
                    trigger=f"simulated: admin_notification_threshold ({total}/{self.policy.admin_notification_threshold})",
                    context={"service": service_name, "simulated": True, "total_failures": total},
                    outcome=f"[SIM] Admin notified for '{service_name}' — {total} failures",
                    success=True,
                ))

            results.append(step_events)

        return results

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for the resilience coordinator."""
        with self.lock:
            total_events = len(self.events)
            actions_by_type: dict[str, int] = {}
            for evt in self.events:
                key = evt.action.value
                actions_by_type[key] = actions_by_type.get(key, 0) + 1

            return {
                "name": self.name,
                "policy": self.policy.to_dict(),
                "registered_services": sorted(
                    set(self.circuit_breakers.keys())
                    | set(self.credential_managers.keys())
                    | set(self.retry_policies.keys())
                ),
                "service_count": len(set(self.circuit_breakers.keys()) | set(self.credential_managers.keys())),
                "total_events": total_events,
                "actions_by_type": actions_by_type,
                "per_service_failures": {
                    svc: dict(cnt)
                    for svc, cnt in self.failure_counters.items()
                    if cnt.get("total", 0) > 0
                },
            }

    def reset(self) -> None:
        """Reset all failure counters and clear event history."""
        with self.lock:
            self.failure_counters.clear()
            self.events.clear()
            for cb in self.circuit_breakers.values():
                try:
                    cb.reset()
                except Exception:
                    pass
