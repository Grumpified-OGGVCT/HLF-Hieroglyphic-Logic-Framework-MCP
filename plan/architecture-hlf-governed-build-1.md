---
goal: Reconstruct the governed HLF build as one packaged execution stack rather than disconnected feature slices
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-22
owner: GitHub Copilot
status: 'In progress'
tags: [architecture, planning, build, governance, routing, memory, verifier, hlf]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan is the concrete build sequence for the HLF governed stack as it actually exists across the packaged repo plus the upstream anchors that still need principled restoration. The point is not to treat entropy anchors, memory, capsules, routing, Sentinel, daemons, and formal verification as separate optional extras. The point is to assemble them into one execution spine.

This plan assumes the following current packaged truth is already real and must be preserved:

- HKS validated-exemplar memory and weekly artifact capture
- pointer-bearing memory references and pass-by-reference execution primitives
- intent capsule validation and approval ledger surfaces
- audit chain logging
- advisory embedding and workload-profile routing
- packaged MCP-facing entropy-anchor evaluation

This plan also assumes the following upstream surfaces are constitutive anchors and must not be flattened away during implementation:

- gateway ingress and middleware in `hlf_source/agents/gateway/bus.py`
- deterministic ALIGN enforcement in `hlf_source/agents/gateway/sentinel_gate.py`
- MoMA routing in `hlf_source/agents/gateway/router.py`
- continuous daemon surfaces in `hlf_source/agents/core/daemons/`
- formal verification in `hlf_source/agents/core/formal_verifier.py`

Current checkpoint validated on 2026-03-21:

- packaged stdio dogfooding entrypoint is `uv run hlf-mcp`
- packaged HTTP bring-up was verified with `HLF_TRANSPORT=sse`, `HLF_PORT=8011`, and `GET /health -> 200 OK`
- repo-visible docs are being aligned to the packaged `hlf_mcp` surface rather than the legacy compatibility line
- the packaged governance spine now normalizes runtime-emitted event kinds, stable `event_ref` payloads, and approval-transition refs across `server_context`, `approval_ledger`, and operator-facing resources
- packaged memory-governance and formal-verification producers now return paired audit-plus-governance evidence instead of isolated event payloads
- operator-facing resources now expose approval-transition history, recent formal-verification evidence, and resolved route-governance basis without requiring raw tool invocation
- witness-governance trust states now produce concrete packaged routing consequences: `watched` and `probation` downshift execution into reviewable deterministic-local routing, while `restricted` fails closed into route denial and capsule-admission containment
- operator-facing governance resources now converge on a shared top-level contract with human-readable summaries and machine-readable evidence refs, while governed-route resources also emit readable fallback and policy-basis summaries

## 1. Requirements & Constraints

- **REQ-001**: The build must preserve the two-channel model: symbolic instruction lane plus pointer-resolved data lane.
- **REQ-002**: Every execution-affecting decision must remain operator-legible through audit, translation, or structured trust outputs.
- **REQ-003**: Routing, governance, memory, runtime, and verification must share traceable event and evidence references.
- **REQ-004**: The packaged lane must expose a coherent governed stack without requiring the full upstream distributed OS to exist first.
- **REQ-005**: Entropy-anchor evaluation must evolve from a single MCP tool into a reusable execution and governance primitive.
- **REQ-006**: Witness governance must feed actual execution consequences such as probation, routing degradation, or approval escalation.
- **REQ-007**: Formal verification must be callable from packaged workflows where constraints, gas feasibility, or invariant proofs matter.
- **REQ-008**: Routing must be governance-aware. Model choice cannot be separated from gas, capsule, trust, and ALIGN outcomes.
- **REQ-009**: The packaged build must have a continuous transparency path, not only compile-time decompilation.
- **REQ-010**: The default local dogfooding entrypoint must be the packaged `hlf_mcp.server:main` surface exposed as `hlf-mcp`, not the legacy compatibility server.
- **REQ-011**: HTTP liveness or transport claims must be supported by packaged-runtime proof before they are promoted into current-truth docs.
- **SEC-001**: Deterministic ALIGN enforcement must stay ahead of model dispatch and tool execution.
- **SEC-002**: Pointer trust decisions must remain explicit, auditable, and bounded by capsule policy.
- **SEC-003**: No stage may silently widen execution rights relative to current packaged capsule and approval rules.
- **SEC-004**: Formal verification failures, unknown results, and skipped checks must be surfaced explicitly rather than treated as passes.
- **ARC-001**: This is a bridge-lane architecture plan that lands in `hlf_mcp/` first while using `hlf_source/` as restoration input.
- **ARC-002**: Existing packaged files are owners unless a change explicitly introduces a new packaged module.
- **CON-001**: Do not replace current packaged surfaces with thin placeholders just to imitate the upstream layout.
- **CON-002**: Do not re-import the entire upstream service mesh wholesale; restore the constitutive semantics in bounded packaged form.
- **CON-003**: Do not treat operator transparency, daemon behavior, or verifier hooks as documentation-only concerns.

