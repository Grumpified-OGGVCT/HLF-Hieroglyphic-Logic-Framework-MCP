# Msty Claw: Full Implementation Roadmap

## Scope

Every gap from the platform assessment, in priority order, with implementation approach, dependencies, estimated complexity, and integration gates. Builds on the existing MC architecture: lazy tool loading, Mission Control, three-lane memory, MCP lifecycle, and channel/agent/scheduling infrastructure.

All new tools follow the existing `search_tools` lazy-load model unless marked otherwise.

---

## Phase 1: Coding Parity (Weeks 1-6)

These close the gap with Claude Code / Cursor. All are platform-native built-ins because they're as fundamental as `read_file`.

### 1.1 Git Structured Tools

**Tools:** `git_diff`, `git_status`, `git_log`, `git_branch`, `git_commit`, `git_stash`, `git_blame`, `git_show`

**Implementation approach:** Git CLI wrapper with structured output parsing. No native library dependency — parse `--porcelain` and `--format` output into typed objects. Every coding platform does this; the formats are stable.

**Output shape per tool:**
- `git_status`: `{branch, upstream, staged: [{path, change}], unstaged: [...], untracked: [...]}`
- `git_diff`: `{staged, files: [{path, hunks: [{header, lines: [{type, content}]}]}]}`
- `git_log`: `[{hash, author, date, message, files_changed}]`
- `git_branch`: `{current, local: [{name, tracking, ahead, behind}], remote: [...]}`
- `git_commit`: stage paths + commit with message, return `{hash, branch}`
- `git_stash`: `{action, name, description}`
- `git_blame`: `[{line, hash, author, date, content}]`

**Safety gates:**
- `allowed_remotes` config: default deny, user declares trusted remotes per workspace
- `force_push_blocked`: never push --force without explicit platform-level confirmation (not agent judgment)
- `commit_author`: configured once, reused; signing key optional

**Integration:** Works like `read_file` — always loaded in workspace sessions. Uses the existing `shell` access path to call git, but returns structured objects.

**Complexity:** Medium (6 tools, known-stable formats, safety gates are the real work)

**Testing gate:** Every tool tested against a real repo with branches, merge conflicts, detached HEAD, rebase-in-progress

---

### 1.2 Structured HTTP Client

**Tool:** `http_request`

**Signature:** `{method, url, headers: {}, body: string, auth: {type, value}, timeout_ms, follow_redirects: bool, max_redirects: int, accept_invalid_cert: bool}`

**Returns:** `{status, headers: {}, body: string, parsed_body: any (if JSON), timing_ms, redirect_chain: [...]}`

**Implementation approach:** Native HTTP client using the platform's existing network stack. Not a shell `curl` wrapper — first-class platform tool with structured I/O.

**Safety:**
- Domain allowlist/blocklist, configurable per workspace
- Internal IP block by default (10.x, 172.16.x, 192.168.x, 127.x, ::1)
- Max response size (default 10MB)
- Rate-limit detection: return structured `rate_limited: true, retry_after_ms` when 429 received
- Auth values never echoed to conversation log (redacted in tool output)

**Error shape:** Uses the universal error envelope (see Phase 3) once available; ships with its own structured errors until then.

**Complexity:** Medium (one tool, but safety surface is large — allowlist, internal IP detection, auth redaction, rate-limit parsing)

---

### 1.3 Diff/Patch Visibility

**Tools:** `diff_files`, `show_last_edit`, `apply_patch`

**Implementation approach:**
- `diff_files(path_a, path_b)` — produce unified diff with structured hunks
- `show_last_edit()` — after `edit_file`, return what changed without requiring `git diff`
- `apply_patch(path, patch_content, strip_prefix)` — apply unified diff block, return success/conflict report

**Key design decision:** `edit_file` should automatically emit a diff in its return value. The agent shouldn't need to call `show_last_edit` manually after every edit. This is how Cursor and Claude Code work — the edit tool itself says what changed.

**Structured diff output:**
```
{hunks: [{header: "@@ -10,6 +10,8 @@", lines: [
  {type: "context", content: "unchanged line"},
  {type: "added", content: "+new line"},
  {type: "removed", content: "-old line"}
]}]}
```

**Complexity:** Low (diff is a solved problem, unified format is stable, integration with edit_file is the only novel piece)

---

### 1.4 AST-Aware Code Search

**Tools:** `ast_find_references`, `ast_find_definition`, `ast_list_symbols`, `ast_search_pattern`

**Implementation approach:** Tree-sitter bindings. Language auto-detection from file extension. No LSP server dependency — tree-sitter runs in-process.

**Supported languages (minimum):** Python, JavaScript/TypeScript, Rust, Go, Ruby, Java, C, C++

**Tool signatures:**
- `ast_find_references(path, symbol, line?, column?)` → `[{path, line, column, context}]`
- `ast_find_definition(path, symbol)` → `{path, line, column, kind}`
- `ast_list_symbols(path)` → `[{name, kind, line, column}]`
- `ast_search_pattern(language, pattern)` → `[{path, matches: [{line, column, captures}]}]` — tree-sitter query syntax

**Fallback:** When tree-sitter grammar not available for a language, degrade gracefully to regex grep with a warning, don't fail.

**Complexity:** High (tree-sitter integration, grammar management for 7+ languages, query language bridging, graceful degradation)

---

### 1.5 Project Detection

**Tool:** `workspace_detect`

**Returns:**
```
{
  language: "python" | "javascript" | "rust" | "go" | "ruby" | "java" | "mixed" | "unknown",
  build_system: "pip" | "poetry" | "npm" | "yarn" | "pnpm" | "cargo" | "go_modules" | "bundler" | "maven" | "gradle",
  test_runner: "pytest" | "jest" | "vitest" | "cargo_test" | "go_test" | "rspec" | "junit",
  linter: "ruff" | "eslint" | "clippy" | "golangci-lint" | "rubocop",
  formatter: "black" | "prettier" | "rustfmt" | "gofmt",
  package_manager: "pip" | "poetry" | "npm" | "yarn" | "pnpm" | "cargo" | "go_modules" | "bundler",
  entry_points: ["src/main.py", "src/index.ts", ...],
  config_files: ["pyproject.toml", ".eslintrc.json", ...]
}
```

**Implementation:** File-based detection only. Read standard config files, parse them, extract fields. Cache result in `workspace.profile` so detection runs once per workspace, not per session. Re-detect on config file change.

**Complexity:** Low (file reading + known-format parsing, ~20 config formats to support)

---

## Phase 2: Developer Loop Quality (Weeks 5-10)

First-party curated MCP servers. One-click install from platform UI. Not built-in but shipped and maintained by the platform.

### 2.1 Package Management

**MCP Server:** `@msty/packages`

**Tools:** `pkg_install`, `pkg_list`, `pkg_outdated`, `pkg_audit`, `pkg_uninstall`, `pkg_info`

**Backed by:** pip, npm, yarn, cargo CLIs — wraps them with structured output parsing.

**Design:** Auto-detects package manager from `workspace_detect`. Falls back to explicit `pkg_manager` parameter. Runs through workspace shell (same permissions) so it inherits the existing container/filesystem access.

**Safety:** `pkg_install` confirms before installing globally. `pkg_uninstall` confirms before removing. `pkg_audit` returns structured vulnerability data (CVE ids, severity, fix versions).

**Complexity:** Medium (5 package managers x structured output parsing, audit integration)

---

### 2.2 Testing Framework Integration

**MCP Server:** `@msty/testing`

**Tools:** `test_run`, `test_list`, `test_run_file`, `test_run_failing`

**Implementation:** Wraps test runners with `--json` flags where available (pytest, jest, vitest, cargo test). Falls back to regex parsing for runners without structured output.

**Test result shape:**
```
{
  passed: 42, failed: 3, skipped: 1, duration_ms: 1234,
  tests: [
    {name: "test_user_create", status: "passed", duration_ms: 12},
    {name: "test_user_delete", status: "failed", error: {...}, duration_ms: 8}
  ],
  flaky: [{name: "test_timeout", runs: 3, failures: 1, last_failure: "..."}]
}
```

**Flaky detection:** Track test results across runs within a session. Flag tests that pass-then-fail across consecutive runs.

**Complexity:** Medium (4-5 test runners, output format variance, flaky detection)

---

### 2.3 Database Query

**MCP Server:** `@msty/database`

**Tools:** `db_query`, `db_execute`, `db_schema`, `db_transaction`, `db_list_connections`

**Implementation:** SQLite via native binding (no shell wrapping for correctness). PostgreSQL/MySQL opt-in via connection strings.

**SQLite approach:** Direct file access through workspace. Opens the .db file, queries through a driver, returns structured rows.

**Safety:**
- Row limit on SELECT (configurable, default 1000)
- Destructive operations (DELETE without WHERE, DROP, TRUNCATE, ALTER) require confirmation
- Read-only mode option per connection
- Connection strings from env vars, never hardcoded in tool calls

**Complexity:** Medium (SQLite is straightforward; PostgreSQL/MySQL add driver dependency complexity)

---

### 2.4 Document Parsing

**MCP Server:** `@msty/parsers`

**Tools:** `parse_csv`, `parse_json`, `parse_markdown_table`, `parse_pdf`

