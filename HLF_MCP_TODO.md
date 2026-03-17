# HLF MCP Implementation TODO

Complete blueprint for the full MCP 2024-2025 integration with self-evolving grammar.

---

## Phase 0: Knowledge Substrate Refactor

**Priority: CRITICAL - Weekly knowledge work should not proceed without a cohesive surface**

### Naming and authority
- [ ] Adopt `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` as the active external research brief
- [ ] Normalize active planning and workflow language to HLF-native knowledge-substrate terminology
- [ ] Preserve `hlf_source/` as archive/reference context without letting archive terminology leak into active implementation surfaces

### Package and module boundaries
- [ ] Define the canonical ownership boundary for chunking, ingest, provenance, freshness, retrieval, and exemplar memory
- [ ] Decide which surfaces belong under `hlf_mcp/` versus `hlf/` before new weekly knowledge modules are added
- [ ] Document the target package map for the knowledge substrate

### Runtime contracts
- [ ] Standardize the MCP retrieval contract for chunk text, provenance, confidence, freshness, trust tier, and rationale
- [ ] Standardize naming for memory search, memory store, exemplar recall, and weekly ingest tools
- [ ] Add migration notes for any compatibility shims required during refactor

### Workflow alignment
- [ ] Add the knowledge-substrate refactor checklist to the weekly automation planning work
- [ ] Ensure workflow labels, docs, and tests are updated in lockstep with naming and schema changes

---

## Phase 1: Core MCP Layer

**Priority: CRITICAL - Everything else depends on this**

### mcp_resources.py
- [ ] Create `hlf/mcp_resources.py`
- [ ] Implement `HLFResourceProvider` class
- [ ] Implement `list_resources()` - grammar, bytecode, dictionaries, version, ast-schema
- [ ] Implement `list_resource_templates()` - programs/{name}, profiles/{tier}
- [ ] Implement `read_resource(uri)` - fetch content for each resource
- [ ] Implement `subscribe_resource()` - file watcher for changes
- [ ] Implement `_generate_dictionaries()` - extract from grammar + programs

### mcp_tools.py
- [ ] Create `hlf/mcp_tools.py`
- [ ] Implement `HLFToolProvider` class
- [ ] Implement tool: `hlf_compile` - source → bytecode
- [ ] Implement tool: `hlf_execute` - bytecode → result
- [ ] Implement tool: `hlf_validate` - syntax/effect/gas validation
- [ ] Implement tool: `hlf_friction_log` - log friction events
- [ ] Implement tool: `hlf_self_observe` - meta-intent emission
- [ ] Implement tool: `hlf_get_version` - version/checksum
- [ ] Implement tool: `hlf_compose` - combine programs
- [ ] Implement tool: `hlf_decompose` - split program into components

### mcp_prompts.py
- [ ] Create `hlf/mcp_prompts.py`
- [ ] Implement `HLFPromptProvider` class
- [ ] Implement prompt: `hlf_initialize_agent` - full grammar injection
- [ ] Implement prompt: `hlf_express_intent` - natural language → HLF
- [ ] Implement prompt: `hlf_troubleshoot` - diagnosis template
- [ ] Implement prompt: `hlf_propose_extension` - friction → proposal
- [ ] Implement prompt: `hlf_compose_agents` - multi-agent composition

### mcp_server_complete.py
- [ ] Create `hlf/mcp_server_complete.py`
- [ ] Implement `MCPServer` class with full protocol support
- [ ] Wire all resources, tools, prompts
- [ ] Implement stdio transport (MCP standard)
- [ ] Implement HTTP transport (FastAPI alternative)
- [ ] Add health endpoint
- [ ] Add logging support

