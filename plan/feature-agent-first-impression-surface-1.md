---
goal: Recover an agent-facing first-impression surface that makes HLF's coordination, authority, and memory value legible at first contact
version: 1.0
date_created: 2026-03-23
last_updated: 2026-03-23
owner: GitHub Copilot
status: 'Planned'
tags: [feature, bridge, agent, onboarding, protocol, operator, hlf]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a bridge-lane implementation for the agent-facing first-impression surface of packaged HLF MCP. The problem is not lack of doctrine. The problem is that an arriving agent currently encounters governance, audit, and tool inventory before it encounters HLF as a shared operating language for agent-to-agent coordination, capability negotiation, governed memory reuse, and model-class-agnostic intent handoff.

The goal of this plan is to make that value legible through concrete packaged affordances rather than through aspirational wording. The first shippable slice is a narrow, resource-backed front door that exposes protocol semantics, current authority, and immediate next actions for an arriving agent without inventing a parallel product or flattening HLF into prose-only explanation.

Lane classification:

- primary lane: bridge
- work type: bridge implementation over current packaged truth
- first host: packaged MCP resources, server instructions, and operator CLI
- non-goal: rewrite the repo story into marketing language or claim full multi-agent completion before the bounded surface is real

## 1. Requirements & Constraints

- **REQ-001**: Make HLF legible at first contact as an agent-to-agent and agent-to-tool protocol, not only as a governed tool menu.
- **REQ-002**: Surface the capsule tier model as both authority boundary and capability-negotiation contract.
- **REQ-003**: Surface the Instinct lifecycle and governed routing seams as bounded coordination substrates that already exist in packaged form, while preserving bridge qualifiers where required.
- **REQ-004**: Preserve the three-lane doctrine explicitly: current packaged truth, bridge-qualified coordination value, and larger vision must not collapse into one flat story.
- **REQ-005**: The first slice must be reachable through the current packaged FastMCP front door without requiring a separate GUI, extension host, or notebook shell.
- **REQ-006**: The first slice must make an arriving agent's immediate working loop obvious: what HLF is, what authority the agent has, what memory and coordination surfaces are reachable, and what next actions are recommended.
- **REQ-007**: The first slice must reuse existing packaged truth from resources, operator CLI surfaces, and server instructions instead of creating a second doctrine or summary authority.
- **REQ-008**: The first slice must expose a handoff contract showing that one agent can emit HLF intent and another can consume it without semantic drift, even if the full multi-agent orchestration target remains bridge-qualified.
- **REQ-009**: The first slice must expose model-class agnosticism in practical terms: local, cloud-via-Ollama, and remote-direct lanes can all participate in the same HLF meaning layer.
- **REQ-010**: The first slice must remain deterministic and queryable through packaged resources so tests can validate the surfacing directly.
- **SEC-001**: No new agent-facing surface may imply authority that is not actually packaged and testable in this checkout.
- **SEC-002**: No new surface may hide denial states, bridge qualifiers, provenance gaps, or missing coordination pillars.
- **SEC-003**: No new surface may introduce opaque model-generated onboarding summaries as the canonical first-contact layer.
- **CON-001**: Do not solve this by rewriting only `README.md`; first-contact value must become visible through packaged MCP affordances.
- **CON-002**: Do not create a parallel education subsystem, alternative datastore, or second protocol schema.
- **CON-003**: Do not describe un-restored upstream gateway or orchestration completion as present-tense packaged truth.
- **GUD-001**: Prefer small additive resources and instruction synthesis over a broad new onboarding framework.
- **GUD-002**: Keep each resource contract explicit enough that another agent can consume it deterministically with no extra repo archaeology.
- **PAT-001**: Build the first slice as resource-backed discovery plus instruction synthesis plus thin operator entrypoints.

### 1.1 Resource Contracts

The first bridge slice should add the following packaged resource contracts.

#### RC-001: `hlf://agent/protocol`

Purpose:

- Explain HLF to an arriving agent as a shared meaning-and-handoff protocol.

Required fields:

- `status`
- `operator_summary`
- `protocol_identity`
- `what_hlf_is_not`
- `agent_to_agent_contract`
- `agent_to_tool_contract`
- `capsule_tiers`
- `coordination_surfaces`
- `memory_surfaces`
- `model_lane_compatibility`
- `source_refs`
- `next_actions`

Current-truth anchors:

- `hlf://status/operator_surfaces`
- `hlf://status/governed_route`
- `hlf://status/instinct`
- `hlf://status/witness_governance`
- `hlf://status/memory_governance`
- `SSOT_HLF_MCP.md`

#### RC-002: `hlf://agent/quickstart`

Purpose:

- Give an arriving agent the minimum deterministic working loop for participation.

Required fields:

- `status`
- `operator_summary`
- `current_authority_model`
- `first_calls`
- `recommended_resources`
- `hll_to_hlf_entrypoints`
- `handoff_pattern`
- `memory_pattern`
- `coordination_pattern`
- `do_not_assume`

Current-truth anchors:

