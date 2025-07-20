"""Tests for performance optimization module."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.performance.optimization import ConnectionPool, BatchProcessor, OptimizationSettings


@pytest.fixture
def optimization_settings():
    """Optimization settings fixture."""
    return OptimizationSettings(
        max_connections=20,
        connection_timeout=30,
        max_batch_size=100,
        batch_timeout=5.0,
        retry_attempts=3,
        retry_delay=1.0
    )


@pytest.fixture
def mock_connection():
    """Mock connection object."""
    connection = Mock()
    connection.close = AsyncMock()
    connection.is_healthy = Mock(return_value=True)
    return connection


class TestConnectionPool:
    """Test cases for ConnectionPool."""

    @pytest.mark.asyncio
    async def test_connection_pool_init_default(self):
        """Test ConnectionPool initialization with defaults."""
        async def factory():
            return Mock()
        
        pool = ConnectionPool(factory)
        assert pool.max_connections == 10
        assert pool.connection_timeout == 30
        assert len(pool._available) == 0
        assert len(pool._in_use) == 0

    @pytest.mark.asyncio
    async def test_connection_pool_init_custom_settings(self, optimization_settings):
        """Test ConnectionPool initialization with custom settings."""
        async def factory():
            return Mock()
        
        pool = ConnectionPool(factory, optimization_settings)
        assert pool.max_connections == 20
        assert pool.connection_timeout == 30

    @pytest.mark.asyncio
    async def test_connection_pool_acquire_new_connection(self, mock_connection):
        """Test acquiring a new connection when pool is empty."""
        async def factory():
            return mock_connection
        
        pool = ConnectionPool(factory)
        
        async with pool.acquire() as conn:
            assert conn == mock_connection
            assert len(pool._in_use) == 1
            assert len(pool._available) == 0
        
        # After context exit, connection should be returned to pool
        assert len(pool._in_use) == 0
        assert len(pool._available) == 1

    @pytest.mark.asyncio
    async def test_connection_pool_reuse_available_connection(self, mock_connection):
        """Test reusing an available connection."""
        async def factory():
            return Mock()
        
        pool = ConnectionPool(factory)
        pool._available.append(mock_connection)
        
        async with pool.acquire() as conn:
            assert conn == mock_connection
            assert len(pool._available) == 0
            assert len(pool._in_use) == 1

    @pytest.mark.asyncio
    async def test_connection_pool_max_connections_limit(self):
        """Test connection pool respects max connections limit."""
        call_count = 0
        
        async def factory():
            nonlocal call_count
            call_count += 1
            return Mock()
        
        pool = ConnectionPool(factory, OptimizationSettings(max_connections=2))
        
        # Acquire all available connections
        async with pool.acquire() as conn1:
            async with pool.acquire() as conn2:
                assert len(pool._in_use) == 2
                
                # Third acquisition should wait
                acquire_task = asyncio.create_task(pool.acquire().__aenter__())
                await asyncio.sleep(0.01)  # Let task start
                assert not acquire_task.done()
                
                acquire_task.cancel()
                try:
                    await acquire_task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_connection_pool_connection_timeout(self):
        """Test connection timeout during acquisition."""
        async def slow_factory():
            await asyncio.sleep(2)
            return Mock()
        
        settings = OptimizationSettings(connection_timeout=0.1)
        pool = ConnectionPool(slow_factory, settings)
        
        with pytest.raises(asyncio.TimeoutError):
            async with pool.acquire():
                pass

    @pytest.mark.asyncio
    async def test_connection_pool_unhealthy_connection_replacement(self):
        """Test replacing unhealthy connections."""
        healthy_connection = Mock()
        healthy_connection.is_healthy = Mock(return_value=True)
        healthy_connection.close = AsyncMock()
        
        unhealthy_connection = Mock()
        unhealthy_connection.is_healthy = Mock(return_value=False)
        unhealthy_connection.close = AsyncMock()
        
        call_count = 0
        async def factory():
            nonlocal call_count
            call_count += 1
            return healthy_connection if call_count > 1 else unhealthy_connection
        
        pool = ConnectionPool(factory)
        pool._available.append(unhealthy_connection)
        
        async with pool.acquire() as conn:
            assert conn == healthy_connection
            unhealthy_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_pool_close(self, mock_connection):
        """Test closing connection pool."""
        async def factory():
            return Mock()
        
        pool = ConnectionPool(factory)
        pool._available.append(mock_connection)
        
        await pool.close()
        
        mock_connection.close.assert_called_once()
        assert len(pool._available) == 0

    @pytest.mark.asyncio
    async def test_connection_pool_stats(self, mock_connection):
        """Test connection pool statistics."""
        async def factory():
            return Mock()
        
        pool = ConnectionPool(factory)
        pool._available.append(mock_connection)
        
        stats = pool.get_stats()
        
        assert stats['total_connections'] == 1
        assert stats['available_connections'] == 1
        assert stats['in_use_connections'] == 0
        assert stats['max_connections'] == 10


class TestBatchProcessor:
    """Test cases for BatchProcessor."""

    @pytest.mark.asyncio
    async def test_batch_processor_init_default(self):
        """Test BatchProcessor initialization with defaults."""
        async def handler(items):
            return items
        
        processor = BatchProcessor(handler)
        assert processor.max_batch_size == 50
        assert processor.batch_timeout == 1.0

    @pytest.mark.asyncio
    async def test_batch_processor_init_custom_settings(self, optimization_settings):
        """Test BatchProcessor initialization with custom settings."""
        async def handler(items):
            return items
        
        processor = BatchProcessor(handler, optimization_settings)
        assert processor.max_batch_size == 100
        assert processor.batch_timeout == 5.0

    @pytest.mark.asyncio
    async def test_batch_processor_single_item(self):
        """Test processing a single item."""
        async def handler(items):
            return [f"processed_{item}" for item in items]
        
        processor = BatchProcessor(handler)
        
        result = await processor.add("test_item")
        assert result == "processed_test_item"

    @pytest.mark.asyncio
    async def test_batch_processor_multiple_items(self):
        """Test processing multiple items in a batch."""
        async def handler(items):
            return [f"processed_{item}" for item in items]
        
        processor = BatchProcessor(handler)
        
        # Add multiple items concurrently
        tasks = [
            processor.add(f"item_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        expected = [f"processed_item_{i}" for i in range(5)]
        assert all(result in expected for result in results)

    @pytest.mark.asyncio
    async def test_batch_processor_max_batch_size_trigger(self):
        """Test batch processing triggered by max batch size."""
        processed_batches = []
        
        async def handler(items):
            processed_batches.append(len(items))
            return [f"processed_{item}" for item in items]
        
        settings = OptimizationSettings(max_batch_size=3)
        processor = BatchProcessor(handler, settings)
        
        # Add items that will trigger batch processing
        tasks = [processor.add(f"item_{i}") for i in range(5)]
        await asyncio.gather(*tasks)
        
        # Should have processed in batches of 3 and 2
        assert len(processed_batches) >= 1
        assert max(processed_batches) <= 3

    @pytest.mark.asyncio
    async def test_batch_processor_timeout_trigger(self):
        """Test batch processing triggered by timeout."""
        processed_batches = []
        
        async def handler(items):
            processed_batches.append(len(items))
            return [f"processed_{item}" for item in items]
        
        settings = OptimizationSettings(max_batch_size=100, batch_timeout=0.1)
        processor = BatchProcessor(handler, settings)
        
        # Add a single item and wait for timeout
        result = await processor.add("test_item")
        
        assert result == "processed_test_item"
        assert len(processed_batches) == 1
        assert processed_batches[0] == 1

    @pytest.mark.asyncio
    async def test_batch_processor_error_handling(self):
        """Test error handling in batch processor."""
        async def failing_handler(items):
            raise ValueError("Processing error")
        
        processor = BatchProcessor(failing_handler)
        
        with pytest.raises(ValueError, match="Processing error"):
            await processor.add("test_item")

    @pytest.mark.asyncio
    async def test_batch_processor_partial_failure(self):
        """Test handling partial failures in batch processing."""
        async def selective_handler(items):
            results = []
            for item in items:
                if item == "fail":
                    raise ValueError(f"Failed to process {item}")
                results.append(f"processed_{item}")
            return results
        
        processor = BatchProcessor(selective_handler)
        
        # Test with mix of successful and failing items
        with pytest.raises(ValueError):
            await asyncio.gather(
                processor.add("success"),
                processor.add("fail"),
                return_exceptions=False
            )

    @pytest.mark.asyncio
    async def test_batch_processor_stop(self):
        """Test stopping batch processor."""
        async def handler(items):
            return items
        
        processor = BatchProcessor(handler)
        
        # Start processor and then stop it
        await processor.start()
        assert processor._running is True
        
        await processor.stop()
        assert processor._running is False

    @pytest.mark.asyncio
    async def test_batch_processor_stats(self):
        """Test batch processor statistics."""
        async def handler(items):
            return items
        
        processor = BatchProcessor(handler)
        
        # Process some items
        await processor.add("item1")
        await processor.add("item2")
        
        stats = processor.get_stats()
        
        assert 'total_items' in stats
        assert 'total_batches' in stats
        assert 'average_batch_size' in stats
        assert stats['total_items'] >= 2

    @pytest.mark.asyncio
    async def test_batch_processor_concurrent_access(self):
        """Test concurrent access to batch processor."""
        processed_items = []
        
        async def handler(items):
            processed_items.extend(items)
            return [f"processed_{item}" for item in items]
        
        processor = BatchProcessor(handler)
        
        # Add many items concurrently
        tasks = [
            processor.add(f"item_{i}")
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All items should be processed
        assert len(results) == 20
        assert len(processed_items) == 20


def test_optimization_settings_validation():
    """Test OptimizationSettings validation."""
    # Valid settings
    settings = OptimizationSettings(
        max_connections=15,
        connection_timeout=60,
        max_batch_size=200,
        batch_timeout=2.0,
        retry_attempts=5,
        retry_delay=0.5
    )
    assert settings.max_connections == 15
    assert settings.connection_timeout == 60
    assert settings.max_batch_size == 200
    assert settings.batch_timeout == 2.0
    assert settings.retry_attempts == 5
    assert settings.retry_delay == 0.5
    
    # Test default values
    default_settings = OptimizationSettings()
    assert default_settings.max_connections == 10
    assert default_settings.connection_timeout == 30
    assert default_settings.max_batch_size == 50
    assert default_settings.batch_timeout == 1.0
    assert default_settings.retry_attempts == 3
    assert default_settings.retry_delay == 1.0


@pytest.mark.asyncio
async def test_connection_pool_integration_with_batch_processor():
    """Test integration between ConnectionPool and BatchProcessor."""
    # Mock connection for the pool
    mock_conn = Mock()
    mock_conn.execute = AsyncMock(return_value="result")
    mock_conn.is_healthy = Mock(return_value=True)
    mock_conn.close = AsyncMock()
    
    async def connection_factory():
        return mock_conn
    
    # Create connection pool
    pool = ConnectionPool(connection_factory)
    
    # Batch handler that uses the connection pool
    async def batch_handler(queries):
        results = []
        async with pool.acquire() as conn:
            for query in queries:
                result = await conn.execute(query)
                results.append(result)
        return results
    
    # Create batch processor
    processor = BatchProcessor(batch_handler)
    
    # Process multiple queries
    tasks = [
        processor.add(f"SELECT * FROM table_{i}")
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # Verify all queries were processed
    assert len(results) == 3
    assert all(result == "result" for result in results)
    
    # Clean up
    await pool.close()
    await processor.stop()