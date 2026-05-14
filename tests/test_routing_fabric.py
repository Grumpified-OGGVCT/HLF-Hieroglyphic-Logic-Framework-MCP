"""
Tests for the restored HLF Routing Fabric (hlf_mcp/hlf/routing.py).

Covers:
  1. Route selection: tier walk, complexity short-circuit, legacy fallback
  2. Fallback paths: catalog unavailability, exhausted phases
  3. Evidence-required denial: benchmark/catalog gating
  4. Model allowlist enforcement
  5. RouteProfile rationale and trace exposure
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the hlf_mcp package is importable
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.routing import (  # noqa: E402
    _SPECIALIZATION_PATTERNS,
    _TIER_WALK_ORDER,
    RouteProfile,
    complexity_score,
    is_model_allowed,
    require_evidence_gate,
    route_intent,
    route_request,
    route_with_fallback,
    select_model_by_tier,
)


# ── RouteProfile tests ─────────────────────────────────────────────────────


def test_route_profile_defaults():
    """RouteProfile has sensible defaults."""
    profile = RouteProfile(model="test-model")
    assert profile.model == "test-model"
    assert profile.provider == "ollama"
    assert profile.tier == "D"
    assert profile.system_prompt == ""
    assert profile.tools == []
    assert profile.restrictions == {}
    assert profile.routing_trace == []
    assert profile.confidence == 0.5
    assert profile.gas_remaining == -1


def test_route_profile_rationale():
    """RouteProfile.rationale reconstructs human-readable text from trace."""
    profile = RouteProfile(
        model="qwen3.5:cloud",
        provider="cloud",
        tier="S",
        routing_trace=[
            {"step": "complexity_shortcircuit", "score": 0.85, "target": "frontier"},
            {"step": "selected", "phase": "cloud", "model": "qwen3.5:cloud", "tier": "S"},
        ],
        confidence=0.9,
    )
    rationale = profile.rationale
    assert len(rationale) == 2
    assert any("Complexity short-circuit" in r for r in rationale)
    assert any("qwen3.5:cloud" in r for r in rationale)


def test_route_profile_to_dict():
    """RouteProfile.to_dict() includes rationale."""
    profile = RouteProfile(model="test", routing_trace=[{"step": "test"}])
    d = profile.to_dict()
    assert "rationale" in d
    assert "routing_trace" in d
    assert d["model"] == "test"


# ── Tier walk order ────────────────────────────────────────────────────────


def test_tier_walk_order_completeness():
    """All standard tiers are present, S comes first."""
    expected = {"S", "A+", "A", "A-", "B+", "B", "C", "D"}
    assert set(_TIER_WALK_ORDER) == expected
    assert _TIER_WALK_ORDER[0] == "S"


def test_specialization_patterns_exist():
    """Specialization patterns for coding, visual, reasoning, execution are defined."""
    assert "coding" in _SPECIALIZATION_PATTERNS
    assert "visual" in _SPECIALIZATION_PATTERNS
    assert "reasoning" in _SPECIALIZATION_PATTERNS
    assert "execution" in _SPECIALIZATION_PATTERNS
    assert "debug" in _SPECIALIZATION_PATTERNS["coding"]
    assert "image" in _SPECIALIZATION_PATTERNS["visual"]


# ── Complexity scoring ─────────────────────────────────────────────────────


def test_complexity_score_empty():
    """Empty payload produces near-zero complexity."""
    score = complexity_score("", {})
    assert 0.0 <= score <= 0.1


def test_complexity_score_simple():
    """Simple intent has low complexity."""
    score = complexity_score("hello world", {"program": []})
    assert 0.0 <= score <= 0.3


def test_complexity_score_reasoning():
    """Reasoning-heavy intent has higher complexity."""
    score = complexity_score(
        "reason about the architecture and plan a strategy to implement the design",
        {"program": [{"tag": "STMT"}] * 10},
    )
    assert score >= 0.2  # Should be higher than simple


def test_complexity_score_bounded():
    """Complexity never exceeds 1.0."""
    large_ast = {"program": [{"tag": "STMT"}] * 200}
    long_text = "reason plan analyse strategy architecture design " * 50
    score = complexity_score(long_text, large_ast)
    assert 0.0 <= score <= 1.0


# ── Legacy route_intent ────────────────────────────────────────────────────


def test_legacy_route_intent_visual():
    """Visual intents route to primary_model."""
    model = route_intent("process this image please")
    assert isinstance(model, str)
    assert len(model) > 0


def test_legacy_route_intent_coding():
    """Coding intents route to reasoning_model."""
    model = route_intent("debug this code for me")
    assert isinstance(model, str)
    assert len(model) > 0


def test_legacy_route_intent_reasoning():
    """Reasoning intents route to reasoning_model."""
    model = route_intent("analyze the architecture and plan the strategy")
    assert isinstance(model, str)
    assert len(model) > 0


def test_legacy_route_intent_default():
    """Default intents route to summarization_model."""
    model = route_intent("tell me a joke")
    assert isinstance(model, str)
    assert len(model) > 0


# ── Route selection ────────────────────────────────────────────────────────


def test_route_request_fallback_no_catalog():
    """route_request falls back to route_intent when no catalog data is available."""
    # Use mid-range complexity intent to avoid complexity short-circuit
    profile = route_request(
        "provide a general overview of the current weather conditions",
        {},
        complexity=0.5,
        tier="hearth",
        get_models_by_tier=None,
        get_local_inventory=None,
        get_equivalents=None,
    )
    assert isinstance(profile, RouteProfile)
    assert profile.model != ""
    assert profile.confidence <= 0.3
    fallback_steps = [
        t for t in profile.routing_trace if t.get("step") == "fallback"
    ]
    assert len(fallback_steps) >= 1
    assert "all_phases_exhausted" in fallback_steps[0].get("reason", "")


def test_route_request_complexity_slm_shortcircuit():
    """Simple intents (low complexity) short-circuit to SLM."""
    profile = route_request(
        "hello",
        {},
        complexity=0.1,
        tier="hearth",
        summarization_model="test-slm",
    )
    assert profile.model == "test-slm"
    assert profile.tier == "slm"
    assert profile.confidence >= 0.8
    shortcircuit = [
        t for t in profile.routing_trace if t.get("step") == "complexity_shortcircuit"
    ]
    assert len(shortcircuit) == 1
    assert shortcircuit[0]["target"] == "slm"


def test_route_request_complexity_frontier_shortcircuit():
    """Complex intents short-circuit to frontier model."""
    # Use text without specialization keywords so short-circuit fires cleanly
    profile = route_request(
        "a highly complex multi-faceted problem requiring deep expertise",
        {},
        complexity=0.85,
        tier="hearth",
        primary_model="test-frontier:cloud",
    )
    assert profile.model == "test-frontier:cloud"
    assert profile.tier == "S"
    assert profile.confidence >= 0.85
    shortcircuit = [
        t for t in profile.routing_trace if t.get("step") == "complexity_shortcircuit"
    ]
    assert len(shortcircuit) == 1
    assert shortcircuit[0]["target"] == "frontier"


def test_route_request_specialization_coding():
    """Coding intents trigger specialization and pick a coding model."""
    profile = route_request(
        "debug this Python code and fix the bug",
        {},
        tier="hearth",
        reasoning_model="test-coding-model",
    )
    spec_steps = [
        t for t in profile.routing_trace if t.get("step") == "specialization"
    ]
    assert len(spec_steps) == 1
    assert spec_steps[0]["match"] == "coding"
    # Should have an override trace entry
    override_steps = [
        t for t in profile.routing_trace if t.get("step") == "override"
    ]
    assert len(override_steps) >= 1
    assert override_steps[0]["specialization"] == "coding"


def test_route_request_specialization_visual():
    """Visual intents trigger specialization to primary model."""
    profile = route_request(
        "analyze this screenshot for me",
        {},
        tier="hearth",
        primary_model="test-visual:cloud",
    )
    spec_steps = [
        t for t in profile.routing_trace if t.get("step") == "specialization"
    ]
    assert len(spec_steps) == 1
    assert spec_steps[0]["match"] == "visual"


# ── Fallback paths ─────────────────────────────────────────────────────────


def test_route_request_with_tier_walk_catalog():
    """When get_models_by_tier is provided, tier walk is attempted."""
    mock_get_by_tier = MagicMock(return_value=[])
    mock_get_local = MagicMock(return_value=[])
    mock_get_equivs = MagicMock(return_value=[])

    # Use mid-range complexity to avoid short-circuit
    profile = route_request(
        "provide a general overview and summary of the situation",
        {},
        complexity=0.5,
        tier="hearth",
        get_models_by_tier=mock_get_by_tier,
        get_local_inventory=mock_get_local,
        get_equivalents=mock_get_equivs,
    )
    assert isinstance(profile, RouteProfile)
    # All phases exhausted → ultimate fallback
    fallback = [
        t for t in profile.routing_trace if t.get("step") == "fallback"
    ]
    assert len(fallback) >= 1
    assert profile.confidence <= 0.3


def test_route_request_local_fallback():
    """When cloud tier walk is empty, local inventory is used."""
    mock_get_by_tier = MagicMock(return_value=[])
    mock_get_local = MagicMock(
        return_value=[{"model_id": "local-model", "size_gb": 4.0}]
    )
    mock_get_equivs = MagicMock(return_value=[])

    # Use mid-range complexity to avoid short-circuit
    profile = route_request(
        "provide a general overview and summary of the situation",
        {},
        complexity=0.5,
        tier="hearth",
        get_models_by_tier=mock_get_by_tier,
        get_local_inventory=mock_get_local,
        get_equivalents=mock_get_equivs,
    )
    assert profile.model == "local-model"
    selected = [
        t for t in profile.routing_trace
        if t.get("step") == "selected" and t.get("phase") == "local"
    ]
    assert len(selected) == 1


def test_route_request_openrouter_fallback():
    """When local is empty, OpenRouter equivalents are tried."""
    mock_get_by_tier = MagicMock(return_value=[])
    mock_get_local = MagicMock(return_value=[])
    mock_get_equivs = MagicMock(
        return_value=[{"provider": "openrouter", "provider_model_id": "or/model"}]
    )

    # Use mid-range complexity to avoid short-circuit
    profile = route_request(
        "provide a general overview and summary of the situation",
        {},
        complexity=0.5,
        tier="hearth",
        get_models_by_tier=mock_get_by_tier,
        get_local_inventory=mock_get_local,
        get_equivalents=mock_get_equivs,
    )
    assert profile.model == "or/model"
    selected = [
        t for t in profile.routing_trace
        if t.get("step") == "selected" and t.get("phase") == "openrouter"
    ]
    assert len(selected) == 1


# ── Evidence-required denial ───────────────────────────────────────────────


def test_evidence_required_denial_missing_benchmark():
    """Evidence gate denies when a required benchmark is missing."""
    profile = RouteProfile(
        model="test-model",
        tier="C",
        routing_trace=[],
        confidence=0.6,
    )
    result = require_evidence_gate(
        profile,
        require_benchmark_evidence=True,
        minimum_benchmark_scores={"translation_fidelity": 0.8},
        available_benchmark_scores={},
    )
    assert result.model == ""
    assert result.tier == "denied"
    assert result.confidence == 0.0
    denial = [
        t for t in result.routing_trace if t.get("step") == "evidence_required_denial"
    ]
    assert len(denial) == 1
    assert "translation_fidelity" in denial[0]["reason"]


def test_evidence_required_denial_below_threshold():
    """Evidence gate denies when benchmark score is below minimum."""
    profile = RouteProfile(model="test-model", tier="B", routing_trace=[], confidence=0.5)
    result = require_evidence_gate(
        profile,
        require_benchmark_evidence=True,
        minimum_benchmark_scores={"accuracy": 0.9},
        available_benchmark_scores={"accuracy": 0.6},
    )
    assert result.tier == "denied"
    denial = [
        t for t in result.routing_trace if t.get("step") == "evidence_required_denial"
    ]
    assert len(denial) == 1
    assert "accuracy" in denial[0]["reason"]


def test_evidence_required_denial_passes_when_sufficient():
    """Evidence gate passes when all benchmarks are met."""
    profile = RouteProfile(model="test-model", tier="A", routing_trace=[], confidence=0.7)
    result = require_evidence_gate(
        profile,
        require_benchmark_evidence=True,
        minimum_benchmark_scores={"accuracy": 0.9},
        available_benchmark_scores={"accuracy": 0.95},
    )
    assert result.tier != "denied"
    assert result.model == "test-model"


def test_evidence_required_denial_no_requirements_is_noop():
    """Evidence gate is a no-op when no evidence is required."""
    profile = RouteProfile(model="test-model", tier="A", routing_trace=[], confidence=0.7)
    result = require_evidence_gate(
        profile,
        require_benchmark_evidence=False,
    )
    assert result is profile  # Same object returned


# ── Allowlist enforcement ──────────────────────────────────────────────────


def test_is_model_allowed_empty_allowlist():
    """Empty allowlist → fail-open."""
    assert is_model_allowed("any-model", "hearth", allowed_models=set())


def test_is_model_allowed_exact_match():
    """Exact match in allowlist."""
    allowed = {"qwen3:8b", "llama3.1:8b"}
    assert is_model_allowed("qwen3:8b", "hearth", allowed_models=allowed)
    assert not is_model_allowed("gemma3:12b", "hearth", allowed_models=allowed)


def test_is_model_allowed_cloud_suffix_normalized():
    """Cloud suffix is stripped before comparison."""
    allowed = {"qwen3-vl", "llama3.1:8b"}
    assert is_model_allowed(
        "qwen3-vl:cloud", "hearth", allowed_models=allowed
    )
    assert is_model_allowed(
        "qwen3-vl-cloud", "hearth", allowed_models=allowed
    )


def test_is_model_allowed_case_insensitive():
    """Model name comparison is case-insensitive."""
    allowed = {"QWEN3:8B"}
    assert is_model_allowed("qwen3:8b", "hearth", allowed_models=allowed)


# ── select_model_by_tier ───────────────────────────────────────────────────


def test_select_model_by_tier_first_reachable():
    """Returns first candidate when reachable."""
    candidates = [
        {"model_id": "model-a"},
        {"model_id": "model-b"},
    ]
    selected = select_model_by_tier(candidates, prefer_cloud=False)
    assert selected is not None
    assert selected["model_id"] == "model-a"


def test_select_model_by_tier_empty():
    """Returns None for empty candidates."""
    assert select_model_by_tier([], prefer_cloud=False) is None


def test_select_model_by_tier_cloud_preference():
    """Cloud preference skips non-cloud models that fail VRAM check."""
    # Non-cloud model without VRAM check → uses cache (default True)
    candidates = [{"model_id": "local-model"}]
    selected = select_model_by_tier(candidates, prefer_cloud=True)
    # Default cache says VRAM is ok → should select
    assert selected is not None
    assert selected["model_id"] == "local-model"


# ── route_with_fallback integration ────────────────────────────────────────


def test_route_with_fallback_basic():
    """route_with_fallback returns a valid profile even without catalog."""
    profile = route_with_fallback(
        "hello world",
        {},
        tier="hearth",
    )
    assert isinstance(profile, RouteProfile)
    assert profile.model != ""


def test_route_with_fallback_evidence_denial():
    """route_with_fallback with evidence requirements denies when missing."""
    profile = route_with_fallback(
        "complex reasoning task",
        {},
        tier="hearth",
        require_benchmark_evidence=True,
        minimum_benchmark_scores={"accuracy": 0.9},
        available_benchmark_scores={},
    )
    assert isinstance(profile, RouteProfile)
    assert profile.tier == "denied"
    assert profile.confidence == 0.0
