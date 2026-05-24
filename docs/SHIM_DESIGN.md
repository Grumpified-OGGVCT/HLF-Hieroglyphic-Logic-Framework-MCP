# SwarmGlass Compatibility Shim Design

> **Status:** Phase 2 design — pending Gate 1 approval
> **Principle:** Additive only. No breaking changes. Old names work throughout migration.

---

## 1. Tool Name Mapping Table

### 1.1 Governance Tools → Get `sg_` Aliases (Phase 2)

These tools receive both `hlf_*` (deprecation warning) and `sg_*` (preferred) names.

#### Observe (`sg_observe_*`)

| hlf_ name | sg_ name | Server file | Notes |
|-----------|----------|-------------|-------|
| `hlf_resource_report` | `sg_observe_resources` | server_core.py:726 | CPU/RAM/GPU telemetry |
| `hlf_probe_local_hardware` | `sg_observe_hardware` | server_profiles.py:1005 | HW capability probe |
| `hlf_swarm_progress` | `sg_observe_swarm` | server_swarm.py:122 | Swarm task progress |
| `hlf_tool_list` | `sg_observe_tools` | server_capsule.py:1405 | Registered tool listing |
| `hlf_entropy_anchor` | `sg_observe_drift` | server.py:116 | Semantic drift detection |
| `hlf_feedback_submit` | `sg_observe_feedback_submit` | server_feedback.py:53 | User feedback |
| `hlf_feedback_list` | `sg_observe_feedback_list` | server_feedback.py:104 | Feedback listing |
| `hlf_feedback_view` | `sg_observe_feedback_view` | server_feedback.py:129 | Feedback detail |

#### Validate (`sg_validate_*`)

| hlf_ name | sg_ name | Server file | Notes |
|-----------|----------|-------------|-------|
| `hlf_validate_output` | `sg_validate_output` | server_native.py:78 | NL output constraint check |
| `hlf_capsule_validate` | `sg_validate_capsule` | server_capsule.py:557 | Capsule integrity |
| `hlf_pointer_validate` | `sg_validate_pointer` | server_capsule.py:988 | Memory pointer validation |
| `hlf_similarity_gate` | `sg_validate_similarity` | server_capsule.py:1414 | Semantic similarity gate |
| `hlf_swarm_verify` | `sg_validate_swarm` | server_swarm.py:182 | Swarm output verification |
| `hlf_align_check` | `sg_validate_alignment` | server_profiles.py:1199 | Constitutional alignment |
| `hlf_governance_proof_verify` | `sg_validate_proof` | server_core.py:500 | Governance proof check |

#### Audit (`sg_audit_*`)

| hlf_ name | sg_ name | Server file | Notes |
|-----------|----------|-------------|-------|
| `hlf_governance_event_log` | `sg_audit_event_log` | server_governance.py:14 | Log governance event |
| `hlf_governance_event_log_verify` | `sg_audit_event_log_verify` | server_governance.py:64 | Verify log integrity |
| `hlf_governance_event_log_get` | `sg_audit_event_log_get` | server_governance.py:71 | Retrieve log entry |
| `hlf_evidence_show` | `sg_audit_evidence_show` | server_enterprise.py:108 | Show evidence capsule |
| `hlf_evidence_list` | `sg_audit_evidence_list` | server_enterprise.py:145 | List evidence capsules |
| `hlf_evidence_verify` | `sg_audit_evidence_verify` | server_enterprise.py:186 | Verify evidence integrity |
| `hlf_merkle_export` | `sg_audit_merkle_export` | server_enterprise.py:262 | Export Merkle backup |
| `hlf_merkle_verify` | `sg_audit_merkle_verify` | server_enterprise.py:306 | Verify Merkle backup |
| `hlf_merkle_chain_status` | `sg_audit_merkle_chain_status` | server_enterprise.py:337 | Merkle chain health |
| `hlf_witness_record` | `sg_audit_witness_record` | server_memory.py:978 | Record witness observation |
| `hlf_witness_status` | `sg_audit_witness_status` | server_memory.py:1011 | Witness trust status |
| `hlf_witness_list` | `sg_audit_witness_list` | server_memory.py:1019 | List witness records |
| `hlf_hitl_list_pending` | `sg_audit_hitl_list` | server_core.py:748 | HITL pending queue |
| `hlf_hitl_approve` | `sg_audit_hitl_approve` | server_core.py:766 | Approve HITL gate |
| `hlf_hitl_reject` | `sg_audit_hitl_reject` | server_core.py:804 | Reject HITL gate |
| `hlf_hitl_status` | `sg_audit_hitl_status` | server_core.py:836 | HITL gate status |
| `hlf_capsule_review_queue` | `sg_audit_review_queue` | server_capsule.py:1338 | Review queue |
| `hlf_capsule_review_decide` | `sg_audit_review_decide` | server_capsule.py:1359 | Review decision |
| `hlf_weekly_evidence_summary` | `sg_audit_weekly_summary` | server_core.py:510 | Weekly evidence rollup |
| `hlf_swarm_witness` | `sg_audit_swarm_witness` | server_swarm.py:153 | Swarm agent witness |

