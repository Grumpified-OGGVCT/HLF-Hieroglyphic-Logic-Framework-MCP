"""MCP tools for the governed event log and governance surface."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.server_context import ServerContext


def register_governance_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_governance_event_log(
        limit: int = 20,
        event_type: str = "",
        severity: str = "",
        summaries_only: bool = False,
    ) -> dict[str, Any]:
        """Return the last N governance event log entries.

        Args:
            limit: Number of entries to return (1..250).
            event_type: Optional filter by event type (e.g. "witness_observation").
            severity: Optional filter by severity (e.g. "warning", "critical").
            summaries_only: If True, return operator-readable summaries instead of full dicts.
        """
        if ctx.governance_event_log is None:
            return {"status": "error", "error": "Governance event log is not initialized"}

        size = max(1, min(limit, 250))
        entries = ctx.governance_event_log.get_last_n(size)

        if event_type:
            entries = [e for e in entries if e.get("event_type") == event_type]
        if severity:
            entries = [e for e in entries if e.get("severity") == severity]

        if summaries_only:
            summaries = ctx.governance_event_log.get_last_n_summaries(size)
            # Re-filter summaries to match the same filtering logic
            if event_type or severity:
                filtered_summaries: list[str] = []
                for entry, summary in zip(entries, summaries):
                    if event_type and entry.get("event_type") != event_type:
                        continue
                    if severity and entry.get("severity") != severity:
                        continue
                    filtered_summaries.append(summary)
                summaries = filtered_summaries
            return {
                "status": "ok",
                "count": len(summaries),
                "summaries": summaries,
            }

        return {
            "status": "ok",
            "count": len(entries),
            "entries": entries,
        }

    @mcp.tool()
    def hlf_governance_event_log_verify(limit: int = 1000) -> dict[str, Any]:
        """Verify content-hash integrity of the most recent log entries."""
        if ctx.governance_event_log is None:
            return {"status": "error", "error": "Governance event log is not initialized"}
        return ctx.governance_event_log.verify_integrity(limit=limit)

    @mcp.tool()
    def hlf_governance_event_log_get(trace_ref: str = "", content_hash: str = "") -> dict[str, Any]:
        """Retrieve a single log entry by trace reference or content hash."""
        if ctx.governance_event_log is None:
            return {"status": "error", "error": "Governance event log is not initialized"}
        if trace_ref:
            entry = ctx.governance_event_log.get_by_trace_ref(trace_ref)
            if entry is None:
                return {"status": "error", "error": f"Entry with trace_ref={trace_ref!r} not found"}
            return {"status": "ok", "entry": entry}
        if content_hash:
            entry = ctx.governance_event_log.get_by_content_hash(content_hash)
            if entry is None:
                return {"status": "error", "error": f"Entry with content_hash={content_hash!r} not found"}
            return {"status": "ok", "entry": entry}
        return {"status": "error", "error": "Provide either trace_ref or content_hash"}

    return {
        "hlf_governance_event_log": hlf_governance_event_log,
        "hlf_governance_event_log_verify": hlf_governance_event_log_verify,
        "hlf_governance_event_log_get": hlf_governance_event_log_get,
    }
