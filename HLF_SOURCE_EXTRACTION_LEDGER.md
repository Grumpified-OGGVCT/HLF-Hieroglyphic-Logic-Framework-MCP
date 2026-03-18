# HLF Source Extraction Ledger

**Generated:** 2026-03-16
**Source repo:** `C:\Users\gerry\generic_workspace\Sovereign_Agentic_OS_with_HLF`
**Target repo:** `C:\Users\gerry\generic_workspace\HLF_MCP`

## Classification Key

- `extracted`: carried over substantially as-is.
- `merged`: source capability absorbed into a broader target surface.
- `renamed`: carried over under a new path or name.
- `superseded`: source surface replaced by a newer canonical target surface.
- `missing`: no credible target equivalent exists yet.

## Batch Decisions

- **Batch 1 now**: `hlfsh`, `hlftest`, packaged CLI wiring for `hlfpm`.
- **Batch 2 executed**: additional example programs from `hlf_programs/` adapted to the packaged v3 grammar.
- **Later / optional**: `hlflsp` and selected reference docs after dependency and drift review.
- **Do not import wholesale**: Sovereign OS plugin-management, Janus worker plumbing, OpenClaw strategy files, and other OS-bound operational scaffolding.

## Scope Correction

This ledger must not be read as "only folders with `hlf` in the path count."

The Sovereign source repo contains substantial HLF-bearing surface outside `hlf/`, `hlf_programs/`, and similarly named directories. That broader surface includes:

- gateway and agent code that compiles, validates, routes, or executes HLF intents
- config and persona specs that define HLF governance, grammar evolution, and doc authority
- scripts that generate HLF grammars, benchmarks, docs, galleries, and repo lint output
- docs and generated assets that function as operator catalogs, quick starts, benchmarks, and visual explainers
- MCP bridge code that accepts raw HLF or text and forwards it into the larger Sovereign runtime

The classifications below are therefore split between:

- **canonical HLF core**: language/runtime/governance/example/test surfaces that directly belong in `HLF_MCP`
- **HLF-adjacent OS integration**: files that are clearly HLF-aware, but belong to the larger Sovereign operating environment rather than the standalone HLF product

## Folder Inventory

| Source path | Type | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- | --- |
| `hlf/` | folder | renamed | split across `hlf/` and `hlf_mcp/hlf/` | yes |
| `hlf/modules/` | folder | missing | source-only module sandbox docs | no |
| `hlf/stdlib/` | folder | renamed | `hlf_mcp/hlf/stdlib/` | yes |
| `mcp/` | folder | superseded | `hlf_mcp/server.py` is canonical MCP product surface | partial |
| `governance/` | folder | merged | canonical governance kept at repo root | yes |
| `governance/templates/` | folder | merged | some content belongs, some is stale or OS-specific | partial |
| `hlf_programs/` | folder | merged | target `fixtures/` is the standalone example surface | yes |
| `hlf_programs/reports/` | folder | missing | derived markdown reports, not runtime-critical | no |
| `scripts/` | folder | merged | only HLF-core scripts should come over | partial |
| `scripts/build/` | folder | superseded | parser is now embedded in packaged grammar/compiler | no |
| `docs/` | folder | merged | reference docs belong selectively, not wholesale | partial |

