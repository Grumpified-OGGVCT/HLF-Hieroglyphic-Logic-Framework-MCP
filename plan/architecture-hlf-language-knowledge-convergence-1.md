---
goal: HLF language, knowledge, and execution convergence bridge plan
version: 1.0
date_created: 2026-03-22
last_updated: 2026-03-24
owner: GitHub Copilot
status: In progress
tags: [architecture, bridge, feature, governance, rag, codegen, routing, verification]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In_progress-yellow)

This plan defines the next bridge-lane PR after the governed review and operator-surface merge. The objective is not repo neatness. The objective is to make HLF visibly more like the intended governed meaning-and-execution substrate by strengthening four constitutive seams together: language-to-code generation, governed routing and execution, HLF Knowledge Substrate / Infinite RAG contracts, and self-verifying operator feedback loops.

Working PR theme:

`HLF learns to speak and code as one`

Interpretation:

- HLF should accept intent in human language
- HLF should canonicalize that intent into governed meaning
- HLF should generate executable or inspectable code artifacts with stronger proof
- HLF should route knowledge through HKS and Infinite RAG with provenance and trust intact
- HLF should use its own techniques on itself before hardening them into doctrine and product claims

Lane classification:

- primary lane: bridge
- work type: restoration plus bridge implementation
- claim discipline: no vision claims should be promoted to current-truth claims until backed by code, tests, and operator-visible evidence

## 1. Requirements & Constraints

- **REQ-001**: Preserve three-lane doctrine. Vision, current truth, and bridge claims must remain separate.
- **REQ-002**: Increase real HLF capability without weakening governance, provenance, or audit trust.
- **REQ-003**: Treat HKS and Infinite RAG as governed memory architecture, not as a generic retrieval bucket.
- **REQ-004**: Strengthen the path from natural-language intent to HLF meaning to code and tool execution.
- **REQ-005**: Use actual HLF-native techniques in the environment where practical before promoting them into docs or PR claims.
- **REQ-006**: Keep MCP as the adoption front door while refusing to collapse HLF into only an MCP wrapper.
- **REQ-007**: Improve operator-legible evidence so major new claims are inspectable from the repo and runtime surfaces.
- **REQ-008**: Preserve the packaged `hlf_mcp/` line as the current product authority unless a stricter canonical surface is intentionally promoted.
- **REQ-009**: Explicitly preserve the new must-return checkpoint: the weekly model-drift harness needs hardening and rerun before any strong model-drift interpretation is trusted.
- **SEC-001**: Any new memory, routing, or codegen path must fail closed on missing trust, missing provenance, or policy violations.
- **SEC-002**: No new path may bypass capsule, tier, or effect restrictions for convenience.
- **CON-001**: Do not import the whole Sovereign OS wholesale. Extract only HLF-constitutive surfaces or their minimal faithful contracts.
- **CON-002**: Do not flatten the legacy `hlf/` and packaged `hlf_mcp/` stacks into a pseudo-unified story without proving canonicality.
- **CON-003**: Avoid docs-first theater. Where code and docs compete for priority, build the real path first and then reconcile the narrative.
- **GUD-001**: Prefer faithful restoration or principled porting over thin stand-ins.
- **GUD-002**: Prefer operator-visible proof surfaces over hidden internal assertions.
- **PAT-001**: Treat new PR work as a convergence campaign of multiple constitutive seams rather than another isolated feature slice.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Establish the new PR as a serious convergence lane with explicit mission boundaries, success metrics, and must-return checkpoints.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-001|Create this bridge implementation plan in `plan/architecture-hlf-language-knowledge-convergence-1.md` and define the PR theme as `HLF learns to speak and code as one`.|✅|2026-03-22|
|TASK-002|Create a companion backlog checkpoint or tracking note that records issue `#39` as a mandatory return point for drift-harness hardening, rerun, and reassessment.|||
|TASK-003|Define the measurable campaign outcomes for this PR: language-to-code proof, governed routing evidence, HKS/Infinite-RAG trust improvement, and operator-visible verifier surfaces.|||

### Implementation Phase 2

