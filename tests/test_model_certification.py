"""
Tests for the dynamic model certification pipeline.

Coverage:
- ModelCertificationResult: fields, is_fluent(), to_dict(), from_dict()
- CertificationReport: aggregation, fluent_models(), best_model(), summary(), to_dict(), from_dict()
- ModelCertificationRunner: dynamic discovery (mock), run_certification (mock), certify_model (mock)
- CLI argument parsing and model filtering
- Round-trip serialization
- Graceful error handling
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from hlf_mcp.hlf.model_certification import (
    CertificationReport,
    ModelCertificationResult,
    ModelCertificationRunner,
    _STANDARD_PROMPTS,
    _resolve_model_list,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_result() -> ModelCertificationResult:
    """A representative certification result for a fluent model."""
    return ModelCertificationResult(
        model_name="deepseek-v4-pro:cloud",
        prompts_tested=6,
        compile_successes=6,
        compile_success_rate=1.0,
        avg_latency_s=2.3,
        avg_prompt_tokens=120,
        avg_completion_tokens=340,
        per_prompt_results=[
            {
                "prompt_label": "SET",
                "prompt_text": "Create an HLF program...",
                "hlf_output": "[HLF-v3]\n...\nΩ",
                "extracted": True,
                "compile_success": True,
                "compile_error": "",
                "latency_s": 2.1,
                "prompt_tokens": 30,
                "completion_tokens": 80,
            },
            {
                "prompt_label": "IF/THEN",
                "prompt_text": "Write HLF that...",
                "hlf_output": "[HLF-v3]\n...\nΩ",
                "extracted": True,
                "compile_success": True,
                "compile_error": "",
                "latency_s": 2.5,
                "prompt_tokens": 35,
                "completion_tokens": 95,
            },
        ],
        errors=[],
    )


@pytest.fixture
def failing_result() -> ModelCertificationResult:
    """A certification result for a model that fails most prompts."""
    return ModelCertificationResult(
        model_name="tinyllama:latest",
        prompts_tested=6,
        compile_successes=1,
        compile_success_rate=1 / 6,
        avg_latency_s=0.5,
        avg_prompt_tokens=50,
        avg_completion_tokens=60,
        per_prompt_results=[],
        errors=["[SET] CompileError: Unexpected token", "[IF/THEN] CompileError: syntax error"],
    )


@pytest.fixture
def empty_report() -> CertificationReport:
    """An empty certification report."""
    return CertificationReport(
        models_tested=0,
        total_prompts_per_model=6,
        results=[],
        rankings=[],
    )


@pytest.fixture
def populated_report(sample_result, failing_result) -> CertificationReport:
    """A report with two models — one fluent, one failing."""
    return CertificationReport(
        models_tested=2,
        total_prompts_per_model=6,
        results=[sample_result, failing_result],
        rankings=[
            {
                "model_name": "deepseek-v4-pro:cloud",
                "compile_success_rate": 1.0,
                "avg_latency_s": 2.3,
                "is_fluent": True,
                "compile_successes": 6,
                "prompts_tested": 6,
            },
            {
                "model_name": "tinyllama:latest",
                "compile_success_rate": 1 / 6,
                "avg_latency_s": 0.5,
                "is_fluent": False,
                "compile_successes": 1,
                "prompts_tested": 6,
            },
        ],
    )


# ── ModelCertificationResult tests ─────────────────────────────────────────────


class TestModelCertificationResult:
    """Tests for the per-model certification result dataclass."""

    def test_fields_after_init(self):
        result = ModelCertificationResult(
            model_name="test-model",
            prompts_tested=6,
            compile_successes=4,
            compile_success_rate=4 / 6,
            avg_latency_s=1.2,
            avg_prompt_tokens=80,
            avg_completion_tokens=150,
            per_prompt_results=[],
            errors=["some error"],
        )
        assert result.model_name == "test-model"
        assert result.prompts_tested == 6
        assert result.compile_successes == 4
        assert result.compile_success_rate == pytest.approx(4 / 6)
        assert result.avg_latency_s == 1.2
        assert result.avg_prompt_tokens == 80
        assert result.avg_completion_tokens == 150
        assert result.errors == ["some error"]

    def test_is_fluent_at_boundary(self):
        # Exactly 80% — fluent
        result = ModelCertificationResult(
            model_name="boundary",
            prompts_tested=5,
            compile_successes=4,
            compile_success_rate=0.8,
            avg_latency_s=1.0,
            avg_prompt_tokens=50,
            avg_completion_tokens=50,
        )
        assert result.is_fluent() is True

    def test_is_fluent_above_boundary(self):
        result = ModelCertificationResult(
            model_name="solid",
            prompts_tested=6,
            compile_successes=5,
            compile_success_rate=5 / 6,
            avg_latency_s=1.0,
            avg_prompt_tokens=50,
            avg_completion_tokens=50,
        )
        assert result.is_fluent() is True  # ~83.3%

    def test_is_fluent_below_boundary(self):
        result = ModelCertificationResult(
            model_name="weak",
            prompts_tested=6,
            compile_successes=4,
            compile_success_rate=4 / 6,
            avg_latency_s=1.0,
            avg_prompt_tokens=50,
            avg_completion_tokens=50,
        )
        assert result.is_fluent() is False  # ~66.7%

    def test_is_fluent_zero_success(self, failing_result):
        assert failing_result.is_fluent() is False

    def test_is_fluent_perfect(self, sample_result):
        assert sample_result.is_fluent() is True

    def test_to_dict_contains_all_keys(self, sample_result):
        d = sample_result.to_dict()
        expected_keys = {
            "model_name", "prompts_tested", "compile_successes",
            "compile_success_rate", "avg_latency_s", "avg_prompt_tokens",
            "avg_completion_tokens", "per_prompt_results", "errors", "is_fluent",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_per_prompt_preserved(self, sample_result):
        d = sample_result.to_dict()
        assert len(d["per_prompt_results"]) == 2
        assert d["per_prompt_results"][0]["prompt_label"] == "SET"

    def test_from_dict_roundtrip(self, sample_result):
        d = sample_result.to_dict()
        restored = ModelCertificationResult.from_dict(d)
        assert restored.model_name == sample_result.model_name
        assert restored.prompts_tested == sample_result.prompts_tested
        assert restored.compile_successes == sample_result.compile_successes
        assert restored.compile_success_rate == sample_result.compile_success_rate
        assert restored.avg_latency_s == sample_result.avg_latency_s
        assert restored.is_fluent() == sample_result.is_fluent()

    def test_to_dict_json_serializable(self, sample_result):
        json_str = json.dumps(sample_result.to_dict())
        parsed = json.loads(json_str)
        assert parsed["model_name"] == "deepseek-v4-pro:cloud"

    def test_from_dict_with_missing_optionals(self):
        data = {
            "model_name": "minimal",
            "prompts_tested": 3,
            "compile_successes": 0,
            "compile_success_rate": 0.0,
            "avg_latency_s": 0.0,
            "avg_prompt_tokens": 0,
            "avg_completion_tokens": 0,
        }
        result = ModelCertificationResult.from_dict(data)
        assert result.per_prompt_results == []
        assert result.errors == []


# ── CertificationReport tests ──────────────────────────────────────────────────


class TestCertificationReport:
    """Tests for the aggregate certification report dataclass."""

    def test_empty_report_properties(self, empty_report):
        assert empty_report.models_tested == 0
        assert empty_report.fluent_models() == []
        assert empty_report.best_model() == ""
        assert empty_report.total_prompts_per_model == 6

    def test_fluent_models_filtering(self, populated_report):
        fluent = populated_report.fluent_models()
        assert len(fluent) == 1
        assert "deepseek-v4-pro:cloud" in fluent
        assert "tinyllama:latest" not in fluent

    def test_fluent_models_none(self, empty_report):
        assert empty_report.fluent_models() == []

    def test_best_model(self, populated_report):
        assert populated_report.best_model() == "deepseek-v4-pro:cloud"

    def test_best_model_empty(self, empty_report):
        assert empty_report.best_model() == ""

    def test_summary_contains_key_info(self, populated_report):
        s = populated_report.summary()
        assert "HLF MODEL CERTIFICATION REPORT" in s
        assert "deepseek-v4-pro:cloud" in s
        assert "tinyllama:latest" in s
        assert "FLUENT" in s
        assert "FAIL" in s
        assert "Fluent models (>=80%)" in s

    def test_summary_empty(self, empty_report):
        s = empty_report.summary()
        assert "NONE" in s
        assert "Models tested:       0" in s

    def test_to_dict_structure(self, populated_report):
        d = populated_report.to_dict()
        assert d["models_tested"] == 2
        assert d["total_prompts_per_model"] == 6
        assert len(d["results"]) == 2
        assert len(d["rankings"]) == 2
        assert "timestamp" in d
        assert d["fluent_models"] == ["deepseek-v4-pro:cloud"]
        assert d["best_model"] == "deepseek-v4-pro:cloud"

    def test_to_dict_json_serializable(self, populated_report):
        json_str = json.dumps(populated_report.to_dict())
        parsed = json.loads(json_str)
        assert parsed["models_tested"] == 2

    def test_from_dict_roundtrip(self, populated_report):
        d = populated_report.to_dict()
        restored = CertificationReport.from_dict(d)
        assert restored.models_tested == populated_report.models_tested
        assert restored.total_prompts_per_model == populated_report.total_prompts_per_model
        assert restored.fluent_models() == populated_report.fluent_models()
        assert restored.best_model() == populated_report.best_model()
        assert len(restored.results) == len(populated_report.results)

    def test_rankings_are_sorted_by_success_rate(self):
        """Verify rankings sort: best success first, ties broken by latency."""
        r1 = ModelCertificationResult(
            model_name="model_a", prompts_tested=6, compile_successes=3,
            compile_success_rate=0.5, avg_latency_s=1.0,
            avg_prompt_tokens=50, avg_completion_tokens=50,
        )
        r2 = ModelCertificationResult(
            model_name="model_b", prompts_tested=6, compile_successes=6,
            compile_success_rate=1.0, avg_latency_s=2.0,
            avg_prompt_tokens=50, avg_completion_tokens=50,
        )
        r3 = ModelCertificationResult(
            model_name="model_c", prompts_tested=6, compile_successes=6,
            compile_success_rate=1.0, avg_latency_s=1.5,
            avg_prompt_tokens=50, avg_completion_tokens=50,
        )
        rankings = sorted(
            [
                {
                    "model_name": r.model_name,
                    "compile_success_rate": r.compile_success_rate,
                    "avg_latency_s": r.avg_latency_s,
                    "is_fluent": r.is_fluent(),
                    "compile_successes": r.compile_successes,
                    "prompts_tested": r.prompts_tested,
                }
                for r in [r1, r2, r3]
            ],
            key=lambda x: (-x["compile_success_rate"], x["avg_latency_s"]),
        )
        # model_c (1.0, 1.5s) should come before model_b (1.0, 2.0s)
        assert rankings[0]["model_name"] == "model_c"
        assert rankings[1]["model_name"] == "model_b"
        assert rankings[2]["model_name"] == "model_a"


# ── _resolve_model_list tests ─────────────────────────────────────────────────


class TestResolveModelList:
    """Tests for CLI/env model list resolution."""

    def test_cli_arg_takes_priority(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list("kimi-k2.5:cloud,deepseek-v4-pro:cloud")
        assert result == ["kimi-k2.5:cloud", "deepseek-v4-pro:cloud"]

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("HLF_CERTIFY_MODELS", "devstral-2:123b-cloud,nemotron-3-super:cloud")
        result = _resolve_model_list(None)
        assert result == ["devstral-2:123b-cloud", "nemotron-3-super:cloud"]

    def test_no_filter_returns_none(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list(None)
        assert result is None

    def test_empty_string_returns_none(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list("")
        assert result is None

    def test_whitespace_only_returns_none(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list("   ,  ")
        assert result is None

    def test_trailing_comma_ignored(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list("model-a,")
        assert result == ["model-a"]

    def test_leading_comma_ignored(self, monkeypatch):
        monkeypatch.delenv("HLF_CERTIFY_MODELS", raising=False)
        result = _resolve_model_list(",model-b")
        assert result == ["model-b"]


# ── ModelCertificationRunner tests (mock-based, no live Ollama) ──────────────


class TestModelCertificationRunner:
    """Tests for the certification runner with mocked Ollama API and LLM bridge."""

    @pytest.fixture
    def mock_ollama_tags_response(self):
        """Simulate a successful /api/tags response."""
        return {
            "models": [
                {"name": "kimi-k2.5:cloud"},
                {"name": "deepseek-v4-pro:cloud"},
                {"name": "tinyllama:latest"},
                {"name": "devstral-2:123b-cloud"},
            ]
        }

    @pytest.fixture
    def runner(self):
        return ModelCertificationRunner(ollama_url="http://localhost:11434", timeout=30)

    # ── discover_models ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_discover_models_returns_names(self, runner, mock_ollama_tags_response):
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_ollama_tags_response)
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_resp

            models = await runner.discover_models()
            assert models == [
                "deepseek-v4-pro:cloud",
                "devstral-2:123b-cloud",
                "kimi-k2.5:cloud",
                "tinyllama:latest",
            ]

    @pytest.mark.asyncio
    async def test_discover_models_empty(self, runner):
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"models": []})
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_resp

            models = await runner.discover_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_discover_models_http_error(self, runner):
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_resp = AsyncMock()
            mock_resp.status = 500
            mock_resp.text = AsyncMock(return_value="Internal Server Error")
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_resp

            models = await runner.discover_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_discover_models_connection_error(self, runner):
        import aiohttp

        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = aiohttp.ClientError("Connection refused")

            models = await runner.discover_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_discover_models_timeout(self, runner):
        with patch("aiohttp.ClientSession.get") as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()

            models = await runner.discover_models()
            assert models == []

    # ── run_certification with mock certify_model ──────────────────────────

    @pytest.mark.asyncio
    async def test_run_certification_with_filters(self, runner):
        """Only specified models are tested, not all discovered."""
        mock_result = ModelCertificationResult(
            model_name="kimi-k2.5:cloud",
            prompts_tested=3,
            compile_successes=3,
            compile_success_rate=1.0,
            avg_latency_s=1.0,
            avg_prompt_tokens=50,
            avg_completion_tokens=50,
        )
        with patch.object(runner, "certify_model", AsyncMock(return_value=mock_result)):
            report = await runner.run_certification(
                models=["kimi-k2.5:cloud"], prompt_count=3,
            )
            assert report.models_tested == 1
            assert report.total_prompts_per_model == 3
            assert len(report.results) == 1
            assert report.results[0].model_name == "kimi-k2.5:cloud"
            assert report.best_model() == "kimi-k2.5:cloud"

    @pytest.mark.asyncio
    async def test_run_certification_discovers_when_none(self, runner, mock_ollama_tags_response):
        """When models=None, discover from Ollama."""
        mock_result = ModelCertificationResult(
            model_name="deepseek-v4-pro:cloud",
            prompts_tested=6,
            compile_successes=6,
            compile_success_rate=1.0,
            avg_latency_s=1.0,
            avg_prompt_tokens=50,
            avg_completion_tokens=50,
        )

        with patch.object(runner, "discover_models", AsyncMock(
            return_value=["kimi-k2.5:cloud", "deepseek-v4-pro:cloud"]
        )):
            with patch.object(runner, "certify_model", AsyncMock(return_value=mock_result)):
                report = await runner.run_certification(models=None)
                assert report.models_tested == 2
                assert report.total_prompts_per_model == 6  # default is 6

    @pytest.mark.asyncio
    async def test_run_certification_no_models(self, runner):
        """Empty model list returns empty report."""
        report = await runner.run_certification(models=[], prompt_count=3)
        assert report.models_tested == 0
        assert len(report.results) == 0
        assert len(report.rankings) == 0

    @pytest.mark.asyncio
    async def test_run_certification_handles_exceptions(self, runner):
        """When certify_model raises, it's caught and reported as failed."""
        async def _raise(*args, **kwargs):
            raise RuntimeError("GPU OOM")

        with patch.object(runner, "certify_model", _raise):
            report = await runner.run_certification(
                models=["doomed-model"], prompt_count=2,
            )
            assert report.models_tested == 1
            assert len(report.results) == 1
            assert report.results[0].compile_success_rate == 0.0
            assert "GPU OOM" in report.results[0].errors[0]

    @pytest.mark.asyncio
    async def test_run_certification_rankings_sorting(self, runner):
        """Verify rankings sort correctly in the report."""
        async def _certify(model_name, prompts=None, **kwargs):
            if "pro" in model_name:
                return ModelCertificationResult(
                    model_name=model_name, prompts_tested=6,
                    compile_successes=6, compile_success_rate=1.0,
                    avg_latency_s=2.0, avg_prompt_tokens=50, avg_completion_tokens=50,
                )
            else:
                return ModelCertificationResult(
                    model_name=model_name, prompts_tested=6,
                    compile_successes=2, compile_success_rate=2 / 6,
                    avg_latency_s=0.5, avg_prompt_tokens=50, avg_completion_tokens=50,
                )

        with patch.object(runner, "certify_model", _certify):
            report = await runner.run_certification(
                models=["weak-model", "pro-model"], prompt_count=6,
            )
            assert report.rankings[0]["model_name"] == "pro-model"
            assert report.rankings[1]["model_name"] == "weak-model"
            assert report.fluent_models() == ["pro-model"]

    # ── certify_model integration (mocked bridge) ──────────────────────────

    @pytest.mark.asyncio
    async def test_certify_model_all_compile_success(self, runner):
        """All prompts compile — perfect score."""
        from hlf_mcp.hlf.hlf_llm_bridge import LLMCallResult

        async def _mock_send(self, prompt, **kwargs):
            return LLMCallResult(
                hlf_output="[HLF-v3]\n⌘ [GOAL] input=\"test\" output=\"r\"\nΩ",
                raw_response="```hlf\n[HLF-v3]\n⌘ [GOAL] input=\"test\" output=\"r\"\nΩ\n```",
                model_used="test-model",
                prompt_tokens=10,
                completion_tokens=20,
                latency_s=0.5,
                compile_success=False,  # bridge doesn't set this
            )

        with patch("hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send", _mock_send):
            # Also need to mock the compiler so it doesn't actually try to parse
            # HLFCompiler is lazily imported inside certify_model, so patch at its source
            with patch("hlf_mcp.hlf.compiler.HLFCompiler") as mock_compiler_cls:
                mock_compiler = MagicMock()
                mock_compiler.compile.return_value = {"ast": {}, "errors": []}
                mock_compiler_cls.return_value = mock_compiler

                result = await runner.certify_model("test-model")
                assert result.model_name == "test-model"
                assert result.prompts_tested == 6
                assert result.compile_successes == 6
                assert result.compile_success_rate == 1.0
                assert result.is_fluent()

    @pytest.mark.asyncio
    async def test_certify_model_all_fail(self, runner):
        """Every prompt raises an error — zero score."""
        from hlf_mcp.hlf.hlf_llm_bridge import LLMCallResult

        async def _mock_send(self, prompt, **kwargs):
            raise RuntimeError("Model not found")

        with patch("hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send", _mock_send):
            result = await runner.certify_model("ghost-model")
            assert result.compile_successes == 0
            assert result.compile_success_rate == 0.0
            assert not result.is_fluent()
            assert len(result.errors) == 6
            assert len(result.per_prompt_results) == 6

    @pytest.mark.asyncio
    async def test_certify_model_partial_success(self, runner):
        """Some prompts compile, some don't."""
        from hlf_mcp.hlf.hlf_llm_bridge import LLMCallResult

        call_count = 0

        async def _mock_send(self, prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return LLMCallResult(
                    hlf_output="[HLF-v3]\n⌘ [GOAL] input=\"x\" output=\"y\"\nΩ",
                    raw_response="```hlf\n[HLF-v3]\n⌘ [GOAL] input=\"x\" output=\"y\"\nΩ\n```",
                    model_used="partial",
                    prompt_tokens=10,
                    completion_tokens=20,
                    latency_s=0.3,
                    compile_success=False,
                )
            else:
                raise RuntimeError("timeout")

        with patch("hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send", _mock_send):
            with patch("hlf_mcp.hlf.compiler.HLFCompiler") as mock_compiler_cls:
                mock_compiler = MagicMock()
                mock_compiler.compile.return_value = {"ast": {}, "errors": []}
                mock_compiler_cls.return_value = mock_compiler

                result = await runner.certify_model("partial-model")
                assert result.compile_successes == 3
                assert result.compile_success_rate == 0.5
                assert not result.is_fluent()
                assert len(result.errors) == 3

    @pytest.mark.asyncio
    async def test_certify_model_compile_error(self, runner):
        """LLM outputs valid-looking HLF that doesn't actually compile."""
        from hlf_mcp.hlf.hlf_llm_bridge import LLMCallResult

        async def _mock_send(self, prompt, **kwargs):
            return LLMCallResult(
                hlf_output="[HLF-v3]\nbroken syntax\nΩ",
                raw_response="[HLF-v3]\nbroken syntax\nΩ",
                model_used="broken-model",
                prompt_tokens=5,
                completion_tokens=3,
                latency_s=0.1,
                compile_success=False,
            )

        with patch("hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send", _mock_send):
            # Let the real compiler attempt compilation (it will fail)
            # But we can mock to return a specific error
            with patch("hlf_mcp.hlf.compiler.HLFCompiler") as mock_compiler_cls:
                mock_compiler = MagicMock()
                mock_compiler.compile.side_effect = Exception("Parse error at line 2")
                mock_compiler_cls.return_value = mock_compiler

                result = await runner.certify_model("broken-model")
                assert result.compile_successes == 0
                # Each prompt result should have compile_error populated
                for pr in result.per_prompt_results:
                    assert not pr["compile_success"]
                    assert "Parse error" in pr["compile_error"]

    @pytest.mark.asyncio
    async def test_certify_model_with_custom_prompts(self, runner):
        """Custom prompt list should be used."""
        from hlf_mcp.hlf.hlf_llm_bridge import LLMCallResult

        async def _mock_send(self, prompt, **kwargs):
            return LLMCallResult(
                hlf_output="[HLF-v3]\n⌘ [EXEC] action=\"do\"\nΩ",
                raw_response="ok",
                model_used="custom",
                prompt_tokens=5,
                completion_tokens=3,
                latency_s=0.1,
                compile_success=False,
            )

        custom_prompts = (
            ("CUSTOM_A", "Write HLF with action A."),
            ("CUSTOM_B", "Write HLF with action B."),
        )

        with patch("hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send", _mock_send):
            with patch("hlf_mcp.hlf.compiler.HLFCompiler") as mock_compiler_cls:
                mock_compiler = MagicMock()
                mock_compiler.compile.return_value = {"ast": {}, "errors": []}
                mock_compiler_cls.return_value = mock_compiler

                result = await runner.certify_model("custom-model", prompts=custom_prompts)
                assert result.prompts_tested == 2
                labels = [p["prompt_label"] for p in result.per_prompt_results]
                assert labels == ["CUSTOM_A", "CUSTOM_B"]

    # ── Standard prompts ───────────────────────────────────────────────────

    def test_standard_prompts_count(self):
        assert len(_STANDARD_PROMPTS) == 6

    def test_standard_prompts_all_have_labels_and_text(self):
        for label, text in _STANDARD_PROMPTS:
            assert isinstance(label, str)
            assert len(label) > 0
            assert isinstance(text, str)
            assert len(text) > 0
            assert "HLF" in text

    @pytest.mark.asyncio
    async def test_prompt_count_capped_at_max(self, runner):
        """Prompt count beyond 6 is capped to 6."""
        mock_result = ModelCertificationResult(
            model_name="capped-model", prompts_tested=6,
            compile_successes=6, compile_success_rate=1.0,
            avg_latency_s=1.0, avg_prompt_tokens=50, avg_completion_tokens=50,
        )
        with patch.object(runner, "certify_model", AsyncMock(return_value=mock_result)):
            report = await runner.run_certification(
                models=["capped-model"], prompt_count=100,
            )
            assert report.total_prompts_per_model == 6

    @pytest.mark.asyncio
    async def test_prompt_count_minimum_one(self, runner):
        """Prompt count below 1 is raised to 1."""
        mock_result = ModelCertificationResult(
            model_name="single-prompt", prompts_tested=1,
            compile_successes=1, compile_success_rate=1.0,
            avg_latency_s=1.0, avg_prompt_tokens=50, avg_completion_tokens=50,
        )
        with patch.object(runner, "certify_model", AsyncMock(return_value=mock_result)):
            report = await runner.run_certification(
                models=["single-prompt"], prompt_count=0,
            )
            assert report.total_prompts_per_model == 1


# ── Serialization round-trip tests ─────────────────────────────────────────────


class TestSerializationRoundTrip:
    """End-to-end serialization tests for JSON persistence."""

    def test_full_report_roundtrip(self, populated_report):
        json_str = json.dumps(populated_report.to_dict())
        parsed = json.loads(json_str)
        restored = CertificationReport.from_dict(parsed)
        assert restored.models_tested == populated_report.models_tested
        assert restored.total_prompts_per_model == populated_report.total_prompts_per_model
        assert restored.best_model() == populated_report.best_model()
        assert restored.fluent_models() == populated_report.fluent_models()
        assert len(restored.results) == len(populated_report.results)
        for orig, rest in zip(populated_report.results, restored.results):
            assert orig.model_name == rest.model_name
            assert orig.compile_success_rate == rest.compile_success_rate

    def test_single_result_roundtrip(self, sample_result):
        json_str = json.dumps(sample_result.to_dict())
        parsed = json.loads(json_str)
        restored = ModelCertificationResult.from_dict(parsed)
        assert restored.model_name == sample_result.model_name
        assert restored.is_fluent() == sample_result.is_fluent()

    def test_empty_report_roundtrip(self, empty_report):
        json_str = json.dumps(empty_report.to_dict())
        parsed = json.loads(json_str)
        restored = CertificationReport.from_dict(parsed)
        assert restored.models_tested == 0
        assert restored.fluent_models() == []
