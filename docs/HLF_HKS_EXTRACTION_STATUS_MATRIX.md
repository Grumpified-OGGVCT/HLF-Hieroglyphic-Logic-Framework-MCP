# HKS Extraction Status Matrix

This document is the repo-facing extraction status view for HKS.

It exists so the HKS maturity story is visible outside the implementation plan and cannot drift into an overclaim.

## Lane Rule

- `vision lane`: the full governed HKS substrate target
- `current-truth lane`: what is packaged and validated now
- `bridge lane`: extracted or planned convergence work that is real but not equivalent to the vision target

## Status Matrix

| Capability | Vision lane target | Current truth now | Status |
| --- | --- | --- | --- |
| Local HKS evaluation authority | full admission, freshness, provenance, and promotion authority | packaged local-evaluation seam with operator/report surfaces | partial extraction |
| External comparator quarantine | optional advisory comparator, never governing truth | packaged and config-gated | strong bounded bridge slice |
| Explicit memory strata | working, episodic, semantic, provenance, archive | packaged contracts now expose memory stratum and storage tier metadata/stats | early bridge slice |
| Hybrid retrieval | lexical, semantic, metadata, graph | lexical, sparse-semantic, metadata-filtered, and persisted graph-linked scoring are packaged | partial extraction |
| Code-aware retrieval | symbol-aware code and doc linkage | not first-class in packaged HKS | not yet extracted |
| Incremental reindex | delta-aware refresh and selective re-embed | not formalized | not yet extracted |
| Multimodal grounding | text, code, image, diagram, structured artifacts | not present as HKS-native runtime contract | not yet extracted |
| Weekly compounding upgrade loop | governed intake, supersession, promotion, deprecation | weekly spine, evidence-query surfaces, and weekly artifact memory graph records are packaged; full governed upgrade loop remains narrow | partial extraction |
| Runtime retrieval substrate | translation, repair, routing, verifier, and orchestration consume governed HKS contracts | translation, repair, routing, verifier, and execution-admission consume governed HKS contracts; orchestration remains partial | partial extraction |

## 2026-03-23 Bridge Update

- Governed recall contracts now carry explicit recall summaries for archive visibility, admission decisions, memory strata, and storage-tier distribution.
- Operator-facing governed recall status, markdown report, and native-comprehension packets now surface that archive/admission summary instead of leaving the bridge state implicit in raw evidence rows.
- The packaged `hlf_memory_stats` MCP tool now exposes an archive/admission bridge summary with active-versus-archived counts and the default archive visibility rule.
- Packaged memory query and governed recall contracts now expose retrieval-path summaries and first graph-linked entity context without overstating this as full graph retrieval.
- Governed route and formal verifier operator surfaces now consume the latest governed-recall posture as advisory context so downstream proof and routing review is not blind to archive visibility or retrieval-path composition.

## 2026-03-24 Bridge Update

- Packaged HKS writes now materialize first-class persisted graph nodes instead of leaving graph structure only as per-record metadata.
- Benchmark artifacts and weekly artifact memory records now emit reusable HKS graph entities for prompt assets, code patterns, upgrade opportunities, and weekly evidence state.
- Packaged query results now emit reusable `governed_hks_contract` payloads and downstream route, repair, verifier, and execution-admission seams consume those admitted contracts directly.
- Capsule execution now denies elevated execution when the routed HKS contract is not admitted, and formal verifier admission upgrades elevated requests to `knowledge_review_required` when governed verifier evidence is missing or inadmissible.
- Focused HKS bridge validation passed in `tests/test_hks_memory.py`, `tests/test_capsule_pointer_trust.py`, and `tests/test_fastmcp_frontdoor.py` (`149 passed`), and adjacent weekly/evidence/workflow/witness validation passed in `31` additional tests.

## Current-Truth Notes

- Packaged HKS lives primarily in [hlf_mcp/rag/memory.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/rag/memory.py), [hlf_mcp/server_memory.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_memory.py), [hlf_mcp/server_context.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_context.py), and [hlf_mcp/server_resources.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_resources.py).
- The packaged HKS front door already includes governed recall, HKS capture/recall, local evaluation surfaces, and quarantined external comparison.
- The packaged memory layer already had hot/warm behavior; the current bridge slice makes memory strata explicit in the contracts, but it does not equal the full upstream tiering architecture.
- The current bridge slice now also includes first-class graph-node persistence and runtime trust gating, but it does not yet equal full code-aware retrieval, uncertainty gating, multimodal evidence assembly, or the complete weekly promotion loop.

## Non-Claims

These are not current-truth claims yet:

- full context-tiering parity with upstream Redis hot-graph loading
- full provenance-anchor parity with intent-bound memory nodes
- fractal summarization and compression-based archive loops
- crew-level HKS synthesis or orchestration as a packaged runtime dependency

## Next Bridge Focus

1. add uncertainty gating and stronger selective invocation rules so HKS retrieval becomes more discriminating at runtime
2. add code-aware ingestion and retrieval depth rather than stopping at graph-linked asset materialization
3. connect weekly drift refresh, supersession, and KPI loops before claiming a fuller HKS platform substrate
