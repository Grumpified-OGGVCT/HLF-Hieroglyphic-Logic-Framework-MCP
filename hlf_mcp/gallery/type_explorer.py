"""
HLF Type Explorer — Interactive demonstration of HLF compilation and verification.

Write HLF types, see compiled output, run the verifier, and observe the gate decision.
This is the primary legibility surface for understanding how HLF programs flow
through the compiler→verifier→gate pipeline.

Usage:
    python -m hlf_mcp.gallery.type_explorer
"""

from __future__ import annotations

import json
import sys
import textwrap
from typing import Any

# ── Windows console encoding fix ────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Rich support (optional) ──────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.text import Text
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False


# ── Sample HLF programs for demonstration ────────────────────────────────────────

SAMPLE_PROGRAMS: dict[str, str] = {
    "system_health": textwrap.dedent("""\
        # HLF v3 — System Health Check
        [HLF-v3]
        Δ analyze /config/settings.json
          Ж [CONSTRAINT] tier="hearth"
          Ж [CONSTRAINT] gas_limit=20
          Ж [EXPECT] config_valid
          ∇ [PARAM] summary="all systems operational"
          ∇ [RESULT] message="System health check passed — all systems operational"
        Ω
    """).strip(),
    "hello_world": textwrap.dedent("""\
        # HLF v3 — Hello World
        [HLF-v3]
        Δ [INTENT] goal="hello_world"
          Ж [ASSERT] status="ok"
          ∇ [RESULT] message="Hello, World!"
        Ω
    """).strip(),
    "security_audit": textwrap.dedent("""\
        # HLF v3 — Security Audit
        [HLF-v3]
        Δ audit_log /var/log/audit.log
          Ж [CONSTRAINT] tier="hearth"
          Ж [EXPECT] audit_complete
          Ж [EXPECT] hash_verified
          ∇ [RESULT] audited=true
          ∇ [PARAM] source="/var/log/audit.log"
        Ω
    """).strip(),
    "routing": textwrap.dedent("""\
        # HLF v3 — Real-Time Resource Mediation (MoMA Router)
        [HLF-v3]
        ⌘ [ROUTE] strategy="auto" tier="hearth"
          ∇ [PARAM] temperature=0.0
          Ж [VOTE] confirmation="required"
        Ω
    """).strip(),
    "decision_matrix": textwrap.dedent("""\
        # HLF v3 — Decision Matrix
        [HLF-v3]
        Δ decide /input/action_request.json
          Ж [CONSTRAINT] tier="hearth"
          Ж [VALIDATE] input_count=3
          Ж [EXPECT] valid_range
          ∇ [PARAM] priority="high"
          ∇ [PARAM] retries=3
          ∇ [RESULT] action="approved"
        Ω
    """).strip(),
    "delegation": textwrap.dedent("""\
        # HLF v3 — Content Delegation
        [HLF-v3]
        Δ delegate /tasks/content_review.json
          Ж [CONSTRAINT] tier="sovereign"
          Ж [EXPECT] review_complete
          Ж [EXPECT] quality_checked
          ∇ [PARAM] assigned_to="agent-42"
          ∇ [RESULT] delegated=true
        Ω
    """).strip(),
}


def _rich_console() -> Any:
    """Create a Rich console or fall back to None."""
    if _RICH:
        return Console()
    return None


def _print_header(title: str) -> None:
    """Print a section header."""
    if _RICH:
        console = Console()
        console.print()
        console.rule(f"[bold cyan]{title}[/bold cyan]")
    else:
        print(f"\n{'=' * 70}")
        print(f"  {title}")
        print(f"{'=' * 70}")


def _display_gate_decision(decision: str) -> None:
    """Display the verification gate decision with color coding."""
    if _RICH:
        console = Console()
        color = "green" if decision == "PROCEED" else "yellow" if decision == "WARN" else "red"
        panel = Panel(
            f"[bold {color}]{decision}[/bold {color}]",
            title="Gate Decision",
            border_style=color,
        )
        console.print(panel)
    else:
        icon = "PASS" if decision == "PROCEED" else "WARN" if decision == "WARN" else "BLOCK"
        print(f"\n  Gate Decision: [{icon}] {decision}")


