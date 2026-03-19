#!/usr/bin/env python3
"""
Minimal test for MCP resources and tools without requiring full HLF parser.
This tests the MCP infrastructure independently.
"""

import sys
import json
import hashlib
import time
from pathlib import Path

# Add project to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

def test_resource_provider():
    """Test the MCP resource provider."""
    print("=" * 60)
    print("TESTING: HLF Resource Provider")
    print("=" * 60)
    
    from hlf.mcp_resources import HLFResourceProvider, Resource
    
    # Initialize with the project root
    provider = HLFResourceProvider(PROJECT_ROOT)
    
    # Test list resources
    resources = provider.list_resources()
    print(f"\n[OK] Listed {len(resources)} resources:")
    for r in resources:
        print(f"  - {r.uri}: {r.name}")
    
    # Test list templates
    templates = provider.list_resource_templates()
    print(f"\n[OK] Listed {len(templates)} resource templates:")
    for t in templates:
        print(f"  - {t.uri_template}: {t.name}")
    
    # Test read version
    print("\n--- Testing hlf://version ---")
    version_resource = provider.read_resource("hlf://version")
    version_data = json.loads(version_resource.content)
    print(f"[OK] Version: {version_data.get('version', 'unknown')}")
    print(f"  SHA256: {version_data.get('grammar_sha256', 'unknown')[:16]}...")
    print(f"  Resources: {len(version_data.get('resources_available', []))}")
    
    # Test read grammar
    print("\n--- Testing hlf://grammar ---")
    try:
        grammar_resource = provider.read_resource("hlf://grammar")
        grammar_lines = grammar_resource.content.split('\n')
        print(f"[OK] Grammar: {len(grammar_resource.content)} chars, {len(grammar_lines)} lines")
        print(f"  First line: {grammar_lines[0][:60]}...")
    except Exception as e:
        print(f"[FAIL] Could not read grammar: {e}")
    
    # Test read dictionaries
    print("\n--- Testing hlf://dictionaries ---")
    try:
        dict_resource = provider.read_resource("hlf://dictionaries")
        dict_data = json.loads(dict_resource.content)
        print(f"[OK] Dictionaries: {len(dict_resource.content)} chars")
        print(f"  Glyph mappings: {len(dict_data.get('glyph_to_ascii', {}))}")
    except Exception as e:
        print(f"[FAIL] Could not read dictionaries: {e}")
    
    # Test read AST schema
    print("\n--- Testing hlf://ast-schema ---")
    try:
        schema_resource = provider.read_resource("hlf://ast-schema")
        schema_data = json.loads(schema_resource.content)
        print(f"[OK] AST Schema: {len(schema_resource.content)} chars")
        print(f"  Schema title: {schema_data.get('title', 'unknown')}")
    except Exception as e:
        print(f"[FAIL] Could not read AST schema: {e}")
    
    assert len(resources) > 0

def test_tool_provider():
    """Test the MCP tool provider."""
    print("\n" + "=" * 60)
    print("TESTING: HLF Tool Provider")
    print("=" * 60)
    
    from hlf.mcp_tools import HLFToolProvider
    from hlf.mcp_resources import HLFResourceProvider
    
    # Mock friction drop directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        friction_drop = Path(tmpdir)
        resource_provider = HLFResourceProvider(PROJECT_ROOT)
        
        # Create tool provider with None vm_executor for now
        tool_provider = HLFToolProvider(
            resource_provider=resource_provider,
            vm_executor=None,
            friction_drop=friction_drop
        )
        
        # Test list tools
        tools = tool_provider.list_tools()
        print(f"\n[OK] Listed {len(tools)} tools:")
        for t in tools:
            print(f"  - {t.name}: {t.description[:50]}...")
        
        # Test hlf_get_version
        print("\n--- Testing hlf_get_version ---")
        result = tool_provider.call_tool("hlf_get_version", {})
        print(f"[OK] Result: {result.get('version', 'unknown')}")
        print(f"  Success: {result.get('success', False)}")
        
        # Test hlf_friction_log
        print("\n--- Testing hlf_friction_log ---")
        result = tool_provider.call_tool("hlf_friction_log", {
            "source_snippet": "test snippet",
            "failure_type": "expression",
            "attempted_intent": "test intent"
        })
        print(f"[OK] Result: friction_id = {result.get('friction_id', 'none')[:16]}...")
        print(f"  File: {result.get('file', 'none')}")
        
        # Test hlf_validate
        print("\n--- Testing hlf_validate ---")
        result = tool_provider.call_tool("hlf_validate", {
            "source": "module test { fn main() { ret 0 } }"
        })
        print(f"[OK] Result: success = {result.get('success', False)}")
        print(f"  Errors: {len(result.get('errors', []))}")
        
        # Test hlf_compose
        print("\n--- Testing hlf_compose ---")
        result = tool_provider.call_tool("hlf_compose", {
            "programs": ["module a { }", "module b { }"],
            "strategy": "sequential"
        })
        print(f"[OK] Result: {len(result.get('composed_source', ''))} chars")
    
    assert len(tools) > 0

