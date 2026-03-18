# HLF MCP Agent Handoff

This document is the stable handoff file for other agents that need to understand the whole HLF MCP surface in this repository.

Use it as the first orientation file when an agent needs the current product truth, the repo boundaries, the server assembly shape, and the main operational rules.

It is written to stay useful even as implementation details continue to evolve.

## What This Repo Is

This repository is the standalone HLF MCP server and packaged HLF runtime surface.

It is not the entire sovereign operating system.

The live packaged product surface is `hlf_mcp/`.

The older `hlf/` tree is retained as a compatibility/support line for migration work, legacy probes, and a small set of helpers, but it is not the default product authority or the normal first-stop implementation surface.

## Truth Boundary

When an agent needs to decide what is true now versus what is design context, use these rules:

1. Current product truth lives in `hlf_mcp/`, `governance/`, `tests/`, and the validated packaged docs.
2. Compatibility and bridge logic live in `hlf/` and should only lead when the task is explicitly legacy-facing.
3. Upstream context and broader ambition live in `hlf_source/` and reference docs.

If a current-behavior claim conflicts between `hlf_mcp/` and `hlf/`, trust `hlf_mcp/`.

## Start Here

If you are a new agent, read these in this order:

1. `README.md`
2. `docs/HLF_AGENT_ONBOARDING.md`
3. `SSOT_HLF_MCP.md`
4. `hlf_mcp/server.py`
5. `hlf_mcp/server_core.py`
6. `hlf_mcp/hlf/compiler.py`
7. `hlf_mcp/hlf/runtime.py`
8. `governance/host_functions.json`
9. `governance/align_rules.json`
10. `governance/tag_i18n.yaml`

This file is the shortcut summary of those surfaces, not a replacement for code.

## Server Refactor Status

The `server.py` refactor is structurally in the right place.

### What is already true

- `hlf_mcp/server.py` is now a thin assembly file, not a monolithic implementation file.
- The human-facing instruction payload is now built through `hlf_mcp/server_instructions.py` instead of living inline in `server.py`.
- Tool logic is split into registration modules:
  - `hlf_mcp/server_core.py`
  - `hlf_mcp/server_translation.py`
  - `hlf_mcp/server_memory.py`
  - `hlf_mcp/server_profiles.py`
  - `hlf_mcp/server_instinct.py`
  - `hlf_mcp/server_capsule.py`
- Resource registration is split into `hlf_mcp/server_resources.py`.
- Shared runtime/compiler/state construction is split into `hlf_mcp/server_context.py`.
- `server.py` mainly does five things:
  1. create the FastMCP instance
  2. build shared context
  3. register tools/resources
  4. expose the health wrapper for HTTP transports
  5. choose transport and run the server

### What is still not fully ideal

- The human-facing tool and resource summary is now generated from the registered packaged MCP surface.
- The module still uses `globals().update(...)` for backward-compatible export behavior.

### Practical judgment

The refactor is not broken.

It is functionally complete enough that other work should continue against the split registration modules, not by collapsing logic back into `server.py`.

If a future cleanup happens, the next likely target is reducing the backward-compatible export surface, not undoing the assembly split.

## Canonical Server Assembly

The packaged entrypoint is:

- `hlf_mcp.server:main`

The canonical server file is:

- `hlf_mcp/server.py`

The server currently supports these transports:

- `stdio`
- `sse`
- `streamable-http`

Selection is via environment variables:

- `HLF_TRANSPORT`
- `HLF_HOST`
- `HLF_PORT`

For HTTP transports, `server.py` wraps the MCP app with a `/health` endpoint.

## Main Architectural Surfaces

### 1. Packaged server surface

These files define the live MCP product surface:

- `hlf_mcp/server.py`
- `hlf_mcp/server_context.py`
- `hlf_mcp/server_core.py`
- `hlf_mcp/server_translation.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_profiles.py`
- `hlf_mcp/server_instinct.py`
- `hlf_mcp/server_capsule.py`
- `hlf_mcp/server_resources.py`

### 2. Compiler and execution surface

These files define the current HLF language and execution truth:

