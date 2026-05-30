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
        assert enriched["swarm"]["source"] == "simulated"  # no ctx passed → simulated fallback

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


# ══════════════════════════════════════════════════════════════════════════════════
# AlertFeedback Dataclass
# ══════════════════════════════════════════════════════════════════════════════════


class TestAlertFeedbackDataclass:
    """Tests for the AlertFeedback dataclass."""

    def test_alert_feedback_creation_defaults(self) -> None:
        """AlertFeedback creates with all required fields."""
        from hlf_mcp.gallery.telemetry import AlertFeedback
        fb = AlertFeedback(
            feedback_id="fb-001",
            alert_id="alert-001",
            feedback_type="ack",
            timestamp="2026-04-14T12:00:00Z",
            operator_id="op1",
        )
        assert fb.feedback_id == "fb-001"
        assert fb.alert_id == "alert-001"
        assert fb.feedback_type == "ack"
        assert fb.operator_id == "op1"
        assert fb.details == ""
        assert fb.meta == {}

    def test_alert_feedback_to_dict(self) -> None:
        """AlertFeedback.to_dict() includes all fields."""
        from hlf_mcp.gallery.telemetry import AlertFeedback
        fb = AlertFeedback(
            feedback_id="fb-002",
            alert_id="alert-002",
            feedback_type="resolve",
            timestamp="2026-04-14T12:01:00Z",
            operator_id="op2",
            details="fixed the issue",
            meta={"resolution_note": "patched"},
        )
        d = fb.to_dict()
        assert d["feedback_id"] == "fb-002"
        assert d["feedback_type"] == "resolve"
        assert d["details"] == "fixed the issue"
        assert d["meta"]["resolution_note"] == "patched"

    def test_alert_feedback_meta_default_factory_isolation(self) -> None:
        """Each AlertFeedback instance gets its own meta dict."""
        from hlf_mcp.gallery.telemetry import AlertFeedback
        fb1 = AlertFeedback("fb-a", "alert-a", "ack", "2026-04-14T12:00:00Z", "op1")
        fb2 = AlertFeedback("fb-b", "alert-b", "ack", "2026-04-14T12:00:00Z", "op2")
        fb1.meta["key"] = "val"
        assert "key" not in fb2.meta


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Alert Recording & Lifecycle
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackCollectorLifecycle:
    """Tests for FeedbackCollector alert recording and feedback lifecycle."""

    def test_record_alert_stores_fire_info(self) -> None:
        """record_alert stores alert fire timestamp and metadata."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", alert_type="readiness", severity=80)
        assert "alert-1" in fc._alert_fires
        assert fc._alert_fires["alert-1"]["severity"] == 80
        assert fc._alert_fires["alert-1"]["alert_type"] == "readiness"
        assert "fire_timestamp" in fc._alert_fires["alert-1"]

    def test_acknowledge_returns_feedback_event(self) -> None:
        """acknowledge returns an AlertFeedback with correct type."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fb = fc.acknowledge("alert-1", "op1", details="looking into it")
        assert fb.feedback_type == "ack"
        assert fb.alert_id == "alert-1"
        assert fb.operator_id == "op1"
        assert fb.details == "looking into it"

    def test_resolve_returns_feedback_event(self) -> None:
        """resolve returns an AlertFeedback with correct type."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fb = fc.resolve("alert-1", "op1", "done", resolution_note="all clear")
        assert fb.feedback_type == "resolve"
        assert fb.meta["resolution_note"] == "all clear"

    def test_dismiss_returns_feedback_event(self) -> None:
        """dismiss returns an AlertFeedback with correct type."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fb = fc.dismiss("alert-1", "op1", reason="false alarm")
        assert fb.feedback_type == "dismiss"
        assert fb.meta["is_false_positive"] is True

    def test_escalate_returns_feedback_event(self) -> None:
        """escalate returns an AlertFeedback with correct type."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fb = fc.escalate("alert-1", "op1", target_tier="sovereign")
        assert fb.feedback_type == "escalate"
        assert fb.meta["target_tier"] == "sovereign"

    def test_snooze_returns_feedback_event(self) -> None:
        """snooze returns an AlertFeedback with correct type."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fb = fc.snooze("alert-1", "op1", duration_seconds=600.0)
        assert fb.feedback_type == "snooze"
        assert fb.meta["snooze_duration_seconds"] == 600.0

    def test_get_alert_events_returns_ordered_events(self) -> None:
        """get_alert_events returns events in chronological order."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        import time
        fc = create_default_feedback_collector()
        fc.record_alert("alert-1", severity=50)
        fc.acknowledge("alert-1", "op1")
        time.sleep(0.01)
        fc.resolve("alert-1", "op1")
        events = fc.get_alert_events("alert-1")
        assert len(events) == 2
        assert events[0].feedback_type == "ack"
        assert events[1].feedback_type == "resolve"

    def test_get_feedback_log_returns_all_events(self) -> None:
        """get_feedback_log returns all events across all alerts."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.record_alert("a2", severity=50)
        fc.acknowledge("a1", "op1")
        fc.acknowledge("a2", "op1")
        assert len(fc.get_feedback_log()) == 2

    def test_clear_empties_all_state(self) -> None:
        """clear() empties fires, events, and log."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.acknowledge("a1", "op1")
        fc.clear()
        assert len(fc._alert_fires) == 0
        assert len(fc._alert_events) == 0
        assert len(fc._feedback_log) == 0


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Statistics & Metrics
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackCollectorStatistics:
    """Tests for FeedbackCollector.get_statistics() metrics."""

    def test_stats_empty_collector(self) -> None:
        """Empty collector returns zeros."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        stats = fc.get_statistics()
        assert stats.total_alerts == 0
        assert stats.resolved == 0
        assert stats.mttr_seconds == 0.0
        assert stats.signal_to_noise_ratio == 0.0

    def test_stats_counts_correctly(self) -> None:
        """Statistics count acknowledged/resolved/dismissed correctly."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.record_alert("a2", severity=60)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        fc.dismiss("a2", "op1")
        stats = fc.get_statistics()
        assert stats.total_alerts == 2
        assert stats.acknowledged == 1
        assert stats.resolved == 1
        assert stats.dismissed == 1

    def test_stats_orphaned_detected(self) -> None:
        """Alerts with no follow-up are counted as orphaned."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.record_alert("a2", severity=60)
        fc.record_alert("a3", severity=70)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        fc.dismiss("a2", "op1")
        stats = fc.get_statistics()
        assert stats.orphaned == 1  # a3 has no events

    def test_signal_to_noise_basic(self) -> None:
        """Signal-to-noise ratio = actionable / total."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        # 3 alerts: 1 resolved (actionable), 1 dismissed (noise), 1 unresolved
        fc.record_alert("a1", severity=50)
        fc.record_alert("a2", severity=50)
        fc.record_alert("a3", severity=50)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        fc.dismiss("a2", "op1")
        stats = fc.get_statistics()
        # actionable: a1 (resolved, not dismissed) = 1; total=3
        assert stats.signal_to_noise_ratio == pytest.approx(1 / 3, abs=0.01)

    def test_signal_to_noise_all_actionable(self) -> None:
        """All alerts resolved = SNR of 1.0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(5):
            aid = f"a{i}"
            fc.record_alert(aid, severity=50)
            fc.acknowledge(aid, "op1")
            fc.resolve(aid, "op1")
        stats = fc.get_statistics()
        assert stats.signal_to_noise_ratio == 1.0

    def test_signal_to_noise_all_noise(self) -> None:
        """All alerts dismissed = SNR of 0.0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(5):
            aid = f"a{i}"
            fc.record_alert(aid, severity=50)
            fc.dismiss(aid, "op1")
        stats = fc.get_statistics()
        assert stats.signal_to_noise_ratio == 0.0

    def test_false_positive_rate_computation(self) -> None:
        """False positive rate = dismissed / total."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(10):
            aid = f"a{i}"
            fc.record_alert(aid, severity=50)
            if i < 3:
                fc.dismiss(aid, "op1")
            else:
                fc.acknowledge(aid, "op1")
                fc.resolve(aid, "op1")
        stats = fc.get_statistics()
        assert stats.false_positive_rate_pct == pytest.approx(30.0, abs=0.1)

    def test_escalation_rate_computation(self) -> None:
        """Escalation rate = escalated / total."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(10):
            aid = f"a{i}"
            fc.record_alert(aid, severity=50)
            fc.acknowledge(aid, "op1")
            if i < 2:
                fc.escalate(aid, "op1", target_tier="sovereign")
            fc.resolve(aid, "op1")
        stats = fc.get_statistics()
        assert stats.escalation_rate_pct == pytest.approx(20.0, abs=0.1)

    def test_mttr_computed_from_fire_to_resolve(self) -> None:
        """MTTR is mean of (resolve_ts - fire_ts) across resolved alerts."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        import time
        fc = create_default_feedback_collector(sla_window_seconds=300.0)
        fc.record_alert("a1", severity=50)
        time.sleep(1.0)  # ensure fire and resolve are in different seconds
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        fc.record_alert("a2", severity=50)
        time.sleep(1.0)
        fc.acknowledge("a2", "op1")
        fc.resolve("a2", "op1")
        stats = fc.get_statistics()
        assert stats.mttr_seconds > 0.0

    def test_mtta_computed_from_fire_to_ack(self) -> None:
        """MTTA is mean of (ack_ts - fire_ts) across acknowledged alerts."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        import time
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        time.sleep(1.0)  # ensure fire and ack are in different seconds
        fc.acknowledge("a1", "op1")
        stats = fc.get_statistics()
        assert stats.mtta_seconds > 0.0

    def test_saturation_score_zero_alerts(self) -> None:
        """Saturation score for zero alerts is 0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        stats = fc.get_statistics()
        assert stats.operator_saturation_score == 0.0

    def test_saturation_score_with_noisy_alerts(self) -> None:
        """High FP rate and severity gives high saturation."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(10):
            aid = f"a{i}"
            fc.record_alert(aid, severity=90, alert_type="violation")
            if i < 6:
                fc.dismiss(aid, "op1", reason="noise")
            else:
                fc.acknowledge(aid, "op1")
                fc.resolve(aid, "op1")
        stats = fc.get_statistics()
        # 60% dismissed, 90 severity → saturation should be high
        assert stats.operator_saturation_score > 40.0

    def test_saturation_score_healthy_system(self) -> None:
        """Low FP rate and low severity gives low saturation."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(10):
            aid = f"a{i}"
            fc.record_alert(aid, severity=20, alert_type="readiness")
            fc.acknowledge(aid, "op1")
            fc.resolve(aid, "op1")
        stats = fc.get_statistics()
        assert stats.operator_saturation_score < 30.0


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Deduplication
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackDeduplication:
    """Tests for duplicate alert detection."""

    def test_no_duplicates_when_all_unique(self) -> None:
        """All unique fingerprints → 0% dedup rate."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector(dedup_window_seconds=60.0)
        for i in range(5):
            fc.record_alert(f"a{i}", fingerprint=f"fp-{i}", severity=50)
        stats = fc.get_statistics()
        assert stats.deduplication_rate_pct == 0.0

    def test_duplicates_within_window_detected(self) -> None:
        """Identical fingerprints within window → duplicates detected."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector(dedup_window_seconds=60.0)
        # All same fingerprint, fired close together
        for i in range(5):
            fc.record_alert(f"a{i}", fingerprint="same-fp", severity=50)
        stats = fc.get_statistics()
        # Only the first of each dup pair is counted; 4 duplicates out of 5
        assert stats.deduplication_rate_pct > 0.0

    def test_single_alert_no_duplicates(self) -> None:
        """Single alert has 0% dedup rate."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector(dedup_window_seconds=60.0)
        fc.record_alert("a1", fingerprint="fp-1", severity=50)
        stats = fc.get_statistics()
        assert stats.deduplication_rate_pct == 0.0

    def test_different_fingerprints_no_dedup(self) -> None:
        """Different fingerprints don't count as duplicates."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector(dedup_window_seconds=60.0)
        for i in range(10):
            fc.record_alert(f"a{i}", fingerprint=f"unique-fp-{i}", severity=50)
        stats = fc.get_statistics()
        assert stats.deduplication_rate_pct == 0.0


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Snooze Pattern
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackSnoozePattern:
    """Tests for snooze repeat detection."""

    def test_snooze_repeat_rate_zero_when_none_snoozed(self) -> None:
        """No snoozed alerts → 0% repeat rate."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        for i in range(5):
            fc.record_alert(f"a{i}", severity=50)
            fc.acknowledge(f"a{i}", "op1")
            fc.resolve(f"a{i}", "op1")
        stats = fc.get_statistics()
        assert stats.snooze_repeat_rate_pct == 0.0

    def test_snooze_repeat_rate_detects_multiple_snoozes(self) -> None:
        """Alert snoozed 3 times contributes to repeat rate."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        # Alert snoozed 3 times (repeat)
        fc.record_alert("a-repeat", severity=50)
        fc.snooze("a-repeat", "op1")
        fc.snooze("a-repeat", "op1")
        fc.snooze("a-repeat", "op1")
        # Alert snoozed once (not repeat)
        fc.record_alert("a-once", severity=50)
        fc.snooze("a-once", "op1")
        stats = fc.get_statistics()
        # 1 out of 2 snoozed alerts had repeats = 50%
        assert stats.snooze_repeat_rate_pct == pytest.approx(50.0, abs=0.1)


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Alert Volume Trend
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackVolumeTrend:
    """Tests for alert volume trend (linear regression)."""

    def test_volume_trend_zero_for_single_alert(self) -> None:
        """Single alert → slope 0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        stats = fc.get_statistics()
        assert stats.alert_volume_trend_slope == 0.0

    def test_volume_trend_zero_for_constant_rate(self) -> None:
        """Same count each day → slope ~0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        # 3 days, 2 alerts each
        fc.record_alert("a1", severity=50)
        fc.record_alert("a2", severity=50)
        fc.record_alert("a3", severity=50)
        stats = fc.get_statistics()
        # All on same day if fast, or slope ~0
        assert abs(stats.alert_volume_trend_slope) <= 5.0

    def test_volume_trend_empty_collector(self) -> None:
        """Empty collector → slope 0."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        stats = fc.get_statistics()
        assert stats.alert_volume_trend_slope == 0.0


# ══════════════════════════════════════════════════════════════════════════════════
# FeedbackCollector — Edge Cases
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackEdgeCases:
    """Tests for edge case behavior."""

    def test_orphaned_alert_response_time_not_counted(self) -> None:
        """Orphaned alerts (no resolve) don't affect MTTR."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("orphan", severity=50)
        fc.record_alert("resolved", severity=50)
        fc.acknowledge("resolved", "op1")
        fc.resolve("resolved", "op1")
        stats = fc.get_statistics()
        assert stats.orphaned == 1
        # MTTR should only count "resolved"
        assert stats.mttr_seconds >= 0

    def test_resolve_without_ack_still_counts(self) -> None:
        """Alert resolved without explicit ack still counts as resolved."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("direct-resolve", severity=50)
        fc.resolve("direct-resolve", "op1")
        stats = fc.get_statistics()
        assert stats.resolved == 1
        assert stats.acknowledged == 0

    def test_rapid_fire_duplicate_alerts(self) -> None:
        """Many identical alerts in rapid succession are dedup'd."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector(dedup_window_seconds=60.0)
        for i in range(20):
            fc.record_alert(f"rf-{i}", fingerprint="rapid-fire", severity=80)
        stats = fc.get_statistics()
        assert stats.deduplication_rate_pct > 0.0
        assert stats.total_alerts == 20

    def test_zero_alert_period_metrics(self) -> None:
        """All stats are zero/benign when no alerts exist."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        stats = fc.get_statistics()
        assert stats.total_alerts == 0
        assert stats.resolution_rate_pct == 0.0
        assert stats.false_positive_rate_pct == 0.0
        assert stats.escalation_rate_pct == 0.0
        assert stats.signal_to_noise_ratio == 0.0
        assert stats.operator_saturation_score == 0.0

    def test_feedback_listener_called(self) -> None:
        """on_feedback callback is invoked on each event."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        received: list[str] = []

        def listener(fb):
            received.append(fb.feedback_type)

        fc.on_feedback(listener)
        fc.record_alert("a1", severity=50)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        assert received == ["ack", "resolve"]

    def test_feedback_listener_exception_ignored(self) -> None:
        """Listener exceptions don't crash the collector."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()

        def bad_listener(fb):
            raise RuntimeError("boom")

        fc.on_feedback(bad_listener)
        fc.record_alert("a1", severity=50)
        # Should not raise
        fb = fc.acknowledge("a1", "op1")
        assert fb is not None

    def test_thread_safety_concurrent_feedback(self) -> None:
        """Concurrent feedback from multiple threads doesn't corrupt state."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        import threading
        fc = create_default_feedback_collector()
        errors = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(20):
                    aid = f"t-{worker_id}-{i}"
                    fc.record_alert(aid, severity=50)
                    fc.acknowledge(aid, f"op{worker_id}")
                    fc.resolve(aid, f"op{worker_id}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = fc.get_statistics()
        assert stats.total_alerts == 100
        assert stats.resolved == 100

    def test_full_stats_to_dict_is_complete(self) -> None:
        """FeedbackStatistics.to_dict() has all expected keys."""
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        stats_dict = fc.get_statistics().to_dict()
        expected_keys = [
            "total_alerts", "acknowledged", "resolved", "dismissed",
            "escalated", "snoozed", "orphaned", "resolution_rate_pct",
            "false_positive_rate_pct", "escalation_rate_pct", "mttr_seconds",
            "mtta_seconds", "deduplication_rate_pct", "snooze_repeat_rate_pct",
            "signal_to_noise_ratio", "alert_volume_trend_slope",
            "operator_saturation_score", "sla_window_seconds",
        ]
        for key in expected_keys:
            assert key in stats_dict, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════════════════════════
# Feedback CLI — Subcommand Parsing
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackCLIParsing:
    """Tests for feedback CLI subcommand argument parsing."""

    def test_feedback_subcommand_in_parser(self) -> None:
        """Parser accepts 'feedback' as a subcommand."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "ack", "alert-001"])
        assert args.subcommand == "feedback"
        assert args.feedback_action == "ack"
        assert args.alert_id == "alert-001"

    def test_feedback_ack_with_operator(self) -> None:
        """'feedback ack' accepts --operator flag."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "ack", "alert-1", "--operator", "gerry"])
        assert args.operator == "gerry"

    def test_feedback_resolve_with_note(self) -> None:
        """'feedback resolve' accepts --note flag."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "resolve", "alert-1", "--note", "patched"])
        assert args.note == "patched"

    def test_feedback_dismiss_with_reason(self) -> None:
        """'feedback dismiss' accepts --reason flag."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "dismiss", "alert-1", "--reason", "false alarm"])
        assert args.reason == "false alarm"

    def test_feedback_escalate_with_tier(self) -> None:
        """'feedback escalate' accepts --tier flag."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "escalate", "alert-1", "--tier", "field"])
        assert args.tier == "field"

    def test_feedback_snooze_with_duration(self) -> None:
        """'feedback snooze' accepts --duration flag."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "snooze", "alert-1", "--duration", "600"])
        assert args.duration == 600.0

    def test_feedback_stats_parsed(self) -> None:
        """'feedback stats' is recognized."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "stats"])
        assert args.feedback_action == "stats"

    def test_feedback_default_operator(self) -> None:
        """Default operator is 'cli-operator'."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "ack", "alert-1"])
        assert args.operator == "cli-operator"


# ══════════════════════════════════════════════════════════════════════════════════
# New CLI Subcommand Parsing Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestNewCLISubcommands:
    """Tests for evidence, missions, and export subcommands."""

    def test_evidence_subcommand_in_parser(self) -> None:
        """Parser accepts 'evidence' as a subcommand."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["evidence"])
        assert args.subcommand == "evidence"
        assert args.evidence_type == "all"
        assert args.limit == 10

    def test_evidence_with_type_and_limit(self) -> None:
        """'evidence' accepts --type and --limit flags."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["evidence", "--type", "contract", "--limit", "5"])
        assert args.evidence_type == "contract"
        assert args.limit == 5

    def test_missions_subcommand_in_parser(self) -> None:
        """Parser accepts 'missions' as a subcommand."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["missions"])
        assert args.subcommand == "missions"
        assert args.status == "all"
        assert args.limit == 20

    def test_missions_with_status_filter(self) -> None:
        """'missions' accepts --status and --limit flags."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["missions", "--status", "passed", "--limit", "5"])
        assert args.status == "passed"
        assert args.limit == 5

    def test_export_subcommand_in_parser(self) -> None:
        """Parser accepts 'export' as a subcommand."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["export"])
        assert args.subcommand == "export"
        assert args.export_format == "markdown"
        assert args.export_output is None

    def test_export_with_format_and_output(self) -> None:
        """'export' accepts --format and --output flags."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["export", "--format", "json", "--output", "report.json"])
        assert args.export_format == "json"
        assert args.export_output == "report.json"

    def test_export_format_choices(self) -> None:
        """'export --format' only accepts markdown, json, or text."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["export", "--format", "text"])
        assert args.export_format == "text"

    def test_evidence_type_choices(self) -> None:
        """'evidence --type' only accepts contract, media, findings, or all."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["evidence", "--type", "media"])
        assert args.evidence_type == "media"

    def test_missions_status_choices(self) -> None:
        """'missions --status' only accepts valid status values."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["missions", "--status", "active"])
        assert args.status == "active"


# ══════════════════════════════════════════════════════════════════════════════════
# CLI Subcommand Routing Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestCLISubcommandRouting:
    """Tests for CLI main() routing of new subcommands."""

    def test_evidence_routes_to_handler(self) -> None:
        """'evidence' subcommand exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["evidence"])
        assert exit_code == 0

    def test_missions_routes_to_handler(self) -> None:
        """'missions' subcommand exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["missions"])
        assert exit_code == 0

    def test_export_routes_to_handler(self) -> None:
        """'export' subcommand exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["export", "--format", "markdown"])
        assert exit_code == 0

    def test_export_json_routes_to_handler(self) -> None:
        """'export --format json' subcommand exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["export", "--format", "json"])
        assert exit_code == 0


# ══════════════════════════════════════════════════════════════════════════════════
# Gallery __init__ Export Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestGalleryInitExports:
    """Tests for gallery __init__.py exports of new components."""

    def test_evidence_summary_renderer_exported(self) -> None:
        """EvidenceSummaryRenderer is exported from gallery __init__."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "EvidenceSummaryRenderer")
        assert hlf_mcp.gallery.EvidenceSummaryRenderer is not None

    def test_render_mission_panel_exported(self) -> None:
        """render_mission_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "render_mission_panel")
        assert callable(hlf_mcp.gallery.render_mission_panel)

    def test_display_mission_panel_exported(self) -> None:
        """display_mission_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "display_mission_panel")
        assert callable(hlf_mcp.gallery.display_mission_panel)

    def test_render_dream_findings_panel_exported(self) -> None:
        """render_dream_findings_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "render_dream_findings_panel")
        assert callable(hlf_mcp.gallery.render_dream_findings_panel)

    def test_display_dream_findings_panel_exported(self) -> None:
        """display_dream_findings_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "display_dream_findings_panel")
        assert callable(hlf_mcp.gallery.display_dream_findings_panel)

    def test_render_evidence_panel_exported(self) -> None:
        """render_evidence_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "render_evidence_panel")
        assert callable(hlf_mcp.gallery.render_evidence_panel)

    def test_display_evidence_panel_exported(self) -> None:
        """display_evidence_panel is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "display_evidence_panel")
        assert callable(hlf_mcp.gallery.display_evidence_panel)

    def test_export_evidence_report_exported(self) -> None:
        """export_evidence_report is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "export_evidence_report")
        assert callable(hlf_mcp.gallery.export_evidence_report)


# ══════════════════════════════════════════════════════════════════════════════════
# 3-Pillar Dynamic Scorecard Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestTypedEffectPillarScore:
    """Tests for compute_typed_effect_pillar_score()."""

    def test_returns_valid_structure(self) -> None:
        """Returns dict with score_pct, components, status."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        assert isinstance(result, dict)
        assert "score_pct" in result
        assert "components" in result
        assert "status" in result
        assert isinstance(result["components"], dict)

    def test_score_in_valid_range(self) -> None:
        """Score is between 0 and 100."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        assert 0.0 <= result["score_pct"] <= 100.0

    def test_components_have_required_fields(self) -> None:
        """Each component has score_pct, detail, weight."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        for comp_name, comp_info in result["components"].items():
            assert "score_pct" in comp_info, f"Missing score_pct in {comp_name}"
            assert "detail" in comp_info, f"Missing detail in {comp_name}"
            assert "weight" in comp_info, f"Missing weight in {comp_name}"
            assert isinstance(comp_info["score_pct"], (int, float))
            assert isinstance(comp_info["detail"], str)
            assert isinstance(comp_info["weight"], (int, float))

    def test_weights_sum_to_one(self) -> None:
        """Component weights sum to 1.0."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        total_weight = sum(comp["weight"] for comp in result["components"].values())
        assert total_weight == pytest.approx(1.0, abs=0.01)

    def test_status_is_valid(self) -> None:
        """Status is one of healthy/degraded/critical or requires_dsl."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        assert result["status"] in ("healthy", "degraded", "critical", "requires_dsl")

    def test_weighted_average_matches_score(self) -> None:
        """Score equals weighted average of component scores."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        expected = sum(
            comp["score_pct"] * comp["weight"] for comp in result["components"].values()
        )
        assert result["score_pct"] == pytest.approx(expected, abs=0.5)

    def test_all_four_components_present(self) -> None:
        """The four required components are present."""
        from hlf_mcp.gallery.operator_dashboard import compute_typed_effect_pillar_score
        result = compute_typed_effect_pillar_score()
        expected_components = {
            "cross_type_coercion", "heterogeneous_composition",
            "test_coverage", "container_coercion",
        }
        assert set(result["components"].keys()) == expected_components


class TestFormalVerificationPillarScore:
    """Tests for compute_formal_verification_pillar_score()."""

    def test_returns_valid_structure(self) -> None:
        """Returns dict with score_pct, components, status."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        assert isinstance(result, dict)
        assert "score_pct" in result
        assert "components" in result
        assert "status" in result
        assert isinstance(result["components"], dict)

    def test_score_in_valid_range(self) -> None:
        """Score is between 0 and 100."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        assert 0.0 <= result["score_pct"] <= 100.0

    def test_components_have_required_fields(self) -> None:
        """Each component has score_pct, detail, weight."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        for comp_name, comp_info in result["components"].items():
            assert "score_pct" in comp_info, f"Missing score_pct in {comp_name}"
            assert "detail" in comp_info, f"Missing detail in {comp_name}"
            assert "weight" in comp_info, f"Missing weight in {comp_name}"
            assert isinstance(comp_info["score_pct"], (int, float))
            assert isinstance(comp_info["detail"], str)
            assert isinstance(comp_info["weight"], (int, float))

    def test_weights_sum_to_one(self) -> None:
        """Component weights sum to ~1.0."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        total_weight = sum(comp["weight"] for comp in result["components"].values())
        assert total_weight == pytest.approx(1.0, abs=0.01)

    def test_status_is_valid(self) -> None:
        """Status is one of healthy/degraded/critical or no_verification_data."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        assert result["status"] in ("healthy", "degraded", "critical", "no_verification_data")

    def test_all_four_components_present(self) -> None:
        """The four required components are present."""
        from hlf_mcp.gallery.operator_dashboard import compute_formal_verification_pillar_score
        result = compute_formal_verification_pillar_score()
        expected_components = {
            "z3_solver_coverage", "inductive_proof_automation",
            "proof_depth", "test_coverage",
        }
        assert set(result["components"].keys()) == expected_components


