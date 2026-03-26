---
goal: Add a bridge-lane native comprehension mode over existing governed operator artifacts
version: 1.0
date_created: 2026-03-23
last_updated: 2026-03-23
owner: GitHub Copilot
status: 'Planned'
tags: [feature, bridge, operator, teaching, comprehension, hlf, hks]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a narrow bridge-lane implementation for an HLF native comprehension mode. The target is not a new tutorial app, not a second explanation engine, and not a translation-heavy beginner shell. The target is a layered reading interface built directly on top of the real governed outputs the packaged MCP already produces.

The first shippable slice is a resource-backed reading layer over existing operator artifacts. It should help a capable user read HLF, HKS, Infinite RAG, and governed proof surfaces in-place while preserving authority boundaries, claim-lane discipline, and evidence provenance.

Lane classification:

- primary lane: bridge
- work type: bridge implementation over current packaged truth
- first host: packaged MCP resources and operator CLI
- non-goal: standalone GUI, alternate datastore, or parallel explanation runtime

## 1. Requirements & Constraints

- **REQ-001**: Build on existing packaged operator resources and reports rather than inventing a new parallel teaching subsystem.
- **REQ-002**: Treat `hlf://status/...`, `hlf://reports/...`, and `hlf://explainer/...` outputs as the source material for comprehension mode.
- **REQ-003**: Preserve authority boundaries explicitly: executable truth remains canonical source, while reading layers remain display-only and operator-facing.
- **REQ-004**: Preserve claim-lane labeling so users can tell current packaged truth from bridge interpretation and future direction.
- **REQ-005**: The first shippable slice must cover at least one language artifact, one knowledge artifact, and one symbolic/operator artifact already present in the MCP.
- **REQ-006**: The interface must teach users how to read governed outputs without flattening HLF into plain-English-only translation.
- **REQ-007**: The reading layer must surface evidence refs, provenance mode, governance state, and reading order directly from the underlying artifact.
- **REQ-008**: The first slice must be reachable from the current operator path without requiring VS Code webviews or a new frontend shell.
- **REQ-009**: The first slice must be additive to existing resources, not a replacement for them.
- **REQ-010**: Keep HKS and Infinite RAG represented as governed substrate concepts, not as a generic memory sidebar.
- **SEC-001**: No reading layer may imply that display-only explainer content has executable or policy authority.
- **SEC-002**: No reading layer may hide denied states, bridge qualifiers, provenance gaps, or missing evidence.
- **SEC-003**: No first-slice implementation may introduce hidden model calls, autonomous summarization loops, or new storage requirements.
- **CON-001**: Do not start with a separate GUI, website, or notebook; the first slice must live inside packaged MCP and CLI surfaces.
- **CON-002**: Do not duplicate operator data contracts in a second schema when the existing resource contract can be composed directly.
- **CON-003**: Do not treat symbolic, translation, or governed-recall surfaces as decorative teaching examples; they are trust-bearing product surfaces.
- **GUD-001**: Prefer layered reading packets that point back to existing resource URIs, reports, and explainers.
- **GUD-002**: Prefer a narrow first slice with real tests over a broader speculative education framework.
- **PAT-001**: The comprehension layer should be resource-backed, indexable, and renderable through the same packaged operator helpers already used by `hlf-operator`.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the reading-layer contract over existing packaged operator surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Define the comprehension-mode contract in `plan/feature-native-comprehension-mode-1.md` as a bridge-layer reading interface over existing governed outputs. | ✅ | 2026-03-23 |
| TASK-002 | Identify the first-slice source surfaces as `hlf://status/translation_contract`, `hlf://status/governed_recall`, and `hlf://status/symbolic_surface`, with `hlf://status/operator_surfaces` as the discovery index. |  |  |
| TASK-003 | Define a derived reading-packet schema in `hlf_mcp/server_resources.py` with exact sections: `surface_snapshot`, `reading_layers`, `authority_boundary`, `claim_lane`, `evidence_refs`, `starter_vocabulary`, `operator_questions`, and `next_resources`. |  |  |
| TASK-004 | Define a resource namespace for the first slice that composes the existing surface contracts instead of replacing them. Recommended URIs: `hlf://teach/native_comprehension`, `hlf://teach/native_comprehension/{surface_id}`. |  |  |

