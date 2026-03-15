"""Test MCP metrics functionality."""

def test_metrics():
    from hlf import mcp_resources, mcp_tools, mcp_prompts, mcp_metrics
    
    # Test metrics
    from hlf.mcp_metrics import (
        record_tool_call, 
        record_friction, 
        suggest_improvement, 
        record_test_result
    )
    
    print('Testing metrics module...')
    
    # Initialize
    metrics = mcp_metrics.get_metrics()
    print(f'1. get_metrics() = {type(metrics).__name__}')
    
    # Record a tool call
    record_tool_call('hlf_compile', success=True, duration_ms=50.5, gas_used=1000)
    print('2. record_tool_call() - OK')
    
    # Record a test
    record_test_result('test_compile', success=True, duration_ms=25.0)
    print('3. record_test_result() - OK')
    
    # Suggest improvement
    suggestion_id = suggest_improvement('Performance', 'Add bytecode caching', priority=2)
    print(f'4. suggest_improvement() = {suggestion_id}')
    
    # Get usage summary
    summary = metrics.get_usage_summary()
    print(f'5. get_usage_summary() = tool_calls={summary.get("total_calls", 0)}')
    
    # Get all suggestions
    suggestions = metrics.get_suggestions()
    print(f'6. get_suggestions() = {len(suggestions)} suggestions')
    
    print('')
    print('ALL METRICS TESTS PASSED')

if __name__ == '__main__':
    test_metrics()