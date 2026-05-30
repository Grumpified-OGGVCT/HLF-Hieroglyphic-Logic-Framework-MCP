"""
HLF Verification Viewer — Displays verification reports with pass/fail/block visualization.

Shows formal verification results as color-coded pass/fail/block summaries.
Operators use this surface to inspect the correctness guarantees of compiled programs.

Usage:
    python -m hlf_mcp.gallery.verification_viewer
"""

from __future__ import annotations

import sys
import time
from typing import Any

# ── Windows console encoding fix ────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False


def build_sample_report() -> dict[str, Any]:
    """Build a sample verification report for demonstration."""
    return {
        "report_id": "sample-001",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "program": "hello_world.hlf",
        "compiled_version": "v3",
        "trust_tier": "hearth",
        "results": [
            {"property": "type_invariant_main", "status": "PROVEN", "kind": "TYPE_INVARIANT",
             "message": "All type constraints verified", "duration_ms": 2.3},
            {"property": "range_check_input", "status": "PROVEN", "kind": "RANGE_CHECK",
             "message": "Input bounds satisfied", "duration_ms": 1.1},
            {"property": "null_safety_ret", "status": "PROVEN", "kind": "NULL_SAFETY",
             "message": "Return value is non-null", "duration_ms": 0.8},
            {"property": "gas_bound_main", "status": "PROVEN", "kind": "GAS_BOUND",
             "message": "Gas estimate 42 within budget 10000", "duration_ms": 0.5},
            {"property": "reachability_exit", "status": "RUNTIME_CHECKED", "kind": "REACHABILITY",
             "message": "All paths reach exit; verified at runtime", "duration_ms": 3.7},
            {"property": "spec_gate_output", "status": "COUNTEREXAMPLE", "kind": "SPEC_GATE",
             "message": "Output contract violation: expected int, got string",
             "counterexample": {"input": {"x": 0}, "output": "zero"}, "duration_ms": 5.2},
            {"property": "align_invariant", "status": "SKIPPED", "kind": "CUSTOM",
             "message": "ALIGN ledger not configured for this tier", "duration_ms": 0.0},
        ],
    }


def _status_to_color(status: str) -> str:
    """Map verification status to display color."""
    return {
        "PROVEN": "green",
        "RUNTIME_CHECKED": "yellow",
        "COUNTEREXAMPLE": "red",
        "UNKNOWN": "grey50",
        "SKIPPED": "grey50",
        "ERROR": "red",
    }.get(status, "white")


def _status_to_icon(status: str) -> str:
    """Map verification status to a display icon."""
    return {
        "PROVEN": "✓",
        "RUNTIME_CHECKED": "~",
        "COUNTEREXAMPLE": "✗",
        "UNKNOWN": "?",
        "SKIPPED": "·",
        "ERROR": "!",
    }.get(status, "?")


