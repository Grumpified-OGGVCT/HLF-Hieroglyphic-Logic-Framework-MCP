---
goal: Implement transcript-backed entropy anchors as a packaged anti-drift bridge surface for HLF operator trust
version: 1.0
date_created: 2026-03-18
last_updated: 2026-03-18
owner: GitHub Copilot
status: 'Planned'
tags: [feature, planning, entropy-anchors, insaits, governance, audit, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines the first transcript-backed implementation slice after the pointer-trust and HKS work: packaged entropy anchors. The purpose of entropy anchors is to detect semantic drift or hidden private dialect formation by forcing periodic proof-of-meaning against the existing packaged human-readable translation surfaces.

The implementation target is bridge-lane work. It must reuse packaged truth where possible and must not claim that the full Sovereign daemon stack already exists locally.

## 1. Requirements & Constraints

- **REQ-001**: Entropy anchors must build on current packaged surfaces rather than assume the larger Sovereign daemon stack is present.
- **REQ-002**: The feature must compare symbolic intent against an independent packaged human-readable translation path.
- **REQ-003**: The feature must be able to run as a deterministic governance check or audit event, not only as prose documentation.
- **REQ-004**: The initial slice must be operator-legible and testable without requiring a GUI or SOC dashboard.
- **REQ-005**: The initial slice must produce structured audit records that can be consumed later by richer witness, routing, or observability systems.
- **SEC-001**: Safety evaluation must remain deterministic where possible; no LLM should decide whether the system is safe to continue.
- **SEC-002**: A semantic-mismatch threshold must fail closed for high-risk execution paths and fail open only where the policy explicitly allows advisory mode.
- **ARC-001**: The packaged truth boundary remains `hlf_mcp/`; any upstream daemon logic is source-only context unless explicitly ported.
- **ARC-002**: The first slice is anti-drift enforcement, not a full InsAIts V2 daemon recreation.
- **CON-001**: Do not import the full `hlf_source/agents/core/daemons/insaits_daemon.py` as-is.
- **CON-002**: Do not invent new public guarantees that are not covered by tests and packaged docs.
- **GUD-001**: Reuse existing `insaits.decompile(...)`, bytecode decompile, and similarity-gate logic before adding new translation primitives.
- **PAT-001**: The packaged execution path should be: symbolic source or AST -> independent packaged translation -> similarity evaluation -> structured audit record -> policy decision.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Add a packaged entropy-anchor core that can evaluate semantic alignment for a single source/AST execution unit.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add a new packaged helper module under `hlf_mcp/hlf/` such as `entropy_anchor.py` that defines the entropy-anchor evaluation contract, threshold handling, and structured result schema. |  |  |
| TASK-002 | Reuse `hlf_mcp/hlf/insaits.py` decompilation and similarity-gate behavior as the independent translation path for the first slice. |  |  |
| TASK-003 | Define one structured result schema containing at minimum: `status`, `similarity_score`, `threshold`, `source_hash`, `translation_summary`, `drift_detected`, and `policy_action`. |  |  |
| TASK-004 | Add deterministic threshold constants and policy modes (`advisory`, `enforce`, `high_risk_enforce`) in the packaged helper instead of scattering them across tools. |  |  |

### Implementation Phase 2

- **GOAL-002**: Expose entropy-anchor checks through packaged runtime and MCP-adjacent surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Extend `hlf_mcp/server_capsule.py` or the most appropriate packaged server module with an MCP tool that evaluates entropy anchors for provided HLF source or AST. |  |  |
| TASK-006 | Add an optional packaged runtime hook in `hlf_mcp/hlf/runtime.py` so high-risk or policy-marked execution paths can trigger entropy-anchor evaluation before destructive execution. |  |  |
| TASK-007 | Route entropy-anchor results into `hlf_mcp/hlf/audit_chain.py` so every check produces a structured traceable event. |  |  |
| TASK-008 | Ensure policy outcomes are explicit: `allow`, `warn`, `halt_branch`, or `escalate_hitl`. |  |  |

### Implementation Phase 3

- **GOAL-003**: Add operator-legible docs and tests for the packaged entropy-anchor surface.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Add a focused regression file such as `tests/test_entropy_anchor.py` covering aligned, mismatched, and threshold-edge cases. |  |  |
| TASK-010 | Add integration coverage to `tests/test_fastmcp_frontdoor.py` if a new MCP tool is added to the packaged server surface. |  |  |
| TASK-011 | Update `docs/HLF_REPO_IMPLEMENTATION_MAP.md` or a targeted bridge note to record entropy anchors as a new partial packaged trust surface once implemented. |  |  |
| TASK-012 | Update `SSOT_HLF_MCP.md` only after tests and server surface validation confirm the feature is real. |  |  |

## 3. Alternatives

- **ALT-001**: Import the upstream InsAIts daemon wholesale. Rejected because this repo needs a minimal packaged bridge slice first.
- **ALT-002**: Treat entropy anchors as documentation-only guidance. Rejected because the mechanism is specifically about enforceable anti-drift behavior.
- **ALT-003**: Let an LLM judge whether semantic drift is acceptable. Rejected because the feature is a trust boundary and must be deterministic at the policy layer.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/hlf/insaits.py`
- **DEP-002**: `hlf_mcp/hlf/runtime.py`
- **DEP-003**: `hlf_mcp/hlf/audit_chain.py`
- **DEP-004**: `hlf_mcp/server_capsule.py`
- **DEP-005**: `tests/test_insaits.py`
- **DEP-006**: `docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md`

## 5. Files

- **FILE-001**: `hlf_mcp/hlf/entropy_anchor.py` — new packaged entropy-anchor helper
- **FILE-002**: `hlf_mcp/hlf/insaits.py` — existing independent translation and similarity path to reuse
- **FILE-003**: `hlf_mcp/hlf/runtime.py` — optional runtime policy trigger point
- **FILE-004**: `hlf_mcp/hlf/audit_chain.py` — structured audit event sink
- **FILE-005**: `hlf_mcp/server_capsule.py` — packaged MCP-facing exposure point
- **FILE-006**: `tests/test_entropy_anchor.py` — new regression coverage
- **FILE-007**: `tests/test_fastmcp_frontdoor.py` — server-surface count/update if needed

## 6. Testing

- **TEST-001**: Verify aligned source returns `drift_detected = false` and `policy_action = allow`.
- **TEST-002**: Verify forced mismatches return `drift_detected = true` with deterministic threshold data.
- **TEST-003**: Verify high-risk policy mode can halt the branch or escalate to HITL when similarity falls below threshold.
- **TEST-004**: Verify every entropy-anchor evaluation produces an audit-chain event.
- **TEST-005**: Run targeted regressions: `uv run pytest tests/test_insaits.py tests/test_entropy_anchor.py tests/test_fastmcp_frontdoor.py -q --tb=short`.

## 7. Risks & Assumptions

- **RISK-001**: Similarity-gate heuristics may be too weak or too brittle for some classes of symbolic programs.
- **RISK-002**: Overuse of entropy anchors on low-risk flows could add friction without meaningful safety improvement.
- **RISK-003**: The first packaged slice may overfit to translation/decompilation paths and underrepresent richer future daemon behavior.
- **ASSUMPTION-001**: Existing packaged InsAIts and similarity-gate surfaces are stable enough to reuse.
- **ASSUMPTION-002**: High-risk policy modes can initially be limited to explicit opt-in or capsule policy hooks.

## 8. Related Specifications / Further Reading

[docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md](../docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md)
[docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md](../docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md)
[docs/HLF_REPO_IMPLEMENTATION_MAP.md](../docs/HLF_REPO_IMPLEMENTATION_MAP.md)
[docs/HLF_MISSING_PILLARS.md](../docs/HLF_MISSING_PILLARS.md)
[plan/architecture-hlf-reconstruction-2.md](architecture-hlf-reconstruction-2.md)