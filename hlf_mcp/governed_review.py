from __future__ import annotations

import json
from typing import Any

from hlf_mcp.persona_contract import resolve_persona_contract, validate_persona_contract

REVIEW_CONTRACT_VERSION = "1.0"

ALLOWED_REVIEW_SEVERITIES = {"info", "warning", "critical"}
ALLOWED_AUTOMATION_STATUSES = {"generated", "not_collected"}
ALLOWED_PILLAR_STATUSES = {"advance", "watch", "risk", "blocked"}
ALLOWED_ACTION_PRIORITIES = {"P1", "P2", "P3"}
ALLOWED_ACTION_EFFORTS = {"small", "medium", "large"}
ALLOWED_IMPLEMENTATION_LANES = {"vision", "current_truth", "bridge"}
ALLOWED_REVIEW_TYPES = {"weekly_artifact", "evolution_planning", "model_drift"}
ALLOWED_TRIAGE_LANES = {
    "ignore",
    "backlog",
    "current_batch",
    "future_batch",
    "doctrine_only",
}

SEVEN_PILLARS = [
    "Deterministic language core",
    "Governance-native execution",
    "Formal verification surface",
    "Gateway and routing fabric",
    "Orchestration lifecycle and plan execution",
    "HLF knowledge substrate and governed memory",
    "Human-readable audit and trust layer",
]

DRIFT_CATEGORY_TO_PILLAR = {
    "grammar": "Deterministic language core",
    "bytecode": "Deterministic language core",
    "security": "Governance-native execution",
    "ethos": "Human-readable audit and trust layer",
    "vm": "Governance-native execution",
    "instinct": "Orchestration lifecycle and plan execution",
    "crypto": "Governance-native execution",
}


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float)) and str(item)]


def _normalize_backend(value: Any) -> dict[str, Any]:
    backend = value if isinstance(value, dict) else {}
    fallback_chain = _as_string_list(backend.get("fallback_chain"))
    tier_index = backend.get("tier_index")
    if not isinstance(tier_index, int):
        tier_index = None
    return {
        "provider": backend.get("provider") if isinstance(backend.get("provider"), str) else None,
        "access_mode": backend.get("access_mode")
        if isinstance(backend.get("access_mode"), str)
        else None,
        "model": backend.get("model") if isinstance(backend.get("model"), str) else None,
        "tier_index": tier_index,
        "fallback_chain": fallback_chain,
    }


