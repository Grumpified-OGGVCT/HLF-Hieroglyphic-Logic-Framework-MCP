---
goal: Recover multimodal and media handling as a governed HLF bridge capability instead of leaving it as source-only ambition
version: 1.1
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'Planned'
tags: [recovery, bridge, multimodal, media, vision, ocr, audio, video, governance]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This recovery spec defines how HLF_MCP should recover modern multimodal capability without collapsing into ungoverned media upload handling or vague provider-dependent promises.

The immediate target is not "support all media magically."

The immediate target is a governed media-evidence lane that lets packaged HLF:

- accept bounded multimodal inputs
- normalize them into evidence-bearing artifacts
- route them through explicit host-function and model contracts
- expose operator-readable outputs and provenance
- make those artifacts usable by dream-cycle, memory, routing, and future proposal lanes

This is a bridge document.

It is not a claim that packaged HLF_MCP already ships full image, OCR, audio, or video tooling.

## 1. Requirements & Constraints

- **REQ-001**: Treat multimodal and media evidence handling as a non-optional maintained bridge capability class.
- **REQ-002**: Support bounded evidence ingestion for at least these classes: image, OCR-bearing document image, structured document render, audio-derived transcript, and video-derived summary.
- **REQ-003**: Normalize media artifacts into typed evidence objects with provenance, digests, timestamps, extraction mode, and safety status.
- **REQ-004**: Keep media handling governed through packaged host-function, model-routing, memory, and operator surfaces.
- **REQ-005**: Make media-derived outputs usable by dream-cycle synthesis, operator trust surfaces, and future autonomous-evolution proposal lanes.
- **REQ-006**: Distinguish raw media ingestion from derived text, extracted structure, and summarized meaning.
- **REQ-007**: Expose only lane-qualified current truth in product statements; do not overstate source-era provider capability as packaged truth.
- **REQ-008**: Add deterministic tests for media schema validation, safety gating, and provenance-preserving recall.
- **SEC-001**: Treat prompt injection via image content, EXIF metadata, embedded documents, and transcript hallucination as first-class risks.
- **SEC-002**: Require explicit safety status, sanitization outcome, and provenance fields before media artifacts can influence routing, memory promotion, or proposal generation.
- **SEC-003**: Do not allow opaque binary payloads to become canonical truth without normalization and operator-legible summaries.
- **CON-001**: Do not treat source-era provider docs or host functions as proof that packaged HLF_MCP already ships multimodal support.
- **CON-002**: Do not hardwire the recovery path to a single provider when the real requirement is governed capability class support.
- **CON-003**: Do not reduce multimodal handling to "just OCR"; image, document, audio, and video lanes carry different governance requirements.
- **ARC-001**: Recover multimodal support through the same core packaged surfaces already used for memory, routing, and operator trust: host-function contracts, `server_context.py`, `server_memory.py`, `server_resources.py`, and profile qualification.

## 2. Source Authorities and Current Packaged Anchors

### Source authorities

- `hlf_source/docs/handoff_zai_api_integration.md`
- `hlf_source/agents/gateway/router.py`
- `hlf_source/config/settings.json`
- `hlf_source/governance/host_functions.json`
- `docs/AGENTS_CATALOG.md`

### Current packaged anchors

- `hlf_mcp/hlf/model_catalog.py`
- `hlf_mcp/server_profiles.py`
- `hlf_mcp/server_context.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_resources.py`
- `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`
- `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`

## 3. Current State Diagnosis

### Present now

- packaged model metadata recognizes a `multimodal` family or lane
- packaged operator and memory surfaces can eventually host media-derived evidence
- source-era doctrine and host-function archaeology clearly establish that multimodal work is part of the larger HLF target

### Missing now

- packaged host-function contracts for vision, OCR, audio, and video analysis
- packaged media evidence schemas
- qualification profiles for the `multimodal` lane
- packaged safety and sanitization controls for media artifacts
- deterministic packaged tests for multimodal ingestion and trust handling

