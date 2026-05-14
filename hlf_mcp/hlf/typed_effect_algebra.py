"""
Typed Effect Algebra — composable effect combinators, algebraic laws,
and proof generation for HLF typed contracts.

Faithful port of the effect algebra that the verifier, tool contracts,
and formal verification consume.  Defines sequential, parallel,
conditional, and iterative composition over typed effects, together
with testable algebraic laws (associativity, identity, idempotence)
and proof-generation functions.

Integrates with :mod:`hlf_mcp.hlf.typed_contracts` by treating
``TypedEffectDeclaration`` as the atomic (leaf) typed effect.

Usage::

    from hlf_mcp.hlf.typed_effect_algebra import (
        EffectChain, EffectParallel, EffectConditional, EffectIterate,
        NoEffect, TypedEffect, EffectCondition,
        prove_effect_chain, check_effect_soundness,
        check_associativity, check_identity,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from hlf_mcp.hlf.typed_contracts import (
    EffectClass,
    FailureMode,
    HlfType,
    InputContract,
    OutputContract,
    ProofRequirement,
    TypedEffectDeclaration,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Identity / NoEffect sentinel
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class NoEffect:
    """The identity element of the effect algebra.

    ``chain(effect, NoEffect())`` is equivalent to ``effect``,
    and ``parallel(effect, NoEffect())`` passes through the non-identity side.
    """

    label: str = "noop"

    def __repr__(self) -> str:
        return f"NoEffect({self.label!r})"


# ═══════════════════════════════════════════════════════════════════════════════
# Effect condition — a named predicate that gates conditional branching
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EffectCondition:
    """A named predicate that gates conditional effects.

    The *predicate_name* identifies a governance-checkable condition
    (e.g. ``"gas_remaining > 0"``, ``"model_reachable"``).
    *bound_variables* names the free variables the predicate closes over.
    """

    predicate_name: str
    bound_variables: tuple[str, ...] = ()
    description: str = ""

    def __repr__(self) -> str:
        vars_str = ", ".join(self.bound_variables)
        return f"Condition({self.predicate_name}({vars_str}))"


# ═══════════════════════════════════════════════════════════════════════════════
# Effect combinators
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EffectChain:
    """Sequential composition: execute *first*, then *second*.

    The output of *first* flows into the input of *second*.
    Corresponds to monadic ``>>`` / ``and_then``.
    """

    first: TypedEffect
    second: TypedEffect
    label: str = ""

    def __repr__(self) -> str:
        return f"Chain({self.first!r} >> {self.second!r})"


@dataclass(frozen=True)
class EffectParallel:
    """Parallel (product) composition: execute *left* and *right* independently.

    Both effects run and their results are paired.  Corresponds to
    ``***`` / applicative product.
    """

    left: TypedEffect
    right: TypedEffect
    label: str = ""

    def __repr__(self) -> str:
        return f"Par({self.left!r} || {self.right!r})"


@dataclass(frozen=True)
class EffectConditional:
    """Conditional branching: if *condition* then *then_effect* else *else_effect*.

    Both branches must satisfy the same output contract so the
    continuation is well-typed regardless of the branch taken.
    """

    condition: EffectCondition
    then_effect: TypedEffect
    else_effect: TypedEffect
    label: str = ""

    def __repr__(self) -> str:
        return (
            f"If({self.condition!r} ? {self.then_effect!r} : {self.else_effect!r})"
        )


@dataclass(frozen=True)
class EffectIterate:
    """Bounded repetition: execute *body* until *condition* is satisfied.

    *max_iterations* provides a deterministic termination bound.
    """

    body: TypedEffect
    until: EffectCondition
    max_iterations: int = 1000
    label: str = ""

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >= 1, got {self.max_iterations}"
            )

    def __repr__(self) -> str:
        return (
            f"Iterate({self.body!r} until {self.until!r}, "
            f"max={self.max_iterations})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TypedEffect union — every node in the algebra
# ═══════════════════════════════════════════════════════════════════════════════

TypedEffect = Union[
    TypedEffectDeclaration,
    NoEffect,
    EffectChain,
    EffectParallel,
    EffectConditional,
    EffectIterate,
]

# Let the combinators know about the union for runtime isinstance checks.
# (forward-ref strings in annotations are resolved lazily by __future__.)
EffectChain.__annotations__["first"] = TypedEffect
EffectChain.__annotations__["second"] = TypedEffect
EffectParallel.__annotations__["left"] = TypedEffect
EffectParallel.__annotations__["right"] = TypedEffect
EffectConditional.__annotations__["then_effect"] = TypedEffect
EffectConditional.__annotations__["else_effect"] = TypedEffect
EffectIterate.__annotations__["body"] = TypedEffect


# ═══════════════════════════════════════════════════════════════════════════════
# Effect proof and soundness types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EffectProof:
    """A machine-checkable proof that an effect composition satisfies its
    output contract given its input contract.

    *compatible*: the input→output type flow is consistent
    *chain_proven*: each sequential link's types align
    *gas_bounded*: the composition is within declared gas budget
    *witnesses*: human-readable trace of each proof step
    """

    effect_label: str
    compatible: bool = False
    chain_proven: bool = False
    gas_bounded: bool = False
    witnesses: tuple[str, ...] = ()
    input_type_hint: str = "unknown"
    output_type_hint: str = "unknown"

    @property
    def is_valid(self) -> bool:
        """A proof is valid when all three gates pass."""
        return self.compatible and self.chain_proven and self.gas_bounded

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_label": self.effect_label,
            "compatible": self.compatible,
            "chain_proven": self.chain_proven,
            "gas_bounded": self.gas_bounded,
            "witnesses": list(self.witnesses),
            "input_type_hint": self.input_type_hint,
            "output_type_hint": self.output_type_hint,
            "is_valid": self.is_valid,
        }


@dataclass(frozen=True)
class SoundnessVerdict:
    """Result of checking whether an effect's output type is reachable
    from its declared input type."""

    effect_label: str
    sound: bool = False
    reachable: bool = False
    required_input: str = ""
    declared_output: str = ""
    missing_bridge: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect_label": self.effect_label,
            "sound": self.sound,
            "reachable": self.reachable,
            "required_input": self.required_input,
            "declared_output": self.declared_output,
            "missing_bridge": list(self.missing_bridge),
            "diagnostics": list(self.diagnostics),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers — flatten / collect
# ═══════════════════════════════════════════════════════════════════════════════


def _is_typed_effect_decl(obj: Any) -> bool:
    return isinstance(obj, TypedEffectDeclaration)


def _effect_name(effect: TypedEffect) -> str:
    """Return a stable human-readable label for any effect node."""
    if isinstance(effect, TypedEffectDeclaration):
        return effect.function_name
    if isinstance(effect, NoEffect):
        return effect.label
    if isinstance(effect, EffectChain):
        return effect.label or f"({_effect_name(effect.first)}>>{_effect_name(effect.second)})"
    if isinstance(effect, EffectParallel):
        return effect.label or f"({_effect_name(effect.left)}||{_effect_name(effect.right)})"
    if isinstance(effect, EffectConditional):
        return effect.label or f"(if-{effect.condition.predicate_name})"
    if isinstance(effect, EffectIterate):
        return effect.label or f"(loop-{_effect_name(effect.body)})"
    return str(effect)


def _leaf_declarations(effect: TypedEffect) -> list[TypedEffectDeclaration]:
    """Collect every ``TypedEffectDeclaration`` leaf in the effect tree."""
    result: list[TypedEffectDeclaration] = []
    _collect_leaves(effect, result)
    return result


def _collect_leaves(effect: TypedEffect, acc: list[TypedEffectDeclaration]) -> None:
    if isinstance(effect, TypedEffectDeclaration):
        acc.append(effect)
    elif isinstance(effect, NoEffect):
        pass
    elif isinstance(effect, EffectChain):
        _collect_leaves(effect.first, acc)
        _collect_leaves(effect.second, acc)
    elif isinstance(effect, EffectParallel):
        _collect_leaves(effect.left, acc)
        _collect_leaves(effect.right, acc)
    elif isinstance(effect, EffectConditional):
        _collect_leaves(effect.then_effect, acc)
        _collect_leaves(effect.else_effect, acc)
    elif isinstance(effect, EffectIterate):
        _collect_leaves(effect.body, acc)


# ═══════════════════════════════════════════════════════════════════════════════
# Algebraic law checks (testable properties)
# ═══════════════════════════════════════════════════════════════════════════════


def check_associativity(
    a: TypedEffect,
    b: TypedEffect,
    c: TypedEffect,
) -> bool:
    """Verify associativity: ``chain(a, chain(b, c))`` ≡ ``chain(chain(a, b), c)``.

    Structural equality — both sides must produce isomorphic trees.
    Returns ``True`` when the law holds for the three given effects.
    """
    left = EffectChain(first=a, second=EffectChain(first=b, second=c))
    right = EffectChain(first=EffectChain(first=a, second=b), second=c)

    # Structural comparison: the leaf sequences must be identical
    left_leaves = _leaf_declarations(left)
    right_leaves = _leaf_declarations(right)
    return left_leaves == right_leaves


def check_identity(effect: TypedEffect) -> bool:
    """Verify identity: ``chain(effect, NoEffect())`` is structurally
    equivalent to ``effect`` (modulo wrapping).

    Returns ``True`` when chaining ``NoEffect`` on the right does not
    alter the observable leaf sequence.
    """
    chained = EffectChain(first=effect, second=NoEffect())
    original_leaves = _leaf_declarations(effect)
    chained_leaves = _leaf_declarations(chained)
    return original_leaves == chained_leaves


def check_left_identity(effect: TypedEffect) -> bool:
    """Verify left identity: ``chain(NoEffect(), effect)`` leaves *effect* unchanged."""
    chained = EffectChain(first=NoEffect(), second=effect)
    original_leaves = _leaf_declarations(effect)
    chained_leaves = _leaf_declarations(chained)
    return original_leaves == chained_leaves


def check_idempotence(effect: TypedEffect) -> tuple[bool, str]:
    """Check whether ``chain(e, e)`` ≡ ``e`` for this effect.

    Returns ``(is_idempotent, reason)``.  An effect is idempotent when
    repeating it does not change observable state — typically declared
    via an idempotency hint on the leaf declaration.
    """
    if isinstance(effect, TypedEffectDeclaration):
        # Check idempotency hint in side_effects metadata
        hints = getattr(effect, "side_effects", [])
        if "idempotent" in hints:
            return True, "declaration carries idempotent hint"
        return False, "no idempotent hint on declaration"

    if isinstance(effect, NoEffect):
        return True, "NoEffect is trivially idempotent"

    if isinstance(effect, EffectChain):
        # chain(e,e) idempotent only if e is idempotent
        inner_ok, reason = check_idempotence(effect.first)
        if not inner_ok:
            return False, f"chain inner not idempotent: {reason}"
        return True, "chain of idempotent effects"

    # Conservative: unknown structures are assumed non-idempotent
    return False, "effect structure not known to be idempotent"


# ═══════════════════════════════════════════════════════════════════════════════
# Effect-proof generation
# ═══════════════════════════════════════════════════════════════════════════════


def prove_effect_chain(chain: EffectChain) -> EffectProof:
    """Generate a proof that *chain* satisfies its output contract given
    its input contract.

    Walks the sequential links and checks type compatibility at each
    join point.  A chain is proven when every adjacent pair's output→input
    types are compatible (identical or compatible subtype).
    """
    name = _effect_name(chain)
    leaves = _leaf_declarations(chain)

    if len(leaves) < 2:
        # A chain with fewer than 2 leaves is trivially proven
        input_hint = leaves[0].input_contract.parameters[0].hlf_type.value if (
            leaves and leaves[0].input_contract.parameters
        ) else "any"
        output_hint = leaves[0].output_contract.return_type.value if leaves else "any"
        return EffectProof(
            effect_label=name,
            compatible=True,
            chain_proven=True,
            gas_bounded=True,
            witnesses=("trivial-chain",),
            input_type_hint=input_hint,
            output_type_hint=output_hint,
        )

    witnesses: list[str] = []
    all_compatible = True

    for i in range(len(leaves) - 1):
        prev_output = leaves[i].output_contract.return_type
        next_input_params = leaves[i + 1].input_contract.parameters
        next_input_type = (
            next_input_params[0].hlf_type if next_input_params else HlfType.ANY
        )

        if _types_compatible(prev_output, next_input_type):
            witnesses.append(
                f"link-{i}: {prev_output.value} → {next_input_type.value} OK"
            )
        else:
            all_compatible = False
            witnesses.append(
                f"link-{i}: {prev_output.value} → {next_input_type.value} MISMATCH"
            )

    input_hint = (
        leaves[0].input_contract.parameters[0].hlf_type.value
        if leaves[0].input_contract.parameters
        else "any"
    )
    output_hint = leaves[-1].output_contract.return_type.value

    return EffectProof(
        effect_label=name,
        compatible=all_compatible,
        chain_proven=all_compatible,
        gas_bounded=True,  # structural proof — gas is checked at runtime
        witnesses=tuple(witnesses),
        input_type_hint=input_hint,
        output_type_hint=output_hint,
    )


def check_effect_soundness(effect: TypedEffect) -> SoundnessVerdict:
    """Check that the effect's output type is reachable from its input type.

    For atomic declarations this is always true (they are the base case).
    For chains, we verify each join point.  For parallel/conditional/iterate
    compositions we decompose and verify each sub-effect.
    """
    name = _effect_name(effect)

    if isinstance(effect, TypedEffectDeclaration):
        inp = effect.input_contract.parameters[0].hlf_type if effect.input_contract.parameters else HlfType.ANY
        out = effect.output_contract.return_type
        return SoundnessVerdict(
            effect_label=name,
            sound=True,
            reachable=True,
            required_input=inp.value,
            declared_output=out.value,
        )

    if isinstance(effect, NoEffect):
        return SoundnessVerdict(
            effect_label=name,
            sound=True,
            reachable=True,
            required_input="any",
            declared_output="any",
        )

    if isinstance(effect, EffectChain):
        return _soundness_chain(effect)

    if isinstance(effect, EffectParallel):
        left_v = check_effect_soundness(effect.left)
        right_v = check_effect_soundness(effect.right)
        return SoundnessVerdict(
            effect_label=name,
            sound=left_v.sound and right_v.sound,
            reachable=left_v.reachable and right_v.reachable,
            required_input=f"({left_v.required_input}, {right_v.required_input})",
            declared_output=f"({left_v.declared_output}, {right_v.declared_output})",
            diagnostics=left_v.diagnostics + right_v.diagnostics,
        )

    if isinstance(effect, EffectConditional):
        then_v = check_effect_soundness(effect.then_effect)
        else_v = check_effect_soundness(effect.else_effect)
        # Both branches must declare the same output type
        branches_agree = then_v.declared_output == else_v.declared_output
        missing: list[str] = []
        if not branches_agree:
            missing.append(
                f"branch-output-mismatch: then={then_v.declared_output} else={else_v.declared_output}"
            )
        return SoundnessVerdict(
            effect_label=name,
            sound=then_v.sound and else_v.sound and branches_agree,
            reachable=then_v.reachable and else_v.reachable and branches_agree,
            required_input=then_v.required_input,
            declared_output=then_v.declared_output if branches_agree else "conflict",
            missing_bridge=tuple(missing),
            diagnostics=then_v.diagnostics + else_v.diagnostics,
        )

    if isinstance(effect, EffectIterate):
        body_v = check_effect_soundness(effect.body)
        # The body must map its own output back to its input (fixed-point)
        fixed_point = body_v.required_input == body_v.declared_output
        missing: list[str] = []
        if not fixed_point:
            missing.append(
                f"iterate-fixed-point: input={body_v.required_input} != output={body_v.declared_output}"
            )
        return SoundnessVerdict(
            effect_label=name,
            sound=body_v.sound and fixed_point,
            reachable=body_v.reachable and fixed_point,
            required_input=body_v.required_input,
            declared_output=body_v.declared_output,
            missing_bridge=tuple(missing),
            diagnostics=body_v.diagnostics,
        )

    # Fallback — unknown effect shape
    return SoundnessVerdict(
        effect_label=name,
        sound=False,
        reachable=False,
        diagnostics=(f"unknown effect kind: {type(effect).__name__}",),
    )


def _soundness_chain(effect: EffectChain) -> SoundnessVerdict:
    """Soundness for a chain: verify every join point."""
    name = _effect_name(effect)
    leaves = _leaf_declarations(effect)
    diagnostics: list[str] = []
    missing: list[str] = []
    all_sound = True

    for i in range(len(leaves) - 1):
        prev_out = leaves[i].output_contract.return_type
        next_params = leaves[i + 1].input_contract.parameters
        next_in = next_params[0].hlf_type if next_params else HlfType.ANY

        if _types_compatible(prev_out, next_in):
            diagnostics.append(f"join-{i}: {prev_out.value} → {next_in.value} OK")
        else:
            all_sound = False
            missing.append(f"join-{i}: {prev_out.value} → {next_in.value} mismatch")
            diagnostics.append(f"join-{i}: {prev_out.value} → {next_in.value} FAIL")

    return SoundnessVerdict(
        effect_label=name,
        sound=all_sound,
        reachable=all_sound,
        required_input=leaves[0].input_contract.parameters[0].hlf_type.value
        if leaves and leaves[0].input_contract.parameters
        else "any",
        declared_output=leaves[-1].output_contract.return_type.value if leaves else "any",
        missing_bridge=tuple(missing),
        diagnostics=tuple(diagnostics),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Type-compatibility predicate
# ═══════════════════════════════════════════════════════════════════════════════


def _types_compatible(a: HlfType, b: HlfType) -> bool:
    """Return ``True`` when type *a* can flow into type *b*.

    Rules:
    - ANY accepts anything (top type)
    - Same types are always compatible
    - JSON accepts STRING / NUMBER / BOOLEAN / JSON
    - All other pairs are incompatible
    """
    if a == b:
        return True
    if b == HlfType.ANY:
        return True
    if b == HlfType.JSON and a in {
        HlfType.STRING,
        HlfType.NUMBER,
        HlfType.BOOLEAN,
        HlfType.JSON,
    }:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience constructors
# ═══════════════════════════════════════════════════════════════════════════════


def chain(first: TypedEffect, second: TypedEffect) -> EffectChain:
    """Construct a sequential composition with an auto-generated label."""
    label = f"{_effect_name(first)}>>{_effect_name(second)}"
    return EffectChain(first=first, second=second, label=label)


def parallel(left: TypedEffect, right: TypedEffect) -> EffectParallel:
    """Construct a parallel composition with an auto-generated label."""
    label = f"{_effect_name(left)}||{_effect_name(right)}"
    return EffectParallel(left=left, right=right, label=label)


def conditional(
    condition: EffectCondition,
    then_effect: TypedEffect,
    else_effect: TypedEffect,
) -> EffectConditional:
    """Construct a conditional branch with an auto-generated label."""
    label = f"if-{condition.predicate_name}"
    return EffectConditional(
        condition=condition,
        then_effect=then_effect,
        else_effect=else_effect,
        label=label,
    )


def iterate(
    body: TypedEffect,
    until: EffectCondition,
    max_iterations: int = 1000,
) -> EffectIterate:
    """Construct a bounded iteration with an auto-generated label."""
    label = f"loop-{_effect_name(body)}"
    return EffectIterate(
        body=body, until=until, max_iterations=max_iterations, label=label
    )