- `hlf_mcp/hlf/compiler.py`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/hlf/bytecode.py`
- `hlf_mcp/hlf/formatter.py`
- `hlf_mcp/hlf/linter.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/capsules.py`
- `hlf_mcp/hlf/ethics/`

### 3. Memory and lifecycle surface

- `hlf_mcp/rag/memory.py`
- `hlf_mcp/instinct/lifecycle.py`

### 4. Governance surface

- `governance/align_rules.json`
- `governance/bytecode_spec.yaml`
- `governance/host_functions.json`
- `governance/tag_i18n.yaml`
- `governance/module_import_rules.yaml`
- `governance/MANIFEST.sha256`

## What HLF Means Here

HLF is a deterministic orchestration language.

In this repo it means:

- strict parsing
- compiled AST and bytecode
- bounded execution with gas metering
- explicit governance checks
- capsule-based execution tiers
- auditable host-function dispatch
- translation bridges between natural language and HLF

The most important execution rule is simple:

Natural language is the front door. HLF is the execution contract.

## Current MCP Capability Areas

The packaged server currently exposes tools across these functional groups:

- compile, format, lint, validate, run, benchmark, disassemble, AST submission
- translation and natural-language front door flows
- memory store/query/stats flows
- embedding profile negotiation and test-suite metrics summary
- instinct lifecycle flows
- capsule validation and sandboxed execution flows

Resources expose grammar, governance artifacts, examples, host functions, opcodes, and stdlib references.

Do not rely on this file alone for exact counts. If exact counts matter, inspect the registration modules or query the running server.

## Special Profile and Handshake Work

This repo now includes an embedding-profile negotiation layer.

Primary file:

- `hlf_mcp/server_profiles.py`

Key behavior:

- recommends local embedding setups for known HLF workloads
- probes hardware conservatively
- checks local Ollama availability
- persists negotiated profiles into server context
- makes profile data available to runtime execution paths

This is advisory infrastructure, not a replacement for governance or deterministic runtime behavior.

## Runtime Memory-Aware Delegation and Routing

The runtime now contains optional memory-aware advisory context for delegation and routing.

Primary file:

- `hlf_mcp/hlf/runtime.py`

Important properties:

- deterministic governance remains primary
- semantic memory context is advisory only
- delegation and routing can attach memory context
- negotiated embedding profile summary can flow into runtime scope

This is intentionally fail-open for advisory retrieval and fail-closed for governance blocks.

## Test Authority

The canonical automated suite is now:

- `tests/`

The canonical runner is now:

- `python run_tests.py`
- `python -m hlf_mcp.test_runner`
- `hlf-test-runner`

Suite results are persisted to:

- `~/.sovereign/mcp_metrics/tests.jsonl`
- `~/.sovereign/mcp_metrics/pytest_last_run.json`
- `~/.sovereign/mcp_metrics/pytest_history.jsonl`

Local scheduled weekly artifacts can now also be generated with:

- `python scripts/run_pipeline_scheduled.py`

That writes:

- `~/.sovereign/mcp_metrics/weekly_pipeline_latest.json`
- `~/.sovereign/mcp_metrics/weekly_pipeline_history.jsonl`

The scheduled artifact combines existing surfaces rather than inventing a parallel truth path:

- git branch + commit snapshot
- governance manifest integrity snapshot
- packaged FastMCP tool/resource/export surface counts
- latest persisted pytest summary
- optional `_toolkit.py status` output

There is also an MCP-facing tool for the latest suite summary:

- `hlf_test_suite_summary`

Legacy root-level probe files were moved to:

- `scripts/legacy_probes/`

Those are manual compatibility probes for the older `hlf/` MCP stack, not part of the packaged product regression suite.

## What Other Agents Should Not Do

Other agents should not:

- treat `hlf_source/` as default product truth
- assume the legacy `hlf/` line outranks `hlf_mcp/`
- re-monolithize `server.py`
- bypass governance assets when reasoning about runtime behavior
- confuse manual legacy probes with the canonical automated suite

## What Other Agents Should Do

Other agents should:

- start from `hlf_mcp/`
- use `server.py` only as the assembly map and entrypoint
- make tool behavior changes in the registration modules
- make runtime behavior changes in `hlf_mcp/hlf/runtime.py`
- make language behavior changes in compiler/formatter/linter/translator files
- validate changes with the canonical test runner
- keep docs aligned to the packaged truth boundary

## Best Single File to Hand Another Agent

If you need one file to hand to another agent first, use this one:

- `docs/HLF_MCP_AGENT_HANDOFF.md`

If the agent has time for a second file, hand it:

- `SSOT_HLF_MCP.md`

If the agent needs a practical repo-orientation companion, add:

- `docs/HLF_AGENT_ONBOARDING.md`

## Short Version

If an agent only reads one page of summary, the safe summary is:

- `hlf_mcp/` is the real product surface.
- `server.py` is the assembly layer and is not broken.
- behavior is split into registration modules and runtime/compiler modules.
- `tests/` is the canonical automated suite.
- `scripts/legacy_probes/` is manual legacy compatibility territory.
- governance remains authoritative.
- this file is the durable handoff entrypoint for the whole MCP surface.
