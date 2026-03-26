# HLF Knowledge Substrate Research Handoff

This document is a single copy-paste brief for an external research contributor.

It is intentionally explicit about what is locally true in this workspace versus what is publicly visible on GitHub.

## Critical Visibility Constraint

You are researching against a repository whose current working truth is on a local, unpublished integration branch.

Public GitHub visibility is limited:

- Public repo: `https://github.com/Grumpified-OGGVCT/HLF-Hieroglyphic-Logic-Framework-MCP`
- Related reference repo: `https://github.com/Grumpified-OGGVCT/Sovereign_Agentic_OS_with_HLF`
- Current working branch in local workspace: `integrate-sovereign`
- Default public branch: `main`

You will likely only be able to inspect what is already on public `main`.

Assume that some implementation details described below are local-branch facts that are not yet visible in the published repository or any published PR.

Do not infer that absence from public GitHub means absence from the real working system.

## Research Goal

Help design a superior, weekly-updated knowledge substrate for HLFMCP.

Local HLF-native name for this subsystem:

- canonical name: `HLF Knowledge Substrate`
- preferred shorthand: `HKS`

The target is not a generic vector store.

The target is a governed, code-aware, standards-aware, HLF-native, Infinite-RAG-backed knowledge layer that gives HLF-powered systems immediate access to trusted, fresh, queryable known knowledge.

This knowledge layer should support:

- modern programming language and framework knowledge
- latest industry standards and innovations
- software engineering best practices
- AI and swarm-orchestration operational knowledge
- ongoing coding and programming technique improvements across the general software stack
- weekly discovery of AI engineering, agentic design, evaluation, safety, and tooling best practices
- known-good prompts
- known-good HLF contracts
- known-good code patterns
- validated repair patterns
- practical upgrade opportunities whenever new methods, tools, or standards materially improve HLF quality, usefulness, or real-world applicability

Weekly mission for HKS:

- improve the whole of coding and programming knowledge available to HLF operators and agents
- keep pace with relevant AI, software engineering, and standards evolution
- adapt external best practices into HLF-native forms instead of copying them blindly
- feed more productive, accurate, and useful real-world HLF usage, repair, translation, orchestration, and governance
- surface upgrade candidates across runtime, memory, tooling, verification, docs, and workflows whenever a credible improvement window appears

Current repo-owned source-audit checkpoint for this intake lane:

- [docs/HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md](HLF_EXTERNAL_TECHNIQUE_SOURCE_AUDIT_2026-03-23.md)

Use that audit to determine which external baselines were actually source-checked, which remain partial, and which lane each item is allowed to influence.

Current bounded implementation-slice plan for this lane:

- [plan/architecture-hks-local-evaluation-bounded-comparator-1.md](../plan/architecture-hks-local-evaluation-bounded-comparator-1.md)

## Canonical Repo Authority Rules

Treat these as the current repo authority model:

1. Canonical product surface: `hlf_mcp/`
2. Compatibility-only line for migration, adapters, metrics glue, and manual legacy probes: `hlf/`
3. Preserved upstream and reference context: `hlf_source/`

Primary authority docs in the local workspace:

- [SSOT_HLF_MCP.md](SSOT_HLF_MCP.md)
- [HLF_CANONICALIZATION_MATRIX.md](HLF_CANONICALIZATION_MATRIX.md)
- [HLF_QUALITY_TARGETS.md](HLF_QUALITY_TARGETS.md)
- [README.md](README.md)
- [docs/HLF_AGENT_ONBOARDING.md](docs/HLF_AGENT_ONBOARDING.md)

Primary authority implementation surfaces in the local workspace:

- [hlf_mcp/server.py](hlf_mcp/server.py)
- [hlf_mcp/hlf/translator.py](hlf_mcp/hlf/translator.py)
- [hlf_mcp/hlf/runtime.py](hlf_mcp/hlf/runtime.py)
- [hlf_mcp/rag/memory.py](hlf_mcp/rag/memory.py)

## Local Branch Facts You Must Treat As Real

The following are true in the working local branch even if you cannot verify them from public `main`.

### 1. Infinite RAG already exists

Current packaged memory surface:

- [hlf_mcp/rag/memory.py](hlf_mcp/rag/memory.py)

Current characteristics:

- SHA-256 dedup
- vector-similarity duplicate suppression
- confidence field
- provenance field
- tags
- Merkle-chain append integrity
- hot and warm tier behavior

### 2. MCP memory tools already exist

Packaged tools in [hlf_mcp/server.py](hlf_mcp/server.py):

- `hlf_memory_store`
- `hlf_memory_query`
- `hlf_memory_stats`

### 3. Weekly automation spine already exists

The correct design should extend this workflow family, not bypass it.

Relevant existing workflows:

- [.github/workflows/weekly-spec-sentinel.yml](.github/workflows/weekly-spec-sentinel.yml)
- [.github/workflows/weekly-evolution-planner.yml](.github/workflows/weekly-evolution-planner.yml)
- [.github/workflows/weekly-model-drift-detect.yml](.github/workflows/weekly-model-drift-detect.yml)
- [.github/workflows/weekly-ethics-review.yml](.github/workflows/weekly-ethics-review.yml)
- [.github/workflows/weekly-doc-security.yml](.github/workflows/weekly-doc-security.yml)
- [.github/workflows/weekly-code-quality.yml](.github/workflows/weekly-code-quality.yml)
- [.github/workflows/weekly-test-health.yml](.github/workflows/weekly-test-health.yml)

### 4. Translation recovery already exists locally

Current local branch includes structured translation resilience work in:

- [hlf_mcp/hlf/translator.py](hlf_mcp/hlf/translator.py)
- [hlf_mcp/server.py](hlf_mcp/server.py)

Local branch capabilities already added:

- multilingual translation diagnostics
- fallback detection
- roundtrip fidelity scoring
- semantic loss flags
- deterministic repair planning for failed translations
- structured repair contract for machine retry
- resilient translation with bounded retries and fail-closed governance behavior

### 5. Known-good translation contracts are already being remembered locally

The local branch already persists known-good translation contract exemplars into the Infinite RAG store and exposes a dedicated recall path.

Treat that as an existing seed pattern for the broader weekly knowledge system.

### 6. Governed safety storage already exists

Relevant local files:

- [governance/pii_policy.json](governance/pii_policy.json)
- [hlf_mcp/hlf/pii_guard.py](hlf_mcp/hlf/pii_guard.py)
- [hlf_mcp/hlf/runtime.py](hlf_mcp/hlf/runtime.py)

### 7. Current local validation is green

Focused regression coverage for the current branch is passing for:

- translator
- fast MCP front door
- PII guard
- ethics

Do not treat the system as speculative or unvalidated.

## What HLFMCP Is Trying To Become

HLFMCP is not just an MCP server.

It is trying to become a deterministic, governed HLF substrate for:

- swarms
- translation and repair
- provenance and audit
- persistent memory
- safer tool use
- repeatable orchestration
- immediate known knowledge at runtime

The knowledge layer you are helping design must fit that target.

## External Baseline Research Program

Research leading production-grade technical knowledge services, continuous RAG systems, code-aware retrieval stacks, and governance-first knowledge architectures.

You are not benchmarking for branding. You are extracting the strongest portable patterns and discarding weak product-specific assumptions.

Research discipline for this lane:

- if an external technique is not yet captured in the repo-owned source audit, treat it as unconfirmed until it is reviewed and added
- preserve HLF-native naming in active implementation and planning surfaces even when external comparisons help the design
- do not promote external technique names into current-truth claims without packaged proof and SSOT updates

## Local Evaluation Authority Rule

HKS must own its own evaluation method.

That means the packaged knowledge substrate is responsible for deciding whether a memory record is:

- grounded enough to trust
- sufficiently cited or provenance-backed
- fresh enough to retain in active governed use
- eligible for exemplar promotion
- still advisory only

The correct target is not an external service deciding what HKS knows.

The correct target is:

- HKS-native evaluation for admission, recall, promotion, and weekly evidence
- optional external comparison only when explicitly requested
- explicit local re-evaluation before any external signal can influence governed truth

## External Comparator Boundary

External search or code-intelligence systems may be useful as comparators, bootstrap donors, or challenge sets.

They are not allowed to become the governing authority for HKS.

Use this hard boundary:

1. external comparator use is optional
2. external comparator use must be configuration-gated
3. comparator results must be labeled as bridge-lane advisory output
4. comparator results must not directly create promoted exemplars
5. comparator results must not directly become route evidence or verifier evidence
6. comparator results must pass back through local HKS evaluation before any governed write or promotion

If a design makes HKS correctness depend on a comparator backend being reachable, that design is wrong for this repo.

## WebCode-Style Method, HKS-Owned

The portable pattern worth extracting from external code-research or web-research systems is the evaluation method, not the dependency shape.

For this repo, that means:

- recreate the useful parts of the method inside HKS
- keep evaluation fields in packaged HKS contracts
- produce operator-visible status and report surfaces for the evaluation chain
- treat any outside backend as a bounded comparison source, not as core runtime authority

In practical terms, the next slice should land in these seams:

- `hlf_mcp/rag/memory.py`
- `hlf_mcp/weekly_artifacts.py`
- `hlf_mcp/server_context.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_resources.py`
- `tests/test_hks_memory.py`
- `tests/test_fastmcp_frontdoor.py`

### Product and system identity

For each relevant external baseline, capture:

- repo URL, if public
- docs URL
- maintainer or vendor
- license, if public
- primary use case
- whether it is a service, framework, library, MCP server, or reference implementation

### Architecture

Capture:

- storage layers
- retrieval path
- ingestion path
- embedding stack
- reranker, if any
- chunking strategy
- metadata schema
- provenance model
- whether it supports hot, warm, and cold tiers

### Update mechanics

Capture:

- how it refreshes knowledge
- whether refresh is scheduled or event-driven
- full re-index versus delta update
- stale-content handling
- weekly versus continuous sync jobs

### Source types

Capture support for:

- code repos
- docs sites
- API specs
- issues and PRs
- changelogs
- package registries
- research papers
- blogs
- notebooks
- local files
- transcripts
- structured data

### Trust and governance

Capture:

- source authority model
- freshness model
- confidence model
- version-awareness
- license-awareness
- verification and trust markings
- whether it separates canonical trusted sources from advisory sources

### Retrieval behavior

Capture:

- keyword search
- semantic search
- hybrid search
- graph-aware search
- metadata-filtered search
- recency bias
- task-aware retrieval
- code-aware retrieval

### Runtime integration model

Capture how consuming systems use it:

- prompt injection
- tool call
- API
- MCP
- SDK
- local cache
- prompt-pack generation

### Evaluation surface

Capture:

- recall and precision
- hallucination reduction
- task completion impact
- freshness impact
- retrieval latency
- duplicate suppression quality
- grounding quality
- benchmark suite, if any

### Weaknesses

Capture recurring weaknesses such as:

- missing provenance
- weak freshness logic
- poor code intelligence
- weak dedup
- shallow update loop
- no multilingual handling
- no governance
- no replayability
- no trust tiers

## What We Need You To Analyze For HLFMCP

Use the repo context above and answer these design questions.

### Core comparison

1. Which external patterns are worth copying into HLFMCP unchanged?
2. Which external patterns are insufficient for HLFMCP's governance and orchestration target?
3. Which ideas are portable design patterns versus product-specific implementation details?

### Knowledge-system design

1. What would make an age-of-AI and swarm-native knowledge layer materially better than a normal developer KB?
2. How should weekly refresh differ from on-demand ingest?
3. What should be stored as raw knowledge versus canonicalized HLF-ready knowledge?
4. What should be remembered as trusted exemplars, and what should remain advisory only?
5. How should low-quality or stale material be prevented from poisoning the store?

### Schema and retrieval

1. What should the freshness, provenance, confidence, and trust-tier schema look like?
2. What retrieval contract should runtime systems use to reduce hallucination and improve immediate utility?

### Evaluation

1. What measurable evaluation loop proves this knowledge system is helping runtime systems rather than just growing storage volume?
2. What weekly KPIs should be tracked for freshness, trusted-source coverage, exemplar yield, and retrieval quality?

### Refactoring lens

1. What repo-level refactors should accompany implementation so the knowledge substrate lands as a coherent HLF-native surface rather than a bolt-on?
2. Which naming, package-boundary, workflow, and tool-contract refactors should happen first?

## Best Practices To Gather

Please research best practices for:

1. Continuous RAG for software engineering knowledge bases
2. Infinite RAG patterns for rolling updates without full re-ingestion
3. Code-aware chunking and code-plus-doc retrieval
4. Provenance and trust-tier design for runtime memory
5. Freshness scoring and decay strategies
6. Delta-ingestion and dedup strategies
7. Version-aware retrieval for frameworks, SDKs, and standards
8. Multilingual retrieval and canonicalization
9. Runtime-facing retrieval contracts that reduce hallucination
10. Evaluation methods for knowledge systems that serve code and orchestration

## Constraints And Design Preferences

Assume these design preferences unless evidence strongly suggests a better alternative:

- governance-first storage
- provenance and auditability are mandatory
- trusted canonical knowledge must be distinguished from advisory knowledge
- code-aware retrieval matters more than generic document search
- weekly scheduled updates should integrate into the existing GitHub Actions spine
- known-good exemplars should be first-class memory citizens
- repair patterns and successful contracts should be reusable memory assets
- the goal is immediate known knowledge for HLF-powered systems, not just a larger archive
- implementation planning must include refactoring of naming, module boundaries, workflow labels, and retrieval contracts

## Preferred Research Output Format

Please return findings in this structure.

### 1. External baseline profile set

Short paragraphs plus links.

### 2. Feature matrix

Columns:

- Capability
- Strongest external pattern
- HLFMCP today
- Gap
- Opportunity

### 3. Architecture notes

Cover:

- storage
- ingest
- retrieval
- update loop
- governance
- evaluation
- refactoring implications

### 4. Best-practice findings

Short bullets with source links.

### 5. Recommended moves for HLFMCP

Prioritize:

1. what to add first
2. what to add second
3. what to add third
4. what to refactor in parallel

### 6. Raw sources

Provide the source list:

- docs
- repos
- benchmarks
- issues
- blog posts
- talks

## Short Version

Research continuous, code-aware, governance-first knowledge-system best practices to help design a weekly-refreshed, trust-tiered, Infinite-RAG-backed knowledge substrate for HLFMCP. Public GitHub will not show all local branch work. Treat the local branch facts in this document as real. The resulting design should deliver immediate, trusted, fresh, queryable, HLF-native known knowledge for translation, repair, orchestration, and swarm use.
