---
goal: Expand HKS from the current bounded local-evaluation slice into the full governed knowledge substrate platform implied by doctrine and source extraction
version: 1.0
date_created: 2026-03-23
last_updated: 2026-03-24
owner: GitHub Copilot
status: In progress
tags: [architecture, hks, bridge, vision, current-truth, memory, retrieval, governance, multimodal, orchestration]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan exists because the bounded HKS slice already completed in the repo is real, but it is not the full HKS extraction target.

The completed slice proves only this narrower claim:

- HKS now has a packaged local-evaluation authority seam
- optional external comparison remains quarantined and bridge-only
- operator and native-comprehension surfaces expose that boundary at the MCP front door

That is useful bridge work.

It is not yet the larger HKS platform the repo doctrine, source extraction, and the user’s target architecture imply.

This plan restores the proper three-lane framing:

- `vision lane`: the full HKS platform target
- `current-truth lane`: what is actually packaged and validated now
- `bridge lane`: the sequence of architectural expansions required to converge from current truth toward the target without collapsing governance or fidelity

Working theme:

`HKS becomes the governed knowledge substrate, not merely a memory-backed comparator lane`

## Lane Classification

### Vision Lane

North-star HKS target:

- multi-tier cognitive memory architecture beyond simple hot/warm behavior
- hybrid lexical, semantic, graph, and code-aware retrieval
- weekly and on-demand ingestion with salience gating, archival, supersession, and provenance chains
- multimodal grounding across text, code, screenshots, diagrams, and structured artifacts
- runtime retrieval contracts that support deterministic tool use, repair, routing, and orchestration
- measurable knowledge-quality loops proving HKS improves actual HLF outcomes

### Current-Truth Lane

Packaged and validated today:

- Infinite RAG memory exists in `hlf_mcp/rag/memory.py`
- memory store/query/stats tools exist at the MCP front door
- translation contract exemplars are already remembered locally
- weekly workflow spine exists and can be extended
- bounded HKS local-evaluation and external-comparator quarantine contracts now exist
- operator surfaces for HKS evaluation and HKS external compare now exist
- native-comprehension packets for those HKS surfaces now exist
- focused front-door validation for the HKS discovery slice is green

### Bridge Lane

Missing but recoverable expansions:

- cognitive-stack memory separation
- salience-driven write gates and hierarchical archival
- uncertainty-aware retrieval gating
- graph-backed and multimodal retrieval
- code-aware chunking and incremental reindexing
- metadata-driven caching and prewarm
- drift/topic refresh loops for knowledge freshness
- runtime retrieval contracts that become first-class route, repair, and orchestration inputs

## 1. Requirements & Constraints

- **REQ-001**: Preserve three-lane doctrine in all HKS planning. Do not flatten vision into current truth or bridge into product-complete claims.
- **REQ-002**: Treat the completed bounded comparator slice as a subcomponent, not the whole HKS architecture.
- **REQ-003**: Keep local HKS evaluation as the only packaged admission and promotion authority unless a stricter local successor replaces it.
- **REQ-004**: HKS must evolve into a governed knowledge substrate for translation, repair, routing, orchestration, and execution support, not a generic retrieval bucket.
- **REQ-005**: The expanded platform must support weekly knowledge improvement without poisoning canonical truth with low-quality or stale external material.
- **REQ-006**: The platform must distinguish raw evidence, advisory knowledge, trusted exemplars, and route-eligible governed knowledge.
- **REQ-007**: The expanded architecture must remain operator-legible through status/report surfaces rather than hiding trust logic inside opaque memory internals.
- **REQ-008**: Use the source audit in `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` as bridge input only. Verified external techniques are not current-truth claims by default.
- **SEC-001**: No external backend may become required for HKS correctness.
- **SEC-002**: No knowledge record may be promoted to governed truth without local provenance, freshness, and authority checks.
- **SEC-003**: Retrieval contracts used by routing, verification, or execution must fail closed on missing provenance, stale evidence, or unresolved trust state.
- **CON-001**: Do not replace the current packaged system with a clean-room rewrite. Extend the real HKS seams that already exist.
- **CON-002**: Do not use vendor terminology as product truth inside packaged contracts unless deliberate compatibility requires it.
- **CON-003**: Avoid “architecture theater.” The bridge plan must name actual files, contracts, workflows, and tests.
- **GUD-001**: Prefer additive extraction and faithful restoration over broad speculative redesign.
- **GUD-002**: Build operator-facing proof surfaces at each major capability step.
- **PAT-001**: Treat HKS as a constitutive pillar that must converge with routing, repair, translation, and weekly evidence, not as an isolated subsystem.

