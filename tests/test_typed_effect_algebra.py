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
    EffectChain,
    EffectCondition,
    EffectConditional,
    EffectIterate,
    EffectParallel,
    EffectProof,
    NoEffect,
    SoundnessVerdict,
    TypedEffect,
    chain,
    check_associativity,
    check_effect_soundness,
    check_idempotence,
    check_identity,
    check_left_identity,
    conditional,
    iterate,
    parallel,
    prove_effect_chain,
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
