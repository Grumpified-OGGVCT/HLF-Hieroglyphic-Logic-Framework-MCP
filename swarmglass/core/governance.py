"""SwarmGlass governance primitives — zero DSL/VM/compiler dependency.

All imports use importlib to load modules directly, bypassing
hlf_mcp/__init__.py and hlf_mcp/hlf/__init__.py entirely.
This means ZERO DSL modules enter sys.modules.
"""

from __future__ import annotations

import importlib
from typing import Any


def _load(mod_path: str, attr: str) -> Any:
    """Import a single attribute from an hlf_mcp submodule without 
    triggering package __init__.py files."""
    return getattr(importlib.import_module(mod_path), attr)


# ── Audit ────────────────────────────────────────────────────────────
AuditChain = lambda: _load("hlf_mcp.hlf.audit_chain", "AuditChain")
ApprovalLedger = lambda: _load("hlf_mcp.hlf.approval_ledger", "ApprovalLedger")

# ── Validation ──────────────────────────────────────────────────────
AlignGovernor = lambda: _load("hlf_mcp.hlf.align_governor", "AlignGovernor")
WitnessGovernance = lambda: _load("hlf_mcp.hlf.witness_governance", "WitnessGovernance")
GovernedIngressController = lambda: _load("hlf_mcp.hlf.governed_ingress", "GovernedIngressController")
IntentNormalizer = lambda: _load("hlf_mcp.hlf.intent_normalizer", "IntentNormalizer")

# ── Memory ──────────────────────────────────────────────────────────
# RAGMemory is in hlf_mcp.rag.memory — safe path, no DSL dependency
RAGMemory = lambda: _load("hlf_mcp.rag.memory", "RAGMemory")

# ── Registry ───────────────────────────────────────────────────────
HostFunctionRegistry = lambda: _load("hlf_mcp.hlf.registry", "HostFunctionRegistry")
ToolRegistry = lambda: _load("hlf_mcp.hlf.tool_dispatch", "ToolRegistry")

# ── Governance helpers ──────────────────────────────────────────────
build_governance_proof = lambda: _load("hlf_mcp.hlf.governance_proofs", "build_governance_proof")
sha256_digest = lambda: _load("hlf_mcp.hlf.governance_proofs", "sha256_digest")
DaemonManager = lambda: _load("hlf_mcp.hlf.daemon_manager", "DaemonManager")


# ── Eager accessors (call once and cache) ──────────────────────────

_CACHE: dict[str, Any] = {}

def _cached(mod_path: str, attr: str) -> Any:
    key = f"{mod_path}.{attr}"
    if key not in _CACHE:
        _CACHE[key] = _load(mod_path, attr)
    return _CACHE[key]


class GovernanceContext:
    """A minimal governance context with zero DSL dependency."""
    
    def __init__(self):
        self.audit_chain = _cached("hlf_mcp.hlf.audit_chain", "AuditChain")()
        self.approval_ledger = _cached("hlf_mcp.hlf.approval_ledger", "ApprovalLedger")()
        self.align_governor = _cached("hlf_mcp.hlf.align_governor", "AlignGovernor")()
        self.witness = _cached("hlf_mcp.hlf.witness_governance", "WitnessGovernance")()
        self.ingress = _cached("hlf_mcp.hlf.governed_ingress", "GovernedIngressController")(
            align_governor=self.align_governor
        )
        self.daemon = _cached("hlf_mcp.hlf.daemon_manager", "DaemonManager")()
        self.normalizer = _cached("hlf_mcp.hlf.intent_normalizer", "IntentNormalizer")()


__all__ = [
    "GovernanceContext",
    "AuditChain",
    "ApprovalLedger",
    "AlignGovernor",
    "WitnessGovernance",
    "GovernedIngressController",
    "IntentNormalizer",
    "RAGMemory",
    "HostFunctionRegistry",
    "ToolRegistry",
    "build_governance_proof",
    "sha256_digest",
    "DaemonManager",
]