## 4. Recovery Scope

### Recover now

- media evidence schema definitions
- host-function contract requirements for vision, OCR, audio-transcript, and video-summary lanes
- safety-control requirements for media artifacts
- operator-readable media evidence summaries
- dream-cycle compatibility requirements for multimodal evidence

### Hold for later bridge work

- image generation and video generation as governed output surfaces
- deeper UI or gallery rendering for media-rich explainer flows
- richer multimodal route optimization and benchmark programs

### Keep out of scope for now

- unconstrained arbitrary file upload handling without schema and safety contracts
- claiming end-to-end packaged media parity across all providers
- treating media understanding as a hidden model-side behavior with no explicit HLF contract

## 5. Canonical Media Evidence Contract

Every media-derived evidence object should be able to carry:

- `artifact_id`
- `media_type`
- `source_class`
- `source_path` or URI
- `sha256`
- `captured_at`
- `collector`
- `extraction_mode`
- `derived_text` or structured extraction pointer
- `summary`
- `confidence`
- `safety_status`
- `sanitization_notes`
- `provenance`
- `witness_status`
- `operator_summary`

Recommended initial `media_type` values:

- `image`
- `document_image`
- `diagram_image`
- `audio_transcript`
- `video_summary`

## 6. Host-Function Recovery Contract

The packaged host-function layer should recover bounded contracts for:

- `VISION_ANALYZE`
- `OCR_EXTRACT`
- `AUDIO_TRANSCRIBE`
- `VIDEO_SUMMARIZE`

These names are placeholders for contract classes, not final registry strings.

Required contract fields:

- input schema
- output schema
- accepted media types
- sensitivity flag
- effect class
- timeout policy
- provenance requirement
- operator-summary requirement

## 7. Routing and Qualification Contract

The `multimodal` lane must stop being an effectively empty qualification family.

Required recovery work:

- define qualification profiles for `multimodal`
- define minimum acceptable capabilities for vision, OCR, audio transcript, and video summary lanes
- route image, OCR, diagram, audio, and video workloads through explicit evidence-backed profiles rather than heuristic drift alone

## 8. Safety and Governance Controls

Required media safety controls:

- EXIF and embedded-metadata sanitization policy
- prompt-injection screening for images and documents
- hallucination labeling for audio transcripts and video summaries
- oversized or unsupported media denial behavior
- provenance-required denial for untracked binary artifacts
- operator-visible explanation when media evidence is admitted, denied, or downgraded

## 9. Dream-Cycle and Memory Integration

Multimodal support is not separate from the dream bridge.

It must be usable there.

Required bridge rule:

- dream-cycle synthesis must be able to consume normalized media-derived evidence objects, not only plain text artifacts

Examples:

- screenshots of dashboards
- architecture diagrams
- OCR output from scanned docs
- transcript artifacts from audio
- summaries derived from short videos

## 10. Operator Surface Contract

Operator surfaces should show:

- what media type was processed
- which host function or model lane handled it
- what extraction or summary was produced
- what safety status was recorded
- what confidence and provenance were attached

This work should land in packaged operator resources before any richer gallery surface is claimed.

## 10.1 Bridge Boot-Asset Contract

A short splash video or sound-only loop may be admitted as a governed media bridge asset when it is explicitly treated as operator-state media rather than as ornamental branding.

### Example bridge asset

- `Genesis Wave`: a short bass-swell startup cue that represents bounded system wake, stabilization, and operator entry into a governed surface

### Required bridge fields

- **Asset purpose**: provide an operator-readable boot cue for system initialization or stabilization
- **Playback trigger**: fire only on explicit surface transitions such as future splash launch, operator-shell entry, or governed session bootstrap
- **State meaning**: represent a declared boot-state contract such as `initializing`, `stabilizing`, or `readying operator surface`; it must not imply hidden autonomous authority
- **Accessibility fallback**: required silent mode, motion-disabled mode, and text-equivalent status message
- **Future taxonomy location**: packaged GUI/operator-surface media lane, not canonical runtime semantics and not fixture-gallery truth content

