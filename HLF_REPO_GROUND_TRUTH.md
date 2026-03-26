# HLF_MCP — Immediate Known True Local Knowledge

**For: Any outside agent, analyst, or advisor working in or on this repo.**
**Snapshot date:** 2026-03-26 | **Version:** 0.5.0 | **Branch:** `rescue/governed-review-recovery-2026-03-21`
**Test baseline:** 963 passed (verified 2026-03-26, 186s runtime)
**NOTHING IN THIS DOCUMENT IS ASPIRATIONAL. Everything stated here is verifiable in the checkout right now.**

---

## Identity — What HLF Actually Is

HLF (Hieroglyphic Logic Framework) is a **deterministic LALR(1) parsed language** with governed execution semantics, compiled to bytecode, served as an MCP (Model Context Protocol) server. It is NOT a thin wrapper, DSL toy, or vibes-coded MVP. The intended end-state is a universal agent coordination protocol connecting intent → agents → tools → memory → governance → verification → execution through one bounded meaning layer with six interchangeable surfaces (grammar, bytecode, AST JSON, MCP tools, host functions, operator reports).

**Grammar:** HLF v3, Lark LALR(1) with contextual lexer. Programs begin with `[HLF-v3]`. 21 statement types, 7 Unicode glyphs (Δ Ж ⨝ ⌘ ∇ ⩕ ⊎) with ASCII aliases. **Bytecode:** 3-byte fixed instructions, `.hlb` v0.4 format, 37 opcodes with gas metering.

## Architecture — What Exists

| Layer | Contents | Key files |
|-------|----------|-----------|
| **Parser/Compiler** | Lark LALR(1) → AST → bytecode | `hlf_mcp/hlf/grammar.py`, `compiler.py`, `bytecode.py` |
| **Runtime/VM** | Stack machine with gas metering | `hlf_mcp/hlf/runtime.py` |
| **Formatter/Linter** | Canonical formatting + diagnostics | `hlf_mcp/hlf/formatter.py`, `linter.py` |
| **Ethics Governor** | 4-layer pipeline, fails closed | `hlf_mcp/hlf/ethics/governor.py` |
| **Capsules** | Intent capsule pre-flight validation | `hlf_mcp/hlf/capsules.py` |
| **Memory/RAG** | SQLite-backed Infinite RAG with governed recall | `hlf_mcp/rag/memory.py` |
| **Routing/Ingress** | Governed admission with ALIGN gate | `hlf_mcp/hlf/governed_routing.py`, `governed_ingress.py` |
| **Execution Admission** | Multi-factor deny/review/admit gating | `hlf_mcp/hlf/execution_admission.py` |
| **Formal Verifier** | ⚠️ See "What's Surface-Level" below | `hlf_mcp/hlf/formal_verifier.py` |
| **MCP Server** | FastMCP, 3 transports (stdio/sse/streamable-http) | `hlf_mcp/server.py` |
| **Instinct/Lifecycle** | SDD lifecycle state machine | `hlf_mcp/instinct/` |
| **Weekly Artifacts** | SHA-256 decision records | `hlf_mcp/weekly_artifacts.py` |
| **Translation** | Multilingual intent → HLF with repair plans | `hlf_mcp/hlf/translation.py` |
| **Benchmark** | Token compression measurement vs NLP | `hlf_mcp/hlf/benchmark.py` |

**Physical counts:** 79 Python source files in `hlf_mcp/`, 59 test files in `tests/`, 76 docs in `docs/`, 27 root-level docs. 12 runtime dependencies headed by `mcp[cli]>=1.26.0`, `lark>=1.3.1`, `fastapi>=0.135.1`.

**MCP surface:** 76 tools, 56 resources, 25 resource templates. Entry: `uv run hlf-mcp` (stdio default) or `HLF_TRANSPORT=sse HLF_PORT=8011 uv run hlf-mcp`.

## Dual-Repo Source Authority — Critical

| Repo | Role | Branch |
|------|------|--------|
| `Sovereign_Agentic_OS_with_HLF` | **Upstream source authority** — original full architecture | `main` |
| `HLF-Hieroglyphic-Logic-Framework-MCP` | **Packaged MCP extraction** — this repo | `rescue/governed-review-recovery-2026-03-21` |

Source material from the upstream repo lives in `hlf_source/` within this checkout. Some constitutive features were never ported (e.g., `CapsuleInterpreter` from `hlf_source/hlf/intent_capsule.py`). **Always check `hlf_source/` before declaring something "not in the design."**

## What's GENUINELY SOLID (real enforcement, real denial paths, tested)

- **Execution admission** — multi-factor deny/review/admit decisions. Strongest governance component.
- **Ethical governor** — 4-layer pipeline, fails closed, actually integrated into runtime, actually blocks.
- **Governed routing** — real ALIGN-block denial paths, trust-state checks, verdicts consumed by server.
- **Governed ingress** — multi-stage pipeline: rate limit → replay → ALIGN → validation. All denial paths tested.
- **Memory read/recall path** — purpose-based policies, freshness checks, revocation filtering, supersession, provenance.
- **Weekly artifacts** — SHA-256 IDs, `_validate_decision_record()` raises ValueError on invalids.
- **Pointer infrastructure** — `HLFPointer` with real hash binding, freshness, revocation.
- **Parser/Compiler/Runtime/Formatter/Linter** — all functional and tested. Grammar bug fixes (ADDOP/MINUS conflict, IF flat/block ambiguity) stable. `_emit_expr` bytecode emitter completed and validated.
- **Benchmark** — real tiktoken-based token compression measurement.

