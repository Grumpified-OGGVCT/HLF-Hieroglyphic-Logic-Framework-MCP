"""
tests/conftest.py — pytest configuration to prevent Ollama/LLM hangs.

Strategy: Patch HLFLLMBridge.send to raise RuntimeError by default,
triggering run_hlf_do's existing fallback to deterministic heuristic
translation (language_to_hlf). Tests that need live Ollama can use
the @pytest.mark.requires_ollama marker.

The existing try/except Exception in run_hlf_do (server_translation.py:430)
catches this RuntimeError and falls through to language_to_hlf(), which
is fast, deterministic, and requires no network.
"""

from __future__ import annotations

import inspect
import pytest


# ── markers ────────────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_ollama: mark test as requiring a live Ollama instance "
        "(skipped by default unless --run-ollama is passed)",
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-ollama",
        action="store_true",
        default=False,
        help="Run tests that require a live Ollama instance",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-ollama"):
        return  # allow all tests
    skip_ollama = pytest.mark.skip(reason="Ollama not available (use --run-ollama to enable)")
    for item in items:
        if "requires_ollama" in item.keywords:
            item.add_marker(skip_ollama)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    """Run async test functions via asyncio.run so pytest-asyncio is not required."""
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        import asyncio
        import inspect as _inspect
        sig = _inspect.signature(pyfuncitem.obj)
        params = set(sig.parameters)
        kwargs = {k: v for k, v in pyfuncitem.funcargs.items() if k in params}
        coro = pyfuncitem.obj(**kwargs)
        asyncio.run(coro)
        return True
    return None


# ── autouse fixture: block real Ollama calls ──────────────────────────────────

@pytest.fixture(autouse=True)
def _block_live_ollama(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Patch HLFLLMBridge.send to fail fast so tests use heuristic fallback.

    Tests marked @pytest.mark.requires_ollama are excluded from this patch
    and will talk to a real Ollama instance.
    """
    if "requires_ollama" in request.node.keywords:
        return  # allow live Ollama for explicitly marked tests

    async def _fake_send(
        _self: object,
        prompt: str,
        *,
        role: str = "agent",
        system: str = "",
        model: str | None = None,
        session: object = None,
    ) -> object:
        raise RuntimeError(
            "Test mode: HLFLLMBridge.send is patched to prevent Ollama hangs. "
            "Use @pytest.mark.requires_ollama and --run-ollama for live tests."
        )

    monkeypatch.setattr(
        "hlf_mcp.hlf.hlf_llm_bridge.HLFLLMBridge.send",
        _fake_send,
    )
