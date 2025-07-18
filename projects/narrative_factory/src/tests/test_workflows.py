"""Tests for Prefect workflow orchestration."""

from unittest.mock import Mock, patch

import pytest

from src.models import ChapterBlueprint, ChapterMetadata, StrategicBrief
from src.workflows.generation import (
    continue_generation_flow,
    finalize_generation_flow,
    initial_generation_flow,
)
from src.workflows.jobs import JobStore


@pytest.fixture
def mock_job_store():
    """Mock JobStore for testing."""
    with patch('src.workflows.generation.job_store') as mock_store:
        yield mock_store


@pytest.fixture
def mock_memory_service():
    """Mock QdrantService for testing."""
    with patch('src.workflows.generation.memory_service') as mock_memory:
        yield mock_memory


@pytest.fixture
def sample_strategic_brief():
    """Sample strategic brief for testing."""
    return StrategicBrief(
        title="Test Chapter",
        scope="SINGLE_CHAPTER",
        estimated_chapters="1",
        pov_character_id="char_protagonist",
        goal="Test goal",
        key_events=["Event 1", "Event 2"],
        emotional_turning_point="Test turning point",
        cliffhanger_concept="Test cliffhanger"
    )


@pytest.fixture
def sample_chapter_blueprint():
    """Sample chapter blueprint for testing."""
    return ChapterBlueprint(
        metadata=ChapterMetadata(
            chapter_goal="Test goal",
            hook_concept="Test hook",
            discovery_log=["Discovery 1"]
        ),
        title_suggestions=["Title 1", "Title 2"],
        beats=[],
        brief_id="test-brief-id"
    )


@pytest.mark.asyncio
async def test_initial_generation_flow_creates_pending_job(mock_job_store, mock_memory_service, sample_strategic_brief):
    """Test that the initial flow runs the director task and creates a pending job."""
    # Mock the agent execution
    with patch('src.workflows.generation.DirectorAgent') as mock_director_class:
        mock_director = Mock()
        mock_director.execute.return_value = sample_strategic_brief
        mock_director_class.return_value = mock_director

        # Mock job store operations
        mock_job_store.create_job.return_value = "test-job-id"

        # Mock the async memory service call
        from unittest.mock import AsyncMock
        mock_memory_service.fetch_context_for_director = AsyncMock(return_value=Mock(model_dump=lambda: {"test": "context"}))

        # Run the initial flow
        result = await initial_generation_flow("A test seed.")

        # Assert job was created and updated
        mock_job_store.create_job.assert_called_once()
        mock_job_store.update_job_as_pending.assert_called_once()

        # Check that the job creation was called with correct parameters
        create_call = mock_job_store.create_job.call_args
        assert create_call[1]['agent'] == "Director"
        assert create_call[1]['input_payload']['chapter_seed'] == "A test seed."

        # Check that the job was updated with the director output
        update_call = mock_job_store.update_job_as_pending.call_args
        assert update_call[0][0] == "test-job-id"  # job_id
        assert update_call[0][1] == sample_strategic_brief.model_dump()  # output_payload

        assert result == "test-job-id"


def test_continue_generation_flow_with_approved_director(mock_job_store, sample_strategic_brief, sample_chapter_blueprint):
    """Test that the continue flow runs the tactician task with approved director output."""
    # Mock the agent execution
    with patch('src.workflows.generation.TacticianAgent') as mock_tactician_class:
        mock_tactician = Mock()
        mock_tactician.execute.return_value = sample_chapter_blueprint
        mock_tactician_class.return_value = mock_tactician

        # Mock job store operations
        mock_job_store.approve_job.return_value = sample_strategic_brief.model_dump()
        mock_job_store.create_job.return_value = "tactician-job-id"

        # Run the continue flow
        result = continue_generation_flow("director-job-id")

        # Assert director job was approved
        mock_job_store.approve_job.assert_called_once_with("director-job-id")

        # Assert tactician job was created
        mock_job_store.create_job.assert_called_once()
        create_call = mock_job_store.create_job.call_args
        assert create_call[1]['agent'] == "Tactician"

        # Assert tactician job was updated as pending
        mock_job_store.update_job_as_pending.assert_called_once()
        update_call = mock_job_store.update_job_as_pending.call_args
        assert update_call[0][0] == "tactician-job-id"

        assert result == "tactician-job-id"


