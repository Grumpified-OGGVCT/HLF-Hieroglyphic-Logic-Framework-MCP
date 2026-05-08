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

## Fast Onboarding Checklist

If you have 10 minutes:

1. Read `README.md`.
2. Read `SSOT_HLF_MCP.md`.
3. Read `HLF_CANONICALIZATION_MATRIX.md`.
4. Inspect `hlf_mcp/server.py`.
5. Inspect `hlf_mcp/hlf/compiler.py` and `hlf_mcp/hlf/runtime.py`.

If you have 30 minutes and need broader context:

1. Read the 10-minute set.
2. Read `docs/AGENTS_CATALOG.md`.
3. Read `hlf_source/config/jules_tasks.yaml`.
4. Read `hlf_source/docs/JULES_COORDINATION.md`.
5. Read `hlf_source/docs/openclaw_integration.md`.

## Why This Document Exists

This repo preserves more than one layer of HLF-related work:

- the live packaged product
- active bridges and migration surfaces
- upstream context from a larger unfinished build

Without an explicit onboarding guide, an unfamiliar agent can either miss important context or over-claim based on preserved reference material.

This document is meant to prevent both failures.
