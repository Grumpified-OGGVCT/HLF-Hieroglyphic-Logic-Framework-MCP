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

## Running the Packaged MCP Server

Primary server entry points:

```bash
uv run hlf-mcp
python -m hlf_mcp.server
```

Transport selection is controlled with environment variables:

- `HLF_TRANSPORT`: `stdio`, `sse`, or `streamable-http`
- `HLF_HOST`: bind host for HTTP transports, default `0.0.0.0`
- `HLF_PORT`: bind port for HTTP transports, default `8000`
- `HLF_REMOTE_MODEL_ENDPOINTS`: JSON list of explicit `remote-direct` model endpoints for governed routing and catalog sync

Examples:

```bash
# stdio transport
HLF_TRANSPORT=stdio uv run hlf-mcp

# SSE transport
HLF_TRANSPORT=sse HLF_PORT=8000 uv run hlf-mcp

# streamable HTTP transport
HLF_TRANSPORT=streamable-http HLF_PORT=8000 uv run hlf-mcp

# remote-direct operator path
HLF_REMOTE_MODEL_ENDPOINTS='[{"name":"gpt-4.1","endpoint":"https://api.example.test/v1/chat/completions","lanes":["explainer","code-generation"],"capabilities":["reasoning","remote-direct"],"reachable":true}]' uv run hlf-mcp
```

The `HLF_REMOTE_MODEL_ENDPOINTS` contract is consumed by the packaged tools `hlf_sync_model_catalog` and `hlf_route_governed_request`. Use it when you want governed routing to consider explicit remote-direct endpoints in addition to local and cloud-via-ollama candidates. Required-local embedding lanes remain locality constrained unless policy changes upstream.

When using an HTTP transport, the health endpoint is:

- `http://localhost:8000/health`

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
