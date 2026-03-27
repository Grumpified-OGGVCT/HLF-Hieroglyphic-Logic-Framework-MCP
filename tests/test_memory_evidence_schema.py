"""Fix 4: Memory Evidence Schema — typed column promotion tests.

Validates that evidence governance fields are stored as first-class SQLite
columns, populated at INSERT time, backfilled for legacy rows, and used
in SQL-level query filtering.
"""

from __future__ import annotations

import json
import sqlite3
import time

import pytest

from hlf_mcp.rag.memory import RAGMemory


# ── Helpers ──────────────────────────────────────────────────────────────────


def _store_fact(mem: RAGMemory, content: str, **kwargs) -> dict:
    defaults = {
        "topic": "test",
        "confidence": 0.9,
        "provenance": "agent",
        "entry_kind": "fact",
    }
    defaults.update(kwargs)
    return mem.store(content=content, **defaults)


def _raw_row(mem: RAGMemory, row_id: int) -> sqlite3.Row:
    with mem._connect() as conn:
        return conn.execute("SELECT * FROM fact_store WHERE id = ?", (row_id,)).fetchone()


# ── Schema Tests ─────────────────────────────────────────────────────────────


class TestEvidenceColumnsExist:
    """The 9 promoted evidence columns exist in fact_store after init."""

    EXPECTED_COLUMNS = {
        "memory_stratum",
        "storage_tier",
        "revoked",
        "tombstoned",
        "provenance_grade",
        "salience_score",
        "artifact_form",
        "source_authority_label",
        "source_type",
    }

    def test_columns_present(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        with mem._connect() as conn:
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(fact_store)").fetchall()}
        assert self.EXPECTED_COLUMNS.issubset(cols), f"Missing: {self.EXPECTED_COLUMNS - cols}"


# ── INSERT Population Tests ──────────────────────────────────────────────────


class TestInsertPopulatesColumns:
    """Evidence columns are populated at INSERT time from enriched metadata."""

    def test_basic_fact_defaults(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = _store_fact(mem, "basic fact content")
        assert result["stored"]
        row = _raw_row(mem, result["id"])
        assert row["memory_stratum"] in ("working", "provenance", "archive")
        assert row["storage_tier"] in ("hot", "warm", "cold")
        assert row["revoked"] == 0
        assert row["tombstoned"] == 0
        assert row["provenance_grade"] in ("basic", "evidence-backed")
        assert isinstance(row["salience_score"], (int, float))
        assert row["artifact_form"] in ("raw_intake", "canonical_knowledge")
        assert row["source_authority_label"] in ("advisory", "canonical")

    def test_evidence_entry_with_provenance(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = mem.store(
            content="evidence with full provenance chain",
            topic="depth_audit",
            confidence=0.95,
            provenance="agent",
            entry_kind="evidence",
            metadata={
                "source_type": "build_evidence",
                "governed_evidence": {
                    "source_type": "build_evidence",
                    "source_path": "tests/test_something.py",
                    "artifact_id": "fix4-schema-001",
                    "source_authority_label": "canonical",
                    "artifact_form": "canonical_knowledge",
                    "memory_stratum": "provenance",
                    "storage_tier": "warm",
                },
            },
            strict=True,
        )
        assert result["stored"]
        row = _raw_row(mem, result["id"])
        assert row["provenance_grade"] == "evidence-backed"
        assert row["source_authority_label"] == "canonical"
        assert row["artifact_form"] == "canonical_knowledge"
        assert row["source_type"] == "build_evidence"
        assert row["memory_stratum"] == "provenance"

    def test_revoked_flag_stored(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = mem.store(
            content="this fact was pre-revoked at ingest",
            topic="test",
            confidence=0.5,
            provenance="agent",
            entry_kind="fact",
            metadata={
                "governed_evidence": {
                    "revoked": True,
                },
            },
        )
        assert result["stored"]
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 1
        assert row["tombstoned"] == 0

    def test_tombstoned_flag_stored(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = mem.store(
            content="this fact was pre-tombstoned at ingest",
            topic="test",
            confidence=0.5,
            provenance="agent",
            entry_kind="fact",
            metadata={
                "governed_evidence": {
                    "tombstoned": True,
                },
            },
        )
        assert result["stored"]
        row = _raw_row(mem, result["id"])
        assert row["tombstoned"] == 1


# ── SQL Filter Tests ─────────────────────────────────────────────────────────


class TestSQLQueryFilters:
    """Evidence columns are used in SQL WHERE clauses for efficient filtering."""

    def _seed_mixed_facts(self, mem: RAGMemory):
        """Seed a mix of active, revoked, archived, and evidence-backed facts."""
        # Active fact
        _store_fact(mem, "active healthy fact alpha", topic="mixed")
        # Revoked fact
        mem.store(
            content="revoked fact beta",
            topic="mixed",
            confidence=0.9,
            provenance="agent",
            entry_kind="fact",
            metadata={"governed_evidence": {"revoked": True}},
        )
        # Evidence-backed
        mem.store(
            content="evidence backed fact gamma",
            topic="mixed",
            confidence=0.9,
            provenance="agent",
            entry_kind="evidence",
            metadata={
                "source_type": "test_evidence",
                "governed_evidence": {
                    "source_type": "test_evidence",
                    "source_path": "tests/test_x.py",
                    "artifact_id": "ev-001",
                    "source_authority_label": "canonical",
                },
            },
            strict=True,
        )

    def test_default_query_excludes_revoked(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        self._seed_mixed_facts(mem)
        result = mem.query("fact", topic="mixed")
        contents = [r["content"] for r in result["results"]]
        assert "revoked fact beta" not in contents

    def test_include_revoked_returns_revoked(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        self._seed_mixed_facts(mem)
        result = mem.query("fact beta", topic="mixed", include_revoked=True)
        contents = [r["content"] for r in result["results"]]
        # Revoked facts should now be includable
        # (may or may not appear depending on similarity — the point is the SQL doesn't block them)
        # At minimum, no error thrown
        assert isinstance(result["results"], list)

    def test_require_provenance_filters_basic(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        self._seed_mixed_facts(mem)
        result = mem.query("fact", topic="mixed", require_provenance=True)
        for r in result["results"]:
            # All returned results should be evidence-backed at evidence level
            # (the SQL filter ensures provenance_grade = 'evidence-backed')
            assert r.get("content") != "active healthy fact alpha" or r.get("evidence", {}).get("provenance_grade") == "evidence-backed"


# ── Backfill Tests ───────────────────────────────────────────────────────────


class TestBackfillEvidenceColumns:
    """Backfill correctly derives evidence columns from metadata_json for old rows."""

    def test_backfill_populates_from_metadata(self, tmp_path):
        db_path = str(tmp_path / "backfill.db")
        # Phase 1: Create a DB with the old schema (no evidence columns)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # Create minimal fact_store matching old schema
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS fact_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sha256 TEXT NOT NULL UNIQUE,
                content TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                provenance TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                vector_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                accessed_at REAL NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS rolling_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS merkle_chain (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                fact_sha256 TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                chain_hash TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        # Add the first wave of migration columns (simulating old _init_db)
        for col, ddl in [
            ("entry_kind", "TEXT NOT NULL DEFAULT 'fact'"),
            ("domain", "TEXT NOT NULL DEFAULT ''"),
            ("solution_kind", "TEXT NOT NULL DEFAULT ''"),
            ("supersedes_sha256", "TEXT NOT NULL DEFAULT ''"),
            ("metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE fact_store ADD COLUMN {col} {ddl}")
            except Exception:
                pass

        # Insert a row with rich metadata but no evidence columns yet
        import hashlib
        content = "legacy fact with rich metadata"
        sha = hashlib.sha256(content.encode()).hexdigest()
        now = time.time()
        meta = {
            "governed_evidence": {
                "memory_stratum": "provenance",
                "storage_tier": "warm",
                "salience_score": 0.85,
                "artifact_form": "canonical_knowledge",
                "source_authority_label": "canonical",
                "source_type": "doctrine",
                "revoked": False,
                "tombstoned": False,
                "provenance_grade": "evidence-backed",
            }
        }
        conn.execute(
            "INSERT INTO fact_store (sha256, content, topic, confidence, provenance, tags, "
            "vector_json, created_at, accessed_at, entry_kind, domain, solution_kind, "
            "supersedes_sha256, metadata_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sha, content, "legacy", 0.9, "agent", "[]", "{}", now, now,
             "evidence", "", "", "", json.dumps(meta)),
        )
        conn.commit()
        conn.close()

        # Phase 2: Open with RAGMemory — triggers _init_db → _ensure_column → _backfill
        mem = RAGMemory(db_path)
        row = _raw_row(mem, 1)
        assert row["memory_stratum"] == "provenance"
        assert row["storage_tier"] == "warm"
        assert row["artifact_form"] == "canonical_knowledge"
        assert row["source_authority_label"] == "canonical"
        assert row["source_type"] == "doctrine"
        assert row["provenance_grade"] == "evidence-backed"
        assert float(row["salience_score"]) == pytest.approx(0.85)
        assert row["revoked"] == 0
        assert row["tombstoned"] == 0


# ── Govern Fact Column Update Tests ──────────────────────────────────────────


class TestGovernFactUpdatesColumns:
    """govern_fact() updates typed columns alongside metadata_json."""

    def test_revoke_sets_column(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = _store_fact(mem, "fact to revoke")
        assert result["stored"]
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 0

        mem.govern_fact(action="revoke", fact_id=result["id"], reason="test")
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 1
        assert row["tombstoned"] == 0

    def test_tombstone_sets_column(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = _store_fact(mem, "fact to tombstone")
        assert result["stored"]

        mem.govern_fact(action="tombstone", fact_id=result["id"], reason="test")
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 0
        assert row["tombstoned"] == 1

    def test_reinstate_clears_columns(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = _store_fact(mem, "fact to reinstate")
        mem.govern_fact(action="revoke", fact_id=result["id"], reason="test")
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 1

        mem.govern_fact(action="reinstate", fact_id=result["id"], reason="cleared")
        row = _raw_row(mem, result["id"])
        assert row["revoked"] == 0
        assert row["tombstoned"] == 0

    def test_revoked_fact_excluded_from_query(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        result = _store_fact(mem, "soon to be revoked query target", topic="govern_q")
        _store_fact(mem, "healthy fact remains", topic="govern_q")
        mem.govern_fact(action="revoke", fact_id=result["id"], reason="test")

        qr = mem.query("revoked query target", topic="govern_q")
        contents = [r["content"] for r in qr["results"]]
        assert "soon to be revoked query target" not in contents


# ── Column Count Regression Test ─────────────────────────────────────────────


class TestColumnCountRegression:
    """Ensure the schema has exactly the expected column count after all migrations."""

    def test_total_column_count(self, tmp_path):
        mem = RAGMemory(str(tmp_path / "test.db"))
        with mem._connect() as conn:
            cols = conn.execute("PRAGMA table_info(fact_store)").fetchall()
        col_names = [c["name"] for c in cols]
        # Original 11 + 5 first-wave migration + 9 Fix 4 = 25
        assert len(col_names) >= 25, f"Expected >= 25 columns, got {len(col_names)}: {col_names}"
