---
goal: Define the triggered refresh procedure for the internal readiness scorecard and dashboard
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: 'In progress'
tags: [readiness, refresh, workflow, governance, internal]
lane: bridge-true
audience: internal operators and maintainers
---

# HLF Readiness Refresh Procedure

## Purpose

This procedure turns the readiness dashboard into a maintained contract instead of a one-time document set.

It exists because the readiness surfaces are downstream of branch-aware truth files.

If those inputs move without a scorecard refresh, the percentages become stale quickly and start signaling false precision.

## Trigger Inputs

The refresh procedure is triggered whenever any of these files change:

- `SSOT_HLF_MCP.md`
- `docs/HLF_MISSING_PILLARS.md`
- `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md`
- committed weekly artifact JSON under `observability/local_validation/**/weekly-*-artifact.json`
- `.github/scripts/generate_status_overview.py` if the rendering contract changes

## Required Refresh Outputs

When one or more trigger inputs move, refresh these surfaces in the same change:

- `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
- `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
- `docs/HLF_STATUS_OVERVIEW.md`
- `docs/index.html`
- `docs/merge-readiness.html`
- `docs/claims-ledger.html`
- this procedure file if the contract itself changed

## CI Guard

The workflow `.github/workflows/readiness-refresh.yml` is the enforcement surface.

It runs on `push`, `pull_request`, and manual dispatch whenever the trigger inputs or readiness outputs change.

The workflow executes `.github/scripts/readiness_refresh_check.py`, which:

1. reads the changed-file set for the current comparison range
2. detects whether any trigger inputs changed
3. fails the job if no readiness output moved in the same change
4. writes a JSON report artifact for operator inspection

The same workflow also runs `.github/scripts/generate_status_overview.py --check`.

That check enforces that the published markdown overview and the styled Pages front door remain generated from current readiness docs plus committed weekly artifact evidence rather than hand-curated drift.

The same generation contract also covers the styled merge-readiness subpage so the public-safe docs surface stays visually consistent without splitting into manual HTML forks.

The branch-aware claims ledger is covered by that same contract so public review can stay on the generated operator-facing surface instead of drifting back to a hand-maintained raw markdown fork.

## Operator Refresh Order

When the guard triggers, refresh in this order:

1. `SSOT_HLF_MCP.md` if branch-aware current truth changed
2. `docs/HLF_MISSING_PILLARS.md` if implementation classification changed
3. `docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md` if proof coverage changed
4. `docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md`
5. `docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md`
6. `python .github/scripts/generate_status_overview.py`
7. `HLF_ACTIONABLE_PLAN.md` and `HLF_MCP_TODO.md` if the score shift changes bridge priority

## Live Validation Evidence

Current local validation checkpoint:

- `weekly-test-health` local replay produced a Steward-owned governed review with `74.8%` coverage and backlog triage
- `weekly-doc-accuracy` local replay produced a Herald-owned governed review with no measured drift and `ignore` triage

Those outputs are stored under `observability/local_validation/2026-03-20/` and should be treated as bridge-true evidence, not public completion claims.

## Publication Note

GitHub Pages now builds from `/docs` on `main`.

That makes freshness and claim-lane discipline more important, not less.

If these readiness docs are merged to `main`, they become part of the published docs surface and must remain explicitly internal planning artifacts in wording and lane labeling.

The generated `docs/index.html` surface is intentionally compact and public-safe: dark theme, restrained spacing, and source-derived status content rather than decorative marketing language.
