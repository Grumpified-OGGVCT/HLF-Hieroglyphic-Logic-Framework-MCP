# HLF Quick Start

> Describe what you want. Get a governed result. Read what happened.

## Install

```bash
uv sync
```

## Use

```bash
# Via MCP (VS Code, Claude Desktop, any MCP client)
uv run hlf-mcp
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
matches the default install path in `pyproject.toml` instead of the older
legacy `hlf.mcp_server_complete` entry path.

## Options

| Parameter | Default | What it does |
|-----------|---------|--------------|
| `intent`  | *(required)* | What you want, in English |
| `tier`    | `"forge"` | Security tier: `hearth` / `forge` / `sovereign` |
| `dry_run` | `false` | Preview what would happen without executing |
| `show_hlf`| `false` | Show the generated HLF source (for the curious) |

## Examples

```
"Read /var/log/system.log and report the top 10 errors"
"Write a config file to /tmp/app.conf"
"Deploy the stack with consensus vote"
"Delegate summarization to the scribe agent, high priority"
"Validate the database migration, read-only"
```

## What's happening behind the scenes

When you call `hlf_do`, HLF:
1. **Compresses** your English into governed HLF v3 glyphs (Shannon entropy minimization)
2. **Scores confidence** (KL-divergence-inspired threshold — rejects below 0.70)
3. **Validates** against the v3 glyph/tag grammar (header, glyphs, tags, terminator)
4. **Checks gas budget** against your tier (hearth=1K, forge=10K, sovereign=100K)
5. **Compiles** to bytecode via the 5-pass pipeline
6. **Executes** in the sandboxed VM
7. **Returns** an English audit trail with math metrics (entropy, compression, gas used)

Like the logograms in *Arrival*: you speak in sentences, HLF thinks in
symbols, and the math guarantees the meaning survives the translation.

## Want to go deeper?

- `show_hlf: true` — see the glyph source HLF generated
- `hlf_translate_to_hlf` — write HLF manually from English
- `hlf_compile` / `hlf_execute` — full compiler control
- `hlf_validate` — validate HLF source directly
- See [README.md](README.md) for the packaged 26-tool FastMCP reference and the broader repo context
