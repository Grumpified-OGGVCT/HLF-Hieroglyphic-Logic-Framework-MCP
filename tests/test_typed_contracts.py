"""Tests for typed effect algebra (B2).

Validates HlfType, EffectClass, FailureMode, ProofRequirement, ProofSurface,
TypeContract, InputContract, OutputContract, TypedEffectDeclaration,
EffectContractAssessment, and the verifier integration with FormalVerifier.
"""

from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())
os.chdir(os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from hlf_mcp.hlf.typed_contracts import (
    HlfType,
    EffectClass,
    EffectContractAssessment,
    FailureMode,
    InputContract,
    OutputContract,
    ProofRequirement,
    ProofSurface,
    TypeContract,
    TypedEffectDeclaration,
    validate_host_function_contract,
)
from hlf_mcp.hlf.formal_verifier import (
    FormalVerifier,
    VerificationResult,
    VerificationStatus,
    ConstraintKind,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HlfType
# ═══════════════════════════════════════════════════════════════════════════════

class TestHlfType:
    def test_all_glyphs_defined(self):
        for member in HlfType:
            assert member.glyph, f"{member.name} missing glyph"

    def test_string_round_trip(self):
        assert HlfType.STRING.glyph == "\U0001d54a"  # 𝕊
        assert HlfType.from_glyph("\U0001d54a") == HlfType.STRING
        assert HlfType.STRING.to_json_schema_type() == "string"

    def test_number_round_trip(self):
        assert HlfType.NUMBER.glyph == "\u2115"  # ℕ
        assert HlfType.from_glyph("\u2115") == HlfType.NUMBER
        assert HlfType.NUMBER.to_json_schema_type() == "number"

    def test_boolean_round_trip(self):
        assert HlfType.BOOLEAN.glyph == "\U0001d539"  # 𝔹
        assert HlfType.from_glyph("\U0001d539") == HlfType.BOOLEAN
        assert HlfType.BOOLEAN.to_json_schema_type() == "boolean"

    def test_json_round_trip(self):
        assert HlfType.JSON.glyph == "\U0001d541"  # 𝕁
        assert HlfType.from_glyph("\U0001d541") == HlfType.JSON
        assert HlfType.JSON.to_json_schema_type() == "object"

    def test_any_round_trip(self):
        assert HlfType.ANY.glyph == "\U0001d538"  # 𝔸
        assert HlfType.from_glyph("\U0001d538") == HlfType.ANY
        assert HlfType.ANY.to_json_schema_type() == "any"

    def test_unknown_glyph_returns_none(self):
        assert HlfType.from_glyph("X") is None

    def test_from_json_schema_type(self):
        assert HlfType.from_json_schema_type("string") == HlfType.STRING
        assert HlfType.from_json_schema_type("integer") == HlfType.INTEGER
        assert HlfType.from_json_schema_type("number") == HlfType.NUMBER
        assert HlfType.from_json_schema_type("boolean") == HlfType.BOOLEAN
        assert HlfType.from_json_schema_type("object") == HlfType.JSON
        assert HlfType.from_json_schema_type("array") == HlfType.JSON
        assert HlfType.from_json_schema_type("unknown") == HlfType.ANY


# ═══════════════════════════════════════════════════════════════════════════════
# EffectClass
# ═══════════════════════════════════════════════════════════════════════════════

class TestEffectClass:
    def test_enum_has_all_33(self):
        members = list(EffectClass)
        assert len(members) == 33, f"Expected 33 effect classes, got {len(members)}"

    def test_system_boundary_returns_nonempty(self):
        for ec in EffectClass:
            sb = ec.system_boundary()
            assert isinstance(sb, str), f"system_boundary for {ec.name} is not a string"
            assert len(sb) > 0, f"system_boundary for {ec.name} is empty"

    def test_file_read_not_mutating(self):
        assert EffectClass.FILE_READ.is_mutating() is False

    def test_file_write_is_mutating(self):
        assert EffectClass.FILE_WRITE.is_mutating() is True

    def test_memory_write_is_mutating(self):
        assert EffectClass.MEMORY_WRITE.is_mutating() is True

    def test_memory_read_not_mutating(self):
        assert EffectClass.MEMORY_READ.is_mutating() is False

    def test_local_analysis_not_mutating(self):
        assert EffectClass.LOCAL_ANALYSIS.is_mutating() is False

    def test_derived_side_effects_nonempty_for_write(self):
        se = EffectClass.FILE_WRITE.derived_side_effects()
        assert len(se) >= 1
        assert any("write" in s.lower() for s in se)

    def test_local_analysis_no_side_effects(self):
        se = EffectClass.LOCAL_ANALYSIS.derived_side_effects()
        assert se == []


# ═══════════════════════════════════════════════════════════════════════════════
# FailureMode
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailureMode:
    def test_enum_has_all_10(self):
        members = list(FailureMode)
        assert len(members) == 10, f"Expected 10 failure modes, got {len(members)}"

    def test_is_recoverable(self):
        assert FailureMode.TIMEOUT_ERROR.is_recoverable() is True
        assert FailureMode.IO_ERROR.is_recoverable() is True
        assert FailureMode.EXECUTION_ERROR.is_recoverable() is False
        assert FailureMode.MEMORY_ERROR.is_recoverable() is False

    def test_is_security_sensitive(self):
        assert FailureMode.GOVERNANCE_ERROR.is_security_sensitive() is True
        assert FailureMode.POLICY_DENIED.is_security_sensitive() is True
        assert FailureMode.VERIFICATION_ERROR.is_security_sensitive() is True
        assert FailureMode.TIMEOUT_ERROR.is_security_sensitive() is False
        assert FailureMode.NETWORK_ERROR.is_security_sensitive() is False


# ═══════════════════════════════════════════════════════════════════════════════
# ProofRequirement
# ═══════════════════════════════════════════════════════════════════════════════

class TestProofRequirement:
    def test_requires_human(self):
        assert ProofRequirement.NONE.requires_human() is False
        assert ProofRequirement.RUNTIME_CHECKED.requires_human() is False
        assert ProofRequirement.VERIFICATION_ADMITTED.requires_human() is False
        assert ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION.requires_human() is True

    def test_requires_formal_proof(self):
        assert ProofRequirement.NONE.requires_formal_proof() is False
        assert ProofRequirement.RUNTIME_CHECKED.requires_formal_proof() is False
        assert ProofRequirement.VERIFICATION_ADMITTED.requires_formal_proof() is True
        assert ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION.requires_formal_proof() is True


# ═══════════════════════════════════════════════════════════════════════════════
# ProofSurface
# ═══════════════════════════════════════════════════════════════════════════════

class TestProofSurface:
    def _make_surface(self, all_proven: bool = True, proven: int = 3, total: int = 3) -> ProofSurface:
        now_ms = int(time.time() * 1000)
        return ProofSurface(
            bundle_sha256="a" * 64,
            ast_sha256="b" * 64,
            report_sha256="c" * 64,
            solver_name="z3",
            z3_available=True,
            all_proven=all_proven,
            proven_count=proven,
            total_count=total,
            failed_count=total - proven,
            timestamp_epoch_ms=now_ms,
        )

    def test_valid_when_all_proven(self):
        ps = self._make_surface(all_proven=True, proven=3, total=3)
        assert ps.all_proven is True
        assert ps.failed_count == 0

    def test_invalid_when_not_all_proven(self):
        ps = self._make_surface(all_proven=False, proven=2, total=3)
        assert ps.all_proven is False
        assert ps.failed_count == 1

    def test_from_verification_report(self):
        report = {
            "bundle_sha256": "a" * 64,
            "ast_sha256": "b" * 64,
            "report_sha256": "c" * 64,
            "solver_name": "z3",
            "z3_available": True,
            "timestamp_epoch_ms": 1719000000000,
            "report": {
                "all_proven": True,
                "proven": 5,
                "total": 5,
                "failed": 0,
            },
        }
        ps = ProofSurface.from_verification_report(report)
        assert ps.all_proven is True
        assert ps.proven_count == 5
        assert ps.total_count == 5
        assert ps.failed_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TypeContract
# ═══════════════════════════════════════════════════════════════════════════════

def _tc(name: str, hlf_type: HlfType, required: bool = True, **kw) -> TypeContract:
    return TypeContract(
        name=name,
        hlf_type=hlf_type,
        json_schema_type=hlf_type.to_json_schema_type(),
        required=required,
        constraints=kw,
    )


class TestTypeContract:
    def test_string_valid(self):
        tc = _tc("username", HlfType.STRING)
        valid, msg = tc.validate_value("hello")
        assert valid is True

    def test_string_invalid_number(self):
        tc = _tc("username", HlfType.STRING)
        valid, msg = tc.validate_value(123)
        assert valid is False

    def test_number_valid(self):
        tc = _tc("count", HlfType.NUMBER)
        valid, msg = tc.validate_value(42)
        assert valid is True

    def test_number_invalid(self):
        tc = _tc("count", HlfType.NUMBER)
        valid, msg = tc.validate_value("xyz")
        assert valid is False

    def test_boolean_valid(self):
        tc = _tc("flag", HlfType.BOOLEAN)
        valid, msg = tc.validate_value(True)
        assert valid is True

    def test_json_valid(self):
        tc = _tc("data", HlfType.JSON)
        valid, msg = tc.validate_value({"key": "val"})
        assert valid is True

    def test_any_valid(self):
        tc = _tc("anything", HlfType.ANY)
        valid, msg = tc.validate_value(None)
        # ANY + required=True rejects None
        assert valid is False

    def test_optional_allows_none(self):
        tc = _tc("opt", HlfType.STRING, required=False)
        assert tc.required is False
        valid, msg = tc.validate_value(None)
        assert valid is True

    def test_required_rejects_none(self):
        tc = _tc("req", HlfType.STRING, required=True)
        assert tc.required is True
        valid, msg = tc.validate_value(None)
        assert valid is False

    def test_min_constraint_stored(self):
        tc = _tc("age", HlfType.NUMBER, min=0, max=150)
        assert tc.constraints.get("min") == 0
        assert tc.constraints.get("max") == 150


# ═══════════════════════════════════════════════════════════════════════════════
# InputContract
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputContract:
    def test_empty_contract_passes(self):
        ic = InputContract(function_name="noop", parameters=[])
        valid, errors = ic.validate({})
        assert valid is True
        assert errors == []

    def test_simple_contract_valid(self):
        ic = InputContract(
            function_name="greet",
            parameters=[_tc("name", HlfType.STRING)],
        )
        valid, errors = ic.validate({"name": "Alice"})
        assert valid is True
        assert errors == []

    def test_missing_required_arg(self):
        ic = InputContract(
            function_name="greet",
            parameters=[_tc("name", HlfType.STRING, required=True)],
        )
        valid, errors = ic.validate({})
        assert valid is False
        assert any("name" in e.lower() for e in errors)

    def test_wrong_type(self):
        ic = InputContract(
            function_name="add",
            parameters=[_tc("x", HlfType.NUMBER)],
        )
        valid, errors = ic.validate({"x": "not-a-number"})
        assert valid is False

    def test_from_json_schema(self):
        schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
        ic = InputContract.from_json_schema("calc", schema)
        valid, errors = ic.validate({"x": 10})
        assert valid is True

        valid2, errors2 = ic.validate({})
        assert valid2 is False


# ═══════════════════════════════════════════════════════════════════════════════
# OutputContract
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutputContract:
    def test_string_output_valid(self):
        oc = OutputContract(function_name="to_str", return_type=HlfType.STRING, output_schema={})
        assert oc.validate("hello") == (True, "")

    def test_number_output_valid(self):
        oc = OutputContract(function_name="to_num", return_type=HlfType.NUMBER, output_schema={})
        assert oc.validate(42) == (True, "")

    def test_wrong_type_fails(self):
        oc = OutputContract(function_name="to_str", return_type=HlfType.STRING, output_schema={})
        valid, err = oc.validate(123)
        assert valid is False

    def test_from_json_schema(self):
        schema = {"type": "string"}
        oc = OutputContract.from_json_schema("echo", schema)
        assert oc.validate("ok") == (True, "")


# ═══════════════════════════════════════════════════════════════════════════════
# TypedEffectDeclaration
# ═══════════════════════════════════════════════════════════════════════════════

def _make_decl(**overrides) -> TypedEffectDeclaration:
    defaults: dict = dict(
        function_name="test_fn",
        effect_class=EffectClass.LOCAL_ANALYSIS,
        input_contract=InputContract(
            function_name="test_fn",
            parameters=[_tc("query", HlfType.STRING)],
        ),
        output_contract=OutputContract(
            function_name="test_fn",
            return_type=HlfType.JSON,
            output_schema={"type": "object"},
        ),
        proof_requirement=ProofRequirement.NONE,
        failure_modes=[FailureMode.TIMEOUT_ERROR],
        review_posture="none",
        safety_class="low",
        execution_mode="inline",
        side_effects=[],
        required_evidence=[],
        egress_validation={},
        supervisory_only=False,
    )
    defaults.update(overrides)
    return TypedEffectDeclaration(**defaults)


class TestTypedEffectDeclaration:
    def test_validate_call_passes(self):
        decl = _make_decl()
        ok, errs = decl.validate_call({"query": "SELECT 1"})
        assert ok is True
        assert errs == []

    def test_validate_call_bad_input(self):
        decl = _make_decl()
        ok, errs = decl.validate_call({"query": 999})  # number instead of string
        assert ok is False
        assert len(errs) > 0

    def test_validate_call_critical_needs_proof(self):
        decl = _make_decl(
            safety_class="critical",
            proof_requirement=ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION,
        )
        ok, errs = decl.validate_call({"query": "ok"})
        # Without proof surface, critical + operator review should fail
        assert ok is False

    def test_validate_call_with_valid_proof(self):
        now_ms = int(time.time() * 1000)
        ps = ProofSurface(
            bundle_sha256="a" * 64,
            ast_sha256="b" * 64,
            report_sha256="c" * 64,
            solver_name="z3",
            z3_available=True,
            all_proven=True,
            proven_count=3,
            total_count=3,
            failed_count=0,
            timestamp_epoch_ms=now_ms,
        )
        decl = _make_decl(
            proof_requirement=ProofRequirement.VERIFICATION_ADMITTED,
        )
        ok, errs = decl.validate_call({"query": "ok"}, proof_surface=ps)
        assert ok is True

    def test_from_host_function_dummy(self):
        """Build a TypedEffectDeclaration from an object with host-function attributes."""

        class DummyHostFunction:
            name = "file.read"
            effect_class = "file_read"
            failure_type = "network_error"
            input_schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
            output_schema = {"type": "string"}
            required_proof = "none"
            audit_requirement = "none"
            safety_class = "low"
            review_posture = "none"
            execution_mode = "inline"
            side_effects = []
            required_evidence = []
            egress_validation = {}
            supervisory_only = False

        decl = TypedEffectDeclaration.from_host_function(DummyHostFunction)
        assert decl.function_name == "file.read"
        assert decl.effect_class == EffectClass.FILE_READ
        assert len(decl.failure_modes) == 1
        assert decl.failure_modes[0] == FailureMode.NETWORK_ERROR


# ═══════════════════════════════════════════════════════════════════════════════
# EffectContractAssessment
# ═══════════════════════════════════════════════════════════════════════════════

class TestEffectContractAssessment:
    def test_admitted_no_reasons(self):
        a = EffectContractAssessment(
            function_name="f",
            admitted=True,
            requires_operator_review=False,
            verdict="admitted",
            reasons=[],
            proof_surface=None,
        )
        assert a.admitted is True
        assert a.requires_operator_review is False

    def test_denied_with_reasons(self):
        a = EffectContractAssessment(
            function_name="f",
            admitted=False,
            requires_operator_review=False,
            verdict="effect_contract_denied",
            reasons=["type mismatch on arg x"],
            proof_surface=None,
        )
        assert a.admitted is False
        assert len(a.reasons) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# validate_host_function_contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateHostFunctionContract:
    def test_valid_minimal(self):
        ok, errs = validate_host_function_contract(
            function_name="tool.ping",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "string"},
            effect_class="file_read",
            failure_type="io_error",
        )
        assert ok is True
        assert errs == []

    def test_invalid_effect_class(self):
        ok, errs = validate_host_function_contract(
            function_name="tool.broken",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "string"},
            effect_class="fictional_effect",
            failure_type="none",
        )
        assert ok is False

    def test_invalid_failure_type(self):
        ok, errs = validate_host_function_contract(
            function_name="tool.broken2",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "string"},
            effect_class="file_read",
            failure_type="nonesense",
        )
        assert ok is False


