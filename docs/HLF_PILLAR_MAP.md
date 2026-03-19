# HLF Pillar Map

Status: bridge-lane planning authority for constitutive pillar recovery on 2026-03-19.

Purpose:

- map each constitutive HLF pillar from doctrine and source authority into explicit reconstruction work
- state the current packaged state without letting that state shrink the target
- assign one deterministic next disposition per pillar
- define explicit recovery work across code, refactor, documentation, and proof surfaces
- rank work by operator trust, auditability, and multi-agent coordination value rather than by language-core neatness

## Authority Rule

This file is doctrine-first and reconstruction-first.

- Vision and bridge documents define what the repo must recover.
- `SSOT_HLF_MCP.md` only limits what can be claimed as implemented now.
- Current packaged gaps must drive recovery upward toward the doctrine; they must not be used to simplify the doctrine downward toward the package.
- `source_only_for_now` never means optional or unimportant. It means constitutive HLF authority that has not yet been faithfully brought back into packaged truth.

## Disposition Vocabulary

- `restore`: bring a constitutive surface back into packaged truth with runtime ownership
- `faithful_port`: port upstream behavior into a new packaged boundary without flattening the source design
- `bridge_contract`: add bounded packaged interfaces, docs, and proofs while leaving some richer logic upstream-only for now
- `source_only_for_now`: preserve as constitutive source evidence and document why it is not yet being moved into packaged truth

## Priority Order

1. routing fabric and operator-visible route evidence
2. formal verification and executable proof surfaces
3. orchestration lifecycle and multi-agent plan execution
4. HLF knowledge substrate, governed memory, provenance, and audit contracts
5. persona and operator doctrine integration
6. gallery/operator-legibility surfaces
7. real-code bridge and broader ecosystem integration

## Pillar Matrix

