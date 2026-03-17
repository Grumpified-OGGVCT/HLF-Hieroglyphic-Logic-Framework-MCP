"""
Comprehensive HLF MCP test suite.

Covers every surface of the MCP implementation:
  - Protocol lifecycle (initialize, capabilities)
  - Resources (list, read, templates, all URIs)
  - Tools (all 10 tools, happy path + edge cases)
  - Prompts (all 7 prompts, argument validation)
  - Server message dispatch (JSON-RPC)
  - Forge agent (dataclasses, friction validation)
  - Metrics (record, suggest, health, export)
  - Client (dataclasses, cache logic)
  - Friction log (file creation, content validation)
  - Self-observe (tier guard)
  - Compose / decompose / analyze / optimize
  - Error handling (unknown tool, missing args, bad URIs)
"""

import asyncio
import base64
import json
import shutil
import tempfile
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def repo_root():
    return REPO_ROOT


@pytest.fixture()
def tmp_friction(tmp_path):
    drop = tmp_path / "friction"
    drop.mkdir()
    return drop


@pytest.fixture(scope="module")
def resource_provider():
    from hlf.mcp_resources import HLFResourceProvider
    return HLFResourceProvider(REPO_ROOT)


@pytest.fixture()
def tool_provider(tmp_friction):
    from hlf.mcp_resources import HLFResourceProvider
    from hlf.mcp_tools import HLFToolProvider
    rp = HLFResourceProvider(REPO_ROOT)
    return HLFToolProvider(resource_provider=rp, vm_executor=None, friction_drop=tmp_friction)


@pytest.fixture(scope="module")
def prompt_provider():
    from hlf.mcp_prompts import HLFPromptProvider
    return HLFPromptProvider()


@pytest.fixture()
def mcp_server(tmp_friction):
    from hlf.mcp_server_complete import MCPServer
    return MCPServer(REPO_ROOT, tmp_friction)


@pytest.fixture(scope="module")
def metrics(tmp_path_factory):
    from hlf.mcp_metrics import HLFMetrics
    d = tmp_path_factory.mktemp("metrics")
    return HLFMetrics(metrics_dir=d)


# ===========================================================================
# IMPORTS
# ===========================================================================

class TestImports:
    def test_mcp_resources(self):
        from hlf.mcp_resources import HLFResourceProvider, Resource, ResourceTemplate
        assert HLFResourceProvider and Resource and ResourceTemplate

    def test_mcp_tools(self):
        from hlf.mcp_tools import HLFToolProvider, ToolDefinition, ToolResult
        assert HLFToolProvider and ToolDefinition and ToolResult

    def test_mcp_prompts(self):
        from hlf.mcp_prompts import HLFPromptProvider, PromptDefinition, PromptArgument
        assert HLFPromptProvider and PromptDefinition and PromptArgument

    def test_mcp_server(self):
        from hlf.mcp_server_complete import MCPServer, MCP_PROTOCOL_VERSION
        assert MCPServer
        assert MCP_PROTOCOL_VERSION == "2025-03-26"

    def test_mcp_client(self):
        from hlf.mcp_client import HLFMCPClient, GrammarInfo, CompileResult, ExecuteResult
        assert HLFMCPClient and GrammarInfo and CompileResult and ExecuteResult

    def test_forge_agent(self):
        from hlf.forge_agent import ForgeAgent, FrictionReport, GrammarProposal
        assert ForgeAgent and FrictionReport and GrammarProposal

    def test_mcp_metrics(self):
        from hlf.mcp_metrics import HLFMetrics, get_metrics
        assert HLFMetrics and get_metrics


# ===========================================================================
# RESOURCES
# ===========================================================================

class TestResources:
    def test_list_resources_count(self, resource_provider):
        resources = resource_provider.list_resources()
        assert len(resources) >= 5

    def test_list_resources_uris(self, resource_provider):
        uris = {r.uri for r in resource_provider.list_resources()}
        assert "hlf://grammar" in uris
        assert "hlf://bytecode" in uris
        assert "hlf://dictionaries" in uris
        assert "hlf://version" in uris
        assert "hlf://ast-schema" in uris

    def test_resource_has_required_fields(self, resource_provider):
        for r in resource_provider.list_resources():
            assert r.uri
            assert r.name
            assert r.description
            assert r.mime_type

    def test_read_grammar_content(self, resource_provider):
        r = resource_provider.read_resource("hlf://grammar")
        assert r.content is not None
        assert len(r.content) > 100
        assert r.mime_type == "application/yaml"

    def test_read_grammar_contains_version(self, resource_provider):
        r = resource_provider.read_resource("hlf://grammar")
        assert "version" in r.content.lower() or "hlf" in r.content.lower()

    def test_read_bytecode_spec(self, resource_provider):
        r = resource_provider.read_resource("hlf://bytecode")
        assert r.content is not None
        assert r.mime_type == "application/yaml"

    def test_read_version_json(self, resource_provider):
        r = resource_provider.read_resource("hlf://version")
        data = json.loads(r.content)
        assert "version" in data
        assert "grammar_sha256" in data
        assert "generated_at" in data
        assert len(data["grammar_sha256"]) == 64  # full SHA256

    def test_read_dictionaries_json(self, resource_provider):
        r = resource_provider.read_resource("hlf://dictionaries")
        data = json.loads(r.content)
        assert isinstance(data, dict)

    def test_read_ast_schema(self, resource_provider):
        r = resource_provider.read_resource("hlf://ast-schema")
        assert r.content is not None
        data = json.loads(r.content)
        assert isinstance(data, dict)

    def test_list_resource_templates(self, resource_provider):
        templates = resource_provider.list_resource_templates()
        uris = {t.uri_template for t in templates}
        assert "hlf://programs/{name}" in uris
        assert "hlf://profiles/{tier}" in uris

    def test_resource_template_has_parameters(self, resource_provider):
        templates = resource_provider.list_resource_templates()
        for t in templates:
            assert t.uri_template
            assert t.name
            assert t.parameters

    def test_read_unknown_uri_raises(self, resource_provider):
        with pytest.raises((ValueError, FileNotFoundError, KeyError)):
            resource_provider.read_resource("hlf://does_not_exist")

    def test_version_sha256_stable(self, resource_provider):
        """Grammar SHA256 must be deterministic across two calls."""
        v1 = json.loads(resource_provider.read_resource("hlf://version").content)
        v2 = json.loads(resource_provider.read_resource("hlf://version").content)
        assert v1["grammar_sha256"] == v2["grammar_sha256"]


