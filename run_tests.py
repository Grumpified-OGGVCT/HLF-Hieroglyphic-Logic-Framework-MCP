#!/usr/bin/env python3
"""Run MCP basic tests."""
import sys
sys.path.insert(0, '.')

from pathlib import Path

# Test 1: Resources
print('Test 1: MCP Resources...')
try:
    from hlf.mcp_resources import HLFResourceProvider
    
    repo_root = Path('.')
    provider = HLFResourceProvider(repo_root)
    
    resources = provider.list_resources()
    print(f'  Found {len(resources)} resources')
    for r in resources[:3]:
        print(f'    - {r.uri}: {r.name}')
    
    version_info = provider._get_version_info()
    print(f'  Version: {version_info["version"]}')
    print('  PASS: Resources work')
except Exception as e:
    print(f'  FAIL: {e}')

# Test 2: Tools
print('')
print('Test 2: MCP Tools...')
try:
    from hlf.mcp_tools import HLFToolProvider
    from hlf.mcp_resources import HLFResourceProvider
    
    repo_root = Path('.')
    friction_drop = Path.home() / '.sovereign' / 'friction_test'
    friction_drop.mkdir(parents=True, exist_ok=True)
    
    provider = HLFResourceProvider(repo_root)
    tools = HLFToolProvider(resource_provider=provider, vm_executor=None, friction_drop=friction_drop)
    
    tool_list = tools.list_tools()
    print(f'  Found {len(tool_list)} tools')
    for t in tool_list[:3]:
        print(f'    - {t.name}')
    print('  PASS: Tools work')
except Exception as e:
    print(f'  FAIL: {e}')

# Test 3: Prompts
print('')
print('Test 3: MCP Prompts...')
try:
    from hlf.mcp_prompts import HLFPromptProvider
    
    prompts = HLFPromptProvider()
    prompt_list = prompts.list_prompts()
    print(f'  Found {len(prompt_list)} prompts')
    
    init_prompt = prompts.get_prompt('hlf_initialize_agent', {'tier': 'forge', 'profile': 'P0'})
    print(f'  Init prompt length: {len(init_prompt)} chars')
    assert 'HLF MODE' in init_prompt
    print('  PASS: Prompts work')
except Exception as e:
    print(f'  FAIL: {e}')

# Test 4: Server
print('')
print('Test 4: MCP Server...')
try:
    from hlf.mcp_server_complete import MCPServer
    
    repo_root = Path('.')
    friction_drop = Path.home() / '.sovereign' / 'friction_test'
    
    server = MCPServer(repo_root, friction_drop)
    
    # Initialize
    result = {'protocolVersion': '2024-11-05', 'capabilities': server.capabilities}
    print(f'  Protocol: {result["protocolVersion"]}')
    print(f'  Capabilities: {list(result["capabilities"].keys())}')
    print('  PASS: Server works')
except Exception as e:
    print(f'  FAIL: {e}')

# Test 5: Client
print('')
print('Test 5: MCP Client...')
try:
    from hlf.mcp_client import HLFMCPClient
    
    client = HLFMCPClient('http://localhost:8000')
    print(f'  Base URL: {client.base_url}')
    print(f'  Cache TTL: {client.cache_ttl}')
    print('  PASS: Client works')
except Exception as e:
    print(f'  FAIL: {e}')

# Test 6: Metrics
print('')
print('Test 6: MCP Metrics...')
try:
    from hlf.mcp_metrics import get_metrics, record_tool_call
    
    metrics = get_metrics()
    metrics_path = Path.home() / '.sovereign' / 'mcp_metrics' / 'stats.json'
    print(f'  Metrics path: {metrics_path}')
    print(f'  Stats: {metrics._stats["total_uses"]} uses')
    
    # Test recording
    record_tool_call('test_tool', success=True, duration_ms=100)
    print('  PASS: Metrics work')
except Exception as e:
    print(f'  FAIL: {e}')

print('')
print('========================================')
print('MCP Basic Tests Complete')
print('========================================')