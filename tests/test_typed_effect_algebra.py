"""Unit tests for hlf_mcp.hlf.typed_effect_algebra — combinator construction,
algebraic laws, proof generation, and soundness checking."""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.typed_contracts import (
    EffectClass,
    HlfType,
    InputContract,
    OutputContract,
    TypeContract,
    TypedEffectDeclaration,
)
from hlf_mcp.hlf.typed_effect_algebra import (
    CoercionProof,
    EffectChain,
    EffectCondition,
    EffectConditional,
    EffectIterate,
    EffectParallel,
    EffectProof,
    EffectSignature,
    EffectType,
    NoEffect,
    SoundnessVerdict,
    TypedEffect,
    build_coercion_table,
    build_composition_matrix,
    chain,
    check_associativity,
    check_effect_soundness,
    check_idempotence,
    check_identity,
    check_left_identity,
    classify_effect,
    conditional,
    iterate,
    parallel,
    prove_coercion,
    prove_composition,
    prove_effect_chain,
    validate_host_function_contract,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_decl(
    name: str,
    input_type: HlfType = HlfType.STRING,
    output_type: HlfType = HlfType.STRING,
    *,
    side_effects: list[str] | None = None,
) -> TypedEffectDeclaration:
    """Create a minimal ``TypedEffectDeclaration`` for testing."""
    return TypedEffectDeclaration(
        function_name=name,
        input_contract=InputContract(
            function_name=name,
            parameters=[
                TypeContract(name="arg0", hlf_type=input_type)
            ],
        ),
        output_contract=OutputContract(
            function_name=name,
            return_type=output_type,
        ),
        side_effects=side_effects or [],
    )


# ── constructor smoke tests ──────────────────────────────────────────────────


class TestCombinatorConstruction:
    def test_no_effect_repr(self):
        n = NoEffect()
        assert repr(n) == "NoEffect('noop')"

    def test_chain_construction(self):
        a = _make_decl("read")
        b = _make_decl("write")
        c = chain(a, b)
        assert isinstance(c, EffectChain)
        assert c.first is a
        assert c.second is b
        assert "read>>write" in c.label

    def test_parallel_construction(self):
        a = _make_decl("f")
        b = _make_decl("g")
        p = parallel(a, b)
        assert isinstance(p, EffectParallel)
        assert p.left is a
        assert p.right is b
        assert "f||g" in p.label

    def test_conditional_construction(self):
        a = _make_decl("then_f")
        b = _make_decl("else_f")
        cond = EffectCondition(predicate_name="model_reachable")
        c = conditional(cond, a, b)
        assert isinstance(c, EffectConditional)
        assert c.then_effect is a
        assert c.else_effect is b
        assert "model_reachable" in c.label

    def test_iterate_construction(self):
        body = _make_decl("step")
        until = EffectCondition(predicate_name="converged")
        loop = iterate(body, until, max_iterations=10)
        assert isinstance(loop, EffectIterate)
        assert loop.body is body
        assert loop.max_iterations == 10

    def test_iterate_rejects_invalid_max(self):
        body = _make_decl("step")
        until = EffectCondition(predicate_name="done")
        with pytest.raises(ValueError, match="max_iterations"):
            EffectIterate(body=body, until=until, max_iterations=0)

    def test_frozen_dataclasses(self):
        """Combinators are frozen — mutation raises FrozenInstanceError."""
        a = _make_decl("f")
        c = chain(a, a)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            c.first = a  # type: ignore[misc]


# ── algebraic law tests ──────────────────────────────────────────────────────


class TestAssociativity:
    def test_three_atomic_effects(self):
        a = _make_decl("a")
        b = _make_decl("b")
        c = _make_decl("c")
        assert check_associativity(a, b, c) is True

    def test_with_no_effect_mixed(self):
        a = _make_decl("a")
        b = _make_decl("b")
        n = NoEffect()
        # chain(a, chain(n, b)) vs chain(chain(a, n), b)
        assert check_associativity(a, n, b) is True

    def test_with_nested_chains(self):
        a = _make_decl("a")
        b = _make_decl("b")
        c = _make_decl("c")
        d = _make_decl("d")
        # chain(chain(a,b), chain(c,d))
        left_inner = chain(a, b)
        right_inner = chain(c, d)
        assert check_associativity(left_inner, right_inner, NoEffect()) is True


class TestIdentity:
    def test_right_identity_atomic(self):
        a = _make_decl("f")
        assert check_identity(a) is True

    def test_right_identity_chain(self):
        a = _make_decl("f")
        b = _make_decl("g")
        c = chain(a, b)
        # chain(c, NoEffect()) leaves leaf-sequence unchanged
        chained = EffectChain(first=c, second=NoEffect())
        from hlf_mcp.hlf.typed_effect_algebra import _leaf_declarations
        assert _leaf_declarations(c) == _leaf_declarations(chained)

    def test_left_identity_atomic(self):
        a = _make_decl("f")
        assert check_left_identity(a) is True

    def test_left_identity_chain(self):
        a = _make_decl("f")
        b = _make_decl("g")
        c = chain(a, b)
        assert check_left_identity(c) is True


class TestIdempotence:
    def test_no_effect_is_idempotent(self):
        ok, reason = check_idempotence(NoEffect())
        assert ok
        assert "trivially" in reason

    def test_decl_without_hint_is_not_idempotent(self):
        a = _make_decl("f")
        ok, reason = check_idempotence(a)
        assert not ok
        assert "no idempotent hint" in reason

    def test_decl_with_hint_is_idempotent(self):
        a = _make_decl("f", side_effects=["idempotent"])
        ok, reason = check_idempotence(a)
        assert ok
        assert "idempotent hint" in reason

    def test_chain_of_idempotent(self):
        a = _make_decl("f", side_effects=["idempotent"])
        c = chain(a, a)
        ok, reason = check_idempotence(c)
        assert ok


# ── proof generation tests ───────────────────────────────────────────────────


class TestProveEffectChain:
    def test_single_leaf_chain(self):
        a = _make_decl("f")
        c = chain(a, NoEffect())
        proof = prove_effect_chain(c)
        assert proof.is_valid
        assert "trivial" in proof.witnesses[0]

    def test_compatible_two_leaf(self):
        a = _make_decl("read", input_type=HlfType.STRING, output_type=HlfType.STRING)
        b = _make_decl("process", input_type=HlfType.STRING, output_type=HlfType.STRING)
        c = chain(a, b)
        proof = prove_effect_chain(c)
        assert proof.is_valid
        assert proof.compatible
        assert proof.chain_proven
        assert "OK" in proof.witnesses[0]

    def test_mismatched_types(self):
        a = _make_decl("read", input_type=HlfType.STRING, output_type=HlfType.NUMBER)
        b = _make_decl("process", input_type=HlfType.STRING, output_type=HlfType.STRING)
        c = chain(a, b)
        proof = prove_effect_chain(c)
        assert not proof.is_valid
        assert "MISMATCH" in proof.witnesses[0]

    def test_any_input_accepts_anything(self):
        """ANY *input* is the top type — accepts any upstream output."""
        a = _make_decl("read", output_type=HlfType.STRING)
        b = _make_decl("process", input_type=HlfType.ANY)
        c = chain(a, b)
        proof = prove_effect_chain(c)
        assert proof.is_valid

    def test_any_output_cannot_satisfy_specific_input(self):
        """ANY *output* cannot guarantee compatibility with a specific downstream input."""
        a = _make_decl("read", output_type=HlfType.ANY)
        b = _make_decl("process", input_type=HlfType.NUMBER)
        c = chain(a, b)
        proof = prove_effect_chain(c)
        assert not proof.is_valid
        assert "MISMATCH" in proof.witnesses[0]

    def test_json_accepts_primitives(self):
        a = _make_decl("read", output_type=HlfType.STRING)
        b = _make_decl("process", input_type=HlfType.JSON)
        c = chain(a, b)
        proof = prove_effect_chain(c)
        assert proof.is_valid

    def test_long_chain(self):
        effects = [
            _make_decl(f"f{i}", input_type=HlfType.STRING, output_type=HlfType.STRING)
            for i in range(5)
        ]
        c: EffectChain = effects[0]
        for e in effects[1:]:
            c = chain(c, e)  # type: ignore[assignment]
        proof = prove_effect_chain(c)  # type: ignore[arg-type]
        assert proof.is_valid
        assert len(proof.witnesses) == len(effects) - 1


# ── soundness tests ──────────────────────────────────────────────────────────


class TestCheckEffectSoundness:
    def test_atomic_is_sound(self):
        a = _make_decl("f")
        v = check_effect_soundness(a)
        assert isinstance(v, SoundnessVerdict)
        assert v.sound
        assert v.reachable

    def test_no_effect_is_sound(self):
        v = check_effect_soundness(NoEffect())
        assert v.sound

    def test_compatible_chain_is_sound(self):
        a = _make_decl("read", input_type=HlfType.STRING, output_type=HlfType.STRING)
        b = _make_decl("process", input_type=HlfType.STRING, output_type=HlfType.STRING)
        c = chain(a, b)
        v = check_effect_soundness(c)
        assert v.sound

    def test_incompatible_chain_is_not_sound(self):
        a = _make_decl("read", output_type=HlfType.NUMBER)
        b = _make_decl("process", input_type=HlfType.STRING)
        c = chain(a, b)
        v = check_effect_soundness(c)
        assert not v.sound
        assert len(v.missing_bridge) > 0

    def test_parallel_is_sound_when_both_sides_sound(self):
        a = _make_decl("f")
        b = _make_decl("g")
        p = parallel(a, b)
        v = check_effect_soundness(p)
        assert v.sound

    def test_conditional_branches_must_agree(self):
        then_e = _make_decl("then", output_type=HlfType.STRING)
        else_e = _make_decl("else", output_type=HlfType.NUMBER)
        cond = EffectCondition(predicate_name="test")
        c = conditional(cond, then_e, else_e)
        v = check_effect_soundness(c)
        assert not v.sound
        assert "branch-output-mismatch" in v.missing_bridge[0]

    def test_conditional_branches_agree_is_sound(self):
        then_e = _make_decl("then", output_type=HlfType.STRING)
        else_e = _make_decl("else", output_type=HlfType.STRING)
        cond = EffectCondition(predicate_name="test")
        c = conditional(cond, then_e, else_e)
        v = check_effect_soundness(c)
        assert v.sound

    def test_iterate_requires_fixed_point(self):
        body = _make_decl("step", input_type=HlfType.STRING, output_type=HlfType.NUMBER)
        until = EffectCondition(predicate_name="done")
        loop = iterate(body, until)
        v = check_effect_soundness(loop)
        assert not v.sound
        assert "fixed-point" in v.missing_bridge[0]

    def test_iterate_fixed_point_is_sound(self):
        body = _make_decl("step", input_type=HlfType.STRING, output_type=HlfType.STRING)
        until = EffectCondition(predicate_name="done")
        loop = iterate(body, until)
        v = check_effect_soundness(loop)
        assert v.sound


# ── leaf collection tests ────────────────────────────────────────────────────


class TestLeafDeclarations:
    def test_atomic_leaf(self):
        from hlf_mcp.hlf.typed_effect_algebra import _leaf_declarations
        a = _make_decl("f")
        leaves = _leaf_declarations(a)
        assert leaves == [a]

    def test_chain_leaves(self):
        from hlf_mcp.hlf.typed_effect_algebra import _leaf_declarations
        a = _make_decl("f")
        b = _make_decl("g")
        c = chain(a, b)
        leaves = _leaf_declarations(c)
        assert leaves == [a, b]

    def test_nested_chain_leaves(self):
        from hlf_mcp.hlf.typed_effect_algebra import _leaf_declarations
        a = _make_decl("a")
        b = _make_decl("b")
        c = _make_decl("c")
        outer = chain(chain(a, b), c)
        leaves = _leaf_declarations(outer)
        assert leaves == [a, b, c]

    def test_no_effect_skipped(self):
        from hlf_mcp.hlf.typed_effect_algebra import _leaf_declarations
        a = _make_decl("f")
        c = chain(a, NoEffect())
        leaves = _leaf_declarations(c)
        assert leaves == [a]


# ── TypeAlias introspection ──────────────────────────────────────────────────


class TestTypedEffectAlias:
    def test_chain_is_typed_effect(self):
        """EffectChain instances satisfy the TypedEffect union."""
        a = _make_decl("f")
        c = chain(a, a)
        # The TypedEffect union includes EffectChain
        from hlf_mcp.hlf.typed_effect_algebra import TypedEffect as TE
        from typing import get_args
        union_members = get_args(TE)
        assert EffectChain in union_members

    def test_typed_effect_declaration_is_typed_effect(self):
        from hlf_mcp.hlf.typed_effect_algebra import TypedEffect as TE
        from typing import get_args
        union_members = get_args(TE)
        assert TypedEffectDeclaration in union_members


# ── EffectProof / SoundnessVerdict serialization ─────────────────────────────


class TestProofSerialization:
    def test_effect_proof_to_dict(self):
        p = EffectProof(
            effect_label="test",
            compatible=True,
            chain_proven=True,
            gas_bounded=True,
            witnesses=("step-0: OK",),
            input_type_hint="string",
            output_type_hint="string",
        )
        d = p.to_dict()
        assert d["is_valid"] is True
        assert d["witnesses"] == ["step-0: OK"]

    def test_soundness_verdict_to_dict(self):
        v = SoundnessVerdict(
            effect_label="test",
            sound=False,
            missing_bridge=("type-mismatch",),
        )
        d = v.to_dict()
        assert d["sound"] is False
        assert d["missing_bridge"] == ["type-mismatch"]


# ═══════════════════════════════════════════════════════════════════════════════
# P2 — Heterogeneous Composition Proofs
# ═══════════════════════════════════════════════════════════════════════════════


# ── EffectType enum ───────────────────────────────────────────────────────────


class TestEffectTypeEnum:
    def test_all_values_present(self):
        """EffectType enum has all expected values."""
        expected = {"pure", "read", "write", "delete", "network", "compute", "audit", "coercion"}
        actual = {e.value for e in EffectType}
        assert expected == actual

    def test_from_effect_class_maps_correctly(self):
        """EffectType.from_effect_class maps known effect classes."""
        assert EffectType.from_effect_class("file_read") == EffectType.READ
        assert EffectType.from_effect_class("file_write") == EffectType.WRITE
        assert EffectType.from_effect_class("web_search") == EffectType.NETWORK
        assert EffectType.from_effect_class("model_inference") == EffectType.COMPUTE
        assert EffectType.from_effect_class("audit_log") == EffectType.AUDIT
        assert EffectType.from_effect_class("assertion") == EffectType.PURE

    def test_unknown_effect_class_defaults_to_pure(self):
        """Unknown effect_class maps to PURE."""
        assert EffectType.from_effect_class("nonexistent_effect") == EffectType.PURE


# ── classify_effect ───────────────────────────────────────────────────────────


class TestClassifyEffect:
    def test_classify_read_file(self):
        """classify_effect returns correct EffectSignature for read_file."""
        entry = {
            "effect_class": "file_read",
            "input_schema": {"type": "object", "properties": {"path": {"type": "path"}}},
            "output_schema": {"type": "string"},
        }
        sig = classify_effect("READ", entry)
        assert sig.effect_type == EffectType.READ
        assert sig.input_type == "J"  # input_schema is an object → JSON domain
        assert sig.output_type == "S"  # string return
        assert not sig.is_pure

    def test_classify_write_file(self):
        """classify_effect returns correct EffectSignature for write_file."""
        entry = {
            "effect_class": "file_write",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "path"}, "data": {"type": "string"}},
            },
            "output_schema": {"type": "boolean"},
        }
        sig = classify_effect("WRITE", entry)
        assert sig.effect_type == EffectType.WRITE
        assert sig.output_type == "B"  # boolean return
        assert "mutates_state" in sig.side_effects

    def test_classify_memory_store_gives_write(self):
        """memory_store with memory_write effect_class → WRITE."""
        entry = {
            "effect_class": "memory_write",
            "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}},
            "output_schema": {"type": "boolean"},
        }
        sig = classify_effect("memory_store", entry)
        assert sig.effect_type == EffectType.WRITE

    def test_classify_pure_assertion(self):
        """assertion effect_class → PURE, is_pure=True."""
        entry = {
            "effect_class": "assertion",
            "input_schema": {"type": "object", "properties": {"expr": {"type": "boolean"}}},
            "output_schema": {"type": "boolean"},
        }
        sig = classify_effect("assert_check", entry)
        assert sig.effect_type == EffectType.PURE
        assert sig.is_pure
        assert sig.side_effects == []


