#!/usr/bin/env python3
"""
Tests for hlf-evidence CLI (Enterprise Hardening #4: Latent Evidence Rendering).

Tests:
- list command (empty, with entries)
- show command (--latent, --capsule-id, --limit)
- verify command (with/without provenance chain)
- edge cases (missing file, malformed JSONL, None fields)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts dir to path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


@pytest.fixture
def temp_traces_dir():
    """Create a temporary directory for trace files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def empty_traces_file(temp_traces_dir):
    """Empty traces JSONL file."""
    f = temp_traces_dir / "latent_traces.jsonl"
    f.write_text("", encoding="utf-8")
    return f


@pytest.fixture
def sample_traces_file(temp_traces_dir):
    """JSONL file with sample trace entries."""
    entries = [
        json.dumps({
            "trace_id": "abc123",
            "event": "latent_governed_infer",
            "data": {
                "capsule_id": "cap-001",
                "num_steps": 6,
                "agents": ["planner", "critic", "solver"],
                "total_gas": 150,
                "total_wall_time_ms": 6900.0,
                "peak_vram_mb": 8800,
                "status": "ok",
                "attestations": [
                    {
                        "round": 1,
                        "source_agent": "planner",
                        "target_agent": "critic",
                        "source_dims": 2048,
                        "target_dims": 2048,
                        "adapter_sha256": "abc123def456",
                        "gas_consumed": 25,
                    },
                    {
                        "round": 2,
                        "source_agent": "critic",
                        "target_agent": "solver",
                        "source_dims": 2048,
                        "target_dims": 1536,
                        "adapter_sha256": "def456ghi789",
                        "gas_consumed": 25,
                    },
                ],
                "provenance_chain": [
                    "a" * 64,
                    "b" * 64,
                ],
                "final_text": "The integral of x*sin(x) dx = sin(x) - x*cos(x) + C",
                "prompt": "Compute the integral of x*sin(x) dx",
            },
        }),
        json.dumps({
            "trace_id": "def456",
            "event": "latent_governed_infer",
            "data": {
                "capsule_id": "cap-002",
                "num_steps": 3,
                "agents": ["planner", "solver"],
                "total_gas": 75,
                "total_wall_time_ms": 3100.0,
                "peak_vram_mb": 8700,
                "status": "aborted",
                "attestations": [],
                "provenance_chain": [],
                "final_text": "[ABORTED: OOM during round 2]",
                "prompt": "Test OOM handling",
            },
        }),
        json.dumps({
            "trace_id": "ghi789",
            "event": "latent_governed_infer",
            "data": {
                "capsule_id": "cap-003",
                "num_steps": 9,
                "agents": ["planner", "critic", "solver"],
                "total_gas": 225,
                "total_wall_time_ms": 12400.0,
                "peak_vram_mb": 9200,
                "status": "ok",
                "attestations": [
                    {
                        "round": 1,
                        "source_agent": "planner",
                        "target_agent": "critic",
                        "source_dims": 2048,
                        "target_dims": 2048,
                        "adapter_sha256": "xyz987abc654",
                        "gas_consumed": 25,
                    },
                ],
                "provenance_chain": ["c" * 64, "d" * 64, "e" * 64],
                "final_text": "Answer: The patient has hypothyroidism.",
                "prompt": "Medical diagnosis prompt here",
            },
        }),
    ]
    f = temp_traces_dir / "latent_traces.jsonl"
    f.write_text("\n".join(entries) + "\n", encoding="utf-8")
    return f


