#!/usr/bin/env python3
"""Generate a TextMate grammar for HLF from packaged metadata surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.grammar import ASCII_ALIASES, STATEMENT_GLYPHS, TAGS


def _regex_union(values: set[str] | list[str]) -> str:
    return "|".join(re.escape(value) for value in sorted(values, key=lambda item: (-len(item), item)))


def _load_tag_i18n(repo_root: Path) -> tuple[set[str], set[str], set[str], set[str]]:
    """Load simple tag/alias surfaces without adding a YAML runtime dependency."""

    path = repo_root / "governance" / "tag_i18n.yaml"
    if not path.exists():
        return set(TAGS), set(), set(), set()

    canonical_and_ascii: set[str] = set(TAGS)
    latin: set[str] = set()
    cjk: set[str] = set()
    arabic: set[str] = set()
    in_tags = False
    current_tag: str | None = None
    tag_header = re.compile(r"^  ([A-Z][A-Z0-9_]*):\s*$")
    alias_list = re.compile(r"^\s{4}[a-z]{2}:\s*\[(.*)\]\s*$")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if line == "tags:":
            in_tags = True
            continue
        if not in_tags:
            continue
        header = tag_header.match(line)
        if header:
            current_tag = header.group(1)
            canonical_and_ascii.add(current_tag)
            continue
        aliases = alias_list.match(line)
        if not aliases or current_tag is None:
            continue
        for value in (item.strip() for item in aliases.group(1).split(",")):
            if not value:
                continue
            if re.fullmatch(r"[A-Z0-9_]+", value):
                canonical_and_ascii.add(value)
            elif re.search(r"[\u0600-\u06ff]", value):
                arabic.add(value)
            elif re.search(r"[\u3040-\u30ff\u3400-\u9fff]", value):
                cjk.add(value)
            elif re.fullmatch(r"[A-Za-z0-9_]+", value):
                latin.add(value)

    return canonical_and_ascii, latin, cjk, arabic


def build_textmate_grammar(repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path(__file__).resolve().parent.parent
    statement_glyph_pattern = _regex_union(set(STATEMENT_GLYPHS))
    tag_pattern, latin_i18n, cjk_i18n, arabic_i18n = _load_tag_i18n(repo_root)
    alias_pattern = _regex_union(set(ASCII_ALIASES))

    patterns: list[dict[str, str]] = [
        {"include": "#comment"},
        {"include": "#version_header"},
        {"include": "#block"},
        {"include": "#terminator"},
        {"include": "#line_glyph"},
        {"include": "#glyph"},
        {"include": "#ascii_alias"},
        {"include": "#canonical_tag"},
    ]
    if latin_i18n:
        patterns.append({"include": "#i18n_latin_tag"})
    if cjk_i18n:
        patterns.append({"include": "#i18n_cjk_tag"})
    if arabic_i18n:
        patterns.append({"include": "#i18n_arabic_tag"})
    patterns.extend(
        [
            {"include": "#generic_tag"},
            {"include": "#string"},
            {"include": "#variable"},
            {"include": "#control_keyword"},
            {"include": "#definition_keyword"},
            {"include": "#declaration_keyword"},
            {"include": "#spec_keyword"},
            {"include": "#builtin_keyword"},
            {"include": "#logical_keyword"},
            {"include": "#boolean"},
            {"include": "#typed_param"},
            {"include": "#property_key"},
            {"include": "#path"},
            {"include": "#number"},
            {"include": "#comparison_operator"},
            {"include": "#arithmetic_operator"},
            {"include": "#assignment_operator"},
            {"include": "#punctuation"},
            {"include": "#identifier"},
        ]
    )

    repository: dict[str, Any] = {
        "comment": {"match": "#.*$", "name": "comment.line.number-sign.hlf"},
        "version_header": {
            "match": r"\[HLF-v\d+(?:\.\d+)*\]",
            "name": "keyword.control.version.hlf",
        },
        "block": {
            "begin": r"\{",
            "beginCaptures": {"0": {"name": "punctuation.definition.block.begin.hlf"}},
            "end": r"\}",
            "endCaptures": {"0": {"name": "punctuation.definition.block.end.hlf"}},
            "name": "meta.block.hlf",
            "patterns": [{"include": "$self"}],
        },
        "terminator": {
            "match": r"Ω|\b(?:Omega|OMEGA|END)\b",
            "name": "keyword.operator.terminator.hlf",
        },
        "line_glyph": {
            "match": rf"^\s*(?:{statement_glyph_pattern})",
            "name": "keyword.control.command.hlf",
        },
        "glyph": {
            "match": rf"(?:{statement_glyph_pattern})",
            "name": "keyword.operator.glyph.hlf",
        },
        "ascii_alias": {
            "match": rf"\b(?:{alias_pattern})\b",
            "name": "support.constant.alias.hlf",
        },
        "canonical_tag": {
            "match": rf"\[(?:{_regex_union(tag_pattern)})\]",
            "name": "entity.name.tag.hlf",
        },
        "generic_tag": {
            "match": r"\[[A-Z][A-Z0-9_]*\]",
            "name": "entity.name.tag.unregistered.hlf",
        },
        "string": {
            "begin": '"',
            "beginCaptures": {"0": {"name": "punctuation.definition.string.begin.hlf"}},
            "end": '"',
            "endCaptures": {"0": {"name": "punctuation.definition.string.end.hlf"}},
            "name": "string.quoted.double.hlf",
            "patterns": [{"include": "#escape"}, {"include": "#string_variable"}],
        },
        "escape": {"match": r"\\.", "name": "constant.character.escape.hlf"},
        "string_variable": {
            "match": r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\}",
            "name": "variable.other.interpolated.hlf",
        },
        "variable": {
            "match": r"\$[A-Za-z_][A-Za-z0-9_]*|\$\{[A-Za-z_][A-Za-z0-9_]*\}",
            "name": "variable.other.hlf",
        },
        "control_keyword": {
            "match": r"\b(?:IF|ELIF|ELSE|ENDIF|FOR|IN|PARALLEL)\b",
            "name": "keyword.control.flow.hlf",
        },
        "definition_keyword": {
            "match": r"\b(?:FUNCTION|INTENT)\b",
            "name": "keyword.control.definition.hlf",
        },
        "declaration_keyword": {"match": r"\b(?:SET|ASSIGN)\b", "name": "storage.type.hlf"},
        "spec_keyword": {
            "match": r"\b(?:SPEC_DEFINE|SPEC_GATE|SPEC_UPDATE|SPEC_SEAL)\b",
            "name": "keyword.other.spec.hlf",
        },
        "builtin_keyword": {
            "match": r"\b(?:CALL|TOOL|IMPORT|LOG|RETURN|MEMORY|RECALL|RESULT|ROUTE|DELEGATE)\b",
            "name": "support.function.hlf",
        },
        "logical_keyword": {"match": r"\b(?:AND|OR|NOT)\b", "name": "keyword.operator.logical.hlf"},
        "boolean": {"match": r"\b(?:true|false)\b", "name": "constant.language.boolean.hlf"},
        "typed_param": {
            "match": r"\b([a-zA-Z_][a-zA-Z0-9_]*)(:)([a-zA-Z_][a-zA-Z0-9_]*)\b",
            "captures": {
                "1": {"name": "variable.parameter.hlf"},
                "2": {"name": "punctuation.separator.type.hlf"},
                "3": {"name": "support.type.hlf"},
            },
        },
        "property_key": {
            "match": r"\b[a-z_][a-zA-Z0-9_]*(?=\s*=)",
            "name": "variable.parameter.key.hlf",
        },
        "path": {
            "match": r"(?:(?<=\s)|^)/(?:[^\s\[\]""#{}()]|\\ )+",
            "name": "string.unquoted.path.hlf",
        },
        "number": {"match": r"\b\d+(?:\.\d+)?\b", "name": "constant.numeric.hlf"},
        "comparison_operator": {"match": r"==|!=|<=|>=|<|>", "name": "keyword.operator.comparison.hlf"},
        "arithmetic_operator": {"match": r"[-+*/%]", "name": "keyword.operator.arithmetic.hlf"},
        "assignment_operator": {"match": "=", "name": "keyword.operator.assignment.hlf"},
        "punctuation": {
            "patterns": [
                {"match": r"\(", "name": "punctuation.section.parens.begin.hlf"},
                {"match": r"\)", "name": "punctuation.section.parens.end.hlf"},
            ]
        },
        "identifier": {"match": r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", "name": "variable.other.readwrite.hlf"},
    }
    if latin_i18n:
        repository["i18n_latin_tag"] = {
            "match": rf"\[(?:{_regex_union(latin_i18n)})\]",
            "name": "entity.name.tag.i18n.hlf",
        }
    if cjk_i18n:
        repository["i18n_cjk_tag"] = {
            "match": rf"\[(?:{_regex_union(cjk_i18n)})\]",
            "name": "entity.name.tag.i18n.hlf",
        }
    if arabic_i18n:
        repository["i18n_arabic_tag"] = {
            "match": rf"\[(?:{_regex_union(arabic_i18n)})\]",
            "name": "entity.name.tag.i18n.hlf",
        }

    return {
        "name": "HLF",
        "scopeName": "source.hlf",
        "fileTypes": ["hlf"],
        "patterns": patterns,
        "repository": repository,
    }


def write_textmate_grammar(output_path: Path) -> Path:
    grammar = build_textmate_grammar(output_path.resolve().parents[1] if output_path.parent.name == "syntaxes" else None)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(grammar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    output_path = repo_root / "syntaxes" / "hlf.tmLanguage.json"
    written = write_textmate_grammar(output_path)
    print(f"Generated {written}")


if __name__ == "__main__":
    main()
