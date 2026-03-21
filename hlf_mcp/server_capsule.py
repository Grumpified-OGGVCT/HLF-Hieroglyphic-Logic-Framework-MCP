from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.execution_admission import evaluate_verifier_admission
from hlf_mcp.hlf.memory_node import verify_pointer_ref
from hlf_mcp.server_context import ServerContext

_TAG_EFFECT_CLASS_MAP = {
    "ACTION": "process_spawn",
    "CALL": "route_selection",
    "DELEGATE": "agent_delegation",
    "IMPORT": "token_transform",
    "MEMORY": "memory_write",
    "RECALL": "memory_read",
    "ROUTE": "route_selection",
    "SHELL_EXEC": "process_spawn",
    "SPAWN": "process_spawn",
    "TOOL": "route_selection",
}


def _parse_json_object(raw: str, *, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {field_name}: {exc}") from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _parse_json_string_list(raw: str, *, field_name: str) -> set[str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {field_name}: {exc}") from exc
    if parsed is None:
        return set()
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field_name} must be a JSON array of strings")
    return {item for item in parsed if item}


def _resolve_approval_request(
    ctx: ServerContext,
    *,
    capsule,
    statements: list[dict[str, Any]],
    approved_by: str,
    approval_token: str,
    extra_requirements: list[dict[str, Any]] | None = None,
) -> tuple[Any, dict[str, Any] | None]:
    requirements = capsule._merged_requirements(statements, extra_requirements)
    if not requirements:
        return capsule, None

    request = ctx.approval_ledger.ensure_request(
        capsule_id=capsule.capsule_id,
        agent_id=capsule.agent_id,
        base_tier=capsule.base_tier,
        requested_tier=capsule.requested_tier,
        requirements=requirements,
        approval_token=capsule.expected_approval_token(statements, extra_requirements),
    )

    if approved_by and approval_token and request.status == "pending":
        request = ctx.approval_ledger.decide(
            request_id=request.request_id,
            decision="approve",
            operator=approved_by,
            approval_token=approval_token,
        )

    if request.status == "approved":
        capsule = capsule_for_tier(
            capsule.base_tier,
            agent_id=capsule.agent_id,
            capsule_id=capsule.capsule_id,
            requested_tier=capsule.requested_tier,
            trusted_pointers=capsule.trusted_pointers,
            pointer_trust_mode=capsule.pointer_trust_mode,
            approval_required_tags=capsule.approval_required_tags,
            approval_required_tools=capsule.approval_required_tools,
            approved_by=request.operator,
            approval_token=request.approval_token,
        )

    return capsule, request.to_dict()


def _effective_verification_admission(
    verification_admission: dict[str, Any],
    *,
    approval_granted: bool,
) -> dict[str, Any]:
    effective = dict(verification_admission)
    if approval_granted and verification_admission.get("requires_operator_review"):
        effective["admitted"] = True
        effective["verdict"] = "verification_review_approved"
        effective["operator_review_approved"] = True
        reasons = [str(reason) for reason in effective.get("reasons", []) if reason]
        reasons.append("Operator review approved execution after incomplete proof coverage.")
        effective["reasons"] = reasons
    return effective


def _collect_effect_basis(ctx: ServerContext, verification: dict[str, Any]) -> dict[str, Any]:
    effect_summary = verification.get("effect_summary", {})
    tool_names = [str(name) for name in effect_summary.get("tools", []) if name]
    effectful_tags = [str(tag) for tag in effect_summary.get("effectful_tags", []) if tag]
    policy_traces: list[dict[str, Any]] = []
    effect_classes = {value for tag in effectful_tags if (value := _TAG_EFFECT_CLASS_MAP.get(tag))}
    audit_requirements: set[str] = set()
    for tool_name in tool_names:
        host_function = ctx.host_registry.get(tool_name)
        if host_function is None:
            continue
        policy_trace = host_function.policy_trace()
        policy_traces.append(policy_trace)
        effect_classes.add(str(policy_trace.get("effect_class") or ""))
        audit_requirement = str(policy_trace.get("audit_requirement") or "")
        if audit_requirement:
            audit_requirements.add(audit_requirement)
    effect_classes.discard("")
    return {
        "effectful": bool(effect_summary.get("effectful", False)),
        "node_count": effect_summary.get("node_count", 0),
        "effectful_tags": effectful_tags,
        "tool_names": tool_names,
        "effect_classes": sorted(effect_classes),
        "policy_traces": policy_traces,
        "audit_requirements": sorted(audit_requirements),
    }


