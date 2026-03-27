from __future__ import annotations

import json
from pathlib import Path

from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.governed_ingress import GovernedIngressController
from hlf_mcp.hlf.governed_ingress import InMemoryIngressRateLimiter
from hlf_mcp.hlf.governed_ingress import InMemoryReplayProtector
from hlf_mcp.hlf.governed_ingress import RateLimitRule


def _align_governor(tmp_path: Path, *, pattern: str, action: str) -> AlignGovernor:
    rules_path = tmp_path / "align_rules.json"
    rules_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "rule-1",
                        "name": "test-rule",
                        "pattern": pattern,
                        "action": action,
                        "description": "test ingress rule",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return AlignGovernor(rules_path)


def test_governed_ingress_denies_rate_limit_before_replay_is_recorded(tmp_path: Path) -> None:
    controller = GovernedIngressController(
        align_governor=_align_governor(tmp_path, pattern="never-match", action="allow"),
        rate_limiter=InMemoryIngressRateLimiter(),
        replay_protector=InMemoryReplayProtector(),
    )
    rule = RateLimitRule(max_requests=1, window_seconds=60)

    first = controller.evaluate("safe payload", subject_key="agent-a", nonce="nonce-1", rate_limit_rule=rule, now=10.0)
    second = controller.evaluate("safe payload", subject_key="agent-a", nonce="nonce-2", rate_limit_rule=rule, now=20.0)
    third = controller.evaluate("safe payload", subject_key="agent-b", nonce="nonce-2", rate_limit_rule=rule, now=21.0)

    assert first.admitted is True
    assert second.admitted is False
    assert second.blocked_stage == "rate_limit"
    assert third.admitted is True


def test_governed_ingress_denies_duplicate_nonce_after_align_passes(tmp_path: Path) -> None:
    controller = GovernedIngressController(
        align_governor=_align_governor(tmp_path, pattern="never-match", action="allow")
    )

    first = controller.evaluate("safe payload", subject_key="agent-a", nonce="nonce-1", now=10.0)
    second = controller.evaluate("safe payload", subject_key="agent-b", nonce="nonce-1", now=11.0)

    assert first.admitted is True
    assert second.admitted is False
    assert second.blocked_stage == "replay_protection"
    assert second.policy_basis["replay_protection"]["status"] == "replayed"


def test_governed_ingress_blocks_on_align_drop_and_preserves_nonce_for_future_safe_call(tmp_path: Path) -> None:
    controller = GovernedIngressController(
        align_governor=_align_governor(tmp_path, pattern="forbidden", action="drop")
    )

    blocked = controller.evaluate("forbidden payload", subject_key="agent-a", nonce="nonce-1", now=10.0)
    allowed = controller.evaluate("safe payload", subject_key="agent-a", nonce="nonce-1", now=11.0)

    assert blocked.admitted is False
    assert blocked.blocked_stage == "align_gate"
    assert blocked.policy_basis["align_gate"]["action"] == "DROP"
    assert allowed.admitted is True


def test_governed_ingress_routes_warning_align_action_into_review(tmp_path: Path) -> None:
    controller = GovernedIngressController(
        align_governor=_align_governor(tmp_path, pattern="review-me", action="route_to_human_approval")
    )

    result = controller.evaluate("review-me payload", subject_key="agent-a", nonce="nonce-1", now=10.0)

    assert result.admitted is True
    assert result.review_required is True
    assert result.decision == "review"
    assert result.route_contract["governance_mode"] == "review"


def test_governed_ingress_denies_when_hlf_validation_is_required_but_missing(tmp_path: Path) -> None:
    controller = GovernedIngressController(
        align_governor=_align_governor(tmp_path, pattern="never-match", action="allow")
    )

    result = controller.evaluate(
        "safe payload",
        subject_key="agent-a",
        nonce="nonce-1",
        require_hlf_validation=True,
        hlf_validated=False,
        now=10.0,
    )

    assert result.admitted is False
    assert result.blocked_stage == "hlf_validation"
    assert result.policy_basis["hlf_validation"]["required"] is True