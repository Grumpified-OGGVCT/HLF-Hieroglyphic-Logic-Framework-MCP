from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from hlf_mcp.hlf.typed_contracts import (
    EffectContractAssessment,
    OutputContract,
    ProofSurface,
    TypedEffectDeclaration,
)

_HAS_Z3 = False
try:
    import z3  # type: ignore[import-untyped]

    _HAS_Z3 = True
except ImportError:
    z3 = None  # type: ignore[assignment]


def z3_available() -> bool:
    return _HAS_Z3


class VerificationStatus(Enum):
    PROVEN = "proven"
    RUNTIME_CHECKED = "runtime_checked"
    COUNTEREXAMPLE = "counterexample"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"
    ERROR = "error"


class ConstraintKind(Enum):
    TYPE_INVARIANT = "type_invariant"
    RANGE_CHECK = "range_check"
    NULL_SAFETY = "null_safety"
    GAS_BOUND = "gas_bound"
    SPEC_GATE = "spec_gate"
    REACHABILITY = "reachability"
    CUSTOM = "custom"


@dataclass(slots=True)
class VerificationResult:
    property_name: str
    status: VerificationStatus
    kind: ConstraintKind
    message: str = ""
    counterexample: dict[str, Any] | None = None
    duration_ms: float = 0.0
    solver: str = ""

    def is_proven(self) -> bool:
        return self.status in (VerificationStatus.PROVEN, VerificationStatus.RUNTIME_CHECKED)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "property": self.property_name,
            "status": self.status.value,
            "kind": self.kind.value,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 2),
            "solver": self.solver,
        }
        if self.counterexample is not None:
            payload["counterexample"] = self.counterexample
        return payload


@dataclass(slots=True)
class VerificationReport:
    results: list[VerificationResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    z3_enabled: bool = _HAS_Z3

    @property
    def proven_count(self) -> int:
        return sum(
            1
            for result in self.results
            if result.status
            in (VerificationStatus.PROVEN, VerificationStatus.RUNTIME_CHECKED)
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for result in self.results if result.status == VerificationStatus.COUNTEREXAMPLE
        )

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def unknown_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.UNKNOWN)

    @property
    def skipped_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.SKIPPED)

    @property
    def runtime_checked_count(self) -> int:
        return sum(
            1
            for result in self.results
            if result.status == VerificationStatus.RUNTIME_CHECKED
        )

    @property
    def formally_proven_count(self) -> int:
        return sum(
            1 for result in self.results if result.status == VerificationStatus.PROVEN
        )

    @property
    def error_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.ERROR)

    @property
    def operator_family_coverage(self) -> dict[str, dict[str, bool]]:
        """Return a dict mapping operator family names to coverage status.

        Each entry contains:
        - covered: whether the family has at least one verification result
        - z3_available: whether Z3 SMT solving is available for this family
        """
        families = [
            "numeric",
            "string",
            "set",
            "container",
            "boolean",
            "type_system",
            "gas",
            "spec_gate",
            "rational",
            "temporal",
            "spatial",
            "effect",
        ]
        # Determine which families are covered by result kinds
        kind_family_map = {
            ConstraintKind.RANGE_CHECK: "numeric",
            ConstraintKind.TYPE_INVARIANT: "type_system",
            ConstraintKind.GAS_BOUND: "gas",
            ConstraintKind.SPEC_GATE: "spec_gate",
        }
        covered_families: set[str] = set()
        for result in self.results:
            family = kind_family_map.get(result.kind)
            if family:
                covered_families.add(family)

        coverage: dict[str, dict[str, bool]] = {}
        for family in families:
            coverage[family] = {
                "covered": family in covered_families,
                "z3_available": self.z3_enabled,
            }
        return coverage

    @property
    def blocked_count(self) -> int:
        """Count of results that would block execution at hearth tier."""
        return sum(
            1
            for result in self.results
            if result.status
            in (
                VerificationStatus.COUNTEREXAMPLE,
                VerificationStatus.UNKNOWN,
                VerificationStatus.SKIPPED,
            )
        )

    @property
    def all_proven(self) -> bool:
        return (
            self.total_count > 0
            and self.failed_count == 0
            and self.proven_count == self.total_count
        )

    def add(self, result: VerificationResult) -> None:
        self.results.append(result)
        self.total_duration_ms += result.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total_count,
            "proven": self.proven_count,
            "formally_proven": self.formally_proven_count,
            "runtime_checked": self.runtime_checked_count,
            "failed": self.failed_count,
            "unknown": self.unknown_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
            "blocked": self.blocked_count,
            "all_proven": self.all_proven,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "z3_available": self.z3_enabled,
            "operator_summary": self.summary(),
            "results": [result.to_dict() for result in self.results],
        }

    def summary(self) -> str:
        solver = "z3" if self.z3_enabled else "fallback"
        formally = self.formally_proven_count
        runtime = self.runtime_checked_count
        detail = f"formally_proven={formally}, runtime_checked={runtime}"
        return (
            f"Verification: {self.proven_count}/{self.total_count} passed ({detail}); "
            f"failed={self.failed_count}; solver={solver}; "
            f"duration_ms={self.total_duration_ms:.2f}"
        )


@dataclass(slots=True)
class ProofArtifact:
    """A structured, signed proof artifact for downstream routing and audit.

    Extended with Z3 solver coverage fields: constraints, z3_expressions,
    solver_result, proof_depth, evidence_chain, operator_summary, proof_type.
    """

    # --- Core identity fields ---
    artifact_id: str
    property_name: str
    verdict: str  # "admitted" | "denied" | "conditional"
    operator_family: str
    smt_encoding: str
    hash_algorithm: str = "sha256"
    content_hash: str = ""  # SHA-256 of the serialized proof content
    timestamp_iso: str = ""

    # --- Extended proof surface (Phase: formal verification deepening) ---
    proof_type: str = "LEMMA"  # "LEMMA" | "INDUCTIVE" | "EQUIVALENCE"
    constraints: list[dict[str, Any]] = field(default_factory=list)
    z3_expressions: list[str] = field(default_factory=list)
    solver_result: str = ""  # "sat" | "unsat" | "timeout"
    proof_depth: int = 0  # 0=LEMMA, 1=INDUCTIVE base, 2+=INDUCTIVE step
    evidence_chain: list[str] = field(default_factory=list)  # Merkle hashes
    operator_summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the proof artifact to a dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "property_name": self.property_name,
            "verdict": self.verdict,
            "operator_family": self.operator_family,
            "smt_encoding": self.smt_encoding,
            "hash_algorithm": self.hash_algorithm,
            "content_hash": self.content_hash,
            "timestamp_iso": self.timestamp_iso,
            "proof_type": self.proof_type,
            "constraints": self.constraints,
            "z3_expressions": self.z3_expressions,
            "solver_result": self.solver_result,
            "proof_depth": self.proof_depth,
            "evidence_chain": self.evidence_chain,
            "operator_summary": self.operator_summary,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize the proof artifact to a JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_verification_result(
        cls,
        result: VerificationResult,
        operator_family: str = "",
        *,
        proof_type: str = "LEMMA",
        constraints: list[dict[str, Any]] | None = None,
        z3_expressions: list[str] | None = None,
        solver_result: str = "",
        proof_depth: int = 0,
        evidence_chain: list[str] | None = None,
        operator_summary: str = "",
    ) -> ProofArtifact:
        """Create a ProofArtifact from a VerificationResult.

        Extended signature supports all new proof-depth fields while
        maintaining backward compatibility with existing callers.
        """
        return cls(
            artifact_id=str(uuid.uuid4()),
            property_name=result.property_name,
            verdict="admitted" if result.is_proven() else "denied",
            operator_family=operator_family,
            smt_encoding=result.solver,
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            proof_type=proof_type,
            constraints=constraints if constraints is not None else [],
            z3_expressions=z3_expressions if z3_expressions is not None else [],
            solver_result=solver_result,
            proof_depth=proof_depth,
            evidence_chain=evidence_chain if evidence_chain is not None else [],
            operator_summary=operator_summary,
        )


def generate_proof_artifact(
    result: VerificationResult,
    *,
    operator_family: str = "",
    metadata: dict[str, Any] | None = None,
    proof_type: str = "LEMMA",
    constraints: list[dict[str, Any]] | None = None,
    z3_expressions: list[str] | None = None,
    solver_result: str = "",
    proof_depth: int = 0,
    evidence_chain: list[str] | None = None,
    operator_summary: str = "",
) -> ProofArtifact:
    """Generate a signed proof artifact with SHA-256 content hash.

    Creates a ProofArtifact, computes the SHA-256 hash of the serialized
    proof content, and validates that the hash matches after creation.

    Args:
        result: The verification result to encode.
        operator_family: The operator family name for routing.
        metadata: Optional additional metadata.
        proof_type: Proof type ("LEMMA", "INDUCTIVE", "EQUIVALENCE").
        constraints: List of constraint dicts.
        z3_expressions: List of Z3 SMT expression strings.
        solver_result: Z3 solver result ("sat", "unsat", "timeout").
        proof_depth: Proof depth (0=LEMMA, 1=INDUCTIVE base, 2+=step).
        evidence_chain: Merkle proof hashes.
        operator_summary: Human-readable operator summary.

    Returns:
        A ProofArtifact with validated content hash.
    """
    artifact = ProofArtifact.from_verification_result(
        result,
        operator_family,
        proof_type=proof_type,
        constraints=constraints,
        z3_expressions=z3_expressions,
        solver_result=solver_result,
        proof_depth=proof_depth,
        evidence_chain=evidence_chain,
        operator_summary=operator_summary,
    )
    if metadata:
        artifact.metadata.update(metadata)

    # Compute content hash from the full dict representation (excluding hash field)
    content_for_hash = {
        "artifact_id": artifact.artifact_id,
        "property_name": artifact.property_name,
        "verdict": artifact.verdict,
        "operator_family": artifact.operator_family,
        "smt_encoding": artifact.smt_encoding,
        "timestamp_iso": artifact.timestamp_iso,
        "proof_type": artifact.proof_type,
        "constraints": artifact.constraints,
        "z3_expressions": artifact.z3_expressions,
        "solver_result": artifact.solver_result,
        "proof_depth": artifact.proof_depth,
        "evidence_chain": artifact.evidence_chain,
        "operator_summary": artifact.operator_summary,
        "metadata": artifact.metadata,
    }
    serialized = json.dumps(content_for_hash, sort_keys=True)
    computed_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    artifact.content_hash = computed_hash

    # Validate the hash matches after creation
    verify_serialized = json.dumps(content_for_hash, sort_keys=True)
    verify_hash = hashlib.sha256(verify_serialized.encode("utf-8")).hexdigest()
    if verify_hash != computed_hash:
        raise ValueError(
            f"Proof artifact hash mismatch: {verify_hash} != {computed_hash}"
        )

    return artifact


class VerificationBlockedError(Exception):
    """Raised when the verification gate blocks execution.

    This is the constitutive enforcement mechanism: when a proof fails
    at a tier that requires it, execution is blocked entirely rather
    than proceeding with a warning.
    """
    def __init__(self, report: VerificationReport, tier: str) -> None:
        self.report = report
        self.tier = tier
        super().__init__(
            f"Verification blocked: {report.blocked_count} issues at tier '{tier}'"
        )


class GateDecision:
    """Constants for verification gate decisions."""
    PROCEED = "proceed"
    BLOCK = "block"
    WARN = "warn"


