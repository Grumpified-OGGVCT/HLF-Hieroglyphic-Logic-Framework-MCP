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
    RUNTIME_CHECKED = "runtime_checked"
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
        return self.status in (VerificationStatus.PROVEN, VerificationStatus.RUNTIME_CHECKED)

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
        return sum(
            1
            for result in self.results
            if result.status
            in (VerificationStatus.PROVEN, VerificationStatus.RUNTIME_CHECKED)
        )

    @property
    def failed_count(self) -> int:
        return sum(
            1 for result in self.results if result.status == VerificationStatus.COUNTEREXAMPLE
        )

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
    def runtime_checked_count(self) -> int:
        return sum(
            1
            for result in self.results
            if result.status == VerificationStatus.RUNTIME_CHECKED
        )

    @property
    def formally_proven_count(self) -> int:
        return sum(
            1 for result in self.results if result.status == VerificationStatus.PROVEN
        )

    @property
    def error_count(self) -> int:
        return sum(1 for result in self.results if result.status == VerificationStatus.ERROR)

    @property
    def all_proven(self) -> bool:
        return (
            self.total_count > 0
            and self.failed_count == 0
            and self.proven_count == self.total_count
        )

    def add(self, result: VerificationResult) -> None:
        self.results.append(result)
        self.total_duration_ms += result.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total_count,
            "proven": self.proven_count,
            "formally_proven": self.formally_proven_count,
            "runtime_checked": self.runtime_checked_count,
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
        solver = "z3" if self.z3_enabled else "fallback"
        formally = self.formally_proven_count
        runtime = self.runtime_checked_count
        detail = f"formally_proven={formally}, runtime_checked={runtime}"
        return (
            f"Verification: {self.proven_count}/{self.total_count} passed ({detail}); "
            f"failed={self.failed_count}; solver={solver}; "
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
            return {
                "program": list(ast.get("program", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        if isinstance(ast.get("statements"), list):
            return {
                "program": list(ast.get("statements", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        nested_ast = ast.get("ast")
        if nested_ast is not None:
            return normalize_ast(nested_ast)
        if isinstance(ast.get("body"), list):
            return {
                "program": list(ast.get("body", [])),
                "env": dict(ast.get("env", {})) if isinstance(ast.get("env"), dict) else {},
            }
        return {"program": [], "env": {}}
    if isinstance(ast, list):
        return {"program": list(ast), "env": {}}
    return {"program": [], "env": {}}


def _decode_value(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("kind") == "value":
            value_type = str(value.get("type", ""))
            scalar = value.get("value")
            if value_type == "ident":
                text = str(scalar).strip().lower()
                if text == "true":
                    return True
                if text == "false":
                    return False
                if text == "null":
                    return None
                return str(scalar)
            if value_type == "var_ref":
                return {"var_ref": str(scalar)}
            return scalar
        if value.get("kind") == "kv_arg":
            return _decode_value(value.get("value"))
    return value


def _decode_arguments(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, list):
        return {}
    decoded: dict[str, Any] = {}
    for argument in arguments:
        if not isinstance(argument, dict):
            continue
        if argument.get("kind") == "kv_arg":
            decoded[str(argument.get("name", ""))] = _decode_value(argument.get("value"))
    return decoded


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _extract_from_node(node: Any, constraints: list[dict[str, Any]]) -> None:
    if not isinstance(node, dict):
        return

    kind = str(node.get("kind", ""))
    tag = str(node.get("tag", ""))
    arguments = _decode_arguments(node.get("arguments", []))
    if tag == "CONSTRAINT":
        name = str(
            arguments.get("name")
            or node.get("name")
            or f"constraint_{len(constraints)}"
        )
        range_value = arguments.get("value")
        if range_value is None:
            numeric_literals = [
                value
                for key, value in arguments.items()
                if key not in {"min", "max"} and isinstance(value, (int, float))
            ]
            if len(numeric_literals) == 1:
                range_value = numeric_literals[0]
        constraints.append(
            {
                "kind": "range_check",
                "name": name,
                "condition": node.get("condition", {}),
                "args": list(node.get("args", [])),
                "value": range_value,
                "low": arguments.get("min"),
                "high": arguments.get("max"),
                "fields": arguments,
            }
        )
    elif tag == "SPEC_GATE" or kind == "spec_gate_stmt":
        gate_name = str(node.get("tag") or node.get("name") or f"spec_gate_{len(constraints)}")
        constraints.append(
            {
                "kind": "spec_gate",
                "name": gate_name,
                "condition": node.get("condition", {}),
                "fields": arguments,
            }
        )
    elif tag == "SET" or kind == "set_stmt":
        value = _decode_value(node.get("value"))
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
    elif tag == "PARALLEL" or kind == "parallel_stmt":
        tasks = list(node.get("tasks", []))
        if not tasks:
            tasks = list(node.get("blocks", []))
        constraints.append(
            {
                "kind": "gas_bound",
                "name": f"parallel_gas_{len(constraints)}",
                "task_count": len(tasks),
            }
        )

    for key in ("then", "else", "body", "inner", "action", "else_clause"):
        child = node.get(key)
        if isinstance(child, dict):
            _extract_from_node(child, constraints)
        elif isinstance(child, list):
            for item in child:
                _extract_from_node(item, constraints)

    for key in ("tasks", "blocks", "statements", "elif_clauses"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
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
            status=VerificationStatus.RUNTIME_CHECKED,
            kind=ConstraintKind.RANGE_CHECK,
            message="Value within range bounds (runtime check)",
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
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.TYPE_INVARIANT,
                message=f"Value matches type '{expected_type}' (runtime check)",
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

    def check_gas_budget(
        self, task_costs: list[int], budget: int, *, name: str = ""
    ) -> VerificationResult:
        start = time.time()
        total = sum(task_costs)
        if total <= budget:
            return VerificationResult(
                property_name=name or "gas_budget",
                status=VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.GAS_BOUND,
                message=f"Total gas {total} <= budget {budget} (runtime check)",
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

    def verify_constraints(
        self, ast: dict[str, Any], *, gas_budget: int = 10_000
    ) -> VerificationReport:
        return self.verify_ast(ast, gas_budget=gas_budget)

    def verify_embodied_contract(self, contract: dict[str, Any] | None) -> VerificationReport:
        report = VerificationReport(z3_enabled=_HAS_Z3)
        if not isinstance(contract, dict) or not contract.get("embodied"):
            return report

        function_name = str(contract.get("function_name") or "embodied_contract")
        action_envelope = (
            dict(contract.get("action_envelope") or {})
            if isinstance(contract.get("action_envelope"), dict)
            else {}
        )
        spatial_bounds = (
            dict(contract.get("spatial_bounds") or {})
            if isinstance(contract.get("spatial_bounds"), dict)
            else {}
        )
        evidence_refs = contract.get("evidence_refs") if isinstance(contract.get("evidence_refs"), list) else []
        world_state_ref = str(contract.get("world_state_ref") or "")
        simulation_only = bool(contract.get("simulation_only", False))
        bounded_spatial_envelope = bool(contract.get("bounded_spatial_envelope", False))

        report.add(
            self.verify_spec_gate(
                fields={"simulation_only": simulation_only},
                property_name=f"{function_name.lower()}_simulation_mode",
            )
        )

        if action_envelope:
            timeout_ms = _numeric_value(action_envelope.get("timeout_ms"))
            if timeout_ms is None:
                report.add(
                    VerificationResult(
                        property_name=f"{function_name.lower()}_timeout_ms",
                        status=VerificationStatus.COUNTEREXAMPLE,
                        kind=ConstraintKind.RANGE_CHECK,
                        message="Embodied action envelope timeout_ms must be a positive numeric literal.",
                        counterexample={"timeout_ms": action_envelope.get("timeout_ms")},
                        solver=self.solver_name,
                    )
                )
            else:
                report.add(
                    self.verify_range(
                        timeout_ms,
                        low=1.0,
                        property_name=f"{function_name.lower()}_timeout_ms",
                    )
                )

            report.add(
                self.verify_spec_gate(
                    fields={"bounded_spatial_envelope": bounded_spatial_envelope},
                    property_name=f"{function_name.lower()}_spatial_envelope",
                )
            )

            for bound_name, bound_value in spatial_bounds.items():
                numeric_bound = _numeric_value(bound_value)
                if numeric_bound is None:
                    report.add(
                        VerificationResult(
                            property_name=f"{function_name.lower()}_{bound_name}",
                            status=VerificationStatus.COUNTEREXAMPLE,
                            kind=ConstraintKind.RANGE_CHECK,
                            message=f"Embodied spatial bound '{bound_name}' must be numeric.",
                            counterexample={"bound": bound_name, "value": bound_value},
                            solver=self.solver_name,
                        )
                    )
                    continue
                report.add(
                    self.verify_range(
                        numeric_bound,
                        low=0.0,
                        property_name=f"{function_name.lower()}_{bound_name}",
                    )
                )

        if function_name in {"WORLD_STATE_RECALL", "TRAJECTORY_PROPOSE"}:
            report.add(
                self.verify_spec_gate(
                    fields={"world_state_ref": bool(world_state_ref)},
                    property_name=f"{function_name.lower()}_world_state_ref",
                )
            )

        if function_name == "GUARDED_ACTUATE":
            report.add(
                self.verify_spec_gate(
                    fields={"evidence_refs": bool(evidence_refs)},
                    property_name="guarded_actuate_evidence_refs",
                )
            )

        return report

    def verify_type(
        self, value: Any, expected_type: str, *, property_name: str = ""
    ) -> VerificationResult:
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

    def verify_spec_gate(
        self,
        fields: dict[str, Any] | None = None,
        *,
        property_name: str = "",
        condition: Any = None,
    ) -> VerificationResult:
        start = time.time()
        effective_fields = dict(fields or {})
        if effective_fields:
            unresolved = [
                name
                for name, value in effective_fields.items()
                if isinstance(value, dict) and "var_ref" in value
            ]
            if unresolved:
                return VerificationResult(
                    property_name=property_name or "spec_gate",
                    status=VerificationStatus.UNKNOWN,
                    kind=ConstraintKind.SPEC_GATE,
                    message=(
                        "SPEC_GATE depends on unresolved variable references: "
                        + ", ".join(sorted(unresolved))
                    ),
                    solver=self.solver_name,
                    duration_ms=(time.time() - start) * 1000,
                )
            false_fields = [
                name for name, value in effective_fields.items() if isinstance(value, bool) and not value
            ]
            if false_fields:
                field_name = false_fields[0]
                return VerificationResult(
                    property_name=property_name or "spec_gate",
                    status=VerificationStatus.COUNTEREXAMPLE,
                    kind=ConstraintKind.SPEC_GATE,
                    message=f"SPEC_GATE literal '{field_name}' resolved to false.",
                    counterexample={
                        "field": field_name,
                        "value": effective_fields[field_name],
                    },
                    solver=self.solver_name,
                    duration_ms=(time.time() - start) * 1000,
                )
            return VerificationResult(
                property_name=property_name or "spec_gate",
                status=VerificationStatus.PROVEN if _HAS_Z3 else VerificationStatus.RUNTIME_CHECKED,
                kind=ConstraintKind.SPEC_GATE,
                message=(
                    "SPEC_GATE resolved to deterministic literal fields: "
                    + ", ".join(sorted(effective_fields))
                ),
                solver=self.solver_name,
                duration_ms=(time.time() - start) * 1000,
            )

        if isinstance(condition, bool):
            _status = (
                (VerificationStatus.PROVEN if _HAS_Z3 else VerificationStatus.RUNTIME_CHECKED)
                if condition
                else VerificationStatus.COUNTEREXAMPLE
            )
            return VerificationResult(
                property_name=property_name or "spec_gate",
                status=_status,
                kind=ConstraintKind.SPEC_GATE,
                message=(
                    "SPEC_GATE condition resolved deterministically."
                    if condition
                    else "SPEC_GATE condition resolved to false."
                ),
                counterexample=None if condition else {"condition": False},
                solver=self.solver_name,
                duration_ms=(time.time() - start) * 1000,
            )

        return VerificationResult(
            property_name=property_name or "spec_gate",
            status=VerificationStatus.SKIPPED,
            kind=ConstraintKind.SPEC_GATE,
            message="SPEC_GATE extraction is present, but no deterministic literal proof contract was available.",
            solver=self.solver_name,
            duration_ms=(time.time() - start) * 1000,
        )

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
                value = constraint.get("value")
                low = _numeric_value(constraint.get("low"))
                high = _numeric_value(constraint.get("high"))
                args = list(constraint.get("args", []))
                if value is None and args and isinstance(args[0], (int, float)):
                    value = args[0]
                    if low is None:
                        low = 0.0
                if isinstance(value, (int, float)):
                    report.add(
                        self.verify_range(
                            value,
                            low=low,
                            high=high,
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
                    self.verify_spec_gate(
                        fields=constraint.get("fields") if isinstance(constraint.get("fields"), dict) else None,
                        property_name=str(constraint.get("name", "spec_gate")),
                        condition=constraint.get("condition"),
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
