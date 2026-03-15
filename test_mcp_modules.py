#!/usr/bin/env python3
"""Test MCP modules independently of lexer/parser."""

from pathlib import Path
import sys

def main():
    print("=" * 60)
    print("HLF MCP MODULE TESTS")
    print("=" * 60)
    
    # Test 1: Resources module
    print("\n[Test 1] Loading mcp_resources...")
    try:
        from hlf.mcp_resources import HLFResourceProvider, Resource, ResourceTemplate
        print("  [PASS] mcp_resources imports OK")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 2: Tools module
    print("\n[Test 2] Loading mcp_tools...")
    try:
        from hlf.mcp_tools import HLFToolProvider, ToolDefinition
        print("  [PASS] mcp_tools imports OK")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 3: Prompts module
    print("\n[Test 3] Loading mcp_prompts...")
    try:
        from hlf.mcp_prompts import HLFPromptProvider, PromptArgument, PromptDefinition
        print("  [PASS] mcp_prompts imports OK")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 4: MCP client
    print("\n[Test 4] Loading mcp_client...")
    try:
        from hlf.mcp_client import HLFMCPClient, GrammarInfo
        print("  [PASS] mcp_client imports OK")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 5: Resource provider
    print("\n[Test 5] Creating resource provider...")
    try:
        repo_root = Path('.').resolve()
        resources = HLFResourceProvider(repo_root)
        print("  [PASS] Resource provider created")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 6: List resources
    print("\n[Test 6] Listing resources...")
    try:
        resource_list = resources.list_resources()
        print(f"  [PASS] Found {len(resource_list)} resources")
        for r in resource_list:
            print(f"        - {r.uri}: {r.name}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 7: List resource templates
    print("\n[Test 7] Listing resource templates...")
    try:
        templates = resources.list_resource_templates()
        print(f"  [PASS] Found {len(templates)} templates")
        for t in templates:
            print(f"        - {t.uri_template}: {t.name}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 8: Tool provider
    print("\n[Test 8] Creating tool provider...")
    try:
        friction_drop = Path.home() / '.sovereign' / 'friction'
        tools = HLFToolProvider(resource_provider=resources, friction_drop=friction_drop)
        print("  [PASS] Tool provider created")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 9: List tools
    print("\n[Test 9] Listing tools...")
    try:
        tool_list = tools.list_tools()
        print(f"  [PASS] Found {len(tool_list)} tools")
        for t in tool_list[:5]:  # Show first 5
            print(f"        - {t.name}")
        if len(tool_list) > 5:
            print(f"        ... and {len(tool_list) - 5} more")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 10: Prompt provider
    print("\n[Test 10] Creating prompt provider...")
    try:
        prompts = HLFPromptProvider()
        print("  [PASS] Prompt provider created")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 11: List prompts
    print("\n[Test 11] Listing prompts...")
    try:
        prompt_list = prompts.list_prompts()
        print(f"  [PASS] Found {len(prompt_list)} prompts")
        for p in prompt_list:
            print(f"        - {p.name}: {len(p.arguments)} args")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 12: Get init prompt
    print("\n[Test 12] Getting init prompt...")
    try:
        init_prompt = prompts.get_prompt('hlf_initialize_agent', {'tier': 'forge', 'profile': 'P0'})
        print(f"  [PASS] Init prompt: {len(init_prompt)} chars")
        # Check for key content
        assert 'HLF MODE' in init_prompt, "Missing HLF MODE marker"
        assert 'forge' in init_prompt.lower(), "Missing tier in prompt"
        assert 'P0' in init_prompt, "Missing profile in prompt"
        print("  [PASS] Content validation OK")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 13: Intent prompt
    print("\n[Test 13] Getting intent prompt...")
    try:
        intent_prompt = prompts.get_prompt('hlf_express_intent', {'intent': 'read a file and filter errors'})
        print(f"  [PASS] Intent prompt: {len(intent_prompt)} chars")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 14: Tool definitions
    print("\n[Test 14] Checking tool definitions...")
    try:
        tool_names = [t.name for t in tool_list]
        expected_tools = ['hlf_compile', 'hlf_execute', 'hlf_validate', 'hlf_friction_log', 
                         'hlf_self_observe', 'hlf_get_version', 'hlf_compose', 'hlf_decompose',
                         'hlf_analyze', 'hlf_optimize']
        for tool in expected_tools:
            assert tool in tool_names, f"Missing tool: {tool}"
        print(f"  [PASS] All {len(expected_tools)} expected tools present")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 15: Friction logging
    print("\n[Test 15] Testing friction log...")
    try:
        friction_drop = Path('./test_friction_drop')
        friction_drop.mkdir(exist_ok=True)
        tools_friction = HLFToolProvider(resource_provider=resources, friction_drop=friction_drop)
        
        result = tools_friction.call_tool('hlf_friction_log', {
            'source_snippet': 'test → main',
            'failure_type': 'expression',
            'attempted_intent': 'Testing friction logging'
        })
        
        assert result['success'], f"Friction log failed: {result}"
        print(f"  [PASS] Friction logged: {result['friction_id']}")
        
        # Cleanup
        import shutil
        shutil.rmtree(friction_drop)
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 16: MCP Client initialization
    print("\n[Test 16] Testing MCP client...")
    try:
        client = HLFMCPClient(base_url="http://localhost:8000")
        print("  [PASS] MCP client created")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    # Test 17: Version check
    print("\n[Test 17] Testing version check...")
    try:
        # Force fresh version fetch
        has_change = client.check_version_change()
        print(f"  [PASS] Version check OK (change detected: {has_change})")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())