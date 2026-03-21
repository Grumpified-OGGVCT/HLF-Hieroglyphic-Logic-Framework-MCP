---
goal: Provide a percent-backed internal readiness dashboard wired to the repo's existing plans, matrices, and branch-aware truth surfaces
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'In progress'
tags: [readiness, dashboard, planning, internal, governance]
lane: bridge-true
audience: internal operators and maintainers
---

# HLF Internal Readiness Dashboard

## Purpose

This document is the percent-backed internal dashboard for the repo.

It does three things at once:

1. gives one overall readiness percent
2. gives inner, cluster-level, and pillar-level percentages
3. wires the existing plans, truth docs, and matrices into one planning surface

## Dashboard Inputs

| Input Surface | Dashboard Role |
| --- | --- |
| `docs/HLF_READINESS_SCORING_MODEL.md` | canonical scoring rules |
| `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md` | pillar-by-pillar scored baseline |
| `docs/HLF_MISSING_PILLARS.md` | implementation-state feed |
| `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | proof-state feed |
| `SSOT_HLF_MCP.md` | branch-aware current-truth corrections |
| `HLF_IMPLEMENTATION_INDEX.md` | packaged/bridge ownership anchors |
| `HLF_ACTIONABLE_PLAN.md` | active bridge-track obligations |
| `plan/architecture-hlf-reconstruction-2.md` | master sequencing authority |
| `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` | control maturity pressure |
| `HLF_MCP_TODO.md` | open backlog pressure and next batch obligations |
| `docs/HLF_READINESS_REFRESH_PROCEDURE.md` | triggered refresh contract and validation checkpoint authority |

## Top-Level Indices

| Index | Score | Reading |
| --- | ---: | --- |
| Overall repo readiness | 58.9% | bridge-active |
| Implementation saturation | 57.3% | branch has real substance, but many constitutive pillars remain damaged or partial |
| Proof saturation | 58.0% | several strong proof surfaces exist, but they remain unevenly distributed |
| Operational integration | 64.3% | planning, doctrine, and branch wiring are ahead of packaged completion |

## Cluster View

| Cluster | Included pillars | Score | Reading |
| --- | --- | ---: | --- |
| Semantic core | deterministic language core; runtime and capsule execution; typed effect algebra; real-code bridge | 70.8% | strongest current cluster |
| Governance and trust | governance-native execution; human-readable audit; knowledge substrate and memory; formal verification | 59.8% | real substance, still proof- and contract-heavy bridge work |
| Coordination and operator systems | routing; orchestration; persona/operator doctrine; ecosystem integration; gallery/operator legibility | 41.3% | main drag on total readiness |

## Inner Specific Percentages

These are the inner percentages the repo did not previously surface canonically.

### Per-Pillar Readiness

| Pillar | Score |
| --- | ---: |
| Deterministic language core | 87.5% |
| Runtime and capsule-bounded execution | 82.5% |
| Governance-native execution | 70.5% |
| Typed effect and capability algebra | 48.5% |
| Human-readable audit and trust layer | 57.5% |
| Real-code bridge | 45.5% |
| Knowledge substrate and governed memory | 56.0% |
| Formal verification surface | 51.0% |
| Gateway and routing fabric | 51.0% |
| Orchestration lifecycle and plan execution | 45.5% |
| Persona and operator doctrine | 38.5% |
| Ecosystem integration surface | 22.5% |
| Gallery and operator-legibility surface | 39.5% |

### Constitutive Pressure Summary

| Pressure Area | Current internal reading |
| --- | --- |
| What is most built | language core, runtime, governance spine |
| What is most under-proved relative to importance | typed effects, formal verification depth, orchestration |
| What is best planned relative to current implementation | memory governance, dream/media bridge, persona/operator doctrine |
| What most suppresses the total score | ecosystem integration, gallery/operator legibility, persona/runtime proof, orchestration depth |

## Wiring Map

This is the explicit wiring between existing repo planning surfaces and the readiness dashboard.

| Dashboard section | Main upstream source | How it is used |
| --- | --- | --- |
| overall score | `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md` | weighted average across all pillars |
| implementation index | `docs/HLF_MISSING_PILLARS.md` plus branch-aware overrides from `SSOT_HLF_MCP.md` | converts status classifications into implementation percentages |
| proof index | `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | converts coverage statuses into proof percentages |
| operational index | `HLF_ACTIONABLE_PLAN.md`, `plan/architecture-hlf-reconstruction-2.md`, `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`, `HLF_MCP_TODO.md` | converts planning maturity and operational wiring into percentages |
| formal-verifier adjustment | `SSOT_HLF_MCP.md`, `HLF_IMPLEMENTATION_INDEX.md` | corrects older source-only assumptions for this branch |
| routing adjustment | `SSOT_HLF_MCP.md`, `HLF_IMPLEMENTATION_INDEX.md`, `docs/HLF_ROUTING_RECOVERY_SPEC.md` | credits real packaged route-evidence slices without overstating restoration |
| orchestration adjustment | `HLF_IMPLEMENTATION_INDEX.md`, `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` | credits packaged lifecycle presence while preserving the broader gap |
| persona/operator adjustment | `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md`, `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md`, `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md` | credits real internal contracts despite thin runtime proof |

