# HLF MCP Build Guide

## Scope

This guide is for the current packaged product surface in `hlf_mcp/`.

- `hlf_mcp/` is the active MCP server, runtime, and test surface.
- `hlf/` remains a compatibility layer and source of legacy probes, not the default build target.
- `scripts/legacy_probes/` contains manual checks for the older stack and is not part of the default automated suite.

## Environment Setup

Preferred local setup uses `uv` and the repo virtual environment.

```bash
cd C:\Users\gerry\generic_workspace\HLF_MCP
uv sync
```

If you are already inside the repo `.venv`, the commands below also work with plain `python`.

## Canonical Test Entry Points

The default automated suite is the pytest tree under `tests/`.

Use one of these entry points:

```bash
python run_tests.py
python -m hlf_mcp.test_runner
hlf-test-runner
uv run pytest tests/ -q --tb=short
```

The packaged test runner persists metrics to:

- `~/.sovereign/mcp_metrics/tests.jsonl`
- `~/.sovereign/mcp_metrics/pytest_last_run.json`
- `~/.sovereign/mcp_metrics/pytest_history.jsonl`

Helpful repo-local commands:

```bash
python _toolkit.py status
python _toolkit.py test
```

## Current Build-Assist Truth

The current packaged repo already supports a local, bounded, governed build-assist loop.

Use this as the first credible recursive-build milestone:

- `python _toolkit.py status` for repo/build-health observation
- `hlf_do` for intent-to-HLF front-door build actions
- `hlf_test_suite_summary` for latest packaged regression summaries
- witness, memory, and audit surfaces for recording build evidence and operator review state

Current transport stance:

---

## 🐕 Recursive Build-Assist (Dogfooding)

The packaged HLF MCP server is now used to help build, test, and explain itself:

- Use `hlf_do`, `_toolkit.py status`, and MCP tools/resources to inspect, test, and explain the system during further development.
- Operator-facing evidence, audit, and regression surfaces are real and queryable.
- `/health` endpoint has been verified on the packaged `hlf_mcp` HTTP/SSE lane with `HLF_TRANSPORT=sse`, `HLF_PORT=8011`, and `GET /health -> 200 OK`.
- This workflow is not full self-hosting, but it is a real recursive build-assist loop: the system is used to help build and verify itself, with each new bridge slice (routing, verification, orchestration, etc.) added and then used to further assist the next round of work.

- `stdio` is the preferred first transport for this recursive build workflow
- `sse` and `streamable-http` health endpoints are still useful for transport bring-up
- do not center the self-build story on remote `streamable-http` until MCP `initialize` succeeds end to end

Health is not the same as full MCP readiness.

## Why Outside Readers Should Care

This build-assist loop is not just an internal convenience.

It is part of the product evidence.

If HLF is meant to become a governed layer between intent and action, one of the strongest bounded proofs of that claim is that the packaged system can already assist with:

- understanding build intent
- inspecting the state of the repo
- summarizing regressions and evidence
- preserving audit trails about what the build learned

That makes the current workflow useful to two audiences at once:

- operators building and recovering HLF now
- future users evaluating whether HLF is actually a trustworthy governed interface

The important distinction is that this repo does not claim full self-hosting.
It claims a staged recursive-build path where stronger claims remain gated by explicit proof.

For the canonical explanation of that claim, read `docs/HLF_RECURSIVE_BUILD_STORY.md`.
For the audience-specific phrasing guide, read `docs/HLF_MESSAGING_LADDER.md`.

## Running the Packaged MCP Server

Primary server entry points:

```bash
uv run hlf-mcp
python -m hlf_mcp.server
```

Transport selection is controlled with environment variables:

- `HLF_TRANSPORT`: `stdio`, `sse`, or `streamable-http`
- `HLF_HOST`: bind host for HTTP transports, default `0.0.0.0`
- `HLF_PORT`: bind port for HTTP transports; required when `HLF_TRANSPORT` is `sse` or `streamable-http`
- `HLF_REMOTE_MODEL_ENDPOINTS`: JSON list of explicit `remote-direct` model endpoints for governed routing and catalog sync

Examples:

```bash
# stdio transport
HLF_TRANSPORT=stdio uv run hlf-mcp

# SSE transport on an explicit chosen port
HLF_TRANSPORT=sse HLF_PORT=<explicit-port> uv run hlf-mcp

# streamable HTTP transport on an explicit chosen port
HLF_TRANSPORT=streamable-http HLF_PORT=<explicit-port> uv run hlf-mcp

# remote-direct operator path
HLF_REMOTE_MODEL_ENDPOINTS='[{"name":"gpt-4.1","endpoint":"https://api.example.test/v1/chat/completions","lanes":["explainer","code-generation"],"capabilities":["reasoning","remote-direct"],"reachable":true}]' uv run hlf-mcp
```

The `HLF_REMOTE_MODEL_ENDPOINTS` contract is consumed by the packaged tools `hlf_sync_model_catalog` and `hlf_route_governed_request`. Use it when you want governed routing to consider explicit remote-direct endpoints in addition to local and cloud-via-ollama candidates. Required-local embedding lanes remain locality constrained unless policy changes upstream.

### Model-role rule

Keep these two layers separate:

- packaged MCP runtime and governed routing defaults under `hlf_mcp/`
- stronger cloud user-agent guidance and controller chains under `.github/scripts/ollama_client.py`

The packaged MCP surface may use local Ollama models and explicit remote-direct endpoints when admitted by policy.
That is not the same thing as the repo's stronger cloud guidance for planner, doer, or controller roles.

Current dependency boundary:

- the packaged MCP server works without any locally tuned HLF-specialized model
- current operator guidance is cloud-first for planning, doer, coding, reasoning, and controller roles unless policy or runtime fit requires a different admitted lane
- any future HLF-specialized local LoRA or QLoRA candidate remains bridge work under `plan/feature-local-slm-tuning-1.md`; it is not a present-tense runtime dependency for `hlf_mcp`

Current packaged MCP-local priorities:

- local embedding and retrieval lanes should prefer admitted local models such as `nomic-embed-text-v2-moe`, `bge-m3`, `mxbai-embed-large`, `embeddinggemma`, and `qwen3-embedding:4b`
- packaged local reasoning lanes may still use local models such as `qwen3:8b` or `devstral:24b` when they fit the governed workload
- cloud models are not implicit packaged MCP dependencies just because they are recommended for user-agent guidance

Current cloud user-agent guidance roles:

- `planning`: `cogito-2.1:671b-cloud` first for math-heavy decomposition, then `kimi-k2-thinking:cloud`, then `kimi-k2.5:cloud`, then `nemotron-3-super`, then `qwen3.5:cloud`
- `doer`: `minimax-m2.7:cloud` first for full-strength execution, then `devstral-2:123b-cloud`, then `qwen3-coder-next:cloud`, then `glm-5:cloud`, then `nemotron-3-super`, then `qwen3.5:cloud`
- `coding`: `devstral-2:123b-cloud` first for software-engineering-agent work, with `minimax-m2.7:cloud` and `qwen3-coder-next:cloud` directly behind it for stronger end-to-end coding and repair loops
- `reasoning`: `glm-5:cloud` first for complex systems engineering and long-horizon reasoning, then `nemotron-3-super`, then `cogito-2.1:671b-cloud`, then `qwen3.5:cloud`
- `controller / structured fallback`: `qwen3.5:cloud` remains the clean structured-output and universal-fallback lane

Current role notes:

- `cogito-2.1:671b-cloud` is treated as a planning and math-heavy specialist, not a packaged MCP runtime default
- `kimi-k2-thinking:cloud` is treated as the deep thinking planner for long tool chains, while `kimi-k2.5:cloud` is treated as the multimodal planner and vision-grounded agent-swarm model
- `minimax-m2.7:cloud` is treated as the stronger cloud doer for coding-run-fix, multi-file edits, professional productivity, and agentic tool loops
- `devstral-2:123b-cloud` and `qwen3-coder-next:cloud` are the stronger cloud coding specialists; the packaged MCP may still separately admit smaller local coding models when policy and hardware require it
- local MCP admission should stay governed by runtime fit, embedding/privacy requirements, and policy, not by cloud leaderboard enthusiasm

Override rule:

- users may override recommended defaults, but only with deliberate substitutions that meet or exceed the displaced role on context window, tool competence, reasoning or coding strength, multimodal needs, and HLF-specific proficiency
- HLF-specific proficiency includes governed instruction following, symbolic and protocol discipline, long-horizon decomposition, structured output reliability, and operator-safe tool behavior
- if a replacement cannot demonstrably satisfy those floors, it should be treated as an experiment or local exception, not as a new recommended default

When using an HTTP transport, the health endpoint is:

- `http://localhost:$HLF_PORT/health`

Port rule:

- do not rely on an implicit default port for HTTP transports
- set `HLF_PORT` explicitly for every `sse` or `streamable-http` launch
- if you publish a command or script, show the port as a caller choice rather than as a baked-in `8000` assumption

Current caution for bridge work:

- `streamable-http` should still be treated as a repair target for real MCP session initialization, not as a finished self-hosting surface
- rerun the smoke harness after dependency/runtime fixes before promoting HTTP self-build claims into current truth

## Docker

```bash
docker compose up -d
```

The compose stack uses the packaged MCP surface and exposes the same HTTP health endpoint.

## Local Scheduled Evidence Pipeline

For local scheduled collection and weekly evidence snapshots, run:

```bash
python scripts/run_pipeline_scheduled.py
```

This pipeline reuses the packaged pytest runner, captures git and governance state, records packaged server surface counts, optionally runs `_toolkit.py status`, and writes:

- `~/.sovereign/mcp_metrics/weekly_pipeline_latest.json`
- `~/.sovereign/mcp_metrics/weekly_pipeline_history.jsonl`

Local scheduler status can be inspected with:

```bash
python scripts/run_pipeline_scheduled.py --print-status
```

## Weekly GitHub Automation

Current weekly workflow inventory in `.github/workflows/`:

- `weekly-code-quality.yml`
- `weekly-doc-security.yml`
- `weekly-ethics-review.yml`
- `weekly-evolution-planner.yml`
- `weekly-model-drift-detect.yml`
- `weekly-spec-sentinel.yml`
- `weekly-test-health.yml`

These workflows are being normalized to emit a shared weekly artifact schema through `.github/scripts/emit_weekly_artifact.py` so scheduled evidence stays machine-readable and comparable with the local scheduled pipeline.

## Current Build Surface

Main packaged files relevant to build and automation:

- `hlf_mcp/server.py`
- `hlf_mcp/server_core.py`
- `hlf_mcp/server_resources.py`
- `hlf_mcp/test_runner.py`
- `hlf_mcp/weekly_artifacts.py`
- `hlf_mcp/local_scheduler.py`
- `.github/scripts/emit_weekly_artifact.py`
- `.github/scripts/create_github_issue.py`
- `scripts/run_pipeline_scheduled.py`

## Legacy Surface

Legacy compatibility and manual probes still exist, but they are not the default build story:

- `hlf/`
- `scripts/legacy_probes/`

Use them only when you are intentionally validating the older MCP surface or migration behavior.
