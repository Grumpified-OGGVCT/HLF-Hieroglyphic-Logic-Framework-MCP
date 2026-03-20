from __future__ import annotations

import urllib.request
from typing import Any

import pytest


def _valid_bytecode() -> bytes:
    from hlf_mcp.hlf.bytecode import HLFBytecode
    from hlf_mcp.hlf.compiler import HLFCompiler

    source = '[HLF-v3]\nΔ [INTENT] goal="x"\nΩ\n'
    result = HLFCompiler().compile(source)
    return HLFBytecode().encode(result["ast"])


def _raise(exc: Exception):
    def _inner(*_args: Any, **_kwargs: Any) -> None:
        raise exc

    return _inner


class TestRuntimeRiskPaths:
    def test_rejects_short_bytecode(self) -> None:
        from hlf_mcp.hlf.runtime import HlfVM

        result = HlfVM().execute(b"\x00" * 31)
        assert result.code == 1
        assert result.error == "Bytecode too short"
        assert result.gas_used == 0

    def test_rejects_invalid_magic(self) -> None:
        from hlf_mcp.hlf.bytecode import _HEADER_SIZE
        from hlf_mcp.hlf.runtime import HlfVM

        invalid_hlb = b"\x00" * 32 + b"BAD!" + b"\x00" * _HEADER_SIZE
        result = HlfVM().execute(invalid_hlb)
        assert result.code == 1
        assert result.error == "Invalid magic bytes"
        assert result.message == "Invalid magic bytes"

    def test_gas_exhaustion_returns_code_2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.runtime import HlfVM, HlfVMGasExhausted

        vm = HlfVM(max_gas=10)
        monkeypatch.setattr(vm, "_execute_code", _raise(HlfVMGasExhausted("Gas limit exceeded")))
        result = vm.execute(_valid_bytecode())
        assert result.code == 2
        assert result.error == "Gas limit exceeded"
        assert "Gas limit exceeded" in result.message

    def test_runtime_error_is_shaped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.runtime import HLFRuntimeError, HlfVM

        vm = HlfVM(max_gas=10)
        monkeypatch.setattr(vm, "_execute_code", _raise(HLFRuntimeError("Stack underflow")))
        result = vm.execute(_valid_bytecode())
        assert result.code == 1
        assert result.error == "Stack underflow"
        assert isinstance(result.stack, list)

    def test_generic_exception_is_shaped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.runtime import HlfVM

        vm = HlfVM(max_gas=10)
        monkeypatch.setattr(vm, "_execute_code", _raise(Exception("Unexpected error")))
        result = vm.execute(_valid_bytecode())
        assert result.code == 1
        assert result.error == "Unexpected error"

    def test_memory_query_empty_returns_none(self) -> None:
        from hlf_mcp.hlf.runtime import _query_memory_context

        assert _query_memory_context("", {}, []) is None
        assert _query_memory_context("   ", {}, []) is None

    def test_memory_query_invalid_top_k_defaults_to_3(self) -> None:
        from hlf_mcp.hlf.runtime import _query_memory_context

        seen: dict[str, Any] = {}

        def retriever(query: str, top_k: int = 0, topic: str | None = None) -> dict[str, Any]:
            seen["query"] = query
            seen["top_k"] = top_k
            seen["topic"] = topic
            return {"count": 1, "results": [{"content": "ok"}]}

        response = _query_memory_context(
            "hello",
            {"_memory_retriever": retriever, "_memory_context_top_k": "bad"},
            [],
        )
        assert response is not None
        assert seen["top_k"] == 3

    @pytest.mark.parametrize(
        ("raw_top_k", "expected_top_k"),
        [
            (-5, 1),
            (100, 10),
        ],
    )
    def test_memory_query_clamps_top_k(self, raw_top_k: int, expected_top_k: int) -> None:
        from hlf_mcp.hlf.runtime import _query_memory_context

        seen: dict[str, Any] = {}

        def retriever(_query: str, top_k: int = 0, topic: str | None = None) -> list[str]:
            seen["top_k"] = top_k
            return ["a", "b", "c"]

        _query_memory_context(
            "hello",
            {"_memory_retriever": retriever, "_memory_context_top_k": raw_top_k},
            [],
        )
        assert seen["top_k"] == expected_top_k


