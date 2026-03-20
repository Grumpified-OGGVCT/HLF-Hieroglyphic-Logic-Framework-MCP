---
goal: Turn HLF autonomous evolution from aspirational doctrine into a governed bridge implementation track
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [feature, bridge, autonomous-evolution, governance, verification, weekly-automation, hlf]
---

<!-- markdownlint-disable MD060 -->

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan captures the useful part of the autonomous-evolution thesis without collapsing into speculative self-improvement theater.

The bridge target is not "HLF already autonomously ships perfect software."

The bridge target is a governed loop where HLF can:

- observe implementation friction and production-adjacent evidence
- turn that evidence into bounded proposals
- verify proposals against tests, governance, and effect contracts
- promote only those changes that survive explicit acceptance gates

That is the path from inspirational recursive-improvement rhetoric to a professional, auditable, operator-trustworthy build system.

## 1. Requirements & Constraints

- **REQ-001**: Preserve three-lane discipline: autonomous evolution belongs to vision and bridge lanes unless a specific capability is implemented and proven.
- **REQ-002**: Define the canonical evolution loop as `observe -> propose -> verify -> promote`.
- **REQ-003**: Treat weekly automation, build telemetry, and governed memory as evidence inputs to the loop, not as the loop itself.
- **REQ-004**: Require every proposal to carry provenance, scope, rationale, and a bounded target surface.
- **REQ-005**: Require deterministic or operator-reviewable verification before any proposal can affect runtime-facing truth.
- **REQ-006**: Connect evolution work to existing HLF pillars: lifecycle, formal verification, memory governance, routing/orchestration, and operator trust.
- **REQ-007**: Translate strong value claims such as speed, reliability, professionalism, and defect reduction into benchmark or control-matrix work items rather than present-tense assertions.
- **SEC-001**: No autonomous-evolution slice may widen capabilities, host-function permissions, or governance boundaries without explicit control updates.
- **SEC-002**: No self-modification path may bypass `VERIFY -> MERGE` controls, CoVE gates, or human/operator approval where required.
- **SEC-003**: Raw automation summaries must not become long-lived truth without deterministic evidence capture and supersession rules.
- **CON-001**: Do not market target-state delivery speed or defect-rate numbers as current repo truth until benchmarked.
- **CON-002**: Do not equate proposal generation with correctness, safety, or production readiness.
- **CON-003**: Do not route speculative architecture changes directly from LLM output into runtime code.
- **CON-004**: Do not treat one-off issue creation or weekly reports as a complete evolution framework.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the governed autonomous-evolution loop as a bridge contract.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Define the canonical loop as `observe -> propose -> verify -> promote` and map each stage to existing repo surfaces. |  |  |
| TASK-002 | Record which existing surfaces already partially satisfy the loop: weekly workflows, `hlf_do`, `hlf_test_suite_summary`, lifecycle guards, verifier surfaces, memory/provenance work. |  |  |
| TASK-003 | Add one operator-facing bridge note describing what is already real versus what remains target-state work. |  |  |

### Implementation Phase 2

- **GOAL-002**: Build the evidence substrate that makes autonomous improvement professional rather than anecdotal.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Normalize weekly automation artifacts so every finding includes branch, commit SHA, workflow run URL, script version, manifest hash, collected time, and confidence. |  |  |
| TASK-005 | Add supersession, expiry, and branch-isolation rules so stale or cross-branch knowledge cannot silently pollute the truth stream. |  |  |
| TASK-006 | Add a second-pass deterministic verifier for machine-extracted weekly findings before issue creation, planning updates, or long-lived memory storage. |  |  |

### Implementation Phase 3

- **GOAL-003**: Turn observed friction into bounded, governable proposals.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Define a proposal schema covering source evidence, affected files, intended gain, risk class, required tests, and required governance review. |  |  |
| TASK-008 | Connect friction logging, `SELF_OBSERVE`, and proposal-generation surfaces so the system can emit candidate improvements without claiming autonomous merge authority. |  |  |
| TASK-009 | Classify proposals into safe buckets such as docs sync, benchmark refresh, schema normalization, test augmentation, or runtime change requiring stronger review. |  |  |

