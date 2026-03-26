# HLF MCP Implementation TODO

Complete blueprint for the full MCP 2024-2025 integration with self-evolving grammar.

---

## 2026-03-19 Normalized Reconstruction Backlog

This section is the active constitutive-pillar backlog.

Working stance:

- doctrine, source archaeology, and bridge plans define the target shape
- packaged truth does not define the target shape; it only defines what can be claimed as already built
- if a constitutive pillar is missing, damaged, or source-only, the task is to recover it without simplification

Use these files as the planning authorities before editing code:

- `plan/architecture-hlf-reconstruction-2.md`
- `docs/HLF_PILLAR_MAP.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `docs/HLF_MISSING_PILLARS.md`

## 2026-03-20 Score-Driven Bridge Batch

This batch is derived from the readiness scorecard and live validation checkpoint.

It does not replace the broader batch structure below.

It sharpens what should move next because those pillars are both weak and proof-bearing.

### Priority A: Typed effects and capability algebra

- [x] Add typed host-function contract fields for input schema, output schema, effect class, structured failure type, and audit requirement
- [x] Add denial-path tests for missing or malformed typed contracts
- [x] Add operator-readable policy traces that expose effect class and failure class without ambiguity

### Priority B: Orchestration lifecycle and execution admission

- [ ] Add packaged delegation, dissent, escalation, and handoff-lineage contracts
- [ ] Add deterministic orchestration trace proofs covering allowed, denied, and escalated steps
- [x] Join verifier output, route evidence, and orchestration state into one execution-admission artifact

### Priority C: Persona/runtime proof

- [ ] Add persona-tagged workflow tests beyond weekly-doc-accuracy and weekly-test-health
- [ ] Prove persona handoff fields survive artifact normalization, evidence query, and operator rendering intact
- [ ] Define the runtime boundary where persona doctrine is advisory versus authoritative

### Priority D: Ecosystem integration discipline

- [ ] Maintain a compatibility matrix by ecosystem, supported transports, and tested SDK versions
- [ ] Define one shared launch-mode and attach-mode contract across JS or TS, Java, Go, and Rust bridges
- [ ] Add a compatibility-watch workflow or documented review loop for upstream MCP SDK and protocol changes

### Batch 1: Operator Trust and Routing Proof

#### Recursive build-assist bridge lane (`bridge_contract`)

- [ ] Document the first packaged recursive build workflow around `stdio`, `hlf_do`, `hlf_test_suite_summary`, and `_toolkit.py status`
- [x] Revalidate the current `streamable-http` initialize lane beyond `/health`; live smoke now completes initialize, initialized notification, MCP list/read/call flow, and positive ingress resource proof
- [x] Extend the live HTTP smoke harness with positive ingress proof via `hlf_run` plus `resources/read` on `hlf://status/ingress/{agent_id}`
- [ ] Keep remote self-build claims out of current-truth docs until the repaired initialize path is proven end to end

#### 2026-03-22 ingress/operator-surface checkpoint (`bridge_contract`)

- [x] Thread shared ingress evidence into the remaining packaged non-route execution front doors
- [x] Expose first-class ingress operator resources at `hlf://status/ingress` and `hlf://status/ingress/{agent_id}`
- [x] Add named operator-shell parity through `hlf-operator ingress-status`
- [x] Revalidate the packaged active transport lane by completing a stdio MCP `initialize` -> `hlf_run` -> `resources/read` proof for `hlf://status/ingress/{agent_id}` with a positive `ok` render
- [x] Carry the same resource proof forward into the validated `streamable-http` smoke harness

#### Self-healing parser and correction assist (`bridge_contract`)

- [ ] Execute `plan/feature-self-healing-parser-1.md` as the bounded parser-usability lane rooted in `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/linter.py`, and `hlf_mcp/hlf/formatter.py`
- [ ] Define the canonical correction object and safe Phase 1 repair classes before any auto-apply behavior ships
- [ ] Add plain-language parser and lint explanations plus repair-preview output without weakening fail-closed compile behavior
- [ ] Add deterministic tests proving correction suggestions never silently change capability class, effect class, or execution admission

#### Routing fabric (`faithful_port`)

- [ ] Create `docs/HLF_ROUTING_RECOVERY_SPEC.md` from `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, and `hlf_source/agents/gateway/sentinel_gate.py`
- [ ] Define packaged ownership for routing traces, route rationale, and policy-backed fallback decisions across `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, `hlf_mcp/server_resources.py`, and any new routing helper module
- [ ] Add deterministic tests for lane-family route selection, evidence-backed fallback, and fail-closed behavior when route evidence is insufficient
- [ ] Document which parts of current routing are packaged truth versus bridge scaffolding

#### Formal verification (`faithful_port`)

