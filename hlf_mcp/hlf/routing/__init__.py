"""
HLF MCP — Distributed Routing Subpackage.

Multi-node distributed routing fabric that complements the existing
model-level routing in ``hlf_mcp.hlf.routing`` (the module, not this
package).  Provides node discovery, capability-based routing, load
balancing, and automatic failover.

This package:
  - Registers distributed nodes with capability declarations
  - Routes work to the best-fitting node based on capabilities
  - Balances load with round-robin or least-loaded strategies
  - Handles node failures with automatic re-routing

Usage::

    from hlf_mcp.hlf.routing import (
        NodeRegistry,
        CapabilityRouter,
        LoadBalancer,
        FailoverManager,
        WorkRequest,
        RouteMatch,
        RegisteredNode,
        NodeFailureEvent,
    )

    registry = NodeRegistry()
    registry.register("node-1", "10.0.0.1", 9090,
                      capabilities={"inference": 8, "embedding": 5})

    router = CapabilityRouter(registry)
    lb = LoadBalancer(registry, router, strategy="round_robin")
    failover = FailoverManager(registry, router, lb, max_retries=3)

    request = WorkRequest(request_id="req-1", capability="inference",
                          required_proficiency=5)
    match = lb.distribute(request)
    if match.matched:
        print(f"Routed to {match.matched_node.node_id}")

The original model-level routing module is available via the fully-qualified
attribute ``_routing_module`` on this package, or via explicit import::

    from hlf_mcp.hlf.routing import route_request  # proxied
"""

from __future__ import annotations

from hlf_mcp.hlf.routing.node_registry import NodeRegistry, RegisteredNode
from hlf_mcp.hlf.routing.capability_router import (
    CapabilityRouter,
    RouteMatch,
    WorkRequest,
)
from hlf_mcp.hlf.routing.load_balancer import LoadBalancer
from hlf_mcp.hlf.routing.failover import (
    FailoverManager,
    NodeFailureEvent,
)

# ── Proxy the original module-level routing API ─────────────────────────
# Python resolves packages before same-named modules.  We still need the
# original routing.py to be reachable.  Load it under a distinct name via
# SourceFileLoader so that both coexist.
import importlib.machinery
import importlib.util
import os
import sys

_routing_py_path = os.path.join(os.path.dirname(__file__), "..", "routing.py")
_routing_mod_name = "hlf_mcp.hlf._distributed_routing_original"
_loader = importlib.machinery.SourceFileLoader(
    _routing_mod_name, str(_routing_py_path)
)
_spec = importlib.util.spec_from_loader(_routing_mod_name, _loader)
if _spec is not None:
    _routing_original = importlib.util.module_from_spec(_spec)
    sys.modules[_routing_mod_name] = _routing_original
    _loader.exec_module(_routing_original)

    # Re-export the key public names into this package's namespace
    for _name in (
        "_SPECIALIZATION_PATTERNS",
        "_TIER_WALK_ORDER",
        "RouteProfile",
        "route_request",
        "route_with_fallback",
        "route_intent",
        "select_model_by_tier",
        "complexity_score",
        "check_vram_threshold",
        "is_model_allowed",
        "require_evidence_gate",
    ):
        _obj = getattr(_routing_original, _name, None)
        if _obj is not None:
            globals()[_name] = _obj


__all__ = [
    # Subpackage (distributed routing)
    "NodeRegistry",
    "RegisteredNode",
    "CapabilityRouter",
    "RouteMatch",
    "WorkRequest",
    "LoadBalancer",
    "FailoverManager",
    "NodeFailureEvent",
    # Re-exported from original module (model-level routing)
    "RouteProfile",
    "route_request",
    "route_with_fallback",
    "route_intent",
    "select_model_by_tier",
    "complexity_score",
    "check_vram_threshold",
    "is_model_allowed",
    "require_evidence_gate",
]
