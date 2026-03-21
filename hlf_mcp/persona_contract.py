from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_HANDOFF_TEMPLATE_REF = "governance/templates/persona_review_handoff.md"

_SOURCE_CHANGE_CLASS_MAP = {
    "weekly-evolution-planner": "planning_only",
    "weekly-doc-accuracy": "docs_truth",
    "weekly-code-quality": "security_sensitive",
    "weekly-security-patterns": "security_sensitive",
    "weekly-spec-sentinel": "workflow_contract",
    "weekly-test-health": "workflow_contract",
    "weekly-model-drift-detect": "workflow_contract",
}

_CHANGE_CLASS_OWNER_MAP = {
    "planning_only": "strategist",
    "docs_truth": "herald",
    "workflow_contract": "steward",
    "security_sensitive": "sentinel",
    "low_risk_maintenance": "strategist",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _matrix_path() -> Path:
    return _repo_root() / "docs" / "HLF_PERSONA_OWNERSHIP_MATRIX.json"


def _fallback_matrix() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "lane": "bridge-true",
        "structured_fields": [
            "change_class",
            "lane",
            "owner_persona",
            "review_personas",
            "required_gates",
            "gate_results",
            "escalate_to_persona",
            "operator_summary",
        ],
        "gate_states": {
            "strategist_review": {"owner_persona": "strategist"},
            "steward_review": {"owner_persona": "steward"},
            "sentinel_review": {"owner_persona": "sentinel"},
            "herald_review": {"owner_persona": "herald"},
            "chronicler_review": {"owner_persona": "chronicler"},
            "cove_review": {"owner_persona": "cove"},
            "operator_promotion": {"owner_persona": "operator"},
        },
        "change_classes": {
            "planning_only": {
                "required_gates": [
                    "strategist_review",
                    "chronicler_review",
                    "cove_review",
                    "operator_promotion",
                ]
            },
            "docs_truth": {
                "required_gates": [
                    "strategist_review",
                    "herald_review",
                    "chronicler_review",
                    "cove_review",
                    "operator_promotion",
                ]
            },
            "workflow_contract": {
                "required_gates": [
                    "strategist_review",
                    "steward_review",
                    "sentinel_review",
                    "herald_review",
                    "cove_review",
                    "operator_promotion",
                ]
            },
            "security_sensitive": {
                "required_gates": [
                    "strategist_review",
                    "sentinel_review",
                    "steward_review",
                    "cove_review",
                    "operator_promotion",
                ]
            },
            "low_risk_maintenance": {
                "required_gates": [
                    "strategist_review",
                    "cove_review",
                    "operator_promotion",
                ]
            },
        },
        "personas": {
            "strategist": {},
            "steward": {},
            "sentinel": {},
            "herald": {},
            "chronicler": {},
            "cove": {},
        },
    }


@lru_cache(maxsize=1)
def load_persona_matrix() -> dict[str, Any]:
    fallback = _fallback_matrix()
    path = _matrix_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback
    return payload if isinstance(payload, dict) else fallback


def _valid_personas(matrix: dict[str, Any]) -> set[str]:
    personas = matrix.get("personas") if isinstance(matrix.get("personas"), dict) else {}
    return set(personas) | {"operator"}


def _gate_states(matrix: dict[str, Any]) -> dict[str, Any]:
    gate_states = matrix.get("gate_states")
    return gate_states if isinstance(gate_states, dict) else {}


def _required_gates_for_change_class(change_class: str, matrix: dict[str, Any]) -> list[str]:
    change_classes = matrix.get("change_classes")
    if not isinstance(change_classes, dict):
        return []
    entry = change_classes.get(change_class)
    if not isinstance(entry, dict):
        return []
    return [
        str(item)
        for item in entry.get("required_gates", [])
        if isinstance(item, str) and item in _gate_states(matrix)
    ]


