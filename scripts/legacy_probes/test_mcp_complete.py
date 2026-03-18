#!/usr/bin/env python3
"""Complete test for HLF MCP implementation."""

import sys
sys.path.insert(0, '.')

from pathlib import Path

def test_imports():
    """Test 1: All imports work."""
    print('TEST 1: Imports...')
    try:
        from hlf.mcp_resources import HLFResourceProvider
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_prompts import HLFPromptProvider
        from hlf.mcp_client import HLFMCPClient
        from hlf.mcp_metric import HLFTestMetrics, VERIFIED_METRICS
        print('  PASS: All imports successful')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)

def test_resources():
    """Test 2: Resources work."""
    print('TEST 2: Resources...')
    try:
        from hlf.mcp_resources import HLFResourceProvider
        provider = HLFResourceProvider(Path('.'))
        resources = provider.list_resources()
        assert len(resources) >= 4, f"Expected >= 4 resources, got {len(resources)}"
        
        grammar = provider.read_resource('hlf://grammar')
        assert grammar.content is not None, "Grammar content is None"
        print('  PASS: Resources working')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)

def test_tools():
    """Test 3: Tools work."""
    print('TEST 3: Tools...')
    try:
        from hlf.mcp_resources import HLFResourceProvider
        from hlf.mcp_tools import HLFToolProvider
        resource_provider = HLFResourceProvider(Path('.'))
        tools = HLFToolProvider(resource_provider=resource_provider)
        tool_list = tools.list_tools()
        names = [t.name for t in tool_list]
        
        assert 'hlf_compile' in names, f"hlf_compile not in {names}"
        assert 'hlf_execute' in names, f"hlf_execute not in {names}"
        assert 'hlf_friction_log' in names, f"hlf_friction_log not in {names}"
        print('  PASS: Tools working')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)

def test_prompts():
    """Test 4: Prompts work."""
    print('TEST 4: Prompts...')
    try:
        from hlf.mcp_prompts import HLFPromptProvider
        prompts = HLFPromptProvider()
        prompt_list = prompts.list_prompts()
        names = [p.name for p in prompt_list]
        
        assert 'hlf_initialize_agent' in names, f"hlf_initialize_agent not in {names}"
        
        init_prompt = prompts.get_prompt('hlf_initialize_agent', {'tier': 'forge', 'profile': 'P0'})
        assert 'HLF MODE' in init_prompt, "HLF MODE not in prompt"
        print('  PASS: Prompts working')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)

def test_metrics():
    """Test 5: Metrics work."""
    print('TEST 5: Metrics...')
    try:
        from hlf.mcp_metric import HLFTestMetrics
        metrics = HLFTestMetrics()
        results = metrics.run_all_tests()
        
        assert "summary" in results
        assert "tests" in results
        assert results["summary"]["total"] >= 5, (
            f"Expected >= 5 tracked metrics, got {results['summary']['total']}"
        )
        assert "tools" in results["tests"], "Expected tools metric in results"
        print('  PASS: Metrics working')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)

def test_client():
    """Test 6: Client works."""
    print('TEST 6: Client...')
    try:
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient('http://localhost:8000')

        assert client.base_url == 'http://localhost:8000'
        assert hasattr(client, 'get_system_prompt')
        assert hasattr(client, 'get_init_prompt')
        print('  PASS: Client working')
    except Exception as e:
        print(f'  FAIL: {e}')
        assert False, str(e)


def _run_test(name, func):
    try:
        func()
        return name, True
    except Exception as exc:
        print(f'  FAIL [{name}]: {exc}')
        return name, False

def main():
    """Run all tests."""
    print('=' * 60)
    print('HLF MCP Complete Test Suite')
    print('=' * 60)
    print()
    
    results = [
        _run_test('Imports', test_imports),
        _run_test('Resources', test_resources),
        _run_test('Tools', test_tools),
        _run_test('Prompts', test_prompts),
        _run_test('Metrics', test_metrics),
        _run_test('Client', test_client),
    ]
    
    print()
    print('=' * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f'RESULTS: {passed}/{total} tests passed')
    
    if all(result for _, result in results):
        print('ALL TESTS PASSED!')
        return 0
    else:
        print('SOME TESTS FAILED!')
        return 1

if __name__ == '__main__':
    sys.exit(main())