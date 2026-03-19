---
goal: Implement the first packaged formal-verifier boundary with structured proof results and gas-feasibility checks
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [feature, verifier, recovery, batch1, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This feature plan executes the first verifier recovery slice from `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md`.

## 1. Requirements & Constraints

- **REQ-001**: Land a packaged verifier boundary under `hlf_mcp/hlf/`.
- **REQ-002**: Preserve structured verification result and report types.
- **REQ-003**: Support gas-feasibility checks in the first slice.
- **CON-001**: Do not expose a weak MCP surface before the verifier contract is stable.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Create the packaged verifier contract.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create packaged verifier module with result and report structures. | ✅ | 2026-03-19 |
| TASK-002 | Port a minimal constraint extractor compatible with packaged ASTs. | ✅ | 2026-03-19 |
| TASK-003 | Add gas-feasibility verification entry point. | ✅ | 2026-03-19 |

### Implementation Phase 2

- **GOAL-002**: Prove the verifier boundary before broader integration.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add focused tests covering proven, failed, unknown, and skipped states. | ✅ | 2026-03-19 |
| TASK-005 | Add at least one negative gas or invariant example. | ✅ | 2026-03-19 |
| TASK-006 | Delay MCP exposure until the structured contract and tests are stable. | ✅ | 2026-03-19 |

## 3. Files

- packaged verifier module under `hlf_mcp/hlf/`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/hlf/capsules.py`
- verifier-focused tests under `tests/`

## 4. Testing

- verifier result and report tests
- gas-feasibility tests
- failing invariant example

## 5. Risks & Assumptions

- **RISK-001**: A minimal verifier slice could be mistaken for full verification if docs are sloppy.
- **ASSUMPTION-001**: The first slice proves the boundary, not the entire upstream verifier surface.
