# HLF Governance Control Matrix

Status: bridge-lane control and proof matrix for packaged and recovering HLF governance surfaces on 2026-03-19.

## Purpose

- map governance artifacts and recovery surfaces to concrete operational controls
- show which controls are implemented now, which are bridge work, and which remain source-backed obligations
- prevent strong governance language from floating free of concrete assets and proofs

## Control Matrix

| Control Area | Primary Assets | Current Status | Proof Surface Required | Notes |
| --- | --- | --- | --- | --- |
| Manifest integrity | `governance/MANIFEST.sha256`, startup manifest checks | implemented now | manifest validation checks and regression coverage | Present-tense packaged control |
| Host-function registry control | `governance/host_functions.json`, packaged dispatch surfaces | bridge work | typed contract fields, denial-path tests, docs sync | Registry exists; typed effect proof is not complete. The embodied host-function family is present, but its shipped proof is still limited to supervisory contract enforcement and simulation-scoped dispatch. |
| Capsule boundary control | `hlf_mcp/hlf/capsules.py`, `hlf_mcp/server_capsule.py` | bridge work | capsule denial tests, approval-required responses, verifier-admission regressions, operator summary | Present and now proof-aware, but not yet the full privilege story |
| Pointer trust and memory reference control | `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/hlf/runtime.py`, `hlf_mcp/server_memory.py` | bridge work | pointer-validation tests, revocation and freshness checks | Strong recent bridge slice |
| Route admission control | routing recovery surfaces, benchmark artifacts, policy basis, persisted execution-admission join | bridge work | route trace contract, denial-path tests, route evidence resources, execution-admission artifact regressions | Route evidence now binds to persisted execution admission and audit refs, but wider orchestration lineage is still bridge work. Embodied-risk routing consequences are not yet fully integrated beyond the current host-call and runtime slice. |
| Formal verification control | `hlf_mcp/hlf/formal_verifier.py`, `hlf_mcp/hlf/execution_admission.py`, runtime/capsule proof gating | bridge work | verifier reports, admission denial regressions, operator proof summaries, route-bound admission traces | Packaged proof and admission surfaces now bind to governed route evidence and audit outputs, but deeper orchestration-state and promotion integrations remain bridge work. Embodied action envelopes are not yet threaded through deeper verifier-backed spatial or motion proof. |
| Memory evidence governance | `hlf_mcp/rag/memory.py`, `hlf_mcp/server_memory.py`, weekly artifacts | bridge work | unified evidence schema, stale-artifact tests, provenance requirements | Batch 1 priority |
| Lifecycle verification and merge control | `hlf_mcp/instinct/lifecycle.py`, packaged orchestration recovery | bridge work | lifecycle transition tests, execution trace proofs | Batch 2 priority |
| Operator-readable audit control | server resources, audit chain, generated reports, governed route status resources | bridge work | operator summaries grounded in structured evidence objects, persisted audit refs, execution-admission resource coverage | Governed route status now exposes route plus execution-admission evidence together, but broader cross-surface audit unification remains bridge work. Embodied-specific operator-resource summaries are not yet complete. |

## Working Rule

No governance claim should be promoted to packaged truth unless its control row has both:

1. a packaged asset boundary
2. a named proof surface
