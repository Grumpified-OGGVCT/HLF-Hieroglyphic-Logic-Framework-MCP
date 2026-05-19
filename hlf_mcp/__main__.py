"""python -m hlf_mcp entrypoint — starts the governed HLF MCP server.

Usage (from repo root):
    python -m hlf_mcp                          # stdio (default for MCP clients)
    HLF_TRANSPORT=sse python -m hlf_mcp        # SSE on default port
    HLF_TRANSPORT=streamable-http python -m hlf_mcp  # Streamable HTTP
    python -m hlf_mcp verify <file.hlf>        # Run formal verifier on HLF source

No Docker. No uv. Just Python 3.12+ and `pip install -e .` (or equivalent).
"""

import sys

if __name__ == "__main__":
    # Route CLI subcommands to operator_cli
    if len(sys.argv) > 1 and sys.argv[1] in (
        "verify", "do", "test-summary", "weekly-evidence-summary",
        "provenance-summary", "agent-protocol", "agent-quickstart",
        "agent-handoff-contract", "agent-current-authority",
        "witness-status", "governed-route", "ingress-status",
        "instinct-status", "formal-verifier", "entropy-anchor",
        "approval-review", "approval-bypass-review", "persona-review",
        "daemon-transparency", "daemon-transparency-report",
        "memory-govern", "resource",
    ):
        from hlf_mcp.operator_cli import main as operator_main
        raise SystemExit(operator_main(sys.argv[1:]))
    else:
        from hlf_mcp.server import main
        main()
