"""Tests for hlf_mcp.hlf.dream_promotion — dream cycle promotion rule binding."""

from __future__ import annotations

import uuid

import pytest

from hlf_mcp.hlf.dream_promotion import (
    DreamFinding,
    FindingState,
    PromotionRule,
    bind_finding_to_rules,
    define_standard_rules,
    evaluate_promotion,
    promote_finding,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helper factories
# ═══════════════════════════════════════════════════════════════════════════


def _make_finding(
    *,
    finding_id: str | None = None,
    state: FindingState = FindingState.VERIFIED,
    proposal: str = "",
    verification_results: list[dict] | None = None,
    applicable_rules: list[str] | None = None,
) -> DreamFinding:
    return DreamFinding(
        finding_id=finding_id or f"finding-{uuid.uuid4().hex[:16]}",
        state=state,
        observed_at="2026-04-01T00:00:00+00:00",
        proposal=proposal,
        verification_results=verification_results or [],
        applicable_rules=applicable_rules or [],
        promotion_evidence=None,
        rejected_reason=None,
    )


def _make_verification_results(passed: bool = True, check_names: list[str] | None = None) -> list[dict]:
    """Generate verification result dicts for the given check names."""
    names = check_names or []
    return [{"check": name, "passed": passed, "name": name} for name in names]


# ═══════════════════════════════════════════════════════════════════════════
# Test: define_standard_rules
# ═══════════════════════════════════════════════════════════════════════════


def test_define_standard_rules_returns_at_least_5_rules() -> None:
    """define_standard_rules returns at least 5 promotion rules."""
    rules = define_standard_rules()
    assert len(rules) >= 5, f"Expected at least 5 rules, got {len(rules)}"

    rule_ids = {r.rule_id for r in rules}
    expected = {"benchmark_improvement", "coverage_increase", "security_fix", "breaking_change", "cosmetic"}
    assert expected.issubset(rule_ids), f"Missing expected rules: {expected - rule_ids}"


# ═══════════════════════════════════════════════════════════════════════════
# Test: benchmark_improvement rule structure
# ═══════════════════════════════════════════════════════════════════════════


def test_benchmark_improvement_rule_has_correct_preconditions() -> None:
    """The benchmark_improvement rule requires benchmark score improvement and baseline."""
    rules = {r.rule_id: r for r in define_standard_rules()}
    rule = rules["benchmark_improvement"]

    assert "benchmark_score_improved >= 5%" in rule.preconditions
    assert "benchmark_baseline_available" in rule.preconditions
    assert "regression_tests_pass" in rule.verification_checks
    assert rule.auto_promote is False
    assert rule.requires_review is True


# ═══════════════════════════════════════════════════════════════════════════
# Test: breaking_change rule requires review
# ═══════════════════════════════════════════════════════════════════════════


def test_breaking_change_rule_requires_review() -> None:
    """The breaking_change rule never auto-promotes and always requires review."""
    rules = {r.rule_id: r for r in define_standard_rules()}
    rule = rules["breaking_change"]

    assert rule.requires_review is True
    assert rule.auto_promote is False
    assert "change_is_breaking" in rule.preconditions
    assert "migration_path_documented" in rule.verification_checks


# ═══════════════════════════════════════════════════════════════════════════
# Test: bind_finding_to_rules
# ═══════════════════════════════════════════════════════════════════════════


def test_bind_finding_to_rules_populates_applicable_rules() -> None:
    """bind_finding_to_rules populates applicable_rules based on proposal keywords."""
    rules = define_standard_rules()
    finding = _make_finding(
        proposal="Fix SQL injection vulnerability in user login endpoint",
        verification_results=_make_verification_results(
            True, ["security_tests_pass", "vulnerability_confirmed_fixed", "no_new_vulnerabilities_introduced"]
        ),
    )

    result = bind_finding_to_rules(finding, rules)
    assert "security_fix" in result.applicable_rules


def test_bind_finding_to_rules_defaults_to_conservative_when_no_match() -> None:
    """When no keyword matches, bind defaults to benchmark_improvement + breaking_change."""
    rules = define_standard_rules()
    finding = _make_finding(
        proposal="Some ambiguous change that doesn't match any keywords clearly",
    )

    result = bind_finding_to_rules(finding, rules)
    # Conservative default
    assert "benchmark_improvement" in result.applicable_rules
    assert "breaking_change" in result.applicable_rules


# ═══════════════════════════════════════════════════════════════════════════
# Test: evaluate_promotion — success path
# ═══════════════════════════════════════════════════════════════════════════


def test_evaluate_promotion_promotes_when_all_rules_pass() -> None:
    """evaluate_promotion transitions to PROMOTED when all rules pass and none require review."""
    rules = define_standard_rules()
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Increase test coverage for the auth module",
        verification_results=_make_verification_results(
            True,
            [
                "regression_tests_pass",
                "coverage_metric_validated",
                "no_new_failures",
            ],
        ),
    )

    # Bind first
    bind_finding_to_rules(finding, rules)
    # Ensure only auto-promotable rules apply
    finding.applicable_rules = ["coverage_increase"]

    result = evaluate_promotion(finding, rules)
    assert result.state == FindingState.PROMOTED
    assert result.promotion_evidence is not None
    assert result.promotion_evidence["all_rules_passed"] is True
    assert result.rejected_reason is None


