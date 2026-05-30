from __future__ import annotations

import json
import types
from collections.abc import Mapping
from typing import Any

from hlf_mcp.hlf.governance_proofs import sha256_digest, verify_governance_proof

ENFORCEMENT_STATUS = "mcp_enforcement_rejected"

# Bootstrap and discovery tools must remain usable before an agent has a proof.
SAFE_BOOTSTRAP_TOOLS: frozenset[str] = frozenset(
    {
        "hlf_do",
        "sg_orchestrate",
        "hlf_translate_to_hlf",
        "hlf_governed_swarm_mechanics",
        "hlf_translate_repair",
        "hlf_translate_resilient",
        # Pure read-only HLF -> NLP egress. It compiles/decompiles the caller's
        # supplied source only and does not mutate protected state.
        "hlf_translate_to_english",
        "hlf_validate",
        "hlf_lint",
        "hlf_compile",
        "hlf_format",
        "hlf_governance_proof_verify",
        "hlf_translation_memory_query",
        "hlf_test_suite_summary",
        "hlf_benchmark",
        "hlf_benchmark_suite",
        "hlf_benchmark_matrix",
        "hlf_translation_memory_benchmark",
        "hlf_routing_context_benchmark",
        "hlf_real_workflow_benchmark",
        "hlf_weekly_evidence_summary",
        "hlf_recommend_embedding_profile",
        "hlf_query_profile_capabilities",
        "hlf_list_profiles",
        "hlf_get_profile",
        "hlf_authority_matrix",
        # Swarm observation tools — read-only, safe for bootstrap
        "hlf_swarm_run",
        "hlf_swarm_progress",
        "hlf_swarm_witness",
        "hlf_swarm_verify",
        # ── SwarmGlass governance tools (sg_* variants) ──────────────────
        # These ARE the governance framework. Requiring a governance proof
        # to call governance tools would be a bootstrap deadlock.
        # Memory
        "sg_memory_store",
        "sg_memory_governed_recall",
        "sg_memory_query",
        "sg_memory_dream_run",
        "sg_memory_register_evidence_bundle",
        "sg_memory_hks_research",
        # Overwatch
        "sg_overwatch_scan",
        "sg_overwatch_health",
        "sg_overwatch_status",
        "sg_overwatch_terminate",
        # Secure
        "sg_secure_secret_store",
        "sg_secure_secret_retrieve",
        "sg_secure_secret_rotate",
        # Coordinate
        "sg_coordinate_orchestration_contract",
        "sg_coordinate_handoff_chain",
        # Audit
        "sg_audit_event_log",
        "sg_audit_merkle_verify",
        "sg_audit_evidence_show",
        # Model
        "sg_model_version_check",
        # Observe
        "sg_observe_drift",
    }
)

PROOF_ARGUMENT_KEYS: frozenset[str] = frozenset(
    {
        "hlf_contract",
        "translation_contract",
        "internal_loop_contract",
        "hlf_governance_proof",
        "governance_proof",
    }
)


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return False
    return True


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _contract_from_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("hlf_contract", "translation_contract"):
        value = arguments.get(key)
        if isinstance(value, dict):
            return value
    loop = arguments.get("internal_loop_contract")
    if isinstance(loop, dict):
        return {"internal_loop_contract": loop}
    return {}


def _tool_action(tool_name: str, arguments: Mapping[str, Any]) -> str:
    for key in ("action", "operation", "mode"):
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{tool_name}.call"


def _strip_enforcement_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(arguments).items() if key not in PROOF_ARGUMENT_KEYS}


def normalized_mcp_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return _strip_enforcement_arguments(arguments)


