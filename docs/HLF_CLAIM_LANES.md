# HLF Claim Lanes

This document formalizes how claims should be classified in this repo.

It exists because HLF work lives across multiple truth conditions at once:

- what is implemented now
- what is partially recovered or bridge-valid
- what is clearly part of the north-star doctrine

Without a compact claim model, wording drifts in predictable ways:

- current truth gets inflated into completion
- bridge work gets mistaken for shipped authority
- vision gets flattened into the easiest packaged surface

## Purpose

Use this file when evaluating or writing:

- README sections
- docs and handoffs
- PR descriptions
- release notes
- issue framing
- assistant outputs
- architecture summaries

The goal is not to make wording timid.
The goal is to keep wording exact.

## The Core Rule

Every significant claim in this repo should be read through one of these lanes:

1. current-true
2. bridge-true
3. vision-true
4. partially overstated
5. reductionist or misaligned

These are not moral categories.
They are interpretive status labels.

## Lane Definitions

### 1. Current-True

Use when the claim is implemented, validated, and safe to assert in present tense for this repo now.

Typical signals:

- backed by code in this checkout
- reflected in `SSOT_HLF_MCP.md`
- matches current packaged behavior
- does not depend on aspiration or planned recovery

Example:

> The packaged FastMCP server under `hlf_mcp/` is the main present-tense product surface.

### 2. Bridge-True

Use when the claim is the correct convergence direction, or is partially real in bounded form, but should not be mistaken for full target-state completion.

Typical signals:

- supported by current work plus explicit bridge planning
- true in staged, bounded, or partial form
- depends on recovery or further proof before promotion into current truth

Example:

> MCP is the right bootstrap surface for bounded recursive-build evidence.

### 3. Vision-True

Use when the claim is clearly part of the repo's intended doctrine and north-star architecture, even if it is not fully shipped.

Typical signals:

- explicit in `HLF_VISION_DOCTRINE.md`
- explicit in `docs/HLF_VISION_PLAIN_LANGUAGE.md` or `docs/HLF_DESIGN_NORTH_STAR.md`
- constitutive to HLF's intended identity

Example:

> HLF is meant to become a governed language and coordination substrate that turns human intent into auditable machine action.

### 4. Partially Overstated

Use when a claim contains a real insight but implies more completeness, authority, or packaging maturity than the repo currently earns.

Typical signals:

- directionally right, but maturity is too strong
- present tense is broader than current proof
- bridge or vision content is being phrased as if it were fully current truth

Example:

> The MCP surface already carries governance, memory, coordination, and explanation as a complete finished system.

The safer classification is usually bridge-true with overstatement in present-tense packaging.

### 5. Reductionist Or Misaligned

Use when a claim shrinks HLF into an easier but weaker story, or confuses non-core scaffolding with constitutive HLF meaning.

Typical signals:

- collapses HLF into "just the MCP server"
- treats current packaged neatness as the whole architectural truth
- erases constitutive but under-recovered pillars
- substitutes a weaker pseudo-equivalent for the intended doctrine

Example:

> HLF is basically the MCP wrapper around a tool menu.

That is not a harmless simplification.
It is a distortion of repo doctrine.

## How To Use The Lanes

When you encounter a claim:

1. ask whether it is executable current truth, bridge-state truth, or doctrine-level truth
2. check whether the phrasing quietly upgrades maturity beyond the evidence
3. check whether the phrasing shrinks HLF into a weaker substitute
4. relabel or rewrite the claim before reusing it

## Compact Matrix

| Label | Meaning | Safe Present-Tense Use | Typical Home |
| --- | --- | --- | --- |
| `current-true` | implemented and validated now | yes | `SSOT_HLF_MCP.md`, `BUILD_GUIDE.md`, README product statements |
| `bridge-true` | correct staged direction or bounded current proof | with qualifiers | `HLF_ACTIONABLE_PLAN.md`, bridge notes, positioning docs |
| `vision-true` | constitutive north-star claim | only as vision | `HLF_VISION_DOCTRINE.md`, north-star docs |
| `partially overstated` | insight is real but maturity is inflated | no, rewrite | reviews, audits, PR summaries |
| `reductionist or misaligned` | shrinks or distorts HLF | no | should be corrected, not reused |

## High-Risk Phrases

These phrases are not automatically wrong, but they often drift across lanes and should be checked carefully:

- self-hosting
- recursive build
- governed environment
- coordination substrate
- meaning layer
- complete memory layer
- formal verification
- orchestration
- autonomous system

Questions to ask when they appear:

- Is this current truth or target-state doctrine?
- Is the bounded milestone explicit?
- Is the phrase making MCP sound like the whole ontology?
- Is a partially restored pillar being described as fully packaged?

## Example Classifications

### Example A

Claim:

> MCP is the right practical front door for HLF.

Classification:

- current-true
- bridge-true
- vision-compatible

### Example B

Claim:

> MCP is the full meaning layer of HLF.

Classification:

- reductionist or misaligned

### Example C

Claim:

> The current packaged repo already proves a bounded recursive-build lane through `stdio`, `hlf_do`, `hlf_test_suite_summary`, and build-observation surfaces.

Classification:

- current-true
- bridge-true

### Example D

Claim:

> The repo already delivers the full target-state governed memory and coordination architecture through the MCP surface.

Classification:

- partially overstated

### Example E

Claim:

> HLF should become a governed meaning and coordination substrate larger than MCP in semantics, memory, trust, and execution.

Classification:

- vision-true
- bridge-true as a positioning statement

## Contributor Guidance

When editing public-facing docs:

- prefer current-true statements for product behavior
- allow bridge-true statements when the bounded qualifier is explicit
- keep vision-true statements clearly attached to doctrine or north-star framing
- rewrite partially overstated claims before they land in README, build guides, or release notes
- reject reductionist phrasing even if it sounds simpler

When reviewing assistant output:

- identify the lane of each major claim
- split mixed claims if one sentence spans multiple lanes
- downgrade overclaimed statements rather than arguing abstractly about tone
- route deeper doctrine questions back to vision docs and current-truth questions back to SSOT

## Short Rule Of Thumb

If a statement sounds strong, ask two questions:

1. strong in which lane?
2. strong enough for which audience?

That usually reveals whether the claim is accurate, premature, or reductive.

## Related Files

- `docs/HLF_MCP_POSITIONING.md`
- `docs/HLF_RECURSIVE_BUILD_STORY.md`
- `docs/HLF_MESSAGING_LADDER.md`
- `docs/HLF_VISION_PLAIN_LANGUAGE.md`
- `docs/HLF_STITCHED_SYSTEM_VIEW.md`
- `HLF_VISION_DOCTRINE.md`
- `SSOT_HLF_MCP.md`