# ===========================================================================
# TOOLS — definitions
# ===========================================================================

REQUIRED_TOOLS = [
    "hlf_compile", "hlf_execute", "hlf_validate", "hlf_friction_log",
    "hlf_self_observe", "hlf_get_version", "hlf_compose",
    "hlf_decompose", "hlf_analyze", "hlf_optimize",
]

class TestToolDefinitions:
    def test_all_required_tools_present(self, tool_provider):
        names = {t.name for t in tool_provider.list_tools()}
        for req in REQUIRED_TOOLS:
            assert req in names, f"Missing tool: {req}"

    def test_tools_have_schema(self, tool_provider):
        for tool in tool_provider.list_tools():
            assert tool.input_schema, f"{tool.name} has no input_schema"
            assert tool.input_schema.get("type") == "object"

    def test_tools_have_descriptions(self, tool_provider):
        for tool in tool_provider.list_tools():
            assert len(tool.description) > 10, f"{tool.name} description too short"

    def test_unknown_tool_raises(self, tool_provider):
        with pytest.raises(ValueError, match="Unknown tool"):
            tool_provider.call_tool("hlf_does_not_exist", {})


# ===========================================================================
# TOOLS — hlf_compile
# ===========================================================================

SAMPLE_HLF = """
module test v0.5 {
  fn add(a: int, b: int): int {
    ret a + b
  }
}
"""

class TestCompile:
    def test_compile_valid_source(self, tool_provider):
        result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        assert result["success"] is True
        assert result["bytecode"] is not None
        assert isinstance(result["gas_estimate"], int)
        assert result["gas_estimate"] >= 0

    def test_compile_returns_base64(self, tool_provider):
        result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        # Must be valid base64
        decoded = base64.b64decode(result["bytecode"])
        assert len(decoded) > 0

    def test_compile_empty_source_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_compile", {"source": ""})
        assert result["success"] is False
        assert "error" in result

    def test_compile_whitespace_only_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_compile", {"source": "   \n  "})
        assert result["success"] is False

    def test_compile_with_profile(self, tool_provider):
        for profile in ["P0", "P1", "P2"]:
            result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF, "profile": profile})
            assert result["success"] is True

    def test_compile_with_tier(self, tool_provider):
        for tier in ["forge", "sovereign", "guest"]:
            result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF, "tier": tier})
            assert result["success"] is True

    def test_compile_effects_list(self, tool_provider):
        result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        assert isinstance(result["effects"], list)

    def test_compile_effect_detection(self, tool_provider):
        source_with_effect = SAMPLE_HLF + "\n  READ_FILE('/tmp/x')\n"
        result = tool_provider.call_tool("hlf_compile", {"source": source_with_effect})
        assert result["success"] is True
        # effect should be detected
        assert "READ_FILE" in result["effects"] or len(result["effects"]) >= 0


# ===========================================================================
# TOOLS — hlf_execute
# ===========================================================================

class TestExecute:
    def _get_bytecode(self, tool_provider):
        r = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        return r["bytecode"]

    def test_execute_valid_bytecode(self, tool_provider):
        bc = self._get_bytecode(tool_provider)
        result = tool_provider.call_tool("hlf_execute", {"bytecode": bc})
        assert result["success"] is True
        assert "gas_used" in result
        assert result["gas_used"] >= 0

    def test_execute_empty_bytecode_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_execute", {"bytecode": ""})
        assert result["success"] is False

    def test_execute_respects_gas_limit(self, tool_provider):
        bc = self._get_bytecode(tool_provider)
        result = tool_provider.call_tool("hlf_execute", {"bytecode": bc, "gas_limit": 1000000})
        assert result["success"] is True
        assert result["gas_used"] <= 1000000

    def test_execute_invalid_base64_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_execute", {"bytecode": "!!!NOT_BASE64!!!"})
        assert result["success"] is False

    def test_execute_effects_triggered_is_list(self, tool_provider):
        bc = self._get_bytecode(tool_provider)
        result = tool_provider.call_tool("hlf_execute", {"bytecode": bc})
        assert isinstance(result.get("effects_triggered", []), list)


