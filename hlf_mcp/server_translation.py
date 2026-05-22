from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.ethics.constitution import evaluate_constitution as _evaluate_constitution
from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge
from hlf_mcp.hlf.translator import (
    build_translation_repair_plan,
    hlf_to_english,
    hlf_to_language,
    language_to_hlf,
    normalize_cognitive_lane_policy,
    resolve_language,
    resolve_language_with_policy,
    translation_diagnostics,
)
from hlf_mcp.ingress_support import (
    build_ingress_denial_reasons,
    persist_runtime_execution_admission,
    resolve_execution_ingress_contract,
)
from hlf_mcp.mcp_enforcement import build_mcp_call_binding
from hlf_mcp.server_context import ServerContext
from hlf_mcp.server_core import run_hlf_swarm_mechanics


def _build_translation_contract(
    ctx: ServerContext,
    *,
    intent: str,
    source: str,
    resolved_language: str,
    language_policy: dict[str, Any],
    tier: str,
    diagnostics: dict[str, Any],
    compile_result: dict[str, Any],
    capsule_violations: list[dict[str, Any]] | list[str],
    align_violations: list[dict[str, Any]] | list[str],
    localized_audit: str,
    english_audit: str,
    benchmark: dict[str, Any],
) -> dict[str, Any]:
    ast = compile_result["ast"]
    bytecode = ctx.bytecoder.encode(ast)
    validation = ctx.compiler.validate(source)
    governed = len(capsule_violations) == 0 and len(align_violations) == 0
    operator_summary = (
        f"Intent was translated from {resolved_language} into canonical HLF and compiled "
        f"to bytecode with governance status {'governed' if governed else 'review-required'}."
    )

    return {
        "contract_version": "1.0",
        "operator_summary": operator_summary,
        "intent": {
            "text": intent,
            "language": resolved_language,
            "tier": tier,
        },
        "language_policy": language_policy,
        "canonical_hlf": {
            "source": source,
            "version": compile_result.get("version"),
            "statement_count": compile_result.get("node_count", 0),
            "ast_sha256": ast.get("sha256", ""),
        },
        "governance": {
            "governed": governed,
            "capsule_violations": list(capsule_violations),
            "align_violations": list(align_violations),
            "validation": validation,
        },
        "proof": {
            "translation": diagnostics,
            "compile": {
                "node_count": compile_result.get("node_count", 0),
                "gas_estimate": compile_result.get("gas_estimate", 0),
                "normalization_changes": list(compile_result.get("normalization_changes", [])),
            },
            "math": {
                "english_tokens": benchmark.get("nlp_tokens", 0),
                "hlf_tokens": benchmark.get("hlf_tokens", 0),
                "compression_pct": benchmark.get("compression_pct", 0.0),
                "token_savings": benchmark.get("savings", 0),
            },
            "audit_surfaces": {
                "localized_summary": localized_audit,
                "english_summary": english_audit,
                "bytecode_summary_en": insaits.decompile_bytecode(bytecode),
            },
        },
        "artifacts": {
            "primary_target": "hlf-bytecode",
            "bytecode_hex": bytecode.hex(),
            "bytecode_size_bytes": len(bytecode),
            "runtime": "HLFRuntime",
        },
    }


def _normalize_handoff_mode(handoff_mode: str) -> str:
    mode = str(handoff_mode or "operator").strip().lower().replace("-", "_")
    aliases = {
        "": "operator",
        "human": "operator",
        "nlp": "operator",
        "raw": "raw_hlf",
        "hlf": "raw_hlf",
        "agent": "subagent",
        "sub_agent": "subagent",
        "fleet": "swarm",
    }
    return aliases.get(mode, mode if mode in {"operator", "raw_hlf", "swarm", "subagent"} else "operator")


def _apply_normalization_gate(
    ctx: Any,  # ServerContext (circular-import avoidance)
    text: str,
    *,
    skip_normalization: bool = False,
) -> dict[str, Any]:
    """Run the IntentNormalizer gate over *text* before HLF translation.

    Returns a dict with:
        text       — the (possibly rewritten) intent string
        verdict    — NormalizationVerdict.to_dict() or None
        rejected   — bool: score too low for rewrite
        rewritten  — bool: score in rewrite zone and rewritten
        reason     — str|None: rejection explanation
        findings   — list[str]: score deductions
        normalization — dict: summary (score, rewritten, etc.)
    """
    if skip_normalization:
        return {
            "text": text,
            "verdict": None,
            "rejected": False,
            "rewritten": False,
            "normalization": None,
            "reason": None,
            "findings": [],
        }

    normalizer = ctx.intent_normalizer
    verdict = normalizer.normalize(text)
    verdict_dict = verdict.to_dict()

    rejected = not verdict.threshold_passed and verdict.rewritten_intent is None
    rewritten = verdict.rewritten_intent is not None
    anomaly_score = (1.0 - verdict.score) if rejected else 0.0

    result_text = text
    if rewritten:
        result_text = verdict.rewritten_intent

    result: dict[str, Any] = {
        "text": result_text,
        "verdict": verdict_dict,
        "rejected": rejected,
        "rewritten": rewritten,
        "reason": verdict.rejection_reason,
        "findings": list(verdict.findings),
        "normalization": {
            "score": verdict.score,
            "threshold_passed": verdict.threshold_passed,
            "rejected": rejected,
            "rewritten": rewritten,
            "rewritten_intent": verdict.rewritten_intent,
            "rejection_reason": verdict.rejection_reason,
            "findings": list(verdict.findings),
        },
    }

    ctx.audit_chain.log(
        "intent_normalized",
        {
            "score": verdict.score,
            "original_intent": text,
            "verdict": verdict_dict,
        },
        anomaly_score=anomaly_score,
    )

    return result


