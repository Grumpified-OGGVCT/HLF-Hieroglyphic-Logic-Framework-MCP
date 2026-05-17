"""
HLF → Msty Claw Audit Trail Bridge.

Consumes Msty Claw's event stream and produces HLF-governed evidence summaries
with causal-chain tracing, natural-language recourse query, and Merkle-chained
weekly evidence exports.

Storage: SQLite (same pattern as RAGMemory in hlf_mcp/rag/memory.py)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Dataclasses ─────────────────────────────────────────────────────────────────


@dataclass
class AuditEvent:
    """A single auditable event in Msty Claw's event stream."""

    event_id: str
    event_type: str  # tool_invoked|memory_written|brief_mutated|subagent_spawned|approval_requested|approval_granted|approval_denied|session_started
    timestamp: str  # ISO8601
    triggering_intent_id: str
    actor: str  # "main_agent"|"subagent:<name>"
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    constraint_checks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CausalChain:
    """Trace from root intent through all downstream effects."""

    root_intent: AuditEvent | None
    chain: list[AuditEvent] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    affected_memories: list[str] = field(default_factory=list)


@dataclass
class RecourseResult:
    """Answer from a natural-language recourse query with supporting evidence."""

    answer: str
    supporting_events: list[AuditEvent] = field(default_factory=list)
    confidence: float = 1.0


