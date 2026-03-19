# Repo Memory: HLF Merge Doctrine — 2026-03-15

**Last updated:** 2026-03-19
**Memory type:** Session doctrine — merge rules, working assumptions, non-negotiables established in the 2026-03-15 recovery session

---

## What Happened On 2026-03-15

On 2026-03-15, a working session established the canonical merge doctrine for extracting HLF from
the `Sovereign_Agentic_OS_with_HLF` source repo into the standalone `HLF-Hieroglyphic-Logic-Framework-MCP` product repo.

The session produced two recovered documents:
- `RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md` — vision, wiring, goals, drift diagnosis
- `RECOVERED_MCP_COMPARISON_2026-03-15.md` — MCP surface comparison and drift analysis

The memory file you are now reading synthesizes the doctrine from those recovered documents into
a compact agent-readable form.

---

## The Core Merge Goal

**Take the full HLF vision expressed in `hlf_source/` and related source docs, and fold it into the
standalone HLF_MCP product in a way that is canonical, testable, and internally consistent.**

That goal explicitly requires:
1. Choosing **one** canonical MCP surface (the packaged `hlf_mcp/` FastMCP server)
2. Choosing **one** canonical compiler/runtime path (`hlf_mcp/hlf/`)
3. Eliminating duplicated legacy-vs-new tool inventories (not combining them)
4. Aligning README claims with actual code
5. **Preserving the full HLF scope** — not reducing it to a toy DSL

---

## The Three-Lane Split (Established 2026-03-15)

The session established this as the fundamental operating doctrine:

| Lane | Purpose | Rule |
|------|---------|------|
| **Vision** | North-star scope for what HLF becomes | Allowed to be larger than current code; never strip it |
| **Current Truth** | Only what is implemented, validated, honest to claim | Strict; no aspirational wording here |
| **Bridge** | Professional convergence plan from truth to vision | Where roadmap lives; drives implementation |

**Core rule:** "Never solve drift by deleting the vision lane. Solve drift by separating vision, truth, and bridge lanes clearly."

---

## Non-Negotiable Merge Principles

### 1. One source of truth per domain

Each domain should have one canonical source, with other artifacts derived from it.

- Grammar spec is canonical.
- Bytecode spec is canonical.
- Host function registry is canonical.
- Docs and inventories must be derived, not hand-maintained drift zones.

### 2. Split docs by truth level

Three truth classes:
- **Normative**: true by spec
- **Generated**: true for this commit
- **Roadmap**: planned

Never mix all three inside README claims. This is the root cause of most drift.

### 3. HLF must become a layered standard

Recovered official profiles:
- `HLF-Core` (weak agents participate)
- `HLF-Effects` (governed tool use)
- `HLF-Agent` (swarm coordination)
- `HLF-Memory` (persistent governed knowledge)
- `HLF-VM` (portable deterministic execution)

This allows scaling from laptop to sovereign swarm without product fragmentation.

### 4. Do not shrink the vision to make things compile

"Do not shrink the vision just to make pieces compile."

If reducing a surface narrows HLF from a governed agent language into a parser-only fragment, that surface is constitutive, not optional.

### 5. Rebuild from original intent outward

Not from a packaged MVP inward. The correct direction is: understand the full HLF intent first, then work backward to what is safe to claim now, then build the bridge.

---

## Merge Doctrine: What The Source Repo Is

Source: `Sovereign_Agentic_OS_with_HLF` / available locally as `hlf_source/`

The source is **not** the final canonical implementation for the standalone repo. It is:
- The richest vision and reference source
- The authoritative upstream for constitutive HLF pillars not yet restored
- The correct archaeology target for understanding what was lost or narrowed

### Three MCP surfaces in the source (2026-03-15 comparison finding)

| Surface | Where | Drift status |
|---------|-------|-------------|
| Source Sovereign MCP bridge | `hlf_source/mcp/sovereign_mcp_server.py` | ~18 tools in code vs. claimed "8 secure tools" in docs — already stale before standalone work began |
| Standalone HLF_MCP product | `hlf_mcp/server.py` | 34 tools / 9 resources in code; README drifts from actual counts |
| Legacy compatibility line | `hlf/mcp_tools.py` | 32 tools (legacy 10 + new 22 combined); over-counted because it merges both surfaces without choosing one |

