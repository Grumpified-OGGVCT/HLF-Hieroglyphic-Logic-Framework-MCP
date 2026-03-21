---
goal: Recover a self-healing parser and correction-assist lane for HLF without weakening canonical meaning or fail-closed execution
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'Planned'
tags: [feature, parser, diagnostics, correction, compiler, usability, bridge]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan defines a bounded self-healing parser and correction-assist lane for HLF. The target is not to make the compiler permissive or ambiguous. The target is to add governed correction suggestions, safe auto-repairs for a narrow class of syntax hygiene issues, and plain-language error explanations that lower adoption friction without weakening canonical meaning or execution safety.

## 1. Requirements & Constraints

- **REQ-001**: Keep the canonical parser deterministic and fail-closed; the correction lane may suggest or stage repairs, but it must not silently widen semantics.
- **REQ-002**: Support a first bounded correction set rooted in existing packaged behavior: homoglyph normalization, missing `Ω`, canonical tag casing, and a small dictionary of common tag or statement mistakes.
- **REQ-003**: Produce plain-language diagnostics that explain intent and likely fix, not only raw parser exceptions.
- **REQ-004**: Emit machine-readable correction suggestions with confidence, category, and proposed replacement so CLI, MCP, and future GUI surfaces can consume the same contract.
- **REQ-005**: Keep correction output separate from execution admission; repaired code must still pass compile, ALIGN, capsule, and verifier paths before execution.
- **REQ-006**: Allow a preview or dry-run repair mode before any auto-applied rewrite is accepted.
- **REQ-007**: Teach canonical HLF patterns through examples grounded in the actual grammar and formatter, not guessed prose.
- **SEC-001**: No repair path may rewrite a statement into a stronger side effect or different capability class without explicit operator visibility.
- **SEC-002**: No correction engine may bypass governance checks or downgrade parser/verifier errors into false success.
- **ARC-001**: This is a bridge-lane usability and adoption feature layered over the current compiler, linter, formatter, and translation surfaces.
- **CON-001**: Do not convert HLF into a loose best-effort language parser.
- **CON-002**: Do not silently auto-correct semantic intent when only syntax evidence is available.
- **GUD-001**: Prefer small, auditable correction classes first, then grow from real error telemetry.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Define the bounded correction contract and safe first correction classes.

- **TASK-001**: Define the canonical correction object shape for category, message, source span, confidence, suggested replacement, and whether the change is safe for auto-apply. Completed: No. Date: N/A.
- **TASK-002**: Classify the initial safe auto-repair set: homoglyph substitution, missing terminator insertion, canonical tag casing, and exact-match tag keyword repair. Completed: No. Date: N/A.
- **TASK-003**: Define out-of-scope classes for Phase 1 such as speculative semantic rewrites, effect-changing repairs, and multi-line structural rewrites. Completed: No. Date: N/A.

### Implementation Phase 2

- **GOAL-002**: Add parser and lint diagnostics that explain problems in plain language.

- **TASK-004**: Extend `hlf_mcp/hlf/compiler.py` exception shaping around `UnexpectedInput`, `UnexpectedToken`, and `UnexpectedCharacters` so parser failures can emit structured friendly diagnostics. Completed: No. Date: N/A.
- **TASK-005**: Add a reusable explanation layer that maps common parse and lint failures to plain-language guidance and canonical examples. Completed: No. Date: N/A.
- **TASK-006**: Integrate linter-derived suggestions from `hlf_mcp/hlf/linter.py` and formatter-derived canonicalization hints from `hlf_mcp/hlf/formatter.py`. Completed: No. Date: N/A.

### Implementation Phase 3

- **GOAL-003**: Add a bounded correction engine and staged repair preview.

- **TASK-007**: Implement a correction helper module under `hlf_mcp/hlf/` that proposes safe repairs without changing the authoritative parser grammar. Completed: No. Date: N/A.
- **TASK-008**: Add repair preview flows for CLI and MCP so users can request suggested fixed HLF and inspect diffs before accepting them. Completed: No. Date: N/A.
- **TASK-009**: Ensure repaired output is run back through canonical compile and lint flows before any success result is returned. Completed: No. Date: N/A.

### Implementation Phase 4

- **GOAL-004**: Expose the correction lane through packaged front-door surfaces.

- **TASK-010**: Define whether the first packaged front door is a new tool such as `hlf_repair` or an expansion of `hlf_validate` and `hlf_compile` results. Completed: No. Date: N/A.
- **TASK-011**: Add operator-readable examples showing invalid input, explanation, and suggested fix in docs and trust surfaces. Completed: No. Date: N/A.
- **TASK-012**: Bind correction telemetry into future weekly evidence or friction analysis so real failures drive later expansion. Completed: No. Date: N/A.

## 3. Alternatives

- **ALT-001**: Keep the current strict compiler and provide no correction assist. Rejected because it preserves correctness but leaves adoption friction unnecessarily high.
- **ALT-002**: Auto-rewrite all invalid HLF opportunistically. Rejected because it would destroy canonicality and operator trust.
- **ALT-003**: Rely only on natural-language translation to hide syntax errors. Rejected because direct HLF authoring and AI-generated HLF still need grounded syntax repair and explanation.

## 4. Dependencies

- **DEP-001**: `hlf_mcp/hlf/compiler.py`
- **DEP-002**: `hlf_mcp/hlf/linter.py`
- **DEP-003**: `hlf_mcp/hlf/formatter.py`
- **DEP-004**: `hlf_mcp/hlf/grammar.py`
- **DEP-005**: `README.md`
- **DEP-006**: `docs/HLF_GRAMMAR_REFERENCE.md`

## 5. Files

- **FILE-001**: `plan/feature-self-healing-parser-1.md`
- **FILE-002**: `hlf_mcp/hlf/compiler.py`
- **FILE-003**: `hlf_mcp/hlf/linter.py`
- **FILE-004**: `hlf_mcp/hlf/formatter.py`
- **FILE-005**: `hlf_mcp/server.py`
- **FILE-006**: `tests/` parser and front-door regression files

## 6. Testing

- **TEST-001**: Add deterministic tests for safe correction classes such as missing `Ω`, lowercase tags, and confusable substitutions.
- **TEST-002**: Add regression tests proving correction suggestions do not silently change semantic effect class or execution capability.
- **TEST-003**: Add front-door tests for plain-language explanation output and repair preview behavior.
- **TEST-004**: Add failure tests proving unsupported or ambiguous corrections remain errors rather than guessed rewrites.

## 7. Risks & Assumptions

- **RISK-001**: Correction assistance can become semantic guesswork if the first correction set is not tightly bounded.
- **RISK-002**: Friendly error wording can drift from the real grammar if it is not generated or validated against parser truth.
- **ASSUMPTION-001**: The current compiler, linter, and formatter already provide enough structure to support a first serious correction-assist layer.

## 8. Related Specifications / Further Reading

- `README.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `plan/architecture-hlf-reconstruction-2.md`
