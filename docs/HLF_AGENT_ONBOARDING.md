# HLF Agent Onboarding

This document is for agents and operators who are new to this repository and need to understand how to use HLF here without confusing the live product surface with preserved reference context.

## What HLF Is In This Repo

HLF in this repository is the language, compiler, runtime, governance, and MCP exposure layer that outside systems can plug into.

It is not the entire sovereign agent operating system.

The live product surface is the packaged `hlf_mcp` line.

## The Three Layers You Will See

### 1. Canonical product layer

Use this for real work, current behavior, and present-tense claims.

- `hlf_mcp/server.py`
- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/hlf/bytecode.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/formatter.py`
- `hlf_mcp/hlf/linter.py`
- `hlf_mcp/hlf/capsules.py`
- `hlf_mcp/hlf/ethics/`
- `governance/`
- `hlf/spec/`

Rule:

- if you are implementing or documenting current HLF behavior, start here

### 2. Compatibility and bridge layer

These files are retained for compatibility, migration, adapters, metrics glue,
and manual legacy validation. They are not the product authority and should not
be your default starting point unless the task explicitly requires legacy
behavior.

- `hlf/mcp_server_complete.py`
- `hlf/mcp_tools.py`
- `hlf/mcp_resources.py`
- `hlf/mcp_prompts.py`
- `hlf/mcp_metric.py`
- `hlf/mcp_metrics.py`
- `hlf/host_functions_minimal.py`
- `hlf/profiles.py`
- `hlf/profile_config.py`
- `hlf/sqlite_hot_store.py`
- `hlf/stores/sqlite_hot_store.py`
- `hlf/ollama_cloud_gateway.py`
- `hlf/infinite_rag_hlf.py`
- `hlf/vm/`

Rule:

- use these only when the task needs compatibility semantics, adapters, migration targets, or legacy probes
- do not let them outrank `hlf_mcp` when deciding current truth

### 3. Preserved upstream context layer

This is mostly under `hlf_source/`.

It contains real work from a deeper unfinished build and is worth preserving, but it is not the live contract of this repo.

Use it for:

- archaeology
- operator context
- design intent
- selective extraction of still-useful semantics

Do not use it as the first source for present-tense product claims.

## How An Unfamiliar Agent Should Work Here

### If your task is about current HLF behavior

Read these first:

- `README.md`
- `SSOT_HLF_MCP.md`
- `HLF_CANONICALIZATION_MATRIX.md`
- `hlf_mcp/server.py`
- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/runtime.py`
- `governance/host_functions.json`
- `governance/align_rules.json`
- `governance/tag_i18n.yaml`

### If your task is about broader system usage or why HLF was built this way

Read these preserved context files:

- `hlf_source/config/agent_registry.json`
- `hlf_source/config/jules_tasks.yaml`
- `hlf_source/docs/JULES_COORDINATION.md`
- `hlf_source/docs/openclaw_integration.md`
- `hlf_source/agents/gateway/router.py`
- `hlf_source/agents/core/formal_verifier.py`
- `docs/AGENTS_CATALOG.md`

These explain:

- how agents were role-specialized around HLF work
- how sequential pipelines and merge policy were supposed to operate
- how gas, tiers, routing, and external-tool use fit around HLF
- how formal verification was intended to connect to HLF constraints

## Practical Use Flow

When acting as an unfamiliar agent, the safest practical flow is:

1. Start from natural-language intent.
2. Prefer the packaged front door when possible.
3. Compile and validate before making claims about execution.
4. Respect capsule and governance boundaries.
5. Use `hlf_source` only to answer why something exists or how the larger system once intended to use it.

In concrete repo terms:

1. Use `hlf_do` or the packaged translation/compiler surfaces first.
2. Validate against packaged governance assets.
3. Treat `hlf_mcp/hlf/runtime.py` as the execution truth.
4. Consult `hlf/vm/` and `hlf_source/` only if you need migration or archaeology context.

## Native MCP First Contact

For non-building agents, MCP is the clean front door. You should not need source
edits, admin rights, or build permissions to discover the HLF-native surface.

### Client config

Use the repo `.mcp.json` from this repository root:

```json
{
  "mcpServers": {
    "hlf-mcp": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "hlf_mcp.server"],
      "env": { "HLF_TRANSPORT": "stdio" }
    }
  }
}
```

VS Code users can use `.vscode\mcp.json`, which points to the same packaged
`python -m hlf_mcp.server` entry point with workspace-local `cwd`. If your MCP
client cannot set a working directory, copy the same entry into private local
client config and add this checkout path there. Keep that absolute path out of
committed repo config. If you prefer the installed package entry point and have
`uv` available, `uv run hlf-mcp` remains equivalent.