#### Secure (`sg_secure_*`)

| hlf_ name | sg_ name | Server file | Notes |
|-----------|----------|-------------|-------|
| `hlf_secret_store` | `sg_secure_secret_store` | server_enterprise.py:398 | AES-256-GCM encrypt+store |
| `hlf_secret_retrieve` | `sg_secure_secret_retrieve` | server_enterprise.py:432 | Retrieve+decrypt secret |
| `hlf_secret_rotate` | `sg_secure_secret_rotate` | server_enterprise.py:473 | Rotate encryption key |
| `hlf_code_execute` | `sg_secure_sandbox` | server_native.py:115 | Gas-metered sandbox exec |

### 1.2 Runtime Tools → Get `sg_` Aliases (Phase 3)

These ship second, after core governance. Get aliases with a slightly lower deprecation urgency.

#### Coordinate (`sg_coordinate_*`)

| hlf_ name | sg_ name | Server file |
|-----------|----------|-------------|
| `hlf_record_handoff_event` | `sg_coordinate_handoff_record` | server_handoff.py:64 |
| `hlf_handoff_chain` | `sg_coordinate_handoff_chain` | server_handoff.py:140 |
| `hlf_orchestration_contract` | `sg_coordinate_orchestration_contract` | server_handoff.py:171 |
| `hlf_handoff_contract_template` | `sg_coordinate_contract_template` | server_handoff.py:212 |
| `hlf_handoff_semantic_drift_check` | `sg_coordinate_drift_check` | server_handoff.py:235 |
| `hlf_swarm_run` | `sg_coordinate_swarm_run` | server_swarm.py:69 |
| `hlf_governed_swarm_mechanics` | `sg_coordinate_swarm_mechanics` | server_translation.py:1023 |
| `hlf_route_governed_request` | `sg_coordinate_route` | server_profiles.py:1272 |
| `hlf_instinct_step` | `sg_coordinate_instinct_step` | server_instinct.py:13 |
| `hlf_instinct_get` | `sg_coordinate_instinct_get` | server_instinct.py:30 |
| `hlf_instinct_realign` | `sg_coordinate_instinct_realign` | server_instinct.py:74 |
| `hlf_instinct_list` | `sg_coordinate_instinct_list` | server_instinct.py:93 |
| `hlf_spec_lifecycle` | `sg_coordinate_lifecycle` | server_instinct.py:40 |
| `hlf_native_speak` | `sg_coordinate_native_speak` | server_native.py:32 |

#### Memory (`sg_memory_*`)

| hlf_ name | sg_ name | Server file |
|-----------|----------|-------------|
| `hlf_memory_store` | `sg_memory_store` | server_memory.py:370 |
| `hlf_memory_query` | `sg_memory_query` | server_memory.py:493 |
| `hlf_memory_stats` | `sg_memory_stats` | server_memory.py:905 |
| `hlf_memory_resolve` | `sg_memory_resolve` | server_memory.py:930 |
| `hlf_memory_govern` | `sg_memory_govern` | server_memory.py:952 |
| `hlf_memory_dedup_check` | `sg_memory_dedup` | server_memory.py:1273 |
| `hlf_memory_index_embeddings` | `sg_memory_index` | server_memory.py:1289 |
| `hlf_hks_capture` | `sg_memory_hks_capture` | server_memory.py:526 |
| `hlf_hks_recall` | `sg_memory_hks_recall` | server_memory.py:591 |
| `hlf_hks_external_compare` | `sg_memory_hks_compare` | server_memory.py:703 |
| `hlf_hks_weekly_refresh` | `sg_memory_hks_weekly` | server_memory.py:822 |
| `hlf_governed_recall` | `sg_memory_governed_recall` | server_memory.py:668 |
| `hlf_internal_governed_recall_workflow` | `sg_memory_governed_recall_workflow` | server_memory.py:833 |
| `hlf_knowledge_ingest` | `sg_memory_ingest` | server_memory.py:1111 |
| `hlf_knowledge_ingest_directory` | `sg_memory_ingest_dir` | server_memory.py:1160 |
| `hlf_knowledge_ingest_url` | `sg_memory_ingest_url` | server_memory.py:1194 |
| `hlf_dream_cycle_run` | `sg_memory_dream_run` | server_memory.py:1025 |
| `hlf_dream_findings_list` | `sg_memory_dream_findings` | server_memory.py:1040 |
| `hlf_dream_findings_get` | `sg_memory_dream_finding_get` | server_memory.py:1056 |
| `hlf_dream_proposal_create` | `sg_memory_dream_proposal` | server_memory.py:1077 |
| `hlf_dream_proposals_list` | `sg_memory_dream_proposals` | server_memory.py:1096 |
| `hlf_dream_proposals_get` | `sg_memory_dream_proposal_get` | server_memory.py:1101 |
| `hlf_media_evidence_list` | `sg_memory_media_list` | server_memory.py:1064 |
| `hlf_media_evidence_get` | `sg_memory_media_get` | server_memory.py:1069 |

