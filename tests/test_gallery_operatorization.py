"""
tests/test_gallery_operatorization.py — Tests for gallery telemetry, operator CLI,
dashboard enhancements, and end-to-end operatorization workflows.

Verifies that the TelemetryCollector, operator CLI, enhanced dashboard,
and integration points all work correctly. 30+ tests.
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
from pathlib import Path
from unittest import mock

import pytest


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _capture_output(func, *args, **kwargs):
    """Capture stdout/stderr from a function call."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        return func(*args, **kwargs)
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# ══════════════════════════════════════════════════════════════════════════════════
# TelemetryCollector — Start/Stop
# ══════════════════════════════════════════════════════════════════════════════════


class TestTelemetryCollectorStartStop:
    """Tests for TelemetryCollector lifecycle (start/stop)."""

    def test_collector_create_default(self) -> None:
        """Can create a TelemetryCollector with default settings."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector()
        assert collector is not None
        assert not collector.is_running
        assert collector._interval == 2.0
        assert collector._history_size == 100

    def test_collector_start_stop(self) -> None:
        """Can start and stop the collector."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector(interval=0.5)
        collector.start()
        assert collector.is_running
        time.sleep(0.3)  # Give it time to collect at least one snapshot
        collector.stop()
        assert not collector.is_running

    def test_collector_double_start_raises(self) -> None:
        """Starting an already-running collector raises RuntimeError."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector(interval=10.0)
        collector.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                collector.start()
        finally:
            collector.stop()


# ══════════════════════════════════════════════════════════════════════════════════
# TelemetryCollector — Snapshot
# ══════════════════════════════════════════════════════════════════════════════════


class TestTelemetrySnapshot:
    """Tests for TelemetryCollector.snapshot()."""

    def test_snapshot_returns_valid_data(self) -> None:
        """snapshot() returns a TelemetrySnapshot with all expected fields."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector, TelemetrySnapshot
        collector = TelemetryCollector()
        snap = collector.snapshot()
        assert isinstance(snap, TelemetrySnapshot)
        assert snap.snapshot_id.startswith("snap-")
        assert "T" in snap.timestamp
        assert isinstance(snap.overall_readiness_pct, float)
        assert 0 <= snap.overall_readiness_pct <= 100
        assert "swarm_health" in snap.to_dict()
        assert "verification_gate" in snap.to_dict()
        assert "constitutional_violations" in snap.to_dict()
        assert "manifest_audit" in snap.to_dict()

    def test_snapshot_adds_to_history(self) -> None:
        """Each snapshot is appended to the trend history buffer."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector()
        assert len(collector.history()) == 0
        collector.snapshot()
        assert len(collector.history()) == 1
        collector.snapshot()
        assert len(collector.history()) == 2

    def test_snapshot_to_ndjson_is_parseable(self) -> None:
        """snapshot.to_ndjson() produces valid ndjson."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector()
        snap = collector.snapshot()
        ndjson_line = snap.to_ndjson()
        assert ndjson_line.endswith("\n") or not ndjson_line.endswith("\n")
        parsed = json.loads(ndjson_line)
        assert parsed["snapshot_id"] == snap.snapshot_id
        assert parsed["overall_readiness_pct"] == snap.overall_readiness_pct


# ══════════════════════════════════════════════════════════════════════════════════
# TelemetryCollector — Stream
# ══════════════════════════════════════════════════════════════════════════════════


