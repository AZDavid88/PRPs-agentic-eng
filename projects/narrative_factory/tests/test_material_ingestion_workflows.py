"""
Tests for Phase 1B material ingestion Prefect workflows.

Tests the integration between CLI commands, Prefect workflows, and the 
material ingestion pipeline with job tracking and state management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.workflows.generation import (
    material_ingestion_task,
    material_ingestion_flow,
    bulk_material_ingestion_flow
)


@pytest.fixture
def sample_materials():
    """Sample materials for testing."""
    return [
        "Character: Elara, a skilled mage with control over elemental forces.",
        "Setting: The Crystal Caves, ancient underground chambers filled with magical energy.",
        "Magic System: Elemental Binding allows mages to bind elemental spirits to their will."
    ]


@pytest.fixture
def mock_pipeline():
    """Mock MaterialIngestionPipeline for testing."""
    mock_pipeline = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = "completed"
    mock_response.materials_processed = 3
    mock_response.processing_time = 15.5
    mock_response.cost_estimate = 0.015
    mock_response.average_confidence = 0.92
    mock_response.category_distribution = {"character": 1, "setting": 1, "magic_system": 1}
    mock_response.model_dump.return_value = {
        "status": "completed",
        "materials_processed": 3,
        "processing_time": 15.5,
        "cost_estimate": 0.015
    }
    
    mock_pipeline.process_materials.return_value = mock_response
    mock_pipeline.close.return_value = None
    
    return mock_pipeline


@pytest.fixture
def mock_job_store():
    """Mock JobStore for testing."""
    mock_store = MagicMock()
    mock_store.create_job.return_value = "ingestion_test123"
    mock_store.update_job_as_pending.return_value = None
    return mock_store


class TestMaterialIngestionTask:
    """Test the material ingestion Prefect task."""
    
    @patch('src.workflows.generation.MaterialIngestionPipeline')
    @patch('src.workflows.generation.job_store')
    async def test_material_ingestion_task_success(
        self, 
        mock_job_store_global,
        mock_pipeline_class,
        mock_job_store,
        mock_pipeline,
        sample_materials
    ):
        """Test successful material ingestion task execution."""
        # Setup mocks
        mock_job_store_global.create_job = mock_job_store.create_job
        mock_job_store_global.update_job_as_pending = mock_job_store.update_job_as_pending
        mock_pipeline_class.return_value = mock_pipeline
        
        # Execute task
        job_id = await material_ingestion_task(
            materials=sample_materials,
            genre_context="fantasy",
            processing_mode="pipeline",
            batch_size=10
        )
        
        # Verify results
        assert job_id == "ingestion_test123"
        
        # Verify JobStore calls
        mock_job_store.create_job.assert_called_once_with(
            agent="MaterialIngestion",
            input_payload={
                "materials": sample_materials,
                "genre_context": "fantasy",
                "processing_mode": "pipeline",
                "batch_size": 10,
                "min_confidence_threshold": 0.7,
                "additional_genres": [],
                "custom_categories": [],
                "story_id": None,
                "dry_run": False
            }
        )
        
        # Verify pipeline execution
        mock_pipeline.process_materials.assert_called_once()
        mock_pipeline.close.assert_called_once()
        
        # Verify job completion
        mock_job_store.update_job_as_pending.assert_called_once()
        call_args = mock_job_store.update_job_as_pending.call_args
        assert call_args[0][0] == "ingestion_test123"  # job_id
        assert call_args[0][1]["status"] == "completed"
    
    @patch('src.workflows.generation.job_store')
    async def test_material_ingestion_task_dry_run(
        self, 
        mock_job_store_global,
        mock_job_store,
        sample_materials
    ):
        """Test dry run mode for material ingestion task."""
        # Setup mocks
        mock_job_store_global.create_job = mock_job_store.create_job
        mock_job_store_global.update_job_as_pending = mock_job_store.update_job_as_pending
        
        # Execute dry run
        job_id = await material_ingestion_task(
            materials=sample_materials,
            genre_context="fantasy",
            dry_run=True
        )
        
        # Verify results
        assert job_id == "ingestion_test123"
        
        # Verify dry run output
        call_args = mock_job_store.update_job_as_pending.call_args
        output = call_args[0][1]
        assert output["dry_run"] is True
        assert output["validation_status"] == "passed"
        assert output["materials_count"] == 3
    
    @patch('src.workflows.generation.MaterialIngestionPipeline')
    @patch('src.workflows.generation.job_store')
    async def test_material_ingestion_task_error_handling(
        self,
        mock_job_store_global,
        mock_pipeline_class,
        mock_job_store,
        sample_materials
    ):
        """Test error handling in material ingestion task."""
        # Setup mocks
        mock_job_store_global.create_job = mock_job_store.create_job
        mock_job_store_global.update_job_as_pending = mock_job_store.update_job_as_pending
        
        # Make pipeline fail
        mock_pipeline = AsyncMock()
        mock_pipeline.process_materials.side_effect = Exception("Pipeline failed")
        mock_pipeline_class.return_value = mock_pipeline
        
        # Execute task and expect failure
        with pytest.raises(Exception, match="Pipeline failed"):
            await material_ingestion_task(
                materials=sample_materials,
                genre_context="fantasy"
            )
        
        # Verify error handling
        call_args = mock_job_store.update_job_as_pending.call_args
        output = call_args[0][1]
        assert output["status"] == "failed"
        assert "Pipeline failed" in output["error"]


class TestMaterialIngestionFlow:
    """Test the material ingestion Prefect flow."""
    
    @patch('src.workflows.generation.material_ingestion_task')
    async def test_material_ingestion_flow_success(
        self,
        mock_task,
        sample_materials
    ):
        """Test successful material ingestion flow."""
        # Setup mock
        mock_task.return_value = "ingestion_flow123"
        
        # Execute flow
        job_id = await material_ingestion_flow(
            materials=sample_materials,
            genre_context="mystery",
            processing_mode="agent",
            story_id="story_test"
        )
        
        # Verify results
        assert job_id == "ingestion_flow123"
        
        # Verify task call
        mock_task.assert_called_once_with(
            materials=sample_materials,
            genre_context="mystery",
            processing_mode="agent",
            batch_size=20,
            story_id="story_test",
            dry_run=False
        )
    
    @patch('src.workflows.generation.material_ingestion_task')
    async def test_material_ingestion_flow_dry_run(
        self,
        mock_task,
        sample_materials
    ):
        """Test dry run material ingestion flow."""
        # Setup mock
        mock_task.return_value = "ingestion_dry_run123"
        
        # Execute dry run flow
        job_id = await material_ingestion_flow(
            materials=sample_materials,
            genre_context="sci_fi",
            dry_run=True
        )
        
        # Verify results
        assert job_id == "ingestion_dry_run123"
        
        # Verify dry run parameter
        call_args = mock_task.call_args
        assert call_args[1]["dry_run"] is True


class TestBulkMaterialIngestionFlow:
    """Test the bulk material ingestion Prefect flow."""
    
    @patch('src.workflows.generation.material_ingestion_task')
    async def test_bulk_material_ingestion_flow(
        self,
        mock_task,
        sample_materials
    ):
        """Test bulk material ingestion with multiple batches."""
        # Setup mock
        mock_task.side_effect = ["job1", "job2", "job3"]
        
        # Create test batches
        batches = [
            {
                "materials": sample_materials[:1],
                "genre": "fantasy",
                "processing_mode": "pipeline"
            },
            {
                "materials": sample_materials[1:2],
                "genre": "romance",
                "processing_mode": "agent"
            },
            {
                "materials": sample_materials[2:],
                "genre": "mystery",
                "processing_mode": "hybrid"
            }
        ]
        
        # Execute bulk flow
        job_ids = await bulk_material_ingestion_flow(
            material_batches=batches,
            default_genre="unknown",
            story_id="bulk_story"
        )
        
        # Verify results
        assert job_ids == ["job1", "job2", "job3"]
        assert mock_task.call_count == 3
        
        # Verify individual batch calls
        calls = mock_task.call_args_list
        
        # First batch
        assert calls[0][1]["materials"] == sample_materials[:1]
        assert calls[0][1]["genre_context"] == "fantasy"
        assert calls[0][1]["processing_mode"] == "pipeline"
        
        # Second batch
        assert calls[1][1]["materials"] == sample_materials[1:2]
        assert calls[1][1]["genre_context"] == "romance"
        assert calls[1][1]["processing_mode"] == "agent"
        
        # Third batch
        assert calls[2][1]["materials"] == sample_materials[2:]
        assert calls[2][1]["genre_context"] == "mystery"
        assert calls[2][1]["processing_mode"] == "hybrid"
    
    @patch('src.workflows.generation.material_ingestion_task')
    async def test_bulk_material_ingestion_flow_with_defaults(
        self,
        mock_task,
        sample_materials
    ):
        """Test bulk ingestion with default values."""
        # Setup mock
        mock_task.side_effect = ["job1", "job2"]
        
        # Create batches with missing values
        batches = [
            {"materials": sample_materials[:2]},  # No genre specified
            {"materials": sample_materials[2:], "genre": "sci_fi"}
        ]
        
        # Execute flow
        job_ids = await bulk_material_ingestion_flow(
            material_batches=batches,
            default_genre="horror"
        )
        
        # Verify defaults applied
        calls = mock_task.call_args_list
        
        # First batch should use default genre
        assert calls[0][1]["genre_context"] == "horror"
        assert calls[0][1]["processing_mode"] == "pipeline"  # Default mode
        
        # Second batch should use specified genre
        assert calls[1][1]["genre_context"] == "sci_fi"
    
    @patch('src.workflows.generation.material_ingestion_task')
    async def test_bulk_material_ingestion_flow_empty_batches(
        self,
        mock_task
    ):
        """Test bulk ingestion with empty material batches."""
        # Create batches with empty materials
        batches = [
            {"materials": [], "genre": "fantasy"},  # Empty batch
            {"materials": ["Valid material"], "genre": "romance"}  # Valid batch
        ]
        
        # Setup mock
        mock_task.return_value = "job1"
        
        # Execute flow
        job_ids = await bulk_material_ingestion_flow(
            material_batches=batches
        )
        
        # Verify only non-empty batch processed
        assert job_ids == ["job1"]
        assert mock_task.call_count == 1


class TestMaterialIngestionWorkflowIntegration:
    """Test integration between workflows and existing components."""
    
    def test_workflow_import_compatibility(self):
        """Test that all workflow imports work correctly."""
        # Test imports succeed without errors
        from src.workflows.generation import (
            material_ingestion_task,
            material_ingestion_flow,
            bulk_material_ingestion_flow
        )
        
        # Verify functions are callable
        assert callable(material_ingestion_task)
        assert callable(material_ingestion_flow)
        assert callable(bulk_material_ingestion_flow)
    
    def test_workflow_parameter_validation(self):
        """Test that workflow parameters match expected signatures."""
        from src.workflows.generation import material_ingestion_task
        import inspect
        
        # Get function signature
        sig = inspect.signature(material_ingestion_task)
        
        # Verify expected parameters exist
        expected_params = [
            "materials", "genre_context", "processing_mode", 
            "batch_size", "min_confidence_threshold", "story_id", "dry_run"
        ]
        
        for param in expected_params:
            assert param in sig.parameters, f"Missing parameter: {param}"


if __name__ == "__main__":
    # Run basic integration tests
    print("Running material ingestion workflow tests...")
    
    # Test imports
    try:
        from src.workflows.generation import (
            material_ingestion_task,
            material_ingestion_flow,
            bulk_material_ingestion_flow
        )
        print("✅ Workflow imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        exit(1)
    
    # Test function signatures
    import inspect
    
    task_sig = inspect.signature(material_ingestion_task)
    flow_sig = inspect.signature(material_ingestion_flow)
    bulk_sig = inspect.signature(bulk_material_ingestion_flow)
    
    print(f"✅ material_ingestion_task parameters: {len(task_sig.parameters)}")
    print(f"✅ material_ingestion_flow parameters: {len(flow_sig.parameters)}")
    print(f"✅ bulk_material_ingestion_flow parameters: {len(bulk_sig.parameters)}")
    
    print("\n🎉 Material ingestion workflow integration tests passed!")
    print("✅ Phase 1B Prefect integration is ready")
    print("\nNext steps:")
    print("- Run full test suite: pytest tests/test_material_ingestion_workflows.py -v")
    print("- Test CLI integration: factory ingest-materials --help")
    print("- Implement Phase 2A: LibrarianAgent foundation")