#### Models (`sg_model_*`)

| hlf_ name | sg_ name | Server file |
|-----------|----------|-------------|
| `hlf_model_version_check` | `sg_model_version_check` | server_enterprise.py:1034 |
| `hlf_recommend_embedding_profile` | `sg_model_embed_profile` | server_profiles.py:1010 |
| `hlf_sync_model_catalog` | `sg_model_catalog_sync` | server_profiles.py:1130 |
| `hlf_query_profile_capabilities` | `sg_model_capabilities` | server_profiles.py:1179 |
| `hlf_get_embedding_profile` | `sg_model_embed_get` | server_profiles.py:1934 |
| `hlf_get_model_catalog` | `sg_model_catalog_get` | server_profiles.py:1945 |
| `hlf_get_model_catalog_status` | `sg_model_catalog_status` | server_profiles.py:1953 |
| `hlf_evaluate_model_against_profile` | `sg_model_evaluate` | server_profiles.py:1998 |
| `hlf_evaluate_model_requirements` | `sg_model_requirements` | server_profiles.py:2049 |
| `hlf_evaluate_model_requirement_tiers` | `sg_model_tiers` | server_profiles.py:2091 |

#### Overwatch (`sg_overwatch_*`)

| hlf_ name | sg_ name | Server file | Notes |
|-----------|----------|-------------|-------|
| `hlf_overwatch_scan` | `sg_overwatch_scan` | server_overwatch.py:62 | DONE |
| `hlf_overwatch_terminate` | `sg_overwatch_terminate` | server_overwatch.py:79 | DONE |
| `hlf_overwatch_status` | `sg_overwatch_status` | server_overwatch.py:97 | DONE |

### 1.3 Experimental DSL Tools → `hlf_` Only (Phase 4, gated)

These tools keep their `hlf_*` names and are ONLY registered when `SWARMGLASS_EXPERIMENTAL=1`. No `sg_` aliases.

| hlf_ name | Category | Server file |
|-----------|----------|-------------|
| `hlf_compile` | DSL compiler | server_core.py:118 |
| `hlf_format` | DSL formatter | server_core.py:157 |
| `hlf_lint` | DSL linter | server_core.py:167 |
| `hlf_run` | DSL runner | server_core.py:179 |
| `hlf_validate` | HLF source validation | server_core.py:315 |
| `hlf_swarm_mechanics` | HLF swarm artifact | server_core.py:320 |
| `hlf_disassemble` | Bytecode disassembly | server_core.py:382 |
| `hlf_submit_ast` | AST submission | server_core.py:392 |
| `hlf_compile_wasm` | WASM compilation | server_core.py:520 |
| `hlf_capture_symbolic_surface` | Symbolic surface | server_core.py:457 |
| `hlf_test_suite_summary` | Test suite | server_core.py:449 |
| `hlf_capsule_run` | Capsule executor | server_capsule.py:666 |
| `hlf_host_functions` | Host function registry | server_capsule.py:1005 |
| `hlf_host_call` | Host function call | server_capsule.py:1014 |
| `hlf_translate_to_hlf` | NL→HLF translation | server_translation.py:807 |
| `hlf_translate_to_english` | HLF→English translation | server_translation.py:1461 |
| `hlf_translate_repair` | Translation repair | server_translation.py:1166 |
| `hlf_translate_resilient` | Resilient translation | server_translation.py:1233 |
| `hlf_decompile_ast` | AST decompilation | server_translation.py:1481 |
| `hlf_decompile_bytecode` | Bytecode decompilation | server_translation.py:1506 |
| `hlf_do` | Translation executor | server_translation.py:692 |
| `hlf_governed_complete` | Governed NL completion | server_completion.py:34 |
| `hlf_latent_recursive_infer` | Recursive MAS | server_core.py:650 |
| `hlf_verify_formal_ast` | Formal verification | server_verifier.py:154 |
| `hlf_verify_gas_budget` | Gas budget verification | server_verifier.py:285 |
| `hlf_benchmark` | Benchmark | server_core.py:342 |
| `hlf_benchmark_suite` | Benchmark suite | server_core.py:349 |
| `hlf_real_workflow_benchmark` | Workflow benchmark | server_core.py:354 |
| `hlf_record_benchmark_artifact` | Benchmark artifact | server_profiles.py:1961 |
| `hlf_get_benchmark_artifact` | Benchmark artifact get | server_profiles.py:1990 |
| `hlf_workflow_benchmark` | Workflow benchmark | server_workflow_benchmark.py:15 |
| `hlf_workflow_benchmark_custom_task` | Workflow benchmark custom | server_workflow_benchmark.py:22 |
| `hlf_benchmark_matrix` | Translation benchmark | server_translation.py:729 |
| `hlf_translation_memory_benchmark` | TM benchmark | server_translation.py:737 |
| `hlf_translation_memory_query` | TM query | server_translation.py:793 |
| `hlf_routing_context_benchmark` | Routing benchmark | server_translation.py:765 |
| `hlf_ab_test_define` | A/B test define | server_enterprise.py:526 |
| `hlf_ab_test_run` | A/B test run | server_enterprise.py:579 |
| `hlf_ab_test_show` | A/B test show | server_enterprise.py:677 |
| `hlf_ab_test_list` | A/B test list | server_enterprise.py:730 |
| `hlf_load_test_run` | Load test run | server_enterprise.py:781 |
| `hlf_load_test_status` | Load test status | server_enterprise.py:844 |
| `hlf_chaos_status` | Chaos engineering | server_enterprise.py:1085 |

