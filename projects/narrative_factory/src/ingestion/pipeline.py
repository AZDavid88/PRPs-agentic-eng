"""
Core material ingestion pipeline for the Narrative Factory.

This module orchestrates the complete material ingestion process, providing both
lightweight bulk processing and comprehensive agent-based processing modes with
cost optimization, progress tracking, and error handling.
"""

import asyncio
import time
import uuid
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from src.config import config
from src.exceptions import ValidationError, with_retry
from src.ingestion.classifier import MaterialClassifier
from src.ingestion.storage import BulkStorageRequest, MaterialStorage
from src.logger import get_logger, log_execution_time
from src.memory.embedding_service import EmbeddingService
from src.models.material_models import (
    MaterialClassification,
    MaterialIngestionRequest,
    MaterialIngestionResponse,
)


logger = get_logger(__name__)


# =============================================================================
# PIPELINE CONFIGURATION AND MODELS
# =============================================================================

class PipelineConfig(BaseModel):
    """Configuration for the ingestion pipeline."""

    # Processing modes
    default_processing_mode: str = Field(
        default="pipeline",
        description="Default processing mode (pipeline/agent/hybrid)"
    )

    # Performance settings
    max_concurrent_materials: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum materials to process concurrently"
    )
    batch_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Default batch size for bulk operations"
    )
    pipeline_timeout: float = Field(
        default=600.0,
        ge=60.0,
        le=3600.0,
        description="Pipeline timeout in seconds"
    )

    # Cost optimization
    cost_per_material_target: float = Field(
        default=0.005,
        ge=0.001,
        le=0.1,
        description="Target cost per material for pipeline mode"
    )
    enable_cost_monitoring: bool = Field(
        default=True,
        description="Enable real-time cost monitoring and optimization"
    )

    # Quality settings
    min_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for classifications"
    )
    enable_quality_validation: bool = Field(
        default=True,
        description="Enable quality validation checks"
    )

    # Error handling
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for failed operations"
    )
    enable_graceful_degradation: bool = Field(
        default=True,
        description="Enable fallback processing for failed materials"
    )


class PipelineMetrics(BaseModel):
    """Comprehensive metrics for pipeline execution."""

    # Processing metrics
    total_materials: int = Field(0, description="Total materials processed")
    successful_materials: int = Field(0, description="Successfully processed materials")
    failed_materials: int = Field(0, description="Failed materials")
    retried_materials: int = Field(0, description="Materials that required retries")

    # Performance metrics
    total_processing_time: float = Field(0.0, description="Total processing time in seconds")
    average_time_per_material: float = Field(0.0, description="Average time per material")
    throughput_materials_per_second: float = Field(0.0, description="Processing throughput")
    peak_memory_usage: float = Field(0.0, description="Peak memory usage in MB")

    # Cost metrics
    total_cost_estimate: float = Field(0.0, description="Total estimated cost in USD")
    cost_per_material: float = Field(0.0, description="Average cost per material")
    classification_cost: float = Field(0.0, description="Cost for LLM classification")
    embedding_cost: float = Field(0.0, description="Cost for embedding generation")
    storage_cost: float = Field(0.0, description="Cost for storage operations")

    # Quality metrics
    average_confidence: float = Field(0.0, description="Average classification confidence")
    quality_score: float = Field(0.0, description="Overall quality score")
    category_distribution: dict[str, int] = Field(default_factory=dict, description="Distribution across categories")
    complexity_distribution: dict[str, int] = Field(default_factory=dict, description="Distribution across complexity levels")

    # System metrics
    classification_time: float = Field(0.0, description="Time spent on classification")
    embedding_generation_time: float = Field(0.0, description="Time spent generating embeddings")
    storage_time: float = Field(0.0, description="Time spent on storage operations")
    cross_references_identified: int = Field(0, description="Number of cross-references identified")