- **GOAL-002**: Strengthen language-to-code convergence so HLF can reliably move from human instruction to governed executable artifacts.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-004|Audit `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/codegen.py`, and `hlf_mcp/hlf/insaits.py` against the vision-lane expectation that HLF should speak English, canonicalize meaning, and emit inspectable output.|✅|2026-03-22|
|TASK-005|Implement a more explicit translation-to-code contract that records source intent, canonical HLF, generated code target, and any governance constraints in one structured payload.|✅|2026-03-22|
|TASK-006|Expand code-generation proof by adding target-specific regression tests that validate generated output structure for at least one serious downstream language or integration path already represented in the repo.|✅|2026-03-23|
|TASK-007|Add operator-visible artifacts or resources that let a user inspect the chain `intent -> HLF -> generated code -> constraints/proof notes` without reading raw internals only.|✅|2026-03-23|

### Implementation Phase 3

- **GOAL-003**: Strengthen HKS and Infinite RAG as governed memory infrastructure rather than a thin retrieval feature.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-008|Audit `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, and `hlf_mcp/server_memory.py` against the missing-pillar requirements for provenance, freshness, confidence, trust tier, forgetting, and evidence discipline.|||
|TASK-009|Design and implement stronger memory contracts that distinguish raw retrieval results, governed memory entries, trusted pointers, and HKS-level recall surfaces.|✅|2026-03-23|
|TASK-009A|Translate the source-audit bridge findings from `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` into explicit HKS contract work: multi-timescale recall and supersession from `MemER`, adaptive context-fit scoring from `TempoFit`, and long-context compression benchmark lanes from `QwenLong-L1.5` without importing vendor naming into packaged runtime contracts.|||
|TASK-010|Add test coverage for trust-sensitive memory behavior including revocation, provenance gaps, stale evidence handling, and supersession semantics.|||
|TASK-011|Expose at least one new operator-facing memory or HKS status surface that makes governed memory state legible without database archaeology.|✅|2026-03-23|

### Implementation Phase 4

- **GOAL-004**: Strengthen routing, admission, and verifier seams so HLF can choose and justify how execution should happen.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-012|Audit `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/governed_routing.py`, `hlf_mcp/hlf/model_catalog.py`, `hlf_mcp/hlf/formal_verifier.py`, and `hlf_mcp/server_verifier.py` for under-recovered gateway, routing, and proof capabilities.|✅|2026-03-23|
|TASK-013|Implement at least one stronger governed-routing admission improvement such as richer profile evidence, route justification, nonce/budget evidence, or deterministic downshift reporting.|✅|2026-03-23|
|TASK-014|Implement at least one stronger formal-verification bridge output such as counterexample-friendly reporting, gas-feasibility proof summaries, or stricter verifier result contracts.|✅|2026-03-23|
|TASK-015|Add regression tests proving the new routing and verifier behaviors through the packaged MCP front door.|✅|2026-03-23|

### Implementation Phase 5

- **GOAL-005**: Use HLF on itself in bounded ways before turning the results into hardened product claims.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-016|Choose one internal workflow where HLF-native techniques can be used on the repo itself in a bounded, reviewable loop, such as intent translation, codegen review, or governed memory recall.|✅|2026-03-23|
|TASK-017|Record the before/after evidence for that internal-use experiment in a reproducible artifact or operator-facing report.|✅|2026-03-23|
|TASK-018|Promote only the portions that survive real usage, test proof, and governance review into current-truth documentation.|✅|2026-03-23|

### Implementation Phase 6

- **GOAL-006**: Return to the deferred but mandatory harness-quality seam and finish it before making strong recursive-improvement claims.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-019|Harden `scripts/monitor_model_drift.py` and the weekly model-drift workflow by disabling inappropriate agentic search behavior for closed-book probes and normalizing structured/fenced JSON responses.|✅|2026-03-23|
|TASK-020|Split evaluation outcomes into semantic wrong answer, protocol/shape failure, and tool-call/agentic-behavior failure classes.|✅|2026-03-23|
|TASK-021|Rerun the drift workflow after the harness changes and reclassify issue `#39` based on trustworthy signal rather than mixed failure modes.|||

## 3. Alternatives

