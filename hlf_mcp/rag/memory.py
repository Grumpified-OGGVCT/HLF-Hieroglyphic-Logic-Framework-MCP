"""
Infinite RAG Memory — SQLite-backed fact store with vector similarity.

Tiers:
  Hot  (in-process dict): active context, sub-ms access
  Warm (SQLite WAL):       persistent embeddings, ~5ms
  Cold (not implemented in this layer): long-term archive

Features:
  - SHA-256 dedup: prevents duplicate storage
  - Vector Race Protection: cosine similarity >0.98 blocks duplicates
  - 30-day decay: low-relevance facts pruned automatically
  - Merkle provenance chain per topic
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
from typing import Any


# ── Simple vector embedding (bag-of-words TF-IDF approximation) ───────────────
# Used when a proper ML embedding model is unavailable.


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bow_vector(text: str, vocab: dict[str, int] | None = None) -> dict[str, float]:
    """Build a term-frequency vector from text."""
    tokens = _tokenize(text)
    tf: dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    if tokens:
        max_tf = max(tf.values())
        tf = {k: v / max_tf for k, v in tf.items()}
    return tf


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two sparse TF vectors."""
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = math.sqrt(sum(v * v for v in a.values()))
    mag_b = math.sqrt(sum(v * v for v in b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Database schema ───────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_store (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256      TEXT    NOT NULL UNIQUE,
    content     TEXT    NOT NULL,
    topic       TEXT    NOT NULL DEFAULT '',
    confidence  REAL    NOT NULL DEFAULT 1.0,
    provenance  TEXT    NOT NULL DEFAULT 'agent',
    tags        TEXT    NOT NULL DEFAULT '[]',
    vector_json TEXT    NOT NULL DEFAULT '{}',
    created_at  REAL    NOT NULL,
    accessed_at REAL    NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rolling_context (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    summary     TEXT    NOT NULL,
    updated_at  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS merkle_chain (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic       TEXT    NOT NULL,
    prev_hash   TEXT    NOT NULL DEFAULT '',
    entry_hash  TEXT    NOT NULL,
    created_at  REAL    NOT NULL
);

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
"""

_DECAY_DAYS = 30
_DEDUP_THRESHOLD = 0.98


class RAGMemory:
    """Infinite RAG memory with hot/warm tiering."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.environ.get("HLF_MEMORY_DB", ":memory:")
        self._lock = threading.Lock()
        # Hot tier: topic → list of recent entries
        self._hot: dict[str, list[dict[str, Any]]] = {}
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Store ─────────────────────────────────────────────────────────────────

    def store(
        self,
        content: str,
        topic: str = "general",
        confidence: float = 1.0,
        provenance: str = "agent",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a fact. Returns {id, sha256, stored, duplicate_reason}."""
        sha256 = hashlib.sha256(content.encode()).hexdigest()
        tags_json = json.dumps(tags or [])
        vec = _bow_vector(content)
        vec_json = json.dumps(vec)
        now = time.time()

        with self._lock, self._connect() as conn:
            # SHA-256 exact dedup
            existing = conn.execute(
                "SELECT id FROM fact_store WHERE sha256 = ?", (sha256,)
            ).fetchone()
            if existing:
                return {
                    "id": existing["id"],
                    "sha256": sha256,
                    "stored": False,
                    "duplicate_reason": "sha256_exact_match",
                }

            # Vector race protection: check cosine similarity > 0.98
            recent = conn.execute(
                "SELECT id, sha256, vector_json FROM fact_store "
                "WHERE topic = ? ORDER BY created_at DESC LIMIT 100",
                (topic,),
            ).fetchall()
            for row in recent:
                existing_vec = json.loads(row["vector_json"] or "{}")
                sim = _cosine(vec, existing_vec)
                if sim >= _DEDUP_THRESHOLD:
                    return {
                        "id": row["id"],
                        "sha256": sha256,
                        "stored": False,
                        "duplicate_reason": f"vector_similarity_{sim:.3f}",
                    }

            # Insert
            cursor = conn.execute(
                """
                INSERT INTO fact_store
                    (sha256, content, topic, confidence, provenance, tags, vector_json, created_at, accessed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sha256, content, topic, confidence, provenance, tags_json, vec_json, now, now),
            )
            row_id = cursor.lastrowid

            # Update Merkle chain
            self._append_merkle(conn, topic, sha256)

            # Update hot tier
            if topic not in self._hot:
                self._hot[topic] = []
            self._hot[topic].append({
                "id": row_id, "content": content, "topic": topic,
                "confidence": confidence, "vector": vec,
            })

        return {"id": row_id, "sha256": sha256, "stored": True, "duplicate_reason": None}

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Query memory by semantic similarity."""
        query_vec = _bow_vector(query_text)
        now = time.time()
        decay_cutoff = now - (_DECAY_DAYS * 86400)

        with self._connect() as conn:
            sql = """
                SELECT id, content, topic, confidence, provenance, tags,
                       vector_json, created_at, accessed_at
                FROM fact_store
                WHERE confidence >= ?
                  AND created_at >= ?
            """
            params: list[Any] = [min_confidence, decay_cutoff]
            if topic:
                sql += " AND topic = ?"
                params.append(topic)
            sql += " ORDER BY confidence DESC, accessed_at DESC LIMIT 500"

            rows = conn.execute(sql, params).fetchall()

        # Score by cosine similarity
        scored: list[dict[str, Any]] = []
        for row in rows:
            vec = json.loads(row["vector_json"] or "{}")
            sim = _cosine(query_vec, vec)
            scored.append({
                "id": row["id"],
                "content": row["content"],
                "topic": row["topic"],
                "confidence": row["confidence"],
                "provenance": row["provenance"],
                "tags": json.loads(row["tags"] or "[]"),
                "similarity": round(sim, 4),
                "created_at": row["created_at"],
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        results = scored[:top_k]

        # Update access stats
        if results:
            ids = [r["id"] for r in results]
            with self._connect() as conn:
                conn.executemany(
                    "UPDATE fact_store SET accessed_at=?, access_count=access_count+1 WHERE id=?",
                    [(now, rid) for rid in ids],
                )

        return {"results": results, "count": len(results), "query": query_text}

    # ── Merkle chain ──────────────────────────────────────────────────────────

    def _append_merkle(self, conn: sqlite3.Connection, topic: str, entry_hash: str) -> None:
        last = conn.execute(
            "SELECT entry_hash FROM merkle_chain WHERE topic=? ORDER BY id DESC LIMIT 1",
            (topic,),
        ).fetchone()
        prev_hash = last["entry_hash"] if last else ""
        chain_hash = hashlib.sha256(f"{prev_hash}{entry_hash}".encode()).hexdigest()
        conn.execute(
            "INSERT INTO merkle_chain (topic, prev_hash, entry_hash, created_at) VALUES (?,?,?,?)",
            (topic, prev_hash, chain_hash, time.time()),
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return memory store statistics."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM fact_store").fetchone()["n"]
            topics = conn.execute(
                "SELECT topic, COUNT(*) AS n FROM fact_store GROUP BY topic ORDER BY n DESC LIMIT 10"
            ).fetchall()
            chain_depth = conn.execute("SELECT COUNT(*) AS n FROM merkle_chain").fetchone()["n"]
        return {
            "total_facts": total,
            "merkle_chain_depth": chain_depth,
            "hot_tier_topics": len(self._hot),
            "top_topics": [{"topic": r["topic"], "count": r["n"]} for r in topics],
            "db_path": self._db_path,
        }

    # ── Decay pruning ─────────────────────────────────────────────────────────

    def prune_decay(self) -> int:
        """Prune facts older than DECAY_DAYS with low confidence."""
        cutoff = time.time() - (_DECAY_DAYS * 86400)
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM fact_store WHERE created_at < ? AND confidence < 0.5",
                (cutoff,),
            )
            return result.rowcount
