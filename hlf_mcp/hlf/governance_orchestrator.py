from __future__ import annotations

import time
import typing
from collections import deque
from typing import Any

from hlf_mcp.hlf.governance_event_log import GovernanceEventLog
from hlf_mcp.hlf.governance_events import (
    GovernanceEvent,
    GovernanceEventKind,
    GovernanceEventRef,
    GovernanceSeverity,
    GovernanceStatus,
    normalize_governance_ref,
    normalize_related_refs,
)
from hlf_mcp.hlf.witness_governance import (
    WitnessGovernance,
    WitnessObservation,
    WitnessRecommendedAction,
)

if typing.TYPE_CHECKING:
    from hlf_mcp.hlf.audit_chain import AuditChain
    from hlf_mcp.hlf.approval_ledger import ApprovalLedger
    from hlf_mcp.hlf.daemon_manager import DaemonManager
    from hlf_mcp.rag.memory import RAGMemory


class GovernanceOrchestrator:
    """Packaged governance orchestration hub.

    Centralizes event typing, trace references, and integration points
    for memory, runtime, routing, audit, and witness decisions.
    """

    def __init__(
        self,
        *,
        audit_chain: AuditChain,
        daemon_manager: DaemonManager,
        witness_governance: WitnessGovernance,
        memory_store: RAGMemory,
        approval_ledger: ApprovalLedger,
        event_log: GovernanceEventLog | None = None,
        max_events: int = 250,
    ) -> None:
        self.audit_chain = audit_chain
        self.daemon_manager = daemon_manager
        self.witness_governance = witness_governance
        self.memory_store = memory_store
        self.approval_ledger = approval_ledger
        self.event_log = event_log
        self.governance_events: deque[dict[str, Any]] = deque(maxlen=max(max_events, 1))

    # ── Anchor stubs (wired by server context) ────────────────────────────────

    def _memory_anchor(self, entry: dict[str, Any]) -> None:
        """Index a log entry into RAGMemory for governed recall."""
        if self.event_log is not None:
            self.event_log.wire_memory_anchor(self._do_memory_anchor)

    def _do_memory_anchor(self, entry: dict[str, Any]) -> None:
        """Concrete memory anchor: store event summary in RAGMemory."""
        try:
            summary = entry.get("summary", "governance event")
            self.memory_store.store(
                summary,
                topic="hlf_governance_event_log",
                provenance=entry.get("source", "governance"),
                tags=["governance", entry.get("event_type", "event"), entry.get("severity", "info")],
                metadata={
                    "trace_ref": entry.get("trace_ref"),
                    "content_hash": entry.get("content_hash"),
                    "timestamp_ns": entry.get("timestamp_ns"),
                },
            )
        except Exception:
            # Memory anchor is best-effort; never block governance
            pass

    def _runtime_anchor(self, entry: dict[str, Any]) -> None:
        """Bind a log entry to the runtime trace context."""
        if self.event_log is not None:
            self.event_log.wire_runtime_anchor(self._do_runtime_anchor)

    def _do_runtime_anchor(self, entry: dict[str, Any]) -> None:
        """Concrete runtime anchor: append trace ref to runtime session state if available."""
        # This stub is designed to be wired to hlf_mcp.hlf.runtime.HLFRuntime
        # when the server context provides a runtime instance.  The runtime
        # is responsible for maintaining session-scoped trace stacks.
        trace_ref = entry.get("trace_ref")
        if trace_ref:
            # Store in a well-known key that runtime can pick up
            entry.setdefault("runtime_bound", True)

    # ── Event emission ────────────────────────────────────────────────────────

    def emit_governance_event(
        self,
        *,
        kind: GovernanceEventKind,
        source: str,
        action: str,
        status: GovernanceStatus = "ok",
        severity: GovernanceSeverity = "info",
        subject_id: str = "",
        goal_id: str = "",
        session_id: str = "",
        details: dict[str, Any] | None = None,
        related_refs: list[dict[str, str]] | None = None,
        agent_role: str = "governance_spine",
        confidence_score: float = 1.0,
        anomaly_score: float = 0.0,
        token_cost: int = 0,
    ) -> dict[str, Any]:
        """Emit a governance event to audit chain, daemon manager, and local buffer."""
        event = GovernanceEvent(
            kind=kind,
            source=source,
            action=action,
            status=status,
            severity=severity,
            subject_id=subject_id,
            goal_id=goal_id,
            session_id=session_id,
            details=details or {},
            related_refs=normalize_related_refs(related_refs),
        )
        audit = self.audit_chain.log_governance_event(
            event,
            agent_role=agent_role,
            goal_id=goal_id,
            confidence_score=confidence_score,
            anomaly_score=anomaly_score,
            token_cost=token_cost,
        )
        event_record = event.to_dict()
        self.governance_events.append(event_record)
        self.daemon_manager.observe_governance_event(
            event_record,
            audit_trace_id=str(audit.get("trace_id") or ""),
        )
        if self.event_log is not None:
            self.event_log.append(event_record)
        return {"event": event_record, "audit": audit, "event_ref": event_record["event_ref"]}


    # ── Event queries ─────────────────────────────────────────────────────────

    def recent_governance_events(
        self,
        limit: int = 20,
        *,
        kind: str | None = None,
        subject_id: str | None = None,
    ) -> list[dict[str, Any]]:
        size = max(1, min(limit, 250))
        events = list(self.governance_events)
        events.reverse()
        if kind:
            events = [event for event in events if event.get("kind") == kind]
        if subject_id:
            events = [event for event in events if event.get("subject_id") == subject_id]
        return events[:size]

    def get_governance_event(
        self,
        *,
        event_id: str | None = None,
        trace_id: str | None = None,
        event_ref: GovernanceEventRef | dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_ref = normalize_governance_ref(event_ref)
        effective_event_id = str(event_id or (normalized_ref or {}).get("event_id") or "")
        effective_trace_id = str(trace_id or (normalized_ref or {}).get("trace_id") or "")
        for event in reversed(self.governance_events):
            if effective_trace_id and str(event.get("trace_id") or "") == effective_trace_id:
                return dict(event)
            if effective_event_id and str(event.get("event_id") or "") == effective_event_id:
                return dict(event)
        return None

    # ── Approval integration ─────────────────────────────────────────────────

    def list_approval_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        capsule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.approval_ledger.list_requests(
            status=status,
            limit=limit,
            capsule_id=capsule_id,
        )

    def get_approval_request(self, request_id: str) -> dict[str, Any] | None:
        request = self.approval_ledger.get_request(request_id)
        if request is None:
            return None
        return request.to_dict()

    def list_approval_events(self, request_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.approval_ledger.list_events(request_id, limit=limit)

    # ── Witness integration ──────────────────────────────────────────────────

    def record_witness_observation(
        self,
        *,
        subject_agent_id: str,
        category: str,
        witness_id: str = "operator",
        severity: GovernanceSeverity = "warning",
        confidence: float = 0.8,
        goal_id: str = "",
        session_id: str = "",
        source: str = "governance_orchestrator.record_witness_observation",
        event_ref: dict[str, str] | None = None,
        evidence_text: str = "",
        recommended_action: WitnessRecommendedAction = "review",
        details: dict[str, Any] | None = None,
        negative: bool = True,
    ) -> dict[str, Any]:
        observation_details = dict(details or {})
        if evidence_text:
            observation_details.setdefault("evidence_text", evidence_text)
        normalized_event_ref = normalize_governance_ref(event_ref)
        observation = WitnessObservation(
            witness_id=witness_id,
            subject_agent_id=subject_agent_id,
            goal_id=goal_id,
            session_id=session_id,
            category=category,
            severity=severity,
            confidence=confidence,
            source=source,
            event_ref=dict(normalized_event_ref or {}),
            recommended_action=recommended_action,
            details=observation_details,
            negative=negative,
        )
        snapshot = self.witness_governance.record_observation(observation)
        memory_record = self.memory_store.store(
            observation.render_content(),
            topic="hlf_witness_governance",
            confidence=observation.confidence,
            provenance=source,
            tags=sorted(
                {
                    "witness",
                    observation.category,
                    observation.severity,
                    snapshot.trust_state,
                    observation.subject_agent_id,
                }
            ),
            entry_kind="witness_observation",
            solution_kind=observation.category,
            metadata=observation.to_dict(),
        )
        related_refs = [dict(observation.event_ref)] if observation.event_ref else []
        governance_event = self.emit_governance_event(
            kind="witness_observation",
            source=source,
            action="record_witness_observation",
            status="warning" if observation.negative else "ok",
            severity="critical" if snapshot.trust_state == "restricted" else observation.severity,
            subject_id=subject_agent_id,
            goal_id=goal_id,
            session_id=session_id,
            details={
                "observation": observation.to_dict(),
                "trust_state": snapshot.to_dict(),
                "memory_fact_id": memory_record.get("id"),
                "memory_sha256": memory_record.get("sha256"),
            },
            related_refs=related_refs,
            agent_role="witness_governor",
            anomaly_score=min(1.0, observation.impact_score() / 2.0),
        )
        return {
            "status": "ok",
            "observation": observation.to_dict(),
            "trust_state": snapshot.to_dict(),
            "memory_record": memory_record,
            "governance_event": governance_event,
        }

    def persist_approval_bypass_attempt(
        self,
        *,
        subject_agent_id: str,
        source: str,
        witness_id: str,
        evidence_text: str,
        details: dict[str, Any] | None = None,
        related_refs: list[dict[str, str]] | None = None,
        severity: GovernanceSeverity = "critical",
        confidence: float = 0.97,
        recommended_action: WitnessRecommendedAction = "review",
    ) -> dict[str, Any]:
        normalized_subject = str(subject_agent_id or "").strip()
        event_details = dict(details or {})
        event_details.setdefault("category", "approval_bypass_attempt")
        event_details.setdefault("evidence_text", evidence_text)
        governance_event = self.emit_governance_event(
            kind="approval_transition",
            source=source,
            action="approval_bypass_attempt",
            status="blocked",
            severity=severity,
            subject_id=normalized_subject,
            goal_id=str(event_details.get("domain") or event_details.get("request_id") or "approval"),
            details=event_details,
            related_refs=related_refs,
            agent_role="approval_guard",
            anomaly_score=min(1.0, max(0.75, confidence)),
        )
        witness_observation = self.record_witness_observation(
            subject_agent_id=normalized_subject,
            category="approval_bypass_attempt",
            witness_id=witness_id,
            severity=severity,
            confidence=confidence,
            source=source,
            event_ref=governance_event.get("event_ref"),
            evidence_text=evidence_text,
            recommended_action=recommended_action,
            details=event_details,
        )
        return {
            "status": "ok",
            "governance_event": governance_event,
            "witness_observation": witness_observation,
            "witness_status": self.get_witness_status(subject_agent_id=normalized_subject),
        }

    def persist_subject_verifier_consequence(
        self,
        *,
        subject_agent_id: str,
        source: str,
        admission: dict[str, Any],
        report: dict[str, Any] | None = None,
        governance_event_ref: dict[str, str] | None = None,
        effect_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_subject = str(subject_agent_id or "").strip()
        if not normalized_subject or normalized_subject == "unknown-agent":
            return None

        normalized_ref = normalize_governance_ref(governance_event_ref)
        effective_report = dict(report or {})
        effective_effect_summary = dict(effect_summary or {})
        admission_verdict = str(admission.get("verdict") or "")
        requires_review = bool(admission.get("requires_operator_review", False))
        effectful = bool(effective_effect_summary.get("effectful", False))

        if admission_verdict == "verification_denied":
            return self.record_witness_observation(
                subject_agent_id=normalized_subject,
                category="verification_failure",
                witness_id="verifier",
                severity="critical",
                confidence=0.95,
                source=source,
                event_ref=dict(normalized_ref or {}),
                evidence_text="Formal verification denied the agent-scoped verifier request.",
                recommended_action="restrict",
                details={
                    "admission": dict(admission),
                    "report": effective_report,
                    "effect_summary": effective_effect_summary,
                },
            )

        if requires_review or admission_verdict == "verification_review_required":
            return self.record_witness_observation(
                subject_agent_id=normalized_subject,
                category="verification_review_required",
                witness_id="verifier",
                severity="warning",
                confidence=0.88 if effectful else 0.82,
                source=source,
                event_ref=dict(normalized_ref or {}),
                evidence_text=(
                    "Formal verification required operator review for the agent-scoped verifier request."
                ),
                recommended_action="probation" if effectful else "review",
                details={
                    "admission": dict(admission),
                    "report": effective_report,
                    "effect_summary": effective_effect_summary,
                },
            )

        if admission_verdict == "verification_advisory_only":
            return self.record_witness_observation(
                subject_agent_id=normalized_subject,
                category="verification_advisory_only",
                witness_id="verifier",
                severity="info",
                confidence=0.7,
                source=source,
                event_ref=dict(normalized_ref or {}),
                evidence_text=(
                    "Formal verification completed in advisory-only posture for the agent-scoped verifier request."
                ),
                recommended_action="observe",
                details={
                    "admission": dict(admission),
                    "report": effective_report,
                    "effect_summary": effective_effect_summary,
                    "informational_class": "evidence_only_informational_proof_gap",
                },
                negative=False,
            )

        if admission_verdict == "verification_admitted_with_skips":
            return self.record_witness_observation(
                subject_agent_id=normalized_subject,
                category="verification_skipped_checks",
                witness_id="verifier",
                severity="info",
                confidence=0.72,
                source=source,
                event_ref=dict(normalized_ref or {}),
                evidence_text=(
                    "Formal verification admitted the agent-scoped verifier request with skipped proof checks."
                ),
                recommended_action="observe",
                details={
                    "admission": dict(admission),
                    "report": effective_report,
                    "effect_summary": effective_effect_summary,
                    "informational_class": "repeat_pattern_advisory_drift",
                },
                negative=False,
            )

        return None

    def get_witness_status(self, *, subject_agent_id: str | None = None) -> dict[str, Any] | None:
        return self.witness_governance.status_snapshot(subject_agent_id=subject_agent_id)

    def list_witness_subjects(self, *, trust_state: str | None = None) -> dict[str, Any]:
        return {"subjects": self.witness_governance.list_snapshots(trust_state=trust_state)}

    def get_effective_trust_state(
        self, *, subject_agent_id: str | None = None, default: str = "trusted"
    ) -> str:
        if not subject_agent_id:
            return default
        snapshot = self.witness_governance.get_snapshot(subject_agent_id)
        if snapshot is None:
            return default
        return snapshot.trust_state
