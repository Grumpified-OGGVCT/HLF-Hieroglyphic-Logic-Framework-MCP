---
goal: Recover persona and operator doctrine as architectural control surfaces without turning them into uncontrolled runtime authority
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [persona, operator, doctrine, recovery, governance, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This spec defines how persona and operator doctrine should be recovered. The target is not to stuff prompt files into runtime and call that integration. The target is to preserve personas as real control surfaces for review, escalation, tool governance, planning, and operator trust.

## 1. Requirements & Constraints

- **REQ-001**: Preserve persona doctrine as a constitutive part of HLF’s governance and operator model.
- **REQ-002**: Keep persona files in the doctrine and bridge lane until bounded packaged integration points are defined.
- **REQ-003**: Use `hlf_source/AGENTS.md` and persona specs as source authority for roles and responsibilities.
- **REQ-004**: Map personas to operator workflows, review checkpoints, escalation rules, and trust surfaces.
- **SEC-001**: Do not allow raw persona text to become hidden runtime authority without explicit contracts.
- **ARC-001**: Do not dismiss personas as style guides or prompt garnish.

## 2. Source Authority and Packaged Targets

### Upstream source authority

- `hlf_source/AGENTS.md`
- `hlf_source/config/personas/steward.md`
- `hlf_source/config/personas/sentinel.md`
- `hlf_source/config/personas/strategist.md`
- related persona files under `hlf_source/config/personas/`

### Current packaged and repo owners

- `AGENTS.md`
- `docs/AGENTS_CATALOG.md`
- `docs/ETHICAL_GOVERNOR_HANDOFF.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`

## 3. Recovery Scope

### Recover into docs and operator flows now

- steward as tool and MCP workflow integrity authority
- sentinel as adversarial security and fail-closed review authority
- strategist as planning and sequencing authority
- operator workflow notes that make these roles inspectable and actionable

### Bridge contract later

- bounded persona-aware checkpoints in routing, verification, orchestration, or operator approval flows
- structured role tags or review states that reference persona responsibilities without embedding raw prompts as code

### Source-only for now

- full upstream persona runtime and registry system
- multi-agent hat engine integration that depends on the full Sovereign OS stack

## 4. Required Persona-to-Operator Mapping

At minimum, the recovered operator doctrine must define:

- which persona owns tool integrity
- which persona owns security review
- which persona owns planning sequence and opportunity cost
- which persona owns audit logging or documentation integrity
- when a human operator must review or override a persona-driven recommendation

## 5. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Document persona responsibilities as architectural controls.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Extract role boundaries for Steward, Sentinel, and Strategist from upstream persona sources. |  |  |
| TASK-002 | Map those roles into operator handoff, review, escalation, and recovery planning surfaces. |  |  |
| TASK-003 | Record which persona surfaces remain source-only and why. |  |  |

### Implementation Phase 2

- **GOAL-002**: Define bounded packaged integration points.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Define where persona-aware review states can appear in packaged routing, verifier, or orchestration outputs. |  |  |
| TASK-005 | Define how operator-visible reports should expose persona ownership without hidden prompt authority. |  |  |
| TASK-006 | Define what stays purely documentary until later recovery batches. |  |  |

## 6. Files

- **FILE-001**: `hlf_source/AGENTS.md`
- **FILE-002**: `hlf_source/config/personas/steward.md`
- **FILE-003**: `hlf_source/config/personas/sentinel.md`
- **FILE-004**: `hlf_source/config/personas/strategist.md`
- **FILE-005**: `AGENTS.md`
- **FILE-006**: `docs/AGENTS_CATALOG.md`

## 7. Testing

- **TEST-001**: operator docs and handoff surfaces consistently map the same responsibilities to the same personas
- **TEST-002**: any future packaged persona-aware output references structured role ownership, not raw prompt text

## 8. Risks & Assumptions

- **RISK-001**: Persona doctrine could be trivialized into style notes if not mapped to actual controls.
- **RISK-002**: Persona files could accidentally become invisible runtime rules without auditability.
- **ASSUMPTION-001**: Persona recovery is primarily an operator and governance surface before it becomes a runtime surface.

## 9. Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `plan/architecture-hlf-reconstruction-2.md`
