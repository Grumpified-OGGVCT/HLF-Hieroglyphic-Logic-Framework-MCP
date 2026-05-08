from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.agent_prompt import build_hlf_native_system_prompt


def register_agent_prompts(mcp: FastMCP) -> dict[str, Any]:
    @mcp.prompt()
    def hlf_native_agent(
        tier: str = "forge",
        language: str = "en",
        focus: str = "",
        swarm_mode: bool = False,
    ) -> str:
        """HLF-native agent prompt enforcing NLP→HLF→gates→execution/coordination→NLP."""
        return build_hlf_native_system_prompt(
            tier=tier,
            language=language,
            focus=focus,
            swarm_mode=swarm_mode,
        )

    return {"hlf_native_agent": hlf_native_agent}
