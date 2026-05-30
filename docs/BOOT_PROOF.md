# Boot Path Proof: HLF_MCP Without DSL/VM/Compiler Stack

Generated: 2026-05-23

## 1. Current Boot Path Analysis

### The Chain of Eager Imports

```
python -m hlf_mcp.server
  │
  ├─ server.py:29         from mcp.server.fastmcp import FastMCP
  ├─ server.py:32–52      16 module-level imports from hlf_mcp.*
  ├─ server.py:72         _ctx = build_server_context()   ← THE ROOT CAUSE
  │
  └─ server_context.py (module level, lines 1–61):
       ├─ line 23:  from hlf_mcp.hlf.compiler import HLFCompiler
       ├─ line 47:  from hlf_mcp.hlf.runtime import HLFRuntime
       ├─ line 22:  from hlf_mcp.hlf.bytecode import HLFBytecode
       ├─ line 25:  from hlf_mcp.hlf.formal_verifier import FormalVerifier
       ├─ line 44:  from hlf_mcp.hlf.linter import HLFLinter
       ├─ line 26:  from hlf_mcp.hlf.formatter import HLFFormatter
       ├─ line 21:  from hlf_mcp.hlf.benchmark import HLFBenchmark
       └─ +35 more imports from hlf_mcp.hlf.*, hlf_mcp.instinct.*,
          hlf_mcp.rag.*, hlf_mcp.*

  └─ hlf_mcp/__init__.py (module level):
       └─ line 5:   from hlf_mcp.hlf import (
                      HLFCompiler, HLFRuntime, HLFBytecode, HLFFormatter,
                      HLFLinter, HLFBenchmark, HLFCodeGenerator, Tone,
                      +all translator functions
                    )

  └─ hlf_mcp/hlf/__init__.py (module level, ~260 lines):
       ├─ line 14:  from hlf_mcp.hlf.benchmark import HLFBenchmark
       ├─ line 15:  from hlf_mcp.hlf.bytecode import HLFBytecode
       ├─ line 24:  from hlf_mcp.hlf.compiler import HLFCompiler
       ├─ line 39:  from hlf_mcp.hlf.formatter import HLFFormatter
       ├─ line 40:  from hlf_mcp.hlf.linter import HLFLinter
       ├─ line 60:  from hlf_mcp.hlf.runtime import HLFRuntime
       ├─ line 224: from hlf_mcp.hlf.formal_verifier import FormalVerifier
       └─ +30 more import blocks (authority, codegen, routing, knowledge,
          entropy_anchor, audit_trail, trust_surface, symbolic_surfaces, …)
```

**Result:** Any `import hlf_mcp` — even from a "clean" module like `server_governance.py` — triggers the entire DSL/VM/compiler stack into `sys.modules`.

### build_server_context() — The Root Cause

`server_context.py:3420`:

```python
def build_server_context() -> ServerContext:
    align_governor = AlignGovernor()
    return ServerContext(
        compiler=HLFCompiler(),           # ← DSL
        formatter=HLFFormatter(),         # ← DSL
        linter=HLFLinter(),               # ← DSL
        runtime=HLFRuntime(),              # ← DSL
        bytecoder=HLFBytecode(),          # ← DSL
        benchmark=HLFBenchmark(),         # ← DSL
        formal_verifier=FormalVerifier(),  # ← DSL
        memory_store=RAGMemory(...),
        instinct_mgr=InstinctLifecycle(),
        host_registry=HostFunctionRegistry(),
        tool_registry=ToolRegistry(),
        align_governor=align_governor,    # ← governance
        ingress_controller=GovernedIngressController(...),  # ← governance
        witness_governance=WitnessGovernance(), # ← governance
        approval_ledger=ApprovalLedger(),       # ← governance
        audit_chain=AuditChain(),               # ← governance
        daemon_manager=DaemonManager(),         # ← governance
        ...
    )
```

7 of the 18 fields instantiated here are DSL-dependent. But `build_server_context()` is called at **module level** in `server.py` line 72 — there is no conditional path.

---

## 2. DSL-Dependent vs DSL-Free Tool Modules

