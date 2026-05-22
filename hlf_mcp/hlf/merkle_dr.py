"""
Merkle Disaster Recovery — append-only signed chain backup for HLF.

Provides:
- export_merkle_backup()  — Export JSONL chain to signed backup archive
- verify_merkle_backup()  — Verify backup parity against Merkle root
- restore_from_backup()   — Restore JSONL from backup archive

Backup archive structure:
```
<backup_dir>/
  manifest.json          # Signed: chain metadata, Merkle root, timestamp
  chains/                # Per-chain JSONL files
    latent_traces.jsonl
    hlf_mcp.audit.jsonl
  signatures/            # HMAC-SHA256 signatures per file
    latent_traces.jsonl.sig
    hlf_mcp.audit.jsonl.sig
```
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CHAINS = ["latent_traces.jsonl", "hlf_mcp.audit.jsonl"]

# HMAC key prefix for domain separation
_HMAC_KEY_PREFIX = b"hlf-merkle-dr-v1:"


class MerkleBackupError(Exception):
    """Raised when backup operations fail."""


def _get_hmac_key() -> bytes:
    """Derive HMAC key from HLF_MASTER_KEY with domain separation."""
    master = os.environ.get("HLF_MASTER_KEY", "")
    if not master:
        raise MerkleBackupError(
            "HLF_MASTER_KEY environment variable is required for Merkle DR signing"
        )
    return hashlib.sha256(_HMAC_KEY_PREFIX + master.encode()).digest()


def _compute_chain_root(jsonl_path: Path) -> str:
    """Compute the Merkle chain root hash from a JSONL file.

    Re-computes trace_ids in sequence to verify chain integrity.
    Returns the final hash (Merkle root) for the chain.
    """
    if not jsonl_path.exists() or jsonl_path.stat().st_size == 0:
        return hashlib.sha256(b"").hexdigest()  # Empty chain hash

    prev_hash = "0" * 64
    with open(jsonl_path, "r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                entry = json.loads(text)
            except json.JSONDecodeError:
                continue

            # Recompute canonical payload matching verify_chain.py
            payload = json.dumps(
                {
                    "event": entry.get("event", ""),
                    "data": entry.get("data", {}),
                },
                sort_keys=True,
            )
            prev_hash = hashlib.sha256(
                f"{prev_hash}{payload}".encode()
            ).hexdigest()

    return prev_hash


def _sign_data(data: bytes) -> str:
    """Sign data with HMAC-SHA256 and return hex signature."""
    key = _get_hmac_key()
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def _verify_signature(data: bytes, signature_hex: str) -> bool:
    """Verify HMAC-SHA256 signature. Constant-time comparison."""
    key = _get_hmac_key()
    expected = hmac.new(key, data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_hex)


def export_merkle_backup(
    source_dir: Path,
    backup_dir: Path,
    *,
    chains: list[str] | None = None,
) -> dict[str, Any]:
    """Export JSONL chains to a signed backup archive.

    Args:
        source_dir: Directory containing JSONL chain files (observability/openllmetry/)
        backup_dir: Destination directory for backup archive
        chains: List of JSONL filenames to export. Defaults to standard chains.

    Returns:
        Manifest dict with chain metadata and Merkle roots.
    """
    if chains is None:
        chains = DEFAULT_CHAINS

    backup_dir = Path(backup_dir)
    chains_dir = backup_dir / "chains"
    sigs_dir = backup_dir / "signatures"
    chains_dir.mkdir(parents=True, exist_ok=True)
    sigs_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: dict[str, dict[str, Any]] = {}
    combined_root_hashes: list[str] = []

    for chain_name in chains:
        src = Path(source_dir) / chain_name
        dst = chains_dir / chain_name
        sig_file = sigs_dir / f"{chain_name}.sig"

        if src.exists():
            # Copy the chain file
            shutil.copy2(src, dst)
            chain_data = dst.read_bytes()
        else:
            # Create empty chain file
            dst.write_text("", encoding="utf-8")
            chain_data = b""

        # Compute Merkle root
        merkle_root = _compute_chain_root(dst)
        combined_root_hashes.append(f"{chain_name}:{merkle_root}")

        # Sign the chain data
        signature = _sign_data(chain_data)
        sig_file.write_text(signature, encoding="utf-8")

        # Count entries
        entry_count = 0
        if dst.exists():
            with open(dst, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        entry_count += 1

        manifest_entries[chain_name] = {
            "file": chain_name,
            "merkle_root": merkle_root,
            "entry_count": entry_count,
            "size_bytes": len(chain_data),
            "signature": signature,
        }

    # Combined Merkle root: SHA-256 of all chain roots concatenated.
    # Sort alphabetically to match json.dumps(sort_keys=True) behavior,
    # which reorders the chains dict alphabetically in the manifest JSON.
    combined_root_hashes.sort()
    combined_root = hashlib.sha256(
        "|".join(combined_root_hashes).encode()
    ).hexdigest()

    manifest = {
        "version": 1,
        "backup_type": "hlf-merkle-dr",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "combined_merkle_root": combined_root,
        "chain_count": len(chains),
        "chains": manifest_entries,
    }

    # Sign the manifest
    manifest_json = json.dumps(manifest, sort_keys=True, indent=2)
    manifest_sig = _sign_data(manifest_json.encode())

    manifest_file = backup_dir / "manifest.json"
    manifest_file.write_bytes(manifest_json.encode())

    sig_file = sigs_dir / "manifest.json.sig"
    sig_file.write_text(manifest_sig, encoding="utf-8")

    return manifest


def verify_merkle_backup(
    backup_dir: Path,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Verify a backup archive's integrity.

    Checks:
    1. Manifest signature is valid
    2. Each chain file's signature is valid
    3. Each chain's Merkle root matches the manifest
    4. All chain roots combine to match combined_merkle_root

    Returns:
        (ok, errors, manifest_dict)
    """
    backup_dir = Path(backup_dir)
    errors: list[str] = []

    manifest_file = backup_dir / "manifest.json"
    sig_file = backup_dir / "signatures" / "manifest.json.sig"

    if not manifest_file.exists():
        return False, [f"Manifest not found: {manifest_file}"], None
    if not sig_file.exists():
        return False, [f"Manifest signature not found: {sig_file}"], None

    manifest_json = manifest_file.read_bytes()

    # Verify manifest signature
    stored_sig = sig_file.read_text(encoding="utf-8").strip()
    if not _verify_signature(manifest_json, stored_sig):
        errors.append("Manifest signature verification FAILED — may be tampered")

    try:
        manifest = json.loads(manifest_json.decode("utf-8"))
    except json.JSONDecodeError as e:
        return False, [f"Invalid manifest JSON: {e}"], None

    chains_dir = backup_dir / "chains"
    sigs_dir = backup_dir / "signatures"

    combined_root_hashes: list[str] = []
    chains = manifest.get("chains", {})

    for chain_name, chain_meta in chains.items():
        chain_file = chains_dir / chain_name
        chain_sig_file = sigs_dir / f"{chain_name}.sig"

        if not chain_file.exists():
            errors.append(f"Chain file missing: {chain_name}")
            continue

        chain_data = chain_file.read_bytes()

        # Verify chain file signature
        if chain_sig_file.exists():
            stored_chain_sig = chain_sig_file.read_text(encoding="utf-8").strip()
            if not _verify_signature(chain_data, stored_chain_sig):
                errors.append(f"Chain signature FAILED: {chain_name}")
        else:
            errors.append(f"Chain signature missing: {chain_name}")

        # Verify Merkle root matches manifest
        actual_root = _compute_chain_root(chain_file)
        if actual_root != chain_meta.get("merkle_root", ""):
            errors.append(
                f"Merkle root mismatch for {chain_name}: "
                f"manifest={chain_meta.get('merkle_root', '')[:16]}... "
                f"computed={actual_root[:16]}..."
            )

        combined_root_hashes.append(f"{chain_name}:{actual_root}")

    # Sort for deterministic combined root (matches export behavior)
    combined_root_hashes.sort()

    # Verify combined Merkle root
    expected_combined = manifest.get("combined_merkle_root", "")
    actual_combined = hashlib.sha256(
        "|".join(combined_root_hashes).encode()
    ).hexdigest()

    if expected_combined and actual_combined != expected_combined:
        errors.append(
            f"Combined Merkle root mismatch: "
            f"manifest={expected_combined[:16]}... computed={actual_combined[:16]}..."
        )

    return len(errors) == 0, errors, manifest


def restore_from_backup(
    backup_dir: Path,
    target_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore JSONL chains from a verified backup archive.

    Args:
        backup_dir: Backup archive directory
        target_dir: Target directory to restore JSONL files to
        dry_run: If True, only verify and report — don't write files

    Returns:
        Dict with restore summary.
    """
    ok, errors, manifest = verify_merkle_backup(backup_dir)
    if not ok:
        raise MerkleBackupError(
            f"Backup verification failed — cannot restore: {'; '.join(errors)}"
        )

    chains_dir = backup_dir / "chains"
    target_dir = Path(target_dir)
    restored: list[str] = []

    if manifest is None:
        raise MerkleBackupError("Manifest is missing from backup")

    for chain_name in manifest.get("chains", {}):
        src = chains_dir / chain_name
        if not src.exists():
            continue

        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / chain_name
            shutil.copy2(src, dst)
        restored.append(chain_name)

    return {
        "restored_chains": restored,
        "target_directory": str(target_dir),
        "dry_run": dry_run,
        "combined_merkle_root": manifest.get("combined_merkle_root", ""),
    }
