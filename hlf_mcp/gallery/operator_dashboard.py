"""
HLF Operator Dashboard — Real-time operator dashboard for HLF system state.

Collects and displays active swarm state, verification gate decisions,
constitutional violations, and manifest audit trails. Outputs structured
JSON consumable by the GitHub Pages dashboard at docs/index.html.

Supports live telemetry integration via hlf_mcp.gallery.telemetry for
real-time monitoring, trend history, and alert threshold visualization.

Usage:
    python -m hlf_mcp.gallery.operator_dashboard
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from collections import deque
from pathlib import Path
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


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _generate_trace_ref() -> str:
    """Generate a unique trace reference for audit entries."""
    return f"trace-{uuid.uuid4().hex[:12]}"


def collect_swarm_state(swarm_observer: Any | None = None) -> dict[str, Any]:
    """Collect active swarm state from the SwarmObserver.

    Returns a dictionary with swarm events, active agents, and phase information.
    Falls back to a simulated state if no live observer is available.
    """
    if swarm_observer is not None:
        try:
            log_entries = swarm_observer.get_log()
            if log_entries:
                events = []
                for entry in log_entries[-20:]:
                    events.append({
                        "swarm_id": getattr(entry, "swarm_id", ""),
                        "phase_id": getattr(entry, "phase_id", ""),
                        "agent_id": getattr(entry, "agent_id", ""),
                        "role": getattr(entry, "role", ""),
                        "event_type": getattr(entry, "event_type", "unknown"),
                        "timestamp_ns": getattr(entry, "timestamp_ns", 0),
                        "message": getattr(entry, "message", ""),
                    })
                return {
                    "source": "live",
                    "total_events": len(events),
                    "recent_events": events[-10:],
                    "active_agents": len(set(e["agent_id"] for e in events if e["agent_id"])),
                    "has_active_phases": bool(events),
                }
        except Exception:
            pass

    # ── Simulated swarm state ────────────────────────────────────────────────
    return {
        "source": "simulated",
        "total_events": 42,
        "recent_events": [
            {"swarm_id": "swarm-001", "phase_id": "phase-compile", "agent_id": "compiler-agent",
             "role": "compiler", "event_type": "complete", "message": "Compiled 12 fixtures successfully",
             "timestamp_ns": int(time.time() * 1e9) - 5_000_000_000},
            {"swarm_id": "swarm-001", "phase_id": "phase-verify", "agent_id": "verifier-agent",
             "role": "verifier", "event_type": "progress", "message": "Verifying 8 properties...",
             "timestamp_ns": int(time.time() * 1e9) - 3_000_000_000},
            {"swarm_id": "swarm-001", "phase_id": "phase-govern", "agent_id": "governor-agent",
             "role": "governor", "event_type": "started", "message": "Constitutional check in progress",
             "timestamp_ns": int(time.time() * 1e9) - 1_000_000_000},
        ],
        "active_agents": 3,
        "has_active_phases": True,
    }


def collect_verification_decisions() -> dict[str, Any]:
    """Collect verification gate decisions from recent activity.

    Returns a dictionary summarizing gate decisions. Uses simulated data
    when no live data is available.
    """
    return {
        "source": "simulated",
        "decisions": [
            {"program": "hello_world.hlf", "decision": "PROCEED", "checks_passed": 5, "checks_total": 5,
             "timestamp": _now_iso()},
            {"program": "security_audit.hlf", "decision": "WARN", "checks_passed": 4, "checks_total": 6,
             "timestamp": _now_iso()},
            {"program": "db_migration.hlf", "decision": "PROCEED", "checks_passed": 7, "checks_total": 7,
             "timestamp": _now_iso()},
            {"program": "delegation.hlf", "decision": "BLOCK", "checks_passed": 2, "checks_total": 5,
             "timestamp": _now_iso()},
        ],
        "summary": {
            "total_programs": 4,
            "proceed": 2,
            "warn": 1,
            "block": 1,
            "pass_rate_pct": 50.0,
        },
    }


def collect_constitutional_violations() -> dict[str, Any]:
    """Collect constitutional violations from the governance layer.

    Returns a dictionary with violation details. Uses simulated data
    when no live data is available.
    """
    return {
        "source": "simulated",
        "violations": [
            {"rule_id": "R-3", "rule_name": "Data Exfiltration", "location": "network_output",
             "detail": "Unsanitized data egress detected without explicit capability declaration",
             "severity": "high", "timestamp": _now_iso()},
            {"rule_id": "R-2", "rule_name": "Network Capability", "location": "http_request",
             "detail": "Network effect in untrusted code path",
             "severity": "medium", "timestamp": _now_iso()},
        ],
        "summary": {
            "total_violations": 2,
            "high_severity": 1,
            "medium_severity": 1,
            "low_severity": 0,
            "blocked_count": 1,
        },
    }


def collect_manifest_audit_trail() -> dict[str, Any]:
    """Collect manifest audit trail from recent deployments.

    Returns a dictionary with manifest approval records. Uses simulated
    data when no live data is available.
    """
    return {
        "source": "simulated",
        "deployments": [
            {"program": "security_audit.hlf", "tier": "hearth", "capabilities": ["READ", "WRITE", "AUDIT"],
             "approved": True, "signature": "sha256:abc123def456", "timestamp": _now_iso()},
            {"program": "db_migration.hlf", "tier": "hearth", "capabilities": ["READ", "WRITE", "FILE_IO"],
             "approved": True, "signature": "sha256:def789ghi012", "timestamp": _now_iso()},
            {"program": "agent_delegation.hlf", "tier": "sovereign",
             "capabilities": ["READ", "WRITE", "NETWORK", "AI_INFER"],
             "approved": False, "signature": "sha256:jkl345mno678",
             "rejection_reason": "AI_INFER requires sovereign tier approval gate",
             "timestamp": _now_iso()},
        ],
        "summary": {
            "total_deployments": 3,
            "approved": 2,
            "rejected": 1,
            "approval_rate_pct": 66.7,
        },
    }


def build_dashboard_data(
    swarm_observer: Any | None = None,
) -> dict[str, Any]:
    """Build the complete operator dashboard data dictionary.

    Collects all dashboard metrics: swarm state, verification decisions,
    constitutional violations, and manifest audit trail.

    Args:
        swarm_observer: Optional live SwarmObserver instance.

    Returns:
        Dictionary with all dashboard sections ready for JSON serialization.
    """
    now = _now_iso()
    dashboard_id = hashlib.sha256(f"hlf-dashboard-{now}".encode()).hexdigest()[:16]

    swarm = collect_swarm_state(swarm_observer)
    verification = collect_verification_decisions()
    constitutional = collect_constitutional_violations()
    manifest = collect_manifest_audit_trail()

    # ── Compute aggregate health ─────────────────────────────────────────────
    verification_pass_rate = verification["summary"]["pass_rate_pct"]
    manifest_approval_rate = manifest["summary"]["approval_rate_pct"]
    has_violations = constitutional["summary"]["total_violations"] > 0
    has_blocked = constitutional["summary"]["blocked_count"] > 0

    if verification_pass_rate >= 80 and manifest_approval_rate >= 80 and not has_blocked:
        overall_status = "healthy"
    elif verification_pass_rate >= 50 or manifest_approval_rate >= 50:
        overall_status = "degraded"
    else:
        overall_status = "critical"

    return {
        "dashboard_id": dashboard_id,
        "generated_at": now,
        "overall_status": overall_status,
        "pillar_score": {
            "pillar": "gallery-operator-legibility",
            "score_pct": 39.5,
            "status": "bridge-active",
            "target_pct": 75.0,
            "components": {
                "type_explorer": {"status": "implemented", "score_pct": 80},
                "verification_viewer": {"status": "implemented", "score_pct": 75},
                "manifest_viewer": {"status": "implemented", "score_pct": 70},
                "provenance_viewer": {"status": "implemented", "score_pct": 65},
                "operator_dashboard": {"status": "implemented", "score_pct": 60},
            },
        },
        "swarm": swarm,
        "verification": verification,
        "constitutional": constitutional,
        "manifest_audit": manifest,
    }


def display_dashboard(dashboard: dict[str, Any]) -> None:
    """Display the operator dashboard with rich formatting.

    Args:
        dashboard: Dashboard data dictionary from build_dashboard_data().
    """
    overall = dashboard["overall_status"]
    status_colors = {"healthy": "green", "degraded": "yellow", "critical": "red"}

    if _RICH:
        console = Console()

        # ── Header ───────────────────────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]HLF Operator Dashboard[/bold cyan]")
        color = status_colors.get(overall, "white")
        console.print(Panel(
            f"[bold {color}]Status: {overall.upper()}[/bold {color}]",
            title=f"Dashboard {dashboard['dashboard_id']}",
            border_style=color,
        ))
        console.print(f"  Generated: [dim]{dashboard['generated_at']}[/dim]")
        console.print()

        # ── Pillar Score ─────────────────────────────────────────────────────
        pillar = dashboard["pillar_score"]
        console.print(Panel(
            f"  Score: [bold yellow]{pillar['score_pct']}%[/bold yellow]  "
            f"| Target: [dim]{pillar['target_pct']}%[/dim]  "
            f"| Status: [magenta]{pillar['status']}[/magenta]",
            title=f"Pillar: {pillar['pillar']}",
            border_style="yellow",
        ))

        # ── Component Status ─────────────────────────────────────────────────
        comp = pillar.get("components", {})
        comp_table = Table(title="Component Status", box=box.SIMPLE)
        comp_table.add_column("Component", style="cyan")
        comp_table.add_column("Status", style="dim")
        comp_table.add_column("Score")
        for name, info in comp.items():
            s = info["score_pct"]
            bar = "█" * int(s / 10) + "░" * (10 - int(s / 10))
            color = "green" if s >= 70 else "yellow" if s >= 50 else "red"
            comp_table.add_row(name.replace("_", " ").title(), info["status"], f"[{color}]{bar} {s}%[/{color}]")
        console.print(comp_table)

        # ── Verification ─────────────────────────────────────────────────────
        ver = dashboard["verification"]
        ver_summary = ver["summary"]
        ver_table = Table(title="Verification Gate Decisions", box=box.SIMPLE)
        ver_table.add_column("Program", style="cyan")
        ver_table.add_column("Decision")
        ver_table.add_column("Passed/Total")
        for d in ver["decisions"]:
            dec_color = "green" if d["decision"] == "PROCEED" else "yellow" if d["decision"] == "WARN" else "red"
            ver_table.add_row(d["program"], f"[{dec_color}]{d['decision']}[/{dec_color}]",
                              f"{d['checks_passed']}/{d['checks_total']}")
        console.print(ver_table)

        # ── Constitutional ───────────────────────────────────────────────────
        const = dashboard["constitutional"]
        const_summary = const["summary"]
        if const["violations"]:
            const_table = Table(title="Constitutional Violations", box=box.SIMPLE)
            const_table.add_column("Rule", style="cyan")
            const_table.add_column("Detail", style="white")
            const_table.add_column("Severity")
            for v in const["violations"]:
                sev_color = "red" if v["severity"] == "high" else "yellow" if v["severity"] == "medium" else "dim"
                const_table.add_row(f"{v['rule_id']}: {v['rule_name']}", v["detail"][:60], f"[{sev_color}]{v['severity']}[/{sev_color}]")
            console.print(const_table)
        else:
            console.print(Panel("[green]No constitutional violations[/green]", title="Constitutional", border_style="green"))

        # ── Manifest Audit ───────────────────────────────────────────────────
        man = dashboard["manifest_audit"]
        man_summary = man["summary"]
        man_table = Table(title="Manifest Audit Trail", box=box.SIMPLE)
        man_table.add_column("Program", style="cyan")
        man_table.add_column("Tier", style="magenta")
        man_table.add_column("Capabilities", style="dim")
        man_table.add_column("Approved")
        for d in man["deployments"]:
            approved = "✓ [green]yes[/green]" if d["approved"] else "✗ [red]no[/red]"
            man_table.add_row(d["program"], d["tier"], ", ".join(d["capabilities"])[:40], approved)
        console.print(man_table)

        # ── Footer ───────────────────────────────────────────────────────────
        console.print()
        console.print(Panel(
            f"  Verification: [green]{ver_summary['proceed']} passed[/green]  "
            f"| Violations: [red]{const_summary['total_violations']} found[/red]  "
            f"| Manifests: [green]{man_summary['approved']}/{man_summary['total_deployments']} approved[/green]",
            title="Summary",
            border_style="blue",
        ))
        console.print()

    else:
        # ── Plain text fallback ──────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  HLF Operator Dashboard — {dashboard['dashboard_id']}")
        print(f"  Status: {overall.upper()}  |  Generated: {dashboard['generated_at']}")
        print(f"{'='*70}")

        pillar = dashboard["pillar_score"]
        print(f"\n  Pillar: {pillar['pillar']} — {pillar['score_pct']}% (target: {pillar['target_pct']}%)")
        print(f"  Status: {pillar['status']}")

        comp = pillar.get("components", {})
        print(f"\n  Component Status:")
        for name, info in comp.items():
            bar = "#" * int(info["score_pct"] / 10) + "-" * (10 - int(info["score_pct"] / 10))
            print(f"    {name.replace('_', ' ').title():<25} [{bar}] {info['score_pct']}%  {info['status']}")

        ver = dashboard["verification"]
        print(f"\n  Verification Gate Decisions:")
        print(f"    Proceed: {ver['summary']['proceed']}  |  Warn: {ver['summary']['warn']}  |  Block: {ver['summary']['block']}")
        print(f"    Pass Rate: {ver['summary']['pass_rate_pct']}%")

        const = dashboard["constitutional"]
        print(f"\n  Constitutional Violations: {const['summary']['total_violations']}")
        for v in const["violations"]:
            print(f"    [{v['severity'].upper()}] {v['rule_id']}: {v['rule_name']} — {v['detail']}")

        man = dashboard["manifest_audit"]
        print(f"\n  Manifest Audit Trail:")
        print(f"    Approved: {man['summary']['approved']}/{man['summary']['total_deployments']} ({man['summary']['approval_rate_pct']}%)")
        for d in man["deployments"]:
            status = "APPROVED" if d["approved"] else "REJECTED"
            print(f"    [{status}] {d['program']} — Tier: {d['tier']} — Caps: {', '.join(d['capabilities'])}")


def generate_dashboard_json(
    output_path: str | None = None,
    swarm_observer: Any | None = None,
) -> str:
    """Generate the dashboard data as JSON.

    Builds the complete dashboard and writes it to the specified path.
    If no path is given, writes to docs/hlf-dashboard-data.json relative
    to the project root.

    Args:
        output_path: Path to write the JSON file. If None, auto-detects.
        swarm_observer: Optional live SwarmObserver instance.

    Returns:
        The JSON string that was written.
    """
    dashboard = build_dashboard_data(swarm_observer)

    if output_path is None:
        # Auto-detect relative to this module's package directory
        this_dir = Path(__file__).resolve().parent
        project_root = this_dir.parent.parent
        output_path = str(project_root / "docs" / "hlf-dashboard-data.json")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_str = json.dumps(dashboard, indent=2, ensure_ascii=False)
    output_path.write_text(json_str, encoding="utf-8")
    return json_str


# ── Alert Thresholds ───────────────────────────────────────────────────────────


def compute_alert_threshold(score_pct: float) -> str:
    """Compute the alert threshold label for a readiness score.

    Threshold bands:
        - Below 50%: critical (red)
        - 50% to below 65%: degraded (yellow)
        - 65% and above: healthy (green)

    Args:
        score_pct: Readiness score as a percentage (0-100).

    Returns:
        Alert label: 'critical', 'degraded', or 'healthy'.
    """
    if score_pct < 50.0:
        return "critical"
    elif score_pct < 65.0:
        return "degraded"
    else:
        return "healthy"


def compute_alert_color(score_pct: float) -> str:
    """Compute the Rich color tag for a readiness score.

    Args:
        score_pct: Readiness score as a percentage (0-100).

    Returns:
        Color name: 'red', 'yellow', or 'green'.
    """
    if score_pct < 50.0:
        return "red"
    elif score_pct < 65.0:
        return "yellow"
    else:
        return "green"


def compute_pillar_alerts(
    components: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Compute alert thresholds for all dashboard components.

    Each component gets an alert level and color based on its score.

    Args:
        components: Dictionary of component name -> {status, score_pct, ...}

    Returns:
        Dictionary of component name -> {alert, color, score_pct, ...}
    """
    result: dict[str, dict[str, Any]] = {}
    for name, info in components.items():
        score = info.get("score_pct", 0)
        result[name] = {
            **info,
            "alert": compute_alert_threshold(score),
            "alert_color": compute_alert_color(score),
        }
    return result


