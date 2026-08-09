"""
Caching layer for WordPress authentication library.

Provides in-memory caching with optional Redis support for production deployments.
"""

import json
import time
from typing import Optional, Any
from abc import ABC, abstractmethod
from .exceptions import CacheError


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: int) -> None:
        """Store a value in cache with TTL in seconds."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a value from cache."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        pass


class InMemoryCache(CacheBackend):
    """
    In-memory cache implementation with TTL support.
    
    This is a simple thread-safe in-memory cache suitable for development
    and single-instance deployments. For production with multiple instances,
    consider using RedisCache.
    """
    
    def __init__(self):
        """Initialize in-memory cache storage."""
        self._cache: dict[str, dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists and not expired, None otherwise
        """
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if entry["expires_at"] < time.time():
            del self._cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        """
        Store a value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds
        """
        try:
            # Ensure value is JSON-serializable
            json.dumps(value)
            
            self._cache[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
            }
        except (TypeError, ValueError) as e:
            raise CacheError(f"Cache value must be JSON-serializable: {e}")
    
    def delete(self, key: str) -> None:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
        """
        self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry["expires_at"] < current_time
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)


class RedisCache(CacheBackend):
    """
    Redis cache implementation for production deployments.
    
    This requires the redis library to be installed. It provides distributed
    caching suitable for multi-instance deployments.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL (default: redis://localhost:6379/0)
            
        Raises:
            CacheError: If redis library is not installed or connection fails
        """
        try:
            import redis
        except ImportError:
            raise CacheError(
                "Redis library not installed. Install with: pip install redis"
            )
        
        try:
            self._client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self._client.ping()
        except Exception as e:
            raise CacheError(f"Failed to connect to Redis: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from Redis cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value if exists, None otherwise
        """
        try:
            value = self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            raise CacheError(f"Failed to get value from Redis: {e}")
    
    def set(self, key: str, value: Any, ttl: int) -> None:
        """
        Store a value in Redis cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds
        """
        try:
            serialized = json.dumps(value)
            self._client.setex(key, ttl, serialized)
        except Exception as e:
            raise CacheError(f"Failed to set value in Redis: {e}")
    
    def delete(self, key: str) -> None:
        """
        Delete a value from Redis cache.
        
        Args:
            key: Cache key
        """
        try:
            self._client.delete(key)
        except Exception as e:
            raise CacheError(f"Failed to delete value from Redis: {e}")
    
    def clear(self) -> None:
        """Clear all cached values from Redis."""
        try:
            self._client.flushdb()
        except Exception as e:
            raise CacheError(f"Failed to clear Redis cache: {e}")


class Cache:
    """
    High-level cache interface that automatically selects backend.
    
    This provides a simple interface for caching authentication results
    to avoid hammering WordPress sites with repeated requests.
    """
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        """
        Initialize cache with specified backend.
        
        Args:
            backend: Cache backend to use. If None, uses InMemoryCache.
        """
        self._backend = backend or InMemoryCache()
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from cache."""
        return self._backend.get(key)
    
    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        Store a value in cache with TTL (default: 5 minutes).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 300)
        """
        self._backend.set(key, value, ttl)
    
    def delete(self, key: str) -> None:
        """Delete a value from cache."""
        self._backend.delete(key)
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._backend.clear()
    
    @staticmethod
    def create_redis(redis_url: str = "redis://localhost:6379/0") -> "Cache":
        """
        Create a Cache instance with Redis backend.
        
        Args:
            redis_url: Redis connection URL
            
        Returns:
            Cache instance with Redis backend
        """
        return Cache(backend=RedisCache(redis_url))
