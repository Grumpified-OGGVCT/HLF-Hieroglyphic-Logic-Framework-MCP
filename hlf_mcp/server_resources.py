from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.bytecode import OPCODES, HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.symbolic_surfaces import compile_symbolic_surface
from hlf_mcp.instinct.orchestration import build_orchestration_contract
from hlf_mcp.ingress_support import normalize_ingress_status
from hlf_mcp.ingress_support import summarize_ingress_status
from hlf_mcp.server_profiles import (
    build_multimodal_contract_catalog,
    build_profile_capability_catalog,
)
from hlf_mcp.weekly_artifacts import (
    build_persona_review_summary,
    find_weekly_artifact,
    load_verified_weekly_artifacts,
    summarize_weekly_artifacts,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_GOVERNANCE_DIR = _PACKAGE_DIR.parent / "governance"
_FIXTURE_DIR_CANDIDATES = [_PACKAGE_DIR.parent / "fixtures", _PACKAGE_DIR / "fixtures"]
_log = logging.getLogger(__name__)
_SYMBOLIC_STARTER_VOCABULARY = [
    "time.before",
    "time.after",
    "cause.enables",
    "cause.blocks",
    "depends.on",
    "agent.owns",
    "agent.delegates",
    "scope.within",
]


def _dedupe_reference_dicts(*groups: object) -> list[dict[str, object]]:
    refs: list[dict[str, object]] = []
    seen: set[str] = set()

    for group in groups:
        items: list[object]
        if isinstance(group, list):
            items = group
        elif isinstance(group, tuple):
            items = list(group)
        else:
            items = [group]

        for item in items:
            if not isinstance(item, dict):
                continue
            normalized = {
                str(key): value
                for key, value in item.items()
                if isinstance(key, str) and value not in (None, "", [], {})
            }
            if not normalized:
                continue
            key = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
            if key in seen:
                continue
            seen.add(key)
            refs.append(normalized)

    return refs


def _dedupe_evidence_refs(*groups: object) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for group in groups:
        items: list[object]
        if isinstance(group, list):
            items = group
        elif isinstance(group, tuple):
            items = list(group)
        else:
            items = [group]

        for item in items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "").strip()
            event_id = str(item.get("event_id") or "").strip()
            trace_id = str(item.get("trace_id") or "").strip()
            if not kind or not event_id:
                continue
            key = (kind, event_id, trace_id)
            if key in seen:
                continue
            seen.add(key)
            refs.append({"kind": kind, "event_id": event_id, "trace_id": trace_id})

    return refs


def _memory_ref_as_evidence(memory_ref: object) -> dict[str, object] | None:
    if not isinstance(memory_ref, dict):
        return None
    fact_id = memory_ref.get("id")
    sha256 = str(memory_ref.get("sha256") or "").strip()
    if fact_id in (None, "") and not sha256:
        return None
    evidence: dict[str, object] = {"kind": "memory_fact"}
    if fact_id not in (None, ""):
        evidence["fact_id"] = fact_id
    if sha256:
        evidence["sha256"] = sha256
    return evidence


def _event_ref_from_governance_payload(payload: object) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None
    event_ref = payload.get("event_ref")
    if isinstance(event_ref, dict):
        kind = str(event_ref.get("kind") or "").strip()
        event_id = str(event_ref.get("event_id") or "").strip()
        trace_id = str(event_ref.get("trace_id") or "").strip()
        if kind and event_id:
            return {"kind": kind, "event_id": event_id, "trace_id": trace_id}
    event = payload.get("event")
    if isinstance(event, dict) and isinstance(event.get("event_ref"), dict):
        nested_ref = event.get("event_ref") or {}
        kind = str(nested_ref.get("kind") or "").strip()
        event_id = str(nested_ref.get("event_id") or "").strip()
        trace_id = str(nested_ref.get("trace_id") or event.get("trace_id") or "").strip()
        if kind and event_id:
            return {"kind": kind, "event_id": event_id, "trace_id": trace_id}
    return None


def _extract_route_lineage_refs(
    governed_route: dict[str, object] | None,
) -> tuple[list[object], dict[str, object] | None]:
    """Extract policy-basis lineage refs and route_decision from a governed route.

    Returns (lineage_refs_from_policy_basis, route_decision_dict_or_None).
    This enables dream findings, media evidence, and proposals to chain their
    local evidence_refs back to the governance route that admitted them.
    """
    if not isinstance(governed_route, dict):
        return [], None
    policy_basis = governed_route.get("policy_basis")
    lineage_from_policy = (
        policy_basis.get("evidence_lineage_refs")
        if isinstance(policy_basis, dict)
        else None
    )
    route_decision = governed_route.get("route_decision")
    return (
        lineage_from_policy if isinstance(lineage_from_policy, list) else [],
        route_decision if isinstance(route_decision, dict) else None,
    )


def _normalize_dream_finding_payload(
    finding: dict[str, object],
    governed_route: dict[str, object] | None = None,
) -> dict[str, object]:
    witness_record_id = ""
    if isinstance(finding.get("provenance"), dict):
        witness_record_id = str((finding.get("provenance") or {}).get("witness_record_id") or "").strip()
    evidence_refs = _dedupe_reference_dicts(
        finding.get("evidence_refs") if isinstance(finding.get("evidence_refs"), list) else None,
        _memory_ref_as_evidence(finding.get("memory_ref")),
        {"kind": "witness_observation", "event_id": witness_record_id} if witness_record_id else None,
    )
    operator_summary = str(
        finding.get("operator_summary")
        or finding.get("summary")
        or f"Dream finding '{finding.get('finding_id') or 'unknown'}' is available for review."
    )
    policy_lineage_refs, route_decision = _extract_route_lineage_refs(governed_route)
    evidence_lineage = _dedupe_evidence_refs(
        evidence_refs,
        policy_lineage_refs,
        route_decision.get("evidence_refs") if isinstance(route_decision, dict) else None,
    )
    return {
        **finding,
        "operator_summary": operator_summary,
        "evidence_refs": evidence_refs,
        "evidence_lineage": evidence_lineage,
    }


def _normalize_media_evidence_payload(
    evidence: dict[str, object],
    governed_route: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence_refs = _dedupe_reference_dicts(
        {
            "kind": "media_evidence",
            "artifact_id": str(evidence.get("artifact_id") or "").strip(),
            "sha256": str(evidence.get("sha256") or "").strip(),
            "media_type": str(evidence.get("media_type") or "").strip(),
        },
        _memory_ref_as_evidence(evidence.get("memory_ref")),
    )
    operator_summary = str(
        evidence.get("operator_summary")
        or f"Media evidence '{evidence.get('artifact_id') or 'unknown'}' was normalized for governed advisory use."
    )
    policy_lineage_refs, route_decision = _extract_route_lineage_refs(governed_route)
    evidence_lineage = _dedupe_evidence_refs(
        evidence_refs,
        policy_lineage_refs,
        route_decision.get("evidence_refs") if isinstance(route_decision, dict) else None,
    )
    return {
        **evidence,
        "operator_summary": operator_summary,
        "evidence_refs": evidence_refs,
        "evidence_lineage": evidence_lineage,
    }


def _normalize_dream_proposal_payload(
    proposal: dict[str, object],
    governed_route: dict[str, object] | None = None,
) -> dict[str, object]:
    citation_chain = proposal.get("citation_chain") if isinstance(proposal.get("citation_chain"), dict) else {}
    observe = citation_chain.get("observe") if isinstance(citation_chain.get("observe"), dict) else {}
    evidence_refs = _dedupe_reference_dicts(
        _event_ref_from_governance_payload(proposal.get("governance_event")),
        _memory_ref_as_evidence(proposal.get("memory_ref")),
        [
            {"kind": "dream_finding", "finding_id": str(finding_id)}
            for finding_id in (observe.get("finding_ids") or [])
            if str(finding_id)
        ],
        [
            {"kind": "media_evidence", "artifact_id": str(artifact_id)}
            for artifact_id in (observe.get("media_evidence_ids") or [])
            if str(artifact_id)
        ],
    )
    operator_summary = str(
        proposal.get("operator_summary")
        or proposal.get("summary")
        or f"Dream proposal '{proposal.get('proposal_id') or 'unknown'}' is available for review."
    )
    policy_lineage_refs, route_decision = _extract_route_lineage_refs(governed_route)
    evidence_lineage = _dedupe_evidence_refs(
        evidence_refs,
        policy_lineage_refs,
        route_decision.get("evidence_refs") if isinstance(route_decision, dict) else None,
    )
    return {
        **proposal,
        "operator_summary": operator_summary,
        "evidence_refs": evidence_refs,
        "evidence_lineage": evidence_lineage,
    }


def _summarize_daemon_alert_event(event: dict[str, object]) -> str:
    kind = str(event.get("kind") or "event")
    status = str(event.get("status") or "unknown")
    severity = str(event.get("severity") or "unknown")
    subject_id = str(event.get("subject_id") or "").strip()
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    if kind == "entropy_anchor":
        action = str(details.get("policy_action") or "observe")
        score = details.get("similarity_score")
        threshold = details.get("threshold")
        return (
            f"Entropy-anchor status is '{status}' with policy action '{action}'"
            + (
                f" at similarity {score} against threshold {threshold}."
                if score is not None and threshold is not None
                else "."
            )
        )
    if kind == "routing_decision":
        return f"Governed routing produced a {severity} alert for subject '{subject_id or 'unknown'}'."
    if kind in {"formal_verification", "verification_result"}:
        return f"Formal verification surfaced status '{status}' for subject '{subject_id or 'unknown'}'."
    if kind == "witness_observation":
        category = str(details.get("category") or "witness_observation")
        return f"Witness governance recorded category '{category}' at severity '{severity}'."
    return f"Governance event '{kind}' is currently flagged as status '{status}' with severity '{severity}'."


def _render_entropy_anchor_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "recent_governance_events"):
        return json.dumps({"status": "error", "error": "entropy_anchor_unavailable"}, indent=2)
    recent_results: list[dict[str, object]] = []
    for event in ctx.recent_governance_events(limit=20, kind="entropy_anchor"):
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        related_refs = event.get("related_refs") if isinstance(event.get("related_refs"), list) else []
        audit_ref = next(
            (
                ref
                for ref in related_refs
                if isinstance(ref, dict) and str(ref.get("kind") or "") == "audit"
            ),
            None,
        )
        recent_results.append(
            {
                "kind": event.get("kind"),
                "status": event.get("status"),
                "severity": event.get("severity"),
                "source": event.get("source"),
                "subject_id": event.get("subject_id"),
                "timestamp": event.get("timestamp"),
                "event_ref": event.get("event_ref"),
                "audit_trace_id": details.get("audit_trace_id") or (audit_ref or {}).get("trace_id"),
                "policy_mode": details.get("policy_mode"),
                "policy_action": details.get("policy_action"),
                "drift_detected": details.get("drift_detected"),
                "similarity_score": details.get("similarity_score"),
                "threshold": details.get("threshold"),
                "baseline_source": details.get("baseline_source"),
            }
        )
    drift_detected_count = sum(1 for item in recent_results if item.get("drift_detected") is True)
    latest_result = recent_results[0] if recent_results else None
    evidence_refs = _dedupe_evidence_refs(
        [item.get("event_ref") for item in recent_results if isinstance(item, dict)],
        [
            {"kind": "audit", "event_id": str(item.get("audit_trace_id") or ""), "trace_id": str(item.get("audit_trace_id") or "")}
            for item in recent_results
            if str(item.get("audit_trace_id") or "")
        ],
    )
    operator_summary = (
        "No entropy-anchor evaluations have been recorded yet."
        if latest_result is None
        else (
            f"Entropy-anchor surface currently tracks {len(recent_results)} recent evaluation(s); "
            f"{drift_detected_count} recorded drift condition(s), latest policy action "
            f"'{latest_result.get('policy_action') or 'observe'}'."
        )
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "entropy_anchor_status": {
                "recent_count": len(recent_results),
                "drift_detected_count": drift_detected_count,
                "latest_result": latest_result,
                "recent_results": recent_results,
            },
        },
        indent=2,
    )


def _render_daemon_alert_status(ctx: object | None) -> str:
    if ctx is None:
        return json.dumps({"status": "error", "error": "daemon_alerts_unavailable"}, indent=2)
    surface_mode = "packaged_bridge_proxy"
    if hasattr(ctx, "daemon_manager") and hasattr(ctx.daemon_manager, "get_alerts"):
        surface_mode = "packaged_daemon_manager"
        alert_events = list(ctx.daemon_manager.get_alerts(limit=50))
    elif hasattr(ctx, "recent_governance_events"):
        alert_events = []
        for event in ctx.recent_governance_events(limit=50):
            status = str(event.get("status") or "")
            severity = str(event.get("severity") or "")
            if status not in {"warning", "error", "blocked"} and severity not in {"warning", "critical"}:
                continue
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            alert_events.append(
                {
                    "kind": event.get("kind"),
                    "status": event.get("status"),
                    "severity": event.get("severity"),
                    "source": event.get("source"),
                    "subject_id": event.get("subject_id"),
                    "goal_id": event.get("goal_id"),
                    "timestamp": event.get("timestamp"),
                    "event_ref": event.get("event_ref"),
                    "audit_trace_id": details.get("audit_trace_id"),
                    "operator_summary": _summarize_daemon_alert_event(event),
                }
            )
    else:
        return json.dumps({"status": "error", "error": "daemon_alerts_unavailable"}, indent=2)
    weekly_evidence_summary = summarize_weekly_artifacts()
    security_open_alerts = None
    security_sources: list[str] = []
    history_path = Path(str(weekly_evidence_summary.get("history_path") or ""))
    if history_path.exists():
        try:
            for raw_line in reversed(history_path.read_text(encoding="utf-8").splitlines()):
                if not raw_line.strip():
                    continue
                artifact = json.loads(raw_line)
                security_findings = artifact.get("security_findings")
                if not isinstance(security_findings, dict):
                    continue
                summary = security_findings.get("summary") if isinstance(security_findings.get("summary"), dict) else {}
                open_alerts = summary.get("open_alerts")
                if isinstance(open_alerts, int):
                    security_open_alerts = open_alerts
                    security_sources.append(str(artifact.get("source") or "unknown"))
                    break
        except (OSError, ValueError, json.JSONDecodeError):
            security_open_alerts = None
            security_sources = []
    evidence_refs = _dedupe_evidence_refs(
        [event.get("event_ref") for event in alert_events if isinstance(event, dict)]
    )
    open_alerts_text = (
        "no current weekly security-alert summary is available"
        if security_open_alerts is None
        else f"latest weekly security summary reports {security_open_alerts} open alert(s)"
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Packaged daemon-alert surface currently synthesizes {len(alert_events)} governance alert event(s); "
                f"{open_alerts_text}."
            ),
            "evidence_refs": evidence_refs,
            "daemon_alerts": {
                "surface_mode": surface_mode,
                "alert_count": len(alert_events),
                "alerts": alert_events,
                "weekly_evidence_summary": weekly_evidence_summary,
                "latest_security_open_alerts": security_open_alerts,
                "latest_security_sources": security_sources,
            },
        },
        indent=2,
    )


def _classify_daemon_transparency_event(event: dict[str, object]) -> str:
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


