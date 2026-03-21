---
goal: Define the canonical internal readiness scoring model for HLF_MCP without collapsing claim-lane discipline into fake precision
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'In progress'
tags: [readiness, scorecard, dashboard, planning, governance, internal]
lane: bridge-true
audience: internal operators and maintainers
---

# HLF Readiness Scoring Model

## Purpose

This document defines the canonical internal scoring model for percent-backed readiness in this repo.

It exists to solve a real gap:

- the repo already has strong doctrine, backlog, and matrix tracking
- the repo does not yet have one canonical percentage model that turns those inputs into an internal readiness view
- a naive single percent would flatten current truth, bridge work, and vision into one misleading number

This model therefore provides disciplined internal scoring without weakening the repo's three-lane doctrine.

## Boundary Rule

This model is for internal planning and prioritization.

It must not be used as a public marketing claim by itself.

The outputs of this model are:

- internal progress indicators
- prioritization aids
- gap-surfacing tools
- cross-document normalization aids

The outputs of this model are not:

- proof that a pillar is complete
- permission to upgrade bridge-true work into current-true claims
- a substitute for tests, acceptance gates, or operator review

## Source Inputs

The model is intentionally downstream of existing repo authorities.

| Source | What it contributes |
| --- | --- |
| `docs/HLF_MISSING_PILLARS.md` | implementation-state baseline for each major pillar |
| `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | proof and regression coverage baseline |
| `SSOT_HLF_MCP.md` | branch-aware current-truth and packaged-surface overrides |
| `HLF_IMPLEMENTATION_INDEX.md` | branch-resident bridge slices and packaged ownership anchors |
| `HLF_ACTIONABLE_PLAN.md` | active bridge direction and implementation obligations |
| `plan/architecture-hlf-reconstruction-2.md` | master sequencing and recovery-phase authority |
| `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` | control maturity and governance hardening posture |
| `HLF_MCP_TODO.md` | open implementation obligations by batch and pillar |

## Pillar Set

The readiness model tracks the following major HLF pillars:

1. Deterministic language core
2. Runtime and capsule-bounded execution
3. Governance-native execution
4. Typed effect and capability algebra
5. Human-readable audit and trust layer
6. Real-code bridge
7. Knowledge substrate and governed memory
8. Formal verification surface
9. Gateway and routing fabric
10. Orchestration lifecycle and plan execution
11. Persona and operator doctrine
12. Ecosystem integration surface
13. Gallery and operator-legibility surface

## Scoring Dimensions

Each pillar receives three dimension scores.

### 1. Implementation Saturation

Question:

How materially present is the pillar in the current branch as packaged code, packaged contracts, or bounded internal doctrine?

Weight in pillar score:

- `50%`

### 2. Proof Saturation

Question:

How strongly is the pillar backed by tests, regression coverage, or other proof surfaces instead of prose alone?

Weight in pillar score:

- `30%`

### 3. Operational Integration

Question:

How well is the pillar wired into present repo planning, operator surfaces, bridge sequencing, and recoverability?

Weight in pillar score:

- `20%`

## Dimension Rubrics

### Implementation Saturation Rubric

| Classification | Score | Meaning |
| --- | ---: | --- |
| `present` | 85 | materially implemented now; still not assumed to be perfect |
| `damaged` | 55 | real implementation exists, but it is narrowed, misaligned, or under-powered |
| `partial_packaged` | 45 | branch-resident packaged slice exists, but the pillar is not yet broadly restored |
| `source_only` | 25 | strong source evidence exists, but the packaged recovery is still absent |
| `missing` | 10 | no credible packaged equivalent or bounded bridge contract yet |

### Proof Saturation Rubric

| Classification | Score | Meaning |
| --- | ---: | --- |
| `strong` | 90 | clear regression ownership and broad proof surface |
| `strong_but_incomplete` | 80 | strong proof exists, but important edge or equivalence cases remain open |
| `partial_substantial` | 60 | real tests and proof slices exist, but not yet enough to call the pillar well proved |
| `partial` | 55 | meaningful but incomplete proof surface |
| `partial_thin` | 40 | a small proof slice exists, but it under-represents pillar breadth |
| `thin` | 30 | mostly documentary or registration-level proof only |
| `missing` | 10 | no meaningful packaged proof surface |

### Operational Integration Rubric

| Classification | Score | Meaning |
| --- | ---: | --- |
| `strong_current_integration` | 90 | indexed, planned, operator-legible, and already part of current repo truth |
| `current_with_active_gaps` | 80 | packaged and active now, but still carrying clear bridge obligations |
| `bridge_owned` | 60 | explicit owner surfaces, active plans, and recovery path already exist |
| `doctrine_only` | 45 | doctrine and planning exist, but the pillar is not well wired operationally |
| `source_only_named_path` | 35 | source-only today, but the path back is explicit |
| `unplanned` | 15 | little or no operational integration |

## Pillar Weights

The model does not weight all pillars equally.

The weights reflect constitutive importance to HLF as a governed meaning and execution substrate.

| Pillar | Weight |
| --- | ---: |
| Deterministic language core | 12 |
| Runtime and capsule-bounded execution | 11 |
| Governance-native execution | 11 |
| Typed effect and capability algebra | 8 |
| Human-readable audit and trust layer | 8 |
| Real-code bridge | 6 |
| Knowledge substrate and governed memory | 10 |
| Formal verification surface | 7 |
| Gateway and routing fabric | 7 |
| Orchestration lifecycle and plan execution | 7 |
| Persona and operator doctrine | 5 |
| Ecosystem integration surface | 4 |
| Gallery and operator-legibility surface | 4 |

Total weight:

- `100`

## Calculation Rules

### Pillar Score

For each pillar:

```text
pillar_readiness =
  (implementation_saturation * 0.50)
  + (proof_saturation * 0.30)
  + (operational_integration * 0.20)
