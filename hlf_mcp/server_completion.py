"""
Governed Completion MCP Tools.

Registers the hlf_governed_complete tool — a single-call entry point
for the full classify → route → orchestrate pipeline.

Registration: imported and called from server.py alongside other
register_*_tools() functions.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.governed_complete import governed_complete
from hlf_mcp.hlf.model_config import load_model_config
from hlf_mcp.hlf.model_orchestrator import ModelOrchestrationError, ModelOrchestrator
from hlf_mcp.server_context import ServerContext

logger = logging.getLogger(__name__)


def register_completion_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    """Register governed completion tools with the FastMCP server.

    Returns a registry dict mapping tool names to their callable function objects,
    consistent with the convention used by all other register_*_tools() functions.
    """

    @mcp.tool()
    async def hlf_governed_complete(
        intent: str,
        messages: list[dict[str, Any]],
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        trust_state: str = "trusted",
        advisory_fallback: bool = True,
        agent_id: str = "",
    ) -> dict[str, Any]:
        """Execute a full governed completion using the HLF routing pipeline.

        Runs the classify → route → orchestrate pipeline in one call:
          1. Classifies the intent into a TaskEnvelope (task type, size, category).
          2. Maps the envelope to an HLF Workload string.
          3. Builds a GovernedRouteVerdict via hlf_route_governed_request logic.
          4. Dispatches to ModelOrchestrator with Ollama-Cloud-first escalation.

        Args:
            intent: Natural-language description of what to accomplish.
                    Used to classify the task and select the routing lane.
            messages: OpenAI-format conversation messages.
            system: Optional system message.
            temperature: Sampling temperature (0.0–2.0). None = model default.
            max_tokens: Maximum response tokens. None = model default.
            trust_state: Governance trust posture for route-gate evaluation.
                         One of: "trusted", "approved", "watched", "untrusted".
            advisory_fallback: When True, proceeds in advisory (ungoverned)
                               mode if routing is denied due to missing benchmark
                               evidence. When False, raises on any routing denial.
            agent_id: Optional agent identifier for audit trail.

        Returns:
            dict with keys:
              content          — model response text
              model_used       — model name that generated the response
              provider_used    — "ollama" | "openrouter"
              lane             — HLF lane used for orchestration
              workload         — HLF workload string
              task_type        — classified task type
              task_category    — broad category (code, build, deploy, …)
              task_size        — effort size (micro, small, medium, large, epic)
              advisory_mode    — True if routing verdict was denied but advisory fallback applied
              governance_warning — human-readable warning when advisory_mode is True
              verdict          — full GovernedRouteVerdict as dict
              escalation_depth — number of models tried before success
              latency_s        — wall-clock time in seconds
              audit_trail      — per-attempt attempt records
        """
        config = load_model_config()
        orchestrator = ModelOrchestrator(config)
        try:
            result = await governed_complete(
                intent=intent,
                messages=messages,
                orchestrator=orchestrator,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
                trust_state=trust_state,
                advisory_fallback=advisory_fallback,
            )
        except ModelOrchestrationError as exc:
            logger.error(
                "hlf_governed_complete failed for intent=%r agent_id=%r: %s",
                intent[:120], agent_id, exc,
            )
            return {
                "error": str(exc),
                "lane": getattr(exc, "lane", ""),
                "audit_trail": getattr(exc, "audit_trail", []),
            }
        finally:
            await orchestrator.close()

        out = result.to_dict()
        if agent_id:
            out["agent_id"] = agent_id
        return out

    return {"hlf_governed_complete": hlf_governed_complete}
