#!/usr/bin/env python3
"""Check if hlf_governed_complete is actually in the MCP tooling."""

from hlf_mcp import server

# The real question: is it in the FastMCP instance's instructions/tools?
print("MCP server tools:")
print(f"  Type of mcp: {type(server.mcp).__name__}")
print(f"  mcp.instructions type: {type(server.mcp.instructions).__name__}")
print()

# Check what's in mcp.instructions as a string
instructions_str = server.mcp.instructions
tool_name = "hlf_governed_complete"

if tool_name in instructions_str:
    print(f"✓ '{tool_name}' FOUND in mcp.instructions")
    # Count occurrences
    count = instructions_str.count(tool_name)
    print(f"  Occurrences: {count}")
else:
    print(f"✗ '{tool_name}' NOT found in mcp.instructions")

# Count all hlf_ tools mentioned
import re
hlf_tools = re.findall(r"hlf_\w+", instructions_str)
unique_tools = set(hlf_tools)
print()
print(f"Total unique hlf_ tools in mcp.instructions: {len(unique_tools)}")
print(f"Sample tools: {sorted(list(unique_tools))[:5]}...")
