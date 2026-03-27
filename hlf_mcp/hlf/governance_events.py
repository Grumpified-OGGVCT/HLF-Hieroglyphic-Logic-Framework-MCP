from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence, cast

GovernanceEventKind = Literal[
    "routing_decision",
    "model_catalog_sync",
    "align_verdict",
    "capsule_verdict",
    "pointer_resolution",
    "memory_governance",
    "memory_store",
    "validated_solution_capture",
    "entropy_anchor",
    "witness_observation",
    "verification_result",
    "formal_verification",
    "approval_transition",
    "dream_cycle",
    "proposal_lane",
]

GovernanceSeverity = Literal["info", "warning", "critical"]
GovernanceStatus = Literal["ok", "blocked", "warning", "error", "pending"]


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _event_id(seed_payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(seed_payload).encode("utf-8")).hexdigest()[:16]


def governance_event_ref(
    *, kind: GovernanceEventKind, event_id: str, trace_id: str = ""
) -> dict[str, str]:
    return GovernanceEventRef(kind=kind, event_id=event_id, trace_id=trace_id).to_dict()


def normalize_governance_ref(
    value: GovernanceEventRef | Mapping[str, Any] | None,
    *,
    default_kind: GovernanceEventKind | None = None,
) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, GovernanceEventRef):
        return value.to_dict()
    kind_raw = str(value.get("kind") or default_kind or "").strip()
    event_id = str(value.get("event_id") or value.get("id") or "").strip()
    trace_id = str(value.get("trace_id") or "").strip()
    if not event_id and trace_id:
        event_id = trace_id[:16]
    if not kind_raw or not event_id:
        return None
    return governance_event_ref(
        kind=cast(GovernanceEventKind, kind_raw),
        event_id=event_id,
        trace_id=trace_id,
    )


def normalize_related_refs(
    values: Sequence[GovernanceEventRef | Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    if not values:
        return normalized
    for value in values:
        ref = normalize_governance_ref(value)
        if ref is not None:
            normalized.append(ref)
    return normalized


@dataclass(slots=True)
class GovernanceEventRef:
    kind: GovernanceEventKind
    event_id: str
    trace_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "event_id": self.event_id,
            "trace_id": self.trace_id,
        }


@dataclass(slots=True)
class GovernanceEvent:
    kind: GovernanceEventKind
    source: str
    action: str
    status: GovernanceStatus = "ok"
    severity: GovernanceSeverity = "info"
    subject_id: str = ""
    goal_id: str = ""
    session_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    related_refs: list[dict[str, str]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""
    trace_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = _event_id(
                {
                    "kind": self.kind,
                    "source": self.source,
                    "action": self.action,
                    "status": self.status,
                    "severity": self.severity,
                    "subject_id": self.subject_id,
                    "goal_id": self.goal_id,
                    "session_id": self.session_id,
                    "details": self.details,
                    "related_refs": self.related_refs,
                    "timestamp_ms": int(self.timestamp * 1000),
                }
            )

    @property
    def event_ref(self) -> GovernanceEventRef:
        return GovernanceEventRef(kind=self.kind, event_id=self.event_id, trace_id=self.trace_id)

    def audit_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "event_id": self.event_id,
            "source": self.source,
            "action": self.action,
            "status": self.status,
            "severity": self.severity,
            "subject_id": self.subject_id,
            "goal_id": self.goal_id,
            "session_id": self.session_id,
            "details": self.details,
            "related_refs": self.related_refs,
            "timestamp": self.timestamp,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.audit_payload()
        payload["trace_id"] = self.trace_id
        payload["event_ref"] = self.event_ref.to_dict()
        return payload
