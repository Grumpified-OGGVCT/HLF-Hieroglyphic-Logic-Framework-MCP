"""
tests/conftest.py — pytest configuration to prevent Ollama/LLM hangs and
isolate test state across modules.

Strategy:
1. Patch HLFLLMBridge.send to raise RuntimeError by default,
   triggering run_hlf_do's existing fallback to deterministic heuristic
   translation (language_to_hlf). Tests that need live Ollama can use
   the @pytest.mark.requires_ollama marker.
2. Reset shared server session state at session start to prevent
   test-ordering state leaks (knowledge contracts, routing artifacts, etc.).
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


# ── session fixture: reset shared server state ────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _reset_server_state() -> None:
    """Clear shared server session state at test session start.
    
    Prevents test-ordering state leaks where a prior test module's stored
    knowledge contracts, routing artifacts, or benchmark artifacts bleed
    into later test modules that expect clean state.
    """
    try:
        from hlf_mcp import server as _srv
        _ctx = _srv._ctx
        # Clear all session-scoped dicts that accumulate test artifacts
        _ctx.session_profiles.clear()
        _ctx.session_model_catalogs.clear()
        _ctx.session_benchmark_artifacts.clear()
        _ctx.session_translation_contracts.clear()
        _ctx.session_governed_recalls.clear()
        _ctx.session_hks_evaluations.clear()
        _ctx.session_hks_external_compares.clear()
        _ctx.session_hks_weekly_refreshes.clear()
        _ctx.session_internal_workflows.clear()
        _ctx.session_governed_routes.clear()
        _ctx.session_execution_admissions.clear()
        _ctx.session_symbolic_surfaces.clear()
        _ctx.session_swarm_mechanics.clear()
        _ctx.session_media_evidence.clear()
        _ctx.session_dream_cycles.clear()
        _ctx.session_dream_findings.clear()
        _ctx.session_dream_proposals.clear()
        _ctx.governance_events.clear()
        _ctx.handoff_events.clear()
        # Clear the disk-backed memory store (SQLite) to prevent stale
        # HKS exemplars from previous test sessions leaking through
        # routing_evidence queries that filter by allowed_entry_kinds.
        try:
            with _ctx.memory_store._connect() as conn:
                conn.execute("DELETE FROM fact_store")
                conn.commit()
        except Exception:
            pass
    except Exception:
        pass  # server not importable (e.g., during collection without deps)
