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

from hlf_mcp.hlf.governance_events import governance_event_ref

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "db" / "hlf_capsule_approvals.sqlite3"
_ZERO_HASH = "0" * 64


class ApprovalDecisionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        request_id: str = "",
        capsule_id: str = "",
        agent_id: str = "",
        operator: str = "",
        decision: str = "",
        status: str = "",
        reason_code: str = "approval_decision_error",
        latest_event_ref: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.capsule_id = capsule_id
        self.agent_id = agent_id
        self.operator = operator
        self.decision = decision
        self.status = status
        self.reason_code = reason_code
        self.latest_event_ref = dict(latest_event_ref or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "capsule_id": self.capsule_id,
            "agent_id": self.agent_id,
            "operator": self.operator,
            "decision": self.decision,
            "status": self.status,
            "reason_code": self.reason_code,
            "latest_event_ref": dict(self.latest_event_ref),
            "error": str(self),
        }


class ApprovalTokenMismatchError(ApprovalDecisionError):
    def __init__(self, message: str = "approval token mismatch", **kwargs: Any) -> None:
        super().__init__(message, reason_code="approval_token_mismatch", **kwargs)

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
    return hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()


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
    latest_event_ref: dict[str, str] | None = None
    latest_trace_id: str = ""
    latest_event_type: str = ""
    approval_event_count: int = 0

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
            "latest_event_ref": dict(self.latest_event_ref) if self.latest_event_ref else None,
            "latest_trace_id": self.latest_trace_id,
            "latest_event_type": self.latest_event_type,
            "approval_event_count": self.approval_event_count,
        }


@dataclass(slots=True)
class ApprovalEvent:
    request_id: str
    event_type: str
    actor: str
    data: dict[str, Any]
    prev_hash: str
    trace_id: str
    created_at: float

    @property
    def event_ref(self) -> dict[str, str]:
        return governance_event_ref(
            kind="approval_transition",
            event_id=self.trace_id[:16],
            trace_id=self.trace_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "data": dict(self.data),
            "prev_hash": self.prev_hash,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "event_ref": self.event_ref,
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

    def _request_event_summary(
        self, conn: sqlite3.Connection, request_id: str
    ) -> tuple[dict[str, str] | None, str, str, int]:
        latest = conn.execute(
            """
            SELECT event_type, trace_id
            FROM approval_events
            WHERE request_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (request_id,),
        ).fetchone()
        count_row = conn.execute(
            "SELECT COUNT(*) AS event_count FROM approval_events WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        latest_trace_id = str(latest["trace_id"]) if latest else ""
        latest_event_type = str(latest["event_type"]) if latest else ""
        latest_event_ref = (
            governance_event_ref(
                kind="approval_transition",
                event_id=latest_trace_id[:16],
                trace_id=latest_trace_id,
            )
            if latest_trace_id
            else None
        )
        return (
            latest_event_ref,
            latest_trace_id,
            latest_event_type,
            int(count_row["event_count"]) if count_row else 0,
        )

    def _row_to_request(
        self, row: sqlite3.Row | None, conn: sqlite3.Connection | None = None
    ) -> ApprovalRequest | None:
        if row is None:
            return None
        active_conn = conn or self._connect()
        latest_event_ref, latest_trace_id, latest_event_type, approval_event_count = (
            self._request_event_summary(active_conn, str(row["request_id"]))
        )
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
            latest_event_ref=latest_event_ref,
            latest_trace_id=latest_trace_id,
            latest_event_type=latest_event_type,
            approval_event_count=approval_event_count,
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
    ) -> ApprovalEvent:
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
        return ApprovalEvent(
            request_id=request_id,
            event_type=event_type,
            actor=actor,
            data=data,
            prev_hash=prev_hash,
            trace_id=trace_id,
            created_at=created_at,
        )

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
                return self._row_to_request(existing, conn)  # type: ignore[return-value]

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
            return self._row_to_request(row, conn)  # type: ignore[return-value]

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return self._row_to_request(row, conn)

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
            return [
                self._row_to_request(row, conn).to_dict()
                for row in rows
                if self._row_to_request(row, conn) is not None
            ]

    def list_events(self, request_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT request_id, event_type, actor, data_json, prev_hash, trace_id, created_at
                FROM approval_events
                WHERE request_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (request_id, max(1, min(limit, 200))),
            ).fetchall()
            return [
                ApprovalEvent(
                    request_id=str(row["request_id"]),
                    event_type=str(row["event_type"]),
                    actor=str(row["actor"]),
                    data=json.loads(row["data_json"] or "{}"),
                    prev_hash=str(row["prev_hash"]),
                    trace_id=str(row["trace_id"]),
                    created_at=float(row["created_at"]),
                ).to_dict()
                for row in rows
            ]

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
            raise ApprovalDecisionError(
                "decision must be 'approve' or 'reject'",
                request_id=request_id,
                operator=operator,
                decision=normalized,
                reason_code="invalid_approval_decision",
            )
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            request = self._row_to_request(row)
            if request is None:
                raise ApprovalDecisionError(
                    f"unknown approval request: {request_id}",
                    request_id=request_id,
                    operator=operator,
                    decision=normalized,
                    reason_code="unknown_approval_request",
                )
            if request.status == "approved" and normalized == "approve":
                return request
            if request.status == "rejected" and normalized == "reject":
                return request
            if request.status != "pending":
                raise ApprovalDecisionError(
                    f"approval request {request_id} is already {request.status}",
                    request_id=request.request_id,
                    capsule_id=request.capsule_id,
                    agent_id=request.agent_id,
                    operator=operator,
                    decision=normalized,
                    status=request.status,
                    reason_code="approval_request_already_resolved",
                    latest_event_ref=request.latest_event_ref,
                )
            if normalized == "approve" and approval_token != request.approval_token:
                raise ApprovalTokenMismatchError(
                    request_id=request.request_id,
                    capsule_id=request.capsule_id,
                    agent_id=request.agent_id,
                    operator=operator,
                    decision=normalized,
                    status=request.status,
                    latest_event_ref=request.latest_event_ref,
                )
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
            return self._row_to_request(updated, conn)  # type: ignore[return-value]

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
            expected = _compute_trace_id(
                prev_hash, _canonical_json({"event": event_type, "data": data})
            )
            actual = str(row["trace_id"])
            if actual != expected:
                errors.append(
                    f"entry {index}: trace_id mismatch expected {expected[:16]} got {actual[:16]}"
                )
            prev_hash = actual or expected
        return len(errors) == 0, errors