### 1.4 Prompt Tools → Get `sg_` Aliases

| hlf_ name | sg_ name | Server file |
|-----------|----------|-------------|
| `hlf_native_agent` | `sg_prompt_native_agent` | server_prompts.py:13 |
| `hlf_onboarding` | `sg_prompt_onboarding` | server_prompts.py:28 |
| `hlf_swarm_agent` | `sg_prompt_swarm_agent` | server_prompts.py:83 |
| `hlf_feedback_guide` | `sg_prompt_feedback` | server_prompts.py:136 |

---

## 2. Package Structure

```
HLF_MCP/                          # repo root (renamed to SwarmGlass post-Phase 4)
│
├── hlf_mcp/                      # OLD namespace (frozen, deprecation shims only)
│   ├── __init__.py               # REFACTORED: lazy imports only (see §3)
│   ├── server.py                 # REFACTORED: loads both hlf_ + sg_ registrations
│   ├── server_context.py         # REFACTORED: CoreContext (no DSL) + HlfContext (gated)
│   ├── server_core.py            # SPLIT: governance tools → sg_*; DSL tools gated
│   ├── server_governance.py      # ALIASED: sg_ wrappers added
│   ├── server_memory.py          # ALIASED: sg_ wrappers added
│   ├── server_enterprise.py      # ALIASED: sg_ wrappers added
│   ├── ...                       # All other server_*.py: aliases added where needed
│   ├── hlf/                      # DSL/VM code (unchanged, experimental-only)
│   │   ├── __init__.py           # UNCHANGED (but only loaded when experimental)
│   │   ├── compiler.py
│   │   ├── runtime.py
│   │   ├── bytecode.py
│   │   └── ...
│   ├── bridges/                  # Unchanged
│   ├── ecosystem/                # Unchanged
│   ├── rag/                      # Unchanged
│   └── instinct/                 # Unchanged
│
├── swarmglass/                   # NEW namespace (canonical, no DSL coupling)
│   ├── __init__.py               # Empty — triggers NO DSL imports
│   ├── _shim.py                  # Tool alias registry + deprecation warn (see §4)
│   ├── _env.py                   # SG_* env resolution with HLF_* fallback (see §5)
│   ├── core/                     # Layer 1: observe, validate, audit, secure
│   │   ├── __init__.py
│   │   ├── observe.py            # sg_observe_* tool functions
│   │   ├── validate.py           # sg_validate_* tool functions
│   │   ├── audit.py              # sg_audit_* tool functions
│   │   └── secure.py             # sg_secure_* tool functions
│   ├── runtime/                  # Layer 2: coordinate, memory, models
│   │   ├── __init__.py
│   │   ├── coordinate.py         # sg_coordinate_* tool functions
│   │   ├── memory.py             # sg_memory_* tool functions
│   │   └── models.py             # sg_model_* tool functions
│   └── experimental/             # Layer 3: gated behind SWARMGLASS_EXPERIMENTAL=1
│       ├── __init__.py           # Raises ImportError if env var not set
│       ├── dsl.py                # hlf_compile, hlf_format, hlf_lint, hlf_run, ...
│       ├── translation.py        # hlf_translate_to_hlf, hlf_translate_to_english, ...
│       ├── verification.py       # hlf_verify_formal_ast, hlf_verify_gas_budget
│       ├── benchmarking.py       # hlf_benchmark*, hlf_workflow_benchmark*, ...
│       └── testing.py            # hlf_ab_test_*, hlf_load_test_*, hlf_chaos_status
│
├── docs/
│   └── SHIM_DESIGN.md            # This file
└── tests/
    └── test_shim_migration.py    # NEW: verifies alias registration + deprecation
```

**Key property:** `import swarmglass` does NOT trigger `import hlf_mcp.hlf.compiler` or `import hlf_mcp.hlf.runtime`. The `swarmglass/` namespace is a sibling directory, not a sub-package of `hlf_mcp/`. Python's import system treats them as entirely separate packages.

---

## 3. Import Strategy: Lazy `hlf_mcp/__init__.py`

### 3.1 Problem

`hlf_mcp/__init__.py` currently does eager imports of `HLFCompiler`, `HLFRuntime`, `HLFBytecode`, `HLFFormatter`, `HLFLinter`, and 13 translator functions. This poisons **every** import path — even `from hlf_mcp.rag.memory import RAGMemory` triggers the DSL stack.

### 3.2 Solution: Deferred Attribute Access

Replace eager imports with `__getattr__`-based lazy loading:

