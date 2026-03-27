---
goal: Establish a single internal source of truth for preserved persona doctrine, operator roles, authority boundaries, and safe future integration into HLF_MCP
version: 2.0
date_created: 2026-03-19
last_updated: 2026-03-20
owner: GitHub Copilot
status: Active bridge doctrine
tags: [persona, operator, doctrine, recovery, governance, hlf, internal]
lane: bridge-true
audience: internal operators and future repo-maintainers
---

# HLF Persona And Operator Recovery Spec

## Executive Summary

This document is the internal source of truth for the preserved upstream persona system and how it does or does not fit into `HLF_MCP` today.8081

The core answer is:

- the persona stack is architecturally valuable and should be preserved
- the persona stack is not current packaged runtime authority
- several personas are immediately useful as repo-level internal operator roles
- direct autonomous promotion of the full upstream persona system into live self-modifying repo authority is too dangerous today
- a bounded, operator-visible, review-first integration path is appropriate and should be roadmapped for the recursive-build lane

The correct near-term move is not “turn the whole persona swarm on.”
The correct move is to recover persona doctrine into explicit internal control surfaces, then selectively bind a few of those surfaces into packaged reports, review gates, and build-assist workflows.

## 1. Core Position

### What these personas are

The preserved persona files under `hlf_source/config/personas/` are not prompt garnish.
They are a doctrine layer describing role-specialized governance, review, planning, security, synthesis, memory, performance, documentation, and self-improvement responsibilities in the broader Sovereign system.

### What they are not

They are not automatically safe to treat as:

- hidden runtime authority
- unattended code-writing authority
- silent merge authority
- self-modifying prompt authority inside the packaged product surface

### Repo-level judgment

For `HLF_MCP` now:

- **current-true**: personas matter as preserved architectural and operator context
- **bridge-true**: personas can be mapped into bounded internal review and build-assist roles
- **not current-true**: the full upstream persona stack is not a packaged autonomous runtime subsystem in this repo

## 2. Authority Split

### Live authority now

These files are the live authority for how agents should reason about this repo today:

| File | Status | Why |
| --- | --- | --- |
| `AGENTS.md` | live repo authority | active workspace handoff and anti-reduction doctrine for HLF_MCP |
| `docs/HLF_AGENT_ONBOARDING.md` | live repo authority | tells unfamiliar agents how to distinguish product truth, bridge surfaces, and source context |
| `docs/HLF_CLAIM_LANES.md` | live repo authority | governs wording and maturity claims |
| repo memory files such as `/memories/repo/HLF_MCP.md` and `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md` | live internal context | persistent repo-scoped operating memory used for decisions |
| this file | live internal bridge authority | single internal doctrine brief for persona recovery and safe integration |

### Preserved context only

These files remain important but are not packaged runtime authority:

| File or Surface | Status | Why |
| --- | --- | --- |
| `hlf_source/AGENTS.md` | preserved context | broader Sovereign OS doctrine, not current repo contract |
| `hlf_source/.github/copilot-instructions.md` | preserved context | upstream scaffold and operating worldview |
| `hlf_source/config/personas/*.md` | preserved context | role doctrine and operator semantics from the larger build |
| `hlf_source/config/agent_registry.json` | preserved context | registry, models, tiers, and role map from the larger system |
| `hlf_source/config/jules_tasks.yaml` | preserved context | ambitious autonomous pipeline from the larger system, not current packaged safe authority |
| generic hat agents in the registry | preserved context | useful framing, not current repo-level executable governance |

### Bridge-contract candidates

These are the safe targets for future bounded integration:

- structured persona ownership labels in operator reports
- persona-tagged review checkpoints in evidence and trust outputs
- operator-facing approval states such as `steward_review`, `sentinel_review`, `strategist_review`
- bounded repo-maintenance roles that work on branches, under tests, with human promotion discipline

## 3. Persona Stack Layers

The persona system should be understood as four layers.

### Layer A: Constitutional layer

Primary file:

- `hlf_source/config/personas/_shared_mandates.md`

Function:

- establishes the anti-reduction constitution
- bans weakening tests, silent deletion, hidden simplification, and casual prompt reduction
- requires evidence, reversibility, auditability, escalation when uncertain, and concurrency safety

