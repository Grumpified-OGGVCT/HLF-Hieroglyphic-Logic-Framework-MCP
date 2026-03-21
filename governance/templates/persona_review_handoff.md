# Persona Review Handoff

## Purpose

Use this handoff when a governed review has been normalized with persona ownership fields and needs bounded operator review, promotion, or escalation handling.

## Required Fields

- `change_class`
- `lane`
- `owner_persona`
- `review_personas`
- `required_gates`
- `gate_results`
- `escalate_to_persona`
- `operator_summary`
- `handoff_template_ref`

## Handoff Checklist

1. Confirm the governed review is still in the correct claim lane for the change.
2. Confirm the `owner_persona` matches the change class in the persona ownership matrix.
3. Review all `required_gates` and record a terminal state or explicit note in `gate_results`.
4. If `escalate_to_persona` is present, route the review before promotion.
5. Preserve operator promotion as the final authority boundary.

## Gate Notes Format

- `status`: approved, revise, defer, blocked, escalate, not_applicable, promote, hold, or reject as allowed by the gate
- `notes`: concise rationale tied to evidence or blocking condition

## Promotion Rule

No governed artifact should be promoted if any required persona gate is missing, blocked, deferred, escalated, or held.

## Related Reference

For the operator-facing surfaced form of this contract in CLI and GitHub issue artifacts, see `governance/templates/persona_review_handoff_contract.md`.