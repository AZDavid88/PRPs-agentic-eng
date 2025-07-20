"""
Connection pooling and batch processing optimization
CodeFarm T04 Production Optimization Implementation
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Callable, Union, TypeVar, Generic
from dataclasses import dataclass
from contextlib import asynccontextmanager
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from pydantic_settings import BaseSettings
import httpx


logger = logging.getLogger(__name__)
T = TypeVar('T')


class OptimizationSettings(BaseSettings):
    """Optimization configuration settings"""
    redis_pool_size: int = 10
    qdrant_pool_size: int = 5
    http_pool_size: int = 20
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    
    class Config:
        env_prefix = "OPTIMIZATION_"


@dataclass
class ConnectionStats:
    """Connection pool statistics"""
    pool_size: int
    active_connections: int
    idle_connections: int
    total_created: int
    total_closed: int
    errors: int


class ConnectionPool(Generic[T]):
    """Generic connection pool for external services"""
    
    def __init__(
        self,
        create_connection: Callable[[], T],
        close_connection: Callable[[T], None] = None,
        validate_connection: Callable[[T], bool] = None,
        max_size: int = 10,
        min_size: int = 1,
        max_idle_time: float = 300.0,
        name: str = "generic"
    ):
        self.create_connection = create_connection
        self.close_connection = close_connection or (lambda x: None)
        self.validate_connection = validate_connection or (lambda x: True)
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle_time = max_idle_time
        self.name = name
        
        # Pool state
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._connections: Dict[int, T] = {}
        self._connection_times: Dict[int, float] = {}
        self._stats = ConnectionStats(
            pool_size=0,
            active_connections=0,
            idle_connections=0,
            total_created=0,
            total_closed=0,
            errors=0
        )
        self._lock = asyncio.Lock()
        self._closed = False
        
    async def initialize(self):
        """Initialize connection pool with minimum connections"""
        async with self._lock:
            if self._closed:
                return
                
            for _ in range(self.min_size):
                try:
                    connection = await self._create_new_connection()
                    await self._pool.put(connection)
                    self._stats.pool_size += 1
                    self._stats.idle_connections += 1
                except Exception as e:
                    logger.error(f"Failed to initialize connection in pool '{self.name}': {e}")
                    self._stats.errors += 1
        
        logger.info(f"Connection pool '{self.name}' initialized with {self._stats.pool_size} connections")
    
    async def _create_new_connection(self) -> T:
        """Create a new connection"""
        try:
            if asyncio.iscoroutinefunction(self.create_connection):
                connection = await self.create_connection()
            else:
                connection = self.create_connection()
            
            connection_id = id(connection)
            self._connections[connection_id] = connection
            self._connection_times[connection_id] = time.time()
            self._stats.total_created += 1
            
            return connection
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Failed to create connection in pool '{self.name}': {e}")
            raise
    
    async def _close_connection(self, connection: T):
        """Close a connection"""
        try:
            connection_id = id(connection)
            
            if asyncio.iscoroutinefunction(self.close_connection):
                await self.close_connection(connection)
            else:
                self.close_connection(connection)
            
            self._connections.pop(connection_id, None)
            self._connection_times.pop(connection_id, None)
            self._stats.total_closed += 1
            
        except Exception as e:
            logger.error(f"Failed to close connection in pool '{self.name}': {e}")
            self._stats.errors += 1
    
    async def _validate_connection(self, connection: T) -> bool:
        """Validate a connection"""
        try:
            if asyncio.iscoroutinefunction(self.validate_connection):
                return await self.validate_connection(connection)
            else:
                return self.validate_connection(connection)
        except Exception as e:
            logger.warning(f"Connection validation failed in pool '{self.name}': {e}")
            return False
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool"""
        if self._closed:
            raise RuntimeError(f"Connection pool '{self.name}' is closed")
        
        connection = None
        try:
            # Try to get from pool
            try:
                connection = await asyncio.wait_for(self._pool.get(), timeout=1.0)
                self._stats.idle_connections -= 1
                self._stats.active_connections += 1
            except asyncio.TimeoutError:
                # Pool is empty, create new connection if under limit
                async with self._lock:
                    if self._stats.pool_size < self.max_size:
                        connection = await self._create_new_connection()
                        self._stats.pool_size += 1
                        self._stats.active_connections += 1
                    else:
                        # Wait for connection to become available
                        connection = await self._pool.get()
                        self._stats.idle_connections -= 1
                        self._stats.active_connections += 1
            
            # Validate connection
            if not await self._validate_connection(connection):
                await self._close_connection(connection)
                connection = await self._create_new_connection()
            
            yield connection
            
        except Exception as e:
            self._stats.errors += 1
            logger.error(f"Error in connection pool '{self.name}': {e}")
            if connection:
                await self._close_connection(connection)
                connection = None
            raise
        finally:
            if connection:
                try:
                    # Return connection to pool
                    await self._pool.put(connection)
                    self._stats.active_connections -= 1
                    self._stats.idle_connections += 1
                except Exception as e:
                    logger.error(f"Failed to return connection to pool '{self.name}': {e}")
                    await self._close_connection(connection)
    
    async def cleanup_idle_connections(self):
        """Remove connections that have been idle too long"""
        if self._closed:
            return
            
        current_time = time.time()
        connections_to_close = []
        
        async with self._lock:
            # Check for idle connections
            for conn_id, conn_time in list(self._connection_times.items()):
                if current_time - conn_time > self.max_idle_time:
                    if conn_id in self._connections:
                        connections_to_close.append(self._connections[conn_id])
        
        # Close idle connections
        for connection in connections_to_close:
            try:
                await self._close_connection(connection)
                self._stats.pool_size -= 1
                # Don't need to adjust idle count as these aren't in the queue
            except Exception as e:
                logger.error(f"Failed to close idle connection in pool '{self.name}': {e}")
    
    def get_stats(self) -> ConnectionStats:
        """Get connection pool statistics"""
        return self._stats
    
    async def close(self):
        """Close all connections in the pool"""
        self._closed = True
        
        # Close all connections in pool
        while not self._pool.empty():
            try:
                connection = await self._pool.get()
                await self._close_connection(connection)
            except Exception as e:
                logger.error(f"Error closing pooled connection in '{self.name}': {e}")
        
        # Close any remaining connections
        for connection in list(self._connections.values()):
            await self._close_connection(connection)
        
        self._connections.clear()
        self._connection_times.clear()
        logger.info(f"Connection pool '{self.name}' closed")


