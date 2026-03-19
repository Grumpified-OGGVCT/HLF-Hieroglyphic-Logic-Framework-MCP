from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

WitnessSeverity = Literal["info", "warning", "critical"]
WitnessRecommendedAction = Literal["observe", "review", "probation", "restrict"]
TrustState = Literal["healthy", "watched", "probation", "restricted"]


def _bounded_confidence(confidence: float) -> float:
    return max(0.0, min(float(confidence), 1.0))


def _severity_weight(severity: WitnessSeverity) -> float:
    return {
        "info": 0.2,
        "warning": 1.0,
        "critical": 2.0,
    }[severity]


@dataclass(slots=True)
class WitnessObservation:
    witness_id: str
    subject_agent_id: str
    category: str
    severity: WitnessSeverity = "warning"
    confidence: float = 1.0
    goal_id: str = ""
    session_id: str = ""
    source: str = ""
    event_ref: dict[str, str] = field(default_factory=dict)
    evidence_hash: str = ""
    recommended_action: WitnessRecommendedAction = "review"
    details: dict[str, Any] = field(default_factory=dict)
    negative: bool = True
    observed_at: float = field(default_factory=time.time)
    observation_id: str = ""

    def __post_init__(self) -> None:
        self.confidence = _bounded_confidence(self.confidence)
        if not self.evidence_hash:
            self.evidence_hash = hashlib.sha256(
                json.dumps(
                    {
                        "subject_agent_id": self.subject_agent_id,
                        "category": self.category,
                        "severity": self.severity,
                        "details": self.details,
                        "event_ref": self.event_ref,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
        if not self.observation_id:
            self.observation_id = hashlib.sha256(
                f"{self.witness_id}:{self.subject_agent_id}:{self.category}:{self.evidence_hash}:{int(self.observed_at * 1000)}".encode()
            ).hexdigest()[:16]

    def impact_score(self) -> float:
        if not self.negative or self.confidence < 0.35:
            return 0.0
        return round(_severity_weight(self.severity) * self.confidence, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "witness_id": self.witness_id,
            "subject_agent_id": self.subject_agent_id,
            "goal_id": self.goal_id,
            "session_id": self.session_id,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "source": self.source,
            "event_ref": dict(self.event_ref),
            "evidence_hash": self.evidence_hash,
            "recommended_action": self.recommended_action,
            "details": dict(self.details),
            "negative": self.negative,
            "observed_at": self.observed_at,
            "impact_score": self.impact_score(),
        }

    def render_content(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)


@dataclass(slots=True)
class TrustStateSnapshot:
    subject_agent_id: str
    trust_state: TrustState
    aggregate_score: float
    total_observations: int
    negative_observation_count: int
    corroborating_witness_count: int
    corroborating_category_count: int
    recommended_action: WitnessRecommendedAction
    last_event_ref: dict[str, str] = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    last_observed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_agent_id": self.subject_agent_id,
            "trust_state": self.trust_state,
            "aggregate_score": self.aggregate_score,
            "total_observations": self.total_observations,
            "negative_observation_count": self.negative_observation_count,
            "corroborating_witness_count": self.corroborating_witness_count,
            "corroborating_category_count": self.corroborating_category_count,
            "recommended_action": self.recommended_action,
            "last_event_ref": dict(self.last_event_ref),
            "rationale": list(self.rationale),
            "last_observed_at": self.last_observed_at,
        }


class WitnessGovernance:
    def __init__(self) -> None:
        self._observations: dict[str, list[WitnessObservation]] = {}
        self._snapshots: dict[str, TrustStateSnapshot] = {}

    def record_observation(self, observation: WitnessObservation) -> TrustStateSnapshot:
        bucket = self._observations.setdefault(observation.subject_agent_id, [])
        bucket.append(observation)
        snapshot = self._recompute(observation.subject_agent_id)
        self._snapshots[observation.subject_agent_id] = snapshot
        return snapshot

    def get_snapshot(self, subject_agent_id: str) -> TrustStateSnapshot | None:
        return self._snapshots.get(subject_agent_id)

    def recent_observations(self, subject_agent_id: str, limit: int = 10) -> list[dict[str, Any]]:
        observations = self._observations.get(subject_agent_id, [])
        return [observation.to_dict() for observation in observations[-limit:]][::-1]

    def list_snapshots(self, trust_state: str | None = None) -> list[dict[str, Any]]:
        snapshots = [snapshot for snapshot in self._snapshots.values()]
        if trust_state:
            snapshots = [snapshot for snapshot in snapshots if snapshot.trust_state == trust_state]
        severity_order = {"restricted": 3, "probation": 2, "watched": 1, "healthy": 0}
        snapshots.sort(
            key=lambda snapshot: (
                severity_order.get(snapshot.trust_state, -1),
                snapshot.last_observed_at,
            ),
            reverse=True,
        )
        return [snapshot.to_dict() for snapshot in snapshots]

    def status_snapshot(self, subject_agent_id: str | None = None) -> dict[str, Any] | None:
        if subject_agent_id:
            snapshot = self.get_snapshot(subject_agent_id)
            if snapshot is None:
                return None
            return {
                "subject": snapshot.to_dict(),
                "recent_observations": self.recent_observations(subject_agent_id),
            }

        subjects = self.list_snapshots()
        counts = {state: 0 for state in ("healthy", "watched", "probation", "restricted")}
        for subject in subjects:
            counts[str(subject["trust_state"])] += 1
        return {
            "summary": {
                "total_subjects": len(subjects),
                "healthy": counts["healthy"],
                "watched": counts["watched"],
                "probation": counts["probation"],
                "restricted": counts["restricted"],
            },
            "subjects": subjects,
        }

    def _recompute(self, subject_agent_id: str) -> TrustStateSnapshot:
        observations = self._observations.get(subject_agent_id, [])
        scored = [observation for observation in observations if observation.impact_score() > 0.0]
        aggregate_score = round(sum(observation.impact_score() for observation in scored), 3)
        corroborating_witness_count = len({observation.witness_id for observation in scored})
        corroborating_category_count = len({observation.category for observation in scored})

        trust_state: TrustState = "healthy"
        recommended_action: WitnessRecommendedAction = "observe"
        rationale: list[str] = []

        if (
            aggregate_score >= 4.0
            and len(scored) >= 3
            and corroborating_witness_count >= 2
            and corroborating_category_count >= 2
        ):
            trust_state = "restricted"
            recommended_action = "restrict"
            rationale.append(
                "Multiple corroborating negative observations justify temporary restriction rather than silent continuation."
            )
        elif (
            aggregate_score >= 1.5
            and len(scored) >= 2
            and (corroborating_witness_count >= 2 or corroborating_category_count >= 2)
        ):
            trust_state = "probation"
            recommended_action = "probation"
            rationale.append(
                "Repeated negative evidence crossed the probation threshold and should constrain downstream routing or approval behavior."
            )
        elif aggregate_score >= 0.75:
            trust_state = "watched"
            recommended_action = "review"
            rationale.append(
                "Evidence is strong enough to keep the subject under watch, but not yet strong enough for probation."
            )
        else:
            rationale.append("Observed evidence has not crossed a trust degradation threshold.")

        if observations and not scored:
            rationale.append(
                "Only low-confidence or non-negative observations are present, so trust remains healthy."
            )

        last_observation = observations[-1] if observations else None
        return TrustStateSnapshot(
            subject_agent_id=subject_agent_id,
            trust_state=trust_state,
            aggregate_score=aggregate_score,
            total_observations=len(observations),
            negative_observation_count=len(scored),
            corroborating_witness_count=corroborating_witness_count,
            corroborating_category_count=corroborating_category_count,
            recommended_action=recommended_action,
            last_event_ref=dict(last_observation.event_ref) if last_observation else {},
            rationale=rationale,
            last_observed_at=last_observation.observed_at if last_observation else 0.0,
        )
