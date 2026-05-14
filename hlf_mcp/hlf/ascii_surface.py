"""
HLF ASCII Surface — bidirectional projection between ASCII keyword syntax
and canonical glyph Unicode syntax.

ASCII keywords round-trip through the existing glyph grammar so that
ASCII-syntax HLF produces the same AST as glyph-syntax HLF.

Surface projection (not a separate grammar):
  ASCII source → ASCIIToHLF → glyph source → existing compiler → AST
  AST → existing compiler output → HLFToASCII → ASCII display

Classes:
  ASCIIToHLF  — ASCII keyword syntax → canonical glyph HLF
  HLFToASCII  — canonical glyph HLF → ASCII keyword syntax
  ascii_roundtrip() — validate ASCII → Glyph → ASCII preservation
  is_ascii_hlf()    — detect ASCII-style vs glyph-style source
"""

from __future__ import annotations

import re
from typing import Any

from hlf_mcp.hlf.grammar import ASCII_ALIASES, GLYPHS, STATEMENT_GLYPHS, TAGS

# ── Glyph → ASCII keyword mapping (canonical reverse of ASCII_ALIASES) ────────

_GLYPH_TO_ASCII_KEYWORD: dict[str, str] = {
    "Δ": "ANALYZE",
    "Ж": "ENFORCE",
    "⨝": "CONSTRAINT",
    "⌘": "EXECUTE",
    "∇": "ASSERT",
    "⩕": "SET",
    "⊎": "IF",
    "⌂": "DEFINE",
    "Σ": "SUMMARY",
    "Ω": "END",
}

# Tag-sensitive overrides: when a glyph has a specific tag, use a different ASCII keyword.
_TAG_KEYWORD_OVERRIDE: dict[str, dict[str, str]] = {
    "Ж": {
        "RETURN": "RETURN",
        "LOG": "LOG",
        "ENFORCE": "ENFORCE",
        "CONSTRAINT": "ENFORCE",
        "ASSERT": "ENFORCE",
        "EXPECT": "ENFORCE",
    },
    "∇": {
        "PARALLEL": "PARALLEL",
        "ASSERT": "ASSERT",
        "SOURCE": "SOURCE",
        "FOR": "FOR",
    },
    "⩕": {
        "SET": "SET",
        "PRIORITY": "PRIORITY",
    },
    "⊎": {
        "IF": "IF",
        "BRANCH": "IF",
    },
    "⌂": {
        "FUNC": "DEFINE",
        "FUNCTION": "DEFINE",
        "MEMORY": "MEMORY",
    },
    "⌘": {
        "EXEC": "EXECUTE",
        "DELEGATE": "EXECUTE",
        "COMMAND": "EXECUTE",
    },
    "Δ": {
        "INTENT": "ANALYZE",
    },
    "⨝": {
        "CONSTRAINT": "CONSTRAINT",
        "VOTE": "VOTE",
    },
    "Σ": {
        "RESULT": "SUMMARY",
    },
}

# ASCII keyword → (glyph, default_tag) mapping for statements that use tag+args form.
_ASCII_TO_GLYPH_TAG: dict[str, tuple[str, str]] = {
    "ANALYZE": ("Δ", "INTENT"),
    "EXECUTE": ("⌘", "EXEC"),
    "SET": ("⩕", "SET"),
    "LET": ("⩕", "SET"),
    "DEFINE": ("⌂", "FUNC"),
    "RETURN": ("Ж", "RETURN"),
    "LOG": ("Ж", "LOG"),
    "ENFORCE": ("Ж", "ENFORCE"),
    "CONSTRAINT": ("⨝", "CONSTRAINT"),
    "ASSERT": ("∇", "ASSERT"),
    "PARALLEL": ("∇", "PARALLEL"),
    "SOURCE": ("∇", "SOURCE"),
    "PRIORITY": ("⩕", "PRIORITY"),
    "SUMMARY": ("Σ", "RESULT"),
    "VOTE": ("⨝", "VOTE"),
    "MEMORY": ("⌂", "MEMORY"),
    "FOR": ("∇", "FOR"),
}

# ── Regex patterns for ASCII keyword lines ─────────────────────────────────────

# Header line: [HLF-v3] etc.
_HEADER_RE = re.compile(r"^\[HLF-v\d+(?:\.\d+)*\]\s*$")

