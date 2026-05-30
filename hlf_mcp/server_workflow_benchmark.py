"""Workflow benchmark tool registration for the MCP server surface."""

from __future__ import annotations

from typing import Any



def register_workflow_benchmark_tools(mcp) -> dict[str, Any]:
    # Lazy DSL import — only loaded when workflow benchmark is invoked
    from hlf_mcp.hlf.workflow_benchmark import run_workflow_benchmark
    """Register hlf_workflow_benchmark and hlf_workflow_benchmark_custom_task."""
    tools: dict[str, Any] = {}

    @mcp.tool()
    def hlf_workflow_benchmark(
        delivery_mode: str = "auto",
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        return run_workflow_benchmark(delivery_mode=delivery_mode, auto_repair=auto_repair)

    @mcp.tool()
    def hlf_workflow_benchmark_custom_task(
        task_id: str,
        description: str,
        domain: str = "general",
        expected_tags: list[str] | None = None,
        expected_concepts: list[str] | None = None,
        min_statements: int = 2,
        max_gas: int = 500,
        delivery_mode: str = "auto",
        auto_repair: bool = True,
    ) -> dict[str, Any]:
        from hlf_mcp.hlf.workflow_benchmark import BenchmarkTask, WorkflowBenchmark

        task = BenchmarkTask(
            task_id=task_id,
            description=description,
            domain=domain,
            expected_tags=expected_tags or ["INTENT"],
            expected_concepts=expected_concepts or [],
            min_statements=min_statements,
            max_gas=max_gas,
        )
        bench = WorkflowBenchmark()
        return bench.run_task(task, lambda text: {"source": text})

    tools["hlf_workflow_benchmark"] = hlf_workflow_benchmark
    tools["hlf_workflow_benchmark_custom_task"] = hlf_workflow_benchmark_custom_task

    def _register_sg_aliases(mcp, aliases: dict):
        import functools
        for sg_name, hlf_func in aliases.items():
            def _make_wrapper(_name, _func):
                @functools.wraps(_func)
                def _wrapper(*args, **kwargs):
                    return _func(*args, **kwargs)
                _wrapper.__name__ = _name
                return _wrapper
            wrapper = _make_wrapper(sg_name, hlf_func)
            mcp.tool(name=sg_name)(wrapper)

    _register_sg_aliases(mcp, {
        "sg_bench_workflow": hlf_workflow_benchmark,
        "sg_bench_workflow_custom": hlf_workflow_benchmark_custom_task,
    })

    tools["sg_bench_workflow"] = hlf_workflow_benchmark
    tools["sg_bench_workflow_custom"] = hlf_workflow_benchmark_custom_task
    return tools
