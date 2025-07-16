"""
Qdrant vector database service for the Narrative Factory memory pipeline.
Implements two-tiered retrieval: Spotlight and Ambient Echo queries.
"""

import asyncio
import logging
import os
from typing import Any, Optional

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchAny,
        MatchValue,
        PointStruct,
        VectorParams,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

# Import ContextRetrievalResult - handle import issues for testing
try:
    from ..agents.models import ContextRetrievalResult
except ImportError:
    try:
        from agents.models import ContextRetrievalResult
    except ImportError:
        # Fallback definition for testing
        from pydantic import BaseModel
        from typing import List, Dict, Any
        
        class ContextRetrievalResult(BaseModel):
            spotlight_context: List[Dict[str, Any]]
            ambient_echo: List[Dict[str, Any]]

logger = logging.getLogger(__name__)


class QdrantService:
    """
    Service for managing Qdrant vector database operations.
    Implements two-tiered context retrieval for narrative generation.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the Qdrant service for cloud deployment.

        Args:
            url: Qdrant Cloud endpoint URL (defaults to QDRANT_URL env var)
            api_key: Qdrant Cloud API key (required for cloud instances)
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers is required. Install with: pip install sentence-transformers")

        # Get cloud configuration
        self.url = url or os.getenv("QDRANT_URL")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")

        # Validate cloud configuration
        if not self.url:
            raise ValueError("QDRANT_URL environment variable is required for cloud deployment")
        
        if not self.api_key:
            raise ValueError("QDRANT_API_KEY environment variable is required for cloud deployment")

        # Initialize cloud client
        self.client = AsyncQdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60.0,  # Longer timeout for cloud
            prefer_grpc=False,  # Use REST for cloud compatibility
        )

        # Initialize embedding configuration based on provider
        self._embedding_model: Optional[SentenceTransformer] = None
        
        # Set embedding dimension based on provider
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "local")
        if embedding_provider == "jina":
            self.embedding_dimension = 2048  # jina-embeddings-v4 full dimension
        else:
            self.embedding_dimension = 384   # sentence-transformers default

    async def _get_embedding_model(self) -> SentenceTransformer:
        """Lazy load the embedding model to avoid startup issues."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model

    async def create_collections(self) -> None:
        """Create the required collections for the narrative factory."""
        collections = ["world_bible", "story_so_far"]

        for collection_name in collections:
            try:
                exists = await self.client.collection_exists(collection_name)
                if not exists:
                    logger.info(f"Creating collection: {collection_name}")
                    await self.client.create_collection(
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
                raise

    async def _embed_text(self, text: str) -> list[float]:
        """
        Generate embeddings for text using sentence-transformers.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (384 dimensions)
        """
        try:
            model = await self._get_embedding_model()
            embedding = model.encode(text)
            return embedding.tolist()
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
            model = await self._get_embedding_model()
            embeddings = model.encode(texts)
            return embeddings.tolist()
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
            await self.client.upsert(
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
            await self.client.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info(f"Ingested {len(documents)} documents to {collection_name}")

        except Exception as e:
            logger.error(f"Failed to ingest {len(documents)} documents: {e}")
            raise

    async def fetch_context_for_director(
        self,
        chapter_seed: str,
        active_characters: list[str],
        max_results_per_tier: int = 5
    ) -> ContextRetrievalResult:
        """
        Two-tiered context retrieval for the Director agent.

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

            # Tier 1: Spotlight Query - Character-specific context
            spotlight_filter = Filter(
                must=[
                    FieldCondition(
                        key="present_characters",
                        match=MatchAny(any=active_characters)
                    )
                ]
            )

            spotlight_results = await self.client.search(
                collection_name="world_bible",
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

            ambient_results = await self.client.search(
                collection_name="story_so_far",
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
            # Return empty context on failure rather than crashing
            return ContextRetrievalResult(
                spotlight_context=[],
                ambient_echo=[]
            )

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

            results = await self.client.search(
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
            info = await self.client.get_collection(collection_name)
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

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_name: Name of the collection to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.client.delete_collection(collection_name)
            logger.info(f"Collection {collection_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {e}")
            return False

    async def close(self) -> None:
        """Close the Qdrant client connection."""
        try:
            await self.client.close()
            logger.info("Qdrant client connection closed")
        except Exception as e:
            logger.error(f"Error closing Qdrant client: {e}")


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
