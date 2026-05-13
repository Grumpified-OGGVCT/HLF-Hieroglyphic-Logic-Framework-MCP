"""python -m hlf_mcp entrypoint — starts the governed HLF MCP server.

Usage (from repo root):
    python -m hlf_mcp                          # stdio (default for MCP clients)
    HLF_TRANSPORT=sse python -m hlf_mcp        # SSE on default port
    HLF_TRANSPORT=streamable-http python -m hlf_mcp  # Streamable HTTP

No Docker. No uv. Just Python 3.12+ and `pip install -e .` (or equivalent).
"""

from hlf_mcp.server import main

if __name__ == "__main__":
    main()
