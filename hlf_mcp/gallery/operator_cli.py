"""
HLF Gallery Operator CLI — Command-line interface for the operator dashboard.

Provides real-time telemetry monitoring, one-shot snapshots, watch mode,
and structured subcommands for inspecting system state.

Usage:
    python -m hlf_mcp.gallery.operator_cli --dashboard     # Live Rich dashboard
    python -m hlf_mcp.gallery.operator_cli --snapshot      # One-shot JSON snapshot
    python -m hlf_mcp.gallery.operator_cli --watch          # Watch mode (text)
    python -m hlf_mcp.gallery.operator_cli status           # Current status summary
    python -m hlf_mcp.gallery.operator_cli pillars          # Per-pillar scores
    python -m hlf_mcp.gallery.operator_cli violations       # Constitutional violations
    python -m hlf_mcp.gallery.operator_cli audit            # Manifest audit trail
"""

from __future__ import annotations

import argparse
import json
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
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.layout import Layout
    from rich import box
    from rich.progress import Progress, BarColumn, TextColumn
    _RICH = True
except ImportError:
    _RICH = False

from hlf_mcp.gallery.telemetry import (
    TelemetryCollector,
    TelemetrySnapshot,
    create_default_collector,
)
from hlf_mcp.gallery.operator_dashboard import (
    build_dashboard_data,
    display_dashboard,
    generate_dashboard_json,
)


# ── Rich Dashboard Rendering ─────────────────────────────────────────────────────