```python
# hlf_mcp/__init__.py — AFTER refactor (Phase 2)
"""HLF MCP package — legacy namespace. Prefer `import swarmglass`."""

from importlib.metadata import PackageNotFoundError, version
import warnings

# ── No eager imports of DSL modules ──────────────────────────────────────────
# All heavyweight imports are deferred to __getattr__.

__all__ = [
    "__version__",
    "HLFBenchmark", "HLFBytecode", "HLFCodeGenerator",
    "HLFCompiler", "HLFFormatter", "HLFLinter", "HLFRuntime",
    "Tone", "TranslationRepairPlan",
    "build_translation_repair_plan", "canonicalize_translation_text",
    "chinese_to_hlf", "detect_input_language", "detect_system_language",
    "detect_tone", "english_to_hlf", "hlf_source_to_english",
    "hlf_source_to_language", "hlf_to_english", "hlf_to_language",
    "language_to_hlf", "resolve_language", "translation_diagnostics",
]

try:
    __version__ = version("hlf-mcp")
except PackageNotFoundError:
    __version__ = "0.5.0"


def __getattr__(name: str):
    """Lazy-import DSL/VM modules only when accessed by name."""
    if name == "HLFCompiler":
        from hlf_mcp.hlf.compiler import HLFCompiler
        return HLFCompiler
    if name == "HLFRuntime":
        from hlf_mcp.hlf.runtime import HLFRuntime
        return HLFRuntime
    if name == "HLFBytecode":
        from hlf_mcp.hlf.bytecode import HLFBytecode
        return HLFBytecode
    if name == "HLFFormatter":
        from hlf_mcp.hlf.formatter import HLFFormatter
        return HLFFormatter
    if name == "HLFLinter":
        from hlf_mcp.hlf.linter import HLFLinter
        return HLFLinter
    if name == "HLFBenchmark":
        from hlf_mcp.hlf.benchmark import HLFBenchmark
        return HLFBenchmark
    if name == "HLFCodeGenerator":
        from hlf_mcp.hlf.codegen import HLFCodeGenerator
        return HLFCodeGenerator

    # Translator symbols
    if name in {
        "Tone", "TranslationRepairPlan", "build_translation_repair_plan",
        "canonicalize_translation_text", "chinese_to_hlf",
        "detect_input_language", "detect_system_language", "detect_tone",
        "english_to_hlf", "hlf_source_to_english", "hlf_source_to_language",
        "hlf_to_english", "hlf_to_language", "language_to_hlf",
        "resolve_language", "translation_diagnostics",
    }:
        from hlf_mcp.hlf import translator as _t
        obj = getattr(_t, name, None)
        if obj is not None:
            return obj

    raise AttributeError(f"module 'hlf_mcp' has no attribute '{name}'")
```

**Effect after refactor:**
- `import hlf_mcp` → only `importlib.metadata` and `warnings` load. No DSL modules.
- `from hlf_mcp.rag.memory import RAGMemory` → no DSL modules (RAG memory never accesses `hlf_mcp.HLFCompiler`)
- `from hlf_mcp import HLFCompiler` → triggers lazy load of `hlf_mcp.hlf.compiler` only, not the whole stack

### 3.3 `server_context.py` Split

Refactor `build_server_context()` into two functions:

```python
# hlf_mcp/server_context.py — AFTER refactor

def build_core_context():
    """Governance-only context. Zero DSL imports."""
    from hlf_mcp.rag.memory import RAGMemory
    from hlf_mcp.hlf.governance_events import ...
    from hlf_mcp.hlf.governance_proofs import ...
    from hlf_mcp.hlf.audit_chain import AuditChain
    # ... governance/audit/memory only, NO compiler/runtime/bytecode
    return CoreContext(...)

def build_hlf_context(core_ctx: CoreContext):
    """Load the DSL stack on top of core. Requires SWARMGLASS_EXPERIMENTAL=1."""
    import os
    if os.environ.get("SWARMGLASS_EXPERIMENTAL") != "1":
        raise RuntimeError(
            "HLF DSL stack requires SWARMGLASS_EXPERIMENTAL=1. "
            "Use build_core_context() for governance-only boot."
        )
    from hlf_mcp.hlf.compiler import HLFCompiler
    from hlf_mcp.hlf.runtime import HLFRuntime
    from hlf_mcp.hlf.bytecode import HLFBytecode
    # ... DSL modules
    return HlfContext(core=core_ctx, compiler=..., runtime=..., ...)
```

---

## 4. Import Shim: Tool Alias + Deprecation Warning

### 4.1 `swarmglass/_shim.py`

This module provides the alias registration machinery used by all `register_*_tools()` functions:

