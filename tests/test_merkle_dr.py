"""
Tests for HLF Merkle DR (Enterprise Hardening #6: Disaster Recovery).

Tests:
- Export → verify → restore cycle
- Manifest signature verification
- Tampered manifest detection
- Tampered chain file detection
- Empty chain handling
- Missing chain handling
- Delete WAL → restore → chain integrity maintained
- Cross-backup isolation (different master keys)
- CLI integration (export/verify/restore subcommands)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest


# ── Fixtures ──

@pytest.fixture
def master_key():
    """Set and restore HLF_MASTER_KEY."""
    old = os.environ.get("HLF_MASTER_KEY")
    os.environ["HLF_MASTER_KEY"] = "test-master-key-for-merkle-dr"
    yield
    if old is not None:
        os.environ["HLF_MASTER_KEY"] = old
    else:
        os.environ.pop("HLF_MASTER_KEY", None)


@pytest.fixture
def chain_factory():
    """Create a temp directory with a valid JSONL chain."""
    def _make_chain(entries: list[dict] | None = None) -> Path:
        tmpdir = Path(tempfile.mkdtemp(prefix="hlf_merkle_test_"))
        chain_file = tmpdir / "latent_traces.jsonl"

        if entries is None:
            entries = [
                {
                    "trace_id": "04fdd9e4f35f8780f8a56f156e91f8fb9817b9ff1a93f2e66c4cbe93c7638a17",
                    "event": "latent_governed_infer",
                    "data": {"capsule_id": "cap-1", "num_steps": 6, "total_gas": 150},
                },
                {
                    "trace_id": "300a75e3e9adb837882ae6af3dd052df45cf851ed017f15d4f382584371be015",
                    "event": "latent_governed_infer",
                    "data": {"capsule_id": "cap-2", "num_steps": 6, "total_gas": 150},
                },
                {
                    "trace_id": "1e277685385b06f3ff959e3fdd17b6bf6cf2585d367cd11e52b45c308f66e0c8",
                    "event": "latent_governed_infer",
                    "data": {"capsule_id": "cap-3", "num_steps": 9, "total_gas": 225},
                },
            ]

        with open(chain_file, "w", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry, sort_keys=True) + "\n")

        return tmpdir

    return _make_chain


# ── Export → Verify → Restore cycle ──

class TestExportVerifyRestore:
    def test_full_cycle(self, master_key, chain_factory):
        """Export a chain, verify it, then restore it."""
        from hlf_mcp.hlf.merkle_dr import (
            export_merkle_backup,
            restore_from_backup,
            verify_merkle_backup,
        )

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_backup_"))
        restore_dir = Path(tempfile.mkdtemp(prefix="hlf_restore_"))

        # Export
        manifest = export_merkle_backup(
            source_dir=source_dir,
            backup_dir=backup_dir,
            chains=["latent_traces.jsonl"],
        )
        assert manifest["chain_count"] == 1
        assert "latent_traces.jsonl" in manifest["chains"]
        assert manifest["chains"]["latent_traces.jsonl"]["entry_count"] == 3

        # Verify
        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert ok
        assert errors == []

        # Restore
        result = restore_from_backup(backup_dir, restore_dir)
        assert len(result["restored_chains"]) == 1

        # Check restored content matches original
        restored_file = restore_dir / "latent_traces.jsonl"
        original_file = source_dir / "latent_traces.jsonl"
        assert restored_file.exists()
        assert restored_file.read_text() == original_file.read_text()

    def test_multiple_chains(self, master_key, chain_factory):
        """Export multiple chains and verify all are backed up."""
        from hlf_mcp.hlf.merkle_dr import (
            export_merkle_backup,
            verify_merkle_backup,
        )

        source_dir = chain_factory()
        # Create second chain
        audit_file = source_dir / "hlf_mcp.audit.jsonl"
        audit_file.write_text(
            json.dumps({"trace_id": "a" * 64, "event": "audit", "data": {}}) + "\n",
            encoding="utf-8",
        )

        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_backup_"))
        manifest = export_merkle_backup(
            source_dir=source_dir,
            backup_dir=backup_dir,
            chains=["latent_traces.jsonl", "hlf_mcp.audit.jsonl"],
        )

        assert manifest["chain_count"] == 2
        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert ok

    def test_empty_chain(self, master_key):
        """Empty chain should export and verify cleanly."""
        from hlf_mcp.hlf.merkle_dr import (
            export_merkle_backup,
            verify_merkle_backup,
        )

        source_dir = Path(tempfile.mkdtemp(prefix="hlf_empty_src_"))
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_empty_bkup_"))

        manifest = export_merkle_backup(
            source_dir=source_dir,
            backup_dir=backup_dir,
            chains=["latent_traces.jsonl"],
        )

        assert manifest["chains"]["latent_traces.jsonl"]["entry_count"] == 0
        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert ok


# ── Tamper Detection ──

class TestTamperDetection:
    def test_tampered_manifest_fails(self, master_key, chain_factory):
        """Modifying the manifest should cause verification failure."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_tamper_"))

        export_merkle_backup(source_dir, backup_dir)

        # Tamper with manifest
        manifest_file = backup_dir / "manifest.json"
        original = manifest_file.read_text()
        tampered = original.replace('"entry_count": 3', '"entry_count": 999')
        manifest_file.write_text(tampered, encoding="utf-8")

        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert not ok
        assert any("Manifest signature" in e for e in errors)

    def test_tampered_chain_file_fails(self, master_key, chain_factory):
        """Modifying a chain file should cause verification failure."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_tamper_"))

        export_merkle_backup(source_dir, backup_dir)

        # Tamper with chain file
        chain_file = backup_dir / "chains" / "latent_traces.jsonl"
        chain_file.write_text("TAMPERED DATA\n", encoding="utf-8")

        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert not ok
        assert any("Chain signature" in e or "Merkle root" in e 
                   for e in errors)

    def test_deleted_chain_file_fails(self, master_key, chain_factory):
        """Deleting a chain file should cause verification failure."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_tamper_"))

        export_merkle_backup(source_dir, backup_dir)

        # Delete chain file
        chain_file = backup_dir / "chains" / "latent_traces.jsonl"
        chain_file.unlink()

        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert not ok

    def test_deleted_signature_fails(self, master_key, chain_factory):
        """Deleting a signature file should cause verification failure."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_tamper_"))

        export_merkle_backup(source_dir, backup_dir)

        # Delete signature
        sig_file = backup_dir / "signatures" / "latent_traces.jsonl.sig"
        sig_file.unlink()

        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert not ok


# ── WAL Disaster Recovery ──

class TestWALDisasterRecovery:
    def test_delete_wal_restore_chain_intact(self, master_key, chain_factory):
        """Simulate WAL corruption: delete source, restore from backup, verify chain."""
        from hlf_mcp.hlf.merkle_dr import (
            export_merkle_backup,
            restore_from_backup,
        )

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_wal_"))

        # Export only the latent_traces chain (explicit, to match source)
        export_merkle_backup(
            source_dir, backup_dir,
            chains=["latent_traces.jsonl"],
        )

        # Simulate disaster: delete the source chain
        original_chain = source_dir / "latent_traces.jsonl"
        original_content = original_chain.read_text(encoding="utf-8")
        original_chain.unlink()
        assert not original_chain.exists()

        # Restore from backup
        result = restore_from_backup(backup_dir, source_dir)
        assert "latent_traces.jsonl" in result["restored_chains"]

        # Chain file is back
        assert original_chain.exists()

        # Verify chain integrity — content should match original
        restored_content = original_chain.read_text(encoding="utf-8")
        assert restored_content == original_content


# ── Dry Run ──

class TestDryRun:
    def test_dry_run_does_not_write(self, master_key, chain_factory):
        """Dry run should verify but not write files."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, restore_from_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_dryrun_"))
        target_dir = Path(tempfile.mkdtemp(prefix="hlf_dryrun_tgt_"))

        export_merkle_backup(source_dir, backup_dir)

        # Delete source to prove dry run doesn't rely on it
        original_chain = source_dir / "latent_traces.jsonl"
        original_chain.unlink()

        result = restore_from_backup(backup_dir, target_dir, dry_run=True)
        assert result["dry_run"] is True

        # Target should be empty (no files written)
        target_chain = target_dir / "latent_traces.jsonl"
        assert not target_chain.exists()


