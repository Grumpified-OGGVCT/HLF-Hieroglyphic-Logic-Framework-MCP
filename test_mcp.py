#!/usr/bin/env python3
"""
Simple test for HLF MCP infrastructure.
Bypasses the pre-existing HLF package which has import issues.
"""

import sys
from pathlib import Path
import json
import time

# Add repo to path
REPO_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

# Import MCP components DIRECTLY, not through hlf package
# This bypasses the broken hlf/__init__.py imports

def test_resource_provider():
    """Test the resource provider can list and read resources."""
    print("\n[TEST] Resource Provider")
    print("-" * 40)
    
    # Direct import
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "mcp_resources", 
        REPO_ROOT / "hlf" / "mcp_resources.py"
    )
    mcp_resources = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_resources)
    
    HLFResourceProvider = mcp_resources.HLFResourceProvider
    
    provider = HLFResourceProvider(REPO_ROOT)
    
    # List resources
    resources = provider.list_resources()
    print(f"  Listed {len(resources)} resources")
    
    for r in resources[:5]:  # Show first 5
        print(f"    - {r.name}: {r.uri}")
    
    # Test version
    try:
        version_resource = provider.read_resource("hlf://version")
        version_data = json.loads(version_resource.content)
        print(f"  Version: {version_data.get('version', 'unknown')}")
        print(f"  SHA256: {version_data.get('grammar_sha256', 'unknown')[:16]}...")
        print("  [PASS] Version resource works")
        return True
    except Exception as e:
        print(f"  [FAIL] Version resource: {e}")
        return False


def test_tool_definitions():
    """Test that tool definitions are valid."""
    print("\n[TEST] Tool Definitions")
    print("-" * 40)
    
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "mcp_tools", 
        REPO_ROOT / "hlf" / "mcp_tools.py"
    )
    mcp_tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_tools)
    
    HLFToolProvider = mcp_tools.HLFToolProvider
    
    # Create a mock resource provider
    class MockResourceProvider:
        def _get_version_info(self):
            return {"version": "0.5.0", "grammar_sha256": "test"}
    
    with __import__('tempfile').TemporaryDirectory() as tmpdir:
        provider = HLFToolProvider(
            resource_provider=MockResourceProvider(),
            vm_executor=None,
            friction_drop=Path(tmpdir)
        )
        
        # List tools
        tools = provider.list_tools()
        print(f"  Listed {len(tools)} tools:")
        
        for t in tools[:5]:  # Show first 5
            print(f"    - {t.name}: {t.description[:50]}...")
        
        # Check required tools exist
        required_tools = ["hlf_compile", "hlf_execute", "hlf_validate", "hlf_friction_log", "hlf_get_version"]
        tool_names = [t.name for t in tools]
        
        all_present = True
        for req in required_tools:
            if req in tool_names:
                print(f"  [PASS] {req} present")
            else:
                print(f"  [FAIL] {req} missing")
                all_present = False
        
        return all_present


def test_prompt_definitions():
    """Test that prompt definitions are valid."""
    print("\n[TEST] Prompt Definitions")
    print("-" * 40)
    
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "mcp_prompts", 
        REPO_ROOT / "hlf" / "mcp_prompts.py"
    )
    mcp_prompts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_prompts)
    
    HLFPromptProvider = mcp_prompts.HLFPromptProvider
    
    provider = HLFPromptProvider()
    
    # List prompts
    prompts = provider.list_prompts()
    print(f"  Listed {len(prompts)} prompts:")
    
    for p in prompts:
        print(f"    - {p.name}: {p.description[:50]}...")
    
    # Test initialization prompt
    try:
        prompt_text = provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge",
            "profile": "P0"
        })
        print(f"  Init prompt length: {len(prompt_text)} chars")
        
        # Check for key content
        checks = ["HLF", "GRAMMAR", "tier", "forge", "gas"]
        all_present = True
        for check in checks:
            if check.lower() in prompt_text.lower():
                print(f"  [PASS] Contains '{check}'")
            else:
                print(f"  [FAIL] Missing '{check}'")
                all_present = False
        
        return all_present
    except Exception as e:
        print(f"  [FAIL] Prompt generation: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_friction_log():
    """Test friction logging functionality."""
    print("\n[TEST] Friction Logging")
    print("-" * 40)
    
    import importlib.util
    import tempfile
    
    spec = importlib.util.spec_from_file_location(
        "mcp_tools", 
        REPO_ROOT / "hlf" / "mcp_tools.py"
    )
    mcp_tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_tools)
    
    HLFToolProvider = mcp_tools.HLFToolProvider
    
    class MockResourceProvider:
        def _get_version_info(self):
            return {"version": "0.5.0", "grammar_sha256": "test123"}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = HLFToolProvider(
            resource_provider=MockResourceProvider(),
            vm_executor=None,
            friction_drop=Path(tmpdir)
        )
        
        result = provider.call_tool("hlf_friction_log", {
            "source_snippet": "test code",
            "failure_type": "expression",
            "attempted_intent": "I tried to express a complex pattern"
        })
        
        print(f"  Result: {result.get('success', False)}")
        print(f"  Friction ID: {result.get('friction_id', 'none')}")
        
        # Check file was created
        friction_files = list(Path(tmpdir).glob("*.hlf"))
        if friction_files:
            print(f"  Friction files created: {len(friction_files)}")
            # Show first file content
            content = json.loads(friction_files[0].read_text())
            print(f"  File keys: {list(content.keys())}")
            print("  [PASS] Friction logging works")
            return True
        else:
            print("  [FAIL] No friction files created")
            return False


