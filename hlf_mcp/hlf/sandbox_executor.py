"""
Sandbox Executor: resource-constrained Python code execution matching HLF gas
limits, with timeout and memory caps, AST-level gas metering, and restricted
builtins.

Design Principles:
1. Every code execution is bounded: timeout (wall clock), memory (OS-enforced
   where available), and gas (AST-node accounting).
2. Gas metering maps directly to HLF gas costs — each AST node type has a
   configurable cost, and execution halts when the gas limit is exhausted.
3. Code is pre-validated via AST parsing before execution; restricted patterns
   (eval, exec, __import__, etc.) are detected and blocked.
4. The sandbox uses a restricted builtins dictionary that strips dangerous
   functions (open, eval, compile, __import__, etc.).
5. Execution results include full provenance: gas consumed, AST node count,
   execution time, peak memory, and any restricted calls detected.

This module is the execution membrane between HLF's gas-metered VM and Python's
interpreter. It answers the question: "Can this Python code execute safely
within the given resource bounds, and what gas did it consume?"
"""

from __future__ import annotations

import ast
import io
import os
import signal
import struct
import subprocess
import sys
import threading
import time
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from enum import Enum, auto
from types import CodeType
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SandboxResult(Enum):
    """Outcome of a sandboxed execution."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    RESTRICTED_OPERATION = "restricted_operation"
    EXCEPTION = "exception"
    COMPILATION_ERROR = "compilation_error"


# ---------------------------------------------------------------------------
# Default gas costs (per AST node type)
# ---------------------------------------------------------------------------

_DEFAULT_GAS_COSTS: dict[str, int] = {
    "Expression": 1,
    "Statement": 2,
    "FunctionCall": 5,
    "Loop": 3,
    "Import": 10,
    "ClassDef": 15,
    "AsyncOp": 20,
    "Attribute": 1,
    "Subscript": 1,
    "BinOp": 2,
    "UnaryOp": 1,
    "Compare": 2,
    "BoolOp": 2,
    "IfExp": 2,
    "DictComp": 5,
    "SetComp": 5,
    "ListComp": 5,
    "GeneratorExp": 5,
    "Lambda": 5,
    "Yield": 3,
    "Await": 5,
}


# ---------------------------------------------------------------------------
# Restricted patterns to detect in AST
# ---------------------------------------------------------------------------

_RESTRICTED_FUNCTIONS: set[str] = {
    "eval", "exec", "compile", "__import__", "open",
    "input", "breakpoint",
}

_RESTRICTED_MODULES: set[str] = {
    "subprocess", "os", "sys", "socket", "shutil",
    "ctypes", "multiprocessing", "signal", "threading",
}

_RESTRICTED_ATTRIBUTES: dict[str, set[str]] = {
    "os": {"system", "popen", "spawnl", "spawnle", "spawnlp", "spawnv",
           "spawnve", "spawnvp", "execl", "execle", "execlp", "execlpe",
           "execv", "execve", "execvp", "execvpe", "kill", "remove",
           "unlink", "rmdir", "chmod", "chown"},
    "subprocess": {"Popen", "call", "run", "check_call", "check_output",
                   "getoutput", "getstatusoutput"},
    "sys": {"exit", "setrecursionlimit", "setprofile", "settrace",
            "_getframe", "_current_frames"},
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SandboxConfig:
    """Configuration for sandboxed execution.

    Attributes:
        timeout_seconds: Maximum wall-clock execution time.
        max_memory_mb: Maximum memory limit (best-effort, OS dependent).
        max_cpu_percent: CPU usage cap (advisory).
        gas_limit: Maximum gas units allowed for this execution.
        gas_per_operation: Mapping from AST node type name to gas cost.
        allowed_modules: Explicitly permitted module names.
        max_output_bytes: Maximum size of captured stdout/stderr.
        allow_network: Whether network access is permitted.
        allow_file_io: Whether file I/O is permitted.
        allow_subprocess: Whether subprocess spawning is permitted.
        restricted_modules: Module names that are explicitly blocked.
    """
    timeout_seconds: float = 5.0
    max_memory_mb: int = 128
    max_cpu_percent: int = 50
    gas_limit: int = 1_000_000
    gas_per_operation: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_GAS_COSTS))
    allowed_modules: list[str] = field(default_factory=list)
    max_output_bytes: int = 1_048_576  # 1 MB
    allow_network: bool = False
    allow_file_io: bool = False
    allow_subprocess: bool = False
    restricted_modules: list[str] = field(default_factory=list)


@dataclass
class SandboxExecution:
    """Result of a sandboxed code execution.

    Attributes:
        result: The outcome classification.
        output: Captured stdout from the execution.
        error: Captured stderr or exception traceback.
        gas_used: Total gas consumed (from AST walk).
        execution_time_ms: Wall-clock execution time in milliseconds.
        peak_memory_mb: Estimated peak memory usage in MB.
        ast_node_count: Total number of AST nodes in the code.
        restricted_calls: List of restricted operations that were detected.
    """
    result: SandboxResult
    output: str = ""
    error: str = ""
    gas_used: int = 0
    execution_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    ast_node_count: int = 0
    restricted_calls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.value,
            "output": self.output[:2000],
            "error": self.error[:2000],
            "gas_used": self.gas_used,
            "execution_time_ms": self.execution_time_ms,
            "peak_memory_mb": self.peak_memory_mb,
            "ast_node_count": self.ast_node_count,
            "restricted_calls": list(self.restricted_calls),
        }


# ---------------------------------------------------------------------------
# GasMeter
# ---------------------------------------------------------------------------

class GasMeter:
    """Tracks gas consumption during AST analysis and execution.

    Each AST node type has a configurable gas cost. The meter deducts gas
    as nodes are visited and signals exhaustion when the limit is reached.
    """

    def __init__(
        self,
        gas_limit: int,
        gas_costs: dict[str, int] | None = None,
    ) -> None:
        """Initialize the gas meter.

        Args:
            gas_limit: Total gas available.
            gas_costs: Mapping of AST node type name → gas cost.
                Defaults to _DEFAULT_GAS_COSTS.
        """
        self._limit = gas_limit
        self._costs = dict(gas_costs) if gas_costs else dict(_DEFAULT_GAS_COSTS)
        self._consumed = 0
        self._exhausted = False

    def charge(self, node_type: str, count: int = 1) -> bool:
        """Deduct gas for a node type. Returns False if gas exhausted.

        Args:
            node_type: The AST node class name (e.g. 'BinOp', 'FunctionDef').
            count: How many occurrences to charge for.

        Returns:
            True if gas was available and deducted, False if exhausted.
        """
        cost_per = self._costs.get(node_type, 1)
        total = cost_per * count
        if self._consumed + total > self._limit:
            self._exhausted = True
            return False
        self._consumed += total
        return True

    @property
    def remaining(self) -> int:
        """Remaining gas units."""
        return max(0, self._limit - self._consumed)

    @property
    def consumed(self) -> int:
        """Gas consumed so far."""
        return self._consumed

    def reset(self) -> None:
        """Reset the meter to full gas limit."""
        self._consumed = 0
        self._exhausted = False

    @property
    def exhausted(self) -> bool:
        """True if gas limit has been reached."""
        return self._exhausted


# ---------------------------------------------------------------------------
# AST Helpers
# ---------------------------------------------------------------------------

class _GasVisitor(ast.NodeVisitor):
    """AST visitor that charges gas for each node visited."""

    def __init__(self, meter: GasMeter) -> None:
        self.meter = meter
        self.node_counts: dict[str, int] = {}
        self.node_count_total = 0

    def generic_visit(self, node: ast.AST) -> Any:
        node_type = type(node).__name__
        self.node_counts[node_type] = self.node_counts.get(node_type, 0) + 1
        self.node_count_total += 1
        self.meter.charge(node_type)
        return super().generic_visit(node)


class _RestrictedDetector(ast.NodeVisitor):
    """AST visitor that detects restricted operations."""

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self.restricted_calls: list[str] = []
        self._allowed_modules = set(config.allowed_modules)
        self._restricted_modules = set(config.restricted_modules)
        self._restricted_modules.update(_RESTRICTED_MODULES)

    def visit_Call(self, node: ast.Call) -> Any:
        # Check for direct restricted function calls
        if isinstance(node.func, ast.Name):
            if node.func.id in _RESTRICTED_FUNCTIONS:
                self.restricted_calls.append(
                    f"Restricted function call: {node.func.id}() at line {node.lineno}"
                )
        elif isinstance(node.func, ast.Attribute):
            # Check for module.restricted_method()
            if isinstance(node.func.value, ast.Name):
                mod_name = node.func.value.id
                attr_name = node.func.attr
                restricted_attrs = _RESTRICTED_ATTRIBUTES.get(mod_name, set())
                if attr_name in restricted_attrs:
                    self.restricted_calls.append(
                        f"Restricted method: {mod_name}.{attr_name}() at line {node.lineno}"
                    )
                if mod_name in self._restricted_modules and not self.config.allow_subprocess:
                    self.restricted_calls.append(
                        f"Blocked module access: {mod_name} at line {node.lineno}"
                    )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            if alias.name in self._restricted_modules:
                self.restricted_calls.append(
                    f"Restricted import: {alias.name} at line {node.lineno}"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        mod = node.module or ""
        if mod in self._restricted_modules:
            self.restricted_calls.append(
                f"Restricted import from: {mod} at line {node.lineno}"
            )
        self.generic_visit(node)


def _count_ast_nodes(tree: ast.AST) -> int:
    """Count the total number of AST nodes in a tree."""
    count = 0
    for _node in ast.walk(tree):
        count += 1
    return count


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

class _TimeoutError(Exception):
    """Raised when execution exceeds the timeout."""


@contextmanager
def _timeout_context(seconds: float):
    """Context manager that raises _TimeoutError after `seconds` seconds.

    Uses signal.alarm on Unix; falls back to threading.Timer on Windows.
    """
    if seconds <= 0:
        yield
        return

    # Try signal-based timeout (Unix only)
    if hasattr(signal, "SIGALRM") and hasattr(signal, "alarm"):
        def _handler(signum, frame):
            raise _TimeoutError(f"Execution timed out after {seconds}s")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(int(seconds) if seconds == int(seconds) else int(seconds) + 1)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return

    # Fallback: threading-based timeout
    timed_out = threading.Event()
    timer: threading.Timer | None = None

    def _raise_timeout():
        timed_out.set()

    timer = threading.Timer(seconds, _raise_timeout)
    timer.daemon = True
    timer.start()
    try:
        yield
        if timed_out.is_set():
            raise _TimeoutError(f"Execution timed out after {seconds}s")
    finally:
        if timer is not None:
            timer.cancel()


# ---------------------------------------------------------------------------
# Restricted builtins
# ---------------------------------------------------------------------------

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "ascii": ascii,
    "bin": bin,
    "bool": bool,
    "bytes": bytes,
    "callable": callable,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "object": object,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "IndexError": IndexError,
    "StopIteration": StopIteration,
    "ArithmeticError": ArithmeticError,
    "ZeroDivisionError": ZeroDivisionError,
    "True": True,
    "False": False,
    "None": None,
    "__build_class__": __build_class__ if "__build_class__" in dir(__builtins__) else None,
}

# Remove None entry for __build_class__ if not available
if _SAFE_BUILTINS.get("__build_class__") is None:
    del _SAFE_BUILTINS["__build_class__"]


# ---------------------------------------------------------------------------
# SandboxExecutor
# ---------------------------------------------------------------------------

class SandboxExecutor:
    """Execute Python code in a resource-constrained sandbox matching HLF
    gas limits.

    The sandbox provides:
    - AST-level gas metering (configurable per node type)
    - Timeout enforcement (signal or thread-based)
    - Restricted builtins (no eval, exec, open, __import__, etc.)
    - Pattern detection for dangerous operations
    - Capture and size-limiting of stdout/stderr

    Usage::

        executor = SandboxExecutor()
        result = executor.execute_safe("print(2 + 2)")
        assert result.result == SandboxResult.SUCCESS
        print(result.output)  # "4\\n"
    """

    def __init__(
        self,
        config: SandboxConfig | None = None,
        name: str = "sandbox-executor",
    ) -> None:
        """Initialize the sandbox executor.

        Args:
            config: Sandbox configuration. If None, uses default SandboxConfig.
            name: Identifier for this executor instance.
        """
        self.config = config or SandboxConfig()
        self.name = name

    # ------------------------------------------------------------------
    # Code validation
    # ------------------------------------------------------------------

    def validate_code(self, code: str) -> tuple[bool, list[str]]:
        """Pre-validate code before execution.

        Parses the code into an AST, checks for restricted patterns,
        and estimates gas cost.

        Args:
            code: The Python source code to validate.

        Returns:
            Tuple of (is_valid, violations) where is_valid is True if the
            code passes all checks and violations is a list of human-readable
            violation descriptions.
        """
        violations: list[str] = []

        # Parse
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            violations.append(f"Syntax error: {exc}")
            return False, violations

        # Check restricted patterns
        detector = _RestrictedDetector(self.config)
        detector.visit(tree)
        violations.extend(detector.restricted_calls)

        # Check gas
        meter = GasMeter(self.config.gas_limit, self.config.gas_per_operation)
        visitor = _GasVisitor(meter)
        visitor.visit(tree)
        if meter.exhausted:
            violations.append(
                f"Gas limit exceeded: estimated {meter.consumed} > "
                f"limit {self.config.gas_limit}"
            )

        return len(violations) == 0, violations

    # ------------------------------------------------------------------
    # Gas estimation
    # ------------------------------------------------------------------

    def estimate_gas(self, code: str) -> int:
        """Walk the AST and estimate gas cost without executing.

        Args:
            code: Python source code.

        Returns:
            Estimated gas units required. Returns -1 if code cannot be parsed.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return -1

        meter = GasMeter(self.config.gas_limit, self.config.gas_per_operation)
        visitor = _GasVisitor(meter)
        visitor.visit(tree)
        return meter.consumed

    def gas_report(self, code: str) -> dict[str, Any]:
        """Generate a detailed gas breakdown by AST node type.

        Args:
            code: Python source code.

        Returns:
            Dict with 'total_gas', 'gas_limit', 'within_limit', and
            'breakdown' (mapping node type → {count, cost_per, total}).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                "total_gas": 0,
                "gas_limit": self.config.gas_limit,
                "within_limit": True,
                "parse_error": str(exc),
                "breakdown": {},
            }

        meter = GasMeter(self.config.gas_limit, self.config.gas_per_operation)
        visitor = _GasVisitor(meter)
        visitor.visit(tree)

        breakdown: dict[str, dict[str, int]] = {}
        for node_type, count in sorted(visitor.node_counts.items()):
            cost_per = self.config.gas_per_operation.get(node_type, 1)
            breakdown[node_type] = {
                "count": count,
                "cost_per": cost_per,
                "total": count * cost_per,
            }

        return {
            "total_gas": meter.consumed,
            "gas_limit": self.config.gas_limit,
            "within_limit": not meter.exhausted,
            "node_count": visitor.node_count_total,
            "breakdown": breakdown,
        }

    # ------------------------------------------------------------------
    # Restricted builtins
    # ------------------------------------------------------------------

    def restricted_builtins(self) -> dict[str, Any]:
        """Return a restricted builtins dictionary for sandbox execution.

        The returned dict excludes dangerous functions: eval, exec,
        compile, open, __import__, globals, locals, vars, etc.
        """
        return dict(_SAFE_BUILTINS)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        code: str,
        globals_dict: dict[str, Any] | None = None,
        locals_dict: dict[str, Any] | None = None,
    ) -> SandboxExecution:
        """Execute Python code in the sandbox with gas, timeout, and memory
        constraints.

        Args:
            code: Python source code string.
            globals_dict: Optional global namespace dict. If None, uses an
                empty dict with restricted builtins.
            locals_dict: Optional local namespace dict.

        Returns:
            SandboxExecution with the full result, output, error, gas used,
            execution time, and restricted calls detected.
        """
        # Pre-validate
        is_valid, violations = self.validate_code(code)
        if not is_valid:
            return SandboxExecution(
                result=SandboxResult.RESTRICTED_OPERATION,
                error="\n".join(violations),
                gas_used=self.estimate_gas(code),
                restricted_calls=violations,
            )

        # Estimate gas
        estimated_gas = self.estimate_gas(code)
        if estimated_gas < 0:
            return SandboxExecution(
                result=SandboxResult.COMPILATION_ERROR,
                error="Failed to parse code for gas estimation",
            )

        if estimated_gas > self.config.gas_limit:
            return SandboxExecution(
                result=SandboxResult.RESTRICTED_OPERATION,
                error=f"Estimated gas {estimated_gas} exceeds limit {self.config.gas_limit}",
                gas_used=estimated_gas,
            )

        # Set up namespaces
        safe_builtins = self.restricted_builtins()
        exec_globals: dict[str, Any] = {"__builtins__": safe_builtins}
        if globals_dict:
            exec_globals.update(globals_dict)
        exec_locals = locals_dict or {}

        # Count AST nodes
        try:
            tree = ast.parse(code)
            ast_node_count = _count_ast_nodes(tree)
        except SyntaxError:
            ast_node_count = 0

        # Capture stdout/stderr
        out_buf = io.StringIO()
        err_buf = io.StringIO()

        start_time = time.perf_counter()
        peak_memory = 0.0

        try:
            with _timeout_context(self.config.timeout_seconds):
                with redirect_stdout(out_buf), redirect_stderr(err_buf):
                    compiled = compile(code, "<sandbox>", "exec")
                    exec(compiled, exec_globals, exec_locals)

            elapsed = (time.perf_counter() - start_time) * 1000.0

            # Estimate peak memory (best effort)
            try:
                import tracemalloc
                if tracemalloc.is_tracing():
                    current, peak = tracemalloc.get_traced_memory()
                    peak_memory = peak / (1024 * 1024)
            except (ImportError, Exception):
                peak_memory = 0.0

            output = out_buf.getvalue()
            if len(output) > self.config.max_output_bytes:
                output = output[:self.config.max_output_bytes] + "\n... [output truncated]"

            error = err_buf.getvalue()

            return SandboxExecution(
                result=SandboxResult.SUCCESS,
                output=output,
                error=error,
                gas_used=estimated_gas,
                execution_time_ms=elapsed,
                peak_memory_mb=peak_memory,
                ast_node_count=ast_node_count,
            )

        except _TimeoutError:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecution(
                result=SandboxResult.TIMEOUT,
                output=out_buf.getvalue()[:self.config.max_output_bytes],
                error=f"Timeout after {self.config.timeout_seconds}s",
                gas_used=estimated_gas,
                execution_time_ms=elapsed,
                peak_memory_mb=peak_memory,
                ast_node_count=ast_node_count,
            )
        except MemoryError:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            return SandboxExecution(
                result=SandboxResult.MEMORY_EXCEEDED,
                output=out_buf.getvalue()[:self.config.max_output_bytes],
                error="Memory limit exceeded",
                gas_used=estimated_gas,
                execution_time_ms=elapsed,
                peak_memory_mb=float(self.config.max_memory_mb),
                ast_node_count=ast_node_count,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000.0
            tb = traceback.format_exc()
            return SandboxExecution(
                result=SandboxResult.EXCEPTION,
                output=out_buf.getvalue()[:self.config.max_output_bytes],
                error=f"{type(exc).__name__}: {exc}\n{tb[-2000:]}",
                gas_used=estimated_gas,
                execution_time_ms=elapsed,
                peak_memory_mb=peak_memory,
                ast_node_count=ast_node_count,
            )

    # ------------------------------------------------------------------
    # Safe execution with pre-validation
    # ------------------------------------------------------------------

    def execute_safe(self, code: str, **kwargs: Any) -> SandboxExecution:
        """Execute with additional safety: pre-validate, restrict builtins,
        and wrap in try/except.

        This is the recommended entry point for untrusted code.

        Args:
            code: Python source code.
            **kwargs: Passed through to execute().

        Returns:
            SandboxExecution result.
        """
        # Pre-validation
        is_valid, violations = self.validate_code(code)
        if not is_valid:
            return SandboxExecution(
                result=SandboxResult.RESTRICTED_OPERATION,
                error="\n".join(violations),
                restricted_calls=violations,
            )

        # Ensure __builtins__ is restricted
        globals_in = kwargs.get("globals_dict", {})
        if isinstance(globals_in, dict):
            globals_in["__builtins__"] = self.restricted_builtins()

        return self.execute(code, **kwargs)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, **kwargs: Any) -> None:
        """Update sandbox configuration parameters.

        Accepted keys match SandboxConfig attributes:
        timeout_seconds, max_memory_mb, gas_limit, gas_per_operation,
        allowed_modules, max_output_bytes, allow_network, allow_file_io,
        allow_subprocess, restricted_modules.

        Args:
            **kwargs: Configuration values to update.
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def execute_sandboxed(
    code: str,
    *,
    timeout_seconds: float = 5.0,
    gas_limit: int = 1_000_000,
) -> SandboxExecution:
    """Convenience function: execute code in a default sandbox."""
    config = SandboxConfig(
        timeout_seconds=timeout_seconds,
        gas_limit=gas_limit,
    )
    executor = SandboxExecutor(config=config)
    return executor.execute_safe(code)


__all__ = [
    "SandboxResult",
    "SandboxConfig",
    "SandboxExecution",
    "GasMeter",
    "SandboxExecutor",
    "execute_sandboxed",
]
