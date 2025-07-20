"""
Caching strategies for performance optimization
CodeFarm T04 Production Optimization Implementation
"""
import asyncio
import json
import hashlib
import logging
from typing import Any, Optional, Dict, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import redis.asyncio as redis
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class CacheSettings(BaseSettings):
    """Cache configuration settings"""
    redis_url: str = "redis://localhost:6379/1"
    default_ttl: int = 3600  # 1 hour
    max_connections: int = 10
    socket_keepalive: bool = True
    health_check_interval: int = 30
    retry_on_timeout: bool = True
    
    class Config:
        env_prefix = "CACHE_"


class CacheManager:
    """Centralized cache management with Redis backend"""
    
    def __init__(self, settings: Optional[CacheSettings] = None):
        self.settings = settings or CacheSettings()
        self.redis_pool: Optional[redis.ConnectionPool] = None
        self.redis_client: Optional[redis.Redis] = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize Redis connection pool"""
        if self._initialized:
            return
            
        try:
            self.redis_pool = redis.ConnectionPool.from_url(
                self.settings.redis_url,
                max_connections=self.settings.max_connections,
                socket_keepalive=self.settings.socket_keepalive,
                health_check_interval=self.settings.health_check_interval,
                retry_on_timeout=self.settings.retry_on_timeout,
                decode_responses=True
            )
            
            self.redis_client = redis.Redis(connection_pool=self.redis_pool)
            
            # Test connection
            await self.redis_client.ping()
            self._initialized = True
            logger.info("Cache manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize cache manager: {e}")
            raise
    
    async def close(self):
        """Close Redis connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.redis_pool:
            await self.redis_pool.disconnect()
        self._initialized = False
        logger.info("Cache manager closed")
        
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        if not self._initialized:
            await self.initialize()
            
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
        return None
        
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set cached value with TTL"""
        if not self._initialized:
            await self.initialize()
            
        try:
            ttl = ttl or self.settings.default_ttl
            serialized = json.dumps(value, default=str)
            
            if nx:
                # Set only if key doesn't exist
                result = await self.redis_client.set(key, serialized, ex=ttl, nx=True)
            elif xx:
                # Set only if key exists
                result = await self.redis_client.set(key, serialized, ex=ttl, xx=True)
            else:
                # Normal set
                result = await self.redis_client.setex(key, ttl, serialized)
                
            return bool(result)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
            
    async def delete(self, key: Union[str, list]) -> int:
        """Delete cached value(s)"""
        if not self._initialized:
            await self.initialize()
            
        try:
            if isinstance(key, str):
                result = await self.redis_client.delete(key)
            else:
                result = await self.redis_client.delete(*key)
            return result
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return 0
            
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self._initialized:
            await self.initialize()
            
        try:
            return bool(await self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
            
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for existing key"""
        if not self._initialized:
            await self.initialize()
            
        try:
            return bool(await self.redis_client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False
            
    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        if not self._initialized:
            await self.initialize()
            
        try:
            return await self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -1
            
    async def get_or_set(
        self, 
        key: str, 
        factory: Callable, 
        ttl: Optional[int] = None
    ) -> Any:
        """Get from cache or compute and cache"""
        # Try cache first
        value = await self.get(key)
        if value is not None:
            return value
            
        # Compute value
        try:
            if asyncio.iscoroutinefunction(factory):
                computed_value = await factory()
            else:
                computed_value = factory()
                
            # Cache the computed value
            await self.set(key, computed_value, ttl)
            return computed_value
        except Exception as e:
            logger.error(f"Factory function error for key {key}: {e}")
            raise
            
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern"""
        if not self._initialized:
            await self.initialize()
            
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate pattern error for {pattern}: {e}")
            return 0
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self._initialized:
            await self.initialize()
            
        try:
            info = await self.redis_client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                )
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}
            
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate"""
        total = hits + misses
        if total == 0:
            return 0.0
        return hits / total


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """Get global cache manager instance"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.initialize()
    return _cache_manager


def cache_result(
    ttl: int = 3600, 
    key_prefix: str = "",
    namespace: str = "default",
    serialize_args: bool = True
):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [namespace, key_prefix, func.__name__]
            
            if serialize_args:
                if args:
                    key_parts.extend(str(arg) for arg in args)
                if kwargs:
                    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Get cache manager
            cache_manager = await get_cache_manager()
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
                
            # Compute and cache result
            logger.debug(f"Cache miss for key: {cache_key}")
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                
            await cache_manager.set(cache_key, result, ttl)
            return result
            
        return wrapper
    return decorator


class CacheInvalidator:
    """Helper class for cache invalidation patterns"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user"""
        pattern = f"*:user:{user_id}:*"
        return await self.cache_manager.invalidate_pattern(pattern)
        
    async def invalidate_agent_cache(self, agent_type: str):
        """Invalidate all cache entries for an agent"""
        pattern = f"*:agent:{agent_type}:*"
        return await self.cache_manager.invalidate_pattern(pattern)
        
    async def invalidate_memory_cache(self, collection_name: str):
        """Invalidate all memory-related cache entries"""
        patterns = [
            f"*:memory:{collection_name}:*",
            f"*:search:{collection_name}:*",
            f"*:qdrant:{collection_name}:*"
        ]
        total_deleted = 0
        for pattern in patterns:
            total_deleted += await self.cache_manager.invalidate_pattern(pattern)
        return total_deleted