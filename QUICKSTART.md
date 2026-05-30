# HLF Quick Start

> Describe what you want. Get a governed result. Read what happened.
>
> MCP is the initial HLF delivery mouthpiece through Grumprolled: the immediate proof bar is native-agent usability through the packaged MCP surface, not full HLF restoration.

## Install

```bash
uv sync
```

## Use

```bash
# Via MCP (VS Code, Claude Desktop, any MCP client)
uv run hlf-mcp
```

## Native MCP client onboarding

The repo `.mcp.json` is the default native-agent entry point. From this
repository root, a fresh MCP client can load:

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

For VS Code, the workspace `.vscode\mcp.json` already points at the same
packaged server with `cwd` set to the workspace folder. For other clients, add
the same `hlf-mcp` server entry to that client's MCP config while keeping the
working directory at this repo root. If a client cannot set a working directory,
put the repo path only in your private local client config; do not commit that
machine-specific path. If you prefer the installed package entry point and have
`uv` available, `uv run hlf-mcp` remains equivalent.

First contact for a non-building agent:

1. Initialize the `hlf-mcp` MCP server from `.mcp.json`.
2. List prompts and apply `hlf_native_agent` for the session.
3. List or read resources and start with `hlf://agent/quickstart`,
   `hlf://agent/protocol`, `hlf://agent/current_authority`, and
   `hlf://agent/handoff_contract`.
4. Use `hlf_do` for the one-call native loop, or use
   `hlf_translate_to_hlf -> hlf_validate/hlf_lint -> hlf_compile ->
   execute/coordinate -> human NLP audit`.
5. For sub-agent or swarm handoff, pass raw HLF plus validation/compile proof;
   prose is explanatory, not the authoritative machine payload.

For packaged HTTP bring-up verification:

```bash
# Windows (PowerShell)
$env:HLF_TRANSPORT='sse'
$env:HLF_PORT='8011'
python -m hlf_mcp.server

# Mac/Linux (bash/zsh)
export HLF_TRANSPORT=sse
export HLF_PORT=8011
python -m hlf_mcp.server

# In another terminal
curl http://localhost:8011/health
```

Expected result:

```json
{"status":"ok","transport":"sse"}
```

Then call `hlf_do`:

```json
{
  "intent": "Audit /etc/config.json, read-only, and get a report."
}
```

That's it. You get back:

```json
{
  "success": true,
  "you_said": "Audit /etc/config.json, read-only, and get a report.",
  "what_hlf_did": "This will audit '/etc/config.json' in read-only mode ...",
  "audit": "GOVERNED — validated and compiled. Gas estimate: 8. ...",
  "tier": "forge",
  "governed": true,
  "math": {
    "confidence": 0.92,
    "entropy_english_bpc": 4.125,
    "entropy_hlf_bpc": 5.157,
    "compression_ratio": -2.04,
    "gas_estimate": 8,
    "gas_budget": 10000
  }
}
```

No glyphs. No bytecode. No compiler knowledge required.
The `math` block shows Shannon entropy, confidence, and gas metering — the
information-theoretic engine running underneath.

The packaged FastMCP server now exposes `hlf_do` directly, so this quick start
matches the default install path in `pyproject.toml`. The latest audited packaged
MCP surface is **84 tools, 87 resources, and 1 prompt**; use the live registry
and generated instructions as the source of truth when that surface changes.

The older `hlf.mcp_server_complete` entry path is retained only for
compatibility and manual legacy probes. It is not the normal install path, the
default runtime surface, or the right basis for present-tense product claims.

## Why This Matters

The same packaged MCP surface you can install is already used in a bounded build-assist loop inside this repo.

Today that means HLF can help with:

- expressing build intent in plain language through `hlf_do`
- observing repo health through `_toolkit.py status`
- reading regression state through `hlf_test_suite_summary`
- preserving build evidence through witness, memory, and audit surfaces
- validating packaged HTTP bring-up through the bounded `/health` probe before making stronger remote claims

For operator review, the packaged status surfaces now share one visible persona-review contract:

- `uv run hlf-operator provenance-summary --json` exposes the provenance contract plus `persona_contract_summary`
- `uv run hlf-operator witness-status --json` exposes witness status plus `persona_review_summary`
- `uv run hlf-operator approval-review --json` exposes approval review plus the same persona-review rollup

The coordination and software-design lanes also have named operator entrypoints now:

- `uv run hlf-operator governed-route --json` exposes routing evidence, fallback summary, and policy-basis summary
- `uv run hlf-operator instinct-status --json` exposes the packaged Instinct lifecycle mission surface with proof state, blockers, CoVE posture, and seal evidence

The proof and drift lanes now have the same first-class operator treatment:

- `uv run hlf-operator formal-verifier --json` exposes solver status plus recent proof evidence
- `uv run hlf-operator entropy-anchor --json` exposes recent drift evaluations plus their audit-linked evidence

That is the current honest milestone: local, bounded, governed build assistance first.

It is already useful, already demonstrable, and already relevant to the finished product story.

For the fuller explanation, read `docs/HLF_RECURSIVE_BUILD_STORY.md`.
For the audience-specific phrasing guide, read `docs/HLF_MESSAGING_LADDER.md`.

## Options

|Parameter|Default|What it does|
|---|---|---|
|`intent`|*(required)*|What you want, in English|
|`tier`|`"forge"`|Security tier: `hearth` / `forge` / `sovereign`|
|`dry_run`|`false`|Preview what would happen without executing|
|`show_hlf`|`false`|Show the generated HLF source (for the curious)|

## Examples

```text
"Read /var/log/system.log and report the top 10 errors"
"Write a config file to /tmp/app.conf"
"Deploy the stack with consensus vote"
"Delegate summarization to the scribe agent, high priority"
"Validate the database migration, read-only"
```

## What's happening behind the scenes

When you call `hlf_do`, HLF performs the native
NLP -> HLF -> validate/correct -> execute/audit -> NLP loop:

1. **Compresses** your English into governed HLF v3 glyphs (Shannon entropy minimization)
2. **Scores confidence and corrects or rejects** weak translations before execution
3. **Validates** against the v3 glyph/tag grammar (header, glyphs, tags, terminator)
4. **Checks gas budget** against your tier (hearth=1K, forge=10K, sovereign=100K)
5. **Compiles** to bytecode via the 5-pass pipeline
6. **Executes or coordinates** through packaged governed surfaces
7. **Audits** with proof, math metrics, and authority context
8. **Returns** a human-readable NLP summary of what happened

Like the logograms in *Arrival*: you speak in sentences, HLF thinks in
symbols, and the math guarantees the meaning survives the translation.

## Want to go deeper?

- `show_hlf: true` — see the glyph source HLF generated
- `hlf_translate_to_hlf` — write HLF manually from English
- `hlf_compile` / `hlf_execute` — full compiler control
- `hlf_validate` — validate HLF source directly
- See [README.md](README.md) for broader repo context; use this quick start, the live MCP registry, and `SSOT_HLF_MCP.md` for current surface counts and claim lanes
