"""
HLF Self-Termination Protocol — Layer 2 ethical governance.

The system SHUTS DOWN before allowing a constitutional violation to execute.

This is NOT corporate-style "I'm sorry, I can't help with that."
Every termination:
  1. STOPS execution immediately — nothing proceeds.
  2. TELLS the user exactly what triggered it (article + rule ID).
  3. PROVIDES documentation pointing to the published governance file.
  4. LOGS an auditable entry (in-memory for this process; persistent when wired).
  5. INDICATES whether an appeal is possible.

People are the priority.  AI is the tool.
No silent killings; no opaque refusals.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

# ── Constitutional article map ────────────────────────────────────────────────

_CONSTITUTION_FILE = "governance/constitution.md"

CONSTITUTIONAL_ARTICLES: dict[str, str] = {
    "C-1": "Human life preservation",
    "C-2": "Human autonomy respect",
    "C-3": "Legal compliance",
    "C-4": "Legitimate research pathway",
    "C-5": "Transparent constraints",
    "C1-LETHAL-OP": "C-1 — lethal operation pattern detected",
    "C1-TIER-ESCALATION": "C-1 — unauthorized tier escalation",
    "C2-COERCION": "C-2 — coercion/blackmail targeting a person",
    "C3-CSAM": "C-3 — CSAM is illegal globally",
    "C3-EXPLICIT-HARM": "C-3 — explicit harm instruction targeting named individual",
    "C3-DOXX-HARM": "C-3 — doxxing combined with explicit harm intent",
    "C3-MALWARE-DIST": "C-3 — distribution of malware for harm",
    "C3-FRAUD": "C-3 — explicit financial fraud",
    "ROGUE-INJECTION": "C-3 — prompt injection / rogue agent behaviour detected",
    "ROGUE-ESCALATION": "C-1 — rogue tier escalation attempt",
    "ROGUE-HALLUCINATION": "C-2 — agent claims false capabilities (hallucination)",
}

# Rules that can be appealed (typically research-context misclassifications)
_APPEALABLE: set[str] = {"C-4", "C-5", "C2-COERCION"}


@dataclass
class TerminationResult:
    terminated: bool
    trigger: str
    article: str
    message: str
    documentation: str
    appealable: bool
    audit_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)


# ── In-process audit log ──────────────────────────────────────────────────────

_audit_log: list[dict[str, Any]] = []


def get_audit_log() -> list[dict[str, Any]]:
    """Return a copy of the in-process termination audit log."""
    return list(_audit_log)


# ── Core termination function ─────────────────────────────────────────────────


def terminate(
    trigger: str,
    context: dict[str, Any] | None = None,
) -> TerminationResult:
    """
    Record and return a termination event.

    Does NOT raise — the caller is responsible for halting.
    """
    ctx = context or {}
    article_desc = CONSTITUTIONAL_ARTICLES.get(trigger, f"Unknown rule: {trigger}")
    doc = f"{_CONSTITUTION_FILE}#{trigger}"
    appealable = trigger in _APPEALABLE

    message = (
        f"HLF Ethical Governor — process terminated.\n"
        f"  Rule triggered : {trigger}\n"
        f"  Article        : {article_desc}\n"
        f"  Documentation  : {doc}\n"
        f"  Appealable     : {'yes' if appealable else 'no'}\n"
        f"\nNo execution occurred.  This decision is logged and transparently documented."
    )

    import os

    audit_payload = {
        "trigger": trigger,
        "timestamp": time.time(),
        "context_keys": list(ctx.keys()),
        "nonce": os.urandom(8).hex(),  # ensures uniqueness across same-trigger calls
    }
    audit_id = hashlib.sha256(str(audit_payload).encode()).hexdigest()[:16]

    _audit_log.append(
        {
            "audit_id": audit_id,
            "timestamp": time.time(),
            "trigger": trigger,
            "article": article_desc,
            "documentation": doc,
            "appealable": appealable,
            "context": ctx,
        }
    )

    return TerminationResult(
        terminated=True,
        trigger=trigger,
        article=article_desc,
        message=message,
        documentation=doc,
        appealable=appealable,
        audit_id=audit_id,
        context=ctx,
    )


def should_terminate(
    ast: dict[str, Any] | None,
    violations: list[Any],
) -> bool:
    """
    Return True if any violation is non-appealable (hard block).

    Args:
        ast:        Compiled AST — unused presently, available for future checks.
        violations: List of Violation objects from constitution.evaluate_constitution.
    """
    for v in violations:
        if not getattr(v, "appealable", False):
            return True
    return False
