# Recovered MCP Comparison

Date: 2026-03-15

This document reconstructs the comparison work that was in progress across the source Sovereign repo, the HLF_MCP product repo, and the local uncommitted MCP implementation changes.

## High-Confidence Intent Recovered

- The working principle was: the README is acting as the product spec, and code is expected to catch up to it.
- MCP work was being judged against the Sovereign instructions that require MCP workflow integrity, no stale docs, and no drift between README and implementation.
- The comparison was not a simple code diff. It was a cross-check between source documentation, source MCP server behavior, the standalone HLF_MCP README claims, and the local implementation state.

## The Three MCP Surfaces

### 1. Source Sovereign MCP bridge

Files:
- `hlf_source/README.md`
- `hlf_source/mcp/sovereign_mcp_server.py`

What it is:
- An operations bridge for the Sovereign Agentic OS and Antigravity.
- Focused on health checks, intent dispatch, dream cycles, findings, governance, and memory/archive access.

Recovered finding:
- The source README describes this as exposing `8 secure tools`.
- The actual implementation in `hlf_source/mcp/sovereign_mcp_server.py` exposes substantially more than 8 tools because it includes the Janus/search/archive/vault tool family as well.
- The source repo therefore already had internal docs-to-code drift before the standalone HLF_MCP work began.

Representative tool set found in code:
- `check_health`
- `dispatch_intent`
- `run_dream_cycle`
- `get_hat_findings`
- `list_align_rules`
- `get_system_state`
- `query_memory`
- `get_dream_history`
- `search_archives`
- `view_thread_history`
- `deep_recall`
- `vault_similar`
- `vault_stats`
- `janus_web_search`
- `janus_advanced_search`
- `extract_page`
- `ingest_url`
- `summarize_text`

### 2. Standalone HLF_MCP product spec

Files:
- `README.md`
- `hlf_mcp/server.py`

What it is:
- A standalone HLF-first MCP product, not just the Antigravity bridge.
- Focused on compiler, runtime, translation, capsule, memory, instinct, and benchmark tooling.

Recovered finding:
- The README advertises a `FastMCP server: 22 tools, 7 resources`.
- The README tools section lists the HLF-first product surface, including compiler, translation, capsule, memory, instinct, and benchmarking tools.
- The resource section in the same README already drifts from the earlier summary count and lists more than 7 resources.

### 3. Local uncommitted compatibility/port work

Files:
- `hlf/mcp_tools.py`
- `hlf/compiler/*`
- `hlf/vm/*`
- `test_all_tools.py`
- `test_pipeline.py`

What it appears to be:
- A local effort to retrofit or port the standalone HLF_MCP product surface into the older `hlf/` provider architecture.
- This is not a finished cleanup. It is an in-progress convergence layer.

Recovered finding:
- The local patch in `hlf/mcp_tools.py` now defines `32` tools.
- That count is explained by preserving the old 10-tool provider surface and then adding the 22-tool README-era HLF surface on top.
- In other words, the local patch currently overshoots the standalone README spec because it combines legacy and new tool inventories instead of choosing one canonical surface.

## Inventory Reconstruction

### Source Sovereign README claim

Claimed MCP scope in docs:
- `8 secure tools`

### Source Sovereign code reality

Observed scope in code:
- ~18 tools
- 2 resources (`sovereign://settings`, `sovereign://build-plan`)

Conclusion:
- Source repo docs were already stale relative to source code.

### HLF_MCP README claim

Claimed HLF MCP scope in docs:
- `22 tools`
- `7 resources`

README listed tools:
- `hlf_compile`
- `hlf_format`
- `hlf_lint`
- `hlf_validate`
- `hlf_run`
- `hlf_disassemble`
- `hlf_translate_to_hlf`
- `hlf_translate_to_english`
- `hlf_decompile_ast`
- `hlf_decompile_bytecode`
- `hlf_similarity_gate`
- `hlf_capsule_validate`
- `hlf_capsule_run`
- `hlf_host_functions`
- `hlf_host_call`
- `hlf_tool_list`
- `hlf_memory_store`
- `hlf_memory_query`
- `hlf_memory_stats`
- `hlf_instinct_step`
- `hlf_instinct_get`
- `hlf_spec_lifecycle`
- `hlf_benchmark`
- `hlf_benchmark_suite`

Recovered finding:
- The tool table itself lists `24` names, not 22.
- So the README is internally inconsistent: the summary count and the detailed table do not agree.

