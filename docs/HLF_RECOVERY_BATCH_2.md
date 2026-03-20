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
| Audit spine completion | bridge contract | `hlf_source/scripts/verify_chain.py`, trust-chain and manifest source clusters | `scripts/verify_chain.py`, operator/audit surfaces under `docs/` and packaged proof-facing resources | audit and operator proof layer |
| Research intake and promotion boundary | bridge contract | weekly workflow and evidence source clusters, autonomous-evolution bridge plan | `hlf_mcp/weekly_artifacts.py`, `.github/scripts/emit_weekly_artifact.py`, `scripts/run_pipeline_scheduled.py`, triage-facing docs and future queue surfaces | governed evidence intake layer |

## Required Tests

- lifecycle transition and realignment regressions
- plan DAG ordering and dependency regressions
- verifier-backed execution denial and admission regressions
- memory supersession and expiry regressions
- weekly evidence schema and second-pass verification regressions
- audit proof-object and trust-chain summary regressions
- research-intake classification versus promotion-gate regressions

## Required Docs Updates

- `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md`
- `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md`
- `plan/feature-autonomous-evolution-1.md`
- `SSOT_HLF_MCP.md` only after new packaged truth is actually landed

## Acceptance Gates

1. Lifecycle state machine is connected to real plan execution artifacts.
2. Delegation, escalation, and verification states are explicit and testable.
3. Verifier output participates in execution-admission logic or explicit operator review.
4. Memory freshness and supersession semantics are enforced where orchestration consumes evidence.
5. Weekly research and automation findings remain advisory on intake and cannot affect promotion without deterministic provenance verification.
6. Audit-spine outputs are operator-readable and grounded in verifiable chain or manifest evidence rather than free text alone.
7. Trust-surface overhead and predictability have at least one benchmark lane for Merkle overhead, gas predictability, or verification latency.
