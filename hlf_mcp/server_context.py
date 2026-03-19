from __future__ import annotations

from collections import deque
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.approval_ledger import ApprovalLedger
from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.governance_events import GovernanceEvent, GovernanceEventKind, GovernanceSeverity, GovernanceStatus
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.registry import HostFunctionRegistry
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.tool_dispatch import ToolRegistry
from hlf_mcp.hlf.witness_governance import WitnessGovernance, WitnessObservation, WitnessRecommendedAction
from hlf_mcp.instinct.lifecycle import InstinctLifecycle
from hlf_mcp.rag.memory import HKSProvenance, HKSTestEvidence, HKSValidatedExemplar, RAGMemory


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

    def get_effective_trust_state(self, *, subject_agent_id: str | None = None, default: str = "trusted") -> str:
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
                        "roundtrip_fidelity_score": translation.get("roundtrip_fidelity_score", 1.0),
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
                collected_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
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

    def get_embedding_profile(self, *, agent_id: str | None = None, profile_id: str | None = None) -> dict[str, Any] | None:
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
        profile_name = str(artifact.get("profile_name") or artifact.get("artifact_id") or "unknown-benchmark")
        persisted_artifact = dict(artifact)
        collected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
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
            "remote_direct_env_var_present": bool(catalog.get("remote_direct_env_var_present", False)),
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
                variables["_embedding_model"] = profile.get("embedding_recommendation", {}).get("model")
                variables["_embedding_endpoint"] = profile.get("embedding_recommendation", {}).get("endpoint")
                variables["_embedding_fallback_model"] = profile.get("fallback_recommendation", {}).get("model")
                variables["_ollama_available"] = profile.get("runtime_status", {}).get("ollama_available", False)
                variables["_embedding_model_runnable"] = profile.get("runtime_status", {}).get("recommended_model_runnable", False)
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






