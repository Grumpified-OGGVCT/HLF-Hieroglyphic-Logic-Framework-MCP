from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hlf_mcp.dream_cycle import DreamCycleReport, build_dream_findings
from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.approval_ledger import ApprovalLedger
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.governance_events import (
    GovernanceEvent,
    GovernanceEventKind,
    GovernanceSeverity,
    GovernanceStatus,
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
from hlf_mcp.weekly_artifacts import load_verified_weekly_artifacts, summarize_weekly_artifacts


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
    session_profiles: dict[str, dict[str, Any]]
    session_model_catalogs: dict[str, dict[str, Any]]
    session_benchmark_artifacts: dict[str, dict[str, Any]]
    session_governed_routes: dict[str, dict[str, Any]]
    session_media_evidence: dict[str, dict[str, Any]]
    session_dream_cycles: dict[str, dict[str, Any]]
    session_dream_findings: dict[str, dict[str, Any]]
    session_dream_proposals: dict[str, dict[str, Any]]
    witness_governance: WitnessGovernance
    approval_ledger: ApprovalLedger
    audit_chain: AuditChain
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
            related_refs=related_refs or [],
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
        observation = WitnessObservation(
            witness_id=witness_id,
            subject_agent_id=subject_agent_id,
            goal_id=goal_id,
            session_id=session_id,
            category=category,
            severity=severity,
            confidence=confidence,
            source=source,
            event_ref=dict(event_ref or {}),
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
        )

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
    ) -> dict[str, Any]:
        normalized_tests: list[HKSTestEvidence] = []
        for item in tests or []:
            if isinstance(item, HKSTestEvidence):
                normalized_tests.append(item)
            else:
                normalized_tests.append(
                    HKSTestEvidence(
                        name=str(item.get("name", "validation")),
                        passed=bool(item.get("passed", False)),
                        exit_code=item.get("exit_code"),
                        counts=item.get("counts"),
                        details=item.get("details"),
                    )
                )

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
        stored = self.memory_store.store(
            json.dumps(persisted_artifact, ensure_ascii=False, sort_keys=True),
            topic="hlf_benchmark_artifacts",
            confidence=1.0,
            provenance="server_context.persist_benchmark_artifact",
            tags=["hlf", "benchmark", profile_name],
            entry_kind="benchmark_artifact",
            metadata={
                "profile_name": profile_name,
                "benchmark_scores": dict(persisted_artifact.get("benchmark_scores") or {}),
                "artifact_id": persisted_artifact.get("artifact_id"),
                "domains": list(persisted_artifact.get("domains") or []),
                "languages": list(persisted_artifact.get("languages") or []),
                "source": persisted_artifact.get("topic") or "hlf_benchmark_artifacts",
                "operator_summary": f"Governed benchmark artifact for {profile_name}",
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
        self.session_governed_routes[agent_id] = dict(route_trace)
        self.emit_governance_event(
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
        return self.session_governed_routes[agent_id]

    def get_governed_route(self, *, agent_id: str | None = None) -> dict[str, Any] | None:
        if agent_id:
            return self.session_governed_routes.get(agent_id)
        if self.session_governed_routes:
            latest_agent_id = next(reversed(self.session_governed_routes))
            return self.session_governed_routes.get(latest_agent_id)
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
        return variables

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

    def persist_media_evidence(
        self,
        media_evidence: list[MediaEvidenceRecord],
    ) -> list[dict[str, Any]]:
        persisted: list[dict[str, Any]] = []
        for item in media_evidence:
            summary = item.operator_summary or f"Normalized {item.media_type} evidence for governed review"
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
        seed = "|".join([created_at, normalized_lane, *normalized_finding_ids])
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
        cycle_id = f"dream-cycle-{hashlib.sha256(created_at.encode('utf-8')).hexdigest()[:12]}"

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
            high_confidence_count=sum(1 for finding in persisted_findings if finding["confidence"] >= 0.8),
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
                    "trace_id": str(witness_record["governance_event"]["event"].get("trace_id", "")),
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
            finding for finding in findings if float(finding.get("confidence", 0.0)) >= min_confidence
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
            "session_surface_counts": {
                "profiles": len(self.session_profiles),
                "model_catalogs": len(self.session_model_catalogs),
                "benchmark_artifacts": len(self.session_benchmark_artifacts),
                "governed_routes": len(self.session_governed_routes),
                "media_evidence": len(self.session_media_evidence),
                "dream_cycles": len(self.session_dream_cycles),
                "dream_findings": len(self.session_dream_findings),
                "dream_proposals": len(self.session_dream_proposals),
            },
        }


def build_server_context() -> ServerContext:
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
        align_governor=AlignGovernor(),
        formal_verifier=FormalVerifier(),
        session_profiles={},
        session_model_catalogs={},
        session_benchmark_artifacts={},
        session_governed_routes={},
        session_media_evidence={},
        session_dream_cycles={},
        session_dream_findings={},
        session_dream_proposals={},
        witness_governance=WitnessGovernance(),
        approval_ledger=ApprovalLedger(),
        audit_chain=AuditChain(),
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
