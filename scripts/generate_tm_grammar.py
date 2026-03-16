#!/usr/bin/env python3
"""Generate a TextMate grammar for HLF from the packaged grammar surface."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.grammar import ASCII_ALIASES, GLYPHS, TAGS


def build_textmate_grammar() -> dict[str, Any]:
    glyph_pattern = "|".join(re.escape(glyph) for glyph in GLYPHS)
    tag_pattern = "|".join(sorted(TAGS))
    alias_pattern = "|".join(re.escape(alias) for alias in sorted(ASCII_ALIASES, key=len, reverse=True))

    return {
        "$schema": "https://raw.githubusercontent.com/martinring/tmlanguage/master/tmlanguage.json",
        "name": "HLF",
        "scopeName": "source.hlf",
        "fileTypes": ["hlf"],
        "patterns": [
            {"include": "#version_header"},
            {"include": "#glyph"},
            {"include": "#ascii_alias"},
            {"include": "#canonical_tag"},
            {"include": "#generic_tag"},
            {"include": "#terminator"},
            {"include": "#variable"},
            {"include": "#string"},
            {"include": "#number"},
            {"include": "#keyword"},
            {"include": "#comment"},
        ],
        "repository": {
            "version_header": {
                "match": r"\[HLF-v\d+(?:\.\d+)*\]",
                "name": "keyword.control.hlf",
            },
            "glyph": {
                "match": rf"(?:{glyph_pattern})",
                "name": "keyword.operator.glyph.hlf",
            },
            "ascii_alias": {
                "match": rf"\b(?:{alias_pattern})\b",
                "name": "support.constant.alias.hlf",
            },
            "canonical_tag": {
                "match": rf"\[(?:{tag_pattern})\]",
                "name": "entity.name.tag.hlf",
            },
            "generic_tag": {
                "match": r"\[[A-Z][A-Z0-9_]*\]",
                "name": "entity.name.tag.unregistered.hlf",
            },
            "terminator": {
                "match": r"Ω|\bOmega\b|\bEND\b",
                "name": "keyword.operator.terminator.hlf",
            },
            "variable": {
                "match": r"\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*\}",
                "name": "variable.other.hlf",
            },
            "string": {
                "match": r'"([^"\\]|\\.)*"',
                "name": "string.quoted.double.hlf",
            },
            "number": {
                "match": r"-?\d+(?:\.\d+)?",
                "name": "constant.numeric.hlf",
            },
            "keyword": {
                "match": r"\b(?:true|false|AND|OR|NOT|SET|ASSIGN|IF|ELIF|ELSE|FOR|IN|CALL|TOOL|IMPORT|LOG|RETURN|MEMORY|RECALL|FUNCTION|INTENT|SPEC_DEFINE|SPEC_GATE|SPEC_UPDATE|SPEC_SEAL|PARALLEL|RESULT)\b",
                "name": "keyword.control.flow.hlf",
            },
            "comment": {
                "match": r"#.*$",
                "name": "comment.line.number-sign.hlf",
            },
        },
    }


def write_textmate_grammar(output_path: Path) -> Path:
    grammar = build_textmate_grammar()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(grammar, indent=2) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "syntaxes" / "hlf.tmLanguage.json"
    written = write_textmate_grammar(output_path)
    print(f"Generated {written}")


if __name__ == "__main__":
    main()