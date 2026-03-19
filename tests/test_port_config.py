import pytest

from hlf.mcp_client import HLFMCPClient, resolve_mcp_url
from hlf_mcp.server import _get_http_bind


def test_resolve_mcp_url_prefers_explicit_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_URL", "http://env.example")

    assert resolve_mcp_url("http://explicit.example") == "http://explicit.example"


def test_resolve_mcp_url_reads_namespaced_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_URL", raising=False)
    monkeypatch.setenv("HLF_MCP_URL", "http://env.example")

    assert resolve_mcp_url() == "http://env.example"


def test_resolve_mcp_url_requires_explicit_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HLF_MCP_URL", raising=False)
    monkeypatch.delenv("MCP_URL", raising=False)

    with pytest.raises(ValueError, match="MCP URL must be provided explicitly"):
        resolve_mcp_url()


def test_client_uses_environment_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_URL", "http://env.example")

    client = HLFMCPClient()

    assert client.base_url == "http://env.example"


def test_http_bind_requires_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HLF_PORT", raising=False)

    with pytest.raises(RuntimeError, match="HLF_PORT must be set explicitly"):
        _get_http_bind()


def test_http_bind_validates_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLF_PORT", "70000")

    with pytest.raises(RuntimeError, match="between 1 and 65535"):
        _get_http_bind()


def test_http_bind_returns_explicit_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HLF_HOST", "127.0.0.1")
    monkeypatch.setenv("HLF_PORT", "8123")

    assert _get_http_bind() == ("127.0.0.1", 8123)