### Implementation Phase 2

- **GOAL-002**: Ship the first narrow slice as a resource-backed layered reading interface.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Implement a comprehension index resource in `hlf_mcp/server_resources.py` that lists supported teaching surfaces, their source URIs, and their intended reading order. |  |  |
| TASK-006 | Implement the first reading packet for `translation_contract` by composing existing translation-contract status/report data into layered sections: what the user is looking at, how intent became HLF, what proof exists, and what remains bridge-qualified. |  |  |
| TASK-007 | Implement the first reading packet for `governed_recall` by composing existing governed-recall status/report data into layered sections: what was recalled, why it is governed rather than generic search, how evidence backing works, and how HKS/Infinite RAG should be interpreted. |  |  |
| TASK-008 | Implement the first reading packet for `symbolic_surface` by composing existing symbolic status/report/explainer data into layered sections: canonical source versus display-only projection, relation artifacts, starter vocabulary, and proof-bundle provenance. |  |  |
| TASK-009 | Keep all first-slice reading packets strictly derived from current resource payloads and report text; no new model-generated paraphrase layer is allowed in this phase. |  |  |

### Implementation Phase 3

- **GOAL-003**: Add the packaged operator entrypoints for using the first slice.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Register the new comprehension resources in the packaged FastMCP surface and ensure they are visible through the existing resource renderer path. |  |  |
| TASK-011 | Extend `hlf_mcp/operator_cli.py` with a narrow command for the first slice. Recommended commands: `hlf-operator native-comprehension --surface-id <id> --json` and `hlf-operator native-comprehension-index --json`. |  |  |
| TASK-012 | Keep the CLI implementation thin by routing through the same resource-render helper already used for packaged operator surfaces. |  |  |
| TASK-013 | Update the packaged operator-surface documentation to point users from the discovery index toward the new layered-reading resources without claiming a full visual teaching product. |  |  |

### Implementation Phase 4

- **GOAL-004**: Prove the first slice with regression tests and current-truth documentation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Add regression tests in `tests/test_fastmcp_frontdoor.py` proving the new comprehension resources are registered, return deterministic sections, and point back to the correct source URIs and evidence refs. |  |  |
| TASK-015 | Add CLI tests in `tests/test_operator_cli.py` proving the new command routes through packaged resources and supports JSON output. |  |  |
| TASK-016 | Update `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` to classify native comprehension mode as a bridge-layer operator surface built from packaged truth rather than as a separate GUI subsystem. |  |  |
| TASK-017 | Update `SSOT_HLF_MCP.md` only after the resources, CLI path, and regression tests are real. Record the first slice as a packaged bridge surface, not as a completed operator workbench. |  |  |

### Implementation Phase 5

- **GOAL-005**: Stage the follow-on path after the first slice is proven.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Expand the reading layer to additional governed surfaces only after the first slice is stable. Priority order: formal verifier, governed route, witness governance, memory governance, internal workflow. |  |  |
| TASK-019 | Feed the proven reading-packet contracts into `plan/architecture-visual-operator-workbench-1.md` as the substrate for any later visual host or extension surface. |  |  |
| TASK-020 | Consider a later VS Code or operator-workbench host only after the packaged resource and CLI forms have stable tests and bounded claim-lane language. |  |  |

## 3. Alternatives

