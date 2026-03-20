---
goal: Preserve one canonical HLF core while building first-class ecosystem compatibility bridges
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [architecture, bridge, ecosystem, compatibility, mcp, javascript, java, go, rust]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines how HLF should play well with major implementation ecosystems without fragmenting the meaning layer or spawning parallel authoritative runtimes. The canonical HLF implementation authority remains the packaged Python MCP surface in `hlf_mcp/`. The compatibility program exists to make that authority reachable, maintainable, and transport-complete across JavaScript or TypeScript, Java, Go, Rust, and adjacent MCP-client ecosystems.

This is a bridge plan, not a claim that those bridges already exist. The target is disciplined reach: one canonical core, many first-class compatibility lanes, explicit transport parity, and an ongoing watch process so HLF keeps pace with upstream MCP SDK evolution rather than falling stale after a one-time scaffold.

## 1. Requirements & Constraints

- **REQ-001**: Keep the packaged `hlf_mcp/` server as the implementation authority for present-tense HLF behavior.
- **REQ-002**: Treat JavaScript or TypeScript, Java, Go, Rust, and similar ecosystems as first-class compatibility targets, not side notes.
- **REQ-003**: Support the same transport story across bridge surfaces wherever the underlying ecosystem can honestly support it: `stdio`, `sse`, and `streamable-http`.
- **REQ-004**: Prefer reference clients, launchers, adapters, or extension shells over duplicate HLF compilers or runtimes in other languages.
- **REQ-005**: Maintain a versioned compatibility matrix that records supported SDKs, tested transports, and known gaps per ecosystem.
- **REQ-006**: Track upstream MCP SDK changes so bridge surfaces can stay current with evolving protocol and SDK expectations.
- **REQ-007**: Keep claim-lane discipline explicit: planned compatibility work is `bridge-true` until code and tests exist in this repo.
- **SEC-001**: Cross-language bridges must not bypass packaged governance, capsule, approval, or audit boundaries.
- **SEC-002**: Secrets and provider credentials must stay in ecosystem-native secret stores or environment variables, not hardcoded demo configs.
- **ARC-001**: One canonical HLF core; no parallel language-specific authorities.
- **ARC-002**: Ecosystem bridges must improve reach and maintainability without flattening HLF into a generic MCP wrapper.
- **CON-001**: Do not overclaim parity for a language bridge until transport, launch, and health behavior have been tested.
- **CON-002**: Do not let reference bridge convenience outrank proof work in routing, verification, governance, and evidence pillars.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Establish the compatibility program as an explicit bridge lane with bounded claims.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Classify cross-language compatibility as `bridge-true`: one canonical packaged HLF core with many ecosystem bridges. | ✅ | 2026-03-19 |
| TASK-002 | Record the current packaged truth boundary: `hlf_mcp/server.py` already exposes `stdio`, `sse`, and `streamable-http`; other ecosystems do not yet have first-class repo bridges. | ✅ | 2026-03-19 |
| TASK-003 | Create and maintain this plan as the compatibility program authority for JS/TS, Java, Go, Rust, and adjacent ecosystems. | ✅ | 2026-03-19 |
| TASK-004 | Define a compatibility matrix document or generated report for bridge inventory, tested SDK version, supported transports, and known gaps. |  |  |

### Implementation Phase 2

- **GOAL-002**: Define the shared bridge contract that every ecosystem surface must follow.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Specify common bridge requirements: launch or attach modes, transport selection, health semantics, endpoint semantics, evidence visibility, and failure diagnostics. |  |  |
| TASK-006 | Define how reference bridges consume packaged metadata from `server.json`, packaged docs, or generated inventories without drifting into manual duplication. |  |  |
| TASK-007 | Define compatibility-lane documentation rules so each bridge states what is scaffolded, tested, and not yet proven. |  |  |
| TASK-008 | Define a protocol-watch workflow that records upstream MCP SDK changes relevant to JS/TS, Java, Go, Rust, Python, and editor hosts. |  |  |

### Implementation Phase 3

- **GOAL-003**: Deliver the first bridge lane in the JavaScript or TypeScript ecosystem.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Use `extensions/hlf-vscode/` as the first operator-shell bridge in the JS/TS ecosystem. |  |  |
| TASK-010 | Add a reference JS/TS launcher or client surface that can manage `stdio`, `sse`, and `streamable-http` against the packaged HLF server. |  |  |
| TASK-011 | Define a JS/TS compatibility checklist for Node runtime, VS Code host expectations, HTTP health checks, and packaging. |  |  |
| TASK-012 | Add validation coverage that proves transport selection and diagnostics behave as documented. |  |  |

