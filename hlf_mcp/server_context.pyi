"""
Type stubs for hlf_mcp.server_context.ServerContext.

IDE support: marks DSL-dependent fields as Optional because they are
None in governance-only mode (SWARMGLASS_EXPERIMENTAL=0).
"""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Optional

# Governance fields — always available in both EXP=0 and EXP=1
from hlf_mcp.hlf.audit_chain import AuditChain
from hlf_mcp.hlf.align_governor import AlignGovernor
from hlf_mcp.hlf.witness_governance import WitnessGovernance
from hlf_mcp.hlf.intent_normalizer import IntentNormalizer
from hlf_mcp.hlf.memory_store import MemoryStore  # type: ignore[import]

# DSL fields — Optional, None in EXP=0 governance-only mode
if TYPE_CHECKING:
    from hlf_mcp.hlf.compiler import HLFCompiler  # type: ignore[import]
    from hlf_mcp.hlf.runtime import HLFRuntime  # type: ignore[import]
    from hlf_mcp.hlf.bytecode import HLFBytecode  # type: ignore[import]
    from hlf_mcp.hlf.formal_verifier import FormalVerifier  # type: ignore[import]
    from hlf_mcp.hlf.formatter import HLFFormatter  # type: ignore[import]
    from hlf_mcp.hlf.linter import HLFLinter  # type: ignore[import]
    from hlf_mcp.hlf.translator import (  # type: ignore[import]
        TranslationContract,
        TranslationRepairPlan,
    )


class ServerContext:
    """Governance + DSL server context.

    In governance-only mode (SWARMGLASS_EXPERIMENTAL=0), DSL fields are None.
    Use ``if ctx.compiler is not None:`` guards before accessing DSL methods.
    """

    # ── Governance (always available) ──────────────────────────────
    align_governor: AlignGovernor
    audit_chain: AuditChain
    witness_governance: WitnessGovernance
    intent_normalizer: IntentNormalizer
    memory_store: MemoryStore
    daemon_manager: Any
    handoff_events: deque[dict[str, Any]]

    # ── DSL (Optional — None in EXP=0) ─────────────────────────────
    compiler: Optional[HLFCompiler]
    runtime: Optional[HLFRuntime]
    formal_verifier: Optional[FormalVerifier]
    bytecoder: Optional[HLFBytecode]
    formatter: Optional[HLFFormatter]
    linter: Optional[HLFLinter]

    # ── Governance methods (always available) ──────────────────────
    def persist_handoff_event(self, event: dict[str, Any]) -> dict[str, Any]: ...
    def get_handoff_chain(self, event_hash: Optional[str] = None) -> Optional[dict[str, Any]]: ...
    def persist_governed_route(self, route_trace: dict[str, Any]) -> dict[str, Any]: ...
    def get_governed_route(self, *, agent_id: Optional[str] = None) -> Optional[dict[str, Any]]: ...
    def get_governed_recall(self, *, recall_id: Optional[str] = None) -> Optional[dict[str, Any]]: ...
    def resolve_memory_pointer(self, pointer: str, **kwargs: Any) -> dict[str, Any]: ...


def build_server_context() -> ServerContext:
    """Build a ServerContext. DSL fields are None when SWARMGLASS_EXPERIMENTAL=0."""
    ...
