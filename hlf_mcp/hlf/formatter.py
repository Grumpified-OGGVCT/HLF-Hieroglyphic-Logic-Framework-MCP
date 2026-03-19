"""
HLF Formatter — canonical source formatting.

Rules:
  - Tags are UPPERCASE: [CONSTRAINT], [DELEGATE], etc.
  - Trailing Ω on its own line
  - Sub-statements (under a glyph) are indented with 2 spaces
  - Key=value pairs separated by single space
  - No trailing whitespace
  - Exactly one blank line between top-level statements (optional)
  - Header on first line
"""

from __future__ import annotations

import re
import sys
from difflib import unified_diff

# ── Glyph → canonical sub-indentation logic ──────────────────────────────────
# Sub-statements (Ж, ∇, ⩕) under a primary glyph (Δ, ⌘, ⊎) are indented.
_PRIMARY_GLYPHS = {"Δ", "⌘", "⊎"}
_SUB_GLYPHS = {"Ж", "∇", "⩕", "⨝"}

# Regex patterns for tokenising a single statement line
_HEADER_RE = re.compile(r"^\[HLF-v\d+(?:\.\d+)*\]\s*$")
_OMEGA_RE = re.compile(r"^\s*Ω\s*$")
_GLYPH_RE = re.compile(r"^(\s*)([ΔЖ⨝⌘∇⩕⊎])\s*(.*)")
_KW_RE = re.compile(
    r"^(\s*)(MEMORY|RECALL|SET|IF|ELSE|ENDIF|IMPORT|LOG|RETURN|FUNCTION|CALL"
    r"|SPEC_DEFINE|SPEC_GATE|SPEC_UPDATE|SPEC_SEAL)\b(.*)"
)
_TAG_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")
_COMMENT_RE = re.compile(r"#.*$")


class HLFFormatter:
    """Canonicalize HLF source."""

    def format(self, source: str) -> str:  # noqa: A003
        """Return formatted version of HLF source."""
        lines = source.splitlines()
        out: list[str] = []
        in_block = False  # True if we just saw a primary glyph

        for raw in lines:
            line = raw.strip()
            if not line or _COMMENT_RE.fullmatch(line):
                continue  # drop blank lines and standalone comments

            # Header
            if _HEADER_RE.match(line):
                out.append(line)
                in_block = False
                continue

            # Terminator
            if _OMEGA_RE.match(line):
                out.append("Ω")
                in_block = False
                continue

            # Keyword statement
            kw_m = _KW_RE.match(line)
            if kw_m:
                kw = kw_m.group(2)
                rest = _format_rest(kw_m.group(3).strip())
                formatted = f"{kw}{' ' + rest if rest else ''}"
                out.append(formatted)
                in_block = False
                continue

            # Glyph statement
            g_m = _GLYPH_RE.match(line)
            if g_m:
                glyph = g_m.group(2)
                rest = _format_rest(g_m.group(3).strip())
                formatted = f"{glyph}{' ' + rest if rest else ''}"
                if glyph in _PRIMARY_GLYPHS:
                    out.append(formatted)
                    in_block = True
                elif glyph in _SUB_GLYPHS and in_block:
                    out.append("  " + formatted)
                else:
                    out.append(formatted)
                continue

            # Fallback — preserve with stripped whitespace
            out.append(line)

        return "\n".join(out) + "\n"

    def diff_summary(self, original: str, formatted: str) -> str:
        """Return a human-readable summary of changes made."""
        orig_lines = original.splitlines(keepends=True)
        fmt_lines = formatted.splitlines(keepends=True)
        diff = list(unified_diff(orig_lines, fmt_lines, fromfile="original", tofile="formatted"))
        if not diff:
            return "No changes"
        added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        return f"+{added} -{removed} lines changed"


def _format_rest(rest: str) -> str:
    """Normalise the argument portion of a statement line."""
    if not rest:
        return ""
    # Uppercase all [tags]
    rest = _TAG_RE.sub(lambda m: f"[{m.group(1).upper()}]", rest)
    # Collapse multiple spaces to single space
    rest = re.sub(r"[ \t]+", " ", rest)
    # Strip trailing comment
    rest = _COMMENT_RE.sub("", rest).rstrip()
    return rest


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> None:
    """CLI: hlffmt <file.hlf>"""
    import argparse

    parser = argparse.ArgumentParser(description="Format HLF source")
    parser.add_argument("file", help="HLF source file")
    parser.add_argument("--check", action="store_true", help="Exit 1 if changes needed")
    args = parser.parse_args()

    with open(args.file) as f:
        source = f.read()

    fmt = HLFFormatter()
    formatted = fmt.format(source)

    if args.check:
        if formatted != source:
            print(f"{args.file}: would reformat", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    print(formatted, end="")
