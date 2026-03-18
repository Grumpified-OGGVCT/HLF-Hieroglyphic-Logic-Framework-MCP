# HLF Memory Governance Recovery Spec

## Purpose
Establish a normalization and recovery plan for the knowledge substrate and memory subsystem, ensuring explicit ownership boundaries, governance, and full alignment with the original HLF vision.

## Scope
- Canonical front-door files: hlf/infinite_rag_hlf.py, hlf_mcp/rag/memory.py, scripts/run_pipeline_scheduled.py, hlf_mcp/weekly_artifacts.py, governance/host_functions.json, governance/bytecode_spec.yaml
- Weekly knowledge ingestion, recall, and artifact generation
- Infinite RAG, dependency-aware retrieval, host function contracts
- Pass-by-reference, pointer trust, provenance chains, memory sanitization, and evidence discipline

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

---