```

### Repo Score

Across all pillars:

```text
repo_readiness = sum(pillar_weight * pillar_readiness) / 100
```

### Dimension Indices

The repo also tracks three cross-pillar subindices:

- `implementation_index`
- `proof_index`
- `operational_index`

Each is computed as the weighted average of that dimension across all pillars.

## Interpretation Bands

These bands are internal planning aids.

| Readiness Band | Range | Internal Reading |
| --- | ---: | --- |
| `foundational` | `0-24.9` | mostly source-only, missing, or weakly planned |
| `emergent` | `25-44.9` | doctrine and early bridge work exist, but practical recovery is still thin |
| `bridge-active` | `45-64.9` | real packaged and bridge work exists, but major constitutive gaps remain |
| `strong-but-open` | `65-79.9` | materially strong with limited but still important open gaps |
| `near-claimable` | `80-100` | very strong internal posture; still subject to claim-lane discipline |

## Anti-Misuse Rules

1. A high score does not override claim lanes.
2. A high score does not substitute for acceptance gates.
3. A pillar may score well and still remain bridge-true.
4. A pillar may score poorly even if it has strong doctrine, when packaged proof is thin.
5. Source-only pillars may not be rounded upward just because the vision is strong.
6. Branch-resident slices may raise internal readiness, but they do not automatically justify public completion claims.

## Update Rule

The model should be refreshed whenever one of these materially changes:

- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `SSOT_HLF_MCP.md`
- `HLF_ACTIONABLE_PLAN.md`
- `plan/architecture-hlf-reconstruction-2.md`
- `HLF_MCP_TODO.md`

The trigger-and-check procedure for that refresh now lives in:

- `docs/HLF_READINESS_REFRESH_PROCEDURE.md`
- `.github/workflows/readiness-refresh.yml`

## Related Files

- `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
- `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `SSOT_HLF_MCP.md`
