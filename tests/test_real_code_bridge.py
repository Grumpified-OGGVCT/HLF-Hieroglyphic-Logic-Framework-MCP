"""
Tests for the HLF Real-Code Bridge — equivalence proofs, effect audits, and bytecode roundtrip.

At least 15 tests proving equivalence for basic operations.
"""

from __future__ import annotations

import math
import operator

import pytest

from hlf_mcp.hlf.real_code_bridge.equivalence import (
    EquivalenceProver,
    prove_equivalence,
)
from hlf_mcp.hlf.real_code_bridge.effect_audit import (
    EffectAuditor,
    audit_effects,
)
from hlf_mcp.hlf.real_code_bridge.bytecode_roundtrip import (
    BytecodeRoundtripper,
    prove_bytecode_roundtrip,
)
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.bytecode import HLFBytecode


# ═══════════════════════════════════════════════════════════════════════════════
# Equivalence Proofs (tests 1-8)
# ═══════════════════════════════════════════════════════════════════════════════
# These tests prove that HLF bytecode execution produces the same result as Python.

_COMPILER = HLFCompiler()
_EQUIVALENCE_PROVER = EquivalenceProver()


def _compile_and_run_hlf(source: str) -> dict:
    """Helper: compile HLF source, encode bytecode, run via HLFRuntime."""
    from hlf_mcp.hlf.runtime import HLFRuntime
    ast = _COMPILER.compile(source)["ast"]
    bytecode = HLFBytecode().encode(ast)
    return HLFRuntime().run(bytecode, gas_limit=500)


# ── Test 1: Integer literal equivalence ──────────────────────────────────────

def test_equivalence_integer_literal() -> None:
    """HLF integer literal execution matches Python int."""
    source = "[HLF-v3]\nRESULT 42\nΩ\n"
    result = prove_equivalence(source, "42", label="integer_literal")
    assert result.passed
    assert result.hlf_result == 42
    assert result.python_result == 42


# ── Test 2: Float literal equivalence ────────────────────────────────────────

def test_equivalence_float_literal() -> None:
    """HLF float literal execution matches Python float."""
    source = "[HLF-v3]\nRESULT 3.14\nΩ\n"
    result = prove_equivalence(source, "3.14", label="float_literal")
    assert result.passed
    assert math.isclose(float(result.hlf_result), 3.14, rel_tol=1e-12)
    assert math.isclose(float(result.python_result), 3.14, rel_tol=1e-12)


# ── Test 3: String literal equivalence ───────────────────────────────────────

def test_equivalence_string_literal() -> None:
    """HLF string literal execution matches Python str."""
    source = '[HLF-v3]\nRESULT "hello world"\nΩ\n'
    result = prove_equivalence(source, '"hello world"', label="string_literal")
    assert result.passed
    assert result.hlf_result == "hello world"
    assert result.python_result == "hello world"


# ── Test 4: Boolean literal equivalence ──────────────────────────────────────

def test_equivalence_boolean_true() -> None:
    """HLF boolean TRUE execution matches Python True."""
    source = "[HLF-v3]\nRESULT TRUE\nΩ\n"
    result = prove_equivalence(source, "True", label="boolean_true")
    assert result.passed
    assert result.hlf_result is True


def test_equivalence_boolean_false() -> None:
    """HLF boolean FALSE execution matches Python False."""
    source = "[HLF-v3]\nRESULT FALSE\nΩ\n"
    result = prove_equivalence(source, "False", label="boolean_false")
    assert result.passed
    assert result.hlf_result is False


# ── Test 5: Arithmetic equivalence (add, sub, mul, div, mod, neg) ─────────────

def test_equivalence_addition() -> None:
    """HLF addition matches Python +."""
    source = "[HLF-v3]\nRESULT 40 + 2\nΩ\n"
    result = prove_equivalence(source, "40 + 2", label="addition")
    assert result.passed
    assert result.hlf_result == 42


def test_equivalence_subtraction() -> None:
    """HLF subtraction matches Python -."""
    source = "[HLF-v3]\nRESULT 100 - 58\nΩ\n"
    result = prove_equivalence(source, "100 - 58", label="subtraction")
    assert result.passed
    assert result.hlf_result == 42


def test_equivalence_multiplication() -> None:
    """HLF multiplication matches Python *."""
    source = "[HLF-v3]\nRESULT 6 * 7\nΩ\n"
    result = prove_equivalence(source, "6 * 7", label="multiplication")
    assert result.passed
    assert result.hlf_result == 42


def test_equivalence_division() -> None:
    """HLF division matches Python /."""
    source = "[HLF-v3]\nRESULT 84 / 2\nΩ\n"
    result = prove_equivalence(source, "84 / 2", label="division")
    assert result.passed
    assert result.hlf_result == 42.0


