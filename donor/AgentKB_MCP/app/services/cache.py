"""
Redis caching service.

Provides caching layer for retrieval results and responses.
"""

import json
import hashlib
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Redis-based caching service.
    
    Caches retrieval results and API responses to reduce
    latency and LLM API costs.
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize the cache service.
        
        Args:
            redis_client: Optional Redis client. If not provided,
                         creates one from settings.
        """
        self.settings = get_settings()
        self._redis: Optional[redis.Redis] = redis_client
        self._connected = False
    
    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.settings.redis.url,
                encoding="utf-8",
                decode_responses=True
            )
        self._connected = True
        logger.info("Redis cache connected")
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            self._connected = False
        logger.info("Redis cache connection closed")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected and self._redis is not None
    
    def _generate_cache_key(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None
    ) -> str:
        """
        Generate a unique cache key for a query.
        
        Args:
            question: The normalized question
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            
        Returns:
            SHA256-based cache key
        """
        components = [
            question.lower().strip(),
            domain or "",
            software_version or "",
            stack_pack or ""
        ]
        content = "|".join(components)
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:32]
        return f"kb:cache:{hash_value}"
    
    async def get(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result for a query.
        
        Args:
            question: The question to look up
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            
        Returns:
            Cached result dict or None if not found
        """
        if not self.is_connected:
            return None
        
        try:
            key = self._generate_cache_key(
                question, domain, software_version, stack_pack
            )
            cached = await self._redis.get(key)
            
            if cached:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(cached)
            
            logger.debug(f"Cache miss for key: {key}")
            return None
            
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    async def set(
        self,
        question: str,
        result: Dict[str, Any],
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None,
        is_hit: bool = True
    ) -> bool:
        """
        Cache a query result.
        
        Args:
            question: The question
            result: The result to cache
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            is_hit: Whether this was a hit (longer TTL) or miss (shorter TTL)
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self.is_connected:
            return False
        
        try:
            key = self._generate_cache_key(
                question, domain, software_version, stack_pack
            )
            
            # Determine TTL based on hit/miss
            ttl = self.settings.redis.cache_ttl_hit if is_hit else self.settings.redis.cache_ttl_miss
            
            # Add cache metadata
            result["_cached_at"] = datetime.utcnow().isoformat()
            result["_cache_ttl"] = ttl
            
            await self._redis.setex(
                key,
                ttl,
                json.dumps(result, default=str)
            )
            
            logger.debug(f"Cached result for key: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    async def invalidate(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None
    ) -> bool:
        """
        Invalidate a cached result.
        
        Args:
            question: The question
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            
        Returns:
            True if invalidated, False otherwise
        """
        if not self.is_connected:
            return False
        
        try:
            key = self._generate_cache_key(
                question, domain, software_version, stack_pack
            )
            await self._redis.delete(key)
            logger.debug(f"Invalidated cache key: {key}")
            return True
            
        except Exception as e:
            logger.warning(f"Cache invalidate error: {e}")
            return False
    
    async def invalidate_domain(self, domain: str) -> int:
        """
        Invalidate all cached results for a domain.
        
        Uses pattern matching to find and delete all keys
        associated with a domain. Note: This is expensive
        and should be used sparingly.
        
        Args:
            domain: The domain to invalidate
            
        Returns:
            Number of keys invalidated
        """
        if not self.is_connected:
            return 0
        
        try:
            # Pattern matching on cache keys
            # Note: KEYS is expensive in production; consider SCAN
            pattern = f"kb:cache:*"
            count = 0
            
            async for key in self._redis.scan_iter(match=pattern):
                # Check if this key is for the domain
                # This is a simplification; proper implementation
                # would store domain in the value
                cached = await self._redis.get(key)
                if cached:
                    data = json.loads(cached)
                    if data.get("domain") == domain:
                        await self._redis.delete(key)
                        count += 1
            
            logger.info(f"Invalidated {count} cache keys for domain: {domain}")
            return count
            
        except Exception as e:
            logger.warning(f"Cache domain invalidate error: {e}")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Redis health.
        
        Returns:
            Health status dict
        """
        import time
        start = time.time()
        
        try:
            if not self.is_connected:
                return {
                    "status": "disconnected",
                    "error": "Not connected to Redis"
                }
            
            await self._redis.ping()
            elapsed_ms = (time.time() - start) * 1000
            
            # Get memory info
            info = await self._redis.info("memory")
            used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            return {
                "status": "healthy",
                "response_time_ms": round(elapsed_ms, 2),
                "used_memory_mb": round(used_memory_mb, 2)
            }
            
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            return {
                "status": "unhealthy",
                "response_time_ms": round(elapsed_ms, 2),
                "error": str(e)
            }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Stats dict with key counts, memory usage, etc.
        """
        if not self.is_connected:
            return {"status": "disconnected"}
        
        try:
            info = await self._redis.info()
            
            # Count KB cache keys
            kb_key_count = 0
            async for _ in self._redis.scan_iter(match="kb:cache:*"):
                kb_key_count += 1
            
            return {
                "status": "connected",
                "kb_cache_keys": kb_key_count,
                "total_keys": info.get("db0", {}).get("keys", 0),
                "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

