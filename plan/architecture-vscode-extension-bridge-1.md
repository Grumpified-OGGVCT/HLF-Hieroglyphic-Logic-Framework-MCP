---
goal: Package HLF as a governed VS Code extension bridge without flattening the MCP product surface
version: 1.0
date_created: 2026-03-19
last_updated: 2026-03-19
owner: GitHub Copilot
status: 'Planned'
tags: [architecture, vscode, extension, mcp, operator, gui, bridge]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines the bridge from the current packaged HLF MCP surface into a first-class VS Code extension and operator shell path. The target is not "an editor plugin because that looks tidy." The target is a governed extension surface that can launch the packaged MCP server, expose the right configurable settings, support multiple transports and use modes honestly, and provide a future home for operator-facing GUI panels without overstating current maturity.

HTTP transport protocols are a non-negotiable part of that target. `stdio` remains the first credible local build-assist lane, but SSE and streamable HTTP are must-have adoption surfaces for remote, containerized, attached-server, and broader ecosystem use.

Current truth already includes the raw ingredients for this bridge:

- local workspace MCP wiring in `.vscode/mcp.json`
- MCP distribution metadata in `server.json`
- packaged transports in `hlf_mcp/server.py`
- bridge-lane GUI notes in `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md`

What does not yet exist is a packaged VS Code extension surface with manifest, commands, settings, views, packaging pipeline, and publish discipline.

## 1. Requirements & Constraints

- **REQ-001**: The extension must treat the packaged `hlf_mcp/` MCP server as the authority rather than reimplementing HLF behavior in TypeScript.
- **REQ-002**: The extension must support all three packaged transport modes: `stdio`, `sse`, and `streamable-http`.
- **REQ-003**: HTTP transport protocols are must-have bridge requirements, not optional future niceties: the extension must treat SSE and streamable HTTP as first-class launch or attach paths.
- **REQ-004**: The extension must provide operator-facing configuration for transport, command path, working directory, environment variables, and evidence directories.
- **REQ-005**: The extension must expose the packaged MCP surface through standard VS Code affordances: commands, settings, views or webviews, walkthroughs, status reporting, and diagnostics where appropriate.
- **REQ-006**: The extension must preserve governed trust surfaces such as audit, route rationale, verifier outputs, memory provenance, and build evidence rather than hiding them behind a generic chat shell.
- **REQ-007**: The extension must distinguish current-truth capabilities from bridge or vision capabilities in its UI and wording.
- **REQ-008**: The extension path must support local developer install, offline VSIX distribution, and Marketplace publication.
- **REQ-009**: The extension must be able to host richer operator GUI surfaces later without forcing the current repo to ship a separate desktop app first.
- **SEC-001**: Secrets, tokens, and host credentials must live in VS Code secret storage or operator-managed environment variables, not plain settings.
- **SEC-002**: Extension commands must not silently widen execution authority beyond the packaged HLF capsule, ALIGN, and approval boundaries.
- **SEC-003**: Any webview or view surface must show governed evidence and explicit transport state rather than opaque "success" banners.
- **ARC-001**: This is a bridge-lane packaging plan. It must not claim that the full operator GUI or full VS Code extension already exists.
- **ARC-002**: The extension should be a sidecar over the packaged server and evidence surfaces, not a separate competing implementation line.
- **CON-001**: Do not build an extension that hardcodes only one MCP client path or collapses HLF into a stdio-only story when the packaged product already has real HTTP transports.
- **CON-002**: Do not treat VS Code presence as equivalent to full operator-surface completion.
- **CON-003**: Prefer generated inventories from packaged MCP metadata over manually duplicated tool or resource claims.

## 2. Context Map

### Files to Modify Later

| File | Purpose | Changes Needed |
|------|---------|----------------|
| `.vscode/mcp.json` | current workspace-local MCP bootstrap | keep aligned with canonical stdio launch command during bridge work |
| `server.json` | MCP distribution metadata | extend or validate as authoritative distribution manifest for extension bootstrap |
| `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` | operator GUI direction | reconcile extension-hosted GUI and view surfaces with this bridge plan |
| `hlf_mcp/server.py` | packaged MCP runtime and transports | expose any extra health or status surfaces the extension needs |
| `hlf_mcp/server_resources.py` | queryable status and trust resources | add extension-facing resources only when backed by packaged authority |
| `README.md` | current-truth product framing | add extension lane only after scaffold exists |

### Files to Create Later

| File | Purpose |
|------|---------|
| `extensions/hlf-vscode/package.json` | extension manifest with commands, configuration, views, and publish metadata |
| `extensions/hlf-vscode/src/extension.ts` | activation, server launch orchestration, commands, and status surfaces |
| `extensions/hlf-vscode/src/config.ts` | typed settings and migration helpers |
| `extensions/hlf-vscode/src/mcpLauncher.ts` | stdio and HTTP launch or attach logic |
| `extensions/hlf-vscode/src/views/*` | tree views or webview providers for operator surfaces |
| `extensions/hlf-vscode/.vscode/launch.json` | extension host debugging |
| `extensions/hlf-vscode/README.md` | extension-specific installation and capability guide |
| `extensions/hlf-vscode/.github/workflows/*` | VSIX package validation and publication pipeline |