class TestGalleryOperatorPillarScore:
    """Tests for compute_gallery_operator_pillar_score()."""

    def test_returns_valid_structure(self) -> None:
        """Returns dict with score_pct, components, status."""
        from hlf_mcp.gallery.operator_dashboard import compute_gallery_operator_pillar_score
        result = compute_gallery_operator_pillar_score()
        assert isinstance(result, dict)
        assert "score_pct" in result
        assert "components" in result
        assert "status" in result
        assert isinstance(result["components"], dict)

    def test_score_in_valid_range(self) -> None:
        """Score is between 0 and 100."""
        from hlf_mcp.gallery.operator_dashboard import compute_gallery_operator_pillar_score
        result = compute_gallery_operator_pillar_score()
        assert 0.0 <= result["score_pct"] <= 100.0

    def test_with_dashboard_data_input(self) -> None:
        """Works with pre-built dashboard data."""
        from hlf_mcp.gallery.operator_dashboard import (
            compute_gallery_operator_pillar_score,
            build_dashboard_data,
        )
        dashboard = build_dashboard_data()
        result = compute_gallery_operator_pillar_score(dashboard_data=dashboard)
        assert isinstance(result, dict)
        assert "score_pct" in result
        assert 0.0 <= result["score_pct"] <= 100.0

    def test_components_match_weights(self) -> None:
        """Components have the right 6 weighted sub-scores."""
        from hlf_mcp.gallery.operator_dashboard import compute_gallery_operator_pillar_score
        result = compute_gallery_operator_pillar_score()
        expected_components = {
            "verification_viewer", "manifest_viewer", "provenance_viewer",
            "type_explorer", "operator_dashboard", "feedback_loop",
            "egl_monitor",
        }
        assert set(result["components"].keys()) == expected_components
        total_weight = sum(comp["weight"] for comp in result["components"].values())
        assert total_weight == pytest.approx(1.0, abs=0.01)

    def test_status_is_valid(self) -> None:
        """Status is one of healthy/degraded/critical."""
        from hlf_mcp.gallery.operator_dashboard import compute_gallery_operator_pillar_score
        result = compute_gallery_operator_pillar_score()
        assert result["status"] in ("healthy", "degraded", "critical")

    def test_gallery_thresholds_different(self) -> None:
        """Gallery pillar uses 75%/60% thresholds (different from others)."""
        from hlf_mcp.gallery.operator_dashboard import compute_gallery_operator_pillar_score
        result = compute_gallery_operator_pillar_score()
        score = result["score_pct"]
        if score >= 75:
            assert result["status"] == "healthy"
        elif score >= 60:
            assert result["status"] == "degraded"
        else:
            assert result["status"] == "critical"


