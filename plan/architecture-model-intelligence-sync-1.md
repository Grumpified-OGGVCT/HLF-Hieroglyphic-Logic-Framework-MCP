---
goal: Governed model intelligence sync for local embeddings, cloud-via-ollama routing, and per-agent recommendations
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: In progress
tags: [architecture, feature, routing, models, governance]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

Define a packaged HLF model-intelligence layer that treats local embeddings, local generative models, and cloud-via-ollama models as one governed reachable plane while preserving explicit locality and trust constraints.

## 1. Requirements & Constraints

- **REQ-001**: Distinguish model discovery from invocation: catalog metadata must not imply the model is callable in the current environment.
- **REQ-002**: Preserve required-local embedding behavior for privacy, data-gravity, and governed memory flows.
- **REQ-003**: Treat Ollama Cloud models accessed through Ollama-compatible endpoints as first-class governed routing targets.
- **REQ-004**: Recommendation outputs must be per workload lane and per agent role, not one global model ranking.
- **CON-001**: Packaged implementation authority stays under `hlf_mcp/`; `hlf_source/` remains archaeology/reference only.
- **CON-002**: Deterministic governance remains authoritative over model suggestions.
- **PAT-001**: Recommendation outputs include rationale, constraints, and operator override hints.

## 2. Implementation Steps

### Implementation Phase 1

- GOAL-001: Define canonical packaged data contracts for model catalog and sync state.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add a packaged schema under `hlf_mcp/` for model entries with access modes `local-via-ollama`, `cloud-via-ollama`, `remote-direct`, and `registry-known-not-configured`. |  |  |
| TASK-002 | Define sync-state fields `installed`, `reachable`, `pullable`, and `known_but_impractical` and map them to user-facing explanations. |  |  |
| TASK-003 | Document required-local embedding rules versus cloud-eligible reasoning lanes in bridge docs and MCP tool descriptions. | ✅ | 2026-03-18 |

### Implementation Phase 2

- GOAL-002: Implement packaged sync and recommendation surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Add packaged model sync tooling that can report reachable local and cloud-via-ollama options without flattening them into one availability flag. |  |  |
| TASK-005 | Add governed per-agent recommendation outputs for retrieval, standards ingestion, code generation, verifier, explainer, and multimodal lanes. |  |  |
| TASK-006 | Bind recommendation outputs to governance events and audit-chain records for operator review. |  |  |

### Implementation Phase 3

- GOAL-003: Validate and operationalize the model-intelligence layer.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Add focused tests for local-only embedding recommendations, cloud-via-ollama recommendations, and fallback behavior when a model is known but unreachable. |  |  |
| TASK-008 | Add docs-sync checks so packaged tool counts and model-lane docs do not drift. |  |  |
| TASK-009 | Add a sync artifact or status report that summarizes best local, best cloud-via-ollama, strongest privacy-preserving, and fallback options per agent lane. |  |  |

## 3. Alternatives

- **ALT-001**: Treat only installed local models as available. Rejected because it hides pullable and cloud-via-ollama options that are operationally relevant.
- **ALT-002**: Rank models only by benchmark score. Rejected because governance, privacy, latency, and role fit matter more than raw leaderboard position.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/server_profiles.py` and future packaged model-catalog helpers.
- **DEP-002**: Governance spine and audit-chain support already landed in Phase 1 and Phase 2 control-plane work.

## 5. Files

- **FILE-001**: `hlf_mcp/server_profiles.py`
- **FILE-002**: `hlf_mcp/server_context.py`
- **FILE-003**: `HLF_ACTIONABLE_PLAN.md`
- **FILE-004**: `HLF_MCP_TODO.md`

## 6. Testing

- **TEST-001**: Focused profile/frontdoor tests for local-only and cloud-via-ollama recommendation outputs.
- **TEST-002**: Governance-event tests confirming recommendation and routing events remain audit-bound.

## 7. Risks & Assumptions

- **RISK-001**: Registry naming drift can create false confidence unless canonicalization rules are enforced.
- **RISK-002**: Model availability may differ from hardware feasibility; recommendation logic must keep both dimensions separate.
- **ASSUMPTION-001**: Ollama-compatible cloud endpoints remain part of the intended reachable model plane for HLF.

## 8. Related Specifications / Further Reading

- `HLF_ACTIONABLE_PLAN.md`
- `HLF_MCP_TODO.md`
- `docs/HLF_STITCHED_SYSTEM_VIEW.md`