## 2. Extraction Status Matrix

| Capability | Vision lane target | Current truth now | Extraction status | Bridge implication |
|---|---|---|---|---|
| Local HKS evaluation authority | Full admission, freshness, provenance, and promotion authority | Present in bounded form | partial | expand evaluation depth and usage sites |
| External comparator quarantine | Optional advisory comparator with explicit recheck boundary | Present | strong bounded slice | preserve as subordinate path only |
| Multi-tier cognitive memory | working, episodic, semantic, provenance archive, compressed cold archive | not present as explicit architecture | not extracted | add real memory strata and contracts |
| Salience-gated ingestion | write-time quality, novelty, corroboration, and archive routing | not present | not extracted | implement ingestion gates before scaling sources |
| Hybrid lexical + semantic + graph retrieval | all three active with metadata filters | lexical + semantic patterns only, limited | partial | add graph and metadata-first retrieval lanes |
| Code-aware retrieval | syntax-aware chunking, code/doc linking, repository intelligence | not first-class in HKS | partial | extend HKS ingest and retrieval around code artifacts |
| Incremental reindex / CDC | delta updates, change-driven refresh | not formalized | not extracted | add source watchers and selective re-embed paths |
| Metadata-driven caching | evidence bundles, TTLs, validation tier, hot reuse | not formalized | not extracted | add retrieval cache contracts |
| Multimodal grounding | text, code, screenshots, diagrams, graph entities | not present | not extracted | add modality-specific stores and evidence assembly |
| Runtime retrieval contracts | route, repair, verifier, and codegen all consume governed HKS contracts | partial in recall/exemplar paths | partial | widen downstream consumers |
| Weekly knowledge upgrade loop | source intake, evaluation, promotion, supersession, deprecation | weekly spine exists, HKS integration is narrow | partial | connect workflows to HKS-native admission and refresh |
| KPI / evaluation loop | measures real runtime improvement, not just KB growth | not formalized | not extracted | add benchmark and quality loops |

## 3. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Make the extraction state explicit so the repo stops treating one bounded slice as if HKS is largely complete.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-001 | Create this plan in `plan/architecture-hks-platform-expansion-1.md` and explicitly classify HKS by `vision`, `current truth`, and `bridge`. | ✅ | 2026-03-23 |
| TASK-002 | Update the HKS planning narrative so the bounded comparator slice is recorded as one completed bridge segment, not the full platform extraction. |  |  |
| TASK-003 | Add a capability matrix to HKS planning artifacts showing which target capabilities are fully extracted, partially extracted, or not yet extracted. |  |  |

### Implementation Phase 2

- **GOAL-002**: Expand memory architecture from the current bounded memory layer into an explicit cognitive-stack HKS substrate.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-004 | Refactor `hlf_mcp/rag/memory.py` to distinguish at minimum: working context, episodic trace records, semantic knowledge nodes, provenance records, and archived cold artifacts. | ✅ | 2026-03-23 |
| TASK-005 | Define durable contracts for supersession, revocation, tombstoning, and archival lineage across those tiers. | ✅ | 2026-03-23 |
| TASK-006 | Extend `hlf_mcp/server_context.py` and HKS persistence surfaces so these layers are queryable and operator-visible rather than implicit. | ✅ | 2026-03-23 |

### Implementation Phase 3

- **GOAL-003**: Add salience-driven write-time gating and governed archival so ingestion quality is controlled before retrieval quality degrades.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-007 | Add a composite salience score to HKS ingestion using novelty, corroboration, source quality, freshness, and semantic uniqueness. | ✅ | 2026-03-23 |
| TASK-008 | Route low-salience material to archival or advisory stores instead of first-class semantic retrieval indexes. | ✅ | 2026-03-23 |
| TASK-009 | Extend `hlf_mcp/weekly_artifacts.py` so weekly evidence admissions carry salience, freshness, and trust-tier decisions. | ✅ | 2026-03-23 |

