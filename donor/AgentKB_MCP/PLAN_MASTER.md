# Private “AgentsKB Pro” Recreation — Master Plan (Planning Only)

**Status**: Planning only (no build execution in this phase)  
**Working name**: TBD (see `docs/naming/shortlist.md`)

This plan implements the exact system behavior described in the provided “AgentsKB Pro System Specification”, while ensuring we are materially improving the concept relative to the published public baseline (see `docs/deep-dive/agentskb-baseline.md`).

---

## 0) Goals and non‑negotiables (replication requirements)

### Core replication requirements

- Instant retrieval and delivery of **pre-researched**, **high-confidence**, **source-backed** Q&A entries for developer technologies.
- **Strict grounding**: answers come only from the curated KB (no hallucination or external knowledge in the primary answering path).
- **Structured output** identical to AgentsKB-style responses:
  - question restatement
  - answer
  - confidence (0.00–1.00)
  - tier (GOLD/SILVER/BRONZE if present)
  - sources list
  - related questions
- Better handling of nuanced/complex/paraphrased/multi-concept queries via stronger reasoning while **remaining grounded**.
- Miss behavior:
  - Immediate response: **exact phrase** “No verified high-confidence answer found in the knowledge base.”
  - Queue the question for later research (private queue).

### Improvements explicitly required by the spec

- Fully private (no shared anonymous queue).
- Superior retrieval: Google File Search + `gemini-embedding-001`.
- Superior reasoning: Gemini 3 Pro with `thinking_level: high` + explicit thinking protocol (prompt).
- Managed retrieval infra: no custom vector DB, no embedding pipeline, no hosting maintenance for retrieval.
- Multimodal ready (diagrams/screenshots stored in KB files and processed natively).
- Optional real-time research mode per query (synchronous research + KB update).
- Human review queue support.

---

## 1) System architecture (components + responsibilities)

### 1.1 Components

- **FastAPI wrapper (`api`)**
  - Exposes `/ask` and related endpoints.
  - Enforces request validation and response schema.
  - Enforces the miss behavior and queuing semantics.

- **KB file store (`kb_files`)**
  - Canonical knowledge is stored as Markdown files per domain under `./kb_files/`.
  - File format is fixed (see Section 3).

- **File Search store (managed)**
  - The KB Markdown files (and optional multimodal KB assets) are uploaded/indexed into a Google File Search store.
  - The store is used exclusively by the `kb_model` for retrieval chunks.

- **Primary KB agent (`kb_model`)**
  - Gemini 3 Pro, `tools=["file_search"]`
  - Must follow the exact system prompt in `prompts/kb_model.xml`.
  - Must produce answers strictly grounded in retrieved chunks; otherwise must emit the exact miss phrase.

- **Research agent (`research_model`)**
  - Gemini 3 Pro with tools `web_search` and `browse_page`
  - Must follow the exact system prompt in `prompts/research_model.xml`.
  - Produces exactly one new KB entry on success; otherwise outputs the exact discard string.

- **Queue DB (`queue_db`)**
  - Stores research queue, statuses, timestamps, and governance metadata.
  - Dev-mode can use SQLite (single-node).
  - Self-scaling requires a shared DB (see ADR-0001).

- **Research worker (`worker`)**
  - Pulls pending queue items, executes `research_model`, appends entries to KB files, and triggers File Search ingestion update.
  - Supports human review queue flow (approve/reject).

### 1.2 Core request flows

#### Flow A — KB hit (confidence >= 0.80)

- Input: `{question, domain?, realtime_research?}`
- `kb_model` runs with File Search retrieval context
- Output must match the structured format from `prompts/kb_model.xml`
- API returns:
  - `source: "knowledge_base_hit"`
  - `answer: {question, answer, confidence, tier?, sources, related_questions, reasoning_summary?}`
  - `processing_time_ms`

#### Flow B — KB miss (confidence < 0.80)

- `kb_model` must emit the exact miss phrase.
- API enqueues the question (dedupe by question + domain).
- API returns:
  - `source: "knowledge_base_miss_queued"`
  - `answer.answer = "No verified high-confidence answer found in the knowledge base."`
  - `note` indicating queuing for official-source research

#### Flow C — Real-time research mode (optional per query)

- If `realtime_research=true`:
  - Enqueue the question
  - Run the worker logic synchronously (bounded by timeout/limits)
  - Update KB file(s)
  - Trigger File Search update
  - Re-ask via `kb_model` and return the new answer

---

## 2) Data model and persistence plan

### 2.1 Canonical knowledge storage

- **Canonical store**: `./kb_files/{domain-lowercase}.md`
- Each entry is appended; dedupe policy is handled by governance metadata and review gates.

### 2.2 Queue DB schema (conceptual)

Minimum required fields (aligned to the provided code):

- `id` (int pk)
- `question` (unique, text)
- `domain` (text)
- `timestamp` (float)
- `status` (enum): `pending | in_progress | completed | discarded | error | needs_review`
- `last_error` (text nullable)
- `attempts` (int)
- `created_entry_id` (text nullable) — the Markdown entry ID created on success

Database selection details: `docs/adr/ADR-0001-datastores.md`

---

## 3) Knowledge base file format (canonical)

The KB entry template is **fixed** and must be copied verbatim into generation logic and into any authoring tooling.

See: Section 2 in the provided “AgentsKB Pro System Specification”.

---

## 4) Prompting (sacrosanct configuration)

- Primary KB prompt: `prompts/kb_model.xml`
- Research agent prompt: `prompts/research_model.xml`

Both prompts must be used verbatim.

---

## 5) API contract (FastAPI)

### 5.1 Endpoints

- `GET /` — service info + endpoint list
- `GET /health` — health check
- `POST /ask` — main query endpoint
- `POST /ask-batch` — batch questions (optional if/when implemented)
- `GET /queue-status` — view queue states (read-only)

### 5.2 Request and response schemas

The plan’s baseline request schema is taken from the provided “Complete Production FastAPI Implementation Code” and must be preserved:

- `AskRequest`:
  - `question: str`
  - `domain: str = "general"`
  - `realtime_research: bool = False`

The response must preserve the miss phrase exactly when confidence < 0.80.

---

## 6) “Self-scaling” and “free” constraints (planning ambiguity)

The provided spec selects:

- Gemini 3 Pro
- Google File Search (managed retrieval)

These are not inherently “free” services. The planning outcome depends on which constraint is primary:

- If **managed retrieval + Gemini 3 Pro** is non-negotiable: cost is intrinsic.
- If **free** is non-negotiable: the model/retrieval choices must be revisited.

This is tracked as an explicit ambiguity to resolve before build.

---

## 7) Evaluation and tests (design-time definition)

Test categories aligned to the spec’s strict grounding + self-expanding behavior:

- **Schema tests**: structured output must match the required fields and omit forbidden fields.
- **Grounding tests**: answers must only contain information present in retrieved chunks; citations must match sources in chunks.
- **Threshold tests**: confidence < 0.80 forces the exact miss phrase and queue behavior.
- **Queue behavior tests**: dedupe, status transitions, error handling.
- **Research agent tests**: only official sources; must output exactly one entry or the exact discard string.
- **File Search update tests**: after KB append, retrieval must see the new content.

---

## 8) Deliverables produced in planning phase

- Baseline deep dive: `docs/deep-dive/agentskb-baseline.md`
- Datastore ADR: `docs/adr/ADR-0001-datastores.md`
- Naming shortlist: `docs/naming/shortlist.md`
- Prompts (verbatim): `prompts/kb_model.xml`, `prompts/research_model.xml`


