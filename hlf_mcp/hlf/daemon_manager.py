from __future__ import annotations

from collections import Counter
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DaemonStatus(Enum):
    STOPPED = "stopped"
    RUNNING = "running"


@dataclass(slots=True)
class DaemonAuditEntry:
    category: str
    kind: str
    action: str
    status: str
    severity: str
    source: str
    subject_id: str
    goal_id: str
    timestamp: str
    event_ref: dict[str, Any]
    audit_trace_id: str
    is_alert: bool
    operator_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "kind": self.kind,
            "action": self.action,
            "status": self.status,
            "severity": self.severity,
            "source": self.source,
            "subject_id": self.subject_id,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
            "event_ref": dict(self.event_ref),
            "audit_trace_id": self.audit_trace_id,
            "is_alert": self.is_alert,
            "operator_summary": self.operator_summary,
        }


@dataclass(slots=True)
class SentinelAlertEntry:
    pattern: str
    category: str
    severity: str
    source: str
    subject_id: str
    goal_id: str
    timestamp: str
    event_ref: dict[str, Any]
    audit_trace_id: str
    recommendation: str
    evidence: dict[str, Any]
    operator_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "category": self.category,
            "severity": self.severity,
            "source": self.source,
            "subject_id": self.subject_id,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
            "event_ref": dict(self.event_ref),
            "audit_trace_id": self.audit_trace_id,
            "recommendation": self.recommendation,
            "evidence": dict(self.evidence),
            "operator_summary": self.operator_summary,
        }


@dataclass(slots=True)
class ScribeEntry:
    timestamp: str
    event_type: str
    source: str
    severity: str
    subject_id: str
    goal_id: str
    token_count: int
    prose: str
    related_event_ref: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "source": self.source,
            "severity": self.severity,
            "subject_id": self.subject_id,
            "goal_id": self.goal_id,
            "token_count": self.token_count,
            "prose": self.prose,
            "related_event_ref": dict(self.related_event_ref),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class DaemonBusEvent:
    source: str
    event_type: str
    severity: str
    timestamp: str
    subject_id: str
    goal_id: str
    related_event_ref: dict[str, Any]
    data: dict[str, Any]
    operator_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "subject_id": self.subject_id,
            "goal_id": self.goal_id,
            "related_event_ref": dict(self.related_event_ref),
            "data": dict(self.data),
            "operator_summary": self.operator_summary,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _severity_rank(severity: str) -> int:
    normalized = str(severity or "info").strip().lower()
    return {"info": 0, "warning": 1, "critical": 2}.get(normalized, 0)


def _clamp_scribe_prose(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(0, limit - 3)].rstrip()}..."


def _classify_event(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "").strip()
    if kind == "routing_decision":
        return "routing"
    if kind == "model_catalog_sync":
        return "routing"
    if kind == "align_verdict":
        return "security"
    if kind in {"formal_verification", "verification_result"}:
        return "verification"
    if kind == "pointer_resolution":
        return "pointer"
    if kind == "approval_transition":
        return "approval"
    if kind == "witness_observation":
        return "witness"
    if kind == "memory_governance":
        return "memory"
    if kind == "entropy_anchor":
        return "entropy"
    if kind == "dream_cycle":
        return "dream"
    if kind == "proposal_lane":
        return "proposal"
    return "governance"


