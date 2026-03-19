---
goal: Define and complete the launch-bounded Chinese cognitive lane for HLF without overclaiming a full Chinese-native execution grammar
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: In progress
tags: [feature, chinese, multilingual, routing, launch, benchmark, audit]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan defines the executable work needed to make the Chinese-enhanced HLF cognitive lane launch-complete.

The target is a bounded launch lane, not a speculative full multiscript execution rewrite.

## 1. Requirements & Constraints

- **REQ-001**: Preserve canonical HLF as the only execution authority at launch.
- **REQ-002**: Treat Chinese as a first-class measured lane across translation, retrieval, and routing proof.
- **REQ-003**: Preserve English operator audit as mandatory at launch.
- **REQ-004**: Prevent unsupported Chinese-specific grammar or symbolic extensions from silently becoming runtime truth.
- **REQ-005**: Use benchmarked outcomes instead of projections for any promotion decision.
- **CON-001**: Current packaged translator truth is limited to `en`, `fr`, `es`, `ar`, and `zh`.
- **CON-002**: Russian and German remain future lanes until translator templates, diagnostics, and tests are implemented.
- **GUD-001**: Add proof surfaces before adding new speculative language features.
- **PAT-001**: Prefer measured lane selection through routing and retrieval instead of making Chinese a global default.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Finish the benchmark and launch-definition foundation.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Maintain [docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md) as the ranking-policy source for supported language lanes. | ✅ | 2026-03-18 |
| TASK-002 | Maintain [docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md) as the launch-scope contract for Chinese-enhanced HLF. | ✅ | 2026-03-18 |
| TASK-003 | Keep Chinese explicit in multilingual benchmark regression coverage in [tests/test_benchmark_multilingual.py](c:/Users/gerry/generic_workspace/HLF_MCP/tests/test_benchmark_multilingual.py). | ✅ | 2026-03-18 |

### Implementation Phase 2

- **GOAL-002**: Add retrieval-backed multilingual proof for Chinese and other supported lanes.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add multilingual translation-memory tests proving exemplar capture and retrieval across `en`, `fr`, `es`, `ar`, and `zh` in the packaged memory/query surfaces. |  |  |
| TASK-005 | Add benchmark helpers that report retrieval success or ranking quality by language lane for translation-memory tasks. |  |  |
| TASK-006 | Document the retrieval evaluation thresholds required before calling the Chinese cognitive lane launch-ready. |  |  |

### Implementation Phase 3

- **GOAL-003**: Add routing-aware language-lane proof.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create the packaged routing recovery spec that folds MoMA-style workload dispatch into current governed routing surfaces. |  |  |
| TASK-008 | Add routing tests proving that language-sensitive workload selection remains governed, auditable, and fail-safe. |  |  |
| TASK-009 | Add explicit policy hooks so Chinese-enhanced routing preferences can be enabled without becoming an uncontrolled global default. |  |  |

### Implementation Phase 4

- **GOAL-004**: Harden audit and anti-fragmentation gates for launch.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-010 | Add tests that prove English sidecar summaries remain available and legible for Chinese-enhanced internal handling. |  |  |
| TASK-011 | Add verifier or linter checks that reject unsupported Chinese-specific symbolic extensions instead of silently interpreting them. |  |  |
| TASK-012 | Update doctrine and launch docs to mark what is canonical, optional, experimental, and forbidden in the Chinese cognitive lane. |  |  |

## 3. Alternatives

- **ALT-001**: Make Chinese the immediate default internal lane without retrieval, routing, or audit proof. Rejected because it promotes projection over measured correctness.
- **ALT-002**: Treat Chinese as only a translation convenience and avoid a cognitive-lane concept entirely. Rejected because it undercounts the compression and semantic-density upside the user is explicitly targeting.
- **ALT-003**: Implement a full new Chinese-native execution grammar before launch. Rejected because the current packaged repo does not yet have the grammar, verifier, or runtime proof for that claim.

## 4. Dependencies

- **DEP-001**: [hlf_mcp/hlf/translator.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/hlf/translator.py)
- **DEP-002**: [hlf_mcp/hlf/benchmark.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/hlf/benchmark.py)
- **DEP-003**: [hlf_mcp/server_profiles.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/server_profiles.py)
- **DEP-004**: [hlf_mcp/rag/memory.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/rag/memory.py)
- **DEP-005**: [hlf_mcp/hlf/insaits.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/hlf/insaits.py)

## 5. Files

- **FILE-001**: [docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md) — launch-scope contract
- **FILE-002**: [docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md) — language-promotion benchmark source
- **FILE-003**: [hlf_mcp/hlf/benchmark.py](c:/Users/gerry/generic_workspace/HLF_MCP/hlf_mcp/hlf/benchmark.py) — benchmark and language comparison logic
- **FILE-004**: [tests/test_benchmark_multilingual.py](c:/Users/gerry/generic_workspace/HLF_MCP/tests/test_benchmark_multilingual.py) — multilingual benchmark regression tests
- **FILE-005**: [tests/test_translator.py](c:/Users/gerry/generic_workspace/HLF_MCP/tests/test_translator.py) — translator regression tests

## 6. Testing

- **TEST-001**: Verify multilingual benchmark regression remains green for supported languages including Chinese.
- **TEST-002**: Add translation-memory retrieval tests with Chinese exemplar coverage.
- **TEST-003**: Add governed routing tests for language-lane-sensitive workload selection.
- **TEST-004**: Add English sidecar audit tests for Chinese-enhanced internal handling.
- **TEST-005**: Add rejection tests for unsupported Chinese-specific symbolic extensions.

## 7. Risks & Assumptions

- **RISK-001**: Compression gains may not correlate with better retrieval or routing outcomes on every workload.
- **RISK-002**: Chinese-heavy internal handling could degrade operator trust if English sidecar quality is weak.
- **RISK-003**: Premature grammar expansion could create a private dialect that weakens determinism.
- **ASSUMPTION-001**: Canonical HLF remains stable enough to act as the execution anchor while language lanes evolve.
- **ASSUMPTION-002**: Chinese remains the strongest current natural-language compression candidate, but it still must win on measured outcomes.

## 8. Related Specifications / Further Reading

[docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md)
[docs/HLF_ZHOTHEPHUN_DEFAULTING_RECOMMENDATION.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_ZHOTHEPHUN_DEFAULTING_RECOMMENDATION.md)
[docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md](c:/Users/gerry/generic_workspace/HLF_MCP/docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md)