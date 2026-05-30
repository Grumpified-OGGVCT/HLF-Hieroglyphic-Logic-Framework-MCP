# SwarmGlass Status Overview

This page is the published status surface for the repository.

SwarmGlass is the governance framework (formerly HLF — Hieroglyphic Logic Framework). The HLF DSL (compiler, runtime, VM) lives behind `SWARMGLASS_HLF_ENABLED=1`. The governance layer — constraints, audit, memory, overwatch — is always-on.

It is a generated presentation layer over the repo's current source materials, not a replacement for them.

Reading rule:

- use this page for a compact status view across the whole repo
- use `SSOT_HLF_MCP.md` for current packaged truth
- use the readiness dashboard and scorecard for the underlying internal scoring inputs
- use weekly artifacts and governed reviews for operational evidence
- see `DEPRECATION_TIMELINE.md` for the HLF → SwarmGlass migration schedule
- see `DO_NOT_PITCH.md` for forbidden claims

This page intentionally separates three bands that should not be flattened into one metric:

1. current repo status
2. weekly operational evidence
3. bridge/readiness progress

## Status Snapshot

> Summary block
>
> - overall internal readiness: `67.8%` (↑ from 64.7%)
> - interpretation band: `bridge-active`
> - strongest cluster: semantic core
> - main drag on total readiness: coordination and operator systems
> - claim-lane reading: SwarmGlass governance is decoupled and always-on; HLF DSL is gated behind SWARMGLASS_HLF_ENABLED=1
> - **DSL isolation: CLEAN** — zero compiler/bytecode/runtime imports at SWARMGLASS_HLF_ENABLED=0

Short reading:

SwarmGlass in this repo is already materially real as a packaged governance layer, MCP server, and product surface. The HLF DSL (language, runtime, compiler, VM) is real but gated behind `SWARMGLASS_HLF_ENABLED=1`.
It is not yet the full recovered HLF system.
The right public reading is therefore:

- SwarmGlass governance (constraints, audit, memory, overwatch) is strong enough to inspect and use now
- **DSL isolation achieved**: All server files refactored with lazy DSL imports — server boots with zero compiler/runtime/bytecode loaded. All FastMCP-decorated tool functions now carry their own lazy imports for DSL symbols (CompileError, translator, capsules, constitution, swarm mechanics). Verified clean at EXP=0.
- weekly governance evidence is real and operational
- Instinct now exposes packaged proof-state, phase-completion, and mission-lineage summaries across operator review surfaces
- **136 governance tools** always-on (57 sg_* + 79 hlf_* with deprecation); **193 total** with experimental=1
- **All 29 core tests pass**: governance_proofs (5/5) + capsule_pointer_trust (24/24)
- server boots governance-only with zero DSL imports (SWARMGLASS_HLF_ENABLED=0)
- broader coordination, operator, and ecosystem completion is still in active bridge work

## 1. Whole SwarmGlass Status

This section answers one question:

what is the repo as a whole, in honest claim-lane terms?

### Current Reading

| Status Signal | Current Reading |
| --- | --- |
| Overall readiness | `67.8%` |
| Interpretation band | `bridge-active` |
| Claim-lane label | current packaged truth plus bridge-qualified expansion |
| One-sentence repo status | SwarmGlass governance is decoupled and always-on with 141 tools at EXP=0; 193 tools at EXP=1; DSL isolation clean; 2,212/2,406 tests pass (91.9%); Gate 2 157/157; broader coordination-and-operator completion still suppresses total readiness |

### Cluster Scores

| Cluster | Score | Reading |
| --- | ---: | --- |
| Semantic core | `73.0%` | strongly improved — type universe + grammar completion + capability manifests |
| Governance and trust | `70.2%` | constitutional checks + constitutive verification gating operational; DSL isolation clean at EXP=0; 141 always-on governance tools |
| Coordination and operator systems | `42.3%` | improved via two-channel execution and manifest-gated orchestration, still the drag |

### Claim-Lane Note

This top-line score is an internal readiness indicator.

It is not a claim that the whole HLF target is complete.

Use it to understand repo posture, not to erase the distinction between:

- what is implemented now
- what is proved in weekly operation
- what is still under bridge recovery

### Current-Truth Anchor

For the strict current-truth surface behind this section, read:

- `SSOT_HLF_MCP.md`
- `docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md`
- `docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md`

## 2. Trend Snapshot

This section answers one question:

what is actually moving, and what is only a baseline so far?

