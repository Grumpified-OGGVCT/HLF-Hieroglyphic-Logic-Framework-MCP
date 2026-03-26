# HLF Knowledge Ingestion Manifest

> **Generated**: 2026-03-26
> **Purpose**: Curated list of repo documents approved for governed knowledge substrate ingestion.
> **Principle**: Only current, accurate, non-redundant content gets ingested. Shit in = shit out.
> **Authority**: This file is the gatekeeper. If a doc isn't listed here as INGEST, it doesn't go in.

---

## Classification Key

| Tag | Meaning |
|-----|---------|
| **INGEST** | Current, accurate, unique — approved for knowledge substrate |
| **SKIP-STALE** | Outdated or superseded by newer content |
| **SKIP-DUPLICATE** | Substantially redundant with another approved doc |
| **SKIP-SCAFFOLD** | Planning/tracking artifact, not knowledge content |
| **SKIP-GENERATED** | Auto-generated, can be regenerated on demand |

---

## Ingestion Authority Levels

Documents are tagged with their authority level for ingestion metadata:

| Level | Meaning |
|-------|---------|
| `canonical` | Doctrine, SSOT, governance specs — highest trust |
| `advisory` | Bridge specs, recovery plans, research — directional but not yet shipped |
| `external` | External comparisons, technique audits — reference context |
| `draft` | Incomplete or in-progress — lowest trust |

---

## Domain Assignments

Each document gets a primary domain for retrieval:

| Domain | Scope |
|--------|-------|
| `hlf-specific` | HLF language, grammar, compiler, runtime, bytecode, governance |
| `general-coding` | Build guides, CLI tools, project setup |
| `ai-engineering` | Model qualification, embeddings, knowledge substrate, dream cycles |
| `security` | PII policy, ethical governor, align rules |
| `devops` | Deployment, Docker, infrastructure |
| `frontend` | VS Code extension, GUI guides |

---

## Scope Boundary

**Main repo** (ingestion targets): `hlf_mcp/`, `docs/`, `governance/`, `fixtures/`, `plan/`, `tests/`, `scripts/`, `extensions/hlf-vscode/`, `.github/`, `observability/`, `syntaxes/`, `examples/`, root config and doctrine files.

**Supportive reference only** (skim for archaeology, do NOT ingest as primary):
- `hlf_source/` — upstream Sovereign Agentic OS submodule
- `donor/AgentKB_MCP/` — HKS research donor project
- `hlf/` — legacy compatibility line
- `ollama_folder_qa/` — separate QA tool
- `.lollms/` — external tool cache

---

## APPROVED FOR INGESTION — Phase 1 (147 files)

### Tier 1: Canonical Doctrine (authority=canonical, domain=hlf-specific)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `AGENTS.md` | hlf-specific | canonical | Workspace handover, foundational doctrine |
| `HLF_VISION_DOCTRINE.md` | hlf-specific | canonical | Core vision framework, three-lane doctrine |
| `SSOT_HLF_MCP.md` | hlf-specific | canonical | Single source of truth, authoritative current state |
| `docs/HLF_DESIGN_NORTH_STAR.md` | hlf-specific | canonical | North-star target architecture |
| `docs/HLF_CLAIM_LANES.md` | hlf-specific | canonical | Claim classification framework |
| `docs/HLF_STITCHED_SYSTEM_VIEW.md` | hlf-specific | canonical | Four-layer system overview |
| `docs/HLF_VISION_MAP.md` | hlf-specific | canonical | Vision-to-implementation mapping |
| `docs/HLF_VISION_PLAIN_LANGUAGE.md` | hlf-specific | canonical | Vision in accessible language |
| `docs/HLF_PILLAR_MAP.md` | hlf-specific | canonical | Disposition matrix, pillar priority |

