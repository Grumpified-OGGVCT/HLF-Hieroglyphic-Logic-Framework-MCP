---
goal: Implement the first packaged orchestration-lifecycle recovery slice with explicit DAG and mission-state contracts
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [feature, orchestration, lifecycle, recovery, batch2, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This feature plan executes the first orchestration recovery slice from `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md`.

## 1. Requirements & Constraints

- **REQ-001**: Extend lifecycle from phase tracking to plan and execution contracts.
- **REQ-002**: Keep ownership inside packaged `hlf_mcp/instinct/` and related packaged modules.
- **REQ-003**: Preserve fail-closed lifecycle transitions.
- **CON-001**: Do not import the full upstream persona runtime or agent shell in this slice.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define packaged orchestration data structures.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add packaged DAG and plan-step contracts adjacent to `hlf_mcp/instinct/lifecycle.py`. | ✅ | 2026-03-19 |
| TASK-002 | Define mission-state fields for task DAG and execution traces. | ✅ | 2026-03-19 |
| TASK-003 | Keep delegation and escalation fields explicit even if initial behavior is narrow. | ✅ | 2026-03-19 |

### Implementation Phase 2

- **GOAL-002**: Add deterministic orchestration behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add plan ordering and dependency semantics to packaged lifecycle flows. | ✅ | 2026-03-19 |
| TASK-005 | Connect verification gating to mission-state transitions. | ✅ | 2026-03-19 |
| TASK-006 | Expose mission and execution summaries through packaged instinct surfaces. | ✅ | 2026-03-19 |

### Implementation Phase 3

- **GOAL-003**: Verify the first orchestration slice.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add focused tests for phase gating, plan ordering, and realignment behavior. | ✅ | 2026-03-19 |
| TASK-008 | Add tests for execution trace serialization. | ✅ | 2026-03-19 |
| TASK-009 | Update operator docs only after structured traces are stable. | ✅ | 2026-03-19 |

## 3. Files

- `hlf_mcp/instinct/lifecycle.py`
- `hlf_mcp/server_instinct.py`
- packaged orchestration modules under `hlf_mcp/instinct/`
- orchestration-focused tests under `tests/`

## 4. Testing

- lifecycle transition tests
- plan ordering tests
- execution trace serialization tests

## 5. Risks & Assumptions

- **RISK-001**: The lifecycle could remain an empty shell if DAG semantics are deferred again.
- **ASSUMPTION-001**: Batch 1 proof surfaces are in place before this feature begins implementation.
