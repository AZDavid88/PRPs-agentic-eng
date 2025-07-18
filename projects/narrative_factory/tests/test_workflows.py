"""Tests for Prefect workflows and JobStore functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from src.workflows.jobs import JobStore
from src.workflows.generation import (
    director_task,
    tactician_task,
    weaver_task,
    initial_generation_flow,
    continue_generation_flow,
    finalize_generation_flow,
    get_pending_jobs,
    get_job_details,
    approve_job_and_continue,
    reject_job_with_feedback
)
from src.models.agent_models import JobState, StrategicBrief, ChapterBlueprint


class TestJobStore:
    """Test JobStore functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Upstash Redis client."""
        with patch('src.workflows.jobs.Redis') as mock_redis_class:
            mock_client = Mock()
            mock_redis_class.from_env.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def job_store(self, mock_redis):
        """Create JobStore instance with mocked Redis."""
        return JobStore()
    
    def test_create_job(self, job_store, mock_redis):
        """Test job creation in JobStore."""
        # Mock Redis set operation
        mock_redis.set.return_value = True
        
        # Create job
        job_id = job_store.create_job("Director", {"chapter_seed": "test seed"})
        
        # Verify job was created
        assert job_id is not None
        assert len(job_id) > 0
        mock_redis.set.assert_called_once()
        
        # Verify the key format
        call_args = mock_redis.set.call_args
        assert call_args[0][0].startswith("job:")
    
    def test_update_job_as_pending(self, job_store, mock_redis):
        """Test updating job to pending approval status."""
        # Mock existing job
        job = JobState(
            agent="Director",
            status="processing",
            input_payload={"chapter_seed": "test"}
        )
        mock_redis.get.return_value = job.model_dump_json()
        mock_redis.set.return_value = True
        
        # Update job as pending
        job_store.update_job_as_pending("test_job_id", {"strategic_brief": "test output"})
        
        # Verify Redis operations
        mock_redis.get.assert_called_once_with("job:test_job_id")
        mock_redis.set.assert_called_once()
        
        # Verify the updated job data
        call_args = mock_redis.set.call_args
        updated_job_json = call_args[0][1]
        updated_job = JobState.model_validate_json(updated_job_json)
        assert updated_job.status == "pending_approval"
        assert updated_job.output_payload == {"strategic_brief": "test output"}
    
    def test_approve_job(self, job_store, mock_redis):
        """Test job approval."""
        # Mock existing job
        job = JobState(
            agent="Director",
            status="pending_approval",
            input_payload={"chapter_seed": "test"},
            output_payload={"strategic_brief": "test output"}
        )
        mock_redis.get.return_value = job.model_dump_json()
        mock_redis.set.return_value = True
        
        # Approve job
        output = job_store.approve_job("test_job_id")
        
        # Verify output returned
        assert output == {"strategic_brief": "test output"}
        
        # Verify Redis operations
        mock_redis.get.assert_called_once_with("job:test_job_id")
        mock_redis.set.assert_called_once()
    
    def test_get_pending_jobs(self, job_store, mock_redis):
        """Test getting pending jobs."""
        # Mock scan_iter and get operations
        mock_redis.scan_iter.return_value = ["job:job1", "job:job2"]
        
        job1 = JobState(agent="Director", status="pending_approval", input_payload={})
        job2 = JobState(agent="Tactician", status="approved", input_payload={})
        
        mock_redis.get.side_effect = [job1.model_dump_json(), job2.model_dump_json()]
        
        # Get pending jobs
        pending_jobs = job_store.get_pending_jobs()
        
        # Verify only pending jobs returned
        assert len(pending_jobs) == 1
        assert pending_jobs[0].agent == "Director"
        assert pending_jobs[0].status == "pending_approval"
    
    def test_health_check(self, job_store, mock_redis):
        """Test Redis health check."""
        # Test successful ping
        mock_redis.ping.return_value = True
        assert job_store.health_check() is True
        
        # Test failed ping
        mock_redis.ping.side_effect = Exception("Connection failed")
        assert job_store.health_check() is False


class TestWorkflowTasks:
    """Test Prefect workflow tasks."""
    
    @pytest.fixture
    def mock_job_store(self):
        """Mock JobStore."""
        with patch('src.workflows.generation.job_store') as mock:
            yield mock
    
    @pytest.fixture
    def mock_memory_service(self):
        """Mock QdrantService."""
        with patch('src.workflows.generation.memory_service') as mock:
            yield mock
    
    @pytest.fixture
    def mock_director_agent(self):
        """Mock DirectorAgent."""
        with patch('src.workflows.generation.DirectorAgent') as mock:
            yield mock
    
    @pytest.fixture
    def mock_tactician_agent(self):
        """Mock TacticianAgent."""
        with patch('src.workflows.generation.TacticianAgent') as mock:
            yield mock
    
    def test_director_task_success(self, mock_job_store, mock_memory_service, mock_director_agent):
        """Test successful director task execution."""
        # Setup mocks
        mock_job_store.create_job.return_value = "test_job_id"
        mock_memory_service.fetch_context_for_director.return_value = "test context"
        
        mock_director_instance = Mock()
        mock_strategic_brief = Mock()
        mock_strategic_brief.model_dump.return_value = {"strategic_brief": "test output"}
        mock_director_instance.execute.return_value = mock_strategic_brief
        mock_director_agent.return_value = mock_director_instance
        
        # Execute task
        result = director_task("test seed", ["char1"])
        
        # Verify result
        assert result == "test_job_id"
        
        # Verify mocks called correctly
        mock_job_store.create_job.assert_called_once_with(
            agent="Director",
            input_payload={"chapter_seed": "test seed", "active_characters": ["char1"]}
        )
        mock_memory_service.fetch_context_for_director.assert_called_once_with("test seed", ["char1"])
        mock_director_instance.execute.assert_called_once_with("test seed", "test context")
        mock_job_store.update_job_as_pending.assert_called_once_with(
            "test_job_id", 
            {"strategic_brief": "test output"}
        )
    
    def test_tactician_task_success(self, mock_job_store, mock_tactician_agent):
        """Test successful tactician task execution."""
        # Setup mocks
        mock_job_store.approve_job.return_value = {"strategic_brief": "test brief"}
        mock_job_store.create_job.return_value = "tactician_job_id"
        
        mock_tactician_instance = Mock()
        mock_blueprint = Mock()
        mock_blueprint.model_dump.return_value = {"chapter_blueprint": "test blueprint"}
        mock_tactician_instance.execute.return_value = mock_blueprint
        mock_tactician_agent.return_value = mock_tactician_instance
        
        # Execute task
        result = tactician_task("director_job_id")
        
        # Verify result
        assert result == "tactician_job_id"
        
        # Verify mocks called correctly
        mock_job_store.approve_job.assert_called_once_with("director_job_id")
        mock_job_store.create_job.assert_called_once_with(
            agent="Tactician",
            input_payload={"strategic_brief": {"strategic_brief": "test brief"}}
        )
        mock_tactician_instance.execute.assert_called_once_with({"strategic_brief": "test brief"})
    
    def test_tactician_task_no_approval(self, mock_job_store):
        """Test tactician task with no approved director job."""
        # Setup mock to return None (no approved job)
        mock_job_store.approve_job.return_value = None
        
        # Execute task and expect exception
        with pytest.raises(ValueError, match="not approved or not found"):
            tactician_task("director_job_id")
    
    def test_weaver_task_success(self, mock_job_store):
        """Test successful weaver task execution."""
        # Setup mocks
        mock_job_store.approve_job.return_value = {"chapter_blueprint": "test blueprint"}
        mock_job_store.create_job.return_value = "weaver_job_id"
        
        with patch('src.workflows.generation.WeaverAgent') as mock_weaver_agent:
            mock_weaver_instance = Mock()
            mock_weaver_instance.execute.return_value = "Generated chapter text"
            mock_weaver_agent.return_value = mock_weaver_instance
            
            # Execute task
            result = weaver_task("tactician_job_id")
            
            # Verify result
            assert result == "Generated chapter text"
            
            # Verify mocks called correctly
            mock_job_store.approve_job.assert_called_once_with("tactician_job_id")
            mock_weaver_instance.execute.assert_called_once_with({"chapter_blueprint": "test blueprint"})
            mock_job_store.update_job_as_pending.assert_called_once_with(
                "weaver_job_id",
                {"chapter_text": "Generated chapter text"}
            )


class TestWorkflowFlows:
    """Test Prefect workflow flows."""
    
    @pytest.fixture
    def mock_director_task(self):
        """Mock director_task."""
        with patch('src.workflows.generation.director_task') as mock:
            yield mock
    
    @pytest.fixture
    def mock_tactician_task(self):
        """Mock tactician_task."""
        with patch('src.workflows.generation.tactician_task') as mock:
            yield mock
    
    @pytest.fixture
    def mock_weaver_task(self):
        """Mock weaver_task."""
        with patch('src.workflows.generation.weaver_task') as mock:
            yield mock
    
    def test_initial_generation_flow(self, mock_director_task):
        """Test initial generation flow."""
        # Setup mock
        mock_director_task.return_value = "test_job_id"
        
        # Execute flow
        result = initial_generation_flow("test seed")
        
        # Verify result
        assert result == "test_job_id"
        
        # Verify task called correctly
        mock_director_task.assert_called_once_with("test seed", None)
    
    def test_continue_generation_flow(self, mock_tactician_task):
        """Test continue generation flow."""
        # Setup mock
        mock_tactician_task.return_value = "tactician_job_id"
        
        # Execute flow
        result = continue_generation_flow("director_job_id")
        
        # Verify result
        assert result == "tactician_job_id"
        
        # Verify task called correctly
        mock_tactician_task.assert_called_once_with("director_job_id")
    
    def test_finalize_generation_flow(self, mock_weaver_task):
        """Test finalize generation flow."""
        # Setup mocks
        mock_job = Mock()
        mock_job.status = "approved"
        mock_job.output_payload = {"chapter_blueprint": "test blueprint"}
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_job.return_value = mock_job
            mock_weaver_task.return_value = "Generated chapter text"
            
            with patch('src.workflows.generation.canonist_task') as mock_canonist_task:
                mock_canonist_task.return_value = "Validated chapter text"
                
                # Execute flow
                result = finalize_generation_flow("tactician_job_id")
                
                # Verify result
                assert result == "Validated chapter text"
                
                # Verify tasks called correctly
                mock_job_store.get_job.assert_called_once_with("tactician_job_id")
                mock_weaver_task.assert_called_once_with("tactician_job_id")
                mock_canonist_task.assert_called_once_with(
                    "Generated chapter text", 
                    {"chapter_blueprint": "test blueprint"}
                )


class TestUtilityFunctions:
    """Test utility functions for CLI integration."""
    
    def test_get_pending_jobs(self):
        """Test getting pending job IDs."""
        mock_job1 = Mock()
        mock_job1.job_id = "job1"
        mock_job2 = Mock()
        mock_job2.job_id = "job2"
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_pending_jobs.return_value = [mock_job1, mock_job2]
            
            result = get_pending_jobs()
            
            assert result == ["job1", "job2"]
    
    def test_get_job_details(self):
        """Test getting job details."""
        mock_job = Mock()
        mock_job.job_id = "test_job_id"
        mock_job.agent = "Director"
        mock_job.status = "pending_approval"
        mock_job.input_payload = {"chapter_seed": "test"}
        mock_job.output_payload = {"strategic_brief": "test output"}
        mock_job.created_at = datetime(2023, 1, 1, 12, 0, 0)
        mock_job.updated_at = datetime(2023, 1, 1, 12, 30, 0)
        mock_job.feedback = None
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_job.return_value = mock_job
            
            result = get_job_details("test_job_id")
            
            expected = {
                "job_id": "test_job_id",
                "agent": "Director",
                "status": "pending_approval",
                "input_payload": {"chapter_seed": "test"},
                "output_payload": {"strategic_brief": "test output"},
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-01T12:30:00",
                "feedback": None
            }
            
            assert result == expected
    
    def test_approve_job_and_continue_director(self):
        """Test approving Director job and continuing to Tactician."""
        mock_job = Mock()
        mock_job.agent = "Director"
        mock_job.status = "pending_approval"
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_job.return_value = mock_job
            mock_job_store.approve_job.return_value = {"strategic_brief": "test"}
            
            with patch('src.workflows.generation.continue_generation_flow') as mock_continue:
                mock_continue.return_value = "tactician_job_id"
                
                result = approve_job_and_continue("director_job_id")
                
                assert result == "tactician_job_id"
                mock_job_store.approve_job.assert_called_once_with("director_job_id")
                mock_continue.assert_called_once_with("director_job_id")
    
    def test_approve_job_and_continue_tactician(self):
        """Test approving Tactician job and continuing to finalize."""
        mock_job = Mock()
        mock_job.agent = "Tactician"
        mock_job.status = "pending_approval"
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_job.return_value = mock_job
            mock_job_store.approve_job.return_value = {"chapter_blueprint": "test"}
            
            with patch('src.workflows.generation.finalize_generation_flow') as mock_finalize:
                mock_finalize.return_value = "final_text"
                
                result = approve_job_and_continue("tactician_job_id")
                
                assert result == "final_text"
                mock_job_store.approve_job.assert_called_once_with("tactician_job_id")
                mock_finalize.assert_called_once_with("tactician_job_id")
    
    def test_reject_job_with_feedback(self):
        """Test rejecting job with feedback."""
        mock_job = Mock()
        mock_job.agent = "Director"
        mock_job.status = "pending_approval"
        mock_job.input_payload = {"chapter_seed": "test seed"}
        
        with patch('src.workflows.generation.job_store') as mock_job_store:
            mock_job_store.get_job.return_value = mock_job
            mock_job_store.reject_job.return_value = {"chapter_seed": "test seed"}
            
            with patch('src.workflows.generation.initial_generation_flow') as mock_initial:
                mock_initial.return_value = "new_director_job_id"
                
                result = reject_job_with_feedback("director_job_id", "Please revise")
                
                assert result == "new_director_job_id"
                mock_job_store.reject_job.assert_called_once_with("director_job_id", "Please revise")
                mock_initial.assert_called_once_with("test seed", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])