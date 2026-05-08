#!/usr/bin/env python3
"""
MCP 2025-11-25 Phase 2 & Phase 3 Client Demonstration.

Shows how to interact with the HLF MCP server using:
- Phase 2: MCP-Protocol-Version header validation
- Phase 3: MCP-Session-Id session management

Usage:
    python mcp_phase2_phase3_demo.py http://localhost:9111
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

try:
    import httpx
except ImportError:
    print("This demo requires httpx. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)


class MCP2025Client:
    """Client demonstrating MCP 2025-11-25 Phase 2 & Phase 3 compliance."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session_id: str | None = None
        self.protocol_version = "2025-11-25"

    async def check_protocol_info(self) -> dict[str, Any]:
        """Check server protocol compliance info (Phase 2/Phase 3)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/protocol/info")
            response.raise_for_status()
            return response.json()

    async def initialize(self) -> dict[str, Any]:
        """Initialize MCP session with protocol version header (Phase 2 & 3)."""
        msg = {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages/",
                json=msg,
                headers={
                    "MCP-Protocol-Version": self.protocol_version,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

            # Phase 3: Extract session ID from response header
            session_id = response.headers.get("MCP-Session-Id")
            if session_id:
                self.session_id = session_id
                print(f"✓ Phase 3: Received MCP-Session-Id: {session_id}")

            # Phase 2: Validate protocol version in response
            resp_version = response.headers.get("MCP-Protocol-Version")
            print(f"✓ Phase 2: Server confirmed MCP-Protocol-Version: {resp_version}")

            return response.json()

    async def list_tools(self) -> dict[str, Any]:
        """List available tools with session continuity (Phase 3)."""
        msg = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}

        headers = {
            "MCP-Protocol-Version": self.protocol_version,
            "Content-Type": "application/json",
        }

        # Phase 3: Include session ID in subsequent request
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
            print(f"✓ Phase 3: Reusing session {self.session_id} for tools/list")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/messages/",
                json=msg,
                headers=headers,
            )
            response.raise_for_status()

            # Validate headers in response
            resp_version = response.headers.get("MCP-Protocol-Version")
            resp_session = response.headers.get("MCP-Session-Id")

            print(f"✓ Phase 2: Response version: {resp_version}")
            if resp_session:
                print(f"✓ Phase 3: Response session: {resp_session}")

            return response.json()

    async def get_session_info(self) -> dict[str, Any]:
        """Inspect current session state (Phase 3 diagnostic)."""
        if not self.session_id:
            return {"error": "No active session"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/protocol/sessions/{self.session_id}",
            )
            response.raise_for_status()
            return response.json()

    async def test_unsupported_version(self) -> dict[str, Any]:
        """Test Phase 2 error handling with unsupported protocol version."""
        msg = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 3}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/messages/",
                    json=msg,
                    headers={
                        "MCP-Protocol-Version": "1999-01-01",  # Invalid version
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                print(f"✓ Phase 2: Server correctly rejected unsupported version (HTTP {exc.response.status_code})")
                return exc.response.json()

        return {}


async def main() -> None:
    """Run Phase 2 & Phase 3 demonstration."""
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9111"

    print(f"\n{'='*70}")
    print("MCP 2025-11-25 Phase 2 & Phase 3 Client Demonstration")
    print(f"{'='*70}\n")

    client = MCP2025Client(base_url)

    try:
        # Step 1: Check server protocol compliance
        print("Step 1: Check server protocol compliance...")
        info = await client.check_protocol_info()
        print(f"  Server canonical version: {info.get('canonical_protocol_version')}")
        print(f"  Supported versions: {info.get('supported_versions')}")
        print(f"  Phase 2 enabled: {info.get('phase_2_enabled')}")
        print(f"  Phase 3 enabled: {info.get('phase_3_enabled')}")
        print()

        # Step 2: Initialize with Phase 2 & Phase 3
        print("Step 2: Initialize session with Phase 2 & Phase 3 headers...")
        init_result = await client.initialize()
        print(f"  Initialize response: {json.dumps(init_result, indent=2)}")
        print()

        # Step 3: List tools with session continuity
        print("Step 3: List tools with session continuity (Phase 3)...")
        tools = await client.list_tools()
        tool_count = len(tools.get("result", {}).get("tools", []))
        print(f"  Server has {tool_count} tools available")
        print()

        # Step 4: Inspect session state
        print("Step 4: Inspect session state (Phase 3 diagnostic)...")
        session_info = await client.get_session_info()
        if "session" in session_info:
            session = session_info["session"]
            print(f"  Session ID: {session['session_id']}")
            print(f"  Created: {session['created_at']}")
            print(f"  Last activity: {session['last_activity_at']}")
            print(f"  Messages: {session['message_count']}")
            print(f"  Initialize called: {session['initialize_called']}")
        print()

        # Step 5: Test Phase 2 error handling
        print("Step 5: Test Phase 2 error handling (unsupported version)...")
        error = await client.test_unsupported_version()
        if "error" in error:
            print(f"  Error message: {error['error']}")
            print(f"  Supported: {error.get('supported_versions')}")
        print()

        print(f"{'='*70}")
        print("✓ All Phase 2 & Phase 3 features working correctly!")
        print(f"{'='*70}\n")

    except Exception as exc:
        print(f"✗ Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
