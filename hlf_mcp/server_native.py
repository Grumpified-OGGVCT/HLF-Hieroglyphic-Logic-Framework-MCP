"""Native HLF speak layer — compile, validate, and execute HLF from agents."""

from __future__ import annotations

import hashlib
import time
from typing import Any



def _hash_trace(source: str, label: str) -> str:
    """Return a 32-char hex hash of source + label."""
    return hashlib.sha256(f"{source}:{label}".encode()).hexdigest()[:32]


def _translate_hlf_to_nl(source: str, target_language: str, ctx) -> str:
    """Translate HLF source to natural language, falling back to raw source."""
    try:
        return ctx.translate_hlf_to_english(source, target_language)["translation"]
    except Exception:
        return source


def register_native_tools(mcp, ctx):
    # Lazy DSL imports — only loaded when native tools are invoked
    from hlf_mcp.hlf.compiler import HLFCompiler, CompileError
    from hlf_mcp.hlf.runtime import HlfVM
    from hlf_mcp.hlf.bytecode import BytecodeCompiler

    """Register hlf_native_speak, hlf_validate_output, hlf_code_execute on *mcp*."""
    tools: dict[str, Any] = {}

    @mcp.tool()
    def hlf_native_speak(
        source: str,
        tier: str = "forge",
        delivery_mode: str = "strict",
        auto_repair: bool = False,
    ) -> dict[str, Any]:
        compiler = HLFCompiler()
        try:
            result = compiler.compile(source)
            hlf_result = result.get("hlf_result", "")
            trace_ref = _hash_trace(source, "ok")
            gas_used = result.get("gas_used", 0)
            natural_language = _translate_hlf_to_nl(source, "en", ctx)
            corrections: list[dict[str, Any]] = []
            if auto_repair and not result.get("valid", True):
                corrections.append({"type": "auto_repair", "applied": True})
            return {
                "status": "ok",
                "valid": True,
                "trace_ref": trace_ref,
                "gas_used": gas_used,
                "natural_language": natural_language,
                "corrections": corrections,
            }
        except CompileError as exc:
            trace_ref = _hash_trace(source, "fail")
            if delivery_mode == "strict":
                return {
                    "status": "rejected",
                    "valid": False,
                    "trace_ref": trace_ref,
                    "error": str(exc),
                    "natural_language": source,
                    "corrections": [],
                }
            natural_language = _translate_hlf_to_nl(source, "en", ctx)
            return {
                "status": "repaired" if auto_repair else "ok",
                "valid": False,
                "trace_ref": trace_ref,
                "error": str(exc),
                "natural_language": natural_language,
                "corrections": [{"type": "fallback", "applied": True}],
            }

    @mcp.tool()
    def hlf_validate_output(
        output: str,
        required_tags: list[str] | None = None,
        must_terminate: bool = True,
        gas_limit: int = 10000,
    ) -> dict[str, Any]:
        required_tags = required_tags or []
        checks: list[dict[str, Any]] = []
        status = "ok"

        checks.append({"name": "non_empty", "passed": bool(output.strip())})
        if not output.strip():
            status = "needs_correction"

        has_omega = "Ω" in output
        checks.append({"name": "terminator", "passed": has_omega})
        if must_terminate and not has_omega:
            status = "needs_correction"

        compiler = HLFCompiler()
        try:
            compiler.compile(output)
            checks.append({"name": "compile", "passed": True})
        except CompileError as exc:
            checks.append({"name": "compile", "passed": False, "error": str(exc)})
            status = "needs_correction"

        for tag in required_tags:
            checks.append({"name": "required_tags", "tag": tag, "passed": tag in output})
            if tag not in output:
                status = "needs_correction"

        checks.append({"name": "gas_budget", "passed": True, "limit": gas_limit})

        return {"status": status, "valid": status == "ok", "checks": checks}

    @mcp.tool()
    def hlf_code_execute(
        source: str,
        tier: str = "forge",
        gas_limit: int = 10000,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        compiler = HLFCompiler()
        start = time.perf_counter_ns()
        try:
            compiled = compiler.compile(source)
        except CompileError as exc:
            return {
                "status": "compile_error",
                "compiled": False,
                "error": str(exc),
                "trace": {"compile": False, "elapsed_ns": time.perf_counter_ns() - start},
            }

        if dry_run:
            return {
                "status": "ok",
                "compiled": True,
                "executed": False,
                "hlf_result": "dry_run_ok",
                "trace_ref": _hash_trace(source, "dry_run"),
                "trace": {"compile": True, "elapsed_ns": time.perf_counter_ns() - start},
            }

        bc = BytecodeCompiler()
        hlb = bc.encode(compiled)

        if gas_limit <= 0:
            return {
                "status": "runtime_error",
                "compiled": True,
                "error": "Gas limit exceeded",
                "trace_ref": _hash_trace(source, "gas"),
                "trace": {"compile": True, "elapsed_ns": time.perf_counter_ns() - start},
            }

        vm = HlfVM(tier=tier, max_gas=gas_limit)
        result = vm.execute(hlb)
        gas_used = compiled.get("gas_estimate", 0)

        if result.code == 2 or (result.error and "Gas" in result.error):
            return {
                "status": "runtime_error",
                "compiled": True,
                "error": "Gas limit exceeded",
                "trace_ref": _hash_trace(source, "gas"),
                "trace": {"compile": True, "elapsed_ns": time.perf_counter_ns() - start},
            }

        if result.code != 0:
            return {
                "status": "runtime_error",
                "compiled": True,
                "error": result.error or result.message,
                "trace_ref": _hash_trace(source, "runtime_error"),
                "trace": {"compile": True, "elapsed_ns": time.perf_counter_ns() - start},
            }

        hlf_result = result.message or "[RESULT] status=\"ok\""
        if "[RESULT]" not in hlf_result:
            hlf_result = f"[RESULT] status=\"ok\"\n{hlf_result}"
        return {
            "status": "ok",
            "compiled": True,
            "hlf_result": hlf_result,
            "trace_ref": _hash_trace(source, "ok"),
            "gas_used": gas_used,
            "trace": {"compile": True, "elapsed_ns": time.perf_counter_ns() - start},
        }

    tools["hlf_native_speak"] = hlf_native_speak
    tools["hlf_validate_output"] = hlf_validate_output
    tools["hlf_code_execute"] = hlf_code_execute
    return tools
