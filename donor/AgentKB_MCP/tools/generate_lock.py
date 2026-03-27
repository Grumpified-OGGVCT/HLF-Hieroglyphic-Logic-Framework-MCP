"""
Lockfile generation tool.

Generates SHA-256 lockfiles for reproducible builds.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import click
from rich.console import Console

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kb_parser import KBParser


console = Console()


@click.command()
@click.option(
    '--kb',
    '-k',
    default='./kb_files',
    help='Path to KB files directory'
)
@click.option(
    '--out',
    '-o',
    default='./locks/lockfile.json',
    help='Output lockfile path'
)
@click.option(
    '--entries',
    '-e',
    help='Comma-separated list of specific entry IDs to lock'
)
@click.option(
    '--domain',
    '-d',
    help='Lock all entries from a specific domain'
)
def main(kb: str, out: str, entries: str, domain: str):
    """Generate a lockfile with SHA-256 hashes for KB entries."""
    
    parser = KBParser()
    kb_path = Path(kb)
    out_path = Path(out)
    
    if not kb_path.exists():
        console.print(f"[red]Error: KB path not found: {kb_path}[/red]")
        sys.exit(1)
    
    console.print(f"\n[bold]Generating lockfile from: {kb_path}[/bold]\n")
    
    # Parse all entries
    all_entries = parser.parse_all()
    
    if not all_entries:
        console.print("[yellow]No entries found in KB.[/yellow]")
        sys.exit(1)
    
    # Filter entries
    if entries:
        entry_ids = [e.strip() for e in entries.split(",")]
        all_entries = [e for e in all_entries if e.id in entry_ids]
    elif domain:
        all_entries = [e for e in all_entries if e.domain.lower() == domain.lower()]
    
    if not all_entries:
        console.print("[yellow]No matching entries found.[/yellow]")
        sys.exit(1)
    
    console.print(f"Locking {len(all_entries)} entries...")
    
    # Generate lockfile
    lockfile = {
        "lockfile_version": "1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "entries": {}
    }
    
    for entry in all_entries:
        lockfile["entries"][entry.id] = {
            "sha256": entry.sha256,
            "version": entry.software_version,
            "domain": entry.domain
        }
    
    # Write lockfile
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(lockfile, f, indent=2)
    
    console.print(f"\n[green]✓ Lockfile written to: {out_path}[/green]")
    console.print(f"  Entries locked: {len(lockfile['entries'])}")
    
    # Show sample
    sample = list(lockfile["entries"].items())[:3]
    console.print("\n[dim]Sample entries:[/dim]")
    for entry_id, info in sample:
        console.print(f"  {entry_id}: {info['sha256'][:16]}...")


if __name__ == "__main__":
    main()

