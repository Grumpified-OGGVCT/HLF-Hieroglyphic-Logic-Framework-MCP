# HLF Recovery Batch 2

Status: planned executable restoration batch for multi-agent execution and proof.

## Batch Goal

Recover orchestration lifecycle and verifier-backed execution admission once Batch 1 trust surfaces are established.

## Included Pillars

| Pillar | Recovery Mode | Upstream Files | Target Files | Owner Module |
| --- | --- | --- | --- | --- |
| Orchestration lifecycle | faithful port | `hlf_source/agents/core/plan_executor.py`, `hlf_source/agents/core/crew_orchestrator.py`, `hlf_source/agents/core/task_classifier.py` | `hlf_mcp/instinct/lifecycle.py`, `hlf_mcp/server_instinct.py`, packaged orchestration modules under `hlf_mcp/instinct/` | packaged orchestration layer |
| Typed effect algebra | faithful port | `hlf_source/governance/hls.yaml`, `hlf_source/agents/core/formal_verifier.py` | governance references plus packaged verifier and tool-contract boundaries | governance and verifier boundary |
| Verifier-backed execution admission | bridge contract | verifier and orchestration source clusters | runtime, capsule, and orchestration touch points in `hlf_mcp/hlf/` and `hlf_mcp/instinct/` | packaged proof and admission layer |
| Memory freshness and supersession enforcement | faithful port / bridge | `hlf_source/agents/core/context_pruner.py`, `hlf_source/scripts/verify_chain.py` | `hlf_mcp/rag/memory.py`, `hlf_mcp/hlf/memory_node.py`, `hlf_mcp/server_memory.py` | packaged memory governance layer |

## Required Tests

- lifecycle transition and realignment regressions
- plan DAG ordering and dependency regressions
- verifier-backed execution denial and admission regressions
- memory supersession and expiry regressions

## Required Docs Updates

- `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md`
- `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `SSOT_HLF_MCP.md` only after new packaged truth is actually landed

## Acceptance Gates

1. Lifecycle state machine is connected to real plan execution artifacts.
2. Delegation, escalation, and verification states are explicit and testable.
3. Verifier output participates in execution-admission logic or explicit operator review.
4. Memory freshness and supersession semantics are enforced where orchestration consumes evidence.
