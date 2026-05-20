"""
Schema Translator — translates HLF type contracts to JSON Schema / OpenAPI
and validates incoming payloads against HLF expectations.

Every HLF program carries typed contracts (InputContract, OutputContract,
TypeContract) and a CapabilityManifest declaring effects. This translator:
  - Maps HLF type algebra → JSON Schema (Draft 2020-12 compatible)
  - Generates full OpenAPI 3.0 / 3.1 specs from CapabilityManifests
  - Validates JSON payloads against HLF contracts with detailed error reporting
  - Generates client SDK snippets in Python, TypeScript, and Go

Schema mapping covers the full HLF type lattice:
  INT → {"type": "integer"}      FLOAT → {"type": "number"}
  STR → {"type": "string"}       BOOL  → {"type": "boolean"}
  LIST → {"type": "array", "items": {...}}
  MAP  → {"type": "object", "additionalProperties": {...}}
  OPTIONAL → {"anyOf": [..., {"type": "null"}]}
  UNION → {"anyOf": [...]}
  Named types → {"$ref": "#/components/schemas/..."}

Integration points:
  - hlf_mcp.ecosystem.mcp_bridge.MCPBridge (tool inputSchema generation)
  - hlf_mcp.ecosystem.rest_bridge.RESTBridge (OpenAPI endpoint schemas)
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest (manifest → spec)
  - hlf_mcp.hlf.typed_contracts (full type algebra support)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hlf_mcp.hlf.typed_contracts import (
        HlfType,
        InputContract,
        OutputContract,
        TypeContract,
        TypedEffectDeclaration,
    )
    from hlf_mcp.hlf.capability_manifest import CapabilityManifest


# ═══════════════════════════════════════════════════════════════════════════════
# SchemaFormat enum
# ═══════════════════════════════════════════════════════════════════════════════


class SchemaFormat(Enum):
    """Supported output schema formats."""

    JSON_SCHEMA = "json_schema"          # JSON Schema Draft 2020-12
    OPENAPI_3_0 = "openapi_3_0"          # OpenAPI 3.0.x
    OPENAPI_3_1 = "openapi_3_1"          # OpenAPI 3.1.x


# ═══════════════════════════════════════════════════════════════════════════════
# SchemaTranslationResult — output of a translation operation
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SchemaTranslationResult:
    """Result of translating an HLF contract to a target schema format.

    Attributes:
        format: The target schema format produced.
        schema: The generated schema as a dict (JSON-compatible).
        warnings: Non-fatal warnings encountered during translation
                  (e.g., unsupported constraints, type approximations).
        unresolved_types: Types that could not be resolved to a schema
                          mapping and were approximated or skipped.
    """

    format: SchemaFormat
    schema: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    unresolved_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format.value,
            "schema": self.schema,
            "warnings": self.warnings,
            "unresolved_types": self.unresolved_types,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SchemaTranslationResult:
        return cls(
            format=SchemaFormat(data.get("format", "json_schema")),
            schema=data.get("schema", {}),
            warnings=data.get("warnings", []),
            unresolved_types=data.get("unresolved_types", []),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# HLF → JSON Schema type mapping table
# ═══════════════════════════════════════════════════════════════════════════════

_HLF_TYPE_TO_JSON_SCHEMA: dict[str, dict[str, Any]] = {
    "string":     {"type": "string"},
    "number":     {"type": "number"},
    "integer":    {"type": "integer"},
    "real":       {"type": "number"},
    "rational":   {"type": "number"},
    "boolean":    {"type": "boolean"},
    "json":       {},  # arbitrary JSON — no type constraint
    "any":        {},  # completely unconstrained
    "list":       {"type": "array"},
    "set":        {"type": "array", "uniqueItems": True},
    "map":        {"type": "object"},
    "refinement": {"type": "string"},
}

# HLF type → OpenAPI type (subset of JSON Schema)
_HLF_TYPE_TO_OPENAPI: dict[str, str] = {
    "string":   "string",
    "number":   "number",
    "integer":  "integer",
    "real":     "number",
    "rational": "number",
    "boolean":  "boolean",
    "json":     "object",
    "any":      "string",
    "list":     "array",
    "set":      "array",
    "map":      "object",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_type_name(name: str) -> str:
    """Normalize an HLF type name to a valid JSON Schema / OpenAPI identifier.

    Converts PascalCase → snake_case, strips non-alphanumeric characters
    except underscores, and lowercases.  Useful for generating component
    schema names like ``$ref: "#/components/schemas/file_read_input"``.
    """
    # Insert underscore before capital letters (PascalCase → snake_case)
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    # Lowercase and strip non-[a-z0-9_]
    normalized = re.sub(r"[^a-z0-9_]", "", s2.lower())
    # Collapse multiple underscores
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "unnamed"


def _apply_constraints_to_schema(
    schema: dict[str, Any],
    constraints: dict[str, Any],
) -> None:
    """Apply HLF constraint keys to a JSON Schema / OpenAPI schema dict.

    Mutates *schema* in place.  Handles: description, default, enum,
    minimum, maximum, minLength, maxLength, pattern, exclusiveMinimum,
    exclusiveMaximum.
    """
    for key, val in constraints.items():
        if key == "description":
            schema["description"] = str(val)
        elif key == "default":
            schema["default"] = val
        elif key == "enum":
            schema["enum"] = list(val) if isinstance(val, (list, tuple)) else [val]
        elif key in (
            "minimum", "maximum", "minLength", "maxLength", "pattern",
            "exclusiveMinimum", "exclusiveMaximum",
        ):
            schema[key] = val


# ═══════════════════════════════════════════════════════════════════════════════
# SchemaTranslator — main class
# ═══════════════════════════════════════════════════════════════════════════════


class SchemaTranslator:
    """Translates HLF type contracts to JSON Schema / OpenAPI representations.

    Provides bidirectional mapping between HLF's type algebra and standard
    schema formats, payload validation, and client SDK generation.

    Attributes:
        name: Human-readable name for this translator instance.
        strict_mode: If True, unresolvable types produce errors and are
                     rejected.  If False, they generate warnings and are
                     approximated to ``{"type": "string"}``.
        component_schemas: Registry of named schema components
                           (populated during manifest translation).
        translation_cache: Memoization cache for repeated type translations.
    """

    def __init__(
        self,
        name: str = "schema-translator",
        strict_mode: bool = True,
    ) -> None:
        self.name = name
        self.strict_mode = strict_mode
        self.component_schemas: dict[str, dict[str, Any]] = {}
        self.translation_cache: dict[str, dict[str, Any]] = {}

    # ── HLF type → JSON Schema ────────────────────────────────────────────────

    def hlf_type_to_json_schema(self, hlf_type: Any) -> dict[str, Any]:
        """Map an HLF type value to its JSON Schema representation.

        Supports all HlfType enum values and custom named types via
        ``$ref`` into the component schemas registry.

        Args:
            hlf_type: An HlfType enum value, a string type name, or a
                      ParametricType / RefinementType instance.

        Returns:
            A JSON Schema type object dict (e.g., ``{"type": "integer"}``).
        """
        # Case 1: already a dict — pass through
        if isinstance(hlf_type, dict):
            return dict(hlf_type)

        # Case 2: HlfType enum
        from hlf_mcp.hlf.typed_contracts import HlfType, ParametricType, RefinementType

        if isinstance(hlf_type, HlfType):
            base = _HLF_TYPE_TO_JSON_SCHEMA.get(hlf_type.value, {"type": "string"})
            return dict(base)

        # Case 3: ParametricType (List⟨T⟩, Set⟨T⟩, Map⟨K,V⟩)
        if isinstance(hlf_type, ParametricType):
            return self._parametric_to_json_schema(hlf_type)

        # Case 4: RefinementType ({var: T | pred})
        if isinstance(hlf_type, RefinementType):
            return self._refinement_to_json_schema(hlf_type)

        # Case 5: string type name — check component schemas, then fall back
        if isinstance(hlf_type, str):
            type_val = hlf_type.lower().strip()
            # Try as HLF type value
            if type_val in _HLF_TYPE_TO_JSON_SCHEMA:
                return dict(_HLF_TYPE_TO_JSON_SCHEMA[type_val])
            # Try as named component
            normalized = _normalize_type_name(type_val)
            if normalized in self.component_schemas:
                return {"$ref": f"#/components/schemas/{normalized}"}
            # Unresolvable
            if self.strict_mode:
                raise ValueError(
                    f"SchemaTranslator '{self.name}': cannot resolve type '{hlf_type}' "
                    f"to a JSON Schema mapping"
                )
            return {"type": "string", "description": f"Unresolved: {hlf_type}"}

        # Fallback
        return {"type": "string"}

    def _parametric_to_json_schema(self, pt: Any) -> dict[str, Any]:
        """Convert a ParametricType (List⟨T⟩, Set⟨T⟩, Map⟨K,V⟩) to JSON Schema."""
        from hlf_mcp.hlf.typed_contracts import HlfType

        if pt.base == HlfType.LIST:
            schema: dict[str, Any] = {"type": "array"}
            if pt.params:
                schema["items"] = self.hlf_type_to_json_schema(pt.params[0])
            return schema

        if pt.base == HlfType.SET:
            schema = {"type": "array", "uniqueItems": True}
            if pt.params:
                schema["items"] = self.hlf_type_to_json_schema(pt.params[0])
            return schema

        if pt.base == HlfType.MAP:
            schema = {"type": "object"}
            if len(pt.params) >= 2:
                # Map⟨K,V⟩: additionalProperties uses the value type
                schema["additionalProperties"] = self.hlf_type_to_json_schema(pt.params[1])
            elif len(pt.params) == 1:
                schema["additionalProperties"] = self.hlf_type_to_json_schema(pt.params[0])
            return schema

        # Unknown parametric base — approximate
        return {"type": "object"}

    def _refinement_to_json_schema(self, rt: Any) -> dict[str, Any]:
        """Convert a RefinementType ({var: T | pred}) to JSON Schema.

        The predicate is captured in the ``description`` and ``pattern``
        fields if it looks like a regex constraint.
        """
        schema = self.hlf_type_to_json_schema(rt.base_type)
        schema["description"] = f"Refinement: {rt.variable} satisfies ({rt.predicate})"
        # Try to extract a pattern if the predicate looks regex-like
        if "match" in rt.predicate.lower() or "regex" in rt.predicate.lower():
            match = re.search(r"""['"]([^'"]+)['"]""", rt.predicate)
            if match:
                schema["pattern"] = match.group(1)
        return schema

    # ── Contract → Schema ─────────────────────────────────────────────────────

    def contract_to_schema(
        self,
        contract: Any,
        format: SchemaFormat = SchemaFormat.JSON_SCHEMA,
    ) -> SchemaTranslationResult:
        """Translate an InputContract or OutputContract to a schema.

        For InputContract: produces ``{"type": "object", "properties": {...},
        "required": [...]}``.
        For OutputContract: produces a schema with the return type.
        For OpenAPI formats: wraps appropriately in requestBody or response
        structures.

        Args:
            contract: An InputContract or OutputContract instance.
            format: Target schema format.

        Returns:
            SchemaTranslationResult with the generated schema.
        """
        from hlf_mcp.hlf.typed_contracts import InputContract, OutputContract

        warnings: list[str] = []
        unresolved: list[str] = []

        if isinstance(contract, InputContract):
            schema = self._input_contract_to_schema(contract, warnings, unresolved)
            if format in (SchemaFormat.OPENAPI_3_0, SchemaFormat.OPENAPI_3_1):
                schema = self._wrap_as_openapi_request_body(schema)

        elif isinstance(contract, OutputContract):
            schema = self._output_contract_to_schema(contract, warnings, unresolved)
            if format in (SchemaFormat.OPENAPI_3_0, SchemaFormat.OPENAPI_3_1):
                schema = self._wrap_as_openapi_response(schema, contract.function_name)

        else:
            raise TypeError(
                f"SchemaTranslator '{self.name}': expected InputContract or "
                f"OutputContract, got {type(contract).__name__}"
            )

        return SchemaTranslationResult(
            format=format,
            schema=schema,
            warnings=warnings,
            unresolved_types=unresolved,
        )

    def _input_contract_to_schema(
        self,
        contract: Any,
        warnings: list[str],
        unresolved: list[str],
    ) -> dict[str, Any]:
        """Build a JSON Schema object from an InputContract."""
        from hlf_mcp.hlf.typed_contracts import TypeContract

        properties: dict[str, Any] = {}
        required_list: list[str] = []

        for param in contract.parameters:
            if not isinstance(param, TypeContract):
                continue
            if not param.name:
                continue

            try:
                prop_schema = self.hlf_type_to_json_schema(param.hlf_type)
            except ValueError as exc:
                unresolved.append(param.name)
                if self.strict_mode:
                    raise
                warnings.append(str(exc))
                prop_schema = {"type": "string"}

            # Apply constraints
            if param.constraints:
                _apply_constraints_to_schema(prop_schema, param.constraints)

            # Handle optional parameters
            if not param.required:
                prop_schema = {
                    "anyOf": [prop_schema, {"type": "null"}],
                }

            properties[param.name] = prop_schema
            if param.required:
                required_list.append(param.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required_list:
            schema["required"] = required_list

        return schema

    def _output_contract_to_schema(
        self,
        contract: Any,
        warnings: list[str],
        unresolved: list[str],
    ) -> dict[str, Any]:
        """Build a JSON Schema representation from an OutputContract."""
        try:
            schema = self.hlf_type_to_json_schema(contract.return_type)
        except ValueError as exc:
            unresolved.append(contract.function_name)
            if self.strict_mode:
                raise
            warnings.append(str(exc))
            schema = {"type": "string"}

        # Merge any output_schema details
        if contract.output_schema:
            for key, val in contract.output_schema.items():
                if key != "type":
                    schema[key] = val

        return schema

    @staticmethod
    def _wrap_as_openapi_request_body(schema: dict[str, Any]) -> dict[str, Any]:
        """Wrap a JSON Schema object as an OpenAPI requestBody."""
        return {
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": schema,
                    },
                },
            },
        }

    @staticmethod
    def _wrap_as_openapi_response(
        schema: dict[str, Any],
        function_name: str,
    ) -> dict[str, Any]:
        """Wrap a JSON Schema object as an OpenAPI response."""
        return {
            "responses": {
                "200": {
                    "description": f"Successful response for {function_name}",
                    "content": {
                        "application/json": {
                            "schema": schema,
                        },
                    },
                },
            },
        }

    # ── Manifest → OpenAPI ────────────────────────────────────────────────────

    def manifest_to_openapi(
        self,
        manifest: Any,
        base_url: str = "http://localhost:8000",
    ) -> dict[str, Any]:
        """Generate a full OpenAPI 3.0 specification from a CapabilityManifest.

        Creates paths from effects, requestBodies from input contracts,
        and responses from output contracts.  Each effect becomes a POST
        endpoint under ``/effects/{effect_name}``.

        Args:
            manifest: A CapabilityManifest instance.
            base_url: The base URL for the ``servers`` block.

        Returns:
            A complete OpenAPI 3.0 spec dict.
        """
        paths: dict[str, Any] = {}
        component_schemas: dict[str, Any] = {}

        for effect in manifest.effects:
            effect_name = _normalize_type_name(effect.function_name)
            path_key = f"/effects/{effect_name}"

            # Build path item
            path_item: dict[str, Any] = {
                "post": {
                    "summary": effect.function_name,
                    "description": (
                        f"Effect class: {effect.effect_class.value}. "
                        f"Safety: {effect.safety_class}. "
                    ),
                    "operationId": f"execute_{effect_name}",
                    "tags": [effect.effect_class.value],
                    "responses": {
                        "200": {
                            "description": f"Result of {effect.function_name}",
                            "content": {
                                "application/json": {
                                    "schema": self.hlf_type_to_json_schema(
                                        effect.output_contract.return_type
                                    ),
                                },
                            },
                        },
                        "400": {"description": "Invalid input"},
                        "403": {"description": "Insufficient trust tier"},
                        "500": {"description": "Execution error"},
                    },
                },
            }

            # Request body from input contract
            if effect.input_contract.parameters:
                input_result = self.contract_to_schema(
                    effect.input_contract,
                    format=SchemaFormat.JSON_SCHEMA,
                )
                path_item["post"]["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": input_result.schema,
                        },
                    },
                }

            # Register component schemas
            schema_name = f"{effect_name}_input"
            if effect.input_contract.parameters:
                input_result = self.contract_to_schema(
                    effect.input_contract,
                    format=SchemaFormat.JSON_SCHEMA,
                )
                component_schemas[schema_name] = input_result.schema

            paths[path_key] = path_item

        # Build top-level spec
        openapi_spec: dict[str, Any] = {
            "openapi": "3.0.3",
            "info": {
                "title": f"HLF Program: {manifest.program_id[:12]}",
                "description": (
                    f"Auto-generated OpenAPI spec from HLF CapabilityManifest. "
                    f"Trust tier: {manifest.trust_tier}. "
                    f"Compiler: {manifest.compiler_version}."
                ),
                "version": "1.0.0",
            },
            "servers": [
                {"url": base_url, "description": "HLF REST Bridge"},
            ],
            "paths": paths,
            "components": {
                "schemas": component_schemas,
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-HLF-API-Key",
                    },
                },
            },
            "security": [{"ApiKeyAuth": []}],
        }

        # Store component schemas for later $ref resolution
        self.component_schemas.update(component_schemas)

        return openapi_spec

    # ── Payload validation ────────────────────────────────────────────────────

    def validate_payload(
        self,
        payload: dict[str, Any],
        contract: Any,
    ) -> tuple[bool, list[str]]:
        """Validate an incoming JSON payload against an HLF contract.

        Checks required fields, type conformance, and value constraints.
        Delegates to the contract's own validation when possible, falling
        back to schema-based validation.

        Args:
            payload: The incoming JSON payload dict.
            contract: An InputContract or OutputContract instance.

        Returns:
            A tuple of (is_valid, list_of_errors).  When valid, errors is
            an empty list.
        """
        from hlf_mcp.hlf.typed_contracts import InputContract, OutputContract

        if isinstance(contract, InputContract):
            return contract.validate(payload)

        if isinstance(contract, OutputContract):
            # For output contracts, validate the entire payload as the return value
            valid, err = contract.validate(payload)
            if valid:
                return True, []
            return False, [err]

        # Unknown contract type — schema-based validation
        errors: list[str] = []
        try:
            schema = self.contract_to_schema(contract, SchemaFormat.JSON_SCHEMA)
        except Exception as exc:
            return False, [f"Schema translation failed: {exc}"]

        errors.extend(self._validate_against_schema(payload, schema.schema))
        return len(errors) == 0, errors

    def _validate_against_schema(
        self,
        payload: dict[str, Any],
        schema: dict[str, Any],
        path: str = "",
    ) -> list[str]:
        """Validate a payload against a JSON Schema dict (simplified subset).

        Supports: type, properties, required, items, additionalProperties,
        enum, minimum, maximum, minLength, maxLength, pattern.
        """
        errors: list[str] = []

        # Type check
        expected_type = schema.get("type")
        if expected_type == "object" and not isinstance(payload, dict):
            errors.append(f"{path or 'root'}: expected object, got {type(payload).__name__}")
            return errors
        if expected_type == "array" and not isinstance(payload, list):
            errors.append(f"{path or 'root'}: expected array, got {type(payload).__name__}")
            return errors
        if expected_type == "string" and not isinstance(payload, str):
            errors.append(f"{path or 'root'}: expected string, got {type(payload).__name__}")
            return errors
        if expected_type == "number" and not isinstance(payload, (int, float)):
            errors.append(f"{path or 'root'}: expected number, got {type(payload).__name__}")
            return errors
        if expected_type == "integer" and not isinstance(payload, int):
            errors.append(f"{path or 'root'}: expected integer, got {type(payload).__name__}")
            return errors
        if expected_type == "boolean" and not isinstance(payload, bool):
            errors.append(f"{path or 'root'}: expected boolean, got {type(payload).__name__}")
            return errors

        # Required fields
        if isinstance(payload, dict):
            for req in schema.get("required", []):
                if req not in payload:
                    errors.append(f"{path}.{req}: required field missing")

            # Properties validation
            for prop_name, prop_schema in schema.get("properties", {}).items():
                if prop_name in payload:
                    sub_errors = self._validate_against_schema(
                        payload[prop_name],
                        prop_schema,
                        path=f"{path}.{prop_name}" if path else prop_name,
                    )
                    errors.extend(sub_errors)

            # Additional properties
            known_props = set(schema.get("properties", {}).keys())
            for key in payload:
                if key not in known_props and schema.get("additionalProperties") is False:
                    errors.append(f"{path}.{key}: unexpected property")

        # Array items
        if isinstance(payload, list) and "items" in schema:
            for idx, item in enumerate(payload):
                sub_errors = self._validate_against_schema(
                    item,
                    schema["items"],
                    path=f"{path}[{idx}]",
                )
                errors.extend(sub_errors)

        # Enum constraint
        if "enum" in schema and payload not in schema["enum"]:
            errors.append(
                f"{path or 'root'}: value {payload!r} not in enum {schema['enum']}"
            )

        # Numeric constraints
        if isinstance(payload, (int, float)) and not isinstance(payload, bool):
            if "minimum" in schema and payload < schema["minimum"]:
                errors.append(f"{path or 'root'}: {payload} < minimum {schema['minimum']}")
            if "maximum" in schema and payload > schema["maximum"]:
                errors.append(f"{path or 'root'}: {payload} > maximum {schema['maximum']}")

        # String constraints
        if isinstance(payload, str):
            if "minLength" in schema and len(payload) < schema["minLength"]:
                errors.append(
                    f"{path or 'root'}: length {len(payload)} < minLength {schema['minLength']}"
                )
            if "maxLength" in schema and len(payload) > schema["maxLength"]:
                errors.append(
                    f"{path or 'root'}: length {len(payload)} > maxLength {schema['maxLength']}"
                )
            if "pattern" in schema:
                try:
                    if not re.match(schema["pattern"], payload):
                        errors.append(
                            f"{path or 'root'}: '{payload}' does not match pattern "
                            f"'{schema['pattern']}'"
                        )
                except re.error:
                    pass  # invalid regex in schema — skip

        return errors

    # ── Client SDK generation ─────────────────────────────────────────────────

    def generate_client_sdk(
        self,
        contract: Any,
        language: str = "python",
    ) -> str:
        """Generate a client SDK snippet for the given contract.

        Args:
            contract: An InputContract or OutputContract instance.
            language: Target language — "python", "typescript", or "go".

        Returns:
            A string containing the generated SDK code.
        """
        from hlf_mcp.hlf.typed_contracts import InputContract, OutputContract, TypeContract

        if isinstance(contract, InputContract):
            return self._generate_input_sdk(contract, language)
        if isinstance(contract, OutputContract):
            return self._generate_output_sdk(contract, language)
        raise TypeError(f"Unsupported contract type: {type(contract).__name__}")

    def _generate_input_sdk(self, contract: Any, language: str) -> str:
        """Generate SDK code for an InputContract."""
        func_name = _normalize_type_name(contract.function_name)
        class_name = f"{func_name.replace('_', ' ').title().replace(' ', '')}Input"

        if language == "python":
            return self._generate_python_input(contract, class_name)
        elif language == "typescript":
            return self._generate_typescript_input(contract, class_name)
        elif language == "go":
            return self._generate_go_input(contract, class_name)
        else:
            raise ValueError(f"Unsupported language: {language}")

    def _generate_python_input(self, contract: Any, class_name: str) -> str:
        """Generate Python pydantic model for an InputContract."""
        from hlf_mcp.hlf.typed_contracts import TypeContract

        lines: list[str] = [
            f"# Auto-generated by SchemaTranslator — HLF Input Contract: {contract.function_name}",
            "from pydantic import BaseModel, Field",
            "from typing import Optional, Any",
            "",
            "",
            f"class {class_name}(BaseModel):",
        ]

        if not contract.parameters:
            lines.append("    pass")
            return "\n".join(lines)

        for param in contract.parameters:
            if not isinstance(param, TypeContract) or not param.name:
                continue

            py_type = self._hlf_type_to_python_type(param.hlf_type)
            field_kwargs: list[str] = []

            # Description
            desc = (param.constraints or {}).get("description", "")
            if desc:
                field_kwargs.append(f"description={json.dumps(desc)}")

            # Default value
            default = (param.constraints or {}).get("default")
            if default is not None:
                field_kwargs.append(f"default={json.dumps(default)}")

            # Constraints as Field kwargs
            constraints = param.constraints or {}
            for ck in ("ge", "le", "min_length", "max_length", "pattern", "enum"):
                mapped = {
                    "ge": "minimum",
                    "le": "maximum",
                    "min_length": "minLength",
                    "max_length": "maxLength",
                }
                schema_key = mapped.get(ck, ck)
                if schema_key in constraints:
                    val = constraints[schema_key]
                    if isinstance(val, str):
                        field_kwargs.append(f"{ck}={json.dumps(val)}")
                    else:
                        field_kwargs.append(f"{ck}={val}")

            field_str = f"    {param.name}: {py_type}"
            if field_kwargs:
                field_str += " = Field(" + ", ".join(field_kwargs) + ")"
            elif not param.required:
                field_str += f" = None"

            lines.append(field_str)

        return "\n".join(lines)

    def _generate_typescript_input(self, contract: Any, class_name: str) -> str:
        """Generate TypeScript interface for an InputContract."""
        from hlf_mcp.hlf.typed_contracts import TypeContract

        lines: list[str] = [
            f"// Auto-generated by SchemaTranslator — HLF Input Contract: {contract.function_name}",
            f"export interface {class_name} {{",
        ]

        for param in contract.parameters:
            if not isinstance(param, TypeContract) or not param.name:
                continue
            ts_type = self._hlf_type_to_typescript_type(param.hlf_type)
            optional = "" if param.required else "?"
            desc = (param.constraints or {}).get("description", "")
            if desc:
                lines.append(f"  /** {desc} */")
            lines.append(f"  {param.name}{optional}: {ts_type};")

        lines.append("}")
        return "\n".join(lines)

    def _generate_go_input(self, contract: Any, class_name: str) -> str:
        """Generate Go struct for an InputContract."""
        from hlf_mcp.hlf.typed_contracts import TypeContract

        lines: list[str] = [
            f"// Auto-generated by SchemaTranslator — HLF Input Contract: {contract.function_name}",
            f"type {class_name} struct {{",
        ]

        for param in contract.parameters:
            if not isinstance(param, TypeContract) or not param.name:
                continue
            go_type = self._hlf_type_to_go_type(param.hlf_type)
            go_name = param.name.title().replace("_", "")
            json_tag = param.name
            if not param.required:
                json_tag += ",omitempty"
            lines.append(f"\t{go_name} {go_type} `json:\"{json_tag}\"`")

        lines.append("}")
        return "\n".join(lines)

    def _generate_output_sdk(self, contract: Any, language: str) -> str:
        """Generate SDK code for an OutputContract."""
        func_name = _normalize_type_name(contract.function_name)
        class_name = f"{func_name.replace('_', ' ').title().replace(' ', '')}Output"

        if language == "python":
            py_type = self._hlf_type_to_python_type(contract.return_type)
            return (
                f"# Auto-generated by SchemaTranslator — HLF Output Contract: {contract.function_name}\n"
                f"from pydantic import BaseModel\n\n\n"
                f"class {class_name}(BaseModel):\n"
                f"    result: {py_type}\n"
            )
        elif language == "typescript":
            ts_type = self._hlf_type_to_typescript_type(contract.return_type)
            return (
                f"// Auto-generated by SchemaTranslator — HLF Output Contract: {contract.function_name}\n"
                f"export interface {class_name} {{\n"
                f"  result: {ts_type};\n"
                f"}}\n"
            )
        elif language == "go":
            go_type = self._hlf_type_to_go_type(contract.return_type)
            return (
                f"// Auto-generated by SchemaTranslator — HLF Output Contract: {contract.function_name}\n"
                f"type {class_name} struct {{\n"
                f"\tResult {go_type} `json:\"result\"`\n"
                f"}}\n"
            )
        else:
            raise ValueError(f"Unsupported language: {language}")

    # ── Type mapping helpers ──────────────────────────────────────────────────

    @staticmethod
    def _hlf_type_to_python_type(hlf_type: Any) -> str:
        """Map HLF type to a Python type annotation string for pydantic."""
        from hlf_mcp.hlf.typed_contracts import HlfType
        mapping: dict[str, str] = {
            "string": "str", "number": "float", "integer": "int",
            "real": "float", "rational": "float", "boolean": "bool",
            "json": "dict[str, Any]", "any": "Any",
            "list": "list[Any]", "set": "list[Any]", "map": "dict[str, Any]",
        }
        if isinstance(hlf_type, HlfType):
            return mapping.get(hlf_type.value, "Any")
        type_name = str(getattr(hlf_type, "value", hlf_type)).lower()
        return mapping.get(type_name, "Any")

    @staticmethod
    def _hlf_type_to_typescript_type(hlf_type: Any) -> str:
        """Map HLF type to a TypeScript type string."""
        from hlf_mcp.hlf.typed_contracts import HlfType
        mapping: dict[str, str] = {
            "string": "string", "number": "number", "integer": "number",
            "real": "number", "rational": "number", "boolean": "boolean",
            "json": "Record<string, unknown>", "any": "unknown",
            "list": "unknown[]", "set": "unknown[]", "map": "Record<string, unknown>",
        }
        if isinstance(hlf_type, HlfType):
            return mapping.get(hlf_type.value, "unknown")
        type_name = str(getattr(hlf_type, "value", hlf_type)).lower()
        return mapping.get(type_name, "unknown")

    @staticmethod
    def _hlf_type_to_go_type(hlf_type: Any) -> str:
        """Map HLF type to a Go type string."""
        from hlf_mcp.hlf.typed_contracts import HlfType
        mapping: dict[str, str] = {
            "string": "string", "number": "float64", "integer": "int64",
            "real": "float64", "rational": "float64", "boolean": "bool",
            "json": "interface{}", "any": "interface{}",
            "list": "[]interface{}", "set": "[]interface{}", "map": "map[string]interface{}",
        }
        if isinstance(hlf_type, HlfType):
            return mapping.get(hlf_type.value, "interface{}")
        type_name = str(getattr(hlf_type, "value", hlf_type)).lower()
        return mapping.get(type_name, "interface{}")

    # ── Batch translation ─────────────────────────────────────────────────────

    def batch_translate(
        self,
        contracts: list[Any],
        format: SchemaFormat,
    ) -> list[SchemaTranslationResult]:
        """Translate multiple contracts in batch.

        Args:
            contracts: List of InputContract or OutputContract instances.
            format: Target schema format for all translations.

        Returns:
            List of SchemaTranslationResult, one per contract, in order.
        """
        results: list[SchemaTranslationResult] = []
        for contract in contracts:
            try:
                result = self.contract_to_schema(contract, format=format)
            except Exception as exc:
                # Capture translation failure as a result with error context
                result = SchemaTranslationResult(
                    format=format,
                    schema={"error": str(exc)},
                    warnings=[f"Translation failed for contract: {exc}"],
                    unresolved_types=[getattr(contract, "function_name", "unknown")],
                )
            results.append(result)
        return results

    # ── Stats / introspection ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return monitoring statistics for the translator."""
        return {
            "name": self.name,
            "strict_mode": self.strict_mode,
            "component_schemas_count": len(self.component_schemas),
            "component_schemas": sorted(self.component_schemas.keys()),
            "cache_size": len(self.translation_cache),
        }

    def clear_cache(self) -> None:
        """Clear the translation cache and component schemas registry."""
        self.translation_cache.clear()
        self.component_schemas.clear()
