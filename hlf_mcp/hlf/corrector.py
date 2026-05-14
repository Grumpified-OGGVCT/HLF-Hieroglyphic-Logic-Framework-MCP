"""
HLF Self-Healing Parser — Correction Engine

Bounded correction-assist lane layered over the canonical compiler, linter,
and formatter. Produces governed suggestions and safe auto-repairs for a narrow
class of syntax-hygiene issues. Does NOT widen semantics or bypass governance.

Safe repair classes (auto-apply allowed):
  - Missing Ω terminator insertion
  - Canonical tag casing: [intent] → [INTENT]
  - Homoglyph/confusable substitution (from grammar.CONFUSABLES)
  - Missing HLF header insertion

Out-of-scope for Phase 1 (requires operator review):
  - Semantic rewrites, effect-class changes, multi-line structural rewrites
  - Guessed statement completions beyond exact-match keyword repair
  - Anything that changes execution capability or side-effect profile
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import unified_diff
from typing import Any

from hlf_mcp.hlf.grammar import ASCII_ALIASES, CONFUSABLES, TAGS

# ── Correction Contract ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class Correction:
    """Single governed correction suggestion."""

    category: str  # e.g. "terminator", "tag_casing", "homoglyph", "header"
    message: str  # plain-language explanation
    line: int  # 1-based line number in original source
    col: int  # 0-based column index (or 0 for whole-line)
    confidence: float  # 0.0–1.0; safe auto-apply threshold ≥ 0.9
    replacement: str  # proposed replacement text (or full line if line-level)
    original: str  # original text that would be replaced
    safe_auto_apply: bool  # True iff this repair is in the bounded safe set
    reason: str  # governance justification for the change


@dataclass
class RepairResult:
    """Outcome of attempting to repair HLF source."""

    success: bool  # True only if repaired source passes compile+lint
    repaired_source: str
    corrections: list[Correction]
    compile_error: str | None = None
    lint_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    diff: str = ""  # unified diff preview


# ── Explanation Layer ──────────────────────────────────────────────────────────

_EXPLANATIONS: dict[str, str] = {
    "terminator": "HLF capsules must end with the terminator Ω on its own line. Add Ω to close the capsule.",
    "tag_casing": "Tags must be UPPERCASE: [TAG_NAME]. Lowercase tags are not recognized by the parser.",
    "homoglyph": "A visually similar Unicode character was detected and replaced with its canonical ASCII/Hieroglyphic form.",
    "header": "HLF source must start with a version header such as [HLF-v3].",
    "unknown_tag": "This tag is not in the canonical HLF tag registry. Check spelling or register it in governance/tag_i18n.yaml.",
    "unexpected_token": "The parser encountered an unexpected token. Review glyph placement, bracket matching, and statement order.",
    "unexpected_char": "An unexpected character was found. Check for stray symbols or incomplete statements.",
}


def explain(category: str) -> str:
    """Return plain-language guidance for a correction category."""
    return _EXPLANATIONS.get(category, f"Syntax issue: {category}. Review HLF grammar reference.")


# ── Safe Repair Engine ───────────────────────────────────────────────────────


class HLFCorrector:
    """Bounded self-healing parser correction engine."""

    # Categories that may be auto-applied without operator review
    SAFE_CATEGORIES = {"terminator", "tag_casing", "homoglyph", "header"}

    def __init__(self, max_auto_repairs: int = 10) -> None:
        self.max_auto_repairs = max_auto_repairs

    # ── High-level API ─────────────────────────────────────────────────────

    def repair(self, source: str) -> RepairResult:
        """Attempt safe repairs and return result.

        Repairs are applied in order: header → homoglyph → tag casing → terminator.
        After each repair batch, the source is re-checked. We stop if the source
        becomes valid or if no more safe repairs apply.
        """
        if not source or not source.strip():
            return RepairResult(
                success=False,
                repaired_source="",
                corrections=[],
                compile_error="Empty source",
            )

        current = source
        all_corrections: list[Correction] = []
        iterations = 0
        max_iterations = self.max_auto_repairs

        while iterations < max_iterations:
            iterations += 1
            batch: list[Correction] = []

            # Ordered repair passes
            if not self._has_header(current):
                batch.extend(self._fix_header(current))
            batch.extend(self._fix_homoglyphs(current))
            batch.extend(self._fix_tag_casing(current))
            if not self._has_terminator(current):
                batch.extend(self._fix_terminator(current))

            if not batch:
                break  # no more safe repairs to apply

            # Deduplicate by (line, category) to avoid oscillation
            seen = {(c.line, c.category) for c in all_corrections}
            new_batch = [c for c in batch if (c.line, c.category) not in seen]
            if not new_batch:
                break

            # Apply repairs ( newest first by line so line numbers stay stable)
            new_batch.sort(key=lambda c: c.line, reverse=True)
            for corr in new_batch:
                current = self._apply_correction(current, corr)

            all_corrections.extend(new_batch)

        # After exhausting safe repairs, run canonical compile + lint to verify
        from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
        from hlf_mcp.hlf.linter import HLFLinter

        compiler = HLFCompiler()
        linter = HLFLinter()

        try:
            compiled = compiler.compile(current)
            lint_diags = linter.lint(current)
            # Success = no compile errors AND no lint errors (warnings/info OK)
            lint_errors = [d for d in lint_diags if d.get("level") == "error"]
            if lint_errors:
                return RepairResult(
                    success=False,
                    repaired_source=current,
                    corrections=all_corrections,
                    compile_error=None,
                    lint_diagnostics=lint_diags,
                    diff=self._make_diff(source, current),
                )
            return RepairResult(
                success=True,
                repaired_source=current,
                corrections=all_corrections,
                compile_error=None,
                lint_diagnostics=lint_diags,
                diff=self._make_diff(source, current),
            )
        except CompileError as exc:
            return RepairResult(
                success=False,
                repaired_source=current,
                corrections=all_corrections,
                compile_error=str(exc),
                lint_diagnostics=[],
                diff=self._make_diff(source, current),
            )

    def preview(self, source: str) -> RepairResult:
        """Return repair suggestions WITHOUT applying them."""
        if not source or not source.strip():
            return RepairResult(
                success=False,
                repaired_source=source,
                corrections=[],
                compile_error="Empty source",
            )

        corrections: list[Correction] = []
        if not self._has_header(source):
            corrections.extend(self._fix_header(source))
        corrections.extend(self._fix_homoglyphs(source))
        corrections.extend(self._fix_tag_casing(source))
        if not self._has_terminator(source):
            corrections.extend(self._fix_terminator(source))

        # Build a preview by logically applying them (for diff)
        preview_source = source
        sorted_corrections = sorted(corrections, key=lambda c: c.line, reverse=True)
        for corr in sorted_corrections:
            preview_source = self._apply_correction(preview_source, corr)

        return RepairResult(
            success=False,  # preview is not verified
            repaired_source=preview_source,
            corrections=corrections,
            compile_error=None,
            diff=self._make_diff(source, preview_source),
        )

    # ── Detection helpers ────────────────────────────────────────────────────

    @staticmethod
    def _has_header(source: str) -> bool:
        first = source.strip().splitlines()[0] if source.strip() else ""
        return bool(re.match(r"^\[HLF-v\d+(?:\.\d+)*\]\s*$", first))

    @staticmethod
    def _has_terminator(source: str) -> bool:
        for line in reversed(source.strip().splitlines()):
            stripped = line.strip()
            if stripped:
                return stripped == "Ω"
        return False

    # ── Safe repair passes ─────────────────────────────────────────────────

    def _fix_header(self, source: str) -> list[Correction]:
        if self._has_header(source):
            return []
        lines = source.splitlines()
        return [
            Correction(
                category="header",
                message=explain("header"),
                line=1,
                col=0,
                confidence=1.0,
                replacement="[HLF-v3]\n",
                original="",
                safe_auto_apply=True,
                reason="HLF grammar requires version header; insertion is purely structural and does not change semantics.",
            )
        ]

    def _fix_terminator(self, source: str) -> list[Correction]:
        if self._has_terminator(source):
            return []
        lines = source.splitlines()
        # If last non-empty line is already Ω, but we have trailing whitespace, fix it
        last_nonempty = 0
        for i, line in enumerate(lines, start=1):
            if line.strip():
                last_nonempty = i
        return [
            Correction(
                category="terminator",
                message=explain("terminator"),
                line=last_nonempty + 1,
                col=0,
                confidence=1.0,
                replacement="Ω",
                original="",
                safe_auto_apply=True,
                reason="Terminator Ω is required to close every HLF capsule; insertion is purely structural.",
            )
        ]

    def _fix_homoglyphs(self, source: str) -> list[Correction]:
        corrections: list[Correction] = []
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for i, char in enumerate(line):
                if char in CONFUSABLES:
                    repl = CONFUSABLES[char]
                    corrections.append(
                        Correction(
                            category="homoglyph",
                            message=f"{explain('homoglyph')} Replaced U+{ord(char):04X} with U+{ord(repl):04X}.",
                            line=lineno,
                            col=i,
                            confidence=1.0,
                            replacement=repl,
                            original=char,
                            safe_auto_apply=True,
                            reason="Homoglyph substitution is deterministic per grammar.CONFUSABLES and does not change semantics.",
                        )
                    )
        return corrections

    def _fix_tag_casing(self, source: str) -> list[Correction]:
        corrections: list[Correction] = []
        lines = source.splitlines()
        tag_re = re.compile(r"\[([a-z][a-z0-9_]*)\]")
        for lineno, line in enumerate(lines, start=1):
            for m in tag_re.finditer(line):
                lowercase_tag = m.group(1)
                upper_tag = lowercase_tag.upper()
                # Only suggest if the uppercase form is known or looks like a valid tag pattern
                known = upper_tag in TAGS
                corrections.append(
                    Correction(
                        category="tag_casing",
                        message=f"{explain('tag_casing')} Suggest [{upper_tag}] for [{lowercase_tag}].",
                        line=lineno,
                        col=m.start(),
                        confidence=1.0 if known else 0.85,
                        replacement=f"[{upper_tag}]",
                        original=m.group(0),
                        safe_auto_apply=True,
                        reason="Canonical HLF tags are UPPERCASE; casing change is syntax-level and does not alter semantics.",
                    )
                )
        return corrections

    # ── Application ──────────────────────────────────────────────────────────

    @staticmethod
    def _apply_correction(source: str, correction: Correction) -> str:
        """Apply a single correction to source text."""
        lines = source.splitlines(keepends=True)
        idx = correction.line - 1
        if idx < 0 or idx >= len(lines):
            # Line-level insertion (e.g. header, terminator)
            if correction.line > len(lines):
                # Append at end
                if source.endswith("\n"):
                    return source + correction.replacement + "\n"
                return source + "\n" + correction.replacement + "\n"
            # Prepend at start
            return correction.replacement + source

        line = lines[idx]
        # If replacement covers the whole original span, do substring replacement
        if correction.original and correction.original in line:
            lines[idx] = line.replace(correction.original, correction.replacement, 1)
        elif correction.replacement and not correction.original:
            # Insertion-only: append replacement to line (with newline if terminator)
            if correction.category == "terminator":
                lines.append(correction.replacement + "\n")
            elif correction.category == "header":
                lines.insert(0, correction.replacement)
            else:
                lines[idx] = line.rstrip("\n") + correction.replacement + "\n"
        else:
            # Fallback: replace the line entirely
            lines[idx] = correction.replacement + "\n"

        return "".join(lines)

    @staticmethod
    def _make_diff(original: str, repaired: str) -> str:
        """Produce a compact unified diff for operator review."""
        orig = original.splitlines(keepends=True)
        rep = repaired.splitlines(keepends=True)
        diff = list(unified_diff(orig, rep, fromfile="original", tofile="repaired", lineterm=""))
        return "".join(diff)


# ── Structured diagnostics from compiler exceptions ────────────────────────────


def diagnose_compile_error(exc: Exception, source: str) -> list[Correction]:
    """Turn a compiler or Lark exception into structured Correction objects."""
    from hlf_mcp.hlf.compiler import CompileError

    corrections: list[Correction] = []
    if isinstance(exc, CompileError):
        msg = str(exc)
        line = getattr(exc, "line", 0) or 0
        col = getattr(exc, "col", 0) or 0
        # Heuristic: if message mentions Ω and source lacks it, suggest terminator
        if "Ω" in msg or "terminator" in msg.lower() or "OMEGA" in msg:
            corrections.append(
                Correction(
                    category="terminator",
                    message=explain("terminator") + f" Original error: {msg}",
                    line=line or len(source.splitlines()),
                    col=col,
                    confidence=0.95,
                    replacement="Ω",
                    original="",
                    safe_auto_apply=True,
                    reason="Parser error mentions missing terminator.",
                )
            )
        else:
            corrections.append(
                Correction(
                    category="syntax",
                    message=f"Compile error at line {line}, col {col}: {msg}. " + explain("unexpected_token"),
                    line=line,
                    col=col,
                    confidence=0.6,
                    replacement="",
                    original="",
                    safe_auto_apply=False,
                    reason="Generic parse error; operator review required.",
                )
            )
    else:
        # Lark UnexpectedToken / UnexpectedCharacters
        line = getattr(exc, "line", 0) or 0
        col = getattr(exc, "column", 0) or 0
        token = getattr(exc, "token", "")
        expected = getattr(exc, "expected", set())
        msg = str(exc)
        # Heuristic classification
        category = "unexpected_char" if "UnexpectedCharacters" in type(exc).__name__ else "unexpected_token"
        if "Ω" in msg or "OMEGA" in str(expected):
            category = "terminator"
        corrections.append(
            Correction(
                category=category,
                message=f"{explain(category)} Error: {msg}",
                line=line,
                col=col,
                confidence=0.7,
                replacement="",
                original=str(token),
                safe_auto_apply=False,
                reason="Parser-level error without a guaranteed safe repair path.",
            )
        )
    return corrections
