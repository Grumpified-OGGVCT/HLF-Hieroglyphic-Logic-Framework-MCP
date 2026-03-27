from __future__ import annotations

from typing import Any

from hlf_mcp.server_context import ServerContext


def resolve_execution_ingress_contract(
    ctx: ServerContext,
    *,
    agent_id: str,
    payload: str | dict[str, Any],
    subject_scope: str,
    nonce: str,
    require_hlf_validation: bool,
    hlf_validated: bool,
) -> dict[str, Any] | None:
    route_trace = ctx.get_governed_route(agent_id=agent_id)
    if isinstance(route_trace, dict):
        policy_basis = route_trace.get("policy_basis", {})
        if isinstance(policy_basis, dict):
            route_ingress = policy_basis.get("ingress_contract")
            if isinstance(route_ingress, dict) and route_ingress:
                return dict(route_ingress)

    if not agent_id or agent_id == "unknown-agent":
        return None

    ingress_contract = ctx.ingress_controller.evaluate(
        payload,
        subject_key=f"{agent_id}:{subject_scope}",
        nonce=nonce,
        require_hlf_validation=require_hlf_validation,
        hlf_validated=hlf_validated,
        enable_rate_limit=True,
        enable_replay_protection=bool(nonce),
    )
    return ingress_contract.to_dict()


def persist_runtime_execution_admission(
    ctx: ServerContext,
    *,
    agent_id: str,
    execution_status: str,
    requested_tier: str,
    surface: str,
    ingress_contract: dict[str, Any] | None,
    run_result: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "unknown-agent")
    normalized_ingress_contract = dict(ingress_contract or {})
    route_trace = ctx.get_governed_route(agent_id=normalized_agent_id)
    route_decision = route_trace.get("route_decision", {}) if isinstance(route_trace, dict) else {}
    policy_basis = route_trace.get("policy_basis", {}) if isinstance(route_trace, dict) else {}
    run_payload = dict(run_result or {})
    side_effects = run_payload.get("side_effects", [])
    if not isinstance(side_effects, list):
        side_effects = []

    effect_classes = sorted(
        {
            str(item.get("effect_class") or item.get("effect") or "").strip()
            for item in side_effects
            if isinstance(item, dict)
            and str(item.get("effect_class") or item.get("effect") or "").strip()
        }
    )
    tool_names = sorted(
        {
            str(
                item.get("tool_name")
                or item.get("function_name")
                or item.get("name")
                or ""
            ).strip()
            for item in side_effects
            if isinstance(item, dict)
            and str(
                item.get("tool_name")
                or item.get("function_name")
                or item.get("name")
                or ""
            ).strip()
        }
    )

    route_evidence = {
        "available": route_trace is not None,
        "selected_lane": route_decision.get("selected_lane"),
        "decision": route_decision.get("decision"),
        "governance_mode": route_decision.get("governance_mode"),
        "review_required": route_decision.get("review_required"),
        "align_action": policy_basis.get("align_action"),
        "deployment_tier": policy_basis.get("deployment_tier"),
        "allowlist_policy": dict(policy_basis.get("allowlist_policy") or {}),
        "route_governance_event_ref": policy_basis.get("governance_event_ref"),
        "policy_constraints": list(policy_basis.get("policy_constraints", [])),
        "missing_evidence_profiles": list(policy_basis.get("missing_evidence_profiles", [])),
        "policy_basis_present": bool(policy_basis.get("policy_basis_present", False)),
    }
    ingress_evidence = {
        "available": bool(normalized_ingress_contract),
        "admitted": normalized_ingress_contract.get("admitted") if normalized_ingress_contract else None,
        "decision": normalized_ingress_contract.get("decision") if normalized_ingress_contract else None,
        "blocked_stage": normalized_ingress_contract.get("blocked_stage") if normalized_ingress_contract else None,
        "review_required": normalized_ingress_contract.get("review_required") if normalized_ingress_contract else None,
        "checks": list(normalized_ingress_contract.get("checks", [])) if normalized_ingress_contract else [],
        "policy_basis": dict(normalized_ingress_contract.get("policy_basis") or {}) if normalized_ingress_contract else {},
    }
    admitted = bool(normalized_ingress_contract.get("admitted", False))
    review_required = bool(normalized_ingress_contract.get("review_required", False))
    resolved_reasons = list(reasons or [])
    if not resolved_reasons and not admitted:
        blocked_stage = str(normalized_ingress_contract.get("blocked_stage") or "ingress")
        resolved_reasons = [f"Packaged ingress blocked {surface} at stage '{blocked_stage}'."]

    operator_summary = (
        f"Runtime admission for agent '{normalized_agent_id}' on surface '{surface}' is '{'allow' if admitted else 'deny'}' "
        f"during execution status '{execution_status}'. Route lane is '{route_evidence.get('selected_lane') or 'unresolved'}' "
        f"and ingress is '{ingress_evidence.get('decision') or 'not-evaluated'}' at stage "
        f"'{ingress_evidence.get('blocked_stage') or 'admit'}'."
    )

    return ctx.persist_execution_admission(
        agent_id=normalized_agent_id,
        admission_record={
            "contract_version": "1.0",
            "agent_id": normalized_agent_id,
            "surface": surface,
            "requested_tier": requested_tier,
            "execution_status": execution_status,
            "admission_verdict": "allow" if admitted else "deny",
            "admitted": admitted,
            "requires_operator_review": review_required,
            "reasons": resolved_reasons,
            "effect_basis": {
                "effect_classes": effect_classes,
                "tool_names": tool_names,
            },
            "embodied_effect": {},
            "ingress_evidence": ingress_evidence,
            "route_evidence": route_evidence,
            "pointer_evidence": {},
            "orchestration_lineage": {
                "contract_version": "1.0",
                "delegation_events": [],
                "mission": {},
            },
            "approval": {
                "status": "not_required",
                "requirements": [],
                "request": None,
            },
            "audit_refs": {
                "execution_trace_id": "",
                "execution_parent_trace_hash": "",
            },
            "verification": {
                "surface": surface,
                "execution_status": execution_status,
            },
            "operator_summary": operator_summary,
        },
    )


