# HLF VM Audit Report — Live Swarm Execution Readiness

**Date:** 2026-05-17
**Scope:** `hlf_mcp/hlf/` compiler, bytecode, runtime, swarm orchestrator, server swarm
**Auditor:** Copilot CLI (systematic code review + test execution)
**Goal:** Determine which VM components are real, which are stubbed/simulated, and what gaps prevent live multi-agent swarm execution orchestrated from HLF bytecode.

---

## 1. Executive Summary

| Component | Status | Reality |
|-----------|--------|---------|
| Compiler (LALR parser → JSON AST) | **Production-grade** | Real — 5-pass pipeline, recovery, ethics governor |
| Bytecode encoder/decoder | **Production-grade** | Real — `.hlb` binary format, roundtrip verified |
| VM (`HlfVM.execute`) | **Functional but limited** | Real stack-machine interpreter with gas metering |
| Host dispatch (`_dispatch_builtin`) | **Mostly real** | 30+ builtins implemented; IO works under ACFS confinement |
| Host dispatch (`_dispatch_host`) | **Real but fragile** | Same functions with tier enforcement + side-effect recording |
| Swarm orchestrator | **Simulation only** | Python dataclass agents, no live process spawning |
| Server swarm (`server_swarm.py`) | **Stub / shim** | Exposes MCP tools that delegate to simulated orchestrator |
| Grammar swarm constructs | **Missing** | No `agent`, `interface`, `effect`, `spawn`, `swarm` statements |
| Live agent execution from HLF | **Blocked** | No bridge from compiled bytecode to actual agent processes |

**Verdict:** The compiler and VM are real and can execute bytecode with genuine side effects (file IO, HTTP, crypto). However, the swarm layer is entirely a Python simulation — it does **not** spawn, message, or coordinate live agents. The gap is not in the VM but in the orchestration layer and language constructs needed to express swarms.

---

## 2. Compiler Pipeline (Real)

### 2.1 Architecture
`hlf_mcp/hlf/compiler.py` — `HLFCompiler.compile()` runs 5 passes:

1. **Unicode normalization** (NFKC) + ASCII glyph alias substitution (`[CMD]` → `⌘`, etc.)
2. **Parse** — Lark LALR(1) grammar (`hlf_mcp/hlf/grammar.py`)
3. **Env collection** — immutable SET binding discovery
4. **ALIGN Ledger security rules** — `∇ [OBSERVE]`, `⩕ [PLAN]` tag validation
5. **Variable expansion** — `$VAR` substitution with scoping

Output: JSON AST array of statement objects.

### 2.2 Language Features Supported

| Feature | Grammar | Bytecode | VM Execution |
|---------|---------|----------|--------------|
| `[SET]` / `ASSIGN` bindings | ✅ | ✅ | ✅ Immutable |
| `IF / ELIF / ELSE` blocks | ✅ | ✅ | ✅ Jump-patched |
| `FOR` loops | ✅ | ✅ | ✅ |
| `PARALLEL` blocks | ✅ | ✅ | ✅ |
| `FUNCTION` declarations | ✅ | ✅ | ✅ |
| `INTENT` statements | ✅ | ✅ | ✅ |
| `TOOL` / `CALL` | ✅ | ✅ | ✅ `CALL_TOOL` opcode |
| `MEMORY` / `RECALL` | ✅ | ✅ | ✅ Host dispatch to `delegate` / `route` |
| `SPEC` lifecycle | ✅ | ✅ | ✅ `SPEC_*` opcodes |
| `IMPORT` | ✅ | ✅ | ✅ |
| `LOG` | ✅ | ✅ | ✅ |
| `RESULT` | ✅ | ✅ | ✅ |
| Glyph tags (`ΔЖ⨝⌘∇⩕⊎`) | ✅ | ✅ | ✅ |

### 2.3 Recovery & Safety
- `HLFCorrector` (`compile_with_recovery`) rewrites malformed SET lines with LLM-like regex heuristics.
- `hlf_mcp.hlf.ethics.governor.check()` is called at compile time and runtime.
- PII guard scans memory store operations for redaction.
- Tier system: `hearth` (default) / `forge` / `sovereign`.

