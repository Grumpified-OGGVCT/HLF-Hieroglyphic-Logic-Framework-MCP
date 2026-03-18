---
goal: Complete HLF reconstruction planning from stitched doctrine to executable recovery batches
version: 2.0
date_created: 2026-03-17
last_updated: 2026-03-17
owner: GitHub Copilot
status: 'In progress'
tags: [architecture, reconstruction, planning, bridge, doctrine, recovery, hlf]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This is the master reconstruction plan for HLF in this repository. It replaces shortcut planning with a full bridge program that ties together the stitched vision docs, present-tense truth docs, source archaeology, recovery sequencing, and acceptance criteria.

This plan is intentionally larger than a normal feature plan because the problem is larger than a feature. The repo is recovering from architectural narrowing. The plan therefore covers documentation authority, source archaeology, ownership boundaries, restoration sequencing, proof surfaces, and backlog normalization.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the three-lane structure: vision, current truth, and bridge.
- **REQ-002**: Treat `docs/HLF_STITCHED_SYSTEM_VIEW.md` as the stitched overview, not as a substitute for the stricter truth or bridge docs.
- **REQ-003**: Use `docs/HLF_VISION_PLAIN_LANGUAGE.md`, `docs/HLF_VISION_MAP.md`, and `docs/HLF_MISSING_PILLARS.md` as the new vision-system baseline.
- **REQ-004**: Use `SSOT_HLF_MCP.md` as the present-tense build truth boundary.
- **REQ-005**: Use `HLF_SOURCE_EXTRACTION_LEDGER.md` and `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` as the authoritative source-archaeology inputs.
- **REQ-006**: Convert missing-pillar analysis into explicit recovery batches with file ownership, acceptance gates, and update rules for backlog documents.
- **REQ-007**: Produce artifacts that another agent can execute without reconstructing the repo history from chat.
- **REQ-008**: Every recovery target must name upstream source, local target, ownership boundary, and validation path.
- **REQ-009**: Planning must cover both documentation reconstruction and code restoration sequencing.
- **REQ-010**: Planning must include what is already complete so future agents do not redo finished framing work.
- **SEC-001**: No planning step may weaken governance, fail-closed behavior, capsule boundaries, or auditability.
- **SEC-002**: No source-only doctrine may become runtime authority without an explicit bridge contract and test plan.
- **SEC-003**: No recovery batch may silently widen permissions or host-function effects without governance updates.
- **ARC-001**: Every damaged area must be classified only as `strong but misaligned`, `strong but not yet packaged`, `wrongly replaced`, or `wrongly deleted`.
- **ARC-002**: Recovery must rebuild from original HLF intent outward, not from a packaged MVP inward.
- **ARC-003**: Missing constitutive surfaces must be ranked by architectural importance, not by implementation ease.
- **CON-001**: Do not import the entire Sovereign OS wholesale.
- **CON-002**: Do not treat the packaged `hlf_mcp/` surface as the full HLF target.
- **CON-003**: Do not use pseudo-equivalents, thin stand-ins, or generic wrappers as substitutes for stronger source architecture.
- **CON-004**: Do not rewrite unrelated files just to make the plan look cleaner.
- **CON-005**: Do not mark a recovery area complete until the proving artifact named in the plan exists.
- **GUD-001**: Prefer additive planning artifacts first, then targeted restoration specs, then code restoration.
- **GUD-002**: Keep the bridge plan machine-readable and versioned under `/plan/`.
- **GUD-003**: Update repo-visible planning entry points so future work starts from the stitched architecture rather than a reduced story.
- **PAT-001**: Plan in this order: authority normalization, archaeology, pillar mapping, recovery specs, batch sequencing, proof surfaces, backlog normalization.

## 2. Implementation Steps

### Implementation Phase 0

