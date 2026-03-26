#!/usr/bin/env python3
"""Quick smoke test of hlf_governed_complete tool in live MCP."""

from hlf_mcp import server

tool_name = "hlf_governed_complete"
in_registered = tool_name in server.REGISTERED_TOOLS
in_instructions = tool_name in server.mcp.instructions
in_dir = tool_name in dir(server)

print(f"{tool_name}:")
print(f"  In REGISTERED_TOOLS: {in_registered}")
print(f"  In mcp.instructions: {in_instructions}")
print(f"  In dir(server): {in_dir}")

if in_dir:
    func = getattr(server, tool_name)
    print(f"  Function: {func}")
    print(f"  Callable: {callable(func)}")
    print()
    print("✓ Tool IS accessible via the live MCP server")
else:
    print("✗ Tool NOT in dir(server)")

print()
print(f"Summary:")
print(f"  Total REGISTERED_TOOLS: {len(server.REGISTERED_TOOLS)}")
print(f"  Total in dir(server) matching hlf_*: {sum(1 for n in dir(server) if n.startswith('hlf_') and callable(getattr(server, n)))}")
print(f"  mcp.instructions type: {type(server.mcp.instructions).__name__}")

