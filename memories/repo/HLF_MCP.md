# Repo Memory: HLF-Hieroglyphic-Logic-Framework-MCP

**Last updated:** 2026-03-19
**Memory type:** Repo state — always read this first before major decisions

---

## Identity

This repo is **HLF-Hieroglyphic-Logic-Framework-MCP**, a standalone extracted and partially-recovered
implementation of the HLF (Hieroglyphic Logic Framework) language and governance system.

It was extracted from the larger `Sovereign_Agentic_OS_with_HLF` source repo. Some constitutive
pillars were preserved during extraction; others were downgraded, omitted, or stranded in
`hlf_source/` pending faithful port or restore work.

**This is not a finished minimal core. It is a serious, partially recovered implementation on the
path toward a larger governed language system.**

---

## The Three-Lane Rule (Non-Negotiable)

Every design decision must stay in one of three lanes:

| Lane | What it is | Primary files |
|------|-----------|---------------|
| **Vision** | Full north-star target — allowed to be larger than current code | `HLF_VISION_DOCTRINE.md`, `docs/HLF_DESIGN_NORTH_STAR.md`, `RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md` |
| **Current Truth** | Only what is implemented, validated, and safe to claim now | `SSOT_HLF_MCP.md`, `HLF_QUALITY_TARGETS.md`, `BUILD_GUIDE.md` |
| **Bridge** | How this repo converges from current truth toward full vision | `HLF_ACTIONABLE_PLAN.md`, `plan/architecture-hlf-reconstruction-2.md`, `HLF_CANONICALIZATION_MATRIX.md`, `HLF_IMPLEMENTATION_INDEX.md` |

Never collapse these three lanes.

---

## Current Build Surface (as of 2026-03-19)

### Packaged product (`hlf_mcp/`)
- Entry point: `hlf-mcp` → `hlf_mcp.server:main`
- FastMCP server: **34 tools, 9 resources, 0 prompts**
- Transports: `stdio`, `sse`, `streamable-http`
- Health endpoint: `/health` for HTTP transports

### What is real now
- **Compiler** (`hlf_mcp/hlf/compiler.py`): multi-pass, LALR parsing, normalization, immutable env, ethics hook, variable expansion, ALIGN validation, gas estimation, AST cache
- **Runtime** (`hlf_mcp/hlf/runtime.py`): bytecode VM, gas metering, stack execution, trace capture, side-effect tracking
- **Bytecode** (`hlf_mcp/hlf/bytecode.py`): encoding/decoding, opcode tables
- **Capsules** (`hlf_mcp/hlf/capsules.py`): tiered execution, gas ceilings, AST validation
- **Translator** (`hlf_mcp/hlf/translator.py`): English-to-HLF, HLF-to-English
- **Formatter** (`hlf_mcp/hlf/formatter.py`) and **Linter** (`hlf_mcp/hlf/linter.py`)
- **Memory** (`hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`): Infinite RAG, HKS exemplar flows, merkle_chain_depth
- **Instinct lifecycle** (`hlf_mcp/instinct/`): SDD stages, mission/state progression
- **Governance assets** (`governance/`): align_rules.json, host_functions.json, MANIFEST.sha256, bytecode_spec.yaml
- **CLI entry points**: `hlfpm`, `hlfsh`, `hlftest`

### Legacy compatibility surface (`hlf/`)
- Still real and testable
- **Not** the package entry point or canonical production surface
- Useful `hlf_do` front door and legacy prompt/resource plumbing still present

---

## Pillar Status Summary

| Pillar | Status |
|--------|--------|
| Deterministic language core | **Present** |
| Runtime and capsule-bounded execution | **Present** |
| Governance-native execution | **Damaged** |
| Typed effect and capability algebra | **Damaged** |
| Human-readable audit and trust layer | **Damaged** |
| Real-code bridge | **Damaged** |
| Knowledge substrate and governed memory | **Damaged** — HKS boundary not yet locked |
| Formal verification surface | **Source-only** — `hlf_source/agents/core/formal_verifier.py` |
| Gateway and routing fabric | **Source-only** — `hlf_source/agents/gateway/{bus,router,sentinel_gate}.py` |
| Orchestration lifecycle | **Source-only** — `hlf_source/agents/core/{plan_executor,crew_orchestrator,task_classifier}.py` |
| Persona and operator doctrine | **Source-only** — `hlf_source/config/personas/` |
| Ecosystem integration surface | **Source-only** — `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md` |
| Gallery and operator-legibility | **Damaged** |