- `hlf_do`
- `hlf_translate_to_hlf`
- `hlf://status/ingress`
- `hlf://status/operator_surfaces`
- packaged operator CLI commands in `hlf_mcp/operator_cli.py`

#### RC-003: `hlf://agent/handoff_contract`

Purpose:

- Show the bounded packaged handoff story in one place.

Required fields:

- `status`
- `operator_summary`
- `canonical_units`
- `producer_roles`
- `consumer_roles`
- `required_authority_checks`
- `example_handoff_sequence`
- `semantic_drift_controls`
- `bridge_gaps`
- `source_refs`

Current-truth anchors:

- packaged compiler, translator, bytecode, capsule, and server resources
- existing explainers or reports where available

#### RC-004: `hlf://agent/current_authority`

Purpose:

- Explain what the current tier means to the arriving agent in actionable terms.

Required fields:

- `status`
- `operator_summary`
- `capsule_tier_model`
- `allowed_categories`
- `bounded_actions`
- `requires_operator_promotion`
- `governance_surfaces`
- `recommended_safe_next_steps`

Current-truth anchors:

- capsules
- ingress surfaces
- approval and witness surfaces where relevant

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the bounded front-door contract and place it in the packaged operator-surface taxonomy.

| Task     | Description                                                                 | Completed | Date       |
|----------|-----------------------------------------------------------------------------|-----------|------------|
| TASK-001 | Create the authoritative bridge plan artifact.                              | ✅        | 2026-03-23 |
| TASK-002 | Define four `hlf://agent/...` contracts in `server_resources.py`.          |           |            |
| TASK-003 | Place the new surfaces in the operator-surface taxonomy doc.                |           |            |
| TASK-004 | Map every contract field to packaged truth or an explicit bridge qualifier. |           |            |

### Implementation Phase 2

- **GOAL-002**: Make the packaged MCP front door itself expose the right first-impression value.

| Task     | Description                                                                      | Completed | Date |
|----------|----------------------------------------------------------------------------------|-----------|------|
| TASK-005 | Update `hlf_mcp/server_instructions.py` to lead with protocol value.             |           |      |
| TASK-006 | Add an `AGENT ARRIVAL` section covering identity, authority, and next actions. |           |      |
| TASK-007 | Keep `hlf_mcp/server.py` regenerating instructions from registered surfaces.     |           |      |
| TASK-008 | Preserve current-truth anchors and explicit bridge qualifiers.              |           |      |

### Implementation Phase 3

- **GOAL-003**: Implement the first shippable slice as packaged resources and thin CLI entrypoints.

| Task     | Description                                                                            | Completed | Date |
|----------|----------------------------------------------------------------------------------------|-----------|------|
| TASK-009 | Implement `hlf://agent/protocol` from operator, backend, and capsule truth. |           |      |
| TASK-010 | Implement `hlf://agent/quickstart` with the arriving-agent working loop.               |           |      |
| TASK-011 | Implement `hlf://agent/handoff_contract` with one bounded packaged handoff sequence.   |           |      |
| TASK-012 | Implement `hlf://agent/current_authority` around capsule and promotion boundaries.     |           |      |
| TASK-013 | Add thin `hlf-operator` entrypoints for the four agent-facing resources.               |           |      |

### Implementation Phase 4

- **GOAL-004**: Prove that the first-impression surface is actually better in deterministic, testable ways.

| Task     | Description                                                                             | Completed | Date |
|----------|-----------------------------------------------------------------------------------------|-----------|------|
| TASK-014 | Add registration tests for the four new `hlf://agent/...` resources.      |           |      |
| TASK-015 | Add payload tests for protocol semantics, model lanes, and next actions.  |           |      |
| TASK-016 | Add instruction tests proving initialize output mentions the arriving-agent loop.       |           |      |
| TASK-017 | Add CLI tests for JSON rendering through packaged resource commands.                    |           |      |
| TASK-018 | Add a discoverability regression using instructions plus one resource read.             |           |      |

### Implementation Phase 5

- **GOAL-005**: Record the slice honestly and stage the follow-on expansion.

| Task     | Description                                                                      | Completed | Date |
|----------|----------------------------------------------------------------------------------|-----------|------|
| TASK-019 | Update `SSOT_HLF_MCP.md` after implementation and tests land.                    |           |      |
| TASK-020 | Keep `HLF_ACTIONABLE_PLAN.md` pointed at this front-door legibility track.       |           |      |
| TASK-021 | Link this plan to comprehension and visual-host follow-on plans.                 |           |      |
| TASK-022 | Defer richer onboarding hosts until packaged resources and tests are stable.     |           |      |

## 3. Alternatives

- **ALT-001**: Rewrite `README.md` to sound more exciting. Rejected because wording alone does not change first-contact agent affordances.
- **ALT-002**: Fold this work into `plan/feature-native-comprehension-mode-1.md` only. Rejected because first-impression protocol legibility is narrower and more foundational than the broader native-comprehension surface.
- **ALT-003**: Start with a VS Code webview or extension-host onboarding shell. Rejected because the packaged MCP front door must become legible before any richer host is justified.
- **ALT-004**: Expose only a plain-English explainer resource. Rejected because the arriving agent also needs authority, handoff, memory, and next-action contracts, not prose alone.

