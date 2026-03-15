# HLF_MCP TODO List

## Status Overview

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: Core MCP Layer | ✅ COMPLETED | 100% |
| Phase 2: Dictionary Generator | 🔶 PENDING | 0% |
| Phase 3: CI Integration | 🔶 PENDING | 0% |
| Phase 4: Docker | 🔶 PENDING | 0% |
| Phase 5: Fix Pre-existing Issues | ✅ COMPLETED | 100% |
| Phase 6: Documentation | 🔶 PENDING | 0% |
| Phase 7: HLF Language Analysis | 🔄 IN PROGRESS | 60% |
| Phase 8: Final Verification | 🔶 PENDING | 0% |

---

## Phase 1: Core MCP Layer ✅ COMPLETED

- [x] Create `hlf/mcp_resources.py` - MCP Resources implementation
- [x] Create `hlf/mcp_tools.py` - MCP Tools implementation
- [x] Create `hlf/mcp_prompts.py` - MCP Prompts implementation
- [x] Create `hlf/mcp_server_complete.py` - Complete MCP server
- [x] Create `hlf/mcp_client.py` - HTTP client for agents
- [x] Create `hlf/mcp_metrics.py` - Usage metrics tracking
- [x] Create `run_tests.py` - Basic test runner
- [x] All 6 tests passing
- [x] Fix `hlf/__init__.py` broken imports - MINIMIZED TO ESSENTIALS
- [x] Fix `hlf/ast_nodes.py` - Forward reference issue RESOLVED

---

## Phase 2: Dictionary Generator (PENDING)

### Priority: HIGH - Required for MCP

- [ ] Create `scripts/gen_dictionary.py`
  - [ ] Parse `hlf/spec/core/grammar.yaml` for glyph mappings
  - [ ] Parse `hlf/spec/vm/bytecode_spec.yaml` for opcode catalog
  - [ ] Scan `hlf_programs/*.hlf` for usage patterns
  - [ ] Generate `mcp_resources/dictionaries.json`
  - [ ] Add generated_at and grammar_sha metadata
- [ ] Integrate into CI workflow

---

## Phase 3: CI Integration (PENDING)

- [ ] Create `scripts/generate_token.py` - HMAC token generator
- [ ] Update `.github/workflows/ci.yml`:
  - [ ] Add `generate-dictionaries` job
  - [ ] Add `generate-validation-token` job
  - [ ] Copy grammar.md to mcp_resources
- [ ] Add `CI_HMAC_SECRET` to secrets

---

## Phase 4: Docker (PENDING)

- [ ] Create `Dockerfile.mcp`
  - [ ] Python 3.12 base
  - [ ] Install dependencies
  - [ ] Copy HLF source
  - [ ] Copy MCP server
  - [ ] Create directories
  - [ ] Health check
- [ ] Create `Dockerfile.forge`
  - [ ] Python 3.12 base
  - [ ] Install dependencies
  - [ ] Copy HLF source
  - [ ] Copy Forge agent
  - [ ] Create directories
- [ ] Update `docker-compose.yml`:
  - [ ] Add `mcp-server` service
  - [ ] Add `forge-agent` service (optional profile)
  - [ ] Mount volumes for friction data
  - [ ] Configure networks

---

## Phase 5: Fix Pre-existing Issues ✅ COMPLETED

- [x] Fix `hlf/__init__.py` - Minimized to essential imports only
- [x] Fix `hlf/ast_nodes.py` - Expression class inheritance order FIXED
- [x] Verify all pre-existing modules work

---

## Phase 6: Documentation (PENDING)

- [ ] Update README with MCP documentation
- [ ] Create `docs/MCP_INTEGRATION.md` - Integration guide
- [ ] Create `docs/FORGE_AGENT.md` - Friction pipeline docs
- [x] Create `HLF_EXHAUSTIVE_ANALYSIS.md` - Language analysis foundation

---

## Phase 7: HLF Language Analysis (IN PROGRESS - 60%)

