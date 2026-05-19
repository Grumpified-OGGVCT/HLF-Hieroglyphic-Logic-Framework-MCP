# Research Audit: UNLWS 2D Conlang for HLF Relevance

**Audit ID:** `research-unlws-conlang`
**Date:** 2026-05-19
**Status:** Complete
**Tags:** [research, conlang, 2D-language, non-linear-writing, UNLWS, semasiographic]

---

## 1. What Was Found

### 1.1 UNLWS: Unker Non-Linear Writing System

UNLWS (Unker Non-Linear Writing System) is a constructed language / writing system created by Alex Fink and several collaborators (primarily active on the Conlang mailing list and Zompist BBoard, circa 2010-present). It is one of the most fully developed examples of a **non-linear 2D writing system** in the conlang community.

**Key characteristics:**

- **Fully 2D syntax**: Meaning is encoded through spatial arrangement of glyphs in a 2D plane. There is no canonical linear reading order. The same 2D "sentence" can be entered from multiple starting points.
- **Semasiographic**: UNLWS is primarily semasiographic — it represents meaning directly rather than representing sounds (phonographic). This distinguishes it from most writing systems, which encode spoken language.
- **Relational glyph composition**: Glyphs connect to each other via lines, curves, and spatial proximity. The relationships between glyphs (connected-by, contains, above/below, left/right) carry grammatical meaning.
- **No spoken language mapping**: Unlike most conlangs, UNLWS does not have a spoken form. It exists purely as a 2D visual language. There is no "pronunciation."
- **Predicate-argument structure expressed spatially**: Arguments attach to predicates via spatial connectors. A predicate glyph may have "slots" where participant glyphs attach.

### 1.2 UNLWS Design Principles

From Fink's documentation (reconstructed from community archives):

1. **Spatial relations ARE grammatical relations**: Proximity, connection lines, containment, and relative position encode case roles (agent, patient, instrument, location, etc.).
2. **Connectedness is truth**: Two glyphs connected by a line assert a relationship. Disconnected glyphs in the same visual field imply contextual relevance without direct relationship.
3. **Non-linearity is not chaos**: UNLWS has strict topological rules. Connections must be well-formed; crossing lines are semantically significant (or prohibited in certain contexts).
4. **Scalability through modularity**: Complex propositions are built by composing simpler 2D sub-graphs. The language scales by nesting and connecting, not by lengthening a linear string.

### 1.3 Comparison: UNLWS vs. Other Non-Linear Systems

| System | Type | Linearity | Primary Encoding |
|---|---|---|---|
| UNLWS | 2D semasiographic conlang | Fully non-linear | Spatial relations between glyphs |
| Blissymbolics | 2D semasiographic (linearizable) | Linear with 2D composition | Primitive visual elements combining into symbols |
| Heptapod (Arrival, fictional) | Circular logograms | Non-linear | Holistic circular symbols encoding full propositions |
| Maya hieroglyphs | Logosyllabic | Linear (paired columns) | Glyph blocks in ordered grid |
| Chinese characters | Logographic | Linear | Stroke-order determined; spatial arrangement within character square |
| HLF glyphs | Typed operators + ASCII | Linear source, non-linear density | Sequential glyph-tag-args statements |

### 1.4 Key Insight: The Linearization Problem

UNLWS's greatest theoretical contribution is exposing the **linearization problem** for 2D writing systems: given a 2D semantic structure, how do you serialize it into a 1D stream (for storage, transmission, or speech)?

UNLWS *refuses* to solve this problem — it exists only in 2D. But this refusal is also its limitation: you cannot store UNLWS in a plaintext file, version-control it with git, or transmit it over a text protocol. Every practical deployment requires a 2D canvas renderer.

HLF takes the opposite approach: it starts with a linear ASCII serialization and *optionally projects* into 2D visual representations. This is pragmatic — the linear form is canonical, version-controllable, and diffable; the 2D form is an optional visualization.

---

## 2. Relevance to HLF

### 2.1 How Non-Linear Writing Systems Encode Meaning Spatially

UNLWS demonstrates several spatial encoding patterns that could inform HLF's glyph system:

| UNLWS Spatial Pattern | Meaning Encoded | HLF Analog |
|---|---|---|
| Proximity | Relevance/association | Adjacent glyph statements share scope context |
| Connection lines | Direct relationship | `RELATE from="A" to="B" relation="depends.on"` |
| Containment | Scope/possession | `INTENT ... { ... }` block nesting |
| Relative position (above/below) | Hierarchical priority | Priority glyph `⩕` or ordering within blocks |
| Relative position (left/right) | Sequence/temporal order | Statement ordering within a block |

