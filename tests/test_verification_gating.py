"""
Integration tests for constitutive verification gating (Phase 3).

Tests that VerificationGate, GateDecision, and VerificationBlockedError
correctly implement tier-differentiated gating:
  - Hearth tier: any counterexample or unknown → BLOCK
  - Forge tier: counterexample → BLOCK, unknown → WARN
  - Sovereign tier: always PROCEED
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.formal_verifier import (
    FormalVerifier,
    VerificationGate,
    GateDecision,
    VerificationBlockedError,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
    ConstraintKind,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tier normalization
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "tier,expected",
    [
        ("hearth", "hearth"),
        ("trusted", "hearth"),
        ("approved", "forge"),
        ("watched", "forge"),
        ("forge", "forge"),
        ("untrusted", "sovereign"),
        ("advisory", "sovereign"),
        ("sovereign", "sovereign"),
        ("unknown_tier", "sovereign"),
        ("", "sovereign"),
    ],
)
def test_tier_normalization(tier: str, expected: str) -> None:
    assert VerificationGate._normalize_tier(tier) == expected


# ═══════════════════════════════════════════════════════════════════════════════
# GateDecision constants
# ═══════════════════════════════════════════════════════════════════════════════


def test_gate_decision_constants_are_distinct() -> None:
    assert GateDecision.PROCEED == "proceed"
    assert GateDecision.BLOCK == "block"
    assert GateDecision.WARN == "warn"
    assert GateDecision.PROCEED != GateDecision.BLOCK
    assert GateDecision.BLOCK != GateDecision.WARN


# ═══════════════════════════════════════════════════════════════════════════════
# VerificationBlockedError
# ═══════════════════════════════════════════════════════════════════════════════


def test_verification_blocked_error_contains_report_and_tier() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.COUNTEREXAMPLE,
            ConstraintKind.RANGE_CHECK,
            message="Value out of bounds",
        )
    )
    error = VerificationBlockedError(report, "hearth")

    assert error.report is report
    assert error.tier == "hearth"
    assert "1 issues" in str(error)
    assert "hearth" in str(error)


# ═══════════════════════════════════════════════════════════════════════════════
# Hearth tier: strictest gating — any failure → BLOCK
# ═══════════════════════════════════════════════════════════════════════════════


def test_hearth_tier_blocks_on_counterexample() -> None:
    """At hearth tier, a counterexample → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.COUNTEREXAMPLE,
            ConstraintKind.RANGE_CHECK,
            message="Out of range",
        )
    )
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.BLOCK


def test_hearth_tier_blocks_on_unknown() -> None:
    """At hearth tier, unknown results → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "type_check",
            VerificationStatus.UNKNOWN,
            ConstraintKind.TYPE_INVARIANT,
            message="Unknown type",
        )
    )
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.BLOCK


def test_hearth_tier_blocks_on_skipped() -> None:
    """At hearth tier, skipped results → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "constraint",
            VerificationStatus.SKIPPED,
            ConstraintKind.CUSTOM,
            message="Skipped",
        )
    )
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.BLOCK


def test_hearth_tier_blocks_on_empty_report() -> None:
    """At hearth tier, empty report → BLOCK."""
    report = VerificationReport()
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.BLOCK


def test_hearth_tier_proceeds_on_all_proven() -> None:
    """At hearth tier, all-proven → PROCEED."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.PROVEN,
            ConstraintKind.RANGE_CHECK,
            message="Within range",
        )
    )
    report.add(
        VerificationResult(
            "type_check",
            VerificationStatus.PROVEN,
            ConstraintKind.TYPE_INVARIANT,
            message="Type matches",
        )
    )
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.PROCEED


def test_hearth_tier_blocks_on_error() -> None:
    """At hearth tier, errors → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.ERROR,
            ConstraintKind.RANGE_CHECK,
            message="Verification error",
        )
    )
    decision = VerificationGate.gate(report, "hearth")
    assert decision == GateDecision.BLOCK


