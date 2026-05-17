"""Tests for the governed event log sink (TASK-002)."""

from __future__ import annotations

import gzip
import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from hlf_mcp.hlf.governance_event_log import GovernanceEventLog, LogRotationConfig


@pytest.fixture
def temp_log_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "governance_events.jsonl"


class TestGovernanceEventLogBasics:
    def test_append_single_event(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        entry = log.append(
            {
                "timestamp_ns": time.time_ns(),
                "kind": "test_event",
                "source": "test",
                "severity": "info",
                "action": "test_action",
                "subject_id": "agent-1",
            }
        )
        assert entry.event_type == "test_event"
        assert entry.source == "test"
        assert entry.severity == "info"
        assert entry.content_hash
        assert len(entry.content_hash) == 64  # SHA-256 hex
        assert temp_log_path.is_file()

    def test_append_produces_valid_jsonl(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.append({"kind": "a", "source": "s", "action": "act"})
        log.append({"kind": "b", "source": "s", "action": "act2"})
        lines = temp_log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "content_hash" in obj
            assert "trace_ref" in obj
            assert "timestamp_ns" in obj

    def test_get_last_n_returns_most_recent_first(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        for i in range(5):
            log.append({"kind": f"event_{i}", "source": "s", "action": "act"})
        entries = log.get_last_n(3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0]["event_type"] == "event_4"
        assert entries[1]["event_type"] == "event_3"
        assert entries[2]["event_type"] == "event_2"

    def test_get_last_n_respects_max_memory_cache(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=3)
        for i in range(5):
            log.append({"kind": f"event_{i}", "source": "s", "action": "act"})
        entries = log.get_last_n(10)
        assert len(entries) == 3
        assert entries[0]["event_type"] == "event_4"

    def test_get_last_n_summaries(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.append({"kind": "x", "source": "s", "action": "act", "subject_id": "sub"})
        summaries = log.get_last_n_summaries(1)
        assert len(summaries) == 1
        assert "act" in summaries[0]
        assert "sub" in summaries[0]


class TestGovernanceEventLogQueries:
    def test_get_by_trace_ref(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        entry = log.append(
            {"kind": "k", "source": "s", "action": "a", "trace_ref": "ref-123"}
        )
        found = log.get_by_trace_ref("ref-123")
        assert found is not None
        assert found["trace_ref"] == "ref-123"
        assert found["content_hash"] == entry.content_hash

    def test_get_by_trace_ref_missing(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        assert log.get_by_trace_ref("missing") is None

    def test_get_by_content_hash(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        entry = log.append({"kind": "k", "source": "s", "action": "a"})
        found = log.get_by_content_hash(entry.content_hash)
        assert found is not None
        assert found["content_hash"] == entry.content_hash


class TestGovernanceEventLogIntegrity:
    def test_verify_integrity_ok(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        for _ in range(5):
            log.append({"kind": "k", "source": "s", "action": "a"})
        result = log.verify_integrity(limit=10)
        assert result["status"] == "ok"
        assert result["checked"] == 5
        assert result["ok"] == 5
        assert result["mismatch"] == 0
        assert result["missing_hash"] == 0

    def test_verify_integrity_detects_tampering(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.append({"kind": "k", "source": "s", "action": "a"})
        # Tamper with the file
        lines = temp_log_path.read_text(encoding="utf-8").strip().splitlines()
        obj = json.loads(lines[0])
        obj["payload"]["kind"] = "tampered"
        lines[0] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        temp_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = log.verify_integrity(limit=10)
        assert result["mismatch"] == 1


class TestGovernanceEventLogRotation:
    def test_rotation_by_size(self, temp_log_path: Path) -> None:
        rotation = LogRotationConfig(max_bytes=500, backup_count=2, compress_backups=False)
        log = GovernanceEventLog(log_path=temp_log_path, rotation=rotation, max_memory_cache=100)
        for i in range(20):
            log.append({"kind": f"event_{i}", "source": "s", "action": "a", "data": "x" * 50})
        # Check backup files exist
        log_dir = temp_log_path.parent
        backups = sorted(log_dir.glob("governance_events.*.jsonl"))
        assert len(backups) >= 1

    def test_rotation_with_compression(self, temp_log_path: Path) -> None:
        rotation = LogRotationConfig(max_bytes=500, backup_count=2, compress_backups=True)
        log = GovernanceEventLog(log_path=temp_log_path, rotation=rotation, max_memory_cache=100)
        for i in range(20):
            log.append({"kind": f"event_{i}", "source": "s", "action": "a", "data": "x" * 50})
        log_dir = temp_log_path.parent
        gz_files = list(log_dir.glob("*.gz"))
        assert len(gz_files) >= 1
        # Verify gzip is readable
        for gz_path in gz_files:
            with gzip.open(gz_path, "rt", encoding="utf-8") as fh:
                content = fh.read()
                assert "event_" in content


class TestGovernanceEventLogAnchors:
    def test_memory_anchor_callback(self, temp_log_path: Path) -> None:
        received: list[dict[str, Any]] = []
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.wire_memory_anchor(lambda entry: received.append(entry))
        log.append({"kind": "k", "source": "s", "action": "a"})
        assert len(received) == 1
        assert received[0]["event_type"] == "k"

    def test_runtime_anchor_callback(self, temp_log_path: Path) -> None:
        received: list[dict[str, Any]] = []
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.wire_runtime_anchor(lambda entry: received.append(entry))
        log.append({"kind": "k", "source": "s", "action": "a"})
        assert len(received) == 1

    def test_anchor_exception_isolated(self, temp_log_path: Path) -> None:
        log = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        log.wire_memory_anchor(lambda _e: (_ for _ in ()).throw(RuntimeError("boom")))
        # Should not raise
        log.append({"kind": "k", "source": "s", "action": "a"})


class TestGovernanceEventLogHydration:
    def test_hydrate_cache_on_startup(self, temp_log_path: Path) -> None:
        log1 = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        for i in range(5):
            log1.append({"kind": f"event_{i}", "source": "s", "action": "a"})
        # Create new instance pointing to same file
        log2 = GovernanceEventLog(log_path=temp_log_path, max_memory_cache=10)
        entries = log2.get_last_n(5)
        assert len(entries) == 5
        assert entries[0]["event_type"] == "event_4"
