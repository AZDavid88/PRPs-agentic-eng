"""Tests for the Narrative Factory CLI commands."""

import pytest
from typer.testing import CliRunner
from unittest.mock import Mock, patch, AsyncMock
from src.cli.commands import app
from src.models.agent_models import JobState
from datetime import datetime

runner = CliRunner()


def test_cli_help():
    """Test that CLI shows help information."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Narrative Factory CLI" in result.stdout
    # Rich wraps text, so check if either the full text or parts are present
    assert "Human-in-the-Loop" in result.stdout or "workflow" in result.stdout


def test_generate_command_help():
    """Test generate command help."""
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "Start a new narrative generation" in result.stdout
    assert "seed" in result.stdout
    assert "characters" in result.stdout


def test_status_command_help():
    """Test status command help."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "Show all jobs pending human review" in result.stdout


def test_review_command_help():
    """Test review command help."""
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0
    assert "Review the output of a specific job" in result.stdout


def test_approve_command_help():
    """Test approve command help."""
    result = runner.invoke(app, ["approve", "--help"])
    assert result.exit_code == 0
    assert "Approve a job and continue the workflow" in result.stdout


def test_reject_command_help():
    """Test reject command help."""
    result = runner.invoke(app, ["reject", "--help"])
    assert result.exit_code == 0
    assert "Reject a job with feedback" in result.stdout


@patch('src.cli.commands.initial_generation_flow')
def test_generate_command(mock_flow):
    """Test the generate command calls the initial flow."""
    mock_flow.return_value = "d-12345678"
    
    result = runner.invoke(app, ["generate", "A mysterious stranger arrives"])
    
    assert result.exit_code == 0
    assert "Starting generation with seed" in result.stdout
    assert "Director task initiated" in result.stdout
    assert "d-12345678" in result.stdout
    mock_flow.assert_called_once()


@patch('src.cli.commands.initial_generation_flow')
def test_generate_command_with_characters(mock_flow):
    """Test the generate command with custom characters."""
    mock_flow.return_value = "d-12345678"
    
    result = runner.invoke(app, ["generate", "Test seed", "--characters", "char_protagonist,char_mentor"])
    
    assert result.exit_code == 0
    assert "Active characters: char_protagonist, char_mentor" in result.stdout
    mock_flow.assert_called_once()
    # Check that the characters were parsed correctly
    call_args = mock_flow.call_args[0]
    assert call_args[1] == ["char_protagonist", "char_mentor"]


@patch('src.cli.commands.job_store')
def test_status_command_no_jobs(mock_job_store):
    """Test status command when no jobs are pending."""
    mock_job_store.get_pending_jobs.return_value = []
    
    result = runner.invoke(app, ["status"])
    
    assert result.exit_code == 0
    assert "No jobs pending review" in result.stdout


@patch('src.cli.commands.job_store')
def test_status_command_with_jobs(mock_job_store):
    """Test status command with pending jobs."""
    # Create mock job
    mock_job = JobState(
        job_id="d-12345678-abcd-1234-5678-123456789012",
        agent="Director",
        status="pending_approval",
        input_payload={"test": "data"},
        created_at=datetime.now()
    )
    mock_job_store.get_pending_jobs.return_value = [mock_job]
    
    result = runner.invoke(app, ["status"])
    
    assert result.exit_code == 0
    assert "Pending Jobs" in result.stdout
    assert "d-12345678-a..." in result.stdout
    assert "Director" in result.stdout


@patch('src.cli.commands.job_store')
def test_review_command(mock_job_store):
    """Test review command displays job details."""
    # Create mock job
    mock_job = JobState(
        job_id="d-12345678",
        agent="Director",
        status="pending_approval",
        input_payload={"test": "data"},
        output_payload={"strategic_brief": "Test output"}
    )
    mock_job_store.get_job.return_value = mock_job
    
    result = runner.invoke(app, ["review", "d-12345678"])
    
    assert result.exit_code == 0
    assert "Reviewing Job: d-12345678" in result.stdout
    assert "Director" in result.stdout
    assert "strategic_brief" in result.stdout


@patch('src.cli.commands.job_store')
def test_review_command_job_not_found(mock_job_store):
    """Test review command when job doesn't exist."""
    mock_job_store.get_job.return_value = None
    
    result = runner.invoke(app, ["review", "invalid-id"])
    
    assert result.exit_code == 1
    assert "Job invalid-id not found" in result.stdout


