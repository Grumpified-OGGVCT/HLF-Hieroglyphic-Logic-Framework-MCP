# HLF Implementation Index

Purpose:

- provide a compact branch-aware index of meaningful HLF implementation surfaces in this checkout
- distinguish packaged current truth from active bridge work
- point readers to the stronger authority documents for exact claims

Reading rule:

- use `SSOT_HLF_MCP.md` for executable current truth
- use `docs/HLF_CLAIM_LANES.md` when reusing wording from this file
- use `docs/HLF_REPO_IMPLEMENTATION_MAP.md` for pillar-by-pillar packaged ownership
- use `HLF_ACTIONABLE_PLAN.md` and `plan/architecture-hlf-reconstruction-2.md` for bridge sequencing

## Packaged Current-Truth Anchors

### Packaged FastMCP surface

- **Status**: Current-true
- **Files**:
  - `hlf_mcp/server.py`
  - `hlf_mcp/server_core.py`
  - `hlf_mcp/server_translation.py`
  - `hlf_mcp/server_memory.py`
  - `hlf_mcp/server_resources.py`
- **Purpose**: Main product-facing HLF MCP assembly with packaged tools, resources, and transport handling

### Deterministic language, runtime, and bytecode

- **Status**: Current-true
- **Files**:
  - `hlf_mcp/hlf/compiler.py`
  - `hlf_mcp/hlf/grammar.py`
  - `hlf_mcp/hlf/formatter.py`
  - `hlf_mcp/hlf/linter.py`
  - `hlf_mcp/hlf/runtime.py`
  - `hlf_mcp/hlf/bytecode.py`
- **Purpose**: Canonical packaged HLF compile, format, lint, execute, and bytecode path

### Governance, capsules, and trust enforcement

- **Status**: Current-true to partial
- **Files**:
  - `hlf_mcp/hlf/capsules.py`
  - `hlf_mcp/server_capsule.py`
  - `hlf_mcp/hlf/memory_node.py`
  - `hlf_mcp/hlf/execution_admission.py`
  - `governance/align_rules.json`
  - `governance/host_functions.json`
- **Purpose**: Packaged tier boundaries, pointer trust, approval-aware execution, and fail-closed governance

### Memory, witness, and weekly evidence substrate

- **Status**: Current-true to partial
- **Files**:
  - `hlf_mcp/rag/memory.py`
  - `hlf_mcp/hlf/witness_governance.py`
  - `hlf_mcp/weekly_artifacts.py`
  - `hlf_mcp/server_memory.py`
  - `hlf_mcp/server_context.py`
- **Purpose**: Governed memory storage, witness records, artifact persistence, and evidence-facing MCP access

## Active Bridge Additions In This Checkout

### Governed review normalization

- **Status**: Bridge-true and implemented in this branch
- **Files**:
  - `hlf_mcp/governed_review.py`
  - `tests/test_governed_review.py`
- **Purpose**: Normalize review outputs for spec drift, test health, ethics review, code quality, doc accuracy, and security-pattern review into one operator-legible contract

### Operator evidence and weekly artifact decisions

- **Status**: Bridge-true and implemented in this branch
- **Files**:
  - `hlf_mcp/weekly_artifacts.py`
  - `hlf_mcp/evidence_query.py`
  - `tests/test_weekly_artifacts.py`
  - `tests/test_evidence_query.py`
- **Purpose**: Persist weekly artifact decisions, load verified evidence, and expose operator-facing evidence review/reporting flows

### Governed routing and profile evidence

- **Status**: Partial packaged pillar with stronger branch proof
- **Files**:
  - `hlf_mcp/server_profiles.py`
  - `hlf_mcp/hlf/model_catalog.py`
  - `hlf_mcp/hlf/routing_trace.py`
  - `tests/test_fastmcp_frontdoor.py`
- **Purpose**: Evidence-aware route selection, capability catalogs, benchmark artifact persistence, and governed profile reporting

### Symbolic relation-edge proof slice

- **Status**: Bridge-true and implemented in this branch
- **Files**:
  - `hlf_mcp/hlf/symbolic_surfaces.py`
  - `tests/test_symbolic_surfaces.py`
- **Purpose**: Recover an ASCII-first semasiographic bridge surface for relation extraction, projection, explanation, and audit logging

### Dream-cycle and multimodal evidence bridge slice

- **Status**: Bridge-true and implemented in this branch
- **Files**:
  - `hlf_mcp/dream_cycle.py`
  - `hlf_mcp/media_evidence.py`
  - `hlf_mcp/server_context.py`
  - `hlf_mcp/server_memory.py`
  - `hlf_mcp/server_resources.py`
  - `hlf_mcp/server_profiles.py`
  - `tests/test_dream_cycle.py`
- **Purpose**: Add advisory dream findings, media evidence normalization, citation-chain proposals, and multimodal contract resources without overclaiming full target-state autonomy or multimodal completion

### VS Code operator bridge scaffold

- **Status**: Bridge-true scaffold in this branch
- **Files**:
  - `extensions/hlf-vscode/README.md`
  - `extensions/hlf-vscode/package.json`
  - `extensions/hlf-vscode/src/*`
- **Purpose**: Establish a claim-lane-aware operator shell and extension boundary over the packaged MCP surface

## Internal Readiness Surfaces

### Canonical readiness scoring model

- **Status**: Bridge-true internal planning authority
- **Files**:
  - `docs/HLF_READINESS_SCORING_MODEL.md`
- **Purpose**: Define the repo's canonical internal percent model without flattening claim-lane discipline into fake completion claims

### Pillar scorecard and internal dashboard

- **Status**: Bridge-true internal planning authority
- **Files**:
  - `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
  - `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
  - `docs/HLF_READINESS_REFRESH_PROCEDURE.md`
- **Purpose**: Convert existing pillar, proof, truth, and backlog surfaces into weighted repo, cluster, and per-pillar readiness percentages for internal use

## Correction Notes

- This file replaces an older, stale index that described unrelated or superseded implementation work.
- It should not be used to argue that every bridge surface is complete.
- It exists to stop public summaries from undercounting work already present in the active branch while preserving the repo's three-lane doctrine.

## Related Files

- `SSOT_HLF_MCP.md`
- `docs/HLF_CLAIM_LANES.md`
- `docs/HLF_REPO_IMPLEMENTATION_MAP.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- `docs/HLF_READINESS_SCORING_MODEL.md`
- `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
- `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
- `docs/HLF_READINESS_REFRESH_PROCEDURE.md`
- `HLF_ACTIONABLE_PLAN.md`
- `plan/architecture-hlf-reconstruction-2.md`
