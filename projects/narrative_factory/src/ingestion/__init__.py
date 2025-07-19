"""
Material ingestion pipeline for the Narrative Factory.

This module provides comprehensive material ingestion with LLM-based classification,
embedding generation, storage, and both lightweight pipeline and comprehensive
agent processing modes.
"""

from .classifier import MaterialClassifier
from .pipeline import (
    MaterialIngestionPipeline,
    PipelineConfig,
    PipelineMetrics,
    PipelineProgressUpdate,
    process_materials_pipeline,
    process_materials_with_cost_optimization,
)
from .storage import (
    BulkStorageRequest,
    BulkStorageResponse,
    MaterialStorageConfig,
    MaterialStorage,
    TemporalGateFilter,
)


__all__ = [
    "MaterialClassifier",
    "MaterialIngestionPipeline",
    "PipelineConfig",
    "PipelineMetrics",
    "PipelineProgressUpdate",
    "process_materials_pipeline",
    "process_materials_with_cost_optimization",
    "MaterialStorage",
    "BulkStorageRequest",
    "BulkStorageResponse",
    "TemporalGateFilter",
    "MaterialStorageConfig",
]