**Decision:** The standalone `hlf_mcp/` FastMCP surface is the one canonical target. The legacy `hlf/` line should be maintained for compatibility but not extended.

---

## Practical Working Assumptions (Established 2026-03-15)

These assumptions are safe for continuing implementation:

1. The standalone HLF_MCP repo is supposed to embody the **full HLF vision**, not just a minimal demo.
2. The source Sovereign repo is the richest vision/reference source, but not the final canonical implementation for this standalone repo.
3. The standalone `README.md` is the clearest product-spec target, but it currently drifts and must be corrected against code.
4. The local uncommitted work at the time was a partially completed merge attempt and should be evaluated as convergence work, not as final truth.
5. HLF work should be judged against: determinism, bounded capability, canonical semantics, and explicit governance.

---

## Immediate Implementation Doctrine (2026-03-15 Rules)

Until the repo is fully reconciled, these rules apply:

- **Do not** shrink the vision just to make pieces compile.
- **Do not** treat README counts as authoritative without verifying inventories.
- **Do not** merge legacy and new surfaces without naming the canonical target.
- **Do not** use standalone neatness as the deciding heuristic when a surface carries doctrine, routing, personas, governance, verification, or ecosystem meaning.
- **Do** preserve the HLF identity as a deterministic, governed language stack.
- **Do** prioritize one source of truth for grammar, bytecode, host functions, and MCP inventory.
- **Do** treat the legacy `hlf/` line as compatibility, not as the extension target.

---

## The Drift Problem (Diagnosed 2026-03-15)

The main failure mode before this session was **canonicality drift**:

Current drift zones identified:
- Source Sovereign MCP bridge docs did not match its tool count
- Standalone HLF_MCP README counts did not match its own tables
- Standalone FastMCP server inventory was ahead of the README summary
- Local uncommitted retrofit work mixed old provider surface and new standalone product surface

This means the core task is **architectural reconciliation**, not blind new feature work.

The wiring HLF should follow (canonical flow):

```
English or glyph source
  → canonical AST
  → validated effects and governance
  → bytecode
  → bounded runtime
  → governed tools and memory
  → MCP exposure
  → human auditability
```

---

## What "A2A-Complete" Means (Vision Target)

HLF becomes A2A-complete when it can govern:
- Intent transfer between agents
- Delegation terms and trust scope
- Effect boundaries and approval requirements
- Consensus and dissent semantics
- Memory anchoring and provenance of every handoff
- Recoverable audit of the full coordination graph

Transport carries packets. **HLF carries governed meaning.**

---

## Recovery Work Triggered By This Doctrine

The 2026-03-15 doctrine directly drove the following recovery work (all now complete through docs):

- `docs/HLF_MISSING_PILLARS.md` — pillar gap classifier
- `docs/HLF_PILLAR_MAP.md` — ownership map per pillar
- `docs/HLF_RECOVERY_BATCH_1.md` and `docs/HLF_RECOVERY_BATCH_2.md` — executable restoration batches
- `docs/HLF_ROUTING_RECOVERY_SPEC.md` — routing fabric spec
- `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` — formal verifier spec
- `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` — orchestration lifecycle spec
- `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` — HKS governed memory spec
- `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` — persona doctrine spec
- `plan/architecture-hlf-reconstruction-2.md` — master reconstruction plan (phases 0–10)
- `plan/feature-routing-fabric-1.md`, `plan/feature-formal-verifier-1.md`, `plan/feature-orchestration-lifecycle-1.md`
- `HLF_SOURCE_EXTRACTION_LEDGER.md` and `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`

---

## Summary: The Two Rules That Never Change

1. **Never solve drift by deleting the vision lane.** Separate the lanes; don't flatten them.

2. **Never treat the packaged surface as the full HLF target.** The packaged surface is the current canonical implementation, but the target is the full governed language and coordination substrate.
