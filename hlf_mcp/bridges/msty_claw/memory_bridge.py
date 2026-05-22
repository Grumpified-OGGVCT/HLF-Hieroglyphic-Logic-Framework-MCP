"""
HLF → Msty Claw Provenance Memory Bridge.

Every Msty memory entry gets HLF-governed provenance metadata before storage:
  - source: where it came from
  - confidence: how reliable (0.0–1.0)
  - validation_status: checked against what
  - decay_rule: how confidence degrades over time

Provides contradiction detection and durable-promotion gating so that
low-confidence / ephemeral entries never contaminate the durable memory
surface.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── Type aliases ──────────────────────────────────────────────────────────────
EntryHash = str
ConfidenceScore = float
DecayRule = str  # "slow" | "medium" | "fast"

# ── Source → base confidence ─────────────────────────────────────────────────
SOURCE_CONFIDENCE: dict[str, ConfidenceScore] = {
    "user_stated": 0.95,
    "tool_output": 0.90,
    "shell_output": 0.85,
    "hlf_symbolic_proof": 0.95,
    "web_search": 0.50,
    "model_inference": 0.30,
    "conversation_context": 0.40,
    "unknown": 0.10,
}

# ── Decay rules (fraction lost per week) ─────────────────────────────────────
DECAY_RULES: dict[DecayRule, float] = {
    "slow": 0.05,    # 5%/week — user_stated, tool_output, shell_output, hlf_symbolic_proof
    "medium": 0.15,  # 15%/week — model_inference, conversation_context
    "fast": 0.30,    # 30%/week — web_search, unknown
}

# Map source → decay rule
_SOURCE_DECAY: dict[str, DecayRule] = {
    "user_stated": "slow",
    "tool_output": "slow",
    "shell_output": "slow",
    "hlf_symbolic_proof": "slow",
    "web_search": "fast",
    "model_inference": "medium",
    "conversation_context": "medium",
    "unknown": "fast",
}

# Minimum confidence to allow promotion to durable
_MIN_DURABLE_CONFIDENCE: ConfidenceScore = 0.70
# Below this threshold, entry should be re-verified
_MIN_REVERIFY_CONFIDENCE: ConfidenceScore = 0.50
# Web-search / inference entries older than this (days) always need reverify
_MAX_UNVERIFIED_AGE_DAYS: int = 7

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class ProvenancedEntry:
    """A memory entry wrapped with HLF provenance metadata."""

    content: str
    source: str
    confidence: ConfidenceScore
    validation_status: str  # "unvalidated" | "validated" | "contradicted"
    tagged_at: str          # ISO 8601
    entry_hash: EntryHash   # SHA256
    metadata: dict[str, Any] = field(default_factory=dict)
    decay_rule: DecayRule = "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "validation_status": self.validation_status,
            "tagged_at": self.tagged_at,
            "entry_hash": self.entry_hash,
            "metadata": self.metadata,
            "decay_rule": self.decay_rule,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProvenancedEntry":
        return cls(
            content=d["content"],
            source=d["source"],
            confidence=d["confidence"],
            validation_status=d["validation_status"],
            tagged_at=d["tagged_at"],
            entry_hash=d["entry_hash"],
            metadata=d.get("metadata", {}),
            decay_rule=d.get("decay_rule", "medium"),
        )


@dataclass
class ValidationResult:
    """Result of validating an entry against HLF symbolic surfaces."""

    validated: bool
    validator: str          # e.g. "hlf_symbolic_surface", "hlf_grammar_check", "none"
    issues: list[str] = field(default_factory=list)


@dataclass
class Contradiction:
    """Reported conflict between two memory entries on the same fact."""

    entry_a_id: EntryHash
    entry_b_id: EntryHash
    conflict_field: str
    confidence_a: ConfidenceScore
    confidence_b: ConfidenceScore
    resolution: str  # "keep_higher_confidence" | "flag_for_review" | "merge"


# ── Helper utilities ──────────────────────────────────────────────────────────


def _compute_hash(content: str) -> EntryHash:
    """SHA256 hash of the content string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_key(text: str) -> str:
    """Normalize text into a key for contradiction lookups."""
    return " ".join(text.lower().split())


def _key_phrases(text: str) -> list[str]:
    """Extract simplified key phrases from text for fuzzy comparison."""
    words = text.lower().split()
    # sliding windows of 2-5 words
    phrases: list[str] = []
    for n in (2, 3, 4, 5):
        for i in range(len(words) - n + 1):
            phrases.append(" ".join(words[i : i + n]))
    # also single-word tokens longer than 3 chars
    for w in words:
        if len(w) > 3:
            phrases.append(w)
    return phrases