# ── prove_coercion ────────────────────────────────────────────────────────────


class TestProveCoercion:
    def test_z_to_r_is_widening_safe(self):
        """Z → R is widening, safe, no runtime check."""
        proof = prove_coercion("Z", "R")
        assert proof.is_safe
        assert proof.direction == "widening"
        assert not proof.requires_runtime_check
        assert "integer" in proof.proof_sketch.lower()

    def test_r_to_z_is_narrowing_conditional(self):
        """R → Z is narrowing, conditional, requires runtime check."""
        proof = prove_coercion("R", "Z")
        assert not proof.is_safe
        assert proof.direction == "narrowing"
        assert proof.requires_runtime_check
        assert "NaN" in proof.edge_cases[0].lower() or any("nan" in ec.lower() for ec in proof.edge_cases)

    def test_list_q_to_set_q_is_isomorphic_safe(self):
        """List⟨Q⟩ → Set⟨Q⟩ is isomorphic, safe, no runtime check."""
        proof = prove_coercion("List<Q>", "Set<Q>")
        assert proof.is_safe
        assert proof.direction == "isomorphic"
        assert not proof.requires_runtime_check
        assert "ordering" in " ".join(proof.edge_cases).lower() or "duplicate" in " ".join(proof.edge_cases).lower()

    def test_set_q_to_list_q_is_isomorphic_conditional(self):
        """Set⟨Q⟩ → List⟨Q⟩ is isomorphic, conditional, requires check."""
        proof = prove_coercion("Set<Q>", "List<Q>")
        assert not proof.is_safe
        assert proof.direction == "isomorphic"
        assert proof.requires_runtime_check

    def test_identity_coercion_is_safe(self):
        """Identity coercion (Z → Z) is safe, isomorphic, no check."""
        proof = prove_coercion("Z", "Z")
        assert proof.is_safe
        assert proof.direction == "isomorphic"
        assert not proof.requires_runtime_check

    def test_q_to_r_is_widening_safe(self):
        """Q → R is widening, safe."""
        proof = prove_coercion("Q", "R")
        assert proof.is_safe
        assert proof.direction == "widening"

    def test_list_z_to_list_r_is_element_wise_widening(self):
        """List⟨Z⟩ → List⟨R⟩ is widening (element-wise Z→R)."""
        proof = prove_coercion("List<Z>", "List<R>")
        assert proof.is_safe
        assert proof.direction == "widening"

    def test_set_z_to_set_r_may_collapse(self):
        """Set⟨Z⟩ → Set⟨R⟩ warns about cardinality collapse."""
        proof = prove_coercion("Set<Z>", "Set<R>")
        assert proof.is_safe
        assert "collapse" in " ".join(proof.edge_cases).lower() or "duplicate" in " ".join(proof.edge_cases).lower()


