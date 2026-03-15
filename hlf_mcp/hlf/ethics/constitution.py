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