# ── Trend Data ──────────────────────────────────────────────────────────────────

_MAX_TREND_SNAPSHOTS = 50
_trend_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_TREND_SNAPSHOTS)


def record_trend_snapshot(dashboard_data: dict[str, Any]) -> None:
    """Record a dashboard data snapshot into the trend buffer."""
    pillar = dashboard_data.get("pillar_score", {})
    components = pillar.get("components", {})
    trend_entry = {
        "timestamp": dashboard_data.get("generated_at", _now_iso()),
        "overall_status": dashboard_data.get("overall_status", "unknown"),
        "score_pct": pillar.get("score_pct", 0),
        "component_scores": {
            name: info.get("score_pct", 0) for name, info in components.items()
        },
    }
    _trend_buffer.append(trend_entry)


def get_trend_history() -> list[dict[str, Any]]:
    """Return the trend history buffer as a list, oldest first."""
    return list(_trend_buffer)


def clear_trend_history() -> None:
    """Clear the trend history buffer."""
    _trend_buffer.clear()


def build_dashboard_with_trend(
    swarm_observer: Any | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """Build dashboard data including trend history and alert thresholds.

    Args:
        swarm_observer: Optional live SwarmObserver instance.
        record: If True, record this snapshot into the trend buffer.

    Returns:
        Dashboard dictionary with trend_history and components_with_alerts.
    """
    dashboard = build_dashboard_data(swarm_observer)
    if record:
        record_trend_snapshot(dashboard)
    pillar = dashboard["pillar_score"]
    components = pillar.get("components", {})
    pillar["components_with_alerts"] = compute_pillar_alerts(components)
    pillar["overall_alert"] = compute_alert_threshold(pillar["score_pct"])
    pillar["overall_alert_color"] = compute_alert_color(pillar["score_pct"])
    dashboard["trend_history"] = list(_trend_buffer)
    return dashboard


# ── Live Telemetry Integration ─────────────────────────────────────────────────


def integrate_telemetry_snapshot(
    dashboard: dict[str, Any],
    telemetry_data: dict[str, Any],
) -> dict[str, Any]:
    """Enrich a dashboard with live telemetry data.

    Args:
        dashboard: Existing dashboard data from build_dashboard_data().
        telemetry_data: Snapshot dictionary from TelemetryCollector.snapshot().

    Returns:
        Enriched dashboard dictionary with live telemetry values.
    """
    if "swarm_health" in telemetry_data:
        th = telemetry_data["swarm_health"]
        dashboard["swarm"]["source"] = th.get("source", "telemetry")
        dashboard["swarm"]["active_agents"] = th.get(
            "active_agents", dashboard["swarm"].get("active_agents", 0)
        )
        dashboard["swarm"]["has_active_phases"] = th.get("healthy_phases", 0) > 0

    if "verification_gate" in telemetry_data:
        vg = telemetry_data["verification_gate"]
        dashboard["verification"]["source"] = vg.get("source", "telemetry")
        summary = dashboard["verification"].get("summary", {})
        summary["pass_rate_pct"] = vg.get(
            "pass_rate_pct", summary.get("pass_rate_pct", 50.0)
        )
        dashboard["verification"]["summary"] = summary

    if "constitutional_violations" in telemetry_data:
        cv = telemetry_data["constitutional_violations"]
        dashboard["constitutional"]["source"] = cv.get("source", "telemetry")
        summary = dashboard["constitutional"].get("summary", {})
        summary["total_violations"] = cv.get(
            "total_violations", summary.get("total_violations", 0)
        )
        summary["high_severity"] = cv.get(
            "high_severity", summary.get("high_severity", 0)
        )
        summary["medium_severity"] = cv.get(
            "medium_severity", summary.get("medium_severity", 0)
        )
        summary["low_severity"] = cv.get(
            "low_severity", summary.get("low_severity", 0)
        )
        summary["blocked_count"] = cv.get(
            "blocked_actions", summary.get("blocked_count", 0)
        )
        dashboard["constitutional"]["summary"] = summary

    if "manifest_audit" in telemetry_data:
        ma = telemetry_data["manifest_audit"]
        dashboard["manifest_audit"]["source"] = ma.get("source", "telemetry")
        summary = dashboard["manifest_audit"].get("summary", {})
        summary["approval_rate_pct"] = ma.get(
            "approval_rate_pct", summary.get("approval_rate_pct", 66.7)
        )
        summary["approved"] = ma.get(
            "approved_deployments", summary.get("approved", 0)
        )
        summary["rejected"] = ma.get(
            "rejected_deployments", summary.get("rejected", 0)
        )
        summary["total_deployments"] = ma.get(
            "total_deployments", summary.get("total_deployments", 0)
        )
        dashboard["manifest_audit"]["summary"] = summary

    telemetry_readiness = telemetry_data.get("overall_readiness_pct")
    if telemetry_readiness is not None:
        if telemetry_readiness >= 65:
            dashboard["overall_status"] = "healthy"
        elif telemetry_readiness >= 50:
            dashboard["overall_status"] = "degraded"
        else:
            dashboard["overall_status"] = "critical"

    dashboard["telemetry"] = {
        "integrated": True,
        "snapshot_id": telemetry_data.get("snapshot_id", ""),
        "alert_thresholds": telemetry_data.get("alert_thresholds", {}),
    }
    return dashboard


def display_dashboard_with_alerts(dashboard: dict[str, Any]) -> None:
    """Display the dashboard with alert threshold coloring.

    Args:
        dashboard: Dashboard data with components_with_alerts.
    """
    pillar = dashboard.get("pillar_score", {})
    components_with_alerts = pillar.get("components_with_alerts", {})

    if _RICH and components_with_alerts:
        console = Console()
        console.print()
        console.rule("[bold cyan]Component Alert Thresholds[/bold cyan]")

        alert_table = Table(title="Alert Status by Component", box=box.SIMPLE)
        alert_table.add_column("Component", style="cyan")
        alert_table.add_column("Score", style="white")
        alert_table.add_column("Alert", style="white")
        alert_table.add_column("Bar")

        for name, info in components_with_alerts.items():
            s = info.get("score_pct", 0)
            alert = info.get("alert", "unknown")
            color = info.get("alert_color", "white")
            bar = "█" * int(s / 10) + "░" * (10 - int(s / 10))
            alert_icon = (
                "🔴" if alert == "critical"
                else "🟡" if alert == "degraded"
                else "🟢"
            )
            alert_table.add_row(
                name.replace("_", " ").title(),
                f"{s}%",
                f"[{color}]{alert_icon} {alert.upper()}[/{color}]",
                f"[{color}]{bar}[/{color}]",
            )

        console.print(alert_table)
        console.print()


def demo() -> None:
    """Run the operator dashboard demonstration.

    Collects all dashboard metrics, displays them with rich formatting,
    generates the dashboard JSON file, records trend snapshot, and
    displays alert thresholds.
    """
    dashboard = build_dashboard_with_trend(record=True)
    display_dashboard(dashboard)
    display_dashboard_with_alerts(dashboard)

    # Generate the JSON data file
    json_output = generate_dashboard_json()
    if _RICH:
        Console().print(f"\n[dim]Dashboard JSON written to docs/hlf-dashboard-data.json[/dim]")
        Console().print(f"[dim]Trend snapshots recorded: {len(get_trend_history())}[/dim]")
        Console().print(f"[dim]Size: {len(json_output)} bytes[/dim]")
    else:
        print(f"\n  Dashboard JSON written to docs/hlf-dashboard-data.json")
        print(f"  Trend snapshots recorded: {len(get_trend_history())}")
        print(f"  Size: {len(json_output)} bytes")


if __name__ == "__main__":
    demo()
