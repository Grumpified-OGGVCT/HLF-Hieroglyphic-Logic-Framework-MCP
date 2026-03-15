"""
codebase_snapshot.py — Generate a structured codebase snapshot for LLM consumption.

Used by the evolution-planner workflow to feed kimi-k2:1t-cloud (256K ctx)
a complete view of the repo without exceeding context limits.

Outputs a single text file containing:
  - File tree
  - All .py source files (with line numbers)
  - governance/ files
  - README.md summary
  - Current test results (if available from test_results.json)

Respects a soft token budget (defaults to 200K tokens @ ~4 chars/token = 800K chars).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

# Paths to always include in full
PRIORITY_PATHS = [
    "hlf_mcp/hlf/compiler.py",
    "hlf_mcp/hlf/bytecode.py",
    "hlf_mcp/hlf/runtime.py",
    "hlf_mcp/hlf/grammar.py",
    "hlf_mcp/server.py",
    "hlf_mcp/rag/memory.py",
    "hlf_mcp/instinct/lifecycle.py",
    "governance/bytecode_spec.yaml",
    "governance/align_rules.json",
    "governance/host_functions.json",
    "docs/QA_FINDINGS_HATS.md",
    "docs/ETHICAL_GOVERNOR_HANDOFF.md",
    "pyproject.toml",
    "README.md",
]

# Paths to include if budget permits
SECONDARY_PATHS_GLOBS = [
    "hlf_mcp/hlf/stdlib/*.py",
    "hlf_mcp/hlf/ethics/*.py",
    "hlf_mcp/hlf/*.py",
    "hlf_mcp/rag/*.py",
    "hlf_mcp/instinct/*.py",
    "tests/*.py",
]

EXCLUDE_PATTERNS = [
    "__pycache__", ".git", ".pytest_cache", "*.pyc", ".venv", "node_modules",
    "*.egg-info", "dist", "build",
]

CHAR_BUDGET = 800_000  # ~200K tokens


def _is_excluded(path: Path) -> bool:
    for pat in EXCLUDE_PATTERNS:
        if pat.startswith("*"):
            if path.name.endswith(pat[1:]):
                return True
        elif pat in str(path):
            return True
    return False


def _file_tree(root: Path, max_depth: int = 4) -> str:
    lines: list[str] = [f"── {root.name}/"]

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            if _is_excluded(entry):
                continue
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(root, "", 1)
    return "\n".join(lines)


def _read_file_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[ERROR reading file: {exc}]"


def build_snapshot(
    output_file: str | None = None,
    char_budget: int = CHAR_BUDGET,
) -> str:
    parts: list[str] = []
    used = 0

    def _add(text: str) -> bool:
        nonlocal used
        if used + len(text) > char_budget:
            return False
        parts.append(text)
        used += len(text)
        return True

    # Header
    _add("=" * 80 + "\n")
    _add("HLF CODEBASE SNAPSHOT — generated for LLM analysis\n")
    _add("=" * 80 + "\n\n")

    # File tree
    tree = _file_tree(ROOT)
    _add(f"## FILE TREE\n\n{tree}\n\n")

    # Priority files
    _add("## PRIORITY SOURCE FILES\n\n")
    for rel in PRIORITY_PATHS:
        path = ROOT / rel
        if not path.exists():
            continue
        content = _read_file_safe(path)
        block = f"### FILE: {rel}\n```\n{content}\n```\n\n"
        if not _add(block):
            _add(f"### FILE: {rel}\n[TRUNCATED — budget exhausted]\n\n")
            break

    # Secondary files (if budget remains)
    if used < char_budget * 0.9:
        _add("## SECONDARY SOURCE FILES\n\n")
        import glob as _glob
        seen = {ROOT / r for r in PRIORITY_PATHS}
        for pattern in SECONDARY_PATHS_GLOBS:
            for match in sorted(_glob.glob(str(ROOT / pattern))):
                p = Path(match)
                if p in seen or _is_excluded(p):
                    continue
                seen.add(p)
                content = _read_file_safe(p)
                rel = p.relative_to(ROOT)
                block = f"### FILE: {rel}\n```\n{content}\n```\n\n"
                if not _add(block):
                    break

    snapshot = "".join(parts)

    if output_file:
        Path(output_file).write_text(snapshot, encoding="utf-8")
        print(f"[codebase_snapshot] Wrote {len(snapshot):,} chars to {output_file}", file=sys.stderr)
    else:
        sys.stdout.write(snapshot)

    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", help="Output file path (default: stdout)")
    parser.add_argument("--budget", type=int, default=CHAR_BUDGET, help="Character budget")
    args = parser.parse_args()
    build_snapshot(output_file=args.output, char_budget=args.budget)


if __name__ == "__main__":
    main()