class TestNetModuleRiskPaths:
    def test_scheme_rejection(self) -> None:
        from hlf_mcp.hlf.stdlib import net_mod

        with pytest.raises(PermissionError, match="scheme"):
            net_mod._validate_url("ftp://example.com/file")

    def test_url_without_host_rejected(self) -> None:
        from hlf_mcp.hlf.stdlib import net_mod

        with pytest.raises(PermissionError, match="no host"):
            net_mod._validate_url("http:///only-path")

    def test_blocked_and_special_addresses_rejected(self) -> None:
        from hlf_mcp.hlf.stdlib import net_mod

        blocked_urls = [
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.1/internal",
            "http://169.254.1.1",
            "http://224.0.0.1",
            "http://127.0.0.1",
        ]
        for url in blocked_urls:
            with pytest.raises(PermissionError):
                net_mod._validate_url(url)

    def test_http_get_validates_before_urlopen(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.stdlib import net_mod

        called: dict[str, bool] = {"urlopen": False}

        def _fake_urlopen(*_args: Any, **_kwargs: Any):
            called["urlopen"] = True
            raise AssertionError("urlopen should not be called for blocked URL")

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
        with pytest.raises(PermissionError):
            net_mod.HTTP_GET("http://169.254.169.254/latest/meta-data")
        assert called["urlopen"] is False

    def test_http_get_and_post_set_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.stdlib import net_mod

        calls: list[dict[str, Any]] = []

        class _Response:
            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_args: Any) -> None:
                pass

            def read(self) -> bytes:
                return b"OK"

        def _fake_urlopen(*args: Any, **kwargs: Any) -> _Response:
            calls.append({"args": args, "kwargs": kwargs})
            return _Response()

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
        net_mod.HTTP_GET("https://example.com")
        net_mod.HTTP_POST("https://example.com", "body")
        assert calls[0]["kwargs"]["timeout"] == 30
        assert calls[1]["kwargs"]["timeout"] == 30


class TestServerCoreCompileErrorShaping:
    def test_hlf_compile_shapes_compile_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.hlf.compiler import CompileError
        from hlf_mcp.server_context import build_server_context
        from hlf_mcp.server_core import register_core_tools

        class DummyMCP:
            def tool(self):
                return lambda fn: fn

        ctx = build_server_context()
        tools = register_core_tools(DummyMCP(), ctx)
        monkeypatch.setattr(
            ctx.compiler, "compile", _raise(CompileError("Syntax error", line=10, col=5))
        )

        result = tools["hlf_compile"]("invalid hlf code")
        assert result["status"] == "error"
        assert result["ast"] is None
        assert result["bytecode_hex"] is None
        assert result["bytecode_size_bytes"] == 0
        assert result["errors"][0]["message"] == "Syntax error"
        assert result["errors"][0]["line"] == 10
        assert result["errors"][0]["col"] == 5

    def test_hlf_compile_shapes_generic_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hlf_mcp.server_context import build_server_context
        from hlf_mcp.server_core import register_core_tools

        class DummyMCP:
            def tool(self):
                return lambda fn: fn

        ctx = build_server_context()
        tools = register_core_tools(DummyMCP(), ctx)
        monkeypatch.setattr(ctx.compiler, "compile", _raise(Exception("Unexpected compiler crash")))

        result = tools["hlf_compile"]("invalid hlf code")
        assert result["status"] == "error"
        assert result["errors"][0]["message"] == "Unexpected compiler crash"
        assert result["errors"][0]["line"] == 0
        assert result["errors"][0]["col"] == 0
