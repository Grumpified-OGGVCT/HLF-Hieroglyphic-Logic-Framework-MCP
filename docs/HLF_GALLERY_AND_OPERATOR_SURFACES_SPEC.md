---
goal: Recover gallery, explainer, and operator-legibility surfaces as trust-bearing HLF product surfaces
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [gallery, operator, reporting, explainer, recovery, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This spec defines how to recover the operator gallery and human-legibility surfaces. These are not decorative extras. They are part of how HLF becomes inspectable, teachable, and trustworthy to operators.

## 1. Requirements & Constraints

- **REQ-001**: Preserve a maintained operator-legibility path for examples, compilation reports, and explainers.
- **REQ-002**: Distinguish static docs, generated reports, and queryable MCP resources.
- **REQ-003**: Use upstream gallery and explainer files as source authority, not as optional inspiration.
- **REQ-004**: Keep generated operator artifacts grounded in packaged truth.
- **ARC-001**: Do not treat gallery and explainer surfaces as fluff.
- **ARC-002**: Do not claim generated reports that are not actually reproducible from packaged code.

## 2. Source Authority and Packaged Targets

### Upstream source authority

- `hlf_source/scripts/run_hlf_gallery.py`
- `hlf_source/docs/hlf_explainer.html`
- `hlf_source/docs/HLF_REFERENCE.md`
- `hlf_source/docs/HLF_GRAMMAR_REFERENCE.md`
- `hlf_source/gui/app.py`

### Current packaged owners

- `fixtures/README.md`
- `docs/HLF_REFERENCE.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- `hlf_mcp/server_resources.py`

## 3. Recovery Scope

### Recover into packaged truth

- gallery compilation and report generation for packaged fixtures or example programs
- operator-facing explainers for route, verifier, memory, and execution surfaces
- stable generated artifacts that summarize packaged example health and proof status

### Bridge contract only

- richer interactive explainer or GUI paths that depend on later operator-surface work

### Source-only for now

- full GUI application restoration
- upstream UI shells that exceed the current packaged operator target

## 4. Required Operator Surface Types

At minimum, the recovered operator surface set must define:

- fixture or example gallery status
- compile or bytecode report summaries
- route evidence summaries
- verifier result summaries
- memory provenance summaries
- clear distinction between generated and hand-authored explanatory content

## 5. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the operator-surface taxonomy.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Define which surfaces are static docs, generated reports, or MCP resources. |  |  |
| TASK-002 | Map upstream gallery and explainer semantics onto packaged fixture and resource surfaces. |  |  |
| TASK-003 | Define a reproducible report-generation path rooted in packaged truth. |  |  |

### Implementation Phase 2

- **GOAL-002**: Build the first generated operator artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add a packaged gallery/report generator or equivalent report workflow for fixture health. |  |  |
| TASK-005 | Add generated summaries for routing, verification, and memory-evidence surfaces. |  |  |
| TASK-006 | Add smoke validation for generated operator artifacts. |  |  |

## 6. Files

- **FILE-001**: `hlf_source/scripts/run_hlf_gallery.py`
- **FILE-002**: `hlf_source/docs/hlf_explainer.html`
- **FILE-003**: `hlf_source/gui/app.py`
- **FILE-004**: `fixtures/README.md`
- **FILE-005**: `docs/HLF_REFERENCE.md`
- **FILE-006**: `docs/HLF_GRAMMAR_REFERENCE.md`
- **FILE-007**: `hlf_mcp/server_resources.py`

## 7. Testing

- **TEST-001**: generated gallery or report artifacts are reproducible from current packaged code
- **TEST-002**: operator summaries match the structured evidence objects they summarize
- **TEST-003**: smoke validation catches stale generated outputs

## 8. Risks & Assumptions

- **RISK-001**: Generated operator surfaces can drift if they are not tied directly to packaged truth.
- **RISK-002**: Treating operator-legibility as optional would weaken audit trust even if runtime code improves.
- **ASSUMPTION-001**: A generated report path is the right first packaged recovery step before any richer GUI restoration.

## 9. Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `plan/architecture-hlf-reconstruction-2.md`