### Governance constraints

- the asset must be traceable as an operator media artifact with provenance and intent metadata
- use of the asset must remain optional and suppressible
- sound-only deployment is acceptable as an interim bridge state before video-capable operator surfaces exist
- no claim should imply that possession of the asset means packaged multimodal boot handling is already shipped

## 11. Testing Requirements

- **TEST-001**: validate the media evidence schema for image, OCR, audio-transcript, and video-summary artifacts
- **TEST-002**: verify media artifacts without provenance or safety status cannot influence dream-cycle, routing, or proposal lanes
- **TEST-003**: verify operator summaries remain grounded in structured media evidence objects
- **TEST-004**: verify media-specific denial paths for unsupported types, oversized inputs, or failed sanitization
- **TEST-005**: verify dream-cycle synthesis can consume normalized media-derived evidence references without bypassing audit and witness rules

## 12. Implementation Phases

### Implementation Phase 1

- **GOAL-001**: Lock multimodal capability into the bridge doctrine and planning stack.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-001 | Create this multimodal/media recovery spec. | ✅ | 2026-03-20 |
| TASK-002 | Add explicit multimodal evidence requirements to the dream-cycle bridge spec. | ✅ | 2026-03-20 |
| TASK-003 | Add backlog entries for media host functions, schemas, safety controls, and tests. | ✅ | 2026-03-20 |

### Implementation Phase 2

- **GOAL-002**: Define the packaged contract surfaces.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-004 | Define the canonical media evidence schema and how it joins the shared evidence substrate. | Pending | TBD |
| TASK-005 | Define the initial packaged host-function contract set for vision, OCR, audio transcript, and video summary lanes. | Pending | TBD |
| TASK-006 | Define the `multimodal` qualification profiles and route evidence expectations. | Pending | TBD |

### Implementation Phase 3

- **GOAL-003**: Recover safety and operator trust surfaces.

| Task | Description | Completed | Date |
| --- | --- | --- | --- |
| TASK-007 | Add media safety-control requirements to governance and operator surfaces. | Pending | TBD |
| TASK-008 | Add operator-facing resources for media evidence status and summaries. | Pending | TBD |
| TASK-009 | Add deterministic tests for media schema, safety denial, and provenance-preserving recall. | Pending | TBD |

## 13. Alternatives

- **ALT-001**: Leave multimodal handling as source-only or provider-specific handoff material. Rejected because it leaves a modern capability class outside packaged governance.
- **ALT-002**: Treat multimodal support as just OCR. Rejected because audio, video, and general image or diagram evidence create different trust and routing obligations.
- **ALT-003**: Let model metadata alone stand in for actual multimodal capability. Rejected because metadata without contracts, controls, and tests is not sufficient.

## 14. Risks & Assumptions

- **RISK-001**: If multimodal remains implicit, future bridge work will overclaim capability while under-specifying governance.
- **RISK-002**: If media artifacts are allowed into memory or dream lanes without explicit sanitization and provenance, trust will degrade fast.
- **RISK-003**: If host-function contracts are provider-shaped instead of capability-shaped, future portability will suffer.
- **ASSUMPTION-001**: The repo needs governed multimodal evidence handling to stay current with contemporary model capabilities.
- **ASSUMPTION-002**: The correct first step is contract and evidence normalization, not immediate provider-specific code restoration.

## 15. Related Specifications / Further Reading

- `docs/HLF_DREAM_CYCLE_BRIDGE_SPEC.md`
- `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md`
- `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md`
- `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md`
- `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`
- `plan/feature-autonomous-evolution-1.md`
- `plan/architecture-hlf-reconstruction-2.md`
