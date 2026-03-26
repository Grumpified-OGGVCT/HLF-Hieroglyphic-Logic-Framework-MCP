---
goal: Implement HKS-native evaluation and quarantine optional external comparators from core governed memory authority
version: 1.0
date_created: 2026-03-23
last_updated: 2026-03-23
owner: GitHub Copilot
status: Completed
tags: [architecture, bridge, hks, memory, evaluation, governance, weekly-artifacts]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This plan turns the current architecture decision into a bounded implementation slice.

Decision already taken:

- HKS must own its own evaluation method for memory quality, grounding, provenance, freshness, and promotion eligibility
- external web or code search systems may be used only as optional comparators
- no external comparator may become the authority for HKS recall, exemplar promotion, or weekly knowledge admission

Working theme:

`HKS evaluates itself before it listens to outsiders`

Lane classification:

- primary lane: bridge
- work type: restoration plus bridge implementation
- claim discipline: no external comparator language is allowed into current-truth HKS claims without packaged code, tests, operator surfaces, and SSOT updates

## 1. Requirements & Constraints

- **REQ-001**: Preserve three-lane doctrine. Local HKS evaluation is the product-direction authority. External comparison remains bridge-only.
- **REQ-002**: Keep HKS-native naming in runtime contracts. Do not let vendor naming leak into packaged truth.
- **REQ-003**: Promotion to exemplar or governed weekly memory must require local evidence fields, not comparator output alone.
- **REQ-004**: The implementation slice must stay function-level and testable inside existing HKS seams.
- **REQ-005**: Operator-facing status and report surfaces must make the distinction between local evaluation and external comparison legible.
- **SEC-001**: External comparator results must default to advisory-only and fail closed for writes, promotion, routing, or verifier evidence unless locally re-evaluated.
- **SEC-002**: Comparator calls must be explicit opt-in and configuration-gated. No hidden dependency on an external service is allowed.
- **CON-001**: Do not create an HKS design that depends on network availability for correctness.
- **CON-002**: Do not flatten governed recall into a web-search wrapper.
- **CON-003**: Prefer extending existing HKS surfaces over introducing a parallel memory subsystem.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Add an HKS-local evaluation contract that can score and explain memory quality without any external backend.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-001 | Extend `hlf_mcp/rag/memory.py` dataclass and normalization seams around `store`, `govern_fact`, `store_exemplar`, and `query` so governed memory records can carry a packaged `evaluation` block. Minimum fields: `evaluation_id`, `authority`, `groundedness`, `citation_coverage`, `freshness_verdict`, `provenance_verdict`, `promotion_eligible`, `operator_summary`. | ✅ | 2026-03-23 |
| TASK-002 | Define the packaged rule that `authority` may be `local_hks` or `external_comparator`, but only `local_hks` may set `promotion_eligible=true`. | ✅ | 2026-03-23 |
| TASK-003 | Require `store_exemplar` to reject exemplar promotion when the record lacks local evaluation or when `promotion_eligible` is false. | ✅ | 2026-03-23 |

### Implementation Phase 2

- **GOAL-002**: Thread local evaluation through weekly artifact generation and governed recall persistence.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-004 | Extend `hlf_mcp/weekly_artifacts.py` functions `build_hks_exemplar_from_weekly_artifact` and `build_weekly_artifact_memory_record` to emit HKS-local evaluation sidecars for weekly memory admissions. | ✅ | 2026-03-23 |
| TASK-005 | Extend `hlf_mcp/server_context.py` with a persisted evaluation sidecar path adjacent to `persist_governed_recall`, `get_governed_recall`, and `capture_validated_solution`. The persisted payload must preserve local-versus-external authority labels. | ✅ | 2026-03-23 |
| TASK-006 | Ensure governed recall payloads can expose an evaluation summary without requiring raw database inspection. | ✅ | 2026-03-23 |

### Implementation Phase 3

- **GOAL-003**: Add a visibly quarantined external comparator path that can assist review without owning truth.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-007 | Add an explicit optional comparator entry point in `hlf_mcp/server_memory.py`. Preferred shape: a separate tool or clearly isolated parameter path that returns advisory comparison only and never writes exemplars directly. | ✅ | 2026-03-23 |
| TASK-008 | Comparator outputs must be normalized as `authority=external_comparator`, `lane=bridge`, `promotion_blocked=true`, and `requires_local_recheck=true`. | ✅ | 2026-03-23 |
| TASK-009 | Add configuration gating so comparator code is inert unless the backend is explicitly enabled by environment or config. | ✅ | 2026-03-23 |

### Implementation Phase 4

- **GOAL-004**: Add operator-visible status and report surfaces that show the evaluation chain and the comparator quarantine boundary.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-010 | Extend `hlf_mcp/server_resources.py` with packaged status and report surfaces for the latest HKS evaluation chain. Preferred URIs: `hlf://status/hks_evaluation`, `hlf://reports/hks_evaluation`, plus per-evaluation URIs when an `evaluation_id` exists. | ✅ | 2026-03-23 |
| TASK-011 | If comparator output is present, expose a separate advisory surface rather than merging it into the main status authority. Preferred URIs: `hlf://status/hks_external_compare`, `hlf://reports/hks_external_compare`. | ✅ | 2026-03-23 |
| TASK-012 | Update operator-teaching or discovery surfaces only after the new status and report contracts exist and are tested. | ✅ | 2026-03-23 |

