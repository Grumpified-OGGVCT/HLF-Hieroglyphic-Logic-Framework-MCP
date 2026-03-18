# HLF Repo Implementation Map

Status: current-truth bridge map for the packaged repo on 2026-03-18.

Purpose:

- map the actual current module ownership in this checkout
- mark each major HLF pillar as built, partial, or missing in packaged truth
- identify the first concrete files to patch for the next recovery step

## Canonical Ownership

| Surface | Primary files | Role |
| --- | --- | --- |
| Packaged MCP assembly | `hlf_mcp/server.py`, `hlf_mcp/server_core.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/server_memory.py`, `hlf_mcp/server_capsule.py`, `hlf_mcp/server_resources.py`, `hlf_mcp/server_context.py` | Current product-facing FastMCP surface |
| Language core | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py`, `hlf_mcp/hlf/translator.py` | Deterministic parse, format, lint, and translation path |
| Runtime and bytecode | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/bytecode.py`, `governance/bytecode_spec.yaml` | Executable HLF runtime contract |
| Capsule and execution boundaries | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py` | Tier-bounded execution, capsule validation, host exposure |
| Memory substrate | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py` | Memory storage, provenance fragments, MCP recall/store surface |
| Governance spine | `governance/align_rules.json`, `governance/host_functions.json`, `governance/module_import_rules.yaml`, `governance/pii_policy.json`, `governance/MANIFEST.sha256` | Governing constraints and executable registries |
| Lifecycle and instinct | `hlf_mcp/instinct/lifecycle.py`, `hlf_mcp/server_instinct.py` | Spec and lifecycle orchestration already packaged |
| Compatibility line | `hlf/`, `scripts/legacy_probes/` | Legacy support, manual probes, migration context only |
| Upstream archaeology | `hlf_source/` | Source-only context and faithful-port inputs |

## Pillar Status Matrix

| Pillar | Status | Current packaged owners | Notes |
| --- | --- | --- | --- |
| Deterministic language core | Built | `hlf_mcp/hlf/compiler.py`, `hlf_mcp/hlf/grammar.py`, `hlf_mcp/hlf/formatter.py`, `hlf_mcp/hlf/linter.py` | Real packaged compiler and grammar path |
| Runtime and bytecode | Built | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/hlf/bytecode.py` | Real executable surface with gas and trace |
| MCP delivery surface | Built | `hlf_mcp/server.py`, `hlf_mcp/server_core.py`, `hlf_mcp/server_resources.py` | Current product front door |
| Translation front door | Built | `hlf_mcp/server_translation.py`, `hlf_mcp/hlf/translator.py` | Packaged English-to-HLF path |
| Capsule-bounded execution | Partial | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py` | Tier allowlists, capsule identity, pointer trust, and deterministic approval-token responses now exist; persisted human workflow and stronger sandbox guarantees remain bridge work |
| Memory provenance and trust | Partial | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py` | Hashing and Merkle fragments exist, but pointer trust, revocation, and freshness contracts were incomplete before this pass |
| Cryptographic pointer trust | Missing | `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/server_capsule.py` | No packaged pointer contract existed before this pass |
| Approval and escalation semantics | Partial | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py` | Requested-tier escalation, approval requirements, deterministic approval tokens, and `approval_required` MCP responses now exist; durable approval ledgers and richer operator workflow are still missing |
| Formal verification lane | Missing | source-only in `hlf_source/agents/core/formal_verifier.py` | Not yet restored into packaged truth |
| Routing fabric | Partial | `hlf_mcp/hlf/runtime.py`, `hlf_mcp/server_translation.py`, `hlf_mcp/server_profiles.py` | Advisory routing exists, but upstream gateway/router fabric is still not restored |
| Entropy-anchor drift checks | Partial | `hlf_mcp/hlf/entropy_anchor.py`, `hlf_mcp/server.py`, `hlf_mcp/hlf/insaits.py`, `hlf_mcp/hlf/audit_chain.py` | Packaged MCP-facing entropy-anchor evaluation now exists for anti-drift and operator-legible proof-of-meaning checks; continuous daemon behavior and deeper runtime enforcement remain bridge work |
| Governed memory nodes | Partial | `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/rag/memory.py` | Structured substrate exists, but richer AST-native and trust-tier semantics remain incomplete |
| ALS / signed audit chain | Missing | `hlf_mcp/hlf/insaits.py`, `scripts/verify_chain.py` | Trace and hash surfaces exist, but packaged ALS sealing is not yet implemented |
| Agent Cards / signed disclosure | Missing | no packaged equivalent yet | Still bridge work |

## First Concrete Patch Set

These are the first concrete files to patch for Intent Capsules and Pointer Trust in the packaged lane.

| File | Why it is first |
| --- | --- |
| `hlf_mcp/hlf/capsules.py` | This is the packaged capsule contract and the correct place to add capsule identity, pointer trust policy, and richer validation |
| `hlf_mcp/hlf/memory_node.py` | This is the right packaged home for pointer parsing, digest validation, freshness, revocation, and registry-entry helpers |
| `hlf_mcp/hlf/runtime.py` | Runtime host dispatch must enforce trusted-pointer resolution instead of treating pointer strings as inert text |
| `hlf_mcp/server_capsule.py` | MCP tools must expose capsule metadata and pointer validation cleanly |
| `hlf_mcp/server_memory.py` | Memory store responses should emit pointer references so the trust contract is usable immediately |
| `tests/test_capsule_pointer_trust.py` | Regression coverage for the new capsule and pointer-trust behavior |

## Implementation Order

1. Add packaged pointer primitives in `hlf_mcp/hlf/memory_node.py`.
2. Extend `hlf_mcp/hlf/capsules.py` so capsules can require trusted pointers.
3. Enforce pointer trust in `hlf_mcp/hlf/runtime.py` host dispatch.
4. Expose validation and runtime wiring through `hlf_mcp/server_capsule.py` and `hlf_mcp/server_memory.py`.
5. Lock the behavior with regression tests.

## Boundary Rule

This file is a repo-specific current-truth implementation map.

It does not claim that the full HLF vision is already packaged.
It does identify the exact packaged files that now own the next recovery move.