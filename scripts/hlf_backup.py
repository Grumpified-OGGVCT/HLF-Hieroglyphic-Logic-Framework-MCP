#!/usr/bin/env python3
"""
HLF Merkle Disaster Recovery CLI — export, verify, and restore signed chain backups.

Usage:
  hlf-backup export [--chains CHAIN [CHAIN ...]] [--source-dir DIR] [--backup-dir DIR]
  hlf-backup verify [--backup-dir DIR]
  hlf-backup restore [--backup-dir DIR] [--target-dir DIR] [--dry-run]

The backup archives Merkle-chained JSONL observability traces with HMAC-SHA256
signatures derived from HLF_MASTER_KEY.  Restore only succeeds after verification.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from hlf_mcp.hlf.merkle_dr import (
    DEFAULT_CHAINS,
    MerkleBackupError,
    export_merkle_backup,
    restore_from_backup,
    verify_merkle_backup,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = REPO_ROOT / "observability" / "openllmetry"
DEFAULT_BACKUP_DIR = REPO_ROOT / "observability" / "merkle_backups" / "latest"


def cmd_export(args: argparse.Namespace) -> int:
    """Export chain files to a signed backup archive."""
    source_dir = Path(args.source_dir)
    backup_dir = Path(args.backup_dir)

    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    try:
        manifest = export_merkle_backup(
            source_dir=source_dir,
            backup_dir=backup_dir,
            chains=args.chains if args.chains else None,
        )
    except MerkleBackupError as e:
        print(f"[ERROR] Backup export failed: {e}", file=sys.stderr)
        return 1

    print(f"[OK] Backup exported to {backup_dir}")
    print(f"     Combined Merkle root: {manifest['combined_merkle_root'][:16]}...")
    print(f"     Chains: {len(manifest['chains'])}")
    for name, meta in manifest["chains"].items():
        print(f"       {name}: {meta['entry_count']} entries, "
              f"root={meta['merkle_root'][:16]}...")

    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify backup archive integrity."""
    backup_dir = Path(args.backup_dir)

    if not backup_dir.exists():
        print(f"[ERROR] Backup directory not found: {backup_dir}", file=sys.stderr)
        return 1

    try:
        ok, errors, manifest = verify_merkle_backup(backup_dir)
    except MerkleBackupError as e:
        print(f"[ERROR] Backup verification failed: {e}", file=sys.stderr)
        return 1

    if ok:
        if manifest:
            print(f"[OK] Backup verified — {manifest.get('chain_count', 0)} chains intact")
            print(f"     Combined Merkle root: {manifest['combined_merkle_root'][:16]}...")
        else:
            print(f"[OK] Backup verified")
        return 0

    for err in errors:
        print(f"[FAIL] {err}", file=sys.stderr)
    return 1


def cmd_restore(args: argparse.Namespace) -> int:
    """Restore chain files from a verified backup archive."""
    backup_dir = Path(args.backup_dir)
    target_dir = Path(args.target_dir)

    if not backup_dir.exists():
        print(f"[ERROR] Backup directory not found: {backup_dir}", file=sys.stderr)
        return 1

    try:
        result = restore_from_backup(
            backup_dir=backup_dir,
            target_dir=target_dir,
            dry_run=args.dry_run,
        )
    except MerkleBackupError as e:
        print(f"[ERROR] Restore failed: {e}", file=sys.stderr)
        return 1

    mode = "[DRY RUN]" if result["dry_run"] else "[OK]"
    print(f"{mode} Restored {len(result['restored_chains'])} chains "
          f"to {result['target_directory']}")
    for chain in result["restored_chains"]:
        print(f"       {chain}")
    print(f"     Merkle root: {result['combined_merkle_root'][:16]}...")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HLF Merkle Disaster Recovery — export/verify/restore signed chain backups",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # ── export ──
    export_parser = subparsers.add_parser("export", help="Export chains to signed backup")
    export_parser.add_argument(
        "--chains", nargs="*", default=None,
        help="Chain files to export (default: all standard chains)",
    )
    export_parser.add_argument(
        "--source-dir", default=str(DEFAULT_SOURCE_DIR),
        help="Directory containing source JSONL chain files",
    )
    export_parser.add_argument(
        "--backup-dir", default=str(DEFAULT_BACKUP_DIR),
        help="Destination directory for backup archive",
    )

    # ── verify ──
    verify_parser = subparsers.add_parser("verify", help="Verify backup archive integrity")
    verify_parser.add_argument(
        "--backup-dir", default=str(DEFAULT_BACKUP_DIR),
        help="Backup archive directory to verify",
    )

    # ── restore ──
    restore_parser = subparsers.add_parser("restore", help="Restore chains from verified backup")
    restore_parser.add_argument(
        "--backup-dir", default=str(DEFAULT_BACKUP_DIR),
        help="Backup archive directory to restore from",
    )
    restore_parser.add_argument(
        "--target-dir", default=str(DEFAULT_SOURCE_DIR),
        help="Directory to restore JSONL files into",
    )
    restore_parser.add_argument(
        "--dry-run", action="store_true",
        help="Verify only, don't write files",
    )

    args = parser.parse_args()

    if args.command == "export":
        sys.exit(cmd_export(args))
    elif args.command == "verify":
        sys.exit(cmd_verify(args))
    elif args.command == "restore":
        sys.exit(cmd_restore(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
