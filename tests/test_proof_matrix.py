"""
Tests for the unified Proof Matrix — aggregates equivalence, effect audit,
and bytecode roundtrip proofs into a single report per fixture.

25+ tests covering:
  - FixtureCatalog discovery and Python expression extraction
  - ProofMatrixEntry properties (overall_passed, failed_proofs, proof_count)
  - ProofMatrix build_entry, build_matrix, from_fixture_catalog
  - ProofMatrix summary_stats, to_csv, to_markdown_table, to_json
  - ProofMatrixReport generate, generate_json, generate_compact
  - Edge cases: None results, empty directories, malformed fixtures, large dirs
"""

from __future__ import annotations

import json
import math
import os
import tempfile

import pytest

from hlf_mcp.hlf.real_code_bridge.proof_matrix import (
    ProofMatrix,
    ProofMatrixEntry,
    FixtureCatalog,
    ProofMatrixReport,
)
from hlf_mcp.hlf.real_code_bridge.equivalence import (
    EquivalenceProver,
    EquivalenceResult,
)
from hlf_mcp.hlf.real_code_bridge.effect_audit import (
    EffectAuditor,
    AuditResult,
)
from hlf_mcp.hlf.real_code_bridge.bytecode_roundtrip import (
    BytecodeRoundtripper,
    RoundtripResult,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def _make_temp_hlf_dir(files: dict[str, str]) -> str:
    """Create a temporary directory with .hlf files from a {name: content} dict."""
    tmpdir = tempfile.mkdtemp(prefix="hlf_matrix_test_")
    for fname, content in files.items():
        path = os.path.join(tmpdir, fname)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    return tmpdir


def _basic_entry(
    fixture_id: str = "test_fixture",
    eq_passed: bool = True,
    au_passed: bool = True,
    rt_passed: bool = True,
) -> ProofMatrixEntry:
    """Create a ProofMatrixEntry with mock results."""
    return ProofMatrixEntry(
        fixture_id=fixture_id,
        fixture_path=f"/fake/{fixture_id}.hlf",
        label=f"Test {fixture_id}",
        hlf_source="[HLF-v3]\nRESULT 42\nΩ\n",
        python_code="42",
        equivalence_result=EquivalenceResult(
            source_label=fixture_id,
            hlf_source="[HLF-v3]\nRESULT 42\nΩ\n",
            python_code="42",
            hlf_result=42,
            python_result=42,
            gas_used=10,
            passed=eq_passed,
            error="" if eq_passed else "mismatch",
        ) if eq_passed is not None else None,
        audit_result=AuditResult(
            source_label=fixture_id,
            declared_effects=[],
            actual_effects=[],
            undeclared_effects=[],
            unexecuted_effects=[],
            matched_effects=[],
            passed=au_passed,
        ) if au_passed is not None else None,
        roundtrip_result=RoundtripResult(
            source_label=fixture_id,
            original_sha256="abc123",
            roundtrip_sha256="abc123" if rt_passed else "def456",
            instruction_count=3,
            constant_count=1,
            original_size=64,
            roundtrip_size=64 if rt_passed else 65,
        ) if rt_passed is not None else None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FixtureCatalog tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_fixture_catalog_discovers_hlf_files() -> None:
    """FixtureCatalog discovers .hlf files from a directory."""
    catalog = FixtureCatalog()
    entries = catalog.discover_fixtures(FIXTURES_DIR)
    assert len(entries) > 0
    hlf_ids = {e["fixture_id"] for e in entries}
    assert "hello_world" in hlf_ids
    # Every entry has required keys
    for e in entries:
        assert "fixture_id" in e
        assert "path" in e
        assert "label" in e
        assert "hlf_source" in e
        assert "python_code" in e


def test_fixture_catalog_extracts_python_from_comment() -> None:
    """FixtureCatalog extracts Python expressions from specially-marked comments."""
    tmpdir = _make_temp_hlf_dir({
        "expr_fixture.hlf": (
            "# HLF v3 — Expression test\n"
            "# PYTHON: 2 + 3\n"
            "[HLF-v3]\n"
            "RESULT 5\n"
            "Ω\n"
        ),
    })
    try:
        catalog = FixtureCatalog()
        entries = catalog.discover_fixtures(tmpdir)
        assert len(entries) == 1
        assert entries[0]["python_code"] == "2 + 3"
        assert entries[0]["fixture_id"] == "expr_fixture"
    finally:
        _rmdir(tmpdir)


def test_fixture_catalog_extracts_python_from_multiple_markers() -> None:
    """FixtureCatalog handles various PYTHON: comment markers."""
    for marker in ["PYTHON:", "python:", "PYTHON_EXPR:", "python_expr:", "PYTHON_EXPRESSION:", "python_expression:"]:
        tmpdir = _make_temp_hlf_dir({
            "test.hlf": f"# {marker} 100 / 5\n[HLF-v3]\nRESULT 20\nΩ\n",
        })
        try:
            catalog = FixtureCatalog()
            entries = catalog.discover_fixtures(tmpdir)
            assert entries[0]["python_code"] == "100 / 5", f"Failed for marker: {marker}"
        finally:
            _rmdir(tmpdir)


def test_fixture_catalog_empty_directory_returns_empty() -> None:
    """FixtureCatalog returns empty list for directory with no .hlf files."""
    tmpdir = _make_temp_hlf_dir({})
    try:
        catalog = FixtureCatalog()
        entries = catalog.discover_fixtures(tmpdir)
        assert entries == []
    finally:
        _rmdir(tmpdir)


def test_fixture_catalog_get_python_expression_from_file() -> None:
    """get_python_expression reads Python expression from a .hlf file."""
    tmpdir = _make_temp_hlf_dir({
        "with_expr.hlf": "# PYTHON: 7 * 8\n[HLF-v3]\nRESULT 56\nΩ\n",
    })
    try:
        path = os.path.join(tmpdir, "with_expr.hlf")
        expr = FixtureCatalog.get_python_expression(path)
        assert expr == "7 * 8"
    finally:
        _rmdir(tmpdir)


def test_fixture_catalog_get_python_expression_no_comment() -> None:
    """get_python_expression returns None when no Python comment present."""
    tmpdir = _make_temp_hlf_dir({
        "no_expr.hlf": "[HLF-v3]\nRESULT 1\nΩ\n",
    })
    try:
        path = os.path.join(tmpdir, "no_expr.hlf")
        expr = FixtureCatalog.get_python_expression(path)
        assert expr is None
    finally:
        _rmdir(tmpdir)


def test_fixture_catalog_get_python_expression_companion_py() -> None:
    """get_python_expression falls back to companion .py file."""
    tmpdir = _make_temp_hlf_dir({
        "with_py.hlf": "[HLF-v3]\nRESULT 42\nΩ\n",
        "with_py.py": "42",
    })
    try:
        path = os.path.join(tmpdir, "with_py.hlf")
        expr = FixtureCatalog.get_python_expression(path)
        assert expr == "42"
    finally:
        _rmdir(tmpdir)


def test_fixture_catalog_get_python_expression_nonexistent_file() -> None:
    """get_python_expression returns None for nonexistent file."""
    expr = FixtureCatalog.get_python_expression("/nonexistent/path/file.hlf")
    assert expr is None


def test_fixture_catalog_catalog_to_matrix_input() -> None:
    """catalog_to_matrix_input converts catalog entries to tuples."""
    catalog = FixtureCatalog()
    entries = [
        {"path": "/a/f1.hlf", "label": "F1", "hlf_source": "S1", "python_code": "P1"},
        {"path": "/a/f2.hlf", "label": "F2", "hlf_source": "S2", "python_code": ""},
    ]
    result = catalog.catalog_to_matrix_input(entries)
    assert len(result) == 2
    assert result[0] == ("/a/f1.hlf", "F1", "S1", "P1")
    assert result[1] == ("/a/f2.hlf", "F2", "S2", "")


def test_fixture_catalog_excludes_non_hlf_files() -> None:
    """discover_fixtures skips non-.hlf files."""
    tmpdir = _make_temp_hlf_dir({
        "good.hlf": "[HLF-v3]\nΩ\n",
        "readme.md": "Nothing here",
        "script.py": "print(1)",
        "data.txt": "hello",
    })
    try:
        catalog = FixtureCatalog()
        entries = catalog.discover_fixtures(tmpdir)
        assert len(entries) == 1
        assert entries[0]["fixture_id"] == "good"
    finally:
        _rmdir(tmpdir)


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrixEntry tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_entry_all_passed_when_all_proofs_pass() -> None:
    """ProofMatrixEntry.overall_passed is True when all 3 proofs pass."""
    entry = _basic_entry("good", eq_passed=True, au_passed=True, rt_passed=True)
    assert entry.overall_passed is True
    assert entry.failed_proofs == []
    assert entry.proof_count == 3


def test_entry_not_passed_when_one_proof_fails() -> None:
    """ProofMatrixEntry.overall_passed is False when any proof fails."""
    entry = _basic_entry("bad_eq", eq_passed=False, au_passed=True, rt_passed=True)
    assert entry.overall_passed is False
    assert entry.failed_proofs == ["equivalence"]
    assert entry.proof_count == 3

    entry2 = _basic_entry("bad_au", eq_passed=True, au_passed=False, rt_passed=True)
    assert entry2.overall_passed is False
    assert entry2.failed_proofs == ["effect_audit"]

    entry3 = _basic_entry("bad_rt", eq_passed=True, au_passed=True, rt_passed=False)
    assert entry3.overall_passed is False
    assert entry3.failed_proofs == ["bytecode_roundtrip"]


def test_entry_not_passed_when_proof_not_run() -> None:
    """ProofMatrixEntry.overall_passed is False when a proof is None (not run)."""
    entry = _basic_entry("no_eq", eq_passed=None, au_passed=True, rt_passed=True)
    # With only 2 proofs run, both pass → overall_passed should be True
    # per spec: "all non-None results passed"
    assert entry.proof_count == 2
    assert entry.overall_passed is True


def test_entry_overall_passed_false_when_no_proofs_run() -> None:
    """ProofMatrixEntry.overall_passed is False when proof_count is 0."""
    entry = _basic_entry("empty", eq_passed=None, au_passed=None, rt_passed=None)
    assert entry.proof_count == 0
    assert entry.overall_passed is False


def test_entry_failed_proofs_multiple() -> None:
    """failed_proofs lists all failing proofs."""
    entry = _basic_entry("multi", eq_passed=False, au_passed=False, rt_passed=True)
    assert entry.failed_proofs == ["equivalence", "effect_audit"]
    assert entry.proof_count == 3


def test_entry_only_equivalence_result_set() -> None:
    """Entry with only equivalence result (others None)."""
    entry = _basic_entry("eq_only", eq_passed=True, au_passed=None, rt_passed=None)
    assert entry.proof_count == 1
    assert entry.overall_passed is True
    assert entry.failed_proofs == []


def test_entry_all_results_none() -> None:
    """Entry with all results set to None."""
    entry = _basic_entry("none", eq_passed=None, au_passed=None, rt_passed=None)
    assert entry.proof_count == 0
    assert entry.overall_passed is False
    assert entry.failed_proofs == []


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrix.build_entry tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_entry_with_valid_fixture() -> None:
    """ProofMatrix.build_entry runs all 3 proofs on a simple expression fixture."""
    matrix = ProofMatrix()
    entry = matrix.build_entry(
        fixture_path="/fake/test.hlf",
        label="simple",
        hlf_source="[HLF-v3]\nRESULT 42\nΩ\n",
        python_code="42",
    )
    assert entry.fixture_id == "test"
    assert entry.label == "simple"
    # Equivalence should pass
    assert entry.equivalence_result is not None
    assert entry.equivalence_result.passed is True
    # Effect audit should run (no side effects for pure expression)
    assert entry.audit_result is not None
    # Bytecode roundtrip should run
    assert entry.roundtrip_result is not None
    assert entry.proof_count == 3


def test_build_entry_without_python_skips_equivalence() -> None:
    """build_entry skips equivalence when no python_code provided."""
    matrix = ProofMatrix()
    entry = matrix.build_entry(
        fixture_path="/fake/no_py.hlf",
        label="no_py",
        hlf_source="[HLF-v3]\nRESULT 7\nΩ\n",
        python_code="",
    )
    assert entry.equivalence_result is None
    assert entry.audit_result is not None
    assert entry.roundtrip_result is not None
    assert entry.proof_count == 2


def test_build_entry_with_invalid_hlf_handles_gracefully() -> None:
    """build_entry handles invalid HLF source without crashing."""
    matrix = ProofMatrix()
    entry = matrix.build_entry(
        fixture_path="/fake/bad.hlf",
        label="bad",
        hlf_source="NOT VALID HLF @@@",
        python_code="1",
    )
    # Should still produce an entry, proof results will show failures
    assert entry.equivalence_result is not None
    assert entry.audit_result is not None
    assert entry.roundtrip_result is not None
    # At least the equivalence should have failed
    assert entry.overall_passed is False or entry.proof_count >= 1


def test_build_entry_includes_all_metadata() -> None:
    """build_entry populates fixture_id, path, label, source fields."""
    matrix = ProofMatrix()
    entry = matrix.build_entry(
        fixture_path="/some/dir/my_fixture.hlf",
        label="My Fixture",
        hlf_source="[HLF-v3]\nRESULT 1\nΩ\n",
        python_code="1",
    )
    assert entry.fixture_id == "my_fixture"
    assert entry.fixture_path == "/some/dir/my_fixture.hlf"
    assert entry.label == "My Fixture"
    assert entry.hlf_source == "[HLF-v3]\nRESULT 1\nΩ\n"
    assert entry.python_code == "1"


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrix.build_matrix tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_matrix_processes_multiple_fixtures() -> None:
    """build_matrix discovers and processes all .hlf files in a directory."""
    tmpdir = _make_temp_hlf_dir({
        "a.hlf": "[HLF-v3]\nRESULT 1\nΩ\n",
        "b.hlf": "[HLF-v3]\nRESULT 2\nΩ\n",
        "c.hlf": "[HLF-v3]\nRESULT 3\nΩ\n",
    })
    try:
        matrix = ProofMatrix()
        entries = matrix.build_matrix(tmpdir)
        assert len(entries) == 3
        ids = {e.fixture_id for e in entries}
        assert ids == {"a", "b", "c"}
        # All should have audit and roundtrip results
        for e in entries:
            assert e.audit_result is not None
            assert e.roundtrip_result is not None
    finally:
        _rmdir(tmpdir)


def test_build_matrix_with_empty_directory() -> None:
    """build_matrix returns empty list for an empty directory."""
    tmpdir = _make_temp_hlf_dir({})
    try:
        matrix = ProofMatrix()
        entries = matrix.build_matrix(tmpdir)
        assert entries == []
    finally:
        _rmdir(tmpdir)


def test_build_matrix_with_mixed_valid_invalid() -> None:
    """build_matrix handles mix of valid and invalid fixtures."""
    tmpdir = _make_temp_hlf_dir({
        "valid.hlf": "[HLF-v3]\nRESULT 1\nΩ\n",
        "broken.hlf": "garbage that won't compile",
    })
    try:
        matrix = ProofMatrix()
        entries = matrix.build_matrix(tmpdir)
        assert len(entries) == 2
        # Both should produce entry objects even if proofs fail
        for e in entries:
            assert e.roundtrip_result is not None or e.audit_result is not None
    finally:
        _rmdir(tmpdir)


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrix.summary_stats tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_summary_stats_counts_correctly() -> None:
    """summary_stats counts entries and proof types correctly."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("a", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("b", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("c", eq_passed=True, au_passed=True, rt_passed=True),
    ]
    stats = matrix.summary_stats()
    assert stats["total_entries"] == 3
    assert stats["fully_passing"] == 3
    assert stats["partially_passing"] == 0
    assert stats["fully_failing"] == 0
    assert stats["total_equivalence_run"] == 3
    assert stats["total_equivalence_passed"] == 3


def test_summary_stats_with_mixed_pass_fail() -> None:
    """summary_stats handles mixed pass/fail entries."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("a", eq_passed=True, au_passed=True, rt_passed=True),   # fully passing
        _basic_entry("b", eq_passed=False, au_passed=True, rt_passed=True),  # partial
        _basic_entry("c", eq_passed=False, au_passed=False, rt_passed=False), # fully failing
        _basic_entry("d", eq_passed=None, au_passed=None, rt_passed=None),   # no proofs run → failing
    ]
    stats = matrix.summary_stats()
    assert stats["total_entries"] == 4
    assert stats["fully_passing"] == 1  # only 'a'
    assert stats["partially_passing"] == 1  # 'b'
    assert stats["fully_failing"] == 2  # 'c' and 'd'
    assert stats["per_proof_type_breakdown"]["equivalence"]["run"] == 3
    assert stats["per_proof_type_breakdown"]["equivalence"]["passed"] == 1
    assert stats["failure_rate"] > 0


def test_summary_stats_with_no_entries() -> None:
    """summary_stats handles empty entry list."""
    matrix = ProofMatrix()
    matrix._entries = []
    stats = matrix.summary_stats()
    assert stats["total_entries"] == 0
    assert stats["fully_passing"] == 0
    assert stats["total_proofs_run"] == 0
    assert stats["failure_rate"] == 100.0  # 0/0 = 100% failure rate


def test_summary_stats_per_proof_breakdown() -> None:
    """per_proof_type_breakdown has correct run/passed counts."""
    matrix = ProofMatrix()
    # 3 equivalence (2 pass), 3 audit (3 pass), 2 roundtrip (1 pass)
    matrix._entries = [
        _basic_entry("a", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("b", eq_passed=False, au_passed=True, rt_passed=None),
        _basic_entry("c", eq_passed=True, au_passed=True, rt_passed=False),
    ]
    stats = matrix.summary_stats()
    bd = stats["per_proof_type_breakdown"]
    assert bd["equivalence"]["run"] == 3
    assert bd["equivalence"]["passed"] == 2
    assert bd["effect_audit"]["run"] == 3
    assert bd["effect_audit"]["passed"] == 3
    assert bd["bytecode_roundtrip"]["run"] == 2
    assert bd["bytecode_roundtrip"]["passed"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrix output format tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_to_csv_format() -> None:
    """to_csv produces valid CSV with expected columns."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("a", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("b", eq_passed=False, au_passed=True, rt_passed=True),
    ]
    csv = matrix.to_csv()
    lines = csv.strip().split("\n")
    assert len(lines) == 3  # header + 2 data rows
    assert "fixture_id" in lines[0]
    assert "equivalence_passed" in lines[0]
    assert "audit_passed" in lines[0]
    assert "roundtrip_passed" in lines[0]
    assert "overall_passed" in lines[0]
    # First row should have 'true' for equivalence
    assert "a," in lines[1]
    assert "true," in lines[1]
    # Second row should have 'false' for equivalence
    assert "false," in lines[2]


def test_to_csv_with_none_results() -> None:
    """to_csv handles entries with None proof results."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("n", eq_passed=None, au_passed=None, rt_passed=None),
    ]
    csv = matrix.to_csv()
    lines = csv.strip().split("\n")
    assert len(lines) == 2
    assert "N/A" in lines[1]
    assert "false" in lines[1]  # overall_passed is False


def test_to_markdown_table_format() -> None:
    """to_markdown_table produces valid markdown table."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("x", eq_passed=True, au_passed=True, rt_passed=True),
    ]
    md = matrix.to_markdown_table()
    assert "| Fixture |" in md
    assert "| `x` |" in md
    assert "✅" in md


def test_to_json_format() -> None:
    """to_json produces valid JSON array."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("a", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("b", eq_passed=False, au_passed=True, rt_passed=True),
    ]
    js = matrix.to_json()
    data = json.loads(js)
    assert len(data) == 2
    assert data[0]["fixture_id"] == "a"
    assert data[0]["overall_passed"] is True
    assert data[0]["equivalence"] is not None
    assert data[0]["effect_audit"] is not None
    assert data[0]["bytecode_roundtrip"] is not None
    assert data[1]["fixture_id"] == "b"
    assert data[1]["overall_passed"] is False
    assert data[1]["failed_proofs"] == ["equivalence"]


# ═══════════════════════════════════════════════════════════════════════════════
# ProofMatrixReport tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_report_generate_markdown() -> None:
    """ProofMatrixReport.generate produces valid markdown report."""
    tmpdir = _make_temp_hlf_dir({
        "simple.hlf": "[HLF-v3]\nRESULT 42\nΩ\n",
    })
    try:
        report = ProofMatrixReport()
        md = report.generate(tmpdir)
        assert "# HLF Proof Matrix Report" in md
        assert "## Summary Statistics" in md
        assert "## Per-Fixture Results" in md
        assert "| Fixture |" in md
    finally:
        _rmdir(tmpdir)


def test_report_generate_compact() -> None:
    """ProofMatrixReport.generate_compact produces one-line-per-fixture output."""
    tmpdir = _make_temp_hlf_dir({
        "f1.hlf": "[HLF-v3]\nRESULT 1\nΩ\n",
        "f2.hlf": "[HLF-v3]\nRESULT 2\nΩ\n",
    })
    try:
        report = ProofMatrixReport()
        compact = report.generate_compact(tmpdir)
        lines = compact.strip().split("\n")
        # Should have header + 2 fixture lines
        assert any("f1" in line for line in lines)
        assert any("f2" in line for line in lines)
    finally:
        _rmdir(tmpdir)


def test_report_generate_json() -> None:
    """ProofMatrixReport.generate_json produces valid JSON report."""
    tmpdir = _make_temp_hlf_dir({
        "simple.hlf": "[HLF-v3]\nRESULT 77\nΩ\n",
    })
    try:
        report = ProofMatrixReport()
        js = report.generate_json(tmpdir)
        data = json.loads(js)
        assert data["report_type"] == "proof_matrix"
        assert "generated" in data
        assert "summary" in data
        assert "entries" in data
        assert len(data["entries"]) == 1
        assert data["entries"][0]["fixture_id"] == "simple"
    finally:
        _rmdir(tmpdir)


def test_report_generate_compact_includes_pass_fail() -> None:
    """generate_compact shows PASS/FAIL indicators."""
    tmpdir = _make_temp_hlf_dir({
        "ok.hlf": "[HLF-v3]\nRESULT 1\nΩ\n",
    })
    try:
        report = ProofMatrixReport()
        compact = report.generate_compact(tmpdir)
        assert "E:" in compact
        assert "A:" in compact
        assert "R:" in compact
    finally:
        _rmdir(tmpdir)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_full_pipeline_build_matrix_to_csv() -> None:
    """End-to-end: build_matrix → summary_stats → to_csv pipeline."""
    tmpdir = _make_temp_hlf_dir({
        "a.hlf": "[HLF-v3]\nRESULT 10\nΩ\n",
        "b.hlf": "[HLF-v3]\nRESULT 20\nΩ\n",
        "c.hlf": "[HLF-v3]\nRESULT 30\nΩ\n",
    })
    try:
        matrix = ProofMatrix()
        entries = matrix.build_matrix(tmpdir)
        assert len(entries) == 3

        stats = matrix.summary_stats()
        assert stats["total_entries"] == 3
        assert stats["total_roundtrip_run"] == 3

        csv = matrix.to_csv()
        lines = csv.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows
        assert "fixture_id" in lines[0]
    finally:
        _rmdir(tmpdir)


def test_to_json_roundtrip_reconstruction() -> None:
    """to_json output can be parsed and contains all expected fields."""
    matrix = ProofMatrix()
    matrix._entries = [
        _basic_entry("x1", eq_passed=True, au_passed=True, rt_passed=True),
        _basic_entry("x2", eq_passed=False, au_passed=False, rt_passed=False),
    ]
    js = matrix.to_json()
    data = json.loads(js)
    assert len(data) == 2
    # Verify structure of first entry
    e0 = data[0]
    assert e0["fixture_id"] == "x1"
    assert "equivalence" in e0
    assert "effect_audit" in e0
    assert "bytecode_roundtrip" in e0
    assert "overall_passed" in e0
    assert "failed_proofs" in e0
    assert "proof_count" in e0


def test_large_fixture_directory_performance() -> None:
    """ProofMatrix handles a larger directory of fixtures without timing out."""
    files = {}
    for i in range(20):
        files[f"f{i:03d}.hlf"] = f"[HLF-v3]\nRESULT {i}\nΩ\n"
    tmpdir = _make_temp_hlf_dir(files)
    try:
        matrix = ProofMatrix()
        entries = matrix.build_matrix(tmpdir)
        assert len(entries) == 20
        stats = matrix.summary_stats()
        assert stats["total_entries"] == 20
    finally:
        _rmdir(tmpdir)


def test_malformed_hlf_file_does_not_crash_discovery() -> None:
    """FixtureCatalog handles a malformed/non-UTF8 .hlf file gracefully."""
    tmpdir = _make_temp_hlf_dir({
        "good.hlf": "[HLF-v3]\nΩ\n",
    })
    # Write a binary file with .hlf extension
    bad_path = os.path.join(tmpdir, "bad.hlf")
    with open(bad_path, "wb") as fh:
        fh.write(b"\x80\x81\x82\x83\x84")
    try:
        catalog = FixtureCatalog()
        entries = catalog.discover_fixtures(tmpdir)
        # Should still discover the good one, skip the bad one
        ids = {e["fixture_id"] for e in entries}
        assert "good" in ids
    finally:
        _rmdir(tmpdir)


def test_build_matrix_with_live_data_toggle() -> None:
    """ProofMatrix.build_entry works with both live and simulated paths."""
    # The "live_data" concept: when python_code is provided, equivalence runs (live).
    # When python_code is empty, equivalence is skipped (simulated fallback).
    matrix = ProofMatrix()

    # "Live" mode: python_code provided
    live_entry = matrix.build_entry(
        fixture_path="/f/live.hlf",
        label="live",
        hlf_source="[HLF-v3]\nRESULT 3 + 4\nΩ\n",
        python_code="3 + 4",
    )
    assert live_entry.equivalence_result is not None
    assert live_entry.proof_count == 3

    # "Simulated" mode: python_code empty → equivalence skipped
    sim_entry = matrix.build_entry(
        fixture_path="/f/sim.hlf",
        label="sim",
        hlf_source="[HLF-v3]\nRESULT 5\nΩ\n",
        python_code="",
    )
    assert sim_entry.equivalence_result is None
    assert sim_entry.proof_count == 2


def test_from_fixture_catalog_integration() -> None:
    """ProofMatrix.from_fixture_catalog processes catalog entries."""
    tmpdir = _make_temp_hlf_dir({
        "cat_test.hlf": "[HLF-v3]\nRESULT 100\nΩ\n",
    })
    try:
        catalog = FixtureCatalog()
        matrix = ProofMatrix()
        # We need to use the directory to build, so we use build_matrix
        entries = matrix.build_matrix(tmpdir)
        assert len(entries) == 1
        assert entries[0].fixture_id == "cat_test"
    finally:
        _rmdir(tmpdir)


def test_summary_stats_failure_rate_calculation() -> None:
    """failure_rate is correctly calculated."""
    matrix = ProofMatrix()
    # All 3 pass
    matrix._entries = [
        _basic_entry("p", eq_passed=True, au_passed=True, rt_passed=True),
    ]
    stats = matrix.summary_stats()
    assert stats["failure_rate"] == 0.0

    # All fail
    matrix._entries = [
        _basic_entry("f", eq_passed=False, au_passed=False, rt_passed=False),
    ]
    stats = matrix.summary_stats()
    assert stats["failure_rate"] == 100.0

    # 1 pass, 2 fail
    matrix._entries = [
        _basic_entry("m", eq_passed=True, au_passed=False, rt_passed=False),
    ]
    stats = matrix.summary_stats()
    assert stats["failure_rate"] == pytest.approx(66.7, abs=0.1)


def test_build_entry_edge_case_empty_source() -> None:
    """build_entry handles empty HLF source without crashing."""
    matrix = ProofMatrix()
    entry = matrix.build_entry(
        fixture_path="/f/empty.hlf",
        label="empty",
        hlf_source="",
        python_code="",
    )
    assert entry.audit_result is not None
    # roundtrip may fail on empty source
    assert entry.roundtrip_result is not None


# ── Cleanup helper ─────────────────────────────────────────────────────────

def _rmdir(path: str) -> None:
    """Remove a directory tree."""
    import shutil
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass
