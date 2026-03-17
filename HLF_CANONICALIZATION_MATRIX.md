# HLF Canonicalization Matrix

**Date:** 2026-03-17
**Purpose:** Preserve all materially built HLF work while defining a non-theoretical consolidation boundary across `hlf_mcp`, `hlf`, and `hlf_source`.

## Comparison Baseline

This matrix is grounded in a same-depth inventory and common-file diff between:

- `C:\Users\gerry\generic_workspace\HLF_MCP`
- `C:\Users\gerry\generic_workspace\HLF-NEW`

High-level outcome:

- `HLF_MCP`: 615 inventoried files
- `HLF-NEW`: 131 inventoried files
- Common relative paths: 130
- Only in `HLF_MCP`: 485
- Only in `HLF-NEW`: 1 (`HLF_README.md`)

Conclusion:

- `HLF_MCP` is already the broader preservation surface.
- `HLF-NEW` does not contain a hidden parallel implementation body that has not been brought over.
- Remaining work is not "find the missing repo" work. It is ownership, convergence, and truth-normalization work inside `HLF_MCP`.

## Highest-Value Semantic Deltas From HLF-NEW

These are the common-file or near-common-file deltas worth preserving explicitly.

### 1. `HLF_README.md` contributes operational framing, not missing code

The only file unique to `HLF-NEW` is `HLF_README.md`. It does not introduce a separate runtime or compiler surface. What it does contribute is useful operator framing:

- P0 / P1 / P2 profile language
- SQLite/LRU hot-tier framing
- direct Ollama Cloud gateway framing
- minimal host-function set framing
- validate / observe CLI posture

Those semantics are already materially represented here through:

- `hlf/profiles.py`
- `hlf/profile_config.py`
- `hlf/sqlite_hot_store.py`
- `hlf/stores/sqlite_hot_store.py`
- `hlf/ollama_cloud_gateway.py`
- `HLF_ACTIONABLE_PLAN.md`

Preservation decision:

- Preserve the profile doctrine as supporting product doctrine.
- Do not treat `HLF_README.md` as a missing implementation artifact.
- If desired, absorb its strongest operational prose into docs later, but do not let it drive architecture ownership.

### 2. `README.md` in `HLF_MCP` is an expansion, not a loss

Detailed diff review shows the current `README.md` is ahead of `HLF-NEW` rather than missing content from it.

Explicitly preserved or expanded in the current repo:

- stronger product framing around the glyph language and deterministic execution
- explicit ethical-governor claims and test posture
- expanded tool/resource counts
- the `hlf_do` front door in public docs
- the Arrival analogy and broader language rationale

Preservation decision:

- Keep `README.md` as the canonical public narrative.
- Only mine `HLF-NEW` / `HLF_README.md` for selective operator prose, not for product-truth authority.

### 3. `hlf_mcp/hlf/compiler.py` is ahead and should stay canonical

Common-file diff review shows the current packaged compiler adds real semantics beyond `HLF-NEW`:

- ASCII alias normalization in Pass 0
- bounded SHA-256 compile-result cache
- explicit `HLF_STRICT=0` downgrade path for ethics blocks
- stronger logging and normalization behavior

Preservation decision:

- `hlf_mcp/hlf/compiler.py` remains the canonical compiler implementation.
- No compiler semantics from `HLF-NEW` were identified that are absent from the current packaged compiler and still need rescue.

### 4. `hlf_mcp/hlf/runtime.py` is ahead but still not the only bytecode knowledge source

The current packaged runtime adds meaningful operational safeguards relative to `HLF-NEW`:

- PII redaction on memory writes
- sensitive environment-variable blocklist
- explicit security-error propagation

Preservation decision:

- `hlf_mcp/hlf/runtime.py` remains the canonical executable runtime.
- `hlf/vm/*` and `hlf_source/hlf/*` still matter as semantic mining surfaces for richer bytecode and module behavior.

### 5. `hlf/vm/bytecode.py` remains a semantic mine, not a public authority

The current `hlf/vm/bytecode.py` is materially richer than the older `HLF-NEW` version in places, but it is still not the packaged product surface.

Unique value still present there:

- richer module/function-oriented serialization model
- wider opcode families and typed constant handling
- alternative `.hlb` modeling that may still contain portable semantics

Preservation decision:

- mine it for semantics
- do not let it outrank `hlf_mcp/hlf/bytecode.py` as the executable contract

### 6. Legacy `hlf/mcp_tools.py` still contains useful orchestration semantics