### HLF_MCP standalone server reality

Observed in `hlf_mcp/server.py`:
- `25` tools
- `9` resources

Tools found in code:
- `hlf_compile`
- `hlf_format`
- `hlf_lint`
- `hlf_run`
- `hlf_validate`
- `hlf_benchmark`
- `hlf_benchmark_suite`
- `hlf_disassemble`
- `hlf_memory_store`
- `hlf_memory_query`
- `hlf_memory_stats`
- `hlf_instinct_step`
- `hlf_instinct_get`
- `hlf_translate_to_hlf`
- `hlf_translate_to_english`
- `hlf_decompile_ast`
- `hlf_decompile_bytecode`
- `hlf_capsule_validate`
- `hlf_capsule_run`
- `hlf_host_functions`
- `hlf_host_call`
- `hlf_tool_list`
- `hlf_similarity_gate`
- `hlf_spec_lifecycle`
- `hlf_submit_ast`

Resources found in code:
- `hlf://grammar`
- `hlf://opcodes`
- `hlf://host_functions`
- `hlf://examples/{name}`
- `hlf://governance/host_functions`
- `hlf://governance/bytecode_spec`
- `hlf://governance/align_rules`
- `hlf://governance/tag_i18n`
- `hlf://stdlib`

Conclusion:
- The standalone server is ahead of the README counts.
- `hlf_submit_ast` and `hlf://governance/tag_i18n` are visible implementation additions beyond the earlier simplified README summary.

### Local legacy provider reality

Observed in local uncommitted `hlf/mcp_tools.py`:
- Original legacy surface retained:
  - `hlf_compile`
  - `hlf_execute`
  - `hlf_validate`
  - `hlf_friction_log`
  - `hlf_self_observe`
  - `hlf_get_version`
  - `hlf_compose`
  - `hlf_decompose`
  - `hlf_analyze`
  - `hlf_optimize`
- New README-era HLF surface added on top:
  - `hlf_format`
  - `hlf_lint`
  - `hlf_run`
  - `hlf_disassemble`
  - `hlf_translate_to_hlf`
  - `hlf_translate_to_english`
  - `hlf_decompile_ast`
  - `hlf_decompile_bytecode`
  - `hlf_similarity_gate`
  - `hlf_capsule_validate`
  - `hlf_capsule_run`
  - `hlf_host_functions`
  - `hlf_host_call`
  - `hlf_tool_list`
  - `hlf_memory_store`
  - `hlf_memory_query`
  - `hlf_memory_stats`
  - `hlf_instinct_step`
  - `hlf_instinct_get`
  - `hlf_spec_lifecycle`
  - `hlf_benchmark`
  - `hlf_benchmark_suite`

Conclusion:
- The local patch is a convergence attempt, not a final aligned state.
- It blends legacy provider responsibilities with the newer standalone product tool surface.

## Likely Lost Conclusions From The Interrupted Session

These conclusions are strongly supported by surviving files, memory, and local changes:

1. The main problem was not just missing code. It was canonicality drift.
2. The source Sovereign MCP server and the standalone HLF_MCP server are different products with different responsibilities.
3. The local uncommitted work was likely trying to port standalone HLF_MCP capabilities into the old provider stack without yet deleting or deprecating the legacy tools.
4. The README cannot currently be treated as numerically authoritative because its own tool/resource counts drift from the tables and the implementation.
5. Before committing anything, one canonical MCP surface needs to be chosen:
   - keep the standalone HLF-first server as canonical,
   - or keep the old provider API as canonical,
   - or explicitly support both as separate modes with different names.

## Immediate Cleanups That Follow From This

1. Decide whether `hlf_mcp/server.py` or `hlf/mcp_tools.py` is the canonical MCP interface.
2. If `hlf_mcp/server.py` is canonical, deprecate or narrow the legacy provider-only tools instead of duplicating surfaces.
3. Update README counts to match the real tool and resource inventory.
4. Exclude generated runtime artifacts like `data/hlf_hot_store.db` from any commit.
5. Validate the local compiler/VM changes before trusting the ported tool behavior.

## Preserved Session Facts From Memory

- HLF is a capability amplifier.
- The README was being treated as the spec target.
- Prior session notes already captured specific metrics API fixes and pending validation work.
- Remaining tasks recorded in memory were: full pytest run, VS Code MCP wiring, smoke test, and commit/push.
