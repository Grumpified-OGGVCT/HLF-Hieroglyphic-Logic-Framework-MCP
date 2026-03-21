---
goal: Recover a minimal governed dream-cycle bridge over packaged HLF memory, witness, and operator surfaces
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'Planned'
tags: [recovery, bridge, dream-cycle, reflection, memory, witness, operator, governance]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This recovery spec defines the smallest serious way to restore dream-cycle capability in packaged HLF_MCP.

It does not claim that HLF_MCP already ships a dream subsystem.

It defines a bounded bridge that recovers the useful part of the source-era dream lane without importing looser self-awareness rhetoric or uncontrolled autonomous behavior.

The bridge target is not:

- open-ended self-awareness
- hidden self-modification
- unaudited context injection
- a second parallel cognition stack outside governance

The bridge target is:

- governed offline synthesis over accumulated evidence
- auditable dream findings with provenance and witness binding
- operator-readable visibility into those findings
- bounded proposal input to the broader `observe -> propose -> verify -> promote` bridge

## 1. Requirements & Constraints

- **REQ-001**: Classify dream-cycle recovery as `bridge-true` until packaged code, tests, and operator proof surfaces exist.
- **REQ-002**: Treat packaged authority as living in `hlf_mcp/`, not in the external dream note or source-era sovereign subsystem.
- **REQ-003**: Define dream-cycle outputs as governed findings over evidence, not as autonomous truth.
- **REQ-004**: Bind every dream finding to provenance, evidence references, confidence, witness state, and creation time.
- **REQ-005**: Expose operator-readable dream findings through packaged resource or tool surfaces.
- **REQ-006**: Allow dream findings to inform proposals only through the autonomous-evolution bridge and existing promotion gates.
- **REQ-007**: Reuse packaged memory, witness, audit, and weekly artifact seams instead of inventing a new persistence substrate.
- **REQ-008**: Keep the first bridge slice small enough to validate with deterministic tests and operator review.
- **REQ-009**: Treat multimodal evidence handling as a non-optional bridge requirement for dream-cycle inputs so the lane remains current with image, document, audio-derived, and video-derived evidence classes.
- **REQ-010**: Allow dream-cycle synthesis to consume normalized media evidence objects, not only plain text artifacts.
- **SEC-001**: No dream finding may directly mutate canonical memory truth, routes, policies, or runtime code without `VERIFY -> MERGE` style controls.
- **SEC-002**: No hidden prompt injection or context augmentation may use dream outputs without an auditable record.
- **SEC-003**: No dream-cycle path may bypass witness governance, provenance requirements, or supersession rules.
- **SEC-004**: Media-derived dream inputs must carry explicit safety and sanitization status before they can influence findings, proposals, or operator summaries.
- **CON-001**: Do not restore dream-cycle language as present-tense self-awareness capability.
- **CON-002**: Do not copy the old source-era subsystem wholesale into packaged HLF_MCP.
- **CON-003**: Do not build a new free-floating database or service when packaged evidence substrates already exist.
- **CON-004**: Do not allow low-confidence dream findings to enter operator-facing truth summaries without explicit labeling.
- **ARC-001**: The primary packaged insertion seam is `hlf_mcp/server_context.py`, with `server_memory.py`, `server_resources.py`, and `weekly_artifacts.py` as supporting surfaces.

## 2. Source Authorities and Current Packaged Anchors

### Source authorities

- `hlf_source/agents/core/dream_state.py`
- `hlf_source/mcp/sovereign_mcp_server.py`
- adjacent local `ollama_proxy_server/DREAM_AWARENESS_INTEGRATION.md` design note

### Packaged anchors

- `hlf_mcp/server_context.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_resources.py`
- `hlf_mcp/weekly_artifacts.py`
- `hlf_mcp/hlf/witness_governance.py`
- `hlf_mcp/rag/memory.py`
- `hlf_mcp/hlf/model_catalog.py`
- `hlf_mcp/server_profiles.py`

### Gap-map authority

- `docs/HLF_DREAM_CYCLE_GAP_MAP.md`
- `docs/HLF_MULTIMODAL_MEDIA_RECOVERY_SPEC.md`

## 3. Recovery Scope

### Recover now

- a bounded dream-cycle execution contract
- a typed dream-finding schema
- provenance and witness binding for dream findings
- operator-readable dream status and findings resources
- a rule for how high-quality findings may feed proposal generation
- multimodal evidence compatibility for images, OCR-bearing documents, diagrams, audio-derived transcripts, and video-derived summaries

