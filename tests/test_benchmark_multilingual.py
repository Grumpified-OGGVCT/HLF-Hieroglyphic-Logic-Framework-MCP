from __future__ import annotations

import pytest

from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.rag.memory import RAGMemory


def test_multilingual_matrix_defaults_include_chinese_with_full_domain_coverage() -> None:
    benchmark = HLFBenchmark()

    matrix = benchmark.multilingual_matrix()

    assert "zh" in matrix["languages"]
    assert "zh" in matrix["per_language"]
    assert matrix["per_language"]["zh"]["samples"] == len(matrix["domains"])

    chinese_rows = [row for row in matrix["rows"] if row["language"] == "zh"]
    assert len(chinese_rows) == len(matrix["domains"])
    assert all("roundtrip_fidelity_score" in row for row in chinese_rows)
    assert all("fallback_used" in row for row in chinese_rows)


def test_language_comparison_summary_ranks_only_measured_languages() -> None:
    benchmark = HLFBenchmark()

    summary = benchmark.language_comparison_summary(languages=["en", "fr", "zh", "es", "ar"])

    assert summary["ranking_policy"] == [
        "roundtrip_fidelity_avg_desc",
        "fallback_rate_asc",
        "compression_pct_desc",
        "language_asc",
    ]
    assert summary["leader"] is not None
    assert [entry["language"] for entry in summary["ranked_languages"]] == summary["languages"] or len(summary["ranked_languages"]) == len(summary["languages"])
    assert any(entry["language"] == "zh" for entry in summary["ranked_languages"])
    assert all("roundtrip_fidelity_avg" in entry for entry in summary["ranked_languages"])
    assert all("fallback_rate" in entry for entry in summary["ranked_languages"])
    assert all("compression_pct" in entry for entry in summary["ranked_languages"])


def test_multilingual_matrix_rejects_unimplemented_language_lanes() -> None:
    benchmark = HLFBenchmark()

    with pytest.raises(ValueError, match="Missing benchmark template"):
        benchmark.multilingual_matrix(languages=["en", "zh", "de"])


def test_translation_memory_retrieval_matrix_reports_chinese_quality() -> None:
    benchmark = HLFBenchmark()
    memory = RAGMemory()

    result = benchmark.translation_memory_retrieval_matrix(
        memory,
        domains=["security_audit", "hello_world"],
        languages=["en", "zh"],
        top_k=2,
        topic="translation_memory_benchmark_test",
    )

    assert "zh" in result["per_language"]
    assert result["per_language"]["zh"]["samples"] == 2
    assert result["per_language"]["zh"]["same_language_hit_rate"] >= 0.5
    assert result["per_language"]["zh"]["retrieval_quality_avg"] >= 0.5