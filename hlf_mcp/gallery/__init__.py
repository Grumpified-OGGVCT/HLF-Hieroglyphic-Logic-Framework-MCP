"""
HLF Gallery — Operator Legibility Surfaces.

Provides live demonstrations, verification visualizations, manifest displays,
provenance chain views, and an operator dashboard.

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
]

from hlf_mcp.gallery.type_explorer import demo as run_type_explorer_demo
from hlf_mcp.gallery.verification_viewer import demo as run_verification_viewer_demo
from hlf_mcp.gallery.manifest_viewer import demo as run_manifest_viewer_demo
from hlf_mcp.gallery.provenance_viewer import demo as run_provenance_viewer_demo
from hlf_mcp.gallery.operator_dashboard import demo as run_operator_dashboard_demo
from hlf_mcp.gallery.operator_dashboard import generate_dashboard_json
