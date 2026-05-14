# HLF Ecosystem Compatibility Matrix

> Claim lane: **bridge_contract**
> Created: 2026-03-25 — HLF_MCP Session
> References: [HLF_PILLAR_MAP](HLF_PILLAR_MAP.md), [HLF_MISSING_PILLARS](HLF_MISSING_PILLARS.md), [hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md](../hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md)

## Purpose

This matrix documents which languages and transports can consume HLF surfaces today (current truth), which are partially available through bridge code (bridge), and which are planned but not yet implemented (planned).

This is a **bridge_contract** document: it documents what is possible now and honestly plans what needs building. No SDK is claimed to be tested until it has deterministic fixture coverage.

## Compatibility Matrix

### Language SDKs and Transport Support

| Language | MCP Transport | SDK / Client | Status | Notes |
|---|---|---|---|---|
| **Python** | stdio (native) | FastMCP (`mcp[cli]>=1.27.0`) | **supported** | Implementation language. Full tool surface available via `hlf_mcp.server`. |
| **Python** | streamable-http | FastMCP / `httpx` | **supported** | `HLF_TRANSPORT=streamable-http` on `127.0.0.1` with session management headers. |
| **Python** | sse | FastMCP (legacy) | **legacy_compatibility** | Deprecated path; prefer streamable-http. |
| **JavaScript / Node.js** | streamable-http | `StreamableHttpMcpClient` (VS Code extension) | **bridge** | Working reference client in `extensions/hlf-vscode/src/mcpHttpClient.js`. Handles SSE parsing, session lifecycle, tool calls, resource reads. Not packaged as standalone SDK. |
| **TypeScript** | stdio | `@modelcontextprotocol/sdk` (donor reference) | **bridge** | Donor project `AgentKB_MCP` demonstrates `McpServer` + `StdioServerTransport` pattern using `@modelcontextprotocol/sdk`. Reference only — not HLF-specific. |
| **TypeScript / Node.js** | stdio | None (HLF-specific) | **planned** | No HLF TypeScript SDK stub exists. A thin wrapper around MCP stdio transport with typed tool schemas is the recommended starting point. |
| **Java** | streamable-http | None | **planned** | No Java SDK stub, client, or example exists. MCP Java SDK (`io.modelcontextprotocol`) can consume HLF via HTTP transport once available. |
| **Go** | streamable-http | None | **planned** | No Go SDK stub, client, or example exists. MCP Go SDK (`github.com/modelcontextprotocol/go-sdk`) can consume HLF via HTTP transport once available. |
| **Rust** | streamable-http | None | **planned** | No Rust SDK stub, client, or example exists. MCP Rust SDK (`crates.io:mcp`) can consume HLF via HTTP transport once available. |

### HLF Surface Availability Per Language

What HLF capabilities each language can consume through MCP:

| Surface | Python | JS/TS (bridge) | Java/Go/Rust (planned) |
|---|---|---|---|
| **Compile** (`hlf_compile`, `hlf_validate`, `hlf_format`) | ✅ Full | ✅ Via MCP tools | ✅ Via MCP tools (once MCP client exists) |
| **Lint** (`hlf_lint`) | ✅ Full | ✅ Via MCP tools | ✅ Via MCP tools |
| **Execute** (`hlf_run`, `hlf_code_execute`) | ✅ Full | ✅ Via MCP tools (governance gates apply) | ✅ Via MCP tools (governance gates apply) |
| **Capsule** (`hlf_capsule_run`, `hlf_capsule_validate`) | ✅ Full | ✅ Via MCP tools | ✅ Via MCP tools |
| **Translate** (`hlf_translate_to_hlf`, `hlf_translate_to_english`) | ✅ Full | ✅ Via MCP tools | ✅ Via MCP tools |
| **Benchmark** (`hlf_benchmark`, `hlf_benchmark_suite`) | ✅ Full | ✅ Via MCP tools | ✅ Via MCP tools |
| **Memory** (`hlf_memory_store`, `hlf_memory_query`) | ✅ Full | ⚠️ Via MCP tools (protected — needs governance proof) | ⚠️ Via MCP tools (protected) |
| **Governance** (`hlf_governance_proof_verify`) | ✅ Full | ⚠️ Via MCP tools (protected) | ⚠️ Via MCP tools (protected) |
| **Tool registry** (`hlf_tool_list`) | ✅ Full | ⚠️ Via MCP tools (protected) | ⚠️ Via MCP tools (protected) |
| **Inline HLF in source** | ✅ Native Python | ⚠️ Must call MCP compile → execute round-trip | ⚠️ Must call MCP compile → execute round-trip |
| **Native VM embedding** | ✅ `hlf_mcp.hlf.runtime` | ❌ No native runtime | ❌ No native runtime |

