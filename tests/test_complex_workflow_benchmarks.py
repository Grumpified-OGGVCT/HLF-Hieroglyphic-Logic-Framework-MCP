"""Tests for complex multi-step workflow benchmarks using PIPE, TEMPLATE, @validate.

Verifies that all 3 new HLF programs compile, PIPE chains expand to correct
stage counts, TEMPLATE refs expand inline, and @validate annotations emit
ENFORCE statements.
"""

import pytest

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf.benchmark import (
    _COMPLEX_WORKFLOW_NLP,
    _COMPLEX_WORKFLOW_HLF,
    _NEW_PIPE_TEMPLATE_SCENARIOS,
    get_pipe_template_hlf,
    get_pipe_template_nlp,
    run_complex_workflow_benchmarks,
)

COMPILER = HLFCompiler()

# ═══════════════════════════════════════════════════════════════════════════════
# Fixture helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _compile(scenario_id: str) -> dict:
    """Compile a scenario by ID, returning the compile result dict."""
    src = _COMPLEX_WORKFLOW_HLF[scenario_id]
    return COMPILER.compile(src)


def _glyph_stmts(result: dict) -> list[dict]:
    """Extract glyph_stmt nodes from compile result."""
    return [s for s in result["ast"]["statements"] if s.get("kind") == "glyph_stmt"]


# ═══════════════════════════════════════════════════════════════════════════════
# Compilation tests — all 3 new scenarios must compile
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("scenario_id", _NEW_PIPE_TEMPLATE_SCENARIOS)
def test_scenario_compiles(scenario_id: str) -> None:
    """Each new PIPE/TEMPLATE scenario compiles without errors."""
    src = _COMPLEX_WORKFLOW_HLF[scenario_id]
    result = COMPILER.compile(src)
    assert result["errors"] == []
    assert result["version"] == "3"
    assert result["node_count"] > 0


@pytest.mark.parametrize("scenario_id", _NEW_PIPE_TEMPLATE_SCENARIOS)
def test_scenario_has_glyphs(scenario_id: str) -> None:
    """Each scenario has glyph statements in its compiled AST."""
    result = _compile(scenario_id)
    glyphs = _glyph_stmts(result)
    assert len(glyphs) > 0, f"Expected glyph statements in {scenario_id}"


@pytest.mark.parametrize("scenario_id", _NEW_PIPE_TEMPLATE_SCENARIOS)
def test_scenario_has_omega(scenario_id: str) -> None:
    """Each scenario source ends with Omega terminator."""
    src = _COMPLEX_WORKFLOW_HLF[scenario_id]
    assert "Ω" in src, f"Missing Omega terminator in {scenario_id}"


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario A: Multi-Stage Deployment Pipeline
# ═══════════════════════════════════════════════════════════════════════════════


def test_deploy_pipe_has_template_definition() -> None:
    """Scenario A defines deploy_pattern TEMPLATE before PIPE chain."""
    src = get_pipe_template_hlf("multi_stage_deploy_pipe")
    assert "TEMPLATE deploy_pattern" in src


def test_deploy_pipe_uses_pipe_operator() -> None:
    """Scenario A uses PIPE operator for agent handoff chains."""
    src = get_pipe_template_hlf("multi_stage_deploy_pipe")
    assert "→" in src, "PIPE operator (U+2192) missing"


def test_deploy_pipe_expands_pipe_stages() -> None:
    """PIPE chain expands to sequential statements with _pipe_context."""
    result = _compile("multi_stage_deploy_pipe")
    glyphs = _glyph_stmts(result)
    pipe_stages = [s for s in glyphs if s.get("_pipe_context")]
    assert len(pipe_stages) == 4, (
        f"Expected 4 pipe stage glyphs, got {len(pipe_stages)}"
    )
    # Each PIPE-triggered stage should be a Δ ACTION
    for s in pipe_stages:
        assert s["glyph"] == "Δ"
        assert s["tag"] == "ACTION"


def test_deploy_pipe_expands_template_refs() -> None:
    """Template refs expand into ENFORCE check statements inline."""
    result = _compile("multi_stage_deploy_pipe")
    glyphs = _glyph_stmts(result)
    # deploy_pattern has 2 ENFORCE checks, referenced twice = 4
    # Plus 2 from @validate = 6 total ENFORCE-tagged Ж glyphs
    enforce_check = [
        s for s in glyphs
        if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"
    ]
    assert len(enforce_check) == 6, (
        f"Expected 6 ENFORCE from templates+@validate, got {len(enforce_check)}"
    )


