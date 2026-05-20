"""High-quality counterexample generation for the HLF formal verifier.

Produces human-readable counterexamples with plain-English explanations,
fix suggestions, and informative comparison between alternatives.

All features degrade gracefully when Z3 is unavailable — counterexamples
are still generated from fallback solver results, just with less depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.formal_verifier import (
    ConstraintKind,
    VerificationResult,
    VerificationStatus,
)

_HAS_Z3 = False
try:
    import z3  # type: ignore[import-untyped]

    _HAS_Z3 = True
except ImportError:
    z3 = None  # type: ignore[assignment]


# ─────────────────────────────────────────────────────────────────────
# Counterexample dataclass
# ─────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Counterexample:
    """A human-readable counterexample explaining a verification failure.

    Designed as the operator-facing surface for proof failures.
    Each field is plain-text suitable for log output, dashboards,
    or operator consoles.
    """

    property_name: str
    """The property that was violated."""

    inputs: dict[str, Any]
    """The concrete input values that trigger the violation."""

    expected_output: str
    """What the property asserted should hold."""

    actual_output: str
    """What was actually observed."""

    violation_path: str
    """Step-by-step trace of how the violation manifests."""

    severity: str = "error"
    """Severity classification: 'error', 'warning', or 'info'."""

    kind: str = ""
    """Constraint kind that was violated (range_check, type_invariant, etc.)."""

    solver: str = ""
    """Solver that produced this counterexample (z3, fallback)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "property_name": self.property_name,
            "inputs": self.inputs,
            "expected_output": self.expected_output,
            "actual_output": self.actual_output,
            "violation_path": self.violation_path,
            "severity": self.severity,
            "kind": self.kind,
            "solver": self.solver,
        }

    def is_actionable(self) -> bool:
        """Whether this counterexample provides enough information to act on."""
        return bool(self.inputs) and bool(self.violation_path)


# ─────────────────────────────────────────────────────────────────────
# InductiveCounterexample dataclass
# ─────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class InductiveCounterexample(Counterexample):
    """Specialized counterexample for inductive proof failures.

    Extends Counterexample with induction-specific failure modes:
    - Base case failures (the smallest case doesn't hold)
    - Step case failures (P(k) holds but P(k+1) doesn't)
    - Termination failures (measure not well-founded)
    - Unwinding failures (induction depth limit reached)
    """

    induction_pattern: str = "none"
    """Detected induction pattern: 'loop', 'recursion', 'range', 'numeric', 'structural'."""

    failure_type: str = ""
    """Specific failure type: 'base_case', 'step_case', 'termination', 'unwinding'."""

    base_case_inputs: dict[str, Any] = field(default_factory=dict)
    """The inputs that cause the base case to fail."""

    step_k_value: Any = None
    """The k value where P(k) holds but P(k+1) fails."""

    step_k_plus_1_value: Any = None
    """The k+1 value where the property fails."""

    termination_measure: str = ""
    """The termination measure expression that was checked."""

    unwinding_depth: int = 0
    """How deep induction was unwound before failure."""

    fix_strategy: str = ""
    """Induction-specific fix strategy (strengthen invariant, add base case, etc.)."""

    def to_dict(self) -> dict[str, Any]:
        """Include induction-specific fields in serialization."""
        base = Counterexample.to_dict(self)
        base.update({
            "induction_pattern": self.induction_pattern,
            "failure_type": self.failure_type,
            "base_case_inputs": self.base_case_inputs,
            "step_k_value": self.step_k_value,
            "step_k_plus_1_value": self.step_k_plus_1_value,
            "termination_measure": self.termination_measure,
            "unwinding_depth": self.unwinding_depth,
            "fix_strategy": self.fix_strategy,
        })
        return base

    def is_base_case_failure(self) -> bool:
        """Whether this is specifically a base case failure."""
        return self.failure_type == "base_case"

    def is_step_case_failure(self) -> bool:
        """Whether this is specifically a step case failure."""
        return self.failure_type == "step_case"

    def is_termination_failure(self) -> bool:
        """Whether this is specifically a termination measure failure."""
        return self.failure_type == "termination"

    def is_unwinding_failure(self) -> bool:
        """Whether this is specifically an unwinding/depth-limit failure."""
        return self.failure_type == "unwinding"


# ─────────────────────────────────────────────────────────────────────
# Violation patterns for fix suggestion heuristics
# ─────────────────────────────────────────────────────────────────────