def _normalize_pillar_assessment(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    pillar = value.get("pillar")
    status = value.get("status")
    rationale = value.get("rationale")
    if not isinstance(pillar, str) or not pillar:
        return None
    if not isinstance(status, str) or status not in ALLOWED_PILLAR_STATUSES:
        return None
    if not isinstance(rationale, str) or not rationale:
        return None
    return {
        "pillar": pillar,
        "status": status,
        "rationale": rationale,
        "evidence_refs": _as_string_list(value.get("evidence_refs")),
    }


def _normalize_action(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    title = value.get("title")
    priority = value.get("priority")
    effort = value.get("effort")
    lane = value.get("lane")
    rationale = value.get("rationale")
    if not isinstance(title, str) or not title:
        return None
    if not isinstance(priority, str) or priority not in ALLOWED_ACTION_PRIORITIES:
        return None
    if not isinstance(effort, str) or effort not in ALLOWED_ACTION_EFFORTS:
        return None
    if not isinstance(lane, str) or lane not in ALLOWED_IMPLEMENTATION_LANES:
        return None
    if not isinstance(rationale, str) or not rationale:
        return None
    return {
        "title": title,
        "priority": priority,
        "effort": effort,
        "lane": lane,
        "rationale": rationale,
        "target_files": _as_string_list(value.get("target_files")),
    }


def default_governed_review(*, source: str | None = None) -> dict[str, Any]:
    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": f"No governed review contract was attached for {source or 'this artifact'}.",
        "severity": "info",
        "automation_status": "not_collected",
        "operator_gate_required": True,
        "recommended_triage_lane": None,
        "backend": {
            "provider": None,
            "access_mode": None,
            "model": None,
            "tier_index": None,
            "fallback_chain": [],
        },
        "pillar_assessments": [],
        "recommended_actions": [],
        "evidence_refs": [],
        "escalation_triggers": [],
        "review_metadata": {"source": source},
    }
    review.update(
        resolve_persona_contract(
            source=source,
            review_type=review["review_type"],
            severity=review["severity"],
            recommended_triage_lane=review["recommended_triage_lane"],
            existing=review,
        )
    )
    return review


def normalize_governed_review(value: Any, *, source: str | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return default_governed_review(source=source)

    normalized = default_governed_review(source=source)
    normalized["contract_version"] = (
        value.get("contract_version")
        if isinstance(value.get("contract_version"), str)
        else REVIEW_CONTRACT_VERSION
    )

    review_type = value.get("review_type")
    if isinstance(review_type, str) and review_type:
        normalized["review_type"] = review_type

    summary = value.get("summary")
    if isinstance(summary, str) and summary:
        normalized["summary"] = summary

    severity = value.get("severity")
    if isinstance(severity, str) and severity in ALLOWED_REVIEW_SEVERITIES:
        normalized["severity"] = severity

    automation_status = value.get("automation_status")
    if isinstance(automation_status, str) and automation_status in ALLOWED_AUTOMATION_STATUSES:
        normalized["automation_status"] = automation_status

    if isinstance(value.get("operator_gate_required"), bool):
        normalized["operator_gate_required"] = value["operator_gate_required"]

    triage_lane = value.get("recommended_triage_lane")
    if triage_lane in ALLOWED_TRIAGE_LANES:
        normalized["recommended_triage_lane"] = triage_lane

    normalized["backend"] = _normalize_backend(value.get("backend"))
    normalized["pillar_assessments"] = [
        assessment
        for assessment in (
            _normalize_pillar_assessment(item) for item in (value.get("pillar_assessments") or [])
        )
        if assessment is not None
    ]
    normalized["recommended_actions"] = [
        action
        for action in (_normalize_action(item) for item in (value.get("recommended_actions") or []))
        if action is not None
    ]
    normalized["evidence_refs"] = _as_string_list(value.get("evidence_refs"))
    normalized["escalation_triggers"] = _as_string_list(value.get("escalation_triggers"))

    metadata = value.get("review_metadata")
    normalized["review_metadata"] = metadata if isinstance(metadata, dict) else {"source": source}

    normalized.update(
        resolve_persona_contract(
            source=source,
            review_type=normalized.get("review_type"),
            severity=normalized.get("severity"),
            recommended_triage_lane=normalized.get("recommended_triage_lane"),
            existing=normalized,
        )
    )
    return normalized


def validate_governed_review(review: Any, errors: list[str]) -> None:
    if not isinstance(review, dict):
        errors.append("governed_review_invalid")
        return

    if review.get("contract_version") != REVIEW_CONTRACT_VERSION:
        errors.append("governed_review_contract_version_invalid")
    if review.get("review_type") not in ALLOWED_REVIEW_TYPES:
        errors.append("governed_review_review_type_invalid")
    if not isinstance(review.get("summary"), str) or not review.get("summary"):
        errors.append("governed_review_summary_invalid")
    if review.get("severity") not in ALLOWED_REVIEW_SEVERITIES:
        errors.append("governed_review_severity_invalid")
    if review.get("automation_status") not in ALLOWED_AUTOMATION_STATUSES:
        errors.append("governed_review_automation_status_invalid")
    if not isinstance(review.get("operator_gate_required"), bool):
        errors.append("governed_review_operator_gate_required_invalid")

    triage_lane = review.get("recommended_triage_lane")
    if triage_lane is not None and triage_lane not in ALLOWED_TRIAGE_LANES:
        errors.append("governed_review_recommended_triage_lane_invalid")

    backend = review.get("backend")
    if not isinstance(backend, dict):
        errors.append("governed_review_backend_invalid")
    else:
        for field_name in ("provider", "access_mode", "model"):
            field_value = backend.get(field_name)
            if field_value is not None and (not isinstance(field_value, str) or not field_value):
                errors.append(f"governed_review_backend_{field_name}_invalid")
        tier_index = backend.get("tier_index")
        if tier_index is not None and not isinstance(tier_index, int):
            errors.append("governed_review_backend_tier_index_invalid")
        fallback_chain = backend.get("fallback_chain")
        if not isinstance(fallback_chain, list) or any(
            not isinstance(item, str) or not item for item in fallback_chain
        ):
            errors.append("governed_review_backend_fallback_chain_invalid")

    pillar_assessments = review.get("pillar_assessments")
    if not isinstance(pillar_assessments, list):
        errors.append("governed_review_pillar_assessments_invalid")
    else:
        for index, assessment in enumerate(pillar_assessments):
            if _normalize_pillar_assessment(assessment) is None:
                errors.append(f"governed_review_pillar_assessment[{index}]_invalid")

    recommended_actions = review.get("recommended_actions")
    if not isinstance(recommended_actions, list):
        errors.append("governed_review_recommended_actions_invalid")
    else:
        for index, action in enumerate(recommended_actions):
            if _normalize_action(action) is None:
                errors.append(f"governed_review_recommended_action[{index}]_invalid")

    for field_name in ("evidence_refs", "escalation_triggers"):
        field_value = review.get(field_name)
        if not isinstance(field_value, list) or any(
            not isinstance(item, str) or not item for item in field_value
        ):
            errors.append(f"governed_review_{field_name}_invalid")

    if not isinstance(review.get("review_metadata"), dict):
        errors.append("governed_review_review_metadata_invalid")

    validate_persona_contract(review, errors)


def _backend_from_ollama_payload(
    payload: dict[str, Any], *, default_provider: str = "ollama_cloud"
) -> dict[str, Any]:
    fallback_chain: list[str] = []
    for entry in payload.get("audit_trail") or []:
        if isinstance(entry, dict):
            model = entry.get("model")
            if isinstance(model, str) and model and model not in fallback_chain:
                fallback_chain.append(model)
    if not fallback_chain:
        requested = payload.get("model_requested")
        used = payload.get("model") or payload.get("modelUsed")
        fallback_chain = [model for model in (requested, used) if isinstance(model, str) and model]
    return {
        "provider": default_provider,
        "access_mode": "cloud-via-ollama",
        "model": payload.get("model") or payload.get("modelUsed"),
        "tier_index": payload.get("tier_index")
        if isinstance(payload.get("tier_index"), int)
        else payload.get("tier"),
        "fallback_chain": fallback_chain,
    }


def evolution_plan_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string"},
            "severity": {"type": "string", "enum": sorted(ALLOWED_REVIEW_SEVERITIES)},
            "recommended_triage_lane": {
                "type": "string",
                "enum": sorted(ALLOWED_TRIAGE_LANES - {"ignore"}),
            },
            "top_priority_index": {"type": "integer", "minimum": 0, "maximum": 6},
            "pillar_assessments": {
                "type": "array",
                "minItems": 7,
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "pillar": {"type": "string", "enum": SEVEN_PILLARS},
                        "status": {"type": "string", "enum": sorted(ALLOWED_PILLAR_STATUSES)},
                        "rationale": {"type": "string"},
                    },
                    "required": ["pillar", "status", "rationale"],
                },
            },
            "evolution_items": {
                "type": "array",
                "minItems": 7,
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "title": {"type": "string"},
                        "why": {"type": "string"},
                        "impact": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "impact_metric": {"type": "string"},
                        "effort": {"type": "string", "enum": ["small", "medium", "large"]},
                        "priority": {"type": "string", "enum": sorted(ALLOWED_ACTION_PRIORITIES)},
                        "lane": {"type": "string", "enum": sorted(ALLOWED_IMPLEMENTATION_LANES)},
                        "phase": {"type": "string"},
                        "pillar": {"type": "string", "enum": SEVEN_PILLARS},
                        "first_step_file": {"type": "string"},
                        "first_step_function": {"type": "string"},
                    },
                    "required": [
                        "title",
                        "why",
                        "impact",
                        "impact_metric",
                        "effort",
                        "priority",
                        "lane",
                        "phase",
                        "pillar",
                        "first_step_file",
                        "first_step_function",
                    ],
                },
            },
            "escalation_triggers": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "summary",
            "severity",
            "recommended_triage_lane",
            "top_priority_index",
            "pillar_assessments",
            "evolution_items",
            "escalation_triggers",
        ],
    }