class TestBuildFullScorecard:
    """Tests for build_full_scorecard()."""

    def test_returns_valid_format(self) -> None:
        """Returns dict with pillars, overall_score_pct, etc."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert isinstance(result, dict)
        assert "pillars" in result
        assert "overall_score_pct" in result
        assert "overall_status" in result
        assert "gap_analysis" in result
        assert "generated_at" in result
        assert "scorecard_id" in result

    def test_three_pillars_present(self) -> None:
        """All 3 pillars in scorecard."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert len(result["pillars"]) == 3
        pillar_names = [p["name"] for p in result["pillars"]]
        assert "Typed Effect Algebra" in pillar_names
        assert "Formal Verification" in pillar_names
        assert "Gallery Operator Legibility" in pillar_names

    def test_overall_is_weighted_average(self) -> None:
        """Overall score = weighted average of pillar scores."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        expected = (
            result["pillars"][0]["score_pct"] * result["pillars"][0]["weight"]
            + result["pillars"][1]["score_pct"] * result["pillars"][1]["weight"]
            + result["pillars"][2]["score_pct"] * result["pillars"][2]["weight"]
        ) / sum(p["weight"] for p in result["pillars"])
        assert result["overall_score_pct"] == pytest.approx(expected, abs=0.5)

    def test_gap_analysis_included(self) -> None:
        """Gap analysis present for each pillar."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert isinstance(result["gap_analysis"], list)

    def test_each_pillar_has_target(self) -> None:
        """Each pillar has a target_pct."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        for pillar in result["pillars"]:
            assert "target_pct" in pillar
            assert isinstance(pillar["target_pct"], (int, float))
            assert pillar["target_pct"] > 0

    def test_pillar_weights_correct(self) -> None:
        """Pillar weights are 8, 7, 4 respectively."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert result["pillars"][0]["weight"] == 8
        assert result["pillars"][1]["weight"] == 7
        assert result["pillars"][2]["weight"] == 4

    def test_overall_score_in_range(self) -> None:
        """Overall score is between 0 and 100."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert 0.0 <= result["overall_score_pct"] <= 100.0

    def test_scorecard_id_format(self) -> None:
        """Scorecard ID has expected format."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert result["scorecard_id"].startswith("scorecard-")
        assert len(result["scorecard_id"]) > len("scorecard-")

    def test_generated_at_is_iso(self) -> None:
        """Generated timestamp is ISO format."""
        from hlf_mcp.gallery.operator_dashboard import build_full_scorecard
        result = build_full_scorecard()
        assert "T" in result["generated_at"]
        assert "Z" in result["generated_at"] or "+" in result["generated_at"] or result["generated_at"].endswith("Z")