# Terminator: END (ASCII) or Ω (glyph, preserved as-is)
_END_RE = re.compile(r"^\s*END\s*$")
_OMEGA_RE = re.compile(r"^\s*Ω\s*$")

# ANALYZE <goal>
_ANALYZE_RE = re.compile(r"^ANALYZE\s+(.+)$")

# EXECUTE <goal>
_EXECUTE_RE = re.compile(r"^EXECUTE\s+(.+)$")

# IF <condition> THEN <tag>
_IF_THEN_RE = re.compile(r"^IF\s+(.+?)\s+THEN\s+\[([A-Z][A-Z0-9_]*)\]\s*$")

# ELSE (standalone)
_ELSE_RE = re.compile(r"^ELSE\s*$")

# ELIF <condition>
_ELIF_RE = re.compile(r"^ELIF\s+(.+)$")

# ENDIF (standalone)
_ENDIF_RE = re.compile(r"^ENDIF\s*$")

# SET / LET <name> = <value>
_SET_RE = re.compile(r"^(?:SET|LET)\s+(\S+)\s*=\s*(.+)$")

# DEFINE <name>(<params>): <body>   OR   DEFINE <name>(<params>)
_DEFINE_RE = re.compile(r"^DEFINE\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*:?\s*(.*)$")

# RETURN <value>
_RETURN_RE = re.compile(r"^RETURN\s+(.+)$")

# LOG <value>
_LOG_RE = re.compile(r"^LOG\s+(.+)$")

# PARALLEL: (block header, indented tasks follow)
_PARALLEL_RE = re.compile(r"^PARALLEL\s*:\s*$")

# CONSTRAINT <name> <min>..<max>
_CONSTRAINT_RE = re.compile(
    r"^CONSTRAINT\s+(\S+)\s+(-?\d+(?:\.\d+)?)\s*\.\.\s*(-?\d+(?:\.\d+)?)\s*$"
)

# SPEC_GATE <name>
_SPEC_GATE_RE = re.compile(r"^SPEC_GATE\s+(.+)$")

# SPEC_DEFINE <name>
_SPEC_DEFINE_RE = re.compile(r"^SPEC_DEFINE\s+(.+)$")

# FOR EACH <item> IN <collection>:
_FOR_EACH_RE = re.compile(
    r"^FOR\s+EACH\s+([a-zA-Z_]\w*)\s+IN\s+(.+?)\s*:\s*$"
)

# ASSERT <condition>
_ASSERT_RE = re.compile(r"^ASSERT\s+(.+)$")

# Generic keyword catch: KEYWORD arg1 arg2 ...
_KEYWORD_LINE_RE = re.compile(
    r"^(ANALYZE|ANALYSE|ANALYSER|ANALIZAR|EXECUTE|ENFORCE|CONSTRAIN|"
    r"JOIN|CONSENSUS|VOTE|CMD|COMMAND|SOURCE|PRIORITY|BRANCH|UNION|"
    r"MEMORY_ANCHOR|SUMMARY|SUMMARIZE|AGGREGATE|SET|LET|IF|ELSE|ELIF|"
    r"ENDIF|DEFINE|RETURN|LOG|PARALLEL|CONSTRAINT|SPEC_GATE|SPEC_DEFINE|"
    r"FOR|ASSERT|MEMORY|RECALL|IMPORT|CALL|TOOL|MODULE|FUNCTION|INTENT|"
    r"RESULT|SPEC_UPDATE|SPEC_SEAL)\b"
)

# ── Glyph line patterns (for HLFToASCII) ───────────────────────────────────────

_GLYPH_LINE_RE = re.compile(r"^(\s*)([ΔЖ⨝⌘∇⩕⊎⌂Σ])\s*(.*)$")

# Tag pattern: [TAG_NAME]
_TAG_RE = re.compile(r"\[([A-Za-z][A-Za-z0-9_]*)\]")

# Key-value argument: key="value" or key=value
_KV_ARG_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_KV_ARG_BARE_RE = re.compile(r"(\w+)\s*=\s*(\S+)")

# Inline condition + arrow: <condition> ⇒ [TAG]
_COND_ARROW_TAG_RE = re.compile(r"^(.+?)\s*⇒\s*\[([A-Z][A-Z0-9_]*)\]\s*$")