### mcp_client.py
- [ ] Create `hlf/mcp_client.py`
- [ ] Implement `HLFMCPClient` class
- [ ] Implement `get_version()` with caching
- [ ] Implement `get_grammar()` with caching
- [ ] Implement `get_dictionaries()` with caching
- [ ] Implement `get_init_prompt()` - tier/profile/focus params
- [ ] Implement `compile()` - remote compilation
- [ ] Implement `execute()` - remote execution
- [ ] Implement `validate()` - remote validation
- [ ] Implement `friction_log()` - report friction
- [ ] Implement `get_system_prompt()` - full injection vector
- [ ] Implement `check_version_change()` - poll for updates

---

## Phase 2: Dictionary Generator

**Priority: HIGH - Required before MCP can serve dictionaries**

### gen_dictionary.py
- [ ] Create `scripts/gen_dictionary.py`
- [ ] Parse `hlf/spec/core/grammar.yaml` for glyph mappings
- [ ] Parse `hlf/spec/vm/bytecode_spec.yaml` for opcode catalog
- [ ] Parse `examples/*.hlf` for pattern examples
- [ ] Generate `glyph_to_ascii` dictionary
- [ ] Generate `ascii_to_glyph` dictionary
- [ ] Generate `opcode_catalog` with gas/effects
- [ ] Generate `effect_index` from grammar
- [ ] Generate `pattern_examples` from programs
- [ ] Add metadata: version, generated_at, grammar_sha256
- [ ] Write to `mcp_resources/dictionaries.json`

### CI Integration
- [ ] Add job to `.github/workflows/ci.yml`: `generate-dictionaries`
- [ ] Run after `grammar-tests` job
- [ ] Copy `hlf/spec/core/grammar.yaml` → `mcp_resources/grammar.md`
- [ ] Upload `mcp_resources/` as artifact

---

## Phase 3: Friction Pipeline

**Priority: MEDIUM - Required for self-evolution**

### forge_agent.py
- [ ] Create `hlf/forge_agent.py`
- [ ] Implement `FrictionReport` dataclass
- [ ] Implement `GrammarProposal` dataclass
- [ ] Implement `ForgeAgent` class
- [ ] Implement `run()` - main poll loop
- [ ] Implement `_parse_friction()` - parse .hlf files
- [ ] Implement `_validate_friction()` - run hlfc/hlflint
- [ ] Implement `_craft_proposal()` - generate extension
- [ ] Implement `_submit_proposal()` - call MCP endpoint
- [ ] Implement `_get_validation_token()` - fetch CI token
- [ ] Add CLI entry point: `forge_main()`

### Host Function Integration
- [ ] Wire `FRICTION_LOG` in `hlf/host_functions_minimal.py`
- [ ] Write to `~/.sovereign/friction/{id}.hlf`
- [ ] Include grammar_sha256 and metadata

### Directory Structure
- [ ] Create `~/.sovereign/friction/` on first run
- [ ] Create `~/.sovereign/friction/processed/`
- [ ] Create `~/.sovereign/grammar/history/`
- [ ] Create `~/.sovereign/cache/bytecode/`

---

## Phase 4: CI Integration

**Priority: HIGH - Required for trust chain**

### generate_token.py
- [ ] Create `scripts/generate_token.py`
- [ ] Implement `generate_token(ci_run_id, grammar_sha)` - HMAC signature
- [ ] Implement `validate_token(token)` - verify CI origin
- [ ] Add expiry checking (1 hour TTL)
- [ ] Add CLI for manual token generation

### CI Workflow Updates
- [ ] Add `generate-dictionaries` job to `.github/workflows/ci.yml`
- [ ] Add `generate-validation-token` job
- [ ] Require `CI_HMAC_SECRET` in repository secrets
- [ ] Upload validation token as artifact
- [ ] Pass token to MCP server deployment

---

## Phase 5: Docker

**Priority: MEDIUM - Required for deployment**

### Dockerfile.mcp
- [ ] Create `Dockerfile.mcp`
- [ ] Base on `python:3.12-slim`
- [ ] Install `uv` for dependency management
- [ ] Copy `hlf/`, `examples/`, `scripts/`
- [ ] Create `/root/.sovereign/friction/`
- [ ] Expose port 8000
- [ ] Add health check
- [ ] Set `MCP_HMAC_KEY` env var