_VIOLATION_PATTERNS: dict[str, dict[str, str]] = {
    "below_low": {
        "pattern": "Value is below the allowed minimum",
        "suggestion": "Increase the value to meet or exceed the minimum bound",
    },
    "above_high": {
        "pattern": "Value exceeds the allowed maximum",
        "suggestion": "Decrease the value to stay within the maximum bound",
    },
    "type_mismatch": {
        "pattern": "Value has an unexpected type",
        "suggestion": "Ensure the value conforms to the expected type annotation",
    },
    "gas_exceeded": {
        "pattern": "Total gas cost exceeds the budget",
        "suggestion": "Reduce task costs or increase the gas budget",
    },
    "spec_gate_false": {
        "pattern": "A required SPEC_GATE literal resolved to false",
        "suggestion": "Set the gating field to true or provide an alternative proof contract",
    },
    "unresolvable_gate": {
        "pattern": "SPEC_GATE could not be discharged",
        "suggestion": "Add deterministic literal fields to the SPEC_GATE or use a typed effect declaration",
    },
    "rational_zero_denom": {
        "pattern": "Rational denominator is zero",
        "suggestion": "Ensure the denominator is a non-zero integer",
    },
    "bool_for_numeric": {
        "pattern": "A boolean was provided where a numeric type was expected",
        "suggestion": "Use a numeric value instead of a boolean",
    },
    "inductive_base_failed": {
        "pattern": "Base case of induction fails to hold",
        "suggestion": "Verify the smallest input case(s). Add explicit base case guards.",
    },
    "inductive_step_failed": {
        "pattern": "Inductive step P(k) → P(k+1) does not hold",
        "suggestion": "Strengthen the induction hypothesis or add auxiliary invariants that carry through the step.",
    },
    "inductive_termination_failed": {
        "pattern": "Termination measure is not well-founded",
        "suggestion": "Provide a decreasing integer measure or structural descent argument that provably terminates.",
    },
    "inductive_unwinding_limit": {
        "pattern": "Induction unwinding reached depth limit without proof",
        "suggestion": "Increase the unwinding bound or add a stronger inductive invariant to close the proof earlier.",
    },
}


# ─────────────────────────────────────────────────────────────────────
# CounterexampleGenerator
# ─────────────────────────────────────────────────────────────────────