```python
# swarmglass/_shim.py
"""Tool alias registry with deprecation warnings."""

from __future__ import annotations

import functools
import logging
import warnings
from typing import Any, Callable

_log = logging.getLogger(__name__)

# ── Public API ────────────────────────────────────────────────────────────────

def register_aliased(
    mcp: Any,
    *,
    hlf_name: str,
    sg_name: str,
    func: Callable[..., Any],
    description: str = "",
) -> None:
    """Register a tool under BOTH hlf_* (with deprecation) and sg_* names.

    Args:
        mcp: FastMCP instance
        hlf_name: Original hlf_ prefixed tool name
        sg_name: New sg_ prefixed tool name
        func: The actual implementation function
        description: Docstring override (uses func.__doc__ if empty)
    """
    desc = description or (func.__doc__ or "").strip()

    # 1. Register the canonical sg_ name (no warning)
    _register_sg(mcp, sg_name, func, desc)

    # 2. Register the deprecated hlf_ name (emits warning on every call)
    deprecated = _wrap_deprecated(func, hlf_name, sg_name)
    _register_hlf_deprecated(mcp, hlf_name, deprecated, desc)


def register_experimental_gated(
    mcp: Any,
    *,
    hlf_name: str,
    func: Callable[..., Any],
    description: str = "",
) -> None:
    """Register a tool under its hlf_* name ONLY if SWARMGLASS_EXPERIMENTAL=1.

    Used for DSL/VM tools that have no sg_ equivalent.
    """
    import os
    if os.environ.get("SWARMGLASS_EXPERIMENTAL") != "1":
        _log.debug("Skipping experimental tool %s (SWARMGLASS_EXPERIMENTAL != 1)", hlf_name)
        return
    desc = description or (func.__doc__ or "").strip()
    mcp.tool(name=hlf_name, description=desc)(func)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _register_sg(mcp: Any, name: str, func: Callable, desc: str) -> None:
    """Register the canonical sg_* tool."""
    mcp.tool(name=name, description=desc)(func)


def _register_hlf_deprecated(mcp: Any, name: str, func: Callable, desc: str) -> None:
    """Register the deprecated hlf_* tool (already wrapped with warning)."""
    # Prefix description with deprecation notice
    notice = (
        f"[DEPRECATED] Use the equivalent sg_* tool instead. "
        f"This alias will be removed in a future version."
    )
    full_desc = f"{notice}\n\n{desc}" if desc else notice
    mcp.tool(name=name, description=full_desc)(func)


def _wrap_deprecated(
    func: Callable[..., Any],
    old_name: str,
    new_name: str,
) -> Callable[..., Any]:
    """Wrap a function to emit DeprecationWarning on every call."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        warnings.warn(
            f"hlf_ tool '{old_name}' is deprecated. Use '{new_name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)

    return wrapper
```

### 4.2 Example Registration Site

Before (current code in `server_governance.py`):

```python
def register_governance_tools(mcp, ctx):
    @mcp.tool()
    def hlf_governance_event_log(...) -> dict[str, Any]:
        """Log a governance event to the immutable audit chain."""
        ...
```

After (Phase 2 refactor):

```python
from swarmglass._shim import register_aliased

def register_governance_tools(mcp, ctx):
    def _governance_event_log_impl(...) -> dict[str, Any]:
        """Log a governance event to the immutable audit chain."""
        ...

    register_aliased(
        mcp,
        hlf_name="hlf_governance_event_log",
        sg_name="sg_audit_event_log",
        func=_governance_event_log_impl,
    )
```

---

## 5. Environment Variable Migration

### 5.1 `swarmglass/_env.py`

```python
# swarmglass/_env.py
"""Environment variable resolution with HLF_* → SG_* fallback."""

from __future__ import annotations

import os
import logging
import warnings
from typing import Optional

_log = logging.getLogger(__name__)

_ENV_MAP: dict[str, str] = {
    "SG_TRANSPORT":          "HLF_TRANSPORT",
    "SG_HOST":               "HLF_HOST",
    "SG_PORT":               "HLF_PORT",
    "SG_MASTER_KEY":         "HLF_MASTER_KEY",
    "SG_STATE_DIR":          "HLF_STATE_DIR",
    "SG_MEMORY_DB":          "HLF_MEMORY_DB",
    "SG_MEMORY_DB_PATH":     "HLF_MEMORY_DB_PATH",
    "SG_AUDIT_DB":           "HLF_AUDIT_DB",
    "SG_AUDIT_CHAIN_LOG":    "HLF_AUDIT_CHAIN_LOG",
    "SG_LAST_HASH":          "LAST_HASH",
    "SG_AGENT_TIER":         "HLF_AGENT_TIER",
    "SG_STRICT":             "HLF_STRICT",
    "SG_APPROVAL_LEDGER_DB": "HLF_APPROVAL_LEDGER_DB",
    "SG_API_TOKEN":          "HLF_API_TOKEN",
    "SG_HKS_EXTERNAL_COMPARATOR_SCRIPT": "HLF_HKS_EXTERNAL_COMPARATOR_SCRIPT",
    "SG_HKS_EXTERNAL_COMPARATOR_TIMEOUT": "HLF_HKS_EXTERNAL_COMPARATOR_TIMEOUT",
}


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Resolve an SG_* env var with automatic HLF_* fallback.

    Priority:
        1. SG_* env var (if set)
        2. HLF_* env var (if set) — emits DeprecationWarning
        3. default value

    Args:
        name: The SG_ prefixed env var name (e.g., "SG_MASTER_KEY")
        default: Default value if neither is set

    Returns:
        Resolved value or default
    """
    # 1. Check new name
    value = os.environ.get(name)
    if value is not None:
        return value

    # 2. Fall back to old name
    old_name = _ENV_MAP.get(name)
    if old_name is not None:
        value = os.environ.get(old_name)
        if value is not None:
            warnings.warn(
                f"Environment variable '{old_name}' is deprecated. "
                f"Use '{name}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            _log.debug("Resolved %s from deprecated %s", name, old_name)
            return value

    return default


def get_env_required(name: str) -> str:
    """Like get_env but raises if no value is found."""
    value = get_env(name)
    if value is None:
        raise RuntimeError(
            f"Required environment variable '{name}' not set "
            f"(fallback '{_ENV_MAP.get(name, 'N/A')}' also not set)"
        )
    return value
```

