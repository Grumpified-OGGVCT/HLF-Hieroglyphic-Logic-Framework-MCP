# HLF README Operationalization Matrix

Status: bridge-lane proof matrix for public README claims on 2026-03-19.

Purpose:

- map major public-facing claims to one of `implemented now`, `bridge work`, `vision only`, or `source-context evidence`
- define the proving artifact required before a bridge claim can graduate upward
- stop README ambition from drifting free of measurable recovery work
- keep doctrine expansive while forcing the repo to earn strong present-tense claims
- keep README claim changes aligned with `docs/HLF_CLAIM_LANES.md` rather than relying on ad hoc judgment

## Status Vocabulary

This matrix is README-specific, but it should be used alongside `docs/HLF_CLAIM_LANES.md`.

Practical translation:

- `implemented now` maps to `current-true`
- `bridge work` maps to `bridge-true`
- `vision only` maps to `vision-true`
- `source-context evidence` should not be promoted into present-tense product language without bridge or current-truth proof

- `implemented now`: backed by packaged code and present-tense truth in this repo
- `bridge work`: a real target with partial packaged support, but still missing a required proof or recovery artifact
- `vision only`: part of doctrine and north-star scope, but not yet represented strongly enough to claim beyond aspiration
- `source-context evidence`: strongly evidenced in upstream doctrine or source, but not yet restored into packaged truth

## Claim Matrix

| Claim Family | README Status | Required Proving Artifact | Primary Quality Dimension | Current References | Next Action |
| --- | --- | --- | --- | --- | --- |
| Governed meaning layer | `bridge work` | `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` plus operator-readable route/policy/verifier evidence surfaces | safety and governance quality | `README.md`, `SSOT_HLF_MCP.md`, `docs/HLF_PILLAR_MAP.md` | Prove that intent, policy, tools, and audit outputs form one inspectable chain |
| Deterministic orchestration | `bridge work` | replay-determinism benchmark and orchestration trace proofs, including delegation, dissent, escalation, and handoff-lineage evidence | execution cleanliness, swarm coordination quality | `README.md`, `HLF_QUALITY_TARGETS.md`, `docs/HLF_PILLAR_MAP.md` | Complete the packaged execute path on top of the existing lifecycle base and add replay-equivalence evidence |
| Five-surface language | `bridge work` | round-trip proof suite covering glyph/ascii/AST/bytecode/audit or listing equivalents | intent capture accuracy, compression efficiency | `README.md`, `SSOT_HLF_MCP.md`, `docs/HLF_PILLAR_MAP.md` | Add explicit round-trip validation rather than relying on architecture diagrams alone |
| Cryptographic governance | `bridge work` | governance control matrix plus chain/pointer verification artifacts | safety and governance quality | `README.md`, `SSOT_HLF_MCP.md`, `docs/HLF_PILLAR_MAP.md` | Expand audit-chain, pointer-trust, and manifest proof surfaces into one operator-readable control story |
| Gas metering | `implemented now` | existing runtime tests plus expanded verifier-backed gas-bound checks | execution cleanliness | `README.md`, `SSOT_HLF_MCP.md` | Keep current truth; later strengthen with formal gas verification |
| HLF knowledge substrate and governed memory | `bridge work` | unified evidence schema with provenance, freshness, confidence, trust-tier, supersession, and expiry tests | tool contract reliability, safety and governance quality | `README.md`, `SSOT_HLF_MCP.md`, `HLF_QUALITY_TARGETS.md`, `docs/HLF_PILLAR_MAP.md`, `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` | Finish memory-governance recovery spec, keep external donor patterns source-audited, and enforce runtime contracts |
| Instinct lifecycle | `bridge work` | orchestration recovery spec and deterministic lifecycle execution traces | swarm coordination quality | `README.md`, `SSOT_HLF_MCP.md`, `docs/HLF_PILLAR_MAP.md` | Complete plan execution, delegation, dissent, escalation, and handoff lineage on top of the current lifecycle and orchestration base |
| Formal verification | `bridge work` | solver-backed packaged verifier behavior, proof serialization, and negative/positive verification regressions | execution cleanliness, safety and governance quality | `README.md`, `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`, `docs/HLF_PILLAR_MAP.md` | Replace the thin packaged verifier boundary with real proof execution grounded in upstream semantics |
| Routing fabric | `bridge work` | routing recovery spec, route-evidence resources, and fail-closed route tests | swarm coordination quality, execution cleanliness | `README.md`, `docs/HLF_PILLAR_MAP.md`, `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` | Finish Batch 1 routing proof and route-trace ownership |
| Code generation / real-code bridge | `bridge work` | fixture-based output proof matrix and target-specific equivalence checks | execution cleanliness, tool contract reliability | `README.md`, `SSOT_HLF_MCP.md`, `docs/HLF_PILLAR_MAP.md` | Add proof surfaces before broadening target claims |
| Human-readable audit | `bridge work` | operator-readable summaries grounded in structured evidence objects plus regression checks against drift | safety and governance quality, intent capture accuracy | `README.md`, `docs/HLF_PILLAR_MAP.md` | Expand route, verifier, promotion, and memory evidence summaries |
| Ecosystem integration | `source-context evidence` | ecosystem checkpoint after Batch 2 plus bounded host-function integration plan | swarm coordination quality, tool contract reliability | `README.md`, `docs/HLF_REJECTED_EXTRACTION_AUDIT.md`, `docs/HLF_PILLAR_MAP.md` | Keep as constitutive scope without overstating packaged truth |

## Narrative Constraints

### 1. What may remain strong in the README

- The README may keep north-star language about what HLF is meant to become.
- The README may describe the architectural direction of HLF as a governed coordination language.
- The README may point to upstream doctrine and bridge artifacts when the repo does not yet fully embody a claim.

### 2. What may not be overstated

- Claims in the README may not be silently interpreted as `implemented now` unless the corresponding proving artifact exists in packaged truth.
- Missing verifier, orchestration, and ecosystem surfaces may not be erased just because the packaged repo is smaller.
- Public diagrams may not stand in for replay, verifier, or audit proof.

### 3. Promotion rule for bridge claims

A `bridge work` claim may only become `implemented now` when all of the following exist:

1. packaged ownership boundary
2. explicit runtime or docs contract
3. targeted regression coverage
4. operator-readable proof surface
5. current-truth update in `SSOT_HLF_MCP.md`

## Immediate Follow-Ons

1. Keep `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` synchronized with the controls and proof surfaces that are actually packaged.
2. Reclassify README claim rows only when `SSOT_HLF_MCP.md`, tests, and operator-readable proof artifacts all move together.
3. Use `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` as the README-facing source-intake guardrail so external baselines do not get promoted into present-tense product language by drift.
4. Extend `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` with the unified evidence contract needed by routing and promotion logic.
5. Add the missing replay-equivalence and round-trip proof artifacts before strengthening orchestration or five-surface language claims.
6. Keep stronger recursive-build and remote transport language in bridge-only phrasing until the repo-owned smoke path proves the intended MCP initialize flow end to end.

## Working Rule

If a future change wants to strengthen or weaken a README claim, update this matrix first so the repo records which proof obligation is being added, deferred, or violated.

Then classify the resulting phrasing with `docs/HLF_CLAIM_LANES.md` before promoting it into README current-product language.
