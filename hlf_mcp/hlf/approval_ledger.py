from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "hlf_capsule_approvals.sqlite3"
_ZERO_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    request_id TEXT PRIMARY KEY,
    capsule_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    base_tier TEXT NOT NULL,
    requested_tier TEXT NOT NULL,
    requirements_json TEXT NOT NULL,
    requirements_hash TEXT NOT NULL,
    approval_token TEXT NOT NULL,
    status TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT '',
    decision_reason TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_lookup
ON approval_requests(capsule_id, requirements_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS approval_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    data_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_events_request
ON approval_events(request_id, id);

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
"""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized = [
        {
            "type": str(item.get("type", "")),
            "scope": str(item.get("scope", "")),
            "value": str(item.get("value", "")),
        }
        for item in requirements
    ]
    normalized.sort(key=lambda item: (item["type"], item["scope"], item["value"]))
    return normalized


def _requirements_hash(requirements: list[dict[str, Any]]) -> str:
    canonical = _canonical_json(_canonical_requirements(requirements))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_trace_id(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}{payload}".encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ApprovalRequest:
    request_id: str
    capsule_id: str
    agent_id: str
    base_tier: str
    requested_tier: str
    requirements: list[dict[str, str]]
    approval_token: str
    status: str
    operator: str
    decision_reason: str
    created_at: float
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "capsule_id": self.capsule_id,
            "agent_id": self.agent_id,
            "base_tier": self.base_tier,
            "requested_tier": self.requested_tier,
            "requirements": list(self.requirements),
            "approval_token": self.approval_token,
            "status": self.status,
            "operator": self.operator,
            "decision_reason": self.decision_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ApprovalLedger:
    def __init__(self, db_path: str | None = None) -> None:
        configured = db_path or os.environ.get("HLF_APPROVAL_LEDGER_DB")
        self._db_path = str(configured or _DEFAULT_DB_PATH)
        path_obj = Path(self._db_path)
        if self._db_path != ":memory:":
            path_obj.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return self._conn

    def _row_to_request(self, row: sqlite3.Row | None) -> ApprovalRequest | None:
        if row is None:
            return None
        return ApprovalRequest(
            request_id=str(row["request_id"]),
            capsule_id=str(row["capsule_id"]),
            agent_id=str(row["agent_id"]),
            base_tier=str(row["base_tier"]),
            requested_tier=str(row["requested_tier"]),
            requirements=json.loads(row["requirements_json"] or "[]"),
            approval_token=str(row["approval_token"]),
            status=str(row["status"]),
            operator=str(row["operator"] or ""),
            decision_reason=str(row["decision_reason"] or ""),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )

    def _last_trace_id(self, conn: sqlite3.Connection) -> str:
        row = conn.execute(
            "SELECT trace_id FROM approval_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return str(row["trace_id"]) if row else _ZERO_HASH

    def _append_event(
        self,
        conn: sqlite3.Connection,
        *,
        request_id: str,
        event_type: str,
        actor: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        prev_hash = self._last_trace_id(conn)
        payload = _canonical_json({"event": event_type, "data": data})
        trace_id = _compute_trace_id(prev_hash, payload)
        created_at = time.time()
        conn.execute(
            """
            INSERT INTO approval_events (request_id, event_type, actor, data_json, prev_hash, trace_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (request_id, event_type, actor, _canonical_json(data), prev_hash, trace_id, created_at),
        )
        return {
            "request_id": request_id,
            "event_type": event_type,
            "actor": actor,
            "data": data,
            "prev_hash": prev_hash,
            "trace_id": trace_id,
            "created_at": created_at,
        }

    def ensure_request(
        self,
        *,
        capsule_id: str,
        agent_id: str,
        base_tier: str,
        requested_tier: str,
        requirements: list[dict[str, Any]],
        approval_token: str,
    ) -> ApprovalRequest:
        canonical_requirements = _canonical_requirements(requirements)
        requirement_hash = _requirements_hash(canonical_requirements)
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM approval_requests
                WHERE capsule_id = ? AND requirements_hash = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (capsule_id, requirement_hash),
            ).fetchone()
            if existing is not None:
                return self._row_to_request(existing)  # type: ignore[return-value]

            now = time.time()
            request_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO approval_requests (
                    request_id, capsule_id, agent_id, base_tier, requested_tier,
                    requirements_json, requirements_hash, approval_token,
                    status, operator, decision_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    capsule_id,
                    agent_id,
                    base_tier,
                    requested_tier,
                    _canonical_json(canonical_requirements),
                    requirement_hash,
                    approval_token,
                    "pending",
                    "",
                    "",
                    now,
                    now,
                ),
            )
            self._append_event(
                conn,
                request_id=request_id,
                event_type="approval_requested",
                actor=agent_id,
                data={
                    "capsule_id": capsule_id,
                    "base_tier": base_tier,
                    "requested_tier": requested_tier,
                    "requirements": canonical_requirements,
                },
            )
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return self._row_to_request(row)  # type: ignore[return-value]

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return self._row_to_request(row)

    def list_requests(
        self,
        *,
        status: str | None = None,
        limit: int = 20,
        capsule_id: str | None = None,
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if status:
            filters.append("status = ?")
            params.append(status)
        if capsule_id:
            filters.append("capsule_id = ?")
            params.append(capsule_id)
        sql = "SELECT * FROM approval_requests"
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        sql += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(1, min(limit, 200)))
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_request(row).to_dict() for row in rows if self._row_to_request(row) is not None]

    def decide(
        self,
        *,
        request_id: str,
        decision: str,
        operator: str,
        approval_token: str = "",
        reason: str = "",
    ) -> ApprovalRequest:
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            request = self._row_to_request(row)
            if request is None:
                raise ValueError(f"unknown approval request: {request_id}")
            if request.status == "approved" and normalized == "approve":
                return request
            if request.status == "rejected" and normalized == "reject":
                return request
            if request.status != "pending":
                raise ValueError(f"approval request {request_id} is already {request.status}")
            if normalized == "approve" and approval_token != request.approval_token:
                raise ValueError("approval token mismatch")
            updated_at = time.time()
            new_status = "approved" if normalized == "approve" else "rejected"
            conn.execute(
                """
                UPDATE approval_requests
                SET status = ?, operator = ?, decision_reason = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (new_status, operator, reason, updated_at, request_id),
            )
            self._append_event(
                conn,
                request_id=request_id,
                event_type=f"approval_{new_status}",
                actor=operator,
                data={
                    "decision": new_status,
                    "reason": reason,
                    "capsule_id": request.capsule_id,
                },
            )
            updated = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return self._row_to_request(updated)  # type: ignore[return-value]

    def verify_chain(self) -> tuple[bool, list[str]]:
        errors: list[str] = []
        prev_hash = _ZERO_HASH
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT event_type, data_json, prev_hash, trace_id FROM approval_events ORDER BY id ASC"
            ).fetchall()
        for index, row in enumerate(rows):
            event_type = str(row["event_type"])
            data = json.loads(row["data_json"] or "{}")
            actual_prev = str(row["prev_hash"])
            if actual_prev != prev_hash:
                errors.append(
                    f"entry {index}: prev_hash mismatch expected {prev_hash[:16]} got {actual_prev[:16]}"
                )
            expected = _compute_trace_id(prev_hash, _canonical_json({"event": event_type, "data": data}))
            actual = str(row["trace_id"])
            if actual != expected:
                errors.append(
                    f"entry {index}: trace_id mismatch expected {expected[:16]} got {actual[:16]}"
                )
            prev_hash = actual or expected
        return len(errors) == 0, errors