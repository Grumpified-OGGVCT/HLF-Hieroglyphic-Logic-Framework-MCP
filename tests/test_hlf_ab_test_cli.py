"""
Enterprise Hardening Commit 8b: A/B Test CLI Tests.

Validates:
  1. `define` creates config file
  2. `define` rejects empty backends
  3. `define` rejects unknown domain
  4. `define` rejects duplicate test names
  5. `run` on nonexistent test gives error
  6. `show` on nonexistent test gives error
  7. Config file is valid JSON
  8. Built-in prompts have reference_keywords
  9. CLI help text exists
 10. Real integration with qwen2.5-coder:0.5b (when Ollama is running)
 11. Mock Ollama: override the factory, not mock the backends
 12. `show` displays correct format for comparison results
 13. `run` and `show` end-to-end with monkeypatched HTTP
 14. `define` CLI with --help shows expected arguments

Strategy:
    - Production code (hlf_ab_test.py) contains NO mocks or dummies.
    - Tests monkeypatch `requests.post` to simulate Ollama responses.
    - Real integration tests are guarded by `@pytest.mark.requires_ollama`.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ──────────────────────────────────────────────────────────────────
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import under test
import scripts.hlf_ab_test as ab_test  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _clean_config_dir(monkeypatch, tmp_path):
    """Override CONFIG_DIR with a temp directory so tests are isolated."""
    monkeypatch.setattr(ab_test, "CONFIG_DIR", tmp_path / "ab_tests")
    ab_test.CONFIG_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def mock_ollama_response():
    """Return a realistic Ollama-like JSON response."""
    def _response(prompt: str) -> dict:
        return {
            "model": "test-model",
            "created_at": "2024-01-01T00:00:00Z",
            "response": f"This is a response to: {prompt[:50]}... It discusses diagnosis and treatment options comprehensively.",
            "done": True,
        }
    return _response


@pytest.fixture
def mock_requests_post(monkeypatch, mock_ollama_response):
    """Monkeypatch requests.post to return fake Ollama responses.

    This overrides the HTTP call, NOT the factory or the backend callable.
    The production code still builds real Ollama backend callables, but the
    HTTP layer is intercepted.
    """
    import requests as req_module

    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self._json = json_data
            self.status_code = status_code

        def json(self):
            return self._json

        def raise_for_status(self):
            if self.status_code >= 400:
                raise req_module.HTTPError(f"HTTP {self.status_code}")

    original_post = req_module.post

    def _mock_post(url, **kwargs):
        if url == ab_test.OLLAMA_GENERATE_URL:
            prompt = kwargs.get("json", {}).get("prompt", "")
            return MockResponse(mock_ollama_response(prompt))
        return original_post(url, **kwargs)

    monkeypatch.setattr(req_module, "post", _mock_post)
    return _mock_post


@pytest.fixture
def mock_ollama_running(monkeypatch):
    """Make check_ollama_running() always return True."""
    monkeypatch.setattr(ab_test, "check_ollama_running", lambda: True)


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 1: define creates config file
# ═══════════════════════════════════════════════════════════════════════════════════


class TestDefineCommand:
    def test_define_creates_config_file(self):
        """`hlf-ab-test define` should create a valid JSON config file."""
        argv = ["define", "--name", "test_v1", "--domain", "medical",
                "--backends", "medgemma:4b,llama3.2:latest"]
        result = ab_test.main(argv)
        assert result == 0

        config_path = ab_test._get_config_path("test_v1")
        assert config_path.exists()

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["name"] == "test_v1"
        assert config["domain"] == "medical"
        assert config["backends"] == ["medgemma:4b", "llama3.2:latest"]
        assert "created_at" in config

    def test_define_rejects_empty_backends(self):
        """`define` should fail when backends list is empty."""
        argv = ["define", "--name", "empty_test", "--domain", "medical",
                "--backends", "  ,  ,  "]
        result = ab_test.main(argv)
        assert result == 1

        # Config file should NOT exist
        config_path = ab_test._get_config_path("empty_test")
        assert not config_path.exists()

    def test_define_rejects_unknown_domain(self):
        """`define` should fail with non-zero exit for unknown domain."""
        argv = ["define", "--name", "bad_domain", "--domain", "astrology",
                "--backends", "llama3.2:latest"]
        # argparse validates choices and calls sys.exit(2) before cmd_define runs
        with pytest.raises(SystemExit) as exc_info:
            ab_test.main(argv)
        assert exc_info.value.code != 0

    def test_define_rejects_duplicate_name(self):
        """`define` should fail if a test with the same name already exists."""
        # First define succeeds
        argv1 = ["define", "--name", "dup_test", "--domain", "code",
                 "--backends", "qwen2.5-coder:0.5b"]
        result1 = ab_test.main(argv1)
        assert result1 == 0

        # Second define fails
        argv2 = ["define", "--name", "dup_test", "--domain", "math",
                 "--backends", "qwen2.5-coder:0.5b"]
        result2 = ab_test.main(argv2)
        assert result2 == 1

    def test_define_config_is_valid_json(self):
        """Config file saved by define should be parseable as valid JSON."""
        argv = ["define", "--name", "json_test", "--domain", "general",
                "--backends", "llama3.2:latest"]
        ab_test.main(argv)

        config_path = ab_test._get_config_path("json_test")
        raw = config_path.read_text(encoding="utf-8")

        # Must parse without error
        parsed = json.loads(raw)

        # Must be a dict with expected keys
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "domain" in parsed
        assert "backends" in parsed
        assert "created_at" in parsed
        assert isinstance(parsed["backends"], list)

    def test_define_accepts_multiple_backends(self):
        """`define` should accept and store multiple backend names."""
        argv = ["define", "--name", "multi_be", "--domain", "math",
                "--backends", "deepseek-r1:8b,qwen3:14b,qwen3.5:9b"]
        result = ab_test.main(argv)
        assert result == 0

        config = ab_test.load_config("multi_be")
        assert len(config["backends"]) == 3
        assert config["backends"] == ["deepseek-r1:8b", "qwen3:14b", "qwen3.5:9b"]


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 2: show on nonexistent test
# ═══════════════════════════════════════════════════════════════════════════════════


class TestShowCommand:
    def test_show_nonexistent_test_fails(self):
        """`show` on a test that was never defined should exit with error."""
        argv = ["show", "--test-name", "nonexistent_xyz"]
        result = ab_test.main(argv)
        assert result == 1

    def test_show_without_results_fails(self):
        """`show` on a defined but not-yet-run test should exit with error."""
        # Define the test
        ab_test.main(["define", "--name", "no_results", "--domain", "code",
                       "--backends", "deepcoder:1.5b"])

        # Try to show without running
        argv = ["show", "--test-name", "no_results"]
        result = ab_test.main(argv)
        assert result == 1

    def test_show_with_results_displays_correct_format(self, mock_requests_post, mock_ollama_running):
        """`show` output should include expected statistical fields."""
        # Define
        ab_test.main(["define", "--name", "show_fmt", "--domain", "medical",
                       "--backends", "medgemma:4b,llama3.2:latest"])

        # Run
        ab_test.main(["run", "--test-name", "show_fmt", "--prompts", "3"])

        # Capture show output
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result = ab_test.main(["show", "--test-name", "show_fmt"])
        finally:
            sys.stdout = old_stdout

        assert result == 0
        output = captured.getvalue()

        # Verify key fields appear in output
        assert "Test: show_fmt" in output
        assert "Backends:" in output
        assert "Prompts:" in output
        assert "Comparisons:" in output
        assert "Cohen's d:" in output
        assert "p-value:" in output
        assert "Winner:" in output
        assert "Recommendation:" in output


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 3: run on nonexistent test
# ═══════════════════════════════════════════════════════════════════════════════════


class TestRunCommand:
    def test_run_nonexistent_test_fails(self):
        """`run` on a test that was never defined should exit with error."""
        argv = ["run", "--test-name", "ghost_test", "--prompts", "5"]
        result = ab_test.main(argv)
        assert result == 1

    def test_run_stores_results(self, mock_requests_post, mock_ollama_running):
        """`run` should produce a results JSON file."""
        ab_test.main(["define", "--name", "run_store", "--domain", "general",
                       "--backends", "llama3.2:latest,qwen3.5:9b"])

        result = ab_test.main(["run", "--test-name", "run_store", "--prompts", "3"])
        assert result == 0

        results_path = ab_test._get_results_path("run_store")
        assert results_path.exists()

        results = json.loads(results_path.read_text(encoding="utf-8"))
        assert results["test_name"] == "run_store"
        assert "comparisons" in results
        assert results["n_prompts"] == 3
        assert "run_id" in results


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 4: Built-in prompts have reference_keywords
# ═══════════════════════════════════════════════════════════════════════════════════


class TestBuiltInPrompts:
    def test_medical_prompts_have_keywords(self):
        """Every medical prompt should have non-empty reference_keywords."""
        for p in ab_test.MEDICAL_PROMPTS:
            assert "reference_keywords" in p, f"Missing keywords in {p['prompt_id']}"
            assert len(p["reference_keywords"]) > 0, f"Empty keywords in {p['prompt_id']}"
            assert "prompt_id" in p
            assert "text" in p
            assert "domain" not in p  # Domain comes from corpus registry

    def test_code_prompts_have_keywords(self):
        """Every code prompt should have non-empty reference_keywords."""
        for p in ab_test.CODE_PROMPTS:
            assert "reference_keywords" in p, f"Missing keywords in {p['prompt_id']}"
            assert len(p["reference_keywords"]) > 0, f"Empty keywords in {p['prompt_id']}"

    def test_math_prompts_have_keywords(self):
        """Every math prompt should have non-empty reference_keywords."""
        for p in ab_test.MATH_PROMPTS:
            assert "reference_keywords" in p, f"Missing keywords in {p['prompt_id']}"
            assert len(p["reference_keywords"]) > 0, f"Empty keywords in {p['prompt_id']}"

    def test_general_prompts_have_keywords(self):
        """Every general prompt should have non-empty reference_keywords."""
        for p in ab_test.GENERAL_PROMPTS:
            assert "reference_keywords" in p, f"Missing keywords in {p['prompt_id']}"
            assert len(p["reference_keywords"]) > 0, f"Empty keywords in {p['prompt_id']}"

    def test_corpus_keywords_match_domains(self):
        """Each domain in CORPUS_KEYWORDS should have the expected entries."""
        assert "medical" in ab_test.CORPUS_KEYWORDS
        assert "code" in ab_test.CORPUS_KEYWORDS
        assert "math" in ab_test.CORPUS_KEYWORDS
        assert "general" in ab_test.CORPUS_KEYWORDS

        assert "diagnosis" in ab_test.CORPUS_KEYWORDS["medical"]
        assert "def" in ab_test.CORPUS_KEYWORDS["code"]
        assert "solution" in ab_test.CORPUS_KEYWORDS["math"]
        assert "answer" in ab_test.CORPUS_KEYWORDS["general"]

    def test_build_prompts_returns_correct_count(self):
        """build_prompts should return the requested number of prompts."""
        prompts = ab_test.build_prompts("medical", limit=5)
        assert len(prompts) == 5
        assert all(isinstance(p, ab_test.BenchmarkPrompt) for p in prompts)
        assert all(p.domain == "medical" for p in prompts)

    def test_build_prompts_rejects_unknown_domain(self):
        """build_prompts should raise ValueError for unknown domains."""
        with pytest.raises(ValueError, match="Unknown domain"):
            ab_test.build_prompts("nonexistent")

    def test_build_prompts_respects_domain(self):
        """Prompts built from a domain should all have that domain."""
        for domain in ["medical", "code", "math", "general"]:
            prompts = ab_test.build_prompts(domain, limit=3)
            for p in prompts:
                assert p.domain == domain, f"Expected {domain}, got {p.domain}"


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 5: CLI help text
# ═══════════════════════════════════════════════════════════════════════════════════


class TestCLIHelp:
    def test_help_text_exists(self):
        """`hlf-ab-test --help` should produce help text."""
        parser = ab_test.build_parser()
        help_text = parser.format_help()
        assert "A/B Backend Framework CLI" in help_text
        assert "define" in help_text
        assert "run" in help_text
        assert "show" in help_text

    def test_define_help(self):
        """`hlf-ab-test define --help` should show define args."""
        parser = ab_test.build_parser()
        # Find the define subparser help
        define_help = None
        for action in parser._actions:
            if hasattr(action, 'choices') and 'define' in (action.choices or {}):
                define_help = action.choices['define'].format_help()
                break
        # Fallback: check by looking at subparsers
        if define_help is None:
            # argparse stores subparsers in _subparsers
            for group in parser._subparsers._group_actions:
                if hasattr(group, 'choices') and 'define' in group.choices:
                    define_help = group.choices['define'].format_help()
                    break
        assert define_help is not None, "Could not find define subparser"
        assert "--name" in define_help
        assert "--domain" in define_help
        assert "--backends" in define_help

    def test_no_command_shows_help_and_exits_1(self):
        """Running with no subcommand should print help and exit 1."""
        result = ab_test.main([])
        assert result == 1


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 6: Mock Ollama — override the factory, not mock the backends
# ═══════════════════════════════════════════════════════════════════════════════════


class TestMockOllamaIntegration:
    """Full integration tests where only the HTTP POST is monkeypatched.

    The factory, backend callable, and benchmark runner are all real production
    code paths. No dummy backends are injected.
    """

    def test_mocked_http_full_workflow(self, mock_requests_post, mock_ollama_running):
        """define → run → show: full CLI workflow with mocked HTTP only."""
        # Define
        result_def = ab_test.main([
            "define", "--name", "full_wf", "--domain", "code",
            "--backends", "deepcoder:1.5b,qwen2.5-coder:0.5b",
        ])
        assert result_def == 0

        # Run
        result_run = ab_test.main([
            "run", "--test-name", "full_wf", "--prompts", "5",
        ])
        assert result_run == 0

        # Show
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result_show = ab_test.main(["show", "--test-name", "full_wf"])
        finally:
            sys.stdout = old_stdout

        assert result_show == 0
        output = captured.getvalue()
        assert "Test: full_wf" in output
        assert "deepcoder:1.5b" in output
        assert "qwen2.5-coder:0.5b" in output

    def test_backend_callable_has_model_name_attribute(self, mock_ollama_running):
        """The Ollama backend callable should expose model_name as attribute."""
        backend = ab_test.make_ollama_backend("test-model:latest")
        assert hasattr(backend, "model_name")
        assert backend.model_name == "test-model:latest"  # type: ignore[attr-defined]

    def test_make_ollama_backend_checks_server(self):
        """make_ollama_backend should raise RuntimeError if Ollama is not running."""
        # Patch check_ollama_running to return False
        with patch.object(ab_test, "check_ollama_running", return_value=False):
            with pytest.raises(RuntimeError, match="not running"):
                ab_test.make_ollama_backend("any-model")

    def test_ollama_timeout_propagates(self, monkeypatch, mock_ollama_running):
        """Timeout from requests should be wrapped and re-raised."""
        import requests as req_module

        def _raise_timeout(*args, **kwargs):
            raise req_module.Timeout("Simulated timeout")

        monkeypatch.setattr(req_module, "post", _raise_timeout)

        backend = ab_test.make_ollama_backend("slow-model")
        with pytest.raises(req_module.Timeout, match="timed out"):
            backend("test prompt")

    def test_ollama_connection_error_propagates(self, monkeypatch, mock_ollama_running):
        """ConnectionError from requests should be wrapped and re-raised."""
        import requests as req_module

        def _raise_conn_error(*args, **kwargs):
            raise req_module.ConnectionError("Simulated connection failure")

        monkeypatch.setattr(req_module, "post", _raise_conn_error)

        backend = ab_test.make_ollama_backend("gone-model")
        with pytest.raises(req_module.ConnectionError, match="Failed to connect"):
            backend("test prompt")

    def test_ollama_empty_response_handled(self, monkeypatch, mock_ollama_running):
        """Empty response from Ollama should raise RuntimeError."""
        import requests as req_module

        class EmptyResponse:
            status_code = 200
            @staticmethod
            def json():
                return {"response": ""}
            @staticmethod
            def raise_for_status():
                pass

        monkeypatch.setattr(req_module, "post", lambda *a, **kw: EmptyResponse())

        backend = ab_test.make_ollama_backend("empty-model")
        with pytest.raises(RuntimeError, match="empty response"):
            backend("test prompt")


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 7: Real Ollama integration — only runs with --run-ollama
# ═══════════════════════════════════════════════════════════════════════════════════


@pytest.mark.requires_ollama
class TestRealOllamaIntegration:
    """Tests that require a live Ollama instance.

    Run with: pytest tests/test_hlf_ab_test_cli.py --run-ollama -v
    """

    def test_real_ollama_define_run_show(self):
        """Full end-to-end with real Ollama using the fastest models available."""
        import uuid
        test_name = f"real_integration_{uuid.uuid4().hex[:8]}"

        # Define with two backends (pairwise comparison needs 2+)
        result_def = ab_test.main([
            "define", "--name", test_name, "--domain", "code",
            "--backends", "qwen2.5-coder:0.5b,deepcoder:1.5b",
        ])
        assert result_def == 0

        # Verify config
        config = ab_test.load_config(test_name)
        assert config["domain"] == "code"
        assert "qwen2.5-coder:0.5b" in config["backends"]
        assert "deepcoder:1.5b" in config["backends"]

        # Run with a small prompt set
        result_run = ab_test.main([
            "run", "--test-name", test_name, "--prompts", "3",
        ])
        assert result_run == 0

        # Verify results exist
        results = ab_test.load_results(test_name)
        assert results["test_name"] == test_name
        assert results["n_prompts"] == 3
        assert "run_id" in results
        assert results["comparisons"]  # Pairwise comparisons between the two backends

    def test_real_ollama_backend_callable(self):
        """Direct test: make_ollama_backend returns a working callable."""
        backend = ab_test.make_ollama_backend("qwen2.5-coder:0.5b")
        assert callable(backend)
        assert hasattr(backend, "model_name")
        assert backend.model_name == "qwen2.5-coder:0.5b"  # type: ignore[attr-defined]

        # Make an actual call
        response = backend("Write a Python function that returns the number 42.")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_check_ollama_running_positive(self):
        """check_ollama_running should return True when Ollama is up."""
        assert ab_test.check_ollama_running() is True


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 8: Results file format
# ═══════════════════════════════════════════════════════════════════════════════════


class TestResultsFile:
    def test_results_file_is_valid_json(self, mock_requests_post, mock_ollama_running):
        """Results file should be parseable as valid JSON."""
        ab_test.main(["define", "--name", "json_results", "--domain", "math",
                       "--backends", "qwen3.5:9b"])
        ab_test.main(["run", "--test-name", "json_results", "--prompts", "2"])

        results_path = ab_test._get_results_path("json_results")
        raw = results_path.read_text(encoding="utf-8")

        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert "test_name" in parsed
        assert "comparisons" in parsed
        assert "run_id" in parsed

    def test_results_comparison_has_all_fields(self, mock_requests_post, mock_ollama_running):
        """Each comparison entry should have all statistical fields."""
        ab_test.main(["define", "--name", "all_fields", "--domain", "general",
                       "--backends", "llama3.2:latest,qwen3.5:9b"])
        ab_test.main(["run", "--test-name", "all_fields", "--prompts", "3"])

        results = ab_test.load_results("all_fields")
        comparisons = results["comparisons"]

        assert len(comparisons) > 0
        for key, comp in comparisons.items():
            assert "backend_a" in comp
            assert "backend_b" in comp
            assert "domain" in comp
            assert "n_prompts" in comp
            assert "mean_a" in comp
            assert "mean_b" in comp
            assert "diff_mean" in comp
            assert "cohens_d" in comp
            assert "p_value" in comp
            assert "confidence_95_lower" in comp
            assert "confidence_95_upper" in comp
            assert "winner" in comp
            assert "significant" in comp
            assert "recommendation" in comp


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 9: Edge cases
# ═══════════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_prompt_limit_capped_at_corpus_size(self, mock_requests_post, mock_ollama_running):
        """Requesting more prompts than available should proceed with what exists."""
        ab_test.main(["define", "--name", "overflow", "--domain", "general",
                       "--backends", "llama3.2:latest"])
        # General has 10 prompts; request 999
        result = ab_test.main(["run", "--test-name", "overflow", "--prompts", "999"])
        assert result == 0

        results = ab_test.load_results("overflow")
        assert results["n_prompts"] <= 10

    def test_define_output_format(self):
        """`define` should print a confirmation message on success."""
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result = ab_test.main([
                "define", "--name", "output_test", "--domain", "code",
                "--backends", "deepcoder:1.5b",
            ])
        finally:
            sys.stdout = old_stdout

        assert result == 0
        output = captured.getvalue()
        assert "Test 'output_test' defined" in output
        assert "Domain: code" in output
        assert "Backends:" in output

    def test_run_prints_summary(self, mock_requests_post, mock_ollama_running):
        """`run` should print a summary of the benchmark."""
        ab_test.main(["define", "--name", "run_summ", "--domain", "math",
                       "--backends", "qwen3.5:9b"])

        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            result = ab_test.main(["run", "--test-name", "run_summ", "--prompts", "3"])
        finally:
            sys.stdout = old_stdout

        assert result == 0
        output = captured.getvalue()
        assert "Running A/B test" in output
        assert "Benchmark complete" in output
        assert "Results saved to:" in output


# ═══════════════════════════════════════════════════════════════════════════════════
# Test 10: ensure NO dummies/mocks in production module
# ═══════════════════════════════════════════════════════════════════════════════════


class TestProductionPurity:
    def test_no_mock_factory_in_module(self):
        """The CLI module must NOT export any mock/dummy backend functions."""
        # The only backend factory should be make_ollama_backend
        # There should be no make_dummy_backend, make_mock_backend, etc.
        module_content = (Path(__file__).resolve().parent.parent
                          / "scripts" / "hlf_ab_test.py").read_text(encoding="utf-8")

        forbidden = [
            "make_dummy_backend",
            "make_fake_backend",
            "make_mock_backend",
            "DummyBackend",
            "FakeBackend",
            "MockBackend",
        ]
        for pattern in forbidden:
            assert pattern not in module_content, (
                f"Forbidden pattern '{pattern}' found in production code. "
                "Production code must not contain dummies or mocks."
            )

    def test_no_hardcoded_test_backends(self):
        """The CLI module must not hardcode test-specific backend responses."""
        module_file = (Path(__file__).resolve().parent.parent
                       / "scripts" / "hlf_ab_test.py")
        content = module_file.read_text(encoding="utf-8")

        # The only references to model names should be in: constants, corpora examples,
        # argparse defaults, or docstrings. No hardcoded "mock returns" paths.
        # This is a heuristic check — we verify make_ollama_backend always makes
        # real HTTP calls.
        assert "def make_ollama_backend" in content
        func_start = content.index("def make_ollama_backend")
        func_body = content[func_start:]

        # The function should contain the requests.post call
        assert "requests.post" in func_body
        assert "OLLAMA_GENERATE_URL" in func_body

    def test_backend_benchmark_imported_not_modified(self):
        """backend_benchmark classes should be imported, not redefined."""
        module_file = (Path(__file__).resolve().parent.parent
                       / "scripts" / "hlf_ab_test.py")
        content = module_file.read_text(encoding="utf-8")

        # These classes should only appear on the import line, not as class definitions
        import_line = "from hlf_mcp.hlf.backend_benchmark import"
        assert import_line in content

        # Count occurrences after the import (should not define new versions)
        after_import = content[content.index(import_line):]
        # class BackendBenchmark / class BenchmarkPrompt — should not exist
        assert "class BackendBenchmark" not in after_import
        assert "class BenchmarkPrompt" not in after_import
