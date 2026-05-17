"""Tests for hlf_mcp.hlf.workflow_benchmark and server_workflow_benchmark."""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.workflow_benchmark import (
    BenchmarkTask,
    WorkflowBenchmark,
    _TASK_CORPUS,
    run_workflow_benchmark,
)
from hlf_mcp.server_workflow_benchmark import register_workflow_benchmark_tools


class FakeMcp:
    """Fake MCP for testing that passes through decorators."""

    def tool(self):
        def decorator(fn):
            return fn

        return decorator


class _FakeCtx:
    pass


# ── BenchmarkTask ─────────────────────────────────────────────────────────────


def test_task_corpus_nonempty():
    assert len(_TASK_CORPUS) > 0
    for t in _TASK_CORPUS:
        assert t.task_id
        assert t.expected_tags
        assert t.expected_concepts


# ── WorkflowBenchmark internals ──────────────────────────────────────────────────


def test_check_tags_found_and_missing():
    source = "Δ [INTENT] goal=hello\n  Ж [ASSERT] status=ok"
    found, missing = WorkflowBenchmark._check_tags(source, ["INTENT", "ASSERT", "VOTE"])
    assert "INTENT" in found
    assert "ASSERT" in found
    assert "VOTE" in missing


def test_check_concepts_found_and_missing():
    source = "Δ [INTENT] goal=hello\n  ∇ [RESULT] message=world"
    found, missing = WorkflowBenchmark._check_concepts(source, ["hello", "world", "missing"])
    assert "hello" in found
    assert "world" in found
    assert "missing" in missing


def test_count_statements():
    source = (
        "[HLF-v3]\n"
        "Δ [INTENT] goal=hello\n"
        "  Ж [ASSERT] status=ok\n"
        "  ∇ [RESULT] message=world\n"
        "Ω\n"
        "# comment\n"
    )
    assert WorkflowBenchmark._count_statements(source) == 3


def test_hlf_to_nl_basic():
    source = (
        "[HLF-v3]\n"
        "Δ [INTENT] goal=hello\n"
        "  Ж [ASSERT] status=ok\n"
        "Ω\n"
    )
    nl = WorkflowBenchmark._hlf_to_nl(source)
    assert "Action:" in nl or "Intent:" in nl
    assert "hello" in nl.lower()


# ── run_task with fake translator ─────────────────────────────────────────────


def _fake_translator(text: str) -> dict[str, str]:
    # Minimal valid HLF for testing
    return {
        "source": (
            "[HLF-v3]\n"
            f"Δ [INTENT] goal=\"{text[:20]}\"\n"
            "  Ж [ASSERT] status=ok\n"
            "Ω\n"
        )
    }


def test_run_task_produces_metrics():
    bench = WorkflowBenchmark()
    task = BenchmarkTask(
        task_id="test",
        description="Say hello",
        domain="greeting",
        expected_tags=["INTENT", "ASSERT"],
        expected_concepts=["hello"],
        min_statements=2,
        max_gas=100,
    )
    result = bench.run_task(task, _fake_translator)

    assert result["task_id"] == "test"
    assert result["domain"] == "greeting"
    assert result["status"] == "ok"
    assert result["trace_ref"]
    assert result["hlf_source"]
    assert result["natural_language"]

    metrics = result["metrics"]
    assert metrics["timing_ns"]["translation"] >= 0
    assert metrics["timing_ns"]["total"] >= metrics["timing_ns"]["translation"]
    assert metrics["tokens"]["input"] > 0
    assert metrics["tokens"]["hlf"] > 0
    assert metrics["quality"]["compile_success"] is True
    assert metrics["scope"]["scope_score"] > 0
    assert metrics["scope"]["thoroughness_score"] > 0
    assert metrics["gas"]["estimate"] >= 0
    assert metrics["gas"]["efficiency"] >= 0


def test_run_task_missing_tags_detected():
    bench = WorkflowBenchmark()
    task = BenchmarkTask(
        task_id="test",
        description="Say hello",
        domain="greeting",
        expected_tags=["INTENT", "ASSERT", "VOTE"],
        expected_concepts=["hello"],
        min_statements=2,
        max_gas=100,
    )
    result = bench.run_task(task, _fake_translator)
    assert result["metrics"]["scope"]["tags_missing"] == ["VOTE"]


# ── run_suite ──────────────────────────────────────────────────────────────────


def test_run_suite_summary():
    report = run_workflow_benchmark(
        translator_fn=_fake_translator,
        tasks=_TASK_CORPUS[:2],
        delivery_mode="auto",
        auto_repair=True,
    )

    assert report["status"] == "ok"
    summary = report["summary"]
    assert summary["tasks_run"] == 2
    assert 0.0 <= summary["compile_success_rate"] <= 1.0
    assert summary["avg_total_tokens"] > 0
    assert summary["avg_time_ms"] >= 0
    assert summary["avg_scope_score"] >= 0
    assert summary["avg_thoroughness_score"] >= 0
    assert "delivery_mode" in summary
    assert "auto_repair_enabled" in summary
    assert report["trace_ref"]
    assert len(report["results"]) == 2


# ── MCP tool registration ──────────────────────────────────────────────────────


def test_register_workflow_benchmark_tools():
    mcp = FakeMcp()
    tools = register_workflow_benchmark_tools(mcp)
    assert "hlf_workflow_benchmark" in tools
    assert "hlf_workflow_benchmark_custom_task" in tools

    # Verify tool callables exist
    assert callable(tools["hlf_workflow_benchmark"])
    assert callable(tools["hlf_workflow_benchmark_custom_task"])


# ── Integration: full corpus ────────────────────────────────────────────────────


def test_full_corpus_run():
    """Run the full task corpus with the fake translator to ensure no exceptions."""
    report = run_workflow_benchmark(
        translator_fn=_fake_translator,
        delivery_mode="auto",
        auto_repair=True,
    )
    assert report["status"] == "ok"
    assert report["summary"]["tasks_run"] == len(_TASK_CORPUS)
    for r in report["results"]:
        assert r["status"] in ("ok", "compile_error")
        assert r["trace_ref"]
