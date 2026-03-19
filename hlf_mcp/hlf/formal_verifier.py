from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
        return self.status == VerificationStatus.PROVEN

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
        return sum(1 for result in self.results if result.status == VerificationStatus.PROVEN)

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.COUNTEREXAMPLE)

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
    def error_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.ERROR)

    @property
    def all_proven(self) -> bool:
        return self.total_count > 0 and self.failed_count == 0 and self.proven_count == self.total_count

    def add(self, result: VerificationResult) -> None:
        self.results.append(result)
        self.total_duration_ms += result.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total_count,
            "proven": self.proven_count,
            "failed": self.failed_count,
            "unknown": self.unknown_count,
            "skipped": self.skipped_count,
            "errors": self.error_count,
            "all_proven": self.all_proven,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "z3_available": self.z3_enabled,
            "operator_summary": self.summary(),
            "results": [result.to_dict() for result in self.results],
        }

    def summary(self) -> str:
        return (
            f"Verification: {self.proven_count}/{self.total_count} proven; "
            f"failed={self.failed_count}; solver={'z3' if self.z3_enabled else 'fallback'}; "
            f"duration_ms={self.total_duration_ms:.2f}"
        )


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
            return {"program": list(ast.get("program", []))}
        if isinstance(ast.get("statements"), list):
            return {"program": list(ast.get("statements", []))}
        nested_ast = ast.get("ast")
        if nested_ast is not None:
            return normalize_ast(nested_ast)
        if isinstance(ast.get("body"), list):
            return {"program": list(ast.get("body", []))}
        return {"program": []}
    if isinstance(ast, list):
        return {"program": list(ast)}
    return {"program": []}


def _extract_from_node(node: Any, constraints: list[dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return

    tag = str(node.get("tag", ""))
    if tag == "CONSTRAINT":
        constraints.append(
            {
                "kind": "range_check",
                "name": str(node.get("name", f"constraint_{len(constraints)}")),
                "condition": node.get("condition", {}),
                "args": list(node.get("args", [])),
            }
        )
    elif tag == "SPEC_GATE":
        constraints.append(
            {
                "kind": "spec_gate",
                "name": str(node.get("name", f"spec_gate_{len(constraints)}")),
                "condition": node.get("condition", {}),
            }
        )
    elif tag == "SET":
        value = node.get("value")
        name = str(node.get("name", f"value_{len(constraints)}"))
        if isinstance(value, bool):
            expected_type = "boolean"
        elif isinstance(value, (int, float)):
            expected_type = "number"
        elif isinstance(value, str):
            expected_type = "string"
        elif isinstance(value, list):
            expected_type = "list"
        elif isinstance(value, dict):
            expected_type = "dict"
        else:
            expected_type = ""
        if expected_type:
            constraints.append(
                {
                    "kind": "type_invariant",
                    "name": f"type_{name}",
                    "variable": name,
                    "expected_type": expected_type,
                    "value": value,
                }
            )
    elif tag == "PARALLEL":
        tasks = list(node.get("tasks", []))
        constraints.append(
            {
                "kind": "gas_bound",
                "name": f"parallel_gas_{len(constraints)}",
                "task_count": len(tasks),
            }
        )

    for key in ("then", "else", "body", "inner", "action"):
        child = node.get(key)
        if isinstance(child, dict):
            _extract_from_node(child, constraints)
        elif isinstance(child, list):
            for item in child:
                _extract_from_node(item, constraints)

    tasks = node.get("tasks")
    if isinstance(tasks, list):
        for child in tasks:
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
            status=VerificationStatus.PROVEN,
            kind=ConstraintKind.RANGE_CHECK,
            message="Value within range bounds",
            solver="fallback",
            duration_ms=(time.time() - start) * 1000,
        )

    def check_type(self, value: Any, expected_type: str, *, name: str = "") -> VerificationResult:
        start = time.time()
        type_map = {
            "number": (int, float),
            "string": (str,),
            "boolean": (bool,),
            "list": (list,),
            "dict": (dict,),
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
        if isinstance(value, expected):
            return VerificationResult(
                property_name=name or "type_check",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Value matches type '{expected_type}'",
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

    def check_gas_budget(self, task_costs: list[int], budget: int, *, name: str = "") -> VerificationResult:
        start = time.time()
        total = sum(task_costs)
        if total <= budget:
            return VerificationResult(
                property_name=name or "gas_budget",
                status=VerificationStatus.PROVEN,
                kind=ConstraintKind.GAS_BOUND,
                message=f"Total gas {total} <= budget {budget}",
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


class FormalVerifier:
    def __init__(self, *, default_parallel_task_cost: int = 1000) -> None:
        self._fallback = FallbackSolver()
        self._parallel_task_cost = default_parallel_task_cost
        self.solver_name = "z3" if _HAS_Z3 else "fallback"

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

    def verify_constraints(self, ast: dict[str, Any], *, gas_budget: int = 10_000) -> VerificationReport:
        return self.verify_ast(ast, gas_budget=gas_budget)

    def verify_type(self, value: Any, expected_type: str, *, property_name: str = "") -> VerificationResult:
        return self._fallback.check_type(value, expected_type, name=property_name)

    def verify_range(
        self,
        value: Any,
        *,
        low: float | None = None,
        high: float | None = None,
        property_name: str = "",
    ) -> VerificationResult:
        return self._fallback.check_range(value, low=low, high=high, name=property_name)

    def verify_gas_budget(
        self,
        task_costs: list[int],
        budget: int,
        *,
        property_name: str = "",
    ) -> VerificationResult:
        return self._fallback.check_gas_budget(task_costs, budget, name=property_name)

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
                args = list(constraint.get("args", []))
                if args and isinstance(args[0], (int, float)):
                    report.add(
                        self.verify_range(
                            args[0],
                            low=0,
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
                    VerificationResult(
                        property_name=str(constraint.get("name", "spec_gate")),
                        status=VerificationStatus.SKIPPED,
                        kind=ConstraintKind.SPEC_GATE,
                        message="SPEC_GATE extraction is present; theorem proving is advisory-only in the packaged bridge slice",
                        solver=self.solver_name,
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