def _render_live_dashboard(console: Console, collector: TelemetryCollector) -> None:
    """Render a live-updating Rich dashboard from the telemetry collector.

    Args:
        console: Rich Console instance for output.
        collector: A running TelemetryCollector instance.
    """
    def _alert_color(score: float) -> str:
        """Return Rich color tag for a readiness score."""
        if score < 50.0:
            return "red"
        elif score < 65.0:
            return "yellow"
        else:
            return "green"

    def _alert_char(score: float) -> str:
        """Return alert character for a readiness score."""
        if score < 50.0:
            return "🔴"
        elif score < 65.0:
            return "🟡"
        else:
            return "🟢"

    def _generate_layout() -> Layout:
        """Build the live dashboard layout from the latest snapshot."""
        history = collector.history()
        if not history:
            return Layout(Panel("Waiting for telemetry data...", title="HLF Operator Dashboard"))

        snap = history[-1]
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="body"),
            Layout(name="trend", size=8),
        )

        # ── Header ─────────────────────────────────────────────────────────
        readiness = snap.overall_readiness_pct
        color = _alert_color(readiness)
        char = _alert_char(readiness)
        status_text = snap.alert_thresholds.get("overall", "unknown").upper()

        header_panel = Panel(
            f"[bold {color}]{char} Status: {status_text}   "
            f"Readiness: {readiness}%   "
            f"Snapshots: {len(history)}[/bold {color}]",
            title=f"[bold cyan]HLF Operator Dashboard[/bold cyan] — {snap.timestamp}",
            border_style=color,
        )
        layout["header"].update(header_panel)

        # ── Body: split into quadrants ──────────────────────────────────────
        body_layout = Layout()
        body_layout.split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        left_layout = Layout()
        left_layout.split_column(
            Layout(name="swarm"),
            Layout(name="verification"),
        )
        right_layout = Layout()
        right_layout.split_column(
            Layout(name="constitutional"),
            Layout(name="manifest"),
        )

        # Swarm Health
        swarm = snap.swarm_health
        swarm_table = Table(title="Swarm Health", box=box.SIMPLE, expand=True)
        swarm_table.add_column("Metric", style="cyan")
        swarm_table.add_column("Value", style="white")
        swarm_table.add_row("Active Agents", str(swarm.get("active_agents", "?")))
        swarm_table.add_row("Queued Events", str(swarm.get("queued_events", "?")))
        swarm_table.add_row("Healthy Phases", f"[green]{swarm.get('healthy_phases', '?')}[/green]")
        swarm_table.add_row("Degraded Phases", f"[yellow]{swarm.get('degraded_phases', '?')}[/yellow]")
        swarm_table.add_row("Failed Phases", f"[red]{swarm.get('failed_phases', '?')}[/red]")
        swarm_table.add_row("Uptime", f"{swarm.get('uptime_seconds', 0):.0f}s")
        left_layout["swarm"].update(swarm_table)

        # Verification Gate
        ver = snap.verification_gate
        ver_table = Table(title="Verification Gate", box=box.SIMPLE, expand=True)
        ver_table.add_column("Metric", style="cyan")
        ver_table.add_column("Value", style="white")
        ver_table.add_row("Programs Verified", str(ver.get("programs_verified", "?")))
        ver_table.add_row("Passed", f"[green]{ver.get('programs_passed', '?')}[/green]")
        ver_table.add_row("Warned", f"[yellow]{ver.get('programs_warned', '?')}[/yellow]")
        ver_table.add_row("Blocked", f"[red]{ver.get('programs_blocked', '?')}[/red]")
        ver_score = ver.get("pass_rate_pct", 0)
        ver_color = _alert_color(ver_score)
        ver_table.add_row("Pass Rate", f"[{ver_color}]{ver_score}%[/{ver_color}]")
        left_layout["verification"].update(ver_table)

        # Constitutional Violations
        const = snap.constitutional_violations
        const_table = Table(title="Constitutional Violations", box=box.SIMPLE, expand=True)
        const_table.add_column("Metric", style="cyan")
        const_table.add_column("Value", style="white")
        const_table.add_row("Total", str(const.get("total_violations", "?")))
        const_table.add_row("High Severity", f"[red]{const.get('high_severity', '?')}[/red]")
        const_table.add_row("Medium Severity", f"[yellow]{const.get('medium_severity', '?')}[/yellow]")
        const_table.add_row("Low Severity", f"[dim]{const.get('low_severity', '?')}[/dim]")
        const_table.add_row("Blocked Actions", str(const.get("blocked_actions", "?")))
        rules = const.get("rules_breached", [])
        const_table.add_row("Rules Breached", ", ".join(rules) if rules else "[green]None[/green]")
        right_layout["constitutional"].update(const_table)

        # Manifest Audit
        man = snap.manifest_audit
        man_table = Table(title="Manifest Audit", box=box.SIMPLE, expand=True)
        man_table.add_column("Metric", style="cyan")
        man_table.add_column("Value", style="white")
        man_table.add_row("Total Deployments", str(man.get("total_deployments", "?")))
        man_table.add_row("Approved", f"[green]{man.get('approved_deployments', '?')}[/green]")
        man_table.add_row("Rejected", f"[red]{man.get('rejected_deployments', '?')}[/red]")
        man_score = man.get("approval_rate_pct", 0)
        man_color = _alert_color(man_score)
        man_table.add_row("Approval Rate", f"[{man_color}]{man_score}%[/{man_color}]")
        tiers = man.get("tiers", {})
        tiers_str = ", ".join(f"{k}: {v}" for k, v in tiers.items())
        man_table.add_row("Tier Distribution", tiers_str or "N/A")
        right_layout["manifest"].update(man_table)

        body_layout["left"].update(left_layout)
        body_layout["right"].update(right_layout)
        layout["body"].update(body_layout)

        # ── Trend ──────────────────────────────────────────────────────────
        trend_table = Table(title="Readiness Trend (Last 10 Snapshots)", box=box.SIMPLE, expand=True)
        trend_table.add_column("Time", style="dim")
        trend_table.add_column("Readiness", style="white")
        trend_table.add_column("Status", style="white")
        trend_table.add_column("Bar", style="white")

        recent = history[-10:]
        for h in recent:
            ts = h.timestamp.split("T")[1][:8] if "T" in h.timestamp else h.timestamp[:8]
            s = h.overall_readiness_pct
            c = _alert_color(s)
            bar_len = max(1, int(s / 10))
            bar = f"[{c}]{'█' * bar_len}{'░' * (10 - bar_len)}[/{c}]"
            status = h.alert_thresholds.get("overall", "?")
            trend_table.add_row(ts, f"[{c}]{s}%[/{c}]", f"[{c}]{status}[/{c}]", bar)

        layout["trend"].update(trend_table)

        return layout

    with Live(_generate_layout(), console=console, refresh_per_second=2, screen=True) as live:
        while collector.is_running:
            live.update(_generate_layout())
            time.sleep(0.5)


# ── CLI Handlers ─────────────────────────────────────────────────────────────────


def _cmd_dashboard(args: argparse.Namespace) -> int:
    """Handle --dashboard: start live telemetry dashboard."""
    if not _RICH:
        print("Error: Rich library is required for the live dashboard.", file=sys.stderr)
        print("Install with: pip install rich", file=sys.stderr)
        return 1

    collector = create_default_collector(interval=args.interval)
    console = Console()

    try:
        # Take an initial snapshot so the dashboard has data immediately
        collector.snapshot()
        collector.start()
        console.print("[bold green]HLF Operator Dashboard started.[/bold green] Press Ctrl+C to exit.")
        console.print(f"[dim]Polling interval: {args.interval}s[/dim]")
        console.print()

        _render_live_dashboard(console, collector)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Shutting down...[/bold yellow]")
    finally:
        collector.stop()

    return 0