def build_mcp_call_binding(tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = normalized_mcp_arguments(arguments)
    return {
        "tool_name": tool_name,
        "action": _tool_action(tool_name, cleaned),
        "arguments_sha256": sha256_digest(cleaned),
    }


def _binding_from_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("mcp_binding", "target_binding", "tool_binding"):
        value = contract.get(key)
        if isinstance(value, dict):
            return value
    for section_name in ("governance", "proof", "artifacts", "internal_loop_contract"):
        section = contract.get(section_name)
        if isinstance(section, dict):
            for key in ("mcp_binding", "target_binding", "tool_binding"):
                value = section.get(key)
                if isinstance(value, dict):
                    return value
    return {}


def _binding_from_proof(proof: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("mcp_binding", "target_binding", "tool_binding"):
        value = proof.get(key)
        if isinstance(value, dict):
            return value
    replay = proof.get("deterministic_replay")
    if isinstance(replay, dict):
        scope = replay.get("scope")
        if isinstance(scope, dict):
            for key in ("mcp_binding", "target_binding", "tool_binding"):
                value = scope.get(key)
                if isinstance(value, dict):
                    return value
            if any(key in scope for key in ("tool_name", "target_tool", "tool", "arguments_sha256", "args_sha256")):
                return scope
    return {}


def _verify_mcp_binding(
    binding: Mapping[str, Any],
    tool_name: str,
    arguments: Mapping[str, Any],
) -> tuple[bool, str]:
    if not binding:
        return False, "missing_mcp_tool_binding"
    expected = build_mcp_call_binding(tool_name, arguments)
    bound_tool = str(binding.get("tool_name") or binding.get("target_tool") or binding.get("tool") or "")
    if bound_tool != expected["tool_name"]:
        return False, "mcp_binding_tool_mismatch"
    bound_action = str(binding.get("action") or binding.get("tool_action") or "")
    if bound_action != expected["action"]:
        return False, "mcp_binding_action_mismatch"
    bound_args_hash = str(
        binding.get("arguments_sha256")
        or binding.get("args_sha256")
        or binding.get("arguments_hash")
        or ""
    )
    if not bound_args_hash:
        return False, "mcp_binding_missing_arguments_sha256"
    if bound_args_hash != expected["arguments_sha256"]:
        return False, "mcp_binding_arguments_sha256_mismatch"
    return True, "mcp_binding_verified"


def _source_from_contract(contract: Mapping[str, Any]) -> str:
    canonical = contract.get("canonical_hlf")
    if isinstance(canonical, dict):
        return str(canonical.get("source") or "")
    artifacts = contract.get("artifacts")
    if isinstance(artifacts, dict):
        return str(artifacts.get("source") or "")
    return ""


def _verify_contract(
    ctx: Any,
    contract: Mapping[str, Any],
    tool_name: str,
    arguments: Mapping[str, Any],
) -> tuple[bool, str]:
    binding_ok, binding_reason = _verify_mcp_binding(
        _binding_from_contract(contract),
        tool_name,
        arguments,
    )
    if not binding_ok:
        return False, binding_reason

    loop = _as_dict(contract.get("internal_loop_contract"))
    governance = _as_dict(contract.get("governance"))
    proof = _as_dict(contract.get("proof"))
    artifacts = _as_dict(contract.get("artifacts"))
    source = _source_from_contract(contract)

    if not source:
        return False, "contract_missing_canonical_hlf_source"
    requested_source = str(arguments.get("source") or "")
    if requested_source and requested_source != source:
        return False, "request_source_does_not_match_contract"

    validation = ctx.compiler.validate(source)
    if not validation.get("valid"):
        return False, "contract_source_failed_validation"
    compile_result = ctx.compiler.compile(source)
    ast_sha = str(compile_result.get("ast", {}).get("sha256") or "")
    declared_sha = str(_as_dict(contract.get("canonical_hlf")).get("ast_sha256") or "")
    if declared_sha and declared_sha != ast_sha:
        return False, "contract_ast_sha256_mismatch"

    gates = _as_dict(loop.get("gates"))
    if loop and not (gates.get("validation") and gates.get("compile")):
        return False, "contract_internal_loop_gates_not_passed"
    if governance and governance.get("governed") is False:
        return False, "contract_governance_not_governed"
    if proof and not _as_dict(proof.get("compile")):
        return False, "contract_missing_compile_proof"
    if artifacts and not artifacts.get("bytecode_hex"):
        return False, "contract_missing_bytecode_artifact"
    return True, "validated_hlf_contract"


def _verify_proof(tool_name: str, arguments: Mapping[str, Any]) -> tuple[bool, str]:
    for key in ("hlf_governance_proof", "governance_proof"):
        proof = arguments.get(key)
        if isinstance(proof, dict):
            binding_ok, binding_reason = _verify_mcp_binding(
                _binding_from_proof(proof),
                tool_name,
                arguments,
            )
            if not binding_ok:
                return False, binding_reason
            report = verify_governance_proof(proof)
            if report.get("verified") is True:
                return True, f"verified_{key}"
            return False, f"invalid_{key}"
    return False, "missing_governance_proof"


def assess_mcp_call(ctx: Any, tool_name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if tool_name in SAFE_BOOTSTRAP_TOOLS:
        return {"allowed": True, "mode": "bootstrap_allowlist", "reason": "safe_bootstrap_tool"}

    contract = _contract_from_arguments(arguments)
    if contract:
        ok, reason = _verify_contract(ctx, contract, tool_name, arguments)
        return {"allowed": ok, "mode": "hlf_contract", "reason": reason}

    ok, reason = _verify_proof(tool_name, arguments)
    return {"allowed": ok, "mode": "governance_proof", "reason": reason}


def _denial(tool_name: str, assessment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": ENFORCEMENT_STATUS,
        "allowed": False,
        "tool": tool_name,
        "error": "Protected MCP tool calls require a validated HLF contract or governance proof.",
        "reason": assessment.get("reason") or "missing_hlf_contract_or_proof",
        "bootstrap_tools": sorted(SAFE_BOOTSTRAP_TOOLS),
    }


def _egress_checked_result(tool_name: str, result: Any, assessment: Mapping[str, Any]) -> Any:
    if not _json_safe(result):
        return {
            "status": ENFORCEMENT_STATUS,
            "allowed": False,
            "tool": tool_name,
            "error": "MCP tool output failed JSON egress validation.",
        }
    if isinstance(result, dict) and assessment.get("mode") != "bootstrap_allowlist":
        result = dict(result)
        result["mcp_enforcement"] = {
            "allowed": True,
            "mode": assessment.get("mode"),
            "reason": assessment.get("reason"),
            "egress_validated": True,
        }
    return result


def install_mcp_enforcement(mcp: Any, ctx: Any) -> None:
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is None or getattr(tool_manager, "_hlf_mcp_enforcement_installed", False):
        return

    async def enforced_call_tool(
        self: Any,
        name: str,
        arguments: dict[str, Any],
        context: Any = None,
        convert_result: bool = False,
    ) -> Any:
        tool = self.get_tool(name)
        if tool is None:
            return await original_call_tool(name, arguments, context=context, convert_result=convert_result)

        assessment = assess_mcp_call(ctx, name, arguments or {})
        if not assessment.get("allowed"):
            denial = _denial(name, assessment)
            return tool.fn_metadata.convert_result(denial) if convert_result else denial

        cleaned_arguments = _strip_enforcement_arguments(arguments or {})
        result = await tool.run(cleaned_arguments, context=context, convert_result=False)
        result = _egress_checked_result(name, result, assessment)
        return tool.fn_metadata.convert_result(result) if convert_result else result

    original_call_tool = tool_manager.call_tool
    tool_manager._hlf_mcp_original_call_tool = original_call_tool
    tool_manager.call_tool = types.MethodType(enforced_call_tool, tool_manager)
    tool_manager._hlf_mcp_enforcement_installed = True
