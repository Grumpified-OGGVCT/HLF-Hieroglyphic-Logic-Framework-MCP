"""Quick test: connect to running HLF MCP server and test HLF-as-agent capabilities."""
from __future__ import annotations

import asyncio
import json
import sys
import os

async def test_hlf_agent():
    # Connect to the running SSE MCP server
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from mcp.client.session import ClientSession

    try:
        async with sse_client("http://127.0.0.1:8765/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("=== CONNECTED TO HLF MCP SERVER ===\n")

                # List all tools
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"Total tools available: {len(tools)}\n")

                # Group tools by area
                tool_names = [t.name for t in tools]
                print("=== ALL TOOL NAMES ===")
                for name in sorted(tool_names):
                    print(f"  - {name}")

                # Now test the key HLF agent tools
                print("\n=== TEST 1: hlf_do (compile+run HLF code) ===")
                try:
                    result = await session.call_tool("hlf_do", {
                        "source": "CALL echo 'Hello from HLF agent!'"
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                print("\n=== TEST 2: hlf_agent_eval (agent-style evaluation) ===")
                try:
                    result = await session.call_tool("hlf_agent_eval", {
                        "source": "CALL summarize [\"The HLF MCP server is running and exposing tools to agents via the Model Context Protocol\"]"
                    })
                    text = result.content[0].text if result.content else "no content"
                    print(text[:500])
                except Exception as e:
                    print(f"Error: {e}")

                print("\n=== TEST 3: hlf_compile (check if HLF can compile) ===")
                try:
                    result = await session.call_tool("hlf_compile", {
                        "source": "LET x = 42\nCALL echo x"
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                print("\n=== TEST 4: hlf_run (execute compiled HLF) ===")
                try:
                    result = await session.call_tool("hlf_run", {
                        "source": "LET greeting = 'Hello Agent World'\nCALL echo greeting"
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                print("\n=== TEST 5: hlf_forge (agent orchestration) ===")
                try:
                    result = await session.call_tool("hlf_forge", {
                        "blueprint": json.dumps({
                            "task": "Test echo capability",
                            "steps": ["echo 'forge test'"]
                        })
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                # Try the native HLF agent execution (if available)
                print("\n=== TEST 6: hlf_execute (native agent execution) ===")
                try:
                    result = await session.call_tool("hlf_execute", {
                        "source": "CALL shell 'echo \"hello from shell\"'"
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:800])
                except Exception as e:
                    print(f"Error: {e}")

                # Check if there's a persona/agent contract
                print("\n=== TEST 7: hlf_new_persona (create agent persona) ===")
                try:
                    result = await session.call_tool("hlf_new_persona", {
                        "agent_kind": "test_agent",
                        "contract_json": json.dumps({
                            "description": "A test agent for HLF verification",
                            "allowed_effects": ["ECHO", "SHELL"],
                            "governed": True
                        })
                    })
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                # Check profiles
                print("\n=== TEST 8: hlf_profiles_list (list personas) ===")
                try:
                    result = await session.call_tool("hlf_profiles_list", {})
                    print(json.dumps(json.loads(result.content[0].text), indent=2)[:500])
                except Exception as e:
                    print(f"Error: {e}")

                print("\n=== SUMMARY ===")
                print("HLF MCP is operational as an agent framework:")
                print(f"  - {len(tools)} tools exposed")
                print(f"  - Server is running on http://127.0.0.1:8765")

            # session closed here
    except Exception as e:
        print(f"FATAL: Could not connect to HLF MCP server: {e}")
        print("Make sure the server is running with: HLF_TRANSPORT=sse HLF_PORT=8765 python -m hlf_mcp.server")

if __name__ == "__main__":
    asyncio.run(test_hlf_agent())