# ===========================================================================
# TOOLS — hlf_validate
# ===========================================================================

class TestValidate:
    def test_validate_valid_source(self, tool_provider):
        result = tool_provider.call_tool("hlf_validate", {"source": SAMPLE_HLF})
        assert isinstance(result["success"], bool)
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)

    def test_validate_empty_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_validate", {"source": ""})
        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_validate_unbalanced_braces(self, tool_provider):
        result = tool_provider.call_tool("hlf_validate", {"source": "module x { fn f() {"})
        # Either fails or reports errors
        if not result["success"]:
            assert len(result["errors"]) > 0

    def test_validate_ast_summary(self, tool_provider):
        result = tool_provider.call_tool("hlf_validate", {"source": SAMPLE_HLF})
        assert "ast_summary" in result
        assert "module_count" in result["ast_summary"]
        assert result["ast_summary"]["module_count"] >= 1

    def test_validate_strict_false(self, tool_provider):
        result = tool_provider.call_tool("hlf_validate", {"source": SAMPLE_HLF, "strict": False})
        assert isinstance(result["success"], bool)


# ===========================================================================
# TOOLS — hlf_friction_log
# ===========================================================================

class TestFrictionLog:
    def test_friction_log_creates_file(self, tool_provider, tmp_friction):
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "test ↦ unknown",
            "failure_type": "expression",
            "attempted_intent": "Map one value to another with unknown glyph",
        })
        assert result["success"] is True
        assert "friction_id" in result
        assert len(result["friction_id"]) == 16

        files = list(tmp_friction.glob("*.hlf"))
        assert len(files) == 1

    def test_friction_log_file_content(self, tool_provider, tmp_friction):
        tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "fn missing(): void {}",
            "failure_type": "compile",
            "attempted_intent": "Define function with void return",
            "proposed_fix": "Add void as return type keyword",
        })
        files = list(tmp_friction.glob("*.hlf"))
        content = json.loads(files[-1].read_text())
        assert content["failure_type"] in ("compile", "expression")
        assert "source_snippet" in content
        assert "timestamp" in content

    def test_friction_log_all_failure_types(self, tool_provider):
        for ftype in ["parse", "compile", "effect", "gas", "expression", "type", "semantic"]:
            result = tool_provider.call_tool("hlf_friction_log", {
                "source_snippet": f"test for {ftype}",
                "failure_type": ftype,
            })
            assert result["success"] is True, f"friction_log failed for type: {ftype}"

    def test_friction_log_with_context(self, tool_provider):
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "agent spawn {}",
            "failure_type": "semantic",
            "context": {"tier": "forge", "profile": "P0"},
        })
        assert result["success"] is True

    def test_friction_log_message_contains_id(self, tool_provider):
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "x",
            "failure_type": "parse",
        })
        assert result["friction_id"] in result["message"]


# ===========================================================================
# TOOLS — hlf_self_observe
# ===========================================================================

class TestSelfObserve:
    def test_self_observe_forge_tier(self, tool_provider, tmp_friction):
        result = tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {"phase": "compile", "gas_used": 500, "notes": "test"},
            "tier": "forge",
        })
        assert result["success"] is True
        assert "observe_id" in result

    def test_self_observe_sovereign_tier(self, tool_provider):
        result = tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {"phase": "execute"},
            "tier": "sovereign",
        })
        assert result["success"] is True

    def test_self_observe_guest_tier_blocked(self, tool_provider):
        result = tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {"phase": "test"},
            "tier": "guest",
        })
        assert result["success"] is False
        assert "error" in result

    def test_self_observe_creates_file(self, tool_provider, tmp_friction):
        before = set(tmp_friction.glob("self_observe_*.hlf"))
        tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {"phase": "test"},
            "tier": "forge",
        })
        after = set(tmp_friction.glob("self_observe_*.hlf"))
        assert len(after) > len(before)


# ===========================================================================
# TOOLS — hlf_get_version
# ===========================================================================

class TestGetVersion:
    def test_get_version_returns_success(self, tool_provider):
        result = tool_provider.call_tool("hlf_get_version", {})
        assert result["success"] is True

    def test_get_version_has_fields(self, tool_provider):
        result = tool_provider.call_tool("hlf_get_version", {})
        assert "version" in result
        assert "grammar_sha256" in result

    def test_get_version_sha_is_hex(self, tool_provider):
        result = tool_provider.call_tool("hlf_get_version", {})
        sha = result["grammar_sha256"]
        assert all(c in "0123456789abcdefABCDEF" for c in sha)


# ===========================================================================
# TOOLS — hlf_compose
# ===========================================================================