def _build_internal_loop_contract(
    *,
    surface: str,
    intent: str,
    source: str,
    validation: dict[str, Any],
    compile_result: dict[str, Any] | None = None,
    capsule_violations: list[dict[str, Any]] | list[str] | None = None,
    align_violations: list[dict[str, Any]] | list[str] | None = None,
    execution_status: str | None = None,
    handoff_mode: str = "operator",
) -> dict[str, Any]:
    normalized_handoff = _normalize_handoff_mode(handoff_mode)
    validation_passed = bool(validation.get("valid"))
    compile_passed = compile_result is not None
    capsule_passed = len(capsule_violations or []) == 0
    align_passed = len(align_violations or []) == 0
    return {
        "contract_version": "1.0",
        "surface": surface,
        "enforced": True,
        "claim_lane": "present-packaged-current-truth",
        "stage_order": [
            "nlp_ingress",
            "hlf_translation",
            "validation",
            "compile",
            "governance_gates",
            "execute_or_coordinate",
            "nlp_egress",
        ],
        "gates": {
            "translation": bool(source.strip()),
            "validation": validation_passed,
            "compile": compile_passed,
            "capsule": capsule_passed,
            "align": align_passed,
            "execution_or_coordination": execution_status or "not_attempted",
        },
        "artifacts": {
            "intent_text": intent,
            "canonical_hlf_required": True,
            "canonical_hlf_present": bool(source.strip()),
            "ast_sha256": (compile_result or {}).get("ast", {}).get("sha256", ""),
            "node_count": (compile_result or {}).get("node_count", 0),
            "gas_estimate": (compile_result or {}).get("gas_estimate", 0),
        },
        "handoff_policy": {
            "mode": normalized_handoff,
            "human_default": "return NLP summary and keep raw HLF internal unless requested",
            "subagent_wire_format": "raw_hlf_source",
            "raw_hlf_required": normalized_handoff in {"raw_hlf", "swarm", "subagent"},
        },
        "fail_closed": not (validation_passed and compile_passed and capsule_passed and align_passed),
        "bridge_gaps": [
            "full autonomous swarm orchestration is not claimed by this packaged surface",
            "runtime effects remain bounded by current compiler, capsule, ingress, and VM behavior",
        ],
    }


def _build_subagent_handoff(
    *,
    source: str,
    compile_result: dict[str, Any],
    validation: dict[str, Any],
    bytecode_hex: str,
    handoff_mode: str,
    tier: str,
) -> dict[str, Any]:
    ast = compile_result.get("ast", {})
    normalized_mode = _normalize_handoff_mode(handoff_mode)
    return {
        "artifact_kind": "raw_hlf_subagent_handoff",
        "handoff_mode": normalized_mode,
        "wire_format": "raw_hlf_source",
        "raw_hlf_source": source,
        "ast_sha256": ast.get("sha256", ""),
        "bytecode_hex": bytecode_hex,
        "validation": validation,
        "tier": tier,
        "swarm_mechanics": {
            "compatible": normalized_mode in {"swarm", "subagent", "raw_hlf"},
            "tool": "hlf_swarm_mechanics",
            "boundary": "local_bounded_swarm",
            "distributed_a2a": False,
        },
        "consumer_requirements": [
            "validate raw_hlf_source with hlf_validate before trusting it",
            "compile with hlf_compile and compare ast_sha256 before execution",
            "check capsule, ingress, witness, and approval surfaces before side effects",
            "for swarm handoff, materialize delegation/vote/dissent/lineage/progress via hlf_swarm_mechanics",
            "translate back to NLP only for human-facing summaries",
        ],
    }


def _build_hlf_translator_system_prompt(language: str = "english") -> str:
    """Build a system prompt that instructs the LLM to produce valid HLF-v3.

    The prompt emphasizes decomposition, not truncation — the LLM must
    break the intent into GOAL, ACTION, CONSTRAINT, ASSERTION, and RESULT
    glyphs, preserving all semantic detail from the original request.
    """
    return (
        "You are a precise HLF-v3 translator. Convert natural-language "
        f"{language} intents into valid HLF source code.\n\n"
        "CRITICAL GRAMMAR RULES:\n"
        "- Start with [HLF-v3] on its own line\n"
        "- End with Ω (Unicode Omega) on its own line\n"
        "- Use glyph statements: Δ (action), Ж (assert/constrain), Σ (result/summary), "
        "⌘ (delegate/route/goal), ⌂ (memory), ∇ (source), ⊎ (branch)\n"
        "- Each glyph has optional tag in [BRACKETS] and key=\"value\" arguments\n"
        "- Tags MUST NOT contain hyphens (-). Use underscores or CamelCase. BAD: [AUDIT-TRAIL], GOOD: [AUDIT_TRAIL]\n"
        "- Tags use UPPERCASE with underscores: [ACTION], [ASSERT], [CONSTRAINT], [RESULT], [EXTRACT], [VALIDATE]\n"
        "- Indent continuation lines under a glyph with 2 spaces\n"
        "- DO NOT use MODULE, FUNCTION, or GOAL as keywords — use glyphs with tags instead\n"
        "- Decompose complex intents into MULTIPLE glyph statements (one per action/step)\n"
        "- Preserve ALL semantic detail from the input. Do not truncate.\n"
        "- Use key=\"value\" arguments to capture parameters and conditions\n"
        "- Output ONLY a code block: ```hlf ... ```\n\n"
        "VALID EXAMPLE (simple):\n"
        "```hlf\n"
        "[HLF-v3]\n"
        "Δ [INTENT] goal=\"deploy auth service to staging\"\n"
        "  Ж [ASSERT] condition=\"deployment successful\"\n"
        "  Σ [RESULT] output=\"service deployed and tested\"\n"
        "Ω\n"
        "```\n\n"
        "VALID EXAMPLE (multi-step, 5-step pipeline):\n"
        "```hlf\n"
        "[HLF-v3]\n"
        "⌘ [GOAL] objective=\"run data pipeline\"\n"
        "⌂ [MEMORY] recall=\"previous pipeline runs\"\n"
        "Δ [EXTRACT] source=\"source DBs\"\n"
        "Δ [VALIDATE] schema=\"check schema\"\n"
        "Δ [TRANSFORM] operation=\"normalize data\"\n"
        "Δ [LOAD] target=\"warehouse\"\n"
        "Ж [CONSTRAINT] condition=\"no data loss\"\n"
        "Σ [REPORT] output=\"quality report generated\"\n"
        "Ω\n"
        "```"
    )