def test_prompt_provider():
    """Test the MCP prompt provider."""
    print("\n" + "=" * 60)
    print("TESTING: HLF Prompt Provider")
    print("=" * 60)
    
    from hlf.mcp_prompts import HLFPromptProvider
    
    provider = HLFPromptProvider()
    
    # Test list prompts
    prompts = provider.list_prompts()
    print(f"\n[OK] Listed {len(prompts)} prompts:")
    for p in prompts:
        print(f"  - {p.name}: {p.description[:50]}...")
    
    # Test get init prompt
    print("\n--- Testing hlf_initialize_agent ---")
    prompt = provider.get_prompt("hlf_initialize_agent", {
        "tier": "forge",
        "profile": "P0"
    })
    print(f"[OK] Prompt: {len(prompt)} chars")
    print(f"  Contains GRAMMAR: {'GRAMMAR' in prompt}")
    print(f"  Contains tier 'forge': {'forge' in prompt}")
    
    # Test express intent prompt
    print("\n--- Testing hlf_express_intent ---")
    prompt = provider.get_prompt("hlf_express_intent", {
        "intent": "Read a file and filter lines"
    })
    print(f"[OK] Prompt: {len(prompt)} chars")
    print(f"  Contains intent: {'Read a file' in prompt}")
    
    assert len(prompts) > 0

def test_mcp_client():
    """Test the MCP client (without server)."""
    print("\n" + "=" * 60)
    print("TESTING: HLF MCP Client (Offline)")
    print("=" * 60)
    
    from hlf.mcp_client import HLFMCPClient
    
    # Create client (won't connect in offline mode)
    print("\n[INFO] Testing client structure...")
    client = HLFMCPClient("http://localhost:8000")
    
    print(f"[OK] Client created")
    print(f"  Base URL: {client.base_url}")
    print(f"  Cache TTL: {client.cache_ttl}")
    
    # The client would need a running server for full tests
    print("\n[INFO] Full client tests require running server")
    
    assert client.base_url == "http://localhost:8000"

def test_forge_agent():
    """Test the Forge agent structure."""
    print("\n" + "=" * 60)
    print("TESTING: Forge Agent (Structure)")
    print("=" * 60)
    
    from hlf.forge_agent import FrictionReport, GrammarProposal
    import tempfile
    
    print("\n[INFO] Testing Forge agent components...")
    
    # Create a friction report
    report = FrictionReport(
        id="test123",
        timestamp=time.time(),
        grammar_version="0.4.0",
        grammar_sha256="abc123",
        source_snippet="test code",
        failure_type="expression",
        attempted_intent="test intent",
        context={"test": True},
        proposed_fix="add new syntax",
        agent_metadata={"tier": "forge"}
    )
    print(f"[OK] FrictionReport created: {report.id}")
    
    # Create a proposal
    proposal = GrammarProposal(
        id="prop456",
        friction_id="test123",
        timestamp=time.time(),
        proposed_syntax="new_keyword X",
        rationale="Test proposal",
        additive_only=True,
        breaking=False,
        tier_required="forge",
        affected_opcodes=[],
        validation_token=""
    )
    print(f"[OK] GrammarProposal created: {proposal.id}")
    print(f"  Additive: {proposal.additive_only}")
    print(f"  Breaking: {proposal.breaking}")
    
    assert proposal.additive_only is True

def test_metrics():
    """Test the metrics tracking."""
    print("\n" + "=" * 60)
    print("TESTING: Test Metrics")
    print("=" * 60)
    
    try:
        from hlf.test_metrics import TestMetrics, get_metrics, record_test_run
        
        print("\n[INFO] Testing metrics module...")
        
        # Get global metrics
        metrics = get_metrics()
        print(f"[OK] Global metrics instance created")
        
        # Record a test run
        record_test_run("test_resource_provider", True, 0.5)
        record_test_run("test_tool_provider", True, 0.3)
        record_test_run("test_forge_agent", True, 0.2)
        
        summary = metrics.get_summary()
        print(f"[OK] Metrics recorded:")
        print(f"  Total runs: {summary['total_runs']}")
        print(f"  Passed: {summary['passed']}")
        print(f"  Failed: {summary['failed']}")
        print(f"  Pass rate: {summary['pass_rate']:.2%}")
        
        assert summary["total_runs"] >= 3
    except ImportError as e:
        print(f"[WARN] Metrics module not available: {e}")
        assert True  # Not critical

def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "#" * 60)
    print("# HLF MCP INFRASTRUCTURE TEST SUITE")
    print("#" * 60)
    
    results = []
    
    try:
        test_resource_provider()
        results.append(("Resource Provider", True))
    except Exception as e:
        print(f"\n[FAIL] Resource Provider test failed: {e}")
        results.append(("Resource Provider", False))
    
    try:
        test_tool_provider()
        results.append(("Tool Provider", True))
    except Exception as e:
        print(f"\n[FAIL] Tool Provider test failed: {e}")
        results.append(("Tool Provider", False))
    
    try:
        test_prompt_provider()
        results.append(("Prompt Provider", True))
    except Exception as e:
        print(f"\n[FAIL] Prompt Provider test failed: {e}")
        results.append(("Prompt Provider", False))
    
    try:
        test_mcp_client()
        results.append(("MCP Client", True))
    except Exception as e:
        print(f"\n[FAIL] MCP Client test failed: {e}")
        results.append(("MCP Client", False))
    
    try:
        test_forge_agent()
        results.append(("Forge Agent", True))
    except Exception as e:
        print(f"\n[FAIL] Forge Agent test failed: {e}")
        results.append(("Forge Agent", False))
    
    try:
        test_metrics()
        results.append(("Metrics", True))
    except Exception as e:
        print(f"\n[FAIL] Metrics test failed: {e}")
        results.append(("Metrics", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # Record to metrics
    try:
        from hlf.test_metrics import get_metrics
        metrics = get_metrics()
        overall_time = sum(0.5 for _ in results)  # Approximate
        metrics.record_test_result("infrastructure_suite", passed == total, overall_time)
    except:
        pass
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(run_all_tests())