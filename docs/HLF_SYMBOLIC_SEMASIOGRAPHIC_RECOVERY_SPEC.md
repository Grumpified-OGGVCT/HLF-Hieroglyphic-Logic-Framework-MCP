---
goal: Recover governed symbolic and semasiographic HLF surfaces as projections over canonical semantics
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-22
owner: GitHub Copilot
status: 'In progress'
tags: [recovery, bridge, symbolic, semasiographic, glyph, grammar, audit, operator]
---

# Introduction

![Status: In progress](https://img.shields.io/badge/status-In%20progress-yellow)

This recovery spec turns the symbolic-surface research run into a concrete bridge contract.

It does not claim that packaged HLF already ships a full symbolic relation language.

It defines how that lane should be recovered without weakening the canonical semantic authority of ASCII authoring, AST, IR, bytecode, governance, and audit surfaces.

## 1. Requirements & Constraints

- **REQ-001**: Keep canonical meaning in deterministic source, AST, IR, bytecode, and governance contracts.
- **REQ-002**: Keep ASCII authoring as the baseline operator surface.
- **REQ-003**: Model symbolic or semasiographic structure through explicit relation edges, not holistic interpretation.
- **REQ-004**: Preserve the existing packaged glyph surface as current truth while keeping newer symbolic relation work in the bridge lane.
- **REQ-005**: Require every symbolic projection to round-trip through canonical source and plain-language explanation.
- **REQ-006**: Bind this lane to grammar, translation, audit, gallery, and operator-surface work.
- **CON-001**: Do not grant rendered glyphs or diagrams runtime authority.
- **CON-002**: Do not add new executable Unicode relation glyphs until there is parser, linter, formatter, translation, and audit proof.
- **CON-003**: Do not promote fiction-derived claims into current-truth repo language.
- **ARC-001**: Classify this work as `bridge-true` unless a narrower statement is clearly `current-true`.

## 2. Source Authority and Current Packaged Anchors

### Current packaged anchors

- `hlf_mcp/hlf/grammar.py`
- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/formatter.py`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`

### Source and legacy semantic mines

- `hlf_source/hlf/hlfc.py`
- `hlf_source/AGENTS.md`
- `hlf_source/docs/hlf_explainer.html`
- `hlf/lexer.py`

### Research authority

- `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md`

## 3. Recovery Scope

### Recover into formal bridge authority now

- canonical ASCII relation-edge authoring
- bounded non-linear intent objects as relation graphs inside `INTENT` blocks
- projection rules for existing glyphs and source-grounded display-only symbols
- audit and explanation rules for symbolic projection

### Hold as later bridge work

- first-class AST node types dedicated to relation edges
- formatter sugar for relation-rich intent graphs
- operator panels that render graph or diagram views

### Keep out of scope for now

- circular or image-native executable source
- free-form symbolic authoring without keyboard-safe fallback
- current-truth claims about symbolic cognition or time-perception effects

## 4. Canonical Authoring Contract

### 4.1 Current safe authoring form

Use the existing glyph statement grammar with explicit tags and arguments.

```hlf
Δ [RELATE] relation="depends.on" from="verify" to="compile"
```

This compiles under the current parser shape because the grammar already supports generic glyph statements with arbitrary uppercase tags and structured key-value arguments.

### 4.2 Canonical relation vocabulary

The first controlled vocabulary is:

- `time.before`
- `time.after`
- `cause.enables`
- `cause.blocks`
- `depends.on`
- `agent.owns`
- `agent.delegates`
- `scope.within`

Future relation kinds may be added only through the same governed promotion path used for other HLF semantic surfaces.

### 4.3 Canonical field set

Every relation-bearing canonical statement must preserve these fields:

- `relation`
- `from`
- `to`

Optional bridge-phase fields:

- `confidence`
- `strength`
- `evidence`
- `scope`

## 5. Non-Linear Intent Object Contract

Non-linear intent objects are represented as bounded graphs within `INTENT` blocks.

```hlf
INTENT release_pipeline goal="ship" {
  Δ [ACTION] id="compile" goal="compile"
  Δ [ACTION] id="verify" goal="verify"
  ⌘ [DELEGATE] id="scribe" agent="scribe" goal="summarize"
  PARALLEL {
    Δ [ACTION] id="prepare_docs" goal="prepare_docs"
  } {
    Δ [ACTION] id="prepare_release_notes" goal="prepare_release_notes"
  }
  Δ [RELATE] relation="depends.on" from="verify" to="compile"
  Δ [RELATE] relation="agent.delegates" from="scribe" to="verify"
}
```

The graph is canonical because the source remains explicit, sequentially authored, and replayable even when its meaning describes non-sequential structure.

## 6. Symbolic Projection Contract

### 6.1 Projection classes

| Class | Examples | Authority level |
| --- | --- | --- |
| plain-text-safe projection | `PARALLEL`, `BARRIER`, `conf=0.8` | safe for terminals and logs |
| Unicode projection | existing HLF glyphs, `∥`, `⋈`, `_{rho:x}` | display-only bridge surface |
| rendered operator view | graph panes, gallery diagrams, explainer cards | display-only bridge surface |

### 6.2 Approved projection set

| Canonical meaning | Canonical source | Projection candidate | Status |
| --- | --- | --- | --- |
| concurrent execution | `PARALLEL { ... } { ... }` | `∥` | display-only approved |
| sync barrier / wait-before-continue | later barrier relation or operator-surface graph edge | `⋈` | display-only approved |
| epistemic confidence | `confidence=<float>` field | `_{rho:x}` | display-only approved |
| agent delegation | `⌘ [DELEGATE] ...` | current glyph surface | current packaged truth |
| governed routing | `⌘ [ROUTE] ...` | current glyph surface | current packaged truth |

### 6.3 Not yet approved for projection

No new dedicated Unicode glyphs are approved yet for `time.before`, `cause.enables`, or `depends.on`.

Those relations remain canonical string-valued edges until a later bridge slice proves a reversible projection table.

## 7. Round-Trip and Audit Rules

Every symbolic surface must obey this path:

1. author canonical ASCII source
2. compile to canonical AST
3. optionally generate symbolic projection
4. generate plain-language explanation from the same canonical structure
5. show canonical source, projection, and explanation side by side in audit surfaces

A projection fails this spec if any of the following are true:

- it cannot be reconstructed from canonical source
- it hides relation endpoints or qualifiers
- it causes the explanation surface to lose causal or temporal meaning
- it is easier to author directly than to verify canonically

## 8. Translation and Explanation Contract

Translation surfaces for symbolic relations must explain:

- which nodes exist
- which relation type connects them
- whether the relation is temporal, causal, dependency, scope, or agent-role based
- whether the relation is operator-asserted, compiler-derived, or merely displayed

Plain-language explanations remain the trust surface for non-expert operators.

## 9. Testing Requirements

- **TEST-001**: compile relation-bearing glyph statements and verify `relation`, `from`, and `to` survive into canonical AST objects
- **TEST-002**: verify `ASCII -> AST -> symbolic projection -> explanation` round-trips without endpoint drift
- **TEST-003**: prove projection-only symbols cannot be accepted as executable source unless normalized back through canonical source rules
- **TEST-004**: verify translation output names relation type and endpoints explicitly
- **TEST-005**: verify operator views label which symbols are canonical and which are display-only
- **TEST-006**: cover the full starter relation vocabulary from the bridge contract: `time.before`, `time.after`, `cause.enables`, `cause.blocks`, `depends.on`, `agent.owns`, `agent.delegates`, and `scope.within`
- **TEST-007**: verify multiple relation edges preserve canonical order, per-edge family labeling, and per-edge side-by-side artifact output
- **TEST-008**: verify the bounded MCP resource `hlf://status/symbolic_surface` exposes symbolic artifacts as inspectable proof with explicit authority labels and `bridge-true` claim labeling
- **TEST-009**: verify the paired markdown report `hlf://reports/symbolic_surface` is generated from the same symbolic proof bundle and preserves the current authority boundary in operator-readable form
- **TEST-010**: verify a runtime-generated symbolic bundle overrides the packaged fallback sample across `hlf://status/symbolic_surface`, `hlf://reports/symbolic_surface`, and the display-only explainer `hlf://explainer/symbolic_surface`

## 10. Implementation Phases

### Implementation Phase 1

- **GOAL-001**: Lock the relation-edge bridge contract into docs, plans, and backlog surfaces.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-001 | Publish the research run and this recovery spec. | ✅ | 2026-03-20 |
| TASK-002 | Update bridge plans and TODO surfaces to point at the research and spec files. | ✅ | 2026-03-20 |
| TASK-003 | Keep the claim lane for this work explicitly `bridge-true`. | ✅ | 2026-03-20 |

### Implementation Phase 2

- **GOAL-002**: Add relation-aware proof surfaces without destabilizing the grammar.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-004 | Add proof tests for AST field preservation, endpoint-stable explanation output, and rejection of display-only Unicode projection as executable source. | ✅ | 2026-03-22 |
| TASK-005 | Add relation-artifact serializers that emit canonical source, plain-text-safe projection, Unicode projection, explanation, and authority labels side by side. | ✅ | 2026-03-22 |
| TASK-006 | Add audit payload output that records canonical source, projection, explanation, relation family, relation assertion, and display-only authority labels together. | ✅ | 2026-03-22 |
| TASK-006A | Expand proof coverage across the full starter relation vocabulary: `time.before`, `time.after`, `cause.enables`, `cause.blocks`, `depends.on`, `agent.owns`, `agent.delegates`, and `scope.within`. | ✅ | 2026-03-22 |
| TASK-006B | Add a bounded MCP status resource that exposes symbolic artifacts as inspectable proof without granting them executable authority. | ✅ | 2026-03-22 |
| TASK-006C | Add a paired markdown report surface derived from the same symbolic proof bundle and explicitly keep runtime provenance marked pending until non-static symbolic data exists. | ✅ | 2026-03-22 |
| TASK-006D | Add a packaged runtime capture path so symbolic operator surfaces can prefer the latest audited non-static bundle while preserving the same `relation_artifacts` contract. | ✅ | 2026-03-22 |
| TASK-006E | Add a display-only explainer surface derived from the same `relation_artifacts` contract and prove it tracks runtime overrides without gaining executable authority. | ✅ | 2026-03-22 |

### Current insertion decision

Thread `relation_artifacts` outward through a tightly bounded operator trio:

- `hlf://status/symbolic_surface`
- `hlf://reports/symbolic_surface`
- `hlf://explainer/symbolic_surface`

Reason:

- the proof slice now covers the full starter vocabulary across dependency, temporal, causal, agent-role, and scope families
- the status resource, markdown report, and explainer all consume the same relation-artifact contract without adding alternate semantic authority
- packaged runtime capture can now record a non-static symbolic bundle and let operator surfaces prefer live audited data over the fallback sample
- this adds an operator seam without promoting Unicode projection or rendered symbolism into alternate executable authority

Remaining promotion gate for broader outward threading:

1. relation-family proof must remain green for the canonical starter vocabulary
2. operator labeling must preserve `canonical-executable` versus `display-only`
3. any future gallery or report surface must consume the same artifact shape without inventing new semantic authority
4. real audit or runtime provenance refs must only be added once packaged symbolic workflows emit non-static symbolic bundles
5. explainer surfaces must remain display-only even when they render a live runtime-generated symbolic bundle

### Implementation Phase 3

- **GOAL-003**: Consider semantic elevation only after proof exists.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-007 | Evaluate whether `RELATE` should become a first-class AST node instead of a generic glyph statement. | pending | - |
| TASK-008 | Evaluate whether additional relation kinds or projection glyphs have enough evidence for promotion. | pending | - |
| TASK-009 | Gate any promotion through grammar, formatter, translator, linter, audit, and operator proof. | pending | - |

## 11. Risks & Assumptions

- **RISK-001**: If relation strings expand too quickly, the lane becomes an untyped metadata dump instead of a governed semantics surface.
- **RISK-002**: If display symbols outrun explanation quality, operator trust will fall instead of rising.
- **RISK-003**: If bridge docs start speaking in present tense about unimplemented symbolic power, repo claims will drift.
- **ASSUMPTION-001**: Explicit relation edges give most of the useful non-linear leverage without requiring a new executable script.
- **ASSUMPTION-002**: The strongest first implementation step is proof-oriented serialization and explanation, not parser novelty.

## 12. Related Specifications / Further Reading

- `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md`
- `plan/feature-symbolic-semantic-surfaces-1.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_CLAIM_LANES.md`
