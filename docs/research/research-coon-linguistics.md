# Research Audit: Jessica Coon Academic Linguistics for HLF Relevance

**Audit ID:** `research-coon-linguistics`
**Date:** 2026-05-19
**Status:** Complete
**Tags:** [research, linguistics, ergativity, field-methods, constraint-grammar, Coon]

---

## 1. What Was Found

### 1.1 Jessica Coon: Academic Profile

Jessica Coon is Professor of Linguistics at McGill University and Canada Research Chair in Syntax and Indigenous Languages. Her work spans three domains directly relevant to HLF's constraint grammar design.

### 1.2 Ergative-Absolutive Alignment

**Core finding:** Coon is a leading expert on ergativity — a grammatical alignment pattern where the subject of an intransitive verb patterns with the object of a transitive verb (absolutive case), while the subject of a transitive verb receives special marking (ergative case).

Contrast with English's nominative-accusative alignment:
```
English (nominative-accusative):
  She[NOM] runs.          (intransitive subject = NOM)
  She[NOM] sees him[ACC]. (transitive subject = NOM, object = ACC)

Mayan (ergative-absolutive):
  She[ABS] runs.          (intransitive subject = ABS)
  She[ERG] sees him[ABS]. (transitive subject = ERG, object = ABS)
```

Key publications:
- Coon, Jessica. 2013. *Aspects of Split Ergativity*. Oxford University Press.
- Coon, Jessica & Pedro Mateo Pedro. 2011. "Extraction and Embedding in Chol." *Natural Language and Linguistic Theory*.

**Relevance to HLF constraint grammar:**

Ergative alignment treats the *undergoer* of an action as the default/unmarked case, and the *initiator* as specially marked. This maps elegantly to HLF's governance model:

- **Ergative ≈ Governed Action Initiator**: When an HLF agent initiates a tool call, mutation, or side effect, it should be *specially marked* (like the ergative case). This is exactly what HLF's glyph system already does — `Δ [INTENT]` marks the action, `Ж [CONSTRAINT]` marks governance bounds.
- **Absolutive ≈ Default/Passive State**: Data, observations, and query results are the "absolutive" default — they require no special marking because they don't initiate change.

This suggests a constraint grammar principle: **"Mark the actor, not the acted-upon."** In HLF terms: governance annotations should attach to the *initiating agent or capsule*, not to the data being processed.

### 1.3 Field Linguistics Methodology

Coon's work on Chol (Mayan, Chiapas, Mexico) and Chuj (Mayan, Guatemala) exemplifies rigorous field linguistics methodology. Key principles from her approach:

1. **Elicitation over assumption**: Never assume a grammatical pattern exists; elicit it from native speakers through structured prompts.
2. **Minimal pairs**: Test meaning contrasts by changing exactly one feature at a time.
3. **Speaker-as-authority**: The native speaker's judgment is the final arbiter of grammaticality.
4. **Documentation of negative evidence**: Record not just what *is* grammatical, but what *is not*.

**Relevance to HLF constraint grammar:**

These field linguistics principles map directly to how HLF should develop and validate its constraint grammar:

| Field Linguistics Principle | HLF Constraint Grammar Analog |
|---|---|
| Elicitation over assumption | Fuzz-test constraints against LLM outputs; don't assume what models will produce |
| Minimal pairs | Constraint regression tests: change one constraint parameter, verify exactly one behavioral delta |
| Speaker-as-authority | Human operator as final arbiter of constraint correctness (operator-override pattern) |
| Negative evidence documentation | Record denied/blocked executions with rationale in audit trail |

Coon's methodology also emphasizes **gradient acceptability** — native speakers don't just say "grammatical" or "ungrammatical"; they report degrees of acceptability. This maps to HLF's confidence-scored governance, where constraints can produce `deny`, `warn`, or `allow_with_evidence` rather than binary pass/fail.

### 1.4 Constructed Languages and Arrival

Coon served as the linguistics consultant for Denis Villeneuve's 2016 film *Arrival*, working on the linguistic realism of the heptapod language. While the film's circular logograms were primarily designed by artist Martine Bertrand, Coon ensured the linguistic analysis scenes reflected genuine field linguistics methodology.

