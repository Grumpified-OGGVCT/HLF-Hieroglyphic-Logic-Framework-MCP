from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.align_governor import AlignGovernor


@dataclass(slots=True, frozen=True)
class RateLimitRule:
    max_requests: int = 50
    window_seconds: int = 60

    def to_dict(self) -> dict[str, int]:
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
        }


class InMemoryIngressRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}

    def check(self, subject_key: str, *, rule: RateLimitRule, now: float | None = None) -> dict[str, Any]:
        effective_now = float(now if now is not None else time.time())
        key = str(subject_key or "anonymous")
        window_floor = effective_now - max(1, int(rule.window_seconds))
        active = [timestamp for timestamp in self._events.get(key, []) if timestamp >= window_floor]
        allowed = len(active) < max(1, int(rule.max_requests))
        if allowed:
            active.append(effective_now)
        self._events[key] = active
        return {
            "stage": "rate_limit",
            "allowed": allowed,
            "subject_key": key,
            "request_count": len(active),
            "remaining": max(0, int(rule.max_requests) - len(active)),
            "rule": rule.to_dict(),
        }


class InMemoryReplayProtector:
    def __init__(self) -> None:
        self._seen: dict[str, float] = {}

    def check(self, nonce: str, *, ttl_seconds: int = 300, now: float | None = None) -> dict[str, Any]:
        effective_now = float(now if now is not None else time.time())
        effective_nonce = str(nonce or "").strip()
        ttl = max(1, int(ttl_seconds))
        self._seen = {
            key: timestamp
            for key, timestamp in self._seen.items()
            if (effective_now - timestamp) < ttl
        }
        if not effective_nonce:
            return {
                "stage": "replay_protection",
                "allowed": False,
                "status": "missing_nonce",
                "ttl_seconds": ttl,
            }
        if effective_nonce in self._seen:
            return {
                "stage": "replay_protection",
                "allowed": False,
                "status": "replayed",
                "nonce": effective_nonce,
                "ttl_seconds": ttl,
            }
        self._seen[effective_nonce] = effective_now
        return {
            "stage": "replay_protection",
            "allowed": True,
            "status": "accepted",
            "nonce": effective_nonce,
            "ttl_seconds": ttl,
        }


@dataclass(slots=True)
class GovernedIngressVerdict:
    admitted: bool
    decision: str
    blocked_stage: str
    review_required: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    route_contract: dict[str, Any] = field(default_factory=dict)
    policy_basis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "decision": self.decision,
            "blocked_stage": self.blocked_stage,
            "review_required": self.review_required,
            "checks": list(self.checks),
            "route_contract": dict(self.route_contract),
            "policy_basis": dict(self.policy_basis),
        }


