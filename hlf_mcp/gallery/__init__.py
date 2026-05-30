"""
HLF Gallery — Operator Legibility Surfaces.

Provides live demonstrations, verification visualizations, manifest displays,
provenance chain views, an operator dashboard, live telemetry, and an operator CLI.

The gallery surfaces expose the internal proof structures of the HLF stack
so that operators, auditors, and developers can inspect compiled programs
through multiple legibility lenses.
"""

from __future__ import annotations

__all__ = [
    "run_type_explorer_demo",
    "run_verification_viewer_demo",
    "run_manifest_viewer_demo",
    "run_provenance_viewer_demo",
    "run_operator_dashboard_demo",
    "generate_dashboard_json",
    "build_dashboard_data_live",
    "TelemetryCollector",
    "TelemetrySnapshot",
    "create_default_collector",
    "FeedbackCollector",
    "AlertFeedback",
    "FeedbackStatistics",
    "create_default_feedback_collector",
    "EvidenceSummaryRenderer",
    "compute_alert_threshold",
    "compute_alert_color",
    "compute_pillar_alerts",
    "get_trend_history",
    "clear_trend_history",
    "record_trend_snapshot",
    "build_dashboard_with_trend",
    "build_dashboard_with_feedback",
    "integrate_telemetry_snapshot",
    "display_dashboard_with_alerts",
    "compute_feedback_metrics",
    "render_fatigue_gauge",
    "display_fatigue_gauge",
    "render_mission_panel",
    "display_mission_panel",
    "render_dream_findings_panel",
    "display_dream_findings_panel",
    "render_evidence_panel",
    "display_evidence_panel",
    "export_evidence_report",
    "operator_cli_main",
    "operator_cli_build_parser",
    "compute_typed_effect_pillar_score",
    "compute_formal_verification_pillar_score",
    "compute_gallery_operator_pillar_score",
    "build_full_scorecard",
]

from hlf_mcp.gallery.type_explorer import demo as run_type_explorer_demo
from hlf_mcp.gallery.verification_viewer import demo as run_verification_viewer_demo
from hlf_mcp.gallery.manifest_viewer import demo as run_manifest_viewer_demo
from hlf_mcp.gallery.provenance_viewer import demo as run_provenance_viewer_demo
from hlf_mcp.gallery.operator_dashboard import demo as run_operator_dashboard_demo
from hlf_mcp.gallery.operator_dashboard import generate_dashboard_json
from hlf_mcp.gallery.operator_dashboard import build_dashboard_data_live
from hlf_mcp.gallery.operator_dashboard import (
    compute_alert_threshold,
    compute_alert_color,
    compute_pillar_alerts,
    get_trend_history,
    clear_trend_history,
    record_trend_snapshot,
    build_dashboard_with_trend,
    build_dashboard_with_feedback,
    integrate_telemetry_snapshot,
    display_dashboard_with_alerts,
    compute_feedback_metrics,
    render_fatigue_gauge,
    display_fatigue_gauge,
    render_mission_panel,
    display_mission_panel,
    render_dream_findings_panel,
    display_dream_findings_panel,
    render_evidence_panel,
    display_evidence_panel,
    export_evidence_report,
    compute_typed_effect_pillar_score,
    compute_formal_verification_pillar_score,
    compute_gallery_operator_pillar_score,
    build_full_scorecard,
)
from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer
from hlf_mcp.gallery.telemetry import (
    TelemetryCollector,
    TelemetrySnapshot,
    FeedbackCollector,
    AlertFeedback,
    FeedbackStatistics,
    create_default_collector,
    create_default_feedback_collector,
)
from hlf_mcp.gallery.operator_cli import main as operator_cli_main
from hlf_mcp.gallery.operator_cli import build_parser as operator_cli_build_parser
