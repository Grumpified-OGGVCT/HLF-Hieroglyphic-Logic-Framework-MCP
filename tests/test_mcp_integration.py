"""
MCP Integration Tests for HLF.

These tests verify:
1. Resource loading (grammar, dictionaries, version)
2. Tool execution (compile, execute, validate)
3. Prompt generation
4. Friction logging
5. Version change detection

Run: python -m pytest tests/test_mcp_integration.py -v --tb=short
"""

import pytest
import json
import time
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMCPResources:
    """Test MCP Resources provider."""
    
    def test_list_resources(self):
        """Test that all resources are listed."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        resources = provider.list_resources()
        
        # Should have core resources
        resource_uris = [r.uri for r in resources]
        assert "hlf://grammar" in resource_uris
        assert "hlf://bytecode" in resource_uris
        assert "hlf://dictionaries" in resource_uris
        assert "hlf://version" in resource_uris
        assert "hlf://ast-schema" in resource_uris
    
    def test_read_grammar(self):
        """Test reading grammar resource."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        grammar = provider.read_resource("hlf://grammar")
        
        assert grammar.content is not None
        assert len(grammar.content) > 0
        assert grammar.mime_type == "application/yaml"
    
    def test_read_version(self):
        """Test reading version info."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        version = provider.read_resource("hlf://version")
        
        assert version.content is not None
        data = json.loads(version.content)
        
        assert "version" in data
        assert "grammar_sha256" in data
        assert "generated_at" in data
    
    def test_read_bytecode_spec(self):
        """Test reading bytecode specification."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        bytecode = provider.read_resource("hlf://bytecode")
        
        assert bytecode.content is not None
        assert bytecode.mime_type == "application/yaml"
    
    def test_list_resource_templates(self):
        """Test that resource templates are available."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        templates = provider.list_resource_templates()
        
        template_uris = [t.uri_template for t in templates]
        assert "hlf://programs/{name}" in template_uris
        assert "hlf://profiles/{tier}" in template_uris


class TestMCPTools:
    """Test MCP Tools provider."""
    
    def test_list_tools(self):
        """Test that all tools are listed."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=repo_root / "tests" / "friction_test"
        )
        
        tools = tool_provider.list_tools()
        
        tool_names = [t.name for t in tools]
        assert "hlf_compile" in tool_names
        assert "hlf_execute" in tool_names
        assert "hlf_validate" in tool_names
        assert "hlf_friction_log" in tool_names
        assert "hlf_self_observe" in tool_names
        assert "hlf_get_version" in tool_names
        assert "hlf_compose" in tool_names
        assert "hlf_decompose" in tool_names
    
    def test_get_version(self):
        """Test getting version info."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=repo_root / "tests" / "friction_test"
        )
        
        result = tool_provider.call_tool("hlf_get_version", {})
        
        assert "version" in result
        assert "grammar_sha256" in result
    
    def test_friction_log(self, tmp_path):
        """Test friction logging."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        
        friction_drop = tmp_path / "friction"
        friction_drop.mkdir(parents=True, exist_ok=True)
        
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=friction_drop
        )
        
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "module test { fn main() { ret unknown_construct() } }",
            "failure_type": "expression",
            "attempted_intent": "Trying to use unknown construct",
            "context": {"tier": "forge", "profile": "P0"}
        })
        
        assert result["success"] is True
        assert "friction_id" in result
        
        # Check file was created
        friction_files = list(friction_drop.glob("*.hlf"))
        assert len(friction_files) == 1
    
    def test_compose(self):
        """Test program composition."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=repo_root / "tests" / "friction_test"
        )
        
        result = tool_provider.call_tool("hlf_compose", {
            "programs": [
                "module a { fn f1() { ret 1 } }",
                "module b { fn f2() { ret 2 } }"
            ],
            "strategy": "sequential"
        })
        
        assert result["success"] is True
        assert "composed_source" in result


class TestMCPrompts:
    """Test MCP Prompts provider."""
    
    def test_list_prompts(self):
        """Test that all prompts are listed."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        prompts = provider.list_prompts()
        
        prompt_names = [p.name for p in prompts]
        assert "hlf_initialize_agent" in prompt_names
        assert "hlf_express_intent" in prompt_names
        assert "hlf_troubleshoot" in prompt_names
        assert "hlf_propose_extension" in prompt_names
        assert "hlf_compose_agents" in prompt_names
    
    def test_initialize_agent_prompt(self):
        """Test agent initialization prompt."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        prompt = provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge",
            "profile": "P0"
        })
        
        assert "HLF MODE" in prompt
        assert "forge" in prompt
        assert "P0" in prompt
        assert "Ω" in prompt
    
    def test_initialize_agent_with_focus(self):
        """Test agent init with focus area."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        prompt = provider.get_prompt("hlf_initialize_agent", {
            "tier": "sovereign",
            "profile": "P2",
            "focus": "code analysis"
        })
        
        assert "sovereign" in prompt
        assert "P2" in prompt
        assert "code analysis" in prompt
    
    def test_troubleshoot_prompt(self):
        """Test troubleshooting prompt."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        prompt = provider.get_prompt("hlf_troubleshoot", {
            "source": "module test { fn main() { ret } }",
            "error": "Missing return expression",
            "context": "Trying to return nothing"
        })
        
        assert "FAILED SOURCE" in prompt
        assert "Missing return expression" in prompt
    
    def test_missing_required_argument(self):
        """Test that missing required argument raises error."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        with pytest.raises(ValueError, match="Missing required argument"):
            provider.get_prompt("hlf_initialize_agent", {})


