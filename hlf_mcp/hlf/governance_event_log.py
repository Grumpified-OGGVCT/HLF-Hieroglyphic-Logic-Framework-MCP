"""Governed event log sink with deterministic trace references, operator-readable summaries, and log rotation.

All GovernanceEvents emitted by the GovernanceOrchestrator are appended to a JSON-lines
log file with SHA-256 content hashes for tamper detection.  Log rotation is size-based
with a configurable backup count.  A bounded in-memory cache provides fast access to
recent events for the MCP tool surface.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class LogRotationConfig:
    """Configuration for log rotation."""

    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    compress_backups: bool = True


@dataclass
class GovernanceEventLogEntry:
    """A single entry in the governed event log."""

    timestamp_ns: int
    trace_ref: str
    event_type: str
    source: str
    severity: str
    summary: str
    payload: dict[str, Any]
    content_hash: str  # SHA-256 of canonical JSON payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ns": self.timestamp_ns,
            "trace_ref": self.trace_ref,
            "event_type": self.event_type,
            "source": self.source,
            "severity": self.severity,
            "summary": self.summary,
            "payload": self.payload,
            "content_hash": self.content_hash,
        }

    def to_operator_summary(self) -> str:
        """Return a single-line, human-readable summary."""
        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp_ns / 1e9))
        return (
            f"[{ts_iso}] {self.severity.upper():8} | {self.event_type:24} | "
            f"{self.source:32} | {self.summary}"
        )


class GovernanceEventLog:
    """Append-only governed event log with rotation and deterministic trace references.

    Integrates with RAGMemory (memory anchor) and HLFRuntime (runtime anchor) via
    optional callback stubs that are wired by the server context at startup.
    """

    def __init__(
        self,
        *,
        log_path: str | Path | None = None,
        rotation: LogRotationConfig | None = None,
        max_memory_cache: int = 250,
    ) -> None:
        self.rotation = rotation or LogRotationConfig()
        self._max_memory_cache = max(max_memory_cache, 1)
        self._memory_cache: deque[GovernanceEventLogEntry] = deque(maxlen=self._max_memory_cache)
        self._lock = os.environ.get("HLF_GOV_LOG_LOCK")  # advisory; real lock is GIL for CPython

        if log_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            log_dir = repo_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "governance_events.jsonl"
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Runtime and memory integration callbacks (wired by server context)
        self._memory_anchor_fn: Callable[[dict[str, Any]], None] | None = None
        self._runtime_anchor_fn: Callable[[dict[str, Any]], None] | None = None

        # Load recent entries from disk into memory cache on startup
        self._hydrate_cache()

    # ── Anchor wiring ──────────────────────────────────────────────────────────

    def wire_memory_anchor(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback that receives every log entry for memory indexing."""
        self._memory_anchor_fn = fn

    def wire_runtime_anchor(self, fn: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback that receives every log entry for runtime trace binding."""
        self._runtime_anchor_fn = fn

    # ── Core append ─────────────────────────────────────────────────────────────

    def append(self, event_record: dict[str, Any]) -> GovernanceEventLogEntry:
        """Append a governance event record to the log."""
        payload = dict(event_record)
        timestamp_ns = int(payload.get("timestamp_ns") or time.time_ns())
        trace_ref = str(payload.get("trace_ref") or payload.get("event_ref", {}).get("trace_ref") or "")
        event_type = str(payload.get("kind") or payload.get("event_type") or "unknown")
        source = str(payload.get("source") or "unknown")
        severity = str(payload.get("severity") or "info")

        # Deterministic content hash of canonical JSON payload
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        summary = self._build_summary(payload)

        entry = GovernanceEventLogEntry(
            timestamp_ns=timestamp_ns,
            trace_ref=trace_ref,
            event_type=event_type,
            source=source,
            severity=severity,
            summary=summary,
            payload=payload,
            content_hash=content_hash,
        )

        # Write to disk with rotation
        self._write_entry(entry)

        # Update memory cache
        self._memory_cache.append(entry)

        # Integration anchors
        entry_dict = entry.to_dict()
        if self._memory_anchor_fn is not None:
            try:
                self._memory_anchor_fn(entry_dict)
            except Exception:
                logger.exception("Memory anchor callback failed")
        if self._runtime_anchor_fn is not None:
            try:
                self._runtime_anchor_fn(entry_dict)
            except Exception:
                logger.exception("Runtime anchor callback failed")

        return entry

    def append_many(self, event_records: list[dict[str, Any]]) -> list[GovernanceEventLogEntry]:
        """Append multiple event records efficiently."""
        return [self.append(rec) for rec in event_records]

    # ── Queries ─────────────────────────────────────────────────────────────────

    def get_last_n(self, n: int = 20) -> list[dict[str, Any]]:
        """Return the last N log entries as dicts (most recent first)."""
        size = max(1, min(n, self._max_memory_cache))
        return [entry.to_dict() for entry in reversed(self._memory_cache)][:size]

    def get_last_n_summaries(self, n: int = 20) -> list[str]:
        """Return operator-readable summaries for the last N entries."""
        size = max(1, min(n, self._max_memory_cache))
        return [entry.to_operator_summary() for entry in reversed(self._memory_cache)][:size]

    def get_by_trace_ref(self, trace_ref: str) -> dict[str, Any] | None:
        """Retrieve a single log entry by its trace reference."""
        for entry in reversed(self._memory_cache):
            if entry.trace_ref == trace_ref:
                return entry.to_dict()
        # Fall back to disk scan
        return self._scan_disk_by_trace_ref(trace_ref)

    def get_by_content_hash(self, content_hash: str) -> dict[str, Any] | None:
        """Retrieve a single log entry by its SHA-256 content hash."""
        for entry in reversed(self._memory_cache):
            if entry.content_hash == content_hash:
                return entry.to_dict()
        return self._scan_disk_by_content_hash(content_hash)

    def verify_integrity(self, limit: int = 1000) -> dict[str, Any]:
        """Verify content hashes for the most recent *limit* entries on disk.

        Returns a report with counts of ok/mismatch/missing-hash entries.
        """
        ok = 0
        mismatch = 0
        missing = 0
        checked = 0
        for entry_dict in self._scan_disk_reverse(limit):
            checked += 1
            stored_hash = entry_dict.get("content_hash")
            if not stored_hash:
                missing += 1
                continue
            payload = entry_dict.get("payload")
            if payload is None:
                missing += 1
                continue
            canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            computed = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if computed == stored_hash:
                ok += 1
            else:
                mismatch += 1
        return {
            "status": "ok",
            "checked": checked,
            "ok": ok,
            "mismatch": mismatch,
            "missing_hash": missing,
            "log_path": str(self.log_path),
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _build_summary(self, payload: dict[str, Any]) -> str:
        """Build a short operator-readable summary from an event payload."""
        action = str(payload.get("action") or "")
        subject = str(payload.get("subject_id") or "")
        status = str(payload.get("status") or "")
        parts: list[str] = []
        if action:
            parts.append(action)
        if subject:
            parts.append(f"subject={subject}")
        if status:
            parts.append(f"status={status}")
        if not parts:
            parts.append("event logged")
        return " | ".join(parts)

    def _write_entry(self, entry: GovernanceEventLogEntry) -> None:
        line = json.dumps(entry.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"
        line_bytes = line.encode("utf-8")

        # Rotate if needed
        if self.log_path.is_file() and self.log_path.stat().st_size + len(line_bytes) > self.rotation.max_bytes:
            self._rotate()

        with self.log_path.open("ab") as fh:
            fh.write(line_bytes)

    def _rotate(self) -> None:
        """Rotate log files, optionally compressing backups."""
        base = self.log_path
        ext = "".join(base.suffixes)  # e.g. ".jsonl"
        stem = base.name[: -len(ext)] if ext else base.name
        log_dir = base.parent

        # Shift existing backups
        for i in range(self.rotation.backup_count - 1, 0, -1):
            src = log_dir / f"{stem}.{i}{ext}"
            dst = log_dir / f"{stem}.{i + 1}{ext}"
            if src.exists():
                src.replace(dst)

        # Move current to .1
        dst1 = log_dir / f"{stem}.1{ext}"
        if self.rotation.compress_backups:
            gz_path = log_dir / f"{stem}.1{ext}.gz"
            with base.open("rb") as src_fh, gzip.open(gz_path, "wb") as gz_fh:
                gz_fh.write(src_fh.read())
            base.unlink()
        else:
            base.replace(dst1)

    def _hydrate_cache(self) -> None:
        """Read recent entries from disk into the memory cache."""
        if not self.log_path.is_file():
            return
        entries: list[GovernanceEventLogEntry] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry = GovernanceEventLogEntry(
                        timestamp_ns=int(obj.get("timestamp_ns", 0)),
                        trace_ref=str(obj.get("trace_ref", "")),
                        event_type=str(obj.get("event_type", "unknown")),
                        source=str(obj.get("source", "unknown")),
                        severity=str(obj.get("severity", "info")),
                        summary=str(obj.get("summary", "")),
                        payload=dict(obj.get("payload", {})),
                        content_hash=str(obj.get("content_hash", "")),
                    )
                    entries.append(entry)
        except Exception:
            logger.exception("Failed to hydrate governance event log cache")
        # Keep only the most recent entries that fit in the cache
        for entry in entries[-self._max_memory_cache :]:
            self._memory_cache.append(entry)

    def _scan_disk_reverse(self, limit: int) -> list[dict[str, Any]]:
        """Scan the current log file from end to beginning, returning up to *limit* entries."""
        if not self.log_path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(obj)
                if len(entries) >= limit:
                    break
        except Exception:
            logger.exception("Failed to scan governance event log")
        return entries

    def _scan_disk_by_trace_ref(self, trace_ref: str) -> dict[str, Any] | None:
        for entry_dict in self._scan_disk_reverse(limit=10000):
            if entry_dict.get("trace_ref") == trace_ref:
                return entry_dict
        return None

    def _scan_disk_by_content_hash(self, content_hash: str) -> dict[str, Any] | None:
        for entry_dict in self._scan_disk_reverse(limit=10000):
            if entry_dict.get("content_hash") == content_hash:
                return entry_dict
        return None
