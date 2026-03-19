# HLF MCP Build Guide

## Status

This document used to describe the older `hlf/` MCP implementation as the primary build surface.

That is no longer the current product truth.

Current authority:

- `hlf_mcp/` is the packaged product surface.
- `hlf/` is a compatibility and support layer.
- `scripts/legacy_probes/` contains manual probes for the legacy MCP path and is not part of the default automated suite.

If you need the active build and automation guide, start with the repo-root guide:

- [BUILD_GUIDE.md](../BUILD_GUIDE.md)

## Current Build Truth

### Canonical test entry points

Use one of these:

```bash
python run_tests.py
python -m hlf_mcp.test_runner
hlf-test-runner
uv run pytest tests/ -q --tb=short
```

These run the packaged default suite under `tests/`.

The packaged runner persists metrics to:

- `~/.sovereign/mcp_metrics/tests.jsonl`
- `~/.sovereign/mcp_metrics/pytest_last_run.json`
- `~/.sovereign/mcp_metrics/pytest_history.jsonl`

### Packaged MCP server entry points

Use the packaged server, not the legacy `hlf.mcp_server_complete` path, for current work:

```bash
uv run hlf-mcp
python -m hlf_mcp.server
```

Transport selection is controlled by:

- `HLF_TRANSPORT`
- `HLF_HOST`
- `HLF_PORT`

Supported transports:

- `stdio`
- `sse`
- `streamable-http`

### Current recursive-build stance

For the current packaged repo, the first credible self-build workflow is local and bounded:

- prefer `stdio` for agent-facing build assistance
- use `hlf_do`, `hlf_test_suite_summary`, and `_toolkit.py status` as the first build-assist loop
- treat HTTP health checks as transport bring-up, not as proof of full remote MCP readiness

Do not center the build story on `streamable-http` self-hosting until full MCP initialization succeeds through the smoke harness.

### Local scheduled evidence pipeline

```bash
python scripts/run_pipeline_scheduled.py
```

This writes:

- `~/.sovereign/mcp_metrics/weekly_pipeline_latest.json`
- `~/.sovereign/mcp_metrics/weekly_pipeline_history.jsonl`

The local scheduled pipeline reuses the packaged pytest runner, records git and governance state, records packaged server surface counts, and can include `_toolkit.py status` output.

### Weekly GitHub automation

Current weekly workflows under `.github/workflows/`:

- `weekly-code-quality.yml`
- `weekly-doc-security.yml`
- `weekly-ethics-review.yml`
- `weekly-evolution-planner.yml`
- `weekly-model-drift-detect.yml`
- `weekly-spec-sentinel.yml`
- `weekly-test-health.yml`

These workflows are being normalized to emit the shared weekly artifact schema via `.github/scripts/emit_weekly_artifact.py`.

## Current Build Surface Files

Primary packaged files:

- `hlf_mcp/server.py`
- `hlf_mcp/server_core.py`
- `hlf_mcp/server_resources.py`
- `hlf_mcp/server_translation.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_profiles.py`
- `hlf_mcp/server_instinct.py`
- `hlf_mcp/server_capsule.py`
- `hlf_mcp/test_runner.py`
- `hlf_mcp/weekly_artifacts.py`
- `hlf_mcp/local_scheduler.py`
- `scripts/run_pipeline_scheduled.py`
- `.github/scripts/emit_weekly_artifact.py`
- `.github/scripts/create_github_issue.py`

## Legacy Boundary

The following remain useful, but they are not the default product-facing build path:

- `hlf/mcp_server_complete.py`
- `hlf/mcp_resources.py`
- `hlf/mcp_tools.py`
- `hlf/mcp_prompts.py`
- `hlf/mcp_client.py`
- `scripts/legacy_probes/`

Treat those as compatibility, migration, or manual validation surfaces.

## Why This Doc Changed

The older version of this file described:

- `hlf/mcp_server_complete.py` as the server entry point
- `hlf/mcp_resources.py`, `hlf/mcp_tools.py`, and `hlf/mcp_prompts.py` as the main MCP implementation
- generated `mcp_resources/` artifacts as the primary build output

Those descriptions were historically useful, but they are no longer the present-tense packaged build truth for this repository.
