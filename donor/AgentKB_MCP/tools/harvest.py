#!/usr/bin/env python3
"""
Knowledge Harvester CLI

Proactively monitors official documentation sources and generates
KB entries for human review.

Usage:
    python -m tools.harvest --check           # Check all sources for changes
    python -m tools.harvest --domain python   # Check specific domain only
    python -m tools.harvest --force           # Ignore check intervals
    python -m tools.harvest --list            # List registered sources
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Harvester - Proactive KB expansion"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check all sources for changes and generate entries",
    )
    parser.add_argument(
        "--domain",
        type=str,
        help="Only check sources for specific domain",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore check intervals, check all sources now",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all registered sources",
    )
    parser.add_argument(
        "--add-domain",
        type=str,
        metavar="KEY:NAME",
        help="Add a new domain (e.g., 'golang:Go Language')",
    )
    parser.add_argument(
        "--add-source",
        type=str,
        nargs=3,
        metavar=("DOMAIN", "URL", "TYPE"),
        help="Add a source to a domain (e.g., 'golang https://go.dev/blog release_notes')",
    )
    
    args = parser.parse_args()
    
    # Import after arg parsing to speed up help display
    from app.harvester.registry import SourceRegistry, Source
    from app.harvester.detector import ChangeDetector
    from app.harvester.generator import EntryGenerator
    from app.services.kb_parser import KBParser
    
    registry = SourceRegistry()
    
    if args.list:
        print("\n=== Registered Sources ===\n")
        for domain in registry.get_domains():
            sources = registry.get_sources(domain)
            print(f"[{domain}]")
            for src in sources:
                print(f"  - {src.url}")
                print(f"    Type: {src.type}, Interval: {src.check_interval}")
            print()
        return 0
    
    if args.add_domain:
        if ":" not in args.add_domain:
            print("Error: Format is KEY:NAME (e.g., 'golang:Go Language')")
            return 1
        key, name = args.add_domain.split(":", 1)
        registry.add_domain(key, name)
        print(f"Added domain: {key} ({name})")
        return 0
    
    if args.add_source:
        domain, url, source_type = args.add_source
        source = Source(url=url, type=source_type)
        registry.add_source(domain, source)
        print(f"Added source to {domain}: {url}")
        return 0
    
    if args.check:
        print("\n=== Knowledge Harvester ===\n")
        
        # Get sources to check
        if args.domain:
            sources = [(args.domain, s) for s in registry.get_sources(args.domain)]
            if not sources:
                print(f"Error: Domain '{args.domain}' not found")
                return 1
        else:
            sources = registry.get_all_sources()
        
        print(f"Checking {len(sources)} sources...")
        
        # Check for changes
        detector = ChangeDetector()
        results = await detector.check_all(sources, force=args.force)
        
        changed = detector.get_changed_sources(results)
        print(f"Found {len(changed)} sources with changes")
        
        if not changed:
            print("No changes detected. KB is up to date.")
            return 0
        
        # Generate entries from changed content
        generator = EntryGenerator()
        kb_parser = KBParser()
        existing = kb_parser.parse_all()
        
        total_generated = 0
        
        for change in changed:
            print(f"\nProcessing: {change.url}")
            
            # Determine content type from source
            source = next(
                (s for d, s in sources if s.url == change.url),
                None
            )
            content_type = source.type if source else "documentation"
            
            entries = await generator.generate_entries(change, content_type)
            
            if entries:
                # Remove duplicates
                unique = await generator.check_duplicates(entries, existing)
                
                if unique:
                    filepath = generator.write_to_staging(unique)
                    print(f"  Generated {len(unique)} entries -> {filepath}")
                    total_generated += len(unique)
                else:
                    print(f"  All {len(entries)} entries were duplicates")
            else:
                print("  No entries extracted")
        
        print(f"\n=== Summary ===")
        print(f"Sources checked: {len(results)}")
        print(f"Sources changed: {len(changed)}")
        print(f"Entries generated: {total_generated}")
        print(f"\nReview staged entries in: ./kb_staging/")
        print("Then run: python -m tools.promote_staging")
        
        return 0
    
    # No action specified
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

