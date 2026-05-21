"""Tests for HLF token compression benchmark overhaul."""

import pytest
from hlf_mcp.hlf.benchmark import (
    HLFBenchmark,
    _COMPLEX_WORKFLOW_HLF,
)


def test_scale_curve_returns_crossover():
    b = HLFBenchmark()
    curve = b.benchmark_scale_curve()
    assert "curve" in curve
    assert "crossover_point" in curve
    assert len(curve["curve"]) == 9  # 1,3,5,7,10,15,20,30,50
    # Verify HLF wins at scale (N>=15 should have positive compression)
    large_steps = [p for p in curve["curve"] if p["steps"] >= 15]
    assert all(p["compression_pct"] > 0 for p in large_steps), "HLF should win at scale >=15"


def test_benchmark_suite_includes_all_categories():
    b = HLFBenchmark()
    result = b.benchmark_suite()
    assert "simple" in result
    assert "complex" in result
    assert "swarm" in result
    assert "scale_curve" in result
    assert "overall_summary" in result


def test_benchmark_suite_with_live_translator():
    b = HLFBenchmark()
    result = b.benchmark_suite(use_live_translator=True)
    assert result["use_live_translator"] is True
    # simple results should have live_hlf_tokens
    assert "live_hlf_tokens" in result["simple"]["results"][0]


def test_real_workflow_benchmark():
    b = HLFBenchmark()
    result = b.benchmark_real_workflow()
    assert result["workflow_name"] == "dream_cycle_observe_propose_verify_promote"
    assert result["nlp_tokens"] > 0
    assert result["hlf_tokens"] > 0
    assert "compression_pct" in result


def test_complex_workflow_hlf_governance_first():
    # Verify the rewritten templates don't use ⚡ [STEP N] syntax
    for key in ["incident_response_7step", "multi_service_deploy_5step", "data_pipeline_6step"]:
        assert "⚡ [STEP" not in _COMPLEX_WORKFLOW_HLF[key], f"{key} should use governance-first"
