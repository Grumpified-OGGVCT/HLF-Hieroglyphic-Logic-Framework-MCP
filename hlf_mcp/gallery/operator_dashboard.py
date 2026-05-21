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

# ── Optional live data imports ─────────────────────────────────────────────────
_LIVE_IMPORTS_OK = False
_LIVE_IMPORT_ERRORS: list[str] = []

try:
    from hlf_mcp.instinct.lifecycle import InstinctLifecycle
    _LIVE_IMPORTS_OK = True
except ImportError as e:
    _LIVE_IMPORT_ERRORS.append(f"InstinctLifecycle: {e}")

try:
    from hlf_mcp.hlf.memory_node import EvidenceContract
except ImportError as e:
    _LIVE_IMPORT_ERRORS.append(f"EvidenceContract: {e}")

try:
    from hlf_mcp.media_evidence import MediaEvidenceRecord
except ImportError as e:
    _LIVE_IMPORT_ERRORS.append(f"MediaEvidenceRecord: {e}")

try:
    from hlf_mcp.dream_cycle import DreamFinding, DreamCycleReport, build_dream_findings
except ImportError as e:
    _LIVE_IMPORT_ERRORS.append(f"DreamCycle: {e}")

# ── Module-level lifecycle singleton for live data ────────────────────────────
_lifecycle: Any = None


def _get_lifecycle() -> Any:
    """Get or create the module-level InstinctLifecycle singleton."""
    global _lifecycle
    if _lifecycle is None and _LIVE_IMPORTS_OK:
        try:
            _lifecycle = InstinctLifecycle()
        except Exception:
            pass
    return _lifecycle


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _generate_trace_ref() -> str:
    """Generate a unique trace reference for audit entries."""
    return f"trace-{uuid.uuid4().hex[:12]}"


def collect_swarm_state(
    swarm_observer: Any | None = None,
    use_live_data: bool = True,
) -> dict[str, Any]:
    """Collect active swarm state from the SwarmObserver.

    Returns a dictionary with swarm events, active agents, and phase information.
    Falls back to a simulated state if no live observer is available.

    Args:
        swarm_observer: Optional live SwarmObserver instance.
        use_live_data: When True, attempt to read from InstinctLifecycle missions.
                       When False, use simulated data immediately.
    """
    # ── Live data path: read from InstinctLifecycle missions ────────────────
    if use_live_data:
        lifecycle = _get_lifecycle()
        if lifecycle is not None:
            try:
                missions = lifecycle.list_missions()
                if missions:
                    phases: dict[str, int] = {}
                    total_events = 0
                    for m in missions:
                        phase = m.get("current_phase", "unknown")
                        phases[phase] = phases.get(phase, 0) + 1
                        total_events += m.get("plan_nodes", 0)
                    phase_distribution = [
                        {"phase": phase, "count": count}
                        for phase, count in sorted(phases.items())
                    ]
                    return {
                        "source": "live",
                        "total_events": total_events,
                        "recent_events": [],
                        "active_agents": len(missions),
                        "has_active_phases": bool(phases),
                        "phase_distribution": phase_distribution,
                        "total_missions": len(missions),
                        "sealed_missions": sum(1 for m in missions if m.get("sealed")),
                    }
            except Exception:
                pass

    # ── Swarm observer path (legacy) ────────────────────────────────────────
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


def collect_verification_decisions(
    use_live_data: bool = True,
) -> dict[str, Any]:
    """Collect verification gate decisions from recent activity.

    Returns a dictionary summarizing gate decisions. Uses simulated data
    when no live data is available.

    Args:
        use_live_data: When True, attempt to read from actual verification missions.
                       When False, use simulated data immediately.
    """
    # ── Live data path: read from InstinctLifecycle missions ────────────────
    if use_live_data:
        lifecycle = _get_lifecycle()
        if lifecycle is not None:
            try:
                missions = lifecycle.list_missions()
                if missions:
                    decisions: list[dict[str, Any]] = []
                    proceed_count = 0
                    warn_count = 0
                    block_count = 0
                    for m in missions:
                        verdict = str(m.get("verdict", "")).lower()
                        mission_id = str(m.get("mission_id", ""))
                        if verdict in ("passed", "proceed"):
                            decision = "PROCEED"
                            proceed_count += 1
                        elif verdict in ("warn", "pending"):
                            decision = "WARN"
                            warn_count += 1
                        elif verdict in ("failed", "blocked", "block", "rejected"):
                            decision = "BLOCK"
                            block_count += 1
                        else:
                            decision = "WARN"
                            warn_count += 1
                        decisions.append({
                            "program": m.get("title", mission_id),
                            "mission_id": mission_id,
                            "decision": decision,
                            "checks_passed": int(m.get("plan_nodes_done", 0)),
                            "checks_total": int(m.get("plan_nodes", 0)),
                            "timestamp": _now_iso(),
                        })
                    total = proceed_count + warn_count + block_count
                    return {
                        "source": "live",
                        "decisions": decisions,
                        "summary": {
                            "total_programs": total,
                            "proceed": proceed_count,
                            "warn": warn_count,
                            "block": block_count,
                            "pass_rate_pct": round(proceed_count / total * 100, 1) if total else 0.0,
                        },
                    }
            except Exception:
                pass

    # ── Simulated verification decisions ────────────────────────────────────
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