The common-file diff is large because the current legacy MCP tool surface has grown far beyond the simpler HLF-NEW baseline.

Its value is now primarily:

- compatibility/test harness behavior
- legacy orchestration helpers
- a place to identify still-unforwarded behaviors worth porting to `hlf_mcp`

Preservation decision:

- keep mining it for forward-port candidates
- stop treating it as a co-equal product surface

## Non-HLF Context Worth Preserving

There was a reasonable concern that `HLF-NEW` might contain non-HLF assets that matter because they teach an unfamiliar agent how HLF is meant to be used in a larger build.

After inspection, `HLF-NEW` itself is thin in that category:

- no `agents/` directory
- no `config/` directory
- only a small `docs/` surface

What `HLF-NEW` does contribute in that area is mainly:

- `docs/BUILD_GUIDE.md` — MCP resource/tool/prompt usage framing
- `docs/ETHICAL_GOVERNOR_HANDOFF.md` — downstream governance implementation intent
- `docs/QA_FINDINGS.md` and `docs/QA_FINDINGS_HATS.md` — operator trust, validation posture, and review heuristics
- `HLF_README.md` — profile/tier/operator framing

The richer system-level context is already preserved in this repo under `hlf_source`, which is where the deeper failed build left its useful operational clues.

### High-value context-only assets already preserved under `hlf_source`

These files are not the canonical HLF product surface, but they are highly valuable reference context for teaching unfamiliar agents how HLF participates in a broader operating model.

| File | Why it matters |
| --- | --- |
| `hlf_source/config/agent_registry.json` | Encodes role-specialized agents, skill boundaries, model selection, and how HLF-related responsibilities were distributed across a multi-agent system |
| `hlf_source/config/jules_tasks.yaml` | Shows the intended sequential autonomous pipeline, invariants, merge policy, anti-simplification rules, and where HLF maximization fits in the larger process |
| `hlf_source/docs/JULES_COORDINATION.md` | Documents branch ownership, handoff protocol, PR-based cooperation, and how multiple agents were supposed to coordinate around HLF work |
| `hlf_source/docs/openclaw_integration.md` | Explains governed external tool usage, whitelisted binary strategy, tier restrictions, and host-function security posture |
| `hlf_source/agents/gateway/router.py` | Shows practical runtime routing concerns: model selection, gas consumption, tier-based model allowlists, and intent routing around HLF execution |
| `hlf_source/agents/core/formal_verifier.py` | Shows how HLF constraints were intended to connect to formal verification rather than remain purely syntactic or rhetorical |

### Preservation decision for non-HLF context assets

- Preserve these files as context-only reference assets.
- Do not collapse them into the core `hlf_mcp` product surface unless a file directly changes HLF language, runtime, governance, or MCP behavior.
- Use them to inform docs, operator guidance, and future integration decisions.
- Treat them as design-intent evidence from the deeper unfinished build, not as default present-tense product truth.
- See `docs/HLF_AGENT_ONBOARDING.md` for the practical reading order and decision rules for unfamiliar agents entering this repo.

## Preserve / Wrap / Archive Matrix

