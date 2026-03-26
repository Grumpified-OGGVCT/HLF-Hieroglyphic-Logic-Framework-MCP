# HLF Analyst Context Correction — 2026-03-26

Purpose: Correct and refine the external analyst's advantages/disadvantages assessment against verified depth-audit findings and existing planning artifacts.

## Corrections to Advantages

### Audit-Backed Reasoning — Downgrade from "every reasoning step" to "read/recall path only"

The Infinite RAG **read/recall path** is genuinely governed: purpose-based policies, freshness checks, revocation, supersession, provenance filtering. Real enforcement, real denial paths.

The **write path** has zero enforcement. `store("anything")` succeeds silently. All 13 mandatory evidence fields are backfilled with permissive defaults by `_normalize_metadata()`. No rejection gate exists anywhere in the store chain (`server_memory.py` → `rag/memory.py`).

Corrected claim: "Read/recall path enforces governed evidence retrieval. Write path is an identified enforcement gap under active remediation planning."

### Security and Transparency Boundaries — Fix timing reference

The Ethical Governor operates at **execution admission time**, not compile time. It is genuinely SOLID: 4-layer pipeline, fails closed, runtime-integrated, actually blocks. The correction is only to the phase description.

## Critical Disadvantages the Analyst Missed

The analyst identified scope/completeness gaps (product gap, extraction gap, ecosystem readiness). Those are valid. But the most operationally critical finding from depth audit is **enforcement gaps in surfaces that already exist and claim to work**:

### 1. Formal Verifier Mislabeling (severity: high)

`hlf_mcp/hlf/formal_verifier.py` (725 lines) contains a `FallbackSolver` that reports `VerificationStatus.PROVEN` based on Python `isinstance` checks and arithmetic comparisons. Z3 import exists as an optional flag but zero Z3 solver calls are ever made. This is a runtime assertion engine mislabeled as formal verification.

### 2. Memory Write-Path Zero Enforcement (severity: high)

`rag/memory.py` `store()` method accepts any content with any metadata. Every evidence parameter in the MCP tool interface (`server_memory.py` `hlf_memory_store`) is optional with permissive defaults. There is no write-time rejection gate for missing evidence, provenance, or governance fields.

### 3. Runtime Bypasses Capsule Constraints (severity: high)

`capsules.py` `validate_ast()` pre-flight genuinely blocks forbidden tags, tools, and tier escalations. But `runtime.py` `_dispatch_host()` (line 1072) dispatches host functions without consulting the capsule boundary. A forge-tier agent can call sovereign-level functions at runtime.

### 4. Host Function Tier Metadata Ignored (severity: medium)

`registry.py` `HostFunction` dataclass carries `tiers`, `safety_class`, `review_posture`, `execution_mode`, `supervisory_only` — none of which `_dispatch_host()` consults. The enforcement infrastructure exists in the registry but is disconnected from the execution path.

### Universal Pattern

Infrastructure and type signatures look complete; enforcement is frequently pre-flight only, read-side only, advisory only, or metadata-labeled but not actually gating at runtime.

## Correction to Planning Status

The analyst stated: "no indication it is currently being solved through specific planned work." This is incorrect.

### Existing planned work (all completed planning artifacts):

| Gap | Planning Artifact | Status |
|-----|-------------------|--------|
| Formal verification recovery | `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` + `plan/feature-formal-verifier-1.md` | Planned, spec complete |
| Memory governance recovery | `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` with 7 mandatory foundation requirements | Planned, spec complete |
| Routing/coordination | `docs/HLF_ROUTING_RECOVERY_SPEC.md` + `plan/feature-routing-fabric-1.md` | Planned, spec complete |
| Orchestration lifecycle | `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` + `plan/feature-orchestration-lifecycle-1.md` | Planned, spec complete |
| Batch sequencing | `docs/HLF_RECOVERY_BATCH_1.md` + `docs/HLF_RECOVERY_BATCH_2.md` | Planned, acceptance gates defined |
| Master reconstruction | `plan/architecture-hlf-reconstruction-2.md` — 55 tasks across 11 phases | All planning tasks complete |

### The one genuinely unplanned item the analyst correctly identified:

The product gap — "no single narrow user outcome that makes adoption feel obviously rational" — is real, is the most serious strategic risk, and has no specific resolution in the current planning artifacts. This is a strategic/positioning problem, not a code task.

## What to Extract and Use

From the analyst's original assessment, these elements are accurate and reusable:

- Three-lane doctrine description — correct
- Ethical Governor characterization (with timing fix) — correct
- Recursive build validation concept — correct
- Product gap identification — correct and important
- Extraction gap characterization — correct
- Ecosystem integration weakness (22.5%) — correct
- Bridge work qualification requirement — correct

## What to Omit

- The claim that reasoning is "audit-backed at every step" — overstates write-path reality
- The characterization that disadvantages are merely "scope gaps" — they are enforcement gaps
- The conclusion that no specific planning exists — extensive recovery specs and batch sequencing exist
- Any framing that treats percentage readiness scores as the primary concern — the depth-of-enforcement problem is more operationally critical than the breadth-of-coverage numbers