class TestMCPClient:
    """Test MCP client."""
    
    @patch('httpx.get')
    @patch('httpx.post')
    def test_client_initialization(self, mock_post, mock_get):
        """Test client can be created."""
        from hlf.mcp_client import HLFMCPClient
        
        client = HLFMCPClient("http://localhost:8000")
        
        assert client.base_url == "http://localhost:8000"
        assert client.cache_ttl == 3600
    
    @patch('httpx.get')
    def test_get_version_with_cache(self, mock_get):
        """Test version caching."""
        from hlf.mcp_client import HLFMCPClient
        
        mock_get.return_value.json.return_value = {
            "content": json.dumps({
                "version": "0.5.0",
                "grammar_sha256": "abc123",
                "generated_at": time.time(),
                "compatibility": ["MCP-2024-11-05"]
            })
        }
        
        client = HLFMCPClient("http://localhost:8000")
        version = client.get_version(use_cache=False)
        
        assert version.version == "0.5.0"
        assert version.sha256 == "abc123"
    
    def test_check_version_change(self):
        """Test version change detection."""
        from hlf.mcp_client import HLFMCPClient
        
        client = HLFMCPClient("http://localhost:8000")
        
        # Simulate cached version
        client.cached_version = type('GrammarInfo', (), {
            'version': '0.4.0',
            'sha256': 'old_hash',
            'generated_at': time.time(),
            'compatibility': []
        })()
        client.last_fetch_time = time.time()
        
        # With mocked get_version that returns different sha
        with patch.object(client, 'get_version') as mock_ver:
            mock_ver.return_value = type('GrammarInfo', (), {
                'version': '0.5.0',
                'sha256': 'new_hash',
                'generated_at': time.time(),
                'compatibility': []
            })()
            
            assert client.check_version_change() is True


# ============================================
# METRICS AND REPORTING TESTS
# ============================================

