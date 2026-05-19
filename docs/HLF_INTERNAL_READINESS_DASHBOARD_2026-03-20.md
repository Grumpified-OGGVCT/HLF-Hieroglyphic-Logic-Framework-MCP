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
| Overall repo readiness | 64.7% | bridge-active |
| Implementation saturation | 64.5% | branch has real substance, constitutive pillars (types, grammar, verification, constitutional) now packaged |
| Proof saturation | 65.0% | proof surfaces strengthened — constitutive gating, capability manifests, constitutional checks all proof-bearing |
| Operational integration | 66.0% | two-channel execution, provenance tracking, and manifest-gated orchestration raise operational depth |

## Cluster View

| Cluster | Included pillars | Score | Reading |
| --- | --- | ---: | --- |
| Semantic core | deterministic language core; runtime and capsule execution; typed effect algebra; real-code bridge | 73.0% | strongly improved — type universe + grammar completion + capability manifests |
| Governance and trust | governance-native execution; human-readable audit; knowledge substrate and memory; formal verification | 65.8% | constitutional checks + constitutive verification gating now operational |
| Coordination and operator systems | routing; orchestration; persona/operator doctrine; ecosystem integration; gallery/operator legibility | 42.3% | improved via two-channel execution and manifest-gated orchestration, still the drag |

## Inner Specific Percentages

These are the inner percentages the repo did not previously surface canonically.

### Per-Pillar Readiness

| Pillar | Score |
| --- | ---: |
| Deterministic language core | 92.5% |
| Runtime and capsule-bounded execution | 85.0% |
| Governance-native execution | 80.0% |
| Typed effect and capability algebra | 68.0% |
| Human-readable audit and trust layer | 60.5% |
| Real-code bridge | 45.5% |
| Knowledge substrate and governed memory | 56.0% |
| Formal verification surface | 68.5% |
| Gateway and routing fabric | 51.0% |
| Orchestration lifecycle and plan execution | 53.5% |
| Persona and operator doctrine | 45.0% |
| Ecosystem integration surface | 22.5% |
| Gallery and operator-legibility surface | 39.5% |

### Constitutive Pressure Summary

| Pressure Area | Current internal reading |
| --- | --- |
| What is most built | language core, runtime, governance spine, type universe, grammar |
| What is most under-proved relative to importance | real-code bridge, ecosystem integration, gallery legibility |
| What is best planned relative to current implementation | memory governance, dream/media bridge, capability manifest integration |
| What most suppresses the total score | ecosystem integration, gallery/operator legibility, real-code bridge, routing depth |

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

- the semantic core is now at production strength (92.5% language core, 85% runtime)
- the constitutive pieces that make the HLF thesis true (types, grammar, verification gating, constitutional check, capability manifest, two-channel execution) are all packaged
- the largest remaining weakness is ecosystem integration (22.5%) — the bridge between HLF's internal guarantees and external systems
- gallery legibility (39.5%) and real-code bridge (45.5%) remain under-proved relative to their importance for operator adoption

## What Should Move The Score Next

The most score-efficient work, while still respecting doctrine, is:

1. strengthen the real-code bridge with equivalence proofs between HLF output and executable code
2. raise ecosystem integration from source-only into packaged proof with at least one end-to-end external integration
3. deepen gallery and operator legibility with a true packaged gallery proof suite
4. extend routing fabric depth beyond the current branch slice to full multi-node routing
5. keep memory governance and evidence contracts converging so the trust substrate improves without fragmentation

## 2026-05-19 Constitutive Build Validation — Post Phase 1-6

The six constitutive build phases are now complete and committed:

- **Phase 1**: Type Universe expanded (ℤ ℝ ℚ + parametric + refinement types) — 160 tests
- **Phase 2**: Grammar completion (§ ~ ⊖ operators, exponentiation, bitwise, list literals, pattern matching) — 107 tests
- **Phase 3**: Constitutive verification gating (tier-differentiated, no longer advisory) — 93 tests
- **Phase 4**: Constitutional check wired (4 rules with real implementations) — 136 tests
- **Phase 5**: Capability manifest as compiled artifact (signed effect profiles) — 108 tests
- **Phase 6**: Two-channel execution model (instruction/data separation, pointer provenance) — 57 tests

Total: 661 new tests across 6 phases, zero regressions in the core suite.

The thesis-proving pieces (types, grammar, verification gating, constitutional check, capability manifest, two-channel execution) are now all packaged and operational. The remaining gaps are in ecosystem integration, gallery legibility, and real-code bridge — areas that don't falsify the HLF thesis but limit its reach.

Interpretation:
- the semantic core (language, runtime, types, grammar) is now at production strength
- governance and trust (constitutional check, verification gating, manifest signing) is operational
- the coordination-and-operator cluster remains the drag, but two-channel execution and provenance tracking provide a solid foundation
- next score-moving work should target ecosystem integration and gallery legibility

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
