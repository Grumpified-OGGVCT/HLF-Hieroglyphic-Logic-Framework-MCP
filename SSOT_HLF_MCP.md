# Single Source of Truth - HLF-Hieroglyphic-Logic-Framework-MCP

**Generated on:** 2026-03-24
**Branch:** rescue/governed-review-recovery-2026-03-21
**Purpose:** Authoritative current-state document for this local checkout, grounded in code present in this branch plus targeted verification runs on 2026-03-20, 2026-03-21, and 2026-03-24, with explicit notes on extraction completeness relative to the Sovereign source repo.

## Truth Boundary

This document separates three classes of truth:

1. **Implemented now**: verifiable in this checkout and executable today.
2. **Partial now**: present as code or scaffolding, but not complete enough to claim as finished.
3. **Roadmap / vision**: valuable design direction, but not default present-tense product truth.

## Operator Workflow (Dogfooding)

The packaged HLF MCP server is now used for bounded, governed build-assist:

- Use `hlf_do`, `_toolkit.py status`, and `hlf_test_suite_summary` to inspect, test, and explain the system during further development.
- All operator-facing evidence, audit, and regression surfaces are real and queryable.
- The packaged `hlf_mcp` HTTP/SSE lane has been verified with `HLF_TRANSPORT=sse`, `HLF_PORT=8011`, and `GET /health -> 200 OK`.
- This workflow is not full self-hosting, but it is a real recursive build-assist loop: the system is used to help build and verify itself, with each new bridge slice (routing, verification, orchestration, etc.) added and then used to further assist the next round of work.

2026-03-21 verification addendum:

- `uv run pytest tests/ -q --tb=short` passed with `816 passed`
- workspace-local MCP wiring now targets `uv run hlf-mcp` rather than the legacy compatibility entrypoint

If a claim is not backed by files in this repo or a command run in this workspace on the verification dates named above, it does not belong in the "implemented now" section.

This document also now distinguishes between:

- **local checkout truth**: what is actually present and working in `HLF_MCP`
- **source extraction completeness**: how much of the HLF-related surface from `Sovereign_Agentic_OS_with_HLF` has or has not been carried over
- **semantic/refit authority**: doctrine, RFC, correction, and local-corpora evidence that does not automatically become present-tense product truth, but still defines what constitutive HLF pillars must eventually be restored, bridged, or explicitly scoped

Short boundary note:

- `README.md` contains north-star framing and aspirational product language.
- `TODO.md`, `HLF_MCP_TODO.md`, and `HLF_QUALITY_TARGETS.md` define the implementation and validation path required to earn those claims.
- `SSOT_HLF_MCP.md` is the present-tense truth surface and should not treat README ambition as already shipped reality.
- `docs/HLF_CLAIM_LANES.md` is the compact interpretation guide for classifying wording reused from README, bridge docs, assistant output, or external summaries.

Additional boundary rule:

- this file remains the authority for executable current truth
- it must not erase constitutive HLF pillars simply because they are only partially packaged today
- when external doctrine or local corpora preserve math, symbol, bytecode, trust-chain, evolution, verifier, or dual-surface HLF semantics, those belong in bridge and recovery planning rather than being silently treated as optional
- when current-truth statements are reused elsewhere, they should remain `current-true` under `docs/HLF_CLAIM_LANES.md` rather than being expanded into bridge or vision phrasing without proof

## Repo Identity

- Repository: HLF-Hieroglyphic-Logic-Framework-MCP
- Workspace path: `C:\Users\gerry\generic_workspace\HLF_MCP`
- Packaged product: `hlf-mcp`
- Packaged entry point: `hlf_mcp.server:main`
- Legacy MCP line still present: `hlf/` modules and `hlf.mcp_server_complete`
- Expected upstream source repo for HLF extraction/reference: `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF`

## Source Extraction Reality

The previous empty placeholder SSOT was trying to become a full extraction-and-refactor ledger. The current SSOT started as a **local truth document**, which means it correctly described what exists here, but it did **not** fully describe how much HLF-related work exists in the Sovereign source repo.

That distinction matters.

It matters even more after the three local external corpora were added to reconstruction work.

Those corpora do not override local executable truth, but they do prove that some HLF pillars are broader than the packaged runtime/compiler surface alone.

In particular, they preserve additional evidence for:

- mathematical-symbolic compression as a constitutive HLF foundation
- a dual-surface language model rather than one flattened syntax story
- bytecode, decompilation, and VM round-trip discipline as first-class HLF concerns
- cryptographic trust-chain semantics for packets, pointers, tools, registries, and traces
- governed language evolution, dialect control, and anti-de-evolution rules

Those areas therefore belong to the repo's semantic/refit authority even where the packaged code has not yet fully absorbed them.

Version rule:

- there is no separately authoritative `HLF 4.0` release established by the evidence set currently under reconstruction
- however, SAFE v4 and correction materials still preserve HLF-relevant bytecode, cryptographic, verifier, and compliance mechanics by substance
- those mechanics should be mined as HLF bridge obligations rather than discarded because of the label they appeared under

### What the Sovereign source repo contains

Direct inspection of `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF` shows a substantially broader HLF ecosystem, including:

- `hlf/` with 37 files
- `mcp/` with 2 files
- `governance/` with 24 files
- `hlf_programs/` with 13 files
- `tests/` with 108 files
- `scripts/` with 22 files

And the HLF-bearing surface is not limited to directories with `hlf` in their names. It also appears in cross-cutting source files such as:

- `agents/gateway/bus.py`, `agents/gateway/router.py`, and `agents/gateway/sentinel_gate.py`
- `agents/core/canary_agent.py` and `agents/core/formal_verifier.py`
- `config/agent_registry.json`, `config/jules_tasks.yaml`, and persona specs under `config/personas/`
- `scripts/generate_tm_grammar.py`, `scripts/gen_docs.py`, `scripts/hlf_token_lint.py`, and `scripts/run_hlf_gallery.py`
- `docs/cli-tools.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, `docs/HLF_REFERENCE.md`, and other HLF operator/reference assets

Notable HLF modules present there include:

- `hlfpm`, `hlflsp`, `hlfsh`, `hlftest`
- `infinite_rag`, `memory_node`, `similarity_gate`, `intent_capsule`
- `tool_dispatch`, `tool_installer`, `tool_lockfile`, `tool_monitor`, `tool_scaffold`
- `gardiner_taxonomy`, `error_corrector`, `oci_client`, `insaits`, `translator`
- `mcp/sovereign_mcp_server.py`

### What this extracted repo currently contains

Direct inspection of `HLF_MCP` shows:

- `hlf/` with 40 files
- `hlf_mcp/` with 40 files
- `governance/` with 7 files
- `fixtures/` with 12 files
- `tests/` with 26 files
- `scripts/` with 6 files
- `docs/` with 17 files

This means the repo is **not empty**, but it is also **not a complete extraction/refactor of all HLF-related material from the Sovereign source repo**.

### Correct interpretation

The earlier SSOT was too narrow if the intended mission was:

- enumerate all HLF-bearing files and systems from the Sovereign source repo
- identify which ones were extracted, renamed, merged, dropped, or still missing
- track refactor completeness across both repos

That scope includes:

- direct language/runtime/governance code
- HLF-aware gateway, MCP, and execution bridge code
- HLF-specific scripts, fixtures, and reference docs
- HLF doctrine embedded in config and persona definitions when it materially shapes the language/runtime boundary

It was accurate for local-checkout truth.
It was incomplete for source-to-extracted migration truth.

## Canonical Build Surface

The repo currently contains **one packaged/default implementation surface and one retained compatibility surface**.

### 1. Packaged FastMCP surface

This is the default build/install surface and the one exposed by `pyproject.toml`.

- Package: `hlf_mcp`
- Entry point: `hlf-mcp`
- Server file: `hlf_mcp/server.py`
- Core compiler/runtime path: `hlf_mcp/hlf/*`
- Current packaged MCP registration count verified in this checkout on 2026-03-20: **69 tools, 31 resources, 0 prompts**

### 2. Legacy MCP compatibility surface

This line is still real and testable, but it is not the package entry point, the default implementation surface, or the right basis for present-tense product claims.

- Package path: `hlf/*`
- Server file: `hlf/mcp_server_complete.py`
- Tool/provider stack: `hlf/mcp_tools.py`, `hlf/mcp_resources.py`, `hlf/mcp_prompts.py`
- Noteworthy capability: older `hlf_do` front door and legacy prompt/resource plumbing

### Current repo truth

The right way to describe the repo is **not** "only one server exists" and **not** "everything is one unified stack already".

The truthful statement is:

- the packaged production-facing surface is `hlf_mcp`
- the legacy `hlf/` line still contains useful, working compatibility components
- this pass merged one high-value capability (`hlf_do`) forward into the packaged FastMCP surface instead of pretending the split does not exist

### Branch-aware supplement for this checkout

This SSOT now also needs one explicit branch-aware clarification because `main` currently underrepresents the active branch.

- Active branch verified on 2026-03-20: `integrate/vscode-operator-governed-review`
- Divergence verified on 2026-03-20: **0 behind, 10 ahead** of `main`
- The local checkout therefore contains meaningful branch-resident surfaces that a public `main` review can still miss.

That does **not** mean every branch surface is current-product completion.

It means this local checkout truth is broader than public-main perception in at least four concrete ways:

- packaged operator-review normalization now exists in `hlf_mcp/governed_review.py`
- packaged weekly artifact decision and evidence-query surfaces now exist above `hlf_mcp/weekly_artifacts.py`
- packaged formal-verifier behavior is now real in `hlf_mcp/hlf/formal_verifier.py` rather than only a placeholder status resource
- packaged bridge slices for symbolic surfaces, dream-cycle/media evidence, multimodal contract resources, and the VS Code operator shell scaffold are present in this checkout even where they remain bridge-qualified rather than fully restored

## Implemented Now

The following claims are grounded in code present in this checkout.

### Compiler and language pipeline

- `hlf_mcp/hlf/compiler.py` implements a real multi-pass compiler.
- Implemented passes present in code: normalization, LALR parsing, immutable env collection, ethics hook, variable expansion, ALIGN validation, gas estimation, AST cache.
- `hlf_mcp/hlf/translator.py` implements English-to-HLF and HLF-to-English translation helpers.
- The packaged translation front door now exposes a first-class cognitive lane policy surface with benchmark-gated default handling, English-audit preference, and fail-closed Chinese-ingress disallow mode.
- `hlf_mcp/hlf/formatter.py` and `hlf_mcp/hlf/linter.py` provide canonical formatting and static analysis.
- The packaged CLI surface now also includes `hlfpm`, `hlfsh`, and `hlftest` entry points for package management, interactive authoring, and fixture/snippet validation.

### Runtime and execution

- `hlf_mcp/hlf/runtime.py` contains a real bytecode VM with gas metering, stack execution, trace capture, and side-effect tracking.
- `hlf_mcp/hlf/bytecode.py` provides bytecode encoding/decoding and opcode tables.
- `hlf_mcp/hlf/capsules.py` implements tiered execution capsules with gas ceilings and AST validation.

### FastMCP server

- `hlf_mcp/server.py` is the packaged FastMCP server.
- The human-facing FastMCP instruction payload is now built through `hlf_mcp/server_instructions.py`, using the actual registered tool and resource surface instead of a hand-maintained inline block in `server.py`.
- Implemented transports: `stdio`, `sse`, and `streamable-http`.
- Implemented health endpoint wrapper: `/health` for HTTP transports.
- Implemented resources: grammar, opcodes, host functions, examples, governance files, stdlib listing.

### Model backend selection and dependency boundary

- The packaged routing and model-catalog surface already distinguishes `local-via-ollama`, `cloud-via-ollama`, and `remote-direct` backend lanes.
- The packaged MCP server works without any locally tuned HLF-specialized model.
- Current operator guidance for planner, doer, coding, reasoning, and controller roles is cloud-first; admitted local lanes remain optional runtime choices rather than a build dependency.
- The future HLF-specialized local LoRA or QLoRA experiment remains `bridge-true` under `plan/feature-local-slm-tuning-1.md`; it is not current packaged truth and not required for MCP operation.

### Current recursive build-assist truth

- The packaged MCP surface is already viable for local, bounded build assistance.
- The first credible operator path for that story is `stdio`, plus packaged build-observation surfaces such as `hlf_do`, `hlf_test_suite_summary`, and `_toolkit.py status`.
- HTTP transport health checks are useful and implemented.
- However, remote `streamable-http` self-hosting is not yet current-truth ready if MCP `initialize` still fails end to end.

Claim-lane reminder:

- the bounded local build-assist lane is `current-true`
- stronger self-build or remote self-hosting language remains `bridge-true` until the proof gates are actually closed

Current truth rule:

- local bounded build assistance may be claimed now
- full remote `streamable-http` self-build may not be claimed until the initialize/smoke path is fixed and rerun successfully

### Memory and lifecycle

- `hlf_mcp/rag/memory.py` provides the repo's current packaged Infinite RAG memory subsystem.
- HLF Knowledge Substrate (HKS)-facing governed knowledge surfaces also exist above that subsystem through `hlf_mcp/server_memory.py`, `hlf_mcp/server_context.py`, and `hlf_mcp/weekly_artifacts.py`.
- Packaged HKS memory now materializes first-class persisted graph nodes rather than relying only on per-record graph metadata at query time.
- Packaged HKS retrieval now emits reusable `governed_hks_contract` payloads backed by lexical, sparse-semantic, metadata-filtered, and persisted graph-linked scoring paths.
- Benchmark artifacts and weekly artifact memory records now emit reusable HKS graph entities for prompt assets, code patterns, upgrade opportunities, and weekly evidence state.
- `hlf_mcp/instinct/lifecycle.py` provides the current Instinct lifecycle state machine surface.

### Governance artifacts

- Root governance files are present: `align_rules.json`, `bytecode_spec.yaml`, `host_functions.json`, `tag_i18n.yaml`, `module_import_rules.yaml`, and `MANIFEST.sha256`.
- Extracted governance support assets now also include `governance/templates/dictionary.json` for future LSP and tag-arity aware tooling.
- `hlf_mcp/server.py` checks the governance manifest at startup.
- This pass fixed a real hash drift in `governance/MANIFEST.sha256` for `tag_i18n.yaml`.

### Additional packaged surfaces verified in this checkout on 2026-03-20

- `hlf_mcp/hlf/formal_verifier.py` now provides a real packaged verifier path with structured proof-status reporting.
- `hlf_mcp/hlf/execution_admission.py` and capsule/runtime wiring now carry verifier results into execution admission and denial behavior.
- `hlf_mcp/server_profiles.py` and `hlf_mcp/hlf/routing_trace.py` now provide real packaged route-evidence, profile-capability, and fallback-trace surfaces.
- `hlf_mcp/governed_review.py` now provides normalized governed-review contracts for spec drift, test health, ethics review, code quality, doc accuracy, and security-pattern review.
- `hlf_mcp/evidence_query.py` and `hlf_mcp/weekly_artifacts.py` now provide operator-facing evidence listing, summary, and decision persistence over verified weekly artifacts.

### 2026-03-24 HKS bridge addendum

- route, repair, verifier, and execution-admission seams now consume admitted HKS governed-knowledge contracts directly rather than depending only on raw recall result lists
- capsule execution now denies elevated execution when the routed HKS contract is not admitted
- formal verifier admission now upgrades elevated requests to `knowledge_review_required` when governed verifier evidence is missing or inadmissible
- focused HKS bridge validation is green in `tests/test_hks_memory.py`, `tests/test_capsule_pointer_trust.py`, and `tests/test_fastmcp_frontdoor.py` (`149 passed`)
- adjacent evidence and weekly-governance validation is green in `tests/test_weekly_artifacts.py`, `tests/test_evidence_query.py`, `tests/test_workflow_support.py`, `tests/test_extracted_support_tools.py`, and `tests/test_witness_governance.py` (`31 passed`)

### Weekly drift harness current truth

- `scripts/monitor_model_drift.py` now runs the weekly semantic drift probes in a closed-book mode: schema enforcement remains on, but web search is disabled and streaming is turned off for stricter JSON stability.
- The weekly drift harness now normalizes fenced JSON and embedded JSON object responses before classification.
- The weekly drift harness now separates three failure classes from true semantic misses: `semantic_wrong_answer`, `protocol_shape_failure`, and `tool_call_behavior_failure`.
- Focused proof for this slice now exists in `tests/test_workflow_support.py`, including regression coverage for fenced-JSON normalization and outcome-class separation.

### Merged forward in this pass

The packaged FastMCP surface now also includes `hlf_do`, a plain-English front door that:

- accepts natural-language intent
- generates HLF source
- validates the generated program
- applies capsule checks for `hearth` / `forge` / `sovereign`
- optionally executes the result
- returns a human-readable audit and token/gas summary

This was previously only a legacy-surface capability.

### Additional extraction progress in this pass

- Four source example programs were extracted and adapted onto the packaged v3 fixture surface: `decision_matrix`, `file_io_demo`, `module_workflow`, and `system_health_check`.
- The repo now ships 11 example fixtures and validates that all shipped fixtures compile under the packaged compiler.
- Two additional source governance assets were extracted into the standalone repo: `module_import_rules.yaml` and `templates/dictionary.json`.
- Three useful support tools were extracted by refactor rather than by direct port: `scripts/generate_tm_grammar.py`, `scripts/gen_docs.py`, and `scripts/hlf_token_lint.py`.
- Those support tools were exercised in this repo and now materialize `syntaxes/hlf.tmLanguage.json`, `docs/HLF_TAG_REFERENCE.md`, `docs/HLF_STDLIB_REFERENCE.md`, and `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`.
- The standalone repo now also carries an extracted `hlflsp` language-server surface adapted to the packaged grammar, host-function registry, stdlib bindings, and dictionary assets.
- Two drifted upstream reference docs are now carried as packaged references: `docs/HLF_GRAMMAR_REFERENCE.md` and `docs/stdlib.md`.
- Dedicated packaged regression coverage now also exists for `translator` and `tool_dispatch`.
- Dedicated packaged regression coverage now also exists for the Python-backed stdlib surface.
- Dedicated packaged regression coverage now also exists for `hlfpm` and `oci_client`.
- Dedicated packaged regression coverage now also exists for the InsAIts decompiler surface.
- The OCI/package reference parser now correctly handles `name@version` refs and deeper registry/namespace paths, matching the packaged `hlfpm` usage story.
- A final selective extraction pass added packaged docs for the CLI surface, HLF runtime/language reference, and Instinct lifecycle reference.
- The standalone repo now also carries a lightweight `scripts/verify_chain.py` integrity helper adapted for packaged JSONL observability traces.
- The standalone repo now also carries `docs/gen_from_spec.py`, which generates `docs/HLF_HOST_FUNCTIONS_REFERENCE.md` from the packaged host-function registry, and that generated reference is now present in the repo.
- Focused regression coverage now also exists for the extracted chain-verifier and spec-doc generator helpers.
- The standalone repo now also carries a packaged `HLFCodeGenerator` builder API at `hlf_mcp/hlf/codegen.py` for programmatic v3 source generation.
- The source gallery README now has a packaged counterpart at `fixtures/README.md`.
- The packaged `scripts/gen_docs.py` pipeline now also generates the host-functions reference, so the extracted doc generator is wired into the normal docs refresh path rather than living as a one-off helper.

## Partial Now

These areas are real, but should not be overstated.

### Ethics governor

- `hlf_mcp/hlf/ethics/` exists and is wired into compilation.
- The compiler contains a real ethics hook and fail-closed behavior.
- However, repo QA documents and current code structure still indicate that parts of the constitutional / rogue-detection / governor logic remain incomplete or evolving.
- Truthful claim: **ethics enforcement exists as a meaningful integrated surface, but the overall ethical governor is not yet honest-to-call fully complete.**

### Dual-surface architecture

- The repo has not yet fully converged the `hlf/` and `hlf_mcp/` lines.
- Some legacy capabilities, tests, and docs still reference the older stack.
- Truthful claim: **the repo is partially unified, not fully unified.**

### Documentation coherence

- Before this pass, core docs still repeated stale counts like `22 tools, 7 resources`.
- Quick start material mixed the legacy entry path with the packaged story.
- The main packaged server assembly is now cleaner because the large inline instruction payload was extracted out of `server.py`, and the human-facing server summary is now generated from the registered MCP surface.
- This pass corrected the most visible drift, but the entire repo has not yet been exhaustively normalized.

### Branch-resident bridge slices present in this checkout

- `hlf_mcp/hlf/symbolic_surfaces.py` provides a real symbolic relation-edge extraction/projection/audit slice, but it remains bridge work rather than a fully restored symbolic-semantic system.
- `hlf_mcp/dream_cycle.py`, `hlf_mcp/media_evidence.py`, `hlf_mcp/server_context.py`, `hlf_mcp/server_memory.py`, and `hlf_mcp/server_resources.py` provide a bounded dream-cycle and media-evidence bridge slice, but that lane remains advisory and bridge-qualified rather than full autonomous-evolution completion.
- `hlf_mcp/server_profiles.py` and `governance/model_qualification_profiles.json` now expose multimodal host-function and qualification-contract surfaces, but multimodal remains a governed bridge lane rather than a complete packaged media stack.
- `extensions/hlf-vscode/` now contains a real operator-bridge scaffold for VS Code, but it remains a bridge scaffold rather than a current-truth claim of Marketplace-shipped extension completion.

### Embodied execution boundary

- `governance/host_functions.json` now includes a first embodied host-function family, and the packaged runtime/front-door surfaces recognize that contract through `hlf_mcp/hlf/embodied.py`, `hlf_mcp/server_capsule.py`, and `hlf_mcp/hlf/runtime.py`.
- Current proof in this checkout covers supervisory host-contract metadata, approval-required guarded actuation, missing-evidence denial, tier-gated runtime dispatch, and structured simulation-only runtime results.
- Truthful claim: **the embodied slice is supervisory and simulation-scoped, not a claim of production robotics execution.**
- Truthful claim: **embodied action envelopes are not yet threaded through deeper verifier-backed spatial or motion proof.**
- Truthful claim: **execution-admission, route, witness, and operator-resource integration for embodied actions is not yet complete beyond the current host-call and runtime slice.**

### Language evolution and bytecode trust bridge

- The repo now has real packaged compiler, runtime, bytecode, manifest, integrity, and InsAIts surfaces.
- The repo does not yet earn a full present-tense claim that governed language evolution, constitution-hash compatibility, signed registry/tool trust, pointer provenance, verifier-gated execution, and richer round-trip proof surfaces are complete in packaged authority.
- Truthful claim: packaged executable bytecode/runtime authority exists now; the broader evolution-and-trust contract remains an active bridge/reconstruction area rather than a finished subsystem.

Claim-lane reminder:

- packaged bytecode/runtime authority is `current-true`
- the fuller evolution-and-trust contract is `bridge-true`, not current product completion

## Roadmap and Vision

The following can be treated as serious design direction, but not as default present-tense shipped truth unless separately verified in code.

- HLF as a universal deterministic orchestration language across agent ecosystems
- larger sovereign / three-brain / ROMA / Darwin-style architecture narratives
- stronger multimodal, research, swarm, and planet-scale coordination claims
- any statement that presumes the full ethics governor, all strategic doctrine, and all surrounding platform layers are production-complete today

### Quality target clarification

The repo now also carries an explicit quality-target track in `HLF_QUALITY_TARGETS.md`.

That document should be interpreted as:

- a serious implementation-governing target surface
- not proof that those targets are already fully achieved

Truthful present-tense claim:

- the repo now defines a measurable path toward "cleaner than NLP-only swarms" outcomes
- it does not yet claim universal or perfect execution quality

These ideas are not invalid. They just belong in the roadmap / doctrine category unless tied to working code in this repo.

## Validation Run on 2026-03-17

The following validations were run in this workspace during this pass.

| Command | Result |
| --- | --- |
| `uv run python -c "import hlf_mcp.server; import hlf_mcp.hlf.compiler; import hlf_mcp.hlf.runtime; print('imports-ok')"` | Passed |
| `uv run pytest test_mcp_minimal.py -q` | Passed (`6 passed`) |
| `uv run pytest tests/test_hlf_dxtools.py tests/test_fastmcp_frontdoor.py -q` | Passed (`13 passed`) |
| `uv run pytest tests/test_hlf_dxtools.py tests/test_fastmcp_frontdoor.py tests/test_fixtures_catalog.py tests/test_governance_assets.py -q` | Passed (`16 passed`) |
| `uv run pytest tests/test_hlf_dxtools.py tests/test_fastmcp_frontdoor.py tests/test_fixtures_catalog.py tests/test_governance_assets.py tests/test_extracted_support_tools.py -q` | Passed (`20 passed`) |
| `uv run pytest tests/test_hlflsp.py -q --tb=short` | Passed (`12 passed`) |
| `uv run pytest tests/test_extracted_support_tools.py tests/test_hlflsp.py -q --tb=short` | Passed (`16 passed`) |
| `uv run pytest tests/test_translator.py tests/test_tool_dispatch.py -q --tb=short` | Passed (`11 passed`) |
| `uv run pytest tests/test_stdlib.py -q --tb=short` | Passed (`15 passed`) |
| `uv run pytest tests/test_hlfpm.py tests/test_oci_client.py -q --tb=short` | Passed (`12 passed`) |
| `uv run pytest tests/test_insaits.py -q --tb=short` | Passed (`6 passed`) |
| `uv run pytest tests/test_verify_chain.py tests/test_gen_from_spec.py -q --tb=short` | Passed (`4 passed`) |
| `uv run pytest tests/test_codegen.py -q --tb=short` | Passed (`2 passed`) |
| `uv run pytest tests/test_extracted_support_tools.py tests/test_hlflsp.py tests/test_translator.py tests/test_tool_dispatch.py tests/test_stdlib.py -q --tb=short` | Passed (`42 passed`) |
| `uv run pytest tests/test_extracted_support_tools.py tests/test_hlflsp.py tests/test_translator.py tests/test_tool_dispatch.py tests/test_stdlib.py tests/test_hlfpm.py tests/test_oci_client.py -q --tb=short` | Passed (`54 passed`) |
| `uv run pytest tests/test_extracted_support_tools.py tests/test_hlflsp.py tests/test_translator.py tests/test_tool_dispatch.py tests/test_stdlib.py tests/test_hlfpm.py tests/test_oci_client.py tests/test_insaits.py -q --tb=short` | Passed (`60 passed`) |
| `uv run python scripts/generate_tm_grammar.py` | Passed |
| `uv run python scripts/gen_docs.py` | Passed |
| `uv run python docs/gen_from_spec.py` | Passed |
| `uv run python scripts/hlf_token_lint.py fixtures` | Passed |
| `uv run pytest tests/test_extracted_support_tools.py tests/test_gen_from_spec.py -q --tb=short` | Passed (`6 passed`) |
| `uv run python -c "import hlf_mcp.server as s; print('imports-ok'); print('registered_tools', len(s.REGISTERED_TOOLS)); print('registered_resources', len(s.REGISTERED_RESOURCES)); print('exported_hlf_callables', len([name for name in dir(s) if name.startswith('hlf_') and callable(getattr(s, name))]))"` | Historical 2026-03-17 run passed (`imports-ok`, `34` registered tools, `9` registered resources, `34` exported callable `hlf_*` names) |
| `uv run pytest tests/test_fastmcp_frontdoor.py -q --tb=short` | Passed (`20 passed`) |
| `uv run pytest -q --tb=short` | Historical 2026-03-17 run passed (`513 passed`) |
| Generated packaged MCP surface in `hlf_mcp.server` | Historical 2026-03-17 value: `34` registered tools, `9` registered resources, `34` exported callable `hlf_*` names |

## Supplemental Verification On 2026-03-20

The following branch-aware facts were revalidated for this local checkout.

| Command | Result |
| --- | --- |
| `git branch --show-current` | Passed (`integrate/vscode-operator-governed-review`) |
| `git rev-list --left-right --count main...HEAD` | Passed (`0` behind, `10` ahead) |
| `uv run python -c "from hlf_mcp import server; print(len(server.REGISTERED_TOOLS), len(server.REGISTERED_RESOURCES))"` | Passed (`69` tools, `31` resources) after re-manifesting `governance/host_functions.json` |
| `uv run pytest -q --tb=short` | Passed (`758 passed`) |

## This Pass Changed

This SSOT corresponds to the following repo-level corrections made in the same pass:

- merged `hlf_do` into the packaged FastMCP server
- added packaged `hlfpm`, `hlfsh`, and `hlftest` CLI surfaces
- extracted four additional source example programs into packaged fixtures
- extracted `module_import_rules.yaml` and `templates/dictionary.json` into the standalone governance surface
- extracted and adapted TextMate grammar generation, packaged reference doc generation, and token-budget linting scripts
- extracted and adapted the `hlflsp` language server onto packaged compiler/linter/registry surfaces
- extracted and adapted packaged grammar and stdlib reference docs from the upstream drifted docs
- extracted dedicated packaged tests for the translator and tool dispatch surfaces
- extracted dedicated packaged tests for the Python-backed stdlib surface
- extracted dedicated packaged tests for `hlfpm` and `oci_client`
- extracted dedicated packaged tests for the InsAIts decompiler surface
- fixed OCI/package reference parsing so packaged `hlfpm` usage supports `name@version` and deeper OCI paths
- fixed governance manifest drift for `tag_i18n.yaml`
- removed pytest return-value warnings from `test_mcp_minimal.py`
- normalized legacy script-style pytest surfaces and aligned stale legacy MCP tests to current constructors and client APIs
- updated README and QA-facing docs to reflect the actual FastMCP surface counts
- updated `QUICKSTART.md` so the default quick-start path matches the packaged entry point
- wired the extracted host-functions reference generator into the main `scripts/gen_docs.py` pipeline and updated README links to point at packaged local references

## Merge Awareness State

Verified current branch facts:

- `integrate/vscode-operator-governed-review` is **10 commits ahead, 0 behind** `main`.
- The packaged surface count in this checkout is now **69 tools and 31 resources**.
- Public-main perception therefore still undercounts meaningful branch work.

Verified caution for merge/readiness interpretation:

- `governance/host_functions.json` drift was resolved in this pass by re-manifesting the tracked governance set through `scripts/gen_manifest.py`
- manifest discipline still matters: future tracked governance changes should refresh `governance/MANIFEST.sha256` in the same commit
- the repo-wide regression suite was rerun on 2026-03-20 and passed with `758 passed`

Recommended commit grouping if the branch is being tidied before push:

1. packaged HLF surface additions and source extraction (`hlf_mcp/*`, fixtures, scripts, governance assets)
2. packaged docs and truth docs (`README.md`, `QUICKSTART.md`, `docs/*`, `SSOT_HLF_MCP.md`, `HLF_SOURCE_EXTRACTION_LEDGER.md`)
3. regression-hardening and legacy test cleanup (`test_mcp*.py`, `tests/test_mcp_direct.py`, `hlf/mcp_metric.py`)

## Files of Record

Use these files first when deciding what is real.

- `pyproject.toml`
- `README.md`
- `QUICKSTART.md`
- `hlf_mcp/server.py`
- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/hlf/capsules.py`
- `hlf_mcp/rag/memory.py`
- `hlf_mcp/instinct/lifecycle.py`
- `governance/MANIFEST.sha256`
- `docs/QA_FINDINGS.md`
- `docs/QA_FINDINGS_HATS.md`

## Immediate Open Gaps

These are the most concrete remaining gaps after this pass.

1. The repo still lacks a single sharply defined usefulness thesis that makes the system clearly valuable on day one.
2. Decide whether the legacy `hlf/` surface will be kept, slimmed, or fully merged into `hlf_mcp/`.
3. Continue hardening the ethics governor from integrated scaffold to clearly complete subsystem.
4. Audit secondary docs for stale counts and legacy-path references beyond the core files updated here.
5. Keep the broader test surface green as consolidation continues.
6. Turn language-evolution, bytecode-trust, and semantic/refit obligations into explicit packaged bridge specs rather than leaving them distributed across source notes and recovery docs.

## Critical Product Gap

The most serious risk is not that nothing works.

The most serious risk is that the repo still does not present one sharply defined usefulness claim strong enough to justify the language, runtime, governance layer, and dual implementation history.

In plain terms:

- there is executable infrastructure
- there are meaningful protocol and governance ideas
- there is partial consolidation progress
- but there is still no single narrow user outcome that makes adoption feel obviously rational

Until that changes, the project remains vulnerable to becoming technically interesting but practically unnecessary.

## Extraction Gap

Separate from the product gap, there is also a **migration / extraction gap**.

This repo currently appears to be:

- a partial extraction
- a partial re-packaging
- a partial forward refactor

It is **not yet** a comprehensive, audited transplant of all HLF-related capability from `Sovereign_Agentic_OS_with_HLF`.

That missing work likely includes more than just extra files. It likely includes:

- tooling surfaces
- package-manager / shell / LSP / test-runner surfaces
- richer governance artifacts
- additional scripts and HLF programs
- broader MCP integration surfaces
- a larger test corpus and operational glue

## Bottom Line

HLF-MCP is not empty, not imaginary, and not just a speculative manifesto.

It already contains a substantive packaged compiler/runtime/server stack, a second legacy implementation line with useful pieces, and enough real code to justify serious continued consolidation.

The central truth problem was not lack of work. It was narrative drift between:

- what is implemented now
- what is partially implemented now
- what is still architectural vision

It also must now resist a fourth drift mode:

- treating constitutive HLF pillars preserved in source RFCs, correction notes, and local corpora as if they were non-HLF just because they are not yet fully packaged

And beneath that, the central product problem is still unresolved: there is not yet one sharply defined usefulness claim that the repo can defend without reaching for the larger vision.

And separately, the central migration problem is also unresolved: this repo does not yet document or complete the full extraction/refactor boundary between itself and `Sovereign_Agentic_OS_with_HLF`.

This document exists to keep those three categories separate.

For compact wording classification when exporting claims from this document into other surfaces, use `docs/HLF_CLAIM_LANES.md`.
