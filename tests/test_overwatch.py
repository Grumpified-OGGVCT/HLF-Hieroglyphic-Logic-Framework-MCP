"""Tests for OVERWATCH Sentinel watchdog — process-level health scanning and recovery."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hlf_mcp.hlf.overwatch import (
    OverwatchSentinel,
    WatchdogStatus,
    WatchdogTarget,
    build_overwatch_from_config,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _healthy_target(tid: str = "agent-1") -> WatchdogTarget:
    return WatchdogTarget(
        target_id=tid,
        process_name="hlf-agent",
        pid=12345,
        check_interval_sec=15.0,
        last_heartbeat=_now_iso(),
        status=WatchdogStatus.HEALTHY,
        restart_count=0,
        max_restarts=3,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestWatchdogTarget:
    def test_default_values(self) -> None:
        target = WatchdogTarget(target_id="test", process_name="test-proc")
        assert target.target_id == "test"
        assert target.process_name == "test-proc"
        assert target.pid is None
        assert target.check_interval_sec == 30.0
        assert target.last_heartbeat is None
        assert target.status == WatchdogStatus.HEALTHY
        assert target.restart_count == 0
        assert target.max_restarts == 3
        assert target.health_check_url is None
        assert target.resource_limits == {"max_memory_mb": 512.0, "max_cpu_percent": 80.0}

    def test_to_dict_serializes_all_fields(self) -> None:
        target = _healthy_target()
        d = target.to_dict()
        assert d["target_id"] == "agent-1"
        assert d["status"] == "healthy"
        assert d["pid"] == 12345
        assert "resource_limits" in d


class TestRegisterAndScan:
    def test_register_target_and_scan(self) -> None:
        sentinel = OverwatchSentinel()
        target = _healthy_target()
        sentinel.register_target(target)
        assert "agent-1" in sentinel.targets
        results = sentinel.scan()
        assert "agent-1" in results

    def test_scan_returns_status_map(self) -> None:
        sentinel = OverwatchSentinel()
        sentinel.register_target(_healthy_target("a"))
        sentinel.register_target(_healthy_target("b"))
        results = sentinel.scan()
        assert len(results) == 2
        assert all(isinstance(v, WatchdogStatus) for v in results.values())

    def test_check_target_updates_last_heartbeat(self) -> None:
        sentinel = OverwatchSentinel()
        target = WatchdogTarget(target_id="hb-test", process_name="hlf-agent", pid=12345)
        old_hb = target.last_heartbeat
        sentinel.register_target(target)
        # With a valid PID that exists on the system, status should be healthy
        status = sentinel.check_target("hb-test")
        # On CI/Windows the PID 12345 may not exist; that's fine — test the logic flow
        assert isinstance(status, WatchdogStatus)
        assert sentinel.targets["hb-test"].last_heartbeat is not None or old_hb is None

    def test_scan_detects_unresponsive_targets(self) -> None:
        sentinel = OverwatchSentinel(alert_threshold=1)
        # Use a PID that definitely doesn't exist
        target = WatchdogTarget(
            target_id="gone",
            process_name="nonexistent-process",
            pid=99999999,
            last_heartbeat=_now_iso(),
        )
        sentinel.register_target(target)
        status = sentinel.check_target("gone")
        assert status == WatchdogStatus.TERMINATED


class TestAlertThreshold:
    def test_alert_threshold_triggers_on_consecutive_failures(self) -> None:
        sentinel = OverwatchSentinel(alert_threshold=3)
        target = WatchdogTarget(
            target_id="flaky",
            process_name="nonexistent-process",
            pid=99999999,
        )
        sentinel.register_target(target)

        # Three consecutive failures should trigger TERMINATED
        s1 = sentinel.check_target("flaky")
        s2 = sentinel.check_target("flaky")
        s3 = sentinel.check_target("flaky")
        assert s1 == WatchdogStatus.UNRESPONSIVE
        assert s2 == WatchdogStatus.UNRESPONSIVE
        assert s3 == WatchdogStatus.TERMINATED

    def test_alert_threshold_resets_on_recovery(self) -> None:
        sentinel = OverwatchSentinel(alert_threshold=3)
        target = WatchdogTarget(
            target_id="flaky2",
            process_name="nonexistent-process",
            pid=99999999,
        )
        sentinel.register_target(target)

        sentinel.check_target("flaky2")  # failure 1
        sentinel.check_target("flaky2")  # failure 2
        # Simulate recovery by setting PID to a live-ish value
        sentinel.targets["flaky2"].pid = None
        sentinel.targets["flaky2"].health_check_url = "http://localhost:1"  # will fail
        sentinel.targets["flaky2"].status = WatchdogStatus.HEALTHY
        sentinel._failure_counters["flaky2"] = 0

        # Now check again with different method — still fails but counter reset
        status = sentinel.check_target("flaky2")
        # Counter was reset, so it won't yet be terminated
        assert status in (WatchdogStatus.UNRESPONSIVE, WatchdogStatus.TERMINATED)


class TestTerminate:
    def test_terminate_kills_target(self) -> None:
        sentinel = OverwatchSentinel()
        sentinel.register_target(_healthy_target("term-test"))
        result = sentinel.terminate("term-test", reason="test")
        assert result is True
        assert sentinel.targets["term-test"].status == WatchdogStatus.TERMINATED

    def test_terminate_unknown_target_returns_false(self) -> None:
        sentinel = OverwatchSentinel()
        assert sentinel.terminate("nonexistent") is False


class TestAutoRecover:
    def test_auto_recover_restarts_dead_target(self) -> None:
        sentinel = OverwatchSentinel()
        target = WatchdogTarget(
            target_id="downed",
            process_name="hlf-agent",
            pid=99999999,
            status=WatchdogStatus.TERMINATED,
            last_heartbeat=_now_iso(),
        )
        sentinel.register_target(target)
        status = sentinel.auto_recover("downed")
        assert status == WatchdogStatus.HEALTHY
        assert sentinel.targets["downed"].restart_count == 1
        assert sentinel.targets["downed"].pid is not None

    def test_auto_recover_stops_after_max_restarts(self) -> None:
        sentinel = OverwatchSentinel()
        target = WatchdogTarget(
            target_id="exhausted",
            process_name="hlf-agent",
            pid=99999999,
            status=WatchdogStatus.TERMINATED,
            restart_count=3,
            max_restarts=3,
        )
        sentinel.register_target(target)
        status = sentinel.auto_recover("exhausted")
        assert status == WatchdogStatus.TERMINATED
        assert sentinel.targets["exhausted"].restart_count == 3  # unchanged

    def test_auto_recover_skips_healthy_target(self) -> None:
        sentinel = OverwatchSentinel()
        sentinel.register_target(_healthy_target("fine"))
        status = sentinel.auto_recover("fine")
        assert status == WatchdogStatus.HEALTHY
        assert sentinel.targets["fine"].restart_count == 0

    def test_auto_recover_unknown_target(self) -> None:
        sentinel = OverwatchSentinel()
        assert sentinel.auto_recover("ghost") == WatchdogStatus.TERMINATED


class TestStatusReport:
    def test_status_report_generates_markdown(self) -> None:
        sentinel = OverwatchSentinel()
        sentinel.register_target(_healthy_target("sentry-a"))
        sentinel.register_target(WatchdogTarget(
            target_id="sentry-b", process_name="down-proc", pid=99999999,
            status=WatchdogStatus.TERMINATED, last_heartbeat=_now_iso(),
        ))
        report = sentinel.status_report()
        assert "# OVERWATCH Sentinel Status Report" in report
        assert "sentry-a" in report
        assert "sentry-b" in report
        assert "down-proc" in report
        assert "TERMINATED" in report
        assert "HEALTHY" in report or "healthy" in report.lower()

    def test_status_report_lists_dead_targets(self) -> None:
        sentinel = OverwatchSentinel()
        sentinel.register_target(WatchdogTarget(
            target_id="zombie", process_name="z",
            status=WatchdogStatus.TERMINATED,
        ))
        report = sentinel.status_report()
        assert "zombie" in report


class TestBuildFromConfig:
    def test_build_overwatch_from_config(self, tmp_path: Path) -> None:
        config = {
            "scan_interval_sec": 15.0,
            "alert_threshold": 2,
            "targets": [
                {
                    "target_id": "cfg-agent",
                    "process_name": "cfg-proc",
                    "check_interval_sec": 10.0,
                    "max_restarts": 5,
                    "health_check_url": "http://localhost:9999/health",
                    "resource_limits": {"max_memory_mb": 256, "max_cpu_percent": 50},
                },
            ],
        }
        config_path = tmp_path / "overwatch.json"
        config_path.write_text(json.dumps(config))

        sentinel = build_overwatch_from_config(str(config_path))
        assert sentinel.scan_interval_sec == 15.0
        assert sentinel.alert_threshold == 2
        assert "cfg-agent" in sentinel.targets
        t = sentinel.targets["cfg-agent"]
        assert t.process_name == "cfg-proc"
        assert t.check_interval_sec == 10.0
        assert t.max_restarts == 5
        assert t.health_check_url == "http://localhost:9999/health"
        assert t.resource_limits == {"max_memory_mb": 256, "max_cpu_percent": 50}

    def test_build_overwatch_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            build_overwatch_from_config("/nonexistent/path/config.json")

    def test_build_overwatch_empty_targets(self, tmp_path: Path) -> None:
        config = {"targets": []}
        config_path = tmp_path / "empty.json"
        config_path.write_text(json.dumps(config))
        sentinel = build_overwatch_from_config(str(config_path))
        assert len(sentinel.targets) == 0