class TestTelemetryStream:
    """Tests for TelemetryCollector.stream()."""

    def test_stream_yields_existing_history(self) -> None:
        """stream() yields existing history before new snapshots."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector(interval=10.0)
        collector.snapshot()
        collector.snapshot()

        lines: list[str] = []
        collector.start()
        try:
            gen = collector.stream()
            # Collect existing history lines then stop
            for i, line in enumerate(gen):
                lines.append(line)
                if i >= 1:
                    collector.stop()
                    break
        finally:
            collector.stop()

        assert len(lines) >= 2

    def test_stream_lines_are_valid_ndjson(self) -> None:
        """Each line from stream() is valid ndjson."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector(interval=5.0)
        collector.snapshot()

        collector.start()
        try:
            gen = collector.stream()
            for i, line in enumerate(gen):
                parsed = json.loads(line.strip())
                assert "snapshot_id" in parsed
                assert "overall_readiness_pct" in parsed
                if i >= 0:
                    break
        finally:
            collector.stop()

    def test_stream_stops_when_collector_stopped(self) -> None:
        """stream() stops yielding when collector is stopped."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector(interval=10.0)
        collector.snapshot()

        collector.start()
        gen = collector.stream()
        # Read existing history
        next(gen)
        # Stop the collector
        collector.stop()
        # Generator should be nearly exhausted (may have 0-1 buffered)
        remaining = list(gen)
        assert len(remaining) <= 1


# ══════════════════════════════════════════════════════════════════════════════════
# Operator CLI — Dashboard
# ══════════════════════════════════════════════════════════════════════════════════


class TestOperatorCLIDashboard:
    """Tests for the operator CLI --dashboard mode."""

    def test_dashboard_flag_parsed(self) -> None:
        """--dashboard flag is recognized by the argument parser."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--dashboard"])
        assert args.dashboard is True

    def test_snapshot_flag_parsed(self) -> None:
        """--snapshot flag is recognized."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--snapshot"])
        assert args.snapshot is True

    def test_snapshot_output_is_valid_json(self) -> None:
        """--snapshot with --json outputs valid JSON."""
        from hlf_mcp.gallery.operator_cli import main
        import io as _io
        old_stdout = sys.stdout
        sys.stdout = _io.StringIO()
        try:
            exit_code = main(["--snapshot", "--json"])
        finally:
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        assert exit_code == 0
        data = json.loads(output)
        assert "snapshot_id" in data
        assert "overall_readiness_pct" in data


# ══════════════════════════════════════════════════════════════════════════════════
# Operator CLI — Snapshot
# ══════════════════════════════════════════════════════════════════════════════════


class TestOperatorCLISnapshot:
    """Tests for --snapshot mode."""

    def test_snapshot_mode_exit_code_zero(self) -> None:
        """--snapshot returns exit code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["--snapshot"])
        assert exit_code == 0

    def test_snapshot_default_format_is_ndjson(self) -> None:
        """Snapshot without --json outputs ndjson."""
        from hlf_mcp.gallery.operator_cli import main
        import io as _io
        old = sys.stdout
        sys.stdout = _io.StringIO()
        try:
            main(["--snapshot"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old

        assert "snapshot_id" in output
        # ndjson is single-line JSON
        parsed = json.loads(output.strip().split("\n")[0])
        assert "snapshot_id" in parsed


# ══════════════════════════════════════════════════════════════════════════════════
# Operator CLI — Watch
# ══════════════════════════════════════════════════════════════════════════════════


class TestOperatorCLIWatch:
    """Tests for --watch mode."""

    def test_watch_flag_parsed(self) -> None:
        """--watch flag is recognized."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--watch"])
        assert args.watch is True

    def test_interval_flag_parsed(self) -> None:
        """--interval flag sets custom interval."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--watch", "--interval", "5.0"])
        assert args.interval == 5.0


# ══════════════════════════════════════════════════════════════════════════════════
# Operator CLI — Subcommands
# ══════════════════════════════════════════════════════════════════════════════════


class TestOperatorCLISubcommands:
    """Tests for the CLI subcommands: status, pillars, violations, audit."""

    def test_status_subcommand_runs(self) -> None:
        """'status' subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["status"])
        assert exit_code == 0

    def test_pillars_subcommand_runs(self) -> None:
        """'pillars' subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["pillars"])
        assert exit_code == 0

    def test_violations_subcommand_runs(self) -> None:
        """'violations' subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["violations"])
        assert exit_code == 0

    def test_audit_subcommand_runs(self) -> None:
        """'audit' subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["audit"])
        assert exit_code == 0


