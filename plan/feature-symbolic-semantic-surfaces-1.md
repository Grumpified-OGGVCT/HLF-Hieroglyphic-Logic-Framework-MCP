---
goal: Add governed symbolic and semasiographic HLF surfaces without weakening canonical semantics
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'In progress'
tags: [feature, bridge, symbolic, semasiographic, glyph, unicode, grammar, operator]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This plan creates a dedicated bridge lane for the new symbolic-surface direction discussed in the Arrival or heptapod-logogram thread.

The purpose is not to replace canonical HLF semantics with mystical glyph interpretation.

The purpose is to research and implement a governed multi-surface model where:

- canonical AST and IR remain the meaning authority
- ASCII authoring remains the primary keyboard-safe authoring surface
- Unicode symbolic projection becomes a secondary semasiographic surface
- rendered glyphic or operator views become optional human-legibility and audit surfaces
- non-linear intent objects and temporal, causal, or agent relations are only admitted when they compile into explicit governed structures

This is a bridge plan, not a present-tense claim that HLF already ships full symbolic cognition or movie-style non-linear language behavior.

## 1. Requirements & Constraints

- **REQ-001**: Keep canonical HLF meaning in deterministic AST, IR, bytecode, and governance contracts.
- **REQ-002**: Treat ASCII as the baseline authoring surface for standard keyboards and local operator workflows.
- **REQ-003**: Allow Unicode symbolic and semasiographic surfaces only as governed secondary projections over canonical semantics.
- **REQ-004**: Define how non-linear intent objects, temporal relations, causal relations, and agent relations are represented in explicit machine-checkable structures.
- **REQ-005**: Add operator-readable projections that improve legibility without becoming alternate semantic authorities.
- **REQ-006**: Integrate this work with doctrine, grammar, translation, routing, audit, and operator-surface plans rather than leaving it as isolated language experimentation.
- **REQ-007**: Produce a dedicated research run for source archaeology, analogues, notation options, and bridge feasibility before implementation promotion.
- **CON-001**: Do not claim time-perception transformation, cognition rewrite, or metaphysical semantic power.
- **CON-002**: Do not allow visual glyphs to bypass governance, validation, compiler checks, or audit traces.
- **CON-003**: Do not replace deterministic textual or structured representations with holistic interpretation that cannot be replayed.
- **CON-004**: Do not treat rendered circular or heptapod-inspired surfaces as canonical execution inputs until they round-trip through ASCII and AST safely.
- **GUD-001**: Phrase this lane as semasiographic and multi-surface HLF, not as a fictional simulation claim.
- **PAT-001**: Every symbolic surface must compile through `projection -> canonical form -> validation -> execution`, never directly from decorative rendering.

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: Establish the doctrine and research boundary for symbolic surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Classify the symbolic-surface lane explicitly as `bridge-true`: canonical semantics remain in AST and IR; symbolic surfaces are governed projections. | ✅ | 2026-03-20 |
| TASK-002 | Record the core boundary in planning artifacts: ASCII authoring is primary, Unicode symbolic projection is secondary, rendered glyph views are optional. | ✅ | 2026-03-20 |
| TASK-003 | Add a dedicated research run covering semasiographic notation, non-linear intent objects, and temporal or causal relation encoding. | ✅ | 2026-03-20 |
| TASK-004 | Map this lane against doctrine files, grammar references, and missing-pillar docs so it does not drift into detached experimentation. | ✅ | 2026-03-20 |

### Implementation Phase 2

- **GOAL-002**: Define a keyboard-safe canonical authoring model for the new semantics.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Specify ASCII syntax candidates for relation operators covering time, cause, agent, dependency, and scope. | ✅ | 2026-03-20 |
| TASK-006 | Define one canonical representation for non-linear intent objects that can be parsed deterministically and validated by the compiler. | ✅ | 2026-03-20 |
| TASK-007 | Define round-trip rules between ASCII authoring, canonical AST serialization, and Unicode symbolic projection. | ✅ | 2026-03-20 |
| TASK-008 | Reject any notation candidate that cannot be typed on a standard keyboard, parsed deterministically, and rendered back into a human-auditable explanation. | ✅ | 2026-03-20 |

### Implementation Phase 3

- **GOAL-003**: Define the symbolic projection and rendering layer.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Define a Unicode symbolic projection table that maps canonical operators and relation types to governed display symbols. | ✅ | 2026-03-20 |
| TASK-010 | Define optional rendered glyph or operator views for audit, gallery, or operator panels without granting them canonical authority. | ✅ | 2026-03-20 |
| TASK-011 | Define which projections are plain-text safe, which are Unicode-only, and which require rendered diagrams or webview surfaces. | ✅ | 2026-03-20 |
| TASK-012 | Add explicit reversibility rules so projected symbolic forms can be traced back to exact canonical source structures. | ✅ | 2026-03-20 |

### Implementation Phase 4

