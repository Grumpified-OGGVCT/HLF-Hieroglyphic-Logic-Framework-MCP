from __future__ import annotations

import hashlib
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.execution_admission import evaluate_verification_report_admission
from hlf_mcp.hlf.execution_admission import summarize_execution_effects
from hlf_mcp.hlf.formal_verifier import VerificationReport
from hlf_mcp.server_context import ServerContext


def _verifier_knowledge_query(*, source: str | None, ast: dict[str, Any]) -> str:
    if source:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        return f"formal_verifier_ast:{digest}"
    ast_fingerprint = str(ast.get("sha256") or "").strip()
    if ast_fingerprint:
        return f"formal_verifier_ast:{ast_fingerprint}"
    canonical_ast = hashlib.sha256(
        json.dumps(ast, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"formal_verifier_ast:{canonical_ast}"


def _build_verification_justification(
    *,
    report: dict[str, Any],
    admission: dict[str, Any],
    effect_summary: dict[str, Any],
    agent_id: str,
    trust_state: str,
) -> dict[str, Any]:
    failed_count = int(report.get("failed", report.get("failed_count", 0)) or 0)
    unknown_count = int(report.get("unknown", 0) or 0)
    skipped_count = int(report.get("skipped", 0) or 0)
    error_count = int(report.get("errors", 0) or 0)
    admitted = bool(admission.get("admitted", False))
    review_required = bool(admission.get("requires_operator_review", False))
    if not admitted and not review_required:
        primary_reason = "Verification failed closed because one or more proof obligations did not satisfy packaged admission rules."
    elif review_required:
        primary_reason = "Verification preserved an operator-review gate because proof coverage or execution posture remained non-final."
    else:
        primary_reason = "Verification admitted the request because packaged proof obligations stayed inside the current policy posture."
    return {
        "agent_id": agent_id,
        "trust_state": trust_state,
        "verdict": admission.get("verdict"),
        "admitted": admitted,
        "review_required": review_required,
        "policy_posture": admission.get("policy_posture"),
        "proof_status": report.get("status") or admission.get("status") or "unknown",
        "failed_count": failed_count,
        "unknown_count": unknown_count,
        "skipped_count": skipped_count,
        "error_count": error_count,
        "effectful": bool(effect_summary.get("effectful", False)),
        "effect_classes": list(effect_summary.get("effect_classes", [])),
        "primary_reason": primary_reason,
    }


def _apply_knowledge_contract_gate(
    *,
    admission: dict[str, Any],
    knowledge_contract: dict[str, Any],
    requested_tier: str,
    effect_summary: dict[str, Any],
) -> dict[str, Any]:
    gated = dict(admission)
    effectful = bool(effect_summary.get("effectful", False)) or str(gated.get("operation_class") or "read_only") != "read_only"
    elevated = str(requested_tier or "").strip().lower() in {"forge", "sovereign"}
    verdict = str(gated.get("verdict") or "")
    already_constrained = bool(gated.get("requires_operator_review", False)) or verdict == "verification_denied"

    if not knowledge_contract:
        if (effectful or elevated) and not already_constrained:
            reasons = list(gated.get("reasons") or [])
            message = "Governed HKS verifier-evidence contract is missing for this effectful or elevated request."
            if message not in reasons:
                reasons.append(message)
            gated["reasons"] = reasons
            gated["admitted"] = False
            gated["requires_operator_review"] = True
            gated["verdict"] = "knowledge_review_required"
            gated["policy_posture"] = "knowledge_constrained"
            gated["risk_factors"] = [
                *list(gated.get("risk_factors") or []),
                "knowledge_contract_missing",
            ]
        gated["knowledge_gate"] = {
            "available": False,
            "decision": "review_required" if (effectful or elevated) and bool(gated.get("requires_operator_review", False)) else "not_evaluated",
            "admitted": not bool(gated.get("requires_operator_review", False)),
            "review_required": bool(gated.get("requires_operator_review", False)),
            "knowledge_contract": {},
        }
        return gated

    if bool(knowledge_contract.get("reference_allowed", False)):
        gated["knowledge_gate"] = {
            "available": True,
            "decision": "allow",
            "admitted": True,
            "review_required": False,
            "knowledge_contract": knowledge_contract,
        }
        return gated

    if effectful or elevated:
        if already_constrained:
            gated["knowledge_gate"] = {
                "available": True,
                "decision": "review_required",
                "admitted": False,
                "review_required": True,
                "knowledge_contract": knowledge_contract,
            }
            return gated
        reasons = list(gated.get("reasons") or [])
        message = "Governed HKS verifier-evidence contract did not clear trust, freshness, provenance, and graph thresholds for this effectful or elevated request."
        if message not in reasons:
            reasons.append(message)
        gated["reasons"] = reasons
        gated["admitted"] = False
        gated["requires_operator_review"] = True
        gated["verdict"] = "knowledge_review_required"
        gated["policy_posture"] = "knowledge_constrained"
        gated["risk_factors"] = [*list(gated.get("risk_factors") or []), "knowledge_contract_missing"]
        gated["knowledge_gate"] = {
            "available": True,
            "decision": "review_required",
            "admitted": False,
            "review_required": True,
            "knowledge_contract": knowledge_contract,
        }
        return gated

    gated["knowledge_gate"] = {
        "available": True,
        "decision": "advisory_only",
        "admitted": False,
        "review_required": False,
        "knowledge_contract": knowledge_contract,
    }
    return gated


def register_verifier_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_verify_formal_ast(
        ast: dict[str, Any] | None = None,
        source: str | None = None,
        gas_budget: int = 10_000,
        agent_id: str = "",
        trust_state: str = "healthy",
        requested_tier: str = "hearth",
        mode: str = "enforce",
    ) -> dict[str, Any]:
        """Run packaged formal verification over an HLF AST or source, covering type invariants, gas bounds, and extracted spec gates."""
        effective_ast = ast
        if effective_ast is None:
            if not source:
                return {"status": "error", "error": "Either ast or source is required."}
            compile_result = ctx.compiler.compile(source)
            effective_ast = compile_result.get("ast")
        if not isinstance(effective_ast, dict):
            return {"status": "error", "error": "Formal verification requires a dict AST."}

        report = ctx.formal_verifier.verify_ast(effective_ast, gas_budget=gas_budget)
        normalized_agent_id = str(agent_id or "").strip()
        effective_trust_state = ctx.get_effective_trust_state(
            subject_agent_id=normalized_agent_id,
            default=trust_state,
        )
        knowledge_query = _verifier_knowledge_query(source=source, ast=effective_ast)
        knowledge_evidence = ctx.memory_store.query(
            knowledge_query,
            top_k=3,
            min_confidence=0.0,
            require_provenance=True,
            purpose="verifier_evidence",
        )
        knowledge_contract = dict(knowledge_evidence.get("governed_hks_contract") or {})
        effect_summary = summarize_execution_effects(effective_ast)
        admission = evaluate_verification_report_admission(
            report,
            tier="hearth",
            requested_tier=requested_tier,
            mode=mode,
            trust_state=effective_trust_state,
            effect_summary=effect_summary,
            unknown_reason="Formal verification returned unknown proof results for this packaged AST.",
            incomplete_reason="Formal verification extracted only advisory proof coverage for this packaged AST.",
            skipped_reason="Formal verification admitted this packaged AST with skipped proof checks.",
        )
        report_payload = report.to_dict()
        admission_payload = _apply_knowledge_contract_gate(
            admission=admission.to_dict(),
            knowledge_contract=knowledge_contract,
            requested_tier=requested_tier,
            effect_summary=effect_summary,
        )
        justification = _build_verification_justification(
            report=report_payload,
            admission=admission_payload,
            effect_summary=effect_summary,
            agent_id=normalized_agent_id,
            trust_state=effective_trust_state,
        )
        audit = ctx.audit_chain.log(
            "hlf_verify_formal_ast",
            {
                "gas_budget": gas_budget,
                "solver_name": ctx.formal_verifier.solver_name,
                "report": report_payload,
                "admission": admission_payload,
                "justification": justification,
                "knowledge_contract": knowledge_contract,
            },
            agent_role="formal_verifier",
            goal_id="formal_ast_verification",
            anomaly_score=1.0 if not admission.admitted and not admission.requires_operator_review else 0.5 if admission.requires_operator_review else 0.0,
        )
        governance_event = ctx.emit_governance_event(
            kind="formal_verification",
            source="server_verifier.hlf_verify_formal_ast",
            action="verify_formal_ast",
            status="blocked"
            if not admission.admitted and not admission.requires_operator_review
            else "warning"
            if admission.requires_operator_review
            else "ok",
            severity="critical"
            if not admission.admitted and not admission.requires_operator_review
            else "warning"
            if admission.requires_operator_review
            else "info",
            details={
                "gas_budget": gas_budget,
                "solver_name": ctx.formal_verifier.solver_name,
                "audit_trace_id": audit.get("trace_id"),
                "report": report_payload,
                "admission": admission_payload,
                "effect_summary": effect_summary,
                "agent_id": normalized_agent_id,
                "trust_state": effective_trust_state,
                "knowledge_evidence": knowledge_evidence,
                "knowledge_contract": knowledge_contract,
                "justification": justification,
            },
            agent_role="formal_verifier",
            anomaly_score=1.0 if not admission.admitted and not admission.requires_operator_review else 0.5 if admission.requires_operator_review else 0.0,
        )
        witness_observation = ctx.persist_subject_verifier_consequence(
            subject_agent_id=normalized_agent_id,
            source="server_verifier.hlf_verify_formal_ast",
            admission=admission_payload,
            report=report_payload,
            governance_event_ref=governance_event.get("event_ref"),
            effect_summary=effect_summary,
        )
        return {
            "status": "ok",
            "solver_name": ctx.formal_verifier.solver_name,
            "agent_id": normalized_agent_id,
            "trust_state": effective_trust_state,
            "report": report_payload,
            "admission": admission_payload,
            "justification": justification,
            "knowledge_evidence": knowledge_evidence,
            "knowledge_contract": knowledge_contract,
            "audit": audit,
            "governance_event": governance_event,
            "witness_observation": witness_observation,
            "witness_status": ctx.get_witness_status(subject_agent_id=normalized_agent_id)
            if normalized_agent_id
            else None,
        }

    @mcp.tool()
    def hlf_verify_gas_budget(
        task_costs: list[int],
        budget: int,
        property_name: str = "gas_budget",
        agent_id: str = "",
        trust_state: str = "healthy",
        requested_tier: str = "hearth",
        mode: str = "enforce",
    ) -> dict[str, Any]:
        """Prove or refute that a deterministic gas budget covers the supplied task costs."""
        result = ctx.formal_verifier.verify_gas_budget(
            task_costs, budget, property_name=property_name
        )
        report = VerificationReport()
        report.add(result)
        normalized_agent_id = str(agent_id or "").strip()
        effective_trust_state = ctx.get_effective_trust_state(
            subject_agent_id=normalized_agent_id,
            default=trust_state,
        )
        knowledge_evidence = ctx.memory_store.query(
            property_name,
            top_k=3,
            min_confidence=0.0,
            require_provenance=True,
            purpose="verifier_evidence",
        )
        knowledge_contract = dict(knowledge_evidence.get("governed_hks_contract") or {})
        effect_summary = {
            "node_count": 1,
            "tags": ["VERIFY"],
            "tools": [],
            "effectful_tags": [],
            "effectful": False,
        }
        admission = evaluate_verification_report_admission(
            report,
            tier="hearth",
            requested_tier=requested_tier,
            mode=mode,
            trust_state=effective_trust_state,
            effect_summary=effect_summary,
            operation_class="read_only",
            unknown_reason="Formal gas-budget verification returned an unknown proof result.",
            incomplete_reason="Formal gas-budget verification did not produce a deterministic proof contract.",
            skipped_reason="Formal gas-budget verification admitted analysis with skipped proof checks.",
        )
        report_payload = report.to_dict()
        admission_payload = _apply_knowledge_contract_gate(
            admission=admission.to_dict(),
            knowledge_contract=knowledge_contract,
            requested_tier=requested_tier,
            effect_summary=effect_summary,
        )
        justification = _build_verification_justification(
            report=report_payload,
            admission=admission_payload,
            effect_summary=effect_summary,
            agent_id=normalized_agent_id,
            trust_state=effective_trust_state,
        )
        audit = ctx.audit_chain.log(
            "hlf_verify_gas_budget",
            {
                "budget": budget,
                "property_name": property_name,
                "task_costs": list(task_costs),
                "result": result.to_dict(),
                "admission": admission_payload,
                "justification": justification,
                "knowledge_contract": knowledge_contract,
            },
            agent_role="formal_verifier",
            goal_id=property_name,
            anomaly_score=1.0 if not admission.admitted and not admission.requires_operator_review else 0.5 if admission.requires_operator_review else 0.0,
        )
        governance_event = ctx.emit_governance_event(
            kind="formal_verification",
            source="server_verifier.hlf_verify_gas_budget",
            action="verify_gas_budget",
            status="blocked"
            if not admission.admitted and not admission.requires_operator_review
            else "warning"
            if admission.requires_operator_review
            else "ok",
            severity="critical"
            if not admission.admitted and not admission.requires_operator_review
            else "warning"
            if admission.requires_operator_review
            else "info",
            details={
                "budget": budget,
                "task_costs": list(task_costs),
                "property_name": property_name,
                "audit_trace_id": audit.get("trace_id"),
                "result": result.to_dict(),
                "report": report_payload,
                "admission": admission_payload,
                "agent_id": normalized_agent_id,
                "trust_state": effective_trust_state,
                "knowledge_evidence": knowledge_evidence,
                "knowledge_contract": knowledge_contract,
                "justification": justification,
            },
            agent_role="formal_verifier",
            anomaly_score=1.0 if not admission.admitted and not admission.requires_operator_review else 0.5 if admission.requires_operator_review else 0.0,
        )
        witness_observation = ctx.persist_subject_verifier_consequence(
            subject_agent_id=normalized_agent_id,
            source="server_verifier.hlf_verify_gas_budget",
            admission=admission_payload,
            report=report_payload,
            governance_event_ref=governance_event.get("event_ref"),
            effect_summary=effect_summary,
        )
        return {
            "status": "ok",
            "agent_id": normalized_agent_id,
            "trust_state": effective_trust_state,
            "result": result.to_dict(),
            "admission": admission_payload,
            "justification": justification,
            "knowledge_evidence": knowledge_evidence,
            "knowledge_contract": knowledge_contract,
            "audit": audit,
            "governance_event": governance_event,
            "witness_observation": witness_observation,
            "witness_status": ctx.get_witness_status(subject_agent_id=normalized_agent_id)
            if normalized_agent_id
            else None,
        }

    return {
        "hlf_verify_formal_ast": hlf_verify_formal_ast,
        "hlf_verify_gas_budget": hlf_verify_gas_budget,
    }