### Discovery sequence

1. Initialize server `hlf-mcp`.
2. List prompts and load `hlf_native_agent`.
   - FastMCP/MCP returns prompt text in `messages[0].content.text` from
     `prompts/get`; there is no top-level `content` field.
   - If a client lists the prompt but displays empty prompt content, read
     `hlf://agent/quickstart` and use
     `prompt_content_fallback.prompt_text` as the explicit resource fallback
     for `hlf_native_agent`.
3. List resources and read these first:
   - `hlf://agent/quickstart`
   - `hlf://agent/protocol`
   - `hlf://agent/current_authority`
   - `hlf://agent/handoff_contract`
4. List tools and prefer:
   - `hlf_do` for the packaged natural-language front door
   - `hlf_translate_to_hlf`
   - `hlf_validate`
   - `hlf_lint`
   - `hlf_compile`
   - packaged execution, routing, approval, witness, and audit/status surfaces
     as reported by `hlf://status/operator_surfaces`

### Native loop

The required operating loop for substantive work is:

```text
NLP intent
  -> HLF translation
  -> validate/lint/correct/compile gates
  -> governed execute or coordinate
  -> audit/proof/status evidence
  -> NLP explanation for humans
```

Use `hlf_do` when you want that loop in one call. Use the explicit tool chain
when another agent needs raw HLF, AST/bytecode proof, or a handoff contract.
For sub-agent or swarm handoff, raw HLF plus validation/compile proof is the
authoritative payload; prose is only an explanation.

## What Not To Confuse

### Do not confuse product truth with preserved ambition

`hlf_source/` includes a much broader sovereign ecosystem. That does not mean all of it is shipped here.

### Do not confuse wrappers with authorities

The legacy `hlf/` MCP stack is compatibility-only unless the task explicitly requires migration, probes, or adapter behavior.

### Do not confuse context-only files with mandatory integration targets

Some `hlf_source` files are valuable for understanding the bigger build, but not every one of them belongs in `hlf_mcp`.

## Non-HLF Context That Still Matters

The broader failed build left behind non-HLF assets that are still important for understanding use patterns.

The most valuable ones are:

- `hlf_source/config/agent_registry.json`
  Why it matters: shows the role map, skill division, and model/tier expectations around HLF-centered work.

## Claim Discipline

When writing or repeating architecture, product, or MCP-positioning statements from this repo, use `docs/HLF_CLAIM_LANES.md` to decide whether the statement is current-true, bridge-true, vision-true, partially overstated, or reductionist.

This matters because onboarding docs are often reused as shorthand, and shorthand is where mixed-lane phrasing hardens fastest.

- `hlf_source/config/jules_tasks.yaml`
  Why it matters: shows the intended autonomous pipeline, invariants, anti-simplification guardrails, and where HLF maximization fits.

- `hlf_source/docs/JULES_COORDINATION.md`
  Why it matters: shows branch ownership, PR coordination, and handoff protocol between collaborating agents.

- `hlf_source/docs/openclaw_integration.md`
  Why it matters: shows governed external binary usage, host-function restrictions, and tool-sandbox expectations.

- `hlf_source/agents/gateway/router.py`
  Why it matters: shows practical routing, gas, tier, and model-allowlist logic around HLF execution.

- `hlf_source/agents/core/formal_verifier.py`
  Why it matters: shows how HLF constraints were expected to tie into formal proof and verification workflows.

## Default Decision Rules

Use these by default unless the task clearly requires archaeology.

- Current behavior: trust `hlf_mcp`.
- Current runtime and `.hlb` contract: trust `hlf_mcp/hlf/runtime.py` and `hlf_mcp/hlf/bytecode.py`.
- Governance truth: trust `governance/` in the current repo.
- Profile/store/gateway support logic: preserve and evaluate as compatibility helpers, but do not silently elevate over the packaged surface.
- Upstream/source ecosystem behavior: treat as context until explicitly ported.

## Enterprise Tools (Available via MCP listTools)

These tools were built during the enterprise hardening sprint (Commits 1-8).
All 313 tests pass (274 hardening + 39 CLI). Authentication is required for HTTP
transports via `HLF_API_TOKEN`.

### How to read the tool tables

Every tool entry includes:
- **Tier**: Minimum agent tier required (`hearth` < `forge` < `sovereign`).
  A hearth agent will NOT see sovereign tools in `listTools`.