### Dependencies

| File | Relationship |
|------|--------------|
| `server.json` | distribution metadata input for extension bootstrap and publishing discipline |
| `docs/HLF_MCP_AGENT_HANDOFF.md` | packaged-server truth boundary the extension must respect |
| `docs/HLF_CLAIM_LANES.md` | wording discipline for UI labels and extension docs |
| `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` | operator-surface recovery guidance |
| `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` | future GUI reference for views and webviews |

## 3. Target State

The target extension surface should make HLF usable in four honest modes:

1. **Workspace-local MCP mode**: launch the packaged HLF MCP server in `stdio` using the repo checkout or installed package.
2. **Attached HTTP server mode**: connect to a running SSE or streamable-HTTP HLF endpoint for remote, containerized, or sidecar-managed setups.
3. **Operator shell mode**: expose governed commands, evidence views, status panels, and trust summaries inside VS Code.
4. **Future GUI-host mode**: embed richer webview-based operator panels that reuse packaged resources and machine-readable evidence.

The extension should provide one adoption lane for broad reach while keeping each mode explicit:

- local developer use through unpacked extension host
- packaged `.vsix` distribution for controlled environments
- Marketplace publication for broad discoverability
- optional repo-local MCP wiring for immediate bootstrap before the full extension exists

## 4. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define canonical extension scope, ownership boundaries, and mandatory transport requirements.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Classify the extension path as `bridge-true`: a sidecar over packaged MCP, not a separate HLF implementation. | ✅ | 2026-03-19 |
| TASK-002 | Record the current-truth bootstrap surfaces: `.vscode/mcp.json`, `server.json`, packaged transports, and GUI draft references. | ✅ | 2026-03-19 |
| TASK-003 | Define the extension repository boundary under a dedicated folder such as `extensions/hlf-vscode/` so Node tooling does not pollute packaged Python authority. | ✅ | 2026-03-19 |
| TASK-004 | Define a transport matrix covering `stdio`, `sse`, and `streamable-http`, with HTTP explicitly recorded as must-have and lane-qualified wording for proof claims. | ✅ | 2026-03-19 |

### Implementation Phase 2

- **GOAL-002**: Scaffold the extension manifest and operator configuration layer.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `extensions/hlf-vscode/package.json` with `engines.vscode`, publisher metadata, command contributions, configuration schema, view containers, and activation events. | ✅ | 2026-03-19 |
| TASK-006 | Add settings for server command, transport, host, port, cwd, env overrides, evidence directory, launch profile selection, and HTTP health or endpoint targeting where needed. | ✅ | 2026-03-19 |
| TASK-007 | Define secret-handling rules using VS Code secret storage for tokens or operator credentials. | ✅ | 2026-03-20 |
| TASK-008 | Add a walkthrough and first-run validation command that verifies the configured HLF server path and transport. | ✅ | 2026-03-20 |

### Implementation Phase 3

- **GOAL-003**: Implement MCP launch and attach flows.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Implement stdio launch against the packaged HLF entrypoint and validate health or handshake readiness before marking the extension ready. |  |  |
| TASK-010 | Implement launched or attached HTTP flows for SSE and streamable-HTTP with explicit operator-visible transport state, health checks, and failure diagnostics. | ✅ | 2026-03-19 |
| TASK-011 | Add commands for start, stop, restart, attach, open health, and copy connection details. | ✅ | 2026-03-19 |
| TASK-012 | Persist transport diagnostics and failure reasons in a user-visible status channel rather than hiding them in logs. | ✅ | 2026-03-19 |

### Implementation Phase 4

- **GOAL-004**: Expose governed operator surfaces inside VS Code.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Add a tree or dashboard surface for transport state, server status, evidence freshness, and registered tool or resource summaries. | ✅ | 2026-03-19 |
| TASK-014 | Add command surfaces for `hlf_do`, test suite summary, weekly evidence, profile catalog, and trust resources that already exist in packaged truth. | ✅ | 2026-03-20 |
| TASK-015 | Add a webview or view layer for audit output, route rationale, verifier results, and memory provenance using packaged machine-readable outputs. | ✅ | 2026-03-20 |
| TASK-016 | Surface claim-lane context in the extension UI so operators can distinguish current packaged truth from bridge targets. | ✅ | 2026-03-20 |

### Implementation Phase 5

