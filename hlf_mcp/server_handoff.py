from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import Icon, ToolAnnotations
from hlf_mcp.server_icons import _emoji_icon

from hlf_mcp.handoff_events import (
    build_handoff_contract_template,
    evaluate_semantic_drift,
    normalize_handoff_event,
    verify_handoff_chain,
)
from hlf_mcp.instinct.orchestration import (
    build_orchestration_contract,
    normalize_execution_trace,
    normalize_task_dag,
    summarize_execution_trace,
)
from hlf_mcp.server_context import ServerContext
import warnings


def _build_persona_lineage_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a bounded persona lineage graph from handoff chain events."""
    edges: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    for event in events:
        src = str(event.get("source_persona") or "")
        tgt = str(event.get("target_persona") or "")
        if src or tgt:
            if src:
                seen_roles.add(src)
            if tgt:
                seen_roles.add(tgt)
            edges.append({
                "from": src,
                "to": tgt,
                "event_hash": str(event.get("event_hash") or ""),
                "lifecycle_phase": str(event.get("lifecycle_phase") or ""),
            })
    return {
        "claim_lane": "bridge-true",
        "roles_present": sorted(seen_roles),
        "transition_count": len(edges),
        "transitions": edges,
        "proof_boundary": {
            "persona_lineage_tracking": True,
            "runtime_enforcement": False,
        },
    }


def register_handoff_tools(mcp: FastMCP, ctx: ServerContext) -> dict[str, Any]:
    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        icons=[_emoji_icon("📋")],
    )
    def hlf_record_handoff_event(
        delegator: str,
        delegate: str,
        scope: str,
        constraints: dict[str, Any] | list[Any] | None = None,
        delegation_gas_ceiling: int | None = None,
        deadline: str = "",
        epoch: str = "",
        event_type: str = "delegate",
        claim_lane: str = "",
        proof_boundary: dict[str, Any] | None = None,
        payload: Any = None,
        payload_json: str = "",
        parent_event_hash: str = "",
        vm_gas_limit: int | None = None,
        source_agent_kind: str = "hlf",
        lifecycle_phase: str = "execute",
        route_trace_ref: str | dict[str, Any] | None = None,
        orchestration_ref: str | dict[str, Any] | None = None,
        original_intent: str = "",
        delegate_result: str = "",
        semantic_drift_threshold: float = 0.55,
        source_persona: str = "",
        target_persona: str = "",
        persist: bool = True,
    ) -> dict[str, Any]:
        """Record a conformant JSON handoff event primitive with hashes and bounds."""
        warnings.warn("hlf_record_handoff_event is deprecated, use sg_coordinate_handoff_record instead", DeprecationWarning, stacklevel=2)
        parent_lineage_hash = ""
        if parent_event_hash and hasattr(ctx, "get_handoff_event"):
            parent = ctx.get_handoff_event(parent_event_hash)
            if isinstance(parent, dict):
                parent_lineage_hash = str(parent.get("lineage_hash") or "")
        semantic_drift = {}
        if original_intent or delegate_result:
            semantic_drift = evaluate_semantic_drift(
                original_intent=original_intent,
                delegate_result=delegate_result,
                threshold=semantic_drift_threshold,
            )
        event = normalize_handoff_event(
            delegator=delegator,
            delegate=delegate,
            scope=scope,
            constraints=constraints,
            delegation_gas_ceiling=delegation_gas_ceiling,
            deadline=deadline,
            epoch=epoch,
            event_type=event_type,
            claim_lane=claim_lane,
            proof_boundary=proof_boundary,
            payload=payload,
            payload_json=payload_json,
            parent_event_hash=parent_event_hash,
            parent_lineage_hash=parent_lineage_hash,
            vm_gas_limit=vm_gas_limit,
            source_agent_kind=source_agent_kind,
            lifecycle_phase=lifecycle_phase,
            route_trace_ref=route_trace_ref,
            orchestration_ref=orchestration_ref,
            semantic_drift=semantic_drift,
            source_persona=source_persona,
            target_persona=target_persona,
        )
        if event.get("status") != "ok" or not persist:
            return event
        return ctx.persist_handoff_event(event)

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        icons=[_emoji_icon("📋")],
    )
    def hlf_handoff_chain(event_hash: str = "") -> dict[str, Any]:
        """Return the latest or selected linear handoff chain and verification summary."""
        warnings.warn("hlf_handoff_chain is deprecated, use sg_coordinate_handoff_chain instead", DeprecationWarning, stacklevel=2)
        chain = ctx.get_handoff_chain(event_hash=event_hash or None)
        if not isinstance(chain, dict):
            return {
                "status": "not_found",
                "event_hash": event_hash,
                "handoff_chain": [],
                "verification_summary": verify_handoff_chain([]),
            }
        events = [event for event in chain.get("events", []) if isinstance(event, dict)]
        verification = verify_handoff_chain(events)
        persona_graph = _build_persona_lineage_graph(events)
        return {
            "status": "ok",
            "head_event_hash": chain.get("head_event_hash"),
            "handoff_chain": events,
            "verification_summary": verification,
            "persona_lineage": persona_graph,
            "memory_freshness": chain.get("memory_freshness", {}),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        icons=[_emoji_icon("🎼")],
    )
    def hlf_orchestration_contract(
        task_dag: list[dict[str, Any]],
        execution_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Normalize a JSON plan DAG and return the DAG-to-execution contract surface."""
        warnings.warn("hlf_orchestration_contract is deprecated, use sg_coordinate_orchestration_contract instead", DeprecationWarning, stacklevel=2)
        normalized_dag = normalize_task_dag(task_dag or [])
        normalized_trace = normalize_execution_trace(
            execution_trace or [],
            task_dag=normalized_dag,
        )
        return {
            "status": "ok",
            "$type": "hlf://schema/orchestration_contract",
            "schema": "hlf-orchestration-contract-v1",
            "lifecycle_phases": ["specify", "plan", "execute", "verify", "merge"],
            "task_dag": normalized_dag,
            "execution_trace": normalized_trace,
            "execution_summary": summarize_execution_trace(
                normalized_trace,
                task_dag=normalized_dag,
            ),
            "orchestration_contract": build_orchestration_contract(
                normalized_dag,
                normalized_trace,
            ),
            "proof_boundary": {
                "contract_surface": True,
                "framework_or_dsl": False,
                "requires_hlf_compilation": False,
            },
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("📋")],
    )
    def hlf_handoff_contract_template(
        template: str,
        scope: str,
        participants: list[str] | None = None,
        lifecycle_phase: str = "verify",
    ) -> dict[str, Any]:
        """Return JSON handoff event composition templates for delegation/vote/dissent/review-board flows."""
        warnings.warn("hlf_handoff_contract_template is deprecated, use sg_coordinate_contract_template instead", DeprecationWarning, stacklevel=2)
        return build_handoff_contract_template(
            template=template,
            scope=scope,
            participants=participants or [],
            lifecycle_phase=lifecycle_phase,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
        icons=[_emoji_icon("📋")],
    )
    def hlf_handoff_semantic_drift_check(
        original_intent: str,
        delegate_result: str,
        threshold: float = 0.55,
    ) -> dict[str, Any]:
        """Check semantic drift between delegation intent and delegate result without HLF compilation."""
        warnings.warn("hlf_handoff_semantic_drift_check is deprecated, use sg_coordinate_drift_check instead", DeprecationWarning, stacklevel=2)
        return {
            "status": "ok",
            "semantic_drift": evaluate_semantic_drift(
                original_intent=original_intent,
                delegate_result=delegate_result,
                threshold=threshold,
            ),
        }

    def _register_sg_aliases(mcp: FastMCP, aliases: dict):
        """Register sg_ aliases that delegate to existing hlf_ tools."""
        import functools
        for sg_name, hlf_func in aliases.items():
            def _make_wrapper(_name, _func):
                @functools.wraps(_func)
                def _wrapper(*args, **kwargs):
                    return _func(*args, **kwargs)
                _wrapper.__name__ = _name
                return _wrapper
            wrapper = _make_wrapper(sg_name, hlf_func)
            mcp.tool(name=sg_name)(wrapper)

    _register_sg_aliases(mcp, {
        "sg_coordinate_handoff_record": hlf_record_handoff_event,
        "sg_coordinate_handoff_chain": hlf_handoff_chain,
        "sg_coordinate_orchestration_contract": hlf_orchestration_contract,
        "sg_coordinate_contract_template": hlf_handoff_contract_template,
        "sg_coordinate_drift_check": hlf_handoff_semantic_drift_check,
    })

    return {
        "hlf_record_handoff_event": hlf_record_handoff_event,
        "hlf_handoff_chain": hlf_handoff_chain,
        "hlf_orchestration_contract": hlf_orchestration_contract,
        "hlf_handoff_contract_template": hlf_handoff_contract_template,
        "hlf_handoff_semantic_drift_check": hlf_handoff_semantic_drift_check,
        "sg_coordinate_handoff_record": hlf_record_handoff_event,
        "sg_coordinate_handoff_chain": hlf_handoff_chain,
        "sg_coordinate_orchestration_contract": hlf_orchestration_contract,
        "sg_coordinate_contract_template": hlf_handoff_contract_template,
        "sg_coordinate_drift_check": hlf_handoff_semantic_drift_check,
    }
