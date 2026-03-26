"""Tests for memory write-path enforcement (Fix 1 — depth audit).

Validates that store() rejects bad input at the gate level and that
strict mode enforces provenance + evidence metadata for evidence-class entries.
"""

from __future__ import annotations

import pytest

from hlf_mcp.rag.memory import RAGMemory


@pytest.fixture()
def mem(tmp_path):
    return RAGMemory(str(tmp_path / "test_enforce.db"))


# ── Basic gate (always enforced) ──────────────────────────────────────────

class TestBasicGate:
    def test_empty_content_rejected(self, mem):
        result = mem.store("")
        assert result["stored"] is False
        assert result["error"] == "empty_content"

    def test_whitespace_only_content_rejected(self, mem):
        result = mem.store("   \n\t  ")
        assert result["stored"] is False
        assert result["error"] == "empty_content"

    def test_confidence_below_zero_rejected(self, mem):
        result = mem.store("valid content", confidence=-0.1)
        assert result["stored"] is False
        assert result["error"] == "confidence_out_of_range"

    def test_confidence_above_one_rejected(self, mem):
        result = mem.store("valid content", confidence=1.01)
        assert result["stored"] is False
        assert result["error"] == "confidence_out_of_range"

    def test_confidence_edge_zero_accepted(self, mem):
        result = mem.store("edge zero", confidence=0.0)
        assert result.get("stored") is True

    def test_confidence_edge_one_accepted(self, mem):
        result = mem.store("edge one", confidence=1.0)
        assert result.get("stored") is True

    def test_valid_content_passes_gate(self, mem):
        result = mem.store("valid fact content")
        assert result.get("stored") is True
        assert result.get("sha256")


# ── Strict mode enforcement ───────────────────────────────────────────────

class TestStrictMode:
    def test_invalid_provenance_rejected(self, mem):
        result = mem.store(
            "strict test",
            provenance="made_up_source",
            strict=True,
        )
        assert result["stored"] is False
        assert "provenance" in result["error"]

    def test_valid_provenance_accepted(self, mem):
        for prov in ("agent", "operator", "system", "pipeline", "hks_capture"):
            result = mem.store(f"fact from {prov}", provenance=prov, strict=True)
            assert result.get("stored") is True, f"provenance={prov} should pass"

    def test_evidence_entry_without_source_type_rejected(self, mem):
        result = mem.store(
            "evidence without source_type",
            provenance="agent",
            entry_kind="evidence",
            metadata={},
            strict=True,
        )
        assert result["stored"] is False
        assert "source_type" in result["error"]

    def test_hks_entry_without_source_type_rejected(self, mem):
        result = mem.store(
            "hks exemplar without source_type",
            provenance="hks_capture",
            entry_kind="hks_exemplar",
            metadata={"governed_evidence": {}},
            strict=True,
        )
        assert result["stored"] is False
        assert "source_type" in result["error"]

    def test_evidence_entry_with_source_type_accepted(self, mem):
        result = mem.store(
            "properly governed evidence",
            provenance="agent",
            entry_kind="evidence",
            metadata={
                "governed_evidence": {
                    "source_type": "benchmark_result",
                }
            },
            strict=True,
        )
        assert result.get("stored") is True

    def test_hks_entry_with_source_type_accepted(self, mem):
        result = mem.store(
            "properly governed hks exemplar",
            provenance="hks_capture",
            entry_kind="hks_exemplar",
            metadata={
                "governed_evidence": {
                    "source_type": "hks_exemplar",
                }
            },
            strict=True,
        )
        assert result.get("stored") is True

    def test_fact_entry_not_blocked_by_evidence_rule(self, mem):
        """entry_kind='fact' should not trigger evidence/hks source_type check."""
        result = mem.store(
            "just a normal fact",
            provenance="agent",
            entry_kind="fact",
            metadata={},
            strict=True,
        )
        assert result.get("stored") is True

    def test_strict_false_does_not_enforce_provenance(self, mem):
        """Default strict=False should allow any provenance string."""
        result = mem.store(
            "loose provenance",
            provenance="totally_custom_source",
            strict=False,
        )
        assert result.get("stored") is True