### Implementation Phase 4

- **GOAL-004**: Redesign retrieval around hybrid multi-index behavior rather than a single generalized recall path.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-010 | Add explicit lexical, dense semantic, metadata-filtered, and graph-oriented retrieval contracts inside `hlf_mcp/server_memory.py` and `hlf_mcp/rag/memory.py`. | ◐ | 2026-03-24 |
| TASK-011 | Introduce graph-linked semantic nodes for entities such as frameworks, APIs, patterns, prompts, contracts, and repair procedures. | ◐ | 2026-03-24 |
| TASK-012 | Expose operator-visible HKS retrieval reports that distinguish result source, retrieval path, provenance grade, freshness verdict, and graph linkage. | ◐ | 2026-03-23 |

### 2026-03-23 Bridge Slice Note

Archive-aware governed recall is now widened beyond the focused HKS memory tests:

- persisted governed recall contracts now carry explicit archive/admission summaries
- `hlf_memory_stats` now exposes an operator-legible archive/admission bridge summary
- governed recall status, markdown, and native-comprehension surfaces now show archive visibility and admission distribution
- packaged memory query and governed recall contracts now expose retrieval-path composition and first graph-linked entity context
- governed route and formal verifier operator surfaces now read the latest governed-recall posture as advisory knowledge context

This advances `TASK-010`, `TASK-011`, and `TASK-012`, but does not complete the full hybrid retrieval redesign. The next honest step remains replacing first graph-linked visibility with actual graph traversal and ranking behavior and widening runtime consumers beyond operator-facing advisory surfaces.

### 2026-03-24 Retrieval Contract Note

The packaged bridge layer now makes the retrieval contract materially more explicit without pretending dense retrieval is already shipped:

- query and result contracts now expose per-path status for `semantic`, `lexical`, `metadata-filtered`, `graph-linked`, and the currently unavailable `dense-semantic` lane
- governed recall surfaces now expose graph-traversal totals, surface-level filtering/truncation counts, and operator-readable path status instead of only raw path counts
- front-door reports and native-comprehension packets now surface the dense-semantic boundary honestly while preserving the current sparse-vector local runtime truth

This moves `TASK-010` forward to partial completion and strengthens `TASK-012`, but it still does not satisfy the larger Phase 4 target. Dense semantic indexing is not yet packaged, and graph-linked semantic nodes are still derived from bounded local graph context rather than a richer first-class knowledge graph substrate.

### 2026-03-23 Bounded Evaluation Slice Note

The bounded HKS local-evaluation slice is now complete as bridge work and should be read as part of the current-truth base for later platform expansion:

- packaged HKS memory records now distinguish source capture, artifact form, artifact kind, and source authority label
- local evaluation and comparator-quarantine boundaries are operator-legible through status, report, and native-comprehension surfaces
- the slice is validated both by focused HKS suites and by the broader repo pytest matrix

This improves the quality of the packaged base layer for future HKS expansion, but it does not change the extraction-status judgment above: the wider governed knowledge substrate still remains only partially extracted.

### Implementation Phase 5

- **GOAL-005**: Add code-aware and version-aware ingestion so HKS becomes materially useful for programming knowledge rather than generic text recall.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-013 | Implement code/doc chunking strategies that preserve repository structure, API version, symbol boundaries, and linked explanatory documentation. |  |  |
| TASK-014 | Add incremental reindexing and selective re-embed paths driven by source deltas rather than full reingestion. |  |  |
| TASK-015 | Add schema support for framework version, SDK version, standard revision, and compatibility windows on HKS records. |  |  |

### Implementation Phase 6

- **GOAL-006**: Add uncertainty and disagreement gating so HKS retrieval is invoked selectively and synthesized conservatively.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-016 | Add retrieval-entry uncertainty gating so the runtime can decide when retrieval should be skipped, invoked, or escalated. |  |  |
| TASK-017 | Expand disagreement handling into provenance-based and corroboration-based acceptance or refusal logic on retrieved knowledge units. |  |  |
| TASK-018 | Surface those decisions in route, verifier, and answer-synthesis contracts rather than as hidden recall heuristics. |  |  |

