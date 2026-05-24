"""MCP tools for the OVERWATCH Sentinel — process-level watchdog for agent lifecycle monitoring.

Exposes scan, terminate, status-report, and health-metrics tools so governance
agents can query overwatch state without needing the standalone daemon.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.server_context import ServerContext
from hlf_mcp.tools.overwatch_health import sg_overwatch_health

# Module-level sentinel cache — built lazily from config on first tool call
_sentinel: Any = None
_sentinel_config_path: str | None = None


def _get_sentinel(config_path: str | None = None) -> Any:
    """Return a cached OverwatchSentinel, building it from config if needed.

    On first call the sentinel is built from *config_path* (defaulting to
    ``hlf_mcp/hlf/overwatch_config.json`` relative to the repo root).  A
    missing config file results in an empty sentinel.
    """
    global _sentinel, _sentinel_config_path

    from hlf_mcp.hlf.overwatch import OverwatchSentinel, build_overwatch_from_config

    effective_path = config_path or _sentinel_config_path
    if effective_path is None:
        # Default config next to overwatch.py
        repo_root = Path(__file__).resolve().parent.parent
        effective_path = str(repo_root / "hlf_mcp" / "hlf" / "overwatch_config.json")

    if _sentinel is not None and effective_path == _sentinel_config_path:
        return _sentinel

    try:
        _sentinel = build_overwatch_from_config(effective_path)
    except FileNotFoundError:
        _sentinel = OverwatchSentinel()
    _sentinel_config_path = effective_path
    return _sentinel


def register_overwatch_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    """Register OVERWATCH sentinel MCP tools.

    Returns a dict of ``{tool_name: callable}`` for inclusion in
    ``REGISTERED_TOOLS``.
    """

    @mcp.tool()
    def hlf_overwatch_scan(
        config_path: str = "",
    ) -> dict[str, Any]:
        """Scan all registered watchdog targets and return their statuses.

        Args:
            config_path: Optional path to an overwatch JSON config file.
                         Defaults to ``hlf_mcp/hlf/overwatch_config.json``.
        """
        sentinel = _get_sentinel(config_path or None)
        results = sentinel.scan()
        return {
            "status": "ok",
            "targets": {
                tid: status.value for tid, status in results.items()
            },
            "target_count": len(results),
        }

    @mcp.tool()
    def hlf_overwatch_terminate(
        target_id: str,
        reason: str = "",
        config_path: str = "",
    ) -> dict[str, Any]:
        """Terminate a watchdog target by ID.

        Args:
            target_id: The target to terminate.
            reason: Human-readable reason for termination.
            config_path: Optional path to an overwatch JSON config file.
        """
        sentinel = _get_sentinel(config_path or None)
        success = sentinel.terminate(target_id, reason=reason)
        return {
            "status": "ok" if success else "error",
            "target_id": target_id,
            "terminated": success,
        }

    @mcp.tool()
    def hlf_overwatch_status(
        config_path: str = "",
    ) -> dict[str, Any]:
        """Return a full Markdown status report of all watchdog targets.

        Args:
            config_path: Optional path to an overwatch JSON config file.
        """
        sentinel = _get_sentinel(config_path or None)
        report = sentinel.status_report()
        return {
            "status": "ok",
            "report": report,
        }

    # Register the standalone health-metrics tool
    mcp.tool(name="sg_overwatch_health")(sg_overwatch_health)

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
        "sg_overwatch_scan": hlf_overwatch_scan,
        "sg_overwatch_terminate": hlf_overwatch_terminate,
        "sg_overwatch_status": hlf_overwatch_status,
    })

    return {
        "hlf_overwatch_scan": hlf_overwatch_scan,
        "hlf_overwatch_terminate": hlf_overwatch_terminate,
        "hlf_overwatch_status": hlf_overwatch_status,
        "sg_overwatch_scan": hlf_overwatch_scan,
        "sg_overwatch_terminate": hlf_overwatch_terminate,
        "sg_overwatch_status": hlf_overwatch_status,
        "sg_overwatch_health": sg_overwatch_health,
    }
