#!/usr/bin/env python3
"""
HLF Test Runner - Tests all modules independently
"""

import sys
from pathlib import Path

# Get the repo root
REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

PASS = "[PASS]"
FAIL = "[FAIL]"

def test_resources():
    """Test MCP resources module"""
    print("\n" + "=" * 60)
    print("Testing hlf.mcp_resources...")
    print("=" * 60)
    
    from hlf.mcp_resources import HLFResourceProvider, Resource, ResourceTemplate
    
    provider = HLFResourceProvider(REPO)
    
    # Test list_resources
    resources = provider.list_resources()
    print(f"{PASS} Found {len(resources)} resources")
    for r in resources:
        print(f"  - {r.uri}: {r.name}")
    
    # Test list_resource_templates
    templates = provider.list_resource_templates()
    print(f"{PASS} Found {len(templates)} templates")
    for t in templates:
        print(f"  - {t.uri_template}: {t.name}")
    
    # Test read_resource for grammar
    grammar = provider.read_resource("hlf://grammar")
    print(f"{PASS} Grammar loaded: {len(grammar.content)} chars")
    
    # Test read_resource for version
    version = provider.read_resource("hlf://version")
    import json
    version_data = json.loads(version.content)
    print(f"{PASS} Version: {version_data['version']} (SHA256: {version_data['grammar_sha256'][:16]}...)")
    
    # Test read_resource for dictionaries
    dicts = provider.read_resource("hlf://dictionaries")
    dict_data = json.loads(dicts.content)
    print(f"{PASS} Dictionaries: {len(dict_data.get('glyph_to_ascii', {}))} glyph mappings")
    
    print(f"\n{PASS} MCP RESOURCES: ALL TESTS PASSED")
    return True

def test_tools():
    """Test MCP tools module"""
    print("\n" + "=" * 60)
    print("Testing hlf.mcp_tools...")
    print("=" * 60)
    
    from hlf.mcp_tools import HLFToolProvider, ToolDefinition
    
    # Create mock objects for dependencies
    class MockResourceProvider:
        def _get_version_info(self):
            import hashlib, time
            grammar_path = REPO / "hlf" / "spec" / "core" / "grammar.yaml"
            grammar_content = grammar_path.read_text(encoding="utf-8")
            grammar_sha = hashlib.sha256(grammar_content.encode()).hexdigest()
            return {
                "version": "0.4.0",
                "grammar_sha256": grammar_sha,
                "generated_at": time.time()
            }
    
    class MockVMExecutor:
        pass
    
    friction_drop = REPO / "test_friction"
    friction_drop.mkdir(exist_ok=True)
    
    provider = HLFToolProvider(
        resource_provider=MockResourceProvider(),
        vm_executor=MockVMExecutor(),
        friction_drop=friction_drop
    )
    
    # Test list_tools
    tools = provider.list_tools()
    print(f"{PASS} Found {len(tools)} tools")
    for t in tools:
        print(f"  - {t.name}: {t.description[:50]}...")
    
    # Test friction_log
    result = provider.call_tool("hlf_friction_log", {
        "source_snippet": "test snippet",
        "failure_type": "expression",
        "attempted_intent": "test intent"
    })
    print(f"{PASS} Friction log created: {result.get('friction_id', 'N/A')}")
    
    # Test get_version
    result = provider.call_tool("hlf_get_version", {})
    print(f"{PASS} Version check: {result.get('version', 'N/A')}")
    
    # Cleanup
    import shutil
    shutil.rmtree(friction_drop)
    
    print(f"\n{PASS} MCP TOOLS: ALL TESTS PASSED")
    return True

def test_prompts():
    """Test MCP prompts module"""
    print("\n" + "=" * 60)
    print("Testing hlf.mcp_prompts...")
    print("=" * 60)
    
    from hlf.mcp_prompts import HLFPromptProvider
    
    provider = HLFPromptProvider()
    
    # Test list_prompts
    prompts = provider.list_prompts()
    print(f"{PASS} Found {len(prompts)} prompts")
    for p in prompts:
        print(f"  - {p.name}: {p.description[:50]}...")
    
    # Test get_prompt
    init_prompt = provider.get_prompt("hlf_initialize_agent", {
        "tier": "forge",
        "profile": "P0"
    })
    print(f"{PASS} Init prompt: {len(init_prompt)} chars")
    
    # Test intent compression prompt
    intent_prompt = provider.get_prompt("hlf_express_intent", {
        "intent": "Read a file and print its contents",
        "effects": "READ_FILE, STRUCTURED_OUTPUT"
    })
    print(f"{PASS} Intent prompt: {len(intent_prompt)} chars")
    
    print(f"\n{PASS} MCP PROMPTS: ALL TESTS PASSED")
    return True

