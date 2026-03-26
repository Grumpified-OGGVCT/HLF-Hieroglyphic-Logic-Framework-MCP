"""
KB validation tool.

Validates KB files against the canonical template.
"""

import sys
from pathlib import Path
from typing import List, Tuple
import click
from rich.console import Console
from rich.table import Table

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.kb_parser import KBParser
from app.models.kb import KBEntry


console = Console()


def validate_file(file_path: Path, parser: KBParser) -> Tuple[int, int, List[str]]:
    """
    Validate a single KB file.
    
    Args:
        file_path: Path to the KB file
        parser: KBParser instance
        
    Returns:
        Tuple of (valid_count, invalid_count, list of errors)
    """
    entries = parser.parse_file(file_path)
    
    valid = 0
    invalid = 0
    errors = []
    
    for entry in entries:
        is_valid, entry_errors = parser.validate_entry(entry)
        
        if is_valid:
            valid += 1
        else:
            invalid += 1
            for error in entry_errors:
                errors.append(f"{entry.id or 'Unknown ID'}: {error}")
    
    return valid, invalid, errors


@click.command()
@click.option(
    '--path',
    '-p',
    default='./kb_files',
    help='Path to KB files directory'
)
@click.option(
    '--staging',
    '-s',
    is_flag=True,
    help='Also validate staging files'
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Show detailed validation results'
)
def main(path: str, staging: bool, verbose: bool):
    """Validate KB files against the canonical template."""
    
    parser = KBParser()
    kb_path = Path(path)
    
    if not kb_path.exists():
        console.print(f"[red]Error: Path not found: {kb_path}[/red]")
        sys.exit(1)
    
    console.print(f"\n[bold]Validating KB files in: {kb_path}[/bold]\n")
    
    # Find all MD files
    files = list(kb_path.glob("*.md"))
    
    if staging:
        staging_path = Path("./kb_staging")
        if staging_path.exists():
            files.extend(staging_path.glob("*-pending.md"))
    
    if not files:
        console.print("[yellow]No KB files found.[/yellow]")
        sys.exit(0)
    
    # Create results table
    table = Table(title="Validation Results")
    table.add_column("File", style="cyan")
    table.add_column("Valid", style="green")
    table.add_column("Invalid", style="red")
    table.add_column("Status")
    
    total_valid = 0
    total_invalid = 0
    all_errors = []
    
    for file in files:
        valid, invalid, errors = validate_file(file, parser)
        
        total_valid += valid
        total_invalid += invalid
        all_errors.extend([(file.name, e) for e in errors])
        
        status = "[green]✓ PASS[/green]" if invalid == 0 else "[red]✗ FAIL[/red]"
        table.add_row(file.name, str(valid), str(invalid), status)
    
    console.print(table)
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total entries: {total_valid + total_invalid}")
    console.print(f"  Valid: [green]{total_valid}[/green]")
    console.print(f"  Invalid: [red]{total_invalid}[/red]")
    
    # Show errors if verbose or any invalid
    if verbose or total_invalid > 0:
        if all_errors:
            console.print(f"\n[bold red]Errors:[/bold red]")
            for file_name, error in all_errors:
                console.print(f"  [{file_name}] {error}")
    
    # Exit code
    sys.exit(1 if total_invalid > 0 else 0)


if __name__ == "__main__":
    main()