| Pillar | Current State | Present Owners | Upstream Evidence | Disposition | Priority | Why This Disposition |
| --- | --- | --- | --- | --- | --- | --- |
| Deterministic language core | Present | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, `hlf_mcp/hlf/bytecode.py` | `hlf_source/hlf/hlfc.py`, `hlf_source/hlf/bytecode.py` | `bridge_contract` | P4 | Core is authoritative now; remaining work is proof and bridge reporting, not wholesale restoration |
| Governance-native execution | Strong but misaligned | `governance/align_rules.json`, `governance/host_functions.json`, `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py` | `hlf_source/governance/ALIGN_LEDGER.yaml`, `hlf_source/agents/gateway/sentinel_gate.py` | `bridge_contract` | P2 | Packaged governance is real, but control-matrix and fail-closed proof surfaces still need explicit bridge work |
| Typed effect and capability algebra | Strong but not yet packaged | `governance/host_functions.json`, `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`, `hlf_mcp/hlf/tool_dispatch.py` | `hlf_source/governance/hls.yaml`, `hlf_source/agents/core/formal_verifier.py` | `faithful_port` | P2 | Current contracts are registry-centric; typed effects and structured failure proofs need a stronger packaged layer |
| Human-readable audit and trust layer | Strong but misaligned | `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/insaits.py`, `hlf_mcp/hlf/audit_chain.py`, `hlf_mcp/server_resources.py` | `hlf_source/docs/hlf_explainer.html`, `hlf_source/gui/app.py` | `bridge_contract` | P1 | Operator trust depends on readable route, policy, and execution evidence before more invisible runtime growth |
| Real-code bridge | Strong but misaligned | `hlf_mcp/hlf/codegen.py`, `hlf_mcp/hlf/compiler.py` | `hlf_source/hlf/translator.py`, `hlf_source/scripts/run_hlf_gallery.py` | `bridge_contract` | P5 | Present codegen is real, but proof of output correctness and broader target coverage remain bridge work |
| HLF knowledge substrate and governed memory | Strong but misaligned | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` | `hlf_source/agents/core/memory_scribe.py`, `hlf_source/agents/core/context_pruner.py`, `hlf_source/scripts/verify_chain.py` | `faithful_port` | P2 | Infinite RAG is a real packaged memory subsystem, and HLF Knowledge Substrate (HKS) bridge surfaces now integrate with it, but the broader governed knowledge substrate still needs stronger provenance, freshness, confidence, revocation, package-boundary, and weekly-evidence contracts |
| Formal verification surface | Wrongly deleted | no packaged authority; bridge traces exist in `hlf_mcp/hlf/entropy_anchor.py` | `hlf_source/agents/core/formal_verifier.py` | `faithful_port` | P1 | This is constitutive for governed claims and cannot stay an aspiration-only surface |
| Gateway and routing fabric | Strong but not yet packaged | `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, `hlf_mcp/server_resources.py` | `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/gateway/sentinel_gate.py` | `faithful_port` | P1 | Advisory routing exists, but upstream routing fabric carries multi-agent and policy semantics that remain under-modeled |
| Orchestration lifecycle and plan execution | Wrongly deleted | `hlf_mcp/instinct/lifecycle.py`, `hlf_mcp/server_instinct.py` | `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, `hlf_source/agents/core/task_classifier.py` | `faithful_port` | P1 | Lifecycle fragments exist, but plan-to-execute and handoff contracts are not packaged |
| Persona and operator doctrine | Strong but not yet packaged | `AGENTS.md`, `docs/AGENTS_CATALOG.md`, `docs/ETHICAL_GOVERNOR_HANDOFF.md` | `hlf_source/AGENTS.md`, `hlf_source/config/personas/steward.md`, `hlf_source/config/personas/sentinel.md`, `hlf_source/config/personas/strategist.md` | `bridge_contract` | P3 | Persona doctrine should shape review and operator flows now, but must not become uncontrolled runtime authority |
| Ecosystem integration surface | Source-only | `HLF_ACTIONABLE_PLAN.md`, `HLF_CANONICALIZATION_MATRIX.md`, `HLF_IMPLEMENTATION_INDEX.md` | `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, `hlf_source/docs/JULES_COORDINATION.md` | `source_only_for_now` | P5 | Constitutive to the full vision, but operator trust and core governed execution proofs have higher immediate value |
| Gallery and operator-legibility surface | Strong but not yet packaged | `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, `fixtures/README.md` | `hlf_source/scripts/run_hlf_gallery.py`, `hlf_source/docs/hlf_explainer.html` | `bridge_contract` | P3 | Needed for demonstrations and operator trust, but should follow route/audit proof work |

## Actionable Recovery Work

### 1. Gateway and Routing Fabric

Target disposition: `faithful_port`

- Create `docs/HLF_ROUTING_RECOVERY_SPEC.md` with upstream-to-packaged ownership for `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, and `hlf_source/agents/gateway/sentinel_gate.py`.
- Define packaged module boundaries across `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, `hlf_mcp/server_resources.py`, and a new packaged routing trace surface if required.
- Add route-trace and route-rationale contracts so selected profile, benchmark evidence, policy basis, and fallback reasons are queryable without raw tool calls.
- Add regression coverage for multi-lane route selection, route evidence persistence, and fail-closed behavior when evidence or policy requirements are missing.
- Update operator docs to explain what route evidence is authoritative now versus bridge-only.

### 2. Formal Verification Surface

Target disposition: `faithful_port`

- Create `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` mapping `hlf_source/agents/core/formal_verifier.py` into packaged ownership.
- Decide whether packaged verifier entry points belong in `hlf_mcp/hlf/` runtime helpers, MCP tool exposure, or both.
- Define proof artifacts for constraints, capability gates, and side-effect admissibility rather than treating verifier output as internal-only.
- Add deterministic tests for accepted and rejected executions, plus proof-surface serialization tests.
- Update `SSOT_HLF_MCP.md` only after a verifier surface exists in packaged truth.

### 3. Orchestration Lifecycle and Plan Execution

Target disposition: `faithful_port`

- Create `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` covering `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, and `hlf_source/agents/core/task_classifier.py`.
- Define ownership boundaries between `hlf_mcp/instinct/lifecycle.py`, packaged MCP surfaces, and any restored DAG or handoff logic.
- Add explicit contracts for delegation, dissent, escalation, and handoff lineage.
- Add tests for plan decomposition, deterministic step ordering, and multi-agent role boundaries.
- Add operator-facing lifecycle notes that explain what orchestration is implemented now versus still source-only.

### 4. HLF Knowledge Substrate and Governed Memory