## `hlf/` File Inventory

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `hlf/__init__.py` | extracted | `hlf_mcp/hlf/__init__.py` | yes |
| `hlf/_parser_cache.py` | merged | `_AST_CACHE` inside `hlf_mcp/hlf/compiler.py` | yes |
| `hlf/bytecode.py` | extracted | `hlf_mcp/hlf/bytecode.py` | yes |
| `hlf/codegen.py` | extracted | adapted as `hlf_mcp/hlf/codegen.py` for parser-compatible packaged v3 source generation | yes |
| `hlf/error_corrector.py` | missing | no packaged structured autocorrect surface yet | maybe |
| `hlf/gardiner_taxonomy.py` | missing | academic taxonomy layer not required for standalone core | no |
| `hlf/hlb_format.py` | merged | binary format folded into `hlf_mcp/hlf/bytecode.py` | yes |
| `hlf/hlfc.py` | renamed | `hlf_mcp/hlf/compiler.py` | yes |
| `hlf/hlffmt.py` | renamed | `hlf_mcp/hlf/formatter.py` | yes |
| `hlf/hlflint.py` | renamed | `hlf_mcp/hlf/linter.py` | yes |
| `hlf/hlflsp.py` | extracted | adapted as `hlf_mcp/hlf/hlflsp.py` against packaged grammar/registry/dictionary surfaces | yes |
| `hlf/hlfpm.py` | extracted | `hlf_mcp/hlf/hlfpm.py` | yes |
| `hlf/hlfrun.py` | merged | CLI lives in `hlf_mcp/hlf/runtime.py` | yes |
| `hlf/hlfsh.py` | extracted | adapted in Batch 1 as `hlf_mcp/hlf/hlfsh.py` | yes |
| `hlf/hlftest.py` | extracted | adapted in Batch 1 as `hlf_mcp/hlf/hlftest.py` | yes |
| `hlf/infinite_rag.py` | renamed | `hlf_mcp/rag/memory.py` plus `hlf_mcp/hlf/memory_node.py` | yes |
| `hlf/insaits.py` | extracted | `hlf_mcp/hlf/insaits.py` | yes |
| `hlf/intent_capsule.py` | renamed | `hlf_mcp/hlf/capsules.py` | yes |
| `hlf/memory_node.py` | extracted | `hlf_mcp/hlf/memory_node.py` | yes |
| `hlf/oci_client.py` | extracted | `hlf_mcp/hlf/oci_client.py` | yes |
| `hlf/runtime.py` | renamed | `hlf_mcp/hlf/runtime.py` | yes |
| `hlf/similarity_gate.py` | missing | semantic round-trip guard not yet packaged | maybe |
| `hlf/tool_dispatch.py` | extracted | `hlf_mcp/hlf/tool_dispatch.py` | yes |
| `hlf/tool_installer.py` | missing | Sovereign OS plugin lifecycle, not standalone HLF-core | no |
| `hlf/tool_lockfile.py` | missing | tied to installer ecosystem, not current standalone product | no |
| `hlf/tool_monitor.py` | missing | tied to installer ecosystem, not current standalone product | no |
| `hlf/tool_scaffold.py` | missing | tied to installer ecosystem, not current standalone product | no |
| `hlf/translator.py` | extracted | `hlf_mcp/hlf/translator.py` | yes |

## `hlf/modules/`

| Source path | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `hlf/modules/README.md` | missing | module authoring doc not yet extracted | maybe |

## `hlf/stdlib/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `hlf/stdlib/agent.hlf` | renamed | `hlf_mcp/hlf/stdlib/agent.py` | yes |
| `hlf/stdlib/collections.hlf` | renamed | `hlf_mcp/hlf/stdlib/collections_mod.py` | yes |
| `hlf/stdlib/crypto.hlf` | renamed | `hlf_mcp/hlf/stdlib/crypto_mod.py` | yes |
| `hlf/stdlib/io.hlf` | renamed | `hlf_mcp/hlf/stdlib/io_mod.py` | yes |
| `hlf/stdlib/math.hlf` | renamed | `hlf_mcp/hlf/stdlib/math_mod.py` | yes |
| `hlf/stdlib/net.hlf` | renamed | `hlf_mcp/hlf/stdlib/net_mod.py` | yes |
| `hlf/stdlib/string.hlf` | renamed | `hlf_mcp/hlf/stdlib/string_mod.py` | yes |
| `hlf/stdlib/system.hlf` | renamed | `hlf_mcp/hlf/stdlib/system_mod.py` | yes |

## `mcp/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `mcp/janus_worker.py` | missing | Janus pipeline worker, upstream OS integration | no |
| `mcp/sovereign_mcp_server.py` | superseded | replaced by packaged `hlf_mcp/server.py` and legacy `hlf/mcp_server_complete.py` | no |

## Cross-Cutting HLF-Bearing Surfaces

These files are important because they prove the HLF surface extends well beyond folders named `hlf*`.

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `agents/gateway/bus.py` | missing | full Sovereign intent gateway; HLF-aware but OS-bound | no |
| `agents/gateway/router.py` | missing | routes HLF/text intents across model tiers; upstream orchestration | no |
| `agents/gateway/sentinel_gate.py` | missing | ALIGN gate for gateway traffic; tied to Sovereign bus | no |
| `agents/core/canary_agent.py` | missing | embeds probe HLF for runtime health checks; operational, not language-core | no |
| `agents/core/formal_verifier.py` | missing | HLF AST constraint verifier is language-relevant and worth later review | maybe |
| `agents/core/build_agent.py` | merged | references `module_import_rules.yaml`; standalone asset now extracted | partial |
| `config/agent_registry.json` | missing | many HLF governance and persona responsibilities; OS persona system | no |
| `config/jules_tasks.yaml` | missing | HLF evolution workflow definitions; upstream planning/orchestration | no |
| `config/personas/*.md` | missing | HLF doctrine and governance roles; useful source material, not product runtime | maybe |
| `scripts/generate_tm_grammar.py` | extracted | adapted as packaged TextMate grammar generation against `hlf_mcp/hlf/grammar.py` | yes |
| `scripts/gen_docs.py` | extracted | adapted as packaged doc generation for tag, stdlib, and host-function references | yes |
| `scripts/hlf_benchmark.py` | merged | benchmark logic already represented in packaged surface/docs | yes |
| `scripts/hlf_token_lint.py` | extracted | adapted as packaged token-budget linting for HLF corpora | yes |
| `scripts/run_hlf_gallery.py` | missing | example gallery compiler/report tool; useful but optional | maybe |
| `docs/cli-tools.md` | extracted | adapted to the packaged nine-command CLI surface defined in `pyproject.toml` and current argparse behavior | yes |
| `docs/HLF_GRAMMAR_REFERENCE.md` | extracted | adapted as packaged grammar/operator reference grounded in parser and dictionary truth | yes |
| `docs/HLF_REFERENCE.md` | extracted | adapted as a packaged repo-level HLF reference grounded in current compiler/runtime/tooling truth | yes |
| `docs/stdlib.md` | extracted | adapted as packaged stdlib guide aligned to Python-backed stdlib bindings | yes |
| `docs/benchmark.json` | missing | generated benchmark artifact, not canonical source | no |
| `docs/hlf_execution_storyboard.svg` | missing | explainer asset, optional for standalone repo | maybe |
| `tests/fixtures/*.hlf` | merged | source test fixtures partly adapted into target `fixtures/` and test corpus | yes |

## `governance/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `governance/adr.py` | missing | architecture decision helper, not runtime-critical | no |
| `governance/align_ledger.py` | missing | source parser/helper for YAML ledger | maybe |
| `governance/ALIGN_LEDGER.yaml` | superseded | target uses `governance/align_rules.json` + ethics modules | no |
| `governance/als_schema.py` | missing | OS logging schema, outside standalone MVP | no |
| `governance/bytecode_spec.yaml` | extracted | `governance/bytecode_spec.yaml` | yes |
| `governance/cove_audit_results.md` | missing | generated review artifact | no |
| `governance/cove_ci_lite.md` | missing | process doc, not product surface | no |
| `governance/cove_qa_prompt.md` | missing | process prompt, not product surface | no |
| `governance/dapr_grpc.proto` | missing | Dapr bus integration, not standalone HLF-core | no |
| `governance/hls.yaml` | superseded | drift-prone grammar descriptor replaced by `hlf_mcp/hlf/grammar.py` | no |
| `governance/host_functions.json` | extracted | `governance/host_functions.json` | yes |
| `governance/kya_init.sh` | missing | OS bootstrap script | no |
| `governance/module_import_rules.yaml` | extracted | carried into the standalone governance surface in Batch 3 | yes |
| `governance/openclaw_strategies.yaml` | missing | OpenClaw-specific orchestration, upstream-only | no |
| `governance/peer_review.md` | missing | process doc, not product surface | no |
| `governance/service_contracts.yaml` | missing | service-bus contracts, mostly OS-level | no |
| `governance/soft_veto.py` | missing | governance workflow helper, not current standalone product | no |

