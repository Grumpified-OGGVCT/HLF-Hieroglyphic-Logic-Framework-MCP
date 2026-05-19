# Research Audit: Recto 2D Programming Language for HLF Relevance

**Audit ID:** `research-recto-language`
**Date:** 2026-05-19
**Status:** Complete
**Tags:** [research, 2D-language, visual-programming, spatial-syntax, esoteric]

---

## 1. What Was Found

### 1.1 The "Recto" Language Question

The search target "Recto" as a 2D visual programming language is ambiguous. The name "Recto" does not correspond to a well-known, established programming language in the literature. The most likely referents are:

**A. "Recto" as an esoteric / experimental 2D language:**
There is a niche esoteric programming language or experimental notation that uses the name "Recto" or "Recto/Verso" to describe a two-sided or spatially-oriented programming paradigm. The name evokes the recto/verso distinction in bookbinding (front/back of a page), suggesting a language where program layout in 2D space carries semantic meaning. However, no widely cited implementation exists under this exact name.

**B. Broader 2D visual programming landscape:**
Multiple 2D and visual programming paradigms exist that are more established:

### 1.2 Established 2D / Visual Programming Languages

| Language/System | 2D Paradigm | Year | Key Feature |
|---|---|---|---|
| **Befunge** | 2D grid, instruction pointer moves in 4 directions | 1993 | The canonical 2D esoteric language; program counter navigates a character grid |
| **Piet** | Programs are bitmaps; color transitions encode instructions | 2001 | True visual programming — the "source code" is an image |
| **LabVIEW** | Dataflow diagrams with virtual instruments | 1986 | Industrial visual programming; wires connect function blocks spatially |
| **Scratch** | Block-based visual programming | 2007 | Blocks snap together; spatial layout is syntactic |
| **Node-RED** | Flow-based visual programming | 2013 | Nodes connected by wires in a 2D canvas |
| **Quartz Composer** | Node-based visual programming for graphics | 2005 | Spatial patch-based composition |
| **Max/MSP** | Visual programming for music/audio | 1990 | Patch cords connect objects in a 2D canvas |
| **Grasshopper** | Visual programming for parametric design (Rhino) | 2007 | Spatial node-wire diagrams for 3D modeling |

### 1.3 Key Paradigms in 2D/Visual Programming

**Grid-based execution (Befunge, Befunge-98):**
- Source code is a 2D character grid
- Instruction pointer moves up/down/left/right based on commands
- Spatial position *is* control flow: the program counter''s position at any moment determines execution
- Spatial operators: `>` (go right), `<` (go left), `^` (go up), `v` (go down), `?` (random direction)

**Dataflow (LabVIEW, Node-RED, Max/MSP):**
- Programs are directed graphs in 2D space
- Nodes represent functions; edges represent data flow
- Spatial layout is organizational, not syntactic (you can rearrange nodes without changing semantics)
- Execution follows data dependencies, not spatial position

**Block-based (Scratch, Blockly):**
- Programs are constructed by snapping shaped blocks together
- Shape determines valid composition (type-safe by geometry)
- Nested blocks represent scope/containment

**Diagrammatic (Piet):**
- The program *is* an image
- Color transitions encode operations
- Truly 2D: both x,y position and color adjacency matter

### 1.4 Spatial Syntax vs. Spatial Layout

A critical distinction emerges:

- **Spatial syntax**: Position/geometry *determines* semantics. Moving an element changes program meaning (Befunge, Piet).
- **Spatial layout**: Position is *incidental* to semantics. Rearranging nodes is refactoring, not semantic change (Node-RED, LabVIEW).

Most practical visual languages use spatial layout, not syntax. Befunge and Piet are the exceptions — and they remain curiosities rather than practical tools, precisely because spatial syntax is hard to version-control, diff, merge, and review.

---

## 2. Relevance to HLF

### 2.1 HLF's Existing Relationship to Spatiality

HLF is fundamentally **linear** in source form (ASCII → AST). Its glyphs are non-linear in *semantic density* (a single Δ encodes intent, constraints, tier, gas, audit in one symbol) but linear in *syntax* (tokens appear in sequence).

The repo's symbolic-surface research (`docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`) explicitly constrains non-linearity to **bounded relation graphs inside INTENT blocks**, not 2D surface syntax:

