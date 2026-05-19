"""FreshnessGuarantee — ensures memory reads stay within freshness bounds.

Integrates with witness_governance.TrustStateSnapshot to tighten freshness
windows for agents under watch, probation, or restriction, and with
memory_node.EvidenceContract and FreshnessVerdict for evidence freshness.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.memory_node import EvidenceContract, FreshnessVerdict
from hlf_mcp.hlf.witness_governance import TrustStateSnapshot

# ---------------------------------------------------------------------------
# Freshness-window presets (seconds) keyed by trust tier
# ---------------------------------------------------------------------------
_FRESHNESS_WINDOWS: dict[str, int] = {
    "verified": 3600,
    "validated": 1800,
    "trusted": 900,
    "untrusted": 300,
    "local": 600,
}

# ---------------------------------------------------------------------------
# Multipliers applied to the trust-tier window when trust_state is degraded
# ---------------------------------------------------------------------------
_TRUST_STATE_MULTIPLIERS: dict[str, float] = {
    "healthy": 1.0,
    "watched": 0.6,
    "probation": 0.35,
    "restricted": 0.15,
}


@dataclass(slots=True)
class FreshnessGuarantee:
    """Result of a freshness check on a single item.

    Attributes:
        passed: Whether the item meets the freshness requirement.
        max_age_seconds: The effective max age applied (may be tightened).
        age_seconds: Actual age of the item in seconds.
        stale: Whether the item is stale (age > max_age).
        policy_action: Recommended action: "keep", "refresh", "evict", "quarantine".
        item_key: Identifier for the item checked.
    """

    passed: bool
    max_age_seconds: int
    age_seconds: float
    stale: bool
    policy_action: str = "keep"
    item_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "max_age_seconds": self.max_age_seconds,
            "age_seconds": self.age_seconds,
            "stale": self.stale,
            "policy_action": self.policy_action,
            "item_key": self.item_key,
        }


class FreshnessGuaranteeChecker:
    """Enforces memory freshness with trust-aware window tightening.

    Accepts optional TrustStateSnapshot to apply stricter freshness windows
    for agents with degraded trust states (watched / probation / restricted).
    """

    def __init__(self, trust_snapshot: TrustStateSnapshot | None = None) -> None:
        """Initialise the checker, optionally bound to an agent's trust snapshot.

        Args:
            trust_snapshot: If provided, freshness windows are tightened
                according to the agent's current trust_state.
        """
        self._trust_snapshot = trust_snapshot

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_freshness_window(self, trust_tier: str) -> int:
        """Return the effective freshness window in seconds for a trust tier.

        The base window is determined by trust_tier.  If a TrustStateSnapshot
        is bound and the agent's trust_state is degraded (watched / probation /
        restricted), the window is multiplied by the corresponding factor.

        Args:
            trust_tier: One of "verified", "validated", "trusted",
                "untrusted", "local".

        Returns:
            Effective freshness window in seconds.
        """
        base = _FRESHNESS_WINDOWS.get(trust_tier, 300)
        if self._trust_snapshot is not None:
            multiplier = _TRUST_STATE_MULTIPLIERS.get(
                self._trust_snapshot.trust_state, 1.0
            )
            base = int(base * multiplier)
        return base

    def check_freshness(
        self,
        memory_node_or_contract: Any,
        max_age_seconds: int | None = None,
    ) -> FreshnessVerdict:
        """Check whether a single memory node or evidence contract is still fresh.

        The check is driven by the ``fresh_until`` timestamp on the
        EvidenceContract.  If no EvidenceContract is present (e.g. a bare
        MemoryNode without evidence) the item is treated as fresh.

        Args:
            memory_node_or_contract: A MemoryNode (which has an ``evidence``
                attribute) or an EvidenceContract directly.
            max_age_seconds: Override maximum age.  If None, the effective
                window is derived from the trust tier via
                :meth:`compute_freshness_window`.

        Returns:
            FreshnessVerdict with admissibility and supporting reasons.
        """
        contract = self._extract_contract(memory_node_or_contract)
        if contract is None:
            return FreshnessVerdict(
                admissible=True,
                freshness_status="fresh",
                reasons=["no evidence contract — treated as fresh"],
            )

        # Compute effective max age
        if max_age_seconds is not None:
            effective_max = max_age_seconds
        else:
            effective_max = self.compute_freshness_window(contract.trust_tier)

        # If the contract has already been revoked or tombstoned, it is never fresh
        if contract.revoked:
            return FreshnessVerdict(
                admissible=False,
                freshness_status="expired",
                reasons=["evidence has been revoked"],
            )
        if contract.tombstoned:
            return FreshnessVerdict(
                admissible=False,
                freshness_status="expired",
                reasons=["evidence has been tombstoned"],
            )

        # Check the fresh_until timestamp
        now_ts = time.time()
        if contract.fresh_until is not None:
            age = now_ts - self._parse_fresh_until_epoch(contract.fresh_until)
            if contract.is_stale(now_ts=now_ts):
                return FreshnessVerdict(
                    admissible=False,
                    freshness_status="stale",
                    reasons=[
                        f"fresh_until ({contract.fresh_until}) has passed — "
                        f"age {age:.0f}s exceeds window {effective_max}s"
                    ],
                )
        else:
            # No explicit fresh_until — measure age from collected_at if available
            age = self._age_from_collected_at(contract, now_ts)

        # Age-based check against the effective window
        if age > effective_max:
            superseeded_by = contract.supersedes_sha256
            return FreshnessVerdict(
                admissible=False,
                freshness_status="stale",
                reasons=[
                    f"age {age:.0f}s exceeds freshness window {effective_max}s"
                ],
                superseded_by_sha256=superseeded_by if superseeded_by else "",
            )

        return FreshnessVerdict(
            admissible=True,
            freshness_status="fresh",
            reasons=[f"age {age:.0f}s within window {effective_max}s"],
        )

    def enforce_freshness(
        self,
        items: list[Any],
        max_age_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Batch-check freshness for a list of memory nodes or evidence contracts.

        Args:
            items: List of MemoryNode instances or EvidenceContract instances.
            max_age_seconds: Optional override for the freshness window.

        Returns:
            A dict with ``fresh``, ``stale``, and ``expired`` lists of keys,
            plus counts and a list of per-item :class:`FreshnessGuarantee` results.
        """
        results: dict[str, list[dict[str, Any]]] = {
            "fresh": [],
            "stale": [],
            "expired": [],
        }
        guarantees: list[dict[str, Any]] = []

        for idx, item in enumerate(items):
            verdict = self.check_freshness(item, max_age_seconds=max_age_seconds)

            contract = self._extract_contract(item)
            key = self._item_key(item, idx)
            if max_age_seconds is not None:
                max_age = max_age_seconds
            elif contract is not None:
                max_age = self.compute_freshness_window(contract.trust_tier)
            else:
                max_age = 0

            age = self._compute_age(item, max_age)

            policy_action = "keep"
            if verdict.freshness_status == "expired":
                policy_action = "quarantine"
            elif verdict.freshness_status == "stale":
                policy_action = "refresh"

            guarantee = FreshnessGuarantee(
                passed=verdict.admissible,
                max_age_seconds=max_age,
                age_seconds=age,
                stale=not verdict.admissible,
                policy_action=policy_action,
                item_key=key,
            )
            guarantees.append(guarantee.to_dict())

            category = {
                "fresh": "fresh",
                "stale": "stale",
                "expired": "expired",
            }.get(verdict.freshness_status, "stale")

            results[category].append(key)

        return {
            "fresh_count": len(results["fresh"]),
            "stale_count": len(results["stale"]),
            "expired_count": len(results["expired"]),
            "fresh": results["fresh"],
            "stale": results["stale"],
            "expired": results["expired"],
            "results": guarantees,
        }

    def stale_policy(self, stale_items: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate policy recommendations for stale items.

        Categorises stale items into refresh / evict / quarantine buckets
        based on the evidence state (revoked, tombstoned, stale, supersession).

        Args:
            stale_items: List of dicts each containing at least ``item_key``,
                and optionally ``evidence`` with revocation/tombstone/flags.

        Returns:
            Dict with ``recommendations`` (per-item) and ``summary`` counts.
        """
        recommendations: list[dict[str, Any]] = []
        summary: dict[str, int] = {"refresh": 0, "evict": 0, "quarantine": 0}

        for item in stale_items:
            evidence = item.get("evidence") or {}
            key = item.get("item_key", item.get("sha256", "unknown"))

            # Always quarantine revoked / tombstoned items
            if isinstance(evidence, dict):
                if evidence.get("revoked") or evidence.get("tombstoned"):
                    action = "quarantine"
                elif evidence.get("supersedes_sha256"):
                    action = "refresh"  # has a newer version
                elif evidence.get("fresh_until"):
                    action = "refresh"
                else:
                    action = "evict"
            elif isinstance(evidence, EvidenceContract):
                if evidence.revoked or evidence.tombstoned:
                    action = "quarantine"
                elif evidence.supersedes_sha256:
                    action = "refresh"
                elif evidence.fresh_until:
                    action = "refresh"
                else:
                    action = "evict"
            else:
                action = "evict"

            summary[action] += 1
            recommendations.append(
                {
                    "item_key": key,
                    "action": action,
                    "rationale": self._action_rationale(action),
                }
            )

        return {
            "summary": summary,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_contract(item: Any) -> EvidenceContract | None:
        """Extract an EvidenceContract from a MemoryNode or return the item itself."""
        if isinstance(item, EvidenceContract):
            return item
        # MemoryNode has .evidence attribute
        evidence = getattr(item, "evidence", None)
        if isinstance(evidence, EvidenceContract):
            return evidence
        return None

    @staticmethod
    def _item_key(item: Any, idx: int) -> str:
        """Derive a stable key for an item."""
        if isinstance(item, EvidenceContract):
            return item.sha256 or f"contract-{idx}"
        node_id = getattr(item, "node_id", None)
        if node_id:
            return str(node_id)
        sha = getattr(item, "content_hash", None) or getattr(item, "sha256", None)
        if sha:
            return str(sha)
        return f"item-{idx}"

    @staticmethod
    def _parse_fresh_until_epoch(fresh_until: str) -> float:
        """Parse a fresh_until ISO timestamp into a Unix epoch float."""
        try:
            from datetime import UTC, datetime as _dt

            parsed = _dt.fromisoformat(fresh_until)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.timestamp()
        except (ValueError, OSError):
            return 0.0

    @staticmethod
    def _age_from_collected_at(contract: EvidenceContract, now_ts: float) -> float:
        """Compute age in seconds from the collected_at timestamp."""
        if not contract.collected_at:
            return 0.0
        try:
            from datetime import UTC, datetime as _dt

            parsed = _dt.fromisoformat(contract.collected_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return now_ts - parsed.timestamp()
        except (ValueError, OSError):
            return 0.0

    @staticmethod
    def _compute_age(item: Any, fallback_max: int) -> float:
        """Compute the best available age for an item."""
        contract = FreshnessGuaranteeChecker._extract_contract(item)
        now_ts = time.time()
        if contract is not None and contract.fresh_until is not None:
            age = now_ts - FreshnessGuaranteeChecker._parse_fresh_until_epoch(
                contract.fresh_until
            )
            return max(0.0, age)
        if contract is not None and contract.collected_at:
            return FreshnessGuaranteeChecker._age_from_collected_at(contract, now_ts)
        # Fallback: use created_at from MemoryNode
        created = getattr(item, "created_at", None)
        if created:
            try:
                from datetime import UTC, datetime as _dt

                parsed = _dt.fromisoformat(created)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return now_ts - parsed.timestamp()
            except (ValueError, OSError):
                pass
        return float(fallback_max)

    @staticmethod
    def _action_rationale(action: str) -> str:
        """Return a human-readable rationale for a policy action."""
        return {
            "refresh": "Item is stale but has a superseding version — refresh recommended.",
            "evict": "Item is stale with no superseding version — eviction recommended.",
            "quarantine": "Item has been revoked or tombstoned — quarantine immediately.",
        }.get(action, "Unknown action.")
