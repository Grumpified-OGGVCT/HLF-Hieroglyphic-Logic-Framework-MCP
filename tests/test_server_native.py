"""Tests for the native HLF speak layer (server_native.py)."""

from __future__ import annotations

import pytest

from hlf_mcp.server_native import _hash_trace, _translate_hlf_to_nl


class _FakeCtx:
    """Minimal fake context for native tools that don't need full server wiring."""

    def translate_hlf_to_english(self, source: str, target_language: str = "en"):
        return {"translation": f"Translated: {source[:20]}..."}

    def emit_governance_event(self, **kwargs):
        pass

    class _FakeStore:
        def store(self, *args, **kwargs):
            pass

    memory_store = _FakeStore()

    def capsule_run(self, **kwargs):
        return {"success": True, "hlf_result": "[RESULT] status=\"ok\"\n"}


class FakeMcp:
    """Minimal fake MCP whose tool decorator is a no-op passthrough."""

    @staticmethod
    def tool():
        def decorator(fn):
            return fn
        return decorator


@pytest.fixture
def fake_ctx():
    return _FakeCtx()


class TestHashTrace:
    def test_hash_trace_is_hex_32(self):
        ref = _hash_trace("hello", "ok")
        assert len(ref) == 32
        assert all(c in "0123456789abcdef" for c in ref)

    def test_hash_trace_changes_with_source(self):
        assert _hash_trace("a", "ok") != _hash_trace("b", "ok")

    def test_hash_trace_changes_with_label(self):
        assert _hash_trace("a", "ok") != _hash_trace("a", "fail")


class TestTranslateFallback:
    def test_translate_uses_ctx_first(self, fake_ctx):
        result = _translate_hlf_to_nl("[INTENT] goal=\"x\"", "en", fake_ctx)
        assert "Translated:" in result

    def test_translate_fallback_on_error(self, fake_ctx):
        class BadCtx:
            def translate_hlf_to_english(self, source, target_language="en"):
                raise RuntimeError("boom")

        result = _translate_hlf_to_nl("[INTENT] goal=\"x\"", "en", BadCtx())
        assert "[INTENT]" in result


class TestHlfNativeSpeak:
    def test_valid_hlf_returns_ok(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_native_speak"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert result["status"] == "ok"
        assert result["valid"] is True
        assert "trace_ref" in result
        assert result["gas_used"] >= 0

    def test_invalid_hlf_strict_rejects(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_native_speak"]

        result = fn("not hlf at all", delivery_mode="strict")

        assert result["status"] == "rejected"
        assert result["valid"] is False
        assert "error" in result

    def test_invalid_hlf_auto_repair(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_native_speak"]

        source = '[hlf-v3]\n[intent] goal="test"\n'
        result = fn(source, delivery_mode="auto", auto_repair=True)

        assert result["status"] in ("ok", "repaired")

    def test_returns_natural_language(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_native_speak"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert "natural_language" in result
        assert isinstance(result["natural_language"], str)

    def test_corrections_list_present(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_native_speak"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert "corrections" in result
        assert isinstance(result["corrections"], list)


class TestHlfValidateOutput:
    def test_valid_output_passes(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_validate_output"]

        output = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(output, required_tags=["INTENT"])

        assert result["status"] == "ok"
        assert result["valid"] is True
        assert any(c["name"] == "compile" and c["passed"] for c in result["checks"])
        assert any(c["name"] == "terminator" and c["passed"] for c in result["checks"])

    def test_missing_tag_fails(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_validate_output"]

        output = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(output, required_tags=["RESULT"])

        assert result["status"] == "needs_correction"
        assert result["valid"] is False
        assert any(c["name"] == "required_tags" and not c["passed"] for c in result["checks"])

    def test_missing_omega_fails(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_validate_output"]

        output = '[HLF-v3]\nΔ [INTENT] goal="test"\n'
        result = fn(output, must_terminate=True)

        assert result["status"] == "needs_correction"
        assert any(c["name"] == "terminator" and not c["passed"] for c in result["checks"])

    def test_empty_output_fails(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_validate_output"]

        result = fn("")

        assert result["status"] == "needs_correction"
        assert any(c["name"] == "non_empty" and not c["passed"] for c in result["checks"])

    def test_gas_check_passes(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_validate_output"]

        output = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(output, gas_limit=10000)

        assert result["status"] == "ok"
        gas_check = next(c for c in result["checks"] if c["name"] == "gas_budget")
        assert gas_check["passed"] is True


class TestHlfCodeExecute:
    def test_compile_error(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        result = fn("totally invalid hlf")

        assert result["status"] == "compile_error"
        assert result["compiled"] is False
        assert "error" in result

    def test_valid_hlf_executes(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert result["compiled"] is True
        assert "hlf_result" in result
        assert "trace_ref" in result

    def test_dry_run_does_not_execute(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source, dry_run=True)

        assert result["status"] == "ok"
        assert result["executed"] is False
        assert "dry_run_ok" in result["hlf_result"]

    def test_gas_limit_enforced(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source, gas_limit=0)

        assert result["status"] == "runtime_error"
        assert "Gas limit exceeded" in result.get("error", "")

    def test_trace_present(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert "trace" in result
        assert "compile" in result["trace"]
        assert "elapsed_ns" in result["trace"]

    def test_returns_hlf_result_block(self, fake_ctx):
        from hlf_mcp.server_native import register_native_tools

        mcp = FakeMcp()
        tools = register_native_tools(mcp, fake_ctx)
        fn = tools["hlf_code_execute"]

        source = '[HLF-v3]\nΔ [INTENT] goal="test"\nΩ\n'
        result = fn(source)

        assert "[RESULT]" in result["hlf_result"]
        assert result["gas_used"] >= 0