class BatchProcessor:
    """Batch processor for optimizing bulk operations"""
    
    def __init__(self, settings: Optional[OptimizationSettings] = None):
        self.settings = settings or OptimizationSettings()
        self._processing_queue: Dict[str, List[Any]] = {}
        self._queue_lock = asyncio.Lock()
        self._processor_tasks: Dict[str, asyncio.Task] = {}
        
    async def add_to_batch(self, batch_type: str, item: Any) -> bool:
        """Add an item to a processing batch"""
        async with self._queue_lock:
            if batch_type not in self._processing_queue:
                self._processing_queue[batch_type] = []
            
            self._processing_queue[batch_type].append(item)
            
            # Start processor if not running
            if batch_type not in self._processor_tasks:
                self._processor_tasks[batch_type] = asyncio.create_task(
                    self._process_batch(batch_type)
                )
            
            return len(self._processing_queue[batch_type]) >= self.settings.batch_size
    
    async def _process_batch(self, batch_type: str):
        """Process a batch of items"""
        while batch_type in self._processing_queue:
            try:
                await asyncio.sleep(0.1)  # Small delay to allow batching
                
                async with self._queue_lock:
                    if not self._processing_queue.get(batch_type):
                        # Remove empty queue and task
                        self._processing_queue.pop(batch_type, None)
                        self._processor_tasks.pop(batch_type, None)
                        break
                    
                    # Get batch to process
                    batch = self._processing_queue[batch_type][:self.settings.batch_size]
                    self._processing_queue[batch_type] = self._processing_queue[batch_type][self.settings.batch_size:]
                
                if batch:
                    await self._execute_batch(batch_type, batch)
                    
            except Exception as e:
                logger.error(f"Error processing batch '{batch_type}': {e}")
                await asyncio.sleep(1.0)  # Back off on error
    
    async def _execute_batch(self, batch_type: str, batch: List[Any]):
        """Execute a batch operation - to be overridden by specific implementations"""
        logger.info(f"Processing batch '{batch_type}' with {len(batch)} items")
        
        # Default implementation - process items individually
        for item in batch:
            try:
                await self._process_single_item(batch_type, item)
            except Exception as e:
                logger.error(f"Error processing item in batch '{batch_type}': {e}")
    
    async def _process_single_item(self, batch_type: str, item: Any):
        """Process a single item - to be overridden"""
        logger.debug(f"Processing single item in batch '{batch_type}': {item}")
    
    async def force_process_batch(self, batch_type: str) -> int:
        """Force immediate processing of pending batch items"""
        async with self._queue_lock:
            batch = self._processing_queue.get(batch_type, [])
            if batch:
                self._processing_queue[batch_type] = []
                await self._execute_batch(batch_type, batch)
                return len(batch)
        return 0
    
    def get_batch_status(self) -> Dict[str, int]:
        """Get current batch queue status"""
        return {
            batch_type: len(items) 
            for batch_type, items in self._processing_queue.items()
        }
    
    async def close(self):
        """Close batch processor and process remaining items"""
        # Process all remaining batches
        for batch_type in list(self._processing_queue.keys()):
            await self.force_process_batch(batch_type)
        
        # Cancel running tasks
        for task in self._processor_tasks.values():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._processor_tasks.clear()
        self._processing_queue.clear()