class TestMetricsCollection:
    """Test that metrics are collected for improvement proposals."""
    
    def test_friction_report_has_metrics(self, tmp_path):
        """Test that friction reports include metrics."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        friction_drop = tmp_path / "friction"
        friction_drop.mkdir(parents=True, exist_ok=True)
        
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=friction_drop
        )
        
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "test",
            "failure_type": "expression",
            "context": {
                "tier": "forge",
                "profile": "P0",
                "gas_used": 1234,
                "execution_time_ms": 500
            }
        })
        
        # Read the friction file
        friction_files = list(friction_drop.glob("*.hlf"))
        friction_data = json.loads(friction_files[0].read_text())
        
        # Verify metrics are present
        assert friction_data["grammar_version"] is not None
        assert friction_data["grammar_sha256"] is not None
        assert friction_data["agent_metadata"]["tier"] == "forge"
    
    def test_self_observe_creates_report(self, tmp_path):
        """Test that self-observation creates report."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        friction_drop = tmp_path / "friction"
        friction_drop.mkdir(parents=True, exist_ok=True)
        
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=friction_drop
        )
        
        result = tool_provider.call_tool("hlf_self_observe", {
            "meta_intent": {
                "phase": "execution",
                "source_hash": "abc123",
                "gas_used": 5000,
                "profile": "P0"
            }
        })
        
        assert result["success"] is True
        assert "observe_id" in result
        
        # Check that a self_observe file was created
        observe_files = list(friction_drop.glob("self_observe_*.hlf"))
        assert len(observe_files) == 1


class TestImprovementProposal:
    """Test that improvement proposals can be generated from metrics."""
    
    def test_friction_to_proposal_conversion(self, tmp_path):
        """Test converting friction to proposal."""
        from hlf.forge_agent import ForgeAgent, FrictionReport
        
        repo_root = Path(__file__).parent.parent
        
        # Create mock MCP client
        mock_client = MagicMock()
        mock_client.base_url = "http://localhost:8000"
        
        forge = ForgeAgent(repo_root, mock_client)
        
        # Create a friction report
        report = FrictionReport(
            id="test123",
            timestamp=time.time(),
            grammar_version="0.5.0",
            grammar_sha256="abc123",
            source_snippet="module test { fn main() { ret NEW_SYNTAX() } }",
            failure_type="expression",
            attempted_intent="Use new syntax feature",
            context={"tier": "forge"},
            proposed_fix=None,
            agent_metadata={"tier": "forge", "profile": "P0"}
        )
        
        # Validate friction report
        assert forge._validate_friction(report) is True


# ============================================
# MCP ENDPOINT TESTS
# ============================================

class TestMCPServerEndpoints:
    """Test MCP server HTTP endpoints."""
    
    @pytest.fixture
    def server(self):
        """Create server instance."""
        from hlf.mcp_server_complete import MCPServer
        
        repo_root = Path(__file__).parent.parent
        friction_drop = repo_root / "tests" / "friction_test"
        friction_drop.mkdir(parents=True, exist_ok=True)
        
        return MCPServer(repo_root, friction_drop)
    
    @pytest.mark.asyncio
    async def test_initialize(self, server):
        """Test MCP initialize."""
        result = await server.initialize({})
        
        assert result["protocolVersion"] in ("2024-11-05", "2025-03-26")
        assert "capabilities" in result
        assert result["serverInfo"]["name"] == "hlf-mcp-server"
    
    @pytest.mark.asyncio
    async def test_resources_list(self, server):
        """Test listing resources."""
        result = await server.resources_list()
        
        assert "resources" in result
        assert len(result["resources"]) >= 5
    
    @pytest.mark.asyncio
    async def test_tools_list(self, server):
        """Test listing tools."""
        result = await server.tools_list()
        
        assert "tools" in result
        tool_names = [t["name"] for t in result["tools"]]
        assert "hlf_compile" in tool_names
        assert "hlf_friction_log" in tool_names
    
    @pytest.mark.asyncio
    async def test_prompts_list(self, server):
        """Test listing prompts."""
        result = await server.prompts_list()
        
        assert "prompts" in result
        prompt_names = [p["name"] for p in result["prompts"]]
        assert "hlf_initialize_agent" in prompt_names


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])