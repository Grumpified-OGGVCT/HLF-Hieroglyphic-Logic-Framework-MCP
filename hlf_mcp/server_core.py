from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import audit_symbolic_surface, compile_symbolic_surface
from hlf_mcp.hlf.code_execution import execute_code_bearing_hlf
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.governance_proofs import render_proof_markdown, verify_governance_proof
from hlf_mcp.hlf.swarm_mechanics import build_swarm_mechanics_artifact
from hlf_mcp.ingress_support import (
    build_ingress_denial_reasons,
    persist_runtime_execution_admission,
    resolve_execution_ingress_contract,
)
from hlf_mcp.server_context import ServerContext
from hlf_mcp.test_runner import DEFAULT_METRICS_DIR, LATEST_SUMMARY_FILE

_log = logging.getLogger(__name__)


def load_test_suite_summary(
    metrics_dir: str | Path | None = None,
    *,
    include_output: bool = False,
) -> dict[str, Any]:
    """Load the latest persisted pytest suite summary from the metrics store."""
    base_dir = Path(metrics_dir).expanduser() if metrics_dir else DEFAULT_METRICS_DIR
    summary_path = base_dir / LATEST_SUMMARY_FILE
    if not summary_path.exists():
        return {
            "status": "not_found",
            "metrics_dir": str(base_dir),
            "summary_path": str(summary_path),
        }
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "error",
            "metrics_dir": str(base_dir),
            "summary_path": str(summary_path),
            "error": str(exc),
        }

    summary = dict(payload)
    if not include_output:
        summary.pop("stdout", None)
        summary.pop("stderr", None)
    return {
        "status": "ok",
        "metrics_dir": str(base_dir),
        "summary_path": str(summary_path),
        "summary": summary,
    }


def run_hlf_swarm_mechanics(
    ctx: ServerContext,
    *,
    source: str = "",
    handoff: dict[str, Any] | None = None,
    votes: list[dict[str, Any]] | None = None,
    dissent: list[dict[str, Any]] | None = None,
    progress_events: list[dict[str, Any]] | None = None,
    quorum: str = "strict",
    persist: bool = True,
) -> dict[str, Any]:
    try:
        normalized_handoff = handoff if isinstance(handoff, dict) else None
        raw_hlf_source = source or str((normalized_handoff or {}).get("raw_hlf_source") or "")
        if not raw_hlf_source.strip():
            return {
                "status": "error",
                "error": "source or handoff.raw_hlf_source is required",
                "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
            }
        validation = ctx.compiler.validate(raw_hlf_source)
        if not validation.get("valid"):
            return {
                "status": "validation_error",
                "error": validation.get("error", "HLF source did not validate."),
                "validation": validation,
                "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
            }
        compile_result = ctx.compiler.compile(raw_hlf_source)
        artifact = build_swarm_mechanics_artifact(
            source=raw_hlf_source,
            ast=compile_result["ast"],
            validation=validation,
            compile_result=compile_result,
            handoff=normalized_handoff,
            votes=votes,
            dissent=dissent,
            progress_events=progress_events,
            quorum=quorum,
        )
        if persist and hasattr(ctx, "persist_swarm_mechanics"):
            artifact = ctx.persist_swarm_mechanics(artifact)
        return {"status": "ok", "swarm_mechanics": artifact}
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "boundary": {"mode": "local_bounded_swarm", "distributed_a2a": False},
        }


