"""Tests for HLF ASCII surface — bidirectional ASCII ↔ Glyph conversion."""

import pytest

from hlf_mcp.hlf.ascii_surface import (
    ASCIIToHLF,
    HLFToASCII,
    ascii_roundtrip,
    is_ascii_hlf,
)
from hlf_mcp.hlf.compiler import CompileError, HLFCompiler

# ── Fixtures ──────────────────────────────────────────────────────────────────

COMPILER = HLFCompiler()
TO_GLYPH = ASCIIToHLF()
TO_ASCII = HLFToASCII()


# ── is_ascii_hlf detection tests ──────────────────────────────────────────────


def test_is_ascii_hlf_detects_ascii_source():
    source = "[HLF-v3]\nANALYZE test_goal\nEND\n"
    assert is_ascii_hlf(source) is True


def test_is_ascii_hlf_detects_glyph_source():
    source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
    assert is_ascii_hlf(source) is False


def test_is_ascii_hlf_empty_returns_false():
    assert is_ascii_hlf("") is False


def test_is_ascii_hlf_only_header_returns_true():
    assert is_ascii_hlf("[HLF-v3]") is True


def test_is_ascii_hlf_if_condition():
    source = "[HLF-v3]\nIF risk > 0 THEN [RESULT]\nEND\n"
    assert is_ascii_hlf(source) is True


# ── ASCIIToHLF: ANALYZE ───────────────────────────────────────────────────────


def test_analyze_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nANALYZE security_audit\nEND\n")
    assert "Δ" in result
    assert "[INTENT]" in result
    assert 'goal="security_audit"' in result
    assert "Ω" in result


def test_analyze_to_glyph_roundtrip():
    source = "[HLF-v3]\nANALYZE test_hello_world\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "ANALYZE" in recovered
    assert "test_hello_world" in recovered
    assert "END" in recovered


# ── ASCIIToHLF: EXECUTE ───────────────────────────────────────────────────────


def test_execute_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nEXECUTE run_pipeline\nEND\n")
    assert "⌘" in result
    assert "[EXEC]" in result
    assert 'goal="run_pipeline"' in result


def test_execute_to_glyph_roundtrip():
    source = "[HLF-v3]\nEXECUTE deploy_service\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "EXECUTE" in recovered
    assert "deploy_service" in recovered


# ── ASCIIToHLF: IF / THEN ─────────────────────────────────────────────────────


def test_if_then_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nIF risk > 0 THEN [RESULT]\nEND\n")
    assert "⊎" in result
    assert "[RESULT]" in result
    assert 'condition="risk > 0"' in result


def test_if_then_roundtrip():
    source = "[HLF-v3]\nIF risk > 0 THEN [RESULT]\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "IF" in recovered
    assert "RESULT" in recovered


def test_if_else_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nIF x > 0 THEN [POSITIVE]\nELSE\nEND\n")
    assert "[ELSE]" in result


def test_if_elif_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nIF x > 0 THEN [POSITIVE]\nELIF x < 0\nEND\n")
    assert "[ELIF]" in result


def test_if_endif_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nIF x > 0 THEN [POSITIVE]\nENDIF\nEND\n")
    assert "[ENDIF]" in result


# ── ASCIIToHLF: SET / LET ─────────────────────────────────────────────────────


def test_set_to_glyph():
    result = TO_GLYPH.convert('[HLF-v3]\nSET threshold = 0.8\nEND\n')
    assert "⩕" in result
    assert "[SET]" in result
    assert 'name="threshold"' in result
    assert 'value="0.8"' in result


def test_let_to_glyph():
    result = TO_GLYPH.convert('[HLF-v3]\nLET limit = 100\nEND\n')
    assert "⩕" in result
    assert "[SET]" in result
    assert 'name="limit"' in result


def test_set_roundtrip():
    source = '[HLF-v3]\nSET mode = "strict"\nEND\n'
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "SET" in recovered
    assert "mode" in recovered


# ── ASCIIToHLF: DEFINE ────────────────────────────────────────────────────────


def test_define_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nDEFINE compute(a, b, c): add all\nEND\n")
    assert "⌂" in result
    assert "[FUNC]" in result
    assert 'name="compute"' in result
    assert 'params="a, b, c"' in result


def test_define_roundtrip():
    source = "[HLF-v3]\nDEFINE add(x, y): x + y\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "DEFINE" in recovered
    assert "add" in recovered
    assert "x, y" in recovered


# ── ASCIIToHLF: RETURN ────────────────────────────────────────────────────────