| Module | Uses compiler/runtime/bytecode/benchmark/verifier? | DSL-Free? |
|--------|---------------------------------------------------|-----------|
| `server_core.py` | ✅ Heavy — compile, format, lint, run, benchmark | ❌ |
| `server_translation.py` | ✅ Heavy — compile, bytecode, run, benchmark | ❌ |
| `server_native.py` | ✅ Imports HLFCompiler, HlfVM | ❌ |
| `server_capsule.py` | ✅ compile, formal_verifier, bytecode, runtime | ❌ |
| `server_verifier.py` | ✅ compile, formal_verifier | ❌ |
| `server_resources.py` | ✅ compiler, formal_verifier | ❌ |
| `server_workflow_benchmark.py` | Uses `_ctx.benchmark` indirectly | ⚠️ |
| `server_governance.py` | ❌ None | ✅ |
| `server_memory.py` | ❌ None | ✅ |
| `server_handoff.py` | ❌ None | ✅ |
| `server_feedback.py` | ❌ None | ✅ |
| `server_profiles.py` | ❌ None | ✅ |
| `server_instinct.py` | ❌ None | ✅ |
| `server_completion.py` | ❌ None | ✅ |
| `server_prompts.py` | ❌ None | ✅ |
| `server_enterprise.py` | ❌ None | ✅ |
| `server_auth.py` | ❌ None | ✅ |

**6 of 16 tool modules** require the DSL stack. **10 of 16** operate purely on governance primitives.

---

## 3. What SWARMGLASS_HLF_ENABLED=0 Boot Looks Like

### Available Tools (Experimental Disabled)

| Tool | Module | Function |
|------|--------|----------|
| `hlf_governance_event_log` | server_governance | Read governance event history |
| `hlf_governance_recent_events` | server_governance | Filtered event queries |
| `hlf_governance_status` | server_governance | Governance health snapshot |
| `hlf_memory_recall` | server_memory | Governed HKS memory recall |
| `hlf_memory_store` | server_memory | Write to governed memory |
| `hlf_memory_governance` | server_memory | Revoke/tombstone/reinstate |
| `hlf_handoff_create` | server_handoff | Agent-to-agent handoff |
| `hlf_handoff_verify` | server_handoff | Chain verification |
| `hlf_profile_*` | server_profiles | Profile management |
| `hlf_feedback_*` | server_feedback | Feedback loop |
| `hlf_completion_*` | server_completion | Completion tools |
| `hlf_prompt_*` | server_prompts | Agent prompts |
| `hlf_enterprise_*` | server_enterprise | Enterprise features |
| `hlf_auth_*` | server_auth | Auth middleware |
| `hlf_instinct_*` | server_instinct | Instinct lifecycle |

### Unavailable Tools (Require DSL)

| Tool | What's Missing |
|------|---------------|
| `hlf_compile` | Needs HLFCompiler |
| `hlf_format` | Needs HLFFormatter |
| `hlf_lint` | Needs HLFLinter |
| `hlf_run` | Needs HLFRuntime |
| `hlf_bytecode_*` | Needs HLFBytecode |
| `hlf_verify` | Needs FormalVerifier |
| `hlf_benchmark_*` | Needs HLFBenchmark |
| `hlf_translate_*` | Needs compiler + translator |
| `hlf_capsule_*` | Needs compiler + verifier |
| `hlf_entropy_anchor` | Needs compiler |

---

## 4. Concrete Refactoring Plan

### 4a. Fix `hlf_mcp/hlf/__init__.py` — Convert to Lazy Imports

**Current:** ~260 lines of eager module-level imports pulling in the entire DSL.

**Fix:** Replace with `__getattr__` lazy loading:

```python
"""Canonical public HLF surface — lazy-loaded."""
# Only keep stdlib/lightweight imports at module level
# Move ALL hlf_mcp.hlf.* imports behind __getattr__

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "HLFCompiler": ("hlf_mcp.hlf.compiler", "HLFCompiler"),
    "HLFRuntime": ("hlf_mcp.hlf.runtime", "HLFRuntime"),
    "HLFBytecode": ("hlf_mcp.hlf.bytecode", "HLFBytecode"),
    "HLFFormatter": ("hlf_mcp.hlf.formatter", "HLFFormatter"),
    "HLFLinter": ("hlf_mcp.hlf.linter", "HLFLinter"),
    "HLFBenchmark": ("hlf_mcp.hlf.benchmark", "HLFBenchmark"),
    "FormalVerifier": ("hlf_mcp.hlf.formal_verifier", "FormalVerifier"),
    # ... all other exports
}

def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        mod_path, attr = _LAZY_ATTRS[name]
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError(f"module 'hlf_mcp.hlf' has no attribute '{name}'")
```

### 4b. Fix `hlf_mcp/__init__.py` — Remove Eager DSL Re-Exports

**Current:** `from hlf_mcp.hlf import (HLFCompiler, HLFRuntime, ...)` at module level.

**Fix:** Replace with `__getattr__` proxy to `hlf_mcp.hlf` (which is now lazy):