# ═══════════════════════════════════════════════════════════════════════════════
# Verifier integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifierEffectContractIntegration:
    @pytest.fixture
    def verifier(self):
        return FormalVerifier()

    @pytest.fixture
    def simple_decl(self):
        return TypedEffectDeclaration(
            function_name="math.add",
            effect_class=EffectClass.LOCAL_ANALYSIS,
            input_contract=InputContract(
                function_name="math.add",
                parameters=[
                    _tc("a", HlfType.NUMBER),
                    _tc("b", HlfType.NUMBER),
                ],
            ),
            output_contract=OutputContract(
                function_name="math.add",
                return_type=HlfType.NUMBER,
                output_schema={"type": "number"},
            ),
            proof_requirement=ProofRequirement.NONE,
            failure_modes=[FailureMode.VALIDATION_ERROR],
            review_posture="none",
            safety_class="low",
            execution_mode="inline",
            side_effects=[],
            required_evidence=[],
            egress_validation={},
            supervisory_only=False,
        )

    def test_pure_function_admitted(self, verifier, simple_decl):
        assessment = verifier.verify_effect_declaration(
            simple_decl,
            args={"a": 1, "b": 2},
        )
        assert assessment.admitted is True

    def test_type_mismatch_detected(self, verifier, simple_decl):
        assessment = verifier.verify_effect_declaration(
            simple_decl,
            args={"a": "not-a-number", "b": 2},
        )
        assert assessment.admitted is False

    def test_proof_required_without_surface(self, verifier):
        decl = TypedEffectDeclaration(
            function_name="admin.delete",
            effect_class=EffectClass.FILE_WRITE,
            input_contract=InputContract(function_name="admin.delete", parameters=[]),
            output_contract=OutputContract(
                function_name="admin.delete",
                return_type=HlfType.BOOLEAN,
                output_schema={"type": "boolean"},
            ),
            proof_requirement=ProofRequirement.VERIFICATION_ADMITTED,
            failure_modes=[FailureMode.EXECUTION_ERROR],
            review_posture="none",
            safety_class="critical",
            execution_mode="replay_only",
            side_effects=[],
            required_evidence=[],
            egress_validation={},
            supervisory_only=False,
        )
        assessment = verifier.verify_effect_declaration(decl)
        assert assessment.admitted is False
        assert any("proof surface" in r.lower() for r in assessment.reasons)

    def test_mutating_effect_without_review(self, verifier):
        decl = TypedEffectDeclaration(
            function_name="db.write",
            effect_class=EffectClass.MEMORY_WRITE,
            input_contract=InputContract(function_name="db.write", parameters=[]),
            output_contract=OutputContract(
                function_name="db.write",
                return_type=HlfType.BOOLEAN,
                output_schema={"type": "boolean"},
            ),
            proof_requirement=ProofRequirement.NONE,
            failure_modes=[FailureMode.TIMEOUT_ERROR],
            review_posture="none",
            safety_class="low",
            execution_mode="inline",
            side_effects=[],
            required_evidence=[],
            egress_validation={},
            supervisory_only=False,
        )
        assessment = verifier.verify_effect_declaration(decl)
        assert assessment.admitted is False
        assert any("mutating" in r.lower() for r in assessment.reasons)

    def test_security_sensitive_failure_without_safety(self, verifier):
        decl = TypedEffectDeclaration(
            function_name="auth.validate",
            effect_class=EffectClass.LOCAL_ANALYSIS,
            input_contract=InputContract(function_name="auth.validate", parameters=[]),
            output_contract=OutputContract(
                function_name="auth.validate",
                return_type=HlfType.BOOLEAN,
                output_schema={"type": "boolean"},
            ),
            proof_requirement=ProofRequirement.NONE,
            failure_modes=[FailureMode.POLICY_DENIED],
            review_posture="none",
            safety_class="low",  # too low for security-sensitive failure
            execution_mode="inline",
            side_effects=[],
            required_evidence=[],
            egress_validation={},
            supervisory_only=False,
        )
        assessment = verifier.verify_effect_declaration(decl)
        assert assessment.admitted is False

    def test_verify_output_contract(self, verifier):
        oc = OutputContract(
            function_name="greet",
            return_type=HlfType.STRING,
            output_schema={"type": "string"},
        )
        result = verifier.verify_output_contract(oc, "hello")
        assert result.status == VerificationStatus.RUNTIME_CHECKED

        result2 = verifier.verify_output_contract(oc, 123)
        assert result2.status == VerificationStatus.COUNTEREXAMPLE
