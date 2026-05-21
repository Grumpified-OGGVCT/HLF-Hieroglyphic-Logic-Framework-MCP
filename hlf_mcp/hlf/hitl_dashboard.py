"""
HLF Tool HITL Gate Dashboard — Lightweight web UI for tool approval.

Renders an HTML page showing all tools in pending_hitl state with
approve/reject buttons. Backed by ToolRegistry.get_pending_tools(),
approve_forged_tool(), and reject_forged_tool().

Served via FastMCP custom_route in server.py::

    from hlf_mcp.hlf.hitl_dashboard import dashboard_html, handle_action

    @mcp.custom_route("/hitl", methods=["GET"])
    async def hitl_dashboard(request):
        return dashboard_html(tool_registry)

    @mcp.custom_route("/hitl/action", methods=["POST"])
    async def hitl_action(request):
        return handle_action(tool_registry, request)
"""

from __future__ import annotations

import json
from typing import Any


# ── HTML template ───────────────────────────────────────────────────────────────

HITL_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HLF Tool HITL Gate</title>
    <style>
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --muted: #8b949e;
            --green: #3fb950;
            --red: #f85149;
            --amber: #d2991d;
            --blue: #58a6ff;
            --code-bg: #1c2128;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; }
        h1 { font-size: 1.5rem; color: var(--blue); margin-bottom: 0.25rem; }
        .subtitle { color: var(--muted); font-size: 0.875rem; margin-bottom: 2rem; }
        table { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
        th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: var(--code-bg); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; color: var(--muted); }
        tr:last-child td { border-bottom: none; }
        .token { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.75rem; color: var(--muted); background: var(--code-bg); padding: 0.15rem 0.4rem; border-radius: 3px; word-break: break-all; }
        .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 12px; font-size: 0.75rem; font-weight: 500; }
        .badge-pending { background: rgba(210, 153, 29, 0.15); color: var(--amber); }
        .badge-active { background: rgba(63, 185, 80, 0.15); color: var(--green); }
        .badge-disabled { background: rgba(248, 81, 73, 0.15); color: var(--red); }
        .btn { padding: 0.35rem 0.85rem; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 500; transition: all 0.15s; }
        .btn-approve { background: rgba(63, 185, 80, 0.12); color: var(--green); border-color: var(--green); }
        .btn-approve:hover { background: rgba(63, 185, 80, 0.25); }
        .btn-reject { background: rgba(248, 81, 73, 0.12); color: var(--red); border-color: var(--red); }
        .btn-reject:hover { background: rgba(248, 81, 73, 0.25); }
        .btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .toast { position: fixed; top: 1rem; right: 1rem; padding: 0.75rem 1.25rem; border-radius: 6px; font-weight: 500; font-size: 0.875rem; opacity: 0; transform: translateY(-10px); transition: all 0.3s; z-index: 999; }
        .toast.show { opacity: 1; transform: translateY(0); }
        .toast-success { background: var(--green); color: #000; }
        .toast-error { background: var(--red); color: #fff; }
        .empty-state { text-align: center; padding: 3rem 1rem; color: var(--muted); }
        .empty-state .icon { font-size: 2rem; margin-bottom: 0.5rem; }
        .approval-token { max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; vertical-align: middle; }
        .actions { display: flex; gap: 0.5rem; }
        .refresh-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .refresh-btn { color: var(--blue); background: none; border: none; cursor: pointer; font-size: 0.8rem; }
    </style>
</head>
<body>
    <h1>&#x1F513; HLF Tool HITL Gate</h1>
    <p class="subtitle">Review and approve forged tools awaiting human-in-the-loop approval.</p>

    <div class="refresh-bar">
        <span id="time">{refresh_time}</span>
        <button class="refresh-btn" onclick="location.reload()">&#x21BB; Refresh</button>
    </div>

    {table_html}

    <div id="toast" class="toast"></div>

    <script>
    async function approve(name, token) {{
        await sendAction(name, 'approve', token);
    }}
    async function reject(name, token) {{
        const reason = prompt('Rejection reason (optional):');
        if (reason === null) return; // cancelled
        await sendAction(name, 'reject', token, reason);
    }}
    async function sendAction(name, action, token, reason) {{
        const btn = document.getElementById(`btn-${{action}}-${{name}}`);
        if (btn) btn.disabled = true;

        try {{
            const body = {{ action, tool_name: name, approval_token: token }};
            if (reason) body.reason = reason;

            const resp = await fetch('/hitl/action', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }},
                body: JSON.stringify(body)
            }});
            const data = await resp.json();
            showToast(data.success ? `${{action === 'approve' ? 'Approved' : 'Rejected'}}: ${{name}}` : (data.error || 'Action failed'), data.success ? 'success' : 'error');
            if (data.success) setTimeout(() => location.reload(), 600);
        }} catch (e) {{
            showToast('Network error: ' + e.message, 'error');
            if (btn) btn.disabled = false;
        }}
    }}
    function showToast(msg, type) {{
        const el = document.getElementById('toast');
        el.textContent = msg;
        el.className = `toast toast-${{type}} show`;
        setTimeout(() => el.className = 'toast', 2500);
    }}
    </script>
