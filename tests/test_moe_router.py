"""
Tests for MoE Router (hlf_mcp/hlf/moe_router.py).

Covers:
  1. ExpertRouter creation with valid params
  2. route_to_expert produces valid decision
  3. route_to_expert confidence within [0, 1]
  4. route_to_expert selected_expert is in expert list
  5. ensemble_route produces decisions for each router
  6. build_fallback_graph produces valid graph
  7. build_fallback_graph detects circular dependencies
  8. validate_gating_decision catches invalid expert
  9. weighted routing distributes proportionally
  10. fallback order is respected when expert fails
  11. context_window affects routing behavior
  12. MoeRoutingDecision to_dict serializes correctly
  13. MoeModelGateway route_and_execute integration
  14. ExpertRouter rejects invalid strategy
  15. ExpertRouter rejects empty experts
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.moe_router import (  # noqa: E402
    ExpertRouter,
    MoeModelGateway,
    MoeRoutingDecision,
    build_fallback_graph,
    ensemble_route,
    route_to_expert,
    validate_gating_decision,
    validate_gating_decision_against_router,
)


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def coding_router() -> ExpertRouter:
    """A confidence-based router for coding tasks."""
    return ExpertRouter(
        name="coding",
        experts=["devstral-2:123b", "qwen3-coder:480b", "qwen3:8b", "codestral:22b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
    )


@pytest.fixture
def embedding_router() -> ExpertRouter:
    """A weighted router for embedding tasks."""
    return ExpertRouter(
        name="embedding",
        experts=["nomic-embed-text-v2-moe", "embeddinggemma", "qwen3-embedding:4b", "bge-m3"],
        gating_model="nomic-embed-text-v2-moe",
        routing_strategy="weighted",
        weights={
            "nomic-embed-text-v2-moe": 0.4,
            "embeddinggemma": 0.3,
            "qwen3-embedding:4b": 0.2,
            "bge-m3": 0.1,
        },
    )


@pytest.fixture
def fallback_router() -> ExpertRouter:
    """A fallback-based router with explicit fallback order."""
    return ExpertRouter(
        name="general",
        experts=["qwen3.5:cloud", "glm-4.6:cloud", "kimi-k2.5:cloud", "gemma-3:12b"],
        gating_model="qwen3.5:cloud",
        routing_strategy="fallback",
        fallback_order=["qwen3.5:cloud", "glm-4.6:cloud", "kimi-k2.5:cloud", "gemma-3:12b"],
    )


@pytest.fixture
def round_robin_router() -> ExpertRouter:
    """A round-robin router."""
    return ExpertRouter(
        name="load-balance",
        experts=["qwen3:8b", "llama3.2:3b", "phi4:14b"],
        gating_model="qwen3:8b",
        routing_strategy="round_robin",
    )


# ── Test 1: ExpertRouter creation with valid params ─────────────────────────


def test_expert_router_creation_valid():
    """ExpertRouter is created successfully with valid parameters."""
    router = ExpertRouter(
        name="test",
        experts=["model-a", "model-b", "model-c"],
        gating_model="model-a",
        routing_strategy="confidence",
    )
    assert router.name == "test"
    assert len(router.experts) == 3
    assert router.gating_model == "model-a"
    assert router.routing_strategy == "confidence"
    assert router.context_window == 2048
    assert router.max_retries == 3


def test_expert_router_rejects_invalid_strategy():
    """ExpertRouter raises ValueError for invalid routing_strategy."""
    with pytest.raises(ValueError, match="Invalid routing_strategy"):
        ExpertRouter(
            name="bad",
            experts=["model-a"],
            gating_model="model-a",
            routing_strategy="nonexistent",
        )


def test_expert_router_rejects_empty_experts():
    """ExpertRouter raises ValueError when experts list is empty."""
    with pytest.raises(ValueError, match="must not be empty"):
        ExpertRouter(
            name="empty",
            experts=[],
            gating_model="model-a",
        )


def test_expert_router_rejects_empty_gating_model():
    """ExpertRouter raises ValueError when gating_model is empty."""
    with pytest.raises(ValueError, match="gating_model must not be empty"):
        ExpertRouter(
            name="no-gate",
            experts=["model-a"],
            gating_model="",
        )


def test_expert_router_normalizes_weights():
    """ExpertRouter normalizes weights to sum to 1.0."""
    router = ExpertRouter(
        name="weighted",
        experts=["a", "b", "c"],
        gating_model="a",
        routing_strategy="weighted",
        weights={"a": 2, "b": 1, "c": 1},
    )
    total = sum(router.weights.values())
    assert abs(total - 1.0) < 0.0001
    assert router.weights["a"] == 0.5
    assert router.weights["b"] == 0.25
    assert router.weights["c"] == 0.25


# ── Test 2-4: route_to_expert core behavior ─────────────────────────────────


def test_route_to_expert_produces_valid_decision(coding_router):
    """route_to_expert returns a MoeRoutingDecision with populated fields."""
    decision = route_to_expert(
        "Write a Python function to implement quicksort",
        coding_router,
    )
    assert isinstance(decision, MoeRoutingDecision)
    assert decision.decision_id.startswith("moe-coding-")
    assert len(decision.input_hash) == 16
    assert decision.selected_expert in coding_router.experts
    assert decision.routing_reason != ""
    assert decision.latency_ms >= 0


def test_route_to_expert_confidence_in_range(coding_router):
    """Confidence routing produces confidence in [0, 1]."""
    prompts = [
        "Write a Rust async TCP server",
        "Explain the theory of relativity",
        "Tell me a story about dragons",
        "",
    ]
    for prompt in prompts:
        decision = route_to_expert(prompt, coding_router)
        assert 0.0 <= decision.confidence <= 1.0, (
            f"Confidence {decision.confidence} out of range for prompt: {prompt!r}"
        )


def test_route_to_expert_selected_expert_in_expert_list(coding_router):
    """The selected expert is always from the router's expert list."""
    prompts = [
        "Write Python code for binary search",
        "Debug this SQL query",
        "Refactor this Java class to use streams",
        "Implement a neural network in PyTorch",
    ]
    for prompt in prompts:
        decision = route_to_expert(prompt, coding_router)
        assert decision.selected_expert in coding_router.experts, (
            f"'{decision.selected_expert}' not in {coding_router.experts}"
        )


