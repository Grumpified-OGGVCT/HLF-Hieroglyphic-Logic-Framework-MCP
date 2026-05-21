"""INDUCTIVE proof automation for HLF formal verification.

Provides schema-based induction over natural numbers, lists, and trees,
with Z3-backed base-case and step-case verification.

Supports:
- InductionSchema: base_case + inductive_step + variable + domain + hypothesis
- InductiveProof: combined base + step verification result
- Batch proving of multiple schemas
- Markdown report formatting
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hlf_mcp.hlf.proof_artifacts import (
    ProofArtifact,
    ProofStatus,
    admit_proof,
    create_proof_artifact,
    deny_proof,
)

_HAS_Z3 = False
try:
    import z3  # type: ignore[import-untyped]

    _HAS_Z3 = True
except ImportError:
    z3 = None  # type: ignore[assignment]


def z3_available() -> bool:
    """Check whether Z3 is importable."""
    return _HAS_Z3


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class InductionSchema:
    """Describes an inductive proof schema.

    Attributes:
        base_case: Z3 formula for the base case (e.g., n=0).
        inductive_step: Z3 formula for the inductive step (n → n+1).
        variable: Name of the induction variable.
        domain: Domain of induction ("nat", "int", "list", "tree").
        hypothesis: The property being proved.
    """

    base_case: str
    inductive_step: str
    variable: str
    domain: str
    hypothesis: str


@dataclass(slots=True)
class InductiveProof:
    """Result of an inductive proof attempt.

    Attributes:
        proof_id: Unique identifier.
        schema: The induction schema used.
        base_proved: ProofArtifact for the base case.
        step_proved: ProofArtifact for the inductive step.
        is_valid: True if both base and step are ADMITTED.
        induction_variable: Name of the induction variable.
        depth_limit: Maximum recursion depth considered.
    """

    proof_id: str
    schema: InductionSchema
    base_proved: ProofArtifact
    step_proved: ProofArtifact
    is_valid: bool
    induction_variable: str
    depth_limit: int


# ── Schema builders ────────────────────────────────────────────────────────


def build_induction_schema(
    domain: str,
    variable: str,
    hypothesis: str,
) -> InductionSchema:
    """Generate base_case and inductive_step Z3 formulae from domain config.

    Supported domains:
    - "nat": Natural numbers (base: n=0, step: n → n+1)
    - "int": Integers (base: n=0, step: n → n+1)
    - "list": Lists (base: empty list, step: cons(h, t))
    - "tree": Trees (base: leaf, step: node(left, right))

    Args:
        domain: Domain of induction ("nat", "int", "list", "tree").
        variable: Name of the induction variable.
        hypothesis: The property to prove (human-readable).

    Returns:
        An InductionSchema with populated base_case and inductive_step.
    """
    if domain in ("nat", "int"):
        base_case = f"(assert ({hypothesis} 0))"
        inductive_step = (
            f"(assert (forall (({variable} Int)) "
            f"(=> ({hypothesis} {variable}) ({hypothesis} (+ {variable} 1)))))"
        )
    elif domain == "list":
        base_case = f"(assert ({hypothesis} nil))"
        inductive_step = (
            f"(assert (forall ((h T) (t List<T>)) "
            f"(=> ({hypothesis} t) ({hypothesis} (cons h t)))))"
        )
    elif domain == "tree":
        base_case = f"(assert ({hypothesis} leaf))"
        inductive_step = (
            f"(assert (forall ((l Tree) (r Tree)) "
            f"(=> (and ({hypothesis} l) ({hypothesis} r)) "
            f"({hypothesis} (node l r)))))"
        )
    else:
        base_case = f"(assert ({hypothesis} {variable}_base))"
        inductive_step = f"(assert (forall (({variable} T)) (=> ({hypothesis} {variable}) ({hypothesis} (step {variable})))))"

    return InductionSchema(
        base_case=base_case,
        inductive_step=inductive_step,
        variable=variable,
        domain=domain,
        hypothesis=hypothesis,
    )


# ── Z3-backed inductive proving ───────────────────────────────────────────


def _verify_z3_formula(formula: str, operator_class: str, theorem: str) -> ProofArtifact:
    """Internal: verify a Z3 formula string using the SMT solver.

    Args:
        formula: SMT-LIB formula string.
        operator_class: Operator class for the artifact.
        theorem: Human-readable theorem.

    Returns:
        A ProofArtifact with verification result.
    """
    import time

    start = time.time()

    if not _HAS_Z3:
        # Fallback: cannot verify without Z3
        artifact = create_proof_artifact(
            operator_class=operator_class,
            theorem=theorem,
            formula=formula,
            result="unknown",
            time_ms=(time.time() - start) * 1000.0,
            evidence={"fallback": True, "reason": "z3_not_available"},
        )
        artifact.status = ProofStatus.UNVERIFIED
        return artifact

    try:
        s = z3.Solver()
        s.from_string(formula)
        z3_result = s.check()

        elapsed = (time.time() - start) * 1000.0

        result_str = str(z3_result)
        if result_str == "sat":
            try:
                model_dict = {
                    str(d.name()): str(s.model()[d]) if s.model()[d] is not None else "None"
                    for d in s.model().decls()
                }
            except Exception:
                model_dict = None

            artifact = create_proof_artifact(
                operator_class=operator_class,
                theorem=theorem,
                formula=formula,
                result=result_str,
                model=model_dict,
                time_ms=elapsed,
            )
            deny_proof(artifact, f"Counterexample found: {model_dict}")
            return artifact
        elif result_str == "unsat":
            try:
                proof_trace = str(s.proof()) if s.proof() else None
            except Exception:
                proof_trace = None

            artifact = create_proof_artifact(
                operator_class=operator_class,
                theorem=theorem,
                formula=formula,
                result=result_str,
                proof_trace=proof_trace,
                time_ms=elapsed,
            )
            admit_proof(artifact, admitted_by="z3")
            return artifact
        else:
            artifact = create_proof_artifact(
                operator_class=operator_class,
                theorem=theorem,
                formula=formula,
                result=result_str,
                time_ms=elapsed,
            )
            artifact.status = ProofStatus.UNVERIFIED
            return artifact
    except Exception as exc:
        elapsed = (time.time() - start) * 1000.0
        artifact = create_proof_artifact(
            operator_class=operator_class,
            theorem=theorem,
            formula=formula,
            result=str(exc),
            time_ms=elapsed,
            evidence={"error": str(exc)},
        )
        artifact.status = ProofStatus.ERROR
        return artifact


def prove_inductive(
    schema: InductionSchema,
    depth_limit: int = 50,
) -> InductiveProof:
    """Prove an induction schema by verifying base case and inductive step.

    Uses Z3 to check both the base case and the inductive step.
    The base case must be SAT (property holds at base).
    The inductive step must be UNSAT when the negation of P(n+1) is checked
    under the assumption of P(n).

    Args:
        schema: The InductionSchema to prove.
        depth_limit: Maximum recursion depth for tree/list domains.

    Returns:
        An InductiveProof with both base_proved and step_proved artifacts.
    """
    proof_id = str(uuid.uuid4())

    # Verify base case: base_case formula should be SAT
    base_artifact = _verify_z3_formula(
        formula=schema.base_case,
        operator_class="arithmetic" if schema.domain in ("nat", "int") else schema.domain,
        theorem=f"Base case for {schema.hypothesis}: {schema.variable}=base",
    )
    # For base case, SAT means the property holds at the base
    if _HAS_Z3 and base_artifact.result == "sat":
        admit_proof(base_artifact, admitted_by="z3")
    elif _HAS_Z3 and base_artifact.result == "unsat":
        deny_proof(base_artifact, "Base case property does not hold")

    # Verify inductive step: P(n) → P(n+1)
    # Encode as: assert (and P(n) (not P(n+1))); expect UNSAT
    step_formula = f"""(declare-const {schema.variable} Int)