# ── Schema ──────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id            TEXT PRIMARY KEY,
    event_type          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    triggering_intent_id TEXT NOT NULL DEFAULT '',
    actor               TEXT NOT NULL DEFAULT 'main_agent',
    payload_json        TEXT NOT NULL DEFAULT '{}',
    session_id          TEXT NOT NULL DEFAULT '',
    constraint_checks_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS merkle_chain (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT NOT NULL DEFAULT 'msty_audit',
    prev_hash   TEXT NOT NULL DEFAULT '',
    entry_hash  TEXT NOT NULL,
    created_at  REAL NOT NULL
);

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
"""

_VALID_EVENT_TYPES = frozenset({
    "tool_invoked",
    "memory_written",
    "brief_mutated",
    "subagent_spawned",
    "approval_requested",
    "approval_granted",
    "approval_denied",
    "session_started",
})

# ── NL Recourse keyword maps ────────────────────────────────────────────────────

_TOOL_KEYWORDS: dict[str, str] = {
    "delete": "file_write",
    "deleted": "file_write",
    "removed": "file_write",
    "wrote": "file_write",
    "created": "file_write",
    "read": "file_read",
    "executed": "shell",
    "ran": "shell",
    "called": "shell",
    "approved": "approval_granted",
    "denied": "approval_denied",
    "requested": "approval_requested",
}


# ── Bridge ──────────────────────────────────────────────────────────────────────


class MstyAuditBridge:
    """HLF-governed audit trail for Msty Claw events.

    Usage::

        bridge = MstyAuditBridge(":memory:")
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type="tool_invoked",
            timestamp=datetime.now(timezone.utc).isoformat(),
            triggering_intent_id="deploy-app",
            actor="main_agent",
            payload={"tool_name": "shell", "args": {"command": "echo hi"}, "duration_ms": 42},
            session_id="sess-001",
        )
        bridge.ingest_event(event)
        chain = bridge.trace_causal_chain(event.event_id)
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.environ.get("HLF_AUDIT_DB", ":memory:")
        self._conn: sqlite3.Connection = sqlite3.connect(
            self._db_path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _connect(self) -> sqlite3.Connection:
        """Return the shared connection (re-entrant safe)."""
        return self._conn

    # ── Merkle helpers ──────────────────────────────────────────────────────────

    def _append_merkle(self, topic: str, entry_hash: str) -> None:
        conn = self._connect()
        last = conn.execute(
            "SELECT entry_hash FROM merkle_chain WHERE topic=? ORDER BY id DESC LIMIT 1",
            (topic,),
        ).fetchone()
        prev_hash = last["entry_hash"] if last else ""
        chain_hash = hashlib.sha256(
            f"{prev_hash}{entry_hash}".encode()
        ).hexdigest()
        conn.execute(
            "INSERT INTO merkle_chain (topic, prev_hash, entry_hash, created_at) "
            "VALUES (?,?,?,?)",
            (topic, prev_hash, chain_hash, datetime.now(timezone.utc).timestamp()),
        )
        conn.commit()

    def _merkle_root(self, topic: str = "msty_audit") -> str:
        """Return the Merkle root hash for the given topic."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT entry_hash FROM merkle_chain WHERE topic=? ORDER BY id",
            (topic,),
        ).fetchall()
        if not rows:
            return hashlib.sha256(b"").hexdigest()
        hashes = [r["entry_hash"] for r in rows]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256((hashes[i] + hashes[i + 1]).encode()).hexdigest()
                for i in range(0, len(hashes), 2)
            ]
        return hashes[0]

    # ── Row → AuditEvent ────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_event(row: sqlite3.Row | dict[str, Any]) -> AuditEvent:
        payload = json.loads(row["payload_json"] if isinstance(row, sqlite3.Row) else row.get("payload_json", "{}"))
        constraint_checks = json.loads(
            row["constraint_checks_json"]
            if isinstance(row, sqlite3.Row)
            else row.get("constraint_checks_json", "[]")
        )
        return AuditEvent(
            event_id=row["event_id"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            triggering_intent_id=row["triggering_intent_id"],
            actor=row["actor"],
            payload=payload,
            session_id=row["session_id"],
            constraint_checks=constraint_checks,
        )

    # ── 1. Ingest ───────────────────────────────────────────────────────────────

    def ingest_event(self, event: AuditEvent) -> str:
        """Store an event. Reject duplicates. Return event_id.

        Raises ValueError on empty/duplicate event_id or invalid event_type.
        """
        if not event.event_id or not event.event_id.strip():
            raise ValueError("event_id must be non-empty")
        if event.event_type not in _VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid event_type: {event.event_type!r}. "
                f"Must be one of {sorted(_VALID_EVENT_TYPES)}"
            )

        conn = self._connect()
        existing = conn.execute(
            "SELECT 1 FROM audit_events WHERE event_id = ?", (event.event_id,)
        ).fetchone()
        if existing:
            raise ValueError(f"Duplicate event_id: {event.event_id}")

        conn.execute(
            """INSERT INTO audit_events
               (event_id, event_type, timestamp, triggering_intent_id, actor,
                payload_json, session_id, constraint_checks_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                event.event_id,
                event.event_type,
                event.timestamp,
                event.triggering_intent_id,
                event.actor,
                json.dumps(event.payload),
                event.session_id,
                json.dumps(event.constraint_checks),
            ),
        )
        conn.commit()

        # Merkle append
        entry_hash = hashlib.sha256(
            f"{event.event_id}{event.event_type}{event.timestamp}".encode()
        ).hexdigest()
        self._append_merkle("msty_audit", entry_hash)

        return event.event_id

    # ── 2. Query ────────────────────────────────────────────────────────────────

    def query_events(self, **filters: Any) -> list[AuditEvent]:
        """Query events with optional filters.

        Supported filters:
            time_range: tuple[str, str]  — (start_iso, end_iso)
            event_type: str
            actor: str
            triggering_intent_id: str
            tool_name: str              — matches payload.tool_name
            session_id: str
        """
        conn = self._connect()
        clauses: list[str] = ["1=1"]
        params: list[Any] = []

        time_range: tuple[str, str] | None = filters.get("time_range")
        if time_range is not None:
            clauses.append("timestamp >= ? AND timestamp <= ?")
            params.extend(time_range)

        for col in ("event_type", "actor", "triggering_intent_id", "session_id"):
            val = filters.get(col)
            if val is not None:
                clauses.append(f"{col} = ?")
                params.append(val)

        tool_name = filters.get("tool_name")
        if tool_name is not None:
            clauses.append("json_extract(payload_json, '$.tool_name') = ?")
            params.append(tool_name)

        query = f"SELECT * FROM audit_events WHERE {' AND '.join(clauses)} ORDER BY timestamp"
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    # ── 3. Causal chain trace ───────────────────────────────────────────────────

    def trace_causal_chain(self, event_id: str) -> CausalChain:
        """Trace backward to root intent and forward to all downstream effects.

        Returns CausalChain with root_intent, chain (chronological), affected_files,
        and affected_memories.
        """
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM audit_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Event not found: {event_id}")

        seed = self._row_to_event(row)
        intent_id = seed.triggering_intent_id

        # All events with the same triggering_intent_id
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE triggering_intent_id = ? ORDER BY timestamp",
            (intent_id,),
        ).fetchall()

        chain = [self._row_to_event(r) for r in rows]

        # Find root (earliest event for this intent)
        root = chain[0] if chain else None

        # Collect affected files and memories
        affected_files: list[str] = []
        affected_memories: list[str] = []
        for ev in chain:
            p = ev.payload
            if ev.event_type == "tool_invoked":
                tool = p.get("tool_name", "")
                args = p.get("args", {})
                if tool in ("file_write", "file_read") and "path" in args:
                    affected_files.append(str(args["path"]))
                if "file" in args:
                    affected_files.append(str(args["file"]))
                if "target" in args:
                    affected_files.append(str(args["target"]))
            elif ev.event_type == "memory_written":
                key = p.get("key", p.get("pack_id", ""))
                if key:
                    affected_memories.append(str(key))

        return CausalChain(
            root_intent=root,
            chain=chain,
            affected_files=sorted(set(affected_files)),
            affected_memories=sorted(set(affected_memories)),
        )

    # ── 4. NL Recourse Query ────────────────────────────────────────────────────

    def recourse_query(self, question: str) -> RecourseResult:
        """Answer a natural-language question using the audit trail.

        Examples:
            "why was file X deleted?"
            "show events between 14:00-14:05"
            "who approved the deploy?"
            "what tools did the main agent run?"

        Uses keyword heuristics (same spirit as translator.py) to parse intent.
        """
        q = question.lower().strip()
        conn = self._connect()
        supporting: list[AuditEvent] = []
        confidence: float = 1.0

        # ── Time-range detection ────────────────────────────────────────────────
        import re

        time_pattern = re.findall(
            r"(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:-|to)\s*(\d{1,2}:\d{2}(?::\d{2})?)", q
        )
        if time_pattern:
            start_t, end_t = time_pattern[0]
            # Try to figure out the date from question context or use today
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            start_iso = f"{today}T{start_t}:00" if len(start_t) <= 5 else f"{today}T{start_t}"
            end_iso = f"{today}T{end_t}:00" if len(end_t) <= 5 else f"{today}T{end_t}"
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp",
                (start_iso, end_iso),
            ).fetchall()
            supporting = [self._row_to_event(r) for r in rows]
            confidence = 0.9 if supporting else 0.3
            return RecourseResult(
                answer=(
                    f"Found {len(supporting)} event(s) between {start_t} and {end_t}."
                    if supporting
                    else f"No events found between {start_t} and {end_t}."
                ),
                supporting_events=supporting,
                confidence=confidence,
            )

        # ── "why" questions → check deleted/removed/wrote keywords ──────────────
        if "why" in q:
            for kw, tool_name in _TOOL_KEYWORDS.items():
                if kw in q:
                    # Search tool_invoked events matching the tool_name in payload
                    rows = conn.execute(
                        "SELECT * FROM audit_events WHERE event_type = 'tool_invoked'"
                        " AND json_extract(payload_json, '$.tool_name') = ?"
                        " ORDER BY timestamp DESC",
                        (tool_name,),
                    ).fetchall()
                    supporting = [self._row_to_event(r) for r in rows]
                    # If no direct tool match, broader search
                    if not supporting:
                        rows = conn.execute(
                            "SELECT * FROM audit_events WHERE event_type = ? ORDER BY timestamp DESC",
                            (tool_name,),
                        ).fetchall()
                        supporting = [self._row_to_event(r) for r in rows]
                    # Try to find a file name mentioned
                    file_match = re.findall(r"file\s+['\"]?([^\s'\"]+)['\"]?", q)
                    if file_match:
                        supporting = [
                            e
                            for e in supporting
                            if file_match[0].lower()
                            in json.dumps(e.payload).lower()
                        ]
                    confidence = 0.7 if supporting else 0.2
                    return RecourseResult(
                        answer=(
                            f"Found {len(supporting)} event(s) related to '{kw}'. "
                            f"Check supporting_events for details."
                            if supporting
                            else f"No events found explaining why {kw} occurred."
                        ),
                        supporting_events=supporting[:20],
                        confidence=confidence,
                    )

            # Fallback for "why" without specific keyword: return all tool_invoked events
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE event_type = 'tool_invoked' ORDER BY timestamp DESC"
            ).fetchall()
            # Try to find a file name
            file_match = re.findall(r"file\s+['\"]?([^\s'\"]+)['\"]?", q)
            supporting = [self._row_to_event(r) for r in rows]
            if file_match:
                supporting = [
                    e for e in supporting
                    if file_match[0].lower() in json.dumps(e.payload).lower()
                ]
            return RecourseResult(
                answer=(
                    f"Found {len(supporting)} tool invocation(s)."
                    if supporting
                    else "No tool invocations found."
                ),
                supporting_events=supporting[:20],
                confidence=0.5 if supporting else 0.1,
            )

        # ── "who" questions → approval events ───────────────────────────────────
        if "who" in q:
            ev_type = "approval_granted" if "approved" in q or "granted" in q else "approval_denied"
            rows = conn.execute(
                "SELECT * FROM audit_events WHERE event_type = ? ORDER BY timestamp DESC",
                (ev_type,),
            ).fetchall()
            supporting = [self._row_to_event(r) for r in rows]
            confidence = 0.8 if supporting else 0.3
            return RecourseResult(
                answer=(
                    f"Found {len(supporting)} approval-related event(s)."
                    if supporting
                    else "No approval events found."
                ),
                supporting_events=supporting[:20],
                confidence=confidence,
            )

        # ── "what" questions → general search across payload ────────────────────
        if "what" in q:
            # Search for keywords in payload
            search_words = [w for w in q.split() if len(w) > 3 and w not in ("what", "tools", "did", "the", "agent", "run", "that")]
            if search_words:
                rows = conn.execute(
                    "SELECT * FROM audit_events ORDER BY timestamp DESC"
                ).fetchall()
                all_events = [self._row_to_event(r) for r in rows]
                for ev in all_events:
                    payload_str = json.dumps(ev.payload).lower()
                    if any(w in payload_str for w in search_words):
                        supporting.append(ev)
                confidence = 0.6 if supporting else 0.2
                return RecourseResult(
                    answer=(
                        f"Found {len(supporting)} event(s) matching '{' '.join(search_words)}'."
                        if supporting
                        else f"No events found matching '{' '.join(search_words)}'."
                    ),
                    supporting_events=supporting[:20],
                    confidence=confidence,
                )

        # ── Fallback: full-text-ish search across payload ───────────────────────
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE payload_json LIKE ? ORDER BY timestamp DESC",
            (f"%{q}%",),
        ).fetchall()
        if rows:
            supporting = [self._row_to_event(r) for r in rows]
        else:
            rows = conn.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 50"
            ).fetchall()
            supporting = [self._row_to_event(r) for r in rows]

        return RecourseResult(
            answer=(
                f"Found {len(supporting)} event(s) matching your query."
                if supporting
                else "No events found."
            ),
            supporting_events=supporting[:20],
            confidence=0.5 if supporting else 0.0,
        )

    # ── 5. Session Summary ──────────────────────────────────────────────────────

    def generate_session_summary(self, session_id: str) -> dict[str, Any]:
        """Generate summary stats for a session.

        Returns dict with:
            tool_counts, memory_mutations, approvals, files_touched,
            violations, duration, event_count
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()

        events = [self._row_to_event(r) for r in rows]
        if not events:
            return {
                "session_id": session_id,
                "event_count": 0,
                "tool_counts": {},
                "memory_mutations": 0,
                "approvals": {"granted": 0, "denied": 0, "requested": 0},
                "files_touched": [],
                "violations": 0,
                "duration": None,
            }

        tool_counts: dict[str, int] = {}
        memory_mutations = 0
        approvals = {"granted": 0, "denied": 0, "requested": 0}
        files_touched: list[str] = []
        violations = 0

        for ev in events:
            p = ev.payload
            if ev.event_type == "tool_invoked":
                tn = p.get("tool_name", "unknown")
                tool_counts[tn] = tool_counts.get(tn, 0) + 1
                for field in ("path", "file", "target"):
                    if field in (p.get("args") or {}):
                        files_touched.append(str(p["args"][field]))
            elif ev.event_type == "memory_written":
                memory_mutations += 1
            elif ev.event_type == "approval_granted":
                approvals["granted"] += 1
            elif ev.event_type == "approval_denied":
                approvals["denied"] += 1
            elif ev.event_type == "approval_requested":
                approvals["requested"] += 1
            # Count constraint violations
            for cc in ev.constraint_checks:
                if not cc.get("passed", True):
                    violations += 1

        # Duration
        duration = None
        if len(events) >= 2:
            try:
                t0 = datetime.fromisoformat(events[0].timestamp)
                t1 = datetime.fromisoformat(events[-1].timestamp)
                duration = (t1 - t0).total_seconds()
            except (ValueError, TypeError):
                pass

        return {
            "session_id": session_id,
            "event_count": len(events),
            "tool_counts": tool_counts,
            "memory_mutations": memory_mutations,
            "approvals": approvals,
            "files_touched": sorted(set(files_touched)),
            "violations": violations,
            "duration": duration,
        }

    # ── 6. Weekly Evidence Export ───────────────────────────────────────────────

    def export_weekly_evidence(self) -> str:
        """Export HLF-compatible evidence JSON with Merkle chain.

        Returns a JSON string with structure:
            {version, generated_at, merkle_root, merkle_chain_depth, events: [...]}
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM audit_events ORDER BY timestamp"
        ).fetchall()
        events = [self._row_to_event(r) for r in rows]
        merkle_root = self._merkle_root("msty_audit")
        chain_depth = conn.execute(
            "SELECT COUNT(*) AS n FROM merkle_chain WHERE topic='msty_audit'"
        ).fetchone()["n"]

        evidence = {
            "version": "HLF-v3",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "merkle_root": merkle_root,
            "merkle_chain_depth": chain_depth,
            "event_count": len(events),
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "timestamp": e.timestamp,
                    "triggering_intent_id": e.triggering_intent_id,
                    "actor": e.actor,
                    "payload": e.payload,
                    "session_id": e.session_id,
                    "constraint_checks": e.constraint_checks,
                }
                for e in events
            ],
        }
        return json.dumps(evidence, indent=2)

    # ── 7. Archive Session (NDJSON + Merkle root) ───────────────────────────────

    def archive_session(self, session_id: str, output_path: str) -> str:
        """Export session events as NDJSON with a Merkle root footer.

        Writes to *output_path* and returns the Merkle root.
        """
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
        events = [self._row_to_event(r) for r in rows]

        path = Path(output_path)
        hashes: list[str] = []
        with path.open("w", encoding="utf-8") as fh:
            for ev in events:
                record = {
                    "event_id": ev.event_id,
                    "event_type": ev.event_type,
                    "timestamp": ev.timestamp,
                    "triggering_intent_id": ev.triggering_intent_id,
                    "actor": ev.actor,
                    "payload": ev.payload,
                    "session_id": ev.session_id,
                    "constraint_checks": ev.constraint_checks,
                }
                line = json.dumps(record, ensure_ascii=False)
                fh.write(line + "\n")
                hashes.append(hashlib.sha256(line.encode()).hexdigest())

            # Compute Merkle root over the NDJSON line hashes
            merkle_root = self._compute_root_from_hashes(hashes)
            # Footer
            footer = json.dumps(
                {"__hlf_footer__": True, "merkle_root": merkle_root, "event_count": len(events)}
            )
            fh.write(footer + "\n")

        return merkle_root

    @staticmethod
    def _compute_root_from_hashes(hashes: list[str]) -> str:
        if not hashes:
            return hashlib.sha256(b"").hexdigest()
        working = list(hashes)
        while len(working) > 1:
            if len(working) % 2 == 1:
                working.append(working[-1])
            working = [
                hashlib.sha256((working[i] + working[i + 1]).encode()).hexdigest()
                for i in range(0, len(working), 2)
            ]
        return working[0]

    # ── Convenience: event count ────────────────────────────────────────────────

    @property
    def event_count(self) -> int:
        conn = self._connect()
        return conn.execute("SELECT COUNT(*) AS n FROM audit_events").fetchone()["n"]
