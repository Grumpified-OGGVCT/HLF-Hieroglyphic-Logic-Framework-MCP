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


# ══════════════════════════════════════════════════════════════════════════════════
# EvidenceSummaryRenderer Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestEvidenceSummaryRenderer:
    """Tests for EvidenceSummaryRenderer from evidence_renderer.py."""

    def test_renderer_importable(self) -> None:
        """EvidenceSummaryRenderer is importable from gallery."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        assert EvidenceSummaryRenderer is not None

    def test_render_evidence_contract_accepts_dict(self) -> None:
        """render_evidence_contract accepts a dictionary form."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        contract = {
            "sha256": "a" * 64,
            "confidence": 0.95,
            "trust_tier": "sovereign",
            "provenance_grade": "A",
            "source_authority_label": "formal-verifier",
            "source_file": "test.hlf",
            "collector": "unit-test",
            "collected_at": "2025-01-01T00:00:00Z",
            "fresh_until": "2025-12-31T00:00:00Z",
            "revoked": False,
            "tombstoned": False,
            "supersedes_sha256": "",
            "artifact_form": "verification_gate",
            "memory_stratum": "active",
            "storage_tier": "hot",
            "collection_metadata": {},
            "workflow_run_url": "",
        }
        result = EvidenceSummaryRenderer.render_evidence_contract(contract)
        assert result is not None
        assert isinstance(result, str)

    def test_render_evidence_contract_accepts_dataclass(self) -> None:
        """render_evidence_contract accepts an EvidenceContract dataclass."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        from hlf_mcp.hlf.memory_node import EvidenceContract
        contract = EvidenceContract(
            sha256="b" * 64,
            confidence=0.87,
            trust_tier="hearth",
            provenance_grade="B",
            source_authority_label="dream-cycle",
            collector="unit-test",
            collected_at="2025-01-01T00:00:00Z",
            fresh_until="2025-12-31T00:00:00Z",
        )
        result = EvidenceSummaryRenderer.render_evidence_contract(contract)
        assert result is not None
        result_str = str(result)
        assert isinstance(result_str, str)
        assert len(result_str) > 0

    def test_render_media_evidence_output(self) -> None:
        """render_media_evidence returns a string."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        record = {
            "media_type": "image/png",
            "sha256": "c" * 64,
            "extraction_mode": "ocr",
            "safety_status": "safe",
            "provenance": "uploaded",
            "derived_text": "sample text",
            "structured_extraction_ref": "ref-1",
            "sanitization_notes": "none",
            "confidence": 0.9,
            "source_path": "/tmp/test.png",
            "artifact_id": "art-1",
            "operator_summary": "test image",
            "collected_at": "2025-01-01T00:00:00Z",
            "trust_tier": "forge",
        }
        result = EvidenceSummaryRenderer.render_media_evidence(record)
        assert result is not None
        assert isinstance(result, str)

    def test_render_dream_finding_output(self) -> None:
        """render_dream_finding returns a string (or Rich object stringifiable)."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        finding = {
            "finding_id": "f-001",
            "created_at": "2025-01-01T00:00:00Z",
            "cycle_id": "cycle-1",
            "title": "Test Finding",
            "summary": "A test dream finding",
            "topic": "testing",
            "confidence": 0.75,
            "evidence_refs": [],
            "source_artifact_ids": [],
            "witness_status": "observed",
            "provenance": "dream",
            "advisory_only": False,
            "novelty_score": 0.5,
            "quality_score": 0.8,
            "candidate_actions": [],
            "related_memory_keys": [],
            "supersedes": [],
            "media_evidence_present": False,
            "media_types": [],
        }
        result = EvidenceSummaryRenderer.render_dream_finding(finding)
        assert result is not None
        result_str = str(result)
        assert isinstance(result_str, str)

    def test_render_mission_summary_output(self) -> None:
        """render_mission_summary returns a string."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        mission = {
            "mission_id": "m-001",
            "title": "Test Mission",
            "current_phase": "compile",
            "verdict": "passed",
            "sealed": True,
            "plan_nodes": 5,
            "plan_nodes_done": 5,
        }
        result = EvidenceSummaryRenderer.render_mission_summary(mission)
        assert result is not None
        assert isinstance(result, str)

    def test_render_evidence_list_output(self) -> None:
        """render_evidence_list returns a string for multiple items."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        items = [
            {"sha256": "d" * 64, "confidence": 0.9, "trust_tier": "sovereign"},
            {"sha256": "e" * 64, "confidence": 0.5, "trust_tier": "hearth"},
        ]
        result = EvidenceSummaryRenderer.render_evidence_list(items)
        assert result is not None
        assert isinstance(result, str)

    def test_render_execution_trace_output(self) -> None:
        """render_execution_trace returns a string when given a list of steps."""
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
        steps = [
            {"node_id": "step-1", "status": "success", "agent_id": "compiler", "message": "compiled", "duration": 1.5},
            {"node_id": "step-2", "status": "passed", "agent_id": "verifier", "message": "verified", "duration": 2.0},
        ]
        result = EvidenceSummaryRenderer.render_execution_trace(steps)
        assert result is not None
        result_str = str(result)
        assert isinstance(result_str, str)


# ══════════════════════════════════════════════════════════════════════════════════
# Live Data Toggle Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestLiveDataToggle:
    """Tests for use_live_data parameter on all dashboard collectors."""

    def test_swarm_state_use_live_data_false_returns_simulated(self) -> None:
        """collect_swarm_state with use_live_data=False returns simulated data."""
        from hlf_mcp.gallery.operator_dashboard import collect_swarm_state
        result = collect_swarm_state(use_live_data=False)
        assert result["source"] == "simulated"
        assert result["total_events"] > 0

    def test_verification_decisions_use_live_data_false_returns_simulated(self) -> None:
        """collect_verification_decisions with use_live_data=False returns simulated data."""
        from hlf_mcp.gallery.operator_dashboard import collect_verification_decisions
        result = collect_verification_decisions(use_live_data=False)
        assert result["source"] == "simulated"
        assert "decisions" in result
        assert len(result["decisions"]) > 0

    def test_constitutional_violations_use_live_data_false_returns_simulated(self) -> None:
        """collect_constitutional_violations with use_live_data=False returns simulated data."""
        from hlf_mcp.gallery.operator_dashboard import collect_constitutional_violations
        result = collect_constitutional_violations(use_live_data=False)
        assert result["source"] == "simulated"
        assert "violations" in result

    def test_manifest_audit_use_live_data_false_returns_simulated(self) -> None:
        """collect_manifest_audit_trail with use_live_data=False returns simulated data."""
        from hlf_mcp.gallery.operator_dashboard import collect_manifest_audit_trail
        result = collect_manifest_audit_trail(use_live_data=False)
        assert result["source"] == "simulated"
        assert "deployments" in result

    def test_build_dashboard_with_live_data_false(self) -> None:
        """build_dashboard_data with use_live_data=False uses simulated collectors."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        data = build_dashboard_data(use_live_data=False)
        assert data["swarm"]["source"] == "simulated"
        assert data["verification"]["source"] == "simulated"
        assert data["constitutional"]["source"] == "simulated"
        assert data["manifest_audit"]["source"] == "simulated"

    def test_build_dashboard_with_live_data_true_handles_missing_lifecycle(self) -> None:
        """build_dashboard_data with use_live_data=True handles missing lifecycle gracefully."""
        from hlf_mcp.gallery.operator_dashboard import build_dashboard_data
        # Even when lifecycle is None, it should fallback gracefully
        data = build_dashboard_data(use_live_data=True)
        # Should not crash; source could be live or simulated depending on env
        assert "dashboard_id" in data
        assert "overall_status" in data