- **GOAL-005**: Package, sign, and publish the extension responsibly.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Add build scripts for compile, test, package, and prepublish using standard VS Code extension packaging. | ✅ | 2026-03-20 |
| TASK-018 | Add `.vsix` packaging validation with `vsce package` and platform-targeted packaging where needed. | ✅ | 2026-03-20 |
| TASK-019 | Document publisher identity, Marketplace publication, and offline VSIX install paths. | ✅ | 2026-03-20 |
| TASK-020 | Define what "signed and publishable" means in practice for this repo: Marketplace integrity, publisher verification, and reproducible VSIX output. | ✅ | 2026-03-20 |

### Implementation Phase 6

- **GOAL-006**: Connect the extension bridge to the larger operator-shell roadmap.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-021 | Reconcile `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` with an extension-hosted webview strategy instead of a separate speculative GUI story. |  |  |
| TASK-022 | Define which operator panels are current-truth extension surfaces versus bridge-lane placeholders. |  |  |
| TASK-023 | Bind extension views to weekly evidence, trust surfaces, and claim-lane docs so the operator shell remains auditable. |  |  |
| TASK-024 | Add acceptance tests for local launch, attached transports, settings migration, and operator-trust view rendering. | ✅ | 2026-03-20 |

## 5. Alternatives

- **ALT-001**: Keep only repo-local `.vscode/mcp.json` wiring. Rejected because it helps local bootstrap but does not create a distributable extension surface.
- **ALT-002**: Build a standalone desktop GUI first. Rejected because the repo already has a natural adoption path through VS Code and MCP before a separate app is justified.
- **ALT-003**: Publish a thin extension that only opens a webview and proxies arbitrary requests. Rejected because it would hide governed trust surfaces and duplicate logic poorly.
- **ALT-004**: Treat streamable-HTTP as the default proof lane for the extension. Rejected because the repo doctrine keeps local `stdio` as the first fully credible build-assist lane.
- **ALT-005**: Treat HTTP transports as optional afterthoughts behind a stdio-only extension shell. Rejected because maximum reach and adaptability require first-class HTTP adoption paths and the packaged server already ships them.

## 6. Dependencies

- **DEP-001**: `server.json`
- **DEP-002**: `.vscode/mcp.json`
- **DEP-003**: `hlf_mcp/server.py`
- **DEP-004**: `hlf_mcp/server_resources.py`
- **DEP-005**: `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md`
- **DEP-006**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- **DEP-007**: `docs/HLF_CLAIM_LANES.md`
- **DEP-008**: `docs/HLF_MCP_AGENT_HANDOFF.md`

## 7. Files

- **FILE-001**: `plan/architecture-vscode-extension-bridge-1.md` — canonical bridge plan for the extension path
- **FILE-002**: `.vscode/mcp.json` — current local MCP bootstrap surface
- **FILE-003**: `server.json` — current MCP distribution metadata
- **FILE-004**: `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` — operator GUI bridge note
- **FILE-005**: `HLF_MCP_TODO.md` — active reconstruction backlog
- **FILE-006**: `TODO.md` — top-level project tracking backlog

## 8. Testing

- **TEST-001**: Verify local extension-host launch can start the packaged HLF server in `stdio` and detect readiness.
- **TEST-002**: Verify launched and attached SSE and streamable-HTTP configurations validate host, port, endpoint, and health or handshake state correctly.
- **TEST-003**: Verify extension settings round-trip and migrate without losing transport or evidence configuration.
- **TEST-004**: Verify operator views render packaged evidence and trust summaries without inventing state.
- **TEST-005**: Verify VSIX packaging and prepublish tasks succeed in CI before Marketplace publication.

## 9. Risks & Assumptions

- **RISK-001**: A VS Code extension can easily overclaim maturity if the UI implies full operator-shell completion before the packaged surfaces exist.
- **RISK-002**: Supporting multiple transport modes can create ambiguous troubleshooting unless transport state is explicit and first-class.
- **RISK-005**: If HTTP support is treated as secondary in the extension shell, the repo will underdeliver on the stated adaptability and distribution goal despite already having packaged HTTP transports.
- **RISK-003**: If the extension duplicates package metadata manually, tool or resource counts will drift from packaged truth.
- **RISK-004**: A webview-first design can become decorative if it does not remain anchored to machine-readable evidence outputs.
- **ASSUMPTION-001**: VS Code is the right first operator-shell host because the repo already uses MCP, workspace settings, and developer-facing evidence loops.
- **ASSUMPTION-002**: Marketplace distribution plus offline VSIX packaging provides enough reach before any separate installer or desktop shell is warranted.

## 10. Related Specifications / Further Reading

[docs/HLF_GUI_BUILD_GUIDE_DRAFT.md](../docs/HLF_GUI_BUILD_GUIDE_DRAFT.md)
[docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md](../docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md)
[docs/HLF_MCP_AGENT_HANDOFF.md](../docs/HLF_MCP_AGENT_HANDOFF.md)
[docs/HLF_CLAIM_LANES.md](../docs/HLF_CLAIM_LANES.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)