def _resolve_change_class(
    source: str | None, review_type: str | None, matrix: dict[str, Any]
) -> str:
    if isinstance(source, str) and source in _SOURCE_CHANGE_CLASS_MAP:
        return _SOURCE_CHANGE_CLASS_MAP[source]
    if review_type == "evolution_planning":
        return "planning_only"
    if review_type == "model_drift":
        return "workflow_contract"
    if review_type == "weekly_artifact" and source == "weekly-doc-accuracy":
        return "docs_truth"
    fallback_classes = (
        matrix.get("change_classes") if isinstance(matrix.get("change_classes"), dict) else {}
    )
    if "workflow_contract" in fallback_classes:
        return "workflow_contract"
    return next(iter(fallback_classes), "workflow_contract")


def _default_owner_persona(change_class: str) -> str:
    return _CHANGE_CLASS_OWNER_MAP.get(change_class, "strategist")


def _normalize_gate_results(
    existing: Any,
    *,
    required_gates: list[str],
    matrix: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    gate_states = _gate_states(matrix)
    valid_personas = _valid_personas(matrix)
    normalized: dict[str, dict[str, Any]] = {}

    if isinstance(existing, dict):
        for gate_name, gate_value in existing.items():
            if gate_name not in gate_states or not isinstance(gate_value, dict):
                continue
            owner_persona = gate_value.get("owner_persona")
            if not isinstance(owner_persona, str) or owner_persona not in valid_personas:
                owner_persona = gate_states.get(gate_name, {}).get("owner_persona")
            normalized[gate_name] = {
                "owner_persona": owner_persona,
                "status": gate_value.get("status")
                if isinstance(gate_value.get("status"), str)
                else None,
                "notes": gate_value.get("notes")
                if isinstance(gate_value.get("notes"), str)
                else None,
            }

    for gate_name in required_gates:
        if gate_name not in normalized:
            normalized[gate_name] = {
                "owner_persona": gate_states.get(gate_name, {}).get("owner_persona"),
                "status": None,
                "notes": None,
            }
    return normalized


def _default_escalation_persona(
    *,
    owner_persona: str,
    severity: str | None,
    recommended_triage_lane: str | None,
) -> str | None:
    if severity == "critical":
        return "operator" if owner_persona == "sentinel" else "sentinel"
    if recommended_triage_lane == "current_batch":
        return "strategist" if owner_persona != "strategist" else "operator"
    return None


def resolve_persona_contract(
    *,
    source: str | None,
    review_type: str | None,
    severity: str | None,
    recommended_triage_lane: str | None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    matrix = load_persona_matrix()
    existing = existing if isinstance(existing, dict) else {}
    valid_personas = _valid_personas(matrix)

    change_class = existing.get("change_class")
    if not isinstance(change_class, str) or change_class not in (
        matrix.get("change_classes") or {}
    ):
        change_class = _resolve_change_class(source, review_type, matrix)

    lane = existing.get("lane")
    if not isinstance(lane, str) or not lane:
        lane = str(matrix.get("lane") or "bridge-true")

    required_gates = existing.get("required_gates")
    if not isinstance(required_gates, list) or any(
        not isinstance(item, str) for item in required_gates
    ):
        required_gates = _required_gates_for_change_class(change_class, matrix)
    required_gates = [gate for gate in required_gates if gate in _gate_states(matrix)]

    owner_persona = existing.get("owner_persona")
    if not isinstance(owner_persona, str) or owner_persona not in valid_personas:
        owner_persona = _default_owner_persona(change_class)

    gate_results = _normalize_gate_results(
        existing.get("gate_results"),
        required_gates=required_gates,
        matrix=matrix,
    )

    review_personas = existing.get("review_personas")
    if not isinstance(review_personas, list) or any(
        not isinstance(item, str) or item not in valid_personas for item in review_personas
    ):
        review_personas = []
        for gate_name in required_gates:
            owner = gate_results.get(gate_name, {}).get("owner_persona")
            if (
                isinstance(owner, str)
                and owner not in {"operator", owner_persona}
                and owner not in review_personas
            ):
                review_personas.append(owner)

    escalate_to_persona = existing.get("escalate_to_persona")
    if escalate_to_persona is not None and (
        not isinstance(escalate_to_persona, str) or escalate_to_persona not in valid_personas
    ):
        escalate_to_persona = None
    if escalate_to_persona is None:
        escalate_to_persona = _default_escalation_persona(
            owner_persona=owner_persona,
            severity=severity,
            recommended_triage_lane=recommended_triage_lane,
        )

    handoff_template_ref = existing.get("handoff_template_ref")
    if not isinstance(handoff_template_ref, str) or not handoff_template_ref:
        handoff_template_ref = DEFAULT_HANDOFF_TEMPLATE_REF

    operator_summary = existing.get("operator_summary")
    if not isinstance(operator_summary, str) or not operator_summary:
        gates_text = ", ".join(required_gates) if required_gates else "no explicit persona gates"
        review_text = (
            ", ".join(review_personas) if review_personas else "no secondary persona reviews"
        )
        operator_summary = (
            f"Owner persona {owner_persona}; review personas {review_text}; "
            f"required gates {gates_text}."
        )

    return {
        "change_class": change_class,
        "lane": lane,
        "owner_persona": owner_persona,
        "review_personas": review_personas,
        "required_gates": required_gates,
        "gate_results": gate_results,
        "escalate_to_persona": escalate_to_persona,
        "operator_summary": operator_summary,
        "handoff_template_ref": handoff_template_ref,
    }


def validate_persona_contract(review: Any, errors: list[str]) -> None:
    if not isinstance(review, dict):
        errors.append("governed_review_persona_contract_invalid")
        return

    matrix = load_persona_matrix()
    valid_personas = _valid_personas(matrix)
    gate_states = _gate_states(matrix)
    change_classes = (
        matrix.get("change_classes") if isinstance(matrix.get("change_classes"), dict) else {}
    )

    change_class = review.get("change_class")
    if not isinstance(change_class, str) or change_class not in change_classes:
        errors.append("governed_review_change_class_invalid")

    lane = review.get("lane")
    if not isinstance(lane, str) or not lane:
        errors.append("governed_review_lane_invalid")

    owner_persona = review.get("owner_persona")
    if not isinstance(owner_persona, str) or owner_persona not in valid_personas:
        errors.append("governed_review_owner_persona_invalid")

    review_personas = review.get("review_personas")
    if not isinstance(review_personas, list) or any(
        not isinstance(item, str) or item not in valid_personas for item in review_personas
    ):
        errors.append("governed_review_review_personas_invalid")

    required_gates = review.get("required_gates")
    if not isinstance(required_gates, list) or any(
        not isinstance(item, str) or item not in gate_states for item in required_gates
    ):
        errors.append("governed_review_required_gates_invalid")

    gate_results = review.get("gate_results")
    if not isinstance(gate_results, dict):
        errors.append("governed_review_gate_results_invalid")
    else:
        for gate_name, gate_value in gate_results.items():
            if gate_name not in gate_states:
                errors.append(f"governed_review_gate_results[{gate_name}]_unknown_gate")
                continue
            if not isinstance(gate_value, dict):
                errors.append(f"governed_review_gate_results[{gate_name}]_invalid")
                continue
            gate_owner = gate_value.get("owner_persona")
            if not isinstance(gate_owner, str) or gate_owner not in valid_personas:
                errors.append(f"governed_review_gate_results[{gate_name}]_owner_invalid")
            gate_status = gate_value.get("status")
            if gate_status is not None and (not isinstance(gate_status, str) or not gate_status):
                errors.append(f"governed_review_gate_results[{gate_name}]_status_invalid")
            gate_notes = gate_value.get("notes")
            if gate_notes is not None and (not isinstance(gate_notes, str) or not gate_notes):
                errors.append(f"governed_review_gate_results[{gate_name}]_notes_invalid")

        if isinstance(required_gates, list):
            for gate_name in required_gates:
                if gate_name not in gate_results:
                    errors.append(f"governed_review_gate_results[{gate_name}]_missing")

    escalate_to_persona = review.get("escalate_to_persona")
    if escalate_to_persona is not None and (
        not isinstance(escalate_to_persona, str) or escalate_to_persona not in valid_personas
    ):
        errors.append("governed_review_escalate_to_persona_invalid")

    operator_summary = review.get("operator_summary")
    if not isinstance(operator_summary, str) or not operator_summary:
        errors.append("governed_review_operator_summary_invalid")

    handoff_template_ref = review.get("handoff_template_ref")
    if not isinstance(handoff_template_ref, str) or not handoff_template_ref:
        errors.append("governed_review_handoff_template_ref_invalid")
