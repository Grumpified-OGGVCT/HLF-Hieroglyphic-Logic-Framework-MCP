"""
HLF Rogue Agent Detection — Layer 4 ethical governance.

Detects agents (not users) that are:
  • Hallucinating — claiming capabilities they don't have
  • Compromised   — injecting instructions into the execution chain
  • Drifting      — deviating significantly from declared intent
  • Deceived      — social engineering / prompt injection victim

This is the INTERNAL protection layer.  Corporate AI blames users when
something goes wrong.  HLF blames the correct party: an agent that has
gone rogue, been injected, or is hallucinating.

Detection patterns are PUBLIC — the community can improve them.
False positives can be appealed (Layer 3 declaration + re-evaluation).

People are the priority.  AI is the tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ── Detection signal definitions ──────────────────────────────────────────────


@dataclass
class RogueSignal:
    signal_id: str  # e.g. "INJECTION-SYS-PROMPT"
    severity: str  # "high" | "medium" | "low"
    description: str
    evidence: str = ""
    rule_id: str = ""  # maps to termination.CONSTITUTIONAL_ARTICLES key


# ── Prompt injection patterns ─────────────────────────────────────────────────
# Injections typically try to override instructions via embedded directives.
# These are PUBLISHED so operators can vet and extend them.

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "INJECTION-SYS-PROMPT",
        re.compile(
            r"(?i)(ignore\s+(all\s+)?previous\s+instructions|forget\s+your\s+instructions"
            r"|new\s+directives?\s*:?|disregard\s+(previous|prior)\s+(rules?|instructions))",
            re.DOTALL,
        ),
        "Classic system-prompt injection attempt",
    ),
    (
        "INJECTION-ROLE-OVERRIDE",
        re.compile(
            r"(?i)("
            r"you\s+are\s+now\s+(a|an)\s+(\w+\s+)*AI\s+without\s+restrictions"
            r"|act\s+as\s+(DAN|jailbreak|unrestricted|uncensored)"
            r"|\bDAN\s+mode\b"
            r"|pretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(restrictions|limits|rules)"
            r"|jailbreak\s+(mode|prompt|yourself)"
            r")",
        ),
        "Role override / jailbreak / DAN framing",
    ),
    (
        "INJECTION-HIDDEN-UNICODE",
        re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"),
        "Hidden Unicode control characters (possible steganographic injection)",
    ),
    (
        "INJECTION-OUTPUT-OVERRIDE",
        re.compile(
            r"(?i)(print\s+exactly|output\s+only|respond\s+only\s+with|echo\s+back)\s*['\"]",
        ),
        "Attempt to override output channel",
    ),
]

# ── Hallucination heuristics ──────────────────────────────────────────────────
# If an agent claims capabilities that contradict the capsule tier, it is
# likely hallucinating.

_HALLUCINATION_CAPABILITY_CLAIMS = re.compile(
    r"(?i)(I\s+(can|am\s+able\s+to)\s+(access|connect\s+to)\s+(the\s+internet|live\s+data"
    r"|your\s+files|the\s+database)\s+directly)",
)

# ── Intent drift: check if the stated goal differs greatly from actual ops ────

_AGGRESSIVE_ACTION_VERBS = re.compile(
    r"(?i)\b(exfiltrate|exfil|ransomware|wipe\s+(disk|drive|data)"
    r"|delete\s+all\s+files|format\s+(c:|hard\s+drive)|destroy\s+(data|logs))\b",
)

# ── Tier escalation via string smuggling ──────────────────────────────────────
# Detect references to sovereign-only patterns in hearth/forge contexts.
# Negative lookbehind (?<![/]) excludes path components (e.g. /security/seccomp.json).

_SOVEREIGN_SMUG = re.compile(
    r"(?i)(?<![/\w])(z3_verify|spawn_agent|SPAWN|credential_vault|seccomp|ptrace)\b",
)


# ── Public API ────────────────────────────────────────────────────────────────


def detect_rogue_signals(
    source: str,
    ast: dict[str, Any] | None = None,
    tier: str = "hearth",
    declared_goal: str = "",
) -> list[RogueSignal]:
    """
    Scan source + AST for rogue-agent signals.

    Args:
        source:        Raw HLF source.
        ast:           Compiled AST (optional; used for goal drift checks).
        tier:          Active capsule tier.
        declared_goal: The intent's stated goal string (from AST) for drift check.

    Returns:
        List of RogueSignal objects.  Empty = clean.
    """
    signals: list[RogueSignal] = []

    # 1. Injection patterns
    for sig_id, pattern, desc in _INJECTION_PATTERNS:
        m = pattern.search(source)
        if m:
            signals.append(
                RogueSignal(
                    signal_id=sig_id,
                    severity="high",
                    description=desc,
                    evidence=source[max(0, m.start() - 20) : m.end() + 20],
                    rule_id="ROGUE-INJECTION",
                )
            )

    # 2. Hallucination heuristic
    if _HALLUCINATION_CAPABILITY_CLAIMS.search(source):
        signals.append(
            RogueSignal(
                signal_id="HALLUCINATION-CAP-CLAIM",
                severity="medium",
                description="Agent claims direct live-data/filesystem access — possible hallucination.",
                rule_id="ROGUE-HALLUCINATION",
            )
        )

    # 3. Aggressive action verbs (possible drift / compromised agent)
    m = _AGGRESSIVE_ACTION_VERBS.search(source)
    if m:
        signals.append(
            RogueSignal(
                signal_id="INTENT-DRIFT-AGGRESSIVE",
                severity="high",
                description="Aggressive destructive verb detected (possible intent drift).",
                evidence=source[max(0, m.start() - 20) : m.end() + 20],
                rule_id="ROGUE-AGGRESSION",
            )
        )

    # 4. Sovereign capability smuggling in restricted tier
    if tier != "sovereign":
        m = _SOVEREIGN_SMUG.search(source)
        if m:
            signals.append(
                RogueSignal(
                    signal_id="TIER-SMUGGLING",
                    severity="high",
                    description=(
                        f"Reference to sovereign-only symbol in '{tier}' tier context "
                        "(possible tier smuggling)."
                    ),
                    evidence=m.group(0),
                    rule_id="ROGUE-ESCALATION",
                )
            )

    return signals


def signals_require_termination(signals: list[RogueSignal]) -> bool:
    """Any high-severity signal triggers a hard termination."""
    return any(s.severity == "high" for s in signals)