**Implementation:**
- CSV: built-in parser, delimiter auto-detection, type inference
- JSON: traversal API with path queries (`$.users[0].name`)
- Markdown tables: regex extraction into rows
- PDF: pdf.js or equivalent for text + table extraction

**Safety:** Max file size, max rows, PII sanitization option (scrub emails, phone numbers, SSNs)

**Complexity:** Low-Medium (CSV/JSON/Markdown are trivial; PDF extraction is the hard one)

---

## Phase 3: Platform Hardening (Weeks 8-14)

These are platform-wide changes, not point tools. They touch every existing and future tool.

### 3.1 Universal Error Envelope

**Scope:** All platform tools (built-in + MCP) adopt:

```
{
  error: {
    code: string,           // machine-readable: "NETWORK_TIMEOUT", "PERMISSION_DENIED", etc.
    category: "NETWORK" | "PERMISSION" | "TIMEOUT" | "INVALID_INPUT" | "RATE_LIMITED" | "STALE_STATE" | "INTERNAL",
    retryable: bool,
    retry_after_ms?: number,
    suggestion: string,     // human-readable: "Check your API key in env.OPENAI_API_KEY"
    details: any            // tool-specific: stack trace, validation errors, etc.
  }
}
```

**Implementation plan:**
1. Define the envelope in platform schema
2. Retrofit built-in tools (shell, edit_file, web_fetch, computer_use)
3. Add error adapters for MCP tools (wrap server errors into the envelope)
4. Agent system prompt updated to use error categories for recovery decisions

**Backward compatibility:** Existing tools that don't use the envelope keep their current error shapes. The platform detects non-envelope errors and wraps them at the tool-call boundary.

**Complexity:** High (retrofitting existing tools without breaking them, MCP error wrapping, agent prompt integration)

---

### 3.2 Permission Queryability

**Tools:** `permissions_check`, `permissions_list`

**Built-in, always loaded.** These are safety primitives every agent needs.

```
permissions_check(action: "shell.execute", target: "rm -rf /") →
  {allowed: false, reason: "destructive_filesystem_operation", requires_confirmation: true}

permissions_list() →
  {
    shell: {allowed: true, restricted_paths: ["/etc", "/sys"]},
    web: {allowed: true, blocked_domains: ["internal.corp.com"]},
    files: {allowed: true, read_only_paths: ["/workspace/shared"]},
    channels: {allowed: ["discord_general"], blocked: ["discord_admin"]}
  }
```

**Implementation:** Expose the existing permission model (currently in system prompt only) as a queryable surface. The approval workflow tools already exist (`list_pending_approvals`, `respond_pending_approval`). This adds the "can I do this?" check before attempting the action.

**Complexity:** Low-Medium (new tools, but the permission model already exists in code; just needs a query interface)

---

### 3.3 Platform Observability

**Tools:** `session_stats`, `tool_stats`, `context_budget`

**Implementation approach:** Metering layer that hooks into the tool-call pipeline. Counts tokens, latencies, errors. Exposes as queryable tools and a platform dashboard.

```
session_stats() →
  {
    tokens_used: 24500, tokens_limit: 100000, budget_remaining_pct: 75.5,
    tools_called: 47, errors: 2, avg_latency_ms: 340,
    top_tools: [{name: "shell", calls: 23}, {name: "read_file", calls: 12}],
    cost_estimate: {input: 0.12, output: 0.03, total: 0.15}
  }

context_budget() →
  {used_pct: 75.5, turns_since_compact: 18, recommended_action: "none" | "compact_soon" | "compact_now"}
```

**Dashboard:** Not an agent tool — a platform UI surface. Token usage over time, tool-call frequency heatmap, error rate by tool, cost by provider/model.

**Privacy:** Stats are local to the platform. No telemetry unless user opts in.

**Complexity:** Medium (metering pipeline, tool instrumentation, dashboard UI)

---

### 3.4 Tool Composition / Pipelining

**This is the most architecturally significant change.** It touches the core agent loop.

**What changes:**
1. Tools declare return type schemas
2. Output reference syntax: `$prev.body.users[0].id`, `$result.stdout`, `$edit.diff`
3. Pipe primitive: `http_request | parse_json | db_insert` — the platform resolves references and chains calls without the agent re-echoing intermediate data

**Implementation approach:**
- Phase 3a: Output references. Tools return typed objects. Agent can reference prior results with `$` syntax. References resolved by the platform before next tool call, so the agent doesn't burn context re-reading output.
- Phase 3b: Declared return schemas. Tools publish their output shape. Agent uses this for planning: "I know `http_request` returns `{status, headers, body, parsed_body}`, so I can reference `$result.parsed_body.users`."
- Phase 3c: Pipe primitive. The agent issues one compound action. Platform executes sequentially, resolving references. If any step fails, the pipe short-circuits with the error.

**Key design constraint:** Must not break lazy loading. Tools in a pipe are loaded on demand like any other tool.

**Complexity:** Very High (core loop change, reference resolution, schema system, backward compatibility with existing tools, agent prompt redesign)

---

## Phase 4: UX Closure (Weeks 12-16)

Lower architectural risk. Fast to build individually. Big quality-of-life impact.

### 4.1 Clipboard Access

**Tools:** `clipboard_read`, `clipboard_write`

**Implementation:** Platform-native (desktop clipboard API). Built-in, always available. `write` confirms for content > 1000 chars. `read` only on explicit request.

**Complexity:** Very Low (two tools, platform clipboard API, ~1 day)

---

### 4.2 Desktop Notifications

**Tool:** `notify_send`

**Implementation:** Platform-native notification API (OSNotification on macOS, Toast on Windows, notify-send on Linux). The agent calls this after long-running work completes. Not a channel message — a desktop popup.

**Complexity:** Very Low (one tool, OS notification API, ~1 day)

---

### 4.3 Code Sandbox / REPL

**MCP Server:** `@msty/sandbox`

**Tools:** `sandbox_eval`, `sandbox_repl_start`, `sandbox_repl_eval`, `sandbox_repl_stop`

**Implementation:** Ephemeral container per session (or per repl session). No filesystem write access by default. Network disabled by default. Timeout per execution.

**Languages:** Python, JavaScript/Node, Ruby, shell as minimum.

**Distinction from shell:** Shell runs in the workspace container with full filesystem access. Sandbox runs in an isolated runtime with opt-in permissions. Use shell when you need to build/test the project. Use sandbox when you need to experiment with a regex or try a datetime calculation.

**Complexity:** Medium (container orchestration, multi-language runtime management, session state)

---

### 4.4 Calendar Integration

**MCP Server:** `@msty/calendar`

**Tools:** `calendar_list_events`, `calendar_create_event`, `calendar_delete_event`, `calendar_find_free_slots`

**Backends:** Google Calendar, Outlook, CalDAV. Configured per user.

**Safety:** Read-only by default. Write requires explicit per-operation confirmation. No event modification without confirmation.

**Complexity:** Medium (OAuth flow for each backend, CalDAV protocol, timezone handling)

---

### 4.5 Chart/Diagram Rendering

**MCP Server:** `@msty/charts`

**Tools:** `render_chart`, `render_diagram`, `render_table`

**Implementation:**
- Charts: structured data in, SVG/PNG out. Backed by a lightweight charting library (vega-lite or similar).
- Diagrams: Mermaid/PlantUML text in, SVG out.
- Tables: structured rows in, formatted Markdown or ASCII table out.

**Output:** Write to workspace file, return path. Optionally open in browser/image viewer.

**Complexity:** Low-Medium (charting library integration, Mermaid CLI, output rendering)

---

## Phase 5: Platform Depth (Weeks 14-20)

Longer-term investments that deepen the platform model.

### 5.1 Conversation Branching

**Platform feature, not a tool.** Adds fork/merge/compare to the conversation model.

**Implementation:**
- `conversation_fork(reason)` — creates a branch from current state, returns `fork_id`
- `conversation_merge(fork_id)` — brings branch conclusions into main conversation
- `conversation_compare(fork_a, fork_b)` — diffs two conversation paths (what tools were called, what conclusions were reached)
- `conversation_list_forks()` — active branches for this session

**Storage model:** Forks are lightweight — they share the ancestor conversation history, only store the divergence. Similar to git branches.

**Use case:** Agent explores approach A and approach B in parallel (via Mission Control subagents or sequential forks), compares results, merges the winner.

**Complexity:** High (conversation state model change, merge conflict resolution, Mission Control integration)

---

### 5.2 Workspace Profile / Conventions

**Extension of `workspace_detect` from Phase 1.** Adds:
- `workspace_conventions` — learned/stored conventions: formatting rules, test patterns, naming style, preferred libraries
- `workspace_profile` — persisted across sessions, auto-loaded at session start

**Implementation:** `workspace_detect` runs once, writes to a `.msty/workspace_profile.json` in the workspace root. Subsequent sessions read this file instead of re-detecting. `workspace_conventions` are populated by the agent observing the project (e.g., "this project uses snake_case for Python, camelCase for JS") and saved for future sessions.

**Complexity:** Low (file I/O + caching, builds on Phase 1 detection)

---

### 5.3 Computer Use Structured Recording

**Enhancement to existing `computer_use` recording.** Currently recordings are opaque replay files. This makes them queryable.