</body>
</html>"""

NO_PENDING_HTML = """
    <div class="empty-state">
        <div class="icon">&#x2705;</div>
        <p>No tools awaiting HITL approval.</p>
        <p style="font-size:0.8rem;margin-top:0.5rem">All registered tools are either active or disabled.</p>
    </div>"""

TOOL_ROW_TEMPLATE = """<tr>
    <td><strong>{name}</strong>{version_html}</td>
    <td><span class="badge badge-pending">PENDING HITL</span></td>
    <td>{description}</td>
    <td><span class="approval-token token" title="{token}">{token_short}</span></td>
    <td>
        <div class="actions">
            <button id="btn-approve-{name}" class="btn btn-approve" onclick="approve('{name}', '{token}')">Approve</button>
            <button id="btn-reject-{name}" class="btn btn-reject" onclick="reject('{name}', '{token}')">Reject</button>
        </div>
    </td>
</tr>"""

TABLE_HEADER = """<table>
    <thead>
        <tr>
            <th>Tool</th>
            <th>Status</th>
            <th>Description</th>
            <th>Approval Token</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>"""

TABLE_FOOTER = """    </tbody>
</table>"""


# ── Dashboard functions ─────────────────────────────────────────────────────────


def dashboard_html(tool_registry: Any) -> Any:
    """Render the HITL dashboard HTML page.

    Args:
        tool_registry: ToolRegistry instance with the pending tools.

    Returns:
        starlette.responses.HTMLResponse
    """
    from datetime import datetime, timezone

    try:
        from starlette.responses import HTMLResponse
    except ImportError:
        from starlette.responses import PlainTextResponse
        return PlainTextResponse("starlette not available", status_code=500)

    pending = tool_registry.get_pending_tools()

    if not pending:
        table_html = NO_PENDING_HTML
    else:
        rows: list[str] = []
        for tool in pending:
            name = tool.get("name", "unknown")
            version = tool.get("version", "")
            version_html = f' <span style="color:var(--muted);font-size:0.75rem">v{version}</span>' if version else ""
            description = tool.get("description", tool.get("entrypoint", "—"))
            token = tool.get("approval_token", "N/A")
            token_short = token[:12] + "…" if len(token) > 12 else token
            rows.append(
                TOOL_ROW_TEMPLATE.format(
                    name=name,
                    version_html=version_html,
                    description=description,
                    token=token,
                    token_short=token_short,
                )
            )
        table_html = TABLE_HEADER + "\n".join(rows) + TABLE_FOOTER

    refresh_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return HTMLResponse(
        HITL_PAGE_TEMPLATE.format(
            refresh_time=refresh_time,
            table_html=table_html,
        )
    )


def handle_action(tool_registry: Any, request: Any) -> Any:
    """Handle approve/reject POST actions from the HITL dashboard.

    Expects JSON body: {"action": "approve"|"reject", "tool_name": "...",
    "approval_token": "...", "reason": "..."}

    Args:
        tool_registry: ToolRegistry instance.
        request: starlette Request object.

    Returns:
        starlette.responses.JSONResponse
    """
    import asyncio
    from starlette.responses import JSONResponse

    # Handle async request body
    try:
        if asyncio.iscoroutine(getattr(request, "body", None)):
            # Async FastMCP request — need to run in event loop
            pass  # body is already available via await
    except Exception:
        pass

    try:
        body = request.json() if hasattr(request, "json") else None
        if body is None:
            return JSONResponse({"success": False, "error": "No JSON body"}, status_code=400)
    except Exception as exc:
        return JSONResponse({"success": False, "error": f"Invalid JSON: {exc}"}, status_code=400)

    action = body.get("action", "")
    tool_name = body.get("tool_name", "")
    approval_token = body.get("approval_token", "")
    reason = body.get("reason", "")
    operator = body.get("operator", "hitl-dashboard")

    if not tool_name:
        return JSONResponse({"success": False, "error": "Missing tool_name"}, status_code=400)
    if not approval_token:
        return JSONResponse({"success": False, "error": "Missing approval_token"}, status_code=400)

    try:
        if action == "approve":
            tool_registry.approve_forged_tool(tool_name, operator, approval_token)
            return JSONResponse({"success": True, "tool_name": tool_name, "action": "approved"})
        elif action == "reject":
            tool_registry.reject_forged_tool(tool_name, operator, approval_token, reason)
            return JSONResponse({"success": True, "tool_name": tool_name, "action": "rejected"})
        else:
            return JSONResponse(
                {"success": False, "error": f"Unknown action: {action}"}, status_code=400
            )
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)
