"""
HLF Workflow Benchmark — measure end-to-end agent task performance.

Compares the HLF-native pipeline against a conceptual baseline,
measuring token efficiency, quality, scope adherence, thoroughness,
error rates, and time-to-completion.

SELF-IMPROVEMENT TASKS: Each task produces an actual improvement to HLF.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.benchmark import _count
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.corrector import HLFCorrector
from hlf_mcp.hlf.linter import HLFLinter


# ── Task Corpus ────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkTask:
    """A single benchmark task with expected deliverables."""

    task_id: str
    description: str
    domain: str
    expected_tags: list[str]  # Tags the HLF should contain
    expected_concepts: list[str]  # Keywords/concepts that must be preserved
    min_statements: int = 1  # Minimum HLF statements expected
    max_gas: int = 500
    artifact_type: str = "hlf"  # hlf | test | grammar | doc | config
    artifact_path: str = ""  # Where the improvement should be written


_TASK_CORPUS: list[BenchmarkTask] = [
    # ── HLF Self-Improvement Tasks ─────────────────────────────────────────────
    BenchmarkTask(
        task_id="add_tag_spec",
        description="Add a new HLF tag TRACE_REF that captures cryptographic trace references in governance events. "
                    "Define its glyph role, ASCII alias, and opcode. Update TAGS and GLYPHS dictionaries.",
        domain="grammar",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "VOTE", "RESULT"],
        expected_concepts=["tag", "specification", "trace", "cryptographic", "governance"],
        min_statements=5,
        max_gas=200,
        artifact_type="grammar",
        artifact_path="hlf_mcp/hlf/grammar.py",
    ),
    BenchmarkTask(
        task_id="improve_translator",
        description="Refine the language_to_hlf translator to produce EXPECT and VOTE tags when the input describes "
                    "constraints or consensus requirements. Add mapping rules for 'strict', 'read-only', 'verify'.",
        domain="translator",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "VOTE"],
        expected_concepts=["translator", "constraint", "consensus", "strict", "verify"],
        min_statements=4,
        max_gas=200,
        artifact_type="config",
        artifact_path="hlf_mcp/hlf/translator.py",
    ),
    BenchmarkTask(
        task_id="generate_test_cases",
        description="Generate 3 new test cases for edge cases in HLF compilation: missing omega terminator, "
                    "unmatched brackets, and homoglyph confusion. Each test should assert failure + correction.",
        domain="testing",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "RESULT"],
        expected_concepts=["test", "edge", "compilation", "correction", "homoglyph"],
        min_statements=4,
        max_gas=200,
        artifact_type="test",
        artifact_path="tests/test_compiler_edge_cases.py",
    ),
    BenchmarkTask(
        task_id="improve_corrector",
        description="Improve the self-healing parser to detect and repair missing bracket pairs in HLF source. "
                    "Add a new correction category BRACKET_MISMATCH with auto-repair logic.",
        domain="parser",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "RESULT"],
        expected_concepts=["parser", "bracket", "mismatch", "correction", "auto-repair"],
        min_statements=4,
        max_gas=200,
        artifact_type="config",
        artifact_path="hlf_mcp/hlf/corrector.py",
    ),
    BenchmarkTask(
        task_id="optimize_gas_model",
        description="Optimize the gas estimation model by analyzing execution traces from the benchmark suite. "
                    "Add per-tag gas weights and improve the total estimation formula.",
        domain="runtime",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "RESULT"],
        expected_concepts=["gas", "estimate", "optimization", "trace", "weight"],
        min_statements=4,
        max_gas=200,
        artifact_type="config",
        artifact_path="hlf_mcp/hlf/runtime.py",
    ),
    BenchmarkTask(
        task_id="expand_benchmark_corpus",
        description="Expand the workflow benchmark corpus with 2 new domains: 'ethics' and 'memory'. "
                    "Each domain needs a task with expected tags, concepts, and min_statements.",
        domain="benchmark",
        expected_tags=["INTENT", "ASSERT", "EXPECT", "VOTE"],
        expected_concepts=["corpus", "ethics", "memory", "domain", "expand"],
        min_statements=4,
        max_gas=200,
        artifact_type="config",
        artifact_path="hlf_mcp/hlf/workflow_benchmark.py",
    ),
]


# ── Metrics ────────────────────────────────────────────────────────────────────

@dataclass
class WorkflowMetrics:
    """Metrics collected for a single task execution."""

    # Timing
    translation_ns: int = 0
    validation_ns: int = 0
    execution_ns: int = 0
    total_ns: int = 0

    # Tokens
    input_tokens: int = 0  # User intent tokens
    hlf_tokens: int = 0  # Generated HLF tokens
    output_tokens: int = 0  # Response tokens
    total_tokens: int = 0  # Sum of all tokens

    # Quality
    compile_success: bool = False
    lint_errors: int = 0
    auto_repair_attempts: int = 0
    auto_repair_success: bool = False

    # Scope & thoroughness
    tags_found: list[str] = field(default_factory=list)
    tags_missing: list[str] = field(default_factory=list)
    concepts_found: list[str] = field(default_factory=list)
    concepts_missing: list[str] = field(default_factory=list)
    statement_count: int = 0
    scope_score: float = 0.0  # 0-1
    thoroughness_score: float = 0.0  # 0-1

    # Gas
    gas_estimate: int = 0
    gas_limit: int = 0
    gas_efficiency: float = 0.0  # gas_estimate / gas_limit

    # Errors
    compile_error: str = ""
    corrections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timing_ns": {
                "translation": self.translation_ns,
                "validation": self.validation_ns,
                "execution": self.execution_ns,
                "total": self.total_ns,
            },
            "tokens": {
                "input": self.input_tokens,
                "hlf": self.hlf_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens,
            },
            "quality": {
                "compile_success": self.compile_success,
                "lint_errors": self.lint_errors,
                "auto_repair_attempts": self.auto_repair_attempts,
                "auto_repair_success": self.auto_repair_success,
            },
            "scope": {
                "tags_found": self.tags_found,
                "tags_missing": self.tags_missing,
                "concepts_found": self.concepts_found,
                "concepts_missing": self.concepts_missing,
                "statement_count": self.statement_count,
                "scope_score": self.scope_score,
                "thoroughness_score": self.thoroughness_score,
            },
            "gas": {
                "estimate": self.gas_estimate,
                "limit": self.gas_limit,
                "efficiency": self.gas_efficiency,
            },
            "errors": {
                "compile_error": self.compile_error,
                "correction_count": len(self.corrections),
                "corrections": self.corrections[:5],  # Cap for brevity
            },
        }


# ── Workflow Benchmark Engine ──────────────────────────────────────────────────

class WorkflowBenchmark:
    """Measure end-to-end HLF workflow performance against task corpus."""

    def __init__(self) -> None:
        self.compiler = HLFCompiler()
        self.corrector = HLFCorrector()
        self.linter = HLFLinter()

    def run_task(
        self,
        task: BenchmarkTask,
        translator_fn: Any,
        delivery_mode: str = "auto",
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        """Execute a single task through the HLF pipeline and collect metrics.

        Args:
            task: The benchmark task definition
            translator_fn: Callable(text) -> dict with 'source' key containing HLF
            delivery_mode: "strict" | "auto" | "permissive"
            auto_repair: Whether to attempt auto-repair on compilation failures

        Returns:
            Full result dict with metrics, HLF source, and natural language output
        """
        metrics = WorkflowMetrics()
        metrics.gas_limit = task.max_gas

        overall_start = time.perf_counter_ns()

        # ── Phase 1: NLP → HLF (Translation) ─────────────────────────────────
        t0 = time.perf_counter_ns()
        translation = translator_fn(task.description)
        metrics.translation_ns = time.perf_counter_ns() - t0

        hlf_source = translation.get("source", "")
        metrics.input_tokens = _count(task.description)
        metrics.hlf_tokens = _count(hlf_source)

        # ── Phase 2: Compile + Auto-repair ────────────────────────────────────
        compile_result = self.compiler.compile_with_recovery(hlf_source)
        metrics.compile_success = bool(compile_result.get("success"))
        metrics.gas_estimate = int(compile_result.get("gas_estimate", 0))
        metrics.corrections = compile_result.get("corrections", [])

        if not metrics.compile_success and auto_repair:
            metrics.auto_repair_attempts = 1
            repaired = self.corrector.repair(hlf_source)
            if repaired.success:
                metrics.auto_repair_success = True
                hlf_source = repaired.repaired_source
                compile_result = self.compiler.compile_with_recovery(hlf_source)
                metrics.compile_success = bool(compile_result.get("success"))
                metrics.gas_estimate = int(compile_result.get("gas_estimate", 0))
                metrics.corrections = compile_result.get("corrections", [])
            else:
                metrics.compile_error = str(compile_result.get("compile_error", ""))[:200]

        # ── Phase 3: Lint ─────────────────────────────────────────────────────
        t0 = time.perf_counter_ns()
        lint_diagnostics = self.linter.lint(hlf_source, gas_limit=task.max_gas)
        metrics.validation_ns = time.perf_counter_ns() - t0
        metrics.lint_errors = len([d for d in lint_diagnostics if d.get("level") == "error"])

        # ── Phase 4: Scope & Thoroughness Analysis ──────────────────────────
        metrics.tags_found, metrics.tags_missing = self._check_tags(hlf_source, task.expected_tags)
        metrics.concepts_found, metrics.concepts_missing = self._check_concepts(
            hlf_source, task.expected_concepts
        )
        metrics.statement_count = self._count_statements(hlf_source)

        metrics.scope_score = len(metrics.tags_found) / max(len(task.expected_tags), 1)
        metrics.thoroughness_score = (
            (len(metrics.tags_found) / max(len(task.expected_tags), 1)) * 0.5
            + (len(metrics.concepts_found) / max(len(task.expected_concepts), 1)) * 0.3
            + (min(metrics.statement_count, task.min_statements) / max(task.min_statements, 1))
            * 0.2
        )

        if metrics.gas_limit > 0:
            metrics.gas_efficiency = round(metrics.gas_estimate / metrics.gas_limit, 4)

        # ── Phase 5: Translate back (simulated output) ────────────────────────
        t0 = time.perf_counter_ns()
        nl_output = self._hlf_to_nl(hlf_source)
        metrics.output_tokens = _count(nl_output)
        metrics.execution_ns = time.perf_counter_ns() - t0

        metrics.total_ns = time.perf_counter_ns() - overall_start
        metrics.total_tokens = metrics.input_tokens + metrics.hlf_tokens + metrics.output_tokens

        trace_ref = hashlib.sha256(
            f"{task.task_id}:{hlf_source}:{metrics.total_ns}".encode()
        ).hexdigest()[:32]

        return {
            "task_id": task.task_id,
            "domain": task.domain,
            "status": "ok" if metrics.compile_success else "compile_error",
            "metrics": metrics.to_dict(),
            "hlf_source": hlf_source,
            "natural_language": nl_output,
            "trace_ref": trace_ref,
        }

    def run_suite(
        self,
        translator_fn: Any,
        tasks: list[BenchmarkTask] | None = None,
        delivery_mode: str = "auto",
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        """Run the full benchmark suite and produce comparison report."""
        tasks = tasks or _TASK_CORPUS
        results: list[dict[str, Any]] = []

        total_compile_success = 0
        total_repair_success = 0
        total_repair_attempts = 0
        total_tokens = 0
        total_time_ns = 0
        total_scope = 0.0
        total_thoroughness = 0.0
        total_lint_errors = 0

        for task in tasks:
            result = self.run_task(task, translator_fn, delivery_mode, auto_repair)
            results.append(result)

            m = result["metrics"]
            total_compile_success += 1 if m["quality"]["compile_success"] else 0
            total_repair_attempts += m["quality"]["auto_repair_attempts"]
            total_repair_success += 1 if m["quality"]["auto_repair_success"] else 0
            total_tokens += m["tokens"]["total"]
            total_time_ns += m["timing_ns"]["total"]
            total_scope += m["scope"]["scope_score"]
            total_thoroughness += m["scope"]["thoroughness_score"]
            total_lint_errors += m["quality"]["lint_errors"]

        n = len(tasks)
        summary = {
            "tasks_run": n,
            "compile_success_rate": round(total_compile_success / n, 3) if n else 0.0,
            "auto_repair_attempt_rate": round(total_repair_attempts / n, 3) if n else 0.0,
            "auto_repair_success_rate": (
                round(total_repair_success / total_repair_attempts, 3)
                if total_repair_attempts
                else 0.0
            ),
            "avg_total_tokens": round(total_tokens / n, 1) if n else 0.0,
            "avg_time_ms": round(total_time_ns / n / 1_000_000, 2) if n else 0.0,
            "avg_scope_score": round(total_scope / n, 3) if n else 0.0,
            "avg_thoroughness_score": round(total_thoroughness / n, 3) if n else 0.0,
            "total_lint_errors": total_lint_errors,
            "delivery_mode": delivery_mode,
            "auto_repair_enabled": auto_repair,
        }

        return {
            "status": "ok",
            "summary": summary,
            "results": results,
            "trace_ref": hashlib.sha256(
                f"suite:{total_tokens}:{total_time_ns}".encode()
            ).hexdigest()[:32],
        }

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _check_tags(source: str, expected: list[str]) -> tuple[list[str], list[str]]:
        found = [t for t in expected if f"[{t}]" in source or f"[KW_{t}]" in source]
        missing = [t for t in expected if t not in found]
        return found, missing

    @staticmethod
    def _check_concepts(source: str, expected: list[str]) -> tuple[list[str], list[str]]:
        source_lower = source.lower()
        found = [c for c in expected if c.lower() in source_lower]
        missing = [c for c in expected if c not in found]
        return found, missing

    @staticmethod
    def _count_statements(source: str) -> int:
        """Count non-empty, non-comment, non-header, non-terminator lines."""
        count = 0
        for line in source.splitlines():
            stripped = line.strip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("[HLF-v")
                and stripped != "Ω"
            ):
                count += 1
        return count

    @staticmethod
    def _hlf_to_nl(source: str) -> str:
        """Convert HLF source to a simple natural language summary."""
        lines = []
        for raw in source.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[HLF-v"):
                continue
            if line == "Ω":
                continue
            # Simple glyph expansion
            line = (
                line.replace("Δ", "Action:")
                .replace("Ж", "Constraint:")
                .replace("⨝", "Consensus:")
                .replace("⌘", "Command:")
                .replace("∇", "Parameter:")
                .replace("⩕", "Priority:")
                .replace("⊎", "Branch:")
            )
            # Tag expansion
            line = re.sub(
                r"\[([A-Z_]+)\]",
                lambda m: m.group(1).replace("_", " ").title() + ":",
                line,
            )
            lines.append(line.strip())
        return " ".join(lines) if lines else source


# ── Convenience exports ────────────────────────────────────────────────────────

def run_workflow_benchmark(
    translator_fn: Any,
    tasks: list[BenchmarkTask] | None = None,
    delivery_mode: str = "auto",
    auto_repair: bool = True,
) -> dict[str, Any]:
    """Run the full workflow benchmark suite."""
    bench = WorkflowBenchmark()
    return bench.run_suite(translator_fn, tasks, delivery_mode, auto_repair)
