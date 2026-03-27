"""
HLF MCP Server — Hieroglyphic Logic Framework Model Context Protocol Server.

Provides the complete HLF toolchain as MCP tools accessible via:
  - stdio     (Claude Desktop, local agents)
  - sse       (HTTP/SSE, remote agents, Docker)
  - streamable-http (modern MCP clients)

Transport is selected via the HLF_TRANSPORT environment variable.
  HLF_TRANSPORT=stdio             (default)
  HLF_TRANSPORT=sse               HTTP + SSE on HLF_HOST:HLF_PORT
  HLF_TRANSPORT=streamable-http   Streamable HTTP on HLF_HOST:HLF_PORT

Quick start:
    docker run -e HLF_TRANSPORT=sse -e HLF_PORT=<explicit-port> -p <explicit-port>:<explicit-port> hlf-mcp
    # → SSE endpoint:          GET  http://localhost:$HLF_PORT/sse
    # → Messages endpoint:     POST http://localhost:$HLF_PORT/messages/
    # → Streamable HTTP:       POST http://localhost:$HLF_PORT/mcp  (if transport=streamable-http)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from hlf_mcp.hlf.entropy_anchor import evaluate_entropy_anchor
from hlf_mcp.doc_ingest import DocumentIngester, summarize_reports
from hlf_mcp.server_capsule import register_capsule_tools
from hlf_mcp.server_completion import register_completion_tools
from hlf_mcp.server_context import build_server_context, check_governance_manifest
from hlf_mcp.server_core import register_core_tools
from hlf_mcp.server_instinct import register_instinct_tools
from hlf_mcp.server_instructions import build_server_instructions
from hlf_mcp.server_memory import register_memory_tools
from hlf_mcp.server_profiles import register_profile_tools
from hlf_mcp.server_resources import register_resources
from hlf_mcp.server_translation import register_translation_tools
from hlf_mcp.server_verifier import register_verifier_tools

_log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Server instance ────────────────────────────────────────────────────────────

_HOST = os.environ.get("HLF_HOST", "0.0.0.0")
_PORT = int(os.environ["HLF_PORT"]) if os.environ.get("HLF_PORT") else 0

mcp = FastMCP(
    name="HLF Hieroglyphic Logic Framework",
    instructions="HLF MCP server loading...",
    host=_HOST,
    port=_PORT,
)

# ── Module-level singletons ────────────────────────────────────────────────────

_ctx = build_server_context()
compiler = _ctx.compiler
formatter = _ctx.formatter
linter = _ctx.linter
_runtime = _ctx.runtime
bytecoder = _ctx.bytecoder
_benchmark = _ctx.benchmark
memory_store = _ctx.memory_store
instinct_mgr = _ctx.instinct_mgr
host_registry = _ctx.host_registry
tool_registry = _ctx.tool_registry

# ── Governance manifest integrity check ───────────────────────────────────────

check_governance_manifest(_log)

# Internal aliases kept for backward-compat with any imports referencing old names
_compiler = compiler
_formatter = formatter
_linter = linter
_bytecode = bytecoder
_memory = memory_store
_instinct = instinct_mgr


# ── Tools ──────────────────────────────────────────────────────────────────────
REGISTERED_TOOLS: dict[str, Any] = {}
REGISTERED_TOOLS.update(register_core_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_translation_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_memory_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_profile_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_instinct_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_verifier_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_capsule_tools(mcp, _ctx))
REGISTERED_TOOLS.update(register_completion_tools(mcp, _ctx))


@mcp.tool()
def hlf_entropy_anchor(
    source: str,
    expected_intent: str = "",
    threshold: float = 0.5,
    policy_mode: str = "advisory",
    subject_agent_id: str = "",
) -> dict[str, Any]:
    """Evaluate semantic drift between packaged HLF meaning and an operator-readable intent baseline."""
    try:
        result = _ctx.compiler.compile(source)
        anchor = evaluate_entropy_anchor(
            source=source,
            ast=result["ast"],
            expected_intent=expected_intent,
            threshold=threshold,
            policy_mode=policy_mode,
        )
        audit = _ctx.audit_chain.log(
            "entropy_anchor_evaluated",
            anchor.audit_payload(),
            anomaly_score=1.0 if anchor.drift_detected else 0.0,
        )
        governance_event = _ctx.emit_governance_event(
            kind="entropy_anchor",
            source="server.hlf_entropy_anchor",
            action="evaluate_entropy_anchor",
            status="warning" if anchor.drift_detected else "ok",
            severity="warning" if anchor.drift_detected else "info",
            subject_id=anchor.source_hash,
            details={
                "policy_mode": anchor.policy_mode,
                "policy_action": anchor.policy_action,
                "drift_detected": anchor.drift_detected,
                "similarity_score": anchor.similarity_score,
                "threshold": anchor.threshold,
                "baseline_source": anchor.baseline_source,
                "audit_trace_id": audit.get("trace_id"),
            },
            agent_role="entropy_anchor",
            anomaly_score=1.0 if anchor.drift_detected else 0.0,
            related_refs=[
                {
                    "kind": "audit",
                    "event_id": str(audit.get("trace_id", "")),
                    "trace_id": str(audit.get("trace_id", "")),
                }
            ],
        )
        witness_observation = None
        normalized_subject_agent_id = str(subject_agent_id or "").strip()
        if normalized_subject_agent_id and anchor.drift_detected:
            witness_observation = _ctx.record_witness_observation(
                subject_agent_id=normalized_subject_agent_id,
                category="entropy_drift",
                witness_id="entropy-anchor",
                severity="critical" if anchor.policy_action == "halt_branch" else "warning",
                confidence=min(1.0, max(0.75, anchor.similarity_score + 0.35)),
                source="server.hlf_entropy_anchor",
                event_ref=governance_event.get("event_ref"),
                evidence_text=(
                    f"Entropy-anchor drift detected with policy action '{anchor.policy_action}' "
                    f"at similarity {anchor.similarity_score:.3f} against threshold {anchor.threshold:.3f}."
                ),
                recommended_action=(
                    "restrict"
                    if anchor.policy_action == "halt_branch"
                    else "probation"
                    if anchor.policy_action == "escalate_hitl"
                    else "review"
                ),
                details={
                    "policy_mode": anchor.policy_mode,
                    "policy_action": anchor.policy_action,
                    "source_hash": anchor.source_hash,
                    "baseline_source": anchor.baseline_source,
                    "similarity_score": anchor.similarity_score,
                    "threshold": anchor.threshold,
                },
            )
        return {
            "status": "ok",
            "anchor": anchor.to_dict(),
            "audit": audit,
            "governance_event": governance_event,
            "subject_agent_id": normalized_subject_agent_id,
            "witness_observation": witness_observation,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


REGISTERED_TOOLS["hlf_entropy_anchor"] = hlf_entropy_anchor
globals().update(REGISTERED_TOOLS)


REGISTERED_RESOURCES = register_resources(mcp, _ctx)
_generated_instructions = build_server_instructions(REGISTERED_TOOLS, REGISTERED_RESOURCES)
# FastMCP exposes instructions as a read-only property; the wrapped low-level
# MCP server owns the writable field that initialize responses actually use.
mcp._mcp_server.instructions = _generated_instructions


# ── Health endpoint (HTTP transports only) ────────────────────────────────────


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_endpoint(request: Any) -> Any:
    """Expose a plain HTTP liveness probe without bypassing FastMCP lifespan handling."""
    from starlette.responses import JSONResponse

    return JSONResponse(
        {
            "status": "ok",
            "transport": os.environ.get("HLF_TRANSPORT", "stdio"),
        }
    )


def _get_http_bind() -> tuple[str, int]:
    """Resolve the explicit host/port bind for HTTP transports."""
    host = os.environ.get("HLF_HOST", "0.0.0.0")
    raw_port = os.environ.get("HLF_PORT")
    if raw_port is None or not raw_port.strip():
        raise RuntimeError(
            "HLF_PORT must be set explicitly when HLF_TRANSPORT uses an HTTP transport"
        )
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError(f"HLF_PORT must be an integer, got {raw_port!r}") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"HLF_PORT must be between 1 and 65535, got {port}")
    return host, port


# ── Entry point ────────────────────────────────────────────────────────────────


def _startup_self_index() -> None:
    """Ingest HLF docs and governance markdown into the governed knowledge substrate.

    Runs once at server startup.  Deduplication in the memory substrate makes
    subsequent startups fast—only new or modified chunks are stored.
    """
    try:
        ingester = DocumentIngester(_ctx.memory_store)
        reports: list = []

        # Canonical HLF documentation
        docs_dir = _REPO_ROOT / "docs"
        if docs_dir.is_dir():
            reports.extend(
                ingester.ingest_directory(
                    docs_dir,
                    domain="hlf-specific",
                    source_authority_label="canonical",
                    file_pattern="*.md",
                    recursive=True,
                )
            )

        # Root-level markdown (README, SSOT, vision doctrine, etc.)
        reports.extend(
            ingester.ingest_directory(
                _REPO_ROOT,
                domain="hlf-specific",
                source_authority_label="canonical",
                file_pattern="*.md",
                recursive=False,
            )
        )

        # Governance assets
        governance_dir = _REPO_ROOT / "governance"
        if governance_dir.is_dir():
            reports.extend(
                ingester.ingest_directory(
                    governance_dir,
                    domain="hlf-specific",
                    source_authority_label="canonical",
                    file_pattern="*.md",
                    recursive=True,
                )
            )

        summary = summarize_reports(reports)
        _log.info(
            "HLK startup self-index: %d stored, %d deduped, %d errors, %d files, %.2fs",
            summary["stored"],
            summary["deduped"],
            summary["errors"],
            summary["files_processed"],
            summary["elapsed_seconds"],
        )
    except Exception:
        _log.exception("HLK startup self-index failed — server will start without self-index")


def main() -> None:
    """Start the HLF MCP server with the configured transport."""
    _db_path = _ctx.memory_store._db_path  # type: ignore[attr-defined]
    if _db_path == ":memory:":
        _log.warning(
            "RAGMemory is using ':memory:' — knowledge will NOT persist across restarts. "
            "Set HLF_MEMORY_DB=<path> or ensure db/hlf_memory.db is writable."
        )
    else:
        _log.info("RAGMemory persistent DB: %s", _db_path)
    _startup_self_index()
    transport = os.environ.get("HLF_TRANSPORT", "stdio").lower().strip()

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport in ("sse", "http"):
        host, port = _get_http_bind()
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")
    elif transport == "streamable-http":
        host, port = _get_http_bind()
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        print(
            f"Unknown transport: {transport!r}. Use: stdio, sse, streamable-http", file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