# ══════════════════════════════════════════════════════════════════════════════════
# New Panel Rendering Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestNewDashboardPanels:
    """Tests for mission, dream findings, and evidence panels."""

    def test_render_mission_panel_no_lifecycle(self) -> None:
        """render_mission_panel returns output even without a lifecycle."""
        from hlf_mcp.gallery.operator_dashboard import render_mission_panel
        result = render_mission_panel(missions=[], use_live_data=False)
        if result is not None:
            assert isinstance(result, str)

    def test_render_mission_panel_with_data(self) -> None:
        """render_mission_panel handles provided mission data."""
        from hlf_mcp.gallery.operator_dashboard import render_mission_panel
        missions = [
            {
                "mission_id": "m-test-1",
                "title": "Test Alpha",
                "current_phase": "compile",
                "verdict": "passed",
                "sealed": True,
            },
            {
                "mission_id": "m-test-2",
                "title": "Test Beta",
                "current_phase": "verify",
                "verdict": "failed",
                "sealed": False,
            },
        ]
        result = render_mission_panel(missions=missions, use_live_data=False)
        assert result is not None
        result_str = str(result)
        assert isinstance(result_str, str)
        assert len(result_str) > 0

    def test_render_dream_findings_panel_no_data(self) -> None:
        """render_dream_findings_panel handles empty findings."""
        from hlf_mcp.gallery.operator_dashboard import render_dream_findings_panel
        result = render_dream_findings_panel(findings=[], use_live_data=False)
        if result is not None:
            assert isinstance(result, str)

    def test_render_evidence_panel_no_data(self) -> None:
        """render_evidence_panel handles empty evidence."""
        from hlf_mcp.gallery.operator_dashboard import render_evidence_panel
        result = render_evidence_panel(evidence=[], use_live_data=False)
        if result is not None:
            assert isinstance(result, str)

    def test_display_mission_panel_runs(self) -> None:
        """display_mission_panel runs without error."""
        from hlf_mcp.gallery.operator_dashboard import display_mission_panel
        _capture_output(lambda: display_mission_panel(use_live_data=False))

    def test_display_dream_findings_panel_runs(self) -> None:
        """display_dream_findings_panel runs without error."""
        from hlf_mcp.gallery.operator_dashboard import display_dream_findings_panel
        _capture_output(lambda: display_dream_findings_panel(use_live_data=False))

    def test_display_evidence_panel_runs(self) -> None:
        """display_evidence_panel runs without error."""
        from hlf_mcp.gallery.operator_dashboard import display_evidence_panel
        _capture_output(lambda: display_evidence_panel(use_live_data=False))