### Tier 2: Current-Truth Reference (authority=canonical, domain varies)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `BUILD_GUIDE.md` | general-coding | canonical | Verified build instructions |
| `QUICKSTART.md` | general-coding | canonical | Practical quick-start guide |
| `README.md` | hlf-specific | canonical | Public product statement |
| `CHANGELOG.md` | hlf-specific | canonical | Release milestones and history |
| `HLF_QUALITY_TARGETS.md` | hlf-specific | canonical | Measurable success criteria |
| `HLF_IMPLEMENTATION_INDEX.md` | hlf-specific | canonical | Packaged surface inventory |
| `HLF_REPO_GROUND_TRUTH.md` | hlf-specific | canonical | Checkout verification, test baseline |
| `HLF_ANALYST_CORRECTION_2026-03-26.md` | hlf-specific | canonical | Latest accuracy correction |
| `docs/HLF_STATUS_OVERVIEW.md` | hlf-specific | canonical | Readiness snapshot |
| `docs/HLF_MCP_POSITIONING.md` | hlf-specific | canonical | MCP role clarification |

### Tier 3: Technical Reference (authority=canonical, domain=hlf-specific)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `docs/HLF_GRAMMAR_REFERENCE.md` | hlf-specific | canonical | Parser authority |
| `docs/HLF_REFERENCE.md` | hlf-specific | canonical | Language reference |
| `docs/HLF_TAG_REFERENCE.md` | hlf-specific | canonical | Tag catalog |
| `docs/HLF_HOST_FUNCTIONS_REFERENCE.md` | hlf-specific | canonical | Host function registry |
| `docs/HLF_STDLIB_REFERENCE.md` | hlf-specific | canonical | Stdlib packaging |
| `docs/HLF_AUDIT_SYSTEM.md` | hlf-specific | canonical | Audit discipline framework |
| `docs/INSTINCT_REFERENCE.md` | hlf-specific | canonical | Lifecycle reference |
| `docs/cli-tools.md` | general-coding | canonical | CLI entry points |
| `docs/stdlib.md` | hlf-specific | canonical | Stdlib module guide |

### Tier 4: Governance Assets (authority=canonical, domain=security)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `governance/align_rules.json` | security | canonical | ALIGN gate policy |
| `governance/bytecode_spec.yaml` | hlf-specific | canonical | Bytecode v0.4.0 spec |
| `governance/host_functions.json` | hlf-specific | canonical | Function registry v1.6.0 |
| `governance/tag_i18n.yaml` | hlf-specific | canonical | Tag i18n support |
| `governance/model_qualification_profiles.json` | ai-engineering | canonical | Model qualification data |
| `governance/module_import_rules.yaml` | hlf-specific | canonical | Import compliance rules |
| `governance/pii_policy.json` | security | canonical | PII handling policy |
| `HLF_ETHICAL_GOVERNOR.md` | security | canonical | Governance philosophy |
| `HLF_ETHICAL_GOVERNOR_ARCHITECTURE.md` | security | canonical | 4-layer governance design |
| `docs/ETHICAL_GOVERNOR_HANDOFF.md` | security | canonical | Governance handoff procedures |
| `docs/HLF_GOVERNANCE_CONTROL_MATRIX.md` | security | canonical | Control mapping |

### Tier 5: Agent & Operator (authority=canonical)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `docs/HLF_AGENT_ONBOARDING.md` | hlf-specific | canonical | Agent onboarding guide |
| `docs/HLF_AGENT_OPERATING_PROTOCOL.md` | hlf-specific | canonical | Agent behavior rules |
| `docs/HLF_AGENT_FLOW.md` | hlf-specific | canonical | Agent workflow |
| `docs/HLF_MCP_AGENT_HANDOFF.md` | hlf-specific | canonical | MCP integration handoff |
| `docs/HLF_INTERNAL_PERSONA_OPERATING_MODEL.md` | hlf-specific | canonical | Persona operating model |
| `docs/HLF_OPERATOR_BUILD_NOTES_2026-03-19.md` | hlf-specific | canonical | Operator guide |
| `docs/HLF_OPERATOR_BOOT_ASSET_MANIFEST.md` | hlf-specific | canonical | Boot asset checklist |
| `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json` | hlf-specific | canonical | Persona/role mappings |
| `docs/AGENTS_CATALOG.md` | hlf-specific | canonical | 154-artifact system inventory: 26 hats, personas, agents, modules, daemons, host functions, architecture diagram. Auto-generated by `catalog_agents.py` but content is unique and not available elsewhere in single-doc form |

