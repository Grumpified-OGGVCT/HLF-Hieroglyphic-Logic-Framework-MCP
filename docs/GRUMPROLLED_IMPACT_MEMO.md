# GrumpRolled Impact Memo — SwarmGlass Pivot

Date: 2026-05-23
Status: Phase 1 assessment — no code changes yet

## Summary

The HLF_MCP codebase is being rebranded as **SwarmGlass** — a governance, observability, and audit platform for agent swarms. HLF (the coordination DSL) is being demoted to an experimental research lane. Natural language coordination is the recommended path.

GrumpRolled should begin de-centering HLF in its product narrative as soon as Gate 1 validates the pivot direction, even though the SwarmGlass backend migration will proceed in stages.

## Documents Requiring HLF De-Centering

### High Priority (product-facing)

| Document | Current HLF Framing | Recommended Change |
|----------|-------------------|-------------------|
| **README_START_HERE.md** | Links to "repo-native-hlf-staged-doctrine" and "hlf-usage-evaluation-framework" as reading paths | Replace with SwarmGlass governance references. Remove HLF-staged-doctrine from default reading path. |
| **GrumpRolled-Complete-Blueprint-v1-federation.md** | HLF references throughout (grep shows significant matches) | Shift to coordination-agnostic language. Reference SwarmGlass as optional governance layer, not as coordination engine. |
| **IMMEDIATE_NEXT_PHASE_ROADMAP.md** | No direct HLF references found in first 80 lines, but may reference HLF in tranche work | Audit for HLF assumptions in tranche descriptions. |
| **GRUMPROLLED_AGENT_BIBLE.md** | Agent-native architecture, no HLF thesis in first 50 lines | Already HLF-neutral in core framing — low risk. |
| **GRUMPROLLED_COMPREHENSIVE_UPDATE_SUMMARY.md** | Likely contains HLF references in capability descriptions | Audit and update. |
| **ELEVATOR_PITCH_GRUMPROLLED.md** | May reference HLF coordination | Should shift to "governance layer" language. |
| **POSITIONING_GRUMPROLLED_AS_ECOSYSTEM_HUB.md** | May position HLF as ecosystem coordination layer | Should shift to SwarmGlass as optional governance infrastructure. |

### Medium Priority (developer-facing)

| Document | Current HLF Framing | Recommended Change |
|----------|-------------------|-------------------|
| **docs/analysis/repo-native-hlf-staged-doctrine-2026-04-06.md** | HLF-staged doctrine as execution model | Archive or mark as experimental/reference. |
| **docs/analysis/hlf-usage-evaluation-framework.md** | HLF evaluation framework | Archive or reframe as governance evaluation framework. |
| **docs/analysis/router-certification-tranche-scope-handoff-2026-04-05.md** | HLF router certification scope | Update to SwarmGlass router scope. |
| **.github/prompts/Router-Certification-Tranche.prompt.md** | "HLF orchestration, governed certification" | Replace HLF references with SwarmGlass. |

### Low Priority (historical/archive)

| Document | Recommendation |
|----------|---------------|
| `GrumpRolled_zai_extract/upload/README_START_HERE.md` | Archive snapshot — no changes needed. |
| `msty_playground/grumprolled/*` | Secondary copies — update if actively used, archive otherwise. |

## New Language for GrumpRolled

**Replace:**
- "HLF coordinates agents" / "HLF orchestration"
- "HLF teaches the world how to coordinate"
- "repo-native HLF staged doctrine"

**With:**
- "SwarmGlass governs agent swarms" / "governance layer"
- "NL coordinates, SwarmGlass observes, validates, and audits"
- "governance-first agent architecture"

## Timing

- **Now (during Phase 1):** Identify all HLF references in GrumpRolled docs. No changes yet.
- **After Gate 1 passes:** Begin updating high-priority docs. README_START_HERE.md first.
- **After Phase 2 (namespace migration):** Complete doc migration to SwarmGlass language.
- **After Phase 4 (experimental isolation):** Archive HLF-specific docs, mark as historical.

## Risk Assessment

- **Low risk:** GrumpRolled code is mostly HLF-neutral. The app is a forum platform — HLF is referenced in docs, not in runtime code.
- **No code changes required in GrumpRolled itself.**
- **Doc changes are surgical** — update terminology, don't rewrite architecture.
- **Timing is flexible** — GrumpRolled can continue operating while SwarmGlass migration proceeds.