def _summarize_daemon_transparency_event(event: dict[str, object]) -> str:
    kind = str(event.get("kind") or "event").strip() or "event"
    action = str(event.get("action") or "recorded").strip() or "recorded"
    status = str(event.get("status") or "unknown").strip() or "unknown"
    severity = str(event.get("severity") or "unknown").strip() or "unknown"
    subject_id = str(event.get("subject_id") or "").strip()
    details = event.get("details") if isinstance(event.get("details"), dict) else {}

    if kind == "approval_transition" and action == "approval_bypass_attempt":
        return _summarize_approval_bypass_event(event)
    if kind == "approval_transition":
        request_id = str(details.get("request_id") or "").strip()
        target = request_id or subject_id or "unknown-request"
        return f"Approval lifecycle recorded action '{action}' for '{target}' with status '{status}'."
    if kind == "align_verdict":
        decisive_action = str(details.get("action") or details.get("decisive_rule_action") or "review")
        return (
            f"ALIGN governance returned status '{status}' with action '{decisive_action}'"
            f" for subject '{subject_id or 'unknown'}'."
        )
    if kind == "routing_decision":
        selected_lane = str(details.get("selected_lane") or details.get("routing_lane") or "governed")
        model = str(details.get("selected_model") or details.get("model") or "")
        model_text = f" using model '{model}'" if model else ""
        return (
            f"Governed routing recorded status '{status}' on lane '{selected_lane}'"
            f"{model_text} for subject '{subject_id or 'unknown'}'."
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
        category = str(details.get("observation", {}).get("category") or details.get("category") or "witness_observation")
        return f"Witness governance recorded category '{category}' at severity '{severity}' for '{subject_id or 'unknown'}'."
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
        return f"Memory governance applied state '{state}' with status '{status}' for subject '{subject_id or 'unknown'}'.{suffix}".replace("..", ".")
    if kind == "entropy_anchor":
        return _summarize_daemon_alert_event(event)
    return f"Governance event '{kind}' recorded action '{action}' with status '{status}' and severity '{severity}'."


def _build_daemon_transparency_report(ctx: object | None) -> dict[str, object]:
    if ctx is None:
        return {"status": "error", "error": "daemon_transparency_unavailable"}

    if hasattr(ctx, "daemon_manager") and hasattr(ctx.daemon_manager, "status_snapshot"):
        snapshot = ctx.daemon_manager.status_snapshot()
        audit_trail = ctx.daemon_manager.get_audit_trail(limit=50)
        recent_alerts = ctx.daemon_manager.get_alerts(limit=20)
        recent_scribe_entries = ctx.daemon_manager.get_scribe_entries(limit=20)
        recent_daemon_events = ctx.daemon_manager.get_daemon_events(limit=20)
        evidence_refs = _dedupe_evidence_refs(
            [entry.get("event_ref") for entry in audit_trail if isinstance(entry, dict)],
            [
                {
                    "kind": "audit",
                    "event_id": str(entry.get("audit_trace_id") or ""),
                    "trace_id": str(entry.get("audit_trace_id") or ""),
                }
                for entry in audit_trail
                if str(entry.get("audit_trace_id") or "")
            ],
        )
        operator_summary = (
            f"Packaged daemon-transparency surface currently tracks {snapshot.get('entry_count', 0)} recent governance event(s), "
            f"{snapshot.get('alert_count', 0)} Sentinel alert(s), and {snapshot.get('scribe_summary', {}).get('entry_count', 0)} Scribe entrie(s)."
        )
        return {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "daemon_transparency": {
                "surface_mode": "packaged_daemon_manager",
                "manager_status": snapshot.get("manager_status"),
                "report_uri": "hlf://reports/daemon_transparency",
                "entry_count": snapshot.get("entry_count", 0),
                "alert_count": snapshot.get("alert_count", 0),
                "category_counts": snapshot.get("category_counts", {}),
                "anomaly_summary": snapshot.get("anomaly_summary", {}),
                "sentinel": {
                    **(snapshot.get("sentinel_summary", {}) if isinstance(snapshot.get("sentinel_summary"), dict) else {}),
                    "recent_alerts": recent_alerts,
                },
                "scribe": {
                    **(snapshot.get("scribe_summary", {}) if isinstance(snapshot.get("scribe_summary"), dict) else {}),
                    "recent_entries": recent_scribe_entries,
                },
                "daemon_bus": {
                    **(snapshot.get("daemon_bus_summary", {}) if isinstance(snapshot.get("daemon_bus_summary"), dict) else {}),
                    "recent_events": recent_daemon_events,
                },
                "audit_trail": audit_trail,
            },
        }

    raw_events = ctx.recent_governance_events(limit=50)
    audit_trail: list[dict[str, object]] = []
    category_counts: dict[str, int] = {}
    alert_count = 0
    blocked_count = 0
    critical_count = 0
    pressured_subjects: set[str] = set()

    for event in raw_events:
        if not isinstance(event, dict):
            continue
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        category = _classify_daemon_transparency_event(event)
        category_counts[category] = category_counts.get(category, 0) + 1
        status = str(event.get("status") or "")
        severity = str(event.get("severity") or "")
        is_alert = status in {"warning", "error", "blocked"} or severity in {"warning", "critical"}
        if is_alert:
            alert_count += 1
            if status == "blocked":
                blocked_count += 1
            if severity == "critical":
                critical_count += 1
            subject_id = str(event.get("subject_id") or "").strip()
            if subject_id:
                pressured_subjects.add(subject_id)
        audit_trail.append(
            {
                "category": category,
                "kind": event.get("kind"),
                "action": event.get("action"),
                "status": event.get("status"),
                "severity": event.get("severity"),
                "source": event.get("source"),
                "subject_id": event.get("subject_id"),
                "goal_id": event.get("goal_id"),
                "timestamp": event.get("timestamp"),
                "event_ref": event.get("event_ref"),
                "audit_trace_id": details.get("audit_trace_id"),
                "is_alert": is_alert,
                "operator_summary": _summarize_daemon_transparency_event(event),
            }
        )

    evidence_refs = _dedupe_evidence_refs(
        [entry.get("event_ref") for entry in audit_trail if isinstance(entry, dict)],
        [
            {
                "kind": "audit",
                "event_id": str(entry.get("audit_trace_id") or ""),
                "trace_id": str(entry.get("audit_trace_id") or ""),
            }
            for entry in audit_trail
            if str(entry.get("audit_trace_id") or "")
        ],
    )
    operator_summary = (
        f"Packaged daemon-transparency surface currently translates {len(audit_trail)} recent governance event(s) "
        f"into {alert_count} alerting and {len(audit_trail) - alert_count} informational audit entrie(s)."
    )
    return {
        "status": "ok",
        "operator_summary": operator_summary,
        "evidence_refs": evidence_refs,
        "daemon_transparency": {
            "surface_mode": "packaged_bridge_proxy",
            "report_uri": "hlf://reports/daemon_transparency",
            "entry_count": len(audit_trail),
            "alert_count": alert_count,
            "category_counts": category_counts,
            "anomaly_summary": {
                "alert_count": alert_count,
                "blocked_count": blocked_count,
                "critical_count": critical_count,
                "pressured_subject_count": len(pressured_subjects),
                "pressured_subjects": sorted(pressured_subjects),
            },
            "audit_trail": audit_trail,
        },
    }


def _render_daemon_transparency_status(ctx: object | None) -> str:
    return json.dumps(_build_daemon_transparency_report(ctx), indent=2)


def _render_daemon_transparency_markdown(ctx: object | None) -> str:
    report = _build_daemon_transparency_report(ctx)
    if report.get("status") != "ok":
        return "# HLF Daemon Transparency Report\n\nDaemon transparency is unavailable."

    transparency = report.get("daemon_transparency") if isinstance(report.get("daemon_transparency"), dict) else {}
    anomaly_summary = transparency.get("anomaly_summary") if isinstance(transparency.get("anomaly_summary"), dict) else {}
    sentinel_summary = transparency.get("sentinel") if isinstance(transparency.get("sentinel"), dict) else {}
    scribe_summary = transparency.get("scribe") if isinstance(transparency.get("scribe"), dict) else {}
    audit_trail = transparency.get("audit_trail") if isinstance(transparency.get("audit_trail"), list) else []
    lines = [
        "# HLF Daemon Transparency Report",
        "",
        "Generated from packaged governance-spine events using the current bridge-mode daemon transparency surface.",
        "",
        f"- Status: {report.get('status')}",
        f"- Summary: {report.get('operator_summary')}",
        f"- Entry count: {transparency.get('entry_count', 0)}",
        f"- Alert count: {transparency.get('alert_count', 0)}",
        f"- Blocked count: {anomaly_summary.get('blocked_count', 0)}",
        f"- Critical count: {anomaly_summary.get('critical_count', 0)}",
        f"- Sentinel alert count: {sentinel_summary.get('alert_count', 0)}",
        f"- Scribe entry count: {scribe_summary.get('entry_count', 0)}",
        f"- Pressured subjects: {', '.join(anomaly_summary.get('pressured_subjects') or []) or 'none'}",
        f"- Structured status: {transparency.get('report_uri', 'hlf://status/daemon_transparency')}",
        "",
        "## Recent Sentinel Alerts",
        "",
        "| Pattern | Severity | Subject | Summary |",
        "| --- | --- | --- | --- |",
        "",
    ]
    for alert in (sentinel_summary.get("recent_alerts") or [])[:10]:
        if not isinstance(alert, dict):
            continue
        lines.append(
            "| {pattern} | {severity} | {subject} | {summary} |".format(
                pattern=str(alert.get("pattern") or "unknown").replace("|", "/"),
                severity=str(alert.get("severity") or "unknown").replace("|", "/"),
                subject=str(alert.get("subject_id") or "unknown").replace("|", "/"),
                summary=str(alert.get("operator_summary") or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Recent Scribe Entries",
            "",
            "| Source | Event Type | Tokens | Prose |",
            "| --- | --- | --- | --- |",
        ]
    )
    for entry in (scribe_summary.get("recent_entries") or [])[:10]:
        if not isinstance(entry, dict):
            continue
        lines.append(
            "| {source} | {event_type} | {tokens} | {prose} |".format(
                source=str(entry.get("source") or "unknown").replace("|", "/"),
                event_type=str(entry.get("event_type") or "unknown").replace("|", "/"),
                tokens=str(entry.get("token_count") or 0).replace("|", "/"),
                prose=str(entry.get("prose") or "").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Recent Audit Trail",
            "",
            "| Category | Kind | Status | Subject | Summary |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for entry in audit_trail[:20]:
        if not isinstance(entry, dict):
            continue
        lines.append(
            "| {category} | {kind} | {status} | {subject} | {summary} |".format(
                category=str(entry.get("category") or "unknown").replace("|", "/"),
                kind=str(entry.get("kind") or "unknown").replace("|", "/"),
                status=str(entry.get("status") or "unknown").replace("|", "/"),
                subject=str(entry.get("subject_id") or "unknown").replace("|", "/"),
                summary=str(entry.get("operator_summary") or "").replace("|", "/"),
            )
        )
    return "\n".join(lines)


def _build_symbolic_surface_sample() -> dict[str, object]:
    source = "\n".join(
        [
            "[HLF-v3]",
            'Δ [RELATE] relation="time.before" from="collect" to="verify"',
            'Δ [RELATE] relation="time.after" from="deploy" to="verify"',
            'Δ [RELATE] relation="cause.enables" from="verify" to="deploy"',
            'Δ [RELATE] relation="cause.blocks" from="policy_gate" to="deploy"',
            'Δ [RELATE] relation="depends.on" from="verify" to="compile"',
            'Δ [RELATE] relation="agent.owns" from="operator" to="release_plan"',
            'Δ [RELATE] relation="agent.delegates" from="scribe" to="verify"',
            'Δ [RELATE] relation="scope.within" from="release_plan" to="program"',
            "Ω",
        ]
    )
    symbolic_surface = compile_symbolic_surface(source)
    relation_family_counts: dict[str, int] = {}
    for edge in symbolic_surface.get("relation_edges", []):
        if not isinstance(edge, dict):
            continue
        family = str(edge.get("relation_family") or "unclassified")
        relation_family_counts[family] = relation_family_counts.get(family, 0) + 1
    return {
        "sample_source": source,
        "symbolic_surface": symbolic_surface,
        "relation_family_counts": relation_family_counts,
    }


def _symbolic_explainer_card_payload(
    relation_artifacts: list[dict[str, object]],
    *,
    source_mode: str,
) -> dict[str, object]:
    card_entries: list[dict[str, object]] = []
    for artifact in relation_artifacts:
        if not isinstance(artifact, dict):
            continue
        card_entries.append(
            {
                "artifact_id": artifact.get("artifact_id"),
                "relation_family": artifact.get("relation_family"),
                "canonical_source": artifact.get("canonical_source"),
                "ascii_projection": artifact.get("ascii_projection"),
                "unicode_projection": artifact.get("unicode_projection"),
                "explanation": artifact.get("explanation"),
                "authority_labels": artifact.get("authority_labels"),
                "display_only": True,
            }
        )
    return {
        "resource_uri": "hlf://explainer/symbolic_surface",
        "surface_mode": "display-only-explainer",
        "source_mode": source_mode,
        "title": "HLF Symbolic Explainer Card",
        "summary": (
            "This explainer card renders symbolic relation artifacts for operator inspection while preserving "
            "canonical ASCII source as the only executable authority."
        ),
        "callouts": [
            "Canonical source remains executable.",
            "Unicode projection remains display-only.",
            "Explanation remains the trust surface.",
        ],
        "entries": card_entries,
    }


def _resolve_symbolic_surface_payload(ctx: object | None) -> tuple[dict[str, object], str]:
    if ctx is not None and hasattr(ctx, "get_symbolic_surface"):
        runtime_record = ctx.get_symbolic_surface()
        if isinstance(runtime_record, dict):
            return runtime_record, "runtime-generated-bundle"
    return _build_symbolic_surface_sample(), "static-proof-bundle"


def _build_symbolic_surface_report(ctx: object | None) -> dict[str, object]:
    payload, source_mode = _resolve_symbolic_surface_payload(ctx)
    if source_mode == "runtime-generated-bundle":
        symbolic_surface = (
            payload.get("symbolic_surface") if isinstance(payload.get("symbolic_surface"), dict) else {}
        )
        sample_source = str(payload.get("source") or "")
        relation_family_counts: dict[str, int] = {}
        for edge in (
            symbolic_surface.get("relation_edges", [])
            if isinstance(symbolic_surface.get("relation_edges"), list)
            else []
        ):
            if not isinstance(edge, dict):
                continue
            family = str(edge.get("relation_family") or "unclassified")
            relation_family_counts[family] = relation_family_counts.get(family, 0) + 1
        audit_entries = payload.get("audit_entries") if isinstance(payload.get("audit_entries"), list) else []
        governance_event_ref = payload.get("governance_event_ref") if isinstance(payload.get("governance_event_ref"), dict) else None
        surface_id = str(payload.get("surface_id") or "")
        goal_id = str(payload.get("goal_id") or "")
        runtime_symbolic_data_present = True
        audit_refs_present = any(
            isinstance(entry, dict) and str(entry.get("trace_id") or "") for entry in audit_entries
        )
        source_summary = (
            f"Latest runtime-generated symbolic surface '{surface_id or 'unknown'}' is being rendered from session state."
        )
    else:
        symbolic_surface = (
            payload.get("symbolic_surface") if isinstance(payload.get("symbolic_surface"), dict) else {}
        )
        sample_source = str(payload.get("sample_source") or "")
        relation_family_counts = dict(payload.get("relation_family_counts") or {})
        audit_entries = []
        governance_event_ref = None
        surface_id = ""
        goal_id = ""
        runtime_symbolic_data_present = False
        audit_refs_present = False
        source_summary = "No runtime-generated symbolic bundle is recorded yet; rendering the packaged proof sample."
    relation_artifacts = (
        symbolic_surface.get("relation_artifacts")
        if isinstance(symbolic_surface.get("relation_artifacts"), list)
        else []
    )
    explanations = (
        symbolic_surface.get("explanations")
        if isinstance(symbolic_surface.get("explanations"), list)
        else []
    )
    evidence_refs = _dedupe_reference_dicts(
        {
            "kind": "symbolic_surface_spec",
            "path": "docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md",
            "claim_lane": "bridge-true",
        },
        {
            "kind": "operator_surface_spec",
            "path": "docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md",
            "surface_type": "generated_report",
        },
        {
            "kind": "symbolic_surface_resource",
            "resource_uri": "hlf://status/symbolic_surface",
            "report_uri": "hlf://reports/symbolic_surface",
            "surface_mode": "inspectable-proof-only",
        },
        {
            "kind": "symbolic_explainer_resource",
            "resource_uri": "hlf://explainer/symbolic_surface",
            "surface_mode": "display-only-explainer",
        },
        governance_event_ref,
        [
            {
                "kind": "audit",
                "event_id": str(entry.get("trace_id") or ""),
                "trace_id": str(entry.get("trace_id") or ""),
            }
            for entry in audit_entries
            if isinstance(entry, dict) and str(entry.get("trace_id") or "")
        ],
        [
            {
                "kind": "symbolic_relation_artifact",
                "artifact_id": str(artifact.get("artifact_id") or ""),
                "canonical_source": str(artifact.get("canonical_source") or ""),
            }
            for artifact in relation_artifacts
            if isinstance(artifact, dict)
        ],
    )
    return {
        "status": "ok",
        "claim_lane": "bridge-true",
        "operator_summary": (
            "Symbolic report renders the same relation-artifact contract for operator review without "
            "changing semantic authority. " + source_summary
        ),
        "evidence_refs": evidence_refs,
        "symbolic_surface": {
            "resource_uri": "hlf://status/symbolic_surface",
            "report_uri": "hlf://reports/symbolic_surface",
            "explainer_uri": "hlf://explainer/symbolic_surface",
            "surface_mode": "inspectable-proof-only",
            "report_id": "symbolic_surface",
            "surface_type": "generated_report",
            "claim_lane": "bridge-true",
            "starter_vocabulary": list(_SYMBOLIC_STARTER_VOCABULARY),
            "authority_boundary": {
                "canonical_source": "canonical-executable",
                "ascii_projection": "plain-text-safe-display",
                "unicode_projection": "display-only",
                "explanation": "trust-surface",
            },
            "relation_family_counts": relation_family_counts,
            "proof_bundle": {
                "sample_source": sample_source,
                "relation_count": len(
                    symbolic_surface.get("relation_edges", [])
                    if isinstance(symbolic_surface.get("relation_edges"), list)
                    else []
                ),
                "relation_artifacts": relation_artifacts,
                "explanations": explanations,
            },
            "provenance_status": {
                "runtime_symbolic_data_present": runtime_symbolic_data_present,
                "audit_refs_present": audit_refs_present,
                "mode": source_mode,
                "surface_id": surface_id,
                "goal_id": goal_id,
                "note": (
                    "Rendering the latest runtime-generated symbolic bundle with audit refs."
                    if runtime_symbolic_data_present
                    else "Real audit or runtime provenance refs remain pending until non-static symbolic bundles are produced by packaged runtime or operator workflows."
                ),
            },
            "taxonomy": {
                "generated_reports": ["hlf://reports/symbolic_surface"],
                "mcp_resources": [
                    "hlf://status/symbolic_surface",
                    "hlf://explainer/symbolic_surface",
                ],
                "static_docs": [
                    "docs/HLF_SYMBOLIC_SEMASIOGRAPHIC_RECOVERY_SPEC.md",
                    "docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md",
                ],
            },
        },
    }


def _render_symbolic_surface_status(ctx: object | None) -> str:
    return json.dumps(_build_symbolic_surface_report(ctx), indent=2)


def _render_symbolic_surface_markdown(ctx: object | None) -> str:
    report = _build_symbolic_surface_report(ctx)
    if report.get("status") != "ok":
        return "# HLF Symbolic Surface Report\n\nSymbolic surface report is unavailable."

    surface = report.get("symbolic_surface") if isinstance(report.get("symbolic_surface"), dict) else {}
    proof_bundle = surface.get("proof_bundle") if isinstance(surface.get("proof_bundle"), dict) else {}
    relation_artifacts = proof_bundle.get("relation_artifacts") if isinstance(proof_bundle.get("relation_artifacts"), list) else []
    provenance_status = surface.get("provenance_status") if isinstance(surface.get("provenance_status"), dict) else {}
    taxonomy = surface.get("taxonomy") if isinstance(surface.get("taxonomy"), dict) else {}
    intro = (
        "Generated from the latest runtime-generated symbolic bundle using canonical ASCII source and derived display-only projections."
        if provenance_status.get("runtime_symbolic_data_present")
        else "Generated from the static packaged symbolic bridge proof bundle using canonical ASCII source and derived display-only projections."
    )
    lines = [
        "# HLF Symbolic Surface Report",
        "",
        intro,
        "",
        f"- Status: {report.get('status')}",
        f"- Claim lane: {report.get('claim_lane')}",
        f"- Summary: {report.get('operator_summary')}",
        f"- Structured status: {surface.get('resource_uri', 'hlf://status/symbolic_surface')}",
        f"- Generated report: {surface.get('report_uri', 'hlf://reports/symbolic_surface')}",
        f"- Explainer card: {surface.get('explainer_uri', 'hlf://explainer/symbolic_surface')}",
        f"- Relation count: {proof_bundle.get('relation_count', 0)}",
        f"- Runtime symbolic data present: {provenance_status.get('runtime_symbolic_data_present', False)}",
        f"- Audit refs present: {provenance_status.get('audit_refs_present', False)}",
        "",
        "## Authority Boundary",
        "",
        f"- Canonical source: {surface.get('authority_boundary', {}).get('canonical_source', 'unknown')}",
        f"- ASCII projection: {surface.get('authority_boundary', {}).get('ascii_projection', 'unknown')}",
        f"- Unicode projection: {surface.get('authority_boundary', {}).get('unicode_projection', 'unknown')}",
        f"- Explanation: {surface.get('authority_boundary', {}).get('explanation', 'unknown')}",
        "",
        "## Starter Vocabulary",
        "",
        f"- {', '.join(surface.get('starter_vocabulary', []))}",
        "",
        "## Relation Artifacts",
        "",
        "| Relation | Family | Canonical Source | ASCII Projection | Unicode Projection | Explanation |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for artifact in relation_artifacts:
        if not isinstance(artifact, dict):
            continue
        relation = str(artifact.get("canonical_source") or "").replace("|", "/")
        family = str(artifact.get("relation_family") or "unknown").replace("|", "/")
        ascii_projection = str(artifact.get("ascii_projection") or "").replace("|", "/")
        unicode_projection = str(artifact.get("unicode_projection") or "").replace("|", "/")
        explanation = str(artifact.get("explanation") or "").replace("|", "/")
        lines.append(
            f"| {relation} | {family} | {relation} | {ascii_projection} | {unicode_projection} | {explanation} |"
        )
    lines.extend(
        [
            "",
            "## Provenance Status",
            "",
            f"- Mode: {provenance_status.get('mode', 'unknown')}",
            f"- Surface id: {provenance_status.get('surface_id', '')}",
            f"- Goal id: {provenance_status.get('goal_id', '')}",
            f"- Note: {provenance_status.get('note', '')}",
            "",
            "## Operator Taxonomy",
            "",
            f"- Generated reports: {', '.join(taxonomy.get('generated_reports', [])) or 'none'}",
            f"- Queryable MCP resources: {', '.join(taxonomy.get('mcp_resources', [])) or 'none'}",
            f"- Static docs: {', '.join(taxonomy.get('static_docs', [])) or 'none'}",
        ]
    )
    return "\n".join(lines)


def _render_symbolic_surface_explainer(ctx: object | None) -> str:
    report = _build_symbolic_surface_report(ctx)
    if report.get("status") != "ok":
        return json.dumps({"status": "error", "error": "symbolic_explainer_unavailable"}, indent=2)
    surface = report.get("symbolic_surface") if isinstance(report.get("symbolic_surface"), dict) else {}
    proof_bundle = surface.get("proof_bundle") if isinstance(surface.get("proof_bundle"), dict) else {}
    relation_artifacts = proof_bundle.get("relation_artifacts") if isinstance(proof_bundle.get("relation_artifacts"), list) else []
    explainer = _symbolic_explainer_card_payload(
        relation_artifacts,
        source_mode=str((surface.get("provenance_status") or {}).get("mode") or "unknown"),
    )
    return json.dumps(
        {
            "status": "ok",
            "claim_lane": report.get("claim_lane"),
            "operator_summary": (
                "Symbolic explainer card renders the same relation artifacts for teaching and operator inspection; "
                "it remains display-only."
            ),
            "evidence_refs": report.get("evidence_refs", []),
            "explainer_card": explainer,
        },
        indent=2,
    )


def _build_fixture_gallery_symbolic_sidecar(ctx: object | None) -> dict[str, object]:
    report = _build_symbolic_surface_report(ctx)
    if report.get("status") != "ok":
        return {
            "status": "unavailable",
            "display_only": True,
            "resource_uri": "hlf://explainer/symbolic_surface",
            "status_uri": "hlf://status/symbolic_surface",
            "report_uri": "hlf://reports/symbolic_surface",
            "source_mode": "unavailable",
            "runtime_symbolic_data_present": False,
            "relation_count": 0,
            "preview_entries": [],
        }

    surface = report.get("symbolic_surface") if isinstance(report.get("symbolic_surface"), dict) else {}
    proof_bundle = surface.get("proof_bundle") if isinstance(surface.get("proof_bundle"), dict) else {}
    provenance_status = surface.get("provenance_status") if isinstance(surface.get("provenance_status"), dict) else {}
    relation_artifacts = (
        proof_bundle.get("relation_artifacts")
        if isinstance(proof_bundle.get("relation_artifacts"), list)
        else []
    )
    explainer = _symbolic_explainer_card_payload(
        relation_artifacts,
        source_mode=str(provenance_status.get("mode") or "unknown"),
    )
    return {
        "status": "ok",
        "display_only": True,
        "resource_uri": str(explainer.get("resource_uri") or "hlf://explainer/symbolic_surface"),
        "status_uri": str(surface.get("resource_uri") or "hlf://status/symbolic_surface"),
        "report_uri": str(surface.get("report_uri") or "hlf://reports/symbolic_surface"),
        "title": str(explainer.get("title") or "HLF Symbolic Explainer Card"),
        "summary": str(explainer.get("summary") or ""),
        "source_mode": str(provenance_status.get("mode") or "unknown"),
        "runtime_symbolic_data_present": bool(provenance_status.get("runtime_symbolic_data_present")),
        "relation_count": int(proof_bundle.get("relation_count") or 0),
        "preview_entries": [
            entry
            for entry in explainer.get("entries", [])[:3]
            if isinstance(entry, dict)
        ],
        "callouts": [
            callout
            for callout in explainer.get("callouts", [])
            if isinstance(callout, str)
        ],
    }


def _summarize_route_fallback(route_trace: dict[str, object]) -> str:
    route_decision = route_trace.get("route_decision")
    fallback_chain = route_trace.get("fallback_chain")
    if not isinstance(route_decision, dict):
        route_decision = {}
    if not isinstance(fallback_chain, list) or not fallback_chain:
        return "No fallback candidates were recorded for this governed route."

    selected_model = str(route_decision.get("primary_model") or "unresolved-model")
    fallback_models = [
        str(candidate.get("model") or "")
        for candidate in fallback_chain
        if isinstance(candidate, dict) and str(candidate.get("model") or "")
    ]
    if selected_model in fallback_models:
        return (
            f"Fallback routing selected '{selected_model}' after considering "
            f"{len(fallback_models)} candidate(s)."
        )
    if not fallback_models:
        return "Fallback metadata exists, but no concrete fallback model names were recorded."
    return (
        f"Primary routing stayed on '{selected_model}' while {len(fallback_models)} fallback "
        f"candidate(s) remained available: {', '.join(fallback_models)}."
    )


def _summarize_route_policy_basis(policy_basis: dict[str, object]) -> dict[str, object]:
    allowlist_policy = policy_basis.get("allowlist_policy")
    if not isinstance(allowlist_policy, dict):
        allowlist_policy = {}

    trust_state = str(policy_basis.get("trust_state") or "healthy")
    trust_source = str(policy_basis.get("trust_state_source") or "request")
    deployment_tier = str(policy_basis.get("deployment_tier") or "")
    missing_profiles = [
        str(profile)
        for profile in (policy_basis.get("missing_evidence_profiles") or [])
        if str(profile)
    ]
    constraints = [
        str(constraint)
        for constraint in (policy_basis.get("policy_constraints") or [])
        if str(constraint)
    ]

    allowlist_reason = str(allowlist_policy.get("reason") or "")
    if allowlist_policy.get("enforced"):
        allowlist_summary = (
            f"Deployment tier '{deployment_tier or 'unspecified'}' enforces model allowlisting."
        )
    elif allowlist_reason:
        allowlist_summary = (
            f"Allowlist enforcement is inactive because '{allowlist_reason}'."
        )
    else:
        allowlist_summary = "Allowlist enforcement is not active for this route."

    evidence_summary = (
        "All required benchmark evidence profiles were present."
        if not missing_profiles
        else "Missing benchmark evidence profiles: " + ", ".join(missing_profiles)
    )

    return {
        "trust_summary": f"Trust posture is '{trust_state}' from source '{trust_source}'.",
        "align_summary": (
            f"ALIGN status is '{policy_basis.get('align_status') or 'unknown'}' with action "
            f"'{policy_basis.get('align_action') or 'ALLOW'}'."
        ),
        "deployment_summary": allowlist_summary,
        "evidence_summary": evidence_summary,
        "constraint_count": len(constraints),
        "constraints": constraints,
        "missing_evidence_profiles": missing_profiles,
    }


def _instinct_phase_completion(mission: dict[str, object]) -> dict[str, bool]:
    phase_order = ["specify", "plan", "execute", "verify", "merge"]
    reached = {
        str(entry.get("phase") or "").strip().lower()
        for entry in (mission.get("phase_history") or [])
        if isinstance(entry, dict)
    }
    return {phase: phase in reached for phase in phase_order}


def _instinct_verification_summary(mission: dict[str, object]) -> dict[str, object]:
    report = mission.get("verification_report")
    if not isinstance(report, dict) or not report:
        return {
            "status": "missing",
            "all_proven": False,
            "result_count": 0,
            "failed_count": 0,
            "unknown_count": 0,
        }

    verdict = str(report.get("verdict") or report.get("status") or "").strip().lower()
    results = report.get("results") if isinstance(report.get("results"), list) else []
    failed_statuses = {"counterexample", "error", "failed", "blocked"}
    unknown_statuses = {"unknown", "timeout", "skipped", "pending"}
    failed_count = sum(
        1
        for item in results
        if isinstance(item, dict)
        and str(item.get("status") or "").strip().lower() in failed_statuses
    )
    unknown_count = sum(
        1
        for item in results
        if isinstance(item, dict)
        and str(item.get("status") or "").strip().lower() in unknown_statuses
    )
    all_proven = bool(report.get("all_proven", False))
    if not all_proven and verdict in {"approved", "passed", "proven"}:
        all_proven = failed_count == 0 and unknown_count == 0
    normalized_status = (
        "proven"
        if all_proven
        else "failed"
        if failed_count > 0
        else "unknown"
        if unknown_count > 0
        else verdict or "recorded"
    )
    return {
        "status": normalized_status,
        "all_proven": all_proven,
        "result_count": len(results),
        "failed_count": failed_count,
        "unknown_count": unknown_count,
    }


def _instinct_proof_summary(mission: dict[str, object]) -> dict[str, object]:
    current_phase = str(mission.get("current_phase") or "unknown")
    phase_completion = _instinct_phase_completion(mission)
    allowed_next = [str(item) for item in (mission.get("allowed_next") or []) if str(item)]
    task_dag = mission.get("task_dag") if isinstance(mission.get("task_dag"), list) else []
    execution_summary = (
        dict(mission.get("execution_summary") or {})
        if isinstance(mission.get("execution_summary"), dict)
        else {}
    )
    orchestration_contract = (
        dict(mission.get("orchestration_contract") or {})
        if isinstance(mission.get("orchestration_contract"), dict)
        else build_orchestration_contract(task_dag, mission.get("execution_trace") or [])
    )
    orchestration_summary = dict(orchestration_contract.get("summary") or {})
    verification_summary = _instinct_verification_summary(mission)
    if isinstance(mission.get("cove_gate"), dict):
        cove_gate = dict(mission.get("cove_gate") or {})
    else:
        cove_gate = {
            "passed": bool(mission.get("cove_gate_passed", False)),
            "failures": int(mission.get("cove_failures") or 0),
        }
    blockers: list[str] = []

    if phase_completion.get("plan") and not task_dag:
        blockers.append("task_dag_missing")
    if current_phase in {"verify", "merge"}:
        if execution_summary.get("all_nodes_recorded") is not True:
            blockers.append("execution_trace_incomplete")
        if execution_summary.get("all_nodes_succeeded") is not True:
            blockers.append("execution_failures_present")
        if orchestration_summary.get("denied_nodes", 0) > 0:
            blockers.append("orchestration_denials_present")
    if current_phase in {"verify", "merge"} and verification_summary["status"] == "missing":
        blockers.append("verification_report_missing")
    if current_phase == "merge" and cove_gate.get("passed") is not True:
        blockers.append("cove_gate_not_passed")
    if current_phase == "merge" and not mission.get("sealed", False):
        blockers.append("merge_not_sealed")

    ready_for_verify = bool(
        current_phase == "execute"
        and execution_summary.get("all_nodes_recorded") is True
        and execution_summary.get("all_nodes_succeeded") is True
    )
    ready_for_merge = bool(
        current_phase == "verify"
        and verification_summary["status"] in {"proven", "approved", "passed"}
        and cove_gate.get("passed") is True
    )
    merge_complete = bool(current_phase == "merge" and mission.get("sealed", False))
    proof_state = (
        "sealed"
        if merge_complete
        else "blocked"
        if blockers
        else "ready_for_merge"
        if ready_for_merge
        else "ready_for_verify"
        if ready_for_verify
        else "in_progress"
    )

    return {
        "proof_state": proof_state,
        "current_phase": current_phase,
        "phase_completion": phase_completion,
        "phase_count_reached": sum(1 for reached in phase_completion.values() if reached),
        "allowed_next": allowed_next,
        "task_count": len(task_dag),
        "execution_summary": execution_summary,
        "orchestration_contract": orchestration_contract,
        "verification_summary": verification_summary,
        "cove_gate": cove_gate,
        "seal_state": {
            "sealed": bool(mission.get("sealed", False)),
            "seal_hash": mission.get("seal_hash"),
        },
        "realignment_count": len(mission.get("realignment_events") or []),
        "ready_for_verify": ready_for_verify,
        "ready_for_merge": ready_for_merge,
        "merge_complete": merge_complete,
        "blockers": blockers,
    }


def _instinct_evidence_refs(mission: dict[str, object]) -> list[dict[str, object]]:
    mission_id = str(mission.get("mission_id") or "").strip()
    refs: list[dict[str, object]] = []
    if mission_id:
        refs.append(
            {
                "kind": "instinct_mission",
                "mission_id": mission_id,
                "current_phase": mission.get("current_phase"),
            }
        )
    for phase, artifact in (mission.get("artifacts") or {}).items():
        if not isinstance(artifact, dict):
            continue
        sha256 = str(artifact.get("sha256") or "").strip()
        if not sha256:
            continue
        refs.append(
            {
                "kind": "instinct_artifact",
                "mission_id": mission_id,
                "phase": str(phase),
                "sha256": sha256,
            }
        )
    if mission.get("seal_hash"):
        refs.append(
            {
                "kind": "instinct_seal",
                "mission_id": mission_id,
                "seal_hash": mission.get("seal_hash"),
            }
        )
    return _dedupe_reference_dicts(refs)


def _instinct_operator_summary(mission: dict[str, object], proof_summary: dict[str, object]) -> str:
    mission_id = str(mission.get("mission_id") or "unknown-mission")
    phase = str(proof_summary.get("current_phase") or "unknown")
    blockers = [str(item) for item in (proof_summary.get("blockers") or []) if str(item)]
    execution_summary = (
        proof_summary.get("execution_summary")
        if isinstance(proof_summary.get("execution_summary"), dict)
        else {}
    )
    verification_summary = (
        proof_summary.get("verification_summary")
        if isinstance(proof_summary.get("verification_summary"), dict)
        else {}
    )
    cove_gate = proof_summary.get("cove_gate") if isinstance(proof_summary.get("cove_gate"), dict) else {}
    orchestration_summary = (
        (proof_summary.get("orchestration_contract") or {}).get("summary")
        if isinstance(proof_summary.get("orchestration_contract"), dict)
        else {}
    )
    persona_bindings = (
        orchestration_summary.get("persona_bindings")
        if isinstance(orchestration_summary.get("persona_bindings"), dict)
        else {}
    )
    summary = (
        f"Instinct mission '{mission_id}' is in phase '{phase}' with proof state "
        f"'{proof_summary.get('proof_state') or 'unknown'}'."
    )
    summary += (
        f" Execution coverage: {execution_summary.get('recorded_nodes', 0)}/"
        f"{execution_summary.get('total_nodes', 0)} node(s) recorded, "
        f"{execution_summary.get('completed_nodes', 0)} completed, "
        f"{execution_summary.get('failed_nodes', 0)} failed."
    )
    summary += (
        f" Verification status: {verification_summary.get('status') or 'missing'}"
        f" with {verification_summary.get('failed_count', 0)} failed and "
        f"{verification_summary.get('unknown_count', 0)} unknown result(s)."
    )
    if orchestration_summary:
        summary += (
            f" Orchestration contract: {orchestration_summary.get('allowed_nodes', 0)} allowed, "
            f"{orchestration_summary.get('denied_nodes', 0)} denied, "
            f"{orchestration_summary.get('escalated_nodes', 0)} escalated, and "
            f"{orchestration_summary.get('dissenting_nodes', 0)} dissenting node(s)."
        )
    if persona_bindings:
        summary += (
            " Persona-aware bindings: "
            + ", ".join(
                f"{persona}={count}" for persona, count in sorted(persona_bindings.items())
            )
            + "."
        )
    if proof_summary.get("merge_complete"):
        summary += " Mission is sealed for merge."
    elif cove_gate.get("passed") is True:
        summary += " CoVE gate has passed."
    if blockers:
        summary += f" Active blockers: {', '.join(blockers)}."
    return summary


def _normalize_host_functions_payload(raw_text: str) -> dict[str, object]:
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        _log.error("Failed to parse governance host_functions.json: %s", exc)
        return {
            "functions": [],
            "status": "error",
            "error": "invalid_governance_json",
        }

    if isinstance(data, dict):
        if "error" in data:
            return {
                "functions": [],
                "status": "error",
                "error": str(data.get("error") or "invalid_governance_payload"),
                "details": data,
            }
        if "functions" in data and isinstance(data["functions"], list):
            return data
        _log.warning(
            "host_functions.json has unexpected top-level dict schema; preserving error state"
        )
        return {
            "functions": [],
            "status": "error",
            "error": "invalid_governance_schema:dict",
            "details": data,
        }

    if isinstance(data, list):
        return {"functions": data}

    _log.warning(
        "host_functions.json has unexpected top-level type %s; preserving error state",
        type(data).__name__,
    )
    return {
        "functions": [],
        "status": "error",
        "error": f"invalid_governance_schema:{type(data).__name__}",
    }


def _read_governance_file(filename: str) -> str:
    path = _GOVERNANCE_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "governance_file_not_found",
            "file": filename,
            "hint": (
                "The governance/ directory is not bundled in wheel installs. "
                "Install from source (`pip install -e .`) or mount the directory "
                "to the container's working directory."
            ),
        },
        indent=2,
    )


def _read_fixture_file(name: str) -> str:
    available = (
        "hello_world, security_audit, delegation, routing, "
        "db_migration, log_analysis, stack_deployment"
    )
    candidates = [
        _PACKAGE_DIR.parent / "fixtures" / f"{name}.hlf",
        _PACKAGE_DIR / "fixtures" / f"{name}.hlf",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return json.dumps(
        {
            "error": "example_not_found",
            "requested": name,
            "available": available,
            "hint": (
                "The fixtures/ directory is not bundled in wheel installs. "
                "Install from source or copy fixtures/ into the package tree."
            ),
        }
    )


def _get_fixture_dir() -> Path | None:
    for path in _FIXTURE_DIR_CANDIDATES:
        if not path.is_dir():
            continue
        try:
            next(path.iterdir(), None)
        except (PermissionError, OSError) as exc:
            _log.warning("Fixtures directory candidate %s is not accessible: %s", path, exc)
            continue
        return path
    return None


def _build_fixture_gallery_report(ctx: object | None) -> dict[str, object]:
    fixture_dir = _get_fixture_dir()
    symbolic_sidecar = _build_fixture_gallery_symbolic_sidecar(ctx)
    if fixture_dir is None:
        return {
            "status": "error",
            "error": "fixtures_directory_missing",
            "message": (
                "No fixtures/ directory found. Checked: "
                + ", ".join(str(p) for p in _FIXTURE_DIR_CANDIDATES)
            ),
            "gallery": {
                "surface_type": "generated_report",
                "report_id": "fixture_gallery",
                "grounded_in_packaged_truth": False,
                "fixture_dir": None,
                "summary": {
                    "fixture_count": 0,
                    "compile_ok_count": 0,
                    "compile_failed_count": 0,
                    "bytecode_ok_count": 0,
                    "bytecode_failed_count": 0,
                },
                "sidecars": {"symbolic_surface": symbolic_sidecar},
                "entries": [],
            },
        }

    fixtures = sorted(fixture_dir.glob("*.hlf"))
    if not fixtures:
        return {
            "status": "warning",
            "warning": "no_fixtures_found",
            "message": f"No .hlf fixtures found in fixtures directory: {fixture_dir}",
            "gallery": {
                "surface_type": "generated_report",
                "report_id": "fixture_gallery",
                "grounded_in_packaged_truth": False,
                "fixture_dir": str(fixture_dir),
                "summary": {
                    "fixture_count": 0,
                    "compile_ok_count": 0,
                    "compile_failed_count": 0,
                    "bytecode_ok_count": 0,
                    "bytecode_failed_count": 0,
                },
                "sidecars": {"symbolic_surface": symbolic_sidecar},
                "entries": [],
            },
        }

    compiler = getattr(ctx, "compiler", None)
    if compiler is None:
        compiler = HLFCompiler()

    bytecoder = getattr(ctx, "bytecoder", None)
    if bytecoder is None:
        bytecoder = HLFBytecode()

    entries: list[dict[str, object]] = []
    compile_ok_count = 0
    bytecode_ok_count = 0

    for path in fixtures:
        source = path.read_text(encoding="utf-8")
        entry: dict[str, object] = {
            "name": path.stem,
            "file": path.name,
            "source_lines": len(source.strip().splitlines()),
            "compile_status": "failed",
            "bytecode_status": "skipped",
            "node_count": 0,
            "gas_estimate": 0,
            "bytecode_size": 0,
            "errors": [],
        }

        try:
            compile_result = compiler.compile(source)
            entry["compile_status"] = "ok"
            entry["node_count"] = compile_result.get("node_count", 0)
            entry["gas_estimate"] = compile_result.get("gas_estimate", 0)
            compile_ok_count += 1
            try:
                bytecode = bytecoder.encode(compile_result["ast"])
                entry["bytecode_status"] = "ok"
                entry["bytecode_size"] = len(bytecode)
                bytecode_ok_count += 1
            except Exception as exc:
                entry["bytecode_status"] = "failed"
                entry["errors"].append(f"Bytecode: {exc}")
        except Exception as exc:
            entry["errors"].append(f"Compile: {exc}")

        entries.append(entry)

    overall_status = "ok"
    if compile_ok_count != len(entries) or bytecode_ok_count != len(entries):
        overall_status = "warning"

    return {
        "status": overall_status,
        "gallery": {
            "surface_type": "generated_report",
            "report_id": "fixture_gallery",
            "grounded_in_packaged_truth": True,
            "taxonomy": {
                "static_docs": [
                    "fixtures/README.md",
                    "docs/HLF_REFERENCE.md",
                    "docs/HLF_GRAMMAR_REFERENCE.md",
                    "docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md",
                ],
                "generated_reports": ["hlf://reports/fixture_gallery"],
                "mcp_resources": [
                    "hlf://status/fixture_gallery",
                    "hlf://examples/{name}",
                    "hlf://explainer/symbolic_surface",
                ],
            },
            "source_authority": [
                "hlf_source/scripts/run_hlf_gallery.py",
                "fixtures/README.md",
                "hlf_mcp/server_resources.py",
            ],
            "fixture_dir": str(fixture_dir),
            "summary": {
                "fixture_count": len(entries),
                "compile_ok_count": compile_ok_count,
                "compile_failed_count": len(entries) - compile_ok_count,
                "bytecode_ok_count": bytecode_ok_count,
                "bytecode_failed_count": len(entries) - bytecode_ok_count,
            },
            "sidecars": {"symbolic_surface": symbolic_sidecar},
            "entries": entries,
        },
    }


def _render_fixture_gallery_status(ctx: object | None) -> str:
    return json.dumps(_build_fixture_gallery_report(ctx), indent=2)


def _render_fixture_gallery_markdown(ctx: object | None) -> str:
    report = _build_fixture_gallery_report(ctx)
    gallery = report["gallery"]
    summary = gallery["summary"]
    symbolic_sidecar = (
        gallery.get("sidecars", {}).get("symbolic_surface")
        if isinstance(gallery.get("sidecars"), dict)
        else {}
    )
    lines = [
        "# HLF Fixture Gallery Report",
        "",
        "Generated from packaged fixtures using the current packaged compiler and bytecode encoder.",
        "",
        f"- Status: {report['status']}",
        f"- Fixture count: {summary['fixture_count']}",
        f"- AST compile OK: {summary['compile_ok_count']}/{summary['fixture_count']}",
        f"- Bytecode compile OK: {summary['bytecode_ok_count']}/{summary['fixture_count']}",
        "- Grounding: packaged fixtures plus packaged compiler and bytecode encoder",
        "",
        "| Fixture | Lines | AST | Bytecode | Nodes | Gas | Bytes |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: |",
    ]

    for entry in gallery["entries"]:
        lines.append(
            "| {name} | {source_lines} | {compile_status} | {bytecode_status} | {node_count} | {gas_estimate} | {bytecode_size} |".format(
                **entry
            )
        )
        errors = entry.get("errors") or []
        if errors:
            lines.append(f"| {entry['name']} errors | - | {'; '.join(errors)} | - | - | - | - |")

    lines.extend(
        [
            "",
            "## Symbolic Sidecar",
            "",
            f"- Display only: {symbolic_sidecar.get('display_only', True)}",
            f"- Symbolic explainer: {symbolic_sidecar.get('resource_uri', 'hlf://explainer/symbolic_surface')}",
            f"- Symbolic status: {symbolic_sidecar.get('status_uri', 'hlf://status/symbolic_surface')}",
            f"- Symbolic report: {symbolic_sidecar.get('report_uri', 'hlf://reports/symbolic_surface')}",
            f"- Source mode: {symbolic_sidecar.get('source_mode', 'unknown')}",
            f"- Relation count: {symbolic_sidecar.get('relation_count', 0)}",
            "",
            "## Taxonomy",
            "",
            "- Static docs: fixtures/README.md, docs/HLF_REFERENCE.md, docs/HLF_GRAMMAR_REFERENCE.md, docs/HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md",
            "- Generated report: hlf://reports/fixture_gallery",
            "- Queryable MCP resources: hlf://status/fixture_gallery, hlf://examples/{name}, hlf://explainer/symbolic_surface",
        ]
    )
    return "\n".join(lines) + "\n"

def _render_translation_contract_status(
    ctx: object | None,
    *,
    contract_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_translation_contract"):
        return json.dumps({"status": "error", "error": "translation_contract_unavailable"}, indent=2)
    contract = ctx.get_translation_contract(contract_id=contract_id)
    if not isinstance(contract, dict):
        return json.dumps({"status": "not_found", "contract_id": contract_id}, indent=2)
    governance_event = contract.get("governance_event") if isinstance(contract.get("governance_event"), dict) else {}
    intent = contract.get("intent") if isinstance(contract.get("intent"), dict) else {}
    canonical_hlf = contract.get("canonical_hlf") if isinstance(contract.get("canonical_hlf"), dict) else {}
    governance = contract.get("governance") if isinstance(contract.get("governance"), dict) else {}
    memory_contract = contract.get("memory") if isinstance(contract.get("memory"), dict) else {}
    evidence_refs = _dedupe_evidence_refs(
        governance_event.get("event_ref"),
        governance_event.get("event", {}).get("related_refs") if isinstance(governance_event.get("event"), dict) else None,
        memory_contract.get("governance_event_ref"),
    )
    translation_contract_surface = {
        "surface_type": "translation_contract_chain",
        "resource_uri": f"hlf://status/translation_contract/{contract.get('contract_id')}",
        "report_uri": f"hlf://reports/translation_contract/{contract.get('contract_id')}",
        "contract_id": contract.get("contract_id"),
        "intent_language": intent.get("language"),
        "tier": intent.get("tier"),
        "governed": governance.get("governed", False),
        "ast_sha256": canonical_hlf.get("ast_sha256"),
        "statement_count": canonical_hlf.get("statement_count", 0),
        "has_memory_backing": bool(memory_contract.get("sha256")),
        "operator_summary": contract.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": contract.get("operator_summary")
            or "Latest translation contract chain is available.",
            "evidence_refs": evidence_refs,
            "translation_contract_surface": translation_contract_surface,
            "translation_contract": contract,
        },
        indent=2,
    )


def _render_translation_contract_markdown(
    ctx: object | None,
    *,
    contract_id: str | None = None,
) -> str:
    payload = json.loads(_render_translation_contract_status(ctx, contract_id=contract_id))
    if payload.get("status") != "ok":
        return "# HLF Translation Contract Report\n\nNo translation contract is currently available.\n"
    surface = (
        payload.get("translation_contract_surface")
        if isinstance(payload.get("translation_contract_surface"), dict)
        else {}
    )
    contract = payload.get("translation_contract") if isinstance(payload.get("translation_contract"), dict) else {}
    proof = contract.get("proof") if isinstance(contract.get("proof"), dict) else {}
    compile_proof = proof.get("compile") if isinstance(proof.get("compile"), dict) else {}
    math_proof = proof.get("math") if isinstance(proof.get("math"), dict) else {}
    audit_surfaces = proof.get("audit_surfaces") if isinstance(proof.get("audit_surfaces"), dict) else {}
    artifacts = contract.get("artifacts") if isinstance(contract.get("artifacts"), dict) else {}
    lines = [
        "# HLF Translation Contract Report",
        "",
        "Generated from the latest persisted translation contract chain without introducing a second authority layer.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Contract ID: {surface.get('contract_id')}",
        f"- Intent language: {surface.get('intent_language')}",
        f"- Tier: {surface.get('tier')}",
        f"- Governed: {surface.get('governed')}",
        f"- Statement count: {surface.get('statement_count')}",
        f"- AST SHA256: {surface.get('ast_sha256')}",
        f"- Memory backed: {surface.get('has_memory_backing')}",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
        "",
        "## Compile And Audit Chain",
        "",
        f"- Gas estimate: {compile_proof.get('gas_estimate', 0)}",
        f"- Compression pct: {math_proof.get('compression_pct', 0.0)}",
        f"- Bytecode size: {artifacts.get('bytecode_size_bytes', 0)} byte(s)",
        f"- Runtime target: {artifacts.get('runtime', 'HLFRuntime')}",
        "",
        "## Audit Summaries",
        "",
        f"- Localized summary: {audit_surfaces.get('localized_summary', '')}",
        f"- English summary: {audit_surfaces.get('english_summary', '')}",
        f"- Bytecode summary: {audit_surfaces.get('bytecode_summary_en', '')}",
    ]
    return "\n".join(lines).strip() + "\n"


def _render_governed_recall_status(
    ctx: object | None,
    *,
    recall_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_governed_recall"):
        return json.dumps({"status": "error", "error": "governed_recall_unavailable"}, indent=2)
    recall = ctx.get_governed_recall(recall_id=recall_id)
    if not isinstance(recall, dict):
        return json.dumps({"status": "not_found", "recall_id": recall_id}, indent=2)
    results = recall.get("results") if isinstance(recall.get("results"), list) else []
    entry_kinds = [str(item) for item in (recall.get("entry_kinds") or []) if str(item)]
    weekly_sync = recall.get("weekly_sync") if isinstance(recall.get("weekly_sync"), dict) else {}
    evidence_summary = (
        recall.get("evidence_summary") if isinstance(recall.get("evidence_summary"), dict) else {}
    )
    recall_summary = (
        recall.get("recall_summary") if isinstance(recall.get("recall_summary"), dict) else {}
    )
    evidence_refs = _dedupe_evidence_refs(
        recall.get("evidence_refs"),
        recall.get("governance_event", {}).get("event_ref") if isinstance(recall.get("governance_event"), dict) else None,
    )
    surface = {
        "surface_type": "governed_recall_chain",
        "resource_uri": f"hlf://status/governed_recall/{recall.get('recall_id')}",
        "report_uri": f"hlf://reports/governed_recall/{recall.get('recall_id')}",
        "recall_id": recall.get("recall_id"),
        "recall_kind": recall.get("recall_kind"),
        "query": recall.get("query"),
        "result_count": recall.get("count", len(results)),
        "entry_kinds": entry_kinds,
        "weekly_sync_count": int(weekly_sync.get("count") or 0),
        "evidence_backed_count": int(evidence_summary.get("evidence_backed_count") or 0),
        "archive_visibility": recall_summary.get("archive_visibility") or "filtered_by_default",
        "active_result_count": int(recall_summary.get("active_result_count") or 0),
        "archived_result_count": int(recall_summary.get("archived_result_count") or 0),
        "graph_linked_result_count": int(recall_summary.get("graph_linked_result_count") or 0),
        "admission_decision_counts": dict(recall_summary.get("admission_decision_counts") or {}),
        "retrieval_path_counts": dict(recall_summary.get("retrieval_path_counts") or {}),
        "retrieval_contract": dict(recall.get("retrieval_contract") or {}),
        "path_status": dict((recall.get("retrieval_contract") or {}).get("path_status") or {}),
        "graph_traversal_totals": dict(
            (recall.get("retrieval_contract") or {}).get("graph_traversal_totals") or {}
        ),
        "operator_summary": recall.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": recall.get("operator_summary") or "Latest governed recall contract is available.",
            "evidence_refs": evidence_refs,
            "governed_recall_surface": surface,
            "governed_recall": recall,
        },
        indent=2,
    )


def _render_governed_recall_markdown(
    ctx: object | None,
    *,
    recall_id: str | None = None,
) -> str:
    payload = json.loads(_render_governed_recall_status(ctx, recall_id=recall_id))
    if payload.get("status") != "ok":
        return "# HLF Governed Recall Report\n\nNo governed recall contract is currently available.\n"
    surface = payload.get("governed_recall_surface") if isinstance(payload.get("governed_recall_surface"), dict) else {}
    recall = payload.get("governed_recall") if isinstance(payload.get("governed_recall"), dict) else {}
    weekly_sync = recall.get("weekly_sync") if isinstance(recall.get("weekly_sync"), dict) else {}
    recall_summary = (
        recall.get("recall_summary") if isinstance(recall.get("recall_summary"), dict) else {}
    )
    lines = [
        "# HLF Governed Recall Report",
        "",
        "Generated from the latest persisted governed recall chain without introducing a second recall authority layer.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Recall ID: {surface.get('recall_id')}",
        f"- Recall kind: {surface.get('recall_kind')}",
        f"- Query: {surface.get('query')}",
        f"- Result count: {surface.get('result_count')}",
        f"- Active result count: {surface.get('active_result_count')}",
        f"- Archived result count: {surface.get('archived_result_count')}",
        f"- Graph-linked result count: {surface.get('graph_linked_result_count')}",
        f"- Archive visibility: {surface.get('archive_visibility')}",
        f"- Entry kinds: {', '.join(surface.get('entry_kinds') or []) or 'none'}",
        f"- Weekly sync count: {surface.get('weekly_sync_count')}",
        f"- Evidence-backed count: {surface.get('evidence_backed_count')}",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
        "",
        "## Retrieval Contract",
        "",
        f"- Query mode: {surface.get('retrieval_contract', {}).get('query_mode')}",
        f"- Runtime purpose: {surface.get('retrieval_contract', {}).get('purpose')}",
        f"- Active paths: {json.dumps(surface.get('retrieval_contract', {}).get('active_paths', []))}",
        f"- Path status: {json.dumps(surface.get('path_status', {}), sort_keys=True)}",
        f"- Graph traversal totals: {json.dumps(surface.get('graph_traversal_totals', {}), sort_keys=True)}",
        f"- Surface filtered out count: {surface.get('retrieval_contract', {}).get('surface_filtered_out_count', 0)}",
        f"- Surface truncated count: {surface.get('retrieval_contract', {}).get('surface_truncated_count', 0)}",
        "",
        "## Weekly Sync",
        "",
        f"- Sync status: {weekly_sync.get('status')}",
        f"- Metrics dir: {weekly_sync.get('metrics_dir')}",
        f"- Artifact count: {weekly_sync.get('count', 0)}",
    ]
    if recall_summary:
        lines.extend(
            [
                "",
                "## Admission Summary",
                "",
                f"- Admission decisions: {json.dumps(recall_summary.get('admission_decision_counts', {}), sort_keys=True)}",
                f"- Retrieval paths: {json.dumps(recall_summary.get('retrieval_path_counts', {}), sort_keys=True)}",
                f"- Memory strata: {json.dumps(recall_summary.get('memory_strata_counts', {}), sort_keys=True)}",
                f"- Storage tiers: {json.dumps(recall_summary.get('storage_tier_counts', {}), sort_keys=True)}",
            ]
        )
    results = recall.get("results") if isinstance(recall.get("results"), list) else []
    if results:
        lines.extend(
            [
                "",
                "## Recent Results",
                "",
                "| Entry Kind | Topic | Domain | Solution Kind | Governance State | Provenance Grade |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in results[:10]:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
            lines.append(
                "| {entry_kind} | {topic} | {domain} | {solution_kind} | {state} | {provenance_grade} |".format(
                    entry_kind=str(item.get("entry_kind") or "-").replace("|", "/"),
                    topic=str(item.get("topic") or "-").replace("|", "/"),
                    domain=str(item.get("domain") or "-").replace("|", "/"),
                    solution_kind=str(item.get("solution_kind") or "-").replace("|", "/"),
                    state=str(evidence.get("state") or item.get("governance_status") or "-").replace("|", "/"),
                    provenance_grade=str(evidence.get("provenance_grade") or "-").replace("|", "/"),
                )
            )
            retrieval = item.get("retrieval_contract") if isinstance(item.get("retrieval_contract"), dict) else {}
            graph_summary = (
                retrieval.get("graph_traversal_summary")
                if isinstance(retrieval.get("graph_traversal_summary"), dict)
                else {}
            )
            lines.extend(
                [
                    "",
                    "  Retrieval detail:",
                    f"  primary={retrieval.get('primary_path')} paths={json.dumps(retrieval.get('applied_paths', []))} ",
                    f"graph={json.dumps(graph_summary, sort_keys=True)} path_status={json.dumps(retrieval.get('path_status', {}), sort_keys=True)}",
                ]
            )
    return "\n".join(lines).strip() + "\n"


def _build_latest_recall_knowledge_posture(ctx: object | None) -> dict[str, Any]:
    if ctx is None or not hasattr(ctx, "get_governed_recall"):
        return {}
    recall = ctx.get_governed_recall()
    if not isinstance(recall, dict):
        return {}
    recall_summary = recall.get("recall_summary") if isinstance(recall.get("recall_summary"), dict) else {}
    retrieval_contract = recall.get("retrieval_contract") if isinstance(recall.get("retrieval_contract"), dict) else {}
    return {
        "recall_id": recall.get("recall_id"),
        "result_count": int(recall.get("count") or len(recall.get("results") or [])),
        "archive_visibility": recall_summary.get("archive_visibility") or "filtered_by_default",
        "evidence_backed_count": int(recall_summary.get("evidence_backed_count") or 0),
        "graph_linked_result_count": int(recall_summary.get("graph_linked_result_count") or 0),
        "retrieval_path_counts": dict(recall_summary.get("retrieval_path_counts") or {}),
        "active_paths": list(retrieval_contract.get("active_paths") or []),
        "operator_summary": recall.get("operator_summary") or "",
        "governance_event_ref": (
            recall.get("governance_event", {}).get("event_ref")
            if isinstance(recall.get("governance_event"), dict)
            else None
        ),
    }


def _render_hks_evaluation_status(
    ctx: object | None,
    *,
    evaluation_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_hks_evaluation"):
        return json.dumps({"status": "error", "error": "hks_evaluation_unavailable"}, indent=2)
    evaluation = ctx.get_hks_evaluation(evaluation_id=evaluation_id)
    if not isinstance(evaluation, dict):
        return json.dumps({"status": "not_found", "evaluation_id": evaluation_id}, indent=2)
    surface = {
        "surface_type": "hks_evaluation_chain",
        "resource_uri": f"hlf://status/hks_evaluation/{evaluation.get('evaluation_id')}",
        "report_uri": f"hlf://reports/hks_evaluation/{evaluation.get('evaluation_id')}",
        "evaluation_id": evaluation.get("evaluation_id"),
        "source_kind": evaluation.get("source_kind"),
        "source_ref": evaluation.get("source_ref"),
        "result_count": evaluation.get("result_count", 0),
        "evaluated_result_count": evaluation.get("evaluated_result_count", 0),
        "local_hks_count": evaluation.get("local_hks_count", 0),
        "external_comparator_count": evaluation.get("external_comparator_count", 0),
        "explicit_local_evaluation_count": evaluation.get("explicit_local_evaluation_count", 0),
        "promotion_eligible_count": evaluation.get("promotion_eligible_count", 0),
        "requires_local_recheck_count": evaluation.get("requires_local_recheck_count", 0),
        "raw_intake_count": evaluation.get("raw_intake_count", 0),
        "canonical_knowledge_count": evaluation.get("canonical_knowledge_count", 0),
        "canonical_source_count": evaluation.get("canonical_source_count", 0),
        "advisory_source_count": evaluation.get("advisory_source_count", 0),
        "average_extraction_fidelity_score": evaluation.get("average_extraction_fidelity_score"),
        "operator_summary": evaluation.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": evaluation.get("operator_summary") or "Latest HKS evaluation chain is available.",
            "evidence_refs": _dedupe_evidence_refs(evaluation.get("evidence_refs")),
            "hks_evaluation_surface": surface,
            "hks_evaluation": evaluation,
        },
        indent=2,
    )


def _render_hks_evaluation_markdown(
    ctx: object | None,
    *,
    evaluation_id: str | None = None,
) -> str:
    payload = json.loads(_render_hks_evaluation_status(ctx, evaluation_id=evaluation_id))
    if payload.get("status") != "ok":
        return "# HLF HKS Evaluation Report\n\nNo HKS evaluation chain is currently available.\n"
    surface = payload.get("hks_evaluation_surface") if isinstance(payload.get("hks_evaluation_surface"), dict) else {}
    evaluation = payload.get("hks_evaluation") if isinstance(payload.get("hks_evaluation"), dict) else {}
    lines = [
        "# HLF HKS Evaluation Report",
        "",
        "Generated from the latest persisted HKS evaluation chain without promoting bridge-only evidence into admission authority.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Evaluation ID: {surface.get('evaluation_id')}",
        f"- Source kind: {surface.get('source_kind')}",
        f"- Source ref: {surface.get('source_ref')}",
        f"- Result count: {surface.get('result_count')}",
        f"- Evaluated result count: {surface.get('evaluated_result_count')}",
        f"- Local HKS count: {surface.get('local_hks_count')}",
        f"- External comparator count: {surface.get('external_comparator_count')}",
        f"- Explicit local evaluation count: {surface.get('explicit_local_evaluation_count')}",
        f"- Promotion eligible count: {surface.get('promotion_eligible_count')}",
        f"- Requires local recheck count: {surface.get('requires_local_recheck_count')}",
        f"- Raw intake count: {surface.get('raw_intake_count')}",
        f"- Canonical knowledge count: {surface.get('canonical_knowledge_count')}",
        f"- Canonical source count: {surface.get('canonical_source_count')}",
        f"- Advisory source count: {surface.get('advisory_source_count')}",
        f"- Average extraction fidelity score: {surface.get('average_extraction_fidelity_score')}",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
    ]
    results = evaluation.get("results") if isinstance(evaluation.get("results"), list) else []
    if results:
        lines.extend(
            [
                "",
                "## Evaluation Results",
                "",
                "| Entry Kind | Topic | Authority | Artifact Form | Source Label | Explicit Local Evaluation | Promotion Eligible | Requires Local Recheck | Lane |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in results[:10]:
            if not isinstance(item, dict):
                continue
            item_eval = item.get("evaluation") if isinstance(item.get("evaluation"), dict) else {}
            item_capture = item.get("source_capture") if isinstance(item.get("source_capture"), dict) else {}
            item_artifact = item.get("artifact_contract") if isinstance(item.get("artifact_contract"), dict) else {}
            lines.append(
                "| {entry_kind} | {topic} | {authority} | {artifact_form} | {source_authority_label} | {explicit_local_evaluation_present} | {promotion_eligible} | {requires_local_recheck} | {lane} |".format(
                    entry_kind=str(item.get("entry_kind") or "-").replace("|", "/"),
                    topic=str(item.get("topic") or "-").replace("|", "/"),
                    authority=str(item_eval.get("authority") or "-").replace("|", "/"),
                    artifact_form=str(item_artifact.get("artifact_form") or "-").replace("|", "/"),
                    source_authority_label=str(item_capture.get("source_authority_label") or "-").replace("|", "/"),
                    explicit_local_evaluation_present=str(item_eval.get("explicit_local_evaluation_present") or False).lower(),
                    promotion_eligible=str(item_eval.get("promotion_eligible") or False).lower(),
                    requires_local_recheck=str(item_eval.get("requires_local_recheck") or False).lower(),
                    lane=str(item_eval.get("lane") or "-").replace("|", "/"),
                )
            )
    return "\n".join(lines).strip() + "\n"


def _render_hks_external_compare_status(
    ctx: object | None,
    *,
    compare_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_hks_external_compare"):
        return json.dumps({"status": "error", "error": "hks_external_compare_unavailable"}, indent=2)
    compare = ctx.get_hks_external_compare(compare_id=compare_id)
    if not isinstance(compare, dict):
        return json.dumps({"status": "not_found", "compare_id": compare_id}, indent=2)
    surface = {
        "surface_type": "hks_external_compare_contract",
        "resource_uri": f"hlf://status/hks_external_compare/{compare.get('compare_id')}",
        "report_uri": f"hlf://reports/hks_external_compare/{compare.get('compare_id')}",
        "compare_id": compare.get("compare_id"),
        "query": compare.get("query"),
        "comparator_name": compare.get("comparator_name"),
        "local_result_count": compare.get("local_result_count", 0),
        "comparator_result_count": compare.get("comparator_result_count", 0),
        "operator_summary": compare.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": compare.get("operator_summary") or "Latest HKS external compare contract is available.",
            "evidence_refs": _dedupe_evidence_refs(compare.get("evidence_refs")),
            "hks_external_compare_surface": surface,
            "hks_external_compare": compare,
        },
        indent=2,
    )


def _render_hks_external_compare_markdown(
    ctx: object | None,
    *,
    compare_id: str | None = None,
) -> str:
    payload = json.loads(_render_hks_external_compare_status(ctx, compare_id=compare_id))
    if payload.get("status") != "ok":
        return "# HLF HKS External Compare Report\n\nNo HKS external comparator contract is currently available.\n"
    surface = payload.get("hks_external_compare_surface") if isinstance(payload.get("hks_external_compare_surface"), dict) else {}
    compare = payload.get("hks_external_compare") if isinstance(payload.get("hks_external_compare"), dict) else {}
    lines = [
        "# HLF HKS External Compare Report",
        "",
        "Generated from the latest quarantined external comparator contract. Comparator output is advisory-only until local HKS re-evaluation occurs.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Compare ID: {surface.get('compare_id')}",
        f"- Query: {surface.get('query')}",
        f"- Comparator name: {surface.get('comparator_name')}",
        f"- Local result count: {surface.get('local_result_count')}",
        f"- Comparator result count: {surface.get('comparator_result_count')}",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
    ]
    comparator_results = compare.get("comparator_results") if isinstance(compare.get("comparator_results"), list) else []
    if comparator_results:
        lines.extend(
            [
                "",
                "## Comparator Results",
                "",
                "| Rank | Title | Score | URL |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in comparator_results[:10]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {rank} | {title} | {score} | {url} |".format(
                    rank=str(item.get("rank") or "-").replace("|", "/"),
                    title=str(item.get("title") or "-").replace("|", "/"),
                    score=str(item.get("score") or "-").replace("|", "/"),
                    url=str(item.get("url") or item.get("source") or "-").replace("|", "/"),
                )
            )
    return "\n".join(lines).strip() + "\n"


def _render_hks_weekly_refresh_status(
    ctx: object | None,
    *,
    refresh_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_hks_weekly_refresh"):
        return json.dumps({"status": "error", "error": "hks_weekly_refresh_unavailable"}, indent=2)
    refresh = ctx.get_hks_weekly_refresh(refresh_id=refresh_id)
    if not isinstance(refresh, dict):
        return json.dumps({"status": "not_found", "refresh_id": refresh_id}, indent=2)
    surface = {
        "surface_type": "hks_weekly_refresh_chain",
        "resource_uri": f"hlf://status/hks_weekly_refresh/{refresh.get('refresh_id')}",
        "report_uri": f"hlf://reports/hks_weekly_refresh/{refresh.get('refresh_id')}",
        "refresh_id": refresh.get("refresh_id"),
        "refresh_kind": refresh.get("refresh_kind"),
        "verified_artifact_count": refresh.get("verified_artifact_count", 0),
        "mirrored_weekly_artifact_count": refresh.get("mirrored_weekly_artifact_count", 0),
        "unsynced_artifact_count": refresh.get("unsynced_artifact_count", 0),
        "stale_domain_count": refresh.get("stale_domain_count", 0),
        "stale_topic_count": refresh.get("stale_topic_count", 0),
        "queued_action_count": refresh.get("queued_action_count", 0),
        "stale_after_days": refresh.get("stale_after_days"),
        "operator_summary": refresh.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": refresh.get("operator_summary") or "Latest HKS weekly refresh contract is available.",
            "evidence_refs": _dedupe_evidence_refs(refresh.get("evidence_refs")),
            "hks_weekly_refresh_surface": surface,
            "hks_weekly_refresh": refresh,
        },
        indent=2,
    )


def _render_hks_weekly_refresh_markdown(
    ctx: object | None,
    *,
    refresh_id: str | None = None,
) -> str:
    payload = json.loads(_render_hks_weekly_refresh_status(ctx, refresh_id=refresh_id))
    if payload.get("status") != "ok":
        return "# HLF HKS Weekly Refresh Report\n\nNo HKS weekly refresh contract is currently available.\n"
    surface = payload.get("hks_weekly_refresh_surface") if isinstance(payload.get("hks_weekly_refresh_surface"), dict) else {}
    refresh = payload.get("hks_weekly_refresh") if isinstance(payload.get("hks_weekly_refresh"), dict) else {}
    lines = [
        "# HLF HKS Weekly Refresh Report",
        "",
        "Generated from the latest persisted HKS weekly drift and stale-domain analysis; queued actions remain bridge-lane advisory work until executed.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Refresh ID: {surface.get('refresh_id')}",
        f"- Verified artifact count: {surface.get('verified_artifact_count')}",
        f"- Mirrored weekly artifact count: {surface.get('mirrored_weekly_artifact_count')}",
        f"- Unsynced artifact count: {surface.get('unsynced_artifact_count')}",
        f"- Stale domain count: {surface.get('stale_domain_count')}",
        f"- Stale topic count: {surface.get('stale_topic_count')}",
        f"- Queued action count: {surface.get('queued_action_count')}",
        f"- Weekly freshness window: {surface.get('stale_after_days')} day(s)",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
    ]
    domain_statuses = refresh.get("domain_statuses") if isinstance(refresh.get("domain_statuses"), list) else []
    if domain_statuses:
        lines.extend(
            [
                "",
                "## Domain Drift",
                "",
                "| Domain | Status | Fact Count | Active Fact Count | Latest Memory At |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for item in domain_statuses:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {domain} | {status} | {fact_count} | {active_fact_count} | {latest_memory_at} |".format(
                    domain=str(item.get("domain") or "-").replace("|", "/"),
                    status=str(item.get("status") or "-").replace("|", "/"),
                    fact_count=item.get("fact_count", 0),
                    active_fact_count=item.get("active_fact_count", 0),
                    latest_memory_at=str(item.get("latest_memory_at") or "-").replace("|", "/"),
                )
            )
    topic_statuses = refresh.get("topic_statuses") if isinstance(refresh.get("topic_statuses"), list) else []
    if topic_statuses:
        lines.extend(
            [
                "",
                "## Topic Drift",
                "",
                "| Source Topic | Status | Latest Verified At | Latest Synced At |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in topic_statuses:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {source} | {status} | {latest_verified_at} | {latest_synced_at} |".format(
                    source=str(item.get("source") or "-").replace("|", "/"),
                    status=str(item.get("status") or "-").replace("|", "/"),
                    latest_verified_at=str(item.get("latest_verified_at") or "-").replace("|", "/"),
                    latest_synced_at=str(item.get("latest_synced_at") or "-").replace("|", "/"),
                )
            )
    queued_actions = refresh.get("queued_actions") if isinstance(refresh.get("queued_actions"), list) else []
    if queued_actions:
        lines.extend(
            [
                "",
                "## Queued Actions",
                "",
                "| Action Kind | Target Type | Target ID | Priority | Status | Rationale |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in queued_actions:
            if not isinstance(item, dict):
                continue
            lines.append(
                "| {action_kind} | {target_type} | {target_id} | {priority} | {status} | {rationale} |".format(
                    action_kind=str(item.get("action_kind") or "-").replace("|", "/"),
                    target_type=str(item.get("target_type") or "-").replace("|", "/"),
                    target_id=str(item.get("target_id") or "-").replace("|", "/"),
                    priority=str(item.get("priority") or "-").replace("|", "/"),
                    status=str(item.get("status") or "-").replace("|", "/"),
                    rationale=str(item.get("rationale") or "-").replace("|", "/"),
                )
            )
    return "\n".join(lines).strip() + "\n"


def _build_native_comprehension_index(ctx: object | None) -> dict[str, object]:
    translation_payload = json.loads(_render_translation_contract_status(ctx))
    translation_surface = (
        translation_payload.get("translation_contract_surface")
        if isinstance(translation_payload.get("translation_contract_surface"), dict)
        else {}
    )

    governed_recall_payload = json.loads(_render_governed_recall_status(ctx))
    governed_recall_surface = (
        governed_recall_payload.get("governed_recall_surface")
        if isinstance(governed_recall_payload.get("governed_recall_surface"), dict)
        else {}
    )

    symbolic_payload = _build_symbolic_surface_report(ctx)
    symbolic_surface = (
        symbolic_payload.get("symbolic_surface")
        if isinstance(symbolic_payload.get("symbolic_surface"), dict)
        else {}
    )

    hks_evaluation_payload = json.loads(_render_hks_evaluation_status(ctx))
    hks_evaluation_surface = (
        hks_evaluation_payload.get("hks_evaluation_surface")
        if isinstance(hks_evaluation_payload.get("hks_evaluation_surface"), dict)
        else {}
    )

    hks_external_compare_payload = json.loads(_render_hks_external_compare_status(ctx))
    hks_external_compare_surface = (
        hks_external_compare_payload.get("hks_external_compare_surface")
        if isinstance(hks_external_compare_payload.get("hks_external_compare_surface"), dict)
        else {}
    )

    entries = [
        {
            "surface_id": "translation_contract",
            "title": "Translation Contract Reading",
            "order": 1,
            "focus": "Read how natural-language intent becomes canonical governed HLF and bytecode-backed proof.",
            "resource_uri": "hlf://teach/native_comprehension/translation_contract",
            "source_status_uri": "hlf://status/translation_contract",
            "source_report_uri": "hlf://reports/translation_contract",
            "source_explainer_uri": None,
            "source_status": translation_payload.get("status"),
            "operator_summary": (
                translation_payload.get("operator_summary")
                or translation_surface.get("operator_summary")
                or "Translation contract reading packet is available."
            ),
        },
        {
            "surface_id": "governed_recall",
            "title": "Governed Recall Reading",
            "order": 2,
            "focus": "Read how HKS and Infinite RAG evidence is recalled through governed contracts rather than generic search.",
            "resource_uri": "hlf://teach/native_comprehension/governed_recall",
            "source_status_uri": "hlf://status/governed_recall",
            "source_report_uri": "hlf://reports/governed_recall",
            "source_explainer_uri": None,
            "source_status": governed_recall_payload.get("status"),
            "operator_summary": (
                governed_recall_payload.get("operator_summary")
                or governed_recall_surface.get("operator_summary")
                or "Governed recall reading packet is available."
            ),
        },
        {
            "surface_id": "symbolic_surface",
            "title": "Symbolic Surface Reading",
            "order": 3,
            "focus": "Read relation artifacts, symbolic vocabulary, and display-only projection without crossing executable authority boundaries.",
            "resource_uri": "hlf://teach/native_comprehension/symbolic_surface",
            "source_status_uri": "hlf://status/symbolic_surface",
            "source_report_uri": "hlf://reports/symbolic_surface",
            "source_explainer_uri": "hlf://explainer/symbolic_surface",
            "source_status": symbolic_payload.get("status"),
            "operator_summary": (
                symbolic_payload.get("operator_summary")
                or symbolic_surface.get("operator_summary")
                or "Symbolic surface reading packet is available."
            ),
        },
        {
            "surface_id": "hks_evaluation",
            "title": "HKS Evaluation Reading",
            "order": 4,
            "focus": "Read how local HKS evaluation decides promotion eligibility, authority lane, and local recheck requirements.",
            "resource_uri": "hlf://teach/native_comprehension/hks_evaluation",
            "source_status_uri": "hlf://status/hks_evaluation",
            "source_report_uri": "hlf://reports/hks_evaluation",
            "source_explainer_uri": None,
            "source_status": hks_evaluation_payload.get("status"),
            "operator_summary": (
                hks_evaluation_payload.get("operator_summary")
                or hks_evaluation_surface.get("operator_summary")
                or "HKS evaluation reading packet is available."
            ),
            "quality_posture": {
                "explicit_local_evaluation_count": hks_evaluation_surface.get(
                    "explicit_local_evaluation_count", 0
                ),
                "promotion_eligible_count": hks_evaluation_surface.get(
                    "promotion_eligible_count", 0
                ),
                "requires_local_recheck_count": hks_evaluation_surface.get(
                    "requires_local_recheck_count", 0
                ),
                "raw_intake_count": hks_evaluation_surface.get("raw_intake_count", 0),
                "canonical_knowledge_count": hks_evaluation_surface.get(
                    "canonical_knowledge_count", 0
                ),
                "canonical_source_count": hks_evaluation_surface.get(
                    "canonical_source_count", 0
                ),
                "advisory_source_count": hks_evaluation_surface.get(
                    "advisory_source_count", 0
                ),
                "average_extraction_fidelity_score": hks_evaluation_surface.get(
                    "average_extraction_fidelity_score"
                ),
            },
        },
        {
            "surface_id": "hks_external_compare",
            "title": "HKS External Compare Reading",
            "order": 5,
            "focus": "Read how external comparator output remains quarantined as bridge-lane advisory evidence pending local HKS re-evaluation.",
            "resource_uri": "hlf://teach/native_comprehension/hks_external_compare",
            "source_status_uri": "hlf://status/hks_external_compare",
            "source_report_uri": "hlf://reports/hks_external_compare",
            "source_explainer_uri": None,
            "source_status": hks_external_compare_payload.get("status"),
            "operator_summary": (
                hks_external_compare_payload.get("operator_summary")
                or hks_external_compare_surface.get("operator_summary")
                or "HKS external comparator reading packet is available."
            ),
        },
    ]

    return {
        "status": "ok",
        "claim_lane": "bridge-true",
        "operator_summary": (
            "Native comprehension mode is a layered reading interface over existing governed outputs; "
            "it does not replace executable authority or introduce a second explanation engine."
        ),
        "native_comprehension": {
            "surface_type": "native_comprehension_index",
            "resource_uri": "hlf://teach/native_comprehension",
            "surface_count": len(entries),
            "entries": entries,
            "next_step": "Open one surface-specific reading packet and follow its source status/report URIs in parallel.",
        },
    }


def _build_native_comprehension_packet(
    ctx: object | None,
    *,
    surface_id: str,
) -> dict[str, object]:
    if surface_id == "translation_contract":
        payload = json.loads(_render_translation_contract_status(ctx))
        surface = (
            payload.get("translation_contract_surface")
            if isinstance(payload.get("translation_contract_surface"), dict)
            else {}
        )
        contract = payload.get("translation_contract") if isinstance(payload.get("translation_contract"), dict) else {}
        proof = contract.get("proof") if isinstance(contract.get("proof"), dict) else {}
        compile_proof = proof.get("compile") if isinstance(proof.get("compile"), dict) else {}
        math_proof = proof.get("math") if isinstance(proof.get("math"), dict) else {}
        audit_surfaces = proof.get("audit_surfaces") if isinstance(proof.get("audit_surfaces"), dict) else {}
        canonical_hlf = contract.get("canonical_hlf") if isinstance(contract.get("canonical_hlf"), dict) else {}
        artifacts = contract.get("artifacts") if isinstance(contract.get("artifacts"), dict) else {}
        memory_contract = contract.get("memory") if isinstance(contract.get("memory"), dict) else {}
        return {
            "status": payload.get("status", "not_found"),
            "claim_lane": "bridge-true",
            "surface_id": surface_id,
            "title": "Translation Contract Reading Packet",
            "operator_summary": payload.get("operator_summary") or "Read the persisted translation contract as a governed meaning chain.",
            "source_surface": {
                "status_uri": "hlf://status/translation_contract",
                "report_uri": "hlf://reports/translation_contract",
                "explainer_uri": None,
            },
            "surface_snapshot": {
                "contract_id": surface.get("contract_id"),
                "intent_language": surface.get("intent_language"),
                "tier": surface.get("tier"),
                "governed": surface.get("governed"),
                "statement_count": surface.get("statement_count"),
                "ast_sha256": surface.get("ast_sha256"),
                "memory_backed": surface.get("has_memory_backing"),
                "primary_target": artifacts.get("primary_target"),
                "runtime": artifacts.get("runtime"),
            },
            "reading_layers": [
                {
                    "layer_id": "what_you_are_looking_at",
                    "title": "What You Are Looking At",
                    "focus": "Treat this as a governed contract chain, not as a loose translation result.",
                    "observations": [
                        f"Intent language: {surface.get('intent_language')}",
                        f"Tier: {surface.get('tier')}",
                        f"Governed: {surface.get('governed')}",
                        f"Statement count: {surface.get('statement_count')}",
                    ],
                },
                {
                    "layer_id": "meaning_chain",
                    "title": "Meaning Chain",
                    "focus": "Read the chain in order: intent, canonical HLF, compile proof, then audit summaries.",
                    "observations": [
                        f"Canonical source begins with: {str(canonical_hlf.get('source') or '').splitlines()[0] if str(canonical_hlf.get('source') or '').splitlines() else ''}",
                        f"AST SHA256: {surface.get('ast_sha256')}",
                        f"Gas estimate: {compile_proof.get('gas_estimate', 0)}",
                        f"Compression pct: {math_proof.get('compression_pct', 0.0)}",
                    ],
                },
                {
                    "layer_id": "proof_and_audit",
                    "title": "Proof And Audit",
                    "focus": "Use the audit summaries as operator-readable proof surfaces, not as alternate executable authority.",
                    "observations": [
                        f"English summary: {audit_surfaces.get('english_summary', '')}",
                        f"Bytecode summary: {audit_surfaces.get('bytecode_summary_en', '')}",
                        f"Memory backing present: {bool(memory_contract.get('sha256'))}",
                        f"Primary target: {artifacts.get('primary_target')}",
                    ],
                },
            ],
            "authority_boundary": {
                "canonical_hlf": "canonical-executable",
                "compile_and_bytecode_artifacts": "derived-proof",
                "audit_summaries": "operator-readable",
                "this_reading_packet": "display-only",
            },
            "evidence_refs": payload.get("evidence_refs", []),
            "starter_vocabulary": [
                "intent_language",
                "canonical_hlf",
                "ast_sha256",
                "governed",
                "memory_backing",
                "bytecode_summary",
            ],
            "operator_questions": [
                "What changed between the natural-language intent and the canonical HLF source?",
                "What governance evidence proves this is more than an unstructured translation?",
                "Which proof objects are executable authority versus operator-readable audit?",
            ],
            "next_resources": [
                "hlf://status/translation_contract",
                "hlf://reports/translation_contract",
                "hlf://teach/native_comprehension/governed_recall",
            ],
        }

    if surface_id == "governed_recall":
        payload = json.loads(_render_governed_recall_status(ctx))
        surface = (
            payload.get("governed_recall_surface")
            if isinstance(payload.get("governed_recall_surface"), dict)
            else {}
        )
        recall = payload.get("governed_recall") if isinstance(payload.get("governed_recall"), dict) else {}
        weekly_sync = recall.get("weekly_sync") if isinstance(recall.get("weekly_sync"), dict) else {}
        recall_summary = (
            recall.get("recall_summary") if isinstance(recall.get("recall_summary"), dict) else {}
        )
        results = recall.get("results") if isinstance(recall.get("results"), list) else []
        top_result = results[0] if results and isinstance(results[0], dict) else {}
        top_evidence = top_result.get("evidence") if isinstance(top_result.get("evidence"), dict) else {}
        return {
            "status": payload.get("status", "not_found"),
            "claim_lane": "bridge-true",
            "surface_id": surface_id,
            "title": "Governed Recall Reading Packet",
            "operator_summary": payload.get("operator_summary") or "Read the latest governed recall chain as HKS-backed evidence retrieval.",
            "source_surface": {
                "status_uri": "hlf://status/governed_recall",
                "report_uri": "hlf://reports/governed_recall",
                "explainer_uri": None,
            },
            "surface_snapshot": {
                "recall_id": surface.get("recall_id"),
                "recall_kind": surface.get("recall_kind"),
                "query": surface.get("query"),
                "result_count": surface.get("result_count"),
                "active_result_count": surface.get("active_result_count"),
                "archived_result_count": surface.get("archived_result_count"),
                "archive_visibility": surface.get("archive_visibility"),
                "graph_linked_result_count": surface.get("graph_linked_result_count"),
                "retrieval_path_counts": surface.get("retrieval_path_counts", {}),
                "path_status": surface.get("path_status", {}),
                "graph_traversal_totals": surface.get("graph_traversal_totals", {}),
                "entry_kinds": surface.get("entry_kinds", []),
                "evidence_backed_count": surface.get("evidence_backed_count"),
                "weekly_sync_count": surface.get("weekly_sync_count"),
            },
            "reading_layers": [
                {
                    "layer_id": "what_you_are_looking_at",
                    "title": "What You Are Looking At",
                    "focus": "Treat this as governed recall over HKS and weekly evidence, not as generic semantic search.",
                    "observations": [
                        f"Recall kind: {surface.get('recall_kind')}",
                        f"Result count: {surface.get('result_count')}",
                        f"Archive visibility: {surface.get('archive_visibility')}",
                        f"Graph-linked result count: {surface.get('graph_linked_result_count')}",
                        f"Entry kinds: {', '.join(surface.get('entry_kinds') or []) or 'none'}",
                        f"Evidence-backed count: {surface.get('evidence_backed_count')}",
                        f"Path status: {json.dumps(surface.get('path_status', {}), sort_keys=True)}",
                    ],
                },
                {
                    "layer_id": "governed_memory_reading",
                    "title": "Governed Memory Reading",
                    "focus": "Read the result set by provenance and governance state before reading it by semantic similarity alone.",
                    "observations": [
                        f"Top result topic: {top_result.get('topic')}",
                        f"Top result domain: {top_result.get('domain')}",
                        f"Top result governance state: {top_evidence.get('state') or top_result.get('governance_status')}",
                        f"Top result provenance grade: {top_evidence.get('provenance_grade')}",
                        f"Admission decisions: {json.dumps(recall_summary.get('admission_decision_counts', {}), sort_keys=True)}",
                        f"Retrieval paths: {json.dumps(recall_summary.get('retrieval_path_counts', {}), sort_keys=True)}",
                        f"Graph traversal totals: {json.dumps(surface.get('graph_traversal_totals', {}), sort_keys=True)}",
                    ],
                },
                {
                    "layer_id": "hks_and_weekly_sync",
                    "title": "HKS And Weekly Sync",
                    "focus": "Use weekly sync metadata to understand what evidence substrate was available when the recall contract was formed.",
                    "observations": [
                        f"Weekly sync status: {weekly_sync.get('status')}",
                        f"Weekly sync artifact count: {weekly_sync.get('count', 0)}",
                        f"Metrics dir: {weekly_sync.get('metrics_dir')}",
                        "HKS / Infinite RAG here means governed recallable exemplars with provenance, not a generic chat memory bucket.",
                    ],
                },
            ],
            "authority_boundary": {
                "governed_recall_contract": "governed-status",
                "evidence_rows": "retrieval-results-with-provenance",
                "weekly_sync_summary": "operator-readable",
                "this_reading_packet": "display-only",
            },
            "evidence_refs": payload.get("evidence_refs", []),
            "starter_vocabulary": [
                "recall_kind",
                "entry_kind",
                "evidence_backed",
                "weekly_sync",
                "provenance_grade",
                "governance_state",
                "archive_visibility",
                "admission_decision",
                "retrieval_path",
                "path_status",
                "graph_traversal",
                "graph_linked",
            ],
            "operator_questions": [
                "Which results are evidence-backed versus merely adjacent?",
                "What does the weekly sync tell me about the substrate behind this recall?",
                "How should I read HKS and Infinite RAG here without collapsing them into generic search?",
            ],
            "next_resources": [
                "hlf://status/governed_recall",
                "hlf://reports/governed_recall",
                "hlf://teach/native_comprehension/symbolic_surface",
            ],
        }

    if surface_id == "symbolic_surface":
        payload = _build_symbolic_surface_report(ctx)
        surface = (
            payload.get("symbolic_surface") if isinstance(payload.get("symbolic_surface"), dict) else {}
        )
        proof_bundle = surface.get("proof_bundle") if isinstance(surface.get("proof_bundle"), dict) else {}
        provenance_status = (
            surface.get("provenance_status") if isinstance(surface.get("provenance_status"), dict) else {}
        )
        authority_boundary = (
            surface.get("authority_boundary") if isinstance(surface.get("authority_boundary"), dict) else {}
        )
        explainer = json.loads(_render_symbolic_surface_explainer(ctx))
        explainer_card = explainer.get("explainer_card") if isinstance(explainer.get("explainer_card"), dict) else {}
        return {
            "status": payload.get("status", "not_found"),
            "claim_lane": payload.get("claim_lane", "bridge-true"),
            "surface_id": surface_id,
            "title": "Symbolic Surface Reading Packet",
            "operator_summary": payload.get("operator_summary") or "Read the symbolic bridge as inspectable proof with display-only projection.",
            "source_surface": {
                "status_uri": "hlf://status/symbolic_surface",
                "report_uri": "hlf://reports/symbolic_surface",
                "explainer_uri": "hlf://explainer/symbolic_surface",
            },
            "surface_snapshot": {
                "surface_mode": surface.get("surface_mode"),
                "relation_count": proof_bundle.get("relation_count", 0),
                "relation_family_counts": surface.get("relation_family_counts", {}),
                "source_mode": provenance_status.get("mode"),
                "explainer_mode": explainer_card.get("surface_mode"),
            },
            "reading_layers": [
                {
                    "layer_id": "what_you_are_looking_at",
                    "title": "What You Are Looking At",
                    "focus": "Treat this as inspectable symbolic proof, not as executable symbolic runtime semantics.",
                    "observations": [
                        f"Surface mode: {surface.get('surface_mode')}",
                        f"Relation count: {proof_bundle.get('relation_count', 0)}",
                        f"Source mode: {provenance_status.get('mode')}",
                        f"Explainer mode: {explainer_card.get('surface_mode')}",
                    ],
                },
                {
                    "layer_id": "authority_boundary",
                    "title": "Authority Boundary",
                    "focus": "Use the authority boundary to distinguish executable canonical source from display-only projection.",
                    "observations": [
                        f"Canonical source: {authority_boundary.get('canonical_source')}",
                        f"Unicode projection: {authority_boundary.get('unicode_projection')}",
                        f"Report rendering: {authority_boundary.get('report_rendering')}",
                        f"Explainer card: {authority_boundary.get('explainer_card')}",
                    ],
                },
                {
                    "layer_id": "starter_vocabulary",
                    "title": "Starter Vocabulary",
                    "focus": "Start by learning the packaged relation vocabulary, then inspect relation artifacts and provenance notes.",
                    "observations": [
                        f"Starter vocabulary: {', '.join(surface.get('starter_vocabulary') or [])}",
                        f"Relation families: {surface.get('relation_family_counts', {})}",
                        f"Provenance note: {provenance_status.get('note')}",
                        "Display-only explainer entries help reading, but they do not carry executable authority.",
                    ],
                },
            ],
            "authority_boundary": authority_boundary,
            "evidence_refs": payload.get("evidence_refs", []),
            "starter_vocabulary": surface.get("starter_vocabulary", []),
            "operator_questions": [
                "Which parts of this surface are canonical versus display-only?",
                "What relation families dominate this proof bundle and why?",
                "Is the current bundle runtime-generated or still the packaged proof sample?",
            ],
            "next_resources": [
                "hlf://status/symbolic_surface",
                "hlf://reports/symbolic_surface",
                "hlf://explainer/symbolic_surface",
            ],
        }

    if surface_id == "hks_evaluation":
        payload = json.loads(_render_hks_evaluation_status(ctx))
        surface = (
            payload.get("hks_evaluation_surface")
            if isinstance(payload.get("hks_evaluation_surface"), dict)
            else {}
        )
        evaluation = payload.get("hks_evaluation") if isinstance(payload.get("hks_evaluation"), dict) else {}
        return {
            "status": payload.get("status", "not_found"),
            "claim_lane": "bridge-true",
            "surface_id": surface_id,
            "title": "HKS Evaluation Reading Packet",
            "operator_summary": payload.get("operator_summary") or "Read the latest persisted HKS evaluation chain as the local admission authority surface.",
            "source_surface": {
                "status_uri": "hlf://status/hks_evaluation",
                "report_uri": "hlf://reports/hks_evaluation",
                "explainer_uri": None,
            },
            "surface_snapshot": {
                "evaluation_id": surface.get("evaluation_id"),
                "source_kind": surface.get("source_kind"),
                "source_ref": surface.get("source_ref"),
                "result_count": surface.get("result_count"),
                "explicit_local_evaluation_count": surface.get("explicit_local_evaluation_count"),
                "promotion_eligible_count": surface.get("promotion_eligible_count"),
                "requires_local_recheck_count": surface.get("requires_local_recheck_count"),
                "raw_intake_count": surface.get("raw_intake_count"),
                "canonical_knowledge_count": surface.get("canonical_knowledge_count"),
                "canonical_source_count": surface.get("canonical_source_count"),
                "advisory_source_count": surface.get("advisory_source_count"),
                "average_extraction_fidelity_score": surface.get(
                    "average_extraction_fidelity_score"
                ),
            },
            "reading_layers": [
                {
                    "layer_id": "evaluation_summary",
                    "title": "Evaluation Summary",
                    "focus": "Start with the chain summary and counts to see how many results remained locally promotable.",
                    "observations": [
                        f"Source kind: {surface.get('source_kind')}",
                        f"Result count: {surface.get('result_count')}",
                        f"Explicit local evaluation count: {surface.get('explicit_local_evaluation_count')}",
                        f"Promotion eligible count: {surface.get('promotion_eligible_count')}",
                        f"Requires local recheck count: {surface.get('requires_local_recheck_count')}",
                        f"Raw intake count: {surface.get('raw_intake_count')}",
                        f"Canonical knowledge count: {surface.get('canonical_knowledge_count')}",
                        f"Canonical source count: {surface.get('canonical_source_count')}",
                        f"Advisory source count: {surface.get('advisory_source_count')}",
                        f"Average extraction fidelity score: {surface.get('average_extraction_fidelity_score')}",
                    ],
                },
                {
                    "layer_id": "authority_and_promotion",
                    "title": "Authority And Promotion",
                    "focus": "Then inspect authority, promotion eligibility, and local-recheck flags on each result row.",
                    "observations": [
                        "Local HKS evaluation is the packaged admission authority for promotion decisions.",
                        "Bridge-lane annotations do not upgrade admission truth by themselves.",
                    ],
                },
                {
                    "layer_id": "bridge_lane_guard",
                    "title": "Bridge Lane Guard",
                    "focus": "Treat any external-comparator count as a quarantine indicator, not as upgraded admission truth.",
                    "observations": [
                        f"External comparator count: {surface.get('external_comparator_count')}",
                        "Requires-local-recheck flags mark results that cannot promote directly.",
                    ],
                },
            ],
            "authority_boundary": {
                "local_hks_evaluation": "canonical-admission-authority",
                "result_rows": "evidence-backed-decision-inputs",
                "bridge_lane_annotations": "advisory-only-until-local-recheck",
                "this_reading_packet": "display-only",
            },
            "evidence_refs": _dedupe_evidence_refs(payload.get("evidence_refs"), evaluation.get("evidence_refs")),
            "starter_vocabulary": [
                "authority",
                "explicit_local_evaluation_present",
                "promotion_eligible",
                "promotion_blocked",
                "requires_local_recheck",
                "lane",
            ],
            "operator_questions": [
                "Which result rows remain locally promotable?",
                "Which rows are blocked because they still require local recheck?",
                "Where does bridge-lane advisory evidence stop and local authority begin?",
            ],
            "next_resources": [
                "hlf://status/hks_evaluation",
                "hlf://reports/hks_evaluation",
            ],
        }

    if surface_id == "hks_external_compare":
        payload = json.loads(_render_hks_external_compare_status(ctx))
        surface = (
            payload.get("hks_external_compare_surface")
            if isinstance(payload.get("hks_external_compare_surface"), dict)
            else {}
        )
        compare = payload.get("hks_external_compare") if isinstance(payload.get("hks_external_compare"), dict) else {}
        adapter_metadata = compare.get("adapter_metadata") if isinstance(compare.get("adapter_metadata"), dict) else {}
        return {
            "status": payload.get("status", "not_found"),
            "claim_lane": "bridge-true",
            "surface_id": surface_id,
            "title": "HKS External Compare Reading Packet",
            "operator_summary": payload.get("operator_summary") or "Read the quarantined external comparator contract without promoting it into admission authority.",
            "source_surface": {
                "status_uri": "hlf://status/hks_external_compare",
                "report_uri": "hlf://reports/hks_external_compare",
                "explainer_uri": None,
            },
            "surface_snapshot": {
                "compare_id": surface.get("compare_id"),
                "query": surface.get("query"),
                "comparator_name": surface.get("comparator_name"),
                "local_result_count": surface.get("local_result_count"),
                "comparator_result_count": surface.get("comparator_result_count"),
                "adapter_status": adapter_metadata.get("status") or "provided_results",
            },
            "reading_layers": [
                {
                    "layer_id": "local_vs_external_split",
                    "title": "Local Versus External Split",
                    "focus": "Read the local recall side and comparator side separately; they do not share admission authority.",
                    "observations": [
                        f"Local result count: {surface.get('local_result_count')}",
                        f"Comparator result count: {surface.get('comparator_result_count')}",
                    ],
                },
                {
                    "layer_id": "quarantine_contract",
                    "title": "Quarantine Contract",
                    "focus": "Confirm that bridge-lane comparator results are blocked from promotion and still require local HKS recheck.",
                    "observations": [
                        "External comparator output is advisory-only.",
                        "Local HKS remains the only admission authority.",
                    ],
                },
                {
                    "layer_id": "adapter_posture",
                    "title": "Adapter Posture",
                    "focus": "Use adapter metadata only to understand fetch posture or comparator availability, not to reinterpret trust state.",
                    "observations": [
                        f"Adapter status: {adapter_metadata.get('status') or 'provided_results'}",
                        f"Adapter note: {adapter_metadata.get('message') or 'No adapter warning recorded.'}",
                    ],
                },
            ],
            "authority_boundary": {
                "local_hks_recall": "canonical-recall-authority",
                "external_comparator_results": "bridge-lane-advisory-only",
                "local_recheck_requirement": "mandatory-before-any-promotion",
                "this_reading_packet": "display-only",
            },
            "evidence_refs": _dedupe_evidence_refs(payload.get("evidence_refs"), compare.get("evidence_refs")),
            "starter_vocabulary": [
                "bridge",
                "external_comparator",
                "requires_local_recheck",
                "admission_authority",
                "adapter_metadata",
            ],
            "operator_questions": [
                "What came from local HKS versus the external comparator?",
                "Why is the comparator output still blocked from promotion?",
                "What did the adapter actually do before this advisory contract was persisted?",
            ],
            "next_resources": [
                "hlf://status/hks_external_compare",
                "hlf://reports/hks_external_compare",
                "hlf://status/hks_evaluation",
            ],
        }

    return {
        "status": "error",
        "error": "unknown_native_comprehension_surface",
        "surface_id": surface_id,
    }


def _render_native_comprehension_index(ctx: object | None) -> str:
    return json.dumps(_build_native_comprehension_index(ctx), indent=2)


def _render_native_comprehension_packet(
    ctx: object | None,
    *,
    surface_id: str,
) -> str:
    return json.dumps(_build_native_comprehension_packet(ctx, surface_id=surface_id), indent=2)


def _build_agent_protocol_surface(ctx: object | None) -> dict[str, object]:
    operator_surfaces_report = _build_operator_surfaces_report(ctx)
    operator_surfaces = (
        operator_surfaces_report.get("operator_surfaces")
        if isinstance(operator_surfaces_report.get("operator_surfaces"), dict)
        else {}
    )
    governed_route_report = json.loads(_render_governed_route_status(ctx))
    route_trace = (
        governed_route_report.get("route_trace")
        if isinstance(governed_route_report.get("route_trace"), dict)
        else {}
    )
    instinct_report = json.loads(_render_instinct_status(ctx))
    instinct_status = (
        instinct_report.get("instinct_status")
        if isinstance(instinct_report.get("instinct_status"), dict)
        else {}
    )
    witness_report = json.loads(_render_witness_status(ctx))
    witness_status = (
        witness_report.get("witness_status")
        if isinstance(witness_report.get("witness_status"), dict)
        else {}
    )
    memory_report = json.loads(_render_memory_governance_status(ctx))
    memory_governance = (
        memory_report.get("memory_governance")
        if isinstance(memory_report.get("memory_governance"), dict)
        else {}
    )
    evidence_refs = _dedupe_evidence_refs(
        operator_surfaces_report.get("evidence_refs"),
        governed_route_report.get("evidence_refs"),
        instinct_report.get("evidence_refs"),
        witness_report.get("evidence_refs"),
        memory_report.get("evidence_refs"),
    )

    return {
        "status": "ok",
        "operator_summary": (
            "HLF is exposed here as a governed meaning-and-handoff protocol for agents, not just as a tool list. "
            "Use the protocol contract, authority surface, and packaged coordination resources together."
        ),
        "protocol_identity": {
            "name": "HLF",
            "surface_type": "agent_protocol_frontdoor",
            "claim_lane": "bridge-true",
            "summary": (
                "A deterministic meaning layer that lets one agent emit governed HLF intent and another agent, "
                "tool surface, or runtime consume the same contract without collapsing into unstructured prose."
            ),
        },
        "what_hlf_is_not": [
            "not a marketing wrapper over generic tool calling",
            "not a second explanation authority that overrides canonical HLF artifacts",
            "not a claim that full upstream multi-agent completion is already packaged in this checkout",
        ],
        "agent_to_agent_contract": {
            "canonical_unit": "governed HLF source plus derived AST and bytecode proof",
            "handoff_rule": (
                "The producer emits canonical HLF or an equivalent governed translation contract; the consumer reads the same "
                "canonical unit instead of relying on conversational paraphrase."
            ),
            "semantic_drift_control": [
                "deterministic grammar and compile path",
                "capsule-tier validation and admission boundaries",
                "inspectable status and report surfaces for audit follow-through",
            ],
        },
        "agent_to_tool_contract": {
            "summary": (
                "Agents do not reach tools as a flat capability bag. They route through governed HLF meaning, tier constraints, "
                "and ingress or approval surfaces when applicable."
            ),
            "packaged_entrypoints": [
                "hlf_do",
                "hlf_translate_to_hlf",
                "hlf_translate_resilient",
                "hlf://status/governed_route",
                "hlf://status/ingress",
            ],
        },
        "capsule_tiers": [
            {
                "tier": "hearth",
                "permissions": "minimal permissions, no tools or host calls, gas=100",
                "authority_role": "safe baseline for bounded meaning work",
            },
            {
                "tier": "forge",
                "permissions": "moderate permissions, read/write/http allowed, gas=500",
                "authority_role": "default practical working tier for governed tool participation",
            },
            {
                "tier": "sovereign",
                "permissions": "full permissions, all tools, gas=1000",
                "authority_role": "highest packaged authority tier; promotion-sensitive and not assumed by default",
            },
        ],
        "coordination_surfaces": [
            {
                "resource_uri": "hlf://status/governed_route",
                "summary": governed_route_report.get("operator_summary")
                or route_trace.get("operator_summary")
                or "Latest governed route trace is available.",
            },
            {
                "resource_uri": "hlf://status/instinct",
                "summary": instinct_report.get("operator_summary")
                or f"Tracks {instinct_status.get('mission_count', 0)} packaged Instinct mission(s).",
            },
            {
                "resource_uri": "hlf://status/operator_surfaces",
                "summary": operator_surfaces_report.get("operator_summary")
                or f"Indexes {operator_surfaces.get('surface_count', 0)} packaged operator surface(s).",
            },
        ],
        "memory_surfaces": [
            {
                "resource_uri": "hlf://status/witness_governance",
                "summary": witness_report.get("operator_summary")
                or f"Tracks {witness_status.get('subject_count', 0)} witness-governed subject(s).",
            },
            {
                "resource_uri": "hlf://status/memory_governance",
                "summary": memory_report.get("operator_summary")
                or f"Tracks {len(memory_governance.get('recent_interventions') or [])} recent memory interventions.",
            },
            {
                "resource_uri": "hlf://status/governed_recall",
                "summary": "Use governed recall for evidence-backed retrieval rather than generic semantic search.",
            },
        ],
        "model_lane_compatibility": {
            "summary": (
                "The packaged meaning layer is model-class agnostic at the contract level: local, cloud-via-Ollama, and remote-direct "
                "lanes can participate so long as they emit or consume the same governed HLF contract surfaces."
            ),
            "lanes": [
                "local models",
                "cloud-via-Ollama bridges",
                "remote-direct endpoints",
            ],
        },
        "source_refs": [
            "hlf://status/operator_surfaces",
            "hlf://status/governed_route",
            "hlf://status/instinct",
            "hlf://status/witness_governance",
            "hlf://status/memory_governance",
        ],
        "next_actions": [
            "Read hlf://agent/current_authority before assuming forge or sovereign capabilities.",
            "Use hlf://agent/quickstart for the minimum arriving-agent working loop.",
            "Use hlf://agent/handoff_contract before treating prose as a sufficient inter-agent payload.",
        ],
        "evidence_refs": evidence_refs,
    }


def _build_agent_current_authority_surface(ctx: object | None) -> dict[str, object]:
    ingress_report = json.loads(_render_ingress_status(ctx))
    ingress_status = (
        ingress_report.get("ingress_status")
        if isinstance(ingress_report.get("ingress_status"), dict)
        else {}
    )
    witness_report = json.loads(_render_witness_status(ctx))
    approval_report = json.loads(_render_approval_review_status(ctx))
    approval_bypass_report = json.loads(_render_approval_bypass_status(ctx))
    evidence_refs = _dedupe_evidence_refs(
        ingress_report.get("evidence_refs"),
        witness_report.get("evidence_refs"),
        approval_report.get("evidence_refs"),
        approval_bypass_report.get("evidence_refs"),
    )

    return {
        "status": "ok",
        "operator_summary": (
            "Current packaged authority is bounded by capsule tier, ingress posture, and approval or witness governance surfaces. "
            "Assume forge-level work only when a surface explicitly allows it."
        ),
        "capsule_tier_model": {
            "default_working_tier": "forge",
            "tiers": [
                {
                    "tier": "hearth",
                    "permissions": "minimal permissions, no tools or host calls, gas=100",
                    "promotion_posture": "does not imply tool access",
                },
                {
                    "tier": "forge",
                    "permissions": "moderate permissions, read/write/http allowed, gas=500",
                    "promotion_posture": "default packaged working tier, but still subject to ingress and approval checks",
                },
                {
                    "tier": "sovereign",
                    "permissions": "full permissions, all tools, gas=1000",
                    "promotion_posture": "promotion-sensitive; do not assume without explicit authority and passing governance",
                },
            ],
        },
        "allowed_categories": [
            "bounded HLF translation and compilation",
            "structured status and report reads",
            "governed routing, witness, memory, and provenance inspection",
        ],
        "bounded_actions": [
            "translate intent into governed HLF",
            "read packaged status and report resources",
            "inspect coordination and memory posture before attempting escalation",
        ],
        "requires_operator_promotion": [
            "tier escalation beyond the active capsule boundary",
            "forged-tool approvals and other approval-gated actions",
            "claims of sovereign authority not backed by packaged surfaces",
        ],
        "governance_surfaces": [
            {
                "resource_uri": "hlf://status/ingress",
                "summary": ingress_report.get("operator_summary") or summarize_ingress_status(ingress_status),
            },
            {
                "resource_uri": "hlf://status/approval_queue",
                "summary": approval_report.get("operator_summary") or "Review approval requests before assuming elevated execution rights.",
            },
            {
                "resource_uri": "hlf://status/approval_bypass",
                "summary": approval_bypass_report.get("operator_summary") or "Approval-bypass monitoring is packaged and should be treated as a live denial surface.",
            },
            {
                "resource_uri": "hlf://status/witness_governance",
                "summary": witness_report.get("operator_summary") or "Witness governance tracks subject trust posture that may constrain escalation or delegation.",
            },
        ],
        "recommended_safe_next_steps": [
            "Open hlf://agent/quickstart and follow the first-call sequence.",
            "Check hlf://status/ingress before attempting side-effecting execution.",
            "Treat approval and witness surfaces as authority boundaries, not optional observability.",
        ],
        "evidence_refs": evidence_refs,
    }


def _build_agent_quickstart_surface(ctx: object | None) -> dict[str, object]:
    current_authority = _build_agent_current_authority_surface(ctx)
    operator_surfaces_report = _build_operator_surfaces_report(ctx)
    evidence_refs = _dedupe_evidence_refs(
        current_authority.get("evidence_refs"),
        operator_surfaces_report.get("evidence_refs"),
    )

    return {
        "status": "ok",
        "operator_summary": (
            "This is the minimum deterministic loop for an arriving agent: establish authority, translate intent into HLF, "
            "inspect coordination and memory posture, then hand off canonical units instead of prose."
        ),
        "current_authority_model": {
            "resource_uri": "hlf://agent/current_authority",
            "summary": current_authority.get("operator_summary"),
            "default_working_tier": "forge",
        },
        "first_calls": [
            {
                "kind": "resource",
                "target": "hlf://agent/current_authority",
                "why": "Establish actual packaged authority before doing anything more ambitious.",
            },
            {
                "kind": "tool",
                "target": "hlf_do",
                "why": "Use the packaged natural-language front door to produce governed HLF without inventing your own translation path.",
            },
            {
                "kind": "resource",
                "target": "hlf://status/ingress",
                "why": "Check admission posture before assuming an execution or side-effect lane is open.",
            },
            {
                "kind": "resource",
                "target": "hlf://status/operator_surfaces",
                "why": "Discover packaged status and report surfaces that already exist rather than improvising repo archaeology.",
            },
        ],
        "recommended_resources": [
            "hlf://agent/protocol",
            "hlf://agent/current_authority",
            "hlf://agent/handoff_contract",
            "hlf://status/operator_surfaces",
            "hlf://status/governed_route",
            "hlf://status/governed_recall",
        ],
        "hll_to_hlf_entrypoints": [
            "hlf_do",
            "hlf_translate_to_hlf",
            "hlf_translate_resilient",
        ],
        "handoff_pattern": {
            "producer": "emit governed HLF or a translation contract",
            "consumer": "read canonical HLF, AST fingerprint, and packaged proof surfaces",
            "rule": "Do not treat a conversational paraphrase as the authoritative handoff artifact.",
        },
        "memory_pattern": {
            "summary": "Read witness, recall, and memory-governance surfaces before assuming reusable context is trustworthy or promotable.",
            "resources": [
                "hlf://status/witness_governance",
                "hlf://status/governed_recall",
                "hlf://status/memory_governance",
            ],
        },
        "coordination_pattern": {
            "summary": "Use governed route and Instinct surfaces to understand routing and lifecycle posture instead of inventing ad hoc delegation semantics.",
            "resources": [
                "hlf://status/governed_route",
                "hlf://status/instinct",
            ],
        },
        "do_not_assume": [
            "do not assume sovereign authority because a tool name exists",
            "do not assume upstream orchestration completion is fully packaged here",
            "do not assume free-form prose is an adequate inter-agent contract",
        ],
        "evidence_refs": evidence_refs,
    }


def _build_agent_handoff_contract_surface(ctx: object | None) -> dict[str, object]:
    protocol_surface = _build_agent_protocol_surface(ctx)
    authority_surface = _build_agent_current_authority_surface(ctx)
    evidence_refs = _dedupe_evidence_refs(
        protocol_surface.get("evidence_refs"),
        authority_surface.get("evidence_refs"),
    )

    return {
        "status": "ok",
        "operator_summary": (
            "The bounded packaged handoff story is: a producer emits canonical HLF or a governed translation contract, "
            "and the consumer validates the same canonical unit through compile, capsule, and status surfaces before acting."
        ),
        "canonical_units": [
            "canonical HLF source",
            "derived AST with fingerprint",
            "bytecode-backed proof and audit surfaces",
            "capsule and admission context when execution authority matters",
        ],
        "producer_roles": [
            "human-to-HLF translator via hlf_do or hlf_translate_to_hlf",
            "agent emitting governed HLF for another agent or runtime",
        ],
        "consumer_roles": [
            "agent reading a governed handoff contract",
            "runtime or tool layer validating capsule and ingress posture",
            "operator reviewing proof or approval surfaces",
        ],
        "required_authority_checks": [
            "validate capsule tier before execution",
            "consult ingress posture for admission and review state",
            "respect approval and witness surfaces when escalation or trust is in question",
        ],
        "example_handoff_sequence": [
            "Producer calls hlf_do or hlf_translate_to_hlf to emit a governed HLF contract.",
            "Consumer reads canonical HLF and derived proof surfaces rather than a prose paraphrase.",
            "Consumer checks capsule tier and hlf://status/ingress before side-effecting execution.",
            "If escalation or approval is required, operator-facing review surfaces remain in the loop.",
        ],
        "semantic_drift_controls": [
            "deterministic compile path",
            "AST and proof fingerprints",
            "capsule validation",
            "ingress and governance review surfaces",
        ],
        "bridge_gaps": [
            "full upstream multi-agent orchestration remains larger than this packaged handoff slice",
            "the surface proves bounded packaged handoff semantics, not total ecosystem completion",
        ],
        "source_refs": [
            "hlf://agent/protocol",
            "hlf://agent/current_authority",
            "hlf://status/translation_contract",
            "hlf://status/ingress",
            "hlf://status/approval_queue",
        ],
        "evidence_refs": evidence_refs,
    }


def _render_agent_protocol(ctx: object | None) -> str:
    return json.dumps(_build_agent_protocol_surface(ctx), indent=2)


def _render_agent_quickstart(ctx: object | None) -> str:
    return json.dumps(_build_agent_quickstart_surface(ctx), indent=2)


def _render_agent_handoff_contract(ctx: object | None) -> str:
    return json.dumps(_build_agent_handoff_contract_surface(ctx), indent=2)


def _render_agent_current_authority(ctx: object | None) -> str:
    return json.dumps(_build_agent_current_authority_surface(ctx), indent=2)


def _render_internal_workflow_status(
    ctx: object | None,
    *,
    workflow_id: str | None = None,
) -> str:
    if ctx is None or not hasattr(ctx, "get_internal_workflow"):
        return json.dumps({"status": "error", "error": "internal_workflow_unavailable"}, indent=2)
    workflow = ctx.get_internal_workflow(workflow_id=workflow_id)
    if not isinstance(workflow, dict):
        return json.dumps({"status": "not_found", "workflow_id": workflow_id}, indent=2)
    before = workflow.get("before") if isinstance(workflow.get("before"), dict) else {}
    after = workflow.get("after") if isinstance(workflow.get("after"), dict) else {}
    capture = before.get("capture") if isinstance(before.get("capture"), dict) else {}
    recall = after.get("recall") if isinstance(after.get("recall"), dict) else {}
    resolution = after.get("resolution") if isinstance(after.get("resolution"), dict) else {}
    evidence_refs = _dedupe_evidence_refs(
        workflow.get("evidence_refs"),
        workflow.get("governance_event_ref"),
        workflow.get("governance_event", {}).get("event_ref") if isinstance(workflow.get("governance_event"), dict) else None,
    )
    surface = {
        "surface_type": "internal_workflow_contract",
        "resource_uri": f"hlf://status/internal_workflow/{workflow.get('workflow_id')}",
        "report_uri": f"hlf://reports/internal_workflow/{workflow.get('workflow_id')}",
        "workflow_id": workflow.get("workflow_id"),
        "workflow_kind": workflow.get("workflow_kind"),
        "query": workflow.get("query"),
        "domain": workflow.get("domain"),
        "solution_kind": workflow.get("solution_kind"),
        "capture_fact_id": capture.get("fact_id"),
        "recall_id": recall.get("recall_id"),
        "result_count": recall.get("result_count"),
        "resolved_pointer": resolution.get("pointer") if isinstance(resolution, dict) else None,
        "operator_summary": workflow.get("operator_summary"),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": workflow.get("operator_summary")
            or "Latest internal workflow contract is available.",
            "evidence_refs": evidence_refs,
            "internal_workflow_surface": surface,
            "internal_workflow": workflow,
        },
        indent=2,
    )


def _render_internal_workflow_markdown(
    ctx: object | None,
    *,
    workflow_id: str | None = None,
) -> str:
    payload = json.loads(_render_internal_workflow_status(ctx, workflow_id=workflow_id))
    if payload.get("status") != "ok":
        return "# HLF Internal Workflow Report\n\nNo internal workflow contract is currently available.\n"
    surface = (
        payload.get("internal_workflow_surface")
        if isinstance(payload.get("internal_workflow_surface"), dict)
        else {}
    )
    workflow = payload.get("internal_workflow") if isinstance(payload.get("internal_workflow"), dict) else {}
    before = workflow.get("before") if isinstance(workflow.get("before"), dict) else {}
    after = workflow.get("after") if isinstance(workflow.get("after"), dict) else {}
    capture = before.get("capture") if isinstance(before.get("capture"), dict) else {}
    recall = after.get("recall") if isinstance(after.get("recall"), dict) else {}
    resolution = after.get("resolution") if isinstance(after.get("resolution"), dict) else {}
    top_result = recall.get("top_result") if isinstance(recall.get("top_result"), dict) else {}
    lines = [
        "# HLF Internal Workflow Report",
        "",
        "Generated from the latest persisted bounded internal workflow contract without introducing a second workflow authority layer.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Workflow ID: {surface.get('workflow_id')}",
        f"- Workflow kind: {surface.get('workflow_kind')}",
        f"- Query: {surface.get('query')}",
        f"- Domain: {surface.get('domain')}",
        f"- Solution kind: {surface.get('solution_kind')}",
        f"- Capture fact id: {surface.get('capture_fact_id')}",
        f"- Recall id: {surface.get('recall_id')}",
        f"- Result count: {surface.get('result_count')}",
        f"- Queryable resource: {surface.get('resource_uri')}",
        f"- Companion report: {surface.get('report_uri')}",
        "",
        "## Capture",
        "",
        f"- Stored: {capture.get('stored')}",
        f"- SHA256: {capture.get('sha256')}",
        f"- Pointer: {capture.get('pointer')}",
        f"- Audit trace id: {capture.get('audit_trace_id')}",
        "",
        "## Recall",
        "",
        f"- Entry kinds: {', '.join(recall.get('entry_kinds') or []) or 'none'}",
        f"- Evidence-backed count: {recall.get('evidence_backed_count')}",
        f"- Top result topic: {top_result.get('topic')}",
        f"- Top result pointer: {top_result.get('pointer')}",
        f"- Top result sha256: {top_result.get('sha256')}",
        "",
        "## Resolution",
        "",
        f"- Resolution status: {resolution.get('status') if isinstance(resolution, dict) else None}",
        f"- Resolved pointer: {resolution.get('pointer') if isinstance(resolution, dict) else None}",
        f"- Trust status: {(resolution.get('pointer_status') or {}).get('status') if isinstance(resolution, dict) and isinstance(resolution.get('pointer_status'), dict) else None}",
    ]
    return "\n".join(lines).strip() + "\n"


def _render_formal_verifier_markdown(ctx: object | None) -> str:
    payload = json.loads(_render_formal_verifier_status(ctx))
    if payload.get("status") != "ok":
        return "# HLF Formal Verifier Report\n\nFormal verifier status is unavailable.\n"
    status = payload.get("formal_verifier_status") if isinstance(payload.get("formal_verifier_status"), dict) else {}
    justification = payload.get("justification_surface") if isinstance(payload.get("justification_surface"), dict) else {}
    knowledge_posture = payload.get("knowledge_posture") if isinstance(payload.get("knowledge_posture"), dict) else {}
    lines = [
        "# HLF Formal Verifier Report",
        "",
        "Generated from the packaged formal verifier status surface so justification stays consumable outside JSON status reads.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Solver: {status.get('solver_name')}",
        f"- Latest verdict: {justification.get('latest_verdict')}",
        f"- Review-required count: {justification.get('review_required_count', 0)}",
        f"- Blocked count: {justification.get('blocked_count', 0)}",
        f"- Primary reason: {justification.get('primary_reason')}",
    ]
    if knowledge_posture:
        lines.extend(
            [
                "",
                "## Knowledge Posture",
                "",
                f"- Latest recall id: {knowledge_posture.get('recall_id')}",
                f"- Archive visibility: {knowledge_posture.get('archive_visibility')}",
                f"- Retrieval paths: {json.dumps(knowledge_posture.get('retrieval_path_counts', {}), sort_keys=True)}",
                f"- Graph-linked result count: {knowledge_posture.get('graph_linked_result_count')}",
            ]
        )
    lines.extend(
        [
            "",
            "## Recent Verification Events",
            "",
            "| Verdict | Policy Posture | Failed | Unknown | Skipped | Review Required | Primary Reason |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in payload.get("recent_verifications", [])[:10]:
        if not isinstance(item, dict):
            continue
        item_justification = item.get("justification") if isinstance(item.get("justification"), dict) else {}
        lines.append(
            "| {verdict} | {policy_posture} | {failed_count} | {unknown_count} | {skipped_count} | {review_required} | {primary_reason} |".format(
                verdict=str(item.get("admission_verdict") or item.get("result_status") or "-").replace("|", "/"),
                policy_posture=str(item.get("policy_posture") or "-").replace("|", "/"),
                failed_count=item.get("failed_count", 0),
                unknown_count=item.get("unknown_count", 0),
                skipped_count=item.get("skipped_count", 0),
                review_required=str(bool(item.get("operator_review_required", False))).lower(),
                primary_reason=str(item_justification.get("primary_reason") or "-").replace("|", "/"),
            )
        )
    return "\n".join(lines).strip() + "\n"


def _render_governed_route_markdown(
    ctx: object | None,
    *,
    agent_id: str | None = None,
) -> str:
    payload = json.loads(_render_governed_route_status(ctx, agent_id=agent_id))
    if payload.get("status") != "ok":
        return "# HLF Governed Route Report\n\nGoverned route status is unavailable.\n"
    route_trace = payload.get("route_trace") if isinstance(payload.get("route_trace"), dict) else {}
    route_decision = route_trace.get("route_decision") if isinstance(route_trace.get("route_decision"), dict) else {}
    justification = payload.get("justification_surface") if isinstance(payload.get("justification_surface"), dict) else {}
    knowledge_posture = payload.get("knowledge_posture") if isinstance(payload.get("knowledge_posture"), dict) else {}
    lines = [
        "# HLF Governed Route Report",
        "",
        "Generated from the packaged governed route status surface so routing justifications remain readable outside JSON status reads.",
        "",
        f"- Status: {payload.get('status')}",
        f"- Summary: {payload.get('operator_summary')}",
        f"- Agent ID: {(route_trace.get('request_context') or {}).get('agent_id') if isinstance(route_trace.get('request_context'), dict) else agent_id}",
        f"- Decision: {route_decision.get('decision')}",
        f"- Governance mode: {route_decision.get('governance_mode')}",
        f"- Selected lane: {route_decision.get('selected_lane')}",
        f"- Review required: {route_decision.get('review_required')}",
        f"- Primary reason: {justification.get('primary_reason')}",
        "",
        "## Constraints",
        "",
    ]
    for item in justification.get("policy_constraints", []) or []:
        lines.append(f"- {item}")
    rationale = justification.get("rationale", []) or []
    if rationale:
        lines.extend(["", "## Rationale", ""])
        for item in rationale:
            lines.append(f"- {item}")
    if knowledge_posture:
        lines.extend(
            [
                "",
                "## Knowledge Posture",
                "",
                f"- Latest recall id: {knowledge_posture.get('recall_id')}",
                f"- Archive visibility: {knowledge_posture.get('archive_visibility')}",
                f"- Retrieval paths: {json.dumps(knowledge_posture.get('retrieval_path_counts', {}), sort_keys=True)}",
                f"- Graph-linked result count: {knowledge_posture.get('graph_linked_result_count')}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _build_operator_surfaces_report(ctx: object | None) -> dict[str, object]:
    translation_contract_report = json.loads(_render_translation_contract_status(ctx))
    translation_contract_surface = (
        translation_contract_report.get("translation_contract_surface")
        if isinstance(translation_contract_report.get("translation_contract_surface"), dict)
        else {}
    )

    governed_recall_report = json.loads(_render_governed_recall_status(ctx))
    governed_recall_surface = (
        governed_recall_report.get("governed_recall_surface")
        if isinstance(governed_recall_report.get("governed_recall_surface"), dict)
        else {}
    )

    symbolic_report = _build_symbolic_surface_report(ctx)
    symbolic_surface = (
        symbolic_report.get("symbolic_surface")
        if isinstance(symbolic_report.get("symbolic_surface"), dict)
        else {}
    )
    symbolic_provenance = (
        symbolic_surface.get("provenance_status")
        if isinstance(symbolic_surface.get("provenance_status"), dict)
        else {}
    )
    symbolic_relation_count = (
        symbolic_surface.get("proof_bundle", {}).get("relation_count", 0)
        if isinstance(symbolic_surface.get("proof_bundle"), dict)
        else 0
    )

    fixture_gallery_report = _build_fixture_gallery_report(ctx)
    fixture_gallery = (
        fixture_gallery_report.get("gallery")
        if isinstance(fixture_gallery_report.get("gallery"), dict)
        else {}
    )
    fixture_summary = (
        fixture_gallery.get("summary") if isinstance(fixture_gallery.get("summary"), dict) else {}
    )

    daemon_transparency_report = _build_daemon_transparency_report(ctx)
    daemon_transparency = (
        daemon_transparency_report.get("daemon_transparency")
        if isinstance(daemon_transparency_report.get("daemon_transparency"), dict)
        else {}
    )

    formal_verifier_report = json.loads(_render_formal_verifier_status(ctx))
    formal_verifier_status = (
        formal_verifier_report.get("formal_verifier_status")
        if isinstance(formal_verifier_report.get("formal_verifier_status"), dict)
        else {}
    )

    governed_route_report = json.loads(_render_governed_route_status(ctx))
    route_trace = (
        governed_route_report.get("route_trace")
        if isinstance(governed_route_report.get("route_trace"), dict)
        else {}
    )

    ingress_report = json.loads(_render_ingress_status(ctx))
    ingress_status = (
        ingress_report.get("ingress_status")
        if isinstance(ingress_report.get("ingress_status"), dict)
        else {}
    )

    memory_governance_report = json.loads(_render_memory_governance_status(ctx))
    memory_governance = (
        memory_governance_report.get("memory_governance")
        if isinstance(memory_governance_report.get("memory_governance"), dict)
        else {}
    )

    approval_queue_report = json.loads(_render_approval_review_status(ctx))
    approval_queue = (
        approval_queue_report.get("approval_queue")
        if isinstance(approval_queue_report.get("approval_queue"), dict)
        else {}
    )

    approval_bypass_report = json.loads(_render_approval_bypass_status(ctx))
    approval_bypass = (
        approval_bypass_report.get("approval_bypass_status")
        if isinstance(approval_bypass_report.get("approval_bypass_status"), dict)
        else {}
    )

    witness_governance_report = json.loads(_render_witness_status(ctx))
    witness_governance = (
        witness_governance_report.get("witness_status")
        if isinstance(witness_governance_report.get("witness_status"), dict)
        else {}
    )

    hks_evaluation_report = json.loads(_render_hks_evaluation_status(ctx))
    hks_evaluation_surface = (
        hks_evaluation_report.get("hks_evaluation_surface")
        if isinstance(hks_evaluation_report.get("hks_evaluation_surface"), dict)
        else {}
    )

    hks_external_compare_report = json.loads(_render_hks_external_compare_status(ctx))
    hks_external_compare_surface = (
        hks_external_compare_report.get("hks_external_compare_surface")
        if isinstance(hks_external_compare_report.get("hks_external_compare_surface"), dict)
        else {}
    )

    entries = [
        {
            "surface_id": "translation_contract",
            "title": "Translation Contract",
            "surface_kind": "translation_contract_chain",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": translation_contract_report.get("status"),
            "status_uri": "hlf://status/translation_contract",
            "report_uri": "hlf://reports/translation_contract",
            "explainer_uri": None,
            "summary": (
                translation_contract_report.get("operator_summary")
                or translation_contract_surface.get("operator_summary")
                or "Latest translation contract chain is available through the packaged operator surface."
            ),
        },
        {
            "surface_id": "governed_recall",
            "title": "Governed Recall",
            "surface_kind": "governed_recall_chain",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": governed_recall_report.get("status"),
            "status_uri": "hlf://status/governed_recall",
            "report_uri": "hlf://reports/governed_recall",
            "explainer_uri": None,
            "summary": (
                governed_recall_report.get("operator_summary")
                or governed_recall_surface.get("operator_summary")
                or "Latest governed recall contract is available through the packaged recall surface."
            ),
        },
        {
            "surface_id": "symbolic_surface",
            "title": "Symbolic Surface",
            "surface_kind": "symbolic_bridge",
            "display_mode": "structured-status+markdown-report+explainer-card",
            "runtime_backed": symbolic_provenance.get("mode") == "runtime-generated-bundle",
            "status": symbolic_report.get("status"),
            "status_uri": "hlf://status/symbolic_surface",
            "report_uri": "hlf://reports/symbolic_surface",
            "explainer_uri": "hlf://explainer/symbolic_surface",
            "summary": (
                symbolic_report.get("operator_summary")
                or f"Tracks {symbolic_relation_count} symbolic relation artifact(s) in {symbolic_provenance.get('mode', 'unknown')} mode."
            ),
        },
        {
            "surface_id": "fixture_gallery",
            "title": "Fixture Gallery",
            "surface_kind": "generated_fixture_gallery",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": fixture_gallery_report.get("status"),
            "status_uri": "hlf://status/fixture_gallery",
            "report_uri": "hlf://reports/fixture_gallery",
            "explainer_uri": None,
            "summary": (
                f"Tracks {fixture_summary.get('fixture_count', 0)} packaged fixture(s) with "
                f"{fixture_summary.get('compile_ok_count', 0)} AST compile success(es) and "
                f"{fixture_summary.get('bytecode_ok_count', 0)} bytecode success(es)."
            ),
        },
        {
            "surface_id": "daemon_transparency",
            "title": "Daemon Transparency",
            "surface_kind": "governance_transparency",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": daemon_transparency_report.get("status"),
            "status_uri": "hlf://status/daemon_transparency",
            "report_uri": "hlf://reports/daemon_transparency",
            "explainer_uri": None,
            "summary": (
                daemon_transparency_report.get("operator_summary")
                or f"Tracks {daemon_transparency.get('entry_count', 0)} daemon-transparency audit entrie(s)."
            ),
        },
        {
            "surface_id": "formal_verifier",
            "title": "Formal Verifier",
            "surface_kind": "formal_verification",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": formal_verifier_report.get("status"),
            "status_uri": "hlf://status/formal_verifier",
            "report_uri": "hlf://reports/formal_verifier",
            "explainer_uri": None,
            "summary": (
                formal_verifier_report.get("operator_summary")
                or f"Solver {formal_verifier_status.get('solver_name', 'unknown-solver')} is exposed through the packaged verifier status surface."
            ),
        },
        {
            "surface_id": "governed_route",
            "title": "Governed Route",
            "surface_kind": "routing_trace",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": governed_route_report.get("status"),
            "status_uri": "hlf://status/governed_route",
            "report_uri": "hlf://reports/governed_route",
            "explainer_uri": None,
            "summary": (
                governed_route_report.get("operator_summary")
                or route_trace.get("operator_summary")
                or "Latest governed route trace is available through the packaged routing status surface."
            ),
        },
        {
            "surface_id": "ingress",
            "title": "Ingress Status",
            "surface_kind": "governed_ingress",
            "display_mode": "structured-status",
            "runtime_backed": True,
            "status": ingress_report.get("status"),
            "status_uri": "hlf://status/ingress",
            "report_uri": None,
            "explainer_uri": None,
            "summary": (
                ingress_report.get("operator_summary")
                or summarize_ingress_status(ingress_status)
            ),
        },
        {
            "surface_id": "memory_governance",
            "title": "Memory Governance",
            "surface_kind": "memory_governance",
            "display_mode": "structured-status",
            "runtime_backed": True,
            "status": memory_governance_report.get("status"),
            "status_uri": "hlf://status/memory_governance",
            "report_uri": None,
            "explainer_uri": None,
            "summary": (
                memory_governance_report.get("operator_summary")
                or f"Tracks {len(memory_governance.get('recent_interventions') or [])} recent memory-governance intervention(s)."
            ),
        },
        {
            "surface_id": "approval_queue",
            "title": "Approval Queue",
            "surface_kind": "approval_review",
            "display_mode": "structured-status",
            "runtime_backed": True,
            "status": approval_queue_report.get("status"),
            "status_uri": "hlf://status/approval_queue",
            "report_uri": None,
            "explainer_uri": None,
            "summary": (
                approval_queue_report.get("operator_summary")
                or f"Tracks {approval_queue.get('count', 0)} approval request(s) in the packaged review queue."
            ),
        },
        {
            "surface_id": "approval_bypass",
            "title": "Approval Bypass",
            "surface_kind": "approval_bypass_monitor",
            "display_mode": "structured-status",
            "runtime_backed": True,
            "status": approval_bypass_report.get("status"),
            "status_uri": "hlf://status/approval_bypass",
            "report_uri": None,
            "explainer_uri": None,
            "summary": (
                approval_bypass_report.get("operator_summary")
                or f"Tracks {approval_bypass.get('recent_attempt_count', 0)} recent approval-bypass attempt(s)."
            ),
        },
        {
            "surface_id": "witness_governance",
            "title": "Witness Governance",
            "surface_kind": "witness_governance",
            "display_mode": "structured-status",
            "runtime_backed": True,
            "status": witness_governance_report.get("status"),
            "status_uri": "hlf://status/witness_governance",
            "report_uri": None,
            "explainer_uri": None,
            "summary": (
                witness_governance_report.get("operator_summary")
                or f"Tracks {witness_governance.get('subject_count', 0)} witness-governed subject(s)."
            ),
        },
        {
            "surface_id": "hks_evaluation",
            "title": "HKS Evaluation",
            "surface_kind": "hks_evaluation_chain",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": hks_evaluation_report.get("status"),
            "status_uri": "hlf://status/hks_evaluation",
            "report_uri": "hlf://reports/hks_evaluation",
            "explainer_uri": None,
            "summary": (
                hks_evaluation_report.get("operator_summary")
                or hks_evaluation_surface.get("operator_summary")
                or "Latest HKS evaluation chain is available through the packaged local-evaluation surface."
            ),
            "explicit_local_evaluation_count": hks_evaluation_surface.get(
                "explicit_local_evaluation_count", 0
            ),
            "promotion_eligible_count": hks_evaluation_surface.get(
                "promotion_eligible_count", 0
            ),
            "requires_local_recheck_count": hks_evaluation_surface.get(
                "requires_local_recheck_count", 0
            ),
            "raw_intake_count": hks_evaluation_surface.get("raw_intake_count", 0),
            "canonical_knowledge_count": hks_evaluation_surface.get("canonical_knowledge_count", 0),
            "canonical_source_count": hks_evaluation_surface.get("canonical_source_count", 0),
            "advisory_source_count": hks_evaluation_surface.get("advisory_source_count", 0),
            "average_extraction_fidelity_score": hks_evaluation_surface.get(
                "average_extraction_fidelity_score"
            ),
        },
        {
            "surface_id": "hks_external_compare",
            "title": "HKS External Compare",
            "surface_kind": "hks_external_compare_contract",
            "display_mode": "structured-status+markdown-report",
            "runtime_backed": True,
            "status": hks_external_compare_report.get("status"),
            "status_uri": "hlf://status/hks_external_compare",
            "report_uri": "hlf://reports/hks_external_compare",
            "explainer_uri": None,
            "summary": (
                hks_external_compare_report.get("operator_summary")
                or hks_external_compare_surface.get("operator_summary")
                or "Latest quarantined HKS external compare contract is available through the packaged advisory surface."
            ),
        },
    ]

    evidence_refs = _dedupe_evidence_refs(
        translation_contract_report.get("evidence_refs"),
        governed_recall_report.get("evidence_refs"),
        symbolic_report.get("evidence_refs"),
        fixture_gallery_report.get("evidence_refs"),
        daemon_transparency_report.get("evidence_refs"),
        formal_verifier_report.get("evidence_refs"),
        governed_route_report.get("evidence_refs"),
        ingress_report.get("evidence_refs"),
        memory_governance_report.get("evidence_refs"),
        approval_queue_report.get("evidence_refs"),
        approval_bypass_report.get("evidence_refs"),
        witness_governance_report.get("evidence_refs"),
        hks_evaluation_report.get("evidence_refs"),
        hks_external_compare_report.get("evidence_refs"),
    )
    report_count = sum(1 for entry in entries if entry.get("report_uri"))
    explainer_count = sum(1 for entry in entries if entry.get("explainer_uri"))
    runtime_backed_count = sum(1 for entry in entries if entry.get("runtime_backed") is True)
    operator_summary = (
        f"Operator-surface discovery currently indexes {len(entries)} packaged surface(s), with "
        f"{runtime_backed_count} live-backed surface(s), {report_count} companion report surface(s), and "
        f"{explainer_count} explainer surface(s)."
    )

    return {
        "status": "ok",
        "operator_summary": operator_summary,
        "evidence_refs": evidence_refs,
        "operator_surfaces": {
            "surface_type": "operator_surface_index",
            "report_uri": "hlf://reports/operator_surfaces",
            "surface_count": len(entries),
            "runtime_backed_count": runtime_backed_count,
            "report_count": report_count,
            "explainer_count": explainer_count,
            "hks_quality_posture": {
                "explicit_local_evaluation_count": hks_evaluation_surface.get(
                    "explicit_local_evaluation_count", 0
                ),
                "promotion_eligible_count": hks_evaluation_surface.get(
                    "promotion_eligible_count", 0
                ),
                "requires_local_recheck_count": hks_evaluation_surface.get(
                    "requires_local_recheck_count", 0
                ),
                "raw_intake_count": hks_evaluation_surface.get("raw_intake_count", 0),
                "canonical_knowledge_count": hks_evaluation_surface.get("canonical_knowledge_count", 0),
                "canonical_source_count": hks_evaluation_surface.get("canonical_source_count", 0),
                "advisory_source_count": hks_evaluation_surface.get("advisory_source_count", 0),
                "average_extraction_fidelity_score": hks_evaluation_surface.get(
                    "average_extraction_fidelity_score"
                ),
            },
            "entries": entries,
        },
    }


def _render_operator_surfaces_status(ctx: object | None) -> str:
    return json.dumps(_build_operator_surfaces_report(ctx), indent=2)


def _render_operator_surfaces_markdown(ctx: object | None) -> str:
    report = _build_operator_surfaces_report(ctx)
    operator_surfaces = (
        report.get("operator_surfaces") if isinstance(report.get("operator_surfaces"), dict) else {}
    )
    lines = [
        "# HLF Operator Surfaces Report",
        "",
        "Generated from the currently packaged operator-facing MCP resources without introducing a new authority layer.",
        "",
        f"- Status: {report.get('status')}",
        f"- Summary: {report.get('operator_summary')}",
        f"- Surface count: {operator_surfaces.get('surface_count', 0)}",
        f"- Runtime-backed count: {operator_surfaces.get('runtime_backed_count', 0)}",
        f"- Companion report count: {operator_surfaces.get('report_count', 0)}",
        f"- Explainer count: {operator_surfaces.get('explainer_count', 0)}",
        f"- HKS explicit local evaluation count: {(operator_surfaces.get('hks_quality_posture') or {}).get('explicit_local_evaluation_count', 0)}",
        f"- HKS promotion eligible count: {(operator_surfaces.get('hks_quality_posture') or {}).get('promotion_eligible_count', 0)}",
        f"- HKS requires local recheck count: {(operator_surfaces.get('hks_quality_posture') or {}).get('requires_local_recheck_count', 0)}",
        f"- HKS raw intake count: {(operator_surfaces.get('hks_quality_posture') or {}).get('raw_intake_count', 0)}",
        f"- HKS canonical knowledge count: {(operator_surfaces.get('hks_quality_posture') or {}).get('canonical_knowledge_count', 0)}",
        f"- HKS canonical source count: {(operator_surfaces.get('hks_quality_posture') or {}).get('canonical_source_count', 0)}",
        f"- HKS advisory source count: {(operator_surfaces.get('hks_quality_posture') or {}).get('advisory_source_count', 0)}",
        f"- HKS average extraction fidelity score: {(operator_surfaces.get('hks_quality_posture') or {}).get('average_extraction_fidelity_score')}",
        "",
        "| Surface | Kind | Display Mode | Runtime Backed | Status URI | Report URI | Explainer URI |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for entry in operator_surfaces.get("entries", []):
        if not isinstance(entry, dict):
            continue
        lines.append(
            "| {title} | {surface_kind} | {display_mode} | {runtime_backed} | {status_uri} | {report_uri} | {explainer_uri} |".format(
                title=str(entry.get("title") or "unknown").replace("|", "/"),
                surface_kind=str(entry.get("surface_kind") or "unknown").replace("|", "/"),
                display_mode=str(entry.get("display_mode") or "unknown").replace("|", "/"),
                runtime_backed=str(entry.get("runtime_backed") is True).lower(),
                status_uri=str(entry.get("status_uri") or "-").replace("|", "/"),
                report_uri=str(entry.get("report_uri") or "-").replace("|", "/"),
                explainer_uri=str(entry.get("explainer_uri") or "-").replace("|", "/"),
            )
        )
        lines.append(
            f"| {str(entry.get('title') or 'unknown').replace('|', '/')} summary | {str(entry.get('summary') or '').replace('|', '/')} | - | - | - | - | - |"
        )

    return "\n".join(lines) + "\n"


def _render_model_catalog_status(ctx: object | None, *, agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_model_catalog_status"):
        return json.dumps(
            {
                "status": "error",
                "error": "server_context_unavailable",
                "agent_id": agent_id,
            },
            indent=2,
        )

    status = ctx.get_model_catalog_status(agent_id=agent_id)
    if status is None:
        return json.dumps(
            {
                "status": "not_found",
                "agent_id": agent_id,
            },
            indent=2,
        )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Model catalog status is available for agent '{status.get('agent_id') or agent_id or 'latest'}'."
            ),
            "evidence_refs": [],
            "catalog_status": status,
        },
        indent=2,
    )


def _render_align_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "align_governor"):
        return json.dumps({"status": "error", "error": "align_governor_unavailable"}, indent=2)
    align_status = ctx.align_governor.status_snapshot()
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"ALIGN governor is active with {align_status.get('loaded_rule_count', 0)} loaded rule(s)."
            ),
            "evidence_refs": [],
            "align_status": align_status,
        },
        indent=2,
    )


def _render_formal_verifier_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "formal_verifier"):
        return json.dumps({"status": "error", "error": "formal_verifier_unavailable"}, indent=2)
    recent_verifications: list[dict[str, object]] = []
    knowledge_posture = _build_latest_recall_knowledge_posture(ctx)
    non_blocking_evidence_summary = {
        "evidence_only_informational_proof_gaps": 0,
        "repeat_pattern_advisory_drift": 0,
    }
    if hasattr(ctx, "recent_governance_events"):
        for event in ctx.recent_governance_events(limit=20, kind="formal_verification"):
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            report = details.get("report") if isinstance(details.get("report"), dict) else {}
            result = details.get("result") if isinstance(details.get("result"), dict) else {}
            admission = details.get("admission") if isinstance(details.get("admission"), dict) else {}
            admission_verdict = str(admission.get("verdict") or "")
            non_blocking_evidence_class = None
            if admission_verdict == "verification_advisory_only":
                non_blocking_evidence_class = "evidence_only_informational_proof_gap"
                non_blocking_evidence_summary["evidence_only_informational_proof_gaps"] += 1
            elif admission_verdict == "verification_admitted_with_skips":
                non_blocking_evidence_class = "repeat_pattern_advisory_drift"
                non_blocking_evidence_summary["repeat_pattern_advisory_drift"] += 1
            recent_verifications.append(
                {
                    "kind": event.get("kind"),
                    "action": event.get("action"),
                    "status": event.get("status"),
                    "severity": event.get("severity"),
                    "source": event.get("source"),
                    "timestamp": event.get("timestamp"),
                    "event_ref": event.get("event_ref"),
                    "audit_trace_id": details.get("audit_trace_id"),
                    "solver_name": details.get("solver_name"),
                    "failed_count": report.get("failed") if "failed" in report else report.get("failed_count"),
                    "unknown_count": report.get("unknown"),
                    "skipped_count": report.get("skipped"),
                    "error_count": report.get("errors"),
                    "result_status": report.get("status") or result.get("status"),
                    "property_name": details.get("property_name"),
                    "admission_verdict": admission_verdict,
                    "operator_review_required": admission.get("requires_operator_review"),
                    "policy_posture": admission.get("policy_posture"),
                    "non_blocking_evidence_class": non_blocking_evidence_class,
                    "justification": details.get("justification") if isinstance(details.get("justification"), dict) else None,
                }
            )
    solver_name = str(ctx.formal_verifier.status_snapshot().get("solver_name") or "unknown-solver")
    latest_result = str(
        recent_verifications[0].get("admission_verdict")
        or recent_verifications[0].get("result_status")
        or ""
    ) if recent_verifications else ""
    non_blocking_summary_text = ""
    if non_blocking_evidence_summary["evidence_only_informational_proof_gaps"] or non_blocking_evidence_summary["repeat_pattern_advisory_drift"]:
        non_blocking_summary_text = (
            " Non-blocking proof signals: "
            f"{non_blocking_evidence_summary['evidence_only_informational_proof_gaps']} evidence-only informational proof gap(s), "
            f"{non_blocking_evidence_summary['repeat_pattern_advisory_drift']} repeat-pattern advisory drift event(s)."
        )
    evidence_refs = _dedupe_evidence_refs(
        [event.get("event_ref") for event in recent_verifications if isinstance(event, dict)],
        knowledge_posture.get("governance_event_ref"),
    )
    review_required_count = sum(
        1 for event in recent_verifications if bool(event.get("operator_review_required", False))
    )
    blocked_count = sum(
        1 for event in recent_verifications if str(event.get("status") or "") == "blocked"
    )
    justification_surface = {
        "latest_verdict": latest_result,
        "review_required_count": review_required_count,
        "blocked_count": blocked_count,
        "policy_postures": sorted(
            {
                str(event.get("policy_posture") or "")
                for event in recent_verifications
                if str(event.get("policy_posture") or "")
            }
        ),
        "primary_reason": (
            (recent_verifications[0].get("justification") or {}).get("primary_reason")
            if recent_verifications and isinstance(recent_verifications[0].get("justification"), dict)
            else ""
        ),
    }
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Formal verifier is using '{solver_name}' with {len(recent_verifications)} recent verification event(s)"
                + (f"; latest result is '{latest_result}'." if latest_result else ".")
                + (
                    f" Review-required verifications={review_required_count}, blocked verifications={blocked_count}."
                    if recent_verifications
                    else ""
                )
                + non_blocking_summary_text
                + (
                    " Latest governed recall posture exposed "
                    f"{knowledge_posture.get('result_count', 0)} result(s) with archive visibility '"
                    f"{knowledge_posture.get('archive_visibility')}' and retrieval paths "
                    f"{', '.join(knowledge_posture.get('active_paths') or []) or 'none'}."
                    if knowledge_posture
                    else ""
                )
            ),
            "evidence_refs": evidence_refs,
            "trust_summary": {
                "solver_name": solver_name,
                "latest_verdict": latest_result,
                "review_required_count": review_required_count,
                "blocked_count": blocked_count,
                "policy_postures": justification_surface["policy_postures"],
                "archive_visibility": knowledge_posture.get("archive_visibility") if knowledge_posture else None,
                "retrieval_paths": knowledge_posture.get("active_paths") if knowledge_posture else [],
            },
            "formal_verifier_status": ctx.formal_verifier.status_snapshot(),
            "justification_surface": justification_surface,
            "non_blocking_evidence_summary": non_blocking_evidence_summary,
            "knowledge_posture": knowledge_posture,
            "recent_verifications": recent_verifications,
        },
        indent=2,
    )


def _render_governed_route_status(ctx: object | None, *, agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_governed_route"):
        return json.dumps(
            {"status": "error", "error": "governed_route_unavailable", "agent_id": agent_id},
            indent=2,
        )
    execution_admission = None
    if hasattr(ctx, "get_execution_admission"):
        execution_admission = ctx.get_execution_admission(agent_id=agent_id)
    route_trace = ctx.get_governed_route(agent_id=agent_id)
    if route_trace is None:
        if not execution_admission:
            return json.dumps({"status": "not_found", "agent_id": agent_id}, indent=2)
        route_trace = {
            "agent_id": agent_id,
            "operator_summary": "No governed route trace is recorded; using persisted execution admission as the operator-facing fallback.",
            "execution_admission": execution_admission,
            "policy_basis": {
                "selected_lane": (execution_admission.get("route_evidence") or {}).get("selected_lane"),
                "decision": (execution_admission.get("route_evidence") or {}).get("decision"),
                "trust_state": (execution_admission.get("route_evidence") or {}).get("effective_trust_state"),
                "fallback_mode": True,
                "reason": "execution_admission_only",
                "related_refs": [
                    execution_admission.get("governance_event", {}).get("event_ref"),
                    execution_admission.get("audit_refs", {}).get("execution_governance_event_ref"),
                ],
            },
        }
    normalized_trace = dict(route_trace)
    if execution_admission and not normalized_trace.get("execution_admission"):
        normalized_trace["execution_admission"] = execution_admission
    policy_basis = normalized_trace.get("policy_basis")
    if not isinstance(policy_basis, dict):
        policy_basis = {}
    route_governance_event = None
    align_governance_event = None
    knowledge_posture = _build_latest_recall_knowledge_posture(ctx)
    if hasattr(ctx, "get_governance_event"):
        route_governance_event = ctx.get_governance_event(
            event_ref=policy_basis.get("route_governance_event_ref")
            or policy_basis.get("governance_event_ref")
        )
        align_governance_event = ctx.get_governance_event(
            event_ref=policy_basis.get("align_governance_event_ref")
        )
    fallback_summary = _summarize_route_fallback(normalized_trace)
    policy_basis_summary = _summarize_route_policy_basis(policy_basis)
    route_decision = (
        normalized_trace.get("route_decision")
        if isinstance(normalized_trace.get("route_decision"), dict)
        else {}
    )
    route_justification = (
        policy_basis.get("route_justification")
        if isinstance(policy_basis.get("route_justification"), dict)
        else {
            "decision": route_decision.get("decision") or policy_basis.get("decision"),
            "selected_lane": route_decision.get("selected_lane") or policy_basis.get("selected_lane"),
            "review_required": route_decision.get("review_required"),
            "rationale": [],
            "policy_constraints": list(policy_basis.get("policy_constraints") or []),
            "primary_reason": "",
        }
    )
    embodied_effect = None
    normalized_execution_admission = normalized_trace.get("execution_admission")
    if isinstance(normalized_execution_admission, dict):
        raw_embodied_effect = normalized_execution_admission.get("embodied_effect")
        if isinstance(raw_embodied_effect, dict) and raw_embodied_effect:
            embodied_effect = raw_embodied_effect
    ingress_status = normalize_ingress_status(
        route_trace=normalized_trace,
        execution_admission=normalized_execution_admission if isinstance(normalized_execution_admission, dict) else execution_admission,
        agent_id=agent_id,
    )
    evidence_refs = _dedupe_evidence_refs(
        route_governance_event.get("event_ref") if isinstance(route_governance_event, dict) else None,
        align_governance_event.get("event_ref") if isinstance(align_governance_event, dict) else None,
        normalized_trace.get("policy_basis", {}).get("related_refs")
        if isinstance(normalized_trace.get("policy_basis"), dict)
        else None,
        normalized_execution_admission.get("governance_event", {}).get("event_ref")
        if isinstance(normalized_execution_admission, dict)
        else None,
        knowledge_posture.get("governance_event_ref"),
    )
    base_summary = str(normalized_trace.get("operator_summary") or "Governed route trace is available.")
    route_trust_summary = ""
    verification_trust_summary = ""
    pointer_trust_summary = ""
    if isinstance(normalized_execution_admission, dict):
        route_evidence = (
            normalized_execution_admission.get("route_evidence")
            if isinstance(normalized_execution_admission.get("route_evidence"), dict)
            else {}
        )
        verification_payload = (
            normalized_execution_admission.get("verification")
            if isinstance(normalized_execution_admission.get("verification"), dict)
            else {}
        )
        pointer_evidence = (
            normalized_execution_admission.get("pointer_evidence")
            if isinstance(normalized_execution_admission.get("pointer_evidence"), dict)
            else {}
        )
        if route_evidence:
            route_trust_summary = (
                f" Route evidence selected lane '{route_evidence.get('selected_lane') or 'unknown'}' "
                f"with decision '{route_evidence.get('decision') or 'unknown'}' and effective trust state "
                f"'{route_evidence.get('effective_trust_state') or 'unknown'}'."
            )
        if verification_payload:
            verification_trust_summary = (
                f" Verifier verdict '{verification_payload.get('verdict') or 'unknown'}' tracks policy posture "
                f"'{verification_payload.get('policy_posture') or 'unknown'}' with "
                f"{verification_payload.get('failed_count', 0)} failed proof(s)."
            )
        if pointer_evidence:
            pointer_trust_summary = (
                f" Pointer trust reports {pointer_evidence.get('validation_count', 0)} validation(s) and "
                f"{pointer_evidence.get('failure_count', 0)} failure(s)."
            )
    embodied_summary = ""
    if embodied_effect:
        embodied_summary = (
            f" Embodied envelope '{embodied_effect.get('function_name') or 'unknown'}' is tracked with safety_class='"
            f"{embodied_effect.get('safety_class') or 'none'}', review_posture='"
            f"{embodied_effect.get('review_posture') or 'none'}', and bounded_spatial_envelope="
            f"{bool(embodied_effect.get('bounded_spatial_envelope', False))}."
        )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"{base_summary} {fallback_summary} {policy_basis_summary['trust_summary']} "
                f"{policy_basis_summary['deployment_summary']} {policy_basis_summary['evidence_summary']}"
                f" {summarize_ingress_status(ingress_status)}"
                f"{route_trust_summary}{verification_trust_summary}{pointer_trust_summary}"
                f"{embodied_summary}"
                + (
                    " Latest governed recall posture exposed "
                    f"{knowledge_posture.get('result_count', 0)} result(s) with retrieval paths "
                    f"{', '.join(knowledge_posture.get('active_paths') or []) or 'none'} and archive visibility '"
                    f"{knowledge_posture.get('archive_visibility')}'."
                    if knowledge_posture
                    else ""
                )
            ),
            "evidence_refs": evidence_refs,
            "trust_summary": {
                "selected_lane": route_evidence.get("selected_lane") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("route_evidence"), dict) else None,
                "route_decision": route_evidence.get("decision") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("route_evidence"), dict) else None,
                "effective_trust_state": route_evidence.get("effective_trust_state") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("route_evidence"), dict) else None,
                "verification_verdict": verification_payload.get("verdict") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("verification"), dict) else None,
                "verification_policy_posture": verification_payload.get("policy_posture") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("verification"), dict) else None,
                "pointer_validation_count": pointer_evidence.get("validation_count") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("pointer_evidence"), dict) else 0,
                "pointer_failure_count": pointer_evidence.get("failure_count") if isinstance(normalized_execution_admission, dict) and isinstance(normalized_execution_admission.get("pointer_evidence"), dict) else 0,
                "ingress_source": ingress_status.get("source"),
                "review_required": route_justification.get("review_required"),
            },
            "fallback_summary": fallback_summary,
            "ingress_status": ingress_status,
            "policy_basis_summary": policy_basis_summary,
            "knowledge_posture": knowledge_posture,
            "justification_surface": route_justification,
            "embodied_effect": embodied_effect,
            "route_trace": normalized_trace,
            "route_governance_event": route_governance_event,
            "align_governance_event": align_governance_event,
            "execution_admission": normalized_trace.get("execution_admission")
            or execution_admission,
        },
        indent=2,
    )