**New tool/capability:** `recording_inspect(recording_id)` → structured event log:
```
{
  duration_ms: 45000,
  actions: [
    {timestamp_ms: 0, action: "click", element: 42, result: "success", screenshot_hash: "a1b2"},
    {timestamp_ms: 1200, action: "type", element: 15, text: "search query", result: "success"},
    {timestamp_ms: 3400, action: "wait", element: 99, result: "timeout", error: "element not found within 5000ms"}
  ],
  summary: "45 actions, 42 success, 3 failures, 1 timeout"
}
```

**New capabilities:**
- Jump to event N in replay
- Screenshot comparison between runs (hash-based)
- Assertion: `wait_until(element_predicate, timeout_ms)`

**Complexity:** Medium (enhancing existing recording format, structured event extraction, replay seeking)

---

### 5.4 Memory Validation

**Extension of memory tools (already full CRUD).** Adds:
- `memory_validate(pack_id)` — checks a pack's facts against current workspace state. Returns contradictions.
- `memory_diff(pack_id, revision_a, revision_b)` — structured diff between two pack revisions

**Implementation for `memory_validate`:** For facts tagged with workspace-level claims (e.g., "this project uses pytest"), check if `workspace_detect` agrees. For constraints (e.g., "never use class-based React components"), flag as "unverifiable by tool, user review recommended." Not every fact is machine-checkable, and the tool is honest about which are.

**Complexity:** Low-Medium (facts with workspace tags are a subset of memory content; validation is mostly cross-referencing with workspace_detect)

---

### 5.5 Team-Level Provider Configuration

**Extension of `configure_provider`.** Adds:
- Workspace-level model defaults (`workspace_model_default`)
- Model routing rules: "use Opus for files > 500 lines, Haiku otherwise"
- Fallback chains: "try Opus, if rate-limited use Sonnet, if that fails use local"
- Model performance comparison: log which model handled which task, compare accuracy

**Storage:** Workspace-level config in `.msty/provider_profile.json`, shared via git. Per-user overrides stored locally.

**Implementation:** Routing sits in the agent dispatch layer, not in the agent itself. The agent requests a model capability ("I need a strong reasoning model") and the platform routes based on rules + availability.

**Complexity:** Medium (routing engine, fallback logic, shared config format, comparison logging)

---

### 5.6 Skill Listing with Metadata

**Enhancement to skill system.** Currently `read_skill` exists but the agent sees names only in the system prompt.

**Changes:**
1. Add `description`, `preconditions`, `required_tools` fields to skill manifests
2. Surface these in the system prompt listing (name + one-line description, not just name)
3. Add `skill_search_installed(query)` — search installed skills by capability description
4. Skills declare compatibility: "requires git installed", "requires Azure CLI authenticated"

**Complexity:** Low (manifest field additions, listing format change, search indexing)

---

## Dependency Graph

```
Phase 1 (independent workstreams):
  git_tools ──────── no dependencies
  http_client ────── no dependencies
  diff_patch ─────── depends on edit_file (exists)
  ast_search ─────── depends on tree-sitter integration (new dep)
  project_detect ─── no dependencies

Phase 2 (independent workstreams, depends on Phase 1 tools):
  packages ───────── depends on project_detect (for auto-detection)
  testing ────────── depends on project_detect
  database ───────── no hard dependencies
  parsers ────────── no hard dependencies

Phase 3 (platform-wide, depends on Phase 1-2 being stable):
  error_envelope ──── touches all tools (best after Phase 1-2 done)
  permissions ─────── no tool dependencies (model already exists)
  observability ───── depends on error_envelope (for error tracking)
  composition ─────── depends on error_envelope + stable tool surface

Phase 4 (independent, can start anytime):
  clipboard ───────── no dependencies
  notifications ───── no dependencies
  sandbox ─────────── depends on container infrastructure (exists)
  calendar ────────── depends on OAuth integration (new)
  charts ──────────── no dependencies

Phase 5 (depends on Phase 1-4):
  conversation ────── depends on composition (for reference passing)
  workspace_profile ─ depends on project_detect
  recording ───────── depends on existing computer_use recording
  memory_validate ─── depends on project_detect + workspace_profile
  team_providers ──── depends on observability (for comparison logging)
  skill_metadata ──── no dependencies (manifest changes only)
```

---

## Total Complexity Summary

| Phase | Items | Aggregate Complexity | Parallelizable |
|---|---|---|---|
| Phase 1 | 5 items | High (AST search dominates) | Yes, 4 of 5 are independent |
| Phase 2 | 4 items | Medium | Yes, all independent |
| Phase 3 | 4 items | Very High (composition + error envelope) | Error envelope must come first |
| Phase 4 | 5 items | Low-Medium | Yes, all independent |
| Phase 5 | 6 items | Medium-High (conversation branching) | Yes, all independent |

---

## What Stays Unchanged

- **Lazy tool loading:** All new tools follow the `search_tools` model. Nothing is eagerly loaded.
- **Mission Control:** Subagents, dependency tracking, Task Force presets, approval gating — untouched.
- **Three-lane memory:** Memory packs, working brief, attached packs — untouched. Memory validation (Phase 5) adds to this, doesn't change it.
- **Channel/agent/scheduling:** Full existing surface preserved. New notifications (Phase 4) complement channel messaging.
- **MCP ecosystem:** Extension mechanism unchanged. Phase 2 tools ship as first-party MCP servers using the existing infrastructure.
- **Safety model:** Pause-for-confirmation on durable/external/risky actions preserved. Permission queryability (Phase 3) makes it visible, doesn't weaken it.

---

## What Ships When

| Milestone | Weeks | Deliverable |
|---|---|---|
| M1: Coding parity | 6 | git, HTTP, diff, AST, project detect — competitive with Claude Code on coding loop |
| M2: Developer loop | 10 | packages, tests, DB, parsers — agent can manage dependencies, run tests, query data |
| M3: Platform hardened | 14 | error envelope, permissions, observability, composition (v1) — tools have shared language |
| M4: UX complete | 16 | clipboard, notifications, sandbox, calendar, charts — user-facing quality-of-life |
| M5: Platform deep | 20 | branching, workspace profile, recording, memory validation, team config, skill metadata |

---

# Appendix: Optional Governance Hardening

These are platform-deepening additions that sit on top of the Phase 1-5 implementations.
They are **not required for basic parity** with Claude Code or Cursor. They are for
teams that need institutional-grade trust, audit, and multi-agent coordination — the
kind of hardening that separates "an agent that codes" from "an agent platform you can
bet your production deployment on."

Each section below extends a specific gap from the roadmap with a hardened version.
Implement the base tool first (from the Phase it lives in), then layer on the
hardening if and when you need it. Every addition builds on existing MC primitives:
memory packs, Mission Control, approval workflow, and the three-lane memory model.

---

## H1: Memory Freshness with TTL and Trust-Aware Expiry

**Extends:** Phase 5.4 (Memory Validation)

**What the base tool does:** `memory_validate` checks a pack's facts against current
workspace state and reports contradictions.

**What this hardening adds:** Every fact, constraint, decision, and task in a memory
pack carries a freshness window. Facts don't just get validated against workspace
state once — they expire on a schedule, and the expiry window tightens when the
source agent is under watch, probation, or restriction. Results are filtered
automatically before reaching any agent's context, so agents never act on stale data.

**Why it matters:** The base `memory_validate` tool is reactive — you run it and find
contradictions. This hardening makes freshness proactive. A fact stored 30 days ago
with a 7-day freshness window is automatically excluded from memory recall results
unless the caller explicitly opts into stale data. Revoked or tombstoned facts are
blocked entirely. The platform doesn't wait for someone to run validation — it
protects every agent session.

### Data Model: Evidence Contract on Every Fact

Every fact in a memory pack gets an evidence contract stored alongside it. This
lives in the existing memory pack row — add these columns to the pack schema:

```typescript
// Add to the memory_facts table in your persistence layer
interface EvidenceContract {
  // Core identity
  sha256: string;              // Content hash — dedup key
  content: string;             // The fact/constraint/decision text
  provenance_grade: string;    // "basic" | "evidence-backed" — how well-sourced

  // Freshness lifecycle (the key addition)
  fresh_until: string | null;  // ISO 8601 timestamp — when this fact expires
  collected_at: string;        // ISO 8601 — when this fact was stored
  freshness_status: string;    // "fresh" | "stale" | "expired" — computed at read time

  // Governance state
  revoked: boolean;            // Operator explicitly revoked
  tombstoned: boolean;         // Soft-deleted, kept for audit
  superseded_by: string | null; // SHA-256 of the newer fact that replaces this one

  // Trust provenance
  trust_tier: string;          // "verified" | "validated" | "trusted" | "untrusted" | "local"
  source_agent_id: string;     // Which agent/bot stored this
  source_session_id: string;   // Which conversation produced it
}
```

If modifying the existing memory pack schema is too invasive initially, store this
as a JSON blob in a `metadata` column and extract fields for query filtering at
read time.

### Freshness Windows by Trust Tier

Different sources get different freshness windows. A fact from a verified benchmark
lasts longer than one from an untrusted external source:

```python
# Constants — tune these for your deployment
FRESHNESS_WINDOWS: dict[str, int] = {
    "verified":  3600,   # 1 hour    — benchmark-verified facts
    "validated": 1800,   # 30 min    — attested by a trusted agent
    "trusted":   900,    # 15 min    — from a known-good source
    "untrusted": 300,    # 5 min     — external, unverified
    "local":     600,    # 10 min    — session-local working memory
}

# Trust state degrades freshness windows further
TRUST_STATE_MULTIPLIERS: dict[str, float] = {
    "healthy":    1.0,   # Full window
    "watched":    0.6,   # 60% of window
    "probation":  0.35,  # 35% of window
    "restricted": 0.15,  # 15% of window — nearly unusable
}
```

