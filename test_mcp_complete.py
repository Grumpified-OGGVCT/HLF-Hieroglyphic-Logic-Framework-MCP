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
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

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
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

def test_tools():
    """Test 3: Tools work."""
    print('TEST 3: Tools...')
    try:
        from hlf.mcp_tools import HLFToolProvider
        tools = HLFToolProvider(repo_root=Path('.'))
        tool_list = tools.list_tools()
        names = [t.name for t in tool_list]
        
        assert 'hlf_compile' in names, f"hlf_compile not in {names}"
        assert 'hlf_execute' in names, f"hlf_execute not in {names}"
        assert 'hlf_friction_log' in names, f"hlf_friction_log not in {names}"
        print('  PASS: Tools working')
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

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
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

def test_metrics():
    """Test 5: Metrics work."""
    print('TEST 5: Metrics...')
    try:
        from hlf.mcp_metric import HLFTestMetrics
        metrics = HLFTestMetrics()
        results = metrics.run_all_tests()
        
        assert len(results) >= 5, f"Expected >= 5 results, got {len(results)}"
        print('  PASS: Metrics working')
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

def test_client():
    """Test 6: Client works."""
    print('TEST 6: Client...')
    try:
        from hlf.mcp_client import HLFMCPClient
        client = HLFMCPClient('http://localhost:8000')
        
        system_prompt = client._build_system_prompt(
            tier='forge',
            profile='P0',
            grammar='# Test grammar',
            dictionaries={'version': '0.5'},
            version_info={'version': '0.5.0', 'grammar_sha256': 'abc123'}
        )
        
        assert 'HLF SYSTEM PROMPT' in system_prompt, "HLF SYSTEM PROMPT not in system_prompt"
        print('  PASS: Client working')
        return True
    except Exception as e:
        print(f'  FAIL: {e}')
        return False

def main():
    """Run all tests."""
    print('=' * 60)
    print('HLF MCP Complete Test Suite')
    print('=' * 60)
    print()
    
    results = [
        test_imports(),
        test_resources(),
        test_tools(),
        test_prompts(),
        test_metrics(),
        test_client()
    ]
    
    print()
    print('=' * 60)
    passed = sum(results)
    total = len(results)
    print(f'RESULTS: {passed}/{total} tests passed')
    
    if all(results):
        print('ALL TESTS PASSED!')
        return 0
    else:
        print('SOME TESTS FAILED!')
        return 1

if __name__ == '__main__':
    sys.exit(main())