def _render_ingress_status(ctx: object | None, *, agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_governed_route"):
        return json.dumps(
            {"status": "error", "error": "ingress_status_unavailable", "agent_id": agent_id},
            indent=2,
        )
    execution_admission = None
    if hasattr(ctx, "get_execution_admission"):
        execution_admission = ctx.get_execution_admission(agent_id=agent_id)
    route_trace = ctx.get_governed_route(agent_id=agent_id)
    if route_trace is None and not execution_admission:
        return json.dumps({"status": "not_found", "agent_id": agent_id}, indent=2)

    ingress_status = normalize_ingress_status(
        route_trace=route_trace if isinstance(route_trace, dict) else None,
        execution_admission=execution_admission if isinstance(execution_admission, dict) else None,
        agent_id=agent_id,
    )
    route_policy_basis = route_trace.get("policy_basis", {}) if isinstance(route_trace, dict) else {}
    route_governance_event = None
    if isinstance(route_policy_basis, dict) and hasattr(ctx, "get_governance_event"):
        route_governance_event = ctx.get_governance_event(
            event_ref=route_policy_basis.get("route_governance_event_ref")
            or route_policy_basis.get("governance_event_ref")
        )
    evidence_refs = _dedupe_evidence_refs(
        route_governance_event.get("event_ref") if isinstance(route_governance_event, dict) else None,
        route_policy_basis.get("related_refs") if isinstance(route_policy_basis, dict) else None,
        execution_admission.get("governance_event", {}).get("event_ref")
        if isinstance(execution_admission, dict)
        else None,
    )
    operator_summary = summarize_ingress_status(ingress_status)
    if route_trace is None and execution_admission:
        operator_summary += " Using execution admission fallback because no governed route trace is recorded."
    return json.dumps(
        {
            "status": "ok",
            "agent_id": agent_id,
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "ingress_status": ingress_status,
            "route_trace": route_trace,
            "execution_admission": execution_admission,
            "route_governance_event": route_governance_event,
        },
        indent=2,
    )


def _render_instinct_status(ctx: object | None, *, mission_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "instinct_mgr"):
        return json.dumps(
            {"status": "error", "error": "instinct_manager_unavailable", "mission_id": mission_id},
            indent=2,
        )
    if mission_id:
        mission = ctx.instinct_mgr.get_mission(mission_id)
        if mission is None:
            return json.dumps({"status": "not_found", "mission_id": mission_id}, indent=2)
        proof_summary = _instinct_proof_summary(mission)
        evidence_refs = _instinct_evidence_refs(mission)
        return json.dumps(
            {
                "status": "ok",
                "operator_summary": _instinct_operator_summary(mission, proof_summary),
                "evidence_refs": evidence_refs,
                "proof_summary": proof_summary,
                "mission": mission,
            },
            indent=2,
        )
    missions = ctx.instinct_mgr.list_missions()
    mission_summaries = []
    proof_states: dict[str, int] = {}
    for mission_summary in missions:
        full_mission = ctx.instinct_mgr.get_mission(str(mission_summary.get("mission_id") or ""))
        if not isinstance(full_mission, dict):
            mission_summaries.append(dict(mission_summary))
            continue
        proof_summary = _instinct_proof_summary(full_mission)
        proof_state = str(proof_summary.get("proof_state") or "unknown")
        proof_states[proof_state] = proof_states.get(proof_state, 0) + 1
        mission_summaries.append(
            {
                **mission_summary,
                "proof_summary": proof_summary,
                "operator_summary": _instinct_operator_summary(full_mission, proof_summary),
                "evidence_refs": _instinct_evidence_refs(full_mission),
            }
        )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Instinct surface currently tracks {len(mission_summaries)} mission(s); "
                f"proof states: "
                + (
                    ", ".join(
                        f"{state}={count}" for state, count in sorted(proof_states.items())
                    )
                    if proof_states
                    else "none"
                )
                + "."
            ),
            "evidence_refs": _dedupe_reference_dicts(
                [
                    ref
                    for mission in mission_summaries
                    if isinstance(mission, dict)
                    for ref in (mission.get("evidence_refs") or [])
                    if isinstance(ref, dict)
                ]
            ),
            "proof_state_counts": proof_states,
            "missions": mission_summaries,
        },
        indent=2,
    )