def _persist_translation_contract(
    ctx: ServerContext,
    *,
    contract: dict[str, Any],
    source: str,
    memory_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not hasattr(ctx, "persist_translation_contract"):
        return contract
    return ctx.persist_translation_contract(
        contract,
        source=source,
        memory_result=memory_result,
    )


def run_hlf_do(
    ctx: ServerContext,
    *,
    intent: str,
    original_intent: str = "",
    tier: str = "forge",
    dry_run: bool = False,
    show_hlf: bool = False,
    language: str = "auto",
    cognitive_lane_policy: str = "benchmark_gated",
    agent_id: str = "",
    ingress_nonce: str = "",
    handoff_mode: str = "operator",
) -> dict[str, Any]:
    """Execute the packaged governed natural-language front door outside the MCP server."""
    normalized_intent = intent.strip()
    normalized_tier = tier.lower().strip()
    normalized_handoff_mode = _normalize_handoff_mode(handoff_mode)
    if not normalized_intent:
        return {
            "success": False,
            "error": "intent is required",
            "example": "Audit /var/log/system.log in read-only mode and summarize the top errors.",
        }
    if normalized_tier not in {"hearth", "forge", "sovereign"}:
        return {
            "success": False,
            "error": f"Unsupported tier '{tier}'. Use hearth, forge, or sovereign.",
        }

    try:
        policy_name = normalize_cognitive_lane_policy(cognitive_lane_policy)
        # Use the original intent for auto language detection so normalization rewrites don't erase cues.
        detection_text = original_intent.strip() if original_intent else normalized_intent
        language_policy = resolve_language_with_policy(
            language,
            text=detection_text,
            cognitive_lane_policy=policy_name,
        )
        if language_policy.blocked:
            return {
                "success": False,
                "phase": "translation",
                "you_said": normalized_intent,
                "tier": normalized_tier,
                "governed": False,
                "language": language_policy.resolved_language,
                "audit_language": language_policy.audit_language,
                "cognitive_lane_policy": policy_name,
                "language_policy": language_policy.to_dict(),
                "error": (
                    "Blocked by cognitive lane policy: "
                    f"{language_policy.blocked_reason or 'language_ingress_disallowed'}."
                ),
            }

        resolved_language = language_policy.resolved_language

        # ── Try LLM-backed translation first (same as hlf_translate_to_hlf) ──
        source = ""
        translation_path = "heuristic"
        try:
            bridge = HLFLLMBridge()
            system_prompt = _build_hlf_translator_system_prompt(resolved_language)
            prompt = (
                f"Translate the following {resolved_language} intent into "
                f"canonical HLF-v3 syntax. Decompose it into structured glyphs: "
                f"GOALs, ACTIONS, CONSTRAINTS, ASSERTIONS, and RESULT expectations. "
                f"Do not truncate or wrap. Preserve all semantic detail.\n\n"
                f"INTENT:\n{normalized_intent}"
            )
            result = asyncio.run(bridge.send(
                prompt, role="translator", system=system_prompt))
            if result.extracted and result.hlf_output and result.hlf_output.strip() != "Ω":
                try:
                    ctx.compiler.compile(result.hlf_output)
                    source = result.hlf_output
                    translation_path = "llm"
                except CompileError:
                    pass  # fall through to heuristic
        except Exception:
            pass  # fall through to heuristic

        if not source:
            source = language_to_hlf(
                normalized_intent,
                language=resolved_language,
                version="3",
                cognitive_lane_policy=policy_name,
            )
        validation = ctx.compiler.validate(source)
        if not validation.get("valid"):
            response = {
                "success": False,
                "phase": "translation",
                "you_said": normalized_intent,
                "tier": normalized_tier,
                "governed": False,
                "language": resolved_language,
                "audit_language": language_policy.audit_language,
                "cognitive_lane_policy": policy_name,
                "language_policy": language_policy.to_dict(),
                "error": validation.get("error", "Generated HLF did not validate."),
            }
            if show_hlf:
                response["hlf_source"] = source
            return response

        compile_result = ctx.compiler.compile(source)
        ast = compile_result["ast"]
        capsule = capsule_for_tier(normalized_tier)
        capsule_violations = capsule.validate_ast(ast.get("statements", []))
        align_violations = compile_result.get("align_violations", [])
        benchmark = ctx.benchmark.analyze(source, compare_text=normalized_intent)
        localized_audit = hlf_to_language(ast, language=language_policy.audit_language)
        english_audit = hlf_to_english(ast)
        diagnostics = translation_diagnostics(
            normalized_intent, language=resolved_language, source=source
        ).to_dict()
        bytecode_hex = ctx.bytecoder.encode(ast).hex()
        translation_contract = _build_translation_contract(
            ctx,
            intent=normalized_intent,
            source=source,
            resolved_language=resolved_language,
            language_policy=language_policy.to_dict(),
            tier=normalized_tier,
            diagnostics=diagnostics,
            compile_result=compile_result,
            capsule_violations=capsule_violations,
            align_violations=align_violations,
            localized_audit=localized_audit,
            english_audit=english_audit,
            benchmark=benchmark,
        )
        internal_loop_contract = _build_internal_loop_contract(
            surface="hlf_do",
            intent=normalized_intent,
            source=source,
            validation=validation,
            compile_result=compile_result,
            capsule_violations=capsule_violations,
            align_violations=align_violations,
            execution_status="dry_run" if dry_run else "pending",
            handoff_mode=normalized_handoff_mode,
        )
        translation_contract["internal_loop_contract"] = internal_loop_contract
        translation_contract = _persist_translation_contract(
            ctx,
            contract=translation_contract,
            source="server_translation.run_hlf_do",
        )

        response: dict[str, Any] = {
            "success": len(capsule_violations) == 0 and len(align_violations) == 0,
            "you_said": normalized_intent,
            "what_hlf_did": localized_audit,
            "what_hlf_did_en": english_audit,
            "audit": (
                f"Validated and compiled for tier '{normalized_tier}'. "
                f"Estimated gas: {compile_result['gas_estimate']} / {capsule.max_gas}."
            ),
            "tier": normalized_tier,
            "governed": len(capsule_violations) == 0 and len(align_violations) == 0,
            "language": resolved_language,
            "audit_language": language_policy.audit_language,
            "cognitive_lane_policy": policy_name,
            "language_policy": language_policy.to_dict(),
            "translation_path": translation_path,
            "dry_run": dry_run,
            "capsule_violations": capsule_violations,
            "align_violations": align_violations,
            "math": {
                "english_tokens": benchmark["nlp_tokens"],
                "hlf_tokens": benchmark["hlf_tokens"],
                "compression_pct": benchmark["compression_pct"],
                "token_savings": benchmark["savings"],
                "gas_estimate": compile_result["gas_estimate"],
                "gas_budget": capsule.max_gas,
                "roundtrip_fidelity_score": diagnostics["roundtrip_fidelity_score"],
                "fallback_used": diagnostics["fallback_used"],
            },
            "translation": diagnostics,
            "translation_contract": translation_contract,
            "internal_loop_contract": internal_loop_contract,
        }
        if normalized_handoff_mode in {"raw_hlf", "swarm", "subagent"}:
            response["subagent_handoff"] = _build_subagent_handoff(
                source=source,
                compile_result=compile_result,
                validation=validation,
                bytecode_hex=bytecode_hex,
                handoff_mode=normalized_handoff_mode,
                tier=normalized_tier,
            )
            response["hlf_source"] = source
        if show_hlf:
            response["hlf_source"] = source

        if capsule_violations or align_violations or dry_run:
            if capsule_violations:
                response["audit"] = (
                    f"Blocked by capsule validation for tier '{normalized_tier}'. "
                    f"{len(capsule_violations)} violation(s) detected."
                )
            elif align_violations:
                response["audit"] = (
                    f"Compiled with ALIGN warnings for tier '{normalized_tier}'. "
                    f"{len(align_violations)} violation(s) reported."
                )
            elif dry_run:
                response["audit"] = (
                    f"Dry run only. Generated HLF validated for tier '{normalized_tier}' "
                    f"with estimated gas {compile_result['gas_estimate']} / {capsule.max_gas}."
                )
            return response

        bc = bytes.fromhex(bytecode_hex)
        normalized_agent_id = str(agent_id or "unknown-agent")
        ingress_contract = resolve_execution_ingress_contract(
            ctx,
            agent_id=normalized_agent_id,
            payload=source,
            subject_scope="hlf_do",
            nonce=ingress_nonce,
            require_hlf_validation=True,
            hlf_validated=True,
        )
        response["ingress_contract"] = ingress_contract
        denial_reasons = build_ingress_denial_reasons(
            ingress_contract,
            surface="hlf_do",
        )
        if denial_reasons:
            execution_admission = persist_runtime_execution_admission(
                ctx,
                agent_id=normalized_agent_id,
                execution_status="ingress_denied",
                requested_tier=normalized_tier,
                surface="hlf_do",
                ingress_contract=ingress_contract,
                reasons=denial_reasons,
            )
            internal_loop_contract["gates"]["execution_or_coordination"] = "ingress_denied"
            internal_loop_contract["fail_closed"] = True
            response["execution"] = {
                "status": "ingress_denied",
                "error": "; ".join(denial_reasons),
                "ingress_contract": ingress_contract,
                "execution_admission": execution_admission,
            }
            response["execution_admission"] = execution_admission
            response["success"] = False
            response["governed"] = False
            response["audit"] = (
                f"Execution blocked by packaged ingress for tier '{normalized_tier}'. "
                f"{'; '.join(denial_reasons)}"
            )
            return response
        run_result = ctx.runtime.run(
            bc,
            gas_limit=capsule.max_gas,
            variables={"DEPLOYMENT_TIER": normalized_tier},
            ast=ast,
            source=source,
            tier=normalized_tier,
        )
        run_result["ingress_contract"] = ingress_contract
        execution_admission = persist_runtime_execution_admission(
            ctx,
            agent_id=normalized_agent_id,
            execution_status=str(run_result.get("status") or "unknown"),
            requested_tier=normalized_tier,
            surface="hlf_do",
            ingress_contract=ingress_contract,
            run_result=run_result,
        )
        run_result["execution_admission"] = execution_admission
        response["execution"] = run_result
        response["execution_admission"] = execution_admission
        response["success"] = run_result.get("status") == "ok"
        internal_loop_contract["gates"]["execution_or_coordination"] = str(run_result.get("status") or "unknown")
        internal_loop_contract["fail_closed"] = internal_loop_contract["fail_closed"] or run_result.get("status") != "ok"
        if run_result.get("status") == "ok":
            response["audit"] = (
                f"Executed at tier '{normalized_tier}'. "
                f"Gas used: {run_result.get('gas_used', 0)} / {capsule.max_gas}."
            )
        else:
            response["audit"] = (
                f"Execution blocked at tier '{normalized_tier}'. "
                f"{run_result.get('error', 'Unknown runtime governance error.')}"
            )
        return response
    except CompileError as exc:
        response = {
            "success": False,
            "phase": "compile",
            "you_said": normalized_intent,
            "tier": normalized_tier,
            "governed": False,
            "error": str(exc),
        }
        if show_hlf:
            response["hlf_source"] = source
        return response
    except Exception as exc:
        response = {
            "success": False,
            "phase": "internal",
            "you_said": normalized_intent,
            "tier": normalized_tier,
            "governed": False,
            "error": str(exc),
        }
        if show_hlf and "source" in locals():
            response["hlf_source"] = source
        return response


def register_translation_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    def _query_translation_support(
        *,
        query: str,
        top_k: int = 3,
        min_confidence: float = 0.8,
        topic: str = "hlf_translation_contracts",
        purpose: str = "translation_memory",
    ) -> dict[str, Any]:
        return ctx.memory_store.query(
            query,
            top_k=top_k,
            topic=topic,
            min_confidence=min_confidence,
            purpose=purpose,
        )

    @mcp.tool()
    def hlf_do(
        intent: str,
        tier: str = "forge",
        dry_run: bool = False,
        show_hlf: bool = False,
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
        agent_id: str = "",
        ingress_nonce: str = "",
        handoff_mode: str = "operator",
        skip_normalization: bool = False,
    ) -> dict[str, Any]:
        """Translate natural-language intent into governed HLF and optionally execute it."""
        _gate = _apply_normalization_gate(ctx, intent, skip_normalization=skip_normalization)
        if _gate["rejected"]:
            return {
                "success": False,
                "status": "rejected",
                "reason": _gate["reason"],
                "normalization": _gate["normalization"],
                "findings": _gate["findings"],
            }
        return run_hlf_do(
            ctx,
            intent=_gate["text"],
            original_intent=intent,
            tier=tier,
            dry_run=dry_run,
            show_hlf=show_hlf,
            language=language,
            cognitive_lane_policy=cognitive_lane_policy,
            agent_id=agent_id,
            ingress_nonce=ingress_nonce,
            handoff_mode=handoff_mode,
        )

    @mcp.tool()
    def hlf_benchmark_matrix(
        domains: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a multilingual benchmark matrix across canonical intent prompts."""
        return ctx.benchmark.multilingual_matrix(domains=domains, languages=languages)

    @mcp.tool()
    def hlf_translation_memory_benchmark(
        domains: list[str] | None = None,
        languages: list[str] | None = None,
        top_k: int = 3,
        topic: str = "hlf_translation_contract_benchmark",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Run retrieval-backed multilingual translation memory benchmarking."""
        result = ctx.benchmark.translation_memory_retrieval_matrix(
            ctx.memory_store,
            domains=domains,
            languages=languages,
            top_k=top_k,
            topic=topic,
        )
        artifact = {
            "artifact_id": f"benchmark:{result['profile_name']}:{topic}",
            "profile_name": result["profile_name"],
            "benchmark_scores": dict(result.get("benchmark_scores") or {}),
            "domains": list(result.get("domains") or []),
            "languages": list(result.get("languages") or []),
            "topic": topic,
            "result": result,
        }
        persisted = ctx.persist_benchmark_artifact(artifact) if persist else artifact
        return {**result, "artifact": persisted}

    @mcp.tool()
    def hlf_routing_context_benchmark(
        domains: list[str] | None = None,
        languages: list[str] | None = None,
        top_k: int = 3,
        topic: str = "hlf_agent_routing_benchmark",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Run retrieval-backed multilingual routing-context benchmarking."""
        result = ctx.benchmark.routing_context_retrieval_matrix(
            ctx.memory_store,
            domains=domains,
            languages=languages,
            top_k=top_k,
            topic=topic,
        )
        artifact = {
            "artifact_id": f"benchmark:{result['profile_name']}:{topic}",
            "profile_name": result["profile_name"],
            "benchmark_scores": dict(result.get("benchmark_scores") or {}),
            "domains": list(result.get("domains") or []),
            "languages": list(result.get("languages") or []),
            "topic": topic,
            "result": result,
        }
        persisted = ctx.persist_benchmark_artifact(artifact) if persist else artifact
        return {**result, "artifact": persisted}

    @mcp.tool()
    def hlf_translation_memory_query(
        query: str,
        top_k: int = 5,
        min_confidence: float = 0.8,
    ) -> dict[str, Any]:
        """Query known-good translation contract exemplars from Infinite RAG memory."""
        return _query_translation_support(
            query=query,
            top_k=top_k,
            min_confidence=min_confidence,
            purpose="translation_memory",
        )

    @mcp.tool()
    async def hlf_translate_to_hlf(
        text: str,
        version: str = "3",
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
        handoff_mode: str = "operator",
        skip_normalization: bool = False,
    ) -> dict[str, Any]:
        """Convert natural language instructions to HLF source code."""
        try:
            _gate = _apply_normalization_gate(ctx, text, skip_normalization=skip_normalization)
            if _gate["rejected"]:
                return {
                    "status": "rejected",
                    "source": "",
                    "reason": _gate["reason"],
                    "normalization": _gate["normalization"],
                    "findings": _gate["findings"],
                }
            working_text = _gate["text"]

            policy_name = normalize_cognitive_lane_policy(cognitive_lane_policy)
            # Use the original text for auto language detection so normalization rewrites don't erase cues.
            detection_text = text if language.lower().strip() == "auto" else working_text
            language_policy = resolve_language_with_policy(
                language,
                text=detection_text,
                cognitive_lane_policy=policy_name,
            )
            if language_policy.blocked:
                return {
                    "status": "error",
                    "error": (
                        "Blocked by cognitive lane policy: "
                        f"{language_policy.blocked_reason or 'language_ingress_disallowed'}"
                    ),
                    "language_policy": language_policy.to_dict(),
                }

            resolved_language = language_policy.resolved_language
            source = ""
            translation_path = "heuristic"
            memory_hits: list[dict[str, Any]] = []

            # ── HKS memory recall: find similar past translations ──────
            try:
                memory_result = ctx.memory_store.query(
                    working_text,
                    top_k=3,
                    topic="hlf_translation_contracts",
                    min_confidence=0.7,
                    purpose="translation_memory",
                )
                memory_hits = memory_result.get("results", []) or []
            except Exception:
                memory_hits = []

            # ── LLM-backed translation (primary path) ──────────────────
            try:
                bridge = HLFLLMBridge()
                system_prompt = _build_hlf_translator_system_prompt(resolved_language)

                # Build few-shot examples from memory hits
                few_shot = ""
                if memory_hits:
                    few_shot_parts = []
                    for i, hit in enumerate(memory_hits[:2]):
                        hit_content = hit.get("content", "")
                        if hit_content and len(hit_content) > 20:
                            few_shot_parts.append(
                                f"EXAMPLE {i + 1} (confidence {hit.get('confidence', 'N/A')}):\n{hit_content}"
                            )
                    if few_shot_parts:
                        few_shot = (
                            "Here are examples of correct HLF translations for similar intents. "
                            "Use these as style and structure reference:\n\n"
                            + "\n\n".join(few_shot_parts)
                            + "\n\n"
                        )

                prompt = (
                    f"Translate the following {resolved_language} intent into "
                    f"canonical HLF-v3 syntax. Decompose it into structured glyphs: "
                    f"GOALs, ACTIONS, CONSTRAINTS, ASSERTIONS, and RESULT expectations. "
                    f"Do not truncate or wrap. Preserve all semantic detail.\n\n"
                    f"{few_shot}"
                    f"INTENT:\n{working_text}"
                )
                result = await bridge.send(
                    prompt, role="translator", system=system_prompt)
                if result.extracted and result.hlf_output and result.hlf_output.strip() != "Ω":
                    # Verify the LLM output is valid HLF
                    try:
                        ctx.compiler.compile(result.hlf_output)
                        source = result.hlf_output
                        translation_path = "llm"
                    except CompileError:
                        logger = __import__("logging").getLogger(__name__)
                        logger.warning("LLM-generated HLF failed compilation, falling back to heuristic")
            except Exception:
                pass  # fall through to heuristic

            if not source:
                source = language_to_hlf(
                    working_text,
                    language=resolved_language,
                    version=version,
                    cognitive_lane_policy=policy_name,
                )
            diagnostics = translation_diagnostics(
                working_text, language=resolved_language, source=source
            ).to_dict()
            compile_result = ctx.compiler.compile(source)
            localized_audit = hlf_to_language(
                compile_result["ast"], language=language_policy.audit_language
            )
            english_audit = hlf_to_english(compile_result["ast"])
            benchmark = ctx.benchmark.analyze(source, compare_text=text)
            validation = ctx.compiler.validate(source)
            bytecode_hex = ctx.bytecoder.encode(compile_result["ast"]).hex()
            internal_loop_contract = _build_internal_loop_contract(
                surface="hlf_translate_to_hlf",
                intent=text,
                source=source,
                validation=validation,
                compile_result=compile_result,
                capsule_violations=[],
                align_violations=compile_result.get("align_violations", []),
                execution_status="coordination_ready",
                handoff_mode=handoff_mode,
            )
            translation_contract = _build_translation_contract(
                ctx,
                intent=text,
                source=source,
                resolved_language=resolved_language,
                language_policy=language_policy.to_dict(),
                tier="forge",
                diagnostics=diagnostics,
                compile_result=compile_result,
                capsule_violations=[],
                align_violations=compile_result.get("align_violations", []),
                localized_audit=localized_audit,
                english_audit=english_audit,
                benchmark=benchmark,
            )
            translation_contract["internal_loop_contract"] = internal_loop_contract
            translation_contract = _persist_translation_contract(
                ctx,
                contract=translation_contract,
                source="server_translation.hlf_translate_to_hlf",
            )

            # ── HKS memory store: feed back for compounding improvement ──
            memory_store_result = {}
            if translation_path == "llm" and source:
                try:
                    store_meta = {
                        "intent": text,
                        "language": resolved_language,
                        "translation_path": translation_path,
                        "compile_success": True,
                        "node_count": len(compile_result.get("ast", {}).get("statements", [])),
                        "governed_evidence": {
                            "source_type": "translation_pipeline",
                            "artifact_form": "hlf_source",
                            "salience_score": 0.95,
                            "source_authority_label": "governed",
                            "branch": "main",
                        },
                    }
                    memory_store_result = ctx.memory_store.store(
                        content=source,
                        topic="hlf_translation_contracts",
                        confidence=0.95,
                        provenance="governed_recall",
                        entry_kind="hks_exemplar",
                        domain="hlf-specific",
                        metadata=store_meta,
                        bypass_vector_dedup=True,
                    )
                except Exception:
                    pass  # non-critical — translation proceeds even if memory store fails

            response = {
                "status": "ok",
                "source": source,
                "language": resolved_language,
                "audit_language": language_policy.audit_language,
                "cognitive_lane_policy": policy_name,
                "language_policy": language_policy.to_dict(),
                "translation": diagnostics,
                "translation_path": translation_path,
                "translation_contract": translation_contract,
                "internal_loop_contract": internal_loop_contract,
                "normalization": _gate["normalization"],
                "hks_memory": {
                    "recall_hits": len(memory_hits),
                    "recall_top_confidence": memory_hits[0].get("confidence", 0) if memory_hits else 0,
                    "stored": bool(memory_store_result.get("stored")) if memory_store_result else False,
                },
            }
            if _normalize_handoff_mode(handoff_mode) in {"raw_hlf", "swarm", "subagent"}:
                response["subagent_handoff"] = _build_subagent_handoff(
                    source=source,
                    compile_result=compile_result,
                    validation=validation,
                    bytecode_hex=bytecode_hex,
                    handoff_mode=handoff_mode,
                    tier="forge",
                )
            return response
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    async def hlf_governed_swarm_mechanics(
        text: str = "",
        source: str = "",
        handoff: dict[str, Any] | None = None,
        votes: list[dict[str, Any]] | None = None,
        dissent: list[dict[str, Any]] | None = None,
        progress_events: list[dict[str, Any]] | None = None,
        quorum: str = "strict",
        persist: bool = True,
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
    ) -> dict[str, Any]:
        """Bootstrap a target-bound HLF contract and materialize swarm mechanics safely."""
        try:
            normalized_handoff = handoff if isinstance(handoff, dict) else None
            raw_hlf_source = source or str((normalized_handoff or {}).get("raw_hlf_source") or "")
            translation: dict[str, Any] | None = None

            if not raw_hlf_source.strip():
                if not text.strip():
                    return {
                        "status": "error",
                        "error": "text, source, or handoff.raw_hlf_source is required",
                        "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
                    }
                translation = await hlf_translate_to_hlf(
                    text,
                    language=language,
                    cognitive_lane_policy=cognitive_lane_policy,
                    handoff_mode="swarm",
                )
                if translation.get("status") != "ok":
                    return translation
                raw_hlf_source = str(translation["source"])
                normalized_handoff = translation.get("subagent_handoff")

            validation = ctx.compiler.validate(raw_hlf_source)
            if not validation.get("valid"):
                return {
                    "status": "validation_error",
                    "error": validation.get("error", "HLF source did not validate."),
                    "validation": validation,
                    "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
                }

            compile_result = ctx.compiler.compile(raw_hlf_source)
            if translation is None:
                resolved_language = resolve_language(language, text=raw_hlf_source)
                language_policy = resolve_language_with_policy(
                    resolved_language,
                    text=raw_hlf_source,
                    cognitive_lane_policy=normalize_cognitive_lane_policy(cognitive_lane_policy),
                )
                benchmark = ctx.benchmark.analyze(raw_hlf_source, compare_text=text or raw_hlf_source)
                translation_contract = _build_translation_contract(
                    ctx,
                    intent=text or "raw HLF swarm mechanics artifact",
                    source=raw_hlf_source,
                    resolved_language=language_policy.resolved_language,
                    language_policy=language_policy.to_dict(),
                    tier="forge",
                    diagnostics=translation_diagnostics(
                        text or raw_hlf_source,
                        language=language_policy.resolved_language,
                        source=raw_hlf_source,
                    ).to_dict(),
                    compile_result=compile_result,
                    capsule_violations=[],
                    align_violations=compile_result.get("align_violations", []),
                    localized_audit=hlf_to_language(
                        compile_result["ast"], language=language_policy.audit_language
                    ),
                    english_audit=hlf_to_english(compile_result["ast"]),
                    benchmark=benchmark,
                )
                translation_contract["internal_loop_contract"] = _build_internal_loop_contract(
                    surface="hlf_governed_swarm_mechanics",
                    intent=text or "raw HLF swarm mechanics artifact",
                    source=raw_hlf_source,
                    validation=validation,
                    compile_result=compile_result,
                    capsule_violations=[],
                    align_violations=compile_result.get("align_violations", []),
                    execution_status="coordination_ready",
                    handoff_mode="swarm",
                )
            else:
                translation_contract = dict(translation["translation_contract"])

            target_arguments: dict[str, Any] = {
                "source": raw_hlf_source,
                "persist": persist,
            }
            if normalized_handoff is not None:
                target_arguments["handoff"] = normalized_handoff
            if votes is not None:
                target_arguments["votes"] = votes
            if dissent is not None:
                target_arguments["dissent"] = dissent
            if progress_events is not None:
                target_arguments["progress_events"] = progress_events
            if quorum != "strict":
                target_arguments["quorum"] = quorum

            contract = dict(translation_contract)
            contract["mcp_binding"] = build_mcp_call_binding(
                "hlf_swarm_mechanics", target_arguments
            )
            contract["target_binding"] = contract["mcp_binding"]

            result = run_hlf_swarm_mechanics(
                ctx,
                source=raw_hlf_source,
                handoff=normalized_handoff,
                votes=votes,
                dissent=dissent,
                progress_events=progress_events,
                quorum=quorum,
                persist=persist,
            )
            result["hlf_contract"] = contract
            result["target_call"] = {
                "tool_name": "hlf_swarm_mechanics",
                "arguments": target_arguments,
            }
            result["governed_workflow"] = {
                "bootstrap_tool": "hlf_governed_swarm_mechanics",
                "protected_tool": "hlf_swarm_mechanics",
                "target_bound_contract": True,
                "direct_protected_call_required": False,
            }
            if translation is not None:
                result["translation"] = translation
            return result
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
            }


    @mcp.tool()
    def hlf_translate_repair(
        text: str,
        failure_status: str = "",
        failure_error: str = "",
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
        skip_normalization: bool = False,
    ) -> dict[str, Any]:
        """Build a deterministic next-step repair request for failed translation flows."""
        _gate = _apply_normalization_gate(ctx, text, skip_normalization=skip_normalization)
        working_text = _gate["text"]
        plan = build_translation_repair_plan(
            working_text,
            language=language,
            failure_status=failure_status,
            failure_error=failure_error,
            original_text=text,
        ).to_dict()
        repair_memory = ctx.store_translation_repair_pattern(
            original_text=text,
            failure_status=failure_status,
            failure_error=failure_error,
            language=language,
            repair_plan=plan,
            provenance="server_translation.hlf_translate_repair",
        )
        retrieval_support = _query_translation_support(
            query=f"{failure_status} {text}".strip() or text,
            top_k=3,
            min_confidence=0.7,
            topic="hlf_repairs",
            purpose="repair_pattern_recall",
        )
        governed_hks_contract = dict(retrieval_support.get("governed_hks_contract") or {})
        invocation_gate = dict((retrieval_support.get("retrieval_contract") or {}).get("invocation_gate") or {})
        plan["knowledge_support"] = {
            "reference_allowed": bool(governed_hks_contract.get("reference_allowed", False)),
            "evidence_count": int(governed_hks_contract.get("evidence_count") or 0),
            "graph_source": str(
                (governed_hks_contract.get("graph_posture") or {}).get("source")
                or "metadata-derived"
            ),
            "decision": str(invocation_gate.get("decision") or "invoke"),
            "review_required": bool(invocation_gate.get("review_required", False)),
        }
        # Augment repair_memory with the metadata/evidence keys the contract expects
        repair_memory_with_metadata = dict(repair_memory)
        repair_memory_with_metadata["metadata"] = {"topic": "hlf_repairs"}
        if "entry_kind" not in repair_memory_with_metadata:
            repair_memory_with_metadata["entry_kind"] = "hks_exemplar"
        governance_event = repair_memory.get("governance_event") or {}
        event_details = dict(governance_event.get("event", {}).get("details", {}))
        repair_memory_with_metadata["evidence"] = {
            "topic": event_details.get("topic", "hlf_repairs"),
            "domain": event_details.get("domain", "hlf-specific"),
            "solution_kind": event_details.get("solution_kind", "repair-pattern"),
        }
        return {
            "status": "ok",
            "repair": plan,
            "repair_memory": repair_memory_with_metadata,
            "retrieval_support": retrieval_support,
            "governed_hks_contract": governed_hks_contract,
            "normalization": _gate["normalization"],
        }

    @mcp.tool()
    def hlf_translate_resilient(
        text: str,
        language: str = "auto",
        tier: str = "forge",
        max_attempts: int = 3,
        min_fidelity: float = 0.9,
        remember_success: bool = True,
        cognitive_lane_policy: str = "benchmark_gated",
        skip_normalization: bool = False,
    ) -> dict[str, Any]:
        """Translate with deterministic retries, fallbacks, and fail-closed exits."""
        # ── Constitutional pre-screen: block provably illegal content ─────────
        constitutional_violations = _evaluate_constitution(
            ast=None, env={}, source=text, tier=tier
        )
        if constitutional_violations:
            return {
                "status": "error",
                "phase": "constitutional_pre_screen",
                "terminal_reason": "policy_block",
                "constitutional_violations": [
                    {"rule_id": v.rule_id, "article": v.article, "message": v.message}
                    for v in constitutional_violations
                ],
                "retryable": False,
            }

        _gate = _apply_normalization_gate(ctx, text, skip_normalization=skip_normalization)
        if _gate["rejected"]:
            return {
                "status": "rejected",
                "reason": _gate["reason"],
                "normalization": _gate["normalization"],
                "findings": _gate["findings"],
            }
        attempts: list[dict[str, Any]] = []
        current_text = _gate["text"]
        current_language = language

        for attempt in range(1, max_attempts + 1):
            translation = asyncio.run(hlf_translate_to_hlf(
                current_text,
                language=current_language,
                cognitive_lane_policy=cognitive_lane_policy,
                skip_normalization=True,  # already gated at this level
            ))
            attempt_record: dict[str, Any] = {
                "attempt": attempt,
                "text": current_text,
                "language": current_language,
                "translation_status": translation.get("status", "error"),
            }
            if translation.get("status") != "ok":
                repair = hlf_translate_repair(
                    current_text,
                    failure_status=translation.get("status", "error"),
                    failure_error=str(translation.get("error", "translation failure")),
                    language=current_language,
                    cognitive_lane_policy=cognitive_lane_policy,
                    skip_normalization=True,  # already gated at this level
                )["repair"]
                attempt_record["repair"] = repair
                attempts.append(attempt_record)
                if not repair["retryable"] or attempt == max_attempts:
                    return {
                        "status": "error",
                        "phase": "translation",
                        "attempts": attempts,
                        "final_error": translation.get("error", "translation failure"),
                        "retryable": repair["retryable"],
                        "terminal_reason": repair["terminal_reason"],
                    }
                current_text = repair["repaired_text"]
                current_language = repair["resolved_language"]
                continue

            source = str(translation["source"])
            translation_meta = translation.get("translation", {})
            attempt_record["translation"] = translation_meta
            validation = ctx.compiler.validate(source)
            attempt_record["validation"] = validation
            if not validation.get("valid"):
                repair = hlf_translate_repair(
                    current_text,
                    failure_status="compile_error",
                    failure_error=str(validation.get("error", "validation failure")),
                    language=str(translation.get("language", current_language)),
                    cognitive_lane_policy=cognitive_lane_policy,
                    skip_normalization=True,  # already gated
                )["repair"]
                attempt_record["repair"] = repair
                attempts.append(attempt_record)
                if not repair["retryable"] or attempt == max_attempts:
                    return {
                        "status": "error",
                        "phase": "validation",
                        "attempts": attempts,
                        "final_error": validation.get("error", "validation failure"),
                        "retryable": repair["retryable"],
                        "terminal_reason": repair["terminal_reason"],
                    }
                current_text = repair["repaired_text"]
                current_language = repair["resolved_language"]
                continue

            try:
                compile_result = ctx.compiler.compile(source)
            except CompileError as exc:
                repair = hlf_translate_repair(
                    current_text,
                    failure_status="compile_error",
                    failure_error=str(exc),
                    language=str(translation.get("language", current_language)),
                    skip_normalization=True,  # already gated
                )["repair"]
                attempt_record["repair"] = repair
                attempts.append(attempt_record)
                if not repair["retryable"] or attempt == max_attempts:
                    return {
                        "status": "error",
                        "phase": "compile",
                        "attempts": attempts,
                        "final_error": str(exc),
                        "retryable": repair["retryable"],
                        "terminal_reason": repair["terminal_reason"],
                    }
                current_text = repair["repaired_text"]
                current_language = repair["resolved_language"]
                continue

            capsule = capsule_for_tier(tier)
            capsule_violations = capsule.validate_ast(compile_result["ast"].get("statements", []))
            attempt_record["capsule_violations"] = capsule_violations
            attempts.append(attempt_record)
            fidelity = float(translation_meta.get("roundtrip_fidelity_score", 0.0))
            fallback_used = bool(translation_meta.get("fallback_used", False))

            if capsule_violations:
                return {
                    "status": "blocked",
                    "phase": "capsule",
                    "attempts": attempts,
                    "source": source,
                    "language": translation.get("language", current_language),
                    "capsule_violations": capsule_violations,
                    "retryable": False,
                    "terminal_reason": "capsule_block",
                }

            if fidelity >= min_fidelity and not fallback_used:
                memory_result = None
                if remember_success:
                    memory_result = ctx.store_known_good_translation_contract(
                        original_text=text,
                        source=source,
                        language=str(translation.get("language", current_language)),
                        translation=translation_meta,
                        tier=tier,
                        provenance="hlf_translate_resilient",
                    )
                translation_contract = _build_translation_contract(
                    ctx,
                    intent=text,
                    source=source,
                    resolved_language=str(translation.get("language", current_language)),
                    language_policy=dict(translation.get("language_policy") or {}),
                    tier=tier,
                    diagnostics=dict(translation_meta),
                    compile_result=compile_result,
                    capsule_violations=[],
                    align_violations=compile_result.get("align_violations", []),
                    localized_audit=hlf_to_language(
                        compile_result["ast"],
                        language=str(
                            translation.get("audit_language")
                            or translation.get("language", current_language)
                        ),
                    ),
                    english_audit=hlf_to_english(compile_result["ast"]),
                    benchmark=ctx.benchmark.analyze(source, compare_text=text),
                )
                translation_contract = _persist_translation_contract(
                    ctx,
                    contract=translation_contract,
                    source="server_translation.hlf_translate_resilient",
                    memory_result=memory_result,
                )
                return {
                    "status": "ok",
                    "attempts": attempts,
                    "source": source,
                    "language": translation.get("language", current_language),
                    "translation": translation_meta,
                    "memory": memory_result,
                    "translation_contract": translation_contract,
                }

            repair = hlf_translate_repair(
                current_text,
                failure_status="low_fidelity",
                failure_error=f"fallback_used={fallback_used}; fidelity={fidelity}",
                language=str(translation.get("language", current_language)),
                skip_normalization=True,  # already gated
            )["repair"]
            attempts[-1]["repair"] = repair
            if attempt == max_attempts:
                return {
                    "status": "partial",
                    "attempts": attempts,
                    "source": source,
                    "language": translation.get("language", current_language),
                    "translation": translation_meta,
                    "retryable": repair["retryable"],
                    "terminal_reason": "max_attempts_low_fidelity",
                }
            current_text = repair["repaired_text"]
            current_language = repair["resolved_language"]

        return {
            "status": "error",
            "phase": "translation",
            "attempts": attempts,
            "final_error": "max_attempts_exhausted",
            "retryable": False,
            "terminal_reason": "max_attempts_exhausted",
        }

    @mcp.tool()
    def hlf_translate_to_english(source: str, language: str = "en") -> dict[str, Any]:
        """Convert HLF source code to a human-readable summary."""
        try:
            result = ctx.compiler.compile(source)
            resolved_language = resolve_language(language)
            summary = (
                insaits.decompile(result["ast"])
                if resolved_language == "en"
                else hlf_to_language(result["ast"], language=resolved_language)
            )
            response = {"status": "ok", "summary": summary, "language": resolved_language}
            if resolved_language != "en":
                response["summary_en"] = insaits.decompile(result["ast"])
            return response
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_decompile_ast(source: str, language: str = "en") -> dict[str, Any]:
        """Compile HLF source and return AST documentation."""
        try:
            result = ctx.compiler.compile(source)
            resolved_language = resolve_language(language)
            docs = (
                insaits.decompile(result["ast"])
                if resolved_language == "en"
                else hlf_to_language(result["ast"], language=resolved_language)
            )
            response = {
                "status": "ok",
                "docs": docs,
                "language": resolved_language,
                "ast": result["ast"],
            }
            if resolved_language != "en":
                response["docs_en"] = insaits.decompile(result["ast"])
            return response
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_decompile_bytecode(source: str) -> dict[str, Any]:
        """Compile HLF source → encode to bytecode → disassemble → produce English docs."""
        try:
            result = ctx.compiler.compile(source)
            bc = ctx.bytecoder.encode(result["ast"])
            docs = insaits.decompile_bytecode(bc)
            return {"status": "ok", "docs": docs, "bytecode_hex": bc.hex()}
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    return {
        "hlf_do": hlf_do,
        "hlf_benchmark_matrix": hlf_benchmark_matrix,
        "hlf_translation_memory_benchmark": hlf_translation_memory_benchmark,
        "hlf_routing_context_benchmark": hlf_routing_context_benchmark,
        "hlf_translation_memory_query": hlf_translation_memory_query,
        "hlf_translate_to_hlf": hlf_translate_to_hlf,
        "hlf_governed_swarm_mechanics": hlf_governed_swarm_mechanics,
        "hlf_translate_repair": hlf_translate_repair,
        "hlf_translate_resilient": hlf_translate_resilient,
        "hlf_translate_to_english": hlf_translate_to_english,
        "hlf_decompile_ast": hlf_decompile_ast,
        "hlf_decompile_bytecode": hlf_decompile_bytecode,
    }