```python
"""HLF MCP package."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hlf-mcp")
except PackageNotFoundError:
    __version__ = "0.5.0"

def __getattr__(name: str):
    import hlf_mcp.hlf as _hlf
    return getattr(_hlf, name)
```

### 4c. Split `ServerContext` — Core vs DSL

**New file: `hlf_mcp/server_context_core.py`** — zero DSL imports:

```python
"""Core context — governance primitives only. No DSL dependency."""
from dataclasses import dataclass, field
from collections import deque
from typing import Any

from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.approval_ledger import ApprovalLedger
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.daemon_manager import DaemonManager
from hlf_mcp.hlf.governed_ingress import GovernedIngressController
from hlf_mcp.hlf.witness_governance import WitnessGovernance, WitnessObservation
from hlf_mcp.hlf.registry import HostFunctionRegistry
from hlf_mcp.hlf.tool_dispatch import ToolRegistry
from hlf_mcp.hlf.intent_normalizer import IntentNormalizer
from hlf_mcp.instinct.lifecycle import InstinctLifecycle
from hlf_mcp.rag.memory import RAGMemory

@dataclass
class CoreContext:
    """Governance spine — no DSL/VM/compiler dependency."""
    memory_store: RAGMemory
    instinct_mgr: InstinctLifecycle
    host_registry: HostFunctionRegistry
    tool_registry: ToolRegistry
    align_governor: AlignGovernor
    ingress_controller: GovernedIngressController
    witness_governance: WitnessGovernance
    approval_ledger: ApprovalLedger
    audit_chain: AuditChain
    daemon_manager: DaemonManager
    intent_normalizer: IntentNormalizer = field(default_factory=IntentNormalizer)
    governance_events: deque = field(default_factory=lambda: deque(maxlen=250))
    handoff_events: deque = field(default_factory=lambda: deque(maxlen=1000))
    # ... session dicts ...
```

**Modified: `server_context.py`** — `ServerContext` extends `CoreContext`:

```python
@dataclass
class ServerContext(CoreContext):
    """Full context including DSL/VM when SWARMGLASS_HLF_ENABLED=1."""
    compiler: Any = None       # HLFCompiler — only when experimental
    formatter: Any = None
    linter: Any = None
    runtime: Any = None
    bytecoder: Any = None
    benchmark: Any = None
    formal_verifier: Any = None
```

### 4d. Conditional `build_server_context()`

```python
def build_server_context() -> ServerContext:
    """Build context. DSL components only when SWARMGLASS_HLF_ENABLED=1."""
    align_governor = AlignGovernor()
    
    ctx = ServerContext(
        # Governance core (always)
        memory_store=RAGMemory(_resolve_memory_db_path(), embed_fn=_build_ollama_embed_fn()),
        instinct_mgr=InstinctLifecycle(),
        host_registry=HostFunctionRegistry(),
        tool_registry=ToolRegistry(),
        align_governor=align_governor,
        ingress_controller=GovernedIngressController(align_governor=align_governor),
        witness_governance=WitnessGovernance(),
        approval_ledger=ApprovalLedger(),
        audit_chain=AuditChain(),
        daemon_manager=DaemonManager(),
        # ... session dicts ...
    )
    
    if os.environ.get("SWARMGLASS_HLF_ENABLED", "0") == "1":
        # Lazy — only imports DSL when explicitly enabled
        from hlf_mcp.hlf.compiler import HLFCompiler
        from hlf_mcp.hlf.runtime import HLFRuntime
        from hlf_mcp.hlf.bytecode import HLFBytecode
        from hlf_mcp.hlf.formatter import HLFFormatter
        from hlf_mcp.hlf.linter import HLFLinter
        from hlf_mcp.hlf.benchmark import HLFBenchmark
        from hlf_mcp.hlf.formal_verifier import FormalVerifier
        
        ctx.compiler = HLFCompiler()
        ctx.formatter = HLFFormatter()
        ctx.linter = HLFLinter()
        ctx.runtime = HLFRuntime()
        ctx.bytecoder = HLFBytecode()
        ctx.benchmark = HLFBenchmark()
        ctx.formal_verifier = FormalVerifier()
    
    return ctx
```

### 4e. Conditional Tool Registration in `server.py`

