#!/usr/bin/env python3
"""Generate packaged Markdown docs from spec files.

Current scope:
  - generate a host-functions reference from governance/host_functions.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOST_FUNCTIONS = REPO_ROOT / "governance" / "host_functions.json"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "HLF_HOST_FUNCTIONS_REFERENCE.md"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def generate_host_functions_reference(path: Path | None = None) -> str:
    """Render a Markdown reference for the packaged host-function registry."""
    source_path = path or DEFAULT_HOST_FUNCTIONS
    data = _load_json(source_path)
    functions = data.get("functions", [])

    lines = [
        "# HLF Host Functions Reference",
        "",
        "Generated from `governance/host_functions.json`.",
        "",
        f"Registry version: `{data.get('version', 'unknown')}`",
        "",
        "| Name | Args | Returns | Tiers | Gas | Backend | Sensitive |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for function in functions:
        args = function.get("args", [])
        arg_text = ", ".join(
            f"`{arg['name']}: {arg['type']}`" for arg in args
        ) or "none"
        tiers = ", ".join(function.get("tier", [])) or "none"
        lines.append(
            "| {name} | {args} | `{returns}` | {tiers} | {gas} | `{backend}` | `{sensitive}` |".format(
                name=function["name"],
                args=arg_text,
                returns=function.get("returns", "unknown"),
                tiers=tiers,
                gas=function.get("gas", "?"),
                backend=function.get("backend", "unknown"),
                sensitive=str(function.get("sensitive", False)).lower(),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This file is generated.",
            "- Update the JSON registry first, then regenerate this page.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_host_functions_reference(
    output_path: Path | None = None,
    source_path: Path | None = None,
) -> Path:
    """Generate and write the packaged host-functions reference file."""
    target = output_path or DEFAULT_OUTPUT
    target.write_text(generate_host_functions_reference(source_path), encoding="utf-8")
    return target


def main() -> None:
    output = write_host_functions_reference()
    print(f"Generated {output}")


if __name__ == "__main__":
    main()