### Tier 6: Bridge Specs & Recovery (authority=advisory, domain=hlf-specific)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `HLF_ACTIONABLE_PLAN.md` | hlf-specific | advisory | Master reconstruction plan |
| `HLF_CANONICALIZATION_MATRIX.md` | hlf-specific | advisory | Extraction inventory |
| `HLF_MCP_TODO.md` | hlf-specific | advisory | Active reconstruction backlog |
| `HLF_SOURCE_EXTRACTION_LEDGER.md` | hlf-specific | advisory | Extraction status tracking |
| `HLF_SUPPORTIVE_SOURCE_CONTEXT_MAP.md` | hlf-specific | advisory | Recovery cluster mapping |
| `docs/HLF_MISSING_PILLARS.md` | hlf-specific | advisory | Gap classifications |
| `docs/HLF_RECOVERY_BATCH_1.md` | hlf-specific | advisory | First recovery batch |
| `docs/HLF_RECOVERY_BATCH_2.md` | hlf-specific | advisory | Second recovery batch |
| `docs/HLF_RECOVERY_ACCEPTANCE_GATES.md` | hlf-specific | advisory | Recovery gate definitions |
| `docs/HLF_FORMAL_VERIFICATION_RECOVERY_SPEC.md` | hlf-specific | advisory | Z3 recovery spec |
| `docs/HLF_MEMORY_GOVERNANCE_RECOVERY_SPEC.md` | hlf-specific | advisory | Memory contract normalization |
| `docs/HLF_ORCHESTRATION_RECOVERY_SPEC.md` | hlf-specific | advisory | Orchestration bridge |
| `docs/HLF_PERSONA_AND_OPERATOR_RECOVERY_SPEC.md` | hlf-specific | advisory | Persona recovery |
| `docs/HLF_ROUTING_RECOVERY_SPEC.md` | hlf-specific | advisory | Routing fabric recovery |
| `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md` | hlf-specific | advisory | Symbolic bridge |
| `docs/HLF_MULTIMODAL_MEDIA_RECOVERY_SPEC.md` | hlf-specific | advisory | Multimodal recovery |
| `docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md` | hlf-specific | advisory | Operator surface recovery |
| `docs/HLF_LANGUAGE_EVOLUTION_AND_BYTECODE_TRUST_SPEC.md` | hlf-specific | advisory | Language evolution |
| `docs/HLF_LANGUAGE_PROMOTION_BENCHMARK_SPEC.md` | hlf-specific | advisory | Promotion framework |
| `docs/HLF_MODEL_QUALIFICATION_AND_PROMOTION_SPEC.md` | ai-engineering | advisory | Model qualification gates |
| `docs/HLF_DREAM_CYCLE_BRIDGE_SPEC.md` | ai-engineering | advisory | Dream cycle recovery |
| `docs/HLF_DREAM_CYCLE_GAP_MAP.md` | ai-engineering | advisory | Dream cycle gaps |
| `docs/HLF_MESSAGING_LADDER.md` | hlf-specific | advisory | Audience-specific messaging |

