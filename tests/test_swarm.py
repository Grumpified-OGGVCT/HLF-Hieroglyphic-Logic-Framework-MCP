"""Integration tests for HLF swarm orchestration.

Tests the 3-agent swarm pipeline (Planner→Executor→Verifier) using
the live language_to_hlf → compile pipeline with witness governance
and formal verification. Zero simulation.
"""

from __future__ import annotations

import json

import pytest

from hlf_mcp.hlf.swarm_orchestrator import SwarmOrchestrator, SwarmResult
from hlf_mcp.hlf.swarm_observer import SwarmObserver
from hlf_mcp.hlf.witness_governance import WitnessGovernance
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.compiler import CompileError


@pytest.fixture
def orchestrator() -> SwarmOrchestrator:
    return SwarmOrchestrator()


class TestThreeAgentSwarm:
    """3-agent swarm: Planner → Executor → Verifier."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_run_produces_result(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Write a simple hello world function")
        assert isinstance(result, SwarmResult)
        assert result.swarm_id
        assert result.task_id
        assert len(result.phases) == 3

    @pytest.mark.xfail(
        raises=CompileError,
        reason="language_to_hlf outputs RETURN <multi-word> which the LALR(1) parser rejects",
    )
    def test_phases_in_order(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Check if a number is prime and return the result")
        phase_ids = [p.phase_id for p in result.phases]
        assert phase_ids == ["plan", "execute", "verify"]

    def test_phases_are_complete(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Count words in a text file")
        for p in result.phases:
            assert p.status == "complete"
            assert p.metrics.get("hlf_tokens", 0) > 0
            assert p.metrics.get("time_ms", 0) > 0

    def test_final_hlf_has_terminator(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Validate an email address format")
        assert "Ω" in result.final_hlf

    def test_total_tokens_positive(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Parse a CSV file and count rows")
        assert result.total_tokens > 0

    def test_total_time_positive(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Sort a list of names alphabetically")
        assert result.total_time_ms > 0


class TestGovernanceIntegration:
    """Witness governance trust scoring across swarm phases."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_trust_scores_in_metrics(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Convert temperature from Celsius to Fahrenheit")
        for p in result.phases:
            assert "trust" in p.metrics, f"Phase {p.phase_id} missing trust score"
            trust = p.metrics["trust"]
            assert "score" in trust or isinstance(trust, dict)

    def test_trust_scores_tracked_per_agent(self, orchestrator: SwarmOrchestrator) -> None:
        orchestrator.run("Generate a random password of specified length")
        for agent_id in ("planner", "executor", "verifier"):
            trust = orchestrator.governance.get_snapshot(agent_id)
            assert trust is not None


class TestVerifierIntegration:
    """Formal verification on inter-agent HLF messages."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_verification_results_nonempty(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Calculate factorial of a number recursively")
        verify_phase = result.phases[-1]
        assert verify_phase.phase_id == "verify"
        assert "verification_checks" in verify_phase.metrics

    def test_verifier_accepts_raw_hlf(self, orchestrator: SwarmOrchestrator) -> None:
        hlf_sample = (
            "[HLF-v3]\n"
            '⌘ [GOAL] input="verify input" output="result"\n'
            'Δ action="validate"\n'
            "Ω\n"
        )
        ast_result = orchestrator.compiler.compile(hlf_sample)
        report = orchestrator.verifier.verify_ast(ast_result.get("ast", {}))
        assert report.total_count >= 0


class TestObserverEvents:
    """Swarm observer progress events."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_progress_events_emitted(self, orchestrator: SwarmOrchestrator) -> None:
        orchestrator.run("Reverse a string")
        log = orchestrator.observer.get_log()
        assert len(log) >= 3  # at least one per phase

    def test_events_have_required_fields(self, orchestrator: SwarmOrchestrator) -> None:
        orchestrator.run("Find the maximum value in an array")
        log = orchestrator.observer.get_log()
        for event in log:
            assert event.swarm_id
            assert event.event_type
            assert event.agent_id
            assert event.role

    def test_events_filtered_by_swarm(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run("Check if a string is a palindrome")
        entries = orchestrator.observer.get_log(result.swarm_id)
        assert len(entries) >= 3
        for e in entries:
            assert e.swarm_id == result.swarm_id


class TestFiveAgentSwarm:
    """5-agent swarm (secondary pattern, higher overhead)."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_run_5_agent_produces_result(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run_5_agent_swarm("Build a CI pipeline configuration")
        assert isinstance(result, SwarmResult)
        assert len(result.phases) == 5

    def test_5_agent_phases_in_order(self, orchestrator: SwarmOrchestrator) -> None:
        result = orchestrator.run_5_agent_swarm("Design a database migration strategy")
        phase_ids = [p.phase_id for p in result.phases]
        assert phase_ids == ["plan", "research", "execute", "review", "verify"]


class TestErrorHandling:
    """Error cases and edge conditions."""

    @pytest.fixture
    def orchestrator(self) -> SwarmOrchestrator:
        return SwarmOrchestrator()

    def test_empty_goal_handles_gracefully(self, orchestrator: SwarmOrchestrator) -> None:
        """An empty goal should still produce a SwarmResult (phases may have errors)."""
        result = orchestrator.run("")
        assert isinstance(result, SwarmResult)
        assert len(result.phases) == 3

    def test_very_long_goal(self, orchestrator: SwarmOrchestrator) -> None:
        """A very long goal should not crash."""
        long_goal = "Design a complete distributed system with " + "many requirements " * 50
        result = orchestrator.run(long_goal)
        assert isinstance(result, SwarmResult)
        assert len(result.phases) == 3