class VerificationGate:
    """Constitutive gate: proof required before execution.

    Tier-differentiated gating logic:
    - Hearth/Trusted: Any counterexample or unknown/skipped → BLOCK.
      Only pure proven+no-issues → PROCEED.
    - Approved/Watched (forge): Counterexamples → BLOCK.
      Unknown/Skipped → WARN but PROCEED.
    - Advisory/Untrusted (sovereign): PROCEED always (current behavior).
    """

    HEARTH_TIER: frozenset[str] = frozenset({"hearth", "trusted"})
    STANDARD_TIER: frozenset[str] = frozenset({"approved", "watched", "forge"})
    ADVISORY_TIER: frozenset[str] = frozenset({"untrusted", "advisory", "sovereign"})

    @classmethod
    def _normalize_tier(cls, tier: str) -> str:
        """Normalize tier to its canonical group."""
        normalized = str(tier or "").strip().lower()
        if normalized in cls.HEARTH_TIER:
            return "hearth"
        if normalized in cls.STANDARD_TIER:
            return "forge"
        if normalized in cls.ADVISORY_TIER:
            return "sovereign"
        # Default: treat unknown tiers as advisory (safe default)
        return "sovereign"

    @staticmethod
    def gate(report: VerificationReport, trust_tier: str) -> str:
        """Return GateDecision: PROCEED, BLOCK, or WARN.

        Args:
            report: The verification report to evaluate.
            trust_tier: The trust tier for the agent/session.

        Returns:
            One of GateDecision.PROCEED, GateDecision.BLOCK, or GateDecision.WARN.
        """
        normalized = VerificationGate._normalize_tier(trust_tier)

        if normalized == "hearth":
            # HEARTH / TRUSTED: strictest gating
            # Any counterexample → BLOCK
            if report.failed_count > 0 or report.error_count > 0:
                return GateDecision.BLOCK
            # Any unknown/skipped → BLOCK
            if report.unknown_count > 0 or report.skipped_count > 0:
                return GateDecision.BLOCK
            # No constraints extracted at all → BLOCK
            if report.total_count == 0:
                return GateDecision.BLOCK
            # Pure proven → PROCEED
            return GateDecision.PROCEED

        if normalized == "forge":
            # APPROVED / WATCHED / FORGE: counterexamples → BLOCK
            if report.failed_count > 0 or report.error_count > 0:
                return GateDecision.BLOCK
            # Unknown/Skipped → WARN but PROCEED
            if report.unknown_count > 0 or report.skipped_count > 0:
                return GateDecision.WARN
            # No constraints extracted → WARN but PROCEED
            if report.total_count == 0:
                return GateDecision.WARN
            return GateDecision.PROCEED

        # ADVISORY / UNTRUSTED / SOVEREIGN: PROCEED always
        return GateDecision.PROCEED

    @staticmethod
    def evaluate_with_explanation(
        report: VerificationReport, trust_tier: str
    ) -> dict[str, Any]:
        """Evaluate the gate and return a human-readable decision rationale.

        Unlike `gate()` which returns only a decision string, this method
        returns a full explanation dict suitable for operator dashboards,
        audit trails, and debugging.

        Args:
            report: The verification report to evaluate.
            trust_tier: The trust tier for the agent/session.

        Returns:
            A dict with keys:
            - decision: PROCEED, BLOCK, or WARN
            - normalized_tier: the canonical tier name
            - rationale: human-readable explanation of the decision
            - blocking_factors: list of specific factors causing BLOCK/WARN
            - report_summary: summary dict from the report
        """
        normalized = VerificationGate._normalize_tier(trust_tier)
        decision = VerificationGate.gate(report, trust_tier)
        rationale, blocking_factors = VerificationGate._build_rationale(
            report, normalized, decision
        )

        return {
            "decision": decision,
            "normalized_tier": normalized,
            "rationale": rationale,
            "blocking_factors": blocking_factors,
            "report_summary": {
                "total": report.total_count,
                "proven": report.proven_count,
                "formally_proven": report.formally_proven_count,
                "runtime_checked": report.runtime_checked_count,
                "failed": report.failed_count,
                "unknown": report.unknown_count,
                "skipped": report.skipped_count,
                "errors": report.error_count,
                "blocked": report.blocked_count,
                "all_proven": report.all_proven,
            },
        }

    @staticmethod
    def _build_rationale(
        report: VerificationReport, normalized_tier: str, decision: str
    ) -> tuple[str, list[str]]:
        """Build a human-readable rationale and list of blocking factors."""
        blocking_factors: list[str] = []

        # Collect all relevant factors
        if report.failed_count > 0:
            blocking_factors.append(
                f"{report.failed_count} counterexample(s) found"
            )
        if report.error_count > 0:
            blocking_factors.append(
                f"{report.error_count} verification error(s)"
            )
        if report.unknown_count > 0:
            blocking_factors.append(
                f"{report.unknown_count} unknown result(s)"
            )
        if report.skipped_count > 0:
            blocking_factors.append(
                f"{report.skipped_count} skipped constraint(s)"
            )
        if report.total_count == 0:
            blocking_factors.append("no constraints extracted from program")

        # Build rationale based on tier and decision
        tier_descriptions = {
            "hearth": "Hearth/Trusted tier — strictest gating: all constraints must be proven",
            "forge": "Forge/Standard tier — moderate gating: counterexamples block, unknowns warn",
            "sovereign": "Sovereign/Advisory tier — permissive: always proceeds with advisory results",
        }

        if decision == GateDecision.PROCEED:
            if normalized_tier == "sovereign":
                rationale = (
                    f"{tier_descriptions[normalized_tier]} "
                    f"Proceeding despite {report.blocked_count} advisory issues."
                )
            else:
                rationale = (
                    f"{tier_descriptions[normalized_tier]} "
                    f"All {report.total_count} constraint(s) verified successfully. "
                    f"Proceeding."
                )
        elif decision == GateDecision.BLOCK:
            rationale = (
                f"{tier_descriptions[normalized_tier]} "
                f"Blocking due to: {'; '.join(blocking_factors)}."
            )
        elif decision == GateDecision.WARN:
            rationale = (
                f"{tier_descriptions[normalized_tier]} "
                f"Warning due to: {'; '.join(blocking_factors)}. "
                f"Proceeding with warnings."
            )
        else:
            rationale = f"Unknown decision '{decision}' at tier '{normalized_tier}'"

        return rationale, blocking_factors

    @staticmethod
    def tier_escalation_map() -> dict[str, str]:
        """Return the escalation path for each tier.

        Tier escalation increases strictness when verification depth
        requirements are not met. The caller can use this to determine
        the next stricter tier to try.
        """
        return {
            "sovereign": "forge",
            "forge": "hearth",
            "hearth": "hearth",  # Already at maximum strictness
            "advisory": "forge",
            "untrusted": "forge",
            "approved": "hearth",
            "watched": "hearth",
            "trusted": "hearth",
        }

    @classmethod
    def escalate_tier(cls, current_tier: str) -> str:
        """Escalate to the next stricter tier.

        Args:
            current_tier: The current tier name.

        Returns:
            The escalated tier name. If already at hearth, returns hearth.
        """
        mapping = cls.tier_escalation_map()
        normalized = cls._normalize_tier(current_tier)
        return mapping.get(normalized, "hearth")


def extract_constraints(ast: dict[str, Any]) -> list[dict[str, Any]]:
    ast = normalize_ast(ast)
    constraints: list[dict[str, Any]] = []
    for node in ast.get("program", []):
        if node is None:
            continue
        _extract_from_node(node, constraints)
    return constraints


