---
goal: Recover HLF routing fabric without flattening upstream gateway semantics into a thin packaged selector
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [routing, recovery, gateway, bridge, governance, orchestration, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This spec defines how to recover the routing fabric as a constitutive HLF surface. The packaged repo already has evidence-backed model selection work in `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, and `hlf_mcp/server_resources.py`, but that is still narrower than the upstream gateway fabric.

The target is not a generic model picker. The target is a governed routing layer that carries route admission, tier discipline, benchmark evidence, policy basis, and operator-visible traces.

## 1. Requirements & Constraints

- **REQ-001**: Preserve routing as execution semantics, not as a convenience helper.
- **REQ-002**: Recover the route-trace story: why a model was selected, what evidence supported it, and what policy gates shaped the decision.
- **REQ-003**: Preserve gas-aware and tier-aware routing constraints.
- **REQ-004**: Preserve allowlist and governance gating as part of routing.
- **REQ-005**: Keep operator-readable route evidence queryable without raw tool invocation.
- **REQ-006**: Use upstream routing files as source authority: `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, and `hlf_source/agents/gateway/sentinel_gate.py`.
- **SEC-001**: Do not widen model eligibility or host-function effects while recovering routing.
- **SEC-002**: Fail closed when required route evidence or policy basis is missing.
- **ARC-001**: Do not import the entire FastAPI gateway bus wholesale into packaged truth.
- **ARC-002**: Recover semantics, traces, and contracts rather than cloning the full Sovereign runtime shell.
- **CON-001**: The packaged runtime authority remains under `hlf_mcp/`.
- **CON-002**: Upstream gateway code remains source authority until packaged ownership is explicit.

## 2. Source Authority and Packaged Targets

### Upstream source authority

- `hlf_source/agents/gateway/bus.py`
- `hlf_source/agents/gateway/router.py`
- `hlf_source/agents/gateway/sentinel_gate.py`

### Current packaged owners

- `hlf_mcp/server_profiles.py`
- `hlf_mcp/hlf/model_catalog.py`
- `hlf_mcp/server_resources.py`
- `hlf_mcp/server_context.py`

### Target packaged ownership

- Keep route candidate generation and qualification evaluation in `hlf_mcp/server_profiles.py` and `hlf_mcp/hlf/model_catalog.py`.
- Add a packaged routing trace authority under `hlf_mcp/hlf/` if current modules become overloaded.
- Keep operator-facing route evidence surfaces in `hlf_mcp/server_resources.py`.
- Keep persisted evidence and benchmark artifact history in `hlf_mcp/server_context.py` and memory-backed storage.

## 3. Recovery Scope

### Restore into packaged truth

- route rationale objects that explain complexity, lane, tier, benchmark evidence, and fallback logic
- policy-backed route admission checks
- deterministic route traces that can be returned to operators and tests
- fail-closed behavior when required route evidence is absent

### Bridge contract only

- full FastAPI ingress middleware chain from `bus.py`
- Dapr publication and Redis-specific surrounding operational shell
- entire external dispatcher layer as currently packaged in Sovereign OS

### Source-only for now

- full upstream gateway hosting and deployment shell
- upstream scheduler and bus-specific operational plumbing unrelated to packaged routing authority

## 4. Required Runtime Contracts

### Route decision contract

Every packaged route decision must eventually expose:

- selected lane
- selected model or profile
- qualification profiles consulted
- benchmark artifacts consulted
- policy gates applied
- gas or budget constraint basis
- fallback reasons
- promotion or rejection rationale

### Route trace contract

Every route trace must eventually serialize:

- `request_context`
- `selected_lane`
- `selection_profiles`
- `profile_evaluations`
- `benchmark_evidence`
- `policy_basis`
- `fallback_chain`
- `operator_summary`

## 5. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Lock the routing contract and ownership boundary.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Document the current packaged routing path across `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, and `hlf_mcp/server_resources.py`. |  |  |
| TASK-002 | Define the packaged route-decision schema and route-trace schema. |  |  |
| TASK-003 | Define which route semantics from `hlf_source/agents/gateway/router.py` must be faithfully ported versus only referenced. |  |  |

### Implementation Phase 2

- **GOAL-002**: Recover governance-backed routing behavior.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Port policy and allowlist gating semantics into the packaged route path. |  |  |
| TASK-005 | Add fail-closed handling when route evidence or policy basis is missing. |  |  |
| TASK-006 | Add deterministic route rationale generation and operator summaries. |  |  |

### Implementation Phase 3

- **GOAL-003**: Prove the routing fabric through tests and operator surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add regression coverage for lane-family selection, fallback ordering, and profile readiness. |  |  |
| TASK-008 | Add regression coverage for policy-backed route denial and evidence-required route denial. |  |  |
| TASK-009 | Add operator-facing resource checks for route evidence, selected profiles, and fallback explanation. |  |  |

## 6. Files

- **FILE-001**: `hlf_source/agents/gateway/bus.py`
- **FILE-002**: `hlf_source/agents/gateway/router.py`
- **FILE-003**: `hlf_source/agents/gateway/sentinel_gate.py`
- **FILE-004**: `hlf_mcp/server_profiles.py`
- **FILE-005**: `hlf_mcp/hlf/model_catalog.py`
- **FILE-006**: `hlf_mcp/server_resources.py`
- **FILE-007**: `hlf_mcp/server_context.py`
- **FILE-008**: `tests/` routing and resource regression files to be added or extended

## 7. Testing

- **TEST-001**: lane-family route selection returns deterministic route trace fields
- **TEST-002**: missing benchmark evidence triggers rejection or explicit degraded result rather than silent success
- **TEST-003**: route evidence resources return the same selection basis as the routing logic used internally
- **TEST-004**: policy or allowlist denial is visible in route rationale output

## 8. Risks & Assumptions

- **RISK-001**: Over-porting the full gateway shell would blur packaged runtime boundaries.
- **RISK-002**: Under-porting the router would preserve only model choice, not the governing route semantics.
- **ASSUMPTION-001**: The current packaged evidence-backed routing work is the correct landing zone for this recovery.

## 9. Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `plan/architecture-hlf-reconstruction-2.md`