| Domain | Preserve As Authority | Wrap / Bridge | Archive / Reference Only | Decision |
| --- | --- | --- | --- | --- |
| Public MCP product surface | `hlf_mcp/server.py`, `hlf_mcp/__init__.py`, packaged entry points in `pyproject.toml` | `hlf/mcp_server_complete.py` only as compatibility/test harness if still needed | `hlf_source/mcp/sovereign_mcp_server.py` | `hlf_mcp` is the only product-facing MCP authority |
| Grammar and AST contract | `hlf/spec/core/grammar.yaml`, `hlf/spec/core/ast_schema.json`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/ast_nodes.py` | legacy parser/AST readers in `hlf/compiler/*` only where needed for migration tests | `hlf_source/docs/HLF_GRAMMAR_REFERENCE.md`, `hlf_source/docs/HLF_REFERENCE.md` | packaged grammar/spec surface owns language truth |
| Compiler / translation / formatting | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, `hlf_mcp/hlf/codegen.py` | `hlf/compiler/full_compiler.py`, `hlf/lexer.py`, `hlf/parser.py` only as migration/reference harnesses | `hlf_source/hlf/translator.py`, `hlf_source/hlf/hlffmt.py`, `hlf_source/hlf/insaits.py` | all new language behavior lands in `hlf_mcp` first |
| Runtime / bytecode / VM | `hlf_mcp/hlf/bytecode.py`, `hlf_mcp/hlf/runtime.py`, `governance/bytecode_spec.yaml`, `hlf/spec/vm/bytecode_spec.yaml` | thin compatibility adapters from legacy VM surfaces only if required by tests or transition tooling | `hlf/vm/bytecode.py`, `hlf/vm/interpreter.py`, `hlf/vm/vm.py`, `hlf/vm/value.py`, `hlf_source/hlf/bytecode.py`, `hlf_source/hlf/runtime.py` | packaged bytecode/runtime defines executable truth; legacy/upstream VM files are semantic mines |
| Governance / ethics / capsules | `hlf_mcp/hlf/ethics/*`, `hlf_mcp/hlf/capsules.py`, `governance/*.json`, `governance/*.yaml`, `governance/MANIFEST.sha256` | compiler and server expose these as enforcement/resources | `hlf_source/governance/*` templates and policy docs | governance files and packaged ethics code stay authoritative here |
| Host functions / stdlib / dispatch | `governance/host_functions.json`, `hlf_mcp/hlf/tool_dispatch.py`, `hlf_mcp/hlf/stdlib/*` | `hlf/host_functions_minimal.py` remains a compatibility shim until registry-backed dispatch fully subsumes it | `hlf_source/hlf/stdlib/*.hlf`, `hlf_source/hlf/tool_dispatch.py`, `hlf_source/hlf/tool_installer.py`, `hlf_source/hlf/tool_lockfile.py`, `hlf_source/hlf/tool_monitor.py`, `hlf_source/hlf/tool_scaffold.py` | executable stdlib truth belongs to packaged Python-backed stdlib and governance registry |
| CLI / packaging / authoring | `hlf_mcp/hlf/hlfpm.py`, `hlf_mcp/hlf/hlfsh.py`, `hlf_mcp/hlf/hlftest.py`, `hlf_mcp/hlf/hlflsp.py`, `hlf_mcp/hlf/oci_client.py` | `hlf/hlf_cli.py` can remain an operator convenience wrapper if documented as such | `hlf_source/hlf/hlfpm.py`, `hlf_source/hlf/hlfsh.py`, `hlf_source/hlf/hlftest.py`, `hlf_source/hlf/hlflsp.py`, `hlf_source/hlf/hlfrun.py` | packaged CLI/LSP line is the canonical developer/operator surface |
| Memory / lifecycle / profile system | `hlf_mcp/rag/memory.py`, `hlf_mcp/instinct/lifecycle.py` for packaged public behavior | `hlf/infinite_rag_hlf.py`, `hlf/profiles.py`, `hlf/profile_config.py`, `hlf/sqlite_hot_store.py`, `hlf/stores/sqlite_hot_store.py`, `hlf/ollama_cloud_gateway.py` are preserved support modules to be explicitly integrated rather than discarded | `hlf_source/hlf/infinite_rag.py`, `hlf_source/hlf/memory_node.py`, related upstream support surfaces | these are real HLF assets; they are not archive-only, but they are not yet the packaged contract |
| Docs / generators / syntax / fixtures / tests | `README.md`, `BUILD_GUIDE.md`, `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`, `scripts/generate_tm_grammar.py`, `scripts/gen_docs.py`, `docs/gen_from_spec.py`, `syntaxes/hlf.tmLanguage.json`, `fixtures/*`, packaged `tests/*` | root smoke tests and compatibility checks remain useful wrappers | `hlf_source/docs/*`, `hlf_source/tests/*`, `hlf_source/hlf_programs/*` stay as upstream reference corpus | docs/tests in the current repo are the living proof surface; upstream docs/tests are research and drift-detection inputs |
| Broader sovereign agent ecosystem | none in `hlf_mcp` by default | selective bridges only when they materially affect HLF language/runtime semantics | `hlf_source/agents/*`, `hlf_source/config/*`, `hlf_source/plugins/*`, `hlf_source/gui/*`, `hlf_source/dapr/*` | out of canonical HLF product scope unless a file directly changes language/runtime/governance behavior |
| Non-HLF operational context for agent usage | none as executable authority | selected doctrine can be echoed into docs and operator guidance | `hlf_source/config/agent_registry.json`, `hlf_source/config/jules_tasks.yaml`, `hlf_source/docs/JULES_COORDINATION.md`, `hlf_source/docs/openclaw_integration.md`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/core/formal_verifier.py` | preserve as context-only teaching material for how HLF was intended to be used in a larger agent system |

## Canonical Runtime / Bytecode Ownership Boundary

### Ownership Decision

Effective immediately, executable HLF runtime and bytecode ownership belongs to the packaged line:

- `hlf_mcp/hlf/bytecode.py`
- `hlf_mcp/hlf/runtime.py`
- `governance/bytecode_spec.yaml`
- `hlf/spec/vm/bytecode_spec.yaml`

These files define the runtime and `.hlb` contract that the packaged MCP server is allowed to execute and document as current truth.

Everything else is subordinate to that boundary.

### What Moves Into The Canonical Boundary

These are not yet blanket file moves. They are the first extraction targets that should be reviewed and ported into the packaged boundary if their semantics are still needed.

From `hlf/vm/bytecode.py`:

- richer module/function metadata model
- any opcode families not yet represented in `hlf_mcp/hlf/bytecode.py` but still aligned with the current governance spec
- constant-pool or typed-entry behavior that improves fidelity without changing public contract unpredictably
- disassembly/round-trip helpers that strengthen inspection and validation

From `hlf/vm/interpreter.py` and related `hlf/vm/*` files:

- value semantics or control-flow behaviors not yet reflected in the packaged runtime
- execution behaviors that are defensible and spec-compatible, not merely historical

From `hlf_source/hlf/runtime.py`:

- module import / namespace merge semantics only if they still belong to the language/runtime product
- host registry dispatch patterns only where they improve the packaged runtime rather than reintroduce source-repo sprawl
- sensitive-output hashing or tier enforcement behaviors not already covered in `hlf_mcp/hlf/runtime.py`

### What Wraps The Canonical Boundary

These files remain useful, but they should defer to packaged ownership instead of competing with it.

- `hlf/mcp_server_complete.py`
- `hlf/mcp_tools.py`
- `hlf/mcp_resources.py`
- `hlf/mcp_prompts.py`
- `hlf/mcp_metric.py`
- `hlf/mcp_metrics.py`
- `hlf/mcp_client.py`

Rule:

- no new product-truth feature lands in these files first
- if a behavior is still valuable, port it into `hlf_mcp` and leave a compatibility wrapper behind only if tests or operators still need it

These support-line files are also preserved as active bridges until the packaged line has fully absorbed what matters:

- `hlf/profiles.py`
- `hlf/profile_config.py`
- `hlf/sqlite_hot_store.py`
- `hlf/stores/sqlite_hot_store.py`
- `hlf/ollama_cloud_gateway.py`
- `hlf/infinite_rag_hlf.py`

These are not archive junk. They are preserved support assets that need explicit integration decisions.

### What Stays Reference-Only

These files are preserved for archaeology, drift detection, and selective semantic mining, but they are not current product authority.

- `hlf_source/hlf/bytecode.py`
- `hlf_source/hlf/runtime.py`
- `hlf_source/hlf/translator.py`
- `hlf_source/hlf/hlffmt.py`
- `hlf_source/hlf/hlflsp.py`
- `hlf_source/hlf/hlfpm.py`
- `hlf_source/hlf/hlfsh.py`
- `hlf_source/hlf/hlftest.py`
- `hlf_source/hlf/stdlib/*.hlf`
- `hlf_source/docs/*`
- `hlf_source/tests/*`
- `hlf_source/hlf_programs/*`

The same rule applies to the broader sovereign agent ecosystem under `hlf_source/agents/*` and adjacent directories unless a file directly changes HLF language, runtime, governance, or MCP behavior.

## First Consolidation Step

The first real consolidation step is now defined:

1. Freeze executable runtime/bytecode ownership in `hlf_mcp/hlf/*` plus the packaged specs.
2. Treat `hlf/vm/*` as extraction targets, not parallel truth.
3. Treat `hlf_source/*` as upstream reference-only unless a file carries unique HLF semantics not yet represented locally.
4. Keep profile/store/gateway support modules alive in `hlf/` until they are either integrated into `hlf_mcp` or explicitly declared outside packaged scope.
5. Forward-port any still-valuable legacy MCP behavior from `hlf/*` into `hlf_mcp`, then leave wrappers instead of dual authorities.

## Immediate Next Port Candidates

When implementation begins, start here:

1. Runtime-governance integration at the packaged runtime layer, not the legacy VM layer.
2. Formal decision on whether module/function metadata from `hlf/vm/bytecode.py` belongs in the packaged `.hlb` contract.
3. Explicit integration or scoping decision for profile/store/gateway support modules in `hlf/`.
4. French-first i18n trust gates against `governance/tag_i18n.yaml` and packaged translation/compiler paths.
5. Externalization of PII/security policy so it is not trapped as ad hoc runtime code.