- **GOAL-004**: Bind the new lane into compiler, translation, and trust surfaces.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Define grammar and AST extension points for relation-rich symbolic surfaces without destabilizing current packaged truth. | ✅ | 2026-03-20 |
| TASK-014 | Define how translation surfaces explain symbolic structures back into English and other operator languages. | ✅ | 2026-03-20 |
| TASK-015 | Define audit outputs showing canonical source, symbolic projection, and plain-language explanation side by side. | ✅ | 2026-03-20 |
| TASK-016 | Define lifecycle and governance gates for symbolic proposals so no new surface reaches runtime authority without replayable validation. | ✅ | 2026-03-20 |

### Implementation Phase 5

- **GOAL-005**: Run the dedicated research and benchmarking track before promotion.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-017 | Execute a source-and-analogue research run covering existing HLF surfaces, user-provided direction, semasiographic notation theory, and practical compiler constraints. | ✅ | 2026-03-20 |
| TASK-018 | Produce benchmark criteria for symbolic surfaces: compression with fidelity, parse determinism, translation clarity, audit readability, and operator usability. | ✅ | 2026-03-20 |
| TASK-019 | Define a controlled experiment comparing plain ASCII HLF, symbolic projection, and human-legibility outputs for one representative workflow family. | ✅ | 2026-03-20 |
| TASK-020 | Promote this lane from research to implementation only after notation, trust, and compiler boundaries are documented in exact files and tests. |  |  |

## 3. Alternatives

- **ALT-001**: Keep the symbolic-surface idea only in chat history. Rejected because it is substantial enough to distort architecture decisions if left undocumented.
- **ALT-002**: Treat symbolic glyphs as the new canonical language surface. Rejected because it would weaken replayability, keyboard accessibility, and governance clarity.
- **ALT-003**: Build decorative rendered glyphs without semantic or compiler grounding. Rejected because that would add presentation without architectural leverage.
- **ALT-004**: Ignore the idea entirely until the rest of HLF is finished. Rejected because the notation boundary affects grammar, audit, translation, and operator-surface planning now.

## 4. Dependencies

- **DEP-001**: `HLF_VISION_DOCTRINE.md`
- **DEP-002**: `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- **DEP-003**: `docs/HLF_VISION_MAP.md`
- **DEP-004**: `docs/HLF_MISSING_PILLARS.md`
- **DEP-005**: `docs/HLF_GRAMMAR_REFERENCE.md`
- **DEP-006**: `plan/feature-research-scaffold-integration-1.md`
- **DEP-007**: `plan/architecture-hlf-reconstruction-2.md`
- **DEP-008**: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`

## 5. Files

- **FILE-001**: `plan/feature-symbolic-semantic-surfaces-1.md` — canonical bridge plan for the symbolic-surface lane
- **FILE-002**: `HLF_ACTIONABLE_PLAN.md` — implementation direction update
- **FILE-003**: `HLF_MCP_TODO.md` — active backlog update
- **FILE-004**: `TODO.md` — top-level priority update
- **FILE-005**: `plan/feature-research-scaffold-integration-1.md` — research-lane linkage for glyph and multilingual investigation
- **FILE-006**: `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md` — completed research pass with grounded notation candidates
- **FILE-007**: `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md` — formal bridge recovery spec for symbolic surfaces

## 6. Testing

- **TEST-001**: Add notation round-trip tests for `ASCII -> AST -> symbolic projection -> explanation`.
- **TEST-002**: Add parser determinism tests for non-linear intent-object syntax candidates.
- **TEST-003**: Add audit-surface tests proving the symbolic display cannot drift from canonical semantics.
- **TEST-004**: Add translation tests showing relation-rich symbolic structures can be explained back in plain language without semantic loss claims beyond measured reality.

## 7. Risks & Assumptions

- **RISK-001**: The lane can collapse into fiction-inspired overclaiming unless the canonical-authority rule stays explicit.
- **RISK-002**: Symbolic notation can become unreadable or brittle if keyboard-safe authoring is not designed first.
- **RISK-003**: Visual richness may tempt premature UI work before grammar and audit contracts exist.
- **ASSUMPTION-001**: A governed semasiographic layer can increase leverage if it improves compression, relation clarity, and operator trust without weakening determinism.
- **ASSUMPTION-002**: The right first step is disciplined research plus bridge design, not immediate runtime mutation.

## 8. Related Specifications / Further Reading

[plan/feature-research-scaffold-integration-1.md](../plan/feature-research-scaffold-integration-1.md)
[plan/architecture-hlf-reconstruction-2.md](../plan/architecture-hlf-reconstruction-2.md)
[HLF_ACTIONABLE_PLAN.md](../HLF_ACTIONABLE_PLAN.md)
[HLF_MCP_TODO.md](../HLF_MCP_TODO.md)
[docs/HLF_GRAMMAR_REFERENCE.md](../docs/HLF_GRAMMAR_REFERENCE.md)
[docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md](../docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md)
[docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md](../docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md)