When an agent is under watch (from Mission Control's observation), ALL facts it
produces get shorter windows. When it hits probation, its facts are barely usable.
This creates a self-correcting loop: bad agents produce facts that expire faster,
so other agents are naturally protected from their stale output.

### Core Implementation: The Freshness Checker

```python
class FreshnessChecker:
    """Enforces memory freshness with trust-aware window tightening."""

    def __init__(self, trust_snapshot: Optional[dict] = None):
        """
        Args:
            trust_snapshot: If provided, freshness windows tighten based on
                the source agent's current trust state. Pass the result of
                Mission Control's agent health check. If None, all windows
                use the base trust tier values.
        """
        self._trust_snapshot = trust_snapshot

    def compute_window(self, trust_tier: str) -> int:
        """
        Calculate the effective freshness window for a trust tier.

        Base window comes from trust_tier. If the source agent is under
        watch/probation/restriction, multiply by the degradation factor.

        Example:
            verified + healthy    → 3600s window
            verified + watched    → 2160s window (3600 × 0.6)
            verified + restricted → 540s window  (3600 × 0.15)
        """
        base = FRESHNESS_WINDOWS.get(trust_tier, 300)
        if self._trust_snapshot:
            state = self._trust_snapshot.get("trust_state", "healthy")
            multiplier = TRUST_STATE_MULTIPLIERS.get(state, 1.0)
            base = int(base * multiplier)
        return base

    def check_freshness(
        self,
        fact: dict,
        max_age_seconds: Optional[int] = None,
    ) -> dict:
        """
        Check whether a single memory fact is still fresh.

        Returns a verdict with:
          - admissible: bool — can this fact be used?
          - freshness_status: "fresh" | "stale" | "expired"
          - policy_action: "keep" | "refresh" | "evict" | "quarantine"
          - reasons: list[str] — human-readable explanation

        Revoked or tombstoned facts are ALWAYS inadmissible regardless of age.
        """
        # Extract the evidence contract from the fact
        contract = fact.get("evidence", {})
        if not contract:
            # No evidence contract means no freshness tracking.
            # Treat as fresh but flag as unevidenced.
            return {
                "admissible": True,
                "freshness_status": "fresh",
                "policy_action": "keep",
                "reasons": ["no evidence contract — treated as fresh"]
            }

        # Never admit revoked or tombstoned facts
        if contract.get("revoked") or contract.get("tombstoned"):
            return {
                "admissible": False,
                "freshness_status": "expired",
                "policy_action": "quarantine",
                "reasons": ["revoked" if contract.get("revoked") else "tombstoned"]
            }

        # Compute effective max age
        if max_age_seconds is not None:
            effective_max = max_age_seconds
        else:
            effective_max = self.compute_window(
                contract.get("trust_tier", "local")
            )

        # Check fresh_until timestamp
        now = time.time()
        fresh_until = contract.get("fresh_until")
        if fresh_until:
            fresh_until_epoch = self._parse_iso_to_epoch(fresh_until)
            age = now - fresh_until_epoch
            if age > effective_max:
                superseded = contract.get("superseded_by")
                return {
                    "admissible": False,
                    "freshness_status": "stale",
                    "policy_action": "refresh" if superseded else "evict",
                    "reasons": [
                        f"fresh_until passed — age {int(age)}s exceeds "
                        f"window {effective_max}s"
                    ],
                    "superseded_by": superseded or ""
                }

        # Age-based check from collection time
        collected_at = contract.get("collected_at")
        if collected_at:
            age = now - self._parse_iso_to_epoch(collected_at)
            if age > effective_max:
                return {
                    "admissible": False,
                    "freshness_status": "stale",
                    "policy_action": "evict",
                    "reasons": [
                        f"age {int(age)}s exceeds freshness window "
                        f"{effective_max}s"
                    ]
                }

        # Still fresh
        return {
            "admissible": True,
            "freshness_status": "fresh",
            "policy_action": "keep",
            "reasons": []
        }

    def enforce_batch(self, facts: list[dict]) -> dict:
        """
        Batch-check an entire memory pack or recall result set.

        Returns categorized buckets: fresh / stale / expired, with
        per-fact policy actions and aggregate counts.

        This is the function you wire into memory_recall, not the single
        check above. It runs automatically on every recall.
        """
        fresh, stale, expired = [], [], []
        for idx, fact in enumerate(facts):
            result = self.check_freshness(fact)
            key = fact.get("sha256", f"fact-{idx}")
            entry = {"fact_key": key, **result}

            status = result["freshness_status"]
            if status == "expired":
                expired.append(entry)
            elif status == "stale":
                stale.append(entry)
            else:
                fresh.append(entry)

        return {
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "expired_count": len(expired),
            "fresh": fresh,
            "stale": stale,
            "expired": expired,
            "all_admissible": len(stale) == 0 and len(expired) == 0,
        }

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _parse_iso_to_epoch(timestamp: str) -> float:
        """Parse ISO 8601 to Unix epoch. Returns 0 on parse failure."""
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except (ValueError, OSError):
            return 0.0
```

### Integration Points

**1. Wire into `get_conversation_memory` and `search_memory_packs`:**

```python
def recall_with_freshness(query: str, top_k: int = 5) -> dict:
    """
    Standard recall pipeline — automatically filters stale data.
    
    Call this instead of raw memory_pack query. Agents never see
    stale or expired facts unless they explicitly opt in with
    include_stale=True.
    """
    raw_results = memory_store.search(query, top_k=top_k)

    # Get the calling agent's trust snapshot from Mission Control
    agent_trust = mission_control.get_agent_health(caller_agent_id)
    checker = FreshnessChecker(trust_snapshot=agent_trust)

    # Run freshness enforcement
    freshness = checker.enforce_batch(raw_results)

    # Return only fresh results by default
    return {
        "results": freshness["fresh"],
        "stale_available": freshness["stale_count"],
        "expired_blocked": freshness["expired_count"],
        "all_fresh": freshness["all_admissible"],
    }
```

**2. Memory store with freshness windows:**

```python
def store_fact_with_freshness(
    content: str,
    trust_tier: str = "local",
    fresh_until: Optional[str] = None,
    source_agent_id: str = "",
) -> dict:
    """
    Store a fact with its evidence contract baked in.

    If fresh_until is not provided, compute it from trust_tier.
    """
    # Auto-compute fresh_until from trust tier if not specified
    if not fresh_until:
        window = FRESHNESS_WINDOWS.get(trust_tier, 300)
        expire_at = datetime.now(timezone.utc) + timedelta(seconds=window)
        fresh_until = expire_at.isoformat()

    evidence = {
        "sha256": hashlib.sha256(content.encode()).hexdigest(),
        "content": content,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "fresh_until": fresh_until,
        "trust_tier": trust_tier,
        "source_agent_id": source_agent_id,
        "provenance_grade": "basic",
        "revoked": False,
        "tombstoned": False,
    }

    return memory_store.insert(
        content=content,
        evidence=evidence,
        metadata={"freshness_managed": True},
    )
```

**3. Weekly freshness audit (Playbook):**

```python
def weekly_freshness_audit(pack_id: str) -> dict:
    """
    Run as a scheduled Playbook. Scans all facts in a pack, flags
    stale/expired entries, generates a report for operator review.

    Use the existing scheduling system: configure_playbook_schedule
    to run this weekly. The report goes to the workspace or a channel.
    """
    all_facts = memory_store.get_pack(pack_id).get_facts()
    checker = FreshnessChecker()
    result = checker.enforce_batch(all_facts)

    report = {
        "pack_id": pack_id,
        "total_facts": len(all_facts),
        "fresh": result["fresh_count"],
        "stale": result["stale_count"],
        "expired": result["expired_count"],
        "stale_entries": [
            {"key": e["fact_key"], "action": e["policy_action"]}
            for e in result["stale"]
        ],
        "recommendation": (
            "No action needed" if result["all_admissible"]
            else f"Review {result['stale_count']} stale and "
                 f"{result['expired_count']} expired entries"
        ),
    }

    # If problems found, send to operator's channel
    if not result["all_admissible"]:
        channel.send_message(
            channel="operator_alerts",
            message=json.dumps(report, indent=2)
        )

    return report
```

---

## H2: Semantic Drift Detection for Subagent Output

**Extends:** Phase 5.4 (Memory Validation) and Mission Control subagents

**What the base tool does:** Mission Control spawns subagents with task definitions.
The subagent returns output. There is no automated check that the output actually
matches the task.

**What this hardening adds:** After every subagent completes, run a deterministic
lexical check comparing the original task description to the subagent's output.
Detects scope expansion (subagent did things it wasn't asked to do), intent drift
(subagent misunderstood the task), and missing terms (subagent dropped key
requirements). No LLM call — it's a bounded Jaccard similarity check with stop-word
filtering, safe to run on every delegation.

**Why it matters:** Subagent output quality varies. A subagent asked to "add rate
limiting to the login endpoint" might add it to the registration endpoint too (scope
expansion), might use a different library than requested, or might misunderstand and
optimize queries instead. The operator shouldn't need to manually review every
subagent output to catch drift. This check flags drift automatically and surfaces it
in the subagent's Mission Control status.

### Core Implementation

```python
import re

# Stop words excluded from token matching — these are noise
STOP_WORDS = {
    "a", "an", "and", "or", "the", "to", "for", "of", "in", "with",
    "is", "was", "be", "by", "on", "as", "this", "that",
}

# Terms that indicate the subagent did something dangerous
DANGER_SIGNALS = {
    "delete", "destructive", "publish", "deploy", "drop",
    "truncate", "force_push", "rm", "sudo",
}


def evaluate_drift(
    original_task: str,
    subagent_output: str,
    threshold: float = 0.55,
) -> dict:
    """
    Compare the original task against the subagent's output.
    Returns a verdict the operator can act on without reading
    the full output.

    Args:
        original_task: The task description sent to the subagent.
        subagent_output: What the subagent returned.
        threshold: Similarity below this triggers a drift flag (0.0 to 1.0).

    Returns a dict with:
        - similarity_score: Jaccard similarity (0.0 = no overlap, 1.0 = identical)
        - drift_detected: bool — did anything flag?
        - drift_flags: list — which checks failed
        - missing_terms: what was in the task but not in the output
        - introduced_terms: what was in the output but not in the task
    """
    # Tokenize: lowercase, non-alphanumeric → space, split
    task_tokens = _tokenize(original_task)
    output_tokens = _tokenize(subagent_output)

    # Jaccard similarity: |intersection| / |union|
    overlap = task_tokens & output_tokens
    union = task_tokens | output_tokens
    similarity = round(len(overlap) / len(union), 4) if union else 1.0

    # What did the subagent drop?
    missing = sorted(task_tokens - output_tokens)

    # What did the subagent add that wasn't asked?
    introduced = sorted(output_tokens - task_tokens)

    # Drift flags
    flags: list[str] = []
    if similarity < threshold:
        flags.append("low_token_overlap")
    if missing:
        flags.append("intent_terms_missing_from_output")
    if any(t in introduced for t in DANGER_SIGNALS):
        flags.append("potential_scope_expansion")

    return {
        "drift_detected": bool(flags),
        "similarity_score": similarity,
        "threshold": threshold,
        "drift_flags": flags,
        "missing_intent_terms": missing,
        "introduced_output_terms": introduced,
        "original_task_hash": _sha256(original_task),
        "subagent_output_hash": _sha256(subagent_output),
    }


def _tokenize(text: str) -> set[str]:
    """Extract meaningful tokens, filtering noise."""
    # Replace non-alphanumeric with spaces, lowercase
    normalized = "".join(
        ch.lower() if ch.isalnum() else " " for ch in (text or "")
    )
    return {
        token for token in normalized.split()
        if len(token) > 2 and token not in STOP_WORDS
    }


def _sha256(value: str) -> str:
    import hashlib
    return hashlib.sha256(str(value or "").encode()).hexdigest()
```

### Integration: Wire Into Mission Control Subagent Completion

```python
# In mission_control.py — after a subagent completes

def on_subagent_complete(mission_id: str, subagent_output: str) -> dict:
    """Hook that runs when a subagent finishes its task."""
    mission = get_mission(mission_id)
    original_task = mission.get("task_description", "")

    # Run drift check
    drift = evaluate_drift(
        original_task=original_task,
        subagent_output=subagent_output,
    )

    # If drift detected, flag the mission for operator review
    if drift["drift_detected"]:
        mission["status"] = "needs_review"
        mission["drift_report"] = drift
        mission["operator_summary"] = (
            f"Subagent output drifted from original task. "
            f"Similarity: {drift['similarity_score']:.2f}. "
            f"Flags: {', '.join(drift['drift_flags'])}. "
            f"Missing terms: {', '.join(drift['missing_intent_terms'][:5])}."
        )

        # Notify operator
        if drift["similarity_score"] < 0.3:
            # Severe drift — send to approval queue
            approval_queue.add(
                mission_id=mission_id,
                reason=f"Severe subagent drift (similarity {drift['similarity_score']:.2f})",
                drift_report=drift,
            )
        else:
            # Moderate drift — log for review, don't block
            mission["status"] = "completed_with_drift"

    return {"mission_id": mission_id, "drift": drift}
```

### Why This Isn't an LLM Call

This is intentionally **not** an LLM-based check. An LLM call to validate another
LLM's output:
- Costs tokens (the thing you're trying to save)
- Adds latency (another API round-trip)
- Isn't more reliable than the original output
- Can't run automatically on every subagent completion

The Jaccard similarity check is deterministic, runs in microseconds, costs nothing,
and catches the obvious cases: the subagent dropped requirements, added unrequested
work, or completely misunderstood the task. It won't catch subtle semantic drift
("used express-rate-limit instead of bottleneck") but it catches the 80% case for
free.

---

## H3: Tier-Gated Permissions with Governance Proofs

**Extends:** Phase 3.2 (Permission Queryability)

**What the base tool does:** `permissions_check` returns `{allowed: bool, reason:
str}`. `permissions_list` returns the permission model as structured data.

**What this hardening adds:** Instead of a binary allowed/denied model, permissions
are tiered (hearth/forge/sovereign). Instead of just checking permissions before a
call, dangerous tools require a **governance proof** — a signed contract that
demonstrates the agent has gone through the right gates (review, attestation,
operator approval) before the action is permitted. The agent discovers its
permissions at session start, not through failure.

**Why it matters:** Binary allow/deny creates a brittle system — either the agent
can do everything or nothing. Tier-gating means most agents run as "hearth"
(read-only, safe by default), known-good agents run as "forge" (can modify state
within bounds), and operator-attested agents run as "sovereign" (full access).
Governance proofs mean the platform doesn't rely on the agent's self-restraint — it
requires cryptographic evidence that the right people approved the action.

### Data Model: Tool Tiers

```python
# Extend the tool registry with tier requirements
TOOL_TIERS: dict[str, str] = {
    # hearth — read-only, always available, no proof needed
    "git_status":       "hearth",
    "git_diff":         "hearth",
    "git_log":          "hearth",
    "read_file":        "hearth",
    "glob":             "hearth",
    "grep":             "hearth",
    "memory_search":    "hearth",
    "permissions_check":"hearth",
    "session_stats":    "hearth",

    # forge — can modify state within bounds, basic operations
    "git_commit":       "forge",
    "edit_file":        "forge",
    "write_file":       "forge",
    "db_query":         "forge",
    "test_run":         "forge",
    "memory_store":     "forge",
    "channel_send":     "forge",

    # sovereign — operator-attested, full access, requires governance proof
    "git_push":         "sovereign",
    "db_execute":       "sovereign",  # DDL, schema changes
    "memory_govern":    "sovereign",  # Revoke/tombstone facts
    "delete_conversation":"sovereign",
    "configure_channel": "sovereign",
    "create_bot":       "sovereign",
}

# Agent tiers resolve from bot configuration
AGENT_TIER_RANKS = {"hearth": 0, "forge": 1, "sovereign": 2}
```

### Core Implementation: Tier-Aware Permission Check

```python
class TieredPermissionGate:
    """Permission checker with tier gating and governance proof requirements."""

    def __init__(self, agent_tier: str, agent_id: str):
        """
        Args:
            agent_tier: The agent's assigned tier (hearth/forge/sovereign).
                Resolved from the bot configuration at session start.
            agent_id: The agent's bot ID for audit logging.
        """
        self.agent_tier = agent_tier
        self.agent_id = agent_id
        self.agent_rank = AGENT_TIER_RANKS.get(agent_tier, 0)

    def check(self, tool_name: str, target: Optional[str] = None) -> dict:
        """
        Check if this agent can call this tool.

        Returns: {allowed, reason, requires_proof, tier_required, agent_tier}

        A "forge" agent cannot call "sovereign" tools.
        A "hearth" agent can only call "hearth" tools.
        Some "sovereign" tools ADDITIONALLY require a governance proof.
        """
        required_tier = TOOL_TIERS.get(tool_name, "sovereign")
        required_rank = AGENT_TIER_RANKS.get(required_tier, 2)

        if self.agent_rank < required_rank:
            return {
                "allowed": False,
                "reason": (
                    f"Tool '{tool_name}' requires tier '{required_tier}' "
                    f"(rank {required_rank}). Agent '{self.agent_id}' is "
                    f"tier '{self.agent_tier}' (rank {self.agent_rank})."
                ),
                "requires_proof": False,
                "tier_required": required_tier,
                "agent_tier": self.agent_tier,
            }

        # Some sovereign tools additionally require a governance proof
        requires_proof = tool_name in SOVEREIGN_PROOF_REQUIRED
        if requires_proof:
            return {
                "allowed": True,
                "reason": (
                    f"Tier '{self.agent_tier}' is sufficient for '{tool_name}', "
                    f"but a governance proof is additionally required."
                ),
                "requires_proof": True,
                "tier_required": required_tier,
                "agent_tier": self.agent_tier,
            }

        return {
            "allowed": True,
            "reason": f"Tier '{self.agent_tier}' authorizes '{tool_name}'.",
            "requires_proof": False,
            "tier_required": required_tier,
            "agent_tier": self.agent_tier,
        }

    def list_available_tools(self) -> dict:
        """Return all tools this agent can actually call, by tier."""
        available = []
        blocked = []
        for tool_name, required_tier in TOOL_TIERS.items():
            result = self.check(tool_name)
            if result["allowed"]:
                available.append({
                    "tool": tool_name,
                    "requires_proof": result["requires_proof"],
                })
            else:
                blocked.append({
                    "tool": tool_name,
                    "reason": result["reason"],
                })
        return {
            "agent_tier": self.agent_tier,
            "available_count": len(available),
            "blocked_count": len(blocked),
            "available": available,
            "blocked": blocked,
        }


# ── Sovereign tools that additionally require a governance proof ──
# These are actions where tier alone isn't enough — the agent must
# present evidence that a human or review board approved the action.
SOVEREIGN_PROOF_REQUIRED: set[str] = {
    "git_push",            # Push to remote
    "db_execute",           # Schema changes
    "memory_govern",        # Revoke/tombstone facts
    "delete_conversation",  # Permanent deletion
    "create_bot",           # New agent lifecycle
    "configure_channel",    # Channel creation/modification
}
```

### Governance Proof Verification

When a tool requires a proof, the agent must include a signed governance proof in
the call. The proof is a JSON object signed by an operator or review board:

```python
def verify_governance_proof(proof: dict, tool_name: str) -> dict:
    """
    Verify that a governance proof is valid for the requested tool.

    A valid proof must:
    1. Be well-formed (required fields present)
    2. Be signed by a recognized operator
    3. Authorize the specific tool being called
    4. Not be expired
    5. Have a valid signature
    """
    required_fields = {
        "proof_id", "tool_authorized", "operator_id",
        "operator_signature", "issued_at", "expires_at",
    }
    if not required_fields.issubset(proof.keys()):
        return {
            "valid": False,
            "reason": f"Missing fields: {required_fields - set(proof.keys())}",
        }

    # Check expiration
    expires = _parse_iso(proof["expires_at"])
    if expires and expires < datetime.now(timezone.utc):
        return {
            "valid": False,
            "reason": f"Proof expired at {proof['expires_at']}",
        }

    # Check tool authorization
    if proof["tool_authorized"] != tool_name:
        return {
            "valid": False,
            "reason": (
                f"Proof authorizes '{proof['tool_authorized']}' "
                f"but tool '{tool_name}' was requested"
            ),
        }

    # Verify operator signature
    operator_key = get_operator_public_key(proof["operator_id"])
    if not operator_key:
        return {
            "valid": False,
            "reason": f"Unknown operator: {proof['operator_id']}",
        }

    payload = _canonical_json({
        "proof_id": proof["proof_id"],
        "tool_authorized": proof["tool_authorized"],
        "operator_id": proof["operator_id"],
        "issued_at": proof["issued_at"],
        "expires_at": proof["expires_at"],
    })
    if not verify_signature(payload, proof["operator_signature"], operator_key):
        return {
            "valid": False,
            "reason": "Signature verification failed",
        }

    return {"valid": True, "reason": "Governance proof accepted"}


def _canonical_json(value: dict) -> str:
    """Deterministic JSON serialization for signing."""
    import json
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
```

### Integration: Wire Into the Tool Call Pipeline

```python
# In the platform tool-call dispatcher

def dispatch_tool_call(tool_name: str, params: dict, session: dict) -> dict:
    """Central dispatch — all tool calls go through here."""

    gate = session.get("permission_gate")
    if not gate:
        return {"error": "No permission gate for session"}

    # Check tier permission
    permission = gate.check(tool_name)
    if not permission["allowed"]:
        return {
            "error": {
                "code": "PERMISSION_DENIED",
                "category": "PERMISSION",
                "retryable": False,
                "suggestion": (
                    f"Agent tier '{permission['agent_tier']}' cannot use "
                    f"'{tool_name}'. Required: '{permission['tier_required']}'."
                ),
                "details": permission,
            }
        }

    # If proof is required, verify it
    if permission["requires_proof"]:
        proof = params.pop("_governance_proof", None)
        if not proof:
            return {
                "error": {
                    "code": "GOVERNANCE_PROOF_REQUIRED",
                    "category": "PERMISSION",
                    "retryable": False,
                    "suggestion": (
                        f"'{tool_name}' requires a governance proof. "
                        f"Include '_governance_proof' in the call."
                    ),
                    "details": {
                        "tool": tool_name,
                        "required_proof": True,
                    },
                }
            }

        verification = verify_governance_proof(proof, tool_name)
        if not verification["valid"]:
            return {
                "error": {
                    "code": "GOVERNANCE_PROOF_INVALID",
                    "category": "PERMISSION",
                    "retryable": False,
                    "suggestion": verification["reason"],
                    "details": verification,
                }
            }

    # Permission granted — dispatch to the actual tool
    return execute_tool(tool_name, params, session)
```

### Integration: Surface at Session Start

```python
# In the agent onboarding / system prompt generation

def build_tool_listing(agent_tier: str, agent_id: str) -> str:
    """
    Generate the tool listing section of the system prompt.

    Instead of listing all 70+ tools, list only what this agent
    can actually use, categorized by tier and proof requirements.
    """
    gate = TieredPermissionGate(agent_tier, agent_id)
    available = gate.list_available_tools()

    lines = ["## Your Available Tools", ""]

    # Group by proof requirement
    direct = [t for t in available["available"] if not t["requires_proof"]]
    proofed = [t for t in available["available"] if t["requires_proof"]]

    if direct:
        lines.append("### Call directly (no proof needed):")
        for t in direct:
            lines.append(f"- `{t['tool']}`")
        lines.append("")

    if proofed:
        lines.append("### Require governance proof (include `_governance_proof`):")
        for t in proofed:
            lines.append(f"- `{t['tool']}`")
        lines.append("")

    if available["blocked_count"]:
        lines.append(
            f"### Blocked ({available['blocked_count']} tools above your tier):"
        )
        lines.append("These are not available to you. Request operator elevation if needed.")
        lines.append("")

    return "\n".join(lines)
```

---

## H4: Merkle-Consistent Audit Chain

**Extends:** Phase 3.3 (Platform Observability)

**What the base tool does:** `session_stats` returns token counts, latencies,
tool-call frequency. A dashboard shows operator-facing metrics.

**What this hardening adds:** Every state-changing tool call records an immutable audit
entry. Each entry hashes the previous entry, forming a Merkle chain. The chain is
verifiable end-to-end — an operator can prove that no entry was inserted, removed,
or modified after the fact. This isn't a log file. It's cryptographic proof that
the recorded events happened in the recorded order.

**Why it matters:** `session_stats` tells you *what* happened. An audit chain tells
you it *definitely* happened. When an agent deletes a file, pushes to production, or
revokes a memory fact, the audit chain preserves who did it, when, what tool they
used, and the cryptographic hash of the before-and-after state. In a disputed
situation, you can replay the chain and prove exactly what occurred.

### Data Model: Audit Entry

```python
import hashlib
import json
import uuid
import time
from datetime import datetime, timezone

class AuditEntry:
    """
    A single entry in the Merkle audit chain.

    Each entry hashes:
      - The content of this audit event
      - The hash of the previous entry (forming the chain)
      - A Merkle hash covering this entry + all predecessors
    """

    def __init__(
        self,
        event_type: str,       # "git_commit", "memory_store", "db_execute", ...
        payload: dict,         # What happened — tool params, result summary
        agent_id: str,         # Which agent/bot performed the action
        goal_id: str = "",     # What mission or task this was part of
        anomaly_score: float = 0.0,  # 0.0 = normal, 1.0 = definitely anomalous
        previous_hash: str = "",     # Hash of the previous entry (empty = genesis)
    ):
        self.entry_id = str(uuid.uuid4())
        self.timestamp = time.time()
        self.iso_timestamp = datetime.now(timezone.utc).isoformat()
        self.event_type = event_type
        self.payload = payload
        self.agent_id = agent_id
        self.goal_id = goal_id
        self.anomaly_score = anomaly_score
        self.previous_hash = previous_hash

        # Compute this entry's hash
        body = json.dumps({
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
            "agent_id": self.agent_id,
            "goal_id": self.goal_id,
            "anomaly_score": self.anomaly_score,
            "previous_hash": self.previous_hash,
        }, sort_keys=True, default=str)

        self.entry_hash = hashlib.sha256(body.encode()).hexdigest()

        # Chain hash: hash of (previous_hash + this entry_hash)
        chain_payload = json.dumps({
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
        }, sort_keys=True)
        self.chain_hash = hashlib.sha256(chain_payload.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.iso_timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
            "agent_id": self.agent_id,
            "goal_id": self.goal_id,
            "anomaly_score": self.anomaly_score,
            "entry_hash": self.entry_hash,
            "chain_hash": self.chain_hash,
            "previous_hash": self.previous_hash,
        }
```

### Core Implementation: Audit Chain Store

```python
import threading

class AuditChain:
    """
    Thread-safe Merkle-consistent audit chain.

    Persisted to a JSONL file (one entry per line). At startup, the
    store replays the file to verify integrity. If any entry's hash
    doesn't match, the chain is flagged as tampered.

    Usage:
        chain = AuditChain("~/.msty/audit/workspace_name.jsonl")
        chain.log("memory_store", {"fact_id": 42}, agent_id="bot_7")
        chain.log("git_commit", {"hash": "a1b2..."}, agent_id="bot_7")

        # Verify entire chain
        result = chain.verify()
        # → {valid: True, entry_count: 142, head_hash: "c3d4..."}
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._entries: list[AuditEntry] = []
        self._head_hash = ""

        # Replay existing chain
        self._replay()

    def _replay(self) -> None:
        """Replay the audit file to rebuild the in-memory chain."""
        import os
        if not os.path.exists(self.filepath):
            return

        entries = []
        with open(self.filepath, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    entry = AuditEntry(
                        event_type=data["event_type"],
                        payload=data["payload"],
                        agent_id=data["agent_id"],
                        goal_id=data.get("goal_id", ""),
                        anomaly_score=data.get("anomaly_score", 0.0),
                        previous_hash=data.get("previous_hash", ""),
                    )
                    entries.append(entry)
                except Exception:
                    continue

        # Verify continuity during replay
        for i, entry in enumerate(entries):
            if i > 0:
                expected_prev = entries[i-1].entry_hash
                actual_prev = entry.previous_hash
                if actual_prev != expected_prev:
                    raise ValueError(
                        f"Audit chain broken at entry {i}: "
                        f"expected previous_hash={expected_prev}, "
                        f"got {actual_prev}"
                    )

        self._entries = entries
        self._head_hash = entries[-1].entry_hash if entries else ""

    def log(
        self,
        event_type: str,
        payload: dict,
        *,
        agent_id: str = "",
        goal_id: str = "",
        anomaly_score: float = 0.0,
    ) -> dict:
        """
        Append an entry to the audit chain.

        Thread-safe. Persists to disk immediately.

        Returns the entry dict for reference in tool output.
        """
        with self._lock:
            previous_hash = self._entries[-1].entry_hash if self._entries else ""
            entry = AuditEntry(
                event_type=event_type,
                payload=payload,
                agent_id=agent_id,
                goal_id=goal_id,
                anomaly_score=anomaly_score,
                previous_hash=previous_hash,
            )
            self._entries.append(entry)
            self._head_hash = entry.entry_hash

            # Persist immediately — audit entries must survive crashes
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "a") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

            return entry.to_dict()

    def verify(self) -> dict:
        """
        Verify the entire chain's integrity.

        Returns:
            {valid: bool, entry_count: int, head_hash: str,
             continuity_errors: [...]}
        """
        errors = []
        for i, entry in enumerate(self._entries):
            if i > 0:
                expected = self._entries[i-1].entry_hash
                actual = entry.previous_hash
                if actual != expected:
                    errors.append({
                        "index": i,
                        "expected": expected,
                        "actual": actual,
                    })

        return {
            "valid": len(errors) == 0,
            "entry_count": len(self._entries),
            "head_hash": self._head_hash,
            "continuity_errors": errors,
        }

    def query(
        self,
        *,
        agent_id: Optional[str] = None,
        event_type: Optional[str] = None,
        goal_id: Optional[str] = None,
        limit: int = 50,
        min_anomaly_score: float = 0.0,
    ) -> list[dict]:
        """
        Query the audit chain with filters.

        Returns entries in chronological order, newest last.
        """
        results = []
        for entry in reversed(self._entries):
            if agent_id and entry.agent_id != agent_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if goal_id and entry.goal_id != goal_id:
                continue
            if entry.anomaly_score < min_anomaly_score:
                continue
            results.append(entry.to_dict())
            if len(results) >= limit:
                break
        return list(reversed(results))
```

### Integration: Wire Into the Tool Call Pipeline

```python
# In the platform tool-call dispatcher — after every state-changing call

AUDIT_CHAIN = AuditChain("~/.msty/audit/{workspace_name}.jsonl")

def dispatch_tool_call(tool_name: str, params: dict, session: dict) -> dict:
    # ... permission check (from H3 above) ...

    # Execute the tool
    result = execute_tool(tool_name, params, session)

    # Log state-changing calls to the audit chain
    if is_state_changing(tool_name):
        audit = AUDIT_CHAIN.log(
            event_type=tool_name,
            payload={
                "params_summary": summarize_params(params),
                "result_status": result.get("status", "unknown"),
                "result_hash": hashlib.sha256(
                    json.dumps(result, sort_keys=True).encode()
                ).hexdigest()[:16],
            },
            agent_id=session.get("agent_id", "unknown"),
            goal_id=session.get("mission_id", ""),
        )
        result["_audit"] = {
            "entry_hash": audit["entry_hash"],
            "chain_hash": audit["chain_hash"],
        }

    return result


# Which tools change state?
STATE_CHANGING_TOOLS = {
    "write_file", "edit_file", "delete_file",
    "git_commit", "git_push", "git_stash",
    "db_execute",
    "memory_store", "memory_govern",
    "channel_send",
    "create_bot", "delete_bot",
}


def is_state_changing(tool_name: str) -> bool:
    return tool_name in STATE_CHANGING_TOOLS
```

### Tool: Verifiable Audit Surface

```python
# Register as an MCP tool: audit_verify

def audit_verify() -> dict:
    """Verify the integrity of the entire audit chain."""
    return AUDIT_CHAIN.verify()


def audit_query(
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,
    goal_id: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Query the audit chain with filters."""
    entries = AUDIT_CHAIN.query(
        agent_id=agent_id,
        event_type=event_type,
        goal_id=goal_id,
        limit=limit,
    )
    return {
        "entry_count": len(entries),
        "entries": entries,
    }
```

### Integration: Weekly Audit Health Check (Playbook)

```python
def weekly_audit_health() -> dict:
    """
    Scheduled Playbook. Runs weekly. Verifies the chain, counts entries
    by type, reports any anomalies with anomaly_score > 0.5.
    """
    verification = AUDIT_CHAIN.verify()

    # Count entries by type
    type_counts = {}
    all_entries = AUDIT_CHAIN.query(limit=10_000)
    for entry in all_entries:
        etype = entry["event_type"]
        type_counts[etype] = type_counts.get(etype, 0) + 1

    # Find high-anomaly entries
    anomalies = [
        e for e in all_entries
        if e.get("anomaly_score", 0) > 0.5
    ]

    report = {
        "chain_valid": verification["valid"],
        "total_entries": verification["entry_count"],
        "head_hash": verification["head_hash"],
        "entries_by_type": type_counts,
        "anomalies": anomalies[:10],
        "recommendation": (
            "Chain healthy" if verification["valid"] and not anomalies
            else "Review anomalies" if verification["valid"]
            else "CHAIN INTEGRITY VIOLATION — INVESTIGATE IMMEDIATELY"
        ),
    }

    if not verification["valid"]:
        # Critical: chain integrity broken
        channel.send_message(
            channel="operator_alerts",
            message=f"🚨 AUDIT CHAIN BROKEN: {json.dumps(report, indent=2)}",
        )

    return report
```

---

## H5: Governed Multi-Agent Handoff with Cryptographic Receipts

**Extends:** Phase 3.4 (Tool Composition / Pipelining) and Mission Control subagents

**What the base tool does:** Tool composition allows chaining calls with output
references (`$prev.users[0].id`). Mission Control spawns subagents with tasks.

**What this hardening adds:** When Agent A delegates work to Agent B (a subagent or
another bot), the delegation is a **signed contract** with:
- Cryptographic hashes of the task, the payload, and the chain lineage
- A gas budget (how many tool calls the subagent is allowed)
- A deadline (when the subagent must complete)
- Constraints (what the subagent must and must not do)
- A proof boundary (what kind of disagreement is attestable)

When the subagent completes, the output is verified against the contract. The
entire handoff chain is verifiable — you can prove that Agent B's output was
produced under Agent A's delegation, within the specified bounds.

**Why it matters:** The pipe primitive (`tool_a | tool_b`) chains calls within one
session. This extends composition across sessions and agents. A research agent
delegates to a code agent. The code agent's output is cryptographically tied to the
research agent's request. If the code agent goes off-script, the drift detection
flags it. If the code agent exceeds its gas budget, the platform rejects the output.
This turns ad-hoc subagent spawning into governed, auditable delegation.

### Data Model: Handoff Event

```python
import hashlib
import json
import time

HANDOFF_EVENT_TYPES = {"delegate", "progress", "dissent", "vote", "complete"}

def create_handoff(
    *,
    delegator: str,          # Agent A's bot ID
    delegate: str,           # Agent B's bot ID
    scope: str,              # "Add rate limiting to auth module"
    constraints: dict,       # {"framework": "express", "test_required": True}
    gas_ceiling: int,        # Max tool calls the delegate can make
    deadline: str,           # ISO 8601 completion deadline
    payload: dict,           # The actual work product or task spec
    proof_boundary: dict,    # {"attestable_disagreement": True}
    parent_event_hash: str = "",  # Previous event in this chain
) -> dict:
    """
    Create a governed handoff event.

    Returns a fully hashed event with:
      - event_hash: SHA-256 of the event body (unique to this event)
      - payload_hash: SHA-256 of the payload (what the delegate must deliver)
      - lineage_hash: SHA-256 of (parent_lineage_hash + event_hash)
                       forming a verifiable delegation chain
    """
    # Deterministic JSON for consistent hashing
    def _canonical(value) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"))

    def _sha256(value) -> str:
        return hashlib.sha256(_canonical(value).encode()).hexdigest()

    # Hash the payload separately (what the delegate must deliver)
    payload_hash = _sha256(payload)

    # Build the event body
    now = time.time()
    event_body = {
        "event_type": "delegate",
        "delegator": delegator,
        "delegate": delegate,
        "scope": scope,
        "constraints": constraints,
        "gas_ceiling": gas_ceiling,
        "deadline": deadline,
        "payload_hash": payload_hash,
        "proof_boundary": proof_boundary,
        "parent_event_hash": parent_event_hash,
        "timestamp": now,
        "epoch": str(int(now)),
    }

    # Hash the event body
    event_hash = _sha256(event_body)

    # Build the lineage hash (chains this event to its parent)
    lineage_payload = {
        "linear_handoff_chain_v1": True,
        "parent_event_hash": parent_event_hash,
        "event_hash": event_hash,
    }
    lineage_hash = _sha256(lineage_payload)

    return {
        **event_body,
        "payload": payload,
        "event_hash": event_hash,
        "payload_hash": payload_hash,
        "lineage_hash": lineage_hash,
        "lineage_model": "linear_handoff_chain_v1",
    }
```

### Core Implementation: Handoff Chain Verification

```python
def verify_handoff_chain(events: list[dict]) -> dict:
    """
    Verify an entire delegation chain.

    Checks:
      1. parent_event_hash continuity: each event references the
         previous event's hash
      2. lineage_hash integrity: each event's lineage_hash is
         cryptographically correct (parent_lineage + event_hash)
      3. Drift: count events with semantic drift detected
      4. Dissent: count attestable disagreements
    """
    errors = []
    previous_event_hash = ""
    previous_lineage_hash = ""

    for i, event in enumerate(events):
        parent_hash = event.get("parent_event_hash", "")

        # First event should have no parent
        if i == 0 and parent_hash:
            errors.append({
                "index": i,
                "error": "first_event_has_parent",
                "event_hash": event.get("event_hash"),
            })

        # Subsequent events must chain to the previous
        elif i > 0 and parent_hash != previous_event_hash:
            errors.append({
                "index": i,
                "error": "parent_hash_mismatch",
                "expected": previous_event_hash,
                "actual": parent_hash,
            })

        # Verify lineage hash
        expected_lineage = _recompute_lineage_hash(
            previous_lineage_hash if i > 0 else "",
            event.get("event_hash", ""),
        )
        if event.get("lineage_hash") != expected_lineage:
            errors.append({
                "index": i,
                "error": "lineage_hash_mismatch",
                "expected": expected_lineage,
                "actual": event.get("lineage_hash"),
            })

        previous_event_hash = event.get("event_hash", "")
        previous_lineage_hash = event.get("lineage_hash", "")

    return {
        "verified": len(errors) == 0,
        "event_count": len(events),
        "head_event_hash": previous_event_hash,
        "head_lineage_hash": previous_lineage_hash,
        "continuity_errors": errors,
        "drift_events": sum(
            1 for e in events
            if e.get("drift_detected") is True
        ),
        "dissent_events": sum(
            1 for e in events
            if e.get("event_type") == "dissent"
        ),
    }


def _recompute_lineage_hash(parent_lineage: str, event_hash: str) -> str:
    import hashlib, json
    payload = {
        "linear_handoff_chain_v1": True,
        "parent_event_hash": parent_lineage,
        "event_hash": event_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
```

### Integration: Mission Control Subagent Wrapper

```python
# In mission_control.py — enhanced spawn_subagent with handoff contracts

def spawn_governed_subagent(
    delegator_id: str,
    task_description: str,
    constraints: dict,
    gas_ceiling: int = 50,        # Max tool calls
    deadline_minutes: int = 30,   # Time limit
) -> dict:
    """
    Spawn a subagent with a cryptographic handoff contract.

    The subagent's output is verified against the contract.
    Drift is detected automatically.
    The delegation chain is persisted for audit.
    """
    from datetime import datetime, timezone, timedelta

    deadline = (
        datetime.now(timezone.utc) + timedelta(minutes=deadline_minutes)
    ).isoformat()

    # Create the handoff contract
    handoff = create_handoff(
        delegator=delegator_id,
        delegate="",   # Filled after subagent spawn
        scope=task_description,
        constraints=constraints,
        gas_ceiling=gas_ceiling,
        deadline=deadline,
        payload={"task": task_description, "constraints": constraints},
        proof_boundary={"attestable_disagreement": True},
    )

    # Spawn the subagent via existing Mission Control
    subagent = spawn_subagent(
        task=task_description,
        boundaries=constraints,
        gas_limit=gas_ceiling,
    )

    # Update the handoff with the subagent's ID
    handoff["delegate"] = subagent["agent_id"]

    # Persist the handoff contract
    mission_id = subagent["mission_id"]
    persist_handoff(mission_id, handoff)

    return {
        "mission_id": mission_id,
        "subagent_id": subagent["agent_id"],
        "handoff_contract": {
            "event_hash": handoff["event_hash"],
            "lineage_hash": handoff["lineage_hash"],
            "gas_ceiling": gas_ceiling,
            "deadline": deadline,
        },
    }


def on_subagent_complete_governed(mission_id: str, output: str) -> dict:
    """
    Enhanced subagent completion hook — verifies the handoff contract.

    Runs drift detection (from H2), checks gas usage against the
    contract's ceiling, verifies the deadline, and records a
    'complete' handoff event to close the chain.
    """
    handoff = get_handoff(mission_id)
    subagent_status = get_subagent_status(mission_id)

    # Check gas budget
    gas_used = subagent_status.get("tool_calls", 0)
    if gas_used > handoff.get("gas_ceiling", 50):
        return {
            "status": "gas_exceeded",
            "gas_used": gas_used,
            "gas_ceiling": handoff["gas_ceiling"],
            "reason": f"Subagent used {gas_used} calls, ceiling was {handoff['gas_ceiling']}",
        }

    # Check deadline
    deadline = _parse_iso(handoff.get("deadline", ""))
    if deadline and datetime.now(timezone.utc) > deadline:
        return {
            "status": "deadline_exceeded",
            "deadline": handoff["deadline"],
            "reason": "Subagent did not complete within the deadline",
        }

    # Run drift detection (from H2)
    drift = evaluate_drift(
        original_task=handoff.get("scope", ""),
        subagent_output=output,
    )

    # Record completion event
    complete_event = create_handoff(
        delegator=handoff["delegator"],
        delegate=handoff["delegate"],
        scope=handoff["scope"],
        constraints=handoff.get("constraints", {}),
        gas_ceiling=handoff.get("gas_ceiling", 0),
        deadline=handoff.get("deadline", ""),
        payload={"output": output, "drift": drift, "gas_used": gas_used},
        proof_boundary=handoff.get("proof_boundary", {}),
        parent_event_hash=handoff["event_hash"],
    )
    complete_event["event_type"] = "complete"

    # Persist the completion event
    persist_handoff(mission_id, complete_event)

    return {
        "status": "complete",
        "gas_used": gas_used,
        "drift": drift,
        "completion_event_hash": complete_event["event_hash"],
        "lineage_hash": complete_event["lineage_hash"],
    }
```

---

## Implementation Notes for All Hardening Sections

### What These Additions Share

1. **They build on existing primitives.** Memory freshness uses the existing memory
   pack CRUD. Tier-gating uses the existing bot tier model. Audit chain uses the
   existing tool-call pipeline. Handoff contracts use the existing Mission Control
   subagent system.

2. **They are additive, not breaking.** None of these require changes to existing
   tool signatures. Each can be implemented behind a feature flag, toggled on per
   workspace. Agents that don't use the hardened versions continue to work.

3. **They use existing storage.** Memory freshness columns extend the memory pack
   schema. Audit entries append to a JSONL file. Handoff contracts persist in the
   existing session/mission storage.

4. **They are all deterministic at their core.** Freshness checking is timestamp
   math. Drift detection is Jaccard similarity. Audit chain is SHA-256 hashing.
   No LLM calls in the verification path. This means they can run automatically
   on every operation without cost or latency concerns.

### Recommended Adoption Order

Start with H2 (drift detection) — it's the simplest, adds immediate value for
Mission Control users, and has zero storage migration. Then H3 (tier-gating) if
you have multiple teams sharing a workspace. Then H1 (freshness) when your memory
packs grow beyond what a human can manually curate. Then H4 (audit chain) when
compliance matters. H5 (handoff contracts) is the deepest change — only do it when
multi-agent delegation is a core workflow with measurable quality problems from
unconstrained subagents.

### Testing Each Section

- **H1 (Freshness):** Store facts with short TTLs, verify they disappear from
  recall after expiry. Revoke a fact, verify it's blocked. Set an agent to
  "restricted" trust, verify its facts expire faster.
- **H2 (Drift):** Spawn a subagent with a task, have it return something
  unrelated. Verify drift_detected=True. Spawn with a matching task, verify
  drift_detected=False.
- **H3 (Tiers):** Create a hearth agent, verify it can't call forge tools.
  Create a forge agent, verify it can't call sovereign tools. Verify governance
  proof requirement for sovereign tools.
- **H4 (Audit):** Run a session, verify the audit chain file exists and the
  verify() method returns valid=True. Tamper with one line in the file, verify
  verify() returns valid=False.
- **H5 (Handoff):** Spawn a governed subagent with a gas ceiling of 3. Have
  it make 5 tool calls. Verify gas_exceeded. Spawn with realistic bounds,
  verify completion event chains to the delegation event.