# ── prove_composition ─────────────────────────────────────────────────────────


class TestProveComposition:
    def test_pure_compose_pure_is_safe(self):
        """Pure∘Pure → safe pure composition."""
        a = EffectSignature(EffectType.PURE, "Z", "Z", is_pure=True, side_effects=[])
        b = EffectSignature(EffectType.PURE, "Z", "Z", is_pure=True, side_effects=[])
        proof = prove_composition(a, b)
        assert proof.is_safe

    def test_read_compose_write_requires_ordering(self):
        """Read∘Write requires ordering check."""
        a = EffectSignature(EffectType.READ, "S", "S", is_pure=False, side_effects=[])
        b = EffectSignature(EffectType.WRITE, "S", "S", is_pure=False, side_effects=["mutates_state"])
        proof = prove_composition(a, b)
        # Read then Write is generally safe, but let's test Write then Read
        proof2 = prove_composition(b, a)
        assert not proof2.is_safe
        assert "ordering" in proof2.proof_sketch.lower() or "flush" in " ".join(proof2.edge_cases).lower()

    def test_delete_compose_anything_requires_audit(self):
        """Delete∘Anything requires audit."""
        a = EffectSignature(EffectType.DELETE, "S", "B", is_pure=False, side_effects=["mutates_state"])
        b = EffectSignature(EffectType.READ, "S", "S", is_pure=False, side_effects=[])
        proof = prove_composition(a, b)
        assert not proof.is_safe
        assert "audit" in proof.proof_sketch.lower() or "audit" in " ".join(proof.edge_cases).lower()

    def test_pure_compose_anything_is_safe(self):
        """Pure∘Anything is safe when types align (stateless)."""
        a = EffectSignature(EffectType.PURE, "Z", "Z", is_pure=True, side_effects=[])
        b = EffectSignature(EffectType.NETWORK, "Z", "S", is_pure=False, side_effects=["network_egress"])
        proof = prove_composition(a, b)
        # Pure∘Anything is side-effect safe; Z→Z is identity coercion
        assert proof.is_safe

    def test_read_compose_read_is_safe(self):
        """Read∘Read is safe (reads commute)."""
        a = EffectSignature(EffectType.READ, "S", "S", is_pure=False, side_effects=[])
        b = EffectSignature(EffectType.READ, "S", "S", is_pure=False, side_effects=[])
        proof = prove_composition(a, b)
        assert proof.is_safe