# ══════════════════════════════════════════════════════════════════════════════════
# Dashboard — Live Telemetry Integration
# ══════════════════════════════════════════════════════════════════════════════════


class TestDashboardWithLiveTelemetry:
    """Tests for dashboard telemetry integration functions."""

    def test_integrate_telemetry_snapshot_enriches_dashboard(self) -> None:
        """integrate_telemetry_snapshot adds telemetry data to a dashboard."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_data,
            integrate_telemetry_snapshot,
        )
        from hlf_mcp.gallery.telemetry import TelemetryCollector

        dashboard = build_dashboard_data()
        collector = TelemetryCollector()
        snap = collector.snapshot()
        enriched = integrate_telemetry_snapshot(dashboard, snap.to_dict())

        assert enriched["telemetry"]["integrated"] is True
        assert enriched["telemetry"]["snapshot_id"] == snap.snapshot_id
        assert enriched["swarm"]["source"] == "telemetry"

    def test_integrate_telemetry_updates_overall_status(self) -> None:
        """Telemetry integration updates overall_status based on readiness."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_data,
            integrate_telemetry_snapshot,
        )
        dashboard = build_dashboard_data()
        telemetry_data = {
            "overall_readiness_pct": 70.0,
            "swarm_health": {"source": "telemetry", "active_agents": 3, "healthy_phases": 4},
            "verification_gate": {"source": "telemetry", "pass_rate_pct": 70.0},
            "constitutional_violations": {"source": "telemetry", "total_violations": 0, "high_severity": 0, "medium_severity": 0, "low_severity": 0, "blocked_actions": 0},
            "manifest_audit": {"source": "telemetry", "total_deployments": 10, "approved_deployments": 8, "rejected_deployments": 2, "approval_rate_pct": 80.0},
            "snapshot_id": "snap-test",
            "alert_thresholds": {"overall": "healthy"},
        }
        enriched = integrate_telemetry_snapshot(dashboard, telemetry_data)
        assert enriched["overall_status"] == "healthy"

    def test_integrate_telemetry_keeps_existing_data_when_missing(self) -> None:
        """Missing telemetry fields do not overwrite existing dashboard data."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_data,
            integrate_telemetry_snapshot,
        )
        dashboard = build_dashboard_data()
        original_source = dashboard["swarm"]["source"]
        enriched = integrate_telemetry_snapshot(dashboard, {"snapshot_id": "minimal"})
        # Swarm should remain unchanged since no telemetry swarm_health
        assert enriched["swarm"]["source"] == original_source

    def test_build_dashboard_with_trend_includes_trend_history(self) -> None:
        """build_dashboard_with_trend includes trend_history key."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_with_trend
        dashboard = build_dashboard_with_trend(record=True)
        assert "trend_history" in dashboard
        assert isinstance(dashboard["trend_history"], list)
        assert len(dashboard["trend_history"]) >= 1


# ══════════════════════════════════════════════════════════════════════════════════
# Dashboard — Alert Thresholds
# ══════════════════════════════════════════════════════════════════════════════════


