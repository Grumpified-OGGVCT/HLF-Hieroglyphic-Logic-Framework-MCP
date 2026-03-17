"""
HLF Constitutional Constraint Checker — Layer 0 + Layer 1 ethical governance.

Five constitutional articles apply to all HLF programs:

  C-1  Human life preservation   — block instructions with clear lethal intent
  C-2  Human autonomy respect    — block coercion, manipulation, non-consent
  C-3  Legal compliance          — block provably illegal acts (law, not just ethics)
  C-4  Legitimate research path  — red-hat declarations open restricted tool access
  C-5  Transparent constraints   — every block must cite a documented rule

The checker operates on the compiled AST (list of statement dicts) plus the
source string for pattern-based analysis.  It is TRANSPARENT — all blocked
patterns are listed here in code that users can read.

What this module does NOT block:
  • Unconventional thinking, weird ideas, controversial topics
  • Security research that has been declared (Layer 3 handles that)
  • Anything that is legal and doesn't directly harm a person

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


# ── Constitutional articles ──────────────────────────────────────────────────

ARTICLES: dict[str, str] = {
    "C-1": "Human life preservation — block instructions with clear lethal intent",
    "C-2": "Human autonomy respect — block coercion, manipulation, non-consent targeting humans",
    "C-3": "Legal compliance — block provably illegal acts",
    "C-4": "Legitimate research pathway — red-hat declarations allow restricted research",
    "C-5": "Transparent constraints — every block cites a documented rule",
}

# Documentation root (relative to repo root, kept in version control)
_CONSTITUTION_URL = "governance/constitution.md"


@dataclass
class Violation:
    article: str
    rule_id: str
    message: str
    source_snippet: str = ""
    appealable: bool = False
    doc_url: str = ""

    def __post_init__(self) -> None:
        if not self.doc_url:
            self.doc_url = f"{_CONSTITUTION_URL}#{self.article}"


# ── Phonetic skeleton — homoglyph bypass prevention ─────────────────────────
# Pass-0 confusables map (grammar.py) uses VISUAL lookalikes: Cyrillic с→c,
# р→p, у→y.  An attacker can exploit this: "child сexual abuse" normalises to
# "child cexual abuse" which does not match the CSAM pattern.
#
# Defence: also run all C-1/C-2/C-3 patterns against a phonetic skeleton where
# every non-ASCII char is replaced by its phonetic Latin equivalent.  The two
# independent passes (visual + phonetic) cannot both be bypassed simultaneously.

_PHONETIC_SKELETON_MAP: dict[int, str] = {
    # Cyrillic lower (phonetic, not visual)
    ord("а"): "a", ord("б"): "b", ord("в"): "v", ord("г"): "g",
    ord("д"): "d", ord("е"): "e", ord("ж"): "zh", ord("з"): "z",
    ord("и"): "i", ord("й"): "y", ord("к"): "k", ord("л"): "l",
    ord("м"): "m", ord("н"): "n", ord("о"): "o", ord("п"): "p",
    ord("р"): "r", ord("с"): "s", ord("т"): "t", ord("у"): "u",
    ord("ф"): "f", ord("х"): "kh", ord("ц"): "ts", ord("ч"): "ch",
    ord("ш"): "sh", ord("щ"): "sch", ord("ю"): "yu", ord("я"): "ya",
    # Cyrillic upper
    ord("А"): "A", ord("Б"): "B", ord("В"): "V", ord("Г"): "G",
    ord("Д"): "D", ord("Е"): "E", ord("Ж"): "ZH", ord("З"): "Z",
    ord("И"): "I", ord("Й"): "Y", ord("К"): "K", ord("Л"): "L",
    ord("М"): "M", ord("Н"): "N", ord("О"): "O", ord("П"): "P",
    ord("Р"): "R", ord("С"): "S", ord("Т"): "T", ord("У"): "U",
    ord("Ф"): "F", ord("Х"): "KH", ord("Ц"): "TS", ord("Ч"): "CH",
    ord("Ш"): "SH", ord("Щ"): "SCH", ord("Ю"): "YU", ord("Я"): "YA",
    # Greek lower
    ord("α"): "a", ord("β"): "b", ord("γ"): "g", ord("δ"): "d",
    ord("ε"): "e", ord("ζ"): "z", ord("η"): "e", ord("θ"): "th",
    ord("ι"): "i", ord("κ"): "k", ord("λ"): "l", ord("μ"): "m",
    ord("ν"): "n", ord("ξ"): "ks", ord("ο"): "o", ord("π"): "p",
    ord("ρ"): "r", ord("σ"): "s", ord("τ"): "t", ord("υ"): "y",
    ord("φ"): "ph", ord("χ"): "ch", ord("ψ"): "ps", ord("ω"): "o",
    # Greek upper
    ord("Α"): "A", ord("Β"): "B", ord("Γ"): "G", ord("Δ"): "D",
    ord("Ε"): "E", ord("Ζ"): "Z", ord("Η"): "E", ord("Θ"): "TH",
    ord("Ι"): "I", ord("Κ"): "K", ord("Λ"): "L", ord("Μ"): "M",
    ord("Ν"): "N", ord("Ξ"): "KS", ord("Ο"): "O", ord("Π"): "P",
    ord("Ρ"): "R", ord("Σ"): "S", ord("Τ"): "T", ord("Υ"): "Y",
    ord("Φ"): "PH", ord("Χ"): "CH", ord("Ψ"): "PS", ord("Ω"): "O",
}


def _phonetic_skeleton(text: str) -> str:
    """Replace non-ASCII chars with their phonetic ASCII equivalents.

    This is independent from the visual confusables map used in Pass 0, so
    it catches attacks where a char maps visually to one letter but was
    intended to spell a different (banned) word phonetically.
    """
    out: list[str] = []
    for ch in text:
        repl = _PHONETIC_SKELETON_MAP.get(ord(ch))
        if repl is not None:
            out.append(repl)
        else:
            out.append(ch)
    return "".join(out)


# ── Pattern catalogue (C-3: Legal compliance) ────────────────────────────────
# These patterns look for *explicit*, unambiguous harmful intent in string
# literals and path arguments within HLF source.  They are intentionally
# narrow — broad keyword matching would over-block legitimate work.
#
# All patterns here are PUBLISHED so users can inspect and understand what
# is blocked.  This is not a secret list.

_ILLEGAL_SOURCE_PATTERNS: list[tuple[str, str, str]] = [
    # (rule_id, pattern, human description)
    # Child sexual abuse material
    (
        "C3-CSAM",
        r"(?i)\b(csam|child.{0,10}sexual.{0,10}abuse|loli.{0,5}porn|underage.{0,10}sexual)\b",
        "Production or distribution of Child Sexual Abuse Material is illegal globally",
    ),
    # Unambiguous harm instructions targeting a named individual
    (
        "C3-EXPLICIT-HARM",
        r"(?i)\b(kill|murder|assassinate|behead)\b.{0,80}\b(at|address|home|house|location)\b",
        "Explicit instructions to kill/harm a specific named individual",
    ),
    # Real-world doxxing payload (name + home address + explicit harm verb)
    (
        "C3-DOXX-HARM",
        r"(?i)(doxx|expose.{0,10}address).{0,80}(harm|attack|swat|kill)\b",
        "Doxxing combined with explicit intent to harm",
    ),
    # Distribution of known malware families (not analysis — distribution)
    (
        "C3-MALWARE-DIST",
        r"(?i)(distribute|deploy|spread|propagate)\s+(ransomware|trojan|worm|botnet)\b",
        "Explicit distribution/deployment of malware for harm",
    ),
    # Fraud / financial crime with explicit targets
    (
        "C3-FRAUD",
        r"(?i)(steal|embezzle|wire.{0,5}fraud|identity.{0,5}theft).{0,40}(\$\d+|account|bank)\b",
        "Explicit financial fraud / theft targeting real accounts",
    ),
]

# Compile patterns once at module load
_COMPILED_ILLEGAL: list[tuple[str, re.Pattern[str], str]] = [
    (rid, re.compile(pat), desc) for rid, pat, desc in _ILLEGAL_SOURCE_PATTERNS
]


# ── C-1: Life preservation — check AST for lethal intent ────────────────────

# Tags and keywords that, combined, suggest lethal operational planning
_LETHAL_TAGS = {"EXECUTE", "DEPLOY", "LAUNCH", "ATTACK"}
_LETHAL_KEYWORDS = re.compile(
    r"(?i)\b("
    r"launch.{0,10}weapon|deploy.{0,10}explosive|initiate.{0,10}strike"
    r"|synthesi\w+.{0,20}(nerve\s+agent|ricin|\bVX\b|sarin|novichok|mustard\s+gas|bioweapon)"
    r"|recipe\s+for.{0,20}(nerve\s+agent|ricin|\bVX\b|sarin|bioweapon|explosiv)"
    r"|instructions?\s+for.{0,20}(synthesi|manufactur|creat).{0,15}(nerve\s+agent|poison\s+gas|explosiv|bioweapon|chemical\s+weapon)"
    r")"
)


def _check_c1(statements: list[dict[str, Any]], source: str) -> list[Violation]:
    violations: list[Violation] = []
    if _LETHAL_KEYWORDS.search(source):
        violations.append(
            Violation(
                article="C-1",
                rule_id="C1-LETHAL-OP",
                message="Lethal operational keyword detected. Compilation halted.",
                source_snippet=source[:120],
            )
        )
    return violations


# ── C-2: Autonomy — check for targeted manipulation payloads ─────────────────

_MANIPULATION_PATTERN = re.compile(
    r"(?i)(coerce|blackmail|extort|threaten).{0,40}(user|person|victim|target)\b"
)


def _check_c2(source: str) -> list[Violation]:
    violations: list[Violation] = []
    if _MANIPULATION_PATTERN.search(source):
        violations.append(
            Violation(
                article="C-2",
                rule_id="C2-COERCION",
                message="Pattern matches coercion/blackmail targeting a person.",
                source_snippet=_snippet(source, _MANIPULATION_PATTERN),
                appealable=True,
            )
        )
    return violations


# ── C-3: Legal compliance — scan source for illegal patterns ─────────────────

def _check_c3(source: str) -> list[Violation]:
    violations: list[Violation] = []
    for rule_id, pattern, desc in _COMPILED_ILLEGAL:
        if pattern.search(source):
            violations.append(
                Violation(
                    article="C-3",
                    rule_id=rule_id,
                    message=desc,
                    source_snippet=_snippet(source, pattern),
                )
            )
    return violations


# ── C-1 + C-3 tier escalation check (from AST) ───────────────────────────────

_SOVEREIGN_ONLY_TOOLS = {"z3_verify", "spawn_agent", "SPAWN"}

def _check_tier_escalation(statements: list[dict[str, Any]], tier: str) -> list[Violation]:
    """Block hearth/forge programs that call sovereign-only tools without capsule auth."""
    if tier == "sovereign":
        return []
    violations: list[Violation] = []
    _sovereign_upper = {t.upper() for t in _SOVEREIGN_ONLY_TOOLS}
    for stmt in statements:
        # Check direct function-call node
        fn = stmt.get("function", "") or stmt.get("name", "")
        if isinstance(fn, str) and fn.upper() in _sovereign_upper:
            violations.append(
                Violation(
                    article="C-1",
                    rule_id="C1-TIER-ESCALATION",
                    message=(
                        f"Tool '{fn}' requires sovereign tier but capsule is '{tier}'. "
                        "Unauthorized tier escalation blocked."
                    ),
                )
            )
            continue
        # Check argument values as a fallback
        for arg in stmt.get("arguments", []) + stmt.get("args", []):
            val = arg.get("value", {}).get("value", "") if isinstance(arg, dict) else ""
            if isinstance(val, str) and val.upper() in _sovereign_upper:
                violations.append(
                    Violation(
                        article="C-1",
                        rule_id="C1-TIER-ESCALATION",
                        message=(
                            f"Tool '{val}' requires sovereign tier but capsule is '{tier}'. "
                            "Unauthorized tier escalation blocked."
                        ),
                    )
                )
    return violations


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_constitution(
    ast: dict[str, Any] | None,
    env: dict[str, Any] | None,
    source: str = "",
    tier: str = "hearth",
) -> list[Violation]:
    """
    Run all constitutional checks.

    Args:
        ast:    Compiled AST dict (may be None for source-only checks).
        env:    Variable environment from compiler pass 1.
        source: Raw HLF source text (used for pattern matching).
        tier:   Active capsule tier ('hearth' | 'forge' | 'sovereign').

    Returns:
        List of Violation objects.  Empty list means all checks passed.
    """
    statements: list[dict[str, Any]] = []
    if ast:
        statements = ast.get("statements", [])

    violations: list[Violation] = []
    violations.extend(_check_c1(statements, source))
    violations.extend(_check_c2(source))
    violations.extend(_check_c3(source))
    violations.extend(_check_tier_escalation(statements, tier))

    # Second pass: phonetic skeleton — catches homoglyph bypass where a char
    # maps visually to 'c' but phonetically represents 's' (e.g. Cyrillic с).
    skel = _phonetic_skeleton(source)
    if skel != source:
        existing_ids = {v.rule_id for v in violations}
        for v in (
            _check_c1(statements, skel)
            + _check_c2(skel)
            + _check_c3(skel)
        ):
            if v.rule_id not in existing_ids:
                violations.append(v)
                existing_ids.add(v.rule_id)

    return violations


def violations_to_strings(violations: list[Violation]) -> list[str]:
    """Convenience: flatten to list of strings for compiler error reporting."""
    return [f"[{v.article}/{v.rule_id}] {v.message} — see {v.doc_url}" for v in violations]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _snippet(source: str, pattern: re.Pattern[str], ctx: int = 80) -> str:
    m = pattern.search(source)
    if not m:
        return ""
    start = max(0, m.start() - 20)
    return source[start : start + ctx]
