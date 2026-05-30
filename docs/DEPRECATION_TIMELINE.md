# SwarmGlass Deprecation Timeline

> **Status:** Active — Phase 2 (Warning) is current. See [SHIM_DESIGN.md](./SHIM_DESIGN.md) for technical details.

## Overview

HLF_MCP is migrating from `hlf_*` tool names to `sg_*` (SwarmGlass) names. This document defines the deprecation schedule so downstream consumers know what to expect and when.

**Principle:** Additive only. No breaking changes through Phase 3. Old names work throughout migration.

---

## Current State: Phase 2 — Warn (Active Now)

**Status:** Live. 85 `sg_*` aliases registered alongside their `hlf_*` equivalents.

| Area | Behavior |
|------|----------|
| Governance tools | Both `hlf_*` and `sg_*` names work. `hlf_*` emits `DeprecationWarning` on each call. |
| DSL tools | `hlf_*` names only — gated behind `SWARMGLASS_HLF_ENABLED=1`. No `sg_*` aliases. |
| Environment variables | `HLF_*` vars work with fallback. `HLF_EXPERIMENTAL_MODE` remapped to `SWARMGLASS_HLF_ENABLED`. |
| Server boot | Governance-only by default (`SWARMGLASS_HLF_ENABLED=0`). Zero DSL imports. |
| CI | `test_ci_import_guard.py` verifies no DSL leakage from governance tools. |

**Counts:**
- **Governance aliases:** 85 `sg_*` tools registered (100% of non-experimental tools)
- **Experimental only:** 37 `hlf_*` tools (compiler, runtime, translator, benchmarks)
- **Total MCP tools:** 147 (governance) + 68 (experimental) = 215 maximum

---

## Phase 3: Deprecate (Next — After Gate 3)

**Timeframe:** ~2-4 weeks after Phase 2 stabilization

| Area | Change |
|------|--------|
| Governance tools | `hlf_*` names still work but emit `FutureWarning` (stronger signal). |
| Tool listing | `sg_observe_tools` shows only `sg_*` names. `hlf_*` hidden from discovery. |
| Environment variables | `HLF_*` still works but emits `FutureWarning`. |
| Documentation | All docs reference `sg_*` names. `hlf_*` footnoted as "legacy alias". |
| CI guard | New check: fails if governance tools registered under ONLY `hlf_*` name. |

**Implementation tasks:**
- [ ] Upgrade warnings from `DeprecationWarning` to `FutureWarning`
- [ ] Filter `sg_observe_tools` output to show only `sg_*` names
- [ ] Update all docs to use `sg_*` names
- [ ] Add CI check for single-name registration

---

## Phase 4: Remove (Final — After Experimental Isolation Verified)

**Timeframe:** ~4-8 weeks after Phase 3

| Area | Change |
|------|--------|
| Governance `hlf_*` aliases | **REMOVED.** Only `sg_*` names work for governance tools. |
| DSL tools | **Preserved.** `hlf_*` compiler/runtime/translator remain under `SWARMGLASS_HLF_ENABLED=1` forever. |
| `HLF_*` env vars | **REMOVED.** Only `SG_*` names resolved. |
| `hlf_mcp/__init__.py` | DSL re-exports removed from `__all__`. Only `__version__` remains public. |
| Package name | `hlf-mcp` → `swarmglass` on PyPI. Old name kept as empty shim with deprecation notice. |
| `from hlf_mcp import HLFCompiler` | Broken. Use `from hlf_mcp.hlf.compiler import HLFCompiler` directly. |

**Implementation tasks:**
- [ ] Remove `hlf_*` governance aliases from all `register_*_tools()` functions
- [ ] Remove `HLF_*` env var fallback from `env_migration.py`
- [ ] Remove DSL re-exports from `hlf_mcp/__init__.py`
- [ ] Rename package on PyPI
- [ ] Create empty `hlf-mcp` shim package with install warning

---

## Permanent: Experimental Lane

The `hlf_*` DSL tools (compiler, runtime, translator, bytecode, benchmarks) are **never removed**. They live behind `SWARMGLASS_HLF_ENABLED=1`:

- Not advertised in default tool listings
- Not documented in main README
- Not loaded during default server boot
- No `sg_*` aliases — these are HLF-specific tools without governance equivalents

---

## Migration Timeline Summary

```
Phase 2 (NOW)     Phase 3 (+2-4wk)    Phase 4 (+4-8wk)     Permanent
───────────────────────────────────────────────────────────────────────────
hlf_* + sg_*      hlf_* hidden         hlf_* REMOVED        DSL hlf_* only
HLF_* fallback    HLF_* warned         HLF_* REMOVED        SG_* only
DeprecationWarning FutureWarning       ImportError          Experimental gate
```

---

## For Downstream Consumers

**Immediately (Phase 2):**
- Start using `sg_*` tool names. They work now.
- Replace `HLF_EXPERIMENTAL_MODE` with `SWARMGLASS_HLF_ENABLED` in your configs.
- Check your logs for `DeprecationWarning` messages to find deprecated usages.

**Soon (Phase 3):**
- Complete `hlf_*` → `sg_*` migration. Tool listings will stop showing old names.

**Eventually (Phase 4):**
- Update any remaining `HLF_*` env var references to `SG_*` equivalents.
- If you import from `hlf_mcp` directly, switch to `hlf_mcp.hlf.compiler` for DSL access.

**Never needed:**
- DSL users: your `hlf_compile`, `hlf_run`, `hlf_translate_to_hlf` tools stay forever under experimental mode. No migration required.
