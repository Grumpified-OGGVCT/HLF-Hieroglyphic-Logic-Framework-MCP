"""
Effect Extractor — walk the compiled HLF AST and extract all declared effects.

This module walks the AST produced by HLFCompiler.compile() and extracts:
  - TypedEffectDeclaration instances from tool_stmt, glyph_stmt, and call_stmt nodes
  - InputContract and OutputContract declarations
  - ProofSurface requirements
  - Required system capabilities
  - Minimum trust tier

The extraction is EXHAUSTIVE — every statement kind that can declare effects
is inspected.  No effect type is silently skipped.

Integration:
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest
  - hlf_mcp.hlf.compiler.HLFCompiler.extract_manifest()
"""

from __future__ import annotations

import hashlib
from typing import Any

from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    ProofSurface,
    ProofRequirement,
    EffectClass,
    FailureMode,
    TypeContract,
    HlfType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool name → EffectClass mapping
# ═══════════════════════════════════════════════════════════════════════════════

_TOOL_TO_EFFECT: dict[str, EffectClass] = {
    # Filesystem
    "file_read": EffectClass.FILE_READ,
    "read_file": EffectClass.FILE_READ,
    "file_write": EffectClass.FILE_WRITE,
    "write_file": EffectClass.FILE_WRITE,
    # Network
    "web_search": EffectClass.WEB_SEARCH,
    "network_read": EffectClass.NETWORK_READ,
    "network_write": EffectClass.NETWORK_WRITE,
    "http_get": EffectClass.NETWORK_READ,
    "http_post": EffectClass.NETWORK_WRITE,
    "fetch_url": EffectClass.NETWORK_READ,
    # Memory
    "memory_read": EffectClass.MEMORY_READ,
    "memory_write": EffectClass.MEMORY_WRITE,
    "recall": EffectClass.MEMORY_READ,
    "remember": EffectClass.MEMORY_WRITE,
    # Model
    "model_inference": EffectClass.MODEL_INFERENCE,
    "infer": EffectClass.MODEL_INFERENCE,
    "llm_call": EffectClass.MODEL_INFERENCE,
    "embedding": EffectClass.EMBEDDING_GENERATION,
    # Process
    "exec": EffectClass.PROCESS_SPAWN,
    "spawn": EffectClass.PROCESS_SPAWN,
    "shell": EffectClass.PROCESS_SPAWN,
    # Agent
    "delegate": EffectClass.AGENT_DELEGATION,
    "agent_call": EffectClass.AGENT_DELEGATION,
    # Verification
    "verify": EffectClass.VERIFICATION,
    "formal_verify": EffectClass.FORMAL_VERIFICATION,
    # Audit
    "audit_log": EffectClass.AUDIT_LOG,
    "merkle_append": EffectClass.MERKLE_APPEND,
    # Embodied
    "sensor_read": EffectClass.SENSOR_READ,
    "actuate": EffectClass.GUARDED_ACTUATION,
    "safety_stop": EffectClass.SAFETY_STOP,
    # Crypto
    "hash": EffectClass.CRYPTOGRAPHIC_HASH,
    "sign": EffectClass.CRYPTOGRAPHIC_HASH,
    # Governance
    "vote": EffectClass.GOVERNANCE_VOTE,
    # Other
    "route": EffectClass.ROUTE_SELECTION,
    "timer": EffectClass.TIMING,
    "similarity": EffectClass.SIMILARITY_MATH,
    "token_transform": EffectClass.TOKEN_TRANSFORM,
    "ocr": EffectClass.MULTIMODAL_OCR,
    "vision": EffectClass.MULTIMODAL_VISION,
    "audio": EffectClass.MULTIMODAL_AUDIO,
    "video": EffectClass.MULTIMODAL_VIDEO,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Glyph + tag → EffectClass mapping
# ═══════════════════════════════════════════════════════════════════════════════

_GLYPH_TAG_TO_EFFECT: dict[tuple[str, str], EffectClass] = {
    # Δ (Delta — analyze / primary action)
    ("Δ", "RELATE"): EffectClass.LOCAL_ANALYSIS,
    ("Δ", "ANALYZE"): EffectClass.LOCAL_ANALYSIS,
    ("Δ", "INFER"): EffectClass.MODEL_INFERENCE,
    ("Δ", "QUERY"): EffectClass.NETWORK_READ,
    ("Δ", "FETCH"): EffectClass.NETWORK_READ,
    ("Δ", "READ"): EffectClass.FILE_READ,
    ("Δ", "SEARCH"): EffectClass.WEB_SEARCH,
    # Ж (Zhe — enforce / constrain / assert)
    ("Ж", "ENFORCE"): EffectClass.ASSERTION,
    ("Ж", "CONSTRAINT"): EffectClass.ASSERTION,
    ("Ж", "VERIFY"): EffectClass.VERIFICATION,
    ("Ж", "CHECK"): EffectClass.VERIFICATION,
    ("Ж", "GUARD"): EffectClass.SAFETY_STOP,
    # ⨝ (Join — consensus / vote)
    ("⨝", "VOTE"): EffectClass.GOVERNANCE_VOTE,
    ("⨝", "CONSENSUS"): EffectClass.GOVERNANCE_VOTE,
    ("⨝", "DELEGATE"): EffectClass.AGENT_DELEGATION,
    # ⌘ (Command — delegate / route)
    ("⌘", "DELEGATE"): EffectClass.AGENT_DELEGATION,
    ("⌘", "ROUTE"): EffectClass.ROUTE_SELECTION,
    ("⌘", "EXEC"): EffectClass.PROCESS_SPAWN,
    ("⌘", "SPAWN"): EffectClass.PROCESS_SPAWN,
    ("⌘", "SHELL"): EffectClass.PROCESS_SPAWN,
    # ∇ (Nabla — source / parameter)
    ("∇", "SOURCE"): EffectClass.ENVIRONMENT_READ,
    ("∇", "PARAM"): EffectClass.ENVIRONMENT_READ,
    ("∇", "IMPORT"): EffectClass.FILE_READ,
    # ⩕ (Bowtie — priority / weight)
    ("⩕", "PRIORITY"): EffectClass.ROUTE_SELECTION,
    ("⩕", "SCORE"): EffectClass.LOCAL_ANALYSIS,
    # ⌂ (House — memory anchor)
    ("⌂", "STORE"): EffectClass.MEMORY_WRITE,
    ("⌂", "RECALL"): EffectClass.MEMORY_READ,
    ("⌂", "ANCHOR"): EffectClass.MEMORY_WRITE,
    # Σ (Sigma — summary / aggregate / capsule surface)
    ("Σ", "VERIFY"): EffectClass.VERIFICATION,
    ("Σ", "EXPORT"): EffectClass.LOCAL_ANALYSIS,
    ("Σ", "SUMMARY"): EffectClass.LOCAL_ANALYSIS,
    ("Σ", "AUDIT"): EffectClass.AUDIT_LOG,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Effect Extractor
# ═══════════════════════════════════════════════════════════════════════════════


class EffectExtractor:
    """Walk a compiled HLF AST and extract all declared effects.

    Usage::

        ast = compiler.compile(source)["ast"]
        manifest = EffectExtractor.extract(ast, source)
    """

    @staticmethod
    def extract(ast: dict[str, Any], source: str = "") -> "CapabilityManifest":
        """Extract a CapabilityManifest from a compiled AST.

        Args:
            ast: The compiled AST dict (from HLFCompiler.compile()).
            source: Optional source text for computing program_id.

        Returns:
            A fully populated CapabilityManifest.
        """
        from hlf_mcp.hlf.capability_manifest import (
            CapabilityManifest,
            _determine_trust_tier,
            _collect_required_capabilities,
        )

        # Compute program ID from source or AST
        if source:
            program_id = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()
        else:
            import json
            canonical = json.dumps(ast, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            program_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        statements = ast.get("statements", [])
        if not isinstance(statements, list):
            statements = [statements] if statements else []

        effects: list[TypedEffectDeclaration] = []
        input_contracts: list[InputContract] = []
        output_contracts: list[OutputContract] = []
        proof_surfaces: list[ProofSurface] = []

        # Walk all statements
        for stmt in statements:
            EffectExtractor._extract_from_node(
                stmt, effects, input_contracts, output_contracts, proof_surfaces
            )

        trust_tier = _determine_trust_tier(effects)
        required_caps = _collect_required_capabilities(effects)

        return CapabilityManifest(
            program_id=program_id,
            effects=effects,
            required_capabilities=required_caps,
            input_contracts=input_contracts,
            output_contracts=output_contracts,
            proof_surfaces=proof_surfaces,
            trust_tier=trust_tier,
        )

    @staticmethod
    def _extract_from_node(
        node: dict[str, Any] | None,
        effects: list[TypedEffectDeclaration],
        input_contracts: list[InputContract],
        output_contracts: list[OutputContract],
        proof_surfaces: list[ProofSurface],
    ) -> None:
        """Recursively extract effects from a single AST node."""
        if not isinstance(node, dict):
            return

        kind = node.get("kind", "")

        # ── tool_stmt ───────────────────────────────────────────────────
        if kind == "tool_stmt":
            EffectExtractor._extract_tool_stmt(node, effects, input_contracts)

        # ── call_stmt ───────────────────────────────────────────────────
        elif kind == "call_stmt":
            EffectExtractor._extract_call_stmt(node, effects, input_contracts)

        # ── glyph_stmt ──────────────────────────────────────────────────
        elif kind == "glyph_stmt":
            EffectExtractor._extract_glyph_stmt(
                node, effects, input_contracts, output_contracts, proof_surfaces
            )

        # ── Recurse into child nodes ─────────────────────────────────────
        EffectExtractor._recurse_children(
            node, effects, input_contracts, output_contracts, proof_surfaces
        )

    @staticmethod
    def _recurse_children(
        node: dict[str, Any],
        effects: list[TypedEffectDeclaration],
        input_contracts: list[InputContract],
        output_contracts: list[OutputContract],
        proof_surfaces: list[ProofSurface],
    ) -> None:
        """Recurse into all child structures of an AST node."""
        # Statements in block bodies
        for key in ("statements", "body"):
            sub = node.get(key)
            if isinstance(sub, dict):
                EffectExtractor._extract_from_node(
                    sub, effects, input_contracts, output_contracts, proof_surfaces
                )
            elif isinstance(sub, list):
                for item in sub:
                    EffectExtractor._extract_from_node(
                        item, effects, input_contracts, output_contracts, proof_surfaces
                    )

        # Sub-blocks in control flow nodes
        if isinstance(node.get("body"), dict):
            EffectExtractor._extract_from_node(
                node["body"], effects, input_contracts, output_contracts, proof_surfaces
            )

        for key in ("then_body", "else_body", "block"):
            sub = node.get(key)
            if isinstance(sub, dict):
                EffectExtractor._extract_from_node(
                    sub, effects, input_contracts, output_contracts, proof_surfaces
                )

        for clause in node.get("elif_clauses", []):
            if isinstance(clause, dict):
                body = clause.get("body")
                if isinstance(body, dict):
                    EffectExtractor._extract_from_node(
                        body, effects, input_contracts, output_contracts, proof_surfaces
                    )

        # Blocks in parallel statements
        for block in node.get("blocks", []):
            if isinstance(block, dict):
                EffectExtractor._extract_from_node(
                    block, effects, input_contracts, output_contracts, proof_surfaces
                )

        # Stages in pipe statements
        for stage in node.get("stages", []):
            if isinstance(stage, dict):
                EffectExtractor._extract_from_node(
                    stage, effects, input_contracts, output_contracts, proof_surfaces
                )

    @staticmethod
    def _extract_tool_stmt(
        node: dict[str, Any],
        effects: list[TypedEffectDeclaration],
        input_contracts: list[InputContract],
    ) -> None:
        """Extract effect declaration from a tool_stmt node."""
        tool_name = str(node.get("name", "")).strip()
        if not tool_name:
            return

        effect_class = EffectExtractor._resolve_effect_class(tool_name)
        args = node.get("arguments", [])

        # Build input contract from tool arguments
        parameters = EffectExtractor._build_type_contracts_from_args(args)
        input_contract = InputContract(
            function_name=tool_name,
            parameters=parameters,
        )
        input_contracts.append(input_contract)

        # Determine failure modes from effect class
        failure_modes = EffectExtractor._infer_failure_modes(effect_class)

        # Determine proof requirement from effect class
        proof_req = EffectExtractor._infer_proof_requirement(effect_class)

        effect = TypedEffectDeclaration(
            function_name=tool_name,
            input_contract=input_contract,
            output_contract=OutputContract(function_name=tool_name),
            effect_class=effect_class,
            failure_modes=failure_modes,
            proof_requirement=proof_req,
            safety_class=EffectExtractor._infer_safety_class(effect_class),
            side_effects=effect_class.derived_side_effects(),
        )
        effects.append(effect)

    @staticmethod
    def _extract_call_stmt(
        node: dict[str, Any],
        effects: list[TypedEffectDeclaration],
        input_contracts: list[InputContract],
    ) -> None:
        """Extract effect declaration from a call_stmt node."""
        func_name = str(node.get("name", "")).strip()
        if not func_name:
            return

        effect_class = EffectExtractor._resolve_effect_class(func_name)
        args = node.get("arguments", [])

        parameters = EffectExtractor._build_type_contracts_from_args(args)
        input_contract = InputContract(
            function_name=func_name,
            parameters=parameters,
        )
        input_contracts.append(input_contract)

        failure_modes = EffectExtractor._infer_failure_modes(effect_class)
        proof_req = EffectExtractor._infer_proof_requirement(effect_class)

        effect = TypedEffectDeclaration(
            function_name=func_name,
            input_contract=input_contract,
            output_contract=OutputContract(function_name=func_name),
            effect_class=effect_class,
            failure_modes=failure_modes,
            proof_requirement=proof_req,
            safety_class=EffectExtractor._infer_safety_class(effect_class),
            side_effects=effect_class.derived_side_effects(),
        )
        effects.append(effect)

    @staticmethod
    def _extract_glyph_stmt(
        node: dict[str, Any],
        effects: list[TypedEffectDeclaration],
        input_contracts: list[InputContract],
        output_contracts: list[OutputContract],
        proof_surfaces: list[ProofSurface],
    ) -> None:
        """Extract effects from a glyph_stmt node.

        Glyph statements carry semantic meaning through their glyph+tag combination.
        Different glyph/tag pairs declare different effects.
        """
        glyph = str(node.get("glyph", ""))
        tag = str(node.get("tag", "")).upper() if node.get("tag") else ""
        args = node.get("arguments", [])

        # Build a functional name for the effect
        func_name = f"{glyph}_{tag}" if tag else f"glyph_{glyph}"

        # Determine effect class from glyph+tag
        effect_class = EffectClass.LOCAL_ANALYSIS
        if glyph and tag:
            effect_class = _GLYPH_TAG_TO_EFFECT.get((glyph, tag), EffectClass.LOCAL_ANALYSIS)
        elif glyph:
            # Use glyph-only mapping for untagged glyphs
            _glyph_only: dict[str, EffectClass] = {
                "Δ": EffectClass.LOCAL_ANALYSIS,
                "Ж": EffectClass.ASSERTION,
                "⨝": EffectClass.GOVERNANCE_VOTE,
                "⌘": EffectClass.AGENT_DELEGATION,
                "∇": EffectClass.ENVIRONMENT_READ,
                "⩕": EffectClass.ROUTE_SELECTION,
                "⌂": EffectClass.MEMORY_READ,
                "Σ": EffectClass.LOCAL_ANALYSIS,
            }
            effect_class = _glyph_only.get(glyph, EffectClass.LOCAL_ANALYSIS)

        # Build input contract from glyph arguments
        parameters = EffectExtractor._build_type_contracts_from_args(args)

        # Extract output contract from export-style glyphs (Σ [EXPORT], П [EXPORT])
        if tag in ("EXPORT", "RETURN", "RESULT"):
            output_contracts.append(OutputContract(
                function_name=func_name,
                return_type=HlfType.ANY,
            ))

        # Extract proof surfaces from verify-style glyphs (Ж [VERIFY], Σ [VERIFY])
        if tag in ("VERIFY", "PROVE", "CHECK") or glyph == "Ж":
            proof_surfaces.append(ProofSurface(
                solver_name="fallback",
                all_proven=False,
            ))

        failure_modes = EffectExtractor._infer_failure_modes(effect_class)
        proof_req = EffectExtractor._infer_proof_requirement(effect_class)
        safety_class = EffectExtractor._infer_safety_class(effect_class)

        input_contract = InputContract(
            function_name=func_name,
            parameters=parameters,
        )
        input_contracts.append(input_contract)

        effect = TypedEffectDeclaration(
            function_name=func_name,
            input_contract=input_contract,
            output_contract=OutputContract(function_name=func_name),
            effect_class=effect_class,
            failure_modes=failure_modes,
            proof_requirement=proof_req,
            safety_class=safety_class,
            side_effects=effect_class.derived_side_effects(),
        )
        effects.append(effect)

    # ── Helper methods ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_effect_class(name: str) -> EffectClass:
        """Resolve a tool/function name to an EffectClass.

        First checks the explicit mapping, then tries to parse the name
        as an EffectClass value directly.
        """
        normalized = name.strip().lower().replace("-", "_")

        # Check explicit mapping
        if normalized in _TOOL_TO_EFFECT:
            return _TOOL_TO_EFFECT[normalized]

        # Try to match as an EffectClass value
        for ec in EffectClass:
            if ec.value == normalized:
                return ec

        # Heuristic: check if name contains known effect words
        if "file" in normalized:
            if "write" in normalized:
                return EffectClass.FILE_WRITE
            return EffectClass.FILE_READ
        if "network" in normalized or "http" in normalized:
            if "write" in normalized or "post" in normalized:
                return EffectClass.NETWORK_WRITE
            return EffectClass.NETWORK_READ
        if "memory" in normalized:
            if "write" in normalized:
                return EffectClass.MEMORY_WRITE
            return EffectClass.MEMORY_READ
        if "model" in normalized or "inference" in normalized or "llm" in normalized:
            return EffectClass.MODEL_INFERENCE
        if "exec" in normalized or "shell" in normalized or "spawn" in normalized:
            return EffectClass.PROCESS_SPAWN
        if "agent" in normalized or "delegate" in normalized:
            return EffectClass.AGENT_DELEGATION
        if "verify" in normalized:
            return EffectClass.VERIFICATION
        if "audit" in normalized:
            return EffectClass.AUDIT_LOG
        if "search" in normalized:
            return EffectClass.WEB_SEARCH
        if "crypto" in normalized or "hash" in normalized or "sign" in normalized:
            return EffectClass.CRYPTOGRAPHIC_HASH
        if "embodied" in normalized or "sensor" in normalized:
            return EffectClass.SENSOR_READ
        if "actuate" in normalized or "safety" in normalized:
            return EffectClass.SAFETY_STOP

        # Default: local analysis (safest default)
        return EffectClass.LOCAL_ANALYSIS

    @staticmethod
    def _build_type_contracts_from_args(args: list[dict[str, Any]]) -> list[TypeContract]:
        """Build TypeContract list from AST argument nodes."""
        parameters: list[TypeContract] = []
        for arg in args:
            if not isinstance(arg, dict):
                continue
            arg_kind = arg.get("kind", "")
            if arg_kind == "kv_arg":
                name = str(arg.get("name", ""))
                value_node = arg.get("value", {})
                hlf_type = EffectExtractor._infer_type_from_value(value_node)
                parameters.append(TypeContract(
                    name=name,
                    hlf_type=hlf_type,
                    json_schema_type=hlf_type.to_json_schema_type(),
                    required=True,
                ))
            elif arg_kind == "pos_arg":
                value_node = arg.get("value", {})
                hlf_type = EffectExtractor._infer_type_from_value(value_node)
                parameters.append(TypeContract(
                    name=f"arg_{len(parameters)}",
                    hlf_type=hlf_type,
                    json_schema_type=hlf_type.to_json_schema_type(),
                    required=True,
                ))
        return parameters

    @staticmethod
    def _infer_type_from_value(value_node: dict[str, Any]) -> HlfType:
        """Infer HlfType from a value AST node."""
        if not isinstance(value_node, dict):
            return HlfType.ANY
        val_type = str(value_node.get("type", "")).lower()
        if val_type == "string":
            return HlfType.STRING
        if val_type in ("int", "integer"):
            return HlfType.INTEGER
        if val_type in ("float", "number"):
            return HlfType.NUMBER
        if val_type in ("bool", "boolean"):
            return HlfType.BOOLEAN
        if val_type in ("json", "object"):
            return HlfType.JSON
        if val_type == "list":
            return HlfType.LIST
        return HlfType.ANY

    @staticmethod
    def _infer_failure_modes(effect_class: EffectClass) -> list[FailureMode]:
        """Infer likely failure modes for an effect class."""
        modes: list[FailureMode] = [FailureMode.EXECUTION_ERROR]

        if effect_class in (EffectClass.FILE_READ, EffectClass.FILE_WRITE):
            modes.append(FailureMode.IO_ERROR)
        if effect_class in (EffectClass.NETWORK_READ, EffectClass.NETWORK_WRITE, EffectClass.WEB_SEARCH):
            modes.extend([FailureMode.NETWORK_ERROR, FailureMode.TIMEOUT_ERROR])
        if effect_class in (EffectClass.MODEL_INFERENCE, EffectClass.EMBEDDING_GENERATION):
            modes.append(FailureMode.INFERENCE_ERROR)
        if effect_class in (EffectClass.MEMORY_READ, EffectClass.MEMORY_WRITE):
            modes.append(FailureMode.MEMORY_ERROR)
        if effect_class in (EffectClass.FORMAL_VERIFICATION, EffectClass.VERIFICATION):
            modes.append(FailureMode.VERIFICATION_ERROR)
        if effect_class in (EffectClass.GOVERNANCE_VOTE,):
            modes.append(FailureMode.GOVERNANCE_ERROR)
        if effect_class in (EffectClass.AGENT_DELEGATION,):
            modes.append(FailureMode.POLICY_DENIED)

        return modes

    @staticmethod
    def _infer_proof_requirement(effect_class: EffectClass) -> ProofRequirement:
        """Infer the proof requirement for an effect class."""
        if effect_class in (EffectClass.GUARDED_ACTUATION, EffectClass.SAFETY_STOP):
            return ProofRequirement.OPERATOR_REVIEW_OR_VERIFIED_ADMISSION
        if effect_class in (EffectClass.PROCESS_SPAWN, EffectClass.AGENT_DELEGATION):
            return ProofRequirement.VERIFICATION_ADMITTED
        if effect_class in (EffectClass.NETWORK_WRITE, EffectClass.FILE_WRITE):
            return ProofRequirement.RUNTIME_CHECKED
        return ProofRequirement.NONE

    @staticmethod
    def _infer_safety_class(effect_class: EffectClass) -> str:
        """Infer the safety class for an effect class."""
        if effect_class in (EffectClass.GUARDED_ACTUATION, EffectClass.SAFETY_STOP):
            return "critical"
        if effect_class in (EffectClass.PROCESS_SPAWN, EffectClass.AGENT_DELEGATION):
            return "high"
        if effect_class in (EffectClass.NETWORK_WRITE, EffectClass.FILE_WRITE, EffectClass.MEMORY_WRITE):
            return "bounded"
        return "none"


# Re-export for convenience
from hlf_mcp.hlf.capability_manifest import CapabilityManifest  # noqa: E402, F401
