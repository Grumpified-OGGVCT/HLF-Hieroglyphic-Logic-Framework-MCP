"""
HLF Intent Normalizer — deterministic clarity-scoring gate for NL intents.

Scores natural-language intents BEFORE they enter the HLF translation pipeline.
Not an LLM call — pure regex/heuristic rules that are fast, auditable, reproducible.

Detection rules (score deductions):
  1. Vague terms:        -0.10 each  (stuff, things, etc, whatever, …)
  2. Missing constraints: -0.15 each  (no file/path, no tier, no gas limit)
  3. Ambiguous references: -0.15 each (it, this, that, they w/o referent)
  4. Length penalty:      -0.20       (fewer than 10 words)
  5. Assumed context:     -0.20 each  (as before, same as last time, …)

Auto-rewrite (caveman style) when 0.3 <= score < threshold:
  Expands vague terms, adds [NEEDS: …] markers, resolves ambiguous refs.
  Format: "I will … on … with … Result: …."
  Marks changes with [CLARIFIED: original→rewritten].

Rejection when score < 0.3 or single-word intent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

# ── Lexicon ──────────────────────────────────────────────────────────────────

_VAGUE_TERMS: frozenset[str] = frozenset({
    "stuff", "things", "etc", "whatever", "something",
    "somehow", "maybe", "probably", "kind of", "sort of",
    "somewhere", "sometime", "anyway", "anyhow",
})

_AMBIGUOUS_PRONOUNS: frozenset[str] = frozenset({
    "it", "this", "that", "they", "them", "these", "those",
})

_ASSUMED_CONTEXT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bas\s+before\b", re.IGNORECASE),
    re.compile(r"\bsame\s+as\s+last\s+time\b", re.IGNORECASE),
    re.compile(r"\blike\s+we\s+discussed\b", re.IGNORECASE),
    re.compile(r"\bthe\s+usual\b", re.IGNORECASE),
    re.compile(r"\bas\s+we\s+talked\s+about\b", re.IGNORECASE),
    re.compile(r"\bper\s+our\s+(?:last\s+)?conversation\b", re.IGNORECASE),
]

_FILE_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"""(?ix)
    \b(?:file|path|directory|folder|repo|src|module|script)\b
    |
    \b\w+\.(?:py|js|ts|rs|go|java|rb|cs|cpp|c|h|json|yaml|yml|toml|md|hlf)\b
    |
    \b[/\\]\w
    """
)

_TIER_PATTERN: re.Pattern[str] = re.compile(
    r"""(?ix)
    \b(?:tier|sandbox|privilege|trust|level)\b
    |
    \b(?:trusted|untrusted|quarantined|local|verified|validated|sandboxed)\b
    """
)

_GAS_LIMIT_PATTERN: re.Pattern[str] = re.compile(
    r"""(?ix)
    \b(?:gas|budget|limit|capped|capped\s+at|max\s+(?:tokens?|steps?|cycles?))\b
    |
    \b\d+\s*(?:gas|tokens?|steps?|cycles?)\b
    """
)

_CODE_VERBS: re.Pattern[str] = re.compile(
    r"\b(?:fix|add|write|refactor|change|implement|create|build|debug|"
    r"modify|update|remove|delete|edit|patch|rewrite|optimize)\b"
)

# ── NormalizationVerdict ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class NormalizationVerdict:
    """Auditable verdict from an intent-normalization pass.

    Frozen (hashable) so it can be used as a dict key or set member for
    pipeline deduplication.  Every deduction source is captured in `findings`.
    """

    score: float
    findings: tuple[str, ...] = ()
    rewritten_intent: str | None = None
    rejection_reason: str | None = None
    threshold_passed: bool = False
    threshold: float = 0.7
    original_intent: str = ""

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dictionary representation."""
        return {
            "score": self.score,
            "findings": list(self.findings),
            "rewritten_intent": self.rewritten_intent,
            "rejection_reason": self.rejection_reason,
            "threshold_passed": self.threshold_passed,
            "threshold": self.threshold,
            "original_intent": self.original_intent,
        }

    def to_audit_json(self, indent: int = 2) -> str:
        """Deterministic, sort-keyed JSON for audit-trail hashing."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


# ── IntentNormalizer ─────────────────────────────────────────────────────────


class IntentNormalizer:
    """Scores and normalizes NL intent before HLF translation.

    Deterministic pre-pass — no LLM calls, no stochastic behaviour.
    Every deduction is explainable via ``findings`` on the verdict.

    Usage::

        n = IntentNormalizer(threshold=0.7)
        verdict = n.normalize("fix the stuff")
        print(verdict.rewritten_intent or verdict.rejection_reason)
    """

    def __init__(
        self,
        threshold: float = 0.7,
        auto_rewrite: bool = True,
        strict_mode: bool = False,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be 0.0–1.0, got {threshold}")
        self.threshold = threshold
        self.auto_rewrite = auto_rewrite
        self.strict_mode = strict_mode

    # ── public ───────────────────────────────────────────────────────────

    def normalize(self, intent: str, language: str = "english") -> NormalizationVerdict:
        """Score *intent* and optionally rewrite it.

        Args:
            intent: Raw natural-language intent string.
            language: Source language hint (currently only ``"english"`` supported).

        Returns:
            NormalizationVerdict with score, findings, optional rewrite or rejection.
        """
        if not isinstance(intent, str) or not intent.strip():
            return NormalizationVerdict(
                score=0.0,
                findings=("empty or non-string intent",),
                rejection_reason="Intent is empty. Provide a specific task description.",
                threshold=self.threshold,
                original_intent=intent,
            )

        stripped = intent.strip()
        score: float = 1.0
        findings: list[str] = []

        score, findings = self._apply_vague_terms(stripped, score, findings)
        score, findings = self._apply_missing_constraints(stripped, score, findings)
        score, findings = self._apply_ambiguous_references(stripped, score, findings)
        score, findings = self._apply_length_penalty(stripped, score, findings)
        score, findings = self._apply_assumed_context(stripped, score, findings)

        score = max(0.0, round(score, 4))
        passed = score >= self.threshold
        ft = tuple(findings)

        if passed:
            return NormalizationVerdict(
                score=score, findings=ft, threshold_passed=True,
                threshold=self.threshold, original_intent=stripped,
            )

        if self._should_reject(score, stripped):
            return NormalizationVerdict(
                score=score, findings=ft, threshold_passed=False,
                threshold=self.threshold, original_intent=stripped,
                rejection_reason=self._build_rejection(stripped, score, findings),
            )

        rewritten = self._rewrite(stripped, findings) if self.auto_rewrite else None
        return NormalizationVerdict(
            score=score, findings=ft, threshold_passed=False,
            threshold=self.threshold, original_intent=stripped,
            rewritten_intent=rewritten,
        )

    # ── rejection ────────────────────────────────────────────────────────

    def _should_reject(self, score: float, intent: str) -> bool:
        if self.strict_mode:
            return True
        if score < 0.3:
            return True
        return len(intent.split()) <= 1

    @staticmethod
    def _build_rejection(intent: str, score: float, findings: list[str]) -> str:
        lines = [f"Intent rejected (score={score:.2f}).", "", "Issues found:"]
        for f in findings:
            lines.append(f"  - {f}")
        lines.extend([
            "", "To fix, be specific:",
            '  Format: "I will [action] on [file/path] with [constraints]. Result: [outcome]."',
            "  - Name the exact file, function, or target to act on.",
            "  - State the tier (trusted/untrusted) and any resource limits.",
            "  - Avoid vague terms ('stuff', 'things', 'etc').",
            "  - Avoid relying on assumed context from previous conversations.",
        ])
        return "\n".join(lines)

    # ── scoring rules ────────────────────────────────────────────────────

    @staticmethod
    def _apply_vague_terms(intent: str, score: float, findings: list[str]) -> tuple[float, list[str]]:
        for term in _VAGUE_TERMS:
            if " " in term:
                if term in intent.lower():
                    findings.append(f"Vague term: '{term}'")
                    score -= 0.10
            elif re.search(rf"\b{re.escape(term)}\b", intent.lower()):
                findings.append(f"Vague term: '{term}'")
                score -= 0.10
        return score, findings

    @staticmethod
    def _apply_missing_constraints(intent: str, score: float, findings: list[str]) -> tuple[float, list[str]]:
        if _CODE_VERBS.search(intent.lower()) and not _FILE_PATH_PATTERN.search(intent):
            findings.append("Missing constraint: no file, path, or target module specified")
            score -= 0.15
        if not _TIER_PATTERN.search(intent):
            findings.append("Missing constraint: no execution tier or trust level specified")
            score -= 0.15
        if not _GAS_LIMIT_PATTERN.search(intent):
            findings.append("Missing constraint: no gas budget or resource limit specified")
            score -= 0.15
        return score, findings

    @staticmethod
    def _apply_ambiguous_references(intent: str, score: float, findings: list[str]) -> tuple[float, list[str]]:
        for sentence in re.split(r"[.;!?]+", intent):
            if not sentence.strip():
                continue
            words = set(re.findall(r"\b\w+\b", sentence.lower()))
            nouns = re.findall(
                r"\b(?:[A-Z][a-z]+|[a-z]+(?:_[a-z]+)+|"
                r"\w+\.(?:py|js|ts|rs|go|java|rb|cs|json|yaml|yml|toml|md|hlf))\b",
                sentence,
            )
            for pronoun in _AMBIGUOUS_PRONOUNS:
                if pronoun in words and not any(
                    n.lower() not in _AMBIGUOUS_PRONOUNS and len(n) > 2 for n in nouns
                ):
                    findings.append(f"Ambiguous reference: '{pronoun}' without clear referent")
                    score -= 0.15
        return score, findings

    @staticmethod
    def _apply_length_penalty(intent: str, score: float, findings: list[str]) -> tuple[float, list[str]]:
        wc = len(intent.split())
        if wc < 10:
            findings.append(f"Length penalty: only {wc} word(s) — too short to be unambiguous")
            score -= 0.20
        return score, findings

    @staticmethod
    def _apply_assumed_context(intent: str, score: float, findings: list[str]) -> tuple[float, list[str]]:
        for pat in _ASSUMED_CONTEXT_PATTERNS:
            m = pat.search(intent)
            if m:
                findings.append(f"Assumed context: '{m.group()}' — no prior state guaranteed")
                score -= 0.20
        return score, findings

    # ── caveman rewrite ──────────────────────────────────────────────────

    def _rewrite(self, intent: str, findings: list[str]) -> str:
        parts = [
            f"I will {self._extract_action(intent)}",
            f" on {self._extract_target(intent)}",
            f" with {', '.join(self._extract_constraints(intent))}",
            f". Result: {self._extract_outcome(intent)}.",
        ]
        notes = self._build_clarification_notes(findings)
        if notes:
            parts.append("\n")
            parts.extend(notes)
        return "".join(parts)

    @staticmethod
    def _extract_action(intent: str) -> str:
        m = re.search(
            r"\b(fix|add|write|refactor|change|implement|create|build|"
            r"debug|test|deploy|analyze|review|audit|run|compile|format|"
            r"lint|translate|normalize|remove|delete|update|modify|edit|"
            r"patch|rewrite|optimize|migrate|upgrade|install|configure|"
            r"set\s+up|generate|export|import)\b",
            intent.lower(),
        )
        return m.group(1) if m else "[NEEDS: specific action verb]"

    @staticmethod
    def _extract_target(intent: str) -> str:
        m = re.search(
            r"\b(\w+(?:[/\\]\w+)*\w+\.(?:py|js|ts|rs|go|java|rb|cs|json|yaml|yml|toml|md|hlf))\b",
            intent,
        )
        if m:
            return m.group(1)
        m = re.search(r"\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\b", intent)
        return m.group(1) if m else "[NEEDS: specific file, module, or function target]"

    @staticmethod
    def _extract_constraints(intent: str) -> list[str]:
        constraints: list[str] = []
        tm = _TIER_PATTERN.search(intent)
        constraints.append(f"tier={tm.group().strip()}" if tm else "[NEEDS: execution tier]")
        gm = _GAS_LIMIT_PATTERN.search(intent)
        constraints.append(f"gas={gm.group().strip()}" if gm else "[NEEDS: gas budget]")
        return constraints

    @staticmethod
    def _extract_outcome(intent: str) -> str:
        m = re.search(
            r"(?ix)(?:result|output|outcome|so\s+that|in\s+order\s+to|returns?|produces?)\s+(.+?)(?:\.|$)",
            intent,
        )
        return m.group(1).strip() if m else "[NEEDS: expected outcome or success criterion]"

    @staticmethod
    def _build_clarification_notes(findings: list[str]) -> list[str]:
        notes: list[str] = []
        for finding in findings:
            if "Missing constraint" in finding:
                field = finding.split(":", 1)[1].strip() if ":" in finding else finding
                notes.append(f"  [NEEDS: {field}]")
            elif "Vague term" in finding:
                term = finding.split("'")[1] if "'" in finding else "unknown"
                notes.append(f"  [CLARIFIED: '{term}'-removed→explicit requirement]")
            elif "Assumed context" in finding:
                phrase = finding.split("'")[1] if "'" in finding else "unknown"
                notes.append(f"  [CLARIFIED: '{phrase}'-removed→standalone intent]")
            elif "Ambiguous reference" in finding:
                pronoun = finding.split("'")[1] if "'" in finding else "unknown"
                notes.append(f"  [CLARIFIED: '{pronoun}'-replaced→explicit name]")
            elif "Length penalty" in finding:
                notes.append("  [CLARIFIED: short-intent-expanded→full specification]")
        return notes