### Tier 7: Readiness & Merge (authority=advisory)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `docs/HLF_READINESS_SCORING_MODEL.md` | hlf-specific | advisory | Scoring methodology |
| `docs/HLF_READINESS_REFRESH_PROCEDURE.md` | hlf-specific | advisory | Refresh procedures |
| `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md` | hlf-specific | advisory | Readiness snapshot |
| `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md` | hlf-specific | advisory | Internal status |
| `docs/HLF_MERGE_READINESS_SUMMARY_2026-03-20.md` | hlf-specific | advisory | Merge readiness |
| `docs/HLF_REVIEWER_HANDOFF_2026-03-20.md` | hlf-specific | advisory | Review protocol |
| `docs/HLF_BRANCH_AWARE_CLAIMS_LEDGER_2026-03-20.md` | hlf-specific | advisory | Branch-aware claims |
| `docs/HLF_BRANCH_BOUNDED_MAINTAINER_PROTOCOL.md` | hlf-specific | advisory | Maintainer discipline |
| `docs/HLF_TRANSCRIPT_MECHANISM_MAP_2026-03-18.md` | hlf-specific | advisory | Transcript mechanisms |
| `docs/HLF_TRANSCRIPT_TARGET_STATE_BRIDGE_2026-03-18.md` | hlf-specific | advisory | Transcript evolution |
| `RECOVERED_HLF_VISION_AND_MERGE_BRIEF_2026-03-15.md` | hlf-specific | advisory | Vision recovery memo |
| `RECOVERED_MCP_COMPARISON_2026-03-15.md` | hlf-specific | advisory | MCP positioning analysis |

### Tier 8: Research & Assessment (authority=advisory/external)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` | hlf-specific | advisory | Doctrine validation |
| `docs/HLF_ASSEMBLY_REFIT_MATRIX.md` | hlf-specific | advisory | Assembly refitting |
| `docs/HLF_REPO_IMPLEMENTATION_MAP.md` | hlf-specific | advisory | Repo packaging map |
| `docs/HLF_README_OPERATIONALIZATION_MATRIX.md` | hlf-specific | advisory | Claim-to-implementation mapping |
| `docs/HLF_HKS_EXTRACTION_STATUS_MATRIX.md` | ai-engineering | advisory | HKS extraction tracking |
| `docs/HLF_HKS_SOURCE_GAP_PASS_2026-03-23.md` | ai-engineering | advisory | HKS gap analysis |
| `docs/HLF_KNOWLEDGE_SUBSTRATE_RESEARCH_HANDOFF.md` | ai-engineering | advisory | Knowledge substrate research |
| `docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md` | ai-engineering | external | External technique baselines |
| `docs/HLF_CHINESE_COGNITIVE_LANE_LAUNCH_CRITERIA.md` | hlf-specific | advisory | Chinese language support |
| `docs/HLF_MOMA_MULTISCRIPT_FIT_ASSESSMENT.md` | hlf-specific | advisory | Multiscript assessment |
| `docs/HLF_ROBOTICS_EMBODIED_FIT_ASSESSMENT.md` | hlf-specific | advisory | Robotics fit analysis |
| `docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RESEARCH_2026-03-20.md` | hlf-specific | advisory | Symbolic research |
| `docs/HLF_EMBEDDING_AGENT_DECISION_MATRIX.md` | ai-engineering | advisory | Embedding agent decisions |
| `docs/HLF_ZHOTHEPHUN_DEFAULTING_RECOMMENDATION.md` | ai-engineering | advisory | Model selection guidance |
| `docs/HLF_RECURSIVE_BUILD_STORY.md` | hlf-specific | advisory | Build narrative |
| `docs/HLF_LOCAL_CORPORA_EXTRACTION.md` | ai-engineering | advisory | Local extraction methodology |
| `docs/HLF_REJECTED_EXTRACTION_AUDIT.md` | hlf-specific | advisory | Extraction audit trail |

### Tier 9: Architecture & Feature Plans (authority=advisory, domain=hlf-specific)