# ── Test 5: ensemble_route ──────────────────────────────────────────────────


def test_ensemble_route_produces_decisions_for_each_router(
    coding_router, embedding_router, fallback_router
):
    """ensemble_route produces one decision per router."""
    routers = [coding_router, embedding_router, fallback_router]
    decisions = ensemble_route("Find documents about machine learning", routers)
    assert len(decisions) == len(routers)
    for decision, router in zip(decisions, routers):
        assert decision.selected_expert in router.experts
        assert decision.decision_id.startswith(f"moe-{router.name}-")


# ── Test 6: build_fallback_graph ────────────────────────────────────────────


def test_build_fallback_graph_produces_valid_graph():
    """build_fallback_graph produces a graph with all experts as keys."""
    routers = [
        ExpertRouter(
            name="r1",
            experts=["a", "b", "c"],
            gating_model="a",
            fallback_order=["a", "b", "c"],
        ),
        ExpertRouter(
            name="r2",
            experts=["c", "d", "e"],
            gating_model="c",
            fallback_order=["c", "d", "e"],
        ),
    ]
    graph = build_fallback_graph(routers)
    assert isinstance(graph, dict)
    assert "a" in graph
    assert "b" in graph
    assert "c" in graph
    assert "d" in graph
    assert "e" in graph
    # a → b and a → c
    assert "b" in graph["a"]
    assert "c" in graph["a"]


# ── Test 7: circular dependency detection ───────────────────────────────────


def test_build_fallback_graph_detects_circular_dependencies():
    """build_fallback_graph raises ValueError on circular fallback chains."""
    # Create routers that form a cycle: a → b → c → a
    routers = [
        ExpertRouter(
            name="cycle-1",
            experts=["a", "b"],
            gating_model="a",
            fallback_order=["a", "b"],
        ),
        ExpertRouter(
            name="cycle-2",
            experts=["b", "c"],
            gating_model="b",
            fallback_order=["b", "c"],
        ),
        ExpertRouter(
            name="cycle-3",
            experts=["c", "a"],
            gating_model="c",
            fallback_order=["c", "a"],
        ),
    ]
    with pytest.raises(ValueError, match="Circular fallback dependency"):
        build_fallback_graph(routers)