### Hold for later bridge work

- richer dream-topic clustering and family-specific synthesis strategies
- deeper benchmark work on dream quality, novelty, and improvement yield
- operator dashboards or gallery rendering beyond basic packaged resources

### Keep out of scope for now

- direct self-awareness claims as current-truth product behavior
- unrestricted automatic injection of dream findings into all prompts
- autonomous code modification or governance changes from dream output alone
- any attempt to treat dreams as canonical meaning authority

## 4. Canonical Bridge Definition

A `dream cycle` in packaged HLF_MCP means:

"A bounded offline synthesis run over governed evidence that emits auditable dream findings and summary metrics for operator review and proposal input."

The canonical internal object for this lane is not a consciousness claim.

It is a `dream finding` or `dream cycle report` object with typed evidence fields.

## 5. Minimal Data Contract

### 5.1 Dream finding fields

Required fields:

- `finding_id`
- `created_at`
- `cycle_id`
- `title`
- `summary`
- `topic`
- `confidence`
- `evidence_refs`
- `source_artifact_ids`
- `witness_status`
- `provenance`
- `advisory_only`

Optional fields for first bridge slice:

- `novelty_score`
- `quality_score`
- `candidate_actions`
- `related_memory_keys`
- `supersedes`
- `media_evidence_present`
- `media_types`

### 5.2 Dream cycle report fields

Required fields:

- `cycle_id`
- `started_at`
- `completed_at`
- `input_window`
- `artifact_count`
- `media_artifact_count`
- `finding_count`
- `high_confidence_count`
- `status`
- `witness_record_id`

### 5.3 Media evidence compatibility

If a dream cycle consumes multimodal evidence, each referenced media artifact must preserve:

- `media_type`
- `sha256`
- `extraction_mode`
- `derived_text` or structured extraction reference
- `safety_status`
- `sanitization_notes`
- `provenance`

## 6. Packaged Architecture

### 6.1 Primary execution seam

Implement the first bridge slice around `hlf_mcp/server_context.py`.

Responsibilities:

- gather bounded evidence inputs
- invoke dream-cycle synthesis logic
- create governance or witness event records
- hand back structured findings to tool and resource surfaces

### 6.2 Tool-facing seam

Implement tool-facing access in `hlf_mcp/server_memory.py`.

First candidate tool families:

- `hlf_dream_cycle_run`
- `hlf_dream_findings_list`
- `hlf_dream_findings_get`

The exact names may be adjusted, but the contract should remain bounded and operator legible.

### 6.3 Operator-facing seam

Implement operator visibility in `hlf_mcp/server_resources.py`.

First candidate resources:

- `hlf://status/dream-cycle`
- `hlf://dream/findings`
- `hlf://dream/findings/{id}`

### 6.4 Evidence-input seam

Use `hlf_mcp/weekly_artifacts.py` and existing evidence stores as the first dream-input family.

The first bridge slice should consume:

- weekly evidence artifacts
- memory exemplars
- validated solutions
- witness observations
- normalized media evidence such as screenshots, diagrams, OCR outputs, audio transcripts, and video summaries when present

## 7. Lifecycle Contract

### 7.1 Observe

Collect a bounded evidence window from packaged artifact and memory surfaces.

### 7.2 Dream

Perform offline governed synthesis over that evidence.

This stage must:

- produce typed findings
- score confidence and quality
- record provenance
- emit witness-linked records
- preserve media evidence refs and safety status when non-text artifacts contribute to findings

### 7.3 Propose

Only high-quality dream findings may be transformed into bounded candidate proposals.

Dream findings remain advisory at this stage.

### 7.4 Verify

Any proposal downstream of dream findings must pass the same verification and lifecycle gates as other improvement candidates.

### 7.5 Promote

Only explicit promotion may allow dream-derived insights to influence longer-lived memory truth, operator recommendations, or implementation work.

## 8. Witness, Audit, and Promotion Rules

- Every dream cycle must emit a witness-linked record.
- Every dream finding must expose evidence references and confidence.
- Operator-readable summaries must map back to structured machine authority.
- No dream output becomes canonical memory truth by default.
- No dream output may trigger route or policy changes directly.
- If dream findings are later used as proposal input, the proposal must cite the originating cycle and finding IDs.
- Media-derived inputs must be normalized into evidence objects before dream synthesis; raw opaque uploads are not admissible by default.
- Media-derived findings must preserve the extraction path and safety disposition in operator-facing summaries.