# ── Key Isolation ──

class TestKeyIsolation:
    def test_different_master_key_rejects_restore(self, chain_factory):
        """Backup signed with key-A should fail verification with key-B."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, verify_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_keyiso_"))

        # Export with key-A
        os.environ["HLF_MASTER_KEY"] = "master-key-alpha"
        export_merkle_backup(source_dir, backup_dir)

        # Verify with key-B
        os.environ["HLF_MASTER_KEY"] = "master-key-beta"
        ok, errors, _ = verify_merkle_backup(backup_dir)
        assert not ok
        assert any("Manifest signature" in e for e in errors)


# ── Missing Master Key ──

class TestMissingMasterKey:
    def test_export_without_master_key_fails(self, chain_factory):
        """Export without HLF_MASTER_KEY should fail."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup, MerkleBackupError

        old = os.environ.pop("HLF_MASTER_KEY", None)
        try:
            source_dir = chain_factory()
            backup_dir = Path(tempfile.mkdtemp(prefix="hlf_nokey_"))
            with pytest.raises(MerkleBackupError, match="HLF_MASTER_KEY"):
                export_merkle_backup(source_dir, backup_dir)
        finally:
            if old is not None:
                os.environ["HLF_MASTER_KEY"] = old


# ── Manifest Metadata ──

