"""Tests for performance cache module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.performance.cache import CacheManager, CacheSettings


@pytest.fixture
def cache_settings():
    """Cache settings fixture."""
    return CacheSettings(
        redis_url="redis://localhost:6379",
        default_ttl=300,
        max_connections=10,
        retry_attempts=3
    )


@pytest.fixture
def mock_redis_pool():
    """Mock Redis connection pool."""
    pool = Mock()
    pool.get_connection = AsyncMock()
    pool.release = Mock()
    return pool


@pytest.mark.asyncio
async def test_cache_manager_init_default_settings():
    """Test CacheManager initialization with default settings."""
    manager = CacheManager()
    assert manager.settings is not None
    assert manager.settings.default_ttl == 3600  # Default 1 hour
    assert manager.redis_pool is None


@pytest.mark.asyncio
async def test_cache_manager_init_custom_settings(cache_settings):
    """Test CacheManager initialization with custom settings."""
    manager = CacheManager(cache_settings)
    assert manager.settings == cache_settings
    assert manager.settings.default_ttl == 300


@pytest.mark.asyncio
async def test_cache_manager_get_connection_creates_pool():
    """Test that get_connection creates Redis pool if not exists."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_pool = Mock()
        mock_pool_class.from_url.return_value = mock_pool
        
        manager = CacheManager()
        await manager._get_connection()
        
        mock_pool_class.from_url.assert_called_once()
        assert manager.redis_pool == mock_pool


@pytest.mark.asyncio
async def test_cache_manager_set_and_get():
    """Test cache set and get operations."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        # Mock Redis connection
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        # Mock Redis operations
        mock_connection.set = AsyncMock()
        mock_connection.get = AsyncMock(return_value=b'{"test": "value"}')
        mock_connection.close = Mock()
        
        manager = CacheManager()
        
        # Test set operation
        await manager.set("test_key", {"test": "value"}, ttl=300)
        mock_connection.set.assert_called_once()
        
        # Test get operation
        result = await manager.get("test_key")
        mock_connection.get.assert_called_once_with("test_key")
        assert result == {"test": "value"}


@pytest.mark.asyncio
async def test_cache_manager_get_missing_key():
    """Test get operation with missing key returns None."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_connection.get = AsyncMock(return_value=None)
        mock_connection.close = Mock()
        
        manager = CacheManager()
        result = await manager.get("missing_key")
        
        assert result is None


@pytest.mark.asyncio
async def test_cache_manager_get_or_set_cache_hit():
    """Test get_or_set with cache hit."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_connection.get = AsyncMock(return_value=b'{"cached": "value"}')
        mock_connection.close = Mock()
        
        manager = CacheManager()
        
        # Factory function should not be called
        factory = Mock(return_value={"new": "value"})
        
        result = await manager.get_or_set("test_key", factory)
        
        assert result == {"cached": "value"}
        factory.assert_not_called()


@pytest.mark.asyncio
async def test_cache_manager_get_or_set_cache_miss():
    """Test get_or_set with cache miss."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        # First get returns None (cache miss), second get not called
        mock_connection.get = AsyncMock(return_value=None)
        mock_connection.set = AsyncMock()
        mock_connection.close = Mock()
        
        manager = CacheManager()
        
        # Factory function that returns a value
        def factory():
            return {"computed": "value"}
        
        result = await manager.get_or_set("test_key", factory, ttl=300)
        
        # Should get the computed value
        assert result == {"computed": "value"}
        
        # Should have called set to cache the result
        mock_connection.set.assert_called_once()


@pytest.mark.asyncio
async def test_cache_manager_get_or_set_async_factory():
    """Test get_or_set with async factory function."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_connection.get = AsyncMock(return_value=None)
        mock_connection.set = AsyncMock()
        mock_connection.close = Mock()
        
        manager = CacheManager()
        
        # Async factory function
        async def async_factory():
            return {"async_computed": "value"}
        
        result = await manager.get_or_set("test_key", async_factory)
        
        assert result == {"async_computed": "value"}


@pytest.mark.asyncio
async def test_cache_manager_delete():
    """Test cache delete operation."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_connection.delete = AsyncMock(return_value=1)
        mock_connection.close = Mock()
        
        manager = CacheManager()
        result = await manager.delete("test_key")
        
        mock_connection.delete.assert_called_once_with("test_key")
        assert result is True


@pytest.mark.asyncio
async def test_cache_manager_clear_pattern():
    """Test cache clear with pattern."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        mock_connection.keys = AsyncMock(return_value=[b"test:key1", b"test:key2"])
        mock_connection.delete = AsyncMock(return_value=2)
        mock_connection.close = Mock()
        
        manager = CacheManager()
        result = await manager.clear("test:*")
        
        mock_connection.keys.assert_called_once_with("test:*")
        mock_connection.delete.assert_called_once()
        assert result == 2


@pytest.mark.asyncio
async def test_cache_manager_connection_error_handling():
    """Test connection error handling with retry logic."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_connection = AsyncMock()
        mock_pool = Mock()
        mock_pool.get_connection = Mock(return_value=mock_connection)
        mock_pool_class.from_url.return_value = mock_pool
        
        # Simulate connection error
        mock_connection.get = AsyncMock(side_effect=Exception("Connection failed"))
        mock_connection.close = Mock()
        
        manager = CacheManager()
        
        # Should handle error gracefully and return None
        result = await manager.get("test_key")
        assert result is None


@pytest.mark.asyncio
async def test_cache_manager_close():
    """Test cache manager close operation."""
    with patch('src.performance.cache.redis.ConnectionPool') as mock_pool_class:
        mock_pool = Mock()
        mock_pool.disconnect = AsyncMock()
        mock_pool_class.from_url.return_value = mock_pool
        
        manager = CacheManager()
        await manager._get_connection()  # Initialize pool
        
        await manager.close()
        
        mock_pool.disconnect.assert_called_once()
        assert manager.redis_pool is None


def test_cache_settings_validation():
    """Test CacheSettings validation."""
    # Valid settings
    settings = CacheSettings(
        redis_url="redis://localhost:6379",
        default_ttl=300,
        max_connections=10
    )
    assert settings.redis_url == "redis://localhost:6379"
    assert settings.default_ttl == 300
    assert settings.max_connections == 10
    
    # Test default values
    default_settings = CacheSettings()
    assert default_settings.default_ttl == 3600
    assert default_settings.max_connections == 10
    assert default_settings.retry_attempts == 3