def build_ingress_denial_reasons(
    ingress_contract: dict[str, Any] | None,
    *,
    surface: str,
) -> list[str]:
    if not isinstance(ingress_contract, dict) or not ingress_contract:
        return []
    if bool(ingress_contract.get("admitted", False)):
        return []
    blocked_stage = str(ingress_contract.get("blocked_stage") or "ingress")
    return [f"Packaged ingress blocked {surface} at stage '{blocked_stage}'."]


def normalize_ingress_status(
    *,
    route_trace: dict[str, Any] | None,
    execution_admission: dict[str, Any] | None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    normalized_agent_id = str(agent_id or "").strip()
    route_policy_basis = route_trace.get("policy_basis", {}) if isinstance(route_trace, dict) else {}
    route_contract = route_policy_basis.get("ingress_contract") if isinstance(route_policy_basis, dict) else None
    admission_evidence = (
        execution_admission.get("ingress_evidence", {})
        if isinstance(execution_admission, dict)
        else {}
    )

    source = "none"
    raw_contract: dict[str, Any] = {}
    if isinstance(route_contract, dict) and route_contract:
        source = "route_trace"
        raw_contract = dict(route_contract)
    elif isinstance(admission_evidence, dict) and admission_evidence.get("available"):
        source = "execution_admission"
        raw_contract = {
            "admitted": admission_evidence.get("admitted"),
            "decision": admission_evidence.get("decision"),
            "blocked_stage": admission_evidence.get("blocked_stage"),
            "review_required": admission_evidence.get("review_required"),
            "checks": list(admission_evidence.get("checks", [])),
            "policy_basis": dict(admission_evidence.get("policy_basis") or {}),
        }

    policy_basis = dict(raw_contract.get("policy_basis") or {}) if raw_contract else {}
    stage_status = {
        "rate_limit": dict(policy_basis.get("rate_limit") or {}),
        "hlf_validation": dict(policy_basis.get("hlf_validation") or {}),
        "align_gate": dict(policy_basis.get("align_gate") or {}),
        "replay_protection": dict(policy_basis.get("replay_protection") or {}),
        "route_contract": dict(policy_basis.get("route_contract") or {}),
    }
    resolved_agent_id = normalized_agent_id
    if not resolved_agent_id and isinstance(route_trace, dict):
        request_context = route_trace.get("request_context", {})
        if isinstance(request_context, dict):
            resolved_agent_id = str(request_context.get("agent_id") or "").strip()
    if not resolved_agent_id and isinstance(execution_admission, dict):
        resolved_agent_id = str(execution_admission.get("agent_id") or "").strip()

    return {
        "available": bool(raw_contract),
        "source": source,
        "agent_id": resolved_agent_id or None,
        "admitted": raw_contract.get("admitted") if raw_contract else None,
        "decision": raw_contract.get("decision") if raw_contract else None,
        "blocked_stage": raw_contract.get("blocked_stage") if raw_contract else None,
        "review_required": raw_contract.get("review_required") if raw_contract else None,
        "checks": list(raw_contract.get("checks", [])) if raw_contract else [],
        "policy_basis": policy_basis,
        "stage_order": list(policy_basis.get("stage_order", [])),
        "stage_status": stage_status,
    }


def summarize_ingress_status(ingress_status: dict[str, Any]) -> str:
    if not isinstance(ingress_status, dict) or not ingress_status.get("available"):
        return "Ingress posture is not yet recorded."

    source = str(ingress_status.get("source") or "unknown")
    decision = str(ingress_status.get("decision") or "unknown")
    blocked_stage = str(ingress_status.get("blocked_stage") or "admit")
    review_required = bool(ingress_status.get("review_required", False))
    rate_status = str((ingress_status.get("stage_status") or {}).get("rate_limit", {}).get("allowed", ""))
    replay_status = str(
        (ingress_status.get("stage_status") or {}).get("replay_protection", {}).get("status") or ""
    )
    source_label = source.replace("_", " ")
    summary = (
        f"Ingress posture from {source_label} is '{decision}' at stage '{blocked_stage}'"
    )
    if review_required:
        summary += " with operator review required"
    if rate_status:
        summary += f"; rate-limit gate allowed={rate_status}"
    if replay_status:
        summary += f"; replay status='{replay_status}'"
    return summary + "."