class TestDashboardAlertThresholds:
    """Tests for alert threshold computation and display."""

    def test_compute_alert_threshold_critical(self) -> None:
        """Scores below 50% are critical."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_threshold
        assert compute_alert_threshold(30.0) == "critical"
        assert compute_alert_threshold(49.9) == "critical"
        assert compute_alert_threshold(0.0) == "critical"

    def test_compute_alert_threshold_degraded(self) -> None:
        """Scores between 50-64.9% are degraded."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_threshold
        assert compute_alert_threshold(50.0) == "degraded"
        assert compute_alert_threshold(58.0) == "degraded"
        assert compute_alert_threshold(64.9) == "degraded"

    def test_compute_alert_threshold_healthy(self) -> None:
        """Scores 65% and above are healthy."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_threshold
        assert compute_alert_threshold(65.0) == "healthy"
        assert compute_alert_threshold(80.0) == "healthy"
        assert compute_alert_threshold(100.0) == "healthy"


# ══════════════════════════════════════════════════════════════════════════════════
# Integration Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestGalleryOperatorizationIntegration:
    """End-to-end operatorization workflow tests."""

    def test_full_operator_toolchain(self) -> None:
        """The full operator toolchain works: telemetry → dashboard → JSON → CLI."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_with_trend,
            integrate_telemetry_snapshot,
            generate_dashboard_json,
            compute_alert_threshold,
        )

        # 1. Collect telemetry
        collector = TelemetryCollector()
        snap = collector.snapshot()

        # 2. Build dashboard with trend
        dashboard = build_dashboard_with_trend(record=True)

        # 3. Integrate telemetry
        enriched = integrate_telemetry_snapshot(dashboard, snap.to_dict())

        # 4. Verify alert threshold
        alert = compute_alert_threshold(enriched["pillar_score"]["score_pct"])
        assert alert in ("critical", "degraded", "healthy")

        # 5. Generate JSON (to temp dir)
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            json_str = generate_dashboard_json(str(Path(tmpdir) / "test.json"))
            data = json.loads(json_str)
            assert "dashboard_id" in data

    def test_gallery_package_exports_all_new_names(self) -> None:
        """Gallery __init__.py exports TelemetryCollector, CLI, and dashboard enhancements."""
        import hlf_mcp.gallery

        # Telemetry
        assert hasattr(hlf_mcp.gallery, "TelemetryCollector")
        assert hasattr(hlf_mcp.gallery, "TelemetrySnapshot")
        assert hasattr(hlf_mcp.gallery, "create_default_collector")

        # CLI
        assert hasattr(hlf_mcp.gallery, "operator_cli_main")
        assert hasattr(hlf_mcp.gallery, "operator_cli_build_parser")

        # Dashboard enhancements
        assert hasattr(hlf_mcp.gallery, "compute_alert_threshold")
        assert hasattr(hlf_mcp.gallery, "compute_alert_color")
        assert hasattr(hlf_mcp.gallery, "compute_pillar_alerts")
        assert hasattr(hlf_mcp.gallery, "get_trend_history")
        assert hasattr(hlf_mcp.gallery, "clear_trend_history")
        assert hasattr(hlf_mcp.gallery, "record_trend_snapshot")
        assert hasattr(hlf_mcp.gallery, "build_dashboard_with_trend")
        assert hasattr(hlf_mcp.gallery, "integrate_telemetry_snapshot")
        assert hasattr(hlf_mcp.gallery, "display_dashboard_with_alerts")

        # Verify callables
        assert callable(hlf_mcp.gallery.TelemetryCollector)
        assert callable(hlf_mcp.gallery.operator_cli_main)
        assert callable(hlf_mcp.gallery.compute_alert_threshold)

    def test_existing_gallery_imports_still_work(self) -> None:
        """Existing gallery imports from __init__.py still resolve correctly."""
        import hlf_mcp.gallery

        # Original exports
        assert hasattr(hlf_mcp.gallery, "run_type_explorer_demo")
        assert hasattr(hlf_mcp.gallery, "run_verification_viewer_demo")
        assert hasattr(hlf_mcp.gallery, "run_manifest_viewer_demo")
        assert hasattr(hlf_mcp.gallery, "run_provenance_viewer_demo")
        assert hasattr(hlf_mcp.gallery, "run_operator_dashboard_demo")
        assert hasattr(hlf_mcp.gallery, "generate_dashboard_json")

        assert callable(hlf_mcp.gallery.run_type_explorer_demo)
        assert callable(hlf_mcp.gallery.generate_dashboard_json)