class CounterexampleGenerator:
    """Produces high-quality, human-readable counterexamples.

    Can generate counterexamples from VerificationResult objects
    (produced by the formal verifier) or from raw property/model pairs.

    All methods work without Z3 — Z3 integration provides deeper
    analysis when available but is never required.
    """

    def __init__(self) -> None:
        self._z3_ctx = z3.Context() if _HAS_Z3 and z3 is not None else None

    @property
    def z3_available(self) -> bool:
        return self._z3_ctx is not None

    # ── Primary generation ──────────────────────────────────────

    def generate(self, result: VerificationResult) -> Counterexample:
        """Generate a Counterexample from a VerificationResult.

        Args:
            result: A VerificationResult with status COUNTEREXAMPLE or ERROR.

        Returns:
            A Counterexample with human-readable fields populated.

        If the result is not a counterexample, returns a minimal Counterexample
        with severity='info' indicating no violation was found.
        """
        ce_data = result.counterexample or {}

        kind = result.kind.value if isinstance(result.kind, ConstraintKind) else str(result.kind)
        property_name = result.property_name

        if result.status == VerificationStatus.COUNTEREXAMPLE:
            inputs, expected, actual, path = self._decompose_counterexample(
                result, ce_data, kind
            )
            return Counterexample(
                property_name=property_name,
                inputs=inputs,
                expected_output=expected,
                actual_output=actual,
                violation_path=path,
                severity="error",
                kind=kind,
                solver=result.solver,
            )

        if result.status == VerificationStatus.ERROR:
            return Counterexample(
                property_name=property_name,
                inputs=ce_data,
                expected_output="Verification should succeed",
                actual_output=result.message,
                violation_path=f"Verification error: {result.message}",
                severity="error",
                kind=kind,
                solver=result.solver,
            )

        # Non-failure results
        return Counterexample(
            property_name=property_name,
            inputs={},
            expected_output="Property should hold",
            actual_output="Property holds",
            violation_path="No violation detected",
            severity="info",
            kind=kind,
            solver=result.solver,
        )

    def _decompose_counterexample(
        self,
        result: VerificationResult,
        ce_data: dict[str, Any],
        kind: str,
    ) -> tuple[dict[str, Any], str, str, str]:
        """Decompose a counterexample dict into human-readable components.

        Returns (inputs, expected_output, actual_output, violation_path).
        """
        if kind == "range_check":
            return self._decompose_range(ce_data)
        if kind == "type_invariant":
            return self._decompose_type(ce_data, result.message)
        if kind == "gas_bound":
            return self._decompose_gas(ce_data)
        if kind == "spec_gate":
            return self._decompose_spec_gate(ce_data, result.message)
        # Generic decomposition
        return self._decompose_generic(ce_data, result.message, kind)

    @staticmethod
    def _decompose_range(ce_data: dict[str, Any]) -> tuple[dict[str, Any], str, str, str]:
        comparison = str(ce_data.get("comparison", ""))
        value = ce_data.get("value", "?")
        bound = ce_data.get("bound", "?")
        inputs = {"value": value}
        if comparison == "below_low":
            expected = f"value >= {bound}"
            actual = f"value = {value} (below minimum)"
            path = f"The value {value} is less than the minimum allowed bound of {bound}"
        elif comparison == "above_high":
            expected = f"value <= {bound}"
            actual = f"value = {value} (above maximum)"
            path = f"The value {value} exceeds the maximum allowed bound of {bound}"
        else:
            low = ce_data.get("low")
            high = ce_data.get("high")
            if low is not None and high is not None:
                expected = f"value in [{low}, {high}]"
                actual = f"value = {value} (outside range)"
                path = f"The value {value} is outside the allowed range [{low}, {high}]"
            else:
                expected = "value within bounds"
                actual = f"value = {value} (out of bounds)"
                path = f"The value {value} violates the range constraint"
        return inputs, expected, actual, path

    @staticmethod
    def _decompose_type(ce_data: dict[str, Any], message: str) -> tuple[dict[str, Any], str, str, str]:
        actual_type = str(ce_data.get("actual_type", "unknown"))
        value = ce_data.get("value", "?")
        inputs = {"value": value}
        if actual_type == "rational_zero_denom":
            expected = "rational with non-zero denominator"
            actual = f"rational with denominator = 0 (value={value})"
            path = "A rational value was provided with a zero denominator, which is undefined"
        elif actual_type == "bool":
            expected = "non-boolean value"
            actual = f"boolean value ({value})"
            path = f"A boolean ({value}) was provided where a non-boolean type was expected"
        else:
            expected = f"value of expected type"
            actual = f"value of type '{actual_type}' ({value})"
            path = f"Type mismatch: {message}"
        return inputs, expected, actual, path

    @staticmethod
    def _decompose_gas(ce_data: dict[str, Any]) -> tuple[dict[str, Any], str, str, str]:
        total = ce_data.get("total_gas", 0)
        budget = ce_data.get("budget", 0)
        over_by = ce_data.get("over_by", 0)
        inputs = {"total_gas": total, "budget": budget}
        expected = f"total_gas <= {budget}"
        actual = f"total_gas = {total} (over by {over_by})"
        path = (
            f"Total gas cost of {total} exceeds the budget of {budget} "
            f"by {over_by} units. Reduce parallel task count or increase budget."
        )
        return inputs, expected, actual, path

    @staticmethod
    def _decompose_spec_gate(ce_data: dict[str, Any], message: str) -> tuple[dict[str, Any], str, str, str]:
        field = str(ce_data.get("field", "?"))
        value = ce_data.get("value")
        inputs = {"field": field, "value": value}
        if "unresolvable" in message.lower():
            expected = "SPEC_GATE with deterministic proof contract"
            actual = "SPEC_GATE without resolvable literal fields"
            path = (
                "The SPEC_GATE cannot be discharged because no deterministic "
                "literal proof contract was available. Add explicit boolean "
                "fields or use a typed effect declaration."
            )
        else:
            expected = f"'{field}' = true"
            actual = f"'{field}' = {value} (false)"
            path = (
                f"The SPEC_GATE field '{field}' resolved to false. "
                f"Set it to true or provide an alternative proof path."
            )
        return inputs, expected, actual, path

    @staticmethod
    def _decompose_generic(
        ce_data: dict[str, Any], message: str, kind: str
    ) -> tuple[dict[str, Any], str, str, str]:
        inputs = dict(ce_data)
        expected = "property should hold"
        actual = message
        path = f"Violation of {kind} constraint: {message}"
        return inputs, expected, actual, path

    # ── Minimal counterexample ───────────────────────────────────

    def generate_minimal_counterexample(
        self, property_name: str, model: dict[str, Any]
    ) -> Counterexample:
        """Generate the smallest failing input for a property.

        Args:
            property_name: The name of the property being checked.
            model: A dict containing the model parameters to minimize.
                Expected keys depend on the constraint kind.

        Returns:
            A Counterexample with the minimal inputs that trigger a violation.

        Works without Z3 by using heuristic minimization. With Z3,
        uses SMT optimization to find the true minimal counterexample.
        """
        kind = str(model.get("kind", "generic"))

        if self.z3_available and kind == "range_check":
            return self._z3_minimize_range(property_name, model)
        if self.z3_available and kind == "gas_bound":
            return self._z3_minimize_gas(property_name, model)

        # Fallback: heuristic minimization
        return self._heuristic_minimize(property_name, model, kind)

    def _z3_minimize_range(self, property_name: str, model: dict[str, Any]) -> Counterexample:
        """Use Z3 optimization to find the minimal violating value."""
        try:
            ctx = self._z3_ctx
            opt = z3.Optimize(ctx=ctx)
            x = z3.Real(property_name, ctx=ctx)
            low = model.get("low")
            high = model.get("high")
            if low is not None:
                opt.add(x < z3.RealVal(float(low), ctx=ctx))
                opt.minimize(z3.RealVal(float(low), ctx=ctx) - x)
            if high is not None:
                opt.add(x > z3.RealVal(float(high), ctx=ctx))
                opt.minimize(x - z3.RealVal(float(high), ctx=ctx))
            if opt.check() == z3.sat:
                z3_model = opt.model()
                value = z3_model.evaluate(x)
                if value is not None:
                    val = float(value.as_fraction())
                    return Counterexample(
                        property_name=property_name,
                        inputs={"minimal_violating_value": val},
                        expected_output=f"value in [{low}, {high}]",
                        actual_output=f"value = {val} (closest violating value)",
                        violation_path=(
                            f"The closest value outside [{low}, {high}] is {val}. "
                            f"Any value further from the bounds would also violate."
                        ),
                        severity="error",
                        kind="range_check",
                        solver="z3",
                    )
        except Exception:
            pass  # Fall through to heuristic
        return self._heuristic_minimize(property_name, model, "range_check")

    def _z3_minimize_gas(self, property_name: str, model: dict[str, Any]) -> Counterexample:
        """Use Z3 optimization to find the minimal gas budget violation."""
        try:
            ctx = self._z3_ctx
            opt = z3.Optimize(ctx=ctx)
            task_count = int(model.get("task_count", 1))
            per_task = int(model.get("per_task_cost", 1000))
            budget = int(model.get("budget", 10000))
            # Variable: actual task count
            n = z3.Int("task_count", ctx=ctx)
            opt.add(n >= 1)
            opt.add(n <= task_count + 10)
            total = n * z3.IntVal(per_task, ctx=ctx)
            opt.add(total > z3.IntVal(budget, ctx=ctx))
            opt.minimize(total - z3.IntVal(budget, ctx=ctx))
            if opt.check() == z3.sat:
                z3_model = opt.model()
                minimal_n = z3_model.evaluate(n)
                if minimal_n is not None:
                    n_val = minimal_n.as_long()
                    return Counterexample(
                        property_name=property_name,
                        inputs={"minimal_violating_tasks": n_val},
                        expected_output=f"tasks * {per_task} <= {budget}",
                        actual_output=f"{n_val} * {per_task} = {n_val * per_task} > {budget}",
                        violation_path=(
                            f"The minimal number of tasks ({n_val}) that exceeds the "
                            f"budget of {budget} with {per_task} gas per task."
                        ),
                        severity="error",
                        kind="gas_bound",
                        solver="z3",
                    )
        except Exception:
            pass
        return self._heuristic_minimize(property_name, model, "gas_bound")

    def _heuristic_minimize(
        self, property_name: str, model: dict[str, Any], kind: str
    ) -> Counterexample:
        """Heuristic minimization without Z3.

        For range checks: if a value violates, report the value.
        For gas: compute the minimal task count that exceeds budget.
        For types: report the offending value directly.
        """
        if kind == "range_check":
            low = model.get("low")
            high = model.get("high")
            value = model.get("value")
            if value is not None:
                return Counterexample(
                    property_name=property_name,
                    inputs={"value": value},
                    expected_output=f"value in [{low}, {high}]",
                    actual_output=f"value = {value}",
                    violation_path=(
                        f"The value {value} violates the range [{low}, {high}]. "
                        f"No smaller violating value could be computed without Z3."
                    ),
                    severity="error",
                    kind=kind,
                    solver="fallback",
                )
        elif kind == "gas_bound":
            task_count = int(model.get("task_count", 0))
            per_task = int(model.get("per_task_cost", 1000))
            budget = int(model.get("budget", 10000))
            total = task_count * per_task
            # Compute minimal task count
            minimal = budget // per_task + 1
            return Counterexample(
                property_name=property_name,
                inputs={
                    "task_count": task_count,
                    "minimal_violating_tasks": minimal,
                },
                expected_output=f"tasks * {per_task} <= {budget}",
                actual_output=f"{task_count} * {per_task} = {total} > {budget}",
                violation_path=(
                    f"Budget exceeded. Minimal violating task count is {minimal} "
                    f"(={minimal * per_task} gas). Current: {task_count} tasks "
                    f"(={total} gas)."
                ),
                severity="error",
                kind=kind,
                solver="fallback",
            )
        elif kind == "type_invariant":
            return Counterexample(
                property_name=property_name,
                inputs={"value": model.get("value", "?")},
                expected_output=f"value of type '{model.get('expected_type', '?')}'",
                actual_output=f"value of type '{model.get('actual_type', '?')}'",
                violation_path=(
                    f"Type mismatch: expected {model.get('expected_type', '?')}, "
                    f"got {model.get('actual_type', '?')}."
                ),
                severity="error",
                kind=kind,
                solver="fallback",
            )

        return Counterexample(
            property_name=property_name,
            inputs=dict(model),
            expected_output="property should hold",
            actual_output="property violated",
            violation_path=f"Violation of {kind}: no minimal counterexample available without Z3",
            severity="error",
            kind=kind,
            solver="fallback",
        )

    # ── Explanation ─────────────────────────────────────────────

    def explain_counterexample(self, counterexample: Counterexample) -> str:
        """Produce a plain-English explanation of a counterexample.

        Args:
            counterexample: The counterexample to explain.

        Returns:
            A multi-line human-readable explanation suitable for
            operator consoles, logs, or audit trails.
        """
        lines = [
            f"Counterexample for property: {counterexample.property_name}",
            f"  Severity: {counterexample.severity}",
            f"  Kind: {counterexample.kind}",
            f"  Solver: {counterexample.solver}",
            "",
            f"  Expected: {counterexample.expected_output}",
            f"  Actual:   {counterexample.actual_output}",
            "",
            f"  Violation path: {counterexample.violation_path}",
        ]
        if counterexample.inputs:
            lines.append("")
            lines.append("  Input values:")
            for key, val in counterexample.inputs.items():
                lines.append(f"    {key} = {val}")
        lines.append("")
        fix = self.suggest_fix(counterexample)
        lines.append(f"  Suggested fix: {fix}")
        return "\n".join(lines)

    # ── Fix suggestion ──────────────────────────────────────────

    def suggest_fix(self, counterexample: Counterexample) -> str:
        """Suggest a heuristic fix based on the violation pattern.

        Args:
            counterexample: The counterexample to analyze.

        Returns:
            A plain-English suggestion for how to fix the violation.
        """
        kind = counterexample.kind
        inputs = counterexample.inputs
        violation = counterexample.violation_path.lower()

        # Pattern-match the counterexample to known violation patterns
        if kind == "range_check":
            if "below" in violation:
                return _VIOLATION_PATTERNS["below_low"]["suggestion"]
            if "above" in violation or "exceeds" in violation:
                return _VIOLATION_PATTERNS["above_high"]["suggestion"]
            if "outside" in violation:
                # Determine direction from inputs
                value = inputs.get("value")
                if isinstance(value, (int, float)):
                    low = inputs.get("low")
                    high = inputs.get("high")
                    if low is not None and isinstance(low, (int, float)) and value < low:
                        return _VIOLATION_PATTERNS["below_low"]["suggestion"]
                    if high is not None and isinstance(high, (int, float)) and value > high:
                        return _VIOLATION_PATTERNS["above_high"]["suggestion"]
            return "Adjust the value to fall within the allowed range"

        if kind == "type_invariant":
            if "zero" in violation:
                return _VIOLATION_PATTERNS["rational_zero_denom"]["suggestion"]
            if "boolean" in violation or "bool" in violation:
                return _VIOLATION_PATTERNS["bool_for_numeric"]["suggestion"]
            return _VIOLATION_PATTERNS["type_mismatch"]["suggestion"]

        if kind == "gas_bound":
            return _VIOLATION_PATTERNS["gas_exceeded"]["suggestion"]

        if kind == "spec_gate":
            if "unresolvable" in violation:
                return _VIOLATION_PATTERNS["unresolvable_gate"]["suggestion"]
            return _VIOLATION_PATTERNS["spec_gate_false"]["suggestion"]

        # Generic fallback
        return "Review the constraint definition and ensure inputs satisfy all conditions"

    # ── Comparison ──────────────────────────────────────────────

    def compare_counterexamples(
        self, a: Counterexample, b: Counterexample
    ) -> str:
        """Compare two counterexamples and determine which is more informative.

        Args:
            a: First counterexample.
            b: Second counterexample.

        Returns:
            A string describing which is more informative and why.
            Possible values: 'a', 'b', 'equal', or a descriptive message.
        """
        score_a = self._informativeness_score(a)
        score_b = self._informativeness_score(b)

        if score_a > score_b:
            winner = "a"
            reason = self._compare_reason(a, b, score_a, score_b)
        elif score_b > score_a:
            winner = "b"
            reason = self._compare_reason(b, a, score_b, score_a)
        else:
            return "equal"

        return f"{winner}: {reason}"

    def _informativeness_score(self, ce: Counterexample) -> int:
        """Score a counterexample by how informative it is (0-10)."""
        score = 0
        # Has concrete inputs: +3
        if ce.inputs:
            score += 3
        # Has detailed violation path: +2 (longer = more detail, capping at 2)
        if len(ce.violation_path) > 40:
            score += 2
        elif ce.violation_path:
            score += 1
        # Z3-backed: +2 (formal SMT is more informative)
        if ce.solver == "z3":
            score += 2
        # Severity is error: +1 (errors are more actionable)
        if ce.severity == "error":
            score += 1
        # Has expected/actual divergence: +2
        if ce.expected_output and ce.actual_output and ce.expected_output != ce.actual_output:
            score += 2
        return score

    @staticmethod
    def _compare_reason(
        winner: Counterexample, loser: Counterexample, score_w: int, score_l: int
    ) -> str:
        """Build a human-readable reason for the comparison result."""
        reasons = []
        if winner.solver == "z3" and loser.solver != "z3":
            reasons.append("Z3-backed (formal SMT proof)")
        if len(winner.violation_path) > len(loser.violation_path):
            reasons.append("more detailed violation path")
        if winner.inputs and not loser.inputs:
            reasons.append("provides concrete input values")
        if winner.severity == "error" and loser.severity != "error":
            reasons.append("higher severity (error)")
        if reasons:
            return f"more informative ({'; '.join(reasons)})"
        return f"score {score_w} vs {score_l}"