- **GOAL-000**: Preserve and register the planning surfaces that are already complete so later work builds on them instead of replacing them.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-000 | Keep `docs/HLF_VISION_PLAIN_LANGUAGE.md` as the plain-language vision statement. | ✅ | 2026-03-17 |
| TASK-001 | Keep `docs/HLF_VISION_MAP.md` as the file-backed evidence map from ideas to repo surfaces. | ✅ | 2026-03-17 |
| TASK-002 | Keep `docs/HLF_MISSING_PILLARS.md` as the pillar gap classifier. | ✅ | 2026-03-17 |
| TASK-003 | Keep `docs/HLF_STITCHED_SYSTEM_VIEW.md` as the top-level stitched overview. | ✅ | 2026-03-17 |
| TASK-004 | Update `AGENTS.md` startup ordering to route future sessions through the stitched docs first. | ✅ | 2026-03-17 |

### Implementation Phase 1

- **GOAL-001**: Normalize planning authority so the repo has one explicit master reconstruction sequence rather than scattered intent.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `plan/architecture-hlf-reconstruction-2.md` as the versioned master plan that supersedes the earlier partial planning sketch in `plan/architecture-hlf-reconstruction-1.md`. | ✅ | 2026-03-17 |
| TASK-006 | Update `HLF_ACTIONABLE_PLAN.md` to point readers at `plan/architecture-hlf-reconstruction-2.md` as the master reconstruction sequencing artifact. |  |  |
| TASK-007 | Add a brief reference to `plan/architecture-hlf-reconstruction-2.md` in `docs/HLF_STITCHED_SYSTEM_VIEW.md` so the stitched overview points to an execution plan, not just concept docs. |  |  |
| TASK-008 | Add a brief reference to `plan/architecture-hlf-reconstruction-2.md` in `README.md` under the bridge reading path so new readers can find the actual recovery sequence. |  |  |

### Implementation Phase 2