All 24 files in `plan/`. These are the concrete bridge-lane build plans — architecture sequences and feature specifications that define how current truth converges toward the full HLF target.

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `plan/architecture-hlf-governed-build-1.md` | hlf-specific | advisory | Governed execution stack assembly |
| `plan/architecture-hlf-reconstruction-1.md` | hlf-specific | advisory | Pillar reconstruction plan v1 |
| `plan/architecture-hlf-reconstruction-2.md` | hlf-specific | advisory | Pillar reconstruction plan v2 |
| `plan/architecture-hlf-language-knowledge-convergence-1.md` | hlf-specific | advisory | Language-knowledge substrate |
| `plan/architecture-ecosystem-compatibility-1.md` | hlf-specific | advisory | Ecosystem integration |
| `plan/architecture-hks-local-evaluation-bounded-comparator-1.md` | ai-engineering | advisory | HKS bounded eval design |
| `plan/architecture-hks-platform-expansion-1.md` | ai-engineering | advisory | HKS platform scaling |
| `plan/architecture-model-intelligence-sync-1.md` | ai-engineering | advisory | Model intelligence sync |
| `plan/architecture-visual-operator-workbench-1.md` | frontend | advisory | Operator workbench design |
| `plan/architecture-vscode-extension-bridge-1.md` | frontend | advisory | VS Code extension bridge |
| `plan/feature-agent-first-impression-surface-1.md` | hlf-specific | advisory | Agent onboarding UX |
| `plan/feature-autonomous-evolution-1.md` | hlf-specific | advisory | Self-healing and evolution |
| `plan/feature-chinese-cognitive-lane-launch-1.md` | hlf-specific | advisory | Chinese language support |
| `plan/feature-entropy-anchors-1.md` | hlf-specific | advisory | Semantic drift detection |
| `plan/feature-formal-verifier-1.md` | hlf-specific | advisory | Z3 formal verification |
| `plan/feature-local-slm-tuning-1.md` | ai-engineering | advisory | Local SLM tuning |
| `plan/feature-native-comprehension-mode-1.md` | hlf-specific | advisory | Native comprehension |
| `plan/feature-orchestration-lifecycle-1.md` | hlf-specific | advisory | Orchestration lifecycle |
| `plan/feature-research-scaffold-integration-1.md` | ai-engineering | advisory | Research scaffold |
| `plan/feature-robotics-embodied-execution-1.md` | hlf-specific | advisory | Robotics execution |
| `plan/feature-routing-fabric-1.md` | hlf-specific | advisory | Routing fabric design |
| `plan/feature-self-healing-parser-1.md` | hlf-specific | advisory | Self-healing parser |
| `plan/feature-symbolic-semantic-surfaces-1.md` | hlf-specific | advisory | Symbolic surfaces |
| `plan/feature-witness-governance-1.md` | hlf-specific | advisory | Witness governance |

### Tier 10: HLF Fixture Programs (authority=canonical, domain=hlf-specific)

The canonical HLF program examples. These are the packaged equivalent of upstream `hlf_programs/` and serve as compiler/runtime validation, documentation, and ingestion exemplars.

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `fixtures/README.md` | hlf-specific | canonical | Fixture gallery catalog and run instructions |
| `fixtures/hello_world.hlf` | hlf-specific | canonical | Minimal end-to-end sanity case |
| `fixtures/decision_matrix.hlf` | hlf-specific | canonical | Structured choice and reasoning flow |
| `fixtures/delegation.hlf` | hlf-specific | canonical | Agent delegation pattern |
| `fixtures/file_io_demo.hlf` | hlf-specific | canonical | File-oriented workflow example |
| `fixtures/log_analysis.hlf` | hlf-specific | canonical | Audit-style analysis flow |
| `fixtures/math_expressions.hlf` | hlf-specific | canonical | Math expression evaluation |
| `fixtures/module_workflow.hlf` | hlf-specific | canonical | Module/package-oriented workflow |
| `fixtures/routing.hlf` | hlf-specific | canonical | Routing and orchestration |
| `fixtures/security_audit.hlf` | hlf-specific | canonical | Policy-heavy security example |
| `fixtures/stack_deployment.hlf` | hlf-specific | canonical | Deployment-oriented workflow |
| `fixtures/system_health_check.hlf` | hlf-specific | canonical | Health-check automation |
| `fixtures/db_migration.hlf` | hlf-specific | canonical | Migration-oriented workflow |

### Tier 11: VS Code Extension (authority=canonical, domain=frontend)

Key documentation and configuration for the HLF VS Code extension bridge.

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `extensions/hlf-vscode/README.md` | frontend | canonical | Extension scope, claim-lane visibility, transport modes |
| `extensions/hlf-vscode/package.json` | frontend | canonical | Extension capabilities, commands, configuration schema |
| `extensions/hlf-vscode/language-configuration.json` | hlf-specific | canonical | HLF language editing support config |