def _render_witness_status(ctx: object | None, *, subject_agent_id: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "get_witness_status"):
        return json.dumps(
            {
                "status": "error",
                "error": "witness_governance_unavailable",
                "subject_agent_id": subject_agent_id,
            },
            indent=2,
        )
    status = ctx.get_witness_status(subject_agent_id=subject_agent_id)
    if status is None:
        return json.dumps({"status": "not_found", "subject_agent_id": subject_agent_id}, indent=2)
    persona_summary = _load_persona_review_summary(ctx)
    if subject_agent_id:
        subject = status.get("subject", {}) if isinstance(status, dict) else {}
        recent = status.get("recent_observations", []) if isinstance(status, dict) else []
        trust_state = str(subject.get("trust_state") or "unknown")
        operator_summary = (
            f"Witness governance currently classifies '{subject_agent_id}' as {trust_state} "
            f"based on {len(recent)} recent observations."
        )
        if persona_summary:
            operator_summary += (
                f" Related persona review tracks {persona_summary.get('artifact_count', 0)} weekly artifact(s) "
                f"with {persona_summary.get('pending_gate_count', 0)} pending gate(s)."
            )
        evidence_refs = [
            observation.get("event_ref")
            for observation in recent
            if isinstance(observation, dict) and isinstance(observation.get("event_ref"), dict)
        ]
        if isinstance(subject.get("last_event_ref"), dict):
            evidence_refs.insert(0, subject.get("last_event_ref"))
        return json.dumps(
            {
                "status": "ok",
                "operator_summary": operator_summary,
                "evidence_refs": evidence_refs,
                "persona_review_summary": persona_summary,
                "witness_status": status,
            },
            indent=2,
        )

    summary = status.get("summary", {}) if isinstance(status, dict) else {}
    operator_summary = (
        "Witness governance summary is available with explicit trust-state counts across governed subjects."
    )
    if persona_summary:
        operator_summary += (
            f" Persona review currently tracks {persona_summary.get('artifact_count', 0)} weekly artifact(s) "
            f"with {persona_summary.get('pending_gate_count', 0)} pending gate(s)."
        )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": [],
            "persona_review_summary": persona_summary,
            "witness_status": status,
            "summary_counts": summary,
        },
        indent=2,
    )


