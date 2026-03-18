from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.memory_node import verify_pointer_ref
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.server_context import ServerContext


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
) -> tuple[Any, dict[str, Any] | None]:
    requirements = capsule.collect_approval_requirements(statements)
    if not requirements:
        return capsule, None

    request = ctx.approval_ledger.ensure_request(
        capsule_id=capsule.capsule_id,
        agent_id=capsule.agent_id,
        base_tier=capsule.base_tier,
        requested_tier=capsule.requested_tier,
        requirements=requirements,
        approval_token=capsule.expected_approval_token(statements),
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
            capsule, approval_request = _resolve_approval_request(
                ctx,
                capsule=capsule,
                statements=stmts,
                approved_by=approved_by,
                approval_token=approval_token,
            )
            violations = capsule.validate_ast(stmts)
            approval_requirements = capsule.collect_approval_requirements(stmts)
            return {
                "status": "ok",
                "tier": tier,
                "requested_tier": capsule.requested_tier,
                "agent_id": agent_id,
                "violations": violations,
                "approval_required": bool(approval_requirements) and not capsule.approval_granted(stmts),
                "approval_granted": capsule.approval_granted(stmts),
                "approval_requirements": approval_requirements,
                "approval_token": capsule.expected_approval_token(stmts),
                "approval_request": approval_request,
                "passed": len(violations) == 0,
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
            capsule, approval_request = _resolve_approval_request(
                ctx,
                capsule=capsule,
                statements=stmts,
                approved_by=approved_by,
                approval_token=approval_token,
            )
            approval_requirements = capsule.collect_approval_requirements(stmts)
            approval_token_value = capsule.expected_approval_token(stmts)
            if approval_requirements and not capsule.approval_granted(stmts):
                return {
                    "status": "approval_required",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "approval_requirements": approval_requirements,
                    "approval_token": approval_token_value,
                    "approval_request": approval_request,
                    "capsule": capsule.to_dict(),
                }
            violations = capsule.validate_ast(stmts)
            if violations:
                return {
                    "status": "capsule_violation",
                    "tier": tier,
                    "requested_tier": capsule.requested_tier,
                    "violations": violations,
                    "approval_requirements": approval_requirements,
                    "capsule": capsule.to_dict(),
                }
            effective_gas = min(gas_limit, capsule.max_gas)
            bc = ctx.bytecoder.encode(result["ast"])
            runtime_variables = ctx.build_runtime_variables(base_variables, agent_id=agent_id)
            runtime_variables["_tier"] = capsule.requested_tier
            runtime_variables["_trusted_pointers"] = trusted_pointers
            runtime_variables["_pointer_trust_mode"] = pointer_trust_mode
            runtime_variables["_capsule"] = capsule.to_dict()
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
            )
            run_result["tier"] = tier
            run_result["requested_tier"] = capsule.requested_tier
            run_result["approval_request"] = approval_request
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
                    "violations": violations,
                    "capsule": capsule.to_dict(),
                }
            result = ctx.host_registry.call(function_name, args, capsule.requested_tier)
            return {"status": "ok", "result": result, "approval_request": approval_request}
        except json.JSONDecodeError as exc:
            return {"status": "error", "error": f"Invalid args_json: {exc}"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_capsule_review_queue(status: str = "pending", limit: int = 20, capsule_id: str = "") -> dict[str, Any]:
        """List persisted capsule approval requests for operator review."""
        try:
            normalized_status = status.strip().lower()
            effective_status = normalized_status if normalized_status in {"pending", "approved", "rejected", "all"} else "pending"
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