### Implementation Phase 7

- **GOAL-007**: Add multimodal and graph-backed grounding so HKS can support screenshot, diagram, and code-reasoning workflows.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-019 | Introduce modality-aware HKS records for text, code, image, and structured artifacts with provenance parity across all modalities. |  |  |
| TASK-020 | Add evidence assembly routines that produce modality-aware bundles for downstream synthesis and operator review. |  |  |
| TASK-021 | Add first operator-facing multimodal HKS surfaces that show how non-text evidence is admitted and cited. |  |  |

### Implementation Phase 8

- **GOAL-008**: Make HKS a first-class runtime substrate for translation, repair, routing, and orchestration.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-022 | Extend translation, repair, and routing flows in `hlf_mcp/server.py` and related seams so they consume governed HKS retrieval contracts rather than generic ad hoc recall. | ◐ | 2026-03-24 |
| TASK-023 | Add reusable HKS asset kinds for known-good prompts, contracts, code patterns, repair patterns, and upgrade opportunities. | ✅ | 2026-03-24 |
| TASK-024 | Ensure route evidence and verifier evidence can reference HKS contracts only when trust, freshness, and provenance thresholds are satisfied. | ✅ | 2026-03-24 |

### 2026-03-24 First-Class Graph / Runtime Gate Note

The packaged bridge layer now advances beyond bounded local graph context without overstating full HKS-platform completion:

- HKS writes now materialize first-class persisted graph nodes in the memory layer rather than relying only on per-record graph metadata at query time
- translation contracts, repair patterns, benchmark artifacts, and weekly artifact records now emit explicit graph entities and relations so contracts, repair procedures, prompt assets, code patterns, upgrade opportunities, and weekly evidence state become addressable graph nodes
- query-time graph scoring now enriches fact-local graph context from the persisted HKS graph substrate and surfaces that backing explicitly as `persisted-hks-node-graph`
- query results now emit a reusable `governed_hks_contract` and the routing, repair, verifier, and execution-admission seams consume that admitted contract directly instead of only raw recall result lists
- capsule execution now denies elevated execution when the routed HKS contract is not admitted, and formal verifier admission now upgrades elevated requests to `knowledge_review_required` when governed verifier evidence is missing or inadmissible
- validation for this bridge segment is green in the focused HKS/capsule/front-door slice (`149 passed`) and in adjacent weekly/evidence/workflow/witness suites (`31 passed`)

This moves `TASK-011` and `TASK-022` forward while closing the current bridge intent for `TASK-023` and `TASK-024`. The remaining honest gap is not this asset/runtime gate slice itself, but the larger HKS-platform work still ahead: uncertainty gating, code-aware ingestion depth, multimodal evidence assembly, weekly drift refresh, and KPI-backed proof that HKS improves downstream HLF behavior.

### Implementation Phase 9

- **GOAL-009**: Integrate HKS with the weekly evolution spine so it can compound improvements instead of passively storing history.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-025 | Connect weekly workflows to governed HKS source intake, evaluation, supersession, deprecation, and promotion steps. |  |  |
| TASK-026 | Add weekly topic-drift and stale-domain detection that queues revalidation or re-research work. |  |  |
| TASK-027 | Record upgrade candidates and accepted promotions as durable HKS governance artifacts with operator review surfaces. |  |  |

### Implementation Phase 10

- **GOAL-010**: Add evaluation loops that prove HKS improves HLF behavior rather than simply increasing storage volume.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-028 | Define HKS KPIs for freshness, trusted-source coverage, exemplar yield, retrieval quality, citation quality, and runtime usefulness. |  |  |
| TASK-029 | Add benchmark harnesses that compare answer quality, repair quality, and route quality with and without HKS support. |  |  |
| TASK-030 | Expose operator-facing HKS health and KPI surfaces that make quality regressions visible. |  |  |

## 4. Alternatives

