"""
MicroSquad → SwarmGlass Bridge

Streams governed_pipeline results as SwarmGlass events, with SQLite fallback
and Merkle-chained provenance. Stdlib only — no hlf_mcp or torch imports.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


__all__ = ["MicroSquadEventEmitter"]


# ── SQL Schema ──────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS microsquad_events (
    event_id TEXT PRIMARY KEY,
    parent_id TEXT,
    stage TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    question TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    prev_hash TEXT NOT NULL DEFAULT '',
    entry_hash TEXT NOT NULL
);
"""


def _compute_merkle_hash(prev_hash: str, event_id: str, payload: dict) -> str:
    """Compute Merkle-chained hash: sha256(prev_hash + event_id + sorted payload JSON)."""
    payload_str = json.dumps(payload, sort_keys=True)
    data = prev_hash + event_id + payload_str
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ── Default DB path ─────────────────────────────────────────────────────────

def _default_db_path() -> str:
    """Return default SQLite path relative to this module or cwd."""
    env_path = os.environ.get("SWARMGLASS_DB_PATH")
    if env_path:
        return env_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "microsquad_events.db")


# ── MicroSquadEventEmitter ──────────────────────────────────────────────────

class MicroSquadEventEmitter:
    """Emits pipeline events to SwarmGlass bridge (HTTP) with SQLite fallback.

    Each event is Merkle-chained for audit integrity.
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or _default_db_path()
        self._conn: Optional[sqlite3.Connection] = None
        self._prev_hash: str = ""
        self._event_chain: List[str] = []  # event IDs in order
        self._events: List[Dict[str, Any]] = []  # full event records
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with schema."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _insert_event(
        self,
        event_id: str,
        parent_id: str,
        stage: str,
        event_type: str,
        payload: dict,
        question: str = None,
    ) -> None:
        """Insert an event record into SQLite with Merkle hash."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry_hash = _compute_merkle_hash(self._prev_hash, event_id, payload)

        self._conn.execute(
            """INSERT INTO microsquad_events
               (event_id, parent_id, stage, event_type, timestamp, question, payload_json, prev_hash, entry_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                parent_id,
                stage,
                event_type,
                timestamp,
                question,
                json.dumps(payload),
                self._prev_hash,
                entry_hash,
            ),
        )
        self._conn.commit()

        self._prev_hash = entry_hash
        self._event_chain.append(event_id)
        self._events.append({
            "event_id": event_id,
            "parent_id": parent_id,
            "stage": stage,
            "event_type": event_type,
            "timestamp": timestamp,
            "question": question,
            "payload": payload,
            "prev_hash": self._prev_hash,
            "entry_hash": entry_hash,
        })

    def _try_post_event(self, event_type: str, payload: dict) -> bool:
        """Post event to SwarmGlass HTTP bridge. Returns True if successful."""
        try:
            data = json.dumps({
                "skill": "microsquad_event",
                "context": event_type,
                "payload": payload,
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://localhost:8767/bridge/invoke",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
            return True
        except Exception:
            return False

    # ── Public emission API ──────────────────────────────────────────────────

    def emit_stage_start(self, stage: str, metadata: dict) -> str:
        """Emit a stage-start event. Returns event_id."""
        event_id = str(uuid.uuid4())
        payload = {
            "stage": stage,
            "status": "start",
            "metadata": metadata,
        }
        self._insert_event(event_id, "", stage, "start", payload)
        self._try_post_event(f"stage_start:{stage}", payload)
        return event_id

    def emit_stage_end(self, stage: str, event_id: str, result: dict) -> str:
        """Emit a stage-end event, linked to the start event. Returns event_id."""
        end_event_id = str(uuid.uuid4())
        payload = {
            "stage": stage,
            "status": "end",
            "result": result,
        }
        self._insert_event(end_event_id, event_id, stage, "end", payload)
        self._try_post_event(f"stage_end:{stage}", payload)
        return end_event_id

    def emit_solution(self, question: str, answer: str, evidence: dict) -> str:
        """Emit the final solution event. Returns event_id."""
        event_id = str(uuid.uuid4())
        payload = {
            "question": question[:500],
            "answer": answer[:5000],
            "evidence": evidence,
        }
        self._insert_event(event_id, self._event_chain[-1] if self._event_chain else "", "pipeline", "solution", payload, question=question[:500])
        self._try_post_event("solution", payload)
        return event_id

    def emit_error(self, stage: str, error: str) -> str:
        """Emit an error event. Returns event_id."""
        event_id = str(uuid.uuid4())
        payload = {
            "stage": stage,
            "error": error,
        }
        self._insert_event(event_id, self._event_chain[-1] if self._event_chain else "", stage, "error", payload)
        self._try_post_event("error", payload)
        return event_id

    # ── Audit API ────────────────────────────────────────────────────────────

    def get_audit_chain(self) -> list:
        """Return the full ordered list of events in this emitter's chain."""
        return list(self._events)

    # ── Cloud Cost Tracking ──────────────────────────────────────────────────

    def track_cloud_usage(self, model: str, prompt_tokens: int, completion_tokens: int,
                          total_tokens: int, cost_usd: float, duration_s: float) -> str:
        """Record a cloud API call for cost tracking."""
        event_id = str(uuid.uuid4())
        payload = {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost_usd,
            "duration_s": duration_s,
        }
        self._insert_event(event_id, None, "cloud", "usage", payload)
        self._try_post_event("cloud_usage", payload)
        return event_id

    def get_cost_summary(self) -> dict:
        """Get cumulative cloud cost summary across all recorded calls."""
        rows = self._conn.execute(
            "SELECT payload_json FROM microsquad_events WHERE stage='cloud' AND event_type='usage'"
        ).fetchall()
        total_cost = 0.0
        total_tokens = 0
        call_count = len(rows)
        models_used = []
        for r in rows:
            p = json.loads(r["payload_json"])
            total_cost += p.get("cost_usd", 0)
            total_tokens += p.get("total_tokens", 0)
            model = p.get("model", "unknown")
            if model not in models_used:
                models_used.append(model)
        return {
            "calls": call_count,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "models_used": models_used,
        }

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
