---
goal: Define the concrete internal operating model for top-tier persona roles in HLF_MCP
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: Active bridge contract
tags: [persona, operator, workflow, approval, governance, internal]
lane: bridge-true
audience: internal operators and bounded repo maintainers
---

# HLF Internal Persona Operating Model

## Purpose

This document turns the persona recovery brief into an exact internal operating model for this repo.

It does not promote upstream persona prompts into hidden runtime authority.
It defines explicit repo-level responsibilities, approval gates, evidence requirements, and escalation rules for bounded internal use.

## Scope

This operating model applies to:

- internal planning and review workflows
- branch-bounded maintenance proposals
- operator-facing handoffs and review artifacts
- doctrine, bridge, governance-adjacent, and trust-surface changes

It does not apply to packaged runtime execution authority.

## Governing Rules

- Upstream persona markdown remains preserved context, not live packaged authority.
- Every persona role must remain operator-visible.
- No persona can silently merge, publish, or mutate runtime authority.
- Every approval gate must be grounded in evidence, not persona prestige.
- When gates disagree, escalation must be explicit and inspectable.

## Operating Lanes

Use this model in the bridge lane first.

| Lane | How personas may act |
| --- | --- |
| `current-true` | may classify claims and review current behavior, but may not imply packaged persona runtime authority |
| `bridge-true` | primary lane for persona-tagged planning, reviews, bounded maintainers, and approval gates |
| `vision-true` | may inform direction and target-state reasoning, but cannot override current repo controls |

## Primary Roles

These roles are the default internal operating set for the repo now.

| Persona | Internal Role | Owns | Must Produce | Cannot Do |
| --- | --- | --- | --- | --- |
| `strategist` | planning authority | scope, priority, lane choice, acceptance shape | plan decision, sequencing rationale, escalation trigger when tradeoffs are unresolved | approve runtime promotion, bypass validation, silence competing risks |
| `steward` | workflow integrity reviewer | MCP workflow, tool use, schema fit, transport discipline, auditability of action flow | workflow review outcome, changed-surface risk note, tool-call discipline note | auto-apply changes, override security findings, skip evidence checks |
| `sentinel` | security and boundary reviewer | security posture, fail-closed behavior, bypass risk, compliance-sensitive drift | security review outcome, risk severity, remediation requirements | waive security risk without operator approval, reduce controls for convenience |
| `herald` | documentation truth reviewer | SSOT alignment, README and handoff truth, claim-lane accuracy, operator readability | claim-lane review, wording corrections, doctrine parity note | rewrite claims to sound more mature than proof supports |
| `chronicler` | drift and debt reviewer | architectural drift, unresolved gaps, debt trend, bridge/current mismatch | drift note, debt tag, follow-up recommendation | approve promotion alone, suppress known drift |
| `cove` | final validation gate | completion quality, regression proof, review completeness, release readiness | validation decision, required fixes, promotion recommendation | merge changes, ignore failed diagnostics, substitute for other role reviews |

## Secondary Roles

These are available when the workflow needs stronger synthesis or conflict handling.

| Persona | Use When | Output |
| --- | --- | --- |
| `scribe` | evidence quality or artifact completeness is disputed | evidence integrity review |
| `arbiter` | two or more required roles disagree materially | explicit adjudication record |
| `consolidator` | multiple reviews need one final operator handoff | synthesis report |
| `catalyst` | performance tradeoffs materially affect change acceptance | performance review |
| `scout` | external research is required before planning or approval | research brief |

## Approval Gates

Every governed internal change uses explicit gate states.