# ── Test 8: validate_gating_decision ────────────────────────────────────────


def test_validate_gating_decision_catches_invalid():
    """validate_gating_decision returns False for malformed decisions."""
    # Empty decision_id
    bad1 = MoeRoutingDecision(decision_id="", input_hash="abc", selected_expert="x")
    assert validate_gating_decision(bad1) is False

    # Empty input_hash
    bad2 = MoeRoutingDecision(decision_id="id1", input_hash="", selected_expert="x")
    assert validate_gating_decision(bad2) is False

    # Empty selected_expert
    bad3 = MoeRoutingDecision(decision_id="id1", input_hash="abc", selected_expert="")
    assert validate_gating_decision(bad3) is False

    # Confidence out of range
    bad4 = MoeRoutingDecision(
        decision_id="id1", input_hash="abc", selected_expert="x", confidence=1.5
    )
    assert validate_gating_decision(bad4) is False

    bad5 = MoeRoutingDecision(
        decision_id="id1", input_hash="abc", selected_expert="x", confidence=-0.1
    )
    assert validate_gating_decision(bad5) is False

    # Negative latency
    bad6 = MoeRoutingDecision(
        decision_id="id1", input_hash="abc", selected_expert="x", latency_ms=-5.0
    )
    assert validate_gating_decision(bad6) is False


def test_validate_gating_decision_accepts_valid():
    """validate_gating_decision returns True for well-formed decisions."""
    good = MoeRoutingDecision(
        decision_id="moe-test-abc12345",
        input_hash="abc12345def67890",
        selected_expert="qwen3:8b",
        confidence=0.85,
        alternatives=["devstral-2:123b"],
        routing_reason="Confidence routing",
        fallback_chain=["devstral-2:123b"],
        latency_ms=12.5,
    )
    assert validate_gating_decision(good) is True


def test_validate_against_router_catches_invalid_expert(coding_router):
    """validate_gating_decision_against_router catches expert not in router."""
    decision = MoeRoutingDecision(
        decision_id="moe-test-abc12345",
        input_hash="abc12345def67890",
        selected_expert="nonexistent-model",
        confidence=0.9,
    )
    assert validate_gating_decision_against_router(decision, coding_router) is False

    # Valid expert should pass
    valid_decision = MoeRoutingDecision(
        decision_id="moe-test-abc12345",
        input_hash="abc12345def67890",
        selected_expert=coding_router.experts[0],
        confidence=0.9,
    )
    assert validate_gating_decision_against_router(valid_decision, coding_router) is True


# ── Test 9: weighted routing distributes proportionally ─────────────────────


def test_weighted_routing_distributes_proportionally(embedding_router):
    """Weighted routing selects experts roughly proportional to weights over many calls."""
    counts: dict[str, int] = {}
    num_calls = 500

    for i in range(num_calls):
        # Use unique prompts so hash-based RNG produces varied selections
        prompt = f"embed document {i} about AI safety and vector retrieval"
        decision = route_to_expert(prompt, embedding_router)
        counts[decision.selected_expert] = counts.get(decision.selected_expert, 0) + 1

    # Check all experts were selected at least once
    for expert in embedding_router.experts:
        assert counts.get(expert, 0) > 0, f"Expert '{expert}' was never selected"

    # Check rough proportionality (within reasonable tolerance)
    total = sum(counts.values())
    for expert, expected_weight in embedding_router.weights.items():
        actual_ratio = counts.get(expert, 0) / total
        # Allow 15% tolerance for statistical variance
        assert abs(actual_ratio - expected_weight) < 0.15, (
            f"Expert '{expert}': expected ~{expected_weight:.2f}, got {actual_ratio:.2f}"
        )


# ── Test 10: fallback order is respected ────────────────────────────────────


