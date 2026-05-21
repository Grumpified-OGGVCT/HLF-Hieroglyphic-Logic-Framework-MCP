"""
Tests for Compatibility Matrix (ecosystem/compatibility_matrix.py).

Validates:
  - CompatibilityMatrixEntry construction and to_dict/from_dict
  - CompatibilityMatrix default matrix population
  - get_supported_languages() returns 5 languages
  - get_feature_coverage() returns correct per-language data
  - render_markdown_table() produces valid GFM table
  - render_json_matrix() produces valid JSON
  - languages_with_feature() filtering
  - feature_coverage_summary() aggregation
  - Compact markdown rendering
  - Edge cases: unknown language, empty feature query
"""

from __future__ import annotations

import json
import os
import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.ecosystem.compatibility_matrix import (
    CompatibilityMatrixEntry,
    CompatibilityMatrix,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def matrix() -> CompatibilityMatrix:
    """Fresh compatibility matrix instance."""
    return CompatibilityMatrix()


@pytest.fixture
def entry_python() -> CompatibilityMatrixEntry:
    """A fully-supported Python entry."""
    return CompatibilityMatrixEntry(
        language="Python",
        mcp_client=True,
        rest_client=True,
        sdk_gen=True,
        typed_contracts=True,
        provenance_passthrough=True,
        rate_limiting=True,
        credential_management=True,
        transport_sse=True,
        transport_stdio=True,
        transport_streamable_http=True,
        notes="Full support",
    )


@pytest.fixture
def entry_minimal() -> CompatibilityMatrixEntry:
    """A minimal entry with no features."""
    return CompatibilityMatrixEntry(
        language="MinimalLang",
        notes="No features",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CompatibilityMatrixEntry tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompatibilityMatrixEntry:
    """Tests for the CompatibilityMatrixEntry dataclass."""

    def test_default_all_false(self) -> None:
        """Default entry has all features disabled."""
        entry = CompatibilityMatrixEntry(language="Test")
        assert entry.mcp_client is False
        assert entry.rest_client is False
        assert entry.sdk_gen is False
        assert entry.typed_contracts is False

    def test_full_entry_all_true(self, entry_python: CompatibilityMatrixEntry) -> None:
        """Full Python entry has all features enabled."""
        assert entry_python.mcp_client is True
        assert entry_python.rest_client is True
        assert entry_python.sdk_gen is True
        assert entry_python.typed_contracts is True
        assert entry_python.provenance_passthrough is True
        assert entry_python.rate_limiting is True
        assert entry_python.credential_management is True
        assert entry_python.transport_sse is True
        assert entry_python.transport_stdio is True
        assert entry_python.transport_streamable_http is True

    def test_to_dict(self, entry_python: CompatibilityMatrixEntry) -> None:
        """to_dict produces correct dictionary."""
        d = entry_python.to_dict()
        assert d["language"] == "Python"
        assert d["mcp_client"] is True
        assert d["notes"] == "Full support"

    def test_from_dict_roundtrip(self, entry_python: CompatibilityMatrixEntry) -> None:
        """from_dict(to_dict(x)) == x"""
        d = entry_python.to_dict()
        restored = CompatibilityMatrixEntry.from_dict(d)
        assert restored.language == entry_python.language
        assert restored.mcp_client == entry_python.mcp_client
        assert restored.notes == entry_python.notes

    def test_minimal_entry(self, entry_minimal: CompatibilityMatrixEntry) -> None:
        """Minimal entry has all features False."""
        assert entry_minimal.language == "MinimalLang"
        assert entry_minimal.mcp_client is False
        assert entry_minimal.notes == "No features"


# ═══════════════════════════════════════════════════════════════════════════════
# CompatibilityMatrix tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompatibilityMatrix:
    """Tests for the CompatibilityMatrix class."""

    def test_matrix_has_five_languages(self, matrix: CompatibilityMatrix) -> None:
        """Default matrix contains 5 languages."""
        assert len(matrix) == 5
        assert len(matrix.entries) == 5

    def test_get_supported_languages(self, matrix: CompatibilityMatrix) -> None:
        """get_supported_languages returns all language names."""
        languages = matrix.get_supported_languages()
        assert "Python" in languages
        assert "TypeScript" in languages
        assert "Java" in languages
        assert "Rust" in languages
        assert "Go" in languages
        assert len(languages) == 5

    def test_get_feature_coverage_python(self, matrix: CompatibilityMatrix) -> None:
        """Python has full feature coverage."""
        coverage = matrix.get_feature_coverage("Python")
        assert coverage["mcp_client"] is True
        assert coverage["rest_client"] is True
        assert coverage["sdk_gen"] is True
        assert coverage["typed_contracts"] is True
        assert coverage["provenance_passthrough"] is True
        assert coverage["language"] == "Python"

    def test_get_feature_coverage_java(self, matrix: CompatibilityMatrix) -> None:
        """Java has SDK gen + typed contracts but not MCP/REST client."""
        coverage = matrix.get_feature_coverage("Java")
        assert coverage["sdk_gen"] is True
        assert coverage["typed_contracts"] is True
        assert coverage["mcp_client"] is False
        assert coverage["rest_client"] is False

    def test_get_feature_coverage_rust(self, matrix: CompatibilityMatrix) -> None:
        """Rust has SDK gen + typed contracts."""
        coverage = matrix.get_feature_coverage("Rust")
        assert coverage["sdk_gen"] is True
        assert coverage["typed_contracts"] is True

    def test_get_feature_coverage_go(self, matrix: CompatibilityMatrix) -> None:
        """Go has REST client only."""
        coverage = matrix.get_feature_coverage("Go")
        assert coverage["rest_client"] is True
        assert coverage["sdk_gen"] is False
        assert coverage["mcp_client"] is False

    def test_get_feature_coverage_case_insensitive(self, matrix: CompatibilityMatrix) -> None:
        """Feature coverage lookup is case-insensitive."""
        coverage_lower = matrix.get_feature_coverage("python")
        coverage_upper = matrix.get_feature_coverage("PYTHON")
        assert coverage_lower["language"] == "Python"
        assert coverage_upper["language"] == "Python"

    def test_get_feature_coverage_unknown_returns_empty(self, matrix: CompatibilityMatrix) -> None:
        """Unknown language returns empty dict."""
        coverage = matrix.get_feature_coverage("Klingon")
        assert coverage == {}

    def test_get_entry_returns_none_for_unknown(self, matrix: CompatibilityMatrix) -> None:
        """get_entry returns None for unknown language."""
        assert matrix.get_entry("Brainfuck") is None

    def test_get_entry_returns_entry_for_known(self, matrix: CompatibilityMatrix) -> None:
        """get_entry returns correct entry for known language."""
        entry = matrix.get_entry("Python")
        assert entry is not None
        assert entry.language == "Python"

    def test_languages_with_feature_mcp_client(self, matrix: CompatibilityMatrix) -> None:
        """Only Python and TypeScript have MCP client support."""
        mcp_langs = matrix.languages_with_feature("mcp_client")
        assert "Python" in mcp_langs
        assert "TypeScript" in mcp_langs
        assert "Java" not in mcp_langs
        assert len(mcp_langs) == 2

    def test_languages_with_feature_sdk_gen(self, matrix: CompatibilityMatrix) -> None:
        """Python, TypeScript, Java, Rust have SDK gen."""
        sdk_langs = matrix.languages_with_feature("sdk_gen")
        assert "Python" in sdk_langs
        assert "TypeScript" in sdk_langs
        assert "Java" in sdk_langs
        assert "Rust" in sdk_langs
        assert "Go" not in sdk_langs
        assert len(sdk_langs) == 4

    def test_feature_coverage_summary(self, matrix: CompatibilityMatrix) -> None:
        """Summary returns correct counts."""
        summary = matrix.feature_coverage_summary()
        assert summary["total_languages"] == 5
        assert summary["mcp_client"] == 2
        assert summary["rest_client"] == 3  # Python, TypeScript, Go
        assert summary["sdk_gen"] == 4  # Python, TypeScript, Java, Rust

    def test_iteration(self, matrix: CompatibilityMatrix) -> None:
        """Matrix is iterable over entries."""
        languages = [e.language for e in matrix]
        assert languages == ["Python", "TypeScript", "Java", "Rust", "Go"]


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMarkdownRendering:
    """Tests for markdown table rendering."""

    def test_render_markdown_table_has_headers(self, matrix: CompatibilityMatrix) -> None:
        """Markdown table includes all expected column headers."""
        md = matrix.render_markdown_table()
        assert "| Language |" in md
        assert "MCP Client" in md
        assert "REST Client" in md
        assert "SDK Gen" in md
        assert "Typed Contracts" in md
        assert "Provenance" in md
        assert "Notes" in md

    def test_render_markdown_table_has_separator(self, matrix: CompatibilityMatrix) -> None:
        """Markdown table has a separator row."""
        md = matrix.render_markdown_table()
        assert " --- " in md

    def test_render_markdown_table_has_all_languages(self, matrix: CompatibilityMatrix) -> None:
        """Markdown table includes all 5 languages."""
        md = matrix.render_markdown_table()
        assert "Python" in md
        assert "TypeScript" in md
        assert "Java" in md
        assert "Rust" in md
        assert "Go" in md

    def test_render_markdown_uses_checkmarks(self, matrix: CompatibilityMatrix) -> None:
        """Markdown table uses ✅ and ❌ for boolean values."""
        md = matrix.render_markdown_table()
        assert "✅" in md
        assert "❌" in md

    def test_render_compact_has_fewer_columns(self, matrix: CompatibilityMatrix) -> None:
        """Compact table has fewer columns than full table."""
        compact = matrix.render_compact()
        full = matrix.render_markdown_table()
        # Compact should have fewer column separators
        assert compact.count(" --- ") < full.count(" --- ")


class TestJSONRendering:
    """Tests for JSON matrix rendering."""

    def test_render_json_matrix_is_valid_json(self, matrix: CompatibilityMatrix) -> None:
        """JSON output is valid parseable JSON."""
        json_str = matrix.render_json_matrix()
        parsed = json.loads(json_str)
        assert "compatibility_matrix" in parsed
        assert "generated_by" in parsed

    def test_render_json_matrix_has_all_entries(self, matrix: CompatibilityMatrix) -> None:
        """JSON output contains all 5 entries."""
        json_str = matrix.render_json_matrix()
        parsed = json.loads(json_str)
        assert len(parsed["compatibility_matrix"]) == 5

    def test_render_json_matrix_entries_have_language(self, matrix: CompatibilityMatrix) -> None:
        """Each JSON entry has a language field."""
        json_str = matrix.render_json_matrix()
        parsed = json.loads(json_str)
        for entry in parsed["compatibility_matrix"]:
            assert "language" in entry
            assert isinstance(entry["language"], str)

    def test_json_matrix_python_full_support(self, matrix: CompatibilityMatrix) -> None:
        """Python entry in JSON has all features true."""
        json_str = matrix.render_json_matrix()
        parsed = json.loads(json_str)
        py_entry = next(
            e for e in parsed["compatibility_matrix"] if e["language"] == "Python"
        )
        features = [
            "mcp_client", "rest_client", "sdk_gen", "typed_contracts",
            "provenance_passthrough", "rate_limiting", "credential_management",
        ]
        for feat in features:
            assert py_entry[feat] is True, f"Python.{feat} should be True"
