# Hidden Coupling Report — Phase 1 Dependency Truth

Generated: 2026-05-23

## Critical Finding: Default Boot Path Pulls In Entire DSL/VM

**`server.py` → `server_context.py` (line 72: `_ctx = build_server_context()` at module level)**

`server_context.py` imports 42 `hlf_mcp` modules at the top level, including:

| Import | Line | Category |
|--------|------|----------|
| `HLFCompiler` | 23 | DSL compiler |
| `HLFRuntime` | 47 | DSL VM |
| `HLFBenchmark` | 21 | HLF-specific benchmarking |
| `HLFBytecode` | 22 | HLF bytecode format |
| `FormalVerifier` | 25 | HLF formal verification |
| `HLFLinter` | 44 | HLF-specific linter |
| `HLFFormatter` | 26 | HLF source formatter |

**Impact:** The server cannot boot without importing the HLF compiler, VM, benchmark, bytecode, formal verifier, and formatter. These are all at module level — not lazy imports.

## Most-Coupled Modules (Import Graph)

| Module | Files That Import It | Risk |
|--------|---------------------|------|
| `hlf_mcp.hlf.compiler.HLFCompiler` | 56 | DSL dependency pulled in by 56 files |
| `hlf_mcp.server` | 26 | Server module coupled to 26 consumers |
| `hlf_mcp.hlf.compiler.CompileError` | 25 | Error type from compiler, used across codebase |
| `hlf_mcp.hlf.formal_verifier.FormalVerifier` | 24 | Formal verification dependency |
| `hlf_mcp.hlf.capability_manifest.CapabilityManifest` | 21 | Manifest tied to HLF effect types |
| `hlf_mcp.hlf.typed_contracts.HlfType` | 21 | HLF type system leak into ecosystem |
| `hlf_mcp.hlf.bytecode.HLFBytecode` | 18 | Bytecode format used by 18 files |

## Env Var Coupling

~40+ `HLF_*` env vars across the codebase. Key examples:

| Env Var | Used In | Migration Difficulty |
|---------|---------|---------------------|
| `HLF_TRANSPORT` | server.py | Low — rename to `SG_TRANSPORT` with fallback |
| `HLF_HOST` / `HLF_PORT` | server.py | Low |
| `HLF_MASTER_KEY` | server_enterprise.py, merkle_dr.py | Low |
| `HLF_MEMORY_DB` | rag/memory.py, server_context.py | Low |
| `HLF_AUDIT_DB` | bridges/ audit_bridge.py | Low |
| `HLF_AUDIT_CHAIN_LOG` / `LAST_HASH` | audit_chain.py | Low |
| `HLF_AGENT_TIER` | server_enterprise.py | Low |
| `HLF_STRICT` | server_core.py | Low |
| `HLF_APPROVAL_LEDGER_DB` | approval_ledger.py | Low |
| `HLF_HKS_EXTERNAL_COMPARATOR_*` | server_memory.py | Low |

All are simple renames with fallback detection. No structural changes needed.

## Runtime Side Effects at Import Time

`server_context.py:72` — `_ctx = build_server_context()` executes at import. This:
1. Instantiates `HLFCompiler` (parses grammar, loads stdlib)
2. Instantiates `HLFRuntime` (loads bytecode definitions)
3. Creates `RAGMemory` with database connection
4. Creates `InstinctLifecycle` (loads SDD state machine)

None of these are lazy. They all execute when `import hlf_mcp.server` runs.

## Config Path Hardcoding

| File | Hardcoded Path |
|------|---------------|
| `persona_contract.py:91` | `governance/HLF_PERSONA_OWNERSHIP_MATRIX.json` |
| `persona_runtime.py:14` | `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` |
| `authority.py:40-42` | `docs/HLF_VISION_PLAIN_LANGUAGE.md`, `docs/HLF_CLAIM_LANES.md` |
| `doc_ingest.py:353` | `docs/HLF_VISION_DOCTRINE.md` |
| `operator_doctrine.py:16` | References `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` |

## CRITICAL: hlf_mcp/__init__.py Poisons Every Import Path

**`hlf_mcp/__init__.py`** (line 15) imports `HLFBytecode`, line 24 imports `HLFCompiler`, and subsequent lines import `HLFRuntime`, `HLFFormatter`, `HLFLinter`, `HLFCodeGenerator`, `Tone`, and all translator functions. These are all **module-level imports** — not lazy.

**Impact:** `import hlf_mcp` (or any submodule import like `from hlf_mcp.rag.memory import RAGMemory`) triggers the parent package `__init__.py`, which loads the entire DSL stack into `sys.modules`. This means:

- **ZERO modules within hlf_mcp are truly DSL-free.** Even the bridge modules (`constraint_bridge.py`, `audit_bridge.py`, `memory_bridge.py`) which have zero `hlf_mcp` imports themselves cannot be reached without triggering the package init.
- **The "clean modules" classification was overly optimistic.** The clean-governance-modules exploration correctly identified that individual `.py` files don't import from `hlf_mcp.hlf.compiler/runtime/bytecode`, but missed that Python's package import mechanism loads `__init__.py` first.
- **The vertical slice proof confirms this.** `from hlf_mcp.rag.memory import RAGMemory` loads `hlf_mcp.hlf.compiler`, `hlf_mcp.hlf.runtime`, and `hlf_mcp.hlf.bytecode` into `sys.modules`, even though `rag/memory.py` only imports from `hlf_mcp.hlf.memory_node`.

**Fix required for Phase 2:** `hlf_mcp/__init__.py` must be refactored to use lazy imports (inside functions) or the package structure must be split so that governance modules live in a separate namespace that doesn't trigger the DSL `__init__.py`.

## Vertical Slice Workaround

The vertical slice proof (`docs/swarmglass_vertical_slice.py`) works around this by reimplementing the governance primitives inline using ONLY Python stdlib — no `hlf_mcp` imports at all. This proves the concepts (constraint validation, Merkle-chained audit, provenance memory with superseding) work without the DSL stack, but it also proves that the current package structure makes this impossible using the real modules.

## Verdict

**The default boot path DOES pull in DSL/VM/compiler code.** This is a Gate 1 blocker if the goal is "server boots without HLF VM imported by default."

**Additional finding: The package-level __init__.py means NO import path is clean.** This is more fundamental than the server_context.py coupling — it affects every single module.

**Mitigation path:** 
1. Refactor `hlf_mcp/__init__.py` to use lazy imports (Phase 2)
2. Split `ServerContext` into `CoreContext` (governance/audit/memory only) and `HlfContext` (adds compiler/runtime/benchmark) gated behind `SWARMGLASS_HLF_ENABLED=1`
3. Move bridge modules to a separate `swarmglass/` namespace that doesn't trigger `hlf_mcp/__init__.py`