def collect_constitutional_violations(
    use_live_data: bool = True,
) -> dict[str, Any]:
    """Collect constitutional violations from the governance layer.

    Returns a dictionary with violation details. Uses simulated data
    when no live data is available.

    Args:
        use_live_data: When True, attempt to read from actual constitutional data.
                       When False, use simulated data immediately.
    """
    # ── Live data path: read from constitution logs / manifest audit ───────
    if use_live_data:
        lifecycle = _get_lifecycle()
        if lifecycle is not None:
            try:
                missions = lifecycle.list_missions()
                violations: list[dict[str, Any]] = []
                for m in missions:
                    verdict = str(m.get("verdict", "")).lower()
                    if verdict in ("blocked", "failed", "rejected"):
                        violations.append({
                            "rule_id": m.get("blocking_rule", "R-X"),
                            "rule_name": m.get("blocking_rule_name", "Constitutional Violation"),
                            "location": str(m.get("mission_id", "unknown")),
                            "detail": str(m.get("verdict_reason", "Blocked by constitutional gate")),
                            "severity": "high" if verdict == "blocked" else "medium",
                            "timestamp": _now_iso(),
                        })
                if violations:
                    high_count = sum(1 for v in violations if v["severity"] == "high")
                    med_count = sum(1 for v in violations if v["severity"] == "medium")
                    low_count = sum(1 for v in violations if v["severity"] == "low")
                    return {
                        "source": "live",
                        "violations": violations,
                        "summary": {
                            "total_violations": len(violations),
                            "high_severity": high_count,
                            "medium_severity": med_count,
                            "low_severity": low_count,
                            "blocked_count": high_count,
                        },
                    }
            except Exception:
                pass

    # ── Simulated constitutional violations ─────────────────────────────────
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