| Gate State | Owner Persona | Required For | Allowed Decisions |
| --- | --- | --- | --- |
| `strategist_review` | `strategist` | new bridge work, priority shifts, roadmap-affecting changes, architecture-level doctrine work | `approved`, `revise`, `defer`, `escalate` |
| `steward_review` | `steward` | MCP workflow changes, tool contracts, transport changes, approval/evidence flow changes | `approved`, `revise`, `blocked`, `escalate` |
| `sentinel_review` | `sentinel` | governance-sensitive changes, external-call changes, security posture changes, policy-boundary changes | `approved`, `revise`, `blocked`, `escalate` |
| `herald_review` | `herald` | README, SSOT, handoffs, public-facing claims, operator docs | `approved`, `revise`, `blocked` |
| `chronicler_review` | `chronicler` | bridge-doctrine changes, debt-affecting refactors, any change that alters open-gap framing | `approved`, `revise`, `flag_drift` |
| `cove_review` | `cove` | promotion recommendation after implementation and validation are complete | `approved`, `revise`, `blocked` |
| `operator_promotion` | human operator | merge, release, publication, or trust-lane promotion | `promote`, `hold`, `reject` |

## Gate Order

The default gate order is:

1. `strategist_review`
2. `steward_review` when workflow or tool surfaces changed
3. `sentinel_review` when security or governance boundaries changed
4. `herald_review` when claims or docs changed
5. `chronicler_review` when drift or debt meaning changed
6. `cove_review`
7. `operator_promotion`

Not every change needs every gate, but every change must end with `cove_review` and `operator_promotion` before promotion beyond the working branch.

## Change Classes

Use these classes to decide which gates are mandatory.

| Change Class | Description | Mandatory Gates |
| --- | --- | --- |
| `planning_only` | plans, backlog sequencing, lane classification, internal priorities | `strategist_review`, `chronicler_review`, `cove_review`, `operator_promotion` |
| `docs_truth` | README, SSOT, handoffs, recovery specs, operator notes | `strategist_review`, `herald_review`, `chronicler_review`, `cove_review`, `operator_promotion` |
| `workflow_contract` | MCP workflow, tool contracts, transport matrix, evidence or approval schemas | `strategist_review`, `steward_review`, `sentinel_review`, `herald_review`, `cove_review`, `operator_promotion` |
| `security_sensitive` | governance controls, fail-closed behavior, policy checks, external effects | `strategist_review`, `sentinel_review`, `steward_review`, `cove_review`, `operator_promotion` |
| `low_risk_maintenance` | bounded internal cleanup with no change to runtime authority | `strategist_review`, role-specific review, `cove_review`, `operator_promotion` |

## Required Evidence Per Gate

| Gate | Minimum Evidence |
| --- | --- |
| `strategist_review` | change class, lane, goal, blast radius, why-now rationale |
| `steward_review` | touched workflow surfaces, affected tools/resources, schema or contract proof, validation commands |
| `sentinel_review` | security assumptions, changed boundaries, failure mode, abuse case or bypass check |
| `herald_review` | claim lane, source files, changed wording rationale, truth-vs-vision check |
| `chronicler_review` | drift summary, open-gap impact, debt note, follow-up candidate |
| `cove_review` | tests, diagnostics, changed files, unresolved risks, rollback note |
| `operator_promotion` | all required gate results plus final recommendation |

## Escalation Rules

- If `sentinel_review` returns `blocked`, the change cannot advance to `operator_promotion` without explicit human override.
- If `steward_review` and `sentinel_review` disagree on workflow safety, escalate to `arbiter` or directly to the operator.
- If `herald_review` and `strategist_review` disagree on claim lane, the stricter lane wins until an operator resolves it.
- If `cove_review` is not `approved`, the change returns to revision regardless of earlier approvals.

## Output Contract

Every persona-aware internal artifact should carry these structured fields when practical:

- `change_class`
- `lane`
- `owner_persona`
- `review_personas`
- `required_gates`
- `gate_results`
- `escalate_to_persona`
- `operator_summary`

## Minimal Workflow Example

For a bridge-doctrine documentation update:

1. `strategist` confirms the work belongs to `bridge-true` and should land now.
2. `herald` reviews claim lanes and public/internal wording boundaries.
3. `chronicler` records whether the change reduces or merely rephrases doctrinal drift.
4. `cove` checks diagnostics, completeness, and cross-file consistency.
5. Human operator decides whether to merge or keep iterating.

## Adoption Rule

Treat this document and the machine-readable ownership matrix as the concrete internal contract for persona-tagged workflows in this repo.

Do not infer stronger authority than what is written here.