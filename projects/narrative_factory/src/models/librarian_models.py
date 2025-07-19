"""
LibrarianAgent data models for material analysis and cross-reference generation.

Provides comprehensive data structures for LibrarianAgent operations including
analysis requests, results, cross-references, and quality assessments.
"""

import time
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.material_models import MaterialClassification


class MaterialAnalysisRequest(BaseModel):
    """Request for LibrarianAgent material analysis."""

    classifications: list[MaterialClassification] = Field(
        description="Materials to analyze"
    )
    analysis_depth: str = Field(
        default="standard",
        description="Analysis depth: quick, standard, comprehensive"
    )
    enable_cross_references: bool = Field(
        default=True,
        description="Generate cross-references between materials"
    )
    enable_quality_assessment: bool = Field(
        default=True,
        description="Perform quality assessment on materials"
    )
    story_context: Optional[str] = Field(
        default=None,
        description="Optional story context for analysis"
    )
    concurrent_limit: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Maximum concurrent processing limit"
    )


class CrossReference(BaseModel):
    """Simple binary relationship between materials."""

    source_material_id: str = Field(description="ID of source material")
    target_material_id: str = Field(description="ID of target material")
    relationship_type: str = Field(
        description="Type of relationship: references, contradicts, expands, similar"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the relationship"
    )
    context: Optional[str] = Field(
        default=None,
        description="Context explaining the relationship"
    )


class QualityAssessment(BaseModel):
    """Simple pass/fail quality assessment."""

    is_acceptable: bool = Field(description="Whether material meets quality standards")
    quality_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall quality score"
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="List of quality issues identified"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )


class ProcessingMetrics(BaseModel):
    """Metrics for tracking LibrarianAgent processing performance."""

    start_time: float = Field(default_factory=time.time)
    materials_processed: int = Field(default=0)
    embeddings_generated: int = Field(default=0)
    memory_operations: int = Field(default=0)
    peak_memory_mb: float = Field(default=0.0)
    concurrent_operations: int = Field(default=0)

    def record_processing_step(self, step_type: str, count: int = 1) -> None:
        """Record processing step for monitoring."""
        if step_type == "material":
            self.materials_processed += count
        elif step_type == "embedding":
            self.embeddings_generated += count
        elif step_type == "memory":
            self.memory_operations += count

    def get_processing_time(self) -> float:
        """Get total processing time in seconds."""
        return time.time() - self.start_time


class MaterialAnalysisResult(BaseModel):
    """Result of LibrarianAgent analysis extending existing classification."""

    source_classification: MaterialClassification = Field(
        description="Original material classification"
    )
    vector_storage_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Qdrant storage metadata and information"
    )
    cross_references: list[CrossReference] = Field(
        default_factory=list,
        description="Cross-references to other materials"
    )
    quality_assessment: Optional[QualityAssessment] = Field(
        default=None,
        description="Quality assessment results"
    )
    specialized_analysis: dict[str, Any] = Field(
        default_factory=dict,
        description="Material-type specific analysis results"
    )
    processing_time: float = Field(
        default=0.0,
        description="Time taken to process this material"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Any errors encountered during processing"
    )


class MaterialAnalysisResponse(BaseModel):
    """Complete response from LibrarianAgent analysis."""

    request_id: str = Field(description="Unique identifier for this analysis request")
    results: list[MaterialAnalysisResult] = Field(
        default_factory=list,
        description="Analysis results for each material"
    )
    successful_count: int = Field(description="Number of successfully processed materials")
    failed_count: int = Field(description="Number of materials that failed processing")
    processing_time: float = Field(description="Total processing time in seconds")
    cross_references_generated: int = Field(description="Total cross-references generated")
    quality_issues_found: int = Field(description="Total quality issues identified")
    metrics: ProcessingMetrics = Field(description="Detailed processing metrics")

    def get_success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.successful_count + self.failed_count
        return (self.successful_count / total * 100) if total > 0 else 0.0


class LibrarianError(Exception):
    """Base exception for LibrarianAgent operations."""
    pass


class EmbeddingGenerationError(LibrarianError):
    """Failed to generate embeddings."""
    pass


class MemoryStorageError(LibrarianError):
    """Failed to store in memory service."""
    pass


class MaterialProcessingError(LibrarianError):
    """Failed to process material."""
    pass


class CrossReferenceGenerationError(LibrarianError):
    """Failed to generate cross-references."""
    pass


# Enhanced message types for agent communication
class MaterialAnalysisMessage(BaseModel):
    """Message for LibrarianAgent analysis requests."""

    message_type: str = "material_analysis_request"
    analysis_request: MaterialAnalysisRequest
    sender_id: str
    recipient_id: str = "librarian_agent"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MaterialAnalysisResponseMessage(BaseModel):
    """Message for LibrarianAgent analysis responses."""

    message_type: str = "material_analysis_response"
    analysis_response: MaterialAnalysisResponse
    sender_id: str = "librarian_agent"
    recipient_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
