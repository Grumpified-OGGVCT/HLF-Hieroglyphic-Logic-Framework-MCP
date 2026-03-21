from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path

READINESS_INPUTS = {
    "SSOT_HLF_MCP.md",
    "docs/HLF_MISSING_PILLARS.md",
    "docs/HLF_DOCTRINE_TEST_COVERAGE_MATRIX.md",
    ".github/scripts/generate_status_overview.py",
}

READINESS_INPUT_PATTERNS = {
    "observability/local_validation/**/weekly-*-artifact.json",
}

READINESS_OUTPUTS = {
    "docs/HLF_PILLAR_READINESS_SCORECARD_2026-03-20.md",
    "docs/HLF_INTERNAL_READINESS_DASHBOARD_2026-03-20.md",
    "docs/HLF_READINESS_REFRESH_PROCEDURE.md",
    "docs/HLF_STATUS_OVERVIEW.md",
    "docs/index.html",
    "docs/merge-readiness.html",
    "docs/claims-ledger.html",
}


def _normalize_paths(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        candidate = line.strip().replace("\\", "/")
        if candidate:
            normalized.append(candidate)
    return normalized


def _match_input_patterns(changed: set[str]) -> list[str]:
    matched: list[str] = []
    for path in changed:
        if any(fnmatch.fnmatch(path, pattern) for pattern in READINESS_INPUT_PATTERNS):
            matched.append(path)
    return sorted(matched)


def build_refresh_report(changed_files: list[str]) -> dict[str, object]:
    changed = set(_normalize_paths(changed_files))
    changed_inputs = sorted(changed & READINESS_INPUTS)
    changed_inputs.extend(path for path in _match_input_patterns(changed) if path not in changed_inputs)
    changed_outputs = sorted(changed & READINESS_OUTPUTS)
    refresh_required = bool(changed_inputs)
    satisfied = not refresh_required or bool(changed_outputs)

    return {
        "refresh_required": refresh_required,
        "satisfied": satisfied,
        "changed_inputs": changed_inputs,
        "changed_outputs": changed_outputs,
        "required_outputs": sorted(READINESS_OUTPUTS),
        "missing_outputs": [] if satisfied else sorted(READINESS_OUTPUTS),
        "note": (
            "Status and readiness source surfaces changed; refresh the generated status surfaces and readiness docs in the same change."
            if refresh_required and not satisfied
            else "Readiness refresh contract satisfied."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate readiness refresh coupling.")
    parser.add_argument("--changed-files-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    changed_lines = args.changed_files_file.read_text(encoding="utf-8").splitlines()
    report = build_refresh_report(changed_lines)
    payload = json.dumps(report, indent=2, ensure_ascii=False)

    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")

    print(payload)
    return 0 if report["satisfied"] else 1


if __name__ == "__main__":
    raise SystemExit(main())