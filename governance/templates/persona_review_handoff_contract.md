# Persona Review Handoff Contract

## Purpose

This document describes the surfaced operator-facing form of the persona handoff contract.

Use it alongside `persona_review_handoff.md`:

- `persona_review_handoff.md` defines what reviewers must check and how promotion gating works.
- `persona_review_handoff_contract.md` defines how the normalized contract should appear when exposed in packaged operator surfaces.

## Surfaces

The current packaged surfaces that should expose this contract are:

- `hlf-evidence show <artifact-id>` plain-text output
- `.github/scripts/governed_review_contract.py` rendered evolution issue markdown

## Required Surfaced Fields

- `change_class`
- `lane`
- `owner_persona`
- `review_personas`
- `required_gates`
- `escalate_to_persona`
- `operator_summary`
- `handoff_template_ref`

## Canonical Wording Shape

### GitHub Issue Markdown

```md
## Persona Handoff

- Change class: planning_only
- Lane: bridge-true
- Owner persona: strategist
- Review personas: chronicler, cove
- Required gates: strategist_review, chronicler_review, cove_review, operator_promotion
- Escalate to: none
- Operator summary: Owner persona strategist; review personas chronicler, cove; required gates strategist_review, chronicler_review, cove_review, operator_promotion.
- Handoff template: `governance/templates/persona_review_handoff.md`
```

### `hlf-evidence show` Plain Output

```text
Governed review:
  Summary: No governed review contract was attached for weekly-code-quality.
  Severity: info
  Change class: security_sensitive
  Owner persona: sentinel
  Review personas: strategist, steward, cove
  Required gates: strategist_review, sentinel_review, steward_review, cove_review, operator_promotion
  Escalate to: none
  Operator summary: Owner persona sentinel; review personas strategist, steward, cove; required gates strategist_review, sentinel_review, steward_review, cove_review, operator_promotion.
  Handoff template: governance/templates/persona_review_handoff.md
```

## Stability Rule

The wording and ordering of surfaced fields should remain stable unless the normalized persona contract itself changes. If wording changes, update:

- the renderer tests
- the CLI docs
- this contract reference

## Authority Boundary

This surfaced contract is advisory and operator-facing.

It does not replace:

- claim-lane discipline
- required persona reviews
- operator promotion authority
- the underlying normalized governed review payload