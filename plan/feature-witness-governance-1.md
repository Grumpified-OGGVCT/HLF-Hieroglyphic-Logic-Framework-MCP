---
goal: Implement transcript-backed witness governance as a packaged probationary swarm-trust bridge surface for HLF
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: 'Planned'
tags: [feature, planning, witness-governance, trust, audit, memory, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines the second transcript-backed implementation slice after entropy anchors: witness governance. The goal is to add a packaged trust and probation mechanism that records structured witness observations, aggregates trust-impacting evidence, and supports probationary degradation rather than brittle single-strike bans.

This is bridge-lane work. It should establish the local trust substrate and operator-review path without importing the entire larger Sovereign swarm-governance stack.

## 1. Requirements & Constraints

- **REQ-001**: Witness governance must be implemented as structured evidence, not as free-form comments or vague logs.
- **REQ-002**: The first slice must support probationary trust degradation before any hard isolation outcome.
- **REQ-003**: Multi-witness confirmation must be possible for stronger enforcement outcomes.
- **REQ-004**: Witness records must be traceable to agent identity, goal/session context, and auditable event chains.
- **REQ-005**: The first slice must be usable by packaged runtime, memory, or governance surfaces without requiring a full service bus restoration.
- **SEC-001**: No single malformed or low-confidence witness observation may automatically create irreversible bans in the packaged first slice.
- **SEC-002**: Witness records that influence execution must be auditable and attributable.
- **SEC-003**: The feature must not silently widen agent permissions or hide trust degradation decisions from operator review.
- **ARC-001**: The first slice is witness evidence + trust scoring + probation, not the full upstream swarm-governance network.
- **ARC-002**: The feature should land in `hlf_mcp/` packaged surfaces first; source-only materials are reference inputs only.
- **CON-001**: Do not import the larger service-bus or broader OS gossip protocol wholesale.
- **CON-002**: Do not encode hard permanent bans into the initial packaged implementation.
- **GUD-001**: Reuse existing ledger, audit, memory, and trust-adjacent surfaces where possible.
- **PAT-001**: The first packaged flow should be: event or execution outcome -> witness observation -> structured storage -> trust-score update -> probation or review recommendation.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Create the packaged witness-record and trust-score substrate.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add a new packaged helper module under `hlf_mcp/hlf/` such as `witness_governance.py` defining witness-record schema, trust-impact schema, and probation-state transitions. |  |  |
| TASK-002 | Define canonical witness fields including at minimum: `witness_id`, `subject_agent_id`, `goal_id`, `session_id`, `event_ref`, `category`, `severity`, `confidence`, `evidence_hash`, and `recommended_action`. |  |  |
| TASK-003 | Add deterministic trust-state outputs such as `healthy`, `watched`, `probation`, and `restricted`. |  |  |
| TASK-004 | Define aggregation rules that require multiple independent negative observations before the system can recommend a stronger restriction than probation. |  |  |

### Implementation Phase 2

- **GOAL-002**: Connect witness governance to existing packaged audit and memory surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Use `hlf_mcp/hlf/audit_chain.py` as the trace sink for witness-related events so trust changes are auditable. |  |  |
| TASK-006 | Add a structured persistence layer using the existing packaged memory substrate or a clearly bounded adjacent SQLite store, rather than ephemeral in-memory state only. |  |  |
| TASK-007 | Add server-context integration so trust state can be queried or updated by packaged governance-aware tools without requiring a service bus. |  |  |
| TASK-008 | Ensure witness evidence can reference existing event hashes from runtime, capsule, or memory operations. |  |  |

### Implementation Phase 3

- **GOAL-003**: Expose a minimal packaged MCP/operator surface for witness governance.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Add MCP tools for recording witness observations, querying trust state, and listing probationary agents through the appropriate packaged server module. |  |  |
| TASK-010 | Add operator-review-friendly output contracts so trust degradations are explicit and legible. |  |  |
| TASK-011 | Avoid any automatic permanent-ban behavior in the first slice; hard isolation should remain a recommendation or high-threshold future extension. |  |  |
| TASK-012 | Define exact interaction points with future routing or execution throttling, but keep them as explicit bridge hooks if not implemented in the first slice. |  |  |

### Implementation Phase 4

- **GOAL-004**: Lock the packaged first slice with tests and bridge-doc updates.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Add focused regression coverage such as `tests/test_witness_governance.py` for schema, aggregation, and probation-state transitions. |  |  |
| TASK-014 | Add integration coverage for any new MCP tools in `tests/test_fastmcp_frontdoor.py` or targeted server tests. |  |  |
| TASK-015 | Update the relevant bridge docs once the feature is real: `docs/HLF_REPO_IMPLEMENTATION_MAP.md`, `SSOT_HLF_MCP.md`, and any transcript bridge notes as needed. |  |  |
| TASK-016 | Add a minimal operator-facing note describing that the packaged first slice is probationary trust governance, not full decentralized swarm ostracism. |  |  |

## 3. Alternatives

- **ALT-001**: Implement hard one-strike bans immediately. Rejected because the transcript itself highlights false-positive cascade risk.
- **ALT-002**: Treat witness governance as source-only and defer all local work. Rejected because the repo already has enough audit/memory substrate to support a bounded first slice.
- **ALT-003**: Hide witness outputs inside general logs. Rejected because trust-affecting evidence must be explicit and operator-reviewable.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/hlf/audit_chain.py`
- **DEP-002**: `hlf_mcp/rag/memory.py`
- **DEP-003**: `hlf_mcp/hlf/approval_ledger.py`
- **DEP-004**: `hlf_mcp/server_context.py`
- **DEP-005**: `hlf_mcp/server_memory.py`
- **DEP-006**: `docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md`

## 5. Files

- **FILE-001**: `hlf_mcp/hlf/witness_governance.py` — new packaged witness/trust helper
- **FILE-002**: `hlf_mcp/hlf/audit_chain.py` — structured trust-event trace sink
- **FILE-003**: `hlf_mcp/rag/memory.py` or adjacent bounded store — persistence target for witness evidence and trust state
- **FILE-004**: `hlf_mcp/server_context.py` — shared trust-state access point
- **FILE-005**: `hlf_mcp/server_memory.py` or another appropriate server module — MCP-facing witness/trust tools
- **FILE-006**: `tests/test_witness_governance.py` — new regression coverage
- **FILE-007**: `tests/test_fastmcp_frontdoor.py` — packaged surface update if new tools are added

## 6. Testing

- **TEST-001**: Verify a single low-confidence negative witness event does not create hard isolation.
- **TEST-002**: Verify repeated or multi-witness negative evidence transitions an agent through `watched` to `probation` deterministically.
- **TEST-003**: Verify trust-state outputs are auditable and tied to concrete evidence hashes.
- **TEST-004**: Verify new MCP-facing witness/trust tools return operator-legible structured outputs.
- **TEST-005**: Run targeted regressions: `uv run pytest tests/test_witness_governance.py tests/test_fastmcp_frontdoor.py -q --tb=short`.

## 7. Risks & Assumptions

- **RISK-001**: Trust aggregation can become noisy if evidence categories and severities are not normalized early.
- **RISK-002**: Hooking witness outcomes into routing or execution too early could create brittle behavior before confidence and review semantics mature.
- **RISK-003**: A first local slice may capture evidence cleanly but still need later refinement for distributed witness identity.
- **ASSUMPTION-001**: Existing packaged audit and ledger surfaces are sufficient for a bounded first implementation.
- **ASSUMPTION-002**: The first slice can remain local-package scoped and does not need a full service-bus restoration to be valuable.

## 8. Related Specifications / Further Reading

[docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md](../docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md)
[docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md](../docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md)
[docs/HLF_REPO_IMPLEMENTATION_MAP.md](../docs/HLF_REPO_IMPLEMENTATION_MAP.md)
[docs/HLF_MISSING_PILLARS.md](../docs/HLF_MISSING_PILLARS.md)
[plan/feature-entropy-anchors-1.md](feature-entropy-anchors-1.md)