def _load_response_content(payload: dict[str, Any]) -> dict[str, Any]:
    content = payload.get("content")
    if isinstance(content, dict):
        return content
    if isinstance(content, str) and content.strip():
        return json.loads(content)
    raise ValueError("response payload missing structured content")


def build_evolution_governed_review(
    plan_payload: dict[str, Any],
    *,
    code_starter_payload: dict[str, Any] | None = None,
    focus_area: str | None = None,
) -> dict[str, Any]:
    plan = _load_response_content(plan_payload)
    items = list(plan.get("evolution_items") or [])
    top_priority_index = int(plan.get("top_priority_index", 0)) if items else 0
    top_priority_index = min(max(top_priority_index, 0), max(len(items) - 1, 0))
    top_priority = items[top_priority_index] if items else {}

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "evolution_planning",
        "summary": plan.get("summary") or "Weekly evolution planning review generated.",
        "severity": plan.get("severity") or "info",
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": plan.get("recommended_triage_lane"),
        "backend": _backend_from_ollama_payload(plan_payload),
        "pillar_assessments": [
            {
                "pillar": item["pillar"],
                "status": item["status"],
                "rationale": item["rationale"],
                "evidence_refs": ["workflow_payload.evolution_plan"],
            }
            for item in plan.get("pillar_assessments") or []
            if isinstance(item, dict)
        ],
        "recommended_actions": [
            {
                "title": item["title"],
                "priority": item["priority"],
                "effort": item["effort"],
                "lane": item["lane"],
                "rationale": item["why"],
                "target_files": [item["first_step_file"]],
            }
            for item in items
            if isinstance(item, dict)
        ],
        "evidence_refs": [
            "workflow_payload.ethics_report",
            "workflow_payload.evolution_plan",
            "workflow_payload.code_starter",
        ],
        "escalation_triggers": _as_string_list(plan.get("escalation_triggers")),
        "review_metadata": {
            "focus_area": focus_area,
            "top_priority_index": top_priority_index,
            "top_priority_title": top_priority.get("title"),
            "top_priority_file": top_priority.get("first_step_file"),
            "top_priority_function": top_priority.get("first_step_function"),
            "planner_model": plan_payload.get("model"),
            "code_starter_model": (code_starter_payload or {}).get("model"),
        },
    }
    return normalize_governed_review(review, source="weekly-evolution-planner")