## `governance/templates/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `governance/templates/cove_compact_validation.md` | missing | generated/process review template | no |
| `governance/templates/cove_full_validation.md` | missing | generated/process review template | no |
| `governance/templates/cove_mega_validation.md` | missing | generated/process review template | no |
| `governance/templates/dictionary.json` | extracted | carried into the standalone governance surface in Batch 3 | yes |
| `governance/templates/eleven_hats_review.md` | missing | upstream process template | no |
| `governance/templates/fourteen_hat_review.md` | missing | upstream process template | no |
| `governance/templates/system_prompt.txt` | missing | OS prompt asset, not HLF-core product surface | no |

## `hlf_programs/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `hlf_programs/README.md` | extracted | adapted as `fixtures/README.md` for the packaged fixture gallery | yes |
| `hlf_programs/agent_delegation.hlf` | renamed | target `fixtures/delegation.hlf` is the closest current example | yes |
| `hlf_programs/decision_matrix.hlf` | renamed | extracted as `fixtures/decision_matrix.hlf` | yes |
| `hlf_programs/file_io_demo.hlf` | renamed | extracted as `fixtures/file_io_demo.hlf` | yes |
| `hlf_programs/hello_world.hlf` | renamed | `fixtures/hello_world.hlf` | yes |
| `hlf_programs/module_workflow.hlf` | renamed | extracted as `fixtures/module_workflow.hlf` | yes |
| `hlf_programs/system_health_check.hlf` | renamed | extracted as `fixtures/system_health_check.hlf` | yes |

## `hlf_programs/reports/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `hlf_programs/reports/agent_delegation.md` | missing | derived report for source example | no |
| `hlf_programs/reports/decision_matrix.md` | missing | derived report for source example | no |
| `hlf_programs/reports/file_io_demo.md` | missing | derived report for source example | no |
| `hlf_programs/reports/hello_world.md` | missing | derived report for source example | no |
| `hlf_programs/reports/module_workflow.md` | missing | derived report for source example | no |
| `hlf_programs/reports/system_health_check.md` | missing | derived report for source example | no |

## `scripts/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `scripts/build/` | superseded | grammar/parser build is now internalized | no |
| `scripts/build/parser-build.sh` | missing | source parser build helper | no |
| `scripts/catalog_agents.py` | missing | OS agent catalog generator | no |
| `scripts/copilot_factory.py` | missing | OS-specific automation | no |
| `scripts/dispatch.py` | missing | OS dispatcher wrapper | no |
| `scripts/generate_tm_grammar.py` | extracted | adapted as `scripts/generate_tm_grammar.py` against packaged grammar/tag surface | yes |
| `scripts/gen_docs.py` | extracted | adapted as `scripts/gen_docs.py` to generate packaged tag, stdlib, and host-function references | yes |
| `scripts/hat_pr_review.py` | missing | upstream review workflow | no |
| `scripts/hlf_benchmark.py` | merged | packaged equivalent at `hlf_mcp/hlf/benchmark.py` | yes |
| `scripts/hlf_metrics.py` | merged | legacy metrics live in `hlf/mcp_metrics.py` and tests | maybe |
| `scripts/hlf_token_lint.py` | extracted | adapted as `scripts/hlf_token_lint.py` with file + per-line token budgets | yes |
| `scripts/jules_dispatch.sh` | missing | OS orchestration | no |
| `scripts/local_autonomous.py` | missing | OS automation loop | no |
| `scripts/model_policy_lint.py` | missing | upstream model-matrix policy lint | maybe |
| `scripts/ollama-audit.sh` | missing | still useful for model audit workflows | maybe |
| `scripts/persona_gambit.py` | missing | upstream persona orchestration | no |
| `scripts/review.py` | missing | upstream review wrapper | no |
| `scripts/run_audit.py` | missing | upstream audit wrapper | no |
| `scripts/run_hlf_gallery.py` | missing | useful for example fixture gallery | maybe |
| `scripts/run_pipeline_scheduled.py` | extracted | adapted as local scheduled evidence pipeline writing weekly metrics, server-surface counts, governance state, and optional toolkit output | yes |
| `scripts/sovereign_tray.py` | missing | OS tray integration | no |
| `scripts/verify_chain.py` | extracted | adapted as packaged JSONL trace-chain verifier with optional final-hash check | yes |
| `scripts/verify_gui.py` | missing | GUI verifier, not standalone MVP | no |

