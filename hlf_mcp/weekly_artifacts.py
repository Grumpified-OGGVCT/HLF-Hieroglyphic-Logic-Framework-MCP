from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hlf_mcp.governed_review import normalize_governed_review, validate_governed_review
from hlf_mcp.rag.memory import HKSProvenance, HKSTestEvidence, HKSValidatedExemplar
from hlf_mcp.test_runner import DEFAULT_METRICS_DIR, LATEST_SUMMARY_FILE

WEEKLY_ARTIFACT_SCHEMA_VERSION = "1.3"
WEEKLY_ARTIFACT_COLLECTOR_VERSION = "2026-03-19"
WEEKLY_LATEST_ARTIFACT = "weekly_pipeline_latest.json"
WEEKLY_HISTORY_ARTIFACT = "weekly_pipeline_history.jsonl"

ALLOWED_ARTIFACT_STATUSES = {
    "advisory",
    "triaged",
    "promoted",
    "rejected",
    "deferred",
}
ALLOWED_TRIAGE_LANES = {
    "ignore",
    "backlog",
    "current_batch",
    "future_batch",
    "doctrine_only",
}
ALLOWED_DECISION_TYPES = {"triaged", "promoted", "rejected", "deferred"}
ALLOWED_SECURITY_COLLECTION_STATES = {
    "not_collected",
    "metadata_only",
    "summary_collected",
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _compute_weekly_artifact_id(
    *, source: str, generated_at: str, git_context: dict[str, Any]
) -> str:
    digest = hashlib.sha256(
        _stable_json(
            {
                "source": source,
                "generated_at": generated_at,
                "branch": git_context.get("branch"),
                "commit_sha": git_context.get("commit_sha"),
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"weekly_{digest[:16]}"


def _promotion_state_for_status(status: str) -> str:
    if status == "promoted":
        return "approved_for_distribution"
    if status == "rejected":
        return "rejected"
    return "requires_verification"


def _default_distribution_contract(status: str) -> dict[str, Any]:
    return {
        "requires_source_compliance": True,
        "eligible_for_governed_distribution": status == "promoted",
        "target_class": "source_compliant_forks_and_mcp_consumers",
        "governor_surface": "governance.update_governor.UpdateGovernor",
        "compliance_surface": "scripts.fork_compliance_check.run_compliance_check",
        "eligibility_reason": (
            "artifact_promoted_for_distribution"
            if status == "promoted"
            else "awaiting_promotion_or_operator_gate"
        ),
    }


def _validate_decision_record(record: dict[str, Any], index: int, errors: list[str]) -> None:
    prefix = f"decision_record[{index}]"
    if not isinstance(record.get("decision_id"), str) or not record.get("decision_id"):
        errors.append(f"{prefix}.decision_id_invalid")
    if record.get("decision") not in ALLOWED_DECISION_TYPES:
        errors.append(f"{prefix}.decision_invalid")
    if record.get("status_after") not in ALLOWED_ARTIFACT_STATUSES:
        errors.append(f"{prefix}.status_after_invalid")
    if not isinstance(record.get("decided_at"), str) or not record.get("decided_at"):
        errors.append(f"{prefix}.decided_at_invalid")
    if not isinstance(record.get("actor"), str) or not record.get("actor"):
        errors.append(f"{prefix}.actor_invalid")
    if not isinstance(record.get("rationale"), str) or not record.get("rationale"):
        errors.append(f"{prefix}.rationale_invalid")
    if not isinstance(record.get("evidence_refs") or [], list):
        errors.append(f"{prefix}.evidence_refs_invalid")
    triage_lane = record.get("triage_lane")
    if triage_lane is not None and triage_lane not in ALLOWED_TRIAGE_LANES:
        errors.append(f"{prefix}.triage_lane_invalid")


def _coerce_metrics_dir(metrics_dir: Path | None) -> Path:
    return metrics_dir or DEFAULT_METRICS_DIR


def _normalize_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _normalize_count_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not key:
            continue
        normalized_count = _normalize_optional_int(count)
        if normalized_count is None:
            continue
        normalized[key] = normalized_count
    return normalized


def _default_security_findings() -> dict[str, Any]:
    return {
        "collection_state": "not_collected",
        "source": None,
        "tool": "CodeQL",
        "codeql_category": None,
        "alerts_available": False,
        "summary": {
            "total_alerts": None,
            "open_alerts": None,
            "closed_alerts": None,
            "severity_counts": {},
            "state_counts": {},
        },
        "evidence_refs": [],
    }


def _normalize_security_findings(workflow_payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized = _default_security_findings()
    if not isinstance(workflow_payload, dict):
        return normalized

    explicit_payload = workflow_payload.get("security_findings")
    code_quality_payload = workflow_payload.get("code_quality")
    code_quality = code_quality_payload if isinstance(code_quality_payload, dict) else None

    if isinstance(explicit_payload, dict):
        summary_payload = explicit_payload.get("summary")
        summary = summary_payload if isinstance(summary_payload, dict) else {}
        collection_state = explicit_payload.get("collection_state")
        if collection_state not in ALLOWED_SECURITY_COLLECTION_STATES:
            collection_state = "summary_collected"

        total_alerts = summary.get("total_alerts")
        if total_alerts is None:
            total_alerts = explicit_payload.get("total_alerts")
        open_alerts = summary.get("open_alerts")
        if open_alerts is None:
            open_alerts = summary.get("open_alert_count")
        if open_alerts is None:
            open_alerts = explicit_payload.get("open_alerts")
        if open_alerts is None:
            open_alerts = explicit_payload.get("open_alert_count")
        closed_alerts = summary.get("closed_alerts")
        if closed_alerts is None:
            closed_alerts = explicit_payload.get("closed_alerts")

        normalized["collection_state"] = collection_state
        normalized["source"] = "workflow_payload.security_findings"
        if isinstance(explicit_payload.get("tool"), str) and explicit_payload.get("tool"):
            normalized["tool"] = explicit_payload["tool"]
        codeql_category = explicit_payload.get("codeql_category") or (
            (code_quality or {}).get("codeql_category")
        )
        if isinstance(codeql_category, str) and codeql_category:
            normalized["codeql_category"] = codeql_category

        alerts_available = explicit_payload.get("alerts_available")
        if isinstance(alerts_available, bool):
            normalized["alerts_available"] = alerts_available
        else:
            normalized["alerts_available"] = collection_state == "summary_collected"

        normalized["summary"] = {
            "total_alerts": _normalize_optional_int(total_alerts),
            "open_alerts": _normalize_optional_int(open_alerts),
            "closed_alerts": _normalize_optional_int(closed_alerts),
            "severity_counts": _normalize_count_mapping(
                summary.get("severity_counts") or explicit_payload.get("severity_counts") or {}
            ),
            "state_counts": _normalize_count_mapping(
                summary.get("state_counts") or explicit_payload.get("state_counts") or {}
            ),
        }
        normalized["evidence_refs"] = [
            str(reference)
            for reference in (explicit_payload.get("evidence_refs") or [])
            if isinstance(reference, (str, int, float)) and str(reference)
        ]
        return normalized

    if code_quality is not None:
        normalized["collection_state"] = "metadata_only"
        normalized["source"] = "workflow_payload.code_quality"
        codeql_category = code_quality.get("codeql_category")
        if isinstance(codeql_category, str) and codeql_category:
            normalized["codeql_category"] = codeql_category
    return normalized


def _validate_security_findings(security_findings: Any, errors: list[str]) -> None:
    if not isinstance(security_findings, dict):
        errors.append("security_findings_invalid")
        return

    if security_findings.get("collection_state") not in ALLOWED_SECURITY_COLLECTION_STATES:
        errors.append("security_findings_collection_state_invalid")
    source = security_findings.get("source")
    if source is not None and (not isinstance(source, str) or not source):
        errors.append("security_findings_source_invalid")
    if not isinstance(security_findings.get("tool"), str) or not security_findings.get("tool"):
        errors.append("security_findings_tool_invalid")
    codeql_category = security_findings.get("codeql_category")
    if codeql_category is not None and (
        not isinstance(codeql_category, str) or not codeql_category
    ):
        errors.append("security_findings_codeql_category_invalid")
    if not isinstance(security_findings.get("alerts_available"), bool):
        errors.append("security_findings_alerts_available_invalid")

    summary = security_findings.get("summary")
    if not isinstance(summary, dict):
        errors.append("security_findings_summary_invalid")
    else:
        for field_name in ("total_alerts", "open_alerts", "closed_alerts"):
            field_value = summary.get(field_name)
            if field_value is not None and _normalize_optional_int(field_value) is None:
                errors.append(f"security_findings_{field_name}_invalid")
        for field_name in ("severity_counts", "state_counts"):
            field_value = summary.get(field_name)
            if not isinstance(field_value, dict):
                errors.append(f"security_findings_{field_name}_invalid")
                continue
            for key, count in field_value.items():
                if not isinstance(key, str) or not key or _normalize_optional_int(count) is None:
                    errors.append(f"security_findings_{field_name}_invalid")
                    break

    evidence_refs = security_findings.get("evidence_refs")
    if not isinstance(evidence_refs, list) or any(
        not isinstance(reference, str) or not reference for reference in evidence_refs
    ):
        errors.append("security_findings_evidence_refs_invalid")


def append_weekly_artifact_decision(
    artifact: dict[str, Any],
    *,
    decision: str,
    actor: str,
    rationale: str,
    triage_lane: str | None = None,
    evidence_refs: list[str] | None = None,
    supersedes: str | None = None,
    policy_basis: list[str] | None = None,
) -> dict[str, Any]:
    if decision not in ALLOWED_DECISION_TYPES:
        raise ValueError(f"unsupported decision: {decision}")
    if triage_lane is not None and triage_lane not in ALLOWED_TRIAGE_LANES:
        raise ValueError(f"unsupported triage lane: {triage_lane}")

    status_after = decision
    decided_at = _utc_now()
    artifact_id = str(artifact.get("artifact_id") or "unknown_artifact")
    decision_id = hashlib.sha256(
        _stable_json(
            {
                "artifact_id": artifact_id,
                "decision": decision,
                "actor": actor,
                "rationale": rationale,
                "decided_at": decided_at,
            }
        ).encode("utf-8")
    ).hexdigest()[:16]

    records = list(artifact.get("decision_records") or [])
    records.append(
        {
            "decision_id": decision_id,
            "decision": decision,
            "status_after": status_after,
            "decided_at": decided_at,
            "actor": actor,
            "rationale": rationale,
            "triage_lane": triage_lane,
            "evidence_refs": list(evidence_refs or []),
            "policy_basis": list(policy_basis or []),
            "supersedes": supersedes,
        }
    )

    evidence_contract = dict(artifact.get("evidence_contract") or {})
    evidence_contract["promotion_state"] = _promotion_state_for_status(status_after)
    evidence_contract["current_status"] = status_after
    evidence_contract["triage_lane"] = triage_lane
    evidence_contract["decision_count"] = len(records)
    evidence_contract["supersedes"] = supersedes

    artifact["artifact_status"] = status_after
    artifact["decision_records"] = records
    artifact["evidence_contract"] = evidence_contract
    artifact["distribution_contract"] = _default_distribution_contract(status_after)
    return artifact


def iter_weekly_artifact_history(metrics_dir: Path | None = None) -> list[dict[str, Any]]:
    effective_metrics_dir = _coerce_metrics_dir(metrics_dir)
    history_path = effective_metrics_dir / WEEKLY_HISTORY_ARTIFACT
    if not history_path.exists():
        return []

    artifacts: list[dict[str, Any]] = []
    for raw_line in history_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            artifacts.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return artifacts


def load_verified_weekly_artifacts(
    metrics_dir: Path | None = None,
    *,
    status: str | None = None,
    source: str | None = None,
    decision: str | None = None,
    verified_only: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    artifacts = iter_weekly_artifact_history(metrics_dir)
    filtered: list[dict[str, Any]] = []
    for artifact in reversed(artifacts):
        verification = artifact.get("verification") or {}
        if verified_only and not verification.get("verified", False):
            continue
        if status is not None and artifact.get("artifact_status") != status:
            continue
        if source is not None and artifact.get("source") != source:
            continue
        if decision is not None:
            decisions = {
                record.get("decision") for record in artifact.get("decision_records") or []
            }
            if decision not in decisions:
                continue
        filtered.append(artifact)
        if limit is not None and len(filtered) >= limit:
            break
    return filtered


def find_weekly_artifact(
    artifact_id: str, metrics_dir: Path | None = None
) -> dict[str, Any] | None:
    for artifact in load_verified_weekly_artifacts(metrics_dir, verified_only=False):
        if artifact.get("artifact_id") == artifact_id:
            return artifact
    return None


def read_latest_weekly_artifact(metrics_dir: Path | None = None) -> dict[str, Any] | None:
    latest_path = _coerce_metrics_dir(metrics_dir) / WEEKLY_LATEST_ARTIFACT
    if not latest_path.exists():
        return None
    return json.loads(latest_path.read_text(encoding="utf-8"))


def persist_weekly_artifact(
    artifact: dict[str, Any], metrics_dir: Path | None = None
) -> dict[str, Any]:
    effective_metrics_dir = _coerce_metrics_dir(metrics_dir)
    effective_metrics_dir.mkdir(parents=True, exist_ok=True)

    verification_report = validate_weekly_artifact(artifact)
    if not verification_report.get("verified"):
        raise ValueError(f"weekly artifact verification failed: {verification_report['errors']}")

    verified_artifact = attach_weekly_artifact_verification(dict(artifact), verification_report)
    latest_path = effective_metrics_dir / WEEKLY_LATEST_ARTIFACT
    latest_path.write_text(json.dumps(verified_artifact, indent=2), encoding="utf-8")

    history_path = effective_metrics_dir / WEEKLY_HISTORY_ARTIFACT
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(verified_artifact) + "\n")
    return verified_artifact


def record_weekly_artifact_decision(
    *,
    artifact_id: str,
    metrics_dir: Path | None = None,
    decision: str,
    actor: str,
    rationale: str,
    triage_lane: str | None = None,
    evidence_refs: list[str] | None = None,
    supersedes: str | None = None,
    policy_basis: list[str] | None = None,
) -> dict[str, Any]:
    artifact = find_weekly_artifact(artifact_id, metrics_dir)
    if artifact is None:
        raise FileNotFoundError(f"weekly artifact not found: {artifact_id}")

    updated_artifact = append_weekly_artifact_decision(
        dict(artifact),
        decision=decision,
        actor=actor,
        rationale=rationale,
        triage_lane=triage_lane,
        evidence_refs=evidence_refs,
        supersedes=supersedes,
        policy_basis=policy_basis,
    )
    verified_artifact = persist_weekly_artifact(updated_artifact, metrics_dir)

    latest_artifact = read_latest_weekly_artifact(metrics_dir)
    if latest_artifact and latest_artifact.get("artifact_id") != artifact_id:
        latest_path = _coerce_metrics_dir(metrics_dir) / WEEKLY_LATEST_ARTIFACT
        latest_path.write_text(json.dumps(latest_artifact, indent=2), encoding="utf-8")
    return verified_artifact


def summarize_weekly_artifacts(metrics_dir: Path | None = None) -> dict[str, Any]:
    artifacts = iter_weekly_artifact_history(metrics_dir)
    status_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    verified_count = 0
    distributable_count = 0

    for artifact in artifacts:
        status_value = str(artifact.get("artifact_status") or "unknown")
        source_value = str(artifact.get("source") or "unknown")
        status_counts[status_value] = status_counts.get(status_value, 0) + 1
        source_counts[source_value] = source_counts.get(source_value, 0) + 1
        if (artifact.get("verification") or {}).get("verified"):
            verified_count += 1
        if (artifact.get("distribution_contract") or {}).get("eligible_for_governed_distribution"):
            distributable_count += 1

    return {
        "artifact_count": len(artifacts),
        "verified_count": verified_count,
        "distribution_eligible_count": distributable_count,
        "status_counts": status_counts,
        "source_counts": source_counts,
        "history_path": str(_coerce_metrics_dir(metrics_dir) / WEEKLY_HISTORY_ARTIFACT),
    }


def _source_type_for_weekly_artifact(source: str) -> str:
    if source == "local-scheduled":
        return "scheduled_pipeline"
    if source.startswith("weekly-"):
        return "workflow_weekly"
    return "manual_artifact"


def _build_weekly_provenance(
    *,
    source: str,
    generated_at: str,
    workflow_run_url: str | None,
    git_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_type": _source_type_for_weekly_artifact(source),
        "source": source,
        "collector": "hlf_mcp.weekly_artifacts",
        "collected_at": generated_at,
        "workflow_run_url": workflow_run_url,
        "branch": git_context.get("branch"),
        "commit_sha": git_context.get("commit_sha"),
        "artifact_path": None,
        "confidence": 1.0,
    }


def validate_weekly_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    expected_top_level = [
        "artifact_id",
        "artifact_status",
        "schema_version",
        "generated_at",
        "source",
        "collector",
        "git",
        "governance",
        "server_surface",
        "provenance",
        "evidence_contract",
        "decision_records",
        "distribution_contract",
        "security_findings",
        "governed_review",
    ]
    for key in expected_top_level:
        if key not in artifact:
            errors.append(f"missing_top_level:{key}")

    if artifact.get("schema_version") != WEEKLY_ARTIFACT_SCHEMA_VERSION:
        errors.append(
            f"schema_version_mismatch:{artifact.get('schema_version')}!={WEEKLY_ARTIFACT_SCHEMA_VERSION}"
        )

    collector = artifact.get("collector") or {}
    if collector.get("name") != "hlf_mcp.weekly_artifacts":
        errors.append("collector_name_invalid")
    if collector.get("version") != WEEKLY_ARTIFACT_COLLECTOR_VERSION:
        errors.append("collector_version_invalid")

    git_context = artifact.get("git") or {}
    provenance = artifact.get("provenance") or {}
    governance = artifact.get("governance") or {}
    evidence_contract = artifact.get("evidence_contract") or {}
    server_surface = artifact.get("server_surface") or {}
    decision_records = artifact.get("decision_records") or []
    distribution_contract = artifact.get("distribution_contract") or {}
    security_findings = artifact.get("security_findings")
    governed_review = artifact.get("governed_review")

    if not isinstance(artifact.get("artifact_id"), str) or not artifact.get("artifact_id"):
        errors.append("artifact_id_invalid")
    artifact_status = artifact.get("artifact_status")
    if artifact_status not in ALLOWED_ARTIFACT_STATUSES:
        errors.append("artifact_status_invalid")

    if provenance.get("source") != artifact.get("source"):
        errors.append("provenance_source_mismatch")
    if provenance.get("collected_at") != artifact.get("generated_at"):
        errors.append("provenance_collected_at_mismatch")
    if provenance.get("branch") != git_context.get("branch"):
        errors.append("provenance_branch_mismatch")
    if provenance.get("commit_sha") != git_context.get("commit_sha"):
        errors.append("provenance_commit_sha_mismatch")

    confidence = provenance.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        errors.append("provenance_confidence_invalid")

    if evidence_contract.get("intake_state") != "advisory":
        errors.append("evidence_contract_intake_state_invalid")
    if evidence_contract.get("promotion_state") not in {
        "requires_verification",
        "approved_for_distribution",
        "rejected",
    }:
        errors.append("evidence_contract_promotion_state_invalid")
    if evidence_contract.get("collector_version") != WEEKLY_ARTIFACT_COLLECTOR_VERSION:
        errors.append("evidence_contract_collector_version_invalid")
    if evidence_contract.get("manifest_sha256") != governance.get("manifest_sha256"):
        errors.append("evidence_contract_manifest_sha256_mismatch")
    if evidence_contract.get("confidence") != confidence:
        errors.append("evidence_contract_confidence_mismatch")
    if evidence_contract.get("current_status") != artifact_status:
        errors.append("evidence_contract_current_status_mismatch")
    if evidence_contract.get("decision_count") != len(decision_records):
        errors.append("evidence_contract_decision_count_mismatch")

    if not isinstance(decision_records, list):
        errors.append("decision_records_invalid")
    else:
        for index, record in enumerate(decision_records):
            if not isinstance(record, dict):
                errors.append(f"decision_record[{index}]_not_object")
                continue
            _validate_decision_record(record, index, errors)
        if decision_records:
            last_status = decision_records[-1].get("status_after")
            if last_status != artifact_status:
                errors.append("decision_records_last_status_mismatch")

    if not isinstance(distribution_contract.get("requires_source_compliance"), bool):
        errors.append("distribution_contract_requires_source_compliance_invalid")
    if not isinstance(distribution_contract.get("eligible_for_governed_distribution"), bool):
        errors.append("distribution_contract_eligible_invalid")
    if not isinstance(
        distribution_contract.get("target_class"), str
    ) or not distribution_contract.get("target_class"):
        errors.append("distribution_contract_target_class_invalid")
    if not isinstance(
        distribution_contract.get("governor_surface"), str
    ) or not distribution_contract.get("governor_surface"):
        errors.append("distribution_contract_governor_surface_invalid")
    if not isinstance(
        distribution_contract.get("compliance_surface"), str
    ) or not distribution_contract.get("compliance_surface"):
        errors.append("distribution_contract_compliance_surface_invalid")
    if not isinstance(
        distribution_contract.get("eligibility_reason"), str
    ) or not distribution_contract.get("eligibility_reason"):
        errors.append("distribution_contract_eligibility_reason_invalid")
    if artifact_status != "promoted" and distribution_contract.get(
        "eligible_for_governed_distribution"
    ):
        errors.append("distribution_contract_promoted_state_mismatch")

    _validate_security_findings(security_findings, errors)
    validate_governed_review(governed_review, errors)

    if governance.get("manifest_present") and not governance.get("manifest_sha256"):
        errors.append("manifest_present_without_sha256")

    if server_surface.get("registered_tool_count") is None:
        errors.append("registered_tool_count_missing")
    if server_surface.get("registered_resource_count") is None:
        errors.append("registered_resource_count_missing")

    source_type = provenance.get("source_type")
    if source_type == "workflow_weekly" and not provenance.get("workflow_run_url"):
        warnings.append("workflow_artifact_missing_run_url")
    if artifact_status == "promoted" and not decision_records:
        warnings.append("promoted_artifact_missing_decision_history")
    if artifact.get("source") == "weekly-code-quality" and isinstance(security_findings, dict):
        if security_findings.get("collection_state") == "not_collected":
            warnings.append("weekly_code_quality_missing_security_findings")
    if artifact.get("source") == "weekly-evolution-planner" and isinstance(governed_review, dict):
        if governed_review.get("automation_status") != "generated":
            warnings.append("weekly_evolution_planner_missing_governed_review")
    if artifact.get("source") == "weekly-model-drift-detect" and isinstance(governed_review, dict):
        if governed_review.get("automation_status") != "generated":
            warnings.append("weekly_model_drift_missing_governed_review")

    return {
        "verified": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked_schema_version": WEEKLY_ARTIFACT_SCHEMA_VERSION,
    }


def attach_weekly_artifact_verification(
    artifact: dict[str, Any],
    verification_report: dict[str, Any],
) -> dict[str, Any]:
    artifact["verification"] = {
        "verified": bool(verification_report.get("verified")),
        "checked_at": _utc_now(),
        "errors": list(verification_report.get("errors") or []),
        "warnings": list(verification_report.get("warnings") or []),
        "checked_schema_version": verification_report.get("checked_schema_version"),
    }
    return artifact


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _git_output(repo_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def collect_git_context(repo_root: Path) -> dict[str, Any]:
    return {
        "branch": _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "commit_sha": _git_output(repo_root, "rev-parse", "HEAD"),
        "commit_short_sha": _git_output(repo_root, "rev-parse", "--short", "HEAD"),
        "status_porcelain": (_git_output(repo_root, "status", "--short") or "").splitlines(),
    }


def _parse_manifest_entries(manifest_path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            expected[parts[1]] = parts[0]
    return expected


def collect_governance_manifest_snapshot(repo_root: Path) -> dict[str, Any]:
    governance_dir = repo_root / "governance"
    manifest_path = governance_dir / "MANIFEST.sha256"
    if not manifest_path.exists():
        return {
            "manifest_present": False,
            "manifest_path": str(manifest_path),
            "manifest_sha256": None,
            "entry_count": 0,
            "drift": ["MANIFEST.sha256 missing"],
        }

    manifest_entries = _parse_manifest_entries(manifest_path)
    drift: list[str] = []
    for relative_path, expected_hash in manifest_entries.items():
        target_path = governance_dir / relative_path
        if not target_path.exists():
            drift.append(f"{relative_path}: missing")
            continue
        actual_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            drift.append(f"{relative_path}: hash mismatch")

    return {
        "manifest_present": True,
        "manifest_path": str(manifest_path),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "entry_count": len(manifest_entries),
        "drift": drift,
    }


def collect_server_surface() -> dict[str, Any]:
    from hlf_mcp import server

    exported = sorted(
        name for name in dir(server) if name.startswith("hlf_") and callable(getattr(server, name))
    )
    instructions = server.mcp.instructions or ""
    return {
        "registered_tool_count": len(server.REGISTERED_TOOLS),
        "registered_resource_count": len(server.REGISTERED_RESOURCES),
        "exported_callable_count": len(exported),
        "registered_tools": sorted(server.REGISTERED_TOOLS),
        "registered_resources": sorted(server.REGISTERED_RESOURCES),
        "exported_callables": exported,
        "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
    }


def read_latest_suite_summary(metrics_dir: Path | None = None) -> dict[str, Any] | None:
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    summary_path = effective_metrics_dir / LATEST_SUMMARY_FILE
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def run_toolkit_command(repo_root: Path, command: str = "status") -> dict[str, Any]:
    toolkit_path = repo_root / "_toolkit.py"
    if not toolkit_path.exists():
        return {
            "attempted": False,
            "command": command,
            "reason": "_toolkit.py not present",
        }

    completed = subprocess.run(
        [sys.executable, str(toolkit_path), command],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "attempted": True,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def build_weekly_artifact(
    *,
    repo_root: Path,
    metrics_dir: Path | None = None,
    source: str,
    workflow_run_url: str | None = None,
    toolkit_command: str | None = None,
    latest_suite_summary: dict[str, Any] | None = None,
    workflow_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    effective_metrics_dir = metrics_dir or DEFAULT_METRICS_DIR
    generated_at = _utc_now()
    git_context = collect_git_context(repo_root)
    governance_snapshot = collect_governance_manifest_snapshot(repo_root)
    artifact_id = _compute_weekly_artifact_id(
        source=source,
        generated_at=generated_at,
        git_context=git_context,
    )
    provenance = _build_weekly_provenance(
        source=source,
        generated_at=generated_at,
        workflow_run_url=workflow_run_url,
        git_context=git_context,
    )
    artifact_status = "advisory"
    artifact = {
        "artifact_id": artifact_id,
        "artifact_status": artifact_status,
        "schema_version": WEEKLY_ARTIFACT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": source,
        "workflow_run_url": workflow_run_url,
        "collector": {
            "name": "hlf_mcp.weekly_artifacts",
            "python": sys.version.split()[0],
            "version": WEEKLY_ARTIFACT_COLLECTOR_VERSION,
        },
        "repo_root": str(repo_root),
        "metrics_dir": str(effective_metrics_dir),
        "git": git_context,
        "governance": governance_snapshot,
        "server_surface": collect_server_surface(),
        "provenance": provenance,
        "evidence_contract": {
            "intake_state": "advisory",
            "promotion_state": _promotion_state_for_status(artifact_status),
            "requires_operator_or_policy_gate": True,
            "confidence": provenance["confidence"],
            "manifest_sha256": governance_snapshot.get("manifest_sha256"),
            "collector_version": WEEKLY_ARTIFACT_COLLECTOR_VERSION,
            "current_status": artifact_status,
            "triage_lane": None,
            "decision_count": 0,
            "supersedes": None,
        },
        "decision_records": [],
        "distribution_contract": _default_distribution_contract(artifact_status),
        "security_findings": _normalize_security_findings(workflow_payload),
        "governed_review": normalize_governed_review(
            (workflow_payload or {}).get("governed_review"),
            source=source,
        ),
        "latest_suite_summary": latest_suite_summary
        if latest_suite_summary is not None
        else read_latest_suite_summary(effective_metrics_dir),
    }
    if toolkit_command:
        artifact["toolkit"] = run_toolkit_command(repo_root, toolkit_command)
    if workflow_payload is not None:
        artifact["workflow_payload"] = workflow_payload
    return artifact


def build_hks_exemplar_from_weekly_artifact(
    artifact: dict[str, Any],
    *,
    artifact_path: Path | None = None,
) -> HKSValidatedExemplar | None:
    verification = artifact.get("verification") or {}
    if verification and not verification.get("verified"):
        return None

    latest_suite_summary = artifact.get("latest_suite_summary") or {}
    if not latest_suite_summary or not latest_suite_summary.get("passed"):
        return None

    provenance_payload = artifact.get("provenance") or {}
    scheduled_pipeline = artifact.get("scheduled_pipeline") or {}
    server_surface = artifact.get("server_surface") or {}
    governance = artifact.get("governance") or {}
    security_findings = artifact.get("security_findings") or {}
    security_summary = security_findings.get("summary") or {}
    counts = latest_suite_summary.get("counts") or {}
    toolkit_command = scheduled_pipeline.get("toolkit_command")
    validated_solution = json.dumps(
        {
            "suite_passed": True,
            "counts": counts,
            "registered_tool_count": server_surface.get("registered_tool_count"),
            "registered_resource_count": server_surface.get("registered_resource_count"),
            "governance_drift": governance.get("drift", []),
            "toolkit_command": toolkit_command,
            "security_findings": {
                "collection_state": security_findings.get("collection_state"),
                "tool": security_findings.get("tool"),
                "codeql_category": security_findings.get("codeql_category"),
                "total_alerts": security_summary.get("total_alerts"),
                "open_alerts": security_summary.get("open_alerts"),
            },
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    summary = (
        f"Weekly pipeline passed with {counts.get('passed', 0)} passing tests, "
        f"{server_surface.get('registered_tool_count', 0)} registered tools, and "
        f"{len(governance.get('drift', []))} governance drift findings."
    )
    return HKSValidatedExemplar(
        problem="How to validate and persist the local HLF weekly pipeline state.",
        validated_solution=validated_solution,
        domain="hlf-specific",
        solution_kind="weekly-pipeline",
        provenance=HKSProvenance(
            source_type=str(provenance_payload.get("source_type") or "scheduled_pipeline"),
            source=str(
                provenance_payload.get("source") or artifact.get("source") or "local-scheduled"
            ),
            collector=str(provenance_payload.get("collector") or "scripts.run_pipeline_scheduled"),
            collected_at=str(
                provenance_payload.get("collected_at") or artifact.get("generated_at") or _utc_now()
            ),
            workflow_run_url=provenance_payload.get("workflow_run_url")
            or artifact.get("workflow_run_url"),
            branch=provenance_payload.get("branch"),
            commit_sha=provenance_payload.get("commit_sha"),
            artifact_path=str(artifact_path) if artifact_path else None,
            confidence=float(provenance_payload.get("confidence") or 1.0),
        ),
        tests=[
            HKSTestEvidence(
                name="pytest_default_suite",
                passed=True,
                exit_code=int(latest_suite_summary.get("exit_code", 0)),
                counts=counts,
                details={
                    "duration_ms": latest_suite_summary.get("duration_ms"),
                    "toolkit_command": toolkit_command,
                },
            )
        ],
        topic="hlf_weekly_validated_runs",
        tags=["weekly", "pipeline", "validated", "hks"],
        summary=summary,
        confidence=float(provenance_payload.get("confidence") or 1.0),
    )
