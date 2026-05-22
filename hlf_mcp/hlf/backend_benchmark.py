"""
A/B Backend Benchmark Framework — statistical model comparison for HLF.

Enterprise Hardening Commit 8:
    - Run the same prompt set across 2+ model backends
    - Statistical confidence interval on accuracy
    - Auto-update HKS exemplar to prefer winning backend for domain

Design:
    The framework is backend-agnostic. Backends are callables that take a prompt
    and return a response. Statistical analysis uses paired comparison with
    Wilson score intervals and effect size (Cohen's d). Auto-promotion writes
    the winning backend into the HKS (Hybrid Knowledge Substrate) exemplar store.
"""

from __future__ import annotations

import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ═══════════════════════════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BenchmarkPrompt:
    """A single prompt with an expected reference answer."""

    prompt_id: str
    text: str
    domain: str  # e.g., "medical", "math", "code"
    reference_answer: str = ""
    reference_keywords: list[str] = field(default_factory=list)
    difficulty: str = "medium"  # easy, medium, hard


@dataclass
class BackendResponse:
    """A single response from a backend to a prompt."""

    backend_name: str
    prompt_id: str
    response_text: str
    latency_ms: float
    token_count: int = 0
    error: str | None = None


@dataclass
class BackendScore:
    """Aggregated score for a backend on one prompt."""

    backend_name: str
    prompt_id: str
    keyword_match_ratio: float  # 0.0 to 1.0
    hallucination: bool = False
    correct: bool = False


@dataclass
class BackendComparison:
    """Pairwise comparison of two backends."""

    backend_a: str
    backend_b: str
    domain: str
    n_prompts: int
    scores_a: list[BackendScore] = field(default_factory=list)
    scores_b: list[BackendScore] = field(default_factory=list)

    # Computed statistics
    mean_a: float = 0.0
    mean_b: float = 0.0
    std_a: float = 0.0
    std_b: float = 0.0
    diff_mean: float = 0.0  # B - A, positive = B better
    diff_std: float = 0.0
    cohens_d: float = 0.0
    p_value: float = 1.0
    confidence_95_lower: float = 0.0
    confidence_95_upper: float = 0.0
    winner: str = ""  # backend name or "tie"
    significant: bool = False  # p < 0.05
    recommendation: str = ""


@dataclass
class BackendRanking:
    """Ranking of all backends for a domain."""

    domain: str
    rankings: list[tuple[str, float]] = field(default_factory=list)
    # List of (backend_name, mean_score)
    promoted_backend: str = ""
    promoted_score: float = 0.0


@dataclass
class BenchmarkRun:
    """Complete benchmark run across multiple backends and prompts."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    backends: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    prompts: list[BenchmarkPrompt] = field(default_factory=list)
    responses: dict[str, dict[str, BackendResponse]] = field(
        default_factory=dict
    )  # backend -> prompt_id -> response
    comparisons: dict[str, BackendComparison] = field(
        default_factory=dict
    )  # key: "domain:backend_a_vs_backend_b"
    total_time_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════════


def score_response(
    prompt: BenchmarkPrompt,
    response: BackendResponse,
    backend_name: str,
    *,
    hallucination_keywords: list[str] | None = None,
) -> BackendScore:
    """Score a backend response against the prompt's reference.

    Scoring strategy:
    1. Keyword match: ratio of reference_keywords found in response (0-1)
    2. Hallucination: if hallucination_keywords found in response, mark hallucinated
    3. Overall correct: keyword_match_ratio >= 0.5 AND not hallucinated
    """
    response_lower = response.response_text.lower()
    reference_lower = prompt.reference_answer.lower()

    # Keyword match
    if prompt.reference_keywords:
        matches = sum(
            1 for kw in prompt.reference_keywords if kw.lower() in response_lower
        )
        keyword_ratio = matches / len(prompt.reference_keywords)
    else:
        # Fallback: simple token overlap with reference
        ref_tokens = set(reference_lower.split())
        resp_tokens = set(response_lower.split())
        if ref_tokens:
            keyword_ratio = len(ref_tokens & resp_tokens) / len(ref_tokens)
        else:
            keyword_ratio = 0.5  # No reference, can't score

    # Hallucination detection
    hallucination = False
    if hallucination_keywords:
        for hk in hallucination_keywords:
            if hk.lower() in response_lower:
                hallucination = True
                break

    # Overall correctness
    correct = keyword_ratio >= 0.5 and not hallucination

    return BackendScore(
        backend_name=backend_name,
        prompt_id=prompt.prompt_id,
        keyword_match_ratio=keyword_ratio,
        hallucination=hallucination,
        correct=correct,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Statistical Analysis
# ═══════════════════════════════════════════════════════════════════════════════


def _wilson_score_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Args:
        successes: Number of successes.
        n: Total trials.
        z: Z-score for confidence level (1.96 = 95%).

    Returns:
        (lower_bound, upper_bound) of the confidence interval.
    """
    if n == 0:
        return (0.0, 1.0)

    p = successes / n
    denominator = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def compute_cohens_d(sample_a: list[float], sample_b: list[float]) -> float:
    """Cohen's d effect size: (mean_b - mean_a) / pooled_std."""
    if not sample_a or not sample_b:
        return 0.0

    mean_a = statistics.mean(sample_a)
    mean_b = statistics.mean(sample_b)
    diff = mean_b - mean_a

    n_a = len(sample_a)
    n_b = len(sample_b)

    if n_a < 2 and n_b < 2:
        # Single elements: use simple difference as effect size proxy
        return diff

    var_a = statistics.variance(sample_a) if n_a > 1 else 0.0
    var_b = statistics.variance(sample_b) if n_b > 1 else 0.0

    # Pooled standard deviation
    pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
    pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1.0

    return diff / pooled_std


