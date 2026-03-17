#!/usr/bin/env python3
"""Verify the deterministic trace chain for JSONL observability events."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAST_HASH_FILE = REPO_ROOT / "observability" / "openllmetry" / "last_hash.txt"
ZERO_HASH = "0" * 64


def canonical_payload(entry: dict[str, Any]) -> str:
    """Return the canonical payload string used for trace hashing."""
    return json.dumps(
        {
            "event": entry.get("event", ""),
            "data": entry.get("data", {}),
        },
        sort_keys=True,
    )


def expected_trace_id(prev_hash: str, entry: dict[str, Any]) -> str:
    """Compute the expected trace id for an entry."""
    return hashlib.sha256(f"{prev_hash}{canonical_payload(entry)}".encode()).hexdigest()


def verify_chain(
    entries: list[dict[str, Any]],
    *,
    seed_hash: str = ZERO_HASH,
    expected_last_hash: str | None = None,
) -> tuple[bool, list[str], str]:
    """Verify a chain of JSON log entries.

    Returns `(ok, errors, final_hash)`.
    """
    errors: list[str] = []
    prev_hash = seed_hash

    for index, entry in enumerate(entries):
        expected = expected_trace_id(prev_hash, entry)
        actual = str(entry.get("trace_id", ""))
        if actual != expected:
            errors.append(
                f"Entry {index}: trace_id mismatch. Expected {expected[:16]}..., got {actual[:16]}..."
            )
        prev_hash = actual or expected

    final_hash = prev_hash
    if expected_last_hash and final_hash != expected_last_hash:
        errors.append(
            f"Final hash mismatch. Expected {expected_last_hash[:16]}..., got {final_hash[:16]}..."
        )

    return len(errors) == 0, errors, final_hash


def load_entries(lines: Iterable[str]) -> list[dict[str, Any]]:
    """Load JSONL entries, ignoring blank lines and malformed records."""
    entries: list[dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        with contextlib.suppress(json.JSONDecodeError):
            value = json.loads(text)
            if isinstance(value, dict):
                entries.append(value)
    return entries


def _read_expected_last_hash(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify HLF observability trace chains")
    parser.add_argument("file", nargs="?", help="Optional JSONL file. Defaults to stdin.")
    parser.add_argument(
        "--last-hash-file",
        default=str(DEFAULT_LAST_HASH_FILE),
        help="Optional file containing the expected final hash.",
    )
    parser.add_argument("--quiet", action="store_true", help="Only use exit status.")
    args = parser.parse_args()

    if args.file:
        lines = Path(args.file).read_text(encoding="utf-8").splitlines()
    else:
        lines = sys.stdin.readlines()

    entries = load_entries(lines)
    expected_last_hash = _read_expected_last_hash(Path(args.last_hash_file))
    ok, errors, final_hash = verify_chain(entries, expected_last_hash=expected_last_hash)

    if ok:
        if not args.quiet:
            print(f"Chain verified: {len(entries)} entries OK. Final hash {final_hash[:16]}...")
        sys.exit(0)

    if not args.quiet:
        for error in errors:
            print(f"CHAIN_ERROR: {error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
