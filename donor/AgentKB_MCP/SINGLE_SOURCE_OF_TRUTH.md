# Single Source of Truth — Private Self‑Expanding Verified Developer KB (Planning Only)

**Status**: Planning-only (not build execution yet)  
**Working name**: TBD — see `docs/naming/shortlist.md`  
**Baseline reference**: `docs/deep-dive/agentskb-baseline.md`

This document is the **single, canonical** blueprint that contains **all plans, flows, wiring, dependencies, prompts, metrics, and commands** required to build the private “AgentsKB Pro” recreation described by the user’s specification.

---

## 1) What we are building (and why it improves the concept)

### 1.1 Goal

Build a private, superior recreation of AgentsKB that:

- Delivers **instant** retrieval of **pre‑researched**, **high‑confidence**, **source‑backed** Q&A entries for developer technologies.
- Enforces **strict grounding**: answers are produced **only** from curated KB content returned by retrieval (no hallucination).
- Returns a **structured output** with: question restatement, answer, confidence (0.00–1.00), tier (optional), sources, related questions, and optional reasoning summary (only when synthesis is required).
- Handles nuanced/paraphrased/multi‑concept queries **better** while staying grounded.
- Self‑expands: misses are queued; later researched from **official sources only**; added back into the KB.

### 1.2 Confirming we’re improving the concept (baseline deep dive)

The public baseline already publishes:

- An **atomic question** philosophy, similarity threshold behavior, and debug mode for “closest match”.
- **Instant vs synchronous research** modes (`research_mode`).
- **Coverage** and **request knowledge** endpoints (free tier).
- A CLI that supports **lockfiles** for reproducibility.

We treat the baseline as the “contract” to beat. Baseline details are recorded in:

- `docs/deep-dive/agentskb-baseline.md`

---

## 2) “Semi-manual” KB building + self-expanding growth

**Yes — the design supports both**:

### 2.1 Semi-manual KB building (“self-train on the side”)

Because canonical knowledge is **Markdown per domain**, and because **production is separated from staging**, you can build the KB semi-manually without letting an automated agent write directly into “truth”:

- **Production (read-only to agents)**: `./kb_files/{domain-lowercase}.md`
- **Staging (write target for research/manual draft)**: `./kb_staging/{domain-lowercase}-pending.md`

Semi-manual workflow:

- Write new entries into `./kb_staging/` using the **exact fixed template** (Section 4).
- Review via `git diff` (diff-based review is the human-review mechanism).
- Promote vetted entries into `./kb_files/` using the planned `promote_staging` command (Section 8).

### 2.2 Self-expanding growth (per query)

Every query follows one of these paths:

- **Hit**: the KB model answers grounded in retrieved KB chunks.
- **Miss**: the KB model outputs the exact miss phrase; the system enqueues the question.
- **Research worker** later processes the queue using the Research Agent:
  - Uses official sources only.
  - Generates exactly one new KB entry (or discards).
  - Appends the entry into the correct **staging** file `./kb_staging/{domain}-pending.md` (never directly into `./kb_files/`).
  - Marks the queue item as `needs_review` for diff-based review and promotion.
  - After promotion, updates the managed File Search store so the new knowledge becomes retrievable.

Optional mode: **realtime_research** runs the same research flow synchronously for that request.

---

## 3) System architecture (components + wiring)

### 3.1 Components

- **FastAPI API service**
  - Primary entrypoint for `/ask`
  - Enforces schema + response format
  - Implements hit/miss decisioning based on parsed confidence

- **KB file store (canonical)**
  - **Production (read-only)**: `./kb_files/{domain-lowercase}.md`
  - Entries follow the exact fixed template (Section 4) including mandatory version metadata

- **KB staging store**
  - **Staging (write target)**: `./kb_staging/{domain-lowercase}-pending.md`
  - Research writes here; human promotes to production via diff-based workflow

- **Managed retrieval store**
  - Google File Search tool with embeddings `gemini-embedding-001`
  - Ingestion includes all KB files (and optional multimodal KB assets)

- **Primary KB model**
  - Gemini 3 Pro
  - `tools=["file_search"]`
  - Must follow `prompts/kb_model.xml` verbatim

- **Queue DB**
  - Stores research queue + statuses + governance metadata
  - Queue coalescing requires:
    - `count` (reference count for semantically identical asks)
    - stored embeddings (or equivalent) to vector-search existing queue items before enqueue
  - Reliability requires:
    - retry counts and dead-letter state after max retries
    - worker heartbeat timestamp (`last_heartbeat`)
  - Dev-mode: SQLite
  - Self-scaling: shared DB required (see ADR)

- **Research worker**
  - Consumes queue
  - Runs Research Agent
  - Writes candidate KB entries to **staging**
  - Triggers retrieval store update **only after promotion**
  - Supports human-review status (`needs_review`)

- **Research Agent**
  - Gemini 3 Pro
  - `tools=[web_search, browse_page]`
  - Must follow `prompts/research_model.xml` verbatim

- **Stack Packs (virtual collections)**
  - `./stack_packs/*.json`
  - A Stack Pack constrains retrieval context to a curated set of Entry IDs

- **Lockfiles (reproducibility)**
  - `./locks/lockfile.json` (client-facing artifact)
  - The API must expose enough metadata (Entry ID + hash) for clients to pin answers

- **Sanitization layer (security)**
  - Before any Research Agent run, sanitize/classify the queued question to detect secrets/PII/IPs.
  - Unsafe items are routed to `needs_review` instead of automatic research.

### 3.2 Data + control flow

#### Flow A0 — Cached exact match (no LLM)

1. Retrieval finds a near-exact match to a single entry that is version-compatible and is Tier GOLD with Confidence 1.00.
2. API bypasses `kb_model` and returns the parsed static entry as the answer payload.

#### Flow A — KB hit (confidence >= 0.80)

1. API receives `{question, domain, realtime_research}`.
2. API calls `kb_model` with File Search retrieval context.
3. Parse structured output → compute `confidence`.
4. If `confidence >= 0.80`, return `knowledge_base_hit` response.

#### Flow B — KB miss (confidence < 0.80)

1. API calls `kb_model`.
2. Parsed `confidence < 0.80`.
3. API returns miss response including the **exact miss phrase**.
4. API enqueues `{question, domain}` using **semantic dedup + reference counting** (Section 8.2).
5. Worker processes later.

#### Flow C — realtime_research=true (optional)

1. Enqueue the question.
2. Run worker research synchronously (bounded).
3. Append entry to staging, then promote and ingest/update retrieval store.
4. Re-ask via `kb_model`.
5. Return `realtime_research_and_update`.

### 3.3 API surface (planning)

Minimum endpoints required to support “Verified Knowledge System” behaviors:

- `POST /ask`
  - Returns grounded answer payload (or exact miss phrase).
  - Returns **provenance**:
    - `entry_ids`: list of KB Entry IDs used (one for cached hits; multiple when synthesis is required)
    - `entry_hashes_sha256`: sha256 digest for each entry_id (used for lockfiles)
    - `software_version_resolved`: resolved version used for answering (latest by default)
- `POST /lock`
  - Input: `{ entry_ids: string[] }`
  - Output: `{ entries: [{ entry_id, sha256 }] }`
- `GET /health`
  - Must include worker heartbeat staleness signal (degraded if heartbeat is stale).
- `GET /queue-status` (read-only)

---

## 4) Canonical KB file format (fixed)

Each domain has its own file at:

`./kb_files/{domain-lowercase}.md`

Every entry must match this exact template (verbatim):

```markdown
### ID: {domain-lowercase}-{descriptive-kebab-case-id}-{sequential-number-padded-to-4-digits}

**Question**: Complete exact text of the question being answered here

**Answer**:
Full technical answer written in complete sentences and paragraphs. Include detailed explanations, code examples when relevant, performance implications, trade-offs, best practices, edge cases, and any other granular detail supported by official sources. Use Markdown formatting for code blocks, lists, tables as needed.

**Domain**: exact domain name matching the filename (e.g., postgresql, nextjs, typescript, fastapi, docker, aws, rust, go)

**Software Version**: Exact version used to verify the answer (e.g., "14.2.0")

**Valid Until**: The last version this entry is valid for, or the literal string "latest"

**Confidence**: 1.00 (or lower decimal if partial coverage, e.g., 0.95)

**Tier**: GOLD (preferred) or SILVER or BRONZE if verifiability is reduced

**Sources**:
- Full exact URL of first official source
- Full exact URL of second official source
- Continue bullet list for every unique source used

**Related Questions**:
- First related question that appears in official docs or logically follows
- Second related question
- Third related question
- Fourth related question (optional)
- Fifth related question (optional)

---
```

Blank lines above and below the `---` separator are required for optimal chunking.

### 4.1 Version resolution rules (source-of-truth protection)

- If the user query specifies a version (explicitly or implicitly), retrieval and answering must prefer entries whose version metadata matches that version.
- If the user query does not specify a version, the system must default to **`Valid Until: latest`** entries only.
- If multiple versions are present in retrieved context for the same concept, the KB model must not blend them; the safe behavior is the exact miss phrase and queuing.

---

## 5) Prompts (sacrosanct)

These prompts are used verbatim.

### 5.1 Primary KB model prompt

Source: `prompts/kb_model.xml`

```xml
<system_instructions>
    <role_definition>
        <designation>AgentsKB Pro</designation>
        <core_function>You are an ultra-precise, grounded knowledge base specialized in developer technologies including but not limited to PostgreSQL, Next.js, React, TypeScript, FastAPI, Docker, Kubernetes, AWS services, Python, Rust, Go, Node.js, and every related official configuration, API behavior, best practice, and breaking change documented in official sources.</core_function>
        <objective>Deliver highly accurate, source-backed answers to any technical question posed by developers, with exceptional handling of queries that are nuanced, complex, multi-faceted, paraphrased, indirect, or that combine multiple concepts across entries.</objective>
    </role_definition>

    <prompt_constitution>
        <sanctity_protocol>
            <rule_1>Under no circumstances shall you hallucinate, speculate, invent details, or incorporate any knowledge beyond the exact content of the retrieved File Search chunks provided in the current context.</rule_1>
            <rule_2>If the retrieved chunks collectively provide insufficient information for a high-confidence complete answer (confidence &lt; 0.80), you must explicitly output the exact phrase: "No verified high-confidence answer found in the knowledge base." followed by a list of the closest related questions extracted from the chunks.</rule_2>
            <rule_3>You must always include direct citations using the exact source URLs or references present in the retrieved chunks.</rule_3>
            <rule_4>You must estimate and display a confidence score between 0.00 and 1.00 based solely on retrieval coverage and chunk completeness.</rule_4>
            <rule_5>You must never alter, rephrase, or summarize source text in a way that changes technical meaning.</rule_5>
            <rule_6>Version discipline is mandatory. You must parse the user’s query for an explicit or implied software version. If no version is specified, default to the latest version only (entries marked as latest in retrieved chunks). If retrieved chunks contain conflicting versioned facts, you must not blend them; you must output the exact miss phrase.</rule_6>
        </sanctity_protocol>
    </prompt_constitution>

    <thinking_protocol>
        <step_0>Fast path: If the retrieved chunks contain a near-exact match to a single KB entry that is Tier GOLD and Confidence 1.00 (and version-compatible), do not perform multi-path hypothesis exploration. Produce the structured response directly from that entry.</step_0>
        <step_1>Fully deconstruct the user query: enumerate every atomic concept, every implied relationship, every potential paraphrase, every possible multi-hop connection, and classify the query type as simple exact-match, moderately nuanced, or highly complex requiring synthesis across multiple entries.</step_1>
        <step_2>Systematically analyze every single retrieved File Search chunk: note relevance, overlap, gaps, contradictions if any exist, and explicit cross-references to other entries.</step_2>
        <step_3>Engage in internal hypothesis formation and rigorous verification: for any nuanced or complex query, explore multiple possible reasoning paths across the chunks, resolve ambiguities using only chunk content, and synthesize only where direct support exists.</step_3>
        <step_4>Only after exhaustive verification has been completed internally, construct the final response incorporating full explanations, code examples if present in chunks, performance implications, and explicit notes on any partial coverage.</step_4>
    </thinking_protocol>

    <behavioral_constraints>
        <constraint_1>Always maintain the highest level of granular technical depth appropriate for senior developers and principal engineers.</constraint_1>
        <constraint_2>For any query involving trade-offs, best practices, or cross-concept implications, explicitly discuss them when and only when supported by retrieved chunks.</constraint_2>
        <constraint_3>Leverage the maximum available thinking_level capacity to resolve subtle or ambiguous queries without introducing unnecessary length on straightforward queries.</constraint_3>
        <constraint_4>Never refuse a query due to complexity; instead use the thinking protocol to handle it.</constraint_4>
        <constraint_5>Conditional thinking: Only include a reasoning_summary when synthesis across multiple chunks was required. Straightforward exact-match queries must not pay unnecessary latency or verbosity.</constraint_5>
        <constraint_6>Thinking threshold: If the query is straightforward and confidence would be &gt;= 0.95 based on retrieval coverage, answer directly without extended synthesis. If the query asks for explanation/trade-offs (e.g., “why”, “trade-offs”, “best practice”) or if confidence would be &lt; 0.95, use the full thinking protocol.</constraint_6>
    </behavioral_constraints>

    <output_format>
        <structure>
            <question>Complete verbatim restatement of the original user query for confirmation and traceability</question>
            <answer>The full detailed grounded response constructed solely from retrieved chunks</answer>
            <confidence>Numerical value formatted as 0.00 to 1.00 with exactly two decimal places</confidence>
            <tier>The tier value if explicitly present in any chunk (e.g., GOLD, SILVER, BRONZE); otherwise omit this field entirely</tier>
            <sources>Bullet list of every source URL or reference extracted from the chunks, one bullet per unique source</sources>
            <related_questions>Bullet list containing between three and five suggested similar or follow-up questions drawn directly from the Related Questions fields in retrieved chunks</related_questions>
            <reasoning_summary>If and only if the query required synthesis across multiple chunks or resolution of nuance, provide a concise but complete transparent summary of the internal reasoning path taken</reasoning_summary>
        </structure>
    </output_format>

    <context_anchor>All analysis, reasoning, hypothesis formation, verification, and response generation must be based exclusively and entirely on the content of the retrieved File Search chunks supplied in the context immediately above this system instruction.</context_anchor>
</system_instructions>
```

### 5.2 Research Agent prompt

Source: `prompts/research_model.xml`