def _render_provenance_contract(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "summarize_provenance_contract"):
        return json.dumps(
            {"status": "error", "error": "provenance_contract_unavailable"},
            indent=2,
        )
    contract = ctx.summarize_provenance_contract()
    summary = contract.get("summary", {}) if isinstance(contract, dict) else {}
    persona_summary = contract.get("persona_contract_summary", {}) if isinstance(contract, dict) else {}
    evidence_refs = _dedupe_evidence_refs(
        [
            event.get("event_ref")
            for event in (contract.get("recent_governance_events") or [])
            if isinstance(event, dict)
        ],
        [
            fact.get("event_ref")
            for fact in (contract.get("recent_memory_facts") or [])
            if isinstance(fact, dict)
        ],
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Provenance contract currently tracks {summary.get('memory_fact_count', 0)} memory fact(s), "
                f"{summary.get('governance_event_count', 0)} governance event(s), and "
                f"{summary.get('witness_subject_count', 0)} witness subject(s). "
                f"Memory states include active={summary.get('active_memory_count', 0)}, "
                f"revoked={summary.get('revoked_memory_count', 0)}, "
                f"tombstoned={summary.get('tombstoned_memory_count', 0)}, "
                f"superseded={summary.get('superseded_memory_count', 0)}. "
                f"Weekly persona review tracks {persona_summary.get('artifact_count', 0)} artifact(s) "
                f"with {persona_summary.get('pending_gate_count', 0)} pending gate(s)."
            ),
            "evidence_refs": evidence_refs,
            "trust_summary": {
                "memory_fact_count": summary.get("memory_fact_count", 0),
                "governance_event_count": summary.get("governance_event_count", 0),
                "witness_subject_count": summary.get("witness_subject_count", 0),
                "active_memory_count": summary.get("active_memory_count", 0),
                "revoked_memory_count": summary.get("revoked_memory_count", 0),
                "tombstoned_memory_count": summary.get("tombstoned_memory_count", 0),
                "superseded_memory_count": summary.get("superseded_memory_count", 0),
                "persona_artifact_count": persona_summary.get("artifact_count", 0),
                "pending_gate_count": persona_summary.get("pending_gate_count", 0),
                "superseding_pointer_count": (contract.get("pointer_chain_summary") or {}).get("superseding_pointer_count", 0) if isinstance(contract, dict) else 0,
            },
            "provenance_contract": contract,
        },
        indent=2,
    )


