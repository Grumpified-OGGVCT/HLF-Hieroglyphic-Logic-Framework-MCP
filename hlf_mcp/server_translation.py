from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.compiler import CompileError
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
from hlf_mcp.ingress_support import build_ingress_denial_reasons
from hlf_mcp.ingress_support import persist_runtime_execution_admission
from hlf_mcp.ingress_support import resolve_execution_ingress_contract
from hlf_mcp.server_context import ServerContext


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
    tier: str = "forge",
    dry_run: bool = False,
    show_hlf: bool = False,
    language: str = "auto",
    cognitive_lane_policy: str = "benchmark_gated",
    agent_id: str = "",
    ingress_nonce: str = "",
) -> dict[str, Any]:
    """Execute the packaged governed natural-language front door outside the MCP server."""
    normalized_intent = intent.strip()
    normalized_tier = tier.lower().strip()
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
        language_policy = resolve_language_with_policy(
            language,
            text=normalized_intent,
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
        }
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

        bc = ctx.bytecoder.encode(ast)
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
    ) -> dict[str, Any]:
        """Translate natural-language intent into governed HLF and optionally execute it."""
        return run_hlf_do(
            ctx,
            intent=intent,
            tier=tier,
            dry_run=dry_run,
            show_hlf=show_hlf,
            language=language,
            cognitive_lane_policy=cognitive_lane_policy,
            agent_id=agent_id,
            ingress_nonce=ingress_nonce,
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
    def hlf_translate_to_hlf(
        text: str,
        version: str = "3",
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
    ) -> dict[str, Any]:
        """Convert natural language instructions to HLF source code."""
        try:
            policy_name = normalize_cognitive_lane_policy(cognitive_lane_policy)
            language_policy = resolve_language_with_policy(
                language,
                text=text,
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
            source = language_to_hlf(
                text,
                language=resolved_language,
                version=version,
                cognitive_lane_policy=policy_name,
            )
            diagnostics = translation_diagnostics(
                text, language=resolved_language, source=source
            ).to_dict()
            compile_result = ctx.compiler.compile(source)
            localized_audit = hlf_to_language(
                compile_result["ast"], language=language_policy.audit_language
            )
            english_audit = hlf_to_english(compile_result["ast"])
            benchmark = ctx.benchmark.analyze(source, compare_text=text)
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
            translation_contract = _persist_translation_contract(
                ctx,
                contract=translation_contract,
                source="server_translation.hlf_translate_to_hlf",
            )
            return {
                "status": "ok",
                "source": source,
                "language": resolved_language,
                "audit_language": language_policy.audit_language,
                "cognitive_lane_policy": policy_name,
                "language_policy": language_policy.to_dict(),
                "translation": diagnostics,
                "translation_contract": translation_contract,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_translate_repair(
        text: str,
        failure_status: str = "",
        failure_error: str = "",
        language: str = "auto",
        cognitive_lane_policy: str = "benchmark_gated",
    ) -> dict[str, Any]:
        """Build a deterministic next-step repair request for failed translation flows."""
        plan = build_translation_repair_plan(
            text,
            language=language,
            failure_status=failure_status,
            failure_error=failure_error,
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
        return {
            "status": "ok",
            "repair": plan,
            "repair_memory": repair_memory,
            "retrieval_support": retrieval_support,
            "governed_hks_contract": governed_hks_contract,
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
    ) -> dict[str, Any]:
        """Translate with deterministic retries, fallbacks, and fail-closed exits."""
        attempts: list[dict[str, Any]] = []
        current_text = text
        current_language = language

        for attempt in range(1, max_attempts + 1):
            translation = hlf_translate_to_hlf(
                current_text,
                language=current_language,
                cognitive_lane_policy=cognitive_lane_policy,
            )
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
                cognitive_lane_policy=cognitive_lane_policy,
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
        "hlf_translate_repair": hlf_translate_repair,
        "hlf_translate_resilient": hlf_translate_resilient,
        "hlf_translate_to_english": hlf_translate_to_english,
        "hlf_decompile_ast": hlf_decompile_ast,
        "hlf_decompile_bytecode": hlf_decompile_bytecode,
    }
