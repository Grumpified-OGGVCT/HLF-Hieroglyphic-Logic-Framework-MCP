# HLF Transcript Mechanism Map — 2026-03-18

Status: bridge-lane mapping from transcript-derived mechanisms to exact current files and current pillar status.

Purpose:

- map transcript mechanisms to real packaged owners where they exist
- identify which missing or damaged pillars each mechanism belongs to
- reduce hand-wavy planning by naming exact files and exact gaps

## Mechanism Map

| Mechanism | Transcript role | Exact current packaged files | Upstream / source-only anchors | Current pillar status | Bridge judgment |
| --- | --- | --- | --- | --- | --- |
| Two-channel pass-by-reference | Keep raw payloads out of LLM context; resolve data only at execution time | `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/rag/memory.py`, `hlf_mcp/server_memory.py`, `hlf_mcp/server_capsule.py` | `hlf_source/agents/core/memory_scribe.py` and related memory context surfaces | Memory as governed substrate = damaged; cryptographic pointer trust = partial bridge slice | Already in active bridge implementation; continue hardening freshness, revocation, and strict resolution behavior |
| Cryptographic content pinning / TOCTOU defense | Prevent data mutation between validation and execution | `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py`, `scripts/verify_chain.py` | `hlf_source/governance/ALIGN_LEDGER.yaml`, source trust-chain logic | Governance-native execution = damaged; memory substrate = damaged | Continue in packaged trust-chain work; transcript reinforces priority |
| MoMA routing | Route workloads by task class rather than generic model selection | `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/runtime.py`, `governance/host_functions.json`, `docs/HLF_EMBEDDING_AGENT_DECISION_MATRIX.md` | `hlf_source/agents/gateway/router.py`, `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/ollama_dispatch.py` | Gateway and routing fabric = source-only / partial packaged advisory routing | Strong target-state signal; needs routing recovery spec and eventual packaged router restoration |
| Hyperledger / Raft shared-state serialization | Serialize concurrent actions and prevent race conditions | no packaged equivalent; nearest local state surfaces are `hlf_mcp/rag/memory.py` and `hlf_mcp/instinct/lifecycle.py` | broader Sovereign service-bus and state-governance architecture | Governance-native execution = damaged; orchestration lifecycle = source-only | Important architectural context, but not the next packaged implementation slice |
| runsc / gVisor microVM boundary | Physically sever agent reasoning from host-kernel privilege | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/server_capsule.py` | source and doctrine references to runsc / stronger sandboxing | Runtime and capsule-bounded execution = present but bridge-incomplete | Keep as sandbox hardening target; do not overclaim current packaged enforcement |
| Entropy anchors | Force periodic proof-of-meaning to detect private dialect drift | `hlf_mcp/hlf/insaits.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/server_capsule.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/audit_chain.py`, `tests/test_insaits.py` | `hlf_source/agents/core/daemons/insaits_daemon.py`, persona/operator doctrine around transparency | Human-readable audit and trust layer = damaged; governance-native execution = damaged | Best next transcript-backed implementation plan because the enabling packaged surfaces already exist |
| Witness / gossip governance | Use decentralized witness reports and probationary trust degradation to manage swarm health | likely packaged landing zone would center on `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/audit_chain.py`, `hlf_mcp/hlf/approval_ledger.py`, `hlf_mcp/server_context.py`, `hlf_mcp/server_memory.py`, and future governance modules | `hlf_source/AGENTS.md` and broader swarm-governance context | Governance-native execution = damaged; memory as governed substrate = damaged; persona/operator doctrine = source-only | Good second implementation plan; broader than entropy anchors and should follow them |
| InsAIts V2 continuous transparency | Translate dense symbolic state back into operator-readable English in real time | `hlf_mcp/hlf/insaits.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/server_capsule.py`, `tests/test_insaits.py` | `hlf_source/agents/core/daemons/insaits_daemon.py`, `hlf_source/config/personas/herald.md` | Human-readable audit and trust layer = damaged; gallery/operator surfaces = damaged | Entropy anchors should reuse these surfaces rather than invent a separate transparency stack |
| Nuance operators | Preserve qualitative / narrative control without collapsing back into free prose | packaged supporting references in compiler/translator/docs; current operator-specific planning in `docs/HLF_LANGUAGE_EVOLUTION_AND_BYTECODE_TRUST_SPEC.md` | RFC 9007-class source evidence | Human-readable trust layer = damaged; language evolution bridge still in progress | Important, but not the next implementation slice requested here |

## Ordered Transcript-Backed Planning Targets

1. **Entropy anchors first**
   Why: packaged InsAIts, translation, similarity-gate, runtime, and audit fragments already exist.

2. **Witness governance second**
   Why: it depends on memory lineage, trust scoring, audit records, routing consequences, and operator-facing review semantics.

## Boundary Rule

This mechanism map records where transcript ideas can land in the repo.

It does not imply that every mechanism belongs in the packaged repo immediately, and it does not imply that every Sovereign OS support system should be imported as-is.