# ═══════════════════════════════════════════════════════════════════════════════
# Forge / Standard tier: counterexample → BLOCK, unknown → WARN
# ═══════════════════════════════════════════════════════════════════════════════


def test_forge_tier_blocks_on_counterexample() -> None:
    """At forge tier, a counterexample → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.COUNTEREXAMPLE,
            ConstraintKind.RANGE_CHECK,
            message="Out of range",
        )
    )
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.BLOCK


def test_forge_tier_warns_on_unknown() -> None:
    """At forge tier, unknown → WARN (not BLOCK)."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "type_check",
            VerificationStatus.UNKNOWN,
            ConstraintKind.TYPE_INVARIANT,
            message="Unknown type",
        )
    )
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.WARN


def test_forge_tier_warns_on_skipped() -> None:
    """At forge tier, skipped → WARN (not BLOCK)."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "constraint",
            VerificationStatus.SKIPPED,
            ConstraintKind.CUSTOM,
            message="Skipped",
        )
    )
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.WARN


def test_forge_tier_warns_on_empty() -> None:
    """At forge tier, empty → WARN."""
    report = VerificationReport()
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.WARN


def test_forge_tier_proceeds_on_all_proven() -> None:
    """At forge tier, all-proven → PROCEED."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.PROVEN,
            ConstraintKind.RANGE_CHECK,
            message="Within range",
        )
    )
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.PROCEED


def test_forge_tier_blocks_on_error() -> None:
    """At forge tier, errors → BLOCK."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.ERROR,
            ConstraintKind.RANGE_CHECK,
            message="Verification error",
        )
    )
    decision = VerificationGate.gate(report, "forge")
    assert decision == GateDecision.BLOCK


# ═══════════════════════════════════════════════════════════════════════════════
# Sovereign / Advisory tier: always PROCEED
# ═══════════════════════════════════════════════════════════════════════════════


def test_sovereign_tier_proceeds_on_counterexample() -> None:
    """At sovereign tier, counterexample → PROCEED (advisory)."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.COUNTEREXAMPLE,
            ConstraintKind.RANGE_CHECK,
            message="Out of range",
        )
    )
    decision = VerificationGate.gate(report, "sovereign")
    assert decision == GateDecision.PROCEED


def test_sovereign_tier_proceeds_on_unknown() -> None:
    """At sovereign tier, unknown → PROCEED."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "type_check",
            VerificationStatus.UNKNOWN,
            ConstraintKind.TYPE_INVARIANT,
            message="Unknown type",
        )
    )
    decision = VerificationGate.gate(report, "sovereign")
    assert decision == GateDecision.PROCEED


def test_sovereign_tier_proceeds_on_empty() -> None:
    """At sovereign tier, empty → PROCEED."""
    report = VerificationReport()
    decision = VerificationGate.gate(report, "sovereign")
    assert decision == GateDecision.PROCEED


def test_sovereign_tier_proceeds_on_error() -> None:
    """At sovereign tier, errors → PROCEED (advisory only)."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "range_check",
            VerificationStatus.ERROR,
            ConstraintKind.RANGE_CHECK,
            message="Verification error",
        )
    )
    decision = VerificationGate.gate(report, "sovereign")
    assert decision == GateDecision.PROCEED


# ═══════════════════════════════════════════════════════════════════════════════
# VerificationReport.blocked_count
# ═══════════════════════════════════════════════════════════════════════════════


def test_blocked_count_counts_counterexamples() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult(
            "ce1", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK
        )
    )
    report.add(
        VerificationResult(
            "ce2", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.TYPE_INVARIANT
        )
    )
    assert report.blocked_count == 2


def test_blocked_count_counts_unknown_and_skipped() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult("u1", VerificationStatus.UNKNOWN, ConstraintKind.CUSTOM)
    )
    report.add(
        VerificationResult("s1", VerificationStatus.SKIPPED, ConstraintKind.CUSTOM)
    )
    assert report.blocked_count == 2


