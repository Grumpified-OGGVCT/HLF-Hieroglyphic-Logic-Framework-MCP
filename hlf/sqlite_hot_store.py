"""
SQLite WAL Hot Store for HLF P0/P1 Profiles

Replaces Redis for hot-tier storage with ACID-compliant SQLite.
Provides sub-10ms access times suitable for non-real-time coordination.

Key Features:
- WAL mode for concurrent reads/writes
- Automatic TTL cleanup
- Atomic transactions for nonce protection
- Zero external dependencies
"""

import sqlite3
import json
import time
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from contextlib import contextmanager
import threading

@dataclass
class MetaIntent:
    """Compiler meta-intent for self-observation"""
    source_hash: str
    timestamp: float
    phase_timings: Dict[str, float]
    warnings: List[str]
    errors: List[str]
    gas_used: int
    profile: str

class SQLiteHotStore:
    """
    SQLite-based hot tier storage for Infinite RAG.
    
    Replaces Redis for P0/P1 profiles with ACID-compliant storage.
    Uses WAL mode for performance and durability.
    """
    
    def __init__(self, db_path: str = "./data/hlf_hot_store.db", ttl_seconds: int = 3600):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, isolation_level=None)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_conn()
        
        # Hot meta intents table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hot_meta (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value BLOB NOT NULL,
                ts REAL NOT NULL,
                ttl REAL NOT NULL
            )
        """)
        
        # Nonce protection table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nonces (
                nonce TEXT PRIMARY KEY,
                ts REAL NOT NULL,
                ttl REAL NOT NULL
            )
        """)
        
        # Queue table for agent coordination
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_name TEXT NOT NULL,
                payload BLOB NOT NULL,
                priority INTEGER DEFAULT 0,
                ts REAL NOT NULL,
                processed INTEGER DEFAULT 0
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_ts ON hot_meta(ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_ttl ON hot_meta(ttl)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_nonces_ttl ON nonces(ttl)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_name ON queue(queue_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_processed ON queue(processed)")
        
        conn.commit()
    
    def add_meta_intent(self, meta_intent: Dict[str, Any]) -> str:
        """
        Add a compiler meta-intent to hot store.
        
        Args:
            meta_intent: Dictionary with source_hash, timestamp, phase_timings, etc.
            
        Returns:
            Key of stored intent
        """
        conn = self._get_conn()
        key = f"meta:{meta_intent['source_hash']}:{meta_intent['timestamp']}"
        now = time.time()
        ttl = now + self.ttl_seconds
        
        conn.execute(
            "INSERT OR REPLACE INTO hot_meta (key, value, ts, ttl) VALUES (?, ?, ?, ?)",
            (key, json.dumps(meta_intent).encode(), now, ttl)
        )
        
        return key
    
    def get_recent_meta_intents(self, since: float, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent meta-intents from hot store.
        
        Args:
            since: Unix timestamp to get intents after
            limit: Maximum number of intents to return
            
        Returns:
            List of meta-intent dictionaries
        """
        conn = self._get_conn()
        now = time.time()
        
        rows = conn.execute(
            "SELECT value FROM hot_meta WHERE ts > ? AND ttl > ? ORDER BY ts DESC LIMIT ?",
            (since, now, limit)
        ).fetchall()
        
        return [json.loads(row[0].decode()) for row in rows]
    
    def get_meta_intent_count(self) -> int:
        """Get total count of meta-intents in hot store"""
        conn = self._get_conn()
        now = time.time()
        
        result = conn.execute(
            "SELECT COUNT(*) FROM hot_meta WHERE ttl > ?",
            (now,)
        ).fetchone()
        
        return result[0] if result else 0
    
    def is_replay(self, nonce: str) -> bool:
        """
        Check if a nonce has been used before (replay protection).
        
        Args:
            nonce: The nonce to check
            
        Returns:
            True if replay detected (nonce already exists), False otherwise
        """
        conn = self._get_conn()
        now = time.time()
        ttl = now + self.ttl_seconds
        
        try:
            conn.execute(
                "INSERT INTO nonces (nonce, ts, ttl) VALUES (?, ?, ?)",
                (nonce, now, ttl)
            )
            return False  # Not a replay
        except sqlite3.IntegrityError:
            return True  # Replay detected
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from all tables.
        
        Returns:
            Number of entries removed
        """
        conn = self._get_conn()
        now = time.time()
        
        conn.execute("DELETE FROM hot_meta WHERE ttl <= ?", (now,))
        hot_deleted = conn.rowcount
        
        conn.execute("DELETE FROM nonces WHERE ttl <= ?", (now,))
        nonce_deleted = conn.rowcount
        
        conn.execute("DELETE FROM queue WHERE processed = 1 AND ts < ?", (now - self.ttl_seconds,))
        queue_deleted = conn.rowcount
        
        conn.execute("VACUUM")
        
        return hot_deleted + nonce_deleted + queue_deleted
    
    def enqueue(self, queue_name: str, payload: Dict[str, Any], priority: int = 0) -> int:
        """
        Add item to queue.
        
        Args:
            queue_name: Name of the queue
            payload: Data to enqueue
            priority: Higher = processed first
            
        Returns:
            Queue item ID
        """
        conn = self._get_conn()
        now = time.time()
        
        cursor = conn.execute(
            "INSERT INTO queue (queue_name, payload, priority, ts, processed) VALUES (?, ?, ?, ?, 0)",
            (queue_name, json.dumps(payload).encode(), priority, now)
        )
        
        return cursor.lastrowid
    
    def dequeue(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Get and mark as processed the highest priority item from queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Dequeued item or None if empty
        """
        conn = self._get_conn()
        
        # Get highest priority item
        row = conn.execute(
            """SELECT id, payload FROM queue 
               WHERE queue_name = ? AND processed = 0 
               ORDER BY priority DESC, ts ASC LIMIT 1""",
            (queue_name,)
        ).fetchone()
        
        if not row:
            return None
        
        # Mark as processed
        conn.execute("UPDATE queue SET processed = 1 WHERE id = ?", (row[0],))
        
        return json.loads(row[1].decode())
    
    def queue_size(self, queue_name: str) -> int:
        """Get number of unprocessed items in queue"""
        conn = self._get_conn()
        
        result = conn.execute(
            "SELECT COUNT(*) FROM queue WHERE queue_name = ? AND processed = 0",
            (queue_name,)
        ).fetchone()
        
        return result[0] if result else 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics"""
        conn = self._get_conn()
        now = time.time()
        
        stats = {
            "meta_intents": conn.execute(
                "SELECT COUNT(*) FROM hot_meta WHERE ttl > ?", (now,)
            ).fetchone()[0],
            "nonces_active": conn.execute(
                "SELECT COUNT(*) FROM nonces WHERE ttl > ?", (now,)
            ).fetchone()[0],
            "queue_items": conn.execute(
                "SELECT COUNT(*) FROM queue WHERE processed = 0"
            ).fetchone()[0],
            "db_path": self.db_path,
            "ttl_seconds": self.ttl_seconds,
        }
        
        return stats


# LRU Cache Hot Store for ultra-low latency (P1)
class LRUHotStore:
    """
    In-process LRU cache for sub-millisecond hot tier access.
    
    For P1 profile when <10ms latency is required.
    Uses Python's OrderedDict for O(1) access.
    """
    
    def __init__(self, maxsize: int = 1000):
        from collections import OrderedDict
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            return None
    
    def set(self, key: str, value: Any):
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.maxsize:
                # Remove oldest
                self.cache.popitem(last=False)
    
    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def clear(self):
        with self._lock:
            self.cache.clear()
    
    def size(self) -> int:
        with self._lock:
            return len(self.cache)


class HybridHotStore:
    """
    Hybrid hot store combining LRU cache (P1) with SQLite (P0).
    
    Tiered approach:
    - L1: LRU cache (sub-ms) for frequently accessed data
    - L2: SQLite (5-10ms) for persistent hot storage
    """
    
    def __init__(self, db_path: str = "./data/hlf_hot_store.db", lru_size: int = 1000):
        self.lru = LRUHotStore(maxsize=lru_size)
        self.sqlite = SQLiteHotStore(db_path=db_path)
        self._lock = threading.Lock()
    
    def add_meta_intent(self, meta_intent: Dict[str, Any]) -> str:
        """Add to both tiers"""
        key = self.sqlite.add_meta_intent(meta_intent)
        self.lru.set(key, meta_intent)
        return key
    
    def get_recent_meta_intents(self, since: float, limit: int = 100) -> List[Dict[str, Any]]:
        """Get from SQLite (LRU not suitable for range queries)"""
        return self.sqlite.get_recent_meta_intents(since, limit)
    
    def get_meta_intent(self, key: str) -> Optional[Dict[str, Any]]:
        """Try LRU first, fallback to SQLite"""
        # Try L1 cache
        cached = self.lru.get(key)
        if cached:
            return cached
        
        # L2 fallback - for direct key lookup we'd need to add that method
        return None
    
    def is_replay(self, nonce: str) -> bool:
        """Check nonce (SQLite only for durability)"""
        return self.sqlite.is_replay(nonce)


# Factory function
def create_hot_store(profile: str = "P0", db_path: str = "./data/hlf_hot_store.db"):
    """
    Create appropriate hot store for profile.
    
    Args:
        profile: "P0", "P1", or "P2"
        db_path: Path to SQLite database
        
    Returns:
        HotStore instance appropriate for profile
    """
    if profile == "P0":
        # P0: SQLite only (cloud-only, minimal footprint)
        return SQLiteHotStore(db_path=db_path)
    elif profile == "P1":
        # P1: Hybrid (LRU + SQLite for performance)
        return HybridHotStore(db_path=db_path)
    else:
        # P2: Redis would be used here (import redis if available)
        try:
            import redis
            # Return Redis-based store
            return SQLiteHotStore(db_path=db_path)  # Fallback for now
        except ImportError:
            return HybridHotStore(db_path=db_path)
