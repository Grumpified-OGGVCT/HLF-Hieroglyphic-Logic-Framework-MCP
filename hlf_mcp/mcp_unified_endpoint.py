"""
Phase 4: MCP Unified Endpoint (/mcp)

This module implements the unified `/mcp` endpoint that consolidates all MCP 2025-11-25
protocol operations into a single entry point with automatic session management.

Architecture:
- Single POST /mcp endpoint handles all protocol operations
- Automatic session creation on first request
- Transparent session reuse on subsequent requests
- Unified error handling and response format
- Backward compatible with Phase 2 & 3

Operations Supported:
- initialize: Start new session
- list_resources: List available resources
- read_resource: Get resource content
- call_tool: Execute a tool
- list_tools: List available tools
- ping: Health check
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import JSONResponse

from .mcp_protocol_v2025 import (
    CANONICAL_PROTOCOL_VERSION,
    build_mcp_response_headers,
    get_session_store,
    validate_protocol_version,
)

_log = logging.getLogger(__name__)


class MCPUnifiedEndpoint:
    """Unified /mcp endpoint handler for Phase 4 convergence."""

    def __init__(self):
        self.session_store = get_session_store()

    async def handle_request(self, request: Request) -> JSONResponse:
        """
        Handle unified MCP request.

        Protocol:
        1. Validate protocol version (Phase 2)
        2. Get or create session (Phase 3)
        3. Parse operation from request body
        4. Execute operation
        5. Return response with session headers
        """

        # Phase 2: Validate protocol version
        protocol_version = request.headers.get("MCP-Protocol-Version")
        is_valid, error = validate_protocol_version(protocol_version)
        if not is_valid:
            _log.warning("Invalid protocol version: %s", error)
            return JSONResponse(
                {"error": error},
                status_code=400,
                headers={"Content-Type": "application/json"},
            )

        # Phase 3: Get or create session
        session_id = request.headers.get("MCP-Session-Id")
        if session_id:
            # Reuse existing session
            session = self.session_store.get_session(session_id)
            if not session:
                return JSONResponse(
                    {"error": f"Session {session_id} not found"},
                    status_code=404,
                )
            _log.debug("Reusing session %s", session_id)
        else:
            # Create new session
            session = self.session_store.create_session()
            _log.debug("Created new session %s", session.session_id)

        # Parse request
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(
                {"error": "Invalid JSON in request body"},
                status_code=400,
            )

        # Extract operation
        operation = body.get("operation", "").lower()
        params = body.get("params", {})

        # Record that initialize was called (if applicable)
        if operation == "initialize":
            self.session_store.record_initialize(session.session_id)

        # Record message activity
        self.session_store.record_message(session.session_id)

        # Execute operation
        result = await self._execute_operation(operation, params)

        # Build response with Phase 3 headers
        response_headers = build_mcp_response_headers(
            session_id=session.session_id,
            protocol_version=protocol_version or CANONICAL_PROTOCOL_VERSION,
        )

        return JSONResponse(
            result,
            headers=response_headers,
        )

    async def _execute_operation(self, operation: str, params: dict) -> dict:
        """Execute the requested operation."""

        # Map operations to handlers
        handlers = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "list_resources": self._handle_list_resources,
            "read_resource": self._handle_read_resource,
            "list_tools": self._handle_list_tools,
            "call_tool": self._handle_call_tool,
        }

        handler = handlers.get(operation)
        if not handler:
            return {
                "error": f"Unknown operation: {operation}",
                "supported_operations": list(handlers.keys()),
            }

        try:
            result = await handler(params)
            return result
        except Exception as e:
            _log.exception("Error executing operation %s: %s", operation, e)
            return {
                "error": f"Operation failed: {str(e)}",
                "operation": operation,
            }

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize operation."""
        return {
            "status": "initialized",
            "protocol_version": CANONICAL_PROTOCOL_VERSION,
            "supported_operations": [
                "initialize",
                "ping",
                "list_resources",
                "read_resource",
                "list_tools",
                "call_tool",
            ],
        }

    async def _handle_ping(self, params: dict) -> dict:
        """Handle ping operation."""
        return {
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _handle_list_resources(self, params: dict) -> dict:
        """Handle list_resources operation."""
        return {
            "resources": [
                {
                    "uri": "hlf://status",
                    "name": "HLF Status",
                    "description": "Latest HLF system status",
                }
            ],
        }

    async def _handle_read_resource(self, params: dict) -> dict:
        """Handle read_resource operation."""
        uri = params.get("uri")
        if not uri:
            return {"error": "uri parameter required"}

        return {
            "uri": uri,
            "content": f"Content of {uri}",
        }

    async def _handle_list_tools(self, params: dict) -> dict:
        """Handle list_tools operation."""
        return {
            "tools": [
                {
                    "name": "hlf_compile",
                    "description": "Compile HLF source to bytecode",
                    "inputSchema": {"type": "object"},
                }
            ],
        }

    async def _handle_call_tool(self, params: dict) -> dict:
        """Handle call_tool operation."""
        tool_name = params.get("name")
        if not tool_name:
            return {"error": "tool name required"}

        return {
            "tool": tool_name,
            "status": "not_implemented",
        }


# Global unified endpoint instance
_unified_endpoint = MCPUnifiedEndpoint()


def get_unified_endpoint() -> MCPUnifiedEndpoint:
    """Get the global unified endpoint handler."""
    return _unified_endpoint


async def unified_mcp_handler(request: Request) -> JSONResponse:
    """AWS-lambda style handler for /mcp endpoints."""
    endpoint = get_unified_endpoint()
    return await endpoint.handle_request(request)