def test_deploy_pipe_validates_emit_enforce() -> None:
    """@validate annotations produce ENFORCE Ж glyphs."""
    result = _compile("multi_stage_deploy_pipe")
    glyphs = _glyph_stmts(result)
    # Find the @validate-sourced ENFORCE for migration.json schema
    schema_enforce = [
        s for s in glyphs
        if s.get("glyph") == "Ж"
        and s.get("tag") == "ENFORCE"
        and any(
            a.get("name") == "check" and a.get("value", {}).get("value") == "schema"
            for a in s.get("arguments", [])
        )
    ]
    assert len(schema_enforce) >= 1, "@validate(schema=...) did not emit ENFORCE"

    # Find the @validate-sourced ENFORCE for prod_approval gate
    gate_enforce = [
        s for s in glyphs
        if s.get("glyph") == "Ж"
        and s.get("tag") == "ENFORCE"
        and any(
            a.get("name") == "check" and a.get("value", {}).get("value") == "gate"
            for a in s.get("arguments", [])
        )
    ]
    assert len(gate_enforce) >= 1, "@validate(gate=...) did not emit ENFORCE"


def test_deploy_pipe_has_assert() -> None:
    """Scenario A ends with a direct ASSERT Ж glyph."""
    result = _compile("multi_stage_deploy_pipe")
    glyphs = _glyph_stmts(result)
    assert_stmts = [
        s for s in glyphs
        if s.get("glyph") == "Ж" and s.get("tag") == "ASSERT"
    ]
    assert len(assert_stmts) == 1


def test_deploy_pipe_has_sigma_result() -> None:
    """Scenario A produces a Sigma summary result."""
    result = _compile("multi_stage_deploy_pipe")
    glyphs = _glyph_stmts(result)
    sigma = [s for s in glyphs if s.get("glyph") == "Σ"]
    assert len(sigma) == 1
    assert sigma[0]["tag"] == "RESULT"


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario B: Security Audit with Remediation
# ═══════════════════════════════════════════════════════════════════════════════


def test_security_audit_has_two_templates() -> None:
    """Scenario B defines audit_surface and remediation_checks templates."""
    src = get_pipe_template_hlf("security_audit_remediate")
    assert "TEMPLATE audit_surface" in src
    assert "TEMPLATE remediation_checks" in src


def test_security_audit_uses_validates() -> None:
    """Scenario B uses @validate for audit schema enforcement."""
    src = get_pipe_template_hlf("security_audit_remediate")
    assert "@validate(schema=\"audit.json\")" in src


def test_security_audit_pipe_stages() -> None:
    """Scenario B has 4 PIPE stages (audit, fix, reaudit, report)."""
    result = _compile("security_audit_remediate")
    glyphs = _glyph_stmts(result)
    pipe_stages = [s for s in glyphs if s.get("_pipe_context")]
    assert len(pipe_stages) == 4


def test_security_audit_template_expansion() -> None:
    """audit_surface (3 checks) * 2 refs + remediation_checks (2 checks) * 1 ref = 8
    Plus 2 @validate = 10 ENFORCE-tagged Ж glyphs total."""
    result = _compile("security_audit_remediate")
    glyphs = _glyph_stmts(result)
    enforce_check = [
        s for s in glyphs
        if s.get("glyph") == "Ж" and s.get("tag") == "ENFORCE"
    ]
    assert len(enforce_check) == 10, (
        f"Expected 10 ENFORCE from templates+@validate, got {len(enforce_check)}"
    )


def test_security_audit_has_log_findings() -> None:
    """Step 'log_findings' is a standalone Δ ACTION."""
    result = _compile("security_audit_remediate")
    glyphs = _glyph_stmts(result)
    log_action = [
        s for s in glyphs
        if s.get("glyph") == "Δ"
        and s.get("tag") == "ACTION"
        and any(
            a.get("name") == "exec"
            and a.get("value", {}).get("value") == "log_findings"
            for a in s.get("arguments", [])
        )
    ]
    assert len(log_action) == 1


def test_security_audit_ends_with_sigma() -> None:
    """Scenario B produces Sigma result and assert."""
    result = _compile("security_audit_remediate")
    glyphs = _glyph_stmts(result)
    sigma = [s for s in glyphs if s.get("glyph") == "Σ"]
    assert len(sigma) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Scenario C: Multi-Agent Research Synthesis
