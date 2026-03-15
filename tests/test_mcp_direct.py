#!/usr/bin/env python3
"""
Direct tests for MCP implementation without pytest infrastructure.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    passed = 0
    failed = 0
    
    # Test MCP resources
    try:
        from hlf.mcp_resources import HLFResourceProvider, Resource, ResourceTemplate
        print(f"  ✓ mcp_resources: HLFResourceProvider, Resource, ResourceTemplate")
        passed += 1
    except Exception as e:
        print(f"  ✗ mcp_resources: {e}")
        failed += 1
    
    # Test MCP tools
    try:
        from hlf.mcp_tools import HLFToolProvider, ToolDefinition
        print(f"  ✓ mcp_tools: HLFToolProvider, ToolDefinition")
        passed += 1
    except Exception as e:
        print(f"  ✗ mcp_tools: {e}")
        failed += 1
    
    # Test MCP prompts
    try:
        from hlf.mcp_prompts import HLFPromptProvider, PromptDefinition, PromptArgument
        print(f"  ✓ mcp_prompts: HLFPromptProvider, PromptDefinition, PromptArgument")
        passed += 1
    except Exception as e:
        print(f"  ✗ mcp_prompts: {e}")
        failed += 1
    
    # Test MCP client
    try:
        from hlf.mcp_client import HLFMCPClient, GrammarInfo
        print(f"  ✓ mcp_client: HLFMCPClient, GrammarInfo")
        passed += 1
    except Exception as e:
        print(f"  ✗ mcp_client: {e}")
        failed += 1
    
    # Test Forge agent
    try:
        from hlf.forge_agent import ForgeAgent, FrictionReport, GrammarProposal
        print(f"  ✓ forge_agent: ForgeAgent, FrictionReport, GrammarProposal")
        passed += 1
    except Exception as e:
        print(f"  ✗ forge_agent: {e}")
        failed += 1
    
    return passed, failed


def test_resource_provider():
    """Test the resource provider functionality."""
    print("\nTesting ResourceProvider...")
    
    passed = 0
    failed = 0
    
    try:
        from hlf.mcp_resources import HLFResourceProvider
        from pathlib import Path
        
        repo_root = Path(__file__).parent.parent
        provider = HLFResourceProvider(repo_root)
        
        # Test list_resources
        resources = provider.list_resources()
        print(f"  ✓ list_resources: {len(resources)} resources")
        passed += 1
        
        # Test list_resource_templates
        templates = provider.list_resource_templates()
        print(f"  ✓ list_resource_templates: {len(templates)} templates")
        passed += 1
        
        # Test get_version
        version = provider._get_version_info()
        print(f"  ✓ version: {version.get('version', 'unknown')}")
        passed += 1
        
    except Exception as e:
        print(f"  ✗ ResourceProvider error: {e}")
        import traceback
        traceback.print_exc()
        failed += 3
    
    return passed, failed


def test_tool_provider():
    """Test the tool provider functionality."""
    print("\nTesting ToolProvider...")
    
    passed = 0
    failed = 0
    
    try:
        from hlf.mcp_tools import HLFToolProvider
        from pathlib import Path
        
        repo_root = Path(__file__).parent.parent
        friction_drop = repo_root / "test_friction_drop"
        friction_drop.mkdir(exist_ok=True)
        
        provider = HLFToolProvider(
            resource_provider=None,  # Would need real one
            vm_executor=None,
            friction_drop=friction_drop
        )
        
        # Test list_tools
        tools = provider.list_tools()
        print(f"  ✓ list_tools: {len(tools)} tools")
        passed += 1
        
        # Test friction_log (doesn't need real VM)
        result = provider._friction_log({
            "source_snippet": "test ↦ unknown",
            "failure_type": "expression",
            "attempted_intent": "Testing friction log"
        })
        print(f"  ✓ friction_log: {result.get('success', False)}")
        passed += 1
        
        # Cleanup
        import shutil
        shutil.rmtree(friction_drop)
        
    except Exception as e:
        print(f"  ✗ ToolProvider error: {e}")
        import traceback
        traceback.print_exc()
        failed += 2
    
    return passed, failed


def test_prompt_provider():
    """Test the prompt provider functionality."""
    print("\nTesting PromptProvider...")
    
    passed = 0
    failed = 0
    
    try:
        from hlf.mcp_prompts import HLFPromptProvider
        
        provider = HLFPromptProvider()
        
        # Test list_prompts
        prompts = provider.list_prompts()
        print(f"  ✓ list_prompts: {len(prompts)} prompts")
        passed += 1
        
        # Test get_prompt (init agent)
        init_prompt = provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge",
            "profile": "P0"
        })
        assert "HLF MODE" in init_prompt
        assert "forge" in init_prompt
        print(f"  ✓ get_prompt (init): {len(init_prompt)} chars")
        passed += 1
        
        # Test intent compression prompt
        intent_prompt = provider.get_prompt("hlf_express_intent", {
            "intent": "Read a file and write the result"
        })
        assert "HLF INTENT COMPRESSION" in intent_prompt
        print(f"  ✓ get_prompt (intent): {len(intent_prompt)} chars")
        passed += 1
        
    except Exception as e:
        print(f"  ✗ PromptProvider error: {e}")
        import traceback
        traceback.print_exc()
        failed += 3
    
    return passed, failed


def test_mcp_server():
    """Test the MCP server initialization."""
    print("\nTesting MCPServer...")
    
    passed = 0
    failed = 0
    
    try:
        from hlf.mcp_server_complete import MCPServer
        from pathlib import Path
        
        repo_root = Path(__file__).parent.parent
        friction_drop = repo_root / "test_friction_drop"
        friction_drop.mkdir(exist_ok=True)
        
        server = MCPServer(repo_root, friction_drop)
        print(f"  ✓ MCPServer initialized")
        passed += 1
        
        # Test capabilities
        assert "resources" in server.capabilities
        assert "tools" in server.capabilities
        assert "prompts" in server.capabilities
        print(f"  ✓ capabilities: {list(server.capabilities.keys())}")
        passed += 1
        
        # Test tools_list (async)
        import asyncio
        
        async def test_async():
            result = await server.tools_list()
            return result
        
        tools = asyncio.run(test_async())
        assert "tools" in tools
        print(f"  ✓ tools_list: {len(tools['tools'])} tools")
        passed += 1
        
        # Cleanup
        import shutil
        shutil.rmtree(friction_drop)
        
    except Exception as e:
        print(f"  ✗ MCPServer error: {e}")
        import traceback
        traceback.print_exc()
        failed += 3
    
    return passed, failed


def test_mcp_client():
    """Test the MCP client (without server)."""
    print("\nTesting MCPClient...")
    
    passed = 0
    failed = 0
    
    try:
        from hlf.mcp_client import HLFMCPClient, GrammarInfo
        
        client = HLFMCPClient("http://localhost:8000")
        
        # Test that methods exist
        assert hasattr(client, 'get_version')
        assert hasattr(client, 'get_grammar')
        assert hasattr(client, 'get_dictionaries')
        assert hasattr(client, 'get_init_prompt')
        assert hasattr(client, 'compile')
        assert hasattr(client, 'execute')
        assert hasattr(client, 'validate')
        assert hasattr(client, 'friction_log')
        assert hasattr(client, 'get_system_prompt')
        print(f"  ✓ all client methods present")
        passed += 1
        
        # Test GrammarInfo
        info = GrammarInfo(
            version="0.5.0",
            sha256="abc123",
            generated_at=1234567890.0,
            compatibility=["MCP-2024-11-05"]
        )
        assert info.version == "0.5.0"
        print(f"  ✓ GrammarInfo dataclass works")
        passed += 1
        
    except Exception as e:
        print(f"  ✗ MCPClient error: {e}")
        import traceback
        traceback.print_exc()
        failed += 2
    
    return passed, failed


def main():
    """Run all tests."""
    print("=" * 60)
    print("HLF MCP Implementation Tests")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    # Run tests
    p, f = test_imports()
    total_passed += p
    total_failed += f
    
    p, f = test_resource_provider()
    total_passed += p
    total_failed += f
    
    p, f = test_tool_provider()
    total_passed += p
    total_failed += f
    
    p, f = test_prompt_provider()
    total_passed += p
    total_failed += f
    
    p, f = test_mcp_server()
    total_passed += p
    total_failed += f
    
    p, f = test_mcp_client()
    total_passed += p
    total_failed += f
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Results: {total_passed} passed, {total_failed} failed")
    print("=" * 60)
    
    if total_failed == 0:
        print("✓ ALL TESTS PASSED")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())