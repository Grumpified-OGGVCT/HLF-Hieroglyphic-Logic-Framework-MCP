from __future__ import annotations

from typing import Any


def test_delegate_includes_memory_context_from_custom_retriever() -> None:
    from hlf_mcp.hlf.runtime import _dispatch_host

    def retriever(query: str, top_k: int = 3, topic: str | None = None) -> dict[str, Any]:
        assert query == "summarize release notes"
        assert top_k == 2
        assert topic == "delegation"
        return {
            "count": 1,
            "results": [{"content": "Use known-good summarization contract", "topic": topic}],
        }

    scope = {
        "_memory_retriever": retriever,
        "_memory_context_top_k": 2,
        "_memory_context_topic": "delegation",
    }
    side_effects: list[dict[str, Any]] = []

    result = _dispatch_host("delegate", ["scribe", "summarize release notes"], scope, side_effects)

    assert result["delegated"] is True
    assert result["memory_context"]["source"] == "custom"
    assert result["memory_context"]["count"] == 1
    assert (
        result["memory_context"]["results"][0]["content"] == "Use known-good summarization contract"
    )

    context_event = next(
        event for event in side_effects if event.get("type") == "memory_context_query"
    )
    assert context_event["source"] == "custom"
    assert context_event["query_chars"] == len("summarize release notes")
    assert "query" not in context_event


def test_route_uses_explicit_context_query_when_present() -> None:
    from hlf_mcp.hlf.runtime import _dispatch_host

    def retriever(query: str, top_k: int = 3, topic: str | None = None) -> dict[str, Any]:
        assert query == "python security audit"
        return {
            "count": 1,
            "results": [{"content": "Prefer security-review routing profile", "similarity": 0.91}],
        }

    scope = {"_memory_retriever": retriever, "_tier": "forge"}
    side_effects: list[dict[str, Any]] = []

    result = _dispatch_host("route", ["auto", "python security audit"], scope, side_effects)

    assert result["routed"] is True
    assert result["tier"] == "forge"
    assert (
        result["memory_context"]["results"][0]["content"]
        == "Prefer security-review routing profile"
    )


def test_delegate_memory_lookup_failure_fails_open() -> None:
    from hlf_mcp.hlf.runtime import _dispatch_host

    def retriever(query: str) -> dict[str, Any]:
        raise RuntimeError("memory unavailable")

    scope = {"_memory_retriever": retriever}
    side_effects: list[dict[str, Any]] = []

    result = _dispatch_host("delegate", ["scribe", "summarize release notes"], scope, side_effects)

    assert result["delegated"] is True
    assert "memory_context" not in result
    error_event = next(
        event for event in side_effects if event.get("type") == "memory_context_error"
    )
    assert error_event["query_chars"] == len("summarize release notes")


def test_delegate_can_use_default_rag_memory_when_enabled(monkeypatch) -> None:
    from hlf_mcp.hlf import runtime
    from hlf_mcp.rag import memory as memory_module

    class FakeMemory:
        def query(
            self, query_text: str, top_k: int = 5, topic: str | None = None
        ) -> dict[str, Any]:
            assert query_text == "repair translation"
            assert top_k == 3
            assert topic == "translator"
            return {
                "count": 1,
                "results": [{"content": "Known-good repair pattern", "topic": topic}],
            }

    monkeypatch.setattr(memory_module, "RAGMemory", FakeMemory)
    scope = {
        "_memory_context_enabled": True,
        "_memory_context_topic": "translator",
    }
    side_effects: list[dict[str, Any]] = []

    result = runtime._dispatch_host(
        "delegate", ["repairer", "repair translation"], scope, side_effects
    )

    assert result["delegated"] is True
    assert result["memory_context"]["source"] == "rag_memory"
    assert result["memory_context"]["results"][0]["content"] == "Known-good repair pattern"


def test_glyph_delegate_host_name_normalizes_to_runtime_delegate() -> None:
    from hlf_mcp.hlf.runtime import _dispatch_host

    side_effects: list[dict[str, Any]] = []

    result = _dispatch_host(
        "⌘ [DELEGATE]",
        ["scribe", "summarize release notes"],
        {},
        side_effects,
    )

    assert result["delegated"] is True
    delegation_event = next(event for event in side_effects if event.get("type") == "delegation")
    assert delegation_event["agent"] == "scribe"
    assert delegation_event["goal"] == "summarize release notes"