def display_verification_report(report_data: dict[str, Any]) -> None:
    """Display a verification report with rich formatting.

    Args:
        report_data: Dictionary with 'results' list of verification result dicts.
    """
    results = report_data.get("results", [])
    proven = sum(1 for r in results if r["status"] == "PROVEN")
    runtime = sum(1 for r in results if r["status"] == "RUNTIME_CHECKED")
    failed = sum(1 for r in results if r["status"] in ("COUNTEREXAMPLE", "ERROR"))
    skipped = sum(1 for r in results if r["status"] in ("UNKNOWN", "SKIPPED"))
    total = len(results)

    if _RICH:
        console = Console()

        # ── Header ───────────────────────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]HLF Verification Report[/bold cyan]")
        console.print(f"  Program: [bold]{report_data.get('program', '?')}[/bold]")
        console.print(f"  Tier: [magenta]{report_data.get('trust_tier', '?')}[/magenta]")
        console.print(f"  Generated: [dim]{report_data.get('generated_at', '?')}[/dim]")
        console.print()

        # ── Summary bar ──────────────────────────────────────────────────────
        bar_width = 60
        proven_pct = proven / max(total, 1)
        runtime_pct = runtime / max(total, 1)
        failed_pct = failed / max(total, 1)
        skipped_pct = skipped / max(total, 1)

        summary_text = Text()
        summary_text.append("█" * int(proven_pct * bar_width), style="green")
        summary_text.append("█" * int(runtime_pct * bar_width), style="yellow")
        summary_text.append("█" * int(failed_pct * bar_width), style="red")
        summary_text.append("█" * int(skipped_pct * bar_width), style="grey50")
        summary_text.append(f"  {proven}/{total} proven")
        console.print(Panel(summary_text, title="Coverage", border_style="blue"))

        # ── Detailed table ───────────────────────────────────────────────────
        table = Table(title="Verification Details", box=box.ROUNDED, show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Property", style="cyan")
        table.add_column("Status", width=20)
        table.add_column("Kind", style="magenta", width=20)
        table.add_column("Message")
        table.add_column("Time", style="dim", justify="right", width=8)

        for i, r in enumerate(results, 1):
            status = r["status"]
            color = _status_to_color(status)
            icon = _status_to_icon(status)
            table.add_row(
                str(i),
                r.get("property", "?"),
                f"[{color}]{icon} {status}[/{color}]",
                r.get("kind", "-"),
                r.get("message", "")[:80],
                f"{r.get('duration_ms', 0):.1f}ms",
            )

        console.print(table)

        # ── Counterexamples ──────────────────────────────────────────────────
        counterexamples = [r for r in results if r.get("counterexample")]
        if counterexamples:
            console.print()
            for ce in counterexamples:
                import json as _json
                ce_text = _json.dumps(ce["counterexample"], indent=2)
                console.print(Panel(
                    ce_text,
                    title=f"[red]Counterexample: {ce['property']}[/red]",
                    border_style="red",
                ))

        # ── Gate Decision ────────────────────────────────────────────────────
        if failed > 0:
            gate_color = "red"
            gate_decision = "BLOCK"
            gate_reason = f"{failed} verification failure(s)"
        elif runtime > 0:
            gate_color = "yellow"
            gate_decision = "WARN"
            gate_reason = f"{runtime} runtime-checked, 0 proven-failures"
        else:
            gate_color = "green"
            gate_decision = "PROCEED"
            gate_reason = "All properties proven"

        console.print()
        console.print(Panel(
            f"[bold {gate_color}]{gate_decision}[/bold {gate_color}] — {gate_reason}",
            title="Gate Decision",
            border_style=gate_color,
        ))

    else:
        # ── Plain text fallback ──────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  HLF Verification Report — {report_data.get('program', '?')}")
        print(f"  Tier: {report_data.get('trust_tier', '?')}")
        print(f"{'='*70}")
        print(f"\n  Coverage: {'█' * int(proven / max(total, 1) * 40)}{'░' * (40 - int(proven / max(total, 1) * 40))}")
        print(f"  {proven} proven, {runtime} checked, {failed} failed, {skipped} skipped")
        print(f"\n  {'#':<3} {'Property':<30} {'Status':<20} {'Kind':<20} {'Time':>8}")
        print(f"  {'-'*3} {'-'*30} {'-'*20} {'-'*20} {'-'*8}")
        for i, r in enumerate(results, 1):
            icon = _status_to_icon(r["status"])
            print(f"  {i:<3} {r.get('property', '?')[:30]:<30} {icon} {r['status']:<17} {r.get('kind', '-'):<20} {r.get('duration_ms', 0):>6.1f}ms")

        for ce in [r for r in results if r.get("counterexample")]:
            import json as _json
            print(f"\n  Counterexample: {ce['property']}")
            print(f"  {_json.dumps(ce['counterexample'], indent=4)}")

        if failed > 0:
            print(f"\n  Gate Decision: [BLOCK] — {failed} verification failure(s)")
        elif runtime > 0:
            print(f"\n  Gate Decision: [WARN] — {runtime} runtime-checked")
        else:
            print(f"\n  Gate Decision: [PROCEED] — All properties proven")


def _build_live_verification_report(ctx: object) -> dict[str, Any]:
    """Build verification report from live governance events."""
    events: list[dict[str, Any]] = []
    try:
        if hasattr(ctx, "recent_governance_events"):
            events = ctx.recent_governance_events(limit=50, kind="formal_verification")
    except Exception:
        pass

    results: list[dict[str, Any]] = []
    for evt in events:
        verdict = str(evt.get("verdict", "")).lower()
        status = "PROVEN" if verdict == "passed" else "COUNTEREXAMPLE" if verdict in ("failed", "blocked") else "RUNTIME_CHECKED"
        results.append({
            "property": str(evt.get("subject_id") or evt.get("event_id", "unknown"))[:48],
            "status": status,
            "kind": "FORMAL_VERIFICATION",
            "message": str(evt.get("summary") or evt.get("details", {}).get("message", "") or "Governance verification event"),
            "duration_ms": float(evt.get("duration_ms", 0.0)),
        })

    return {
        "report_id": f"live-{len(events)}-events",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "program": "live_verification_surface",
        "compiled_version": "v3",
        "trust_tier": "hearth",
        "results": results,
        "source": "live",
    }


def live(ctx: object) -> dict[str, Any]:
    """Return live verification data from governance events (no demo fallback).

    Args:
        ctx: ServerContext with recent_governance_events() method.

    Returns:
        Report dict suitable for display_verification_report(), with ``source`` = ``"live"``.
    """
    return _build_live_verification_report(ctx)


def demo(ctx: object | None = None) -> None:
    """Run the verification viewer demonstration.

    When *ctx* is a ServerContext, queries live governance events for
    formal verification results.
    When *ctx* is None (backward compatible), uses hardcoded sample data
    tagged with ``"source": "demo"``.

    Args:
        ctx: Optional ServerContext for live verification queries.
    """
    if ctx is not None:
        try:
            report = _build_live_verification_report(ctx)
            if report.get("results"):
                display_verification_report(report)
                return
        except Exception:
            pass
    report = build_sample_report()
    report["source"] = "demo"
    display_verification_report(report)


if __name__ == "__main__":
    try:
        from hlf_mcp.server_context import build_server_context
        ctx = build_server_context()
    except Exception:
        ctx = None
    demo(ctx)
