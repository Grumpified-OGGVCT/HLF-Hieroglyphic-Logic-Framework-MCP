# Instinct Reference

Packaged Instinct lifecycle reference for this repository.

This document is grounded in `hlf_mcp/instinct/lifecycle.py`, which is the current standalone implementation surface. It replaces the broader upstream narrative with the state machine that actually ships here now.

## What Instinct Is Here

Instinct is a deterministic mission lifecycle manager for HLF-driven workflows. In the packaged repo, it is implemented as a thread-safe state machine with:

- sequential phase enforcement
- optional override-based escape hatches
- a verification gate before merge
- SHA-256 artifact sealing on merge
- an in-memory ledger of transitions

## Phase Model

The packaged lifecycle uses five phases:

1. `specify`
2. `plan`
3. `execute`
4. `verify`
5. `merge`

Allowed forward transitions are strictly linear:

```text
specify -> plan -> execute -> verify -> merge
```

## Gate Rules

The phase metadata currently encoded in `lifecycle.py` is:

| Phase | Description | Requires | Produces |
| --- | --- | --- | --- |
| `specify` | Mission is being specified | none | `mission_spec` |
| `plan` | Mission plan is being developed | `mission_spec` | `mission_plan` |
| `execute` | Mission is executing | `mission_plan` | `execution_artifacts` |
| `verify` | CoVE adversarial verification gate | `execution_artifacts` | `verification_report` |
| `merge` | Merging verified results | `verification_report` | `merged_state` |

Enforced behavior:

- new missions must start at `specify`
- backward transitions are blocked unless `override=True`
- skipped phases are blocked unless `override=True`
- `verify -> merge` is blocked if the CoVE gate does not pass

## Mission State Shape

Each mission is stored with:

- `mission_id`
- `current_phase`
- `phase_history`
- `artifacts`
- `created_at`
- `sealed`
- `seal_hash`
- `cove_gate_passed`
- `cove_failures`

Each phase artifact stores:

- the submitted payload
- a timestamp
- a SHA-256 hash of the payload

When a mission reaches `merge`, the lifecycle seals the mission by hashing the full artifact map and storing the result in `seal_hash`.

## API Surface

The packaged implementation exposes these primary methods on `InstinctLifecycle`:

| Method | Purpose |
| --- | --- |
| `step(...)` | Advance a mission to a target phase |
| `get_mission(mission_id)` | Return one mission snapshot |
| `list_missions()` | Return a summary of known missions |
| `get_ledger(mission_id=None)` | Return transition ledger entries |

`step(...)` accepts:

- `mission_id`
- `phase`
- `payload`
- `override`
- `cove_result`

## CoVE Gate Behavior

The packaged merge gate can pass in two ways:

1. Provide `cove_result={"passed": true}` explicitly.
2. Omit `cove_result` and let the lifecycle apply its built-in heuristic: merge is allowed only if a non-empty `verify` payload exists.

If the gate fails and no override is supplied, the lifecycle returns a blocked result instead of advancing the mission.

## Ledger Behavior

The lifecycle keeps an in-memory ledger containing:

- mission id
- event name
- phase
- timestamp
- payload hash

This is a useful deterministic audit surface, but it is not currently a durable persistence layer.

## Example

```python
from hlf_mcp.instinct.lifecycle import InstinctLifecycle

instinct = InstinctLifecycle()

instinct.step("mission-1", "specify", {"goal": "audit release"})
instinct.step("mission-1", "plan", {"tasks": ["compile", "test"]})
instinct.step("mission-1", "execute", {"result": "done"})
instinct.step("mission-1", "verify", {"report": "pass"})
instinct.step("mission-1", "merge", {"summary": "merged"}, cove_result={"passed": True})
```

## Boundaries

This repo currently ships the lifecycle state machine, not the entire upstream doctrine around broader crew orchestration, database persistence, or worktree automation. Treat `hlf_mcp/instinct/lifecycle.py` as the authoritative implementation surface.
