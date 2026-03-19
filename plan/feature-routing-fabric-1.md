---
goal: Implement the first packaged routing-fabric recovery slice with deterministic route traces and fail-closed evidence handling
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [feature, routing, recovery, batch1, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This feature plan executes the first routing recovery slice from `docs/HLF_ROUTING_RECOVERY_SPEC.md`.

## 1. Requirements & Constraints

- **REQ-001**: Implement only the first packaged routing recovery slice.
- **REQ-002**: Add deterministic route traces and route rationale objects.
- **REQ-003**: Fail closed when route evidence requirements are unmet.
- **CON-001**: Do not import the full upstream gateway shell.
- **CON-002**: Do not widen route permissions or model eligibility silently.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define packaged route trace structures.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add route-decision and route-trace schema helpers in packaged routing code. | ✅ | 2026-03-19 |
| TASK-002 | Thread route-trace fields through `hlf_mcp/server_profiles.py` and `hlf_mcp/hlf/model_catalog.py`. | ✅ | 2026-03-19 |
| TASK-003 | Expose operator-facing route summaries in `hlf_mcp/server_resources.py`. | ✅ | 2026-03-19 |

### Implementation Phase 2

- **GOAL-002**: Enforce evidence-required routing.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add fail-closed handling when required benchmark evidence or policy basis is absent. | ✅ | 2026-03-19 |
| TASK-005 | Preserve fallback chains explicitly in route traces. | ✅ | 2026-03-19 |
| TASK-006 | Keep all changes inside packaged routing owners only. | ✅ | 2026-03-19 |

### Implementation Phase 3

- **GOAL-003**: Verify and document the slice.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add focused tests for route selection, fallback, and denial paths. | ✅ | 2026-03-19 |
| TASK-008 | Update route-related operator docs only after tests pass. | ✅ | 2026-03-19 |
| TASK-009 | Run focused regression scope first, then broader validation if needed. | ✅ | 2026-03-19 |

## 3. Files

- `hlf_mcp/server_profiles.py`
- `hlf_mcp/hlf/model_catalog.py`
- `hlf_mcp/server_resources.py`
- route-related tests under `tests/`

## 4. Testing

- focused route-selection tests
- route-evidence resource tests
- fail-closed missing-evidence tests

## 5. Risks & Assumptions

- **RISK-001**: Route trace additions could become a dumping ground without a stable schema.
- **ASSUMPTION-001**: Existing evidence-backed routing surfaces are the correct base for the first slice.