Judgment:

- this is the most important upstream persona artifact
- it is too strong to ignore
- it is also too broad to inject directly as hidden runtime authority without a bounded contract

### Layer B: Named persona layer

Primary files:

- `hlf_source/config/personas/*.md`

Function:

- defines specialized roles such as security, tool governance, planning, synthesis, performance, docs, memory, forecasting, research, and prompt improvement

Judgment:

- these are the real internal role doctrines
- several map cleanly to current `HLF_MCP` needs

### Layer C: Registry and orchestration layer

Primary files:

- `hlf_source/config/agent_registry.json`
- `hlf_source/config/jules_tasks.yaml`

Function:

- assigns models, tiers, restrictions, and role metadata
- describes a strong autonomous pipeline and auto-apply posture

Judgment:

- useful as design evidence
- unsafe to adopt wholesale in this repo now
- especially unsafe where it implies auto-apply or auto-publish behavior

### Layer D: Repo-local doctrine layer

Primary files:

- `AGENTS.md`
- `docs/HLF_AGENT_ONBOARDING.md`
- this file

Function:

- adapts preserved doctrine to current HLF_MCP truth conditions
- prevents over-promotion of source context into current packaged claims

## 4. Stitched Operator Brief

This is the stitched practical view of the persona stack for `HLF_MCP`.

| Persona File | Core Responsibility | Practical Value To HLF_MCP Now | Safe Internal Fit Now | Promotion Risk |
| --- | --- | --- | --- | --- |
| `_shared_mandates.md` | constitutional operating law | extremely high | doctrine baseline for internal maintainers | high if injected invisibly into runtime decisions |
| `steward.md` | MCP workflow integrity, tool and session governance | extremely high | internal tool-call reviewer and transport/workflow gate owner | moderate |
| `sentinel.md` | adversarial security and compliance | extremely high | security review owner for build-assist and operator surfaces | moderate |
| `strategist.md` | roadmap sequencing, opportunity cost, prioritization | extremely high | planning authority for recovery and autonomous build roadmap | low |
| `scribe.md` | audit trail, gas/token accounting, memory hygiene | high | evidence and budget-review role for internal reports | moderate |
| `arbiter.md` | adjudication between competing findings or roles | high | explicit escalation and tie-break role with operator visibility | moderate to high |
| `consolidator.md` | synthesis across specialist roles | high | final internal summary and conflict/gap reporting | moderate |
| `cove.md` | terminal QA validation | high | final pre-promotion review role | moderate |
| `chronicler.md` | technical debt and architecture drift tracking | high | health and drift-monitoring role for repo maintenance | low |
| `herald.md` | documentation integrity and translation | high | doc-truth reviewer for SSOT, README, handoffs, reports | low |
| `catalyst.md` | performance and optimization | medium-high | performance benchmark and bottleneck review role | low to moderate |
| `scout.md` | external research and technology scanning | medium-high | research-only role feeding bounded improvement proposals | low |
| `oracle.md` | scenario modeling and second-order effects | medium | risk and consequence modeling for major changes | low |
| `palette.md` | UX and accessibility | medium | useful for operator UI and extension surfaces, less central for core repo maintenance | low |
| `cdda.md` | saturation-level repo analysis | medium | deep audit spike role before big architecture moves | low |
| `weaver.md` | prompt optimization and HLF self-improvement | strategically high, operationally dangerous | proposal-only meta-role under strict review | high |

## 5. Ranking By Importance And Practical Usefulness

This ranking is for `HLF_MCP` specifically, not the entire upstream Sovereign system.

### Tier 1: Immediate Internal Value

These are the persona files with the highest practical payoff for repo-level maintenance and recovery now.

1. `_shared_mandates.md`
2. `steward.md`
3. `sentinel.md`
4. `strategist.md`
5. `herald.md`
6. `chronicler.md`
7. `cove.md`

Why this tier matters:

- it covers constitutional discipline, tool governance, security, planning, documentation truth, drift detection, and final review
- those are the exact surfaces this repo currently needs most

### Tier 2: Strong Near-Term Multipliers

These are very useful once Tier 1 is stabilized as an internal workflow.

1. `scribe.md`
2. `arbiter.md`
3. `consolidator.md`
4. `catalyst.md`
5. `scout.md`