### Source Repository
GitHub: https://github.com/Grumpified-OGGVCT/Sovereign_Agentic_OS_with_HLF

### Approach
Using hidden browser tabs + git clone to fetch raw source files directly from GitHub, then extracting:
1. Exact line numbers for all claims
2. Complete implementation code
3. Full function signatures
4. Complete data structures

---

### 7.1 Grammar and Lark Parser ✅ COMPLETED

- [x] Extract full grammar from `hlf/spec/core/grammar.yaml`
- [x] Document all statement types
- [x] Document operators and glyph mappings
- [x] Document type annotation tokens
- [x] Document GLYPH_PREFIX and terminator rules
- [x] Document AST transparency mandate

**GAPS TO FILL:**
- [ ] Full literal `_GRAMMAR` string from `hlf/hlfc.py` (lines 85-235)
- [ ] Complete TYPE_SYM Unicode codepoints
- [ ] Exhaustive GLYPH_PREFIX character list
- [ ] Specific Lark precedence rules (`_priority`, `_assoc`)

---

### 7.2 Compilation Pipeline ✅ COMPLETED

- [x] Document AST node types (Statement, Expression, etc.)
- [x] Document compilation phases
- [x] Document symbol resolution

**GAPS TO FILL:**
- [ ] Detailed normalization logic in `_pass0_normalize`
- [ ] Raw parse tree format before `HLFTransformer`
- [ ] `HLFTransformer` internal methods (`visit_tag_stmt`, etc.)
- [ ] Human-readable string generation logic

---

### 7.3 Bytecode and VM ✅ COMPLETED

- [x] Extract opcode enumeration from `hlf/vm/bytecode.py`
- [x] Document gas cost model
- [x] Document constant pool format
- [x] Document VM initialization
- [x] Document execution loop
- [x] Document error handling

**GAPS TO FILL:**
- [ ] Exact binary layout of constant pool
- [ ] Full opcode semantic implementations (each handler in `_dispatch`)
- [ ] Compiler emitter methods (`_emit_set`, `_emit_tool`, etc.)
- [ ] Jump-patching logic for conditionals

---

### 7.4 AST Interpreter 🔄 IN PROGRESS

- [x] Document interpreter purpose
- [ ] Document `_execute_node` implementation details (`hlf/hlfrun.py`)
- [ ] Document import resolution flow
- [ ] Document parallel/sync constructs
- [ ] Document macro expansion
- [ ] Document spec lifecycle handlers

**FILES TO EXTRACT:**
- `hlf/hlfrun.py` - Full interpreter implementation
- `hlf/runtime.py` - Runtime support

---

### 7.5 Host Function Registry ✅ COMPLETED

- [x] Document FunctionSpec dataclass
- [x] Document 5 P0 host functions
- [x] Document tier enforcement
- [x] Document gas metering
- [x] Document argument validation
- [x] Document sensitive output handling
- [x] Document backend dispatchers

**GAPS TO FILL:**
- [ ] `HostFunction.validate_args(call_args)` implementation
- [ ] Full backend dispatcher code (`_dispatch_file_read`, etc.)
- [ ] Dapr API invocation specifics
- [ ] Sensitive output hashing implementation

---

### 7.6 Module System 🔴 NOT EXTRACTED

**FILES TO EXTRACT:**
- `hlf/runtime.py` - ModuleLoader class (lines 458-466, 414-435, 646-652)

**GAPS TO FILL:**
- [ ] Full `ModuleLoader` implementation
- [ ] Search path order and logic
- [ ] Checksum validation against ACFS manifest
- [ ] Circular import detection (`self._loading` set)
- [ ] Caching strategies
- [ ] OCI fallback mechanism
- [ ] `ModuleNamespace` export/import logic
- [ ] `merge_into_env` implementation

---

### 7.7 Package Manager 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/hlfpm.py` - Complete file