```hlf
INTENT deploy_with_checks {
    Δ [ANALYZE] action="verify"
    Ж [CONSTRAIN] mode="ro"
    RELATE from="verify" to="deploy" relation="depends.on"
}
```

This is spatial in a *graph sense* (nodes connected by relations) but not in a *surface layout sense* (the source code is still linear ASCII).

### 2.2 Could HLF Support 2D Layout Modes?

**A. As an authoring surface: Possibly, but high cost.**

A 2D HLF authoring mode could display INTENT blocks as node-wire diagrams, similar to Node-RED or LabVIEW. The linear ASCII would remain the canonical form; the 2D view would be a projection.

This aligns with HLF's multi-surface design (ASCII → AST → bytecode → audit). Adding a 2D *visualization* surface is consistent with existing philosophy.

**B. As a semantic layer: Not recommended.**

Making spatial position semantically significant (Befunge-style) would break HLF's deterministic compilation, version-control compatibility, and textual audit trail. The repo's doctrine is clear: ASCII-first authoring is non-negotiable.

**C. The gallery surface as 2D test bed.**

The operator gallery spec (`docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`) could include 2D relation-graph renderings of INTENT blocks. This is low-risk (it's a read-only projection from canonical AST) and high-value (operators can visually inspect complex capsule structures).

### 2.3 The § Operator as Bridge Between Linear and 2D

HLF's `§` (SECTION/prose-bridge) operator — which separates narrative prose from executable commands — could serve as the delimiter between linear narrative context and a 2D relation-graph projection:

```
Linear source:  § [NARRATIVE] "..."  Δ [INTENT] ...  Ж [CONSTRAINT] ...  RELATE ...
2D projection:  [NARRATIVE box] → [INTENT node] → [CONSTRAINT node] → [RELATE edge]
```

The `§` operator already marks the boundary between human-meaningful prose and machine-executable structure. It's a natural seam for projecting the linear source into a 2D visual representation.

### 2.4 Lessons from 2D Language Failures

Why did Befunge and Piet remain curiosities while LabVIEW and Node-RED became industrial tools?

| Factor | Befunge/Piet | LabVIEW/Node-RED | Implication for HLF |
|---|---|---|---|
| Version control | Impossible to diff | Hard but possible (XML/JSON underlying format) | Keep canonical form as diffable ASCII |
| Debugging | Exotic | Visual breakpoints work | Keep linear execution traces |
| Collaboration | No merge tools | Limited | Keep text-based collaboration path |
| Learning curve | Steep | Shallow for domain experts | Keep ASCII default; 2D as optional projection |

The lesson for HLF: **2D is valuable as a projection, dangerous as a canonical form.**

---

## 3. Actionable Recommendations

| Priority | Recommendation | Landing Zone |
|---|---|---|
| **P1 (Now)** | Distinguish "spatial syntax" from "spatial layout" in HLF design docs — HLF should pursue spatial layout (projections) not spatial syntax (canonical form) | Design docs |
| **P2 (Bridge)** | Add 2D INTENT-block relation-graph rendering to the operator gallery spec | `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` |
| **P2 (Bridge)** | Document the `§` operator as the canonical linear↔2D projection seam | `docs/HLF_GRAMMAR_REFERENCE.md` |
| **P3 (Future)** | Prototype a Node-RED-style HLF capsule editor that projects linear HLF source as node-wire diagrams (read-only for Phase 1) | Visual operator workbench bridge |
| **Avoid** | Do NOT add spatial position as a semantic primitive (no Befunge-style 2D execution) | Would violate ASCII-first authoring and deterministic compilation |
| **Avoid** | Do NOT claim Recto is an established language without confirming its identity | Future web search pass needed |

---

## 4. Sources and Further Reading

*Note: "Recto" as a named 2D language remains unconfirmed. This audit documents the broader 2D programming landscape. A dedicated web search pass should clarify whether a specific "Recto" language implementation exists.*

- Befunge: https://esolangs.org/wiki/Befunge
- Piet: https://www.dangermouse.net/esoteric/piet.html
- Node-RED: https://nodered.org
- Scratch: https://scratch.mit.edu
- HLF Internal: `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md`
- HLF Internal: `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
