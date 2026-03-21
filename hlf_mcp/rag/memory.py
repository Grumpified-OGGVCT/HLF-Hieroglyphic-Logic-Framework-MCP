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
from dataclasses import asdict, dataclass, field
from typing import Any

# ── Simple vector embedding (bag-of-words TF-IDF approximation) ───────────────
# Used when a proper ML embedding model is unavailable.


def _tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.findall(r"[\u3400-\u9fff]|[\u0600-\u06ff]+|[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", text)
    ]


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
HKS_DOMAINS = {"general-coding", "ai-engineering", "hlf-specific"}


def _timestamp_to_iso8601(value: float | int | None) -> str | None:
    if value is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(value)))


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _parse_fresh_until(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            return time.mktime(time.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            try:
                return float(normalized)
            except ValueError:
                return None
    return None


@dataclass(slots=True)
class HKSTestEvidence:
    name: str
    passed: bool
    exit_code: int | None = None
    counts: dict[str, int] | None = None
    details: dict[str, Any] | None = None


@dataclass(slots=True)
class HKSProvenance:
    source_type: str
    source: str
    collector: str
    collected_at: str
    workflow_run_url: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    artifact_path: str | None = None
    confidence: float | None = None


@dataclass(slots=True)
class HKSValidatedExemplar:
    problem: str
    validated_solution: str
    domain: str
    solution_kind: str
    provenance: HKSProvenance
    tests: list[HKSTestEvidence] = field(default_factory=list)
    supersedes: str | None = None
    topic: str = "hlf_validated_exemplars"
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    schema_version: str = "1.0"
    status: str = "validated"

    def __post_init__(self) -> None:
        if self.domain not in HKS_DOMAINS:
            raise ValueError(f"Unsupported HKS domain: {self.domain}")

    def to_content(self) -> str:
        parts = [
            self.problem,
            self.validated_solution,
            self.summary,
            self.domain,
            self.solution_kind,
        ]
        if self.tags:
            parts.append(" ".join(self.tags))
        return "\n".join(part for part in parts if part)

    def to_metadata(self) -> dict[str, Any]:
        return asdict(self)


class RAGMemory:
    """Infinite RAG memory with hot/warm tiering."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path or os.environ.get("HLF_MEMORY_DB", ":memory:")
        self._lock = threading.Lock()
        # Hot tier: topic → list of recent entries
        self._hot: dict[str, list[dict[str, Any]]] = {}
        # Persistent shared connection for `:memory:` databases (each new
        # sqlite3.connect(":memory:") would open a *distinct* empty database).
        # For file-backed paths we still share the connection for simplicity
        # and to avoid WAL conflicts between competing connections.
        self._conn: sqlite3.Connection = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._ensure_column("fact_store", "entry_kind", "TEXT NOT NULL DEFAULT 'fact'")
        self._ensure_column("fact_store", "domain", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "solution_kind", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "supersedes_sha256", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column("fact_store", "metadata_json", "TEXT NOT NULL DEFAULT '{}' ")

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        existing = {
            row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _connect(self) -> sqlite3.Connection:
        return self._conn

    def _normalize_metadata(
        self,
        *,
        metadata: dict[str, Any] | None,
        topic: str,
        confidence: float,
        provenance: str,
        entry_kind: str,
        domain: str,
        solution_kind: str,
        supersedes_sha256: str,
        created_at: float,
    ) -> dict[str, Any]:
        normalized = dict(metadata or {})
        provenance_payload = normalized.get("provenance")
        if not isinstance(provenance_payload, dict):
            provenance_payload = {}
        governed_evidence = normalized.get("governed_evidence")
        if not isinstance(governed_evidence, dict):
            governed_evidence = {}

        source_path = (
            governed_evidence.get("source_path")
            or normalized.get("artifact_path")
            or normalized.get("source_path")
            or provenance_payload.get("artifact_path")
        )
        artifact_id = governed_evidence.get("artifact_id") or normalized.get("artifact_id")
        collector = (
            governed_evidence.get("collector") or provenance_payload.get("collector") or provenance
        )
        collected_at = (
            governed_evidence.get("collected_at")
            or provenance_payload.get("collected_at")
            or _timestamp_to_iso8601(created_at)
        )
        governed_evidence.update(
            {
                "source_class": governed_evidence.get("source_class") or entry_kind,
                "source_type": governed_evidence.get("source_type")
                or provenance_payload.get("source_type")
                or entry_kind,
                "source": governed_evidence.get("source")
                or provenance_payload.get("source")
                or normalized.get("source")
                or provenance,
                "source_path": source_path,
                "artifact_id": artifact_id,
                "workflow_run_url": governed_evidence.get("workflow_run_url")
                or provenance_payload.get("workflow_run_url"),
                "branch": governed_evidence.get("branch") or provenance_payload.get("branch"),
                "commit_sha": governed_evidence.get("commit_sha")
                or provenance_payload.get("commit_sha"),
                "collector": collector,
                "collector_version": governed_evidence.get("collector_version")
                or normalized.get("collector_version"),
                "collected_at": collected_at,
                "confidence": float(
                    governed_evidence.get("confidence")
                    or provenance_payload.get("confidence")
                    or confidence
                ),
                "fresh_until": governed_evidence.get("fresh_until")
                or normalized.get("fresh_until"),
                "trust_tier": governed_evidence.get("trust_tier")
                or normalized.get("trust_tier")
                or "local",
                "operator_summary": governed_evidence.get("operator_summary")
                or normalized.get("operator_summary")
                or normalized.get("summary")
                or "",
                "revoked": _coerce_bool(
                    governed_evidence.get("revoked") or normalized.get("revoked")
                ),
                "tombstoned": _coerce_bool(
                    governed_evidence.get("tombstoned") or normalized.get("tombstoned")
                ),
                "supersedes": governed_evidence.get("supersedes") or supersedes_sha256,
                "topic": topic,
                "domain": domain,
                "solution_kind": solution_kind,
            }
        )
        normalized["governed_evidence"] = governed_evidence
        return normalized

    def _superseded_hashes(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            "SELECT DISTINCT supersedes_sha256 FROM fact_store WHERE supersedes_sha256 != ''"
        ).fetchall()
        return {
            str(row["supersedes_sha256"]).strip().lower()
            for row in rows
            if row["supersedes_sha256"]
        }

    def _build_evidence(
        self,
        *,
        row: sqlite3.Row,
        metadata: dict[str, Any],
        superseded_hashes: set[str],
        now: float,
    ) -> dict[str, Any]:
        governed = (
            metadata.get("governed_evidence")
            if isinstance(metadata.get("governed_evidence"), dict)
            else {}
        )
        provenance_payload = (
            metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
        )

        collector = (
            governed.get("collector") or provenance_payload.get("collector") or row["provenance"]
        )
        collected_at = (
            governed.get("collected_at")
            or provenance_payload.get("collected_at")
            or _timestamp_to_iso8601(row["created_at"])
        )
        source = (
            governed.get("source")
            or provenance_payload.get("source")
            or metadata.get("source")
            or row["provenance"]
        )
        source_type = (
            governed.get("source_type")
            or provenance_payload.get("source_type")
            or row["entry_kind"]
        )
        source_path = (
            governed.get("source_path")
            or metadata.get("artifact_path")
            or provenance_payload.get("artifact_path")
            or metadata.get("source_path")
        )
        artifact_id = governed.get("artifact_id") or metadata.get("artifact_id")
        workflow_run_url = governed.get("workflow_run_url") or provenance_payload.get(
            "workflow_run_url"
        )
        branch = governed.get("branch") or provenance_payload.get("branch")
        commit_sha = governed.get("commit_sha") or provenance_payload.get("commit_sha")
        operator_summary = (
            governed.get("operator_summary")
            or metadata.get("operator_summary")
            or metadata.get("summary")
            or ""
        )
        operator_identity = {
            "operator_id": str(governed.get("operator_id") or metadata.get("operator_id") or ""),
            "operator_display_name": str(
                governed.get("operator_display_name")
                or metadata.get("operator_display_name")
                or ""
            ),
            "operator_channel": str(
                governed.get("operator_channel") or metadata.get("operator_channel") or ""
            ),
        }
        collector_version = governed.get("collector_version") or metadata.get("collector_version")
        trust_tier = governed.get("trust_tier") or metadata.get("trust_tier") or "local"
        fresh_until = governed.get("fresh_until") or metadata.get("fresh_until")
        fresh_until_ts = _parse_fresh_until(fresh_until)
        freshness_status = (
            "stale" if fresh_until_ts is not None and fresh_until_ts < now else "fresh"
        )
        revoked = _coerce_bool(governed.get("revoked") or metadata.get("revoked"))
        tombstoned = _coerce_bool(governed.get("tombstoned") or metadata.get("tombstoned"))
        superseded = str(row["sha256"]).lower() in superseded_hashes
        provenance_backed = bool(provenance_payload) or any(
            [
                source_path,
                artifact_id,
                workflow_run_url,
                branch,
                commit_sha,
            ]
        )
        if tombstoned:
            state = "tombstoned"
        elif revoked:
            state = "revoked"
        elif superseded:
            state = "superseded"
        elif freshness_status == "stale":
            state = "stale"
        else:
            state = "active"

        return {
            "sha256": row["sha256"],
            "entry_kind": row["entry_kind"],
            "topic": row["topic"],
            "domain": row["domain"],
            "solution_kind": row["solution_kind"],
            "source_class": governed.get("source_class") or row["entry_kind"],
            "source_type": source_type,
            "source": source,
            "source_path": source_path,
            "artifact_id": artifact_id,
            "workflow_run_url": workflow_run_url,
            "branch": branch,
            "commit_sha": commit_sha,
            "collector": collector,
            "collector_version": collector_version,
            "collected_at": collected_at,
            "created_at": _timestamp_to_iso8601(row["created_at"]),
            "accessed_at": _timestamp_to_iso8601(row["accessed_at"]),
            "confidence": float(
                governed.get("confidence")
                or provenance_payload.get("confidence")
                or row["confidence"]
            ),
            "trust_tier": trust_tier,
            "fresh_until": fresh_until,
            "freshness_status": freshness_status,
            "revoked": revoked,
            "tombstoned": tombstoned,
            "supersedes": governed.get("supersedes") or row["supersedes_sha256"],
            "superseded": superseded,
            "state": state,
            "operator_summary": operator_summary,
            "operator_identity": operator_identity,
            "provenance_grade": "evidence-backed" if provenance_backed else "basic",
            "provenance_available": bool(collector and collected_at),
        }

    def _row_to_fact(
        self,
        *,
        row: sqlite3.Row,
        metadata: dict[str, Any],
        evidence: dict[str, Any],
        similarity: float | None = None,
    ) -> dict[str, Any]:
        result = {
            "id": row["id"],
            "sha256": row["sha256"],
            "content": row["content"],
            "topic": row["topic"],
            "confidence": row["confidence"],
            "provenance": row["provenance"],
            "tags": json.loads(row["tags"] or "[]"),
            "created_at": row["created_at"],
            "entry_kind": row["entry_kind"],
            "domain": row["domain"],
            "solution_kind": row["solution_kind"],
            "supersedes_sha256": row["supersedes_sha256"],
            "metadata": metadata,
            "evidence": evidence,
            "governance_status": evidence["state"],
        }
        if similarity is not None:
            result["similarity"] = round(similarity, 4)
        return result

    def _include_fact(
        self,
        *,
        evidence: dict[str, Any],
        include_stale: bool,
        include_superseded: bool,
        include_revoked: bool,
        require_provenance: bool,
    ) -> bool:
        if not include_revoked and (evidence["revoked"] or evidence["tombstoned"]):
            return False
        if not include_stale and evidence["freshness_status"] == "stale":
            return False
        if not include_superseded and evidence["superseded"]:
            return False
        if require_provenance and evidence["provenance_grade"] != "evidence-backed":
            return False
        return True

    # ── Store ─────────────────────────────────────────────────────────────────

    def store(
        self,
        content: str,
        topic: str = "general",
        confidence: float = 1.0,
        provenance: str = "agent",
        tags: list[str] | None = None,
        *,
        entry_kind: str = "fact",
        domain: str | None = None,
        solution_kind: str | None = None,
        supersedes_sha256: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Store a fact. Returns {id, sha256, stored, duplicate_reason}."""
        normalized_domain = self._normalize_domain(domain)
        sha256 = hashlib.sha256(content.encode()).hexdigest()
        tags_json = json.dumps(tags or [])
        vec = _bow_vector(content)
        vec_json = json.dumps(vec)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        now = time.time()
        normalized_metadata = self._normalize_metadata(
            metadata=metadata,
            topic=topic,
            confidence=confidence,
            provenance=provenance,
            entry_kind=entry_kind,
            domain=normalized_domain,
            solution_kind=solution_kind or "",
            supersedes_sha256=supersedes_sha256 or "",
            created_at=now,
        )
        metadata_json = json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True)

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
                    (
                        sha256, content, topic, confidence, provenance, tags, vector_json,
                        created_at, accessed_at, entry_kind, domain, solution_kind,
                        supersedes_sha256, metadata_json
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sha256,
                    content,
                    topic,
                    confidence,
                    provenance,
                    tags_json,
                    vec_json,
                    now,
                    now,
                    entry_kind,
                    normalized_domain,
                    solution_kind or "",
                    supersedes_sha256 or "",
                    metadata_json,
                ),
            )
            row_id = cursor.lastrowid

            # Update Merkle chain
            self._append_merkle(conn, topic, sha256)

            # Update hot tier
            if topic not in self._hot:
                self._hot[topic] = []
            self._hot[topic].append(
                {
                    "id": row_id,
                    "content": content,
                    "topic": topic,
                    "confidence": confidence,
                    "vector": vec,
                }
            )

        return {
            "id": row_id,
            "sha256": sha256,
            "stored": True,
            "duplicate_reason": None,
            "entry_kind": entry_kind,
            "domain": normalized_domain,
            "solution_kind": solution_kind or "",
            "supersedes_sha256": supersedes_sha256 or "",
            "metadata": normalized_metadata,
            "evidence": {
                "sha256": sha256,
                "entry_kind": entry_kind,
                "topic": topic,
                "domain": normalized_domain,
                "solution_kind": solution_kind or "",
                "source_class": normalized_metadata["governed_evidence"].get("source_class")
                or entry_kind,
                "source_type": normalized_metadata["governed_evidence"].get("source_type")
                or entry_kind,
                "source": normalized_metadata["governed_evidence"].get("source") or provenance,
                "source_path": normalized_metadata["governed_evidence"].get("source_path"),
                "artifact_id": normalized_metadata["governed_evidence"].get("artifact_id"),
                "workflow_run_url": normalized_metadata["governed_evidence"].get(
                    "workflow_run_url"
                ),
                "branch": normalized_metadata["governed_evidence"].get("branch"),
                "commit_sha": normalized_metadata["governed_evidence"].get("commit_sha"),
                "collector": normalized_metadata["governed_evidence"].get("collector")
                or provenance,
                "collector_version": normalized_metadata["governed_evidence"].get(
                    "collector_version"
                ),
                "collected_at": normalized_metadata["governed_evidence"].get("collected_at")
                or _timestamp_to_iso8601(now),
                "created_at": _timestamp_to_iso8601(now),
                "accessed_at": _timestamp_to_iso8601(now),
                "confidence": normalized_metadata["governed_evidence"].get(
                    "confidence", confidence
                ),
                "trust_tier": normalized_metadata["governed_evidence"].get("trust_tier", "local"),
                "fresh_until": normalized_metadata["governed_evidence"].get("fresh_until"),
                "freshness_status": "fresh",
                "revoked": normalized_metadata["governed_evidence"].get("revoked", False),
                "tombstoned": normalized_metadata["governed_evidence"].get("tombstoned", False),
                "supersedes": normalized_metadata["governed_evidence"].get("supersedes")
                or supersedes_sha256
                or "",
                "superseded": False,
                "state": "active",
                "operator_summary": normalized_metadata["governed_evidence"].get("operator_summary")
                or "",
                "provenance_grade": "evidence-backed"
                if bool(normalized_metadata.get("provenance"))
                or any(
                    [
                        normalized_metadata["governed_evidence"].get("source_path"),
                        normalized_metadata["governed_evidence"].get("artifact_id"),
                        normalized_metadata["governed_evidence"].get("workflow_run_url"),
                        normalized_metadata["governed_evidence"].get("branch"),
                        normalized_metadata["governed_evidence"].get("commit_sha"),
                    ]
                )
                else "basic",
                "provenance_available": True,
            },
        }

    def govern_fact(
        self,
        *,
        action: str,
        fact_id: int | None = None,
        sha256: str | None = None,
        operator_summary: str = "",
        governed_by: str = "operator",
        reason: str = "",
        operator_id: str = "",
        operator_display_name: str = "",
        operator_channel: str = "",
    ) -> dict[str, Any] | None:
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"revoke", "tombstone", "reinstate"}:
            raise ValueError(f"unsupported governance action: {action!r}")
        if fact_id is None and not sha256:
            raise ValueError("fact_id or sha256 is required")

        with self._lock, self._connect() as conn:
            if fact_id is not None:
                row = conn.execute(
                    "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                    "created_at, accessed_at, entry_kind, domain, solution_kind, "
                    "supersedes_sha256, metadata_json FROM fact_store WHERE id = ?",
                    (fact_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                    "created_at, accessed_at, entry_kind, domain, solution_kind, "
                    "supersedes_sha256, metadata_json FROM fact_store WHERE sha256 = ?",
                    (str(sha256).strip().lower(),),
                ).fetchone()

            if row is None:
                return None

            metadata = json.loads(row["metadata_json"] or "{}")
            governed_evidence = metadata.get("governed_evidence")
            if not isinstance(governed_evidence, dict):
                governed_evidence = {}
            if normalized_action == "revoke":
                governed_evidence["revoked"] = True
                governed_evidence["tombstoned"] = False
            elif normalized_action == "tombstone":
                governed_evidence["revoked"] = False
                governed_evidence["tombstoned"] = True
            else:
                governed_evidence["revoked"] = False
                governed_evidence["tombstoned"] = False

            if operator_summary:
                governed_evidence["operator_summary"] = operator_summary
            metadata["governed_evidence"] = governed_evidence
            metadata["governance_action"] = normalized_action
            metadata["governed_by"] = governed_by
            metadata["governed_reason"] = reason
            metadata["operator_id"] = str(operator_id or "")
            metadata["operator_display_name"] = str(operator_display_name or "")
            metadata["operator_channel"] = str(operator_channel or "")
            metadata["governed_at"] = _timestamp_to_iso8601(time.time())

            normalized_metadata = self._normalize_metadata(
                metadata=metadata,
                topic=str(row["topic"] or ""),
                confidence=float(row["confidence"]),
                provenance=str(row["provenance"] or "agent"),
                entry_kind=str(row["entry_kind"] or "fact"),
                domain=str(row["domain"] or ""),
                solution_kind=str(row["solution_kind"] or ""),
                supersedes_sha256=str(row["supersedes_sha256"] or ""),
                created_at=float(row["created_at"]),
            )
            now = time.time()
            conn.execute(
                "UPDATE fact_store SET metadata_json = ?, accessed_at = ? WHERE id = ?",
                (json.dumps(normalized_metadata, ensure_ascii=False, sort_keys=True), now, row["id"]),
            )
            superseded_hashes = self._superseded_hashes(conn)

        evidence = self._build_evidence(
            row=row,
            metadata=normalized_metadata,
            superseded_hashes=superseded_hashes,
            now=now,
        )
        return self._row_to_fact(row=row, metadata=normalized_metadata, evidence=evidence)

    def store_exemplar(self, exemplar: HKSValidatedExemplar) -> dict[str, Any]:
        metadata = exemplar.to_metadata()
        tags = sorted(set([*exemplar.tags, "hks", exemplar.domain, exemplar.solution_kind]))
        return self.store(
            exemplar.to_content(),
            topic=exemplar.topic,
            confidence=exemplar.confidence,
            provenance=exemplar.provenance.collector,
            tags=tags,
            entry_kind="hks_exemplar",
            domain=exemplar.domain,
            solution_kind=exemplar.solution_kind,
            supersedes_sha256=exemplar.supersedes,
            metadata=metadata,
        )

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        topic: str | None = None,
        min_confidence: float = 0.0,
        *,
        entry_kind: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
    ) -> dict[str, Any]:
        """Query memory by semantic similarity."""
        query_vec = _bow_vector(query_text)
        now = time.time()
        decay_cutoff = now - (_DECAY_DAYS * 86400)
        normalized_domain = self._normalize_domain(domain)

        with self._connect() as conn:
            sql = """
                SELECT id, content, topic, confidence, provenance, tags,
                      sha256, vector_json, created_at, accessed_at, entry_kind,
                       domain, solution_kind, supersedes_sha256, metadata_json
                FROM fact_store
                WHERE confidence >= ?
                  AND created_at >= ?
            """
            params: list[Any] = [min_confidence, decay_cutoff]
            if topic:
                sql += " AND topic = ?"
                params.append(topic)
            if entry_kind:
                sql += " AND entry_kind = ?"
                params.append(entry_kind)
            if normalized_domain:
                sql += " AND domain = ?"
                params.append(normalized_domain)
            if solution_kind:
                sql += " AND solution_kind = ?"
                params.append(solution_kind)
            sql += " ORDER BY confidence DESC, accessed_at DESC LIMIT 500"

            superseded_hashes = self._superseded_hashes(conn)
            rows = conn.execute(sql, params).fetchall()

        # Score by cosine similarity
        scored: list[dict[str, Any]] = []
        for row in rows:
            vec = json.loads(row["vector_json"] or "{}")
            sim = _cosine(query_vec, vec)
            metadata = json.loads(row["metadata_json"] or "{}")
            evidence = self._build_evidence(
                row=row,
                metadata=metadata,
                superseded_hashes=superseded_hashes,
                now=now,
            )
            if not self._include_fact(
                evidence=evidence,
                include_stale=include_stale,
                include_superseded=include_superseded,
                include_revoked=include_revoked,
                require_provenance=require_provenance,
            ):
                continue
            scored.append(
                self._row_to_fact(row=row, metadata=metadata, evidence=evidence, similarity=sim)
            )

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

        return {
            "results": results,
            "count": len(results),
            "query": query_text,
            "entry_kind": entry_kind,
            "domain": normalized_domain,
            "solution_kind": solution_kind,
            "include_stale": include_stale,
            "include_superseded": include_superseded,
            "include_revoked": include_revoked,
            "require_provenance": require_provenance,
        }

    def query_facts(
        self,
        *,
        entry_kind: str | None = None,
        topic: str | None = None,
        domain: str | None = None,
        solution_kind: str | None = None,
        profile: str | None = None,
        model: str | None = None,
        include_stale: bool = False,
        include_superseded: bool = False,
        include_revoked: bool = False,
        require_provenance: bool = False,
    ) -> list[dict[str, Any]]:
        normalized_domain = self._normalize_domain(domain)
        with self._connect() as conn:
            sql = (
                "SELECT id, sha256, content, topic, confidence, provenance, tags, "
                "created_at, accessed_at, entry_kind, domain, solution_kind, "
                "supersedes_sha256, metadata_json FROM fact_store WHERE 1=1"
            )
            params: list[Any] = []
            if entry_kind:
                sql += " AND entry_kind = ?"
                params.append(entry_kind)
            if topic:
                sql += " AND topic = ?"
                params.append(topic)
            if normalized_domain:
                sql += " AND domain = ?"
                params.append(normalized_domain)
            if solution_kind:
                sql += " AND solution_kind = ?"
                params.append(solution_kind)
            sql += " ORDER BY created_at DESC"
            superseded_hashes = self._superseded_hashes(conn)
            rows = conn.execute(sql, params).fetchall()

        now = time.time()
        results: list[dict[str, Any]] = []
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            if profile and str(metadata.get("profile_name") or "") != profile:
                continue
            if model and str(metadata.get("model") or metadata.get("model_name") or "") != model:
                continue
            evidence = self._build_evidence(
                row=row,
                metadata=metadata,
                superseded_hashes=superseded_hashes,
                now=now,
            )
            if not self._include_fact(
                evidence=evidence,
                include_stale=include_stale,
                include_superseded=include_superseded,
                include_revoked=include_revoked,
                require_provenance=require_provenance,
            ):
                continue
            results.append(self._row_to_fact(row=row, metadata=metadata, evidence=evidence))
        return results

    def all_facts(self) -> list[dict[str, Any]]:
        return self.query_facts(include_stale=True, include_superseded=True, include_revoked=True)

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
            exemplar_count = conn.execute(
                "SELECT COUNT(*) AS n FROM fact_store WHERE entry_kind = 'hks_exemplar'"
            ).fetchone()["n"]
            topics = conn.execute(
                "SELECT topic, COUNT(*) AS n FROM fact_store GROUP BY topic ORDER BY n DESC LIMIT 10"
            ).fetchall()
            domains = conn.execute(
                "SELECT domain, COUNT(*) AS n FROM fact_store WHERE domain != '' GROUP BY domain ORDER BY n DESC"
            ).fetchall()
            chain_depth = conn.execute("SELECT COUNT(*) AS n FROM merkle_chain").fetchone()["n"]
        return {
            "total_facts": total,
            "hks_exemplars": exemplar_count,
            "merkle_chain_depth": chain_depth,
            "hot_tier_topics": len(self._hot),
            "top_topics": [{"topic": r["topic"], "count": r["n"]} for r in topics],
            "domains": [{"domain": r["domain"], "count": r["n"]} for r in domains],
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

    def _normalize_domain(self, domain: str | None) -> str:
        if domain is None:
            return ""
        if domain not in HKS_DOMAINS:
            raise ValueError(f"Unsupported HKS domain: {domain}")
        return domain
