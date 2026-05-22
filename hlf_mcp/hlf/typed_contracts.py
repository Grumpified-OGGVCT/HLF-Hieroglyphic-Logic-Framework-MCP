"""
Typed Effect Algebra — input/output type contracts, effect declarations,
failure modes, and proof surface types for HLF tool calls.

Faithful port from hls.yaml type system (HLS v0.4.0) and governance/host_functions.json
contract schema.  Preserves the original semantic depth: types are not just validation
tags — they carry effect tracking, failure classification, and proof-gate semantics.

Type symbols (from hls.yaml terminals):
    𝕊 — string    ℕ — number    𝔹 — boolean    𝕁 — json    𝔸 — any

Effect classes (from registry _ALLOWED_EFFECT_CLASSES):
    file_read, file_write, network_read, network_write, memory_read, memory_write,
    model_inference, process_spawn, agent_delegation, formal_verification, …

Failure modes:
    io_error, network_error, timeout_error, validation_error, policy_denied,
    governance_error, verification_error, inference_error, memory_error, execution_error

Proof surface types:
    runtime_checked — fallback solver passed
    verification_admitted — CoVE gate passed
    operator_review_or_verified_admission — human-in-the-loop or formal proof

Integration points:
    - hlf_mcp.hlf.formal_verifier: FormalVerifier references contract types
    - hlf_mcp.hlf.registry: HostFunction declares typed effects
    - hlf_mcp.hlf.execution_admission: effect contract admission decisions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


# ═══════════════════════════════════════════════════════════════════════════════
# Type Symbols (from hls.yaml — TYPE_SYM terminal)
# ═══════════════════════════════════════════════════════════════════════════════

class HlfType(Enum):
    """Canonical HLF type symbols with their Unicode glyphs and JSON-Schema mappings."""
    STRING = "string"
    NUMBER = "number"        # ℕ — Natural numbers (non-negative)
    INTEGER = "integer"      # ℤ — Signed integers
    REAL = "real"            # ℝ — Real numbers (floats)
    RATIONAL = "rational"    # ℚ — Rational numbers (exact ratio)
    BOOLEAN = "boolean"
    JSON = "json"
    ANY = "any"
    LIST = "list"            # List⟨T⟩ — parametric list
    SET = "set"              # Set⟨T⟩ — parametric set
    MAP = "map"              # Map⟨K,V⟩ — parametric map
    REFINEMENT = "refinement"  # {var: T | pred} — refinement type

    @property
    def glyph(self) -> str:
        _glyphs: dict[HlfType, str] = {
            HlfType.STRING: "\U0001d54a",   # 𝕊
            HlfType.NUMBER: "\u2115",        # ℕ
            HlfType.INTEGER: "\u2124",       # ℤ
            HlfType.REAL: "\u211d",          # ℝ
            HlfType.RATIONAL: "\u211a",      # ℚ
            HlfType.BOOLEAN: "\U0001d539",   # 𝔹
            HlfType.JSON: "\U0001d541",      # 𝕁
            HlfType.ANY: "\U0001d538",       # 𝔸
        }
        return _glyphs.get(self, "?")

    @classmethod
    def from_glyph(cls, glyph: str) -> HlfType | None:
        _reverse: dict[str, HlfType] = {
            "\U0001d54a": cls.STRING,
            "\u2115": cls.NUMBER,
            "\u2124": cls.INTEGER,
            "\u211d": cls.REAL,
            "\u211a": cls.RATIONAL,
            "\U0001d539": cls.BOOLEAN,
            "\U0001d541": cls.JSON,
            "\U0001d538": cls.ANY,
        }
        return _reverse.get(glyph)

    def to_json_schema_type(self) -> str:
        """Map HLF type to JSON Schema type string."""
        _mapping: dict[HlfType, str] = {
            HlfType.STRING: "string",
            HlfType.NUMBER: "number",
            HlfType.INTEGER: "integer",
            HlfType.REAL: "number",
            HlfType.RATIONAL: "number",
            HlfType.BOOLEAN: "boolean",
            HlfType.JSON: "object",
            HlfType.ANY: "any",
            HlfType.LIST: "array",
            HlfType.SET: "array",
            HlfType.MAP: "object",
        }
        return _mapping.get(self, "any")

    @classmethod
    def from_json_schema_type(cls, schema_type: str) -> HlfType:
        """Reverse-map JSON Schema type to HLF type."""
        normalized = schema_type.strip().lower()
        _reverse: dict[str, HlfType] = {
            "string": cls.STRING,
            "number": cls.NUMBER,
            "integer": cls.INTEGER,
            "boolean": cls.BOOLEAN,
            "object": cls.JSON,
            "array": cls.JSON,
            "path": cls.STRING,
            "any": cls.ANY,
        }
        return _reverse.get(normalized, cls.ANY)


# ═══════════════════════════════════════════════════════════════════════════════
# Parametric & Refinement Types
# ═══════════════════════════════════════════════════════════════════════════════

# Composite type for all HLF type representations
HlfTypeAnnotation = Union[HlfType, "ParametricType", "RefinementType"]


@dataclass(slots=True)
class ParametricType:
    """A parametric type: List⟨ℕ⟩, Set⟨𝕊⟩, Map⟨𝕊, ℤ⟩.

    The *base* is the container kind (LIST, SET, MAP) and *params* are
    the type parameters.  Arity is validated at compile-time:
      - List, Set: exactly 1 parameter
      - Map: exactly 2 parameters (key, value)
    """
    base: HlfType
    params: tuple[HlfType, ...]

    @classmethod
    def from_ast(cls, base_str: str, param_strs: list[str]) -> ParametricType:
        """Build from AST glyph strings (e.g. base='List', params=['ℕ'])."""
        base_map: dict[str, HlfType] = {
            "List": HlfType.LIST,
            "Set": HlfType.SET,
            "Map": HlfType.MAP,
        }
        base = base_map.get(base_str, HlfType.LIST)
        params = tuple(
            HlfType.from_glyph(p) or HlfType.ANY
            for p in param_strs
        )
        return cls(base=base, params=params)

    def validate_arity(self) -> tuple[bool, str]:
        """Check that the parametric type has the correct number of parameters."""
        if self.base == HlfType.MAP:
            if len(self.params) != 2:
                return False, f"Map⟨K,V⟩ requires exactly 2 type params, got {len(self.params)}"
        elif self.base in (HlfType.LIST, HlfType.SET):
            if len(self.params) != 1:
                return False, f"{self.base.name}⟨T⟩ requires exactly 1 type param, got {len(self.params)}"
        return True, ""

    def to_glyph_str(self) -> str:
        """Render as Unicode glyph string, e.g. 'List⟨ℕ⟩'."""
        param_str = ", ".join(p.glyph for p in self.params)
        return f"{self.base.name}⟨{param_str}⟩"

    def __hash__(self) -> int:
        return hash((self.base, self.params))

    def __repr__(self) -> str:
        return self.to_glyph_str()


@dataclass(slots=True)
class RefinementType:
    """A refinement type: {var: ℕ | var > 0}.

    The *variable* names the bound identifier, *base_type* is the
    underlying HLF type, and *predicate* is the boolean expression
    that constrains valid inhabitants.
    """
    variable: str
    base_type: HlfType
    predicate: str  # The expression AST or string representation

    def to_glyph_str(self) -> str:
        return f"{{{self.variable}: {self.base_type.glyph} | {self.predicate}}}"

    def __hash__(self) -> int:
        return hash((self.variable, self.base_type, self.predicate))

    def __repr__(self) -> str:
        return self.to_glyph_str()


# ═══════════════════════════════════════════════════════════════════════════════
# Effect Class Declarations (what side effects a function can have)
# ═══════════════════════════════════════════════════════════════════════════════

class EffectClass(Enum):
    """Canonical effect classes — what kind of side effect a host function produces.

    Mirrors registry._ALLOWED_EFFECT_CLASSES.  Each value maps to a system boundary
    that governance policy can gate independently.
    """
    AGENT_DELEGATION = "agent_delegation"
    ASSERTION = "assertion"
    AUDIT_LOG = "audit_log"
    CRYPTOGRAPHIC_HASH = "cryptographic_hash"
    EMBEDDING_GENERATION = "embedding_generation"
    ENVIRONMENT_READ = "environment_read"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FORMAL_VERIFICATION = "formal_verification"
    GUARDED_ACTUATION = "guarded_actuation"
    GOVERNANCE_VOTE = "governance_vote"
    LATENT_COMMUNICATION = "latent_communication"
    LOCAL_ANALYSIS = "local_analysis"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    MERKLE_APPEND = "merkle_append"
    MODEL_INFERENCE = "model_inference"
    MULTIMODAL_AUDIO = "multimodal_audio"
    MULTIMODAL_OCR = "multimodal_ocr"
    MULTIMODAL_VIDEO = "multimodal_video"
    MULTIMODAL_VISION = "multimodal_vision"
    NETWORK_READ = "network_read"
    NETWORK_WRITE = "network_write"
    PROCESS_SPAWN = "process_spawn"
    ROUTE_SELECTION = "route_selection"
    SAFETY_STOP = "safety_stop"
    SENSOR_READ = "sensor_read"
    SIMILARITY_MATH = "similarity_math"
    TIMING = "timing"
    TOKEN_TRANSFORM = "token_transform"
    TRAJECTORY_PLAN = "trajectory_plan"
    VERIFICATION = "verification"
    WEB_SEARCH = "web_search"
    WORLD_STATE_READ = "world_state_read"

    def system_boundary(self) -> str:
        """Return the system boundary category for governance gating."""
        _boundaries: dict[EffectClass, str] = {
            EffectClass.FILE_READ: "filesystem",
            EffectClass.FILE_WRITE: "filesystem",
            EffectClass.NETWORK_READ: "network",
            EffectClass.NETWORK_WRITE: "network",
            EffectClass.WEB_SEARCH: "network",
            EffectClass.MEMORY_READ: "memory",
            EffectClass.MEMORY_WRITE: "memory",
            EffectClass.MODEL_INFERENCE: "model",
            EffectClass.EMBEDDING_GENERATION: "model",
            EffectClass.PROCESS_SPAWN: "process",
            EffectClass.AGENT_DELEGATION: "agent",
            EffectClass.GOVERNANCE_VOTE: "governance",
            EffectClass.FORMAL_VERIFICATION: "verifier",
            EffectClass.VERIFICATION: "verifier",
            EffectClass.SENSOR_READ: "embodied",
            EffectClass.WORLD_STATE_READ: "embodied",
            EffectClass.TRAJECTORY_PLAN: "embodied",
            EffectClass.GUARDED_ACTUATION: "embodied",
            EffectClass.SAFETY_STOP: "embodied",
            EffectClass.LATENT_COMMUNICATION: "model",
        }
        return _boundaries.get(self, "local")

    def is_mutating(self) -> bool:
        """Return True when the effect modifies state outside the HLF sandbox."""
        _mutating: frozenset[EffectClass] = frozenset({
            EffectClass.FILE_WRITE,
            EffectClass.NETWORK_WRITE,
            EffectClass.MEMORY_WRITE,
            EffectClass.PROCESS_SPAWN,
            EffectClass.AGENT_DELEGATION,
            EffectClass.GOVERNANCE_VOTE,
            EffectClass.MERKLE_APPEND,
            EffectClass.AUDIT_LOG,
            EffectClass.GUARDED_ACTUATION,
            EffectClass.TRAJECTORY_PLAN,
            EffectClass.SAFETY_STOP,
        })
        return self in _mutating

    def derived_side_effects(self) -> list[str]:
        """Map effect class to concrete side-effect labels used by registry."""
        _mapping: dict[EffectClass, list[str]] = {
            EffectClass.FILE_READ: ["filesystem:read"],
            EffectClass.FILE_WRITE: ["filesystem:write"],
            EffectClass.NETWORK_READ: ["network:egress:read"],
            EffectClass.NETWORK_WRITE: ["network:egress:write"],
            EffectClass.WEB_SEARCH: ["network:egress:read", "model:external_search"],
            EffectClass.PROCESS_SPAWN: ["process:spawn"],
            EffectClass.MEMORY_READ: ["memory:read"],
            EffectClass.MEMORY_WRITE: ["memory:write"],
            EffectClass.AGENT_DELEGATION: ["agent:delegate"],
            EffectClass.ROUTE_SELECTION: ["routing:select"],
            EffectClass.GOVERNANCE_VOTE: ["governance:vote"],
            EffectClass.MERKLE_APPEND: ["audit:append"],
            EffectClass.AUDIT_LOG: ["audit:append"],
            EffectClass.MODEL_INFERENCE: ["model:inference"],
            EffectClass.EMBEDDING_GENERATION: ["model:embedding"],
            EffectClass.MULTIMODAL_OCR: ["model:multimodal", "filesystem:read"],
            EffectClass.MULTIMODAL_VISION: ["model:multimodal", "filesystem:read"],
            EffectClass.MULTIMODAL_AUDIO: ["model:multimodal", "filesystem:read"],
            EffectClass.MULTIMODAL_VIDEO: ["model:multimodal", "filesystem:read"],
            EffectClass.FORMAL_VERIFICATION: ["verifier:execute"],
            EffectClass.VERIFICATION: ["verifier:execute"],
            EffectClass.SENSOR_READ: ["embodied:sensor_read"],
            EffectClass.WORLD_STATE_READ: ["embodied:world_state_read"],
            EffectClass.TRAJECTORY_PLAN: ["embodied:trajectory_plan"],
            EffectClass.GUARDED_ACTUATION: ["embodied:guarded_actuation"],
            EffectClass.SAFETY_STOP: ["embodied:safety_stop"],
            EffectClass.LATENT_COMMUNICATION: ["model:latent_extract", "model:latent_project", "model:latent_inject"],
        }
        return _mapping.get(self, [])


# ═══════════════════════════════════════════════════════════════════════════════
# Failure Mode Types
# ═══════════════════════════════════════════════════════════════════════════════

class FailureMode(Enum):
    """Canonical failure modes for host function calls.

    Each tool call must declare which failure modes it can produce.
    The governance layer gates execution based on failure mode severity.
    """
    EXECUTION_ERROR = "execution_error"
    GOVERNANCE_ERROR = "governance_error"
    INFERENCE_ERROR = "inference_error"
    IO_ERROR = "io_error"
    MEMORY_ERROR = "memory_error"
    NETWORK_ERROR = "network_error"
    POLICY_DENIED = "policy_denied"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    VERIFICATION_ERROR = "verification_error"

    def is_recoverable(self) -> bool:
        """Return True when a retry or fallback path is safe to attempt."""
        _recoverable: frozenset[FailureMode] = frozenset({
            FailureMode.TIMEOUT_ERROR,
            FailureMode.NETWORK_ERROR,
            FailureMode.IO_ERROR,
            FailureMode.VALIDATION_ERROR,
        })
        return self in _recoverable

    def is_security_sensitive(self) -> bool:
        """Return True when failure may indicate a security boundary violation."""
        _sensitive: frozenset[FailureMode] = frozenset({
            FailureMode.POLICY_DENIED,
            FailureMode.GOVERNANCE_ERROR,
            FailureMode.VERIFICATION_ERROR,
        })
        return self in _sensitive

    @property
    def severity(self) -> str:
        """Governance severity tier for audit classification."""
        if self.is_security_sensitive():
            return "critical"
        if self.is_recoverable():
            return "warning"
        return "error"


# ═══════════════════════════════════════════════════════════════════════════════
# Proof Surface Types (what verification evidence looks like)
# ═══════════════════════════════════════════════════════════════════════════════

class ProofRequirement(Enum):
    """Proof gate levels for host function admission."""
    NONE = "none"
    RUNTIME_CHECKED = "runtime_checked"
    VERIFICATION_ADMITTED = "verification_admitted"
    OPERATOR_REVIEW_OR_VERIFIED_ADMISSION = "operator_review_or_verified_admission"

    def requires_human(self) -> bool:
        return self == ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION

    def requires_formal_proof(self) -> bool:
        return self in {
            ProofRequirement.VERIFICATION_ADMITTED,
            ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION,
        }


@dataclass(slots=True)
class ProofSurface:
    """What verification evidence a tool call must produce for admission.

    Mirrors the proof bundle export from FormalVerifier.export_proof_bundle.
    """
    bundle_sha256: str = ""
    ast_sha256: str = ""
    report_sha256: str = ""
    solver_name: str = "fallback"
    z3_available: bool = False
    all_proven: bool = False
    proven_count: int = 0
    total_count: int = 0
    failed_count: int = 0
    timestamp_epoch_ms: int = 0

    def is_valid_proof(self) -> bool:
        """A proof surface is valid when it carries a non-empty chain and passes."""
        return bool(
            self.bundle_sha256
            and self.ast_sha256
            and self.report_sha256
            and self.all_proven
            and self.total_count > 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_sha256": self.bundle_sha256,
            "ast_sha256": self.ast_sha256,
            "report_sha256": self.report_sha256,
            "solver_name": self.solver_name,
            "z3_available": self.z3_available,
            "all_proven": self.all_proven,
            "proven_count": self.proven_count,
            "total_count": self.total_count,
            "failed_count": self.failed_count,
            "timestamp_epoch_ms": self.timestamp_epoch_ms,
        }

    @classmethod
    def from_verification_report(cls, report: dict[str, Any]) -> ProofSurface:
        return cls(
            bundle_sha256=str(report.get("bundle_sha256", "")),
            ast_sha256=str(report.get("ast_sha256", "")),
            report_sha256=str(report.get("report_sha256", "")),
            solver_name=str(report.get("solver_name", "fallback")),
            z3_available=bool(report.get("z3_available", False)),
            all_proven=bool((report.get("report") or {}).get("all_proven", False)),
            proven_count=int((report.get("report") or {}).get("proven", 0)),
            total_count=int((report.get("report") or {}).get("total", 0)),
            failed_count=int((report.get("report") or {}).get("failed", 0)),
            timestamp_epoch_ms=int(report.get("timestamp_epoch_ms", 0)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Input / Output Type Contracts
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class TypeContract:
    """A typed contract for a single argument or return value.

    Carries the expected HLF type, JSON Schema type, optional constraints,
    and whether the value is required.
    """
    name: str
    hlf_type: HlfType = HlfType.ANY
    json_schema_type: str = "any"
    required: bool = True
    constraints: dict[str, Any] = field(default_factory=dict)

    def validate_value(self, value: Any) -> tuple[bool, str]:
        """Validate a concrete value against this type contract.

        Returns (is_valid, error_message).
        """
        if value is None:
            if self.required:
                return False, f"'{self.name}' is required but received None"
            return True, ""

        if self.hlf_type == HlfType.STRING:
            if not isinstance(value, str):
                return False, f"'{self.name}' expected string, got {type(value).__name__}"
            if self.constraints.get("min_length") is not None and len(value) < self.constraints["min_length"]:
                return False, f"'{self.name}' length {len(value)} < min {self.constraints['min_length']}"
            if self.constraints.get("max_length") is not None and len(value) > self.constraints["max_length"]:
                return False, f"'{self.name}' length {len(value)} > max {self.constraints['max_length']}"
            if self.constraints.get("pattern") is not None:
                import re
                if not re.match(self.constraints["pattern"], value):
                    return False, f"'{self.name}' does not match pattern '{self.constraints['pattern']}'"
            return True, ""

        if self.hlf_type == HlfType.NUMBER:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"'{self.name}' expected number, got {type(value).__name__}"
            if self.constraints.get("minimum") is not None and value < self.constraints["minimum"]:
                return False, f"'{self.name}' value {value} < minimum {self.constraints['minimum']}"
            if self.constraints.get("maximum") is not None and value > self.constraints["maximum"]:
                return False, f"'{self.name}' value {value} > maximum {self.constraints['maximum']}"
            return True, ""

        if self.hlf_type == HlfType.INTEGER:
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"'{self.name}' expected integer, got {type(value).__name__}"
            if self.constraints.get("minimum") is not None and value < self.constraints["minimum"]:
                return False, f"'{self.name}' value {value} < minimum {self.constraints['minimum']}"
            if self.constraints.get("maximum") is not None and value > self.constraints["maximum"]:
                return False, f"'{self.name}' value {value} > maximum {self.constraints['maximum']}"
            return True, ""

        if self.hlf_type == HlfType.REAL:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"'{self.name}' expected real, got {type(value).__name__}"
            return True, ""

        if self.hlf_type == HlfType.RATIONAL:
            # Rational is represented as a tuple (numerator, denominator)
            if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
                if value[1] == 0:
                    return False, f"'{self.name}' rational denominator cannot be zero"
                return True, ""
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True, ""
            return False, f"'{self.name}' expected rational (int pair or number), got {type(value).__name__}"

        if self.hlf_type == HlfType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"'{self.name}' expected boolean, got {type(value).__name__}"
            return True, ""

        if self.hlf_type == HlfType.JSON:
            if not isinstance(value, (dict, list)):
                return False, f"'{self.name}' expected JSON (dict/list), got {type(value).__name__}"
            return True, ""

        # ANY — always valid
        return True, ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "hlf_type": self.hlf_type.value,
            "json_schema_type": self.json_schema_type,
            "required": self.required,
            "constraints": dict(self.constraints),
        }

    @classmethod
    def from_json_schema_property(cls, name: str, prop_schema: dict[str, Any], required: bool = True) -> TypeContract:
        schema_type = str(prop_schema.get("type", "any")).strip().lower()
        hlf_type = HlfType.from_json_schema_type(schema_type)
        constraints: dict[str, Any] = {}
        for constraint_key in ("minimum", "maximum", "min_length", "max_length", "pattern", "enum"):
            if constraint_key in prop_schema:
                constraints[constraint_key] = prop_schema[constraint_key]
        return cls(
            name=name,
            hlf_type=hlf_type,
            json_schema_type=schema_type,
            required=required,
            constraints=constraints,
        )


@dataclass(slots=True)
class InputContract:
    """Full input type contract for a host function call.

    Validates all arguments against their declared types.
    """
    function_name: str
    parameters: list[TypeContract] = field(default_factory=list)

    def validate(self, args: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a dict of named arguments against this contract.

        Returns (is_valid, list_of_errors).
        """
        errors: list[str] = []
        param_map: dict[str, TypeContract] = {p.name: p for p in self.parameters}

        # Check required params are present
        for param in self.parameters:
            if param.required and param.name not in args:
                errors.append(f"'{self.function_name}': missing required parameter '{param.name}'")

        # Check provided args against contracts
        for arg_name, arg_value in args.items():
            contract = param_map.get(arg_name)
            if contract is None:
                errors.append(f"'{self.function_name}': unknown parameter '{arg_name}'")
                continue
            valid, err = contract.validate_value(arg_value)
            if not valid:
                errors.append(f"'{self.function_name}': {err}")

        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "parameters": [p.to_dict() for p in self.parameters],
        }

    @classmethod
    def from_json_schema(
        cls,
        function_name: str,
        input_schema: dict[str, Any],
    ) -> InputContract:
        """Build an InputContract from a JSON Schema object definition."""
        properties = input_schema.get("properties", {})
        required_list: list[str] = input_schema.get("required", [])
        if not isinstance(properties, dict):
            return cls(function_name=function_name)

        parameters: list[TypeContract] = []
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue
            is_required = prop_name in required_list
            parameters.append(
                TypeContract.from_json_schema_property(prop_name, prop_schema, required=is_required)
            )
        return cls(function_name=function_name, parameters=parameters)


