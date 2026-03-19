# HLF Recovery Batch 1

Status: planned executable restoration batch for operator trust and routing proof.

## Batch Goal

Recover the first trust-bearing constitutive cluster:

1. routing fabric
2. formal verification lane boundary
3. governance control matrix skeleton
4. HLF knowledge-substrate and memory-evidence contract normalization
5. operator-readable proof surfaces

## Included Pillars

| Pillar | Recovery Mode | Upstream Files | Target Files | Owner Module |
| --- | --- | --- | --- | --- |
| Routing fabric | faithful port | `hlf_source/agents/gateway/bus.py`, `hlf_source/agents/gateway/router.py`, `hlf_source/agents/gateway/sentinel_gate.py` | `hlf_mcp/server_profiles.py`, `hlf_mcp/hlf/model_catalog.py`, `hlf_mcp/server_resources.py`, packaged routing helper under `hlf_mcp/hlf/` if needed | packaged routing layer |
| Formal verification lane boundary | faithful port start | `hlf_source/agents/core/formal_verifier.py` | packaged verifier module under `hlf_mcp/hlf/`, adjacent touch points in `hlf_mcp/hlf/runtime.py` and `hlf_mcp/hlf/capsules.py` | packaged verifier layer |
| HLF knowledge-substrate and memory-evidence normalization | faithful port / bridge | `hlf_source/agents/core/memory_scribe.py`, `hlf_source/agents/core/context_pruner.py`, `hlf_source/scripts/verify_chain.py` | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py`, `hlf_mcp/server_context.py` | packaged memory layer |
| Governance control skeleton | bridge contract | `hlf_source/governance/ALIGN_LEDGER.yaml`, `hlf_source/agents/gateway/sentinel_gate.py` | `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` and associated packaged references | bridge docs and governance surface |
| Operator proof surfaces | bridge contract | route, verifier, and memory source clusters above | `hlf_mcp/server_resources.py`, related docs and tests | operator surface layer |

## Excluded From Batch 1 And Why

| Pillar | Reason Not In Batch 1 |
| --- | --- |
| Orchestration lifecycle | Depends on verifier and route proof surfaces so execution admission is not restored on a weaker base |
| Persona and operator doctrine integration | Needs Batch 1 proof surfaces first so roles map onto real controls rather than abstractions |
| Gallery/operator-legibility expansion | Must follow real route/verifier/memory evidence objects to avoid decorative stand-ins |
| Real-code bridge proof expansion | Lower trust priority than verifier and routing proof |
| Ecosystem integration | Constitutive scope, but downstream of core governed coordination proof |

## Required Tests

- route selection and fallback regressions
- evidence-required route denial regressions
- early verifier result-structure regressions
- memory evidence schema and stale-artifact regressions
- resource-level proof-surface regressions

## Required Docs Updates

- `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` if claim status changes
- `SSOT_HLF_MCP.md` only after packaged truth actually changes

## Acceptance Gates

1. Every restored surface has explicit packaged ownership.
2. Route decisions expose deterministic rationale and evidence references.
3. Verifier boundary exists in packaged code, even if initial scope is narrow.
4. Memory evidence schema exists and is enforced where route or promotion logic consumes artifacts.
5. Operator-readable summaries are grounded in structured evidence, not free text.