def register_core_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_compile(source: str) -> dict[str, Any]:
        """Compile HLF source code to a JSON AST and bytecode."""
        try:
            result = ctx.compiler.compile(source)
            bc = ctx.bytecoder.encode(result["ast"])
            return {
                "status": "ok",
                "ast": result["ast"],
                "bytecode_hex": bc.hex(),
                "bytecode_size_bytes": len(bc),
                "node_count": result["node_count"],
                "gas_estimate": result["gas_estimate"],
                "version": result["version"],
                "errors": [],
            }
        except CompileError as exc:
            return {
                "status": "error",
                "ast": None,
                "bytecode_hex": None,
                "bytecode_size_bytes": 0,
                "node_count": 0,
                "gas_estimate": 0,
                "version": None,
                "errors": [{"message": str(exc), "line": exc.line, "col": exc.col}],
            }
        except Exception as exc:
            return {
                "status": "error",
                "ast": None,
                "bytecode_hex": None,
                "bytecode_size_bytes": 0,
                "node_count": 0,
                "gas_estimate": 0,
                "version": None,
                "errors": [{"message": str(exc), "line": 0, "col": 0}],
            }

    @mcp.tool()
    def hlf_format(source: str) -> dict[str, Any]:
        """Format HLF source to canonical form."""
        try:
            formatted = ctx.formatter.format(source)
            diff = ctx.formatter.diff_summary(source, formatted)
            return {"status": "ok", "formatted": formatted, "diff_summary": diff}
        except Exception as exc:
            return {"status": "error", "formatted": source, "diff_summary": str(exc)}

    @mcp.tool()
    def hlf_lint(source: str, gas_limit: int = 1000, token_limit: int = 30) -> dict[str, Any]:
        """Lint HLF source and return diagnostics."""
        diags = ctx.linter.lint(source, gas_limit=gas_limit, token_limit=token_limit)
        return {
            "passed": all(d["level"] != "error" for d in diags),
            "diagnostics": diags,
            "error_count": sum(1 for d in diags if d["level"] == "error"),
            "warning_count": sum(1 for d in diags if d["level"] == "warning"),
            "info_count": sum(1 for d in diags if d["level"] == "info"),
        }

    @mcp.tool()
    def hlf_run(
        source: str,
        gas_limit: int = 1000,
        variables: dict[str, Any] | None = None,
        agent_id: str = "",
        ingress_nonce: str = "",
    ) -> dict[str, Any]:
        """Execute an HLF program in the stack-machine VM."""
        try:
            result = ctx.compiler.compile(source)
            if result.get("errors"):
                return {
                    "status": "compile_error",
                    "error": result["errors"],
                    "gas_used": 0,
                    "trace": [],
                    "side_effects": [],
                }
            bc = ctx.bytecoder.encode(result["ast"])
            runtime_variables = variables or {}
            normalized_agent_id = str(agent_id or "unknown-agent")
            runtime_tier = str(runtime_variables.get("DEPLOYMENT_TIER", "hearth"))
            ingress_contract = resolve_execution_ingress_contract(
                ctx,
                agent_id=normalized_agent_id,
                payload=source,
                subject_scope="hlf_run",
                nonce=ingress_nonce,
                require_hlf_validation=True,
                hlf_validated=True,
            )
            denial_reasons = build_ingress_denial_reasons(
                ingress_contract,
                surface="hlf_run",
            )
            if denial_reasons:
                execution_admission = persist_runtime_execution_admission(
                    ctx,
                    agent_id=normalized_agent_id,
                    execution_status="ingress_denied",
                    requested_tier=runtime_tier,
                    surface="hlf_run",
                    ingress_contract=ingress_contract,
                    reasons=denial_reasons,
                )
                return {
                    "status": "ingress_denied",
                    "error": "; ".join(denial_reasons),
                    "gas_used": 0,
                    "trace": [],
                    "side_effects": [],
                    "ingress_contract": ingress_contract,
                    "execution_admission": execution_admission,
                }
            run_result = ctx.runtime.run(
                bc,
                gas_limit=gas_limit,
                variables=runtime_variables,
                ast=result["ast"],
                source=source,
                tier=runtime_tier,
            )
            run_result["ingress_contract"] = ingress_contract
            run_result["execution_admission"] = persist_runtime_execution_admission(
                ctx,
                agent_id=normalized_agent_id,
                execution_status=str(run_result.get("status") or "unknown"),
                requested_tier=runtime_tier,
                surface="hlf_run",
                ingress_contract=ingress_contract,
                run_result=run_result,
            )
            return run_result
        except CompileError as exc:
            from hlf_mcp.hlf.exceptions import HLFCompileError
            raise HLFCompileError(str(exc)) from exc
        except Exception as exc:
            return {
                "status": "runtime_error",
                "error": str(exc),
                "gas_used": 0,
                "trace": [],
                "side_effects": [],
            }

    @mcp.tool()
    def hlf_code_execute(
        source: str,
        entrypoint: str = "",
        gas_limit: int = 500,
        tier: str = "hearth",
        dry_run: bool = False,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Compile, verify, and bounded-run MODULE/FUNCTION/[CODE] HLF blocks."""
        try:
            result = execute_code_bearing_hlf(
                source,
                entrypoint=entrypoint,
                gas_limit=gas_limit,
                tier=tier,
                variables=variables,
                dry_run=dry_run,
                compiler=ctx.compiler,
                linter=ctx.linter,
                verifier=ctx.formal_verifier,
                runtime=ctx.runtime,
                bytecoder=ctx.bytecoder,
                audit_logger=ctx.audit_chain,
            )
            if hasattr(ctx, "emit_governance_event"):
                governance_event = ctx.emit_governance_event(
                    kind="code_execute",
                    source="server_core.hlf_code_execute",
                    action="code_execute",
                    status="ok" if result.get("status") in {"ok", "dry_run_ok"} else "warning",
                    severity="info" if result.get("status") in {"ok", "dry_run_ok"} else "warning",
                    subject_id=str(result.get("trace_ref", "")),
                    details={
                        "entrypoint": entrypoint,
                        "gas_limit": gas_limit,
                        "tier": tier,
                        "dry_run": dry_run,
                        "compiled": result.get("compiled", False),
                        "verified": result.get("verified", False),
                        "executed": result.get("executed", False),
                        "sandbox_mode": result.get("sandbox_mode", ""),
                    },
                    agent_role="code_bearing_hlf",
                )
                result["governance_event"] = governance_event
            return result
        except Exception as exc:
            return {"status": "error", "compiled": False, "executed": False, "error": str(exc)}

    @mcp.tool()
    def hlf_validate(source: str) -> dict[str, Any]:
        """Quickly validate HLF syntax without full compilation."""
        return ctx.compiler.validate(source)

    @mcp.tool()
    def hlf_swarm_mechanics(
        source: str = "",
        handoff: dict[str, Any] | None = None,
        votes: list[dict[str, Any]] | None = None,
        dissent: list[dict[str, Any]] | None = None,
        progress_events: list[dict[str, Any]] | None = None,
        quorum: str = "strict",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Materialize bounded local delegation, voting, dissent, lineage, and progress as HLF artifacts."""
        return run_hlf_swarm_mechanics(
            ctx,
            source=source,
            handoff=handoff,
            votes=votes,
            dissent=dissent,
            progress_events=progress_events,
            quorum=quorum,
            persist=persist,
        )

    @mcp.tool()
    def hlf_benchmark(
        source: str, compare_text: str | None = None, domain: str | None = None
    ) -> dict[str, Any]:
        """Measure HLF token compression vs natural language."""
        return ctx.benchmark.analyze(source, compare_text=compare_text, domain=domain)

    @mcp.tool()
    def hlf_benchmark_suite() -> dict[str, Any]:
        """Run the full HLF benchmark suite against all 6 domain NLP templates."""
        return ctx.benchmark.benchmark_suite()

    @mcp.tool()
    def hlf_real_workflow_benchmark(
        workflow_ids: list[str] | None = None,
        mode: str = "patch-plan",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Benchmark real HLF self-improvement patch-plan workflows against non-HLF baselines."""
        result = ctx.benchmark.real_workflow_self_improvement_benchmark(
            workflow_ids=workflow_ids,
            mode=mode,
        )
        artifact = {
            "artifact_id": f"benchmark:{result['profile_name']}:{mode}",
            "profile_name": result["profile_name"],
            "benchmark_scores": dict(result.get("benchmark_scores") or {}),
            "topic": "hlf_real_workflow_benchmarks",
            "domains": list(result.get("workflow_ids") or []),
            "details": {
                "benchmark_kind": result.get("benchmark_kind"),
                "mode": mode,
                "headline": (result.get("summary") or {}).get("headline"),
                "covered_surfaces": (result.get("summary") or {}).get("covered_surfaces", []),
            },
            "result": result,
        }
        persisted = ctx.persist_benchmark_artifact(artifact) if persist else artifact
        return {**result, "artifact": persisted}

    @mcp.tool()
    def hlf_disassemble(bytecode_hex: str) -> dict[str, Any]:
        """Disassemble HLF .hlb bytecode to human-readable assembly."""
        try:
            bc_bytes = bytes.fromhex(bytecode_hex.strip())
            result = ctx.bytecoder.disassemble(bc_bytes)
            return {"status": "ok", **result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_submit_ast(ast_json: str) -> dict[str, Any]:
        """Fast-lane AST submission: skip LALR parse for pre-built JSON ASTs."""
        import json
        import os as _os

        try:
            ast = json.loads(ast_json)
        except json.JSONDecodeError as exc:
            return {"status": "error", "error": f"Invalid JSON: {exc}"}
        if not isinstance(ast, dict) or "statements" not in ast:
            return {"status": "error", "error": '"statements" key required in AST'}

        from hlf_mcp.hlf.compiler import _estimate_gas, _pass3_align_validate

        stmts = ast.get("statements", [])
        env: dict[str, Any] = {}
        try:
            from hlf_mcp.hlf.ethics.governor import GovernorError
            from hlf_mcp.hlf.ethics.governor import check as _ethics_check

            governor_result = _ethics_check(ast=ast, env=env, source="", tier="hearth")
            strict_mode = _os.environ.get("HLF_STRICT", "1") != "0"
            if not governor_result.passed:
                term = governor_result.termination
                if term is not None:
                    msg = (
                        f"Ethics Governor [{term.trigger}]: {term.message}\n"
                        f"Audit ID: {term.audit_id}"
                    )
                    if strict_mode:
                        return {"status": "blocked", "error": msg}
                    _log.warning("[HLF_STRICT=0] Governor suppressed: %s", msg)
                elif strict_mode:
                    return {"status": "blocked", "error": "; ".join(governor_result.blocks)}
                else:
                    _log.warning(
                        "[HLF_STRICT=0] Governor blocks: %s", "; ".join(governor_result.blocks)
                    )
        except GovernorError as exc:
            return {"status": "blocked", "error": str(exc)}
        except Exception as exc:  # pragma: no cover
            return {"status": "blocked", "error": f"Governor error (fail-closed): {exc}"}

        try:
            violations = _pass3_align_validate(stmts, strict=ctx.compiler.strict_align)
        except CompileError as exc:
            return {"status": "blocked", "error": str(exc)}

        gas = _estimate_gas(stmts)
        return {
            "status": "ok",
            "node_count": len(stmts),
            "gas_estimate": gas,
            "align_violations": violations,
        }

    @mcp.tool()
    def hlf_test_suite_summary(
        metrics_dir: str | None = None,
        include_output: bool = False,
    ) -> dict[str, Any]:
        """Return the latest persisted pytest suite summary from the metrics store."""
        return load_test_suite_summary(metrics_dir, include_output=include_output)

    @mcp.tool()
    def hlf_capture_symbolic_surface(
        source: str,
        surface_id: str = "",
        goal_id: str = "",
    ) -> dict[str, Any]:
        """Compile and audit a symbolic proof bundle from canonical HLF source and persist it for operator surfaces."""
        try:
            symbolic_surface = compile_symbolic_surface(source, compiler=ctx.compiler)
            resolved_surface_id = surface_id.strip() or hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
            resolved_goal_id = goal_id.strip() or resolved_surface_id
            audit_entries = audit_symbolic_surface(
                symbolic_surface,
                ctx.audit_chain,
                goal_id=resolved_goal_id,
                agent_role="hlf_symbolic_surface",
            )
            persisted = ctx.persist_symbolic_surface(
                {
                    "surface_id": resolved_surface_id,
                    "goal_id": resolved_goal_id,
                    "source": source,
                    "symbolic_surface": symbolic_surface,
                    "audit_entries": audit_entries,
                    "operator_summary": (
                        f"Runtime-generated symbolic surface '{resolved_surface_id}' recorded "
                        f"{len(symbolic_surface.get('relation_edges', []))} relation edge(s)."
                    ),
                }
            )
            return {
                "status": "ok",
                "surface_id": resolved_surface_id,
                "goal_id": resolved_goal_id,
                "symbolic_surface": symbolic_surface,
                "audit_entries": audit_entries,
                "persisted": persisted,
            }
        except CompileError as exc:
            return {"status": "error", "error": str(exc), "surface_id": surface_id or None}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "surface_id": surface_id or None}

    @mcp.tool()
    def hlf_governance_proof_verify(proof: dict[str, Any], include_report: bool = False) -> dict[str, Any]:
        """Verify a first-class governance proof hash chain and its memory/runtime anchors."""
        if not isinstance(proof, dict):
            return {"status": "error", "verified": False, "error": "proof must be an object"}
        report = verify_governance_proof(proof)
        if include_report:
            report["human_report"] = render_proof_markdown(proof)
        return report

    @mcp.tool()
    def hlf_weekly_evidence_summary(
        metrics_dir: str | None = None,
    ) -> dict[str, Any]:
        """Return the governed weekly evidence history summary from the metrics store."""
        from hlf_mcp.weekly_artifacts import summarize_weekly_artifacts

        resolved_metrics_dir = Path(metrics_dir).expanduser() if metrics_dir else None
        return summarize_weekly_artifacts(resolved_metrics_dir)

    @mcp.tool()
    def hlf_compile_wasm(
        source: str,
        module_name: str = "hlf_module",
    ) -> dict[str, Any]:
        """Compile HLF source to WebAssembly Text Format (WAT).

        Produces WAT output that can be compiled to .wasm via wat2wasm or
        run directly in wasmtime. Maps HLF's stack-based bytecode to WASM's
        stack machine with structured control flow.

        Args:
            source: HLF source code to compile.
            module_name: Name for the WASM module (default: 'hlf_module').

        Returns:
            dict with 'wat', 'module_name', 'opcode_count', and 'status'.
        """
        from hlf_mcp.hlf.wasm_compiler import WasmCompiler

        try:
            compiler = WasmCompiler(module_name=module_name)
            wat_text = compiler.compile_file_source(source)
            opcode_count = wat_text.count("\n  ")  # rough count of instructions
            return {
                "status": "ok",
                "module_name": module_name,
                "opcode_count": opcode_count,
                "wat": wat_text,
            }
        except Exception as exc:
            return {
                "status": "error",
                "module_name": module_name,
                "error": str(exc),
                "wat": "",
            }

    return {
        "hlf_compile": hlf_compile,
        "hlf_format": hlf_format,
        "hlf_lint": hlf_lint,
        "hlf_run": hlf_run,
        "hlf_code_execute": hlf_code_execute,
        "hlf_validate": hlf_validate,
        "hlf_swarm_mechanics": hlf_swarm_mechanics,
        "hlf_governance_proof_verify": hlf_governance_proof_verify,
        "hlf_benchmark": hlf_benchmark,
        "hlf_benchmark_suite": hlf_benchmark_suite,
        "hlf_real_workflow_benchmark": hlf_real_workflow_benchmark,
        "hlf_disassemble": hlf_disassemble,
        "hlf_submit_ast": hlf_submit_ast,
        "hlf_test_suite_summary": hlf_test_suite_summary,
        "hlf_capture_symbolic_surface": hlf_capture_symbolic_surface,
        "hlf_weekly_evidence_summary": hlf_weekly_evidence_summary,
        "hlf_compile_wasm": hlf_compile_wasm,
    }