Why this tier matters:

- they improve evidence quality, conflict resolution, synthesis, performance, and external research
- they are multipliers, but they depend on Tier 1 control surfaces to stay trustworthy

### Tier 3: Situational Or Later-Phase Roles

These are valuable, but less central to present repo maintenance.

1. `oracle.md`
2. `palette.md`
3. `cdda.md`

Why this tier matters:

- they are strong specialist lenses
- they become more important once broader operator shells, UI surfaces, or major architecture spikes are active

### Tier 4: Strategic But Dangerous To Promote Early

1. `weaver.md`

Why it is last in practical promotion order:

- not because it is unimportant
- because it directly concerns prompt mutation, persona optimization, and HLF self-improvement
- that makes it strategically central but operationally risky to grant authority too early

## 6. Recommended Repo-Level Internal Role Map

If this repo adopts internal non-public persona roles, the safest first mapping is:

| Internal Role | Upstream Persona Source | Recommended Duty In HLF_MCP |
| --- | --- | --- |
| Tool and workflow reviewer | `steward.md` | validate MCP transport, tools, external calls, session discipline, schema checks |
| Security reviewer | `sentinel.md` | review security posture, fail-closed behavior, governance bypass risk |
| Planning authority | `strategist.md` | rank bridge work, sequence recovery, define what to build next |
| Documentation truth reviewer | `herald.md` | keep doctrine, SSOT, handoffs, and claims aligned |
| Drift and debt reviewer | `chronicler.md` | track misalignment between packaged truth and preserved doctrine |
| Final validation reviewer | `cove.md` | pre-promotion quality gate for major internal changes |
| Evidence and budget reviewer | `scribe.md` | check trace completeness, token/gas/evidence integrity |
| Adjudicator | `arbiter.md` | resolve conflicting recommendations with explicit operator visibility |
| Synthesis lead | `consolidator.md` | produce final internal recommendation bundle from multiple reviews |

## 7. Safe Versus Unsafe Integration

### Safe now

These are safe as repo-level internal agents or roles if they remain operator-visible and branch-bounded:

- planning and sequencing guidance
- documentation truth review
- security review
- tool-workflow review
- drift and debt review
- final validation checklists
- synthesis and escalation summaries

### Conditionally safe later

These become safe only with explicit controls:

- automated evidence classification
- persona-tagged report generation
- branch-local autonomous code suggestions
- bounded remediation tasks with full tests and no direct merge rights

Required controls:

- branch-only writes
- no direct push to protected branches
- no silent file deletion
- required tests and diagnostics
- structured human promotion point
- explicit audit trace for every recommendation and code change

### Unsafe now

These are too dangerous to promote today:

- raw upstream persona prompts as hidden runtime governors
- direct auto-apply from `jules_tasks.yaml`
- self-modifying prompt authority from `weaver.md`
- unattended repo maintenance with merge or publish rights
- hidden persona-based vetoes or permissions not surfaced to operators

## 8. Can These Become Repo-Level Autonomous Maintainers?

### Short answer

Yes, partially and later.
No, not as a full direct-import of the upstream system.

### Current judgment

The repo can responsibly move toward internal persona-backed autonomous maintenance only if it uses a staged model:

#### Stage 1: Internal advisory mode

- personas exist as documented internal roles
- they produce reports, rankings, and review outcomes
- no persona has direct hidden runtime control

#### Stage 2: Bounded branch-maintainer mode

- selected personas may draft changes on branches
- all changes remain gated by tests, diagnostics, and operator review
- no auto-publish or silent merge

#### Stage 3: Structured autonomous maintenance mode

- selected low-risk domains gain bounded autonomy
- examples: docs synchronization, report generation, drift detection, safe tool-schema updates, low-risk refactors with strong regression proof
- promotion to shared branches still requires explicit governance gates

#### Stage 4: Recursive-build assistance mode

- packaged HLF helps maintain packaged HLF through bounded local build loops
- persona doctrine informs the orchestration and review surfaces
- stronger autonomy only follows stronger proof

### Why full promotion is too dangerous today

