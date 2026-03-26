# HLF Agent Operating Protocol

This document is the execution-layer companion to [AGENTS.md](../AGENTS.md).

Use it when work touches architecture, recovery, doctrine, governance, claim-lane wording, or any change that could quietly narrow HLF into a weaker story than the repo is actually meant to preserve.

## 1. Authority Boundary

- [AGENTS.md](../AGENTS.md) is the constitutional handover.
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md) is the executable current-truth surface.
- This protocol governs how agents classify, compare, escalate, and report work.
- [docs/HLF_CLAIM_LANES.md](./HLF_CLAIM_LANES.md) remains the wording-classification authority.

## 2. When This Protocol Applies

Use this protocol for:

- architecture work
- recovery or extraction work
- doctrine-sensitive edits
- governance-sensitive edits
- claim-lane-sensitive wording or summaries
- major repo reviews

Do not burden small bounded edits with the full protocol unless those edits materially affect architecture, trust, or product-positioning truth.

## 3. Lightweight Mode vs High-Rigor Mode

### Lightweight mode

Use for:

- small bugfixes
- narrow implementation edits
- local improvements that do not change doctrine, claim lane, or constitutive-surface judgment

Minimum expectations:

- do not overstate truth
- do not flatten constitutive surfaces
- report exclusions if review coverage was partial

### High-rigor mode

Use for:

- architectural changes
- recovery or reconstruction work
- doctrine or governance changes
- wording that affects current-truth, bridge, or vision claims
- any judgment that a surface is optional, superseded, or non-constitutive

Minimum expectations:

- classify the lane
- classify the work type
- compare before dismissing
- escalate material ambiguity
- use the audit system when required

## 4. Required Pre-Work By Task Type

### Architecture or recovery work

Read:

- [AGENTS.md](../AGENTS.md)
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
- [HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
- [HLF_SOURCE_EXTRACTION_LEDGER.md](../HLF_SOURCE_EXTRACTION_LEDGER.md)
- [HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md](../HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md)

### Wording, positioning, or maturity claims

Read:

- [AGENTS.md](../AGENTS.md)
- [SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md)
- [docs/HLF_CLAIM_LANES.md](./HLF_CLAIM_LANES.md)

### Operator-facing handoff or onboarding work

Read:

- [AGENTS.md](../AGENTS.md)
- [docs/HLF_AGENT_ONBOARDING.md](./HLF_AGENT_ONBOARDING.md)
- [docs/HLF_MCP_AGENT_HANDOFF.md](./HLF_MCP_AGENT_HANDOFF.md)

## 5. Lane Classification Procedure

Every major task must be classified into one lane before editing:

- vision: north-star doctrine, intended end-state, not present-tense product truth
- current truth: implemented, validated, and safe to assert in present tense now
- bridge: bounded work that connects current truth toward the intended target without overstating completion

If material in multiple lanes is present, do not collapse it into one story. State which part belongs to which lane.

## 6. Work Type Classification Procedure

Every major architecture, recovery, doctrine, or claim-sensitive task must be classified as one of:

- restoration
- faithful port
- bridge implementation
- current-truth validation

If none of these fit cleanly, classify conservatively as bridge work and explain why.

## 7. Constitutive Surface Test

Use this test before calling a surface optional or supportive:

If removing the surface narrows HLF from a governed coordination and execution language into a weaker parser-runtime fragment, the surface is not merely supportive.

Practical signs that a surface is constitutive:

- it changes admission, routing, governance, verifier linkage, or execution semantics
- it changes provenance, memory trust, or auditability
- it changes operator legibility in a way that reduces governability or inspectability

## 8. Comparison Before Dismissal

Before declaring a surface optional, superseded, or out of scope:

1. compare source, doctrine, and packaged truth
2. identify what semantics would be lost
3. state any exclusions explicitly
4. classify the claim lane before reusing the conclusion elsewhere

If equivalence is not proven, do not silently downgrade the stronger surface.

## 9. Escalation Thresholds

Escalate when ambiguity materially affects:

- architecture
- scope
- correctness
- claim lane
- constitutive-surface judgment

Do not escalate for trivial wording uncertainty that does not change technical meaning.

If escalation is required, surface the ambiguity directly instead of inventing a silent interpretation.

## 10. Review Procedure

During review, answer these questions explicitly:

1. Is the claim current truth, bridge, or vision?
2. Has a constitutive surface been flattened into a weaker substitute?
3. Does the change preserve operator trust, governance legibility, and architectural intent?
4. Does the change increase real capability, or does it merely make the package look tidier?

If wording is part of the review, classify it with [docs/HLF_CLAIM_LANES.md](./HLF_CLAIM_LANES.md) before reuse.

## 11. Reporting Rules

Final summaries should:

- distinguish current truth from bridge and vision
- state what was actually verified
- state any material exclusions
- avoid promoting bounded bridge work into present-tense completion

## 12. Relationship To Audit System

Use [docs/HLF_AUDIT_SYSTEM.md](./HLF_AUDIT_SYSTEM.md) when work is high-risk enough to require backward-verifiable records.

Do not create audit artifacts mechanically for every small edit.

## 13. Anti-Patterns

Do not do the following:

- silently overstate maturity
- replace a constitutive surface with a thinner pseudo-equivalent
- imply full review coverage when exclusions exist
- collapse current truth, bridge, and vision into one flattened claim

## 14. Compact Checklist

- lane classified
- work type classified
- constitutive test applied if needed
- comparison performed before dismissal if needed
- ambiguity escalated if materially outcome-changing
- audit system used if required
- final wording kept in the correct lane