## `docs/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `docs/AGENTS_CATALOG.md` | extracted | `docs/AGENTS_CATALOG.md` already present | yes |
| `docs/Automated_Runner_Setup_Guide.md` | missing | upstream automation doc | no |
| `docs/benchmark.json` | missing | generated benchmark artifact | no |
| `docs/cli-tools.md` | extracted | adapted as packaged CLI reference for `hlf-mcp`, compiler, runtime, shell, LSP, package manager, and test harness | yes |
| `docs/gen_from_spec.py` | extracted | adapted as packaged spec-driven host-functions reference generator | yes |
| `docs/getting_started.md` | merged | target `QUICKSTART.md` / `BUILD_GUIDE.md` cover this surface | yes |
| `docs/handoff_zai_api_integration.md` | missing | provider-specific upstream doc | no |
| `docs/hat_review_pr50.md` | missing | process artifact | no |
| `docs/hlf_execution_storyboard.svg` | missing | visual asset, optional | no |
| `docs/hlf_explainer.html` | missing | explainer asset, optional | maybe |
| `docs/HLF_GRAMMAR_REFERENCE.md` | extracted | adapted as packaged grammar reference grounded in `hlf_mcp/hlf/grammar.py` and dictionary tooling truth | yes |
| `docs/HLF_PROGRESS.md` | missing | historical progress doc, useful as source evidence | maybe |
| `docs/HLF_REFERENCE.md` | extracted | adapted as packaged language/runtime reference with links to grammar, stdlib, lifecycle, and CLI docs | yes |
| `docs/index.html` | missing | site asset | no |
| `docs/index.md` | missing | site asset | no |
| `docs/infinite_rag_comparison.png` | missing | visual asset | no |
| `docs/INSTINCT_REFERENCE.md` | extracted | adapted as packaged lifecycle reference grounded in `hlf_mcp/instinct/lifecycle.py` | yes |
| `docs/jules_architecture.png` | missing | OS-specific visual asset | no |
| `docs/JULES_COORDINATION.md` | missing | OS-specific doc | no |
| `docs/jules_flow.png` | missing | OS-specific visual asset | no |
| `docs/jules_governance_pipeline.png` | missing | OS-specific visual asset | no |
| `docs/language-reference.md` | missing | overlapping reference doc, likely merged into future generated docs | maybe |
| `docs/metrics.json` | missing | generated artifact | no |
| `docs/openclaw_integration.md` | missing | OpenClaw-specific integration doc | no |
| `docs/README_UPDATE_INSTRUCTIONS.md` | missing | upstream maintenance doc | no |
| `docs/registry_router_flow.png` | missing | visual asset | no |
| `docs/result.md` | missing | generated artifact | no |
| `docs/RFC_9000_SERIES.md` | missing | protocol doctrine source, useful reference | maybe |
| `docs/SESSION_HANDOVER.md` | missing | process doc | no |
| `docs/social_preview.png` | missing | marketing asset | no |
| `docs/Sovereign_OS_Master_Build_Plan.md` | missing | upstream umbrella build plan | no |
| `docs/sovereign_visual_brief.svg` | missing | marketing / vision asset | no |
| `docs/stdlib.md` | extracted | adapted as packaged stdlib guide aligned to Python-backed stdlib bindings and current import drift | yes |
| `docs/system_architecture.png` | missing | visual asset | no |
| `docs/TODO.md` | missing | upstream todo doc | no |
| `docs/TODO_MASTER.md` | missing | upstream todo doc | no |
| `docs/UNIFIED_ECOSYSTEM_ROADMAP.md` | missing | upstream roadmap doc | no |
| `docs/WALKTHROUGH.md` | missing | onboarding doc worth selective extraction | maybe |

