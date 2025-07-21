"""
Qdrant vector database service for the Narrative Factory memory pipeline.
Implements two-tiered retrieval: Spotlight and Ambient Echo queries with
advanced connection pooling, resource management, and production-ready patterns.
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchAny,
        MatchValue,
        PayloadSchemaType,
        PointStruct,
        VectorParams,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    # Provide fallback types for testing
    AsyncQdrantClient = None
    Distance = None
    FieldCondition = None
    Filter = None
    MatchAny = None
    MatchValue = None
    PayloadSchemaType = None
    PointStruct = None
    VectorParams = None

# Lazy import sentence_transformers to avoid bus error during testing
SENTENCE_TRANSFORMERS_AVAILABLE = None

def _check_sentence_transformers():
    """Lazy check for sentence_transformers availability."""
    global SENTENCE_TRANSFORMERS_AVAILABLE
    if SENTENCE_TRANSFORMERS_AVAILABLE is None:
        try:
            import importlib.util
            spec = importlib.util.find_spec("sentence_transformers")
            SENTENCE_TRANSFORMERS_AVAILABLE = spec is not None
        except ImportError:
            SENTENCE_TRANSFORMERS_AVAILABLE = False
    return SENTENCE_TRANSFORMERS_AVAILABLE

# Import ContextRetrievalResult - handle import issues for testing
try:
    from src.models import ContextRetrievalResult
except ImportError:
    # Fallback definition for testing
    from typing import Any

    from pydantic import BaseModel

    class ContextRetrievalResult(BaseModel):
        spotlight_context: list[dict[str, Any]]
        ambient_echo: list[dict[str, Any]]

# Enhanced imports for production features
from src.config import config
from src.exceptions import (
    DatabaseError,
    handle_errors,
    with_retry,
)
from src.health import register_health_check
from src.logger import get_logger, log_execution_time


logger = get_logger(__name__)


@dataclass
class ConnectionStats:
    """Statistics for connection monitoring."""
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    last_error_time: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def reset(self) -> None:
        """Reset statistics."""
        self.total_connections = 0
        self.active_connections = 0
        self.failed_connections = 0
        self.total_requests = 0
        self.total_errors = 0
        self.last_error_time = None
        self.created_at = time.time()


class QdrantConnectionPool:
    """Connection pool manager for Qdrant clients."""

    def __init__(
        self,
        url: str,
        api_key: Optional[str] = None,
        max_connections: int = 10,
        min_connections: int = 2,
        connection_timeout: int = 30,
        max_retries: int = 3
    ):
        """Initialize connection pool."""
        self.url = url
        self.api_key = api_key
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries

        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections: set = set()
        self._stats = ConnectionStats()
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info(f"Initializing Qdrant connection pool with {self.min_connections} connections")

            # Create minimum number of connections
            for _ in range(self.min_connections):
                try:
                    client = await self._create_client()
                    await self._pool.put(client)
                    self._stats.total_connections += 1
                    logger.debug("Created initial connection")
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
                    self._stats.failed_connections += 1
                    raise DatabaseError(f"Failed to initialize connection pool: {e}") from e

            self._initialized = True
            logger.info("Qdrant connection pool initialized successfully")

    async def _create_client(self) -> AsyncQdrantClient:
        """Create a new Qdrant client."""
        try:
            client = AsyncQdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=self.connection_timeout,
                prefer_grpc=False
            )

            # Test connection
            await client.get_collections()
            return client

        except Exception as e:
            logger.error(f"Failed to create Qdrant client: {e}")
            raise DatabaseError(f"Failed to create Qdrant client: {e}") from e

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[AsyncQdrantClient, None]:
        """Get a connection from the pool."""
        if not self._initialized:
            await self.initialize()

        client = None
        try:
            # Try to get existing connection
            try:
                client = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.connection_timeout
                )
                self._active_connections.add(client)
                self._stats.active_connections += 1
                logger.debug("Retrieved connection from pool")
            except asyncio.TimeoutError:
                # Pool is empty, create new connection if under limit
                if len(self._active_connections) < self.max_connections:
                    client = await self._create_client()
                    self._active_connections.add(client)
                    self._stats.total_connections += 1
                    self._stats.active_connections += 1
                    logger.debug("Created new connection")
                else:
                    raise DatabaseError("Connection pool exhausted") from None

            yield client

        except Exception as e:
            self._stats.total_errors += 1
            self._stats.last_error_time = time.time()
            logger.error(f"Connection error: {e}")
            raise

        finally:
            if client:
                self._active_connections.discard(client)
                self._stats.active_connections -= 1

                # Return connection to pool
                try:
                    await self._pool.put(client)
                    logger.debug("Returned connection to pool")
                except asyncio.QueueFull:
                    # Pool is full, close connection
                    await client.close()
                    logger.debug("Closed excess connection")

    async def close(self) -> None:
        """Close all connections in the pool."""
        logger.info("Closing Qdrant connection pool")

        # Close all connections in pool
        while not self._pool.empty():
            try:
                client = await self._pool.get()
                await client.close()
            except Exception as e:
                logger.error(f"Error closing pooled connection: {e}")

        # Close active connections
        for client in self._active_connections:
            try:
                await client.close()
            except Exception as e:
                logger.error(f"Error closing active connection: {e}")

        self._active_connections.clear()
        self._initialized = False
        logger.info("Qdrant connection pool closed")

    def get_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        return {
            "total_connections": self._stats.total_connections,
            "active_connections": self._stats.active_connections,
            "failed_connections": self._stats.failed_connections,
            "total_requests": self._stats.total_requests,
            "total_errors": self._stats.total_errors,
            "last_error_time": self._stats.last_error_time,
            "pool_size": self._pool.qsize(),
            "max_connections": self.max_connections,
            "uptime_seconds": time.time() - self._stats.created_at
        }


class QdrantService:
    """
    Production-ready service for managing Qdrant vector database operations.
    Implements two-tiered context retrieval for narrative generation with
    connection pooling, retry logic, and comprehensive error handling.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Qdrant service with production-ready configuration.

        Args:
            url: Qdrant endpoint URL (defaults to config)
            api_key: Qdrant API key (defaults to config)
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

        if not _check_sentence_transformers():
            raise ImportError("sentence-transformers is required. Install with: pip install sentence-transformers")

        # Get configuration from config system
        self.url = url or config.qdrant.url
        self.api_key = api_key or config.qdrant.api_key

        # Validate configuration
        if not self.url:
            raise DatabaseError("Qdrant URL is required")

        # Initialize connection pool with config-driven settings
        self.connection_pool = QdrantConnectionPool(
            url=self.url,
            api_key=self.api_key,
            max_connections=config.app.max_concurrent_tasks,
            min_connections=2,
            connection_timeout=config.qdrant.timeout,
            max_retries=config.qdrant.retries
        )

        # Initialize embedding configuration from config
        self._embedding_service = None
        self.embedding_dimension = config.qdrant.vector_size
        self.embedding_provider = config.models.embedding_provider

        # Register health check
        register_health_check("qdrant_service", self._health_check)

        logger.info(f"QdrantService initialized with URL: {self.url}")

    async def _health_check(self, include_detailed: bool = False) -> dict[str, Any]:
        """Health check for the Qdrant service."""
        try:
            async with self.connection_pool.get_connection() as client:
                collections = await client.get_collections()

                pool_stats = self.connection_pool.get_stats()

                details = {}
                if include_detailed:
                    details = {
                        "collections_count": len(collections.collections),
                        "pool_stats": pool_stats,
                        "embedding_provider": self.embedding_provider,
                        "embedding_dimension": self.embedding_dimension
                    }

                return {
                    "status": "healthy",
                    "message": "Qdrant service operational",
                    "details": details
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Qdrant service error: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _get_embedding_service(self):
        """Lazy load the embedding service to avoid startup issues."""
        if self._embedding_service is None:
            # Import here to avoid circular imports
            from .embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService(provider=self.embedding_provider)
        return self._embedding_service

    async def _get_embedding_model(self):
        """Lazy load the embedding model to avoid startup issues. (Deprecated - use _get_embedding_service)"""
        if self._embedding_model is None:
            if not _check_sentence_transformers():
                raise RuntimeError("sentence-transformers not available")
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model

    @with_retry(max_attempts=3, base_delay=1.0)
    @log_execution_time(__name__)
    async def create_collections(self) -> None:
        """Create the required collections for the narrative factory."""
        collections = [
            config.qdrant.world_bible_collection,
            config.qdrant.story_so_far_collection
        ]

        for collection_name in collections:
            try:
                async with self.connection_pool.get_connection() as client:
                    exists = await client.collection_exists(collection_name)
                    if not exists:
                        logger.info(f"Creating collection: {collection_name}")
                        await client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=self.embedding_dimension,
                                distance=Distance.COSINE
                            )
                        )
                        logger.info(f"Collection {collection_name} created successfully")
                    else:
                        logger.info(f"Collection {collection_name} already exists")

            except Exception as e:
                logger.error(f"Failed to create collection {collection_name}: {e}")
                raise DatabaseError(f"Failed to create collection {collection_name}: {e}") from e

        # Create payload indexes for filtering
        await self._create_payload_indexes()

    async def _create_payload_indexes(self) -> None:
        """Create payload indexes for efficient filtering."""
        collections = [
            config.qdrant.world_bible_collection,
            config.qdrant.story_so_far_collection
        ]

        # Define required indexes for narrative factory filtering
        required_indexes = {
            "present_characters": PayloadSchemaType.KEYWORD,
            "doc_type": PayloadSchemaType.KEYWORD,
            "thread_id": PayloadSchemaType.KEYWORD,
            "tension_status": PayloadSchemaType.KEYWORD,
            "character_name": PayloadSchemaType.KEYWORD,
            "status": PayloadSchemaType.KEYWORD
        }

        for collection_name in collections:
            for field_name, schema_type in required_indexes.items():
                try:
                    async with self.connection_pool.get_connection() as client:
                        await client.create_payload_index(
                            collection_name=collection_name,
                            field_name=field_name,
                            field_schema=schema_type
                        )
                        logger.info(f"Created payload index: {collection_name}.{field_name}")
                except Exception as e:
                    # Index might already exist, check if it's a "already exists" error
                    if "already exists" in str(e).lower() or "index exists" in str(e).lower():
                        logger.debug(f"Payload index {collection_name}.{field_name} already exists")
                    else:
                        logger.warning(f"Failed to create payload index {collection_name}.{field_name}: {e}")
                        # Don't raise - indexes are nice to have but not critical for basic operation

    async def _embed_text(self, text: str) -> list[float]:
        """
        Generate embeddings for text using the configured embedding service.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (dimension depends on provider)
        """
        try:
            service = await self._get_embedding_service()
            embedding = await service.generate_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            raise

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            service = await self._get_embedding_service()
            embeddings = await service.generate_embeddings(texts)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate embeddings for {len(texts)} texts: {e}")
            raise

    async def ingest_document(
        self,
        doc_id: str,
        content: str,
        collection_name: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Ingest a single document into Qdrant.

        Args:
            doc_id: Unique document identifier
            content: Document content to embed
            collection_name: Target collection
            metadata: Additional document metadata
        """
        try:
            # Generate embedding
            embedding = await self._embed_text(content)

            # Prepare payload
            payload = {"content": content}
            if metadata:
                payload.update(metadata)

            # Create point
            point = PointStruct(
                id=doc_id,
                vector=embedding,
                payload=payload
            )

            # Upsert to collection
            async with self.connection_pool.get_connection() as client:
                await client.upsert(
                    collection_name=collection_name,
                    points=[point]
                )

            logger.info(f"Document {doc_id} ingested to {collection_name}")

        except Exception as e:
            logger.error(f"Failed to ingest document {doc_id}: {e}")
            raise

    async def ingest_documents(
        self,
        documents: list[dict[str, Any]],
        collection_name: str
    ) -> None:
        """
        Ingest multiple documents into Qdrant efficiently.

        Args:
            documents: List of document dictionaries with 'id', 'content', and optional metadata
            collection_name: Target collection
        """
        try:
            # Extract content for batch embedding
            contents = [doc["content"] for doc in documents]
            embeddings = await self._embed_texts(contents)

            # Create points
            points = []
            for doc, embedding in zip(documents, embeddings):
                payload = {key: value for key, value in doc.items() if key != "id"}

                point = PointStruct(
                    id=doc["id"],
                    vector=embedding,
                    payload=payload
                )
                points.append(point)

            # Batch upsert
            async with self.connection_pool.get_connection() as client:
                await client.upsert(
                    collection_name=collection_name,
                    points=points
                )

            logger.info(f"Ingested {len(documents)} documents to {collection_name}")

        except Exception as e:
            logger.error(f"Failed to ingest {len(documents)} documents: {e}")
            raise

    @with_retry(max_attempts=3, base_delay=1.0)
    @log_execution_time(__name__)
    @handle_errors(reraise=False, return_default=ContextRetrievalResult(spotlight_context=[], ambient_echo=[]))
    async def fetch_context_for_director(
        self,
        chapter_seed: str,
        active_characters: list[str],
        max_results_per_tier: int = 5
    ) -> ContextRetrievalResult:
        """
        Two-tiered context retrieval for the Director agent with production-ready patterns.

        Tier 1 - Spotlight Query: High-relevance context filtered by present characters
        Tier 2 - Ambient Echo: Background tension and unresolved conflicts

        Args:
            chapter_seed: The narrative seed to search against
            active_characters: List of character IDs currently active
            max_results_per_tier: Maximum results per tier (default: 5)

        Returns:
            ContextRetrievalResult with spotlight_context and ambient_echo
        """
        try:
            # Generate query embedding
            query_vector = await self._embed_text(chapter_seed)

            async with self.connection_pool.get_connection() as client:
                # Tier 1: Spotlight Query - Character-specific context
                spotlight_filter = Filter(
                    must=[
                        FieldCondition(
                            key="present_characters",
                            match=MatchAny(any=active_characters)
                        )
                    ]
                )

                spotlight_results = await client.search(
                    collection_name=config.qdrant.world_bible_collection,
                    query_vector=query_vector,
                    query_filter=spotlight_filter,
                    limit=max_results_per_tier
                )

                # Tier 2: Ambient Echo Query - Unresolved tensions
                ambient_filter = Filter(
                    must=[
                        FieldCondition(
                            key="doc_type",
                            match=MatchValue(value="tension_report")
                        ),
                        FieldCondition(
                            key="status",
                            match=MatchAny(any=["unresolved", "escalating"])
                        )
                    ]
                )

                ambient_results = await client.search(
                    collection_name=config.qdrant.story_so_far_collection,
                    query_vector=query_vector,
                    query_filter=ambient_filter,
                    limit=max_results_per_tier
                )

            # Format results
            spotlight_context = [
                {
                    **hit.payload,
                    "score": hit.score,
                    "id": hit.id
                }
                for hit in spotlight_results
            ]

            ambient_echo = [
                {
                    **hit.payload,
                    "score": hit.score,
                    "id": hit.id
                }
                for hit in ambient_results
            ]

            logger.info(
                f"Retrieved {len(spotlight_context)} spotlight items and "
                f"{len(ambient_echo)} ambient echo items for seed: {chapter_seed[:50]}..."
            )

            return ContextRetrievalResult(
                spotlight_context=spotlight_context,
                ambient_echo=ambient_echo
            )

        except Exception as e:
            logger.error(f"Failed to fetch context for director: {e}")
            raise DatabaseError(f"Failed to fetch context for director: {e}") from e

    async def search_by_content(
        self,
        query_text: str,
        collection_name: str,
        filters: Optional[Filter] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Generic content search with optional filtering.

        Args:
            query_text: Text to search for
            collection_name: Collection to search
            filters: Optional Qdrant filters
            limit: Maximum results to return

        Returns:
            List of search results with metadata
        """
        try:
            query_vector = await self._embed_text(query_text)

            async with self.connection_pool.get_connection() as client:
                results = await client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=filters,
                    limit=limit
                )

            return [
                {
                    **hit.payload,
                    "score": hit.score,
                    "id": hit.id
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Search failed for query '{query_text}': {e}")
            return []

    async def get_collection_info(self, collection_name: str) -> dict[str, Any]:
        """
        Get information about a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection information dictionary
        """
        try:
            async with self.connection_pool.get_connection() as client:
                info = await client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
                "config": {
                    "vector_size": info.config.params.vectors.size,
                    "distance": info.config.params.vectors.distance
                }
            }
        except Exception as e:
            logger.error(f"Failed to get collection info for {collection_name}: {e}")
            return {}

    async def list_collections(self) -> list[str]:
        """
        List all available collections.

        Returns:
            List of collection names
        """
        try:
            async with self.connection_pool.get_connection() as client:
                collections = await client.get_collections()
            return [collection.name for collection in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.connection_pool.get_connection() as client:
                await client.delete_collection(collection_name)
            logger.info(f"Collection {collection_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False

    async def store_embeddings_bulk(
        self,
        embeddings: list[list[float]],
        collection: str,
        metadata: dict[str, Any],
        create_collection_if_missing: bool = True,
        check_duplicates: bool = True
    ) -> dict[str, Any]:
        """
        Store multiple embeddings with metadata in Qdrant using bulk operations.
        
        This method bridges the API gap between MemoryService expectations
        and QdrantService implementation patterns with duplicate prevention.

        Args:
            embeddings: List of embedding vectors to store
            collection: Collection name (will be used as collection_name)
            metadata: Shared metadata to apply to all points
            create_collection_if_missing: Whether to create collection if it doesn't exist
            check_duplicates: Whether to check for and skip duplicate content_hash

        Returns:
            Dictionary with storage result information
        """
        try:
            collection_name = collection  # Alias for clarity
            
            # Handle collection creation if needed
            if create_collection_if_missing:
                async with self.connection_pool.get_connection() as client:
                    exists = await client.collection_exists(collection_name)
                    if not exists:
                        # Determine vector size from first embedding
                        vector_size = len(embeddings[0]) if embeddings else self.embedding_dimension
                        
                        logger.info(f"Creating collection {collection_name} with vector size {vector_size}")
                        await client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=vector_size,
                                distance=Distance.COSINE
                            )
                        )
                        logger.info(f"Collection {collection_name} created successfully")

            if not embeddings:
                logger.warning("No embeddings provided for bulk storage")
                return {
                    "status": "success",
                    "points_stored": 0,
                    "collection": collection_name,
                    "message": "No embeddings to store"
                }

            # Check for duplicates if requested
            content_hash = metadata.get('content_hash')
            duplicate_check_result = None
            
            if check_duplicates and content_hash:
                try:
                    async with self.connection_pool.get_connection() as client:
                        # Check if this content_hash already exists
                        existing_points = await client.scroll(
                            collection_name=collection_name,
                            scroll_filter=Filter(
                                must=[
                                    FieldCondition(
                                        key="content_hash",
                                        match=MatchValue(value=content_hash)
                                    )
                                ]
                            ),
                            limit=1,
                            with_payload=True
                        )
                        
                        if existing_points[0]:  # Points found
                            existing_point = existing_points[0][0]
                            duplicate_check_result = {
                                "duplicate_found": True,
                                "existing_point_id": str(existing_point.id),
                                "existing_material_id": existing_point.payload.get('material_id', 'unknown'),
                                "existing_created_at": existing_point.payload.get('created_at', 'unknown')
                            }
                            
                            logger.info(f"Duplicate content detected: {content_hash} already exists in {collection_name}")
                            return {
                                "status": "duplicate_skipped",
                                "points_stored": 0,
                                "collection": collection_name,
                                "duplicate_info": duplicate_check_result,
                                "message": f"Content with hash {content_hash} already exists"
                            }
                            
                except Exception as e:
                    logger.warning(f"Duplicate check failed, proceeding with storage: {e}")
                    # Continue with storage if duplicate check fails

            # Create PointStruct objects following Context7 patterns
            points = []
            import uuid
            
            for idx, embedding in enumerate(embeddings):
                # Generate unique UUID for point ID (Qdrant requirement)
                point_id = str(uuid.uuid4())
                
                # Create point-specific metadata
                point_metadata = {
                    **metadata,  # Include all shared metadata
                    "chunk_index": idx,
                    "total_chunks": len(embeddings),
                    "point_id": point_id
                }
                
                # Create PointStruct following Context7 documentation patterns
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=point_metadata
                )
                points.append(point)

            # Perform bulk upsert using existing connection pool
            async with self.connection_pool.get_connection() as client:
                operation_info = await client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True  # Wait for operation completion for reliability
                )

            logger.info(f"Successfully stored {len(points)} embeddings in collection {collection_name}")

            # Return structured result matching MemoryService expectations
            return {
                "status": "success", 
                "points_stored": len(points),
                "collection": collection_name,
                "operation_info": {
                    "operation_id": getattr(operation_info, 'operation_id', None),
                    "status": getattr(operation_info, 'status', 'completed')
                },
                "metadata": {
                    "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
                    "total_embeddings": len(embeddings),
                    "base_material_id": metadata.get('material_id', 'unknown')
                }
            }

        except Exception as e:
            logger.error(f"Failed to store embeddings bulk in collection {collection}: {e}")
            raise DatabaseError(f"Bulk embedding storage failed: {e}") from e

    async def delete_points_by_filter(
        self,
        collection_name: str,
        filter_condition: Filter
    ) -> dict[str, Any]:
        """
        Delete points from a collection based on filter conditions.
        
        Args:
            collection_name: Name of the collection
            filter_condition: Qdrant Filter object specifying which points to delete
            
        Returns:
            Dictionary with deletion results
        """
        try:
            async with self.connection_pool.get_connection() as client:
                result = await client.delete(
                    collection_name=collection_name,
                    points_selector=filter_condition,
                    wait=True
                )
                
            logger.info(f"Deleted points from collection {collection_name} using filter")
            return {
                "status": "success",
                "operation_id": getattr(result, 'operation_id', None),
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(f"Failed to delete points from {collection_name}: {e}")
            raise DatabaseError(f"Point deletion failed: {e}") from e

    async def remove_duplicates_by_content_hash(
        self,
        collection_name: str,
        dry_run: bool = True
    ) -> dict[str, Any]:
        """
        Remove duplicate points based on content_hash, keeping the most recent.
        
        Args:
            collection_name: Name of the collection to deduplicate
            dry_run: If True, only report what would be deleted without actually deleting
            
        Returns:
            Dictionary with deduplication results
        """
        try:
            # Scroll through all points to find duplicates
            async with self.connection_pool.get_connection() as client:
                # Get all points with their payloads
                scroll_result = await client.scroll(
                    collection_name=collection_name,
                    limit=10000,  # Adjust based on collection size
                    with_payload=True
                )
                
                points = scroll_result[0]  # First element contains the points
                
            # Group points by content_hash
            hash_groups = {}
            for point in points:
                content_hash = point.payload.get('content_hash')
                if content_hash:
                    if content_hash not in hash_groups:
                        hash_groups[content_hash] = []
                    hash_groups[content_hash].append(point)
            
            # Find duplicates (groups with more than one point)
            duplicates_to_remove = []
            kept_points = []
            
            for content_hash, point_group in hash_groups.items():
                if len(point_group) > 1:
                    # Sort by created_at timestamp, keep the most recent
                    sorted_points = sorted(
                        point_group,
                        key=lambda p: p.payload.get('created_at', ''),
                        reverse=True
                    )
                    
                    # Keep the first (most recent), mark others for deletion
                    kept_points.append(sorted_points[0])
                    duplicates_to_remove.extend(sorted_points[1:])
                else:
                    kept_points.extend(point_group)
            
            result = {
                "status": "success",
                "collection": collection_name,
                "total_points": len(points),
                "unique_content_hashes": len(hash_groups),
                "duplicates_found": len(duplicates_to_remove),
                "points_to_keep": len(kept_points),
                "dry_run": dry_run,
                "duplicate_details": [
                    {
                        "id": str(point.id),
                        "material_id": point.payload.get('material_id', 'unknown'),
                        "created_at": point.payload.get('created_at', 'unknown'),
                        "content_hash": point.payload.get('content_hash', 'unknown')
                    }
                    for point in duplicates_to_remove
                ]
            }
            
            if not dry_run and duplicates_to_remove:
                # Actually delete the duplicate points
                point_ids_to_delete = [str(point.id) for point in duplicates_to_remove]
                
                async with self.connection_pool.get_connection() as client:
                    delete_result = await client.delete(
                        collection_name=collection_name,
                        points_selector=point_ids_to_delete,
                        wait=True
                    )
                
                result["deletion_operation_id"] = getattr(delete_result, 'operation_id', None)
                logger.info(f"Removed {len(point_ids_to_delete)} duplicate points from {collection_name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to remove duplicates from {collection_name}: {e}")
            raise DatabaseError(f"Deduplication failed: {e}") from e

    async def cleanup_test_collections(self, confirm: bool = False) -> dict[str, Any]:
        """
        Clean up test collections created during development/testing.
        
        Args:
            confirm: Must be True to actually delete collections
            
        Returns:
            Dictionary with cleanup results
        """
        test_collection_patterns = [
            'test_',
            'materials_test',
            'test_uuid_fix',
            'test_materials_character_sheet'
        ]
        
        try:
            collections = await self.list_collections()
            test_collections = [
                col for col in collections 
                if any(pattern in col for pattern in test_collection_patterns)
            ]
            
            result = {
                "status": "success",
                "test_collections_found": test_collections,
                "collections_to_delete": len(test_collections),
                "confirmed": confirm
            }
            
            if confirm and test_collections:
                deleted_collections = []
                failed_deletions = []
                
                for collection in test_collections:
                    try:
                        success = await self.delete_collection(collection)
                        if success:
                            deleted_collections.append(collection)
                        else:
                            failed_deletions.append(collection)
                    except Exception as e:
                        failed_deletions.append(f"{collection}: {e}")
                
                result.update({
                    "deleted_collections": deleted_collections,
                    "failed_deletions": failed_deletions,
                    "successfully_deleted": len(deleted_collections)
                })
                
            return result
            
        except Exception as e:
            logger.error(f"Failed to cleanup test collections: {e}")
            raise DatabaseError(f"Test cleanup failed: {e}") from e

    async def delete_document(self, doc_id: str, collection_name: str) -> bool:
        """
        Delete document from Qdrant collection.
        
        Args:
            doc_id: Document ID to delete
            collection_name: Target collection
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            async with self.connection_pool.get_connection() as client:
                from qdrant_client import models
                
                await client.delete(
                    collection_name=collection_name,
                    points_selector=models.PointIdsList(points=[doc_id])
                )
            
            logger.info(f"Document {doc_id} deleted from {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    async def update_document(self, doc_id: str, new_content: str, collection_name: str, metadata: Optional[dict[str, Any]] = None) -> bool:
        """
        Update existing document in Qdrant collection.
        
        Args:
            doc_id: Document ID to update
            new_content: New content for the document
            collection_name: Target collection
            metadata: Optional metadata to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First delete old version
            await self.delete_document(doc_id, collection_name)
            
            # Then ingest new version (use existing method)
            await self.ingest_document(doc_id, new_content, collection_name, metadata)
            
            logger.info(f"Document {doc_id} updated in {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update document {doc_id}: {e}")
            return False

    async def search_with_filters(self, filters: dict[str, Any], collection_name: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Search documents with metadata filters.
        
        Args:
            filters: Metadata filters (e.g., {"story_id": "my_serial", "doc_type": "character_sheet"})
            collection_name: Target collection
            limit: Maximum results
            
        Returns:
            list: Matching documents with metadata
        """
        try:
            async with self.connection_pool.get_connection() as client:
                from qdrant_client import models
                
                # Build filter conditions
                conditions = []
                for key, value in filters.items():
                    conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                    )
                
                filter_query = models.Filter(must=conditions) if conditions else None
                
                # Get collection info to determine correct vector dimension
                collection_info = await client.get_collection(collection_name)
                actual_vector_size = collection_info.config.params.vectors.size
                
                # Search with dummy vector (we want metadata filtering)
                dummy_vector = [0.0] * actual_vector_size
                
                results = await client.search(
                    collection_name=collection_name,
                    query_vector=dummy_vector,
                    query_filter=filter_query,
                    limit=limit,
                    with_payload=True
                )
                
                # Extract documents with metadata
                documents = []
                for result in results:
                    documents.append({
                        "doc_id": str(result.id),
                        "content": result.payload.get("content", ""),
                        "doc_type": result.payload.get("doc_type", "unknown"),
                        "story_id": result.payload.get("story_id", None),
                        "metadata": result.payload
                    })
                
                logger.info(f"Found {len(documents)} documents with filters {filters}")
                return documents
                
        except Exception as e:
            logger.error(f"Search with filters failed: {e}")
            return []

    async def close(self) -> None:
        """Close the Qdrant connection pool and embedding service."""
        try:
            await self.connection_pool.close()
            if self._embedding_service is not None:
                await self._embedding_service.close()
            logger.info("Qdrant connection pool and embedding service closed")
        except Exception as e:
            logger.error(f"Error closing Qdrant service: {e}")
            raise DatabaseError(f"Error closing Qdrant service: {e}") from e

    def get_service_stats(self) -> dict[str, Any]:
        """Get comprehensive service statistics."""
        return {
            "connection_pool": self.connection_pool.get_stats(),
            "embedding_provider": self.embedding_provider,
            "embedding_dimension": self.embedding_dimension,
            "service_url": self.url,
            "collections": [
                config.qdrant.world_bible_collection,
                config.qdrant.story_so_far_collection
            ]
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connection_pool.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def main():
    """Example usage of QdrantService."""
    service = QdrantService()

    try:
        # Create collections
        await service.create_collections()

        # Example document ingestion
        sample_docs = [
            {
                "id": "char_001",
                "content": "Selene is a skilled tactician with a mysterious past.",
                "doc_type": "character_sheet",
                "present_characters": ["selene"],
                "character_name": "Selene"
            },
            {
                "id": "tension_001",
                "content": "The unresolved conflict between the northern clans creates ongoing political tension.",
                "doc_type": "tension_report",
                "status": "unresolved",
                "severity": "high"
            }
        ]

        await service.ingest_documents(sample_docs, "world_bible")

        # Example context retrieval
        context = await service.fetch_context_for_director(
            chapter_seed="The meeting begins in the council chamber",
            active_characters=["selene", "marcus"]
        )

        print(f"Spotlight context: {len(context.spotlight_context)} items")
        print(f"Ambient echo: {len(context.ambient_echo)} items")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
