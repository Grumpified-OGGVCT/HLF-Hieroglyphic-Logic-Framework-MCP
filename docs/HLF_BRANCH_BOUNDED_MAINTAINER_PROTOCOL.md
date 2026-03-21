---
goal: Define safe branch-bounded autonomous maintainer rules for selected persona roles in HLF_MCP
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: Active bridge contract
tags: [persona, maintainer, autonomy, branch, governance, internal]
lane: bridge-true
audience: internal operators and bounded autonomous maintainers
---

# HLF Branch-Bounded Maintainer Protocol

## Purpose

This document defines the safe protocol for allowing selected persona roles to maintain the repo in a bounded way.

The protocol is intentionally narrower than the upstream autonomous pipeline.
It allows drafting and validation on branches only.
It does not allow silent merge, publish, or hidden runtime control.

## Personas Covered Now

- `strategist`
- `steward`
- `sentinel`
- `herald`
- `cove`

## Hard Safety Rules

- Branch-only writes.
- No direct push to protected branches.
- No automatic merge.
- No automatic publish.
- No silent file deletion.
- No changes to governance authority files without explicit operator approval.
- No packaged runtime authority may depend on raw upstream persona prompt text.

These rules are stricter than convenience and stronger than speed.

## Branch Contract

Allowed working branch pattern:

- `persona/<persona>/<slug>`

Examples:

- `persona/strategist/operator-doctrine-gates`
- `persona/herald/claim-lane-sync`
- `persona/steward/workflow-contract-audit`

Required branch metadata in the working note, PR body, or internal handoff:

- `owner_persona`
- `change_class`
- `lane`
- `required_gates`
- `tests_run`
- `promotion_status`

## Permission Model By Persona

| Persona | May Propose | May Edit | Must Not Edit Without Operator Approval |
| --- | --- | --- | --- |
| `strategist` | plans, sequencing, bridge priorities, roadmap docs, acceptance criteria | `plan/**`, `docs/**`, backlog and planning docs | packaged runtime code, `governance/**`, release workflows |
| `steward` | workflow hardening, tool-contract checks, transport review, evidence-flow notes | workflow-support docs, tests, narrowly scoped MCP contract code with tests | protected branch policy, raw governance manifests, merge controls |
| `sentinel` | hardening patches, fail-closed fixes, security tests, security review notes | security tests, security review docs, bounded hardening changes with regression proof | credentials, secret material, policy relaxation, automatic approvals |
| `herald` | SSOT sync, README/handoff corrections, claim-lane fixes, operator summaries | `README.md`, `SSOT_HLF_MCP.md`, `docs/**`, review handoffs | runtime code except trivial docstrings explicitly requested |
| `cove` | validation summaries, release-readiness findings, regression proof bundles | test reports, validation notes, issue or PR review artifacts | feature code as primary author, governance policy changes |

## Required Workflow

### Phase 1: Frame

Required owner:

- `strategist`

Required outputs:

- change class
- lane
- blast radius
- success criteria
- required gates

### Phase 2: Draft

Required owner:

- one of the bounded maintainer personas

Required constraints:

- stay inside approved file scope
- announce intended changes before editing
- keep edits reversible
- preserve tests and diagnostics

### Phase 3: Review

Required reviewers depend on change class:

- `steward` for workflow contract changes
- `sentinel` for security-sensitive changes
- `herald` for docs and claims
- `cove` for final validation

### Phase 4: Validate

Minimum validation:

- diagnostics for touched files
- targeted tests when behavior changed
- changed-file review against stated blast radius
- explicit unresolved-risk list if anything remains open

### Phase 5: Promote Or Hold

Only a human operator may:

- merge
- publish
- bless a change as new current truth
- widen a persona's edit scope

## Allowed Autonomy Level By Persona

| Persona | Autonomy Level Now | Notes |
| --- | --- | --- |
| `strategist` | advisory and drafting | may define work, not approve promotion alone |
| `steward` | bounded drafting and blocking review | strongest maintainer candidate for workflow surfaces |
| `sentinel` | bounded drafting and blocking review | can block on security, cannot silently waive risk |
| `herald` | bounded drafting and blocking review | best low-risk maintainer for docs truth and handoffs |
| `cove` | review-only | final validation authority, not primary implementer |

## Forbidden Patterns

- importing `jules_tasks.yaml` auto-apply semantics directly
- granting merge rights to persona processes
- letting `cove` replace test execution with opinion
- using `sentinel` to justify opaque hardening without evidence
- using `strategist` to outrank diagnostics or security failures
- using `herald` to market bridge work as current truth

## Required Review States

Each bounded maintainer change must surface these states where relevant:

- `strategist_review`
- `steward_review`
- `sentinel_review`
- `herald_review`
- `cove_review`
- `operator_promotion`

If a state is not required for a given change, mark it as `not_applicable` rather than omitting it silently.

## Stop Conditions

The maintainer must stop and escalate if any of the following become true:

- the requested change crosses from docs or bridge work into hidden runtime authority
- a governance file must change
- the blast radius expands beyond the approved file set
- diagnostics fail and root cause is unclear
- a required reviewer blocks the change
- the task would require weakening tests, controls, or evidence collection

## Default Escalation Map

| Problem | Escalate To |
| --- | --- |
| planning conflict | `strategist` then operator |
| workflow ambiguity | `steward` then operator |
| security uncertainty | `sentinel` then operator |
| claim-lane ambiguity | `herald` then `strategist` |
| release readiness dispute | `cove` then operator |
| irreconcilable disagreement | `arbiter` or operator |

## Acceptance Rule

This protocol is valid only while all of the following remain true:

- work stays branch-bounded
- all required gates are surfaced explicitly
- validation remains evidence-backed
- operator promotion remains mandatory

If any of those conditions weaken, the protocol should be treated as violated rather than partially satisfied.