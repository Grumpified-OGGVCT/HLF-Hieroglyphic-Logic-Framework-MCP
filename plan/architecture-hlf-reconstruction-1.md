---
goal: HLF reconstruction architecture plan from doctrinal north-star to executable recovery work
version: 1.0
date_created: 2026-03-17
last_updated: 2026-03-17
owner: GitHub Copilot
status: Planned
tags: [architecture, refactor, reconstruction, bridge, doctrine, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan converts the active HLF doctrine, extraction ledgers, and source-archaeology inputs into a deterministic reconstruction program for the standalone HLF MCP repository. The plan is intentionally bridge-lane work: it does not flatten the vision lane and it does not treat the current packaged surface as sufficient by default.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the three-lane model defined by `AGENTS.md`, `HLF_VISION_DOCTRINE.md`, `SSOT_HLF_MCP.md`, and `HLF_ACTIONABLE_PLAN.md`.
- **REQ-002**: Convert README-scale north-star claims into executable repo work instead of deleting or toning them down.
- **REQ-003**: Build recovery around constitutive HLF pillars: governance, routing, orchestration, verification, memory, audit, personas, and ecosystem interfaces.
- **REQ-004**: Produce artifacts that another agent can execute without re-deriving architectural intent from chat history.
- **REQ-005**: Separate source-only context from packaged-runtime truth while still preserving lineage to the Sovereign source repo.
- **REQ-006**: Use `HLF_SOURCE_EXTRACTION_LEDGER.md` and `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` as primary recovery maps.
- **REQ-007**: Use the top-priority source targets already ranked in `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` as the first archaeological batch.
- **REQ-008**: Turn “Rosetta Stone for Machines” README language into measured implementation work for canonicality, determinism, governance, and recovery.
- **SEC-001**: Recovery work must not weaken fail-closed governance, capsule boundaries, or auditability.
- **SEC-002**: Recovery work must not silently promote advisory retrieval, routing, or persona doctrine into runtime authority without an explicit contract.
- **ARC-001**: Damaged surfaces must be classified only as `strong but misaligned`, `strong but not yet packaged`, `wrongly replaced`, or `wrongly deleted`.
- **ARC-002**: Every restoration or port must cite upstream source lineage and target file ownership.
- **CON-001**: Do not import the entire Sovereign OS wholesale.
- **CON-002**: Do not use “packaged core neatness” as a deciding heuristic for omission.
- **CON-003**: Do not replace stronger source architecture with pseudo-equivalents or thin stand-ins.
- **CON-004**: Do not overwrite unrelated user changes already present in the working tree.
- **GUD-001**: Prefer faithful porting of constitutive logic, or explicit source-only retention rationale when not yet ported.
- **GUD-002**: Prefer additive artifacts first: audits, maps, plans, generated inventories, targeted restoration batches.
- **PAT-001**: First establish recovery authority, then restore missing pillars, then operationalize README claims, then consolidate canonical product boundaries.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Produce a rejected-extraction audit that closes the gap between current packaged surfaces and the broader constitutive HLF architecture.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` documenting every source surface in `HLF_SOURCE_EXTRACTION_LEDGER.md` currently marked `missing`, `optional`, `OS-bound`, `process-only`, or `superseded` that may still be constitutive. |  |  |
| TASK-002 | For each source surface in the audit, record: upstream path, current classification, target classification, why it matters to HLF, whether it belongs in packaged runtime, doctrine, bridge, or source-only context. |  |  |
| TASK-003 | Use the ten ranked targets in `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` as the first audit batch: `hlf_source/AGENTS.md`, `agents/gateway/bus.py`, `agents/gateway/router.py`, `agents/core/formal_verifier.py`, `agents/core/plan_executor.py`, `agents/core/crew_orchestrator.py`, `config/personas/steward.md`, `governance/ALIGN_LEDGER.yaml`, `docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, `scripts/run_hlf_gallery.py`. |  |  |
| TASK-004 | Add a per-surface recovery disposition column with only these values: `restore`, `faithful_port`, `bridge_contract`, `source_only_for_now`. |  |  |

### Implementation Phase 2

- **GOAL-002**: Build a pillar map that defines the real HLF reconstruction stack rather than package-shaped cleanup work.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `docs/HLF_PILLAR_MAP.md` with one section per pillar: semantic core, effects/capabilities, governance spine, routing fabric, orchestration/lifecycle, formal verification, memory/audit, personas/operator doctrine, ecosystem integration, operator-legibility surfaces. |  |  |
| TASK-006 | For each pillar in `docs/HLF_PILLAR_MAP.md`, map current local state to one of the four required damage classifications and name the controlling files under `hlf_mcp/`, `hlf/`, `governance/`, `docs/`, and `hlf_source/`. |  |  |
| TASK-007 | Record which pillars are already strong in packaged form, which are only represented as doctrine, which are only represented upstream, and which are currently mis-modeled. |  |  |
| TASK-008 | Link each pillar to the relevant bridge documents: `HLF_ACTIONABLE_PLAN.md`, `HLF_CANONICALIZATION_MATRIX.md`, `HLF_IMPLEMENTATION_INDEX.md`, and `HLF_MCP_TODO.md`. |  |  |

### Implementation Phase 3

- **GOAL-003**: Turn README-scale ambition into measurable restoration batches instead of leaving it as blended prose.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` mapping major README claims to one of: `implemented now`, `bridge work`, `vision only`, `source-context evidence`. |  |  |
| TASK-010 | Add exact claim rows for deterministic orchestration, five-surface language, cryptographic governance, gas metering, infinite RAG, Instinct lifecycle, ethical governor, formal verification, routing, ecosystem integration, and operator trust surfaces. |  |  |
| TASK-011 | For every row marked `bridge work`, define the proving artifact required: test suite, generated inventory, benchmark, control matrix, recovery port, or packaged contract. |  |  |
| TASK-012 | Cross-link the matrix back to `README.md`, `SSOT_HLF_MCP.md`, and `HLF_QUALITY_TARGETS.md` so the repo can keep strong ambition without reintroducing drift. |  |  |

### Implementation Phase 4

- **GOAL-004**: Execute the first real recovery batch against constitutive upstream files instead of continuing with generic cleanup.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Read and compare `hlf_source/agents/gateway/bus.py` and `hlf_source/agents/gateway/router.py` against current packaged routing and runtime surfaces to determine whether a packaged governance-routing bridge contract is missing. |  |  |
| TASK-014 | Read and compare `hlf_source/agents/core/formal_verifier.py` against the current packaged verification surface and decide whether to restore verifier contracts under `hlf_mcp/hlf/` or expose them as MCP-adjacent bridge tooling first. |  |  |
| TASK-015 | Read and compare `hlf_source/scripts/run_hlf_gallery.py` against current `fixtures/`, support tooling, and docs generation to decide whether a packaged gallery compiler/report tool should be restored. |  |  |
| TASK-016 | Read and compare `hlf_source/config/personas/steward.md` and related persona doctrine files against current agent handoff docs to determine what governance/operator doctrine remains wrongly downgraded. |  |  |

### Implementation Phase 5

- **GOAL-005**: Define the first faithful restoration targets and the exact repo files that will own them.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Add `docs/HLF_RECOVERY_BATCH_1.md` naming the first faithful restoration or bridge-port targets chosen from the audit and pillar map. |  |  |
| TASK-018 | For each selected target, specify: upstream file, packaged target file, owner module, public contract, tests to add, docs to update, and what must remain source-only for now. |  |  |
| TASK-019 | Define the first recovery acceptance gates: upstream lineage recorded, packaged tests added, generated inventory refreshed, README operationalization row updated, and no weakening of governance boundaries. |  |  |
| TASK-020 | Update `HLF_MCP_TODO.md` and `TODO.md` with only the recovery tasks selected for Batch 1 so implementation execution stops being abstract. |  |  |

## 3. Alternatives

- **ALT-001**: Rewrite the README again and treat stronger prose as progress. Rejected because the repo already has north-star language; the missing artifact is executable recovery sequencing.
- **ALT-002**: Keep working only inside `hlf_mcp/` without upstream archaeology. Rejected because doctrine explicitly identifies omitted constitutive surfaces as the core problem.
- **ALT-003**: Import large sections of the Sovereign repo wholesale. Rejected because the merge doctrine requires minimum-complete HLF extraction, not full OS duplication.
- **ALT-004**: Treat all routing, persona, orchestration, and ecosystem surfaces as OS-only. Rejected because the source context map already shows these can be constitutive to HLF’s governed meaning layer.

## 4. Dependencies

- **DEP-001**: `AGENTS.md`
- **DEP-002**: `HLF_VISION_DOCTRINE.md`
- **DEP-003**: `SSOT_HLF_MCP.md`
- **DEP-004**: `HLF_ACTIONABLE_PLAN.md`
- **DEP-005**: `HLF_CANONICALIZATION_MATRIX.md`
- **DEP-006**: `HLF_SOURCE_EXTRACTION_LEDGER.md`
- **DEP-007**: `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`
- **DEP-008**: `HLF_MCP_TODO.md`
- **DEP-009**: upstream source repo at `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF`

## 5. Files

- **FILE-001**: `plan/architecture-hlf-reconstruction-1.md` — this implementation plan
- **FILE-002**: `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` — to be created in Phase 1
- **FILE-003**: `docs/HLF_PILLAR_MAP.md` — to be created in Phase 2
- **FILE-004**: `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` — to be created in Phase 3
- **FILE-005**: `docs/HLF_RECOVERY_BATCH_1.md` — to be created in Phase 5
- **FILE-006**: `HLF_MCP_TODO.md` — update selected recovery tasks after batch definition
- **FILE-007**: `TODO.md` — update selected recovery tasks after batch definition

## 6. Testing

- **TEST-001**: Validate every new audit or pillar-map document against the source files it cites; no unlabeled source claims allowed.
- **TEST-002**: For each recovery batch, add or update targeted tests in `tests/` covering the restored contract or package-level bridge surface.
- **TEST-003**: If a source surface is ported into `hlf_mcp/`, run `uv run pytest tests/ -q --tb=short` after implementation.
- **TEST-004**: If a generated inventory or README-operationalization matrix is updated, verify that counts, labels, and stated contracts align with the actual packaged server surface and governance files.

## 7. Risks & Assumptions

- **RISK-001**: Upstream files may embed doctrine and runtime logic together, making direct extraction non-trivial.
- **RISK-002**: Recovery work can accidentally promote source-only operator doctrine into runtime authority without an explicit bridge contract.
- **RISK-003**: Existing branch-local edits may already be moving parts of this plan, so each touched file must be reviewed before modification.
- **RISK-004**: Strong README language may tempt future sessions to skip the proving artifacts and restate ambition as if it were implemented.
- **ASSUMPTION-001**: The local upstream source checkout at `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF` remains available for archaeology.
- **ASSUMPTION-002**: The packaged product surface remains `hlf_mcp/` unless a future bridge document explicitly changes that ownership.

## 8. Related Specifications / Further Reading

[AGENTS.md](../AGENTS.md)
[HLF_VISION_DOCTRINE.md](../HLF_VISION_DOCTRINE.md)
[SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
[HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
[HLF_CANONICALIZATION_MATRIX.md](../HLF_CANONICALIZATION_MATRIX.md)
[HLF_SOURCE_EXTRACTION_LEDGER.md](../HLF_SOURCE_EXTRACTION_LEDGER.md)
[HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md](../HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)