### Tier 12: Governance Templates & Code (authority=canonical, domain=security)

Governance templates and enforcement code not already covered in Tier 4.

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `governance/templates/persona_review_handoff.md` | security | canonical | Persona review handoff template |
| `governance/templates/persona_review_handoff_contract.md` | security | canonical | Persona review contract template |
| `governance/templates/dictionary.json` | hlf-specific | canonical | Governance dictionary |
| `governance/license_revocation.py` | security | canonical | Fork license compliance enforcement |
| `governance/update_governor.py` | security | canonical | Governor update automation |

### Tier 13: CI/CD & Automation (authority=canonical, domain=devops)

Agentic workflow intent and key automation scripts.

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `.github/agentic/weekly-triage.md` | devops | canonical | Agentic triage intent and philosophy |

### Tier 14: TextMate Grammar (authority=canonical, domain=hlf-specific)

| File | Domain | Authority | Reason |
|------|--------|-----------|--------|
| `syntaxes/hlf.tmLanguage.json` | hlf-specific | canonical | TextMate grammar for HLF syntax highlighting |

---

## PHASE 2 — Code-Aware Ingestion (noted, not yet ingestible)

These files contain real knowledge but require code-aware chunking (by class/function + docstrings) rather than the current markdown-heading splitter. They are tracked here for Phase 2 ingestion capability.

### Source Code (`hlf_mcp/` — 42+ Python files)

The product itself. Module docstrings, class definitions, function signatures, and inline comments contain authoritative implementation knowledge. Key files include:

- `hlf_mcp/server.py` — FastMCP server entry and transport configuration
- `hlf_mcp/server_core.py` — Core tool registration (compile, format, lint, run, validate)
- `hlf_mcp/server_memory.py` — Memory tools (store, query, HKS capture/recall, ingestion)
- `hlf_mcp/server_translation.py` — Translation tools (to_hlf, to_english, resilient)
- `hlf_mcp/server_resources.py` — Resource and operator surface registration
- `hlf_mcp/server_verifier.py` — Formal verification tools
- `hlf_mcp/server_capsule.py` — Intent capsule tools
- `hlf_mcp/server_instinct.py` — Instinct lifecycle tools
- `hlf_mcp/server_profiles.py` — Model qualification tools
- `hlf_mcp/rag/memory.py` — RAGMemory engine (2900+ lines)
- `hlf_mcp/doc_ingest.py` — Document ingestion pipeline
- `hlf_mcp/dream_cycle.py` — Dream cycle advisory system
- `hlf_mcp/governed_review.py` — Governed review contracts
- `hlf_mcp/persona_contract.py` — Persona ownership contracts
- `hlf_mcp/weekly_artifacts.py` — Weekly evidence artifact capture

### CI/CD Workflows (`.github/workflows/` — 12 YAML files)

Automation pipelines: nightly-status-refresh, readiness-refresh, weekly-code-quality, weekly-doc-security, weekly-ethics-review, weekly-evolution-planner, weekly-model-drift-detect, weekly-spec-sentinel, weekly-test-health, upstream-sync, vscode-extension-package, test-live-ollama-api.

### CI/CD Scripts (`.github/scripts/` — 10 Python files)

Governance automation: codebase_snapshot, create_github_issue, emit_weekly_artifact, ethics_compliance_check, fetch_code_scanning_summary, generate_status_overview, governed_review_contract, ollama_client, readiness_refresh_check, spec_drift_check.

### Scripts (`scripts/` — 17 files)

Tooling: fork_compliance_check, gen_docs, gen_manifest, generate_tm_grammar, hlf_token_lint, live_api_test, monitor_forks, monitor_model_drift, run_pipeline_scheduled, verify_chain. Plus `legacy_probes/` with 6 test scripts and README.

### Test Suite (`tests/` — 58 Python files)

Behavioral specifications via assertions. Each test file defines expected behavior for a module. Key tests: test_compiler, test_ethics, test_governance_spine, test_formal_verifier, test_capsule_pointer_trust, test_memory_evidence_schema, test_hks_memory, test_doc_ingest.

