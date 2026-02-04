"""Caching service for expensive operations."""
import logging
import time
import hashlib
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheEntry:
    """A cache entry with TTL."""
    
    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.created_at = datetime.now()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        age = datetime.now() - self.created_at
        return age.total_seconds() > self.ttl_seconds
    
    def get_age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        age = datetime.now() - self.created_at
        return age.total_seconds()


class AgentCache:
    """In-memory cache for agent operations."""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Create a cache key from prefix and arguments."""
        # Create a hash of the arguments
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        if entry.is_expired():
            logger.debug(f"Cache entry expired: {key}")
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        logger.debug(f"Cache hit: {key} (age: {entry.get_age_seconds():.1f}s)")
        return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache with TTL."""
        self._cache[key] = CacheEntry(value, ttl_seconds)
        logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
    
    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache delete: {key}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        # Count expired entries
        expired_count = sum(1 for entry in self._cache.values() if entry.is_expired())
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "expired_entries": expired_count
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)


# Global cache instance
_global_cache = AgentCache()


def cached(prefix: str, ttl_seconds: int = 300):
    """
    Decorator to cache function results.
    
    Args:
        prefix: Cache key prefix
        ttl_seconds: Time to live in seconds (default: 5 minutes)
    
    Example:
        @cached("schema", ttl_seconds=600)
        async def get_schema(datasource_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = _global_cache._make_key(prefix, *args, **kwargs)
            
            # Try cache first
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Cache miss - execute function
            result = await func(*args, **kwargs)
            
            # Cache the result
            _global_cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache_key = _global_cache._make_key(prefix, *args, **kwargs)
            
            # Try cache first
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Cache miss - execute function
            result = func(*args, **kwargs)
            
            # Cache the result
            _global_cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def get_cache() -> AgentCache:
    """Get the global cache instance."""
    return _global_cache