# ═══════════════════════════════════════════════════════════════════════════
# Test: evaluate_promotion — requires review
# ═══════════════════════════════════════════════════════════════════════════


def test_evaluate_promotion_keeps_verified_when_rule_requires_review() -> None:
    """evaluate_promotion stays at VERIFIED when an applicable rule requires human review."""
    rules = define_standard_rules()
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Breaking API change: remove deprecated v1 endpoints",
        verification_results=_make_verification_results(
            True,
            [
                "impact_assessment_complete",
                "migration_path_documented",
                "deprecation_notice_published",
            ],
        ),
        applicable_rules=["breaking_change"],
    )

    result = evaluate_promotion(finding, rules)
    assert result.state == FindingState.VERIFIED
    assert result.rejected_reason is None


# ═══════════════════════════════════════════════════════════════════════════
# Test: evaluate_promotion — verification failure
# ═══════════════════════════════════════════════════════════════════════════


def test_evaluate_promotion_rejects_when_verification_fails() -> None:
    """evaluate_promotion transitions to REJECTED when verification checks fail."""
    rules = define_standard_rules()
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Add new security hardening for password hashing",
        verification_results=_make_verification_results(
            False,  # all checks FAIL
            [
                "security_tests_pass",
                "vulnerability_confirmed_fixed",
                "no_new_vulnerabilities_introduced",
            ],
        ),
    )

    bind_finding_to_rules(finding, rules)
    # Force security_fix only
    finding.applicable_rules = ["security_fix"]

    result = evaluate_promotion(finding, rules)
    assert result.state == FindingState.REJECTED
    assert result.rejected_reason is not None
    assert "verification_failed" in result.rejected_reason


# ═══════════════════════════════════════════════════════════════════════════
# Test: promote_finding — success path
# ═══════════════════════════════════════════════════════════════════════════


def test_promote_finding_transitions_verified_to_promoted() -> None:
    """promote_finding transitions VERIFIED→PROMOTED when rules allow auto-promote."""
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Cosmetic: fix typo in README",
        applicable_rules=["cosmetic"],
    )

    result = promote_finding(finding)
    assert result.state == FindingState.PROMOTED
    assert result.promotion_evidence is not None
    assert result.promotion_evidence["promoted_by"] == "explicit_promote"


# ═══════════════════════════════════════════════════════════════════════════
# Test: promote_finding — ValueError for non-VERIFIED state
# ═══════════════════════════════════════════════════════════════════════════


def test_promote_finding_raises_valueerror_for_non_verified_state() -> None:
    """promote_finding raises ValueError when finding is not in VERIFIED state."""
    finding = _make_finding(
        state=FindingState.OBSERVED,
        proposal="Some proposal",
        applicable_rules=["cosmetic"],
    )

    with pytest.raises(ValueError, match="VERIFIED"):
        promote_finding(finding)


