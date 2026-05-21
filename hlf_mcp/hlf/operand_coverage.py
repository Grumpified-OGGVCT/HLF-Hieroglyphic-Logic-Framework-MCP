"""
Operand Coverage Proofs — systematic verification that every type in the
12-type HLF universe has complete operator definitions.

This module provides the machinery to check that every HlfType → operator
combination is defined, producing coverage matrices, gap reports, and
formal completeness proofs.

Types in the 12-type universe:
    Primitive (8):   ℕ(NUMBER)  𝕊(STRING)  𝔹(BOOLEAN)  𝕁(JSON)  𝔸(ANY)
                     ℤ(INTEGER)  ℝ(REAL)  ℚ(RATIONAL)
    Parametric (3):  List⟨T⟩  Set⟨T⟩  Map⟨K,V⟩
    Refinement (1):  {var: T | pred}

Operator families:
    Arithmetic : add, sub, mul, div, mod, neg, pow
    Comparison : eq, neq, lt, gt, leq, geq
    Logical    : and_op, or_op, not_op
    Container  : len, get, set, contains, append, remove, keys, values
    Set-specific: union, intersection, difference, subset
    Type ops   : cast, is_instance

Integration:
    - hlf_mcp.hlf.typed_contracts.HlfType
    - hlf_mcp.hlf.parametric_proofs.ParametricProver
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from hlf_mcp.hlf.typed_contracts import HlfType


# ═══════════════════════════════════════════════════════════════════════════════
# Operator taxonomy
# ═══════════════════════════════════════════════════════════════════════════════


class OperatorFamily(Enum):
    """Taxonomic families of operators in the HLF type system."""
    ARITHMETIC = auto()
    COMPARISON = auto()
    LOGICAL = auto()
    CONTAINER = auto()
    SET_THEORY = auto()
    TYPE_OPS = auto()
    STRING_OPS = auto()  # concat, slice, format, etc.
    JSON_OPS = auto()     # merge, project, keys, values, etc.
    MAP_OPS = auto()      # lookup, insert, delete, etc.
    RATIONAL_OPS = auto() # numer, denom, simplify, etc.


# ═══════════════════════════════════════════════════════════════════════════════
# Canonical operator set — the complete list of operators that MUST be checked
# against every type
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Operator:
    """A single operator in the HLF type system.

    Carries its canonical name, family, arity, and whether it is a
    mutating or pure operator.
    """
    name: str
    family: OperatorFamily
    arity: int = 2  # 1 = unary, 2 = binary
    mutating: bool = False
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Operator):
            return self.name == other.name
        return NotImplemented

    def __repr__(self) -> str:
        return f"Op({self.name!r})"


# ═══════════════════════════════════════════════════════════════════════════════
# The complete operator catalog — every operator the HLF type system supports
# ═══════════════════════════════════════════════════════════════════════════════


CANONICAL_OPERATORS: list[Operator] = [
    # ── Arithmetic ──────────────────────────────────────────────────────────
    Operator("add", OperatorFamily.ARITHMETIC, 2, False, "Addition: a + b"),
    Operator("sub", OperatorFamily.ARITHMETIC, 2, False, "Subtraction: a - b"),
    Operator("mul", OperatorFamily.ARITHMETIC, 2, False, "Multiplication: a * b"),
    Operator("div", OperatorFamily.ARITHMETIC, 2, False, "Division: a / b"),
    Operator("mod", OperatorFamily.ARITHMETIC, 2, False, "Modulo: a % b"),
    Operator("neg", OperatorFamily.ARITHMETIC, 1, False, "Negation: -a"),
    Operator("pow", OperatorFamily.ARITHMETIC, 2, False, "Exponentiation: a ^ b"),

    # ── Comparison ──────────────────────────────────────────────────────────
    Operator("eq", OperatorFamily.COMPARISON, 2, False, "Equality: a == b"),
    Operator("neq", OperatorFamily.COMPARISON, 2, False, "Inequality: a != b"),
    Operator("lt", OperatorFamily.COMPARISON, 2, False, "Less than: a < b"),
    Operator("gt", OperatorFamily.COMPARISON, 2, False, "Greater than: a > b"),
    Operator("leq", OperatorFamily.COMPARISON, 2, False, "Less or equal: a <= b"),
    Operator("geq", OperatorFamily.COMPARISON, 2, False, "Greater or equal: a >= b"),

    # ── Logical ─────────────────────────────────────────────────────────────
    Operator("and_op", OperatorFamily.LOGICAL, 2, False, "Logical AND: a && b"),
    Operator("or_op", OperatorFamily.LOGICAL, 2, False, "Logical OR: a || b"),
    Operator("not_op", OperatorFamily.LOGICAL, 1, False, "Logical NOT: !a"),

    # ── Container ───────────────────────────────────────────────────────────
    Operator("len", OperatorFamily.CONTAINER, 1, False, "Length/size"),
    Operator("get", OperatorFamily.CONTAINER, 2, False, "Index/field access"),
    Operator("set", OperatorFamily.CONTAINER, 3, True, "Mutable index/field set"),
    Operator("contains", OperatorFamily.CONTAINER, 2, False, "Membership test"),
    Operator("append", OperatorFamily.CONTAINER, 2, True, "Append element"),
    Operator("remove", OperatorFamily.CONTAINER, 2, True, "Remove element"),
    Operator("keys", OperatorFamily.CONTAINER, 1, False, "Enumerate keys/indices"),
    Operator("values", OperatorFamily.CONTAINER, 1, False, "Enumerate values"),

    # ── Set theory ──────────────────────────────────────────────────────────
    Operator("union", OperatorFamily.SET_THEORY, 2, False, "Set union"),
    Operator("intersection", OperatorFamily.SET_THEORY, 2, False, "Set intersection"),
    Operator("difference", OperatorFamily.SET_THEORY, 2, False, "Set difference"),
    Operator("subset", OperatorFamily.SET_THEORY, 2, False, "Subset test"),

    # ── String-specific ─────────────────────────────────────────────────────
    Operator("concat", OperatorFamily.STRING_OPS, 2, False, "String concatenation"),
    Operator("slice", OperatorFamily.STRING_OPS, 3, False, "String slicing"),
    Operator("format", OperatorFamily.STRING_OPS, 2, False, "String formatting"),
    Operator("upper", OperatorFamily.STRING_OPS, 1, False, "Uppercase"),
    Operator("lower", OperatorFamily.STRING_OPS, 1, False, "Lowercase"),
    Operator("split", OperatorFamily.STRING_OPS, 2, False, "String split"),

    # ── JSON-specific ───────────────────────────────────────────────────────
    Operator("merge", OperatorFamily.JSON_OPS, 2, False, "JSON merge"),
    Operator("project", OperatorFamily.JSON_OPS, 2, False, "JSON field projection"),
    Operator("flatten", OperatorFamily.JSON_OPS, 1, False, "JSON flatten"),

    # ── Map-specific ────────────────────────────────────────────────────────
    Operator("lookup", OperatorFamily.MAP_OPS, 2, False, "Map key lookup"),
    Operator("insert", OperatorFamily.MAP_OPS, 3, True, "Map key insertion"),
    Operator("delete", OperatorFamily.MAP_OPS, 2, True, "Map key deletion"),

    # ── Rational-specific ───────────────────────────────────────────────────
    Operator("numer", OperatorFamily.RATIONAL_OPS, 1, False, "Rational numerator"),
    Operator("denom", OperatorFamily.RATIONAL_OPS, 1, False, "Rational denominator"),
    Operator("simplify", OperatorFamily.RATIONAL_OPS, 1, False, "Rational simplification"),

    # ── Type operations ─────────────────────────────────────────────────────
    Operator("cast", OperatorFamily.TYPE_OPS, 2, False, "Type cast"),
    Operator("is_instance", OperatorFamily.TYPE_OPS, 2, False, "Type instance check"),
]

CANONICAL_OPERATORS_BY_NAME: dict[str, Operator] = {op.name: op for op in CANONICAL_OPERATORS}


# ═══════════════════════════════════════════════════════════════════════════════
# Type × Operator coverage rules
# ═══════════════════════════════════════════════════════════════════════════════
#
# For each type, we define which operators are semantically valid.
# An operator is "covered" for a type if it is either:
#   1. Defined as applicable (present in the type's operator set), OR
#   2. Explicitly excluded as semantically meaningless (noted as gap)

# Type → set of applicable operator names
TYPE_OPERATOR_COVERAGE: dict[HlfType, set[str]] = {
    # ── ℕ (NUMBER) — natural numbers ────────────────────────────────────
    HlfType.NUMBER: {
        "add", "sub", "mul", "div", "mod", "neg", "pow",
        "eq", "neq", "lt", "gt", "leq", "geq",
        "len",  # digit count
        "not_op",  # truthiness: 0 is falsy
        "cast", "is_instance",
    },
    # ── ℤ (INTEGER) — signed integers ───────────────────────────────────
    HlfType.INTEGER: {
        "add", "sub", "mul", "div", "mod", "neg", "pow",
        "eq", "neq", "lt", "gt", "leq", "geq",
        "len",  # digit count
        "not_op",  # truthiness: 0 is falsy
        "cast", "is_instance",
    },
    # ── ℝ (REAL) — floating-point numbers ───────────────────────────────
    HlfType.REAL: {
        "add", "sub", "mul", "div", "neg", "pow",
        "eq", "neq", "lt", "gt", "leq", "geq",
        "len",  # digit count (integer part)
        "not_op",  # truthiness: 0.0 is falsy
        "cast", "is_instance",
    },
    # ── ℚ (RATIONAL) — exact rational numbers ───────────────────────────
    HlfType.RATIONAL: {
        "add", "sub", "mul", "div", "neg",
        "eq", "neq", "lt", "gt", "leq", "geq",
        "numer", "denom", "simplify",
        "cast", "is_instance",
    },
    # ── 𝕊 (STRING) ──────────────────────────────────────────────────────
    HlfType.STRING: {
        "eq", "neq", "lt", "gt", "leq", "geq",
        "len", "get", "contains",
        "concat", "slice", "format", "upper", "lower", "split",
        "not_op",  # truthiness: empty string is falsy
        "cast", "is_instance",
    },
    # ── 𝔹 (BOOLEAN) ─────────────────────────────────────────────────────
    HlfType.BOOLEAN: {
        "eq", "neq",
        "and_op", "or_op", "not_op",
        "cast", "is_instance",
    },
    # ── 𝕁 (JSON) — JSON objects/arrays ──────────────────────────────────
    HlfType.JSON: {
        "eq", "neq",
        "len", "get", "set", "contains",
        "keys", "values",
        "merge", "project", "flatten",
        "slice",   # JSON array slicing
        "cast", "is_instance",
    },
    # ── 𝔸 (ANY) — wildcard type ─────────────────────────────────────────
    HlfType.ANY: {
        "eq", "neq",
        "not_op",  # truthiness: falsy values exist in every type
        "cast", "is_instance",
    },
    # ── List⟨T⟩ ─────────────────────────────────────────────────────────
    HlfType.LIST: {
        "eq", "neq", "lt", "gt", "leq", "geq",  # lexicographic ordering
        "len", "get", "set", "contains",
        "append", "remove",
        "keys",  # returns indices
        "values",
        "concat",  # list concatenation
        "slice",   # sublist extraction
        "union", "intersection", "difference", "subset",  # list set operations
        "cast", "is_instance",
    },
    # ── Set⟨T⟩ ──────────────────────────────────────────────────────────
    HlfType.SET: {
        "eq", "neq", "lt", "gt", "leq", "geq",  # size-based/subset ordering
        "len", "contains",
        "append",  # add element
        "remove",
        "keys",    # enumerate elements (same as values for sets)
        "union", "intersection", "difference", "subset",
        "values",
        "cast", "is_instance",
    },
    # ── Map⟨K,V⟩ ────────────────────────────────────────────────────────
    HlfType.MAP: {
        "eq", "neq", "lt", "gt", "leq", "geq",  # key-set lexicographic ordering
        "len", "contains",
        "keys", "values",
        "get", "set",
        "lookup", "insert", "delete",
        "merge",   # map merging
        "cast", "is_instance",
    },
    # ── REFINEMENT {var: T | pred} ──────────────────────────────────────
    HlfType.REFINEMENT: {
        "eq", "neq",
        "not_op",  # delegates to base type truthiness
        "cast", "is_instance",
    },
}


# Type → explicitly excluded operators (semantically meaningless)
TYPE_EXCLUDED_OPERATORS: dict[HlfType, set[str]] = {
    HlfType.NUMBER: {"and_op", "or_op", "concat", "slice", "format",
                     "upper", "lower", "split", "merge", "project", "flatten",
                     "union", "intersection", "difference", "subset",
                     "lookup", "insert", "delete", "numer", "denom", "simplify", "set",
                     "get", "contains", "append", "remove", "keys", "values"},
    HlfType.INTEGER: {"and_op", "or_op", "concat", "slice", "format",
                      "upper", "lower", "split", "merge", "project", "flatten",
                      "union", "intersection", "difference", "subset",
                      "lookup", "insert", "delete", "numer", "denom", "simplify", "set",
                      "get", "contains", "append", "remove", "keys", "values"},
    HlfType.REAL: {"and_op", "or_op", "mod", "concat", "slice", "format",
                   "upper", "lower", "split", "merge", "project", "flatten",
                   "union", "intersection", "difference", "subset",
                   "lookup", "insert", "delete", "numer", "denom", "simplify", "set",
                   "get", "contains", "append", "remove", "keys", "values"},
    HlfType.RATIONAL: {"and_op", "or_op", "not_op", "mod", "pow",
                       "concat", "slice", "format", "upper", "lower", "split",
                       "merge", "project", "flatten",
                       "union", "intersection", "difference", "subset",
                       "lookup", "insert", "delete", "set",
                       "len", "get", "contains", "keys", "values",
                       "append", "remove"},
    HlfType.STRING: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                     "and_op", "or_op",
                     "set", "append", "remove", "keys", "values",
                     "union", "intersection", "difference", "subset",
                     "merge", "project", "flatten",
                     "lookup", "insert", "delete", "numer", "denom", "simplify"},
    HlfType.BOOLEAN: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                      "lt", "gt", "leq", "geq",
                      "len", "get", "set", "contains", "append", "remove",
                      "keys", "values",
                      "concat", "slice", "format", "upper", "lower", "split",
                      "union", "intersection", "difference", "subset",
                      "merge", "project", "flatten",
                      "lookup", "insert", "delete", "numer", "denom", "simplify"},
    HlfType.JSON: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                   "and_op", "or_op", "not_op",
                   "lt", "gt", "leq", "geq",
                   "concat", "format", "upper", "lower", "split",
                   "append", "remove",
                   "union", "intersection", "difference", "subset",
                   "lookup", "insert", "delete", "numer", "denom", "simplify"},
    HlfType.ANY: set(),  # ANY can receive anything at runtime — nothing excluded
    HlfType.LIST: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                   "and_op", "or_op", "not_op",
                   "format", "upper", "lower", "split",
                   "merge", "project", "flatten",
                   "lookup", "insert", "delete", "numer", "denom", "simplify"},
    HlfType.SET: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                  "and_op", "or_op", "not_op",
                  "get", "set",
                  "concat", "slice", "format", "upper", "lower", "split",
                  "merge", "project", "flatten",
                  "lookup", "insert", "delete", "numer", "denom", "simplify"},
    HlfType.MAP: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                  "and_op", "or_op", "not_op",
                  "append", "remove",
                  "concat", "slice", "format", "upper", "lower", "split",
                  "union", "intersection", "difference", "subset",
                  "project", "flatten",
                  "numer", "denom", "simplify"},
    HlfType.REFINEMENT: {"add", "sub", "mul", "div", "mod", "neg", "pow",
                         "lt", "gt", "leq", "geq",
                         "and_op", "or_op",
                         "len", "get", "set", "contains", "append", "remove",
                         "keys", "values",
                         "concat", "slice", "format", "upper", "lower", "split",
                         "union", "intersection", "difference", "subset",
                         "merge", "project", "flatten",
                         "lookup", "insert", "delete", "numer", "denom", "simplify"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# OperandMatrix — type × operator grid
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OperandMatrix:
    """A type × operator grid tracking which (type, operator) pairs are defined.

    Each cell in the matrix has one of three states:
        - "covered": the operator is defined and applicable for this type
        - "gap": the operator is semantically meaningful but NOT defined
        - "excluded": the operator is semantically meaningless for this type

    The matrix is lazy-built from TYPE_OPERATOR_COVERAGE and
    TYPE_EXCLUDED_OPERATORS.
    """
    covered: dict[tuple[HlfType, str], bool] = field(default_factory=dict)
    excluded: dict[tuple[HlfType, str], bool] = field(default_factory=dict)
    type_order: tuple[HlfType, ...] = field(default_factory=tuple)
    operator_order: tuple[str, ...] = field(default_factory=tuple)

    def cell(self, hlf_type: HlfType, operator_name: str) -> str:
        """Return the cell status: 'covered', 'gap', or 'excluded'."""
        if (hlf_type, operator_name) in self.covered:
            return "covered"
        if (hlf_type, operator_name) in self.excluded:
            return "excluded"
        return "gap"

    def covered_count(self) -> int:
        """Total number of covered (type, operator) pairs."""
        return sum(1 for v in self.covered.values() if v)

    def gap_count(self) -> int:
        """Total number of gap cells (semantically meaningful but undefined)."""
        total_cells = len(self.type_order) * len(self.operator_order)
        covered = self.covered_count()
        excluded = sum(1 for v in self.excluded.values() if v)
        return total_cells - covered - excluded

    def coverage_ratio(self) -> float:
        """Fraction of semantically meaningful cells that are covered."""
        meaningful = len(self.type_order) * len(self.operator_order) - sum(1 for v in self.excluded.values() if v)
        if meaningful == 0:
            return 1.0
        return self.covered_count() / meaningful


# ═══════════════════════════════════════════════════════════════════════════════
# OperandCoverage — main coverage analysis class
# ═══════════════════════════════════════════════════════════════════════════════


class OperandCoverage:
    """Systematic operand coverage analysis for the 12-type HLF universe.

    Usage::

        cov = OperandCoverage()
        # Build the matrix
        matrix = cov.build_matrix()
        # Find gaps
        gaps = cov.find_operand_gaps()
        # Prove completeness
        proof = cov.prove_operand_completeness()
        # Generate human-readable report
        report = cov.generate_coverage_report()
    """

    def __init__(self, operators: list[Operator] | None = None) -> None:
        """Initialize with the canonical operator set.

        Args:
            operators: Override operator set (defaults to CANONICAL_OPERATORS).
        """
        self._operators = operators or CANONICAL_OPERATORS
        self._operator_names = [op.name for op in self._operators]
        self._types: list[HlfType] = list(HlfType)
        self._matrix: OperandMatrix | None = None

    # ── Matrix construction ────────────────────────────────────────────────

    def build_matrix(self) -> OperandMatrix:
        """Build the full type × operator coverage matrix.

        Populates covered and excluded cells from the canonical
        TYPE_OPERATOR_COVERAGE and TYPE_EXCLUDED_OPERATORS tables.
        """
        matrix = OperandMatrix(
            type_order=tuple(self._types),
            operator_order=tuple(self._operator_names),
        )

        for hlf_type in self._types:
            covered_ops = TYPE_OPERATOR_COVERAGE.get(hlf_type, set())
            excluded_ops = TYPE_EXCLUDED_OPERATORS.get(hlf_type, set())

            for op_name in self._operator_names:
                if op_name in covered_ops:
                    matrix.covered[(hlf_type, op_name)] = True
                elif op_name in excluded_ops:
                    matrix.excluded[(hlf_type, op_name)] = True
                # else: remains as "gap"

        self._matrix = matrix
        return matrix

    @property
    def matrix(self) -> OperandMatrix:
        """Return the cached matrix, building it on first access."""
        if self._matrix is None:
            self.build_matrix()
        assert self._matrix is not None
        return self._matrix

    # ── Gap detection ──────────────────────────────────────────────────────

    def find_operand_gaps(self) -> list[tuple[HlfType, str, str]]:
        """Find all (type, operator) pairs that are undefined but semantically meaningful.

        Returns:
            List of (HlfType, operator_name, gap_category) tuples where:
            - gap_category is one of 'undefined', 'missing_implementation', 'ambiguous'

            A gap is "semantically meaningful" when the operator is NOT in the
            type's excluded set — meaning it could reasonably apply to that type
            but no definition exists.
        """
        matrix = self.matrix
        gaps: list[tuple[HlfType, str, str]] = []

        for hlf_type in self._types:
            for op_name in self._operator_names:
                cell = matrix.cell(hlf_type, op_name)
                if cell == "gap":
                    # Categorize: is this a missing implementation or truly undefined?
                    op = CANONICAL_OPERATORS_BY_NAME.get(op_name)
                    category = "undefined"
                    if op is not None:
                        # Check if similar types have this operator
                        covered_by_siblings = self._is_covered_by_any(
                            self._sibling_types(hlf_type), op_name
                        )
                        if covered_by_siblings:
                            category = "missing_implementation"
                        elif self._is_partially_applicable(hlf_type, op):
                            category = "ambiguous"
                    gaps.append((hlf_type, op_name, category))
        return gaps

    def _sibling_types(self, hlf_type: HlfType) -> list[HlfType]:
        """Return types in the same semantic family."""
        numeric = {HlfType.NUMBER, HlfType.INTEGER, HlfType.REAL, HlfType.RATIONAL}
        container = {HlfType.LIST, HlfType.SET, HlfType.MAP}
        scalar = {HlfType.STRING, HlfType.BOOLEAN}

        if hlf_type in numeric:
            return [t for t in numeric if t != hlf_type]
        if hlf_type in container:
            return [t for t in container if t != hlf_type]
        if hlf_type in scalar:
            return [t for t in scalar if t != hlf_type]
        return []

    def _is_covered_by_any(self, types: list[HlfType], op_name: str) -> bool:
        """Check if any of the given types cover this operator."""
        matrix = self.matrix
        for t in types:
            if matrix.cell(t, op_name) == "covered":
                return True
        return False

    @staticmethod
    def _is_partially_applicable(hlf_type: HlfType, op: Operator) -> bool:
        """Check if an operator could plausibly apply (e.g. 'len' on integers)."""
        # Heuristic: operators that are widely applicable across domains
        widely_applicable = {"len", "eq", "neq", "cast", "is_instance"}
        if op.name in widely_applicable:
            return True
        # Numeric ops on non-numeric types
        if op.family == OperatorFamily.ARITHMETIC:
            return False  # Not partially applicable — full mismatch
        return False

    # ── Completeness proof ─────────────────────────────────────────────────

    def prove_operand_completeness(
        self,
        type_system: list[HlfType] | None = None,
    ) -> tuple[bool, list[str]]:
        """Prove (or find counterexample) that every type has full operator coverage.

        Args:
            type_system: Types to check (defaults to all 12 HlfType members).

        Returns:
            (is_complete, list_of_counterexamples) where counterexamples
            are human-readable descriptions of missing coverage.
        """
        types_to_check = type_system or self._types
        matrix = self.matrix
        counterexamples: list[str] = []

        for hlf_type in types_to_check:
            covered = TYPE_OPERATOR_COVERAGE.get(hlf_type, set())
            excluded = TYPE_EXCLUDED_OPERATORS.get(hlf_type, set())
            total = set(self._operator_names)

            # Operators that are neither covered nor excluded are gaps
            gaps = total - covered - excluded

            if gaps:
                gap_ops = [CANONICAL_OPERATORS_BY_NAME.get(g) for g in gaps]
                gap_details: list[str] = []
                for g, op in zip(sorted(gaps), gap_ops):
                    family = op.family.name if op else "unknown"
                    gap_details.append(f"  - {g} ({family})")
                counterexamples.append(
                    f"{hlf_type.name} ({hlf_type.glyph}): missing {len(gaps)} operators:\n"
                    + "\n".join(gap_details)
                )

        is_complete = len(counterexamples) == 0
        return is_complete, counterexamples

    # ── Coverage report ────────────────────────────────────────────────────

    def generate_coverage_report(self) -> str:
        """Generate a human-readable coverage matrix report.

        Returns a multi-line string with a formatted table showing
        coverage status for every (type, operator) combination.
        """
        matrix = self.matrix
        lines: list[str] = []
        lines.append("=" * 80)
        lines.append("HLF TYPE × OPERATOR COVERAGE MATRIX")
        lines.append("=" * 80)
        lines.append("")

        # Summary statistics
        total_cells = len(self._types) * len(self._operator_names)
        covered = matrix.covered_count()
        excluded = sum(1 for v in matrix.excluded.values() if v)
        gaps = total_cells - covered - excluded
        meaningful = total_cells - excluded

        lines.append(f"Types:     {len(self._types)}")
        lines.append(f"Operators: {len(self._operator_names)}")
        lines.append(f"Total cells: {total_cells}")
        lines.append(f"  Covered:   {covered} ({100*covered/total_cells:.1f}%)")
        lines.append(f"  Excluded:  {excluded} ({100*excluded/total_cells:.1f}%)")
        if gaps > 0:
            lines.append(f"  GAPS:      {gaps} ({100*gaps/total_cells:.1f}%) ⚠")
        else:
            lines.append(f"  Gaps:      {gaps}")
        lines.append(f"Coverage ratio (meaningful cells): {matrix.coverage_ratio():.1%}")
        lines.append("")

        # Per-type breakdown
        lines.append("-" * 80)
        lines.append("PER-TYPE BREAKDOWN")
        lines.append("-" * 80)

        for hlf_type in self._types:
            type_covered = sum(1 for op in self._operator_names
                              if matrix.cell(hlf_type, op) == "covered")
            type_excluded = sum(1 for op in self._operator_names
                               if matrix.cell(hlf_type, op) == "excluded")
            type_gaps = len(self._operator_names) - type_covered - type_excluded
            type_meaningful = len(self._operator_names) - type_excluded
            ratio = type_covered / type_meaningful if type_meaningful > 0 else 1.0

            status = "✓ COMPLETE" if type_gaps == 0 else f"⚠ {type_gaps} GAPS"
            lines.append(
                f"  {hlf_type.name:<12} {hlf_type.glyph}  "
                f"covered={type_covered:>2}/{type_meaningful:>2} "
                f"({ratio:.0%})  excluded={type_excluded:>2}  {status}"
            )

        # Gap details if any
        gap_list = self.find_operand_gaps()
        if gap_list:
            lines.append("")
            lines.append("-" * 80)
            lines.append("GAP DETAILS")
            lines.append("-" * 80)
            by_type: dict[HlfType, list[tuple[str, str]]] = {}
            for t, op_name, cat in gap_list:
                by_type.setdefault(t, []).append((op_name, cat))
            for t in sorted(by_type, key=lambda x: x.name):
                ops = by_type[t]
                lines.append(f"  {t.name} ({t.glyph}): {len(ops)} gaps")
                for op_name, cat in ops:
                    lines.append(f"    - {op_name} [{cat}]")

        lines.append("")
        lines.append("=" * 80)
        lines.append("COVERAGE COMPLETE" if len(gap_list) == 0 else
                     f"COVERAGE INCOMPLETE — {len(gap_list)} gaps remaining")
        lines.append("=" * 80)

        return "\n".join(lines)

    # ── Specific coverage queries ──────────────────────────────────────────

    def is_covered(self, hlf_type: HlfType, operator_name: str) -> bool:
        """Check whether a specific (type, operator) pair is covered."""
        return self.matrix.cell(hlf_type, operator_name) == "covered"

    def operators_for_type(self, hlf_type: HlfType) -> list[str]:
        """List all operators defined for a given type."""
        return sorted(
            op for op in self._operator_names
            if self.matrix.cell(hlf_type, op) == "covered"
        )

    def types_for_operator(self, operator_name: str) -> list[HlfType]:
        """List all types that define a given operator."""
        return sorted(
            (t for t in self._types
             if self.matrix.cell(t, operator_name) == "covered"),
            key=lambda t: t.value,
        )

    def operator_density(self, hlf_type: HlfType) -> float:
        """Fraction of semantically meaningful operators covered for a type."""
        excluded = sum(1 for op in self._operator_names
                       if self.matrix.cell(hlf_type, op) == "excluded")
        meaningful = len(self._operator_names) - excluded
        if meaningful == 0:
            return 1.0
        covered = sum(1 for op in self._operator_names
                      if self.matrix.cell(hlf_type, op) == "covered")
        return covered / meaningful

    def to_dict(self) -> dict[str, Any]:
        """Serialize the coverage analysis to a JSON-compatible dict."""
        matrix = self.matrix
        return {
            "num_types": len(self._types),
            "num_operators": len(self._operator_names),
            "covered_count": matrix.covered_count(),
            "gap_count": matrix.gap_count(),
            "coverage_ratio": matrix.coverage_ratio(),
            "per_type": {
                t.name: {
                    "glyph": t.glyph,
                    "covered": len(self.operators_for_type(t)),
                    "excluded": sum(1 for op in self._operator_names
                                    if matrix.cell(t, op) == "excluded"),
                    "density": self.operator_density(t),
                }
                for t in self._types
            },
            "gaps": [
                {"type": t.name, "operator": op, "category": cat}
                for t, op, cat in self.find_operand_gaps()
            ],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience functions
# ═══════════════════════════════════════════════════════════════════════════════


def find_operand_gaps(coverage: OperandCoverage | None = None) -> list[tuple[HlfType, str, str]]:
    """Find all (type, operator) pairs that are semantically meaningful but undefined.

    Convenience wrapper around OperandCoverage.find_operand_gaps().
    """
    cov = coverage or OperandCoverage()
    return cov.find_operand_gaps()


def prove_operand_completeness(
    type_system: list[HlfType] | None = None,
    coverage: OperandCoverage | None = None,
) -> tuple[bool, list[str]]:
    """Prove full operand coverage or return counterexamples.

    Convenience wrapper around OperandCoverage.prove_operand_completeness().
    """
    cov = coverage or OperandCoverage()
    return cov.prove_operand_completeness(type_system)


def generate_coverage_report(coverage: OperandCoverage | None = None) -> str:
    """Generate a human-readable coverage matrix report.

    Convenience wrapper around OperandCoverage.generate_coverage_report().
    """
    cov = coverage or OperandCoverage()
    return cov.generate_coverage_report()
