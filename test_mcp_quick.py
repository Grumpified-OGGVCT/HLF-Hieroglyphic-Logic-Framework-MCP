#!/usr/bin/env python3
"""Quick test of MCP modules."""

import sys
sys.path.insert(0, '.')

def test_imports():
    print("Testing imports...")
    
    # Test mcp_resources
    try:
        from hlf.mcp_resources import HLFResourceProvider
        print("  mcp_resources: OK")
    except Exception as e:
        print(f"  mcp_resources: ERROR - {e}")
        return False
    
    # Test mcp_tools
    try:
        from hlf.mcp_tools import HLFToolProvider
        print("  mcp_tools: OK")
    except Exception as e:
        print(f"  mcp_tools: ERROR - {e}")
        return False
    
    # Test mcp_client
    try:
        from hlf.mcp_client import HLFMCPClient
        print("  mcp_client: OK")
    except Exception as e:
        print(f"  mcp_client: ERROR - {e}")
        return False
    
    # Test forge_agent
    try:
        from hlf.forge_agent import ForgeAgent
        print("  forge_agent: OK")
    except Exception as e:
        print(f"  forge_agent: ERROR - {e}")
        return False
    
    assert True

def test_resource_provider():
    print("\nTesting HLFResourceProvider...")
    from pathlib import Path
    from hlf.mcp_resources import HLFResourceProvider
    
    repo_root = Path('.')
    provider = HLFResourceProvider(repo_root)
    
    # Test list resources
    resources = provider.list_resources()
    print(f"  Resources: {len(resources)} found")
    for r in resources[:3]:
        print(f"    - {r.uri}: {r.name}")
    
    # Test get version
    version = provider._get_version_info()
    print(f"  Version: {version['version']}")
    print(f"  SHA256: {version['grammar_sha256'][:16]}...")
    
    assert True

def test_tool_provider():
    print("\nTesting HLFToolProvider...")
    from pathlib import Path
    from hlf.mcp_tools import HLFToolProvider
    from hlf.mcp_resources import HLFResourceProvider
    
    repo_root = Path('.')
    friction_drop = Path.home() / '.sovereign' / 'friction_test'
    friction_drop.mkdir(parents=True, exist_ok=True)
    
    resource_provider = HLFResourceProvider(repo_root)
    tool_provider = HLFToolProvider(resource_provider=resource_provider, friction_drop=friction_drop)
    
    # Test list tools
    tools = tool_provider.list_tools()
    print(f"  Tools: {len(tools)} found")
    for t in tools[:3]:
        print(f"    - {t.name}")
    
    assert True

def test_client():
    print("\nTesting HLFMCPClient...")
    from hlf.mcp_client import HLFMCPClient
    
    client = HLFMCPClient("http://localhost:8000")
    print(f"  Base URL: {client.base_url}")
    print(f"  Cache TTL: {client.cache_ttl}")
    
    assert True


def _run_test(name, func):
    try:
        func()
        return name, True
    except Exception as exc:
        print(f"  ERROR [{name}]: {exc}")
        return name, False

def main():
    print("=" * 60)
    print("HLF MCP Module Tests")
    print("=" * 60)
    
    results = []
    
    # Test imports
    results.append(_run_test("Imports", test_imports))
    
    # Test resource provider
    try:
        results.append(_run_test("ResourceProvider", test_resource_provider))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("ResourceProvider", False))
    
    # Test tool provider
    try:
        results.append(_run_test("ToolProvider", test_tool_provider))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("ToolProvider", False))
    
    # Test client
    try:
        results.append(_run_test("Client", test_client))
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append(("Client", False))
    
    print("\n" + "=" * 60)
    print("Results:")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)