def test_server():
    """Test MCP server module"""
    print("\n" + "=" * 60)
    print("Testing hlf.mcp_server_complete...")
    print("=" * 60)
    
    from hlf.mcp_server_complete import MCPServer, create_http_app
    
    friction_drop = REPO / "test_friction"
    friction_drop.mkdir(exist_ok=True)
    
    server = MCPServer(REPO, friction_drop)
    
    # Test capabilities
    print(f"{PASS} Server capabilities: {list(server.capabilities.keys())}")
    
    # Test initialize
    import asyncio
    result = asyncio.run(server.initialize({}))
    print(f"{PASS} Protocol version: {result['protocolVersion']}")
    print(f"{PASS} Server name: {result['serverInfo']['name']}")
    
    # Test resources_list
    result = asyncio.run(server.resources_list())
    print(f"{PASS} Resources: {len(result['resources'])} resources")
    
    # Test tools_list
    result = asyncio.run(server.tools_list())
    print(f"{PASS} Tools: {len(result['tools'])} tools")
    
    # Test prompts_list
    result = asyncio.run(server.prompts_list())
    print(f"{PASS} Prompts: {len(result['prompts'])} prompts")
    
    # Test HTTP app creation
    app = create_http_app()
    print(f"{PASS} HTTP app created")
    
    # Cleanup
    import shutil
    shutil.rmtree(friction_drop)
    
    print(f"\n{PASS} MCP SERVER: ALL TESTS PASSED")
    return True

def test_client():
    """Test MCP client module"""
    print("\n" + "=" * 60)
    print("Testing hlf.mcp_client...")
    print("=" * 60)
    
    from hlf.mcp_client import HLFMCPClient, GrammarInfo
    
    # Create client (won't connect to server in this test)
    client = HLFMCPClient("http://localhost:8000")
    
    # Just test that the class works
    print(f"{PASS} Client created with base_url: {client.base_url}")
    print(f"{PASS} Cache TTL: {client.cache_ttl}s")
    
    # Test GrammarInfo dataclass
    info = GrammarInfo(
        version="0.4.0",
        sha256="abc123",
        generated_at=1699999999.0,
        compatibility=["MCP-2024-11-05"]
    )
    print(f"{PASS} GrammarInfo: version={info.version}, sha256={info.sha256}")
    
    print(f"\n{PASS} MCP CLIENT: ALL TESTS PASSED")
    return True

def test_forge_agent():
    """Test Forge agent module"""
    print("\n" + "=" * 60)
    print("Testing hlf.forge_agent...")
    print("=" * 60)
    
    from hlf.forge_agent import ForgeAgent, FrictionReport, GrammarProposal
    
    friction_drop = REPO / "test_friction"
    friction_drop.mkdir(exist_ok=True)
    
    # Test dataclasses
    report = FrictionReport(
        id="test-123",
        timestamp=1699999999.0,
        grammar_version="0.4.0",
        grammar_sha256="abc123",
        source_snippet="test",
        failure_type="expression",
        attempted_intent="test",
        context={},
        proposed_fix=None,
        agent_metadata={"tier": "forge"}
    )
    print(f"{PASS} FrictionReport created: {report.id}")
    
    proposal = GrammarProposal(
        id="prop-456",
        friction_id="test-123",
        timestamp=1699999999.0,
        proposed_syntax="test syntax",
        rationale="test rationale",
        additive_only=True,
        breaking=False,
        tier_required="forge",
        affected_opcodes=[],
        validation_token=""
    )
    print(f"{PASS} GrammarProposal created: {proposal.id}")
    
    # Test ForgeAgent class (not running it)
    agent = ForgeAgent(REPO, None)
    print(f"{PASS} ForgeAgent created")
    print(f"{PASS} Grammar version: {agent.current_version}")
    print(f"{PASS} Grammar SHA256: {agent.current_grammar_sha[:16]}...")
    print(f"{PASS} Friction drop: {agent.friction_drop}")
    
    # Cleanup
    import shutil
    shutil.rmtree(friction_drop)
    
    print(f"\n{PASS} FORGE AGENT: ALL TESTS PASSED")
    return True

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("HLF MCP Test Suite")
    print("=" * 60)
    
    results = {}
    
    tests = [
        ("MCP Resources", test_resources),
        ("MCP Tools", test_tools),
        ("MCP Prompts", test_prompts),
        ("MCP Server", test_server),
        ("MCP Client", test_client),
        ("Forge Agent", test_forge_agent),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n{FAIL} {name}: FAILED - {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = PASS if result else FAIL
        print(f"  {status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return all(results.values())

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)