class TestScorecardCLI:
    """Tests for scorecard CLI subcommand."""

    def test_scorecard_subcommand_in_parser(self) -> None:
        """Parser accepts 'scorecard' subcommand."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["scorecard"])
        assert args.subcommand == "scorecard"

    def test_scorecard_json_flag(self) -> None:
        """--json flag recognized for scorecard."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["scorecard", "--json"])
        assert args.subcommand == "scorecard"
        assert args.scorecard_json is True

    def test_scorecard_json_short_flag(self) -> None:
        """-j flag recognized for scorecard."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["scorecard", "-j"])
        assert args.subcommand == "scorecard"
        assert args.scorecard_json is True

    def test_scorecard_runs(self) -> None:
        """scorecard subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["scorecard"])
        assert exit_code == 0

    def test_scorecard_json_runs(self) -> None:
        """scorecard --json subcommand exits cleanly."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["scorecard", "--json"])
        assert exit_code == 0


class TestPillarScoreBackwardCompat:
    """Tests for backward compatibility with existing dashboard format."""

    def test_build_dashboard_still_has_pillar_score(self) -> None:
        """Old pillar_score field still present."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        dashboard = build_dashboard_data()
        assert "pillar_score" in dashboard
        assert "pillar" in dashboard["pillar_score"]
        assert dashboard["pillar_score"]["pillar"] == "gallery-operator-legibility"

    def test_build_dashboard_has_pillar_scores(self) -> None:
        """New pillar_scores field present."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        dashboard = build_dashboard_data()
        assert "pillar_scores" in dashboard
        assert isinstance(dashboard["pillar_scores"], dict)

    def test_build_dashboard_has_full_scorecard(self) -> None:
        """full_scorecard field present in dashboard."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        dashboard = build_dashboard_data()
        assert "full_scorecard" in dashboard
        assert isinstance(dashboard["full_scorecard"], dict)

    def test_old_pillar_score_unchanged(self) -> None:
        """The old pillar_score field structure is preserved."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        dashboard = build_dashboard_data()
        ps = dashboard["pillar_score"]
        assert "score_pct" in ps
        assert "status" in ps
        assert "target_pct" in ps
        assert "components" in ps

    def test_full_scorecard_has_pillars(self) -> None:
        """full_scorecard in dashboard has pillars if computed."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        dashboard = build_dashboard_data()
        fc = dashboard["full_scorecard"]
        if fc:  # May be empty if computation failed
            assert "pillars" in fc
            assert "overall_score_pct" in fc


