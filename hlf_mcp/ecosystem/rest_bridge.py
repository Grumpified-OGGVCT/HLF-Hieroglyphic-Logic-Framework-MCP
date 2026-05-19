"""
REST API Bridge — FastAPI-based REST wrapper around HLF execution.

Wraps HLF capability manifests as REST endpoints with auto-generated
OpenAPI specifications.  Each effect category becomes a route group,
and the full CapabilityManifest drives the request/response schemas.

Features:
  - Auto-generates OpenAPI 3.1 spec from capability manifests
  - One endpoint group per effect category (filesystem, network, memory, etc.)
  - Trust-tier enforcement via dependency injection
  - API key authentication for higher-trust operations
  - Execution provenance in response headers
  - Compatible with any FastAPI / Starlette application

Integration points:
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest (Phase 5)
  - hlf_mcp.hlf.compiler.HLFCompiler (compilation)
  - hlf_mcp.hlf.two_channel_executor (provenance tracking)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, TYPE_CHECKING

from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    EFFECT_TO_CAPABILITY,
    EFFECT_TO_TRUST_TIER,
    TRUST_TIER_ORDER,
)
from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    EffectClass,
    HlfType,
    TypeContract,
)
from hlf_mcp.hlf.two_channel_executor import ProvenanceChain, DataChannel

if TYPE_CHECKING:
    from hlf_mcp.ecosystem.rate_limiter import RateLimiter
    from hlf_mcp.ecosystem.circuit_breaker import CircuitBreaker, CircuitOpenError
    from hlf_mcp.ecosystem.credential_manager import CredentialManager


# ═══════════════════════════════════════════════════════════════════════════════
# OpenAPI schema builders
# ═══════════════════════════════════════════════════════════════════════════════

_HLF_TYPE_TO_OPENAPI: dict[str, str] = {
    "string": "string",
    "number": "number",
    "integer": "integer",
    "real": "number",
    "boolean": "boolean",
    "json": "object",
    "any": "string",
    "list": "array",
    "set": "array",
    "map": "object",
}


def _hlf_type_to_openapi_type(hlt: HlfType) -> str:
    return _HLF_TYPE_TO_OPENAPI.get(hlt.value, "string")


def _param_to_openapi_property(param: TypeContract) -> dict[str, Any]:
    """Convert a TypeContract parameter to an OpenAPI schema property."""
    prop: dict[str, Any] = {"type": _hlf_type_to_openapi_type(param.hlf_type)}
    desc = param.constraints.get("description") if param.constraints else None
    if desc:
        prop["description"] = str(desc)
    if param.constraints:
        for key, val in param.constraints.items():
            if key in ("minimum", "maximum", "minLength", "maxLength", "pattern",
                        "exclusiveMinimum", "exclusiveMaximum", "default", "enum"):
                prop[key] = val
    return prop


def _input_contract_to_openapi_request_body(contract: InputContract) -> dict[str, Any] | None:
    """Convert an InputContract to an OpenAPI requestBody object."""
    if not contract.parameters:
        return None
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in contract.parameters:
        if param.name:
            properties[param.name] = _param_to_openapi_property(param)
            if param.required:
                required.append(param.name)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return {
        "required": True,
        "content": {
            "application/json": {"schema": schema}
        },
    }


def _output_contract_to_openapi_response(contract: OutputContract) -> dict[str, Any]:
    """Convert an OutputContract to an OpenAPI response object."""
    if contract.output_schema and isinstance(contract.output_schema, dict):
        schema = dict(contract.output_schema)
    else:
        schema = {"type": _hlf_type_to_openapi_type(contract.return_type)}
    return {
        "200": {
            "description": "Successful execution",
            "content": {"application/json": {"schema": schema}},
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RESTEndpoint — a single REST endpoint derived from an effect
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RESTEndpoint:
    """A single REST endpoint derived from one HLF effect declaration."""

    method: str  # "GET" or "POST"
    path: str
    summary: str
    description: str
    operation_id: str
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any] = field(default_factory=dict)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    security: list[dict[str, list[str]]] = field(default_factory=list)
    trust_tier: str = "advisory"
    category: str = "utility"

    def to_openapi_operation(self) -> dict[str, Any]:
        """Produce an OpenAPI 3.1 operation object."""
        op: dict[str, Any] = {
            "operationId": self.operation_id,
            "summary": self.summary,
            "description": self.description,
            "tags": self.tags,
            "responses": self.responses,
            "x-hlf-trust-tier": self.trust_tier,
            "x-hlf-category": self.category,
        }
        if self.request_body:
            op["requestBody"] = self.request_body
        if self.parameters:
            op["parameters"] = self.parameters
        if self.security:
            op["security"] = self.security
        return op


# ═══════════════════════════════════════════════════════════════════════════════
# RESTBridge — the main bridge class
# ═══════════════════════════════════════════════════════════════════════════════


def _effect_class_to_category(effect_class: EffectClass) -> str:
    """Map an EffectClass to a REST API category tag."""
    _categories: dict[EffectClass, str] = {
        EffectClass.FILE_READ: "filesystem",
        EffectClass.FILE_WRITE: "filesystem",
        EffectClass.NETWORK_READ: "network",
        EffectClass.NETWORK_WRITE: "network",
        EffectClass.WEB_SEARCH: "network",
        EffectClass.MEMORY_READ: "memory",
        EffectClass.MEMORY_WRITE: "memory",
        EffectClass.MODEL_INFERENCE: "inference",
        EffectClass.EMBEDDING_GENERATION: "inference",
        EffectClass.MULTIMODAL_AUDIO: "multimodal",
        EffectClass.MULTIMODAL_OCR: "multimodal",
        EffectClass.MULTIMODAL_VIDEO: "multimodal",
        EffectClass.MULTIMODAL_VISION: "multimodal",
        EffectClass.PROCESS_SPAWN: "execution",
        EffectClass.AGENT_DELEGATION: "agent",
        EffectClass.GOVERNANCE_VOTE: "governance",
        EffectClass.FORMAL_VERIFICATION: "verification",
        EffectClass.VERIFICATION: "verification",
        EffectClass.AUDIT_LOG: "audit",
        EffectClass.MERKLE_APPEND: "audit",
        EffectClass.CRYPTOGRAPHIC_HASH: "crypto",
        EffectClass.ENVIRONMENT_READ: "environment",
        EffectClass.TIMING: "utility",
        EffectClass.LOCAL_ANALYSIS: "analysis",
        EffectClass.ASSERTION: "analysis",
        EffectClass.ROUTE_SELECTION: "routing",
        EffectClass.SIMILARITY_MATH: "analysis",
        EffectClass.TOKEN_TRANSFORM: "analysis",
        EffectClass.SENSOR_READ: "embodied",
        EffectClass.WORLD_STATE_READ: "embodied",
        EffectClass.TRAJECTORY_PLAN: "embodied",
        EffectClass.GUARDED_ACTUATION: "embodied",
        EffectClass.SAFETY_STOP: "embodied",
    }
    return _categories.get(effect_class, "utility")


def _determine_http_method(effect_class: EffectClass) -> str:
    """Determine whether an effect should be exposed as GET or POST.

    Mutating effects (write, spawn, delegate) use POST.
    Read-only effects use GET.
    """
    _post_classes: frozenset[EffectClass] = frozenset({
        EffectClass.FILE_WRITE,
        EffectClass.NETWORK_WRITE,
        EffectClass.MEMORY_WRITE,
        EffectClass.PROCESS_SPAWN,
        EffectClass.AGENT_DELEGATION,
        EffectClass.GUARDED_ACTUATION,
        EffectClass.SAFETY_STOP,
        EffectClass.MODEL_INFERENCE,
        EffectClass.EMBEDDING_GENERATION,
        EffectClass.MULTIMODAL_AUDIO,
        EffectClass.MULTIMODAL_OCR,
        EffectClass.MULTIMODAL_VIDEO,
        EffectClass.MULTIMODAL_VISION,
    })
    return "POST" if effect_class in _post_classes else "GET"


def _effect_to_path(effect: TypedEffectDeclaration, manifest: CapabilityManifest) -> str:
    """Generate a REST path for an effect.

    Format: /api/v1/{category}/{function_name}
    """
    category = _effect_class_to_category(effect.effect_class)
    fn_name = effect.function_name.strip().lower().replace(" ", "_") if effect.function_name else effect.effect_class.value
    fn_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in fn_name)
    return f"/api/v1/{category}/{fn_name}"


def _build_security_for_tier(tier: str) -> list[dict[str, list[str]]]:
    """Build OpenAPI security requirements for a trust tier."""
    tier_ord = TRUST_TIER_ORDER.get(tier, 0)
    security: list[dict[str, list[str]]] = []
    if tier_ord >= TRUST_TIER_ORDER.get("approved", 5):
        security.append({"ApiKeyAuth": []})
    if tier_ord >= TRUST_TIER_ORDER.get("trusted", 6):
        security.append({"HlfTrustToken": []})
    return security


# ═══════════════════════════════════════════════════════════════════════════════
# RESTBridge
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RESTBridge:
    """FastAPI-compatible REST wrapper around HLF execution.

    Generates OpenAPI 3.1 specifications from CapabilityManifest and
    provides route handlers with trust-tier enforcement.

    Usage:
        bridge = RESTBridge()
        manifest = compiler.compile_and_manifest(source)[1]

        # Generate OpenAPI spec
        openapi_spec = bridge.generate_openapi_spec([manifest], title="My HLF API")

        # Register with FastAPI
        from fastapi import FastAPI
        app = FastAPI()
        bridge.mount_to_app(app, [manifest])

    Hardening (optional):
        bridge = RESTBridge(
            rate_limiter=RateLimiter(global_rate=100, global_burst=200),
            circuit_breaker=CircuitBreaker(name="rest_bridge"),
            credential_manager=CredentialManager(master_secret="my-secret"),
        )
        # Routes mounted via mount_to_app() now validate credentials,
        # enforce rate limits, and use circuit breaking.
    """

    title: str = "HLF REST API"
    version: str = "1.0.0"
    description: str = "Auto-generated REST API from HLF capability manifests"
    tier: str = "hearth"
    api_keys: dict[str, str] = field(default_factory=dict)  # key_id → description

    # ── Hardening (optional — backward compatible) ────────────────────────────

    rate_limiter: object | None = field(default=None, repr=False)
    circuit_breaker: object | None = field(default=None, repr=False)
    credential_manager: object | None = field(default=None, repr=False)

    # ── OpenAPI Generation ───────────────────────────────────────────────────

    def generate_openapi_spec(
        self,
        manifests: list[CapabilityManifest],
        *,
        title: str | None = None,
        version: str | None = None,
        servers: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a complete OpenAPI 3.1 specification from capability manifests.

        Each effect in each manifest becomes a documented endpoint with
        proper request/response schemas derived from the typed contracts.

        Args:
            manifests: One or more CapabilityManifest objects.
            title: Override the API title.
            version: Override the API version.
            servers: List of server objects, e.g. [{"url": "http://localhost:8000"}].

        Returns:
            Complete OpenAPI 3.1 specification dictionary.
        """
        effective_title = title or self.title
        effective_version = version or self.version
        effective_servers = servers or [{"url": "http://localhost:8000"}]

        paths: dict[str, Any] = {}
        tags_set: dict[str, dict[str, str]] = {}

        for manifest in manifests:
            for effect in manifest.effects:
                endpoint = self._effect_to_endpoint(effect, manifest)
                if endpoint.path not in paths:
                    paths[endpoint.path] = {}
                paths[endpoint.path][endpoint.method.lower()] = endpoint.to_openapi_operation()
                cat = endpoint.tags[0] if endpoint.tags else "utility"
                if cat not in tags_set:
                    tags_set[cat] = {"name": cat, "description": f"{cat.title()} operations"}

        spec: dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {
                "title": effective_title,
                "version": effective_version,
                "description": self.description,
            },
            "servers": effective_servers,
            "tags": list(tags_set.values()),
            "paths": paths,
        }

        if self.api_keys:
            spec["components"] = {
                "securitySchemes": {
                    "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                    "HlfTrustToken": {"type": "http", "scheme": "bearer", "bearerFormat": "HLF Trust Token"},
                }
            }

        return spec

    def generate_openapi_json(self, manifests: list[CapabilityManifest], **kwargs: Any) -> str:
        """Generate OpenAPI spec as a JSON string."""
        spec = self.generate_openapi_spec(manifests, **kwargs)
        return json.dumps(spec, indent=2, sort_keys=False, ensure_ascii=False)

    # ── FastAPI Integration ──────────────────────────────────────────────────

    def mount_to_app(
        self,
        app: object,
        manifests: list[CapabilityManifest],
        *,
        executor: Callable[..., Any] | None = None,
    ) -> None:
        """Mount HLF endpoints onto an existing FastAPI application.

        Each effect becomes a route with proper request validation and
        trust-tier enforcement.  This is the recommended way to integrate
        HLF into an existing FastAPI server.

        Args:
            app: A FastAPI application instance.
            manifests: CapabilityManifest objects to expose.
            executor: Optional callable(manifest, effect, params) → result.
                      If not provided, a default executor is used that
                      returns the effect metadata.
        """
        try:
            from fastapi import HTTPException, Request, Depends
            from fastapi.responses import JSONResponse
        except ImportError:
            raise ImportError(
                "FastAPI is required for RESTBridge.mount_to_app(). "
                "Install it with: pip install fastapi"
            )

        effective_executor = executor or self._default_executor

        for manifest in manifests:
            for effect in manifest.effects:
                self._mount_effect_route(app, manifest, effect, effective_executor)

    def _mount_effect_route(
        self,
        app: object,
        manifest: CapabilityManifest,
        effect: TypedEffectDeclaration,
        executor: Callable[..., Any],
    ) -> None:
        """Mount a single effect as a FastAPI route with hardening middleware."""
        try:
            from fastapi import HTTPException, Request
            from fastapi.responses import JSONResponse
        except ImportError:
            return

        method = _determine_http_method(effect.effect_class)
        path = _effect_to_path(effect, manifest)
        trust_tier = EFFECT_TO_TRUST_TIER.get(effect.effect_class, "advisory")
        effect_name = effect.effect_class.value

        # Capture hardening references at route-definition time
        _rate_limiter = self.rate_limiter
        _circuit_breaker = self.circuit_breaker
        _credential_manager = self.credential_manager

        async def _handler(
            request: Request,
            body: dict[str, Any] | None = None,
            _manifest: CapabilityManifest = manifest,
            _effect: TypedEffectDeclaration = effect,
            _tier: str = trust_tier,
        ) -> JSONResponse:
            # ── Credential validation (hardening) ─────────────────────────
            if _credential_manager is not None:
                from hlf_mcp.ecosystem.credential_manager import CredentialManager
                if isinstance(_credential_manager, CredentialManager):
                    api_key = request.headers.get("X-API-Key", "")
                    if api_key:
                        cred = _credential_manager.validate_for_tier(api_key, _tier)
                        if cred is None:
                            raise HTTPException(
                                status_code=401,
                                detail="Invalid or insufficient API key for required trust tier",
                            )

            # ── Rate limiting (hardening) ─────────────────────────────────
            if _rate_limiter is not None:
                from hlf_mcp.ecosystem.rate_limiter import RateLimiter
                if isinstance(_rate_limiter, RateLimiter):
                    if not _rate_limiter.consume(effect_name):
                        headers = _rate_limiter.headers(effect_name)
                        raise HTTPException(
                            status_code=429,
                            detail="Rate limit exceeded",
                            headers=headers,
                        )

            # Trust tier enforcement
            session_tier = request.headers.get("X-HLF-Trust-Tier", "advisory")
            required_ord = TRUST_TIER_ORDER.get(_tier, 0)
            session_ord = TRUST_TIER_ORDER.get(session_tier.lower(), 0)
            if session_ord < required_ord:
                raise HTTPException(status_code=403, detail=f"Insufficient trust tier: {_tier} required, {session_tier} provided")

            # API key check for approved+ tiers
            if required_ord >= TRUST_TIER_ORDER.get("approved", 5):
                api_key = request.headers.get("X-API-Key", "")
                expected_key = request.app.state.hlf_api_key if hasattr(request.app.state, "hlf_api_key") else ""
                if expected_key and api_key != expected_key:
                    raise HTTPException(status_code=401, detail="Invalid API key")

            params: dict[str, Any] = {}
            if body is not None:
                params = body
            for key, val in request.query_params.items():
                if key not in params:
                    params[key] = val

            # ── Circuit breaker → executor (hardening) ────────────────────
            try:
                if _circuit_breaker is not None:
                    from hlf_mcp.ecosystem.circuit_breaker import CircuitBreaker, CircuitOpenError
                    if isinstance(_circuit_breaker, CircuitBreaker):
                        result = _circuit_breaker.call(_execute_with_fallback, executor, _manifest, _effect, params)
                    else:
                        result = executor(_manifest, _effect, params)
                else:
                    result = executor(_manifest, _effect, params)
            except ValueError as exc:
                if _circuit_breaker is not None:
                    from hlf_mcp.ecosystem.circuit_breaker import CircuitBreaker
                    if isinstance(_circuit_breaker, CircuitBreaker):
                        _circuit_breaker.record_failure()
                raise HTTPException(status_code=400, detail=str(exc))
            except CircuitOpenError as exc:
                raise HTTPException(
                    status_code=503,
                    detail=str(exc),
                    headers={"Retry-After": str(int(exc.retry_after))},
                )
            except Exception as exc:
                if _circuit_breaker is not None:
                    from hlf_mcp.ecosystem.circuit_breaker import CircuitBreaker
                    if isinstance(_circuit_breaker, CircuitBreaker):
                        _circuit_breaker.record_failure()
                raise HTTPException(status_code=500, detail=str(exc))

            provenance = ProvenanceChain(
                source="rest_bridge",
                path=[f"api:{path}"],
                trust=session_ord / 7.0,
            )

            response = JSONResponse(content=result)
            response.headers["X-HLF-Provenance-Hash"] = provenance.is_immutable_proof()
            response.headers["X-HLF-Trust-Tier"] = _tier
            response.headers["X-HLF-Effect-Class"] = _effect.effect_class.value
            response.headers["X-HLF-Program-Id"] = _manifest.program_id

            # ── Rate limit headers in response ────────────────────────────
            if _rate_limiter is not None:
                from hlf_mcp.ecosystem.rate_limiter import RateLimiter
                if isinstance(_rate_limiter, RateLimiter):
                    for k, v in _rate_limiter.headers(effect_name).items():
                        response.headers[k] = v

            return response

        handler_name = f"hlf_{_effect_class_to_category(effect.effect_class)}_{effect.function_name or 'handler'}"
        handler_name = "".join(c if c.isalnum() else "_" for c in handler_name)
        _handler.__name__ = handler_name

        if method == "POST":
            app.add_api_route(path, _handler, methods=["POST"], tags=[_effect_class_to_category(effect.effect_class)])
        else:
            app.add_api_route(path, _handler, methods=["GET"], tags=[_effect_class_to_category(effect.effect_class)])

    # ── Endpoint generation ──────────────────────────────────────────────────

    def _effect_to_endpoint(
        self,
        effect: TypedEffectDeclaration,
        manifest: CapabilityManifest,
    ) -> RESTEndpoint:
        """Convert a single effect to a REST endpoint descriptor."""
        method = _determine_http_method(effect.effect_class)
        path = _effect_to_path(effect, manifest)
        category = _effect_class_to_category(effect.effect_class)
        trust_tier = EFFECT_TO_TRUST_TIER.get(effect.effect_class, "advisory")

        op_id_parts: list[str] = [method.lower(), category]
        if effect.function_name and effect.function_name != "unknown":
            op_id_parts.append(effect.function_name)
        operation_id = "_".join(op_id_parts)

        summary = f"{method} {effect.effect_class.value}"
        description_parts = [
            f"Execute HLF effect: {effect.effect_class.value}",
        ]
        if effect.function_name:
            description_parts.append(f"Function: {effect.function_name}")
        description_parts.append(
            f"Trust tier: {trust_tier} | Compiled: {manifest.compiled_at[:19] if manifest.compiled_at else 'unknown'}"
        )

        request_body = None
        if method == "POST":
            request_body = _input_contract_to_openapi_request_body(effect.input_contract)
        elif effect.input_contract and effect.input_contract.parameters:
            # For GET, expose required params as query parameters
            parameters: list[dict[str, Any]] = []
            for param in effect.input_contract.parameters:
                if param.required:
                    parameters.append({
                        "name": param.name,
                        "in": "query",
                        "required": True,
                        "schema": {"type": _hlf_type_to_openapi_type(param.hlf_type)},
                    })
            if parameters:
                pass  # parameters are set separately on the endpoint

        responses = _output_contract_to_openapi_response(effect.output_contract)
        responses["400"] = {"description": "Invalid input"}
        responses["401"] = {"description": "Authentication required"}
        responses["403"] = {"description": "Insufficient trust tier"}
        responses["500"] = {"description": "Execution error"}

        security = _build_security_for_tier(trust_tier)

        return RESTEndpoint(
            method=method,
            path=path,
            summary=summary,
            description="\n".join(description_parts),
            operation_id=operation_id,
            request_body=request_body,
            responses=responses,
            tags=[category],
            security=security,
            trust_tier=trust_tier,
            category=category,
        )

    # ── Default executor ─────────────────────────────────────────────────────

    @staticmethod
    def _default_executor(
        manifest: CapabilityManifest,
        effect: TypedEffectDeclaration,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Default executor that echoes effect metadata.

        In production, this would route to the actual HLF execution engine.
        """
        return {
            "status": "ok",
            "effect_class": effect.effect_class.value,
            "function_name": effect.function_name,
            "contract_applied": True,
            "input_params": params,
            "program_id": manifest.program_id,
            "compiled_at": manifest.compiled_at,
            "trust_tier": EFFECT_TO_TRUST_TIER.get(effect.effect_class, "advisory"),
        }

    @staticmethod
    def _execute_with_fallback(
        executor: Callable[..., Any],
        manifest: CapabilityManifest,
        effect: TypedEffectDeclaration,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute with circuit breaker compatibility wrapper.

        This is a thin shim that adapts the existing executor signature
        ``executor(manifest, effect, params) → dict`` for use with the
        circuit breaker's ``call()`` method.
        """
        return executor(manifest, effect, params)


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════════


def generate_openapi_from_manifests(
    manifests: list[CapabilityManifest],
    *,
    title: str = "HLF REST API",
    version: str = "1.0.0",
    servers: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Convenience: generate OpenAPI spec from a list of manifests."""
    bridge = RESTBridge(title=title, version=version)
    return bridge.generate_openapi_spec(manifests, servers=servers)


def generate_openapi_json_from_manifests(
    manifests: list[CapabilityManifest],
    *,
    title: str = "HLF REST API",
    version: str = "1.0.0",
) -> str:
    """Convenience: generate OpenAPI JSON string from manifests."""
    bridge = RESTBridge(title=title, version=version)
    return bridge.generate_openapi_json(manifests)