## `tests/`

| Source file | Classification | Target / note | Belongs in HLF_MCP |
| --- | --- | --- | --- |
| `tests/test_bytecode.py` | merged | covered by packaged bytecode/runtime/compiler tests | yes |
| `tests/test_bus_bytecode.py` | superseded | source bus integration test, not standalone HLF-core | no |
| `tests/test_gardiner_taxonomy.py` | missing | no packaged taxonomy surface | no |
| `tests/test_grammar_roundtrip.py` | merged | target compiler/formatter/linter tests cover grammar conformance | yes |
| `tests/test_hlf.py` | merged | target `tests/test_mcp_hlf.py` and compiler/runtime coverage | yes |
| `tests/test_hlfc_cli.py` | merged | packaged CLI exercised by compiler/runtime/fixture tests | yes |
| `tests/test_hlflsp.py` | extracted | adapted as packaged LSP regression coverage in `tests/test_hlflsp.py` | yes |
| `tests/test_hlfpm.py` | extracted | adapted as packaged package-manager coverage in `tests/test_hlfpm.py` | yes |
| `tests/test_hlfsh.py` | renamed | extracted as `tests/test_hlf_dxtools.py` shell coverage | yes |
| `tests/test_hlftest.py` | renamed | extracted as `tests/test_hlf_dxtools.py` harness coverage | yes |
| `tests/test_infinite_rag.py` | merged | target memory tests plus `hlf_mcp/rag/memory.py` coverage | yes |
| `tests/test_insaits.py` | extracted | adapted as packaged InsAIts decompiler coverage in `tests/test_insaits.py` | yes |
| `tests/test_intent_capsule.py` | merged | covered by capsule/runtime/frontdoor tests | yes |
| `tests/test_oci_client.py` | extracted | adapted as packaged OCI client coverage in `tests/test_oci_client.py` | yes |
| `tests/test_runtime.py` | merged | covered by current compiler/runtime/integration tests | yes |
| `tests/test_sdd_lifecycle.py` | merged | target instinct lifecycle coverage exists in repo tests/docs | yes |
| `tests/test_soft_veto.py` | superseded | upstream governance workflow helper not extracted | no |
| `tests/test_spec_opcodes.py` | merged | packaged bytecode spec alignment covered indirectly; direct conformance still desirable | yes |
| `tests/test_stdlib.py` | extracted | adapted as packaged Python-backed stdlib coverage in `tests/test_stdlib.py` | yes |
| `tests/test_tool_ecosystem.py` | superseded | tied to upstream installer/monitor ecosystem | no |
| `tests/test_tool_installer.py` | superseded | tied to upstream installer surface intentionally left upstream | no |
| `tests/test_tool_registry.py` | extracted | adapted as packaged tool dispatch coverage in `tests/test_tool_dispatch.py` | yes |
| `tests/test_translator.py` | extracted | adapted as packaged translator coverage in `tests/test_translator.py` | yes |

## Immediate Refactor Outcome