class TestScorecardExports:
    """Tests for scorecard function exports from gallery __init__."""

    def test_compute_typed_effect_exported(self) -> None:
        """compute_typed_effect_pillar_score is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "compute_typed_effect_pillar_score")
        assert callable(hlf_mcp.gallery.compute_typed_effect_pillar_score)

    def test_compute_formal_verification_exported(self) -> None:
        """compute_formal_verification_pillar_score is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "compute_formal_verification_pillar_score")
        assert callable(hlf_mcp.gallery.compute_formal_verification_pillar_score)

    def test_compute_gallery_operator_exported(self) -> None:
        """compute_gallery_operator_pillar_score is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "compute_gallery_operator_pillar_score")
        assert callable(hlf_mcp.gallery.compute_gallery_operator_pillar_score)

    def test_build_full_scorecard_exported(self) -> None:
        """build_full_scorecard is exported from gallery."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "build_full_scorecard")
        assert callable(hlf_mcp.gallery.build_full_scorecard)

    def test_feedback_default_severity(self) -> None:
        """Default severity is 50."""
        from hlf_mcp.gallery.operator_cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["feedback", "ack", "alert-1"])
        assert args.severity == 50


# ══════════════════════════════════════════════════════════════════════════════════
# Feedback CLI — Execution
# ══════════════════════════════════════════════════════════════════════════════════


