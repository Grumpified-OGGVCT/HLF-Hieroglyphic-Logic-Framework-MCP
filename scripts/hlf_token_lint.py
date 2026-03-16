#!/usr/bin/env python3
"""Lint HLF source files for token budget and basic structural invariants."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import tiktoken


DEFAULT_FILE_TOKEN_LIMIT = 1500
DEFAULT_LINE_TOKEN_LIMIT = 30


def discover_hlf_files(paths: Iterable[str]) -> list[Path]:
    if not paths:
        return sorted(Path(".").glob("**/*.hlf"))

    discovered: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            discovered.extend(sorted(path.glob("**/*.hlf")))
        elif path.suffix == ".hlf" and path.exists():
            discovered.append(path)
    return discovered


def lint_text(text: str, encoder: tiktoken.Encoding, *, max_file_tokens: int, max_line_tokens: int) -> list[str]:
    errors: list[str] = []
    total_tokens = len(encoder.encode(text))
    if total_tokens > max_file_tokens:
        errors.append(
            f"File exceeds maximum token budget of {max_file_tokens} (count: {total_tokens})"
        )

    if "[HLF-v2]" not in text and "[HLF-v3]" not in text:
        errors.append("Missing [HLF-v2] or [HLF-v3] header")
    if "Ω" not in text and "Omega" not in text:
        errors.append("Missing Ω terminator")

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        line_tokens = len(encoder.encode(stripped))
        if line_tokens > max_line_tokens:
            errors.append(
                f"Line {line_number} exceeds per-line token budget of {max_line_tokens} (count: {line_tokens})"
            )
    return errors


def lint_file(path: Path, encoder: tiktoken.Encoding, *, max_file_tokens: int, max_line_tokens: int) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Failed to read file: {exc}"]
    return lint_text(
        text,
        encoder,
        max_file_tokens=max_file_tokens,
        max_line_tokens=max_line_tokens,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint HLF files for token and structure budgets")
    parser.add_argument("paths", nargs="*", help="Files or directories to scan; defaults to all .hlf files")
    parser.add_argument("--max-file-tokens", type=int, default=DEFAULT_FILE_TOKEN_LIMIT)
    parser.add_argument("--max-line-tokens", type=int, default=DEFAULT_LINE_TOKEN_LIMIT)
    args = parser.parse_args()

    files = discover_hlf_files(args.paths)
    encoder = tiktoken.get_encoding("cl100k_base")

    has_errors = False
    for path in files:
        errors = lint_file(
            path,
            encoder,
            max_file_tokens=args.max_file_tokens,
            max_line_tokens=args.max_line_tokens,
        )
        if errors:
            has_errors = True
            print(f"FAIL: {path}")
            for error in errors:
                print(f"  - {error}")

    if has_errors:
        return 1

    print(f"Linted {len(files)} file(s) successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())