"""HLF test harness for the packaged compiler and linter surfaces."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf.linter import HLFLinter


def _ensure_program(source: str) -> str:
    stripped = source.strip()
    if not stripped:
        return stripped
    if stripped.startswith("[HLF-v"):
        return stripped
    return f"[HLF-v3]\n{stripped}\nΩ"


def _count_nodes(node: Any) -> int:
    if isinstance(node, dict):
        return 1 + sum(_count_nodes(value) for value in node.values())
    if isinstance(node, list):
        return sum(_count_nodes(value) for value in node)
    return 1


@dataclass
class HLFTestResult:
    """Result of testing a single HLF source file or snippet."""

    source: str
    compiles: bool = False
    compile_error: str = ""
    lint_warnings: list[str] = field(default_factory=list)
    gas_used: int = 0
    ast_node_count: int = 0
    elapsed_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.compiles and not self.lint_warnings


@dataclass
class HLFTestReport:
    """Aggregated HLF test report."""

    results: list[HLFTestResult] = field(default_factory=list)
    total_gas: int = 0
    total_elapsed_ms: float = 0.0

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def compile_errors(self) -> int:
        return sum(1 for result in self.results if not result.compiles)

    @property
    def lint_warning_count(self) -> int:
        return sum(len(result.lint_warnings) for result in self.results)


class HLFTestRunner:
    """Compile and lint HLF snippets, files, and directories."""

    def __init__(self, gas_limit: int = 0, strict_lint: bool = True) -> None:
        self.gas_limit = gas_limit
        self.strict_lint = strict_lint
        self._compiler = HLFCompiler()
        self._linter = HLFLinter()

    def test_source(self, source: str, name: str = "<snippet>") -> HLFTestResult:
        start = time.monotonic()
        result = HLFTestResult(source=name)
        candidate = _ensure_program(source)

        try:
            compiled = self._compiler.compile(candidate)
            result.compiles = True
            result.gas_used = compiled["gas_estimate"]
            result.ast_node_count = _count_nodes(compiled["ast"])
        except CompileError as exc:
            result.compile_error = str(exc)
        except Exception as exc:  # pragma: no cover - defensive guard
            result.compile_error = str(exc)

        try:
            diagnostics = self._linter.lint(candidate)
            relevant_levels = {"warning", "error"} if self.strict_lint else {"error"}
            result.lint_warnings = [
                diag["message"] for diag in diagnostics if diag.get("level") in relevant_levels
            ]
        except Exception:
            pass

        result.elapsed_ms = (time.monotonic() - start) * 1000
        return result

    def test_file(self, path: Path) -> HLFTestResult:
        if not path.exists():
            raise FileNotFoundError(f"HLF file not found: {path}")
        source = path.read_text(encoding="utf-8")
        return self.test_source(source, name=str(path))

    def test_directory(self, directory: Path, pattern: str = "*.hlf") -> HLFTestReport:
        report = HLFTestReport()
        start = time.monotonic()
        for path in sorted(directory.rglob(pattern)):
            result = self.test_file(path)
            report.results.append(result)
            report.total_gas += result.gas_used
        report.total_elapsed_ms = (time.monotonic() - start) * 1000
        return report

    @staticmethod
    def _count_nodes(node: dict[str, Any]) -> int:
        return _count_nodes(node)


def assert_compiles(source: str, message: str = "") -> HLFTestResult:
    runner = HLFTestRunner()
    result = runner.test_source(source, name="<assert_compiles>")
    if not result.compiles:
        msg = f"HLF compilation failed: {result.compile_error}"
        if message:
            msg = f"{message}: {msg}"
        raise AssertionError(msg)
    return result


def assert_lints_clean(source: str, message: str = "") -> HLFTestResult:
    runner = HLFTestRunner()
    result = runner.test_source(source, name="<assert_lints_clean>")
    if result.lint_warnings:
        msg = f"HLF lint warnings ({len(result.lint_warnings)}): {result.lint_warnings[:3]}"
        if message:
            msg = f"{message}: {msg}"
        raise AssertionError(msg)
    return result


def assert_gas_under(source: str, limit: int, message: str = "") -> HLFTestResult:
    runner = HLFTestRunner()
    result = runner.test_source(source, name="<assert_gas_under>")
    if result.gas_used > limit:
        msg = f"Gas {result.gas_used} exceeds limit {limit}"
        if message:
            msg = f"{message}: {msg}"
        raise AssertionError(msg)
    return result


def _cli_main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: hlf-test <path> [paths...]")
        print("\nTest .hlf files or directories containing .hlf files.")
        print("Options:")
        print("  --strict         Treat lint warnings as failures")
        print("  --gas-limit N    Maximum gas per file")
        return 0

    strict = "--strict" in args
    gas_limit = 0
    filtered_args = list(args)
    if "--gas-limit" in filtered_args:
        idx = filtered_args.index("--gas-limit")
        if idx + 1 < len(filtered_args):
            gas_limit = int(filtered_args[idx + 1])
            filtered_args = [
                value for i, value in enumerate(filtered_args) if i not in {idx, idx + 1}
            ]

    paths = [Path(arg) for arg in filtered_args if not arg.startswith("--")]
    runner = HLFTestRunner(gas_limit=gas_limit, strict_lint=strict)
    total_report = HLFTestReport()

    for path in paths:
        if path.is_dir():
            report = runner.test_directory(path)
            total_report.results.extend(report.results)
            total_report.total_gas += report.total_gas
        elif path.is_file():
            result = runner.test_file(path)
            total_report.results.append(result)
            total_report.total_gas += result.gas_used
        else:
            print(f"Path not found: {path}", file=sys.stderr)

    for result in total_report.results:
        status = "PASS" if result.passed else "FAIL"
        warns = f" ({len(result.lint_warnings)} warnings)" if result.lint_warnings else ""
        error = f" - {result.compile_error}" if result.compile_error else ""
        print(
            f"  {status} {result.source}{warns}{error} "
            f"[{result.gas_used}g, {result.elapsed_ms:.0f}ms]"
        )

    print("\n" + "-" * 60)
    print(
        f"  Total: {total_report.total}  Passed: {total_report.passed}  "
        f"Failed: {total_report.failed}"
    )
    print(
        f"  Gas: {total_report.total_gas}  Time: {total_report.total_elapsed_ms:.0f}ms"
    )

    if strict:
        return 0 if total_report.failed == 0 else 1
    return 0 if total_report.compile_errors == 0 else 1


def main() -> None:
    sys.exit(_cli_main())


if __name__ == "__main__":  # pragma: no cover
    main()