def test_fallback_order_respected_when_expert_fails(fallback_router):
    """When an expert is marked as failed in context, fallback order is respected."""
    # Simulate primary expert failure
    context = {"failed_experts": ["qwen3.5:cloud"]}
    decision = route_to_expert("General chat question", fallback_router, context)

    # Should skip qwen3.5:cloud and pick glm-4.6:cloud
    assert decision.selected_expert == "glm-4.6:cloud"
    assert "qwen3.5:cloud" not in decision.fallback_chain
    assert decision.confidence == 0.3  # Lower confidence because primary failed


def test_fallback_order_returns_first_when_none_failed(fallback_router):
    """When no experts have failed, fallback selects the first in order."""
    decision = route_to_expert("General chat question", fallback_router, {})
    assert decision.selected_expert == fallback_router.fallback_order[0]
    assert decision.confidence == 0.5


# ── Test 11: context_window affects routing behavior ────────────────────────


def test_context_window_affects_routing_behavior():
    """Different context_window values produce valid decisions (truncation is implicit)."""
    short_router = ExpertRouter(
        name="short-ctx",
        experts=["qwen3:8b", "phi4:14b", "llama3.2:3b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
        context_window=64,
    )
    long_router = ExpertRouter(
        name="long-ctx",
        experts=["qwen3:8b", "phi4:14b", "llama3.2:3b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
        context_window=8192,
    )

    long_prompt = "Write Python code " + "with detailed comments " * 200

    short_decision = route_to_expert(long_prompt, short_router)
    long_decision = route_to_expert(long_prompt, long_router)

    # Both produce valid decisions
    assert short_decision.selected_expert in short_router.experts
    assert long_decision.selected_expert in long_router.experts
    # The actual routing may differ depending on truncated vs full prompt keywords
    # (but heuristic routing on truncated prompts will differ if keyword density differs)
    # We simply verify both are valid — context_window is passed through for
    # future gating-model integration


def test_context_window_rejects_invalid():
    """ExpertRouter rejects context_window < 1."""
    with pytest.raises(ValueError, match="context_window must be >= 1"):
        ExpertRouter(
            name="bad-ctx",
            experts=["a"],
            gating_model="a",
            context_window=0,
        )


# ── Test 12: MoeRoutingDecision to_dict serialization ───────────────────────


def test_moe_routing_decision_to_dict_serializes():
    """MoeRoutingDecision.to_dict produces a JSON-compatible dict."""
    decision = MoeRoutingDecision(
        decision_id="moe-test-abc12345",
        input_hash="abc12345def67890",
        selected_expert="qwen3:8b",
        confidence=0.92,
        alternatives=["devstral-2:123b", "codestral:22b"],
        routing_reason="Confidence routing: high coding score",
        fallback_chain=["devstral-2:123b", "codestral:22b"],
        latency_ms=3.7,
    )
    d = decision.to_dict()

    assert d["decision_id"] == "moe-test-abc12345"
    assert d["input_hash"] == "abc12345def67890"
    assert d["selected_expert"] == "qwen3:8b"
    assert d["confidence"] == 0.92
    assert d["alternatives"] == ["devstral-2:123b", "codestral:22b"]
    assert d["routing_reason"] == "Confidence routing: high coding score"
    assert d["fallback_chain"] == ["devstral-2:123b", "codestral:22b"]
    assert d["latency_ms"] == 3.7

    # Round-trip
    restored = MoeRoutingDecision.from_dict(d)
    assert restored.decision_id == decision.decision_id
    assert restored.selected_expert == decision.selected_expert
    assert restored.confidence == decision.confidence


# ── Test 13: MoeModelGateway integration ────────────────────────────────────


def test_moe_model_gateway_route_and_execute():
    """MoeModelGateway wraps a base gateway and produces routing + execution."""
    # Mock base gateway
    base_gateway = MagicMock()
    base_gateway.handle_chat_completion.return_value = {
        "choices": [{"message": {"content": "def foo(): pass"}}],
    }

    router = ExpertRouter(
        name="coding",
        experts=["devstral-2:123b", "qwen3:8b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
    )

    moe_gw = MoeModelGateway(base_gateway, router)
    result = moe_gw.route_and_execute("Write a Python function")

    assert "decision" in result
    assert "model" in result
    assert "response" in result
    assert result["model"] in router.experts
    assert result["decision"]["selected_expert"] == result["model"]
    assert len(moe_gw.decision_log) == 1

    # Base gateway was called with the selected model
    base_gateway.handle_chat_completion.assert_called_once()
    call_args = base_gateway.handle_chat_completion.call_args[0][0]
    assert call_args["model"] == result["model"]


def test_moe_model_gateway_fallback_on_failure():
    """MoeModelGateway tries fallback experts when primary fails."""
    base_gateway = MagicMock()
    # First two calls fail, third succeeds
    base_gateway.handle_chat_completion.side_effect = [
        RuntimeError("Primary failed"),
        RuntimeError("First fallback failed"),
        {"choices": [{"message": {"content": "ok"}}]},
    ]

    router = ExpertRouter(
        name="coding",
        experts=["devstral-2:123b", "qwen3-coder:480b", "qwen3:8b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
        max_retries=2,
    )

    moe_gw = MoeModelGateway(base_gateway, router)
    result = moe_gw.route_and_execute("Write code")

    assert result["response"] is not None
    assert base_gateway.handle_chat_completion.call_count == 3


def test_moe_model_gateway_exhausts_fallbacks():
    """MoeModelGateway raises RuntimeError when all experts fail."""
    base_gateway = MagicMock()
    base_gateway.handle_chat_completion.side_effect = RuntimeError("All failed")

    router = ExpertRouter(
        name="coding",
        experts=["devstral-2:123b", "qwen3:8b"],
        gating_model="qwen3:8b",
        routing_strategy="confidence",
        max_retries=1,
    )

    moe_gw = MoeModelGateway(base_gateway, router)
    with pytest.raises(RuntimeError, match="MoE routing exhausted"):
        moe_gw.route_and_execute("Write code")


# ── Test: round-robin cycles through experts ────────────────────────────────


def test_round_robin_cycles_through_experts(round_robin_router):
    """Round-robin routing cycles through experts sequentially."""
    experts = round_robin_router.experts
    seen: list[str] = []
    for i in range(len(experts) * 2):
        decision = route_to_expert(f"prompt {i}", round_robin_router)
        seen.append(decision.selected_expert)

    # After len(experts) calls, all experts should have been selected
    first_cycle = seen[:len(experts)]
    assert set(first_cycle) == set(experts), (
        f"First cycle should cover all experts, got: {first_cycle}"
    )

    # Second cycle should repeat the same order
    second_cycle = seen[len(experts):len(experts) * 2]
    assert first_cycle == second_cycle


# ── Test: build_fallback_graph with single router ───────────────────────────


def test_build_fallback_graph_single_router():
    """build_fallback_graph handles a single-router graph correctly."""
    router = ExpertRouter(
        name="solo",
        experts=["a", "b", "c"],
        gating_model="a",
        routing_strategy="fallback",
        fallback_order=["a", "b", "c"],
    )
    graph = build_fallback_graph([router])
    assert graph == {"a": ["b", "c"], "b": ["c"], "c": []}


# ── Test: build_fallback_graph with no explicit fallback_order ──────────────


def test_build_fallback_graph_defaults_to_experts_order():
    """build_fallback_graph uses router.experts when fallback_order is empty."""
    router = ExpertRouter(
        name="default-fb",
        experts=["x", "y", "z"],
        gating_model="x",
        routing_strategy="confidence",  # not "fallback", so fallback_order stays default
    )
    graph = build_fallback_graph([router])
    assert "x" in graph
    assert "y" in graph
    assert "z" in graph


# ── Test: MoeModelGateway property access ───────────────────────────────────


def test_moe_model_gateway_router_property():
    """MoeModelGateway exposes its router and decision_log."""
    router = ExpertRouter(
        name="test",
        experts=["a", "b"],
        gating_model="a",
    )
    gw = MoeModelGateway(MagicMock(), router)
    assert gw.router is router
    assert gw.decision_log == []
