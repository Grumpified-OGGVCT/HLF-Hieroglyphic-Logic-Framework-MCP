"""
tests/test_hlfsh_llm.py — Tests for LLM-backed commands in the HLF Shell REPL.

Tests the new :gen, :model, :models, and :certify commands on HLFShell
using mocked LLM bridges so no actual Ollama connection is required.
"""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.hlfsh import HELP_TEXT, HLFShell

# ── valid HLF sample used across tests ───────────────────────────────────

VALID_HLF = """\
[HLF-v3]
Δ [INTENT] goal="hello_world"
  ⩕ [PRIORITY] level="high"
Ω"""

INVALID_HLF = "[HLF-v3]\nΔ completely broken {{ syntax\nΩ"

VALID_RESULT = """\
[HLF-v3]
RESULT 0 "success"
Ω"""


# ── mock LLMCallResult builder ───────────────────────────────────────────


def _mock_result(
    hlf_output: str = VALID_HLF,
    model_used: str = "deepseek-v4-pro:cloud",
    latency_s: float = 0.5,
    extracted: bool = True,
    raw_response: str = "",
) -> MagicMock:
    """Build a MagicMock that quacks like an LLMCallResult."""
    result = MagicMock()
    result.hlf_output = hlf_output
    result.model_used = model_used
    result.latency_s = latency_s
    result.extracted = extracted
    result.raw_response = raw_response or f"```hlf\n{hlf_output}\n```"
    result.compile_success = False
    return result


def _mock_bridge(result_override: MagicMock | None = None) -> MagicMock:
    """Build a mock bridge with an async send() that returns a result."""
    bridge = MagicMock()
    bridge.send = AsyncMock(return_value=result_override or _mock_result())
    return bridge


# ── fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def shell() -> HLFShell:
    """Create a fresh HLFShell with default settings (no live bridge)."""
    return HLFShell(gas_limit=100)


# ── :model command tests ─────────────────────────────────────────────────


class TestModelCommand:
    """Tests for the :model command (show/switch active model)."""

    def test_model_no_arg_shows_current(self, shell: HLFShell) -> None:
        """":model" without argument should show the current model."""
        capture = StringIO()
        with patch("sys.stdout", capture):
            shell._cmd_model("")
        output = capture.getvalue()
        assert shell.active_model in output
        assert "Current model" in output

    def test_model_switch_updates_active(self, shell: HLFShell) -> None:
        """:model <name> should switch the active model."""
        capture = StringIO()
        with patch("sys.stdout", capture):
            shell._cmd_model("kimi-k2.5:cloud")
        output = capture.getvalue()
        assert shell.active_model == "kimi-k2.5:cloud"
        assert "Switched" in output

    def test_model_switch_nulls_bridge(self, shell: HLFShell) -> None:
        """:model <name> should invalidate the cached bridge."""
        # Access bridge to create it
        with patch(
            "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge"
        ) as mock_bridge_cls:
            mock_bridge_cls.return_value = MagicMock()
            _ = shell.bridge  # force creation
            assert shell._bridge is not None

        # Now switch model
        shell._cmd_model("gemma3:12b-cloud")
        assert shell._bridge is None

    def test_model_switch_new_bridge_uses_new_model(self, shell: HLFShell) -> None:
        """:model <name> should cause the next bridge init to use the new model."""
        shell._cmd_model("nemotron-3-super:cloud")
        with patch(
            "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge"
        ) as mock_bridge_cls:
            mock_bridge_cls.return_value = MagicMock()
            _ = shell.bridge
            mock_bridge_cls.assert_called_once_with(
                model="nemotron-3-super:cloud", ollama_url="http://localhost:11434"
            )

    def test_model_via_dispatch(self, shell: HLFShell) -> None:
        """:model should be reachable via _dispatch_command."""
        result = shell._dispatch_command("model", "devstral-2:123b-cloud")
        assert result is True
        assert shell.active_model == "devstral-2:123b-cloud"

    def test_model_via_dispatch_no_arg(self, shell: HLFShell) -> None:
        """:model without arg via dispatch should show current model."""
        result = shell._dispatch_command("model", "")
        assert result is True

    def test_model_switch_whitespace_arg(self, shell: HLFShell) -> None:
        """Whitespace-only arg should be treated as no arg."""
        original = shell.active_model
        capture = StringIO()
        with patch("sys.stdout", capture):
            shell._cmd_model("   ")
        output = capture.getvalue()
        # Should show current model, not "switch" to empty
        assert "Current model" in output
        assert shell.active_model == original


