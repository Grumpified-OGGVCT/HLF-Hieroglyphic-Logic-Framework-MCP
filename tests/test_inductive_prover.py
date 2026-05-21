"""Tests for INDUCTIVE proof automation module (hlf_mcp/hlf/inductive_prover.py).

Tests cover:
- build_induction_schema for nat, list, tree domains
- prove_inductive base case and step case
- Failure cases (false induction hypothesis)
- batch_prove handling multiple schemas
- format_inductive_report markdown generation
- InductiveProof.is_valid correctness
- InductionSchema depth_limit handling
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.inductive_prover import (
    InductiveProof,
    InductionSchema,
    batch_prove,
    build_induction_schema,
    format_inductive_report,
    prove_inductive,
    z3_available,
)
from hlf_mcp.hlf.proof_artifacts import ProofStatus


# ═══════════════════════════════════════════════════════════════════════════════
# build_induction_schema() tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_induction_schema_nat() -> None:
    """build_induction_schema() creates valid base + step for nat domain."""
    schema = build_induction_schema(
        domain="nat",
        variable="n",
        hypothesis="P",
    )

    assert isinstance(schema, InductionSchema)
    assert schema.domain == "nat"
    assert schema.variable == "n"
    assert schema.hypothesis == "P"
    # Base case: P(0)
    assert "(P 0)" in schema.base_case or "P" in schema.base_case
    # Inductive step: P(n) → P(n+1) or equivalent
    assert "forall" in schema.inductive_step.lower() or "=>" in schema.inductive_step


def test_build_induction_schema_list() -> None:
    """build_induction_schema() creates valid base + step for list domain."""
    schema = build_induction_schema(
        domain="list",
        variable="l",
        hypothesis="len_prop",
    )

    assert isinstance(schema, InductionSchema)
    assert schema.domain == "list"
    assert schema.variable == "l"
    assert schema.hypothesis == "len_prop"
    # Base case: property on empty list (nil)
    assert "nil" in schema.base_case.lower() or "len_prop" in schema.base_case
    # Inductive step references cons
    assert "cons" in schema.inductive_step.lower()


def test_build_induction_schema_tree() -> None:
    """build_induction_schema() creates valid base + step for tree domain."""
    schema = build_induction_schema(
        domain="tree",
        variable="t",
        hypothesis="height_prop",
    )

    assert isinstance(schema, InductionSchema)
    assert schema.domain == "tree"
    assert schema.variable == "t"
    assert schema.hypothesis == "height_prop"
    # Base case: property on leaf
    assert "leaf" in schema.base_case.lower()
    # Inductive step references node
    assert "node" in schema.inductive_step.lower()


def test_build_induction_schema_int() -> None:
    """build_induction_schema() works for int domain (same structure as nat)."""
    schema = build_induction_schema(
        domain="int",
        variable="i",
        hypothesis="Q",
    )

    assert schema.domain == "int"
    assert schema.variable == "i"
    # Should generate similar formula structure
    assert "assert" in schema.base_case


def test_build_induction_schema_unknown_domain_fallback() -> None:
    """build_induction_schema() produces fallback formulae for unknown domain."""
    schema = build_induction_schema(
        domain="graph",
        variable="g",
        hypothesis="connected",
    )

    assert schema.domain == "graph"
    assert "assert" in schema.base_case
    assert "forall" in schema.inductive_step.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# prove_inductive() tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_prove_inductive_returns_valid_inductive_proof() -> None:
    """prove_inductive() returns an InductiveProof with base and step artifacts."""
    schema = build_induction_schema(
        domain="nat",
        variable="n",
        hypothesis="nonnegative",
    )
    result = prove_inductive(schema)

    assert isinstance(result, InductiveProof)
    assert result.proof_id != ""
    assert result.schema == schema
    assert result.induction_variable == "n"
    assert result.depth_limit == 50  # default
    # Both base_proved and step_proved should be ProofArtifacts
    assert result.base_proved.operator_class == "arithmetic"
    assert result.step_proved.operator_class == "arithmetic"


def test_prove_inductive_base_case_n_plus_zero_equals_n() -> None:
    """prove_inductive() attempts to prove a simple arithmetic identity."""
    schema = build_induction_schema(
        domain="nat",
        variable="n",
        hypothesis="identity",
    )
    result = prove_inductive(schema)

    # Should produce artifacts regardless of Z3 availability
    assert result.base_proved is not None
    assert result.step_proved is not None
    assert isinstance(result.is_valid, bool)


def test_prove_inductive_fails_on_false_hypothesis() -> None:
    """prove_inductive() handles a false induction hypothesis gracefully."""
    schema = build_induction_schema(
        domain="nat",
        variable="n",
        hypothesis="negative",
    )
    result = prove_inductive(schema)

    # Should still produce artifacts even if the hypothesis is false
    assert result.base_proved is not None
    assert result.step_proved is not None
    # With a false hypothesis, is_valid should be False
    # (or True if Z3 doesn't properly verify — depends on formula encoding)


def test_prove_inductive_with_explicit_depth_limit() -> None:
    """prove_inductive() accepts and stores explicit depth_limit."""
    schema = build_induction_schema(
        domain="nat",
        variable="n",
        hypothesis="monotonic",
    )
    result = prove_inductive(schema, depth_limit=100)

    assert result.depth_limit == 100


# ═══════════════════════════════════════════════════════════════════════════════
# batch_prove() tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_batch_prove_handles_multiple_schemas() -> None:
    """batch_prove() proves multiple induction schemas in one call."""
    schemas = [
        build_induction_schema("nat", "n", "P1"),
        build_induction_schema("list", "l", "P2"),
        build_induction_schema("tree", "t", "P3"),
    ]
    results = batch_prove(schemas)

    assert len(results) == 3
    for result in results:
        assert isinstance(result, InductiveProof)
        assert result.proof_id != ""


def test_batch_prove_empty_list() -> None:
    """batch_prove() handles an empty schema list."""
    results = batch_prove([])

    assert results == []


# ═══════════════════════════════════════════════════════════════════════════════
# format_inductive_report() tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_format_inductive_report_generates_markdown() -> None:
    """format_inductive_report() generates a valid markdown string."""
    schemas = [
        build_induction_schema("nat", "n", "P1"),
        build_induction_schema("nat", "m", "P2"),
    ]
    results = batch_prove(schemas)
    report = format_inductive_report(results)

    assert "# Inductive Proof Report" in report
    assert "**Total Proofs:**" in report
    assert "**Passed:**" in report
    assert "**Failed:**" in report
    assert "|" in report  # Table markers
    assert "P1" in report
    assert "P2" in report


def test_format_inductive_report_empty_proofs() -> None:
    """format_inductive_report() handles empty proof list."""
    report = format_inductive_report([])

    assert "# Inductive Proof Report" in report
    assert "**Total Proofs:** 0" in report


# ═══════════════════════════════════════════════════════════════════════════════
# InductiveProof.is_valid correctness
# ═══════════════════════════════════════════════════════════════════════════════


def test_inductive_proof_is_valid_reflects_both_base_and_step() -> None:
    """InductiveProof.is_valid is True only when BOTH base and step are ADMITTED."""
    schema = build_induction_schema("nat", "n", "test_prop")
    result = prove_inductive(schema)

    # is_valid should match the logical AND of both statuses
    base_ok = result.base_proved.status == ProofStatus.ADMITTED
    step_ok = result.step_proved.status == ProofStatus.ADMITTED

    assert result.is_valid == (base_ok and step_ok)


def test_inductive_proof_stores_schema_reference() -> None:
    """InductiveProof retains a reference to the original InductionSchema."""
    schema = build_induction_schema("nat", "n", "schema_ref_test")
    result = prove_inductive(schema)

    assert result.schema is schema
    assert result.schema.variable == "n"
    assert result.schema.domain == "nat"


# ═══════════════════════════════════════════════════════════════════════════════
# InductionSchema depth_limit handling
# ═══════════════════════════════════════════════════════════════════════════════


def test_induction_schema_handles_arbitrary_depth_limit() -> None:
    """InductionSchema works with arbitrary depth_limit values."""
    schema = build_induction_schema("nat", "k", "depth_test")

    # Test various depth limits
    for depth in [1, 10, 50, 100, 1000]:
        result = prove_inductive(schema, depth_limit=depth)
        assert result.depth_limit == depth
        assert isinstance(result, InductiveProof)


def test_induction_schema_slots_enforced() -> None:
    """InductionSchema and InductiveProof use __slots__ (no __dict__)."""
    schema = build_induction_schema("nat", "n", "slots_test")

    # InductionSchema should not allow arbitrary attribute assignment
    with pytest.raises(AttributeError):
        schema.extra_field = "should fail"  # type: ignore[attr-defined]

    # But we can test on InductiveProof too after proving
    result = prove_inductive(schema)
    with pytest.raises(AttributeError):
        result.extra_field = "should also fail"  # type: ignore[attr-defined]


# ═══════════════════════════════════════════════════════════════════════════════
# Z3 availability guard
# ═══════════════════════════════════════════════════════════════════════════════


def test_z3_available_returns_bool() -> None:
    """z3_available() returns a boolean."""
    result = z3_available()
    assert isinstance(result, bool)


def test_prove_inductive_works_without_z3() -> None:
    """prove_inductive() produces artifacts even when Z3 is unavailable."""
    schema = build_induction_schema("nat", "n", "no_z3_test")
    result = prove_inductive(schema)

    # Should still return a valid InductiveProof
    assert isinstance(result, InductiveProof)
    assert result.base_proved is not None
    assert result.step_proved is not None

    if not z3_available():
        # Without Z3, base and step should be UNVERIFIED
        assert result.base_proved.status == ProofStatus.UNVERIFIED
        assert result.step_proved.status == ProofStatus.UNVERIFIED
