---
goal: Execute the symbolic and semasiographic research run for HLF without overstating current packaged truth
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'Completed'
tags: [research, bridge, symbolic, semasiographic, glyph, operator, grammar]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This document executes the dedicated research run required by `plan/feature-symbolic-semantic-surfaces-1.md`.

Its job is to determine which parts of the symbolic-surface idea are grounded enough to become bridge specifications, and which parts must remain out of current-truth claims.

Claim classification for this document:

- current packaged HLF already supports multi-surface authoring and audit: `current-true`
- a governed symbolic projection lane above canonical AST and IR is the correct next direction: `bridge-true`
- fiction-style non-linear cognition claims remain out of bounds: `reductionist or misaligned` if treated as shipped reality

## 1. Research Inputs

Primary packaged authorities reviewed:

- `hlf_mcp/hlf/grammar.py`
- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/formatter.py`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_CLAIM_LANES.md`

Primary source and legacy authorities reviewed:

- `hlf_source/hlf/hlfc.py`
- `hlf_source/docs/hlf_explainer.html`
- `hlf_source/AGENTS.md`
- `hlf_source/README.md`
- `hlf/lexer.py`

## 2. Research Findings

### FIND-001: Multi-surface HLF is already constitutive, not optional

The repo doctrine already treats HLF as a multi-surface language with ASCII authoring, glyph source, JSON AST, bytecode, and English audit. That means the symbolic lane is not a random add-on. It is a bounded extension of an existing core property.

### FIND-002: ASCII-first authoring is already a non-negotiable boundary

Both repo doctrine and packaged compiler behavior support ASCII as the baseline operator surface. The compiler already normalizes ASCII aliases into canonical glyph positions, which means the safest symbolic recovery path is `ASCII first -> canonical AST -> optional projection`.

### FIND-003: The packaged parser already exposes a conservative extension seam

The packaged grammar accepts generic glyph statements with uppercase tags and structured key-value arguments. That means relation-bearing constructs can be represented immediately with deterministic source forms such as:

```hlf
Δ [RELATE] relation="depends.on" from="verify" to="compile"
```

This is materially safer than adding new executable glyphs or non-ASCII infix operators before replay, translation, and audit rules exist.

### FIND-004: Legacy and source materials contain richer symbolic precedents, but they are not packaged truth

The source and legacy lines contain precedents for `parallel`, `sync barrier`, `epistemic confidence`, `assignment`, and additional operator symbols. Those are useful mines for projection design and future bridge work. They are not grounds to claim a broader canonical glyph language already ships in the packaged product.

### FIND-005: Human-readable audit is the real trust anchor for this lane

The compiler, translator, and source `InsAIts` line all converge on the same requirement: every symbolic surface must remain explainable in plain language. This rules out any projection that cannot be losslessly traced back to canonical source and human-readable explanation.

## 3. Grounded Notation Candidates

The research output separates notation into three classes.

### 3.1 Approved canonical authoring candidates

These are grounded enough to enter a formal bridge spec now because they fit the current parser shape or require only bounded semantic elevation later.

| Candidate | Canonical ASCII form | Purpose | Grounding | Research verdict |
| --- | --- | --- | --- | --- |
| `CAND-001` | `Δ [RELATE] relation="time.before" from="collect" to="verify"` | explicit temporal edge | fits current generic glyph + tag + arg grammar | promote to bridge spec |
| `CAND-002` | `Δ [RELATE] relation="cause.enables" from="verify" to="deploy"` | explicit causal edge | fits current packaged grammar | promote to bridge spec |
| `CAND-003` | `Δ [RELATE] relation="depends.on" from="merge" to="verify"` | dependency edge | fits current packaged grammar | promote to bridge spec |
| `CAND-004` | `⌘ [DELEGATE] agent="scribe" goal="summarize"` | agent-role edge | already present in packaged codegen and docs | keep as canonical authority |
| `CAND-005` | `⌘ [ROUTE] strategy="auto"` | routing edge | already present in packaged code and grammar tag surface | keep as canonical authority |
| `CAND-006` | `PARALLEL { ... } { ... }` | concurrency relation | already first-class in packaged grammar | keep as canonical authority |

