# Contributing to HLF MCP

Thanks for helping improve the packaged HLF surface.

## First read

Use these files before making changes:

- `README.md` for the public front door
- `SSOT_HLF_MCP.md` for strict current-truth claims
- `BUILD_GUIDE.md` for the canonical setup and test commands
- `docs/HLF_CLAIM_LANES.md` for wording discipline on README/docs changes

## Local setup

Preferred setup:

```bash
uv sync
```

Fallback inside a virtual environment:

```bash
python -m pip install -e '.[dev]'
```

## Validation commands

Use the existing repo commands only. If you are not inside the repo `.venv`, prefer the `uv run ...` forms below so you do not accidentally use the system interpreter.

```bash
uv run pytest tests/ -q --tb=short
uv run ruff check hlf_mcp/
uv run python run_tests.py
uv run python -m hlf_mcp.test_runner
```

If you are touching docs only, keep the scope surgical and still record the current validation state in your PR notes.

## Starter contribution ideas

Low-risk places to help without needing a large architecture change:

1. Tighten README, BUILD_GUIDE, or CLI examples so the first-run path stays accurate.
2. Add or improve fixture-based examples under `fixtures/` and document them in `README.md` or `docs/cli-tools.md`.
3. Improve operator or extension docs under `extensions/hlf-vscode/README.md` without overstating release state.
4. Add focused regression tests when a packaged CLI, resource, or tool contract changes.
5. Improve generated-reference workflows by updating the inputs and rerunning the existing docs generators.

## Practical rules

- Keep claims aligned with `SSOT_HLF_MCP.md`.
- Treat `hlf_mcp/` as the packaged product surface; `hlf/` is compatibility and bridge context unless the task specifically targets it.
- Prefer small, reviewable PRs over large rewrites.
- Do not promote bridge or vision language (the repo's staged-recovery and north-star lanes; see `docs/HLF_CLAIM_LANES.md`) into present-tense README claims without proof.

## Good places to orient quickly

- `docs/cli-tools.md`
- `docs/HLF_HOST_FUNCTIONS_REFERENCE.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `extensions/hlf-vscode/README.md`
- `tests/`
