"""
Capability Decay Model — tracks persona capability freshness, triggers
re-certification when capabilities become stale.

Provides:
  - CapabilityDecayModel: tracks capability freshness over time
  - CapabilityRecord: a single capability's freshness record
  - DecayReport: aggregate decay report for a persona
  - RecertificationTrigger: conditions under which re-certification fires

Integration points:
  - hlf_mcp.persona.operator_doctrine: OperatorDoctrine for capability baseline
  - hlf_mcp.persona.gate_integration: PersonaGate for re-certification gating
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# CapabilityRecord — freshness record for a single capability
# ---------------------------------------------------------------------------


@dataclass
class CapabilityRecord:
    """Tracks freshness of a single persona capability.

    Attributes:
        capability_name: The capability being tracked.
        persona: The persona that owns this capability.
        last_certified_at: Unix timestamp of last certification.
        certification_ttl_seconds: How long certification is valid.
        current_level: Current capability level (0.0 to 1.0).
        certified_level: Level at last certification.
        certification_evidence: Evidence hash from last cert.
        renewal_count: Number of times this capability has been renewed.
    """

    capability_name: str
    persona: str = ""
    last_certified_at: float = field(default_factory=time.time)
    certification_ttl_seconds: float = 86400.0  # 24 hours default
    current_level: float = 1.0
    certified_level: float = 1.0
    certification_evidence: str = ""
    renewal_count: int = 0

    def is_stale(self, now: float | None = None) -> bool:
        """Check if the capability certification has expired."""
        t = now if now is not None else time.time()
        return (t - self.last_certified_at) > self.certification_ttl_seconds

    def time_until_stale(self, now: float | None = None) -> float:
        """Return seconds until this capability becomes stale, or 0 if already stale."""
        t = now if now is not None else time.time()
        remaining = self.certification_ttl_seconds - (t - self.last_certified_at)
        return max(0.0, remaining)

    def age_seconds(self, now: float | None = None) -> float:
        """Return the age of this certification in seconds."""
        t = now if now is not None else time.time()
        return t - self.last_certified_at

    def freshness_score(self, now: float | None = None) -> float:
        """Return a freshness score (0.0 = stale, 1.0 = freshly certified)."""
        t = now if now is not None else time.time()
        age = t - self.last_certified_at
        if age <= 0:
            return 1.0
        if age >= self.certification_ttl_seconds:
            return 0.0
        return 1.0 - (age / self.certification_ttl_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_name": self.capability_name,
            "persona": self.persona,
            "last_certified_at": self.last_certified_at,
            "certification_ttl_seconds": self.certification_ttl_seconds,
            "current_level": self.current_level,
            "certified_level": self.certified_level,
            "certification_evidence": self.certification_evidence,
            "renewal_count": self.renewal_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRecord":
        return cls(
            capability_name=str(data.get("capability_name", "")),
            persona=str(data.get("persona", "")),
            last_certified_at=float(data.get("last_certified_at", time.time())),
            certification_ttl_seconds=float(data.get("certification_ttl_seconds", 86400.0)),
            current_level=float(data.get("current_level", 1.0)),
            certified_level=float(data.get("certified_level", 1.0)),
            certification_evidence=str(data.get("certification_evidence", "")),
            renewal_count=int(data.get("renewal_count", 0)),
        )


# ---------------------------------------------------------------------------
# DecayReport — aggregate decay report for a persona
# ---------------------------------------------------------------------------


@dataclass
class DecayReport:
    """Aggregate capability decay report for a persona.

    Attributes:
        report_id: Unique report identifier.
        persona: The persona being reported on.
        total_capabilities: Number of capabilities tracked.
        stale_capabilities: Number of stale capabilities.
        critical_capabilities: Number of critically stale (freshness < 0.1).
        average_freshness: Mean freshness score across all capabilities.
        capabilities: All capability records.
        recertification_needed: Whether any capability needs re-cert.
        generated_at: Report timestamp.
    """

    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    persona: str = ""
    total_capabilities: int = 0
    stale_capabilities: int = 0
    critical_capabilities: int = 0
    average_freshness: float = 1.0
    capabilities: list[CapabilityRecord] = field(default_factory=list)
    recertification_needed: bool = False
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "persona": self.persona,
            "total_capabilities": self.total_capabilities,
            "stale_capabilities": self.stale_capabilities,
            "critical_capabilities": self.critical_capabilities,
            "average_freshness": round(self.average_freshness, 4),
            "capabilities": [c.to_dict() for c in self.capabilities],
            "recertification_needed": self.recertification_needed,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# RecertificationTrigger — when to trigger re-cert
# ---------------------------------------------------------------------------


@dataclass
class RecertificationTrigger:
    """Conditions under which re-certification fires for a persona.

    Attributes:
        trigger_id: Unique trigger identifier.
        persona: The persona to re-certify.
        trigger_reason: Why re-certification was triggered.
        capabilities_affected: Which capabilities need renewal.
        urgency: How urgent the re-cert is (low / medium / high / critical).
        recommended_actions: Suggested actions for the operator.
        triggered_at: Timestamp of trigger.
    """

    trigger_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    persona: str = ""
    trigger_reason: str = ""
    capabilities_affected: list[str] = field(default_factory=list)
    urgency: str = "medium"
    recommended_actions: list[str] = field(default_factory=list)
    triggered_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "persona": self.persona,
            "trigger_reason": self.trigger_reason,
            "capabilities_affected": list(self.capabilities_affected),
            "urgency": self.urgency,
            "recommended_actions": list(self.recommended_actions),
            "triggered_at": self.triggered_at,
        }


# ---------------------------------------------------------------------------
# CapabilityDecayModel — tracks and predicts capability freshness
# ---------------------------------------------------------------------------


class CapabilityDecayModel:
    """Tracks persona capability freshness and triggers re-certification.

    Each persona capability has a certification TTL.  As capabilities
    age, their freshness score decays.  When freshness drops below
    configurable thresholds, re-certification triggers are fired.

    Usage::

        model = CapabilityDecayModel()
        model.register_capability(
            persona="steward",
            capability="review_tool_contracts",
            ttl_seconds=86400,
        )
        report = model.generate_decay_report("steward")
        if report.recertification_needed:
            triggers = model.check_triggers("steward")
    """

    def __init__(
        self,
        doctrine: Any = None,  # OperatorDoctrine (lazy import)
        default_ttl: float = 86400.0,
        stale_threshold: float = 0.3,
        critical_threshold: float = 0.1,
    ) -> None:
        self._doctrine = doctrine
        self._default_ttl = default_ttl
        self._stale_threshold = stale_threshold
        self._critical_threshold = critical_threshold
        self._capabilities: dict[str, dict[str, CapabilityRecord]] = {}
        self._triggers: list[RecertificationTrigger] = []
        self._reports: list[DecayReport] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_capability(
        self,
        persona: str,
        capability: str,
        ttl_seconds: float | None = None,
        initial_level: float = 1.0,
        evidence: str = "",
    ) -> CapabilityRecord:
        """Register a capability for decay tracking.

        Args:
            persona: The persona owning the capability.
            capability: The capability name.
            ttl_seconds: Custom TTL (defaults to model default).
            initial_level: Initial capability level.
            evidence: Certification evidence hash.

        Returns:
            The created CapabilityRecord.
        """
        p = persona.strip().lower()
        cap = capability.strip().lower()

        if p not in self._capabilities:
            self._capabilities[p] = {}

        record = CapabilityRecord(
            capability_name=cap,
            persona=p,
            certification_ttl_seconds=(
                ttl_seconds if ttl_seconds is not None else self._default_ttl
            ),
            current_level=initial_level,
            certified_level=initial_level,
            certification_evidence=evidence,
        )
        self._capabilities[p][cap] = record
        return record

    def certify(
        self,
        persona: str,
        capability: str,
        level: float = 1.0,
        evidence: str = "",
    ) -> CapabilityRecord | None:
        """Re-certify a capability, resetting its decay clock.

        Args:
            persona: The persona being certified.
            capability: The capability being certified.
            level: New certification level.
            evidence: Certification evidence hash.

        Returns:
            Updated CapabilityRecord, or None if not registered.
        """
        p = persona.strip().lower()
        cap = capability.strip().lower()

        record = self._capabilities.get(p, {}).get(cap)
        if record is None:
            return None

        record.last_certified_at = time.time()
        record.certified_level = level
        record.current_level = max(record.current_level, level)
        record.certification_evidence = evidence
        record.renewal_count += 1
        return record

    def degrade_capability(
        self, persona: str, capability: str, level: float
    ) -> CapabilityRecord | None:
        """Manually degrade a capability level (e.g., after an incident).

        Args:
            persona: The persona.
            capability: The capability to degrade.
            level: New lowered level.

        Returns:
            Updated CapabilityRecord, or None if not registered.
        """
        p = persona.strip().lower()
        cap = capability.strip().lower()

        record = self._capabilities.get(p, {}).get(cap)
        if record is None:
            return None

        record.current_level = max(0.0, min(1.0, level))
        return record

    def get_capability(
        self, persona: str, capability: str
    ) -> CapabilityRecord | None:
        """Get a specific capability record."""
        p = persona.strip().lower()
        cap = capability.strip().lower()
        return self._capabilities.get(p, {}).get(cap)

    def get_all_capabilities(self, persona: str) -> list[CapabilityRecord]:
        """Get all capability records for a persona."""
        p = persona.strip().lower()
        return list(self._capabilities.get(p, {}).values())

    def generate_decay_report(self, persona: str) -> DecayReport:
        """Generate a decay report for a persona.

        Computes freshness scores, identifies stale and critical capabilities,
        and determines if re-certification is needed.

        Args:
            persona: The persona to report on.

        Returns:
            DecayReport with detailed decay analysis.
        """
        p = persona.strip().lower()
        capabilities = list(self._capabilities.get(p, {}).values())
        now = time.time()

        total = len(capabilities)
        stale = 0
        critical = 0
        freshness_sum = 0.0

        for record in capabilities:
            score = record.freshness_score(now)
            freshness_sum += score
            if score <= self._stale_threshold:
                stale += 1
            if score <= self._critical_threshold:
                critical += 1

        avg_freshness = freshness_sum / max(total, 1)
        needs_recert = stale > 0

        report = DecayReport(
            persona=p,
            total_capabilities=total,
            stale_capabilities=stale,
            critical_capabilities=critical,
            average_freshness=avg_freshness,
            capabilities=capabilities,
            recertification_needed=needs_recert,
        )
        self._reports.append(report)
        return report

    def generate_all_reports(self) -> dict[str, DecayReport]:
        """Generate decay reports for all tracked personas.

        Returns:
            Dict mapping persona name to DecayReport.
        """
        reports: dict[str, DecayReport] = {}
        for persona in sorted(self._capabilities.keys()):
            reports[persona] = self.generate_decay_report(persona)
        return reports

    def check_triggers(self, persona: str) -> list[RecertificationTrigger]:
        """Check if any capabilities need re-certification and generate triggers.

        Args:
            persona: The persona to check.

        Returns:
            List of RecertificationTriggers for capabilities needing renewal.
        """
        p = persona.strip().lower()
        capabilities = self._capabilities.get(p, {})
        now = time.time()
        triggers: list[RecertificationTrigger] = []

        for cap_name, record in capabilities.items():
            score = record.freshness_score(now)

            if score <= self._critical_threshold:
                urgency = "critical"
                reason = (
                    f"Capability '{cap_name}' for persona '{p}' is critically stale "
                    f"(freshness: {score:.2f}). Immediate re-certification required."
                )
                actions = [
                    f"Re-certify '{cap_name}' for persona '{p}' immediately",
                    f"Escalate to operator if re-certification cannot be completed",
                ]
            elif score <= self._stale_threshold:
                urgency = "high"
                reason = (
                    f"Capability '{cap_name}' for persona '{p}' is stale "
                    f"(freshness: {score:.2f}). Re-certification recommended."
                )
                actions = [
                    f"Schedule re-certification for '{cap_name}'",
                    f"Review capability '{cap_name}' evidence before expiry",
                ]
            elif score <= 0.5:
                urgency = "medium"
                reason = (
                    f"Capability '{cap_name}' for persona '{p}' is approaching staleness "
                    f"(freshness: {score:.2f})."
                )
                actions = [
                    f"Plan re-certification for '{cap_name}' within {record.time_until_stale(now):.0f}s",
                ]
            else:
                continue  # No trigger needed

            trigger = RecertificationTrigger(
                persona=p,
                trigger_reason=reason,
                capabilities_affected=[cap_name],
                urgency=urgency,
                recommended_actions=actions,
            )
            triggers.append(trigger)
            self._triggers.append(trigger)

        return triggers

    def check_all_triggers(self) -> dict[str, list[RecertificationTrigger]]:
        """Check triggers for all tracked personas.

        Returns:
            Dict mapping persona name to list of RecertificationTriggers.
        """
        all_triggers: dict[str, list[RecertificationTrigger]] = {}
        for persona in sorted(self._capabilities.keys()):
            triggers = self.check_triggers(persona)
            if triggers:
                all_triggers[persona] = triggers
        return all_triggers

    def get_trigger_history(
        self, persona: str | None = None
    ) -> list[RecertificationTrigger]:
        """Get trigger history, optionally filtered by persona."""
        if persona is not None:
            p = persona.strip().lower()
            return [t for t in self._triggers if t.persona == p]
        return list(self._triggers)

    def get_urgency_summary(self) -> dict[str, Any]:
        """Return summary of all triggers by urgency."""
        if not self._triggers:
            return {
                "total_triggers": 0,
                "by_urgency": {},
                "personas_affected": [],
            }

        by_urgency: dict[str, int] = {}
        personas = set()

        for trigger in self._triggers:
            by_urgency[trigger.urgency] = by_urgency.get(trigger.urgency, 0) + 1
            personas.add(trigger.persona)

        return {
            "total_triggers": len(self._triggers),
            "by_urgency": by_urgency,
            "personas_affected": sorted(personas),
        }

    def get_freshness_matrix(self) -> dict[str, dict[str, float]]:
        """Return a freshness matrix: persona → capability → freshness_score.

        Returns:
            Nested dict of freshness scores.
        """
        now = time.time()
        matrix: dict[str, dict[str, float]] = {}

        for persona, caps in sorted(self._capabilities.items()):
            matrix[persona] = {}
            for cap_name, record in sorted(caps.items()):
                matrix[persona][cap_name] = round(record.freshness_score(now), 4)

        return matrix

    def auto_register_from_doctrine(self, persona: str) -> int:
        """Auto-register capabilities from a persona's doctrine contract.

        Each permission and obligation in the doctrine becomes a tracked
        capability with default TTL.

        Args:
            persona: The persona to auto-register.

        Returns:
            Number of capabilities registered.
        """
        doctrine = self._get_doctrine()
        contract = doctrine.get_contract(persona.strip().lower())
        if contract is None:
            return 0

        count = 0
        for perm in contract.permissions:
            self.register_capability(persona, perm)
            count += 1
        for obl in contract.obligations:
            if obl not in {c.capability_name for c in self.get_all_capabilities(persona)}:
                self.register_capability(persona, obl)
                count += 1

        return count

    def remove_capability(self, persona: str, capability: str) -> bool:
        """Remove a capability from tracking.

        Returns:
            True if the capability was removed, False if it didn't exist.
        """
        p = persona.strip().lower()
        cap = capability.strip().lower()
        if p in self._capabilities and cap in self._capabilities[p]:
            del self._capabilities[p][cap]
            return True
        return False

    def clear(self) -> None:
        """Clear all capabilities, triggers, and reports."""
        self._capabilities.clear()
        self._triggers.clear()
        self._reports.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_doctrine(self) -> Any:
        """Lazy-load the OperatorDoctrine if not provided."""
        if self._doctrine is not None:
            return self._doctrine
        from hlf_mcp.persona.operator_doctrine import build_operator_doctrine

        self._doctrine = build_operator_doctrine()
        return self._doctrine
