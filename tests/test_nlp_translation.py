"""Tests for HLF NLP translation layer covering all statement patterns.

Each test:
1. Calls english_to_hlf() with an English intent string
2. Verifies the generated HLF contains the expected keyword/pattern
3. Verifies the HLF compiles successfully using the compiler
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.translator import english_to_hlf
from hlf_mcp.hlf.compiler import CompileError, HLFCompiler

compiler = HLFCompiler()


def _compile(hlf_source: str):
    """Helper: compile HLF and return result dict. Raises AssertionError on error."""
    try:
        result = compiler.compile(hlf_source)
    except CompileError as exc:
        raise AssertionError(f"Compilation failed: {exc}") from exc
    if result.get("status") == "error":
        errors = result.get("errors", [])
        raise AssertionError(f"Compilation failed: {errors}")
    return result


class TestNLPTranslation:
    """Grouped tests for all NLP-to-HLF translation statement patterns."""

    # ── FUNCTION patterns ──────────────────────────────────────────────────

    def test_function_with_params(self) -> None:
        hlf = english_to_hlf("Define function greet(name) that returns greeting")
        assert "FUNCTION greet(name)" in hlf, hlf
        assert "RETURN greeting" in hlf, hlf
        _compile(hlf)

    def test_function_simple_name(self) -> None:
        """Simple function definition using placeholder param for grammar compatibility."""
        hlf = english_to_hlf("Define function check")
        assert "FUNCTION check" in hlf, hlf
        assert "(_void)" in hlf, "Expected placeholder param for grammar compatibility"
        _compile(hlf)

    # ── CONTROL-FLOW patterns ──────────────────────────────────────────────

    def test_if_else(self) -> None:
        hlf = english_to_hlf("If active then show warning else show normal")
        assert "IF active" in hlf, hlf
        assert "ELSE" in hlf, hlf
        _compile(hlf)

    def test_if_only(self) -> None:
        hlf = english_to_hlf("When ready then start process")
        assert "IF ready" in hlf, hlf
        _compile(hlf)

    def test_for_loop(self) -> None:
        hlf = english_to_hlf("For each item in collection")
        assert "FOR item IN collection" in hlf, hlf
        _compile(hlf)

    def test_parallel(self) -> None:
        hlf = english_to_hlf("Do tasks in parallel")
        assert "PARALLEL" in hlf, hlf
        _compile(hlf)

    # ── VARIABLE patterns ──────────────────────────────────────────────────

    def test_set_variable(self) -> None:
        hlf = english_to_hlf("Set session_id = active")
        assert "SET session_id" in hlf, hlf
        assert "active" in hlf, hlf
        _compile(hlf)

    def test_assign_variable(self) -> None:
        hlf = english_to_hlf("Let count = 42")
        assert "SET count" in hlf, hlf
        assert "42" in hlf, hlf
        _compile(hlf)

    # ── I/O patterns ───────────────────────────────────────────────────────

    def test_log(self) -> None:
        hlf = english_to_hlf("Log system startup complete")
        assert "LOG " in hlf, hlf
        assert "system startup complete" in hlf, hlf
        _compile(hlf)

    def test_return(self) -> None:
        hlf = english_to_hlf("Return success")
        assert "RETURN success" in hlf, hlf
        _compile(hlf)

    # ── DATA-FLOW patterns ─────────────────────────────────────────────────

    def test_summarize(self) -> None:
        hlf = english_to_hlf("Summarize the build health")
        assert "SUMMARY" in hlf, hlf
        _compile(hlf)

    def test_source_flow(self) -> None:
        hlf = english_to_hlf("Source data from /data/input.csv")
        assert "SOURCE" in hlf, hlf
        _compile(hlf)

    def test_branch(self) -> None:
        hlf = english_to_hlf("Branch the pipeline into two paths")
        assert "BRANCH" in hlf, hlf
        _compile(hlf)

    # ── SPEC / LIFECYCLE patterns ──────────────────────────────────────────

    def test_spec_lifecycle(self) -> None:
        hlf = english_to_hlf("Instinct lifecycle gate spec")
        assert "SPEC_DEFINE" in hlf, hlf
        _compile(hlf)

    # ── MEMORY patterns ────────────────────────────────────────────────────

    def test_memory_store(self) -> None:
        hlf = english_to_hlf(
            "Store a memory record: key=fluency, value=verified"
        )
        assert "MEMORY [fluency]" in hlf, hlf
        assert "verified" in hlf, hlf
        _compile(hlf)

    def test_memory_recall(self) -> None:
        hlf = english_to_hlf("Recall the memory record with key fluency")
        assert "RECALL [fluency]" in hlf, hlf
        _compile(hlf)

    # ── FALLBACK / HEADER patterns ─────────────────────────────────────────

    def test_fallback_compiles(self) -> None:
        """Even fallback translations should produce valid, compilable HLF."""
        hlf = english_to_hlf(
            "Some random unstructured text without matched words"
        )
        assert "[HLF-v3]" in hlf
        _compile(hlf)

    def test_all_patterns_use_correct_header(self) -> None:
        """Every translation must start with the HLF version header."""
        intents = [
            "Define function foo(name)",
            "If active then show ok",
            "Set a = 1",
            "Log test",
        ]
        for intent in intents:
            hlf = english_to_hlf(intent)
            assert hlf.startswith("[HLF-v3]"), f"Missing header for: {intent}"