## 4. Dependencies

- **DEP-001**: `AGENTS.md`
- **DEP-002**: `/memories/repo/HLF_MCP.md`
- **DEP-003**: `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- **DEP-004**: `docs/HLF_CLAIM_LANES.md`
- **DEP-005**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- **DEP-006**: `SSOT_HLF_MCP.md`
- **DEP-007**: `plan/feature-native-comprehension-mode-1.md`
- **DEP-008**: `plan/architecture-visual-operator-workbench-1.md`
- **DEP-009**: `hlf_mcp/server_resources.py`
- **DEP-010**: `hlf_mcp/server_instructions.py`
- **DEP-011**: `hlf_mcp/server.py`
- **DEP-012**: `hlf_mcp/operator_cli.py`
- **DEP-013**: `tests/test_fastmcp_frontdoor.py`
- **DEP-014**: `tests/test_operator_cli.py`

## 5. Files

- **FILE-001**: `plan/feature-agent-first-impression-surface-1.md` — authoritative bridge plan for agent-facing first-contact surfacing
- **FILE-002**: `hlf_mcp/server_resources.py` — packaged agent-facing resource contracts and derived payload builders
- **FILE-003**: `hlf_mcp/server_instructions.py` — generated initialize-time front-door instructions for arriving agents
- **FILE-004**: `hlf_mcp/server.py` — registration integration and instruction regeneration over actual registered resources
- **FILE-005**: `hlf_mcp/operator_cli.py` — thin operator commands for agent-facing resources
- **FILE-006**: `tests/test_fastmcp_frontdoor.py` — resource registration, payload, and discoverability regression coverage
- **FILE-007**: `tests/test_operator_cli.py` — CLI coverage for agent-facing front-door commands
- **FILE-008**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` — taxonomy placement for the new bridge-layer agent surface
- **FILE-009**: `SSOT_HLF_MCP.md` — post-implementation current-truth recording with bridge qualifier
- **FILE-010**: `HLF_ACTIONABLE_PLAN.md` — pointer to this bounded front-door bridge track

## 6. Testing

- **TEST-001**: Verify `hlf://agent/protocol`, `hlf://agent/quickstart`, `hlf://agent/handoff_contract`, and `hlf://agent/current_authority` are registered in the packaged FastMCP surface.
- **TEST-002**: Verify `hlf://agent/protocol` contains explicit fields for agent-to-agent semantics, agent-to-tool semantics, capsule negotiation, coordination surfaces, memory surfaces, and model-lane compatibility.
- **TEST-003**: Verify `hlf://agent/quickstart` returns a deterministic arriving-agent loop with first calls and recommended resources that point to real packaged surfaces.
- **TEST-004**: Verify `hlf://agent/handoff_contract` includes a bounded example handoff sequence and explicit semantic-drift controls tied to HLF compile or inspect paths.
- **TEST-005**: Verify `hlf://agent/current_authority` states what is allowed now, what is bounded, and what requires operator promotion.
- **TEST-006**: Verify the generated instructions from `hlf_mcp/server_instructions.py` include an arriving-agent section and point to the new agent-facing resources at initialize time.
- **TEST-007**: Verify the operator CLI commands for the new agent-facing resources render valid JSON and return success when the underlying resource status is `ok`.
- **TEST-008**: Verify first-impression improvement through deterministic discoverability criteria: an arriving agent can identify protocol identity, current authority, and next recommended actions from server instructions plus one targeted resource read.
- **TEST-009**: Run focused validation after implementation: `uv run pytest tests/test_fastmcp_frontdoor.py tests/test_operator_cli.py -q --tb=short`.

## 7. Risks & Assumptions

- **RISK-001**: The new surface could become a second doctrine layer if it stops deriving from current packaged truth and explicitly qualified bridge language.
- **RISK-002**: Overexplaining bridge value could accidentally overstate un-restored orchestration and routing completion.
- **RISK-003**: If the arriving-agent loop is too abstract, the new surface will still read as documentation rather than as an actionable front door.
- **RISK-004**: If the first slice ignores handoff semantics and focuses only on governance again, the core first-impression problem will remain unsolved.
- **ASSUMPTION-001**: The user wants a serious agent-facing operating surface, not a simplified beginner tutorial.
- **ASSUMPTION-002**: Existing packaged resources and instruction plumbing are already strong enough to support a bounded first-contact layer without new backend services.
- **ASSUMPTION-003**: Deterministic discoverability tests are the right way to prove the first-impression surface is better before attempting qualitative UX expansion.

## 8. Related Specifications / Further Reading

- `AGENTS.md`
- `/memories/repo/HLF_MCP.md`
- `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
- `docs/HLF_CLAIM_LANES.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `SSOT_HLF_MCP.md`
- `plan/feature-native-comprehension-mode-1.md`
- `plan/architecture-visual-operator-workbench-1.md`
