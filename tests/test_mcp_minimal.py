"""
Minimal tests for MCP implementation.
Tests the core functionality without requiring full HLF parser/lexer.
"""

import pytest
import json
import time
import hashlib
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test that we can import the MCP modules
def test_import_mcp_resources():
    """Test that mcp_resources can be imported."""
    from hlf.mcp_resources import HLFResourceProvider, Resource, ResourceTemplate
    assert HLFResourceProvider is not None
    assert Resource is not None
    assert ResourceTemplate is not None

def test_import_mcp_tools():
    """Test that mcp_tools can be imported."""
    from hlf.mcp_tools import HLFToolProvider, ToolDefinition
    assert HLFToolProvider is not None
    assert ToolDefinition is not None

def test_import_mcp_prompts():
    """Test that mcp_prompts can be imported."""
    from hlf.mcp_prompts import HLFPromptProvider, PromptDefinition
    assert HLFPromptProvider is not None
    assert PromptDefinition is not None

def test_import_mcp_server():
    """Test that mcp_server_complete can be imported."""
    from hlf.mcp_server_complete import MCPServer
    assert MCPServer is not None

def test_import_mcp_client():
    """Test that mcp_client can be imported."""
    from hlf.mcp_client import HLFMCPClient, GrammarInfo
    assert HLFMCPClient is not None
    assert GrammarInfo is not None

def test_import_forge_agent():
    """Test that forge_agent can be imported."""
    from hlf.forge_agent import ForgeAgent, FrictionReport, GrammarProposal
    assert ForgeAgent is not None
    assert FrictionReport is not None
    assert GrammarProposal is not None


# Test MCP Resources functionality
class TestMCPResources:
    """Test MCP Resources implementation."""
    
    def test_resource_definition(self):
        """Test Resource dataclass."""
        from hlf.mcp_resources import Resource
        
        resource = Resource(
            uri="hlf://test",
            name="Test Resource",
            description="A test resource",
            mime_type="text/plain",
            content="Hello"
        )
        
        assert resource.uri == "hlf://test"
        assert resource.name == "Test Resource"
        assert resource.content == "Hello"
    
    def test_resource_template(self):
        """Test ResourceTemplate dataclass."""
        from hlf.mcp_resources import ResourceTemplate
        
        template = ResourceTemplate(
            uri_template="hlf://programs/{name}",
            name="Program Template",
            description="Load HLF program",
            mime_type="text/x-hlf",
            parameters={"name": {"type": "string"}}
        )
        
        assert template.uri_template == "hlf://programs/{name}"
    
    def test_resource_provider_list(self):
        """Test listing resources."""
        from hlf.mcp_resources import HLFResourceProvider
        
        # Use the hlf directory as repo root
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        resources = provider.list_resources()
        assert len(resources) >= 5  # grammar, bytecode, dictionaries, version, ast-schema
        
        uris = [r.uri for r in resources]
        assert "hlf://grammar" in uris
        assert "hlf://dictionaries" in uris
        assert "hlf://version" in uris
    
    def test_version_info(self):
        """Test version info generation."""
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        version = provider._get_version_info()
        
        assert "version" in version
        assert "grammar_sha256" in version
        assert "generated_at" in version


# Test MCP Tools functionality
class TestMCPTools:
    """Test MCP Tools implementation."""
    
    def test_tool_definition(self):
        """Test ToolDefinition dataclass."""
        from hlf.mcp_tools import ToolDefinition
        
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"}
        )
        
        assert tool.name == "test_tool"
    
    def test_tool_provider_list(self):
        """Test listing tools."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(resource_provider)
        
        tools = tool_provider.list_tools()
        assert len(tools) >= 5  # compile, execute, validate, friction_log, etc
        
        names = [t.name for t in tools]
        assert "hlf_compile" in names
        assert "hlf_execute" in names
        assert "hlf_validate" in names
        assert "hlf_friction_log" in names
        assert "hlf_get_version" in names
    
    def test_friction_log(self, tmp_path):
        """Test friction logging."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(
            resource_provider, 
            friction_drop=tmp_path / "friction"
        )
        
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "test ↦ undefined",
            "failure_type": "expression",
            "attempted_intent": "Trying to use undefined operator"
        })
        
        assert result["success"] == True
        assert "friction_id" in result
        assert Path(result["file"]).exists()
    
    def test_get_version_tool(self):
        """Test version tool."""
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_resources import HLFResourceProvider
        
        repo_root = Path(__file__).parent.parent
        resource_provider = HLFResourceProvider(repo_root)
        tool_provider = HLFToolProvider(resource_provider)
        
        result = tool_provider.call_tool("hlf_get_version", {})
        
        assert "version" in result
        assert "grammar_sha256" in result


# Test MCP Prompts functionality
class TestMCPPrompts:
    """Test MCP Prompts implementation."""
    
    def test_prompt_definition(self):
        """Test PromptDefinition dataclass."""
        from hlf.mcp_prompts import PromptDefinition, PromptArgument
        
        prompt = PromptDefinition(
            name="test_prompt",
            description="A test prompt",
            arguments=[PromptArgument("arg1", "First arg")],
            template="Hello {{arg1}}"
        )
        
        assert prompt.name == "test_prompt"
    
    def test_prompt_provider_list(self):
        """Test listing prompts."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        prompts = provider.list_prompts()
        
        assert len(prompts) >= 5  # init, intent, troubleshoot, propose, compose
        
        names = [p.name for p in prompts]
        assert "hlf_initialize_agent" in names
        assert "hlf_express_intent" in names
        assert "hlf_troubleshoot" in names
    
    def test_init_prompt(self):
        """Test initialization prompt generation."""
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        prompt = provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge",
            "profile": "P0"
        })
        
        assert "forge" in prompt.lower()
        assert "P0" in prompt or "profile" in prompt.lower()
        assert "HLF" in prompt or "grammar" in prompt.lower()


# Test Friction Report format
class TestFrictionReport:
    """Test Friction report structure."""
    
    def test_friction_report_structure(self):
        """Test that friction reports have correct structure."""
        from hlf.forge_agent import FrictionReport
        
        report = FrictionReport(
            id="test123",
            timestamp=time.time(),
            grammar_version="0.4.0",
            grammar_sha256="abc123",
            source_snippet="test",
            failure_type="expression",
            attempted_intent="test intent",
            context={},
            proposed_fix="add new operator"
        )
        
        assert report.id == "test123"
        assert report.failure_type == "expression"
    
    def test_grammar_proposal_structure(self):
        """Test that grammar proposals have correct structure."""
        from hlf.forge_agent import GrammarProposal
        
        proposal = GrammarProposal(
            id="prop123",
            friction_id="friction123",
            timestamp=time.time(),
            proposed_syntax="new_op ↦ existing_op",
            rationale="Needed for X",
            additive_only=True,
            breaking=False,
            tier_required="forge",
            affected_opcodes=[],
            validation_token=""
        )
        
        assert proposal.additive_only == True
        assert proposal.breaking == False


# Test MCP Client
class TestMCPClient:
    """Test MCP client functionality."""
    
    def test_client_creation(self):
        """Test client can be created."""
        from hlf.mcp_client import HLFMCPClient
        
        client = HLFMCPClient("http://localhost:8000")
        assert client.base_url == "http://localhost:8000"
    
    def test_grammar_info_structure(self):
        """Test GrammarInfo dataclass."""
        from hlf.mcp_client import GrammarInfo
        
        info = GrammarInfo(
            version="0.4.0",
            sha256="abc123",
            generated_at=time.time(),
            compatibility=["MCP-2024-11-05"]
        )
        
        assert info.version == "0.4.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])