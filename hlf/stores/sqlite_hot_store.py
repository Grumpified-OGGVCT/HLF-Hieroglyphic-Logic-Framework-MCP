"""
SQLite Hot Store Implementation
Replaces Redis for P0/P1 profiles with ACID-compliant WAL mode
"""

import sqlite3
import json
import time
import os
from typing import List, Dict, Any, Optional


class SQLiteHotStore:
    """
    SQLite-based hot tier store for P0/P1 profiles.
    
    Uses SQLite WAL mode for:
    - ACID compliance
    - Concurrent read/write
    - Crash safety
    - Zero external dependencies
    
    Tradeoff: ~5ms latency vs Redis <1ms
    Solution: Increase GAS_TOLERANCE_MS for P0/P1 profiles
    """
    
    def __init__(self, db_path: str = "./data/hlf_hot.db"):
        """
        Initialize SQLite hot store with WAL mode.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect with WAL mode for concurrent access
        self.conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        
        # Enable WAL mode for better concurrency
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self.conn.execute("PRAGMA temp_store=MEMORY")
        
        # Create tables
        self._init_schema()
    
    def _init_schema(self):
        """Initialize database schema."""
        # Hot meta intents table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS hot_meta (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                ts REAL NOT NULL,
                ttl INTEGER DEFAULT 0
            )
        """)
        
        # Nonce protection table (for replay prevention)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS nonces (
                nonce TEXT PRIMARY KEY,
                ts REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        
        # Agent coordination queue
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                task BLOB NOT NULL,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                created_at REAL NOT NULL,
                processed_at REAL
            )
        """)
        
        # Create indexes for performance
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_meta_ts ON hot_meta(ts)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_hot_meta_ttl ON hot_meta(ttl)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_nonces_ts ON nonces(ts)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_nonces_expires ON nonces(expires_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_queue_status ON agent_queue(status, priority)")
    
    def add_meta_intent(self, meta_intent: Dict[str, Any]) -> str:
        """
        Add a meta-intent to the hot store.
        
        Args:
            meta_intent: Dictionary containing meta-intent data
            
        Returns:
            Key of stored meta-intent
        """
        key = f"meta:{meta_intent.get('source_hash', 'unknown')}:{meta_intent.get('timestamp', time.time())}"
        
        self.conn.execute(
            "INSERT OR REPLACE INTO hot_meta (key, value, ts, ttl) VALUES (?, ?, ?, ?)",
            (key, json.dumps(meta_intent).encode(), time.time(), meta_intent.get('ttl', 0))
        )
        
        return key
    
    def get_recent_meta_intents(self, since: float, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent meta-intents from hot store.
        
        Args:
            since: Unix timestamp - only return intents after this time
            limit: Maximum number of intents to return
            
        Returns:
            List of meta-intent dictionaries
        """
        rows = self.conn.execute(
            "SELECT value FROM hot_meta WHERE ts > ? ORDER BY ts DESC LIMIT ?",
            (since, limit)
        ).fetchall()
        
        return [json.loads(row[0].decode()) for row in rows]
    
    def get_meta_intent(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a specific meta-intent by key."""
        row = self.conn.execute(
            "SELECT value FROM hot_meta WHERE key = ?",
            (key,)
        ).fetchone()
        
        if row:
            return json.loads(row[0].decode())
        return None
    
    def delete_meta_intent(self, key: str) -> bool:
        """Delete a meta-intent by key."""
        cursor = self.conn.execute("DELETE FROM hot_meta WHERE key = ?", (key,))
        return cursor.rowcount > 0
    
    def check_nonce(self, nonce: str, ttl_seconds: float = 3600) -> bool:
        """
        Check if a nonce has been used (replay protection).
        
        Args:
            nonce: The nonce to check
            ttl_seconds: Time-to-live for nonce records
            
        Returns:
            True if nonce is new (not a replay), False if replay detected
        """
        now = time.time()
        expires_at = now + ttl_seconds
        
        try:
            self.conn.execute(
                "INSERT INTO nonces (nonce, ts, expires_at) VALUES (?, ?, ?)",
                (nonce, now, expires_at)
            )
            return True  # New nonce
        except sqlite3.IntegrityError:
            return False  # Replay detected
    
    def cleanup_expired_nonces(self) -> int:
        """Clean up expired nonce records. Returns count deleted."""
        now = time.time()
        cursor = self.conn.execute(
            "DELETE FROM nonces WHERE expires_at < ?",
            (now,)
        )
        return cursor.rowcount
    
    def enqueue_agent_task(self, agent_id: str, task: Dict[str, Any], priority: int = 5) -> int:
        """
        Add a task to the agent coordination queue.
        
        Args:
            agent_id: ID of the agent
            task: Task definition dictionary
            priority: Priority (1-10, lower is higher priority)
            
        Returns:
            Task ID
        """
        cursor = self.conn.execute(
            """
            INSERT INTO agent_queue (agent_id, task, priority, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (agent_id, json.dumps(task).encode(), priority, time.time())
        )
        return cursor.lastrowid
    
    def dequeue_agent_task(self, agent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get the next pending task from the queue.
        
        Args:
            agent_id: If specified, only get tasks for this agent
            
        Returns:
            Task dictionary or None if no tasks
        """
        if agent_id:
            row = self.conn.execute(
                """
                SELECT id, agent_id, task, priority, created_at 
                FROM agent_queue 
                WHERE agent_id = ? AND status = 'pending'
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """,
                (agent_id,)
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT id, agent_id, task, priority, created_at 
                FROM agent_queue 
                WHERE status = 'pending'
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """
            ).fetchone()
        
        if row:
            task_id, agent_id, task_data, priority, created_at = row
            
            # Mark as processing
            self.conn.execute(
                "UPDATE agent_queue SET status = 'processing', processed_at = ? WHERE id = ?",
                (time.time(), task_id)
            )
            
            return {
                'id': task_id,
                'agent_id': agent_id,
                'task': json.loads(task_data.decode()),
                'priority': priority,
                'created_at': created_at
            }
        
        return None
    
    def complete_agent_task(self, task_id: int, status: str = 'completed') -> bool:
        """Mark an agent task as completed or failed."""
        cursor = self.conn.execute(
            "UPDATE agent_queue SET status = ? WHERE id = ?",
            (status, task_id)
        )
        return cursor.rowcount > 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        meta_count = self.conn.execute("SELECT COUNT(*) FROM hot_meta").fetchone()[0]
        nonce_count = self.conn.execute("SELECT COUNT(*) FROM nonces").fetchone()[0]
        queue_pending = self.conn.execute(
            "SELECT COUNT(*) FROM agent_queue WHERE status = 'pending'"
        ).fetchone()[0]
        queue_processing = self.conn.execute(
            "SELECT COUNT(*) FROM agent_queue WHERE status = 'processing'"
        ).fetchone()[0]
        
        # Get database file size
        db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        wal_size = os.path.getsize(self.db_path + "-wal") if os.path.exists(self.db_path + "-wal") else 0
        
        return {
            'meta_intents': meta_count,
            'nonces': nonce_count,
            'queue_pending': queue_pending,
            'queue_processing': queue_processing,
            'db_size_bytes': db_size,
            'wal_size_bytes': wal_size,
            'total_size_mb': round((db_size + wal_size) / (1024 * 1024), 2)
        }
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
