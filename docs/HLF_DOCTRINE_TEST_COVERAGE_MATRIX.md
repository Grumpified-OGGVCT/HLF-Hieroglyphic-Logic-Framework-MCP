---
goal: Map constitutive HLF doctrine pillars to current regression coverage and name the next proof gaps
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: 'In progress'
tags: [testing, doctrine, bridge, multilingual, glyphs, coverage, hlf]
---

# HLF Doctrine To Test Coverage Matrix

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This file maps constitutive HLF doctrine pillars to current packaged tests.

It exists to prevent a familiar failure mode:

- proving only the MVP path
- mistaking public docs for runtime proof
- undercounting multilingual, glyph, memory, governance, and operator-trust surfaces because they are spread across multiple files

## 1. Reading Rule

- This is a bridge-lane artifact, not a marketing document.
- A pillar can be present in code and still be under-proved in tests.
- A pillar can be documented strongly and still remain source-only in packaged truth.
- Multilingual and glyph-surface work must not be silently collapsed into a generic "translator works" claim.

## 2. Matrix

| Pillar | Current packaged owners | Current regression proof | Coverage status | Main uncovered or under-proved areas |
| --- | --- | --- | --- | --- |
| Deterministic language core | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py` | `tests/test_compiler.py`, `tests/test_formatter.py`, `tests/test_linter.py`, `tests/test_fixtures_catalog.py` | Strong | More explicit proof for chained glyph modifiers and broader grammar/document conformance |
| Runtime and bytecode | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/bytecode.py` | `tests/test_bytecode_roundtrip.py`, `tests/test_capsule_pointer_trust.py`, `tests/test_runtime_memory_context.py`, `tests/test_compiler.py` | Strong but incomplete | Broader replay proofs, richer bytecode/runtime equivalence, deeper trace validation |
| Governance-native execution | `governance/align_rules.json`, `hlf_mcp/hlf/ethics/*`, `hlf_mcp/server_context.py` | `tests/test_ethics.py`, `tests/test_governance_spine.py`, `tests/test_security.py`, `tests/test_update_governor.py` | Strong | Cross-surface governance proofs for restored routing/verifier/orchestration work |
| Capsule, escalation, and approval semantics | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py`, `hlf_mcp/hlf/approval_ledger.py` | `tests/test_capsule_pointer_trust.py` | Strong for current bridge slice | Durable operator workflow and longer-lived approval/audit interactions |
| HLF knowledge substrate and governed memory | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` | `tests/test_hks_memory.py`, `tests/test_runtime_memory_context.py`, `tests/test_capsule_pointer_trust.py`, `tests/test_governance_spine.py`, `tests/test_witness_governance.py` | Partial | Stronger freshness, revocation, trust-tier, provenance, chain-verification, and package-boundary contracts |
| Multilingual intent capture and reverse audit | `hlf_mcp/hlf/translator.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/hlf/benchmark.py`, `hlf_mcp/server_resources.py` | `tests/test_translator.py`, `tests/test_fastmcp_frontdoor.py` | Partial but real | No packaged evaluation suite yet for multilingual recall quality, fallback discipline, and memory-backed multilingual retrieval |
| Glyph / ASCII dual-surface language model | `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/bytecode.py` | `tests/test_compiler.py`, `tests/test_formatter.py`, `tests/test_bytecode_roundtrip.py`, `tests/test_fastmcp_frontdoor.py` | Partial | Canonical proof for deeper glyph chaining, broader dictionary authority, and docs-to-parser conformance |
| Chinese and multi-script handling | `hlf_mcp/hlf/translator.py`, `governance/tag_i18n.yaml`, `hlf_mcp/server_resources.py` | `tests/test_translator.py`, `tests/test_fastmcp_frontdoor.py` | Partial and narrower than vision | Chinese is currently supported as natural-language input/output and tag registry material, not as a separate canonical pictogram grammar layer or preserved Zho'thephun-style multi-script framework |
| Human-readable trust surface | `hlf_mcp/hlf/insaits.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/server_resources.py`, `hlf_mcp/hlf/audit_chain.py` | `tests/test_insaits.py`, `tests/test_fastmcp_frontdoor.py`, `tests/test_governance_spine.py` | Partial | Continuous transparency, operator dashboards, richer effect previews, and gallery-grade proof artifacts |
| Routing fabric | `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/runtime.py` | `tests/test_runtime_memory_context.py` | Thin / partial | Upstream gateway/router semantics, MoMA-style workload routing, routing traces, and governance-aware provider selection are not yet restored |
| Formal verification lane | source-only upstream anchor in `hlf_source/agents/core/formal_verifier.py`; packaged status resource in current MCP surface | Surface registration checks in `tests/test_fastmcp_frontdoor.py` | Thin / placeholder | No real packaged formal-verifier behavior or proof-producing regression suite yet |
| Orchestration lifecycle | `hlf_mcp/instinct/lifecycle.py`, `hlf_mcp/server_instinct.py` | `tests/test_fastmcp_frontdoor.py` | Partial | Instinct is present, but full plan-execution and crew-orchestration restoration is still source-only |
| Tool/effect lifecycle | `hlf_mcp/hlf/tool_dispatch.py` | `tests/test_tool_dispatch.py` | Strong | Cross-check against future routing/orchestration restoration |
| Weekly artifact and workflow proof | `.github/scripts/*`, `hlf_mcp/weekly_artifacts.py`, `hlf_mcp/test_runner.py` | `tests/test_workflow_support.py`, `tests/test_weekly_artifacts.py`, `tests/test_test_runner.py`, `tests/test_github_scripts.py` | Strong | Need tie-in to broader doctrine batch acceptance gates |
| Persona / operator doctrine | `AGENTS.md`, `docs/AGENTS_CATALOG.md`, operator handoff docs | No dedicated packaged doctrine regression suite | Thin | No current packaged tests asserting persona doctrine effects on runtime, operator review, or governance workflows |
| Ecosystem / gallery bridge | docs and source-only materials | No dedicated packaged regression suite | Missing in packaged proof | Still bridge work; no packaged gallery/operator demo proof suite |