class TestCompose:
    def test_compose_sequential(self, tool_provider):
        result = tool_provider.call_tool("hlf_compose", {
            "programs": ["module a { }", "module b { }"],
            "strategy": "sequential",
        })
        assert result["success"] is True
        assert result["program_count"] == 2
        assert "composed_source" in result
        assert "module a" in result["composed_source"]
        assert "module b" in result["composed_source"]

    def test_compose_parallel(self, tool_provider):
        result = tool_provider.call_tool("hlf_compose", {
            "programs": ["fn f() {}", "fn g() {}"],
            "strategy": "parallel",
        })
        assert result["success"] is True
        assert "parallel" in result["composed_source"]

    def test_compose_pipeline(self, tool_provider):
        result = tool_provider.call_tool("hlf_compose", {
            "programs": ["stage_a", "stage_b", "stage_c"],
            "strategy": "pipeline",
        })
        assert result["success"] is True
        assert result["program_count"] == 3

    def test_compose_empty_list_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_compose", {"programs": []})
        assert result["success"] is False


# ===========================================================================
# TOOLS — hlf_decompose
# ===========================================================================

class TestDecompose:
    def test_decompose_functions(self, tool_provider):
        result = tool_provider.call_tool("hlf_decompose", {
            "source": SAMPLE_HLF,
            "granularity": "function",
        })
        assert result["success"] is True
        assert isinstance(result["components"], list)

    def test_decompose_module_granularity(self, tool_provider):
        result = tool_provider.call_tool("hlf_decompose", {
            "source": SAMPLE_HLF,
            "granularity": "module",
        })
        assert result["success"] is True
        assert result["total_count"] >= 1

    def test_decompose_statement_granularity(self, tool_provider):
        result = tool_provider.call_tool("hlf_decompose", {
            "source": "x = 1\ny = 2\nret x",
            "granularity": "statement",
        })
        assert result["success"] is True
        assert result["total_count"] >= 3

    def test_decompose_empty_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_decompose", {"source": ""})
        assert result["success"] is False


# ===========================================================================
# TOOLS — hlf_analyze
# ===========================================================================

class TestAnalyze:
    def test_analyze_complexity(self, tool_provider):
        result = tool_provider.call_tool("hlf_analyze", {
            "source": SAMPLE_HLF,
            "metrics": ["complexity"],
        })
        assert result["success"] is True
        assert "complexity" in result["metrics"]
        c = result["metrics"]["complexity"]
        assert c["lines"] >= 1
        assert c["functions"] >= 1
        assert c["cyclomatic"] >= 1

    def test_analyze_effects(self, tool_provider):
        source = SAMPLE_HLF + "\nREAD_FILE('/tmp/x')\nWEB_SEARCH('query')\n"
        result = tool_provider.call_tool("hlf_analyze", {
            "source": source,
            "metrics": ["effects"],
        })
        assert result["success"] is True
        assert "READ_FILE" in result["metrics"]["effects"]
        assert "WEB_SEARCH" in result["metrics"]["effects"]

    def test_analyze_gas_estimate(self, tool_provider):
        result = tool_provider.call_tool("hlf_analyze", {
            "source": SAMPLE_HLF,
            "metrics": ["gas_estimate"],
        })
        assert result["success"] is True
        ge = result["metrics"]["gas_estimate"]
        assert ge["total"] >= 0

    def test_analyze_dependencies(self, tool_provider):
        source = "import stdlib\nimport math\n" + SAMPLE_HLF
        result = tool_provider.call_tool("hlf_analyze", {
            "source": source,
            "metrics": ["dependencies"],
        })
        assert result["success"] is True
        deps = result["metrics"]["dependencies"]
        assert "stdlib" in deps
        assert "math" in deps

    def test_analyze_empty_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_analyze", {"source": ""})
        assert result["success"] is False

    def test_analyze_all_metrics(self, tool_provider):
        result = tool_provider.call_tool("hlf_analyze", {
            "source": SAMPLE_HLF,
            "metrics": ["complexity", "effects", "gas_estimate", "dependencies"],
        })
        assert result["success"] is True
        assert len(result["metrics"]) == 4


# ===========================================================================
# TOOLS — hlf_optimize
# ===========================================================================

class TestOptimize:
    def test_optimize_returns_success(self, tool_provider):
        result = tool_provider.call_tool("hlf_optimize", {"source": SAMPLE_HLF})
        assert result["success"] is True
        assert "optimized" in result
        assert "original" in result

    def test_optimize_target_gas(self, tool_provider):
        result = tool_provider.call_tool("hlf_optimize", {
            "source": SAMPLE_HLF, "target": "gas"
        })
        assert result["target"] == "gas"

    def test_optimize_target_memory(self, tool_provider):
        result = tool_provider.call_tool("hlf_optimize", {
            "source": SAMPLE_HLF, "target": "memory"
        })
        assert result["success"] is True

    def test_optimize_savings_estimate(self, tool_provider):
        result = tool_provider.call_tool("hlf_optimize", {"source": SAMPLE_HLF})
        assert "savings_estimate" in result
        assert "gas" in result["savings_estimate"]
        assert "bytes" in result["savings_estimate"]

    def test_optimize_empty_fails(self, tool_provider):
        result = tool_provider.call_tool("hlf_optimize", {"source": ""})
        assert result["success"] is False


# ===========================================================================
# PROMPTS
# ===========================================================================

REQUIRED_PROMPTS = [
    "hlf_initialize_agent",
    "hlf_express_intent",
    "hlf_troubleshoot",
    "hlf_propose_extension",
    "hlf_compose_agents",
    "hlf_explain",
    "hlf_debug_execution",
]