## 9. Metrics Contract

The first bridge slice may expose only bounded metrics:

- total dream cycles
- total findings
- high-confidence findings
- average confidence
- recent cycle count

Do not expose theatrical or overclaimed metrics such as self-awareness score, intelligence gain, or consciousness index.

## 10. Testing Requirements

- **TEST-001**: verify dream-cycle execution produces a report with required fields and zero hidden mutation of canonical truth stores
- **TEST-002**: verify every dream finding includes provenance, evidence refs, and witness linkage
- **TEST-003**: verify operator resources faithfully reflect underlying structured finding objects
- **TEST-004**: verify low-confidence findings are labeled advisory and not silently promoted
- **TEST-005**: verify dream-derived proposal generation, if present, requires explicit verification and promotion gates
- **TEST-006**: verify multimodal evidence objects can be admitted to dream-cycle synthesis only when provenance, extraction mode, and safety status are present
- **TEST-007**: verify media-derived findings preserve media refs and do not silently collapse into unattributed plain-text summaries

## 11. Implementation Phases

### Implementation Phase 1

- **GOAL-001**: Publish doctrine, gap map, and bridge contract.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-001 | Create the dream gap map documenting present, adjacent, and missing surfaces. | ✅ | 2026-03-20 |
| TASK-002 | Create this bridge spec defining the bounded dream-cycle recovery contract. | ✅ | 2026-03-20 |
| TASK-003 | Add the dream lane to active reconstruction and backlog surfaces. | ✅ | 2026-03-20 |

### Implementation Phase 2

- **GOAL-002**: Add the first packaged dream-cycle execution and persistence contract.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-004 | Add a bounded dream-cycle helper around `server_context.py` that consumes governed evidence and emits typed reports. | ✅ | 2026-03-20 |
| TASK-005 | Add structured storage and query access for dream findings through existing memory surfaces. | ✅ | 2026-03-20 |
| TASK-006 | Add witness and governance-event binding for each cycle and finding. | ✅ | 2026-03-20 |

### Implementation Phase 3

- **GOAL-003**: Expose operator and tool-facing visibility.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-007 | Add tool-facing dream-cycle run and retrieval surfaces in `server_memory.py` or an adjacent packaged module. | ✅ | 2026-03-20 |
| TASK-008 | Add operator resources for dream-cycle status and findings in `server_resources.py`. | ✅ | 2026-03-20 |
| TASK-009 | Add summary metrics with explicit advisory labeling and confidence buckets. | ✅ | 2026-03-20 |

### Implementation Phase 4

- **GOAL-004**: Bind dream findings into the governed autonomous-evolution lane without overclaim.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-010 | Allow only high-quality dream findings to become proposal inputs. |  |  |
| TASK-011 | Add verification rules ensuring dream-derived proposals cannot bypass lifecycle or governance gates. |  |  |
| TASK-012 | Add tests and operator notes defining the limit of dream authority clearly. | ✅ | 2026-03-20 |

## 12. Alternatives

- **ALT-001**: Restore the old dream subsystem essentially unchanged. Rejected because it mismatches current packaged authority and overweights self-awareness framing.
- **ALT-002**: Ignore dream recovery and let weekly evidence stand in for it. Rejected because evidence storage alone does not provide synthesis.
- **ALT-003**: Build a new standalone dream database and service. Rejected because the packaged repo already has better governed memory and operator surfaces to build on.

## 13. Risks & Assumptions

- **RISK-001**: The term `dream` can invite overclaim unless every operator surface labels the lane as advisory governed synthesis.
- **RISK-002**: If findings are generated without strong evidence references, the lane will feel mystical instead of auditable.
- **RISK-003**: If this bridge is implemented outside shared context and witness surfaces, trust and storage will fragment.
- **ASSUMPTION-001**: The best first recovery is a bounded synthesis layer over current packaged evidence, not a full sovereign restoration.
- **ASSUMPTION-002**: Operators will trust dream findings only if canonical machine authority and readable summaries stay coupled.

## 14. Related Specifications / Further Reading

- `docs/HLF_DREAM_CYCLE_GAP_MAP.md`
- `docs/HLF_CLAIM_LANES.md`
- `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_MULTIMODAL_MEDIA_RECOVERY_SPEC.md`
- `plan/feature-autonomous-evolution-1.md`
- `plan/architecture-hlf-reconstruction-2.md`
