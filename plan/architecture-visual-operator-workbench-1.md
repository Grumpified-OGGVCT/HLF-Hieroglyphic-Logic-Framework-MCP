---
goal: Define a visual operator workbench for HLF that makes intent, execution, and governance visible without overstating current UI maturity
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'Planned'
tags: [architecture, gui, vscode, operator, visualization, debugging, bridge]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a visual operator workbench for HLF. The target is not a separate decorative GUI. The target is an extension-hosted operator workbench that makes HLF intent structure, execution flow, capsule boundaries, verifier state, and audit evidence legible to humans. The correct host for the first serious version is the existing VS Code extension bridge and operator-shell path, not a fresh standalone desktop surface.

## 1. Requirements & Constraints

- **REQ-001**: Treat the packaged Python server and its resources as the implementation authority; visualization must consume packaged machine-readable outputs rather than duplicating logic in UI code.
- **REQ-002**: Support live intent visualization across at least three synchronized surfaces: authored HLF text, canonical AST structure, and human-readable explanation.
- **REQ-003**: Expose governance state visibly: capsule tier, denied or admitted capability paths, ALIGN results, verifier results, and trust-lane context.
- **REQ-004**: Stage execution visualization in increasing order of proof: current packaged status and evidence first, richer step traces and time-travel only after trace artifacts exist.
- **REQ-005**: Keep claim-lane visibility explicit so the UI distinguishes current packaged truth, bridge work, and target-state aspirations.
- **REQ-006**: Make the workbench useful for both debugging and teaching: show why code is valid, denied, or risky rather than only rendering pretty graphs.
- **SEC-001**: No visualization surface may imply that denied actions, verifier failures, or bridge-only capabilities are admitted just because they are visible.
- **SEC-002**: Time-travel or replay surfaces must use explicit trace artifacts and never synthesize fake runtime state.
- **ARC-001**: The first serious host is `extensions/hlf-vscode/` plus packaged resources and trust surfaces.
- **CON-001**: Do not frame this as already-built product truth.
- **CON-002**: Do not build a second execution engine in TypeScript for the sake of visualization.
- **GUD-001**: Prefer visualizations backed by resource endpoints, AST data, and recorded evidence before adding bespoke interactive metaphors.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Classify which parts of the wishlist are current seams, bridge work, or later-stage work.

- **TASK-001**: Bind live glyph and intent visualization to existing compiler, grammar, formatter, and explainer outputs rather than treating it as a free-floating renderer. Completed: No. Date: N/A.
- **TASK-002**: Classify execution flow visualization as bridge work that depends on richer packaged trace outputs. Completed: No. Date: N/A.
- **TASK-003**: Classify time-travel debugging as later-stage bridge work gated on authoritative step trace or replay artifacts. Completed: No. Date: N/A.

### Implementation Phase 2

- **GOAL-002**: Define the machine-readable visualization substrate.

- **TASK-004**: Define the packaged data contract for intent graphs, AST summaries, governance panels, and execution-state summaries. Completed: No. Date: N/A.
- **TASK-005**: Add or extend packaged resources for route evidence, verifier results, memory provenance, and any future execution trace summaries. Completed: No. Date: N/A.
- **TASK-006**: Reconcile the workbench data contract with `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` and the operator-surface taxonomy in `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`. Completed: No. Date: N/A.

### Implementation Phase 3

- **GOAL-003**: Implement the first operator workbench slice inside the VS Code extension bridge.

- **TASK-007**: Add a webview or panel in `extensions/hlf-vscode/` that renders authored HLF, glyph projection, AST structure, and human-readable explanation side by side. Completed: No. Date: N/A.
- **TASK-008**: Add governance visibility panels showing capsule state, ALIGN checks, verifier state, and claim-lane status from packaged resources. Completed: No. Date: N/A.
- **TASK-009**: Add execution and evidence panels that visualize current packaged runtime summaries without inventing missing step traces. Completed: No. Date: N/A.
- **TASK-009A**: Bind any future operator boot asset, including the local-only `Genesis Wave` placeholder recorded in `docs/HLF_OPERATOR_BOOT_ASSET_MANIFEST.md`, to explicit bridge-only claim-lane labeling, silent-mode support, text fallback, and extension-hosted initialization states before any packaged playback or bundling claim is made. Completed: No. Date: N/A.

### Implementation Phase 4

- **GOAL-004**: Stage richer debugging and replay only when proof artifacts exist.

- **TASK-010**: Define the authoritative step-trace schema required before any time-travel debugger claim is made. Completed: No. Date: N/A.
- **TASK-011**: Add replay or state-timeline panels only after packaged trace artifacts, gas state, and Merkle or audit progression can be surfaced faithfully. Completed: No. Date: N/A.
- **TASK-012**: Add acceptance tests proving the rendered execution view matches structured trace authority and does not invent state. Completed: No. Date: N/A.

## 3. Alternatives

- **ALT-001**: Build a standalone desktop GUI first. Rejected because the extension bridge and packaged operator resources already provide the correct initial host.
- **ALT-002**: Limit the work to static screenshots or docs. Rejected because the wishlist value comes from interactive debugging and teaching, not only marketing imagery.
- **ALT-003**: Implement time-travel immediately with synthetic UI state. Rejected because it would overclaim runtime evidence that the package does not yet produce.

## 4. Dependencies

- **DEP-001**: `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md`
- **DEP-002**: `plan/architecture-vscode-extension-bridge-1.md`
- **DEP-003**: `extensions/hlf-vscode/README.md`
- **DEP-004**: `hlf_mcp/server_resources.py`
- **DEP-005**: `hlf_mcp/hlf/compiler.py`
- **DEP-006**: `hlf_mcp/hlf/insaits.py`

## 5. Files

- **FILE-001**: `plan/architecture-visual-operator-workbench-1.md`
- **FILE-002**: `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md`
- **FILE-003**: `plan/architecture-vscode-extension-bridge-1.md`
- **FILE-004**: `extensions/hlf-vscode/README.md`
- **FILE-005**: `extensions/hlf-vscode/src/*`
- **FILE-006**: `hlf_mcp/server_resources.py`

## 6. Testing

- **TEST-001**: Add UI or renderer tests proving AST and glyph visualizations remain grounded in packaged compiler outputs.
- **TEST-002**: Add tests proving governance panels match packaged resource values and claim-lane state.
- **TEST-003**: Add future replay tests only after step-trace artifacts exist.

## 7. Risks & Assumptions

- **RISK-001**: Visualization can quickly overclaim maturity if bridge-only concepts are rendered like shipped product truth.
- **RISK-002**: Time-travel debugging will be misleading if added before authoritative trace capture exists.
- **ASSUMPTION-001**: The existing VS Code bridge is the right first operator host for a serious visual workbench.

## 8. Related Specifications / Further Reading

- `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_OPERATOR_BOOT_ASSET_MANIFEST.md`
- `plan/architecture-vscode-extension-bridge-1.md`
- `plan/architecture-hlf-reconstruction-2.md`