- **Callability**: Whether the tool can be called directly without preamble.
  - `[callable]` — Invoke immediately, no HLF knowledge needed.
  - `[compile-required]` — Must pass HLF-compiled intent first.
  - `[HITL-gated]` — Requires human operator approval. Agent will block until approved.
  - `[operator-only]` — Sovereign tier only. Calling as a lower tier returns nothing (tool invisible).
- **Error surface**: What to expect when things go wrong (not a complete list, but the common failures).

### HITL Gate (Commit 1) — Human-in-the-loop approval/rejection

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_hitl_approve(capsule_id, reason)` | sovereign | [operator-only] [HITL-gated] | Approve a gated capsule for execution. The operator's signature is recorded in the Merkle chain. |
| `hlf_hitl_reject(capsule_id, reason)` | sovereign | [operator-only] [HITL-gated] | Reject with mandatory reason. Capsule status changes to REJECTED and gas is NOT consumed. |
| `hlf_hitl_list(status)` | hearth | [callable] | List capsules by HITL status: pending, approved, rejected. |

**Call pattern:**
```
hlf_hitl_list(status="pending") → find capsule needing approval
hlf_hitl_approve(capsule_id="abc123", reason="Diagnosis matches ground truth") → approve
hlf_hitl_list(status="approved") → verify it took
```

**Common errors:**
- `"capsule not found"` — Double-check the capsule_id. Partial match supported.
- `"already approved"` — Idempotent; re-approving returns OK.
- `"reason required for rejection"` — `hlf_hitl_reject` demands a non-empty reason.

**Important:** An agent must NEVER call `hlf_hitl_approve` on its own capsule. The tier gate prevents this for non-sovereign tiers, but stdio/local dev defaults to sovereign. The audit trail records WHO approved — self-approval is detectable in post-hoc review.

### Chaos Engineering (Commit 2) — Resilience status

| Tool | Tier | Callability |
|------|------|-------------|
| `hlf_chaos_status()` | hearth | [callable] |

**What it returns:** Current chaos engineering readiness: OOM resilience active, VRAM cleanup active, graceful degradation active. All 15 chaos tests pass.

**When to call:** Before running a load test or A/B benchmark. If chaos status shows degraded resilience, do not proceed — fix the underlying issue first.

### Model Version Pinning (Commit 3) — Manifest integrity

| Tool | Tier | Callability |
|------|------|-------------|
| `hlf_model_version_check(model_name)` | hearth | [callable] |

**What it does:** Verifies installed Ollama model digests against the governance manifest (`governance/model_versions.json`). Returns match/mismatch/digest for each model.

**When to call:** After `ollama pull`, before governed inference. A digest mismatch means the model changed upstream — inference proceeds but the event is logged as a governance anomaly. A missing model returns `not_installed`.

### Latent Evidence (Commit 4) — Provenance audit

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_evidence_show(capsule_id, show_latent)` | hearth | [callable] | Retrieve a capsule trace with provenance trail, Merkle chain integrity, adapter hashes, and gas accounting. |
| `hlf_evidence_list(limit)` | hearth | [callable] | List recent capsule traces from the observability JSONL store. |
| `hlf_evidence_verify(capsule_id)` | hearth | [callable] | Verify a capsule's Merkle chain integrity. Returns chain_status: intact/broken/missing. |

**Call pattern (full audit):**
```
hlf_evidence_list(limit=20) → get recent capsule IDs
hlf_evidence_show(capsule_id="6b7f9ce36d94e0ee", show_latent=True) → full provenance with handoffs
hlf_evidence_verify(capsule_id="6b7f9ce36d94e0ee") → confirm chain intact
```

**When `show_latent=True`:** Renders full handoff trail: agent names, model names with dimensionality (e.g., `2048d`), adapter names resolved from checkpoint filenames, gas per handoff, provenance hashes. No JSON brackets, no raw tensor dumps.

**When `show_latent=False` (default):** One-line summary: `"Latent recursion: 2 rounds, 6 handoffs, 150 gas. Use --latent for details."`

**Error cases:**
- `"not_found"` — Capsule ID doesn't exist in the JSONL store.
- `"⚠ HASH MISMATCH"` — Handoff hash doesn't match chain. Chain integrity broken. This is a forensic alert.
- `"UNKNOWN"` adapter hash — Checkpoint was loaded before the hash registry existed.

