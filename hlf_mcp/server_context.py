from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hlf_mcp.dream_cycle import DreamCycleReport, build_dream_findings
from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.approval_ledger import ApprovalLedger
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.daemon_manager import DaemonManager
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.governed_ingress import GovernedIngressController
from hlf_mcp.hlf.governance_events import (
    GovernanceEvent,
    GovernanceEventRef,
    GovernanceEventKind,
    GovernanceSeverity,
    GovernanceStatus,
    normalize_governance_ref,
    normalize_related_refs,
)
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.memory_node import build_pointer_ref
from hlf_mcp.hlf.registry import HostFunctionRegistry
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.tool_dispatch import ToolRegistry
from hlf_mcp.hlf.witness_governance import (
    WitnessGovernance,
    WitnessObservation,
    WitnessRecommendedAction,
)
from hlf_mcp.instinct.lifecycle import InstinctLifecycle
from hlf_mcp.media_evidence import MediaEvidenceRecord, normalize_media_evidence
from hlf_mcp.rag.memory import HKSProvenance, HKSTestEvidence, HKSValidatedExemplar, RAGMemory
from hlf_mcp.weekly_artifacts import (
    build_weekly_artifact_memory_record,
    load_verified_weekly_artifacts,
    summarize_weekly_artifacts,
)


def _build_hks_evaluation_snapshot(
    results: list[dict[str, Any]],
    *,
    source_kind: str,
    source_ref: str,
    query: str | None = None,
    operator_summary: str = "",
    evidence_refs: list[Any] | None = None,
) -> dict[str, Any] | None:
    evaluation_results: list[dict[str, Any]] = []
    local_hks_count = 0
    external_comparator_count = 0
    explicit_local_evaluation_count = 0
    promotion_eligible_count = 0
    requires_local_recheck_count = 0
    raw_intake_count = 0
    canonical_knowledge_count = 0
    canonical_source_count = 0
    advisory_source_count = 0
    extraction_fidelity_total = 0.0
    extraction_fidelity_count = 0

    for item in results:
        if not isinstance(item, dict):
            continue
        evaluation = item.get("evaluation") if isinstance(item.get("evaluation"), dict) else {}
        raw_source_capture = item.get("source_capture")
        source_capture: dict[str, Any] = dict(raw_source_capture) if isinstance(raw_source_capture, dict) else {}
        raw_artifact_contract = item.get("artifact_contract")
        artifact_contract: dict[str, Any] = (
            dict(raw_artifact_contract) if isinstance(raw_artifact_contract, dict) else {}
        )
        if not evaluation:
            continue
        authority = str(evaluation.get("authority") or "local_hks")
        if authority == "local_hks":
            local_hks_count += 1
        elif authority == "external_comparator":
            external_comparator_count += 1
        if bool(evaluation.get("explicit_local_evaluation_present", False)):
            explicit_local_evaluation_count += 1
        if bool(evaluation.get("promotion_eligible", False)):
            promotion_eligible_count += 1
        if bool(evaluation.get("requires_local_recheck", False)):
            requires_local_recheck_count += 1
        if artifact_contract.get("artifact_form") == "canonical_knowledge":
            canonical_knowledge_count += 1
        else:
            raw_intake_count += 1
        if source_capture.get("source_authority_label") == "canonical":
            canonical_source_count += 1
        else:
            advisory_source_count += 1
        extraction_fidelity = source_capture.get("extraction_fidelity_score")
        if isinstance(extraction_fidelity, (int, float)):
            extraction_fidelity_count += 1
            extraction_fidelity_total += float(extraction_fidelity)
        evaluation_results.append(
            {
                "fact_id": item.get("id"),
                "entry_kind": item.get("entry_kind"),
                "topic": item.get("topic"),
                "domain": item.get("domain"),
                "solution_kind": item.get("solution_kind"),
                "sha256": item.get("sha256"),
                "pointer": item.get("pointer"),
                "evaluation": dict(evaluation),
                "source_capture": source_capture,
                "artifact_contract": artifact_contract,
            }
        )

    if not evaluation_results:
        return None

    summary = operator_summary or (
        f"HKS evaluation tracked {len(evaluation_results)} evaluated result(s): "
        f"{local_hks_count} local_hks and {external_comparator_count} external_comparator."
    )
    return {
        "source_kind": source_kind,
        "source_ref": source_ref,
        "query": query,
        "operator_summary": summary,
        "result_count": len(evaluation_results),
        "evaluated_result_count": len(evaluation_results),
        "local_hks_count": local_hks_count,
        "external_comparator_count": external_comparator_count,
        "explicit_local_evaluation_count": explicit_local_evaluation_count,
        "promotion_eligible_count": promotion_eligible_count,
        "requires_local_recheck_count": requires_local_recheck_count,
        "raw_intake_count": raw_intake_count,
        "canonical_knowledge_count": canonical_knowledge_count,
        "canonical_source_count": canonical_source_count,
        "advisory_source_count": advisory_source_count,
        "average_extraction_fidelity_score": round(
            extraction_fidelity_total / extraction_fidelity_count, 4
        )
        if extraction_fidelity_count
        else None,
        "results": evaluation_results,
        "evidence_refs": list(evidence_refs or []),
    }


def _parse_hks_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _build_governed_recall_summary(
    results: list[dict[str, Any]],
    *,
    include_archive: bool,
    require_provenance: bool,
    allowed_entry_kinds: set[str],
) -> dict[str, Any]:
    entry_kind_counts = {kind: 0 for kind in sorted(allowed_entry_kinds)}
    memory_strata_counts: dict[str, int] = {}
    storage_tier_counts: dict[str, int] = {}
    admission_decision_counts: dict[str, int] = {}
    retrieval_path_counts: dict[str, int] = {}
    active_result_count = 0
    archived_result_count = 0
    evidence_backed_count = 0
    stale_result_count = 0
    graph_linked_result_count = 0

    for item in results:
        if not isinstance(item, dict):
            continue
        entry_kind = str(item.get("entry_kind") or "")
        if entry_kind:
            entry_kind_counts[entry_kind] = entry_kind_counts.get(entry_kind, 0) + 1
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            evidence = {}
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        memory_stratum = str(
            item.get("memory_stratum")
            or evidence.get("memory_stratum")
            or metadata.get("memory_stratum")
            or "working"
        )
        storage_tier = str(
            item.get("storage_tier")
            or evidence.get("storage_tier")
            or metadata.get("storage_tier")
            or "warm"
        )
        admission_decision = str(evidence.get("admission_decision") or item.get("admission_decision") or "active")
        freshness_status = str(evidence.get("freshness_status") or item.get("freshness_status") or "unknown")
        provenance_grade = str(evidence.get("provenance_grade") or item.get("provenance_grade") or "unverified")
        retrieval_contract_value = item.get("retrieval_contract")
        retrieval_contract = (
            retrieval_contract_value if isinstance(retrieval_contract_value, dict) else {}
        )
        for path in retrieval_contract.get("applied_paths") or []:
            normalized_path = str(path or "").strip()
            if not normalized_path:
                continue
            retrieval_path_counts[normalized_path] = retrieval_path_counts.get(normalized_path, 0) + 1
        if bool(retrieval_contract.get("graph_linked")):
            graph_linked_result_count += 1

        memory_strata_counts[memory_stratum] = memory_strata_counts.get(memory_stratum, 0) + 1
        storage_tier_counts[storage_tier] = storage_tier_counts.get(storage_tier, 0) + 1
        admission_decision_counts[admission_decision] = admission_decision_counts.get(admission_decision, 0) + 1

        if memory_stratum == "archive" or admission_decision == "archive":
            archived_result_count += 1
        else:
            active_result_count += 1
        if freshness_status == "stale":
            stale_result_count += 1
        if provenance_grade == "evidence-backed":
            evidence_backed_count += 1

    return {
        "result_count": len(results),
        "entry_kind_counts": entry_kind_counts,
        "memory_strata_counts": dict(sorted(memory_strata_counts.items())),
        "storage_tier_counts": dict(sorted(storage_tier_counts.items())),
        "admission_decision_counts": dict(sorted(admission_decision_counts.items())),
        "retrieval_path_counts": dict(sorted(retrieval_path_counts.items())),
        "active_result_count": active_result_count,
        "archived_result_count": archived_result_count,
        "graph_linked_result_count": graph_linked_result_count,
        "stale_result_count": stale_result_count,
        "evidence_backed_count": evidence_backed_count,
        "archive_visibility": "included" if include_archive else "filtered_by_default",
        "provenance_gate": "required" if require_provenance else "optional",
    }


