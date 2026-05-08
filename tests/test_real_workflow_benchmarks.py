from __future__ import annotations

import json

from hlf_mcp import server
from hlf_mcp.hlf.benchmark import HLFBenchmark


def test_real_workflow_benchmark_uses_hlf_self_improvement_and_honest_modes() -> None:
    result = HLFBenchmark().real_workflow_self_improvement_benchmark()

    assert result["profile_name"] == "real_hlf_self_improvement_workflow_compare"
    assert result["mode"] == "patch-plan"
    assert result["summary"]["surface_coverage"] == 1.0
    assert result["summary"]["avg_validation_coverage_delta"] > 0
    assert result["summary"]["avg_proof_coverage_delta"] > 0
    assert result["governance_proof_verification"]["verified"] is True
    assert "no repository file modification" in result["measurement_policy"]["not_claimed"]

    workflow_ids = {row["workflow_id"] for row in result["rows"]}
    assert workflow_ids == {
        "authority-grammar-loop",
        "code-bearing-contract",
        "swarm-governance-report",
    }
    assert all(row["hlf_workflow"]["file_modification_claimed"] is False for row in result["rows"])
    assert all(row["non_hlf_baseline"]["estimated_by_text_rubric"] is True for row in result["rows"])

    code_row = next(row for row in result["rows"] if row["workflow_id"] == "code-bearing-contract")
    assert code_row["hlf_workflow"]["code_execution"]["status"] == "dry_run_ok"
    assert code_row["hlf_workflow"]["code_execution"]["executed"] is False

    swarm_row = next(row for row in result["rows"] if row["workflow_id"] == "swarm-governance-report")
    assert swarm_row["hlf_workflow"]["swarm"]["boundary"]["distributed_a2a"] is False
    assert swarm_row["hlf_workflow"]["tamper_detection"]["detected"] is True


def test_real_workflow_benchmark_tool_persists_report_resource() -> None:
    result = server.hlf_real_workflow_benchmark(
        workflow_ids=["code-bearing-contract"],
        persist=True,
    )

    assert result["artifact"]["profile_name"] == "real_hlf_self_improvement_workflow_compare"
    assert result["artifact"]["memory_ref"]["sha256"]
    assert "hlf://reports/real_workflow_benchmarks" in server.REGISTERED_RESOURCES

    status = json.loads(server.REGISTERED_RESOURCES["hlf://status/real_workflow_benchmarks"]())
    report = server.REGISTERED_RESOURCES["hlf://reports/real_workflow_benchmarks"]()

    assert status["status"] == "ok"
    assert status["summary"]["workflow_count"] == 1
    assert "Real HLF Self-Improvement Workflow Benchmarks" in report
    assert "code-bearing-contract" in report