## 2. Implementation Steps

### Implementation Phase 0

- **GOAL-000**: Lock the packaged dogfooding baseline so the governed-build plan starts from verified current truth instead of a legacy entrypoint.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-000|Verify the packaged `hlf_mcp` server starts in HTTP/SSE mode with explicit environment variables and returns `200 OK` from `GET /health`.|✅|2026-03-21|
|TASK-000A|Switch workspace-local VS Code MCP wiring in `.vscode/mcp.json` to the packaged `hlf-mcp` stdio entrypoint so dogfooding targets the present-tense product surface.|✅|2026-03-21|
|TASK-000B|Update quickstart, current-truth, and operator-facing docs so the recursive build-assist story references the packaged server and bounded proof boundary accurately.|✅|2026-03-21|

### Implementation Phase 1

- **GOAL-001**: Establish one packaged governance spine that all other phases plug into.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-001|Define a packaged governance orchestration module under `hlf_mcp/` that centralizes event typing, trace references, and integration points for memory, runtime, routing, audit, and witness decisions.|||
|TASK-002|Normalize the shared event contract around current packaged owners: `hlf_mcp/server_context.py`, `hlf_mcp/hlf/audit_chain.py`, `hlf_mcp/hlf/approval_ledger.py`, and `hlf_mcp/rag/memory.py`.|✅|2026-03-21|
|TASK-003|Add explicit packaged event kinds for at least: `routing_decision`, `align_verdict`, `capsule_verdict`, `pointer_resolution`, `entropy_anchor`, `witness_observation`, `verification_result`, and `approval_transition`.|✅|2026-03-21|
|TASK-004|Ensure every event kind supports a stable `event_ref` or hash so downstream memory, witness, and audit records can point to the same execution fact.|✅|2026-03-21|

### Implementation Phase 2

- **GOAL-002**: Reconstruct packaged ingress, routing, and deterministic governance gating.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-005|Add a packaged gateway-layer module modeled on `hlf_source/agents/gateway/bus.py` but scoped for `hlf_mcp/`, preserving the middleware order: rate limiting -> HLF validation -> ALIGN gate -> replay protection -> governed routing.|||
|TASK-006|Port the deterministic ALIGN enforcement semantics from `hlf_source/agents/gateway/sentinel_gate.py` into a packaged governance helper rather than leaving them source-only.|||
|TASK-007|Extend current advisory routing in `hlf_mcp/server_profiles.py` into a packaged routing verdict API that includes model, workload class, gas impact, trust constraints, and fallback reasoning.|✅|2026-03-21|
|TASK-008|Use `hlf_source/agents/gateway/router.py` as the upstream anchor for gas, model allowlisting, idle-state logic, and fallback routing behavior, but map those semantics into packaged owners instead of copying the file structure blindly.|||
|TASK-009|Make routing consume current packaged trust state, capsule limits, and ALIGN verdicts before selecting an execution target.|✅|2026-03-21|
|TASK-010|Add regression coverage for packaged ingress and routing decisions including blocked ALIGN flows, gas failures, and fallback-routing traces.|✅|2026-03-21|

Current packaged checkpoint for Phase 2:

- a bounded packaged ingress contract now exists in `hlf_mcp/hlf/governed_ingress.py`, restoring the upstream middleware order as a deterministic helper surface: rate limit -> HLF validation -> ALIGN gate -> replay protection -> governed routing handoff
- replay protection and rate limiting are currently restored in-memory and testable first, which preserves the front-door contract without prematurely importing the upstream Redis/FastAPI gateway bus wholesale
- ALIGN gating for this packaged ingress lane now reuses the existing packaged `AlignGovernor` instead of leaving the ingress contract dependent on source-only gateway helpers
- the packaged governed-route tool path now carries the ingress contract into its existing route trace and can fail closed on replay-protection or validation denial before profile selection, without introducing a new public tool surface

### Implementation Phase 3

- **GOAL-003**: Harden runtime, pass-by-reference, and memory governance into one execution contract.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-011|Treat `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, and `hlf_mcp/server_context.py` as one subsystem and add the missing freshness, revocation, and pointer-trust checks already identified in bridge docs.|✅|2026-03-22|
|TASK-012|Promote current pointer metadata into explicit governed resolution outcomes that include trust mode, freshness verdict, revocation state, and evidence hashes.|✅|2026-03-21|
|TASK-013|Tie memory recall and pointer resolution to execution purpose so pass-by-reference is enforced as a boundary, not as a convenience API.|✅|2026-03-21|
|TASK-014|Feed weekly artifact and HKS exemplar captures into this same governed substrate so validated solutions, translation contracts, and future witness evidence share one recall discipline.|✅|2026-03-22|
|TASK-015|Add integration tests proving that runtime pointer resolution, HKS recall, and capsule trust settings interact deterministically.|✅|2026-03-22|

### Implementation Phase 4

- **GOAL-004**: Move entropy anchors from isolated tool to continuous execution primitive.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-016|Reuse `hlf_mcp/hlf/entropy_anchor.py` as the base evaluator, but add packaged call sites in runtime, translation, or governance flow where high-risk intent classes require proof-of-meaning checks automatically.|||
|TASK-017|Add policy-aware entropy-anchor thresholds keyed by workload, capsule tier, and trust state rather than a single static usage pattern.|||
|TASK-018|Record entropy-anchor outcomes into the shared governance spine so they can feed witness observations, approval escalation, or routing degradation.|✅|2026-03-21|
|TASK-019|Use upstream `hlf_source/agents/core/daemons/insaits_daemon.py` as the behavior anchor for continuous transparency rather than inventing a second unrelated audit subsystem.|||
|TASK-020|Expand tests so the packaged implementation covers direct tool usage plus automatic anchor checks in governed execution paths.|||

### Implementation Phase 5

- **GOAL-005**: Land witness governance as the trust consequence layer.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-021|Implement the already-planned packaged witness-governance substrate so execution events can produce structured witness observations with traceable evidence.|✅|2026-03-21|
|TASK-022|Ensure witness evidence can be sourced from routing anomalies, ALIGN failures, entropy-anchor drift, pointer-trust failures, verification failures, and approval bypass attempts.|✅|2026-03-21|
|TASK-023|Define deterministic trust-state outputs that affect downstream behavior: `healthy`, `watched`, `probation`, `restricted`.|✅|2026-03-21|
|TASK-024|Connect trust-state outputs to concrete packaged actions such as tighter routing, mandatory approval, or stronger entropy-anchor requirements.|✅|2026-03-21|
|TASK-025|Preserve the initial anti-fragile rule that single low-confidence events do not create irreversible isolation.|||

Current packaged checkpoint for Phase 5:

- witness observations now escalate into real routing consequences instead of remaining observational only
- witness evidence is now sourced from routing anomalies, verification failures, entropy-anchor drift, pointer-trust failures, ALIGN failures, and approval-bypass attempts through packaged owners rather than ad hoc side channels
- `watched` and `probation` trust states enforce review-required deterministic-local routing
- `restricted` trust state now denies the governed route and carries the trust basis through capsule-admission reasons
- approval-token mismatches and equivalent forged-tool approval bypass attempts now emit governance-backed witness evidence from the approval and tool-dispatch owners rather than wrapper-only stand-ins

### Implementation Phase 6

- **GOAL-006**: Restore the daemon layer in packaged form as continuous governance and transparency services.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-026|Create a packaged daemon manager modeled on `hlf_source/agents/core/daemons/__init__.py` with bounded local equivalents for Sentinel, Scribe, and Arbiter behavior.|✅|2026-03-21|
|TASK-027|Port the minimum viable Sentinel behavior from `hlf_source/agents/core/daemons/sentinel.py`: ALIGN violations, injection patterns, privilege escalation signals, and gas anomalies.|✅|2026-03-22|
|TASK-028|Port the minimum viable continuous transparency behavior from `hlf_source/agents/core/daemons/insaits_daemon.py` and `scribe.py` into a packaged audit trail/report surface.|✅|2026-03-22|
|TASK-029|Keep the packaged daemon bus local and testable first, but align event shapes with the governance spine so later service-bus restoration is additive rather than disruptive.|✅|2026-03-22|
|TASK-030|Add operator-facing query surfaces for recent daemon events, current alerts, and transparency reports.|✅|2026-03-21|

Current packaged checkpoint for Phase 6:

- a packaged local daemon manager now ingests governance events at emission time and serves rolling daemon alert/transparency state from live manager-backed data instead of read-time recomputation alone
- daemon alert and daemon transparency surfaces now expose bridge-mode queryable operator views over recent governance-spine events without introducing a second event store
- daemon transparency now includes rolling human-readable audit entries, anomaly counts, and a markdown report surface while the full daemon manager remains a later restoration step
- the packaged daemon manager now restores a bounded Sentinel lane that classifies approval bypass, ALIGN intervention, pointer-resolution denial, routing degradation, witness pressure, verification failures, and entropy drift from governance-spine events on the existing local bus
- the packaged daemon manager now restores a bounded Scribe lane that translates governance and Sentinel events into structured prose entries with token-budget accounting instead of a second reporting path
- governed recall now emits a governance-spine event under `memory_governance`, so pointer resolution, witness evidence, and governed recall all feed the same packaged Sentinel/Scribe observability surface

Current packaged checkpoint for Phase 3:

- pointer trust is no longer only a thin runtime yes/no check: the packaged memory substrate now emits explicit governed pointer-resolution outcomes carrying purpose, trust mode, freshness, governance state, provenance grade, and admission reasons
- runtime pointer dispatch now consumes that governed outcome contract so execution-purpose pointer use is enforced as a boundary rather than a convenience lookup
- the packaged MCP surface now exposes governed memory-pointer resolution directly for operator and future self-build use through the same HKS / Infinite RAG substrate
- verified weekly artifacts are now promotable into the same governed memory substrate and can be recalled through one packaged governed-evidence surface alongside HKS exemplars and witness evidence rather than via file-only side paths
- the scheduled weekly pipeline now persists both weekly artifact evidence and HKS exemplar capture when a governed memory database is configured, keeping weekly proof and validated exemplar recall on the same substrate
- cross-system regressions now prove that governed recall, pointer resolution, capsule trust, and runtime pointer dispatch agree on the same admitted evidence contract

### Implementation Phase 7

- **GOAL-007**: Integrate formal verification into packaged governed execution.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-031|Use `hlf_source/agents/core/formal_verifier.py` as the semantic anchor and extend the packaged verification surface beyond isolated helper usage.|||
|TASK-032|Add packaged verifier entry points for constraint satisfiability, SPEC-gate properties, type invariants, reachability, and gas feasibility checks where those matter to execution or approval.|||
|TASK-033|Feed verifier outcomes into the governance spine and witness layer with explicit states for proven, counterexample, unknown, skipped, and error.|||
|TASK-034|Define when verifier results are advisory versus blocking, keyed by capsule tier, trust state, and operation class.|||
|TASK-035|Add targeted regressions for counterexample handling, unknown/timeout handling, and verifier-to-approval escalation behavior.|||

Current packaged checkpoint for Phase 7:

- standalone verifier MCP tools now share the same admission contract already used by packaged execution admission and formal-verifier operator surfaces
- agent-scoped verifier-tool flows now emit subject-bound witness-governance consequences for denied and review-required verifier outcomes, rather than leaving those results as raw proof reports without trust consequences
- advisory-only and admitted-with-skips verifier outcomes now also emit explicit subject-bound evidence in a trust-neutral posture, preserving inspectability without turning non-blocking proof gaps into noisy degradation

### Implementation Phase 8

- **GOAL-008**: Expose one operator-legible packaged surface for the governed stack.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-036|Add MCP-facing tools or resources that let operators inspect routing verdicts, daemon alerts, witness state, entropy-anchor results, and formal verification reports without digging through raw storage.|✅|2026-03-21|
|TASK-036A|Expose packaged approval-transition inspection, recent formal-verification evidence, and resolved route-governance basis through operator-facing resource URIs.|✅|2026-03-21|
|TASK-036B|Expose recent approval-bypass attempts explicitly through operator-facing resource URIs, including subject-scoped trust consequences and evidence refs.|✅|2026-03-21|
|TASK-036C|Expose named operator CLI review commands for approval-bypass inspection and daemon transparency/report review so key packaged surfaces are discoverable without raw resource URIs.|✅|2026-03-21|
|TASK-037|Ensure each operator-facing result includes human-readable summaries plus machine-readable evidence references.|✅|2026-03-21|
|TASK-038|Reuse current packaged InsAIts and translation surfaces instead of creating a new explanation vocabulary.|||
|TASK-039|Add end-to-end regressions covering a governed intent flow from ingress through routing, memory, entropy-anchor, witness, verification, and operator review outputs.|✅|2026-03-21|
|TASK-040|Update SSOT and bridge docs only after the packaged surfaces are real, naming exactly which parts remain source-only.|||

Current packaged checkpoint for Phase 8:

- operator-facing status resources now expose route, witness, verifier, approval queue, entropy-anchor, daemon alert, and explicit approval-bypass slices through the same summary-plus-evidence contract
- approval-bypass status resources now surface recent blocked attempts across governed subjects and per-subject trust consequences without requiring raw governance-event inspection

## 3. Alternatives

- **ALT-001**: Keep implementing one feature slice at a time without a unified governance spine. Rejected because that is exactly how architectural surfaces keep getting forgotten.
- **ALT-002**: Copy the upstream service stack wholesale into `hlf_mcp/`. Rejected because it would obscure ownership and likely import more distributed machinery than the packaged lane can honestly sustain.
- **ALT-003**: Leave routing, daemon, and verifier behavior as source-only theory while expanding only MCP tools. Rejected because that preserves the parser-wrapper failure mode.
- **ALT-004**: Treat operator transparency as documentation only. Rejected because HLF doctrine makes human-legible trust constitutive, not decorative.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/server_context.py`
- **DEP-002**: `hlf_mcp/rag/memory.py`
- **DEP-003**: `hlf_mcp/server_memory.py`
- **DEP-004**: `hlf_mcp/hlf/runtime.py`
- **DEP-005**: `hlf_mcp/hlf/memory_node.py`
- **DEP-006**: `hlf_mcp/hlf/capsules.py`
- **DEP-007**: `hlf_mcp/server_capsule.py`
- **DEP-008**: `hlf_mcp/hlf/approval_ledger.py`
- **DEP-009**: `hlf_mcp/hlf/audit_chain.py`
- **DEP-010**: `hlf_mcp/hlf/entropy_anchor.py`
- **DEP-011**: `hlf_mcp/server_profiles.py`
- **DEP-012**: `hlf_mcp/weekly_artifacts.py`
- **DEP-013**: `hlf_source/agents/gateway/bus.py`
- **DEP-014**: `hlf_source/agents/gateway/sentinel_gate.py`
- **DEP-015**: `hlf_source/agents/gateway/router.py`
- **DEP-016**: `hlf_source/agents/core/daemons/__init__.py`
- **DEP-017**: `hlf_source/agents/core/daemons/insaits_daemon.py`
- **DEP-018**: `hlf_source/agents/core/formal_verifier.py`

