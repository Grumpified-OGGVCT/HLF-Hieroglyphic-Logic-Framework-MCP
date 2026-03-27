"""
Lockfile verification tool.

Verifies KB entries haven't drifted from locked hashes.
"""

import sys
import json
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kb_parser import KBParser


console = Console()


@click.command()
@click.option(
    '--lockfile',
    '-l',
    default='./locks/lockfile.json',
    help='Path to lockfile'
)
@click.option(
    '--kb',
    '-k',
    default='./kb_files',
    help='Path to KB files directory'
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Show all entries, not just mismatches'
)
def main(lockfile: str, kb: str, verbose: bool):
    """Verify KB entries haven't drifted from locked hashes."""
    
    parser = KBParser()
    lockfile_path = Path(lockfile)
    kb_path = Path(kb)
    
    if not lockfile_path.exists():
        console.print(f"[red]Error: Lockfile not found: {lockfile_path}[/red]")
        sys.exit(1)
    
    if not kb_path.exists():
        console.print(f"[red]Error: KB path not found: {kb_path}[/red]")
        sys.exit(1)
    
    # Load lockfile
    with open(lockfile_path, "r", encoding="utf-8") as f:
        lock_data = json.load(f)
    
    console.print(f"\n[bold]Verifying lockfile: {lockfile_path}[/bold]")
    console.print(f"  Version: {lock_data.get('lockfile_version', 'unknown')}")
    console.print(f"  Generated: {lock_data.get('generated_at', 'unknown')}")
    console.print(f"  Entries: {len(lock_data.get('entries', {}))}")
    console.print()
    
    # Verify each entry
    entries = lock_data.get("entries", {})
    
    matches = []
    mismatches = []
    missing = []
    
    for entry_id, expected in entries.items():
        expected_hash = expected.get("sha256") if isinstance(expected, dict) else expected
        
        entry = parser.get_entry_by_id(entry_id)
        
        if entry is None:
            missing.append(entry_id)
        elif entry.sha256 == expected_hash:
            matches.append(entry_id)
        else:
            mismatches.append((entry_id, expected_hash, entry.sha256))
    
    # Show results
    if verbose or mismatches or missing:
        table = Table(title="Verification Results")
        table.add_column("Entry ID", style="cyan")
        table.add_column("Status")
        table.add_column("Details", style="dim")
        
        if verbose:
            for entry_id in matches:
                table.add_row(entry_id, "[green]✓ Match[/green]", "")
        
        for entry_id in missing:
            table.add_row(entry_id, "[red]✗ Missing[/red]", "Entry not found in KB")
        
        for entry_id, expected, actual in mismatches:
            table.add_row(
                entry_id,
                "[red]✗ Mismatch[/red]",
                f"Expected: {expected[:16]}... Got: {actual[:16]}..."
            )
        
        if verbose or table.row_count > 0:
            console.print(table)
    
    # Summary
    total = len(entries)
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total: {total}")
    console.print(f"  Matches: [green]{len(matches)}[/green]")
    console.print(f"  Mismatches: [red]{len(mismatches)}[/red]")
    console.print(f"  Missing: [yellow]{len(missing)}[/yellow]")
    
    # Overall result
    if mismatches or missing:
        console.print(f"\n[red bold]✗ Verification FAILED[/red bold]")
        sys.exit(1)
    else:
        console.print(f"\n[green bold]✓ Verification PASSED[/green bold]")
        sys.exit(0)


if __name__ == "__main__":
    main()

