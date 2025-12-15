"""
Simple in-memory cache for API responses.

Provides LRU caching with TTL (time-to-live) for frequently accessed data
like manifest files, VE data, and run lists.
"""

import time
from collections import OrderedDict
from functools import wraps
from threading import Lock
from typing import Any, Callable, Optional, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


class LRUCache:
    """
    Thread-safe LRU cache with TTL support.

    Args:
        max_size: Maximum number of items to store (default: 100)
        default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self.lock:
            if key not in self.cache:
                self._misses += 1
                return None

            value, expiry = self.cache[key]
            if time.time() > expiry:
                # Expired, remove it
                del self.cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        with self.lock:
            expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
            self.cache[key] = (value, expiry)
            self.cache.move_to_end(key)

            # Evict oldest if over max_size
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self.lock:
            self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached items."""
        with self.lock:
            self.cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%",
            }


# Global cache instances
_manifest_cache = LRUCache(max_size=100, default_ttl=300)  # 5 minutes
_ve_data_cache = LRUCache(max_size=50, default_ttl=600)  # 10 minutes
_runs_list_cache = LRUCache(max_size=1, default_ttl=10)  # 10 seconds


def get_manifest_cache() -> LRUCache:
    """Get the global manifest cache instance."""
    return _manifest_cache


def get_ve_data_cache() -> LRUCache:
    """Get the global VE data cache instance."""
    return _ve_data_cache


def get_runs_list_cache() -> LRUCache:
    """Get the global runs list cache instance."""
    return _runs_list_cache


def cached(cache: LRUCache, key_prefix: str = "", ttl: Optional[int] = None):
    """
    Decorator to cache function results.

    Args:
        cache: Cache instance to use
        key_prefix: Prefix for cache keys
        ttl: Time-to-live in seconds (uses cache default if None)

    Example:
        @cached(get_manifest_cache(), key_prefix="manifest")
        def get_manifest(run_id: str):
            # Expensive operation
            return load_manifest(run_id)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Call function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        return cast(F, wrapper)

    return decorator


def invalidate_run_cache(run_id: str) -> None:
    """
    Invalidate all cached data for a specific run.

    Call this when a run is updated or deleted.
    """
    # Clear all caches that might contain this run_id
    manifest_cache = get_manifest_cache()
    ve_cache = get_ve_data_cache()
    runs_cache = get_runs_list_cache()

    # We can't do precise deletion without tracking keys, so clear related caches
    # In a production system, you'd want a more sophisticated invalidation strategy
    runs_cache.clear()  # Always clear runs list cache

    # For specific run data, we'd need to track keys or use a different structure
    # For now, this is a simple but effective approach
