#!/usr/bin/env python3
"""
HLF CLI - Command Line Interface for Hierarchical Language Framework

Provides commands for:
- Profile management
- Validation
- Testing
- Health checks
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hlf import ProfileManager, get_profile_summary, validate_current_profile
from hlf.infinite_rag_hlf import InfiniteRAGHLF, Fact


def cmd_profile(args):
    """Show current profile information"""
    profile = ProfileManager(args.profile)
    print(profile.get_summary())
    
    if args.validate:
        result = profile.validate()
        print(f"\nValidation: {'✅ PASSED' if result['valid'] else '❌ FAILED'}")
        if result['issues']:
            print("Issues:")
            for issue in result['issues']:
                print(f"  - {issue}")
    
    return 0


def cmd_validate(args):
    """Validate HLF configuration"""
    profile = ProfileManager(args.profile)
    result = profile.validate()
    
    print(f"Profile: {result['profile']}")
    print(f"Valid: {'✅ YES' if result['valid'] else '❌ NO'}")
    
    if result['issues']:
        print("\nIssues Found:")
        for issue in result['issues']:
            print(f"  ❌ {issue}")
        return 1
    else:
        print("\n✅ All checks passed!")
        print(f"\nProfile Summary:{profile.get_summary()}")
        return 0


def cmd_rag_stats(args):
    """Show Infinite RAG statistics"""
    rag = InfiniteRAGHLF(
        db_path=args.db or "./data/hlf_rag.db",
        profile=args.profile or os.getenv("HLF_PROFILE", "P0")
    )
    
    stats = rag.get_stats()
    print(json.dumps(stats, indent=2))
    return 0


def cmd_rag_test(args):
    """Test Infinite RAG functionality"""
    profile = args.profile or os.getenv("HLF_PROFILE", "P0")
    print(f"Testing Infinite RAG with profile: {profile}")
    
    rag = InfiniteRAGHLF(
        db_path=args.db or "./data/hlf_rag_test.db",
        profile=profile
    )
    
    # Test 1: Add a fact
    print("\n1. Adding test fact...")
    fact = Fact(
        id="test_1",
        content="HLF is a hierarchical language framework",
        source="test_suite"
    )
    fact_id = rag.add_fact(fact)
    print(f"   ✓ Added fact: {fact_id}")
    
    # Test 2: Retrieve fact
    print("\n2. Retrieving fact...")
    retrieved = rag.get_fact(fact_id)
    if retrieved and retrieved.content == fact.content:
        print(f"   ✓ Retrieved fact successfully")
    else:
        print(f"   ✗ Failed to retrieve fact")
        return 1
    
    # Test 3: Search facts
    print("\n3. Searching facts...")
    results = rag.search_facts("hierarchical", limit=5)
    if len(results) > 0:
        print(f"   ✓ Found {len(results)} matching fact(s)")
    else:
        print(f"   ✗ No facts found")
        return 1
    
    # Test 4: Add meta-intent (self-observation)
    print("\n4. Testing self-observation (meta-intent)...")
    meta_intent = {
        "source_hash": "abc123",
        "timestamp": 1234567890.0,
        "phase_timings": {"parse": 0.001, "compile": 0.002},
        "warnings": [],
        "errors": [],
        "gas_used": 100,
        "profile": profile
    }
    intent_id = rag.add_meta_intent(meta_intent)
    print(f"   ✓ Added meta-intent: {intent_id}")
    
    # Test 5: Retrieve meta-intents
    print("\n5. Retrieving meta-intents...")
    intents = rag.get_recent_meta_intents(since=1234567880.0, limit=10)
    if len(intents) > 0:
        print(f"   ✓ Retrieved {len(intents)} meta-intent(s)")
    else:
        print(f"   ✗ No meta-intents found")
        return 1
    
    # Test 6: Get stats
    print("\n6. Getting RAG statistics...")
    stats = rag.get_stats()
    print(f"   Facts: {stats['facts']}")
    print(f"   Meta Intents: {stats['meta_intents']}")
    print(f"   Profile: {stats['profile']}")
    
    # Cleanup
    if args.cleanup:
        print("\n7. Cleaning up test data...")
        removed = rag.cleanup(max_age_days=0)
        print(f"   ✓ Removed {removed} items")
    
    print("\n✅ All RAG tests passed!")
    return 0


def cmd_env(args):
    """Show environment configuration"""
    print("HLF Environment Configuration")
    print("=" * 40)
    
    env_vars = {
        "HLF_PROFILE": os.getenv("HLF_PROFILE", "(not set, will auto-detect)"),
        "HLF_OLLAMA_MODE": os.getenv("HLF_OLLAMA_MODE", "(not set)"),
        "HLF_DEFAULT_MODEL": os.getenv("HLF_DEFAULT_MODEL", "(not set)"),
        "HLF_OLLAMA_USE_CLOUD_DIRECT": os.getenv("HLF_OLLAMA_USE_CLOUD_DIRECT", "(not set)"),
        "OLLAMA_API_KEY": "***SET***" if os.getenv("OLLAMA_API_KEY") else "(not set - REQUIRED for P0)",
        "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "(not set)"),
    }
    
    for key, value in env_vars.items():
        print(f"{key}: {value}")
    
    # Detect profile
    profile = ProfileManager()
    print(f"\nDetected Profile: {profile.current_profile}")
    
    return 0


def cmd_init(args):
    """Initialize HLF environment"""
    print("🚀 Initializing HLF Environment")
    print("=" * 40)
    
    # Create data directory
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Data directory: {data_dir.absolute()}")
    
    # Detect/create profile
    profile = ProfileManager(args.profile)
    print(f"\nProfile: {profile.current_profile}")
    print(profile.get_summary())
    
    # Validate
    result = profile.validate()
    if not result['valid']:
        print("\n❌ Validation failed:")
        for issue in result['issues']:
            print(f"  - {issue}")
        print("\nPlease set the required environment variables.")
        return 1
    
    # Initialize RAG
    print("\nInitializing Infinite RAG...")
    rag = InfiniteRAGHLF(
        db_path=str(data_dir / "hlf_rag.db"),
        profile=profile.current_profile
    )
    stats = rag.get_stats()
    print(f"✓ RAG initialized")
    print(f"  Facts: {stats['facts']}")
    print(f"  Meta Intents: {stats['meta_intents']}")
    
    print("\n✅ HLF initialization complete!")
    print(f"\nNext steps:")
    print(f"  1. Run tests: python -m hlf.test_suite")
    print(f"  2. Start CLI: python -m hlf.hlf_cli --help")
    
    return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="HLF - Hierarchical Language Framework CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s profile --validate
  %(prog)s validate --profile P0
  %(prog)s rag-test --profile P0
  %(prog)s init --profile P0
        """
    )
    
    parser.add_argument(
        "--profile",
        choices=["P0", "P1", "P2"],
        help="HLF profile to use"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Profile command
    profile_parser = subparsers.add_parser("profile", help="Show profile information")
    profile_parser.add_argument("--validate", action="store_true", help="Validate profile")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    
    # RAG stats command
    rag_stats_parser = subparsers.add_parser("rag-stats", help="Show RAG statistics")
    rag_stats_parser.add_argument("--db", help="Database path")
    
    # RAG test command
    rag_test_parser = subparsers.add_parser("rag-test", help="Test RAG functionality")
    rag_test_parser.add_argument("--db", help="Database path")
    rag_test_parser.add_argument("--cleanup", action="store_true", help="Clean up test data")
    
    # Env command
    env_parser = subparsers.add_parser("env", help="Show environment configuration")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize HLF environment")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Dispatch to command handler
    commands = {
        "profile": cmd_profile,
        "validate": cmd_validate,
        "rag-stats": cmd_rag_stats,
        "rag-test": cmd_rag_test,
        "env": cmd_env,
        "init": cmd_init,
    }
    
    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
