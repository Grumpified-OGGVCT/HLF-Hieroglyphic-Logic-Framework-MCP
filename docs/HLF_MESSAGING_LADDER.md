# HLF Messaging Ladder

This document derives audience-specific phrasing from the canonical explanation in `docs/HLF_RECURSIVE_BUILD_STORY.md`.

Its purpose is to:

- keep messaging aligned across public surfaces
- preserve current-proof boundaries
- let different readers receive the same truth at the right resolution

This is a messaging ladder, not a replacement for doctrine, SSOT, or architecture documents.

## Source Authority

Use this file only in alignment with:

- `docs/HLF_RECURSIVE_BUILD_STORY.md`
- `docs/HLF_VISION_PLAIN_LANGUAGE.md`
- `SSOT_HLF_MCP.md`
- `HLF_ACTIONABLE_PLAN.md`

If any version in this file drifts from those sources, the canonical and current-truth documents win.

## Ladder Rules

Every audience-specific version should preserve all three of these properties:

1. architecturally meaningful
2. externally legible
3. disciplined by current proof boundaries

That means every reusable phrasing should:

- connect the recursive-build idea to the larger HLF shape
- remain understandable to a reader who has not done source archaeology
- avoid promoting bounded local proof into broad self-hosting claims

## Core Meaning To Preserve

The stable meaning underneath every version is:

HLF is not only intended to be useful after the system is finished.
It is intended to become useful during construction, verification, and recovery as well.

The current honest proof remains bounded:

- local before remote
- bounded before broad
- auditable before ambitious
- proof before promotion

## Terms To Prefer

Prefer these phrases when describing the recursive-build idea:

- bounded recursive build assistance
- governed build-assist loop
- product evidence during construction
- local, inspectable self-assist lane
- staged reduction of the gap between build, operation, and audit

## Terms To Use Carefully

These phrases are not banned, but they require extra qualification:

- recursive build
- self-assist
- self-verification
- self-hosting
- system helping finish itself

If they are used, make the bounded milestone explicit.

## Terms To Avoid In Current Truth

Do not use these as present-tense repo claims unless new proof lands:

- fully self-hosting
- end-to-end recursive autonomy
- complete self-building system
- remote recursive operation is already solved
- HLF now builds itself

## Messaging Ladder

### 1. README Version

Use when the reader needs a strong front-door explanation that is still disciplined.

Recommended version:

> HLF is not only meant to be useful after the system is finished. It is being shaped into a governed language and coordination layer that can already help inspect state, summarize regressions, explain intended actions, and preserve evidence during parts of its own build and recovery process. That does not mean full self-hosting is complete. It means the repo already contains a bounded, inspectable proof that construction, operation, and audit can begin to converge inside the same governed system.

Why this version works:

- it keeps the full HLF shape visible
- it tells first-time readers why the idea matters
- it states the boundary against overclaiming

### 2. Quickstart Version

Use when the reader needs immediate practical relevance more than architectural sweep.

Recommended version:

> The same packaged MCP surface you can install is already used in a bounded build-assist loop inside this repo. Today that means HLF can help express build intent, inspect repo state, summarize regressions, and preserve evidence through governed surfaces such as `hlf_do`, `hlf_test_suite_summary`, and `_toolkit.py status`.

Why this version works:

- it stays close to concrete surfaces
- it explains why the quickstart matters now
- it avoids remote or maximal claims

### 3. Release Notes Version

Use when the reader needs a public-safe explanation of what changed and why it matters.

Recommended version:

> This release strengthens the repo's recursive-build story by making it explicit, canonical, and easier to read across major documentation surfaces. HLF's current claim remains bounded: the packaged system already supports a local build-assist loop that helps inspect state, summarize regressions, explain intended actions, and preserve audit evidence, while stronger self-hosting claims remain gated behind additional proof.

Shorter release-note variant:

> Canonicalized the recursive-build story and aligned major docs around one public-safe explanation of HLF's bounded local build-assist loop.

Why this version works:

- it is change-focused rather than visionary-only
- it describes the improvement without hype
- it is safe for public release summaries

### 4. External Summary Version

Use for previews, repository listings, issue summaries, handoffs, or short public descriptions.

Recommended version:

> HLF is a governed language and MCP-based system that is designed to be useful not only after deployment, but during its own build and recovery process. In its current proven form, it already supports a bounded local loop for expressing intent, inspecting state, summarizing regressions, and preserving operator-reviewable evidence.

Compact variant:

> HLF's distinctive claim is not just governed execution after the build. It is bounded, inspectable build assistance during the build.

Why this version works:

- it is reusable outside the repo
- it preserves the distinctive claim
- it stays inside current proof boundaries

## Audience Notes

### First-Time Reader

Emphasize:

- why this is distinctive
- what is real today
- why bounded proof matters

Avoid:

- long doctrine language before basic orientation

### Builder Or Contributor

Emphasize:

- current milestone
- workflow surfaces
- anti-overclaim boundary

Avoid:

- vague visionary language without specific packaged surfaces

### Architecture-Minded Reader

Emphasize:

- why this concept protects the full HLF shape
- how current proof relates to target-state architecture
- why routing, governance, memory, orchestration, and human-legibility surfaces remain constitutive

Avoid:

- treating the packaged MCP surface as the whole story

### Public-Facing Reader

Emphasize:

- distinctiveness
- bounded evidence
- disciplined claims

Avoid:

- insider shorthand that assumes prior repo context

## Reuse Pattern

When writing a new public-facing surface, follow this sequence:

1. start from `docs/HLF_RECURSIVE_BUILD_STORY.md`
2. choose the closest ladder version in this file
3. adapt for audience length and context
4. recheck against `SSOT_HLF_MCP.md` if any maturity claim changed

## Editorial Guardrail

If a draft makes the recursive-build idea sound more dramatic, magical, or mature than the underlying proof, step it back.

The value of this concept comes from disciplined evidence, not from sounding futuristic.

## Related Files

- `docs/HLF_RECURSIVE_BUILD_STORY.md`
- `README.md`
- `QUICKSTART.md`
- `BUILD_GUIDE.md`
- `SSOT_HLF_MCP.md`