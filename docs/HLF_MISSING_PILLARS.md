# HLF Missing Pillars

This document shows which parts of the HLF vision are:

- present
- damaged
- missing
- source-only

It exists so reconstruction work can be pointed at real gaps instead of vague ambition.

## Status Meanings

- **Present**: materially implemented in this repo now
- **Damaged**: present in partial, narrowed, misaligned, or under-powered form
- **Missing**: no credible local equivalent yet
- **Source-only**: strong evidence exists in `hlf_source/`, but it is not yet restored or faithfully ported

## Pillar Status Map

| Pillar | Status | What Exists Now | What Is Still Missing Or Damaged | Main Evidence |
| --- | --- | --- | --- | --- |
| Deterministic language core | Present | Packaged grammar, compiler, translator, formatter, linter, bytecode, CLI, docs | Still needs continued consolidation of semantic mines from legacy and source files | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/bytecode.py`, `SSOT_HLF_MCP.md` |
| Runtime and capsule-bounded execution | Present | Real runtime, gas model, bytecode, capsule enforcement, governance files | Stronger replay, proof, and richer runtime semantics are still bridge work | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/capsules.py`, `governance/bytecode_spec.yaml`, `HLF_MCP_TODO.md` |
| Governance-native execution | Damaged | Manifest checks, align rules, host-function registry, policy artifacts, ethics hook | Full control matrix, stronger fail-closed proof, richer ALIGN/live-ledger style surfaces are not restored | `governance/align_rules.json`, `governance/host_functions.json`, `governance/MANIFEST.sha256`, `SSOT_HLF_MCP.md`, `hlf_source/governance/ALIGN_LEDGER.yaml` |
| Typed effect and capability algebra | Damaged | Host-function registry and reference docs exist | Strong typed contracts for inputs, outputs, effects, failures, and proof surfaces are still incomplete | `governance/host_functions.json`, `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`, `HLF_MCP_TODO.md` |
| Human-readable audit and trust layer | Damaged | Translation, reference docs, explanatory narrative, plain-language vision surfaces | More explicit operator-facing audit, effect previews, and execution explanations still need hardening | `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/insaits.py`, `README.md`, `docs/HLF_VISION_PLAIN_LANGUAGE.md` |
| Real-code bridge | Damaged | Code generation exists and the doctrine is explicit | Broader target-language output, proof of correctness, and stronger generated-output workflows are still thin | `hlf_mcp/hlf/codegen.py`, `docs/HLF_DESIGN_NORTH_STAR.md`, `HLF_MCP_TODO.md` |
| Knowledge substrate and governed memory | Damaged | Packaged Infinite RAG, memory-node, and MCP memory surfaces exist, and the repo already carries an explicit HLF Knowledge Substrate (HKS) line above those subsystem pieces | Provenance, freshness, confidence, trust-tier, forgetting, weekly evidence discipline, and the full HKS package boundary are not yet locked down as first-class contracts | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`, `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`, `HLF_MCP_TODO.md`, `hlf_source/agents/core/memory_scribe.py` |
| Formal verification surface | Source-only | Doctrine and TODOs point at verification needs | No packaged equivalent to the upstream verifier is in place yet | `hlf_source/agents/core/formal_verifier.py`, `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md`, `HLF_SOURCE_EXTRACTION_LEDGER.md` |
| Gateway and routing fabric | Source-only | The current repo has MCP and runtime entry points, but not the fuller routing fabric | Validation chain, nonce/gas/routing middleware, richer provider selection, and routing traces are not restored | `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/gateway/sentinel_gate.py` |
| Orchestration lifecycle and plan execution | Source-only | Some fixture and doctrine support exists | Spec-to-plan-to-execute lifecycle and DAG execution surfaces are not restored into the packaged repo | `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, `hlf_source/agents/core/task_classifier.py` |
| Persona and operator doctrine | Source-only | Repo-level `AGENTS.md` and some handoff docs survive | The richer persona system that shaped governance, orchestration, and review is still mostly upstream-only | `AGENTS.md`, `docs/AGENTS_CATALOG.md`, `hlf_source/config/personas/steward.md`, `hlf_source/config/personas/sentinel.md`, `hlf_source/AGENTS.md` |
| Ecosystem integration surface | Source-only | Bridge docs acknowledge broader ecosystem scope | External integration doctrine, unified ecosystem roadmap, and operational coordination remain upstream-only | `HLF_ACTIONABLE_PLAN.md`, `HLF_CANONICALIZATION_MATRIX.md`, `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, `hlf_source/docs/JULES_COORDINATION.md` |
| Gallery and operator-legibility surface | Damaged | References, fixtures, and explainers exist in partial form | A full gallery/report surface and stronger operator demo path are not yet restored | `fixtures/README.md`, `docs/HLF_REFERENCE.md`, `hlf_source/scripts/run_hlf_gallery.py`, `hlf_source/docs/hlf_explainer.html` |

## Short Reading

The important point is not that HLF is absent.

It is not absent.

The important point is that the repo already has a real semantic core, runtime, governance assets, docs, examples, and MCP delivery surface, but several of the larger constitutive pillars are still narrowed, damaged, or stranded in source-only form.

The biggest under-recovered pillars are:

1. gateway and routing fabric
2. orchestration lifecycle
3. formal verification
4. HLF knowledge substrate and richer governed memory contracts
5. persona/operator doctrine
6. ecosystem integration surfaces

## What To Do With This

Use this document to decide what kind of work a missing area needs:

- restore it
- port it faithfully
- bridge to it explicitly
- or record why it remains source-only for now

If a pillar is constitutive, it should never be silently treated as optional just because the smaller story is easier to maintain.

That rule applies to the HLF-native knowledge substrate as well. The repo is not allowed to flatten Infinite RAG as a subsystem, plus the broader HKS governed-memory and weekly-evidence work, back into a generic retrieval bucket or an unnamed "memory feature" lane.