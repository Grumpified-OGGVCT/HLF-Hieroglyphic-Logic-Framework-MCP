from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.memory_node import build_pointer_ref
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
        store_result = ctx.memory_store.store(
            content,
            topic=topic,
            confidence=confidence,
            provenance=provenance,
            tags=tags or [],
        )
        pointer_alias = f"{topic}-{store_result.get('id', 'entry')}"
        store_result["pointer"] = build_pointer_ref(pointer_alias, str(store_result.get("sha256", "")))
        store_result["pointer_entry"] = {
            "alias": pointer_alias,
            "content_hash": str(store_result.get("sha256", "")),
            "content": content,
            "trust_tier": "local",
            "fresh_until": None,
            "revoked": False,
            "tombstoned": False,
            "topic": topic,
        }
        store_result["audit"] = ctx.audit_chain.log(
            "hlf_memory_store",
            {
                "topic": topic,
                "fact_id": store_result.get("id"),
                "sha256": store_result.get("sha256"),
                "stored": store_result.get("stored"),
                "provenance": provenance,
                "confidence": confidence,
                "pointer": store_result["pointer"],
                "pointer_alias": pointer_alias,
                "tag_count": len(tags or []),
            },
            agent_role="memory_store",
            goal_id=topic,
        )
        store_result["governance_event"] = ctx.emit_governance_event(
            kind="memory_store",
            source="server_memory.hlf_memory_store",
            action="store_memory_fact",
            subject_id=str(store_result.get("id", "")),
            goal_id=topic,
            details={
                "topic": topic,
                "sha256": store_result.get("sha256"),
                "pointer": store_result["pointer"],
                "pointer_alias": pointer_alias,
                "confidence": confidence,
                "provenance": provenance,
            },
            agent_role="memory_store",
        )
        return store_result

    @mcp.tool()
    def hlf_memory_query(
        query: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
        entry_kind: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
    ) -> dict[str, Any]:
        """Query the Infinite RAG memory by semantic similarity."""
        return ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
            entry_kind=entry_kind,
            domain=domain,
            solution_kind=solution_kind,
        )

    @mcp.tool()
    def hlf_hks_capture(
        problem: str,
        validated_solution: str,
        domain: str,
        solution_kind: str = "repair-pattern",
        topic: str = "hlf_validated_exemplars",
        provenance: str = "hlf_hks_capture",
        confidence: float = 1.0,
        tags: list[str] | None = None,
        tests: list[dict[str, Any]] | None = None,
        supersedes: str | None = None,
        summary: str = "",
        source_type: str = "mcp_tool",
        source: str | None = None,
        workflow_run_url: str | None = None,
        branch: str | None = None,
        commit_sha: str | None = None,
        artifact_path: str | None = None,
    ) -> dict[str, Any]:
        """Capture a validated HKS exemplar for future governed recall."""
        result = ctx.capture_validated_solution(
            problem=problem,
            validated_solution=validated_solution,
            domain=domain,
            solution_kind=solution_kind,
            provenance=provenance,
            tests=tests,
            topic=topic,
            confidence=confidence,
            tags=tags,
            supersedes=supersedes,
            summary=summary,
            source_type=source_type,
            source=source,
            workflow_run_url=workflow_run_url,
            branch=branch,
            commit_sha=commit_sha,
            artifact_path=artifact_path,
        )
        result["audit"] = ctx.audit_chain.log(
            "hlf_hks_capture",
            {
                "topic": topic,
                "domain": domain,
                "solution_kind": solution_kind,
                "fact_id": result.get("id"),
                "sha256": result.get("sha256"),
                "stored": result.get("stored"),
                "confidence": confidence,
            },
            agent_role="hks_capture",
            goal_id=topic,
        )
        return result

    @mcp.tool()
    def hlf_hks_recall(
        query: str,
        top_k: int = 5,
        domain: str | None = None,
        solution_kind: str | None = None,
        topic: str = "hlf_validated_exemplars",
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Recall validated HKS exemplars filtered by domain and solution pattern."""
        return ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
            entry_kind="hks_exemplar",
            domain=domain,
            solution_kind=solution_kind,
        )

    @mcp.tool()
    def hlf_memory_stats() -> dict[str, Any]:
        """Return Infinite RAG memory store statistics."""
        return ctx.memory_store.stats()

    return {
        "hlf_memory_store": hlf_memory_store,
        "hlf_memory_query": hlf_memory_query,
        "hlf_hks_capture": hlf_hks_capture,
        "hlf_hks_recall": hlf_hks_recall,
        "hlf_memory_stats": hlf_memory_stats,
    }