### MCP Server Transports

| Transport | HLF_TRANSPORT Value | Status | Suitable For |
|---|---|---|---|
| **stdio** | `stdio` | **supported** | Local agent integration (Claude Desktop, Copilot, etc.) |
| **Streamable HTTP** | `streamable-http` | **supported** | Remote clients, multi-language SDK consumption |
| **SSE (legacy)** | `sse` | **legacy_compatibility** | Backward compatibility only |

## Current Truth

- **The HLF MCP server** (`python -m hlf_mcp.server`) exposes all HLF surfaces as MCP tools.
- **Any MCP-compatible client** in any language can call these tools over `stdio` or `streamable-http`.
- **The VS Code extension** (`extensions/hlf-vscode/`) contains a working `StreamableHttpMcpClient` in JavaScript — it handles MCP protocol initialization, session management, SSE parsing, tool calls, and resource reads.
- **The AgentKB_MCP donor** (`donor/AgentKB_MCP/`) demonstrates a TypeScript MCP server using `@modelcontextprotocol/sdk` — it is a reference pattern, not HLF-specific.

## Bridge Gaps

What exists and works but is not packaged as an SDK:

1. **JS StreamableHttpMcpClient** — works, but is embedded in the VS Code extension. Would need extraction into a standalone `@grumprolled/hlf-mcp-client` npm package.
2. **No typed tool schemas** in non-Python languages — every client must discover tools via `tools/list` at runtime rather than importing typed definitions.
3. **No governance proof helpers** in non-Python — clients calling protected tools must build target-bound contracts manually.
4. **No native VM** outside Python — all non-Python execution goes through MCP round-trips to the Python server.

## Planned SDK Surfaces

In priority order:

| Priority | Language | Deliverable |
|---|---|---|
| 1 | **TypeScript/Node.js** | `@grumprolled/hlf-mcp-client` — typed MCP client with compile/format/lint/validate helpers + governance proof builders |
| 2 | **Java** | `com.grumprolled:hlf-mcp-client` — HTTP MCP client with tool schema bindings |
| 3 | **Go** | `github.com/grumprolled/hlf-mcp-go` — MCP HTTP client |
| 4 | **Rust** | `grumprolled-hlf-mcp` crate — MCP HTTP client |

Each SDK should:
- Wrap MCP transport (stdio and/or streamable-http)
- Provide typed tool call signatures matching the Python server's registered tools
- Handle session lifecycle (initialize → notifications/initialized → session-id propagation)
- Document governance proof requirements for protected tools
- Carry claim-lane metadata matching this repository's classification

## Host-Function Ecosystem (Vision)

Per [hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md](../hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md), the north-star vision includes HLF host functions for:

- **LOLLMS** (`lollms.generate`, `lollms.rag_query`)
- **MSTY Studio** (`msty.knowledge_query`, `msty.split_chat`)
- **AnythingLLM** (`anythingllm.workspace_query`)
- **Jan.ai** (`jan.generate`)
- Plus 10 user-repo integrations (Janus, OVERWATCH, API-Keeper, Jules_Choice, etc.)

This is **vision-true** — not implemented in the packaged MCP surface.

## Related Documents

- [HLF_MCP_TRANSPORT_GUIDE.md](HLF_MCP_TRANSPORT_GUIDE.md) — connecting non-Python MCP clients
- [HLF_ECOSYSTEM_COMPAT_WATCH.md](HLF_ECOSYSTEM_COMPAT_WATCH.md) — upstream MCP SDK breaking-change watch
- [HLF_PILLAR_MAP.md](HLF_PILLAR_MAP.md) — pillar disposition and batch planning
- [HLF_MISSING_PILLARS.md](HLF_MISSING_PILLARS.md) — damaged/source-only pillar inventory
