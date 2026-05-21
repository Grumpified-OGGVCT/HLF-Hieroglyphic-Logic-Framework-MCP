"""
HLF Ecosystem Integration Bridge

Claim lane: bridge_contract

This package holds ecosystem bridge contracts, language-SDK adapters,
transport compatibility documentation, and production hardening components
for non-Python HLF consumers.

Current truth:
- The HLF MCP server (Python/FastMCP) is the only executable surface.
- The VS Code extension (extensions/hlf-vscode/) contains a working
  JavaScript StreamableHttpMcpClient.
- The AgentKB_MCP donor (donor/AgentKB_MCP/) contains a TypeScript
  MCP server reference pattern.

No SDK stubs for Java, Go, or Rust exist yet. This package documents
the bridge path and will hold SDK adapters as they are built.

Hardening components (production):
- rate_limiter: TokenBucket rate limiter with per-effect + global scoping
- circuit_breaker: CircuitBreaker with CLOSED/OPEN/HALF_OPEN states
- retry_policy: RetryPolicy with exponential backoff + jitter
- credential_manager: CredentialManager with scoped API keys + rotation

Integration depth hardening (ecosystem):
- schema_translator: SchemaTranslator — HLF contracts → JSON Schema / OpenAPI
- distributed_rate_limiter: DistributedRateLimiter — multi-instance coordination
- resilience_coordinator: ResilienceCoordinator — unified resilience cascade
- bridge_health: BridgeHealthAggregator — aggregated health + alerts
"""

# ── Bridge exports ────────────────────────────────────────────────────────────

from hlf_mcp.ecosystem.mcp_bridge import (
    MCPBridge,
    MCPToolRegistration,
    register_manifest_as_mcp_tools,
    manifest_to_mcp_tool_schemas,
)

from hlf_mcp.ecosystem.rest_bridge import (
    RESTBridge,
    RESTEndpoint,
    generate_openapi_from_manifests,
    generate_openapi_json_from_manifests,
)

# ── Hardening exports ─────────────────────────────────────────────────────────

from hlf_mcp.ecosystem.rate_limiter import (
    TokenBucket,
    RateLimiter,
)

from hlf_mcp.ecosystem.circuit_breaker import (
    CircuitState,
    CircuitOpenError,
    CircuitBreaker,
)

from hlf_mcp.ecosystem.retry_policy import (
    RetryDecision,
    RetryPolicy,
    READ_RETRY_POLICY,
    WRITE_RETRY_POLICY,
    DEFAULT_RETRY_POLICY,
    retry_policy_for_effect,
)

from hlf_mcp.ecosystem.credential_manager import (
    CredentialScope,
    Credential,
    CredentialManager,
)

# ── Integration depth hardening exports ───────────────────────────────────────

from hlf_mcp.ecosystem.schema_translator import (
    SchemaFormat,
    SchemaTranslationResult,
    SchemaTranslator,
)

from hlf_mcp.ecosystem.distributed_rate_limiter import (
    CoordinationMode,
    RateLimitState,
    DistributedRateLimiter,
)

from hlf_mcp.ecosystem.resilience_coordinator import (
    ResilienceAction,
    ResilienceEvent,
    ResiliencePolicy,
    ResilienceCoordinator,
)

from hlf_mcp.ecosystem.bridge_health import (
    HealthStatus,
    BridgeHealth,
    HealthAggregation,
    BridgeHealthAggregator,
)

# ── Compatibility matrix exports ───────────────────────────────────────────────

from hlf_mcp.ecosystem.compatibility_matrix import (
    CompatibilityMatrixEntry,
    CompatibilityMatrix,
)

# ── Watch workflow export ──────────────────────────────────────────────────────

from hlf_mcp.ecosystem.watch_workflow import (
    run_once as watch_workflow_run_once,
    run_watch as watch_workflow_run_watch,
    main as watch_workflow_main,
)

__all__ = [
    # Bridges
    "MCPBridge",
    "MCPToolRegistration",
    "register_manifest_as_mcp_tools",
    "manifest_to_mcp_tool_schemas",
    "RESTBridge",
    "RESTEndpoint",
    "generate_openapi_from_manifests",
    "generate_openapi_json_from_manifests",
    # Rate limiting
    "TokenBucket",
    "RateLimiter",
    # Circuit breaking
    "CircuitState",
    "CircuitOpenError",
    "CircuitBreaker",
    # Retry policies
    "RetryDecision",
    "RetryPolicy",
    "READ_RETRY_POLICY",
    "WRITE_RETRY_POLICY",
    "DEFAULT_RETRY_POLICY",
    "retry_policy_for_effect",
    # Credential management
    "CredentialScope",
    "Credential",
    "CredentialManager",
    # Schema translation
    "SchemaFormat",
    "SchemaTranslationResult",
    "SchemaTranslator",
    # Distributed rate limiting
    "CoordinationMode",
    "RateLimitState",
    "DistributedRateLimiter",
    # Resilience coordination
    "ResilienceAction",
    "ResilienceEvent",
    "ResiliencePolicy",
    "ResilienceCoordinator",
    # Bridge health aggregation
    "HealthStatus",
    "BridgeHealth",
    "HealthAggregation",
    "BridgeHealthAggregator",
    # Compatibility matrix
    "CompatibilityMatrixEntry",
    "CompatibilityMatrix",
    # Watch workflow
    "watch_workflow_run_once",
    "watch_workflow_run_watch",
    "watch_workflow_main",
]