def build_model_drift_governed_review(drift_payload: dict[str, Any]) -> dict[str, Any]:
    status = drift_payload.get("status") or "ALERT"
    severity = {"OK": "info", "WARN": "warning", "ALERT": "critical"}.get(status, "critical")
    recommended_triage_lane = {"OK": "ignore", "WARN": "backlog", "ALERT": "current_batch"}.get(
        status
    )

    probes = list(drift_payload.get("probes") or [])
    pillar_rollup: dict[str, dict[str, Any]] = {}
    for probe in probes:
        if not isinstance(probe, dict):
            continue
        category = probe.get("category")
        pillar = DRIFT_CATEGORY_TO_PILLAR.get(category)
        if pillar is None:
            continue
        entry = pillar_rollup.setdefault(
            pillar,
            {
                "pillar": pillar,
                "status": "advance",
                "rationale": "All mapped probes for this pillar passed in the current drift run.",
                "evidence_refs": ["workflow_payload.drift_output"],
            },
        )
        if not probe.get("correct", False):
            entry["status"] = "risk" if status == "ALERT" else "watch"
            entry["rationale"] = (
                f"Probe {probe.get('id', 'unknown')} in category {category} failed, indicating semantic drift for this pillar."
            )

    recommended_actions: list[dict[str, Any]] = []
    if status != "OK":
        recommended_actions.append(
            {
                "title": "Review failing drift probes",
                "priority": "P1" if status == "ALERT" else "P2",
                "effort": "small",
                "lane": "bridge",
                "rationale": drift_payload.get("summary")
                or "Semantic drift requires operator review.",
                "target_files": [
                    "scripts/monitor_model_drift.py",
                    ".github/workflows/weekly-model-drift-detect.yml",
                ],
            }
        )
    if status == "ALERT":
        recommended_actions.append(
            {
                "title": "Escalate model qualification review",
                "priority": "P1",
                "effort": "medium",
                "lane": "bridge",
                "rationale": "ALERT-level drift means the current model understanding is no longer within acceptable bounds.",
                "target_files": [
                    "governance/model_qualification_profiles.json",
                    "scripts/monitor_model_drift.py",
                ],
            }
        )

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "model_drift",
        "summary": drift_payload.get("summary") or "Weekly model drift review generated.",
        "severity": severity,
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": recommended_triage_lane,
        "backend": _backend_from_ollama_payload(
            {
                "modelUsed": drift_payload.get("modelUsed"),
                "tier": drift_payload.get("tier"),
                "audit_trail": [
                    {"model": model_name}
                    for model_name in _as_string_list(drift_payload.get("chainUsed"))
                ],
            }
        ),
        "pillar_assessments": list(pillar_rollup.values()),
        "recommended_actions": recommended_actions,
        "evidence_refs": ["workflow_payload.drift_output"],
        "escalation_triggers": [
            "drift_status_alert",
            "drift_score_above_0.40",
        ]
        if status == "ALERT"
        else ([] if status == "OK" else ["drift_status_warn"]),
        "review_metadata": {
            "drift_score": drift_payload.get("driftScore"),
            "correct": drift_payload.get("correct"),
            "total": drift_payload.get("total"),
        },
    }
    return normalize_governed_review(review, source="weekly-model-drift-detect")


