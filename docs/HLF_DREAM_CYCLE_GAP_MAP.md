# HLF Dream-Cycle Gap Map

## Purpose

This document maps the external dream-system note in `C:\Users\gerry\ollama_proxy_server\DREAM_AWARENESS_INTEGRATION.md` onto the current HLF_MCP repository.

It does three things:

1. separates source-era dream authority from packaged current truth
2. marks each dream capability as `present`, `adjacent`, or `missing`
3. identifies the safest packaged insertion point for a minimal governed dream-cycle bridge

This document is a bridge artifact, not a current-truth product claim.

Use `docs/HLF_CLAIM_LANES.md` when reusing any statement from this file.

## Claim-Lane Classification

- `current-true`: packaged HLF_MCP already has governed memory, witness, audit, operator resources, and weekly artifact surfaces that can host bounded reflection outputs
- `bridge-true`: HLF_MCP should recover a minimal governed dream-cycle bridge over those packaged surfaces
- `vision-true`: HLF should eventually support deeper offline synthesis and governed learning loops larger than the current packaged implementation
- `not current-true`: packaged HLF_MCP does not currently ship a first-class dream-cycle tool, resource family, or runtime module

## Source Authorities and Packaged Anchors

### Source-era dream authorities

- `hlf_source/agents/core/dream_state.py`
- `hlf_source/mcp/sovereign_mcp_server.py`
- `C:\Users\gerry\ollama_proxy_server\DREAM_AWARENESS_INTEGRATION.md`

### Current packaged anchors

- `hlf_mcp/server_context.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_resources.py`
- `hlf_mcp/weekly_artifacts.py`
- `hlf_mcp/hlf/witness_governance.py`
- `hlf_mcp/rag/memory.py`

## Executive Judgment

The repo did not forget dream cycles completely.

What happened instead is narrower and more defensible:

- the explicit dream subsystem stayed mostly in source-era and bridge-lane material
- the packaged repo retained adjacent constitutive pieces that can support a bounded recovery
- the missing part is the contract that turns accumulated evidence into governed offline synthesis outputs

That means the correct move is not to restore a theatrical self-awareness subsystem.

The correct move is to recover a governed dream-cycle bridge that:

- consumes bounded evidence
- synthesizes candidate findings offline
- records provenance and witness state
- exposes operator-readable results
- never silently mutates truth without promotion gates

## Gap Table

| Dream-note capability | Source-era authority | Packaged HLF_MCP surface | Status | Interpretation |
| --- | --- | --- | --- | --- |
| wake-state exploration produces material for later synthesis | `dream_state.py` experience intake, external note wake-state loop | weekly evidence, benchmark artifacts, memory storage, witness observations | adjacent | Packaged repo has evidence intake, but not a named dream-input contract |
| explicit sleep or dream cycle trigger | `run_dream_cycle` in `sovereign_mcp_server.py` | no packaged dream-cycle tool or scheduler contract | missing | Trigger contract needs recovery |
| consolidation from prior sessions into synthesized findings | `DreamStateEngine` synthesizes rules from experiences | no first-class packaged synthesis stage over stored evidence | missing | This is the core capability gap |
| persistence of dream outputs | dream reports and dream history in source-era code | memory, RAG, weekly artifacts, witness state | adjacent | Persistence substrate exists, but not a dedicated dream-finding record |
| topic or quality filtering of dream outputs | dream quality scoring and topic retrieval in external note and source-era design | memory query and artifact retrieval are present, but no dream-specific scoring contract | adjacent | Retrieval exists, quality schema does not |
| explicit self-evolution dream retrieval | external note `get_self_evolution_dreams()` | no packaged dream retrieval tool | missing | Needs packaged tool or resource recovery |
| self-awareness prompt injection | external note injects dreams into self-awareness cycles | packaged repo has operator and evidence surfaces, but no dream-context injector | missing | Defer strong self-awareness framing; recover as governed reflection context |
| use dream outputs as improvement inputs | source-era dream-to-rule path, external note improvement-cycle integration | autonomous-evolution bridge plan already tracks `observe -> propose -> verify -> promote` | adjacent | The loop exists conceptually, but dream outputs are not yet one of its formal evidence classes |
| dream statistics | source-era dream history and external note metrics | no packaged dream metrics surface | missing | Add bounded dream-cycle metrics after schema exists |
| admin or operator endpoint for dream results | source-era MCP methods and external note endpoints | operator resources exist in `server_resources.py` | adjacent | Best operator exposure seam already exists |
| audit or trust binding for dream outputs | source-era logic implies retained reports; external note does not fully govern promotion | audit chain, witness governance, weekly artifacts already exist | present for substrate, missing for dream-specific contract | The trust substrate is already packaged, which is why this bridge can be governed |

## Present, Adjacent, Missing

### Present now