# ── build_composition_matrix ──────────────────────────────────────────────────


class TestBuildCompositionMatrix:
    def test_has_expected_size(self):
        """build_composition_matrix returns 8×8 entries (all EffectType values)."""
        matrix = build_composition_matrix()
        all_types = list(EffectType)
        # Every row and column should be present
        for row_type in all_types:
            assert row_type.value in matrix, f"Missing row: {row_type.value}"
            for col_type in all_types:
                assert col_type.value in matrix[row_type.value], (
                    f"Missing cell: {row_type.value} → {col_type.value}"
                )

    def test_all_cells_are_coercion_proofs(self):
        """Every cell is a CoercionProof."""
        matrix = build_composition_matrix()
        for row in matrix:
            for col in matrix[row]:
                assert isinstance(matrix[row][col], CoercionProof)

    def test_pure_pure_is_safe(self):
        """Pure∘Pure cell is safe."""
        matrix = build_composition_matrix()
        assert matrix["pure"]["pure"].is_safe

    def test_delete_any_requires_audit(self):
        """Delete row has audit warnings."""
        matrix = build_composition_matrix()
        delete_row = matrix["delete"]
        # At least some cells should not be safe due to audit requirement
        audit_unsafe = any(not cell.is_safe for cell in delete_row.values())
        assert audit_unsafe, "Delete compositions should have audit constraints"


