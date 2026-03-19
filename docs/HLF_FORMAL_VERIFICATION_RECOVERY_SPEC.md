---
goal: Recover the formal verification lane as packaged HLF authority rather than leaving it as source-only doctrine
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [verification, proof, recovery, z3, governance, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This spec defines how to restore the formal verification surface from `hlf_source/agents/core/formal_verifier.py` into packaged HLF truth. The verifier is not optional polish. It is one of the clearest upstream proofs that HLF was intended to verify constraints, invariants, reachability, and gas feasibility rather than merely compile and run.

## 1. Requirements & Constraints

- **REQ-001**: Recover a packaged verifier surface that can check constraints, invariants, and gas-related properties.
- **REQ-002**: Preserve the distinction between proven, counterexample, unknown, skipped, and error outcomes.
- **REQ-003**: Preserve solver-agnostic behavior where Z3 is optional and a fallback path still exists.
- **REQ-004**: Expose verifier results in machine-readable and operator-readable form.
- **REQ-005**: Tie verifier recovery to governance and route-admission stories rather than leaving it isolated.
- **SEC-001**: Do not claim verifier-backed execution until proof artifacts and negative tests exist.
- **ARC-001**: Do not reduce the verifier to a simple lint pass or syntax check.
- **ARC-002**: Do not require the full Sovereign agent runtime to obtain packaged verification value.

## 2. Source Authority and Packaged Targets

### Upstream source authority

- `hlf_source/agents/core/formal_verifier.py`

### Current packaged owners and adjacent proof surfaces

- `hlf_mcp/hlf/entropy_anchor.py`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/hlf/capsules.py`
- `hlf_mcp/server.py`

### Target packaged ownership

- Add packaged verifier ownership under `hlf_mcp/hlf/`.
- Add MCP exposure only after the verifier result contract is stable.
- Keep verifier outputs reusable by routing, capsule validation, memory governance, and operator proof surfaces.

## 3. Recovery Scope

### Restore into packaged truth

- verification result types and reports
- constraint extraction from packaged AST forms
- gas-budget feasibility checks
- proof serialization for operator and test use

### Bridge contract only

- deeper theorem-prover integrations that are not needed for an initial packaged authority
- Sovereign-specific orchestration around verifier invocation

### Source-only for now

- any upstream integrations that require the full Sovereign multi-agent runtime shell before packaged contracts exist

## 4. Required Verifier Contracts

### Verification result contract

Verifier output must include:

- property name
- verification status
- constraint kind
- message
- counterexample if present
- duration
- solver used

### Verification report contract

Aggregate reports must include:

- total checks
- proven count
- failed count
- unknown count
- skipped count
- all-proven flag
- total duration
- solver availability
- per-check results

## 5. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Land a packaged verifier boundary.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create packaged verifier module ownership under `hlf_mcp/hlf/`. |  |  |
| TASK-002 | Port verification result and report structures from the upstream source. |  |  |
| TASK-003 | Define AST compatibility between packaged compiler output and the verifier extractor. |  |  |

### Implementation Phase 2

- **GOAL-002**: Connect verification to governance and execution.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add verifier entry points for constraint and gas-budget evaluation. |  |  |
| TASK-005 | Define how verifier outputs influence capsule admission, route admission, or operator warnings. |  |  |
| TASK-006 | Add operator-readable proof summaries backed by structured verifier reports. |  |  |

### Implementation Phase 3

- **GOAL-003**: Prove the verifier surface with negative and positive coverage.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add regression coverage for proven, counterexample, unknown, skipped, and error paths. |  |  |
| TASK-008 | Add gas-budget feasibility tests and at least one failing invariant example. |  |  |
| TASK-009 | Add MCP or resource exposure only after structured outputs are stable and tested. |  |  |

## 6. Files

- **FILE-001**: `hlf_source/agents/core/formal_verifier.py`
- **FILE-002**: `hlf_mcp/hlf/entropy_anchor.py`
- **FILE-003**: `hlf_mcp/hlf/runtime.py`
- **FILE-004**: `hlf_mcp/hlf/capsules.py`
- **FILE-005**: packaged verifier module to be created under `hlf_mcp/hlf/`

## 7. Testing

- **TEST-001**: packaged verifier reproduces all core verification statuses
- **TEST-002**: failing constraints return structured counterexamples where available
- **TEST-003**: gas-budget verification distinguishes feasible from infeasible plans
- **TEST-004**: operator proof summaries remain grounded in structured verifier results

## 8. Risks & Assumptions

- **RISK-001**: A thin port could degrade the verifier into a label rather than a proof surface.
- **RISK-002**: Tightly coupling the verifier to MCP too early could freeze a weak contract.
- **ASSUMPTION-001**: The upstream verifier is the correct semantic authority for the first packaged proof lane.

## 9. Related Specifications / Further Reading

- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`
- `docs/HLF_README_OPERATIONALIZATION_MATRIX.md`
- `plan/architecture-hlf-reconstruction-2.md`
