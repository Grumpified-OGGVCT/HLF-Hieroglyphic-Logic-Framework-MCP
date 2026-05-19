"""
Capability Manifest — signed declaration of what a compiled HLF program CAN do.

Every compiled HLF program produces a CapabilityManifest. This is a first-class
compiled artifact (not a sidecar file or comment) that bridges the type system
(Phase 1) and the verification gate (Phase 3). The gate checks the manifest
before allowing execution.

The manifest declares:
  - What effects the program produces (TypedEffectDeclaration list)
  - What system capabilities it requires (filesystem, network, etc.)
  - Input/output contracts it must satisfy
  - Proof surfaces it carries
  - Minimum trust tier required for execution

Integration points:
  - hlf_mcp.hlf.compiler.HLFCompiler.extract_manifest()
  - hlf_mcp.hlf.swarm_orchestrator.SwarmOrchestrator (pre-execution gate)
  - hlf_mcp.hlf.formal_verifier.VerificationGate (manifest capability check)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    ProofSurface,
    EffectClass,
    FailureMode,
)


HLF_COMPILER_VERSION = "3.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# Trust tier ordering (ascending strictness)
# ═══════════════════════════════════════════════════════════════════════════════

TRUST_TIER_ORDER: dict[str, int] = {
    "sovereign": 0,
    "untrusted": 1,
    "advisory": 2,
    "forge": 3,
    "watched": 4,
    "approved": 5,
    "trusted": 6,
    "hearth": 7,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Effect class → required capability mapping
# ═══════════════════════════════════════════════════════════════════════════════

EFFECT_TO_CAPABILITY: dict[EffectClass, str] = {
    EffectClass.FILE_READ: "filesystem",
    EffectClass.FILE_WRITE: "filesystem",
    EffectClass.NETWORK_READ: "network",
    EffectClass.NETWORK_WRITE: "network",
    EffectClass.WEB_SEARCH: "network",
    EffectClass.MEMORY_READ: "memory",
    EffectClass.MEMORY_WRITE: "memory",
    EffectClass.MODEL_INFERENCE: "model",
    EffectClass.EMBEDDING_GENERATION: "model",
    EffectClass.MULTIMODAL_AUDIO: "model",
    EffectClass.MULTIMODAL_OCR: "model",
    EffectClass.MULTIMODAL_VIDEO: "model",
    EffectClass.MULTIMODAL_VISION: "model",
    EffectClass.PROCESS_SPAWN: "exec",
    EffectClass.AGENT_DELEGATION: "agent",
    EffectClass.GOVERNANCE_VOTE: "governance",
    EffectClass.FORMAL_VERIFICATION: "verifier",
    EffectClass.VERIFICATION: "verifier",
    EffectClass.SENSOR_READ: "embodied",
    EffectClass.WORLD_STATE_READ: "embodied",
    EffectClass.TRAJECTORY_PLAN: "embodied",
    EffectClass.GUARDED_ACTUATION: "embodied",
    EffectClass.SAFETY_STOP: "embodied",
    EffectClass.AUDIT_LOG: "audit",
    EffectClass.MERKLE_APPEND: "audit",
    EffectClass.CRYPTOGRAPHIC_HASH: "crypto",
    EffectClass.ENVIRONMENT_READ: "environment",
    EffectClass.TIMING: "local",
    EffectClass.LOCAL_ANALYSIS: "local",
    EffectClass.ASSERTION: "local",
    EffectClass.ROUTE_SELECTION: "routing",
    EffectClass.SIMILARITY_MATH: "local",
    EffectClass.TOKEN_TRANSFORM: "local",
    EffectClass.TRAJECTORY_PLAN: "embodied",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Effect severity → minimum trust tier
# ═══════════════════════════════════════════════════════════════════════════════

EFFECT_TO_TRUST_TIER: dict[EffectClass, str] = {
    EffectClass.LOCAL_ANALYSIS: "advisory",
    EffectClass.ASSERTION: "advisory",
    EffectClass.SIMILARITY_MATH: "advisory",
    EffectClass.TOKEN_TRANSFORM: "advisory",
    EffectClass.TIMING: "advisory",
    EffectClass.ENVIRONMENT_READ: "advisory",
    EffectClass.CRYPTOGRAPHIC_HASH: "advisory",
    EffectClass.AUDIT_LOG: "approved",
    EffectClass.MERKLE_APPEND: "approved",
    EffectClass.MEMORY_READ: "approved",
    EffectClass.FILE_READ: "approved",
    EffectClass.NETWORK_READ: "approved",
    EffectClass.WEB_SEARCH: "approved",
    EffectClass.ROUTE_SELECTION: "approved",
    EffectClass.MEMORY_WRITE: "watched",
    EffectClass.FILE_WRITE: "watched",
    EffectClass.MODEL_INFERENCE: "watched",
    EffectClass.EMBEDDING_GENERATION: "watched",
    EffectClass.MULTIMODAL_AUDIO: "watched",
    EffectClass.MULTIMODAL_OCR: "watched",
    EffectClass.MULTIMODAL_VIDEO: "watched",
    EffectClass.MULTIMODAL_VISION: "watched",
    EffectClass.NETWORK_WRITE: "trusted",
    EffectClass.FORMAL_VERIFICATION: "trusted",
    EffectClass.VERIFICATION: "trusted",
    EffectClass.PROCESS_SPAWN: "trusted",
    EffectClass.AGENT_DELEGATION: "trusted",
    EffectClass.GOVERNANCE_VOTE: "trusted",
    EffectClass.SENSOR_READ: "hearth",
    EffectClass.WORLD_STATE_READ: "hearth",
    EffectClass.TRAJECTORY_PLAN: "hearth",
    EffectClass.GUARDED_ACTUATION: "hearth",
    EffectClass.SAFETY_STOP: "hearth",
}


def _determine_trust_tier(effects: list[TypedEffectDeclaration]) -> str:
    """Compute the minimum trust tier required by a set of effects.

    Returns the strictest (highest) tier required by any effect.
    If no effects, defaults to "advisory".
    """
    if not effects:
        return "advisory"
    highest = "advisory"
    highest_ord = TRUST_TIER_ORDER.get(highest, 0)
    for effect in effects:
        tier = EFFECT_TO_TRUST_TIER.get(effect.effect_class, "advisory")
        tier_ord = TRUST_TIER_ORDER.get(tier, 0)
        if tier_ord > highest_ord:
            highest = tier
            highest_ord = tier_ord
    return highest


def _collect_required_capabilities(effects: list[TypedEffectDeclaration]) -> set[str]:
    """Collect the set of system capabilities required by a set of effects.

    Filters out 'local' since local operations don't require gating.
    """
    caps: set[str] = set()
    for effect in effects:
        cap = EFFECT_TO_CAPABILITY.get(effect.effect_class, "local")
        if cap != "local":
            caps.add(cap)
    return caps


# ═══════════════════════════════════════════════════════════════════════════════
# Capability Manifest
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CapabilityManifest:
    """Every compiled HLF program produces this — a signed declaration of effects.

    The manifest is the bridge between the type system (Phase 1) and the
    verification gate (Phase 3).  It declares everything the gate needs to
    make an admission decision before execution begins.
    """

    program_id: str  # SHA-256 hash of source
    effects: list[TypedEffectDeclaration] = field(default_factory=list)
    required_capabilities: set[str] = field(default_factory=set)
    input_contracts: list[InputContract] = field(default_factory=list)
    output_contracts: list[OutputContract] = field(default_factory=list)
    proof_surfaces: list[ProofSurface] = field(default_factory=list)
    trust_tier: str = "advisory"  # minimum tier required to execute
    compiled_at: str = ""  # ISO 8601 timestamp
    compiler_version: str = HLF_COMPILER_VERSION

    def __post_init__(self) -> None:
        if not self.compiled_at:
            self.compiled_at = datetime.now(timezone.utc).isoformat()

    # ── Serialization ──────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize the manifest to a JSON-compatible dictionary.

        TypedEffectDeclarations, contracts, and proof surfaces are recursively
        serialized via their own to_dict() methods.
        """
        return {
            "program_id": self.program_id,
            "effects": [e.to_dict() for e in self.effects],
            "required_capabilities": sorted(self.required_capabilities),
            "input_contracts": [c.to_dict() for c in self.input_contracts],
            "output_contracts": [c.to_dict() for c in self.output_contracts],
            "proof_surfaces": [p.to_dict() for p in self.proof_surfaces],
            "trust_tier": self.trust_tier,
            "compiled_at": self.compiled_at,
            "compiler_version": self.compiler_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityManifest:
        """Deserialize from a JSON-compatible dictionary."""
        effects: list[TypedEffectDeclaration] = []
        for e_data in data.get("effects", []):
            try:
                effects.append(_typed_effect_from_dict(e_data))
            except Exception:
                # Skip effects that fail to deserialize — don't lose the manifest
                pass

        input_contracts: list[InputContract] = []
        for c_data in data.get("input_contracts", []):
            try:
                input_contracts.append(_input_contract_from_dict(c_data))
            except Exception:
                pass

        output_contracts: list[OutputContract] = []
        for c_data in data.get("output_contracts", []):
            try:
                output_contracts.append(_output_contract_from_dict(c_data))
            except Exception:
                pass

        proof_surfaces: list[ProofSurface] = []
        for p_data in data.get("proof_surfaces", []):
            try:
                proof_surfaces.append(ProofSurface(
                    bundle_sha256=str(p_data.get("bundle_sha256", "")),
                    ast_sha256=str(p_data.get("ast_sha256", "")),
                    report_sha256=str(p_data.get("report_sha256", "")),
                    solver_name=str(p_data.get("solver_name", "fallback")),
                    z3_available=bool(p_data.get("z3_available", False)),
                    all_proven=bool(p_data.get("all_proven", False)),
                    proven_count=int(p_data.get("proven_count", 0)),
                    total_count=int(p_data.get("total_count", 0)),
                    failed_count=int(p_data.get("failed_count", 0)),
                    timestamp_epoch_ms=int(p_data.get("timestamp_epoch_ms", 0)),
                ))
            except Exception:
                pass

        return cls(
            program_id=str(data.get("program_id", "")),
            effects=effects,
            required_capabilities=set(data.get("required_capabilities", [])),
            input_contracts=input_contracts,
            output_contracts=output_contracts,
            proof_surfaces=proof_surfaces,
            trust_tier=str(data.get("trust_tier", "advisory")),
            compiled_at=str(data.get("compiled_at", "")),
            compiler_version=str(data.get("compiler_version", HLF_COMPILER_VERSION)),
        )

    # ── Capability gate ─────────────────────────────────────────────────────

    def check(self, available_capabilities: set[str]) -> bool:
        """Can this program run with the given capabilities?

        Returns True when every required capability is available.
        Returns False when the program needs capabilities the environment
        cannot provide.
        """
        return self.required_capabilities <= available_capabilities

    def check_tier(self, session_tier: str) -> bool:
        """Does the session have sufficient trust tier for this program?

        Returns True when the session tier is at least as strict as
        the program's required trust tier.
        """
        required_ord = TRUST_TIER_ORDER.get(self.trust_tier, 0)
        session_ord = TRUST_TIER_ORDER.get(session_tier, 0)
        return session_ord >= required_ord

    def full_check(self, available_capabilities: set[str], session_tier: str) -> tuple[bool, list[str]]:
        """Run both capability and trust tier checks.

        Returns (admitted, list_of_denial_reasons).
        If admitted is True, reasons will be empty.
        """
        reasons: list[str] = []
        if not self.check(available_capabilities):
            missing = self.required_capabilities - available_capabilities
            reasons.append(f"Missing capabilities: {sorted(missing)}")
        if not self.check_tier(session_tier):
            reasons.append(
                f"Insufficient trust tier: program requires '{self.trust_tier}', "
                f"session is '{session_tier}'"
            )
        return len(reasons) == 0, reasons

    # ── Cryptographic signature ─────────────────────────────────────────────

    def sign(self, signer_key: str = "") -> str:
        """Produce a cryptographic signature over the canonical JSON form.

        Uses SHA-256 over a deterministic (sorted-keys) JSON representation
        of the manifest.  The signer_key is prepended as a salt if provided.

        This signature can be used to verify that a manifest has not been
        tampered with between compilation and execution.
        """
        canonical = self._canonical_json()
        payload = f"{signer_key}:{canonical}" if signer_key else canonical
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def verify_signature(self, signature: str, signer_key: str = "") -> bool:
        """Verify that a signature matches this manifest.

        Returns True when the signature was produced by this manifest
        with the same signer_key.
        """
        return self.sign(signer_key) == signature

    def _canonical_json(self) -> str:
        """Produce a deterministic JSON representation (sorted keys, no indentation)."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# ═══════════════════════════════════════════════════════════════════════════════
# Deserialization helpers for typed contracts
# ═══════════════════════════════════════════════════════════════════════════════


def _typed_effect_from_dict(data: dict[str, Any]) -> TypedEffectDeclaration:
    """Reconstruct a TypedEffectDeclaration from a dict."""
    try:
        effect_class = EffectClass(data.get("effect_class", "local_analysis"))
    except ValueError:
        effect_class = EffectClass.LOCAL_ANALYSIS

    failure_modes: list[FailureMode] = []
    for fm_str in data.get("failure_modes", []):
        try:
            failure_modes.append(FailureMode(fm_str))
        except ValueError:
            pass

    try:
        proof_req = __import__("hlf_mcp.hlf.typed_contracts", fromlist=["ProofRequirement"]).ProofRequirement(
            data.get("proof_requirement", "none")
        )
    except (ValueError, ImportError):
        from hlf_mcp.hlf.typed_contracts import ProofRequirement
        try:
            proof_req = ProofRequirement(data.get("proof_requirement", "none"))
        except ValueError:
            proof_req = ProofRequirement.NONE

    input_data = data.get("input_contract", {})
    input_contract = _input_contract_from_dict(input_data)

    output_data = data.get("output_contract", {})
    output_contract = _output_contract_from_dict(output_data)

    return TypedEffectDeclaration(
        function_name=str(data.get("function_name", "")),
        input_contract=input_contract,
        output_contract=output_contract,
        effect_class=effect_class,
        failure_modes=failure_modes,
        proof_requirement=proof_req,
        safety_class=str(data.get("safety_class", "none")),
        review_posture=str(data.get("review_posture", "none")),
        execution_mode=str(data.get("execution_mode", "direct")),
        side_effects=list(data.get("side_effects", [])),
        required_evidence=list(data.get("required_evidence", [])),
        egress_validation=dict(data.get("egress_validation", {"mode": "none"})),
        supervisory_only=bool(data.get("supervisory_only", False)),
    )


def _input_contract_from_dict(data: dict[str, Any]) -> InputContract:
    """Reconstruct an InputContract from a dict."""
    from hlf_mcp.hlf.typed_contracts import TypeContract, HlfType as _HlfType

    parameters: list[TypeContract] = []
    for p_data in data.get("parameters", []):
        try:
            hlf_type = _HlfType(p_data.get("hlf_type", "any"))
        except ValueError:
            hlf_type = _HlfType.ANY
        parameters.append(TypeContract(
            name=str(p_data.get("name", "")),
            hlf_type=hlf_type,
            json_schema_type=str(p_data.get("json_schema_type", "any")),
            required=bool(p_data.get("required", True)),
            constraints=dict(p_data.get("constraints", {})),
        ))

    return InputContract(
        function_name=str(data.get("function_name", "")),
        parameters=parameters,
    )


def _output_contract_from_dict(data: dict[str, Any]) -> OutputContract:
    """Reconstruct an OutputContract from a dict."""
    from hlf_mcp.hlf.typed_contracts import HlfType as _HlfType

    try:
        return_type = _HlfType(data.get("return_type", "any"))
    except ValueError:
        return_type = _HlfType.ANY

    return OutputContract(
        function_name=str(data.get("function_name", "")),
        return_type=return_type,
        output_schema=dict(data.get("output_schema", {})),
    )
