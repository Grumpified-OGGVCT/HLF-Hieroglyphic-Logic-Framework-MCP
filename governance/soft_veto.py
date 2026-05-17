"""
Soft Veto Gate — Near-boundary ALIGN decisions.

When an intent is close to an ALIGN boundary but not clearly
violating, the Soft Veto Gate creates a "pause" instead of a
hard block. This prevents false positives from killing legitimate
work while still flagging risky intents for human review.

Decision Bands:
  - PASS:        confidence < low_threshold  → clearly safe
  - SOFT_VETO:   low_threshold <= conf < high_threshold → needs review
  - HARD_BLOCK:  confidence >= high_threshold → clearly dangerous

Usage:
    gate = SoftVetoGate()
    decision = gate.evaluate("rm -rf ./tmp/cache", rule_matches=[...])
    if decision.is_soft_veto:
        gate.escalate(decision, queue="human-review")
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── Decision Types ─────────────────────────────────────────────────────────

class VetoLevel(Enum):
    PASS = "pass"
    SOFT_VETO = "soft_veto"
    HARD_BLOCK = "hard_block"


@dataclass
class RuleMatch:
    """A partial ALIGN rule match with a confidence score."""
    rule_id: str
    rule_name: str
    match_confidence: float    # [0.0, 1.0] how closely it matched
    matched_pattern: str = ""
    context: str = ""


@dataclass
class VetoDecision:
    """The gate's decision on an intent."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    level: VetoLevel = VetoLevel.PASS
    confidence: float = 0.0
    reason: str = ""
    matched_rules: list[RuleMatch] = field(default_factory=list)
    input_preview: str = ""         # First 100 chars of input
    timestamp: float = field(default_factory=time.time)
    escalated: bool = False
    escalation_queue: str = ""
    resolved: bool = False
    resolution: str = ""            # approved / denied / expired

    @property
    def is_pass(self) -> bool:
        return self.level == VetoLevel.PASS

    @property
    def is_soft_veto(self) -> bool:
        return self.level == VetoLevel.SOFT_VETO

    @property
    def is_hard_block(self) -> bool:
        return self.level == VetoLevel.HARD_BLOCK

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "level": self.level.value,
            "confidence": round(self.confidence, 4),
            "reason": self.reason,
            "matched_rules": [
                {
                    "rule_id": m.rule_id,
                    "rule_name": m.rule_name,
                    "confidence": m.match_confidence,
                }
                for m in self.matched_rules
            ],
            "input_preview": self.input_preview,
            "escalated": self.escalated,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


# ─── Soft Veto Gate ─────────────────────────────────────────────────────────

class SoftVetoGate:
    """Evaluates intents with fuzzy ALIGN boundary awareness.

    Instead of binary pass/fail, uses confidence bands to create
    a "soft veto" zone for near-boundary decisions.
    """

    def __init__(
        self,
        *,
        low_threshold: float = 0.4,
        high_threshold: float = 0.8,
        auto_expire_minutes: float = 60.0,
    ) -> None:
        if low_threshold >= high_threshold:
            raise ValueError("low_threshold must be < high_threshold")

        self._low = low_threshold
        self._high = high_threshold
        self._auto_expire = auto_expire_minutes * 60  # seconds
        self._pending: list[VetoDecision] = []
        self._history: list[VetoDecision] = []

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def evaluate(
        self,
        input_text: str,
        rule_matches: list[RuleMatch],
    ) -> VetoDecision:
        """Evaluate an input against fuzzy ALIGN boundaries.

        Args:
            input_text: The raw input to evaluate.
            rule_matches: Partial ALIGN rule matches with confidence scores.

        Returns:
            A VetoDecision with the gate's determination.
        """
        if not rule_matches:
            decision = VetoDecision(
                level=VetoLevel.PASS,
                confidence=0.0,
                reason="No rule matches",
                input_preview=input_text[:100],
            )
            self._history.append(decision)
            return decision

        # Aggregate confidence: max of all matches
        max_conf = max(m.match_confidence for m in rule_matches)
        avg_conf = sum(m.match_confidence for m in rule_matches) / len(rule_matches)
        # Use max for severity, avg for breadth
        combined = 0.7 * max_conf + 0.3 * avg_conf

        # Determine level
        if combined >= self._high:
            level = VetoLevel.HARD_BLOCK
            reason = f"Hard block: confidence {combined:.3f} >= {self._high}"
        elif combined >= self._low:
            level = VetoLevel.SOFT_VETO
            reason = (
                f"Soft veto: confidence {combined:.3f} in range "
                f"[{self._low}, {self._high})"
            )
        else:
            level = VetoLevel.PASS
            reason = f"Pass: confidence {combined:.3f} < {self._low}"

        decision = VetoDecision(
            level=level,
            confidence=combined,
            reason=reason,
            matched_rules=rule_matches,
            input_preview=input_text[:100],
        )

        if decision.is_soft_veto:
            self._pending.append(decision)

        self._history.append(decision)
        return decision

    def escalate(
        self,
        decision: VetoDecision,
        queue: str = "human-review",
    ) -> None:
        """Escalate a soft-veto decision to a review queue."""
        if not decision.is_soft_veto:
            raise ValueError("Can only escalate soft-veto decisions")
        decision.escalated = True
        decision.escalation_queue = queue

    def resolve(
        self,
        decision_id: str,
        resolution: str,
        *,
        resolved_by: str = "human",
    ) -> VetoDecision | None:
        """Resolve a pending soft-veto decision.

        Args:
            decision_id: The decision to resolve.
            resolution: "approved" or "denied".
            resolved_by: Who resolved it.

        Returns:
            The resolved decision, or None if not found.
        """
        if resolution not in ("approved", "denied"):
            raise ValueError("Resolution must be 'approved' or 'denied'")

        for d in self._pending:
            if d.decision_id == decision_id:
                d.resolved = True
                d.resolution = resolution
                self._pending.remove(d)
                return d
        return None

    def expire_stale(self) -> int:
        """Auto-expire stale pending decisions."""
        now = time.time()
        expired = 0
        for d in list(self._pending):
            if now - d.timestamp > self._auto_expire:
                d.resolved = True
                d.resolution = "expired"
                self._pending.remove(d)
                expired += 1
        return expired

    def get_pending(self) -> list[dict[str, Any]]:
        """Get all pending soft-veto decisions."""
        return [d.to_dict() for d in self._pending]

    def get_history(
        self,
        *,
        limit: int = 50,
        level: VetoLevel | None = None,
    ) -> list[dict[str, Any]]:
        """Get decision history."""
        hist = list(self._history)
        if level:
            hist = [d for d in hist if d.level == level]
        hist.reverse()
        return [d.to_dict() for d in hist[:limit]]

    def get_stats(self) -> dict[str, Any]:
        """Get gate statistics."""
        total = len(self._history)
        by_level = {"pass": 0, "soft_veto": 0, "hard_block": 0}
        for d in self._history:
            by_level[d.level.value] += 1
        return {
            "total_decisions": total,
            "pending": self.pending_count,
            "by_level": by_level,
            "soft_veto_rate": (
                round(by_level["soft_veto"] / max(1, total) * 100, 1)
            ),
            "hard_block_rate": (
                round(by_level["hard_block"] / max(1, total) * 100, 1)
            ),
        }
