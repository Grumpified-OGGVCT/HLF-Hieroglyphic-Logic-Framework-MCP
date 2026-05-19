"""
tests/test_operator_dashboard.py — Verify operator dashboard generation and JSON output.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
from pathlib import Path

import pytest


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _capture_output(func):
    """Capture stdout/stderr from a function call."""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        func()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# ── Dashboard Import and Demo ───────────────────────────────────────────────────

def test_operator_dashboard_import() -> None:
    """Operator dashboard module is importable."""
    from hlf_mcp.gallery.operator_dashboard import (
        demo,
        build_dashboard_data,
        display_dashboard,
        generate_dashboard_json,
        collect_swarm_state,
        collect_verification_decisions,
        collect_constitutional_violations,
        collect_manifest_audit_trail,
    )
    assert callable(demo)
    assert callable(build_dashboard_data)
    assert callable(display_dashboard)
    assert callable(generate_dashboard_json)
    assert callable(collect_swarm_state)
    assert callable(collect_verification_decisions)
    assert callable(collect_constitutional_violations)
    assert callable(collect_manifest_audit_trail)


def test_operator_dashboard_demo_runs() -> None:
    """Operator dashboard demo() runs without raising."""
    from hlf_mcp.gallery.operator_dashboard import demo
    _capture_output(demo)


# ── Dashboard Data Structure ────────────────────────────────────────────────────

def test_build_dashboard_data_structure() -> None:
    """Dashboard data has all expected top-level keys."""
    from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
    data = build_dashboard_data()

    # Top-level keys
    assert "dashboard_id" in data
    assert "generated_at" in data
    assert "overall_status" in data
    assert "pillar_score" in data
    assert "swarm" in data
    assert "verification" in data
    assert "constitutional" in data
    assert "manifest_audit" in data

    # Overall status is valid
    assert data["overall_status"] in ("healthy", "degraded", "critical")

    # Dashboard ID is a hex string
    assert isinstance(data["dashboard_id"], str)
    assert len(data["dashboard_id"]) == 16


def test_pillar_score_structure() -> None:
    """Pillar score has expected fields."""
    from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
    data = build_dashboard_data()
    pillar = data["pillar_score"]

    assert pillar["pillar"] == "gallery-operator-legibility"
    assert isinstance(pillar["score_pct"], (int, float))
    assert isinstance(pillar["target_pct"], (int, float))
    assert pillar["status"] == "bridge-active"

    # Components
    components = pillar.get("components", {})
    expected_components = [
        "type_explorer",
        "verification_viewer",
        "manifest_viewer",
        "provenance_viewer",
        "operator_dashboard",
    ]
    for comp in expected_components:
        assert comp in components
        assert "status" in components[comp]
        assert "score_pct" in components[comp]
        assert components[comp]["status"] == "implemented"


def test_swarm_state_structure() -> None:
    """Swarm state has expected fields."""
    from hlf_mcp.gallery.operator_dashboard import collect_swarm_state
    swarm = collect_swarm_state()

    assert "source" in swarm
    assert "total_events" in swarm
    assert swarm["total_events"] > 0
    assert "recent_events" in swarm
    assert "active_agents" in swarm

    # Each recent event has required fields
    for event in swarm["recent_events"]:
        assert "event_type" in event
        assert event["event_type"] in ("started", "progress", "complete", "error", "cancelled")


def test_verification_decisions_structure() -> None:
    """Verification decisions have expected fields."""
    from hlf_mcp.gallery.operator_dashboard import collect_verification_decisions
    ver = collect_verification_decisions()

    assert "source" in ver
    assert "decisions" in ver
    assert "summary" in ver
    assert len(ver["decisions"]) > 0

    summary = ver["summary"]
    assert "total_programs" in summary
    assert "proceed" in summary
    assert "warn" in summary
    assert "block" in summary
    assert "pass_rate_pct" in summary

    for d in ver["decisions"]:
        assert d["decision"] in ("PROCEED", "WARN", "BLOCK")
        assert d["checks_passed"] <= d["checks_total"]


def test_constitutional_violations_structure() -> None:
    """Constitutional violations have expected fields."""
    from hlf_mcp.gallery.operator_dashboard import collect_constitutional_violations
    const = collect_constitutional_violations()

    assert "source" in const
    assert "violations" in const
    assert "summary" in const

    summary = const["summary"]
    assert "total_violations" in summary
    assert "blocked_count" in summary

    for v in const["violations"]:
        assert "rule_id" in v
        assert "rule_name" in v
        assert "severity" in v
        assert v["severity"] in ("high", "medium", "low")


def test_manifest_audit_trail_structure() -> None:
    """Manifest audit trail has expected fields."""
    from hlf_mcp.gallery.operator_dashboard import collect_manifest_audit_trail
    man = collect_manifest_audit_trail()

    assert "source" in man
    assert "deployments" in man
    assert "summary" in man

    summary = man["summary"]
    assert "total_deployments" in summary
    assert "approved" in summary
    assert "rejected" in summary
    assert "approval_rate_pct" in summary

    for d in man["deployments"]:
        assert "program" in d
        assert "tier" in d
        assert "capabilities" in d
        assert "approved" in d
        assert isinstance(d["approved"], bool)


# ── JSON Generation ─────────────────────────────────────────────────────────────

def test_generate_dashboard_json_returns_valid_json() -> None:
    """generate_dashboard_json() returns valid JSON string."""
    from hlf_mcp.gallery.operator_dashboard import generate_dashboard_json

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test-dashboard.json"
        json_str = generate_dashboard_json(str(output_path))

        # Returns a string
        assert isinstance(json_str, str)
        assert len(json_str) > 100

        # Parsable as JSON
        data = json.loads(json_str)
        assert "dashboard_id" in data

        # File was written
        assert output_path.exists()
        file_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert file_data == data


def test_generate_dashboard_json_default_path() -> None:
    """generate_dashboard_json() writes to docs/hlf-dashboard-data.json by default."""
    from hlf_mcp.gallery.operator_dashboard import generate_dashboard_json

    json_str = generate_dashboard_json()
    data = json.loads(json_str)
    assert "dashboard_id" in data
    assert "pillar_score" in data

    # Verify the file exists at the default path
    default_path = Path(__file__).resolve().parent.parent / "docs" / "hlf-dashboard-data.json"
    assert default_path.exists(), f"Expected {default_path} to exist"
    file_data = json.loads(default_path.read_text(encoding="utf-8"))
    assert file_data["dashboard_id"] == data["dashboard_id"]


# ── Dashboard JSON is consumed by GitHub Pages ──────────────────────────────────

def test_dashboard_json_is_valid_for_status_page() -> None:
    """The generated dashboard JSON is valid for the GitHub Pages status page."""
    from hlf_mcp.gallery.operator_dashboard import build_dashboard_data

    data = build_dashboard_data()
    json_str = json.dumps(data, indent=2, ensure_ascii=False)

    # Verify JSON is valid
    parsed = json.loads(json_str)
    assert parsed == data

    # Verify the dashboard contains all sections the status page references
    assert "swarm" in parsed
    assert "verification" in parsed
    assert "constitutional" in parsed
    assert "manifest_audit" in parsed
    assert "pillar_score" in parsed
    assert "overall_status" in parsed

    # Verify pillar score matches the expected gallery pillar
    pillar = parsed["pillar_score"]
    assert pillar["pillar"] == "gallery-operator-legibility"


# ── Edge Cases ──────────────────────────────────────────────────────────────────

def test_collect_swarm_state_with_none_observer() -> None:
    """collect_swarm_state with None returns simulated data."""
    from hlf_mcp.gallery.operator_dashboard import collect_swarm_state
    swarm = collect_swarm_state(None)
    assert swarm["source"] == "simulated"
    assert swarm["total_events"] > 0


def test_build_dashboard_data_with_none_observer() -> None:
    """build_dashboard_data with None observer works."""
    from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
    data = build_dashboard_data(None)
    assert data["swarm"]["source"] == "simulated"
    assert data["overall_status"] in ("healthy", "degraded", "critical")