Target disposition: `faithful_port`

- Keep `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` and `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` as the active recovery authorities and extend them with provenance, confidence, freshness, trust-tier, supersession, expiry, and package-boundary contracts.
- Preserve the explicit HLF-native knowledge-substrate line so HKS remains the broader constitutive surface while Infinite RAG stays visible as its distinct memory subsystem and integration point.
- Normalize memory MCP outputs in `hlf_mcp/server_memory.py` and storage contracts in `hlf_mcp/rag/memory.py` so weekly evidence, benchmark artifacts, and exemplars share one schema.
- Add deterministic verifier passes for stored evidence and artifact-history aggregation.
- Add tests for revocation, supersession, stale-artifact handling, and provenance-required retrieval paths.
- Update operator docs to distinguish advisory retrieval from governed evidence.

### 5. Governance-Native Execution and Typed Effect Algebra

Target disposition: `bridge_contract` for governance and `faithful_port` for effect algebra

- Create `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` linking align rules, host-function registry entries, capsule mediation, and route/promotion evidence to concrete operator controls.
- Add typed host-function contract fields for input schema, output schema, effect class, structured failure type, and audit requirement.
- Add tests for fail-closed host-function denial, missing-contract rejection, and policy trace completeness.
- Update `docs/HLF_HOST_FUNCTIONS_REFERENCE.md` to reflect contract-gate status rather than raw registry data only.

### 6. Human-Readable Audit and Trust Layer

Target disposition: `bridge_contract`

- Create operator-readable evidence resources for route decisions, policy basis, verifier results, and memory provenance summaries.
- Add human-facing summary generation for route promotions, benchmark evidence, and approval-required execution responses.
- Add documentation that maps each operator surface to its underlying machine authority and known limits.
- Add regression tests that assert operator summaries are grounded in packaged evidence objects rather than free text.

### 7. Persona and Operator Doctrine

Target disposition: `bridge_contract`

- Create `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` that maps persona files to review, escalation, and operator-facing behaviors.
- Keep persona doctrine in docs and handoff flows until a bounded packaged integration contract exists.
- Add operator workflow notes for steward, sentinel, strategist, and reviewer responsibilities.
- Add tests only when a packaged persona-aware boundary exists; until then, track this as doctrine and handoff work.

### 8. Gallery and Operator-Legibility Surface

Target disposition: `bridge_contract`

- Create `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` for gallery, explainer, and demo-path restoration.
- Define which surfaces stay static docs, which become generated reports, and which become queryable MCP resources.
- Add an artifact-generation path for demo-ready route/proof/memory summaries.
- Add lightweight smoke coverage for generated gallery artifacts once they exist.

### 9. Real-Code Bridge

Target disposition: `bridge_contract`

- Create a code-output proof matrix that ties `hlf_mcp/hlf/codegen.py` outputs to fixture-based equivalence checks.
- Expand supported targets only when each target has deterministic fixture coverage and an audit explanation path.
- Add docs showing what “real-code bridge” means today versus target-state claims in the doctrine.

### 10. Ecosystem Integration Surface

Target disposition: `source_only_for_now`

- Record the ecosystem cluster as constitutive source evidence in planning docs instead of flattening it away.
- Do not move this cluster ahead of routing, verifier, orchestration, memory, and operator-trust bridge work.
- Revisit after Batch 2 once packaged governance and multi-agent coordination proofs are in place.

## Batch Recommendation

### Batch 1: Operator Trust and Routing Proof

- routing fabric faithful port planning
- formal verification recovery planning
- route evidence resources and audit summaries
- governance control matrix skeleton
- HLF knowledge-substrate and memory-evidence contract normalization

### Batch 2: Multi-Agent Execution and Memory Proof

- orchestration lifecycle recovery
- typed effect algebra packaging
- verifier-backed execution admission
- memory freshness and supersession enforcement

### Batch 3: Operator Doctrine and Ecosystem Visibility

- persona/operator doctrine integration
- gallery/operator-legibility surfaces
- real-code bridge proof surfaces
- ecosystem integration checkpoint

## Working Rule

If a future task touches routing, formal verification, orchestration, memory governance, personas, or operator trust, start here before editing code. This file names the approved disposition, the packaged owners, and the priority order to follow.