### Secret Management (Commit 5) — AES-256-GCM encrypted secrets

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_secret_store(key, value, ttl_seconds)` | sovereign | [operator-only] | Encrypt and store a secret with AES-256-GCM. Returns a secret_hash for audit. |
| `hlf_secret_retrieve(key)` | forge | [compile-required] | Retrieve and decrypt a stored secret. Decryption failure returns `InvalidTag` wrapped as `SecretCapsuleError`. |
| `hlf_secret_rotate(key)` | sovereign | [operator-only] | Rotate encryption (fresh key, salt, nonce). Old ciphertext is re-encrypted. |

**Call pattern:**
```
hlf_secret_store(key="api_key", value="sk-abc123", ttl_seconds=86400)
  → {"status": "ok", "secret_hash": "sha256:def456..."}

hlf_secret_retrieve(key="api_key")
  → {"status": "ok", "value": "sk-abc123", "secret_hash": "sha256:def456..."}

hlf_secret_rotate(key="api_key")
  → {"status": "ok", "old_hash": "sha256:def456...", "new_hash": "sha256:789abc..."}
```

**Important:** `hlf_secret_retrieve` is forge-tier (not hearth) because decrypted secrets leave the capsule boundary. The audit trail records every retrieval. `hlf_secret_store` is sovereign-tier because creating secrets is a trust root operation.

**TTL behavior:** Secrets expire after `ttl_seconds`. Retrieval after expiry returns `"expired"`. Default TTL is 3600s (1 hour). Set `ttl_seconds=0` for no expiry.

### Merkle Disaster Recovery (Commit 6) — Signed backup/restore

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_merkle_export(chains, output_dir)` | forge | [callable] | Export signed Merkle chain backups with HMAC-SHA256 signatures to Parquet+manifest. |
| `hlf_merkle_verify(backup_dir)` | forge | [callable] | Verify backup integrity and validate HMAC signatures. Returns chain_status per chain. |
| `hlf_merkle_chain_status()` | hearth | [callable] | List all active Merkle chains with current root hashes. |

**DR workflow (the 3 AM scenario):**
```
hlf_merkle_chain_status()
  → {"chains": {"latent_traces.jsonl": "sha256:abc...", "hlf_mcp.audit.jsonl": "sha256:def..."}}

hlf_merkle_export(chains=["latent_traces.jsonl"], output_dir="./backups/")
  → {"status": "ok", "manifest": "./backups/merkle_manifest.json", "chains_exported": 1}

# Disaster happens. Database is corrupted.

hlf_merkle_verify(backup_dir="./backups/")
  → {"status": "ok", "chains": {"latent_traces.jsonl": "intact"}, "manifest_valid": true}
  # Restores the chain from Parquet export. Runbook covers the SQLite WAL deletion step.
```

**Technical note:** The export uses `write_bytes()` (not `write_text()`) to avoid Windows `\r\n` corruption. The combined root hash is computed from `sorted(chain_hashes)` to guarantee canonical ordering regardless of insertion order — this was the `json.dumps(sort_keys=True)` ordering bug found and fixed in Commit 6.

### Load Testing (Commit 7) — Capsule queue stress test

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_load_test_run(config)` | forge | [callable] | Run a capsule load test with configurable queue depth, gas limits, and backpressure. |
| `hlf_load_test_status()` | forge | [callable] | Get default load test configuration and current queue health. |

**Config options:**
```json
{
  "n_capsules": 50,
  "gas_per_capsule": 500,
  "concurrency": "serial",
  "with_ollama": false
}
```

**Performance reality:** With `with_ollama: false` (VM-only lightweight intents), 50 capsules complete in ~1.6 seconds. With `with_ollama: true` and real model loading, expect minutes per capsule. The 3060 cannot load 50 models concurrently — capsules execute serially by design.

**What to watch:**
- Gas exhaustion: later capsules get `GAS_POOL_EXHAUSTED` if queue drains the pool.
- Timeout: capsules exceeding `timeout_seconds` abort with `TIMEOUT`.
- VRAM: peak VRAM should stay flat; if it climbs with queue depth, VRAM isn't being released between capsules.

### A/B Backend Testing (Commit 8b) — Statistical model comparison

| Tool | Tier | Callability | What it does |
|------|------|-------------|--------------|
| `hlf_ab_test_define(name, domain, backends)` | forge | [callable] | Define a new A/B test comparing Ollama backends. |
| `hlf_ab_test_run(test_name)` | hearth | [callable] | Execute the test against real Ollama backends. Computes Cohen's d, Wilson CI, p-value. |
| `hlf_ab_test_show(test_name)` | hearth | [callable] | Get formatted statistical results with winner and recommendation. |
| `hlf_ab_test_list()` | hearth | [callable] | List all defined A/B test configurations. |

**Call pattern (domain routing discovery):**
```
hlf_ab_test_define(name="medical_v1", domain="medical", backends="medgemma:4b,llama3.2:latest")
  → Test defined, config saved to ~/.hlf/ab_tests/