- [ ] Create `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` from `hlf_source/agents/core/formal_verifier.py`
- [ ] Define packaged verifier ownership in `hlf_mcp/hlf/` and MCP exposure requirements before implementation starts
- [ ] Specify proof artifact formats for admitted and denied executions
- [ ] Add targeted regression plans for verifier-backed capability and side-effect admission

#### Governance control and typed effects (`bridge_contract` + `faithful_port`)

- [ ] Create `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` linking capsules, host-function registry entries, route evidence, and audit outputs to concrete controls
- [x] Define typed host-function contract fields for input schema, output schema, effect class, structured failure type, and audit requirement
- [x] Add tests for missing-contract denial and policy trace completeness
- [x] Update `docs/HLF_HOST_FUNCTIONS_REFERENCE.md` to reflect contract-gate status

#### HLF knowledge substrate, governed memory, and evidence contracts (`faithful_port`)

- [ ] Extend `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` with provenance, confidence, freshness, trust-tier, supersession, and expiry contracts
- [ ] Keep `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` and `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` synchronized so the HLF-native knowledge-substrate line remains a named constitutive pillar
- [ ] Normalize `hlf_mcp/server_memory.py` and `hlf_mcp/rag/memory.py` outputs so benchmark artifacts, exemplars, and weekly knowledge use one evidence schema
- [ ] Add deterministic verification for stored artifact histories before they influence route or promotion decisions
- [ ] Add tests for stale artifact handling, supersession, and provenance-required retrieval

#### Dream-cycle governed reflection bridge (`bridge_contract`)

- [ ] Keep `docs/HLF_DREAM_CYCLE_GAP_MAP.md` and `docs/HLF_DREAM_CYCLE_BRIDGE_SPEC.md` synchronized so dream recovery stays bounded to governed offline synthesis rather than drifting into self-awareness overclaim
- [x] Define packaged ownership for dream-cycle execution in `hlf_mcp/server_context.py` with supporting tool exposure in `hlf_mcp/server_memory.py`
- [x] Define the canonical `dream finding` and `dream cycle report` schemas with provenance, evidence refs, confidence, witness status, and advisory-only defaults
- [x] Add operator-facing dream status and findings resources through `hlf_mcp/server_resources.py`
- [ ] Bind dream findings to `observe -> propose -> verify -> promote` only after explicit promotion, supersession, and witness rules exist
- [x] Add deterministic tests proving dream findings cannot silently mutate canonical truth, route state, or policy state
- [x] Extend the dream-cycle contract so normalized media evidence objects can participate as first-class inputs with safety status, extraction mode, and provenance preserved

#### Multimodal and media evidence recovery (`bridge_contract`)

- [ ] Keep `docs/HLF_MULTIMODAL_MEDIA_RECOVERY_SPEC.md` synchronized with `docs/HLF_DREAM_CYCLE_BRIDGE_SPEC.md` so dream and memory lanes share one explicit media-evidence contract
- [ ] Define the canonical media evidence schema for image, document-image, diagram-image, audio-transcript, and video-summary artifacts
- [ ] Define packaged host-function contract requirements for vision, OCR, audio transcript, and video summary lanes before implementation starts
- [ ] Add qualification profiles for the `multimodal` lane in `hlf_mcp/server_profiles.py` so multimodal stops being an effectively empty lane family
- [ ] Add media safety controls covering EXIF or embedded metadata sanitization, prompt injection screening, unsupported payload denial, and transcript hallucination labeling
- [ ] Add operator-facing media evidence summaries through `hlf_mcp/server_resources.py` so processed media remains inspectable and provenance-bearing
- [ ] Add deterministic tests for media schema validation, media safety denial paths, provenance-required recall, and dream-cycle compatibility with media-derived evidence

#### Operator trust surfaces (`bridge_contract`)

- [ ] Add operator-readable summaries for route evidence, promotion rationale, verifier results, and memory provenance
- [ ] Ensure every human-facing summary maps back to a packaged machine authority
- [ ] Add regression tests that fail if operator summaries drift from structured evidence objects
- [ ] Update operator docs to state the limits of each trust surface clearly

### Batch 2: Multi-Agent Execution and Proof

#### Orchestration lifecycle (`faithful_port`)

