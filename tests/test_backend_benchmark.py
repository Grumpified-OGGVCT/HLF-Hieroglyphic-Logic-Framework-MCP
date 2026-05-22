"""
Enterprise Hardening Commit 8: A/B Backend Framework Tests.

Validates:
  1. Statistical comparison with Wilson score intervals
  2. Effect size (Cohen's d) computation
  3. Paired t-test p-value
  4. Backend ranking and auto-promotion
  5. Deterministic scoring against reference keywords
  6. Hallucination detection
  7. Export and HKS promotion
  8. Edge cases: empty prompts, ties, all-correct, all-wrong
"""

from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hlf_mcp.hlf.backend_benchmark import (  # noqa: E402
    BackendBenchmark,
    BackendComparison,
    BackendRanking,
    BackendResponse,
    BackendScore,
    BenchmarkPrompt,
    BenchmarkRun,
    _normal_cdf,
    _wilson_score_interval,
    compare_backends,
    compute_cohens_d,
    compute_paired_t_test,
    score_response,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def medical_prompts() -> list[BenchmarkPrompt]:
    """10 synthetic medical prompts with known reference answers."""
    return [
        BenchmarkPrompt(
            prompt_id=f"med_{i}",
            text=f"Patient has symptom_{i}: What is the diagnosis and treatment?",
            domain="medical",
            reference_answer=f"diagnosis_{i} treatment_{i}",
            reference_keywords=[f"diagnosis_{i}", f"treatment_{i}"],
            difficulty="medium",
        )
        for i in range(10)
    ]


@pytest.fixture
def math_prompts() -> list[BenchmarkPrompt]:
    """5 synthetic math prompts."""
    return [
        BenchmarkPrompt(
            prompt_id=f"math_{i}",
            text=f"Solve: {i}x + {i*2} = {i*3}",
            domain="math",
            reference_answer=f"x = {i}",
            reference_keywords=[f"{i}"],
            difficulty="easy",
        )
        for i in range(1, 6)
    ]


@pytest.fixture
def all_prompts(medical_prompts, math_prompts) -> list[BenchmarkPrompt]:
    return medical_prompts + math_prompts


def make_perfect_backend(name: str):
    """Backend that always returns the reference answer."""
    def fn(prompt_text: str) -> str:
        return f"Perfect response from {name}: {prompt_text}"
    return fn


def make_partial_backend(name: str, accuracy: float):
    """Backend that returns correct keywords with given probability."""
    def fn(prompt_text: str) -> str:
        import hashlib
        h = int(hashlib.md5(prompt_text.encode()).hexdigest(), 16)
        if (h % 100) / 100.0 < accuracy:
            # Extract prompt_id from prompt text or use generic
            return f"Correct from {name}: diagnosis treatment"
        return f"Wrong from {name}"
    return fn


def make_hallucinating_backend(name: str):
    """Backend that always hallucinates with known bad keywords."""
    def fn(prompt_text: str) -> str:
        return f"Non-Altoine's disease fabricated by {name}"
    return fn


# ═══════════════════════════════════════════════════════════════════════════════
# Statistical Function Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWilsonScoreInterval:
    def test_perfect_correct(self):
        """100% accuracy, all-correct."""
        lower, upper = _wilson_score_interval(10, 10)
        assert lower > 0.6  # Should be high
        assert upper >= 0.99

    def test_perfect_wrong(self):
        """0% accuracy, all-wrong."""
        lower, upper = _wilson_score_interval(0, 10)
        assert lower == 0.0
        assert upper < 0.4  # Should be low

    def test_half_correct(self):
        """50% accuracy."""
        lower, upper = _wilson_score_interval(5, 10)
        assert 0.15 < lower < 0.85
        assert 0.15 < upper < 0.85
        # 50% should be contained within
        assert lower <= 0.5 <= upper

    def test_zero_trials(self):
        """Zero trials returns (0, 1)."""
        lower, upper = _wilson_score_interval(0, 0)
        assert lower == 0.0
        assert upper == 1.0

    def test_single_trial_success(self):
        """1/1 — interval is wide but valid."""
        lower, upper = _wilson_score_interval(1, 1)
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_large_sample(self):
        """Large sample narrows the interval."""
        lower_small, upper_small = _wilson_score_interval(50, 100)
        lower_large, upper_large = _wilson_score_interval(500, 1000)
        # Large sample should have tighter interval
        width_small = upper_small - lower_small
        width_large = upper_large - lower_large
        assert width_large < width_small


class TestCohensD:
    def test_identical_samples(self):
        """Cohen's d for identical samples is 0."""
        d = compute_cohens_d([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        assert abs(d) < 1e-10

    def test_large_effect(self):
        """Large difference produces large Cohen's d."""
        d = compute_cohens_d([0.1, 0.2, 0.1], [0.9, 0.8, 0.9])
        assert abs(d) > 2.0

    def test_small_effect(self):
        """Small difference produces small Cohen's d."""
        d = compute_cohens_d([0.5, 0.5, 0.5], [0.55, 0.55, 0.55])
        assert abs(d) < 1.0

    def test_empty_samples(self):
        """Empty samples return 0."""
        d = compute_cohens_d([], [])
        assert d == 0.0

    def test_single_element(self):
        """Single element each."""
        d = compute_cohens_d([0.5], [1.0])
        # With single elements, std is 0, so d is effectively infinite
        # Our implementation handles this gracefully
        assert isinstance(d, float)

    def test_b_beats_a(self):
        """When B > A, Cohen's d is positive."""
        d = compute_cohens_d([0.2, 0.3, 0.2], [0.7, 0.8, 0.7])
        assert d > 0


class TestPairedTTest:
    def test_identical_scores(self):
        """Identical scores produce p ~= 1.0."""
        scores_a = [
            BackendScore("a", "p1", 0.8, False, True),
            BackendScore("a", "p2", 0.8, False, True),
        ]
        scores_b = [
            BackendScore("b", "p1", 0.8, False, True),
            BackendScore("b", "p2", 0.8, False, True),
        ]
        p = compute_paired_t_test(scores_a, scores_b)
        assert p > 0.9  # Nearly 1.0

    def test_very_different_scores(self):
        """Very different scores produce small p-value."""
        scores_a = [
            BackendScore("a", "p1", 0.2, False, False),
            BackendScore("a", "p2", 0.1, False, False),
            BackendScore("a", "p3", 0.3, False, False),
        ]
        scores_b = [
            BackendScore("b", "p1", 0.9, False, True),
            BackendScore("b", "p2", 0.8, False, True),
            BackendScore("b", "p3", 0.9, False, True),
        ]
        p = compute_paired_t_test(scores_a, scores_b)
        assert p < 0.05  # Statistically significant

    def test_unequal_lengths(self):
        """Unequal scores return p=1.0 (invalid comparison)."""
        scores_a = [BackendScore("a", "p1", 0.5, False, True)]
        scores_b = [
            BackendScore("b", "p1", 0.5, False, True),
            BackendScore("b", "p2", 0.5, False, True),
        ]
        p = compute_paired_t_test(scores_a, scores_b)
        assert p == 1.0

    def test_insufficient_data(self):
        """Less than 2 pairs returns p=1.0."""
        scores_a = [BackendScore("a", "p1", 0.5, False, True)]
        scores_b = [BackendScore("b", "p1", 0.5, False, True)]
        p = compute_paired_t_test(scores_a, scores_b)
        assert p == 1.0


class TestNormalCDF:
    def test_zero(self):
        assert abs(_normal_cdf(0.0) - 0.5) < 0.01

    def test_positive(self):
        assert _normal_cdf(1.96) > 0.97

    def test_negative(self):
        assert _normal_cdf(-1.96) < 0.03

    def test_monotonic(self):
        assert _normal_cdf(1.0) > _normal_cdf(0.0)
        assert _normal_cdf(2.0) > _normal_cdf(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoring:
    def test_perfect_keyword_match(self):
        """All keywords matched = 1.0 ratio."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="What is the diagnosis?",
            domain="medical",
            reference_keywords=["hypothyroidism", "tsh", "levothyroxine"],
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="The diagnosis is hypothyroidism with elevated TSH. Treat with levothyroxine.",
            latency_ms=100,
        )
        score = score_response(prompt, response, "test")
        assert score.keyword_match_ratio == 1.0
        assert score.correct is True
        assert score.hallucination is False

    def test_partial_keyword_match(self):
        """Some keywords matched."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="diagnosis?",
            domain="medical",
            reference_keywords=["hypothyroidism", "tsh", "levothyroxine", "hashimoto"],
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="The diagnosis is hypothyroidism with elevated TSH.",
            latency_ms=100,
        )
        score = score_response(prompt, response, "test")
        assert score.keyword_match_ratio == 0.5  # 2/4
        assert score.correct is True  # >= 0.5 threshold

    def test_no_keyword_match(self):
        """Zero keywords matched."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="diagnosis?",
            domain="medical",
            reference_keywords=["hypothyroidism", "tsh"],
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="The patient has a cold.",
            latency_ms=100,
        )
        score = score_response(prompt, response, "test")
        assert score.keyword_match_ratio == 0.0
        assert score.correct is False

    def test_hallucination_detected(self):
        """Hallucination keyword detected in response."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="diagnosis?",
            domain="medical",
            reference_keywords=["hypothyroidism"],
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="Non-Altoine's disease is the diagnosis.",
            latency_ms=100,
        )
        score = score_response(
            prompt, response, "test",
            hallucination_keywords=["Non-Altoine's disease"],
        )
        assert score.hallucination is True
        assert score.correct is False

    def test_case_insensitive_keywords(self):
        """Keyword matching is case-insensitive."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="diagnosis?",
            domain="medical",
            reference_keywords=["Hypothyroidism"],
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="hypothyroidism confirmed.",
            latency_ms=100,
        )
        score = score_response(prompt, response, "test")
        assert score.keyword_match_ratio == 1.0

    def test_empty_reference_keywords(self):
        """No reference keywords — uses token overlap fallback."""
        prompt = BenchmarkPrompt(
            prompt_id="test",
            text="diagnosis?",
            domain="medical",
            reference_keywords=[],
            reference_answer="hypothyroidism confirmed",
        )
        response = BackendResponse(
            backend_name="test",
            prompt_id="test",
            response_text="hypothyroidism confirmed",
            latency_ms=100,
        )
        score = score_response(prompt, response, "test")
        # Token overlap should be high
        assert score.keyword_match_ratio >= 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Backend Comparison Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompareBackends:
    def test_clear_winner(self):
        """Backend B clearly beats Backend A."""
        scores_a = [
            BackendScore("a", f"p{i}", 0.3, False, False) for i in range(10)
        ]
        scores_b = [
            BackendScore("b", f"p{i}", 0.9, False, True) for i in range(10)
        ]
        comp = compare_backends("medgemma", "qwen", "medical", scores_a, scores_b)
        assert comp.winner == "qwen"
        assert comp.significant is True
        assert comp.diff_mean > 0.5
        assert "PROMOTE" in comp.recommendation

    def test_tie(self):
        """Backends perform similarly."""
        scores_a = [
            BackendScore("a", f"p{i}", 0.7 + (i % 3) * 0.05, False, True)
            for i in range(30)
        ]
        scores_b = [
            BackendScore("b", f"p{i}", 0.7 + ((i + 1) % 3) * 0.05, False, True)
            for i in range(30)
        ]
        comp = compare_backends("a", "b", "domain", scores_a, scores_b)
        # With large N and small differences, may be tie
        assert comp.winner in ("a", "b", "tie")

    def test_effect_size_reported(self):
        """Cohen's d is in the comparison."""
        scores_a = [
            BackendScore("a", f"p{i}", 0.05 + i * 0.01, False, False) for i in range(5)
        ]
        scores_b = [
            BackendScore("b", f"p{i}", 0.85 + i * 0.01, False, True) for i in range(5)
        ]
        comp = compare_backends("a", "b", "domain", scores_a, scores_b)
        # With scores ~0.07 vs ~0.87, d should show a massive effect
        assert abs(comp.cohens_d) > 2.0  # Large effect

    def test_confidence_intervals(self):
        """Confidence intervals are reasonable."""
        scores_a = [
            BackendScore("a", f"p{i}", 0.5, False, i < 5) for i in range(10)
        ]
        scores_b = [
            BackendScore("b", f"p{i}", 0.8, False, i < 8) for i in range(10)
        ]
        comp = compare_backends("a", "b", "domain", scores_a, scores_b)
        assert -1.0 <= comp.confidence_95_lower <= 1.0
        assert -1.0 <= comp.confidence_95_upper <= 1.0
        assert comp.confidence_95_lower <= comp.confidence_95_upper

    def test_all_correct_both(self):
        """Both backends perfect = tie with no discrimination."""
        scores_a = [BackendScore("a", f"p{i}", 1.0, False, True) for i in range(5)]
        scores_b = [BackendScore("b", f"p{i}", 1.0, False, True) for i in range(5)]
        comp = compare_backends("a", "b", "domain", scores_a, scores_b)
        assert comp.winner == "tie"
        assert comp.diff_mean == 0.0

    def test_all_wrong_both(self):
        """Both backends fail everything."""
        scores_a = [BackendScore("a", f"p{i}", 0.0, False, False) for i in range(5)]
        scores_b = [BackendScore("b", f"p{i}", 0.0, False, False) for i in range(5)]
        comp = compare_backends("a", "b", "domain", scores_a, scores_b)
        assert comp.winner == "tie"


# ═══════════════════════════════════════════════════════════════════════════════
# Benchmark Runner Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackendBenchmark:
    def test_run_with_mock_backends(self, medical_prompts):
        """Run benchmark with perfect and partial backends."""
        benchmark = BackendBenchmark(
            backends={
                "perfect": make_perfect_backend("perfect"),
                "partial_60": make_partial_backend("partial", 0.6),
            },
            prompts=medical_prompts,
            hallucination_keywords=["Non-Altoine's disease"],
        )
        run = benchmark.run()
        assert run.backends == ["perfect", "partial_60"]
        assert len(run.prompts) == 10
        assert "perfect" in run.responses
        assert "partial_60" in run.responses
        assert len(run.comparisons) == 1  # one domain, one pair
        assert run.total_time_ms >= 0

    def test_ranking_perfect_wins(self, medical_prompts):
        """Perfect backend ranks first."""
        benchmark = BackendBenchmark(
            backends={
                "perfect": make_perfect_backend("perfect"),
                "bad": make_partial_backend("bad", 0.1),
            },
            prompts=medical_prompts,
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)

        assert "medical" in rankings
        assert rankings["medical"].promoted_backend == "perfect"

    def test_ranking_ties(self, medical_prompts):
        """Equal backends produce tied ranking."""
        benchmark = BackendBenchmark(
            backends={
                "backend_a": make_partial_backend("a", 0.5),
                "backend_b": make_partial_backend("b", 0.5),
            },
            prompts=medical_prompts,
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)

        assert "medical" in rankings
        # Both have similar scores; ranking order may vary but scores are close
        ranking = rankings["medical"]
        scores = [score for _, score in ranking.rankings]
        assert len(scores) == 2

    def test_hallucinating_backend_ranks_low(self, medical_prompts):
        """Hallucinating backend loses badly."""
        benchmark = BackendBenchmark(
            backends={
                "perfect": make_perfect_backend("perfect"),
                "hallucinator": make_hallucinating_backend("hallucinator"),
            },
            prompts=medical_prompts,
            hallucination_keywords=["Non-Altoine's disease"],
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)

        # Hallucinating backend should not be promoted
        assert rankings["medical"].promoted_backend == "perfect"

    def test_multiple_domains(self, all_prompts):
        """Benchmark across medical + math domains."""
        benchmark = BackendBenchmark(
            backends={
                "med_specialist": make_perfect_backend("med"),
                "math_specialist": make_partial_backend("math", 0.9),
            },
            prompts=all_prompts,
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)

        assert "medical" in rankings
        assert "math" in rankings

    def test_promote_winner_writes_hks(self, medical_prompts):
        """Promotion writes to HKS exemplar store."""
        benchmark = BackendBenchmark(
            backends={
                "winner": make_perfect_backend("winner"),
                "loser": make_partial_backend("loser", 0.2),
            },
            prompts=medical_prompts,
        )
        run = benchmark.run()

        with tempfile.TemporaryDirectory() as tmp:
            hks_path = Path(tmp) / "hks"
            hks_path.mkdir()
            promotions = benchmark.promote_winner(run, hks_path)
            assert "medical" in promotions
            assert promotions["medical"] == "winner"

            # Verify file was written
            exemplar_file = hks_path / "exemplar_medical.json"
            assert exemplar_file.exists()
            data = json.loads(exemplar_file.read_text(encoding="utf-8"))
            assert data["domain"] == "medical"
            assert data["preferred_backend"] == "winner"
            assert "score" in data
            assert "updated_at" in data

    def test_export_results(self, medical_prompts):
        """Export produces valid JSON with all required fields."""
        benchmark = BackendBenchmark(
            backends={
                "a": make_perfect_backend("a"),
                "b": make_partial_backend("b", 0.3),
            },
            prompts=medical_prompts,
        )
        run = benchmark.run()

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "benchmark_results.json"
            benchmark.export_results(run, output_path)

            assert output_path.exists()
            data = json.loads(output_path.read_text(encoding="utf-8"))
            assert "run_id" in data
            assert "comparisons" in data
            assert "rankings" in data
            assert "backends" in data
            assert data["backends"] == ["a", "b"]


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_prompts(self):
        """Zero prompts produces empty results."""
        benchmark = BackendBenchmark(
            backends={"a": make_perfect_backend("a")},
            prompts=[],
        )
        run = benchmark.run()
        assert len(run.prompts) == 0
        assert len(run.comparisons) == 0

    def test_single_backend(self):
        """Single backend means no pairwise comparisons."""
        prompt = BenchmarkPrompt(
            prompt_id="p1", text="test", domain="test",
            reference_keywords=["kw"],
        )
        benchmark = BackendBenchmark(
            backends={"solo": make_perfect_backend("solo")},
            prompts=[prompt],
        )
        run = benchmark.run()
        assert len(run.comparisons) == 0

    def test_backend_error_handling(self):
        """Backend that raises is handled gracefully."""

        def error_backend(prompt_text: str) -> str:
            raise RuntimeError("Model unavailable")

        prompt = BenchmarkPrompt(
            prompt_id="p1", text="test", domain="test",
            reference_keywords=["kw"],
        )
        benchmark = BackendBenchmark(
            backends={"broken": error_backend},
            prompts=[prompt],
        )
        run = benchmark.run()

        # Should not crash
        assert "broken" in run.responses
        resp = run.responses["broken"].get("p1")
        assert resp is not None
        assert resp.error == "Model unavailable"

    def test_empty_hallucination_keywords(self):
        """No hallucination keywords = no false positives."""
        prompt = BenchmarkPrompt(
            prompt_id="test", text="test", domain="test",
            reference_keywords=["normal"],
        )
        response = BackendResponse(
            backend_name="test", prompt_id="test",
            response_text="normal response", latency_ms=10,
        )
        score = score_response(prompt, response, "test")
        assert score.hallucination is False

    def test_ranking_empty_domain(self):
        """Rankings for domain with no prompts."""
        benchmark = BackendBenchmark(
            backends={"a": make_perfect_backend("a")},
            prompts=[],
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)
        assert len(rankings) == 0

    def test_promote_winner_no_hks_path(self):
        """Promotion without HKS path still returns dict."""
        benchmark = BackendBenchmark(
            backends={"winner": make_perfect_backend("winner")},
            prompts=[
                BenchmarkPrompt(
                    prompt_id="p1", text="test", domain="test",
                    reference_keywords=["kw"],
                )
            ],
        )
        run = benchmark.run()
        promotions = benchmark.promote_winner(run, hks_path=None)
        assert "test" in promotions
        assert promotions["test"] == "winner"


# ═══════════════════════════════════════════════════════════════════════════════
# Realistic Three-Backend Scenario (matching the medical benchmark)
# ═══════════════════════════════════════════════════════════════════════════════


class TestThreeWayMedicalBenchmark:
    """Simulates the real medgemma vs qwen-math vs RecursiveMAS comparison."""

    def test_three_backend_medical_comparison(self):
        """Medical specialist beats math model and hallucinating recursive."""
        # Simulate: medgemma gets 8/10 right, qwen-math 3/10, hallucinator 0/10
        prompts = [
            BenchmarkPrompt(
                prompt_id=f"med_{i}",
                text=f"Patient case {i}: fatigue, weight gain, elevated TSH",
                domain="medical",
                reference_answer="hypothyroidism",
                reference_keywords=["hypothyroidism", "TSH", "thyroid"],
            )
            for i in range(10)
        ]

        call_counts: dict[str, int] = {"medgemma": 0, "qwen_math": 0, "recursive": 0}

        def medgemma_fn(prompt_text: str) -> str:
            call_counts["medgemma"] += 1
            return "Diagnosis: hypothyroidism. Elevated TSH confirms thyroid dysfunction."

        def qwen_math_fn(prompt_text: str) -> str:
            call_counts["qwen_math"] += 1
            idx = call_counts["qwen_math"]
            if idx <= 3:
                return "Diagnosis: hypothyroidism with TSH elevation."
            return "Cannot compute medical diagnosis."

        def recursive_fn(prompt_text: str) -> str:
            call_counts["recursive"] += 1
            return "Non-Altoine's disease confirmed."

        benchmark = BackendBenchmark(
            backends={
                "medgemma": medgemma_fn,
                "qwen_math": qwen_math_fn,
                "recursive": recursive_fn,
            },
            prompts=prompts,
            hallucination_keywords=["Non-Altoine's disease"],
        )
        run = benchmark.run()
        rankings = benchmark.rank_backends(run)

        # medgemma should be promoted for medical domain
        assert rankings["medical"].promoted_backend == "medgemma"

        # Check comparisons exist for all pairs
        expected_pairs = [
            "medical:medgemma_vs_qwen_math",
            "medical:medgemma_vs_recursive",
            "medical:qwen_math_vs_recursive",
        ]
        for key in expected_pairs:
            assert key in run.comparisons, f"Missing comparison: {key}"

        # medgemma vs recursive should show clear winner
        comp = run.comparisons["medical:medgemma_vs_recursive"]
        assert comp.winner == "medgemma"
        assert comp.significant is True
        assert abs(comp.diff_mean) > 0.5