class TestManifestMetadata:
    def test_manifest_contains_required_fields(self, master_key, chain_factory):
        """Manifest should have version, timestamp, merkle root, chains."""
        from hlf_mcp.hlf.merkle_dr import export_merkle_backup

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_meta_"))

        manifest = export_merkle_backup(source_dir, backup_dir)

        assert manifest["version"] == 1
        assert manifest["backup_type"] == "hlf-merkle-dr"
        assert "timestamp_utc" in manifest
        assert len(manifest["combined_merkle_root"]) == 64
        assert manifest["chain_count"] >= 1

        for chain_name, meta in manifest["chains"].items():
            assert len(meta["merkle_root"]) == 64
            assert "entry_count" in meta
            assert "size_bytes" in meta
            assert "signature" in meta
            assert len(meta["signature"]) == 64


# ── CLI Integration ──

class TestCLIIntegration:
    def test_export_verify_restore_cli(self, master_key, chain_factory):
        """End-to-end CLI: export → verify → restore via subprocess."""
        import subprocess
        import sys

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_cli_"))
        restore_dir = Path(tempfile.mkdtemp(prefix="hlf_cli_restore_"))

        script = str(Path(__file__).parent.parent / "scripts" / "hlf_backup.py")

        # Export
        result = subprocess.run(
            [sys.executable, script, "export",
             "--source-dir", str(source_dir),
             "--backup-dir", str(backup_dir),
             "--chains", "latent_traces.jsonl"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Export failed: {result.stderr}"
        assert "Backup exported" in result.stdout

        # Verify
        result = subprocess.run(
            [sys.executable, script, "verify",
             "--backup-dir", str(backup_dir)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Verify failed: {result.stderr}"
        assert "Backup verified" in result.stdout

        # Restore
        result = subprocess.run(
            [sys.executable, script, "restore",
             "--backup-dir", str(backup_dir),
             "--target-dir", str(restore_dir)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Restore failed: {result.stderr}"
        assert "Restored" in result.stdout

        # Verify restored content
        restored_file = restore_dir / "latent_traces.jsonl"
        original_file = source_dir / "latent_traces.jsonl"
        assert restored_file.read_text() == original_file.read_text()

    def test_verify_tampered_fails_cli(self, master_key, chain_factory):
        """CLI verify should exit non-zero on tampered backup."""
        import subprocess
        import sys

        source_dir = chain_factory()
        backup_dir = Path(tempfile.mkdtemp(prefix="hlf_cli_tamper_"))

        script = str(Path(__file__).parent.parent / "scripts" / "hlf_backup.py")

        # Export
        subprocess.run(
            [sys.executable, script, "export",
             "--source-dir", str(source_dir),
             "--backup-dir", str(backup_dir)],
            capture_output=True, text=True,
        )

        # Tamper with chain file
        chain_file = backup_dir / "chains" / "latent_traces.jsonl"
        chain_file.write_text("CORRUPTED\n", encoding="utf-8")

        # Verify should now fail
        result = subprocess.run(
            [sys.executable, script, "verify",
             "--backup-dir", str(backup_dir)],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "FAIL" in result.stderr

    def test_backup_missing_source(self, master_key):
        """CLI should error gracefully on missing source directory."""
        import subprocess
        import sys

        script = str(Path(__file__).parent.parent / "scripts" / "hlf_backup.py")

        result = subprocess.run(
            [sys.executable, script, "export",
             "--source-dir", "/nonexistent/path/xyz",
             "--backup-dir", str(tempfile.mkdtemp())],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "ERROR" in result.stderr