# ── build_coercion_table ──────────────────────────────────────────────────────


class TestBuildCoercionTable:
    def test_covers_z_to_r(self):
        """Coercion table covers Z → R."""
        table = build_coercion_table()
        assert "Z" in table
        assert "R" in table["Z"]
        proof = table["Z"]["R"]
        assert proof.is_safe
        assert proof.direction == "widening"

    def test_covers_list_to_set(self):
        """Coercion table covers List⟨Z⟩ → Set⟨Z⟩."""
        table = build_coercion_table()
        assert "List<Z>" in table
        assert "Set<Z>" in table["List<Z>"]
        proof = table["List<Z>"]["Set<Z>"]
        assert proof.direction == "isomorphic"

    def test_all_49_entries_present(self):
        """Coercion table has 7×7 = 49 entries."""
        table = build_coercion_table()
        expected_domains = {"Z", "R", "Q", "List<Z>", "List<R>", "Set<Z>", "Set<R>"}
        assert set(table.keys()) == expected_domains
        for src in expected_domains:
            assert set(table[src].keys()) == expected_domains


# ── validate_host_function_contract ───────────────────────────────────────────


class TestValidateHostFunctionContract:
    def test_detects_missing_input_schema(self):
        """Missing input_schema is detected."""
        entry = {
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert "input_schema" in missing

    def test_detects_missing_output_schema(self):
        """Missing output_schema is detected."""
        entry = {
            "input_schema": {"type": "object", "properties": {}},
            "effect_class": "file_read",
            "failure_type": "io_error",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert "output_schema" in missing

    def test_detects_missing_effect_class(self):
        """Missing effect_class is detected."""
        entry = {
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "string"},
            "failure_type": "io_error",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert "effect_class" in missing

    def test_detects_missing_failure_type(self):
        """Missing structured_failure_type/failure_type is detected."""
        entry = {
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert "structured_failure_type" in missing

    def test_detects_missing_audit_requirement(self):
        """Missing audit_requirement is detected."""
        entry = {
            "input_schema": {"type": "object", "properties": {}},
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
        }
        missing = validate_host_function_contract(entry)
        assert "audit_requirement" in missing

    def test_passes_for_complete_contract(self):
        """Complete contract passes validation."""
        entry = {
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "path"},
                },
                "required": ["path"],
            },
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert missing == []

    def test_empty_input_schema_detected(self):
        """Empty dict input_schema is treated as missing."""
        entry = {
            "input_schema": {},
            "output_schema": {"type": "string"},
            "effect_class": "file_read",
            "failure_type": "io_error",
            "audit_requirement": "standard",
        }
        missing = validate_host_function_contract(entry)
        assert "input_schema" in missing


# ── CoercionProof serialization ───────────────────────────────────────────────


class TestCoercionProofSerialization:
    def test_to_dict(self):
        """CoercionProof.to_dict serializes correctly."""
        proof = CoercionProof(
            source_type="Z",
            target_type="R",
            is_safe=True,
            direction="widening",
            requires_runtime_check=False,
            proof_sketch="Integers embed in reals.",
            edge_cases=["Large integers may lose precision"],
        )
        d = proof.to_dict()
        assert d["source_type"] == "Z"
        assert d["target_type"] == "R"
        assert d["is_safe"] is True
        assert d["direction"] == "widening"
        assert not d["requires_runtime_check"]
        assert len(d["edge_cases"]) == 1
