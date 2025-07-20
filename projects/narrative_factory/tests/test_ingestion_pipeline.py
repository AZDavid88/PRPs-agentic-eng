"""Tests for ingestion pipeline module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.ingestion.pipeline import (
    IngestionPipeline,
    PipelineSettings,
    IngestionResult,
    DocumentProcessor,
    MetadataExtractor
)
from src.models.material_models import MaterialMetadata, SourceMaterial


@pytest.fixture
def pipeline_settings():
    """Pipeline settings fixture."""
    return PipelineSettings(
        batch_size=10,
        max_workers=4,
        chunk_size=1000,
        chunk_overlap=200,
        enable_classification=True,
        enable_validation=True
    )


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "content": "This is a sample document about fantasy adventures. The hero embarks on a quest to find the magical artifact that will save the kingdom.",
        "metadata": {
            "title": "Sample Fantasy Story",
            "author": "Test Author",
            "source": "test_source",
            "file_path": "/path/to/document.txt"
        }
    }


@pytest.fixture
def mock_classifier():
    """Mock material classifier."""
    classifier = Mock()
    classifier.classify = AsyncMock(return_value={
        "primary_category": "narrative",
        "secondary_categories": ["fantasy", "adventure"],
        "genre": "fantasy",
        "content_type": "story",
        "confidence": 0.95
    })
    return classifier


@pytest.fixture
def mock_storage():
    """Mock storage service."""
    storage = Mock()
    storage.store_material = AsyncMock(return_value="material_123")
    storage.store_chunks = AsyncMock(return_value=["chunk_1", "chunk_2"])
    return storage


class TestPipelineSettings:
    """Test cases for PipelineSettings."""

    def test_pipeline_settings_defaults(self):
        """Test PipelineSettings with default values."""
        settings = PipelineSettings()
        assert settings.batch_size == 20
        assert settings.max_workers == 4
        assert settings.chunk_size == 1000
        assert settings.chunk_overlap == 200
        assert settings.enable_classification is True

    def test_pipeline_settings_custom_values(self):
        """Test PipelineSettings with custom values."""
        settings = PipelineSettings(
            batch_size=50,
            max_workers=8,
            chunk_size=2000,
            chunk_overlap=400,
            enable_classification=False,
            enable_validation=False
        )
        assert settings.batch_size == 50
        assert settings.max_workers == 8
        assert settings.chunk_size == 2000
        assert settings.chunk_overlap == 400
        assert settings.enable_classification is False
        assert settings.enable_validation is False


class TestDocumentProcessor:
    """Test cases for DocumentProcessor."""

    def test_document_processor_init(self, pipeline_settings):
        """Test DocumentProcessor initialization."""
        processor = DocumentProcessor(pipeline_settings)
        assert processor.settings == pipeline_settings

    @pytest.mark.asyncio
    async def test_process_text(self, pipeline_settings):
        """Test text processing."""
        processor = DocumentProcessor(pipeline_settings)
        
        text = "This is a sample text for processing. " * 50  # Long text for chunking
        
        chunks = await processor.process_text(text)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) <= pipeline_settings.chunk_size for chunk in chunks)

    @pytest.mark.asyncio
    async def test_extract_metadata(self, pipeline_settings, sample_document):
        """Test metadata extraction."""
        processor = DocumentProcessor(pipeline_settings)
        
        metadata = await processor.extract_metadata(sample_document)
        
        assert isinstance(metadata, dict)
        assert "title" in metadata
        assert "author" in metadata
        assert "source" in metadata

    @pytest.mark.asyncio
    async def test_validate_document(self, pipeline_settings, sample_document):
        """Test document validation."""
        processor = DocumentProcessor(pipeline_settings)
        
        is_valid = await processor.validate_document(sample_document)
        assert is_valid is True
        
        # Test invalid document
        invalid_doc = {"content": ""}  # Empty content
        is_valid = await processor.validate_document(invalid_doc)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_preprocess_content(self, pipeline_settings):
        """Test content preprocessing."""
        processor = DocumentProcessor(pipeline_settings)
        
        raw_content = "  This is MESSY content with\n\n\nextra whitespace  \t"
        
        processed_content = await processor.preprocess_content(raw_content)
        
        assert processed_content.strip() == "This is MESSY content with extra whitespace"
        assert "\n\n\n" not in processed_content
        assert processed_content == processed_content.strip()


class TestMetadataExtractor:
    """Test cases for MetadataExtractor."""

    def test_metadata_extractor_init(self):
        """Test MetadataExtractor initialization."""
        extractor = MetadataExtractor()
        assert extractor is not None

    @pytest.mark.asyncio
    async def test_extract_from_text(self, sample_document):
        """Test metadata extraction from text content."""
        extractor = MetadataExtractor()
        
        metadata = await extractor.extract_from_text(sample_document["content"])
        
        assert isinstance(metadata, dict)
        assert "content_type" in metadata
        assert "estimated_reading_time" in metadata
        assert "word_count" in metadata

    @pytest.mark.asyncio
    async def test_extract_from_file_path(self):
        """Test metadata extraction from file path."""
        extractor = MetadataExtractor()
        
        file_path = Path("/path/to/fantasy_story_2023.txt")
        metadata = await extractor.extract_from_file_path(file_path)
        
        assert metadata["file_name"] == "fantasy_story_2023.txt"
        assert metadata["file_extension"] == ".txt"
        assert "file_size" in metadata

    @pytest.mark.asyncio
    async def test_detect_language(self):
        """Test language detection."""
        extractor = MetadataExtractor()
        
        english_text = "This is an English text sample."
        language = await extractor.detect_language(english_text)
        assert language == "en"

    @pytest.mark.asyncio
    async def test_estimate_reading_time(self):
        """Test reading time estimation."""
        extractor = MetadataExtractor()
        
        text = "This is a sample text. " * 200  # ~400 words
        reading_time = await extractor.estimate_reading_time(text)
        
        assert reading_time > 0
        assert isinstance(reading_time, (int, float))


class TestIngestionPipeline:
    """Test cases for IngestionPipeline."""

    def test_ingestion_pipeline_init(self, pipeline_settings, mock_classifier, mock_storage):
        """Test IngestionPipeline initialization."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        assert pipeline.settings == pipeline_settings
        assert pipeline.classifier == mock_classifier
        assert pipeline.storage == mock_storage

    @pytest.mark.asyncio
    async def test_process_single_document(self, pipeline_settings, mock_classifier, mock_storage, sample_document):
        """Test processing a single document."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        result = await pipeline.process_document(sample_document)
        
        assert isinstance(result, IngestionResult)
        assert result.success is True
        assert result.material_id is not None
        assert len(result.chunk_ids) > 0
        
        # Verify classifier was called
        mock_classifier.classify.assert_called_once()
        
        # Verify storage was called
        mock_storage.store_material.assert_called_once()
        mock_storage.store_chunks.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_batch(self, pipeline_settings, mock_classifier, mock_storage):
        """Test processing multiple documents in batch."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        documents = [
            {"content": f"Document {i} content", "metadata": {"title": f"Doc {i}"}}
            for i in range(5)
        ]
        
        results = await pipeline.process_batch(documents)
        
        assert len(results) == 5
        assert all(isinstance(r, IngestionResult) for r in results)
        assert all(r.success for r in results)
        
        # Verify all documents were processed
        assert mock_classifier.classify.call_count == 5
        assert mock_storage.store_material.call_count == 5

    @pytest.mark.asyncio
    async def test_process_document_error_handling(self, pipeline_settings, mock_storage):
        """Test error handling during document processing."""
        # Mock classifier that raises an exception
        mock_classifier = Mock()
        mock_classifier.classify = AsyncMock(side_effect=Exception("Classification failed"))
        
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        document = {"content": "Test content", "metadata": {"title": "Test"}}
        result = await pipeline.process_document(document)
        
        assert result.success is False
        assert "Classification failed" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_pipeline_requirements(self, pipeline_settings, mock_classifier, mock_storage):
        """Test pipeline requirements validation."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        # Test with valid document
        valid_doc = {
            "content": "Valid content with sufficient length for processing.",
            "metadata": {"title": "Valid Document"}
        }
        
        is_valid = await pipeline.validate_requirements(valid_doc)
        assert is_valid is True
        
        # Test with invalid document
        invalid_doc = {"content": ""}  # Empty content
        
        is_valid = await pipeline.validate_requirements(invalid_doc)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_pipeline_stats(self, pipeline_settings, mock_classifier, mock_storage):
        """Test getting pipeline statistics."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        # Process some documents
        documents = [
            {"content": f"Document {i}", "metadata": {"title": f"Doc {i}"}}
            for i in range(3)
        ]
        
        await pipeline.process_batch(documents)
        
        stats = pipeline.get_stats()
        
        assert stats["total_processed"] == 3
        assert stats["success_count"] == 3
        assert stats["error_count"] == 0
        assert "processing_time" in stats

    @pytest.mark.asyncio
    async def test_pipeline_with_classification_disabled(self, mock_storage):
        """Test pipeline with classification disabled."""
        settings = PipelineSettings(enable_classification=False)
        pipeline = IngestionPipeline(
            settings=settings,
            classifier=None,  # No classifier needed
            storage=mock_storage
        )
        
        document = {"content": "Test content", "metadata": {"title": "Test"}}
        result = await pipeline.process_document(document)
        
        assert result.success is True
        # Should still store material even without classification
        mock_storage.store_material.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_chunking_strategy(self, pipeline_settings, mock_classifier, mock_storage):
        """Test different chunking strategies."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        # Long document that will require chunking
        long_content = "This is a sentence. " * 100  # 500 sentences
        document = {
            "content": long_content,
            "metadata": {"title": "Long Document"}
        }
        
        result = await pipeline.process_document(document)
        
        assert result.success is True
        assert len(result.chunk_ids) > 1  # Should be split into multiple chunks

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, pipeline_settings, mock_classifier, mock_storage):
        """Test concurrent document processing."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        # Create many documents for concurrent processing
        documents = [
            {"content": f"Document {i} with unique content", "metadata": {"title": f"Doc {i}"}}
            for i in range(20)
        ]
        
        # Process with limited workers
        results = await pipeline.process_batch(documents, max_workers=4)
        
        assert len(results) == 20
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_pipeline_memory_management(self, pipeline_settings, mock_classifier, mock_storage):
        """Test pipeline memory management with large batches."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        # Simulate large documents
        large_documents = [
            {
                "content": "Large content " * 1000,  # Large document
                "metadata": {"title": f"Large Doc {i}"}
            }
            for i in range(10)
        ]
        
        # Should handle large batch without memory issues
        results = await pipeline.process_batch(large_documents)
        
        assert len(results) == 10
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_pipeline_progress_tracking(self, pipeline_settings, mock_classifier, mock_storage):
        """Test pipeline progress tracking."""
        pipeline = IngestionPipeline(
            settings=pipeline_settings,
            classifier=mock_classifier,
            storage=mock_storage
        )
        
        progress_updates = []
        
        def progress_callback(processed, total):
            progress_updates.append((processed, total))
        
        documents = [
            {"content": f"Doc {i}", "metadata": {"title": f"Doc {i}"}}
            for i in range(5)
        ]
        
        await pipeline.process_batch(documents, progress_callback=progress_callback)
        
        # Should have received progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1] == (5, 5)  # Final update should be (total, total)


class TestIngestionResult:
    """Test cases for IngestionResult."""

    def test_ingestion_result_success(self):
        """Test successful IngestionResult."""
        result = IngestionResult(
            success=True,
            material_id="material_123",
            chunk_ids=["chunk_1", "chunk_2"],
            processing_time=1.5,
            metadata={"category": "narrative"}
        )
        
        assert result.success is True
        assert result.material_id == "material_123"
        assert len(result.chunk_ids) == 2
        assert result.processing_time == 1.5
        assert result.error_message is None

    def test_ingestion_result_failure(self):
        """Test failed IngestionResult."""
        result = IngestionResult(
            success=False,
            error_message="Processing failed",
            processing_time=0.1
        )
        
        assert result.success is False
        assert result.error_message == "Processing failed"
        assert result.material_id is None
        assert result.chunk_ids is None

    def test_ingestion_result_serialization(self):
        """Test IngestionResult serialization."""
        result = IngestionResult(
            success=True,
            material_id="material_123",
            chunk_ids=["chunk_1"],
            processing_time=1.0
        )
        
        result_dict = result.model_dump()
        
        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["material_id"] == "material_123"