class QdrantBatchProcessor(BatchProcessor):
    """Specialized batch processor for Qdrant operations"""
    
    def __init__(self, qdrant_client: AsyncQdrantClient, settings: Optional[OptimizationSettings] = None):
        super().__init__(settings)
        self.qdrant_client = qdrant_client
    
    async def _execute_batch(self, batch_type: str, batch: List[Any]):
        """Execute Qdrant batch operations"""
        if batch_type == "upsert":
            await self._batch_upsert(batch)
        elif batch_type == "delete":
            await self._batch_delete(batch)
        else:
            await super()._execute_batch(batch_type, batch)
    
    async def _batch_upsert(self, batch: List[Dict[str, Any]]):
        """Batch upsert operations to Qdrant"""
        try:
            # Group by collection
            collections = {}
            for item in batch:
                collection_name = item.get("collection_name")
                if collection_name:
                    if collection_name not in collections:
                        collections[collection_name] = []
                    collections[collection_name].append(item)
            
            # Process each collection
            for collection_name, items in collections.items():
                points = []
                for item in items:
                    point = PointStruct(
                        id=item.get("id"),
                        vector=item.get("vector"),
                        payload=item.get("payload", {})
                    )
                    points.append(point)
                
                await self.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                
                logger.info(f"Batch upserted {len(points)} points to collection '{collection_name}'")
                
        except Exception as e:
            logger.error(f"Batch upsert failed: {e}")
            raise
    
    async def _batch_delete(self, batch: List[Dict[str, Any]]):
        """Batch delete operations from Qdrant"""
        try:
            # Group by collection
            collections = {}
            for item in batch:
                collection_name = item.get("collection_name")
                if collection_name:
                    if collection_name not in collections:
                        collections[collection_name] = []
                    collections[collection_name].append(item.get("id"))
            
            # Process each collection
            for collection_name, point_ids in collections.items():
                await self.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=point_ids
                )
                
                logger.info(f"Batch deleted {len(point_ids)} points from collection '{collection_name}'")
                
        except Exception as e:
            logger.error(f"Batch delete failed: {e}")
            raise


# Factory functions for common connection pools
async def create_redis_pool(
    redis_url: str = "redis://localhost:6379/1",
    max_size: int = 10
) -> ConnectionPool[redis.Redis]:
    """Create a Redis connection pool"""
    
    async def create_connection() -> redis.Redis:
        return redis.Redis.from_url(redis_url, decode_responses=True)
    
    async def close_connection(conn: redis.Redis):
        await conn.close()
    
    async def validate_connection(conn: redis.Redis) -> bool:
        try:
            await conn.ping()
            return True
        except:
            return False
    
    pool = ConnectionPool(
        create_connection=create_connection,
        close_connection=close_connection,
        validate_connection=validate_connection,
        max_size=max_size,
        name="redis"
    )
    
    await pool.initialize()
    return pool


async def create_qdrant_pool(
    qdrant_url: str = "http://localhost:6333",
    max_size: int = 5
) -> ConnectionPool[AsyncQdrantClient]:
    """Create a Qdrant connection pool"""
    
    async def create_connection() -> AsyncQdrantClient:
        return AsyncQdrantClient(url=qdrant_url)
    
    async def close_connection(conn: AsyncQdrantClient):
        await conn.close()
    
    async def validate_connection(conn: AsyncQdrantClient) -> bool:
        try:
            await conn.get_collections()
            return True
        except:
            return False
    
    pool = ConnectionPool(
        create_connection=create_connection,
        close_connection=close_connection,
        validate_connection=validate_connection,
        max_size=max_size,
        name="qdrant"
    )
    
    await pool.initialize()
    return pool


async def create_http_pool(
    max_size: int = 20,
    timeout: float = 30.0
) -> ConnectionPool[httpx.AsyncClient]:
    """Create an HTTP client connection pool"""
    
    async def create_connection() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=max_size)
        )
    
    async def close_connection(conn: httpx.AsyncClient):
        await conn.aclose()
    
    async def validate_connection(conn: httpx.AsyncClient) -> bool:
        return not conn.is_closed
    
    pool = ConnectionPool(
        create_connection=create_connection,
        close_connection=close_connection,
        validate_connection=validate_connection,
        max_size=max_size,
        name="http"
    )
    
    await pool.initialize()
    return pool