def build_spec_sentinel_governed_review(
    drift_payload: dict[str, Any],
    *,
    ai_analysis_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    has_drift = bool(drift_payload.get("drift_detected"))
    findings = list(drift_payload.get("findings") or [])
    drift_checks = sum(1 for item in findings if isinstance(item, dict) and item.get("drift"))

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": (
            f"Spec sentinel detected drift in {drift_checks} check(s)."
            if has_drift
            else "Spec sentinel found no implementation/spec drift."
        ),
        "severity": "warning" if has_drift else "info",
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": "current_batch" if has_drift else "ignore",
        "backend": _backend_from_ollama_payload(ai_analysis_payload or {})
        if isinstance(ai_analysis_payload, dict)
        else _normalize_backend({}),
        "pillar_assessments": [
            {
                "pillar": "Deterministic language core",
                "status": "risk" if has_drift else "advance",
                "rationale": (
                    f"{drift_checks} spec-consistency checks reported mismatches."
                    if has_drift
                    else "The current drift run reports spec and implementation consistency."
                ),
                "evidence_refs": ["workflow_payload.drift_report"],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Repair spec and implementation drift",
                    "priority": "P1",
                    "effort": "small",
                    "lane": "current_truth",
                    "rationale": "The weekly spec sentinel found concrete mismatches between governance specs and implementation surfaces.",
                    "target_files": [
                        "governance/bytecode_spec.yaml",
                        "governance/host_functions.json",
                        "hlf_mcp/hlf/bytecode.py",
                        "hlf_mcp/hlf/runtime.py",
                        "README.md",
                    ],
                }
            ]
            if has_drift
            else []
        ),
        "evidence_refs": ["workflow_payload.drift_report", "workflow_payload.ai_analysis"],
        "escalation_triggers": ["spec_drift_detected"] if has_drift else [],
        "review_metadata": {
            "drift_detected": has_drift,
            "drift_check_count": drift_checks,
        },
    }
    return normalize_governed_review(review, source="weekly-spec-sentinel")


