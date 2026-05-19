"""
Equivalence Proof: prove that HLF bytecode execution is equivalent to Python execution.

The proof works by:
1. Compile HLF source to AST
2. Encode AST to bytecode via BytecodeCompiler
3. Execute bytecode in the HLF VM (HlfVM)
4. Execute equivalent Python code
5. Assert outputs match — the VM result must be identical to the Python result

This proves that the HLF bytecode semantics are faithfully implemented by the
stack-machine VM and produce results consistent with Python's own evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.runtime import HLFRuntime


@dataclass
class EquivalenceResult:
    """Result of a single equivalence proof run."""

    source_label: str
    hlf_source: str
    python_code: str
    hlf_result: Any  # VM result (top of stack)
    python_result: Any  # Python eval result
    gas_used: int
    passed: bool
    error: str = ""

    @property
    def output(self) -> dict[str, Any]:
        return {
            "source_label": self.source_label,
            "python_code": self.python_code,
            "hlf_result": self.hlf_result,
            "python_result": self.python_result,
            "gas_used": self.gas_used,
            "passed": self.passed,
            "error": self.error,
        }


class EquivalenceProver:
    """Prove HLF bytecode execution is equivalent to Python execution."""

    def __init__(self, compiler: HLFCompiler | None = None) -> None:
        self.compiler = compiler or HLFCompiler()

    def _execute_hlf(self, source: str, variables: dict[str, Any]) -> tuple[Any, int]:
        """Execute HLF source through compile -> bytecode -> VM pipeline."""
        ast = self.compiler.compile(source)["ast"]
        bytecode = HLFBytecode().encode(ast)
        runtime = HLFRuntime()
        result = runtime.run(bytecode, gas_limit=500, variables=variables)
        top = result["result"]
        gas = result["gas_used"]
        return top, int(gas)

    def _execute_python(self, python_expr: str, variables: dict[str, Any]) -> Any:
        """Evaluate Python expression in a context with the given variables."""
        import math
        safe_builtins = {"abs": abs, "min": min, "max": max, "round": round,
                         "int": int, "float": float, "str": str, "bool": bool,
                         "len": len, "list": list, "dict": dict, "sum": sum,
                         "math": math}
        safe_builtins.update(variables)
        return eval(python_expr, {"__builtins__": safe_builtins}, variables)

    def prove_equivalence(
        self,
        hlf_source: str,
        python_code: str,
        *,
        label: str = "",
        variables: dict[str, Any] | None = None,
    ) -> EquivalenceResult:
        """Prove HLF bytecode execution is equivalent to Python execution."""
        effective_vars = variables or {}
        try:
            hlf_val, gas = self._execute_hlf(hlf_source, effective_vars)
        except Exception as exc:
            return EquivalenceResult(
                source_label=label or "unnamed",
                hlf_source=hlf_source,
                python_code=python_code,
                hlf_result=None,
                python_result=None,
                gas_used=0,
                passed=False,
                error=f"HLF execution error: {exc}",
            )

        try:
            py_val = self._execute_python(python_code, effective_vars)
        except Exception as exc:
            return EquivalenceResult(
                source_label=label or "unnamed",
                hlf_source=hlf_source,
                python_code=python_code,
                hlf_result=hlf_val,
                python_result=None,
                gas_used=gas,
                passed=False,
                error=f"Python execution error: {exc}",
            )

        # Compare with tolerance for floating-point
        same = _values_equal(hlf_val, py_val)
        return EquivalenceResult(
            source_label=label or "unnamed",
            hlf_source=hlf_source,
            python_code=python_code,
            hlf_result=hlf_val,
            python_result=py_val,
            gas_used=gas,
            passed=same,
            error="" if same else f"Output mismatch: HLF={hlf_val!r}, Python={py_val!r}",
        )


def _values_equal(a: Any, b: Any) -> bool:
    """Compare two values with float tolerance."""
    if isinstance(a, float) and isinstance(b, float):
        import math
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-12
    if a is None and b is None:
        return True
    if isinstance(a, bool) and isinstance(b, bool):
        return a == b
    return a == b


def prove_equivalence(
    hlf_source: str,
    python_code: str,
    *,
    label: str = "",
    variables: dict[str, Any] | None = None,
) -> EquivalenceResult:
    """Convenience function for proving HLF-Python execution equivalence."""
    return EquivalenceProver().prove_equivalence(
        hlf_source, python_code, label=label, variables=variables
    )
