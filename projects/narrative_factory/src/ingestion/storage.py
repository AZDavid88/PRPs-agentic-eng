"""
Qdrant storage layer for material ingestion with temporal gating and spoiler prevention.

This module implements the storage layer for the Narrative Factory ingestion pipeline,
providing bulk material storage, temporal gating for spoiler prevention, and advanced
query capabilities with filtering support.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Any, Optional


try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        GeoBoundingBox,
        MatchAny,
        MatchExcept,
        MatchValue,
        PayloadSchemaType,
        PointStruct,
        Range,
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
    PointStruct = None
    VectorParams = None
    Range = None
    GeoBoundingBox = None
    MatchExcept = None

from pydantic import BaseModel, Field

from src.config import config
from src.exceptions import DatabaseError, with_retry
from src.logger import get_logger, log_execution_time
from src.memory.embedding_service import EmbeddingService
from src.memory.qdrant import QdrantConnectionPool
from src.models.material_models import (
    CategoryManager,
    MaterialClassification,
    MaterialQueryRequest,
    MaterialQueryResponse,
)


logger = get_logger(__name__)


class MaterialStorageConfig(BaseModel):
    """Configuration for material storage operations."""

    collection_name: str = Field(
        default="material_storage",
        description="Primary collection for material storage"
    )
    enable_temporal_gating: bool = Field(
        default=True,
        description="Enable temporal gating for spoiler prevention"
    )
    enable_versioning: bool = Field(
        default=True,
        description="Enable material versioning"
    )
    batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Default batch size for bulk operations"
    )
    max_query_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum results per query"
    )
    embedding_dimension: int = Field(
        default=2048,
        ge=384,
        le=4096,
        description="Embedding vector dimension"
    )
    enable_compression: bool = Field(
        default=True,
        description="Enable vector compression for storage efficiency"
    )


class BulkStorageRequest(BaseModel):
    """Request model for bulk material storage."""

    materials: list[MaterialClassification] = Field(
        ...,
        description="Materials to store"
    )
    collection_name: Optional[str] = Field(
        None,
        description="Target collection (uses default if not specified)"
    )
    enable_temporal_gating: bool = Field(
        default=True,
        description="Apply temporal gating to materials"
    )
    overwrite_existing: bool = Field(
        default=False,
        description="Overwrite existing materials with same ID"
    )
    generate_embeddings: bool = Field(
        default=True,
        description="Generate embeddings if not present"
    )
    batch_size: Optional[int] = Field(
        None,
        description="Override default batch size"
    )


class BulkStorageResponse(BaseModel):
    """Response model for bulk storage operations."""

    job_id: str = Field(..., description="Storage job identifier")
    status: str = Field(..., description="Storage status")
    stored_count: int = Field(0, description="Number of materials stored")
    failed_count: int = Field(0, description="Number of materials that failed")
    skipped_count: int = Field(0, description="Number of materials skipped")
    processing_time: float = Field(0.0, description="Total processing time in seconds")
    collection_name: str = Field(..., description="Target collection")
    errors: list[str] = Field(default_factory=list, description="Error messages")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")

    # Detailed metrics
    embedding_generation_time: float = Field(0.0, description="Time spent generating embeddings")
    qdrant_storage_time: float = Field(0.0, description="Time spent storing in Qdrant")
    temporal_gating_applied: int = Field(0, description="Number of materials with temporal gating")
    total_tokens_processed: int = Field(0, description="Total tokens processed for embeddings")
    estimated_storage_cost: float = Field(0.0, description="Estimated storage cost")


class TemporalGateFilter(BaseModel):
    """Temporal gating filter for spoiler prevention."""

    current_chapter: int = Field(
        ...,
        ge=1,
        description="Current chapter number for filtering"
    )
    story_thread: Optional[str] = Field(
        None,
        description="Specific story thread to filter by"
    )
    include_timeless: bool = Field(
        default=True,
        description="Include materials with timeless temporal scope"
    )
    spoiler_risk_threshold: str = Field(
        default="medium",
        description="Maximum spoiler risk level to include"
    )


class MaterialStorage:
    """
    Qdrant storage service for material ingestion with temporal gating and advanced querying.

    Provides bulk storage operations, spoiler prevention through temporal gating,
    and comprehensive query capabilities with filtering support.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        config_override: Optional[MaterialStorageConfig] = None
    ):
        """
        Initialize the material storage service.

        Args:
            url: Qdrant endpoint URL (defaults to config)
            api_key: Qdrant API key (defaults to config)
            config_override: Override default storage configuration
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is required. Install with: pip install qdrant-client")

        # Configuration
        self.config = config_override or MaterialStorageConfig()
        self.url = url or config.qdrant.url
        self.api_key = api_key or config.qdrant.api_key

        if not self.url:
            raise DatabaseError("Qdrant URL is required")

        # Initialize connection pool
        self.connection_pool = QdrantConnectionPool(
            url=self.url,
            api_key=self.api_key,
            max_connections=config.app.max_concurrent_tasks,
            min_connections=2,
            connection_timeout=config.qdrant.timeout,
            max_retries=config.qdrant.retries
        )

        # Initialize embedding service for on-demand embedding generation
        self._embedding_service = None

        # Storage statistics
        self._stats = {
            "total_stored": 0,
            "total_queries": 0,
            "average_storage_time": 0.0,
            "average_query_time": 0.0,
            "temporal_gates_applied": 0,
            "embedding_cache_hits": 0,
        }

        logger.info(f"MaterialStorage initialized with config: {self.config}")

    async def _get_embedding_service(self) -> EmbeddingService:
        """Lazy load the embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService(
                provider=config.models.embedding_provider
            )
        return self._embedding_service

    @with_retry(max_attempts=3, base_delay=1.0)
    @log_execution_time(__name__)
    async def create_collections(self) -> None:
        """Create required collections for material storage."""
        collections_to_create = [
            self.config.collection_name,
            f"{self.config.collection_name}_versioned",
            f"{self.config.collection_name}_temporal_index"
        ]

        for collection_name in collections_to_create:
            try:
                async with self.connection_pool.get_connection() as client:
                    exists = await client.collection_exists(collection_name)
                    if not exists:
                        logger.info(f"Creating collection: {collection_name}")
                        await client.create_collection(
                            collection_name=collection_name,
                            vectors_config=VectorParams(
                                size=self.config.embedding_dimension,
                                distance=Distance.COSINE
                            )
                        )
                        
                        # Create payload index for material_id field
                        await client.create_payload_index(
                            collection_name=collection_name,
                            field_name="material_id",
                            field_schema=PayloadSchemaType.KEYWORD
                        )
                        logger.info(f"Collection {collection_name} created successfully with material_id index")
                    else:
                        logger.info(f"Collection {collection_name} already exists")

            except Exception as e:
                logger.error(f"Failed to create collection {collection_name}: {e}")
                raise DatabaseError(f"Failed to create collection {collection_name}: {e}") from e

    async def store_material(
        self,
        material: MaterialClassification,
        collection_name: Optional[str] = None,
        generate_embedding: bool = True
    ) -> str:
        """
        Store a single material in Qdrant.

        Args:
            material: Material classification to store
            collection_name: Target collection (uses default if not specified)
            generate_embedding: Generate embedding if not present

        Returns:
            Point ID of stored material
        """
        target_collection = collection_name or self.config.collection_name

        try:
            # Generate embedding if needed
            if generate_embedding and not material.embedding_vector:
                embedding_service = await self._get_embedding_service()
                # Create content for embedding (combine key fields)
                content = self._create_embedding_content(material)
                material.embedding_vector = await embedding_service.generate_embedding(content)
                logger.debug(f"Generated embedding for material {material.material_id}")

            # Apply temporal gating if enabled
            if self.config.enable_temporal_gating:
                self._apply_temporal_gating(material)

            # Prepare point payload
            payload = self._prepare_storage_payload(material)

            # Create point with UUID for Qdrant compatibility
            point_id = str(uuid.uuid4())
            point = PointStruct(
                id=point_id,
                vector=material.embedding_vector or [0.0] * self.config.embedding_dimension,
                payload=payload
            )

            # Store in Qdrant
            async with self.connection_pool.get_connection() as client:
                await client.upsert(
                    collection_name=target_collection,
                    points=[point]
                )

            logger.info(f"Material {material.material_id} stored successfully as {point_id}")
            self._stats["total_stored"] += 1

            return point_id

        except Exception as e:
            logger.error(f"Failed to store material {material.material_id}: {e}")
            raise DatabaseError(f"Failed to store material: {e}") from e

    @with_retry(max_attempts=3, base_delay=1.0)
    @log_execution_time(__name__)
    async def bulk_store_materials(
        self,
        request: BulkStorageRequest
    ) -> BulkStorageResponse:
        """
        Store multiple materials in bulk with optimized processing.

        Args:
            request: Bulk storage request with materials and configuration

        Returns:
            Bulk storage response with detailed metrics
        """
        start_time = time.time()
        job_id = f"bulk_storage_{uuid.uuid4().hex[:8]}"
        target_collection = request.collection_name or self.config.collection_name
        batch_size = request.batch_size or self.config.batch_size

        logger.info(f"Starting bulk storage job {job_id} with {len(request.materials)} materials")

        # Initialize response
        response = BulkStorageResponse(
            job_id=job_id,
            status="processing",
            collection_name=target_collection
        )

        try:
            # Phase 1: Generate embeddings for materials that need them
            embedding_start = time.time()
            await self._bulk_generate_embeddings(request.materials, request.generate_embeddings)
            response.embedding_generation_time = time.time() - embedding_start

            # Phase 2: Apply temporal gating if enabled
            if request.enable_temporal_gating and self.config.enable_temporal_gating:
                for material in request.materials:
                    self._apply_temporal_gating(material)
                    response.temporal_gating_applied += 1

            # Phase 3: Bulk store in Qdrant
            storage_start = time.time()
            stored_count, failed_count, skipped_count, errors = await self._bulk_store_to_qdrant(
                request.materials,
                target_collection,
                batch_size,
                request.overwrite_existing
            )
            response.qdrant_storage_time = time.time() - storage_start

            # Update response with results
            response.stored_count = stored_count
            response.failed_count = failed_count
            response.skipped_count = skipped_count
            response.errors = errors
            response.status = "completed" if failed_count == 0 else "partial"
            response.total_tokens_processed = sum(
                len(m.extracted_entities) for m in request.materials
            )

            # Update statistics
            self._stats["total_stored"] += stored_count

            logger.info(
                f"Bulk storage job {job_id} completed: "
                f"{stored_count} stored, {failed_count} failed, {skipped_count} skipped"
            )

        except Exception as e:
            logger.error(f"Bulk storage job {job_id} failed: {e}")
            response.status = "failed"
            response.errors.append(str(e))

        finally:
            response.processing_time = time.time() - start_time

        return response

    async def _bulk_generate_embeddings(
        self,
        materials: list[MaterialClassification],
        generate_embeddings: bool
    ) -> None:
        """Generate embeddings for materials that need them."""
        if not generate_embeddings:
            return

        # Find materials without embeddings
        materials_needing_embeddings = [
            m for m in materials if not m.embedding_vector
        ]

        if not materials_needing_embeddings:
            logger.debug("All materials already have embeddings")
            return

        logger.info(f"Generating embeddings for {len(materials_needing_embeddings)} materials")

        embedding_service = await self._get_embedding_service()

        # Prepare content for embedding
        contents = [
            self._create_embedding_content(material)
            for material in materials_needing_embeddings
        ]

        # Generate embeddings in bulk
        embeddings = await embedding_service.generate_embeddings(contents)

        # Assign embeddings back to materials
        for material, embedding in zip(materials_needing_embeddings, embeddings):
            material.embedding_vector = embedding

        logger.info(f"Generated {len(embeddings)} embeddings successfully")

    async def _bulk_store_to_qdrant(
        self,
        materials: list[MaterialClassification],
        collection_name: str,
        batch_size: int,
        overwrite_existing: bool
    ) -> tuple[int, int, int, list[str]]:
        """Store materials to Qdrant in batches."""
        stored_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []

        # Process in batches
        for i in range(0, len(materials), batch_size):
            batch = materials[i:i + batch_size]

            try:
                # Prepare points for this batch
                points = []
                for material in batch:
                    # Check if material already exists (if not overwriting)
                    if not overwrite_existing:
                        exists = await self._material_exists(material.material_id, collection_name)
                        if exists:
                            skipped_count += 1
                            continue

                    # Create point with UUID for Qdrant compatibility
                    point_id = str(uuid.uuid4())
                    payload = self._prepare_storage_payload(material)

                    point = PointStruct(
                        id=point_id,
                        vector=material.embedding_vector or [0.0] * self.config.embedding_dimension,
                        payload=payload
                    )
                    points.append(point)

                # Batch upsert to Qdrant
                if points:
                    async with self.connection_pool.get_connection() as client:
                        await client.upsert(
                            collection_name=collection_name,
                            points=points
                        )
                    stored_count += len(points)

                logger.debug(f"Stored batch {i//batch_size + 1}: {len(points)} materials")

            except Exception as e:
                error_msg = f"Batch {i//batch_size + 1} failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                failed_count += len(batch)

        return stored_count, failed_count, skipped_count, errors

    async def _material_exists(self, material_id: str, collection_name: str) -> bool:
        """Check if a material already exists in the collection."""
        try:
            async with self.connection_pool.get_connection() as client:
                results = await client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="material_id",
                                match=MatchValue(value=material_id)
                            )
                        ]
                    ),
                    limit=1
                )
                return len(results[0]) > 0
        except Exception:
            return False

    def _create_embedding_content(self, material: MaterialClassification) -> str:
        """Create content string for embedding generation."""
        content_parts = []

        # Add primary classification info
        content_parts.append(f"Category: {material.primary_category}")

        if material.secondary_categories:
            content_parts.append(f"Secondary: {', '.join(material.secondary_categories)}")

        # Add genre context
        content_parts.append(f"Genre: {material.genre_context}")

        # Add extracted entities
        if material.extracted_entities:
            content_parts.append(f"Entities: {', '.join(material.extracted_entities)}")

        # Add temporal scope
        content_parts.append(f"Temporal: {material.temporal_scope}")

        # Add advanced metadata if available
        if material.advanced_metadata:
            for key, value in material.advanced_metadata.items():
                if isinstance(value, str):
                    content_parts.append(f"{key}: {value}")

        return " | ".join(content_parts)

    def _apply_temporal_gating(self, material: MaterialClassification) -> None:
        """Apply temporal gating rules to material."""
        if not material.chapter_availability:
            # Default gating based on spoiler risk
            spoiler_to_chapter = {
                "low": 1,
                "medium": 5,
                "high": 10
            }
            default_chapter = spoiler_to_chapter.get(material.spoiler_risk, 1)
            material.chapter_availability = {"main": default_chapter}

        self._stats["temporal_gates_applied"] += 1

    def _prepare_storage_payload(self, material: MaterialClassification) -> dict[str, Any]:
        """Prepare the payload for Qdrant storage."""
        payload = {
            # Core identification
            "material_id": material.material_id,
            "content_hash": material.content_hash,

            # Classification data
            "primary_category": material.primary_category,
            "secondary_categories": material.secondary_categories,
            "category_confidence": material.category_confidence,

            # Genre and context
            "genre_context": material.genre_context,
            "additional_genres": material.additional_genres,
            "complexity_level": material.complexity_level,

            # Content metadata
            "extracted_entities": material.extracted_entities,
            "content_length": material.content_length,

            # Temporal gating
            "chapter_availability": material.chapter_availability,
            "spoiler_risk": material.spoiler_risk,
            "temporal_scope": material.temporal_scope,

            # Processing metadata
            "processing_priority": material.processing_priority,
            "created_at": material.created_at.isoformat(),
            "classification_version": material.classification_version,

            # Advanced metadata
            "relationship_mapping": material.relationship_mapping or [],
            "cross_references": material.cross_references or {},
        }

        # Add advanced metadata if present
        if material.advanced_metadata:
            payload["advanced_metadata"] = material.advanced_metadata

        return payload

    @log_execution_time(__name__)
    async def query_materials(
        self,
        request: MaterialQueryRequest,
        temporal_filter: Optional[TemporalGateFilter] = None
    ) -> MaterialQueryResponse:
        """
        Query materials with advanced filtering and temporal gating.

        Args:
            request: Query request with filtering parameters
            temporal_filter: Temporal gating filter for spoiler prevention

        Returns:
            Query response with matching materials and metadata
        """
        start_time = time.time()
        collection_name = self.config.collection_name

        try:
            # Build Qdrant filters
            filters = self._build_query_filters(request, temporal_filter)

            # Execute query
            async with self.connection_pool.get_connection() as client:
                if request.similarity_query:
                    # Semantic similarity search
                    embedding_service = await self._get_embedding_service()
                    query_vector = await embedding_service.generate_embedding(request.similarity_query)

                    results = await client.search(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        query_filter=filters,
                        limit=request.limit,
                        score_threshold=request.min_similarity_score
                    )
                else:
                    # Filter-only search
                    results, _ = await client.scroll(
                        collection_name=collection_name,
                        scroll_filter=filters,
                        limit=request.limit
                    )

            # Convert results to MaterialClassification objects
            materials = []
            for result in results:
                material = self._payload_to_material(result.payload)
                materials.append(material)

            # Handle cross-references if requested
            cross_references = None
            if request.include_cross_references:
                cross_references = await self._fetch_cross_references(materials)

            # Build response
            response = MaterialQueryResponse(
                materials=materials,
                total_count=len(materials),
                query_time=time.time() - start_time,
                filters_applied=self._summarize_filters(request, temporal_filter),
                cross_references=cross_references
            )

            self._stats["total_queries"] += 1
            logger.info(f"Query completed: {len(materials)} materials found")

            return response

        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise DatabaseError(f"Query failed: {e}") from e

    def _build_query_filters(
        self,
        request: MaterialQueryRequest,
        temporal_filter: Optional[TemporalGateFilter]
    ) -> Optional[Filter]:
        """Build Qdrant filters from query request and temporal gating."""
        conditions = []

        # Category filters
        if request.categories:
            conditions.append(
                FieldCondition(
                    key="primary_category",
                    match=MatchAny(any=request.categories)
                )
            )

        # Genre filters
        if request.genre_context:
            conditions.append(
                FieldCondition(
                    key="genre_context",
                    match=MatchValue(value=request.genre_context)
                )
            )

        # Complexity filters
        if request.complexity_levels:
            conditions.append(
                FieldCondition(
                    key="complexity_level",
                    match=MatchAny(any=request.complexity_levels)
                )
            )

        # Spoiler risk filters
        if request.spoiler_risk:
            conditions.append(
                FieldCondition(
                    key="spoiler_risk",
                    match=MatchAny(any=request.spoiler_risk)
                )
            )

        # Temporal scope filters
        if request.temporal_scope:
            conditions.append(
                FieldCondition(
                    key="temporal_scope",
                    match=MatchAny(any=request.temporal_scope)
                )
            )

        # Temporal gating filters
        if temporal_filter:
            self._add_temporal_gating_filters(conditions, temporal_filter)

        return Filter(must=conditions) if conditions else None

    def _add_temporal_gating_filters(
        self,
        conditions: list[FieldCondition],
        temporal_filter: TemporalGateFilter
    ) -> None:
        """Add temporal gating conditions for spoiler prevention."""
        # Filter by chapter availability
        if temporal_filter.story_thread:
            # Specific story thread
            chapter_key = f"chapter_availability.{temporal_filter.story_thread}"
            conditions.append(
                FieldCondition(
                    key=chapter_key,
                    range=Range(lte=temporal_filter.current_chapter)
                )
            )
        else:
            # Main story thread
            conditions.append(
                FieldCondition(
                    key="chapter_availability.main",
                    range=Range(lte=temporal_filter.current_chapter)
                )
            )

        # Spoiler risk threshold
        spoiler_risk_levels = ["low"]
        if temporal_filter.spoiler_risk_threshold in ["medium", "high"]:
            spoiler_risk_levels.append("medium")
        if temporal_filter.spoiler_risk_threshold == "high":
            spoiler_risk_levels.append("high")

        conditions.append(
            FieldCondition(
                key="spoiler_risk",
                match=MatchAny(any=spoiler_risk_levels)
            )
        )

        # Include timeless materials if specified
        if temporal_filter.include_timeless:
            # This would require an OR condition - for simplicity, we'll handle in post-processing
            pass

    def _payload_to_material(self, payload: dict[str, Any]) -> MaterialClassification:
        """Convert Qdrant payload back to MaterialClassification."""
        return MaterialClassification(
            material_id=payload["material_id"],
            primary_category=payload["primary_category"],
            secondary_categories=payload.get("secondary_categories", []),
            category_confidence=payload.get("category_confidence", {}),
            genre_context=payload["genre_context"],
            additional_genres=payload.get("additional_genres", []),
            available_categories=CategoryManager.get_valid_categories(payload["genre_context"]),
            complexity_level=payload.get("complexity_level", "medium"),
            content_hash=payload["content_hash"],
            extracted_entities=payload.get("extracted_entities", []),
            content_length=payload.get("content_length", 0),
            chapter_availability=payload.get("chapter_availability", {}),
            spoiler_risk=payload.get("spoiler_risk", "low"),
            temporal_scope=payload.get("temporal_scope", "timeless"),
            processing_priority=payload.get("processing_priority", "normal"),
            created_at=datetime.fromisoformat(payload.get("created_at", datetime.utcnow().isoformat())),
            classification_version=payload.get("classification_version", "1.0"),
            relationship_mapping=payload.get("relationship_mapping"),
            cross_references=payload.get("cross_references"),
            advanced_metadata=payload.get("advanced_metadata")
        )

    async def _fetch_cross_references(
        self,
        materials: list[MaterialClassification]
    ) -> dict[str, list[MaterialClassification]]:
        """Fetch cross-referenced materials."""
        cross_references = {}

        for material in materials:
            if material.cross_references:
                for category, ref_ids in material.cross_references.items():
                    if category not in cross_references:
                        cross_references[category] = []

                    # Fetch referenced materials
                    for ref_id in ref_ids[:3]:  # Limit to 3 per category
                        try:
                            ref_material = await self._fetch_material_by_id(ref_id)
                            if ref_material:
                                cross_references[category].append(ref_material)
                        except Exception as e:
                            logger.warning(f"Failed to fetch cross-reference {ref_id}: {e}")

        return cross_references

    async def _fetch_material_by_id(self, material_id: str) -> Optional[MaterialClassification]:
        """Fetch a material by its ID."""
        try:
            async with self.connection_pool.get_connection() as client:
                results, _ = await client.scroll(
                    collection_name=self.config.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="material_id",
                                match=MatchValue(value=material_id)
                            )
                        ]
                    ),
                    limit=1
                )

                if results:
                    return self._payload_to_material(results[0].payload)
                return None

        except Exception as e:
            logger.error(f"Failed to fetch material {material_id}: {e}")
            return None

    def _summarize_filters(
        self,
        request: MaterialQueryRequest,
        temporal_filter: Optional[TemporalGateFilter]
    ) -> dict[str, Any]:
        """Summarize applied filters for response metadata."""
        summary = {}

        if request.categories:
            summary["categories"] = request.categories
        if request.genre_context:
            summary["genre_context"] = request.genre_context
        if request.complexity_levels:
            summary["complexity_levels"] = request.complexity_levels
        if request.spoiler_risk:
            summary["spoiler_risk"] = request.spoiler_risk
        if request.temporal_scope:
            summary["temporal_scope"] = request.temporal_scope
        if request.similarity_query:
            summary["similarity_query"] = request.similarity_query
            summary["min_similarity_score"] = request.min_similarity_score

        if temporal_filter:
            summary["temporal_gating"] = {
                "current_chapter": temporal_filter.current_chapter,
                "story_thread": temporal_filter.story_thread,
                "spoiler_risk_threshold": temporal_filter.spoiler_risk_threshold
            }

        return summary

    async def get_storage_stats(self) -> dict[str, Any]:
        """Get comprehensive storage statistics."""
        collection_stats = {}

        try:
            async with self.connection_pool.get_connection() as client:
                info = await client.get_collection(self.config.collection_name)
                collection_stats = {
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "status": info.status.value,
                    "vector_size": info.config.params.vectors.size,
                    "distance_metric": info.config.params.vectors.distance.value
                }
        except Exception as e:
            logger.warning(f"Failed to get collection stats: {e}")
            collection_stats = {"error": str(e)}

        return {
            "service_stats": self._stats,
            "collection_stats": collection_stats,
            "connection_pool_stats": self.connection_pool.get_stats(),
            "configuration": {
                "collection_name": self.config.collection_name,
                "embedding_dimension": self.config.embedding_dimension,
                "temporal_gating_enabled": self.config.enable_temporal_gating,
                "versioning_enabled": self.config.enable_versioning,
                "batch_size": self.config.batch_size
            }
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on storage service."""
        health_status = {
            "storage_service_healthy": True,
            "qdrant_connected": False,
            "embedding_service_ready": False,
            "collections_accessible": False,
            "errors": []
        }

        try:
            # Test Qdrant connection
            async with self.connection_pool.get_connection() as client:
                await client.get_collections()
                health_status["qdrant_connected"] = True

                # Test collection access
                exists = await client.collection_exists(self.config.collection_name)
                health_status["collections_accessible"] = exists

        except Exception as e:
            health_status["errors"].append(f"Qdrant connection failed: {e}")
            health_status["storage_service_healthy"] = False

        try:
            # Test embedding service
            embedding_service = await self._get_embedding_service()
            await embedding_service.generate_embedding("test")
            health_status["embedding_service_ready"] = True

        except Exception as e:
            health_status["errors"].append(f"Embedding service failed: {e}")
            health_status["storage_service_healthy"] = False

        return health_status

    async def close(self) -> None:
        """Close the storage service and cleanup resources."""
        try:
            await self.connection_pool.close()
            if self._embedding_service:
                await self._embedding_service.close()
            logger.info("MaterialStorage closed successfully")
        except Exception as e:
            logger.error(f"Error closing MaterialStorage: {e}")
            raise DatabaseError(f"Error closing storage service: {e}") from e

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connection_pool.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience functions for common operations

async def create_material_storage_service(
    config_override: Optional[MaterialStorageConfig] = None
) -> MaterialStorage:
    """Create and initialize a material storage service."""
    service = MaterialStorage(config_override=config_override)
    await service.create_collections()
    return service


async def bulk_store_materials(
    materials: list[MaterialClassification],
    collection_name: Optional[str] = None,
    enable_temporal_gating: bool = True,
    generate_embeddings: bool = True
) -> BulkStorageResponse:
    """Convenience function for bulk material storage."""
    async with MaterialStorage() as storage_service:
        request = BulkStorageRequest(
            materials=materials,
            collection_name=collection_name,
            enable_temporal_gating=enable_temporal_gating,
            generate_embeddings=generate_embeddings
        )
        return await storage_service.bulk_store_materials(request)


async def query_materials_with_temporal_gating(
    categories: Optional[list[str]] = None,
    current_chapter: int = 1,
    spoiler_risk_threshold: str = "medium",
    limit: int = 50
) -> MaterialQueryResponse:
    """Convenience function for querying materials with temporal gating."""
    async with MaterialStorage() as storage_service:
        query_request = MaterialQueryRequest(
            categories=categories,
            limit=limit
        )
        temporal_filter = TemporalGateFilter(
            current_chapter=current_chapter,
            spoiler_risk_threshold=spoiler_risk_threshold
        )
        return await storage_service.query_materials(query_request, temporal_filter)


# Convenience alias for backwards compatibility
MaterialStorageService = MaterialStorage


if __name__ == "__main__":
    async def main():
        """Example usage of MaterialStorage."""
        # Create sample materials for testing
        from src.models.material_models import MaterialClassification

        sample_materials = [
            MaterialClassification(
                material_id="test_001",
                primary_category="character",
                genre_context="fantasy",
                content_hash="abc123def456",
                extracted_entities=["Aragorn", "Ranger"],
                spoiler_risk="low",
                temporal_scope="timeless"
            ),
            MaterialClassification(
                material_id="test_002",
                primary_category="plot_element",
                genre_context="fantasy",
                content_hash="def456ghi789",
                extracted_entities=["Ring", "Quest"],
                spoiler_risk="high",
                temporal_scope="future"
            )
        ]

        async with MaterialStorage() as storage_service:
            # Test bulk storage
            request = BulkStorageRequest(materials=sample_materials)
            response = await storage_service.bulk_store_materials(request)
            print(f"Stored {response.stored_count} materials")

            # Test query with temporal gating
            query_request = MaterialQueryRequest(categories=["character"])
            temporal_filter = TemporalGateFilter(current_chapter=1)
            query_response = await storage_service.query_materials(query_request, temporal_filter)
            print(f"Found {len(query_response.materials)} materials")

            # Print stats
            stats = await storage_service.get_storage_stats()
            print(f"Storage stats: {stats}")

    asyncio.run(main())
