---
goal: Provide the first percent-backed scorecard across the major HLF pillars using the canonical internal readiness model
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'In progress'
tags: [readiness, scorecard, pillars, governance, internal]
lane: bridge-true
audience: internal operators and maintainers
---

# HLF Pillar Readiness Scorecard

## Reading Rule

This scorecard is an internal planning artifact.

It does not replace:

- `SSOT_HLF_MCP.md` for current truth
- `docs/HLF_MISSING_PILLARS.md` for gap classification
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` for proof coverage
- `HLF_ACTIONABLE_PLAN.md` and `plan/architecture-hlf-reconstruction-2.md` for sequencing

It converts those surfaces into one internal scorecard using `docs/HLF_READINESS_SCORING_MODEL.md`.

## Branch-Aware Note

This scorecard is based on the current checkout on `2026-03-20`.

That matters for three pillars in particular:

- formal verification
- routing fabric
- orchestration lifecycle

Older gap docs classify these more harshly because they predate the branch-resident slices now documented in `SSOT_HLF_MCP.md` and `HLF_IMPLEMENTATION_INDEX.md`.

## Scorecard

| Pillar | Weight | Implementation basis | Impl | Proof basis | Proof | Operational basis | Ops | Readiness |
| --- | ---: | --- | ---: | --- | ---: | --- | ---: | ---: |
| Deterministic language core | 12 | `present` from `docs/HLF_MISSING_PILLARS.md` | 85 | `strong` from `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | 90 | `strong_current_integration` from `SSOT_HLF_MCP.md` and `HLF_IMPLEMENTATION_INDEX.md` | 90 | 87.5 |
| Runtime and capsule-bounded execution | 11 | `present` from `docs/HLF_MISSING_PILLARS.md` | 85 | `strong_but_incomplete` from runtime and capsule proof rows | 80 | `current_with_active_gaps` from packaged runtime plus bridge obligations | 80 | 82.5 |
| Governance-native execution | 11 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `strong` from governance, ethics, and security proof rows | 90 | `current_with_active_gaps` from packaged controls and control-matrix gaps | 80 | 70.5 |
| Typed effect and capability algebra | 8 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `partial_thin` because tool dispatch is proved but typed contracts remain incomplete | 40 | `doctrine_only` from control-matrix and TODO ownership without strong packaged closure | 45 | 48.5 |
| Human-readable audit and trust layer | 8 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `partial_substantial` from InsAIts, governed review, symbolic, and dream proof slices | 60 | `bridge_owned` via packaged operator resources and trust-surface plans | 60 | 57.5 |
| Real-code bridge | 6 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `thin` because codegen exists but equivalence proof is still sparse | 30 | `doctrine_only` from active bridge direction but weak packaged validation | 45 | 45.5 |
| Knowledge substrate and governed memory | 10 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `partial` from memory, witness, and runtime-context proof surfaces | 55 | `bridge_owned` through active recovery specs, weekly artifacts, and memory surfaces | 60 | 56.0 |
| Formal verification surface | 7 | `partial_packaged` using branch-aware override from `SSOT_HLF_MCP.md` and `HLF_IMPLEMENTATION_INDEX.md` | 45 | `partial` from `tests/test_formal_verifier.py` and front-door coverage | 55 | `bridge_owned` because packaged seam and recovery path are both explicit | 60 | 51.0 |
| Gateway and routing fabric | 7 | `partial_packaged` using branch-aware override from route traces and profile evidence surfaces | 45 | `partial` from routing/profile proof in `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | 55 | `bridge_owned` from `docs/HLF_ROUTING_RECOVERY_SPEC.md` and plan ownership | 60 | 51.0 |
| Orchestration lifecycle and plan execution | 7 | `partial_packaged` leaning lower because lifecycle exists but fuller orchestration remains unrecovered | 40 | `partial_thin` from limited front-door proof only | 45 | `bridge_owned` through packaged instinct plus explicit recovery planning | 60 | 45.5 |
| Persona and operator doctrine | 5 | `partial_packaged` on doctrine only: strong internal docs/contracts, weak runtime integration | 35 | `thin` because packaged runtime and workflow tests are still minimal | 30 | `bridge_owned` through new operator doctrine contracts and ownership matrix | 60 | 38.5 |
| Ecosystem integration surface | 4 | `source_only` from `docs/HLF_MISSING_PILLARS.md` | 25 | `missing` in packaged proof | 10 | `source_only_named_path` from action plan and ecosystem bridge planning | 35 | 22.5 |
| Gallery and operator-legibility surface | 4 | `damaged` from `docs/HLF_MISSING_PILLARS.md` | 55 | `missing` for a true packaged gallery proof suite | 10 | `doctrine_only` with some packaged report work but limited end-to-end operatorization | 45 | 39.5 |

## Weighted Result

Using the canonical pillar weights, the current branch-wide internal readiness score is:

- `58.9%`

Internal interpretation band:

- `bridge-active`

## Strongest Pillars

| Pillar | Score | Why it leads |
| --- | ---: | --- |
| Deterministic language core | 87.5 | strongest combination of implementation, proof, and repo integration |
| Runtime and capsule-bounded execution | 82.5 | real packaged runtime with strong proof, even though richer semantics remain open |
| Governance-native execution | 70.5 | strong control and proof surfaces despite still-damaged typed-effect closure |

## Weakest Pillars

| Pillar | Score | Why it lags |
| --- | ---: | --- |
| Ecosystem integration surface | 22.5 | explicit doctrine exists, but packaged proof and implementation remain mostly absent |
| Persona and operator doctrine | 38.5 | internal contracts are now real, but proof of runtime and workflow effect is still thin |
| Gallery and operator-legibility surface | 39.5 | operator legibility has improved, but gallery-grade packaged proof remains weak |

## Immediate Scoring Pressure Points

The fastest legitimate readiness gains are not in the already-strong language core.

They are in:

1. typed effect and capability algebra
2. knowledge substrate and governed memory contracts
3. formal verification proof depth
4. routing and orchestration restoration
5. persona and operator doctrine proof surfaces

## 2026-03-20 Live Validation Checkpoint

Two real local validation slices were run against the branch's weekly-governance machinery and folded back into this scorecard as evidence notes.

### Weekly lane: `weekly-test-health`

- Local replay path: `observability/local_validation/2026-03-20/test-health-chain/`
- Result: normalized artifact emitted successfully
- Governed review summary: `Test health reports partial coverage at 74.8%.`
- Owner persona: `steward`
- Recommended triage lane: `backlog`
- Validation note: the first replay attempt degraded because the local Windows venv lacked workflow coverage tooling; after installing the workflow-assumed tools, the lane replayed correctly
- Residual blocker surfaced by the same replay: `tests/test_github_scripts.py::TestSpecDriftCheck::test_count_mcp_tools` failed before the follow-on fix in `.github/scripts/spec_drift_check.py`

### Persona-tagged lane: `weekly-doc-accuracy`

- Local replay path: `observability/local_validation/2026-03-20/doc-accuracy/`
- Result: normalized artifact emitted successfully
- Governed review summary: `Documentation accuracy review found no measured drift.`
- Owner persona: `herald`
- Recommended triage lane: `ignore`
- Validation note: this is now a real packaged persona-tagged workflow effect, not just doctrine text

### Score Interpretation After Validation

- keep the current numeric scores unchanged for now
- treat these runs as proof that persona-tagged governed review is operationally real in packaged weekly flows
- use the observed `74.8%` test-health reading and successful Herald handoff as evidence when reprioritizing proof-bearing bridge work rather than as a reason to inflate public claims

## Related Files

- `docs/HLF_READINESS_SCORING_MODEL.md`
- `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
- `docs/HLF_READINESS_REFRESH_PROCEDURE.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `SSOT_HLF_MCP.md`