def _summarize_event(event: dict[str, Any]) -> str:
    kind = str(event.get("kind") or "event").strip() or "event"
    action = str(event.get("action") or "recorded").strip() or "recorded"
    status = str(event.get("status") or "unknown").strip() or "unknown"
    severity = str(event.get("severity") or "unknown").strip() or "unknown"
    subject_id = str(event.get("subject_id") or "").strip()
    details = event.get("details") if isinstance(event.get("details"), dict) else {}

    if kind == "approval_transition" and action == "approval_bypass_attempt":
        domain = str(details.get("domain") or "capsule_approval").strip() or "capsule_approval"
        reason_code = str(details.get("reason_code") or "unknown_reason").strip() or "unknown_reason"
        request_id = str(details.get("request_id") or "").strip()
        capsule_id = str(details.get("capsule_id") or "").strip()
        tool_name = str(details.get("tool_name") or details.get("name") or "").strip()
        operator = str(details.get("operator") or "").strip()
        if domain == "forged_tool_approval":
            target = tool_name or subject_id or "unknown-tool"
            text = f"Blocked forged-tool approval bypass attempt for '{target}' with reason '{reason_code}'."
        else:
            target = request_id or capsule_id or subject_id or "unknown-request"
            text = f"Blocked capsule approval bypass attempt for '{target}' with reason '{reason_code}'."
        if operator:
            return f"{text[:-1]} by operator '{operator}'."
        return text

    if kind == "approval_transition":
        request_id = str(details.get("request_id") or "").strip()
        target = request_id or subject_id or "unknown-request"
        return f"Approval lifecycle recorded action '{action}' for '{target}' with status '{status}'."

    if kind == "align_verdict":
        decisive_action = str(details.get("action") or details.get("decisive_rule_action") or "review")
        return (
            f"ALIGN governance returned status '{status}' with action '{decisive_action}' "
            f"for subject '{subject_id or 'unknown'}'."
        )

    if kind == "routing_decision":
        selected_lane = str(details.get("selected_lane") or details.get("routing_lane") or "governed")
        model = str(details.get("selected_model") or details.get("model") or "")
        model_text = f" using model '{model}'" if model else ""
        return (
            f"Governed routing recorded status '{status}' on lane '{selected_lane}'{model_text} "
            f"for subject '{subject_id or 'unknown'}'."
        )

    if kind == "pointer_resolution":
        admitted = bool(details.get("admitted"))
        purpose = str(details.get("purpose") or "execution")
        trust_mode = str(details.get("trust_mode") or "enforce")
        reason = str(details.get("reason") or "").strip()
        summary = (
            f"Pointer resolution {'admitted' if admitted else 'blocked'} pointer use for purpose '{purpose}' "
            f"with trust mode '{trust_mode}' on subject '{subject_id or 'unknown'}'."
        )
        if reason:
            summary = f"{summary[:-1]} Reason: {reason}."
        return summary

    if kind in {"formal_verification", "verification_result"}:
        report = details.get("report") if isinstance(details.get("report"), dict) else {}
        failed_count = int(report.get("failed_count") or 0)
        unknown_count = int(report.get("unknown_count") or 0)
        return (
            f"Formal verification recorded status '{status}' with {failed_count} failed and "
            f"{unknown_count} unknown proof result(s) for subject '{subject_id or 'unknown'}'."
        )

    if kind == "witness_observation":
        observation = details.get("observation") if isinstance(details.get("observation"), dict) else {}
        category = str(observation.get("category") or details.get("category") or "witness_observation")
        return (
            f"Witness governance recorded category '{category}' at severity '{severity}' "
            f"for '{subject_id or 'unknown'}'."
        )

    if kind == "memory_governance":
        if action == "recall_governed_evidence":
            result_count = int(details.get("result_count") or 0)
            entry_kinds = [str(item) for item in (details.get("entry_kinds") or []) if str(item)]
            kinds_text = ", ".join(entry_kinds) if entry_kinds else "governed evidence"
            return (
                f"Governed recall returned {result_count} result(s) across {kinds_text} "
                f"for query '{details.get('query') or subject_id or 'unknown'}'."
            )
        state = str(details.get("state") or "unknown")
        reason = str(details.get("reason") or "").strip()
        suffix = f" Reason: {reason}." if reason else "."
        return (
            f"Memory governance applied state '{state}' with status '{status}' "
            f"for subject '{subject_id or 'unknown'}'.{suffix}"
        ).replace("..", ".")

    if kind == "entropy_anchor":
        action_name = str(details.get("policy_action") or "observe")
        score = details.get("similarity_score")
        threshold = details.get("threshold")
        return (
            f"Entropy-anchor status is '{status}' with policy action '{action_name}'"
            + (
                f" at similarity {score} against threshold {threshold}."
                if score is not None and threshold is not None
                else "."
            )
        )

    return f"Governance event '{kind}' recorded action '{action}' with status '{status}' and severity '{severity}'."