Key insight: In the film, linguist Louise Banks (loosely inspired by Coon's work) uses **elicitation frames** — showing objects/actions and recording the heptapod response — to gradually decode the alien language. This is identical to Coon's real field methodology.

The Arrival connection is particularly salient because HLF's founding narrative explicitly draws from heptapod logograms (`README.md` L404-425, `Cogito_Discussion.md` L359-375, `docs/HLF_FULL_MANIFESTO.md` L428-447). Understanding Coon's actual linguistics work provides scientific grounding for what HLF metaphorically invokes.

### 1.5 Non-Linear Writing Systems

While Coon's primary expertise is in Mayan syntax, her broader field includes contact with Mesoamerican writing systems. Maya hieroglyphic writing is a logosyllabic system with both logographic and phonetic components, arranged in paired columns read left-to-right, top-to-bottom. This is not fully non-linear (it's ordered), but the glyph-block structure — where multiple signs compose into a single block — has spatial dimensionality absent from alphabetic writing.

---

## 2. Relevance to HLF

### 2.1 Ergative Constraint Patterns for HLF Grammar

HLF's constraint grammar could adopt an **ergative governance pattern**:

```hlf
# ERGATIVE PATTERN: Mark the initiator, not the data
Δ [INTENT] action="deploy" target="/app"        # ← "Ergative": marked action
  Ж [CONSTRAINT] mode="ro" scope="filesystem"   # ← Governance bound on the initiator
  RESULT 0 "deployed under constraint"
```

The constraint (`Ж`) marks the ergative agent (the deployment action), not the absolute target (`/app`). This aligns with Coon's finding that ergative systems *mark the agent of transitive verbs* because agency is the marked/special condition.

### 2.2 Field Elicitation for Constraint Development

Coon's field methodology suggests a concrete process for developing HLF constraints:

1. **Elicitation phase**: Run diverse LLMs against constraint candidates; collect both accepted and rejected outputs
2. **Minimal pair testing**: For each constraint, create test pairs that differ by exactly one feature; verify the constraint fires on exactly the right case
3. **Gradient acceptability**: Support `confidence` scores on constraints, not just binary gates
4. **Speaker corpus**: Maintain a corpus of human operator judgments on constraint acceptability

### 2.3 Arrival-Inspired Elicitation for Glyph Semantics

The film's elicitation-frame methodology (showing an object → recording the glyph response → building a dictionary) maps to a potential HLF workflow for validating glyph semantics:

1. Present an HLF glyph statement to a human operator
2. Operator provides a plain-language interpretation
3. Compare operator interpretation against InsAIts decompilation
4. Drift = either the glyph is ambiguous or the decompiler needs refinement

### 2.4 The `§` Prose Bridge as Elicitation Frame

HLF's `§` (SECTION/prose-bridge) operator — designed to separate narrative prose from executable commands — can be understood as an **elicitation frame delimiter**. In field linguistics, the frame (the context of elicitation) is separated from the elicited form. Similarly, `§` separates the human narrative context from the machine-executable glyph form:

```hlf
§ [NARRATIVE] "The user wants to deploy with safety checks"
Δ [INTENT] action="deploy" target="/app"
Ж [CONSTRAINT] require_approval=true
```

---

## 3. Actionable Recommendations

| Priority | Recommendation | Landing Zone |
|---|---|---|
| **P1 (Now)** | Document ergative governance pattern: mark initiators, not data | Constraint grammar design docs |
| **P1 (Now)** | Adopt "gradient acceptability" for constraints: `deny | warn | allow_with_evidence` instead of binary | `hlf_mcp/hlf/grammar.py`, constraint system |
| **P2 (Bridge)** | Design an elicitation-frame protocol: operator-judgment corpus for constraint validation | Bridge spec in `plan/` |
| **P2 (Bridge)** | Add minimal-pair constraint tests: change one parameter, verify one behavioral delta | Test suite |
| **P3 (Future)** | Explore ergative case-marking as a first-class HLF type annotation for capsules | Language evolution bridge |
| **Avoid** | Do NOT claim HLF "implements ergative grammar" — use as design inspiration, not scientific claim | Truth discipline |

---

## 4. Key Sources

*Note: This audit draws on the assistant's training knowledge. A live web search pass would enrich specific citations and publication details.*

- Coon, Jessica. 2013. *Aspects of Split Ergativity*. Oxford University Press.
- Coon, Jessica. 2010. "Complementation in Chol (Mayan): A Theory of Split Ergativity." PhD Dissertation, MIT.
- Coon, Jessica & Pedro Mateo Pedro. 2011. "Extraction and Embedding in Chol." NLLT.
- McGill University Linguistics: https://www.mcgill.ca/linguistics/people/faculty/coon
- Arrival (2016) — Linguistics consultation
- HLF Internal: `docs/HLF_CONSTRAINT_GLOSSARY.md`
- HLF Internal: `docs/HLF_GRAMMAR_REFERENCE.md`
