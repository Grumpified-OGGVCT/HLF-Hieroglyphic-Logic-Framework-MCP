from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.instinct.lifecycle import SDDRealignmentEvent
from hlf_mcp.server_context import ServerContext


def register_instinct_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool()
    def hlf_instinct_step(
        mission_id: str,
        phase: str,
        payload: dict[str, Any] | None = None,
        override: bool = False,
        cove_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Advance an Instinct SDD lifecycle mission, preserving spec, task_dag, and verification payloads by phase."""
        return ctx.instinct_mgr.step(
            mission_id,
            phase=phase,
            payload=payload or {},
            override=override,
            cove_result=cove_result,
        )

    @mcp.tool()
    def hlf_instinct_get(mission_id: str) -> dict[str, Any]:
        """Get the current state of an Instinct SDD mission."""
        mission = ctx.instinct_mgr.get_mission(mission_id)
        if mission is None:
            return {"error": f"Mission '{mission_id}' not found", "mission_id": mission_id}
        from hlf_mcp.instinct.lifecycle import _ok_state

        return _ok_state(mission)

    @mcp.tool()
    def hlf_spec_lifecycle(
        mission_id: str,
        phase: str,
        action: str = "advance",
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Manage an Instinct spec lifecycle mission through SPECIFY→PLAN→EXECUTE→VERIFY→MERGE."""
        valid_phases = {"SPECIFY", "PLAN", "EXECUTE", "VERIFY", "MERGE"}
        phase_upper = phase.upper()
        if phase_upper not in valid_phases:
            return {
                "status": "error",
                "error": f"Invalid phase {phase!r}. Must be one of: {', '.join(sorted(valid_phases))}",
            }

        if action == "get":
            mission = ctx.instinct_mgr.get_mission(mission_id)
            if mission is None:
                return {"status": "error", "error": f"Mission '{mission_id}' not found"}
            from hlf_mcp.instinct.lifecycle import _ok_state

            return {"status": "ok", "mission": _ok_state(mission)}

        try:
            result = ctx.instinct_mgr.step(
                mission_id,
                phase=phase_upper.lower(),
                payload=evidence or {},
            )
            return {"status": "ok", "mission": result}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    @mcp.tool()
    def hlf_instinct_realign(
        mission_id: str,
        change_type: str,
        change_description: str,
        affected_nodes: list[str] | None = None,
        triggered_by: str = "operator",
    ) -> dict[str, Any]:
        """Record a deterministic SDD realignment event without skipping the lifecycle state machine."""
        return ctx.instinct_mgr.realign(
            mission_id,
            SDDRealignmentEvent(
                triggered_by=triggered_by,
                change_type=change_type,
                change_description=change_description,
                affected_nodes=list(affected_nodes or []),
            ),
        )

    @mcp.tool()
    def hlf_instinct_list() -> dict[str, Any]:
        """List tracked Instinct lifecycle missions with their current phase and realignment counts."""
        return {"status": "ok", "missions": ctx.instinct_mgr.list_missions()}

    return {
        "hlf_instinct_step": hlf_instinct_step,
        "hlf_instinct_get": hlf_instinct_get,
        "hlf_spec_lifecycle": hlf_spec_lifecycle,
        "hlf_instinct_realign": hlf_instinct_realign,
        "hlf_instinct_list": hlf_instinct_list,
    }