## Progress Update

- 2026-03-23: Translation contract chains now have packaged operator status/report resources, including per-contract URIs.
- 2026-03-23: Packaged code generation now emits an explicit `hlf-bytecode` artifact contract with structured disassembly and regression proof for the downstream runtime target.
- 2026-03-23: Governed recall chains now persist through session context and are queryable through packaged status/report resources, including per-recall URIs.
- 2026-03-23: Formal verifier and governed route surfaces now include markdown companion reports in addition to structured status payloads.
- 2026-03-23: A bounded internal HLF-on-HLF workflow now uses governed memory recall on the repo itself, persists a reviewable workflow contract in session context, and exposes packaged status/report resources via `hlf://status/internal_workflow` and `hlf://reports/internal_workflow`.
- 2026-03-23: The weekly model-drift harness now runs as a closed-book JSON-evaluation path, normalizes fenced or embedded JSON responses, and classifies failures into semantic wrong answers, protocol-shape failures, and tool-call behavior failures before scoring drift.
- 2026-03-23: Focused validation for the bounded internal workflow slice completed with `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_hks_memory.py -q --tb=short` -> `95 passed`.
- 2026-03-23: Focused workflow-support validation for the drift harness slice completed with `uv run pytest tests/test_workflow_support.py -q --tb=short` -> `6 passed`.
- 2026-03-23: Broader convergence validation completed with `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_hks_memory.py tests/test_operator_cli.py tests/test_translator.py tests/test_codegen.py tests/test_workflow_support.py -q --tb=short` -> `143 passed`.
- 2026-03-23: Validation completed with `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_hks_memory.py -q --tb=short` -> `94 passed` and `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_hks_memory.py tests/test_operator_cli.py tests/test_translator.py tests/test_codegen.py -q --tb=short` -> `134 passed`.
- 2026-03-23: Additional focused convergence validation completed with `uv run pytest tests/test_codegen.py` -> `4 passed` and `uv run pytest tests/test_codegen.py tests/test_translator.py tests/test_fastmcp_frontdoor.py -q --tb=short` -> `110 passed`.
- 2026-03-23: Full repository regression validation completed after the bounded HKS bridge slice with `uv run pytest -q --tb=short` -> `944 passed`.
- 2026-03-24: Governed recall contracts now expose explicit per-path status, graph traversal totals, and surface-level filtering/truncation counts while keeping dense-semantic retrieval explicitly unshipped in current truth.
- 2026-03-24: Focused validation for the retrieval-contract/operator-surface increment completed with `uv run pytest tests/test_hks_memory.py tests/test_fastmcp_frontdoor.py -q --tb=short` -> `121 passed` and adjacent operator-surface validation completed with `uv run pytest tests/test_operator_cli.py -q --tb=short` -> `18 passed`.
- 2026-03-24: HKS now materializes first-class persisted graph nodes for governed semantic assets, and query-time graph scoring explicitly reports `persisted-hks-node-graph` when routing/repair/verifier flows consume admitted HKS evidence contracts.
- 2026-03-24: Runtime consumers now carry governed HKS contracts directly in repair, routing, and verifier flows instead of depending only on raw query result lists.
- 2026-03-24: Focused validation for the first-class graph/runtime-contract increment completed with `uv run pytest tests/test_hks_memory.py tests/test_fastmcp_frontdoor.py -q --tb=short` -> `122 passed` and adjacent operator validation completed with `uv run pytest tests/test_operator_cli.py -q --tb=short` -> `18 passed`.

- **ALT-001**: Focus only on the drift harness next. Rejected because it is a must-return checkpoint, but not the full strategic use of the next PR lane.
- **ALT-002**: Focus only on code generation. Rejected because it would under-serve routing, verification, and HKS/Infinite RAG convergence.
- **ALT-003**: Focus only on memory. Rejected because isolated memory improvements without language-to-code and routing proof would not produce the glimpse of unified HLF behavior the user wants.
- **ALT-004**: Import major upstream OS orchestration layers wholesale. Rejected because it violates the merge doctrine and would confuse HLF-core with OS scaffolding.

## 4. Dependencies