# ═══════════════════════════════════════════════════════════════════════════════


def test_research_synthesis_has_two_research_agents() -> None:
    """Scenario C routes to researcher_a and researcher_b via PIPE."""
    result = _compile("multi_agent_research_synthesis")
    glyphs = _glyph_stmts(result)
    route_stmts = [s for s in glyphs if s.get("glyph") == "⌘" and s.get("tag") == "ROUTE"]
    assert len(route_stmts) == 2
    agents = []
    for s in route_stmts:
        for a in s.get("arguments", []):
            if a.get("name") == "agent":
                agents.append(a.get("value", {}).get("value"))
    assert "researcher_a" in agents
    assert "researcher_b" in agents


def test_research_synthesis_uses_join_consensus() -> None:
    """Scenario C uses JOIN glyph for strict consensus."""
    result = _compile("multi_agent_research_synthesis")
    glyphs = _glyph_stmts(result)
    join_stmts = [s for s in glyphs if s.get("glyph") == "⨝"]
    assert len(join_stmts) == 1
    assert join_stmts[0]["tag"] == "JOIN"
    # consensus=strict
    args = join_stmts[0].get("arguments", [])
    consensus = next(
        (a for a in args if a.get("name") == "consensus"), None
    )
    assert consensus is not None
    assert consensus["value"]["value"] == "strict"


def test_research_synthesis_pipe_stages() -> None:
    """Scenario C has 2 PIPE stages (one per research delegation)."""
    result = _compile("multi_agent_research_synthesis")
    glyphs = _glyph_stmts(result)
    pipe_stages = [s for s in glyphs if s.get("_pipe_context")]
    assert len(pipe_stages) == 2


def test_research_synthesis_synthesize_action() -> None:
    """After JOIN, synthesize_findings and evaluate_tradeoffs execute."""
    result = _compile("multi_agent_research_synthesis")
    glyphs = _glyph_stmts(result)
    action_names = []
    for s in glyphs:
        if s.get("glyph") == "Δ" and s.get("tag") == "ACTION":
            for a in s.get("arguments", []):
                if a.get("name") == "exec":
                    action_names.append(a.get("value", {}).get("value"))
    assert "synthesize_findings" in action_names
    assert "evaluate_tradeoffs" in action_names


def test_research_synthesis_evidence_assert() -> None:
    """Recommendation is research-backed with evidence assert."""
    result = _compile("multi_agent_research_synthesis")
    glyphs = _glyph_stmts(result)
    evidence = [
        s for s in glyphs
        if s.get("glyph") == "Ж"
        and s.get("tag") == "ASSERT"
        and any(
            a.get("name") == "evidence"
            for a in s.get("arguments", [])
        )
    ]
    assert len(evidence) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Benchmark runner integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_benchmark_runner_returns_all_scenarios() -> None:
    """Runner returns results for all 8 scenarios."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    assert len(data["scenarios"]) == 8
    scenario_ids = [r["scenario_id"] for r in data["scenarios"]]
    for key in _NEW_PIPE_TEMPLATE_SCENARIOS:
        assert key in scenario_ids, f"Missing scenario {key}"


def test_benchmark_runner_all_compile() -> None:
    """All scenarios must compile successfully."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    for r in data["scenarios"]:
        assert r["compile_success"], (
            f"Scenario {r['scenario_id']} failed: {r.get('compile_error')}"
        )


def test_benchmark_runner_pipe_stages_detected() -> None:
    """Runner detects PIPE stages in the 3 new scenarios."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    pipe_scenarios = {
        r["scenario_id"]: r["pipe_stages"] for r in data["scenarios"]
    }
    assert pipe_scenarios["multi_stage_deploy_pipe"] == 4
    assert pipe_scenarios["security_audit_remediate"] == 4
    assert pipe_scenarios["multi_agent_research_synthesis"] == 2


def test_benchmark_runner_validate_enforce_detected() -> None:
    """Runner detects @validate/template-sourced ENFORCE statements."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    val_scenarios = {
        r["scenario_id"]: r["validate_enforce"] for r in data["scenarios"]
    }
    assert val_scenarios["multi_stage_deploy_pipe"] == 6
    assert val_scenarios["security_audit_remediate"] == 10