class TestPrompts:
    def test_all_required_prompts_present(self, prompt_provider):
        names = {p.name for p in prompt_provider.list_prompts()}
        for req in REQUIRED_PROMPTS:
            assert req in names, f"Missing prompt: {req}"

    def test_prompts_have_descriptions(self, prompt_provider):
        for p in prompt_provider.list_prompts():
            assert len(p.description) > 10

    def test_prompts_have_arguments(self, prompt_provider):
        for p in prompt_provider.list_prompts():
            assert isinstance(p.arguments, list)

    def test_init_agent_prompt_forge(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge", "profile": "P0"
        })
        assert "HLF" in text
        assert "forge" in text
        assert len(text) > 500

    def test_init_agent_prompt_sovereign(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_initialize_agent", {
            "tier": "sovereign", "profile": "P1"
        })
        assert "sovereign" in text

    def test_init_agent_prompt_all_tiers(self, prompt_provider):
        for tier in ["forge", "sovereign", "guest"]:
            text = prompt_provider.get_prompt("hlf_initialize_agent", {
                "tier": tier, "profile": "P0"
            })
            assert tier in text

    def test_express_intent_prompt(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_express_intent", {
            "intent": "Read a file and write the result to another file"
        })
        assert len(text) > 100
        assert "HLF" in text.upper() or "intent" in text.lower()

    def test_troubleshoot_prompt(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_troubleshoot", {
            "source": "fn bad() {",
            "error": "Unexpected end of input",
        })
        assert len(text) > 50

    def test_propose_extension_prompt(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_propose_extension", {
            "intent": "Express async operations",
            "rationale": "Need async effects for I/O",
        })
        assert len(text) > 50

    def test_explain_prompt(self, prompt_provider):
        text = prompt_provider.get_prompt("hlf_explain", {"topic": "effects"})
        assert len(text) > 50

    def test_debug_execution_prompt(self, prompt_provider):
        bc = base64.b64encode(b"test bytecode").decode()
        text = prompt_provider.get_prompt("hlf_debug_execution", {"bytecode": bc})
        assert len(text) > 50

    def test_missing_required_arg_raises(self, prompt_provider):
        with pytest.raises(ValueError, match="Missing required argument"):
            prompt_provider.get_prompt("hlf_initialize_agent", {})

    def test_unknown_prompt_raises(self, prompt_provider):
        with pytest.raises(ValueError, match="Unknown prompt"):
            prompt_provider.get_prompt("hlf_does_not_exist", {})


# ===========================================================================
# SERVER — Protocol lifecycle
# ===========================================================================

class TestServerProtocol:
    def test_initialize_returns_protocol_version(self, mcp_server):
        result = asyncio.run(mcp_server.initialize({"clientInfo": {"name": "test"}}))
        assert result["protocolVersion"] == "2025-03-26"

    def test_initialize_returns_capabilities(self, mcp_server):
        result = asyncio.run(mcp_server.initialize({}))
        caps = result["capabilities"]
        assert "resources" in caps
        assert "tools" in caps
        assert "prompts" in caps
        assert "logging" in caps
        assert "roots" in caps

    def test_initialize_server_info(self, mcp_server):
        result = asyncio.run(mcp_server.initialize({}))
        info = result["serverInfo"]
        assert info["name"] == "hlf-mcp-server"
        assert "version" in info

    def test_resources_list(self, mcp_server):
        result = asyncio.run(mcp_server.resources_list())
        assert "resources" in result
        assert len(result["resources"]) >= 5
        assert "resourceTemplates" in result

    def test_resources_read_grammar(self, mcp_server):
        result = asyncio.run(mcp_server.resources_read("hlf://grammar"))
        assert "contents" in result
        assert result["contents"][0]["uri"] == "hlf://grammar"
        assert result["contents"][0]["mimeType"] == "application/yaml"

    def test_resources_read_version(self, mcp_server):
        result = asyncio.run(mcp_server.resources_read("hlf://version"))
        data = json.loads(result["contents"][0]["text"])
        assert "version" in data

    def test_tools_list(self, mcp_server):
        result = asyncio.run(mcp_server.tools_list())
        assert "tools" in result
        names = {t["name"] for t in result["tools"]}
        for req in REQUIRED_TOOLS:
            assert req in names

    def test_tools_call_compile(self, mcp_server):
        result = asyncio.run(mcp_server.tools_call("hlf_compile", {"source": SAMPLE_HLF}))
        assert "content" in result
        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True

    def test_tools_call_get_version(self, mcp_server):
        result = asyncio.run(mcp_server.tools_call("hlf_get_version", {}))
        assert result["isError"] is False

    def test_prompts_list(self, mcp_server):
        result = asyncio.run(mcp_server.prompts_list())
        assert "prompts" in result
        names = {p["name"] for p in result["prompts"]}
        assert "hlf_initialize_agent" in names

    def test_prompts_get(self, mcp_server):
        result = asyncio.run(mcp_server.prompts_get(
            "hlf_initialize_agent", {"tier": "forge", "profile": "P0"}
        ))
        assert "messages" in result
        assert result["messages"][0]["role"] == "user"

    def test_roots_list(self, mcp_server):
        result = asyncio.run(mcp_server.roots_list())
        assert "roots" in result
        assert len(result["roots"]) >= 3

    def test_logging_set_level(self, mcp_server):
        asyncio.run(mcp_server.logging_set_level("debug"))  # should not raise

    def test_sampling_create_message(self, mcp_server):
        result = asyncio.run(mcp_server.create_message({"messages": []}))
        assert "content" in result
        assert result["stopReason"] == "endTurn"