def collect_manifest_audit_trail(
    use_live_data: bool = True,
) -> dict[str, Any]:
    """Collect manifest audit trail from recent deployments.

    Returns a dictionary with manifest approval records. Uses simulated
    data when no live data is available.

    Args:
        use_live_data: When True, attempt to read from actual mission data.
                       When False, use simulated data immediately.
    """
    # ── Live data path: read from mission ledgers ──────────────────────────
    if use_live_data:
        lifecycle = _get_lifecycle()
        if lifecycle is not None:
            try:
                missions = lifecycle.list_missions()
                deployments: list[dict[str, Any]] = []
                for m in missions:
                    mission_id = str(m.get("mission_id", ""))
                    try:
                        ledger = lifecycle.get_ledger(mission_id) if mission_id else None
                    except Exception:
                        ledger = None
                    approved = bool(m.get("sealed", False)) and str(m.get("verdict", "")) == "passed"
                    deployments.append({
                        "program": str(m.get("title", mission_id)),
                        "mission_id": mission_id,
                        "tier": str(m.get("tier", "hearth")),
                        "capabilities": m.get("declared_capabilities", []),
                        "approved": approved,
                        "signature": f"sha256:mission-{mission_id[:12]}",
                        "timestamp": _now_iso(),
                        "ledger_entries": len(ledger) if isinstance(ledger, list) else 0,
                    })
                approved_count = sum(1 for d in deployments if d["approved"])
                rejected_count = len(deployments) - approved_count
                total = len(deployments)
                return {
                    "source": "live",
                    "deployments": deployments,
                    "summary": {
                        "total_deployments": total,
                        "approved": approved_count,
                        "rejected": rejected_count,
                        "approval_rate_pct": round(approved_count / total * 100, 1) if total else 0.0,
                    },
                }
            except Exception:
                pass

    # ── Simulated manifest audit trail ─────────────────────────────────────
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
    use_live_data: bool = True,
) -> dict[str, Any]:
    """Build the complete operator dashboard data dictionary.

    Collects all dashboard metrics: swarm state, verification decisions,
    constitutional violations, and manifest audit trail.

    Args:
        swarm_observer: Optional live SwarmObserver instance.
        use_live_data: When True, attempt to read from live data sources.
                       When False, use simulated data for all collectors.

    Returns:
        Dictionary with all dashboard sections ready for JSON serialization.
    """
    now = _now_iso()
    dashboard_id = hashlib.sha256(f"hlf-dashboard-{now}".encode()).hexdigest()[:16]

    swarm = collect_swarm_state(swarm_observer, use_live_data=use_live_data)
    verification = collect_verification_decisions(use_live_data=use_live_data)
    constitutional = collect_constitutional_violations(use_live_data=use_live_data)
    manifest = collect_manifest_audit_trail(use_live_data=use_live_data)

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

    # ── Compute pillar score from component scores ─────────────────────────────
    components = {
        "type_explorer": {"status": "implemented", "score_pct": 80},
        "verification_viewer": {"status": "implemented", "score_pct": 75},
        "manifest_viewer": {"status": "implemented", "score_pct": 70},
        "provenance_viewer": {"status": "implemented", "score_pct": 65},
        "operator_dashboard": {"status": "implemented", "score_pct": 60},
    }
    pillar_score_pct = round(sum(c["score_pct"] for c in components.values()) / len(components), 1)

    return {
        "dashboard_id": dashboard_id,
        "generated_at": now,
        "overall_status": overall_status,
        "pillar_score": {
            "pillar": "gallery-operator-legibility",
            "score_pct": pillar_score_pct,
            "status": "bridge-active",
            "target_pct": 75.0,
            "components": components,
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


# ── Mission Panel ─────────────────────────────────────────────────────────────


def render_mission_panel(
    missions: list[dict[str, Any]] | None = None,
    use_live_data: bool = True,
    max_display: int = 10,
) -> str | None:
    """Render a mission status panel from InstinctLifecycle mission data.

    Args:
        missions: Pre-fetched mission list, or None to auto-fetch.
        use_live_data: If auto-fetching, whether to use live data.
        max_display: Maximum number of missions to display.

    Returns:
        Rich-rendered panel string, or None if Rich unavailable.
    """
    if missions is None:
        lifecycle = _get_lifecycle()
        if lifecycle is not None and use_live_data:
            try:
                missions = lifecycle.list_missions()
            except Exception:
                missions = []

    if not missions:
        if _RICH:
            return str(Panel(
                "[dim]No missions found[/dim]",
                title="Active Missions",
                border_style="dim",
            ))
        return None

    if not _RICH:
        # Plain text fallback
        lines = ["\n── Active Missions ──"]
        for m in missions[:max_display]:
            mid = str(m.get("mission_id", ""))[:12]
            title = str(m.get("title", "unnamed"))[:40]
            sealed = "🔒" if m.get("sealed") else "📋"
            verdict = str(m.get("verdict", "pending"))
            lines.append(f"  {sealed} {mid}  {title:<42}  [{verdict}]")
        return "\n".join(lines)

    from rich.table import Table as RichTable
    table = RichTable(title="Active Missions", box=box.SIMPLE)
    table.add_column("ID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Phase", style="magenta")
    table.add_column("Verdict")
    table.add_column("Sealed")

    for m in missions[:max_display]:
        mid = str(m.get("mission_id", ""))[:12]
        title = str(m.get("title", "unnamed"))[:50]
        phase = str(m.get("current_phase", "unknown"))
        verdict = str(m.get("verdict", "pending"))
        verdict_color = (
            "green" if verdict == "passed"
            else "red" if verdict in ("failed", "blocked", "rejected")
            else "yellow" if verdict == "warn"
            else "dim"
        )
        sealed = "[green]✓[/green]" if m.get("sealed") else "[dim]○[/dim]"
        table.add_row(mid, title, phase, f"[{verdict_color}]{verdict}[/{verdict_color}]", sealed)

    return str(table)


def display_mission_panel(
    use_live_data: bool = True,
    max_display: int = 10,
) -> None:
    """Display the mission status panel on the console.

    Args:
        use_live_data: Whether to attempt live data fetch.
        max_display: Maximum missions to show.
    """
    panel = render_mission_panel(use_live_data=use_live_data, max_display=max_display)
    if panel:
        if _RICH:
            Console().print(panel)
            Console().print()
        else:
            print(panel)


# ── Dream Findings Panel ──────────────────────────────────────────────────────


def render_dream_findings_panel(
    findings: list[Any] | None = None,
    use_live_data: bool = True,
    max_display: int = 5,
) -> str | None:
    """Render a dream findings panel with quality scores and witness status.

    Args:
        findings: Pre-fetched DreamFinding list, or None to auto-fetch.
        use_live_data: If auto-fetching, whether to use live data.
        max_display: Maximum findings to show.

    Returns:
        Rich-rendered panel string, or None if Rich unavailable.
    """
    if findings is None and use_live_data:
        try:
            from hlf_mcp.dream_cycle import build_dream_findings
            findings = build_dream_findings() or []
        except Exception:
            findings = []

    if not findings:
        if _RICH:
            return str(Panel(
                "[dim]No dream findings available[/dim]",
                title="Dream Findings",
                border_style="dim",
            ))
        return None

    if not _RICH:
        lines = ["\n── Dream Findings ──"]
        for f in findings[:max_display]:
            fid = str(getattr(f, "finding_id", "?"))[:12]
            title = str(getattr(f, "title", "untitled"))[:50]
            quality = getattr(f, "quality_score", 0.0)
            witness = str(getattr(f, "witness_status", "?"))
            lines.append(f"  [{witness}] {fid}  {title}  (quality: {quality:.2f})")
        return "\n".join(lines)

    table = Table(title="Dream Findings", box=box.SIMPLE)
    table.add_column("ID", style="dim")
    table.add_column("Title", style="cyan")
    table.add_column("Quality", style="yellow")
    table.add_column("Witness", style="magenta")
    table.add_column("Advisory")

    for f in findings[:max_display]:
        fid = str(getattr(f, "finding_id", "?"))[:12]
        title = str(getattr(f, "title", "untitled"))[:50]
        quality = getattr(f, "quality_score", 0.0)
        witness = str(getattr(f, "witness_status", "?"))
        advisory = "[yellow]⚠[/yellow]" if getattr(f, "advisory_only", False) else "[green]✓[/green]"
        quality_color = "green" if quality >= 0.7 else "yellow" if quality >= 0.4 else "red"
        table.add_row(fid, title, f"[{quality_color}]{quality:.2f}[/{quality_color}]", witness, advisory)

    return str(table)


def display_dream_findings_panel(
    use_live_data: bool = True,
    max_display: int = 5,
) -> None:
    """Display the dream findings panel on the console.

    Args:
        use_live_data: Whether to attempt live data fetch.
        max_display: Maximum findings to show.
    """
    panel = render_dream_findings_panel(use_live_data=use_live_data, max_display=max_display)
    if panel:
        if _RICH:
            Console().print(panel)
            Console().print()
        else:
            print(panel)


# ── Evidence Panel ────────────────────────────────────────────────────────────


def render_evidence_panel(
    evidence: list[Any] | None = None,
    use_live_data: bool = True,
    max_display: int = 8,
) -> str | None:
    """Render an evidence summary panel from EvidenceContract or MediaEvidenceRecord data.

    Args:
        evidence: Pre-fetched evidence list, or None to auto-fetch.
        use_live_data: If auto-fetching, whether to use live data.
        max_display: Maximum evidence items to show.

    Returns:
        Rich-rendered panel string, or None if Rich unavailable.
    """
    if evidence is None and use_live_data:
        try:
            from hlf_mcp.hlf.memory_node import EvidenceContract
            from hlf_mcp.media_evidence import MediaEvidenceRecord
        except ImportError:
            evidence = []

    if not evidence:
        if _RICH:
            return str(Panel(
                "[dim]No evidence records found[/dim]",
                title="Evidence Chain",
                border_style="dim",
            ))
        return None

    if not _RICH:
        lines = ["\n── Evidence Chain ──"]
        for e in evidence[:max_display]:
            if isinstance(e, dict):
                sha = str(e.get("sha256", e.get("artifact_id", "?")))[:12]
                tier = str(e.get("trust_tier", "?"))
                confidence = e.get("confidence", 0.0)
                lines.append(f"  [{tier}] {sha}  confidence: {confidence:.0%}")
            else:
                sha = str(getattr(e, "sha256", getattr(e, "artifact_id", "?")))[:12]
                tier = str(getattr(e, "trust_tier", "?"))
                confidence = getattr(e, "confidence", 0.0)
                lines.append(f"  [{tier}] {sha}  confidence: {confidence:.0%}")
        return "\n".join(lines)

    table = Table(title="Evidence Chain", box=box.SIMPLE)
    table.add_column("SHA", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Tier", style="magenta")
    table.add_column("Confidence")
    table.add_column("Provenance")

    for e in evidence[:max_display]:
        sha = str(getattr(e, "sha256", getattr(e, "artifact_id", "?")))[:12]
        artifact_form = str(getattr(e, "artifact_form", getattr(e, "media_type", "evidence")))
        tier = str(getattr(e, "trust_tier", "?"))
        confidence = float(getattr(e, "confidence", 0.0))
        provenance = str(getattr(e, "provenance_grade", getattr(e, "provenance", "?")))
        conf_color = "green" if confidence >= 0.8 else "yellow" if confidence >= 0.5 else "red"
        table.add_row(sha, artifact_form, tier, f"[{conf_color}]{confidence:.0%}[/{conf_color}]", provenance)

    return str(table)


def display_evidence_panel(
    use_live_data: bool = True,
    max_display: int = 8,
) -> None:
    """Display the evidence chain panel on the console.

    Args:
        use_live_data: Whether to attempt live data fetch.
        max_display: Maximum evidence items to show.
    """
    panel = render_evidence_panel(use_live_data=use_live_data, max_display=max_display)
    if panel:
        if _RICH:
            Console().print(panel)
            Console().print()
        else:
            print(panel)


# ── Evidence Report Export ────────────────────────────────────────────────────


def export_evidence_report(
    output_format: str = "markdown",
    output_path: str | None = None,
    use_live_data: bool = True,
) -> str:
    """Export an evidence report in the specified format.

    Args:
        output_format: One of 'markdown', 'json', or 'text'.
        output_path: Optional file path to write the report. If None, returns as string.
        use_live_data: Whether to attempt live data for evidence sources.

    Returns:
        The report content as a string.

    Raises:
        ValueError: If output_format is unsupported.
    """
    # ── Collect all evidence data ──────────────────────────────────────────
    dashboard = build_dashboard_data(use_live_data=use_live_data)
    lifecycle = _get_lifecycle()
    missions_data: list[dict[str, Any]] = []
    if lifecycle and use_live_data:
        try:
            missions_data = lifecycle.list_missions() or []
        except Exception:
            pass

    now = _now_iso()

    if output_format == "json":
        report_data = {
            "report_id": hashlib.sha256(f"evidence-report-{now}".encode()).hexdigest()[:16],
            "generated_at": now,
            "dashboard": dashboard,
            "missions": missions_data,
            "source_mode": "live" if use_live_data else "simulated",
        }
        content = json.dumps(report_data, indent=2, ensure_ascii=False)

    elif output_format in ("markdown", "text"):
        lines: list[str] = []
        lines.append(f"# HLF Evidence Report")
        lines.append(f"")
        lines.append(f"**Generated:** {now}")
        lines.append(f"**Source Mode:** {'Live' if use_live_data else 'Simulated'}")
        lines.append(f"**Dashboard ID:** {dashboard['dashboard_id']}")
        lines.append(f"**Overall Status:** {dashboard['overall_status'].upper()}")
        lines.append(f"")

        # Verification summary
        ver = dashboard["verification"]
        ver_s = ver.get("summary", {})
        lines.append(f"## Verification Gate")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Source | {ver.get('source', 'unknown')} |")
        lines.append(f"| Total Programs | {ver_s.get('total_programs', 'N/A')} |")
        lines.append(f"| Proceed | {ver_s.get('proceed', 'N/A')} |")
        lines.append(f"| Warn | {ver_s.get('warn', 'N/A')} |")
        lines.append(f"| Block | {ver_s.get('block', 'N/A')} |")
        lines.append(f"| Pass Rate | {ver_s.get('pass_rate_pct', 'N/A')}% |")
        lines.append(f"")

        # Constitutional
        const = dashboard["constitutional"]
        const_s = const.get("summary", {})
        lines.append(f"## Constitutional Violations")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Source | {const.get('source', 'unknown')} |")
        lines.append(f"| Total | {const_s.get('total_violations', 'N/A')} |")
        lines.append(f"| High | {const_s.get('high_severity', 'N/A')} |")
        lines.append(f"| Medium | {const_s.get('medium_severity', 'N/A')} |")
        lines.append(f"| Low | {const_s.get('low_severity', 'N/A')} |")
        lines.append(f"| Blocked | {const_s.get('blocked_count', 'N/A')} |")
        lines.append(f"")

        # Manifest
        man = dashboard["manifest_audit"]
        man_s = man.get("summary", {})
        lines.append(f"## Manifest Audit")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Source | {man.get('source', 'unknown')} |")
        lines.append(f"| Total | {man_s.get('total_deployments', 'N/A')} |")
        lines.append(f"| Approved | {man_s.get('approved', 'N/A')} |")
        lines.append(f"| Rejected | {man_s.get('rejected', 'N/A')} |")
        lines.append(f"| Rate | {man_s.get('approval_rate_pct', 'N/A')}% |")
        lines.append(f"")

        # Missions
        if missions_data:
            lines.append(f"## Missions ({len(missions_data)} total)")
            lines.append(f"")
            lines.append(f"| ID | Title | Phase | Verdict | Sealed |")
            lines.append(f"|----|-------|-------|---------|--------|")
            for m in missions_data[:20]:
                mid = str(m.get("mission_id", ""))[:12]
                title = str(m.get("title", "unnamed"))[:40]
                phase = str(m.get("current_phase", "unknown"))
                verdict = str(m.get("verdict", "pending"))
                sealed = "✓" if m.get("sealed") else "○"
                lines.append(f"| {mid} | {title} | {phase} | {verdict} | {sealed} |")
            lines.append(f"")

        # Pillar score
        pillar = dashboard.get("pillar_score", {})
        lines.append(f"## Pillar Score")
        lines.append(f"")
        lines.append(f"- **Pillar:** {pillar.get('pillar', 'N/A')}")
        lines.append(f"- **Score:** {pillar.get('score_pct', 'N/A')}%")
        lines.append(f"- **Target:** {pillar.get('target_pct', 'N/A')}%")
        lines.append(f"- **Status:** {pillar.get('status', 'N/A')}")
        lines.append(f"")

        content = "\n".join(lines)

    else:
        raise ValueError(f"Unsupported output format: {output_format!r}. Use 'markdown', 'json', or 'text'.")

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    return content


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


# ── Feedback Loop & Fatigue Gauge ──────────────────────────────────────────────


def compute_feedback_metrics(
    feedback_collector: Any | None = None,
) -> dict[str, Any]:
    """Compute operator feedback loop metrics from a FeedbackCollector.

    If no collector is provided, returns a default/empty metrics dict suitable
    for embedding in a dashboard.

    Args:
        feedback_collector: A FeedbackCollector instance, or None for defaults.

    Returns:
        Dictionary with feedback loop metrics (response time, MTTR, SNR, etc.).
    """
    if feedback_collector is None:
        return {
            "total_alerts": 0,
            "acknowledged": 0,
            "resolved": 0,
            "dismissed": 0,
            "escalated": 0,
            "orphaned": 0,
            "mttr_seconds": 0.0,
            "mtta_seconds": 0.0,
            "resolution_rate_pct": 0.0,
            "false_positive_rate_pct": 0.0,
            "escalation_rate_pct": 0.0,
            "deduplication_rate_pct": 0.0,
            "snooze_repeat_rate_pct": 0.0,
            "signal_to_noise_ratio": 0.0,
            "alert_volume_trend_slope": 0.0,
            "operator_saturation_score": 0.0,
            "sla_window_seconds": 0.0,
        }

    from hlf_mcp.gallery.telemetry import FeedbackStatistics
    stats = feedback_collector.get_statistics()
    return stats.to_dict()


def render_fatigue_gauge(
    saturation_score: float,
    signal_to_noise: float,
    mttr_seconds: float,
    false_positive_rate: float,
    alert_volume_trend: float,
    title: str = "Operator Alert Fatigue Gauge",
) -> str | None:
    """Render an alert fatigue gauge panel using Rich.

    Args:
        saturation_score: Composite saturation 0-100.
        signal_to_noise: Signal-to-noise ratio (0-1 scale).
        mttr_seconds: Mean time to resolve in seconds.
        false_positive_rate: False positive rate percentage.
        alert_volume_trend: Daily alert volume trend slope.
        title: Panel title.

    Returns:
        Rich-rendered panel string, or None if Rich is unavailable.
    """
    if not _RICH:
        return None

    # Saturation color: green < 30, yellow < 60, red >= 60
    if saturation_score < 30:
        sat_color = "green"
        sat_icon = "🟢"
        sat_label = "LOW SATURATION"
    elif saturation_score < 60:
        sat_color = "yellow"
        sat_icon = "🟡"
        sat_label = "MODERATE SATURATION"
    else:
        sat_color = "red"
        sat_icon = "🔴"
        sat_label = "HIGH SATURATION"

    # SNR color
    if signal_to_noise >= 0.7:
        snr_color = "green"
    elif signal_to_noise >= 0.4:
        snr_color = "yellow"
    else:
        snr_color = "red"

    # MTTR color
    if mttr_seconds <= 120:
        mttr_color = "green"
    elif mttr_seconds <= 300:
        mttr_color = "yellow"
    else:
        mttr_color = "red"

    # FP rate color
    if false_positive_rate <= 10:
        fp_color = "green"
    elif false_positive_rate <= 30:
        fp_color = "yellow"
    else:
        fp_color = "red"

    # Volume trend color
    if alert_volume_trend <= 1:
        vol_color = "green"
    elif alert_volume_trend <= 3:
        vol_color = "yellow"
    else:
        vol_color = "red"

    # Build saturation bar
    bar_filled = max(1, int(saturation_score / 10))
    bar = f"[{sat_color}]{'█' * bar_filled}{'░' * (10 - bar_filled)}[/{sat_color}]"

    gauge_table = Table(title=title, box=box.SIMPLE, expand=True)
    gauge_table.add_column("Metric", style="cyan")
    gauge_table.add_column("Value", style="white")
    gauge_table.add_column("Status")

    gauge_table.add_row(
        "Saturation Score",
        f"[bold {sat_color}]{sat_icon} {saturation_score:.1f}/100[/bold {sat_color}]",
        f"[{sat_color}]{sat_label}[/{sat_color}]",
    )
    gauge_table.add_row("Saturation Bar", bar, "")
    gauge_table.add_row(
        "Signal-to-Noise",
        f"{signal_to_noise:.3f}",
        f"[{snr_color}]{'GOOD' if signal_to_noise >= 0.7 else 'FAIR' if signal_to_noise >= 0.4 else 'POOR'}[/{snr_color}]",
    )
    gauge_table.add_row(
        "MTTR",
        f"{mttr_seconds:.1f}s",
        f"[{mttr_color}]{'FAST' if mttr_seconds <= 120 else 'OK' if mttr_seconds <= 300 else 'SLOW'}[/{mttr_color}]",
    )
    gauge_table.add_row(
        "False Positive Rate",
        f"{false_positive_rate:.1f}%",
        f"[{fp_color}]{'LOW' if false_positive_rate <= 10 else 'MODERATE' if false_positive_rate <= 30 else 'HIGH'}[/{fp_color}]",
    )
    gauge_table.add_row(
        "Volume Trend",
        f"{alert_volume_trend:+.3f} alerts/day",
        f"[{vol_color}]{'STABLE' if alert_volume_trend <= 1 else 'RISING' if alert_volume_trend <= 3 else 'SPIKING'}[/{vol_color}]",
    )

    return gauge_table


def display_fatigue_gauge(
    saturation_score: float,
    signal_to_noise: float = 0.0,
    mttr_seconds: float = 0.0,
    false_positive_rate: float = 0.0,
    alert_volume_trend: float = 0.0,
) -> None:
    """Display the alert fatigue gauge on the console.

    Args:
        saturation_score: Operator saturation score 0-100.
        signal_to_noise: Signal-to-noise ratio.
        mttr_seconds: Mean time to resolve.
        false_positive_rate: False positive rate percentage.
        alert_volume_trend: Daily alert volume slope.
    """
    if not _RICH:
        print(f"Operator Saturation: {saturation_score:.1f}/100")
        print(f"Signal-to-Noise: {signal_to_noise:.3f}")
        print(f"MTTR: {mttr_seconds:.1f}s")
        print(f"False Positives: {false_positive_rate:.1f}%")
        return

    gauge = render_fatigue_gauge(
        saturation_score, signal_to_noise,
        mttr_seconds, false_positive_rate, alert_volume_trend,
    )
    if gauge is not None:
        console = Console()
        console.print(gauge)
        console.print()


def build_dashboard_with_feedback(
    swarm_observer: Any | None = None,
    feedback_collector: Any | None = None,
    record: bool = True,
) -> dict[str, Any]:
    """Build dashboard data including trend history, alert thresholds, and
    operator feedback loop metrics.

    Args:
        swarm_observer: Optional live SwarmObserver instance.
        feedback_collector: Optional FeedbackCollector for fatigue metrics.
        record: If True, record this snapshot into the trend buffer.

    Returns:
        Dashboard dictionary with trend_history, components_with_alerts,
        and feedback_metrics.
    """
    dashboard = build_dashboard_with_trend(swarm_observer, record=record)
    feedback_metrics = compute_feedback_metrics(feedback_collector)
    dashboard["feedback_metrics"] = feedback_metrics

    # Update pillar score to reflect new feedback components
    pillar = dashboard["pillar_score"]
    fb = feedback_metrics

    # Add feedback-specific component scores
    components = dict(pillar.get("components", {}))
    components["feedback_response_time"] = {
        "status": "active",
        "score_pct": max(0, 100 - min(100, fb.get("mttr_seconds", 0) / 3)),
    }
    components["feedback_signal_to_noise"] = {
        "status": "active",
        "score_pct": fb.get("signal_to_noise_ratio", 0) * 100,
    }
    components["feedback_saturation"] = {
        "status": "active",
        "score_pct": max(0, 100 - fb.get("operator_saturation_score", 0)),
    }
    components["feedback_false_positive"] = {
        "status": "active",
        "score_pct": max(0, 100 - fb.get("false_positive_rate_pct", 0)),
    }
    pillar["components"] = components

    # Recompute overall pillar score with feedback components
    all_scores = [info.get("score_pct", 0) for info in components.values()]
    if all_scores:
        new_overall = round(sum(all_scores) / len(all_scores), 1)
        pillar["score_pct"] = new_overall
        pillar["overall_alert"] = compute_alert_threshold(new_overall)
        pillar["overall_alert_color"] = compute_alert_color(new_overall)

    dashboard["pillar_score"] = pillar
    return dashboard


def demo(
    use_live_data: bool = True,
) -> None:
    """Run the operator dashboard demonstration.

    Collects all dashboard metrics, displays them with rich formatting,
    generates the dashboard JSON file, records trend snapshot, displays
    alert thresholds, mission panel, dream findings, evidence panel,
    and shows the fatigue gauge.

    Args:
        use_live_data: When True, attempt live data from InstinctLifecycle.
                       When False, use simulated data for all panels.
    """
    dashboard = build_dashboard_with_trend(record=True, swarm_observer=None)
    display_dashboard(dashboard)
    display_dashboard_with_alerts(dashboard)

    # ── New operator panels ────────────────────────────────────────────────
    display_mission_panel(use_live_data=use_live_data)
    display_dream_findings_panel(use_live_data=use_live_data)
    display_evidence_panel(use_live_data=use_live_data)

    # Display fatigue gauge with demo data
    from hlf_mcp.gallery.telemetry import FeedbackCollector, create_default_feedback_collector
    fb_collector = create_default_feedback_collector()
    # Record some demo alerts with feedback
    import random
    for i in range(1, 9):
        alert_id = f"alert-demo-{i:03d}"
        fb_collector.record_alert(
            alert_id,
            alert_type=random.choice(["readiness", "violation", "manifest"]),
            severity=random.randint(20, 90),
        )
        time.sleep(0.01)
        fb_collector.acknowledge(alert_id, "demo-operator")
        if i % 3 != 0:
            time.sleep(0.01)
            fb_collector.resolve(alert_id, "demo-operator", "resolved during demo")
        if i == 7:
            fb_collector.dismiss(alert_id, "demo-operator", "false alarm")
        if i == 8:
            fb_collector.escalate(alert_id, "demo-operator", "sovereign")

    fb_metrics = compute_feedback_metrics(fb_collector)
    display_fatigue_gauge(
        saturation_score=fb_metrics["operator_saturation_score"],
        signal_to_noise=fb_metrics["signal_to_noise_ratio"],
        mttr_seconds=fb_metrics["mttr_seconds"],
        false_positive_rate=fb_metrics["false_positive_rate_pct"],
        alert_volume_trend=fb_metrics["alert_volume_trend_slope"],
    )

    # Generate the JSON data file
    json_output = generate_dashboard_json(swarm_observer=None)
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
