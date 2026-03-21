#!/usr/bin/env python3
"""Generate the governance manifest used by startup drift checks."""

from __future__ import annotations

import hashlib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
MANIFEST_PATH = GOVERNANCE_DIR / "MANIFEST.sha256"
TRACKED_FILES = (
    "align_rules.json",
    "bytecode_spec.yaml",
    "host_functions.json",
    "tag_i18n.yaml",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_manifest() -> str:
    lines = [
        "# HLF governance file manifest — SHA-256 hashes",
        "# Generated at commit time; server checks this at startup (warns on drift).",
        "# Regenerate: uv run python scripts/gen_manifest.py",
        "# Format: <sha256hex>  <filename>  (two spaces, GNU coreutils sha256sum style)",
        "",
    ]
    for filename in TRACKED_FILES:
        path = GOVERNANCE_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Tracked governance file missing: {path}")
        lines.append(f"{_sha256(path)}  {filename}")
    return "\n".join(lines) + "\n"


def main() -> None:
    MANIFEST_PATH.write_text(render_manifest(), encoding="utf-8")
    print(f"Generated {MANIFEST_PATH}")


if __name__ == "__main__":
    main()