## What's SURFACE-LEVEL (looks right, doesn't really do the thing)

| Claimed Feature | Reality | File |
|----------------|---------|------|
| **Formal verification (Z3)** | Z3 import exists, boolean flag exists, but **ZERO Z3 solver calls are ever made.** `FallbackSolver` does trivial `isinstance`/comparison checks. "PROVEN" = passed simple Python comparison. It is a runtime assertion engine **mislabeled** as formal verification. | `formal_verifier.py` (725 lines) |
| **Memory write-path governance** | **ZERO enforcement.** `store("anything")` silently succeeds. All 13 mandatory evidence fields backfilled with permissive defaults. | `rag/memory.py` |
| **MCP memory tool enforcement** | Every evidence parameter is optional. No write-time rejection gate. | `server_memory.py` |
| **Governance events enforcement** | Pure audit trail — records events but gates nothing. No governance spine consuming them. | `governance_events.py` |

## What's PARTIAL (real but incomplete)

| Feature | What works | What doesn't | File |
|---------|------------|--------------|------|
| **Capsule boundary** | Pre-flight `validate_ast()` genuinely blocks. Approval workflow with SHA-256 tokens real. | **No CapsuleInterpreter in VM.** Capsule validates before execution but not during. Bytecode can include denied host calls. | `capsules.py` |
| **Host function tiers** | Registry has tier metadata + PermissionError definitions. | **`_dispatch_host()` bypasses registry.** Forge-tier can call sovereign-level functions at runtime. | `registry.py`, `runtime.py` |
| **Memory evidence schema** | SQLite table exists. | All 13 evidence fields in a single untyped `metadata_json TEXT` blob. Zero DB constraints. | `rag/memory.py` |
| **MemoryNode evidence** | Pointer infrastructure solid. | Carries 1/13 required evidence fields (confidence only). | `memory_node.py` |

## The Universal Pattern To Watch For

> **Infrastructure and type signatures look complete; enforcement is frequently pre-flight only, read-side only, advisory only, or metadata-labeled but not actually gating at runtime.**

This is the single most important thing to know about the current codebase. Claims look real until you trace them to execution. Always verify: does this code actually block, deny, or reject in the hot path — or does it only log, record, or validate before the hot path?

## Three-Lane Doctrine — Non-Negotiable

| Lane | Purpose | Authority files |
|------|---------|----------------|
| **Vision** | North-star scope. Allowed to be bigger than implemented. | `HLF_VISION_DOCTRINE.md`, `docs/HLF_DESIGN_NORTH_STAR.md` |
| **Current Truth** | Only what is implemented, validated, and honest to claim now. | `SSOT_HLF_MCP.md`, `HLF_QUALITY_TARGETS.md` |
| **Bridge** | How this repo converges from current truth toward vision. | `HLF_ACTIONABLE_PLAN.md`, `HLF_CANONICALIZATION_MATRIX.md` |

**Never collapse these into one flattened story. Never promote bridge or vision claims into present-tense truth without implementation + test evidence.**

## Recovery Batch Sequence (Active Plan)

- **Batch 1 (P1 — current):** Formal verification recovery, governance control matrix, normalized memory evidence contracts, operator proof surface validation
- **Batch 2 (P1-P2):** Orchestration lifecycle, typed effect algebra, verifier-backed admission, memory freshness, audit spine
- **Batch 3 (P3):** Persona/operator doctrine, gallery/legibility, VS Code extension, real-code bridge

## Hard Rules

1. **"No governance claim promoted without packaged asset + named proof surface."** — Every governance claim must point to a specific file that actually enforces it.
2. **Do not reduce complexity to simplify.** Complex systems require complex solutions. Removing enforcement to make code tidier is a regression, not a cleanup.
3. **Source comparison before declaring anything optional.** Check `hlf_source/` and doctrine before excluding a feature.
4. **Ban pseudo-equivalents.** A thinner substitute that preserves labels but removes constitutive semantics (governance, verification, provenance, tier enforcement) is a regression.
5. **Z3 is not installed.** `import z3` will fail. The formal verifier currently runs entirely on the trivial FallbackSolver. This is known debt, not a runtime bug.

## Tech Stack (Verified)

- Python 3.13.11, `uv` package manager, `hatchling` build
- `pytest` 9.x (963 tests), `lark` 1.3+ (LALR parser), `fastapi` 0.135+ (HTTP), `mcp[cli]` 1.26+
- SQLite3 for capsule approvals (`db/hlf_capsule_approvals.sqlite3`) and memory
- No external database. No Redis required (optional `valkey` extra).
- VS Code MCP wiring via `.vscode/mcp.json` targeting `uv run hlf-mcp`

## What Not To Do

- Do not frame HLF as "just an MCP server" or "just a parser."
- Do not delete governance surfaces to make the repo cleaner.
- Do not assume README claims are implemented — cross-reference `SSOT_HLF_MCP.md`.
- Do not add features, libraries, or abstractions the build plans don't call for.
- Do not confuse the `hlf/` (legacy compat line) directory with `hlf_mcp/` (current product).
- Do not treat the formal verifier as functional formal verification. It is not.