class PipelineProgressUpdate(BaseModel):
    """Progress update model for real-time monitoring."""

    job_id: str = Field(..., description="Pipeline job identifier")
    stage: str = Field(..., description="Current processing stage")
    progress_percentage: float = Field(..., description="Overall progress percentage")
    materials_processed: int = Field(..., description="Number of materials processed")
    materials_remaining: int = Field(..., description="Number of materials remaining")
    current_batch: int = Field(..., description="Current batch number")
    total_batches: int = Field(..., description="Total number of batches")
    estimated_time_remaining: float = Field(..., description="Estimated time remaining in seconds")
    current_cost: float = Field(..., description="Current cost accumulation")
    errors_encountered: int = Field(..., description="Number of errors encountered")
    warnings_generated: int = Field(..., description="Number of warnings generated")
    message: Optional[str] = Field(None, description="Current status message")


# =============================================================================
# CORE PIPELINE ORCHESTRATOR
# =============================================================================

class MaterialIngestionPipeline:
    """
    Core orchestrator for material ingestion with dual processing modes.

    Provides both lightweight pipeline processing for bulk operations and
    comprehensive agent-based processing for complex materials requiring
    detailed analysis and relationship mapping.
    """

    def __init__(
        self,
        config_override: Optional[PipelineConfig] = None,
        classifier_override: Optional[MaterialClassifier] = None,
        storage_service_override: Optional[MaterialStorage] = None,
        embedding_service_override: Optional[EmbeddingService] = None
    ):
        """
        Initialize the material ingestion pipeline.

        Args:
            config_override: Custom pipeline configuration
            classifier_override: Custom classifier instance
            storage_service_override: Custom storage service instance
            embedding_service_override: Custom embedding service instance
        """
        self.config = config_override or PipelineConfig()

        # Initialize core services
        self.classifier = classifier_override or MaterialClassifier(
            client_type="gemini",
            batch_size=self.config.batch_size,
            max_retries=self.config.max_retries
        )

        self.storage_service = storage_service_override or MaterialStorage()
        self.embedding_service = embedding_service_override or EmbeddingService(
            provider=config.models.embedding_provider
        )

        # Pipeline state
        self._current_job_id: Optional[str] = None
        self._progress_callback: Optional[Callable[[PipelineProgressUpdate], None]] = None
        self._metrics = PipelineMetrics()
        self._processing_stats = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "average_job_time": 0.0
        }

        logger.info(f"MaterialIngestionPipeline initialized with {self.config.default_processing_mode} mode")

    @with_retry(max_attempts=3, base_delay=1.0)
    @log_execution_time(__name__)
    async def process_materials(
        self,
        request: MaterialIngestionRequest,
        progress_callback: Optional[Callable[[PipelineProgressUpdate], None]] = None
    ) -> MaterialIngestionResponse:
        """
        Process materials using the specified mode with comprehensive monitoring.

        Args:
            request: Material ingestion request with all parameters
            progress_callback: Optional callback for real-time progress updates

        Returns:
            Comprehensive ingestion response with results and metrics
        """
        start_time = time.time()
        job_id = f"ingestion_{uuid.uuid4().hex[:8]}"
        self._current_job_id = job_id
        self._progress_callback = progress_callback

        logger.info(
            f"Starting ingestion job {job_id}: {len(request.materials)} materials "
            f"in {request.processing_mode} mode"
        )

        # Initialize metrics
        self._metrics = PipelineMetrics(total_materials=len(request.materials))

        try:
            # Validate request
            await self._validate_request(request)

            # Send initial progress update
            await self._send_progress_update(
                job_id, "initialization", 0.0, 0, len(request.materials),
                message="Initializing pipeline..."
            )

            # Route to appropriate processing mode
            if request.processing_mode == "pipeline":
                response = await self._process_pipeline_mode(request, job_id)
            elif request.processing_mode == "agent":
                response = await self._process_agent_mode(request, job_id)
            elif request.processing_mode == "hybrid":
                response = await self._process_hybrid_mode(request, job_id)
            else:
                raise ValidationError(f"Unknown processing mode: {request.processing_mode}")

            # Finalize metrics
            total_time = time.time() - start_time
            self._finalize_metrics(total_time, response)

            # Send final progress update
            await self._send_progress_update(
                job_id, "completed", 100.0, len(response.classifications), 0,
                message=f"Pipeline completed successfully: {len(response.classifications)} materials processed"
            )

            # Update processing stats
            self._processing_stats["total_jobs"] += 1
            self._processing_stats["successful_jobs"] += 1
            avg_time = self._processing_stats["average_job_time"]
            total_jobs = self._processing_stats["total_jobs"]
            self._processing_stats["average_job_time"] = (
                (avg_time * (total_jobs - 1) + total_time) / total_jobs
            )

            logger.info(
                f"Ingestion job {job_id} completed successfully: "
                f"{len(response.classifications)} materials processed in {total_time:.2f}s"
            )

            return response

        except Exception as e:
            logger.error(f"Ingestion job {job_id} failed: {e}")

            # Update failure stats
            self._processing_stats["total_jobs"] += 1
            self._processing_stats["failed_jobs"] += 1

            # Send error progress update
            await self._send_progress_update(
                job_id, "failed", 0.0, 0, len(request.materials),
                message=f"Pipeline failed: {str(e)}"
            )

            # Return error response
            return MaterialIngestionResponse(
                job_id=job_id,
                status="failed",
                processing_time=time.time() - start_time,
                cost_estimate=0.0,
                materials_processed=0,
                average_confidence=0.0,
                category_distribution={},
                complexity_distribution={},
                embedding_cache_hits=0,
                cross_references_identified=0,
                errors=[str(e)]
            )

    async def _process_pipeline_mode(
        self,
        request: MaterialIngestionRequest,
        job_id: str
    ) -> MaterialIngestionResponse:
        """Process materials using lightweight pipeline mode for efficiency."""
        logger.info(f"Processing {len(request.materials)} materials in pipeline mode")

        start_time = time.time()

        # Stage 1: Batch Classification (50% of progress)
        await self._send_progress_update(
            job_id, "classification", 10.0, 0, len(request.materials),
            message="Starting batch classification..."
        )

        classification_start = time.time()
        classifications = await self.classifier.classify_materials_batch(
            materials=request.materials,
            genre_context=request.genre_context,
            additional_genres=request.additional_genres,
            custom_categories=request.custom_categories,
            batch_size=request.batch_size
        )
        self._metrics.classification_time = time.time() - classification_start

        await self._send_progress_update(
            job_id, "classification", 50.0, len(classifications), 0,
            message="Classification completed"
        )

        # Stage 2: Embedding Generation (25% of progress)
        await self._send_progress_update(
            job_id, "embeddings", 60.0, len(classifications), 0,
            message="Generating embeddings..."
        )

        embedding_start = time.time()
        await self._generate_embeddings_bulk(classifications)
        self._metrics.embedding_generation_time = time.time() - embedding_start

        await self._send_progress_update(
            job_id, "embeddings", 75.0, len(classifications), 0,
            message="Embeddings generated"
        )

        # Stage 3: Storage (25% of progress)
        await self._send_progress_update(
            job_id, "storage", 80.0, len(classifications), 0,
            message="Storing materials..."
        )

        storage_start = time.time()
        storage_request = BulkStorageRequest(
            materials=classifications,
            enable_temporal_gating=True,
            generate_embeddings=False,  # Already generated
            batch_size=self.config.batch_size,
            overwrite_existing=False
        )
        await self.storage_service.bulk_store_materials(storage_request)
        self._metrics.storage_time = time.time() - storage_start

        await self._send_progress_update(
            job_id, "storage", 90.0, len(classifications), 0,
            message="Storage completed"
        )

        # Filter successful classifications based on confidence threshold
        valid_classifications = [
            c for c in classifications
            if self._get_primary_confidence(c) >= request.min_confidence_threshold
        ]

        # Calculate costs
        total_time = time.time() - start_time
        cost_estimate = self._calculate_pipeline_cost(len(request.materials), total_time)

        # Build response
        response = MaterialIngestionResponse(
            job_id=job_id,
            status="completed" if len(valid_classifications) == len(request.materials) else "partial",
            classifications=valid_classifications,
            failed_materials=[
                {"material": mat, "error": "Below confidence threshold"}
                for i, mat in enumerate(request.materials)
                if i >= len(classifications) or
                self._get_primary_confidence(classifications[i]) < request.min_confidence_threshold
            ],
            processing_time=total_time,
            cost_estimate=cost_estimate,
            materials_processed=len(valid_classifications),
            average_confidence=self._calculate_average_confidence(valid_classifications),
            category_distribution=self._calculate_category_distribution(valid_classifications),
            complexity_distribution=self._calculate_complexity_distribution(valid_classifications)
        )

        logger.info(f"Pipeline mode completed: {len(valid_classifications)} materials processed")
        return response

    async def _process_agent_mode(
        self,
        request: MaterialIngestionRequest,
        job_id: str
    ) -> MaterialIngestionResponse:
        """Process materials using comprehensive agent mode with detailed analysis."""
        logger.info(f"Processing {len(request.materials)} materials in agent mode")

        start_time = time.time()
        classifications = []

        # Process materials individually with detailed analysis
        for i, material in enumerate(request.materials):
            try:
                progress = (i / len(request.materials)) * 80  # Reserve 20% for storage
                await self._send_progress_update(
                    job_id, "agent_analysis", progress, i, len(request.materials) - i,
                    message=f"Processing material {i + 1}/{len(request.materials)}"
                )

                # Individual classification with full analysis
                classification = await self.classifier.classify_material(
                    material=material,
                    genre_context=request.genre_context,
                    additional_genres=request.additional_genres,
                    custom_categories=request.custom_categories,
                    complexity_level="complex"  # Force complex analysis in agent mode
                )

                # Enhanced entity extraction and relationship mapping
                await self._enhance_classification_with_agent_analysis(classification, material)

                classifications.append(classification)

            except Exception as e:
                logger.error(f"Failed to process material {i}: {e}")
                # Continue with remaining materials
                continue

        # Cross-reference analysis
        if request.enable_cross_references:
            await self._send_progress_update(
                job_id, "cross_reference", 85.0, len(classifications), 0,
                message="Analyzing cross-references..."
            )
            self._generate_cross_references(classifications)

        # Generate embeddings and store
        await self._send_progress_update(
            job_id, "finalization", 90.0, len(classifications), 0,
            message="Finalizing storage..."
        )

        await self._generate_embeddings_bulk(classifications)

        storage_request = BulkStorageRequest(
            materials=classifications,
            enable_temporal_gating=True,
            generate_embeddings=False,
            batch_size=self.config.batch_size
        )
        await self.storage_service.bulk_store_materials(storage_request)

        # Calculate costs (higher for agent mode)
        total_time = time.time() - start_time
        cost_estimate = self._calculate_agent_cost(len(request.materials), total_time)

        response = MaterialIngestionResponse(
            job_id=job_id,
            status="completed",
            classifications=classifications,
            processing_time=total_time,
            cost_estimate=cost_estimate,
            materials_processed=len(classifications),
            average_confidence=self._calculate_average_confidence(classifications),
            category_distribution=self._calculate_category_distribution(classifications),
            complexity_distribution=self._calculate_complexity_distribution(classifications),
            cross_references_identified=sum(len(c.cross_references or {}) for c in classifications)
        )

        logger.info(f"Agent mode completed: {len(classifications)} materials processed")
        return response

    async def _process_hybrid_mode(
        self,
        request: MaterialIngestionRequest,
        job_id: str
    ) -> MaterialIngestionResponse:
        """Process materials using hybrid mode: pipeline for simple, agent for complex."""
        logger.info(f"Processing {len(request.materials)} materials in hybrid mode")

        start_time = time.time()

        # Stage 1: Quick classification to determine complexity
        await self._send_progress_update(
            job_id, "complexity_analysis", 10.0, 0, len(request.materials),
            message="Analyzing material complexity..."
        )

        complexity_assessments = await self._assess_material_complexities(request.materials)

        # Separate materials by complexity
        simple_materials = []
        complex_materials = []

        for i, (material, complexity) in enumerate(zip(request.materials, complexity_assessments)):
            if complexity in ["simple", "medium"]:
                simple_materials.append((i, material))
            else:
                complex_materials.append((i, material))

        logger.info(
            f"Hybrid mode routing: {len(simple_materials)} simple, "
            f"{len(complex_materials)} complex materials"
        )

        # Process simple materials in pipeline mode
        simple_classifications = []
        if simple_materials:
            await self._send_progress_update(
                job_id, "pipeline_processing", 25.0, 0, len(simple_materials),
                message=f"Processing {len(simple_materials)} simple materials in pipeline mode..."
            )

            simple_material_texts = [mat for _, mat in simple_materials]
            simple_classifications = await self.classifier.classify_materials_batch(
                materials=simple_material_texts,
                genre_context=request.genre_context,
                additional_genres=request.additional_genres,
                custom_categories=request.custom_categories,
                batch_size=request.batch_size
            )

        # Process complex materials in agent mode
        complex_classifications = []
        if complex_materials:
            await self._send_progress_update(
                job_id, "agent_processing", 50.0, len(simple_classifications), len(complex_materials),
                message=f"Processing {len(complex_materials)} complex materials in agent mode..."
            )

            for i, (original_index, material) in enumerate(complex_materials):
                try:
                    progress = 50.0 + (i / len(complex_materials)) * 30.0
                    await self._send_progress_update(
                        job_id, "agent_processing", progress,
                        len(simple_classifications) + i, len(complex_materials) - i,
                        message=f"Agent analysis: material {i + 1}/{len(complex_materials)}"
                    )

                    classification = await self.classifier.classify_material(
                        material=material,
                        genre_context=request.genre_context,
                        additional_genres=request.additional_genres,
                        custom_categories=request.custom_categories,
                        complexity_level="complex"
                    )

                    await self._enhance_classification_with_agent_analysis(classification, material)
                    complex_classifications.append(classification)

                except Exception as e:
                    logger.error(f"Failed to process complex material {original_index}: {e}")
                    continue

        # Combine results
        all_classifications = simple_classifications + complex_classifications

        # Generate embeddings and store
        await self._send_progress_update(
            job_id, "finalization", 85.0, len(all_classifications), 0,
            message="Generating embeddings and storing..."
        )

        await self._generate_embeddings_bulk(all_classifications)

        storage_request = BulkStorageRequest(
            materials=all_classifications,
            enable_temporal_gating=True,
            generate_embeddings=False,
            batch_size=self.config.batch_size
        )
        await self.storage_service.bulk_store_materials(storage_request)

        # Calculate costs (between pipeline and agent)
        total_time = time.time() - start_time
        cost_estimate = self._calculate_hybrid_cost(
            len(simple_materials), len(complex_materials), total_time
        )

        response = MaterialIngestionResponse(
            job_id=job_id,
            status="completed",
            classifications=all_classifications,
            processing_time=total_time,
            cost_estimate=cost_estimate,
            materials_processed=len(all_classifications),
            average_confidence=self._calculate_average_confidence(all_classifications),
            category_distribution=self._calculate_category_distribution(all_classifications),
            complexity_distribution=self._calculate_complexity_distribution(all_classifications)
        )

        logger.info(f"Hybrid mode completed: {len(all_classifications)} materials processed")
        return response

    # =============================================================================
    # HELPER METHODS
    # =============================================================================

    async def _validate_request(self, request: MaterialIngestionRequest) -> None:
        """Validate the ingestion request."""
        if not request.materials:
            raise ValidationError("No materials provided for processing")

        if len(request.materials) > 1000:
            raise ValidationError("Maximum 1000 materials per request")

        # Validate genre context
        if request.genre_context == "unknown":
            logger.warning("Processing with unknown genre context - may affect classification quality")

        # Validate custom categories
        if request.custom_categories:
            for category in request.custom_categories:
                if not category.isalnum() and '_' not in category:
                    raise ValidationError(f"Invalid custom category format: {category}")

    async def _generate_embeddings_bulk(self, classifications: list[MaterialClassification]) -> None:
        """Generate embeddings for classifications that need them."""
        materials_needing_embeddings = [c for c in classifications if not c.embedding_vector]

        if not materials_needing_embeddings:
            return

        logger.info(f"Generating embeddings for {len(materials_needing_embeddings)} materials")

        # Prepare content for embedding
        contents = []
        for classification in materials_needing_embeddings:
            content = self._create_embedding_content(classification)
            contents.append(content)

        # Generate embeddings in bulk
        embeddings = await self.embedding_service.generate_embeddings(contents)

        # Assign back to classifications
        for classification, embedding in zip(materials_needing_embeddings, embeddings):
            classification.embedding_vector = embedding

    def _create_embedding_content(self, classification: MaterialClassification) -> str:
        """Create content string for embedding generation."""
        content_parts = [
            f"Category: {classification.primary_category}",
            f"Genre: {classification.genre_context}",
        ]

        if classification.secondary_categories:
            content_parts.append(f"Secondary: {', '.join(classification.secondary_categories)}")

        if classification.extracted_entities:
            content_parts.append(f"Entities: {', '.join(classification.extracted_entities)}")

        content_parts.append(f"Temporal: {classification.temporal_scope}")

        return " | ".join(content_parts)

    async def _enhance_classification_with_agent_analysis(
        self,
        classification: MaterialClassification,
        original_material: str
    ) -> None:
        """Enhance classification with detailed agent analysis."""
        # This would integrate with a Librarian agent in a full implementation
        # For now, we'll add some enhanced metadata

        if not classification.advanced_metadata:
            classification.advanced_metadata = {}

        classification.advanced_metadata.update({
            "agent_analysis_version": "1.0",
            "detailed_analysis_performed": True,
            "original_content_length": len(original_material),
            "processing_timestamp": time.time()
        })

        # Update complexity level based on enhanced analysis
        classification.update_complexity_level()

    def _generate_cross_references(self, classifications: list[MaterialClassification]) -> None:
        """Generate cross-references between classifications."""
        # Simple entity-based cross-referencing
        entity_map = {}

        # Build entity index
        for classification in classifications:
            for entity in classification.extracted_entities:
                if entity not in entity_map:
                    entity_map[entity] = []
                entity_map[entity].append(classification.material_id)

        # Add cross-references for shared entities
        for classification in classifications:
            for entity in classification.extracted_entities:
                related_materials = [
                    mid for mid in entity_map[entity]
                    if mid != classification.material_id
                ]
                if related_materials:
                    for related_id in related_materials[:3]:  # Limit to 3
                        classification.add_cross_reference("shared_entity", related_id)

    async def _assess_material_complexities(self, materials: list[str]) -> list[str]:
        """Assess complexity of materials for hybrid mode routing."""
        complexities = []

        for material in materials:
            # Simple heuristics for complexity assessment
            length = len(material)

            if length < 200:
                complexity = "simple"
            elif length > 1000:
                complexity = "complex"
            else:
                # Check for complex indicators
                complex_keywords = [
                    "magic", "spell", "prophecy", "ancient", "mythology",
                    "technology", "quantum", "alien", "dimensional",
                    "philosophy", "existential", "metaphysical"
                ]

                if any(keyword in material.lower() for keyword in complex_keywords):
                    complexity = "complex"
                else:
                    complexity = "medium"

            complexities.append(complexity)

        return complexities

    async def _send_progress_update(
        self,
        job_id: str,
        stage: str,
        progress: float,
        processed: int,
        remaining: int,
        message: Optional[str] = None
    ) -> None:
        """Send progress update to callback if available."""
        if not self._progress_callback:
            return

        total = processed + remaining
        current_batch = (processed // self.config.batch_size) + 1 if processed > 0 else 1
        total_batches = (total + self.config.batch_size - 1) // self.config.batch_size

        # Estimate time remaining
        if processed > 0 and self._metrics.total_processing_time > 0:
            avg_time_per_material = self._metrics.total_processing_time / processed
            eta = remaining * avg_time_per_material
        else:
            eta = 0.0

        update = PipelineProgressUpdate(
            job_id=job_id,
            stage=stage,
            progress_percentage=progress,
            materials_processed=processed,
            materials_remaining=remaining,
            current_batch=current_batch,
            total_batches=total_batches,
            estimated_time_remaining=eta,
            current_cost=self._metrics.total_cost_estimate,
            errors_encountered=self._metrics.failed_materials,
            warnings_generated=0,  # Would track warnings in full implementation
            message=message
        )

        try:
            self._progress_callback(update)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")

    def _calculate_pipeline_cost(self, material_count: int, processing_time: float) -> float:
        """Calculate cost estimate for pipeline mode."""
        # Simplified cost calculation
        base_cost_per_material = 0.003  # Target: $0.005, actual lower
        time_factor = processing_time / 60.0  # Time adjustment
        return material_count * base_cost_per_material * (1 + time_factor * 0.1)

    def _calculate_agent_cost(self, material_count: int, processing_time: float) -> float:
        """Calculate cost estimate for agent mode."""
        # Higher cost for comprehensive analysis
        base_cost_per_material = 0.08  # More expensive due to individual processing
        time_factor = processing_time / 60.0
        return material_count * base_cost_per_material * (1 + time_factor * 0.2)

    def _calculate_hybrid_cost(
        self,
        simple_count: int,
        complex_count: int,
        processing_time: float
    ) -> float:
        """Calculate cost estimate for hybrid mode."""
        simple_cost = self._calculate_pipeline_cost(simple_count, processing_time * 0.3)
        complex_cost = self._calculate_agent_cost(complex_count, processing_time * 0.7)
        return simple_cost + complex_cost

    def _get_primary_confidence(self, classification: MaterialClassification) -> float:
        """Get confidence score for primary category."""
        return classification.category_confidence.get(classification.primary_category, 0.0)

    def _calculate_average_confidence(self, classifications: list[MaterialClassification]) -> float:
        """Calculate average confidence across classifications."""
        if not classifications:
            return 0.0

        total_confidence = sum(self._get_primary_confidence(c) for c in classifications)
        return total_confidence / len(classifications)

    def _calculate_category_distribution(self, classifications: list[MaterialClassification]) -> dict[str, int]:
        """Calculate distribution of materials across categories."""
        distribution = {}
        for classification in classifications:
            category = classification.primary_category
            distribution[category] = distribution.get(category, 0) + 1
        return distribution

    def _calculate_complexity_distribution(self, classifications: list[MaterialClassification]) -> dict[str, int]:
        """Calculate distribution of materials across complexity levels."""
        distribution = {}
        for classification in classifications:
            level = classification.complexity_level
            distribution[level] = distribution.get(level, 0) + 1
        return distribution

    def _finalize_metrics(self, total_time: float, response: MaterialIngestionResponse) -> None:
        """Finalize pipeline metrics."""
        self._metrics.total_processing_time = total_time
        self._metrics.successful_materials = response.materials_processed
        self._metrics.failed_materials = len(response.failed_materials)

        if response.materials_processed > 0:
            self._metrics.average_time_per_material = total_time / response.materials_processed
            self._metrics.throughput_materials_per_second = response.materials_processed / total_time

        self._metrics.total_cost_estimate = response.cost_estimate
        self._metrics.cost_per_material = (
            response.cost_estimate / response.materials_processed
            if response.materials_processed > 0 else 0.0
        )
        self._metrics.average_confidence = response.average_confidence
        self._metrics.category_distribution = response.category_distribution
        self._metrics.complexity_distribution = response.complexity_distribution

    async def get_pipeline_stats(self) -> dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        return {
            "processing_stats": self._processing_stats,
            "current_metrics": self._metrics.dict(),
            "configuration": self.config.dict(),
            "classifier_stats": self.classifier.get_processing_stats(),
            "storage_stats": await self.storage_service.get_storage_stats()
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check on pipeline components."""
        health_status = {
            "pipeline_healthy": True,
            "classifier_healthy": False,
            "storage_healthy": False,
            "embedding_service_healthy": False,
            "errors": []
        }

        try:
            # Check classifier
            classifier_health = await self.classifier.health_check()
            health_status["classifier_healthy"] = classifier_health.get("classifier_ready", False)
            if not health_status["classifier_healthy"]:
                health_status["errors"].extend(classifier_health.get("errors", []))
        except Exception as e:
            health_status["errors"].append(f"Classifier health check failed: {e}")

        try:
            # Check storage service
            storage_health = await self.storage_service.health_check()
            health_status["storage_healthy"] = storage_health.get("storage_service_healthy", False)
            if not health_status["storage_healthy"]:
                health_status["errors"].extend(storage_health.get("errors", []))
        except Exception as e:
            health_status["errors"].append(f"Storage health check failed: {e}")

        try:
            # Check embedding service
            await self.embedding_service.generate_embedding("test")
            health_status["embedding_service_healthy"] = True
        except Exception as e:
            health_status["errors"].append(f"Embedding service failed: {e}")

        # Overall health
        health_status["pipeline_healthy"] = (
            health_status["classifier_healthy"] and
            health_status["storage_healthy"] and
            health_status["embedding_service_healthy"]
        )

        return health_status

    async def close(self) -> None:
        """Close the pipeline and cleanup resources."""
        try:
            await self.storage_service.close()
            await self.embedding_service.close()
            logger.info("MaterialIngestionPipeline closed successfully")
        except Exception as e:
            logger.error(f"Error closing pipeline: {e}")
            raise


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def process_materials_pipeline(
    materials: list[str],
    genre_context: str = "unknown",
    processing_mode: str = "pipeline",
    batch_size: int = 20,
    progress_callback: Optional[Callable[[PipelineProgressUpdate], None]] = None
) -> MaterialIngestionResponse:
    """
    Convenience function for processing materials with the pipeline.

    Args:
        materials: List of raw material content
        genre_context: Genre context for classification
        processing_mode: Processing mode (pipeline/agent/hybrid)
        batch_size: Batch size for processing
        progress_callback: Optional progress callback

    Returns:
        Material ingestion response
    """
    pipeline = MaterialIngestionPipeline()

    try:
        request = MaterialIngestionRequest(
            materials=materials,
            genre_context=genre_context,
            processing_mode=processing_mode,
            batch_size=batch_size
        )

        return await pipeline.process_materials(request, progress_callback)

    finally:
        await pipeline.close()


async def process_materials_with_cost_optimization(
    materials: list[str],
    target_cost_per_material: float = 0.005,
    genre_context: str = "unknown"
) -> MaterialIngestionResponse:
    """
    Process materials with cost optimization by selecting the best mode.

    Args:
        materials: List of raw material content
        target_cost_per_material: Target cost per material
        genre_context: Genre context for classification

    Returns:
        Material ingestion response
    """
    # Choose processing mode based on material count and cost target
    if len(materials) > 50 and target_cost_per_material < 0.01:
        processing_mode = "pipeline"
    elif len(materials) < 10:
        processing_mode = "agent"
    else:
        processing_mode = "hybrid"

    pipeline = MaterialIngestionPipeline()

    try:
        request = MaterialIngestionRequest(
            materials=materials,
            genre_context=genre_context,
            processing_mode=processing_mode,
            batch_size=min(50, len(materials))
        )

        return await pipeline.process_materials(request)

    finally:
        await pipeline.close()


if __name__ == "__main__":
    async def main():
        """Example usage of the material ingestion pipeline."""
        sample_materials = [
            "Character: Ren, a young geomancer with the ability to manipulate stone and earth.",
            "Setting: The Ashfall Wastes, a desolate region covered in volcanic ash.",
            "System: The Deep Current, an ancient magical force that flows through the world.",
            "Plot: The prophecy speaks of a chosen one who will unite the fractured kingdoms."
        ]

        def progress_callback(update: PipelineProgressUpdate):
            print(f"Progress: {update.progress_percentage:.1f}% - {update.message}")

        # Test pipeline mode
        response = await process_materials_pipeline(
            materials=sample_materials,
            genre_context="fantasy",
            processing_mode="pipeline",
            progress_callback=progress_callback
        )

        print("\nPipeline Results:")
        print(f"Materials processed: {response.materials_processed}")
        print(f"Processing time: {response.processing_time:.2f}s")
        print(f"Cost estimate: ${response.cost_estimate:.4f}")
        print(f"Average confidence: {response.average_confidence:.2f}")
        print(f"Category distribution: {response.category_distribution}")

    import asyncio
    asyncio.run(main())