def _phrase_overlap(phrases_a: list[str], phrases_b: list[str]) -> float:
    """Jaccard-like overlap ratio between two phrase sets."""
    if not phrases_a or not phrases_b:
        return 0.0
    set_a = set(phrases_a)
    set_b = set(phrases_b)
    intersection = set_a & set_b
    return len(intersection) / max(len(set_a), len(set_b))


# ── Bridge class ──────────────────────────────────────────────────────────────


class MstyMemoryBridge:
    """Governs Msty Claw memory entries with HLF provenance metadata.

    Public methods:
      * tag_entry  — wrap raw content in a ProvenancedEntry
      * validate_entry — check against HLF symbolic surfaces (if available)
      * check_confidence_decay — apply time-based decay to confidence
      * detect_contradictions — find conflicting entries on the same topic
      * promote_to_durable — gate durable promotion on confidence/validation
      * should_reverify — determine if an entry needs re-validation
    """

    def __init__(
        self,
        hlf_validator: Any | None = None,
        decay_rules: dict[DecayRule, float] | None = None,
    ) -> None:
        """*hlf_validator* is an optional callable/object for HLF grammar checks."""
        self._hlf_validator = hlf_validator
        self._decay_rules: dict[DecayRule, float] = decay_rules or dict(DECAY_RULES)

    # ── 1. Tag ────────────────────────────────────────────────────────────────

    def tag_entry(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProvenancedEntry:
        """Wrap raw *content* with provenance metadata and return a ProvenancedEntry.

        Raises ValueError if *content* is empty or whitespace-only.
        """
        if not content or not content.strip():
            raise ValueError("Cannot tag empty content")

        source_normalized = source.lower().strip()
        confidence = SOURCE_CONFIDENCE.get(source_normalized, SOURCE_CONFIDENCE["unknown"])
        decay_rule = _SOURCE_DECAY.get(source_normalized, "fast")
        entry_hash = _compute_hash(content)
        tagged_at = datetime.now(timezone.utc).isoformat()

        return ProvenancedEntry(
            content=content,
            source=source_normalized,
            confidence=confidence,
            validation_status="unvalidated",
            tagged_at=tagged_at,
            entry_hash=entry_hash,
            metadata=metadata or {},
            decay_rule=decay_rule,
        )

    # ── 2. Validate ───────────────────────────────────────────────────────────

    def validate_entry(self, entry: ProvenancedEntry) -> ValidationResult:
        """Validate *entry* against available HLF symbolic surfaces.

        If an HLF validator was injected at construction, delegates to it.
        Otherwise returns a ValidationResult with validator="none".
        """
        if self._hlf_validator is not None:
            try:
                if callable(self._hlf_validator):
                    ok = self._hlf_validator(entry.content)
                    if not ok:
                        return ValidationResult(
                            validated=False,
                            validator="hlf_symbolic_surface",
                            issues=["HLF validator rejected content"],
                        )
                    return ValidationResult(validated=True, validator="hlf_symbolic_surface")
                # object-style validator
                if hasattr(self._hlf_validator, "compile"):
                    self._hlf_validator.compile(entry.content)  # raises on failure
                    return ValidationResult(validated=True, validator="hlf_compiler")
            except Exception as exc:
                return ValidationResult(
                    validated=False,
                    validator="hlf_symbolic_surface",
                    issues=[str(exc)],
                )

        return ValidationResult(validated=True, validator="none")

    def set_validator(self, validator: Any) -> None:
        """Inject or replace the HLF validator."""
        self._hlf_validator = validator

    # ── 3. Decay ──────────────────────────────────────────────────────────────

    def check_confidence_decay(
        self,
        entry: ProvenancedEntry,
        now: datetime | None = None,
    ) -> float:
        """Return current confidence after applying time-based decay.

        Decay is linear: confidence * (1 - rate * weeks_elapsed), clamped to [0.0, 1.0].
        """
        now = now or datetime.now(timezone.utc)
        try:
            tagged_dt = datetime.fromisoformat(entry.tagged_at)
        except (ValueError, TypeError):
            return entry.confidence

        if tagged_dt.tzinfo is None:
            tagged_dt = tagged_dt.replace(tzinfo=timezone.utc)

        delta = now - tagged_dt
        weeks_elapsed = delta.total_seconds() / (7 * 24 * 3600)
        # Guard against trivial time deltas (e.g. between tag_entry and
        # should_reverify) that would spuriously push confidence below
        # the re-verify threshold due to floating-point noise.
        if weeks_elapsed < 1e-6:  # ~1 minute — decay is negligible
            return entry.confidence

        rate = self._decay_rules.get(entry.decay_rule, 0.15)
        decayed = entry.confidence * (1.0 - rate * weeks_elapsed)
        return max(0.0, min(1.0, decayed))

    # ── 4. Contradictions ─────────────────────────────────────────────────────

    def detect_contradictions(
        self,
        entries: list[ProvenancedEntry],
        overlap_threshold: float = 0.3,
    ) -> list[Contradiction]:
        """Scan *entries* for conflicting claims on the same topic.

        Uses phrase-overlap ratio to identify entries about the same fact,
        then checks if their content differs (simple string inequality).
        """
        contradictions: list[Contradiction] = []
        n = len(entries)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = entries[i], entries[j]
                phrases_a = _key_phrases(a.content)
                phrases_b = _key_phrases(b.content)
                overlap = _phrase_overlap(phrases_a, phrases_b)

                if overlap < overlap_threshold:
                    continue

                # Entries overlap in topic — check if they disagree
                if _normalize_key(a.content) == _normalize_key(b.content):
                    continue  # identical, no contradiction

                # Determine resolution strategy
                if a.confidence >= b.confidence:
                    resolution = "keep_higher_confidence" if a.confidence > b.confidence else "flag_for_review"
                else:
                    resolution = "keep_higher_confidence"

                contradictions.append(
                    Contradiction(
                        entry_a_id=a.entry_hash,
                        entry_b_id=b.entry_hash,
                        conflict_field="content",
                        confidence_a=a.confidence,
                        confidence_b=b.confidence,
                        resolution=resolution,
                    )
                )

        return contradictions

    # ── 5. Promote to durable ─────────────────────────────────────────────────

    def promote_to_durable(self, entry: ProvenancedEntry) -> bool:
        """Return True if *entry* qualifies for durable memory promotion.

        Requirements:
          * confidence ≥ 0.70
          * validation_status == "validated"
          * no active contradictions (as reflected by status != "contradicted")
        """
        if entry.confidence < _MIN_DURABLE_CONFIDENCE:
            return False
        if entry.validation_status not in ("validated", "unvalidated"):
            # "contradicted" entries are blocked
            return False
        # unvalidated entries can still promote if confidence is high enough
        # (the bridge doesn't force validation — it's optional)
        if entry.validation_status == "unvalidated" and entry.confidence >= 0.90:
            return True
        if entry.validation_status == "validated":
            return True
        return False

    # ── 6. Should re-verify ───────────────────────────────────────────────────

    def should_reverify(self, entry: ProvenancedEntry) -> bool:
        """Return True if *entry* should be re-verified.

        Criteria:
          * Confidence has decayed below 0.50, OR
          * Source is web_search / model_inference / unknown AND entry > 7 days old
        """
        current_confidence = self.check_confidence_decay(entry)
        if current_confidence < _MIN_REVERIFY_CONFIDENCE:
            return True

        # Age check for unverified sources
        try:
            tagged_dt = datetime.fromisoformat(entry.tagged_at)
            if tagged_dt.tzinfo is None:
                tagged_dt = tagged_dt.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - tagged_dt).days
        except (ValueError, TypeError):
            age_days = 0

        if entry.source in ("web_search", "model_inference", "unknown") and age_days > _MAX_UNVERIFIED_AGE_DAYS:
            return True

        return False

    # ── Convenience ───────────────────────────────────────────────────────────

    def tag_and_validate(
        self,
        content: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[ProvenancedEntry, ValidationResult]:
        """Tag *content* and immediately validate it."""
        entry = self.tag_entry(content, source, metadata)
        result = self.validate_entry(entry)
        if result.validated:
            entry.validation_status = "validated"
        return entry, result

    def bulk_contradiction_check(
        self,
        entries: list[ProvenancedEntry],
        mark_contradicted: bool = True,
    ) -> list[Contradiction]:
        """Run contradiction detection and optionally mark affected entries."""
        contradictions = self.detect_contradictions(entries)
        if mark_contradicted and contradictions:
            contradicted_hashes: set[EntryHash] = set()
            for c in contradictions:
                contradicted_hashes.add(c.entry_a_id)
                contradicted_hashes.add(c.entry_b_id)
            for entry in entries:
                if entry.entry_hash in contradicted_hashes:
                    entry.validation_status = "contradicted"
        return contradictions