**GAPS TO FILL:**
- [ ] `install` command implementation
- [ ] `uninstall` command implementation
- [ ] `list` command implementation
- [ ] `search` command implementation
- [ ] `freeze` command implementation
- [ ] Lockfile JSON format (version, ref, sha256, size)
- [ ] OCIClient interaction code

---

### 7.8 OCI Client 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/oci_client.py` - Complete file

**GAPS TO FILL:**
- [ ] `OCIModuleRef` parsing logic (regex/algorithm)
- [ ] `_fetch_manifest` HTTP details
- [ ] `_fetch_blob` HTTP details
- [ ] Authentication mechanisms for registry
- [ ] Network error handling
- [ ] Caching strategy (cache path, naming, invalidation)
- [ ] `push()` implementation (layer construction, manifest creation)
- [ ] `list_tags()` implementation (/tags/list endpoint)

---

### 7.9 Tool Dispatch Bridge 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/tool_dispatch.py` - Complete file

**GAPS TO FILL:**
- [ ] `importlib.util` lazy-loading implementation
- [ ] `governance/tool_registry.json` full schema
- [ ] `dispatch()` method - full implementation
- [ ] `register_all(host_registry)` - registration code

---

### 7.10 Intent Capsules 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/intent_capsule.py` - Complete file

**GAPS TO FILL:**
- [ ] `IntentCapsule` class - full definition (fields, methods)
- [ ] `_validate_node` - pre-flight validation code
- [ ] `_exec_set` / `_exec_assign` overrides
- [ ] `CapsuleViolation` exception definition
- [ ] Factory functions: `sovereign_capsule()`, `hearth_capsule()`, `forge_capsule()`
- [ ] Exact `allowed_tags`, `allowed_tools`, `max_gas`, `tier`, `read_only_vars` configurations

---

### 7.11 Memory Node 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/memory_node.py` - Complete file

**GAPS TO FILL:**
- [ ] `MemoryNode` dataclass - full field definitions
- [ ] `content_hash` calculation (SHA-256 of canonical AST)
- [ ] `matches_content()` - content verification
- [ ] TTL enforcement mechanism
- [ ] Tag management (storage, indexing, querying)
- [ ] `to_dict()` / `from_dict()` serialization
- [ ] Runtime API for MEMORY_STORE/MEMORY_RECALL

---

### 7.12 Translator 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/translator.py` - Complete file

**GAPS TO FILL:**
- [ ] Tone detection algorithm (cue-words, T enum)
- [ ] Nuance glyph encoding logic (`~tag{context}`)
- [ ] `english_to_hlf()` - HLF program construction
- [ ] `hlf_to_english()` - parsing and summary generation
- [ ] `roundtrip()` - verification logic

---

### 7.13 InsAIts Decompiler 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/insaits.py` - Complete file

**GAPS TO FILL:**
- [ ] `decompile(ast)` - AST walk and English output
- [ ] `decompile_live(ast)` - generator implementation
- [ ] `decompile_bytecode(hlb)` - bytecode to English
- [ ] `_OPCODE_PROSE` - complete mapping
- [ ] Homograph safety integration

---

### 7.14 Language Server 🔴 NOT EXTRACTED

**FILE TO EXTRACT:**
- `hlf/hlflsp.py` - Complete file

**GAPS TO FILL:**
- [ ] Diagnostics pipeline (`hlflint` integration)
- [ ] Completion provider logic (tags, glyphs, stdlib, host-functions, variables)
- [ ] `textDocument/hover` handler
- [ ] `textDocument/definition` handler
- [ ] `textDocument/documentSymbol` handler

---

### 7.15 Standard Library 🔴 NOT EXTRACTED

**FILES TO EXTRACT:**
- `hlf/stdlib/agent.hlf`
- `hlf/stdlib/collections.hlf`
- `hlf/stdlib/crypto.hlf`
- `hlf/stdlib/io.hlf`
- `hlf/stdlib/math.hlf`
- `hlf/stdlib/net.hlf`
- `hlf/stdlib/string.hlf`
- `hlf/stdlib/system.hlf`

