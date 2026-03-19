# HLF Recovery Acceptance Gates

Status: bridge-lane acceptance rules for restoration work on 2026-03-19.

## Purpose

- define the exact rules a recovery slice must satisfy before it is marked complete
- standardize minimum regression and artifact-refresh expectations across restoration classes
- stop partial or narrative-only restorations from being mistaken for complete recovery

## Universal Acceptance Gates

Every restoration must satisfy all of the following:

1. explicit packaged ownership boundary
2. explicit source authority named in the recovery spec
3. structured runtime or docs contract
4. targeted regression coverage
5. operator-facing proof or summary surface where applicable
6. backlog and handoff docs updated if truth boundaries changed

## Minimum Regression Additions By Restoration Class

| Class | Minimum Regression Additions |
| --- | --- |
| Runtime | success and failure execution paths, denial paths, contract serialization |
| Routing | selection, fallback, evidence-required denial, policy-backed denial, resource parity |
| Verifier | proven, counterexample, unknown, skipped, gas-feasibility, negative invariant |
| Orchestration | phase gating, plan ordering, dependency preservation, realignment, trace serialization |
| Memory | provenance-required retrieval, stale artifact handling, supersession, revocation, pointer validation |
| Persona/operator | role mapping consistency and operator-surface parity if packaged outputs reference personas |

## Minimum Generated Artifact Refresh By Restoration Class

| Class | Required Artifact Refresh |
| --- | --- |
| Runtime | docs or references if public behavior changed |
| Routing | route evidence resources, operator notes, any affected claim matrix rows |
| Verifier | proof summaries, claim matrix row review, operator notes |
| Orchestration | lifecycle notes, mission-state summaries, operator handoff updates |
| Memory | evidence schema docs, operator notes, weekly artifact contract review |
| Persona/operator | operator build notes, AGENTS-adjacent docs, role mapping docs |
| Gallery/operator surfaces | generated reports or smoke-validated artifacts |

## Completion Rule

A recovery slice is not complete if it has only code, only docs, or only a plan. It is complete only when code, proof, tests, and operator-facing explanation are all aligned at the required depth for that class.