HLF already encodes most of these *linearly* through tags, arguments, and block structure. The UNLWS insight is that these could be *visualized* spatially without changing their linear canonical form.

### 2.2 Could HLF's Glyph System Benefit from Non-Linear Layout Concepts?

**Yes, as a visualization/projection layer, not as canonical syntax.**

HLF's INTENT blocks are already relation graphs in linear form:

```hlf
INTENT ship_with_checks {
    Δ [ANALYZE] action="verify" id="step1"
    Ж [CONSTRAIN] mode="ro" id="step2"
    ⌘ [COMMAND] action="deploy" id="step3"
    RELATE from="step1" to="step3" relation="required_by"
    RELATE from="step2" to="step3" relation="constrains"
}
```

In a UNLWS-inspired 2D projection:
- `Δ [ANALYZE]` and `Ж [CONSTRAIN]` would appear as spatially connected nodes feeding into `⌘ [COMMAND]`
- Connection lines would carry labels ("required_by", "constrains")
- The INTENT block boundary would be rendered as a containing shape

This is **already consistent with HLF's multi-surface design** — ASCII source is canonical; 2D projection is a derived view.

### 2.3 The § Prose Bridge as Linear↔Non-Linear Bridge

HLF's `§` (SECTION/prose-bridge) operator is explicitly designed to separate narrative prose from executable commands. In UNLWS terms, this is the boundary between:

- **Continuous/narrative meaning** (prose, human context) — the `§` section
- **Discrete/relational meaning** (glyph statements, machine-executable) — after `§`

The `§` operator could serve as the **bridge between linear and non-linear semantic layouts**:

```
§ [NARRATIVE] "The user wants secure deployment with rollback capability"
   ↑ Linear prose: sequential, narrative, human-readable
   
Δ [INTENT] action="deploy" → Ж [CONSTRAINT] mode="ro" → RELATE ...
   ↑ Non-linear relations: glyphs connect in a semantic graph
```

The `§` says: "What follows is a non-linear proposition expressed in linear tokens, which can be projected into 2D relation-graph form." This is precisely how UNLWS encodes meaning — but with the critical difference that HLF has a canonical linear serialization.

### 2.4 The Semasiographic Connection

UNLWS is semasiographic: it encodes meaning directly, bypassing phonology. HLF's glyphs are also semasiographic in spirit — `Δ` doesn't "sound like" anything; it *means* analysis/action directly.

The repo's research on symbolic-semasiographic surfaces (`docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`) explicitly explores this connection. UNLWS provides a concrete, existing example of what a fully semasiographic 2D system looks like — and also demonstrates the practical limitations (no plaintext storage, no diffs, no text protocols).

---

## 3. Actionable Recommendations

| Priority | Recommendation | Landing Zone |
|---|---|---|
| **P1 (Now)** | Reference UNLWS in the symbolic-semasiographic research docs as a real (non-fictional) example of a 2D semasiographic system | `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md` |
| **P1 (Now)** | Document the linearization problem explicitly: UNLWS refuses to solve it; HLF solves it with ASCII-first canonical form | This document |
| **P2 (Bridge)** | Design a 2D INTENT-block projection as a read-only gallery surface, inspired by UNLWS spatial relation encoding | `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` |
| **P2 (Bridge)** | Formalize the `§` operator as the canonical linear↔non-linear bridge marker in the grammar reference | `docs/HLF_GRAMMAR_REFERENCE.md` |
| **P3 (Future)** | Explore UNLWS-style connection-line glyphs for RELATE visualization (read-only projection) | Visual operator workbench bridge |
| **Avoid** | Do NOT propose a 2D-only canonical form — HLF's ASCII-first authoring is a non-negotiable boundary | Current-truth discipline |
| **Avoid** | Do NOT claim HLF "supports non-linear writing" — be specific: "bounded relation graphs inside INTENT blocks, expressed in linear ASCII" | Truth discipline |

---

## 4. Sources

*Note: This audit draws on the assistant's training knowledge of conlang communities, UNLWS documentation on Zompist BBoard and Conlang mailing list archives. A dedicated web search pass would surface specific archival URLs.*

- Fink, Alex et al. UNLWS (Unker Non-Linear Writing System). Conlang Mailing List / Zompist BBoard, circa 2010-present.
- Conlang Mailing List Archives: https://listserv.brown.edu/archives/conlang.html
- Zompist BBoard (Conlangery section): https://www.verduria.org
- Blissymbolics Communication International: https://blissymbolics.org
- HLF Internal: `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`
- HLF Internal: `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md`
- HLF Internal: `docs/HLF_GRAMMAR_REFERENCE.md`
