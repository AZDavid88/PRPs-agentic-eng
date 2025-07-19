"""
Tests for Phase 1B CLI material ingestion commands.

Tests the CLI integration with the material ingestion pipeline,
including command validation, file processing, and error handling.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typer.testing import CliRunner

from src.cli.commands import app


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_material_file():
    """Create a temporary file with sample material content."""
    content = """Character: Elena Stormwind, a skilled archer with wind magic abilities and a fierce loyalty to her companions.

Magic System: Elemental Archery - the ability to infuse arrows with elemental magic, allowing them to pierce magical defenses or create area effects on impact.

Setting: The Windspear Garrison, a fortress built into a mountain cliff where elite archer units train and defend the northern borders."""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    
    # Cleanup
    Path(f.name).unlink(missing_ok=True)


class TestCLIIngestionCommands:
    """Test the CLI ingestion command implementation."""
    
    def test_ingest_materials_help(self, runner):
        """Test that ingest-materials help displays correctly."""
        result = runner.invoke(app, ["ingest-materials", "--help"])
        assert result.exit_code == 0
        assert "Ingest materials using the Material Ingestion Pipeline" in result.stdout
        assert "--genre" in result.stdout
        assert "--batch-size" in result.stdout
        assert "--confidence" in result.stdout
    
    def test_ingest_validate_help(self, runner):
        """Test that ingest-validate help displays correctly."""
        result = runner.invoke(app, ["ingest-validate", "--help"])
        assert result.exit_code == 0
        assert "Validate materials before ingestion" in result.stdout
        assert "--check-duplicates" in result.stdout
        assert "--estimate-cost" in result.stdout
    
    def test_ingest_config_help(self, runner):
        """Test that ingest-config help displays correctly."""
        result = runner.invoke(app, ["ingest-config", "--help"])
        assert result.exit_code == 0
        assert "Configure and test the material ingestion pipeline" in result.stdout
        assert "--test-connections" in result.stdout
        assert "--setup" in result.stdout
    
    def test_ingest_status_help(self, runner):
        """Test that ingest-status help displays correctly."""
        result = runner.invoke(app, ["ingest-status", "--help"])
        assert result.exit_code == 0
        assert "Check the status of material ingestion jobs" in result.stdout
        assert "--all" in result.stdout
        assert "--watch" in result.stdout
    
    def test_ingest_materials_validation_errors(self, runner):
        """Test parameter validation for ingest-materials command."""
        # Test invalid batch size
        result = runner.invoke(app, ["ingest-materials", "test.txt", "--batch-size", "150"])
        assert result.exit_code == 1
        assert "Batch size must be between 1 and 100" in result.stdout
        
        # Test invalid confidence threshold
        result = runner.invoke(app, ["ingest-materials", "test.txt", "--confidence", "1.5"])
        assert result.exit_code == 1
        assert "Confidence threshold must be between 0.0 and 1.0" in result.stdout
        
        # Test invalid processing mode
        result = runner.invoke(app, ["ingest-materials", "test.txt", "--mode", "invalid"])
        assert result.exit_code == 1
        assert "Processing mode must be: pipeline, agent, or hybrid" in result.stdout
        
        # Test invalid output format
        result = runner.invoke(app, ["ingest-materials", "test.txt", "--output", "invalid"])
        assert result.exit_code == 1
        assert "Output format must be: table, json, or stream" in result.stdout
    
    def test_validate_command_with_file(self, runner, sample_material_file):
        """Test validate command with actual file."""
        result = runner.invoke(app, [
            "ingest-validate",
            sample_material_file,
            "--genre", "fantasy"
        ])
        assert result.exit_code == 0
        assert "Validating 1 files" in result.stdout
        assert "✅ All files are valid for ingestion" in result.stdout
    
    def test_validate_command_with_nonexistent_file(self, runner):
        """Test validate command with non-existent file."""
        result = runner.invoke(app, [
            "ingest-validate",
            "nonexistent_file.txt"
        ])
        assert result.exit_code == 0
        assert "Invalid Files:" in result.stdout or "No valid files found" in result.stdout
    
    def test_dry_run_mode(self, runner, sample_material_file):
        """Test dry-run mode for ingest-materials."""
        result = runner.invoke(app, [
            "ingest-materials",
            sample_material_file,
            "--genre", "fantasy",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.stdout
        assert "Would process 1 files" in result.stdout
        assert "Genre: fantasy" in result.stdout
    
    def test_config_show_command(self, runner):
        """Test configuration display command."""
        result = runner.invoke(app, ["ingest-config", "--show"])
        assert result.exit_code == 0
        assert "Current Configuration" in result.stdout
        assert "Embedding Provider" in result.stdout
        assert "Qdrant URL" in result.stdout
    
    def test_deprecated_ingest_command(self, runner):
        """Test that the old ingest command shows deprecation warning."""
        result = runner.invoke(app, ["ingest"])
        assert result.exit_code == 0
        assert "This command is deprecated" in result.stdout
        assert "factory ingest-materials" in result.stdout
    
    @patch('src.cli.commands.MaterialIngestionPipeline')
    def test_ingestion_with_mocked_pipeline(self, mock_pipeline_class, runner, sample_material_file):
        """Test actual ingestion with mocked pipeline."""
        # Mock the pipeline response
        mock_response = MagicMock()
        mock_response.status = "completed"
        mock_response.materials_processed = 1
        mock_response.processing_time = 2.5
        mock_response.cost_estimate = 0.005
        mock_response.average_confidence = 0.95
        mock_response.category_distribution = {"character": 1, "magic_system": 1, "setting": 1}
        
        mock_pipeline_instance = AsyncMock()
        mock_pipeline_instance.process_materials.return_value = mock_response
        mock_pipeline_class.return_value = mock_pipeline_instance
        
        # Test the command
        result = runner.invoke(app, [
            "ingest-materials",
            sample_material_file,
            "--genre", "fantasy",
            "--sync"  # Use sync mode for easier testing
        ])
        
        # Verify the command completed
        assert result.exit_code == 0
        assert "Processing" in result.stdout or "completed" in result.stdout


class TestCLIIntegrationPatterns:
    """Test that CLI follows existing patterns correctly."""
    
    def test_command_naming_consistency(self, runner):
        """Test that new commands follow existing naming patterns."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        
        # Check that ingestion commands are present and properly named
        assert "ingest-materials" in result.stdout
        assert "ingest-status" in result.stdout
        assert "ingest-validate" in result.stdout
        assert "ingest-config" in result.stdout
    
    def test_output_formatting_consistency(self, runner, sample_material_file):
        """Test that output formatting matches existing CLI style."""
        result = runner.invoke(app, [
            "ingest-validate",
            sample_material_file
        ])
        assert result.exit_code == 0
        
        # Check for Rich table formatting (unicode box characters)
        assert "┏" in result.stdout or "┌" in result.stdout  # Table borders
        assert "✅" in result.stdout or "All files are valid" in result.stdout  # Success indicators
    
    def test_error_handling_consistency(self, runner):
        """Test that error handling matches existing patterns."""
        result = runner.invoke(app, ["ingest-materials"])  # Missing required argument
        assert result.exit_code == 2  # Typer validation error
        assert "Missing argument" in result.stdout.lower() or "required" in result.stdout.lower()


if __name__ == "__main__":
    # Run basic smoke tests
    print("Running CLI ingestion smoke tests...")
    
    runner = CliRunner()
    
    # Test help commands
    print("✓ Testing help commands...")
    for cmd in ["ingest-materials", "ingest-validate", "ingest-config", "ingest-status"]:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0, f"Help command failed for {cmd}"
    
    print("✓ Testing parameter validation...")
    result = runner.invoke(app, ["ingest-materials", "test.txt", "--batch-size", "150"])
    assert result.exit_code == 1, "Batch size validation should fail"
    
    print("✓ Testing config display...")
    result = runner.invoke(app, ["ingest-config", "--show"])
    assert result.exit_code == 0, "Config display should work"
    
    print("\n🎉 All CLI ingestion smoke tests passed!")
    print("✅ Phase 1B CLI implementation is ready")
    print("\nNext steps:")
    print("- Run full test suite: pytest tests/test_cli_ingestion.py -v")
    print("- Test with real files: factory ingest-materials <file> --genre <genre>")
    print("- Implement Phase 1B Prefect workflow integration")