## 5. Files

- **FILE-001**: `plan/architecture-hlf-governed-build-1.md` — this build sequence
- **FILE-002**: `hlf_mcp/server_context.py` — packaged governance spine entry point
- **FILE-003**: `hlf_mcp/rag/memory.py` — governed memory and HKS evidence substrate
- **FILE-004**: `hlf_mcp/server_memory.py` — packaged memory, HKS, and future witness-facing MCP surface
- **FILE-005**: `hlf_mcp/hlf/runtime.py` — execution integration point for pointer trust, entropy anchors, and verification
- **FILE-006**: `hlf_mcp/hlf/memory_node.py` — pointer verification and provenance contract
- **FILE-007**: `hlf_mcp/hlf/capsules.py` — tier, trust, and approval policy surface
- **FILE-008**: `hlf_mcp/server_capsule.py` — packaged capsule tool surface
- **FILE-009**: `hlf_mcp/hlf/entropy_anchor.py` — anti-drift primitive
- **FILE-010**: `hlf_mcp/server_profiles.py` — advisory routing owner to evolve into governed routing verdicts
- **FILE-011**: `hlf_mcp/hlf/audit_chain.py` — shared trace sink
- **FILE-012**: `hlf_mcp/hlf/approval_ledger.py` — approval consequences and escalation substrate
- **FILE-013**: `hlf_mcp/hlf/witness_governance.py` — planned trust consequence helper
- **FILE-014**: `hlf_mcp/hlf/governance_router.py` or equivalent new packaged module — planned routing/governance bridge
- **FILE-015**: `hlf_mcp/hlf/daemon_manager.py` or equivalent new packaged module — planned local daemon orchestration
- **FILE-016**: `tests/test_witness_governance.py` — trust regression coverage
- **FILE-017**: `tests/test_entropy_anchor.py` — anchor regressions to extend
- **FILE-018**: `tests/test_fastmcp_frontdoor.py` — packaged surface inventory
- **FILE-019**: new targeted tests for ingress, routing, verifier, and daemon behavior

