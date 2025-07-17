"""
Memory service abstraction for the Narrative Factory.

Provides a high-level interface for memory operations with production-ready patterns.
"""

from typing import Optional

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

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Global memory service instance
_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


logger.info("Memory service module initialized")