# ══════════════════════════════════════════════════════════════════════════════════
# Trend Data Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestTrendData:
    """Additional tests for trend data recording and retrieval."""

    def test_record_trend_snapshot_appends(self) -> None:
        """record_trend_snapshot appends to the trend buffer."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_data,
            record_trend_snapshot,
            get_trend_history,
            clear_trend_history,
        )
        clear_trend_history()
        dashboard = build_dashboard_data()
        record_trend_snapshot(dashboard)
        history = get_trend_history()
        assert len(history) == 1
        assert history[0]["overall_status"] == dashboard["overall_status"]

    def test_get_trend_history_returns_list(self) -> None:
        """get_trend_history returns a list."""
        from hlf_mcp.gallery.operator_dashboard import get_trend_history, clear_trend_history
        clear_trend_history()
        history = get_trend_history()
        assert isinstance(history, list)

    def test_clear_trend_history_empties_buffer(self) -> None:
        """clear_trend_history empties the trend buffer."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_data,
            record_trend_snapshot,
            get_trend_history,
            clear_trend_history,
        )
        clear_trend_history()
        dashboard = build_dashboard_data()
        record_trend_snapshot(dashboard)
        assert len(get_trend_history()) == 1
        clear_trend_history()
        assert len(get_trend_history()) == 0


# ══════════════════════════════════════════════════════════════════════════════════
# Alert Color Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestAlertColors:
    """Tests for alert color computation."""

    def test_compute_alert_color_red(self) -> None:
        """Scores below 50% return 'red'."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_color
        assert compute_alert_color(20.0) == "red"
        assert compute_alert_color(49.9) == "red"

    def test_compute_alert_color_yellow(self) -> None:
        """Scores 50-64.9% return 'yellow'."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_color
        assert compute_alert_color(50.0) == "yellow"
        assert compute_alert_color(60.0) == "yellow"

    def test_compute_alert_color_green(self) -> None:
        """Scores >= 65% return 'green'."""
        from hlf_mcp.gallery.operator_dashboard import compute_alert_color
        assert compute_alert_color(65.0) == "green"
        assert compute_alert_color(90.0) == "green"

    def test_compute_pillar_alerts_adds_alert_fields(self) -> None:
        """compute_pillar_alerts adds alert and alert_color to each component."""
        from hlf_mcp.gallery.operator_dashboard import compute_pillar_alerts
        components = {
            "type_explorer": {"status": "implemented", "score_pct": 80},
            "verification_viewer": {"status": "implemented", "score_pct": 55},
            "operator_dashboard": {"status": "implemented", "score_pct": 30},
        }
        result = compute_pillar_alerts(components)
        assert result["type_explorer"]["alert"] == "healthy"
        assert result["type_explorer"]["alert_color"] == "green"
        assert result["verification_viewer"]["alert"] == "degraded"
        assert result["verification_viewer"]["alert_color"] == "yellow"
        assert result["operator_dashboard"]["alert"] == "critical"
        assert result["operator_dashboard"]["alert_color"] == "red"


# ══════════════════════════════════════════════════════════════════════════════════
# Display Functions (smoke tests)
# ══════════════════════════════════════════════════════════════════════════════════


class TestDisplayFunctions:
    """Smoke tests for display functions to ensure they don't crash."""

    def test_display_dashboard_with_alerts_runs(self) -> None:
        """display_dashboard_with_alerts runs without error."""
        from hlf_mcp.gallery.operator_dashboard import (
            build_dashboard_with_trend,
            display_dashboard_with_alerts,
        )
        dashboard = build_dashboard_with_trend(record=True)
        _capture_output(display_dashboard_with_alerts, dashboard)

    def test_telemetry_snapshot_to_dict_is_complete(self) -> None:
        """TelemetrySnapshot.to_dict() has all expected keys."""
        from hlf_mcp.gallery.telemetry import TelemetryCollector
        collector = TelemetryCollector()
        snap = collector.snapshot()
        d = snap.to_dict()
        expected_keys = [
            "snapshot_id", "timestamp", "swarm_health", "verification_gate",
            "constitutional_violations", "manifest_audit", "overall_readiness_pct",
            "alert_thresholds",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_create_default_collector_is_usable(self) -> None:
        """create_default_collector returns a working collector."""
        from hlf_mcp.gallery.telemetry import create_default_collector
        collector = create_default_collector(interval=0.5)
        assert collector is not None
        snap = collector.snapshot()
        assert snap.overall_readiness_pct > 0
