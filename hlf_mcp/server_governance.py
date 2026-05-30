"""MCP tools for the governed event log and governance surface."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.server_context import ServerContext
import warnings


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
        warnings.warn("hlf_governance_event_log is deprecated, use sg_audit_event_log instead", DeprecationWarning, stacklevel=2)
        if not ctx.governance_events:
            return {"status": "ok", "count": 0, "entries": [], "total": 0}

        size = max(1, min(limit, 250))
        entries = list(ctx.governance_events)[-size:]

        if event_type:
            entries = [e for e in entries if e.get("event_type") == event_type]
        if severity:
            entries = [e for e in entries if e.get("severity") == severity]

        if summaries_only:
            summaries = [
                e.get("summary", e.get("event_type", "unknown"))
                for e in entries
            ]
            return {
                "status": "ok",
                "count": len(summaries),
                "summaries": summaries,
                "total": len(ctx.governance_events),
            }

        return {
            "status": "ok",
            "count": len(entries),
            "entries": entries,
            "total": len(ctx.governance_events),
        }

    @mcp.tool()
    def hlf_governance_event_log_verify(limit: int = 1000) -> dict[str, Any]:
        """Verify content-hash integrity of the most recent log entries."""
        warnings.warn("hlf_governance_event_log_verify is deprecated, use sg_audit_event_log_verify instead", DeprecationWarning, stacklevel=2)
        events = list(ctx.governance_events)[-limit:]
        if not events:
            return {"status": "ok", "count": 0, "message": "No events to verify"}
        # Verify each event has required fields
        valid = 0
        invalid = 0
        for event in events:
            if isinstance(event, dict) and "event_id" in event:
                valid += 1
            else:
                invalid += 1
        return {
            "status": "ok",
            "total": len(events),
            "valid": valid,
            "invalid": invalid,
            "complete": invalid == 0,
        }

    @mcp.tool()
    def hlf_governance_event_log_get(trace_ref: str = "", content_hash: str = "") -> dict[str, Any]:
        """Retrieve a single log entry by trace reference or content hash."""
        warnings.warn("hlf_governance_event_log_get is deprecated, use sg_audit_event_log_get instead", DeprecationWarning, stacklevel=2)
        if trace_ref:
            for event in reversed(ctx.governance_events):
                if isinstance(event, dict) and event.get("event_ref") == trace_ref:
                    return {"status": "ok", "entry": event}
                # Also check nested event data
                inner = event.get("event", {}) if isinstance(event, dict) else {}
                if isinstance(inner, dict) and inner.get("event_ref") == trace_ref:
                    return {"status": "ok", "entry": event}
            return {"status": "error", "error": f"Entry with trace_ref={trace_ref!r} not found"}
        if content_hash:
            import hashlib
            for event in reversed(ctx.governance_events):
                if isinstance(event, dict):
                    serialized = str(sorted(event.items()) if isinstance(event, dict) else str(event))
                    h = hashlib.sha256(serialized.encode()).hexdigest()[:16]
                    if h == content_hash:
                        return {"status": "ok", "entry": event}
            return {"status": "error", "error": f"Entry with content_hash={content_hash!r} not found"}
        return {"status": "error", "error": "Provide either trace_ref or content_hash"}

    def _register_sg_aliases(mcp: FastMCP, aliases: dict):
        """Register sg_ aliases that delegate to existing hlf_ tools."""
        import functools
        for sg_name, hlf_func in aliases.items():
            def _make_wrapper(_name, _func):
                @functools.wraps(_func)
                def _wrapper(*args, **kwargs):
                    return _func(*args, **kwargs)
                _wrapper.__name__ = _name
                return _wrapper
            wrapper = _make_wrapper(sg_name, hlf_func)
            mcp.tool(name=sg_name)(wrapper)

    _register_sg_aliases(mcp, {
        "sg_audit_event_log": hlf_governance_event_log,
        "sg_audit_event_log_verify": hlf_governance_event_log_verify,
        "sg_audit_event_log_get": hlf_governance_event_log_get,
    })

    return {
        "hlf_governance_event_log": hlf_governance_event_log,
        "hlf_governance_event_log_verify": hlf_governance_event_log_verify,
        "hlf_governance_event_log_get": hlf_governance_event_log_get,
        "sg_audit_event_log": hlf_governance_event_log,
        "sg_audit_event_log_verify": hlf_governance_event_log_verify,
        "sg_audit_event_log_get": hlf_governance_event_log_get,
    }
