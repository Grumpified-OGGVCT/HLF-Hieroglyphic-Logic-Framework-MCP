# HLF Rejected Extraction Audit

Status: bridge-lane archaeology authority for rejected or downgraded constitutive surfaces on 2026-03-19.

Purpose:

- audit source surfaces that were previously treated as `missing`, `optional`, `process-only`, `OS-bound`, or `superseded`
- identify which of those surfaces actually carry constitutive HLF doctrine, routing, verification, governance, persona, orchestration, or ecosystem meaning
- correct prior reductionist classifications without importing the full Sovereign OS wholesale
- assign one deterministic disposition for each audited surface

## Audit Rule

This file is not a packaged-truth document.

- It exists because prior extraction logic sometimes treated messy or distributed architecture as expendable.
- If a surface narrows HLF from a governed coordination language into a syntax/runtime fragment when removed, it belongs here.
- A surface can remain source-only for now and still be architecturally constitutive.

## Disposition Vocabulary

- `restore`: restore directly into packaged truth with runtime ownership
- `faithful_port`: port into a new packaged boundary without flattening the source design
- `bridge_contract`: preserve the source authority while creating bounded packaged interfaces, docs, and proof surfaces
- `source_only_for_now`: preserve as constitutive evidence, but defer movement into packaged truth until earlier bridge batches land
- `not_hlf_core`: useful context, but not constitutive to HLF reconstruction in this repo

## Audit Table

| Source Surface | Prior Ledger / Heuristic | Corrected Classification | Why It Matters | Surface Type | Disposition | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `hlf_source/agents/gateway/bus.py` | `missing`, `OS-bound` | strong but not yet packaged | Preserves the end-to-end gateway pipeline: ingress, validation, ALIGN, gas, nonce, routing, and dispatch. This is execution semantics, not incidental scaffolding. | runtime | `faithful_port` | Port gateway semantics selectively into packaged routing and audit boundaries; do not import FastAPI bus wholesale |
| `hlf_source/agents/gateway/router.py` | `missing`, `upstream orchestration` | strong but not yet packaged | Preserves richer routing logic: complexity scoring, tier walk, allowlist gating, dynamic downshifting, routing traces, and gas-aware model selection. | runtime | `faithful_port` | Source of truth for Batch 1 routing recovery |
| `hlf_source/agents/gateway/sentinel_gate.py` | `missing`, tied to Sovereign bus | strong but not yet packaged | Shows governance as part of intent execution flow rather than an after-the-fact wrapper. | runtime/governance | `bridge_contract` | Its semantics should inform packaged control-matrix and route-admission behavior |
| `hlf_source/agents/core/formal_verifier.py` | `missing`, `maybe` | wrongly deleted | Directly encodes satisfiability, invariant, gas-budget, reachability, and spec-gate verification concepts that are constitutive to trustworthy HLF execution. | runtime/proof | `faithful_port` | Top-priority recovery surface; absence weakens governed-language claims |
| `hlf_source/agents/core/plan_executor.py` | not extracted, treated as upstream workflow | wrongly deleted | Converts plans into DAG execution order with agent assignment and verification steps. This is a core multi-agent coordination surface, not generic automation. | runtime/orchestration | `faithful_port` | Must be restored with clear packaged ownership boundaries |
| `hlf_source/agents/core/crew_orchestrator.py` | not extracted, treated as upstream workflow | wrongly deleted | Preserves multi-persona round-robin synthesis, SDD lifecycle ordering, and consolidation protocol. | runtime/orchestration | `faithful_port` | Strong evidence that lifecycle/orchestration is part of HLF’s intended shape |
| `hlf_source/agents/core/task_classifier.py` | not extracted, process-oriented | strong but not yet packaged | Preserves task vocabulary and launcher doctrine connecting plans, provenance, and execution scope. | runtime/orchestration | `faithful_port` | Include in orchestration recovery spec rather than leaving implicit |
| `hlf_source/AGENTS.md` | context-only handover | wrongly replaced | High-signal architecture document connecting layers, hats, invariants, operator roles, and HLF-bearing data flow. | doctrine/operator | `bridge_contract` | Current root `AGENTS.md` should stay, but this file remains authoritative source evidence for persona/operator recovery |
| `hlf_source/.github/agents/hats.agent.md` | process-only | strong but not yet packaged | Encodes adversarial review and decomposition logic as operational system discipline rather than mere prompt style. | doctrine/operator | `bridge_contract` | Preserve as operator doctrine input, not runtime code authority |
| `hlf_source/config/agent_registry.json` | `missing`, `OS persona system` | wrongly omitted | Defines role-specialized agent boundaries, model assignment, and persona coverage that shape orchestration and governance. | doctrine/runtime boundary | `source_only_for_now` | Important for future persona-aware orchestration, but not a first packaged import |
| `hlf_source/config/personas/steward.md` | `missing`, useful source material | wrongly replaced | Steward frames MCP and tool orchestration as governed trust-boundary work. This is constitutive to HLF’s tool-use worldview. | doctrine/operator | `bridge_contract` | Use as primary input for persona/operator recovery spec |
| `hlf_source/config/personas/strategist.md` | `missing`, useful source material | strong but not yet packaged | Preserves planning and recovery discipline beyond local implementation convenience. | doctrine/operator | `bridge_contract` | Keep in doctrine lane until bounded packaged integration exists |
| `hlf_source/config/personas/sentinel.md` | `missing`, useful source material | strong but not yet packaged | Carries security and governance posture that informs fail-closed review and route admission. | doctrine/operator | `bridge_contract` | Important for operator doctrine and governance control narratives |
| `hlf_source/governance/ALIGN_LEDGER.yaml` | `superseded` by `align_rules.json` | strong but misaligned | Preserves richer governance rule identity and historical control semantics that should not be collapsed into a thinner local representation without accounting. | governance/doctrine | `bridge_contract` | Do not re-authorize YAML wholesale; mine it into packaged control matrices and proofs |
| `hlf_source/governance/hls.yaml` | `superseded`, drift-prone grammar descriptor | strong but misaligned | Machine-readable language-scope authority tied to typed capabilities and governance semantics. | governance/language | `bridge_contract` | Useful for effect-algebra recovery even if packaged compiler remains canonical |
| `hlf_source/agents/core/memory_scribe.py` | renamed/merged into memory surfaces | strong but misaligned | Preserves governed memory with WAL storage, archive logic, vector hooks, and evidence-oriented lifecycle. | runtime/memory | `faithful_port` | Core source for memory-governance recovery beyond simple retrieval |
| `hlf_source/agents/core/context_pruner.py` | not extracted | strong but not yet packaged | Shows forgetting-curve and bounded-context doctrine instead of naive memory accumulation. | runtime/memory | `bridge_contract` | Required for a lossless memory-governance story |
| `hlf_source/scripts/verify_chain.py` | lightweight helper, process-ish | strong but not yet packaged | Gives concrete audit-chain verification behavior for Merkle and provenance integrity. | audit/proof | `bridge_contract` | Good candidate for packaged audit proof tooling |
| `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md` | omitted as non-core roadmap | wrongly omitted | Proves HLF was meant to mediate broader ecosystem integrations through host functions and governance rather than stay a local package. | doctrine/ecosystem | `source_only_for_now` | Constitutive for long-range scope; not higher priority than trust and orchestration batches |
| `hlf_source/docs/JULES_COORDINATION.md` | omitted as workflow doc | strong but not yet packaged | Shows intended multi-agent collaboration protocol around the repo and larger system. | doctrine/ecosystem | `source_only_for_now` | Preserve as bridge evidence for later ecosystem and operator workflow recovery |
| `hlf_source/scripts/run_hlf_gallery.py` | `missing`, useful but optional | strong but not yet packaged | Systematizes gallery compilation, reporting, and operator visibility for HLF programs. | operator/reporting | `bridge_contract` | Should be restored as part of operator-legibility surfaces, not dismissed as decorative |
| `hlf_source/docs/hlf_explainer.html` | optional explainer asset | strong but not yet packaged | Preserves human-legibility and operator education surfaces that keep HLF inspectable. | operator/reporting | `bridge_contract` | Treat as part of gallery/operator surface spec |
| `hlf_source/gui/app.py` | optional GUI | strong but not yet packaged | Demonstrates operator-facing explainability and interactive trust surfaces. | operator/reporting | `source_only_for_now` | Valuable reference, but not a Batch 1 or Batch 2 packaged import |
| `hlf_source/scripts/persona_gambit.py` | omitted as OS automation | wrongly omitted | Shows persona coverage operationalized instead of merely documented. | doctrine/ecosystem | `source_only_for_now` | Keep as evidence for later persona-integration work |
| `hlf_source/scripts/local_autonomous.py` | omitted as OS automation | strong but not yet packaged | Encodes autonomous loop expectations and external coordination behavior around HLF. | doctrine/ecosystem | `source_only_for_now` | Important context, but downstream of Batch 1 and Batch 2 recovery |