- [ ] Create `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` from `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, and `hlf_source/agents/core/task_classifier.py`
- [ ] Define ownership boundaries between `hlf_mcp/instinct/lifecycle.py`, packaged MCP surfaces, and restored DAG or handoff modules
- [ ] Add packaged contracts for delegation, dissent, escalation, and handoff lineage
- [ ] Add tests for deterministic plan ordering and role-boundary enforcement

#### Multi-agent audit and verifier-backed admission

- [ ] Define how verifier output, route evidence, and orchestration state join into one execution-admission story
- [ ] Add trace artifacts that explain why an orchestration step was allowed, denied, or escalated
- [ ] Add batch-level acceptance gates covering route proof, verifier proof, and orchestration trace completeness

### Batch 3: Operator Doctrine, Legibility, and Ecosystem Visibility

#### Persona and operator doctrine (`bridge_contract`)

- [x] Create `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` from `hlf_source/config/personas/*.md` and `hlf_source/AGENTS.md`
- [x] Define operator workflow notes for steward, sentinel, strategist, and reviewer roles
- [x] Keep persona doctrine out of runtime authority until a bounded packaged contract exists
- [x] Create `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md` with exact responsibilities and approval gates
- [x] Create `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md` for Steward, Sentinel, Strategist, Herald, and CoVE
- [x] Create `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` so future agents can use structured role tags instead of raw prompt text

#### Gallery and operator-legibility surfaces (`bridge_contract`)

- [ ] Create `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` from `hlf_source/scripts/run_hlf_gallery.py` and `hlf_source/docs/hlf_explainer.html`
- [ ] Define which outputs become static docs, generated reports, or MCP resources
- [ ] Add smoke validation once generated operator artifacts exist

#### VS Code extension and operator shell (`bridge_contract`)

- [x] Create `plan/architecture-vscode-extension-bridge-1.md` covering sidecar packaging, transport matrix, settings, views, and publish discipline
- [x] Scaffold a dedicated extension boundary such as `extensions/hlf-vscode/` so Node tooling does not blur packaged Python authority
- [x] Define the extension transport matrix around `stdio`, `sse`, and `streamable-http`, with HTTP transports treated as must-have adoption surfaces and `stdio` treated as the first credible build-assist lane
- [x] Add operator-facing settings for launch command, transport, cwd, env, evidence path, and attached-server mode
- [x] Keep SSE and streamable-HTTP first-class in extension launch or attach flows, including health, endpoint, and failure-state diagnostics
- [x] Add the first operator panel slice for bridge state, evidence snapshot visibility, and packaged status-resource inventory derived from `hlf_mcp/server_resources.py`
- [x] Define the first extension-hosted operator surfaces for audit, evidence, trust state, and packaged MCP status resources
- [x] Add secret storage, first-run validation, packaged action commands, and a trust webview over packaged `hlf-operator` surfaces
- [x] Add VSIX packaging, Marketplace publication, and offline distribution requirements to the build pipeline backlog
- [x] Document publisher identity, Marketplace publication path, and offline VSIX install procedure now that local packaging exists

#### Visual operator workbench (`bridge_contract`)

- [ ] Execute `plan/architecture-visual-operator-workbench-1.md` as the bridge plan for live intent visualization, governance visibility, and later replay debugging
- [ ] Keep the first serious visual host inside `extensions/hlf-vscode/` and the packaged operator-shell path rather than starting a separate desktop GUI line
- [ ] Add machine-readable data contracts for AST, intent, governance, and execution-state visualization before building richer panels
- [ ] Treat time-travel debugging as gated on authoritative step-trace artifacts rather than immediate UI invention

#### Real-code bridge and ecosystem surfaces (`bridge_contract` + `source_only_for_now`)

- [ ] Add a proof matrix for `hlf_mcp/hlf/codegen.py` outputs using fixture-based equivalence checks
- [x] Create `plan/architecture-ecosystem-compatibility-1.md` so JavaScript/TypeScript, Java, Go, Rust, and adjacent ecosystems are tracked as an explicit compatibility bridge program
- [ ] Define the shared bridge contract for launch mode, attach mode, transport selection, endpoint semantics, health checks, and failure diagnostics across language bridges
- [ ] Add a JS/TS compatibility lane beyond the VS Code extension itself: reference launcher or client, runtime expectations, and transport smoke coverage
- [ ] Add explicit Go, Java, and Rust bridge lanes with official SDK lineage, transport expectations, and current-proof status
- [ ] Maintain a compatibility matrix showing per-ecosystem support level, tested SDK version, and supported transports
- [ ] Add a recurring compatibility-watch workflow or documented process for upstream MCP SDK and protocol changes
- [ ] Document ecosystem surfaces as constitutive source evidence in planning docs without overstating packaged truth
- [ ] Re-evaluate deeper ecosystem recovery only after Batch 1 and Batch 2 proof surfaces are in place

#### Symbolic and semasiographic surfaces (`bridge_contract`)

- [x] Create `plan/feature-symbolic-semantic-surfaces-1.md` so the Arrival-inspired symbolic-surface lane has its own governed bridge plan
- [x] Run a dedicated research pass for semasiographic notation, non-linear intent objects, temporal relations, causal relations, and agent-relation encoding
- [x] Define keyboard-safe ASCII syntax before any glyphic or rendered operator surface is promoted
- [x] Define round-trip rules between ASCII authoring, canonical AST/IR, Unicode symbolic projection, and plain-language explanation
- [x] Define which symbolic surfaces are plain-text safe, which are Unicode-only, and which require rendered operator or gallery views
- [x] Bind symbolic-surface work into grammar, translation, audit, and operator-surface plans without granting glyph renderings semantic authority
- [ ] Execute the real Phase 1 symbolic-upgrade slice in `hlf_mcp/hlf/symbolic_surfaces.py`, `tests/test_symbolic_surfaces.py`, `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`, and `plan/feature-symbolic-semantic-surfaces-1.md` before considering any new renderer or dependency
- [ ] Add relation-edge compilation, projection, and explanation tests from `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`
- [ ] Decide whether relation edges stay generic tagged glyph statements or earn a dedicated AST node after proof exists

Useful vs noise triage for this lane:

| Bucket | Classification | Why | Next action |
| --- | --- | --- | --- |
| Relation-edge semantics for time, cause, dependency, scope, and agent roles | useful now | strengthens canonical machine-checkable meaning without changing the trust model | expand compilation, projection, explanation, and audit tests |
| Side-by-side canonical source, symbolic projection, and plain-language explanation | useful now | improves operator legibility while preserving canonical authority | add audit-output proof and operator labeling |
| Compression, determinism, translation-clarity, and legibility benchmark lanes | useful now | turns symbolic claims into measurable evidence instead of style claims | define benchmark fixtures and acceptance thresholds |
| Optional rendered diagrams or gallery surfaces derived from canonical relations | useful later | can help operator understanding, but only after round-trip proof exists | keep display-only and defer until proof surfaces are green |
| Fractal or shape-based renderers | defer | may be useful only as a derived operator surface, not as semantic or parser infrastructure | do not add dependencies until an operator/gallery seam explicitly requires them |
| Gematria or deterministic numeric annotations | defer hard | at most optional metadata; not justified as a core meaning layer | require one narrow benchmarked use case before reopening |
| QRNG, qutrit, or other quantum semantics in core symbolic paths | reject for current lane | adds complexity without strengthening deterministic governed meaning | keep out of compiler, memory, and audit contracts |
| Claims about cognition rewrite, non-linear time perception, or already-built symbolic subsystems without repo proof | reject | violates current-truth discipline and creates claim drift | demand file-level evidence before planning any follow-on work |

### Working Rule

- [ ] Do not start a recovery implementation slice unless the corresponding recovery spec exists
- [ ] Do not mark a pillar complete until code, tests, docs, and operator proof surfaces are all updated together
- [ ] Do not reduce scope by replacing a constitutive source surface with a thinner packaged substitute without recording the justification in bridge docs
- [ ] Do not foreground monetization in public repo surfaces during the reconstruction phase; keep sustainability details mostly private until there is real beta/control-group evidence, with at most a small non-intrusive support link when the operator decides it is appropriate

## Phase R: Reconstruction Discipline

### Priority: ABSOLUTE - No more simplified stand-ins, pseudo-equivalents, or MVP-first substitutions

### Source-of-truth recovery

- [ ] Recover every omitted or downgraded HLF pillar from `Sovereign_Agentic_OS_with_HLF`, NotebookLM planning exports, and surviving repo doctrine docs before approving further simplification
- [ ] Build a rejection audit for every source surface previously marked `missing`, `optional`, `process-only`, `OS-bound`, or `superseded` that may actually carry constitutive HLF doctrine, routing, verification, governance, persona, or ecosystem logic
- [ ] Reclassify every damaged area as exactly one of: strong but misaligned, strong but not yet packaged, wrongly replaced, wrongly deleted

### Reconstruction rules

- [ ] Ban pseudo-equivalents during reconstruction: no fake stand-ins, no simplified replacements, no "good enough" packaged-core substitute for stronger original architecture
- [ ] Ban "standalone packaged core" as the deciding heuristic when doctrine, routing, personas, verification, governance workflow, or ecosystem coordination are architecturally constitutive
- [ ] Require every forward design move to show lineage back to original HLF intent rather than just local MVP convenience

### Sprint tracking for the real end zone

- [ ] Define the final reconstruction sprint stack around original HLF pillars instead of server/package neatness
- [ ] Track which pillars are already present in damaged or partial form versus which require true recovery from source
- [ ] Refuse any new cleanup, consolidation, or rewrite that reduces architectural scope unless the reduction is explicitly proven faithful to original intent

---

## Phase 0: HLF Knowledge Substrate Refactor

### Priority: CRITICAL - Weekly knowledge work should not proceed without a cohesive surface

### Naming and authority

### Package and module boundaries

### Normalization and Recovery Tasks

- [ ] Preserve the HLF-native knowledge-substrate / Infinite-RAG / governed-memory line as a named constitutive recovery surface in pillar, batch, and backlog docs
- [ ] Consolidate canonical front-door files:
  - `hlf/infinite_rag_hlf.py`
  - `hlf_mcp/rag/memory.py`
  - `scripts/run_pipeline_scheduled.py`
  - `hlf_mcp/weekly_artifacts.py`
  - `governance/host_functions.json`
  - `governance/bytecode_spec.yaml`
- [ ] Create and maintain `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` for normalization, explicit ownership boundary, and recovery plan
- [ ] Map subsystem boundaries and contracts
- [ ] Identify fragmentation, gaps, and normalization targets
- [ ] Define governance, provenance, and audit requirements
- [ ] Track progress in `docs/HLF_MISSING_PILLARS.md` and `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- [ ] Validate subsystem exceeds AgentKB/AgentSKB capabilities (unbranded)
- [ ] Ensure anti-reductionist doctrine: no simplification by omission
- [ ] Update actionable plan and bridge implementation steps

---

### Runtime contracts

- [ ] Standardize the MCP retrieval contract for chunk text, provenance, confidence, freshness, trust tier, and rationale
- [ ] Standardize naming for memory search, memory store, exemplar recall, and weekly ingest tools
- [ ] Add migration notes for any compatibility shims required during refactor

### Workflow alignment

- [ ] Add the knowledge-substrate refactor checklist to the weekly automation planning work
- [ ] Ensure workflow labels, docs, and tests are updated in lockstep with naming and schema changes
- [ ] Add an explicit weekly automation inventory to the active backlog covering: model drift (Sunday 00:00 UTC), spec sentinel (Sunday 02:00 UTC), upstream sync/compliance (Sunday 03:00 UTC), code quality (Monday 00:00 UTC), evolution planner (Monday 03:00 UTC), ethics review (Tuesday 02:00 UTC), doc/security review (Wednesday 02:00 UTC), test health (Thursday 02:00 UTC), and live Ollama canary (Thursday 06:00 UTC)
- [ ] Record for each weekly workflow its trigger, required secrets, output artifact, issue labels, and source-of-truth script so weekly knowledge gathering is auditable instead of inferred from YAML comments
- [ ] Add a local scheduled-run inventory covering `python run_tests.py`, `python -m hlf_mcp.test_runner`, `python scripts/run_pipeline_scheduled.py`, and `_toolkit.py` launcher flows, with clear guidance on what is manual versus actually scheduled
- [ ] Define branch/PR isolation rules so weekly stored knowledge never mixes `main`, `integrate-sovereign`, local-only, and archived `hlf_source/` observations into one truth stream
- [ ] Add freshness/expiry policy for stored weekly coding knowledge so stale benchmark, drift, and ethics findings decay or require explicit reconfirmation
- [ ] Require weekly jobs to persist raw evidence alongside summaries: commit SHA, workflow run URL, script version, test counts, coverage summary, governance manifest hash, and generated tool/resource counts
- [ ] Add a second-pass deterministic verifier for weekly knowledge artifacts so machine-extracted counts and hashes are rechecked before any issue or summary is stored

---

## Phase 0.5: README North-Star Claims To Operationalize

### Priority: CRITICAL - Keep ambitious README positioning, but convert each strong claim into measurable implementation work

### Product thesis and framing

- [ ] Define one sharply scoped usefulness thesis that justifies HLF beyond general architectural elegance
- [ ] Document the boundary between README north-star language, SSOT truth, and quality-target claims
- [ ] Add a stable cross-reference so README claims map to tracked implementation or validation work

### Deterministic orchestration evidence

- [ ] Add explicit replay-determinism validation for representative single-agent and multi-step workflows
- [ ] Add measurable execution-audit outputs for bytecode hash, gas usage, and side-effect trace completeness
- [ ] Add a benchmark/reporting surface that compares governed HLF execution against NLP-only baselines on repeatability and drift

### Policy-first and compliance-oriented deployment

- [ ] Define a compliance-oriented deployment profile instead of implying present-tense compliance readiness
- [ ] Produce a governance control matrix mapping manifest assets, align rules, and audit outputs to concrete operational controls
- [ ] Add validation tasks for policy trace completeness, PII handling coverage, and fail-closed enforcement behavior

### Capsule and privilege model hardening

- [ ] Define a more explicit capsule privilege-escalation and host-function mediation story for hearth, forge, and sovereign tiers
- [ ] Add tests for capsule boundary enforcement and privileged-host-function denial paths
- [ ] Document what capsule isolation means today versus what stronger sandbox guarantees remain target-state work

### Memory and retrieval claims

- [ ] Promote advisory memory hooks into a first-class measured retrieval surface with stable contracts for provenance, confidence, and freshness
- [ ] Evaluate external vector-store integration targets only after the packaged advisory memory contract is finalized
- [ ] Add tests and docs for deterministic use of retrieved context as governed execution inputs

### Tool contract and agent substrate quality

- [ ] Define typed host-function contract gates for inputs, outputs, effects, and structured failures
- [ ] Add a proof surface for "auditable agent substrate" claims using packaged test-suite summaries, runtime traces, and governance checks
- [ ] Add a docs-sync task so tool/resource counts and high-level server claims can be regenerated or checked automatically
- [ ] Add a knowledge-sync task so weekly issue bodies and stored research summaries are generated from machine-readable artifacts first and LLM interpretation second
- [ ] Add a provenance schema for weekly knowledge entries: source class, source path, line or artifact ID, branch, commit SHA, collected_at, collector version, confidence, and supersedes pointer

---

## Phase 0.6: Governed Autonomous Evolution Bridge

### Priority: HIGH - Make self-improvement auditable, bounded, and real before expanding the claim surface

### Evolution loop contract

- [ ] Publish the canonical bridge loop as `observe -> propose -> verify -> promote`
- [ ] Map each loop stage to existing repo surfaces: weekly workflows, lifecycle guards, verifier outputs, memory/provenance work, and operator review
- [ ] Add one operator-facing note that distinguishes current autonomous-evolution reality from target-state vision

### Evidence substrate

- [ ] Normalize weekly evidence records so every stored finding includes branch, commit SHA, workflow run URL, script version, manifest hash, collected time, and confidence
- [ ] Add supersession, expiry, and branch-isolation rules so automation cannot silently pollute long-lived truth across branches
- [ ] Add a deterministic second-pass verifier before weekly findings can create issues, update planning artifacts, or enter longer-lived memory

### Proposal generation and promotion

- [ ] Define a bounded proposal schema: source evidence, target files, intended gain, risk class, required tests, and governance-review requirement
- [ ] Connect friction logging and self-observe surfaces to proposal generation without granting autonomous merge authority
- [ ] Classify proposal types into docs sync, benchmark refresh, schema normalization, test augmentation, and runtime change requiring stronger review
- [ ] Bind all promoted proposals to explicit `VERIFY -> MERGE` evidence, including test status, trace completeness, and control-matrix checks

### Benchmark discipline

- [ ] Define benchmark tracks for cycle time, defect escape, audit completeness, replayability, and operator handoff speed
- [ ] Require benchmark artifacts before claiming orders-of-magnitude delivery or reliability gains in public-facing docs
- [ ] Add one governed-HLF-versus-NLP-only comparison lane for a representative workflow family

---

## Phase 0.7: Symbolic and Semasiographic Surface Research

### Priority: HIGH - Research this lane explicitly before it mutates grammar, translation, or operator surfaces

### Canonical authority boundary

- [x] Keep canonical semantics in AST, IR, bytecode, and governance contracts
- [x] Keep ASCII as the baseline keyboard-safe authoring surface
- [x] Treat Unicode symbolic projection and rendered glyph surfaces as secondary governed projections only

### Dedicated research pass

- [x] Run a dedicated action-research pass for semasiographic notation theory, symbolic surface analogues, and practical compiler constraints
- [x] Define non-linear intent-object structures and relation operators for time, cause, dependency, and agent roles in machine-checkable terms
- [x] Record which ideas belong to doctrine, which belong to bridge implementation, and which are speculative and must stay out of current-truth claims

### Projection and trust rules

- [x] Define exact round-trip rules for `ASCII -> canonical structure -> symbolic projection -> explanation`
- [x] Add audit and translation requirements proving symbolic projections cannot drift from canonical meaning
- [x] Define benchmark lanes for compression with fidelity, parse determinism, and operator legibility before promotion
- [ ] Add the first regression tests for relation-edge round-trip and explanation fidelity
- [ ] Require external symbolic research intake to include repo file targets, exact claim lane (`current-truth`, `bridge`, or `vision`), deterministic test proposals, and dependency cost before it can enter backlog promotion

---

## Phase 1: Core MCP Layer

### Priority: CRITICAL - Everything else depends on this

### mcp_resources.py

- [ ] Create `hlf/mcp_resources.py`
- [ ] Implement `HLFResourceProvider` class
- [ ] Implement `list_resources()` - grammar, bytecode, dictionaries, version, ast-schema
- [ ] Implement `list_resource_templates()` - programs/{name}, profiles/{tier}
- [ ] Implement `read_resource(uri)` - fetch content for each resource
- [ ] Implement `subscribe_resource()` - file watcher for changes
- [ ] Implement `_generate_dictionaries()` - extract from grammar + programs

### mcp_tools.py

- [ ] Create `hlf/mcp_tools.py`
- [ ] Implement `HLFToolProvider` class
- [ ] Implement tool: `hlf_compile` - source → bytecode
- [ ] Implement tool: `hlf_execute` - bytecode → result
- [ ] Implement tool: `hlf_validate` - syntax/effect/gas validation
- [ ] Implement tool: `hlf_friction_log` - log friction events
- [ ] Implement tool: `hlf_self_observe` - meta-intent emission
- [ ] Implement tool: `hlf_get_version` - version/checksum
- [ ] Implement tool: `hlf_compose` - combine programs
- [ ] Implement tool: `hlf_decompose` - split program into components

### mcp_prompts.py

- [ ] Create `hlf/mcp_prompts.py`
- [ ] Implement `HLFPromptProvider` class
- [ ] Implement prompt: `hlf_initialize_agent` - full grammar injection
- [ ] Implement prompt: `hlf_express_intent` - natural language → HLF
- [ ] Implement prompt: `hlf_troubleshoot` - diagnosis template
- [ ] Implement prompt: `hlf_propose_extension` - friction → proposal
- [ ] Implement prompt: `hlf_compose_agents` - multi-agent composition

### mcp_server_complete.py

- [ ] Create `hlf/mcp_server_complete.py`
- [ ] Implement `MCPServer` class with full protocol support
- [ ] Wire all resources, tools, prompts
- [ ] Implement stdio transport (MCP standard)
- [ ] Implement HTTP transport (FastAPI alternative)
- [ ] Add health endpoint
- [ ] Add logging support

### mcp_client.py

- [ ] Create `hlf/mcp_client.py`
- [ ] Implement `HLFMCPClient` class
- [ ] Implement `get_version()` with caching
- [ ] Implement `get_grammar()` with caching
- [ ] Implement `get_dictionaries()` with caching
- [ ] Implement `get_init_prompt()` - tier/profile/focus params
- [ ] Implement `compile()` - remote compilation
- [ ] Implement `execute()` - remote execution
- [ ] Implement `validate()` - remote validation
- [ ] Implement `friction_log()` - report friction
- [ ] Implement `get_system_prompt()` - full injection vector
- [ ] Implement `check_version_change()` - poll for updates

---

## Phase 2: Dictionary Generator

### Priority: HIGH - Required before MCP can serve dictionaries

### gen_dictionary.py

- [ ] Create `scripts/gen_dictionary.py`
- [ ] Parse `hlf/spec/core/grammar.yaml` for glyph mappings
- [ ] Parse `hlf/spec/vm/bytecode_spec.yaml` for opcode catalog
- [ ] Parse `examples/*.hlf` for pattern examples
- [ ] Generate `glyph_to_ascii` dictionary
- [ ] Generate `ascii_to_glyph` dictionary
- [ ] Generate `opcode_catalog` with gas/effects
- [ ] Generate `effect_index` from grammar
- [ ] Generate `pattern_examples` from programs
- [ ] Add metadata: version, generated_at, grammar_sha256
- [ ] Write to `mcp_resources/dictionaries.json`

### CI Integration

- [ ] Add job to `.github/workflows/ci.yml`: `generate-dictionaries`
- [ ] Run after `grammar-tests` job
- [ ] Copy `hlf/spec/core/grammar.yaml` → `mcp_resources/grammar.md`
- [ ] Upload `mcp_resources/` as artifact

---

## Phase 3: Friction Pipeline

### Priority: MEDIUM - Required for self-evolution

### forge_agent.py

- [ ] Create `hlf/forge_agent.py`
- [ ] Implement `FrictionReport` dataclass
- [ ] Implement `GrammarProposal` dataclass
- [ ] Implement `ForgeAgent` class
- [ ] Implement `run()` - main poll loop
- [ ] Implement `_parse_friction()` - parse .hlf files
- [ ] Implement `_validate_friction()` - run hlfc/hlflint
- [ ] Implement `_craft_proposal()` - generate extension
- [ ] Implement `_submit_proposal()` - call MCP endpoint
- [ ] Implement `_get_validation_token()` - fetch CI token
- [ ] Add CLI entry point: `forge_main()`

### Host Function Integration

- [ ] Wire `FRICTION_LOG` in `hlf/host_functions_minimal.py`
- [ ] Write to `~/.sovereign/friction/{id}.hlf`
- [ ] Include grammar_sha256 and metadata

### Directory Structure

- [ ] Create `~/.sovereign/friction/` on first run
- [ ] Create `~/.sovereign/friction/processed/`
- [ ] Create `~/.sovereign/grammar/history/`
- [ ] Create `~/.sovereign/cache/bytecode/`

---

## Phase 4: CI Integration

### Priority: HIGH - Required for trust chain

### generate_token.py

- [ ] Create `scripts/generate_token.py`
- [ ] Implement `generate_token(ci_run_id, grammar_sha)` - HMAC signature
- [ ] Implement `validate_token(token)` - verify CI origin
- [ ] Add expiry checking (1 hour TTL)
- [ ] Add CLI for manual token generation

### CI Workflow Updates

- [ ] Add `generate-dictionaries` job to `.github/workflows/ci.yml`
- [ ] Add `generate-validation-token` job
- [ ] Require `CI_HMAC_SECRET` in repository secrets
- [ ] Upload validation token as artifact
- [ ] Pass token to MCP server deployment

---

## Phase 5: Docker

**Priority: MEDIUM - Required for deployment**

### Dockerfile.mcp
- [ ] Create `Dockerfile.mcp`
- [ ] Base on `python:3.12-slim`
- [ ] Install `uv` for dependency management
- [ ] Copy `hlf/`, `examples/`, `scripts/`
- [ ] Create `/root/.sovereign/friction/`
- [ ] Expose port 8000
- [ ] Add health check
- [ ] Set `MCP_HMAC_KEY` env var

### Dockerfile.forge
- [ ] Create `Dockerfile.forge`
- [ ] Base on `python:3.12-slim`
- [ ] Install `git` for PR creation
- [ ] Copy `hlf/`, `scripts/`
- [ ] Run `hlf.forge_agent`

### docker-compose.yml Updates
- [ ] Add `mcp-server` service
- [ ] Add `forge-agent` service (optional profile)
- [ ] Mount `./data/friction:/root/.sovereign/friction`
- [ ] Mount `./mcp_resources:/app/mcp_resources:ro`
- [ ] Configure `MCP_HMAC_KEY` from env
- [ ] Configure `GITHUB_TOKEN` from env
- [ ] Add health checks
- [ ] Create `sovereign-net` network

---

## Phase 6: Documentation

**Priority: LOW - Required for adoption**

### MCP_INTEGRATION.md
- [ ] Create `docs/MCP_INTEGRATION.md`
- [ ] Document all resource URIs
- [ ] Document all tool signatures
- [ ] Document all prompt templates
- [ ] Include code examples for each endpoint
- [ ] Include error handling examples
- [ ] Include caching recommendations

### FORGE_AGENT.md
- [ ] Create `docs/FORGE_AGENT.md`
- [ ] Document Forge agent architecture
- [ ] Document friction report format
- [ ] Document proposal lifecycle
- [ ] Document CI token validation
- [ ] Include troubleshooting guide

### README Updates
- [ ] Update `HLF_README.md` with MCP section
- [ ] Add quick start for MCP client
- [ ] Add quick start for Forge agent
- [ ] Link to full documentation

---

## Optional: Agent Integration for Existing Systems

**The MCP layer is designed to be agent-agnostic. Systems with existing agents can integrate without using the Forge/Sovereign agent architecture:**

### For Claude/GPT-4/etc. (via MCP Client)
- [ ] Use `mcp_client.get_system_prompt()` to inject grammar
- [ ] Use `mcp_client.compile()` to compile HLF source
- [ ] Use `mcp_client.execute()` to run bytecode
- [ ] Use `mcp_client.friction_log()` to report issues
- [ ] Poll `mcp_client.check_version_change()` for updates

### For Custom Agents (via HTTP API)
- [ ] GET `/resource/grammar` - fetch grammar
- [ ] GET `/resource/dictionaries` - fetch compression dicts
- [ ] POST `/tool/compile` - compile source
- [ ] POST `/tool/execute` - execute bytecode
- [ ] POST `/tool/friction_log` - report friction

### For MCP-Native Agents (via stdio)
- [ ] Implement MCP protocol handshake
- [ ] Call `resources/list` → get available resources
- [ ] Call `resources/read` → fetch grammar/dictionaries
- [ ] Call `tools/list` → get available tools
- [ ] Call `tools/call` → compile/execute/friction
- [ ] Call `prompts/list` → get prompt templates
- [ ] Call `prompts/get` → get initialization prompt

---

## Verification Checklist

After implementation, verify:

- [ ] `python -m hlf.mcp_server_complete --stdio` starts correctly
- [ ] `curl localhost:8000/resource/grammar` returns grammar
- [ ] `curl localhost:8000/resource/dictionaries` returns dictionaries
- [ ] `curl localhost:8000/resource/version` returns version info
- [ ] `POST /tool/compile` compiles HLF source
- [ ] `POST /tool/execute` executes bytecode
- [ ] `POST /tool/friction_log` creates friction file
- [ ] Forge agent processes friction files
- [ ] CI generates validation tokens
- [ ] Docker Compose starts all services
- [ ] MCP client can initialize from scratch

---

## Notes

- All file paths are relative to `C:/Users/gerry/generic_workspace/HLF_MCP/`
- Phase 1 is blocking - everything else depends on MCP layer
- Phase 2-4 can be parallelized
- Phase 5-6 can be done last
- The Forge agent is OPTIONAL for external systems