def test_finalize_generation_flow_with_weaver_and_canonist(mock_job_store, sample_chapter_blueprint):
    """Test that the finalize flow runs weaver and canonist tasks."""
    # Mock the agent executions
    with patch('src.workflows.generation.WeaverAgent') as mock_weaver_class, \
         patch('src.workflows.generation.CanonistAgent') as mock_canonist_class:

        mock_weaver = Mock()
        mock_weaver.execute.return_value = "Generated chapter text"
        mock_weaver_class.return_value = mock_weaver

        mock_canonist = Mock()
        mock_canonist.execute.return_value = "Validated chapter text"
        mock_canonist_class.return_value = mock_canonist

        # Mock job store operations
        mock_job_data = Mock()
        mock_job_data.status = "approved"
        mock_job_data.output_payload = sample_chapter_blueprint.model_dump()

        mock_job_store.get_job.return_value = mock_job_data
        mock_job_store.approve_job.return_value = sample_chapter_blueprint.model_dump()
        mock_job_store.create_job.return_value = "weaver-job-id"

        # Run the finalize flow
        result = finalize_generation_flow("tactician-job-id")

        # Assert tactician job was retrieved
        mock_job_store.get_job.assert_called_once_with("tactician-job-id")

        # Assert weaver job was created
        mock_job_store.create_job.assert_called_once()
        create_call = mock_job_store.create_job.call_args
        assert create_call[1]['agent'] == "Weaver"

        # Assert both agents were executed
        mock_weaver.execute.assert_called_once()
        mock_canonist.execute.assert_called_once()

        assert result == "Validated chapter text"


def test_director_task_failure_handling(mock_job_store, mock_memory_service):
    """Test that director task handles failures properly."""
    from src.workflows.generation import director_task

    # Mock the agent execution to fail
    with patch('src.workflows.generation.DirectorAgent') as mock_director_class:
        mock_director = Mock()
        mock_director.execute.side_effect = Exception("Director execution failed")
        mock_director_class.return_value = mock_director

        # Mock job store operations
        mock_job_store.create_job.return_value = "test-job-id"

        # Mock the async memory service call
        from unittest.mock import AsyncMock
        mock_memory_service.fetch_context_for_director = AsyncMock(return_value=Mock(model_dump=lambda: {"test": "context"}))

        # Run the director task and expect it to raise an exception
        with pytest.raises(Exception, match="Director execution failed"):
            import asyncio
            asyncio.run(director_task("A test seed."))

        # Assert job was created (possibly multiple times due to retries)
        assert mock_job_store.create_job.call_count >= 1
        assert mock_job_store.update_job_as_pending.call_count >= 1

        # Check that the job was updated with error status
        update_call = mock_job_store.update_job_as_pending.call_args
        assert update_call[0][0] == "test-job-id"  # job_id
        assert "error" in update_call[0][1]  # error in output_payload
        assert update_call[0][1]["status"] == "failed"


def test_job_store_redis_operations():
    """Test JobStore Redis operations."""

    # This test would require a real Redis instance, so we'll mock it
    with patch('src.workflows.jobs.Redis') as mock_redis_class:
        mock_redis = Mock()
        mock_redis_class.from_env.return_value = mock_redis

        # Test job creation
        job_store = JobStore()
        job_id = job_store.create_job("Director", {"test": "input"})

        # Assert Redis set was called
        mock_redis.set.assert_called_once()

        # Assert job_id is a string
        assert isinstance(job_id, str)
        assert len(job_id) > 0