# ─────────────────────────────────────────────────────────────────────
# InductiveCounterexampleGenerator
# ─────────────────────────────────────────────────────────────────────


class InductiveCounterexampleGenerator:
    """Generates induction-specific counterexamples with fix strategies."""

    def __init__(self) -> None:
        self._z3_ctx = z3.Context() if _HAS_Z3 and z3 is not None else None

    @property
    def z3_available(self) -> bool:
        """Whether Z3 is available for deeper induction analysis."""
        return self._z3_ctx is not None

    def generate_base_case_failure(
        self,
        property_name: str,
        inputs: dict[str, Any],
        induction_pattern: str = "numeric",
    ) -> InductiveCounterexample:
        """Generate a counterexample for a failed base case.

        Args:
            property_name: The property whose base case failed.
            inputs: The inputs that cause the base case to fail.
            induction_pattern: The detected induction pattern.

        Returns:
            An InductiveCounterexample describing the base case failure.
        """
        return InductiveCounterexample(
            property_name=property_name,
            inputs=inputs,
            expected_output=f"P({list(inputs.values())[0] if inputs else 'base'}) should hold",
            actual_output=f"Base case P({list(inputs.values())[0] if inputs else 'base'}) does not hold",
            violation_path=(
                f"The base case of induction on '{property_name}' fails for inputs "
                f"{inputs}. The smallest case does not satisfy the property."
            ),
            severity="error",
            kind="inductive_base_failed",
            solver="z3" if self.z3_available else "fallback",
            induction_pattern=induction_pattern,
            failure_type="base_case",
            base_case_inputs=inputs,
            fix_strategy=(
                "Add or correct the base case. "
                "Verify P(0) or P(empty) holds."
            ),
        )

    def generate_step_case_failure(
        self,
        property_name: str,
        k_value: Any,
        k_plus_1_value: Any,
        property_desc: str = "",
        induction_pattern: str = "numeric",
    ) -> InductiveCounterexample:
        """Generate a counterexample where P(k) holds but P(k+1) fails.

        Args:
            property_name: The property whose step case failed.
            k_value: The k where P(k) holds.
            k_plus_1_value: The k+1 where the property fails.
            property_desc: Optional description of the property.
            induction_pattern: The detected induction pattern.

        Returns:
            An InductiveCounterexample describing the step case failure.
        """
        desc = f" ({property_desc})" if property_desc else ""
        return InductiveCounterexample(
            property_name=property_name,
            inputs={"k": k_value, "k+1": k_plus_1_value},
            expected_output=f"P(k+1) should hold given P(k){desc}",
            actual_output=(
                f"P({k_value}) holds, but P({k_plus_1_value}) does not hold"
            ),
            violation_path=(
                f"The inductive step fails: P({k_value}) is true but the step to "
                f"P({k_plus_1_value}) does not preserve the property{desc}. "
                f"The induction hypothesis is too weak to carry through."
            ),
            severity="error",
            kind="inductive_step_failed",
            solver="z3" if self.z3_available else "fallback",
            induction_pattern=induction_pattern,
            failure_type="step_case",
            step_k_value=k_value,
            step_k_plus_1_value=k_plus_1_value,
            fix_strategy=(
                "Strengthen the induction hypothesis. "
                "The invariant may be too weak to carry through the step."
            ),
        )

    def generate_termination_failure(
        self,
        property_name: str,
        measure_expr: str,
        counterexample_detail: str = "",
        induction_pattern: str = "recursion",
    ) -> InductiveCounterexample:
        """Generate a counterexample for a non-well-founded termination measure.

        Args:
            property_name: The property whose termination measure failed.
            measure_expr: The termination measure expression that was checked.
            counterexample_detail: Additional detail about the failure.
            induction_pattern: The detected induction pattern.

        Returns:
            An InductiveCounterexample describing the termination failure.
        """
        detail = f": {counterexample_detail}" if counterexample_detail else ""
        return InductiveCounterexample(
            property_name=property_name,
            inputs={"measure": measure_expr},
            expected_output=(
                f"Termination measure '{measure_expr}' should be well-founded "
                f"(strictly decreasing)"
            ),
            actual_output=(
                f"Termination measure '{measure_expr}' is not well-founded{detail}"
            ),
            violation_path=(
                f"The termination measure '{measure_expr}' for induction on "
                f"'{property_name}' is not well-founded{detail}. "
                f"It must strictly decrease on each recursive call or loop iteration."
            ),
            severity="error",
            kind="inductive_termination_failed",
            solver="z3" if self.z3_available else "fallback",
            induction_pattern=induction_pattern,
            failure_type="termination",
            termination_measure=measure_expr,
            fix_strategy=(
                "Add a well-founded termination measure "
                "(decreasing integer, structural descent)."
            ),
        )

    def generate_unwinding_failure(
        self,
        property_name: str,
        depth: int,
        partial_findings: str = "",
        induction_pattern: str = "numeric",
    ) -> InductiveCounterexample:
        """Generate a counterexample when induction unwinding hits a depth limit.

        Args:
            property_name: The property where unwinding hit the limit.
            depth: How deep induction was unwound.
            partial_findings: Optional partial findings before the limit.
            induction_pattern: The detected induction pattern.

        Returns:
            An InductiveCounterexample describing the unwinding failure.
        """
        findings = f" Partial findings: {partial_findings}" if partial_findings else ""
        return InductiveCounterexample(
            property_name=property_name,
            inputs={"unwinding_depth": depth},
            expected_output=(
                f"Induction on '{property_name}' should complete within {depth} steps"
            ),
            actual_output=(
                f"Induction unwinding reached depth {depth} without completing the proof"
            ),
            violation_path=(
                f"Induction on '{property_name}' was unwound to depth {depth} "
                f"without reaching a proof.{findings} "
                f"Consider increasing the bound or adding a stronger invariant."
            ),
            severity="error",
            kind="inductive_unwinding_limit",
            solver="z3" if self.z3_available else "fallback",
            induction_pattern=induction_pattern,
            failure_type="unwinding",
            unwinding_depth=depth,
            fix_strategy=(
                "Increase the induction depth limit or add a more aggressive "
                "termination measure."
            ),
        )

    def suggest_inductive_fix(self, ce: InductiveCounterexample) -> str:
        """Suggest a fix strategy based on the induction failure type.

        Args:
            ce: The InductiveCounterexample to analyze.

        Returns:
            A plain-English fix suggestion for the induction failure.
        """
        if ce.is_base_case_failure():
            return (
                "Add or correct the base case. "
                "Verify P(0) or P(empty) holds."
            )
        if ce.is_step_case_failure():
            return (
                "Strengthen the induction hypothesis. "
                "The invariant may be too weak to carry through the step."
            )
        if ce.is_termination_failure():
            return (
                "Add a well-founded termination measure "
                "(decreasing integer, structural descent)."
            )
        if ce.is_unwinding_failure():
            return (
                "Increase the induction depth limit or add a more aggressive "
                "termination measure."
            )
        # Fallback: return the pre-computed fix strategy if available
        if ce.fix_strategy:
            return ce.fix_strategy
        return (
            "Review the induction setup. Ensure base cases, step cases, "
            "and termination measures are correctly specified."
        )


