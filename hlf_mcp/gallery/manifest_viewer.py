"""
HLF Manifest Viewer — Displays capability manifests with effect categories.

Shows what capabilities a compiled program requires, its trust tier,
effect declarations with categories, and proof surfaces. Operators use
this surface to audit what permissions programs need before deployment.

Usage:
    python -m hlf_mcp.gallery.manifest_viewer
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


# ── Effect categories for display ────────────────────────────────────────────────

EFFECT_CATEGORIES: dict[str, str] = {
    "PURE": "Pure — No side effects, always deterministic",
    "READ": "Read — Access to external data sources",
    "WRITE": "Write — Modifies external state",
    "NETWORK": "Network — Network I/O operations",
    "FILE_IO": "File I/O — Filesystem access",
    "CRYPTO": "Crypto — Cryptographic operations",
    "AI_INFER": "AI Inference — Invokes ML models",
    "SYS_CALL": "System Call — Operating system interaction",
    "HUMAN_APPROVAL": "Human Approval — Requires human-in-the-loop",
    "AUDIT": "Audit — Generates audit trail entries",
}


def build_sample_manifest() -> dict[str, Any]:
    """Build a sample capability manifest for demonstration."""
    return {
        "program_id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "trust_tier": "hearth",
        "compiled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compiler_version": "v3",
        "effects": [
            {"name": "read_input", "category": "READ", "description": "Read input from stdin",
             "direction": "input", "deterministic": True},
            {"name": "write_output", "category": "WRITE", "description": "Write result to stdout",
             "direction": "output", "deterministic": True},
            {"name": "hash_data", "category": "CRYPTO", "description": "SHA-256 hashing",
             "direction": "internal", "deterministic": True},
            {"name": "audit_trail", "category": "AUDIT", "description": "Record audit entry",
             "direction": "output", "deterministic": False},
        ],
        "required_capabilities": ["READ", "WRITE", "CRYPTO", "AUDIT"],
        "input_contracts": [
            {"name": "input_text", "type": "string", "nullable": False, "min_length": 1, "max_length": 1024},
        ],
        "output_contracts": [
            {"name": "result_hash", "type": "string", "format": "hex", "length": 64},
            {"name": "audit_record", "type": "dict", "required_keys": ["hash", "timestamp", "source"]},
        ],
        "proof_surfaces": [
            {"name": "determinism_proof", "status": "proven", "description": "All paths deterministic"},
            {"name": "range_proof", "status": "runtime_checked", "description": "Input bounds verified at runtime"},
        ],
    }


def _category_color(category: str) -> str:
    """Map effect category to display color."""
    colors = {
        "PURE": "green",
        "READ": "blue",
        "WRITE": "yellow",
        "NETWORK": "yellow",
        "FILE_IO": "yellow",
        "CRYPTO": "magenta",
        "AI_INFER": "red",
        "SYS_CALL": "red",
        "HUMAN_APPROVAL": "orange1",
        "AUDIT": "cyan",
    }
    return colors.get(category, "white")


def display_manifest(manifest_data: dict[str, Any]) -> None:
    """Display a capability manifest with categorized effect visualization.

    Args:
        manifest_data: Dictionary with manifest fields (effects, capabilities, contracts).
    """
    if _RICH:
        console = Console()

        # ── Header ───────────────────────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]HLF Capability Manifest[/bold cyan]")
        console.print(f"  Program: [bold]{manifest_data.get('program_id', '?')[:16]}...[/bold]")
        console.print(f"  Tier: [magenta]{manifest_data.get('trust_tier', '?')}[/magenta]  |  "
                      f"Compiler: [dim]{manifest_data.get('compiler_version', '?')}[/dim]  |  "
                      f"Compiled: [dim]{manifest_data.get('compiled_at', '?')}[/dim]")
        console.print()

        # ── Required Capabilities ────────────────────────────────────────────
        caps = manifest_data.get("required_capabilities", [])
        cap_text = Text()
        for cap in caps:
            color = _category_color(cap)
            cap_text.append(f" [{color}]■ {cap}[/{color}] ")
        console.print(Panel(cap_text, title="Required Capabilities", border_style="blue"))

        # ── Effects Table ────────────────────────────────────────────────────
        effects = manifest_data.get("effects", [])
        table = Table(title="Effect Declarations", box=box.ROUNDED, show_lines=True)
        table.add_column("Effect", style="cyan")
        table.add_column("Category", style="magenta")
        table.add_column("Direction", style="dim")
        table.add_column("Deterministic")
        table.add_column("Description", style="white")

        for eff in effects:
            cat = eff.get("category", "?")
            color = _category_color(cat)
            det = "✓" if eff.get("deterministic") else "~"
            det_style = "green" if eff.get("deterministic") else "yellow"
            dir_icon = {"input": "←", "output": "→", "internal": "↻"}.get(eff.get("direction", ""), "?")
            table.add_row(
                eff.get("name", "?"),
                f"[{color}]{cat}[/{color}]",
                f"{dir_icon} {eff.get('direction', '?')}",
                f"[{det_style}]{det}[/{det_style}]",
                eff.get("description", "")[:60],
            )
        console.print(table)

        # ── Contracts ────────────────────────────────────────────────────────
        in_contracts = manifest_data.get("input_contracts", [])
        out_contracts = manifest_data.get("output_contracts", [])

        if in_contracts or out_contracts:
            contract_table = Table(title="I/O Contracts", box=box.ROUNDED)
            contract_table.add_column("Direction", style="cyan")
            contract_table.add_column("Name", style="white")
            contract_table.add_column("Constraints", style="dim")

            for c in in_contracts:
                constraints = []
                if c.get("nullable") is False:
                    constraints.append("non-null")
                if c.get("min_length"):
                    constraints.append(f"min_len={c['min_length']}")
                if c.get("max_length"):
                    constraints.append(f"max_len={c['max_length']}")
                contract_table.add_row(
                    "[blue]← INPUT[/blue]",
                    c.get("name", "?"),
                    ", ".join(constraints) if constraints else "-",
                )

            for c in out_contracts:
                constraints = []
                if c.get("format"):
                    constraints.append(f"fmt={c['format']}")
                if c.get("length"):
                    constraints.append(f"len={c['length']}")
                if c.get("required_keys"):
                    constraints.append(f"keys={c['required_keys']}")
                contract_table.add_row(
                    "[yellow]→ OUTPUT[/yellow]",
                    c.get("name", "?"),
                    ", ".join(constraints) if constraints else "-",
                )
            console.print(contract_table)

        # ── Proof Surfaces ───────────────────────────────────────────────────
        proofs = manifest_data.get("proof_surfaces", [])
        if proofs:
            proof_tree = Tree("[bold]Proof Surfaces[/bold]")
            for p in proofs:
                status = p.get("status", "?")
                color = "green" if status == "proven" else "yellow"
                icon = "✓" if status == "proven" else "~"
                proof_tree.add(f"[{color}]{icon} {p['name']}[/{color}] — {p.get('description', '')}")
            console.print()
            console.print(Panel(proof_tree, border_style="blue"))
        console.print()

    else:
        # ── Plain text fallback ──────────────────────────────────────────────
        print(f"\n{'='*70}")
        print(f"  HLF Capability Manifest")
        print(f"  Program: {manifest_data.get('program_id', '?')[:16]}...")
        print(f"  Tier: {manifest_data.get('trust_tier', '?')}  |  "
              f"Compiler: {manifest_data.get('compiler_version', '?')}")
        print(f"{'='*70}")

        caps = manifest_data.get("required_capabilities", [])
        print(f"\n  Required Capabilities: {', '.join(caps)}")

        effects = manifest_data.get("effects", [])
        print(f"\n  Effect Declarations ({len(effects)}):")
        print(f"  {'Effect':<20} {'Category':<15} {'Dir':>4} {'Det':>4}  Description")
        print(f"  {'-'*20} {'-'*15} {'-'*4} {'-'*4}  {'-'*30}")
        for eff in effects:
            det = "YES" if eff.get("deterministic") else "~"
            dir_str = {"input": "IN", "output": "OUT", "internal": "INT"}.get(eff.get("direction", ""), "?")
            print(f"  {eff.get('name', '?')[:20]:<20} {eff.get('category', '?'):<15} {dir_str:>4} {det:>4}  {eff.get('description', '')[:30]}")

        in_contracts = manifest_data.get("input_contracts", [])
        out_contracts = manifest_data.get("output_contracts", [])
        if in_contracts:
            print(f"\n  Input Contracts:")
            for c in in_contracts:
                print(f"    ← {c.get('name', '?')} : {c.get('type', '?')} "
                      f"(nullable={c.get('nullable')}, len={c.get('min_length')}-{c.get('max_length')})")
        if out_contracts:
            print(f"\n  Output Contracts:")
            for c in out_contracts:
                print(f"    → {c.get('name', '?')} : {c.get('type', '?')} "
                      f"(fmt={c.get('format')}, len={c.get('length')})")

        proofs = manifest_data.get("proof_surfaces", [])
        if proofs:
            print(f"\n  Proof Surfaces:")
            for p in proofs:
                icon = "PASS" if p.get("status") == "proven" else "WARN"
                print(f"    [{icon}] {p.get('name', '?')} — {p.get('description', '')}")


def demo() -> None:
    """Run the manifest viewer demonstration.

    Builds sample manifest data and displays it with categorized effect visualization
    suitable for pre-deployment audit.
    """
    manifest = build_sample_manifest()
    display_manifest(manifest)


if __name__ == "__main__":
    demo()