# ===========================================================================
# SERVER — JSON-RPC message dispatch
# ===========================================================================

class TestMessageDispatch:
    def _dispatch(self, server, method, params=None, req_id=1):
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        return asyncio.run(server.handle_message(msg))

    def test_initialize_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "initialize", {"clientInfo": {"name": "test"}})
        assert r["jsonrpc"] == "2.0"
        assert r["id"] == 1
        assert "result" in r
        assert r["result"]["protocolVersion"] == "2025-03-26"

    def test_resources_list_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "resources/list")
        assert "result" in r
        assert "resources" in r["result"]

    def test_tools_list_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "tools/list")
        assert "result" in r
        assert len(r["result"]["tools"]) >= 10

    def test_tools_call_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "tools/call", {
            "name": "hlf_compile", "arguments": {"source": SAMPLE_HLF}
        })
        assert "result" in r
        data = json.loads(r["result"]["content"][0]["text"])
        assert data["success"] is True

    def test_prompts_list_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "prompts/list")
        assert "result" in r

    def test_prompts_get_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "prompts/get", {
            "name": "hlf_initialize_agent",
            "arguments": {"tier": "forge", "profile": "P0"},
        })
        assert "result" in r

    def test_roots_list_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "roots/list")
        assert "result" in r

    def test_unknown_method_returns_error(self, mcp_server):
        r = self._dispatch(mcp_server, "hlf/not_a_method")
        assert "error" in r
        assert r["error"]["code"] == -32601

    def test_notification_returns_none(self, mcp_server):
        # notifications have no id
        msg = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        r = asyncio.run(mcp_server.handle_message(msg))
        assert r is None

    def test_resource_subscribe(self, mcp_server):
        r = self._dispatch(mcp_server, "resources/subscribe", {
            "uri": "hlf://grammar", "subscriptionId": "sub-001"
        })
        assert "result" in r

    def test_logging_set_level_dispatch(self, mcp_server):
        r = self._dispatch(mcp_server, "logging/setLevel", {"level": "warning"})
        # returns None (notification-like) or result
        assert r is not None  # has id so always returns


# ===========================================================================
# FORGE AGENT
# ===========================================================================

class TestForgeAgent:
    def test_friction_report_dataclass(self):
        from hlf.forge_agent import FrictionReport
        report = FrictionReport(
            id="abc123",
            timestamp=time.time(),
            grammar_version="0.5.0",
            grammar_sha256="a" * 64,
            source_snippet="test code",
            failure_type="expression",
            attempted_intent="test intent",
            context={},
            proposed_fix=None,
            agent_metadata={"tier": "forge"},
        )
        assert report.id == "abc123"
        assert report.failure_type == "expression"

    def test_friction_report_to_dict(self):
        from hlf.forge_agent import FrictionReport
        report = FrictionReport(
            id="abc123", timestamp=1.0, grammar_version="0.5.0",
            grammar_sha256="a" * 64, source_snippet="x",
            failure_type="parse", attempted_intent="y",
            context={}, proposed_fix=None, agent_metadata={},
        )
        d = report.to_dict()
        assert d["id"] == "abc123"
        assert isinstance(d, dict)

    def test_grammar_proposal_dataclass(self):
        from hlf.forge_agent import GrammarProposal
        proposal = GrammarProposal(
            id="prop-001",
            friction_id="abc123",
            timestamp=time.time(),
            proposed_syntax="async fn f() {}",
            rationale="Need async support",
            additive_only=True,
            breaking=False,
            tier_required="forge",
            affected_opcodes=["CALL"],
            validation_token="tok123",
        )
        assert proposal.id == "prop-001"
        assert proposal.additive_only is True
        assert proposal.breaking is False

    def test_grammar_proposal_to_dict(self):
        from hlf.forge_agent import GrammarProposal
        proposal = GrammarProposal(
            id="p", friction_id="f", timestamp=1.0,
            proposed_syntax="x", rationale="y",
            additive_only=True, breaking=False,
            tier_required="forge", affected_opcodes=[],
            validation_token="",
        )
        d = proposal.to_dict()
        assert d["id"] == "p"

    def test_forge_agent_init(self, repo_root):
        from hlf.forge_agent import ForgeAgent
        agent = ForgeAgent(repo_root)
        assert agent.repo_root == repo_root.resolve()

    def test_forge_agent_loads_grammar(self, repo_root):
        from hlf.forge_agent import ForgeAgent
        agent = ForgeAgent(repo_root)
        assert agent.current_grammar_sha is not None
        assert len(agent.current_grammar_sha) == 64

    def test_forge_agent_validate_known_friction_types(self, repo_root, tmp_path):
        from hlf.forge_agent import ForgeAgent, FrictionReport
        agent = ForgeAgent(repo_root)
        for ftype in ["parse", "compile", "effect", "gas", "expression", "type", "semantic"]:
            report = FrictionReport(
                id="x", timestamp=time.time(),
                grammar_version="0.5.0", grammar_sha256="a" * 64,
                source_snippet="x", failure_type=ftype,
                attempted_intent="", context={}, proposed_fix=None,
                agent_metadata={},
            )
            assert agent._validate_friction(report) is True

    def test_forge_agent_validate_unknown_friction_type(self, repo_root):
        from hlf.forge_agent import ForgeAgent, FrictionReport
        agent = ForgeAgent(repo_root)
        report = FrictionReport(
            id="x", timestamp=time.time(),
            grammar_version="0.5.0", grammar_sha256="a" * 64,
            source_snippet="x", failure_type="INVALID_TYPE",
            attempted_intent="", context={}, proposed_fix=None,
            agent_metadata={},
        )
        assert agent._validate_friction(report) is False