- **ALT-001**: Build a brand-new teaching app or website first. Rejected because the packaged MCP already has real operator artifacts and the user explicitly asked for a non-parallel first slice.
- **ALT-002**: Build a translation-only explainer that rewrites HLF into plain English everywhere. Rejected because the goal is native comprehension of governed artifacts, not flattening HLF back into prose.
- **ALT-003**: Start with a VS Code webview or GUI shell. Rejected because that adds host complexity before the resource contract exists.
- **ALT-004**: Store separate educational summaries in a new database or memory tier. Rejected because the first slice should compose existing truth, not create a second authority store.

## 4. Dependencies

- **DEP-001**: `AGENTS.md`
- **DEP-002**: `/memories/repo/HLF_MCP.md`
- **DEP-003**: `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- **DEP-004**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- **DEP-005**: `plan/architecture-visual-operator-workbench-1.md`
- **DEP-006**: `hlf_mcp/server_resources.py`
- **DEP-007**: `hlf_mcp/operator_cli.py`
- **DEP-008**: `tests/test_fastmcp_frontdoor.py`
- **DEP-009**: `tests/test_operator_cli.py`
- **DEP-010**: `SSOT_HLF_MCP.md`

## 5. Files

- **FILE-001**: `plan/feature-native-comprehension-mode-1.md` — bridge implementation plan for the native comprehension slice
- **FILE-002**: `hlf_mcp/server_resources.py` — reading-packet builders, new resource registrations, and derived comprehension index
- **FILE-003**: `hlf_mcp/operator_cli.py` — thin packaged CLI entrypoints for the new reading resources
- **FILE-004**: `tests/test_fastmcp_frontdoor.py` — resource registration and payload regression tests
- **FILE-005**: `tests/test_operator_cli.py` — CLI regression tests for first-slice commands
- **FILE-006**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` — taxonomy update for the new bridge-layer reading surface
- **FILE-007**: `SSOT_HLF_MCP.md` — current-truth update after implementation and tests are real
- **FILE-008**: `plan/architecture-visual-operator-workbench-1.md` — later host plan that should consume this resource contract rather than inventing its own

## 6. Testing

- **TEST-001**: Verify `hlf://teach/native_comprehension` and `hlf://teach/native_comprehension/{surface_id}` are registered in the packaged MCP surface.
- **TEST-002**: Verify each first-slice reading packet points back to the correct source status/report/explainer URIs and does not drop evidence refs or authority-boundary fields.
- **TEST-003**: Verify the `translation_contract` reading packet includes canonical-HLF, proof, and bridge-lane sections without inventing a second explanation authority.
- **TEST-004**: Verify the `governed_recall` reading packet distinguishes governed evidence from generic retrieval and preserves HKS/Infinite RAG framing.
- **TEST-005**: Verify the `symbolic_surface` reading packet preserves display-only labeling, provenance mode, and starter vocabulary.
- **TEST-006**: Verify the operator CLI commands route through packaged resources and support JSON output deterministically.
- **TEST-007**: Run focused validation after implementation: `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_operator_cli.py -q --tb=short`.

## 7. Risks & Assumptions

- **RISK-001**: The reading layer could silently become a second authority if it starts paraphrasing beyond the underlying resource contracts.
- **RISK-002**: A too-broad first slice could turn into a speculative education framework before any real operator path is shipped.
- **RISK-003**: If HKS/Infinite RAG are explained as generic memory or search, the bridge would damage doctrinal accuracy.
- **RISK-004**: GUI-first implementation would likely overstate maturity before the packaged operator substrate is proven.
- **ASSUMPTION-001**: The user wants a serious advanced-user comprehension path, not a simplified beginner mode.
- **ASSUMPTION-002**: Existing operator resources are already strong enough to support a narrow derived reading interface.
- **ASSUMPTION-003**: The correct first shippable unit is resource-plus-CLI, with later visual hosting as a separate phase.

## 8. Related Specifications / Further Reading

- `AGENTS.md`
- `/memories/repo/HLF_MCP.md`
- `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`
- `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`
- `plan/architecture-visual-operator-workbench-1.md`