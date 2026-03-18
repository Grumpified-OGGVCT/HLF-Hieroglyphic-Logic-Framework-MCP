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





