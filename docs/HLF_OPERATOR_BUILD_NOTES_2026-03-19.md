# HLF Operator Build Notes — 2026-03-19

Status: bridge-lane handoff note for operators and future agents.

Purpose:

- state what is materially present in packaged truth
- state what is bridge work in progress
- state what remains source-only and why
- identify the next prioritized bridge slices for trustworthy HLF recovery

## Non-Reduction Rule

These notes are not permission to trim the vision down to current code.

- Vision and bridge docs remain the reconstruction authority.
- Packaged truth is the honesty boundary for present-tense claims only.
- If doctrine is ahead of the repo, the repo is expected to move toward doctrine.
- If a constitutive surface is source-only, the correct action is to classify and recover it, not to treat it as expendable because the packaged line is neater.

## Executive Read

The repo is no longer missing a coherent architecture story. It now has a clear doctrine, current-truth boundary, stitched system view, and a pillar-based recovery map.

The repo is also not yet the full recovered HLF system, and that gap should be read as reconstruction work owed to the doctrine rather than as a reason to flatten the doctrine.

What is real now is a substantial packaged MCP and runtime surface with active bridge work around evidence-backed routing, artifact-aware model promotion, witness governance, entropy-anchor checks, and capsule/pointer trust.

What is still missing are the deeper constitutive pillars that let HLF claim governed multi-agent coordination end to end: routing fabric, formal verification, orchestration lifecycle, stronger HLF knowledge-substrate and governed-memory contracts, persona/operator doctrine integration, and gallery/operator surfaces.

## Present In Packaged Truth

### Deterministic and packaged now

- Packaged FastMCP server surface in `hlf_mcp/`
- deterministic language core in `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, and `hlf_mcp/hlf/bytecode.py`
- runtime and capsule-bounded execution in `hlf_mcp/hlf/runtime.py` and `hlf_mcp/hlf/capsules.py`
- translation front door and governed memory surfaces in `hlf_mcp/server_translation.py` and `hlf_mcp/server_memory.py`
- benchmark-artifact-backed route and promotion logic already extended in packaged routing surfaces
- operator-queryable resource surfaces for artifact status, active profiles, and evidence summaries
- deterministic packaged route traces now persist in session context and are exposed through governed-route status resources
- packaged verifier reports now expose structured proof status counts and operator summaries from the packaged verifier boundary
- packaged instinct lifecycle now carries normalized task DAGs, execution traces, and execution summaries through mission state
- packaged capsule and runtime execution now consume verifier-admission decisions, denying execution on counterexamples and carrying proof verdicts into execution responses
- packaged build-observation surfaces are already strong enough to support a bounded local recursive build lane through `hlf_do`, `hlf_test_suite_summary`, and `_toolkit.py status`

### Bridge slices already landed in packaged truth

- pointer trust and approval-aware capsule mediation
- witness governance MCP tools and storage surfaces
- entropy-anchor drift checks with operator-legible audit artifacts
- route-evidence and profile-evidence resources so operators can inspect model selection logic without invoking tools directly
- fail-closed governed routing when required benchmark evidence or policy basis is absent from the packaged route decision
- verify-to-merge transitions now use structured verification reports instead of treating any non-empty verify payload as sufficient proof

## Bridge Work In Progress

These surfaces are partially represented in packaged code or docs, but they are not yet strong enough to claim as fully restored.

| Surface | Current Packaged Base | Why It Is Still Bridge Work |
| --- | --- | --- |
| Governance control matrix | `governance/align_rules.json`, `governance/host_functions.json`, capsules | Controls exist, but the repo still lacks a full operator-facing control matrix and proof mapping |
| Typed effect algebra | host-function registry and tool dispatch | Inputs, outputs, effects, and structured failures are not yet formalized as packaged contracts |
| HLF knowledge substrate and memory governance | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py` | Infinite RAG as a subsystem and HKS-facing governed retrieval surfaces are real, but freshness, supersession, trust-tier, expiry, and one runtime schema still need to be locked down coherently |
| Human trust surface | translator, audit chain, resources | Evidence exists, but policy, route, and verifier explanations are not yet complete operator products |
| Real-code bridge | `hlf_mcp/hlf/codegen.py` | Code output exists, but proof of correctness and broader target coverage are not yet packaged proof surfaces |

### Routing slice now packaged

- `hlf_mcp/hlf/routing_trace.py` defines packaged route-decision and route-trace structures
- `hlf_mcp/server_profiles.py` now persists route traces with policy basis, fallback chain, and operator summary
- `hlf_mcp/server_resources.py` now exposes `hlf://status/governed_route` and `hlf://status/governed_route/{agent_id}`
- packaged governed routing now denies execution when required benchmark evidence is missing instead of silently widening eligibility