### 3.2 Approved symbolic projection candidates

These are grounded by source or legacy precedent, but they should remain projection-only until packaged round-trip proof exists.

| Candidate | Projection form | Canonical source authority | Intended use | Research verdict |
| --- | --- | --- | --- | --- |
| `PROJ-001` | `∥` | `PARALLEL` blocks | display concurrent branches in operator surfaces | approve as display-only |
| `PROJ-002` | `⋈` | sync-barrier precedent in source docs | display wait-then-continue barriers | approve as display-only |
| `PROJ-003` | `_{rho:x}` | source epistemic notation | display confidence or epistemic metadata derived from canonical fields | approve as display-only |
| `PROJ-004` | existing HLF glyph set | packaged glyph statements | keep current glyph view as one projection lane | current packaged truth |

### 3.3 Rejected or held candidates

| Candidate class | Reason held or rejected |
| --- | --- |
| circular heptapod-style canonical authoring | no deterministic parser, no audit contract, no keyboard-safe path |
| new executable Unicode relation glyphs for time or cause | no packaged grammar authority yet; relation strings are safer first step |
| free-form rendered diagrams as source of execution truth | violates replayability and auditability |
| cognition or time-perception claims | outside the repo's truth boundary |

## 4. Recommended Canonical Model

The safest near-term model is a relation-edge layer represented inside existing statement forms.

### 4.1 Canonical relation statement

Use uppercase tag plus explicit fields.

```hlf
Δ [RELATE] relation="depends.on" from="verify" to="compile"
```

### 4.2 Canonical relation vocabulary

Promote a small controlled relation vocabulary first:

- `time.before`
- `time.after`
- `cause.enables`
- `cause.blocks`
- `depends.on`
- `agent.owns`
- `agent.delegates`
- `scope.within`

### 4.3 Canonical non-linear intent object

Represent non-linear intent as a bounded graph inside an `INTENT` block, not as a holistic single glyph.

```hlf
INTENT release_pipeline goal="ship" {
  Δ [ACTION] id="compile" goal="compile"
  Δ [ACTION] id="verify" goal="verify"
  ⌘ [DELEGATE] id="scribe" agent="scribe" goal="summarize"
  Δ [RELATE] relation="depends.on" from="verify" to="compile"
  Δ [RELATE] relation="agent.delegates" from="scribe" to="verify"
}
```

This keeps non-linearity explicit, bounded, and machine-checkable.

## 5. Benchmark Lanes

The plan required benchmark criteria before promotion. The research run recommends five lanes.

- `BENCH-001`: compression with fidelity
- `BENCH-002`: parse determinism
- `BENCH-003`: translation clarity
- `BENCH-004`: audit readability
- `BENCH-005`: operator usability

Success means the symbolic projection improves one or more of those lanes without lowering the others below the ASCII baseline.

## 6. Controlled Experiment Recommendation

Use one representative workflow family that already exists in packaged HLF patterns:

- delegate a summarization task
- route execution automatically
- declare a source artifact
- assert a resource constraint
- run parallel preparation steps
- synchronize before final result

Compare three renderings of the same canonical intent object:

1. plain ASCII HLF source
2. symbolic projection view
3. plain-language explanation

Evaluate each rendering across the five benchmark lanes above.

## 7. Recommendation

Promote the symbolic lane into a formal recovery specification with the following rule set:

1. keep canonical authoring in ASCII-first statement and edge forms
2. treat relation strings as the first bridge mechanism for time, cause, dependency, and agent structure
3. reuse only source-grounded symbolic projections such as `∥`, `⋈`, and epistemic overlays in display surfaces
4. refuse any projection that cannot round-trip back to canonical source plus plain-language audit

## 8. Follow-up Actions

- create `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`
- update `plan/feature-symbolic-semantic-surfaces-1.md` with completed research tasks
- update `HLF_ACTIONABLE_PLAN.md` and `HLF_MCP_TODO.md` to point at the new authoritative research and spec files
- add round-trip and explanation tests before any runtime promotion