@dataclass(slots=True)
class DaemonManager:
    max_entries: int = 250
    scribe_token_budget: int = 4096
    status: DaemonStatus = DaemonStatus.RUNNING
    _audit_trail: deque[DaemonAuditEntry] = field(default_factory=deque)
    _sentinel_alerts: deque[SentinelAlertEntry] = field(default_factory=deque)
    _scribe_entries: deque[ScribeEntry] = field(default_factory=deque)
    _daemon_events: deque[DaemonBusEvent] = field(default_factory=deque)
    _scribe_tokens_used: int = 0

    def __post_init__(self) -> None:
        self.max_entries = max(25, int(self.max_entries))
        self.scribe_token_budget = max(256, int(self.scribe_token_budget))
        self._audit_trail = deque(self._audit_trail, maxlen=self.max_entries)
        self._sentinel_alerts = deque(self._sentinel_alerts, maxlen=self.max_entries)
        self._scribe_entries = deque(self._scribe_entries, maxlen=self.max_entries)
        self._daemon_events = deque(self._daemon_events, maxlen=self.max_entries)

    def _record_daemon_event(
        self,
        *,
        source: str,
        event_type: str,
        severity: str,
        timestamp: str,
        subject_id: str,
        goal_id: str,
        related_event_ref: dict[str, Any] | None,
        data: dict[str, Any] | None,
        operator_summary: str,
    ) -> dict[str, Any]:
        event = DaemonBusEvent(
            source=source,
            event_type=event_type,
            severity=str(severity or "info"),
            timestamp=timestamp,
            subject_id=subject_id,
            goal_id=goal_id,
            related_event_ref=dict(related_event_ref or {}),
            data=dict(data or {}),
            operator_summary=operator_summary,
        )
        self._daemon_events.append(event)
        return event.to_dict()

    def _record_scribe_entry(
        self,
        *,
        timestamp: str,
        event_type: str,
        source: str,
        severity: str,
        subject_id: str,
        goal_id: str,
        related_event_ref: dict[str, Any] | None,
        prose: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_prose = _clamp_scribe_prose(prose)
        token_count = _estimate_tokens(normalized_prose)
        if self._scribe_tokens_used + token_count > self.scribe_token_budget:
            normalized_prose = _clamp_scribe_prose(
                f"[budget-constrained] {normalized_prose}",
                limit=140,
            )
            token_count = _estimate_tokens(normalized_prose)
        entry = ScribeEntry(
            timestamp=timestamp,
            event_type=event_type,
            source=source,
            severity=str(severity or "info"),
            subject_id=subject_id,
            goal_id=goal_id,
            token_count=token_count,
            prose=normalized_prose,
            related_event_ref=dict(related_event_ref or {}),
            metadata=dict(metadata or {}),
        )
        self._scribe_entries.append(entry)
        self._scribe_tokens_used = min(
            self.scribe_token_budget,
            self._scribe_tokens_used + token_count,
        )
        return entry.to_dict()

    def _derive_sentinel_alerts(
        self,
        event: dict[str, Any],
        entry: DaemonAuditEntry,
    ) -> list[SentinelAlertEntry]:
        kind = entry.kind
        action = entry.action
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        alerts: list[SentinelAlertEntry] = []

        def add_alert(
            pattern: str,
            *,
            severity: str,
            recommendation: str,
            evidence: dict[str, Any] | None = None,
            operator_summary: str | None = None,
        ) -> None:
            alerts.append(
                SentinelAlertEntry(
                    pattern=pattern,
                    category=entry.category,
                    severity=str(severity or entry.severity or "warning"),
                    source=entry.source,
                    subject_id=entry.subject_id,
                    goal_id=entry.goal_id,
                    timestamp=entry.timestamp,
                    event_ref=dict(entry.event_ref),
                    audit_trace_id=entry.audit_trace_id,
                    recommendation=recommendation,
                    evidence=dict(evidence or {}),
                    operator_summary=operator_summary or entry.operator_summary,
                )
            )

        if kind == "approval_transition" and action == "approval_bypass_attempt":
            add_alert(
                "approval_bypass_attempt",
                severity="critical",
                recommendation="Maintain fail-closed approval boundaries and require explicit operator review.",
                evidence={
                    "reason_code": details.get("reason_code"),
                    "request_id": details.get("request_id"),
                    "domain": details.get("domain"),
                },
            )

        elif kind == "align_verdict":
            decisive_action = str(details.get("action") or details.get("decisive_rule_action") or "ALLOW")
            if entry.status in {"blocked", "error"} or decisive_action in {
                "DROP",
                "DROP_AND_QUARANTINE",
                "ROUTE_TO_HUMAN_APPROVAL",
                "QUARANTINE",
            }:
                add_alert(
                    "align_intervention",
                    severity="critical" if decisive_action in {"DROP", "DROP_AND_QUARANTINE", "QUARANTINE"} else "warning",
                    recommendation="Review ALIGN evidence and keep model or tool execution behind deterministic governance gates.",
                    evidence={
                        "decisive_action": decisive_action,
                        "status": entry.status,
                    },
                )

        elif kind == "pointer_resolution":
            admitted = bool(details.get("admitted"))
            governance_status = str(details.get("governance_status") or "unknown")
            freshness_status = str(details.get("freshness_status") or "unknown")
            reason = str(details.get("reason") or "").strip()
            if not admitted or entry.status in {"blocked", "error", "warning"}:
                derived_severity = "critical" if governance_status in {"revoked", "restricted", "tombstoned"} else "warning"
                add_alert(
                    "pointer_resolution_denied",
                    severity=derived_severity,
                    recommendation="Review pointer freshness, revocation state, and capsule trust mode before reusing this memory reference.",
                    evidence={
                        "governance_status": governance_status,
                        "freshness_status": freshness_status,
                        "reason": reason,
                        "trust_mode": details.get("trust_mode"),
                    },
                )

        elif kind == "witness_observation":
            observation = details.get("observation") if isinstance(details.get("observation"), dict) else {}
            trust_state = details.get("trust_state") if isinstance(details.get("trust_state"), dict) else {}
            category = str(observation.get("category") or details.get("category") or "witness_observation")
            negative = bool(observation.get("negative", True))
            effective_trust_state = str(trust_state.get("trust_state") or details.get("trust_state") or "")
            if effective_trust_state == "restricted":
                add_alert(
                    "trust_state_restricted",
                    severity="critical",
                    recommendation="Keep the subject in fail-closed review until operator trust is re-established.",
                    evidence={"category": category, "trust_state": effective_trust_state},
                )
            elif negative and entry.status in {"warning", "blocked", "error"}:
                add_alert(
                    f"witness_{category}",
                    severity="critical" if _severity_rank(entry.severity) >= _severity_rank("critical") else "warning",
                    recommendation="Review witness evidence and apply the matching trust-state consequences before broader execution.",
                    evidence={"category": category, "trust_state": effective_trust_state},
                )

        elif kind == "memory_governance":
            state = str(details.get("state") or "unknown")
            if action != "recall_governed_evidence" and (
                entry.status in {"warning", "blocked", "error"}
                or state in {"restricted", "revoked", "tombstoned"}
            ):
                add_alert(
                    "memory_governance_intervention",
                    severity="critical" if state in {"revoked", "restricted", "tombstoned"} else "warning",
                    recommendation="Confirm that governed memory state changes propagate to recall and execution boundaries.",
                    evidence={"state": state, "reason": details.get("reason")},
                )

        elif kind == "routing_decision" and entry.status in {"warning", "blocked", "error"}:
            selected_lane = str(details.get("selected_lane") or details.get("routing_lane") or "governed")
            add_alert(
                "governed_route_degraded" if entry.status != "blocked" else "governed_route_blocked",
                severity="critical" if entry.status == "blocked" else "warning",
                recommendation="Review routing evidence, trust state, and fallback policy before widening execution lanes.",
                evidence={"selected_lane": selected_lane, "model": details.get("selected_model")},
            )

        elif kind in {"formal_verification", "verification_result"}:
            report = details.get("report") if isinstance(details.get("report"), dict) else {}
            failed_count = int(report.get("failed_count") or 0)
            unknown_count = int(report.get("unknown_count") or 0)
            if failed_count > 0 or entry.status in {"warning", "blocked", "error"}:
                add_alert(
                    "verification_failure",
                    severity="critical" if failed_count > 0 and entry.status == "blocked" else "warning",
                    recommendation="Do not promote verification-dependent changes until failed and unknown proof outcomes are resolved.",
                    evidence={"failed_count": failed_count, "unknown_count": unknown_count},
                )

        elif kind == "entropy_anchor" and entry.status in {"warning", "blocked", "error"}:
            add_alert(
                "entropy_anchor_drift",
                severity="critical" if entry.status == "blocked" else "warning",
                recommendation="Investigate semantic drift before allowing the affected intent into broader execution lanes.",
                evidence={
                    "policy_action": details.get("policy_action"),
                    "similarity_score": details.get("similarity_score"),
                    "threshold": details.get("threshold"),
                },
            )

        if not alerts and entry.is_alert:
            add_alert(
                f"{entry.category}_attention",
                severity=entry.severity or "warning",
                recommendation="Review the recorded governance event and confirm that the current guardrails remain sufficient.",
            )
        return alerts

    def observe_governance_event(
        self,
        event: dict[str, Any],
        *,
        audit_trace_id: str = "",
    ) -> dict[str, Any]:
        if self.status != DaemonStatus.RUNNING:
            return {"status": self.status.value, "entry": None}

        status = str(event.get("status") or "")
        severity = str(event.get("severity") or "")
        entry = DaemonAuditEntry(
            category=_classify_event(event),
            kind=str(event.get("kind") or ""),
            action=str(event.get("action") or ""),
            status=status,
            severity=severity,
            source=str(event.get("source") or ""),
            subject_id=str(event.get("subject_id") or ""),
            goal_id=str(event.get("goal_id") or ""),
            timestamp=str(event.get("timestamp") or ""),
            event_ref=dict(event.get("event_ref") or {}),
            audit_trace_id=audit_trace_id,
            is_alert=status in {"warning", "error", "blocked"} or severity in {"warning", "critical"},
            operator_summary=_summarize_event(event),
        )
        self._audit_trail.append(entry)
        daemon_events = [
            self._record_daemon_event(
                source="governance",
                event_type=entry.kind or "governance_event",
                severity=severity or ("warning" if entry.is_alert else "info"),
                timestamp=entry.timestamp,
                subject_id=entry.subject_id,
                goal_id=entry.goal_id,
                related_event_ref=entry.event_ref,
                data={
                    "category": entry.category,
                    "action": entry.action,
                    "status": entry.status,
                },
                operator_summary=entry.operator_summary,
            )
        ]
        sentinel_alerts = []
        for alert in self._derive_sentinel_alerts(event, entry):
            self._sentinel_alerts.append(alert)
            sentinel_payload = alert.to_dict()
            sentinel_alerts.append(sentinel_payload)
            daemon_events.append(
                self._record_daemon_event(
                    source="sentinel",
                    event_type="alert",
                    severity=alert.severity,
                    timestamp=alert.timestamp,
                    subject_id=alert.subject_id,
                    goal_id=alert.goal_id,
                    related_event_ref=alert.event_ref,
                    data={
                        "pattern": alert.pattern,
                        "category": alert.category,
                        "recommendation": alert.recommendation,
                    },
                    operator_summary=alert.operator_summary,
                )
            )

        scribe_entries = [
            self._record_scribe_entry(
                timestamp=entry.timestamp,
                event_type=entry.kind or "governance_event",
                source="governance",
                severity=entry.severity or ("warning" if entry.is_alert else "info"),
                subject_id=entry.subject_id,
                goal_id=entry.goal_id,
                related_event_ref=entry.event_ref,
                prose=entry.operator_summary,
                metadata={
                    "category": entry.category,
                    "action": entry.action,
                    "status": entry.status,
                },
            )
        ]
        for alert in sentinel_alerts:
            scribe_entries.append(
                self._record_scribe_entry(
                    timestamp=str(alert.get("timestamp") or entry.timestamp),
                    event_type=f"sentinel_{alert.get('pattern') or 'alert'}",
                    source="sentinel",
                    severity=str(alert.get("severity") or "warning"),
                    subject_id=str(alert.get("subject_id") or ""),
                    goal_id=str(alert.get("goal_id") or ""),
                    related_event_ref=alert.get("event_ref") if isinstance(alert.get("event_ref"), dict) else {},
                    prose=str(alert.get("operator_summary") or entry.operator_summary),
                    metadata={
                        "pattern": alert.get("pattern"),
                        "category": alert.get("category"),
                        "recommendation": alert.get("recommendation"),
                    },
                )
            )

        return {
            "status": "ok",
            "entry": entry.to_dict(),
            "sentinel_alerts": sentinel_alerts,
            "scribe_entries": scribe_entries,
            "daemon_events": daemon_events,
        }

    def get_audit_trail(self, *, limit: int = 50, subject_id: str | None = None) -> list[dict[str, Any]]:
        size = max(1, min(limit, self.max_entries))
        entries = list(self._audit_trail)
        entries.reverse()
        if subject_id:
            entries = [entry for entry in entries if entry.subject_id == subject_id]
        return [entry.to_dict() for entry in entries[:size]]

    def get_alerts(
        self,
        *,
        limit: int = 50,
        severity: str | None = None,
        pattern: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        entries = list(reversed(self._sentinel_alerts))
        if severity:
            entries = [entry for entry in entries if entry.severity == severity]
        if pattern:
            entries = [entry for entry in entries if entry.pattern == pattern]
        if subject_id:
            entries = [entry for entry in entries if entry.subject_id == subject_id]
        return [entry.to_dict() for entry in entries[: max(1, min(limit, self.max_entries))]]

    def get_scribe_entries(
        self,
        *,
        limit: int = 50,
        source: str | None = None,
        event_type: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        entries = list(reversed(self._scribe_entries))
        if source:
            entries = [entry for entry in entries if entry.source == source]
        if event_type:
            entries = [entry for entry in entries if entry.event_type == event_type]
        if subject_id:
            entries = [entry for entry in entries if entry.subject_id == subject_id]
        return [entry.to_dict() for entry in entries[: max(1, min(limit, self.max_entries))]]

    def get_daemon_events(
        self,
        *,
        limit: int = 50,
        source: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        entries = list(reversed(self._daemon_events))
        if source:
            entries = [entry for entry in entries if entry.source == source]
        if event_type:
            entries = [entry for entry in entries if entry.event_type == event_type]
        return [entry.to_dict() for entry in entries[: max(1, min(limit, self.max_entries))]]

    def status_snapshot(self) -> dict[str, Any]:
        entries = list(self._audit_trail)
        category_counts: dict[str, int] = {}
        blocked_count = 0
        critical_count = 0
        pressured_subjects: set[str] = set()
        for entry in entries:
            category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
        alert_entries = list(self._sentinel_alerts)
        for alert in alert_entries:
            if alert.severity == "critical":
                critical_count += 1
            if alert.subject_id:
                pressured_subjects.add(alert.subject_id)
            if any(token in alert.pattern for token in {"blocked", "denied", "restricted", "intervention"}):
                blocked_count += 1
        alert_count = len(alert_entries)
        alert_pattern_counts = Counter(alert.pattern for alert in alert_entries)
        alert_subjects = sorted({alert.subject_id for alert in alert_entries if alert.subject_id})
        scribe_source_counts = Counter(entry.source for entry in self._scribe_entries)
        daemon_source_counts = Counter(event.source for event in self._daemon_events)
        daemon_type_counts = Counter(event.event_type for event in self._daemon_events)
        return {
            "manager_status": self.status.value,
            "entry_count": len(entries),
            "alert_count": alert_count,
            "category_counts": category_counts,
            "anomaly_summary": {
                "alert_count": alert_count,
                "blocked_count": blocked_count,
                "critical_count": critical_count,
                "pressured_subject_count": len(pressured_subjects),
                "pressured_subjects": sorted(pressured_subjects),
            },
            "sentinel_summary": {
                "alert_count": alert_count,
                "critical_count": sum(1 for alert in alert_entries if alert.severity == "critical"),
                "warning_count": sum(1 for alert in alert_entries if alert.severity == "warning"),
                "pattern_counts": dict(alert_pattern_counts),
                "subject_count": len(alert_subjects),
                "subjects": alert_subjects,
            },
            "scribe_summary": {
                "entry_count": len(self._scribe_entries),
                "token_budget": self.scribe_token_budget,
                "tokens_used": self._scribe_tokens_used,
                "tokens_remaining": max(0, self.scribe_token_budget - self._scribe_tokens_used),
                "source_counts": dict(scribe_source_counts),
            },
            "daemon_bus_summary": {
                "event_count": len(self._daemon_events),
                "source_counts": dict(daemon_source_counts),
                "event_type_counts": dict(daemon_type_counts),
            },
        }
