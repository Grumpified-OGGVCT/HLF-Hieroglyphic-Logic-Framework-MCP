"""
LRU Cache Hot Store Implementation
Ultra-low latency (<0.1ms) for P0 profile without external dependencies
"""

import json
import time
from collections import OrderedDict
from typing import List, Dict, Any, Optional
import threading


class LRUHotStore:
    """
    In-process LRU cache hot tier for P0 profile.
    
    Provides:
    - <0.1ms latency (faster than Redis <1ms)
    - Zero external dependencies
    - Thread-safe operations
    - Automatic eviction of oldest items
    
    Tradeoff: Data lost on process restart (acceptable for hot tier)
    Solution: Use warm tier (SQLite) for persistence
    """
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize LRU hot store.
        
        Args:
            maxsize: Maximum number of items to store
        """
        self.maxsize = maxsize
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def add_meta_intent(self, meta_intent: Dict[str, Any]) -> str:
        """
        Add a meta-intent to the hot store.
        
        Args:
            meta_intent: Dictionary containing meta-intent data
            
        Returns:
            Key of stored meta-intent
        """
        key = f"meta:{meta_intent.get('source_hash', 'unknown')}:{meta_intent.get('timestamp', time.time())}"
        
        with self.lock:
            self.cache[key] = meta_intent
            self.cache.move_to_end(key)
            
            # Evict oldest if over capacity
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
        
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
        results = []
        
        with self.lock:
            # Iterate in reverse (newest first)
            for key, value in reversed(self.cache.items()):
                if value.get('timestamp', 0) > since:
                    results.append(value)
                if len(results) >= limit:
                    break
        
        return results
    
    def get_meta_intent(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific meta-intent by key.
        Moves item to end (marks as recently used).
        """
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                self._hits += 1
                return self.cache[key]
            self._misses += 1
            return None
    
    def delete_meta_intent(self, key: str) -> bool:
        """Delete a meta-intent by key."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def check_nonce(self, nonce: str, ttl_seconds: float = 3600) -> bool:
        """
        Check if a nonce has been used (replay protection).
        
        Note: Nonces in LRU store are not persisted across restarts.
        For durable nonce protection, use SQLiteHotStore.
        
        Args:
            nonce: The nonce to check
            ttl_seconds: Ignored for LRU store (memory-based only)
            
        Returns:
            True if nonce is new, False if replay
        """
        key = f"nonce:{nonce}"
        
        with self.lock:
            if key in self.cache:
                return False  # Replay
            
            # Store nonce with timestamp
            self.cache[key] = {'created_at': time.time(), 'ttl': ttl_seconds}
            self.cache.move_to_end(key)
            
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
            
            return True
    
    def cleanup_expired(self, max_age_seconds: float = 3600) -> int:
        """
        Remove items older than max_age_seconds.
        
        Returns:
            Number of items removed
        """
        now = time.time()
        to_remove = []
        
        with self.lock:
            for key, value in self.cache.items():
                if isinstance(value, dict) and 'created_at' in value:
                    if now - value['created_at'] > max_age_seconds:
                        to_remove.append(key)
            
            for key in to_remove:
                del self.cache[key]
        
        return len(to_remove)
    
    def clear(self):
        """Clear all items from cache."""
        with self.lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        with self.lock:
            total_size = len(self.cache)
            
            # Count meta intents vs nonces
            meta_count = sum(1 for k in self.cache.keys() if k.startswith('meta:'))
            nonce_count = sum(1 for k in self.cache.keys() if k.startswith('nonce:'))
            
            # Estimate memory usage (rough approximation)
            import sys
            data_size = sum(
                sys.getsizeof(k) + sys.getsizeof(v)
                for k, v in self.cache.items()
            )
            
            hit_rate = 0.0
            total_requests = self._hits + self._misses
            if total_requests > 0:
                hit_rate = self._hits / total_requests
            
            return {
                'total_items': total_size,
                'meta_intents': meta_count,
                'nonces': nonce_count,
                'max_size': self.maxsize,
                'utilization': round(total_size / self.maxsize * 100, 1),
                'estimated_memory_kb': round(data_size / 1024, 2),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate * 100, 1)
            }
    
    def keys(self) -> List[str]:
        """Return all keys (for debugging)."""
        with self.lock:
            return list(self.cache.keys())
    
    def __len__(self) -> int:
        return len(self.cache)
    
    def __contains__(self, key: str) -> bool:
        return key in self.cache