# ── Indentation helpers ────────────────────────────────────────────────────────

_BLOCK_KEYWORDS = {"PARALLEL", "FOR", "DEFINE"}
_INDENT_RE = re.compile(r"^(\s*)")


def _get_indent(line: str) -> int:
    """Return indentation level (number of leading spaces)."""
    m = _INDENT_RE.match(line)
    return len(m.group(1)) if m else 0


def _is_block_header(line: str) -> bool:
    """Check if a line is a block-introducing header (ends with colon)."""
    stripped = line.strip()
    return stripped.endswith(":") and any(
        stripped.startswith(kw) for kw in _BLOCK_KEYWORDS
    )


# ── ASCIIToHLF ─────────────────────────────────────────────────────────────────


class ASCIIToHLF:
    """Convert ASCII keyword-syntax HLF source to canonical glyph HLF source.

    The output is valid glyph-syntax HLF that can be fed directly to the
    existing HLFCompiler.  ASCII block constructs (PARALLEL:, FOR EACH...)
    are converted to glyph statements with body blocks.

    Usage:
        converter = ASCIIToHLF()
        glyph_source = converter.convert(ascii_source)
    """

    def __init__(self) -> None:
        pass

    def convert(self, source: str) -> str:
        """Convert ASCII HLF source to glyph HLF source.

        Args:
            source: ASCII-syntax HLF source text.

        Returns:
            Canonical glyph-syntax HLF source string.
        """
        self._block_types = []
        lines = source.splitlines()
        out: list[str] = []
        pending_indent: int | None = None
        block_body_lines: list[str] = []

        i = 0
        while i < len(lines):
            raw = lines[i]
            stripped = raw.strip()

            # Blank lines: preserve if not in block body
            if not stripped:
                if block_body_lines:
                    block_body_lines.append("")
                else:
                    out.append("")
                i += 1
                continue

            # Comment lines
            if stripped.startswith("#"):
                if block_body_lines:
                    block_body_lines.append(raw)
                else:
                    out.append(raw)
                i += 1
                continue

            # Header
            if _HEADER_RE.match(stripped):
                out.append(stripped)
                i += 1
                continue

            # If we're inside a block body, check for dedent
            # IMPORTANT: this must come BEFORE END/OMEGA checks so that
            # END at dedent level triggers block flush before termination.
            if pending_indent is not None:
                indent = _get_indent(raw)
                if indent <= pending_indent and not (stripped == ""):
                    # End of block body — flush it
                    block_type = (
                        self._block_types.pop()
                        if hasattr(self, "_block_types") and self._block_types
                        else "PARALLEL"
                    )
                    if block_type == "PARALLEL":
                        # Each indented line is its own parallel task block
                        for body_line in block_body_lines:
                            if body_line.strip():
                                out.append("{")
                                out.append(body_line)
                                out.append("}")
                    elif block_type == "FOR":
                        # Single block body
                        block_text = "\n".join(block_body_lines)
                        out.append("{")
                        if block_text.strip():
                            out.append(block_text)
                        out.append("}")
                    else:
                        # Generic block (DEFINE etc.)
                        block_text = "\n".join(block_body_lines)
                        out.append("{")
                        if block_text.strip():
                            out.append(block_text)
                        out.append("}")
                    pending_indent = None
                    block_body_lines = []
                    # Reprocess this line
                    continue
                else:
                    # Still inside block, convert recursively
                    block_body_lines.append(self.convert_line(stripped))
                    i += 1
                    continue

            # Check for block header
            if _is_block_header(stripped):
                block_keyword = stripped.rstrip(":").split(None, 1)[0].upper()
                header_glyph = self._convert_block_header(stripped)
                out.append(header_glyph)
                pending_indent = _get_indent(raw)
                block_body_lines = []
                # Tag this block with its keyword type for post-processing
                if not hasattr(self, "_block_types"):
                    self._block_types = []
                self._block_types.append(block_keyword)
                i += 1
                continue

            # Check for indented continuation (sub-statement under previous primary)
            current_indent = _get_indent(raw)
            if current_indent > 0 and out:
                # Indented sub-statement
                converted = self.convert_line(stripped)
                out.append("  " + converted)
                i += 1
                continue

            # Terminator (ASCII: END → Ω)
            if _END_RE.match(stripped):
                out.append("Ω")
                i += 1
                continue

            # Omega terminator (already glyph, pass through)
            if _OMEGA_RE.match(stripped):
                out.append("Ω")
                i += 1
                continue

            # Regular statement
            converted = self.convert_line(stripped)
            out.append(converted)
            i += 1

        # Flush any remaining block
        if pending_indent is not None:
            block_type = (
                self._block_types.pop()
                if hasattr(self, "_block_types") and self._block_types
                else "PARALLEL"
            )
            if block_type == "PARALLEL":
                for body_line in block_body_lines:
                    if body_line.strip():
                        out.append("{")
                        out.append(body_line)
                        out.append("}")
            elif block_type == "FOR":
                block_text = "\n".join(block_body_lines)
                out.append("{")
                if block_text.strip():
                    out.append(block_text)
                out.append("}")
            else:
                block_text = "\n".join(block_body_lines)
                out.append("{")
                if block_text.strip():
                    out.append(block_text)
                out.append("}")

        return "\n".join(out) + "\n"

    def convert_line(self, line: str) -> str:
        """Convert a single ASCII keyword line to glyph form.

        Args:
            line: A single ASCII-syntax statement line (no leading whitespace).

        Returns:
            Glyph-syntax equivalent line.
        """
        line = line.strip()

        # Already a glyph line
        if line and line[0] in "ΔЖ⨝⌘∇⩕⊎⌂Σ":
            return line

        # Already has [HLF- header
        if _HEADER_RE.match(line):
            return line

        # ANALYZE <goal>
        m = _ANALYZE_RE.match(line)
        if m:
            goal = m.group(1).strip()
            return f'Δ [INTENT] goal="{_escape_str(goal)}"'

        # EXECUTE <goal>
        m = _EXECUTE_RE.match(line)
        if m:
            goal = m.group(1).strip()
            return f'⌘ [EXEC] goal="{_escape_str(goal)}"'

        # IF <condition> THEN [<tag>]
        m = _IF_THEN_RE.match(line)
        if m:
            condition = m.group(1).strip()
            tag = m.group(2)
            return f'⊎ [{tag}] condition="{_escape_str(condition)}"'

        # ELSE (standalone)
        if _ELSE_RE.match(line):
            return "⊎ [ELSE]"

        # ELIF <condition>
        m = _ELIF_RE.match(line)
        if m:
            condition = m.group(1).strip()
            return f'⊎ [ELIF] condition="{_escape_str(condition)}"'

        # ENDIF
        if _ENDIF_RE.match(line):
            return "⊎ [ENDIF]"

        # SET / LET <name> = <value>
        m = _SET_RE.match(line)
        if m:
            name = m.group(1).strip()
            value = m.group(2).strip()
            return f'⩕ [SET] name="{_escape_str(name)}" value="{_escape_str(value)}"'

        # DEFINE <name>(<params>): <body>  or  DEFINE <name>(<params>)
        m = _DEFINE_RE.match(line)
        if m:
            name = m.group(1).strip()
            params = m.group(2).strip()
            body = m.group(3).strip()
            result = f'⌂ [FUNC] name="{_escape_str(name)}" params="{_escape_str(params)}"'
            if body:
                result += f' body="{_escape_str(body)}"'
            return result

        # RETURN <value>
        m = _RETURN_RE.match(line)
        if m:
            value = m.group(1).strip()
            return f'Ж [RETURN] value="{_escape_str(value)}"'

        # LOG <value>
        m = _LOG_RE.match(line)
        if m:
            value = m.group(1).strip()
            return f'Ж [LOG] value="{_escape_str(value)}"'

        # PARALLEL:
        if _PARALLEL_RE.match(line):
            return "∇ [PARALLEL]"

        # CONSTRAINT <name> <min>..<max>
        m = _CONSTRAINT_RE.match(line)
        if m:
            name = m.group(1).strip()
            vmin = m.group(2).strip()
            vmax = m.group(3).strip()
            return (
                f'⨝ [CONSTRAINT] name="{_escape_str(name)}" '
                f'min={vmin} max={vmax}'
            )

        # SPEC_GATE <name>
        m = _SPEC_GATE_RE.match(line)
        if m:
            name = m.group(1).strip()
            return f'⌘ [SPEC_GATE] name="{_escape_str(name)}"'

        # SPEC_DEFINE <name>
        m = _SPEC_DEFINE_RE.match(line)
        if m:
            name = m.group(1).strip()
            return f'⌘ [SPEC_DEFINE] name="{_escape_str(name)}"'

        # FOR EACH <item> IN <collection>:
        m = _FOR_EACH_RE.match(line)
        if m:
            item = m.group(1).strip()
            collection = m.group(2).strip()
            return (
                f'∇ [FOR] item="{_escape_str(item)}" '
                f'collection="{_escape_str(collection)}"'
            )

        # ASSERT <condition>
        m = _ASSERT_RE.match(line)
        if m:
            condition = m.group(1).strip()
            return f'∇ [ASSERT] condition="{_escape_str(condition)}"'

        # Generic ASCII_ALIASES substitution for simple keyword lines
        m = _KEYWORD_LINE_RE.match(line)
        if m:
            keyword = m.group(1)
            rest = line[len(keyword) :].strip()
            glyph, tag = _ASCII_TO_GLYPH_TAG.get(keyword, (None, None))
            if glyph is not None and tag is not None:
                if rest:
                    return f'{glyph} [{tag}] value="{_escape_str(rest)}"'
                else:
                    return f"{glyph} [{tag}]"
            # Fallback: use ASCII_ALIASES for glyph substitution
            if keyword in ASCII_ALIASES:
                glyph_char = ASCII_ALIASES[keyword]
                if rest:
                    return f"{glyph_char} {rest}"
                return glyph_char

        # Fallback: pass through unchanged (might be a value or already glyph)
        return line

    def _convert_block_header(self, line: str) -> str:
        """Convert a block-introducing header (ends with colon) to glyph/keyword form.

        Returns the opening line for the block.  For constructs that the
        grammar handles via keywords (PARALLEL, FOR), the keyword form is
        returned.  For others, glyph form is used.
        """
        stripped = line.rstrip(":").strip()

        # PARALLEL: → keyword form (grammar: KW_PARALLEL block block+)
        if stripped == "PARALLEL":
            return "PARALLEL"

        # FOR EACH <item> IN <collection>: → keyword form (grammar: KW_FOR IDENT KW_IN expr block)
        m = _FOR_EACH_RE.match(line)
        if m:
            item = m.group(1).strip()
            collection = m.group(2).strip()
            return f"FOR {item} IN {collection}"

        # DEFINE <name>(<params>): → glyph form
        if stripped.startswith("DEFINE"):
            m = _DEFINE_RE.match(line.rstrip(":"))
            if m:
                name = m.group(1).strip()
                params = m.group(2).strip()
                return (
                    f'⌂ [FUNC] name="{_escape_str(name)}" '
                    f'params="{_escape_str(params)}"'
                )

        # Generic: KEYWORD: → glyph form
        parts = stripped.split(None, 1)
        kw = parts[0].upper() if parts else stripped.upper()
        info = _ASCII_TO_GLYPH_TAG.get(kw)
        if info:
            glyph, tag = info
            rest = parts[1] if len(parts) > 1 else ""
            if rest:
                return f'{glyph} [{tag}] value="{_escape_str(rest)}"'
            return f"{glyph} [{tag}]"

        return f"∇ [{kw}]"


