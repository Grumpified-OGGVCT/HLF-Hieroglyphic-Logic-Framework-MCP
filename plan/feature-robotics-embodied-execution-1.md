---
goal: Implement the first packaged embodied-execution boundary for robotics and physical-world action without overstating current real-time capability
version: 1.0
date_created: 2026-03-22
last_updated: 2026-03-22
owner: GitHub Copilot
status: 'In progress'
tags: [feature, robotics, embodied, safety, verifier, routing, hlf]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This feature plan defines the first bounded robotics and embodied-execution recovery slice.

The goal is not to turn packaged HLF into a hard-real-time motor controller.

The goal is to add a governed supervisory boundary where physical-world evidence, action requests, safety envelopes, approval rules, and operator audit all share one explicit contract.

## 1. Requirements & Constraints

- **REQ-001**: Treat robotics as a supervisory and coordination lane first, not as a replacement for low-level control loops.
- **REQ-002**: Add typed embodied capability contracts for sensor evidence, world-state access, guarded actuation, and emergency stop semantics.
- **REQ-003**: Require verifier and capsule policy to participate before embodied actions are admitted.
- **REQ-004**: Preserve audit, witness, and operator-readable explanation across the whole embodied action path.
- **REQ-005**: Keep simulation, replay, or mock-hardware validation in scope before stronger physical-world claims are promoted.
- **CON-001**: Do not claim hard-real-time guarantees from the current packaged Python runtime.
- **CON-002**: Do not claim collision avoidance, medical safety, or autonomous-vehicle readiness without domain-specific proof surfaces.
- **CON-003**: Do not add robotics-specific effects as ad hoc tool calls; they must live inside explicit host-function and governance contracts.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the packaged embodied capability contract.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-001|Define embodied host-function contract families for `sensor_read`, `world_state_recall`, `trajectory_propose`, `guarded_actuate`, and `emergency_stop`.|✅|2026-03-22|
|TASK-002|Extend governance metadata so embodied effects carry safety class, failure type, audit requirement, and review posture.|✅|2026-03-22|
|TASK-003|Define the action-envelope schema: requested action, target object or frame, bounds, timeout, operator intent, and required evidence refs.|✅|2026-03-22|

### Implementation Phase 2

- **GOAL-002**: Bind embodied actions into existing packaged trust seams.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-004|Thread embodied action requests through capsule validation and execution-admission policy.|||
|TASK-005|Extend the formal verifier path so action envelopes can prove simple bounds such as range, timeout, workspace, or disallowed mode violations.|||
|TASK-006|Bind route, approval, and witness consequences to embodied-risk classes so unsafe requests fail closed or require review.|||
|TASK-006A|Use the audited external robotics rows in `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` as explicit bounded donors for this phase: compare command and status structure to `CRCL`, controller-boundary semantics to `URScript`, verifier-coupled DSL admission to `RSL` and `LTLCodeGen`, and lifecycle-guard structure to `BehaviorTree.CPP` without importing any of those names into packaged current-truth claims.|||

### Implementation Phase 3

- **GOAL-003**: Establish embodied evidence and operator proof surfaces.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-007|Add world-state or sensor-evidence pointer contracts so physical evidence is referenced through governed memory rather than raw opaque blobs.|||
|TASK-008|Add operator-readable summaries explaining why an embodied action was admitted, denied, or escalated.|||
|TASK-009|Add audit-linked evidence refs so post-action review can reconstruct operator intent, evidence basis, verifier outcome, and final action verdict.|||

### Implementation Phase 4

- **GOAL-004**: Prove the first slice without overclaiming live hardware capability.

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-010|Add simulation, mock-hardware, or replay-backed tests for embodied action admission and denial paths.|✅|2026-03-22|
|TASK-011|Add negative tests for missing sensor evidence, unsafe workspace bounds, stale world-state pointers, and required emergency-stop posture.|||
|TASK-012|Keep all claims at the supervisory embodied boundary until real simulator or hardware proof exists.|||

Current checkpoint validated on 2026-03-22:

- `governance/host_functions.json` now defines the first supervisory embodied host-function family
- `hlf_mcp/hlf/embodied.py` now provides packaged action-envelope helpers and embodied contract assessment
- `hlf_mcp/server_capsule.py` now routes embodied review posture through the existing approval path for `hlf_host_call`
- `hlf_mcp/hlf/runtime.py` now returns structured simulation-only embodied results for the new embodied host functions
- focused regression coverage now proves registry metadata, approval-required guarded actuation, missing-evidence denial, generated host-function docs, and runtime simulation behavior
- the current embodied implementation is supervisory and simulation-scoped, not a claim of production robotics execution
- embodied action envelopes are not yet threaded through deeper verifier-backed spatial or motion proof
- execution-admission, route, witness, and operator-resource integration for embodied actions is not yet complete beyond the current host-call and runtime slice
- host-contract pointer fields such as `world_state_ref` and `evidence_refs` now exist, but deeper governed-memory and operator-surface integration remains future work in this plan

## 3. Files

- `governance/host_functions.json`
- packaged embodied helper surface under `hlf_mcp/hlf/`
- `hlf_mcp/hlf/formal_verifier.py`
- `hlf_mcp/hlf/execution_admission.py`
- `hlf_mcp/hlf/capsules.py`
- `hlf_mcp/server_capsule.py`
- `hlf_mcp/server_resources.py`
- embodied and simulation-focused tests under `tests/`

## 4. Testing

- mock or simulated sensor-evidence admission tests
- verifier-backed action-envelope tests
- fail-closed missing-evidence tests
- approval-required high-risk actuation tests
- operator-resource tests for embodied action summaries

## 5. Risks & Assumptions

- **RISK-001**: Robotics language can drift into overclaim if supervisory control is confused with low-level real-time control.
- **RISK-002**: Embodied capabilities could become ad hoc without an explicit effect and evidence schema.
- **ASSUMPTION-001**: The existing verifier, capsule, routing, audit, witness, and memory seams are the right base for the first embodied slice.
- **ASSUMPTION-002**: Simulation or replay validation is sufficient for the first packaged claim lane, while live hardware remains a later bridge step.