## What The Score Says

The repo is not in a vague “somewhere in the middle” state.

The score says something more specific:

- the semantic core is already strong enough to count as real infrastructure
- the repo has built more governance, trust, and bridge wiring than a public-main skim would suggest
- the largest remaining weakness is not the parser or compiler
- the largest remaining weakness is the broader coordination-and-operator zone: routing depth, orchestration depth, persona/runtime proof, ecosystem compatibility, and gallery/operator completion

## What Should Move The Score Next

The most score-efficient work, while still respecting doctrine, is:

1. raise typed effect and capability algebra from damaged doctrine into stronger packaged contract proof
2. deepen formal verification and routing proof beyond the current branch slice
3. turn orchestration from partial lifecycle presence into a richer packaged coordination surface
4. convert persona/operator doctrine from strong internal documents into bounded proof-bearing workflow effects
5. keep memory governance and evidence contracts converging so the trust substrate improves without fragmentation

## 2026-03-20 Validation Fold-Back

The dashboard now has one real weekly-lane replay and one real persona-tagged replay behind it.

Observed evidence:

- `weekly-test-health` replay emitted a valid artifact and produced a Steward-owned governed review with `74.8%` coverage and `backlog` triage
- `weekly-doc-accuracy` replay emitted a valid artifact and produced a Herald-owned governed review with no measured drift and `ignore` triage
- the first weekly replay also exposed an actual blocker in `.github/scripts/spec_drift_check.py`, which means the weekly evidence lane is useful not just as reporting but as regression discovery

Interpretation:

- persona-tagged workflow effects are now operationally demonstrated in packaged weekly governance
- the coordination-and-operator cluster remains the main drag on total readiness, but it is now backed by live branch evidence instead of doctrine alone
- the next score-moving work should bias toward proof-bearing surfaces, not more explanatory prose

## What Should Not Move The Score Artificially

The dashboard must not be gamed by:

- rewriting prose without changing proof surfaces
- renaming bridge work as current truth
- adding decorative operator docs without packaged authority underneath
- crediting source-only files as if they were packaged completion

## Recommended Maintenance Rule

When a major pillar changes, update these in order:

1. `SSOT_HLF_MCP.md` if current truth moved
2. `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` if proof moved
3. `docs/HLF_MISSING_PILLARS.md` if implementation-state classification changed
4. `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
5. this dashboard file

The triggered guard for that rule is now:

- `.github/workflows/readiness-refresh.yml`
- `.github/scripts/readiness_refresh_check.py`

## Related Files

- `docs/HLF_READINESS_SCORING_MODEL.md`
- `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `HLF_ACTIONABLE_PLAN.md`
- `plan/architecture-hlf-reconstruction-2.md`
