"""
Test suite for LibrarianAgent Prefect workflow integration.

Tests the Prefect tasks and flows for LibrarianAgent material analysis,
enhanced material ingestion, and JobStore integration.
"""

import asyncio
import pytest
import time
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from src.workflows.generation import (
    librarian_analysis_task,
    enhanced_material_ingestion_task,
    librarian_analysis_flow,
    enhanced_material_ingestion_flow
)
from src.models.material_models import MaterialClassification
from src.models.librarian_models import MaterialAnalysisResponse, ProcessingMetrics
from src.workflows.jobs import JobStore


class TestLibrarianAnalysisTask:
    """Test the librarian_analysis_task Prefect task."""
    
    @pytest.fixture
    def sample_materials(self) -> List[MaterialClassification]:
        """Create sample materials for testing."""
        return [
            MaterialClassification(
                id="char_001",
                content="Elena is a skilled warrior with a mysterious past.",
                category="character",
                confidence_score=0.95
            ),
            MaterialClassification(
                id="setting_001",
                content="The ancient fortress guards the mountain pass.",
                category="setting", 
                confidence_score=0.88
            )
        ]
    
    @pytest.fixture
    def mock_job_store(self):
        """Create mock JobStore for testing."""
        mock_store = MagicMock(spec=JobStore)
        mock_store.create_job.return_value = "test_job_123"
        mock_store.update_job_as_pending.return_value = True
        return mock_store
    
    @pytest.fixture
    def mock_librarian_response(self):
        """Create mock LibrarianAgent response."""
        return MaterialAnalysisResponse(
            request_id="analysis_123",
            results=[],
            successful_count=2,
            failed_count=0,
            processing_time=5.5,
            cross_references_generated=1,
            quality_issues_found=0,
            metrics=ProcessingMetrics()
        )
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_task_dry_run(self, sample_materials, mock_job_store):
        """Test librarian_analysis_task in dry run mode."""
        with patch('src.workflows.generation.job_store', mock_job_store):
            job_id = await librarian_analysis_task(
                materials=sample_materials,
                dry_run=True
            )
            
            assert job_id == "test_job_123"
            mock_job_store.create_job.assert_called_once()
            mock_job_store.update_job_as_pending.assert_called_once()
            
            # Verify dry run output structure
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            dry_run_output = call_args[1]
            assert dry_run_output["dry_run"] is True
            assert "estimated_processing_time" in dry_run_output
            assert "estimated_embedding_cost" in dry_run_output
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_task_success(self, sample_materials, mock_job_store, mock_librarian_response):
        """Test successful librarian_analysis_task execution."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation._get_memory_service') as mock_memory:
            
            # Setup mocks
            mock_agent_instance = AsyncMock()
            MockAgent.return_value = mock_agent_instance
            mock_agent_instance.analyze_materials.return_value = mock_librarian_response
            
            job_id = await librarian_analysis_task(
                materials=sample_materials,
                analysis_depth="comprehensive",
                enable_cross_references=True
            )
            
            assert job_id == "test_job_123"
            mock_job_store.create_job.assert_called_once()
            mock_job_store.update_job_as_pending.assert_called_once()
            mock_agent_instance.analyze_materials.assert_called_once()
            mock_agent_instance.close.assert_called_once()
            
            # Verify output structure
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            output = call_args[1]
            assert "analysis_response" in output
            assert "summary" in output
            assert output["summary"]["materials_processed"] == 2
            assert output["summary"]["success_rate"] == 100.0
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_task_validation_errors(self, mock_job_store):
        """Test librarian_analysis_task input validation."""
        with patch('src.workflows.generation.job_store', mock_job_store):
            # Empty materials list
            with pytest.raises(ValueError, match="Materials list cannot be empty"):
                await librarian_analysis_task(materials=[])
            
            # Invalid concurrent limit
            sample_material = MaterialClassification(
                id="test", content="test", category="test", confidence_score=0.8
            )
            with pytest.raises(ValueError, match="Concurrent limit must be between 1 and 20"):
                await librarian_analysis_task(materials=[sample_material], concurrent_limit=0)
            
            with pytest.raises(ValueError, match="Concurrent limit must be between 1 and 20"):
                await librarian_analysis_task(materials=[sample_material], concurrent_limit=25)
            
            # Invalid analysis depth
            with pytest.raises(ValueError, match="Analysis depth must be"):
                await librarian_analysis_task(materials=[sample_material], analysis_depth="invalid")
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_task_timeout(self, sample_materials, mock_job_store):
        """Test librarian_analysis_task timeout handling."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation._get_memory_service'):
            
            # Setup mock to timeout
            mock_agent_instance = AsyncMock()
            MockAgent.return_value = mock_agent_instance
            
            async def slow_analysis(*args, **kwargs):
                await asyncio.sleep(2)  # Longer than timeout
                return mock_librarian_response
            
            mock_agent_instance.analyze_materials.side_effect = slow_analysis
            
            with pytest.raises(TimeoutError):
                await librarian_analysis_task(
                    materials=sample_materials,
                    timeout_minutes=0.01  # Very short timeout
                )
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_task_error_handling(self, sample_materials, mock_job_store):
        """Test librarian_analysis_task error handling."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation._get_memory_service'):
            
            # Setup mock to raise exception
            mock_agent_instance = AsyncMock()
            MockAgent.return_value = mock_agent_instance
            mock_agent_instance.analyze_materials.side_effect = Exception("Mock analysis failure")
            
            with pytest.raises(Exception, match="Mock analysis failure"):
                await librarian_analysis_task(materials=sample_materials)
            
            # Verify error was logged to JobStore
            mock_job_store.update_job_as_pending.assert_called()
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            error_output = call_args[1]
            assert error_output["status"] == "failed"
            assert "error" in error_output
            assert error_output["materials_processed"] == 0


class TestEnhancedMaterialIngestionTask:
    """Test the enhanced_material_ingestion_task Prefect task."""
    
    @pytest.fixture
    def sample_raw_materials(self) -> List[str]:
        """Create sample raw materials for testing."""
        return [
            "Elena is a skilled archer with piercing blue eyes.",
            "The ancient library towers above the misty valley.",
            "A mysterious plague spreads through the capital."
        ]
    
    @pytest.fixture
    def mock_job_store(self):
        """Create mock JobStore for testing."""
        mock_store = MagicMock(spec=JobStore)
        mock_store.create_job.return_value = "enhanced_job_456"
        mock_store.update_job_as_pending.return_value = True
        
        # Mock ingestion job result
        mock_ingestion_job = MagicMock()
        mock_ingestion_job.status = "pending_approval"
        mock_ingestion_job.output_payload = {
            "response": {
                "classifications": [
                    {
                        "id": "char_001",
                        "content": "Elena is a skilled archer with piercing blue eyes.",
                        "category": "character",
                        "confidence_score": 0.95
                    }
                ]
            }
        }
        mock_store.get_job.return_value = mock_ingestion_job
        
        return mock_store
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_task_disabled_librarian(self, sample_raw_materials, mock_job_store):
        """Test enhanced ingestion with LibrarianAgent disabled."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.material_ingestion_task') as mock_ingestion:
            
            mock_ingestion.return_value = "ingestion_job_123"
            
            job_id = await enhanced_material_ingestion_task(
                materials=sample_raw_materials,
                enable_librarian_analysis=False
            )
            
            assert job_id == "enhanced_job_456"
            mock_ingestion.assert_called_once()
            
            # Verify output structure
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            output = call_args[1]
            assert output["phase_1_ingestion"]["status"] == "completed"
            assert output["phase_2_librarian"]["status"] == "disabled"
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_task_enabled_librarian(self, sample_raw_materials, mock_job_store):
        """Test enhanced ingestion with LibrarianAgent enabled."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.material_ingestion_task') as mock_ingestion, \
             patch('src.workflows.generation.librarian_analysis_task') as mock_librarian:
            
            mock_ingestion.return_value = "ingestion_job_123"
            mock_librarian.return_value = "librarian_job_789"
            
            job_id = await enhanced_material_ingestion_task(
                materials=sample_raw_materials,
                enable_librarian_analysis=True,
                librarian_analysis_depth="comprehensive"
            )
            
            assert job_id == "enhanced_job_456"
            mock_ingestion.assert_called_once()
            mock_librarian.assert_called_once()
            
            # Verify LibrarianAgent was called with correct parameters
            librarian_call_args = mock_librarian.call_args
            assert librarian_call_args[1]["analysis_depth"] == "comprehensive"
            assert len(librarian_call_args[1]["materials"]) == 1
            
            # Verify output structure
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            output = call_args[1]
            assert output["phase_2_librarian"]["status"] == "completed"
            assert output["phase_2_librarian"]["job_id"] == "librarian_job_789"
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_task_no_classifications(self, sample_raw_materials, mock_job_store):
        """Test enhanced ingestion when no materials are classified."""
        # Mock empty classifications
        mock_job_store.get_job.return_value.output_payload = {
            "response": {"classifications": []}
        }
        
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.material_ingestion_task') as mock_ingestion:
            
            mock_ingestion.return_value = "ingestion_job_123"
            
            job_id = await enhanced_material_ingestion_task(
                materials=sample_raw_materials,
                enable_librarian_analysis=True
            )
            
            # Verify LibrarianAgent analysis was skipped
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            output = call_args[1]
            assert output["phase_2_librarian"]["status"] == "skipped"
            assert "No classified materials" in output["phase_2_librarian"]["reason"]
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_task_dry_run(self, sample_raw_materials, mock_job_store):
        """Test enhanced ingestion in dry run mode."""
        with patch('src.workflows.generation.job_store', mock_job_store), \
             patch('src.workflows.generation.material_ingestion_task') as mock_ingestion:
            
            mock_ingestion.return_value = "ingestion_job_123"
            
            job_id = await enhanced_material_ingestion_task(
                materials=sample_raw_materials,
                enable_librarian_analysis=True,
                dry_run=True
            )
            
            # Verify LibrarianAgent analysis was skipped for dry run
            call_args = mock_job_store.update_job_as_pending.call_args[0]
            output = call_args[1]
            assert output["phase_2_librarian"]["status"] == "skipped_dry_run"


class TestLibrarianAnalysisFlow:
    """Test the librarian_analysis_flow Prefect flow."""
    
    @pytest.fixture
    def sample_materials(self) -> List[MaterialClassification]:
        """Create sample materials for testing."""
        return [
            MaterialClassification(
                id="test_001",
                content="Test material content",
                category="character",
                confidence_score=0.9
            )
        ]
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_flow_success(self, sample_materials):
        """Test successful librarian analysis flow execution."""
        with patch('src.workflows.generation.librarian_analysis_task') as mock_task:
            mock_task.return_value = "analysis_job_123"
            
            job_id = await librarian_analysis_flow(
                materials=sample_materials,
                analysis_depth="comprehensive",
                enable_cross_references=True
            )
            
            assert job_id == "analysis_job_123"
            mock_task.assert_called_once()
            
            # Verify correct parameters were passed
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["analysis_depth"] == "comprehensive"
            assert call_kwargs["enable_cross_references"] is True
    
    @pytest.mark.asyncio
    async def test_librarian_analysis_flow_dry_run(self, sample_materials):
        """Test librarian analysis flow in dry run mode."""
        with patch('src.workflows.generation.librarian_analysis_task') as mock_task:
            mock_task.return_value = "dry_run_job_123"
            
            job_id = await librarian_analysis_flow(
                materials=sample_materials,
                dry_run=True
            )
            
            assert job_id == "dry_run_job_123"
            mock_task.assert_called_once_with(
                materials=sample_materials,
                analysis_depth="standard",
                enable_cross_references=True,
                enable_quality_assessment=True,
                concurrent_limit=10,
                story_id=None,
                dry_run=True
            )


class TestEnhancedMaterialIngestionFlow:
    """Test the enhanced_material_ingestion_flow Prefect flow."""
    
    @pytest.fixture
    def sample_raw_materials(self) -> List[str]:
        """Create sample raw materials for testing."""
        return [
            "Character description content",
            "Setting description content"
        ]
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_flow_success(self, sample_raw_materials):
        """Test successful enhanced material ingestion flow."""
        with patch('src.workflows.generation.enhanced_material_ingestion_task') as mock_task:
            mock_task.return_value = "enhanced_job_789"
            
            job_id = await enhanced_material_ingestion_flow(
                materials=sample_raw_materials,
                genre_context="fantasy",
                enable_librarian_analysis=True,
                librarian_analysis_depth="comprehensive"
            )
            
            assert job_id == "enhanced_job_789"
            mock_task.assert_called_once()
            
            # Verify correct parameters were passed
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["genre_context"] == "fantasy"
            assert call_kwargs["enable_librarian_analysis"] is True
            assert call_kwargs["librarian_analysis_depth"] == "comprehensive"
    
    @pytest.mark.asyncio
    async def test_enhanced_material_ingestion_flow_disabled_librarian(self, sample_raw_materials):
        """Test enhanced material ingestion flow with LibrarianAgent disabled."""
        with patch('src.workflows.generation.enhanced_material_ingestion_task') as mock_task:
            mock_task.return_value = "basic_job_456"
            
            job_id = await enhanced_material_ingestion_flow(
                materials=sample_raw_materials,
                enable_librarian_analysis=False
            )
            
            assert job_id == "basic_job_456"
            
            # Verify LibrarianAgent was disabled
            call_kwargs = mock_task.call_args[1]
            assert call_kwargs["enable_librarian_analysis"] is False


class TestWorkflowIntegration:
    """Test integration between LibrarianAgent workflows and existing systems."""
    
    @pytest.mark.asyncio
    async def test_workflow_jobstore_integration(self):
        """Test that LibrarianAgent workflows integrate properly with JobStore."""
        # This test would verify that:
        # 1. Jobs are created with correct agent names
        # 2. Job payloads match expected format
        # 3. Job status transitions work correctly
        # 4. Error handling preserves job state
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.create_job.return_value = "integration_test_job"
            
            sample_material = MaterialClassification(
                id="integration_test",
                content="Test content for integration",
                category="character",
                confidence_score=0.8
            )
            
            # Test that job creation uses correct agent name
            await librarian_analysis_task(materials=[sample_material], dry_run=True)
            
            create_call = mock_job_store.create_job.call_args
            assert create_call[1]["agent"] == "LibrarianAgent"
            assert "materials_count" in create_call[1]["input_payload"]
    
    @pytest.mark.asyncio
    async def test_workflow_memory_service_integration(self):
        """Test LibrarianAgent workflow integration with memory service."""
        with patch('src.workflows.generation._get_memory_service') as mock_memory_getter, \
             patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation.job_store') as mock_job_store:
            
            mock_memory_service = AsyncMock()
            mock_memory_getter.return_value = mock_memory_service
            
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent
            mock_agent.analyze_materials.return_value = MaterialAnalysisResponse(
                request_id="test",
                results=[],
                successful_count=1,
                failed_count=0,
                processing_time=1.0,
                cross_references_generated=0,
                quality_issues_found=0,
                metrics=ProcessingMetrics()
            )
            
            mock_job_store.create_job.return_value = "memory_test_job"
            
            sample_material = MaterialClassification(
                id="memory_test",
                content="Test memory integration",
                category="setting",
                confidence_score=0.9
            )
            
            await librarian_analysis_task(materials=[sample_material])
            
            # Verify LibrarianAgent was initialized with memory service
            MockAgent.assert_called_once_with(memory_service=mock_memory_service)


class TestPerformanceAndScaling:
    """Test performance characteristics and scaling behavior."""
    
    @pytest.mark.asyncio
    async def test_large_batch_processing(self):
        """Test LibrarianAgent workflow with large material batches."""
        # Create large batch of materials
        large_batch = [
            MaterialClassification(
                id=f"perf_test_{i}",
                content=f"Performance test material {i} with sufficient content for processing",
                category="character" if i % 2 == 0 else "setting",
                confidence_score=0.8 + (i % 3) * 0.1
            )
            for i in range(100)
        ]
        
        with patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation.job_store') as mock_job_store, \
             patch('src.workflows.generation._get_memory_service'):
            
            # Mock fast processing
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent
            mock_agent.analyze_materials.return_value = MaterialAnalysisResponse(
                request_id="perf_test",
                results=[],
                successful_count=100,
                failed_count=0,
                processing_time=5.0,  # Reasonable time for 100 materials
                cross_references_generated=50,
                quality_issues_found=5,
                metrics=ProcessingMetrics()
            )
            
            mock_job_store.create_job.return_value = "perf_test_job"
            
            start_time = time.time()
            
            job_id = await librarian_analysis_task(
                materials=large_batch,
                concurrent_limit=20,  # Max concurrency
                dry_run=False
            )
            
            execution_time = time.time() - start_time
            
            assert job_id == "perf_test_job"
            assert execution_time < 10.0  # Should complete reasonably quickly
            
            # Verify concurrent limit was passed correctly
            call_kwargs = mock_agent.analyze_materials.call_args[0][0]  # MaterialAnalysisRequest
            assert call_kwargs.concurrent_limit == 20
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self):
        """Test that memory usage is properly monitored during processing."""
        # This test would verify that ProcessingMetrics tracks memory usage
        # In a real environment, this would check actual memory consumption
        
        sample_materials = [
            MaterialClassification(
                id="memory_test",
                content="Large content " * 1000,  # Simulate large material
                category="character",
                confidence_score=0.9
            )
        ]
        
        with patch('src.workflows.generation.LibrarianAgent') as MockAgent, \
             patch('src.workflows.generation.job_store') as mock_job_store, \
             patch('src.workflows.generation._get_memory_service'):
            
            mock_metrics = ProcessingMetrics()
            mock_metrics.peak_memory_mb = 150.5  # Mock memory usage
            
            mock_agent = AsyncMock()
            MockAgent.return_value = mock_agent
            mock_agent.analyze_materials.return_value = MaterialAnalysisResponse(
                request_id="memory_test",
                results=[],
                successful_count=1,
                failed_count=0,
                processing_time=2.0,
                cross_references_generated=0,
                quality_issues_found=0,
                metrics=mock_metrics
            )
            
            mock_job_store.create_job.return_value = "memory_test_job"
            
            await librarian_analysis_task(materials=sample_materials)
            
            # Verify metrics were captured in job output
            update_call = mock_job_store.update_job_as_pending.call_args[0][1]
            assert update_call["metrics"]["peak_memory_mb"] == 150.5


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])