def build_test_health_governed_review(
    coverage_payload: dict[str, Any] | None,
    *,
    test_suggestions_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage_payload = coverage_payload if isinstance(coverage_payload, dict) else {}
    totals = (
        coverage_payload.get("totals") if isinstance(coverage_payload.get("totals"), dict) else {}
    )
    percent_covered = totals.get("percent_covered")
    if not isinstance(percent_covered, (int, float)):
        percent_covered = None

    if percent_covered is None:
        severity = "warning"
        lane = "backlog"
        status = "watch"
        summary = "Test health run completed without usable coverage totals."
    elif percent_covered < 60:
        severity = "critical"
        lane = "current_batch"
        status = "risk"
        summary = f"Test health reports low coverage at {percent_covered:.1f}% for HLF surfaces."
    elif percent_covered < 80:
        severity = "warning"
        lane = "backlog"
        status = "watch"
        summary = f"Test health reports partial coverage at {percent_covered:.1f}%."
    else:
        severity = "info"
        lane = "ignore"
        status = "advance"
        summary = f"Test health reports acceptable coverage at {percent_covered:.1f}%."

    has_ai_suggestions = isinstance(test_suggestions_payload, dict) and bool(
        test_suggestions_payload
    )
    if has_ai_suggestions:
        summary = f"{summary} Deterministic coverage data is authoritative; AI-generated test output is advisory only and requires operator review plus deduplication against existing suites."

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": summary,
        "severity": severity,
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": lane,
        "backend": _backend_from_ollama_payload(test_suggestions_payload or {})
        if isinstance(test_suggestions_payload, dict)
        else _normalize_backend({}),
        "pillar_assessments": [
            {
                "pillar": "Human-readable audit and trust layer",
                "status": status,
                "rationale": "Coverage and executable tests are part of whether HLF can be trusted by external operators, but advisory AI suggestions must be reviewed against existing suites before promotion.",
                "evidence_refs": [
                    "workflow_payload.coverage",
                    "workflow_payload.test_suggestions",
                    "workflow_payload.existing_test_context",
                ],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Close high-risk coverage gaps",
                    "priority": "P1" if severity == "critical" else "P2",
                    "effort": "medium",
                    "lane": "current_truth",
                    "rationale": "The weekly test health workflow found coverage gaps large enough to weaken confidence in current behavior; use AI output only as candidate material and prefer extending existing suites over creating duplicate umbrella tests.",
                    "target_files": ["tests/", "hlf_mcp/"],
                }
            ]
            if lane != "ignore"
            else []
        ),
        "evidence_refs": [
            "workflow_payload.coverage",
            "workflow_payload.test_suggestions",
            "workflow_payload.existing_test_context",
        ],
        "escalation_triggers": ["coverage_below_threshold"]
        if severity in {"warning", "critical"}
        else [],
        "review_metadata": {
            "percent_covered": percent_covered,
            "ai_suggestions_advisory_only": has_ai_suggestions,
            "requires_existing_test_review": has_ai_suggestions,
            "requires_deduplication_against_existing_tests": has_ai_suggestions,
            "preferred_integration_strategy": "extend_existing_test_suites",
            "existing_test_context_present": bool(
                isinstance(test_suggestions_payload, dict)
                and (
                    test_suggestions_payload.get("existing_test_context")
                    or test_suggestions_payload.get("context_digest")
                )
            ),
        },
    }
    return normalize_governed_review(review, source="weekly-test-health")