hlf_ab_test_run(test_name="medical_v1")
  → Runs 10 medical prompts through both backends.
  → Expect ~249 seconds for real Ollama (model loading dominates first calls).
  → Returns: comparisons with Cohen's d, Wilson 95% CI, p-value, winner.

hlf_ab_test_show(test_name="medical_v1")
  → Formatted output:
    medgemma:4b:    0.82 ± 0.06 (95% CI)  ← winner
    llama3.2:latest: 0.45 ± 0.09 (95% CI)
    Cohen's d: 0.95 (large), p < 0.001
    Recommendation: PROMOTE medgemma:4b for medical domain
```

**Built-in domains and their prompt corpora:**
- `medical` — 10 diagnosis/symptom/drug interaction prompts
- `code` — 10 Python function generation prompts
- `math` — 10 math reasoning prompts
- `general` — 10 general knowledge prompts

**Statistical rigor:**
- Wilson score interval for binomial proportions (correct/incorrect per backend)
- Cohen's d effect size (small < 0.5 < medium < 0.8 < large)
- Paired t-test since both backends see the same prompt set
- No promotion if 95% CIs overlap — HKS keeps the incumbent

**The 249-second reality:** Real Ollama benchmarking takes minutes, not milliseconds. The 1.6-second load test (Commit 7) uses lightweight VM intents without model loading. A/B tests call `http://localhost:11434/api/generate` for each prompt×backend combination. With 10 prompts × 2 backends = 20 Ollama calls. Model loading dominates the first few calls per model. Plan accordingly.

### Authentication

For HTTP transports (SSE, streamable-http), set `HLF_API_TOKEN` to require
Bearer token authentication on all requests. The `/health` endpoint is always
exempt. stdio transport never requires authentication.

**Security model — honest limitations:**
This is a single static bearer token. It gates access, not identity.
- Suitable for: single-tenant local deployments, CI pipelines with known agents.
- NOT suitable for: multi-tenant deployments (no per-agent identity), production
  HTTP exposure (no token rotation, expiry, or JWT).
- For multi-tenant: rotate `HLF_API_TOKEN` via your secret manager, or layer an
  external auth proxy (OAuth, mTLS) in front of the MCP server.

**Agent tier resolution:**
- stdio transport: always defaults to `sovereign` (full tool access).
- HTTP transports: respects `HLF_AGENT_TIER` env var (`hearth`, `forge`, `sovereign`).
- A hearth agent calling via HTTP will NOT see `hlf_hitl_approve` in `listTools`.
- Tier is resolved at `register_enterprise_tools()` time — dynamic tool visibility.

```bash
# Enable auth for HTTP transports
export HLF_API_TOKEN="your-secret-token"
export HLF_AGENT_TIER="forge"  # Optional: restrict tool visibility
export HLF_TRANSPORT="sse"
python -m hlf_mcp.server

# Clients must include:
# Authorization: Bearer your-secret-token
```

If `HLF_API_TOKEN` is not set, the server runs without authentication
(backward compatible with local development and stdio usage).

## Fast Onboarding Checklist

If you have 10 minutes:

1. Read `README.md`.
2. Read `SSOT_HLF_MCP.md`.
3. Read `HLF_CANONICALIZATION_MATRIX.md`.
4. Inspect `hlf_mcp/server.py`.
5. Inspect `hlf_mcp/hlf/compiler.py` and `hlf_mcp/hlf/runtime.py`.

If you have 30 minutes and need broader context:

1. Read the 10-minute set.
2. Read the **Enterprise Tools** section above — this tells you what 20 additional MCP tools your agent can call.
3. Read `docs/AGENTS_CATALOG.md`.
4. Read `hlf_source/config/jules_tasks.yaml`.
5. Read `hlf_source/docs/JULES_COORDINATION.md`.
6. Read `hlf_source/docs/openclaw_integration.md`.

If you need to call enterprise tools from an HTTP MCP client:

1. Set `HLF_API_TOKEN` and `HLF_AGENT_TIER` on the server.
2. Include `Authorization: Bearer <token>` in every request.
3. Check `listTools` — you should see only tools visible to your tier.
4. Call `/health` first to confirm the server is up and auth is working.

## Why This Document Exists

This repo preserves more than one layer of HLF-related work:

- the live packaged product
- active bridges and migration surfaces
- upstream context from a larger unfinished build

Without an explicit onboarding guide, an unfamiliar agent can either miss important context or over-claim based on preserved reference material.

This document is meant to prevent both failures.