class GovernedIngressController:
    def __init__(
        self,
        *,
        align_governor: AlignGovernor | None = None,
        rate_limiter: InMemoryIngressRateLimiter | None = None,
        replay_protector: InMemoryReplayProtector | None = None,
    ) -> None:
        self.align_governor = align_governor or AlignGovernor()
        self.rate_limiter = rate_limiter or InMemoryIngressRateLimiter()
        self.replay_protector = replay_protector or InMemoryReplayProtector()

    def evaluate(
        self,
        payload: str | dict[str, Any],
        *,
        subject_key: str,
        nonce: str,
        rate_limit_rule: RateLimitRule | None = None,
        replay_ttl_seconds: int = 300,
        require_hlf_validation: bool = False,
        hlf_validated: bool = True,
        enable_rate_limit: bool = True,
        enable_replay_protection: bool = True,
        now: float | None = None,
    ) -> GovernedIngressVerdict:
        checks: list[dict[str, Any]] = []
        effective_rule = rate_limit_rule or RateLimitRule()

        if enable_rate_limit:
            rate_limit = self.rate_limiter.check(subject_key, rule=effective_rule, now=now)
        else:
            rate_limit = {
                "stage": "rate_limit",
                "allowed": True,
                "status": "skipped",
                "subject_key": str(subject_key or "anonymous"),
                "rule": effective_rule.to_dict(),
            }
        checks.append(rate_limit)
        if not rate_limit["allowed"]:
            return GovernedIngressVerdict(
                admitted=False,
                decision="deny",
                blocked_stage="rate_limit",
                review_required=False,
                checks=checks,
                route_contract={
                    "admitted": False,
                    "governance_mode": "rate_limited",
                    "next_stage": None,
                },
                policy_basis={
                    "stage_order": [
                        "rate_limit",
                        "hlf_validation",
                        "align_gate",
                        "replay_protection",
                        "governed_routing",
                    ],
                    "rate_limit": rate_limit,
                },
            )

        validation = {
            "stage": "hlf_validation",
            "allowed": (not require_hlf_validation) or bool(hlf_validated),
            "required": bool(require_hlf_validation),
            "validated": bool(hlf_validated),
        }
        checks.append(validation)
        if not validation["allowed"]:
            return GovernedIngressVerdict(
                admitted=False,
                decision="deny",
                blocked_stage="hlf_validation",
                review_required=False,
                checks=checks,
                route_contract={
                    "admitted": False,
                    "governance_mode": "validation_failed",
                    "next_stage": None,
                },
                policy_basis={
                    "stage_order": [
                        "rate_limit",
                        "hlf_validation",
                        "align_gate",
                        "replay_protection",
                        "governed_routing",
                    ],
                    "rate_limit": rate_limit,
                    "hlf_validation": validation,
                },
            )

        align_verdict = self.align_governor.evaluate(payload)
        align_check = {
            "stage": "align_gate",
            "allowed": bool(align_verdict.allowed),
            "status": align_verdict.status,
            "action": align_verdict.action,
            "decisive_rule_id": align_verdict.decisive_rule_id,
            "subject_hash": align_verdict.subject_hash,
            "loaded_rule_count": align_verdict.loaded_rule_count,
        }
        checks.append(align_check)
        if not align_check["allowed"]:
            return GovernedIngressVerdict(
                admitted=False,
                decision="deny",
                blocked_stage="align_gate",
                review_required=False,
                checks=checks,
                route_contract={
                    "admitted": False,
                    "governance_mode": "align_blocked",
                    "next_stage": None,
                },
                policy_basis={
                    "stage_order": [
                        "rate_limit",
                        "hlf_validation",
                        "align_gate",
                        "replay_protection",
                        "governed_routing",
                    ],
                    "rate_limit": rate_limit,
                    "hlf_validation": validation,
                    "align_gate": align_check,
                },
            )

        if enable_replay_protection:
            replay = self.replay_protector.check(nonce, ttl_seconds=replay_ttl_seconds, now=now)
        else:
            replay = {
                "stage": "replay_protection",
                "allowed": True,
                "status": "skipped",
                "ttl_seconds": max(1, int(replay_ttl_seconds)),
            }
        checks.append(replay)
        if not replay["allowed"]:
            return GovernedIngressVerdict(
                admitted=False,
                decision="deny",
                blocked_stage="replay_protection",
                review_required=False,
                checks=checks,
                route_contract={
                    "admitted": False,
                    "governance_mode": "replay_blocked",
                    "next_stage": None,
                },
                policy_basis={
                    "stage_order": [
                        "rate_limit",
                        "hlf_validation",
                        "align_gate",
                        "replay_protection",
                        "governed_routing",
                    ],
                    "rate_limit": rate_limit,
                    "hlf_validation": validation,
                    "align_gate": align_check,
                    "replay_protection": replay,
                },
            )

        review_required = align_verdict.status == "warning" or align_verdict.action == "ROUTE_TO_HUMAN_APPROVAL"
        governance_mode = "review" if review_required else "direct"
        route_contract = {
            "admitted": True,
            "governance_mode": governance_mode,
            "review_required": review_required,
            "next_stage": "governed_routing",
            "align_status": align_verdict.status,
            "align_action": align_verdict.action,
        }
        return GovernedIngressVerdict(
            admitted=True,
            decision="review" if review_required else "allow",
            blocked_stage="",
            review_required=review_required,
            checks=checks,
            route_contract=route_contract,
            policy_basis={
                "stage_order": [
                    "rate_limit",
                    "hlf_validation",
                    "align_gate",
                    "replay_protection",
                    "governed_routing",
                ],
                "rate_limit": rate_limit,
                "hlf_validation": validation,
                "align_gate": align_check,
                "replay_protection": replay,
                "route_contract": route_contract,
            },
        )