def test_benchmark_runner_pre_written_method() -> None:
    """New scenarios use pre_written method (keyword can't generate PIPE yet)."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    for r in data["scenarios"]:
        if r["scenario_id"] in _NEW_PIPE_TEMPLATE_SCENARIOS:
            assert r["translate_method"] == "pre_written", (
                f"{r['scenario_id']} should use pre_written, got {r['translate_method']}"
            )


def test_benchmark_runner_aggregates() -> None:
    """Aggregate metrics are computed correctly."""
    data = run_complex_workflow_benchmarks(use_llm=False)
    agg = data["aggregates"]
    assert agg["total_scenarios"] == 8
    assert agg["compile_success"] == 8
    assert agg["compile_rate_pct"] == 100.0
    assert agg["total_pipe_stages"] == 10  # 4+4+2
    assert agg["total_validate_enforce"] == 16  # 6+10+0


def test_benchmark_runner_deterministic() -> None:
    """Pre-written and keyword routes are deterministic (same input = same HLF)."""
    data1 = run_complex_workflow_benchmarks(use_llm=False)
    data2 = run_complex_workflow_benchmarks(use_llm=False)
    # Token counts should be identical
    for r1, r2 in zip(data1["scenarios"], data2["scenarios"]):
        assert r1["nlp_tokens"] == r2["nlp_tokens"]
        assert r1["hlf_tokens"] == r2["hlf_tokens"]
        assert r1["compile_success"] == r2["compile_success"]


# ═══════════════════════════════════════════════════════════════════════════════
# NLP ↔ HLF consistency
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("scenario_id", _NEW_PIPE_TEMPLATE_SCENARIOS)
def test_nlp_and_hlf_both_exist(scenario_id: str) -> None:
    """Each scenario has both NLP intent and HLF source defined."""
    nlp = get_pipe_template_nlp(scenario_id)
    hlf = get_pipe_template_hlf(scenario_id)
    assert len(nlp) > 20, f"NLP intent too short for {scenario_id}"
    assert "[HLF-v3]" in hlf, f"HLF missing version header for {scenario_id}"
    assert "Ω" in hlf, f"HLF missing Omega terminator for {scenario_id}"


def test_nlp_for_deploy_mentions_all_stages() -> None:
    """Deployment NLP mentions all 6 stages of the pipeline."""
    nlp = get_pipe_template_nlp("multi_stage_deploy_pipe")
    assert "migrate" in nlp.lower()
    assert "api gateway" in nlp.lower()
    assert "canary" in nlp.lower()
    assert "integration tests" in nlp.lower()
    assert "workers" in nlp.lower()
    assert "smoke tests" in nlp.lower()
    assert "switch" in nlp.lower() and "traffic" in nlp.lower()


def test_nlp_for_security_mentions_audit_remediate() -> None:
    """Security audit NLP mentions audit, fix, re-audit, compliance."""
    nlp = get_pipe_template_nlp("security_audit_remediate")
    assert "sql injection" in nlp.lower()
    assert "xss" in nlp.lower()
    assert "re-audit" in nlp.lower() or "reaudit" in nlp.lower()
    assert "SOC2" in nlp or "compliance" in nlp.lower()


def test_nlp_for_research_mentions_agents_and_synthesis() -> None:
    """Research NLP names two agents, consensus, and synthesis."""
    nlp = get_pipe_template_nlp("multi_agent_research_synthesis")
    assert "researcher_a" in nlp
    assert "researcher_b" in nlp
    assert "consensus" in nlp.lower()
    assert "synthesize" in nlp.lower() or "synthesis" in nlp.lower()
    assert "trade-off" in nlp.lower() or "tradeoff" in nlp.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


def test_get_pipe_template_hlf_raises_on_unknown() -> None:
    """Accessing unknown scenario raises KeyError."""
    with pytest.raises(KeyError):
        get_pipe_template_hlf("nonexistent_scenario")


def test_get_pipe_template_nlp_raises_on_unknown() -> None:
    """Accessing unknown scenario raises KeyError."""
    with pytest.raises(KeyError):
        get_pipe_template_nlp("nonexistent_scenario")


def test_compile_each_scenario_independently() -> None:
    """Compiling scenarios independently doesn't pollute template registry."""
    compiler = HLFCompiler()
    for sid in _NEW_PIPE_TEMPLATE_SCENARIOS:
        src = _COMPLEX_WORKFLOW_HLF[sid]
        result = compiler.compile(src)
        assert result["errors"] == []
        # Template registry should be empty after each compile (reset)
        assert len(compiler._template_registry) == 0
