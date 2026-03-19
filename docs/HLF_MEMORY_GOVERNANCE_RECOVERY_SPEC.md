---
goal: Recover governed memory as an evidence-bearing HLF substrate instead of a generic retrieval layer
version: 2.0
date_created: 2026-03-17
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [memory, provenance, recovery, governance, audit, hlf]
---

# HLF Memory Governance Recovery Spec

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

## Purpose

Establish a normalization and recovery plan for the knowledge substrate and memory subsystem, ensuring explicit ownership boundaries, governance, provenance, trust-tier semantics, and alignment with the original HLF vision.

## Scope

- Canonical front-door files: `hlf/infinite_rag_hlf.py`, `hlf_mcp/rag/memory.py`, `scripts/run_pipeline_scheduled.py`, `hlf_mcp/weekly_artifacts.py`, `governance/host_functions.json`, `governance/bytecode_spec.yaml`
- Upstream memory authority: `hlf_source/agents/core/memory_scribe.py`, `hlf_source/agents/core/context_pruner.py`, `hlf_source/scripts/verify_chain.py`
- Weekly knowledge ingestion, recall, and artifact generation
- Infinite RAG, dependency-aware retrieval, host function contracts
- Pass-by-reference, pointer trust, provenance chains, memory sanitization, forgetting curves, and evidence discipline

## Goals
1. Normalize fragmented memory/knowledge surfaces into a coherent subsystem
2. Define explicit ownership and governance boundaries
3. Make it mandatory that the subsystem exceeds generic AgentKB/AgentSKB capabilities (unbranded), rather than merely matching them
4. Preserve anti-reductionist doctrine: no simplification by omission
5. Document recovery steps, gaps, and bridge plan
6. Refit earlier memory-governance evidence into current local authority instead of discarding it

## Mandatory Unification Baseline

This repo is no longer allowed to treat a generic AgentKB-style memory layer as an acceptable end state.

The merged HLF target must exceed that baseline at the mandatory foundation level by wiring in:

1. governed pointer trust and pass-by-reference resolution
2. approval-aware memory writes and reviewable high-risk mutations
3. chained audit lineage for execution, recall, and storage events
4. freshness, recency, and tombstone-aware memory semantics
5. anti-poisoning and sanitization rules with explicit failure states
6. evidence-grade provenance that survives weekly ingest, summary generation, and replay
7. trust tiers, operator-legible review, and verifier-ready handoff surfaces

If a proposed knowledge subsystem does not exceed generic AgentKB/AgentSKB capability on those axes, it is below the HLF target and should be treated as incomplete bridge work.

## Recovery Plan
1. Inventory all memory/knowledge substrate files and contracts
2. Map subsystem boundaries and ownership
3. Identify fragmentation, gaps, and normalization targets
4. Define governance, provenance, and audit requirements
5. Specify recovery tasks and bridge implementation steps
6. Update actionable plan and TODOs
7. Explicitly reconcile prior evidence with current local adjustments using the assembly refit rule

## Immediate Actions
- Consolidate canonical front-door files
- Document subsystem boundaries and contracts
- Update HLF_MCP_TODO.md with normalization tasks
- Track progress in docs/HLF_MISSING_PILLARS.md and docs/HLF_STITCHED_SYSTEM_VIEW.md
- Add hash-chain, evidence-lineage, and pointer-integrity requirements to the memory contract
- Distinguish instruction-lane memory references from data-lane payload resolution

## Ownership Boundary
- Subsystem is owned by HLF_MCP, governed by host function contracts
- All memory/knowledge surfaces must be traceable and auditable
- External prior notes remain evidence inputs, but packaged local contracts remain current runtime authority

## Required Runtime Contract

Every governed memory object must be able to carry:

1. `source_class`
2. `source_path` or artifact identifier
3. `branch`
4. `commit_sha`
5. `collected_at`
6. `collector_version`
7. `confidence`
8. `freshness`
9. `trust_tier`
10. `pointer`
11. `supersedes`
12. `revoked` or tombstone state
13. `operator_summary`

These fields are not optional if the entry is used as route evidence, verifier evidence, weekly knowledge, or promoted exemplar memory.

## Implementation Phases

### Implementation Phase 1

- **GOAL-001**: Normalize the evidence schema and ownership boundary.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Define one packaged evidence schema shared by benchmark artifacts, weekly knowledge, exemplars, and memory recall outputs. |  |  |
| TASK-002 | Map ownership between `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, and `hlf_mcp/weekly_artifacts.py`. |  |  |
| TASK-003 | Define how pointer trust, supersession, expiry, and revocation are represented in packaged truth. |  |  |

### Implementation Phase 2

- **GOAL-002**: Recover governed memory lifecycle behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Port evidence-friendly storage and archival semantics from `memory_scribe.py` where they strengthen packaged memory contracts. |  |  |
| TASK-005 | Port forgetting-curve and pruning semantics from `context_pruner.py` as bounded-memory behavior rather than silent deletion. |  |  |
| TASK-006 | Add chain-verification and provenance verification hooks informed by `verify_chain.py`. |  |  |

### Implementation Phase 3

- **GOAL-003**: Prove memory governance with deterministic tests and operator surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add tests for stale artifact handling, supersession, revocation, and provenance-required recall. |  |  |
| TASK-008 | Add tests proving benchmark or weekly artifacts cannot influence routing or promotion without required evidence fields. |  |  |
| TASK-009 | Add operator-facing summaries that distinguish advisory retrieval from governed evidence. |  |  |

## Required Contract Additions

The local corpora and related recovery work now make the following additions mandatory to the memory-governance target:

1. provenance chains for memory writes and recalls
2. recency / lineage hash checks for stored memory blocks
3. anti-poisoning or sanitization rules for stale or mismatched memory
4. explicit pass-by-reference / pointer-resolution trust rules
5. evidence-discipline for weekly ingest so recall surfaces can be audited back to source artifacts
6. trust-tier and freshness semantics that survive translation between legacy and packaged memory surfaces
7. approval-ledger integration for privileged or destructive memory mutations
8. audit-chain sealing for memory and execution adjacency, not memory in isolation
9. witness-ready output contracts so future verifier/sentinel lanes can inspect memory lineage without reverse engineering ad hoc logs

## Refit Rule For Memory

Do not throw earlier memory-governance evidence away because local implementation has already advanced.

Instead:

- preserve the current local memory front door
- absorb older but still-valid provenance, hash-chain, sanitization, and pointer-trust semantics into the target contract
- record every unresolved gap as bridge work instead of simplifying the subsystem back down to generic storage and retrieval

## Bridge Implementation
- Recovery tasks must be tracked and validated
- No reduction of vision or scope

## Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `docs/HLF_README_OPERATIONALIZATION_MATRIX.md`
- `plan/architecture-hlf-reconstruction-2.md`

---
