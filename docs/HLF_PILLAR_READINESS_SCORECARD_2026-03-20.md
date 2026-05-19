---
goal: Provide the first percent-backed scorecard across the major HLF pillars using the canonical internal readiness model
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20-v3
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
| Deterministic language core | 12 | `present` from `docs/HLF_MISSING_PILLARS.md` + Type Universe expansion (ℤ ℝ ℚ, parametric, refinement) + Grammar completion (§ ~ ⊖) | 95 | `strong` from `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` + 160+ new tests | 92 | `strong_current_integration` from `SSOT_HLF_MCP.md` and `HLF_IMPLEMENTATION_INDEX.md` | 90 | 92.5 |
| Runtime and capsule-bounded execution | 11 | `present` from `docs/HLF_MISSING_PILLARS.md` + Two-channel execution model | 88 | `strong_but_incomplete` from runtime and capsule proof rows + 57 two-channel tests | 85 | `current_with_active_gaps` from packaged runtime plus bridge obligations | 80 | 85.0 |
| Governance-native execution | 11 | `damaged` → `partial_packaged` from `docs/HLF_MISSING_PILLARS.md` + Constitutional check wired (4 real rules) | 70 | `strong` from governance, ethics, and security proof rows + 36 constitutional tests | 92 | `current_with_active_gaps` from packaged controls and control-matrix gaps | 80 | 80.0 |
| Typed effect and capability algebra | 8 | `damaged` → `present` from `docs/HLF_MISSING_PILLARS.md` + 12-type universe + CapabilityManifest + EffectExtractor | 75 | `partial_thin` → `partial_substantial` — typed contracts complete, capability manifest signed, 108 manifest tests | 65 | `doctrine_only` → `bridge_owned` — manifest compiled artifact with swarm integration | 60 | 68.0 |
| Human-readable audit and trust layer | 8 | `damaged` from `docs/HLF_MISSING_PILLARS.md` + ProvenanceChain tracking | 58 | `partial_substantial` from InsAIts, governed review, symbolic, and dream proof slices | 60 | `bridge_owned` via packaged operator resources, trust-surface plans, and provenance chains | 65 | 60.5 |
| Real-code bridge | 6 | `damaged` → `present` — equivalence proofs (43 tests), effect audit, bytecode roundtrip | 75 | `thin` → `partial_substantial` — HLF↔Python equivalence verified for arithmetic, booleans, control flow | 65 | `doctrine_only` → `bridge_owned` — real-code bridge with auditable roundtrip and effect verification | 65 | 70.0 |
| Knowledge substrate and governed memory | 10 | `damaged` → `present` — freshness guarantee, consistency proof, memory lease (20 tests) | 70 | `partial` → `partial_substantial` — cross-witness agreement proofs, fork detection, trust-tier-aware freshness | 70 | `bridge_owned` → `current_with_active_gaps` — scoped lease system, entropy-anchor drift integration | 70 | 70.0 |
| Formal verification surface | 7 | `partial_packaged` using branch-aware override + Constitutive gating (not advisory) + 38 gate tests | 60 | `partial` → `strong` from `tests/test_formal_verifier.py`, verification gating, and front-door coverage | 75 | `bridge_owned` → `current_with_active_gaps` — gate is constitutive, tier-differentiated | 70 | 68.5 |
| Gateway and routing fabric | 7 | `partial_packaged` → `present` — node registry, capability router, load balancer, failover (51 tests) | 70 | `partial` → `partial_substantial` — thread-safe discovery, proficiency-based routing, round-robin + least-loaded | 68 | `bridge_owned` → `current_with_active_gaps` — failover with retry logic, health-check loop | 68 | 68.5 |
| Orchestration lifecycle and plan execution | 7 | `partial_packaged` → hardened — two-channel dispatch + plan_versioning (versioning, rollback, diff, chain integrity) + checkpoint_executor (save/resume, multi-phase integration) | 62 | `partial_thin` → `partial` — 57 two-channel tests + 30 orchestration lifecycle tests (12 awaiting lifecycle methods) | 62 | `bridge_owned` → hardened — checkpointable execution with plan history, versioning, and rollback | 65 | 63.0 |
| Persona and operator doctrine | 5 | `partial_packaged` → `present` — Steward/Herald/Builder/Sentinel with runtime proof pipeline (24 tests) | 60 | `thin` → `partial_substantial` — 4-persona pipeline proven, constitutional check integrated | 55 | `bridge_owned` → `current_with_active_gaps` — operator doctrine contracts, persona gating wired | 60 | 58.0 |
| Ecosystem integration surface | 4 | `source_only` → hardened — MCP bridge + REST bridge with rate limiting, circuit breaking (CLOSED/OPEN/HALF_OPEN), retry policy (exponential backoff + jitter), credential manager (scoped keys, HMAC, TTL, rotation) | 78 | `missing` → `partial_substantial` — 121 tests (68 bridge + 53 hardening) | 65 | `source_only_named_path` → hardened — production-ready middleware stack on both bridges | 65 | 70.0 |
| Gallery and operator-legibility surface | 4 | `damaged` → hardened — type/verification/manifest/provenance viewers + operator dashboard + TelemetryCollector (live readiness polling, ndjson streaming, trend buffer) + operator CLI (Rich dashboard, snapshot/JSON, watch mode, subcommands) | 82 | `missing` → `partial_substantial` — 65 tests (25 gallery + 40 operatorization) | 65 | `doctrine_only` → hardened — live dashboard with alerts, CLI tooling, telemetry streaming | 70 | 73.0 |

## Weighted Result

Using the canonical pillar weights, the current branch-wide internal readiness score is:

- `73.4%`

Internal interpretation band:

- `bridge-active`

## Strongest Pillars

| Pillar | Score | Why it leads |
| --- | ---: | --- |
| Deterministic language core | 92.5 | strongest combination of implementation, proof, and repo integration; type universe fully expanded, grammar complete |
| Runtime and capsule-bounded execution | 85.0 | real packaged runtime with two-channel execution and strong proof surface |
| Governance-native execution | 80.0 | 4 constitutional rules wired, strong proof despite still-damaged typed-effect closure |

## Weakest Pillars

| Pillar | Score | Why it lags |
| --- | ---: | --- |
| Orchestration lifecycle and plan execution | 63.0 | plan versioning and checkpointing built, but lifecycle methods (classify_and_plan, execute_plan_with_routing) not yet wired |
| Persona and operator doctrine | 58.0 | 4-persona pipeline with runtime proofs, but operator doctrine contracts still partial |
| Human-readable audit and trust layer | 60.5 | provenance chain tracking exists, but InsAIts and governed review proofs are still thin |

## Immediate Scoring Pressure Points

The fastest legitimate readiness gains are in:

1. typed effect and capability algebra
2. knowledge substrate and governed memory contracts
3. formal verification proof depth
4. orchestration lifecycle completion (classify_and_plan, execute_plan_with_routing, CoVE gate)
5. persona and operator doctrine proof surfaces
6. human-readable audit and trust layer (InsAIts + governed review proofs)

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