### Implementation Phase 5

- **GOAL-005**: Prove the slice with deterministic tests and bounded artifact outputs.

| Task | Description | Completed | Date |
|---|---|---|---|
| TASK-013 | Extend `tests/test_hks_memory.py` to cover: local evaluation persistence, exemplar promotion blocking without local evaluation, comparator quarantine flags, and weekly artifact evaluation propagation. | ✅ | 2026-03-23 |
| TASK-014 | Extend `tests/test_fastmcp_frontdoor.py` to cover: new status and report resources, advisory comparator surfaces, and proof that comparator output does not become governed authority. | ✅ | 2026-03-23 |
| TASK-015 | Validate the slice with focused commands: `uv run pytest tests/test_hks_memory.py -q --tb=short`, `uv run pytest tests/test_fastmcp_frontdoor.py -q --tb=short`, and then `uv run pytest tests/test_hks_memory.py tests/test_fastmcp_frontdoor.py -q --tb=short`. | ✅ | 2026-03-23 |

### 2026-03-23 Bridge Completion Note

Current truth for this bounded slice is now stronger and explicitly validated:

- packaged HKS memory contracts carry local evaluation, source-capture, and artifact-shape fields through storage, weekly admission, retrieval, and operator surfaces
- optional external comparison remains a bridge-lane advisory path and does not become packaged admission authority
- HKS evaluation, operator, and native-comprehension resources now expose the local-versus-advisory boundary directly at the front door

Validation completed at two levels:

- focused HKS slice validation: `uv run pytest tests/test_hks_memory.py tests/test_fastmcp_frontdoor.py -q --tb=short` -> `121 passed`
- broader repository matrix validation: `uv run pytest -q --tb=short` -> `944 passed`

This closes the bounded local-evaluation and comparator-quarantine slice as completed bridge work. It does not claim that the wider HKS platform extraction is complete.

## 3. Exact Files

- **FILE-001**: `plan/architecture-hks-local-evaluation-bounded-comparator-1.md` — this implementation slice plan
- **FILE-002**: `hlf_mcp/rag/memory.py` — HKS-local evaluation contract, authority labeling, promotion gating
- **FILE-003**: `hlf_mcp/weekly_artifacts.py` — weekly artifact evaluation sidecars and admission metadata
- **FILE-004**: `hlf_mcp/server_context.py` — persisted evaluation chains and session recall lookup
- **FILE-005**: `hlf_mcp/server_memory.py` — MCP tool surface for local evaluation exposure and optional comparator isolation
- **FILE-006**: `hlf_mcp/server_resources.py` — status and markdown report surfaces for HKS evaluation and advisory comparator output
- **FILE-007**: `tests/test_hks_memory.py` — memory-governance regression proof
- **FILE-008**: `tests/test_fastmcp_frontdoor.py` — packaged front-door and operator-surface proof
- **FILE-009**: `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` — doctrinal boundary for local evaluation and comparator quarantine
- **FILE-010**: `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` — bridge-lane comparator guardrail

## 4. Commands

- **CMD-001**: `uv run pytest tests/test_hks_memory.py -q --tb=short`
- **CMD-002**: `uv run pytest tests/test_fastmcp_frontdoor.py -q --tb=short`
- **CMD-003**: `uv run pytest tests/test_hks_memory.py tests/test_fastmcp_frontdoor.py -q --tb=short`

## 5. Artifact Outputs

- **ART-001**: structured local evaluation payload persisted with each eligible governed memory promotion candidate
- **ART-002**: weekly artifact memory records that carry local HKS evaluation summaries
- **ART-003**: operator-readable structured status resource at `hlf://status/hks_evaluation`
- **ART-004**: operator-readable markdown report at `hlf://reports/hks_evaluation`
- **ART-005**: optional advisory comparator status resource at `hlf://status/hks_external_compare`
- **ART-006**: optional advisory comparator markdown report at `hlf://reports/hks_external_compare`
- **ART-007**: per-evaluation status and report URIs when an `evaluation_id` exists, following the same status/report pattern already used by translation contracts and governed recall

## 6. Alternatives

- **ALT-001**: Make an external search system the default HKS authority. Rejected because it would collapse governed memory into dependency-shaped retrieval.
- **ALT-002**: Skip local evaluation and rely on weekly human review only. Rejected because it would weaken deterministic admission and exemplar promotion discipline.
- **ALT-003**: Merge local and external comparison into one opaque score. Rejected because it would hide authority boundaries from operators and tests.

## 7. Risks & Assumptions

- **RISK-001**: Comparator code can silently become a hidden dependency if it is wired into default recall flows.
- **RISK-002**: Promotion rules can drift if the evaluation contract is underspecified at the memory-layer seam.
- **RISK-003**: Operator surfaces can become misleading if local and external authority are not clearly separated.
- **ASSUMPTION-001**: The next HKS slice should optimize for trustworthy admission and operator-legible proof, not for the largest possible ingestion surface.
- **ASSUMPTION-002**: Existing HKS functions and resource patterns are sufficient to host this slice without a new subsystem.

## 8. Related Specifications / Further Reading

- `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`
- `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md`
- `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`
- `plan/architecture-hlf-language-knowledge-convergence-1.md`
- `HLF_ACTIONABLE_PLAN.md`