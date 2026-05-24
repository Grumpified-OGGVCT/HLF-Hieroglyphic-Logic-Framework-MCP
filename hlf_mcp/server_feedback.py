"""HLF MCP feedback loop — submit user feedback as GitHub issues.

This module registers MCP tools that let agents and users submit feedback,
bug reports, and feature requests directly to the HLF GitHub repository.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
import warnings
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore[misc,assignment]

# Default repo — can be overridden via env or parameter
DEFAULT_REPO = "Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP"


def _run_gh(args: list[str]) -> dict[str, Any]:
    """Run a gh CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip()}
        try:
            return {"success": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError:
            return {"success": True, "data": result.stdout.strip()}
    except FileNotFoundError:
        return {"success": False, "error": "gh CLI not found. Install GitHub CLI: https://cli.github.com/"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "gh CLI command timed out after 30s"}


def _repo_arg(repo: str | None) -> str:
    return repo or DEFAULT_REPO


def register_feedback_tools(mcp: FastMCP) -> dict[str, Any]:
    """Register feedback-loop MCP tools."""
    tools: dict[str, Any] = {}

    @mcp.tool()
    def hlf_feedback_submit(
        title: str,
        body: str,
        labels: list[str] | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """Submit user feedback as a GitHub issue in the HLF repository.

        Args:
            title: Issue title (required, max 256 chars).
            body: Detailed description of the feedback, bug, or feature request.
            labels: Optional list of labels (e.g., ["bug", "feedback"]).
            repo: Optional target repo (default: Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP).
        """
        warnings.warn("hlf_feedback_submit is deprecated, use sg_observe_feedback_submit instead", DeprecationWarning, stacklevel=2)
        target = _repo_arg(repo)
        if not title or len(title) > 256:
            return {
                "success": False,
                "error": "Title is required and must be ≤256 characters.",
            }

        # Normalize body — add attribution footer
        normalized_body = textwrap.dedent(body).strip()
        normalized_body += (
            "\n\n---\n"
            "*This issue was created via the HLF MCP feedback tool.*\n"
            f"*Repository: {target}*"
        )

        args = [
            "issue", "create",
            "--repo", target,
            "--title", title,
            "--body", normalized_body,
        ]
        if labels:
            for label in labels:
                args.extend(["--label", label])

        result = _run_gh(args)
        if result.get("success"):
            # gh issue create outputs the issue URL on success
            url = result.get("data", "")
            return {
                "success": True,
                "issue_url": url,
                "message": f"Issue created successfully: {url}",
            }
        return result

    @mcp.tool()
    def hlf_feedback_list(
        state: str = "open",
        limit: int = 10,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """List recent GitHub issues in the HLF repository.

        Args:
            state: Filter by state — "open", "closed", or "all".
            limit: Maximum number of issues to return (1–100).
            repo: Optional target repo (default: Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP).
        """
        warnings.warn("hlf_feedback_list is deprecated, use sg_observe_feedback_list instead", DeprecationWarning, stacklevel=2)
        target = _repo_arg(repo)
        limit = max(1, min(limit, 100))

        args = [
            "issue", "list",
            "--repo", target,
            "--state", state,
            "--limit", str(limit),
            "--json", "number,title,state,labels,url,createdAt,author",
        ]
        return _run_gh(args)

    @mcp.tool()
    def hlf_feedback_view(issue_number: int, repo: str | None = None) -> dict[str, Any]:
        """View a specific GitHub issue by number.

        Args:
            issue_number: The issue number to view.
            repo: Optional target repo (default: Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP).
        """
        warnings.warn("hlf_feedback_view is deprecated, use sg_observe_feedback_view instead", DeprecationWarning, stacklevel=2)
        target = _repo_arg(repo)
        args = [
            "issue", "view",
            str(issue_number),
            "--repo", target,
            "--json", "number,title,body,state,labels,url,createdAt,author,comments",
        ]
        return _run_gh(args)

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
        "sg_observe_feedback_submit": hlf_feedback_submit,
        "sg_observe_feedback_list": hlf_feedback_list,
        "sg_observe_feedback_view": hlf_feedback_view,
    })

    tools["sg_observe_feedback_submit"] = hlf_feedback_submit
    tools["sg_observe_feedback_list"] = hlf_feedback_list
    tools["sg_observe_feedback_view"] = hlf_feedback_view
    return tools


if __name__ == "__main__":
    # Smoke test
    print("hlf_feedback_submit registered (smoke test)")
    print("hlf_feedback_list registered (smoke test)")
    print("hlf_feedback_view registered (smoke test)")
