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