- **DEP-001**: `AGENTS.md` doctrine and three-lane reconstruction rules
- **DEP-002**: `/memories/repo/HLF_MCP.md`
- **DEP-003**: `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- **DEP-004**: `docs/HLF_VISION_MAP.md`
- **DEP-005**: `docs/HLF_MISSING_PILLARS.md`
- **DEP-006**: `HLF_ACTIONABLE_PLAN.md`
- **DEP-007**: `HLF_SOURCE_EXTRACTION_LEDGER.md`
- **DEP-008**: `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`

## 5. Files

- **FILE-001**: `plan/architecture-hlf-language-knowledge-convergence-1.md` — bridge implementation plan and PR campaign definition
- **FILE-002**: `hlf_mcp/hlf/translator.py` — intent-to-HLF contract surface
- **FILE-003**: `hlf_mcp/hlf/compiler.py` — canonical meaning path and metadata propagation
- **FILE-004**: `hlf_mcp/hlf/codegen.py` — generated code bridge hardening
- **FILE-005**: `hlf_mcp/hlf/insaits.py` — operator-readable trust and explanation surface
- **FILE-006**: `hlf_mcp/rag/memory.py` — Infinite RAG subsystem contracts
- **FILE-007**: `hlf_mcp/hlf/memory_node.py` — governed memory entry contracts and trust data
- **FILE-008**: `hlf_mcp/server_memory.py` — MCP memory surface and HKS exposure
- **FILE-009**: `hlf_mcp/server_profiles.py` — routed execution evidence and profile surfaces
- **FILE-010**: `hlf_mcp/hlf/governed_routing.py` — governed route decision logic
- **FILE-011**: `hlf_mcp/hlf/formal_verifier.py` — verification contract strengthening
- **FILE-012**: `hlf_mcp/server_verifier.py` — packaged verifier MCP surface
- **FILE-013**: `scripts/monitor_model_drift.py` — must-return drift harness seam
- **FILE-014**: `.github/workflows/weekly-model-drift-detect.yml` — drift workflow behavior and issue generation

## 6. Testing

- **TEST-001**: Translation-to-code regression tests proving structured `intent -> HLF -> code` payload correctness
- **TEST-002**: Packaged MCP tests for any new codegen or explanation surfaces exposed through `hlf_mcp/server.py`
- **TEST-003**: Governed memory regression tests covering provenance, trust, revocation, stale evidence, and supersession behavior
- **TEST-004**: Routed execution tests covering profile evidence, route decisions, and verifier-linked operator outputs
- **TEST-005**: Drift harness tests proving fenced JSON normalization, no-search closed-book behavior, and separate classification of protocol failures vs semantic failures
- **TEST-006**: Focused package validation for touched seams, followed by broader `uv run pytest tests/ -q --tb=short` before PR promotion

## 7. Risks & Assumptions

- **RISK-001**: The scope is large enough to sprawl if phases are not sequenced around convergent seams.
- **RISK-002**: Over-promoting bridge-lane experiments into current-truth claims would create narrative drift.
- **RISK-003**: Pulling too much from `hlf_source/` at once could smuggle OS scaffolding into HLF-core.
- **RISK-004**: Memory and routing changes can weaken trust if provenance and admission contracts are loosened.
- **RISK-005**: Model-drift reruns may still show real degradation even after harness fixes; the harness fix is necessary but not guaranteed to clear the issue.
- **ASSUMPTION-001**: The user wants this next PR to optimize for architectural leverage and constitutive recovery rather than minimal diff size.
- **ASSUMPTION-002**: The right early proof of progress is a visible improvement in integrated behavior, not merely a larger tool count.
- **ASSUMPTION-003**: HLF can and should begin using bounded versions of its own techniques internally before those techniques are hardened into stronger doctrine or marketing claims.

## 8. Related Specifications / Further Reading

- `AGENTS.md`
- `/memories/repo/HLF_MCP.md`
- `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- `docs/HLF_VISION_MAP.md`
- `docs/HLF_MISSING_PILLARS.md`
- `HLF_ACTIONABLE_PLAN.md`
- `HLF_SOURCE_EXTRACTION_LEDGER.md`
- `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`