def test_return_to_glyph():
    result = TO_GLYPH.convert('[HLF-v3]\nRETURN result_data\nEND\n')
    assert "Ж" in result
    assert "[RETURN]" in result
    assert 'value="result_data"' in result


def test_return_roundtrip():
    source = '[HLF-v3]\nRETURN "success"\nEND\n'
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "RETURN" in recovered


# ── ASCIIToHLF: LOG ───────────────────────────────────────────────────────────


def test_log_to_glyph():
    result = TO_GLYPH.convert('[HLF-v3]\nLOG "processing started"\nEND\n')
    assert "Ж" in result
    assert "[LOG]" in result
    assert 'value="\\"processing started\\""' in result


def test_log_roundtrip():
    source = '[HLF-v3]\nLOG error_count\nEND\n'
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "LOG" in recovered
    assert "error_count" in recovered


# ── ASCIIToHLF: PARALLEL ──────────────────────────────────────────────────────


def test_parallel_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nPARALLEL:\n  ANALYZE task_a\n  ANALYZE task_b\nEND\n")
    assert "PARALLEL" in result
    assert "{" in result
    assert "}" in result
    assert "Δ" in result  # Nested ANALYZE converted to glyph
    assert "Ω" in result


def test_parallel_roundtrip():
    source = "[HLF-v3]\nPARALLEL:\n  ANALYZE task_1\n  ANALYZE task_2\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "PARALLEL" in recovered


# ── ASCIIToHLF: CONSTRAINT ────────────────────────────────────────────────────


def test_constraint_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nCONSTRAINT max_retries 1..5\nEND\n")
    assert "⨝" in result
    assert "[CONSTRAINT]" in result
    assert 'name="max_retries"' in result
    assert "min=1" in result
    assert "max=5" in result


def test_constraint_roundtrip():
    source = "[HLF-v3]\nCONSTRAINT timeout 10..60\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "CONSTRAINT" in recovered
    assert "timeout" in recovered


# ── ASCIIToHLF: ASSERT ────────────────────────────────────────────────────────


def test_assert_to_glyph():
    result = TO_GLYPH.convert('[HLF-v3]\nASSERT status == "ok"\nEND\n')
    assert "∇" in result
    assert "[ASSERT]" in result
    assert 'condition="status == \\"ok\\""' in result


def test_assert_roundtrip():
    source = "[HLF-v3]\nASSERT x > 0\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "ASSERT" in recovered
    assert "x > 0" in recovered


# ── ASCIIToHLF: FOR EACH ──────────────────────────────────────────────────────


def test_for_each_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nFOR EACH item IN items:\n  ANALYZE item\nEND\n")
    assert "FOR" in result
    assert "IN" in result
    assert "{" in result
    assert "}" in result
    assert "Δ" in result  # Nested ANALYZE converted to glyph


def test_for_each_roundtrip():
    source = "[HLF-v3]\nFOR EACH elem IN elements:\n  ANALYZE elem\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "FOR EACH" in recovered
    assert "elements" in recovered


# ── ASCIIToHLF: SPEC_GATE ─────────────────────────────────────────────────────


def test_spec_gate_to_glyph():
    result = TO_GLYPH.convert("[HLF-v3]\nSPEC_GATE auth_required\nEND\n")
    assert "[SPEC_GATE]" in result
    assert 'name="auth_required"' in result


def test_spec_gate_roundtrip():
    source = "[HLF-v3]\nSPEC_GATE policy_check\nEND\n"
    glyph = TO_GLYPH.convert(source)
    recovered = TO_ASCII.convert(glyph)
    assert "SPEC_GATE" in recovered


# ── Full ascii_roundtrip validation ────────────────────────────────────────────


def test_ascii_roundtrip_simple():
    source = "[HLF-v3]\nANALYZE test_goal\nEND\n"
    result = ascii_roundtrip(source)
    assert result["roundtrip_success"] is True
    assert result["fidelity"] >= 0.9
    assert "Δ" in result["generated_glyph"]
    assert "ANALYZE" in result["recovered_ascii"]


def test_ascii_roundtrip_multi_line():
    source = "[HLF-v3]\nANALYZE security_audit\nSET threshold = 0.8\nLOG audit_complete\nEND\n"
    result = ascii_roundtrip(source)
    assert result["roundtrip_success"] is True
    assert result["fidelity"] >= 0.9