## 6. Testing

- **TEST-001**: Verify deterministic ALIGN blocking occurs before model dispatch.
- **TEST-002**: Verify governed routing consumes gas, trust, and capsule inputs before returning a verdict.
- **TEST-003**: Verify pointer freshness, revocation, and trust-mode decisions affect runtime resolution deterministically.
- **TEST-004**: Verify automatic entropy-anchor checks can raise operator-visible drift results during governed execution.
- **TEST-005**: Verify witness observations generated from execution events produce bounded trust-state transitions.
- **TEST-006**: Verify daemon alerts and transparency prose remain tied to the same underlying event references.
- **TEST-007**: Verify verifier outcomes are never collapsed into silent success on timeout, unknown, or missing solver conditions.
- **TEST-008**: Verify operator-facing MCP surfaces expose routing, trust, anchor, and verification outcomes with evidence references.
- **TEST-009**: Run focused suites for each phase before any broad regression pass.

## 7. Risks & Assumptions

- **RISK-001**: If the governance spine is underspecified, later witness, daemon, and verifier work will fork event semantics again.
- **RISK-002**: Routing integration can become shallow if it only wraps the current profile recommendation logic without consuming trust and policy inputs.
- **RISK-003**: Formal verification can look present while remaining operationally irrelevant unless its outcomes feed execution and approval policy.
- **RISK-004**: Continuous transparency can devolve into duplicate logging if it is not wired to the same evidence references as audit and witness flows.
- **RISK-005**: Over-porting distributed upstream machinery too early can hide the real packaged owners and slow convergence.
- **ASSUMPTION-001**: The existing packaged memory, audit, approval, capsule, and runtime surfaces are strong enough to serve as the local authority layer.
- **ASSUMPTION-002**: Upstream gateway, daemon, and verifier files are reliable semantic anchors even where their deployment assumptions differ from the packaged repo.

## 8. Related Specifications / Further Reading

[plan/feature-entropy-anchors-1.md](feature-entropy-anchors-1.md)
[plan/feature-witness-governance-1.md](feature-witness-governance-1.md)
[docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md](../docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md)
[docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md](../docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md)
[docs/HLF_REPO_IMPLEMENTATION_MAP.md](../docs/HLF_REPO_IMPLEMENTATION_MAP.md)
[docs/HLF_ASSEMBLY_REFIT_MATRIX.md](../docs/HLF_ASSEMBLY_REFIT_MATRIX.md)