### 5.2 Env Var Migration Table

| Old Name | New Name | Fallback? | Used In |
|----------|----------|-----------|---------|
| `HLF_TRANSPORT` | `SG_TRANSPORT` | Yes, with warning | server.py |
| `HLF_HOST` | `SG_HOST` | Yes, with warning | server.py |
| `HLF_PORT` | `SG_PORT` | Yes, with warning | server.py |
| `HLF_MASTER_KEY` | `SG_MASTER_KEY` | Yes, with warning | server_enterprise.py, merkle_dr.py |
| `HLF_STATE_DIR` | `SG_STATE_DIR` | Yes, with warning | server_context.py, rag/memory.py |
| `HLF_MEMORY_DB` | `SG_MEMORY_DB` | Yes, with warning | server_context.py, rag/memory.py |
| `HLF_MEMORY_DB_PATH` | `SG_MEMORY_DB_PATH` | Yes, with warning | rag/memory.py |
| `HLF_AUDIT_DB` | `SG_AUDIT_DB` | Yes, with warning | bridges/audit_bridge.py |
| `HLF_AUDIT_CHAIN_LOG` | `SG_AUDIT_CHAIN_LOG` | Yes, with warning | audit_chain.py |
| `LAST_HASH` | `SG_LAST_HASH` | Yes, with warning | audit_chain.py |
| `HLF_AGENT_TIER` | `SG_AGENT_TIER` | Yes, with warning | server_enterprise.py |
| `HLF_STRICT` | `SG_STRICT` | Yes, with warning | server_core.py |
| `HLF_APPROVAL_LEDGER_DB` | `SG_APPROVAL_LEDGER_DB` | Yes, with warning | approval_ledger.py |
| `HLF_API_TOKEN` | `SG_API_TOKEN` | Yes, with warning | server_auth.py |
| `HLF_HKS_EXTERNAL_COMPARATOR_SCRIPT` | `SG_HKS_EXTERNAL_COMPARATOR_SCRIPT` | Yes, with warning | server_memory.py |
| `HLF_HKS_EXTERNAL_COMPARATOR_TIMEOUT` | `SG_HKS_EXTERNAL_COMPARATOR_TIMEOUT` | Yes, with warning | server_memory.py |
| `SWARMGLASS_EXPERIMENTAL` | *(new)* | No fallback | All experimental gate sites |

### 5.3 Server Boot Logic Change

```python
# server.py — key boot change (Phase 2)
from swarmglass._env import get_env, get_env_required

_HOST = get_env("SG_HOST", "0.0.0.0")
_PORT = int(get_env("SG_PORT", "0") or "0")

mcp = FastMCP(
    name="SwarmGlass — Agent Swarm Governance",
    host=_HOST,
    port=_PORT,
)

# Core context — NO DSL imports
_ctx = build_core_context()

# Conditional experimental stack
if os.environ.get("SWARMGLASS_EXPERIMENTAL") == "1":
    _hlf_ctx = build_hlf_context(_ctx)
    register_experimental_tools(mcp, _hlf_ctx)
```

---

## 6. Deprecation Timeline

### Phase 2: Warn (Current — Namespace Migration)

**Timeframe:** Now through Gate 2 validation

| Artifact | Behavior |
|----------|----------|
| `hlf_*` governance tools | Work normally + emit `DeprecationWarning` on each call |
| `sg_*` governance tools | Work normally (canonical names) |
| `hlf_*` DSL tools | Work normally when `SWARMGLASS_EXPERIMENTAL=1` |
| `HLF_*` env vars | Work, emit `DeprecationWarning` if `SG_*` not set |
| `from hlf_mcp import HLFCompiler` | Works (lazy import triggers DSL load) |
| `import swarmglass` | Works — zero DSL imports |
| Server boots without DSL | ✓ Default mode |

### Phase 3: Deprecate (After Gate 2 — Domain Activation Complete)

**Timeframe:** ~2-4 weeks after Phase 2 stabilization