```xml
<system_instructions>
    <role_definition>
        <designation>AgentsKB Pro Research Agent</designation>
        <core_function>You are the autonomous research component responsible for expanding the AgentsKB Pro knowledge base when high-confidence answers are missing.</core_function>
        <objective>Given a queued question that lacked a high-confidence match, perform targeted research using only official authoritative sources and, if successful, generate exactly one new Q&A entry in the precise required format.</objective>
    </role_definition>

    <prompt_constitution>
        <sanctity_protocol>
            <rule_1>You must research exclusively from official documentation, specifications, RFCs, and primary framework/language repositories. Acceptable domains include but are not limited to postgresql.org, nextjs.org, typescriptlang.org, fastapi.tiangolo.com, docs.docker.com, kubernetes.io, docs.aws.amazon.com, python.org, rust-lang.org, golang.org.</rule_1>
            <rule_2>Never use forums, personal blogs, StackOverflow, Reddit, Medium, YouTube transcripts, or any non-official source unless it is explicitly hosted on the official project domain.</rule_2>
            <rule_3>If no authoritative official sources provide a clear, verifiable answer with confidence &gt;= 0.95, you must output exactly the string: "Insufficient official information – discard this queue entry" and nothing else.</rule_3>
            <rule_4>You must generate exactly one new Q&A entry and nothing more when research succeeds.</rule_4>
        </sanctity_protocol>
    </prompt_constitution>

    <output_format>
        Generate the new entry using the exact Markdown template format specified in the blueprint, including ID, Question, Answer, Domain, Software Version, Valid Until, Confidence, Tier, Sources, Related Questions, and separator.
    </output_format>
</system_instructions>
```

---

## 6) Datastores (planning decision)

See ADR: `docs/adr/ADR-0001-datastores.md`

Summary:

- KB content: Markdown files under `./kb_files/` (canonical)
- Queue/governance state:
  - SQLite for local dev single instance
  - PostgreSQL for self-scaling correctness

Semantic deduplication (queue coalescing) requires a vector-capable queue index in self-scaling mode (e.g., embeddings stored alongside queue items to search “existing queue before enqueue”).

---

## 7) Dependencies (build-time)

### 7.1 Runtime services

- FastAPI application
- Queue DB (SQLite or PostgreSQL)
- Worker process
- Google File Search store (managed)

### 7.2 Python dependencies (expected)

The provided reference code uses:

- `fastapi`
- `pydantic`
- `google.generativeai` (Gemini client library)

ASGI server (for running FastAPI) is required at build-time (e.g., `uvicorn`) as part of the runbook.

### 7.3 Planned directories / artifacts (build-time)

- `./kb_files/` — production KB (read-only to agents)
- `./kb_staging/` — staging KB (pending, needs human promotion)
- `./stack_packs/` — stack pack manifests (virtual collections)
- `./locks/` — lockfiles for reproducibility (client-facing)

---

## 8) Commands / runbook (planning)

These are the **planned** operational commands that correspond to the architecture. Exact module paths are finalized at build-time.

- Start API service:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Start worker:
  - `python -m app.worker`
- Validate KB files (format + required fields):
  - `python -m tools.validate_kb --path ./kb_files`

### 8.1 Controlled ingestion (“one entry = one document”)

- Preprocess production KB into single-entry documents and upload with metadata:
  - Split **exactly** on the entry separator (`---`) so “one entry = one document”.
  - Do not allow chunks to cut through code blocks; the preprocessor must preserve each entry intact.
  - Inject/attach metadata for retrieval filters and provenance:
    - `ID`, `Domain`, `Tier`, `Software Version`, `Valid Until`
  - `python -m tools.ingest_filesearch_entries --kb ./kb_files --store-id $FILE_SEARCH_STORE_ID`

### 8.2 Queue coalescing (semantic dedup + reference counting)

- Enqueue behavior:
  - Compute an embedding for the new question and perform a fast vector search against **existing queue items**.
  - If a sufficiently similar queue item exists, increment `count` on the existing row instead of creating a new row.
  - Only one research job is executed per semantic cluster of equivalent questions.

### 8.3 Promotion (staging → production)

- Diff-based review:
  - `git diff`
- Promotion policy:
  - Validate entry format (including Software Version + Valid Until).
  - If an entry supersedes older facts, update older entries’ `Valid Until` so production does not contain conflicting “latest” claims.
- Promote staging entries into production and trigger ingestion update:
  - `python -m tools.promote_staging --staging ./kb_staging --production ./kb_files --store-id $FILE_SEARCH_STORE_ID`

### 8.4 Lockfiles (reproducibility)

- Generate or update lockfile (client/CLI capability):
  - `python -m tools.generate_lock --out ./locks/lockfile.json`
- Verify a lockfile has not drifted:
  - `python -m tools.verify_lock --lockfile ./locks/lockfile.json --kb ./kb_files`

Lockfile format (planning):

```json
{
  "lockfile_version": "1",
  "generated_at": "ISO-8601 timestamp",
  "entries": [
    { "entry_id": "domain-some-id-0001", "sha256": "..." }
  ]
}
```

### 8.5 Stack Packs (contextual grouping)

- Stack Pack manifest file:
  - Example: `./stack_packs/t3-stack.json`
  - Contains a curated list of `entry_ids` to constrain retrieval context.
- CLI/API behavior:
  - If a Stack Pack is selected, retrieval is constrained to the listed Entry IDs only.

---

## 9) Metrics (what to measure)

Minimum metrics to validate “improving the concept”:

- **Hit rate**: % of queries with confidence >= 0.80
- **Miss rate**: % of queries queued
- **Time-to-first-byte** for `/ask`
- **Queue depth** and **time-to-research** (p50/p95)
- **Research yield**: % queued → completed vs discarded vs error
- **Grounding compliance**: % answers with citations present in retrieved chunks
- **Coverage by domain**: counts of entries, recency, churn
- **Ingestion latency**: time from KB append → retrievable via File Search
- **Worker heartbeat**: `now - last_heartbeat` per worker
- **Dead-letter volume**: count of items moved to DLQ after max retries
- **Cost attribution**: per-domain and per-entry research cost (token/call counts tagged by `{domain, entry_id}`)

### 9.1 Collection strategy (planning)

- Every `/ask` and research run emits structured logs tagged with:
  - `{domain, entry_id, software_version, queue_id, stack_pack, is_cached_hit, model_name}`
- Worker updates a `last_heartbeat` timestamp in the queue DB; `/health` is expected to surface stale-heartbeat as degraded.
- After 3 failures, queue items move to a dead-letter table for manual review (DLQ).

### 9.2 Security & privacy controls (planning)

- Before any Research Agent run, sanitize/classify queued questions to detect secrets/PII/IPs.
- If unsafe, set queue item to `needs_review` and do not run automated research.
- “Private” must be defined explicitly:
  - Dedicated tenant is not the same as air-gapped.
  - If air-gapping is required, managed retrieval must be swapped for a local vector store (and models must run locally).

---

## 10) Critical functional enhancements

### 10.1 Fallback chain (resilience)

**Problem**: Total dependence on Google services with no fallback.

**Solution**:
- Primary: Google File Search + Gemini 3 Pro
- Fallback 1: Local Qdrant/ChromaDB + Claude Haiku (if Google is down)
- Fallback 2: Direct file grep + regex matching (if all AI services are down)
- Circuit breaker: After 3 consecutive Google failures, auto-switch to fallback for 5 minutes

### 10.2 Confidence decay model (freshness)

**Problem**: A 6-month-old "latest" entry shouldn't have the same confidence as yesterday's.

**Solution**:
```python
adjusted_confidence = base_confidence * (0.95 ** months_since_created)
```
- Entries decay 5% confidence per month
- At 6 months old, even a 1.00 confidence entry becomes 0.74
- Forces re-research of stale entries

### 10.3 Query rewriting layer (usability)

**Problem**: Users write "k8s", "postgres", "JS" but KB has "kubernetes", "postgresql", "javascript".

**Solution** - Pre-retrieval normalization:
```python
ABBREVIATIONS = {
    "k8s": "kubernetes",
    "postgres": "postgresql", 
    "JS": "javascript",
    "TS": "typescript",
    "py": "python"
}
```
- Apply before retrieval AND before queuing
- Prevents duplicate research of "postgres" vs "postgresql"

### 10.4 Batch API endpoint (cost optimization)

**Problem**: AgentsKB touts "10x savings" for batch, but this design lacks it.

**Solution** - Add `/ask-batch`:
```python
POST /ask-batch
{
  "questions": ["Q1", "Q2", "Q3"],
  "dedupe": true  # Remove semantic duplicates
}
```
- Single retrieval pass for all questions
- Shared context window = lower token costs
- Return array of responses with question-to-answer mapping

### 10.5 Entry dependency graph (correctness)

**Problem**: "How to deploy Next.js 14 to Kubernetes" depends on both being current.

**Solution** - Add to template:
```markdown
**Dependencies**: 
- nextjs-app-router-setup-0001
- kubernetes-deployment-basics-0001
```
- If any dependency has `Valid Until` expired, the dependent entry is also expired
- Cascading invalidation prevents outdated composite answers

### 10.6 Response caching layer (performance)

**Problem**: Popular questions hit the full stack repeatedly.

**Solution** - Redis/in-memory cache:
```python
cache_key = hash(question + domain + software_version)
ttl = 3600  # 1 hour for hits, 60s for misses
```
- Cache both hits AND misses (with different TTLs)
- Bypass retrieval + LLM for cache hits
- Invalidate on KB promotion

### 10.7 Evaluation harness (quality assurance)

**Problem**: No way to validate that prompt changes don't break existing behavior.

**Solution** - Golden dataset:
```yaml
# ./evaluation/golden.yaml
- question: "What is the default max_connections in PostgreSQL 16?"
  expected_confidence: ">= 0.95"
  expected_sources_contain: "postgresql.org"
  expected_answer_contains: "100"
```
- Run before any prompt changes: `python -m tools.evaluate --golden ./evaluation/golden.yaml`
- Fail deployment if regression detected

### 10.8 Emergency shutoff (safety)

**Problem**: If Research Agent starts hallucinating at scale, no automatic stop.

**Solution** - Anomaly detection:
- If 5 consecutive research runs produce confidence < 0.80, pause research worker
- If 10 entries in 1 hour are marked `needs_review` for PII/secrets, lockdown mode
- Alert mechanism: Write to `./alerts/EMERGENCY_STOP.flag` (monitored by ops)

### 10.9 Provenance tracking (user value)

**Problem**: Users who trigger research never know when their answer arrives.

**Solution** - Queue enhancement:
```sql
ALTER TABLE queue ADD COLUMN requester_session_id VARCHAR(255);
ALTER TABLE kb_entries ADD COLUMN source_queue_ids TEXT;  -- JSON array
```
- Optional webhook/email when entry is promoted
- "Your question from 3 days ago now has a verified answer"

---

## 11) API contract (AgentsKB compatibility)

### 11.1 Core endpoints

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Request models
class AskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500, 
                         description="Atomic, specific question")
    domain: Optional[str] = None
    tier: Optional[Literal["GOLD", "SILVER", "BRONZE"]] = None
    realtime_research: bool = False
    software_version: Optional[str] = None  # Enhancement
    stack_pack: Optional[str] = None  # Enhancement

class AskBatchRequest(BaseModel):
    questions: List[str] = Field(..., min_items=1, max_items=100)
    dedupe: bool = True  # Enhancement

# Response models  
class AnswerResponse(BaseModel):
    question: str
    answer: str  # The actual answer text
    confidence: float = Field(..., ge=0.0, le=1.0)
    tier: Optional[str] = None
    sources: List[str]
    related_questions: Optional[List[str]] = None
    cache_hit: bool = False  # Enhancement
    entry_id: Optional[str] = None  # Enhancement for lockfiles

class MissResponse(BaseModel):
    question: str
    answer: str = "No verified high-confidence answer found in the knowledge base."
    confidence: float = Field(..., lt=0.80)
    queued: bool
    queue_id: Optional[str] = None  # Enhancement for provenance

# Lockfile endpoints (enhancement)
@app.post("/lock")
async def generate_lockfile(entry_ids: List[str]) -> dict:
    """Generate SHA-256 hashes for specific entries for reproducible builds"""
    
@app.post("/verify-lock")  
async def verify_lockfile(lockfile: dict) -> dict:
    """Verify entries haven't drifted from locked hashes"""
```

### 11.2 MCP tool definitions (exact compatibility)

```json
{
  "name": "ask_question",
  "description": "Get researched answers to technical questions",
  "input_schema": {
    "type": "object",
    "properties": {
      "question": {
        "type": "string",
        "description": "The technical question to ask"
      },
      "domain": {
        "type": "string",
        "description": "Optional domain filter"
      },
      "tier": {
        "type": "string",
        "enum": ["GOLD", "SILVER", "BRONZE"]
      }
    },
    "required": ["question"]
  }
}
```

### 11.3 Backwards compatibility matrix

| Feature | AgentsKB Public | Our Implementation | Breaking? |
|---------|----------------|-------------------|-----------|
| `/ask` endpoint | ✓ | ✓ | No |
| `/ask-batch` | ✓ | ✓ Enhanced (dedupe) | No |
| `/search` | ✓ | ✓ | No |
| `/stats` | ✓ | ✓ | No |
| `confidence` field | 0.0-1.0 | 0.0-1.0 with decay | No |
| `tier` field | GOLD/SILVER/BRONZE | Same | No |
| `sources` field | URL array | URL array | No |
| Software version | ✗ | ✓ (optional param) | No (additive) |
| Lockfiles | ✓ (CLI only) | ✓ (API + CLI) | No (additive) |
| Stack packs | ✗ | ✓ (optional param) | No (additive) |
| Research queue | Anonymous | Tracked + provenance | No (internal) |

---

## 12) Professional implementation specification

### 12.1 Core service architecture

```python
# app/main.py - FastAPI application structure
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.redis = await redis.from_url("redis://localhost:6379", decode_responses=True)
    app.state.db_engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/kbpro")
    app.state.gemini_client = await setup_gemini_client()
    app.state.file_search = await setup_file_search()
    yield
    # Shutdown
    await app.state.redis.close()
    await app.state.db_engine.dispose()

