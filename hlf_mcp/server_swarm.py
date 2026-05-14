"""HLF Swarm MCP surface — thin delegation to SwarmOrchestrator.

Exposes 4 MCP tools per plan:
  hlf_swarm_progress  — progress event log for a swarm
  hlf_swarm_run       — execute a 3-agent swarm (Planner→Executor→Verifier)
  hlf_swarm_witness   — trust/degradation status for an agent or swarm
  hlf_swarm_verify    — formal verification results for an HLF message

The heavy lifting happens in hlf_mcp.hlf.swarm_orchestrator.SwarmOrchestrator.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.types import Icon, ToolAnnotations

from hlf_mcp.server_icons import _emoji_icon
from hlf_mcp.task_helpers import task_meta

from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.swarm_observer import SwarmObserver
from hlf_mcp.hlf.swarm_orchestrator import SwarmOrchestrator
from hlf_mcp.hlf.witness_governance import WitnessGovernance
from hlf_mcp.hlf.exceptions import HLFToolError
from hlf_mcp.hlf import HLFCompiler

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared engine instances (created once, reused)
# ---------------------------------------------------------------------------

_observer = SwarmObserver()
_governance = WitnessGovernance()
_verifier = FormalVerifier()
_compiler = HLFCompiler()
_orchestrator = SwarmOrchestrator(
    observer=_observer,
    governance=_governance,
    verifier=_verifier,
)


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register_swarm_tools(mcp_instance: Any) -> dict[str, Any]:  # noqa: C901
    """Register the 4 swarm MCP tools on an MCP server instance."""

    registered: dict[str, Any] = {}

    # ── hlf_swarm_run ────────────────────────────────────────────────────────

    @mcp_instance.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("🐝")],
        meta=task_meta(),
    )
    async def hlf_swarm_run(goal: str, language: str = "english") -> str:
        """Run a 3-agent swarm (Planner→Executor→Verifier) on a natural-language goal.

        Uses the live HLF translation → compilation pipeline. Every phase
        invokes language_to_hlf + compile — zero simulation. Results include
        trust scoring from witness_governance and verification from formal_verifier.

        Args:
            goal: Natural language description of the task.
            language: Source language (default "english").

        Returns:
            JSON with swarm_id, phases, final_hlf, final_nl, trust_scores,
            compile_success, and verification diagnostics.
        """
        result = _orchestrator.run(goal, language=language)
        return json.dumps({
            "swarm_id": result.swarm_id,
            "task_id": result.task_id,
            "final_status": result.final_status,
            "compile_success": result.compile_success,
            "scope_score": result.scope_score,
            "thoroughness_score": result.thoroughness_score,
            "total_tokens": result.total_tokens,
            "total_time_ms": result.total_time_ms,
            "final_nl": result.final_nl,
            "final_hlf": result.final_hlf,
            "phases": [
                {
                    "phase_id": p.phase_id,
                    "agent_id": p.agent_id,
                    "role": p.role,
                    "action": p.action,
                    "status": p.status,
                    "metrics": p.metrics,
                }
                for p in result.phases
            ],
        })

    registered["hlf_swarm_run"] = hlf_swarm_run

    # ── hlf_swarm_progress ────────────────────────────────────────────────────

    @mcp_instance.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("🐝")],
    )
    async def hlf_swarm_progress(swarm_id: str = "") -> str:
        """Query swarm progress events.

        If swarm_id is provided, returns events for that swarm only.
        Otherwise, returns all recent events across all swarms.

        Args:
            swarm_id: Optional swarm identifier to filter by.

        Returns:
            JSON with event_type, agent_id, role, message, timestamp per event.
        """
        if swarm_id:
            entries = _observer.latest_for(swarm_id)
        else:
            entries = _observer.get_log()
        return json.dumps(entries)

    registered["hlf_swarm_progress"] = hlf_swarm_progress

    # ── hlf_swarm_witness ─────────────────────────────────────────────────────

    @mcp_instance.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("🐝")],
    )
    async def hlf_swarm_witness(agent_id: str) -> str:
        """Get witness-governance trust status for an agent.

        Returns trust scores for the specified agent. The governance system
        enforces: aggregate_score >= 4.0 ∧ scored ≥ 3 ∧ corroborating
        witnesses ≥ 2 → restricted.

        Args:
            agent_id: The agent identifier (e.g., "planner", "executor").

        Returns:
            JSON with agent_id, trust_score, and any degradation info.
        """
        snapshot = _governance.get_snapshot(agent_id)
        return json.dumps(snapshot.to_dict() if snapshot else {"agent_id": agent_id, "trust": None})

    registered["hlf_swarm_witness"] = hlf_swarm_witness

    # ── hlf_swarm_verify ──────────────────────────────────────────────────────

    @mcp_instance.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("🐝")],
    )
    async def hlf_swarm_verify(hlf_source: str) -> str:
        """Run formal verification on an HLF message.

        Checks type invariants, range assertions, null safety, gas bounds,
        and spec gates. Returns a structured list of findings.

        Args:
            hlf_source: Raw HLF source to verify.

        Returns:
            JSON with verification results including severity, category,
            message, and location for each finding.
        """
        try:
            ast_result = _compiler.compile(hlf_source)
            ast = ast_result.get("ast", ast_result) if ast_result else {}
            report = _verifier.verify_ast(ast)
            return json.dumps(report.to_dict())
        except Exception as exc:
            raise HLFToolError(str(exc))

    registered["hlf_swarm_verify"] = hlf_swarm_verify

    return registered
