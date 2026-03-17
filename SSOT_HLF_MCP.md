# Single Source of Truth - HLF-Hieroglyphic-Logic-Framework-MCP

**Generated on:** 2026-03-16
**Branch:** integrate-sovereign
**Purpose:** Authoritative current-state document for this local checkout, grounded in code and validation run on 2026-03-16, with explicit notes on extraction completeness relative to the Sovereign source repo.

## Truth Boundary

This document separates three classes of truth:

1. **Implemented now**: verifiable in this checkout and executable today.
2. **Partial now**: present as code or scaffolding, but not complete enough to claim as finished.
3. **Roadmap / vision**: valuable design direction, but not default present-tense product truth.

If a claim is not backed by files in this repo or a command run in this workspace on 2026-03-16, it does not belong in the "implemented now" section.

This document also now distinguishes between:

- **local checkout truth**: what is actually present and working in `HLF_MCP`
- **source extraction completeness**: how much of the HLF-related surface from `Sovereign_Agentic_OS_with_HLF` has or has not been carried over

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

The repo currently contains **two real implementation surfaces**.

### 1. Packaged FastMCP surface

This is the default build/install surface and the one exposed by `pyproject.toml`.

- Package: `hlf_mcp`
- Entry point: `hlf-mcp`
- Server file: `hlf_mcp/server.py`
- Core compiler/runtime path: `hlf_mcp/hlf/*`
- Current decorator count after this pass: **26 tools, 9 resources, 0 prompts**

### 2. Legacy MCP / support surface

This line is still real and testable, but it is not the package entry point.

- Package path: `hlf/*`
- Server file: `hlf/mcp_server_complete.py`
- Tool/provider stack: `hlf/mcp_tools.py`, `hlf/mcp_resources.py`, `hlf/mcp_prompts.py`
- Noteworthy capability: older `hlf_do` front door and legacy prompt/resource plumbing

### Current repo truth

The right way to describe the repo is **not** "only one server exists" and **not** "everything is one unified stack already".

The truthful statement is:

- the packaged production-facing surface is `hlf_mcp`
- the legacy `hlf/` line still contains useful, working components
- this pass merged one high-value capability (`hlf_do`) forward into the packaged FastMCP surface instead of pretending the split does not exist

## Implemented Now

The following claims are grounded in code present in this checkout.

### Compiler and language pipeline

- `hlf_mcp/hlf/compiler.py` implements a real multi-pass compiler.
- Implemented passes present in code: normalization, LALR parsing, immutable env collection, ethics hook, variable expansion, ALIGN validation, gas estimation, AST cache.
- `hlf_mcp/hlf/translator.py` implements English-to-HLF and HLF-to-English translation helpers.
- `hlf_mcp/hlf/formatter.py` and `hlf_mcp/hlf/linter.py` provide canonical formatting and static analysis.
- The packaged CLI surface now also includes `hlfpm`, `hlfsh`, and `hlftest` entry points for package management, interactive authoring, and fixture/snippet validation.

### Runtime and execution

- `hlf_mcp/hlf/runtime.py` contains a real bytecode VM with gas metering, stack execution, trace capture, and side-effect tracking.
- `hlf_mcp/hlf/bytecode.py` provides bytecode encoding/decoding and opcode tables.
- `hlf_mcp/hlf/capsules.py` implements tiered execution capsules with gas ceilings and AST validation.

### FastMCP server

- `hlf_mcp/server.py` is the packaged FastMCP server.
- Implemented transports: `stdio`, `sse`, and `streamable-http`.
- Implemented health endpoint wrapper: `/health` for HTTP transports.
- Implemented resources: grammar, opcodes, host functions, examples, governance files, stdlib listing.

### Memory and lifecycle

- `hlf_mcp/rag/memory.py` provides the repo's current Infinite RAG memory implementation surface.
- `hlf_mcp/instinct/lifecycle.py` provides the current Instinct lifecycle state machine surface.

### Governance artifacts

- Root governance files are present: `align_rules.json`, `bytecode_spec.yaml`, `host_functions.json`, `tag_i18n.yaml`, `module_import_rules.yaml`, and `MANIFEST.sha256`.
- Extracted governance support assets now also include `governance/templates/dictionary.json` for future LSP and tag-arity aware tooling.
- `hlf_mcp/server.py` checks the governance manifest at startup.
- This pass fixed a real hash drift in `governance/MANIFEST.sha256` for `tag_i18n.yaml`.

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
- This pass corrected the most visible drift, but the entire repo has not yet been exhaustively normalized.

## Roadmap and Vision

The following can be treated as serious design direction, but not as default present-tense shipped truth unless separately verified in code.

- HLF as a universal deterministic orchestration language across agent ecosystems
- larger sovereign / three-brain / ROMA / Darwin-style architecture narratives
- stronger multimodal, research, swarm, and planet-scale coordination claims
- any statement that presumes the full ethics governor, all strategic doctrine, and all surrounding platform layers are production-complete today

These ideas are not invalid. They just belong in the roadmap / doctrine category unless tied to working code in this repo.

## Validation Run on 2026-03-16

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
| `uv run pytest -q --tb=short` | Passed (`513 passed`) |
| FastMCP decorator count in `hlf_mcp/server.py` | 26 tool decorators, 9 resource decorators |

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

## Branch Cleanup State

The branch is currently in a good cleanup posture for PR preparation.

- `integrate-sovereign` is **7 commits ahead, 0 behind** `main`.
- The broad configured regression run is green: `uv run pytest -q --tb=short` passed with `513 passed`.
- The latest cleanup pass removed legacy pytest return-value noise and fixed the stale legacy assumptions that cleanup exposed in `test_mcp_complete.py` and `hlf/mcp_metric.py`.
- The remaining work before commit/PR polish is editorial and organizational rather than functional: keep docs truthful, decide the intentional omissions, and optionally split the current working tree into a small number of coherent commits.

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

And beneath that, the central product problem is still unresolved: there is not yet one sharply defined usefulness claim that the repo can defend without reaching for the larger vision.

And separately, the central migration problem is also unresolved: this repo does not yet document or complete the full extraction/refactor boundary between itself and `Sovereign_Agentic_OS_with_HLF`.

This document exists to keep those three categories separate.