### Dockerfile.forge
- [ ] Create `Dockerfile.forge`
- [ ] Base on `python:3.12-slim`
- [ ] Install `git` for PR creation
- [ ] Copy `hlf/`, `scripts/`
- [ ] Run `hlf.forge_agent`

### docker-compose.yml Updates
- [ ] Add `mcp-server` service
- [ ] Add `forge-agent` service (optional profile)
- [ ] Mount `./data/friction:/root/.sovereign/friction`
- [ ] Mount `./mcp_resources:/app/mcp_resources:ro`
- [ ] Configure `MCP_HMAC_KEY` from env
- [ ] Configure `GITHUB_TOKEN` from env
- [ ] Add health checks
- [ ] Create `sovereign-net` network

---

## Phase 6: Documentation

**Priority: LOW - Required for adoption**

### MCP_INTEGRATION.md
- [ ] Create `docs/MCP_INTEGRATION.md`
- [ ] Document all resource URIs
- [ ] Document all tool signatures
- [ ] Document all prompt templates
- [ ] Include code examples for each endpoint
- [ ] Include error handling examples
- [ ] Include caching recommendations

### FORGE_AGENT.md
- [ ] Create `docs/FORGE_AGENT.md`
- [ ] Document Forge agent architecture
- [ ] Document friction report format
- [ ] Document proposal lifecycle
- [ ] Document CI token validation
- [ ] Include troubleshooting guide

### README Updates
- [ ] Update `HLF_README.md` with MCP section
- [ ] Add quick start for MCP client
- [ ] Add quick start for Forge agent
- [ ] Link to full documentation

---

## Optional: Agent Integration for Existing Systems

**The MCP layer is designed to be agent-agnostic. Systems with existing agents can integrate without using the Forge/Sovereign agent architecture:**

### For Claude/GPT-4/etc. (via MCP Client)
- [ ] Use `mcp_client.get_system_prompt()` to inject grammar
- [ ] Use `mcp_client.compile()` to compile HLF source
- [ ] Use `mcp_client.execute()` to run bytecode
- [ ] Use `mcp_client.friction_log()` to report issues
- [ ] Poll `mcp_client.check_version_change()` for updates

### For Custom Agents (via HTTP API)
- [ ] GET `/resource/grammar` - fetch grammar
- [ ] GET `/resource/dictionaries` - fetch compression dicts
- [ ] POST `/tool/compile` - compile source
- [ ] POST `/tool/execute` - execute bytecode
- [ ] POST `/tool/friction_log` - report friction

### For MCP-Native Agents (via stdio)
- [ ] Implement MCP protocol handshake
- [ ] Call `resources/list` → get available resources
- [ ] Call `resources/read` → fetch grammar/dictionaries
- [ ] Call `tools/list` → get available tools
- [ ] Call `tools/call` → compile/execute/friction
- [ ] Call `prompts/list` → get prompt templates
- [ ] Call `prompts/get` → get initialization prompt

---

## Verification Checklist

After implementation, verify:

- [ ] `python -m hlf.mcp_server_complete --stdio` starts correctly
- [ ] `curl localhost:8000/resource/grammar` returns grammar
- [ ] `curl localhost:8000/resource/dictionaries` returns dictionaries
- [ ] `curl localhost:8000/resource/version` returns version info
- [ ] `POST /tool/compile` compiles HLF source
- [ ] `POST /tool/execute` executes bytecode
- [ ] `POST /tool/friction_log` creates friction file
- [ ] Forge agent processes friction files
- [ ] CI generates validation tokens
- [ ] Docker Compose starts all services
- [ ] MCP client can initialize from scratch

---

## Notes

- All file paths are relative to `C:/Users/gerry/generic_workspace/HLF_MCP/`
- Phase 1 is blocking - everything else depends on MCP layer
- Phase 2-4 can be parallelized
- Phase 5-6 can be done last
- The Forge agent is OPTIONAL for external systems