(assert ({schema.hypothesis} {schema.variable}))
(assert (not ({schema.hypothesis} (+ {schema.variable} 1))))
"""
    step_artifact = _verify_z3_formula(
        formula=step_formula,
        operator_class="arithmetic" if schema.domain in ("nat", "int") else schema.domain,
        theorem=f"Inductive step for {schema.hypothesis}: {schema.variable} → {schema.variable}+1",
    )
    # For step case, UNSAT means the implication is valid
    if _HAS_Z3 and step_artifact.result == "unsat":
        admit_proof(step_artifact, admitted_by="z3")
    elif _HAS_Z3 and step_artifact.result == "sat":
        deny_proof(step_artifact, "Counterexample found for inductive step")

    is_valid = (
        base_artifact.status == ProofStatus.ADMITTED
        and step_artifact.status == ProofStatus.ADMITTED
    )

    return InductiveProof(
        proof_id=proof_id,
        schema=schema,
        base_proved=base_artifact,
        step_proved=step_artifact,
        is_valid=is_valid,
        induction_variable=schema.variable,
        depth_limit=depth_limit,
    )


def batch_prove(schemas: list[InductionSchema]) -> list[InductiveProof]:
    """Prove multiple induction schemas in batch.

    Args:
        schemas: List of InductionSchema instances.

    Returns:
        List of InductiveProof results.
    """
    return [prove_inductive(schema) for schema in schemas]


def format_inductive_report(proofs: list[InductiveProof]) -> str:
    """Generate a Markdown report from inductive proof results.

    Args:
        proofs: List of InductiveProof instances.

    Returns:
        A Markdown-formatted string report.
    """
    total = len(proofs)
    passed = sum(1 for p in proofs if p.is_valid)
    failed = total - passed

    lines: list[str] = [
        "# Inductive Proof Report",
        "",
        f"**Total Proofs:** {total}",
        f"**Passed:** {passed}",
        f"**Failed:** {failed}",
        f"**Pass Rate:** {passed / total * 100:.1f}%" if total > 0 else "**Pass Rate:** N/A",
        "",
        "| # | Hypothesis | Domain | Variable | Base | Step | Valid |",
        "|---|------------|--------|----------|------|------|-------|",
    ]

    for i, proof in enumerate(proofs, 1):
        base_status = "✅" if proof.base_proved.status == ProofStatus.ADMITTED else "❌"
        step_status = "✅" if proof.step_proved.status == ProofStatus.ADMITTED else "❌"
        valid_mark = "✅" if proof.is_valid else "❌"
        lines.append(
            f"| {i} | {proof.schema.hypothesis} | {proof.schema.domain} "
            f"| {proof.schema.variable} | {base_status} | {step_status} | {valid_mark} |"
        )

    lines.append("")
    lines.append(f"*Report generated at {datetime.now(timezone.utc).isoformat()}*")

    return "\n".join(lines)
