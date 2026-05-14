# HLF Persona Doctrine

## Lane Classification

**Claim lane: bridge-true**

This document defines the persona doctrine for HLF — the boundary between advisory guidance and authoritative enforcement for persona roles within the HLF governance and execution substrate.

## Persona Roles

HLF recognizes the following persona roles. Each has defined permissions sourced from `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json`.

### Core Operational Personas

| Role        | Internal Role               | Tier   | Runtime Authority |
|-------------|-----------------------------|--------|-------------------|
| planner     | planning_authority          | tier_1 | advisory only     |
| executor    | execution_agent             | tier_1 | advisory only     |
| verifier    | verification_agent          | tier_1 | advisory only     |
| scribe      | documentation_agent         | tier_1 | advisory only     |
| operator    | human_operator              | tier_0  | authoritative     |

### Governance Personas

| Role        | Internal Role               | Tier   | Runtime Authority |
|-------------|-----------------------------|--------|-------------------|
| strategist  | planning_authority          | tier_1 | advisory only     |
| steward     | workflow_integrity_reviewer | tier_1 | advisory only     |
| sentinel    | security_boundary_reviewer  | tier_1 | advisory only     |
| herald      | documentation_truth_reviewer| tier_1 | advisory only     |
| chronicler  | drift_and_debt_reviewer     | tier_1 | advisory only     |
| cove        | final_validation_gate       | tier_1 | advisory only     |

## Advisory vs Authoritative Boundary

### Advisory (Guidance Only)

Persona doctrine is **advisory** in these contexts:

1. **Agent self-classification** — agents may tag themselves with a persona role for routing and audit purposes, but this tag does not confer runtime authority.
2. **Workflow role assignment** — swarm mechanics assign planner/executor/verifier roles as organizational labels; these are routing hints, not permission grants.
3. **Handoff lineage tracking** — `source_persona` and `target_persona` fields on handoff events are audit-trail metadata; they do not gate or block handoff execution.
4. **Gate review sequencing** — `required_gates` in the persona ownership matrix define recommended review order; skipping a gate generates a warning, not a block, unless the gate is operator-gated.
5. **Persona contract validation** — `validate_persona_contract` checks structural conformance; failures produce diagnostic errors for operator review but do not halt compilation or execution.

### Authoritative (Hard Enforcement)

Persona doctrine is **authoritative** in these contexts:

1. **Operator promotion gate** — the `operator_promotion` gate in the persona matrix is the only hard gate. A change cannot be promoted from bridge to current-truth without operator approval.
2. **CoVE merge gate** — the Verify→Merge transition in the Instinct lifecycle requires the cove persona's final validation gate, enforced by `hlf_instinct_step` phase rules.
3. **Sentinel blocking** — on `security_sensitive` change classes, sentinel review status `blocked` prevents promotion regardless of other gate statuses.
4. **Runtime authority** — no persona except `operator` carries `runtime_authority: true`. All other personas operate in advisory mode; the matrix explicitly sets `live_packaged_runtime_authority: false` and `upstream_persona_prompts_are_runtime_governors: false`.

## Compile-Time vs Runtime

### Compile-Time Persona Constraints

- Persona contract schema validation (`validate_persona_contract`) runs at packaging/validation time
- Handoff event schema enforcement requires `source_persona` and `target_persona` fields (validated via JSON Schema)
- Persona ownership matrix is loaded at module import time and cached

### Runtime Persona Constraints

- Persona lineage tracking on handoff chains (`persona_transitions`) is computed at query time
- Gate status evaluation in `resolve_persona_contract` runs on each call
- Instinct lifecycle phase transitions with CoVE gating are runtime-enforced

### NOT Enforced (Bridge Gap)

The following are documented as bridge gaps — not yet implemented:

- Cross-persona capability verification at handoff time
- Persona-based tool access control in the HLF VM
- Persona-aware gas accounting
- Operator-override audit trails for persona gate bypass

## Handoff Event Persona Fields

Every conformant HLF handoff event now carries:

```json
{
  "source_persona": "planner",
  "target_persona": "executor"
}
```

These fields are:
- **Required** by the handoff event JSON schema (`hlf-handoff-event-v1`)
- **Advisory** for execution — they do not gate or block handoff
- **Traceable** through `persona_lineage` in handoff chain verification

## Cross-Persona Handoff Lineage

The `hlf_handoff_chain` tool returns a `persona_lineage` graph showing:
- All persona roles present in the chain
- Each source→target persona transition
- The event hash and lifecycle phase for each transition

This enables auditability of persona role handoffs without introducing runtime authority for non-operator personas.

## Relationship to Other Surfaces

- `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` — data authority for persona definitions
- `hlf_mcp/persona_contract.py` — resolution and validation logic
- `hlf_mcp/persona_runtime.py` — runtime metadata catalog
- `hlf_mcp/handoff_events.py` — handoff event schema with persona fields
- `hlf_mcp/server_handoff.py` — MCP tool surface for persona-tagged handoffs
- `hlf_mcp/instinct/lifecycle.py` — task-type-to-persona-role mapping

## Version

- **Schema version**: 1.0
- **Last updated**: 2026-03-24
- **Status**: active-bridge-contract