# ── :models command tests ────────────────────────────────────────────────


class TestModelsCommand:
    """Tests for the :models command (list available Ollama models)."""

    def test_models_via_dispatch(self, shell: HLFShell) -> None:
        """:models should be reachable via _dispatch_command."""
        # Mock the API response
        mock_response = {"models": [{"name": "llama3:8b"}, {"name": "deepseek-v4-pro:cloud"}]}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(mock_response).encode()
            )
            capture = StringIO()
            with patch("sys.stdout", capture):
                result = shell._dispatch_command("models", "")
            assert result is True
            output = capture.getvalue()
            assert "llama3:8b" in output
            assert "deepseek-v4-pro:cloud" in output

    def test_models_marks_active(self, shell: HLFShell) -> None:
        """The active model should be marked in the list."""
        shell._cmd_model("kimi-k2.5:cloud")
        mock_response = {"models": [{"name": "kimi-k2.5:cloud"}, {"name": "gemma3:12b-cloud"}]}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(mock_response).encode()
            )
            capture = StringIO()
            with patch("sys.stdout", capture):
                shell._cmd_models()
            output = capture.getvalue()
            assert "(active)" in output
            assert "kimi-k2.5:cloud" in output

    def test_models_api_error_fallback_ollama_cli(self, shell: HLFShell) -> None:
        """When API fails, fall back to 'ollama list' shell command."""
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with patch("subprocess.check_output") as mock_check_output:
                mock_check_output.return_value = (
                    "NAME                    ID              SIZE      MODIFIED\n"
                    "llama3:8b              abc123          4.7 GB    2 days ago\n"
                    "deepseek-v4-pro:cloud  def456          12 GB     5 hours ago\n"
                )
                capture = StringIO()
                with patch("sys.stdout", capture):
                    shell._cmd_models()
                output = capture.getvalue()
                assert "llama3:8b" in output
                assert "deepseek-v4-pro:cloud" in output

    def test_models_complete_failure(self, shell: HLFShell) -> None:
        """When both API and CLI fail, show error message."""
        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with patch("subprocess.check_output", side_effect=FileNotFoundError("ollama not found")):
                capture = StringIO()
                with patch("sys.stdout", capture):
                    shell._cmd_models()
                output = capture.getvalue()
                assert "Cannot reach Ollama" in output

    def test_models_empty_list(self, shell: HLFShell) -> None:
        """When no models are available, show appropriate message."""
        mock_response = {"models": []}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(mock_response).encode()
            )
            capture = StringIO()
            with patch("sys.stdout", capture):
                shell._cmd_models()
            output = capture.getvalue()
            assert "no models" in output.lower()

    def test_models_sorted_output(self, shell: HLFShell) -> None:
        """Models should be listed in alphabetical order."""
        mock_response = {
            "models": [
                {"name": "z-model:latest"},
                {"name": "a-model:latest"},
                {"name": "m-model:latest"},
            ]
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(mock_response).encode()
            )
            capture = StringIO()
            with patch("sys.stdout", capture):
                shell._cmd_models()
            output = capture.getvalue()
            lines = [l.strip() for l in output.splitlines() if l.strip().startswith("  ")]
            # Strip "(active)" markers for comparison
            names = [l.split()[0] if l.split() else "" for l in lines]
            assert names == sorted(names), f"Not sorted: {names}"


# ── :gen command tests ───────────────────────────────────────────────────


