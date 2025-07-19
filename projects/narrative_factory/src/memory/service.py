"""
Memory service abstraction for the Narrative Factory.

Provides a high-level interface for memory operations with production-ready patterns.
Extended with LibrarianAgent-specific capabilities for material analysis and storage.
"""

from datetime import datetime
from typing import Any, Optional

from src.logger import get_logger
from src.memory.qdrant import QdrantService


logger = get_logger(__name__)


class MemoryService:
    """High-level memory service interface."""

    def __init__(self, qdrant_service: Optional[QdrantService] = None):
        """Initialize memory service."""
        self.qdrant_service = qdrant_service or QdrantService()
        logger.info("Memory service initialized")

    async def initialize(self) -> None:
        """Initialize the memory service."""
        await self.qdrant_service.connection_pool.initialize()
        await self.qdrant_service.create_collections()
        logger.info("Memory service initialization complete")

    async def close(self) -> None:
        """Close the memory service."""
        await self.qdrant_service.close()
        logger.info("Memory service closed")

    async def __aenter__(self) -> 'MemoryService':
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # === LIBRARIAN AGENT EXTENSIONS ===

    async def store_material_embeddings(
        self,
        content: str,
        embeddings: list[list[float]],
        category: str,
        material_id: str,
        metadata: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Store material embeddings with enhanced metadata and indexing.

        Args:
            content: Original material content
            embeddings: List of embedding vectors
            category: Material category for collection organization
            material_id: Unique material identifier
            metadata: Additional metadata for storage

        Returns:
            Storage result with metadata
        """
        try:
            # Dynamic collection selection based on category
            collection_name = f"materials_{category.lower()}"

            # Enhanced metadata for better retrieval
            enhanced_metadata = {
                "category": category,
                "material_id": material_id,
                "content_preview": content[:200],
                "content_length": len(content),
                "chunks_count": len(embeddings),
                "processing_timestamp": datetime.utcnow().isoformat(),
                "embedding_model": "text-embedding-3-small",
                **(metadata or {})
            }

            # Store embeddings using existing Qdrant service
            storage_result = await self.qdrant_service.store_embeddings_bulk(
                embeddings=embeddings,
                collection=collection_name,
                metadata=enhanced_metadata,
                create_collection_if_missing=True
            )

            logger.debug(f"Stored {len(embeddings)} embeddings for material {material_id} in {collection_name}")

            return {
                "status": "success",
                "collection": collection_name,
                "embeddings_stored": len(embeddings),
                "material_id": material_id,
                "storage_result": storage_result
            }

        except Exception as e:
            logger.error(f"Failed to store material embeddings for {material_id}: {e}")
            raise Exception(f"Material embedding storage failed: {e}") from e

    async def retrieve_related_materials(
        self,
        material_id: str,
        relationship_types: Optional[list[str]] = None,
        limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Retrieve materials related to given material.

        Args:
            material_id: Material to find relationships for
            relationship_types: Types of relationships to search for
            limit: Maximum number of related materials to return

        Returns:
            List of related materials with metadata
        """
        try:
            # Default relationship types
            if relationship_types is None:
                relationship_types = ["references", "similar", "expands"]

            # Query across all material collections
            related_materials = []

            # Get all material collections
            collections = await self.qdrant_service.list_collections()
            material_collections = [col for col in collections if col.startswith("materials_")]

            for collection in material_collections:
                try:
                    # Query for related materials in this collection
                    results = await self.qdrant_service.query_similar_materials(
                        collection=collection,
                        material_id=material_id,
                        relationship_types=relationship_types,
                        limit=limit
                    )

                    related_materials.extend(results)

                except Exception as e:
                    logger.warning(f"Failed to query collection {collection}: {e}")
                    continue

            # Sort by relevance score and limit results
            related_materials.sort(key=lambda x: x.get("score", 0), reverse=True)

            logger.debug(f"Found {len(related_materials)} related materials for {material_id}")

            return related_materials[:limit]

        except Exception as e:
            logger.error(f"Failed to retrieve related materials for {material_id}: {e}")
            return []

    async def fetch_material_analysis_context(
        self,
        material_ids: list[str],
        analysis_depth: str = "standard"
    ) -> dict[str, Any]:
        """
        Fetch context for material analysis operations.

        Args:
            material_ids: List of material IDs to fetch context for
            analysis_depth: Depth of context to retrieve

        Returns:
            Context dictionary with relevant information
        """
        try:
            context = {
                "material_count": len(material_ids),
                "analysis_depth": analysis_depth,
                "related_materials": {},
                "category_distribution": {},
                "total_content_length": 0
            }

            # Fetch related materials for each ID
            for material_id in material_ids:
                related = await self.retrieve_related_materials(
                    material_id,
                    limit=5 if analysis_depth == "quick" else 10
                )
                context["related_materials"][material_id] = related

            # Calculate category distribution
            all_related = [
                item for related_list in context["related_materials"].values()
                for item in related_list
            ]

            categories = [item.get("category", "unknown") for item in all_related]
            for category in categories:
                context["category_distribution"][category] = context["category_distribution"].get(category, 0) + 1

            logger.debug(f"Fetched analysis context for {len(material_ids)} materials")

            return context

        except Exception as e:
            logger.error(f"Failed to fetch material analysis context: {e}")
            return {
                "material_count": len(material_ids),
                "analysis_depth": analysis_depth,
                "error": str(e)
            }

    async def store_cross_references(
        self,
        cross_references: list[dict[str, Any]]
    ) -> bool:
        """
        Store cross-references between materials.

        Args:
            cross_references: List of cross-reference data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Store cross-references in dedicated collection
            collection_name = "material_cross_references"

            # Prepare cross-reference data for storage
            embeddings_data = []
            for cross_ref in cross_references:
                # Create embedding data for the cross-reference
                ref_data = {
                    "source_id": cross_ref.get("source_material_id"),
                    "target_id": cross_ref.get("target_material_id"),
                    "relationship_type": cross_ref.get("relationship_type"),
                    "confidence": cross_ref.get("confidence", 0.0),
                    "context": cross_ref.get("context", ""),
                    "created_at": datetime.utcnow().isoformat()
                }

                embeddings_data.append({
                    "embedding": [0.0] * 1536,  # Placeholder embedding for cross-reference
                    "metadata": ref_data
                })

            # Store using bulk operations
            if embeddings_data:
                await self.qdrant_service.store_embeddings_bulk(
                    embeddings=[item["embedding"] for item in embeddings_data],
                    collection=collection_name,
                    metadata=[item["metadata"] for item in embeddings_data],
                    create_collection_if_missing=True
                )

            logger.debug(f"Stored {len(cross_references)} cross-references")
            return True

        except Exception as e:
            logger.error(f"Failed to store cross-references: {e}")
            return False

    async def get_material_statistics(self) -> dict[str, Any]:
        """
        Get statistics about stored materials.

        Returns:
            Dictionary with material statistics
        """
        try:
            stats = {
                "total_materials": 0,
                "collections": {},
                "categories": {},
                "total_embeddings": 0
            }

            # Get all collections
            collections = await self.qdrant_service.list_collections()
            material_collections = [col for col in collections if col.startswith("materials_")]

            for collection in material_collections:
                try:
                    # Get collection info
                    collection_info = await self.qdrant_service.get_collection_info(collection)

                    # Extract category from collection name
                    category = collection.replace("materials_", "")

                    # Update statistics
                    point_count = collection_info.get("points_count", 0)
                    stats["collections"][collection] = point_count
                    stats["categories"][category] = point_count
                    stats["total_materials"] += point_count

                except Exception as e:
                    logger.warning(f"Failed to get stats for collection {collection}: {e}")
                    continue

            logger.debug(f"Retrieved material statistics: {stats['total_materials']} total materials")

            return stats

        except Exception as e:
            logger.error(f"Failed to get material statistics: {e}")
            return {"error": str(e), "total_materials": 0}


# Global memory service instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


logger.info("Memory service module initialized")