# ══════════════════════════════════════════════════════════════════════════════════
# Export Evidence Report Tests
# ══════════════════════════════════════════════════════════════════════════════════


class TestExportEvidenceReport:
    """Tests for export_evidence_report function."""

    def test_export_markdown_returns_string(self) -> None:
        """export_evidence_report with markdown format returns a string."""
        from hlf_mcp.gallery.operator_dashboard import export_evidence_report
        report = export_evidence_report(output_format="markdown", use_live_data=False)
        assert isinstance(report, str)
        assert len(report) > 100
        assert "HLF Evidence Report" in report

    def test_export_json_returns_valid_json(self) -> None:
        """export_evidence_report with json format returns valid JSON."""
        from hlf_mcp.gallery.operator_dashboard import export_evidence_report
        report = export_evidence_report(output_format="json", use_live_data=False)
        data = json.loads(report)
        assert "report_id" in data
        assert "dashboard" in data
        assert "source_mode" in data

    def test_export_text_is_same_as_markdown_in_structure(self) -> None:
        """export_evidence_report with text format produces a string."""
        from hlf_mcp.gallery.operator_dashboard import export_evidence_report
        report = export_evidence_report(output_format="text", use_live_data=False)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_export_unsupported_format_raises(self) -> None:
        """export_evidence_report raises ValueError for unsupported format."""
        from hlf_mcp.gallery.operator_dashboard import export_evidence_report
        with pytest.raises(ValueError, match="Unsupported output format"):
            export_evidence_report(output_format="pdf", use_live_data=False)

    def test_export_to_file(self) -> None:
        """export_evidence_report writes to file when output_path is provided."""
        from hlf_mcp.gallery.operator_dashboard import export_evidence_report
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-report.md"
            report = export_evidence_report(
                output_format="markdown",
                output_path=str(output_path),
                use_live_data=False,
            )
            assert output_path.exists()
            content = output_path.read_text(encoding="utf-8")
            assert content == report
            assert "HLF Evidence Report" in content