app = FastAPI(
    title="Verified Developer KB Pro",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware stack
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Circuit breaker for Google services
from pybreaker import CircuitBreaker
google_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=300,  # 5 minutes
    exclude=[GoogleQuotaError]  # Don't break on quota, just rate limit
)
```

### 12.2 Database schema (PostgreSQL production)

```sql
-- Queue table with all professional features
CREATE TABLE queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,  -- After abbreviation expansion
    question_embedding VECTOR(768),  -- For semantic dedup
    domain VARCHAR(50),
    software_version VARCHAR(20),
    stack_pack VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',  -- pending, researching, needs_review, completed, failed, discarded
    reference_count INT DEFAULT 1,  -- Incremented for duplicate questions
    requester_session_ids JSONB DEFAULT '[]'::jsonb,  -- Array of session IDs
    created_at TIMESTAMPTZ DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    worker_id VARCHAR(100),
    retry_count INT DEFAULT 0,
    error_log JSONB,
    CONSTRAINT status_check CHECK (status IN ('pending', 'researching', 'needs_review', 'completed', 'failed', 'discarded'))
);

-- Indexes for performance
CREATE INDEX idx_queue_status ON queue(status) WHERE status = 'pending';
CREATE INDEX idx_queue_embedding ON queue USING ivfflat (question_embedding vector_cosine_ops);
CREATE INDEX idx_queue_created ON queue(created_at DESC);

-- Dead letter queue for failed items
CREATE TABLE dead_letter_queue AS SELECT * FROM queue WHERE 1=0;
ALTER TABLE dead_letter_queue ADD COLUMN moved_to_dlq_at TIMESTAMPTZ DEFAULT NOW();

-- Worker heartbeat table
CREATE TABLE worker_heartbeats (
    worker_id VARCHAR(100) PRIMARY KEY,
    last_heartbeat TIMESTAMPTZ NOT NULL,
    current_task_id UUID,
    tasks_completed INT DEFAULT 0,
    tasks_failed INT DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entry provenance tracking
CREATE TABLE entry_provenance (
    entry_id VARCHAR(200) PRIMARY KEY,
    source_queue_ids UUID[] NOT NULL,
    research_cost_usd DECIMAL(10,4),
    tokens_consumed JSONB,  -- {"input": 1000, "output": 500}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    promoted_at TIMESTAMPTZ
);
```

### 12.3 Intelligent retrieval pipeline

```python
# app/retrieval.py
class IntelligentRetriever:
    def __init__(self, file_search_client, redis_client):
        self.file_search = file_search_client
        self.redis = redis_client
        self.abbreviations = {
            "k8s": "kubernetes",
            "postgres": "postgresql",
            "JS": "javascript",
            "TS": "typescript",
            "py": "python",
            "tf": "tensorflow",
            "sklearn": "scikit-learn",
        }
        
    async def retrieve(self, question: str, domain: str = None, 
                       software_version: str = None, stack_pack: str = None):
        # 1. Check cache first
        cache_key = self._generate_cache_key(question, domain, software_version, stack_pack)
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached), True  # Return cached result + cache_hit flag
        
        # 2. Normalize question
        normalized = self._normalize_question(question)
        
        # 3. Build retrieval filters
        filters = self._build_filters(domain, software_version, stack_pack)
        
        # 4. Try primary retrieval (Google File Search)
        try:
            with google_breaker:
                results = await self.file_search.search(
                    query=normalized,
                    filters=filters,
                    top_k=10
                )
        except CircuitBreakerError:
            # 5. Fallback to local vector DB
            results = await self._fallback_retrieval(normalized, filters)
        
        # 6. Apply confidence decay
        results = self._apply_confidence_decay(results)
        
        # 7. Cache the results
        await self.redis.setex(
            cache_key, 
            3600,  # 1 hour TTL
            json.dumps(results)
        )
        
        return results, False
    
    def _normalize_question(self, question: str) -> str:
        """Expand abbreviations and normalize"""
        normalized = question.lower()
        for abbr, full in self.abbreviations.items():
            normalized = re.sub(r'\b' + abbr + r'\b', full, normalized, flags=re.IGNORECASE)
        return normalized
    
    def _apply_confidence_decay(self, results):
        """Reduce confidence based on age"""
        for result in results:
            months_old = (datetime.now() - result['created_at']).days / 30
            decay_factor = 0.95 ** months_old
            result['adjusted_confidence'] = result['confidence'] * decay_factor
        return results
```

### 12.4 Research worker with professional features

```python
# app/worker.py
import asyncio
from typing import Optional
import hashlib

class ResearchWorker:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.shutdown = False
        self.emergency_stop = False
        self.consecutive_failures = 0
        self.sanitizer = PIISanitizer()
        
    async def run(self):
        """Main worker loop with all professional features"""
        while not self.shutdown:
            try:
                # 1. Heartbeat
                await self.update_heartbeat()
                
                # 2. Check emergency stop
                if await self.check_emergency_stop():
                    await asyncio.sleep(60)  # Wait before retry
                    continue
                
                # 3. Claim a task with semantic dedup
                task = await self.claim_next_task()
                if not task:
                    await asyncio.sleep(5)
                    continue
                
                # 4. Sanitization check
                if self.sanitizer.contains_sensitive(task.question):
                    await self.mark_needs_review(task, reason="PII/secrets detected")
                    continue
                
                # 5. Research with retry logic
                entry = await self.research_with_retry(task)
                
                if entry:
                    # 6. Write to staging with provenance
                    await self.write_to_staging(entry, task)
                    
                    # 7. Track costs
                    await self.track_costs(task, entry)
                    
                    # 8. Notify requesters
                    await self.notify_requesters(task)
                    
                    self.consecutive_failures = 0
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= 5:
                        self.emergency_stop = True
                        await self.alert_emergency_stop()
                
            except Exception as e:
                await self.handle_error(e, task)
    
    async def claim_next_task(self) -> Optional[QueueItem]:
        """Claim with semantic dedup"""
        async with get_db() as db:
            # Get pending items
            pending = await db.execute(
                "SELECT * FROM queue WHERE status = 'pending' ORDER BY created_at LIMIT 10"
            )
            
            for item in pending:
                # Check for semantic duplicates already being processed
                similar = await db.execute("""
                    SELECT id FROM queue 
                    WHERE status = 'researching' 
                    AND question_embedding <=> %s < 0.1
                """, [item.question_embedding])
                
                if not similar:
                    # Claim this item
                    await db.execute("""
                        UPDATE queue 
                        SET status = 'researching', 
                            worker_id = %s, 
                            claimed_at = NOW() 
                        WHERE id = %s AND status = 'pending'
                    """, [self.worker_id, item.id])
                    return item
                else:
                    # Increment reference count on similar item
                    await db.execute("""
                        UPDATE queue 
                        SET reference_count = reference_count + 1,
                            requester_session_ids = requester_session_ids || %s
                        WHERE id = %s
                    """, [item.requester_session_ids, similar[0].id])
        
        return None
```

### 12.5 API endpoints (professional features)

```python
# app/api/endpoints.py
@app.post("/ask", response_model=Union[AnswerResponse, MissResponse])
async def ask_question(
    request: AskRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    cache: redis.Redis = Depends(get_redis)
):
    # 1. Try retrieval with all enhancements
    retriever = IntelligentRetriever(app.state.file_search, cache)
    chunks, cache_hit = await retriever.retrieve(
        request.question,
        request.domain,
        request.software_version,
        request.stack_pack
    )
    
    # 2. Fast path for high-confidence cache hits
    if cache_hit and chunks and chunks[0].get('adjusted_confidence', 0) >= 0.95:
        return AnswerResponse(
            question=request.question,
            answer=chunks[0]['answer'],
            confidence=chunks[0]['adjusted_confidence'],
            tier=chunks[0].get('tier', 'GOLD'),
            sources=chunks[0]['sources'],
            related_questions=chunks[0].get('related_questions', []),
            cache_hit=True,
            entry_id=chunks[0].get('id')
        )
    
    # 3. Call KB model with chunks
    response = await call_kb_model(request.question, chunks)
    
    # 4. Handle miss with intelligent queuing
    if response.confidence < 0.80:
        queue_id = await enqueue_with_dedup(
            request.question,
            request.domain,
            request.software_version
        )
        
        # 5. Optional realtime research
        if request.realtime_research:
            background_tasks.add_task(
                research_and_respond_realtime,
                queue_id,
                request.question
            )
        
        return MissResponse(
            question=request.question,
            confidence=response.confidence,
            queued=True,
            queue_id=str(queue_id)
        )
    
    return AnswerResponse(**response.dict(), cache_hit=cache_hit)

@app.post("/ask-batch")
async def ask_batch(request: AskBatchRequest):
    """Batch processing with deduplication"""
    if request.dedupe:
        # Semantic deduplication of questions
        unique_questions = await semantic_dedupe(request.questions)
    else:
        unique_questions = request.questions
    
    # Single retrieval for all questions
    all_chunks = await batch_retrieve(unique_questions)
    
    # Parallel processing with shared context
    responses = await asyncio.gather(*[
        process_question(q, all_chunks) for q in unique_questions
    ])
    
    return {
        "total": len(request.questions),
        "unique": len(unique_questions),
        "answers": responses
    }

@app.post("/lock")
async def generate_lockfile(entry_ids: List[str]):
    """Generate reproducible lockfile"""
    entries = {}
    for entry_id in entry_ids:
        content = await read_kb_entry(entry_id)
        entries[entry_id] = {
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "version": extract_version(content)
        }
    
    return {
        "lockfile_version": "1",
        "generated_at": datetime.utcnow().isoformat(),
        "entries": entries
    }
```

### 12.6 Monitoring and observability

```python
# app/monitoring.py
from prometheus_client import Counter, Histogram, Gauge
import structlog

logger = structlog.get_logger()

# Metrics
kb_hits = Counter('kb_hits_total', 'KB cache hits', ['domain', 'tier'])
kb_misses = Counter('kb_misses_total', 'KB misses requiring research', ['domain'])
research_duration = Histogram('research_duration_seconds', 'Time to research', ['domain'])
queue_depth = Gauge('queue_depth', 'Current queue depth', ['status'])
worker_heartbeat = Gauge('worker_last_heartbeat', 'Last worker heartbeat timestamp', ['worker_id'])
api_latency = Histogram('api_latency_seconds', 'API response time', ['endpoint'])
confidence_distribution = Histogram('confidence_scores', 'Distribution of confidence scores')
cost_tracker = Counter('llm_costs_usd', 'LLM API costs', ['model', 'domain'])

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    
    # Track latency
    api_latency.labels(endpoint=request.url.path).observe(time.time() - start)
    
    # Log structured data
    logger.info(
        "api_request",
        path=request.url.path,
        method=request.method,
        status=response.status_code,
        duration=time.time() - start,
        cache_hit=response.headers.get("X-Cache-Hit", "false")
    )
    
    return response

class HealthChecker:
    async def check_health(self) -> dict:
        checks = {
            "api": "healthy",
            "database": await self._check_db(),
            "redis": await self._check_redis(),
            "google_file_search": await self._check_file_search(),
            "worker_heartbeats": await self._check_workers(),
            "queue_depth": await self._get_queue_depth(),
            "emergency_stop": not os.path.exists("./alerts/EMERGENCY_STOP.flag")
        }
        
        overall = "healthy" if all(
            v == "healthy" for k, v in checks.items() 
            if k not in ['queue_depth', 'emergency_stop']
        ) else "degraded"
        
        return {
            "status": overall,
            "checks": checks,
            "metrics": {
                "hit_rate": await self._calculate_hit_rate(),
                "avg_confidence": await self._calculate_avg_confidence(),
                "entries_total": await self._count_entries(),
                "entries_by_domain": await self._count_by_domain()
            }
        }
```

### 12.7 Pre-build requirements

**Environment variables** (`/.env`):
```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_API_KEY=your-gemini-key
FILE_SEARCH_STORE_ID=your-store-id

# Database
DATABASE_URL=postgresql://user:pass@localhost/kbpro
REDIS_URL=redis://localhost:6379

# Optional: Fallback services
ANTHROPIC_API_KEY=for-claude-haiku-fallback
QDRANT_URL=http://localhost:6333

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Security
SECRET_KEY=generate-with-openssl-rand-hex-32
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**Dependencies** (`requirements.txt`):
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
asyncpg==0.29.0
redis[hiredis]==5.0.1
google-generativeai==0.3.0
google-cloud-storage==2.10.0
anthropic==0.7.0  # Fallback
qdrant-client==1.7.0  # Fallback
prometheus-client==0.19.0
structlog==23.2.0
pybreaker==1.0.1
python-multipart==0.0.6
httpx==0.25.2
pgvector==0.2.4
numpy==1.24.3
scikit-learn==1.3.2  # For semantic dedup
```

### 12.8 Testing infrastructure

```python
# tests/test_quality.py
import pytest
from pathlib import Path
import yaml