- Batch 1 executed here: packaged `hlfsh`, packaged `hlftest`, and packaged `hlfpm` CLI wiring.
- Batch 2 executed here: four source example programs extracted into packaged v3 fixtures plus a regression that compiles every shipped fixture.
- Batch 3 executed here: extracted `dictionary.json` and `module_import_rules.yaml` into the standalone governance surface.
- Batch 4 executed here: extracted and refactored three support tools — TextMate grammar generation, packaged doc generation, and token-budget linting.
- Batch 5 executed here: extracted the packaged `hlflsp` language server and adapted its tests to the current dual-surface repo reality.
- Batch 6 executed here: extracted and adapted the packaged grammar and stdlib reference docs from the drifted upstream doc surfaces.
- Batch 7 executed here: extracted dedicated packaged regression coverage for the translator and tool dispatch surfaces.
- Batch 8 executed here: extracted dedicated packaged stdlib regression coverage against the Python-backed stdlib modules.
- Batch 9 executed here: extracted dedicated packaged regression coverage for `hlfpm` and `oci_client`.
- Batch 10 executed here: extracted dedicated packaged regression coverage for the InsAIts decompiler surface.
- The remaining gaps are now mostly optional `maybe` surfaces, historical docs, or broader OS-level orchestration assets rather than obvious standalone HLF-core misses.
- The installer/monitor/lockfile/scaffold family remains intentionally upstream because it solves Sovereign OS plugin lifecycle problems rather than the standalone HLF language + MCP product problem.

## Remaining `maybe` Triage

The `maybe` bucket is no longer being treated as an undifferentiated backlog. After the broader extraction pass and full green regression sweep, the remaining `maybe` items split into two categories.

### Real follow-up work

These items still have credible standalone HLF value and are worth future review if more extraction work is chosen:

- `hlf/error_corrector.py` — still a real missing capability if the packaged language is going to support structured authoring repair or IDE-guided autocorrection.
- `hlf/modules/README.md` — worth extracting only if packaged module authoring and publishing become a first-class story beyond the current `hlfpm` install/freeze surface.
- `agents/core/formal_verifier.py` — worth targeted review because an AST/formal verification helper could materially strengthen the language/runtime boundary without dragging in wider Sovereign orchestration.
- `scripts/run_hlf_gallery.py` — still useful if the fixture gallery should become an executable demo/report surface rather than a static folder of examples.
- `governance/align_ledger.py` — worth review only if compatibility with the upstream YAML ALIGN ledger format becomes a real requirement; not needed for the current JSON-based packaged governance truth.
- `docs/HLF_PROGRESS.md` — useful as historical extraction evidence, but documentation-only follow-up rather than runtime work.
- `docs/RFC_9000_SERIES.md` — useful reference doctrine if the standalone repo wants to preserve more upstream protocol rationale locally.
- `docs/WALKTHROUGH.md` — worth selective extraction if the packaged repo needs a stronger operator onboarding narrative than `QUICKSTART.md` and `BUILD_GUIDE.md` currently provide.

### Intentional omissions or already-absorbed surfaces

These items are no longer strong candidates for follow-up because they are either upstream-only, overlapping, or already represented elsewhere in the packaged repo:

- `hlf/similarity_gate.py` — no standalone extraction required now; the similarity-gate behavior is already represented in the packaged `hlf_mcp/hlf/insaits.py` surface and covered by tests.
- `config/personas/*.md` — useful source material, but they belong to the larger Sovereign doctrine/persona system rather than the standalone HLF product runtime.
- `docs/hlf_execution_storyboard.svg` and `docs/hlf_explainer.html` — optional explainer assets, not core extraction debt.
- `scripts/hlf_metrics.py` — already functionally absorbed by the legacy metrics/test surfaces in this repo; no separate extraction needed.
- `scripts/model_policy_lint.py` — tied to upstream model-matrix governance rather than the packaged HLF-core boundary.
- `scripts/ollama-audit.sh` — potentially useful for local model ops, but outside the HLF-core extraction target.
- `docs/language-reference.md` — overlapping with the packaged `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, and generated references already extracted.
- `docs/hlf_explainer.html` — optional presentation asset, not a blocker for source completeness.

Bottom line: the remaining `maybe` list is not hiding obvious core misses. What remains is either selective future enhancement or deliberate non-extraction.