def _collect_delegation_events(side_effects: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not side_effects:
        return []
    lineage: list[dict[str, Any]] = []
    for event in side_effects:
        if str(event.get("type") or "") != "delegation":
            continue
        lineage.append(
            {
                "agent": str(event.get("agent") or ""),
                "goal": str(event.get("goal") or ""),
                "task_id": str(event.get("task_id") or ""),
                "memory_context_source": str(event.get("memory_context_source") or ""),
                "memory_context_count": int(event.get("memory_context_count") or 0),
                "embedding_profile_id": str(event.get("embedding_profile_id") or ""),
            }
        )
    return lineage


def _collect_mission_lineage(
    ctx: ServerContext,
    runtime_variables: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not runtime_variables:
        return None
    mission_id = runtime_variables.get("MISSION_ID") or runtime_variables.get("mission_id")
    if not mission_id or not hasattr(ctx, "instinct_mgr"):
        return None
    mission = ctx.instinct_mgr.get_mission(str(mission_id))
    if mission is None:
        return {"mission_id": str(mission_id), "status": "not_found"}

    execution_trace = mission.get("execution_trace", [])
    task_dag = mission.get("task_dag", [])
    handoff_trace = [
        dict(entry)
        for entry in execution_trace
        if str(entry.get("delegated_to") or "").strip()
        or str(entry.get("escalation_role") or "").strip()
        or str(entry.get("dissent_state") or "none") != "none"
    ]
    handoff_plan = [
        dict(step)
        for step in task_dag
        if str(step.get("delegated_to") or "").strip()
        or str(step.get("escalation_role") or "").strip()
        or str(step.get("dissent_state") or "none") != "none"
    ]
    return {
        "mission_id": mission.get("mission_id"),
        "status": "ok",
        "topic": mission.get("topic"),
        "current_phase": mission.get("current_phase"),
        "execution_summary": dict(mission.get("execution_summary") or {}),
        "phase_history": list(mission.get("phase_history") or [])[-5:],
        "handoff_plan": handoff_plan,
        "handoff_trace": handoff_trace,
    }


def _build_execution_admission_record(
    ctx: ServerContext,
    *,
    agent_id: str,
    capsule,
    verification: dict[str, Any],
    execution_status: str,
    approval_requirements: list[dict[str, Any]],
    approval_request: dict[str, Any] | None,
    execution_audit: dict[str, Any] | None = None,
    side_effects: list[dict[str, Any]] | None = None,
    runtime_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route_trace = ctx.get_governed_route(agent_id=agent_id)
    route_decision = route_trace.get("route_decision", {}) if isinstance(route_trace, dict) else {}
    policy_basis = route_trace.get("policy_basis", {}) if isinstance(route_trace, dict) else {}
    effect_basis = _collect_effect_basis(ctx, verification)
    delegation_events = _collect_delegation_events(side_effects)
    mission_lineage = _collect_mission_lineage(ctx, runtime_variables)
    route_evidence = {
        "available": route_trace is not None,
        "selected_lane": route_decision.get("selected_lane"),
        "decision": route_decision.get("decision"),
        "governance_mode": route_decision.get("governance_mode"),
        "review_required": route_decision.get("review_required"),
        "route_governance_event_ref": policy_basis.get("governance_event_ref"),
        "policy_constraints": list(policy_basis.get("policy_constraints", [])),
        "missing_evidence_profiles": list(policy_basis.get("missing_evidence_profiles", [])),
        "policy_basis_present": bool(policy_basis.get("policy_basis_present", False)),
    }
    approval_status = "not_required"
    if approval_request is not None:
        approval_status = str(approval_request.get("status") or "pending")
    elif approval_requirements:
        approval_status = "required"
    operator_summary = (
        f"Execution admission for agent '{agent_id}' is '{verification.get('verdict', '')}' "
        f"during status '{execution_status}'. "
        f"Route lane is '{route_evidence.get('selected_lane') or 'unresolved'}' and effect classes are "
        f"{', '.join(effect_basis['effect_classes']) or 'none'}; approval is '{approval_status}'; "
        f"delegations recorded: {len(delegation_events)}."
    )
    return {
        "contract_version": "1.0",
        "agent_id": agent_id,
        "capsule_id": capsule.capsule_id,
        "requested_tier": capsule.requested_tier,
        "execution_status": execution_status,
        "admission_verdict": verification.get("verdict"),
        "admitted": bool(verification.get("admitted", False)),
        "requires_operator_review": bool(verification.get("requires_operator_review", False)),
        "reasons": list(verification.get("reasons", [])),
        "effect_basis": effect_basis,
        "route_evidence": route_evidence,
        "orchestration_lineage": {
            "delegation_events": delegation_events,
            "mission": mission_lineage,
        },
        "approval": {
            "status": approval_status,
            "requirements": list(approval_requirements),
            "request": approval_request,
        },
        "audit_refs": {
            "execution_trace_id": str(execution_audit.get("trace_id", ""))
            if execution_audit
            else "",
            "execution_parent_trace_hash": str(execution_audit.get("parent_trace_hash", ""))
            if execution_audit
            else "",
        },
        "verification": verification,
        "operator_summary": operator_summary,
    }


def register_capsule_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_capsule_validate(
        source: str,
        tier: str = "hearth",
        agent_id: str = "unknown-agent",
        capsule_id: str = "",
        requested_tier: str = "",
        pointers_json: str = "{}",
        pointer_trust_mode: str = "enforce",
        approval_required_tags_json: str = "[]",
        approval_required_tools_json: str = "[]",
        approved_by: str = "",
        approval_token: str = "",
    ) -> dict[str, Any]:
        """Validate HLF source AST against the intent capsule for the given tier."""
        try:
            trusted_pointers = _parse_json_object(pointers_json, field_name="pointers_json")
            approval_required_tags = _parse_json_string_list(
                approval_required_tags_json,
                field_name="approval_required_tags_json",
            )
            approval_required_tools = _parse_json_string_list(
                approval_required_tools_json,
                field_name="approval_required_tools_json",
            )
            result = ctx.compiler.compile(source)
            capsule = capsule_for_tier(
                tier,
                agent_id=agent_id,
                capsule_id=capsule_id or None,
                requested_tier=requested_tier or None,
                trusted_pointers=trusted_pointers,
                pointer_trust_mode=pointer_trust_mode,
                approval_required_tags=approval_required_tags,
                approval_required_tools=approval_required_tools,
                approved_by=approved_by,
                approval_token=approval_token,
            )
            stmts = result["ast"].get("statements", [])
            verification_admission = evaluate_verifier_admission(
                {"statements": stmts},
                verifier=ctx.formal_verifier,
                tier=tier,
                requested_tier=capsule.requested_tier,
            ).to_dict()
            verification_requirements = list(
                verification_admission.get("approval_requirements", [])
            )
            capsule, approval_request = _resolve_approval_request(
                ctx,
                capsule=capsule,
                statements=stmts,
                approved_by=approved_by,
                approval_token=approval_token,
                extra_requirements=verification_requirements,
            )
            approval_requirements = capsule._merged_requirements(stmts, verification_requirements)
            approval_granted = capsule.approval_granted(stmts, verification_requirements)
            effective_verification = _effective_verification_admission(
                verification_admission,
                approval_granted=approval_granted,
            )
            violations = capsule.validate_ast(stmts, verification_requirements)
            if not effective_verification.get("admitted", False) and not effective_verification.get(
                "requires_operator_review", False
            ):
                violations = [
                    f"Verifier admission denied: {reason}"
                    for reason in effective_verification.get("reasons", [])
                    if reason
                ] + violations
            return {
                "status": "ok",
                "tier": tier,
                "requested_tier": capsule.requested_tier,
                "agent_id": agent_id,
                "violations": violations,
                "approval_required": bool(approval_requirements) and not approval_granted,
                "approval_granted": approval_granted,
                "approval_requirements": approval_requirements,
                "approval_token": capsule.expected_approval_token(stmts, verification_requirements),
                "approval_request": approval_request,
                "passed": len(violations) == 0,
                "verification": effective_verification,
                "capsule": capsule.to_dict(),
            }
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_capsule_run(
        source: str,
        tier: str = "hearth",
        gas_limit: int = 1000,
        agent_id: str = "unknown-agent",
        capsule_id: str = "",
        requested_tier: str = "",
        variables_json: str = "{}",
        pointers_json: str = "{}",
        pointer_trust_mode: str = "enforce",
        approval_required_tags_json: str = "[]",
        approval_required_tools_json: str = "[]",
        approved_by: str = "",
        approval_token: str = "",
    ) -> dict[str, Any]:
        """Compile, capsule-validate, then execute HLF source within a sandboxed tier."""
        try:
            trusted_pointers = _parse_json_object(pointers_json, field_name="pointers_json")
            base_variables = _parse_json_object(variables_json, field_name="variables_json")
            approval_required_tags = _parse_json_string_list(
                approval_required_tags_json,
                field_name="approval_required_tags_json",
            )
            approval_required_tools = _parse_json_string_list(
                approval_required_tools_json,
                field_name="approval_required_tools_json",
            )
            result = ctx.compiler.compile(source)
            capsule = capsule_for_tier(
                tier,
                agent_id=agent_id,
                capsule_id=capsule_id or None,
                requested_tier=requested_tier or None,
                trusted_pointers=trusted_pointers,
                pointer_trust_mode=pointer_trust_mode,
                approval_required_tags=approval_required_tags,
                approval_required_tools=approval_required_tools,
                approved_by=approved_by,
                approval_token=approval_token,
            )
            stmts = result["ast"].get("statements", [])
            verification_admission = evaluate_verifier_admission(
                {"statements": stmts},
                verifier=ctx.formal_verifier,
                tier=tier,
                requested_tier=capsule.requested_tier,
            ).to_dict()
            verification_requirements = list(
                verification_admission.get("approval_requirements", [])
            )
            capsule, approval_request = _resolve_approval_request(
                ctx,
                capsule=capsule,
                statements=stmts,
                approved_by=approved_by,
                approval_token=approval_token,
                extra_requirements=verification_requirements,
            )
            approval_requirements = capsule._merged_requirements(stmts, verification_requirements)
            approval_granted = capsule.approval_granted(stmts, verification_requirements)
            effective_verification = _effective_verification_admission(
                verification_admission,
                approval_granted=approval_granted,
            )
            approval_token_value = capsule.expected_approval_token(stmts, verification_requirements)
            if approval_requirements and not approval_granted:
                execution_admission = ctx.persist_execution_admission(
                    agent_id=agent_id,
                    admission_record=_build_execution_admission_record(
                        ctx,
                        agent_id=agent_id,
                        capsule=capsule,
                        verification=effective_verification,
                        execution_status="approval_required",
                        approval_requirements=approval_requirements,
                        approval_request=approval_request,
                    ),
                )
                return {
                    "status": "approval_required",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "approval_requirements": approval_requirements,
                    "approval_token": approval_token_value,
                    "approval_request": approval_request,
                    "verification": effective_verification,
                    "execution_admission": execution_admission,
                    "capsule": capsule.to_dict(),
                }
            if not effective_verification.get("admitted", False):
                execution_admission = ctx.persist_execution_admission(
                    agent_id=agent_id,
                    admission_record=_build_execution_admission_record(
                        ctx,
                        agent_id=agent_id,
                        capsule=capsule,
                        verification=effective_verification,
                        execution_status="verification_denied",
                        approval_requirements=approval_requirements,
                        approval_request=approval_request,
                    ),
                )
                return {
                    "status": "verification_denied",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "verification": effective_verification,
                    "approval_requirements": approval_requirements,
                    "execution_admission": execution_admission,
                    "capsule": capsule.to_dict(),
                }
            violations = capsule.validate_ast(stmts, verification_requirements)
            if violations:
                execution_admission = ctx.persist_execution_admission(
                    agent_id=agent_id,
                    admission_record=_build_execution_admission_record(
                        ctx,
                        agent_id=agent_id,
                        capsule=capsule,
                        verification=effective_verification,
                        execution_status="capsule_violation",
                        approval_requirements=approval_requirements,
                        approval_request=approval_request,
                    ),
                )
                return {
                    "status": "capsule_violation",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "violations": violations,
                    "approval_requirements": approval_requirements,
                    "verification": effective_verification,
                    "execution_admission": execution_admission,
                    "capsule": capsule.to_dict(),
                }
            effective_gas = min(gas_limit, capsule.max_gas)
            bc = ctx.bytecoder.encode(result["ast"])
            runtime_variables = ctx.build_runtime_variables(base_variables, agent_id=agent_id)
            runtime_variables["_tier"] = capsule.requested_tier
            runtime_variables["_trusted_pointers"] = trusted_pointers
            runtime_variables["_pointer_trust_mode"] = pointer_trust_mode
            runtime_variables["_capsule"] = capsule.to_dict()
            runtime_variables["_verification_admission"] = effective_verification
            if approval_request is not None:
                runtime_variables["_capsule_request_id"] = approval_request.get("request_id")
            run_result = ctx.runtime.run(
                bc,
                gas_limit=effective_gas,
                variables=runtime_variables,
                ast=result["ast"],
                source=source,
                tier=capsule.requested_tier,
                audit_logger=ctx.audit_chain,
                verification_admission=effective_verification,
            )
            run_result["tier"] = tier
            run_result["requested_tier"] = capsule.requested_tier
            run_result["approval_request"] = approval_request
            run_result["verification"] = effective_verification
            run_result["execution_admission"] = ctx.persist_execution_admission(
                agent_id=agent_id,
                admission_record=_build_execution_admission_record(
                    ctx,
                    agent_id=agent_id,
                    capsule=capsule,
                    verification=effective_verification,
                    execution_status=str(run_result.get("status") or "ok"),
                    approval_requirements=approval_requirements,
                    approval_request=approval_request,
                    execution_audit=run_result.get("audit", {}).get("execution"),
                    side_effects=run_result.get("side_effects"),
                    runtime_variables=runtime_variables,
                ),
            )
            run_result["capsule"] = capsule.to_dict()
            return run_result
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}
        except CompileError as exc:
            return {"status": "compile_error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_pointer_validate(
        pointer: str,
        pointer_entry_json: str = "{}",
        content: str = "",
    ) -> dict[str, Any]:
        """Validate a canonical HLF pointer against registry metadata and optional content."""
        try:
            entry = _parse_json_object(pointer_entry_json, field_name="pointer_entry_json")
            return verify_pointer_ref(
                pointer,
                registry_entry=entry or None,
                content=content or None,
            )
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_host_functions(tier: str = "hearth") -> dict[str, Any]:
        """List host functions available for the given execution tier."""
        try:
            functions = ctx.host_registry.list_for_tier(tier)
            return {"status": "ok", "tier": tier, "functions": functions, "count": len(functions)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_host_call(
        function_name: str,
        args_json: str = "[]",
        tier: str = "hearth",
        requested_tier: str = "",
        capsule_id: str = "",
        approved_by: str = "",
        approval_token: str = "",
    ) -> dict[str, Any]:
        """Call a host function from the registry."""
        try:
            args = json.loads(args_json)
            if not isinstance(args, list):
                return {"status": "error", "error": "args_json must be a JSON array"}
            host_function = ctx.host_registry.get(function_name)
            policy_trace = host_function.policy_trace() if host_function else None
            capsule = capsule_for_tier(
                tier,
                capsule_id=capsule_id or None,
                requested_tier=requested_tier or None,
                approved_by=approved_by,
                approval_token=approval_token,
            )
            capsule, approval_request = _resolve_approval_request(
                ctx,
                capsule=capsule,
                statements=[],
                approved_by=approved_by,
                approval_token=approval_token,
            )
            approval_requirements = capsule.collect_approval_requirements([])
            if approval_requirements and not capsule.approval_granted([]):
                return {
                    "status": "approval_required",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "policy_trace": policy_trace,
                    "approval_requirements": approval_requirements,
                    "approval_token": capsule.expected_approval_token([]),
                    "approval_request": approval_request,
                    "capsule": capsule.to_dict(),
                }
            violations = capsule.validate_host_function(function_name)
            if violations:
                return {
                    "status": "capsule_violation",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "policy_trace": policy_trace,
                    "violations": violations,
                    "capsule": capsule.to_dict(),
                }
            result = ctx.host_registry.call(function_name, args, capsule.requested_tier)
            return {
                "status": "ok",
                "result": result,
                "policy_trace": result.get("policy_trace"),
                "approval_request": approval_request,
            }
        except json.JSONDecodeError as exc:
            return {"status": "error", "error": f"Invalid args_json: {exc}"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_capsule_review_queue(
        status: str = "pending", limit: int = 20, capsule_id: str = ""
    ) -> dict[str, Any]:
        """List persisted capsule approval requests for operator review."""
        try:
            normalized_status = status.strip().lower()
            effective_status = (
                normalized_status
                if normalized_status in {"pending", "approved", "rejected", "all"}
                else "pending"
            )
            requests = ctx.approval_ledger.list_requests(
                status=None if effective_status == "all" else effective_status,
                limit=limit,
                capsule_id=capsule_id or None,
            )
            return {"status": "ok", "requests": requests, "count": len(requests)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_capsule_review_decide(
        request_id: str,
        decision: str,
        operator: str,
        approval_token: str = "",
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve or reject a persisted capsule review request."""
        try:
            request = ctx.approval_ledger.decide(
                request_id=request_id,
                decision=decision,
                operator=operator,
                approval_token=approval_token,
                reason=reason,
            )
            return {"status": "ok", "request": request.to_dict()}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_tool_list() -> dict[str, Any]:
        """List all tools registered in the HLF ToolRegistry."""
        try:
            tools = ctx.tool_registry.list_tools()
            return {"status": "ok", "tools": tools, "count": len(tools)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_similarity_gate(source_a: str, source_b: str) -> dict[str, Any]:
        """Compare two HLF programs for semantic similarity using InsAIts similarity gate."""
        try:
            result_a = ctx.compiler.compile(source_a)
            result_b = ctx.compiler.compile(source_b)
            text_a = insaits.decompile(result_a["ast"])
            text_b = insaits.decompile(result_b["ast"])
            score = insaits.similarity_gate(text_a, text_b)
            return {"status": "ok", "similarity": score}
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    return {
        "hlf_capsule_validate": hlf_capsule_validate,
        "hlf_capsule_run": hlf_capsule_run,
        "hlf_capsule_review_decide": hlf_capsule_review_decide,
        "hlf_capsule_review_queue": hlf_capsule_review_queue,
        "hlf_pointer_validate": hlf_pointer_validate,
        "hlf_host_functions": hlf_host_functions,
        "hlf_host_call": hlf_host_call,
        "hlf_tool_list": hlf_tool_list,
        "hlf_similarity_gate": hlf_similarity_gate,
    }
