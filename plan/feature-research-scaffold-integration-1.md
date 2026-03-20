---
goal: Integrate research scaffolds into the HLF bridge lane without collapsing them into disposable side files
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: 'Planned'
tags: [feature, bridge, research, scaffold, ollama, multilingual, archaeology, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan turns the current research-scaffold situation into an explicit bridge program.

Its immediate target is `ollama_folder_qa/`, but the real purpose is broader:

- preserve constitutive research without leaving it as an ungoverned side pocket
- define which research outputs become canonical docs, tests, or source-archaeology inputs
- prevent multilingual, routing, and multi-script findings from disappearing into cache or one-off notes

## 1. Requirements & Constraints

- **REQ-001**: Do not treat research scaffolds as disposable if they encode constitutive HLF recovery knowledge.
- **REQ-002**: Keep packaged runtime authority separate from research tooling authority.
- **REQ-003**: Any scaffold retained in-repo must have a clear role: archaeology tool, batch auditor, or bridge-report generator.
- **REQ-004**: Multilingual, glyph, routing, and multi-script findings must be mappable into canonical docs or tests.
- **REQ-005**: Preserve anti-reductionist reconstruction discipline; do not shrink the research lane to only what the current packaged code already supports.
- **CON-001**: Do not bind the packaged server runtime directly to an external Ollama dependency just to keep the scaffold.
- **CON-002**: Do not leave the scaffold as an undocumented orphan directory.
- **CON-003**: Do not claim titled research artifacts exist in tracked repo truth if they are not on disk.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Reclassify the current Ollama scaffold from incidental directory to explicit bridge artifact.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Rehome `ollama_folder_qa/` conceptually as a bridge-lane archaeology utility for constitutive-surface audits. |  |  |
| TASK-002 | Document that its current implementation is batch-only, external-model-dependent, and not yet integrated with HKS or repo planning outputs. |  |  |
| TASK-003 | Add a canonical reference from a bridge doc so future sessions know why the scaffold exists. |  |  |

### Implementation Phase 2

- **GOAL-002**: Turn the scaffold into a usable recovery aid rather than a blind whole-folder prompt loop.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add include/exclude controls so the tool can target pillar clusters instead of scanning the entire repo indiscriminately. |  |  |
| TASK-005 | Add output modes that emit structured Markdown/JSON reports suitable for `docs/` and `plan/` ingestion. |  |  |
| TASK-006 | Add question packs for specific bridge targets: multilingual/glyph surfaces, routing, formal verification, orchestration, persona doctrine, memory governance. |  |  |
| TASK-007 | Add deterministic metadata to results: scanned files, skipped files, model name, timestamp, and prompt pack. |  |  |

### Implementation Phase 3

- **GOAL-003**: Connect scaffold outputs to canonical bridge artifacts.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-008 | Define a report path from scaffold output into `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` and `docs/HLF_PILLAR_MAP.md`. |  |  |
| TASK-009 | Define how multilingual and multi-script findings become new rows in `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`. |  |  |
| TASK-010 | Define how routing findings become inputs to `docs/HLF_ROUTING_RECOVERY_SPEC.md`. |  |  |
| TASK-010A | Define how symbolic-surface and semasiographic findings feed into `plan/feature-symbolic-semantic-surfaces-1.md` without bypassing canonical grammar or audit planning. |  |  |

### Implementation Phase 4

- **GOAL-004**: Preserve missing research clusters explicitly when the exact source artifact is not yet tracked.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Create a bridge note listing titled research artifacts known from user context but not currently preserved in tracked repo truth. |  |  |
| TASK-012 | Classify each such artifact as one of: `recover from source`, `reconstruct from doctrine`, `record as missing external input`, or `not canonical`. |  |  |
| TASK-013 | Prioritize the multilingual/pictogram/routing cluster first because it affects doctrine, translation, and routing recovery together. |  |  |

## 3. Alternatives

- **ALT-001**: Delete the scaffold because it is not packaged runtime code. Rejected because the bridge lane needs research tooling and archaeology support.
- **ALT-002**: Wire the scaffold directly into the FastMCP surface now. Rejected because it would import unstable external-model behavior into packaged product truth.
- **ALT-003**: Leave the scaffold untouched as an unowned side directory. Rejected because that is how constitutive findings disappear.

## 4. Dependencies

- **DEP-001**: `ollama_folder_qa/README.md`
- **DEP-002**: `ollama_folder_qa/ENHANCEMENT_PLAN.md`
- **DEP-003**: `ollama_folder_qa/ollama_folder_qa.py`
- **DEP-004**: `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- **DEP-005**: `plan/architecture-hlf-reconstruction-2.md`

## 5. Files

- **FILE-001**: `ollama_folder_qa/README.md`
- **FILE-002**: `ollama_folder_qa/ENHANCEMENT_PLAN.md`
- **FILE-003**: `ollama_folder_qa/ollama_folder_qa.py`
- **FILE-004**: `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- **FILE-005**: future bridge note for missing external research artifacts
- **FILE-006**: `plan/feature-symbolic-semantic-surfaces-1.md`

## 6. Testing

- **TEST-001**: Add a deterministic smoke test for manifest generation and include/exclude filtering.
- **TEST-002**: Add a report-shape test for Markdown and JSON export outputs.
- **TEST-003**: Add a question-pack selection test so multilingual and routing probes can be executed independently.

## 7. Risks & Assumptions

- **RISK-001**: Whole-folder prompting can produce low-signal output unless context selection becomes pillar-aware.
- **RISK-002**: External-model dependence can make archaeology results noisy if not recorded as advisory.
- **ASSUMPTION-001**: The scaffold is intended as a bridge/research utility, not packaged runtime authority.
- **ASSUMPTION-002**: Some titled research artifacts mentioned by the user may currently exist only outside tracked repo files.

## 8. Related Specifications / Further Reading

- `plan/architecture-hlf-reconstruction-2.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `docs/HLF_MISSING_PILLARS.md`
- `plan/feature-symbolic-semantic-surfaces-1.md`