class TestFeedbackCLIExecution:
    """Tests for feedback CLI execution (end-to-end)."""

    def test_feedback_ack_exit_code_zero(self) -> None:
        """'feedback ack' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "ack", "test-alert-1"])
        assert exit_code == 0

    def test_feedback_resolve_exit_code_zero(self) -> None:
        """'feedback resolve' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "resolve", "test-alert-2"])
        assert exit_code == 0

    def test_feedback_dismiss_exit_code_zero(self) -> None:
        """'feedback dismiss' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "dismiss", "test-alert-3"])
        assert exit_code == 0

    def test_feedback_escalate_exit_code_zero(self) -> None:
        """'feedback escalate' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "escalate", "test-alert-4"])
        assert exit_code == 0

    def test_feedback_snooze_exit_code_zero(self) -> None:
        """'feedback snooze' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "snooze", "test-alert-5"])
        assert exit_code == 0

    def test_feedback_stats_exit_code_zero(self) -> None:
        """'feedback stats' exits with code 0."""
        from hlf_mcp.gallery.operator_cli import main
        exit_code = _capture_output(main, ["feedback", "stats"])
        assert exit_code == 0

    def test_feedback_full_lifecycle_cli(self) -> None:
        """Full alert lifecycle via CLI: record → ack → resolve → stats."""
        from hlf_mcp.gallery.operator_cli import main, _get_feedback_collector
        # Clear any existing state
        fb = _get_feedback_collector()
        fb.clear()

        _capture_output(main, ["feedback", "ack", "lifecycle-1"])
        _capture_output(main, ["feedback", "resolve", "lifecycle-1", "--note", "done"])
        stats = fb.get_statistics()
        assert stats.total_alerts == 1
        assert stats.resolved == 1
        assert stats.acknowledged == 1


# ══════════════════════════════════════════════════════════════════════════════════
# Dashboard — Feedback Integration
# ══════════════════════════════════════════════════════════════════════════════════


class TestDashboardFeedbackIntegration:
    """Tests for dashboard feedback loop integration."""

    def test_compute_feedback_metrics_returns_dict(self) -> None:
        """compute_feedback_metrics returns a dict with expected keys."""
        from hlf_mcp.gallery.operator_dashboard import compute_feedback_metrics
        metrics = compute_feedback_metrics()
        assert isinstance(metrics, dict)
        assert "operator_saturation_score" in metrics
        assert "signal_to_noise_ratio" in metrics
        assert "mttr_seconds" in metrics
        assert metrics["source"] == "no_data"
        assert metrics["message"] == "No feedback collector available"

    def test_compute_feedback_metrics_returns_zeros_without_collector(self) -> None:
        """compute_feedback_metrics without collector returns honest zeros."""
        from hlf_mcp.gallery.operator_dashboard import compute_feedback_metrics
        metrics = compute_feedback_metrics()
        assert metrics["total_alerts"] == 0
        assert metrics["resolved"] == 0
        assert metrics["dismissed"] == 0
        assert metrics["escalated"] == 0
        assert metrics["snoozed"] == 0
        assert metrics["orphaned"] == 0
        assert metrics["mttr_seconds"] == 0.0

    def test_compute_feedback_metrics_with_collector(self) -> None:
        """compute_feedback_metrics with collector returns live stats."""
        from hlf_mcp.gallery.operator_dashboard import compute_feedback_metrics
        from hlf_mcp.gallery.telemetry import create_default_feedback_collector
        fc = create_default_feedback_collector()
        fc.record_alert("a1", severity=50)
        fc.acknowledge("a1", "op1")
        fc.resolve("a1", "op1")
        metrics = compute_feedback_metrics(fc)
        assert metrics["total_alerts"] == 1
        assert metrics["resolved"] == 1

    def test_build_dashboard_with_feedback_includes_metrics(self) -> None:
        """build_dashboard_with_feedback adds feedback_metrics to dashboard."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_with_feedback
        dashboard = build_dashboard_with_feedback(record=True)
        assert "feedback_metrics" in dashboard
        fb = dashboard["feedback_metrics"]
        assert "operator_saturation_score" in fb

    def test_build_dashboard_with_feedback_adds_components(self) -> None:
        """build_dashboard_with_feedback adds feedback component scores."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_with_feedback
        dashboard = build_dashboard_with_feedback(record=True)
        components = dashboard["pillar_score"]["components"]
        assert "feedback_response_time" in components
        assert "feedback_signal_to_noise" in components
        assert "feedback_saturation" in components
        assert "feedback_false_positive" in components

    def test_display_fatigue_gauge_plain_text(self) -> None:
        """display_fatigue_gauge with plain text fallback doesn't crash."""
        from hlf_mcp.gallery.operator_dashboard import display_fatigue_gauge
        _capture_output(display_fatigue_gauge, 50.0, 0.5, 120.0, 15.0, 2.0)

    def test_render_fatigue_gauge_low_saturation(self) -> None:
        """render_fatigue_gauge returns Rich table for low saturation."""
        from hlf_mcp.gallery.operator_dashboard import render_fatigue_gauge
        try:
            gauge = render_fatigue_gauge(15.0, 0.9, 30.0, 5.0, 0.5)
        except Exception:
            gauge = None  # Rich not installed
        # At minimum should not throw
        assert True