### 2.4 Test Evidence
- `tests/test_compiler.py` — **21/21 passed** — all fixtures parse correctly.
- `tests/test_codegen.py` — **4/4 passed** — programmatic HLF builder produces valid AST and bytecode artifacts.
- `tests/test_bytecode_roundtrip.py` — **1/1 passed** — `.hlb` serialization ↔ deserialization verified.

---

## 3. Bytecode System (Real)

`hlf_mcp/hlf/bytecode.py`

### 3.1 Format (v0.4)
- 32-byte SHA-256 prefix
- 16-byte header: `magic(4)`, `version(4)`, `code_len(4)`, `crc32(4)`, `flags(2)`, `reserved(2)`
- Typed constant pool (big-endian type tag + little-endian size + bytes)
- Fixed 3-byte instructions: `opcode(1) + operand(2)` little-endian

### 3.2 Opcode Coverage (30 opcodes)

| Category | Opcodes |
|----------|---------|
| Stack | `PUSH_CONST`, `POP`, `DUP`, `SWAP` |
| Arithmetic | `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `POW` |
| Comparison | `EQ`, `NE`, `LT`, `LE`, `GT`, `GE` |
| Control | `JUMP`, `JUMP_IF_TRUE`, `JUMP_IF_FALSE`, `LABEL` |
| Calls | `CALL_BUILTIN`, `CALL_HOST`, `CALL_TOOL`, `OPENCLAW_TOOL` |
| Memory/Spec | `TAG`, `INTENT`, `MEMORY`, `RECALL`, `SPEC_NEW`, `SPEC_RUN`, `SPEC_HALT` |
| Halt | `HALT` |

### 3.3 Bytecode Compiler
`BytecodeCompiler.encode(ast)` → `_emit_stmt()` handles ~15 AST statement kinds with forward jump patching for control flow.

### 3.4 Disassembler
`Disassembler.decode(data)` produces structured opcodes + constant pool dump.

---

## 4. VM / Runtime (Real but with Caveats)

`hlf_mcp/hlf/runtime.py`

### 4.1 `HlfVM` (~line 302)
Pure stack-machine interpreter:
- Fetches 3-byte instructions
- Maintains operand stack and locals dict
- Gas metering (`vm.gas` decremented per opcode)
- Immutability enforcement for `[SET]` bindings
- Execution trace recording

### 4.2 `HLFRuntime` (~line 1527)
Wrapper that adds:
- Ethics governor pre-flight check
- Formal verifier admission gate (`admit` flag)
- Audit logging (`audit_log` dict)
- Side-effect sealing (`side_effects` list)
- Pointer resolution (`_resolve_pointer`)
- PII guard (`_pii_guard`)
- Memory context (`_memory_context`)

### 4.3 Host Function Registry
`HOST_FUNCTIONS` declares 30+ functions with:
- Tier restriction (`hearth`/`forge`/`sovereign`)
- Effect tags (`read_fs`, `write_fs`, `network`, `spawn`, `crypto`)
- Pointer support
- Immutability flag

### 4.4 Two Dispatch Paths

#### Path A: `_dispatch_builtin` (~line 779)
Called by `Op.CALL_BUILTIN`. Direct Python implementations:
- Math, string, list, crypto, system, agent, IO builtins
- `WRITE` / `FILE_WRITE` → calls `hlf_mcp.hlf.stdlib.io_mod.FILE_WRITE`
- Actually writes files under ACFS confinement

#### Path B: `_dispatch_host` (~line 1085)
Called by `Op.CALL_HOST`. Same functions plus:
- Tier enforcement (raises `PermissionError` if tier mismatch)
- Side-effect recording (appends to `side_effects` list)
- Pointer resolution
- PII guarding
- Memory context injection

### 4.5 Critical Finding: Host Dispatch Duality
There are **two parallel implementations** of the same host functions. They are mostly identical but diverge in:
- `_dispatch_builtin` lacks tier enforcement and side-effect recording
- `_dispatch_host` has extra security layers but the same underlying calls

**Risk:** Maintaining two dispatch paths invites drift. A fix in one may not propagate to the other.

### 4.6 Critical Finding: `analyze` Verb Dispatch Bug
When `fn_name == "analyze"` and `args[0]` is a known verb, `_dispatch_host` rewrites `fn_name = args[0]` and trims `args = args[1:]`. This is used for `⌘ [ACTION] verb="write_file" target="..."` patterns.

**Bug discovered:** In `scripts/test_live_execution.py`, the HLF source was:
```
⌘ [ACTION] verb="write_file" target="agent_output.txt"
  ∇ [PARAM] content="Hello from the HLF agent harness!"
  Ж [EXPECT] write_complete
