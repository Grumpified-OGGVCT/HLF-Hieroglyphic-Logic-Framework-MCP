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

# ── Imports for distributed routing subpackage tests ──────────────────────
from hlf_mcp.hlf.routing.node_registry import (  # noqa: E402
    NodeRegistry,
    RegisteredNode,
)
from hlf_mcp.hlf.routing.capability_router import (  # noqa: E402
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer  # noqa: E402
from hlf_mcp.hlf.routing.failover import (  # noqa: E402
    FailoverManager,
    NodeFailureEvent,
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


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for hlf_mcp.hlf.routing PACKAGE (distributed routing fabric)
# ═══════════════════════════════════════════════════════════════════════════════


# ── NodeRegistry tests ───────────────────────────────────────────────────────


class TestNodeRegistry:
    """Tests for NodeRegistry — distributed node discovery and registration."""

    def test_node_registry_register(self):
        """Register a node and verify it exists."""
        registry = NodeRegistry()
        node = registry.register(
            "node-1", "10.0.0.1", 9090,
            capabilities={"inference": 8, "embedding": 5},
            metadata={"zone": "us-east"},
        )
        assert node.node_id == "node-1"
        assert node.host == "10.0.0.1"
        assert node.port == 9090
        assert node.capabilities == {"inference": 8, "embedding": 5}
        assert node.metadata == {"zone": "us-east"}
        assert node.health == "healthy"
        assert node.last_heartbeat > 0

        # Verify retrieval
        retrieved = registry.get_node("node-1")
        assert retrieved is not None
        assert retrieved.node_id == "node-1"
        assert retrieved.host == "10.0.0.1"

    def test_node_registry_unregister(self):
        """Register then unregister, verify gone."""
        registry = NodeRegistry()
        registry.register("node-2", "10.0.0.2", 9091)
        assert registry.get_node("node-2") is not None

        result = registry.unregister("node-2")
        assert result is True
        assert registry.get_node("node-2") is None

        # Unregistering again returns False
        result = registry.unregister("node-2")
        assert result is False

    def test_node_registry_list_by_capability(self):
        """Register nodes with different capabilities, filter by capability."""
        registry = NodeRegistry()
        registry.register("node-a", "10.0.0.1", 9090,
                          capabilities={"inference": 8})
        registry.register("node-b", "10.0.0.2", 9091,
                          capabilities={"embedding": 5})
        registry.register("node-c", "10.0.0.3", 9092,
                          capabilities={"inference": 6, "embedding": 3})

        inference_nodes = registry.list_by_capability("inference")
        assert len(inference_nodes) == 2
        ids = {n.node_id for n in inference_nodes}
        assert ids == {"node-a", "node-c"}

        embedding_nodes = registry.list_by_capability("embedding")
        assert len(embedding_nodes) == 2
        ids = {n.node_id for n in embedding_nodes}
        assert ids == {"node-b", "node-c"}

        # Unknown capability returns empty
        none_nodes = registry.list_by_capability("unknown")
        assert len(none_nodes) == 0

    def test_node_registry_heartbeat(self):
        """Heartbeat updates timestamp."""
        import time
        registry = NodeRegistry()
        node = registry.register("node-1", "10.0.0.1", 9090)
        original_ts = node.last_heartbeat

        # Small sleep to ensure time difference
        time.sleep(0.01)
        result = registry.heartbeat("node-1")
        assert result is True
        assert node.last_heartbeat > original_ts

        # Heartbeat on unknown node returns False
        result = registry.heartbeat("nonexistent")
        assert result is False

    def test_node_registry_mark_unhealthy(self):
        """mark_unhealthy sets health to unhealthy."""
        registry = NodeRegistry()
        registry.register("node-1", "10.0.0.1", 9090)
        registry.mark_unhealthy("node-1")

        node = registry.get_node("node-1")
        assert node is not None
        assert node.health == "unhealthy"

        # Should be excluded from healthy_nodes
        assert len(registry.healthy_nodes()) == 0
        assert len(registry.operational_nodes()) == 0

        # Unknown node returns False
        result = registry.mark_unhealthy("nonexistent")
        assert result is False

    def test_node_registry_thread_safety(self):
        """Concurrent registrations don't corrupt."""
        import threading
        registry = NodeRegistry()
        errors = []

        def register_node(node_id: str) -> None:
            try:
                registry.register(node_id, "10.0.0.1", 9090,
                                  capabilities={"test": 1})
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(50):
            t = threading.Thread(
                target=register_node,
                args=(f"node-{i}",),
                daemon=True,
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        nodes = registry.list_nodes()
        assert len(nodes) == 50
        # Verify all nodes have valid health
        for node in nodes:
            assert node.health == "healthy"
            assert node.host == "10.0.0.1"
            assert node.capabilities == {"test": 1}


# ── CapabilityRouter tests ───────────────────────────────────────────────────


class TestCapabilityRouter:
    """Tests for CapabilityRouter — capability-based routing to nodes."""

    def _setup_registry_with_nodes(self) -> NodeRegistry:
        """Helper to create a registry with diverse nodes."""
        registry = NodeRegistry()
        registry.register(
            "node-inference", "10.0.0.1", 9090,
            capabilities={"inference": 9, "embedding": 3},
        )
        registry.register(
            "node-embedding", "10.0.0.2", 9091,
            capabilities={"embedding": 8, "inference": 4},
        )
        registry.register(
            "node-general", "10.0.0.3", 9092,
            capabilities={"inference": 6, "embedding": 5, "vision": 7},
        )
        registry.register(
            "node-visual", "10.0.0.4", 9093,
            capabilities={"vision": 9},
        )
        # Unhealthy node — should be excluded by find_capable_nodes
        registry.register(
            "node-dead", "10.0.0.5", 9094,
            capabilities={"inference": 10},
        )
        registry.mark_unhealthy("node-dead")
        return registry

    def test_capability_router_find_capable_nodes(self):
        """Finds nodes with matching capability at sufficient proficiency."""
        registry = self._setup_registry_with_nodes()
        router = CapabilityRouter(registry)

        # All nodes with inference capability at default min_proficiency=1
        nodes = router.find_capable_nodes("inference")
        ids = {n.node_id for n in nodes}
        assert ids == {"node-inference", "node-embedding", "node-general"}
        # At proficiency 5+ (node-embedding has only 4)
        nodes = router.find_capable_nodes("inference", min_proficiency=5)
        ids = {n.node_id for n in nodes}
        assert ids == {"node-inference", "node-general"}

        # Unhealthy node is excluded
        assert "node-dead" not in {n.node_id for n in router.find_capable_nodes("inference")}

        # Unknown capability
        assert len(router.find_capable_nodes("unknown")) == 0

    def test_capability_router_match_request(self):
        """Matches a WorkRequest to the best node."""
        registry = self._setup_registry_with_nodes()
        router = CapabilityRouter(registry)

        request = WorkRequest(
            request_id="req-1",
            capability="inference",
            required_proficiency=5,
        )
        match = router.match_request(request)
        assert match.matched is True
        assert match.matched_node is not None
        # node-inference has proficiency 9, node-general has 6 — best is node-inference
        assert match.matched_node.node_id == "node-inference"
        assert match.confidence > 0.8
        assert "node-inference" in match.rationale

        # Request with high proficiency threshold
        request = WorkRequest(
            request_id="req-2",
            capability="inference",
            required_proficiency=9,
        )
        match = router.match_request(request)
        assert match.matched is True
        assert match.matched_node.node_id == "node-inference"

        # Request for capability nobody has
        request = WorkRequest(
            request_id="req-3",
            capability="unknown",
        )
        match = router.match_request(request)
        assert match.matched is False
        assert match.matched_node is None
        assert match.confidence == 0.0

    def test_capability_router_exclude_nodes(self):
        """Respects exclude_nodes in WorkRequest."""
        registry = self._setup_registry_with_nodes()
        router = CapabilityRouter(registry)

        request = WorkRequest(
            request_id="req-1",
            capability="inference",
            required_proficiency=1,
            exclude_nodes={"node-inference"},
        )
        match = router.match_request(request)
        assert match.matched is True
        # Should skip node-inference, next best is node-general (proficiency 6)
        assert match.matched_node.node_id == "node-general"

        # Exclude all capable nodes
        request = WorkRequest(
            request_id="req-2",
            capability="inference",
            exclude_nodes={"node-inference", "node-general", "node-embedding", "node-dead"},
        )
        match = router.match_request(request)
        assert match.matched is False
        assert match.matched_node is None

    def test_capability_router_require_healthy(self):
        """Filters out unhealthy nodes when require_healthy=True."""
        registry = self._setup_registry_with_nodes()
        router = CapabilityRouter(registry)

        # Mark node-inference as degraded
        registry.mark_degraded("node-inference")

        request = WorkRequest(
            request_id="req-1",
            capability="inference",
            required_proficiency=1,
        )
        # With require_healthy=True (default in route_with_constraints)
        matches = router.route_with_constraints(request, max_nodes=10, require_healthy=True)
        ids = {m.matched_node.node_id for m in matches if m.matched_node}
        assert "node-inference" not in ids  # degraded, excluded
        assert "node-general" in ids

        # With require_healthy=False, degraded nodes are included
        matches = router.route_with_constraints(request, max_nodes=10, require_healthy=False)
        ids = {m.matched_node.node_id for m in matches if m.matched_node}
        assert "node-inference" in ids  # degraded but included
        assert "node-general" in ids


# ── LoadBalancer tests ───────────────────────────────────────────────────────


class TestLoadBalancer:
    """Tests for LoadBalancer — work distribution strategies."""

    def _setup_balancer(self) -> LoadBalancer:
        """Helper to create a LoadBalancer with pre-registered nodes."""
        registry = NodeRegistry()
        registry.register(
            "node-1", "10.0.0.1", 9090,
            capabilities={"inference": 8},
        )
        registry.register(
            "node-2", "10.0.0.2", 9091,
            capabilities={"inference": 8},
        )
        registry.register(
            "node-3", "10.0.0.3", 9092,
            capabilities={"inference": 7},
        )
        router = CapabilityRouter(registry)
        return LoadBalancer(registry, router, strategy="round_robin")

    def test_load_balancer_round_robin(self):
        """Distributes across nodes in sequence."""
        lb = self._setup_balancer()

        request = WorkRequest(
            request_id="rr-req",
            capability="inference",
            required_proficiency=1,
        )

        # Round-robin should cycle through eligible nodes
        match1 = lb.distribute(request)
        match2 = lb.distribute(request)
        match3 = lb.distribute(request)
        match4 = lb.distribute(request)  # Should wrap back to first

        assert match1.matched_node.node_id == "node-1"
        assert match2.matched_node.node_id == "node-2"
        assert match3.matched_node.node_id == "node-3"
        assert match4.matched_node.node_id == "node-1"

    def test_load_balancer_least_loaded(self):
        """Picks least loaded node."""
        lb = self._setup_balancer()
        lb.set_strategy("least_loaded")

        # Manually set some load
        lb.increment_active("node-1")
        lb.increment_active("node-1")
        lb.increment_active("node-2")

        request = WorkRequest(
            request_id="ll-req",
            capability="inference",
        )
        match = lb.distribute(request)
        # node-3 has 0, node-2 has 1, node-1 has 2 → pick node-3
        assert match.matched_node.node_id == "node-3"
        assert lb.active_count("node-3") == 1

        # Clean up
        lb.decrement_active("node-1")
        lb.decrement_active("node-1")
        lb.decrement_active("node-2")
        lb.decrement_active("node-3")

    def test_load_balancer_set_strategy(self):
        """Switching strategies works."""
        lb = self._setup_balancer()
        assert lb.strategy == "round_robin"

        # Switch to least_loaded
        lb.set_strategy("least_loaded")
        assert lb.strategy == "least_loaded"

        # Switch back
        lb.set_strategy("round_robin")
        assert lb.strategy == "round_robin"

        # Unknown strategy raises error
        import pytest
        with pytest.raises(ValueError, match="Unknown strategy"):
            lb.set_strategy("random")


# ── Failover tests ───────────────────────────────────────────────────────────


class TestFailover:
    """Tests for FailoverManager — failure handling and recovery."""

    def _setup_failover(self) -> tuple[NodeRegistry, CapabilityRouter, LoadBalancer, FailoverManager]:
        """Helper to create a full failover setup."""
        registry = NodeRegistry()
        registry.register(
            "node-alpha", "10.0.0.1", 9090,
            capabilities={"inference": 9, "embedding": 5},
        )
        registry.register(
            "node-beta", "10.0.0.2", 9091,
            capabilities={"inference": 8, "embedding": 6},
        )
        registry.register(
            "node-gamma", "10.0.0.3", 9092,
            capabilities={"embedding": 7},
        )
        router = CapabilityRouter(registry)
        lb = LoadBalancer(registry, router, strategy="round_robin")
        failover = FailoverManager(registry, router, lb, max_retries=3)
        return registry, router, lb, failover

    def test_failover_handle_failure(self):
        """Node marked unhealthy, alternative found."""
        registry, router, lb, failover = self._setup_failover()

        # Simulate active tasks on node-alpha
        lb.increment_active("node-alpha")
        lb.increment_active("node-alpha")

        match = failover.handle_failure("node-alpha")

        # Node should be unhealthy
        node = registry.get_node("node-alpha")
        assert node.health == "unhealthy"

        # Active tasks cleared
        assert lb.active_count("node-alpha") == 0

        # Alternative found — handle_failure tries capabilities in descending
        # proficiency order. node-alpha's best cap is inference:9, but
        # required_proficiency=9 excludes node-beta (inference:8). Falls back
        # to embedding:5 → node-gamma (proficiency 7) beats node-beta (6).
        assert match.matched is True
        assert match.matched_node.node_id == "node-gamma"

        # Failure event recorded
        events = failover.failure_events
        assert len(events) == 1
        assert events[0].node_id == "node-alpha"

    def test_failover_recover_node(self):
        """Recover marks node healthy again."""
        registry, router, lb, failover = self._setup_failover()

        registry.mark_unhealthy("node-alpha")
        assert registry.get_node("node-alpha").health == "unhealthy"

        result = failover.recover_node("node-alpha")
        assert result is True
        assert registry.get_node("node-alpha").health == "healthy"

        # Recovering unknown node returns False
        result = failover.recover_node("nonexistent")
        assert result is False

    def test_failover_max_retries(self):
        """Respects max_retries in failover_route."""
        registry, router, lb, failover = self._setup_failover()
        # Set max_retries to 2 for this test
        failover._max_retries = 2

        # Create a request excluding all nodes except the failing one
        request = WorkRequest(
            request_id="fail-req",
            capability="inference",
            exclude_nodes={"node-beta", "node-alpha"},  # only node-alpha has inference
        )

        # Patch time.sleep to avoid delays
        with patch("time.sleep", return_value=None):
            match = failover.failover_route(request, "node-alpha")

        # All retries exhausted → no match
        assert match.matched is False
        assert match.matched_node is None
        assert "exhausted" in match.rationale.lower()

    def test_failover_node_failure_event(self):
        """NodeFailureEvent dataclass works properly."""
        event = NodeFailureEvent(
            node_id="node-x",
            reason="test failure",
            previous_health="healthy",
        )
        d = event.to_dict()
        assert d["node_id"] == "node-x"
        assert d["reason"] == "test failure"
        assert d["previous_health"] == "healthy"
        assert "timestamp" in d