### Verifier slice now packaged

- `hlf_mcp/hlf/formal_verifier.py` now normalizes packaged AST payloads before extraction and emits explicit proven, counterexample, unknown, skipped, and error counts in verifier reports
- packaged verifier reports now include operator summaries so MCP tools and resources share one proof vocabulary
- focused verifier regressions now cover status counting, normalized AST compatibility, failing invariants, and negative gas proofs
- `hlf_mcp/hlf/execution_admission.py` now defines a packaged verifier-admission contract so proof reports can become execution decisions instead of remaining informational only
- `hlf_mcp/server_capsule.py` and `hlf_mcp/hlf/runtime.py` now carry structured verifier verdicts through capsule validation and runtime execution, with fail-closed denial on verifier counterexamples

### Orchestration slice now packaged

- `hlf_mcp/instinct/orchestration.py` now defines packaged plan-step and execution-trace contracts for the lifecycle owner
- `hlf_mcp/instinct/lifecycle.py` now normalizes task DAG ordering, records execution traces, and computes execution summaries
- verify-to-merge gating now respects structured verification reports and execution completeness before allowing merge

## Source-Only For Now

These are constitutive to the full HLF target. They are not honest present-tense packaged claims yet, but they remain real recovery obligations.

| Surface | Main Source Evidence | Why It Stays Source-Only Right Now |
| --- | --- | --- |
| Full formal-verification stack | `hlf_source/agents/core/formal_verifier.py` | A packaged verifier slice now exists, but richer upstream verification semantics and deeper integrations still remain source authority for further recovery |
| Full routing fabric | `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/gateway/sentinel_gate.py` | Packaged routing is still advisory compared with the upstream coordination fabric |
| Full orchestration lifecycle | `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, `hlf_source/agents/core/task_classifier.py` | Packaged lifecycle and DAG slices now exist, but not the full plan-to-execute and delegation stack from upstream |
| Persona system | `hlf_source/config/personas/*.md`, `hlf_source/AGENTS.md` | Persona doctrine is preserved in docs, but not yet bounded into packaged operator contracts |
| Ecosystem roadmap | `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, `hlf_source/docs/JULES_COORDINATION.md` | Important for long-range recovery, but not higher priority than core trust and coordination pillars |
| Gallery and explainer runtime | `hlf_source/scripts/run_hlf_gallery.py`, `hlf_source/docs/hlf_explainer.html` | Operator-legibility assets are not yet reconstituted as maintained packaged surfaces |

## Prioritized Next Bridge Work

### 0. Recursive build-assist lane

- use the packaged surface immediately for local bounded build assistance
- prefer `stdio` as the first credible transport for that workflow
- keep remote `streamable-http` promotion gated until the venv-safe MCP initialize path is encoded in repo-owned smoke workflow and passes end to end repeatably
- write the explicit operator workflow for using `hlf_do`, `hlf_test_suite_summary`, witness/audit surfaces, and `_toolkit.py status` together

### 1. Operator trust and routing proof

- finish `docs/HLF_PILLAR_MAP.md`-driven Batch 1 work
- refine `docs/HLF_ROUTING_RECOVERY_SPEC.md` against actual packaged routing ownership and tests
- refine `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` against the packaged verifier boundary that now exists
- maintain `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` as the proving matrix for stronger governance claims
- normalize memory evidence contracts used by route and promotion logic

### 2. Multi-agent execution proof

- produce `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md`
- define packaged handoff and delegation contracts
- add typed host-function effect gates and verifier-backed execution admission

### 3. Operator doctrine and legibility

- produce `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md`
- produce `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- add generated operator reports for route, verifier, and memory evidence

## Current Decision Rule

When deciding what to implement next, prefer the next step that improves at least one of these:

1. operator trust
2. audit completeness
3. governed multi-agent coordination
4. verifier-backed admission or denial
5. memory provenance and evidence quality

Additional bridge rule:

- if a self-build claim depends on remote MCP transport, do not promote it from bridge language into current truth until the real MCP initialize path is proven through the intended repo runtime, not just `/health`

Do not prioritize neatness of the language core over these surfaces. The language core is already real enough to stop being the default excuse for avoiding the harder constitutive pillars.

## Files To Read First Next Session

1. `AGENTS.md`
2. `docs/HLF_STITCHED_SYSTEM_VIEW.md`
3. `docs/HLF_PILLAR_MAP.md`
4. `docs/HLF_MISSING_PILLARS.md`
5. `plan/architecture-hlf-reconstruction-2.md`
6. `HLF_MCP_TODO.md`

## Handoff Note

The active planning delta for 2026-03-19 is that the repo now has an explicit pillar map and a normalized recovery priority order. Future work should treat that mapping as the execution filter for backlog edits, recovery specs, and code restoration.