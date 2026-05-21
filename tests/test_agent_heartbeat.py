"""Tests for Multi-Agent Heartbeat Monitor — confidence-based routing and health tracking."""

from __future__ import annotations

import time

from hlf_mcp.hlf.agent_heartbeat import HeartbeatMonitor, HeartbeatRecord


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _alive_record(agent_id: str, agent_type: str = "doer", confidence: float = 0.9,
                  error_count: int = 0) -> HeartbeatRecord:
    return HeartbeatRecord(
        agent_id=agent_id,
        agent_type=agent_type,
        timestamp=_now_iso(),
        status="alive",
        last_action="completed task",
        memory_usage_mb=128.0,
        cpu_percent=15.0,
        uptime_sec=3600.0,
        confidence_score=confidence,
        error_count=error_count,
    )


def _dead_record(agent_id: str, agent_type: str = "doer") -> HeartbeatRecord:
    return HeartbeatRecord(
        agent_id=agent_id,
        agent_type=agent_type,
        timestamp=_now_iso(),
        status="dead",
        last_action="none",
        memory_usage_mb=0.0,
        cpu_percent=0.0,
        uptime_sec=0.0,
        confidence_score=0.0,
        error_count=10,
    )


def _ancient_record(agent_id: str, agent_type: str = "doer") -> HeartbeatRecord:
    """Record with a timestamp far in the past — guaranteed 'dead' by threshold."""
    return HeartbeatRecord(
        agent_id=agent_id,
        agent_type=agent_type,
        timestamp="2020-01-01T00:00:00Z",
        status="alive",
        last_action="ancient task",
        memory_usage_mb=64.0,
        cpu_percent=5.0,
        uptime_sec=100.0,
        confidence_score=0.5,
        error_count=0,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestRecordHeartbeat:
    def test_record_heartbeat_stores_record(self) -> None:
        monitor = HeartbeatMonitor()
        rec = _alive_record("agent-1")
        monitor.record_heartbeat(rec)
        assert "agent-1" in monitor.records
        assert len(monitor.records["agent-1"]) == 1
        assert monitor.records["agent-1"][0] is rec

    def test_record_multiple_heartbeats(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a"))
        monitor.record_heartbeat(_alive_record("a"))
        monitor.record_heartbeat(_alive_record("a"))
        assert len(monitor.records["a"]) == 3

    def test_history_capped_at_max_history(self) -> None:
        monitor = HeartbeatMonitor(max_history=5)
        for i in range(10):
            monitor.record_heartbeat(_alive_record("a"))
        assert len(monitor.records["a"]) == 5


class TestCheckStatus:
    def test_check_status_returns_alive_for_recent_heartbeat(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a"))
        assert monitor.check_status("a") == "alive"

    def test_check_status_returns_dead_after_threshold(self) -> None:
        monitor = HeartbeatMonitor(dead_threshold_sec=1.0)
        monitor.record_heartbeat(_ancient_record("a"))
        assert monitor.check_status("a") == "dead"

    def test_check_status_returns_dead_for_explicitly_dead(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_dead_record("a"))
        assert monitor.check_status("a") == "dead"

    def test_check_status_returns_degraded(self) -> None:
        monitor = HeartbeatMonitor()
        rec = HeartbeatRecord(
            agent_id="degraded-1",
            agent_type="doer",
            timestamp=_now_iso(),
            status="degraded",
            last_action="slow response",
            memory_usage_mb=450.0,
            cpu_percent=85.0,
            uptime_sec=1000.0,
            confidence_score=0.4,
            error_count=5,
        )
        monitor.record_heartbeat(rec)
        assert monitor.check_status("degraded-1") == "degraded"

    def test_check_status_unknown_agent_returns_dead(self) -> None:
        monitor = HeartbeatMonitor()
        assert monitor.check_status("nonexistent") == "dead"


class TestGetConfidence:
    def test_get_confidence_with_recent_clean_agent(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a", error_count=0))
        conf = monitor.get_confidence("a")
        assert conf > 0.8, f"Expected high confidence, got {conf}"

    def test_get_confidence_penalizes_errors(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a", error_count=50))
        conf_error = monitor.get_confidence("a")

        monitor2 = HeartbeatMonitor()
        monitor2.record_heartbeat(_alive_record("b", error_count=0))
        conf_clean = monitor2.get_confidence("b")

        assert conf_error < conf_clean, f"error={conf_error}, clean={conf_clean}"

    def test_get_confidence_unknown_agent_returns_zero(self) -> None:
        monitor = HeartbeatMonitor()
        assert monitor.get_confidence("ghost") == 0.0

    def test_get_confidence_bounded_0_to_1(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a"))
        conf = monitor.get_confidence("a")
        assert 0.0 <= conf <= 1.0


class TestRouteByConfidence:
    def test_route_by_confidence_picks_highest(self) -> None:
        monitor = HeartbeatMonitor()
        # Agent A: high confidence
        monitor.record_heartbeat(_alive_record("a", "doer", confidence=0.95, error_count=0))
        # Agent B: lower confidence (more errors)
        monitor.record_heartbeat(_alive_record("b", "doer", confidence=0.6, error_count=20))
        winner = monitor.route_by_confidence("doer")
        assert winner == "a"

    def test_route_by_confidence_excludes_dead(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_dead_record("a", "doer"))
        monitor.record_heartbeat(_alive_record("b", "doer"))
        winner = monitor.route_by_confidence("doer")
        assert winner == "b"

    def test_route_by_confidence_no_match_returns_none(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a", "doer"))
        assert monitor.route_by_confidence("planner") is None


class TestDeadAgents:
    def test_dead_agents_returns_only_dead(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("alive-1"))
        monitor.record_heartbeat(_dead_record("dead-1"))
        monitor.record_heartbeat(_alive_record("alive-2"))
        dead = monitor.dead_agents()
        assert "dead-1" in dead
        assert "alive-1" not in dead
        assert "alive-2" not in dead

    def test_dead_agents_empty_when_all_alive(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a"))
        monitor.record_heartbeat(_alive_record("b"))
        assert monitor.dead_agents() == []


class TestAggregateReport:
    def test_aggregate_report_has_correct_structure(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a", "doer"))
        monitor.record_heartbeat(_dead_record("b", "planner"))
        report = monitor.aggregate_report()
        assert report["total_agents"] == 2
        assert report["healthy_agents"] >= 0
        assert report["dead_agents"] >= 0
        assert "agents" in report
        assert "a" in report["agents"]
        assert "b" in report["agents"]
        assert report["agents"]["a"]["agent_type"] == "doer"
        assert report["agents"]["b"]["agent_type"] == "planner"
        assert "confidence" in report["agents"]["a"]

    def test_aggregate_report_counts_correctly(self) -> None:
        monitor = HeartbeatMonitor()
        monitor.record_heartbeat(_alive_record("a"))
        monitor.record_heartbeat(_dead_record("b"))
        report = monitor.aggregate_report()
        assert report["healthy_agents"] >= 1
        assert report["dead_agents"] >= 1