def test_blocked_count_ignores_proven() -> None:
    report = VerificationReport()
    report.add(
        VerificationResult("p1", VerificationStatus.PROVEN, ConstraintKind.RANGE_CHECK)
    )
    report.add(
        VerificationResult(
            "rt1", VerificationStatus.RUNTIME_CHECKED, ConstraintKind.TYPE_INVARIANT
        )
    )
    assert report.blocked_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# FormalVerifier.verify() — integrated gated path
# ═══════════════════════════════════════════════════════════════════════════════


def test_verify_method_returns_proceed_for_provable_program() -> None:
    """A program with a provable constraint → PROCEED at hearth tier."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "x", "value": 5},
        ]
    }
    report, decision = verifier.verify(ast, trust_tier="hearth")
    assert isinstance(report, VerificationReport)
    assert decision == GateDecision.PROCEED


def test_verify_method_returns_block_for_counterexample_at_hearth() -> None:
    """A program with a counterexample → BLOCK at hearth tier."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "temperature", "value": 7},
            {"tag": "CONSTRAINT", "arguments": [
                {"kind": "kv_arg", "name": "name", "value": {"kind": "value", "type": "ident", "value": "temp_range"}},
                {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
            ]},
        ]
    }
    report, decision = verifier.verify(ast, trust_tier="hearth")
    assert isinstance(report, VerificationReport)
    assert decision == GateDecision.BLOCK
    assert report.failed_count >= 1


def test_verify_method_advisory_tier_always_proceeds() -> None:
    """Even with counterexamples, advisory tier → PROCEED."""
    verifier = FormalVerifier()
    ast = {
        "program": [
            {"tag": "SET", "name": "temperature", "value": 7},
            {"tag": "CONSTRAINT", "arguments": [
                {"kind": "kv_arg", "name": "name", "value": {"kind": "value", "type": "ident", "value": "temp_range"}},
                {"kind": "kv_arg", "name": "min", "value": {"kind": "value", "type": "number", "value": 1}},
                {"kind": "kv_arg", "name": "max", "value": {"kind": "value", "type": "number", "value": 5}},
                {"kind": "kv_arg", "name": "value", "value": {"kind": "value", "type": "number", "value": 7}},
            ]},
        ]
    }
    report, decision = verifier.verify(ast, trust_tier="advisory")
    assert isinstance(report, VerificationReport)
    assert decision == GateDecision.PROCEED
    # The report still shows the failure — it's just not gated
    assert report.failed_count >= 1


def test_verify_method_empty_ast_blocks_at_hearth() -> None:
    """Empty AST → BLOCK at hearth tier (no constraints extracted)."""
    verifier = FormalVerifier()
    ast = {"program": []}
    report, decision = verifier.verify(ast, trust_tier="hearth")
    assert decision == GateDecision.BLOCK
    assert report.blocked_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tier aliases
# ═══════════════════════════════════════════════════════════════════════════════


def test_trusted_is_same_as_hearth() -> None:
    """'trusted' tier normalizes to hearth behavior."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "ce", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK
        )
    )
    assert VerificationGate.gate(report, "trusted") == GateDecision.BLOCK


def test_approved_is_same_as_forge() -> None:
    """'approved' tier normalizes to forge behavior."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "u", VerificationStatus.UNKNOWN, ConstraintKind.CUSTOM
        )
    )
    assert VerificationGate.gate(report, "approved") == GateDecision.WARN


def test_watched_is_same_as_forge() -> None:
    """'watched' tier normalizes to forge behavior."""
    report = VerificationReport()
    report.add(
        VerificationResult(
            "ce", VerificationStatus.COUNTEREXAMPLE, ConstraintKind.RANGE_CHECK
        )
    )
    assert VerificationGate.gate(report, "watched") == GateDecision.BLOCK