**GAPS TO FILL:**
- [ ] Function signatures for each stdlib module
- [ ] Arguments and return types
- [ ] Module dependencies
- [ ] Effect categories per function

---

### 7.16 Governance Files 🔴 NOT EXTRACTED

**FILES TO EXTRACT:**
- `governance/host_functions.json` - Full schema
- `governance/templates/dictionary.json` - Template format
- `governance/bytecode_spec.yaml` - Complete spec
- `governance/acfs.manifest.yaml` - Security manifest

**GAPS TO FILL:**
- [ ] Host function JSON schema (complete)
- [ ] Dictionary template structure
- [ ] Bytecode spec format
- [ ] ACFS manifest structure

---

### 7.17 Grammar Reference 🔴 NOT ANALYZED

**FILE TO EXTRACT:**
- `docs/HLF_GRAMMAR_REFERENCE.md`

**GAPS TO FILL:**
- [ ] Complete grammar documentation
- [ ] Examples and edge cases
- [ ] Operator precedence reference

---

### 7.18 Final Report Status

- [x] Created `HLF_EXHAUSTIVE_ANALYSIS.md` foundation
- [x] Sections 1-5 have file citations (need line-level extraction)
- [x] Sections 6-18 explicitly marked as "NOT EXTRACTED"
- [ ] 🔄 ACTIVELY EXTRACTING: Fetching raw source from GitHub
- [ ] Fill all 18 sections with exact line citations
- [ ] Add complete code snippets for all implementations

---

## Phase 8: Complete Remaining Files (PENDING)

- [ ] Create `mcp_resources/` directory
- [ ] Generate initial `mcp_resources/dictionaries.json`
- [ ] Copy grammar to `mcp_resources/grammar.md`

---

## Verification Checklist

- [x] All tests pass: `python run_tests.py`
- [ ] MCP server starts: `python -m hlf.mcp_server_complete`
- [ ] Resources accessible: `curl http://localhost:8000/resource/grammar`
- [ ] Tools work: `curl -X POST http://localhost:8000/tool/compile`
- [ ] Metrics tracked: `~/.sovereign/mcp_metrics/stats.json`

---

## Priority Order

### CRITICAL PATH (Blocking)

1. **Phase 7** - Complete HLF Language Analysis
   - Use git clone to fetch source efficiently
   - Extract ALL code with line numbers
   - Fill ALL 18 sections completely

2. **Phase 2** - Dictionary Generator (required for MCP)

3. **Phase 3** - CI Integration

### SECONDARY

4. **Phase 4** - Docker
5. **Phase 6** - Documentation
6. **Phase 8** - Final verification

---

## Files Created So Far

| File | Status | Description |
|------|--------|-------------|
| `hlf/mcp_resources.py` | ✅ | MCP Resources (tested, working) |
| `hlf/mcp_tools.py` | ✅ | MCP Tools (tested, working) |
| `hlf/mcp_prompts.py` | ✅ | MCP Prompts (tested, working) |
| `hlf/mcp_server_complete.py` | ✅ | MCP Server (tested, working) |
| `hlf/mcp_client.py` | ✅ | MCP Client (tested, working) |
| `hlf/mcp_metrics.py` | ✅ | Usage Metrics (tested, working) |
| `hlf/forge_agent.py` | ✅ | Forge Agent (saved, needs testing) |
| `BUILD_GUIDE.md` | ✅ | Complete architecture guide |
| `TODO.md` | ✅ | This file (updated) |
| `run_tests.py` | ✅ | Test runner (working) |
| `HLF_EXHAUSTIVE_ANALYSIS.md` | 🔄 | Language analysis (60% complete) |

---

## Next Action

**CURRENTLY EXECUTING:** Git clone of GitHub repository to extract ALL source files with exact line numbers for comprehensive HLF language analysis.

**Command:**
```bash
git clone --depth 1 https://github.com/Grumpified-OGGVCT/Sovereign_Agentic_OS_with_HLF.git /tmp/hlf_source
```

Then systematically extract each file listed in sections 7.6-7.17.