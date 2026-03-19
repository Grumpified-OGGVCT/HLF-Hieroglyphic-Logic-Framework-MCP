# HLF Vision Map

This document links the big HLF ideas to files that already support them.

It exists to stop the repo from collapsing into either of these mistakes:

- a huge vision with no grounding
- a cramped implementation story that forgets what HLF is actually trying to become

Use this map like this:

- if you want the plain-language version, read `docs/HLF_VISION_PLAIN_LANGUAGE.md`
- if you want the north-star doctrine, read `docs/HLF_DESIGN_NORTH_STAR.md` and `HLF_VISION_DOCTRINE.md`
- if you want strict current build truth, read `SSOT_HLF_MCP.md`
- if you want to see where the vision is still damaged or absent, read `docs/HLF_MISSING_PILLARS.md`

## Vision Map

| Big Idea | What It Means | Current Supporting Files In This Repo | Source / Reconstruction Evidence | Bridge Implication |
| --- | --- | --- | --- | --- |
| HLF as the meaning layer | HLF sits between human intent and machine action, carrying governed meaning instead of loose prose | `HLF_VISION_DOCTRINE.md`, `docs/HLF_DESIGN_NORTH_STAR.md`, `docs/HLF_VISION_PLAIN_LANGUAGE.md`, `README.md` | `AGENTS.md`, `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` | Keep HLF framed as a language and coordination substrate, not just a parser or MCP tool pack |
| Deterministic language core | Stable grammar, AST, compiler, formatter, linter, translation, and bytecode are the semantic spine | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/bytecode.py`, `docs/HLF_GRAMMAR_REFERENCE.md`, `docs/HLF_REFERENCE.md` | `HLF_SOURCE_EXTRACTION_LEDGER.md`, `hlf_source/hlf/hlfc.py`, `hlf_source/hlf/hlffmt.py`, `hlf_source/hlf/translator.py`, `hlf_source/hlf/bytecode.py` | This pillar is real now and should stay authoritative in the packaged surface |
| Governance built into execution | Safety and policy are part of compile and run behavior, not bolted on later | `governance/align_rules.json`, `governance/host_functions.json`, `governance/bytecode_spec.yaml`, `governance/module_import_rules.yaml`, `governance/pii_policy.json`, `governance/MANIFEST.sha256`, `hlf_mcp/hlf/capsules.py` | `hlf_source/governance/ALIGN_LEDGER.yaml`, `hlf_source/agents/gateway/sentinel_gate.py`, `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` | Preserve and deepen this as a core HLF claim rather than treating it like middleware |
| Effect and capability algebra | HLF should express what can happen, not only what should be done | `governance/host_functions.json`, `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`, `hlf_mcp/hlf/tool_dispatch.py`, `hlf_mcp/hlf/capsules.py` | `hlf_source/governance/host_functions.json`, `hlf_source/governance/hls.yaml`, `hlf_source/agents/core/formal_verifier.py` | Current capability surfaces exist, but typed proof and stronger contract gates still need work |
| Governed runtime and replayable execution | Programs run under gas, trace, capsule, and bytecode boundaries | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/bytecode.py`, `governance/bytecode_spec.yaml`, `BUILD_GUIDE.md`, `SSOT_HLF_MCP.md` | `hlf_source/hlf/runtime.py`, `hlf_source/hlf/bytecode.py`, `hlf_source/agents/core/formal_verifier.py` | Keep runtime truth in the packaged line while mining richer semantics from legacy and source files |
| MCP as the adoption path | Any agent should be able to connect and gain HLF capabilities immediately | `hlf_mcp/server.py`, `README.md`, `BUILD_GUIDE.md`, `QUICKSTART.md`, `docs/HLF_MCP_AGENT_HANDOFF.md`, `docs/HLF_AGENT_ONBOARDING.md` | `hlf_source/mcp/sovereign_mcp_server.py`, `hlf_source/config/personas/steward.md` | Treat MCP as the front door to HLF, not as the full definition of HLF |
| HLF knowledge substrate and governed memory | Memory should carry provenance, freshness, confidence, trust, and weekly evidence discipline, not just storage, and Infinite RAG should remain part of a named HLF-native knowledge substrate rather than a generic retrieval bucket | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md`, `HLF_MCP_TODO.md` | `hlf_source/agents/core/memory_scribe.py`, `hlf_source/agents/core/context_pruner.py`, `hlf_source/scripts/verify_chain.py` | This pillar exists in partial form and needs stronger contracts, package boundaries, and audit shape |
| Multi-agent coordination language | HLF should express delegation, votes, trust boundaries, and handoff contracts | `docs/HLF_DESIGN_NORTH_STAR.md`, `HLF_VISION_DOCTRINE.md`, fixtures such as `fixtures/delegation.hlf` and `fixtures/decision_matrix.hlf` | `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py` | This is one of the biggest under-recovered pillars in the packaged repo |
| Human-readable trust surface | Users should be able to read what the system will do and why | `README.md`, `docs/HLF_REFERENCE.md`, `docs/HLF_GRAMMAR_REFERENCE.md`, `docs/HLF_VISION_PLAIN_LANGUAGE.md`, `hlf_mcp/hlf/translator.py`, `hlf_mcp/hlf/insaits.py` | `hlf_source/docs/HLF_REFERENCE.md`, `hlf_source/docs/hlf_explainer.html`, `hlf_source/gui/app.py` | Keep building operator-legible explainers, audits, and gallery surfaces |
| Real-code output bridge | HLF must generate real work in real languages and tools | `hlf_mcp/hlf/codegen.py`, `hlf_mcp/hlf/compiler.py`, `BUILD_GUIDE.md`, `docs/HLF_DESIGN_NORTH_STAR.md` | `hlf_source/hlf/translator.py`, `hlf_source/hlf/insaits.py`, `hlf_source/scripts/run_hlf_gallery.py` | The bridge exists, but it still needs broader target coverage and stronger proof/report surfaces |
| Persona and review doctrine | Personas and adversarial review are part of how HLF stays governed and legible | `AGENTS.md`, `docs/AGENTS_CATALOG.md`, `docs/ETHICAL_GOVERNOR_HANDOFF.md` | `hlf_source/AGENTS.md`, `hlf_source/config/personas/steward.md`, `hlf_source/config/personas/strategist.md`, `hlf_source/config/personas/sentinel.md`, `hlf_source/.github/agents/hats.agent.md` | This is architectural doctrine, not just writing style; keep it visible |
| Ecosystem and operator bridge | HLF is meant to plug into a wider agent ecosystem, not stay locked inside one package | `HLF_ACTIONABLE_PLAN.md`, `HLF_CANONICALIZATION_MATRIX.md`, `HLF_IMPLEMENTATION_INDEX.md` | `hlf_source/docs/UNIFIED_ECOSYSTEM_ROADMAP.md`, `hlf_source/docs/JULES_COORDINATION.md`, `hlf_source/scripts/persona_gambit.py`, `hlf_source/scripts/local_autonomous.py` | Recovery work must account for ecosystem scope even when code is not ported wholesale |

## Reading The Map Correctly

This map does not say every pillar is already finished.

It says the vision is already supported by real doctrine, code, governance assets, source evidence, and operator surfaces.

That matters because the repo should build from its real architectural intent, not from the smallest subset that is easiest to describe.

## Related Docs

- `docs/HLF_VISION_PLAIN_LANGUAGE.md` for the direct statement of the vision
- `docs/HLF_MISSING_PILLARS.md` for the gap report
- `SSOT_HLF_MCP.md` for present-tense build truth
- `HLF_SOURCE_EXTRACTION_LEDGER.md` for extraction status
- `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` for high-value source clusters