# ── HLFToASCII ─────────────────────────────────────────────────────────────────


class HLFToASCII:
    """Convert canonical glyph HLF source to ASCII keyword-syntax HLF.

    The output uses ASCII keywords (IF, ANALYZE, SET, etc.) and END
    as the terminator instead of Ω.

    Usage:
        converter = HLFToASCII()
        ascii_source = converter.convert(glyph_source)
    """

    def convert(self, source: str) -> str:
        """Convert glyph HLF source to ASCII keyword-syntax HLF source.

        Args:
            source: Glyph-syntax HLF source text.

        Returns:
            ASCII keyword-syntax HLF source string.
        """
        lines = source.splitlines()
        out: list[str] = []
        in_block = False

        for raw in lines:
            stripped = raw.strip()

            # Blank lines
            if not stripped:
                out.append("")
                continue

            # Comment lines
            if stripped.startswith("#"):
                out.append(raw)
                continue

            # Header
            if _HEADER_RE.match(stripped):
                out.append(stripped)
                continue

            # Omega terminator → END
            if _OMEGA_RE.match(stripped):
                out.append("END")
                in_block = False
                continue

            # Block close
            if stripped == "}":
                in_block = False
                out.append("}")
                continue

            # Glyph line
            g_m = _GLYPH_LINE_RE.match(stripped)
            if g_m:
                prefix = g_m.group(1)
                glyph = g_m.group(2)
                rest = g_m.group(3).strip() if g_m.group(3) else ""

                converted = self._convert_glyph_line(
                    glyph, rest, is_sub=bool(prefix)
                )
                if converted:
                    # Preserve indentation for sub-statements
                    indent = prefix if prefix else ""
                    out.append(indent + converted)
                    if glyph in {"Δ", "⌘", "⊎", "⌂", "Σ"}:
                        in_block = True
                else:
                    out.append(stripped)
                continue

            # Keyword statement lines (PARALLEL, FOR, etc.)
            kw_converted = self._convert_keyword_line(stripped)
            if kw_converted is not None:
                out.append(kw_converted)
                continue

            # Non-glyph/non-keyword line — pass through
            out.append(stripped)

        return "\n".join(out) + "\n"

    def _convert_glyph_line(
        self, glyph: str, rest: str, *, is_sub: bool = False
    ) -> str:
        """Convert a single glyph line (glyph + rest) to ASCII keyword form.

        Args:
            glyph: The Unicode glyph character.
            rest: Everything after the glyph on the line.
            is_sub: True if this is a sub-statement (indented).

        Returns:
            ASCII keyword equivalent line, or empty string if unresolvable.
        """
        # Extract tag from rest
        tag_match = _TAG_RE.search(rest)
        tag = tag_match.group(1) if tag_match else None

        # Extract key-value arguments
        kv_args: dict[str, str] = {}
        for m in _KV_ARG_RE.finditer(rest):
            kv_args[m.group(1)] = m.group(2)
        # Bare key=value (no quotes)
        remainder = rest
        if tag_match:
            remainder = rest[tag_match.end() :].strip()
        for m in _KV_ARG_BARE_RE.finditer(remainder):
            if m.group(1) not in kv_args:
                kv_args[m.group(1)] = m.group(2)

        # Check for inline condition ⇒ [TAG] pattern
        cond_arrow = _COND_ARROW_TAG_RE.match(rest)
        if cond_arrow:
            condition = cond_arrow.group(1).strip()
            arrow_tag = cond_arrow.group(2)
            return f"IF {condition} THEN [{arrow_tag}]"

        # Determine ASCII keyword from glyph and tag
        ascii_kw = self._resolve_keyword(glyph, tag)

        # ── Build ASCII output based on keyword ──────────────────────────────

        # ANALYZE (Δ)
        if ascii_kw == "ANALYZE":
            goal = kv_args.get("goal", kv_args.get("value", rest.strip()))
            return f"ANALYZE {goal}"

        # EXECUTE (⌘)
        if ascii_kw == "EXECUTE":
            goal = kv_args.get("goal", kv_args.get("value", rest.strip()))
            return f"EXECUTE {goal}"

        # IF (⊎)
        if ascii_kw == "IF":
            condition = kv_args.get("condition", "")
            if condition and tag and tag not in ("IF", "BRANCH", "ELSE", "ELIF", "ENDIF"):
                return f"IF {condition} THEN [{tag}]"
            if tag == "ELSE":
                return "ELSE"
            if tag == "ELIF":
                condition = kv_args.get("condition", "")
                return f"ELIF {condition}"
            if tag == "ENDIF":
                return "ENDIF"
            if condition:
                return f"IF {condition}"
            return f"IF [{tag}]" if tag else "IF"

        # SET (⩕)
        if ascii_kw == "SET":
            name = kv_args.get("name", "")
            value = kv_args.get("value", rest.strip())
            return f"SET {name} = {value}"

        # DEFINE (⌂)
        if ascii_kw == "DEFINE":
            name = kv_args.get("name", "")
            params = kv_args.get("params", "")
            return f"DEFINE {name}({params})"

        # RETURN (Ж)
        if ascii_kw == "RETURN":
            value = kv_args.get("value", rest.strip())
            return f"RETURN {value}"

        # LOG (Ж)
        if ascii_kw == "LOG":
            value = kv_args.get("value", rest.strip())
            return f"LOG {value}"

        # ASSERT (∇)
        if ascii_kw == "ASSERT":
            condition = kv_args.get("condition", rest.strip())
            return f"ASSERT {condition}"

        # PARALLEL (∇)
        if ascii_kw == "PARALLEL":
            return "PARALLEL:"

        # CONSTRAINT (⨝)
        if ascii_kw == "CONSTRAINT":
            name = kv_args.get("name", "")
            vmin = kv_args.get("min", "0")
            vmax = kv_args.get("max", "100")
            return f"CONSTRAINT {name} {vmin}..{vmax}"

        # ENFORCE (Ж)
        if ascii_kw == "ENFORCE":
            value = kv_args.get("value", rest.strip())
            return f"ENFORCE {value}"

        # SOURCE (∇)
        if ascii_kw == "SOURCE":
            value = kv_args.get("value", rest.strip())
            return f"SOURCE {value}"

        # PRIORITY (⩕)
        if ascii_kw == "PRIORITY":
            value = kv_args.get("value", rest.strip())
            return f"PRIORITY {value}"

        # SUMMARY (Σ)
        if ascii_kw == "SUMMARY":
            value = kv_args.get("value", rest.strip())
            return f"SUMMARY {value}"

        # VOTE (⨝)
        if ascii_kw == "VOTE":
            value = kv_args.get("value", rest.strip())
            return f"VOTE {value}"

        # MEMORY (⌂)
        if ascii_kw == "MEMORY":
            name = kv_args.get("name", "")
            value = kv_args.get("value", rest.strip())
            if name and value:
                return f"MEMORY [{name}] value=\"{value}\""
            if name:
                return f"MEMORY [{name}]"
            return "MEMORY"

        # SPEC_GATE
        if tag == "SPEC_GATE":
            name = kv_args.get("name", kv_args.get("value", rest.strip()))
            return f"SPEC_GATE {name}"

        # SPEC_DEFINE
        if tag == "SPEC_DEFINE":
            name = kv_args.get("name", kv_args.get("value", rest.strip()))
            return f"SPEC_DEFINE {name}"

        # FOR loop
        if tag == "FOR":
            item = kv_args.get("item", "")
            collection = kv_args.get("collection", rest.strip())
            return f"FOR EACH {item} IN {collection}:"

        # Fallback: generic glyph → keyword + rest
        if ascii_kw and ascii_kw != glyph:
            if rest.strip():
                return f"{ascii_kw} {rest}"
            return ascii_kw

        # Ultimate fallback: keep glyph
        return f"{glyph} {rest}"

    def _resolve_keyword(self, glyph: str, tag: str | None) -> str:
        """Resolve the ASCII keyword for a glyph+tag combination."""
        # Check tag-sensitive overrides first
        if tag and glyph in _TAG_KEYWORD_OVERRIDE:
            override = _TAG_KEYWORD_OVERRIDE[glyph].get(tag)
            if override:
                return override

        # Fall back to canonical mapping
        return _GLYPH_TO_ASCII_KEYWORD.get(glyph, glyph)

    @staticmethod
    def _convert_keyword_line(line: str) -> str | None:
        """Convert a non-glyph keyword line to ASCII surface form.

        Handles keyword statements like FOR, PARALLEL that appear in the
        glyph output as keywords (since the grammar uses keyword form for
        block-bearing constructs).

        Returns the converted line, or None if the line is not a
        recognized keyword form.
        """
        # FOR <item> IN <collection> → FOR EACH <item> IN <collection>:
        for_m = re.match(r"^FOR\s+(\S+)\s+IN\s+(.+)$", line)
        if for_m:
            item = for_m.group(1)
            collection = for_m.group(2)
            return f"FOR EACH {item} IN {collection}:"

        # PARALLEL (already correct, just normalize)
        if line.strip() == "PARALLEL":
            return "PARALLEL:"

        return None