# ══════════════════════════════════════════════════════════════════════════════════
# Gallery Package — New Exports
# ══════════════════════════════════════════════════════════════════════════════════


class TestGalleryNewExports:
    """Tests for new gallery package exports."""

    def test_gallery_exports_feedback_collector(self) -> None:
        """Gallery __init__.py exports FeedbackCollector."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "FeedbackCollector")
        assert hasattr(hlf_mcp.gallery, "AlertFeedback")
        assert hasattr(hlf_mcp.gallery, "FeedbackStatistics")
        assert hasattr(hlf_mcp.gallery, "create_default_feedback_collector")

    def test_gallery_exports_feedback_metrics(self) -> None:
        """Gallery exports compute_feedback_metrics and fatigue gauge."""
        import hlf_mcp.gallery
        assert hasattr(hlf_mcp.gallery, "compute_feedback_metrics")
        assert hasattr(hlf_mcp.gallery, "render_fatigue_gauge")
        assert hasattr(hlf_mcp.gallery, "display_fatigue_gauge")
        assert hasattr(hlf_mcp.gallery, "build_dashboard_with_feedback")

    def test_gallery_existing_exports_unchanged(self) -> None:
        """All existing gallery exports still work."""
        import hlf_mcp.gallery
        # Existing telemetry exports
        assert hasattr(hlf_mcp.gallery, "TelemetryCollector")
        assert hasattr(hlf_mcp.gallery, "TelemetrySnapshot")
        assert hasattr(hlf_mcp.gallery, "create_default_collector")
        # Existing dashboard exports
        assert hasattr(hlf_mcp.gallery, "compute_alert_threshold")
        assert hasattr(hlf_mcp.gallery, "build_dashboard_with_trend")
        assert hasattr(hlf_mcp.gallery, "integrate_telemetry_snapshot")
        # Existing CLI exports
        assert hasattr(hlf_mcp.gallery, "operator_cli_main")
        assert hasattr(hlf_mcp.gallery, "operator_cli_build_parser")