class TestHLFEvidenceCLI:
    """Test the hlf-evidence CLI tool."""

    def _run_cli(self, args: list[str], traces_file: Path | None = None):
        """Run the CLI and return (exit_code, stdout, stderr)."""
        import subprocess

        script = str(_SCRIPTS_DIR / "hlf_evidence.py")
        env = os.environ.copy()
        if traces_file:
            # Override _TRACES_FILE via monkeypatching the module level variable
            # We'll use environment variable approach instead
            pass

        # Use direct import and execution to avoid subprocess issues
        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            from io import StringIO

            out = StringIO()
            err = StringIO()
            sys.stdout = out
            sys.stderr = err

            # Monkey-patch the traces file path
            import hlf_evidence as cli
            if traces_file:
                cli._TRACES_FILE = traces_file

            sys.argv = ["hlf_evidence.py"] + args
            try:
                exit_code = cli.main()
            except SystemExit as e:
                exit_code = e.code if isinstance(e.code, int) else 1

            return exit_code, out.getvalue(), err.getvalue()
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    # ── list command ──

    def test_list_empty(self, empty_traces_file):
        exit_code, stdout, _ = self._run_cli(["list"], traces_file=empty_traces_file)
        assert "No latent traces found" in stdout
        assert exit_code == 0

    def test_list_with_entries(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["list"], traces_file=sample_traces_file)
        assert "cap-001" in stdout
        assert "cap-002" in stdout
        assert "cap-003" in stdout
        assert "3 trace(s) total" in stdout
        assert exit_code == 0

    def test_list_header_present(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["list"], traces_file=sample_traces_file)
        assert "Trace ID" in stdout
        assert "Capsule" in stdout
        assert "Status" in stdout
        assert "Gas" in stdout
        assert exit_code == 0

    # ── show command ──

    def test_show_latent_default_limit(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--latent"], traces_file=sample_traces_file)
        # Should show last 5 by default (we have 3)
        assert "cap-001" in stdout
        assert "cap-002" in stdout
        assert "cap-003" in stdout
        assert exit_code == 0

    def test_show_latent_limit_1(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--latent", "--limit", "1"], traces_file=sample_traces_file)
        # Should only show the most recent (cap-003)
        assert "cap-003" in stdout
        assert "cap-001" not in stdout
        assert exit_code == 0

    def test_show_by_capsule_id(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-001"], traces_file=sample_traces_file)
        assert "cap-001" in stdout
        assert "150" in stdout  # gas
        assert "6.9s" in stdout  # wall time
        assert exit_code == 0

    def test_show_by_partial_capsule_id(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-00"], traces_file=sample_traces_file)
        # Partial match finds first one
        assert "cap-001" in stdout
        assert exit_code == 0

    def test_show_nonexistent_capsule(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "nonexistent"], traces_file=sample_traces_file)
        assert "No trace found" in stdout
        assert exit_code == 1

    def test_show_empty_traces(self, empty_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--latent"], traces_file=empty_traces_file)
        assert "No latent traces found" in stdout
        assert exit_code == 0

    # ── show renders attestations ──

    def test_show_renders_attestations_with_latent_flag(self, sample_traces_file):
        """With --latent flag, full handoff trail is rendered."""
        exit_code, stdout, _ = self._run_cli(
            ["show", "--latent", "--capsule-id", "cap-001"], traces_file=sample_traces_file
        )
        # Rich output has "Latent Handoff Trail" (title case), plain text has "LATENT HANDOFF TRAIL"
        assert "Handoff Trail" in stdout
        assert "planner" in stdout
        assert "critic" in stdout
        assert "solver" in stdout
        assert "2048d" not in stdout  # Rich output doesn't show dims inline
        assert exit_code == 0

    def test_show_renders_summary_without_latent_flag(self, sample_traces_file):
        """Without --latent flag, summary line is shown instead of full trail."""
        exit_code, stdout, _ = self._run_cli(
            ["show", "--capsule-id", "cap-001"], traces_file=sample_traces_file
        )
        assert "Use --latent for details" in stdout
        assert "LATENT HANDOFF TRAIL" not in stdout
        assert exit_code == 0

    def test_show_renders_adapter_name(self, sample_traces_file):
        """Adapter hashes should be present in the output."""
        exit_code, stdout, _ = self._run_cli(
            ["show", "--latent", "--capsule-id", "cap-001"], traces_file=sample_traces_file
        )
        # Rich output: adapter hash shown as "adapter=abc123def456..."
        assert "abc123def456" in stdout
        assert exit_code == 0

    def test_show_renders_merkle_root(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-001"], traces_file=sample_traces_file)
        assert "MERKLE ROOT" in stdout
        assert "Chain depth" in stdout
        assert exit_code == 0

    def test_show_renders_final_output(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-001"], traces_file=sample_traces_file)
        assert "FINAL OUTPUT" in stdout
        assert "sin(x) - x*cos(x)" in stdout
        assert exit_code == 0

    def test_show_renders_status_aborted(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-002"], traces_file=sample_traces_file)
        assert "[ABORTED]" in stdout
        assert "OOM during round 2" in stdout
        assert exit_code == 0

    # ── show renders prompt ──

    def test_show_renders_prompt(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["show", "--capsule-id", "cap-003"], traces_file=sample_traces_file)
        assert "Medical diagnosis" in stdout
        assert exit_code == 0

    # ── verify command ──

    def test_verify_valid_chain(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["verify", "--capsule-id", "cap-001"], traces_file=sample_traces_file)
        assert "Merkle chain integrity verified" in stdout
        assert exit_code == 0

    def test_verify_no_provenance(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["verify", "--capsule-id", "cap-002"], traces_file=sample_traces_file)
        assert "No provenance chain in trace" in stdout
        assert exit_code == 1

    def test_verify_nonexistent_capsule(self, sample_traces_file):
        exit_code, stdout, _ = self._run_cli(["verify", "--capsule-id", "fake-capsule"], traces_file=sample_traces_file)
        assert "No trace found" in stdout
        assert exit_code == 1

    def test_verify_missing_arg(self, sample_traces_file):
        exit_code, _, stderr = self._run_cli(["verify"], traces_file=sample_traces_file)
        assert exit_code != 0 or "required" in stderr.lower()

    # ── malformed JSONL handling ──

    def test_malformed_jsonl(self, temp_traces_dir):
        f = temp_traces_dir / "latent_traces.jsonl"
        f.write_text('{"valid": "json"}\nnot-json\n{"also": "valid"}\n', encoding="utf-8")
        exit_code, stdout, _ = self._run_cli(["list"], traces_file=f)
        assert "2 trace(s) total" in stdout  # skips malformed line
        assert exit_code == 0

    # ── no command (prints help) ──

    def test_no_command_prints_help(self, empty_traces_file):
        exit_code, stdout, _ = self._run_cli([], traces_file=empty_traces_file)
        # Should print help and exit 0
        assert "usage" in stdout.lower() or "hlf-evidence" in stdout.lower()
        assert exit_code == 0

    # ── gas as percentage ──

    def test_show_renders_gas_percentage(self, sample_traces_file):
        """Gas should be shown as absolute and percentage of 500 budget."""
        exit_code, stdout, _ = self._run_cli(
            ["show", "--capsule-id", "cap-001"], traces_file=sample_traces_file
        )
        assert "150 / 500" in stdout
        assert "30%" in stdout
        assert exit_code == 0

    # ── tamper detection ──

    def test_verify_with_tampered_attestation(self, temp_traces_dir):
        """Tamper detection: attestation hash not in provenance chain."""
        entry = json.dumps({
            "trace_id": "tamper001",
            "event": "latent_governed_infer",
            "data": {
                "capsule_id": "tampered-cap",
                "num_steps": 3,
                "agents": ["planner"],
                "total_gas": 75,
                "status": "ok",
                "attestations": [
                    {
                        "round": 1,
                        "source_agent": "planner",
                        "target_agent": "critic",
                        "source_dims": 2048,
                        "target_dims": 2048,
                        "adapter_sha256": "abc123",
                        "provenance_hash": "ff" * 32,  # NOT in the chain!
                        "gas_consumed": 25,
                    },
                ],
                "provenance_chain": ["a" * 64, "b" * 64],
                "final_text": "test",
            },
        })
        f = temp_traces_dir / "latent_traces.jsonl"
        f.write_text(entry + "\n", encoding="utf-8")
        exit_code, stdout, _ = self._run_cli(["verify", "--capsule-id", "tampered-cap"], traces_file=f)
        assert "TAMPER ALERT" in stdout
        assert exit_code == 1
