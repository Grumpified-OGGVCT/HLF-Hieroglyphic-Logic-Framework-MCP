"""
HLF MCP Server Authentication — Bearer token middleware for HTTP transports.

Enterprise hardening Commit 9: MCP Auth.

Auth is OPT-IN:
  - If HLF_API_TOKEN is NOT set, everything works as before (backward compat)
  - If HLF_API_TOKEN IS set, ALL HTTP requests must include Authorization: Bearer <token>
  - stdio transport is always exempt (local only, no network surface)

SECURITY NOTICE — Honest limitations:
  This is a SINGLE static bearer token. It gates access, not identity. Suitable for:
    • Single-tenant local deployments (one operator, one machine)
    • CI pipelines with a known agent
  NOT suitable for:
    • Multi-tenant deployments (no per-agent identity)
    • Production HTTP exposure (no token rotation, no expiry, no JWT)
  For multi-tenant or production: rotate HLF_API_TOKEN via your secret manager,
  or layer an external auth proxy (OAuth, mTLS) in front of the MCP server.

Usage:
    from hlf_mcp.server_auth import auth_middleware, HLF_API_TOKEN, verify_token

    # In server startup:
    if transport in ("sse", "http", "streamable-http"):
        auth_middleware(transport)
"""

from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)

HLF_API_TOKEN = os.environ.get("HLF_API_TOKEN", "")
_auth_required = bool(HLF_API_TOKEN)

if not _auth_required:
    _log.warning(
        "HLF_API_TOKEN not set — MCP server running without authentication. "
        "Set HLF_API_TOKEN to enable Bearer token auth for HTTP transports."
    )


def verify_token(token: str | None) -> bool:
    """Verify a bearer token against HLF_API_TOKEN.

    Args:
        token: The Authorization header value, or None.

    Returns:
        True if the token is valid or auth is not required.
    """
    if not _auth_required:
        return True
    if token is None:
        return False
    # Support both "Bearer xxx" and raw token
    if token.startswith("Bearer "):
        token = token[7:]
    return token == HLF_API_TOKEN


def _create_auth_middleware():
    """Create a Starlette middleware class that enforces Bearer token auth.

    Returns a middleware class (not an instance) suitable for
    app.add_middleware().
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class HLFAuthMiddleware(BaseHTTPMiddleware):
        """FastMCP-compatible middleware that validates Bearer tokens.

        Intercepts all HTTP requests on SSE and streamable-http transports.
        Requests missing a valid Authorization header receive a 401.
        """

        async def dispatch(self, request: Any, call_next: Any) -> Any:
            auth_header = request.headers.get("Authorization", "")
            
            # Always allow /health endpoint without auth
            if request.url.path == "/health":
                return await call_next(request)
            
            token = auth_header if auth_header else None
            if not verify_token(token):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "Unauthorized",
                        "detail": "Valid HLF_API_TOKEN required",
                    },
                )
            return await call_next(request)

    return HLFAuthMiddleware


def auth_middleware(transport: str) -> None:
    """Register auth middleware for HTTP transports.

    For HTTP transports (sse, http, streamable-http), this adds Bearer token
    validation middleware to the FastMCP server's underlying Starlette app.

    CRITICAL: FastMCP creates its Starlette app lazily during mcp.run().
    This function uses a background thread to wait for app creation and
    install middleware immediately after, before any client connections
    are accepted.

    For stdio transport, this is a no-op (local only, no network surface).

    Args:
        transport: The transport name ("sse", "http", "streamable-http", or "stdio").

    Raises:
        ImportError: If Starlette is not available (shouldn't happen — FastMCP
            requires Starlette for HTTP transports).
    """
    if transport not in ("sse", "http", "streamable-http"):
        _log.debug("stdio transport — auth middleware not applicable.")
        return

    if not _auth_required:
        _log.info(
            "HTTP transport (%s) active but HLF_API_TOKEN not set — "
            "auth middleware will NOT be installed.",
            transport,
        )
        return

    # Deferred import to access the mcp instance at call time
    from hlf_mcp.server import mcp

    def _install_middleware() -> None:
        """Try to install auth middleware after FastMCP creates its app."""
        import threading
        import time

        middleware_cls = _create_auth_middleware()

        def _try_install() -> None:
            # FastMCP creates the Starlette app during mcp.run().
            # We poll briefly after run() starts to attach middleware.
            for attempt in range(50):  # up to 5 seconds
                time.sleep(0.1)
                try:
                    if hasattr(mcp, "_mcp_server") and hasattr(mcp._mcp_server, "app"):
                        app = mcp._mcp_server.app
                        app.add_middleware(middleware_cls)
                        _log.info(
                            "Auth middleware installed for transport=%s. "
                            "All HTTP requests require Bearer token.",
                            transport,
                        )
                        return
                except Exception:
                    pass
            _log.warning(
                "Could not install auth middleware after 5s — "
                "server may be running without authentication for transport=%s. "
                "Check that FastMCP version creates _mcp_server.app during run().",
                transport,
            )

        thread = threading.Thread(target=_try_install, daemon=True)
        thread.start()

    # Patch mcp.run() so the background thread launches concurrently
    original_run = mcp.run

    def _patched_run(*args: Any, **kwargs: Any) -> Any:
        _install_middleware()
        return original_run(*args, **kwargs)

    mcp.run = _patched_run  # type: ignore[method-assign]
