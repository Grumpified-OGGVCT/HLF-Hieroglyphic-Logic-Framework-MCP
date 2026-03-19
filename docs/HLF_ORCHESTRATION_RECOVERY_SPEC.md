---
goal: Recover orchestration lifecycle and plan execution as constitutive HLF multi-agent surfaces
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [orchestration, lifecycle, dag, recovery, multi-agent, instinct, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This spec defines how to recover the orchestration lifecycle from upstream plan execution and crew coordination into packaged truth. The packaged repo already has `hlf_mcp/instinct/lifecycle.py` and `hlf_mcp/server_instinct.py`, but these are still narrower than the upstream `plan_executor.py` and `crew_orchestrator.py` surfaces.

The recovery target is a deterministic plan-to-execute layer with delegation, dissent, verification gates, and handoff lineage.

## 1. Requirements & Constraints

- **REQ-001**: Preserve the SDD lifecycle ordering: specify, plan, execute, verify, merge.
- **REQ-002**: Recover plan-to-DAG and execution semantics rather than only phase labels.
- **REQ-003**: Preserve role-boundary and persona-aware orchestration concepts without importing the entire upstream agent shell.
- **REQ-004**: Preserve handoff lineage, escalation, and verification checkpoints.
- **REQ-005**: Keep orchestration compatible with packaged MCP exposure.
- **SEC-001**: Verification and merge transitions must remain gated rather than becoming optimistic defaults.
- **ARC-001**: Do not reduce orchestration to a thin mission-status store.
- **ARC-002**: Do not collapse multi-persona synthesis into one undifferentiated agent step.

## 2. Source Authority and Packaged Targets

### Upstream source authority

- `hlf_source/agents/core/plan_executor.py`
- `hlf_source/agents/core/crew_orchestrator.py`
- `hlf_source/agents/core/task_classifier.py`

### Current packaged owners

- `hlf_mcp/instinct/lifecycle.py`
- `hlf_mcp/server_instinct.py`

### Target packaged ownership

- Keep lifecycle state machine authority in `hlf_mcp/instinct/lifecycle.py`.
- Add packaged planning and execution modules under `hlf_mcp/instinct/` or `hlf_mcp/hlf/` only if ownership remains clear.
- Keep MCP exposure in `hlf_mcp/server_instinct.py` once the orchestration contracts are stable.

## 3. Recovery Scope

### Restore into packaged truth

- task-to-DAG conversion semantics
- execution result aggregation semantics
- deterministic phase gating and realignment handling
- handoff lineage and delegation contracts

### Bridge contract only

- full upstream persona API call machinery
- OS-specific agent sandbox or build-agent shells not required for the packaged recovery slice

### Source-only for now

- broader Sovereign crew infrastructure that depends on the full OS registry and persona runtime

## 4. Required Orchestration Contracts

### Mission contract

Packaged orchestration must eventually track:

- mission topic
- lifecycle phase
- spec
- task DAG
- verification report
- phase history
- realignment events
- seal status

### Execution trace contract

Packaged execution traces must eventually include:

- node id
- task type
- assigned role or handler
- success or failure
- duration
- affected files or outputs
- escalation or dissent state if applicable

## 5. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define packaged orchestration ownership beyond lifecycle labels.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Map current `InstinctLifecycle` semantics against upstream `SDDSession`, `PlanExecutor`, and crew orchestration flow. |  |  |
| TASK-002 | Define packaged DAG and plan-step contracts. |  |  |
| TASK-003 | Define where delegation, dissent, and escalation states live in packaged truth. |  |  |

### Implementation Phase 2

- **GOAL-002**: Recover deterministic plan execution behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Port plan-to-DAG semantics into a packaged orchestration boundary. |  |  |
| TASK-005 | Add packaged execution result aggregation compatible with lifecycle state. |  |  |
| TASK-006 | Connect verification gating so execute-to-verify-to-merge carries real proof artifacts. |  |  |

### Implementation Phase 3

- **GOAL-003**: Prove orchestration through deterministic traces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add tests for blocked phase skips, blocked backward transitions, and merge gating. |  |  |
| TASK-008 | Add tests for plan ordering, dependency preservation, and realignment events. |  |  |
| TASK-009 | Add operator-readable lifecycle summaries backed by structured mission state and execution traces. |  |  |

## 6. Files

- **FILE-001**: `hlf_source/agents/core/plan_executor.py`
- **FILE-002**: `hlf_source/agents/core/crew_orchestrator.py`
- **FILE-003**: `hlf_source/agents/core/task_classifier.py`
- **FILE-004**: `hlf_mcp/instinct/lifecycle.py`
- **FILE-005**: `hlf_mcp/server_instinct.py`
- **FILE-006**: packaged orchestration modules to be created under `hlf_mcp/instinct/` or adjacent packaged boundary

## 7. Testing

- **TEST-001**: mission lifecycle remains sequential and fail-closed
- **TEST-002**: plan DAG preserves task ordering and dependency requirements
- **TEST-003**: verification and merge states cannot be advanced without required artifacts
- **TEST-004**: orchestration summaries reflect real mission and execution-trace data

## 8. Risks & Assumptions

- **RISK-001**: Treating current lifecycle tools as sufficient would leave orchestration materially underpowered.
- **RISK-002**: Importing full upstream persona runtime too early would muddy packaged ownership.
- **ASSUMPTION-001**: Existing `InstinctLifecycle` is the correct packaged landing zone for this recovery, but not the whole solution.

## 9. Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `docs/HLF_README_OPERATIONALIZATION_MATRIX.md`
- `plan/architecture-hlf-reconstruction-2.md`