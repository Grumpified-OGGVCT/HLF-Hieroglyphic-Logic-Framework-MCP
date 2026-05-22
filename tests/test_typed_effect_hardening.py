"""
Tests for typed effect and capability algebra hardening.

Validates:
  - OperandCoverage: matrix construction, gap detection, completeness proofs
  - OperandMatrix: cell status, coverage ratio
  - ParametricProver: list invariance, set uniqueness, map key uniqueness,
    refinement soundness
  - ManifestIntegrityProof: hash consistency, capability alignment,
    trust tier validity, round-trip consistency
  - EffectCompositionProof: sequential, parallel, conditional composition
  - CrossManifestConsistency: cross-manifest checks

Total: ~28 tests
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())
os.chdir(os.path.dirname(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from hlf_mcp.hlf.operand_coverage import (
    OperandCoverage,
    OperandMatrix,
    Operator,
    OperatorFamily,
    CANONICAL_OPERATORS,
    TYPE_OPERATOR_COVERAGE,
    TYPE_EXCLUDED_OPERATORS,
    find_operand_gaps,
    prove_operand_completeness,
    generate_coverage_report,
)
from hlf_mcp.hlf.parametric_proofs import (
    ParametricProver,
    ParametricProofResult,
    RefinementProofResult,
    prove_list_invariance,
    prove_set_uniqueness,
    prove_map_key_uniqueness,
    prove_refinement_soundness,
)
from hlf_mcp.hlf.typed_contracts import (
    HlfType,
    EffectClass,
    FailureMode,
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    TypeContract,
    ProofRequirement,
    ParametricType,
    RefinementType,
)
from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    ManifestIntegrityProof,
    CrossManifestConsistency,
    prove_manifest_integrity,
    check_cross_manifest_consistency,
)
from hlf_mcp.hlf.effect_extractor import (
    EffectExtractor,
    EffectCompositionProof,
    prove_sequential_composition,
    prove_parallel_composition,
    prove_conditional_composition,
)
from hlf_mcp.hlf.compiler import HLFCompiler


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_decl(
    name: str,
    effect_class: EffectClass = EffectClass.LOCAL_ANALYSIS,
    input_type: HlfType = HlfType.STRING,
    output_type: HlfType = HlfType.STRING,
    side_effects: list[str] | None = None,
) -> TypedEffectDeclaration:
    """Create a minimal TypedEffectDeclaration for testing."""
    return TypedEffectDeclaration(
        function_name=name,
        input_contract=InputContract(
            function_name=name,
            parameters=[TypeContract(name="arg0", hlf_type=input_type)],
        ),
        output_contract=OutputContract(function_name=name, return_type=output_type),
        effect_class=effect_class,
        side_effects=side_effects or [],
    )


def _make_manifest(program_id: str = "test123") -> CapabilityManifest:
    """Create a CapabilityManifest with a single effect."""
    decl = _make_decl("test_func")
    from hlf_mcp.hlf.capability_manifest import _determine_trust_tier, _collect_required_capabilities
    return CapabilityManifest(
        program_id=program_id,
        effects=[decl],
        required_capabilities=_collect_required_capabilities([decl]),
        trust_tier=_determine_trust_tier([decl]),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# OperandCoverage tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOperandCoverageMatrix:
    """Tests for OperandCoverage matrix construction and queries."""

    def test_build_matrix_all_12_types(self):
        """Matrix covers all 12 HlfType members."""
        cov = OperandCoverage()
        matrix = cov.build_matrix()
        assert len(matrix.type_order) == 12, f"Expected 12 types, got {len(matrix.type_order)}"
        for hlf_type in HlfType:
            assert hlf_type in matrix.type_order, f"{hlf_type.name} missing from matrix"

    def test_build_matrix_all_operators(self):
        """Matrix covers all CANONICAL_OPERATORS."""
        cov = OperandCoverage()
        matrix = cov.build_matrix()
        assert len(matrix.operator_order) == len(CANONICAL_OPERATORS)

    def test_cell_status_returns_valid_string(self):
        """Every cell returns 'covered', 'gap', or 'excluded'."""
        cov = OperandCoverage()
        matrix = cov.build_matrix()
        valid = {"covered", "gap", "excluded"}
        for t in HlfType:
            for op in CANONICAL_OPERATORS:
                assert matrix.cell(t, op.name) in valid, \
                    f"Cell ({t.name}, {op.name}) returned '{matrix.cell(t, op.name)}'"

    def test_no_cell_is_both_covered_and_excluded(self):
        """No type/operator pair can be both covered and excluded."""
        for t in HlfType:
            covered = TYPE_OPERATOR_COVERAGE.get(t, set())
            excluded = TYPE_EXCLUDED_OPERATORS.get(t, set())
            overlap = covered & excluded
            assert not overlap, f"{t.name} has overlap in covered & excluded: {overlap}"

    def test_coverage_ratio_between_0_and_1(self):
        """Coverage ratio is well-formed."""
        cov = OperandCoverage()
        ratio = cov.matrix.coverage_ratio()
        assert 0.0 <= ratio <= 1.0, f"Ratio {ratio} out of [0, 1]"

    def test_covered_count_positive(self):
        """At least some cells are covered."""
        cov = OperandCoverage()
        count = cov.matrix.covered_count()
        assert count > 0, "No covered cells in matrix"

    def test_operators_for_type_on_string(self):
        """String type has expected operators."""
        cov = OperandCoverage()
        ops = cov.operators_for_type(HlfType.STRING)
        assert "concat" in ops
        assert "len" in ops
        assert "eq" in ops
        assert "add" not in ops  # String does NOT have arithmetic

    def test_operators_for_type_on_integer(self):
        """Integer type has arithmetic operators."""
        cov = OperandCoverage()
        ops = cov.operators_for_type(HlfType.INTEGER)
        assert "add" in ops
        assert "sub" in ops
        assert "mul" in ops
        assert "concat" not in ops  # Integer does NOT have string ops

    def test_types_for_operator_eq(self):
        """Equality operator is defined for all 12 types."""
        cov = OperandCoverage()
        types = cov.types_for_operator("eq")
        assert len(types) == 12, f"Expected eq on all 12 types, got {len(types)}"

    def test_operator_density_boolean_is_focused(self):
        """Boolean has high density (few operators, most covered)."""
        cov = OperandCoverage()
        density = cov.operator_density(HlfType.BOOLEAN)
        assert density >= 0.8, f"Boolean density should be high, got {density}"


class TestOperandGapDetection:
    """Tests for gap detection."""

    def test_find_operand_gaps_returns_list(self):
        """Gap detection returns a list of (type, operator, category) tuples."""
        cov = OperandCoverage()
        gaps = cov.find_operand_gaps()
        assert isinstance(gaps, list)
        for gap in gaps:
            assert isinstance(gap, tuple) and len(gap) == 3
            t, op_name, cat = gap
            assert isinstance(t, HlfType)
            assert isinstance(op_name, str)
            assert cat in ("undefined", "missing_implementation", "ambiguous")

    def test_find_operand_gaps_any_has_all_excluded(self):
        """ANY type has no excluded operators — most are gaps (runtime catch-all)."""
        cov = OperandCoverage()
        gaps = cov.find_operand_gaps()
        any_gaps = [(t, op, cat) for t, op, cat in gaps if t == HlfType.ANY]
        # ANY covers {eq, neq, not_op, cast, is_instance}, excludes nothing → 40 gaps
        assert len(any_gaps) == 40, \
            f"ANY has {len(any_gaps)} gaps (covers 5/45, excludes 0/45)"

    def test_convenience_functions_work(self):
        """find_operand_gaps() convenience function matches class method."""
        cov = OperandCoverage()
        class_gaps = cov.find_operand_gaps()
        conv_gaps = find_operand_gaps()
        assert len(class_gaps) == len(conv_gaps)


class TestOperandCompletenessProof:
    """Tests for completeness proof generation."""

    def test_prove_operand_completeness_returns_tuple(self):
        """Completeness proof returns (bool, list[str])."""
        is_complete, counterexamples = prove_operand_completeness()
        assert isinstance(is_complete, bool)
        assert isinstance(counterexamples, list)

    def test_prove_operand_completeness_on_single_type(self):
        """Check completeness for a specific type subset."""
        is_complete, cex = prove_operand_completeness(
            type_system=[HlfType.STRING, HlfType.INTEGER]
        )
        assert isinstance(is_complete, bool)
        assert isinstance(cex, list)

    def test_generate_coverage_report_contains_key_sections(self):
        """Report contains expected section headers."""
        report = generate_coverage_report()
        assert "HLF TYPE" in report and "OPERATOR COVERAGE MATRIX" in report
        assert "PER-TYPE BREAKDOWN" in report
        assert "COVERAGE" in report.upper()

    def test_operator_all_have_names(self):
        """Every canonical operator has a name."""
        for op in CANONICAL_OPERATORS:
            assert op.name, f"Operator {op} has no name"
            assert isinstance(op.name, str)

    def test_operator_family_enum(self):
        """OperatorFamily enum has expected members."""
        families = list(OperatorFamily)
        assert OperatorFamily.ARITHMETIC in families
        assert OperatorFamily.COMPARISON in families
        assert OperatorFamily.CONTAINER in families


# ═══════════════════════════════════════════════════════════════════════════════
# ParametricProver tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestParametricProver:
    """Tests for ParametricProver methods."""

    def test_prove_list_invariance_homogeneous(self):
        """List homogeneity holds — all elements are of type T."""
        result = prove_list_invariance("homogeneous", HlfType.STRING)
        assert result.holds
        assert "homogeneity" in str(result.witness).lower()

    def test_prove_list_invariance_nonempty_fails(self):
        """Non-emptiness is NOT invariant under list construction."""
        result = prove_list_invariance("non_empty", HlfType.INTEGER)
        assert not result.holds

    def test_prove_list_invariance_immutable_fails(self):
        """Immutability does NOT hold for List (append/remove exist)."""
        result = prove_list_invariance("immutable", HlfType.NUMBER)
        assert not result.holds

    def test_prove_set_uniqueness_integer(self):
        """Set⟨ℤ⟩ enforces uniqueness."""
        result = prove_set_uniqueness(HlfType.INTEGER)
        assert result.holds

    def test_prove_set_uniqueness_any_fails(self):
        """Set⟨𝔸⟩ cannot enforce uniqueness."""
        result = prove_set_uniqueness(HlfType.ANY)
        assert not result.holds

    def test_prove_map_key_uniqueness_string_key(self):
        """Map⟨𝕊,ℕ⟩ enforces key uniqueness."""
        result = prove_map_key_uniqueness(HlfType.STRING, HlfType.NUMBER)
        assert result.holds

    def test_prove_map_key_uniqueness_any_key_fails(self):
        """Map⟨𝔸,V⟩ cannot enforce key uniqueness."""
        result = prove_map_key_uniqueness(HlfType.ANY, HlfType.STRING)
        assert not result.holds

    def test_prove_refinement_soundness_positive_int(self):
        """Refinement {x: ℤ | x > 0} is satisfiable."""
        result = prove_refinement_soundness(HlfType.INTEGER, "x > 0")
        assert result.satisfiable
        assert result.sound

    def test_prove_refinement_soundness_negative_for_natural(self):
        """Refinement {x: ℕ | x < 0} is unsatisfiable."""
        result = prove_refinement_soundness(HlfType.NUMBER, "x < 0")
        assert not result.satisfiable

    def test_prove_refinement_soundness_custom_variable(self):
        """Refinement with custom variable name works."""
        result = prove_refinement_soundness(
            HlfType.INTEGER, "counter > 5", variable="counter"
        )
        assert result.satisfiable
        assert result.variable == "counter"


# ═══════════════════════════════════════════════════════════════════════════════
# Manifest Integrity Proof tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestIntegrityProofs:
    """Tests for manifest integrity proofs."""

    def test_prove_manifest_integrity_on_valid_manifest(self):
        """A valid manifest passes integrity checks."""
        m = _make_manifest("test_integrity")
        proof = prove_manifest_integrity(m)
        assert proof.hash_consistent
        assert proof.capabilities_aligned
        assert proof.trust_tier_valid
        assert proof.roundtrip_consistent
        assert proof.is_valid

    def test_prove_manifest_integrity_has_witnesses(self):
        """Integrity proof carries witness trace."""
        m = _make_manifest("test_witness")
        proof = prove_manifest_integrity(m)
        assert len(proof.witnesses) >= 3, f"Expected >=3 witnesses, got {len(proof.witnesses)}"

    def test_prove_manifest_integrity_on_empty_manifest(self):
        """Empty manifest is flagged but still structurally valid."""
        m = CapabilityManifest(program_id="empty")
        proof = prove_manifest_integrity(m)
        assert proof.hash_consistent
        assert not proof.effects_present  # Empty -> flagged
        assert proof.roundtrip_consistent

    def test_manifest_integrity_to_dict(self):
        """Integrity proof serializes correctly."""
        m = _make_manifest("test_serialize")
        proof = prove_manifest_integrity(m)
        d = proof.to_dict()
        assert d["program_id"] == "test_serialize"
        assert d["is_valid"] is True
        assert "witnesses" in d


class TestCrossManifestConsistency:
    """Tests for cross-manifest consistency checks."""

    def test_two_identical_manifests_consistent(self):
        """Two identical manifests are consistent."""
        m1 = _make_manifest("prog_a")
        m2 = _make_manifest("prog_b")
        result = check_cross_manifest_consistency(m1, m2)
        assert result.consistent

    def test_single_manifest_trivially_consistent(self):
        """A single manifest is trivially consistent."""
        m = _make_manifest("solo")
        result = check_cross_manifest_consistency(m)
        assert result.consistent
        assert result.num_manifests == 1

    def test_cross_manifest_returns_witnesses(self):
        """Cross-manifest check returns witness trace."""
        m1 = _make_manifest("prog_a")
        m2 = _make_manifest("prog_b")
        result = check_cross_manifest_consistency(m1, m2)
        assert len(result.witnesses) > 0

    def test_cross_manifest_to_dict(self):
        """CrossManifestConsistency serializes correctly."""
        m1 = _make_manifest("prog_a")
        m2 = _make_manifest("prog_b")
        result = check_cross_manifest_consistency(m1, m2)
        d = result.to_dict()
        assert d["consistent"] is True
        assert d["num_manifests"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Effect Composition Proof tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEffectCompositionProofs:
    """Tests for effect composition proofs."""

    def test_sequential_composition_trivial(self):
        """Single effect is vacuously sound."""
        effects = [_make_decl("step1", effect_class=EffectClass.LOCAL_ANALYSIS)]
        result = prove_sequential_composition(effects)
        assert result.is_valid

    def test_sequential_composition_compatible(self):
        """Two compatible effects produce valid proof."""
        effects = [
            _make_decl("read", EffectClass.FILE_READ, HlfType.STRING, HlfType.STRING),
            _make_decl("analyze", EffectClass.LOCAL_ANALYSIS, HlfType.STRING, HlfType.STRING),
        ]
        result = prove_sequential_composition(effects)
        assert result.well_typed

    def test_parallel_composition_no_conflicts(self):
        """Non-mutating parallel effects are safe."""
        effects = [
            _make_decl("read_a", EffectClass.FILE_READ),
            _make_decl("read_b", EffectClass.MEMORY_READ),
        ]
        result = prove_parallel_composition(effects)
        assert result.effect_safe

    def test_parallel_composition_conflicting_writes(self):
        """Mutating parallel effects to same resource are unsafe."""
        effects = [
            _make_decl("write_a", EffectClass.FILE_WRITE,
                       side_effects=["filesystem:write"]),
            _make_decl("write_b", EffectClass.FILE_WRITE,
                       side_effects=["filesystem:write"]),
        ]
        result = prove_parallel_composition(effects)
        assert not result.effect_safe

    def test_conditional_composition_empty_branches(self):
        """Empty conditional is vacuously sound."""
        result = prove_conditional_composition("test_cond", [], [])
        assert result.is_valid

    def test_composition_proof_to_dict(self):
        """Composition proof serializes."""
        effects = [_make_decl("step")]
        result = prove_sequential_composition(effects)
        d = result.to_dict()
        assert d["composition_kind"] == "sequential"
        assert d["is_valid"] is True
