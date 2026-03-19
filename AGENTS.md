# AGENTS.md

This file is the active workspace-level handover for HLF_MCP.

It exists so future agents do not start from the wrong premise, repeat the same reductionist mistakes, or treat the current packaged repo as if it were the full HLF vision.

## Start Here First

Before answering architectural questions, planning major changes, or deciding that a surface is optional, read these in order:

1. Repo memory: `/memories/repo/HLF_MCP.md`
2. Repo memory: `/memories/repo/HLF_MERGE_DOCTRINE_2026-03-15.md`
3. [docs/HLF_STITCHED_SYSTEM_VIEW.md](docs/HLF_STITCHED_SYSTEM_VIEW.md)
4. [docs/HLF_VISION_PLAIN_LANGUAGE.md](docs/HLF_VISION_PLAIN_LANGUAGE.md)
5. [docs/HLF_VISION_MAP.md](docs/HLF_VISION_MAP.md)
6. [docs/HLF_MISSING_PILLARS.md](docs/HLF_MISSING_PILLARS.md)
7. [HLF_VISION_DOCTRINE.md](HLF_VISION_DOCTRINE.md)
8. [SSOT_HLF_MCP.md](SSOT_HLF_MCP.md)
9. [HLF_ACTIONABLE_PLAN.md](HLF_ACTIONABLE_PLAN.md)

For reconstruction, extraction, or architecture-recovery work, also read:

10. [HLF_SOURCE_EXTRACTION_LEDGER.md](HLF_SOURCE_EXTRACTION_LEDGER.md)
11. [HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md](HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md)
12. [HLF_MCP_TODO.md](HLF_MCP_TODO.md)

When assessing architectural wording, MCP positioning, or maturity claims, also read:

13. [docs/HLF_CLAIM_LANES.md](docs/HLF_CLAIM_LANES.md)

For source archaeology against the upstream Sovereign repo, use:

14. [hlf_source/AGENTS.md](hlf_source/AGENTS.md)
15. [hlf_source/.github/copilot-instructions.md](hlf_source/.github/copilot-instructions.md)

## Why This File Exists

This repo did not begin as a clean, neutral greenfield implementation.

It reached the current state through an extraction and narrowing process from the larger Sovereign Agentic OS with HLF codebase. During that process, some genuinely constitutive HLF surfaces were preserved, but others were downgraded, omitted, reclassified as optional, or treated as if they were merely surrounding system scaffolding.

That created a specific failure mode:

- the packaged repo remained real and useful
- but the larger HLF vision was flattened toward a neat standalone core
- and some governance, routing, orchestration, persona, verification, and ecosystem surfaces were undercounted or excluded

This handover exists to prevent future sessions from repeating that mistake.

## The Backstory In Plain Terms

HLF is not supposed to be treated as only:

- a glyph syntax
- a parser/compiler experiment
- a small MCP wrapper
- or a tidy standalone DSL package

The intended target is larger:

HLF is meant to become an A2A-complete governed communications and programming language that connects intent, agents, tools, memory, governance, verification, and execution through one bounded meaning layer.

That means the repo must preserve and reason about more than grammar and bytecode alone.

The recovery work in this workspace was triggered by recognizing that the current repo, while substantial, still reflected contraction relative to the original doctrine and source architecture.

## The Three-Lane Doctrine

This repo must always preserve three separate lanes.

### 1. Vision lane

North-star scope. This is allowed to be bigger than what is already implemented.

Primary files:

- [HLF_VISION_DOCTRINE.md](HLF_VISION_DOCTRINE.md)
- [RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md](RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md)
- [docs/HLF_DESIGN_NORTH_STAR.md](docs/HLF_DESIGN_NORTH_STAR.md)

### 2. Current-truth lane

Only what is implemented, validated, and honest to claim now.

Primary files:

- [SSOT_HLF_MCP.md](SSOT_HLF_MCP.md)
- [HLF_QUALITY_TARGETS.md](HLF_QUALITY_TARGETS.md)
- [BUILD_GUIDE.md](BUILD_GUIDE.md)

### 3. Bridge lane

How this repo professionally converges from current truth toward the full target.

Primary files:

- [HLF_ACTIONABLE_PLAN.md](HLF_ACTIONABLE_PLAN.md)
- [HLF_CANONICALIZATION_MATRIX.md](HLF_CANONICALIZATION_MATRIX.md)
- [HLF_IMPLEMENTATION_INDEX.md](HLF_IMPLEMENTATION_INDEX.md)

