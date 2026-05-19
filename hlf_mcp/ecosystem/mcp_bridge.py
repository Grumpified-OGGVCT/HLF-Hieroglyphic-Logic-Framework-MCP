"""
MCP-Native Bridge — converts HLF CapabilityManifest to MCP tool registrations.

Bridges the gap between HLF's capability system and the Model Context Protocol.
Every compiled HLF program carries a CapabilityManifest (Phase 5) that declares
its effects, contracts, and proof surfaces. This bridge:

  - Reads CapabilityManifest from compiled HLF programs
  - Auto-registers each effect as an MCP tool with proper input/output schemas
  - Preserves provenance chains through MCP metadata (Phase 6 passthrough)
  - Produces standard MCP Tool annotations consumable by any MCP server

Integration points:
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest (Phase 5)
  - hlf_mcp.hlf.two_channel_executor.ProvenanceChain (Phase 6 provenance)
  - hlf_mcp.hlf.two_channel_executor.InstructionChannel (execution context)

MCP Tool schema reference:
  {
    "name": "tool_name",
    "description": "...",
    "inputSchema": { "type": "object", "properties": { ... }, "required": [...] },
    "annotations": { ... }
  }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    EFFECT_TO_CAPABILITY,
    EFFECT_TO_TRUST_TIER,
)
from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    EffectClass,
    HlfType,
    TypeContract,
    ProofSurface,
)
from hlf_mcp.hlf.two_channel_executor import (
    ProvenanceChain,
    InstructionChannel,
    DataChannel,
)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Schema type mapping
# ═══════════════════════════════════════════════════════════════════════════════

_HLF_TO_JSONSCHEMA: dict[str, str] = {
    "string": "string",
    "number": "number",
    "integer": "integer",
    "real": "number",
    "rational": "number",
    "boolean": "boolean",
    "json": "object",
    "any": "string",
    "list": "array",
    "set": "array",
    "map": "object",
    "refinement": "string",
}


def _hlf_type_to_json_schema(hlt: HlfType) -> dict[str, Any]:
    """Convert a single HLF type to a JSON Schema type object."""
    schema_type = _HLF_TO_JSONSCHEMA.get(hlt.value, "string")
    return {"type": schema_type}


def _contract_parameter_to_schema(param: TypeContract) -> tuple[str, dict[str, Any]]:
    """Convert a single TypeContract parameter to a JSON Schema property entry."""
    prop: dict[str, Any] = _hlf_type_to_json_schema(param.hlf_type)
    if param.constraints:
        for key, val in param.constraints.items():
            if key == "description":
                prop["description"] = str(val)
            elif key == "default":
                prop["default"] = val
            elif key == "enum":
                prop["enum"] = list(val) if isinstance(val, (list, tuple)) else [val]
            elif key in ("minimum", "maximum", "minLength", "maxLength", "pattern"):
                prop[key] = val
    return param.name, prop


def _input_contract_to_json_schema(contract: InputContract) -> dict[str, Any]:
    """Convert an InputContract to an MCP-compatible JSON Schema (Draft-07 compatible)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in contract.parameters:
        name, prop = _contract_parameter_to_schema(param)
        properties[name] = prop
        if param.required:
            required.append(name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _output_contract_to_json_schema(contract: OutputContract) -> dict[str, Any]:
    """Convert an OutputContract to a JSON Schema output descriptor."""
    if contract.output_schema:
        if isinstance(contract.output_schema, dict):
            return dict(contract.output_schema)
    return _hlf_type_to_json_schema(contract.return_type)


def _effect_class_to_category(effect_class: EffectClass) -> str:
    """Map an EffectClass to a human-readable category name."""
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


def _effect_safety_class(effect: TypedEffectDeclaration) -> str:
    """Derive MCP safety annotation from effect safety class."""
    sc = effect.safety_class.lower()
    if sc in ("critical", "dangerous"):
        return "potentially_dangerous"
    if sc == "guarded":
        return "requires_approval"
    if sc == "audited":
        return "audited"
    return "safe"


# ═══════════════════════════════════════════════════════════════════════════════
# MCPToolRegistration — a single registered MCP tool from an effect
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MCPToolRegistration:
    """A single MCP tool registration derived from one HLF effect declaration.

    Each TypedEffectDeclaration in a CapabilityManifest produces one
    MCPToolRegistration.  The registration carries the full provenance
    chain so MCP consumers can verify data lineage.
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    output_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] = field(default_factory=dict)
    category: str = "utility"
    trust_tier: str = "advisory"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_mcp_tool(self) -> dict[str, Any]:
        """Produce the MCP-standard tool descriptor dict.

        Conforms to the MCP specification:
        https://spec.modelcontextprotocol.io/specification/2025-03-26/server/tools/
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                **self.annotations,
                "hlf_provenance": self.provenance,
                "hlf_trust_tier": self.trust_tier,
                "hlf_category": self.category,
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MCPBridge — the main bridge class
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MCPBridge:
    """Bridge between HLF CapabilityManifest and MCP tool registrations.

    Usage:
        bridge = MCPBridge()
        manifest = compiler.compile_and_manifest(source)[1]
        tools = bridge.register_tools(manifest)
        # tools is a list of MCPToolRegistration objects
        # Each registration.to_mcp_tool() produces a standard MCP tool dict
    """

    session_id: str = ""
    tier: str = "hearth"

    # ── Main API ─────────────────────────────────────────────────────────────

    def register_tools(
        self,
        manifest: CapabilityManifest,
        *,
        provenance_from: dict[str, ProvenanceChain] | None = None,
    ) -> list[MCPToolRegistration]:
        """Convert a CapabilityManifest into a list of MCP tool registrations.

        Each effect in the manifest becomes a registered MCP tool with
        proper input/output schemas and provenance metadata.

        Args:
            manifest: The CapabilityManifest from a compiled HLF program.
            provenance_from: Optional provenance chains from the execution
                             context (Phase 6 DataChannel). If provided,
                             each registration carries provenance proof.

        Returns:
            List of MCPToolRegistration objects ready for MCP server use.
        """
        registrations: list[MCPToolRegistration] = []
        for effect in manifest.effects:
            reg = self._register_single_effect(effect, manifest, provenance_from)
            registrations.append(reg)
        return registrations

    def register_tools_from_ast(
        self,
        manifest: CapabilityManifest,
        *,
        instruction: InstructionChannel | None = None,
        data: DataChannel | None = None,
    ) -> list[MCPToolRegistration]:
        """Convert a manifest with full two-channel execution context.

        This is the recommended entry point when you have a compiled
        InstructionChannel (Phase 6) — provenance chains from the
        DataChannel are automatically threaded through into the MCP
        tool annotations.

        Args:
            manifest: The CapabilityManifest from the instruction channel.
            instruction: Optional InstructionChannel carrying bytecode, verification.
            data: Optional DataChannel carrying runtime inputs and provenance.

        Returns:
            List of MCPToolRegistration objects.
        """
        provenance_map: dict[str, ProvenanceChain] = {}
        if data is not None:
            provenance_map = dict(data.provenance)

        registrations = self.register_tools(manifest, provenance_from=provenance_map)

        if instruction is not None:
            for reg in registrations:
                reg.annotations["hlf_instruction_signature"] = instruction.signature
                reg.annotations["hlf_tier"] = instruction.tier
                reg.annotations["hlf_program_id"] = instruction.program_id
                if instruction.verification and instruction.verification.all_proven:
                    reg.annotations["hlf_verification_status"] = "proven"

        return registrations

    def register_tool_list(
        self,
        manifests: list[CapabilityManifest],
        *,
        provenance_from: dict[str, ProvenanceChain] | None = None,
    ) -> list[dict[str, Any]]:
        """Register tools from multiple manifests and return raw MCP dicts.

        Convenience for MCP server list_tools() implementations.
        """
        tools: list[dict[str, Any]] = []
        for manifest in manifests:
            registrations = self.register_tools(manifest, provenance_from=provenance_from)
            for reg in registrations:
                tools.append(reg.to_mcp_tool())
        return tools

    # ── Single effect registration ───────────────────────────────────────────

    def _register_single_effect(
        self,
        effect: TypedEffectDeclaration,
        manifest: CapabilityManifest,
        provenance_from: dict[str, ProvenanceChain] | None,
    ) -> MCPToolRegistration:
        """Register a single effect as an MCP tool."""
        tool_name = self._tool_name(effect, manifest)
        description = self._tool_description(effect, manifest)
        input_schema = _input_contract_to_json_schema(effect.input_contract)
        output_schema = _output_contract_to_json_schema(effect.output_contract)
        category = _effect_class_to_category(effect.effect_class)
        trust_tier = EFFECT_TO_TRUST_TIER.get(effect.effect_class, "advisory")

        annotations: dict[str, Any] = {
            "effect_class": effect.effect_class.value,
            "safety_class": effect.safety_class,
            "execution_mode": effect.execution_mode,
            "proof_requirement": effect.proof_requirement.value if effect.proof_requirement else "none",
            "review_posture": effect.review_posture,
            "program_id": manifest.program_id,
            "manifest_trust_tier": manifest.trust_tier,
            "compiler_version": manifest.compiler_version,
            "mcp_safety": _effect_safety_class(effect),
        }
        if effect.failure_modes:
            annotations["failure_modes"] = [fm.value for fm in effect.failure_modes]
        if effect.side_effects:
            annotations["side_effects"] = list(effect.side_effects)

        # ── Provenance passthrough ───────────────────────────────────────────
        provenance: dict[str, Any] = {
            "manifest_program_id": manifest.program_id,
            "manifest_signature": manifest.sign(""),
            "manifest_compiled_at": manifest.compiled_at,
            "effect_count": len(manifest.effects),
            "required_capabilities": sorted(manifest.required_capabilities),
            "proof_surfaces": [
                {
                    "bundle_sha256": ps.bundle_sha256,
                    "all_proven": ps.all_proven,
                    "proven_count": ps.proven_count,
                    "total_count": ps.total_count,
                    "solver_name": ps.solver_name,
                }
                for ps in manifest.proof_surfaces
            ],
        }

        # Thread through runtime provenance chains if available
        if provenance_from:
            provenance["runtime_provenance"] = {
                name: chain.to_dict() for name, chain in provenance_from.items()
            }

        # Build the registration
        return MCPToolRegistration(
            name=tool_name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            annotations=annotations,
            category=category,
            trust_tier=trust_tier,
            provenance=provenance,
        )

    # ── Naming helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _tool_name(effect: TypedEffectDeclaration, manifest: CapabilityManifest) -> str:
        """Generate a unique MCP tool name from an effect declaration.

        Uses effect_class + function_name to produce stable, descriptive names.
        Falls back to a hash of the effect declaration for uniqueness.
        """
        base = effect.function_name.strip() if effect.function_name else "effect"
        ec_name = effect.effect_class.value
        if base and base != "unknown":
            name = f"hlf_{ec_name}__{base}"
        else:
            # Use manifest program_id short hash as suffix
            short_id = manifest.program_id[:8] if manifest.program_id else "noid"
            name = f"hlf_{ec_name}_{short_id}"
        # Sanitize: only alphanumeric, underscore, hyphen
        name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
        return name.lower()

    @staticmethod
    def _tool_description(effect: TypedEffectDeclaration, manifest: CapabilityManifest) -> str:
        """Generate a human-readable MCP tool description."""
        parts: list[str] = []
        ec = effect.effect_class.value
        parts.append(f"HLF {ec.replace('_', ' ')} tool")
        if effect.function_name and effect.function_name != "unknown":
            parts.append(f"({effect.function_name})")
        if effect.input_contract and effect.input_contract.parameters:
            param_names = [p.name for p in effect.input_contract.parameters if p.name]
            if param_names:
                parts.append(f"— inputs: {', '.join(param_names)}")
        if effect.safety_class and effect.safety_class != "none":
            parts.append(f"[{effect.safety_class}]")
        return " ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════════


def register_manifest_as_mcp_tools(
    manifest: CapabilityManifest,
    *,
    tier: str = "hearth",
    provenance_from: dict[str, ProvenanceChain] | None = None,
) -> list[MCPToolRegistration]:
    """Convenience: register all effects in a manifest as MCP tools.

    Args:
        manifest: The CapabilityManifest to register.
        tier: Trust tier for the registration.
        provenance_from: Optional provenance chains for metadata passthrough.

    Returns:
        List of MCPToolRegistration objects.
    """
    bridge = MCPBridge(tier=tier)
    return bridge.register_tools(manifest, provenance_from=provenance_from)


def manifest_to_mcp_tool_schemas(
    manifest: CapabilityManifest,
    *,
    tier: str = "hearth",
) -> list[dict[str, Any]]:
    """Convenience: convert a manifest directly to MCP tool dicts.

    Returns raw dicts suitable for an MCP server's list_tools() response.
    """
    bridge = MCPBridge(tier=tier)
    return bridge.register_tool_list([manifest])