class TestGenCommand:
    """Tests for the :gen command (generate HLF from natural language)."""

    @pytest.mark.asyncio
    async def test_gen_valid_hlf_compiles_and_evals(self, shell: HLFShell) -> None:
        """:gen should compile and eval valid generated HLF."""
        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("create hello world program")
        output = capture.getvalue()
        assert "✓ Compiled successfully" in output
        assert "gas:" in output

    @pytest.mark.asyncio
    async def test_gen_invalid_hlf_shows_error(self, shell: HLFShell) -> None:
        """:gen should show compile error for invalid HLF."""
        shell._bridge = _mock_bridge(
            _mock_result(hlf_output=INVALID_HLF, extracted=True)
        )
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("create something broken")
        output = capture.getvalue()
        assert "✗ Compile failed" in output

    @pytest.mark.asyncio
    async def test_gen_not_extracted_shows_raw(self, shell: HLFShell) -> None:
        """:gen should show raw response when HLF wasn't extracted."""
        raw = "Here is a program: ```\nprint('hello')\n```"
        shell._bridge = _mock_bridge(
            _mock_result(hlf_output=INVALID_HLF, extracted=False, raw_response=raw)
        )
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("create something")
        output = capture.getvalue()
        assert "Raw LLM response" in output
        assert "print('hello')" in output

    @pytest.mark.asyncio
    async def test_gen_empty_description(self, shell: HLFShell) -> None:
        """:gen with empty description should show usage."""
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("")
        output = capture.getvalue()
        assert "Usage" in output

    @pytest.mark.asyncio
    async def test_gen_llm_error(self, shell: HLFShell) -> None:
        """:gen should handle LLM call failures gracefully."""
        bridge = MagicMock()
        bridge.send = AsyncMock(side_effect=RuntimeError("Connection refused"))
        shell._bridge = bridge
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("create a function")
        output = capture.getvalue()
        assert "LLM call failed" in output

    @pytest.mark.asyncio
    async def test_gen_uses_active_model(self, shell: HLFShell) -> None:
        """:gen should use the current active model."""
        shell._cmd_model("kimi-k2.5:cloud")

        bridge = MagicMock()
        bridge.send = AsyncMock(return_value=_mock_result(model_used="kimi-k2.5:cloud"))
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("test prompt")
        output = capture.getvalue()
        # Should mention the active model in the output
        assert "kimi-k2.5:cloud" in output

    @pytest.mark.asyncio
    async def test_gen_via_dispatch(self, shell: HLFShell) -> None:
        """:gen should be reachable via _dispatch_command."""
        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        capture = StringIO()
        with patch("sys.stdout", capture):
            # _dispatch_command uses asyncio.run() which conflicts with
            # pytest-asyncio's running loop — call _cmd_gen directly via await
            await shell._cmd_gen("hello world")
        output = capture.getvalue()
        assert "Generated HLF" in output
        assert "✓ Compiled successfully" in output

    @pytest.mark.asyncio
    async def test_gen_displays_result_details(self, shell: HLFShell) -> None:
        """:gen should show model name and latency in output."""
        shell._bridge = _mock_bridge(
            _mock_result(hlf_output=VALID_HLF, model_used="devstral-2:123b-cloud", latency_s=2.3)
        )
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("test")
        output = capture.getvalue()
        assert "devstral-2:123b-cloud" in output
        assert "2.3s" in output

    @pytest.mark.asyncio
    async def test_gen_eval_pipeline_tracks_state(self, shell: HLFShell) -> None:
        """:gen should track gas and env state when compile succeeds."""
        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_RESULT))
        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_gen("return success")
        # After successful gen+eval, gas should be incremented
        assert shell.gas_used > 0
        assert shell.statement_count > 0

    def test_gen_dispatch_entry_mocked(self, shell: HLFShell) -> None:
        """":gen dispatch entry calls asyncio.run with _cmd_gen."""
        import asyncio

        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        with patch("asyncio.run") as mock_run:
            result = shell._dispatch_command("gen", "hello world")
        assert result is True
        mock_run.assert_called_once()

    def test_gen_dispatch_returns_true(self, shell: HLFShell) -> None:
        """":gen via dispatch should return True (handled)."""
        import asyncio

        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        # Mock asyncio.run to avoid running in pytest-asyncio's loop
        with patch("asyncio.run", side_effect=lambda coro: None):
            result = shell._dispatch_command("gen", "test")
        assert result is True


# ── :certify command tests ───────────────────────────────────────────────