# ─────────────────────────────────────────────────────────────────────
# Top-level convenience functions
# ─────────────────────────────────────────────────────────────────────

_generator: CounterexampleGenerator | None = None


def _get_generator() -> CounterexampleGenerator:
    """Lazy-init the singleton generator."""
    global _generator
    if _generator is None:
        _generator = CounterexampleGenerator()
    return _generator


def generate_minimal_counterexample(
    property_name: str,
    model: dict[str, Any],
) -> Counterexample:
    """Generate the smallest failing input for a property.

    Convenience function that delegates to CounterexampleGenerator.
    """
    return _get_generator().generate_minimal_counterexample(property_name, model)


def explain_counterexample(counterexample: Counterexample) -> str:
    """Produce a plain-English explanation of a counterexample.

    Convenience function that delegates to CounterexampleGenerator.
    """
    return _get_generator().explain_counterexample(counterexample)


def suggest_fix(counterexample: Counterexample) -> str:
    """Suggest a heuristic fix based on the violation pattern.

    Convenience function that delegates to CounterexampleGenerator.
    """
    return _get_generator().suggest_fix(counterexample)


def compare_counterexamples(a: Counterexample, b: Counterexample) -> str:
    """Compare two counterexamples and determine which is more informative.

    Convenience function that delegates to CounterexampleGenerator.
    """
    return _get_generator().compare_counterexamples(a, b)


