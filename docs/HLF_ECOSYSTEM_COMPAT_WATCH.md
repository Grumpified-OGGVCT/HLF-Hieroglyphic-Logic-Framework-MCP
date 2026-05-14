# HLF Ecosystem Compatibility Watch

> Claim lane: **bridge_contract**
> Created: 2026-03-25 — HLF_MCP Session
> Purpose: Track upstream MCP SDK and protocol changes that could break HLF integration surfaces.

## What This Watches

HLF exposes its entire tool surface through the MCP protocol. When the upstream MCP specification, Python SDK, or language-specific MCP SDKs change their protocol contracts, HLF's ecosystem integration surface can break silently — because non-Python clients are not covered by the packaged pytest suite.

## Upstream Dependencies Under Watch

| Dependency | Current Floor | Breakage Risk | Notes |
|---|---|---|---|
| **MCP Python SDK** (`mcp[cli]`) | `>=1.27.0` | **High** | Core server dependency. API changes in `FastMCP`, `@mcp.tool()` decorator, or transport registration break the server. |
| **MCP Protocol Spec** | `2025-11-25` target | **High** | `initialize` handshake format, session ID header name, content types, SSE framing. Changes break ALL clients. |
| **MCP TypeScript SDK** (`@modelcontextprotocol/sdk`) | N/A (reference only) | **Medium** | Breaking changes to `McpServer`, `StdioServerTransport`, or `Client` APIs affect the donor example and future TS SDK. |
| **MCP Java SDK** (`io.modelcontextprotocol`) | N/A (planned) | **Low** | No Java integration exists yet; breakage risk is forward-looking. |
| **MCP Go SDK** (`github.com/modelcontextprotocol/go-sdk`) | N/A (planned) | **Low** | No Go integration exists yet. |
| **MCP Rust SDK** (`crates.io:mcp`) | N/A (planned) | **Low** | No Rust integration exists yet. |
| **FastMCP** (bundled in `mcp`) | Current bundled | **Medium** | `FastMCP.run(transport=...)` and `FastMCP.tool()` are the primary API surface; changes break tool registration and server startup. |

## Specific Breakage Scenarios

### 1. MCP Protocol Version Bump

**Trigger:** Upstream MCP releases `2026-03-26` spec with breaking changes to initialize handshake.

**Impact:**
- `hlf_mcp/mcp_protocol_v2025.py` session negotiation may reject or mishandle new version.
- Non-Python clients using newer SDKs may fail to negotiate with HLF's `2025-11-25` target.

**Mitigation:**
- `hlf_mcp/server_resources.py::_build_agent_mcp_transport_contract_surface()` explicitly documents the spec target.
- `hlf_mcp/mcp_protocol_v2025.py` already handles `2025-11-25` and `2024-11-05` — extend with new version support.
- Tests needed: protocol version negotiation across supported versions.

### 2. Session Header Rename

**Trigger:** MCP spec changes the session ID header from `mcp-session-id` to a different name.

**Impact:**
- `hlf_mcp/mcp_unified_endpoint.py` session management breaks.
- `hlf_mcp/mcp_protocol_v2025.py::MCPSession` uses the current header name.
- All non-Python clients (VS Code extension, future SDKs) break.

**Mitigation:**
- Centralize header name in a single constant.
- The VS Code extension's `StreamableHttpMcpClient` already hardcodes the header name — would need updating.

### 3. FastMCP API Change

**Trigger:** FastMCP changes `mcp.run(transport=...)` signature or `@mcp.tool()` decorator behavior.

**Impact:**
- `hlf_mcp/server.py` transport selection (`stdio`/`sse`/`streamable-http`) breaks.
- All tool registration functions break.
- `hlf_mcp/mcp_enforcement.py` wrapper injection breaks.

**Mitigation:**
- Keep `install_mcp_enforcement()` and tool registration patterns against FastMCP's public API only.
- Avoid private API usage where possible.

### 4. Content-Type / SSE Framing Changes

**Trigger:** MCP streamable-http spec changes content negotiation or SSE event format.

**Impact:**
- Non-Python SSE parsers (VS Code `parseEventStreamMessages()`) break.
- `Accept: application/json, text/event-stream` header negotiation may fail.

**Mitigation:**
- The VS Code extension has a working SSE parser — keep it in sync with spec.
- Document the expected framing in `HLF_MCP_TRANSPORT_GUIDE.md`.

### 5. JSON-RPC Method Renames

**Trigger:** Upstream MCP renames standard methods like `tools/call` → `tools/invoke`, `resources/read` → `resources/get`, etc.

**Impact:**
- All non-Python clients break at the protocol level.
- The HLF server's FastMCP dependency auto-handles this if kept up-to-date, but non-Python SDKs may lag.

**Mitigation:**
- Pin `mcp[cli]` version floor explicitly in `pyproject.toml`.
- Test against the declared spec target regularly.

## Verification Workflow

When a suspected upstream change occurs:

1. **Check spec target**: Compare `hlf_mcp/server_resources.py` contract version against upstream.
2. **Run packaged tests**: `python -m pytest tests/ -x --timeout=30 -q`
3. **Check transport bring-up**: Start server with each transport and verify health.
4. **Check VS Code extension**: `run.bat extension-test` — verifies the only non-Python client.
5. **Check donor reference**: `donor/AgentKB_MCP/src/index.ts` pattern still valid?
6. **Update this document**: Record the change, impact, and resolution.

## Current Known Gaps

- **No automated cross-SDK integration tests.** The VS Code extension tests exist but are manual (`run.bat extension-test`), not part of the CI-fast path.
- **No protocol version negotiation test.** FastMCP handles this internally; no explicit test covers version downgrade/upgrade.
- **No non-Python client fixtures.** The Python test suite cannot verify that a TypeScript client receives correct tool schemas.

## Planned Hardening

| Task | Priority | Description |
|---|---|---|
| Extract JS `StreamableHttpMcpClient` as npm package | **Medium** | Makes the reference client testable independently. |
| Add protocol-version smoke test | **Medium** | `hlf://agent/mcp_transport_contract` already documents the contract; add a test that reads it via MCP and verifies version. |
| Add SSE framing regression test | **Low** | Capture expected SSE event format; detect format changes. |
| Standalone non-Python client smoke | **Low** | Write a small script (Node/Python subprocess) that initializes MCP and calls `hlf_validate`. |

## Related Documents

- [HLF_ECOSYSTEM_MATRIX.md](HLF_ECOSYSTEM_MATRIX.md) — full compatibility matrix
- [HLF_MCP_TRANSPORT_GUIDE.md](HLF_MCP_TRANSPORT_GUIDE.md) — transport guide with examples
- [BUILD_GUIDE.md](BUILD_GUIDE.md) — current build and automation truth