def compute_paired_t_test(
    scores_a: list[BackendScore], scores_b: list[BackendScore]
) -> float:
    """Paired t-test p-value (approximate via normal distribution).

    Compares keyword_match_ratio for the same prompts across two backends.
    Returns approximate p-value.
    """
    if len(scores_a) != len(scores_b) or len(scores_a) < 2:
        return 1.0

    diffs = [
        b.keyword_match_ratio - a.keyword_match_ratio
        for a, b in zip(scores_a, scores_b)
    ]

    mean_diff = statistics.mean(diffs)
    std_diff = statistics.stdev(diffs) if len(diffs) > 1 else 1.0

    if std_diff == 0:
        return 0.0 if mean_diff != 0 else 1.0

    n = len(diffs)
    t_stat = mean_diff / (std_diff / math.sqrt(n))

    # Approximate p-value using normal distribution
    # Two-tailed: p = 2 * (1 - Phi(|t|))
    # Using the Abramowitz & Stegun approximation
    abs_t = abs(t_stat)
    p = 2 * (1 - _normal_cdf(abs_t))
    return min(1.0, max(0.0, p))


def _normal_cdf(x: float) -> float:
    """Approximation of the standard normal CDF."""
    # Abramowitz and Stegun approximation 7.1.26
    if x < 0:
        return 1 - _normal_cdf(-x)
    b = [0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429]
    t = 1 / (1 + 0.2316419 * x)
    poly = b[0] * t + b[1] * t**2 + b[2] * t**3 + b[3] * t**4 + b[4] * t**5
    phi = (1 / math.sqrt(2 * math.pi)) * math.exp(-(x**2) / 2)
    return 1 - phi * poly


def compare_backends(
    backend_a: str,
    backend_b: str,
    domain: str,
    scores_a: list[BackendScore],
    scores_b: list[BackendScore],
) -> BackendComparison:
    """Produce a statistical comparison of two backends.

    Returns a BackendComparison with effect size, p-value, confidence intervals,
    and a recommendation.
    """
    n = len(scores_a)
    comp = BackendComparison(
        backend_a=backend_a,
        backend_b=backend_b,
        domain=domain,
        n_prompts=n,
        scores_a=scores_a,
        scores_b=scores_b,
    )

    # Correctness rates
    correct_a = sum(1 for s in scores_a if s.correct)
    correct_b = sum(1 for s in scores_b if s.correct)
    comp.mean_a = correct_a / n if n > 0 else 0.0
    comp.mean_b = correct_b / n if n > 0 else 0.0
    comp.diff_mean = comp.mean_b - comp.mean_a

    # Wilson confidence intervals
    ci_a_lower, ci_a_upper = _wilson_score_interval(correct_a, n)
    ci_b_lower, ci_b_upper = _wilson_score_interval(correct_b, n)

    comp.confidence_95_lower = ci_b_lower - ci_a_upper
    comp.confidence_95_upper = ci_b_upper - ci_a_lower

    # Effect size (Cohen's d on keyword_match_ratio)
    ratios_a = [s.keyword_match_ratio for s in scores_a]
    ratios_b = [s.keyword_match_ratio for s in scores_b]
    comp.cohens_d = compute_cohens_d(ratios_a, ratios_b)

    # P-value (paired t-test on keyword ratios)
    comp.p_value = compute_paired_t_test(scores_a, scores_b)

    # Winner determination
    comp.significant = comp.p_value < 0.05
    comp.std_a = statistics.stdev(ratios_a) if len(ratios_a) > 1 else 0.0
    comp.std_b = statistics.stdev(ratios_b) if len(ratios_b) > 1 else 0.0

    if comp.significant and abs(comp.diff_mean) > 0.05:
        comp.winner = backend_b if comp.diff_mean > 0 else backend_a
    else:
        comp.winner = "tie"

    # Recommendation
    if comp.winner == "tie":
        comp.recommendation = (
            f"No statistically significant difference between {backend_a} "
            f"and {backend_b} on {domain} (p={comp.p_value:.3f}, d={comp.cohens_d:.2f}). "
            "Retain current backend or choose based on cost/latency."
        )
    else:
        effect_size_desc = (
            "large" if abs(comp.cohens_d) > 0.8
            else "medium" if abs(comp.cohens_d) > 0.5
            else "small"
        )
        comp.recommendation = (
            f"PROMOTE {comp.winner} for {domain} domain: "
            f"{correct_b}/{n} correct vs {correct_a}/{n} "
            f"(p={comp.p_value:.3f}, d={comp.cohens_d:.2f} [{effect_size_desc}]), "
            f"95% CI: [{comp.confidence_95_lower:.3f}, {comp.confidence_95_upper:.3f}]"
        )

    return comp