## 3. Findings On Multilingual And Multi-Script HLF

### ACTUAL packaged truth

1. Multilingual support is still real in the packaged lane.
2. The packaged translator resolves `en`, `fr`, `es`, `ar`, and `zh` and has dedicated Chinese translation handling.
3. The packaged FastMCP front door exercises non-English input and localized reverse summaries.
4. The packaged resource surface exposes a multilingual tag registry through `hlf://governance/tag_i18n`.

### What is not currently true

1. The repo does not currently preserve a separately implemented canonical Chinese pictogram grammar for HLF.
2. The repo does not currently preserve a named `Zho'thephun` or equivalent multi-script framework artifact in tracked canonical docs or packaged code.
3. The repo does not currently contain tracked copies of the titled research/article artifacts listed in the current conversation.
4. MoMA routing survives as bridge doctrine and transcript-backed planning context, not as a restored packaged routing subsystem.

### Correct reading

The multilingual lane was not erased.

What happened instead is narrower and more important:

- multilingual natural-language input/output survived in packaged code
- glyph/ASCII dual-surface semantics survived in grammar/compiler/runtime/docs
- Chinese support survived at the translator and registry layer
- broader multi-script and routing research appears not to have been canonically preserved as first-class packaged artifacts under their original titles

That means this is a preservation and bridge gap, not proof that the whole multilingual idea disappeared.

## 4. Exact Gaps To Close Next

- **TEST-ML-001**: add a dedicated multilingual benchmark regression suite for fidelity, fallback, and reverse-summary quality across `en`, `fr`, `es`, `ar`, and `zh`
- **TEST-ML-002**: add translation-memory tests that prove multilingual exemplar capture and retrieval, not just direct translator invocation
- **TEST-GS-001**: add glyph/ASCII conformance tests that prove the same program round-trips and compiles equivalently across both surfaces
- **TEST-GS-002**: add explicit regression coverage for broader glyph chains and documented dictionary-backed glyph usage
- **TEST-RT-001**: create routing restoration tests once the packaged routing recovery spec exists
- **TEST-FV-001**: create a real packaged formal-verifier test plan before calling that lane restored
- **TEST-PD-001**: define operator/persona doctrine tests that prove those surfaces affect runtime behavior or review workflow rather than existing only as prose

## 5. Related Files

- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_REPO_IMPLEMENTATION_MAP.md`
- `plan/architecture-hlf-reconstruction-2.md`
- `tests/test_translator.py`
- `tests/test_fastmcp_frontdoor.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/grammar.py`
- `hlf_mcp/server_resources.py`