def build_ethics_review_governed_review(
    ethics_report_payload: dict[str, Any] | None,
    *,
    ethics_review_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ethics_report_payload = ethics_report_payload if isinstance(ethics_report_payload, dict) else {}
    review_content = None
    if isinstance(ethics_review_payload, dict):
        review_content = ethics_review_payload.get("content")
    if not isinstance(review_content, str):
        review_content = ""
    has_findings = "NO_ACTIONABLE_FINDINGS" not in review_content and review_content.strip() != ""

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": (
            "Ethics review found actionable changed-surface findings."
            if has_findings
            else (
                ethics_report_payload.get("summary_text")
                or "Ethics review found no actionable changed-surface findings."
            )
        ),
        "severity": "critical" if has_findings else "info",
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": "current_batch" if has_findings else "ignore",
        "backend": _backend_from_ollama_payload(ethics_review_payload or {})
        if isinstance(ethics_review_payload, dict)
        else _normalize_backend({}),
        "pillar_assessments": [
            {
                "pillar": "Governance-native execution",
                "status": "risk" if has_findings else "advance",
                "rationale": (
                    "Changed ethics or governance surfaces produced actionable findings."
                    if has_findings
                    else "The current changed-surface ethics review did not report actionable regressions."
                ),
                "evidence_refs": [
                    "workflow_payload.ethics_report",
                    "workflow_payload.ethics_review",
                ],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Resolve ethics alignment finding",
                    "priority": "P1",
                    "effort": "medium",
                    "lane": "bridge",
                    "rationale": "Weekly ethics review reported a changed-surface governance or ethics regression.",
                    "target_files": [
                        "governance/",
                        "hlf_mcp/hlf/ethics/",
                        "hlf_mcp/hlf/compiler.py",
                        "hlf_mcp/hlf/runtime.py",
                    ],
                }
            ]
            if has_findings
            else []
        ),
        "evidence_refs": ["workflow_payload.ethics_report", "workflow_payload.ethics_review"],
        "escalation_triggers": ["ethics_actionable_findings"] if has_findings else [],
        "review_metadata": {"has_findings": has_findings},
    }
    return normalize_governed_review(review, source="weekly-ethics-review")


def build_code_quality_governed_review(
    code_quality_payload: dict[str, Any] | None,
    *,
    security_findings_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    code_quality_payload = code_quality_payload if isinstance(code_quality_payload, dict) else {}
    security_findings_payload = (
        security_findings_payload if isinstance(security_findings_payload, dict) else {}
    )
    summary = (
        security_findings_payload.get("summary")
        if isinstance(security_findings_payload.get("summary"), dict)
        else {}
    )
    open_alerts = summary.get("open_alerts")
    if not isinstance(open_alerts, int):
        open_alerts = None
    high_count = 0
    severity_counts = (
        summary.get("severity_counts") if isinstance(summary.get("severity_counts"), dict) else {}
    )
    if isinstance(severity_counts.get("high"), int):
        high_count = severity_counts["high"]

    if open_alerts is None:
        severity = "info"
        lane = "ignore"
        status = "advance"
        text = "Code quality workflow completed without open security alert counts."
    elif open_alerts > 0:
        severity = "critical" if high_count > 0 else "warning"
        lane = "current_batch" if high_count > 0 else "backlog"
        status = "risk" if high_count > 0 else "watch"
        text = f"Code quality workflow reports {open_alerts} open security alert(s)."
    else:
        severity = "info"
        lane = "ignore"
        status = "advance"
        text = "Code quality workflow reports no open security alerts in the collected summary."

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": text,
        "severity": severity,
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": lane,
        "backend": _normalize_backend({}),
        "pillar_assessments": [
            {
                "pillar": "Human-readable audit and trust layer",
                "status": status,
                "rationale": "Security and code-quality summaries directly affect whether the current surface can be trusted and promoted honestly.",
                "evidence_refs": [
                    "workflow_payload.code_quality",
                    "workflow_payload.security_findings",
                ],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Triaged open code-quality alerts",
                    "priority": "P1" if severity == "critical" else "P2",
                    "effort": "small",
                    "lane": "current_truth",
                    "rationale": "The weekly code quality workflow surfaced open alerts that need explicit operator review.",
                    "target_files": [".github/workflows/weekly-code-quality.yml", "hlf_mcp/"],
                }
            ]
            if lane != "ignore"
            else []
        ),
        "evidence_refs": ["workflow_payload.code_quality", "workflow_payload.security_findings"],
        "escalation_triggers": ["open_security_alerts"] if lane != "ignore" else [],
        "review_metadata": {
            "open_alerts": open_alerts,
            "high_severity_alerts": high_count,
            "coverage_xml_present": code_quality_payload.get("coverage_xml_present"),
        },
    }
    return normalize_governed_review(review, source="weekly-code-quality")