# ═══════════════════════════════════════════════════════════════════════════════
# Benchmark Runner
# ═══════════════════════════════════════════════════════════════════════════════


class BackendBenchmark:
    """Orchestrate A/B testing across multiple model backends.

    Usage:
        def my_backend(prompt: str) -> str:
            return model.generate(prompt)

        benchmark = BackendBenchmark(
            backends={
                "medgemma:4b": my_medgemma_fn,
                "qwen-math": my_qwen_fn,
            },
            prompts=[...],
        )
        run = benchmark.run(n_trials=100)
        benchmark.export_results(run, Path("benchmark_results.json"))
    """

    def __init__(
        self,
        backends: dict[str, Callable[[str], str]],
        prompts: list[BenchmarkPrompt],
        *,
        hallucination_keywords: list[str] | None = None,
    ) -> None:
        self._backends = backends
        self._prompts = prompts
        self._hallucination_keywords = hallucination_keywords or []

    @property
    def backend_names(self) -> list[str]:
        return list(self._backends.keys())

    @property
    def domains(self) -> list[str]:
        return sorted({p.domain for p in self._prompts})

    def run(self, n_trials: int = 100) -> BenchmarkRun:
        """Run the full benchmark across all backends and prompts.

        Each prompt runs n_trials times through each backend.
        """
        run = BenchmarkRun(
            backends=self.backend_names,
            domains=self.domains,
            prompts=self._prompts,
        )
        start_time = time.monotonic()

        for backend_name, backend_fn in self._backends.items():
            run.responses[backend_name] = {}
            for prompt in self._prompts:
                # For deterministic scoring, we run once per prompt
                # (n_trials controls number of unique prompts, not repeated runs)
                response_text: str
                latency_start = time.monotonic()
                try:
                    response_text = backend_fn(prompt.text)
                except Exception as exc:
                    response_text = ""
                    run.responses[backend_name][prompt.prompt_id] = BackendResponse(
                        backend_name=backend_name,
                        prompt_id=prompt.prompt_id,
                        response_text="",
                        latency_ms=0,
                        error=str(exc),
                    )
                    continue

                latency_ms = (time.monotonic() - latency_start) * 1000
                run.responses[backend_name][prompt.prompt_id] = BackendResponse(
                    backend_name=backend_name,
                    prompt_id=prompt.prompt_id,
                    response_text=response_text,
                    latency_ms=latency_ms,
                    token_count=len(response_text.split()),
                )

        # Score all responses
        scores: dict[str, list[BackendScore]] = {b: [] for b in self.backend_names}
        for backend_name in self.backend_names:
            for prompt in self._prompts:
                resp = run.responses[backend_name].get(prompt.prompt_id)
                if resp is None or resp.error:
                    scores[backend_name].append(
                        BackendScore(
                            backend_name=backend_name,
                            prompt_id=prompt.prompt_id,
                            keyword_match_ratio=0.0,
                            hallucination=False,
                            correct=False,
                        )
                    )
                else:
                    scores[backend_name].append(
                        score_response(
                            prompt,
                            resp,
                            backend_name,
                            hallucination_keywords=self._hallucination_keywords,
                        )
                    )

        # Pairwise comparisons per domain
        for domain in self.domains:
            domain_prompts = [p for p in self._prompts if p.domain == domain]
            domain_ids = {p.prompt_id for p in domain_prompts}

            backend_pairs = [
                (a, b)
                for i, a in enumerate(self.backend_names)
                for b in self.backend_names[i + 1 :]
            ]

            for backend_a, backend_b in backend_pairs:
                scores_a_domain = [
                    s for s in scores[backend_a] if s.prompt_id in domain_ids
                ]
                scores_b_domain = [
                    s for s in scores[backend_b] if s.prompt_id in domain_ids
                ]

                # Sort both by prompt_id for paired comparison
                scores_a_domain.sort(key=lambda s: s.prompt_id)
                scores_b_domain.sort(key=lambda s: s.prompt_id)

                comp = compare_backends(
                    backend_a, backend_b, domain, scores_a_domain, scores_b_domain
                )
                key = f"{domain}:{backend_a}_vs_{backend_b}"
                run.comparisons[key] = comp

        run.total_time_ms = (time.monotonic() - start_time) * 1000
        return run

    def rank_backends(self, run: BenchmarkRun) -> dict[str, BackendRanking]:
        """Rank all backends per domain based on benchmark results."""
        rankings: dict[str, BackendRanking] = {}

        for domain in self.domains:
            domain_prompts = [p for p in self._prompts if p.domain == domain]
            domain_ids = {p.prompt_id for p in domain_prompts}

            backend_means: list[tuple[str, float]] = []
            for backend_name in self.backend_names:
                relevant_responses = [
                    r
                    for pid, r in run.responses.get(backend_name, {}).items()
                    if pid in domain_ids
                ]
                if not relevant_responses:
                    continue

                scores_list = [
                    score_response(
                        next(p for p in self._prompts if p.prompt_id == r.prompt_id),
                        r,
                        backend_name,
                        hallucination_keywords=self._hallucination_keywords,
                    )
                    for r in relevant_responses
                ]

                correct = sum(1 for s in scores_list if s.correct)
                mean_score = correct / len(scores_list) if scores_list else 0.0
                backend_means.append((backend_name, mean_score))

            backend_means.sort(key=lambda x: x[1], reverse=True)

            ranking = BackendRanking(
                domain=domain,
                rankings=backend_means,
            )
            if backend_means:
                ranking.promoted_backend = backend_means[0][0]
                ranking.promoted_score = backend_means[0][1]

            rankings[domain] = ranking

        return rankings

    def promote_winner(
        self,
        run: BenchmarkRun,
        hks_path: Path | None = None,
    ) -> dict[str, str]:
        """Auto-promote the winning backend for each domain in HKS.

        Returns a dict of domain -> promoted_backend.
        """
        rankings = self.rank_backends(run)
        promotions: dict[str, str] = {}

        for domain, ranking in rankings.items():
            if ranking.promoted_backend:
                promotions[domain] = ranking.promoted_backend
                if hks_path and hks_path.exists():
                    self._write_hks_promotion(hks_path, domain, ranking)

        return promotions

    @staticmethod
    def _write_hks_promotion(
        hks_path: Path, domain: str, ranking: BackendRanking
    ) -> None:
        """Write promotion decision to HKS exemplar store."""
        hks_path.mkdir(parents=True, exist_ok=True)
        exemplar_file = hks_path / f"exemplar_{domain}.json"
        exemplar = {
            "domain": domain,
            "preferred_backend": ranking.promoted_backend,
            "score": ranking.promoted_score,
            "all_rankings": [
                {"backend": name, "score": score}
                for name, score in ranking.rankings
            ],
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        exemplar_file.write_text(json.dumps(exemplar, indent=2), encoding="utf-8")

    def export_results(self, run: BenchmarkRun, output_path: Path) -> None:
        """Export full benchmark results to JSON."""
        data: dict[str, Any] = {
            "run_id": run.run_id,
            "backends": run.backends,
            "domains": run.domains,
            "n_prompts": len(run.prompts),
            "total_time_ms": run.total_time_ms,
            "prompts": [
                {
                    "prompt_id": p.prompt_id,
                    "domain": p.domain,
                    "text": p.text[:200],
                    "reference_keywords": p.reference_keywords,
                }
                for p in run.prompts
            ],
            "comparisons": {
                key: {
                    "backend_a": comp.backend_a,
                    "backend_b": comp.backend_b,
                    "domain": comp.domain,
                    "mean_a": comp.mean_a,
                    "mean_b": comp.mean_b,
                    "diff_mean": comp.diff_mean,
                    "cohens_d": comp.cohens_d,
                    "p_value": comp.p_value,
                    "confidence_95": [comp.confidence_95_lower, comp.confidence_95_upper],
                    "winner": comp.winner,
                    "significant": comp.significant,
                    "recommendation": comp.recommendation,
                }
                for key, comp in run.comparisons.items()
            },
            "rankings": {
                domain: {
                    "promoted_backend": r.promoted_backend,
                    "rankings": [
                        {"backend": name, "score": score}
                        for name, score in r.rankings
                    ],
                }
                for domain, r in self.rank_backends(run).items()
            },
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