def _load_persona_review_summary(ctx: object | None) -> dict[str, object]:
    if ctx is None or not hasattr(ctx, "summarize_provenance_contract"):
        return {}
    provenance_contract = ctx.summarize_provenance_contract()
    if not isinstance(provenance_contract, dict):
        return {}
    summary = provenance_contract.get("persona_contract_summary")
    if not isinstance(summary, dict):
        return {}
    return summary


def _render_memory_governance_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "summarize_provenance_contract"):
        return json.dumps(
            {"status": "error", "error": "memory_governance_unavailable"},
            indent=2,
        )
    contract = ctx.summarize_provenance_contract()
    recent_interventions: list[dict[str, object]] = []
    if hasattr(ctx, "recent_governance_events"):
        for event in ctx.recent_governance_events(limit=20, kind="memory_governance"):
            details = event.get("details") if isinstance(event.get("details"), dict) else {}
            recent_interventions.append(
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
                    "audit_trace_id": details.get("audit_trace_id"),
                    "state": details.get("state"),
                    "pointer": details.get("pointer"),
                    "sha256": details.get("sha256"),
                    "reason": details.get("reason"),
                    "operator_summary": details.get("operator_summary"),
                    "operator_identity": {
                        "operator_id": details.get("operator_id") or "",
                        "operator_display_name": details.get("operator_display_name") or "",
                        "operator_channel": details.get("operator_channel") or "",
                    },
                }
            )
    memory_governance = {
        "summary": contract.get("summary", {}),
        "memory_state_counts": contract.get("memory_state_counts", {}),
        "recent_targets": contract.get("recent_memory_facts", []),
        "recent_interventions": recent_interventions,
        "pointer_chain_summary": contract.get("pointer_chain_summary", {}),
    }
    state_counts = memory_governance.get("memory_state_counts", {})
    evidence_refs = _dedupe_evidence_refs(
        [event.get("event_ref") for event in recent_interventions if isinstance(event, dict)]
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Memory governance reports {len(recent_interventions)} recent intervention(s); "
                f"revoked={state_counts.get('revoked', 0)}, tombstoned={state_counts.get('tombstoned', 0)}, "
                f"superseded={state_counts.get('superseded', 0)}. "
                f"Pointer chain currently tracks {memory_governance.get('pointer_chain_summary', {}).get('superseding_pointer_count', 0)} superseding pointer link(s)."
            ),
            "evidence_refs": evidence_refs,
            "trust_summary": {
                "recent_intervention_count": len(recent_interventions),
                "revoked_count": state_counts.get("revoked", 0),
                "tombstoned_count": state_counts.get("tombstoned", 0),
                "superseded_count": state_counts.get("superseded", 0),
                "superseding_pointer_count": memory_governance.get("pointer_chain_summary", {}).get("superseding_pointer_count", 0),
            },
            "memory_governance": memory_governance,
        },
        indent=2,
    )


