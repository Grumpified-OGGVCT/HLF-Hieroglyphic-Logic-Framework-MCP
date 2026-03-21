# HLF Branch-Aware Claims Ledger

Status: public-facing branch-aware review aid for 2026-03-20.

Purpose:

- give reviewers and PR readers a compact way to distinguish public-main perception from current branch reality
- keep branch improvements visible without promoting bridge work into false completion
- separate stale public gap claims from the real remaining architectural gaps

Reading rule:

- use `docs/HLF_CLAIM_LANES.md` when reusing or promoting any statement from this file
- this ledger is branch-aware, not `main`-only
- a `branch-resolved` item means the gap is no longer accurate for this checkout, not that the full target pillar is complete

Verified branch facts used here:

- active branch: `integrate/vscode-operator-governed-review`
- divergence from `main`: `0` behind, `10` ahead
- packaged surface count in this checkout: `69` tools, `31` resources

## 1. Overstated Public Gaps

| Public gap claim | Branch-aware reality | True remaining gap after both are considered |
| --- | --- | --- |
| Formal verification is only a placeholder or source-only idea | Packaged formal-verifier behavior now exists in `hlf_mcp/hlf/formal_verifier.py` with tests and front-door resource proof | Deeper verifier semantics, broader proof coverage, and fuller upstream restoration remain open |
| There is no governed review or operator evidence normalization | `hlf_mcp/governed_review.py` and weekly artifact/evidence-query surfaces now exist and are tested | The fuller operator product and richer audit dashboards remain open |
| The repo has no symbolic bridge lane at all | `hlf_mcp/hlf/symbolic_surfaces.py` provides tested relation-edge extraction, projection, explanation, and audit logging | Broader symbolic-semantic restoration remains bridge work |
| Dream/media evidence is absent as a governed branch lane | Bounded dream-cycle, media evidence, citation-chain proposal, and multimodal contract surfaces now exist in this checkout | The lane is still advisory and not yet a fully restored autonomous-evolution subsystem |
| There is no VS Code bridge or operator shell work | `extensions/hlf-vscode/` now contains a real claim-lane-aware operator bridge scaffold | It remains a scaffold, not Marketplace-shipped completion |

## 2. Valid Public Gaps

| Public gap claim | Branch-aware reality | True remaining gap after both are considered |
| --- | --- | --- |
| The fuller upstream routing fabric is not yet restored | Correct | Still open: packaged route traces and governed selection exist, but the broader gateway/router fabric is not yet back |
| Orchestration is still only partially packaged | Correct | Still open: packaged lifecycle and DAG slices exist, but not the full upstream plan-execution and delegation stack |
| Memory governance is still incomplete | Correct | Still open: freshness, revocation, supersession, trust-tier, and unified evidence contracts still need stronger completion |
| Gallery/operator legibility is not yet fully restored | Correct | Still open: current operator-readable resources are stronger, but gallery-grade and end-to-end operator surfaces remain bridge work |
| Signed disclosure and ALS-style audit sealing are still missing | Correct | Still open |

## 3. Branch-Resolved Gaps

| Gap previously inferred from public-facing materials | What now exists in this checkout | Lane-qualified reading |
| --- | --- | --- |
| Weekly artifact handling is only a basic automation baseline | Decision persistence, verified loading, evidence querying, and normalized governed-review outputs now exist | `current-true` for the bounded packaged surfaces; broader operatorization remains `bridge-true` |
| Multimodal is an empty lane family | Qualification profiles and `hlf://status/multimodal_contracts` now exist | `bridge-true` |
| Dream findings cannot be inspected or linked to proposals | Dream-cycle status/findings/resources and observe-propose-verify-promote citation-chain proposals now exist | `bridge-true` |
| Formal verifier only exposes a status stub | Tools, reports, and regression proof now exist | `current-true` for the packaged slice |
| Symbolic proof has no concrete implementation slice | Tested relation-edge symbolic surface now exists | `bridge-true` |

## 4. Still-Open Architectural Gaps

| Gap | Why it is still open |
| --- | --- |
| Full routing fabric restoration | Packaged routing is stronger, but the upstream gateway/bus/router coordination layer is not yet restored |
| Full orchestration lifecycle restoration | Packaged lifecycle and DAG normalization exist, but multi-agent execution, delegation, and fuller crew orchestration remain incomplete |
| Stronger memory-governance closure | Revocation, expiry, supersession, and one coherent evidence contract still need stronger packaged closure |
| Deeper formal-verification semantics | The packaged verifier is real now, but the upstream proof stack is broader than the current packaged slice |
| Operator/gallery-grade trust surfaces | Current resources are useful but not yet the full operator trust product |
| Governance integrity cleanup | The host-function registry drift was resolved by re-manifesting `governance/host_functions.json`, but integrity still depends on keeping `MANIFEST.sha256` refreshed when tracked governance files change |
| Remote recursive-build promotion | Local bounded build assistance is real, but remote `streamable-http` self-hosting remains gated until the full initialize path is proven |

## Bottom Line

The public repo can still make the branch look thinner than it is.

The corrective reading is:

- some public gaps are stale or overstated for this checkout
- some are genuinely resolved in the branch but still bridge-qualified
- some remain real architectural gaps even after the branch work is counted

That is the split reviewers should use before judging whether the repo is merely under-documented, materially improved, or still missing constitutive HLF pillars.