def _display_compilation_result(entry: dict[str, Any]) -> None:
    """Display a compilation result."""
    if _RICH:
        console = Console()
        table = Table(title="Compilation Result", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Status", "OK" if not entry.get("errors") else f"Errors: {entry['errors']}")
        table.add_row("Version", entry.get("version", "?"))
        table.add_row("Node Count", str(entry.get("node_count", 0)))
        table.add_row("Gas Estimate", f"{entry.get('gas_estimate', 0):,}")
        table.add_row("Align Violations", str(len(entry.get("align_violations", []))))
        if entry.get("errors"):
            for err in entry["errors"]:
                table.add_row("Error", f"[red]{err}[/red]", style="red")
        console.print(table)

        if entry.get("ast"):
            ast_text = json.dumps(entry["ast"], indent=2, default=str)
            if len(ast_text) > 2000:
                ast_text = ast_text[:2000] + "\n... (truncated)"
            syntax = Syntax(ast_text, "json", theme="monokai", word_wrap=True)
            panel = Panel(syntax, title="AST Output", border_style="blue")
            console.print(panel)
    else:
        print(f"\n  Compilation: {'OK' if not entry.get('errors') else 'FAILED'}")
        print(f"  Version: {entry.get('version', '?')}")
        print(f"  Nodes: {entry.get('node_count', 0)}")
        print(f"  Gas Estimate: {entry.get('gas_estimate', 0):,}")
        print(f"  Align Violations: {len(entry.get('align_violations', []))}")
        if entry.get("errors"):
            for err in entry["errors"]:
                print(f"  ERROR: {err}")
        if entry.get("ast"):
            ast_text = json.dumps(entry["ast"], indent=2, default=str)
            if len(ast_text) > 1000:
                ast_text = ast_text[:1000] + "\n... (truncated)"
            print(f"\n  AST Output:\n{ast_text}")


def _display_verification(report: Any) -> None:
    """Display a verification report."""
    # report is a VerificationReport dataclass or dict
    results = getattr(report, "results", []) if hasattr(report, "results") else report.get("results", [])

    if _RICH:
        console = Console()
        table = Table(title="Verification Results", box=box.ROUNDED)
        table.add_column("Property", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Kind", style="magenta")
        table.add_column("Message", style="white")
        table.add_column("Time", style="dim")

        status_styles = {
            "PROVEN": "green",
            "RUNTIME_CHECKED": "yellow",
            "COUNTEREXAMPLE": "red",
            "UNKNOWN": "grey",
            "SKIPPED": "dim",
            "ERROR": "red",
        }

        for r in results:
            status = getattr(r, "status", None)
            status_str = status.value if hasattr(status, "value") else str(status)
            kind = getattr(r, "kind", None)
            kind_str = kind.value if hasattr(kind, "value") else str(kind) if kind else "-"
            msg = getattr(r, "message", "")
            dur = getattr(r, "duration_ms", 0)
            style = status_styles.get(status_str, "white")
            table.add_row(
                getattr(r, "property_name", "?"),
                f"[{style}]{status_str}[/{style}]",
                kind_str,
                str(msg)[:60],
                f"{dur:.1f}ms",
            )
        console.print(table)

        proven = sum(1 for r in results if getattr(r, "status", None) and
                     getattr(r.status, "value", str(r.status)) == "PROVEN")
        failed = sum(1 for r in results if getattr(r, "status", None) and
                     getattr(r.status, "value", str(r.status)) in ("COUNTEREXAMPLE", "ERROR"))
        blocked = getattr(report, "blocked_count", 0) if hasattr(report, "blocked_count") else 0
        summary = (
            f"[green]{proven} proven[/green]  "
            f"[yellow]{len(results) - proven - failed} checked[/yellow]  "
            f"[red]{failed} failed[/red]  "
            f"[red]{blocked} blocked[/red]"
        )
        console.print(Panel(summary, title="Summary", border_style="blue"))
    else:
        print(f"\n  Verification Results ({len(results)} checks):")
        print(f"  {'Property':<30} {'Status':<20} {'Kind':<20} {'Time':>8}")
        print(f"  {'-'*30} {'-'*20} {'-'*20} {'-'*8}")
        for r in results:
            status = getattr(r, "status", None)
            status_str = status.value if hasattr(status, "value") else str(status)
            kind = getattr(r, "kind", None)
            kind_str = kind.value if hasattr(kind, "value") else str(kind) if kind else "-"
            dur = getattr(r, "duration_ms", 0)
            print(f"  {getattr(r, 'property_name', '?'):<30} {status_str:<20} {kind_str:<20} {dur:>6.1f}ms")
        proven = sum(1 for r in results if getattr(r, "status", None) and
                     getattr(r.status, "value", str(r.status)) == "PROVEN")
        failed = sum(1 for r in results if getattr(r, "status", None) and
                     getattr(r.status, "value", str(r.status)) in ("COUNTEREXAMPLE", "ERROR"))
        blocked = getattr(report, "blocked_count", 0) if hasattr(report, "blocked_count") else 0
        print(f"\n  Summary: {proven} proven, {len(results) - proven - failed} checked, {failed} failed, {blocked} blocked")


def _display_source(source: str, name: str) -> None:
    """Display the HLF source code."""
    if _RICH:
        console = Console()
        syntax = Syntax(source, "c", theme="monokai", line_numbers=True, word_wrap=True)
        panel = Panel(syntax, title=f"Source: {name}", border_style="green")
        console.print(panel)
    else:
        print(f"\n  Source ({name}):")
        print(f"  {'-'*50}")
        for i, line in enumerate(source.splitlines(), 1):
            print(f"  {i:>3} | {line}")
        print(f"  {'-'*50}")


def demo() -> None:
    """Run the interactive type explorer demonstration.

    Compiles several sample HLF programs through the full compiler→verifier→gate
    pipeline and displays results with rich formatting.
    """
    from hlf_mcp.hlf.compiler import HLFCompiler, CompileError
    from hlf_mcp.hlf.formal_verifier import FormalVerifier

    compiler = HLFCompiler()
    verifier = FormalVerifier()

    _print_header("HLF Type Explorer — Compiler → Verifier → Gate Pipeline")

    for name, source in SAMPLE_PROGRAMS.items():
        _display_source(source, name)

        # ── Compile ──────────────────────────────────────────────────────────
        try:
            compile_result = compiler.compile(source)
        except CompileError as exc:
            if _RICH:
                Console().print(f"[red]Compile Error: {exc}[/red]")
            else:
                print(f"  Compile Error: {exc}")
            continue

        _display_compilation_result(compile_result)

        # ── Verify ───────────────────────────────────────────────────────────
        ast = compile_result.get("ast", {})
        if ast:
            try:
                report, gate_decision = verifier.verify(compile_result, trust_tier="hearth")
                _display_verification(report)
                _display_gate_decision(gate_decision)
            except Exception as exc:
                if _RICH:
                    Console().print(f"[yellow]Verification skipped: {exc}[/yellow]")
                else:
                    print(f"  Verification skipped: {exc}")

    # ── Summary ─────────────────────────────────────────────────────────────
    _print_header("Pipeline Summary")
    total = len(SAMPLE_PROGRAMS)
    if _RICH:
        console = Console()
        grid = Table.grid()
        grid.add_column()
        grid.add_column(style="green")
        grid.add_row("Programs compiled: ", str(total))
        grid.add_row("Verification gate: ", "hearth (strict)")
        grid.add_row("Compiler version: ", "v3 (LALR)")
        console.print(Panel(grid, title="Session Stats", border_style="cyan"))
    else:
        print(f"\n  Programs compiled: {total}")
        print(f"  Verification gate: hearth (strict)")
        print(f"  Compiler version: v3 (LALR)")


if __name__ == "__main__":
    demo()