Never collapse these three lanes into one flattened story.

## Non-Negotiable Reconstruction Rules

These rules were established because earlier work drifted toward simplification by omission.

1. Recover omitted or downgraded HLF pillars from source and doctrine before assuming the packaged surface is sufficient.
2. Classify damaged areas explicitly as one of:
   - strong but misaligned
   - strong but not yet packaged
   - wrongly replaced
   - wrongly deleted
3. Ban pseudo-equivalents.
4. Ban fake stand-ins.
5. Ban simplifications that replace stronger original architecture with easier packaged-core substitutes.
6. Do not use standalone neatness as the deciding heuristic when a surface carries doctrine, routing, personas, governance workflow, verification, or ecosystem meaning.
7. Rebuild from original intent outward, not from MVP inward.

## What Counts As Constitutive, Not Merely Supportive

Do not restrict HLF archaeology to files with HLF in the name.

In this repo’s recovery work, the following have already been recognized as often constitutive:

- governance spine surfaces
- gateway and routing fabric
- orchestration lifecycle files
- formal verification direction
- memory, provenance, and audit substrate
- persona and operator doctrine
- ecosystem integration plans and host-function worldview
- human-legibility surfaces such as galleries, explainers, and operator references

If removing a surface narrows HLF from governed agent language into a parser-only fragment, it is not merely supportive.

## What Got Us Here

The current repo contains real value:

- packaged `hlf_mcp/` product surface
- retained legacy `hlf/` compatibility line
- compiler, formatter, linter, runtime, capsules, memory, lifecycle, server, docs, governance assets, examples, and extracted tools

But source analysis also showed that the upstream Sovereign repo contains broader HLF-bearing architecture spread across:

- `agents/gateway/`
- `agents/core/`
- `config/personas/`
- `governance/`
- `scripts/`
- `docs/`

The recovery effort therefore shifted from “what neat package can we preserve?” to “what real HLF pillars were lost, blurred, or under-modeled?”

That is the correct framing.

## How We Are Solving It Now

The current professional recovery method is:

1. Preserve current truth without overstating it.
2. Preserve the full vision without pretending it is already shipped.
3. Build a bridge using extraction ledgers, context maps, and pillar-based planning.
4. Use source archaeology against the Sovereign repo to identify constitutive surfaces.
5. Rank recovery work by real architectural importance, not packaging convenience.
6. Plan forward work around HLF pillars, not just repo cleanup.

In practice, this means:

- keeping current-truth claims in [SSOT_HLF_MCP.md](SSOT_HLF_MCP.md)
- keeping vision doctrine in [HLF_VISION_DOCTRINE.md](HLF_VISION_DOCTRINE.md)
- using [HLF_SOURCE_EXTRACTION_LEDGER.md](HLF_SOURCE_EXTRACTION_LEDGER.md) and [HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md](HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md) for reconstruction judgment
- using Ollama-assisted focused source interrogation only as an aid, not as authority by itself
- requiring that future design decisions show lineage back to original HLF intent

## Working Style Required For This Repo

When operating in this workspace:

1. Check repo memory before major decisions.
2. Distinguish vision claims from current implementation claims.
3. Do source comparison before declaring anything optional, superseded, or out of scope.
4. Prefer faithful restoration or principled porting over thin replacements.
5. Document why something stays source-only if it is constitutive but not yet restored.
6. Keep planning artifacts updated when recovery understanding changes.

## If You Are Planning New Work

Use this sequence:

1. Read repo memory and doctrine files listed above.
2. Decide which lane the task belongs to: vision, current truth, or bridge.
3. If the task touches architecture, recovery, doctrine, governance, routing, personas, lifecycle, verification, or ecosystem scope, consult the extraction ledger and supportive source context map before editing code.
4. State whether the work is:
   - restoration
   - faithful port
   - bridge implementation
   - current-truth validation
5. Only then write or modify code.

## If You Are Reviewing The Repo

Default questions:

1. Is this claim current truth, vision, or bridge?
2. Has any constitutive surface been flattened into a weaker substitute?
3. Does this change preserve operator trust, governance legibility, and architectural intent?
4. Does this move the repo toward full HLF completion professionally, or only toward a tidier package?

If wording or positioning is part of the review, classify the claim explicitly with `docs/HLF_CLAIM_LANES.md` before reusing or promoting it.

## Final Directive

Do not treat this repository as a finished minimal core.

Treat it as a serious, partially recovered implementation on the path toward a larger governed language system, and do the remaining work with professional fidelity to that original vision.