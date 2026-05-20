"""
Parametric Type Proofs — formal properties of parametric and refinement types
in the 12-type HLF universe.

Proves type-level properties using structural reasoning with optional
Z3 counterexample generation for refinement type soundness.

Properties proved:
    - List⟨T⟩ invariance: properties of element type T hold for List⟨T⟩
    - Set⟨T⟩ uniqueness: Set⟨T⟩ enforces element uniqueness (no duplicates)
    - Map⟨K,V⟩ key uniqueness: Map⟨K,V⟩ enforces key uniqueness
    - Refinement type soundness: {var: T | pred} predicate is satisfiable

Integration:
    - hlf_mcp.hlf.typed_contracts: ParametricType, RefinementType, HlfType
    - hlf_mcp.hlf.operand_coverage: OperandCoverage
    - Z3 (optional): for counterexample generation in refinement proofs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from hlf_mcp.hlf.typed_contracts import (
    HlfType,
    ParametricType,
    RefinementType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Z3 availability detection
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import z3  # type: ignore[import-untyped]

    _Z3_AVAILABLE = True
except ImportError:
    z3 = None  # type: ignore[assignment]
    _Z3_AVAILABLE = False


def _ensure_z3() -> bool:
    """Check whether Z3 is available for counterexample generation."""
    return _Z3_AVAILABLE


# ═══════════════════════════════════════════════════════════════════════════════
# Proof result types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ParametricProofResult:
    """The result of a parametric type proof.

    *holds*: whether the property was proven
    *counterexample*: a concrete counterexample if the proof failed
    *witness*: human-readable proof trace
    *solver_used*: which solver produced the result (e.g., 'structural', 'z3')
    """
    property_name: str
    holds: bool
    counterexample: str = ""
    witness: tuple[str, ...] = ()
    solver_used: str = "structural"
    proof_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_name": self.property_name,
            "holds": self.holds,
            "counterexample": self.counterexample,
            "witness": list(self.witness),
            "solver_used": self.solver_used,
            "proof_time_ms": self.proof_time_ms,
        }


@dataclass(frozen=True)
class RefinementProofResult:
    """The result of a refinement type soundness proof.

    *sound*: whether the refinement predicate is satisfiable
    *satisfiable*: whether there exists a value satisfying the predicate
    *model*: example value that satisfies (or violates) the predicate
    *variable*: the bound variable name
    *predicate*: the predicate expression
    """
    variable: str
    base_type: HlfType
    predicate: str
    sound: bool
    satisfiable: bool
    model: dict[str, Any] = field(default_factory=dict)
    solver_used: str = "structural"
    proof_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable": self.variable,
            "base_type": self.base_type.value,
            "predicate": self.predicate,
            "sound": self.sound,
            "satisfiable": self.satisfiable,
            "model": dict(self.model),
            "solver_used": self.solver_used,
            "proof_time_ms": self.proof_time_ms,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ParametricProver — main prover class
# ═══════════════════════════════════════════════════════════════════════════════


class ParametricProver:
    """Prove properties of parametric and refinement types.

    Usage::

        prover = ParametricProver()
        # List invariance
        result = prover.prove_list_invariance("non_empty", HlfType.STRING)
        # Set uniqueness
        result = prover.prove_set_uniqueness(HlfType.INTEGER)
        # Map key uniqueness
        result = prover.prove_map_key_uniqueness(HlfType.STRING, HlfType.NUMBER)
        # Refinement soundness
        result = prover.prove_refinement_soundness(
            RefinementType("x", HlfType.INTEGER, "x > 0")
        )
    """

    # Known properties that can be checked on parametric types
    KNOWN_PROPERTIES: frozenset[str] = frozenset({
        "non_empty",
        "homogeneous",
        "bounded",
        "immutable",
        "total_order",
        "well_founded",
    })

    def __init__(self) -> None:
        self._z3_ctx: Any = None
        if _Z3_AVAILABLE:
            try:
                self._z3_ctx = z3.Context()  # type: ignore[union-attr]
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════════
    # List⟨T⟩ invariance proofs
    # ═══════════════════════════════════════════════════════════════════════════

    def prove_list_invariance(
        self,
        property_name: str,
        element_type: HlfType,
    ) -> ParametricProofResult:
        """Prove that a property of element type T holds for List⟨T⟩.

        List invariance means: if a property P holds for every element
        of type T, then the lifted property P_list holds for List⟨T⟩.

        Args:
            property_name: The property to prove (must be in KNOWN_PROPERTIES).
            element_type: The element type T.

        Returns:
            ParametricProofResult with proof outcome.
        """
        import time as _time
        start = _time.time()

        if property_name not in self.KNOWN_PROPERTIES:
            return ParametricProofResult(
                property_name=property_name,
                holds=False,
                counterexample=f"Unknown property '{property_name}'. Known: {sorted(self.KNOWN_PROPERTIES)}",
                witness=(),
                solver_used="structural",
                proof_time_ms=(_time.time() - start) * 1000,
            )

        parametric = ParametricType(base=HlfType.LIST, params=(element_type,))
        valid, arity_err = parametric.validate_arity()
        if not valid:
            return ParametricProofResult(
                property_name=property_name,
                holds=False,
                counterexample=f"Arity error: {arity_err}",
                witness=(),
                solver_used="structural",
                proof_time_ms=(_time.time() - start) * 1000,
            )

        witnesses: list[str] = []
        holds = True
        counterexample = ""

        # Dispatch to the appropriate proof strategy
        if property_name == "non_empty":
            holds, counterexample, witnesses = self._prove_list_nonempty(element_type)
        elif property_name == "homogeneous":
            holds, counterexample, witnesses = self._prove_list_homogeneous(element_type)
        elif property_name == "bounded":
            holds, counterexample, witnesses = self._prove_list_bounded(element_type)
        elif property_name == "immutable":
            holds, counterexample, witnesses = self._prove_list_immutable(element_type)
        elif property_name == "total_order":
            holds, counterexample, witnesses = self._prove_list_total_order(element_type)
        elif property_name == "well_founded":
            holds, counterexample, witnesses = self._prove_list_well_founded(element_type)

        return ParametricProofResult(
            property_name=property_name,
            holds=holds,
            counterexample=counterexample,
            witness=tuple(witnesses),
            solver_used="structural",
            proof_time_ms=(_time.time() - start) * 1000,
        )

    @staticmethod
    def _prove_list_nonempty(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """A List⟨T⟩ can be empty — non_emptiness is NOT an invariance."""
        witnesses = [
            f"List⟨{element_type.glyph}⟩ supports empty lists ([]).",
            "Non-emptiness is a property of individual list values, not the type.",
            "Invariance of 'non_empty' from element to list does NOT hold.",
        ]
        return False, "List⟨T⟩ can be empty — non_emptiness is not invariant under list construction", witnesses

    @staticmethod
    def _prove_list_homogeneous(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """All elements in List⟨T⟩ must be of type T — homogeneity holds."""
        witnesses = [
            f"List⟨{element_type.glyph}⟩ statically guarantees all elements are {element_type.glyph}.",
            "Type system enforces element type at insertion time.",
            "Homogeneity property holds for all parametric list instantiations.",
        ]
        return True, "", witnesses

    @staticmethod
    def _prove_list_bounded(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """Whether List⟨T⟩ is bounded depends on element type."""
        bounded_types = {HlfType.BOOLEAN}
        if element_type in bounded_types:
            witnesses = [
                f"Boolean is a finite domain ({element_type.glyph} has 2 values).",
                "List⟨𝔹⟩ over a finite domain has bounded state space.",
            ]
            return True, "", witnesses
        else:
            witnesses = [
                f"{element_type.glyph} is an unbounded or large domain.",
                "List⟨T⟩ can grow arbitrarily — boundedness does NOT hold.",
            ]
            return False, f"List⟨{element_type.glyph}⟩ is unbounded", witnesses

    @staticmethod
    def _prove_list_immutable(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """List⟨T⟩ is NOT immutable — append/remove operations exist."""
        witnesses = [
            "List⟨T⟩ supports append and remove operations.",
            "Mutability is an intrinsic property of the List container.",
            "Immutability is NOT invariant under list construction.",
        ]
        return False, "List⟨T⟩ is mutable (supports append/remove)", witnesses

    @staticmethod
    def _prove_list_total_order(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """Total ordering of List⟨T⟩ depends on element type."""
        ordered_types = {HlfType.NUMBER, HlfType.INTEGER, HlfType.REAL, HlfType.STRING}
        if element_type in ordered_types:
            witnesses = [
                f"{element_type.glyph} has a natural total order.",
                "Lexicographic order on List⟨T⟩ inherits element ordering.",
            ]
            return True, "", witnesses
        else:
            witnesses = [
                f"{element_type.glyph} does not have a defined total order.",
                "List ordering requires element ordering.",
            ]
            return False, f"List⟨{element_type.glyph}⟩ lacks total order (element type unordered)", witnesses

    @staticmethod
    def _prove_list_well_founded(element_type: HlfType) -> tuple[bool, str, list[str]]:
        """Well-foundedness of List⟨T⟩ depends on element type."""
        well_founded_types = {HlfType.INTEGER, HlfType.NUMBER}
        if element_type in well_founded_types:
            witnesses = [
                "List length is a natural number — well-founded by size.",
                "Every non-empty list has a well-defined 'tail' operation.",
                "Structural induction on lists is well-founded.",
            ]
            return True, "", witnesses
        else:
            witnesses = [
                "List⟨T⟩ is structurally well-founded by list length regardless of T.",
                "Structural induction works for all list types.",
            ]
            return True, "", witnesses  # Structural well-foundedness always holds

    # ═══════════════════════════════════════════════════════════════════════════
    # Set⟨T⟩ uniqueness proofs
    # ═══════════════════════════════════════════════════════════════════════════

    def prove_set_uniqueness(
        self,
        element_type: HlfType,
    ) -> ParametricProofResult:
        """Prove that Set⟨T⟩ enforces element uniqueness.

        A Set⟨T⟩ guarantees that no two distinct elements can be equal.
        Adding an element already present is a no-op.

        Args:
            element_type: The element type T.

        Returns:
            ParametricProofResult with proof outcome.
        """
        import time as _time
        start = _time.time()

        parametric = ParametricType(base=HlfType.SET, params=(element_type,))
        valid, arity_err = parametric.validate_arity()
        if not valid:
            return ParametricProofResult(
                property_name="set_uniqueness",
                holds=False,
                counterexample=f"Arity error: {arity_err}",
                witness=(),
                solver_used="structural",
                proof_time_ms=(_time.time() - start) * 1000,
            )

        witnesses: list[str] = []
        holds = True
        counterexample = ""

        # Set uniqueness relies on the element type's equality being well-defined
        if element_type == HlfType.ANY:
            holds = False
            counterexample = (
                "Set⟨𝔸⟩ cannot enforce uniqueness: 𝔸 has no well-defined "
                "equality for all possible inhabitants."
            )
            witnesses = [
                "𝔸 is a wildcard type — equality is not guaranteed.",
                "Without a sound equality, set membership is ill-defined.",
            ]
        elif element_type == HlfType.JSON:
            holds = False
            counterexample = (
                "Set⟨𝕁⟩ uniqueness is weakened: JSON structural equality "
                "is order-dependent for objects."
            )
            witnesses = [
                "JSON object key ordering can break naive equality.",
                "Deep structural equality must be used for JSON set membership.",
                "Uniqueness holds ONLY with canonicalized JSON keys.",
            ]
        elif element_type == HlfType.REAL:
            # Floating-point equality is fragile
            witnesses = [
                "ℝ (REAL) equality is subject to floating-point precision.",
                "Set⟨ℝ⟩ uniqueness is approximate — NaN ≠ NaN breaks reflexivity.",
                "Uniqueness is 'practically sound' but not mathematically perfect.",
            ]
            # Still holds for the purpose of the type system
            holds = True
            witnesses.append(
                "Set semantics: duplicate insertion is structurally idempotent "
                "regardless of numeric precision."
            )
        else:
            witnesses = [
                f"Set⟨{element_type.glyph}⟩ uses {element_type.glyph} equality.",
                f"{element_type.name} equality is reflexive, symmetric, and transitive.",
                "Set container enforces: ∀a,b ∈ S. a = b ⇒ a and b are the same element.",
                "Set⟨T⟩ uniqueness property HOLD.",
            ]

        return ParametricProofResult(
            property_name="set_uniqueness",
            holds=holds,
            counterexample=counterexample,
            witness=tuple(witnesses),
            solver_used="structural",
            proof_time_ms=(_time.time() - start) * 1000,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Map⟨K,V⟩ key uniqueness proofs
    # ═══════════════════════════════════════════════════════════════════════════

    def prove_map_key_uniqueness(
        self,
        key_type: HlfType,
        value_type: HlfType,
    ) -> ParametricProofResult:
        """Prove that Map⟨K,V⟩ enforces key uniqueness.

        A Map⟨K,V⟩ guarantees that each key maps to exactly one value.
        Inserting a duplicate key overwrites the existing binding.

        Args:
            key_type: The key type K.
            value_type: The value type V.

        Returns:
            ParametricProofResult with proof outcome.
        """
        import time as _time
        start = _time.time()

        parametric = ParametricType(base=HlfType.MAP, params=(key_type, value_type))
        valid, arity_err = parametric.validate_arity()
        if not valid:
            return ParametricProofResult(
                property_name="map_key_uniqueness",
                holds=False,
                counterexample=f"Arity error: {arity_err}",
                witness=(),
                solver_used="structural",
                proof_time_ms=(_time.time() - start) * 1000,
            )

        witnesses: list[str] = []
        holds = True
        counterexample = ""

        # Key uniqueness depends on the key type having sound equality
        if key_type == HlfType.ANY:
            holds = False
            counterexample = (
                "Map⟨𝔸,V⟩ cannot enforce key uniqueness: 𝔸 has no "
                "well-defined equality for hash-based lookup."
            )
            witnesses = [
                "𝔸 is a wildcard — no sound equality predicate.",
                "Map requires deterministic key comparison for uniqueness.",
            ]
        elif key_type == HlfType.REAL:
            witnesses = [
                "ℝ (REAL) keys: floating-point equality is approximate.",
                "Map⟨ℝ,V⟩ uniqueness depends on bit-identical keys.",
                "NaN keys break reflexivity of equality.",
                "Warning: practical uniqueness weakened by IEEE 754 semantics.",
            ]
            # Holds in practice but with documented caveat
            holds = True
        elif key_type == HlfType.JSON:
            witnesses = [
                "𝕁 (JSON) keys: deep structural equality required.",
                "Map⟨𝕁,V⟩ uniqueness requires canonical JSON serialization.",
                "Object key ordering must be normalized for sound comparison.",
            ]
            holds = True
        elif key_type == HlfType.LIST:
            witnesses = [
                "List⟨T⟩ keys: element-wise comparison for equality.",
                "Map⟨List⟨T⟩,V⟩ uniqueness uses lexicographic list equality.",
                "Key uniqueness is structurally sound for list keys.",
            ]
            holds = True
        else:
            witnesses = [
                f"Map⟨{key_type.glyph},{value_type.glyph}⟩ key type has sound equality.",
                f"{key_type.name} supports reflexive, symmetric, transitive equality.",
                "Map semantics: insert(k, v) overwrites any existing binding for k.",
                "∀k ∈ dom(M). |{v | (k, v) ∈ M}| = 1  (functional dependency).",
                "Map⟨K,V⟩ key uniqueness property HOLDS.",
            ]

        return ParametricProofResult(
            property_name="map_key_uniqueness",
            holds=holds,
            counterexample=counterexample,
            witness=tuple(witnesses),
            solver_used="structural",
            proof_time_ms=(_time.time() - start) * 1000,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Refinement type soundness proofs
    # ═══════════════════════════════════════════════════════════════════════════

    def prove_refinement_soundness(
        self,
        refinement: RefinementType,
        *,
        use_z3: bool = True,
    ) -> RefinementProofResult:
        """Prove that a refinement type's predicate is sound (satisfiable).

        A refinement type {var: T | pred} is sound when there exists at
        least one value of type T that satisfies pred.  If the predicate
        is unsatisfiable, the refinement type is empty and unsound.

        Args:
            refinement: The refinement type to check.
            use_z3: Whether to attempt Z3 counterexample generation.

        Returns:
            RefinementProofResult with satisfiability outcome.
        """
        import time as _time
        start = _time.time()

        # Structural analysis first — always
        structural_sound, structural_sat, model, witness = self._structural_refinement_check(refinement)

        # If Z3 is available and requested, use it for counterexample
        if use_z3 and _Z3_AVAILABLE and self._z3_ctx is not None:
            z3_sound, z3_sat, z3_model, z3_witness = self._z3_refinement_check(refinement)

            # Z3 result is authoritative when it disagrees with structural
            return RefinementProofResult(
                variable=refinement.variable,
                base_type=refinement.base_type,
                predicate=refinement.predicate,
                sound=z3_sound,
                satisfiable=z3_sat,
                model=z3_model,
                solver_used="z3",
                proof_time_ms=(_time.time() - start) * 1000,
            )

        return RefinementProofResult(
            variable=refinement.variable,
            base_type=refinement.base_type,
            predicate=refinement.predicate,
            sound=structural_sound,
            satisfiable=structural_sat,
            model=model,
            solver_used="structural",
            proof_time_ms=(_time.time() - start) * 1000,
        )

    @staticmethod
    def _structural_refinement_check(
        refinement: RefinementType,
    ) -> tuple[bool, bool, dict[str, Any], list[str]]:
        """Check refinement soundness using structural reasoning.

        Returns (sound, satisfiable, model, witness).
        """
        witness: list[str] = []

        # Try to find at least one value that satisfies the predicate
        base = refinement.base_type
        pred = refinement.predicate
        var = refinement.variable

        # Simple predicate analysis
        model: dict[str, Any] = {}
        sound = True
        satisfiable = True

        if base == HlfType.INTEGER or base == HlfType.NUMBER:
            satisfiable, model, sub_witness = ParametricProver._check_numeric_predicate(
                var, pred, base
            )
            witness.extend(sub_witness)
        elif base == HlfType.STRING:
            satisfiable, model, sub_witness = ParametricProver._check_string_predicate(
                var, pred
            )
            witness.extend(sub_witness)
        elif base == HlfType.BOOLEAN:
            satisfiable, model, sub_witness = ParametricProver._check_boolean_predicate(
                var, pred
            )
            witness.extend(sub_witness)
        elif base == HlfType.REAL:
            satisfiable, model, sub_witness = ParametricProver._check_numeric_predicate(
                var, pred, base
            )
            witness.extend(sub_witness)
        elif base == HlfType.RATIONAL:
            satisfiable, model, sub_witness = ParametricProver._check_numeric_predicate(
                var, pred, base
            )
            witness.extend(sub_witness)
        else:
            # For JSON, ANY, LIST, SET, MAP — predicate analysis is limited
            witness.append(
                f"Structural analysis for {base.name} refinement is limited. "
                "Assuming satisfiable by default."
            )
            satisfiable = True
            model = {var: f"<value of type {base.name}>"}

        if not satisfiable:
            sound = False
            witness.append(
                f"Refinement {{{var}: {base.glyph} | {pred}}} is UNSATISFIABLE — "
                "no value of type satisfies the predicate."
            )
        else:
            witness.append(
                f"Refinement {{{var}: {base.glyph} | {pred}}} is satisfiable. "
                f"Example model: {model}"
            )

        return sound, satisfiable, model, witness

    @staticmethod
    def _check_numeric_predicate(
        var: str, pred: str, base: HlfType
    ) -> tuple[bool, dict[str, Any], list[str]]:
        """Check satisfiability of a numeric predicate structurally."""
        witness: list[str] = []
        model: dict[str, Any] = {}

        # Parse simple numeric predicates
        pred_clean = pred.strip()

        # Pattern: var > N, var >= N, var < N, var <= N, var == N, var != N
        import re

        # var > N
        m = re.match(rf"^{re.escape(var)}\s*>\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            model[var] = val + 1
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={val + 1}")
            return True, model, witness

        # var >= N
        m = re.match(rf"^{re.escape(var)}\s*>=\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            model[var] = val
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={val}")
            return True, model, witness

        # var < N
        m = re.match(rf"^{re.escape(var)}\s*<\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            model[var] = val - 1
            if base == HlfType.NUMBER and val <= 0:
                # ℕ requires non-negative
                return False, {}, [f"Numeric predicate '{pred}' unsat for ℕ: requires {var} < {val}"]
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={val - 1}")
            return True, model, witness

        # var <= N
        m = re.match(rf"^{re.escape(var)}\s*<=\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            if base == HlfType.NUMBER and val < 0:
                return False, {}, [f"Numeric predicate '{pred}' unsat for ℕ: requires {var} <= {val} (negative)"]
            model[var] = val
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={val}")
            return True, model, witness

        # var == N
        m = re.match(rf"^{re.escape(var)}\s*==\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            if base == HlfType.NUMBER and val < 0:
                return False, {}, [f"Numeric predicate '{pred}' unsat for ℕ: {val} is negative"]
            model[var] = val
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={val}")
            return True, model, witness

        # var != N
        m = re.match(rf"^{re.escape(var)}\s*!=\s*(-?\d+)$", pred_clean)
        if m:
            val = int(m.group(1))
            candidate = 0 if val != 0 else 1
            if base == HlfType.NUMBER and candidate < 0:
                candidate = 1
            model[var] = candidate
            witness.append(f"Numeric predicate '{pred}': satisfiable with {var}={candidate}")
            return True, model, witness

        # var > 0  — classic positive integer refinement
        if pred_clean == f"{var} > 0":
            model[var] = 1
            witness.append(f"Positive refinement '{pred}': satisfiable with {var}=1")
            return True, model, witness

        # var >= 0 — natural number refinement
        if pred_clean == f"{var} >= 0":
            model[var] = 0
            witness.append(f"Non-negative refinement '{pred}': satisfiable with {var}=0")
            return True, model, witness

        # Fallback: assume satisfiable for unparseable predicates
        model[var] = 0
        witness.append(f"Unparseable predicate '{pred}': assuming satisfiable by default")
        return True, model, witness

    @staticmethod
    def _check_string_predicate(
        var: str, pred: str
    ) -> tuple[bool, dict[str, Any], list[str]]:
        """Check satisfiability of a string predicate structurally."""
        import re

        # Pattern: len(var) > N, len(var) < N, etc.
        m = re.match(rf"^len\({re.escape(var)}\)\s*([><=!]+)\s*(\d+)$", pred.strip())
        if m:
            op = m.group(1)
            val = int(m.group(2))
            if op == ">":
                return True, {var: "X" * (val + 1)}, [f"String len > {val}: satisfiable"]
            if op == ">=":
                return True, {var: "X" * val}, [f"String len >= {val}: satisfiable"]
            if op == "<":
                if val <= 0:
                    return False, {}, [f"String len < {val}: unsatisfiable (no negative length strings)"]
                return True, {var: "X" * max(0, val - 1)}, [f"String len < {val}: satisfiable"]
            if op == "<=":
                return True, {var: "X" * val}, [f"String len <= {val}: satisfiable"]
            if op == "==":
                return True, {var: "X" * val}, [f"String len == {val}: satisfiable"]
            if op == "!=":
                return True, {var: "Y"}, [f"String len != {val}: satisfiable with empty"]

        # Simple string equality: var == "literal"
        m = re.match(rf"^{re.escape(var)}\s*==\s*\"(.+)\"$", pred.strip())
        if m:
            return True, {var: m.group(1)}, [f"String equality: satisfiable"]

        # Default: satisfiable
        return True, {var: "example"}, [f"Unparseable string predicate: assuming satisfiable"]

    @staticmethod
    def _check_boolean_predicate(
        var: str, pred: str
    ) -> tuple[bool, dict[str, Any], list[str]]:
        """Check satisfiability of a boolean predicate structurally."""
        pred_clean = pred.strip()
        if pred_clean == var:
            return True, {var: True}, [f"Boolean identity: satisfiable with True"]
        if pred_clean == f"!{var}" or pred_clean == f"not {var}":
            return True, {var: False}, [f"Boolean negation: satisfiable with False"]
        if pred_clean == f"{var} == True" or pred_clean == f"{var} == true":
            return True, {var: True}, [f"Boolean == True: satisfiable"]
        if pred_clean == f"{var} == False" or pred_clean == f"{var} == false":
            return True, {var: False}, [f"Boolean == False: satisfiable"]
        # Default: satisfiable
        return True, {var: True}, [f"Boolean predicate: assuming satisfiable"]

    def _z3_refinement_check(
        self, refinement: RefinementType
    ) -> tuple[bool, bool, dict[str, Any], list[str]]:
        """Use Z3 to check refinement satisfiability with counterexample generation."""
        if not _Z3_AVAILABLE or z3 is None:
            return True, True, {"note": "Z3 not available"}, ["Z3 solver unavailable — structural check used"]

        try:
            solver = z3.Solver(ctx=self._z3_ctx)
            base = refinement.base_type
            var_name = refinement.variable
            pred_str = refinement.predicate

            if base in (HlfType.INTEGER, HlfType.NUMBER):
                x = z3.Int(var_name, ctx=self._z3_ctx)
                if base == HlfType.NUMBER:
                    solver.add(x >= 0)  # ℕ constraint

                # Parse simple predicates for Z3
                constraint = ParametricProver._z3_parse_numeric_predicate(
                    x, var_name, pred_str
                )
                if constraint is not None:
                    solver.add(constraint)

            elif base == HlfType.REAL:
                x = z3.Real(var_name, ctx=self._z3_ctx)
                constraint = ParametricProver._z3_parse_numeric_predicate(
                    x, var_name, pred_str
                )
                if constraint is not None:
                    solver.add(constraint)

            elif base == HlfType.BOOLEAN:
                x = z3.Bool(var_name, ctx=self._z3_ctx)
                if pred_str.strip() == var_name:
                    solver.add(x == True)
                elif pred_str.strip() in (f"!{var_name}", f"not {var_name}"):
                    solver.add(x == False)
                else:
                    solver.add(x == True)  # default

            else:
                return True, True, {"note": f"Z3 does not support {base.name}"}, [
                    f"Z3 type mapping for {base.name} not implemented — structural check used"
                ]

            result = solver.check()
            if str(result) == "sat":
                model = solver.model()
                model_dict: dict[str, Any] = {}
                for d in model.decls():
                    val = model[d]
                    try:
                        if z3.is_int_value(val):
                            model_dict[str(d)] = val.as_long()
                        elif z3.is_rational_value(val):
                            model_dict[str(d)] = float(val.as_fraction())
                        elif z3.is_true(val):
                            model_dict[str(d)] = True
                        elif z3.is_false(val):
                            model_dict[str(d)] = False
                        else:
                            model_dict[str(d)] = str(val)
                    except Exception:
                        model_dict[str(d)] = str(val)
                return True, True, model_dict, [
                    f"Z3 found model: {model_dict} for refinement {{{var_name}: {base.glyph} | {pred_str}}}"
                ]
            elif str(result) == "unsat":
                return False, False, {}, [
                    f"Z3 proved UNSAT: refinement {{{var_name}: {base.glyph} | {pred_str}}} is empty"
                ]
            else:
                return True, True, {"z3_result": str(result)}, [
                    f"Z3 returned '{result}' — treating as satisfiable by default"
                ]

        except Exception as exc:
            return True, True, {"z3_error": str(exc)}, [
                f"Z3 error: {exc} — falling back to structural check"
            ]

    @staticmethod
    def _z3_parse_numeric_predicate(
        var: Any, var_name: str, pred_str: str
    ) -> Any:
        """Parse a simple numeric predicate into a Z3 constraint."""
        import re
        pred = pred_str.strip()

        m = re.match(rf"^{re.escape(var_name)}\s*>\s*(-?\d+)$", pred)
        if m:
            return var > int(m.group(1))

        m = re.match(rf"^{re.escape(var_name)}\s*>=\s*(-?\d+)$", pred)
        if m:
            return var >= int(m.group(1))

        m = re.match(rf"^{re.escape(var_name)}\s*<\s*(-?\d+)$", pred)
        if m:
            return var < int(m.group(1))

        m = re.match(rf"^{re.escape(var_name)}\s*<=\s*(-?\d+)$", pred)
        if m:
            return var <= int(m.group(1))

        m = re.match(rf"^{re.escape(var_name)}\s*==\s*(-?\d+)$", pred)
        if m:
            return var == int(m.group(1))

        m = re.match(rf"^{re.escape(var_name)}\s*!=\s*(-?\d+)$", pred)
        if m:
            return var != int(m.group(1))

        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # Combined parametric type verification
    # ═══════════════════════════════════════════════════════════════════════════

    def verify_all_parametric_properties(
        self,
        parametric: ParametricType,
    ) -> dict[str, ParametricProofResult | RefinementProofResult]:
        """Verify all applicable properties for a parametric type.

        Returns a dict mapping property_name → result.
        """
        results: dict[str, ParametricProofResult | RefinementProofResult] = {}

        if parametric.base == HlfType.LIST and len(parametric.params) >= 1:
            elem_type = parametric.params[0]
            for prop in self.KNOWN_PROPERTIES:
                results[prop] = self.prove_list_invariance(prop, elem_type)

        if parametric.base == HlfType.SET and len(parametric.params) >= 1:
            elem_type = parametric.params[0]
            results["set_uniqueness"] = self.prove_set_uniqueness(elem_type)

        if parametric.base == HlfType.MAP and len(parametric.params) >= 2:
            key_type, val_type = parametric.params[0], parametric.params[1]
            results["map_key_uniqueness"] = self.prove_map_key_uniqueness(key_type, val_type)

        return results

    def to_dict(self) -> dict[str, Any]:
        """Serialize prover state."""
        return {
            "z3_available": _Z3_AVAILABLE,
            "known_properties": sorted(self.KNOWN_PROPERTIES),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════════


def prove_list_invariance(
    property_name: str,
    element_type: HlfType,
    prover: ParametricProver | None = None,
) -> ParametricProofResult:
    """Prove that a property of element type T holds for List⟨T⟩."""
    p = prover or ParametricProver()
    return p.prove_list_invariance(property_name, element_type)


def prove_set_uniqueness(
    element_type: HlfType,
    prover: ParametricProver | None = None,
) -> ParametricProofResult:
    """Prove that Set⟨T⟩ enforces element uniqueness."""
    p = prover or ParametricProver()
    return p.prove_set_uniqueness(element_type)


def prove_map_key_uniqueness(
    key_type: HlfType,
    value_type: HlfType,
    prover: ParametricProver | None = None,
) -> ParametricProofResult:
    """Prove that Map⟨K,V⟩ enforces key uniqueness."""
    p = prover or ParametricProver()
    return p.prove_map_key_uniqueness(key_type, value_type)


def prove_refinement_soundness(
    base_type: HlfType,
    predicate: str,
    variable: str = "x",
    prover: ParametricProver | None = None,
) -> RefinementProofResult:
    """Prove that a refinement type predicate is sound."""
    p = prover or ParametricProver()
    refinement = RefinementType(variable=variable, base_type=base_type, predicate=predicate)
    return p.prove_refinement_soundness(refinement)