class TestCertifyCommand:
    """Tests for the :certify command (self-test model HLF accuracy)."""

    @pytest.mark.asyncio
    async def test_certify_all_pass(self, shell: HLFShell) -> None:
        """:certify should show 6/6 when all prompts compile."""
        bridge = MagicMock()
        bridge.send = AsyncMock(
            return_value=_mock_result(hlf_output=VALID_HLF, latency_s=1.0)
        )
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "6/6" in output
        assert "FLUENT" in output

    @pytest.mark.asyncio
    async def test_certify_all_fail(self, shell: HLFShell) -> None:
        """:certify should show 0/6 when nothing compiles."""
        bridge = MagicMock()
        bridge.send = AsyncMock(
            return_value=_mock_result(hlf_output=INVALID_HLF, latency_s=0.5)
        )
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "0/6" in output
        assert "NOT fluent" in output

    @pytest.mark.asyncio
    async def test_certify_partial(self, shell: HLFShell) -> None:
        """:certify should show partial score (3/6 → PARTIAL)."""
        bridge = MagicMock()
        # Alternate pass/fail
        call_count = 0

        async def alternating_send(prompt: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return _mock_result(hlf_output=VALID_HLF, latency_s=0.3)
            else:
                return _mock_result(hlf_output=INVALID_HLF, latency_s=0.3)

        bridge.send = AsyncMock(side_effect=alternating_send)
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "3/6" in output
        assert "PARTIAL" in output

    @pytest.mark.asyncio
    async def test_certify_edge_threshold_80(self, shell: HLFShell) -> None:
        """:certify with 5/6 should show FLUENT (>= 80%)."""
        bridge = MagicMock()
        call_count = 0

        async def mostly_pass(prompt: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _mock_result(hlf_output=INVALID_HLF, latency_s=0.3)
            return _mock_result(hlf_output=VALID_HLF, latency_s=0.3)

        bridge.send = AsyncMock(side_effect=mostly_pass)
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "5/6" in output
        assert "FLUENT" in output

    @pytest.mark.asyncio
    async def test_certify_llm_error_in_middle(self, shell: HLFShell) -> None:
        """:certify should handle LLM errors during the test run."""
        bridge = MagicMock()
        call_count = 0

        async def error_on_third(prompt: str, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise RuntimeError("Timeout")
            return _mock_result(hlf_output=VALID_HLF, latency_s=0.3)

        bridge.send = AsyncMock(side_effect=error_on_third)
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "LLM error" in output
        # Should still show 5/6 (one errored, rest passed)
        assert "5/6" in output

    @pytest.mark.asyncio
    async def test_certify_shows_model_name(self, shell: HLFShell) -> None:
        """:certify should display the model being tested."""
        shell._cmd_model("gemini-3-pro-preview:latest")
        bridge = MagicMock()
        bridge.send = AsyncMock(
            return_value=_mock_result(hlf_output=VALID_HLF, latency_s=1.0)
        )
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "gemini-3-pro-preview:latest" in output

    @pytest.mark.asyncio
    async def test_certify_labels_appear(self, shell: HLFShell) -> None:
        """:certify should show all 6 test labels."""
        bridge = MagicMock()
        bridge.send = AsyncMock(
            return_value=_mock_result(hlf_output=VALID_HLF, latency_s=0.2)
        )
        shell._bridge = bridge

        capture = StringIO()
        with patch("sys.stdout", capture):
            await shell._cmd_certify()
        output = capture.getvalue()
        expected_labels = ["SET", "INTENT", "CONSTRAINT", "DELEGATE", "RESULT", "MEMORY"]
        for label in expected_labels:
            assert label in output, f"Missing label: {label}"

    @pytest.mark.asyncio
    async def test_certify_via_dispatch(self, shell: HLFShell) -> None:
        """:certify should be reachable via _dispatch_command."""
        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF, latency_s=0.1))
        capture = StringIO()
        with patch("sys.stdout", capture):
            # _dispatch_command uses asyncio.run() — test via direct await
            await shell._cmd_certify()
        output = capture.getvalue()
        assert "Score:" in output

    def test_certify_dispatch_entry_mocked(self, shell: HLFShell) -> None:
        """":certify dispatch entry calls asyncio.run with _cmd_certify."""
        import asyncio

        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        with patch("asyncio.run") as mock_run:
            result = shell._dispatch_command("certify", "")
        assert result is True
        mock_run.assert_called_once()

    def test_certify_dispatch_returns_true(self, shell: HLFShell) -> None:
        """":certify via dispatch should return True (handled)."""
        import asyncio

        shell._bridge = _mock_bridge(_mock_result(hlf_output=VALID_HLF))
        with patch("asyncio.run", side_effect=lambda coro: None):
            result = shell._dispatch_command("certify", "")
        assert result is True


# ── dispatch and integration tests ───────────────────────────────────────


class TestDispatch:
    """Tests for the _dispatch_command multiplexer."""

    def test_unknown_cmd_returns_false(self, shell: HLFShell) -> None:
        """Unknown commands should return False so handle_command handles them."""
        result = shell._dispatch_command("foobar", "")
        assert result is False

    def test_unknown_cmd_falls_through_to_handle(self, shell: HLFShell) -> None:
        """Unknown commands via dispatch should still be caught by handle_command."""
        result = shell.handle_command(":foobar")
        assert "Unknown command" in result

    def test_old_commands_still_work(self, shell: HLFShell) -> None:
        """Pre-existing commands should still work through handle_command."""
        # :dispatch won't handle it, so falls to handle_command
        assert shell._dispatch_command("help", "") is False
        result = shell.handle_command(":help")
        assert result == HELP_TEXT

    def test_env_still_works(self, shell: HLFShell) -> None:
        """:env should still work through handle_command."""
        assert shell._dispatch_command("env", "") is False
        result = shell.handle_command(":env")
        assert "empty" in result.lower()

    def test_quit_still_works(self, shell: HLFShell) -> None:
        """:quit should still raise SystemExit."""
        assert shell._dispatch_command("quit", "") is False
        with pytest.raises(SystemExit):
            shell.handle_command(":quit")


# ── constructor tests ────────────────────────────────────────────────────


class TestConstructor:
    """Tests for the updated HLFShell constructor."""

    def test_default_model_set(self) -> None:
        """Default model should be deepseek-v4-pro:cloud."""
        s = HLFShell()
        assert s.active_model == "deepseek-v4-pro:cloud"

    def test_custom_model_set(self) -> None:
        """Custom model should override the default."""
        s = HLFShell(model="llama3:8b")
        assert s.active_model == "llama3:8b"

    def test_ollama_url_default(self) -> None:
        """Default Ollama URL should be localhost:11434."""
        s = HLFShell()
        assert s.ollama_url == "http://localhost:11434"

    def test_ollama_url_trailing_slash_stripped(self) -> None:
        """Trailing slashes on ollama_url should be stripped."""
        s = HLFShell(ollama_url="http://localhost:11434/")
        assert s.ollama_url == "http://localhost:11434"

    def test_custom_ollama_url(self) -> None:
        """Custom Ollama URL should be preserved."""
        s = HLFShell(ollama_url="http://ollama.internal:8080")
        assert s.ollama_url == "http://ollama.internal:8080"

    def test_bridge_starts_none(self) -> None:
        """Bridge should start as None (lazy init)."""
        s = HLFShell()
        assert s._bridge is None

    def test_backward_compatible_no_new_args(self) -> None:
        """Constructor should work with only gas_limit (backward compat)."""
        s = HLFShell(gas_limit=500)
        assert s.gas_limit == 500
        assert s.active_model == "deepseek-v4-pro:cloud"
        assert s._bridge is None


# ── bridge property tests ────────────────────────────────────────────────


class TestBridgeProperty:
    """Tests for the lazy bridge property."""

    def test_bridge_creates_on_first_access(self, shell: HLFShell) -> None:
        """Accessing .bridge should create a new HLFLLMBridge."""
        with patch(
            "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge"
        ) as mock_bridge_cls:
            mock_bridge_cls.return_value = MagicMock()
            bridge = shell.bridge
            assert bridge is not None
            mock_bridge_cls.assert_called_once()

    def test_bridge_uses_active_model(self, shell: HLFShell) -> None:
        """Bridge should be created with the active model."""
        shell._cmd_model("kimi-k2.5:cloud")
        with patch(
            "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge"
        ) as mock_bridge_cls:
            mock_bridge_cls.return_value = MagicMock()
            _ = shell.bridge
            mock_bridge_cls.assert_called_once_with(
                model="kimi-k2.5:cloud", ollama_url="http://localhost:11434"
            )

    def test_bridge_cached_after_creation(self, shell: HLFShell) -> None:
        """Bridge should be cached and only created once."""
        with patch(
            "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge"
        ) as mock_bridge_cls:
            mock_bridge_cls.return_value = MagicMock()
            b1 = shell.bridge
            b2 = shell.bridge
            assert b1 is b2
            mock_bridge_cls.assert_called_once()  # only once


# ── HELP_TEXT test ───────────────────────────────────────────────────────


def test_help_text_includes_new_commands() -> None:
    """HELP_TEXT should include the new LLM commands."""
    assert ":gen" in HELP_TEXT
    assert ":model" in HELP_TEXT
    assert ":models" in HELP_TEXT
    assert ":certify" in HELP_TEXT