@dataclass(slots=True)
class OutputContract:
    """Output type contract — what a function is expected to return."""
    function_name: str
    return_type: HlfType = HlfType.ANY
    output_schema: dict[str, Any] = field(default_factory=dict)

    def validate(self, value: Any) -> tuple[bool, str]:
        """Validate a return value against the output contract."""
        if self.return_type == HlfType.ANY:
            return True, ""

        if self.return_type == HlfType.STRING:
            if isinstance(value, str):
                return True, ""
            return False, f"'{self.function_name}' expected string return, got {type(value).__name__}"

        if self.return_type == HlfType.NUMBER:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True, ""
            return False, f"'{self.function_name}' expected number return, got {type(value).__name__}"

        if self.return_type == HlfType.INTEGER:
            if isinstance(value, int) and not isinstance(value, bool):
                return True, ""
            return False, f"'{self.function_name}' expected integer return, got {type(value).__name__}"

        if self.return_type == HlfType.REAL:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True, ""
            return False, f"'{self.function_name}' expected real return, got {type(value).__name__}"

        if self.return_type == HlfType.RATIONAL:
            if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
                if value[1] != 0:
                    return True, ""
                return False, f"'{self.function_name}' rational denominator cannot be zero"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return True, ""
            return False, f"'{self.function_name}' expected rational return, got {type(value).__name__}"

        if self.return_type == HlfType.BOOLEAN:
            if isinstance(value, bool):
                return True, ""
            return False, f"'{self.function_name}' expected boolean return, got {type(value).__name__}"

        if self.return_type == HlfType.JSON:
            if isinstance(value, (dict, list)):
                return True, ""
            return False, f"'{self.function_name}' expected JSON return, got {type(value).__name__}"

        return True, ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "return_type": self.return_type.value,
            "output_schema": dict(self.output_schema),
        }

    @classmethod
    def from_json_schema(cls, function_name: str, output_schema: dict[str, Any]) -> OutputContract:
        schema_type = str(output_schema.get("type", "any")).strip().lower()
        return cls(
            function_name=function_name,
            return_type=HlfType.from_json_schema_type(schema_type),
            output_schema=dict(output_schema),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Typed Effect Declaration (full contract for a tool call)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class TypedEffectDeclaration:
    """A complete typed effect declaration for a host function.

    Bundles input/output contracts, effect class, failure modes, proof
    requirements, and safety posture into one governed surface that the
    verifier and admission gates can evaluate deterministically.
    """
    function_name: str
    input_contract: InputContract = field(default_factory=lambda: InputContract(function_name=""))
    output_contract: OutputContract = field(default_factory=lambda: OutputContract(function_name=""))
    effect_class: EffectClass = EffectClass.LOCAL_ANALYSIS
    failure_modes: list[FailureMode] = field(default_factory=list)
    proof_requirement: ProofRequirement = ProofRequirement.NONE
    safety_class: str = "none"          # none | bounded | high | critical
    review_posture: str = "none"        # none | operator_review | post_action_review
    execution_mode: str = "direct"      # direct | simulation_only | simulation_preferred | replay_only
    side_effects: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    egress_validation: dict[str, Any] = field(default_factory=lambda: {"mode": "none"})
    supervisory_only: bool = False

    def validate_call(
        self,
        args: dict[str, Any],
        *,
        proof_surface: ProofSurface | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate a complete tool call against this typed effect declaration.

        Checks:
          1. Input contract (types, required fields)
          2. Proof surface (if required by proof_requirement)
          3. Safety posture alignment

        Returns (is_admitted, list_of_denial_reasons).
        """
        reasons: list[str] = []

        # 1. Input contract validation
        args_valid, arg_errors = self.input_contract.validate(args)
        if not args_valid:
            reasons.extend(arg_errors)

        # 2. Proof surface gate
        if self.proof_requirement.requires_formal_proof():
            if proof_surface is None:
                reasons.append(
                    f"'{self.function_name}': proof surface required "
                    f"({self.proof_requirement.value}) but none provided"
                )
            elif not proof_surface.is_valid_proof():
                reasons.append(
                    f"'{self.function_name}': proof surface invalid — "
                    f"all_proven={proof_surface.all_proven}, "
                    f"proven={proof_surface.proven_count}/{proof_surface.total_count}"
                )

        # 3. Safety gate
        if self.safety_class == "critical" and self.execution_mode != "simulation_only":
            if self.proof_requirement.requires_human() and (
                proof_surface is None or not proof_surface.is_valid_proof()
            ):
                reasons.append(
                    f"'{self.function_name}': safety_class=critical with "
                    f"execution_mode={self.execution_mode} requires valid proof surface "
                    f"or operator review"
                )

        return len(reasons) == 0, reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "input_contract": self.input_contract.to_dict(),
            "output_contract": self.output_contract.to_dict(),
            "effect_class": self.effect_class.value,
            "failure_modes": [fm.value for fm in self.failure_modes],
            "proof_requirement": self.proof_requirement.value,
            "safety_class": self.safety_class,
            "review_posture": self.review_posture,
            "execution_mode": self.execution_mode,
            "side_effects": list(self.side_effects),
            "required_evidence": list(self.required_evidence),
            "egress_validation": dict(self.egress_validation),
            "supervisory_only": self.supervisory_only,
        }

    @classmethod
    def from_host_function(
        cls,
        function: Any,  # HostFunction from registry
    ) -> TypedEffectDeclaration:
        """Build a TypedEffectDeclaration from a registry HostFunction.

        This is the primary bridge between the registry's contract fields
        and the typed effect algebra used by the verifier.
        """
        try:
            effect_class = EffectClass(function.effect_class)
        except ValueError:
            effect_class = EffectClass.LOCAL_ANALYSIS

        failure_modes: list[FailureMode] = []
        try:
            failure_modes.append(FailureMode(function.failure_type))
        except ValueError:
            pass

        try:
            proof_req = ProofRequirement(function.required_proof)
        except ValueError:
            proof_req = ProofRequirement.NONE

        return cls(
            function_name=function.name,
            input_contract=InputContract.from_json_schema(function.name, function.input_schema),
            output_contract=OutputContract.from_json_schema(function.name, function.output_schema),
            effect_class=effect_class,
            failure_modes=failure_modes,
            proof_requirement=proof_req,
            safety_class=str(function.safety_class or "none"),
            review_posture=str(function.review_posture or "none"),
            execution_mode=str(function.execution_mode or "direct"),
            side_effects=list(function.side_effects),
            required_evidence=list(function.required_evidence),
            egress_validation=dict(function.egress_validation) if isinstance(function.egress_validation, dict) else {"mode": "none"},
            supervisory_only=bool(function.supervisory_only),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Effect Contract Assessment (admission decision)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(slots=True)
class EffectContractAssessment:
    """Result of evaluating a typed effect declaration against a concrete call."""
    function_name: str
    admitted: bool = False
    requires_operator_review: bool = False
    verdict: str = ""
    reasons: list[str] = field(default_factory=list)
    proof_surface: ProofSurface | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "admitted": self.admitted,
            "requires_operator_review": self.requires_operator_review,
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "proof_surface": self.proof_surface.to_dict() if self.proof_surface else None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════════════

def validate_host_function_contract(
    function_name: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    effect_class: str,
    failure_type: str,
) -> tuple[bool, list[str]]:
    """Validate that all five typed-contract fields are present and well-formed.

    Used by HostFunctionRegistry during loading to reject malformed entries.
    """
    errors: list[str] = []

    if not function_name or not function_name.strip():
        errors.append("function_name is empty")
    if not isinstance(input_schema, dict) or not input_schema:
        errors.append("input_schema is missing or not an object")
    if not isinstance(output_schema, dict) or not output_schema:
        errors.append("output_schema is missing or not an object")
    if not effect_class or effect_class not in {e.value for e in EffectClass}:
        errors.append(f"effect_class '{effect_class}' is not a valid EffectClass")
    if not failure_type or failure_type not in {f.value for f in FailureMode}:
        errors.append(f"failure_type '{failure_type}' is not a valid FailureMode")

    return len(errors) == 0, errors


# ═══════════════════════════════════════════════════════════════════════════════
# Typed contract decorator for MCP tools and host functions
# ═══════════════════════════════════════════════════════════════════════════════

import functools as _functools
from typing import Callable as _Callable


def typed_contract(
    *,
    function_name: str | None = None,
    effect_class: str = "local_analysis",
    failure_type: str = "execution_error",
    input_schema: dict[str, Any] | None = None,
    output_schema: dict[str, Any] | None = None,
    proof_requirement: str = "none",
    safety_class: str = "none",
    review_posture: str = "none",
    execution_mode: str = "direct",
    side_effects: list[str] | None = None,
    required_evidence: list[str] | None = None,
    egress_validation: dict[str, Any] | None = None,
    supervisory_only: bool = False,
    gas: int = 1,
) -> _Callable[[_Callable[..., Any]], _Callable[..., Any]]:
    """Decorator that attaches a TypedEffectDeclaration to a Python callable.

    The decorated function gains a ``__hlf_contract__`` attribute holding
    the :class:`TypedEffectDeclaration`.  The verifier and admission gates
    can inspect this attribute at runtime to enforce typed contracts without
    requiring a separate registry entry.

    Usage::

        @typed_contract(
            function_name="math.add",
            effect_class="local_analysis",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
            output_schema={"type": "number"},
        )
        def add(a: float, b: float) -> float:
            return a + b
    """

    def _decorator(fn: _Callable[..., Any]) -> _Callable[..., Any]:
        effective_name = function_name or fn.__name__

        effective_input_schema = dict(input_schema or {})
        effective_output_schema = dict(output_schema or {})

        try:
            eff_class = EffectClass(effect_class)
        except ValueError:
            eff_class = EffectClass.LOCAL_ANALYSIS

        failure_modes: list[FailureMode] = []
        try:
            failure_modes.append(FailureMode(failure_type))
        except ValueError:
            pass

        try:
            proof_req = ProofRequirement(proof_requirement)
        except ValueError:
            proof_req = ProofRequirement.NONE

        decl = TypedEffectDeclaration(
            function_name=effective_name,
            input_contract=InputContract.from_json_schema(
                effective_name, effective_input_schema
            ) if effective_input_schema else InputContract(function_name=effective_name),
            output_contract=OutputContract.from_json_schema(
                effective_name, effective_output_schema
            ) if effective_output_schema else OutputContract(function_name=effective_name),
            effect_class=eff_class,
            failure_modes=failure_modes,
            proof_requirement=proof_req,
            safety_class=str(safety_class),
            review_posture=str(review_posture),
            execution_mode=str(execution_mode),
            side_effects=list(side_effects or []),
            required_evidence=list(required_evidence or []),
            egress_validation=dict(egress_validation or {"mode": "none"}),
            supervisory_only=bool(supervisory_only),
        )

        # Attach contract and gas cost
        fn.__hlf_contract__ = decl  # type: ignore[attr-defined]
        fn.__hlf_gas__ = gas  # type: ignore[attr-defined]

        @_functools.wraps(fn)
        def _wrapper(*args: Any, **kwargs: Any) -> Any:
            # Validate positional + keyword args against input contract
            # Build arg dict from positional + keyword
            arg_dict: dict[str, Any] = dict(kwargs)
            param_names = [p.name for p in decl.input_contract.parameters]
            for i, val in enumerate(args):
                if i < len(param_names):
                    arg_dict[param_names[i]] = val

            ok, errs = decl.validate_call(arg_dict)
            if not ok:
                raise ValueError(
                    f"Typed contract violation for '{effective_name}': {'; '.join(errs)}"
                )

            result = fn(*args, **kwargs)

            # Validate output contract
            out_ok, out_err = decl.output_contract.validate(result)
            if not out_ok:
                raise ValueError(
                    f"Typed contract output violation for '{effective_name}': {out_err}"
                )

            return result

        return _wrapper

    return _decorator


# ═══════════════════════════════════════════════════════════════════════════════
# Contract registry — maps tool/function names to TypedEffectDeclarations
# ═══════════════════════════════════════════════════════════════════════════════

class ContractRegistry:
    """Registry of typed contracts indexed by function name.

    Built from decorator-attached ``__hlf_contract__`` attributes,
    HostFunction registry entries, or manual registration.
    """

    def __init__(self) -> None:
        self._contracts: dict[str, TypedEffectDeclaration] = {}

    def register(self, declaration: TypedEffectDeclaration) -> None:
        self._contracts[declaration.function_name] = declaration

    def register_from_function(self, fn: Any) -> TypedEffectDeclaration | None:
        decl = getattr(fn, "__hlf_contract__", None)
        if isinstance(decl, TypedEffectDeclaration):
            self._contracts[decl.function_name] = decl
            return decl
        return None

    def register_from_host_function(self, hf: Any) -> TypedEffectDeclaration | None:
        """Register a HostFunction by converting it to a TypedEffectDeclaration."""
        try:
            decl = TypedEffectDeclaration.from_host_function(hf)
            self._contracts[decl.function_name] = decl
            return decl
        except Exception:
            return None

    def get(self, function_name: str) -> TypedEffectDeclaration | None:
        return self._contracts.get(function_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            name: decl.to_dict()
            for name, decl in self._contracts.items()
        }

    def as_verify_map(self) -> dict[str, TypedEffectDeclaration]:
        """Return the internal map for passing to FormalVerifier.verify_ast()."""
        return dict(self._contracts)