# ── Round-trip validation ──────────────────────────────────────────────────────


def ascii_roundtrip(text: str) -> dict[str, Any]:
    """Validate ASCII → Glyph → ASCII round-trip preserves semantics.

    Converts ASCII source to glyph form and back, then compares the
    original and recovered ASCII for fidelity.

    Args:
        text: ASCII-syntax HLF source to validate.

    Returns:
        dict with keys:
          - roundtrip_success: bool
          - original_ascii: str
          - generated_glyph: str
          - recovered_ascii: str
          - fidelity: float (0.0–1.0 percentage match)
    """
    to_glyph = ASCIIToHLF()
    to_ascii = HLFToASCII()

    generated_glyph = to_glyph.convert(text)
    recovered_ascii = to_ascii.convert(generated_glyph)

    # Compute fidelity as normalized line-level match
    orig_lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    recov_lines = [l.strip() for l in recovered_ascii.strip().splitlines() if l.strip()]

    if not orig_lines:
        fidelity = 1.0 if not recov_lines else 0.0
    else:
        matches = 0
        for orig_line in orig_lines:
            # Look for a matching line in recovered (order-independent comparison
            # because some constructs like blocks may reorder)
            for recov_line in recov_lines:
                if _lines_semantically_match(orig_line, recov_line):
                    matches += 1
                    break
        fidelity = matches / len(orig_lines) if orig_lines else 1.0

    roundtrip_success = fidelity >= 0.90

    return {
        "roundtrip_success": roundtrip_success,
        "original_ascii": text,
        "generated_glyph": generated_glyph,
        "recovered_ascii": recovered_ascii,
        "fidelity": round(fidelity, 4),
    }