def build_doc_accuracy_governed_review(doc_drift_payload: dict[str, Any] | None) -> dict[str, Any]:
    doc_drift_payload = doc_drift_payload if isinstance(doc_drift_payload, dict) else {}
    has_drift = bool(doc_drift_payload.get("drift_detected"))
    findings = list(doc_drift_payload.get("findings") or [])
    drift_checks = sum(1 for item in findings if isinstance(item, dict) and item.get("drift"))

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": (
            f"Documentation accuracy review detected drift in {drift_checks} measured check(s)."
            if has_drift
            else "Documentation accuracy review found no measured drift."
        ),
        "severity": "warning" if has_drift else "info",
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": "backlog" if has_drift else "ignore",
        "backend": _normalize_backend({}),
        "pillar_assessments": [
            {
                "pillar": "Human-readable audit and trust layer",
                "status": "watch" if has_drift else "advance",
                "rationale": (
                    "Measured doc drift weakens operator trust because public counts or surface claims no longer match packaged reality."
                    if has_drift
                    else "Measured documentation counts remain aligned with packaged truth in this run."
                ),
                "evidence_refs": ["workflow_payload.doc_drift"],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Correct measured documentation drift",
                    "priority": "P2",
                    "effort": "small",
                    "lane": "current_truth",
                    "rationale": "Documentation claims should be regenerated or corrected when weekly drift checks detect mismatches.",
                    "target_files": ["README.md", "docs/", "governance/"],
                }
            ]
            if has_drift
            else []
        ),
        "evidence_refs": ["workflow_payload.doc_drift"],
        "escalation_triggers": ["documentation_drift_detected"] if has_drift else [],
        "review_metadata": {
            "drift_detected": has_drift,
            "drift_check_count": drift_checks,
        },
    }
    return normalize_governed_review(review, source="weekly-doc-accuracy")


def build_security_patterns_governed_review(
    security_review_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    security_review_payload = (
        security_review_payload if isinstance(security_review_payload, dict) else {}
    )
    review_content = security_review_payload.get("content")
    if not isinstance(review_content, str):
        review_content = ""
    normalized_content = review_content.strip()
    has_findings = bool(
        normalized_content
        and "NO_ACTIONABLE_FINDINGS" not in normalized_content
        and "No actionable findings" not in normalized_content
    )

    review = {
        "contract_version": REVIEW_CONTRACT_VERSION,
        "review_type": "weekly_artifact",
        "summary": (
            "Security pattern review reported actionable adversarial findings."
            if has_findings
            else "Security pattern review reported no actionable adversarial findings."
        ),
        "severity": "critical" if has_findings else "info",
        "automation_status": "generated",
        "operator_gate_required": True,
        "recommended_triage_lane": "current_batch" if has_findings else "ignore",
        "backend": _backend_from_ollama_payload(security_review_payload),
        "pillar_assessments": [
            {
                "pillar": "Governance-native execution",
                "status": "risk" if has_findings else "advance",
                "rationale": (
                    "Actionable adversarial findings indicate current governance or runtime protections need attention."
                    if has_findings
                    else "The current adversarial review did not identify actionable security-pattern gaps."
                ),
                "evidence_refs": ["workflow_payload.security_review"],
            }
        ],
        "recommended_actions": (
            [
                {
                    "title": "Triage weekly security pattern findings",
                    "priority": "P1",
                    "effort": "medium",
                    "lane": "bridge",
                    "rationale": "Actionable adversarial findings should be triaged against current governance and runtime controls.",
                    "target_files": [
                        "governance/align_rules.json",
                        "hlf_mcp/hlf/compiler.py",
                        "hlf_mcp/hlf/runtime.py",
                    ],
                }
            ]
            if has_findings
            else []
        ),
        "evidence_refs": ["workflow_payload.security_review"],
        "escalation_triggers": ["security_actionable_findings"] if has_findings else [],
        "review_metadata": {"has_findings": has_findings},
    }
    return normalize_governed_review(review, source="weekly-security-patterns")