# ─────────────────────────────────────────────────────────────────────
# Top-level convenience functions – induction
# ─────────────────────────────────────────────────────────────────────

_inductive_generator: InductiveCounterexampleGenerator | None = None


def _get_inductive_generator() -> InductiveCounterexampleGenerator:
    """Lazy-init the singleton inductive generator."""
    global _inductive_generator
    if _inductive_generator is None:
        _inductive_generator = InductiveCounterexampleGenerator()
    return _inductive_generator


def generate_inductive_counterexample(
    failure_type: str,
    property_name: str,
    **kwargs: Any,
) -> InductiveCounterexample:
    """Generate an induction-specific counterexample.

    Convenience function that delegates to InductiveCounterexampleGenerator.

    Args:
        failure_type: One of 'base_case', 'step_case', 'termination', 'unwinding'.
        property_name: The name of the property that failed.
        **kwargs: Additional arguments passed to the specific generator method.
            For base_case: inputs (dict), induction_pattern (str).
            For step_case: k_value, k_plus_1_value, property_desc, induction_pattern.
            For termination: measure_expr, counterexample_detail, induction_pattern.
            For unwinding: depth, partial_findings, induction_pattern.

    Returns:
        An InductiveCounterexample describing the failure.
    """
    gen = _get_inductive_generator()
    if failure_type == "base_case":
        return gen.generate_base_case_failure(
            property_name,
            kwargs.get("inputs", {}),
            kwargs.get("induction_pattern", "numeric"),
        )
    elif failure_type == "step_case":
        return gen.generate_step_case_failure(
            property_name,
            kwargs.get("k_value"),
            kwargs.get("k_plus_1_value"),
            kwargs.get("property_desc", ""),
            kwargs.get("induction_pattern", "numeric"),
        )
    elif failure_type == "termination":
        return gen.generate_termination_failure(
            property_name,
            kwargs.get("measure_expr", ""),
            kwargs.get("counterexample_detail", ""),
            kwargs.get("induction_pattern", "recursion"),
        )
    elif failure_type == "unwinding":
        return gen.generate_unwinding_failure(
            property_name,
            kwargs.get("depth", 0),
            kwargs.get("partial_findings", ""),
            kwargs.get("induction_pattern", "numeric"),
        )
    else:
        return InductiveCounterexample(
            property_name=property_name,
            inputs={},
            expected_output="induction proof",
            actual_output="unknown failure",
            violation_path="Unknown induction failure",
            failure_type=failure_type,
        )


def suggest_inductive_fix(counterexample: InductiveCounterexample) -> str:
    """Suggest a fix strategy for an inductive proof failure.

    Convenience function that delegates to InductiveCounterexampleGenerator.
    """
    return _get_inductive_generator().suggest_inductive_fix(counterexample)
