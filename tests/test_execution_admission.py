from __future__ import annotations

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.execution_admission import evaluate_verifier_admission
from hlf_mcp.hlf.formal_verifier import ConstraintKind
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.formal_verifier import VerificationReport
from hlf_mcp.hlf.formal_verifier import VerificationResult
from hlf_mcp.hlf.formal_verifier import VerificationStatus
from hlf_mcp.hlf.runtime import HLFRuntime


def test_execution_admission_denies_counterexample() -> None:
    verifier = FormalVerifier()

    decision = evaluate_verifier_admission(
        {
            "statements": [
                {
                    "tag": "PARALLEL",
                    "tasks": [{} for _ in range(101)],
                }
            ]
        },
        verifier=verifier,
        tier="hearth",
    )

    assert decision.admitted is False
    assert decision.verdict == "verification_denied"
    assert decision.report["failed"] == 1


def test_runtime_blocks_when_verification_admission_denies() -> None:
    source = '[HLF-v3]\nΔ [INTENT] goal="sealed-run"\nЖ [ASSERT] status="ok"\n∇ [RESULT] message="sealed"\nΩ\n'
    compiler = HLFCompiler()
    bytecoder = HLFBytecode()
    compiled = compiler.compile(source)
    bytecode = bytecoder.encode(compiled["ast"])

    result = HLFRuntime().run(
        bytecode,
        ast=compiled["ast"],
        source=source,
        verification_admission={
            "admitted": False,
            "verdict": "verification_denied",
            "reasons": ["Counterexample found during proof preflight."],
        },
    )

    assert result["status"] == "verification_blocked"
    assert result["gas_used"] == 0
    assert result["verification"]["verdict"] == "verification_denied"


def test_execution_admission_denies_false_spec_gate_literal() -> None:
    compiler = HLFCompiler()
    verifier = FormalVerifier()
    compiled = compiler.compile('[HLF-v3]\nSPEC_GATE [MIGRATION] rollback_on_fail=false\nΩ\n')

    decision = evaluate_verifier_admission(
        compiled["ast"],
        verifier=verifier,
        tier="forge",
    )

    assert decision.admitted is False
    assert decision.verdict == "verification_denied"
    assert decision.report["failed"] == 1


def test_execution_admission_keeps_unknown_read_only_hearth_as_warning(monkeypatch) -> None:
    verifier = FormalVerifier()
    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="unresolved_read_only",
            status=VerificationStatus.UNKNOWN,
            kind=ConstraintKind.CUSTOM,
            message="read-only proof remained incomplete",
        )
    )
    monkeypatch.setattr(verifier, "verify_constraints", lambda ast: report)

    decision = evaluate_verifier_admission(
        {"statements": [{"tag": "SET", "name": "note", "value": "ok"}]},
        verifier=verifier,
        tier="hearth",
        trust_state="healthy",
    )

    assert decision.admitted is True
    assert decision.requires_operator_review is False
    assert decision.verdict == "verification_warning"
    assert decision.operation_class == "read_only"
    assert decision.policy_posture == "warning"


def test_execution_admission_routes_unknown_effectful_probation_into_review(monkeypatch) -> None:
    verifier = FormalVerifier()
    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="unresolved_effectful",
            status=VerificationStatus.UNKNOWN,
            kind=ConstraintKind.CUSTOM,
            message="effectful proof remained incomplete",
        )
    )
    monkeypatch.setattr(verifier, "verify_constraints", lambda ast: report)

    decision = evaluate_verifier_admission(
        {"statements": [{"tag": "ACTION", "goal": "execute"}]},
        verifier=verifier,
        tier="hearth",
        trust_state="probation",
    )

    assert decision.admitted is False
    assert decision.requires_operator_review is True
    assert decision.verdict == "verification_review_required"
    assert decision.operation_class == "effectful"
    assert "trust_probation" in decision.risk_factors


def test_execution_admission_routes_skipped_delegated_forge_into_review(monkeypatch) -> None:
    verifier = FormalVerifier()
    report = VerificationReport()
    report.add(
        VerificationResult(
            property_name="delegated_lane",
            status=VerificationStatus.SKIPPED,
            kind=ConstraintKind.CUSTOM,
            message="no deterministic delegated proof contract was extracted",
        )
    )
    monkeypatch.setattr(verifier, "verify_constraints", lambda ast: report)

    decision = evaluate_verifier_admission(
        {"statements": [{"tag": "DELEGATE", "agent": "scribe", "goal": "execute"}]},
        verifier=verifier,
        tier="hearth",
        requested_tier="forge",
        trust_state="healthy",
    )

    assert decision.admitted is False
    assert decision.requires_operator_review is True
    assert decision.verdict == "verification_review_required"
    assert decision.operation_class == "delegated"
    assert "elevated_tier" in decision.risk_factors
