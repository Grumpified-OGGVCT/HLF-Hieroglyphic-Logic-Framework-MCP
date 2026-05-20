"""
RouteTraceLedger — append-only, verifiable route evidence store.

Stores RouteEvidence and FallbackDecision records as an immutable,
SHA-256 chain-linked ledger.  Supports in-memory storage with optional
file and sqlite backends for persistent audit trails.

Usage::

    from hlf_mcp.hlf.routing.route_trace import RouteTraceLedger

    ledger = RouteTraceLedger()
    ledger.append_evidence(evidence)
    ledger.append_fallback(fallback)

    # Query
    records = ledger.query(node_id="node-1")
    records = ledger.query_by_time(start_ns, end_ns)
    records = ledger.query_by_policy("round_robin")

    # Export
    json_str = ledger.export_json()
    ledger.export_file("trace_audit.json")

    # Chain integrity
    is_valid = ledger.verify_chain()
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TraceRecord:
    """A single entry in the route trace ledger.

    Attributes:
        record_type: "route_evidence" or "fallback_decision".
        record_id: Unique record identifier.
        timestamp_ns: Nanosecond-resolution timestamp.
        chain_hash: SHA-256 linking this record to the previous one.
        payload: The RouteEvidence or FallbackDecision serialised as a dict.
        prev_chain_hash: SHA-256 of the previous record (for verification).
    """

    record_type: str
    record_id: str
    timestamp_ns: int
    chain_hash: str
    payload: dict[str, Any]
    prev_chain_hash: str = ""

    def compute_chain_hash(self) -> str:
        """Recompute the chain hash of this record."""
        canonical = {
            "record_type": self.record_type,
            "record_id": self.record_id,
            "timestamp_ns": self.timestamp_ns,
            "prev_chain_hash": self.prev_chain_hash,
            "payload": dict(sorted(self.payload.items()))
            if isinstance(self.payload, dict)
            else self.payload,
        }
        serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type,
            "record_id": self.record_id,
            "timestamp_ns": self.timestamp_ns,
            "chain_hash": self.chain_hash,
            "payload": self.payload,
            "prev_chain_hash": self.prev_chain_hash,
        }


class RouteTraceLedger:
    """Append-only, verifiable store for route evidence records.

    Each record is SHA-256 chain-linked to the previous one, making
    the entire ledger tamper-evident.  Supports in-memory storage
    with optional file and sqlite backends.

    Thread-safe: all append/query operations are guarded by a lock.
    """

    def __init__(self, backend: str = "memory") -> None:
        """Initialise the ledger.

        Args:
            backend: "memory", "file", or "sqlite".  When "file", records
                are written to a JSON-lines file on each append.
                When "sqlite", records are persisted to a SQLite database.
        """
        self._backend = backend
        self._records: list[TraceRecord] = []
        self._lock = threading.Lock()
        self._file_path: Path | None = None
        self._sqlite_conn: sqlite3.Connection | None = None

        if backend == "sqlite":
            self._init_sqlite(":memory:")

    # ── Backend initialisation ──────────────────────────────────────────────

    def _init_sqlite(self, db_path: str) -> None:
        """Initialise SQLite backend."""
        self._sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS trace_records (
                record_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                timestamp_ns INTEGER NOT NULL,
                chain_hash TEXT NOT NULL,
                prev_chain_hash TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL
            )
        """)
        self._sqlite_conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trace_node
            ON trace_records (record_type, timestamp_ns)
        """)
        self._sqlite_conn.commit()

    def set_file_path(self, path: str | Path) -> None:
        """Set the file path for 'file' backend."""
        self._file_path = Path(path)

    # ── Append ──────────────────────────────────────────────────────────────

    def _prev_hash(self) -> str:
        """Return the chain hash of the last record, or empty string."""
        if not self._records:
            return ""
        return self._records[-1].chain_hash

    def append_evidence(self, evidence: Any) -> TraceRecord:
        """Append a RouteEvidence record to the ledger.

        Args:
            evidence: A RouteEvidence instance to record.

        Returns:
            The TraceRecord that was appended.
        """
        return self._append(
            record_type="route_evidence",
            record_id=evidence.route_id if hasattr(evidence, "route_id") else "",
            timestamp_ns=evidence.timestamp_ns if hasattr(evidence, "timestamp_ns") else time.time_ns(),
            payload=evidence.to_dict() if hasattr(evidence, "to_dict") else {},
        )

    def append_fallback(self, fallback: Any) -> TraceRecord:
        """Append a FallbackDecision record to the ledger.

        Args:
            fallback: A FallbackDecision instance to record.

        Returns:
            The TraceRecord that was appended.
        """
        return self._append(
            record_type="fallback_decision",
            record_id=f"fallback-{fallback.primary_node}-{fallback.timestamp_ns}"
            if hasattr(fallback, "primary_node")
            else "",
            timestamp_ns=fallback.timestamp_ns if hasattr(fallback, "timestamp_ns") else time.time_ns(),
            payload=fallback.to_dict() if hasattr(fallback, "to_dict") else {},
        )

    def _append(
        self,
        record_type: str,
        record_id: str,
        timestamp_ns: int,
        payload: dict[str, Any],
    ) -> TraceRecord:
        """Internal append with chain linking."""
        prev = self._prev_hash()
        record = TraceRecord(
            record_type=record_type,
            record_id=record_id,
            timestamp_ns=timestamp_ns,
            chain_hash="",  # computed below
            payload=payload,
            prev_chain_hash=prev,
        )
        record.chain_hash = record.compute_chain_hash()

        with self._lock:
            self._records.append(record)

        # Persist based on backend
        if self._backend == "file" and self._file_path is not None:
            self._persist_file(record)
        elif self._backend == "sqlite" and self._sqlite_conn is not None:
            self._persist_sqlite(record)

        return record

    def _persist_file(self, record: TraceRecord) -> None:
        """Write a record as a JSON line to the file."""
        if self._file_path is None:
            return
        line = json.dumps(record.to_dict(), ensure_ascii=True, default=str)
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _persist_sqlite(self, record: TraceRecord) -> None:
        """Insert a record into SQLite."""
        if self._sqlite_conn is None:
            return
        payload_json = json.dumps(record.payload, ensure_ascii=True, default=str)
        self._sqlite_conn.execute(
            """INSERT OR REPLACE INTO trace_records
               (record_id, record_type, timestamp_ns, chain_hash,
                prev_chain_hash, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record.record_id,
                record.record_type,
                record.timestamp_ns,
                record.chain_hash,
                record.prev_chain_hash,
                payload_json,
            ),
        )
        self._sqlite_conn.commit()

    # ── Query ───────────────────────────────────────────────────────────────

    def query(
        self,
        route_id: str | None = None,
        node_id: str | None = None,
        policy_basis: str | None = None,
        time_start_ns: int | None = None,
        time_end_ns: int | None = None,
        record_type: str | None = None,
    ) -> list[TraceRecord]:
        """Query records by one or more filters.

        All filters are AND-ed together.  Returns matching records.
        """
        results: list[TraceRecord] = []

        with self._lock:
            for record in self._records:
                if record_type is not None and record.record_type != record_type:
                    continue
                if time_start_ns is not None and record.timestamp_ns < time_start_ns:
                    continue
                if time_end_ns is not None and record.timestamp_ns > time_end_ns:
                    continue
                if route_id is not None:
                    rid = record.payload.get("route_id", "")
                    if rid != route_id:
                        continue
                if node_id is not None:
                    # Check selected_node in evidence, or primary/final in fallback
                    sn = record.payload.get("selected_node", "")
                    pn = record.payload.get("primary_node", "")
                    fn = record.payload.get("final_node", "")
                    if node_id not in (sn, pn, fn):
                        # Also check fallback chain hop nodes
                        chain = record.payload.get("fallback_chain", [])
                        found = False
                        for hop in chain:
                            if hop.get("node_id") == node_id:
                                found = True
                                break
                        if not found:
                            continue
                if policy_basis is not None:
                    pb = record.payload.get("policy_basis", "")
                    if pb != policy_basis:
                        continue
                results.append(record)

        return results

    def query_by_time(
        self, start_ns: int, end_ns: int
    ) -> list[TraceRecord]:
        """Query records within a time window."""
        return self.query(time_start_ns=start_ns, time_end_ns=end_ns)

    def query_by_node(self, node_id: str) -> list[TraceRecord]:
        """Query all records involving a specific node."""
        return self.query(node_id=node_id)

    def query_by_policy(self, policy_basis: str) -> list[TraceRecord]:
        """Query all records for a specific policy basis."""
        return self.query(policy_basis=policy_basis)

    # ── Chain integrity ─────────────────────────────────────────────────────

    def verify_chain(self) -> tuple[bool, str]:
        """Verify the integrity of the entire SHA-256 chain.

        Returns:
            (True, "") if the chain is intact, or
            (False, error_description) if a record has been tampered with.
        """
        with self._lock:
            if not self._records:
                return True, "Ledger is empty."

            prev_hash = ""
            for idx, record in enumerate(self._records):
                # Verify prev_chain_hash links correctly
                if record.prev_chain_hash != prev_hash:
                    return (
                        False,
                        f"Chain break at record {idx} ({record.record_id}): "
                        f"prev_chain_hash '{record.prev_chain_hash}' != "
                        f"expected '{prev_hash}'.",
                    )
                # Verify this record's hash is consistent
                computed = record.compute_chain_hash()
                if computed != record.chain_hash:
                    return (
                        False,
                        f"Tamper detected at record {idx} ({record.record_id}): "
                        f"stored hash '{record.chain_hash}' != "
                        f"computed hash '{computed}'.",
                    )
                prev_hash = record.chain_hash

        return True, f"Chain verified: {len(self._records)} records intact."

    def verify_record(self, index: int) -> tuple[bool, str]:
        """Verify a single record's hash at *index*."""
        with self._lock:
            if index < 0 or index >= len(self._records):
                return False, f"Index {index} out of range (0–{len(self._records) - 1})."
            record = self._records[index]
            computed = record.compute_chain_hash()
            if computed != record.chain_hash:
                return (
                    False,
                    f"Record {index} ({record.record_id}): "
                    f"hash mismatch.",
                )
            return True, f"Record {index} verified."

    # ── Export ──────────────────────────────────────────────────────────────

    def export_json(self, pretty: bool = True) -> str:
        """Export the entire ledger as a JSON string.

        Args:
            pretty: If True, pretty-print with indentation.

        Returns:
            A JSON string of all records.
        """
        with self._lock:
            data = [record.to_dict() for record in self._records]
        indent = 2 if pretty else None
        return json.dumps(data, indent=indent, ensure_ascii=True, default=str)

    def export_file(self, path: str | Path) -> None:
        """Export the ledger to a JSON file.

        Args:
            path: File path to write to.
        """
        json_str = self.export_json(pretty=True)
        filepath = Path(path)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json_str, encoding="utf-8")

    # ── Statistics ──────────────────────────────────────────────────────────

    @property
    def record_count(self) -> int:
        """Total number of records in the ledger."""
        with self._lock:
            return len(self._records)

    def stats(self) -> dict[str, Any]:
        """Return summary statistics about the ledger."""
        with self._lock:
            evidence_count = sum(
                1 for r in self._records if r.record_type == "route_evidence"
            )
            fallback_count = sum(
                1 for r in self._records if r.record_type == "fallback_decision"
            )
            if self._records:
                first_ts = self._records[0].timestamp_ns
                last_ts = self._records[-1].timestamp_ns
                span_ns = last_ts - first_ts
            else:
                first_ts = 0
                last_ts = 0
                span_ns = 0

            return {
                "total_records": len(self._records),
                "evidence_records": evidence_count,
                "fallback_records": fallback_count,
                "first_timestamp_ns": first_ts,
                "last_timestamp_ns": last_ts,
                "time_span_ns": span_ns,
            }

    def clear(self) -> None:
        """Clear all records from the ledger."""
        with self._lock:
            self._records.clear()

    def get_record(self, index: int) -> TraceRecord | None:
        """Get a record by index."""
        with self._lock:
            if 0 <= index < len(self._records):
                return self._records[index]
            return None

    def __len__(self) -> int:
        return self.record_count

    def __getitem__(self, index: int) -> TraceRecord:
        with self._lock:
            return self._records[index]