@dataclass(slots=True)
class ServerContext:
    compiler: HLFCompiler
    formatter: HLFFormatter
    linter: HLFLinter
    runtime: HLFRuntime
    bytecoder: HLFBytecode
    benchmark: HLFBenchmark
    memory_store: RAGMemory
    instinct_mgr: InstinctLifecycle
    host_registry: HostFunctionRegistry
    tool_registry: ToolRegistry
    align_governor: AlignGovernor
    formal_verifier: FormalVerifier
    ingress_controller: GovernedIngressController
    session_profiles: dict[str, dict[str, Any]]
    session_model_catalogs: dict[str, dict[str, Any]]
    session_benchmark_artifacts: dict[str, dict[str, Any]]
    session_translation_contracts: dict[str, dict[str, Any]]
    session_governed_recalls: dict[str, dict[str, Any]]
    session_hks_evaluations: dict[str, dict[str, Any]]
    session_hks_external_compares: dict[str, dict[str, Any]]
    session_hks_weekly_refreshes: dict[str, dict[str, Any]]
    session_internal_workflows: dict[str, dict[str, Any]]
    session_governed_routes: dict[str, dict[str, Any]]
    session_execution_admissions: dict[str, dict[str, Any]]
    session_symbolic_surfaces: dict[str, dict[str, Any]]
    session_media_evidence: dict[str, dict[str, Any]]
    session_dream_cycles: dict[str, dict[str, Any]]
    session_dream_findings: dict[str, dict[str, Any]]
    session_dream_proposals: dict[str, dict[str, Any]]
    witness_governance: WitnessGovernance
    approval_ledger: ApprovalLedger
    audit_chain: AuditChain
    daemon_manager: DaemonManager
    governance_events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=250))

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
        return {"event": event_record, "audit": audit, "event_ref": event_record["event_ref"]}

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
        source: str = "server_context.record_witness_observation",
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

    def store_known_good_translation_contract(
        self,
        *,
        original_text: str,
        source: str,
        language: str,
        translation: dict[str, Any],
        tier: str,
        provenance: str,
    ) -> dict[str, Any]:
        payload = {
            "kind": "hlf_translation_contract",
            "language": language,
            "tier": tier,
            "original_text": original_text,
            "hlf_source": source,
            "translation": translation,
        }
        return self.capture_validated_solution(
            problem=original_text,
            validated_solution=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            domain="hlf-specific",
            solution_kind="translation-contract",
            provenance=provenance,
            tests=[
                {
                    "name": "translation_roundtrip",
                    "passed": True,
                    "details": {
                        "language": language,
                        "tier": tier,
                        "roundtrip_fidelity_score": translation.get(
                            "roundtrip_fidelity_score", 1.0
                        ),
                    },
                }
            ],
            topic="hlf_translation_contracts",
            confidence=float(translation.get("roundtrip_fidelity_score", 1.0)),
            tags=["hlf", "translation", "contract", language, tier],
            source_type="translation",
            source=source,
            graph_context={
                "entities": [
                    {"kind": "contract", "value": "translation-contract"},
                    {"kind": "language", "value": language},
                    {"kind": "tier", "value": tier},
                    {"kind": "pattern", "value": "translation-memory"},
                ],
                "links": [
                    {
                        "source": "contract:translation-contract",
                        "relation": "operates_in",
                        "target": f"language:{language}",
                    },
                    {
                        "source": "contract:translation-contract",
                        "relation": "governed_for",
                        "target": f"tier:{tier}",
                    },
                    {
                        "source": "pattern:translation-memory",
                        "relation": "materializes_as",
                        "target": "contract:translation-contract",
                    },
                ],
            },
        )

    def store_translation_repair_pattern(
        self,
        *,
        original_text: str,
        failure_status: str,
        failure_error: str,
        language: str,
        repair_plan: dict[str, Any],
        provenance: str,
    ) -> dict[str, Any]:
        normalized_failure_status = str(failure_status or "unknown_failure").strip() or "unknown_failure"
        payload = {
            "kind": "hlf_translation_repair_pattern",
            "language": language,
            "failure_status": normalized_failure_status,
            "failure_error": failure_error,
            "original_text": original_text,
            "repair_plan": repair_plan,
        }
        problem = f"{normalized_failure_status}: {original_text}" if original_text else normalized_failure_status
        return self.capture_validated_solution(
            problem=problem,
            validated_solution=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            domain="hlf-specific",
            solution_kind="repair-pattern",
            provenance=provenance,
            tests=[
                {
                    "name": "translation_repair_contract",
                    "passed": True,
                    "details": {
                        "language": language,
                        "failure_status": normalized_failure_status,
                        "retryable": repair_plan.get("retryable", False),
                        "recommended_tool": repair_plan.get("recommended_tool"),
                    },
                }
            ],
            topic="hlf_repairs",
            confidence=1.0 if bool(repair_plan.get("retryable")) else 0.85,
            tags=["hlf", "translation", "repair", language, normalized_failure_status],
            source_type="translation_repair",
            source=provenance,
            graph_context={
                "entities": [
                    {"kind": "contract", "value": "translation-repair"},
                    {"kind": "repair_procedure", "value": normalized_failure_status},
                    {"kind": "language", "value": language},
                    {"kind": "pattern", "value": "repair-pattern-recall"},
                ],
                "links": [
                    {
                        "source": "contract:translation-repair",
                        "relation": "operates_in",
                        "target": f"language:{language}",
                    },
                    {
                        "source": "contract:translation-repair",
                        "relation": "repairs",
                        "target": f"repair_procedure:{normalized_failure_status}",
                    },
                    {
                        "source": "pattern:repair-pattern-recall",
                        "relation": "materializes_as",
                        "target": "contract:translation-repair",
                    },
                ],
            },
        )

    def persist_translation_contract(
        self,
        contract: dict[str, Any],
        *,
        source: str,
        memory_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        persisted = dict(contract)
        canonical_hlf = cast(
            dict[str, Any],
            persisted.get("canonical_hlf") if isinstance(persisted.get("canonical_hlf"), dict) else {},
        )
        intent = cast(
            dict[str, Any],
            persisted.get("intent") if isinstance(persisted.get("intent"), dict) else {},
        )
        governance = cast(
            dict[str, Any],
            persisted.get("governance") if isinstance(persisted.get("governance"), dict) else {},
        )
        memory_payload = dict(memory_result or {})
        contract_id = str(
            persisted.get("contract_id")
            or canonical_hlf.get("ast_sha256")
            or f"translation-{uuid.uuid4().hex[:12]}"
        )
        persisted["contract_id"] = contract_id
        persisted["resource_uri"] = f"hlf://status/translation_contract/{contract_id}"
        persisted["report_uri"] = f"hlf://reports/translation_contract/{contract_id}"

        related_refs: list[dict[str, str]] = []
        memory_governance_event = memory_payload.get("governance_event")
        if isinstance(memory_governance_event, dict):
            memory_event_ref = memory_governance_event.get("event_ref") or (
                memory_governance_event.get("event") or {}
            ).get("event_ref")
            normalized_memory_ref = normalize_governance_ref(memory_event_ref)
            if normalized_memory_ref is not None:
                related_refs.append(normalized_memory_ref)

        governance_event = self.emit_governance_event(
            kind="validated_solution_capture",
            source=source,
            action="persist_translation_contract",
            status="ok" if bool(governance.get("governed", False)) else "warning",
            severity="info" if bool(governance.get("governed", False)) else "warning",
            subject_id=contract_id,
            goal_id=str(intent.get("tier") or intent.get("language") or "translation_contract"),
            details={
                "contract_id": contract_id,
                "intent_text": intent.get("text"),
                "intent_language": intent.get("language"),
                "tier": intent.get("tier"),
                "ast_sha256": canonical_hlf.get("ast_sha256"),
                "statement_count": canonical_hlf.get("statement_count"),
                "governed": governance.get("governed", False),
                "memory_fact_id": memory_payload.get("id"),
                "memory_sha256": memory_payload.get("sha256"),
                "operator_summary": persisted.get("operator_summary"),
            },
            related_refs=related_refs,
            agent_role="translation_contract",
            anomaly_score=0.5 if not bool(governance.get("governed", False)) else 0.0,
        )
        persisted["governance_event"] = governance_event
        persisted["governance_event_ref"] = governance_event.get("event_ref")
        if memory_payload:
            persisted["memory"] = {
                "id": memory_payload.get("id"),
                "sha256": memory_payload.get("sha256"),
                "stored": memory_payload.get("stored"),
                "evidence": memory_payload.get("evidence"),
                "governance_event_ref": normalize_governance_ref(
                    (memory_governance_event or {}).get("event_ref")
                    if isinstance(memory_governance_event, dict)
                    else None
                ),
            }
        if contract_id in self.session_translation_contracts:
            self.session_translation_contracts.pop(contract_id)
        self.session_translation_contracts[contract_id] = persisted
        return self.session_translation_contracts[contract_id]

    def get_translation_contract(
        self,
        *,
        contract_id: str | None = None,
    ) -> dict[str, Any] | None:
        if contract_id:
            return self.session_translation_contracts.get(contract_id)
        if self.session_translation_contracts:
            latest_contract_id = next(reversed(self.session_translation_contracts))
            return self.session_translation_contracts.get(latest_contract_id)
        return None

    def persist_hks_evaluation(
        self,
        evaluation_payload: dict[str, Any],
        *,
        source: str,
    ) -> dict[str, Any]:
        persisted = dict(evaluation_payload)
        raw_results = persisted.get("results")
        results = raw_results if isinstance(raw_results, list) else []
        inferred_evaluation_id = ""
        if len(results) == 1 and isinstance(results[0], dict):
            first_result = results[0]
            raw_result_evaluation = first_result.get("evaluation")
            result_evaluation = raw_result_evaluation if isinstance(raw_result_evaluation, dict) else {}
            inferred_evaluation_id = str(result_evaluation.get("evaluation_id") or "")
        evaluation_id = str(
            persisted.get("evaluation_id") or inferred_evaluation_id or f"hks-eval-{uuid.uuid4().hex[:12]}"
        )
        persisted["evaluation_id"] = evaluation_id
        persisted["resource_uri"] = f"hlf://status/hks_evaluation/{evaluation_id}"
        persisted["report_uri"] = f"hlf://reports/hks_evaluation/{evaluation_id}"
        persisted["source"] = source
        if evaluation_id in self.session_hks_evaluations:
            self.session_hks_evaluations.pop(evaluation_id)
        self.session_hks_evaluations[evaluation_id] = persisted
        return self.session_hks_evaluations[evaluation_id]

    def get_hks_evaluation(
        self,
        *,
        evaluation_id: str | None = None,
    ) -> dict[str, Any] | None:
        if evaluation_id:
            return self.session_hks_evaluations.get(evaluation_id)
        if self.session_hks_evaluations:
            latest_evaluation_id = next(reversed(self.session_hks_evaluations))
            return self.session_hks_evaluations.get(latest_evaluation_id)
        return None

    def persist_hks_external_compare(
        self,
        compare_payload: dict[str, Any],
        *,
        source: str,
    ) -> dict[str, Any]:
        persisted = dict(compare_payload)
        compare_id = str(persisted.get("compare_id") or f"hks-compare-{uuid.uuid4().hex[:12]}")
        persisted["compare_id"] = compare_id
        persisted["resource_uri"] = f"hlf://status/hks_external_compare/{compare_id}"
        persisted["report_uri"] = f"hlf://reports/hks_external_compare/{compare_id}"
        persisted["source"] = source
        if compare_id in self.session_hks_external_compares:
            self.session_hks_external_compares.pop(compare_id)
        self.session_hks_external_compares[compare_id] = persisted
        return self.session_hks_external_compares[compare_id]

    def get_hks_external_compare(
        self,
        *,
        compare_id: str | None = None,
    ) -> dict[str, Any] | None:
        if compare_id:
            return self.session_hks_external_compares.get(compare_id)
        if self.session_hks_external_compares:
            latest_compare_id = next(reversed(self.session_hks_external_compares))
            return self.session_hks_external_compares.get(latest_compare_id)
        return None

    def persist_hks_weekly_refresh(
        self,
        refresh_payload: dict[str, Any],
        *,
        source: str,
    ) -> dict[str, Any]:
        persisted = dict(refresh_payload)
        refresh_id = str(persisted.get("refresh_id") or f"hks-refresh-{uuid.uuid4().hex[:12]}")
        persisted["refresh_id"] = refresh_id
        persisted["resource_uri"] = f"hlf://status/hks_weekly_refresh/{refresh_id}"
        persisted["report_uri"] = f"hlf://reports/hks_weekly_refresh/{refresh_id}"
        persisted["source"] = source
        if refresh_id in self.session_hks_weekly_refreshes:
            self.session_hks_weekly_refreshes.pop(refresh_id)
        self.session_hks_weekly_refreshes[refresh_id] = persisted
        return self.session_hks_weekly_refreshes[refresh_id]

    def get_hks_weekly_refresh(
        self,
        *,
        refresh_id: str | None = None,
    ) -> dict[str, Any] | None:
        if refresh_id:
            return self.session_hks_weekly_refreshes.get(refresh_id)
        if self.session_hks_weekly_refreshes:
            latest_refresh_id = next(reversed(self.session_hks_weekly_refreshes))
            return self.session_hks_weekly_refreshes.get(latest_refresh_id)
        return None

    def analyze_hks_weekly_refresh(
        self,
        *,
        metrics_dir: str | None = None,
        stale_after_days: int = 7,
    ) -> dict[str, Any]:
        resolved_metrics_dir = Path(metrics_dir).expanduser() if metrics_dir else None
        verified_artifacts = load_verified_weekly_artifacts(
            resolved_metrics_dir,
            verified_only=True,
        )
        synced_weekly_facts = self.memory_store.query_facts(
            entry_kind="weekly_artifact",
            include_stale=True,
            include_superseded=True,
            include_revoked=True,
            include_archive=True,
        )
        all_memory_facts = self.memory_store.query_facts(
            include_stale=True,
            include_superseded=True,
            include_revoked=True,
            include_archive=True,
        )

        normalized_stale_after_days = max(int(stale_after_days), 1)
        now = datetime.now(UTC)
        cutoff = now.timestamp() - normalized_stale_after_days * 86400

        synced_artifact_ids: set[str] = set()
        synced_source_latest: dict[str, datetime] = {}
        for fact in synced_weekly_facts:
            if not isinstance(fact, dict):
                continue
            raw_metadata = fact.get("metadata")
            metadata: dict[str, Any] = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
            artifact_id = str(metadata.get("artifact_id") or "").strip()
            if artifact_id:
                synced_artifact_ids.add(artifact_id)
            source = str(metadata.get("source") or "").strip()
            synced_at = _parse_hks_timestamp(metadata.get("generated_at")) or _parse_hks_timestamp(
                fact.get("created_at")
            )
            current_latest = synced_source_latest.get(source)
            if source and synced_at and (current_latest is None or synced_at > current_latest):
                synced_source_latest[source] = synced_at

        verified_source_latest: dict[str, datetime] = {}
        unsynced_artifacts: list[dict[str, Any]] = []
        for artifact in verified_artifacts:
            artifact_id = str(artifact.get("artifact_id") or "").strip()
            source = str(artifact.get("source") or "unknown").strip() or "unknown"
            generated_at = _parse_hks_timestamp(artifact.get("generated_at")) or now
            current_latest = verified_source_latest.get(source)
            if current_latest is None or generated_at > current_latest:
                verified_source_latest[source] = generated_at
            if artifact_id and artifact_id not in synced_artifact_ids:
                unsynced_artifacts.append(
                    {
                        "artifact_id": artifact_id,
                        "source": source,
                        "artifact_status": artifact.get("artifact_status"),
                        "generated_at": artifact.get("generated_at"),
                    }
                )

        domain_fact_counts = {domain: 0 for domain in ("ai-engineering", "general-coding", "hlf-specific")}
        domain_active_counts = {domain: 0 for domain in domain_fact_counts}
        domain_latest_ts: dict[str, float] = {}
        for fact in all_memory_facts:
            if not isinstance(fact, dict):
                continue
            if str(fact.get("entry_kind") or "") == "hks_graph_node":
                continue
            domain = str(fact.get("domain") or "").strip()
            if domain not in domain_fact_counts:
                continue
            domain_fact_counts[domain] += 1
            if str(fact.get("governance_status") or "") == "active":
                domain_active_counts[domain] += 1
            created_at = fact.get("created_at")
            if isinstance(created_at, (int, float)):
                domain_latest_ts[domain] = max(float(created_at), domain_latest_ts.get(domain, 0.0))

        domain_statuses: list[dict[str, Any]] = []
        topic_statuses: list[dict[str, Any]] = []
        queued_actions: list[dict[str, Any]] = []

        def _queue_action(
            *,
            action_kind: str,
            target_type: str,
            target_id: str,
            priority: str,
            rationale: str,
        ) -> None:
            action_id = hashlib.sha256(
                json.dumps(
                    {
                        "action_kind": action_kind,
                        "target_type": target_type,
                        "target_id": target_id,
                        "rationale": rationale,
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()[:16]
            queued_actions.append(
                {
                    "action_id": action_id,
                    "action_kind": action_kind,
                    "target_type": target_type,
                    "target_id": target_id,
                    "priority": priority,
                    "status": "queued",
                    "lane": "bridge",
                    "requires_operator_review": True,
                    "rationale": rationale,
                }
            )

        for domain in sorted(domain_fact_counts):
            fact_count = domain_fact_counts[domain]
            active_count = domain_active_counts[domain]
            latest_ts = domain_latest_ts.get(domain)
            latest_iso = datetime.fromtimestamp(latest_ts, tz=UTC).isoformat() if latest_ts else None
            if fact_count == 0:
                status = "empty"
                _queue_action(
                    action_kind="re_research_domain",
                    target_type="hks_domain",
                    target_id=domain,
                    priority="high",
                    rationale=f"HKS domain '{domain}' has no persisted non-graph facts and needs re-research seeding.",
                )
            elif latest_ts is None or latest_ts < cutoff:
                status = "stale"
                _queue_action(
                    action_kind="revalidate_domain",
                    target_type="hks_domain",
                    target_id=domain,
                    priority="medium",
                    rationale=(
                        f"HKS domain '{domain}' has {fact_count} persisted fact(s) but none newer than the weekly freshness threshold."
                    ),
                )
            else:
                status = "fresh"
            domain_statuses.append(
                {
                    "domain": domain,
                    "status": status,
                    "fact_count": fact_count,
                    "active_fact_count": active_count,
                    "latest_memory_at": latest_iso,
                }
            )

        for source, latest_verified_at in sorted(verified_source_latest.items()):
            synced_at = synced_source_latest.get(source)
            if synced_at is None:
                status = "not_ingested"
                _queue_action(
                    action_kind="sync_weekly_source_topic",
                    target_type="weekly_source_topic",
                    target_id=source,
                    priority="high",
                    rationale=f"Verified weekly source '{source}' has no mirrored weekly artifact in packaged HKS memory yet.",
                )
            elif synced_at < latest_verified_at:
                status = "behind_verified_artifacts"
                _queue_action(
                    action_kind="revalidate_topic",
                    target_type="weekly_source_topic",
                    target_id=source,
                    priority="medium",
                    rationale=(
                        f"Weekly source '{source}' has newer verified artifacts than the latest mirrored HKS weekly artifact."
                    ),
                )
            elif synced_at.timestamp() < cutoff:
                status = "stale"
                _queue_action(
                    action_kind="revalidate_topic",
                    target_type="weekly_source_topic",
                    target_id=source,
                    priority="medium",
                    rationale=(
                        f"Weekly source '{source}' has not refreshed the packaged HKS mirror within the weekly freshness threshold."
                    ),
                )
            else:
                status = "fresh"
            topic_statuses.append(
                {
                    "source": source,
                    "status": status,
                    "latest_verified_at": latest_verified_at.isoformat(),
                    "latest_synced_at": synced_at.isoformat() if synced_at else None,
                }
            )

        stale_domain_count = sum(1 for item in domain_statuses if item["status"] in {"empty", "stale"})
        stale_topic_count = sum(1 for item in topic_statuses if item["status"] != "fresh")
        payload = {
            "status": "ok",
            "refresh_kind": "hks_weekly_refresh",
            "lane": "bridge",
            "stale_after_days": normalized_stale_after_days,
            "analyzed_at": now.replace(microsecond=0).isoformat(),
            "verified_artifact_count": len(verified_artifacts),
            "mirrored_weekly_artifact_count": len(synced_weekly_facts),
            "unsynced_artifact_count": len(unsynced_artifacts),
            "stale_domain_count": stale_domain_count,
            "stale_topic_count": stale_topic_count,
            "queued_action_count": len(queued_actions),
            "unsynced_artifacts": unsynced_artifacts[:12],
            "domain_statuses": domain_statuses,
            "topic_statuses": topic_statuses,
            "queued_actions": queued_actions,
            "operator_summary": (
                f"HKS weekly refresh detected {stale_domain_count} stale-or-empty domain(s), "
                f"{stale_topic_count} weekly source topic(s) needing attention, and {len(unsynced_artifacts)} unsynced verified artifact(s)."
            ),
            "evidence_refs": [],
            "metrics_dir": str(resolved_metrics_dir) if resolved_metrics_dir else None,
        }
        persisted = self.persist_hks_weekly_refresh(
            payload,
            source="server_context.analyze_hks_weekly_refresh",
        )
        governance_event = self.emit_governance_event(
            kind="memory_governance",
            source="server_context.analyze_hks_weekly_refresh",
            action="analyze_hks_weekly_refresh",
            status="warning" if queued_actions else "ok",
            severity="warning" if queued_actions else "info",
            subject_id=str(persisted.get("refresh_id") or ""),
            goal_id="hks_weekly_refresh",
            details={
                "verified_artifact_count": persisted.get("verified_artifact_count"),
                "mirrored_weekly_artifact_count": persisted.get("mirrored_weekly_artifact_count"),
                "unsynced_artifact_count": persisted.get("unsynced_artifact_count"),
                "stale_domain_count": persisted.get("stale_domain_count"),
                "stale_topic_count": persisted.get("stale_topic_count"),
                "queued_action_count": persisted.get("queued_action_count"),
                "operator_summary": persisted.get("operator_summary"),
            },
            agent_role="hks_weekly_refresh",
        )
        persisted["governance_event"] = governance_event
        persisted["governance_event_ref"] = governance_event.get("event_ref")
        persisted["evidence_refs"] = [governance_event.get("event_ref")]
        self.session_hks_weekly_refreshes[str(persisted.get("refresh_id"))] = persisted
        return persisted

    def persist_governed_recall(
        self,
        recall_payload: dict[str, Any],
        *,
        source: str,
    ) -> dict[str, Any]:
        persisted = dict(recall_payload)
        recall_id = str(persisted.get("recall_id") or f"recall-{uuid.uuid4().hex[:12]}")
        persisted["recall_id"] = recall_id
        persisted["resource_uri"] = f"hlf://status/governed_recall/{recall_id}"
        persisted["report_uri"] = f"hlf://reports/governed_recall/{recall_id}"
        persisted["source"] = source
        evaluation_snapshot = _build_hks_evaluation_snapshot(
            list(persisted.get("results") or []),
            source_kind=str(persisted.get("recall_kind") or "governed_recall"),
            source_ref=recall_id,
            query=str(persisted.get("query") or "") or None,
            operator_summary=str(persisted.get("operator_summary") or ""),
            evidence_refs=list(persisted.get("evidence_refs") or []),
        )
        if evaluation_snapshot is not None:
            evaluation_chain = self.persist_hks_evaluation(
                evaluation_snapshot,
                source="server_context.persist_governed_recall",
            )
            persisted["hks_evaluation"] = evaluation_chain
            persisted["evaluation_id"] = evaluation_chain.get("evaluation_id")
            persisted["evaluation_resource_uri"] = evaluation_chain.get("resource_uri")
            persisted["evaluation_report_uri"] = evaluation_chain.get("report_uri")
        if recall_id in self.session_governed_recalls:
            self.session_governed_recalls.pop(recall_id)
        self.session_governed_recalls[recall_id] = persisted
        return self.session_governed_recalls[recall_id]

    def get_governed_recall(
        self,
        *,
        recall_id: str | None = None,
    ) -> dict[str, Any] | None:
        if recall_id:
            return self.session_governed_recalls.get(recall_id)
        if self.session_governed_recalls:
            latest_recall_id = next(reversed(self.session_governed_recalls))
            return self.session_governed_recalls.get(latest_recall_id)
        return None

    def persist_internal_workflow(
        self,
        workflow_payload: dict[str, Any],
        *,
        source: str,
    ) -> dict[str, Any]:
        persisted = dict(workflow_payload)
        workflow_id = str(
            persisted.get("workflow_id")
            or f"workflow-{uuid.uuid4().hex[:12]}"
        )
        persisted["workflow_id"] = workflow_id
        persisted["resource_uri"] = f"hlf://status/internal_workflow/{workflow_id}"
        persisted["report_uri"] = f"hlf://reports/internal_workflow/{workflow_id}"
        persisted["source"] = source

        related_refs = normalize_related_refs(
            [item for item in (persisted.get("evidence_refs") or []) if isinstance(item, dict)]
        )
        raw_before = persisted.get("before")
        before = raw_before if isinstance(raw_before, dict) else {}
        raw_after = persisted.get("after")
        after = raw_after if isinstance(raw_after, dict) else {}
        raw_capture = before.get("capture")
        capture = raw_capture if isinstance(raw_capture, dict) else {}
        raw_recall = after.get("recall")
        recall = raw_recall if isinstance(raw_recall, dict) else {}

        governance_event = self.emit_governance_event(
            kind="validated_solution_capture",
            source=source,
            action="persist_internal_workflow",
            status="ok",
            severity="info",
            subject_id=workflow_id,
            goal_id=str(persisted.get("workflow_kind") or "internal_workflow"),
            details={
                "workflow_id": workflow_id,
                "workflow_kind": persisted.get("workflow_kind"),
                "query": persisted.get("query"),
                "domain": persisted.get("domain"),
                "solution_kind": persisted.get("solution_kind"),
                "capture_fact_id": capture.get("fact_id"),
                "capture_sha256": capture.get("sha256"),
                "recall_id": recall.get("recall_id"),
                "result_count": recall.get("result_count"),
                "operator_summary": persisted.get("operator_summary"),
            },
            related_refs=related_refs,
            agent_role="internal_workflow",
        )
        persisted["governance_event"] = governance_event
        persisted["governance_event_ref"] = governance_event.get("event_ref")
        if workflow_id in self.session_internal_workflows:
            self.session_internal_workflows.pop(workflow_id)
        self.session_internal_workflows[workflow_id] = persisted
        return self.session_internal_workflows[workflow_id]

    def get_internal_workflow(
        self,
        *,
        workflow_id: str | None = None,
    ) -> dict[str, Any] | None:
        if workflow_id:
            return self.session_internal_workflows.get(workflow_id)
        if self.session_internal_workflows:
            latest_workflow_id = next(reversed(self.session_internal_workflows))
            return self.session_internal_workflows.get(latest_workflow_id)
        return None

    def capture_validated_solution(
        self,
        *,
        problem: str,
        validated_solution: str,
        domain: str,
        solution_kind: str,
        provenance: str,
        tests: list[dict[str, Any] | HKSTestEvidence] | None = None,
        topic: str = "hlf_validated_exemplars",
        confidence: float = 1.0,
        tags: list[str] | None = None,
        supersedes: str | None = None,
        summary: str = "",
        source_type: str = "runtime",
        source: str | None = None,
        workflow_run_url: str | None = None,
        branch: str | None = None,
        commit_sha: str | None = None,
        artifact_path: str | None = None,
        graph_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_tests: list[HKSTestEvidence] = []
        for item in tests or []:
            if isinstance(item, HKSTestEvidence):
                normalized_tests.append(item)
            else:
                raw_status = str(item.get("status") or "").strip().lower()
                inferred_passed = item.get("passed")
                if inferred_passed is None and raw_status:
                    inferred_passed = raw_status in {"passed", "pass", "ok", "success", "succeeded"}
                normalized_tests.append(
                    HKSTestEvidence(
                        name=str(item.get("name", "validation")),
                        passed=bool(inferred_passed),
                        exit_code=item.get("exit_code"),
                        counts=item.get("counts"),
                        details=item.get("details"),
                    )
                )

        all_tests_passed = all(test.passed for test in normalized_tests) if normalized_tests else True
        evaluation = {
            "authority": "local_hks",
            "groundedness": 1.0 if all_tests_passed else 0.0,
            "citation_coverage": 1.0,
            "freshness_verdict": "fresh",
            "provenance_verdict": "evidence-backed",
            "promotion_eligible": all_tests_passed,
            "promotion_blocked": not all_tests_passed,
            "requires_local_recheck": False,
            "lane": "current_truth",
            "operator_summary": (
                f"Local HKS evaluation {'approved' if all_tests_passed else 'blocked'} exemplar promotion for '{problem}' "
                f"with {len(normalized_tests)} validation test(s)."
            ),
        }

        exemplar = HKSValidatedExemplar(
            problem=problem,
            validated_solution=validated_solution,
            domain=domain,
            solution_kind=solution_kind,
            provenance=HKSProvenance(
                source_type=source_type,
                source=source or provenance,
                collector=provenance,
                collected_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
                workflow_run_url=workflow_run_url,
                branch=branch,
                commit_sha=commit_sha,
                artifact_path=artifact_path,
                confidence=confidence,
            ),
            tests=normalized_tests,
            supersedes=supersedes,
            topic=topic,
            tags=tags or [],
            summary=summary,
            confidence=confidence,
            evaluation=evaluation,
            graph_context=graph_context,
        )
        result = self.memory_store.store_exemplar(exemplar)
        result["governance_event"] = self.emit_governance_event(
            kind="validated_solution_capture",
            source="server_context.capture_validated_solution",
            action="capture_validated_solution",
            subject_id=str(result.get("id", "")),
            goal_id=topic,
            details={
                "topic": topic,
                "domain": domain,
                "solution_kind": solution_kind,
                "sha256": result.get("sha256"),
                "confidence": confidence,
                "test_count": len(normalized_tests),
            },
            agent_role="validated_solution_capture",
        )
        evaluation_snapshot = _build_hks_evaluation_snapshot(
            [result],
            source_kind="hks_capture",
            source_ref=str(result.get("id") or ""),
            query=problem,
            operator_summary=(
                f"Local HKS capture stored exemplar {result.get('id')} for '{problem}' with a governed evaluation snapshot."
            ),
            evidence_refs=[result.get("governance_event", {}).get("event_ref")],
        )
        if evaluation_snapshot is not None:
            evaluation_chain = self.persist_hks_evaluation(
                evaluation_snapshot,
                source="server_context.capture_validated_solution",
            )
            result["hks_evaluation"] = evaluation_chain
            result["evaluation_resource_uri"] = evaluation_chain.get("resource_uri")
            result["evaluation_report_uri"] = evaluation_chain.get("report_uri")
        return result

    def persist_embedding_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(profile.get("agent_id") or "unknown-agent")
        self.session_profiles[agent_id] = dict(profile)
        self.emit_governance_event(
            kind="routing_decision",
            source="server_context.persist_embedding_profile",
            action="persist_embedding_profile",
            subject_id=agent_id,
            goal_id=str(profile.get("profile_id", "")),
            details={
                "profile_id": profile.get("profile_id"),
                "workload": profile.get("workload_profile", {}).get("workload"),
                "model": profile.get("embedding_recommendation", {}).get("model"),
                "fallback_model": profile.get("fallback_recommendation", {}).get("model"),
            },
            agent_role="routing_profile",
        )
        return self.session_profiles[agent_id]

    def get_embedding_profile(
        self, *, agent_id: str | None = None, profile_id: str | None = None
    ) -> dict[str, Any] | None:
        if agent_id:
            return self.session_profiles.get(agent_id)
        if profile_id:
            for profile in self.session_profiles.values():
                if str(profile.get("profile_id")) == profile_id:
                    return profile
        return None

    def persist_model_catalog(self, catalog: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(catalog.get("agent_id") or "unknown-agent")
        self.session_model_catalogs[agent_id] = dict(catalog)
        summary = dict(catalog.get("summary") or {})
        self.emit_governance_event(
            kind="model_catalog_sync",
            source="server_context.persist_model_catalog",
            action="persist_model_catalog",
            subject_id=agent_id,
            goal_id=str(catalog.get("ollama_endpoint", "")),
            details={
                "ollama_access_mode": catalog.get("ollama_access_mode"),
                "preferred_lanes": catalog.get("preferred_lanes", []),
                "total_models": summary.get("total_models", 0),
                "reachable_count": summary.get("reachable_count", 0),
                "configured_remote_direct_count": summary.get("configured_remote_direct_count", 0),
            },
            agent_role="model_catalog",
        )
        return self.session_model_catalogs[agent_id]

    def persist_benchmark_artifact(self, artifact: dict[str, Any]) -> dict[str, Any]:
        profile_name = str(
            artifact.get("profile_name") or artifact.get("artifact_id") or "unknown-benchmark"
        )
        persisted_artifact = dict(artifact)
        collected_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        benchmark_scores = dict(persisted_artifact.get("benchmark_scores") or {})
        details = dict(persisted_artifact.get("details") or {})
        result_payload = dict(persisted_artifact.get("result") or {})
        domains = [str(item) for item in (persisted_artifact.get("domains") or []) if str(item)]
        languages = [str(item) for item in (persisted_artifact.get("languages") or []) if str(item)]
        benchmark_entities: list[dict[str, str]] = [
            {"kind": "profile", "value": profile_name},
            *[
                {"kind": "benchmark_metric", "value": metric}
                for metric in sorted(benchmark_scores.keys())[:6]
            ],
            *[{"kind": "domain", "value": domain} for domain in domains[:4]],
            *[{"kind": "language", "value": language} for language in languages[:4]],
        ]
        for key, kind in (
            ("prompt_name", "prompt_asset"),
            ("prompt_asset", "prompt_asset"),
            ("code_pattern", "code_pattern"),
            ("upgrade_candidate", "upgrade_opportunity"),
            ("recommended_upgrade", "upgrade_opportunity"),
        ):
            value = details.get(key) or result_payload.get(key)
            normalized = str(value or "").strip()
            if normalized:
                benchmark_entities.append({"kind": kind, "value": normalized})

        benchmark_links: list[dict[str, str]] = [
            {
                "source": f"profile:{profile_name}",
                "relation": "measured_by",
                "target": f"benchmark_metric:{metric}",
            }
            for metric in sorted(benchmark_scores.keys())[:6]
        ]
        benchmark_links.extend(
            {
                "source": f"profile:{profile_name}",
                "relation": "covers_domain",
                "target": f"domain:{domain}",
            }
            for domain in domains[:4]
        )
        benchmark_links.extend(
            {
                "source": f"profile:{profile_name}",
                "relation": "validated_in",
                "target": f"language:{language}",
            }
            for language in languages[:4]
        )
        if str(details.get("prompt_name") or result_payload.get("prompt_name") or "").strip():
            prompt_name = str(details.get("prompt_name") or result_payload.get("prompt_name") or "").strip()
            benchmark_links.append(
                {
                    "source": f"profile:{profile_name}",
                    "relation": "materializes_prompt",
                    "target": f"prompt_asset:{prompt_name}",
                }
            )
        if str(details.get("code_pattern") or result_payload.get("code_pattern") or "").strip():
            code_pattern = str(details.get("code_pattern") or result_payload.get("code_pattern") or "").strip()
            benchmark_links.append(
                {
                    "source": f"profile:{profile_name}",
                    "relation": "materializes_code_pattern",
                    "target": f"code_pattern:{code_pattern}",
                }
            )
        if str(details.get("upgrade_candidate") or details.get("recommended_upgrade") or result_payload.get("upgrade_candidate") or result_payload.get("recommended_upgrade") or "").strip():
            upgrade_name = str(
                details.get("upgrade_candidate")
                or details.get("recommended_upgrade")
                or result_payload.get("upgrade_candidate")
                or result_payload.get("recommended_upgrade")
                or ""
            ).strip()
            benchmark_links.append(
                {
                    "source": f"profile:{profile_name}",
                    "relation": "suggests_upgrade",
                    "target": f"upgrade_opportunity:{upgrade_name}",
                }
            )
        stored = self.memory_store.store(
            json.dumps(persisted_artifact, ensure_ascii=False, sort_keys=True),
            topic="hlf_benchmark_artifacts",
            confidence=1.0,
            provenance="server_context.persist_benchmark_artifact",
            tags=["hlf", "benchmark", profile_name],
            entry_kind="benchmark_artifact",
            metadata={
                "profile_name": profile_name,
                "benchmark_scores": benchmark_scores,
                "artifact_id": persisted_artifact.get("artifact_id"),
                "domains": domains,
                "languages": languages,
                "details": details,
                "result": result_payload,
                "source": persisted_artifact.get("topic") or "hlf_benchmark_artifacts",
                "operator_summary": f"Governed benchmark artifact for {profile_name}",
                "artifact_kind": "benchmark_artifact",
                "artifact_contract": {
                    "artifact_form": "canonical_knowledge",
                    "artifact_kind": "benchmark_artifact",
                    "canonicalized": True,
                },
                "graph_context": {
                    "entities": benchmark_entities,
                    "links": benchmark_links,
                },
                "governed_evidence": {
                    "source_class": "benchmark_artifact",
                    "source_type": "benchmark_artifact",
                    "source": persisted_artifact.get("topic") or "hlf_benchmark_artifacts",
                    "source_path": persisted_artifact.get("artifact_id"),
                    "artifact_id": persisted_artifact.get("artifact_id"),
                    "collector": "server_context.persist_benchmark_artifact",
                    "collected_at": collected_at,
                    "trust_tier": "validated",
                    "operator_summary": f"Governed benchmark artifact for {profile_name}",
                },
            },
        )
        persisted_artifact["memory_ref"] = {"id": stored.get("id"), "sha256": stored.get("sha256")}
        persisted_artifact["memory_evidence"] = stored.get("evidence")
        self.session_benchmark_artifacts[profile_name] = persisted_artifact
        self.emit_governance_event(
            kind="validated_solution_capture",
            source="server_context.persist_benchmark_artifact",
            action="persist_benchmark_artifact",
            subject_id=profile_name,
            goal_id=str(persisted_artifact.get("artifact_id", "")),
            details={
                "profile_name": profile_name,
                "benchmark_scores": dict(persisted_artifact.get("benchmark_scores") or {}),
                "memory_fact_id": stored.get("id"),
                "memory_sha256": stored.get("sha256"),
            },
            agent_role="benchmark_artifact",
        )
        return persisted_artifact

    def get_benchmark_artifact(self, *, profile_name: str | None = None) -> dict[str, Any] | None:
        if profile_name:
            return self.session_benchmark_artifacts.get(profile_name)
        if self.session_benchmark_artifacts:
            latest_profile_name = next(reversed(self.session_benchmark_artifacts))
            return self.session_benchmark_artifacts.get(latest_profile_name)
        return None

    def get_benchmark_scores(self, *, profile_name: str) -> dict[str, float] | None:
        artifact = self.get_benchmark_artifact(profile_name=profile_name)
        if artifact is None:
            return None
        return dict(artifact.get("benchmark_scores") or {})

    def get_model_catalog(self, *, agent_id: str | None = None) -> dict[str, Any] | None:
        if agent_id:
            return self.session_model_catalogs.get(agent_id)
        if self.session_model_catalogs:
            latest_agent_id = next(reversed(self.session_model_catalogs))
            return self.session_model_catalogs.get(latest_agent_id)
        return None

    def get_model_catalog_status(self, *, agent_id: str | None = None) -> dict[str, Any] | None:
        catalog = self.get_model_catalog(agent_id=agent_id)
        if catalog is None:
            return None

        available_agent_ids = sorted(self.session_model_catalogs)
        resolved_agent_id = str(catalog.get("agent_id") or agent_id or "")
        return {
            "agent_id": resolved_agent_id,
            "available_agent_ids": available_agent_ids,
            "preferred_lanes": list(catalog.get("preferred_lanes", [])),
            "ollama_endpoint": catalog.get("ollama_endpoint"),
            "ollama_access_mode": catalog.get("ollama_access_mode"),
            "summary": dict(catalog.get("summary") or {}),
            "agent_lane_summary": dict(catalog.get("agent_lane_summary") or {}),
            "remote_direct_env_var_present": bool(
                catalog.get("remote_direct_env_var_present", False)
            ),
            "remote_direct_env_error": catalog.get("remote_direct_env_error"),
            "remote_direct_entries": list(catalog.get("remote_direct_entries") or []),
        }

    def persist_governed_route(self, route_trace: dict[str, Any]) -> dict[str, Any]:
        agent_id = str(route_trace.get("request_context", {}).get("agent_id") or "unknown-agent")
        existing_admission = self.session_execution_admissions.get(agent_id)
        if existing_admission and not route_trace.get("execution_admission"):
            route_trace = dict(route_trace)
            route_trace["execution_admission"] = dict(existing_admission)
        normalized_route = dict(route_trace)
        policy_basis = normalized_route.get("policy_basis")
        if not isinstance(policy_basis, dict):
            policy_basis = {}
        route_event_ref = normalize_governance_ref(policy_basis.get("governance_event_ref"))
        route_governance_event = self.get_governance_event(event_ref=route_event_ref)
        if route_governance_event is None:
            emitted = self.emit_governance_event(
                kind="routing_decision",
                source="server_context.persist_governed_route",
                action="persist_governed_route",
                subject_id=agent_id,
                goal_id=str(route_trace.get("route_decision", {}).get("selected_lane", "")),
                details={
                    "decision": route_trace.get("route_decision", {}).get("decision"),
                    "selected_lane": route_trace.get("route_decision", {}).get("selected_lane"),
                    "primary_model": route_trace.get("route_decision", {}).get("primary_model"),
                    "fallback_model": route_trace.get("route_decision", {}).get("fallback_model"),
                },
                agent_role="governed_router",
            )
            route_governance_event = emitted.get("event")
            route_event_ref = normalize_governance_ref(emitted.get("event_ref"))
        align_event_ref = normalize_governance_ref(policy_basis.get("align_governance_event_ref"))
        policy_basis["governance_event_ref"] = route_event_ref
        policy_basis["route_governance_event_ref"] = route_event_ref
        policy_basis["align_governance_event_ref"] = align_event_ref
        policy_basis["related_refs"] = list(route_governance_event.get("related_refs") or []) if route_governance_event else []
        lineage_refs: list[dict[str, Any]] = []
        for item in (
            route_governance_event.get("event_ref") if route_governance_event else None,
            policy_basis.get("align_governance_event_ref"),
            policy_basis.get("governance_event_ref"),
        ):
            normalized = normalize_governance_ref(item)
            if normalized and normalized not in lineage_refs:
                lineage_refs.append(normalized)
        route_decision = normalized_route.get("route_decision")
        if isinstance(route_decision, dict):
            for item in route_decision.get("evidence_refs") or []:
                if isinstance(item, dict) and item not in lineage_refs:
                    lineage_refs.append(item)
        execution_admission = normalized_route.get("execution_admission")
        if isinstance(execution_admission, dict):
            governance_event = execution_admission.get("governance_event")
            if isinstance(governance_event, dict):
                event_ref = normalize_governance_ref(governance_event.get("event_ref"))
                if event_ref and event_ref not in lineage_refs:
                    lineage_refs.append(event_ref)
        policy_basis["evidence_lineage_refs"] = lineage_refs
        normalized_route["policy_basis"] = policy_basis
        normalized_route["route_governance_event"] = route_governance_event
        self.session_governed_routes[agent_id] = normalized_route
        return self.session_governed_routes[agent_id]

    def get_governed_route(self, *, agent_id: str | None = None) -> dict[str, Any] | None:
        if agent_id:
            return self.session_governed_routes.get(agent_id)
        if self.session_governed_routes:
            latest_agent_id = next(reversed(self.session_governed_routes))
            return self.session_governed_routes.get(latest_agent_id)
        return None

    def persist_symbolic_surface(self, symbolic_record: dict[str, Any]) -> dict[str, Any]:
        persisted = dict(symbolic_record)
        surface_id = str(
            persisted.get("surface_id")
            or persisted.get("symbolic_surface", {}).get("surface_id")
            or f"symbolic-{uuid.uuid4().hex[:12]}"
        )
        persisted["surface_id"] = surface_id
        raw_symbolic_surface = persisted.get("symbolic_surface")
        symbolic_surface: dict[str, Any] = (
            dict(raw_symbolic_surface) if isinstance(raw_symbolic_surface, dict) else {}
        )
        raw_relation_edges = symbolic_surface.get("relation_edges")
        relation_edges: list[Any] = raw_relation_edges if isinstance(raw_relation_edges, list) else []
        raw_relation_artifacts = symbolic_surface.get("relation_artifacts")
        relation_artifacts: list[Any] = (
            raw_relation_artifacts if isinstance(raw_relation_artifacts, list) else []
        )
        raw_audit_entries = persisted.get("audit_entries")
        audit_entries: list[Any] = raw_audit_entries if isinstance(raw_audit_entries, list) else []
        governance_event = self.emit_governance_event(
            kind="validated_solution_capture",
            source="server_context.persist_symbolic_surface",
            action="persist_symbolic_surface",
            subject_id=surface_id,
            goal_id=str(persisted.get("goal_id") or "symbolic_surface"),
            details={
                "surface_id": surface_id,
                "relation_count": len(relation_edges),
                "artifact_count": len(relation_artifacts),
                "audit_trace_ids": [
                    str(entry.get("trace_id") or "")
                    for entry in audit_entries
                    if isinstance(entry, dict) and str(entry.get("trace_id") or "")
                ],
                "operator_summary": persisted.get("operator_summary"),
            },
            agent_role="symbolic_surface",
        )
        persisted["governance_event"] = governance_event
        persisted["governance_event_ref"] = governance_event.get("event_ref")
        self.session_symbolic_surfaces[surface_id] = persisted
        return self.session_symbolic_surfaces[surface_id]

    def get_symbolic_surface(self, *, surface_id: str | None = None) -> dict[str, Any] | None:
        if surface_id:
            return self.session_symbolic_surfaces.get(surface_id)
        if self.session_symbolic_surfaces:
            latest_surface_id = next(reversed(self.session_symbolic_surfaces))
            return self.session_symbolic_surfaces.get(latest_surface_id)
        return None

    def persist_execution_admission(
        self,
        *,
        agent_id: str,
        admission_record: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_agent_id = str(agent_id or "unknown-agent")
        persisted = dict(admission_record)
        orchestration_lineage = persisted.get("orchestration_lineage", {})
        if not isinstance(orchestration_lineage, dict):
            orchestration_lineage = {}
        mission_lineage = orchestration_lineage.get("mission")
        if not isinstance(mission_lineage, dict):
            mission_lineage = {}
        self.session_execution_admissions[normalized_agent_id] = persisted

        route_trace = self.session_governed_routes.get(normalized_agent_id)
        related_refs: list[dict[str, str]] = []
        if route_trace is not None:
            updated_route = dict(route_trace)
            updated_route["execution_admission"] = persisted
            self.session_governed_routes[normalized_agent_id] = updated_route
            route_ref = route_trace.get("policy_basis", {}).get("governance_event_ref")
            if isinstance(route_ref, dict) and route_ref.get("event_id"):
                related_refs.append(
                    {
                        "kind": str(route_ref.get("kind") or "routing_decision"),
                        "event_id": str(route_ref.get("event_id") or ""),
                        "trace_id": str(route_ref.get("trace_id") or ""),
                    }
                )

        execution_trace_id = str(persisted.get("audit_refs", {}).get("execution_trace_id") or "")
        if execution_trace_id:
            related_refs.append(
                {
                    "kind": "audit",
                    "event_id": execution_trace_id,
                    "trace_id": execution_trace_id,
                }
            )

        admitted = bool(persisted.get("admitted", False))
        requires_review = bool(persisted.get("requires_operator_review", False))
        governance_event = self.emit_governance_event(
            kind="verification_result",
            source="server_context.persist_execution_admission",
            action="persist_execution_admission",
            status="blocked"
            if not admitted and not requires_review
            else "warning"
            if requires_review
            else "ok",
            severity="critical"
            if not admitted and not requires_review
            else "warning"
            if requires_review
            else "info",
            subject_id=normalized_agent_id,
            goal_id=str(persisted.get("requested_tier") or persisted.get("execution_status") or ""),
            details={
                "execution_status": persisted.get("execution_status"),
                "admission_verdict": persisted.get("admission_verdict"),
                "requested_tier": persisted.get("requested_tier"),
                "effect_classes": list(persisted.get("effect_basis", {}).get("effect_classes", [])),
                "tool_names": list(persisted.get("effect_basis", {}).get("tool_names", [])),
                "selected_lane": persisted.get("route_evidence", {}).get("selected_lane"),
                "route_decision": persisted.get("route_evidence", {}).get("decision"),
                "ingress_decision": persisted.get("ingress_evidence", {}).get("decision"),
                "ingress_blocked_stage": persisted.get("ingress_evidence", {}).get("blocked_stage"),
                "delegation_count": len(orchestration_lineage.get("delegation_events", [])),
                "mission_id": mission_lineage.get("mission_id"),
                "execution_trace_id": execution_trace_id,
            },
            agent_role="execution_admission",
            anomaly_score=1.0
            if not admitted and not requires_review
            else 0.5
            if requires_review
            else 0.0,
            related_refs=related_refs,
        )
        persisted["governance_event"] = governance_event
        witness_observations: list[dict[str, Any]] = []
        route_evidence = persisted.get("route_evidence", {})
        pointer_evidence = persisted.get("pointer_evidence", {})
        approval_details = persisted.get("approval", {})
        approval_requirements = approval_details.get("requirements", [])
        admission_verdict = str(persisted.get("admission_verdict") or "")
        embodied_effect = persisted.get("embodied_effect", {})
        if not isinstance(embodied_effect, dict):
            embodied_effect = {}
        governance_ref = governance_event.get("event_ref")

        route_review_required = any(
            isinstance(requirement, dict)
            and str(requirement.get("type") or "") == "route_review"
            for requirement in approval_requirements
        )
        verification_review_required = any(
            isinstance(requirement, dict)
            and str(requirement.get("type") or "") == "verification_review"
            for requirement in approval_requirements
        )
        embodied_review_required = any(
            isinstance(requirement, dict)
            and str(requirement.get("type") or "") == "embodied_review"
            for requirement in approval_requirements
        )

        if str(route_evidence.get("decision") or "") == "deny":
            witness_observations.append(
                self.record_witness_observation(
                    subject_agent_id=normalized_agent_id,
                    category="routing_anomaly",
                    witness_id="router",
                    severity="critical",
                    confidence=0.95,
                    source="server_context.persist_execution_admission",
                    event_ref=governance_ref,
                    evidence_text="Governed route denied execution admission.",
                    recommended_action="restrict",
                    details={
                        "execution_status": persisted.get("execution_status"),
                        "route_evidence": dict(route_evidence),
                        "embodied_effect": dict(embodied_effect),
                    },
                )
            )
        elif route_review_required:
            witness_observations.append(
                self.record_witness_observation(
                    subject_agent_id=normalized_agent_id,
                    category="routing_anomaly",
                    witness_id="router",
                    severity="warning",
                    confidence=0.82,
                    source="server_context.persist_execution_admission",
                    event_ref=governance_ref,
                    evidence_text="Governed route required operator review before execution.",
                    recommended_action="review",
                    details={
                        "execution_status": persisted.get("execution_status"),
                        "route_evidence": dict(route_evidence),
                        "embodied_effect": dict(embodied_effect),
                    },
                )
            )

        if admission_verdict == "verification_denied":
            witness_observations.append(
                self.record_witness_observation(
                    subject_agent_id=normalized_agent_id,
                    category="verification_failure",
                    witness_id="verifier",
                    severity="critical",
                    confidence=0.95,
                    source="server_context.persist_execution_admission",
                    event_ref=governance_ref,
                    evidence_text="Formal verification denied execution admission.",
                    recommended_action="restrict",
                    details={
                        "execution_status": persisted.get("execution_status"),
                        "verification": dict(persisted.get("verification") or {}),
                        "embodied_effect": dict(embodied_effect),
                    },
                )
            )
        elif verification_review_required and route_review_required:
            witness_observations.append(
                self.record_witness_observation(
                    subject_agent_id=normalized_agent_id,
                    category="verification_review_required",
                    witness_id="verifier",
                    severity="warning",
                    confidence=0.86,
                    source="server_context.persist_execution_admission",
                    event_ref=governance_ref,
                    evidence_text="Formal verification required operator review before execution.",
                    recommended_action="probation",
                    details={
                        "execution_status": persisted.get("execution_status"),
                        "verification": dict(persisted.get("verification") or {}),
                        "embodied_effect": dict(embodied_effect),
                    },
                )
            )

        if embodied_effect:
            function_name = str(embodied_effect.get("function_name") or "unknown")
            if admission_verdict == "embodied_contract_denied":
                witness_observations.append(
                    self.record_witness_observation(
                        subject_agent_id=normalized_agent_id,
                        category="embodied_execution_boundary",
                        witness_id="embodied-guard",
                        severity="critical",
                        confidence=0.96,
                        source="server_context.persist_execution_admission",
                        event_ref=governance_ref,
                        evidence_text=(
                            f"Embodied function '{function_name}' was denied by the packaged supervisory boundary."
                        ),
                        recommended_action="restrict",
                        details={
                            "execution_status": persisted.get("execution_status"),
                            "admission_verdict": admission_verdict,
                            "embodied_effect": dict(embodied_effect),
                            "verification": dict(persisted.get("verification") or {}),
                        },
                    )
                )
            elif embodied_review_required:
                witness_observations.append(
                    self.record_witness_observation(
                        subject_agent_id=normalized_agent_id,
                        category="embodied_review_required",
                        witness_id="embodied-guard",
                        severity="warning",
                        confidence=0.88,
                        source="server_context.persist_execution_admission",
                        event_ref=governance_ref,
                        evidence_text=(
                            f"Embodied function '{function_name}' requires operator review before admission."
                        ),
                        recommended_action="review",
                        details={
                            "execution_status": persisted.get("execution_status"),
                            "admission_verdict": admission_verdict,
                            "embodied_effect": dict(embodied_effect),
                            "approval_requirements": list(approval_requirements),
                        },
                    )
                )

        pointer_failures = []
        if isinstance(pointer_evidence, dict):
            raw_failures = pointer_evidence.get("failures", [])
            if isinstance(raw_failures, list):
                pointer_failures = [failure for failure in raw_failures if isinstance(failure, dict)]

        for failure in pointer_failures:
            status = str(failure.get("status") or "unknown")
            severity = "critical" if status in {"hash_mismatch", "revoked"} else "warning"
            confidence = 0.94 if severity == "critical" else 0.82
            recommended_action = "restrict" if severity == "critical" else "review"
            alias = str(failure.get("alias") or failure.get("pointer") or "unknown-pointer")
            witness_observations.append(
                self.record_witness_observation(
                    subject_agent_id=normalized_agent_id,
                    category="pointer_trust_failure",
                    witness_id="pointer-guard",
                    severity=severity,
                    confidence=confidence,
                    source="server_context.persist_execution_admission",
                    event_ref=governance_ref,
                    evidence_text=(
                        f"Pointer trust validation failed for '{alias}' with status '{status}'."
                    ),
                    recommended_action=recommended_action,
                    details={
                        "execution_status": persisted.get("execution_status"),
                        "pointer_validation": dict(failure),
                    },
                )
            )

        if witness_observations:
            persisted["witness_observations"] = witness_observations
            persisted["witness_status"] = self.get_witness_status(subject_agent_id=normalized_agent_id)
        self.session_execution_admissions[normalized_agent_id] = persisted
        if route_trace is not None:
            updated_route = dict(self.session_governed_routes[normalized_agent_id])
            updated_route["execution_admission"] = persisted
            self.session_governed_routes[normalized_agent_id] = updated_route
        return persisted

    def get_execution_admission(self, *, agent_id: str | None = None) -> dict[str, Any] | None:
        if agent_id:
            return self.session_execution_admissions.get(agent_id)
        if self.session_execution_admissions:
            latest_agent_id = next(reversed(self.session_execution_admissions))
            return self.session_execution_admissions.get(latest_agent_id)
        return None

    def build_runtime_variables(
        self,
        base_variables: dict[str, Any] | None = None,
        *,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        variables = dict(base_variables or {})
        effective_agent_id = agent_id or variables.get("AGENT_ID") or variables.get("agent_id")
        if effective_agent_id:
            variables["AGENT_ID"] = effective_agent_id
            profile = self.get_embedding_profile(agent_id=str(effective_agent_id))
            if profile:
                workload = str(profile.get("workload_profile", {}).get("workload", ""))
                topic_map = {
                    "translation_memory": "hlf_translation_contracts",
                    "repair_pattern_recall": "hlf_repairs",
                    "governance_policy_retrieval": "governance_advisory",
                    "code_pattern_retrieval": "hlf_code_patterns",
                    "agent_routing_context": "hlf_agent_routing",
                    "long_form_standards_ingestion": "hlf_standards",
                }
                variables["_embedding_profile"] = profile
                variables["_embedding_profile_id"] = profile.get("profile_id")
                variables["_embedding_model"] = profile.get("embedding_recommendation", {}).get(
                    "model"
                )
                variables["_embedding_endpoint"] = profile.get("embedding_recommendation", {}).get(
                    "endpoint"
                )
                variables["_embedding_fallback_model"] = profile.get(
                    "fallback_recommendation", {}
                ).get("model")
                variables["_ollama_available"] = profile.get("runtime_status", {}).get(
                    "ollama_available", False
                )
                variables["_embedding_model_runnable"] = profile.get("runtime_status", {}).get(
                    "recommended_model_runnable", False
                )
                if "_memory_context_enabled" not in variables:
                    variables["_memory_context_enabled"] = bool(
                        profile.get("allowed_modes", {}).get("default_enable_memory_context", False)
                    )
                if "_memory_context_topic" not in variables and workload in topic_map:
                    variables["_memory_context_topic"] = topic_map[workload]
            catalog = self.get_model_catalog(agent_id=str(effective_agent_id))
            if catalog:
                variables["_model_catalog"] = catalog
                variables["_model_catalog_summary"] = catalog.get("summary", {})
                variables["_model_lane_summary"] = catalog.get("agent_lane_summary", {})
        variables.setdefault("_pointer_resolver", self.resolve_memory_pointer)
        variables.setdefault("_pointer_resolution_purpose", "execution")
        return variables

    def resolve_memory_pointer(
        self,
        pointer: str,
        *,
        purpose: str = "execution",
        trust_mode: str = "enforce",
        registry_entry: dict[str, Any] | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
        emit_event: bool = True,
        source: str = "server_context.resolve_memory_pointer",
    ) -> dict[str, Any]:
        outcome = self.memory_store.resolve_pointer(
            pointer,
            purpose=purpose,
            registry_entry=registry_entry,
            trust_mode=trust_mode,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
        )
        if emit_event:
            event = self.emit_governance_event(
                kind="pointer_resolution",
                source=source,
                action="resolve_memory_pointer",
                status="ok" if outcome.get("admitted") else "blocked",
                severity="info" if outcome.get("admitted") else "warning",
                subject_id=str((outcome.get("resolution") or {}).get("fact", {}).get("id") or ""),
                goal_id=str(purpose or ""),
                details={
                    "pointer": outcome.get("pointer"),
                    "purpose": outcome.get("purpose"),
                    "trust_mode": outcome.get("trust_mode"),
                    "status": outcome.get("status"),
                    "admitted": outcome.get("admitted"),
                    "reason": outcome.get("reason", ""),
                    "trust_tier": outcome.get("trust_tier", "unknown"),
                    "governance_status": outcome.get("governance_status", "unknown"),
                    "freshness_status": outcome.get("freshness_status", "unknown"),
                    "fact_sha256": str((outcome.get("resolution") or {}).get("fact", {}).get("sha256") or ""),
                },
                agent_role="memory_pointer_resolution",
            )
            outcome["governance_event"] = event
        return outcome

    def _find_memory_fact(
        self,
        *,
        entry_kind: str,
        artifact_id: str | None = None,
        sha256: str | None = None,
    ) -> dict[str, Any] | None:
        for fact in self.memory_store.query_facts(
            entry_kind=entry_kind,
            include_stale=True,
            include_superseded=True,
            include_revoked=True,
        ):
            metadata = dict(fact.get("metadata") or {})
            if artifact_id and str(metadata.get("artifact_id") or "") == artifact_id:
                return fact
            if sha256 and str(fact.get("sha256") or "") == sha256:
                return fact
        return None

    def sync_verified_weekly_artifacts_to_memory(
        self,
        *,
        metrics_dir: str | Path | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        resolved_metrics_dir = (
            Path(metrics_dir).expanduser() if isinstance(metrics_dir, (str, Path)) and metrics_dir else None
        )
        artifacts = load_verified_weekly_artifacts(
            resolved_metrics_dir,
            verified_only=True,
            limit=limit,
        )
        synced: list[dict[str, Any]] = []
        for artifact in artifacts:
            memory_record = build_weekly_artifact_memory_record(
                artifact,
                artifact_path=(resolved_metrics_dir / "weekly_pipeline_latest.json")
                if resolved_metrics_dir
                else None,
            )
            if memory_record is None:
                continue
            artifact_id = str(memory_record["metadata"].get("artifact_id") or "")
            existing = self._find_memory_fact(entry_kind="weekly_artifact", artifact_id=artifact_id)
            if existing is not None:
                synced.append(
                    {
                        "artifact_id": artifact_id,
                        "status": "existing",
                        "memory_ref": {
                            "id": existing.get("id"),
                            "sha256": existing.get("sha256"),
                        },
                        "memory_evidence": existing.get("evidence"),
                    }
                )
                continue
            stored = self.memory_store.store(
                memory_record["content"],
                topic=str(memory_record["topic"]),
                confidence=float(memory_record["confidence"]),
                provenance=str(memory_record["provenance"]),
                tags=list(memory_record["tags"]),
                entry_kind=str(memory_record["entry_kind"]),
                metadata=dict(memory_record["metadata"]),
            )
            synced.append(
                {
                    "artifact_id": artifact_id,
                    "status": "stored" if stored.get("stored") else "existing",
                    "memory_ref": {
                        "id": stored.get("id"),
                        "sha256": stored.get("sha256"),
                    },
                    "memory_evidence": stored.get("evidence"),
                }
            )
        return {
            "status": "ok",
            "count": len(synced),
            "artifacts": synced,
            "metrics_dir": str(resolved_metrics_dir) if resolved_metrics_dir else None,
        }

    def recall_governed_evidence(
        self,
        query: str,
        *,
        top_k: int = 5,
        domain: str | None = None,
        solution_kind: str | None = None,
        metrics_dir: str | Path | None = None,
        include_weekly_artifacts: bool = True,
        include_hks: bool = True,
        include_witness_evidence: bool = True,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = True,
        include_archive: bool = False,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        normalized_purpose = str(purpose or "default").strip().lower() or "default"
        weekly_sync = {
            "status": "skipped",
            "count": 0,
            "artifacts": [],
            "metrics_dir": str(metrics_dir) if metrics_dir else None,
        }
        if include_weekly_artifacts:
            weekly_sync = self.sync_verified_weekly_artifacts_to_memory(
                metrics_dir=metrics_dir,
                limit=max(top_k, 10),
            )

        allowed_entry_kinds: set[str] = set()
        if include_hks:
            allowed_entry_kinds.add("hks_exemplar")
        if include_witness_evidence:
            allowed_entry_kinds.add("witness_observation")
        if include_weekly_artifacts:
            allowed_entry_kinds.add("weekly_artifact")

        recalled = self.memory_store.query(
            query,
            top_k=max(top_k * 4, top_k),
            domain=domain,
            solution_kind=solution_kind,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
            include_archive=include_archive,
            purpose=normalized_purpose,
        )
        surface_results = [
            result
            for result in recalled.get("results", [])
            if str(result.get("entry_kind") or "") in allowed_entry_kinds
        ]
        results = surface_results[:top_k]
        recall_summary = _build_governed_recall_summary(
            results,
            include_archive=include_archive,
            require_provenance=require_provenance,
            allowed_entry_kinds=allowed_entry_kinds,
        )
        retrieval_contract = dict(recalled.get("retrieval_contract") or {})
        retrieval_contract["surface_allowed_entry_kinds"] = sorted(allowed_entry_kinds)
        retrieval_contract["surface_result_count"] = len(results)
        retrieval_contract["surface_filtered_out_count"] = max(
            0,
            len(recalled.get("results", [])) - len(surface_results),
        )
        retrieval_contract["surface_truncated_count"] = max(0, len(surface_results) - len(results))
        governed_hks_contract = dict(recalled.get("governed_hks_contract") or {})
        governance_event = self.emit_governance_event(
            kind="memory_governance",
            source="server_context.recall_governed_evidence",
            action="recall_governed_evidence",
            status="ok",
            severity="info",
            subject_id=str(results[0].get("id") or "") if results else "",
            goal_id=query,
            details={
                "query": query,
                "result_count": len(results),
                "top_k": top_k,
                "domain": domain,
                "solution_kind": solution_kind,
                "entry_kinds": sorted(allowed_entry_kinds),
                "entry_kind_counts": recall_summary.get("entry_kind_counts"),
                "weekly_sync_count": int(weekly_sync.get("count") or 0),
                "require_provenance": require_provenance,
                "purpose": normalized_purpose,
                "archive_visibility": recall_summary.get("archive_visibility"),
                "admission_decision_counts": recall_summary.get("admission_decision_counts"),
                "archived_result_count": recall_summary.get("archived_result_count"),
            },
            agent_role="governed_recall",
        )
        payload = {
            "status": "ok",
            "recall_kind": "governed_recall",
            "query": query,
            "count": len(results),
            "results": results,
            "purpose": normalized_purpose,
            "entry_kinds": sorted(allowed_entry_kinds),
            "retrieval_contract": retrieval_contract,
            "governed_hks_contract": governed_hks_contract,
            "recall_summary": recall_summary,
            "weekly_sync": weekly_sync,
            "governance_event": governance_event,
            "evidence_refs": [governance_event.get("event_ref")],
            "operator_summary": (
                f"Governed recall returned {len(results)} result(s) for query '{query}' across "
                f"{', '.join(sorted(allowed_entry_kinds)) or 'governed evidence'} with "
                f"runtime purpose '{normalized_purpose}', "
                f"{int(weekly_sync.get('count') or 0)} weekly artifact sync entrie(s), "
                f"{int(recall_summary.get('active_result_count') or 0)} active result(s), and "
                f"{int(recall_summary.get('archived_result_count') or 0)} archived result(s) "
                f"visible under archive mode '{recall_summary.get('archive_visibility')}'."
            ),
        }
        return self.persist_governed_recall(
            payload,
            source="server_context.recall_governed_evidence",
        )

    def persist_media_evidence(
        self,
        media_evidence: list[MediaEvidenceRecord],
    ) -> list[dict[str, Any]]:
        persisted: list[dict[str, Any]] = []
        for item in media_evidence:
            summary = (
                item.operator_summary
                or f"Normalized {item.media_type} evidence for governed review"
            )
            metadata = {
                **item.to_dict(),
                "artifact_id": item.artifact_id,
                "operator_summary": summary,
                "provenance": dict(item.provenance),
                "governed_evidence": {
                    "source_class": "media_evidence",
                    "source_type": "multimodal_evidence",
                    "source": item.provenance.get("source")
                    or item.provenance.get("collector")
                    or "server_context.persist_media_evidence",
                    "source_path": item.source_path or item.provenance.get("artifact_path"),
                    "artifact_id": item.artifact_id,
                    "collector": item.provenance.get("collector")
                    or "server_context.persist_media_evidence",
                    "collected_at": item.collected_at,
                    "confidence": item.confidence,
                    "trust_tier": item.trust_tier,
                    "operator_summary": summary,
                },
            }
            stored = self.memory_store.store(
                item.render_content(),
                topic="hlf_media_evidence",
                confidence=float(item.confidence),
                provenance=str(
                    item.provenance.get("collector")
                    or item.provenance.get("source")
                    or "server_context.persist_media_evidence"
                ),
                tags=["media", item.media_type, "governed"],
                entry_kind="media_evidence",
                metadata=metadata,
            )
            evidence = stored.get("evidence")
            memory_ref = {"id": stored.get("id"), "sha256": stored.get("sha256")}
            if evidence is None:
                existing = self._find_memory_fact(
                    entry_kind="media_evidence",
                    artifact_id=item.artifact_id,
                    sha256=str(stored.get("sha256") or item.sha256),
                )
                if existing is not None:
                    evidence = existing.get("evidence")
                    memory_ref = {
                        "id": existing.get("id"),
                        "sha256": existing.get("sha256"),
                    }
            payload = {
                **item.to_dict(),
                "memory_ref": memory_ref,
                "memory_evidence": evidence,
            }
            self.session_media_evidence[item.artifact_id] = payload
            persisted.append(payload)
        return persisted

    def list_media_evidence(self, *, media_type: str | None = None) -> dict[str, Any]:
        evidence = list(self.session_media_evidence.values())
        if media_type:
            evidence = [item for item in evidence if item.get("media_type") == media_type]
        evidence.sort(key=lambda item: str(item.get("collected_at", "")), reverse=True)
        return {"media_evidence": evidence, "count": len(evidence)}

    def get_media_evidence(self, artifact_id: str) -> dict[str, Any] | None:
        return self.session_media_evidence.get(artifact_id)

    def create_dream_proposal(
        self,
        *,
        finding_ids: list[str],
        title: str,
        summary: str,
        lane: str = "bridge",
        proposal_text: str = "",
        verification_plan: list[str] | None = None,
    ) -> dict[str, Any]:
        allowed_lanes = {"vision", "bridge", "current_truth"}
        normalized_lane = str(lane or "bridge")
        if normalized_lane not in allowed_lanes:
            return {
                "status": "error",
                "error": "invalid_lane",
                "allowed_lanes": sorted(allowed_lanes),
            }

        normalized_finding_ids = [str(item) for item in finding_ids if str(item)]
        if not normalized_finding_ids:
            return {"status": "error", "error": "finding_ids_required"}

        findings: list[dict[str, Any]] = []
        missing_finding_ids: list[str] = []
        for finding_id in normalized_finding_ids:
            finding = self.get_dream_finding(finding_id)
            if finding is None:
                missing_finding_ids.append(finding_id)
                continue
            findings.append(finding)
        if missing_finding_ids:
            return {
                "status": "error",
                "error": "dream_findings_not_found",
                "missing_finding_ids": missing_finding_ids,
            }

        created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        seed = "|".join([created_at, normalized_lane, *normalized_finding_ids, uuid.uuid4().hex])
        proposal_id = f"dream-proposal-{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"

        normalized_plan = [
            str(item).strip() for item in (verification_plan or []) if str(item).strip()
        ]
        if not normalized_plan:
            normalized_plan = [
                "produce an explicit verification artifact before any promotion decision",
                "record operator review before promote transition",
            ]

        cited_media_evidence_ids = sorted(
            {
                str(ref.get("artifact_id") or "")
                for finding in findings
                for ref in (finding.get("evidence_refs") or [])
                if str(ref.get("kind") or "") == "media_evidence"
                and str(ref.get("artifact_id") or "")
            }
        )
        cited_memory_fact_ids = [
            str((finding.get("memory_ref") or {}).get("id") or "")
            for finding in findings
            if str((finding.get("memory_ref") or {}).get("id") or "")
        ]
        witness_record_ids = sorted(
            {
                str((finding.get("provenance") or {}).get("witness_record_id") or "")
                for finding in findings
                if str((finding.get("provenance") or {}).get("witness_record_id") or "")
            }
        )
        citation_chain = {
            "observe": {
                "finding_ids": normalized_finding_ids,
                "memory_fact_ids": cited_memory_fact_ids,
                "media_evidence_ids": cited_media_evidence_ids,
                "witness_record_ids": witness_record_ids,
            },
            "propose": {
                "proposal_id": proposal_id,
                "lane": normalized_lane,
                "title": title,
                "summary": summary,
                "proposal_text": proposal_text,
            },
            "verify": {
                "required": True,
                "status": "pending",
                "verification_plan": normalized_plan,
                "verification_artifact_ids": [],
            },
            "promote": {
                "eligible": False,
                "status": "blocked_pending_verify",
                "blocked_by": ["verify_stage_incomplete", "operator_gate_required"],
            },
        }
        proposal = {
            "proposal_id": proposal_id,
            "created_at": created_at,
            "lane": normalized_lane,
            "title": title,
            "summary": summary,
            "proposal_text": proposal_text,
            "status": "proposed",
            "advisory_only": True,
            "cited_finding_ids": normalized_finding_ids,
            "cited_media_evidence_ids": cited_media_evidence_ids,
            "citation_chain": citation_chain,
            "promotion_gate": citation_chain["promote"],
        }
        stored = self.memory_store.store(
            json.dumps(proposal, ensure_ascii=False, sort_keys=True),
            topic="hlf_dream_proposals",
            confidence=0.72,
            provenance="server_context.create_dream_proposal",
            tags=["dream", "proposal", normalized_lane],
            entry_kind="dream_proposal",
            metadata={
                **proposal,
                "artifact_id": proposal_id,
                "operator_summary": summary,
                "governed_evidence": {
                    "source_class": "dream_proposal",
                    "source_type": "proposal_lane",
                    "source": "server_context.create_dream_proposal",
                    "artifact_id": proposal_id,
                    "collector": "server_context.create_dream_proposal",
                    "collected_at": created_at,
                    "trust_tier": "advisory",
                    "operator_summary": summary,
                },
            },
        )
        governance_event = self.emit_governance_event(
            kind="proposal_lane",
            source="server_context.create_dream_proposal",
            action="create_dream_proposal",
            status="pending",
            severity="info",
            subject_id=proposal_id,
            goal_id=normalized_lane,
            details={
                "cited_finding_ids": normalized_finding_ids,
                "cited_media_evidence_ids": cited_media_evidence_ids,
                "verification_plan": normalized_plan,
            },
            agent_role="proposal_lane",
        )
        payload = {
            **proposal,
            "memory_ref": {"id": stored.get("id"), "sha256": stored.get("sha256")},
            "memory_evidence": stored.get("evidence"),
            "governance_event": governance_event,
        }
        self.session_dream_proposals[proposal_id] = payload
        return {"status": "ok", "proposal": payload}

    def list_dream_proposals(self, *, lane: str | None = None) -> dict[str, Any]:
        proposals = list(self.session_dream_proposals.values())
        if lane:
            proposals = [item for item in proposals if item.get("lane") == lane]
        proposals.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return {"proposals": proposals, "count": len(proposals)}

    def get_dream_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        return self.session_dream_proposals.get(proposal_id)

    def run_dream_cycle(
        self,
        *,
        metrics_dir: str | None = None,
        max_artifacts: int = 3,
        max_facts: int = 10,
        media_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
        cycle_id = f"dream-cycle-{hashlib.sha256((created_at + uuid.uuid4().hex).encode('utf-8')).hexdigest()[:12]}"

        try:
            normalized_media = normalize_media_evidence(media_evidence)
        except ValueError as exc:
            return {
                "status": "error",
                "error": "invalid_media_evidence",
                "validation_errors": [str(exc)],
            }

        persisted_media = self.persist_media_evidence(normalized_media) if normalized_media else []

        resolved_metrics_dir = Path(metrics_dir).expanduser() if metrics_dir else None
        self.sync_verified_weekly_artifacts_to_memory(
            metrics_dir=resolved_metrics_dir,
            limit=max_artifacts,
        )
        weekly_artifacts = load_verified_weekly_artifacts(
            resolved_metrics_dir,
            verified_only=False,
        )[: max(0, max_artifacts)]

        memory_candidates = self.memory_store.query_facts(
            include_stale=False,
            include_superseded=False,
            include_revoked=False,
        )
        allowed_entry_kinds = {
            "benchmark_artifact",
            "hks_exemplar",
            "media_evidence",
            "witness_observation",
        }
        memory_facts = [
            fact for fact in memory_candidates if str(fact.get("entry_kind")) in allowed_entry_kinds
        ][: max(0, max_facts)]

        witness_record = self.record_witness_observation(
            subject_agent_id=cycle_id,
            category="dream_cycle_run",
            witness_id="dream-cycle",
            severity="info",
            confidence=1.0,
            source="server_context.run_dream_cycle",
            evidence_text="Bounded dream-cycle run over governed evidence.",
            recommended_action="observe",
            details={
                "artifact_count": len(weekly_artifacts),
                "memory_fact_count": len(memory_facts),
                "media_artifact_count": len(persisted_media),
            },
            negative=False,
        )

        findings = build_dream_findings(
            cycle_id=cycle_id,
            created_at=created_at,
            weekly_artifacts=weekly_artifacts,
            memory_facts=memory_facts,
            media_evidence=normalized_media,
            witness_record_id=str(witness_record["governance_event"]["event"]["event_id"]),
        )

        persisted_findings: list[dict[str, Any]] = []
        for finding in findings:
            finding_dict = finding.to_dict()
            finding_record = self.memory_store.store(
                finding.render_content(),
                topic="hlf_dream_findings",
                confidence=float(finding.confidence),
                provenance="server_context.run_dream_cycle",
                tags=["dream", finding.topic, "advisory"],
                entry_kind="dream_finding",
                metadata={
                    **finding_dict,
                    "artifact_id": finding.finding_id,
                    "operator_summary": finding.summary,
                    "provenance": dict(finding.provenance),
                    "governed_evidence": {
                        "source_class": "dream_finding",
                        "source_type": "dream_cycle",
                        "source": "server_context.run_dream_cycle",
                        "artifact_id": finding.finding_id,
                        "collector": "server_context.run_dream_cycle",
                        "collected_at": finding.created_at,
                        "trust_tier": "advisory",
                        "operator_summary": finding.summary,
                    },
                },
            )
            finding_payload = {
                **finding_dict,
                "memory_ref": {
                    "id": finding_record.get("id"),
                    "sha256": finding_record.get("sha256"),
                },
                "memory_evidence": finding_record.get("evidence"),
            }
            self.session_dream_findings[finding.finding_id] = finding_payload
            persisted_findings.append(finding_payload)

        report = DreamCycleReport(
            cycle_id=cycle_id,
            started_at=created_at,
            completed_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
            input_window="bounded_governed_recent",
            artifact_count=len(weekly_artifacts) + len(memory_facts),
            media_artifact_count=len(persisted_media),
            finding_count=len(persisted_findings),
            high_confidence_count=sum(
                1 for finding in persisted_findings if finding["confidence"] >= 0.8
            ),
            status="completed",
            witness_record_id=str(witness_record["governance_event"]["event"]["event_id"]),
            artifact_ids=[str(artifact.get("artifact_id", "")) for artifact in weekly_artifacts],
            finding_ids=[finding["finding_id"] for finding in persisted_findings],
        )
        report_dict = report.to_dict()
        report_record = self.memory_store.store(
            json.dumps(report_dict, ensure_ascii=False, sort_keys=True),
            topic="hlf_dream_cycles",
            confidence=1.0,
            provenance="server_context.run_dream_cycle",
            tags=["dream", "cycle", "advisory"],
            entry_kind="dream_cycle_report",
            metadata={
                **report_dict,
                "artifact_id": cycle_id,
                "operator_summary": (
                    f"Dream cycle {cycle_id} completed with {report.finding_count} finding(s)."
                ),
                "provenance": {
                    "source_type": "dream_cycle",
                    "source": "server_context.run_dream_cycle",
                    "collector": "server_context.run_dream_cycle",
                    "collected_at": report.completed_at,
                },
                "governed_evidence": {
                    "source_class": "dream_cycle_report",
                    "source_type": "dream_cycle",
                    "source": "server_context.run_dream_cycle",
                    "artifact_id": cycle_id,
                    "collector": "server_context.run_dream_cycle",
                    "collected_at": report.completed_at,
                    "trust_tier": "advisory",
                    "operator_summary": (
                        f"Dream cycle {cycle_id} completed with {report.finding_count} finding(s)."
                    ),
                },
            },
        )
        governance_event = self.emit_governance_event(
            kind="dream_cycle",
            source="server_context.run_dream_cycle",
            action="run_dream_cycle",
            subject_id=cycle_id,
            goal_id="hlf_dream_cycle",
            details={
                "report": report_dict,
                "memory_report_id": report_record.get("id"),
                "memory_report_sha256": report_record.get("sha256"),
            },
            related_refs=[
                {
                    "kind": "witness_observation",
                    "event_id": str(witness_record["governance_event"]["event"]["event_id"]),
                    "trace_id": str(
                        witness_record["governance_event"]["event"].get("trace_id", "")
                    ),
                }
            ],
            agent_role="dream_cycle",
        )
        report_payload = {
            **report_dict,
            "memory_ref": {"id": report_record.get("id"), "sha256": report_record.get("sha256")},
            "memory_evidence": report_record.get("evidence"),
            "governance_event": governance_event,
        }
        self.session_dream_cycles[cycle_id] = report_payload
        return {
            "status": "ok",
            "report": report_payload,
            "findings": persisted_findings,
            "media_evidence": persisted_media,
            "advisory_only": True,
        }

    def list_dream_findings(
        self,
        *,
        cycle_id: str | None = None,
        topic: str | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        findings = list(self.session_dream_findings.values())
        if cycle_id:
            findings = [finding for finding in findings if finding.get("cycle_id") == cycle_id]
        if topic:
            findings = [finding for finding in findings if finding.get("topic") == topic]
        findings = [
            finding
            for finding in findings
            if float(finding.get("confidence", 0.0)) >= min_confidence
        ]
        findings.sort(key=lambda finding: str(finding.get("created_at", "")), reverse=True)
        return {"findings": findings, "count": len(findings)}

    def get_dream_finding(self, finding_id: str) -> dict[str, Any] | None:
        return self.session_dream_findings.get(finding_id)

    def get_dream_cycle_status(self) -> dict[str, Any]:
        cycles = list(self.session_dream_cycles.values())
        findings = list(self.session_dream_findings.values())
        latest_cycle = cycles[-1] if cycles else None
        return {
            "total_cycles": len(cycles),
            "total_findings": len(findings),
            "total_media_evidence": len(self.session_media_evidence),
            "total_proposals": len(self.session_dream_proposals),
            "high_confidence_findings": sum(
                1 for finding in findings if float(finding.get("confidence", 0.0)) >= 0.8
            ),
            "latest_cycle": latest_cycle,
        }

    def summarize_provenance_contract(
        self,
        *,
        metrics_dir: str | None = None,
        memory_limit: int = 8,
        governance_limit: int = 12,
    ) -> dict[str, Any]:
        memory_facts = self.memory_store.all_facts()
        memory_entry_kind_counts: dict[str, int] = {}
        memory_state_counts: dict[str, int] = {
            "active": 0,
            "stale": 0,
            "superseded": 0,
            "revoked": 0,
            "tombstoned": 0,
        }
        recent_memory_facts: list[dict[str, Any]] = []
        pointer_chain_entries: list[dict[str, Any]] = []
        superseding_pointer_count = 0

        for fact in memory_facts:
            entry_kind = str(fact.get("entry_kind") or "fact")
            memory_entry_kind_counts[entry_kind] = memory_entry_kind_counts.get(entry_kind, 0) + 1

            evidence = dict(fact.get("evidence") or {})
            metadata = dict(fact.get("metadata") or {})
            state = str(evidence.get("state") or "active")
            if state not in memory_state_counts:
                memory_state_counts[state] = 0
            memory_state_counts[state] += 1

            pointer_alias = f"{fact.get('topic') or 'general'}-{fact.get('id') or 'entry'}"
            pointer = build_pointer_ref(pointer_alias, str(fact.get("sha256") or ""))
            supersedes = str(evidence.get("supersedes") or fact.get("supersedes_sha256") or "")
            if supersedes:
                superseding_pointer_count += 1

            if len(pointer_chain_entries) < max(1, memory_limit):
                pointer_chain_entries.append(
                    {
                        "id": fact.get("id"),
                        "topic": fact.get("topic"),
                        "sha256": fact.get("sha256"),
                        "pointer": pointer,
                        "pointer_alias": pointer_alias,
                        "state": state,
                        "freshness_status": evidence.get("freshness_status"),
                        "revoked": evidence.get("revoked", False),
                        "tombstoned": evidence.get("tombstoned", False),
                        "superseded": evidence.get("superseded", False),
                        "supersedes": supersedes,
                        "trust_tier": evidence.get("trust_tier"),
                        "artifact_id": evidence.get("artifact_id"),
                    }
                )

            if len(recent_memory_facts) >= max(1, memory_limit):
                continue

            recent_memory_facts.append(
                {
                    "id": fact.get("id"),
                    "entry_kind": entry_kind,
                    "topic": fact.get("topic"),
                    "sha256": fact.get("sha256"),
                    "confidence": fact.get("confidence"),
                    "created_at": fact.get("created_at"),
                    "operator_summary": metadata.get("operator_summary")
                    or evidence.get("operator_summary")
                    or metadata.get("summary")
                    or "",
                    "source": evidence.get("source") or fact.get("provenance"),
                    "trust_tier": evidence.get("trust_tier"),
                    "artifact_id": evidence.get("artifact_id"),
                    "provenance_grade": evidence.get("provenance_grade"),
                    "pointer": pointer,
                    "state": state,
                    "operator_identity": evidence.get("operator_identity")
                    or {
                        "operator_id": str(metadata.get("operator_id") or ""),
                        "operator_display_name": str(metadata.get("operator_display_name") or ""),
                        "operator_channel": str(metadata.get("operator_channel") or ""),
                    },
                    "freshness_status": evidence.get("freshness_status"),
                    "revoked": evidence.get("revoked", False),
                    "tombstoned": evidence.get("tombstoned", False),
                    "superseded": evidence.get("superseded", False),
                    "supersedes": supersedes,
                    "event_ref": metadata.get("event_ref"),
                }
            )

        governance_events = self.recent_governance_events(limit=max(1, governance_limit))
        recent_governance_events = [
            {
                "kind": event.get("kind"),
                "action": event.get("action"),
                "status": event.get("status"),
                "severity": event.get("severity"),
                "source": event.get("source"),
                "subject_id": event.get("subject_id"),
                "goal_id": event.get("goal_id"),
                "timestamp": event.get("timestamp"),
                "event_ref": event.get("event_ref"),
            }
            for event in governance_events
        ]

        witness_subjects = self.list_witness_subjects().get("subjects", [])
        witness_summary = {
            "subject_count": len(witness_subjects),
            "watched_count": sum(
                1 for subject in witness_subjects if subject.get("trust_state") == "watched"
            ),
            "probation_count": sum(
                1 for subject in witness_subjects if subject.get("trust_state") == "probation"
            ),
            "restricted_count": sum(
                1 for subject in witness_subjects if subject.get("trust_state") == "restricted"
            ),
            "subjects": witness_subjects[:5],
        }

        resolved_metrics_dir = Path(metrics_dir).expanduser() if metrics_dir else None
        weekly_evidence_summary = summarize_weekly_artifacts(resolved_metrics_dir)
        persona_contract_summary = weekly_evidence_summary.get("persona_review_summary", {})

        return {
            "contract_version": "1.0",
            "summary": {
                "memory_fact_count": len(memory_facts),
                "memory_topic_count": len({str(fact.get("topic") or "") for fact in memory_facts}),
                "active_memory_count": memory_state_counts.get("active", 0),
                "stale_memory_count": memory_state_counts.get("stale", 0),
                "superseded_memory_count": memory_state_counts.get("superseded", 0),
                "revoked_memory_count": memory_state_counts.get("revoked", 0),
                "tombstoned_memory_count": memory_state_counts.get("tombstoned", 0),
                "governance_event_count": len(self.governance_events),
                "witness_subject_count": witness_summary["subject_count"],
                "active_profile_count": len(self.session_profiles),
                "active_model_catalog_count": len(self.session_model_catalogs),
                "active_translation_contract_count": len(self.session_translation_contracts),
                "active_governed_recall_count": len(self.session_governed_recalls),
                "active_hks_evaluation_count": len(self.session_hks_evaluations),
                "active_hks_external_compare_count": len(self.session_hks_external_compares),
                "active_hks_weekly_refresh_count": len(self.session_hks_weekly_refreshes),
                "active_internal_workflow_count": len(self.session_internal_workflows),
                "active_route_count": len(self.session_governed_routes),
                "active_media_evidence_count": len(self.session_media_evidence),
                "pointer_count": len(memory_facts),
                "active_pointer_count": memory_state_counts.get("active", 0),
                "revoked_pointer_count": memory_state_counts.get("revoked", 0),
                "tombstoned_pointer_count": memory_state_counts.get("tombstoned", 0),
                "superseded_pointer_count": memory_state_counts.get("superseded", 0),
                "stale_pointer_count": memory_state_counts.get("stale", 0),
                "weekly_artifact_count": weekly_evidence_summary.get("artifact_count", 0),
                "weekly_distribution_eligible_count": weekly_evidence_summary.get(
                    "distribution_eligible_count", 0
                ),
                "weekly_persona_review_artifact_count": persona_contract_summary.get(
                    "artifact_count", 0
                ),
                "weekly_pending_persona_gate_count": persona_contract_summary.get(
                    "pending_gate_count", 0
                ),
            },
            "memory_stats": self.memory_store.stats(),
            "memory_entry_kind_counts": memory_entry_kind_counts,
            "memory_state_counts": memory_state_counts,
            "recent_memory_facts": recent_memory_facts,
            "pointer_chain_summary": {
                "pointer_count": len(memory_facts),
                "active_pointer_count": memory_state_counts.get("active", 0),
                "revoked_pointer_count": memory_state_counts.get("revoked", 0),
                "tombstoned_pointer_count": memory_state_counts.get("tombstoned", 0),
                "superseded_pointer_count": memory_state_counts.get("superseded", 0),
                "stale_pointer_count": memory_state_counts.get("stale", 0),
                "superseding_pointer_count": superseding_pointer_count,
                "recent_pointers": pointer_chain_entries,
            },
            "recent_governance_events": recent_governance_events,
            "witness_summary": witness_summary,
            "weekly_evidence_summary": weekly_evidence_summary,
            "persona_contract_summary": persona_contract_summary,
            "session_surface_counts": {
                "profiles": len(self.session_profiles),
                "model_catalogs": len(self.session_model_catalogs),
                "benchmark_artifacts": len(self.session_benchmark_artifacts),
                "translation_contracts": len(self.session_translation_contracts),
                "governed_recalls": len(self.session_governed_recalls),
                "hks_evaluations": len(self.session_hks_evaluations),
                "hks_external_compares": len(self.session_hks_external_compares),
                "hks_weekly_refreshes": len(self.session_hks_weekly_refreshes),
                "internal_workflows": len(self.session_internal_workflows),
                "governed_routes": len(self.session_governed_routes),
                "execution_admissions": len(self.session_execution_admissions),
                "media_evidence": len(self.session_media_evidence),
                "dream_cycles": len(self.session_dream_cycles),
                "dream_findings": len(self.session_dream_findings),
                "dream_proposals": len(self.session_dream_proposals),
            },
        }


def build_server_context() -> ServerContext:
    align_governor = AlignGovernor()
    return ServerContext(
        compiler=HLFCompiler(),
        formatter=HLFFormatter(),
        linter=HLFLinter(),
        runtime=HLFRuntime(),
        bytecoder=HLFBytecode(),
        benchmark=HLFBenchmark(),
        memory_store=RAGMemory(),
        instinct_mgr=InstinctLifecycle(),
        host_registry=HostFunctionRegistry(),
        tool_registry=ToolRegistry(),
        align_governor=align_governor,
        formal_verifier=FormalVerifier(),
        ingress_controller=GovernedIngressController(align_governor=align_governor),
        session_profiles={},
        session_model_catalogs={},
        session_benchmark_artifacts={},
        session_translation_contracts={},
        session_governed_recalls={},
        session_hks_evaluations={},
        session_hks_external_compares={},
        session_hks_weekly_refreshes={},
        session_internal_workflows={},
        session_governed_routes={},
        session_execution_admissions={},
        session_symbolic_surfaces={},
        session_media_evidence={},
        session_dream_cycles={},
        session_dream_findings={},
        session_dream_proposals={},
        witness_governance=WitnessGovernance(),
        approval_ledger=ApprovalLedger(),
        audit_chain=AuditChain(),
        daemon_manager=DaemonManager(),
        governance_events=deque(maxlen=250),
    )


def check_governance_manifest(logger: logging.Logger) -> None:
    """Warn if governance files have drifted from MANIFEST.sha256."""
    gov_dir = Path(__file__).resolve().parents[1] / "governance"
    manifest_path = gov_dir / "MANIFEST.sha256"
    if not manifest_path.is_file():
        return

    expected: dict[str, str] = {}
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    expected[parts[1]] = parts[0]

    drift: list[str] = []
    for filename, expected_hash in expected.items():
        path = gov_dir / filename
        if not path.is_file():
            drift.append(f"{filename}: missing")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            drift.append(f"{filename}: hash mismatch")

    if drift:
        logger.warning(
            "Governance file drift detected (MANIFEST.sha256): %s",
            ", ".join(drift),
        )