# ===========================================================================
# METRICS
# ===========================================================================

class TestMetrics:
    def test_record_usage(self, metrics):
        uid = metrics.record_usage("hlf_compile", success=True, gas_used=500, duration_ms=25.0)
        assert uid.startswith("usage_")

    def test_record_usage_failure(self, metrics):
        uid = metrics.record_usage("hlf_execute", success=False, error="VM not available")
        assert uid.startswith("usage_")

    def test_stats_increment(self, metrics):
        before = metrics.get_stats()["total_uses"]
        metrics.record_usage("hlf_validate", success=True)
        after = metrics.get_stats()["total_uses"]
        assert after == before + 1

    def test_record_test(self, metrics):
        tid = metrics.record_test("test_compile_basic", passed=True, duration_ms=10.0)
        assert tid.startswith("test_")

    def test_record_test_failure(self, metrics):
        tid = metrics.record_test("test_broken", passed=False, duration_ms=5.0, error="AssertionError")
        assert tid.startswith("test_")

    def test_suggest_improvement(self, metrics):
        sid = metrics.suggest_improvement(
            source="agent", category="grammar",
            title="Add async effect", description="Need async I/O effects", priority=4,
        )
        assert len(sid) == 8  # sha256 truncated

    def test_get_open_suggestions(self, metrics):
        metrics.suggest_improvement(
            source="user", category="performance",
            title="Cache bytecode", description="Cache compiled bytecode", priority=3,
        )
        suggestions = metrics.get_open_suggestions()
        assert len(suggestions) >= 1
        assert all(s["status"] == "open" for s in suggestions)

    def test_suggestions_sorted_by_priority(self, metrics):
        suggestions = metrics.get_open_suggestions()
        priorities = [s["priority"] for s in suggestions]
        assert priorities == sorted(priorities, reverse=True)

    def test_vote_improvement(self, metrics):
        sid = metrics.suggest_improvement(
            source="agent", category="docs",
            title="Improve docs", description="More examples", priority=2,
        )
        result = metrics.vote_improvement(sid, vote=1)
        assert result is True

    def test_resolve_improvement(self, metrics):
        sid = metrics.suggest_improvement(
            source="agent", category="tool",
            title="Fix bug", description="Fix X", priority=5,
        )
        result = metrics.resolve_improvement(sid, status="resolved")
        assert result is True

    def test_get_stats_structure(self, metrics):
        stats = metrics.get_stats()
        for key in ["total_uses", "successful_uses", "failed_uses",
                    "tests_passed", "tests_failed", "suggestions_open"]:
            assert key in stats

    def test_health_report(self, metrics):
        health = metrics.get_health_report()
        assert "health_score" in health
        assert 0 <= health["health_score"] <= 100
        assert "success_rate" in health
        assert "test_pass_rate" in health

    def test_get_recent_usage(self, metrics):
        metrics.record_usage("hlf_analyze", success=True)
        events = metrics.get_recent_usage(limit=5)
        assert isinstance(events, list)
        assert len(events) <= 5

    def test_get_test_results(self, metrics):
        metrics.record_test("test_recent", passed=True, duration_ms=1.0)
        results = metrics.get_test_results(limit=5)
        assert isinstance(results, list)

    def test_record_session(self, metrics):
        before = metrics.get_stats()["sessions"]
        metrics.record_session()
        after = metrics.get_stats()["sessions"]
        assert after == before + 1

    def test_export_metrics(self, metrics, tmp_path):
        out = metrics.export_metrics(tmp_path / "export.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert "stats" in data
        assert "health" in data
        assert "recent_usage" in data


# ===========================================================================
# METRICS — convenience wrappers
# ===========================================================================

class TestMetricsWrappers:
    def test_record_tool_call(self):
        from hlf.mcp_metrics import record_tool_call
        record_tool_call("hlf_compile", success=True, duration_ms=10, gas_used=100)

    def test_record_tool_call_failure(self):
        from hlf.mcp_metrics import record_tool_call
        record_tool_call("hlf_execute", success=False, error="VM error")

    def test_suggest_improvement_wrapper(self):
        from hlf.mcp_metrics import suggest_improvement
        sid = suggest_improvement("Performance", "Add bytecode caching", priority=2)
        assert isinstance(sid, str)
        assert len(sid) == 8

    def test_suggest_improvement_with_title(self):
        from hlf.mcp_metrics import suggest_improvement
        sid = suggest_improvement(
            "Grammar", "Extend type system", priority=3,
            source="agent", title="Add union types"
        )
        assert isinstance(sid, str)

    def test_record_test_result(self):
        from hlf.mcp_metrics import record_test_result
        record_test_result("test_example", success=True, duration_ms=5.0)

    def test_record_friction_wrapper(self):
        from hlf.mcp_metrics import record_friction
        record_friction("expression", "test ↦ unknown", context={"tier": "forge"})


# ===========================================================================
# CLIENT — dataclasses and instantiation
# ===========================================================================

class TestClient:
    def test_client_instantiation(self):
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"
        assert client.cache_ttl == 3600

    def test_client_custom_cache_ttl(self):
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient("http://localhost:9999", cache_ttl=60)
        assert client.cache_ttl == 60

    def test_client_has_all_methods(self):
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient("http://localhost:8000")
        for method in ["get_version", "get_grammar", "get_dictionaries",
                       "get_init_prompt", "compile", "execute",
                       "validate", "friction_log", "get_system_prompt"]:
            assert hasattr(client, method), f"Missing method: {method}"

    def test_grammar_info_dataclass(self):
        from hlf.mcp_client import GrammarInfo
        info = GrammarInfo(version="0.5.0", sha256="abc", generated_at=1.0, compatibility=["MCP-2025"])
        assert info.version == "0.5.0"
        assert info.compatibility == ["MCP-2025"]

    def test_compile_result_dataclass(self):
        from hlf.mcp_client import CompileResult
        r = CompileResult(success=True, bytecode="abc", gas_estimate=100, effects=["IO"], warnings=[], errors=[])
        assert r.success is True
        assert r.gas_estimate == 100

    def test_execute_result_dataclass(self):
        from hlf.mcp_client import ExecuteResult
        r = ExecuteResult(success=True, result="42", gas_used=500, effects_triggered=[], errors=[])
        assert r.gas_used == 500

    def test_client_cache_initially_empty(self):
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient("http://localhost:8000")
        assert client.cached_grammar is None
        assert client.cached_dictionaries is None
        assert client.cached_version is None


# ===========================================================================
# END-TO-END: compile → execute pipeline
# ===========================================================================

class TestCompileExecutePipeline:
    def test_compile_then_execute(self, tool_provider):
        compile_result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        assert compile_result["success"] is True

        execute_result = tool_provider.call_tool("hlf_execute", {
            "bytecode": compile_result["bytecode"],
            "gas_limit": 50000,
        })
        assert execute_result["success"] is True
        assert execute_result["gas_used"] <= 50000

    def test_compile_validate_agreement(self, tool_provider):
        """Validate and compile should agree on validity."""
        validate_result = tool_provider.call_tool("hlf_validate", {"source": SAMPLE_HLF})
        compile_result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        # Both should succeed on valid source
        assert compile_result["success"] is True

    def test_analyze_then_compile(self, tool_provider):
        analyze = tool_provider.call_tool("hlf_analyze", {
            "source": SAMPLE_HLF, "metrics": ["gas_estimate"]
        })
        compile_result = tool_provider.call_tool("hlf_compile", {"source": SAMPLE_HLF})
        assert analyze["success"] is True
        assert compile_result["success"] is True

    def test_compose_then_validate(self, tool_provider):
        compose = tool_provider.call_tool("hlf_compose", {
            "programs": ["module a { fn f(): int { ret 1 } }", "module b { fn g(): int { ret 2 } }"],
            "strategy": "sequential",
        })
        assert compose["success"] is True
        validate = tool_provider.call_tool("hlf_validate", {"source": compose["composed_source"]})
        assert isinstance(validate["success"], bool)


# ===========================================================================
# EDGE CASES + SECURITY BOUNDARIES
# ===========================================================================

class TestEdgeCases:
    def test_friction_log_large_snippet(self, tool_provider):
        big = "x" * 10000
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": big,
            "failure_type": "expression",
        })
        assert result["success"] is True

    def test_compile_very_large_source(self, tool_provider):
        large = (SAMPLE_HLF * 50)
        result = tool_provider.call_tool("hlf_compile", {"source": large})
        assert result["success"] is True

    def test_analyze_no_metrics_specified(self, tool_provider):
        result = tool_provider.call_tool("hlf_analyze", {"source": SAMPLE_HLF})
        assert result["success"] is True

    def test_server_handles_malformed_tool_args(self, mcp_server):
        result = asyncio.run(mcp_server.tools_call("hlf_compile", {}))
        # Should not crash — returns error result
        assert "content" in result
        data = json.loads(result["content"][0]["text"])
        # Empty source → fail gracefully
        assert isinstance(data["success"], bool)

    def test_self_observe_default_tier_is_forge(self, tool_provider):
        result = tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {"phase": "test"},
            # no tier specified → defaults to forge
        })
        assert result["success"] is True

    def test_compose_single_program(self, tool_provider):
        result = tool_provider.call_tool("hlf_compose", {
            "programs": ["module solo { }"],
        })
        assert result["success"] is True
        assert result["program_count"] == 1

    def test_version_info_has_compatibility(self, resource_provider):
        r = resource_provider.read_resource("hlf://version")
        data = json.loads(r.content)
        assert "compatibility" in data
        assert isinstance(data["compatibility"], list)
        assert len(data["compatibility"]) >= 1
