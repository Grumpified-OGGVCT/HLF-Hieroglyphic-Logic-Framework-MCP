#!/usr/bin/env python3
"""Verify hlf_governed_complete is correctly registered as a function."""

from hlf_mcp import server

tool_name = "hlf_governed_complete"
in_registered = tool_name in server.REGISTERED_TOOLS
fn = server.REGISTERED_TOOLS.get(tool_name)

print(f"{tool_name}:")
print(f"  In REGISTERED_TOOLS: {in_registered}")
print(f"  Type: {type(fn).__name__}")
print(f"  Callable: {callable(fn)}")
if fn and hasattr(fn, "__doc__"):
    doc_preview = (fn.__doc__ or "")[:100]
    print(f"  Docstring: {doc_preview}...")

