# HLF MCP Transport Guide — Non-Python Client Integration

> Claim lane: **bridge_contract**
> Created: 2026-03-25 — HLF_MCP Session

## Purpose

This guide documents how non-Python MCP clients connect to the HLF MCP server. It covers transport options, protocol versioning, session management, and provides a working TypeScript example.

## Quick Reference: Transport Endpoints

### stdio

The server speaks JSON-RPC 2.0 over stdin/stdout. Stdout must contain only MCP protocol messages; logs go to stderr.

```bash
python -m hlf_mcp.server
# or
HLF_TRANSPORT=stdio python -m hlf_mcp.server
```

MCP client configuration (e.g., Claude Desktop `.mcp.json`):

```json
{
  "mcpServers": {
    "hlf-mcp": {
      "type": "stdio",
      "command": ".\\run.bat",
      "args": ["stdio"],
      "env": { "HLF_TRANSPORT": "stdio" }
    }
  }
}
```

### Streamable HTTP

Single MCP endpoint managed by FastMCP. Supports POST and optional SSE streaming.

```bash
HLF_TRANSPORT=streamable-http HLF_HOST=127.0.0.1 HLF_PORT=8123 python -m hlf_mcp.server
```

Endpoint: `http://127.0.0.1:8123/mcp`

### SSE (Legacy)

Deprecated HTTP+SSE compatibility path. Prefer streamable-http.

```bash
HLF_TRANSPORT=sse HLF_HOST=127.0.0.1 HLF_PORT=8123 python -m hlf_mcp.server
```

## Protocol Version

Current spec target: **`2025-11-25`**

The server also supports `2024-11-05` clients. Negotiation occurs during the `initialize` handshake.

Dependency floor: `mcp[cli]>=1.27.0`

## Session Lifecycle

Every MCP client must follow this sequence:

```
1. POST initialize →    server returns mcp-session-id header
2. POST notifications/initialized (no response expected)
3. All subsequent requests include mcp-session-id header
```

### Required Headers (Streamable HTTP)

```
Accept: application/json, text/event-stream
Content-Type: application/json
MCP-Protocol-Version: 2025-11-25        # after negotiation
MCP-Session-Id: <session-uuid>           # after initialize
```

## Available MCP Tools

The HLF MCP server registers tools in these categories. Every tool is accessible to any MCP-compatible client.

### Bootstrap-Safe (No Governance Proof Required)

These tools can be called without a target-bound governance contract:

| Tool | Description |
|---|---|
| `hlf_agent_admission` | Create a provisional MCP-native agent admission contract |
| `hlf_authority_matrix` | Expose the current authority-matrix surface |
| `hlf_benchmark` | Measure HLF token compression vs natural language |
| `hlf_benchmark_matrix` | Run multilingual benchmark matrix |
| `hlf_benchmark_suite` | Run full HLF benchmark suite across all 6 domains |
| `hlf_compile` | Compile HLF source to JSON AST and bytecode |
| `hlf_do` | Translate natural-language intent into governed HLF and optionally execute |
| `hlf_export_meaning_proof` | Export self-contained end-to-end HLF meaning proof bundle |
| `hlf_format` | Format HLF source to canonical form |
| `hlf_get_profile` | Retrieve a previously negotiated embedding profile |
| `hlf_governance_proof_verify` | Verify a governance proof hash chain |
| `hlf_governed_swarm_mechanics` | Bootstrap target-bound swarm contract |
| `hlf_lint` | Lint HLF source and return diagnostics |
| `hlf_list_profiles` | List available qualification and embedding profiles |
| `hlf_meaning_proof_verify` | Verify an exported meaning proof bundle via SHA-256 linkage |
| `hlf_query_profile_capabilities` | Query governed qualification profiles |
| `hlf_real_workflow_benchmark` | Benchmark real HLF self-improvement workflows |
| `hlf_recommend_embedding_profile` | Negotiate hardware-aware embedding profile |
| `hlf_routing_context_benchmark` | Retrieval-backed multilingual routing-context benchmarking |
| `hlf_test_suite_summary` | Return latest persisted pytest suite summary |
| `hlf_translate_repair` | Build deterministic next-step repair request |
| `hlf_translate_resilient` | Translate with deterministic retries and fallbacks |
| `hlf_translate_to_english` | Convert HLF source to human-readable summary |
| `hlf_translate_to_hlf` | Convert natural language to HLF source |
| `hlf_translation_memory_benchmark` | Retrieval-backed multilingual translation memory benchmarking |
| `hlf_translation_memory_query` | Query known-good translation contract exemplars |
| `hlf_validate` | Quickly validate HLF syntax without full compilation |
| `hlf_weekly_evidence_summary` | Return governed weekly evidence history summary |

### Protected Tools (Governance Proof Required)

The following categories require a validated governance proof or contract:

- **Execution**: `hlf_run`, `hlf_code_execute`, `hlf_capsule_run`
- **Memory write**: `hlf_memory_store`, `hlf_memory_govern`
- **Knowledge ingest**: `hlf_knowledge_ingest`, `hlf_knowledge_ingest_directory`, `hlf_knowledge_ingest_url`
- **Capsule management**: `hlf_capsule_validate`, `hlf_capsule_review_queue`, `hlf_capsule_review_decide`
- **Swarm execution**: `hlf_swarm_run`, `hlf_swarm_verify`, `hlf_swarm_witness`
- **Tool introspection**: `hlf_tool_list`, `hlf_host_functions`
- **Model catalog**: `hlf_sync_model_catalog`, `hlf_get_model_catalog`
- **Witness operations**: `hlf_witness_record`, `hlf_witness_list`, `hlf_witness_status`
- **Instinct lifecycle**: `hlf_instinct_step`, `hlf_instinct_realign`

To call a protected tool, first obtain admission via `hlf_agent_admission`, then build the required governance proof.

## Example: TypeScript MCP Client Connecting to HLF

Below is a minimal TypeScript example using `@modelcontextprotocol/sdk` to connect to an HLF MCP server over streamable HTTP.

This example is **bridge_contract**: it demonstrates the pattern but is not a packaged, tested SDK.

```typescript
// minimal-hlf-client.ts
// Bridge-contract example — not a packaged SDK
// Requires: npm install @modelcontextprotocol/sdk

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const HLF_SERVER_URL = "http://127.0.0.1:8123/mcp";

interface HlfCompileResult {
  status: string;
  ast: Record<string, unknown>;
  bytecode_hex: string;
}

async function connectHlf(): Promise<Client> {
  const transport = new StreamableHTTPClientTransport(
    new URL(HLF_SERVER_URL)
  );

  const client = new Client(
    { name: "my-hlf-client", version: "0.1.0" },
    { capabilities: {} }
  );

  await client.connect(transport);
  console.log("Connected to HLF MCP server");
  return client;
}

async function compileHlf(client: Client, source: string): Promise<HlfCompileResult> {
  const result = await client.callTool({
    name: "hlf_compile",
    arguments: { source },
  });

  // MCP returns content as array of text/embedded resources
  const text = result.content
    .filter((c: { type: string }) => c.type === "text")
    .map((c: { text: string }) => c.text)
    .join("\n");

  return JSON.parse(text);
}

async function validateHlf(client: Client, source: string): Promise<boolean> {
  const result = await client.callTool({
    name: "hlf_validate",
    arguments: { source },
  });
  const text = result.content
    .filter((c: { type: string }) => c.type === "text")
    .map((c: { text: string }) => c.text)
    .join("\n");
  const parsed = JSON.parse(text);
  return parsed.valid === true;
}

// Usage
async function main() {
  const client = await connectHlf();

  const hlfSource = `MODULE example:\n  FUNCTION greet(name: string) -> string:\n    RETURN "Hello, " + name + "!"`;

  // Validate syntax
  const valid = await validateHlf(client, hlfSource);
  console.log("HLF valid:", valid);

  // Compile
  const compiled = await compileHlf(client, hlfSource);
  console.log("AST node count:", Object.keys(compiled.ast).length);

  await client.close();
}

main().catch(console.error);
```

## Calling Protected Tools (Bridge Notes)

Protected tools require a governance proof. The pattern:

```typescript
// 1. Get admission
const admission = await client.callTool({
  name: "hlf_agent_admission",
  arguments: {
    agent_label: "my-ts-client",
    agent_role: "builder",
    requested_workflow: "execution",
  },
});

// 2. Build proof from admission result
// (Governance proof construction helpers are PLANNED — not packaged)

// 3. Call protected tool with proof
const result = await client.callTool({
  name: "hlf_run",
  arguments: {
    source: hlfSource,
    // proof fields go here once SDK helpers exist
  },
});
```

This flow is **planned** for SDK packaging. Currently, governance-proof construction requires understanding the contract format documented in the `hlf://agent/tool_contract` resource.

## Security Requirements

1. Bind local HTTP transports to `127.0.0.1` unless fronted by a secure deployment layer.
2. Validate Origin/authentication at any remote edge before exposing Streamable HTTP beyond localhost.
3. Do not treat MCP tool descriptions as trusted permission grants — HLF tool gates still enforce contracts and proofs.

## Current Limitations (Honest Gaps)

- **No typed SDK for any non-Python language.** All client code must construct MCP JSON-RPC messages manually or use generic MCP SDKs.
- **No non-Python governance proof helpers.** Building target-bound contracts requires understanding the proof format.
- **No non-Python VM embedding.** All execution flows through MCP to the Python server.
- **The VS Code JS client** is the only working non-Python reference — it is embedded in the extension, not packaged as a standalone library.

## Related Documents

- [HLF_ECOSYSTEM_MATRIX.md](HLF_ECOSYSTEM_MATRIX.md) — full compatibility matrix
- [HLF_ECOSYSTEM_COMPAT_WATCH.md](HLF_ECOSYSTEM_COMPAT_WATCH.md) — upstream MCP SDK breaking-change watch
- [BUILD_GUIDE.md](BUILD_GUIDE.md) — build and automation guide
- [hlf_mcp/server_resources.py](../hlf_mcp/server_resources.py) `_build_agent_mcp_transport_contract_surface` — authoritative transport contract