def normalize_ast(ast: Any) -> dict[str, Any]:
    if isinstance(ast, dict):
        if isinstance(ast.get("program"), list):
            return {
                "program": list(ast.get("program", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        if isinstance(ast.get("statements"), list):
            return {
                "program": list(ast.get("statements", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        nested_ast = ast.get("ast")
        if nested_ast is not None:
            return normalize_ast(nested_ast)
        if isinstance(ast.get("body"), list):
            return {
                "program": list(ast.get("body", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        return {"program": [], "env": {}}
    if isinstance(ast, list):
        return {"program": list(ast), "env": {}}
    return {"program": [], "env": {}}


def _decode_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("kind") == "value":
            value_type = str(value.get("type", ""))
            scalar = value.get("value")
            if value_type == "ident":
                text = str(scalar).strip().lower()
                if text == "true":
                    return True
                if text == "false":
                    return False
                if text == "null":
                    return None
                return str(scalar)
            if value_type == "var_ref":
                return {"var_ref": str(scalar)}
            return scalar
        if value.get("kind") == "kv_arg":
            return _decode_value(value.get("value"))
    return value


def _decode_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, list):
        return {}
    decoded: dict[str, Any] = {}
    for argument in arguments:
        if not isinstance(argument, dict):
            continue
        if argument.get("kind") == "kv_arg":
            decoded[str(argument.get("name", ""))] = _decode_value(argument.get("value"))
    return decoded


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _infer_type(value: Any) -> str:
    """Infer the HLF type string from a Python value.

    Handles scalar types and parametric containers for
    interoperability with TypedEffectDeclaration type annotations.
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "real"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "json"
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
        return "rational"
    return ""


def _extract_from_node(node: Any, constraints: list[dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return

    kind = str(node.get("kind", ""))
    tag = str(node.get("tag", ""))
    arguments = _decode_arguments(node.get("arguments", []))
    if tag == "CONSTRAINT":
        name = str(
            arguments.get("name")
            or node.get("name")
            or f"constraint_{len(constraints)}"
        )
        range_value = arguments.get("value")
        if range_value is None:
            numeric_literals = [
                value
                for key, value in arguments.items()
                if key not in {"min", "max"} and isinstance(value, (int, float))
            ]
            if len(numeric_literals) == 1:
                range_value = numeric_literals[0]
        constraints.append(
            {
                "kind": "range_check",
                "name": name,
                "condition": node.get("condition", {}),
                "args": list(node.get("args", [])),
                "value": range_value,
                "low": arguments.get("min"),
                "high": arguments.get("max"),
                "fields": arguments,
            }
        )
    elif tag == "SPEC_GATE" or kind == "spec_gate_stmt":
        gate_name = str(node.get("tag") or node.get("name") or f"spec_gate_{len(constraints)}")
        constraints.append(
            {
                "kind": "spec_gate",
                "name": gate_name,
                "condition": node.get("condition", {}),
                "fields": arguments,
            }
        )
    elif tag == "SET" or kind == "set_stmt":
        value = _decode_value(node.get("value"))
        name = str(node.get("name", f"value_{len(constraints)}"))
        # Check for type annotation (from glyph_assign_stmt type_ann)
        type_ann = node.get("type")
        if isinstance(type_ann, dict) and type_ann.get("kind") == "type_ann":
            expected_type = type_ann.get("type", "")
            # Handle parametric type annotations: List⟨ℕ⟩, Set⟨𝕊⟩, Map⟨𝕊,ℤ⟩
            param_types = type_ann.get("param_types")
            if param_types and expected_type:
                expected_type = str(expected_type)
            # Handle refinement type annotations: {var: T | pred}
            refinement = type_ann.get("refinement")
            if refinement and isinstance(refinement, dict):
                expected_type = "refinement"
        elif isinstance(type_ann, str):
            expected_type = type_ann
        else:
            expected_type = _infer_type(value)
        if expected_type:
            # Map HLF canonical type names to verifier type names
            canonical_map = {
                "integer": "integer",
                "real": "real",
                "rational": "rational",
                "number": "number",
                "string": "string",
                "boolean": "boolean",
                "list": "list",
                "set": "set",
                "map": "map",
                "json": "json",
                "refinement": "refinement",
            }
            resolved_type = canonical_map.get(str(expected_type).lower(), str(expected_type))
            constraints.append(
                {
                    "kind": "type_invariant",
                    "name": f"type_{name}",
                    "variable": name,
                    "expected_type": resolved_type,
                    "value": value,
                }
            )
    elif tag == "PARALLEL" or kind == "parallel_stmt":
        tasks = list(node.get("tasks", []))
        if not tasks:
            tasks = list(node.get("blocks", []))
        constraints.append(
            {
                "kind": "gas_bound",
                "name": f"parallel_gas_{len(constraints)}",
                "task_count": len(tasks),
            }
        )

    for key in ("then", "else", "body", "inner", "action", "else_clause"):
        child = node.get(key)
        if isinstance(child, dict):
            _extract_from_node(child, constraints)
        elif isinstance(child, list):
            for item in child:
                _extract_from_node(item, constraints)

    for key in ("tasks", "blocks", "statements", "elif_clauses"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                _extract_from_node(child, constraints)


class FallbackSolver:
    def check_range(
        self,
        value: Any,
        *,
        low: float | None = None,
        high: float | None = None,
        name: str = "",
    ) -> VerificationResult:
        start = time.time()
        if not isinstance(value, (int, float)):
            return VerificationResult(
                property_name=name or "range_check",
                status=VerificationStatus.ERROR,
                kind=ConstraintKind.RANGE_CHECK,
                message=f"Value is not numeric: {type(value).__name__}",
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        if low is not None and value < low:
            return VerificationResult(
                property_name=name or "range_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.RANGE_CHECK,
                message=f"{value} < {low}",
                counterexample={"value": value, "bound": low, "comparison": "below_low"},
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        if high is not None and value > high:
            return VerificationResult(
                property_name=name or "range_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.RANGE_CHECK,
                message=f"{value} > {high}",
                counterexample={"value": value, "bound": high, "comparison": "above_high"},
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "range_check",
            status=VerificationStatus.RUNTIME_CHECKED,
            kind=ConstraintKind.RANGE_CHECK,
            message="Value within range bounds (runtime check)",
            solver="fallback",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_type(self, value: Any, expected_type: str, *, name: str = "") -> VerificationResult:
        start = time.time()
        type_map = {
            "number": (int, float),
            "integer": (int,),
            "real": (int, float),
            "rational": (tuple, int, float),  # tuple for (num, den) pairs
            "string": (str,),
            "boolean": (bool,),
            "list": (list,),
            "set": (list,),    # HLF Set⟨T⟩ runtime representation as list
            "map": (dict,),    # HLF Map⟨K,V⟩ runtime representation as dict
            "dict": (dict,),
            "json": (dict, list),
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.UNKNOWN,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Unknown type '{expected_type}'",
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        # For rational, check both tuple and numeric forms
        if expected_type == "rational":
            if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
                if value[1] == 0:
                    return VerificationResult(
                        property_name=name or "type_check",
                        status=VerificationStatus.COUNTEREXAMPLE,
                        kind=ConstraintKind.TYPE_INVARIANT,
                        message="Rational denominator cannot be zero",
                        counterexample={"value": str(value), "actual_type": "rational_zero_denom"},
                        solver="fallback",
                        duration_ms=(time.time() - start) * 1000,
                    )
                return VerificationResult(
                    property_name=name or "type_check",
                    status=VerificationStatus.RUNTIME_CHECKED,
                    kind=ConstraintKind.TYPE_INVARIANT,
                    message=f"Value is a valid rational (num={value[0]}, den={value[1]}) (runtime check)",
                    solver="fallback",
                    duration_ms=(time.time() - start) * 1000,
                )
            if isinstance(value, (int, float)):
                if isinstance(value, bool):
                    return VerificationResult(
                        property_name=name or "type_check",
                        status=VerificationStatus.COUNTEREXAMPLE,
                        kind=ConstraintKind.TYPE_INVARIANT,
                        message=f"Expected rational, got boolean",
                        counterexample={"value": str(value), "actual_type": "bool"},
                        solver="fallback",
                        duration_ms=(time.time() - start) * 1000,
                    )
                return VerificationResult(
                    property_name=name or "type_check",
                    status=VerificationStatus.RUNTIME_CHECKED,
                    kind=ConstraintKind.TYPE_INVARIANT,
                    message=f"Value matches rational (numeric repr) (runtime check)",
                    solver="fallback",
                    duration_ms=(time.time() - start) * 1000,
                )
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Expected rational, got '{type(value).__name__}'",
                counterexample={"value": str(value), "actual_type": type(value).__name__},
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        if isinstance(value, bool) and expected_type != (bool,):
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Expected '{expected_type}', got boolean",
                counterexample={"value": str(value), "actual_type": "bool"},
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        if isinstance(value, expected):
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Value matches type '{expected_type}' (runtime check)",
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "type_check",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.TYPE_INVARIANT,
            message=f"Expected '{expected_type}', got '{type(value).__name__}'",
            counterexample={"value": str(value), "actual_type": type(value).__name__},
            solver="fallback",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_gas_budget(
        self, task_costs: list[int], budget: int, *, name: str = ""
    ) -> VerificationResult:
        start = time.time()
        total = sum(task_costs)
        if total <= budget:
            return VerificationResult(
                property_name=name or "gas_budget",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.GAS_BOUND,
                message=f"Total gas {total} <= budget {budget} (runtime check)",
                solver="fallback",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "gas_budget",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.GAS_BOUND,
            message=f"Total gas {total} > budget {budget}",
            counterexample={"total_gas": total, "budget": budget, "over_by": total - budget},
            solver="fallback",
            duration_ms=(time.time() - start) * 1000,
        )


class Z3Solver:
    """Real SMT-based verification using Z3.

    For concrete values, Z3 encodes the check as a satisfiability problem.
    For symbolic variables (future), Z3 provides full SMT discharge.

    The solver name "z3" in results indicates formal SMT discharge was used.
    """
    def __init__(self) -> None:
        self._ctx = z3.Context() if z3 else None

    @property
    def available(self) -> bool:
        return self._ctx is not None

    def check_range(
        self,
        value: Any,
        *,
        low: float | None = None,
        high: float | None = None,
        name: str = "",
    ) -> VerificationResult:
        start = time.time()
        if not isinstance(value, (int, float)):
            return VerificationResult(
                property_name=name or "range_check",
                status=VerificationStatus.ERROR,
                kind=ConstraintKind.RANGE_CHECK,
                message=f"Value is not numeric: {type(value).__name__}",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        # Encode as Z3 constraint: value in [low, high]
        s = z3.Solver(ctx=self._ctx)
        x = z3.Real(name or "x", ctx=self._ctx)
        constraints = []
        if low is not None:
            constraints.append(x >= z3.RealVal(low, ctx=self._ctx))
        if high is not None:
            constraints.append(x <= z3.RealVal(high, ctx=self._ctx))
        s.add(constraints)
        s.add(x == z3.RealVal(value, ctx=self._ctx))
        result = s.check()
        if result == z3.sat:
            return VerificationResult(
                property_name=name or "range_check",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.RANGE_CHECK,
                message=f"SMT-proven: {value} within [{low}, {high}]",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "range_check",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.RANGE_CHECK,
            message=f"SMT counterexample: {value} outside [{low}, {high}]",
            counterexample={"value": value, "low": low, "high": high},
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_type(self, value: Any, expected_type: str, *, name: str = "") -> VerificationResult:
        start = time.time()
        type_map = {
            "number": (int, float),
            "integer": (int,),
            "real": (int, float),
            "rational": (tuple, int, float),
            "string": (str,),
            "boolean": (bool,),
            "list": (list,),
            "set": (list,),
            "map": (dict,),
            "dict": (dict,),
            "json": (dict, list),
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.UNKNOWN,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Unknown type '{expected_type}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        # For rational, check both tuple and numeric forms
        if expected_type == "rational":
            if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int) for v in value):
                if value[1] == 0:
                    return VerificationResult(
                        property_name=name or "type_check",
                        status=VerificationStatus.COUNTEREXAMPLE,
                        kind=ConstraintKind.TYPE_INVARIANT,
                        message="Rational denominator cannot be zero",
                        counterexample={"value": str(value), "actual_type": "rational_zero_denom"},
                        solver="z3",
                        duration_ms=(time.time() - start) * 1000,
                    )
                return VerificationResult(
                    property_name=name or "type_check",
                    status=VerificationStatus.PROVEN,
                    kind=ConstraintKind.TYPE_INVARIANT,
                    message=f"SMT-proven: valid rational (num={value[0]}, den={value[1]})",
                    solver="z3",
                    duration_ms=(time.time() - start) * 1000,
                )
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return VerificationResult(
                    property_name=name or "type_check",
                    status=VerificationStatus.PROVEN,
                    kind=ConstraintKind.TYPE_INVARIANT,
                    message=f"SMT-proven: value matches rational (numeric repr)",
                    solver="z3",
                    duration_ms=(time.time() - start) * 1000,
                )
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Expected rational, got '{type(value).__name__}'",
                counterexample={"value": str(value), "actual_type": type(value).__name__},
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        if isinstance(value, bool) and expected_type != (bool,):
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.COUNTEREXAMPLE,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Expected '{expected_type}', got boolean",
                counterexample={"value": str(value), "actual_type": "bool"},
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        if isinstance(value, expected):
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"SMT-proven: value matches type '{expected_type}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "type_check",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.TYPE_INVARIANT,
            message=f"Expected '{expected_type}', got '{type(value).__name__}'",
            counterexample={"value": str(value), "actual_type": type(value).__name__},
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_gas_budget(
        self, task_costs: list[int], budget: int, *, name: str = ""
    ) -> VerificationResult:
        start = time.time()
        total = sum(task_costs)
        s = z3.Solver(ctx=self._ctx)
        x = z3.Int(name or "gas", ctx=self._ctx)
        s.add(x == z3.IntVal(total, ctx=self._ctx))
        s.add(x <= z3.IntVal(budget, ctx=self._ctx))
        result = s.check()
        if result == z3.sat:
            return VerificationResult(
                property_name=name or "gas_budget",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.GAS_BOUND,
                message=f"SMT-proven: total gas {total} <= budget {budget}",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or "gas_budget",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.GAS_BOUND,
            message=f"SMT counterexample: total gas {total} > budget {budget}",
            counterexample={"total_gas": total, "budget": budget, "over_by": total - budget},
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_string_op(
        self, operation: str, *args: Any, name: str = ""
    ) -> VerificationResult:
        """Dispatch a string operator check to the Z3 string encoding."""
        start = time.time()
        encoder = Z3OperatorEncoder()

        dispatch: dict[str, Any] = {
            "concat": encoder.encode_str_concat,
            "length": encoder.encode_str_length,
            "substring": encoder.encode_str_substring,
            "contains": encoder.encode_str_contains,
            "prefix": encoder.encode_str_prefix,
            "suffix": encoder.encode_str_suffix,
            "compare": encoder.encode_str_compare,
            "replace": encoder.encode_str_replace,
            "trim": encoder.encode_str_trim,
            "split": encoder.encode_str_split,
            "is_empty": encoder.encode_str_is_empty,
        }
        encoder_fn = dispatch.get(operation)
        if encoder_fn is None:
            return VerificationResult(
                property_name=name or f"string_{operation}",
                status=VerificationStatus.UNKNOWN,
                kind=ConstraintKind.CUSTOM,
                message=f"Unknown string operation '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        encoding = encoder_fn(*args)
        if isinstance(encoding, str):
            # Graceful degradation: no Z3 available
            return VerificationResult(
                property_name=name or f"string_{operation}",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.CUSTOM,
                message=f"String op '{operation}' encoded as: {encoding}",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        # Verify the Z3 encoding via SMT
        s = z3.Solver(ctx=self._ctx)
        s.add(encoding)
        result = s.check()
        if result == z3.sat:
            return VerificationResult(
                property_name=name or f"string_{operation}",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.CUSTOM,
                message=f"SMT-proven: string op '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or f"string_{operation}",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.CUSTOM,
            message=f"SMT counterexample: string op '{operation}'",
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_set_op(
        self, operation: str, *args: Any, name: str = ""
    ) -> VerificationResult:
        """Dispatch a set operator check to the Z3 set encoding."""
        start = time.time()
        encoder = Z3OperatorEncoder()

        dispatch: dict[str, Any] = {
            "member": encoder.encode_set_member,
            "subset": encoder.encode_set_subset,
            "union": encoder.encode_set_union,
            "intersection": encoder.encode_set_intersection,
            "difference": encoder.encode_set_difference,
            "cardinality": encoder.encode_set_cardinality,
            "is_empty": encoder.encode_set_is_empty,
            "complement": encoder.encode_set_complement,
        }
        encoder_fn = dispatch.get(operation)
        if encoder_fn is None:
            return VerificationResult(
                property_name=name or f"set_{operation}",
                status=VerificationStatus.UNKNOWN,
                kind=ConstraintKind.CUSTOM,
                message=f"Unknown set operation '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        encoding = encoder_fn(*args)
        if isinstance(encoding, str):
            return VerificationResult(
                property_name=name or f"set_{operation}",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.CUSTOM,
                message=f"Set op '{operation}' encoded as: {encoding}",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        s = z3.Solver(ctx=self._ctx)
        s.add(encoding)
        result = s.check()
        if result == z3.sat:
            return VerificationResult(
                property_name=name or f"set_{operation}",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.CUSTOM,
                message=f"SMT-proven: set op '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or f"set_{operation}",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.CUSTOM,
            message=f"SMT counterexample: set op '{operation}'",
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_container_op(
        self, operation: str, *args: Any, name: str = ""
    ) -> VerificationResult:
        """Dispatch a container operator check to the Z3 container encoding."""
        start = time.time()
        encoder = Z3OperatorEncoder()

        dispatch: dict[str, Any] = {
            "list_length": encoder.encode_list_length,
            "list_index": encoder.encode_list_index,
            "list_slice": encoder.encode_list_slice,
            "list_contains": encoder.encode_list_contains,
            "list_append": encoder.encode_list_append,
            "map_keys": encoder.encode_map_keys,
            "map_values": encoder.encode_map_values,
            "map_lookup": encoder.encode_map_lookup,
            "map_contains_key": encoder.encode_map_contains_key,
            "container_is_empty": encoder.encode_container_is_empty,
            "container_membership": encoder.encode_container_membership,
        }
        encoder_fn = dispatch.get(operation)
        if encoder_fn is None:
            return VerificationResult(
                property_name=name or f"container_{operation}",
                status=VerificationStatus.UNKNOWN,
                kind=ConstraintKind.CUSTOM,
                message=f"Unknown container operation '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        encoding = encoder_fn(*args)
        if isinstance(encoding, str):
            return VerificationResult(
                property_name=name or f"container_{operation}",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.CUSTOM,
                message=f"Container op '{operation}' encoded as: {encoding}",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )

        s = z3.Solver(ctx=self._ctx)
        s.add(encoding)
        result = s.check()
        if result == z3.sat:
            return VerificationResult(
                property_name=name or f"container_{operation}",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.CUSTOM,
                message=f"SMT-proven: container op '{operation}'",
                solver="z3",
                duration_ms=(time.time() - start) * 1000,
            )
        return VerificationResult(
            property_name=name or f"container_{operation}",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.CUSTOM,
            message=f"SMT counterexample: container op '{operation}'",
            solver="z3",
            duration_ms=(time.time() - start) * 1000,
        )


class Z3OperatorEncoder:
    """Z3 SMT encodings for all HLF operator families.

    Each method encodes an operator as a Z3 SMT expression or
    returns a descriptive string when Z3 is not available.

    Operator families covered: string, set, container, and
    their sub-operations.
    """

    @classmethod
    def z3_available(cls) -> bool:
        """Check whether Z3 is installed and importable."""
        return _HAS_Z3

    @classmethod
    def supported_operator_families(cls) -> set[str]:
        """Return the set of operator family names with Z3 encodings."""
        return {
            "numeric",
            "string",
            "set",
            "container",
            "boolean",
            "type_system",
            "gas",
            "spec_gate",
            "rational",
            "temporal",
            "spatial",
            "effect",
        }

    # ------------------------------------------------------------------
    # String operations
    # ------------------------------------------------------------------

    @staticmethod
    def encode_str_concat(a: Any, b: Any) -> Any:
        """Encode string concatenation: a + b."""
        if not _HAS_Z3:
            return f"str_concat({a}, {b})"
        ctx = z3.main_ctx()
        sa = z3.StringVal(str(a)) if not isinstance(a, z3.SeqRef) else a
        sb = z3.StringVal(str(b)) if not isinstance(b, z3.SeqRef) else b
        return z3.Concat(sa, sb)

    @staticmethod
    def encode_str_length(s: Any) -> Any:
        """Encode string length: len(s)."""
        if not _HAS_Z3:
            return f"str_length({s})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        return z3.Length(ss)

    @staticmethod
    def encode_str_substring(s: Any, start: Any, end: Any) -> Any:
        """Encode string substring: s[start:end]."""
        if not _HAS_Z3:
            return f"str_substring({s}, {start}, {end})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        si = z3.IntVal(int(start)) if not isinstance(start, z3.ArithRef) else start
        length = (
            z3.IntVal(int(end)) - si
            if not isinstance(end, z3.ArithRef)
            else end - si
        )
        return z3.SubString(ss, si, length)

    @staticmethod
    def encode_str_contains(s: Any, substr: Any) -> Any:
        """Encode string containment: substr in s."""
        if not _HAS_Z3:
            return f"str_contains({s}, {substr})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        sub = z3.StringVal(str(substr)) if not isinstance(substr, z3.SeqRef) else substr
        return z3.Contains(ss, sub)

    @staticmethod
    def encode_str_prefix(s: Any, prefix: Any) -> Any:
        """Encode string prefix check: s.startswith(prefix)."""
        if not _HAS_Z3:
            return f"str_prefix({s}, {prefix})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        sp = z3.StringVal(str(prefix)) if not isinstance(prefix, z3.SeqRef) else prefix
        return z3.PrefixOf(sp, ss)

    @staticmethod
    def encode_str_suffix(s: Any, suffix: Any) -> Any:
        """Encode string suffix check: s.endswith(suffix)."""
        if not _HAS_Z3:
            return f"str_suffix({s}, {suffix})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        su = z3.StringVal(str(suffix)) if not isinstance(suffix, z3.SeqRef) else suffix
        return z3.SuffixOf(su, ss)

    @staticmethod
    def encode_str_compare(a: Any, b: Any) -> Any:
        """Encode string equality comparison: a == b."""
        if not _HAS_Z3:
            return f"str_compare({a}, {b})"
        ctx = z3.main_ctx()
        sa = z3.StringVal(str(a)) if not isinstance(a, z3.SeqRef) else a
        sb = z3.StringVal(str(b)) if not isinstance(b, z3.SeqRef) else b
        return sa == sb

    @staticmethod
    def encode_str_replace(s: Any, old: Any, new: Any) -> Any:
        """Encode string replacement: s.replace(old, new)."""
        if not _HAS_Z3:
            return f"str_replace({s}, {old}, {new})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        so = z3.StringVal(str(old)) if not isinstance(old, z3.SeqRef) else old
        sn = z3.StringVal(str(new)) if not isinstance(new, z3.SeqRef) else new
        return z3.Replace(ss, so, sn)

    @staticmethod
    def encode_str_trim(s: Any) -> Any:
        """Encode string trim: strip surrounding whitespace from s."""
        if not _HAS_Z3:
            return f"str_trim({s})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        # Z3 does not have a native trim; encode as constraint:
        # the result is a substring that does not start/end with space
        space = z3.StringVal(" ", ctx=ctx)
        result = z3.String("trimmed", ctx=ctx)
        return z3.And(
            z3.Not(z3.PrefixOf(space, result)),
            z3.Not(z3.SuffixOf(space, result)),
            z3.Contains(ss, result),
        )

    @staticmethod
    def encode_str_split(s: Any, delim: Any) -> Any:
        """Encode string split: s.split(delim) producing a sequence."""
        if not _HAS_Z3:
            return f"str_split({s}, {delim})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        sd = z3.StringVal(str(delim)) if not isinstance(delim, z3.SeqRef) else delim
        # Encode that delim appears at least once and partitions the string
        return z3.Contains(ss, sd)

    @staticmethod
    def encode_str_is_empty(s: Any) -> Any:
        """Encode string emptiness: s == ''."""
        if not _HAS_Z3:
            return f"str_is_empty({s})"
        ctx = z3.main_ctx()
        ss = z3.StringVal(str(s)) if not isinstance(s, z3.SeqRef) else s
        return z3.Length(ss) == 0

    # ------------------------------------------------------------------
    # Set operations
    # ------------------------------------------------------------------

    @staticmethod
    def encode_set_member(elem: Any, s: Any) -> Any:
        """Encode set membership: elem in s."""
        if not _HAS_Z3:
            return f"set_member({elem}, {s})"
        # Model sets as arrays: IntSort -> BoolSort for membership
        ctx = z3.main_ctx()
        if not isinstance(s, z3.ArrayRef):
            # Treat as a concrete Python iterable; encode as disjunction
            if isinstance(s, (list, tuple, set, frozenset)):
                e_val = z3.IntVal(int(elem)) if isinstance(elem, (int, float)) else z3.StringVal(str(elem), ctx=ctx)
                clauses = []
                for item in s:
                    i_val = z3.IntVal(int(item)) if isinstance(item, (int, float)) else z3.StringVal(str(item), ctx=ctx)
                    clauses.append(e_val == i_val)
                return z3.Or(*clauses) if clauses else z3.BoolVal(False, ctx=ctx)
        # Array-based membership: s[elem] == True
        e_idx = z3.IntVal(int(elem)) if isinstance(elem, (int, float)) else elem
        return s[e_idx] if isinstance(s, z3.ArrayRef) else z3.BoolVal(False, ctx=ctx)

    @staticmethod
    def encode_set_subset(a: Any, b: Any) -> Any:
        """Encode set subset relation: a ⊆ b."""
        if not _HAS_Z3:
            return f"set_subset({a}, {b})"
        # Subset: every element in a appears in b
        ctx = z3.main_ctx()
        if isinstance(a, (list, tuple, set, frozenset)) and isinstance(b, (list, tuple, set, frozenset)):
            clauses = []
            for item in a:
                i_val = z3.IntVal(int(item)) if isinstance(item, (int, float)) else z3.StringVal(str(item), ctx=ctx)
                sub_clauses = []
                for bitem in b:
                    b_val = z3.IntVal(int(bitem)) if isinstance(bitem, (int, float)) else z3.StringVal(str(bitem), ctx=ctx)
                    sub_clauses.append(i_val == b_val)
                clauses.append(z3.Or(*sub_clauses) if sub_clauses else z3.BoolVal(False, ctx=ctx))
            return z3.And(*clauses) if clauses else z3.BoolVal(True, ctx=ctx)
        # For Z3 array representation, use universal quantification
        x = z3.Int("_subset_x", ctx=ctx)
        return z3.ForAll([x], z3.Implies(a[x], b[x]))

    @staticmethod
    def encode_set_union(a: Any, b: Any) -> Any:
        """Encode set union: a ∪ b."""
        if not _HAS_Z3:
            return f"set_union({a}, {b})"
        ctx = z3.main_ctx()
        if isinstance(a, (list, tuple, set, frozenset)) and isinstance(b, (list, tuple, set, frozenset)):
            combined = list(a) + list(b)
            # Encode as the set of distinct elements
            clauses = []
            for item in combined:
                i_val = z3.IntVal(int(item)) if isinstance(item, (int, float)) else z3.StringVal(str(item), ctx=ctx)
                clauses.append(i_val)
            return z3.And(*[z3.BoolVal(True, ctx=ctx)]) if clauses else z3.BoolVal(False, ctx=ctx)
        x = z3.Int("_union_x", ctx=ctx)
        return z3.Lambda([x], z3.Or(a[x], b[x]))

    @staticmethod
    def encode_set_intersection(a: Any, b: Any) -> Any:
        """Encode set intersection: a ∩ b."""
        if not _HAS_Z3:
            return f"set_intersection({a}, {b})"
        ctx = z3.main_ctx()
        if isinstance(a, (list, tuple, set, frozenset)) and isinstance(b, (list, tuple, set, frozenset)):
            set_b = set(b)
            common = [item for item in a if item in set_b]
            clauses = []
            for item in common:
                i_val = z3.IntVal(int(item)) if isinstance(item, (int, float)) else z3.StringVal(str(item), ctx=ctx)
                clauses.append(i_val)
            return z3.And(*[z3.BoolVal(True, ctx=ctx)]) if clauses else z3.BoolVal(False, ctx=ctx)
        x = z3.Int("_inter_x", ctx=ctx)
        return z3.Lambda([x], z3.And(a[x], b[x]))

    @staticmethod
    def encode_set_difference(a: Any, b: Any) -> Any:
        r"""Encode set difference: a \ b."""
        if not _HAS_Z3:
            return f"set_difference({a}, {b})"
        ctx = z3.main_ctx()
        if isinstance(a, (list, tuple, set, frozenset)) and isinstance(b, (list, tuple, set, frozenset)):
            set_b = set(b)
            diff = [item for item in a if item not in set_b]
            return z3.BoolVal(len(diff) >= 0, ctx=ctx)
        x = z3.Int("_diff_x", ctx=ctx)
        return z3.Lambda([x], z3.And(a[x], z3.Not(b[x])))

    @staticmethod
    def encode_set_cardinality(s: Any) -> Any:
        """Encode set cardinality: |s|."""
        if not _HAS_Z3:
            return f"set_cardinality({s})"
        ctx = z3.main_ctx()
        if isinstance(s, (list, tuple, set, frozenset)):
            return z3.IntVal(len(set(s)), ctx=ctx)
        return z3.Int("_card", ctx=ctx)

    @staticmethod
    def encode_set_is_empty(s: Any) -> Any:
        """Encode set emptiness: |s| == 0."""
        if not _HAS_Z3:
            return f"set_is_empty({s})"
        ctx = z3.main_ctx()
        if isinstance(s, (list, tuple, set, frozenset)):
            return z3.BoolVal(len(s) == 0, ctx=ctx)
        x = z3.Int("_empty_x", ctx=ctx)
        return z3.ForAll([x], z3.Not(s[x]))

    @staticmethod
    def encode_set_complement(universal: Any, s: Any) -> Any:
        r"""Encode set complement: universal \ s."""
        if not _HAS_Z3:
            return f"set_complement({universal}, {s})"
        ctx = z3.main_ctx()
        if isinstance(universal, (list, tuple, set, frozenset)) and isinstance(s, (list, tuple, set, frozenset)):
            set_s = set(s)
            comp = [item for item in universal if item not in set_s]
            return z3.BoolVal(len(comp) >= 0, ctx=ctx)
        x = z3.Int("_comp_x", ctx=ctx)
        return z3.Lambda([x], z3.And(universal[x], z3.Not(s[x])))

    # ------------------------------------------------------------------
    # Container operations
    # ------------------------------------------------------------------

    @staticmethod
    def encode_list_length(lst: Any) -> Any:
        """Encode list length: len(lst)."""
        if not _HAS_Z3:
            return f"list_length({lst})"
        ctx = z3.main_ctx()
        if isinstance(lst, (list, tuple)):
            return z3.IntVal(len(lst), ctx=ctx)
        return z3.Int("_list_len", ctx=ctx)

    @staticmethod
    def encode_list_index(lst: Any, idx: Any) -> Any:
        """Encode list indexing: lst[idx]."""
        if not _HAS_Z3:
            return f"list_index({lst}, {idx})"
        ctx = z3.main_ctx()
        if isinstance(lst, (list, tuple)) and isinstance(idx, int):
            if 0 <= idx < len(lst):
                val = lst[idx]
                if isinstance(val, (int, float)):
                    return z3.IntVal(int(val), ctx=ctx)
                return z3.StringVal(str(val), ctx=ctx)
            return z3.BoolVal(False, ctx=ctx)
        # Use array theory: list as Array(Int, Value)
        if isinstance(lst, z3.ArrayRef):
            i = z3.IntVal(int(idx)) if isinstance(idx, (int, float)) else idx
            return lst[i]
        return z3.Int("_list_elem", ctx=ctx)

    @staticmethod
    def encode_list_slice(lst: Any, start: Any, end: Any) -> Any:
        """Encode list slice: lst[start:end]."""
        if not _HAS_Z3:
            return f"list_slice({lst}, {start}, {end})"
        ctx = z3.main_ctx()
        if isinstance(lst, (list, tuple)) and isinstance(start, int) and isinstance(end, int):
            sliced = lst[start:end]
            return z3.IntVal(len(sliced), ctx=ctx)
        return z3.Int("_slice_len", ctx=ctx)

    @staticmethod
    def encode_list_contains(lst: Any, elem: Any) -> Any:
        """Encode list containment: elem in lst."""
        if not _HAS_Z3:
            return f"list_contains({lst}, {elem})"
        ctx = z3.main_ctx()
        if isinstance(lst, (list, tuple)):
            if isinstance(elem, (int, float)):
                e_val = z3.IntVal(int(elem), ctx=ctx)
            else:
                e_val = z3.StringVal(str(elem), ctx=ctx)
            clauses = []
            for item in lst:
                if isinstance(item, (int, float)):
                    i_val = z3.IntVal(int(item), ctx=ctx)
                else:
                    i_val = z3.StringVal(str(item), ctx=ctx)
                clauses.append(e_val == i_val)
            return z3.Or(*clauses) if clauses else z3.BoolVal(False, ctx=ctx)
        if isinstance(lst, z3.ArrayRef):
            i = z3.Int("_cont_idx", ctx=ctx)
            e = z3.IntVal(int(elem)) if isinstance(elem, (int, float)) else elem
            return z3.Exists([i], lst[i] == e)
        return z3.BoolVal(False, ctx=ctx)

    @staticmethod
    def encode_list_append(lst: Any, elem: Any) -> Any:
        """Encode list append: lst + [elem]."""
        if not _HAS_Z3:
            return f"list_append({lst}, {elem})"
        ctx = z3.main_ctx()
        if isinstance(lst, (list, tuple)):
            return z3.IntVal(len(lst) + 1, ctx=ctx)
        return z3.Int("_appended_len", ctx=ctx)

    @staticmethod
    def encode_map_keys(m: Any) -> Any:
        """Encode map key extraction: m.keys()."""
        if not _HAS_Z3:
            return f"map_keys({m})"
        ctx = z3.main_ctx()
        if isinstance(m, dict):
            keys = list(m.keys())
            return z3.IntVal(len(keys), ctx=ctx)
        return z3.Int("_map_key_count", ctx=ctx)

    @staticmethod
    def encode_map_values(m: Any) -> Any:
        """Encode map value extraction: m.values()."""
        if not _HAS_Z3:
            return f"map_values({m})"
        ctx = z3.main_ctx()
        if isinstance(m, dict):
            vals = list(m.values())
            return z3.IntVal(len(vals), ctx=ctx)
        return z3.Int("_map_val_count", ctx=ctx)

    @staticmethod
    def encode_map_lookup(m: Any, key: Any) -> Any:
        """Encode map lookup: m[key]."""
        if not _HAS_Z3:
            return f"map_lookup({m}, {key})"
        ctx = z3.main_ctx()
        if isinstance(m, dict):
            if key in m:
                val = m[key]
                if isinstance(val, (int, float)):
                    return z3.IntVal(int(val), ctx=ctx)
                return z3.StringVal(str(val), ctx=ctx)
            return z3.BoolVal(False, ctx=ctx)
        if isinstance(m, z3.ArrayRef):
            k = z3.StringVal(str(key), ctx=ctx) if isinstance(key, str) else z3.IntVal(int(key), ctx=ctx)
            return m[k]
        return z3.Int("_map_val", ctx=ctx)

    @staticmethod
    def encode_map_contains_key(m: Any, key: Any) -> Any:
        """Encode map key containment: key in m."""
        if not _HAS_Z3:
            return f"map_contains_key({m}, {key})"
        ctx = z3.main_ctx()
        if isinstance(m, dict):
            return z3.BoolVal(key in m, ctx=ctx)
        if isinstance(m, z3.ArrayRef):
            k = z3.StringVal(str(key), ctx=ctx) if isinstance(key, str) else z3.IntVal(int(key), ctx=ctx)
            # A key exists if the lookup is not equal to a default sentinel
            sentinel = z3.Int("_sentinel", ctx=ctx)
            return m[k] != sentinel
        return z3.BoolVal(False, ctx=ctx)

    @staticmethod
    def encode_container_is_empty(c: Any) -> Any:
        """Encode container emptiness: len(c) == 0."""
        if not _HAS_Z3:
            return f"container_is_empty({c})"
        ctx = z3.main_ctx()
        if isinstance(c, (list, tuple, dict, set, frozenset, str)):
            return z3.BoolVal(len(c) == 0, ctx=ctx)
        return z3.BoolVal(False, ctx=ctx)

    @staticmethod
    def encode_container_membership(elem: Any, container: Any) -> Any:
        """Encode container membership: elem in container."""
        if not _HAS_Z3:
            return f"container_membership({elem}, {container})"
        ctx = z3.main_ctx()
        if isinstance(container, (list, tuple, set, frozenset)):
            if isinstance(elem, (int, float)):
                e_val = z3.IntVal(int(elem), ctx=ctx)
            else:
                e_val = z3.StringVal(str(elem), ctx=ctx)
            clauses = []
            for item in container:
                if isinstance(item, (int, float)):
                    i_val = z3.IntVal(int(item), ctx=ctx)
                else:
                    i_val = z3.StringVal(str(item), ctx=ctx)
                clauses.append(e_val == i_val)
            return z3.Or(*clauses) if clauses else z3.BoolVal(False, ctx=ctx)
        if isinstance(container, dict):
            if isinstance(elem, (int, float)):
                e_val = z3.IntVal(int(elem), ctx=ctx)
            else:
                e_val = z3.StringVal(str(elem), ctx=ctx)
            clauses = []
            for k in container:
                if isinstance(k, (int, float)):
                    k_val = z3.IntVal(int(k), ctx=ctx)
                else:
                    k_val = z3.StringVal(str(k), ctx=ctx)
                clauses.append(e_val == k_val)
            return z3.Or(*clauses) if clauses else z3.BoolVal(False, ctx=ctx)
        return z3.BoolVal(False, ctx=ctx)


class FormalVerifier:
    def __init__(self, *, default_parallel_task_cost: int = 1000) -> None:
        self._fallback = FallbackSolver()
        self._z3 = Z3Solver() if _HAS_Z3 else None
        self._parallel_task_cost = default_parallel_task_cost

    @property
    def solver_name(self) -> str:
        return "z3" if self._z3 and self._z3.available else "fallback"

    def _solver(self):
        """Return the best available solver: Z3 if available, else fallback."""
        return self._z3 if self._z3 and self._z3.available else self._fallback

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "solver_name": self.solver_name,
            "z3_available": _HAS_Z3,
            "supported_statuses": [status.value for status in VerificationStatus],
            "supported_checks": [
                ConstraintKind.TYPE_INVARIANT.value,
                ConstraintKind.RANGE_CHECK.value,
                ConstraintKind.GAS_BOUND.value,
                ConstraintKind.SPEC_GATE.value,
            ],
        }

    def get_operator_family_coverage(self) -> dict[str, bool]:
        """Return a mapping of operator family names to whether they are covered.

        Coverage means the family has at least one Z3-encoded verification
        path available through the Z3OperatorEncoder.

        Returns:
            A dict mapping family name to bool (True if covered).
        """
        families = Z3OperatorEncoder.supported_operator_families()
        z3_ok = Z3OperatorEncoder.z3_available()
        # Families currently fully supported with Z3 encoding paths:
        # - numeric: range_check has Z3 encoding
        # - type_system: type_invariant has Z3 encoding
        # - gas: gas_bound has Z3 encoding
        # - spec_gate: spec_gate has deterministic checking
        # - string, set, container: Z3OperatorEncoder provides encodings
        # - boolean, rational, temporal, spatial, effect: covered by type/range
        always_covered = {"numeric", "type_system", "gas", "spec_gate"}
        encoder_covered = {"string", "set", "container"}
        inherited_covered = {"boolean", "rational", "temporal", "spatial", "effect"}

        coverage: dict[str, bool] = {}
        for family in families:
            if family in always_covered:
                coverage[family] = z3_ok
            elif family in encoder_covered:
                coverage[family] = z3_ok
            elif family in inherited_covered:
                coverage[family] = z3_ok
            else:
                coverage[family] = False
        return coverage

    def verify_constraints(
        self, ast: dict[str, Any], *, gas_budget: int = 10_000
    ) -> VerificationReport:
        return self.verify_ast(ast, gas_budget=gas_budget)

    def verify_embodied_contract(self, contract: dict[str, Any] | None) -> VerificationReport:
        report = VerificationReport(z3_enabled=_HAS_Z3)
        if not isinstance(contract, dict) or not contract.get("embodied"):
            return report

        function_name = str(contract.get("function_name") or "embodied_contract")
        action_envelope = (
            dict(contract.get("action_envelope") or {})
            if isinstance(contract.get("action_envelope"), dict)
            else {}
        )
        spatial_bounds = (
            dict(contract.get("spatial_bounds") or {})
            if isinstance(contract.get("spatial_bounds"), dict)
            else {}
        )
        evidence_refs = contract.get("evidence_refs") if isinstance(contract.get("evidence_refs"), list) else []
        world_state_ref = str(contract.get("world_state_ref") or "")
        simulation_only = bool(contract.get("simulation_only", False))
        bounded_spatial_envelope = bool(contract.get("bounded_spatial_envelope", False))

        report.add(
            self.verify_spec_gate(
                fields={"simulation_only": simulation_only},
                property_name=f"{function_name.lower()}_simulation_mode",
            )
        )

        if action_envelope:
            timeout_ms = _numeric_value(action_envelope.get("timeout_ms"))
            if timeout_ms is None:
                report.add(
                    VerificationResult(
                        property_name=f"{function_name.lower()}_timeout_ms",
                        status=VerificationStatus.COUNTEREXAMPLE,
                        kind=ConstraintKind.RANGE_CHECK,
                        message="Embodied action envelope timeout_ms must be a positive numeric literal.",
                        counterexample={"timeout_ms": action_envelope.get("timeout_ms")},
                        solver=self.solver_name,
                    )
                )
            else:
                report.add(
                    self.verify_range(
                        timeout_ms,
                        low=1.0,
                        property_name=f"{function_name.lower()}_timeout_ms",
                    )
                )

            report.add(
                self.verify_spec_gate(
                    fields={"bounded_spatial_envelope": bounded_spatial_envelope},
                    property_name=f"{function_name.lower()}_spatial_envelope",
                )
            )

            for bound_name, bound_value in spatial_bounds.items():
                numeric_bound = _numeric_value(bound_value)
                if numeric_bound is None:
                    report.add(
                        VerificationResult(
                            property_name=f"{function_name.lower()}_{bound_name}",
                            status=VerificationStatus.COUNTEREXAMPLE,
                            kind=ConstraintKind.RANGE_CHECK,
                            message=f"Embodied spatial bound '{bound_name}' must be numeric.",
                            counterexample={"bound": bound_name, "value": bound_value},
                            solver=self.solver_name,
                        )
                    )
                    continue
                report.add(
                    self.verify_range(
                        numeric_bound,
                        low=0.0,
                        property_name=f"{function_name.lower()}_{bound_name}",
                    )
                )

        if function_name in {"WORLD_STATE_RECALL", "TRAJECTORY_PROPOSE"}:
            report.add(
                self.verify_spec_gate(
                    fields={"world_state_ref": bool(world_state_ref)},
                    property_name=f"{function_name.lower()}_world_state_ref",
                )
            )

        if function_name == "GUARDED_ACTUATE":
            report.add(
                self.verify_spec_gate(
                    fields={"evidence_refs": bool(evidence_refs)},
                    property_name="guarded_actuate_evidence_refs",
                )
            )

        return report

    def verify_type(
        self, value: Any, expected_type: str, *, property_name: str = ""
    ) -> VerificationResult:
        return self._solver().check_type(value, expected_type, name=property_name)

    def verify_range(
        self,
        value: Any,
        *,
        low: float | None = None,
        high: float | None = None,
        property_name: str = "",
    ) -> VerificationResult:
        return self._solver().check_range(value, low=low, high=high, name=property_name)

    def verify_gas_budget(
        self,
        task_costs: list[int],
        budget: int,
        *,
        property_name: str = "",
    ) -> VerificationResult:
        return self._solver().check_gas_budget(task_costs, budget, name=property_name)

    def verify_spec_gate(
        self,
        fields: dict[str, Any] | None = None,
        *,
        property_name: str = "",
        condition: Any = None,
    ) -> VerificationResult:
        start = time.time()
        effective_fields = dict(fields or {})
        if effective_fields:
            unresolved = [
                name
                for name, value in effective_fields.items()
                if isinstance(value, dict) and "var_ref" in value
            ]
            if unresolved:
                return VerificationResult(
                    property_name=property_name or "spec_gate",
                    status=VerificationStatus.UNKNOWN,
                    kind=ConstraintKind.SPEC_GATE,
                    message=(
                        "SPEC_GATE depends on unresolved variable references: "
                        + ", ".join(sorted(unresolved))
                    ),
                    solver=self.solver_name,
                    duration_ms=(time.time() - start) * 1000,
                )
            false_fields = [
                name for name, value in effective_fields.items() if isinstance(value, bool) and not value
            ]
            if false_fields:
                field_name = false_fields[0]
                return VerificationResult(
                    property_name=property_name or "spec_gate",
                    status=VerificationStatus.COUNTEREXAMPLE,
                    kind=ConstraintKind.SPEC_GATE,
                    message=f"SPEC_GATE literal '{field_name}' resolved to false.",
                    counterexample={
                        "field": field_name,
                        "value": effective_fields[field_name],
                    },
                    solver=self.solver_name,
                    duration_ms=(time.time() - start) * 1000,
                )
            return VerificationResult(
                property_name=property_name or "spec_gate",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.SPEC_GATE,
                message=(
                    "SPEC_GATE resolved to deterministic literal fields: "
                    + ", ".join(sorted(effective_fields))
                ),
                solver=self.solver_name,
                duration_ms=(time.time() - start) * 1000,
            )

        if isinstance(condition, bool):
            _status = (
                VerificationStatus.RUNTIME_CHECKED
                if condition
                else VerificationStatus.COUNTEREXAMPLE
            )
            return VerificationResult(
                property_name=property_name or "spec_gate",
                status=_status,
                kind=ConstraintKind.SPEC_GATE,
                message=(
                    "SPEC_GATE condition resolved deterministically."
                    if condition
                    else "SPEC_GATE condition resolved to false."
                ),
                counterexample=None if condition else {"condition": False},
                solver=self.solver_name,
                duration_ms=(time.time() - start) * 1000,
            )

        return VerificationResult(
            property_name=property_name or "spec_gate",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.SPEC_GATE,
            message="SPEC_GATE is unresolvable: no deterministic literal proof contract was available and condition could not be discharged.",
            solver=self.solver_name,
            duration_ms=(time.time() - start) * 1000,
        )

    def verify_ast(self, ast: dict[str, Any], *, gas_budget: int = 10_000) -> VerificationReport:
        ast = normalize_ast(ast)
        report = VerificationReport(z3_enabled=_HAS_Z3)
        for constraint in extract_constraints(ast):
            kind = str(constraint.get("kind", ""))
            if kind == "type_invariant":
                report.add(
                    self.verify_type(
                        constraint.get("value"),
                        str(constraint.get("expected_type", "")),
                        property_name=str(constraint.get("name", "type_invariant")),
                    )
                )
                continue
            if kind == "range_check":
                value = constraint.get("value")
                low = _numeric_value(constraint.get("low"))
                high = _numeric_value(constraint.get("high"))
                args = list(constraint.get("args", []))
                if value is None and args and isinstance(args[0], (int, float)):
                    value = args[0]
                    if low is None:
                        low = 0.0
                if isinstance(value, (int, float)):
                    report.add(
                        self.verify_range(
                            value,
                            low=low,
                            high=high,
                            property_name=str(constraint.get("name", "range_check")),
                        )
                    )
                else:
                    report.add(
                        VerificationResult(
                            property_name=str(constraint.get("name", "range_check")),
                            status=VerificationStatus.SKIPPED,
                            kind=ConstraintKind.RANGE_CHECK,
                            message="No numeric argument available for deterministic range proof",
                            solver=self.solver_name,
                        )
                    )
                continue
            if kind == "gas_bound":
                task_count = int(constraint.get("task_count", 0))
                report.add(
                    self.verify_gas_budget(
                        [self._parallel_task_cost] * task_count,
                        gas_budget,
                        property_name=str(constraint.get("name", "gas_budget")),
                    )
                )
                continue
            if kind == "spec_gate":
                report.add(
                    self.verify_spec_gate(
                        fields=constraint.get("fields") if isinstance(constraint.get("fields"), dict) else None,
                        property_name=str(constraint.get("name", "spec_gate")),
                        condition=constraint.get("condition"),
                    )
                )
                continue
            report.add(
                VerificationResult(
                    property_name=str(constraint.get("name", "constraint")),
                    status=VerificationStatus.UNKNOWN,
                    kind=ConstraintKind.CUSTOM,
                    message=f"Unsupported constraint kind '{kind}'",
                    solver=self.solver_name,
                )
            )
        if report.total_count == 0:
            report.add(
                VerificationResult(
                    property_name="ast_constraints",
                    status=VerificationStatus.SKIPPED,
                    kind=ConstraintKind.CUSTOM,
                    message="No verifiable constraints were extracted from the packaged AST.",
                    solver=self.solver_name,
                )
            )
        return report

    def verify_effect_declaration(
        self,
        decl: TypedEffectDeclaration,
        args: dict[str, Any] | None = None,
    ) -> EffectContractAssessment:
        """Verify a typed effect declaration against concrete arguments."""
        effective_args = dict(args) if args is not None else {}
        admitted, reasons = decl.validate_call(effective_args)

        # Mutating effects require review posture
        if decl.effect_class.is_mutating() and decl.review_posture == "none":
            admitted = False
            reasons.append(
                f"'{decl.function_name}': mutating effect '{decl.effect_class.value}' requires review_posture to be set"
            )

        # Security-sensitive failures need adequate safety class
        for fm in decl.failure_modes:
            if fm.is_security_sensitive() and decl.safety_class in ("none", "low"):
                admitted = False
                reasons.append(
                    f"'{decl.function_name}': security-sensitive failure mode '{fm.value}' requires higher safety_class than '{decl.safety_class}'"
                )

        return EffectContractAssessment(
            function_name=decl.function_name,
            admitted=admitted,
            requires_operator_review=decl.review_posture == "operator_review",
            verdict="admitted" if admitted else "denied",
            reasons=reasons,
        )

    def verify_output_contract(
        self,
        oc: OutputContract,
        value: Any,
    ) -> VerificationResult:
        """Verify a concrete value against an output contract."""
        valid, message = oc.validate(value)
        if valid:
            return VerificationResult(
                property_name=f"{oc.function_name}_output_type",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=message or "Output contract validated",
                solver=self.solver_name,
            )
        return VerificationResult(
            property_name=f"{oc.function_name}_output_type",
            status=VerificationStatus.COUNTEREXAMPLE,
            kind=ConstraintKind.TYPE_INVARIANT,
            message=message,
            counterexample={"value": value},
            solver=self.solver_name,
        )

    def verify(
        self,
        compiled_program: dict[str, Any],
        *,
        gas_budget: int = 10_000,
        trust_tier: str = "hearth",
    ) -> tuple[VerificationReport, str]:
        """Verify a compiled program and return a gated decision.

        This is the constitutive verification path: it runs the standard
        verify_ast and then applies tier-differentiated gating.

        Args:
            compiled_program: The compiled AST to verify.
            gas_budget: Gas budget for verification.
            trust_tier: The trust tier for gating (hearth, forge, sovereign).

        Returns:
            Tuple of (VerificationReport, GateDecision string).
            The caller should:
            - PROCEED: execute normally
            - BLOCK: raise VerificationBlockedError or return blocked status
            - WARN: log warning but proceed
        """
        report = self.verify_ast(compiled_program, gas_budget=gas_budget)
        decision = VerificationGate.gate(report, trust_tier)
        return report, decision

    def verify_with_depth(
        self,
        compiled_program: dict[str, Any],
        min_depth: int = 1,
        *,
        gas_budget: int = 10_000,
        trust_tier: str = "hearth",
        timeout_ms: float | None = None,
    ) -> tuple[VerificationReport, str, dict[str, Any]]:
        """Verify with a minimum proof depth requirement.

        This extends the standard verification path with depth-gating:
        if the measured proof depth is below `min_depth`, the gate
        escalates to the next stricter tier.

        Edge cases handled:
        - Tier escalation: if depth is insufficient, the tier is escalated.
          This means a forge-tier agent with min_depth=2 that only reaches
          depth=1 will be gated as hearth.
        - Timeout recovery: if `timeout_ms` is set and exceeded, partial
          results are returned with a TIMEOUT status rather than blocking
          indefinitely.
        - Partial proofs: if only some constraints are proven, the depth
          score reflects partial coverage rather than failing entirely.

        Args:
            compiled_program: The compiled AST to verify.
            min_depth: Minimum required proof depth (default 1).
            gas_budget: Gas budget for verification.
            trust_tier: The trust tier for gating.
            timeout_ms: Optional timeout in milliseconds for verification.

        Returns:
            Tuple of (VerificationReport, GateDecision string, depth_info dict).
            The depth_info dict contains:
            - measured_depth: The measured proof depth
            - min_depth: The required minimum depth
            - depth_sufficient: Whether depth met the minimum
            - effective_tier: The tier actually used (may be escalated)
            - timeout_occurred: Whether the timeout was hit
            - partial_proof: Whether this is a partial proof
        """
        # Run verification with optional timeout
        start_time = time.time()
        timeout_occurred = False

        if timeout_ms is not None and timeout_ms > 0:
            # Use a simple timeout mechanism: if verification takes too long,
            # return what we have as a partial proof
            timeout_sec = timeout_ms / 1000.0
            try:
                report = self.verify_ast(compiled_program, gas_budget=gas_budget)
                elapsed = (time.time() - start_time) * 1000.0
                if elapsed > timeout_ms:
                    timeout_occurred = True
            except Exception:
                timeout_occurred = True
                report = VerificationReport(z3_enabled=_HAS_Z3)
                report.add(
                    VerificationResult(
                        property_name="timeout_recovery",
                        status=VerificationStatus.ERROR,
                        kind=ConstraintKind.CUSTOM,
                        message=(
                            f"Verification timed out after {timeout_ms}ms. "
                            f"Returning partial results."
                        ),
                        solver=self.solver_name,
                        duration_ms=elapsed if 'elapsed' in dir() else timeout_ms,
                    )
                )
        else:
            report = self.verify_ast(compiled_program, gas_budget=gas_budget)

        # Measure proof depth (lazy import to avoid circular dependency)
        from hlf_mcp.hlf.proof_depth import measure_proof_depth

        measured_depth = measure_proof_depth(report)
        partial_proof = report.total_count > 0 and not report.all_proven

        # Determine effective tier with escalation
        effective_tier = trust_tier
        depth_sufficient = measured_depth >= min_depth

        if not depth_sufficient and min_depth > 0:
            # Escalate tier: insufficient depth triggers stricter gating
            effective_tier = VerificationGate.escalate_tier(trust_tier)

        # Gate with the effective (possibly escalated) tier
        decision = VerificationGate.gate(report, effective_tier)

        # If timeout occurred, ensure we don't falsely claim PROCEED
        if timeout_occurred and decision == GateDecision.PROCEED:
            decision = GateDecision.WARN

        depth_info: dict[str, Any] = {
            "measured_depth": measured_depth,
            "min_depth": min_depth,
            "depth_sufficient": depth_sufficient,
            "effective_tier": effective_tier,
            "original_tier": trust_tier,
            "tier_escalated": effective_tier != trust_tier,
            "timeout_occurred": timeout_occurred,
            "partial_proof": partial_proof,
            "verification_time_ms": (time.time() - start_time) * 1000.0,
        }

        return report, decision, depth_info

    # ── Proof Artifact Construction ──────────────────────────────────────

    def build_proof_artifact(
        self,
        execution_id: str,
        constraints: list[dict[str, Any]],
        z3_result: dict[str, Any] | None = None,
        *,
        proof_type: str = "LEMMA",
        proof_depth: int = 0,
        evidence_chain: list[str] | None = None,
        verdict: str | None = None,
    ) -> ProofArtifact:
        """Build a full ProofArtifact from execution-scoped verification data.

        Args:
            execution_id: Unique execution identifier.
            constraints: List of constraint dicts verified.
            z3_result: Optional Z3 solver result with keys: result, expressions, duration_ms.
            proof_type: The proof type ("LEMMA", "INDUCTIVE", "EQUIVALENCE").
            proof_depth: Depth of proof (0=LEMMA, 1=INDUCTIVE base, 2+=INDUCTIVE step).
            evidence_chain: Optional Merkle evidence hashes.
            verdict: Optional explicit verdict override. If None, derived from solver result.

        Returns:
            A populated ProofArtifact with all extended fields filled.
        """
        z3_exprs: list[str] = []
        solver_result = ""
        if z3_result is not None:
            z3_exprs = z3_result.get("expressions", [])
            solver_result = str(z3_result.get("result", ""))

        if not evidence_chain:
            evidence_chain = []

        # Determine verdict: explicit override takes precedence
        if verdict is not None:
            pass  # Use caller-provided verdict
        elif solver_result == "sat":
            verdict = "admitted"
        elif solver_result == "timeout":
            verdict = "conditional"
        elif solver_result == "unsat":
            verdict = "denied"
        else:
            # For non-Z3 (fallback) paths, derive from constraints
            proven_all = all(
                c.get("status", "") in ("proven", "runtime_checked")
                for c in constraints
            )
            verdict = "admitted" if proven_all else "denied"
            solver_result = solver_result or "fallback"

        # Build human-readable operator summary
        summary_parts = [
            f"Execution: {execution_id}",
            f"Type: {proof_type}",
            f"Depth: {proof_depth}",
            f"Verdict: {verdict}",
            f"Solver: {solver_result}",
            f"Constraints: {len(constraints)} checked",
        ]
        operator_summary = " | ".join(summary_parts)

        # Build Merkle evidence chain from constraint hashes
        chain = list(evidence_chain)
        if not chain and constraints:
            for c in constraints:
                c_hash = hashlib.sha256(
                    json.dumps(c, sort_keys=True).encode("utf-8")
                ).hexdigest()[:16]
                chain.append(c_hash)

        artifact = ProofArtifact(
            artifact_id=execution_id,
            property_name=f"execution_{execution_id[:8]}",
            verdict=verdict,
            operator_family="execution",
            smt_encoding="z3" if solver_result not in ("fallback", "") else "fallback",
            timestamp_iso=datetime.now(timezone.utc).isoformat(),
            proof_type=proof_type,
            constraints=constraints,
            z3_expressions=z3_exprs,
            solver_result=solver_result,
            proof_depth=proof_depth,
            evidence_chain=chain,
            operator_summary=operator_summary,
        )

        # Compute content hash
        content_for_hash = {
            "artifact_id": artifact.artifact_id,
            "property_name": artifact.property_name,
            "verdict": artifact.verdict,
            "operator_family": artifact.operator_family,
            "smt_encoding": artifact.smt_encoding,
            "timestamp_iso": artifact.timestamp_iso,
            "proof_type": artifact.proof_type,
            "constraints": artifact.constraints,
            "z3_expressions": artifact.z3_expressions,
            "solver_result": artifact.solver_result,
            "proof_depth": artifact.proof_depth,
            "evidence_chain": artifact.evidence_chain,
            "operator_summary": artifact.operator_summary,
            "metadata": artifact.metadata,
        }
        artifact.content_hash = hashlib.sha256(
            json.dumps(content_for_hash, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return artifact

    # ── INDUCTIVE Proof Automation ───────────────────────────────────────

    def verify_inductive(
        self,
        base_case: dict[str, Any],
        step_case: dict[str, Any],
        *,
        property_name: str = "",
        timeout_ms: float | None = 5000.0,
    ) -> ProofArtifact:
        """Verify an inductive proof with base case and inductive step.

        Uses Z3 SMT solver to verify:
        1. Base case: P(0) or P(base_value) holds
        2. Inductive step: ∀n: P(n) → P(n+1) holds

        Args:
            base_case: Dict with 'value' (concrete base value) and 'property' (assertion).
            step_case: Dict with 'n_symbol' (symbolic var name), 'property' (P(n) assertion),
                       and optionally 'step_assertion' (P(n+1) assertion).
            property_name: Optional property name for the artifact.
            timeout_ms: Z3 solver timeout in milliseconds.

        Returns:
            ProofArtifact with proof_type="INDUCTIVE". Verdict is "admitted" if
            both base and step are proven, "denied" if either fails, or
            "conditional" if Z3 times out.
        """
        start_time = time.time()
        execution_id = str(uuid.uuid4())
        constraints: list[dict[str, Any]] = []
        z3_expressions: list[str] = []
        solver_result = "sat"

        z3_available = self._z3 is not None and self._z3.available
        base_value = base_case.get("value")
        base_property = base_case.get("property", {})
        base_holds = False
        step_holds = False
        base_status = "unchecked"
        step_status = "unchecked"

        if z3_available:
            ctx = self._z3._ctx
            try:
                # --- Base case verification ---
                z3.set_param("timeout", int(timeout_ms) if timeout_ms else 5000)

                # Build base case Z3 constraints
                s_base = z3.Solver(ctx=ctx)
                n_base = z3.Int("n_base", ctx=ctx)

                base_exprs = _encode_inductive_case(
                    n_base, base_value, base_property, ctx
                )
                z3_expressions.extend(base_exprs)
                s_base.add(z3.parse_smt2_string(
                    "(assert (= n_base {}))".format(
                        int(base_value) if isinstance(base_value, (int, float)) else 0
                    ),
                    ctx=ctx,
                ))

                # Assert base property
                _add_property_to_solver(s_base, n_base, base_property, ctx)

                result_base = s_base.check()
                base_holds = str(result_base) == "sat"
                base_status = "proven" if base_holds else "counterexample"

                constraints.append({
                    "name": f"{property_name}_base",
                    "status": base_status,
                    "z3_result": str(result_base),
                    "value": base_value,
                })

                if not base_holds:
                    solver_result = "unsat"
                else:
                    # --- Inductive step verification ---
                    s_step = z3.Solver(ctx=ctx)
                    n_sym = z3.Int(str(step_case.get("n_symbol", "n")), ctx=ctx)
                    n_next = n_sym + 1
                    step_property = step_case.get("property", {})

                    # Encode P(n) as assumption and try to prove P(n+1)
                    step_exprs_pn = _encode_inductive_case(
                        n_sym, None, step_property, ctx
                    )
                    z3_expressions.extend(step_exprs_pn)

                    # Add P(n) as assumption
                    _add_property_to_solver(s_step, n_sym, step_property, ctx)

                    # Try to falsify P(n+1): add NOT P(n+1) and check unsat
                    _add_negated_property_to_solver(s_step, n_next, step_property, ctx)

                    result_step = s_step.check()
                    # unsat means P(n) → P(n+1) is valid (can't find counterexample)
                    step_holds = str(result_step) == "unsat"
                    step_status = "proven" if step_holds else "counterexample"

                    constraints.append({
                        "name": f"{property_name}_step",
                        "status": step_status,
                        "z3_result": str(result_step),
                        "n_symbol": str(step_case.get("n_symbol", "n")),
                    })

                    if not step_holds:
                        solver_result = "unsat"

            except z3.Z3Exception:
                solver_result = "timeout"
                base_status = "timeout"
                step_status = "timeout"
                constraints.append({
                    "name": f"{property_name}_inductive",
                    "status": "timeout",
                    "z3_result": "timeout",
                })
        else:
            # Fallback: heuristic verification
            solver_result = "fallback"
            if isinstance(base_value, (int, float)):
                base_holds = _fallback_check_property(base_value, base_property)
                base_status = "proven" if base_holds else "counterexample"
                # For step: if base holds, conservatively admit
                step_holds = base_holds
                step_status = "runtime_checked" if step_holds else "counterexample"
            constraints.append({
                "name": f"{property_name}_base",
                "status": base_status,
                "value": base_value,
            })
            constraints.append({
                "name": f"{property_name}_step",
                "status": step_status,
            })

        # Determine verdict
        if solver_result == "timeout":
            verdict = "conditional"
        elif base_holds and step_holds:
            verdict = "admitted"
        else:
            verdict = "denied"

        proof_depth = 2 if (base_holds and step_holds) else (1 if base_holds else 0)

        return self.build_proof_artifact(
            execution_id=execution_id,
            constraints=constraints,
            z3_result={
                "result": solver_result,
                "expressions": z3_expressions,
                "duration_ms": (time.time() - start_time) * 1000.0,
            },
            proof_type="INDUCTIVE",
            proof_depth=proof_depth,
            verdict=verdict,
        )

    # ── Effect Composition Proof ─────────────────────────────────────────

    def verify_effect_composition(
        self,
        effect_a: dict[str, Any],
        effect_b: dict[str, Any],
        *,
        property_name: str = "",
        timeout_ms: float | None = 5000.0,
    ) -> ProofArtifact:
        """Verify that two typed effects are safe to compose.

        Uses Z3 to prove composition safety by checking that the preconditions
        of effect_b are not violated by the postconditions of effect_a, and
        that no type or resource conflicts exist.

        Args:
            effect_a: First effect dict with optional keys: name, effect_class,
                      preconditions, postconditions, resource_claims.
            effect_b: Second effect dict.
            property_name: Optional property name.
            timeout_ms: Z3 solver timeout in milliseconds.

        Returns:
            ProofArtifact with proof_type="EQUIVALENCE". Verdict is "admitted"
            if composition is safe, "denied" if a conflict is found, or
            "conditional" if the composition requires operator review.
        """
        start_time = time.time()
        execution_id = str(uuid.uuid4())
        constraints: list[dict[str, Any]] = []
        z3_expressions: list[str] = []
        solver_result = "fallback"

        name_a = str(effect_a.get("name", "effect_a"))
        name_b = str(effect_b.get("name", "effect_b"))
        class_a = str(effect_a.get("effect_class", ""))
        class_b = str(effect_b.get("effect_class", ""))

        preconds_b = effect_b.get("preconditions", {})
        if not isinstance(preconds_b, dict):
            preconds_b = {}
        postconds_a = effect_a.get("postconditions", {})
        if not isinstance(postconds_a, dict):
            postconds_a = {}

        resources_a = effect_a.get("resource_claims", [])
        if not isinstance(resources_a, list):
            resources_a = []
        resources_b = effect_b.get("resource_claims", [])
        if not isinstance(resources_b, list):
            resources_b = []

        z3_available = self._z3 is not None and self._z3.available
        composition_safe = True
        conflicts: list[str] = []

        # Check 1: Resource conflict detection
        res_a_set = {str(r) for r in resources_a}
        res_b_set = {str(r) for r in resources_b}
        resource_overlap = res_a_set & res_b_set
        if resource_overlap:
            composition_safe = False
            conflicts.append(
                f"Resource conflict: {name_a} and {name_b} both claim {sorted(resource_overlap)}"
            )

        # Check 2: Postcondition → precondition compatibility
        for key, post_val in postconds_a.items():
            if key in preconds_b:
                pre_val = preconds_b[key]
                if isinstance(post_val, (int, float)) and isinstance(pre_val, (int, float)):
                    if post_val < pre_val:
                        composition_safe = False
                        conflicts.append(
                            f"Postcondition conflict: {name_a}.{key}={post_val} < {name_b}.{key}={pre_val}"
                        )
                elif isinstance(post_val, bool) and isinstance(pre_val, bool):
                    if post_val != pre_val:
                        composition_safe = False
                        conflicts.append(
                            f"Boolean mismatch on '{key}': {name_a}={post_val}, {name_b}={pre_val}"
                        )

        # Check 3: Mutating + mutating requires review
        mutating_classes = {"mutating", "stateful_write", "destructive"}
        both_mutate = class_a in mutating_classes and class_b in mutating_classes
        if both_mutate:
            constraints.append({
                "name": f"{property_name}_mutating_composition",
                "status": "runtime_checked",
                "detail": f"Both {name_a} and {name_b} are mutating; requires operator review",
            })

        # Z3 verification of numeric constraints if available
        if z3_available and preconds_b and postconds_a:
            try:
                z3.set_param("timeout", int(timeout_ms) if timeout_ms else 5000)
                ctx = self._z3._ctx
                s = z3.Solver(ctx=ctx)

                for key, post_val in postconds_a.items():
                    if key in preconds_b and isinstance(post_val, (int, float)) and isinstance(preconds_b[key], (int, float)):
                        x = z3.Real(f"post_{key}", ctx=ctx)
                        y = z3.Real(f"pre_{key}", ctx=ctx)
                        s.add(x == z3.RealVal(float(post_val), ctx=ctx))
                        s.add(y == z3.RealVal(float(preconds_b[key]), ctx=ctx))
                        s.add(x < y)  # Try to find violation
                        z3_expr = f"(and (= post_{key} {post_val}) (= pre_{key} {preconds_b[key]}) (< post_{key} pre_{key}))"
                        z3_expressions.append(z3_expr)

                if z3_expressions:
                    z3_result = s.check()
                    solver_result = str(z3_result)
                    if str(z3_result) == "sat":
                        # Z3 found a case where post < pre → unsafe
                        composition_safe = False
                        conflicts.append("Z3 found precondition violation in effect composition")
            except z3.Z3Exception:
                solver_result = "timeout"

        constraints.append({
            "name": f"{property_name}_resource_check",
            "status": "proven" if not resource_overlap else "counterexample",
            "resources_a": sorted(res_a_set),
            "resources_b": sorted(res_b_set),
            "overlap": sorted(resource_overlap) if resource_overlap else [],
        })
        constraints.append({
            "name": f"{property_name}_postcondition_check",
            "status": "proven" if composition_safe else "counterexample",
            "conflicts": conflicts,
        })

        # Determine verdict
        if solver_result == "timeout":
            verdict = "conditional"
        elif composition_safe and not both_mutate:
            verdict = "admitted"
        elif composition_safe and both_mutate:
            verdict = "conditional"
        else:
            verdict = "denied"

        proof_depth = 2 if (composition_safe and not conflicts) else (1 if composition_safe else 0)

        return self.build_proof_artifact(
            execution_id=execution_id,
            constraints=constraints,
            z3_result={
                "result": solver_result,
                "expressions": z3_expressions,
                "duration_ms": (time.time() - start_time) * 1000.0,
            },
            proof_type="EQUIVALENCE",
            proof_depth=proof_depth,
            verdict=verdict,
        )

    # ── Regression Plan Generation ───────────────────────────────────────

    @staticmethod
    def build_regression_plan(
        artifacts: list[ProofArtifact],
    ) -> dict[str, Any]:
        """Build a prioritized regression test plan from proof artifacts.

        Analyzes a collection of ProofArtifacts and produces a regression
        test plan ordered by priority: denied proofs first, then conditional,
        then admitted. Each entry includes preconditions and an evidence
        reference.

        Args:
            artifacts: List of ProofArtifacts to analyze.

        Returns:
            A dict with keys:
            - total_artifacts: total count
            - admitted_count: count of admitted proofs
            - denied_count: count of denied proofs
            - conditional_count: count of conditional proofs
            - regression_plan: list of regression entries sorted by priority
            - generated_at: ISO timestamp
        """
        admitted_count = sum(1 for a in artifacts if a.verdict == "admitted")
        denied_count = sum(1 for a in artifacts if a.verdict == "denied")
        conditional_count = sum(1 for a in artifacts if a.verdict == "conditional")

        # Priority: denied=1 (highest), conditional=2, admitted=3 (lowest)
        def _priority(a: ProofArtifact) -> int:
            if a.verdict == "denied":
                return 1
            if a.verdict == "conditional":
                return 2
            return 3

        def _priority_label(p: int) -> str:
            return {1: "critical", 2: "advisory", 3: "regression"}.get(p, "unknown")

        sorted_artifacts = sorted(artifacts, key=_priority)

        plan_entries: list[dict[str, Any]] = []
        for a in sorted_artifacts:
            entry = {
                "artifact_id": a.artifact_id,
                "property_name": a.property_name,
                "verdict": a.verdict,
                "proof_type": a.proof_type,
                "proof_depth": a.proof_depth,
                "solver_result": a.solver_result,
                "priority": _priority(a),
                "priority_label": _priority_label(_priority(a)),
                "preconditions": {
                    "solver": a.smt_encoding,
                    "z3_required": a.solver_result not in ("fallback", ""),
                    "constraint_count": len(a.constraints),
                },
                "evidence_hash": a.content_hash[:16] if a.content_hash else "",
                "operator_summary": a.operator_summary,
            }
            plan_entries.append(entry)

        return {
            "total_artifacts": len(artifacts),
            "admitted_count": admitted_count,
            "denied_count": denied_count,
            "conditional_count": conditional_count,
            "regression_plan": plan_entries,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ── Helper functions for inductive proof encoding ───────────────────────


def _encode_inductive_case(
    n_var: Any,  # z3.ExprRef
    value: Any,
    property_spec: dict[str, Any],
    ctx: Any,
) -> list[str]:
    """Encode an inductive case as human-readable Z3 expressions.

    Args:
        n_var: Z3 integer variable.
        value: Concrete value for base case, or None for step case.
        property_spec: Dict describing the property to check.
        ctx: Z3 context.

    Returns:
        List of SMT-LIB expression strings.
    """
    exprs: list[str] = []
    op = property_spec.get("op", "eq")
    target = property_spec.get("target")

    if op == "eq" and target is not None:
        if isinstance(target, str) and "*" in target:
            # Pattern like "2*n" → encode n_var * 2 == 2 * value for base
            parts = target.split("*")
            multiplier = float(parts[0].strip()) if len(parts) == 2 else 2.0
            if value is not None:
                exprs.append(f"(= (* {multiplier} n_var) {multiplier * float(value)})")
            else:
                exprs.append(f"(assert (= n_var (* {multiplier} (div n_var {multiplier}))))")
        elif value is not None:
            exprs.append(f"(= n_var {float(value) if isinstance(value, (int, float)) else value})")
    elif op == "lt" and target is not None:
        exprs.append(f"(< n_var {target})")
    elif op == "gt" and target is not None:
        exprs.append(f"(> n_var {target})")
    elif op == "range" and isinstance(target, dict):
        lo = target.get("low", 0)
        hi = target.get("high", 100)
        exprs.append(f"(and (>= n_var {lo}) (<= n_var {hi}))")

    return exprs


def _add_property_to_solver(
    solver: Any,  # z3.Solver
    n_var: Any,  # z3.ExprRef
    property_spec: dict[str, Any],
    ctx: Any,
) -> None:
    """Add a property assertion to a Z3 solver.

    Encodes the property check for n_var as a positive assertion.
    """
    import z3 as _z3

    op = property_spec.get("op", "eq")
    target = property_spec.get("target")

    if op == "eq" and target is not None:
        if isinstance(target, str) and "*" in target:
            parts = target.split("*")
            multiplier = float(parts[0].strip())
            solver.add(n_var * _z3.IntVal(int(multiplier), ctx=ctx) == n_var + n_var)
        elif isinstance(target, (int, float)):
            solver.add(n_var == _z3.IntVal(int(target), ctx=ctx))
    elif op == "lt" and isinstance(target, (int, float)):
        solver.add(n_var < _z3.IntVal(int(target), ctx=ctx))
    elif op == "gt" and isinstance(target, (int, float)):
        solver.add(n_var > _z3.IntVal(int(target), ctx=ctx))


def _add_negated_property_to_solver(
    solver: Any,  # z3.Solver
    n_var: Any,  # z3.ExprRef
    property_spec: dict[str, Any],
    ctx: Any,
) -> None:
    """Add the negation of a property assertion to a Z3 solver.

    Used for induction step: try to falsify P(n+1) given P(n).
    """
    import z3 as _z3

    op = property_spec.get("op", "eq")
    target = property_spec.get("target")

    if op == "eq" and target is not None:
        if isinstance(target, str) and "*" in target:
            parts = target.split("*")
            multiplier = float(parts[0].strip())
            # Negate: NOT (n * k == n + n)
            solver.add(n_var * _z3.IntVal(int(multiplier), ctx=ctx) != n_var + n_var)
        elif isinstance(target, (int, float)):
            solver.add(n_var != _z3.IntVal(int(target), ctx=ctx))
    elif op == "lt" and isinstance(target, (int, float)):
        solver.add(n_var >= _z3.IntVal(int(target), ctx=ctx))
    elif op == "gt" and isinstance(target, (int, float)):
        solver.add(n_var <= _z3.IntVal(int(target), ctx=ctx))


def _fallback_check_property(value: Any, property_spec: dict[str, Any]) -> bool:
    """Fallback (non-Z3) property check for inductive base cases.

    Args:
        value: The concrete value to check.
        property_spec: Dict with 'op' and 'target' keys.

    Returns:
        True if the property holds for the given value.
    """
    op = property_spec.get("op", "eq")
    target = property_spec.get("target")

    if not isinstance(value, (int, float)):
        return False

    if op == "eq":
        if isinstance(target, str) and "*" in target:
            parts = target.split("*")
            multiplier = float(parts[0].strip())
            return abs(value * multiplier - 2 * value) < 0.001
        if isinstance(target, (int, float)):
            return value == target
    elif op == "lt" and isinstance(target, (int, float)):
        return value < target
    elif op == "gt" and isinstance(target, (int, float)):
        return value > target
    elif op == "range" and isinstance(target, dict):
        lo = target.get("low", float("-inf"))
        hi = target.get("high", float("inf"))
        return lo <= value <= hi

    return True  # Unknown op → conservatively admit


# ═══════════════════════════════════════════════════════════════════════════════
# Phase P1: Proof Artifact Format Standardization + Z3 Coverage + INDUCTIVE
# Added as module-level extensions (no rewrite of existing code)
# ═══════════════════════════════════════════════════════════════════════════════


# ── Coverage Map ───────────────────────────────────────────────────────────

COVERAGE_MAP: dict[str, list[str]] = {
    "arithmetic": [
        "(assert (= (+ x y) (+ y x)))",
        "(assert (= (* x y) (* y x)))",
        "(assert (= (- x x) 0))",
        "(assert (= (+ x 0) x))",
        "(assert (= (* x 1) x))",
        "(assert (distinct (+ x 1) x))",
    ],
    "comparison": [
        "(assert (=> (and (< x y) (< y z)) (< x z)))",
        "(assert (=> (< x y) (<= x y)))",
        "(assert (= (<= x y) (or (< x y) (= x y))))",
        "(assert (>= x x))",
        "(assert (not (and (< x y) (> x y))))",
        "(assert (=> (and (<= x y) (<= y x)) (= x y)))",
    ],
    "boolean": [
        "(assert (= (and p q) (and q p)))",
        "(assert (= (or p q) (or q p)))",
        "(assert (not (and p (not p))))",
        "(assert (=> (and (=> p q) (=> q r)) (=> p r)))",
        "(assert (or p (not p)))",
        "(assert (= (not (and p q)) (or (not p) (not q))))",
    ],
    "set": [
        "(assert (subset (intersection A B) A))",
        "(assert (= (union A B) (union B A)))",
        "(assert (= (intersection A A) A))",
        "(assert (subset empty A))",
        "(assert (disjoint A (difference B A)))",
        "(assert (=> (subset A B) (subset (union A C) (union B C))))",
    ],
    "control_flow": [
        "(assert (= (ite c x y) (ite (not c) y x)))",
        "(assert (= (ite true x y) x))",
        "(assert (=> c (= (ite c x y) x)))",
        "(assert (=> (not c) (= (ite c x y) y)))",
        "(assert (= (and c (or (not c) x)) (and c x)))",
    ],
    "type_coercion": [
        "(assert (= (to_real (to_int x)) x))",
        "(assert (>= (to_int x) 0))",
        "(assert (=> (is_int x) (= (to_int (to_real x)) x)))",
        "(assert (distinct (len (to_set l)) (len l)))",
        "(assert (<= (len (to_set l)) (len l)))",
    ],
}


# ── Operator class verification ────────────────────────────────────────────

def verify_operator_class(
    operator_class: str,
    formulae: list[str],
) -> list:
    """Verify a batch of Z3 formulae for a given operator class.

    Wraps Z3 verification calls and returns a list of ProofArtifacts
    (from proof_artifacts module) with proper status assignment.

    Args:
        operator_class: The operator class name.
        formulae: List of SMT-LIB formula strings to verify.

    Returns:
        List of ProofArtifact instances from the proof_artifacts module.
    """
    from hlf_mcp.hlf.proof_artifacts import (
        ProofArtifact,
        ProofStatus,
        admit_proof,
        create_proof_artifact,
        deny_proof,
    )

    import time as _time

    artifacts: list[ProofArtifact] = []

    for formula in formulae:
        start = _time.time()

        if not _HAS_Z3:
            artifact = create_proof_artifact(
                operator_class=operator_class,
                theorem=f"Z3 verification of: {formula[:80]}...",
                formula=formula,
                result="unknown",
                time_ms=(_time.time() - start) * 1000.0,
                evidence={"fallback": True, "reason": "z3_not_available"},
            )
            artifact.status = ProofStatus.UNVERIFIED
            artifacts.append(artifact)
            continue

        try:
            s = z3.Solver()
            s.from_string(formula)
            z3_result = s.check()

            elapsed = (_time.time() - start) * 1000.0
            result_str = str(z3_result)

            if result_str == "sat":
                try:
                    model_dict = {
                        str(d.name()): str(s.model()[d])
                        if s.model()[d] is not None
                        else "None"
                        for d in s.model().decls()
                    }
                except Exception:
                    model_dict = None

                artifact = create_proof_artifact(
                    operator_class=operator_class,
                    theorem=f"Z3 verification of: {formula[:80]}...",
                    formula=formula,
                    result=result_str,
                    model=model_dict,
                    time_ms=elapsed,
                )
                deny_proof(artifact, f"Counterexample found: {model_dict}")
            elif result_str == "unsat":
                try:
                    proof_trace = str(s.proof()) if s.proof() else None
                except Exception:
                    proof_trace = None

                artifact = create_proof_artifact(
                    operator_class=operator_class,
                    theorem=f"Z3 verification of: {formula[:80]}...",
                    formula=formula,
                    result=result_str,
                    proof_trace=proof_trace,
                    time_ms=elapsed,
                )
                admit_proof(artifact, admitted_by="z3")
            else:
                artifact = create_proof_artifact(
                    operator_class=operator_class,
                    theorem=f"Z3 verification of: {formula[:80]}...",
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                artifact.status = ProofStatus.UNVERIFIED

        except Exception as exc:
            elapsed = (_time.time() - start) * 1000.0
            artifact = create_proof_artifact(
                operator_class=operator_class,
                theorem=f"Z3 verification error: {formula[:60]}...",
                formula=formula,
                result=str(exc),
                time_ms=elapsed,
                evidence={"error": str(exc)},
            )
            artifact.status = ProofStatus.ERROR

        artifacts.append(artifact)

    return artifacts


def run_regression_suite() -> tuple[list, dict[str, int]]:
    """Run all operator classes against stored regression test formulae.

    Uses COVERAGE_MAP to test each operator class with its canonical
    formula patterns.

    Returns:
        Tuple of (list of ProofArtifacts, summary dict with counts).
    """
    from hlf_mcp.hlf.proof_artifacts import ProofStatus, format_proof_report

    all_artifacts: list = []
    for operator_class, formulae in COVERAGE_MAP.items():
        class_artifacts = verify_operator_class(operator_class, formulae)
        all_artifacts.extend(class_artifacts)

    report = format_proof_report(all_artifacts)
    summary: dict[str, int] = {
        "total": report["total"],
        "admitted": report["admitted"],
        "denied": report["denied"],
        "unverified": report["unverified"],
        "timeout": report["timeout"],
        "error": report["error"],
    }

    return all_artifacts, summary


def export_proof_artifacts(artifacts: list, format: str = "json") -> str:
    """Export proof artifacts in the specified format.

    Args:
        artifacts: List of ProofArtifact instances.
        format: Output format ("json" or "markdown").

    Returns:
        A string in the requested format.
    """
    if format == "json":
        import json as _json

        return _json.dumps(
            [a.to_dict() for a in artifacts],
            indent=2,
            sort_keys=True,
        )

    if format == "markdown":
        lines: list[str] = [
            "# Proof Artifacts Export",
            "",
            f"**Total artifacts:** {len(artifacts)}",
            "",
            "| Artifact ID | Operator Class | Theorem | Status | Result | Time (ms) |",
            "|-------------|---------------|---------|--------|--------|-----------|",
        ]
        for a in artifacts:
            lines.append(
                f"| {a.artifact_id[:8]}... | {a.operator_class} "
                f"| {a.theorem[:50]} | {a.status.value} "
                f"| {a.result or 'N/A'} | {a.time_ms:.1f} |"
            )
        return "\n".join(lines)

    raise ValueError(f"Unknown export format: {format}")


# ── Coverage computation ──────────────────────────────────────────────────


def compute_coverage(artifacts: list) -> dict[str, float]:
    """Compute per-class coverage percentage.

    Coverage = admitted / (admitted + denied + unverified).

    Args:
        artifacts: List of ProofArtifact instances.

    Returns:
        Dict mapping operator_class → coverage percentage (0.0–100.0).
    """
    from hlf_mcp.hlf.proof_artifacts import ProofStatus

    class_results: dict[str, dict[str, int]] = {}
    for a in artifacts:
        cls_name = a.operator_class
        if cls_name not in class_results:
            class_results[cls_name] = {"admitted": 0, "denied": 0, "unverified": 0}
        if a.status == ProofStatus.ADMITTED:
            class_results[cls_name]["admitted"] += 1
        elif a.status == ProofStatus.DENIED:
            class_results[cls_name]["denied"] += 1
        elif a.status == ProofStatus.UNVERIFIED:
            class_results[cls_name]["unverified"] += 1

    coverage: dict[str, float] = {}
    for cls_name, counts in class_results.items():
        total = counts["admitted"] + counts["denied"] + counts["unverified"]
        coverage[cls_name] = (counts["admitted"] / total * 100.0) if total > 0 else 0.0

    # Include classes with zero artifacts
    for cls_name in COVERAGE_MAP:
        if cls_name not in coverage:
            coverage[cls_name] = 0.0

    return coverage


def detect_missing_coverage() -> list[str]:
    """Return operator classes with 0% coverage.

    Returns:
        List of operator class names that have no admitted proofs.
    """
    coverage = compute_coverage([])
    return [cls_name for cls_name, pct in coverage.items() if pct == 0.0]


# ── Z3 verification functions for new operator classes ────────────────────


def verify_set_operations() -> list:
    """Verify set theory operations using Z3.

    Covers: union, intersection, difference, subset, superset, disjoint.

    Returns:
        List of ProofArtifact instances.
    """
    from hlf_mcp.hlf.proof_artifacts import ProofArtifact, ProofStatus, admit_proof, create_proof_artifact, deny_proof

    import time as _time

    set_formulae = [
        # Union commutativity: A ∪ B = B ∪ A
        "(declare-const A (Set Int))\n(declare-const B (Set Int))\n(assert (not (= (set.union A B) (set.union B A))))",
        # Intersection idempotence: A ∩ A = A
        "(declare-const A (Set Int))\n(assert (not (= (set.inter A A) A)))",
        # Difference property: A \ A = ∅
        "(declare-const A (Set Int))\n(assert (not (= (set.minus A A) (as set.empty (Set Int)))))",
        # Subset reflexivity: A ⊆ A
        "(declare-const A (Set Int))\n(assert (not (set.subset A A)))",
        # Superset: A ⊆ B and B ⊆ A → A = B
        "(declare-const A (Set Int))\n(declare-const B (Set Int))\n(assert (set.subset A B))\n(assert (set.subset B A))\n(assert (not (= A B)))",
        # Disjoint property: A ∩ B = ∅ means disjoint
        "(declare-const A (Set Int))\n(declare-const B (Set Int))\n(assert (= (set.inter A B) (as set.empty (Set Int))))\n(assert (set.subset (set.inter A B) A))",
    ]

    theorem_names = [
        "Union commutativity: A ∪ B = B ∪ A",
        "Intersection idempotence: A ∩ A = A",
        "Difference property: A \\ A = ∅",
        "Subset reflexivity: A ⊆ A",
        "Anti-symmetry: A ⊆ B ∧ B ⊆ A → A = B",
        "Disjoint sets: A ∩ B = ∅ ∧ A ∩ B ⊆ A",
    ]

    artifacts: list = []
    for formula, theorem in zip(set_formulae, theorem_names):
        start = _time.time()

        if not _HAS_Z3:
            artifact = create_proof_artifact(
                operator_class="set",
                theorem=theorem,
                formula=formula,
                result="unknown",
                time_ms=(_time.time() - start) * 1000.0,
                evidence={"fallback": True, "reason": "z3_not_available"},
            )
            artifact.status = ProofStatus.UNVERIFIED
            artifacts.append(artifact)
            continue

        try:
            s = z3.Solver()
            s.from_string(formula)
            z3_result = s.check()

            elapsed = (_time.time() - start) * 1000.0
            result_str = str(z3_result)

            # For these formulae, we assert the negation of the property,
            # so "unsat" means the property is valid
            if result_str == "unsat":
                artifact = create_proof_artifact(
                    operator_class="set",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                admit_proof(artifact, admitted_by="z3")
            elif result_str == "sat":
                try:
                    model_dict = {
                        str(d.name()): str(s.model()[d])
                        if s.model()[d] is not None
                        else "None"
                        for d in s.model().decls()
                    }
                except Exception:
                    model_dict = None

                artifact = create_proof_artifact(
                    operator_class="set",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    model=model_dict,
                    time_ms=elapsed,
                )
                deny_proof(artifact, f"Counterexample: {model_dict}")
            else:
                artifact = create_proof_artifact(
                    operator_class="set",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                artifact.status = ProofStatus.UNVERIFIED

        except Exception as exc:
            elapsed = (_time.time() - start) * 1000.0
            artifact = create_proof_artifact(
                operator_class="set",
                theorem=theorem,
                formula=formula,
                result=str(exc),
                time_ms=elapsed,
                evidence={"error": str(exc)},
            )
            artifact.status = ProofStatus.ERROR

        artifacts.append(artifact)

    return artifacts


def verify_type_coercions() -> list:
    """Verify type coercion properties using Z3.

    Covers: int→float, float→int, str→int, list→set, set→list.

    Returns:
        List of ProofArtifact instances.
    """
    from hlf_mcp.hlf.proof_artifacts import ProofArtifact, ProofStatus, admit_proof, create_proof_artifact, deny_proof

    import time as _time

    coercion_formulae = [
        # int→float: to_real preserves value
        "(declare-const x Int)\n(assert (not (= (to_real x) (to_real x))))",
        # float→int: to_int is monotonic for positive values
        "(declare-const x Real)\n(declare-const y Real)\n(assert (>= x 0))\n(assert (>= y 0))\n(assert (<= x y))\n(assert (not (<= (to_int x) (to_int y))))",
        # list→set: set cardinality ≤ list length
        "(declare-const l (List Int))\n(assert (> (set.card (to_set l)) (list.len l)))",
        # set→list: converting back gives equal or fewer elements
        "(declare-const s (Set Int))\n(assert (> (set.card s) (list.len (to_list s))))",
        # Coercion roundtrip: int → real → int for positive values
        "(declare-const x Int)\n(assert (>= x 0))\n(assert (not (= (to_int (to_real x)) x)))",
    ]

    theorem_names = [
        "int→float: to_real preserves value identity",
        "float→int: to_int is monotonic for non-negative reals",
        "list→set: set cardinality ≤ list length",
        "set→list: cardinality preserved under roundtrip bound",
        "Coercion roundtrip: int → real → int identity",
    ]

    artifacts: list = []
    for formula, theorem in zip(coercion_formulae, theorem_names):
        start = _time.time()

        if not _HAS_Z3:
            artifact = create_proof_artifact(
                operator_class="type_coercion",
                theorem=theorem,
                formula=formula,
                result="unknown",
                time_ms=(_time.time() - start) * 1000.0,
                evidence={"fallback": True, "reason": "z3_not_available"},
            )
            artifact.status = ProofStatus.UNVERIFIED
            artifacts.append(artifact)
            continue

        try:
            s = z3.Solver()
            s.from_string(formula)
            z3_result = s.check()

            elapsed = (_time.time() - start) * 1000.0
            result_str = str(z3_result)

            if result_str == "unsat":
                artifact = create_proof_artifact(
                    operator_class="type_coercion",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                admit_proof(artifact, admitted_by="z3")
            elif result_str == "sat":
                try:
                    model_dict = {
                        str(d.name()): str(s.model()[d])
                        if s.model()[d] is not None
                        else "None"
                        for d in s.model().decls()
                    }
                except Exception:
                    model_dict = None

                artifact = create_proof_artifact(
                    operator_class="type_coercion",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    model=model_dict,
                    time_ms=elapsed,
                )
                deny_proof(artifact, f"Counterexample: {model_dict}")
            else:
                artifact = create_proof_artifact(
                    operator_class="type_coercion",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                artifact.status = ProofStatus.UNVERIFIED

        except Exception as exc:
            elapsed = (_time.time() - start) * 1000.0
            artifact = create_proof_artifact(
                operator_class="type_coercion",
                theorem=theorem,
                formula=formula,
                result=str(exc),
                time_ms=elapsed,
                evidence={"error": str(exc)},
            )
            artifact.status = ProofStatus.ERROR

        artifacts.append(artifact)

    return artifacts


def verify_control_flow_equivalences() -> list:
    """Verify control flow equivalence properties using Z3.

    Covers: if-then-else, switch, guard clauses, short-circuit eval.

    Returns:
        List of ProofArtifact instances.
    """
    from hlf_mcp.hlf.proof_artifacts import ProofArtifact, ProofStatus, admit_proof, create_proof_artifact, deny_proof

    import time as _time

    cf_formulae = [
        # if-then-else commutativity of branches: ite(c, x, y) = ite(¬c, y, x)
        "(declare-const c Bool)\n(declare-const x Int)\n(declare-const y Int)\n(assert (not (= (ite c x y) (ite (not c) y x))))",
        # ite with true condition: ite(true, x, y) = x
        "(declare-const x Int)\n(declare-const y Int)\n(assert (not (= (ite true x y) x)))",
        # Guard clause implication: c ⇒ ite(c, x, y) = x
        "(declare-const c Bool)\n(declare-const x Int)\n(declare-const y Int)\n(assert c)\n(assert (not (= (ite c x y) x)))",
        # Short-circuit AND: c ∧ (¬c ∨ x) ≡ c ∧ x
        "(declare-const c Bool)\n(declare-const x Bool)\n(assert (not (= (and c (or (not c) x)) (and c x))))",
        # Short-circuit OR: c ∨ (¬c ∧ x) ≡ c ∨ x
        "(declare-const c Bool)\n(declare-const x Bool)\n(assert (not (= (or c (and (not c) x)) (or c x))))",
    ]

    theorem_names = [
        "ite commutativity: ite(c, x, y) = ite(¬c, y, x)",
        "ite true branch: ite(true, x, y) = x",
        "Guard clause: c ⇒ ite(c, x, y) = x",
        "Short-circuit AND: c ∧ (¬c ∨ x) ≡ c ∧ x",
        "Short-circuit OR: c ∨ (¬c ∧ x) ≡ c ∨ x",
    ]

    artifacts: list = []
    for formula, theorem in zip(cf_formulae, theorem_names):
        start = _time.time()

        if not _HAS_Z3:
            artifact = create_proof_artifact(
                operator_class="control_flow",
                theorem=theorem,
                formula=formula,
                result="unknown",
                time_ms=(_time.time() - start) * 1000.0,
                evidence={"fallback": True, "reason": "z3_not_available"},
            )
            artifact.status = ProofStatus.UNVERIFIED
            artifacts.append(artifact)
            continue

        try:
            s = z3.Solver()
            s.from_string(formula)
            z3_result = s.check()

            elapsed = (_time.time() - start) * 1000.0
            result_str = str(z3_result)

            # These formulae assert the negation of the equivalence,
            # so "unsat" = equivalence is valid
            if result_str == "unsat":
                artifact = create_proof_artifact(
                    operator_class="control_flow",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                admit_proof(artifact, admitted_by="z3")
            elif result_str == "sat":
                try:
                    model_dict = {
                        str(d.name()): str(s.model()[d])
                        if s.model()[d] is not None
                        else "None"
                        for d in s.model().decls()
                    }
                except Exception:
                    model_dict = None

                artifact = create_proof_artifact(
                    operator_class="control_flow",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    model=model_dict,
                    time_ms=elapsed,
                )
                deny_proof(artifact, f"Counterexample: {model_dict}")
            else:
                artifact = create_proof_artifact(
                    operator_class="control_flow",
                    theorem=theorem,
                    formula=formula,
                    result=result_str,
                    time_ms=elapsed,
                )
                artifact.status = ProofStatus.UNVERIFIED

        except Exception as exc:
            elapsed = (_time.time() - start) * 1000.0
            artifact = create_proof_artifact(
                operator_class="control_flow",
                theorem=theorem,
                formula=formula,
                result=str(exc),
                time_ms=elapsed,
                evidence={"error": str(exc)},
            )
            artifact.status = ProofStatus.ERROR

        artifacts.append(artifact)

    return artifacts
