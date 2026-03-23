"""
HLF Host Function Registry — JSON-backed registry with tier/gas/backend dispatch.

Loads from governance/host_functions.json at init. Falls back to built-in
defaults if JSON is not found (Docker/test environments).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_SCHEMA_TYPE_ALIASES = {
    "bool": "boolean",
    "int": "integer",
    "float": "number",
    "list": "array",
    "map": "object",
}
_ALLOWED_SCHEMA_TYPES = {
    "any",
    "array",
    "boolean",
    "integer",
    "number",
    "object",
    "path",
    "string",
}
_ALLOWED_EFFECT_CLASSES = {
    "agent_delegation",
    "assertion",
    "audit_log",
    "cryptographic_hash",
    "embedding_generation",
    "environment_read",
    "file_read",
    "file_write",
    "formal_verification",
    "governance_vote",
    "local_analysis",
    "memory_read",
    "memory_write",
    "merkle_append",
    "model_inference",
    "multimodal_audio",
    "multimodal_ocr",
    "multimodal_video",
    "multimodal_vision",
    "network_read",
    "network_write",
    "process_spawn",
    "route_selection",
    "similarity_math",
    "timing",
    "token_transform",
    "verification",
    "web_search",
}
_ALLOWED_FAILURE_TYPES = {
    "execution_error",
    "governance_error",
    "inference_error",
    "io_error",
    "memory_error",
    "network_error",
    "policy_denied",
    "timeout_error",
    "validation_error",
    "verification_error",
}
_ALLOWED_AUDIT_REQUIREMENTS = {"full", "sensitive_hash", "standard"}
_TYPED_CONTRACT_FIELDS = (
    "input_schema",
    "output_schema",
    "effect_class",
    "failure_type",
    "audit_requirement",
)


def _normalize_schema_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return _SCHEMA_TYPE_ALIASES.get(normalized, normalized)


def _validate_schema(schema: Any, *, field_name: str, fn_name: str) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError(f"{fn_name}: {field_name} must be an object schema")

    normalized = dict(schema)
    schema_type = _normalize_schema_type(normalized.get("type"))
    if schema_type not in _ALLOWED_SCHEMA_TYPES:
        raise ValueError(
            f"{fn_name}: {field_name}.type must be one of {sorted(_ALLOWED_SCHEMA_TYPES)}"
        )
    normalized["type"] = schema_type

    if schema_type != "object":
        return normalized

    properties = normalized.get("properties", {})
    if not isinstance(properties, dict):
        raise ValueError(f"{fn_name}: {field_name}.properties must be an object")

    normalized_properties: dict[str, dict[str, Any]] = {}
    for key, value in properties.items():
        if not isinstance(value, dict):
            raise ValueError(f"{fn_name}: {field_name}.properties.{key} must be an object")
        property_schema = dict(value)
        property_type = _normalize_schema_type(property_schema.get("type"))
        if property_type not in _ALLOWED_SCHEMA_TYPES:
            raise ValueError(
                f"{fn_name}: {field_name}.properties.{key}.type must be one of "
                f"{sorted(_ALLOWED_SCHEMA_TYPES)}"
            )
        property_schema["type"] = property_type
        normalized_properties[str(key)] = property_schema

    required = normalized.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ValueError(f"{fn_name}: {field_name}.required must be a list of strings")
    unknown_required = sorted(set(required) - set(normalized_properties))
    if unknown_required:
        raise ValueError(
            f"{fn_name}: {field_name}.required references unknown properties: {unknown_required}"
        )

    normalized["properties"] = normalized_properties
    normalized["required"] = required
    normalized["additionalProperties"] = bool(normalized.get("additionalProperties", False))
    return normalized


def _validate_contract_literal(
    value: Any,
    *,
    field_name: str,
    fn_name: str,
    allowed_values: set[str],
) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in allowed_values:
        raise ValueError(f"{fn_name}: {field_name} must be one of {sorted(allowed_values)}")
    return normalized


@dataclasses.dataclass
class HostFunction:
    name: str
    args: list[dict[str, Any]]  # [{"name": "path", "type": "path"}]
    returns: str
    tiers: list[str]
    gas: int
    backend: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    effect_class: str
    failure_type: str
    audit_requirement: str
    sensitive: bool = False
    binary_path: str | None = None
    binary_sha256: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HostFunction":
        name = str(data.get("name") or "").strip()
        missing_fields = [field for field in _TYPED_CONTRACT_FIELDS if field not in data]
        if missing_fields:
            raise ValueError(
                f"{name or 'host_function'}: missing typed contract fields {missing_fields}"
            )

        return cls(
            name=name,
            args=data.get("args", []),
            returns=data.get("returns", "any"),
            tiers=data.get("tier", ["hearth", "forge", "sovereign"]),
            gas=data.get("gas", 1),
            backend=data.get("backend", "builtin"),
            input_schema=_validate_schema(
                data.get("input_schema"),
                field_name="input_schema",
                fn_name=name or "host_function",
            ),
            output_schema=_validate_schema(
                data.get("output_schema"),
                field_name="output_schema",
                fn_name=name or "host_function",
            ),
            effect_class=_validate_contract_literal(
                data.get("effect_class"),
                field_name="effect_class",
                fn_name=name or "host_function",
                allowed_values=_ALLOWED_EFFECT_CLASSES,
            ),
            failure_type=_validate_contract_literal(
                data.get("failure_type"),
                field_name="failure_type",
                fn_name=name or "host_function",
                allowed_values=_ALLOWED_FAILURE_TYPES,
            ),
            audit_requirement=_validate_contract_literal(
                data.get("audit_requirement"),
                field_name="audit_requirement",
                fn_name=name or "host_function",
                allowed_values=_ALLOWED_AUDIT_REQUIREMENTS,
            ),
            sensitive=data.get("sensitive", False),
            binary_path=data.get("binary_path"),
            binary_sha256=data.get("binary_sha256"),
        )

    def validate_args(self, call_args: list[Any]) -> None:
        if len(call_args) != len(self.args):
            raise ValueError(f"{self.name}: expected {len(self.args)} args, got {len(call_args)}")

    def policy_trace(self) -> dict[str, Any]:
        return {
            "function_name": self.name,
            "effect_class": self.effect_class,
            "failure_type": self.failure_type,
            "audit_requirement": self.audit_requirement,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "backend": self.backend,
            "sensitive": self.sensitive,
            "gas": self.gas,
        }

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class HostFunctionRegistry:
    """Registry of available host functions."""

    def __init__(self, json_path: str | None = None):
        self._functions: dict[str, HostFunction] = {}
        self._load(json_path)

    def _load(self, json_path: str | None) -> None:
        path = None
        if json_path:
            path = Path(json_path)
        else:
            # Try governance dir relative to package
            candidates = [
                Path(__file__).parent.parent.parent / "governance" / "host_functions.json",
                Path("governance") / "host_functions.json",
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break

        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for fd in data.get("functions", []):
                    fn = HostFunction.from_dict(fd)
                    self._functions[fn.name] = fn
                logger.debug("Loaded %d host functions from %s", len(self._functions), path)
                return
            except Exception as exc:
                if json_path:
                    raise ValueError(
                        f"Failed to load host function registry from {path}: {exc}"
                    ) from exc
                logger.warning("Failed to load host_functions.json: %s", exc)

        # Built-in defaults
        self._load_defaults()

    def _load_defaults(self) -> None:
        defaults = [
            (
                "READ",
                [{"name": "path", "type": "path"}],
                "string",
                ["hearth", "forge", "sovereign"],
                1,
                "dapr_file_read",
                {
                    "type": "object",
                    "properties": {"path": {"type": "path"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "file_read",
                "io_error",
                "standard",
                False,
            ),
            (
                "WRITE",
                [{"name": "path", "type": "path"}, {"name": "data", "type": "string"}],
                "bool",
                ["hearth", "forge", "sovereign"],
                2,
                "dapr_file_write",
                {
                    "type": "object",
                    "properties": {"path": {"type": "path"}, "data": {"type": "string"}},
                    "required": ["path", "data"],
                    "additionalProperties": False,
                },
                {"type": "boolean"},
                "file_write",
                "io_error",
                "full",
                False,
            ),
            (
                "HTTP_GET",
                [{"name": "url", "type": "string"}],
                "string",
                ["forge", "sovereign"],
                3,
                "dapr_http_proxy",
                {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "network_read",
                "network_error",
                "standard",
                False,
            ),
            (
                "HTTP_POST",
                [{"name": "url", "type": "string"}, {"name": "body", "type": "string"}],
                "string",
                ["forge", "sovereign"],
                5,
                "dapr_http_proxy",
                {
                    "type": "object",
                    "properties": {"url": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["url", "body"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "network_write",
                "network_error",
                "full",
                False,
            ),
            (
                "SPAWN",
                [{"name": "image", "type": "string"}, {"name": "env", "type": "map"}],
                "string",
                ["forge", "sovereign"],
                5,
                "docker_orchestrator",
                {
                    "type": "object",
                    "properties": {"image": {"type": "string"}, "env": {"type": "object"}},
                    "required": ["image", "env"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "process_spawn",
                "execution_error",
                "full",
                False,
            ),
            (
                "SLEEP",
                [{"name": "ms", "type": "int"}],
                "bool",
                ["hearth", "forge", "sovereign"],
                0,
                "builtin",
                {
                    "type": "object",
                    "properties": {"ms": {"type": "integer"}},
                    "required": ["ms"],
                    "additionalProperties": False,
                },
                {"type": "boolean"},
                "timing",
                "timeout_error",
                "standard",
                False,
            ),
            (
                "WEB_SEARCH",
                [{"name": "query", "type": "string"}],
                "string",
                ["forge", "sovereign"],
                5,
                "dapr_http_proxy",
                {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "web_search",
                "network_error",
                "sensitive_hash",
                True,
            ),
            (
                "analyze",
                [{"name": "target", "type": "string"}],
                "string",
                ["hearth", "forge", "sovereign"],
                2,
                "builtin",
                {
                    "type": "object",
                    "properties": {"target": {"type": "string"}},
                    "required": ["target"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "local_analysis",
                "execution_error",
                "standard",
                False,
            ),
            (
                "hash_sha256",
                [{"name": "data", "type": "string"}],
                "string",
                ["hearth", "forge", "sovereign"],
                2,
                "builtin",
                {
                    "type": "object",
                    "properties": {"data": {"type": "string"}},
                    "required": ["data"],
                    "additionalProperties": False,
                },
                {"type": "string"},
                "cryptographic_hash",
                "validation_error",
                "standard",
                False,
            ),
            (
                "log_emit",
                [{"name": "msg", "type": "string"}],
                "bool",
                ["hearth", "forge", "sovereign"],
                1,
                "builtin",
                {
                    "type": "object",
                    "properties": {"msg": {"type": "string"}},
                    "required": ["msg"],
                    "additionalProperties": False,
                },
                {"type": "boolean"},
                "audit_log",
                "execution_error",
                "full",
                False,
            ),
            (
                "memory_store",
                [{"name": "key", "type": "string"}, {"name": "value", "type": "any"}],
                "bool",
                ["hearth", "forge", "sovereign"],
                5,
                "builtin",
                {
                    "type": "object",
                    "properties": {"key": {"type": "string"}, "value": {"type": "any"}},
                    "required": ["key", "value"],
                    "additionalProperties": False,
                },
                {"type": "boolean"},
                "memory_write",
                "memory_error",
                "full",
                False,
            ),
            (
                "memory_recall",
                [{"name": "key", "type": "string"}],
                "any",
                ["hearth", "forge", "sovereign"],
                5,
                "builtin",
                {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                    "additionalProperties": False,
                },
                {"type": "any"},
                "memory_read",
                "memory_error",
                "standard",
                False,
            ),
            (
                "get_tier",
                [],
                "string",
                ["hearth", "forge", "sovereign"],
                1,
                "builtin",
                {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                {"type": "string"},
                "environment_read",
                "execution_error",
                "standard",
                False,
            ),
            (
                "get_vram",
                [],
                "string",
                ["hearth", "forge", "sovereign"],
                1,
                "builtin",
                {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                {"type": "string"},
                "environment_read",
                "execution_error",
                "standard",
                False,
            ),
            (
                "vote",
                [{"name": "config", "type": "string"}],
                "bool",
                ["hearth", "forge", "sovereign"],
                1,
                "builtin",
                {
                    "type": "object",
                    "properties": {"config": {"type": "string"}},
                    "required": ["config"],
                    "additionalProperties": False,
                },
                {"type": "boolean"},
                "governance_vote",
                "governance_error",
                "full",
                False,
            ),
            (
                "delegate",
                [{"name": "agent", "type": "string"}, {"name": "goal", "type": "string"}],
                "any",
                ["forge", "sovereign"],
                3,
                "builtin",
                {
                    "type": "object",
                    "properties": {"agent": {"type": "string"}, "goal": {"type": "string"}},
                    "required": ["agent", "goal"],
                    "additionalProperties": False,
                },
                {"type": "any"},
                "agent_delegation",
                "execution_error",
                "full",
                False,
            ),
            (
                "route",
                [{"name": "strategy", "type": "string"}],
                "any",
                ["forge", "sovereign"],
                2,
                "builtin",
                {
                    "type": "object",
                    "properties": {"strategy": {"type": "string"}},
                    "required": ["strategy"],
                    "additionalProperties": False,
                },
                {"type": "any"},
                "route_selection",
                "policy_denied",
                "full",
                False,
            ),
        ]
        for row in defaults:
            (
                name,
                args,
                returns,
                tiers,
                gas,
                backend,
                input_schema,
                output_schema,
                effect_class,
                failure_type,
                audit_requirement,
                sensitive,
            ) = row
            self._functions[name] = HostFunction(
                name=name,
                args=args,
                returns=returns,
                tiers=tiers,
                gas=gas,
                backend=backend,
                input_schema=input_schema,
                output_schema=output_schema,
                effect_class=effect_class,
                failure_type=failure_type,
                audit_requirement=audit_requirement,
                sensitive=sensitive,
            )

    def get(self, name: str) -> HostFunction | None:
        return self._functions.get(name)

    def call(self, name: str, args: list[Any], tier: str = "hearth") -> dict[str, Any]:
        """Validate a host function call and return a metadata envelope.

        This method is the *registry layer* — it validates the function name,
        tier permissions, and argument schema, then returns a validated metadata
        envelope.  **Actual execution** must be routed through
        ``hlf_mcp.hlf.runtime.HlfRuntime._dispatch_host()``, which implements
        every backend (analyze, vote, delegate, HTTP, file I/O, crypto, etc.).

        Callers that need real results should never call this method directly;
        use the runtime dispatcher instead.  This layer exists so the registry
        can be queried about costs, tier requirements, and argument shapes
        independently of the runtime.
        """
        fn = self._functions.get(name)
        if not fn:
            raise ValueError(f"Unknown host function: {name}")
        if tier not in fn.tiers:
            raise PermissionError(f"Function {name!r} not available in tier {tier!r}")
        fn.validate_args(args)
        # Return validated metadata envelope — callers route through runtime for execution.
        result: dict[str, Any] = {
            "host_fn": name,
            "status": "validated",
            "tier": tier,
            "gas": fn.gas,
            "dispatch": "route_through_runtime",
            "effect_class": fn.effect_class,
            "failure_type": fn.failure_type,
            "audit_requirement": fn.audit_requirement,
            "input_schema": fn.input_schema,
            "output_schema": fn.output_schema,
            "policy_trace": fn.policy_trace(),
        }
        if fn.sensitive:
            result["args_hash"] = hashlib.sha256(
                json.dumps(args, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
        else:
            result["args"] = args[:4]
        return result

    def list_all(self) -> list[dict[str, Any]]:
        return [fn.to_dict() for fn in self._functions.values()]

    def list_for_tier(self, tier: str) -> list[dict[str, Any]]:
        return [fn.to_dict() for fn in self._functions.values() if tier in fn.tiers]