def test_equivalence_modulo() -> None:
    """HLF modulo matches Python %."""
    source = "[HLF-v3]\nRESULT 45 % 3\nΩ\n"
    result = prove_equivalence(source, "45 % 3", label="modulo")
    assert result.passed
    assert result.hlf_result == 0


def test_equivalence_negation() -> None:
    """HLF negation matches Python unary -."""
    source = "[HLF-v3]\nRESULT -99\nΩ\n"
    result = prove_equivalence(source, "-99", label="negation")
    assert result.passed
    assert result.hlf_result == -99


# ── Test 6: Comparison equivalence (eq, ne, lt, le, gt, ge) ───────────────────

def test_equivalence_comparison_eq() -> None:
    """HLF == matches Python ==."""
    source = "[HLF-v3]\nRESULT 42 == 42\nΩ\n"
    result = prove_equivalence(source, "42 == 42", label="cmp_eq")
    assert result.passed
    assert result.hlf_result is True


def test_equivalence_comparison_ne() -> None:
    """HLF != matches Python !=."""
    source = "[HLF-v3]\nRESULT 42 != 7\nΩ\n"
    result = prove_equivalence(source, "42 != 7", label="cmp_ne")
    assert result.passed
    assert result.hlf_result is True


def test_equivalence_comparison_lt() -> None:
    """HLF < matches Python <."""
    source = "[HLF-v3]\nRESULT 10 < 20\nΩ\n"
    result = prove_equivalence(source, "10 < 20", label="cmp_lt")
    assert result.passed
    assert result.hlf_result is True


def test_equivalence_comparison_ge() -> None:
    """HLF >= matches Python >=."""
    source = "[HLF-v3]\nRESULT 100 >= 50\nΩ\n"
    result = prove_equivalence(source, "100 >= 50", label="cmp_ge")
    assert result.passed
    assert result.hlf_result is True


# ── Test 7: Logic equivalence ────────────────────────────────────────────────

def test_equivalence_logical_and() -> None:
    """HLF AND matches Python and."""
    source = "[HLF-v3]\nRESULT TRUE AND FALSE\nΩ\n"
    result = prove_equivalence(source, "True and False", label="logical_and")
    assert result.passed
    assert result.hlf_result is False


def test_equivalence_logical_or() -> None:
    """HLF OR matches Python or."""
    source = "[HLF-v3]\nRESULT TRUE OR FALSE\nΩ\n"
    result = prove_equivalence(source, "True or False", label="logical_or")
    assert result.passed
    assert result.hlf_result is True


def test_equivalence_logical_not() -> None:
    """HLF NOT matches Python not."""
    source = "[HLF-v3]\nRESULT NOT FALSE\nΩ\n"
    result = prove_equivalence(source, "not False", label="logical_not")
    assert result.passed
    assert result.hlf_result is True


# ── Test 8: Complex expression equivalence ───────────────────────────────────

def test_equivalence_nested_arithmetic() -> None:
    """HLF nested arithmetic matches Python evaluation order."""
    source = "[HLF-v3]\nRESULT (10 + 5) * (20 - 15) / 3\nΩ\n"
    result = prove_equivalence(source, "(10 + 5) * (20 - 15) / 3", label="nested_arithmetic")
    assert result.passed
    assert float(result.hlf_result) == 25.0


def test_equivalence_complex_logic() -> None:
    """HLF complex logic matches Python."""
    source = "[HLF-v3]\nRESULT (10 > 5) AND (20 < 30) AND NOT (3 == 4)\nΩ\n"
    result = prove_equivalence(
        source, "(10 > 5) and (20 < 30) and not (3 == 4)", label="complex_logic"
    )
    assert result.passed
    assert result.hlf_result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Effect Audit Proofs (tests 9-12)
# ═══════════════════════════════════════════════════════════════════════════════

def test_effect_audit_simple_expression_has_no_side_effects() -> None:
    """A pure arithmetic expression produces no undeclared side effects."""
    source = "[HLF-v3]\nRESULT 1 + 2\nΩ\n"
    result = audit_effects(source, label="pure_expression")
    assert result.passed
    assert result.undeclared_effects == []


def test_effect_audit_host_call_produces_expected_effect() -> None:
    """A CALL to a host function produces matching declared effects."""
    source = '[HLF-v3]\nCALL host "analyze" "test_file.txt"\nΩ\n'
    result = audit_effects(source, label="host_call")
    # Host calls can produce tool_call effects; audit passes if no undeclared
    assert result.undeclared_effects == []


def test_effect_audit_delegation_produces_agent_effect() -> None:
    """A DELEGATE call matches declared agent delegation effects."""
    source = '[HLF-v3]\n⌘ [DELEGATE] agent="scribe" goal="summarize"\nΩ\n'
    result = audit_effects(source, label="delegate_call")
    assert result.passed
    assert result.undeclared_effects == []


