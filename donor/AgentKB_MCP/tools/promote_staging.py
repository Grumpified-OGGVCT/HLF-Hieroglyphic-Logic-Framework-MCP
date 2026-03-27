"""
Staging promotion tool.

Promotes validated entries from staging to production KB.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kb_parser import KBParser
from app.models.kb import KBEntry


console = Console()


def get_pending_entries(staging_path: Path, parser: KBParser) -> List[Tuple[Path, List[KBEntry]]]:
    """
    Get all pending entries from staging.
    
    Returns:
        List of (file_path, entries) tuples
    """
    results = []
    
    for file in staging_path.glob("*-pending.md"):
        entries = parser.parse_file(file)
        if entries:
            results.append((file, entries))
    
    return results


def show_diff(entry: KBEntry):
    """Show a diff-style view of an entry."""
    console.print(f"\n[bold cyan]+ {entry.id}[/bold cyan]")
    console.print(f"  Question: {entry.question[:100]}...")
    console.print(f"  Domain: {entry.domain}")
    console.print(f"  Version: {entry.software_version}")
    console.print(f"  Tier: {entry.tier}")
    console.print(f"  Sources: {len(entry.sources)}")


def promote_entry(
    entry: KBEntry,
    production_path: Path,
    parser: KBParser
) -> bool:
    """
    Promote a single entry to production.
    
    Args:
        entry: The entry to promote
        production_path: Path to production KB directory
        parser: KBParser instance
        
    Returns:
        True if promoted successfully
    """
    # Validate entry first
    is_valid, errors = parser.validate_entry(entry)
    
    if not is_valid:
        console.print(f"[red]Validation failed for {entry.id}:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        return False
    
    # Determine target file
    target_file = production_path / f"{entry.domain.lower()}.md"
    
    # Read existing content
    existing = ""
    if target_file.exists():
        existing = target_file.read_text(encoding="utf-8")
        if not existing.endswith("\n\n"):
            existing += "\n\n"
    
    # Check for duplicate IDs
    existing_entries = parser.parse_file(target_file) if target_file.exists() else []
    for existing_entry in existing_entries:
        if existing_entry.id == entry.id:
            console.print(f"[yellow]Entry {entry.id} already exists in production[/yellow]")
            return False
    
    # Append entry
    new_content = existing + entry.to_markdown()
    
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(new_content, encoding="utf-8")
    
    return True


@click.command()
@click.option(
    '--staging',
    '-s',
    default='./kb_staging',
    help='Path to staging directory'
)
@click.option(
    '--production',
    '-p',
    default='./kb_files',
    help='Path to production directory'
)
@click.option(
    '--yes',
    '-y',
    is_flag=True,
    help='Skip confirmation prompts'
)
@click.option(
    '--dry-run',
    '-n',
    is_flag=True,
    help='Show what would be promoted without making changes'
)
@click.option(
    '--entry-id',
    '-e',
    help='Promote only a specific entry by ID'
)
def main(staging: str, production: str, yes: bool, dry_run: bool, entry_id: str):
    """Promote staging entries to production KB."""
    
    parser = KBParser()
    staging_path = Path(staging)
    production_path = Path(production)
    
    if not staging_path.exists():
        console.print(f"[red]Error: Staging path not found: {staging_path}[/red]")
        sys.exit(1)
    
    # Get pending entries
    pending = get_pending_entries(staging_path, parser)
    
    if not pending:
        console.print("[yellow]No pending entries found in staging.[/yellow]")
        sys.exit(0)
    
    # Count entries
    total_entries = sum(len(entries) for _, entries in pending)
    
    console.print(f"\n[bold]Found {total_entries} entries in staging:[/bold]\n")
    
    # Show entries
    entries_to_promote = []
    
    for file_path, entries in pending:
        console.print(f"[dim]{file_path.name}:[/dim]")
        
        for entry in entries:
            if entry_id and entry.id != entry_id:
                continue
            
            show_diff(entry)
            entries_to_promote.append((file_path, entry))
    
    if not entries_to_promote:
        if entry_id:
            console.print(f"[yellow]Entry {entry_id} not found in staging.[/yellow]")
        sys.exit(0)
    
    # Dry run - just show and exit
    if dry_run:
        console.print(f"\n[yellow]Dry run - no changes made.[/yellow]")
        console.print(f"Would promote {len(entries_to_promote)} entries.")
        sys.exit(0)
    
    # Confirm
    if not yes:
        console.print()
        if not Confirm.ask(f"Promote {len(entries_to_promote)} entries to production?"):
            console.print("[yellow]Cancelled.[/yellow]")
            sys.exit(0)
    
    # Promote entries
    console.print()
    promoted = 0
    failed = 0
    
    for file_path, entry in entries_to_promote:
        console.print(f"Promoting {entry.id}...", end=" ")
        
        if promote_entry(entry, production_path, parser):
            console.print("[green]✓[/green]")
            promoted += 1
        else:
            console.print("[red]✗[/red]")
            failed += 1
    
    # Clean up staging files
    if promoted > 0:
        console.print(f"\n[bold]Cleaning up staging files...[/bold]")
        
        for file_path, entries in pending:
            # Get remaining entries (not promoted)
            promoted_ids = {e.id for _, e in entries_to_promote if promote_entry}
            remaining = [e for e in entries if e.id not in promoted_ids]
            
            if not remaining:
                # Remove empty staging file
                file_path.unlink()
                console.print(f"  Removed {file_path.name}")
            else:
                # Rewrite with remaining entries
                content = "\n\n".join(e.to_markdown() for e in remaining)
                file_path.write_text(content, encoding="utf-8")
                console.print(f"  Updated {file_path.name} ({len(remaining)} remaining)")
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Promoted: [green]{promoted}[/green]")
    console.print(f"  Failed: [red]{failed}[/red]")
    
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()