### Implementation Phase 4

- **GOAL-004**: Define promotion gates so only verified improvements can advance.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Require `VERIFY -> MERGE` lifecycle evidence for every promoted proposal, including test status, trace completeness, and governance pass/fail state. |  |  |
| TASK-011 | Define which proposal classes require human approval, which require formal-verifier participation, and which can remain advisory only. |  |  |
| TASK-012 | Add one acceptance checklist tying proposal promotion to `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`, `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md`, and batch-specific tests. |  |  |

### Implementation Phase 5

- **GOAL-005**: Convert ambitious outcome claims into measurable benchmark work.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Define benchmark tracks for cycle time, defect escape, replayability, audit completeness, and operator handoff speed. |  |  |
| TASK-014 | Add a rule that any claim of orders-of-magnitude delivery improvement must cite a benchmark artifact, not only doctrine or examples. |  |  |
| TASK-015 | Add a measured comparison lane between governed HLF execution and NLP-only orchestration for at least one representative workflow family. |  |  |

## 3. Alternatives

- **ALT-001**: Leave autonomous evolution as vision-only prose. Rejected because the repo already has enough partial surfaces that the bridge path should be explicit.
- **ALT-002**: Claim the current weekly automation stack already constitutes full autonomous evolution. Rejected because it overstates what the repo can currently prove.
- **ALT-003**: Implement open-ended self-modification before evidence, provenance, and promotion gates exist. Rejected because that would weaken governance and operator trust.

## 4. Dependencies

- **DEP-001**: `plan/architecture-hlf-reconstruction-2.md`
- **DEP-002**: `HLF_ACTIONABLE_PLAN.md`
- **DEP-003**: `HLF_MCP_TODO.md`
- **DEP-004**: `docs/HLF_DESIGN_NORTH_STAR.md`
- **DEP-005**: `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- **DEP-006**: `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md`
- **DEP-007**: `.github/workflows/weekly-doc-security.yml`
- **DEP-008**: `.github/workflows/weekly-ethics-review.yml`
- **DEP-009**: `.github/workflows/weekly-test-health.yml`
- **DEP-010**: `hlf_mcp/instinct/lifecycle.py`

## 5. Files

- **FILE-001**: `plan/feature-autonomous-evolution-1.md`
- **FILE-002**: `HLF_ACTIONABLE_PLAN.md`
- **FILE-003**: `HLF_MCP_TODO.md`
- **FILE-004**: `docs/HLF_DESIGN_NORTH_STAR.md`
- **FILE-005**: weekly automation workflows and support scripts under `.github/`

## 6. Testing

- **TEST-001**: Add one deterministic validation path for weekly evidence artifacts before issue or memory promotion.
- **TEST-002**: Add one proposal-schema validation test for bounded improvement proposals.
- **TEST-003**: Add one lifecycle test proving autonomous-improvement candidates cannot bypass `VERIFY -> MERGE` gates.

## 7. Risks & Assumptions

- **RISK-001**: Strong vision language can create pressure to overclaim current delivery speed or correctness.
- **RISK-002**: Weekly automation can become noisy if evidence verification and supersession are not implemented first.
- **RISK-003**: Proposal generation without bounded scopes can collapse into generalized self-improvement theater.
- **ASSUMPTION-001**: The repo should aim for professional autonomous evolution, not uncontrolled self-modification.
- **ASSUMPTION-002**: Operator trust and governance legibility are more important than maximal autonomy at this stage.

## 8. Related Specifications / Further Reading

- `plan/architecture-hlf-reconstruction-2.md`
- `docs/HLF_DESIGN_NORTH_STAR.md`
- `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md`