### Implementation Phase 4

- **GOAL-004**: Create explicit bridge plans for Go, Java, and Rust without creating duplicate authorities.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Define a Go reference bridge using the official Go MCP SDK as a launcher, attach client, or integration test harness rather than as a new HLF authority. |  |  |
| TASK-014 | Define a Java reference bridge using the official Java MCP SDK with the same transport and health expectations. |  |  |
| TASK-015 | Define a Rust reference bridge using the rmcp ecosystem with the same transport and health expectations. |  |  |
| TASK-016 | Add per-language support tables covering status, SDK lineage, transport support, and proof level. |  |  |

### Implementation Phase 5

- **GOAL-005**: Operationalize ongoing compatibility maintenance instead of one-off scaffolds.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Add a recurring compatibility review that checks upstream SDK drift, protocol changes, and broken transport assumptions. |  |  |
| TASK-018 | Add fixture-based smoke probes per ecosystem so compatibility claims stay test-backed. |  |  |
| TASK-019 | Tie compatibility updates into operator docs, build notes, and weekly evidence when the bridges become real. |  |  |
| TASK-020 | Define promotion gates from planned bridge to accepted bridge: scaffold exists, transport matrix implemented, health diagnostics verified, docs aligned. |  |  |

## 3. Alternatives

- **ALT-001**: Reimplement HLF core behavior separately in each language. Rejected because it fractures the meaning layer and multiplies canonicality drift.
- **ALT-002**: Ignore non-Python ecosystems until the entire north-star is finished. Rejected because adoption reach and operator accessibility are explicit goals now, not distant cleanup.
- **ALT-003**: Support only one language bridge, such as VS Code, and call the problem solved. Rejected because the goal is ongoing compatibility with major ecosystems, not one editor surface.
- **ALT-004**: Expose only stdio in bridge planning. Rejected because the packaged server already ships real HTTP transports and the user explicitly elevated them to must-have adoption surfaces.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/server.py`
- **DEP-002**: `server.json`
- **DEP-003**: `.vscode/mcp.json`
- **DEP-004**: `plan/architecture-vscode-extension-bridge-1.md`
- **DEP-005**: `docs/HLF_CLAIM_LANES.md`
- **DEP-006**: `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`

## 5. Files

- **FILE-001**: `plan/architecture-ecosystem-compatibility-1.md` — canonical compatibility bridge plan
- **FILE-002**: `plan/architecture-vscode-extension-bridge-1.md` — first detailed JS/TS bridge lane
- **FILE-003**: `HLF_ACTIONABLE_PLAN.md` — broader workstream alignment
- **FILE-004**: `HLF_MCP_TODO.md` — active reconstruction backlog
- **FILE-005**: `TODO.md` — top-level priorities

## 6. Testing

- **TEST-001**: Verify each bridge lane states tested versus untested transports explicitly.
- **TEST-002**: Add fixture-backed transport smoke coverage per ecosystem before claiming parity.
- **TEST-003**: Verify compatibility tables stay aligned with actual bridge scaffolds and proofs.
- **TEST-004**: Verify bridge surfaces preserve packaged governance and health semantics rather than inventing divergent conventions.

## 7. Risks & Assumptions

- **RISK-001**: Cross-language enthusiasm can turn into duplicate-authority sprawl if bridge boundaries are not enforced.
- **RISK-002**: Upstream MCP SDK churn can make bridges stale quickly without an explicit watch process.
- **RISK-003**: Transport parity can be overstated if attach and health semantics are not validated in each ecosystem.
- **ASSUMPTION-001**: The official MCP SDK ecosystems for JS/TS, Java, Go, and Rust are the right first compatibility lanes because they can meet the transport and operator-host goals without redefining HLF.
- **ASSUMPTION-002**: The VS Code extension is the first concrete bridge lane, not the last one.

## 8. Related Specifications / Further Reading

[plan/architecture-vscode-extension-bridge-1.md](../plan/architecture-vscode-extension-bridge-1.md)
[docs/HLF_CLAIM_LANES.md](../docs/HLF_CLAIM_LANES.md)
[HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)
[hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md](../hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md)