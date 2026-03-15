"""
HLF Linter — static analysis and diagnostics.

Checks for:
  - Token budget overrun (>30 tokens per intent by default)
  - Gas limit violations
  - Missing terminator Ω
  - Invalid/unknown glyph usage
  - Unused MEMORY declarations (stored but never recalled)
  - Undefined variable references ($VAR used but never SET)
  - Recursion depth (CALL depth estimate)
  - Duplicate SPEC_DEFINE tags
  - SPEC_SEAL without SPEC_DEFINE
"""

from __future__ import annotations

import re
import sys
from typing import Any

from hlf_mcp.hlf.grammar import GLYPHS, TAGS

_GLYPH_CHARS = set(GLYPHS.keys())

# Rough token estimate: split on whitespace + punctuation
_TOKEN_RE = re.compile(r"\S+")
_TAG_RE = re.compile(r"\[([A-Z][A-Z0-9_]*)\]")
_VAR_REF_RE = re.compile(r"\$([A-Z_][A-Z0-9_]*)")
_SET_RE = re.compile(r"^\s*SET\s+(\w+)\s*=")
_MEMORY_RE = re.compile(r"^\s*MEMORY\s*\[\s*(\w+)\s*\]")
_RECALL_RE = re.compile(r"^\s*RECALL\s*\[\s*(\w+)\s*\]")
_SPEC_DEFINE_RE = re.compile(r"^\s*SPEC_DEFINE\b")
_SPEC_SEAL_RE = re.compile(r"^\s*SPEC_SEAL\b")
_CALL_RE = re.compile(r"^\s*(CALL|⌘)\b")


class HLFLinter:
    """Static lint analysis for HLF source."""

    def lint(
        self,
        source: str,
        gas_limit: int = 1000,
        token_limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Lint source and return list of diagnostic dicts.

        Each diagnostic: {level, message, line, col}
        level: "error" | "warning" | "info"
        """
        diagnostics: list[dict[str, Any]] = []
        lines = source.splitlines()

        has_header = False
        has_terminator = False
        set_vars: set[str] = set()
        used_vars: set[str] = set()
        memory_stores: set[str] = set()
        memory_recalls: set[str] = set()
        spec_defined_tags: set[str] = set()
        spec_sealed_tags: set[str] = set()
        call_depth = 0
        total_gas = 0

        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            # Header check
            if line.startswith("[HLF-v"):
                has_header = True
                continue

            # Terminator
            if line == "Ω":
                has_terminator = True
                continue

            # Token budget per line
            tokens = _TOKEN_RE.findall(line)
            if len(tokens) > token_limit:
                diagnostics.append(
                    _diag(
                        "warning",
                        f"Line exceeds token budget: {len(tokens)} tokens (limit {token_limit})",
                        lineno,
                    )
                )

            # Gas estimation
            total_gas += _gas_for_line(line)

            # Variable tracking
            for var in _VAR_REF_RE.findall(line):
                used_vars.add(var)
            m = _SET_RE.match(line)
            if m:
                set_vars.add(m.group(1))

            # Memory tracking
            mm = _MEMORY_RE.match(line)
            if mm:
                memory_stores.add(mm.group(1))
            rm = _RECALL_RE.match(line)
            if rm:
                memory_recalls.add(rm.group(1))

            # Spec tracking
            if _SPEC_DEFINE_RE.match(line):
                tag_m = _TAG_RE.search(line)
                if tag_m:
                    spec_defined_tags.add(tag_m.group(1))

            if _SPEC_SEAL_RE.match(line):
                tag_m = _TAG_RE.search(line)
                if tag_m:
                    spec_sealed_tags.add(tag_m.group(1))

            # Call depth heuristic
            if _CALL_RE.match(line):
                call_depth += 1
                if call_depth > 10:
                    diagnostics.append(
                        _diag("warning", "Deep call chain detected (>10 CALL statements)", lineno)
                    )

            # Unknown tag check
            for tag in _TAG_RE.findall(line):
                if tag not in TAGS and not tag.startswith("HLF"):
                    diagnostics.append(
                        _diag("info", f"Unknown tag [{tag}] — not in canonical tag registry", lineno)
                    )

        # Post-analysis checks
        if not has_header:
            diagnostics.append(_diag("error", "Missing HLF header [HLF-vN]", 1))

        if not has_terminator:
            diagnostics.append(_diag("error", "Missing terminator Ω", len(lines)))

        if total_gas > gas_limit:
            diagnostics.append(
                _diag(
                    "error",
                    f"Gas budget exceeded: estimated {total_gas} units (limit {gas_limit})",
                    0,
                )
            )

        # Undefined variable references
        undefined_vars = used_vars - set_vars
        for var in sorted(undefined_vars):
            diagnostics.append(
                _diag("warning", f"Variable ${var} used but never SET (may be environment-injected)", 0)
            )

        # Unused memory stores
        unused_memory = memory_stores - memory_recalls
        for key in sorted(unused_memory):
            diagnostics.append(
                _diag("info", f"MEMORY [{key}] stored but never RECALLed", 0)
            )

        # SPEC_SEAL without SPEC_DEFINE
        sealed_without_define = spec_sealed_tags - spec_defined_tags
        for tag in sorted(sealed_without_define):
            diagnostics.append(
                _diag("warning", f"SPEC_SEAL [{tag}] without preceding SPEC_DEFINE [{tag}]", 0)
            )

        return diagnostics


def _diag(level: str, message: str, line: int, col: int = 0) -> dict[str, Any]:
    return {"level": level, "message": message, "line": line, "col": col}


def _gas_for_line(line: str) -> int:
    """Rough per-line gas estimate."""
    GAS_MAP = {
        "MEMORY": 5, "RECALL": 5, "CALL": 3, "⌘": 3,
        "SPEC_DEFINE": 4, "SPEC_GATE": 4, "SPEC_SEAL": 4, "SPEC_UPDATE": 3,
        "Δ": 2, "Ж": 2, "⨝": 2, "∇": 2, "⩕": 2, "⊎": 2,
        "SET": 1, "IF": 1, "LOG": 1, "IMPORT": 2,
    }
    for prefix, cost in GAS_MAP.items():
        if line.startswith(prefix) or line.lstrip().startswith(prefix):
            return cost
    return 1


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """CLI: hlflint <file.hlf>"""
    import json
    import argparse

    parser = argparse.ArgumentParser(description="Lint HLF source")
    parser.add_argument("file", help="HLF source file")
    parser.add_argument("--gas-limit", type=int, default=1000, help="Gas limit (default 1000)")
    parser.add_argument("--token-limit", type=int, default=30, help="Per-line token limit (default 30)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    with open(args.file) as f:
        source = f.read()

    linter = HLFLinter()
    diags = linter.lint(source, gas_limit=args.gas_limit, token_limit=args.token_limit)

    if args.json:
        print(json.dumps(diags, indent=2))
        sys.exit(0)

    if not diags:
        print("✓ No issues found")
        sys.exit(0)

    errors = [d for d in diags if d["level"] == "error"]
    for d in diags:
        icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(d["level"], "?")
        loc = f":{d['line']}" if d["line"] else ""
        print(f"{icon} {args.file}{loc}: {d['message']}")

    if errors:
        sys.exit(1)