- **GOAL-002**: Create the complete archaeology and classification layer for omitted or downgraded HLF pillars.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` covering every source surface currently treated as `missing`, `superseded`, `optional`, `process-only`, or `OS-bound` where the surface may still be constitutive to HLF. |  |  |
| TASK-010 | For each surface in `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`, record: upstream path, current ledger classification, corrected classification, why it matters, whether it is runtime, doctrine, operator, or source-only context, and proposed disposition. |  |  |
| TASK-011 | Seed the audit with the top ranked files already identified in `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`: `hlf_source/AGENTS.md`, `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/core/formal_verifier.py`, `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, `hlf_source/config/personas/steward.md`, `hlf_source/governance/ALIGN_LEDGER.yaml`, `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, and `hlf_source/scripts/run_hlf_gallery.py`. |  |  |
| TASK-012 | Add a deterministic disposition field for every audited file with only these values: `restore`, `faithful_port`, `bridge_contract`, `source_only_for_now`, `not_hlf_core`. |  |  |

### Implementation Phase 3

- **GOAL-003**: Convert the pillar classification into an ownership map that future implementation can follow without guessing.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Create `docs/HLF_PILLAR_MAP.md` with one section per pillar: semantic core, governance spine, effect algebra, runtime/bytecode, routing fabric, orchestration lifecycle, formal verification, memory/audit, persona doctrine, ecosystem integration, operator gallery/trust surfaces. |  |  |
| TASK-014 | For each pillar, map the local ownership boundary across `hlf_mcp/`, `hlf/`, `governance/`, `docs/`, and `hlf_source/`. |  |  |
| TASK-015 | For each pillar, record the current state using only the approved damage classes and name the exact files supporting that decision. |  |  |
| TASK-016 | For each pillar, record the preferred next action using only the approved dispositions: `restore`, `faithful_port`, `bridge_contract`, or `source_only_for_now`. |  |  |

### Implementation Phase 4

- **GOAL-004**: Operationalize the README and stitched-vision claims so ambition stays connected to proof.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Create `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` mapping major public claims to one of: `implemented now`, `bridge work`, `vision only`, `source-context evidence`. |  |  |
| TASK-018 | Add rows for these specific claim families: governed meaning layer, deterministic orchestration, five-surface language, cryptographic governance, gas metering, memory substrate, Instinct lifecycle, formal verification, routing, code generation, human-readable audit, ecosystem integration. |  |  |
| TASK-019 | For every row marked `bridge work`, define the proving artifact required: regression tests, benchmark, governance control matrix, trace artifact, generated inventory, code restoration spec, or runtime contract. |  |  |
| TASK-020 | Link each matrix row back to `README.md`, `SSOT_HLF_MCP.md`, `HLF_QUALITY_TARGETS.md`, and the relevant pillar section in `docs/HLF_PILLAR_MAP.md`. |  |  |

### Implementation Phase 5

- **GOAL-005**: Produce faithful recovery specifications for the first missing pillar clusters rather than jumping straight to code with half-understood scope.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Create `docs/HLF_ROUTING_RECOVERY_SPEC.md` covering `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, and `hlf_source/agents/gateway/sentinel_gate.py`: what should be restored, what should become a bridge contract, and what remains source-only. |  |  |
| TASK-022 | Create `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` covering `hlf_source/agents/core/formal_verifier.py` and any related current local verification surfaces. |  |  |
| TASK-023 | Create `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` covering `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, and `hlf_source/agents/core/task_classifier.py`. |  |  |
| TASK-024 | Create `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` covering governed memory contracts, provenance schema, freshness, trust tiers, context pruning, and chain verification. |  |  |
| TASK-025 | Create `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` covering `hlf_source/config/personas/*.md`, `hlf_source/AGENTS.md`, and how persona doctrine should influence runtime, docs, or operator guidance without becoming uncontrolled code authority. |  |  |
| TASK-026 | Create `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` covering `hlf_source/scripts/run_hlf_gallery.py`, explainer surfaces, and operator-legibility assets. |  |  |

### Implementation Phase 6

- **GOAL-006**: Convert the recovery specifications into ranked executable restoration batches.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-027 | Create `docs/HLF_RECOVERY_BATCH_1.md` naming the first implementation batch. This batch must include exact upstream files, exact target files, the ownership module, required tests, required docs updates, and acceptance gates. |  |  |
| TASK-028 | Create `docs/HLF_RECOVERY_BATCH_2.md` naming the second implementation batch using the same structure. |  |  |
| TASK-029 | Rank batch priority using architectural importance first: routing fabric, formal verification, orchestration lifecycle, memory governance, persona doctrine integration, gallery/operator surfaces. |  |  |
| TASK-030 | Add an explicit reason for every pillar not selected for Batch 1 so the repo does not silently forget unselected work. |  |  |

### Implementation Phase 7

- **GOAL-007**: Define the code-restoration sequence for Batch 1 with no ambiguity.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-031 | Create `plan/feature-routing-fabric-1.md` if Batch 1 starts with routing. Include file-level steps, target tests, dependency order, and rollback points. |  |  |
| TASK-032 | Create `plan/feature-formal-verifier-1.md` if Batch 1 includes formal verification. Include target module ownership and required governance/CLI/MCP exposure decisions. |  |  |
| TASK-033 | Create `plan/feature-orchestration-lifecycle-1.md` if Batch 1 includes orchestration surfaces. Include contract boundaries so runtime and operator-layer code do not get mixed blindly. |  |  |
| TASK-034 | Add a deterministic decision rule in each feature plan stating what belongs in packaged runtime, what belongs in docs/operator surfaces, and what stays source-only for now. |  |  |

### Implementation Phase 8

- **GOAL-008**: Build the proof and verification surfaces that make restored work claimable.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-035 | Create `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` mapping manifest assets, align rules, host-function contracts, capsules, and any restored routing/verifier surfaces to operational controls. |  |  |
| TASK-036 | Create `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md` listing the exact rules a restoration must meet before it can be marked complete. |  |  |
| TASK-037 | Define the minimum regression suite additions required for each restoration class: runtime, routing, verifier, orchestration, memory, persona/operator. |  |  |
| TASK-038 | Define the minimum generated artifact refresh required for each restoration class: docs generation, fixture coverage, manifest checks, resource/tool counts, gallery output, trace verification. |  |  |

### Implementation Phase 9

- **GOAL-009**: Normalize the repo backlog so the planning system drives execution instead of drifting apart.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-039 | Update `HLF_MCP_TODO.md` so recovery tasks are grouped by pillar and batch, not just by historical topic accumulation. |  |  |
| TASK-040 | Update `TODO.md` so the high-level backlog points to the master plan, batch docs, and recovery specs instead of duplicating them loosely. |  |  |
| TASK-041 | Update `HLF_ACTIONABLE_PLAN.md` to retain its broader implementation value while explicitly deferring reconstruction sequencing authority to `plan/architecture-hlf-reconstruction-2.md`. |  |  |
| TASK-042 | Verify that `AGENTS.md`, `README.md`, and `docs/HLF_STITCHED_SYSTEM_VIEW.md` all point to the same current planning entry points. |  |  |

## 3. Alternatives

- **ALT-001**: Continue with the earlier partial reconstruction sketch in `plan/architecture-hlf-reconstruction-1.md` and infer the rest during implementation. Rejected because it leaves too many ownership and acceptance decisions implicit.
- **ALT-002**: Treat `HLF_ACTIONABLE_PLAN.md` and `HLF_MCP_TODO.md` as enough planning. Rejected because they contain valuable work but do not fully sequence archaeology, batching, proof surfaces, and ownership boundaries.
- **ALT-003**: Skip recovery specs and jump straight into coding from the top-ranked source files. Rejected because this is how narrowing, pseudo-equivalents, and accidental omissions happen again.
- **ALT-004**: Merge upstream doctrine and runtime code wholesale. Rejected because the repo must recover the real HLF shape without becoming an uncontrolled clone of the full Sovereign OS.
- **ALT-005**: Freeze planning at the documentation layer and defer all code sequencing until later. Rejected because the user explicitly asked to complete the planning with no shortcuts.

## 4. Dependencies

- **DEP-001**: `AGENTS.md`
- **DEP-002**: `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- **DEP-003**: `docs/HLF_VISION_PLAIN_LANGUAGE.md`
- **DEP-004**: `docs/HLF_VISION_MAP.md`
- **DEP-005**: `docs/HLF_MISSING_PILLARS.md`
- **DEP-006**: `HLF_VISION_DOCTRINE.md`
- **DEP-007**: `SSOT_HLF_MCP.md`
- **DEP-008**: `HLF_ACTIONABLE_PLAN.md`
- **DEP-009**: `HLF_CANONICALIZATION_MATRIX.md`
- **DEP-010**: `HLF_IMPLEMENTATION_INDEX.md`
- **DEP-011**: `HLF_SOURCE_EXTRACTION_LEDGER.md`
- **DEP-012**: `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`
- **DEP-013**: `HLF_MCP_TODO.md`
- **DEP-014**: `TODO.md`
- **DEP-015**: upstream repo at `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF`

## 5. Files

- **FILE-001**: `plan/architecture-hlf-reconstruction-1.md` — earlier partial reconstruction sketch retained for history
- **FILE-002**: `plan/architecture-hlf-reconstruction-2.md` — master reconstruction plan
- **FILE-003**: `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` — archaeology and disposition audit
- **FILE-004**: `docs/HLF_PILLAR_MAP.md` — pillar ownership and state map
- **FILE-005**: `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` — claim-to-proof matrix
- **FILE-006**: `docs/HLF_ROUTING_RECOVERY_SPEC.md` — routing restoration spec
- **FILE-007**: `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` — verifier restoration spec
- **FILE-008**: `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` — orchestration restoration spec
- **FILE-009**: `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` — memory/provenance restoration spec
- **FILE-010**: `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` — persona/operator doctrine spec
- **FILE-011**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` — gallery/operator surface spec
- **FILE-012**: `docs/HLF_RECOVERY_BATCH_1.md` — first executable restoration batch
- **FILE-013**: `docs/HLF_RECOVERY_BATCH_2.md` — second executable restoration batch
- **FILE-014**: `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` — control and proof matrix
- **FILE-015**: `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md` — completion rules for restorations
- **FILE-016**: `HLF_ACTIONABLE_PLAN.md` — broader action plan updated to point at the master reconstruction plan
- **FILE-017**: `HLF_MCP_TODO.md` — backlog normalized by pillar and batch
- **FILE-018**: `TODO.md` — high-level backlog normalized by plan and batch
- **FILE-019**: `README.md` — bridge path updated to point at the master plan
- **FILE-020**: `docs/HLF_STITCHED_SYSTEM_VIEW.md` — overview updated to point at the master plan

## 6. Testing

- **TEST-001**: Validate every new planning or audit doc against the actual file paths it cites. No guessed file references are allowed.
- **TEST-002**: For each recovery spec, verify that the source files named in the spec exist in `hlf_source/` before implementation begins.
- **TEST-003**: For each batch doc, verify that every target file has an owner module and a defined acceptance gate.
- **TEST-004**: For each backlog update, verify that `HLF_MCP_TODO.md`, `TODO.md`, and `HLF_ACTIONABLE_PLAN.md` do not contradict the master plan.
- **TEST-005**: Before any code restoration begins, verify that the relevant feature plan under `/plan/` exists and names exact test files to run or add.
- **TEST-006**: After future code restoration, run the smallest exact regression scope first, then broader repo validation, instead of skipping straight to vague “seems good” claims.

## 7. Risks & Assumptions

- **RISK-001**: Some upstream files combine doctrine, runtime, orchestration, and operational concerns in one module, which means restoration will require careful decomposition.
- **RISK-002**: Over-eager implementation may accidentally pull operator doctrine into runtime authority without a contract boundary.
- **RISK-003**: Existing local legacy modules under `hlf/` may look like substitutes for upstream pillars even where they are actually weaker or differently scoped.
- **RISK-004**: The backlog files already contain old planning layers, so normalization may surface contradictions that require explicit resolution.
- **RISK-005**: README and north-star language may still tempt future sessions to restate ambition without building the proving artifact.
- **ASSUMPTION-001**: The upstream source checkout remains available and readable locally.
- **ASSUMPTION-002**: The main packaged product surface remains `hlf_mcp/` unless a future bridge artifact explicitly changes that ownership.
- **ASSUMPTION-003**: The user wants full planning completion now, with implementation to follow as a separate stage unless explicitly continued.

## 8. Related Specifications / Further Reading

[AGENTS.md](../AGENTS.md)
[README.md](../README.md)
[docs/HLF_STITCHED_SYSTEM_VIEW.md](../docs/HLF_STITCHED_SYSTEM_VIEW.md)
[docs/HLF_VISION_PLAIN_LANGUAGE.md](../docs/HLF_VISION_PLAIN_LANGUAGE.md)
[docs/HLF_VISION_MAP.md](../docs/HLF_VISION_MAP.md)
[docs/HLF_MISSING_PILLARS.md](../docs/HLF_MISSING_PILLARS.md)
[HLF_VISION_DOCTRINE.md](../HLF_VISION_DOCTRINE.md)
[SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
[HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
[HLF_CANONICALIZATION_MATRIX.md](../HLF_CANONICALIZATION_MATRIX.md)
[HLF_IMPLEMENTATION_INDEX.md](../HLF_IMPLEMENTATION_INDEX.md)
[HLF_SOURCE_EXTRACTION_LEDGER.md](../HLF_SOURCE_EXTRACTION_LEDGER.md)
[HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md](../HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)
[TODO.md](../TODO.md)