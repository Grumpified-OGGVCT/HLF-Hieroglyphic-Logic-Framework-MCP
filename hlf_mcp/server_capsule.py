from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf import insaits
from hlf_mcp.hlf.capsules import capsule_for_tier
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.server_context import ServerContext


def register_capsule_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_capsule_validate(source: str, tier: str = "hearth") -> dict[str, Any]:
        """Validate HLF source AST against the intent capsule for the given tier."""
        try:
            result = ctx.compiler.compile(source)
            capsule = capsule_for_tier(tier)
            stmts = result["ast"].get("statements", [])
            violations = capsule.validate_ast(stmts)
            return {
                "status": "ok",
                "tier": tier,
                "violations": violations,
                "passed": len(violations) == 0,
            }
        except CompileError as exc:
            return {"status": "error", "error": str(exc)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_capsule_run(
        source: str,
        tier: str = "hearth",
        gas_limit: int = 1000,
    ) -> dict[str, Any]:
        """Compile, capsule-validate, then execute HLF source within a sandboxed tier."""
        try:
            result = ctx.compiler.compile(source)
            capsule = capsule_for_tier(tier)
            stmts = result["ast"].get("statements", [])
            violations = capsule.validate_ast(stmts)
            if violations:
                return {
                    "status": "capsule_violation",
                    "tier": tier,
                    "violations": violations,
                }
            effective_gas = min(gas_limit, capsule.max_gas)
            bc = ctx.bytecoder.encode(result["ast"])
            run_result = ctx.runtime.run(
                bc,
                gas_limit=effective_gas,
                ast=result["ast"],
                source=source,
                tier=tier,
            )
            run_result["tier"] = tier
            return run_result
        except CompileError as exc:
            return {"status": "compile_error", "error": str(exc)}
        except Exception as exc:
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
    ) -> dict[str, Any]:
        """Call a host function from the registry."""
        try:
            args = json.loads(args_json)
            if not isinstance(args, list):
                return {"status": "error", "error": "args_json must be a JSON array"}
            result = ctx.host_registry.call(function_name, args, tier)
            return {"status": "ok", "result": result}
        except json.JSONDecodeError as exc:
            return {"status": "error", "error": f"Invalid args_json: {exc}"}
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
        "hlf_host_functions": hlf_host_functions,
        "hlf_host_call": hlf_host_call,
        "hlf_tool_list": hlf_tool_list,
        "hlf_similarity_gate": hlf_similarity_gate,
    }