- **ALT-001**: Treat the current bounded comparator slice as “close enough” to the full HKS extraction target. Rejected because it hides major missing architecture.
- **ALT-002**: Rewrite HKS from scratch around an external RAG framework. Rejected because it would lose packaged truth and governance seams already present in the repo.
- **ALT-003**: Keep HKS limited to memory storage plus optional comparator checks. Rejected because it under-shoots the intended knowledge-substrate role for HLF.
- **ALT-004**: Promote external research stack terminology directly into current-truth HKS docs. Rejected because it would violate claim-lane discipline.

## 5. Dependencies

- **DEP-001**: `AGENTS.md`
- **DEP-002**: `/memories/repo/HLF_MCP.md`
- **DEP-003**: `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- **DEP-004**: `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`
- **DEP-005**: `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md`
- **DEP-006**: `plan/architecture-hks-local-evaluation-bounded-comparator-1.md`
- **DEP-007**: `plan/architecture-hlf-language-knowledge-convergence-1.md`
- **DEP-008**: `SSOT_HLF_MCP.md`

## 6. Files

- **FILE-001**: `plan/architecture-hks-platform-expansion-1.md` — full HKS platform bridge plan
- **FILE-002**: `hlf_mcp/rag/memory.py` — memory tiering, ingest, retrieval, trust, supersession
- **FILE-003**: `hlf_mcp/server_memory.py` — HKS MCP retrieval and ingest contracts
- **FILE-004**: `hlf_mcp/server_context.py` — persisted HKS state and operator-ready retrieval chains
- **FILE-005**: `hlf_mcp/weekly_artifacts.py` — weekly intake, promotion, supersession, freshness updates
- **FILE-006**: `hlf_mcp/server_resources.py` — HKS operator surfaces, reports, KPIs, and native-comprehension packets
- **FILE-007**: `tests/test_hks_memory.py` — memory and governance tests
- **FILE-008**: `tests/test_fastmcp_frontdoor.py` — front-door operator and native-comprehension tests
- **FILE-009**: `.github/workflows/weekly-*.yml` — weekly evolution and knowledge-refresh integration

## 7. Testing

- **TEST-001**: HKS tiering tests for working, episodic, semantic, provenance, and archive contracts
- **TEST-002**: salience-gating tests covering archival versus promotion routing
- **TEST-003**: retrieval tests for lexical, semantic, metadata, and graph-backed paths
- **TEST-004**: code-aware and version-aware ingest/retrieval tests
- **TEST-005**: runtime integration tests proving translation, repair, routing, and verifier flows improve via HKS contracts
- **TEST-006**: weekly refresh and supersession regression tests
- **TEST-007**: KPI and operator-surface tests for HKS health visibility
- **TEST-008**: focused bridge validation now includes `tests/test_hks_memory.py`, `tests/test_capsule_pointer_trust.py`, and `tests/test_fastmcp_frontdoor.py`
- **TEST-009**: adjacent evidence-surface validation now includes `tests/test_weekly_artifacts.py`, `tests/test_evidence_query.py`, `tests/test_workflow_support.py`, `tests/test_extracted_support_tools.py`, and `tests/test_witness_governance.py`

## 8. Risks & Assumptions

- **RISK-001**: The repo may overstate HKS maturity because the bounded comparator slice is now visible and green.
- **RISK-002**: Memory growth without strong ingest gating will degrade trust and retrieval quality.
- **RISK-003**: Adding multimodal or graph paths prematurely could create complexity without operator legibility.
- **RISK-004**: External baseline influence could leak into current-truth claims if the bridge lane is not actively guarded.
- **ASSUMPTION-001**: The source that informed the user’s standard is close enough to serve as a practical extraction ceiling for HKS bridge planning.
- **ASSUMPTION-002**: The right next step is not to declare HKS “nearly complete,” but to measure and execute the missing extraction work deliberately.

## 9. Related Specifications / Further Reading

- `AGENTS.md`
- `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`
- `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md`
- `plan/architecture-hks-local-evaluation-bounded-comparator-1.md`
- `plan/architecture-hlf-language-knowledge-convergence-1.md`
- `HLF_ACTIONABLE_PLAN.md`
- `SSOT_HLF_MCP.md`