def test_promote_finding_raises_valueerror_for_rejected_state() -> None:
    """promote_finding raises ValueError when finding is in REJECTED state."""
    finding = _make_finding(
        state=FindingState.REJECTED,
        proposal="Already rejected",
        applicable_rules=["cosmetic"],
    )
    finding.rejected_reason = "already evaluated"

    with pytest.raises(ValueError, match="VERIFIED"):
        promote_finding(finding)


# ═══════════════════════════════════════════════════════════════════════════
# Test: promote_finding — ValueError when rules require review
# ═══════════════════════════════════════════════════════════════════════════


def test_promote_finding_raises_valueerror_when_rules_require_review() -> None:
    """promote_finding raises ValueError when an applicable rule requires human review."""
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Breaking change to core API",
        applicable_rules=["breaking_change"],
    )

    with pytest.raises(ValueError, match="requires human review"):
        promote_finding(finding)


# ═══════════════════════════════════════════════════════════════════════════
# Test: rejected finding
# ═══════════════════════════════════════════════════════════════════════════


def test_rejected_finding_has_rejected_reason_set() -> None:
    """A rejected finding has a non-empty rejected_reason."""
    rules = define_standard_rules()
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Security fix attempt that fails tests",
        verification_results=_make_verification_results(
            False, ["security_tests_pass", "vulnerability_confirmed_fixed", "no_new_vulnerabilities_introduced"]
        ),
        applicable_rules=["security_fix"],
    )

    result = evaluate_promotion(finding, rules)
    assert result.state == FindingState.REJECTED
    assert result.rejected_reason is not None
    assert len(result.rejected_reason) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: promote_finding sets promotion_evidence
# ═══════════════════════════════════════════════════════════════════════════


def test_promote_finding_sets_promotion_evidence() -> None:
    """promote_finding sets promotion_evidence with promoted_at, promoted_by, and rules_applied."""
    finding = _make_finding(
        state=FindingState.VERIFIED,
        proposal="Increase test coverage by 15%",
        applicable_rules=["coverage_increase"],
    )

    result = promote_finding(finding)
    assert result.promotion_evidence is not None
    assert "promoted_at" in result.promotion_evidence
    assert "promoted_by" in result.promotion_evidence
    assert result.promotion_evidence["promoted_by"] == "explicit_promote"
    assert "rules_applied" in result.promotion_evidence
    assert "coverage_increase" in result.promotion_evidence["rules_applied"]


# ═══════════════════════════════════════════════════════════════════════════
# Test: FindingState transitions
# ═══════════════════════════════════════════════════════════════════════════


def test_finding_state_valid_transitions() -> None:
    """FindingState.can_transition_to validates the observe→propose→verify→promote flow."""
    assert FindingState.OBSERVED.can_transition_to(FindingState.PROPOSED) is True
    assert FindingState.OBSERVED.can_transition_to(FindingState.REJECTED) is True
    assert FindingState.OBSERVED.can_transition_to(FindingState.PROMOTED) is False  # skip!

    assert FindingState.PROPOSED.can_transition_to(FindingState.VERIFIED) is True
    assert FindingState.PROPOSED.can_transition_to(FindingState.REJECTED) is True

    assert FindingState.VERIFIED.can_transition_to(FindingState.PROMOTED) is True
    assert FindingState.VERIFIED.can_transition_to(FindingState.REJECTED) is True

    # Terminal states have no valid transitions
    assert FindingState.PROMOTED.can_transition_to(FindingState.VERIFIED) is False
    assert FindingState.REJECTED.can_transition_to(FindingState.PROPOSED) is False


def test_finding_state_terminal_check() -> None:
    """FindingState.is_terminal is True only for REJECTED."""
    assert FindingState.OBSERVED.is_terminal() is False
    assert FindingState.PROPOSED.is_terminal() is False
    assert FindingState.VERIFIED.is_terminal() is False
    assert FindingState.PROMOTED.is_terminal() is False
    assert FindingState.REJECTED.is_terminal() is True
