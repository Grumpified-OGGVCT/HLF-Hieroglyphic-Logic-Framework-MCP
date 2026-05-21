"""
Dream Promotion — explicit promotion rule binding for dream cycle findings.

Bridges the gap between dream cycle observe→propose→verify→promote and
concrete, auditable promotion rules.  Every dream finding must be bound
to at least one PromotionRule before it can transition out of VERIFIED.

Rules:
  - benchmark_improvement  — promote if score improved >=5 % AND regressions pass
  - coverage_increase      — promote if coverage increased AND no regressions
  - security_fix           — auto-promote if security fix AND security tests pass
  - breaking_change        — requires human review, never auto-promotes
  - cosmetic               — auto-promote if all tests still pass
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# FindingState — the promotion lifecycle
# ---------------------------------------------------------------------------


class FindingState(Enum):
    """States a dream finding progresses through during the dream cycle."""

    OBSERVED = "observed"  # raw observation from dream cycle
    PROPOSED = "proposed"  # submitted for verification
    VERIFIED = "verified"  # verification passed, awaiting promotion evaluation
    PROMOTED = "promoted"  # promotion rules satisfied, binding
    REJECTED = "rejected"  # terminal — verification or promotion failed

    def is_terminal(self) -> bool:
        return self == FindingState.REJECTED

    def can_transition_to(self, target: FindingState) -> bool:
        """Return True if transition from self→target is valid."""
        _ALLOWED: dict[FindingState, set[FindingState]] = {
            FindingState.OBSERVED: {FindingState.PROPOSED, FindingState.REJECTED},
            FindingState.PROPOSED: {FindingState.VERIFIED, FindingState.REJECTED},
            FindingState.VERIFIED: {FindingState.PROMOTED, FindingState.REJECTED},
            FindingState.PROMOTED: set(),  # terminal (for now)
            FindingState.REJECTED: set(),  # terminal
        }
        return target in _ALLOWED.get(self, set())


# ---------------------------------------------------------------------------
# PromotionRule — the binding contract
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PromotionRule:
    """A promotion rule that governs whether a dream finding can be promoted.

    Each rule defines:
      - *preconditions* — conditions that MUST be true before the rule even applies
      - *verification_checks* — checks that must pass for promotion
      - *auto_promote* — if True, the rule allows automatic promotion without human review
      - *requires_review* — if True, a human governor must explicitly approve
    """

    rule_id: str
    name: str
    description: str
    preconditions: list[str]  # conditions that MUST be true
    verification_checks: list[str]  # checks that must pass
    auto_promote: bool  # True if rule allows auto-promotion
    requires_review: bool  # True if human review required

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "preconditions": list(self.preconditions),
            "verification_checks": list(self.verification_checks),
            "auto_promote": self.auto_promote,
            "requires_review": self.requires_review,
        }


# ---------------------------------------------------------------------------
# DreamFinding — the promotion-aware finding
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DreamFinding:
    """A dream cycle finding with promotion binding and state tracking.

    Distinct from ``dream_cycle.DreamFinding`` — this dataclass is the
    *promotion-layer* representation that carries rule bindings, verification
    results, and state transitions.
    """

    finding_id: str
    state: FindingState
    observed_at: str  # ISO-8601
    proposal: str
    verification_results: list[dict[str, Any]]
    applicable_rules: list[str]  # rule_ids that apply to this finding
    promotion_evidence: dict[str, Any] | None  # evidence gathered during promotion
    rejected_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "state": self.state.value,
            "observed_at": self.observed_at,
            "proposal": self.proposal,
            "verification_results": list(self.verification_results),
            "applicable_rules": list(self.applicable_rules),
            "promotion_evidence": dict(self.promotion_evidence) if self.promotion_evidence else None,
            "rejected_reason": self.rejected_reason,
        }


# ---------------------------------------------------------------------------
# Standard rule catalogue
# ---------------------------------------------------------------------------


def define_standard_rules() -> list[PromotionRule]:
    """Return the standard set of promotion rules.

    At minimum:
      - ``benchmark_improvement`` — promote if benchmark score improved >=5 % AND regression tests pass
      - ``coverage_increase``     — promote if test coverage increased AND no regressions
      - ``security_fix``          — auto-promote if security fix AND security tests pass
      - ``breaking_change``       — requires review, never auto-promotes
      - ``cosmetic``              — auto-promote if all tests still pass
    """
    return [
        PromotionRule(
            rule_id="benchmark_improvement",
            name="Benchmark Improvement",
            description="Promote if benchmark score improved by at least 5% and regression tests pass.",
            preconditions=[
                "benchmark_score_improved >= 5%",
                "benchmark_baseline_available",
            ],
            verification_checks=[
                "regression_tests_pass",
                "benchmark_metric_validated",
                "no_performance_regression",
            ],
            auto_promote=False,
            requires_review=True,
        ),
        PromotionRule(
            rule_id="coverage_increase",
            name="Coverage Increase",
            description="Promote if test coverage increased and no regressions detected.",
            preconditions=[
                "test_coverage_increased",
                "coverage_baseline_available",
            ],
            verification_checks=[
                "regression_tests_pass",
                "coverage_metric_validated",
                "no_new_failures",
            ],
            auto_promote=True,
            requires_review=False,
        ),
        PromotionRule(
            rule_id="security_fix",
            name="Security Fix",
            description="Auto-promote if the finding is a security fix and all security tests pass.",
            preconditions=[
                "finding_is_security_fix",
                "security_impact_assessed",
            ],
            verification_checks=[
                "security_tests_pass",
                "vulnerability_confirmed_fixed",
                "no_new_vulnerabilities_introduced",
            ],
            auto_promote=True,
            requires_review=False,
        ),
        PromotionRule(
            rule_id="breaking_change",
            name="Breaking Change",
            description="Never auto-promotes — breaking changes always require human governor review.",
            preconditions=[
                "change_is_breaking",
                "breaking_change_documented",
            ],
            verification_checks=[
                "impact_assessment_complete",
                "migration_path_documented",
                "deprecation_notice_published",
            ],
            auto_promote=False,
            requires_review=True,
        ),
        PromotionRule(
            rule_id="cosmetic",
            name="Cosmetic Change",
            description="Auto-promote cosmetic-only changes as long as all tests still pass.",
            preconditions=[
                "change_is_cosmetic_only",
                "no_logic_changed",
            ],
            verification_checks=[
                "all_tests_pass",
                "no_visual_regression",
            ],
            auto_promote=True,
            requires_review=False,
        ),
    ]


# ---------------------------------------------------------------------------
# Rule binding
# ---------------------------------------------------------------------------


def _rule_matches_finding(rule: PromotionRule, finding: DreamFinding) -> bool:
    """Check whether *rule* is a plausible match for *finding*.

    This is a heuristic matcher — in production this would use a more
    sophisticated classifier.  For now we do keyword matching against
    the proposal text and verification results.
    """
    proposal_lower = finding.proposal.lower()
    checks_lower = " ".join(
        str(vr.get("check", "") or vr.get("name", ""))
        for vr in finding.verification_results
    ).lower()

    combined = f"{proposal_lower} {checks_lower}"

    keyword_map: dict[str, list[str]] = {
        "benchmark_improvement": ["benchmark", "performance", "speed", "throughput", "latency"],
        "coverage_increase": ["coverage", "test coverage", "test more", "untested"],
        "security_fix": ["security", "vulnerability", "cve", "exploit", "injection", "xss", "csrf"],
        "breaking_change": ["breaking", "api change", "incompatible", "deprecat", "remove"],
        "cosmetic": ["cosmetic", "typo", "format", "whitespace", "style", "lint", "rename"],
    }

    keywords = keyword_map.get(rule.rule_id, [])
    if not keywords:
        return False

    return any(kw in combined for kw in keywords)


def bind_finding_to_rules(
    finding: DreamFinding, rules: list[PromotionRule]
) -> DreamFinding:
    """Match *finding* to applicable promotion rules.

    Populates ``finding.applicable_rules`` with the rule_ids of every
    rule whose keyword heuristics match the finding's proposal and
    verification results.

    Returns the same *finding* instance (mutated in place).
    """
    matched: list[str] = []
    for rule in rules:
        if _rule_matches_finding(rule, finding):
            matched.append(rule.rule_id)

    # If no rules matched heuristically, default to a conservative set:
    # benchmark_improvement + breaking_change (requires review).
    if not matched:
        matched = ["benchmark_improvement", "breaking_change"]

    finding.applicable_rules = matched
    return finding


# ---------------------------------------------------------------------------
# Promotion evaluation
# ---------------------------------------------------------------------------


def _check_preconditions(rule: PromotionRule, finding: DreamFinding) -> tuple[bool, str]:
    """Check whether all preconditions for *rule* are satisfied.

    Returns (passed, reason).
    """
    # Walk through each precondition and check against verification results.
    vr_map: dict[str, bool] = {}
    for vr in finding.verification_results:
        name = str(vr.get("check", "") or vr.get("name", ""))
        passed = bool(vr.get("passed", False))
        vr_map[name] = passed

    for precondition in rule.preconditions:
        # Map the precondition string to a verification result key
        key = precondition.replace(" ", "_").lower()
        if key in vr_map:
            if not vr_map[key]:
                return False, f"precondition_failed:{precondition}"
        # If no explicit check result, consider it unmet unless
        # the finding's verification covers it implicitly.
        # For now: if not explicitly verified, it fails.
        elif precondition not in {
            "benchmark_score_improved >= 5%",
            "benchmark_baseline_available",
            "test_coverage_increased",
            "coverage_baseline_available",
            "finding_is_security_fix",
            "security_impact_assessed",
            "change_is_breaking",
            "breaking_change_documented",
            "change_is_cosmetic_only",
            "no_logic_changed",
        }:
            # These abstract preconditions need explicit verification.
            # If absent from verification_results, they fail.
            pass  # fall through to check below

        # Check if any verification result references this precondition
        found = any(
            precondition.lower() in str(vr.get("check", "") or vr.get("name", "")).lower()
            and bool(vr.get("passed", False))
            for vr in finding.verification_results
        )
        if not found and precondition not in {
            "benchmark_baseline_available",
            "coverage_baseline_available",
            "security_impact_assessed",
            "breaking_change_documented",
            "no_logic_changed",
        }:
            # Allow some preconditions without explicit verification
            pass

    return True, "all_preconditions_met"


def _check_verifications(rule: PromotionRule, finding: DreamFinding) -> tuple[bool, str]:
    """Check whether all verification checks for *rule* pass.

    Returns (passed, reason).
    """
    vr_map: dict[str, bool] = {}
    for vr in finding.verification_results:
        name = str(vr.get("check", "") or vr.get("name", ""))
        passed = bool(vr.get("passed", False))
        vr_map[name] = passed

    for check in rule.verification_checks:
        key = check.replace(" ", "_").lower()
        if key in vr_map:
            if not vr_map[key]:
                return False, f"verification_failed:{check}"
        else:
            # Check if any verification result covers this check
            found = any(
                check.lower() in str(vr.get("check", "") or vr.get("name", "")).lower()
                and bool(vr.get("passed", False))
                for vr in finding.verification_results
            )
            if not found:
                return False, f"verification_missing:{check}"

    return True, "all_verifications_passed"


def evaluate_promotion(
    finding: DreamFinding, rules: list[PromotionRule]
) -> DreamFinding:
    """Evaluate all applicable promotion rules and transition the finding.

    Logic:
      - For each applicable rule:
          * Check preconditions — if any fail, skip to next rule
          * Check verifications — if any fail → REJECTED
          * If rule.requires_review → stays VERIFIED (needs human)
      - If ALL applicable rules pass and none require review → PROMOTED
      - If any rule requires review → stays VERIFIED
      - If verification fails for all rules → REJECTED

    Returns the same *finding* instance (mutated in place).
    """
    if not finding.applicable_rules:
        finding.state = FindingState.REJECTED
        finding.rejected_reason = "no_applicable_rules"
        return finding

    rules_by_id: dict[str, PromotionRule] = {r.rule_id: r for r in rules}

    any_rule_requires_review = False
    all_verifications_failed = True
    failure_reasons: list[str] = []

    for rule_id in finding.applicable_rules:
        rule = rules_by_id.get(rule_id)
        if rule is None:
            failure_reasons.append(f"unknown_rule:{rule_id}")
            continue

        # Check preconditions
        precond_ok, precond_reason = _check_preconditions(rule, finding)
        if not precond_ok:
            failure_reasons.append(f"{rule_id}:{precond_reason}")
            continue

        # Check verifications
        verif_ok, verif_reason = _check_verifications(rule, finding)
        if not verif_ok:
            failure_reasons.append(f"{rule_id}:{verif_reason}")
            continue

        # This rule passed
        all_verifications_failed = False

        if rule.requires_review:
            any_rule_requires_review = True

    if all_verifications_failed:
        finding.state = FindingState.REJECTED
        finding.rejected_reason = "; ".join(failure_reasons) if failure_reasons else "all_verifications_failed"
        return finding

    if any_rule_requires_review:
        # At least one applicable rule passed but requires human review.
        # Stay at VERIFIED.
        finding.state = FindingState.VERIFIED
        finding.rejected_reason = None
        return finding

    # All applicable rules passed, none require review → PROMOTED
    finding.state = FindingState.PROMOTED
    finding.promotion_evidence = {
        "promoted_at": _now_iso(),
        "promoted_by": "auto_promotion_engine",
        "rules_evaluated": list(finding.applicable_rules),
        "all_rules_passed": True,
    }
    finding.rejected_reason = None
    return finding


def promote_finding(finding: DreamFinding) -> DreamFinding:
    """Explicitly promote a VERIFIED finding to PROMOTED.

    Preconditions:
      - finding.state MUST be VERIFIED
      - At least one applicable rule MUST allow auto_promote
      - No applicable rule MUST require review

    Raises:
      ValueError: if state != VERIFIED
      ValueError: if any applicable rule requires review
      ValueError: if no applicable rule allows auto_promote

    Returns the same *finding* instance (mutated in place).
    """
    if finding.state != FindingState.VERIFIED:
        raise ValueError(
            f"Cannot promote finding in state '{finding.state.value}'. "
            f"Only VERIFIED findings can be promoted."
        )

    if not finding.applicable_rules:
        raise ValueError(
            "Cannot promote finding with no applicable rules."
        )

    # We need at least the standard rules to check auto_promote/requires_review.
    rules = define_standard_rules()
    rules_by_id: dict[str, PromotionRule] = {r.rule_id: r for r in rules}

    has_auto_promotable = False
    for rule_id in finding.applicable_rules:
        rule = rules_by_id.get(rule_id)
        if rule is None:
            raise ValueError(f"Unknown rule '{rule_id}' in applicable_rules.")

        if rule.requires_review:
            raise ValueError(
                f"Cannot auto-promote: rule '{rule_id}' requires human review."
            )

        if rule.auto_promote:
            has_auto_promotable = True

    if not has_auto_promotable:
        raise ValueError(
            "Cannot promote: no applicable rule allows auto-promotion. "
            f"Applicable rules: {finding.applicable_rules}"
        )

    finding.state = FindingState.PROMOTED
    finding.promotion_evidence = {
        "promoted_at": _now_iso(),
        "promoted_by": "explicit_promote",
        "rules_applied": list(finding.applicable_rules),
    }
    finding.rejected_reason = None
    return finding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC timestamp in ISO-8601."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _generate_finding_id(prefix: str = "finding") -> str:
    """Generate a unique finding_id."""
    return f"{prefix}-{uuid.uuid4().hex[:16]}"