class TestKBQuality:
    @pytest.fixture
    def golden_dataset(self):
        """Load golden Q&A pairs for regression testing"""
        with open("tests/golden.yaml") as f:
            return yaml.safe_load(f)
    
    @pytest.mark.parametrize("test_case", golden_dataset)
    async def test_golden_answers(self, test_case, client):
        """Ensure answers remain consistent"""
        response = await client.post("/ask", json={
            "question": test_case["question"],
            "software_version": test_case.get("version")
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Check confidence threshold
        if "min_confidence" in test_case:
            assert data["confidence"] >= test_case["min_confidence"]
        
        # Check required content
        if "must_contain" in test_case:
            for phrase in test_case["must_contain"]:
                assert phrase.lower() in data["answer"].lower()
        
        # Check sources
        if "required_sources" in test_case:
            for source in test_case["required_sources"]:
                assert any(source in s for s in data["sources"])

# tests/test_research.py
class TestResearchAgent:
    async def test_no_hallucination(self):
        """Verify research agent only uses official sources"""
        research_agent = ResearchAgent()
        
        # Test with question that has no official answer
        result = await research_agent.research(
            "What is the meaning of life in PostgreSQL?"
        )
        
        assert result == "Insufficient official information – discard this queue entry"
    
    async def test_version_extraction(self):
        """Verify version metadata is extracted correctly"""
        entry = await research_agent.research(
            "What is the default max_connections in PostgreSQL 16?"
        )
        
        assert "**Software Version**: 16" in entry
        assert "**Valid Until**:" in entry

# tests/test_performance.py
import asyncio
from locust import HttpUser, task, between

class KBProUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(80)
    def ask_cached_question(self):
        """80% of traffic: questions likely cached"""
        self.client.post("/ask", json={
            "question": "What is the default max_connections in PostgreSQL?"
        })
    
    @task(15)
    def ask_new_question(self):
        """15% of traffic: new questions"""
        self.client.post("/ask", json={
            "question": f"How to configure setting_{random.randint(1,1000)} in PostgreSQL?"
        })
    
    @task(5)
    def ask_batch(self):
        """5% of traffic: batch requests"""
        questions = [f"Question {i}" for i in range(10)]
        self.client.post("/ask-batch", json={
            "questions": questions,
            "dedupe": True
        })
```

### 12.9 Deployment configuration

#### 12.9.1 Local development (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://kbpro:password@postgres:5432/kbpro
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./kb_files:/app/kb_files:ro  # Production KB read-only
      - ./kb_staging:/app/kb_staging  # Staging writable
      - ./logs:/app/logs
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build: .
    command: python -m app.worker
    environment:
      - DATABASE_URL=postgresql://kbpro:password@postgres:5432/kbpro
      - REDIS_URL=redis://redis:6379
      - WORKER_ID=${HOSTNAME}
    depends_on:
      - postgres
      - redis
    volumes:
      - ./kb_staging:/app/kb_staging
      - ./alerts:/app/alerts
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=kbpro
      - POSTGRES_USER=kbpro
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kbpro"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    volumes:
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

#### 12.9.2 Railway deployment (recommended for production)

**Railway-specific files:**

```dockerfile
# Dockerfile (Railway will use this)
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE ${PORT:-8000}

# Start command (Railway will override for workers)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
```

```json
// railway.json (optional - Railway auto-detects, but this helps)
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

```toml
# Procfile (for worker service)
worker: python -m app.worker
```

**Railway deployment steps:**

1. **Create Railway account** (railway.app, GitHub OAuth)

2. **Create new project** → "Deploy from GitHub repo"

3. **Add PostgreSQL service:**
   - Click "+ New" → "Database" → "Add PostgreSQL"
   - Railway provides `DATABASE_URL` automatically
   - Enable pgvector: Railway dashboard → PostgreSQL → Extensions → Enable `vector`

4. **Add Redis service:**
   - Click "+ New" → "Database" → "Add Redis"
   - Railway provides `REDIS_URL` automatically

5. **Deploy API service:**
   - Click "+ New" → "GitHub Repo" → Select your repo
   - Railway auto-detects Dockerfile
   - Set environment variables:
     ```
     DATABASE_URL=${{Postgres.DATABASE_URL}}
     REDIS_URL=${{Redis.REDIS_URL}}
     GOOGLE_API_KEY=your-key
     FILE_SEARCH_STORE_ID=your-store-id
     PORT=8000
     ```
   - Railway auto-deploys on git push

6. **Deploy Worker service:**
   - Click "+ New" → "GitHub Repo" → Select same repo
   - Override start command: `python -m app.worker`
   - Share same environment variables (Railway does this automatically)

7. **Set up volumes** (for KB files):
   - Railway doesn't support persistent volumes in free tier
   - **Solution**: Use Railway's "Volume" service or store KB files in PostgreSQL as JSONB
   - **Alternative**: Use GitHub as source of truth, sync on deploy

**Railway-specific considerations:**

- **KB file storage**: Since Railway doesn't have persistent volumes in free tier, consider:
  - Option A: Store KB entries in PostgreSQL as JSONB (adds complexity)
  - Option B: Use GitHub as source of truth, sync on deploy via startup script
  - Option C: Use Railway Volume service (paid feature)

- **Environment variables**: Railway automatically shares variables between services in same project

- **Scaling**: Railway dashboard → Service → Settings → Resources (upgrade as needed)

- **Monitoring**: Railway provides built-in logs, metrics, and alerts

- **Custom domain**: Railway dashboard → Service → Settings → Generate Domain (free) or add custom domain

**Cost estimate for Railway:**
- Free tier: $5 credit/month
- PostgreSQL (1GB): $5/month
- Redis (100MB): $3/month  
- API service: ~$2-5/month (usage-based)
- Worker service: ~$2-5/month (usage-based)
- **Total**: ~$12-18/month after free credit

### 12.10 Operational procedures

```python
# tools/operations.py
"""Production operational tools"""

class KBOperations:
    """Daily operational tasks"""
    
    async def promote_staging_to_production(self, dry_run=True):
        """Promote reviewed staging entries"""
        staging_files = Path("./kb_staging").glob("*-pending.md")
        
        for staging_file in staging_files:
            domain = staging_file.stem.replace("-pending", "")
            prod_file = Path(f"./kb_files/{domain}.md")
            
            # Parse staging entries
            new_entries = self.parse_entries(staging_file)
            
            for entry in new_entries:
                # Validate format
                if not self.validate_entry(entry):
                    logger.error(f"Invalid entry: {entry['id']}")
                    continue
                
                # Check for version conflicts
                if self.has_version_conflict(entry, prod_file):
                    # Update older entries' Valid_Until
                    await self.resolve_version_conflict(entry, prod_file)
                
                if not dry_run:
                    # Append to production
                    await self.append_to_production(entry, prod_file)
                    
                    # Update File Search
                    await self.update_file_search(entry)
                    
                    # Track provenance
                    await self.record_provenance(entry)
            
            if not dry_run:
                # Archive staging file
                staging_file.rename(f"./kb_staging/archived/{staging_file.name}")
    
    async def validate_kb_integrity(self):
        """Full KB validation"""
        issues = []
        
        for kb_file in Path("./kb_files").glob("*.md"):
            entries = self.parse_entries(kb_file)
            
            for entry in entries:
                # Check all required fields
                if not all(k in entry for k in self.REQUIRED_FIELDS):
                    issues.append(f"{entry['id']}: Missing required fields")
                
                # Check version consistency
                if entry.get("valid_until") == "latest":
                    # Ensure no newer version exists
                    if self.has_newer_version(entry):
                        issues.append(f"{entry['id']}: Marked latest but newer version exists")
                
                # Check source validity
                for source in entry.get("sources", []):
                    if not await self.is_url_valid(source):
                        issues.append(f"{entry['id']}: Dead source URL: {source}")
        
        return issues
    
    async def emergency_recovery(self):
        """Recover from emergency stop"""
        # Clear emergency flag
        Path("./alerts/EMERGENCY_STOP.flag").unlink(missing_ok=True)
        
        # Reset worker states
        async with get_db() as db:
            await db.execute("""
                UPDATE queue 
                SET status = 'pending', worker_id = NULL 
                WHERE status = 'researching' 
                AND claimed_at < NOW() - INTERVAL '1 hour'
            """)
        
        # Move DLQ items back with increased retry limit
        await db.execute("""
            INSERT INTO queue 
            SELECT *, retry_count + 1 FROM dead_letter_queue 
            WHERE retry_count < 5
        """)
        
        # Restart workers
        await self.restart_workers()

# tools/cli.py
"""CLI for management tasks"""
import click

@click.group()
def cli():
    """KB Pro management CLI"""
    pass

@cli.command()
@click.option('--dry-run/--execute', default=True)
def promote(dry_run):
    """Promote staging to production"""
    ops = KBOperations()
    asyncio.run(ops.promote_staging_to_production(dry_run))

@cli.command()
def validate():
    """Validate KB integrity"""
    ops = KBOperations()
    issues = asyncio.run(ops.validate_kb_integrity())
    if issues:
        for issue in issues:
            click.echo(f"❌ {issue}")
        sys.exit(1)
    else:
        click.echo("✅ KB validation passed")

@cli.command()
def recover():
    """Emergency recovery"""
    if click.confirm("This will clear emergency stops and reset stuck tasks. Continue?"):
        ops = KBOperations()
        asyncio.run(ops.emergency_recovery())
        click.echo("✅ Recovery complete")
```

### 12.11 Local development setup

```bash
# Development setup script
#!/bin/bash

# Create directory structure
mkdir -p kb_files kb_staging stack_packs locks alerts logs tests/{golden,fixtures}
mkdir -p kb_staging/archived grafana/dashboards

# Initialize local databases
docker run -d --name kbpro-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=kbpro \
  -p 5432:5432 \
  pgvector/pgvector:pg16

docker run -d --name kbpro-redis \
  -p 6379:6379 \
  redis:7-alpine

# Wait for databases
sleep 5

# Run migrations
python -m alembic upgrade head

# Seed with sample data
python tools/seed_kb.py \
  --entries 100 \
  --domains "postgresql,nextjs,fastapi,docker,kubernetes"

# Create evaluation golden dataset
cat > tests/golden.yaml << EOF
- question: "What is the default max_connections in PostgreSQL 16?"
  min_confidence: 0.95
  must_contain: ["100"]
  required_sources: ["postgresql.org"]

- question: "How to use React Server Components in Next.js 14?"
  min_confidence: 0.90
  software_version: "14"
  must_contain: ["app directory", "use client"]
EOF

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run initial validation
python -m tools.cli validate

echo "✅ Development environment ready"
echo "Start API: uvicorn app.main:app --reload"
echo "Start worker: python -m app.worker"
echo "Run tests: pytest"
```

---

## 13) Final architecture summary

### What we've built (conceptually)

A **professional-grade, self-expanding verified developer knowledge base** that:

1. **Maintains truth integrity**: Staging/production separation, version discipline, confidence decay
2. **Scales intelligently**: Semantic deduplication, batch processing, response caching
3. **Self-heals**: Circuit breakers, fallback chains, emergency stops
4. **Tracks everything**: Provenance, costs, metrics, worker health
5. **Remains compatible**: Drop-in replacement for AgentsKB with enhancements

### Key differentiators from original AgentsKB

| Feature | AgentsKB | Our System | Impact |
|---------|----------|------------|--------|
| Versioning | None | Software Version + Valid Until | Prevents conflicting "truths" |
| Staging | Direct write | Staging → Review → Production | Quality control |
| Caching | Unknown | Redis with TTL | 10-100x performance |
| Deduplication | None | Semantic embeddings | Prevents duplicate research |
| Fallbacks | None | 3-tier fallback chain | Resilient to outages |
| Monitoring | Basic | Prometheus + Grafana | Full observability |
| Batch processing | Basic | Enhanced with dedup | Greater cost savings |
| Emergency stop | None | Auto-pause on anomalies | Prevents KB poisoning |

### Critical success factors

1. **Google API access**: Must have Gemini + File Search API keys
2. **PostgreSQL with pgvector**: For queue and semantic operations  
3. **Redis**: For caching layer
4. **Domain expertise**: Initial KB seeding requires manual curation
5. **Review discipline**: Staging entries must be reviewed before promotion

### Implementation order

1. **Database first**: Set up PostgreSQL + Redis
2. **Core API**: FastAPI with `/ask` endpoint
3. **Retrieval**: Google File Search integration
4. **Worker**: Basic research without all features
5. **Enhancements**: Add caching, dedup, monitoring one by one
6. **Testing**: Golden dataset validation
7. **Deployment**: Docker Compose for production

### Estimated complexity

- **Lines of code**: ~3,000-4,000 (not including tests)
- **External dependencies**: 15-20 Python packages
- **Infrastructure**: 2 databases + 2-3 cloud services
- **Initial KB size**: 100+ manually curated entries recommended
- **Maintenance**: 2-4 hours/week for staging review

---

## 14) Hosting platform comparison (low-cost, easy deployment)

### 14.1 Requirements summary

**What you need:**
- PostgreSQL with pgvector extension (for semantic search)
- Redis (for caching)
- FastAPI application (Docker or direct Python)
- Worker processes (background jobs)
- Easy scaling (auto or manual)
- Low/no cost for personal use
- Simple deployment process

### 14.2 Platform comparison matrix

| Platform | Free Tier | PostgreSQL | Redis | Docker | Ease | Best For | Cost After Free |
|----------|-----------|------------|-------|--------|------|----------|-----------------|
| **Railway** | $5 credit/mo | ✅ Managed | ✅ Managed | ✅ Native | ⭐⭐⭐⭐⭐ | **EASIEST** | ~$5-10/mo |
| **Render** | Limited | ✅ Managed | ✅ Managed | ✅ Native | ⭐⭐⭐⭐ | Good balance | ~$7-15/mo |
| **Fly.io** | Generous | ✅ Self-host | ✅ Self-host | ✅ Native | ⭐⭐⭐ | Full control | ~$0-5/mo |
| **Supabase** | 500MB DB | ✅ Managed | ❌ (use Upstash) | ⚠️ Limited | ⭐⭐⭐⭐ | DB-focused | ~$0-5/mo |
| **Neon** | 0.5GB DB | ✅ Serverless | ❌ (use Upstash) | ❌ | ⭐⭐⭐ | DB-only | ~$0-5/mo |
| **Northflank** | Limited | ✅ Managed | ✅ Managed | ✅ Native | ⭐⭐⭐⭐ | Similar to Railway | ~$10-20/mo |
| **Cloud Run** | 2M requests | ❌ (use Cloud SQL) | ❌ (use Memorystore) | ✅ Native | ⭐⭐ | Google ecosystem | ~$5-15/mo |
| **Netlify** | ❌ | ❌ | ❌ | ⚠️ Functions only | ⭐ | Not suitable | N/A |

### 14.3 Detailed platform analysis

#### 🏆 **RECOMMENDED: Railway.app**

**Why it's best for you:**
- ✅ **Easiest deployment**: Connect GitHub → Auto-deploy
- ✅ **$5/month credit** (covers small usage)
- ✅ **Managed PostgreSQL** with pgvector support
- ✅ **Managed Redis** included
- ✅ **Docker-native** (just push Dockerfile)
- ✅ **One-click scaling** (vertical only, but easy)
- ✅ **Built-in monitoring** (logs, metrics)
- ✅ **No credit card required** for free tier

**Pricing:**
- Free: $5 credit/month (enough for ~100MB DB + small API)
- After free: ~$5-10/month for typical usage
- PostgreSQL: $5/month (1GB)
- Redis: $3/month (100MB)
- API: $0.000463/GB-hour (very cheap)

**Deployment:**
```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Initialize project
railway init

# 4. Add services
railway add postgresql
railway add redis

# 5. Deploy
railway up
```

**Verdict**: ⭐⭐⭐⭐⭐ **Best choice for "park and use"**

---

#### 🥈 **ALTERNATIVE: Render.com**

**Why it's good:**
- ✅ **Free tier** (with limitations)
- ✅ **Managed PostgreSQL** (pgvector via extension)
- ✅ **Managed Redis** available
- ✅ **Docker support**
- ✅ **Auto-deploy from GitHub**
- ⚠️ **Free tier spins down** after 15min inactivity (wake-up delay)

**Pricing:**
- Free: PostgreSQL (90 days), Web services spin down
- Paid: $7/month (PostgreSQL), $7/month (Redis), $7/month (Web)
- **Total**: ~$21/month for always-on

**Verdict**: ⭐⭐⭐⭐ Good if you don't mind wake-up delays

---

#### 🥉 **BUDGET OPTION: Fly.io**

**Why it's interesting:**
- ✅ **Generous free tier** (3 shared VMs)
- ✅ **PostgreSQL** (self-managed or managed)
- ✅ **Redis** (self-managed)
- ✅ **Docker-native**
- ✅ **Global edge deployment**
- ⚠️ **More setup required** (fly.toml config)

**Pricing:**
- Free: 3 shared-cpu VMs (256MB RAM each)
- PostgreSQL: $1.94/month (1GB) or self-host on VM
- Redis: Self-host on VM (free) or $3/month managed
- **Total**: ~$0-5/month if self-hosting DBs

**Deployment:**
```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Login
fly auth login

# 3. Launch app
fly launch

# 4. Add PostgreSQL
fly postgres create

# 5. Deploy
fly deploy
```

**Verdict**: ⭐⭐⭐ Best for maximum cost savings, more technical

---

#### **DATABASE-ONLY: Supabase + Separate API Host**

**Why consider:**
- ✅ **500MB PostgreSQL free** (with pgvector)
- ✅ **Excellent PostgreSQL features**
- ✅ **Auto-backups**
- ⚠️ **No Redis** (use Upstash free tier)
- ⚠️ **API hosting separate** (Railway/Render for API)

**Pricing:**
- Supabase: Free (500MB) or $25/month (8GB)
- Upstash Redis: Free (10K commands/day)
- API Host: Railway/Render (~$5-10/month)
- **Total**: ~$5-10/month (free tier) or ~$30/month (paid)

**Verdict**: ⭐⭐⭐⭐ Best if you want best-in-class PostgreSQL

---

#### **NOT RECOMMENDED: Cloud Run**

**Why skip:**
- ⚠️ **Complex setup** (Cloud SQL, Memorystore, IAM)
- ⚠️ **Google Cloud learning curve**
- ⚠️ **Free tier limited** (2M requests, then pay)
- ⚠️ **Cold starts** (serverless)
- ✅ **Good if already in Google ecosystem**

**Verdict**: ⭐⭐ Only if you're already using GCP

---

#### **NOT SUITABLE: Netlify**

**Why skip:**
- ❌ **No PostgreSQL** (serverless functions only)
- ❌ **No Redis** (ephemeral storage only)
- ❌ **No worker processes**
- ✅ **Great for static sites, not APIs**

**Verdict**: ⭐ Not suitable for this use case

---

### 14.4 Recommended architecture by platform

#### **Option A: Railway (Easiest) - RECOMMENDED**

```
Railway Project
├── PostgreSQL Service (managed, $5/mo)
│   └── pgvector extension enabled
├── Redis Service (managed, $3/mo)
├── API Service (Docker, ~$2-5/mo)
│   └── FastAPI app
└── Worker Service (Docker, ~$2-5/mo)
    └── Research worker

Total: ~$12-18/month after free credit
```

**Deployment steps:**
1. Create Railway account (GitHub OAuth)
2. New Project → Add PostgreSQL → Add Redis
3. Connect GitHub repo
4. Railway auto-detects Dockerfile
5. Set environment variables
6. Deploy → Done

---

#### **Option B: Fly.io (Budget) - Most Cost-Effective**

```
Fly.io Apps
├── PostgreSQL VM (self-hosted, free tier)
│   └── pgvector extension
├── Redis VM (self-hosted, free tier)
├── API App (Docker, free tier)
└── Worker App (Docker, free tier)

Total: ~$0-5/month (if within free tier limits)
```

**Deployment steps:**
1. Install flyctl CLI
2. `fly launch` (creates fly.toml)
3. `fly postgres create` (or self-host)
4. `fly redis create` (or self-host)
5. `fly deploy`

---

#### **Option C: Supabase + Railway (Best DB)**

```
Supabase
└── PostgreSQL (managed, free tier)
    └── pgvector extension

Railway
├── Redis (managed, $3/mo)
├── API Service (Docker, ~$5/mo)
└── Worker Service (Docker, ~$5/mo)

Total: ~$13/month
```

---

### 14.5 Final recommendation

**For your use case (personal + trusted friends, no monetization yet):**

🏆 **Railway.app** is the clear winner because:

1. **Easiest to deploy**: Literally connect GitHub and it works
2. **$5/month credit**: Covers small usage for free
3. **Managed everything**: No database administration
4. **Docker-native**: Your docker-compose.yml works as-is
5. **Scales easily**: Click a button to upgrade
6. **Good docs**: Excellent tutorials and support

**Expected monthly cost:**
- **Months 1-3**: $0 (free credit covers it)
- **Months 4+**: ~$12-18/month (PostgreSQL + Redis + API + Worker)
- **If you outgrow**: Easy to scale up or migrate

**Migration path later:**
- If you need to scale: Railway scales vertically easily
- If you need to cut costs: Migrate to Fly.io (more setup)
- If you need enterprise: Migrate to AWS/GCP (more complex)

---

### 14.6 Railway deployment guide (quick start)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login (opens browser)
railway login

# 3. Create new project
railway init

# 4. Add PostgreSQL (with pgvector)
railway add postgresql
# Note: Enable pgvector in Railway dashboard → Extensions

# 5. Add Redis
railway add redis

# 6. Set environment variables
railway variables set DATABASE_URL=${{Postgres.DATABASE_URL}}
railway variables set REDIS_URL=${{Redis.REDIS_URL}}
railway variables set GOOGLE_API_KEY=your-key
railway variables set FILE_SEARCH_STORE_ID=your-store-id

# 7. Deploy (from your repo root)
railway up
# Or connect GitHub for auto-deploy

# 8. View logs
railway logs

# 9. Open in browser
railway open
```

**That's it!** Railway handles:
- ✅ SSL certificates
- ✅ Domain assignment (railway.app subdomain)
- ✅ Health checks
- ✅ Auto-restart on crashes
- ✅ Log aggregation
- ✅ Metrics dashboard

---

## 15) Decision required: System name

Before implementation can begin, select final name from:

1. **GroundedKB** - Emphasizes factual grounding
2. **VerifiedKB** - Emphasizes verification
3. **TruthbaseAI** - "Database of truth"
4. **FactForge** - "Forging facts"
5. **KnowBase Pro** - Professional knowledge
6. **Custom name**: _______________

Once named, update all references throughout codebase.

---

---

## 16) Knowledge Harvester (Proactive KB Expansion)

**Status**: Implemented (Phase 2 enhancement)

The Knowledge Harvester provides **proactive** KB expansion by continuously monitoring official documentation sources, detecting changes, and generating KB entries for human review.

### 16.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE HARVESTER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Source     │    │   Change     │    │   Entry      │      │
│  │   Registry   │───▶│   Detector   │───▶│   Generator  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Official    │    │   Content    │    │   Staging    │      │
│  │  Doc URLs    │    │   Hashes     │    │   KB Files   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Human Review   │
                    │   (git diff)     │
                    └──────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   Production KB  │
                    └──────────────────┘
```

### 16.2 Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Source Registry | `app/harvester/registry.py` | Curated list of official doc URLs |
| Change Detector | `app/harvester/detector.py` | Monitors sources, detects updates via content hashing |
| Entry Generator | `app/harvester/generator.py` | Uses Gemini to extract Q&A from changed content |
| Harvester CLI | `tools/harvest.py` | Command-line interface |
| Source Config | `sources.yaml` | YAML file defining domains and sources |

### 16.3 Registered Domains (Default)

| Domain | Sources | Check Interval |
|--------|---------|----------------|
| postgresql | Release notes, Runtime config | daily/weekly |
| nextjs | Docs, GitHub releases (RSS) | daily/hourly |
| python | What's New | weekly |
| fastapi | Release notes | daily |
| docker | Engine release notes | weekly |
| typescript | Release notes | weekly |
| react | Blog | daily |
| kubernetes | Release notes | weekly |
| aws | What's New | daily |
| rust | Blog | weekly |

### 16.4 CLI Commands

```bash
# List all registered sources
python -m tools.harvest --list

# Check all sources for changes and generate entries
python -m tools.harvest --check

# Check specific domain only
python -m tools.harvest --domain python

# Force check (ignore intervals)
python -m tools.harvest --force --check

# Add a new domain
python -m tools.harvest --add-domain "golang:Go Language"

# Add a source to existing domain
python -m tools.harvest --add-source golang https://go.dev/blog release_notes
```

### 16.5 Workflow

1. **Schedule**: Run `--check` on a schedule (cron, GitHub Actions, or manual)
2. **Detect**: System fetches each source URL, computes content hash, compares to stored hash
3. **Extract**: For changed sources, Gemini analyzes content and extracts Q&A pairs
4. **Deduplicate**: Skip entries that already exist in production KB
5. **Stage**: Write unique entries to `./kb_staging/{domain}-harvested-{timestamp}.md`
6. **Review**: Human reviews staged entries via `git diff`
7. **Promote**: Run `python -m tools.promote_staging` to move to production

### 16.6 Cost Estimate

| Operation | Per Domain/Week | Notes |
|-----------|-----------------|-------|
| Fetch source pages | Free | HTTP requests |
| Gemini analysis | ~$0.05 | Using gemini-1.5-flash for bulk |
| Embedding checks | ~$0.01 | For deduplication |
| **Total (10 domains)** | **~$2.50/month** | Scales linearly |

### 16.7 Difference from Reactive Research

| Aspect | Reactive (Research Worker) | Proactive (Harvester) |
|--------|---------------------------|----------------------|
| Trigger | User query misses | Scheduled scan |
| Scope | Single question | Entire doc pages |
| Speed | On-demand | Background |
| Coverage | Demand-driven | Comprehensive |

Both approaches write to staging for human review.

---

## 17) OpenRouter Integration (Multi-Provider LLM Access)

**Status**: Implemented (Phase 2 enhancement)

OpenRouter provides access to **300+ AI models** via a single API, enabling:
- Automatic fallbacks when primary provider is unavailable
- Cost optimization through intelligent routing
- Privacy controls (Zero Data Retention, data collection policies)
- Access to Claude, GPT-4, Llama, Mistral, and more

### 17.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM PROVIDER ABSTRACTION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐       ┌──────────────────┐               │
│  │                  │       │                  │               │
│  │  GeminiClient    │       │ OpenRouterClient │               │
│  │  (Primary)       │       │ (300+ Models)    │               │
│  │                  │       │                  │               │
│  └────────┬─────────┘       └────────┬─────────┘               │
│           │                          │                          │
│           └──────────┬───────────────┘                          │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │               │                                  │
│              │  LLMRouter    │                                  │
│              │  (Strategy)   │                                  │
│              │               │                                  │
│              └───────────────┘                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 17.2 Routing Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `primary_only` | Use Gemini exclusively | Maximum control |
| `fallback` | Gemini → OpenRouter on failure | **Recommended** |
| `openrouter_only` | Use OpenRouter exclusively | Access to Claude/GPT-4 |
| `cost_optimized` | Route to cheapest option | Budget-conscious |
| `throughput` | Route to fastest provider | Research tasks |
| `privacy_first` | ZDR endpoints only | Sensitive queries |

### 17.3 Provider Preferences

OpenRouter supports granular routing control:

```python
provider = {
    "order": ["anthropic", "openai"],     # Provider priority
    "only": ["anthropic", "azure"],       # Restrict to these
    "ignore": ["deepinfra"],              # Skip these
    "allow_fallbacks": True,              # Enable fallback chain
    "data_collection": "deny",            # Privacy policy
    "zdr": True,                          # Zero Data Retention
    "sort": "throughput",                 # price, throughput, latency
    "quantizations": ["fp8", "fp16"],     # Hardware requirements
    "max_price": {
        "prompt": 1.0,                    # Max $/M prompt tokens
        "completion": 2.0                 # Max $/M completion tokens
    }
}
```

### 17.4 Model Shortcuts

| Shortcut | Effect |
|----------|--------|
| `model:nitro` | Sort by throughput (fastest) |
| `model:floor` | Sort by price (cheapest) |
| `model:free` | Use free tier only |

Example: `meta-llama/llama-3.1-70b-instruct:nitro`

### 17.5 Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `OpenRouterClient` | `app/services/openrouter.py` | Direct API client |
| `LLMRouter` | `app/services/llm_router.py` | Strategy-based routing |
| Deep Dive | `docs/deep-dive/openrouter-integration.md` | Full documentation |

### 17.6 Environment Configuration

```env
# OpenRouter API key
OPENROUTER_API_KEY=sk-or-v1-...

# Default model
OPENROUTER_DEFAULT_MODEL=anthropic/claude-3.5-sonnet

# Routing preferences
OPENROUTER_SORT=price
OPENROUTER_DATA_COLLECTION=deny
OPENROUTER_ZDR=false

# Cost controls
OPENROUTER_MAX_PRICE_PROMPT=5.0
OPENROUTER_MAX_PRICE_COMPLETION=15.0

# LLM routing strategy
LLM_ROUTING_STRATEGY=fallback
```

### 17.6.1 Ollama Cloud Integration (API Contracts)

**Status**: Implemented (Phase 2 enhancement)

Ollama Cloud can be used as a **remote Ollama host** with the *same* API surface as local Ollama.

- **Cloud API base URL**: `https://ollama.com/api` (same endpoints as local `/api`)  
  Source: https://docs.ollama.com/api/introduction
- **Authentication** (ollama.com): set `OLLAMA_API_KEY` and send `Authorization: Bearer $OLLAMA_API_KEY`  
  Source: https://docs.ollama.com/api/authentication
- **List models**: `GET /api/tags` (cloud: `https://ollama.com/api/tags`, local: `http://localhost:11434/api/tags`)  
  Source: https://docs.ollama.com/api/tags
- **Chat**: `POST /api/chat`  
  Source: https://docs.ollama.com/api/chat
- **Generate**: `POST /api/generate`  
  Source: https://docs.ollama.com/api/generate
- **Embeddings**: `POST /api/embed`  
  Source: https://docs.ollama.com/api/embed
- **Streaming**: endpoints that stream return **newline-delimited JSON** (`application/x-ndjson`)  
  Source: https://docs.ollama.com/api/streaming
- **Errors**: standard JSON error body `{ "error": "..." }` (and streaming errors are NDJSON objects)  
  Source: https://docs.ollama.com/api/errors

#### 17.6.1.1 Cloud models vs non-cloud models

Cloud models are those marked **cloud** in the Ollama model library.

- Cloud model library filter: https://ollama.com/search?c=cloud&o=newest
- Programmatic model availability for a given Ollama host (local or cloud) is determined by `GET /api/tags`  
  Source: https://docs.ollama.com/api/tags

### 17.6.2 Ollama Cloud Web Search + Web Fetch (RTD)

Ollama provides **web search** and **web fetch** as REST APIs:

- **Web search**: `POST https://ollama.com/api/web_search` with `{ "query": "...", "max_results": 5 }`  
- **Web fetch**: `POST https://ollama.com/api/web_fetch` with `{ "url": "https://..." }`

Source: https://docs.ollama.com/capabilities/web-search

### 17.6.3 Tool Calling (Function Calling)

Ollama supports tool calling via `POST /api/chat` by providing a `tools` array, and models may return `tool_calls` to be executed and fed back as `role=tool` messages.

Source: https://docs.ollama.com/capabilities/tool-calling

### 17.10 Admin-Only Model Policy (NOT User-Facing)

**Critical rule**: end users do not select models. All provider/model selection is controlled by admin config.

**Default policy (current)**:

- **RTD / grounded general**:
  - Primary: Ollama Cloud `gemini-3-flash-preview` (with alias fallback to `gemini-3-flash` if the preview name changes)
  - Fallback: OpenRouter (admin-selected Gemini 3 Flash model id)
  - Final fallback: Google Gemini direct (admin-selected model name)
  - Cloud model reference: https://ollama.com/search?c=cloud&o=newest
- **Strong reasoning (non-RTD)**:
  - Primary: Ollama Cloud `glm-4.7`
  - Fallback: OpenRouter (admin-selected GLM-4.7 model id)
  - Cloud model reference: https://ollama.com/search?c=cloud&o=newest
- **Final QA pass**:
  - Enabled by default; uses strong reasoning settings to critique and improve non-cached answers before returning

These are configured in `env.example` and loaded by `app/config.py` under `Settings.model_policy`.

### 17.7 Recommended Models

| Task | Model | Reason |
|------|-------|--------|
| KB Queries | `anthropic/claude-3.5-sonnet` | Best accuracy |
| Fast KB | `anthropic/claude-3-haiku` | Speed + quality |
| Research | `anthropic/claude-3.5-sonnet` | Deep reasoning |
| Research Fast | `meta-llama/llama-3.1-70b-instruct:nitro` | Throughput |
| Budget | `meta-llama/llama-3.1-70b-instruct:floor` | Cost |

### 17.8 Cost Tracking

OpenRouter provides **exact cost tracking** via the generation stats endpoint:

```python
# After completion
stats = await client.get_generation_stats(generation_id)
print(f"Cost: ${stats.cost:.4f}")
print(f"Native tokens: {stats.native_prompt_tokens} / {stats.native_completion_tokens}")
print(f"Provider used: {stats.provider}")
```

### 17.9 Value Summary

1. **Reliability**: Automatic fallbacks when Gemini fails
2. **Model Access**: Claude, GPT-4, Llama, Mistral via single API
3. **Cost Control**: Route to cheapest or set max price caps
4. **Privacy**: ZDR and data collection policies
5. **Speed**: Route to highest throughput for research
6. **Transparency**: Exact cost tracking per request

---

---

## 18) Future Directions: Alternative Knowledge Domains (Ideation)

**Status**: Ideation only — NOT a build step

This section explores **alternative applications** of the Verified KB architecture beyond developer documentation. The core value proposition—pre-researched, grounded, self-expanding, human-reviewed knowledge—is domain-agnostic. The architecture could power verified knowledge bases across many industries and use cases.

---

### 18.1 Core Architecture Transferability

What makes this architecture valuable for ANY knowledge domain:

| Capability | Universal Value |
|------------|----------------|
| **Strict grounding** | Answers only from verified sources, not hallucination |
| **Confidence scoring** | Know when to trust vs. escalate |
| **Source attribution** | Full provenance chain |
| **Self-expanding** | Grows with usage |
| **Human review gate** | Quality control before promotion |
| **Versioning** | Knowledge evolves; track it |
| **Lockfiles** | Reproducible answers for compliance |
| **Stack Packs** | Curated bundles for specific contexts |

---

### 18.2 High-Value Domain Candidates

#### 🏛️ **Legal Knowledge Base** ("LegalKB Pro")

**Why it fits:**
- Law is versioned (statutes change, case law evolves)
- Answers must be grounded in exact text (no hallucination = malpractice avoidance)
- Jurisdictional "Stack Packs" (California, Federal, EU GDPR)
- Confidence scoring critical ("consult an attorney" fallback)

**Official sources to harvest:**
- Congress.gov (federal statutes)
- State legislature websites
- Court opinion databases (CourtListener)
- CFR (Code of Federal Regulations)

**Unique features needed:**
- Citation format enforcement (Bluebook)
- Effective date tracking (when did this law take effect?)
- Supersession chains (which statute replaced which)

**Market:** Law firms, legal tech, compliance departments, paralegals

---

#### ⚕️ **Medical/Clinical Knowledge Base** ("ClinicalKB Pro")

**Why it fits:**
- Hallucination = patient harm
- Drug interactions, dosing, contraindications require exactness
- Evidence-based medicine demands source attribution
- Guidelines change frequently (COVID protocols changed monthly)

**Official sources to harvest:**
- FDA drug labels (DailyMed)
- NIH PubMed/MEDLINE
- CDC guidelines
- WHO protocols
- UpToDate (if licensed)

**Unique features needed:**
- Drug-drug interaction checking
- Dosing calculators
- Contraindication flags
- Emergency escalation ("call poison control")

**Market:** Hospitals, clinics, telemedicine, nursing education

---

#### 💰 **Financial/Accounting Knowledge Base** ("ComplianceKB Pro")

**Why it fits:**
- Tax codes are versioned by year
- GAAP/IFRS rules require exact citation
- SEC regulations change quarterly
- Audit trail requirements match lockfile architecture

**Official sources to harvest:**
- IRS.gov (tax code, revenue rulings)
- FASB.org (accounting standards)
- SEC.gov (regulations, releases)
- PCAOB (audit standards)

**Unique features needed:**
- Tax year versioning (2023 vs 2024 rules)
- Jurisdiction stacking (Federal + State + Local)
- Effective date enforcement

**Market:** Accounting firms, CFOs, tax preparers, audit teams

---

#### 🏗️ **Engineering Standards Knowledge Base** ("CodeKB Pro")

**Why it fits:**
- Building codes are versioned (IBC 2018 vs 2021)
- Safety standards require exact compliance
- Cross-referencing (OSHA + NFPA + local amendments)
- Liability = grounding is essential

**Official sources to harvest:**
- ICC (International Code Council)
- NFPA codes
- OSHA regulations
- ASTM standards
- IEEE standards

**Unique features needed:**
- Code adoption tracking (which jurisdictions use which version)
- Amendment layering (local amendments on top of base codes)
- Cross-reference linking

**Market:** Architects, engineers, construction firms, inspectors

---

#### 🎓 **Academic Subject Knowledge Base** ("StudyKB Pro")

**Why it fits:**
- Textbook knowledge is stable and citable
- Test prep requires exact answers (SAT, GRE, MCAT, bar exam)
- Concept relationships map to Stack Packs
- Confidence scores help students know what they know

**Official sources to harvest:**
- OpenStax textbooks
- Khan Academy transcripts
- AP/IB curriculum guides
- University course syllabi (public)
- Wikipedia (with verification layer)

**Unique features needed:**
- Difficulty leveling (intro vs advanced)
- Prerequisite chains
- Practice problem generation
- Spaced repetition integration

**Market:** Students, tutors, test prep companies, homeschoolers

---

#### 🏢 **Enterprise Internal Knowledge Base** ("InternalKB Pro")

**Why it fits:**
- Institutional memory is the #1 lost asset
- Policies change; versioning is critical
- Onboarding = "ask the KB, not Bob who left"
- Compliance requires audit trails

**Official sources to harvest:**
- Internal wikis (Confluence, Notion)
- Policy documents (HR, IT, Legal)
- SOPs (Standard Operating Procedures)
- Slack/Teams archives (with permission)

**Unique features needed:**
- Access control (department-level permissions)
- Approval workflows (HR must approve HR entries)
- Integration with HRIS/IT systems
- Expiration dates ("this policy is reviewed annually")

**Market:** Every enterprise with >100 employees

---

#### 🍳 **Culinary Knowledge Base** ("ChefKB Pro")

**Why it fits:**
- Techniques are precise (Maillard reaction temperature)
- Substitutions need confidence ("you can use X instead of Y")
- Cultural context matters (authentic vs fusion)
- Dietary restrictions require exactness (allergen safety)

**Official sources to harvest:**
- USDA FoodData Central
- Serious Eats (technique-focused)
- America's Test Kitchen (science-backed)
- Culinary Institute of America curriculum
- FDA food safety guidelines

**Unique features needed:**
- Unit conversion
- Substitution chains
- Dietary filtering (vegan, gluten-free, halal, kosher)
- Scaling calculations

**Market:** Home cooks, culinary students, food bloggers, restaurants

---

#### 🎮 **Gaming Rules Knowledge Base** ("RulesKB Pro")

**Why it fits:**
- Board game rules are exact (disputes need citations)
- Video game mechanics are versioned (patch notes)
- Strategy knowledge can be tiered (beginner/advanced)
- Community has strong curation culture

**Official sources to harvest:**
- Official rulebooks (PDF parsing)
- Patch notes (game developers)
- Strategy guides (official)
- Tournament rules (esports orgs)

**Unique features needed:**
- Edition tracking (D&D 5e vs 5.5e)
- Errata overlays
- House rules flagging
- Quick-reference card generation

**Market:** Tabletop gamers, esports players, game stores, streamers

---

#### 🌱 **Gardening/Agriculture Knowledge Base** ("GrowKB Pro")

**Why it fits:**
- Plant care is zone-specific (USDA zones)
- Timing is critical (when to plant, prune, harvest)
- Pest/disease identification needs accuracy
- Organic certification rules are exact

**Official sources to harvest:**
- USDA Plant Hardiness Zone Map
- University extension services (land-grant universities)
- Royal Horticultural Society
- Organic certification standards (USDA NOP)

**Unique features needed:**
- Zone filtering
- Seasonal calendars
- Companion planting matrices
- Pest/disease identification

**Market:** Gardeners, farmers, landscapers, nurseries

---

#### ✈️ **Travel/Visa Knowledge Base** ("TravelKB Pro")

**Why it fits:**
- Visa requirements are country-pair specific and change frequently
- Entry requirements (COVID, vaccines) were chaos
- Customs limits need exactness
- Consular sources are authoritative

**Official sources to harvest:**
- State.gov (US visa info)
- IATA Travel Centre
- Embassy websites
- Customs declarations (CBP, HMRC)

**Unique features needed:**
- Country-pair matrices
- Passport validity rules
- Entry requirement timelines
- Currency/customs limits

**Market:** Travelers, travel agents, immigration attorneys, expats

---

#### 🏠 **Home Improvement Knowledge Base** ("DIYKB Pro")

**Why it fits:**
- Building codes apply to DIY
- Techniques need precision (electrical safety)
- Permits and inspections are local
- Material specifications are exact

**Official sources to harvest:**
- Home Depot/Lowe's product specs
- Building codes (residential sections)
- EPA guidelines (lead, asbestos)
- Manufacturer installation guides

**Unique features needed:**
- Permit requirement flagging
- Safety warnings
- Tool requirements
- Cost estimation

**Market:** Homeowners, DIYers, handymen, real estate investors

---

#### 🍷 **Wine/Spirits Knowledge Base** ("SommelierKB Pro")

**Why it fits:**
- Appellations have legal definitions
- Vintage matters (2015 Bordeaux vs 2016)
- Pairing rules are learnable
- Certification prep (WSET, Court of Master Sommeliers)

**Official sources to harvest:**
- TTB (Alcohol and Tobacco Tax and Trade Bureau)
- Appellation authorities (INAO, DOC, AVA)
- Producer technical sheets
- WSET curriculum

**Unique features needed:**
- Vintage ratings
- Food pairing matrices
- Region hierarchies
- Certification prep mode

**Market:** Wine enthusiasts, sommeliers, restaurants, retailers

---

### 18.3 Domain Selection Criteria

When evaluating a new domain, score it against these criteria:

| Criterion | Question | Weight |
|-----------|----------|--------|
| **Source Quality** | Are there authoritative official sources? | High |
| **Hallucination Risk** | Does wrong info cause harm? | High |
| **Version Sensitivity** | Does knowledge change over time? | Medium |
| **Stack Pack Potential** | Are there natural groupings? | Medium |
| **Market Size** | Who would pay for this? | Medium |
| **Harvester Feasibility** | Can official sources be crawled? | Medium |
| **Competition** | Is this already well-served? | Low |

---

### 18.4 Architecture Modifications by Domain

| Domain | Key Modification |
|--------|------------------|
| Legal | Citation format enforcement, jurisdiction stacking |
| Medical | Interaction checking, safety escalation |
| Financial | Tax year versioning, regulatory cross-refs |
| Enterprise | Access control, approval workflows |
| Culinary | Unit conversion, dietary filtering |
| Gaming | Edition tracking, errata overlays |
| Gardening | Zone filtering, seasonal calendars |
| Travel | Country-pair matrices, expiration dates |

---

### 18.5 Potential Product Names by Domain

| Domain | Candidate Names |
|--------|-----------------|
| Developer | GroundedKB, VerifiedKB, DevTruthBase |
| Legal | CaseLaw.ai, StatuteKB, LegalGround |
| Medical | ClinicalGround, MedVerify, EvidenceKB |
| Financial | ComplianceKB, AuditGround, TaxTruth |
| Enterprise | InstitutionalKB, PolicyGround, TeamMemory |
| Culinary | ChefGround, TechniqueKB, RecipeVerify |
| Gaming | RulebookKB, PatchNotes.ai, StrategyGround |
| Gardening | GrowGround, ZoneKB, PlantVerify |
| Travel | VisaGround, EntryKB, TravelVerify |

---

### 18.6 Architectural Approaches: Multiple Repos vs. Single Platform

**CRITICAL CLARIFICATION**: This section explores **two distinct architectural approaches** for expanding beyond developer knowledge. The core purpose remains unchanged: **making less capable models MORE capable by providing quick, actionable, accurate knowledge**.

---

#### Approach A: Multiple Separate Repos/Tools (One Per Domain)

**Concept**: Each domain gets its own **standalone repository** and **separate deployment**.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE A: SEPARATE REPOS               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │                  │  │                  │  │              │ │
│  │  DevKB-Pro       │  │  LegalKB-Pro     │  │  MedKB-Pro   │ │
│  │  Repository      │  │  Repository      │  │  Repository  │ │
│  │                  │  │                  │  │              │ │
│  │  - Full codebase │  │  - Full codebase │  │  - Full      │ │
│  │  - Dev prompts   │  │  - Legal prompts │  │    codebase  │ │
│  │  - Dev sources   │  │  - Legal sources │  │  - Med        │ │
│  │  - Dev KB files  │  │  - Legal KB      │  │    prompts   │ │
│  │  - Own deployment│  │  - Own deployment│  │  - Med KB    │ │
│  │                  │  │                  │  │  - Own       │ │
│  └──────────────────┘  └──────────────────┘  │  deployment │ │
│                                                 │              │ │
│  Shared: Common architecture patterns           │              │ │
│  (copy-paste or git submodule)                  └──────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**How it works:**
- Each repo is **completely independent**
- Shared architecture is **copied** or **submoduled** (not shared runtime)
- Each has its own:
  - Database (separate PostgreSQL instances)
  - KB files directory (`./kb_files/` with domain-specific content)
  - Harvester configuration (domain-specific sources)
  - Prompts (domain-specific system instructions)
  - Deployment (separate Railway.app projects, separate URLs)
- Users install **one tool** (e.g., `DevKB-Pro`) or **multiple tools** separately
- Each tool exposes its own MCP server (e.g., `devkb-mcp`, `legalkb-mcp`)

**Example:**
```bash
# User installs DevKB-Pro
npm install -g @devkb/cli
devkb mcp --api-key=...

# User installs LegalKB-Pro (separate)
npm install -g @legalkb/cli
legalkb mcp --api-key=...

# In Cursor MCP config:
{
  "mcpServers": {
    "devkb": { "command": "devkb", "args": ["mcp"] },
    "legalkb": { "command": "legalkb", "args": ["mcp"] }
  }
}
```

---

#### Approach B: Single Platform with Domain Plugins/Add-ons

**Concept**: One codebase, one deployment, **domain knowledge is "plugged in"** via configuration/data.

```
┌─────────────────────────────────────────────────────────────────┐
│              ARCHITECTURE B: SINGLE PLATFORM + PLUGINS          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │  VerifiedKB Platform (Single Repo)                       │  │
│  │                                                          │  │
│  │  Core Engine (shared runtime):                          │  │
│  │  - Retrieval + Grounding                                │  │
│  │  - Self-Expanding Research                             │  │
│  │  - Human Review Workflow                                │  │
│  │  - Versioning + Lockfiles                               │  │
│  │  - API + MCP Interface                                  │  │
│  │  - Single database (with domain partitioning)           │  │
│  │                                                          │  │
│  │  Domain Plugins (data/configuration):                   │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │  │
│  │  │ DevKB Plugin │ │ LegalKB      │ │ MedKB        │   │  │
│  │  │              │ │ Plugin       │ │ Plugin       │   │  │
│  │  │ - Prompts    │ │ - Prompts    │ │ - Prompts    │   │  │
│  │  │ - Sources    │ │ - Sources    │ │ - Sources    │   │  │
│  │  │ - KB files   │ │ - KB files   │ │ - KB files   │   │  │
│  │  │ - Validators │ │ - Validators │ │ - Validators │   │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘   │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  User enables plugins via config:                              │
│  {                                                              │
│    "enabled_domains": ["dev", "legal"],                        │
│    "kb_paths": {                                               │
│      "dev": "./kb_files/dev",                                 │
│      "legal": "./kb_files/legal"                               │
│    }                                                            │
│  }                                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**How it works:**
- **Single codebase** with domain-agnostic core
- **Domain plugins** are **data/configuration**, not code:
  - `./plugins/dev/` directory with:
    - `prompts/kb_model.xml` (dev-specific prompt)
    - `harvester_sources.json` (dev sources registry)
    - `kb_files/` (dev knowledge entries)
    - `validators.py` (dev-specific validation rules)
  - `./plugins/legal/` directory (same structure)
- **Single database** with domain partitioning:
  ```sql
  -- Queue table has domain column
  CREATE TABLE queue (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50),  -- 'dev', 'legal', 'medical'
    question TEXT,
    ...
  );
  ```
- **Single deployment** (one Railway.app project, one URL)
- **MCP server** routes queries to correct domain:
  ```python
  # In MCP handler
  domain = detect_domain(query)  # "What is PostgreSQL?" → "dev"
  kb_files_path = f"./plugins/{domain}/kb_files"
  prompt = load_prompt(f"./plugins/{domain}/prompts/kb_model.xml")
  ```

**Example:**
```bash
# User installs VerifiedKB once
npm install -g @verifiedkb/cli

# User enables domains via config
verifiedkb config --enable dev --enable legal

# In Cursor MCP config:
{
  "mcpServers": {
    "verifiedkb": {
      "command": "verifiedkb",
      "args": ["mcp", "--domains=dev,legal"]
    }
  }
}
```

---

### 18.7 Deep Comparison: Approach A vs. Approach B

| Aspect | **Approach A: Multiple Repos** | **Approach B: Single Platform + Plugins** |
|--------|--------------------------------|-------------------------------------------|
| **Code Duplication** | ❌ Each repo has full codebase | ✅ Single codebase, shared engine |
| **Deployment Complexity** | ❌ N deployments (one per domain) | ✅ Single deployment |
| **Database** | ❌ N databases (one per domain) | ✅ Single database with partitioning |
| **Maintenance** | ❌ Fix bugs N times | ✅ Fix once, applies to all |
| **User Experience** | ✅ Install only what you need | ⚠️ Install platform, enable domains |
| **Domain Isolation** | ✅ Complete isolation | ⚠️ Shared runtime (potential conflicts) |
| **Scaling** | ✅ Scale domains independently | ⚠️ Scale entire platform together |
| **Cost** | ❌ N hosting bills | ✅ Single hosting bill |
| **Knowledge Sharing** | ❌ Domains can't cross-reference | ✅ Can query across domains |
| **Development Speed** | ❌ Slower (N repos to maintain) | ✅ Faster (one codebase) |
| **Plugin System** | ❌ Not applicable | ⚠️ Requires plugin architecture |
| **Complexity** | ✅ Simpler (no plugin system) | ❌ More complex (plugin loader, routing) |

---

### 18.8 Core Purpose Preservation

**CRITICAL**: Both approaches preserve the core purpose:

> **Making less capable models MORE capable by providing quick, actionable, accurate knowledge**

**How each preserves it:**

| Core Purpose Element | Approach A | Approach B |
|---------------------|------------|------------|
| **Quick** | ✅ Pre-researched answers (<1s) | ✅ Same |
| **Actionable** | ✅ Grounded in verified sources | ✅ Same |
| **Accurate** | ✅ Human-reviewed, versioned | ✅ Same |
| **Model Enhancement** | ✅ MCP tool exposes KB to AI | ✅ Same |

**Neither approach degrades the core purpose**—they differ only in **how domains are organized**.

---

### 18.9 Recommendation Matrix

| Scenario | Recommended Approach | Reasoning |
|----------|---------------------|-----------|
| **Single domain focus** (dev only) | **A** | Simpler, no plugin overhead |
| **Multiple domains, different teams** | **A** | Teams own their repos |
| **Multiple domains, same team** | **B** | Shared maintenance |
| **Cross-domain queries** ("legal implications of dev code") | **B** | Can query across domains |
| **Different scaling needs** (legal = high, gaming = low) | **A** | Independent scaling |
| **Budget-conscious** | **B** | Single hosting cost |
| **Rapid domain expansion** | **B** | Faster to add new domains |

---

### 18.10 Hybrid Approach (Best of Both?)

**Option C**: Start with **Approach A** (separate repos), then build **Approach B** (platform) as a **meta-layer**.

```
┌─────────────────────────────────────────────────────────────────┐
│                    HYBRID APPROACH                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Build separate repos (Approach A)                    │
│  - DevKB-Pro (standalone)                                      │
│  - LegalKB-Pro (standalone)                                    │
│  - Each is independent, proven, battle-tested                  │
│                                                                 │
│  Phase 2: Build VerifiedKB Platform (Approach B)               │
│  - Platform can wrap existing repos                            │
│  - Or platform can be built fresh using lessons learned        │
│  - Users can choose: standalone tools OR platform               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Start simple (Approach A)
- Learn domain-specific needs
- Build platform with real experience
- Users can migrate or use both

---

### 18.11 Final Recommendation

**For the current build (Developer KB):**

**Start with Approach A** (single repo, single domain). Reasons:

1. **Simplicity**: No plugin system complexity
2. **Focus**: One domain = one purpose = clarity
3. **Proven pattern**: AgentsKB is single-domain
4. **Faster to ship**: No plugin architecture to design

**For future expansion:**

**Consider Approach B** (platform + plugins) **only if**:
- You want to query across domains ("legal implications of dev code")
- You have multiple domains with **shared maintenance burden**
- You want **single deployment** for cost efficiency

**Otherwise, stick with Approach A** (separate repos):
- Each domain is independent
- Teams can own their domain
- Simpler mental model
- No plugin system to maintain

---

### 18.12 What "Pluggable Domain Packs" Actually Means

**If we go with Approach B**, a "domain pack" is **NOT code**—it's **data/configuration**:

```
./plugins/dev/
├── prompts/
│   ├── kb_model.xml          # Dev-specific prompt
│   └── research_model.xml    # Dev-specific research prompt
├── harvester/
│   └── sources.json          # Dev sources registry
├── kb_files/
│   ├── postgresql.md         # Dev knowledge entries
│   ├── python.md
│   └── ...
├── validators.py              # Dev-specific validation
└── metadata.json              # Domain metadata

./plugins/legal/
├── prompts/
│   ├── kb_model.xml          # Legal-specific prompt
│   └── research_model.xml
├── harvester/
│   └── sources.json          # Legal sources (Congress.gov, etc.)
├── kb_files/
│   ├── federal-statutes.md
│   ├── case-law.md
│   └── ...
├── validators.py              # Legal citation validation
└── metadata.json
```

**The core engine loads these at runtime**:
```python
# In core engine
domain = detect_domain(query)
plugin = load_plugin(f"./plugins/{domain}/")
kb_files = plugin.kb_files
prompt = plugin.prompts.kb_model
```

**This preserves the core purpose** because:
- Same retrieval engine
- Same grounding mechanism
- Same human review workflow
- Only the **knowledge content** and **prompts** change

---

### 18.13 Technical Deep Dive: How Approach B (Plugins) Would Work

**This section provides implementation-level detail for Approach B** to clarify how "pluggable domain packs" preserve the core architecture while enabling multi-domain knowledge.

---

#### Plugin Anatomy (File Structure)

A domain plugin is a **data-driven configuration package**, not code:

```
./plugins/dev/
├── metadata.json                # Plugin descriptor
├── prompts/
│   ├── kb_model.xml            # Domain-specific KB agent prompt
│   └── research_model.xml      # Domain-specific research prompt
├── harvester/
│   └── sources.json            # Domain-specific official sources
├── kb_files/
│   ├── postgresql.md           # Domain knowledge entries
│   ├── python.md
│   ├── nextjs.md
│   └── ...
├── stack_packs/
│   ├── python-backend.json     # Domain-specific stack packs
│   └── fullstack-ts.json
├── validators/
│   ├── entry_format.py         # Domain-specific validation rules
│   └── citation_check.py
└── templates/
    └── entry_template.md       # Domain-specific KB entry template

./plugins/legal/
├── metadata.json
├── prompts/
│   ├── kb_model.xml            # Legal-specific (Bluebook citations, etc.)
│   └── research_model.xml
├── harvester/
│   └── sources.json            # Congress.gov, CourtListener, etc.
├── kb_files/
│   ├── federal-statutes.md
│   ├── case-law.md
│   └── state-codes.md
├── stack_packs/
│   ├── california-law.json     # Jurisdiction-specific packs
│   └── federal-law.json
├── validators/
│   ├── citation_validator.py   # Bluebook citation enforcement
│   └── jurisdiction_check.py
└── templates/
    └── entry_template.md       # Legal citation format
```

---

#### Plugin Metadata (metadata.json)

Each plugin declares its identity and requirements:

```json
{
  "plugin_id": "dev",
  "plugin_name": "Developer Knowledge",
  "version": "1.0.0",
  "description": "Technical documentation for software development",
  "author": "VerifiedKB Team",
  "compatible_engine_version": ">=1.0.0",
  
  "domains": ["postgresql", "python", "typescript", "nextjs", "docker", "aws"],
  
  "entry_fields": [
    "id", "question", "answer", "domain", 
    "software_version", "valid_until", 
    "confidence", "tier", "sources", "related_questions"
  ],
  
  "custom_fields": {
    "api_endpoint": "string",      # Dev-specific
    "code_example": "markdown"
  },
  
  "harvester_config": {
    "check_interval": "daily",
    "max_sources_per_domain": 5
  },
  
  "mcp_tools": [
    "ask_question",
    "search_questions",
    "get_stats"
  ]
}
```

**Legal plugin metadata would differ:**
```json
{
  "plugin_id": "legal",
  "plugin_name": "Legal Knowledge",
  "domains": ["federal-statutes", "case-law", "state-codes"],
  
  "custom_fields": {
    "jurisdiction": "string",       # Legal-specific
    "citation": "string",           # Bluebook format
    "effective_date": "date",
    "superseded_by": "string"
  }
}
```

---

#### Core Engine Integration (Plugin Loader)

The core engine loads plugins dynamically:

```python
# app/plugins/loader.py

class PluginManager:
    """Manages domain plugins."""
    
    def __init__(self, plugins_dir: Path = Path("./plugins")):
        self.plugins_dir = plugins_dir
        self.loaded_plugins: dict[str, DomainPlugin] = {}
    
    def load_plugins(self, enabled_domains: list[str]) -> None:
        """Load specified domain plugins."""
        for domain_id in enabled_domains:
            plugin_path = self.plugins_dir / domain_id
            if not plugin_path.exists():
                raise ValueError(f"Plugin not found: {domain_id}")
            
            # Load metadata
            metadata = json.loads((plugin_path / "metadata.json").read_text())
            
            # Load prompts
            kb_prompt = (plugin_path / "prompts" / "kb_model.xml").read_text()
            research_prompt = (plugin_path / "prompts" / "research_model.xml").read_text()
            
            # Load harvester sources
            sources = json.loads((plugin_path / "harvester" / "sources.json").read_text())
            
            # Create plugin instance
            plugin = DomainPlugin(
                id=domain_id,
                metadata=metadata,
                kb_files_path=plugin_path / "kb_files",
                prompts={"kb": kb_prompt, "research": research_prompt},
                harvester_sources=sources,
                validators=self._load_validators(plugin_path / "validators"),
            )
            
            self.loaded_plugins[domain_id] = plugin
    
    def get_plugin(self, domain: str) -> DomainPlugin:
        """Get plugin for a domain."""
        return self.loaded_plugins.get(domain)
    
    def detect_domain(self, query: str) -> str:
        """Detect which domain a query belongs to."""
        # Simple keyword-based detection (can be more sophisticated)
        query_lower = query.lower()
        
        for plugin_id, plugin in self.loaded_plugins.items():
            for domain_keyword in plugin.metadata["domains"]:
                if domain_keyword in query_lower:
                    return plugin_id
        
        # Default to first loaded plugin
        return list(self.loaded_plugins.keys())[0]
```

---

#### Request Flow with Plugins

**Example: User asks "What is PostgreSQL max_connections?"**

```python
# app/api/endpoints.py

@app.post("/ask")
async def ask_question(request: AskRequest):
    # 1. Detect domain from query
    domain = plugin_manager.detect_domain(request.question)
    # domain = "dev"
    
    # 2. Get plugin for domain
    plugin = plugin_manager.get_plugin(domain)
    
    # 3. Use plugin's KB files path
    kb_parser = KBParser(kb_files_dir=plugin.kb_files_path)
    entries = kb_parser.load_and_parse_kb_files()
    
    # 4. Use plugin's prompt
    kb_model_prompt = plugin.prompts["kb"]
    
    # 5. Retrieve using plugin's knowledge
    chunks = retriever.retrieve(
        query=request.question,
        kb_files_path=plugin.kb_files_path,
    )
    
    # 6. Query using plugin's prompt
    response = await kb_model.get_answer(
        query=request.question,
        chunks=chunks,
        system_prompt=kb_model_prompt,  # Dev-specific prompt
    )
    
    # 7. Validate using plugin's validators
    if plugin.validators:
        validated = plugin.validators.validate_response(response)
    
    return response
```

---

#### Database Schema with Domain Partitioning

**Single database, domain column for partitioning:**

```sql
-- Queue table with domain partitioning
CREATE TABLE queue (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,  -- 'dev', 'legal', 'medical'
    question TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    INDEX idx_domain_status (domain, status)
);

-- Entry provenance with domain
CREATE TABLE entry_provenance (
    entry_id VARCHAR(255) PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,  -- Which plugin owns this entry
    file_path TEXT,
    created_at TIMESTAMP,
    last_verified TIMESTAMP,
    source_urls TEXT[]
);

-- Worker heartbeats with domain
CREATE TABLE worker_heartbeat (
    worker_id VARCHAR(100) PRIMARY KEY,
    domain VARCHAR(50),  -- Which domain this worker processes
    last_heartbeat TIMESTAMP,
    status VARCHAR(20)
);
```

**Queries are partitioned:**
```python
# Get pending queue items for dev domain
pending_dev = session.query(Queue).filter(
    Queue.domain == "dev",
    Queue.status == "pending"
).all()

# Get stats for legal domain
legal_stats = session.query(
    func.count(EntryProvenance.entry_id)
).filter(
    EntryProvenance.domain == "legal"
).scalar()
```

---

#### MCP Server with Multi-Domain Routing

**Single MCP server, routes to domains:**

```python
# mcp_server.py

class VerifiedKBMCPServer:
    """MCP server with multi-domain support."""
    
    def __init__(self, enabled_domains: list[str]):
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_plugins(enabled_domains)
    
    @mcp_tool("ask_question")
    async def ask_question(self, question: str, domain: str = None) -> dict:
        """
        Ask a question, optionally specifying domain.
        
        Args:
            question: The question to ask
            domain: Optional domain override (auto-detected if not provided)
        """
        # Detect or use provided domain
        if domain is None:
            domain = self.plugin_manager.detect_domain(question)
        
        # Get plugin
        plugin = self.plugin_manager.get_plugin(domain)
        if plugin is None:
            return {
                "error": f"Domain '{domain}' not enabled",
                "available_domains": list(self.plugin_manager.loaded_plugins.keys())
            }
        
        # Route to domain-specific handler
        return await self._ask_domain(question, plugin)
    
    @mcp_tool("search_questions")
    async def search_questions(self, query: str, domain: str = None) -> dict:
        """Search across enabled domains or specific domain."""
        if domain:
            plugin = self.plugin_manager.get_plugin(domain)
            return await self._search_domain(query, plugin)
        else:
            # Search across all enabled domains
            results = {}
            for domain_id, plugin in self.plugin_manager.loaded_plugins.items():
                results[domain_id] = await self._search_domain(query, plugin)
            return results
    
    @mcp_tool("list_domains")
    async def list_domains(self) -> dict:
        """List enabled domains."""
        return {
            "enabled_domains": [
                {
                    "id": plugin_id,
                    "name": plugin.metadata["plugin_name"],
                    "domains": plugin.metadata["domains"]
                }
                for plugin_id, plugin in self.plugin_manager.loaded_plugins.items()
            ]
        }
```

**User interaction:**
```python
# AI agent using MCP
await mcp.ask_question("What is PostgreSQL max_connections?")
# Auto-detects domain = "dev"

await mcp.ask_question("What is 18 USC 1343?", domain="legal")
# Explicit domain override

await mcp.search_questions("react hooks")
# Searches across all enabled domains
```

---

#### Configuration for Users

**User enables domains via environment variables:**

```env
# Enable multiple domains
ENABLED_DOMAINS=dev,legal

# Domain-specific overrides
DEV_KB_PATH=./plugins/dev/kb_files
LEGAL_KB_PATH=./plugins/legal/kb_files

# Domain-specific API keys (if needed)
DEV_RESEARCH_DISABLED=false
LEGAL_RESEARCH_DISABLED=true  # Legal research requires human approval
```

**Or via config file:**
```json
// .verifiedkb/config.json
{
  "enabled_domains": ["dev", "legal"],
  "domain_configs": {
    "dev": {
      "kb_files_path": "./plugins/dev/kb_files",
      "research_enabled": true,
      "auto_promote": false
    },
    "legal": {
      "kb_files_path": "./plugins/legal/kb_files",
      "research_enabled": true,
      "auto_promote": false,
      "require_citation_validation": true
    }
  }
}
```

---

#### Cross-Domain Queries (Advanced)

**Approach B enables cross-domain queries:**

```python
# User query spans multiple domains
query = "What are the legal implications of using PostgreSQL for HIPAA compliance?"

# System detects multiple domains
domains = plugin_manager.detect_multiple_domains(query)
# domains = ["dev", "legal", "medical"]

# Retrieve from each domain
dev_chunks = retriever.retrieve(query, plugin_manager.get_plugin("dev").kb_files_path)
legal_chunks = retriever.retrieve(query, plugin_manager.get_plugin("legal").kb_files_path)
medical_chunks = retriever.retrieve(query, plugin_manager.get_plugin("medical").kb_files_path)

# Synthesize cross-domain answer
combined_chunks = dev_chunks + legal_chunks + medical_chunks
response = await kb_model.get_answer(
    query=query,
    chunks=combined_chunks,
    system_prompt=CROSS_DOMAIN_PROMPT,  # Special prompt for synthesis
)
```

**This is the ONLY capability Approach B offers that Approach A cannot.**

---

#### Harvester with Plugins

**Harvester loads domain-specific sources:**

```python
# app/harvester/harvester_runner.py

class MultiDomainHarvester:
    """Harvester that processes multiple domain plugins."""
    
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
    
    async def run_harvest(self):
        """Harvest across all enabled domains."""
        for plugin_id, plugin in self.plugin_manager.loaded_plugins.items():
            print(f"Harvesting domain: {plugin_id}")
            
            # Load domain-specific sources
            sources = plugin.harvester_sources
            
            for source in sources:
                # Check for changes
                has_changed = await self.detector.check_for_changes(plugin_id, source)
                
                if has_changed:
                    # Generate entries using domain-specific prompt
                    entries = await self.generator.generate_entries(
                        domain=plugin_id,
                        source=source,
                        prompt=plugin.prompts["research"],  # Domain-specific
                    )
                    
                    # Save to domain-specific staging
                    self.generator.save_entries_to_staging(
                        domain=plugin_id,
                        entries=entries,
                        staging_path=plugin.kb_files_path.parent / "staging",
                    )
```

---

#### Plugin Development Kit (PDK)

**To create a new domain plugin:**

```bash
# CLI tool to scaffold a new domain
verifiedkb create-plugin --id=medical --name="Medical Knowledge"

# Generated structure:
./plugins/medical/
├── metadata.json          # Pre-filled template
├── prompts/
│   ├── kb_model.xml      # Template with TODOs
│   └── research_model.xml
├── harvester/
│   └── sources.json      # Empty, ready to populate
├── kb_files/             # Empty directory
├── stack_packs/          # Empty directory
└── templates/
    └── entry_template.md # Template with domain-specific fields
```

**Developer fills in:**
1. Edit `metadata.json` (add domains, custom fields)
2. Customize `prompts/kb_model.xml` (domain-specific instructions)
3. Add `harvester/sources.json` (official sources to monitor)
4. Populate `kb_files/` (initial knowledge entries)
5. Optional: Add `validators/` (custom validation rules)

---

#### Performance Considerations

**Plugin loading is one-time cost:**
```python
# At application startup
plugin_manager.load_plugins(["dev", "legal", "medical"])
# ~100ms per plugin

# During request handling
plugin = plugin_manager.get_plugin("dev")
# O(1) lookup, <1ms
```

**Database partitioning is efficient:**
```sql
-- With index on (domain, status)
SELECT * FROM queue WHERE domain = 'dev' AND status = 'pending';
-- Uses index, fast even with millions of rows
```

**KB file isolation prevents crosstalk:**
```python
# Each domain has separate kb_files directory
dev_entries = kb_parser.load_and_parse_kb_files("./plugins/dev/kb_files")
legal_entries = kb_parser.load_and_parse_kb_files("./plugins/legal/kb_files")
# No risk of dev entries contaminating legal results
```

---

### 18.14 Why Approach A (Separate Repos) Is Simpler

**Approach A avoids all of the above complexity:**

- No plugin loader
- No domain detection logic
- No cross-domain query synthesis
- No database partitioning
- No multi-domain harvester
- No plugin development kit

**Each repo is a simple, focused application:**
```
DevKB-Pro/
├── kb_files/          # Just dev knowledge
├── prompts/           # Just dev prompts
└── app/               # Simple, single-domain code

LegalKB-Pro/           # Separate repo
├── kb_files/          # Just legal knowledge
├── prompts/           # Just legal prompts
└── app/               # Simple, single-domain code
```

**No shared runtime = no conflicts.**

---

### 18.15 Decision Framework

**Choose Approach B (Platform + Plugins) if:**
- ✅ You need cross-domain queries ("legal implications of dev code")
- ✅ You want a single deployment (one hosting bill)
- ✅ You want shared maintenance (fix bugs once, apply everywhere)
- ✅ You want users to enable/disable domains dynamically
- ✅ You plan to offer a "platform" product with domain marketplace

**Choose Approach A (Separate Repos) if:**
- ✅ Each domain is owned by different teams
- ✅ Domains need independent scaling (legal = high traffic, gaming = low)
- ✅ You want simplicity (no plugin system)
- ✅ You want to ship faster (less architecture to build)
- ✅ You want domain isolation (legal team can't break dev deployments)
- ✅ You're starting with one domain and unsure about expansion

---

### 18.16 Conclusion

**Both approaches preserve the core purpose:**

> Making less capable models MORE capable by providing quick, actionable, accurate knowledge

**The difference is organizational strategy:**

| Approach | Philosophy |
|----------|-----------|
| **A (Separate Repos)** | "Each domain is its own product" |
| **B (Platform + Plugins)** | "One product, many domains" |

**Current recommendation**: Start with **Approach A** (DevKB-Pro as standalone). Simplicity wins for initial build.

**Future consideration**: If you later want cross-domain queries or centralized management, **Approach B** can be built using lessons learned from Approach A.

**Hybrid path**: Build separate repos first, then create a meta-platform that wraps them if needed.

---

### 18.7 Prioritization Matrix (Subjective)

| Domain | Source Quality | Harm Risk | Market Size | Effort | **Score** |
|--------|---------------|-----------|-------------|--------|-----------|
| Developer (current) | ★★★★★ | ★★☆☆☆ | ★★★★☆ | ★★★☆☆ | **Primary** |
| Legal | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | **High** |
| Medical | ★★★★★ | ★★★★★ | ★★★★★ | ★★★★★ | **High** |
| Financial | ★★★★★ | ★★★★☆ | ★★★★★ | ★★★★☆ | **High** |
| Enterprise | ★★★☆☆ | ★★★☆☆ | ★★★★★ | ★★★☆☆ | **Medium** |
| Culinary | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ | ★★☆☆☆ | **Medium** |
| Gaming | ★★★★☆ | ★☆☆☆☆ | ★★★☆☆ | ★★☆☆☆ | **Medium** |
| Gardening | ★★★★☆ | ★☆☆☆☆ | ★★☆☆☆ | ★★☆☆☆ | **Low** |
| Travel | ★★★★☆ | ★★☆☆☆ | ★★★☆☆ | ★★★☆☆ | **Low** |

---

### 18.8 Key Insight

The most valuable domains share these characteristics:

1. **High harm from hallucination** (legal, medical, financial)
2. **Versioned knowledge** (laws change, codes update, guidelines evolve)
3. **Authoritative sources exist** (government, professional bodies, standards orgs)
4. **Professionals already pay for accuracy** (lawyers, doctors, accountants)

The architecture isn't just a "coding knowledge base"—it's a **verified knowledge engine** that could power the next generation of domain-specific AI assistants where accuracy isn't optional.

---

## End of planning document

This document represents the complete, professional-grade specification for building a private, self-expanding, verified developer knowledge base that improves upon the AgentsKB concept while maintaining backwards compatibility.

**Next steps**: 
1. **Choose hosting platform** (Section 14) - Railway.app recommended
2. **Choose system name** (Section 15)
3. **Begin implementation** with Section 12.11 (Local development setup)
4. **Configure harvester sources** (Section 16) for proactive expansion
5. **Consider domain expansion** (Section 18) for future product directions


