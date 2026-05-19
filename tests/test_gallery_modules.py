"""
tests/test_gallery_modules.py — Verify each gallery module's demo() runs without error.

Tests that all four gallery legibility surfaces are importable and produce output.
"""

from __future__ import annotations

import io
import sys
import pytest


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


# ── Type Explorer ────────────────────────────────────────────────────────────────

def test_type_explorer_import() -> None:
    """Type explorer module is importable."""
    from hlf_mcp.gallery.type_explorer import demo, SAMPLE_PROGRAMS
    assert callable(demo)
    assert isinstance(SAMPLE_PROGRAMS, dict)
    assert len(SAMPLE_PROGRAMS) >= 4


def test_type_explorer_demo_runs() -> None:
    """Type explorer demo() runs without raising."""
    from hlf_mcp.gallery.type_explorer import demo
    _capture_output(demo)


# ── Verification Viewer ──────────────────────────────────────────────────────────

def test_verification_viewer_import() -> None:
    """Verification viewer module is importable."""
    from hlf_mcp.gallery.verification_viewer import demo, build_sample_report, display_verification_report
    assert callable(demo)
    assert callable(build_sample_report)
    assert callable(display_verification_report)


def test_verification_viewer_demo_runs() -> None:
    """Verification viewer demo() runs without raising."""
    from hlf_mcp.gallery.verification_viewer import demo
    _capture_output(demo)


def test_verification_viewer_report_structure() -> None:
    """Sample report has expected structure."""
    from hlf_mcp.gallery.verification_viewer import build_sample_report
    report = build_sample_report()
    assert "results" in report
    assert isinstance(report["results"], list)
    assert len(report["results"]) >= 3
    # Check status distribution
    statuses = [r["status"] for r in report["results"]]
    assert "PROVEN" in statuses
    assert "COUNTEREXAMPLE" in statuses


# ── Manifest Viewer ─────────────────────────────────────────────────────────────

def test_manifest_viewer_import() -> None:
    """Manifest viewer module is importable."""
    from hlf_mcp.gallery.manifest_viewer import demo, build_sample_manifest, display_manifest
    assert callable(demo)
    assert callable(build_sample_manifest)
    assert callable(display_manifest)


def test_manifest_viewer_demo_runs() -> None:
    """Manifest viewer demo() runs without raising."""
    from hlf_mcp.gallery.manifest_viewer import demo
    _capture_output(demo)


def test_manifest_viewer_structure() -> None:
    """Sample manifest has expected structure."""
    from hlf_mcp.gallery.manifest_viewer import build_sample_manifest
    manifest = build_sample_manifest()
    assert "program_id" in manifest
    assert "effects" in manifest
    assert "required_capabilities" in manifest
    assert "input_contracts" in manifest
    assert "output_contracts" in manifest
    assert "trust_tier" in manifest
    assert manifest["trust_tier"] == "hearth"
    assert len(manifest["effects"]) >= 2


# ── Provenance Viewer ───────────────────────────────────────────────────────────

def test_provenance_viewer_import() -> None:
    """Provenance viewer module is importable."""
    from hlf_mcp.gallery.provenance_viewer import demo, build_sample_provenance, display_provenance
    assert callable(demo)
    assert callable(build_sample_provenance)
    assert callable(display_provenance)


def test_provenance_viewer_demo_runs() -> None:
    """Provenance viewer demo() runs without raising."""
    from hlf_mcp.gallery.provenance_viewer import demo
    _capture_output(demo)


def test_provenance_viewer_structure() -> None:
    """Sample provenance data has expected structure."""
    from hlf_mcp.gallery.provenance_viewer import build_sample_provenance
    prov = build_sample_provenance()
    assert "provenance" in prov
    assert "execution_result" in prov
    assert "channel" in prov
    assert prov["channel"] == "data"
    chains = prov["provenance"]
    assert len(chains) >= 3
    # Each chain has required fields
    for item_id, chain in chains.items():
        assert "source" in chain
        assert "path" in chain
        assert "trust" in chain
        assert isinstance(chain["trust"], (int, float))
        assert 0 <= chain["trust"] <= 1


# ── Gallery Package ─────────────────────────────────────────────────────────────

def test_gallery_package_imports() -> None:
    """Gallery package exports expected names."""
    import hlf_mcp.gallery
    assert hasattr(hlf_mcp.gallery, "run_type_explorer_demo")
    assert hasattr(hlf_mcp.gallery, "run_verification_viewer_demo")
    assert hasattr(hlf_mcp.gallery, "run_manifest_viewer_demo")
    assert hasattr(hlf_mcp.gallery, "run_provenance_viewer_demo")
    assert hasattr(hlf_mcp.gallery, "run_operator_dashboard_demo")
    assert hasattr(hlf_mcp.gallery, "generate_dashboard_json")
    assert callable(hlf_mcp.gallery.run_type_explorer_demo)
