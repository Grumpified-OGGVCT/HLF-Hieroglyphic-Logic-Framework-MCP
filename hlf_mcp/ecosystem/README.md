# HLF Ecosystem — Bridge Directory

> Claim lane: **bridge_contract**

## What This Directory Is

The `hlf_mcp/ecosystem/` directory is the packaged home for ecosystem integration bridge contracts and SDK adapters. It is built to grow as the ecosystem surface matures from `source_only_for_now` toward `bridge_contract` and eventually `current-true`.

## Current Contents

| Path | Description | Status |
|---|---|---|
| `__init__.py` | Python package marker with bridge documentation | **bridge_contract** |
| (future) `typescript/` | TypeScript SDK adapter and typed tool schemas | **planned** |
| (future) `java/` | Java SDK adapter | **planned** |
| (future) `go/` | Go SDK adapter | **planned** |
| (future) `rust/` | Rust SDK adapter | **planned** |

## What Exists Elsewhere (Bridge Reference)

These reference implementations exist outside this package but inform the ecosystem bridge:

| Reference | Location | Language | What It Shows |
|---|---|---|---|
| **VS Code MCP Client** | `extensions/hlf-vscode/src/mcpHttpClient.js` | JavaScript | Working `StreamableHttpMcpClient`: MCP initialize, session management, SSE parsing, `tools/call`, `resources/read` |
| **AgentKB_MCP Server** | `donor/AgentKB_MCP/src/index.ts` | TypeScript | MCP server built with `@modelcontextprotocol/sdk`: `McpServer`, `StdioServerTransport`, Zod schemas, tool registration pattern |
| **HLF MCP Transport Contract** | `hlf_mcp/server_resources.py` (line 4315) | Python | Canonical transport contract: spec target, transports, security requirements, upgrade gaps |

## Bridge Path

The ecosystem surface is currently at **22.5% readiness** (per `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`). The bridge path is:

1. ✅ Document the current truth — compatibility matrix, transport guide, compat watch (done in `docs/`)
2. ✅ Create this bridge directory as the packaging home
3. 🔲 Extract the VS Code `StreamableHttpMcpClient` into a standalone `@grumprolled/hlf-mcp-client` npm package
4. 🔲 Add typed TypeScript tool schemas matching the Python server's registered tools
5. 🔲 Add governance proof helper functions for TypeScript
6. 🔲 Repeat for Java, Go, Rust as demand warrants

## Honest Gap Statement

No non-Python SDK has been packaged, tested, or published. The VS Code extension's JavaScript client is the only working non-Python MCP reference, and it is embedded in the extension, not designed as a reusable library. Every other language has zero lines of HLF-specific client code.

This is not a failure — it is the correct priority ordering. The ecosystem surface was explicitly deferred behind governance, routing, verifier, orchestration, and memory bridge work (see `docs/HLF_PILLAR_MAP.md`, Batch 2).

## Related Documents

- [docs/HLF_ECOSYSTEM_MATRIX.md](../../docs/HLF_ECOSYSTEM_MATRIX.md) — full compatibility matrix
- [docs/HLF_MCP_TRANSPORT_GUIDE.md](../../docs/HLF_MCP_TRANSPORT_GUIDE.md) — transport guide for non-Python clients
- [docs/HLF_ECOSYSTEM_COMPAT_WATCH.md](../../docs/HLF_ECOSYSTEM_COMPAT_WATCH.md) — upstream MCP breaking-change watch