- current repo doctrine explicitly says persona doctrine should stay out of runtime authority until a bounded packaged contract exists
- upstream persona prompts assume a larger Sovereign OS with services and controls not fully present here
- automatic prompt-driven self-improvement risks invisible authority drift
- automatic merge and publish behavior in the upstream pipeline is not yet acceptable for `HLF_MCP`

## 9. Recommended Roadmap

### Phase A: Lock the doctrine boundary

- treat this file as the internal source of truth for persona recovery
- keep upstream personas classified as preserved context, not live packaged authority
- reference persona ownership in operator notes and internal reviews only

### Phase B: Add bounded persona ownership to outputs

- add structured labels such as `owner_persona`, `review_persona`, `escalate_to_persona` in internal reports
- expose persona ownership in review handoffs, trust surfaces, and evidence summaries
- use `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` as the machine-readable bridge contract for those fields

### Phase C: Enable branch-bounded internal maintainers

- start with `strategist`, `herald`, `chronicler`, `steward`, `sentinel`, and `cove`
- restrict them to drafting, validating, and recommending
- require explicit operator approval for merge or publication
- bind their exact duties and gates through `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md`
- bind their branch-only autonomy constraints through `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md`

### Phase D: Add synthesis and adjudication

- bring in `consolidator`, `arbiter`, and `scribe` for multi-role resolution and evidence discipline
- keep all adjudication operator-visible and reversible

### Phase E: Gate recursive self-improvement

- allow `weaver` only in proposal mode first
- require measurement, diff review, rollback plan, and explicit approval for any prompt or self-improvement change
- never allow silent prompt mutation to become current truth

## 10. Concrete Recommendations For This Repo

### Adopt now

- `_shared_mandates.md` as internal constitutional reference
- `steward`, `sentinel`, `strategist`, `herald`, `chronicler`, and `cove` as named internal review roles
- this file as the single internal stitched brief
- `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md` as the exact role-and-gate contract
- `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md` as the bounded-autonomy contract
- `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` as the structured persona-tag source

### Bind later

- `scribe`, `arbiter`, `consolidator`, `catalyst`, and `scout` once internal review artifacts and evidence paths are more mature

### Do not bind yet

- full `jules_tasks.yaml` pipeline semantics
- raw agent registry restrictions and model bindings as packaged truth
- autonomous `weaver`-driven prompt mutation

## 11. Validation Criteria

- operator docs, handoffs, and internal planning surfaces map the same responsibility to the same persona consistently
- no packaged runtime behavior depends on hidden raw persona prompt text
- any persona-aware output uses structured, inspectable ownership fields rather than opaque prompt authority
- autonomous maintenance remains branch-bounded, test-gated, and promotion-disciplined

## 12. Files In Scope

### Live repo doctrine

- `AGENTS.md`
- `docs/HLF_AGENT_ONBOARDING.md`
- `docs/HLF_CLAIM_LANES.md`
- this file
- `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md`
- `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md`
- `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json`

### Preserved persona doctrine

- `hlf_source/AGENTS.md`
- `hlf_source/.github/copilot-instructions.md`
- `hlf_source/config/personas/_shared_mandates.md`
- `hlf_source/config/personas/arbiter.md`
- `hlf_source/config/personas/catalyst.md`
- `hlf_source/config/personas/cdda.md`
- `hlf_source/config/personas/chronicler.md`
- `hlf_source/config/personas/consolidator.md`
- `hlf_source/config/personas/cove.md`
- `hlf_source/config/personas/herald.md`
- `hlf_source/config/personas/oracle.md`
- `hlf_source/config/personas/palette.md`
- `hlf_source/config/personas/scout.md`
- `hlf_source/config/personas/scribe.md`
- `hlf_source/config/personas/sentinel.md`
- `hlf_source/config/personas/steward.md`
- `hlf_source/config/personas/strategist.md`
- `hlf_source/config/personas/weaver.md`
- `hlf_source/config/agent_registry.json`
- `hlf_source/config/jules_tasks.yaml`

## 13. Final Decision

Persona doctrine should be recovered and used.
It should not yet be promoted wholesale into autonomous hidden repo authority.

The right professional move is:

- preserve it
- classify it
- use it internally
- bind it gradually into explicit, auditable, branch-bounded operator workflows
- promote only the portions that earn trust through bounded recursive-build proof
