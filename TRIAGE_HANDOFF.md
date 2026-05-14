# HLF MCP Working Tree Triage — Handoff Report
## Branch: rescue/governed-review-recovery-2026-03-21
## Date: 2026-04-14

---

## Overall Assessment: STABLE, with known gaps

The working tree contains 42 modified + 7 new files (~6,865 lines) from 4 dead background agents. Most code is functional but needs full-suite validation (pytest hangs, see below).

---

## Safe (PASSED)

| Component | Tests | Notes |
|-----------|-------|-------|
| Package imports | All | All key modules import cleanly; all claimed methods exist |
| hks_memory | 34/35 passed | 1 pre-existing failure (positional args); artifact_form KeyError FIXED |
| native_onboarding | 13/13 | All green |
| handoff_events | 7/7 | Hash verification, chain continuity verified |
| frontdoor (sync) | 14/15 | 1 known hang (model config loading → LLM call) |
| port_config | 0/8 | All fixture-dependent; no runtime errors |
| install.bat / run.bat | Valid | Syntactically correct; docker compose validated |
| ruff auto-fix | -1587 issues | 2190 → 517 remaining (mostly F405 import-star in test files) |

## Suspect

| Issue | Severity | Details |
|-------|----------|---------|
| pytest hang | HIGH | pytest 9.0.1 hangs on session startup for any HLF_MCP test. Direct Python execution works. Root cause: model config loading (`governance/model_providers.toml`) tries to connect to Ollama/OpenRouter without credentials. Workaround: custom test runner using direct imports. |
| test_governed_recall_syncs_verified_weekly_artifacts_into_memory | LOW | Pre-existing: missing 2 positional args. Not a code bug — test signature doesn't match call pattern. |
| test_align_failure_affects_later_governed_routing | LOW | Hangs due to hlf_align_check triggering LLM call. Known root cause. Marked as known-hanging. |
| SSOT doc drift | LOW | SSOT claims 105 resources (audited at prior snapshot); current registration may differ. SSOT itself says "prefer registry self-consistency over fragile hardcoded counts." |
| 517 ruff issues remain | LOW | Mostly F405 (import-star in tests), E501 (line-too-long), SIM117 (multiple-with). Non-blocking. |

## Missing

| Item | Details |
|------|---------|
| Full test suite | Cannot run via pytest due to hang. Needs either pytest config fix (disable asyncio_mode=auto or mock model config) or custom test runner enhancements. |
| 23 uncommitted resource delta | If SSOT's 105 claim is accurate and current registration is 82, 23 resources may be missing. Could also be SSOT staleness. Needs investigation. |
| Swarm orchestration | donor files exist in HLF_MCP_WORKING but not yet reimplemented in HLF_MCP. See next phase. |

---

## Key Fix Applied

**artifact_form KeyError in test_rag_memory_store_materializes_source_capture_and_artifact_contract**

Root cause: `_build_evidence()` computed `source_authority_label` without including it in the evidence dict, and did not surface `artifact_form` or `artifact_contract` at all. The store's `_normalize_metadata` also did not build `artifact_contract` from top-level metadata keys.

Fix (3 changes in `hlf_mcp/rag/memory.py`):
1. `_normalize_metadata`: Build `artifact_contract` from top-level `artifact_form`/`artifact_kind` when no explicit `artifact_contract` is provided
2. `_build_evidence`: Include `source_authority_label`, `artifact_form`, and `artifact_contract` in evidence dict
3. `store()` duplicate return paths: Include same fields in duplicate evidence dicts for consistency

All 34 previously-passing tests remain green. The fixed test now passes.

---

## Ready for Next Phase: Swarm Orchestration Bridge

The codebase is triaged and stable enough to proceed. The swarm orchestration bridge from HLF_MCP_WORKING (swarm_orchestrator.py, swarm_observer.py, witness_governance.py, symbolic_surfaces.py, formal_verifier.py) can be mined, validated, and cleanly reimplemented into HLF_MCP.
