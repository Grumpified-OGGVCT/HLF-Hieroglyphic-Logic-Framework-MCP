"""
HLF Provenance Viewer — Visualizes provenance chains from two-channel execution.

Shows data lineage, trust scores, and cross-boundary degradation. Operators use
this surface to trace how data flows through the system and verify integrity
across trust boundaries.

Usage:
    python -m hlf_mcp.gallery.provenance_viewer
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
    from rich.tree import Tree
    from rich.text import Text
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False


def _trust_bar(trust: float, width: int = 30) -> str:
    """Generate a trust score bar."""
    filled = int(trust * width)
    if trust >= 0.8:
        color_char = "█"
    elif trust >= 0.5:
        color_char = "▓"
    else:
        color_char = "░"
    return color_char * filled + "·" * (width - filled)


def _trust_color(trust: float) -> str:
    """Map trust score to display color."""
    if trust >= 0.9:
        return "green"
    elif trust >= 0.7:
        return "yellow"
    elif trust >= 0.5:
        return "orange1"
    else:
        return "red"


def build_sample_provenance() -> dict[str, Any]:
    """Build sample provenance data for demonstration."""
    return {
        "channel": "data",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capabilities": ["READ", "WRITE", "CRYPTO"],
        "inputs": {
            "user_query": "compute sha256 of 'hello world'",
            "source_file": "input.txt",
        },
        "provenance": {
            "user_query": {
                "source": "user-input",
                "path": ["user", "agent.receive", "agent.parse", "agent.validate"],
                "trust": 1.0,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "parsed_intent": {
                "source": "agent.parse",
                "path": ["agent.receive", "agent.parse"],
                "trust": 0.95,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "file_content": {
                "source": "filesystem",
                "path": ["filesystem", "agent.read_file", "agent.sanitize", "agent.verify"],
                "trust": 0.85,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "computed_hash": {
                "source": "crypto.sha256",
                "path": ["agent.receive", "crypto.sha256"],
                "trust": 0.99,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "audit_record": {
                "source": "audit.recorder",
                "path": ["crypto.sha256", "audit.recorder", "ledger.append"],
                "trust": 0.92,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        },
        "execution_result": {
            "status": "success",
            "gate_decision": "PROCEED",
            "instruction_intact": True,
            "manifest_ok": True,
        },
    }


def display_provenance(prov_data: dict[str, Any]) -> None:
    """Display provenance chains with trust visualization.

    Args:
        prov_data: Dictionary with 'provenance' map of item_id -> chain info.
    """
    provenance = prov_data.get("provenance", {})
    exec_result = prov_data.get("execution_result", {})

    if _RICH:
        console = Console()

        # ── Header ───────────────────────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]HLF Provenance Chain Viewer[/bold cyan]")
        console.print(f"  Channel: [bold]{prov_data.get('channel', '?')}[/bold]  |  "
                      f"Created: [dim]{prov_data.get('created_at', '?')}[/dim]")
        caps = prov_data.get("capabilities", [])
        cap_text = " ".join(f"[dim]{c}[/dim]" for c in caps)
        console.print(f"  Capabilities: {cap_text}")
        console.print()

        # ── Execution Status ─────────────────────────────────────────────────
        status_color = "green" if exec_result.get("status") == "success" else "red"
        gate_color = "green" if exec_result.get("gate_decision") == "PROCEED" else "yellow"
        status_panel = Panel(
            f"  Execution: [bold {status_color}]{exec_result.get('status', '?')}[/bold {status_color}]  "
            f"| Gate: [bold {gate_color}]{exec_result.get('gate_decision', '?')}[/bold {gate_color}]  "
            f"| Instruction Intact: {'✓' if exec_result.get('instruction_intact') else '✗'}  "
            f"| Manifest OK: {'✓' if exec_result.get('manifest_ok', False) else '✗'}",
            title="Execution Result",
            border_style=status_color,
        )
        console.print(status_panel)

        # ── Provenance Tree ──────────────────────────────────────────────────
        prov_tree = Tree("[bold]Provenance Chains[/bold]")
        for item_id, chain in provenance.items():
            trust = chain.get("trust", 0.0)
            color = _trust_color(trust)
            bar = _trust_bar(trust, 25)
            path_short = " → ".join(chain.get("path", [])[-3:])
            branch = prov_tree.add(
                f"[cyan]{item_id}[/cyan]  [{color}]{bar}[/{color}]  [{color}]{trust:.0%}[/{color}]"
            )
            branch.add(f"[dim]Source: {chain.get('source', '?')}[/dim]")
            branch.add(f"[dim]Path: {path_short}[/dim]")

        console.print(prov_tree)
        console.print()

        # ── Trust Distribution ───────────────────────────────────────────────
        trust_values = [(item_id, c.get("trust", 0)) for item_id, c in provenance.items()]
        trust_values.sort(key=lambda x: x[1], reverse=True)

        table = Table(title="Trust Scores", box=box.SIMPLE)
        table.add_column("Data Item", style="cyan")
        table.add_column("Trust", style="white")
        table.add_column("Source", style="dim")
        table.add_column("Path Length", style="dim", justify="right")

        for item_id, trust in trust_values:
            color = _trust_color(trust)
            bar = _trust_bar(trust, 20)
            chain = provenance[item_id]
            table.add_row(
                item_id,
                f"[{color}]{bar}  {trust:.0%}[/{color}]",
                chain.get("source", "?"),
                str(len(chain.get("path", []))),
            )
        console.print(table)
        console.print()

    else:
        # ── Plain text fallback ──────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  HLF Provenance Chain Viewer")
        print(f"  Channel: {prov_data.get('channel', '?')}  |  "
              f"Created: {prov_data.get('created_at', '?')}")
        print(f"{'='*70}")
        print(f"\n  Execution: {exec_result.get('status', '?')}  |  "
              f"Gate: {exec_result.get('gate_decision', '?')}")
        print(f"  Instruction Intact: {exec_result.get('instruction_intact')}  |  "
              f"Manifest OK: {exec_result.get('manifest_ok')}")

        print(f"\n  Provenance Chains ({len(provenance)} items):")
        print(f"  {'Data Item':<20} {'Trust':>8}  {'Source':<20}  Path")
        print(f"  {'-'*20} {'-'*8}  {'-'*20}  {'-'*30}")
        for item_id, chain in provenance.items():
            trust = chain.get("trust", 0)
            bar = _trust_bar(trust, 10)
            path_short = " → ".join(chain.get("path", [])[-3:])
            print(f"  {item_id[:20]:<20} {bar} {trust:>3.0%}  {chain.get('source', '?')[:20]:<20}  {path_short}")

        trust_values = [(item_id, c.get("trust", 0)) for item_id, c in provenance.items()]
        trust_values.sort(key=lambda x: x[1])
        print(f"\n  Trust Score Summary:")
        print(f"  Min: {trust_values[0][1]:.0%}  |  Max: {trust_values[-1][1]:.0%}  |  "
              f"Avg: {sum(v[1] for v in trust_values) / len(trust_values):.0%}")


def _build_live_provenance(ctx: object) -> dict[str, Any]:
    """Build provenance data from live audit chain entries."""
    entries: list[dict[str, Any]] = []
    try:
        if hasattr(ctx, "audit_chain"):
            entries = ctx.audit_chain.iter_entries(limit=100)
    except Exception:
        pass
    if not entries:
        try:
            if hasattr(ctx, "audit_chain"):
                entries = ctx.audit_chain.recent(limit=100)
        except Exception:
            pass

    provenance: dict[str, dict[str, Any]] = {}
    for entry in entries:
        tid = str(entry.get("trace_id") or id(entry))
        trust = 1.0 - abs(float(entry.get("anomaly_score", 0.0)))
        provenance[tid] = {
            "source": str(entry.get("action", "audit")),
            "path": ["audit.recorder", "ledger.append"],
            "trust": max(0.0, min(1.0, trust)),
            "timestamp": str(entry.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ"))),
        }

    return {
        "channel": "audit",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capabilities": sorted(set(
            str(e.get("action", "READ")) for e in entries
        )) if entries else ["AUDIT"],
        "inputs": {},
        "provenance": provenance,
        "execution_result": {
            "status": "success" if entries else "empty",
            "gate_decision": "PROCEED",
            "instruction_intact": True,
            "manifest_ok": True,
        },
        "source": "live",
    }


def live(ctx: object) -> dict[str, Any]:
    """Return live provenance data from the audit chain (no demo fallback).

    Args:
        ctx: ServerContext with audit_chain attribute.

    Returns:
        Provenance dict suitable for display_provenance(), with ``source`` = ``"live"``.
    """
    return _build_live_provenance(ctx)


def demo(ctx: object | None = None) -> None:
    """Run the provenance viewer demonstration.

    When *ctx* is a ServerContext, queries the live audit chain.
    When *ctx* is None (backward compatible), uses hardcoded sample data
    tagged with ``"source": "demo"``.

    Args:
        ctx: Optional ServerContext for live provenance queries.
    """
    if ctx is not None:
        try:
            prov_data = _build_live_provenance(ctx)
            if prov_data.get("provenance"):
                display_provenance(prov_data)
                return
        except Exception:
            pass
    prov_data = build_sample_provenance()
    prov_data["source"] = "demo"
    display_provenance(prov_data)


if __name__ == "__main__":
    try:
        from hlf_mcp.server_context import build_server_context
        ctx = build_server_context()
    except Exception:
        ctx = None
    demo(ctx)