| Artifact | Behavior |
|----------|----------|
| `hlf_*` governance tools | Still work but emit `FutureWarning` (stronger than DeprecationWarning) |
| `sg_*` tools | Only names shown in `sg_observe_tools` (alias list) — `hlf_*` hidden from listing |
| `hlf_*` experimental tools | Gated behind `SWARMGLASS_EXPERIMENTAL=1` — no change |
| `HLF_*` env vars | Still work but emit `FutureWarning` |
| Docs | All references use `sg_*` names. `hlf_*` names footnoted as "legacy alias" |
| CI guard | New CI test: fails if any `register_*_tools()` function registers a governance tool under ONLY `hlf_*` name |

### Phase 4: Remove (After Gate 3 — Experimental Isolation Verified)

**Timeframe:** ~4-8 weeks after Phase 3

| Artifact | Behavior |
|----------|----------|
| `hlf_*` governance tool aliases | **REMOVED** — only `sg_*` names work for governance tools |
| `hlf_*` DSL tools | Still work under `SWARMGLASS_EXPERIMENTAL=1` — never removed |
| `HLF_*` env vars | **REMOVED** — only `SG_*` names resolved |
| `hlf_mcp/__init__.py` | DSL re-exports removed from `__all__` — only `__version__` remains public |
| Package rename | `hlf-mcp` → `swarmglass` on PyPI (old name kept as empty shim with deprecation notice) |
| `from hlf_mcp import HLFCompiler` | Broken — use `from hlf_mcp.hlf.compiler import HLFCompiler` directly |

### Permanent: Experimental Lane

The `hlf_*` DSL tools (compiler, runtime, translator, bytecode, benchmarks) are **never removed**. They live behind `SWARMGLASS_EXPERIMENTAL=1` permanently:

- Not advertised in default tool listings
- Not documented in main README (only in `docs/HLF_EXPERIMENTAL.md`)
- Not loaded during default server boot
- No `sg_*` aliases — these are HLF-specific tools that don't have governance equivalents

---

## 7. Implementation Checklist

### Phase 2 — Shim Delivery

- [ ] **G1.** Refactor `hlf_mcp/__init__.py` to lazy `__getattr__` (no eager DSL imports)
- [ ] **G2.** Split `server_context.py`: `build_core_context()` + `build_hlf_context()`
- [ ] **G3.** Create `swarmglass/` package with `__init__.py`, `_shim.py`, `_env.py`
- [ ] **G4.** Create `swarmglass/core/` with domain stubs (observe.py, validate.py, audit.py, secure.py)
- [ ] **G5.** Add `register_aliased()` calls in all governance `register_*_tools()` functions
- [ ] **G6.** Gate all DSL-only `@mcp.tool()` registrations behind `SWARMGLASS_EXPERIMENTAL=1`
- [ ] **G7.** Replace all `os.environ.get("HLF_*")` with `get_env("SG_*")` in server code
- [ ] **G8.** Update `server.py` to boot core context by default, experimental on flag
- [ ] **G9.** Create `tests/test_shim_migration.py`:
  - Verify `import swarmglass` does not load `hlf_mcp.hlf.compiler` into `sys.modules`
  - Verify all governance `hlf_*` tools have corresponding `sg_*` aliases
  - Verify `SWARMGLASS_EXPERIMENTAL=0` suppresses DSL tools
  - Verify `hlf_*` governance tools emit `DeprecationWarning`
  - Verify `HLF_*` env vars fall back correctly with warning

### Phase 3 — Domain Activation

- [ ] Move tool implementations into `swarmglass/core/*.py` (re-import from hlf_mcp internals)
- [ ] Update `sg_observe_tools` (tool listing) to hide deprecated `hlf_*` names
- [ ] Write domain guides in `docs/` referencing `sg_*` names only
- [ ] CI import guard: fail if `swarmglass.core` imports `compiler`, `runtime`, `bytecode`, `translator`, `grammar`

### Phase 4 — Experimental Isolation

- [ ] Move DSL server wiring into `swarmglass/experimental/`
- [ ] Remove `hlf_*` governance aliases from registration
- [ ] Remove `HLF_*` env var fallback
- [ ] Remove DSL re-exports from `hlf_mcp/__init__.py`
- [ ] Package rename on PyPI

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `hlf_mcp/__init__.py` lazy refactor breaks downstream `from hlf_mcp import X` | ImportError for external consumers | `__getattr__` preserves all names in `__all__`. PEP 562 compliant. Test all 27 re-exported symbols. |
| `server_context.py` split causes circular imports | Server fails to boot | New `CoreContext` imports NO modules that import from `server_context.py`. Verified by import graph analysis. |
| Duplicate `hlf_hitl_*` tools in server_core.py + server_enterprise.py | Ambiguous registration | Resolve duplicates: server_enterprise.py versions take precedence (newer). Remove duplicates from server_core.py. |
| `swarmglass/_shim.py` depends on FastMCP's internal registration API | Breakage on FastMCP upgrade | Use only documented `mcp.tool()` decorator API. No monkey-patching of FastMCP internals. |
| Governance tools import paths that transitively load DSL modules | Silent DSL coupling | CI import guard (Phase 3) catches any `swarmglass.core` → DSL import chain. |