## Seed Coverage Required By Master Plan

The master plan explicitly required these top-ranked files to seed this audit. They are now covered above:

1. `hlf_source/AGENTS.md`
2. `hlf_source/agents/gateway/bus.py`
3. `hlf_source/agents/gateway/router.py`
4. `hlf_source/agents/core/formal_verifier.py`
5. `hlf_source/agents/core/plan_executor.py`
6. `hlf_source/agents/core/crew_orchestrator.py`
7. `hlf_source/config/personas/steward.md`
8. `hlf_source/governance/ALIGN_LEDGER.yaml`
9. `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`
10. `hlf_source/scripts/run_hlf_gallery.py`

## Rejection Patterns That Need To Stop

These were the recurring extraction mistakes revealed by the audit.

- Treating gateway and orchestration code as mere OS glue even when it carries HLF execution semantics.
- Treating persona and hat files as writing-style prompts instead of governance and workflow-control doctrine.
- Treating formal verification as aspirational even when a concrete verifier surface exists upstream.
- Treating gallery, explainer, and operator-reference surfaces as polish rather than trust-bearing product surfaces.
- Treating ecosystem and coordination docs as irrelevant because they are not runtime code, even when they define the intended scope of HLF as a coordination substrate.

## Immediate Recovery Consequences

1. Batch 1 must stay centered on routing, verifier, memory evidence, and operator trust.
2. Batch 2 must restore orchestration lifecycle and verifier-backed execution admission.
3. Persona and ecosystem surfaces stay in doctrine and bridge lanes for now, but they may not be reclassified as optional.
4. The extraction ledger should eventually be updated so these constitutive surfaces are no longer flattened into `no` or thinly scoped `maybe` judgments without bridge context.

## Working Rule

Before any future file is dismissed as optional, check whether removing it narrows HLF from a governed coordination language into a smaller parser-runtime package. If it does, it belongs in reconstruction work even if it remains source-only for a while.