def test_ascii_roundtrip_if_condition():
    source = "[HLF-v3]\nIF risk > 0 THEN [RESULT]\nEND\n"
    result = ascii_roundtrip(source)
    assert result["roundtrip_success"] is True
    assert result["fidelity"] >= 0.9


# ── Compiler integration tests ────────────────────────────────────────────────


def test_ascii_compiles_through_glyph_compiler():
    """Verify ASCII source compiles successfully after glyph conversion."""
    source = "[HLF-v3]\nANALYZE test_goal\nEND\n"
    glyph = TO_GLYPH.convert(source)
    result = COMPILER.compile(glyph)
    assert result is not None
    assert "ast" in result
    ast = result["ast"]
    assert ast["kind"] == "program"
    assert ast["node_count"] >= 1


def test_ascii_if_compiles_through_glyph_compiler():
    source = "[HLF-v3]\nIF risk > 0 THEN [RESULT]\nEND\n"
    glyph = TO_GLYPH.convert(source)
    result = COMPILER.compile(glyph)
    assert result is not None
    assert "ast" in result


def test_ascii_set_compiles_through_glyph_compiler():
    source = '[HLF-v3]\nSET threshold = 0.8\nEND\n'
    glyph = TO_GLYPH.convert(source)
    result = COMPILER.compile(glyph)
    assert result is not None
    assert "ast" in result


def test_ascii_parallel_compiles_through_glyph_compiler():
    source = "[HLF-v3]\nPARALLEL:\n  ANALYZE task_a\n  ANALYZE task_b\nEND\n"
    glyph = TO_GLYPH.convert(source)
    result = COMPILER.compile(glyph)
    assert result is not None
    assert "ast" in result


def test_ascii_define_compiles_through_glyph_compiler():
    source = "[HLF-v3]\nDEFINE add(x, y): x + y\nEND\n"
    glyph = TO_GLYPH.convert(source)
    result = COMPILER.compile(glyph)
    assert result is not None
    assert "ast" in result


# ── HLFToASCII round-trip tests ───────────────────────────────────────────────


def test_glyph_to_ascii_analyze():
    source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "ANALYZE" in result
    assert "test" in result
    assert "END" in result


def test_glyph_to_ascii_enforce():
    source = '[HLF-v3]\nЖ [ENFORCE] value="strict_mode"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "ENFORCE" in result


def test_glyph_to_ascii_constraint():
    source = '[HLF-v3]\n⨝ [CONSTRAINT] name="limit" min=1 max=10\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "CONSTRAINT" in result
    assert "limit" in result


def test_glyph_to_ascii_set():
    source = '[HLF-v3]\n⩕ [SET] name="timeout" value="30"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "SET" in result
    assert "timeout" in result


def test_glyph_to_ascii_return():
    source = '[HLF-v3]\nЖ [RETURN] value="ok"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "RETURN" in result


def test_glyph_to_ascii_log():
    source = '[HLF-v3]\nЖ [LOG] value="processing"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "LOG" in result


def test_glyph_to_ascii_define():
    source = '[HLF-v3]\n⌂ [FUNC] name="compute" params="a, b"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "DEFINE" in result
    assert "compute" in result


def test_glyph_to_ascii_parallel():
    source = "[HLF-v3]\n∇ [PARALLEL]\nΩ\n"
    result = TO_ASCII.convert(source)
    assert "PARALLEL" in result


def test_glyph_to_ascii_assert():
    source = '[HLF-v3]\n∇ [ASSERT] condition="x > 0"\nΩ\n'
    result = TO_ASCII.convert(source)
    assert "ASSERT" in result


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_ascii_with_comments():
    source = "[HLF-v3]\n# This is a comment\nANALYZE test\n# Another comment\nEND\n"
    glyph = TO_GLYPH.convert(source)
    assert "Ω" in glyph
    recovered = TO_ASCII.convert(glyph)
    assert "ANALYZE" in recovered


def test_ascii_preserves_header():
    source = "[HLF-v3]\nANALYZE test\nEND\n"
    glyph = TO_GLYPH.convert(source)
    assert "[HLF-v3]" in glyph
    recovered = TO_ASCII.convert(glyph)
    assert "[HLF-v3]" in recovered


def test_ascii_empty_is_handled():
    source = "[HLF-v3]\nEND\n"
    glyph = TO_GLYPH.convert(source)
    assert "Ω" in glyph


def test_already_glyph_passes_through():
    source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
    # Passing glyph to ASCIIToHLF should not corrupt it
    result = TO_GLYPH.convert(source)
    assert "Δ" in result
    assert "[INTENT]" in result
    assert "Ω" in result
