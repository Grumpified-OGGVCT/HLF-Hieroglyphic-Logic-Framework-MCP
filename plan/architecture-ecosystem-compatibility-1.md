---
goal: Preserve one canonical packaged HLF MCP authority while building first-class host-application and ecosystem compatibility bridges
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [architecture, bridge, ecosystem, compatibility, mcp, javascript, java, go, rust]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines how the packaged HLF MCP surface should play well with major implementation ecosystems and host applications without fragmenting the meaning layer or spawning parallel authoritative runtimes. The canonical implementation authority remains the packaged Python MCP surface in `hlf_mcp/`. The compatibility program exists to make that full packaged authority reachable, maintainable, and transport-complete across JavaScript or TypeScript, Java, Go, Rust, editor hosts, agent shells, bot shells, and adjacent MCP-client ecosystems.

This is a bridge plan, not a claim that those bridges already exist. The target is disciplined reach: one canonical core, many first-class compatibility lanes, explicit transport parity, and an ongoing watch process so HLF keeps pace with upstream MCP SDK evolution rather than falling stale after a one-time scaffold.

## 1. Requirements & Constraints

- **REQ-001**: Keep the packaged `hlf_mcp/` MCP surface as the implementation authority for present-tense HLF behavior, not just the language core in isolation.
- **REQ-002**: Treat JavaScript or TypeScript, Java, Go, Rust, and similar ecosystems as first-class compatibility targets, not side notes.
- **REQ-003**: Support the same transport story across bridge surfaces wherever the underlying ecosystem can honestly support it: `stdio`, `sse`, and `streamable-http`.
- **REQ-004**: Prefer reference clients, launchers, adapters, or extension shells over duplicate HLF compilers or runtimes in other languages.
- **REQ-005**: Maintain a versioned compatibility matrix that records supported SDKs, tested transports, and known gaps per ecosystem.
- **REQ-006**: Track upstream MCP SDK changes so bridge surfaces can stay current with evolving protocol and SDK expectations.
- **REQ-007**: Keep claim-lane discipline explicit: planned compatibility work is `bridge-true` until code and tests exist in this repo.
- **REQ-008**: Preserve a deferred post-build integration-advisory lane for external host ecosystems and host applications that may want the packaged HLF MCP surface in full, or HLF plus additional MCP-host integration, with recommendations regenerated against then-current upstream repo reality rather than frozen from early bridge assumptions.
- **REQ-009**: Treat host-application adoption as a host-integration architecture, not as permission to flatten HLF into a few client helpers or to duplicate HLF authority inside host libraries.
- **REQ-010**: Keep example hosts such as LoLLMs explicitly subordinate to the broader target: many host applications should be able to carry the packaged MCP surface, not just one favored ecosystem.
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

### Implementation Phase 4A

- **GOAL-004A**: Preserve the deferred external-host integration advisory lane so the packaged HLF MCP surface can be recommended into many host applications from a stronger, more current build state.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016A | Record a post-build revisit lane for host-application integration patterns across editor hosts, bot shells, agent shells, coding shells, and adjacent MCP-capable ecosystems, with LoLLMs preserved as one concrete example lane. | ✅ | 2026-03-24 |
| TASK-016B | Keep the revisit question explicit: packaged HLF MCP adoption versus deeper host integration, with recommendations regenerated from the then-current packaged HLF truth and live upstream host-application repo shapes. | ✅ | 2026-03-24 |
| TASK-016C | Defer concrete implementation recommendations until the current HLF build is materially complete enough to give an up-to-date, working, test-backed integration lane instead of an early architectural sketch. | ✅ | 2026-03-24 |

### Implementation Phase 4B

- **GOAL-004B**: Preserve an honest end-state wiring model for how host applications would carry the packaged HLF MCP surface without becoming second HLF authorities.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-016D | Record the target boundary explicitly: host applications should act as operator hosts, model-runtime shells, MCP clients or registries, personality or workflow shells, and UX surfaces around HLF, while the packaged `hlf_mcp/` surface remains the canonical meaning, governance, routing, capsule, evidence, and audit authority. | ✅ | 2026-03-24 |
| TASK-016E | Record the likely end-state wiring: host UI, bot, editor, or personality entrypoints hand intent into HLF front-door tools, HLF resolves governed meaning and admission, host applications execute or broker tool and model lanes through their runtime surfaces, and operator-facing HLF evidence returns to those hosts for rendering rather than being reimplemented there. | ✅ | 2026-03-24 |
| TASK-016F | Keep the adoption modes separate in the plan: `HLF-as-MCP/service` for the safest near-term host integration, and `HLF-aware deeper host integration` for later lanes covering personalities, workflows, coding shells, bots, and internal orchestration once the packaged HLF build is stronger. | ✅ | 2026-03-24 |
| TASK-016G | Preserve LoLLMs as one concrete example host lane inside the broader host-application program rather than as the singular end-state target. | ✅ | 2026-03-24 |

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
- **ALT-005**: Collapse HLF into a specific host application's client-side wrappers or duplicate core logic inside host repos. Rejected because that would turn the host ecosystem into a second, drifting HLF authority.

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
- **FILE-006**: `/memories/repo/HLF_ECOSYSTEM_COMPATIBILITY_2026-03-19.md` — repo memory for deferred external-host revisit lanes

## 6. Testing

- **TEST-001**: Verify each bridge lane states tested versus untested transports explicitly.
- **TEST-002**: Add fixture-backed transport smoke coverage per ecosystem before claiming parity.
- **TEST-003**: Verify compatibility tables stay aligned with actual bridge scaffolds and proofs.
- **TEST-004**: Verify bridge surfaces preserve packaged governance and health semantics rather than inventing divergent conventions.

## 7. Risks & Assumptions

- **RISK-001**: Cross-language enthusiasm can turn into duplicate-authority sprawl if bridge boundaries are not enforced.
- **RISK-002**: Upstream MCP SDK churn can make bridges stale quickly without an explicit watch process.
- **RISK-003**: Transport parity can be overstated if attach and health semantics are not validated in each ecosystem.
- **RISK-004**: Early external integration recommendations can age badly while HLF is still actively changing, so deferred advisory lanes must be refreshed from live repo truth before promotion.
- **RISK-005**: Host-rich ecosystems can blur responsibility boundaries unless the plan keeps HLF authority, host duties, and MCP-versus-deeper-integration lanes explicit.
- **ASSUMPTION-001**: The official MCP SDK ecosystems for JS/TS, Java, Go, and Rust are the right first compatibility lanes because they can meet the transport and operator-host goals without redefining HLF.
- **ASSUMPTION-002**: The VS Code extension is the first concrete bridge lane, not the last one.
- **ASSUMPTION-003**: The strongest eventual host-application adoption path is likely HLF-hosted governance plus host-managed UX, personalities, tool shells, and model backends, rather than a full transplant of HLF internals into client libraries.

## 8. Related Specifications / Further Reading

[plan/architecture-vscode-extension-bridge-1.md](../plan/architecture-vscode-extension-bridge-1.md)
[docs/HLF_CLAIM_LANES.md](../docs/HLF_CLAIM_LANES.md)
[HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)
[hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md](../hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md)