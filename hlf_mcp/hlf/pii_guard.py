"""
HLF Runtime PII Guard Module

Provides runtime scanning and redaction of Personally Identifiable Information (PII)
before data is stored in RAG memory. This module enforces the privacy-first ethos
of the HLF architecture by preventing PII leakage into persistent storage.

Philosophy: People-first, privacy-first, AI as tool, transparent governance.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional
from collections.abc import Sequence


class PIICategory(Enum):
    """Categories of PII that can be detected."""
    EMAIL = auto()
    PHONE = auto()
    SSN = auto()
    CREDIT_CARD = auto()
    IP_ADDRESS = auto()
    DATE_OF_BIRTH = auto()
    ADDRESS = auto()
    NAME = auto()
    URL = auto()
    CUSTOM = auto()


@dataclass
class PIIDetection:
    """Represents a detected PII instance."""
    category: PIICategory
    value: str
    start_index: int
    end_index: int
    confidence: float
    redacted_value: str = ""

    def __post_init__(self) -> None:
        if not self.redacted_value:
            self.redacted_value = self._generate_redaction()

    def _generate_redaction(self) -> str:
        """Generate redacted version of the PII value."""
        if len(self.value) <= 4:
            return "*" * len(self.value)
        return self.value[:2] + "*" * (len(self.value) - 4) + self.value[-2:]


@dataclass
class PIIScanResult:
    """Result of a PII scan operation."""
    has_pii: bool
    detections: list[PIIDetection] = field(default_factory=list)
    redacted_text: str = ""
    scan_timestamp: float = field(default_factory=time.time)
    categories_found: set[PIICategory] = field(default_factory=set)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "has_pii": self.has_pii,
            "detection_count": len(self.detections),
            "categories": [cat.name for cat in self.categories_found],
            "redacted": self.redacted_text,
            "safe_to_store": not self.has_pii,
        }


def _default_policy() -> dict[str, Any]:
    return {
        "strict_mode": False,
        "min_confidence": 0.7,
        "enabled_categories": [category.name for category in PIICategory if category is not PIICategory.CUSTOM],
        "context_indicators": {
            "EMAIL": ["email", "contact", "reach"],
            "PHONE": ["phone", "call", "tel", "mobile"],
            "SSN": ["ssn", "social", "security"],
            "CREDIT_CARD": ["card", "payment", "cc", "visa"],
        },
        "title_indicators": ["Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Captain", "President"],
        "common_non_name_words": ["The", "A", "An", "In", "On", "At", "For", "With"],
    }


def _governance_policy_path() -> Path:
    return Path(__file__).resolve().parents[2] / "governance" / "pii_policy.json"


def load_pii_policy(policy_path: str | Path | None = None) -> dict[str, Any]:
    policy = _default_policy()
    resolved_path = Path(policy_path) if policy_path is not None else _governance_policy_path()
    if not resolved_path.exists():
        return policy
    try:
        loaded = json.loads(resolved_path.read_text(encoding="utf-8"))
    except Exception:
        return policy
    if not isinstance(loaded, dict):
        return policy
    policy.update(loaded)
    return policy


class PIIGuard:
    """
    Runtime PII Guard for HLF Memory Store operations.

    Scans text content for PII patterns and provides redaction capabilities
    before data is persisted to RAG memory.

    Usage::

        guard = PIIGuard()
        result = guard.scan(text_content)
        if result.has_pii:
            logger.warning(f"PII detected: {result.categories_found}")
            safe_content = result.redacted_text
        else:
            safe_content = text_content
    """

    # Precompiled regex patterns for PII detection
    PATTERNS: dict[PIICategory, re.Pattern[str]] = {
        PIICategory.EMAIL: re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        ),
        PIICategory.PHONE: re.compile(
            r'\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?)[-.\s]?\d{3}[-.\s]?\d{4}\b'
        ),
        PIICategory.SSN: re.compile(
            r'\b\d{3}[-]?\d{2}[-]?\d{4}\b'
        ),
        PIICategory.CREDIT_CARD: re.compile(
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?'
            r'|5[1-5][0-9]{14}'
            r'|3[47][0-9]{13}'
            r'|6(?:011|5[0-9]{2})[0-9]{12})\b'
        ),
        PIICategory.IP_ADDRESS: re.compile(
            r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        ),
        PIICategory.DATE_OF_BIRTH: re.compile(
            r'\b(?:0?[1-9]|1[0-2])[/\-](?:0?[1-9]|[12][0-9]|3[01])[/\-](?:19|20)\d{2}\b'
        ),
        PIICategory.URL: re.compile(
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}'
            r'\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_+.~#?&/=]*)'
        ),
    }

    # Additional patterns requiring context-aware detection
    NAME_PATTERN: re.Pattern[str] = re.compile(
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'
    )
    ADDRESS_PATTERN: re.Pattern[str] = re.compile(
        r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln)\b'
    )

    def __init__(
        self,
        strict_mode: bool | None = None,
        custom_patterns: Optional[dict[PIICategory, re.Pattern[str]]] = None,
        min_confidence: float | None = None,
        policy: dict[str, Any] | None = None,
        policy_path: str | Path | None = None,
    ) -> None:
        """
        Initialize PII Guard.

        Args:
            strict_mode: If True, flag potential PII with lower confidence threshold.
            custom_patterns: Additional regex patterns for custom PII types.
            min_confidence: Minimum confidence score to flag as PII (0.0–1.0).
        """
        effective_policy = load_pii_policy(policy_path=policy_path)
        if policy:
            effective_policy.update(policy)

        self.policy = effective_policy
        self.strict_mode = effective_policy["strict_mode"] if strict_mode is None else strict_mode
        self.custom_patterns = custom_patterns or {}
        self.min_confidence = float(effective_policy["min_confidence"] if min_confidence is None else min_confidence)

        enabled_names = {
            str(name).upper()
            for name in effective_policy.get("enabled_categories", [])
        }
        enabled_categories = {category for category in PIICategory if category.name in enabled_names}
        self._patterns: dict[PIICategory, re.Pattern[str]] = {
            category: pattern
            for category, pattern in {**self.PATTERNS, **self.custom_patterns}.items()
            if category in enabled_categories or category in self.custom_patterns
        }
        self._context_indicators: dict[PIICategory, list[str]] = {
            PIICategory[key]: list(values)
            for key, values in effective_policy.get("context_indicators", {}).items()
            if key in PIICategory.__members__ and isinstance(values, list)
        }
        self._title_indicators = [str(value) for value in effective_policy.get("title_indicators", [])]
        self._common_non_name_words = {str(value) for value in effective_policy.get("common_non_name_words", [])}

    def scan(self, text: str) -> PIIScanResult:
        """
        Scan text for PII patterns.

        Args:
            text: The text content to scan.

        Returns:
            PIIScanResult with detection details and redacted text.
        """
        scan_timestamp = time.time()
        detections: list[PIIDetection] = []
        categories_found: set[PIICategory] = set()

        # Scan each pattern category
        for category, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                confidence = self._calculate_confidence(category, match.group(), text)
                if confidence >= self.min_confidence or self.strict_mode:
                    detection = PIIDetection(
                        category=category,
                        value=match.group(),
                        start_index=match.start(),
                        end_index=match.end(),
                        confidence=confidence,
                    )
                    detections.append(detection)
                    categories_found.add(category)

        # Apply name detection with context awareness
        for match in self.NAME_PATTERN.finditer(text):
            confidence = self._calculate_name_confidence(match.group(), text, match.start())
            if confidence >= self.min_confidence:
                detections.append(
                    PIIDetection(
                        category=PIICategory.NAME,
                        value=match.group(),
                        start_index=match.start(),
                        end_index=match.end(),
                        confidence=confidence,
                    )
                )
                categories_found.add(PIICategory.NAME)

        # Apply address detection
        for match in self.ADDRESS_PATTERN.finditer(text):
            confidence = self._calculate_confidence(PIICategory.ADDRESS, match.group(), text)
            if confidence >= self.min_confidence:
                detections.append(
                    PIIDetection(
                        category=PIICategory.ADDRESS,
                        value=match.group(),
                        start_index=match.start(),
                        end_index=match.end(),
                        confidence=confidence,
                    )
                )
                categories_found.add(PIICategory.ADDRESS)

        # Generate redacted text
        redacted_text = self._apply_redactions(text, detections)

        return PIIScanResult(
            has_pii=len(detections) > 0,
            detections=detections,
            redacted_text=redacted_text,
            scan_timestamp=scan_timestamp,
            categories_found=categories_found,
        )

    def _calculate_confidence(
        self,
        category: PIICategory,
        value: str,
        full_text: str,
    ) -> float:
        """
        Calculate confidence score for PII detection.

        Args:
            category: The PII category.
            value: The matched value.
            full_text: The full text context.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if category == PIICategory.SSN:
            base_confidence = 0.95
        elif category == PIICategory.CREDIT_CARD:
            base_confidence = 0.92
        elif category == PIICategory.EMAIL:
            base_confidence = 0.90
        elif category == PIICategory.PHONE:
            base_confidence = 0.85
        elif category in (PIICategory.NAME, PIICategory.ADDRESS):
            base_confidence = 0.70
        else:
            base_confidence = 0.80

        # Boost confidence when contextual keywords appear nearby
        if category in self._context_indicators:
            idx = full_text.find(value)
            context_text = full_text[max(0, idx - 50): idx + 50].lower()
            for indicator in self._context_indicators[category]:
                if indicator in context_text:
                    base_confidence = min(1.0, base_confidence + 0.05)
                    break

        return base_confidence

    def _calculate_name_confidence(
        self,
        name: str,
        full_text: str,
        position: int,
    ) -> float:
        """
        Calculate confidence for name detection with context awareness.

        Args:
            name: The detected name candidate.
            full_text: Full text context.
            position: Start position in text.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        base_confidence = 0.65

        preceding_text = full_text[max(0, position - 20): position]
        for title in self._title_indicators:
            if title in preceding_text:
                base_confidence = 0.85
                break

        if position == 0 or full_text[position - 1] in "\n\r":
            base_confidence = min(1.0, base_confidence + 0.10)

        # Reduce false positives for common non-name word pairs
        if name.split()[0] in self._common_non_name_words:
            base_confidence = 0.40

        return base_confidence

    def _apply_redactions(
        self,
        text: str,
        detections: Sequence[PIIDetection],
    ) -> str:
        """
        Apply redactions to text based on detected PII.

        Works in reverse position order so that index offsets remain valid
        after each substitution.

        Args:
            text: Original text.
            detections: List of PII detections.

        Returns:
            Redacted text.
        """
        sorted_detections = sorted(detections, key=lambda d: d.start_index, reverse=True)
        result = text
        for detection in sorted_detections:
            result = (
                result[: detection.start_index]
                + detection.redacted_value
                + result[detection.end_index :]
            )
        return result

    def scan_and_block(self, text: str) -> tuple[bool, str]:
        """
        Scan text and return whether it is safe to store.

        Args:
            text: Text to scan.

        Returns:
            ``(is_safe, content_to_store)`` — when PII is detected
            *is_safe* is ``False`` and *content_to_store* is the redacted version.
        """
        result = self.scan(text)
        if result.has_pii:
            return False, result.redacted_text
        return True, text

    def get_statistics(self) -> dict[str, Any]:
        """
        Return statistics about the configured PII patterns.

        Returns:
            Dictionary with pattern statistics.
        """
        return {
            "pattern_count": len(self._patterns),
            "categories": [cat.name for cat in self._patterns],
            "strict_mode": self.strict_mode,
            "min_confidence": self.min_confidence,
            "policy_source": str(_governance_policy_path()),
        }


# ── Module-level convenience helpers ─────────────────────────────────────────

def scan_for_pii(text: str, strict_mode: bool = False) -> PIIScanResult:
    """
    Convenience function to scan text for PII.

    Args:
        text: Text to scan.
        strict_mode: Use strict detection mode.

    Returns:
        PIIScanResult with detection details.
    """
    return PIIGuard(strict_mode=strict_mode).scan(text)


def redact_pii(text: str, strict_mode: bool = False) -> str:
    """
    Convenience function to redact PII from text.

    Args:
        text: Text to redact.
        strict_mode: Use strict detection mode.

    Returns:
        Redacted text.
    """
    result = PIIGuard(strict_mode=strict_mode).scan(text)
    return result.redacted_text