### VS Code Extension Source (`extensions/hlf-vscode/src/` — 13 JS files)

Operator surface implementations: extension.js, operatorPanel.js, trustPanel.js, claimLanes.js, diagnostics.js, memoryGovernance.js, packagedActions.js, resourceCatalog.js, launcher.js, config.js, mcpHttpClient.js, secrets.js, resourceUriTemplate.js. Plus 8 acceptance test files.

### Infrastructure Configs

- `pyproject.toml` — Project metadata, dependencies, tool configuration
- `docker-compose.yml` — Container orchestration
- `Dockerfile` — Container build
- `Caddyfile` — Reverse proxy configuration
- `server.json` — Server configuration
- `components.json` — UI component registry
- `.vscode/mcp.json` — VS Code MCP wiring

### Observability Artifacts (`observability/` — 17 files)

Point-in-time validation evidence from 2026-03-20 across doc-accuracy, test-health, and coverage chains. JSON-format governed review artifacts. These are evidence records, not knowledge docs — they may be better suited for `witness_record` or `media_evidence` ingestion paths rather than the standard document chunker.

---

## SUPPORTIVE REFERENCE (not ingestion targets)

These directories live in the workspace but are **not part of the main HLF_MCP repo**. They exist for source archaeology, research, and compatibility. Agents may skim them for context but should NOT ingest them as primary knowledge.

| Directory | Role | Use |
|-----------|------|-----|
| `hlf_source/` | Upstream Sovereign Agentic OS submodule | Source archaeology, constitutive surface recovery |
| `donor/AgentKB_MCP/` | HKS research donor project | External technique comparison |
| `hlf/` | Legacy compatibility line | Historical reference only |
| `ollama_folder_qa/` | Separate QA tool | Not HLF knowledge |
| `.lollms/` | External tool cache | Not HLF knowledge |

---

## EXCLUDED FROM INGESTION (20 files)

### SKIP-STALE (outdated, superseded)

| File | Reason |
|------|--------|
| `HLF_IMPLEMENTATION_SUMMARY.md` | 2025-01-XX date, superseded by SSOT + Implementation Index |
| `HLF_IMPLEMENTATION_COMPLETE.md` | 2025-01-XX date, superseded by current-truth surfaces |
| `HLF_INTEGRATION_SUMMARY.md` | Redundant with above, older content |
| `HLF_SUMMARY.txt` | Fragmented, low density vs structured docs |

### SKIP-DUPLICATE (redundant with approved docs)

| File | Superseded By |
|------|---------------|
| `IMPLEMENTATION_INDEX.md` | `HLF_IMPLEMENTATION_INDEX.md` |

### SKIP-SCAFFOLD (planning artifacts, not knowledge)

| File | Reason |
|------|--------|
| `TODO.md` | Generic task list, no structured knowledge |
| `Cogito_Discussion.md` | Discussion notes, no clear authority |
| `docs/HLF_GUI_BUILD_GUIDE_DRAFT.md` | Draft status, not current truth |

### SKIP-GENERATED (auto-generated, regenerable)

| File | Reason |
|------|--------|
| `HLF_EXHAUSTIVE_ANALYSIS.md` | Extracted source analysis, regenerable |
| `HLF_EXHAUSTIVE_GAPS_ANALYSIS.md` | Superseded by HLF_MISSING_PILLARS.md |
| ~~`docs/AGENTS_CATALOG.md`~~ | **RECLASSIFIED → Tier 5** (contains 154 unique artifacts, not merely regenerable) |
| `docs/QA_FINDINGS.md` | QA report snapshot, regenerable |
| `docs/QA_FINDINGS_HATS.md` | QA findings by persona, regenerable |

---

## IDENTIFIED DUPLICATE CLUSTERS (for awareness, not action)

1. **Implementation Completion** — `HLF_IMPLEMENTATION_SUMMARY.md`, `HLF_IMPLEMENTATION_COMPLETE.md`, `HLF_INTEGRATION_SUMMARY.md` all stale. Use `HLF_IMPLEMENTATION_INDEX.md` as authority.

