from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.server_context import ServerContext


def register_memory_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_memory_store(
        content: str,
        topic: str = "general",
        confidence: float = 1.0,
        provenance: str = "agent",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a fact in the Infinite RAG memory."""
        return ctx.memory_store.store(
            content,
            topic=topic,
            confidence=confidence,
            provenance=provenance,
            tags=tags or [],
        )

    @mcp.tool()
    def hlf_memory_query(
        query: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Query the Infinite RAG memory by semantic similarity."""
        return ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
        )

    @mcp.tool()
    def hlf_memory_stats() -> dict[str, Any]:
        """Return Infinite RAG memory store statistics."""
        return ctx.memory_store.stats()

    return {
        "hlf_memory_store": hlf_memory_store,
        "hlf_memory_query": hlf_memory_query,
        "hlf_memory_stats": hlf_memory_stats,
    }