```

The `∇ [PARAM]` is a **separate glyph statement**, not a nested argument. Therefore the bytecode:
1. Pushes `"write_file"`, `"agent_output.txt"` → stack
2. Calls `CALL_HOST "⌘ [ACTION]"` → resolves to `fn_name="write_file"`, `args=["agent_output.txt"]`
3. `write_file` receives only 1 arg (path, no data) → returns `False`
4. `∇ [PARAM]` and `Ж [EXPECT]` are executed as independent tag statements

**Result:** Side-effect `write_fs` was recorded (because `write_file` is declared with that effect tag), but **no file was actually written** because the call was malformed (missing `data` arg). The PermissionError from ACFS path validation was swallowed or bypassed because the function returned `False` before reaching the filesystem call.

**This is a language semantics gap, not a VM stub.** The VM correctly dispatched the call; the HLF source didn't compose the action with its parameters correctly.

### 4.7 ACFS Confinement
`hlf_mcp/hlf/stdlib/io_mod.py` restricts file paths to:
- `~/.hlf/workspace`
- `/tmp/hlf`
- `./hlf`

Any path outside these roots raises `PermissionError`. This is real security, not a stub.

### 4.8 Test Evidence
- `tests/test_runtime_memory_context.py` — **5/5 passed** — `delegate`/`route` with memory context works.
- `scripts/test_live_execution.py` — VM executes bytecode, returns `OK`, but file IO was **not observed** due to the argument arity bug described above.

---

## 5. Swarm Orchestrator (Simulation Only)

`hlf_mcp/hlf/swarm_orchestrator.py`

### 5.1 Architecture
`SwarmOrchestrator` runs two simulation modes:
- `run_3_agent_stack()` — Planner → Executor → Verifier
- `run_5_agent_swarm()` — adds Analyst + Auditor

### 5.2 What It Actually Does
1. Accepts a `translator_fn` (injected Python callable)
2. Manually appends missing tags (`_expand_hlf`, `_enrich_hlf`)
3. Calls `compiler.compile()` on the resulting HLF text
4. Calls `linter.lint()` for static checks
5. Returns a structured result dict with `agents`, `plan`, `verdict`

### 5.3 What It Does NOT Do
- ❌ Spawn live agent processes (no `subprocess`, `multiprocessing`, or container launch)
- ❌ Execute bytecode during swarm phases
- ❌ Inter-agent message bus or shared memory
- ❌ Dynamic agent discovery or registration
- ❌ Real-time consensus voting (the `⨝ [VOTE]` glyph is parsed but not executed as a distributed protocol)

**Verdict:** The swarm orchestrator is a **Python simulation of agent coordination**, not a live execution engine. It validates HLF plans but does not execute them across multiple live agents.

---

## 6. Server Swarm (`server_swarm.py`)

`hlf_mcp/server_swarm.py` exposes MCP tools:
- `run_swarm_orchestrator_3agent`
- `run_swarm_orchestrator_5agent`
- `run_swarm_orchestrator_custom`

These are thin shims that:
1. Accept HLF text via MCP parameters
2. Instantiate `SwarmOrchestrator`
3. Call the simulation methods above
4. Return the orchestrator result dict

**There is no live agent dispatch.** The server runs the simulation entirely in-process.

---

## 7. Grammar Assessment — Swarm Constructs

`hlf_mcp/hlf/grammar.py` defines 21 statement types.

### 7.1 Missing Constructs for Live Swarm

| Construct | Status | Impact |
|-----------|--------|--------|
| `agent` declaration | ❌ Not in grammar | Cannot declare agent capabilities in HLF |
| `interface` block | ❌ Not in grammar | Cannot define agent contracts |
| `effect` annotation | ❌ Not in grammar | Side effects are host-function metadata, not language constructs |
| `spawn` statement | ❌ Not in grammar | Cannot spawn agents from HLF |
| `swarm` block | ❌ Not in grammar | Cannot define swarm topology |
| `message` / `send` / `receive` | ❌ Not in grammar | No inter-agent communication primitives |
| `consensus` protocol | ❌ Not in grammar | `⨝ [VOTE]` is a tag, not an executable protocol |

### 7.2 Agent Concepts in HLF Today
Agent ideas exist only as:
- **Glyph tags:** `[DELEGATE]`, `[ROUTE]`, `[OBSERVE]`, `[PLAN]`, `[VOTE]`, `[ACTION]`
- **Stdlib function declarations:** `hlf_source/hlf/stdlib/agent.hlf` defines signatures in an older syntax that the v3 compiler does **not** parse
- **Host function names:** `delegate`, `route`, `spawn_agent` in `HOST_FUNCTIONS`

### 7.3 `swarm.hlf` Parsing Capability
**There is no `swarm.hlf` file in the repository.** The `glyph_showcase.hlf` fixture contains a single `⌘ [INTENT] orchestrate "swarm_task"` line, but this is just an intent tag — it does not declare a swarm.

**Conclusion:** The grammar **cannot** parse a dedicated `swarm.hlf` file because the necessary constructs do not exist. Any swarm coordination must be written in Python and injected via `translator_fn`.

---

## 8. Stub / Mock Inventory

### 8.1 Fully Stubbed / Mocked

| Component | Location | Nature |
|-----------|----------|--------|
| Swarm agent processes | `swarm_orchestrator.py` | Python dataclasses, no OS processes |
| Inter-agent message bus | Not present | N/A |
| Dynamic agent registry | Not present | N/A |
| Distributed consensus | Not present | `⨝ [VOTE]` is a parsed tag only |
| `spawn_agent` host function | `runtime.py` line ~1406 | Calls `FILE_WRITE` (not actual process spawn) |

### 8.2 Partially Implemented

| Component | What Works | What's Missing |
|-----------|-----------|----------------|
| `HlfVM.execute` | Stack ops, arithmetic, jumps, calls, tags, memory, specs | No JIT, no concurrency, no sandboxing beyond gas |
| `CALL_TOOL` / `OPENCLAW_TOOL` | Opcode exists | No actual tool server integration; `OPENCLAW_TOOL` is a stub |
| Host dispatch | 30+ functions implemented | `spawn_agent` writes a file instead of spawning; `z3_verify` requires external solver |
| `PARALLEL` block | Bytecode emits parallel marker | VM does not actually run blocks in parallel (sequential execution) |

### 8.3 Fully Implemented

| Component | Evidence |
|-----------|----------|
| Unicode normalization + glyph substitution | `compiler.py` lines ~477–490 |
| LALR(1) parsing + AST generation | `compiler.py` lines ~635–650 |
| ALIGN Ledger security rules | `compiler.py` lines ~583–600 |
| Ethics governor integration | `compiler.py` line ~672, `runtime.py` line ~1560 |
| Bytecode serialization / deserialization | `bytecode.py` roundtrip test passed |
| Gas metering | `runtime.py` `HlfVM.execute` loop |
| Immutability enforcement | `runtime.py` `write_memory` guards |
| ACFS file IO | `stdlib/io_mod.py` real path validation + read/write/delete |
| Audit logging | `runtime.py` `audit_log` dict populated per execution |
| Side-effect sealing | `runtime.py` `side_effects` list |

---

## 9. Gaps Preventing Live Swarm Execution

### 9.1 Language Gap: No Swarm Constructs
The grammar cannot express:
- Agent definitions with capabilities and interfaces
- Swarm topology (who talks to whom)
- Spawn / kill lifecycle
- Message passing between agents
- Distributed consensus protocols

**Impact:** Even if the VM could execute bytecode, there is no HLF syntax to describe a swarm.

### 9.2 Orchestration Gap: No Live Agent Dispatch
The swarm orchestrator is a simulation. To go live, it needs:
- Process/container spawning for each agent
- Inter-agent transport (message bus, shared memory, or sockets)
- Agent lifecycle management (health checks, restarts, teardown)
- Dynamic role assignment based on HLF plan

**Impact:** Swarm plans are validated but never executed across multiple live compute units.

### 9.3 VM Gap: No Concurrency
`PARALLEL` blocks are parsed and bytecode is emitted, but the VM executes them sequentially. There is no thread pool, async runtime, or multiprocessing integration.

**Impact:** Multi-agent workloads cannot exploit parallelism in the VM.

### 9.4 VM Gap: `OPENCLAW_TOOL` is a Stub
The opcode exists but dispatches to a placeholder that does nothing meaningful.

**Impact:** External tool integration (the "claw" mechanism) is not functional.

### 9.5 Host Gap: `spawn_agent` Does Not Spawn
`spawn_agent` in `HOST_FUNCTIONS` is wired to a function that writes a file instead of starting a process.

**Impact:** No way to dynamically create agents from within HLF execution.

### 9.6 Host Gap: `CALL_TOOL` Lacks Server Integration
While `CALL_TOOL` dispatches to Python functions, there is no integration with an external MCP tool server or plugin registry.

**Impact:** Tools must be statically linked into the runtime.

---

## 10. Recommended Build Plan

### Phase 1: Language Extensions (Grammar + Compiler) — ~2 weeks
**Goal:** Add swarm constructs to HLF v3 grammar.

1. **Extend grammar** (`grammar.py`):
   - `agent_stmt`: `agent <name> [interface <iface>] [tier <tier>] [capabilities <cap_list>]`
   - `swarm_stmt`: `swarm <name> { agent <ref> [as <role>] ... }`
   - `spawn_stmt`: `spawn <agent_name> [with <params>]`
   - `send_stmt`: `send <message> to <agent_ref>`
   - `receive_stmt`: `receive [from <agent_ref>] [timeout <ms>]`
   - `effect_decl`: `effect <name> [tier <tier>] [tags <tag_list>]`

2. **Update compiler passes**:
   - Env collection: collect agent/swarm bindings
   - ALIGN Ledger: add rules for agent tier compatibility
   - Ethics governor: add rules for spawn/network effects

3. **Update AST + bytecode**:
   - New AST node types: `agent`, `swarm`, `spawn`, `send`, `receive`
   - New opcodes: `SPAWN_AGENT`, `SEND_MSG`, `RECV_MSG`, `JOIN_SWARM`

### Phase 2: Live Agent Runtime — ~3 weeks
**Goal:** Replace simulation with live agent processes.

1. **Agent process model**:
   - Define `AgentProcess` class using `multiprocessing.Process` or `asyncio.subprocess`
   - Each agent runs its own `HLFRuntime` + `HlfVM` instance
   - Agents communicate via `multiprocessing.Queue` or ZeroMQ

2. **Swarm orchestrator rewrite** (`swarm_orchestrator.py`):
   - `spawn(agent_def)` → starts `AgentProcess`
   - `send(agent_id, msg)` → enqueues message
   - `receive(agent_id)` → dequeues message
   - `run_swarm(swarm_def)` → parses `swarm_stmt`, spawns agents, monitors health

3. **Lifecycle management**:
   - Health heartbeat from each agent
   - Auto-restart on crash (configurable)
   - Graceful shutdown with `SPEC_HALT`

### Phase 3: Distributed Consensus — ~2 weeks
**Goal:** Make `⨝ [VOTE]` a real protocol.

1. **Consensus engine**:
   - Implement Raft or simple majority vote over message bus
   - `VOTE_PROPOSE`, `VOTE_COMMIT`, `VOTE_ABORT` opcodes
   - Timeout and deadlock detection

2. **Integrate with swarm orchestrator**:
   - Swarm phases: `propose` → `vote` → `commit`/`abort`
   - HLF syntax: `consensus "majority" quorum=5 { ... }`

### Phase 4: Parallel VM Execution — ~2 weeks
**Goal:** Make `PARALLEL` blocks actually parallel.

1. **Thread pool executor** in `HlfVM`:
   - `PARALLEL_BEGIN` / `PARALLEL_END` opcodes
   - Sub-bytecode blocks dispatched to `concurrent.futures.ThreadPoolExecutor`
   - Shared memory context via `multiprocessing.Manager().dict()`
   - Gas metering aggregated across threads

2. **Safety**:
   - Immutable SET bindings are naturally thread-safe
   - Mutable locals need per-thread isolation or locking

### Phase 5: Tool Server Integration — ~1 week
**Goal:** Make `OPENCLAW_TOOL` and `CALL_TOOL` talk to external services.

1. **MCP client integration**:
   - `CALL_TOOL` resolves tool name to MCP server endpoint
   - HTTP/gRPC transport with timeout
   - Result deserialization back to VM stack

2. **Plugin registry**:
   - JSON manifest for tool capabilities
   - Dynamic loading without restarting VM

### Phase 6: Hardening & Observability — ~2 weeks
**Goal:** Production-ready swarm execution.

1. **Fix host dispatch duality**:
   - Merge `_dispatch_builtin` and `_dispatch_host` into a single dispatch path
   - Ensure all security layers (tier, side-effect, PII) are always applied

2. **Observability**:
   - Structured logging (OpenTelemetry spans)
   - Metrics: gas used per agent, message latency, consensus rounds
   - Dashboard for swarm health

3. **Security hardening**:
   - Sandbox agent processes (seccomp, gVisor, or Windows Job Objects)
   - Network policy: agents can only talk to orchestrator + designated peers
   - Secret injection via environment variables (not HLF source)

**Total estimated effort: ~12 weeks (3 months) with 1 senior engineer.**

---

## 11. Immediate Next Steps (If User Wants to Start)

1. **Decide agent process model:** `multiprocessing`, `asyncio`, containers, or WASM?
2. **Design message protocol:** Python `pickle`, JSON, protobuf, or Cap'n Proto?
3. **Approve grammar extensions:** Review proposed `agent`/`swarm` syntax
4. **Fix `spawn_agent` host function:** Make it actually spawn a process (even if just a dummy subprocess for now)
5. **Fix host dispatch duality:** Merge `_dispatch_builtin` and `_dispatch_host` to prevent divergence
6. **Write `swarm.hlf` example:** Draft the first real swarm program once grammar is extended

---

## 12. Appendix: File Inventory

| File | Lines | Role | Status |
|------|-------|------|--------|
| `hlf_mcp/hlf/compiler.py` | ~900 | 5-pass compiler | ✅ Real |
| `hlf_mcp/hlf/grammar.py` | ~80 | Lark grammar v3 | ✅ Real |
| `hlf_mcp/hlf/bytecode.py` | ~700 | Encoder/decoder/disassembler | ✅ Real |
| `hlf_mcp/hlf/runtime.py` | ~1900 | VM + HLFRuntime + host dispatch | ✅ Real (caveats noted) |
| `hlf_mcp/hlf/codegen.py` | ~400 | Programmatic HLF builder | ✅ Real |
| `hlf_mcp/hlf/swarm_orchestrator.py` | ~350 | Swarm simulation | ⚠️ Simulation only |
| `hlf_mcp/server_swarm.py` | ~150 | MCP server shim | ⚠️ Delegates to simulation |
| `hlf_mcp/hlf/stdlib/io_mod.py` | ~70 | File IO with ACFS | ✅ Real |
| `hlf_mcp/hlf/ethics/governor.py` | ~200 | Ethics checks | ✅ Real |
| `tests/test_compiler.py` | ~400 | Compiler tests | ✅ 21/21 pass |
| `tests/test_codegen.py` | ~150 | Codegen tests | ✅ 4/4 pass |
| `tests/test_bytecode_roundtrip.py` | ~80 | Bytecode tests | ✅ 1/1 pass |
| `tests/test_runtime_memory_context.py` | ~120 | Runtime tests | ✅ 5/5 pass |
| `scripts/test_live_execution.py` | ~80 | E2E probe | ⚠️ Exposed argument arity bug |

---

*End of audit report.*
