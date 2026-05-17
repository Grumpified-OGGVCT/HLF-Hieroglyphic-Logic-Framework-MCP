"""
Cross-Agent Consistency Benchmark — verify HLF behaves identically across agents.

Runs the same task through different agent configurations and measures:
1. Output consistency (same HLF structure)
2. Pillar compliance variance
3. Token efficiency variance
4. Semantic equivalence (intent preservation)
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from hlf_mcp.hlf.pillar_auditor import PillarComplianceAuditor, PillarAudit
from hlf_mcp.hlf.swarm_orchestrator import SwarmOrchestrator
from hlf_mcp.hlf.workflow_benchmark import BenchmarkTask, WorkflowBenchmark


@dataclass
class AgentConfig:
    """Configuration for a single agent in the benchmark."""

    agent_id: str
    name: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    translator_hints: list[str] = field(default_factory=list)


@dataclass
class ConsistencyRun:
    """Result of running a task through one agent configuration."""

    run_id: str
    agent_id: str
    task_id: str
    hlf_source: str
    tokens: int
    time_ms: float
    compile_success: bool
    pillar_audit: PillarAudit
    scope_score: float
    thoroughness_score: float


@dataclass
class ConsistencyResult:
    """Aggregated consistency results across agent configurations."""

    benchmark_id: str
    task_id: str
    runs: list[ConsistencyRun]

    # Consistency metrics
    hlf_hash_variance: float = 0.0  # 0 = identical, 1 = completely different
    pillar_score_variance: float = 0.0
    token_variance: float = 0.0
    time_variance: float = 0.0
    scope_variance: float = 0.0
    thoroughness_variance: float = 0.0
    compile_success_rate: float = 0.0
    overall_consistency: float = 0.0  # 1.0 = perfectly consistent

    # Semantic equivalence
    intent_preserved: bool = False
    concept_coverage_variance: float = 0.0


class CrossAgentBenchmark:
    """Benchmark HLF consistency across different agent configurations."""

    def __init__(self) -> None:
        self.auditor = PillarComplianceAuditor()
        self.bench = WorkflowBenchmark()

    def run(
        self,
        task: BenchmarkTask,
        agent_configs: list[AgentConfig],
        translator_fn: Callable[[str], dict[str, Any]],
    ) -> ConsistencyResult:
        """Run a task through multiple agent configs and measure consistency."""
        benchmark_id = hashlib.sha256(
            f"xab:{task.task_id}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        runs: list[ConsistencyRun] = []
        for cfg in agent_configs:
            run_id = f"{benchmark_id}-{cfg.agent_id}"
            start = time.perf_counter_ns()

            # Run the task
            trans = translator_fn(task.description)
            hlf = trans.get("source", "")
            elapsed = (time.perf_counter_ns() - start) / 1_000_000

            # Audit pillars
            audit = self.auditor.audit(hlf, audit_id=run_id)

            # Compute scope/thoroughness using WorkflowBenchmark helpers
            from hlf_mcp.hlf.workflow_benchmark import WorkflowBenchmark
            tags_found, _ = WorkflowBenchmark._check_tags(hlf, task.expected_tags)
            concepts_found, _ = WorkflowBenchmark._check_concepts(hlf, task.expected_concepts)
            stmt_count = WorkflowBenchmark._count_statements(hlf)
            scope = len(tags_found) / max(len(task.expected_tags), 1)
            thoroughness = (
                (len(tags_found) / max(len(task.expected_tags), 1)) * 0.5
                + (len(concepts_found) / max(len(task.expected_concepts), 1)) * 0.3
                + (min(stmt_count, task.min_statements) / max(task.min_statements, 1)) * 0.2
            )

            # Quick compile check
            from hlf_mcp.hlf.compiler import HLFCompiler
            try:
                compile_result = HLFCompiler().compile(hlf)
                compile_ok = True
            except Exception:
                compile_ok = False

            runs.append(
                ConsistencyRun(
                    run_id=run_id,
                    agent_id=cfg.agent_id,
                    task_id=task.task_id,
                    hlf_source=hlf,
                    tokens=len(hlf.split()),
                    time_ms=elapsed,
                    compile_success=compile_ok,
                    pillar_audit=audit,
                    scope_score=scope,
                    thoroughness_score=thoroughness,
                )
            )

        # Compute consistency metrics
        result = ConsistencyResult(benchmark_id=benchmark_id, task_id=task.task_id, runs=runs)
        result.hlf_hash_variance = self._compute_hlf_variance(runs)
        result.pillar_score_variance = self._compute_variance([r.pillar_audit.overall_score for r in runs])
        result.token_variance = self._compute_variance([r.tokens for r in runs])
        result.time_variance = self._compute_variance([r.time_ms for r in runs])
        result.scope_variance = self._compute_variance([r.scope_score for r in runs])
        result.thoroughness_variance = self._compute_variance([r.thoroughness_score for r in runs])
        result.compile_success_rate = sum(1 for r in runs if r.compile_success) / max(len(runs), 1)

        # Overall consistency: inverse of average normalized variance
        variances = [
            result.pillar_score_variance,
            result.token_variance / max(max(r.tokens for r in runs), 1),
            result.scope_variance,
            result.thoroughness_variance,
        ]
        avg_var = statistics.mean(variances) if variances else 0.0
        result.overall_consistency = max(0.0, 1.0 - avg_var)

        # Intent preservation: all runs should have INTENT
        result.intent_preserved = all(r.pillar_audit.has_intent for r in runs)

        # Concept coverage variance
        concept_scores = []
        for r in runs:
            _, concepts_found = WorkflowBenchmark._check_concepts(r.hlf_source, task.expected_concepts)
            concept_scores.append(len(concepts_found) / max(len(task.expected_concepts), 1))
        result.concept_coverage_variance = self._compute_variance(concept_scores)

        return result

    def run_suite(
        self,
        tasks: list[BenchmarkTask],
        agent_configs: list[AgentConfig],
        translator_fn: Callable[[str], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run consistency benchmark across a task suite."""
        results = [self.run(t, agent_configs, translator_fn) for t in tasks]
        return {
            "task_count": len(tasks),
            "agent_count": len(agent_configs),
            "avg_consistency": round(statistics.mean([r.overall_consistency for r in results]), 3),
            "min_consistency": round(min([r.overall_consistency for r in results]), 3),
            "max_consistency": round(max([r.overall_consistency for r in results]), 3),
            "avg_compile_success": round(statistics.mean([r.compile_success_rate for r in results]), 3),
            "intent_preserved_rate": round(sum(1 for r in results if r.intent_preserved) / max(len(results), 1), 3),
            "results": results,
        }

    @staticmethod
    def _compute_variance(values: list[float]) -> float:
        """Compute normalized variance (0 = identical, higher = more different)."""
        if len(values) < 2:
            return 0.0
        mean_val = statistics.mean(values)
        if mean_val == 0:
            return 0.0
        var = statistics.variance(values)
        return var / (mean_val ** 2) if mean_val != 0 else 0.0

    @staticmethod
    def _compute_hlf_variance(runs: list[ConsistencyRun]) -> float:
        """Compute structural variance between HLF outputs."""
        if len(runs) < 2:
            return 0.0
        hashes = [hashlib.sha256(r.hlf_source.encode()).hexdigest() for r in runs]
        unique = len(set(hashes))
        return (unique - 1) / max(len(runs) - 1, 1)
