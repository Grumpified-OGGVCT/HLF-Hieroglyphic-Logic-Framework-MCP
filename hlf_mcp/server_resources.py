from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.bytecode import OPCODES


_PACKAGE_DIR = Path(__file__).resolve().parent
_GOVERNANCE_DIR = _PACKAGE_DIR.parent / "governance"


def _read_governance_file(filename: str) -> str:
    path = _GOVERNANCE_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "governance_file_not_found",
            "file": filename,
            "hint": (
                "The governance/ directory is not bundled in wheel installs. "
                "Install from source (`pip install -e .`) or mount the directory "
                "to the container's working directory."
            ),
        },
        indent=2,
    )


def _read_fixture_file(name: str) -> str:
    available = (
        "hello_world, security_audit, delegation, routing, "
        "db_migration, log_analysis, stack_deployment"
    )
    candidates = [
        _PACKAGE_DIR.parent / "fixtures" / f"{name}.hlf",
        _PACKAGE_DIR / "fixtures" / f"{name}.hlf",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "example_not_found",
            "requested": name,
            "available": available,
            "hint": (
                "The fixtures/ directory is not bundled in wheel installs. "
                "Install from source or copy fixtures/ into the package tree."
            ),
        }
    )


def register_resources(mcp: FastMCP) -> None:
    @mcp.resource("hlf://grammar")
    def get_grammar() -> str:
        """HLF grammar specification (LALR(1) Lark format)."""
        from hlf_mcp.hlf.grammar import HLF_GRAMMAR

        return HLF_GRAMMAR

    @mcp.resource("hlf://opcodes")
    def get_opcodes() -> str:
        """HLF bytecode opcode table (37 opcodes)."""
        return json.dumps(OPCODES, indent=2)

    @mcp.resource("hlf://host_functions")
    def get_host_functions() -> str:
        """Available HLF host function registry (28 functions)."""
        from hlf_mcp.hlf.runtime import HOST_FUNCTIONS

        return json.dumps(HOST_FUNCTIONS, indent=2)

    @mcp.resource("hlf://examples/{name}")
    def get_example(name: str) -> str:
        """Return a named example HLF program."""
        return _read_fixture_file(name)

    @mcp.resource("hlf://governance/host_functions")
    def get_governance_host_functions() -> str:
        """Governance host_functions.json — full host function definitions."""
        return _read_governance_file("host_functions.json")

    @mcp.resource("hlf://governance/bytecode_spec")
    def get_governance_bytecode_spec() -> str:
        """Governance bytecode_spec.yaml — bytecode encoding specification."""
        return _read_governance_file("bytecode_spec.yaml")

    @mcp.resource("hlf://governance/align_rules")
    def get_governance_align_rules() -> str:
        """Governance align_rules.json — alignment and safety rules."""
        return _read_governance_file("align_rules.json")

    @mcp.resource("hlf://governance/tag_i18n")
    def get_governance_tag_i18n() -> str:
        """Multilingual HLF tag registry — 14 canonical tags × 8 languages + ASCII glyph aliases."""
        return _read_governance_file("tag_i18n.yaml")

    @mcp.resource("hlf://stdlib")
    def get_stdlib() -> str:
        """List all available HLF stdlib modules."""
        stdlib_dir = _PACKAGE_DIR / "hlf" / "stdlib"
        if not os.path.isdir(stdlib_dir):
            return json.dumps({"modules": []})
        modules = sorted(
            name[:-3]
            for name in os.listdir(stdlib_dir)
            if name.endswith(".py") and not name.startswith("_")
        )
        return json.dumps({"modules": modules}, indent=2)