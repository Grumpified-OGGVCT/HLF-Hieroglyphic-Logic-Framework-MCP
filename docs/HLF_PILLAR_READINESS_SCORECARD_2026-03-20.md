---
goal: Provide the first percent-backed scorecard across the major HLF pillars using the canonical internal readiness model
version: 1.0
date_created: 2026-03-20
last_updated: 2026-06-06
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
| Typed effect and capability algebra | 8 | `damaged` → operand-hardened — 12-type universe + CapabilityManifest + EffectExtractor + operand coverage matrix (12 types × 45 operators) + parametric proofs (List/Set/Map/Refinement) + manifest integrity + cross-manifest consistency + effect composition proofs (150 tests) | 82 | `partial_substantial` → `substantial` — operand completeness proofs, parametric type soundness with Z3, manifest integrity verified, effect composition proven | 75 | `bridge_owned` → operand-hardened — manifest integrity checks, cross-manifest consistency validation, full operand coverage report | 70 | 76.0 |
| Human-readable audit and trust layer | 8 | `damaged` → audit-diffable — ProvenanceChain + AuditTrail + TrustSurface + ReviewProof + AuditDiff (structural diff engine, anomaly detection, delta reports) + TrustDebtQuantifier (compound-interest projection, paydown priorities, aging) + RemediationPlanner (Kahn's topological sort, critical path DP) + TrustTrending (linear regression + R², 2σ anomaly detection, forecast with confidence bands, period comparison) — 105 tests | 82 | `partial_substantial` → `substantial` — 105 audit tests: diff correctness, debt projection accuracy, remediation plan optimality, trend statistical validity, trust chain completeness | 80 | `bridge_owned` → audit-diffable — diffable audit trails with anomaly detection, trust debt quantification with paydown priorities, auto-generated remediation plans, time-series trust trending with alerts | 78 | 80.0 |
| Real-code bridge | 6 | `damaged` → sandbox-hardened — equivalence proofs (43 tests) + TypeCoercionContract (safe HLF→Python mapping, roundtrip validation, overflow protection) + ImportWhitelist (per-tier allowlists, transitive dep scanning) + SandboxExecutor (AST-walking GasMeter, resource-capped execution, restricted builtins) + ErrorTranslator (bidirectional Python exception↔HLF violation with provenance) — 88 new tests | 82 | `thin` → `substantial` — 88 real-code bridge tests: coercion safety, import whitelist enforcement, sandbox resource caps, error translation fidelity, roundtrip guarantee | 78 | `doctrine_only` → sandbox-hardened — sandboxed execution with gas limits matching HLF tiers, whitelisted imports per capability, bidirectional error provenance | 78 | 80.0 |
| Knowledge substrate and governed memory | 10 | `present` → `hardened` — freshness guarantee, consistency proof, memory lease, + entropy-anchor drift detection (DriftDetector with structural/lexical/semantic dimensions, ReAnchoringProtocol with chain integrity), cross-witness agreement proofs (CrossWitnessProver with Byzantine tolerance 3f+1, QuorumPolicy including WEIGHTED_BY_PROFICIENCY, DisagreementResolver), memory lease hardening (LeaseNegotiator with priority-based preemption, LeaseAuditor with idle/TTL enforcement, MemoryPressureHandler with pinned lease protection, LeaseMigration with hot/warm/cold tiers), knowledge provenance chain (ProvenanceChain with Merkle-linked derivation, ProvenanceVerifier walking back to trust roots, TrustRootRegistry, ProvenanceGapDetector for orphans/broken links) | 82 | `partial_substantial` → `substantial` — 92 hardening tests covering: entropy anchor drift detection and chain integrity, cross-witness Byzantine tolerance with quorum policies, memory lease negotiation/auditing/pressure/migration, knowledge provenance Merkle verification and gap detection. Plus 24 existing tests all passing (no regressions). | 80 | `current_with_active_gaps` → `operational` — priority-based lease negotiation with preemption, TTL/idle auditing with access pattern analysis, tier-aware migration (hot/warm/cold) with utilization tracking, provenance chain verification with trust root registry and gap detection, drift severity classification with operator guidance | 78 | 80.0 |
| Formal verification surface | 7 | `partial_packaged` → verification-deepened — constitutive gating + counterexample quality (human-readable with fix suggestions, 8 violation patterns) + proof depth (BASIC/LEMMA/INDUCTIVE, depth-gated verification) + tier escalation + timeout recovery + partial proof handling (98 tests) | 78 | `strong` → `very_strong` — 60 new verification deepening tests, Z3 counterexample minimization, proof obligation extraction with impact ranking, human-readable gate explanations | 82 | `current_with_active_gaps` → verification-deepened — depth-gated verification, tier escalation through sovereign→forge→hearth, timeout recovery, partial proof detection | 75 | 78.0 |
| Gateway and routing fabric | 7 | `partial_packaged` → stress-hardened — node registry + capability router + load balancer (weighted round-robin, least-connections, resource-aware) + failover (circuit breaker, configurable backoff) + stress testing (concurrent routing, graceful degradation, partition tolerance, thundering herd) + 7 edge cases (86 tests) | 80 | `partial_substantial` → `substantial` — 35 stress tests, concurrent routing proven, edge cases handled, load balancer fairness verified | 78 | `current_with_active_gaps` → stress-hardened — circuit breaker integration, configurable exponential backoff, health check flapping resilience, partition tolerance | 75 | 78.0 |
| Orchestration lifecycle and plan execution | 7 | `partial_packaged` → failure-hardened — two-channel dispatch + plan_versioning + checkpoint_executor + classify_and_plan + execute_plan_with_routing + CoVE gate integration + SwarmLeaderElection (vector clock split-brain detection) + CrashRecovery (plan replay) + PlanRebalancer (node-loss redistribution) + SwarmHandoffContract (cryptographic receipts, capability attestation, timeout/abort) — 141 tests | 82 | `partial` → `substantial` — 141 orchestration tests: leader re-election, split-brain resolution, stale plan detection, plan rebalancing after node loss, handoff success/failure, crash recovery replay | 80 | `bridge_owned` → failure-hardened — leader election with vector clocks, split-brain resolution, crash recovery with plan replay, swarm-to-swarm handoff with cryptographic receipts | 78 | 80.0 |
| Persona and operator doctrine | 5 | `partial_packaged` → composition-hardened — Steward/Herald/Builder/Sentinel + OperatorDoctrine + PersonaGate + PersonaTransitionProof + handoff contracts + DoctrineDriftDetector (behavior-vs-doctrine comparison, corrective HLF constraint generation) + PersonaCompositionProver (multi-agent handoff soundness proofs) + CapabilityDecayModel (freshness tracking, re-certification triggers) — 97 tests | 82 | `partial_substantial` → `substantial` — 97 persona tests: drift detection accuracy, composition proof soundness, decay model correctness, handoff breach detection, 4-persona full pipeline | 78 | `current_with_active_gaps` → composition-hardened — doctrine drift detection with corrective constraints, persona composition proofs for multi-agent handoffs, capability decay monitoring with re-certification | 78 | 80.0 |
| Ecosystem integration surface | 4 | `source_only` → integration-hardened — MCP bridge + REST bridge with rate limiting, circuit breaking, retry policy, credential manager + SchemaTranslator (HLF types→JSON Schema/OpenAPI, payload validation) + DistributedRateLimiter (multi-instance coordination, Jain's fairness index) + ResilienceCoordinator (auth failure→open circuit→rotate credentials→half-open probe cascade) + BridgeHealthAggregator (weighted scoring: latency 30% + error_rate 30% + uptime 25% + failures 15%) — 88 tests | 82 | `missing` → `substantial` — 88 ecosystem tests: schema translation correctness, distributed rate fairness, resilience cascade logic, bridge health scoring accuracy | 78 | `source_only_named_path` → integration-hardened — schema translation layer, coordinated resilience (circuit breaker + credential rotation + retry), multi-bridge health aggregation with alerts | 78 | 80.0 |
| Gallery and operator-legibility surface | 4 | `damaged` → hardened — type/verification/manifest/provenance viewers + operator dashboard + TelemetryCollector (live readiness polling, ndjson streaming, trend buffer) + operator CLI (Rich dashboard, snapshot/JSON, watch mode, subcommands) | 82 | `missing` → `partial_substantial` — 65 tests (25 gallery + 40 operatorization) | 65 | `doctrine_only` → hardened — live dashboard with alerts, CLI tooling, telemetry streaming | 70 | 73.0 |

## Weighted Result

Using the canonical pillar weights, the current branch-wide internal readiness score is:

- `81.2%`

Internal interpretation band:

- `bridge-active`

## Strongest Pillars

| Pillar | Score | Why it leads |
| --- | ---: | --- |
| Deterministic language core | 92.5 | strongest combination of implementation, proof, and repo integration; type universe fully expanded, grammar complete |
| Runtime and capsule-bounded execution | 85.0 | real packaged runtime with two-channel execution and strong proof surface |
| Knowledge substrate and governed memory | 80.0 | entropy-anchor drift detection, cross-witness Byzantine agreement proofs, memory lease hardening, and knowledge provenance chain all built with 92 tests — now operational |

## Weakest Pillars

| Pillar | Score | Why it lags |
| --- | ---: | --- |
| Typed effect and capability algebra | 76.0 | 12-type universe + operand coverage + parametric proofs built, but effect composition across heterogeneous types still needs deeper proof |
| Gallery and operator-legibility surface | 73.0 | dashboard + telemetry + CLI built, but real operator feedback loop and alert fatigue metrics not yet measured |
| Formal verification surface | 78.0 | constitutive gating + counterexample quality + proof depth built, but full Z3 integration for all operator classes not complete |

## Immediate Scoring Pressure Points

The remaining legitimate readiness gains are in:

1. typed effect and capability algebra (76.0%) — heterogeneous effect composition proofs, cross-type soundness
2. gallery and operator-legibility surface (73.0%) — operator feedback loop measurement, alert fatigue metrics
3. formal verification surface (78.0%) — full Z3 operator class coverage, inductive proof automation

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
