"""
HLF Ecosystem Integration Bridge

Claim lane: bridge_contract

This package holds ecosystem bridge contracts, language-SDK adapters,
and transport compatibility documentation for non-Python HLF consumers.

Current truth:
- The HLF MCP server (Python/FastMCP) is the only executable surface.
- The VS Code extension (extensions/hlf-vscode/) contains a working
  JavaScript StreamableHttpMcpClient.
- The AgentKB_MCP donor (donor/AgentKB_MCP/) contains a TypeScript
  MCP server reference pattern.

No SDK stubs for Java, Go, or Rust exist yet. This package documents
the bridge path and will hold SDK adapters as they are built.
"""
