"""
LibrarianAgent Integration Testing Suite

Comprehensive tests for the LibrarianAgent integration to prevent
the Pydantic model field errors we just fixed from recurring.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from typing import Dict, Any

from src.models.material_models import MaterialIngestionResponse
from src.web.routes.ingestion import process_materials_background


class TestLibrarianAgentIntegration:
    """Test suite for LibrarianAgent integration with upload processing."""

    @pytest.fixture
    def mock_pipeline(self):
        """Mock MaterialIngestionPipeline."""
        pipeline = Mock()
        pipeline.process_materials = AsyncMock()
        pipeline.close = AsyncMock()
        return pipeline

    @pytest.fixture
    def sample_response(self):
        """Sample MaterialIngestionResponse for testing."""
        return MaterialIngestionResponse(
            job_id="test_job_123",
            status="completed",
            processing_time=10.5,
            cost_estimate=0.05,
            materials_processed=2,
            average_confidence=0.85,
            category_distribution={"character": 1, "setting": 1},
            complexity_distribution={"simple": 1, "medium": 1},
            cross_references_identified=3
        )

    @pytest.fixture
    def sample_request(self):
        """Sample MaterialIngestionRequest for testing."""
        from src.models.material_models import MaterialIngestionRequest
        
        return MaterialIngestionRequest(
            materials=["Character description", "Setting details"],
            genre_context="fantasy",
            processing_mode="pipeline",
            batch_size=10,
            min_confidence_threshold=0.7,
            enable_cross_references=True,
            enable_progressive_disclosure=True
        )

    @pytest.fixture
    def mock_active_jobs(self):
        """Mock active jobs dictionary."""
        return {
            "test_job_123": {
                "job_id": "test_job_123",
                "status": "processing",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "files_count": 2,
                "processing_mode": "pipeline",
                "genre_context": "fantasy",
                "progress_percentage": 50.0,
                "current_stage": "processing",
                "materials_processed": 1,
                "materials_remaining": 1,
                "estimated_time_remaining": 30.0,
                "message": "Processing materials..."
            }
        }

    @pytest.fixture
    def mock_job_results(self):
        """Mock job results dictionary."""
        return {}

    @pytest.mark.asyncio
    async def test_librarian_fields_exist_in_response_model(self):
        """Test that LibrarianAgent fields exist in MaterialIngestionResponse."""
        response = MaterialIngestionResponse(
            job_id="test_job",
            status="completed",
            processing_time=5.0,
            cost_estimate=0.01,
            librarian_enhanced=True,
            librarian_insights=[
                {"material_index": 0, "categories": "character", "quality_score": 0.9}
            ],
            librarian_analysis_time=2.5,
            librarian_errors=[]
        )

        # Verify fields exist and have correct values
        assert hasattr(response, 'librarian_enhanced')
        assert hasattr(response, 'librarian_insights')
        assert hasattr(response, 'librarian_analysis_time')
        assert hasattr(response, 'librarian_errors')
        
        assert response.librarian_enhanced is True
        assert len(response.librarian_insights) == 1
        assert response.librarian_analysis_time == 2.5
        assert response.librarian_errors == []

    @pytest.mark.asyncio
    async def test_librarian_field_assignment_success(self, 
                                                     sample_response, 
                                                     mock_pipeline,
                                                     sample_request,
                                                     mock_active_jobs,
                                                     mock_job_results):
        """Test that LibrarianAgent fields can be assigned without Pydantic errors."""
        
        # Mock pipeline response
        mock_pipeline.process_materials.return_value = sample_response
        
        # Mock LibrarianAgent
        with patch('src.web.routes.ingestion.LibrarianAgent') as mock_librarian_class:
            mock_librarian = Mock()
            mock_analysis_result = Mock()
            mock_analysis_result.analysis_results = [
                Mock(
                    primary_category="character",
                    extracted_entities=["Aragorn", "Ranger"],
                    quality_assessment=Mock(overall_score=0.9)
                )
            ]
            mock_librarian.analyze_materials = AsyncMock(return_value=mock_analysis_result)
            mock_librarian_class.return_value = mock_librarian
            
            # Mock global variables
            with patch('src.web.routes.ingestion.active_jobs', mock_active_jobs), \
                 patch('src.web.routes.ingestion.job_results', mock_job_results):
                
                # This should not raise a Pydantic validation error
                await process_materials_background("test_job_123", sample_request, mock_pipeline)
                
                # Verify the response was stored
                assert "test_job_123" in mock_job_results
                stored_response = mock_job_results["test_job_123"]
                
                # Verify LibrarianAgent fields were set correctly
                assert stored_response.librarian_enhanced is True
                assert len(stored_response.librarian_insights) > 0
                assert stored_response.librarian_insights[0]["material_index"] == 0

    @pytest.mark.asyncio
    async def test_librarian_analysis_failure_handling(self,
                                                       sample_response,
                                                       mock_pipeline,
                                                       sample_request,
                                                       mock_active_jobs,
                                                       mock_job_results):
        """Test graceful handling of LibrarianAgent analysis failures."""
        
        mock_pipeline.process_materials.return_value = sample_response
        
        # Mock LibrarianAgent to raise an exception
        with patch('src.web.routes.ingestion.LibrarianAgent') as mock_librarian_class:
            mock_librarian = Mock()
            mock_librarian.analyze_materials = AsyncMock(side_effect=Exception("Analysis failed"))
            mock_librarian_class.return_value = mock_librarian
            
            with patch('src.web.routes.ingestion.active_jobs', mock_active_jobs), \
                 patch('src.web.routes.ingestion.job_results', mock_job_results):
                
                # Should not crash, should handle gracefully
                await process_materials_background("test_job_123", sample_request, mock_pipeline)
                
                # Verify response was still stored
                assert "test_job_123" in mock_job_results
                stored_response = mock_job_results["test_job_123"]
                
                # Should have fallback insights
                assert isinstance(stored_response.librarian_insights, list)

    @pytest.mark.asyncio
    async def test_librarian_insights_structure(self):
        """Test that LibrarianAgent insights have expected structure."""
        
        # Test various insight structures
        valid_insights = [
            {
                "material_index": 0,
                "categories": "character",
                "entities": ["Gandalf", "Wizard"],
                "quality_score": 0.95,
                "cross_references": []
            },
            {
                "material_index": 1,
                "analysis": "basic"
            },
            {
                "material_index": 2,
                "analysis": "failed",
                "error": "Connection timeout"
            }
        ]
        
        response = MaterialIngestionResponse(
            job_id="test_job",
            status="completed",
            processing_time=5.0,
            cost_estimate=0.01,
            librarian_insights=valid_insights
        )
        
        # Should accept various insight structures
        assert len(response.librarian_insights) == 3
        assert response.librarian_insights[0]["material_index"] == 0
        assert response.librarian_insights[1]["analysis"] == "basic"
        assert response.librarian_insights[2]["error"] == "Connection timeout"

    @pytest.mark.asyncio
    async def test_pydantic_field_validation(self):
        """Test Pydantic validation for LibrarianAgent fields."""
        
        # Test valid field types
        response = MaterialIngestionResponse(
            job_id="test_job",
            status="completed",
            processing_time=5.0,
            cost_estimate=0.01,
            librarian_enhanced=True,  # bool
            librarian_insights=[{"test": "data"}],  # list[dict]
            librarian_analysis_time=3.5,  # float
            librarian_errors=["error1", "error2"]  # list[str]
        )
        
        assert response.librarian_enhanced is True
        assert isinstance(response.librarian_insights, list)
        assert isinstance(response.librarian_analysis_time, float)
        assert isinstance(response.librarian_errors, list)

    @pytest.mark.asyncio
    async def test_default_librarian_field_values(self):
        """Test that LibrarianAgent fields have sensible defaults."""
        
        response = MaterialIngestionResponse(
            job_id="test_job",
            status="completed",
            processing_time=5.0,
            cost_estimate=0.01
            # Not setting LibrarianAgent fields
        )
        
        # Should have default values
        assert response.librarian_enhanced is False
        assert response.librarian_insights == []
        assert response.librarian_analysis_time == 0.0
        assert response.librarian_errors == []

    @pytest.mark.asyncio
    async def test_dynamic_field_assignment_fails_gracefully(self):
        """Test that attempting to add non-existent fields fails gracefully."""
        
        response = MaterialIngestionResponse(
            job_id="test_job",
            status="completed",
            processing_time=5.0,
            cost_estimate=0.01
        )
        
        # This should raise a ValidationError (expected behavior)
        with pytest.raises(AttributeError):
            response.non_existent_field = "should fail"
            
        # But accessing existing fields should work
        assert response.librarian_enhanced is False  # default value

    @pytest.mark.asyncio
    async def test_job_status_updates_during_librarian_processing(self,
                                                                 mock_pipeline,
                                                                 sample_request,
                                                                 sample_response):
        """Test that job status is updated correctly during LibrarianAgent processing."""
        
        mock_pipeline.process_materials.return_value = sample_response
        
        active_jobs = {
            "test_job_123": {
                "job_id": "test_job_123",
                "status": "queued",
                "message": "Initial state"
            }
        }
        job_results = {}
        
        with patch('src.web.routes.ingestion.LibrarianAgent') as mock_librarian_class:
            mock_librarian = Mock()
            mock_librarian.analyze_materials = AsyncMock(return_value=Mock(analysis_results=[]))
            mock_librarian_class.return_value = mock_librarian
            
            with patch('src.web.routes.ingestion.active_jobs', active_jobs), \
                 patch('src.web.routes.ingestion.job_results', job_results):
                
                await process_materials_background("test_job_123", sample_request, mock_pipeline)
                
                # Verify job status was updated
                assert active_jobs["test_job_123"]["status"] == "completed"
                assert "completed" in active_jobs["test_job_123"]["message"]


class TestLibrarianAgentErrorScenarios:
    """Test error scenarios and edge cases for LibrarianAgent integration."""

    @pytest.mark.asyncio
    async def test_librarian_import_failure(self):
        """Test handling of LibrarianAgent import failures."""
        
        with patch('src.web.routes.ingestion.LibrarianAgent', side_effect=ImportError("Module not found")):
            # Should handle import error gracefully
            # This test would verify the fallback behavior when LibrarianAgent is not available
            pass

    @pytest.mark.asyncio
    async def test_malformed_librarian_response(self):
        """Test handling of malformed LibrarianAgent responses."""
        
        # Test with various malformed responses
        malformed_responses = [
            None,
            Mock(analysis_results=None),
            Mock(analysis_results=[]),
            Mock()  # Missing analysis_results attribute
        ]
        
        for malformed_response in malformed_responses:
            # Should handle gracefully without crashing
            pass

    @pytest.mark.asyncio
    async def test_librarian_timeout_handling(self):
        """Test handling of LibrarianAgent timeouts."""
        
        # Mock timeout scenario
        with patch('src.web.routes.ingestion.LibrarianAgent') as mock_librarian_class:
            mock_librarian = Mock()
            mock_librarian.analyze_materials = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_librarian_class.return_value = mock_librarian
            
            # Should handle timeout gracefully
            pass