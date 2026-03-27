# AgentsKB Baseline Deep Dive (Public Surface Area)

This document captures the baseline behavior and public surface area currently exposed by AgentsKB / “ConsensusKB API”, used to anchor our private “AgentsKB Pro recreation” plan to observable reality.

## Primary sources reviewed

- API root: `https://agentskb-api.agentskb.com/`
- OpenAPI spec: `https://agentskb-api.agentskb.com/openapi.json`
- Swagger UI: `https://agentskb-api.agentskb.com/docs`
- AgentsKB MCP page: `https://agentskb.com/agentskb-mcp/`
- Upstream MCP wrapper repo: `https://github.com/Cranot/agentskb-mcp`
- CLI package readme: `https://www.npmjs.com/package/@agentskb/cli`

## 1) What the “AgentsKB API” actually is (as published)

The REST service at `agentskb-api.agentskb.com` self-identifies as:

- **Title**: “ConsensusKB API”
- **Description**: “Multi-model consensus knowledge base with self-improving authority system”
- **Version**: 1.0.0

The API root advertises:

- `POST /api/ask`
- `GET /api/stats`
- `GET /health`
- `GET /docs` (Swagger UI)

## 2) REST endpoints (from OpenAPI)

### 2.1 Core endpoints

- `POST /api/ask`: ask a question
- `GET /api/stats`: statistics
- `GET /health`: health check

### 2.2 Free-tier endpoints (subset)

The OpenAPI spec documents a distinct set of “free-tier” routes, including:

- `POST /api/free/ask`
- `POST /api/free/ask-batch`
- `GET /api/free/quota`
- `POST /api/free/coverage`
- `POST /api/free/verifications`
- `POST /api/free/request`
- `POST /api/free/changelog`
- `GET /api/free/facets`
- `GET /api/free/browse`
- `GET /api/free/packs`
- `GET /api/free/packs/{pack_id}`
- `GET /api/free/stacks/stats`
- `POST /api/free/taxonomy/navigate`
- `POST /api/free/taxonomy/prerequisites`
- `GET /api/free/taxonomy/stats`
- `GET /api/free/taxonomy/tree`

## 3) /api/ask schema and behavioral constraints (from OpenAPI)

### 3.1 Request (`AskQuestionRequest`)

Documented fields:

- `question` (required): string, 3–500 chars. Description emphasizes: **atomic and specific**.
- `force_refresh` (optional, default false): bypass cache and “force new multi-model consensus validation”.
- `boost_domains` (optional): list of domain paths to bias scoring.
- `research_mode` (optional):
  - null/omitted: **INSTANT MODE** (auto-queue for background research, return immediately)
  - `"research"`: **RESEARCH MODE** (research synchronously, user waits)
- `force_closest` (optional, default false): returns closest match even if below threshold; response may include `below_threshold=true`.

The spec’s description explicitly states the system validates that questions are “atomic” and “not compound”, and suggests “3–25 words with proper context”.

### 3.2 Response (`AnswerResponse`)

Key response fields:

- `question` (string)
- `answer` (string)
- `confidence` (0–1)
- `sources` (string[])
- `source_count` (int)
- `researched` (bool)
- `match_score` (0–1 or null)
- `matched_question` (string or null)
- `auth_level` (string, documented as FREE/ADMIN)
- `quota_used` (number or null)
- `quota_limit` (number or null)
- `is_authenticated` (bool or null)
- `is_rehit` (bool or null)
- `below_threshold` (bool or null; documented as present when `force_closest=true`)

Notable published mechanics:

- **Similarity threshold** is explicitly referenced as **0.90** (in `below_threshold` description).
- A cost model is implied via `quota_used` and `is_rehit` (rehit discount).

## 4) MCP and CLI baseline (from official docs + npm readme + upstream README)

### 4.1 MCP surface exists as a remote service

AgentsKB publishes a remote MCP endpoint:

- `https://mcp.agentskb.com/mcp-kb`

The public MCP page includes examples of adding it to Claude Code and using a Pro/Scale key by passing an **`X-AgentsKB-Key`** header.

### 4.2 CLI includes more than “ask”

The `@agentskb/cli` readme documents:

- “Check coverage” before starting a project (`agentskb check`)
- “Lock answers” for reproducibility (`agentskb lock`, `agentskb update`, `agentskb verify`)
- “Request knowledge” for questions not yet covered (`agentskb request`)
- MCP integration support (Claude Code / Cursor / Cline) and env var `AGENTSKB_API_KEY` (optional for free tier)

## 5) Baseline implications for “improving the concept”

The published baseline already includes:

- An explicit **atomic question** philosophy.
- A **similarity threshold** and a debug mode (`force_closest`) to return “closest match”.
- A concept of **instant vs synchronous research** (`research_mode`).
- A concept of **coverage** and **request knowledge** in the free-tier API.
- A concept of **reproducibility via lockfiles** in the CLI.

Any “superior recreation” plan can be evaluated against this baseline by checking whether it:

- Preserves strict grounding constraints while handling nuanced/multi-concept queries.
- Preserves fast responses on misses while queuing research.
- Improves retrieval quality and match behavior without breaking atomicity constraints.
- Adds privacy/control (private queue + approval) without losing the “self-expanding” loop.