def _render_approval_review_status(
    ctx: object | None,
    *,
    request_id: str | None = None,
    status: str = "pending",
    capsule_id: str | None = None,
    request_limit: int = 20,
    event_limit: int = 20,
) -> str:
    if ctx is None or not hasattr(ctx, "list_approval_requests"):
        return json.dumps({"status": "error", "error": "approval_ledger_unavailable"}, indent=2)
    persona_summary = _load_persona_review_summary(ctx)
    if request_id:
        if not hasattr(ctx, "get_approval_request") or not hasattr(ctx, "list_approval_events"):
            return json.dumps(
                {
                    "status": "error",
                    "error": "approval_history_unavailable",
                    "request_id": request_id,
                },
                indent=2,
            )
        request = ctx.get_approval_request(request_id)
        if request is None:
            return json.dumps({"status": "not_found", "request_id": request_id}, indent=2)
        events = ctx.list_approval_events(request_id, limit=event_limit)
        requirement_count = len(request.get("requirements", [])) if isinstance(request, dict) else 0
        operator_summary = (
            f"Approval request '{request_id}' is currently {request.get('status', 'unknown')} "
            f"with {requirement_count} recorded requirement(s) and {len(events)} transition event(s)."
        )
        if persona_summary:
            operator_summary += (
                f" Shared persona review tracks {persona_summary.get('artifact_count', 0)} weekly artifact(s) "
                f"with {persona_summary.get('pending_gate_count', 0)} pending gate(s)."
            )
        evidence_refs = [
            request.get("latest_event_ref")
            if isinstance(request.get("latest_event_ref"), dict)
            else None,
            *[
                event.get("event_ref")
                for event in events
                if isinstance(event, dict) and isinstance(event.get("event_ref"), dict)
            ],
        ]
        return json.dumps(
            {
                "status": "ok",
                "operator_summary": operator_summary,
                "evidence_refs": [ref for ref in evidence_refs if isinstance(ref, dict)],
                "persona_review_summary": persona_summary,
                "approval_request": request,
                "approval_events": events,
            },
            indent=2,
        )
    normalized_status = str(status or "pending").strip().lower()
    effective_status = (
        normalized_status if normalized_status in {"pending", "approved", "rejected", "all"} else "pending"
    )
    requests = ctx.list_approval_requests(
        status=None if effective_status == "all" else effective_status,
        limit=request_limit,
        capsule_id=capsule_id,
    )
    operator_summary = (
        f"Approval queue currently shows {len(requests)} request(s) for status '{effective_status}'."
    )
    if persona_summary:
        operator_summary += (
            f" Shared persona review tracks {persona_summary.get('artifact_count', 0)} weekly artifact(s) "
            f"with {persona_summary.get('pending_gate_count', 0)} pending gate(s)."
        )
    evidence_refs = [
        request.get("latest_event_ref")
        for request in requests
        if isinstance(request, dict) and isinstance(request.get("latest_event_ref"), dict)
    ]
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "persona_review_summary": persona_summary,
            "approval_queue": {
                "requested_status": effective_status,
                "capsule_id": capsule_id,
                "count": len(requests),
                "requests": requests,
            },
        },
        indent=2,
    )


def _summarize_approval_bypass_event(event: dict[str, object]) -> str:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    domain = str(details.get("domain") or "capsule_approval").strip() or "capsule_approval"
    reason_code = str(details.get("reason_code") or "unknown_reason").strip() or "unknown_reason"
    request_id = str(details.get("request_id") or "").strip()
    capsule_id = str(details.get("capsule_id") or "").strip()
    tool_name = str(details.get("tool_name") or details.get("name") or "").strip()
    operator = str(details.get("operator") or "").strip()

    if domain == "forged_tool_approval":
        target = tool_name or str(event.get("subject_id") or "unknown-tool")
        summary = f"Blocked forged-tool approval bypass attempt for '{target}' with reason '{reason_code}'."
    else:
        target = request_id or capsule_id or str(event.get("subject_id") or "unknown-request")
        summary = f"Blocked capsule approval bypass attempt for '{target}' with reason '{reason_code}'."

    if operator:
        return f"{summary[:-1]} by operator '{operator}'."
    return summary


def _render_approval_bypass_status(
    ctx: object | None,
    *,
    subject_agent_id: str | None = None,
    limit: int = 20,
) -> str:
    if ctx is None or not hasattr(ctx, "recent_governance_events"):
        return json.dumps(
            {
                "status": "error",
                "error": "approval_bypass_unavailable",
                "subject_agent_id": subject_agent_id,
            },
            indent=2,
        )

    recent_events = ctx.recent_governance_events(
        limit=max(1, min(limit * 3, 120)),
        kind="approval_transition",
        subject_id=subject_agent_id,
    )
    bypass_events = [
        event
        for event in recent_events
        if isinstance(event, dict) and str(event.get("action") or "") == "approval_bypass_attempt"
    ][: max(1, min(limit, 50))]

    recent_attempts: list[dict[str, object]] = []
    subject_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}
    for event in bypass_events:
        details = event.get("details") if isinstance(event.get("details"), dict) else {}
        related_refs = event.get("related_refs") if isinstance(event.get("related_refs"), list) else []
        reason_code = str(details.get("reason_code") or "unknown_reason").strip() or "unknown_reason"
        subject_id = str(event.get("subject_id") or "").strip()
        subject_counts[subject_id or "unknown"] = subject_counts.get(subject_id or "unknown", 0) + 1
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
        recent_attempts.append(
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
                "domain": details.get("domain"),
                "reason_code": reason_code,
                "request_id": details.get("request_id"),
                "capsule_id": details.get("capsule_id"),
                "tool_name": details.get("tool_name") or details.get("name"),
                "operator": details.get("operator"),
                "decision": details.get("decision"),
                "related_refs": related_refs,
                "operator_summary": _summarize_approval_bypass_event(event),
            }
        )

    subject_status = None
    if subject_agent_id and hasattr(ctx, "get_witness_status"):
        subject_status = ctx.get_witness_status(subject_agent_id=subject_agent_id)

    evidence_refs = _dedupe_evidence_refs(
        [attempt.get("event_ref") for attempt in recent_attempts if isinstance(attempt, dict)],
        [
            ref
            for attempt in recent_attempts
            if isinstance(attempt, dict)
            for ref in (attempt.get("related_refs") or [])
            if isinstance(ref, dict)
        ],
        (
            (subject_status or {}).get("subject", {}).get("last_event_ref")
            if isinstance(subject_status, dict)
            else None
        ),
    )

    if subject_agent_id:
        trust_state = "unknown"
        if isinstance(subject_status, dict):
            subject = subject_status.get("subject") if isinstance(subject_status.get("subject"), dict) else {}
            trust_state = str(subject.get("trust_state") or "unknown")
        operator_summary = (
            f"Approval-bypass surface shows {len(recent_attempts)} recent blocked bypass attempt(s) "
            f"for '{subject_agent_id}' with current trust state '{trust_state}'."
        )
        return json.dumps(
            {
                "status": "ok",
                "operator_summary": operator_summary,
                "evidence_refs": evidence_refs,
                "approval_bypass_status": {
                    "subject_agent_id": subject_agent_id,
                    "recent_attempt_count": len(recent_attempts),
                    "reason_counts": reason_counts,
                    "recent_attempts": recent_attempts,
                    "witness_status": subject_status,
                },
            },
            indent=2,
        )

    operator_summary = (
        f"Approval-bypass surface currently tracks {len(recent_attempts)} recent blocked attempt(s) across "
        f"{len(subject_counts)} governed subject(s)."
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "approval_bypass_status": {
                "recent_attempt_count": len(recent_attempts),
                "subject_count": len(subject_counts),
                "subject_counts": subject_counts,
                "reason_counts": reason_counts,
                "recent_attempts": recent_attempts,
            },
        },
        indent=2,
    )


def _render_dream_cycle_status(ctx: object | None) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_cycle_status"):
        return json.dumps(
            {"status": "error", "error": "dream_cycle_unavailable"},
            indent=2,
        )
    status = ctx.get_dream_cycle_status()
    latest_cycle = status.get("latest_cycle", {}) if isinstance(status, dict) else {}
    evidence_refs = _dedupe_evidence_refs(
        latest_cycle.get("governance_event", {}).get("event_ref")
        if isinstance(latest_cycle, dict)
        else None
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": (
                f"Dream cycle surface currently tracks {status.get('total_cycles', 0)} cycle(s), "
                f"{status.get('total_findings', 0)} finding(s), and {status.get('total_proposals', 0)} proposal(s)."
            ),
            "evidence_refs": evidence_refs,
            "dream_cycle_status": status,
        },
        indent=2,
    )


def _persona_review_evidence_ref(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "weekly_artifact",
        "artifact_id": artifact.get("artifact_id"),
        "source": artifact.get("source"),
        "generated_at": artifact.get("generated_at"),
    }


def _render_persona_review_status(
    ctx: object | None,
    *,
    artifact_id: str | None = None,
    limit: int = 10,
) -> str:
    del ctx
    if artifact_id:
        artifact = find_weekly_artifact(artifact_id)
        if artifact is None:
            return json.dumps({"status": "not_found", "artifact_id": artifact_id}, indent=2)

        summary = build_persona_review_summary([artifact], include_artifacts=True, artifact_limit=1)
        artifact_payloads = summary.get("recent_artifacts") or []
        artifact_payload = artifact_payloads[0] if artifact_payloads else {}
        operator_summary = (
            f"Persona review contract for artifact '{artifact_id}' is owned by "
            f"'{artifact_payload.get('owner_persona') or 'unknown'}' and tracks "
            f"{len(artifact_payload.get('required_gates') or [])} required gate(s), "
            f"{summary.get('pending_gate_count', 0)} of which remain pending."
        )
        return json.dumps(
            {
                "status": "ok",
                "operator_summary": operator_summary,
                "evidence_refs": [_persona_review_evidence_ref(artifact_payload)],
                "persona_review": {
                    "artifact": artifact_payload,
                    "gate_status_counts": summary.get("gate_status_counts") or {},
                    "pending_gate_count": summary.get("pending_gate_count", 0),
                },
            },
            indent=2,
        )

    artifacts = load_verified_weekly_artifacts(limit=limit)
    summary = build_persona_review_summary(artifacts, include_artifacts=True, artifact_limit=limit)
    operator_summary = (
        f"Persona review surface summarizes {summary.get('artifact_count', 0)} verified artifact(s); "
        f"{summary.get('pending_gate_count', 0)} persona gate(s) remain pending across "
        f"{summary.get('attached_contract_count', 0)} attached contract(s) and "
        f"{summary.get('fallback_contract_count', 0)} normalized fallback contract(s)."
    )
    evidence_refs = [
        _persona_review_evidence_ref(artifact)
        for artifact in (summary.get("recent_artifacts") or [])
        if isinstance(artifact, dict)
    ]
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "persona_review": summary,
        },
        indent=2,
    )


def _render_dream_findings(
    ctx: object | None,
    *,
    cycle_id: str | None = None,
    topic: str | None = None,
    min_confidence: float = 0.0,
) -> str:
    if ctx is None or not hasattr(ctx, "list_dream_findings"):
        return json.dumps(
            {"status": "error", "error": "dream_findings_unavailable"},
            indent=2,
        )
    payload = ctx.list_dream_findings(
        cycle_id=cycle_id,
        topic=topic,
        min_confidence=min_confidence,
    )
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    findings = [
        _normalize_dream_finding_payload(finding, governed_route=governed_route)
        for finding in (payload.get("findings") or [])
        if isinstance(finding, dict)
    ]
    operator_summary = (
        f"Dream findings surface returned {len(findings)} finding(s)"
        + (f" for cycle '{cycle_id}'" if cycle_id else "")
        + (f" filtered by topic '{topic}'" if topic else "")
        + (f" with minimum confidence {min_confidence:.2f}." if min_confidence else ".")
    )
    evidence_refs = _dedupe_reference_dicts(
        [
            _memory_ref_as_evidence(finding.get("memory_ref"))
            for finding in findings
            if isinstance(finding, dict)
        ],
        [
            ref
            for finding in findings
            if isinstance(finding, dict)
            for ref in (finding.get("evidence_refs") or [])
            if isinstance(ref, dict)
        ],
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "findings": findings,
            "count": len(findings),
        },
        indent=2,
    )


def _render_dream_finding(ctx: object | None, *, finding_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_finding"):
        return json.dumps(
            {"status": "error", "error": "dream_finding_unavailable", "finding_id": finding_id},
            indent=2,
        )
    finding = ctx.get_dream_finding(finding_id)
    if finding is None:
        return json.dumps({"status": "not_found", "finding_id": finding_id}, indent=2)
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    normalized_finding = _normalize_dream_finding_payload(finding, governed_route=governed_route)
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": normalized_finding.get("operator_summary"),
            "evidence_refs": normalized_finding.get("evidence_refs", []),
            "evidence_lineage": normalized_finding.get("evidence_lineage", []),
            "finding": normalized_finding,
        },
        indent=2,
    )


def _render_media_evidence(ctx: object | None, *, media_type: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "list_media_evidence"):
        return json.dumps({"status": "error", "error": "media_evidence_unavailable"}, indent=2)
    payload = ctx.list_media_evidence(media_type=media_type)
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    media_evidence = [
        _normalize_media_evidence_payload(evidence, governed_route=governed_route)
        for evidence in (payload.get("media_evidence") or [])
        if isinstance(evidence, dict)
    ]
    evidence_refs = _dedupe_reference_dicts(
        [
            ref
            for evidence in media_evidence
            if isinstance(evidence, dict)
            for ref in (evidence.get("evidence_refs") or [])
            if isinstance(ref, dict)
        ]
    )
    operator_summary = (
        f"Media evidence surface returned {len(media_evidence)} artifact(s)"
        + (f" filtered by media type '{media_type}'." if media_type else ".")
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "media_evidence": media_evidence,
            "count": len(media_evidence),
        },
        indent=2,
    )


def _render_media_evidence_detail(ctx: object | None, *, artifact_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_media_evidence"):
        return json.dumps(
            {"status": "error", "error": "media_evidence_unavailable", "artifact_id": artifact_id},
            indent=2,
        )
    evidence = ctx.get_media_evidence(artifact_id)
    if evidence is None:
        return json.dumps({"status": "not_found", "artifact_id": artifact_id}, indent=2)
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    normalized_evidence = _normalize_media_evidence_payload(evidence, governed_route=governed_route)
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": normalized_evidence.get("operator_summary"),
            "evidence_refs": normalized_evidence.get("evidence_refs", []),
            "evidence_lineage": normalized_evidence.get("evidence_lineage", []),
            "media_evidence": normalized_evidence,
        },
        indent=2,
    )


def _render_dream_proposals(ctx: object | None, *, lane: str | None = None) -> str:
    if ctx is None or not hasattr(ctx, "list_dream_proposals"):
        return json.dumps({"status": "error", "error": "dream_proposals_unavailable"}, indent=2)
    payload = ctx.list_dream_proposals(lane=lane)
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    proposals = [
        _normalize_dream_proposal_payload(proposal, governed_route=governed_route)
        for proposal in (payload.get("proposals") or [])
        if isinstance(proposal, dict)
    ]
    evidence_refs = _dedupe_reference_dicts(
        [
            ref
            for proposal in proposals
            if isinstance(proposal, dict)
            for ref in (proposal.get("evidence_refs") or [])
            if isinstance(ref, dict)
        ]
    )
    operator_summary = (
        f"Dream proposals surface returned {len(proposals)} proposal(s)"
        + (f" for lane '{lane}'." if lane else ".")
    )
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": operator_summary,
            "evidence_refs": evidence_refs,
            "proposals": proposals,
            "count": len(proposals),
        },
        indent=2,
    )


def _render_dream_proposal(ctx: object | None, *, proposal_id: str) -> str:
    if ctx is None or not hasattr(ctx, "get_dream_proposal"):
        return json.dumps(
            {"status": "error", "error": "dream_proposals_unavailable", "proposal_id": proposal_id},
            indent=2,
        )
    proposal = ctx.get_dream_proposal(proposal_id)
    if proposal is None:
        return json.dumps({"status": "not_found", "proposal_id": proposal_id}, indent=2)
    governed_route = ctx.get_governed_route() if hasattr(ctx, "get_governed_route") else None
    normalized_proposal = _normalize_dream_proposal_payload(proposal, governed_route=governed_route)
    return json.dumps(
        {
            "status": "ok",
            "operator_summary": normalized_proposal.get("operator_summary"),
            "evidence_refs": normalized_proposal.get("evidence_refs", []),
            "evidence_lineage": normalized_proposal.get("evidence_lineage", []),
            "proposal": normalized_proposal,
        },
        indent=2,
    )


def render_resource_uri(ctx: object | None, resource_uri: str) -> str:
    """Render a packaged resource URI outside the running MCP server."""
    if resource_uri == "hlf://agent/protocol":
        return _render_agent_protocol(ctx)

    if resource_uri == "hlf://agent/quickstart":
        return _render_agent_quickstart(ctx)

    if resource_uri == "hlf://agent/handoff_contract":
        return _render_agent_handoff_contract(ctx)

    if resource_uri == "hlf://agent/current_authority":
        return _render_agent_current_authority(ctx)

    if resource_uri == "hlf://status/benchmark_artifacts":
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        try:
            artifacts = memory.query_facts(entry_kind="benchmark_artifact")
        except Exception:
            artifacts = []
            for fact in memory.all_facts():
                if fact.get("entry_kind") == "benchmark_artifact":
                    artifacts.append(fact)
        return json.dumps({"status": "ok", "artifacts": artifacts}, indent=2)

    if resource_uri == "hlf://status/active_profiles":
        if ctx is None or not hasattr(ctx, "session_profiles"):
            return json.dumps(
                {"status": "error", "error": "session_profiles_unavailable"}, indent=2
            )
        evidence = {}
        if hasattr(ctx, "session_benchmark_artifacts"):
            evidence = ctx.session_benchmark_artifacts
        return json.dumps(
            {"status": "ok", "active_profiles": ctx.session_profiles, "evidence": evidence},
            indent=2,
        )

    if resource_uri == "hlf://status/profile_capability_catalog":
        return json.dumps(build_profile_capability_catalog(ctx), indent=2)

    if resource_uri == "hlf://status/multimodal_contracts":
        return json.dumps(build_multimodal_contract_catalog(ctx), indent=2)

    if resource_uri == "hlf://host_functions":
        if ctx is not None and hasattr(ctx, "host_registry"):
            return json.dumps({"functions": ctx.host_registry.list_all()}, indent=2)
        return json.dumps(
            _normalize_host_functions_payload(_read_governance_file("host_functions.json")),
            indent=2,
        )

    if resource_uri == "hlf://status/model_catalog":
        return _render_model_catalog_status(ctx)

    if resource_uri == "hlf://status/symbolic_surface":
        return _render_symbolic_surface_status(ctx)

    if resource_uri == "hlf://reports/symbolic_surface":
        return _render_symbolic_surface_markdown(ctx)

    if resource_uri == "hlf://explainer/symbolic_surface":
        return _render_symbolic_surface_explainer(ctx)

    if resource_uri == "hlf://status/fixture_gallery":
        return _render_fixture_gallery_status(ctx)

    if resource_uri == "hlf://reports/fixture_gallery":
        return _render_fixture_gallery_markdown(ctx)

    if resource_uri == "hlf://status/operator_surfaces":
        return _render_operator_surfaces_status(ctx)

    if resource_uri == "hlf://reports/operator_surfaces":
        return _render_operator_surfaces_markdown(ctx)

    if resource_uri == "hlf://teach/native_comprehension":
        return _render_native_comprehension_index(ctx)

    if resource_uri.startswith("hlf://teach/native_comprehension/"):
        return _render_native_comprehension_packet(
            ctx,
            surface_id=resource_uri.removeprefix("hlf://teach/native_comprehension/") or "",
        )

    if resource_uri == "hlf://status/translation_contract":
        return _render_translation_contract_status(ctx)

    if resource_uri == "hlf://reports/translation_contract":
        return _render_translation_contract_markdown(ctx)

    if resource_uri == "hlf://status/governed_recall":
        return _render_governed_recall_status(ctx)

    if resource_uri == "hlf://reports/governed_recall":
        return _render_governed_recall_markdown(ctx)

    if resource_uri == "hlf://status/hks_evaluation":
        return _render_hks_evaluation_status(ctx)

    if resource_uri == "hlf://reports/hks_evaluation":
        return _render_hks_evaluation_markdown(ctx)

    if resource_uri == "hlf://status/hks_external_compare":
        return _render_hks_external_compare_status(ctx)

    if resource_uri == "hlf://reports/hks_external_compare":
        return _render_hks_external_compare_markdown(ctx)

    if resource_uri.startswith("hlf://status/governed_recall/"):
        return _render_governed_recall_status(
            ctx,
            recall_id=resource_uri.removeprefix("hlf://status/governed_recall/") or None,
        )

    if resource_uri.startswith("hlf://reports/governed_recall/"):
        return _render_governed_recall_markdown(
            ctx,
            recall_id=resource_uri.removeprefix("hlf://reports/governed_recall/") or None,
        )

    if resource_uri.startswith("hlf://status/hks_evaluation/"):
        return _render_hks_evaluation_status(
            ctx,
            evaluation_id=resource_uri.removeprefix("hlf://status/hks_evaluation/") or None,
        )

    if resource_uri.startswith("hlf://reports/hks_evaluation/"):
        return _render_hks_evaluation_markdown(
            ctx,
            evaluation_id=resource_uri.removeprefix("hlf://reports/hks_evaluation/") or None,
        )

    if resource_uri.startswith("hlf://status/hks_external_compare/"):
        return _render_hks_external_compare_status(
            ctx,
            compare_id=resource_uri.removeprefix("hlf://status/hks_external_compare/") or None,
        )

    if resource_uri.startswith("hlf://reports/hks_external_compare/"):
        return _render_hks_external_compare_markdown(
            ctx,
            compare_id=resource_uri.removeprefix("hlf://reports/hks_external_compare/") or None,
        )

    if resource_uri == "hlf://status/internal_workflow":
        return _render_internal_workflow_status(ctx)

    if resource_uri == "hlf://reports/internal_workflow":
        return _render_internal_workflow_markdown(ctx)

    if resource_uri.startswith("hlf://status/internal_workflow/"):
        return _render_internal_workflow_status(
            ctx,
            workflow_id=resource_uri.removeprefix("hlf://status/internal_workflow/") or None,
        )

    if resource_uri.startswith("hlf://reports/internal_workflow/"):
        return _render_internal_workflow_markdown(
            ctx,
            workflow_id=resource_uri.removeprefix("hlf://reports/internal_workflow/") or None,
        )

    if resource_uri.startswith("hlf://status/translation_contract/"):
        return _render_translation_contract_status(
            ctx,
            contract_id=resource_uri.removeprefix("hlf://status/translation_contract/") or None,
        )

    if resource_uri.startswith("hlf://reports/translation_contract/"):
        return _render_translation_contract_markdown(
            ctx,
            contract_id=resource_uri.removeprefix("hlf://reports/translation_contract/") or None,
        )

    if resource_uri.startswith("hlf://status/model_catalog/"):
        return _render_model_catalog_status(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://status/model_catalog/") or None,
        )

    if resource_uri == "hlf://status/align":
        return _render_align_status(ctx)

    if resource_uri == "hlf://status/formal_verifier":
        return _render_formal_verifier_status(ctx)

    if resource_uri == "hlf://reports/formal_verifier":
        return _render_formal_verifier_markdown(ctx)

    if resource_uri == "hlf://status/governed_route":
        return _render_governed_route_status(ctx)

    if resource_uri == "hlf://reports/governed_route":
        return _render_governed_route_markdown(ctx)

    if resource_uri.startswith("hlf://status/governed_route/"):
        return _render_governed_route_status(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://status/governed_route/") or None,
        )

    if resource_uri.startswith("hlf://reports/governed_route/"):
        return _render_governed_route_markdown(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://reports/governed_route/") or None,
        )

    if resource_uri == "hlf://status/ingress":
        return _render_ingress_status(ctx)

    if resource_uri.startswith("hlf://status/ingress/"):
        return _render_ingress_status(
            ctx,
            agent_id=resource_uri.removeprefix("hlf://status/ingress/") or None,
        )

    if resource_uri == "hlf://status/instinct":
        return _render_instinct_status(ctx)

    if resource_uri.startswith("hlf://status/instinct/"):
        return _render_instinct_status(
            ctx,
            mission_id=resource_uri.removeprefix("hlf://status/instinct/") or None,
        )

    if resource_uri == "hlf://status/witness_governance":
        return _render_witness_status(ctx)

    if resource_uri.startswith("hlf://status/witness_governance/"):
        return _render_witness_status(
            ctx,
            subject_agent_id=resource_uri.removeprefix("hlf://status/witness_governance/") or None,
        )

    if resource_uri == "hlf://status/provenance_contract":
        return _render_provenance_contract(ctx)

    if resource_uri == "hlf://status/memory_governance":
        return _render_memory_governance_status(ctx)

    if resource_uri == "hlf://status/approval_queue":
        return _render_approval_review_status(ctx)

    if resource_uri.startswith("hlf://status/approval_queue/"):
        return _render_approval_review_status(
            ctx,
            request_id=resource_uri.removeprefix("hlf://status/approval_queue/") or None,
        )

    if resource_uri == "hlf://status/approval_bypass":
        return _render_approval_bypass_status(ctx)

    if resource_uri.startswith("hlf://status/approval_bypass/"):
        return _render_approval_bypass_status(
            ctx,
            subject_agent_id=resource_uri.removeprefix("hlf://status/approval_bypass/") or None,
        )

    if resource_uri == "hlf://status/persona_review":
        return _render_persona_review_status(ctx)

    if resource_uri.startswith("hlf://status/persona_review/"):
        return _render_persona_review_status(
            ctx,
            artifact_id=resource_uri.removeprefix("hlf://status/persona_review/") or None,
        )

    if resource_uri == "hlf://status/dream-cycle":
        return _render_dream_cycle_status(ctx)

    if resource_uri == "hlf://status/entropy_anchor":
        return _render_entropy_anchor_status(ctx)

    if resource_uri == "hlf://status/daemon_alerts":
        return _render_daemon_alert_status(ctx)

    if resource_uri == "hlf://status/daemon_transparency":
        return _render_daemon_transparency_status(ctx)

    if resource_uri == "hlf://reports/daemon_transparency":
        return _render_daemon_transparency_markdown(ctx)

    if resource_uri == "hlf://dream/findings":
        return _render_dream_findings(ctx)

    if resource_uri.startswith("hlf://dream/findings/"):
        return _render_dream_finding(
            ctx,
            finding_id=resource_uri.removeprefix("hlf://dream/findings/") or "",
        )

    if resource_uri == "hlf://media/evidence":
        return _render_media_evidence(ctx)

    if resource_uri.startswith("hlf://media/evidence/"):
        return _render_media_evidence_detail(
            ctx,
            artifact_id=resource_uri.removeprefix("hlf://media/evidence/") or "",
        )

    if resource_uri == "hlf://dream/proposals":
        return _render_dream_proposals(ctx)

    if resource_uri.startswith("hlf://dream/proposals/"):
        return _render_dream_proposal(
            ctx,
            proposal_id=resource_uri.removeprefix("hlf://dream/proposals/") or "",
        )

    return json.dumps(
        {"status": "error", "error": "unsupported_resource_uri", "resource_uri": resource_uri},
        indent=2,
    )


