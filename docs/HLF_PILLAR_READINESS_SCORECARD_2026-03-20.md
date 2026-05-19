---
goal: Provide the first percent-backed scorecard across the major HLF pillars using the canonical internal readiness model
version: 1.0
date_created: 2026-03-20
last_updated: 2026-05-19
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
| Human-readable audit and trust layer | 8 | `damaged` → audit-hardened — ProvenanceChain + AuditTrail (markdown/html operator reports) + TrustSurface (13 components, 12 edges, BFS validation) + ReviewProof (completeness proofs, gap detection) + two-channel executor integration (70 new tests) | 73 | `partial_substantial` → `substantial` — 60.5% proof → 70%: audit trail completeness, trust chain validation, review proof generation all verified | 70 | `bridge_owned` → audit-hardened — self-contained human-readable audit reports, trust surface DOT visualization, governed review proof pipeline | 70 | 71.0 |
| Real-code bridge | 6 | `damaged` → `present` — equivalence proofs (43 tests), effect audit, bytecode roundtrip | 75 | `thin` → `partial_substantial` — HLF↔Python equivalence verified for arithmetic, booleans, control flow | 65 | `doctrine_only` → `bridge_owned` — real-code bridge with auditable roundtrip and effect verification | 65 | 70.0 |
| Knowledge substrate and governed memory | 10 | `damaged` → `present` — freshness guarantee, consistency proof, memory lease (20 tests) | 70 | `partial` → `partial_substantial` — cross-witness agreement proofs, fork detection, trust-tier-aware freshness | 70 | `bridge_owned` → `current_with_active_gaps` — scoped lease system, entropy-anchor drift integration | 70 | 70.0 |
| Formal verification surface | 7 | `partial_packaged` using branch-aware override + Constitutive gating (not advisory) + 38 gate tests | 60 | `partial` → `strong` from `tests/test_formal_verifier.py`, verification gating, and front-door coverage | 75 | `bridge_owned` → `current_with_active_gaps` — gate is constitutive, tier-differentiated | 70 | 68.5 |
| Gateway and routing fabric | 7 | `partial_packaged` → `present` — node registry, capability router, load balancer, failover (51 tests) | 70 | `partial` → `partial_substantial` — thread-safe discovery, proficiency-based routing, round-robin + least-loaded | 68 | `bridge_owned` → `current_with_active_gaps` — failover with retry logic, health-check loop | 68 | 68.5 |
| Orchestration lifecycle and plan execution | 7 | `partial_packaged` → lifecycle-complete — two-channel dispatch + plan_versioning + checkpoint_executor + classify_and_plan + execute_plan_with_routing + CoVE gate integration (96 tests) | 72 | `partial` → `partial_substantial` — 96 orchestration lifecycle tests, full lifecycle pipeline proven | 70 | `bridge_owned` → lifecycle-complete — checkpointable execution with plan history, routing dispatch, and CoVE verification gating | 68 | 70.0 |
| Persona and operator doctrine | 5 | `partial_packaged` → doctrine-hardened — Steward/Herald/Builder/Sentinel + OperatorDoctrine (contracts, obligations, permissions, prohibitions) + PersonaGate (constitutional integration) + PersonaTransitionProof (runtime pipeline) + handoff contracts (62 new tests) | 75 | `partial_substantial` → `substantial` — 132 persona tests (59 existing + 62 doctrine + 11 gate), full 4-persona pipeline with constitutional gating proven | 68 | `current_with_active_gaps` → doctrine-hardened — operator doctrine contracts, persona gating wired, cross-persona handoff proof pipeline | 65 | 70.0 |
| Ecosystem integration surface | 4 | `source_only` → hardened — MCP bridge + REST bridge with rate limiting, circuit breaking (CLOSED/OPEN/HALF_OPEN), retry policy (exponential backoff + jitter), credential manager (scoped keys, HMAC, TTL, rotation) | 78 | `missing` → `partial_substantial` — 121 tests (68 bridge + 53 hardening) | 65 | `source_only_named_path` → hardened — production-ready middleware stack on both bridges | 65 | 70.0 |
| Gallery and operator-legibility surface | 4 | `damaged` → hardened — type/verification/manifest/provenance viewers + operator dashboard + TelemetryCollector (live readiness polling, ndjson streaming, trend buffer) + operator CLI (Rich dashboard, snapshot/JSON, watch mode, subcommands) | 82 | `missing` → `partial_substantial` — 65 tests (25 gallery + 40 operatorization) | 65 | `doctrine_only` → hardened — live dashboard with alerts, CLI tooling, telemetry streaming | 70 | 73.0 |

## Weighted Result

Using the canonical pillar weights, the current branch-wide internal readiness score is:

- `75.3%`

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
| Typed effect and capability algebra | 68.0 | 12-type universe + CapabilityManifest + EffectExtractor built, but typed contracts still partial and operand coverage incomplete |
| Formal verification surface | 68.5 | constitutive gating is wired, but proof depth and counterexample quality still need hardening |
| Gateway and routing fabric | 68.5 | node registry, capability router, load balancer, failover all built, but real-world routing stress tests remain thin |

## Immediate Scoring Pressure Points

The remaining legitimate readiness gains are in:

1. typed effect and capability algebra (68.0%) — operand coverage, type contracts, parametric type proofs
2. formal verification proof depth (68.5%) — counterexample quality, Z3 integration depth
3. gateway and routing fabric (68.5%) — real-world routing stress tests, multi-node failover scenarios

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
