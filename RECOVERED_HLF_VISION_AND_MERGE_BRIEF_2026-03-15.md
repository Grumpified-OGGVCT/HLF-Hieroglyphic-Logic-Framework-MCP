# Recovered HLF Vision And Merge Brief

Date: 2026-03-15

This file reconstructs the goals, vision, architecture intent, and merge target for HLF using surviving repo memory, the standalone HLF_MCP README, and the source Sovereign OS docs.

## 1. What HLF Is

HLF is not primarily a syntax.

HLF is a contract for deterministic meaning under bounded capability.

That means:
- syntax is reversible
- semantics are canonical
- effects are explicit
- execution is reproducible
- audit is built-in
- tooling is generated
- evolution is governed

Recovered from:
- `/memories/repo/hlf_blueprint.md`
- `README.md`
- `hlf_source/README.md`

## 2. Why It Exists

The core purpose is not just compression or a clever DSL.

HLF exists to make AI capability more useful, portable, governed, and widely accessible across the entire model spectrum.

The intended effect is:
- reduce ambiguity between humans, tools, local models, and cloud models
- compress coordination overhead
- enforce deterministic execution and bounded effects
- make ordinary and mid-tier systems perform above baseline through structure and routing
- reduce dependence on frontier-only access by using structure as a capability amplifier

Recovered formulation:
- HLF is a capability amplifier
- the whole ecosystem should become more powerful and more usable

## 3. Product Direction

The merge target is not just “have an MCP server.”

The merge target is to pull HLF out of the broader Sovereign OS and make it stand on its own as a fully coherent product that still preserves the full vision stated in the source repo.

That standalone product is represented most clearly by:
- `README.md`
- `hlf_mcp/server.py`

The direction is:
- preserve the full HLF vision from Sovereign OS
- normalize it into a canonical, standalone HLF package and MCP server
- ensure README, tools, resources, compiler, VM, governance, and memory all agree

## 4. Canonical Design Principles

### A. One source of truth per domain

The surviving blueprint makes this explicit.

Each domain should have one canonical source, with other artifacts generated from it.

Examples:
- grammar spec is canonical
- bytecode spec is canonical
- host function registry is canonical
- docs and inventories should be derived, not hand-maintained drift zones

### B. Split docs by truth level

There are three truth classes:
- normative: what is true by spec
- generated: what is true for this commit
- roadmap: what is planned

This matters because current drift is partly caused by mixing all three inside README claims.

### C. HLF must become a layered standard

Recovered official profiles:
- HLF-Core
- HLF-Effects
- HLF-Agent
- HLF-Memory
- HLF-VM

### D. HLF must support five interchangeable surfaces

Recovered surfaces:
- glyph source
- ASCII source
- JSON AST
- bytecode `.hlb`
- English audit / human-readable explanation

## 5. What The Full Vision Includes

From the source Sovereign README and the standalone README, the intended HLF stack includes all of the following categories, not just parsing:

### Language and compiler
- deterministic grammar
- canonical formatting
- linting
- AST generation
- bytecode generation
- disassembly

### Runtime and safety
- gas metering
- effect boundaries
- capsule validation by tier
- governed host function calls
- reproducible execution

### Memory
- Infinite RAG style memory
- provenance and auditability
- semantic query interface
- memory stats and lifecycle awareness

### Lifecycle and orchestration
- Instinct SDD lifecycle
- spec-driven execution stages
- mission/state progression

### Translation and human legibility
- English to HLF
- HLF to English
- AST-level explanation
- bytecode-level explanation

### Governance
- ALIGN rules
- host function governance
- bytecode spec
- multilingual tag registry
- audit and manifest integrity

### Delivery surface
- MCP server
- stdio, SSE, streamable HTTP
- clear tools and resources
- Docker/local install path

## 6. Wiring And Flow

The recovered wiring is this:

1. Source or English intent enters the system.
2. Source is normalized and parsed deterministically.
3. Governance and validation gates run before execution.
4. AST is treated as a canonical intermediate meaning layer.
5. AST compiles to bytecode for reproducible execution.
6. Runtime executes under gas and capsule constraints.
7. Host functions are mediated through explicit registry rules.
8. Memory writes and reads are treated as governed, queryable system capabilities.
9. MCP exposes these capabilities as tools and resources to external agents.
10. Human-readable decompilation and audit views keep the system explainable.

Short version:

English or glyph source -> canonical AST -> validated effects and governance -> bytecode -> bounded runtime -> governed tools and memory -> MCP exposure -> human auditability

## 7. What Is Broken Right Now

The main break is not that HLF is unknowable.

The main break is canonicality drift.

Current drift zones recovered from surviving analysis:
- source Sovereign MCP bridge docs do not match its tool count
- standalone HLF_MCP README counts do not match its own tables
- standalone FastMCP server inventory is ahead of the README summary
- local uncommitted retrofit work mixes the old provider surface and the new standalone product surface

This means the core task is architectural reconciliation, not blind new feature work.

## 8. Canonical Merge Goal

The likely intended merge goal from the lost session was:

Take the full HLF vision expressed in `hlf_source/README.md` and related source docs, then fold it into the standalone HLF_MCP product in a way that is canonical, testable, and internally consistent.

That requires:
- choosing one canonical MCP surface
- choosing one canonical compiler/runtime path
- eliminating duplicated legacy-vs-new tool inventories
- aligning README claims with actual code
- preserving the full HLF scope, not reducing it to a toy DSL

## 9. Practical Working Assumptions Going Forward

These are safe assumptions for continuing implementation:

1. The standalone HLF_MCP repo is supposed to embody the full HLF vision, not just a minimal demo.
2. The source Sovereign repo is the richest vision/reference source, but not the final canonical implementation for this standalone repo.
3. The standalone `README.md` is the clearest product-spec target, but it currently drifts and must be corrected against code.
4. The local uncommitted work is a partially completed merge attempt and should be evaluated as convergence work, not as final truth.
5. HLF work should be judged against determinism, bounded capability, canonical semantics, and explicit governance.

## 10. Immediate Implementation Doctrine

Until the repo is reconciled, use this doctrine:

- Do not shrink the vision just to make pieces compile.
- Do not treat README counts as authoritative without verifying inventories.
- Do not merge legacy and new surfaces without naming the canonical target.
- Do preserve the HLF identity as a deterministic, governed language stack.
- Do prioritize one source of truth for grammar, bytecode, host functions, and MCP inventory.