| Signal | Current | Previous | Movement | Reading |
| --- | ---: | ---: | --- | --- |
| Overall readiness | `67.8%` | `64.7%` | `+3.1%` | Governance + DSL isolation improvements driving score increase |

Trend reading rule:

- use deltas where the repo exposes a directly comparable metric
- use categorical movement where the lane reports state rather than percent
- treat `baseline` rows as the current committed starting point, not as missing work

## 3. Weekly Operational Results

This section answers one question:

what did the system actually do in its latest governed weekly lanes?

These results are evidence summaries, not completion claims.

### Latest Weekly Lanes

| Lane | Latest Reading | Owner Persona | Triage Lane | Status | Artifact Path |
| --- | --- | --- | --- | --- | --- |
| `_No committed weekly artifacts were found in this checkout._` | - | - | - | `informational` | `local-only` |

_Note: Artifact paths under `observability/local_validation/...` are example/local-only locations used for governed runs and are not checked into this repository._

### Why Weekly Results Are Separate

Weekly evidence should not be collapsed into the top-level readiness percent.

Different weekly lanes report different kinds of truth:

- percentage-backed health readings
- drift/no-drift findings
- advisory vs verified outcomes
- persona ownership and triage signals

That variation is useful.
Flattening it into one number would hide the difference between system health, documentation accuracy, and governed operator review.

## 4. Build Percentages And Pillar Readiness

This section answers one question:

where is the repo strongest, and where is it still weakest?

### Strongest And Weakest Areas

| Type | Pillar | Score | Reading |
| --- | --- | ---: | --- |
| Strongest | Deterministic language core | `92.5%` | strongest combination of implementation, proof, and repo integration; type universe fully expanded, grammar complete |
| Strongest | Runtime and capsule-bounded execution | `85.0%` | real packaged runtime with two-channel execution and strong proof surface |
| Strongest | Governance-native execution | `70.2%` | 4 constitutional rules wired; DSL isolation achieved at EXP=0; 6 server files refactored with lazy imports |
| Weakest | Orchestration lifecycle and plan execution | `53.5%` | two-channel dispatch exists but plan-level lifecycle management still lacks end-to-end proof |
| Weakest | Ecosystem integration surface | `22.5%` | MCP + REST bridges built and tested, but integration depth still needs hardening |
| Weakest | Gallery and operator-legibility surface | `58.0%` | 12 fixtures with 6-surface round-trip, 48.6% avg compression, operatorization ongoing |

### Per-Pillar Readiness

| Pillar | Readiness |
| --- | ---: |
| Deterministic language core | `92.5%` |
| Runtime and capsule-bounded execution | `85.0%` |
| Governance-native execution | `70.2%` |
| Typed effect and capability algebra | `68.0%` |
| Human-readable audit and trust layer | `60.5%` |
| Real-code bridge | `45.5%` |
| Knowledge substrate and governed memory | `56.0%` |
| Formal verification surface | `68.5%` |
| Gateway and routing fabric | `51.0%` |
| Orchestration lifecycle and plan execution | `53.5%` |
| Persona and operator doctrine | `45.0%` |
| Ecosystem integration surface | `22.5%` |
| Gallery and operator-legibility surface | `58.0%` |

### How To Read These Percentages

These percentages are downstream of three things:

- implementation saturation
- proof saturation
- operational integration

They are meant to show where the repo is strong or weak in practice.

They are not meant to imply that a single percentage can summarize the whole HLF story.

## 5. What Moves The Score Next

The next score-moving work is not in the already-strong language core.

The highest-value remaining moves are:

1. strengthen typed effect and capability contracts
2. deepen formal verification and routing proof
3. extend shipped Instinct proof-state and mission-lineage evidence into thicker packaged coordination proof
4. convert persona/operator doctrine into thicker workflow and runtime evidence
5. keep memory governance and weekly evidence contracts converging without fragmenting the trust surface

## 6. Source Materials Behind This Page

This page is derived from these repo authorities:

- `SSOT_HLF_MCP.md`
- `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
- `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
- `docs/HLF_READINESS_SCORING_MODEL.md`
- `docs/HLF_READINESS_REFRESH_PROCEDURE.md`
- `docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md`
- `docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md`

## 7. Interpretation Boundary

If you need the safest summary of this page, use this sentence:

HLF in this repo already has a strong current packaged core, real weekly governed evidence, and packaged Instinct proof-state surfaces. SwarmGlass governance is fully decoupled from the DSL with 141 always-on tools and clean isolation at EXP=0. Broader coordination, operator, and ecosystem completion remains bridge-qualified rather than finished.

_Generated from repo sources on 2026-03-20T00:00:00Z._