def _cmd_snapshot(args: argparse.Namespace) -> int:
    """Handle --snapshot: one-shot readiness snapshot to stdout."""
    collector = create_default_collector()
    snap = collector.snapshot()

    if args.json_output:
        print(json.dumps(snap.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(snap.to_ndjson())

    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    """Handle --watch: repeated snapshots with configurable refresh."""
    collector = create_default_collector(interval=args.interval)
    console = Console() if _RICH else None

    try:
        collector.start()
        if _RICH and console:
            console.print("[bold green]Watch mode started.[/bold green] Press Ctrl+C to exit.")
        else:
            print("Watch mode started. Press Ctrl+C to exit.")

        while True:
            history = collector.history()
            if history:
                snap = history[-1]

                if _RICH and console:
                    color = "green" if snap.overall_readiness_pct >= 65 else \
                            "yellow" if snap.overall_readiness_pct >= 50 else "red"
                    console.print(
                        f"[{color}]{snap.timestamp}[/{color}]  "
                        f"Readiness: [{color}]{snap.overall_readiness_pct}%[/{color}]  "
                        f"Status: [{color}]{snap.alert_thresholds.get('overall', '?')}[/{color}]"
                    )
                else:
                    print(
                        f"{snap.timestamp}  Readiness: {snap.overall_readiness_pct}%  "
                        f"Status: {snap.alert_thresholds.get('overall', '?')}"
                    )

            time.sleep(args.interval)

    except KeyboardInterrupt:
        if _RICH and console:
            console.print("\n[bold yellow]Watch mode stopped.[/bold yellow]")
        else:
            print("\nWatch mode stopped.")
    finally:
        collector.stop()

    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    """Handle 'status' subcommand: current status summary."""
    dashboard = build_dashboard_data()
    overall = dashboard["overall_status"]
    pillar = dashboard["pillar_score"]

    if _RICH:
        console = Console()
        color = {"healthy": "green", "degraded": "yellow", "critical": "red"}.get(overall, "white")
        console.print(Panel(
            f"[bold {color}]Overall Status: {overall.upper()}[/bold {color}]\n"
            f"Pillar: {pillar['pillar']}\n"
            f"Score: {pillar['score_pct']}% (target: {pillar['target_pct']}%)\n"
            f"Status: {pillar['status']}\n"
            f"Generated: {dashboard['generated_at']}",
            title="HLF Status",
            border_style=color,
        ))
    else:
        print(f"Overall Status: {overall.upper()}")
        print(f"Pillar: {pillar['pillar']} — {pillar['score_pct']}% (target: {pillar['target_pct']}%)")
        print(f"Status: {pillar['status']}")
        print(f"Generated: {dashboard['generated_at']}")

    return 0


def _cmd_pillars(args: argparse.Namespace) -> int:
    """Handle 'pillars' subcommand: per-pillar scores."""
    dashboard = build_dashboard_data()
    components = dashboard["pillar_score"].get("components", {})

    if _RICH:
        console = Console()
        table = Table(title="Per-Pillar Readiness Scores", box=box.SIMPLE)
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="dim")
        table.add_column("Score", style="white")
        for name, info in components.items():
            s = info["score_pct"]
            color = "green" if s >= 70 else "yellow" if s >= 50 else "red"
            bar = "█" * int(s / 10) + "░" * (10 - int(s / 10))
            table.add_row(
                name.replace("_", " ").title(),
                info["status"],
                f"[{color}]{bar} {s}%[/{color}]",
            )
        console.print(table)
    else:
        print(f"{'Component':<25} {'Status':<15} {'Score'}")
        print("-" * 55)
        for name, info in components.items():
            s = info["score_pct"]
            bar = "#" * int(s / 10) + "-" * (10 - int(s / 10))
            print(f"{name.replace('_', ' ').title():<25} {info['status']:<15} [{bar}] {s}%")

    return 0


def _cmd_violations(args: argparse.Namespace) -> int:
    """Handle 'violations' subcommand: constitutional violations."""
    from hlf_mcp.gallery.operator_dashboard import collect_constitutional_violations
    const = collect_constitutional_violations()
    summary = const["summary"]
    violations = const["violations"]

    if _RICH:
        console = Console()
        console.print(Panel(
            f"Total: [red]{summary['total_violations']}[/red]  "
            f"High: [red]{summary['high_severity']}[/red]  "
            f"Medium: [yellow]{summary['medium_severity']}[/yellow]  "
            f"Low: [dim]{summary['low_severity']}[/dim]  "
            f"Blocked: {summary['blocked_count']}",
            title="Constitutional Violations",
            border_style="red" if summary["total_violations"] > 0 else "green",
        ))
        if violations:
            table = Table(box=box.SIMPLE)
            table.add_column("Rule", style="cyan")
            table.add_column("Detail", style="white")
            table.add_column("Severity")
            for v in violations:
                sev = v["severity"]
                sev_color = "red" if sev == "high" else "yellow" if sev == "medium" else "dim"
                table.add_row(
                    f"{v['rule_id']}: {v['rule_name']}",
                    v["detail"][:60],
                    f"[{sev_color}]{sev}[/{sev_color}]",
                )
            console.print(table)
    else:
        print(f"Constitutional Violations: {summary['total_violations']}")
        print(f"  High: {summary['high_severity']}, Medium: {summary['medium_severity']}, Low: {summary['low_severity']}")
        for v in violations:
            print(f"  [{v['severity'].upper()}] {v['rule_id']}: {v['rule_name']} — {v['detail']}")

    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    """Handle 'audit' subcommand: manifest audit trail."""
    from hlf_mcp.gallery.operator_dashboard import collect_manifest_audit_trail
    man = collect_manifest_audit_trail()
    summary = man["summary"]
    deployments = man["deployments"]

    if _RICH:
        console = Console()
        console.print(Panel(
            f"Total: {summary['total_deployments']}  "
            f"Approved: [green]{summary['approved']}[/green]  "
            f"Rejected: [red]{summary['rejected']}[/red]  "
            f"Rate: {summary['approval_rate_pct']}%",
            title="Manifest Audit Trail",
            border_style="blue",
        ))
        table = Table(box=box.SIMPLE)
        table.add_column("Program", style="cyan")
        table.add_column("Tier", style="magenta")
        table.add_column("Capabilities", style="dim")
        table.add_column("Approved")
        for d in deployments:
            approved = "✓ [green]yes[/green]" if d["approved"] else "✗ [red]no[/red]"
            table.add_row(
                d["program"],
                d["tier"],
                ", ".join(d["capabilities"])[:40],
                approved,
            )
        console.print(table)
    else:
        print(f"Manifest Audit Trail:")
        print(f"  Total: {summary['total_deployments']}, Approved: {summary['approved']}, Rejected: {summary['rejected']}")
        print(f"  Approval Rate: {summary['approval_rate_pct']}%")
        for d in deployments:
            status = "APPROVED" if d["approved"] else "REJECTED"
            print(f"  [{status}] {d['program']} — Tier: {d['tier']} — Caps: {', '.join(d['capabilities'])}")

    return 0


# ── Argument Parser ──────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the operator CLI.

    Returns:
        Configured ArgumentParser with all subcommands and flags.
    """
    parser = argparse.ArgumentParser(
        prog="hlf-operator",
        description="HLF Gallery Operator CLI — monitor and inspect HLF system state.",
    )

    # Mutually exclusive mode flags
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dashboard",
        action="store_true",
        help="Start live telemetry dashboard with Rich UI",
    )
    mode_group.add_argument(
        "--snapshot",
        action="store_true",
        help="Take a one-shot readiness snapshot and output to stdout",
    )
    mode_group.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: continuously output snapshots at intervals",
    )

    # --json is NOT mutually exclusive; it modifies --snapshot output format
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output snapshot as pretty-printed JSON instead of ndjson",
    )

    # Shared options
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Polling/refresh interval in seconds (default: 2.0)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="subcommand", help="Inspection subcommands")

    subparsers.add_parser("status", help="Show current system status summary")
    subparsers.add_parser("pillars", help="Show per-pillar readiness scores")
    subparsers.add_parser("violations", help="Show constitutional violations")
    subparsers.add_parser("audit", help="Show manifest audit trail")

    return parser


# ── Main Entry Point ─────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the operator CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Route to handler based on mode
    if args.dashboard:
        return _cmd_dashboard(args)
    elif args.snapshot:
        return _cmd_snapshot(args)
    elif args.watch:
        return _cmd_watch(args)
    elif args.subcommand == "status":
        return _cmd_status(args)
    elif args.subcommand == "pillars":
        return _cmd_pillars(args)
    elif args.subcommand == "violations":
        return _cmd_violations(args)
    elif args.subcommand == "audit":
        return _cmd_audit(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
