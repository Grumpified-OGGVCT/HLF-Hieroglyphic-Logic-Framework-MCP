from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.server_context import ServerContext


def register_verifier_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_verify_formal_ast(
        ast: dict[str, Any] | None = None,
        source: str | None = None,
        gas_budget: int = 10_000,
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
        governance_event = ctx.emit_governance_event(
            kind="formal_verification",
            source="server_verifier.hlf_verify_formal_ast",
            action="verify_formal_ast",
            status="warning" if report.failed_count else "ok",
            severity="warning" if report.failed_count else "info",
            details={
                "gas_budget": gas_budget,
                "solver_name": ctx.formal_verifier.solver_name,
                "report": report.to_dict(),
            },
            agent_role="formal_verifier",
            anomaly_score=1.0 if report.failed_count else 0.0,
        )
        return {
            "status": "ok",
            "solver_name": ctx.formal_verifier.solver_name,
            "report": report.to_dict(),
            "governance_event": governance_event,
        }

    @mcp.tool()
    def hlf_verify_gas_budget(
        task_costs: list[int],
        budget: int,
        property_name: str = "gas_budget",
    ) -> dict[str, Any]:
        """Prove or refute that a deterministic gas budget covers the supplied task costs."""
        result = ctx.formal_verifier.verify_gas_budget(task_costs, budget, property_name=property_name)
        governance_event = ctx.emit_governance_event(
            kind="formal_verification",
            source="server_verifier.hlf_verify_gas_budget",
            action="verify_gas_budget",
            status="warning" if not result.is_proven() else "ok",
            severity="warning" if not result.is_proven() else "info",
            details={
                "budget": budget,
                "task_costs": list(task_costs),
                "result": result.to_dict(),
            },
            agent_role="formal_verifier",
            anomaly_score=1.0 if not result.is_proven() else 0.0,
        )
        return {
            "status": "ok",
            "result": result.to_dict(),
            "governance_event": governance_event,
        }

    return {
        "hlf_verify_formal_ast": hlf_verify_formal_ast,
        "hlf_verify_gas_budget": hlf_verify_gas_budget,
    }