def test_client():
    """Test MCP client initialization."""
    print("\n[TEST] MCP Client")
    print("-" * 40)
    
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "mcp_client", 
        REPO_ROOT / "hlf" / "mcp_client.py"
    )
    mcp_client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mcp_client)
    
    HLFMCPClient = mcp_client.HLFMCPClient
    
    # Create client (won't connect without server)
    client = HLFMCPClient("http://localhost:8000")
    
    print(f"  Base URL: {client.base_url}")
    print(f"  Cache TTL: {client.cache_ttl}")
    print("  [PASS] Client instantiated")
    
    # Check methods exist
    required_methods = [
        "get_version", "get_grammar", "get_dictionaries",
        "get_init_prompt", "compile", "execute", 
        "validate", "friction_log", "get_system_prompt"
    ]
    
    all_present = True
    for method in required_methods:
        if hasattr(client, method):
            print(f"  [PASS] Has method '{method}'")
        else:
            print(f"  [FAIL] Missing method '{method}'")
            all_present = False
    
    return all_present


def test_forge_agent():
    """Test Forge agent initialization."""
    print("\n[TEST] Forge Agent")
    print("-" * 40)
    
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "forge_agent", 
        REPO_ROOT / "hlf" / "forge_agent.py"
    )
    forge_agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(forge_agent)
    
    FrictionReport = forge_agent.FrictionReport
    GrammarProposal = forge_agent.GrammarProposal
    
    # Test dataclasses exist
    report = FrictionReport(
        id="test-123",
        timestamp=time.time(),
        grammar_version="0.5.0",
        grammar_sha256="abc123",
        source_snippet="test code",
        failure_type="expression",
        attempted_intent="test intent",
        context={},
        proposed_fix=None,
        agent_metadata={"tier": "forge"}
    )
    
    print(f"  FrictionReport created: {report.id}")
    print(f"  Failure type: {report.failure_type}")
    
    proposal = GrammarProposal(
        id="prop-456",
        friction_id="test-123",
        timestamp=time.time(),
        proposed_syntax="new syntax",
        rationale="test rationale",
        additive_only=True,
        breaking=False,
        tier_required="forge",
        affected_opcodes=[],
        validation_token=""
    )
    
    print(f"  GrammarProposal created: {proposal.id}")
    print("  [PASS] Forge agent dataclasses work")
    
    return True


def test_file_structure():
    """Test that all expected files exist."""
    print("\n[TEST] File Structure")
    print("-" * 40)
    
    expected_files = [
        "hlf/mcp_resources.py",
        "hlf/mcp_tools.py",
        "hlf/mcp_prompts.py",
        "hlf/mcp_server_complete.py",
        "hlf/mcp_client.py",
        "hlf/forge_agent.py",
        "BUILD_GUIDE.md",
        "TODO.md",
    ]
    
    all_exist = True
    for file_path in expected_files:
        full_path = REPO_ROOT / file_path
        if full_path.exists():
            size = full_path.stat().st_size
            print(f"  [PASS] {file_path} ({size:,} bytes)")
        else:
            print(f"  [FAIL] {file_path} MISSING")
            all_exist = False
    
    return all_exist


def main():
    print("=" * 60)
    print("HLF MCP INFRASTRUCTURE TEST SUITE")
    print("=" * 60)
    print(f"Testing directory: {REPO_ROOT}")
    
    results = []
    
    # Run tests
    results.append(("File Structure", test_file_structure()))
    results.append(("Resource Provider", test_resource_provider()))
    results.append(("Tool Definitions", test_tool_definitions()))
    results.append(("Prompt Definitions", test_prompt_definitions()))
    results.append(("Friction Logging", test_friction_log()))
    results.append(("MCP Client", test_client()))
    results.append(("Forge Agent", test_forge_agent()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    # Write results as metrics for MCP exposure
    metrics_path = REPO_ROOT / "mcp_metrics.json"
    metrics = {
        "timestamp": time.time(),
        "test_suite": "mcp_infrastructure",
        "total_tests": total,
        "passed_tests": passed,
        "failed_tests": total - passed,
        "success_rate": round(passed / total * 100, 1) if total > 0 else 0,
        "results": {name: result for name, result in results}
    }
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"\nMetrics saved to: {metrics_path}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())