```python
# Always register governance tools
REGISTERED_TOOLS.update(register_governance_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_memory_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_handoff_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_feedback_tools(mcp))
REGISTERED_TOOLS.update(register_profile_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_instinct_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_completion_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_prompts_tools(mcp))
REGISTERED_TOOLS.update(register_enterprise_tools(mcp, _ctx))

# DSL-dependent tools — only when experimental
if os.environ.get("SWARMGLASS_HLF_ENABLED", "0") == "1":
    REGISTERED_TOOLS.update(register_core_tools(mcp, _ctx))
    REGISTERED_TOOLS.update(register_translation_tools(mcp, _ctx))
    REGISTERED_TOOLS.update(register_verifier_tools(mcp, _ctx))
    REGISTERED_TOOLS.update(register_capsule_tools(mcp, _ctx))
    REGISTERED_TOOLS.update(register_native_tools(mcp, _ctx))
    REGISTERED_TOOLS.update(register_workflow_benchmark_tools(mcp))
```

---

## 5. Feasibility Assessment

### Within Phase 2 Scope

| Change | Files Affected | Risk | Effort |
|--------|---------------|------|--------|
| `hlf_mcp/hlf/__init__.py` → `__getattr__` | 1 file | Low — pattern already exists for `_get_checkpoint_types()` at line 148 | ~30 min |
| `hlf_mcp/__init__.py` → `__getattr__` | 1 file | Low — just a proxy | ~10 min |
| `server_context.py` → lazy DSL in `build_server_context()` | 1 file | Medium — must preserve all existing behavior when EXPERIMENTAL=1 | ~1 hr |
| `server.py` → conditional tool registration | 1 file | Low — additive gate | ~20 min |
| `ServerContext` → field defaults `= None` | 1 file | Medium — 6 fields become Optional; all consumers in DSL modules need null checks | ~1 hr |

**Total:** ~3 hours of surgical work. **Feasible within Phase 2.**

### What Needs Phase 3 Restructuring

- **`server_context.py` module-level imports.** The 42+ imports at lines 1–61 still execute at import time even if `build_server_context()` is conditional. Moving them ALL to lazy would require restructuring the helper functions (`_build_hks_evaluation_snapshot`, `_parse_hks_timestamp`, etc.) that use these imports. This is Phase 3 work.
- **`hlf_mcp/hlf/__init__.py` full migration.** Converting ~260 lines of imports to `__getattr__` entries. Tedious but mechanical.
- **Type stubs for IDE support.** The `Any` fallback types on compiler/runtime/etc. would need proper `TYPE_CHECKING` guards.

### Minimal Viable Phase 2 Fix

The **smallest change** that enables `SWARMGLASS_HLF_ENABLED=0` boot is:

1. Make `build_server_context()` conditional (server_context.py line 3420)
2. Make tool registration conditional (server.py lines 97–112)
3. Change `ServerContext` DSL fields to have `= None` defaults

This is ~20 lines of changes in 2 files. The `hlf/__init__.py` and `hlf_mcp/__init__.py` lazy-loading can follow in Phase 3.

---

## 6. Verification

### Proof Script Results (2026-05-23)

Run: `python docs/boot_proof_test.py`

```
Part A  — ServerContext import: 10 DSL modules leaked       ✗ FAIL (current state)
Part B  — Single gov submodule:  10 DSL modules leaked       ✗ FAIL (package init pollution)
Part B2 — AST source analysis:   12 clean, 0 with DSL        ✓ PASS
Part C  — Instantiation:         11/11 passed                ✓ PASS
Part D  — DSL in sys.modules:    10/10 present               ✗ FAIL (current state)
```

**Key findings:**

1. **Part A** — `from hlf_mcp.server_context import ServerContext` pulls in all 10 DSL modules (compiler, runtime, bytecode, formatter, linter, benchmark, formal_verifier, codegen, grammar, translator) plus 48 other hlf_mcp submodules.

2. **Part B** — Even a single governance import like `from hlf_mcp.hlf.align_governor import AlignGovernor` triggers 64 modules into sys.modules because Python's package system loads `hlf_mcp/__init__.py` → `hlf_mcp/hlf/__init__.py` first.

3. **Part B2** — AST static analysis proves all 12 governance source files are DSL-free at the source level. None import from compiler, runtime, bytecode, formatter, linter, benchmark, formal_verifier, codegen, grammar, or translator. The pollution comes **ONLY from package `__init__.py` files**.

4. **Part C** — All 11 governance objects instantiate successfully: AlignGovernor, AuditChain, ApprovalLedger, WitnessGovernance, DaemonManager, HostFunctionRegistry, ToolRegistry, IntentNormalizer, GovernedIngressController, build_governance_proof, sha256_digest.

5. **Part D** — Confirms 10/10 DSL modules are in sys.modules after the governance imports (current state — these would NOT be present after the refactoring).