2. **Vision Stack** — `HLF_VISION_DOCTRINE.md`, `HLF_DESIGN_NORTH_STAR.md`, `HLF_VISION_MAP.md`, `HLF_STITCHED_SYSTEM_VIEW.md`, `HLF_VISION_PLAIN_LANGUAGE.md` — **intentional layering** by audience and lane. NOT duplicates. All approved.

3. **Gap Analysis** — `HLF_EXHAUSTIVE_GAPS_ANALYSIS.md` (generated) superseded by `HLF_MISSING_PILLARS.md` (authoritative). Skip the generated one.

4. **Implementation Index** — `IMPLEMENTATION_INDEX.md` is a duplicate of `HLF_IMPLEMENTATION_INDEX.md`. Skip the shorter one.

5. **Readiness Stack** — `HLF_QUALITY_TARGETS.md`, `HLF_READINESS_SCORING_MODEL.md`, `HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md` — **intentional stratification** (what/how/score). NOT duplicates.

---

## INGESTION ORDER (recommended)

### Phase 1 — Markdown/Text/JSON/YAML (current chunker)

1. **Governance assets first** (Tier 4 + Tier 12) — these constrain everything else
2. **Canonical doctrine** (Tier 1) — foundational framework
3. **Current-truth reference** (Tier 2) — what's actually real now
4. **Technical reference** (Tier 3) — parser, grammar, stdlib, host functions
5. **Agent & operator** (Tier 5) — how agents interact with HLF
6. **HLF fixture programs** (Tier 10) — canonical language examples
7. **Bridge specs** (Tier 6) — recovery and convergence plans
8. **Architecture & feature plans** (Tier 9) — bridge-lane build sequences
9. **Readiness & merge** (Tier 7) — status and merge governance
10. **Research & assessment** (Tier 8) — external baselines, fit assessments
11. **VS Code extension docs** (Tier 11) — operator shell documentation
12. **TextMate grammar** (Tier 14) — syntax highlighting spec
13. **CI/CD intent** (Tier 13) — automation philosophy

### Phase 2 — Code-Aware Ingestion (requires new chunker)

After Phase 1 is complete. Requires class/function/docstring-aware chunking:

1. `hlf_mcp/` source code — product implementation knowledge
2. `.github/scripts/` + `.github/workflows/` — governance automation
3. `scripts/` — tooling and monitoring
4. `tests/` — behavioral specifications
5. `extensions/hlf-vscode/src/` — operator surface implementations
6. Infrastructure configs (pyproject.toml, docker-compose.yml, etc.)

### Phase 3 — Evidence Artifacts (requires specialized paths)

1. `observability/` artifacts — point-in-time validation evidence
   (may route through `witness_record` or `media_evidence` rather than doc chunker)

---

## NOTES FOR INGESTION

- **SHA-256 dedup**: The ingestion pipeline already does content-hash dedup, so re-ingestion is safe
- **Domain tags**: Use the domain column for `governed_evidence["domain"]`
- **Authority levels**: Use the authority column for `governed_evidence["authority_level"]`
- **Freshness**: All Phase 1 approved docs are current as of 2026-03-26 branch state
- **JSON files**: `governance/*.json`, `docs/HLF_PERSONA_OWNERSHIP_MATRIX.json`, and `governance/templates/dictionary.json` need JSON-aware chunking, not markdown splitting
- **YAML files**: `governance/*.yaml` need YAML-aware chunking
- **HLF files**: `.hlf` fixture programs are short text — treat as single chunks or split by HLF block markers
- **Extension JSON**: `package.json` and `language-configuration.json` need JSON-aware chunking
- **Scope boundary**: Only main-repo files are ingestion targets. `hlf_source/`, `donor/`, `hlf/`, `ollama_folder_qa/` are supportive reference — skim for context, do NOT ingest as primary knowledge
- **Phase total**: Phase 1 covers ~148 files. Phase 2 adds ~150+ source/test/CI files. Phase 3 adds ~17 observability artifacts
