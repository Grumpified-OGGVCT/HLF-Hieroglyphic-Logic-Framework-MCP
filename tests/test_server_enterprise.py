"""
Tests for Commit 9: MCP Auth + Enterprise Tool Registration.

Covers:
  - Auth: token verification, Bearer prefix handling, stdio exemption
  - Enterprise tools: all 8 registrars produce discoverable tools
  - Tool docstrings and parameter annotations
  - Server integration: imports, REGISTERED_TOOLS dict
  - Onboarding doc: enterprise tools section present
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def _clear_token_env():
    """Clear HLF_API_TOKEN for tests that expect no auth."""
    old = os.environ.pop("HLF_API_TOKEN", None)
    yield
    if old is not None:
        os.environ["HLF_API_TOKEN"] = old


@pytest.fixture
def _set_token_env():
    """Set HLF_API_TOKEN to a known value for auth tests."""
    old = os.environ.get("HLF_API_TOKEN")
    os.environ["HLF_API_TOKEN"] = "test-secret-token"
    # Force re-import to reflect the env change
    import hlf_mcp.server_auth as auth_mod
    auth_mod.HLF_API_TOKEN = "test-secret-token"
    auth_mod._auth_required = True
    yield
    if old is not None:
        os.environ["HLF_API_TOKEN"] = old
    else:
        os.environ.pop("HLF_API_TOKEN", None)
    # Reset module state
    auth_mod.HLF_API_TOKEN = old or ""
    auth_mod._auth_required = bool(auth_mod.HLF_API_TOKEN)


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuth:
    """Test Bearer token authentication middleware."""

    def test_no_token_configured_allows_all(self, _clear_token_env):
        """When HLF_API_TOKEN is not set, verify_token returns True for anything."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth._auth_required is False
        assert auth.verify_token(None) is True
        assert auth.verify_token("anything") is True
        assert auth.verify_token("Bearer anything") is True
        assert auth.verify_token("") is True

    def test_valid_token_accepted(self, _set_token_env):
        """When HLF_API_TOKEN is set, the correct token passes."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth._auth_required is True
        assert auth.verify_token("test-secret-token") is True

    def test_invalid_token_rejected(self, _set_token_env):
        """Wrong token is rejected."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth.verify_token("wrong-token") is False

    def test_bearer_prefix_handling(self, _set_token_env):
        """Bearer prefix is stripped before comparison."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth.verify_token("Bearer test-secret-token") is True
        assert auth.verify_token("Bearer wrong-token") is False
        # Extra whitespace after "Bearer " is NOT stripped (strict match)
        assert auth.verify_token("Bearer  test-secret-token") is False

    def test_empty_token_rejected(self, _set_token_env):
        """Empty or None token is rejected when auth is required."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth.verify_token(None) is False
        assert auth.verify_token("") is False

    def test_token_case_sensitive(self, _set_token_env):
        """Token comparison is case-sensitive."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)
        auth = hlf_mcp.server_auth

        assert auth.verify_token("TEST-SECRET-TOKEN") is False
        assert auth.verify_token("test-secret-token") is True


class TestAuthModuleStructure:
    """Verify the auth module exports what server.py expects."""

    def test_module_exports_verify_token(self):
        from hlf_mcp.server_auth import verify_token
        assert callable(verify_token)

    def test_module_exports_auth_middleware(self):
        from hlf_mcp.server_auth import auth_middleware
        assert callable(auth_middleware)

    def test_module_exports_hlf_api_token(self):
        from hlf_mcp.server_auth import HLF_API_TOKEN
        assert isinstance(HLF_API_TOKEN, str)


class TestAuthMiddlewareCreation:
    """Test the Starlette middleware class itself."""

    def test_middleware_class_is_created(self, _set_token_env):
        """_create_auth_middleware returns a middleware class."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)

        middleware_cls = hlf_mcp.server_auth._create_auth_middleware()
        assert middleware_cls is not None

        # Should be a Starlette BaseHTTPMiddleware subclass
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(middleware_cls, BaseHTTPMiddleware)

    def test_middleware_can_be_instantiated(self, _set_token_env):
        """Middleware class can be instantiated."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)

        middleware_cls = hlf_mcp.server_auth._create_auth_middleware()
        app = MagicMock()
        instance = middleware_cls(app)
        assert instance is not None

    def test_auth_middleware_stdio_is_noop(self, _set_token_env):
        """auth_middleware('stdio') does nothing (no Starlette import needed)."""
        import importlib
        import hlf_mcp.server_auth
        importlib.reload(hlf_mcp.server_auth)

        # Should not raise
        hlf_mcp.server_auth.auth_middleware("stdio")


# ═══════════════════════════════════════════════════════════════════════════════
# Enterprise Tool Registration Tests
# ═══════════════════════════════════════════════════════════════════════════════


def _make_mock_mcp():
    """Create a mock FastMCP instance that supports @mcp.tool() decorator."""
    mock = MagicMock()
    # Store tools registered via @mcp.tool()
    mock._registered_tools = {}

    def _tool_decorator(*args, **kwargs):
        """Simulate @mcp.tool() decorator — registers the function."""
        # If called as @mcp.tool() (no args), return a decorator
        # If called as @mcp.tool(fn), decorate fn directly
        if len(args) == 1 and callable(args[0]):
            fn = args[0]
            mock._registered_tools[fn.__name__] = fn
            return fn
        else:
            def decorator(fn):
                mock._registered_tools[fn.__name__] = fn
                return fn
            return decorator

    mock.tool = MagicMock(side_effect=_tool_decorator)
    mock.add_tool = MagicMock()
    return mock


class TestEnterpriseToolsRegistered:
    """Verify all enterprise tool registrars produce discoverable tools."""

    @pytest.fixture
    def enterprise_tools(self):
        """Register enterprise tools with a mock MCP and return the tool dict."""
        from hlf_mcp.server_enterprise import register_enterprise_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = register_enterprise_tools(mock_mcp, mock_ctx)
        return tools, mock_mcp

    def test_evidence_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_evidence_show" in tools
        assert "hlf_evidence_list" in tools
        assert "hlf_evidence_verify" in tools

    def test_merkle_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_merkle_export" in tools
        assert "hlf_merkle_verify" in tools
        assert "hlf_merkle_chain_status" in tools

    def test_secret_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_secret_store" in tools
        assert "hlf_secret_retrieve" in tools
        assert "hlf_secret_rotate" in tools

    def test_ab_test_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_ab_test_define" in tools
        assert "hlf_ab_test_run" in tools
        assert "hlf_ab_test_show" in tools
        assert "hlf_ab_test_list" in tools

    def test_load_test_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_load_test_run" in tools
        assert "hlf_load_test_status" in tools

    def test_hitl_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_hitl_approve" in tools
        assert "hlf_hitl_reject" in tools
        assert "hlf_hitl_list" in tools

    def test_model_version_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_model_version_check" in tools

    def test_chaos_tools_registered(self, enterprise_tools):
        tools, _mock_mcp = enterprise_tools
        assert "hlf_chaos_status" in tools

    def test_all_enterprise_docstrings_non_empty(self, enterprise_tools):
        """Every enterprise tool must have a docstring (agent-facing docs)."""
        tools, _mock_mcp = enterprise_tools
        for name, fn in tools.items():
            assert fn.__doc__, f"Tool {name} is missing a docstring"

    def test_all_enterprise_tools_are_callable(self, enterprise_tools):
        """Every registered tool must be callable."""
        tools, _mock_mcp = enterprise_tools
        for name, fn in tools.items():
            assert callable(fn), f"Tool {name} is not callable"

    def test_enterprise_tool_count(self, enterprise_tools):
        """We expect exactly 20 enterprise tools (from 8 registrars)."""
        tools, _mock_mcp = enterprise_tools
        assert len(tools) == 20, f"Expected 20 enterprise tools, got {len(tools)}: {sorted(tools.keys())}"


class TestEnterpriseToolsBehavior:
    """Test that enterprise tools return structured results (not exceptions)."""

    def test_evidence_show_nonexistent_returns_not_found(self):
        """hlf_evidence_show for nonexistent capsule returns not_found."""
        from hlf_mcp.server_enterprise import _register_evidence_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_evidence_tools(mock_mcp, mock_ctx)

        result = tools["hlf_evidence_show"]("nonexistent-capsule-99999")
        assert result["status"] == "not_found"

    def test_evidence_list_returns_structured(self):
        """hlf_evidence_list returns a dict with traces list."""
        from hlf_mcp.server_enterprise import _register_evidence_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_evidence_tools(mock_mcp, mock_ctx)

        result = tools["hlf_evidence_list"](limit=5)
        assert "status" in result
        assert "traces" in result
        assert isinstance(result["traces"], list)

    def test_evidence_verify_nonexistent_returns_not_found(self):
        """hlf_evidence_verify for nonexistent capsule returns not_found."""
        from hlf_mcp.server_enterprise import _register_evidence_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_evidence_tools(mock_mcp, mock_ctx)

        result = tools["hlf_evidence_verify"]("nonexistent-99999")
        assert result["status"] == "not_found"

    def test_chaos_status_returns_ok(self):
        """hlf_chaos_status always returns ok (read-only status check)."""
        from hlf_mcp.server_enterprise import _register_chaos_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_chaos_tools(mock_mcp, mock_ctx)

        result = tools["hlf_chaos_status"]()
        assert result["status"] == "ok"
        assert result["chaos_tests_passing"] == 15

    def test_load_test_status_returns_ok(self):
        """hlf_load_test_status returns ok with default config."""
        from hlf_mcp.server_enterprise import _register_load_test_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_load_test_tools(mock_mcp, mock_ctx)

        result = tools["hlf_load_test_status"]()
        assert result["status"] == "ok"
        assert "default_config" in result

    def test_ab_test_list_returns_structured(self):
        """hlf_ab_test_list returns a dict with tests list."""
        from hlf_mcp.server_enterprise import _register_ab_test_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_ab_test_tools(mock_mcp, mock_ctx)

        result = tools["hlf_ab_test_list"]()
        assert "status" in result
        assert "tests" in result
        assert isinstance(result["tests"], list)

    def test_ab_test_define_invalid_domain_returns_error(self):
        """hlf_ab_test_define with invalid domain returns error."""
        from hlf_mcp.server_enterprise import _register_ab_test_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_ab_test_tools(mock_mcp, mock_ctx)

        result = tools["hlf_ab_test_define"](
            name="test_invalid",
            domain="nonexistent_domain",
            backends="model1,model2",
        )
        assert result["status"] == "error"

    def test_ab_test_show_nonexistent_returns_error(self):
        """hlf_ab_test_show for nonexistent test returns error."""
        from hlf_mcp.server_enterprise import _register_ab_test_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_ab_test_tools(mock_mcp, mock_ctx)

        result = tools["hlf_ab_test_show"]("nonexistent_test_99999")
        assert result["status"] == "error"

    def test_hitl_list_returns_structured(self):
        """hlf_hitl_list returns a dict with requests list."""
        from hlf_mcp.server_enterprise import _register_hitl_tools
        from hlf_mcp.hlf.hitl_gate import HITLGate

        # Reset the singleton and use a temp dir
        HITLGate.reset_instance()
        import tempfile
        tmpdir = Path(tempfile.mkdtemp(prefix="hitl_enterprise_test_"))

        try:
            gate = HITLGate.get_instance(tmpdir)
            mock_mcp = _make_mock_mcp()
            mock_ctx = MagicMock()
            tools = _register_hitl_tools(mock_mcp, mock_ctx)

            result = tools["hlf_hitl_list"](status="pending")
            assert "status" in result
            assert "requests" in result
            assert isinstance(result["requests"], list)
        finally:
            HITLGate.reset_instance()
            import shutil
            try:
                shutil.rmtree(str(tmpdir), ignore_errors=True)
            except PermissionError:
                pass

    def test_hitl_approve_nonexistent_returns_not_found(self):
        """hlf_hitl_approve for nonexistent capsule returns not_found."""
        from hlf_mcp.server_enterprise import _register_hitl_tools
        from hlf_mcp.hlf.hitl_gate import HITLGate

        HITLGate.reset_instance()
        import tempfile
        tmpdir = Path(tempfile.mkdtemp(prefix="hitl_enterprise_test_"))

        try:
            gate = HITLGate.get_instance(tmpdir)
            mock_mcp = _make_mock_mcp()
            mock_ctx = MagicMock()
            tools = _register_hitl_tools(mock_mcp, mock_ctx)

            result = tools["hlf_hitl_approve"]("nonexistent-capsule-99999")
            assert result["status"] == "not_found"
        finally:
            HITLGate.reset_instance()
            import shutil
            try:
                shutil.rmtree(str(tmpdir), ignore_errors=True)
            except PermissionError:
                pass

    def test_merkle_export_requires_master_key(self):
        """hlf_merkle_export without HLF_MASTER_KEY returns error."""
        from hlf_mcp.server_enterprise import _register_merkle_tools

        old = os.environ.pop("HLF_MASTER_KEY", None)
        try:
            mock_mcp = _make_mock_mcp()
            mock_ctx = MagicMock()
            tools = _register_merkle_tools(mock_mcp, mock_ctx)

            result = tools["hlf_merkle_export"](chains=["latent_traces.jsonl"], output_dir="/tmp")
            assert result["status"] == "error"
        finally:
            if old is not None:
                os.environ["HLF_MASTER_KEY"] = old

    def test_merkle_chain_status_returns_structured(self):
        """hlf_merkle_chain_status returns a dict with chains."""
        from hlf_mcp.server_enterprise import _register_merkle_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_merkle_tools(mock_mcp, mock_ctx)

        result = tools["hlf_merkle_chain_status"]()
        assert "status" in result
        assert "chains" in result
        assert isinstance(result["chains"], dict)

    def test_load_test_run_returns_structured(self):
        """hlf_load_test_run returns metrics dict."""
        from hlf_mcp.server_enterprise import _register_load_test_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_load_test_tools(mock_mcp, mock_ctx)

        result = tools["hlf_load_test_run"]({"capsule_count": 5, "max_rounds": 20})
        assert result["status"] == "ok"
        assert "metrics" in result


class TestSecretTools:
    """Test secret management tool behavior (requires cryptography)."""

    @pytest.fixture(autouse=True)
    def _ensure_master_key(self):
        """Ensure HLF_MASTER_KEY is set for secret tests."""
        old = os.environ.get("HLF_MASTER_KEY")
        os.environ["HLF_MASTER_KEY"] = "test-master-key-for-enterprise"
        yield
        if old is not None:
            os.environ["HLF_MASTER_KEY"] = old
        else:
            os.environ.pop("HLF_MASTER_KEY", None)

    def _skip_if_no_crypto(self):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        except ImportError:
            pytest.skip("cryptography library not available")

    def test_secret_store_and_retrieve(self):
        """Store a secret, then retrieve it."""
        self._skip_if_no_crypto()
        from hlf_mcp.server_enterprise import _register_secret_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_secret_tools(mock_mcp, mock_ctx)

        store_result = tools["hlf_secret_store"](
            key="test_key_1",
            value="my-secret-value-abc",
        )
        assert store_result["status"] == "ok"
        assert "ciphertext_hash" in store_result
        assert len(store_result["ciphertext_hash"]) == 64

        retrieve_result = tools["hlf_secret_retrieve"]("test_key_1")
        assert retrieve_result["status"] == "ok"
        assert retrieve_result["value"] == "my-secret-value-abc"

    def test_secret_retrieve_nonexistent(self):
        """Retrieving a nonexistent secret returns not_found."""
        self._skip_if_no_crypto()
        from hlf_mcp.server_enterprise import _register_secret_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_secret_tools(mock_mcp, mock_ctx)

        result = tools["hlf_secret_retrieve"]("never_stored_key")
        assert result["status"] == "not_found"

    def test_secret_rotate(self):
        """Rotate a secret — old hash != new hash."""
        self._skip_if_no_crypto()
        from hlf_mcp.server_enterprise import _register_secret_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_secret_tools(mock_mcp, mock_ctx)

        tools["hlf_secret_store"](key="rotate_key", value="rotate-me")
        result = tools["hlf_secret_rotate"]("rotate_key")
        assert result["status"] == "ok"
        assert result["old_hash"] != result["new_hash"]

    def test_secret_rotate_nonexistent(self):
        """Rotating nonexistent secret returns not_found."""
        self._skip_if_no_crypto()
        from hlf_mcp.server_enterprise import _register_secret_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_secret_tools(mock_mcp, mock_ctx)

        result = tools["hlf_secret_rotate"]("never_stored_rotate")
        assert result["status"] == "not_found"


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Onboarding Doc Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentOnboarding:
    """Verify the onboarding doc reflects enterprise tools."""

    @pytest.fixture
    def onboarding_text(self):
        path = _REPO_ROOT / "docs" / "HLF_AGENT_ONBOARDING.md"
        if not path.exists():
            pytest.skip("HLF_AGENT_ONBOARDING.md not found")
        return path.read_text(encoding="utf-8")

    def test_onboarding_doc_exists(self):
        path = _REPO_ROOT / "docs" / "HLF_AGENT_ONBOARDING.md"
        assert path.exists(), "HLF_AGENT_ONBOARDING.md must exist"

    def test_onboarding_mentions_enterprise_tools(self, onboarding_text):
        assert "Enterprise Tools" in onboarding_text, (
            "Onboarding doc must have an 'Enterprise Tools' section"
        )

    def test_onboarding_mentions_auth(self, onboarding_text):
        assert "HLF_API_TOKEN" in onboarding_text, (
            "Onboarding doc must mention HLF_API_TOKEN"
        )

    def test_onboarding_mentions_hitl(self, onboarding_text):
        assert "hlf_hitl_approve" in onboarding_text
        assert "hlf_hitl_reject" in onboarding_text
        assert "hlf_hitl_list" in onboarding_text

    def test_onboarding_mentions_evidence(self, onboarding_text):
        assert "hlf_evidence_show" in onboarding_text

    def test_onboarding_mentions_merkle(self, onboarding_text):
        assert "hlf_merkle_export" in onboarding_text

    def test_onboarding_mentions_secrets(self, onboarding_text):
        assert "hlf_secret_store" in onboarding_text

    def test_onboarding_mentions_ab_test(self, onboarding_text):
        assert "hlf_ab_test_define" in onboarding_text

    def test_onboarding_mentions_load_test(self, onboarding_text):
        assert "hlf_load_test_run" in onboarding_text

    def test_onboarding_mentions_chaos(self, onboarding_text):
        assert "hlf_chaos_status" in onboarding_text

    def test_onboarding_mentions_274_tests(self, onboarding_text):
        assert "274" in onboarding_text, (
            "Onboarding doc must mention 'All 274 tests pass'"
        )

    def test_onboarding_mentions_transport_auth(self, onboarding_text):
        assert "HTTP transport" in onboarding_text.lower() or "sse" in onboarding_text.lower(), (
            "Onboarding should mention that auth applies to HTTP transports"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Server Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestServerIntegration:
    """Verify server.py correctly imports and wires enterprise modules."""

    def test_server_imports_enterprise_module(self):
        """server.py must import register_enterprise_tools."""
        # Read the server.py source
        server_path = _REPO_ROOT / "hlf_mcp" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        assert "from hlf_mcp.server_enterprise import register_enterprise_tools" in source

    def test_server_imports_auth_module(self):
        """server.py must import auth_middleware and HLF_API_TOKEN."""
        server_path = _REPO_ROOT / "hlf_mcp" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        assert "from hlf_mcp.server_auth import" in source

    def test_enterprise_tools_in_registered_dict(self):
        """REGISTERED_TOOLS must include enterprise tools after registration."""
        # Check the source for REGISTERED_TOOLS.update(register_enterprise_tools(...))
        server_path = _REPO_ROOT / "hlf_mcp" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        assert "register_enterprise_tools(mcp, _ctx)" in source

    def test_auth_middleware_called_before_stdio(self):
        """auth_middleware must be called for HTTP transports before mcp.run()."""
        server_path = _REPO_ROOT / "hlf_mcp" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        assert "auth_middleware(transport)" in source

    def test_enterprise_registration_after_handoff(self):
        """Enterprise tools should be registered after handoff tools (order matters)."""
        server_path = _REPO_ROOT / "hlf_mcp" / "server.py"
        source = server_path.read_text(encoding="utf-8")
        # Find the positions
        handoff_pos = source.find("register_handoff_tools(mcp, _ctx)")
        enterprise_pos = source.find("register_enterprise_tools(mcp, _ctx)")
        assert handoff_pos > 0, "register_handoff_tools not found in server.py"
        assert enterprise_pos > 0, "register_enterprise_tools not found in server.py"
        assert enterprise_pos > handoff_pos, (
            "Enterprise tools must be registered AFTER handoff tools"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Model Version Tool Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelVersionTool:
    """Test model version check tool behavior."""

    def test_model_version_check_with_empty_manifest(self):
        """Empty model_versions returns ok with zero models."""
        from hlf_mcp.server_enterprise import _register_model_version_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_model_version_tools(mock_mcp, mock_ctx)

        result = tools["hlf_model_version_check"]({"model_versions": {}})
        assert result["status"] == "ok"
        assert result["model_count"] == 0

    def test_model_version_check_no_live_data(self):
        """When no live models available, returns trust-mode (no violations)."""
        from hlf_mcp.server_enterprise import _register_model_version_tools

        mock_mcp = _make_mock_mcp()
        mock_ctx = MagicMock()
        tools = _register_model_version_tools(mock_mcp, mock_ctx)

        result = tools["hlf_model_version_check"]({
            "model_versions": {
                "llama3.2:latest": "abc123def4567890" * 4,
            }
        })
        assert result["status"] == "ok"
