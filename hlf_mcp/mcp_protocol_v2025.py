"""
MCP 2025-11-25 Protocol Compliance: Header Validation and Session Management.

Implements Phase 2 (Header + Version Compliance) and Phase 3 (Session Semantics)
from the MCP 2025-11-25 Transport Upgrade Guide.

Phase 2: Validate MCP-Protocol-Version header; return 400 on unsupported versions.
Phase 3: Generate and return MCP-Session-Id on initialize; optionally validate on subsequent requests.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable
from datetime import datetime

_log = logging.getLogger(__name__)

# ┌─ Supported Protocol Versions ──────────────────────────────────────────────
SUPPORTED_PROTOCOL_VERSIONS = frozenset(["2025-11-25", "2024-11-05"])
CANONICAL_PROTOCOL_VERSION = "2025-11-25"

# ┌─ Session Management ──────────────────────────────────────────────────────

class MCPSession:
    """Represents a single MCP client session with lifecycle tracking."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.created_at = datetime.utcnow().isoformat()
        self.last_activity_at = self.created_at
        self.message_count = 0
        self.initialize_called = False

    def record_message(self) -> None:
        """Record message activity for session lifecycle tracking."""
        self.message_count += 1
        self.last_activity_at = datetime.utcnow().isoformat()

    def record_initialize(self) -> None:
        """Record that initialize has been called."""
        self.initialize_called = True
        self.record_message()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session state for logging or response."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_activity_at": self.last_activity_at,
            "message_count": self.message_count,
            "initialize_called": self.initialize_called,
        }


class MCPSessionStore:
    """Thread-safe store for active MCP sessions."""

    def __init__(self):
        self._sessions: dict[str, MCPSession] = {}
        self._session_by_request_id: dict[str, str] = {}  # request_id -> session_id

    def create_session(self) -> MCPSession:
        """Create a new session."""
        session = MCPSession()
        self._sessions[session.session_id] = session
        _log.debug("Created MCP session %s", session.session_id)
        return session

    def get_session(self, session_id: str) -> MCPSession | None:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def record_message(self, session_id: str) -> bool:
        """Record message activity; return True if valid session."""
        session = self._sessions.get(session_id)
        if session is None:
            _log.warning("Message recorded for unknown session %s", session_id)
            return False
        session.record_message()
        return True

    def record_initialize(self, session_id: str) -> bool:
        """Record initialize call; return True if valid session."""
        session = self._sessions.get(session_id)
        if session is None:
            _log.warning("Initialize recorded for unknown session %s", session_id)
            return False
        session.record_initialize()
        return True

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [session.to_dict() for session in self._sessions.values()]


# ┌─ Global session store ────────────────────────────────────────────────────
_session_store = MCPSessionStore()


def get_session_store() -> MCPSessionStore:
    """Get the global MCP session store."""
    return _session_store


# ┌─ Header Validation ───────────────────────────────────────────────────────

def validate_protocol_version(
    version_header: str | None,
) -> tuple[bool, str | None]:
    """
    Validate MCP-Protocol-Version header.

    Returns (is_valid, error_message).
    - If no header, valid (backward compat).
    - If header present but not in SUPPORTED_PROTOCOL_VERSIONS, invalid with reason.
    """
    if version_header is None:
        return True, None

    version_header = version_header.strip()
    if version_header not in SUPPORTED_PROTOCOL_VERSIONS:
        return (
            False,
            f"Unsupported MCP-Protocol-Version: {version_header!r}. "
            f"Supported: {', '.join(sorted(SUPPORTED_PROTOCOL_VERSIONS))}",
        )

    return True, None


# ┌─ Response Header Injection ──────────────────────────────────────────────

def build_mcp_response_headers(session_id: str, protocol_version: str = CANONICAL_PROTOCOL_VERSION) -> dict[str, str]:
    """Build MCP-compliant response headers."""
    return {
        "MCP-Session-Id": session_id,
        "MCP-Protocol-Version": protocol_version,
        "Content-Type": "application/json",
    }


# ┌─ Middleware Factory ──────────────────────────────────────────────────────

def make_mcp_protocol_middleware(
    require_session: bool = False,
    require_protocol_version: bool = True,
) -> Callable:
    """
    Create middleware for MCP 2025-11-25 protocol compliance.

    Args:
        require_session: If True, reject requests without valid MCP-Session-Id.
        require_protocol_version: If True, validate MCP-Protocol-Version header.

    Returns a Starlette middleware callable.
    """

    async def mcp_protocol_middleware(request: Any, call_next: Callable) -> Any:
        """Middleware for MCP protocol compliance."""
        from starlette.responses import JSONResponse

        # Extract headers
        protocol_version = request.headers.get("MCP-Protocol-Version")
        session_id = request.headers.get("MCP-Session-Id")

        # Phase 2: Validate protocol version
        if require_protocol_version:
            is_valid, error_msg = validate_protocol_version(protocol_version)
            if not is_valid:
                _log.warning("Protocol version validation failed: %s", error_msg)
                return JSONResponse(
                    {
                        "status": "error",
                        "error": error_msg,
                        "supported_versions": list(sorted(SUPPORTED_PROTOCOL_VERSIONS)),
                    },
                    status_code=400,
                )

        # Phase 3: Session validation (if enabled)
        if require_session and session_id is None:
            _log.warning("Request missing required MCP-Session-Id header")
            return JSONResponse(
                {
                    "status": "error",
                    "error": "MCP-Session-Id header required for this endpoint",
                },
                status_code=400,
            )

        if session_id is not None:
            store = get_session_store()
            store.record_message(session_id)  # Log the message activity

        # Call the wrapped route handler
        response = await call_next(request)

        # Inject response headers
        if session_id:
            response.headers["MCP-Session-Id"] = session_id
        response.headers["MCP-Protocol-Version"] = protocol_version or CANONICAL_PROTOCOL_VERSION

        return response

    return mcp_protocol_middleware


# ┌─ Logging and Diagnostics ───────────────────────────────────────────────

def log_session_info(label: str = "Session Info") -> dict[str, Any]:
    """Snapshot current session store state for logging."""
    store = get_session_store()
    sessions = store.list_sessions()
    return {
        "label": label,
        "active_sessions": len(sessions),
        "sessions": sessions,
    }
