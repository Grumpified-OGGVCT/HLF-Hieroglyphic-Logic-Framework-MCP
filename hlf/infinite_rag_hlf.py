"""
Infinite RAG Implementation for HLF

Provides tiered memory storage:
- Hot tier: LRU cache (P1) or SQLite (P0)
- Warm tier: SQLite facts
- Cold tier: Parquet files

Replaces Redis with SQLite WAL for P0/P1 profiles.
"""

import os
import json
import time
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """A semantic fact in the knowledge base"""
    id: str
    content: str
    source: str
    embedding: Optional[List[float]] = None
    timestamp: float = 0.0
    access_count: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class InfiniteRAGHLF:
    """
    Infinite Retrieval-Augmented Generation for HLF.
    
    Three-tier architecture:
    - Hot: LRU cache (P1) or SQLite (P0) - sub-10ms
    - Warm: SQLite - persistent facts
    - Cold: Parquet files - archive
    """
    
    def __init__(
        self,
        db_path: str = "./data/hlf_rag.db",
        profile: str = "P0",
        hot_store=None
    ):
        """
        Initialize Infinite RAG.
        
        Args:
            db_path: Path to SQLite database
            profile: HLF profile (P0, P1, P2)
            hot_store: Optional hot store instance
        """
        self.db_path = db_path
        self.profile = profile
        self._init_db()
        
        # Set up hot tier
        if hot_store:
            self.hot_store = hot_store
        elif profile == "P0":
            from .sqlite_hot_store import SQLiteHotStore
            self.hot_store = SQLiteHotStore(db_path=db_path.replace(".db", "_hot.db"))
        elif profile == "P1":
            from .sqlite_hot_store import HybridHotStore
            self.hot_store = HybridHotStore(db_path=db_path.replace(".db", "_hot.db"))
        else:
            # P2 would use Redis
            from .sqlite_hot_store import HybridHotStore
            self.hot_store = HybridHotStore(db_path=db_path.replace(".db", "_hot.db"))
    
    def _init_db(self):
        """Initialize warm tier database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Facts table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT,
                embedding BLOB,
                timestamp REAL,
                access_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Meta intents table (compiler observations)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meta_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_hash TEXT,
                timestamp REAL,
                phase_timings TEXT,
                warnings TEXT,
                errors TEXT,
                gas_used INTEGER,
                profile TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_timestamp ON facts(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_facts_source ON facts(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_hash ON meta_intents(source_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_meta_timestamp ON meta_intents(timestamp)")
        
        conn.commit()
        conn.close()
    
    def add_fact(self, fact: Fact) -> str:
        """
        Add a fact to warm tier.
        
        Args:
            fact: Fact to store
            
        Returns:
            Fact ID
        """
        conn = sqlite3.connect(self.db_path)
        
        embedding_blob = None
        if fact.embedding:
            embedding_blob = json.dumps(fact.embedding).encode()
        
        conn.execute(
            """INSERT OR REPLACE INTO facts 
               (id, content, source, embedding, timestamp, access_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fact.id, fact.content, fact.source, embedding_blob, 
             fact.timestamp, fact.access_count)
        )
        
        conn.commit()
        conn.close()
        
        return fact.id
    
    def get_fact(self, fact_id: str) -> Optional[Fact]:
        """
        Retrieve a fact by ID.
        
        Args:
            fact_id: Fact identifier
            
        Returns:
            Fact or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        row = conn.execute(
            "SELECT * FROM facts WHERE id = ?",
            (fact_id,)
        ).fetchone()
        
        if row:
            # Update access count
            conn.execute(
                "UPDATE facts SET access_count = access_count + 1 WHERE id = ?",
                (fact_id,)
            )
            conn.commit()
            
            embedding = None
            if row["embedding"]:
                embedding = json.loads(row["embedding"].decode())
            
            fact = Fact(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                embedding=embedding,
                timestamp=row["timestamp"],
                access_count=row["access_count"] + 1
            )
        else:
            fact = None
        
        conn.close()
        return fact
    
    def search_facts(self, query: str, limit: int = 10) -> List[Fact]:
        """
        Search facts by content (simple substring search).
        
        For production, use vector similarity search.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching facts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute(
            "SELECT * FROM facts WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        ).fetchall()
        
        facts = []
        for row in rows:
            embedding = None
            if row["embedding"]:
                embedding = json.loads(row["embedding"].decode())
            
            facts.append(Fact(
                id=row["id"],
                content=row["content"],
                source=row["source"],
                embedding=embedding,
                timestamp=row["timestamp"],
                access_count=row["access_count"]
            ))
        
        conn.close()
        return facts
    
    def add_meta_intent(self, meta_intent: Dict[str, Any]) -> int:
        """
        Add compiler meta-intent for self-observation.
        
        Also adds to hot tier for fast access.
        
        Args:
            meta_intent: Dictionary with compiler metadata
            
        Returns:
            Intent ID
        """
        # Add to warm tier
        conn = sqlite3.connect(self.db_path)
        
        cursor = conn.execute(
            """INSERT INTO meta_intents 
               (source_hash, timestamp, phase_timings, warnings, errors, gas_used, profile)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                meta_intent.get("source_hash", ""),
                meta_intent.get("timestamp", time.time()),
                json.dumps(meta_intent.get("phase_timings", {})),
                json.dumps(meta_intent.get("warnings", [])),
                json.dumps(meta_intent.get("errors", [])),
                meta_intent.get("gas_used", 0),
                meta_intent.get("profile", "P0")
            )
        )
        
        intent_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Also add to hot tier
        if self.hot_store:
            self.hot_store.add_meta_intent(meta_intent)
        
        return intent_id
    
    def get_recent_meta_intents(self, since: float, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent compiler meta-intents.
        
        Args:
            since: Unix timestamp
            limit: Maximum results
            
        Returns:
            List of meta-intent dictionaries
        """
        # Try hot tier first for P0/P1
        if self.profile in ["P0", "P1"] and self.hot_store:
            try:
                return self.hot_store.get_recent_meta_intents(since, limit)
            except Exception as e:
                logger.warning(f"Hot tier failed, falling back to warm: {e}")
        
        # Fallback to warm tier
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute(
            """SELECT * FROM meta_intents 
               WHERE timestamp > ? 
               ORDER BY timestamp DESC LIMIT ?""",
            (since, limit)
        ).fetchall()
        
        intents = []
        for row in rows:
            intents.append({
                "id": row["id"],
                "source_hash": row["source_hash"],
                "timestamp": row["timestamp"],
                "phase_timings": json.loads(row["phase_timings"]),
                "warnings": json.loads(row["warnings"]),
                "errors": json.loads(row["errors"]),
                "gas_used": row["gas_used"],
                "profile": row["profile"],
            })
        
        conn.close()
        return intents
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics"""
        conn = sqlite3.connect(self.db_path)
        
        fact_count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        intent_count = conn.execute("SELECT COUNT(*) FROM meta_intents").fetchone()[0]
        
        # Recent intents
        recent = conn.execute(
            "SELECT COUNT(*) FROM meta_intents WHERE timestamp > ?",
            (time.time() - 86400,)  # Last 24 hours
        ).fetchone()[0]
        
        conn.close()
        
        stats = {
            "facts": fact_count,
            "meta_intents": intent_count,
            "recent_intents_24h": recent,
            "profile": self.profile,
        }
        
        # Add hot tier stats if available
        if self.hot_store:
            try:
                hot_stats = self.hot_store.get_stats()
                stats["hot_tier"] = hot_stats
            except Exception as e:
                stats["hot_tier_error"] = str(e)
        
        return stats
    
    def cleanup(self, max_age_days: int = 30) -> int:
        """
        Remove old data.
        
        Args:
            max_age_days: Maximum age in days
            
        Returns:
            Number of items removed
        """
        cutoff = time.time() - (max_age_days * 86400)
        
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("DELETE FROM facts WHERE timestamp < ?", (cutoff,))
        facts_deleted = conn.rowcount
        
        conn.execute("DELETE FROM meta_intents WHERE timestamp < ?", (cutoff,))
        intents_deleted = conn.rowcount
        
        conn.commit()
        conn.close()
        
        # Cleanup hot tier
        if self.hot_store:
            try:
                self.hot_store.cleanup_expired()
            except Exception as e:
                logger.warning(f"Hot tier cleanup failed: {e}")
        
        return facts_deleted + intents_deleted