def _lines_semantically_match(a: str, b: str) -> bool:
    """Check if two ASCII HLF lines are semantically equivalent."""
    # Normalize: strip comments, collapse whitespace
    a_norm = re.sub(r"#.*$", "", a).strip()
    b_norm = re.sub(r"#.*$", "", b).strip()

    if a_norm == b_norm:
        return True

    # LET and SET are equivalent
    a_set = a_norm.replace("LET ", "SET ")
    b_set = b_norm.replace("LET ", "SET ")
    if a_set == b_set:
        return True

    # ANALYZE / ANALYSE are equivalent
    a_analyze = a_set.replace("ANALYSE ", "ANALYZE ")
    b_analyze = b_set.replace("ANALYSE ", "ANALYZE ")
    if a_analyze == b_analyze:
        return True

    return False


# ── ASCII detection ────────────────────────────────────────────────────────────


def is_ascii_hlf(source: str) -> bool:
    """Detect whether source is ASCII-style HLF vs glyph-style HLF.

    ASCII-style HLF starts with ASCII keywords (ANALYZE, IF, SET, etc.)
    or the [HLF-vN] header followed by ASCII keywords.

    Glyph-style HLF starts with Unicode glyphs (Δ, Ж, ⨝, ⌘, etc.)
    or the [HLF-vN] header followed by glyphs.

    Args:
        source: HLF source text to analyze.

    Returns:
        True if the source is ASCII-style HLF, False if glyph-style.
    """
    lines = [l.strip() for l in source.splitlines() if l.strip()]
    if not lines:
        return False

    for line in lines:
        # Skip header, blank, and comment lines
        if not line or line.startswith("#") or _HEADER_RE.match(line):
            continue

        # If line starts with a glyph character, it's glyph-style
        if line and line[0] in "ΔЖ⨝⌘∇⩕⊎⌂Σ":
            return False

        # If line starts with a recognized ASCII keyword, it's ASCII-style
        if _KEYWORD_LINE_RE.match(line) or line.startswith("END"):
            return True

        # If the line starts with END, it's ASCII
        if _END_RE.match(line):
            return True

        # If line starts with { or } (block delimiters), skip
        if line in ("{", "}"):
            continue

        # Any other non-empty line: check first char
        if line:
            first_char = line[0]
            if ord(first_char) > 127:
                return False  # Unicode → glyph-style
            return True  # ASCII → ascii-style

    # All lines were headers/blank/comments — default to ASCII
    return True


# ── String escaping helper ─────────────────────────────────────────────────────


def _escape_str(s: str) -> str:
    """Escape a string value for inclusion in a quoted glyph argument."""
    return s.replace("\\", "\\\\").replace('"', '\\"')