Full detail: `docs/HLF_MISSING_PILLARS.md` and `docs/HLF_PILLAR_MAP.md`

---

## Planning Authority

### Master reconstruction plan
`plan/architecture-hlf-reconstruction-2.md` — versioned, all phases 0–10 complete through docs

### Phase completion status (as of 2026-03-19)
- Phase 0–10: ✅ All planning documentation tasks complete
- Code restoration batches: **not yet started**

### Next recovery batches (priority order)
1. Gateway and routing fabric
2. Formal verification surface
3. Orchestration lifecycle
4. HLF knowledge substrate / governed memory contracts
5. Persona and operator doctrine integration
6. Gallery and operator-legibility surfaces

Batch specs: `docs/HLF_RECOVERY_BATCH_1.md`, `docs/HLF_RECOVERY_BATCH_2.md`
Feature plans: `plan/feature-routing-fabric-1.md`, `plan/feature-formal-verifier-1.md`, `plan/feature-orchestration-lifecycle-1.md`

---

## Key Architecture Truths

1. **HLF is a meaning layer**, not just a syntax or parser. It must carry governed intent from human input through agents, tools, memory, execution, and audit.

2. **The packaged `hlf_mcp/` line is the canonical production surface.** The legacy `hlf/` line has useful components but is not the merge target.

3. **Recursive build assistance is the first credible self-use milestone.** Centered on `stdio` + `hlf_do` + `hlf_test_suite_summary` + build-observation surfaces. Remote `streamable-http` self-hosting is bridge work, not current truth.

4. **`SSOT_HLF_MCP.md` is the current-truth authority.** Do not use README ambition as proof of current behavior.

5. **`docs/HLF_CLAIM_LANES.md` classifies all wording** into current-true, bridge-true, or vision-only. Use it when writing or reviewing docs.

---

## Test Suite

```
pip install -e ".[dev]" && python -m pytest tests/ -q
```
105 tests, ~0.3s passing. Includes `tests/test_github_scripts.py` (63 tests covering ollama_client circuit breaker, streaming, fallback, spec drift, ethics).

Python ≥ 3.12 required.

---

## Weekly CI

8 workflows under `.github/workflows/weekly-*.yml`. Uses Ollama Cloud (`https://ollama.com/api`).
Fallback chains:
- REASONING: `nemotron-3-super` → `kimi-k2:1t-cloud` → `qwen3.5:cloud` → `deepseek-r1:14b`
- CODING: `devstral:24b` → `nemotron-3-super` → `qwen3.5:cloud` → `deepseek-r1:14b`

---

## Prohibited Actions (Reconstruction Rules)

1. Do not treat `hlf_mcp/` as the full HLF target — it is the current canonical surface, not the destination.
2. Do not shrink vision to fit current code. Separate lanes; don't collapse them.
3. Do not substitute pseudo-equivalents or thin stand-ins for stronger source architecture.
4. Do not mark a recovery area complete until code, tests, docs, and operator surfaces are all updated.
5. Do not widen capsule permissions, host-function effects, or governance without explicit governance updates.
6. Do not treat any surface as optional if removing it narrows HLF from "governed agent language" to "parser-only fragment."
7. Do not claim `streamable-http` self-hosting readiness until `initialize` succeeds end-to-end.

---

## Source Reference

Source repo: `Sovereign_Agentic_OS_with_HLF` (available in `hlf_source/` directory)

The source contains broader HLF surfaces including:
- `agents/gateway/` — routing fabric (constitutive)
- `agents/core/` — formal verifier, plan executor, orchestrator (constitutive)
- `config/personas/` — steward, sentinel, and other persona doctrine
- `governance/ALIGN_LEDGER.yaml` — richer live-ledger governance
- `docs/UNIFIED_ECOSYSTEM_ROADMAP.md` — ecosystem integration doctrine
- `scripts/run_hlf_gallery.py` — operator gallery/legibility surface
