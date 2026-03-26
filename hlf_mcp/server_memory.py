from __future__ import annotations

import json
import os
from urllib import error as urllib_error
from urllib import request as urllib_request
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.memory_node import build_pointer_ref
from hlf_mcp.server_context import ServerContext
from hlf_mcp.doc_ingest import (
    DocumentIngester,
    KNOWN_DOMAINS,
    AUTHORITY_LEVELS,
    summarize_reports,
)

_SUPPORTED_MEMORY_GOVERNANCE_ACTIONS = {"revoke", "tombstone", "reinstate"}


def _coerce_external_compare_results(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("results", "items", "data", "matches"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _fetch_external_compare_results(
    *,
    query: str,
    comparator_name: str,
    top_k: int,
    domain: str | None,
    solution_kind: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    comparator_url = str(os.environ.get("HLF_HKS_EXTERNAL_COMPARATOR_URL", "")).strip()
    if not comparator_url:
        return [], {
            "status": "not_configured",
            "message": "HLF_HKS_EXTERNAL_COMPARATOR_URL is not configured.",
        }

    timeout_raw = str(os.environ.get("HLF_HKS_EXTERNAL_COMPARATOR_TIMEOUT_SECONDS", "8")).strip()
    try:
        timeout_seconds = max(1.0, float(timeout_raw))
    except ValueError:
        timeout_seconds = 8.0

    auth_header = str(os.environ.get("HLF_HKS_EXTERNAL_COMPARATOR_AUTH_HEADER", "")).strip()
    auth_token = str(os.environ.get("HLF_HKS_EXTERNAL_COMPARATOR_AUTH_TOKEN", "")).strip()
    request_body = {
        "query": query,
        "comparator_name": comparator_name,
        "top_k": top_k,
        "domain": domain,
        "solution_kind": solution_kind,
    }
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "hlf-mcp-hks-external-compare/1.0",
    }
    if auth_header and auth_token:
        request_headers[auth_header] = auth_token

    request_obj = urllib_request.Request(
        comparator_url,
        data=json.dumps(request_body).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(request_obj, timeout=timeout_seconds) as response:
            raw_payload = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        return [], {
            "status": "http_error",
            "message": f"Comparator returned HTTP {exc.code}.",
            "status_code": exc.code,
        }
    except urllib_error.URLError as exc:
        return [], {
            "status": "network_error",
            "message": str(exc.reason),
        }

    try:
        decoded_payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return [], {
            "status": "invalid_response",
            "message": "Comparator response was not valid JSON.",
        }

    return _coerce_external_compare_results(decoded_payload), None


def _normalize_memory_governance_action(action: str) -> str:
    return str(action or "").strip().lower()


def _invalid_memory_governance_request(
    *,
    action: str,
    fact_id: int | None,
    sha256: str | None,
    message: str,
) -> dict[str, Any]:
    return {
        "status": "error",
        "error": "invalid_request",
        "message": message,
        "action": action,
        "fact_id": fact_id,
        "sha256": sha256,
    }


def apply_memory_governance(
    ctx: ServerContext,
    *,
    action: str,
    fact_id: int | None = None,
    sha256: str | None = None,
    operator_summary: str = "",
    reason: str = "",
    operator_id: str = "",
    operator_display_name: str = "",
    operator_channel: str = "",
    source: str = "server_memory.hlf_memory_govern",
) -> dict[str, Any]:
    """Apply a governed memory intervention and emit the matching audit/governance records."""
    normalized_action = _normalize_memory_governance_action(action)
    if normalized_action not in _SUPPORTED_MEMORY_GOVERNANCE_ACTIONS:
        return _invalid_memory_governance_request(
            action=normalized_action,
            fact_id=fact_id,
            sha256=sha256,
            message=f"unsupported governance action: {action!r}",
        )
    if fact_id is None and not sha256:
        return _invalid_memory_governance_request(
            action=normalized_action,
            fact_id=fact_id,
            sha256=sha256,
            message="fact_id or sha256 is required",
        )

    governed_fact = ctx.memory_store.govern_fact(
        action=normalized_action,
        fact_id=fact_id,
        sha256=sha256,
        operator_summary=operator_summary,
        governed_by=source,
        reason=reason,
        operator_id=operator_id,
        operator_display_name=operator_display_name,
        operator_channel=operator_channel,
    )
    if governed_fact is None:
        return {
            "status": "not_found",
            "fact_id": fact_id,
            "sha256": sha256,
            "action": normalized_action,
        }

    pointer_alias = (
        f"{governed_fact.get('topic') or 'general'}-{governed_fact.get('id') or 'entry'}"
    )
    pointer = build_pointer_ref(pointer_alias, str(governed_fact.get("sha256") or ""))
    audit = ctx.audit_chain.log(
        "hlf_memory_govern",
        {
            "action": normalized_action,
            "fact_id": governed_fact.get("id"),
            "sha256": governed_fact.get("sha256"),
            "topic": governed_fact.get("topic"),
            "pointer": pointer,
            "reason": reason,
            "operator_id": operator_id,
            "operator_display_name": operator_display_name,
            "operator_channel": operator_channel,
        },
        agent_role="memory_governance",
        goal_id=str(governed_fact.get("topic") or ""),
    )
    governance_event = ctx.emit_governance_event(
        kind="memory_governance",
        source=source,
        action=f"memory_{normalized_action}",
        status="ok",
        severity="warning" if normalized_action in {"revoke", "tombstone"} else "info",
        subject_id=str(governed_fact.get("id") or ""),
        goal_id=str(governed_fact.get("topic") or ""),
        details={
            "sha256": governed_fact.get("sha256"),
            "pointer": pointer,
            "state": governed_fact.get("governance_status"),
            "audit_trace_id": audit.get("trace_id"),
            "reason": reason,
            "operator_summary": operator_summary,
            "operator_id": operator_id,
            "operator_display_name": operator_display_name,
            "operator_channel": operator_channel,
        },
        agent_role="memory_governance",
    )
    return {
        "status": "ok",
        "action": normalized_action,
        "fact": governed_fact,
        "audit": audit,
        "governance_event": governance_event,
    }


def _decorate_recalled_facts(results: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    evidence_backed_count = 0
    stale_count = 0
    superseded_count = 0
    revoked_count = 0
    evaluated_count = 0
    promotion_eligible_count = 0
    requires_local_recheck_count = 0
    evaluation_authorities: set[str] = set()
    domains: set[str] = set()
    solution_kinds: set[str] = set()

    for item in results:
        normalized = dict(item)
        pointer_alias = f"{normalized.get('topic') or 'general'}-{normalized.get('id') or 'entry'}"
        pointer = build_pointer_ref(pointer_alias, str(normalized.get("sha256") or ""))
        normalized["pointer"] = pointer
        evidence = normalized.get("evidence") if isinstance(normalized.get("evidence"), dict) else {}
        if evidence:
            evidence = dict(evidence)
            evidence.setdefault("pointer", pointer)
            evidence.setdefault("pointer_alias", pointer_alias)
            normalized["evidence"] = evidence
            if evidence.get("provenance_grade") == "evidence-backed":
                evidence_backed_count += 1
            if evidence.get("freshness_status") == "stale":
                stale_count += 1
            if bool(evidence.get("superseded", False)):
                superseded_count += 1
            if bool(evidence.get("revoked", False)) or bool(evidence.get("tombstoned", False)):
                revoked_count += 1
        if normalized.get("domain"):
            domains.add(str(normalized.get("domain")))
        if normalized.get("solution_kind"):
            solution_kinds.add(str(normalized.get("solution_kind")))
        evaluation = normalized.get("evaluation") if isinstance(normalized.get("evaluation"), dict) else {}
        if evaluation:
            evaluated_count += 1
            if bool(evaluation.get("promotion_eligible", False)):
                promotion_eligible_count += 1
            if bool(evaluation.get("requires_local_recheck", False)):
                requires_local_recheck_count += 1
            evaluation_authorities.add(str(evaluation.get("authority") or ""))
        decorated.append(normalized)

    summary = {
        "result_count": len(decorated),
        "evidence_backed_count": evidence_backed_count,
        "stale_count": stale_count,
        "superseded_count": superseded_count,
        "revoked_or_tombstoned_count": revoked_count,
        "evaluated_count": evaluated_count,
        "promotion_eligible_count": promotion_eligible_count,
        "requires_local_recheck_count": requires_local_recheck_count,
        "evaluation_authorities": sorted(item for item in evaluation_authorities if item),
        "domains": sorted(domains),
        "solution_kinds": sorted(solution_kinds),
    }
    return decorated, summary


def _build_internal_governed_recall_workflow(
    *,
    problem: str,
    query: str,
    domain: str,
    solution_kind: str,
    capture_result: dict[str, Any],
    recall_result: dict[str, Any],
    resolution_result: dict[str, Any] | None,
    summary: str,
) -> dict[str, Any]:
    capture_governance_event = (
        capture_result.get("governance_event")
        if isinstance(capture_result.get("governance_event"), dict)
        else {}
    )
    recall_governance_event = (
        recall_result.get("governance_event")
        if isinstance(recall_result.get("governance_event"), dict)
        else {}
    )
    resolution_governance_event = (
        resolution_result.get("governance_event")
        if isinstance(resolution_result, dict)
        and isinstance(resolution_result.get("governance_event"), dict)
        else {}
    )
    results = recall_result.get("results") if isinstance(recall_result.get("results"), list) else []
    first_result = results[0] if results and isinstance(results[0], dict) else {}
    evidence_summary = (
        recall_result.get("evidence_summary")
        if isinstance(recall_result.get("evidence_summary"), dict)
        else {}
    )
    operator_summary = (
        f"Bounded internal governed-recall workflow stored repo repair evidence for '{problem}' and "
        f"recalled {int(recall_result.get('count') or 0)} governed result(s) for '{query}'."
    )
    if summary:
        operator_summary = f"{operator_summary} {summary.strip()}"
    return {
        "status": "ok",
        "workflow_kind": "internal_governed_recall_loop",
        "problem": problem,
        "query": query,
        "domain": domain,
        "solution_kind": solution_kind,
        "operator_summary": operator_summary,
        "before": {
            "capture": {
                "fact_id": capture_result.get("id"),
                "sha256": capture_result.get("sha256"),
                "pointer": capture_result.get("pointer"),
                "stored": capture_result.get("stored"),
                "audit_trace_id": (capture_result.get("audit") or {}).get("trace_id"),
                "governance_event_ref": capture_governance_event.get("event_ref"),
            }
        },
        "after": {
            "recall": {
                "recall_id": recall_result.get("recall_id"),
                "result_count": recall_result.get("count"),
                "entry_kinds": list(recall_result.get("entry_kinds") or []),
                "evidence_backed_count": evidence_summary.get("evidence_backed_count", 0),
                "top_result": {
                    "entry_kind": first_result.get("entry_kind"),
                    "topic": first_result.get("topic"),
                    "pointer": first_result.get("pointer"),
                    "sha256": first_result.get("sha256"),
                },
                "governance_event_ref": recall_governance_event.get("event_ref"),
            },
            "resolution": resolution_result,
        },
        "evidence_refs": [
            capture_governance_event.get("event_ref"),
            recall_governance_event.get("event_ref"),
            resolution_governance_event.get("event_ref"),
        ],
    }


def register_memory_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_memory_store(
        content: str,
        topic: str = "general",
        confidence: float = 1.0,
        provenance: str = "agent",
        tags: list[str] | None = None,
        source_type: str | None = None,
        source_authority_label: str = "advisory",
        artifact_form: str = "raw_intake",
        artifact_kind: str | None = None,
        source_version: str | None = None,
        fresh_until: str | None = None,
        extraction_fidelity_score: float | None = None,
        code_block_recall_score: float | None = None,
        structure_fidelity_score: float | None = None,
        citation_recoverability_score: float | None = None,
        canonicalized: bool | None = None,
    ) -> dict[str, Any]:
        """Store a fact in the Infinite RAG memory."""
        metadata = {
            "artifact_form": artifact_form,
            "artifact_kind": artifact_kind or "fact",
            "source_authority_label": source_authority_label,
            "source_capture": {
                "extraction_fidelity_score": extraction_fidelity_score,
                "code_block_recall_score": code_block_recall_score,
                "structure_fidelity_score": structure_fidelity_score,
                "citation_recoverability_score": citation_recoverability_score,
                "source_type_classification": source_type or "fact",
                "source_authority_label": source_authority_label,
                "source_version": source_version or "",
                "freshness_marker": fresh_until or "",
            },
            "artifact_contract": {
                "artifact_form": artifact_form,
                "artifact_kind": artifact_kind or "fact",
                "canonicalized": canonicalized if canonicalized is not None else artifact_form == "canonical_knowledge",
            },
            "governed_evidence": {
                "source_type": source_type or "fact",
                "source_authority_label": source_authority_label,
                "artifact_form": artifact_form,
                "artifact_kind": artifact_kind or "fact",
                "fresh_until": fresh_until,
                "source_version": source_version,
                "extraction_fidelity_score": extraction_fidelity_score,
                "code_block_recall_score": code_block_recall_score,
                "structure_fidelity_score": structure_fidelity_score,
                "citation_recoverability_score": citation_recoverability_score,
            },
        }
        effective_entry_kind = artifact_kind or "fact"
        _STRICT_ENTRY_KINDS = {"evidence", "hks_exemplar", "weekly_artifact", "benchmark_artifact"}
        use_strict = effective_entry_kind in _STRICT_ENTRY_KINDS
        store_result = ctx.memory_store.store(
            content,
            topic=topic,
            confidence=confidence,
            provenance=provenance,
            tags=tags or [],
            entry_kind=effective_entry_kind,
            metadata=metadata,
            strict=use_strict,
        )
        pointer_alias = f"{topic}-{store_result.get('id', 'entry')}"
        store_result["pointer"] = build_pointer_ref(
            pointer_alias, str(store_result.get("sha256", ""))
        )
        store_result["pointer_entry"] = {
            "alias": pointer_alias,
            "content_hash": str(store_result.get("sha256", "")),
            "content": content,
            "trust_tier": "local",
            "fresh_until": None,
            "revoked": False,
            "tombstoned": False,
            "topic": topic,
            "artifact_form": store_result.get("artifact_contract", {}).get("artifact_form") or artifact_form,
            "source_authority_label": store_result.get("source_capture", {}).get("source_authority_label") or source_authority_label,
        }
        if isinstance(store_result.get("evidence"), dict):
            store_result["evidence"].update(
                {
                    "pointer": store_result["pointer"],
                    "pointer_alias": pointer_alias,
                }
            )
        store_result["audit"] = ctx.audit_chain.log(
            "hlf_memory_store",
            {
                "topic": topic,
                "fact_id": store_result.get("id"),
                "sha256": store_result.get("sha256"),
                "stored": store_result.get("stored"),
                "provenance": provenance,
                "confidence": confidence,
                "pointer": store_result["pointer"],
                "pointer_alias": pointer_alias,
                "tag_count": len(tags or []),
            },
            agent_role="memory_store",
            goal_id=topic,
        )
        store_result["governance_event"] = ctx.emit_governance_event(
            kind="memory_store",
            source="server_memory.hlf_memory_store",
            action="store_memory_fact",
            subject_id=str(store_result.get("id", "")),
            goal_id=topic,
            details={
                "topic": topic,
                "sha256": store_result.get("sha256"),
                "pointer": store_result["pointer"],
                "pointer_alias": pointer_alias,
                "audit_trace_id": store_result["audit"].get("trace_id"),
                "confidence": confidence,
                "provenance": provenance,
            },
            agent_role="memory_store",
        )
        return store_result

    @mcp.tool()
    def hlf_memory_query(
        query: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
        entry_kind: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
        include_archive: bool = False,
        purpose: str | None = None,
    ) -> dict[str, Any]:
        """Query the Infinite RAG memory by semantic similarity."""
        return ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
            entry_kind=entry_kind,
            domain=domain,
            solution_kind=solution_kind,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
            include_archive=include_archive,
            purpose=purpose,
        )

    @mcp.tool()
    def hlf_hks_capture(
        problem: str,
        validated_solution: str,
        domain: str,
        solution_kind: str = "repair-pattern",
        topic: str = "hlf_validated_exemplars",
        provenance: str = "hlf_hks_capture",
        confidence: float = 1.0,
        tags: list[str] | None = None,
        tests: list[dict[str, Any]] | None = None,
        supersedes: str | None = None,
        summary: str = "",
        source_type: str = "mcp_tool",
        source: str | None = None,
        workflow_run_url: str | None = None,
        branch: str | None = None,
        commit_sha: str | None = None,
        artifact_path: str | None = None,
    ) -> dict[str, Any]:
        """Capture a validated HKS exemplar for future governed recall."""
        result = ctx.capture_validated_solution(
            problem=problem,
            validated_solution=validated_solution,
            domain=domain,
            solution_kind=solution_kind,
            provenance=provenance,
            tests=tests,
            topic=topic,
            confidence=confidence,
            tags=tags,
            supersedes=supersedes,
            summary=summary,
            source_type=source_type,
            source=source,
            workflow_run_url=workflow_run_url,
            branch=branch,
            commit_sha=commit_sha,
            artifact_path=artifact_path,
        )
        result["audit"] = ctx.audit_chain.log(
            "hlf_hks_capture",
            {
                "topic": topic,
                "domain": domain,
                "solution_kind": solution_kind,
                "fact_id": result.get("id"),
                "sha256": result.get("sha256"),
                "stored": result.get("stored"),
                "confidence": confidence,
            },
            agent_role="hks_capture",
            goal_id=topic,
        )
        governance_event = result.get("governance_event")
        if isinstance(governance_event, dict):
            event_payload = governance_event.get("event")
            if isinstance(event_payload, dict):
                details = event_payload.get("details")
                if isinstance(details, dict):
                    details.setdefault("audit_trace_id", result["audit"].get("trace_id"))
        return result

    @mcp.tool()
    def hlf_hks_recall(
        query: str,
        top_k: int = 5,
        domain: str | None = None,
        solution_kind: str | None = None,
        topic: str = "hlf_validated_exemplars",
        min_confidence: float = 0.0,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = True,
        include_archive: bool = False,
    ) -> dict[str, Any]:
        """Recall validated HKS exemplars filtered by domain and solution pattern."""
        recalled = ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
            entry_kind="hks_exemplar",
            domain=domain,
            solution_kind=solution_kind,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
            include_archive=include_archive,
        )
        decorated_results, evidence_summary = _decorate_recalled_facts(
            list(recalled.get("results") or [])
        )
        governance_event = ctx.emit_governance_event(
            kind="memory_governance",
            source="server_memory.hlf_hks_recall",
            action="recall_hks_exemplar",
            status="ok",
            severity="info",
            subject_id=str(decorated_results[0].get("id") or "") if decorated_results else "",
            goal_id=query,
            details={
                "query": query,
                "topic": topic,
                "result_count": len(decorated_results),
                "domain": domain,
                "solution_kind": solution_kind,
                "require_provenance": require_provenance,
                "evidence_backed_count": evidence_summary["evidence_backed_count"],
                "entry_kinds": ["hks_exemplar"],
            },
            agent_role="hks_recall",
        )
        payload = {
            **recalled,
            "status": "ok",
            "recall_kind": "hks_recall",
            "results": decorated_results,
            "entry_kinds": ["hks_exemplar"],
            "weekly_sync": {
                "status": "not_applicable",
                "count": 0,
                "artifacts": [],
                "metrics_dir": None,
            },
            "operator_summary": (
                f"HKS recall returned {len(decorated_results)} exemplar(s) for query '{query}' with "
                f"{evidence_summary['evidence_backed_count']} evidence-backed result(s)."
            ),
            "evidence_refs": [governance_event.get("event_ref")],
            "evidence_summary": evidence_summary,
            "governance_event": governance_event,
        }
        return ctx.persist_governed_recall(
            payload,
            source="server_memory.hlf_hks_recall",
        )

    @mcp.tool()
    def hlf_governed_recall(
        query: str,
        top_k: int = 5,
        domain: str | None = None,
        solution_kind: str | None = None,
        metrics_dir: str | None = None,
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
        """Recall governed evidence across weekly artifacts, HKS exemplars, and witness memory."""
        return ctx.recall_governed_evidence(
            query,
            top_k=top_k,
            domain=domain,
            solution_kind=solution_kind,
            metrics_dir=metrics_dir,
            include_weekly_artifacts=include_weekly_artifacts,
            include_hks=include_hks,
            include_witness_evidence=include_witness_evidence,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
            include_archive=include_archive,
            purpose=purpose,
        )

    @mcp.tool()
    def hlf_hks_external_compare(
        query: str,
        comparator_name: str = "external_comparator",
        comparator_results: list[dict[str, Any]] | None = None,
        top_k: int = 5,
        domain: str | None = None,
        solution_kind: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Produce a quarantined advisory comparison between local HKS recall and optional external comparator results."""
        effective_enabled = enabled
        if effective_enabled is None:
            effective_enabled = str(os.environ.get("HLF_ENABLE_HKS_EXTERNAL_COMPARATOR", "")).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        if not effective_enabled:
            return {
                "status": "disabled",
                "compare_kind": "hks_external_compare",
                "lane": "bridge",
                "operator_summary": (
                    "External comparator comparison is disabled. Enable it explicitly to create a quarantined advisory contract."
                ),
                "requires_local_recheck": True,
                "admission_authority": "local_hks_only",
            }

        local_recall = hlf_governed_recall(
            query,
            top_k=top_k,
            domain=domain,
            solution_kind=solution_kind,
            include_weekly_artifacts=False,
            include_witness_evidence=False,
            include_hks=True,
            require_provenance=True,
        )
        adapter_metadata: dict[str, Any] | None = None
        raw_comparator_results = comparator_results
        if raw_comparator_results is None:
            raw_comparator_results, adapter_metadata = _fetch_external_compare_results(
                query=query,
                comparator_name=comparator_name,
                top_k=top_k,
                domain=domain,
                solution_kind=solution_kind,
            )
        normalized_results: list[dict[str, Any]] = []
        for index, item in enumerate(raw_comparator_results or [], start=1):
            if not isinstance(item, dict):
                continue
            normalized_results.append(
                {
                    "rank": index,
                    "title": str(item.get("title") or item.get("name") or f"result-{index}"),
                    "snippet": str(item.get("snippet") or item.get("summary") or ""),
                    "url": str(item.get("url") or item.get("source") or ""),
                    "score": item.get("score"),
                    "provider": str(item.get("provider") or comparator_name),
                    "authority": "external_comparator",
                    "promotion_eligible": False,
                    "promotion_blocked": True,
                    "requires_local_recheck": True,
                    "lane": "bridge",
                }
            )

        governance_event = ctx.emit_governance_event(
            kind="memory_governance",
            source="server_memory.hlf_hks_external_compare",
            action="compare_external_hks",
            status="ok",
            severity="info",
            subject_id=str(local_recall.get("recall_id") or ""),
            goal_id=query,
            details={
                "query": query,
                "comparator_name": comparator_name,
                "local_result_count": int(local_recall.get("count") or 0),
                "comparator_result_count": len(normalized_results),
                "adapter_metadata": dict(adapter_metadata or {}),
                "requires_local_recheck": True,
                "lane": "bridge",
            },
            agent_role="hks_external_compare",
        )
        payload = {
            "status": "ok",
            "compare_kind": "hks_external_compare",
            "query": query,
            "comparator_name": comparator_name,
            "lane": "bridge",
            "requires_local_recheck": True,
            "admission_authority": "local_hks_only",
            "local_recall_id": local_recall.get("recall_id"),
            "local_result_count": int(local_recall.get("count") or 0),
            "local_results": list(local_recall.get("results") or []),
            "comparator_result_count": len(normalized_results),
            "comparator_results": normalized_results,
            "adapter_metadata": dict(adapter_metadata or {}),
            "operator_summary": (
                f"Comparator '{comparator_name}' returned {len(normalized_results)} advisory result(s) for '{query}'. "
                "Local HKS remains the only admission authority and all comparator output requires local recheck."
            ),
            "evidence_refs": [
                governance_event.get("event_ref"),
                local_recall.get("governance_event", {}).get("event_ref") if isinstance(local_recall.get("governance_event"), dict) else None,
            ],
            "governance_event": governance_event,
        }
        return ctx.persist_hks_external_compare(
            payload,
            source="server_memory.hlf_hks_external_compare",
        )

    @mcp.tool()
    def hlf_hks_weekly_refresh(
        metrics_dir: str | None = None,
        stale_after_days: int = 7,
    ) -> dict[str, Any]:
        """Analyze weekly HKS drift and queue bridge-lane revalidation or re-research actions."""
        return ctx.analyze_hks_weekly_refresh(
            metrics_dir=metrics_dir,
            stale_after_days=stale_after_days,
        )

    @mcp.tool()
    def hlf_internal_governed_recall_workflow(
        problem: str,
        validated_solution: str,
        query: str = "",
        domain: str = "general-coding",
        solution_kind: str = "repair-pattern",
        topic: str = "hlf_validated_exemplars",
        provenance: str = "hlf_internal_governed_recall_workflow",
        confidence: float = 1.0,
        tags: list[str] | None = None,
        tests: list[dict[str, Any]] | None = None,
        summary: str = "",
        top_k: int = 5,
        include_weekly_artifacts: bool = False,
        include_witness_evidence: bool = False,
        metrics_dir: str | None = None,
    ) -> dict[str, Any]:
        """Run a bounded repo-self-use governed recall loop and persist it as a reviewable internal workflow contract."""
        effective_query = str(query or problem).strip()
        capture_result = hlf_hks_capture(
            problem=problem,
            validated_solution=validated_solution,
            domain=domain,
            solution_kind=solution_kind,
            topic=topic,
            provenance=provenance,
            confidence=confidence,
            tags=tags,
            tests=tests,
            summary=summary,
            source="server_memory.hlf_internal_governed_recall_workflow",
        )
        recall_result = hlf_governed_recall(
            effective_query,
            top_k=top_k,
            domain=domain,
            solution_kind=solution_kind,
            metrics_dir=metrics_dir,
            include_weekly_artifacts=include_weekly_artifacts,
            include_hks=True,
            include_witness_evidence=include_witness_evidence,
            require_provenance=True,
        )

        resolution_result = None
        recall_results = recall_result.get("results") if isinstance(recall_result.get("results"), list) else []
        first_result = recall_results[0] if recall_results and isinstance(recall_results[0], dict) else {}
        first_pointer = str(first_result.get("pointer") or "").strip()
        if first_pointer:
            resolution_result = hlf_memory_resolve(
                first_pointer,
                purpose="operator_review",
                trust_mode="enforce",
                require_provenance=True,
            )

        workflow = _build_internal_governed_recall_workflow(
            problem=problem,
            query=effective_query,
            domain=domain,
            solution_kind=solution_kind,
            capture_result=capture_result,
            recall_result=recall_result,
            resolution_result=resolution_result,
            summary=summary,
        )
        return ctx.persist_internal_workflow(
            workflow,
            source="server_memory.hlf_internal_governed_recall_workflow",
        )

    @mcp.tool()
    def hlf_memory_stats() -> dict[str, Any]:
        """Return Infinite RAG memory store statistics."""
        stats = ctx.memory_store.stats()
        memory_strata = dict(stats.get("memory_strata") or {})
        storage_tiers = dict(stats.get("storage_tiers") or {})
        total_facts = int(stats.get("total_facts") or 0)
        archive_facts = int(memory_strata.get("archive") or 0)
        active_facts = max(total_facts - archive_facts, 0)
        stats["claim_lane"] = "bridge-true"
        stats["archive_admission"] = {
            "active_facts": active_facts,
            "archive_facts": archive_facts,
            "archive_ratio": round((archive_facts / total_facts), 4) if total_facts else 0.0,
            "memory_strata": memory_strata,
            "storage_tiers": storage_tiers,
            "archive_visibility_default": "filtered",
            "admission_model": "salience_and_governance_gated",
        }
        stats["operator_summary"] = (
            f"HKS memory currently holds {total_facts} fact(s): {active_facts} active and {archive_facts} archived. "
            "Archive-tier facts stay hidden from default governed recall unless archive mode is explicitly enabled."
        )
        return stats

    @mcp.tool()
    def hlf_memory_resolve(
        pointer: str,
        purpose: str = "operator_review",
        trust_mode: str = "enforce",
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
    ) -> dict[str, Any]:
        """Resolve a governed memory pointer against the packaged HKS / Infinite RAG substrate."""
        return ctx.resolve_memory_pointer(
            pointer,
            purpose=purpose,
            trust_mode=trust_mode,
            include_stale=include_stale,
            include_superseded=include_superseded,
            include_revoked=include_revoked,
            require_provenance=require_provenance,
            source="server_memory.hlf_memory_resolve",
        )

    @mcp.tool()
    def hlf_memory_govern(
        action: str,
        fact_id: int | None = None,
        sha256: str | None = None,
        operator_summary: str = "",
        reason: str = "",
        operator_id: str = "",
        operator_display_name: str = "",
        operator_channel: str = "",
        source: str = "server_memory.hlf_memory_govern",
    ) -> dict[str, Any]:
        """Apply a governed memory intervention such as revoke, tombstone, or reinstate."""
        return apply_memory_governance(
            ctx,
            action=action,
            fact_id=fact_id,
            sha256=sha256,
            operator_summary=operator_summary,
            reason=reason,
            operator_id=operator_id,
            operator_display_name=operator_display_name,
            operator_channel=operator_channel,
            source=source,
        )

    @mcp.tool()
    def hlf_witness_record(
        subject_agent_id: str,
        category: str,
        severity: str = "warning",
        confidence: float = 0.8,
        witness_id: str = "operator",
        goal_id: str = "",
        session_id: str = "",
        source: str = "server_memory.hlf_witness_record",
        event_ref: dict[str, str] | None = None,
        evidence_text: str = "",
        recommended_action: str = "review",
        details: dict[str, Any] | None = None,
        negative: bool = True,
    ) -> dict[str, Any]:
        """Record a structured witness observation and compute the subject's packaged trust state."""
        return ctx.record_witness_observation(
            subject_agent_id=subject_agent_id,
            category=category,
            witness_id=witness_id,
            severity=str(severity).lower(),
            confidence=confidence,
            goal_id=goal_id,
            session_id=session_id,
            source=source,
            event_ref=event_ref,
            evidence_text=evidence_text,
            recommended_action=str(recommended_action).lower(),
            details=details,
            negative=negative,
        )

    @mcp.tool()
    def hlf_witness_status(subject_agent_id: str | None = None) -> dict[str, Any]:
        """Return the current packaged witness-governance trust state for a subject or the global summary."""
        status = ctx.get_witness_status(subject_agent_id=subject_agent_id)
        if status is None:
            return {"status": "not_found", "subject_agent_id": subject_agent_id}
        return {"status": "ok", "witness_status": status}

    @mcp.tool()
    def hlf_witness_list(trust_state: str | None = None) -> dict[str, Any]:
        """List subjects tracked by witness governance, optionally filtered by trust state."""
        listing = ctx.list_witness_subjects(trust_state=trust_state)
        return {"status": "ok", **listing}

    @mcp.tool()
    def hlf_dream_cycle_run(
        metrics_dir: str | None = None,
        max_artifacts: int = 3,
        max_facts: int = 10,
        media_evidence: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run a bounded governed dream cycle over recent evidence and return advisory findings."""
        return ctx.run_dream_cycle(
            metrics_dir=metrics_dir,
            max_artifacts=max_artifacts,
            max_facts=max_facts,
            media_evidence=media_evidence,
        )

    @mcp.tool()
    def hlf_dream_findings_list(
        cycle_id: str | None = None,
        topic: str | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """List advisory dream findings produced during bounded dream-cycle runs."""
        return {
            "status": "ok",
            **ctx.list_dream_findings(
                cycle_id=cycle_id,
                topic=topic,
                min_confidence=min_confidence,
            ),
        }

    @mcp.tool()
    def hlf_dream_findings_get(finding_id: str) -> dict[str, Any]:
        """Return a specific advisory dream finding by ID."""
        finding = ctx.get_dream_finding(finding_id)
        if finding is None:
            return {"status": "not_found", "finding_id": finding_id}
        return {"status": "ok", "finding": finding}

    @mcp.tool()
    def hlf_media_evidence_list(media_type: str | None = None) -> dict[str, Any]:
        """List normalized shared media evidence records admitted into governed memory."""
        return {"status": "ok", **ctx.list_media_evidence(media_type=media_type)}

    @mcp.tool()
    def hlf_media_evidence_get(artifact_id: str) -> dict[str, Any]:
        """Return a specific shared media evidence record by artifact ID."""
        evidence = ctx.get_media_evidence(artifact_id)
        if evidence is None:
            return {"status": "not_found", "artifact_id": artifact_id}
        return {"status": "ok", "media_evidence": evidence}

    @mcp.tool()
    def hlf_dream_proposal_create(
        finding_ids: list[str],
        title: str,
        summary: str,
        lane: str = "bridge",
        proposal_text: str = "",
        verification_plan: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create an advisory dream proposal with explicit observe-propose-verify-promote citation gates."""
        return ctx.create_dream_proposal(
            finding_ids=finding_ids,
            title=title,
            summary=summary,
            lane=lane,
            proposal_text=proposal_text,
            verification_plan=verification_plan,
        )

    @mcp.tool()
    def hlf_dream_proposals_list(lane: str | None = None) -> dict[str, Any]:
        """List advisory dream proposals staged for a governed implementation lane."""
        return {"status": "ok", **ctx.list_dream_proposals(lane=lane)}

    @mcp.tool()
    def hlf_dream_proposals_get(proposal_id: str) -> dict[str, Any]:
        """Return a specific advisory dream proposal by ID."""
        proposal = ctx.get_dream_proposal(proposal_id)
        if proposal is None:
            return {"status": "not_found", "proposal_id": proposal_id}
        return {"status": "ok", "proposal": proposal}

    # ── Knowledge Ingestion Tools ─────────────────────────────────────

    @mcp.tool()
    def hlf_knowledge_ingest(
        content: str,
        domain: str = "general-coding",
        source_authority_label: str = "advisory",
        source_file: str = "inline",
        topic: str | None = None,
        confidence: float = 0.9,
        tags: list[str] | None = None,
        fresh_until: str | None = None,
    ) -> dict[str, Any]:
        """Ingest text content into the governed knowledge substrate.

        Markdown-aware: splits on headers, preserves section hierarchy,
        stores each chunk as governed evidence with full provenance.

        Domains: general-coding, ai-engineering, hlf-specific, devops,
                 security, data-engineering, frontend, backend, infrastructure.

        Authority: canonical (authoritative source of truth),
                   advisory (best-practice guidance),
                   external (third-party reference),
                   draft (unvalidated working material).
        """
        ingester = DocumentIngester(ctx.memory_store)
        report = ingester.ingest_text(
            content,
            source_file=source_file,
            domain=domain,
            source_authority_label=source_authority_label,
            topic=topic,
            confidence=confidence,
            tags=tags,
            fresh_until=fresh_until,
        )
        return {
            "status": "ok" if report.error_count == 0 else "partial",
            "source_file": report.source_file,
            "source_sha256": report.source_sha256,
            "domain": report.domain,
            "total_chunks": report.total_chunks,
            "stored": report.stored_count,
            "deduped": report.deduped_count,
            "errors": report.error_count,
            "error_details": report.errors[:10],
            "chunk_ids": report.chunk_ids,
            "elapsed_seconds": round(report.elapsed_seconds, 3),
        }

    @mcp.tool()
    def hlf_knowledge_ingest_directory(
        dir_path: str,
        domain: str = "general-coding",
        source_authority_label: str = "advisory",
        topic: str | None = None,
        confidence: float = 0.9,
        tags: list[str] | None = None,
        fresh_until: str | None = None,
        file_pattern: str = "*.md",
        recursive: bool = True,
    ) -> dict[str, Any]:
        """Ingest all matching files from a directory into the knowledge substrate.

        Scans for files matching file_pattern (default: *.md), chunks each
        markdown document, and stores governed evidence with full provenance.

        Returns a summary across all processed files.
        """
        ingester = DocumentIngester(ctx.memory_store)
        reports = ingester.ingest_directory(
            dir_path,
            domain=domain,
            source_authority_label=source_authority_label,
            topic=topic,
            confidence=confidence,
            tags=tags,
            fresh_until=fresh_until,
            file_pattern=file_pattern,
            recursive=recursive,
        )
        summary = summarize_reports(reports)
        return {"status": "ok" if summary["errors"] == 0 else "partial", **summary}

    return {
        "hlf_memory_store": hlf_memory_store,
        "hlf_memory_query": hlf_memory_query,
        "hlf_hks_capture": hlf_hks_capture,
        "hlf_hks_recall": hlf_hks_recall,
        "hlf_governed_recall": hlf_governed_recall,
        "hlf_hks_external_compare": hlf_hks_external_compare,
        "hlf_hks_weekly_refresh": hlf_hks_weekly_refresh,
        "hlf_internal_governed_recall_workflow": hlf_internal_governed_recall_workflow,
        "hlf_memory_stats": hlf_memory_stats,
        "hlf_memory_resolve": hlf_memory_resolve,
        "hlf_memory_govern": hlf_memory_govern,
        "hlf_witness_record": hlf_witness_record,
        "hlf_witness_status": hlf_witness_status,
        "hlf_witness_list": hlf_witness_list,
        "hlf_dream_cycle_run": hlf_dream_cycle_run,
        "hlf_dream_findings_list": hlf_dream_findings_list,
        "hlf_dream_findings_get": hlf_dream_findings_get,
        "hlf_media_evidence_list": hlf_media_evidence_list,
        "hlf_media_evidence_get": hlf_media_evidence_get,
        "hlf_dream_proposal_create": hlf_dream_proposal_create,
        "hlf_dream_proposals_list": hlf_dream_proposals_list,
        "hlf_dream_proposals_get": hlf_dream_proposals_get,
        "hlf_knowledge_ingest": hlf_knowledge_ingest,
        "hlf_knowledge_ingest_directory": hlf_knowledge_ingest_directory,
    }