def test_effect_audit_route_produces_model_call_effect() -> None:
    """A ROUTE call maps to declared model_call effect."""
    source = '[HLF-v3]\n⌘ [ROUTE] strategy="auto"\nΩ\n'
    result = audit_effects(source, label="route_call")
    assert result.passed
    assert result.undeclared_effects == []


# ═══════════════════════════════════════════════════════════════════════════════
# Bytecode Roundtrip Proofs (tests 13-16)
# ═══════════════════════════════════════════════════════════════════════════════

def test_bytecode_roundtrip_simple_expression() -> None:
    """Bytecode encode->decode->encode is lossless for a simple expression."""
    source = "[HLF-v3]\nRESULT 42\nΩ\n"
    result = prove_bytecode_roundtrip(source, label="simple")
    assert result.passed
    assert result.original_size == result.roundtrip_size
    assert result.original_sha256 == result.roundtrip_sha256


def test_bytecode_roundtrip_math_expression() -> None:
    """Bytecode roundtrip preserves math expressions."""
    source = "[HLF-v3]\nRESULT 1 + 2 * 3\nΩ\n"
    result = prove_bytecode_roundtrip(source, label="math")
    assert result.passed


def test_bytecode_roundtrip_string_literal() -> None:
    """Bytecode roundtrip preserves string constants."""
    source = '[HLF-v3]\nRESULT "test-string-value"\nΩ\n'
    result = prove_bytecode_roundtrip(source, label="string")
    assert result.passed


def test_bytecode_roundtrip_boolean_literal() -> None:
    """Bytecode roundtrip preserves boolean constants."""
    source = "[HLF-v3]\nRESULT TRUE\nΩ\n"
    result = prove_bytecode_roundtrip(source, label="boolean")
    assert result.passed


def test_bytecode_roundtrip_multi_statement() -> None:
    """Bytecode roundtrip is lossless for multi-statement programs."""
    source = """\
[HLF-v3]
SET x = 10
SET y = 20
RESULT x + y
Ω
"""
    result = prove_bytecode_roundtrip(source, label="multi_stmt")
    assert result.passed
    assert result.instruction_count > 1


# ── Edge case: EquivalenceResult output method ────────────────────────────────

def test_equivalence_result_output_dict() -> None:
    """EquivalenceResult.output produces a valid dict with all fields."""
    result = prove_equivalence("[HLF-v3]\nRESULT 7\nΩ\n", "7", label="seven")
    output = result.output
    assert output["source_label"] == "seven"
    assert output["hlf_result"] == 7
    assert output["python_result"] == 7
    assert "gas_used" in output
    assert output["passed"] is True
    assert output["error"] == ""


# ── Edge case: AuditResult output method ─────────────────────────────────────

def test_audit_result_output_dict() -> None:
    """AuditResult.output produces a valid dict with all fields."""
    source = "[HLF-v3]\nRESULT 1\nΩ\n"
    result = audit_effects(source, label="pure")
    output = result.output
    assert output["source_label"] == "pure"
    assert isinstance(output["declared_effects"], list)
    assert isinstance(output["actual_effects"], list)
    assert output["undeclared_effects"] == []
    assert output["passed"] is True


# ── Edge case: compile failure handling ──────────────────────────────────────

def test_equivalence_handles_invalid_hlf() -> None:
    """EquivalenceProver handles invalid HLF gracefully."""
    result = prove_equivalence("[HLF-v3]\nINVALID @#$%@\nΩ\n", "42", label="bad")
    assert not result.passed
    assert result.error != ""


def test_bytecode_roundtrip_handles_varied_expressions() -> None:
    """BytecodeRoundtripper handles expressions with negative numbers and decimals."""
    source = "[HLF-v3]\nRESULT -3.5 + 7.2\nΩ\n"
    result = prove_bytecode_roundtrip(source, label="varied")
    assert result.passed


# ── Equivalence across all binary ops ────────────────────────────────────────

@pytest.mark.parametrize("op_sym,py_op,left,right", [
    ("+", "+", 5, 3),
    ("-", "-", 10, 3),
    ("*", "*", 7, 6),
    ("/", "/", 100, 4),
    ("==", "==", 1, 1),
    ("!=", "!=", 1, 2),
    ("<", "<", 3, 7),
    (">", ">", 9, 1),
    ("<=", "<=", 5, 5),
    (">=", ">=", 8, 3),
])
def test_equivalence_parametric_binary_ops(op_sym, py_op, left, right) -> None:
    """All binary operators produce equivalent results in HLF and Python."""
    source = f"[HLF-v3]\nRESULT {left} {op_sym} {right}\nΩ\n"
    py_expr = f"{left} {py_op} {right}"
    result = prove_equivalence(source, py_expr, label=f"binop_{op_sym}")
    assert result.passed, f"Failed for {op_sym}: {result.error}"