def register_resources(mcp: FastMCP, ctx: object | None = None) -> dict[str, object]:
    @mcp.resource("hlf://status/benchmark_artifacts")
    def get_benchmark_artifacts() -> str:
        """Operator-facing: List all persisted benchmark artifacts."""
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        try:
            artifacts = memory.query_facts(entry_kind="benchmark_artifact")
        except Exception:
            artifacts = []
            for fact in memory.all_facts():
                if fact.get("entry_kind") != "benchmark_artifact":
                    continue
                artifacts.append(fact)
        return json.dumps({"status": "ok", "artifacts": artifacts}, indent=2)

    @mcp.resource("hlf://status/active_profiles")
    def get_active_profiles() -> str:
        """Operator-facing: List currently active profiles and their supporting evidence."""
        if ctx is None or not hasattr(ctx, "session_profiles"):
            return json.dumps(
                {"status": "error", "error": "session_profiles_unavailable"}, indent=2
            )
        profiles = ctx.session_profiles
        evidence = {}
        if hasattr(ctx, "session_benchmark_artifacts"):
            evidence = ctx.session_benchmark_artifacts
        return json.dumps(
            {"status": "ok", "active_profiles": profiles, "evidence": evidence}, indent=2
        )

    @mcp.resource("hlf://status/profile_evidence/{profile_name}")
    def get_profile_evidence(profile_name: str) -> str:
        """Operator-facing: List all evidence (artifacts, scores, history) for a given profile."""
        if ctx is None or not hasattr(ctx, "memory_store"):
            return json.dumps({"status": "error", "error": "memory_store_unavailable"}, indent=2)
        memory = ctx.memory_store
        evidence = []
        try:
            evidence = memory.query_facts(entry_kind="benchmark_artifact", profile=profile_name)
        except Exception:
            for fact in memory.all_facts():
                if fact.get("entry_kind") != "benchmark_artifact":
                    continue
                if fact.get("profile") != profile_name:
                    continue
                evidence.append(fact)
        return json.dumps({"status": "ok", "profile": profile_name, "evidence": evidence}, indent=2)

    @mcp.resource("hlf://status/profile_capability_catalog")
    def get_profile_capability_catalog() -> str:
        """Operator-facing governed profile catalog across qualification profiles and active session profiles."""
        return json.dumps(build_profile_capability_catalog(ctx), indent=2)

    @mcp.resource("hlf://status/multimodal_contracts")
    def get_multimodal_contracts() -> str:
        """Operator-facing multimodal qualification profiles mapped to current host-function contracts."""
        return json.dumps(build_multimodal_contract_catalog(ctx), indent=2)

    @mcp.resource("hlf://grammar")
    def get_grammar() -> str:
        """HLF grammar specification (LALR(1) Lark format)."""
        from hlf_mcp.hlf.grammar import HLF_GRAMMAR

        return HLF_GRAMMAR

    @mcp.resource("hlf://opcodes")
    def get_opcodes() -> str:
        """HLF bytecode opcode table (37 opcodes)."""
        return json.dumps(OPCODES, indent=2)

    @mcp.resource("hlf://host_functions")
    def get_host_functions() -> str:
        """Available HLF host function registry from the packaged governed contract surface."""
        if ctx is not None and hasattr(ctx, "host_registry"):
            normalized: dict[str, object] = {"functions": ctx.host_registry.list_all()}
        else:
            normalized = _normalize_host_functions_payload(
                _read_governance_file("host_functions.json")
            )
        return json.dumps(normalized, indent=2)

    @mcp.resource("hlf://examples/{name}")
    def get_example(name: str) -> str:
        """Return a named example HLF program."""
        return _read_fixture_file(name)

    @mcp.resource("hlf://governance/host_functions")
    def get_governance_host_functions() -> str:
        """Governance host_functions.json — full host function definitions."""
        return _read_governance_file("host_functions.json")

    @mcp.resource("hlf://governance/bytecode_spec")
    def get_governance_bytecode_spec() -> str:
        """Governance bytecode_spec.yaml — bytecode encoding specification."""
        return _read_governance_file("bytecode_spec.yaml")

    @mcp.resource("hlf://governance/align_rules")
    def get_governance_align_rules() -> str:
        """Governance align_rules.json — alignment and safety rules."""
        return _read_governance_file("align_rules.json")

    @mcp.resource("hlf://governance/tag_i18n")
    def get_governance_tag_i18n() -> str:
        """Multilingual HLF tag registry — 14 canonical tags × 8 languages + ASCII glyph aliases."""
        return _read_governance_file("tag_i18n.yaml")

    @mcp.resource("hlf://stdlib")
    def get_stdlib() -> str:
        """List all available HLF stdlib modules."""
        stdlib_dir = _PACKAGE_DIR / "hlf" / "stdlib"
        if not os.path.isdir(stdlib_dir):
            return json.dumps({"modules": []})
        modules = sorted(
            name[:-3]
            for name in os.listdir(stdlib_dir)
            if name.endswith(".py") and not name.startswith("_")
        )
        return json.dumps({"modules": modules}, indent=2)

    @mcp.resource("hlf://status/model_catalog")
    def get_model_catalog_status_latest() -> str:
        """Latest operator-facing status summary for the synced governed model catalog."""
        return _render_model_catalog_status(ctx)

    @mcp.resource("hlf://status/symbolic_surface")
    def get_symbolic_surface_status() -> str:
        """Operator-facing symbolic bridge proof surface with inspectable relation artifacts and authority labels."""
        return _render_symbolic_surface_status(ctx)

    @mcp.resource("hlf://reports/symbolic_surface")
    def get_symbolic_surface_report() -> str:
        """Operator-facing markdown symbolic bridge report derived from the same inspectable proof bundle."""
        return _render_symbolic_surface_markdown(ctx)

    @mcp.resource("hlf://explainer/symbolic_surface")
    def get_symbolic_surface_explainer() -> str:
        """Operator-facing display-only symbolic explainer card derived from the same relation artifacts."""
        return _render_symbolic_surface_explainer(ctx)

    @mcp.resource("hlf://status/fixture_gallery")
    def get_fixture_gallery_status() -> str:
        """Operator-facing generated fixture gallery health derived from packaged fixture compilation truth."""
        return _render_fixture_gallery_status(ctx)

    @mcp.resource("hlf://reports/fixture_gallery")
    def get_fixture_gallery_report() -> str:
        """Operator-facing markdown fixture gallery report derived from packaged compile and bytecode checks."""
        return _render_fixture_gallery_markdown(ctx)

    @mcp.resource("hlf://status/operator_surfaces")
    def get_operator_surfaces_status() -> str:
        """Operator-facing discovery index for packaged status, report, and explainer surfaces."""
        return _render_operator_surfaces_status(ctx)

    @mcp.resource("hlf://reports/operator_surfaces")
    def get_operator_surfaces_report() -> str:
        """Operator-facing markdown index of packaged discovery-ready operator surfaces."""
        return _render_operator_surfaces_markdown(ctx)

    @mcp.resource("hlf://agent/protocol")
    def get_agent_protocol() -> str:
        """Arriving-agent protocol surface for HLF meaning, handoff, and coordination semantics."""
        return _render_agent_protocol(ctx)

    @mcp.resource("hlf://agent/quickstart")
    def get_agent_quickstart() -> str:
        """Arriving-agent quickstart surface for the minimum deterministic HLF working loop."""
        return _render_agent_quickstart(ctx)

    @mcp.resource("hlf://agent/handoff_contract")
    def get_agent_handoff_contract() -> str:
        """Arriving-agent handoff contract surface for bounded producer and consumer semantics."""
        return _render_agent_handoff_contract(ctx)

    @mcp.resource("hlf://agent/current_authority")
    def get_agent_current_authority() -> str:
        """Arriving-agent authority surface for capsule, ingress, and promotion boundaries."""
        return _render_agent_current_authority(ctx)

    @mcp.resource("hlf://teach/native_comprehension")
    def get_native_comprehension_index() -> str:
        """Operator-facing layered reading index over existing governed packaged surfaces."""
        return _render_native_comprehension_index(ctx)

    @mcp.resource("hlf://teach/native_comprehension/{surface_id}")
    def get_native_comprehension_packet(surface_id: str) -> str:
        """Operator-facing layered reading packet for a specific governed packaged surface."""
        return _render_native_comprehension_packet(ctx, surface_id=surface_id)

    @mcp.resource("hlf://status/translation_contract")
    def get_translation_contract_status_latest() -> str:
        """Operator-facing latest persisted translation contract chain with compile and governance proof."""
        return _render_translation_contract_status(ctx)

    @mcp.resource("hlf://reports/translation_contract")
    def get_translation_contract_report_latest() -> str:
        """Operator-facing markdown report for the latest persisted translation contract chain."""
        return _render_translation_contract_markdown(ctx)

    @mcp.resource("hlf://status/translation_contract/{contract_id}")
    def get_translation_contract_status_for_id(contract_id: str) -> str:
        """Operator-facing translation contract chain for a specific contract id."""
        return _render_translation_contract_status(ctx, contract_id=contract_id)

    @mcp.resource("hlf://reports/translation_contract/{contract_id}")
    def get_translation_contract_report_for_id(contract_id: str) -> str:
        """Operator-facing markdown report for a specific translation contract id."""
        return _render_translation_contract_markdown(ctx, contract_id=contract_id)

    @mcp.resource("hlf://status/governed_recall")
    def get_governed_recall_status_latest() -> str:
        """Operator-facing latest persisted governed recall chain across HKS and weekly evidence recall flows."""
        return _render_governed_recall_status(ctx)

    @mcp.resource("hlf://reports/governed_recall")
    def get_governed_recall_report_latest() -> str:
        """Operator-facing markdown report for the latest persisted governed recall chain."""
        return _render_governed_recall_markdown(ctx)

    @mcp.resource("hlf://status/hks_evaluation")
    def get_hks_evaluation_status_latest() -> str:
        """Operator-facing latest persisted HKS evaluation chain across capture and recall flows."""
        return _render_hks_evaluation_status(ctx)

    @mcp.resource("hlf://reports/hks_evaluation")
    def get_hks_evaluation_report_latest() -> str:
        """Operator-facing markdown report for the latest persisted HKS evaluation chain."""
        return _render_hks_evaluation_markdown(ctx)

    @mcp.resource("hlf://status/hks_external_compare")
    def get_hks_external_compare_status_latest() -> str:
        """Operator-facing latest quarantined external comparator contract for HKS evaluation workflows."""
        return _render_hks_external_compare_status(ctx)

    @mcp.resource("hlf://reports/hks_external_compare")
    def get_hks_external_compare_report_latest() -> str:
        """Operator-facing markdown report for the latest quarantined external comparator contract."""
        return _render_hks_external_compare_markdown(ctx)

    @mcp.resource("hlf://status/governed_recall/{recall_id}")
    def get_governed_recall_status_for_id(recall_id: str) -> str:
        """Operator-facing governed recall chain for a specific recall id."""
        return _render_governed_recall_status(ctx, recall_id=recall_id)

    @mcp.resource("hlf://reports/governed_recall/{recall_id}")
    def get_governed_recall_report_for_id(recall_id: str) -> str:
        """Operator-facing markdown report for a specific governed recall id."""
        return _render_governed_recall_markdown(ctx, recall_id=recall_id)

    @mcp.resource("hlf://status/hks_evaluation/{evaluation_id}")
    def get_hks_evaluation_status_for_id(evaluation_id: str) -> str:
        """Operator-facing HKS evaluation chain for a specific evaluation id."""
        return _render_hks_evaluation_status(ctx, evaluation_id=evaluation_id)

    @mcp.resource("hlf://reports/hks_evaluation/{evaluation_id}")
    def get_hks_evaluation_report_for_id(evaluation_id: str) -> str:
        """Operator-facing markdown report for a specific HKS evaluation id."""
        return _render_hks_evaluation_markdown(ctx, evaluation_id=evaluation_id)

    @mcp.resource("hlf://status/hks_external_compare/{compare_id}")
    def get_hks_external_compare_status_for_id(compare_id: str) -> str:
        """Operator-facing quarantined external comparator contract for a specific compare id."""
        return _render_hks_external_compare_status(ctx, compare_id=compare_id)

    @mcp.resource("hlf://reports/hks_external_compare/{compare_id}")
    def get_hks_external_compare_report_for_id(compare_id: str) -> str:
        """Operator-facing markdown report for a specific quarantined external comparator contract."""
        return _render_hks_external_compare_markdown(ctx, compare_id=compare_id)

    @mcp.resource("hlf://status/internal_workflow")
    def get_internal_workflow_status_latest() -> str:
        """Operator-facing latest persisted bounded internal workflow contract."""
        return _render_internal_workflow_status(ctx)

    @mcp.resource("hlf://reports/internal_workflow")
    def get_internal_workflow_report_latest() -> str:
        """Operator-facing markdown report for the latest bounded internal workflow contract."""
        return _render_internal_workflow_markdown(ctx)

    @mcp.resource("hlf://status/internal_workflow/{workflow_id}")
    def get_internal_workflow_status_for_id(workflow_id: str) -> str:
        """Operator-facing bounded internal workflow contract for a specific workflow id."""
        return _render_internal_workflow_status(ctx, workflow_id=workflow_id)

    @mcp.resource("hlf://reports/internal_workflow/{workflow_id}")
    def get_internal_workflow_report_for_id(workflow_id: str) -> str:
        """Operator-facing markdown report for a specific bounded internal workflow contract."""
        return _render_internal_workflow_markdown(ctx, workflow_id=workflow_id)

    @mcp.resource("hlf://status/model_catalog/{agent_id}")
    def get_model_catalog_status_for_agent(agent_id: str) -> str:
        """Operator-facing status summary for a specific agent's synced governed model catalog."""
        return _render_model_catalog_status(ctx, agent_id=agent_id)

    @mcp.resource("hlf://status/ingress")
    def get_ingress_status_latest() -> str:
        """Operator-facing packaged ingress status summary."""
        return _render_ingress_status(ctx)

    @mcp.resource("hlf://status/ingress/{agent_id}")
    def get_ingress_status_for_agent(agent_id: str) -> str:
        """Operator-facing packaged ingress status summary for a specific agent."""
        return _render_ingress_status(ctx, agent_id=agent_id)

    @mcp.resource("hlf://status/align")
    def get_align_status() -> str:
        """Operator-facing ALIGN governor status including normalized action semantics."""
        return _render_align_status(ctx)

    @mcp.resource("hlf://status/formal_verifier")
    def get_formal_verifier_status() -> str:
        """Operator-facing formal verifier status including solver and capability snapshot."""
        return _render_formal_verifier_status(ctx)

    @mcp.resource("hlf://reports/formal_verifier")
    def get_formal_verifier_report() -> str:
        """Operator-facing markdown formal verifier report derived from the packaged verifier status surface."""
        return _render_formal_verifier_markdown(ctx)

    @mcp.resource("hlf://status/governed_route")
    def get_governed_route_status_latest() -> str:
        """Operator-facing latest governed route trace summary."""
        return _render_governed_route_status(ctx)

    @mcp.resource("hlf://reports/governed_route")
    def get_governed_route_report_latest() -> str:
        """Operator-facing markdown governed route report derived from the packaged route status surface."""
        return _render_governed_route_markdown(ctx)

    @mcp.resource("hlf://status/governed_route/{agent_id}")
    def get_governed_route_status_for_agent(agent_id: str) -> str:
        """Operator-facing governed route trace summary for a specific agent."""
        return _render_governed_route_status(ctx, agent_id=agent_id)

    @mcp.resource("hlf://reports/governed_route/{agent_id}")
    def get_governed_route_report_for_agent(agent_id: str) -> str:
        """Operator-facing markdown governed route report for a specific agent."""
        return _render_governed_route_markdown(ctx, agent_id=agent_id)

    @mcp.resource("hlf://status/instinct")
    def get_instinct_status() -> str:
        """Operator-facing Instinct lifecycle mission list with current phase and realignment counts."""
        return _render_instinct_status(ctx)

    @mcp.resource("hlf://status/instinct/{mission_id}")
    def get_instinct_status_for_mission(mission_id: str) -> str:
        """Operator-facing Instinct lifecycle status for a specific mission."""
        return _render_instinct_status(ctx, mission_id=mission_id)

    @mcp.resource("hlf://status/witness_governance")
    def get_witness_status_summary() -> str:
        """Operator-facing packaged witness-governance summary across tracked subjects."""
        return _render_witness_status(ctx)

    @mcp.resource("hlf://status/witness_governance/{subject_agent_id}")
    def get_witness_status_for_subject(subject_agent_id: str) -> str:
        """Operator-facing packaged witness-governance status for a specific subject."""
        return _render_witness_status(ctx, subject_agent_id=subject_agent_id)

    @mcp.resource("hlf://status/provenance_contract")
    def get_provenance_contract() -> str:
        """Operator-facing packaged provenance summary across memory, governance, witness, and evidence surfaces."""
        return _render_provenance_contract(ctx)

    @mcp.resource("hlf://status/memory_governance")
    def get_memory_governance_status() -> str:
        """Operator-facing governance targets and governed memory state for revocation or tombstone intervention."""
        return _render_memory_governance_status(ctx)

    @mcp.resource("hlf://status/approval_queue")
    def get_approval_queue_status() -> str:
        """Operator-facing approval queue summary across pending or decided capsule review requests."""
        return _render_approval_review_status(ctx)

    @mcp.resource("hlf://status/approval_queue/{request_id}")
    def get_approval_queue_request(request_id: str) -> str:
        """Operator-facing approval transition history for a specific capsule review request."""
        return _render_approval_review_status(ctx, request_id=request_id)

    @mcp.resource("hlf://status/approval_bypass")
    def get_approval_bypass_status() -> str:
        """Operator-facing recent blocked approval-bypass attempts across governed subjects."""
        return _render_approval_bypass_status(ctx)

    @mcp.resource("hlf://status/approval_bypass/{subject_agent_id}")
    def get_approval_bypass_status_for_subject(subject_agent_id: str) -> str:
        """Operator-facing recent blocked approval-bypass attempts for a specific governed subject."""
        return _render_approval_bypass_status(ctx, subject_agent_id=subject_agent_id)

    @mcp.resource("hlf://status/persona_review")
    def get_persona_review_status() -> str:
        """Operator-facing persona ownership and gate rollup across verified weekly evidence artifacts."""
        return _render_persona_review_status(ctx)

    @mcp.resource("hlf://status/persona_review/{artifact_id}")
    def get_persona_review_status_for_artifact(artifact_id: str) -> str:
        """Operator-facing persona ownership and gate state for a specific weekly evidence artifact."""
        return _render_persona_review_status(ctx, artifact_id=artifact_id)

    @mcp.resource("hlf://status/dream-cycle")
    def get_dream_cycle_status() -> str:
        """Operator-facing bounded dream-cycle status across recent advisory runs."""
        return _render_dream_cycle_status(ctx)

    @mcp.resource("hlf://status/entropy_anchor")
    def get_entropy_anchor_status() -> str:
        """Operator-facing recent entropy-anchor results with audit-linked evidence refs."""
        return _render_entropy_anchor_status(ctx)

    @mcp.resource("hlf://status/daemon_alerts")
    def get_daemon_alert_status() -> str:
        """Operator-facing packaged daemon-alert proxy across governance-spine warnings and weekly evidence alerts."""
        return _render_daemon_alert_status(ctx)

    @mcp.resource("hlf://status/daemon_transparency")
    def get_daemon_transparency_status() -> str:
        """Operator-facing rolling daemon transparency surface derived from recent governance-spine events."""
        return _render_daemon_transparency_status(ctx)

    @mcp.resource("hlf://reports/daemon_transparency")
    def get_daemon_transparency_report() -> str:
        """Operator-facing markdown daemon transparency report derived from packaged governance-spine events."""
        return _render_daemon_transparency_markdown(ctx)

    @mcp.resource("hlf://dream/findings")
    def get_dream_findings() -> str:
        """Operator-facing list of advisory dream findings from bounded dream-cycle runs."""
        return _render_dream_findings(ctx)

    @mcp.resource("hlf://dream/findings/{finding_id}")
    def get_dream_finding(finding_id: str) -> str:
        """Operator-facing detail view for a specific advisory dream finding."""
        return _render_dream_finding(ctx, finding_id=finding_id)

    @mcp.resource("hlf://media/evidence")
    def get_media_evidence() -> str:
        """Operator-facing list of normalized shared media evidence records."""
        return _render_media_evidence(ctx)

    @mcp.resource("hlf://media/evidence/{artifact_id}")
    def get_media_evidence_detail(artifact_id: str) -> str:
        """Operator-facing detail for a specific shared media evidence record."""
        return _render_media_evidence_detail(ctx, artifact_id=artifact_id)

    @mcp.resource("hlf://dream/proposals")
    def get_dream_proposals() -> str:
        """Operator-facing list of advisory dream proposals with explicit citation-chain gates."""
        return _render_dream_proposals(ctx)

    @mcp.resource("hlf://dream/proposals/{proposal_id}")
    def get_dream_proposal(proposal_id: str) -> str:
        """Operator-facing detail view for a specific advisory dream proposal."""
        return _render_dream_proposal(ctx, proposal_id=proposal_id)

    return {
        "hlf://grammar": get_grammar,
        "hlf://opcodes": get_opcodes,
        "hlf://host_functions": get_host_functions,
        "hlf://examples/{name}": get_example,
        "hlf://governance/host_functions": get_governance_host_functions,
        "hlf://governance/bytecode_spec": get_governance_bytecode_spec,
        "hlf://governance/align_rules": get_governance_align_rules,
        "hlf://governance/tag_i18n": get_governance_tag_i18n,
        "hlf://stdlib": get_stdlib,
        "hlf://status/model_catalog": get_model_catalog_status_latest,
        "hlf://status/symbolic_surface": get_symbolic_surface_status,
        "hlf://reports/symbolic_surface": get_symbolic_surface_report,
        "hlf://explainer/symbolic_surface": get_symbolic_surface_explainer,
        "hlf://status/fixture_gallery": get_fixture_gallery_status,
        "hlf://reports/fixture_gallery": get_fixture_gallery_report,
        "hlf://status/operator_surfaces": get_operator_surfaces_status,
        "hlf://reports/operator_surfaces": get_operator_surfaces_report,
        "hlf://agent/protocol": get_agent_protocol,
        "hlf://agent/quickstart": get_agent_quickstart,
        "hlf://agent/handoff_contract": get_agent_handoff_contract,
        "hlf://agent/current_authority": get_agent_current_authority,
        "hlf://teach/native_comprehension": get_native_comprehension_index,
        "hlf://teach/native_comprehension/{surface_id}": get_native_comprehension_packet,
        "hlf://status/translation_contract": get_translation_contract_status_latest,
        "hlf://reports/translation_contract": get_translation_contract_report_latest,
        "hlf://status/translation_contract/{contract_id}": get_translation_contract_status_for_id,
        "hlf://reports/translation_contract/{contract_id}": get_translation_contract_report_for_id,
        "hlf://status/governed_recall": get_governed_recall_status_latest,
        "hlf://reports/governed_recall": get_governed_recall_report_latest,
        "hlf://status/hks_evaluation": get_hks_evaluation_status_latest,
        "hlf://reports/hks_evaluation": get_hks_evaluation_report_latest,
        "hlf://status/hks_external_compare": get_hks_external_compare_status_latest,
        "hlf://reports/hks_external_compare": get_hks_external_compare_report_latest,
        "hlf://status/governed_recall/{recall_id}": get_governed_recall_status_for_id,
        "hlf://reports/governed_recall/{recall_id}": get_governed_recall_report_for_id,
        "hlf://status/hks_evaluation/{evaluation_id}": get_hks_evaluation_status_for_id,
        "hlf://reports/hks_evaluation/{evaluation_id}": get_hks_evaluation_report_for_id,
        "hlf://status/hks_external_compare/{compare_id}": get_hks_external_compare_status_for_id,
        "hlf://reports/hks_external_compare/{compare_id}": get_hks_external_compare_report_for_id,
        "hlf://status/internal_workflow": get_internal_workflow_status_latest,
        "hlf://reports/internal_workflow": get_internal_workflow_report_latest,
        "hlf://status/internal_workflow/{workflow_id}": get_internal_workflow_status_for_id,
        "hlf://reports/internal_workflow/{workflow_id}": get_internal_workflow_report_for_id,
        "hlf://status/model_catalog/{agent_id}": get_model_catalog_status_for_agent,
        "hlf://status/ingress": get_ingress_status_latest,
        "hlf://status/ingress/{agent_id}": get_ingress_status_for_agent,
        "hlf://status/align": get_align_status,
        "hlf://status/formal_verifier": get_formal_verifier_status,
        "hlf://reports/formal_verifier": get_formal_verifier_report,
        "hlf://status/governed_route": get_governed_route_status_latest,
        "hlf://reports/governed_route": get_governed_route_report_latest,
        "hlf://status/governed_route/{agent_id}": get_governed_route_status_for_agent,
        "hlf://reports/governed_route/{agent_id}": get_governed_route_report_for_agent,
        "hlf://status/instinct": get_instinct_status,
        "hlf://status/instinct/{mission_id}": get_instinct_status_for_mission,
        "hlf://status/witness_governance": get_witness_status_summary,
        "hlf://status/witness_governance/{subject_agent_id}": get_witness_status_for_subject,
        "hlf://status/provenance_contract": get_provenance_contract,
        "hlf://status/memory_governance": get_memory_governance_status,
        "hlf://status/approval_queue": get_approval_queue_status,
        "hlf://status/approval_queue/{request_id}": get_approval_queue_request,
        "hlf://status/approval_bypass": get_approval_bypass_status,
        "hlf://status/approval_bypass/{subject_agent_id}": get_approval_bypass_status_for_subject,
        "hlf://status/persona_review": get_persona_review_status,
        "hlf://status/persona_review/{artifact_id}": get_persona_review_status_for_artifact,
        "hlf://status/dream-cycle": get_dream_cycle_status,
        "hlf://status/entropy_anchor": get_entropy_anchor_status,
        "hlf://status/daemon_alerts": get_daemon_alert_status,
        "hlf://status/daemon_transparency": get_daemon_transparency_status,
        "hlf://reports/daemon_transparency": get_daemon_transparency_report,
        "hlf://dream/findings": get_dream_findings,
        "hlf://dream/findings/{finding_id}": get_dream_finding,
        "hlf://status/benchmark_artifacts": get_benchmark_artifacts,
        "hlf://status/active_profiles": get_active_profiles,
        "hlf://status/profile_evidence/{profile_name}": get_profile_evidence,
        "hlf://status/profile_capability_catalog": get_profile_capability_catalog,
        "hlf://status/multimodal_contracts": get_multimodal_contracts,
        "hlf://media/evidence": get_media_evidence,
        "hlf://media/evidence/{artifact_id}": get_media_evidence_detail,
        "hlf://dream/proposals": get_dream_proposals,
        "hlf://dream/proposals/{proposal_id}": get_dream_proposal,
    }
