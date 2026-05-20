"""
Trust Debt Quantifier — tracks and compounds debt from trust surface violations.

When trust surface violations go unresolved they accumulate "trust debt" —
a quantifiable measure of governance risk that compounds over time.
This module assigns debt scores to violations, calculates compound
interest, generates aging reports, and produces paydown priorities
so operators know exactly what to fix first.

Key design principles:
  - Debt metaphor: violations are loans against trust that accrue
    daily compound interest until resolved.
  - Severity-weighted: constitutional boundary violations (FORK, DETACH)
    carry higher principal and higher interest rates than lesser ones.
  - Operator-first: paydown priorities are sorted by the total accrued
    cost so the most expensive item is always at the top.
  - Time-aware: aging buckets and debt timelines show how debt grew
    over time and what it looks like if left unresolved.

Integration points:
  - hlf_mcp.hlf.trust_surface.find_trust_violations    → violation input
  - hlf_mcp.hlf.trust_surface.validate_trust_against_constitution → violation input
  - hlf_mcp.hlf.trust_trending.TrustTrending            → debt_total feeds snapshots
  - hlf_mcp.hlf.remediation_planner.RemediationPlanner  → debt priorities become tasks
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # trust_surface violations are plain dicts, no import needed


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

_VIOLATION_SEVERITY: dict[str, float] = {
    "FORK": 0.9,
    "DETACH": 0.8,
    "DIVERT": 0.7,
    "EVADE": 0.6,
    "high_trust_c1_boundary": 0.9,
    "high_trust_c2_boundary": 0.85,
    "high_trust_c3_boundary": 0.8,
    "high_trust_constitutional_boundary": 0.8,
    "trust_without_evidence": 0.5,
    "conditional_trust_no_conditions": 0.45,
    "circular_trust_dependency": 0.35,
}

_PRINCIPAL_MULTIPLIER: float = 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# DebtItem — a single trust debt instrument
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class DebtItem:
    """A single trust debt item representing one unresolved violation.

    Each DebtItem behaves like a financial instrument: it has a
    principal (base debt), an interest rate (daily compounding), and
    an incurred date from which interest accrues.  Resolving the
    violation stops interest accumulation.

    Attributes:
        violation_id: Unique identifier for the violation.
        source: Which component or edge originated the debt.
        category: Violation category (FORK, DETACH, DIVERT, EVADE, etc.).
        severity: How severe the violation is (0.0–1.0).
        principal: Base debt amount before interest.
        interest_rate: Daily compounding rate.
        incurred_at: ISO-8601 timestamp when the violation was detected.
        last_assessed_at: ISO-8601 timestamp of the most recent assessment.
        resolved: Whether the violation has been addressed.
        resolution_note: Human-readable note about the resolution.
    """

    violation_id: str
    source: str
    category: str
    severity: float
    principal: float
    interest_rate: float
    incurred_at: str
    last_assessed_at: str
    resolved: bool = False
    resolution_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the debt item."""
        return {
            "violation_id": self.violation_id,
            "source": self.source,
            "category": self.category,
            "severity": self.severity,
            "principal": self.principal,
            "interest_rate": self.interest_rate,
            "incurred_at": self.incurred_at,
            "last_assessed_at": self.last_assessed_at,
            "resolved": self.resolved,
            "resolution_note": self.resolution_note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DebtItem:
        """Deserialize from a dict."""
        return cls(
            violation_id=str(data.get("violation_id", "")),
            source=str(data.get("source", "")),
            category=str(data.get("category", "")),
            severity=float(data.get("severity", 0.5)),
            principal=float(data.get("principal", 0.0)),
            interest_rate=float(data.get("interest_rate", 0.01)),
            incurred_at=str(data.get("incurred_at", "")),
            last_assessed_at=str(data.get("last_assessed_at", "")),
            resolved=bool(data.get("resolved", False)),
            resolution_note=str(data.get("resolution_note", "")),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _compound_interest(principal: float, rate: float, days: float) -> float:
    """Calculate compound interest: principal × (1 + rate)^days.

    Args:
        principal: Base amount.
        rate: Daily compounding rate (e.g. 0.01 = 1% per day).
        days: Number of days to compound.

    Returns:
        The total amount including compounded interest.
    """
    if days <= 0 or rate <= 0:
        return principal
    return principal * math.pow(1.0 + rate, days)


def _days_between(iso_a: str, iso_b: str) -> float:
    """Compute fractional days between two ISO-8601 timestamps.

    Returns 0.0 if either timestamp is missing or unparseable.
    """
    try:
        dt_a = datetime.fromisoformat(iso_a.replace("Z", "+00:00"))
        dt_b = datetime.fromisoformat(iso_b.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 0.0
    return (dt_b - dt_a).total_seconds() / 86400.0


def _iso_now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_violation_id(source: str, category: str, timestamp: str) -> str:
    """Generate a stable violation ID from source + category + timestamp."""
    import hashlib
    raw = f"{source}::{category}::{timestamp}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


# ═══════════════════════════════════════════════════════════════════════════════
# TrustDebtQuantifier — main debt tracking engine
# ═══════════════════════════════════════════════════════════════════════════════


class TrustDebtQuantifier:
    """Assigns, tracks, and compounds trust debt from surface violations.

    Trust debt is the governance risk that accumulates when violations
    of the trust surface are detected but not resolved.  This quantifier
    models violations as financial debt instruments and provides
    operators with clear paydown priorities.

    Usage::

        quantifier = TrustDebtQuantifier(name="production-debt", daily_interest_base=0.02)
        debt_items = quantifier.assess_violations(violations)
        current = quantifier.calculate_current_debt(debt_items)
        priorities = quantifier.paydown_priorities(debt_items)
    """

    def __init__(
        self,
        name: str = "trust-debt",
        daily_interest_base: float = 0.01,
    ) -> None:
        """Initialise the debt quantifier.

        Args:
            name: Human-readable label for this quantifier instance.
            daily_interest_base: Base daily interest rate applied to all
                violations before severity weighting (default 1%).
        """
        self.name = name
        self.daily_interest_base = daily_interest_base

    # ── Violation assessment ────────────────────────────────────────────────

    def assess_violations(self, violations: list[dict[str, Any]]) -> list[DebtItem]:
        """Convert trust surface violations into debt items.

        Each violation is assigned a severity based on its category
        (FORK→0.9, DETACH→0.8, DIVERT→0.7, EVADE→0.6, unknown→0.5),
        a principal of severity × 100, and a daily interest rate of
        daily_interest_base × severity.

        Args:
            violations: List of violation dicts from
                TrustSurface.find_trust_violations() or
                validate_trust_against_constitution().

        Returns:
            List of DebtItem objects, one per violation.
        """
        now = _iso_now()
        items: list[DebtItem] = []

        for violation in violations:
            category = str(violation.get("violation_type", violation.get("category", "")))
            severity = _VIOLATION_SEVERITY.get(category, 0.5)
            principal = severity * _PRINCIPAL_MULTIPLIER
            interest_rate = self.daily_interest_base * severity
            source = str(violation.get("component", violation.get("source", "unknown")))
            timestamp = str(violation.get("timestamp", now))
            violation_id = _generate_violation_id(source, category, timestamp)

            items.append(DebtItem(
                violation_id=violation_id,
                source=source,
                category=category,
                severity=severity,
                principal=principal,
                interest_rate=interest_rate,
                incurred_at=timestamp,
                last_assessed_at=now,
            ))

        return items

    # ── Current debt calculation ────────────────────────────────────────────

    def calculate_current_debt(
        self,
        items: list[DebtItem],
        as_of: str | None = None,
    ) -> float:
        """Calculate the total current trust debt including compound interest.

        Sums the compounded value of every unresolved debt item from
        its incurrence date to the assessment date (or now).

        Args:
            items: The debt items to evaluate.
            as_of: Optional ISO-8601 timestamp for the valuation date.
                Defaults to now.

        Returns:
            Total debt as a float.
        """
        as_of_ts = as_of if as_of else _iso_now()
        total: float = 0.0

        for item in items:
            if item.resolved:
                continue
            days = _days_between(item.incurred_at, as_of_ts)
            if days <= 0:
                total += item.principal
            else:
                total += _compound_interest(item.principal, item.interest_rate, days)

        return round(total, 4)

    # ── Aging report ───────────────────────────────────────────────────────

    def aging_report(self, items: list[DebtItem]) -> dict[str, Any]:
        """Group unresolved debt items by age buckets.

        Buckets:
          - 0-1d: incurred within the last 24 hours.
          - 1-7d: incurred 1–7 days ago.
          - 7-30d: incurred 7–30 days ago.
          - 30d+: incurred more than 30 days ago.

        Args:
            items: The debt items to analyse.

        Returns:
            A dict with keys:
                buckets: dict mapping bucket name to {count, total_debt, items}.
                total_unresolved: int — number of unresolved items.
                total_debt: float — current total debt.
                oldest_item: dict | None — the single oldest unresolved item.
        """
        now = _iso_now()
        unresolved = [item for item in items if not item.resolved]

        buckets: dict[str, dict[str, Any]] = {
            "0-1d": {"count": 0, "total_debt": 0.0, "items": []},
            "1-7d": {"count": 0, "total_debt": 0.0, "items": []},
            "7-30d": {"count": 0, "total_debt": 0.0, "items": []},
            "30d+": {"count": 0, "total_debt": 0.0, "items": []},
        }

        oldest_item: dict[str, Any] | None = None
        oldest_days: float = 0.0

        for item in unresolved:
            days = _days_between(item.incurred_at, now)
            current_value = _compound_interest(
                item.principal, item.interest_rate, max(days, 0)
            )

            if days <= 1:
                bucket = "0-1d"
            elif days <= 7:
                bucket = "1-7d"
            elif days <= 30:
                bucket = "7-30d"
            else:
                bucket = "30d+"

            buckets[bucket]["count"] += 1
            buckets[bucket]["total_debt"] += current_value
            buckets[bucket]["items"].append(item.violation_id)

            if days > oldest_days:
                oldest_days = days
                oldest_item = {
                    "violation_id": item.violation_id,
                    "source": item.source,
                    "category": item.category,
                    "days_outstanding": round(days, 1),
                    "current_value": round(current_value, 4),
                }

        return {
            "buckets": buckets,
            "total_unresolved": len(unresolved),
            "total_debt": round(
                sum(
                    _compound_interest(
                        item.principal,
                        item.interest_rate,
                        max(_days_between(item.incurred_at, now), 0),
                    )
                    for item in unresolved
                ),
                4,
            ),
            "oldest_item": oldest_item,
        }

    # ── Paydown priorities ─────────────────────────────────────────────────

    def paydown_priorities(self, items: list[DebtItem]) -> list[DebtItem]:
        """Sort unresolved debt items by total accrued cost descending.

        Priority score = principal × interest_rate × days_outstanding.
        Higher scores mean more accumulated risk — fix these first.

        Args:
            items: The debt items to prioritise.

        Returns:
            Sorted list of unresolved DebtItem objects, highest priority first.
        """
        now = _iso_now()
        unresolved = [item for item in items if not item.resolved]

        def _priority_score(item: DebtItem) -> float:
            days = max(_days_between(item.incurred_at, now), 0.01)
            return item.principal * item.interest_rate * days

        return sorted(unresolved, key=_priority_score, reverse=True)

    # ── Debt timeline projection ───────────────────────────────────────────

    def debt_timeline(
        self,
        items: list[DebtItem],
        intervals: int = 10,
    ) -> list[dict[str, Any]]:
        """Project total debt at N evenly-spaced intervals from earliest
        incurred_at to now, assuming no resolution events.

        Args:
            items: The debt items to project.
            intervals: Number of evenly-spaced sample points (default 10).

        Returns:
            List of dicts, each with:
                timestamp: str — ISO-8601 timestamp of the sample point.
                total_debt: float — total compound debt at that point.
                unresolved_count: int — number of unresolved items.
        """
        now = _iso_now()
        unresolved = [item for item in items if not item.resolved]

        if not unresolved:
            return [{
                "timestamp": now,
                "total_debt": 0.0,
                "unresolved_count": 0,
            }]

        # Find earliest incurrence
        earliest = min(
            (item.incurred_at for item in unresolved),
            key=lambda ts: ts,
        )

        try:
            dt_earliest = datetime.fromisoformat(earliest.replace("Z", "+00:00"))
            dt_now = datetime.fromisoformat(now.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return [{
                "timestamp": now,
                "total_debt": 0.0,
                "unresolved_count": len(unresolved),
            }]

        total_span = (dt_now - dt_earliest).total_seconds()
        if total_span <= 0:
            return [{
                "timestamp": now,
                "total_debt": sum(item.principal for item in unresolved),
                "unresolved_count": len(unresolved),
            }]

        timeline: list[dict[str, Any]] = []
        for i in range(intervals + 1):
            offset = total_span * i / intervals
            point_dt = dt_earliest + timedelta(seconds=offset)
            point_iso = point_dt.isoformat()

            total: float = 0.0
            active_count: int = 0
            for item in unresolved:
                try:
                    item_dt = datetime.fromisoformat(item.incurred_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
                if item_dt > point_dt:
                    continue
                active_count += 1
                days = (point_dt - item_dt).total_seconds() / 86400.0
                total += _compound_interest(item.principal, item.interest_rate, max(days, 0))

            timeline.append({
                "timestamp": point_iso,
                "total_debt": round(total, 4),
                "unresolved_count": active_count,
            })

        return timeline

    # ── Debt resolution ────────────────────────────────────────────────────

    def resolve_debt(self, item: DebtItem, note: str = "") -> DebtItem:
        """Mark a debt item as resolved and record the resolution note.

        Args:
            item: The debt item to resolve.
            note: Human-readable note about how/why it was resolved.

        Returns:
            A new DebtItem with resolved=True and the resolution note set.
        """
        return DebtItem(
            violation_id=item.violation_id,
            source=item.source,
            category=item.category,
            severity=item.severity,
            principal=item.principal,
            interest_rate=item.interest_rate,
            incurred_at=item.incurred_at,
            last_assessed_at=_iso_now(),
            resolved=True,
            resolution_note=note,
        )