@patch('src.cli.commands.job_store')
@patch('src.cli.commands.continue_generation_flow')
def test_approve_director_job(mock_flow, mock_job_store):
    """Test approving a Director job triggers Tactician flow."""
    # Create mock Director job
    mock_job = JobState(
        job_id="d-12345678",
        agent="Director",
        status="pending_approval",
        input_payload={"test": "data"}
    )
    mock_job_store.get_job.return_value = mock_job
    mock_job_store.approve_job.return_value = {"approved": True}
    mock_flow.return_value = "t-87654321"
    
    result = runner.invoke(app, ["approve", "d-12345678"])
    
    assert result.exit_code == 0
    assert "Approving Director job" in result.stdout
    assert "Starting Tactician workflow" in result.stdout
    assert "t-87654321" in result.stdout
    mock_flow.assert_called_once_with("d-12345678")


@patch('src.cli.commands.job_store')
@patch('src.cli.commands.finalize_generation_flow')
def test_approve_tactician_job(mock_flow, mock_job_store):
    """Test approving a Tactician job triggers final generation."""
    # Create mock Tactician job
    mock_job = JobState(
        job_id="t-87654321",
        agent="Tactician",
        status="pending_approval",
        input_payload={"test": "data"}
    )
    mock_job_store.get_job.return_value = mock_job
    mock_job_store.approve_job.return_value = {"approved": True}
    mock_flow.return_value = "Once upon a time..." * 100  # Mock chapter text
    
    result = runner.invoke(app, ["approve", "t-87654321"])
    
    assert result.exit_code == 0
    assert "Approving Tactician job" in result.stdout
    assert "Starting final generation" in result.stdout
    assert "Chapter generation complete" in result.stdout
    assert "words" in result.stdout
    mock_flow.assert_called_once_with("t-87654321")


@patch('src.cli.commands.job_store')
def test_reject_command(mock_job_store):
    """Test reject command with feedback."""
    mock_job_store.reject_job.return_value = {"input_payload": {"test": "data"}}
    
    result = runner.invoke(app, ["reject", "d-12345678", "--feedback", "Needs more detail"])
    
    assert result.exit_code == 0
    assert "Rejecting job: d-12345678" in result.stdout
    assert "Feedback: Needs more detail" in result.stdout
    assert "Job rejected" in result.stdout
    mock_job_store.reject_job.assert_called_once_with("d-12345678", "Needs more detail")


@patch('src.cli.commands.job_store')
def test_reject_command_missing_feedback(mock_job_store):
    """Test reject command requires feedback."""
    result = runner.invoke(app, ["reject", "d-12345678"])
    
    # Should fail because feedback is required
    assert result.exit_code != 0
    assert "Missing option" in result.stdout


@patch('src.cli.commands.job_store')
def test_test_connection_command_all_ok(mock_job_store):
    """Test connection test when all services are available."""
    mock_job_store.health_check.return_value = True
    
    with patch('src.cli.commands.QdrantService') as mock_qdrant:
        mock_qdrant_instance = AsyncMock()
        mock_qdrant.return_value = mock_qdrant_instance
        mock_qdrant_instance.get_collection_info.return_value = {"points_count": 10}
        
        result = runner.invoke(app, ["test-connection"])
        
        assert result.exit_code == 0
        assert "Testing service connections" in result.stdout
        assert "Redis connection: OK" in result.stdout
        assert "Qdrant connection" in result.stdout


@patch('src.cli.commands.job_store')
def test_test_connection_command_redis_fail(mock_job_store):
    """Test connection test when Redis is unavailable."""
    mock_job_store.health_check.return_value = False
    
    result = runner.invoke(app, ["test-connection"])
    
    assert result.exit_code == 0  # Command completes even if connection fails
    assert "Redis connection: FAILED" in result.stdout


def test_test_command():
    """Test the basic test command."""
    result = runner.invoke(app, ["test"])
    
    assert result.exit_code == 0
    assert "Narrative Factory CLI is working!" in result.stdout
    assert "MVP Phase 5: CLI Implementation complete" in result.stdout


@pytest.mark.skip(reason="LEGACY TEST - ingest command deprecated, replaced by ingest-materials command")
def test_ingest_command_deprecated():
    """Legacy test - ingest command replaced by ingest-materials."""
    pass


@pytest.mark.skip(reason="LEGACY TEST - ingest command deprecated, replaced by ingest-materials command")
def test_ingest_command_error_deprecated():
    """Legacy test - ingest command replaced by ingest-materials."""
    pass


# Integration test helper - can be skipped in CI
@pytest.mark.skip(reason="Requires running services")
def test_full_workflow_integration():
    """Integration test for full workflow (requires running services)."""
    # This would test the actual workflow with real services
    # Skip in CI but useful for local development
    pass