These are current packaged truths that materially support dream-cycle recovery:

- governed memory capture and query surfaces
- witness governance and operator trust snapshots
- audit-chain and governance-event recording through shared context
- weekly evidence artifact production and storage
- operator-facing resource publication through `server_resources.py`

### Adjacent now

These are partly-real surfaces that can host the bridge but do not yet constitute dream capability by themselves:

- weekly artifacts as evidence inputs to offline synthesis
- translation-memory and exemplar storage as candidate source material
- autonomous-evolution planning as the receiving lane for bounded findings
- operator resources as the right visibility plane for dream findings

### Missing now

These are the specific bridge gaps that prevent honest present-tense dream claims:

- a packaged dream-cycle trigger and execution contract
- a typed dream-finding or reflection-finding schema
- quality, provenance, and supersession rules for dream outputs
- operator resource(s) exposing dream findings and metrics
- a bounded rule saying how dream findings may influence proposals or memory promotion

## Best Packaged Insertion Point

### Primary insertion seam: `hlf_mcp/server_context.py`

This is the strongest packaged seam for a minimal governed dream-cycle bridge because it already centralizes:

- shared memory access
- witness governance
- audit or governance-event emission
- validated-solution capture
- session and evidence context

The dream bridge belongs here first because the core missing capability is contextual synthesis over already-governed evidence, not a standalone storage layer.

### Supporting seams

#### `hlf_mcp/server_memory.py`

Use this surface for:

- tool-facing capture and retrieval of dream findings
- query filters by topic, quality, recency, and provenance
- explicit operator actions such as listing or storing governed reflection outputs

#### `hlf_mcp/server_resources.py`

Use this surface for:

- operator-readable dream status and dream findings resources
- side-by-side machine authority and human-readable summaries
- trust-safe visibility without inventing a separate GUI surface first

#### `hlf_mcp/weekly_artifacts.py`

Use this surface for:

- bounded offline input material for dream synthesis
- summarized reflection artifacts
- deterministic evidence packaging before findings reach longer-lived memory or proposal lanes

## Why Not Restore the Old Dream System Directly

The old dream architecture should not be copied into packaged HLF_MCP unchanged.

Reasons:

- its framing leans too close to open-ended self-awareness language
- the packaged repo has stronger governance and trust surfaces than the external note assumes
- a direct copy would overfit to source-era system boundaries instead of current packaged authority
- the packaged repo needs bounded synthesis over governed evidence, not a loosely-bounded autonomous cognition narrative

## Minimal Governed Bridge Definition

The first acceptable dream-cycle bridge should be defined as:

"A bounded offline synthesis cycle that consumes governed evidence, produces auditable dream findings, records provenance and witness state, and exposes operator-readable outputs without directly mutating runtime truth."

That definition is stricter and better than the older self-awareness framing because it preserves the useful capability while fitting the repo's existing trust model.

## Recommended First Bridge Slice

### Inputs

- weekly evidence artifacts
- stored memory exemplars
- validated solutions and witness observations
- optionally, bounded operator-selected evidence subsets

### Process

- gather a bounded evidence window
- synthesize candidate findings
- score findings for confidence, novelty, and evidence coverage
- record provenance and witness linkage
- emit an auditable dream-cycle report

### Outputs

- `dream finding` records with typed fields
- dream-cycle summary metrics
- operator-readable resources
- advisory proposal inputs for the autonomous-evolution lane

### Explicit non-goals for the first slice

- direct self-modification
- unrestricted self-awareness claims
- hidden model-context injection without audit record
- unrestricted ingestion of dream outputs into canonical truth

## Relation to Autonomous Evolution

Dream-cycle recovery is not a separate ideology lane.

It is one bounded sub-lane inside the broader autonomous-evolution bridge:

- `observe`: collect evidence
- `dream`: perform offline governed synthesis over that evidence
- `propose`: convert high-quality dream findings into bounded candidate actions
- `verify`: run lifecycle, audit, and test gates
- `promote`: only then allow truth-affecting adoption

That means dream-cycle work belongs alongside the autonomous-evolution bridge, memory governance, and operator trust surfaces.

## Risks

- If dream findings are phrased as consciousness or self-awareness truth, claim discipline will drift.
- If dream outputs bypass witness and audit binding, operator trust will fall.
- If dream findings directly rewrite memory or routes without promotion gates, the bridge becomes unsafe.
- If the bridge is framed as a whole new subsystem instead of a bounded synthesis layer, implementation scope will bloat and doctrinal clarity will weaken.

## Next Documents

- `docs/HLF_DREAM_CYCLE_BRIDGE_SPEC.md`
- `plan/feature-autonomous-evolution-1.md`
- `HLF_ACTIONABLE_PLAN.md`
- `HLF_MCP_TODO.md`
- `TODO.md`