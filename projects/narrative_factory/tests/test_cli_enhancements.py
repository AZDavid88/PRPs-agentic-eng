"""Tests for the Phase 4 CLI enhancements - memory inspection, catalyst management, and enhanced workflows."""

import pytest
from typer.testing import CliRunner
from unittest.mock import Mock, patch, AsyncMock
from src.cli.commands import app

runner = CliRunner()


class TestMemoryInspection:
    """Test memory inspection CLI commands."""
    
    def test_inspect_memory_help(self):
        """Test inspect-memory command help."""
        result = runner.invoke(app, ["inspect-memory", "--help"])
        assert result.exit_code == 0
        assert "Inspect memory/knowledge base" in result.stdout
        assert "QUERY" in result.stdout
        assert "--collection" in result.stdout
        assert "--limit" in result.stdout
        assert "--similarity-threshold" in result.stdout

    @patch('src.cli.commands.QdrantService')
    def test_inspect_memory_basic(self, mock_qdrant_service):
        """Test basic memory inspection command."""
        # Mock the service
        mock_service = Mock()
        mock_service.get_collection_info.return_value = {
            'points_count': 100,
            'status': 'green'
        }
        mock_service.search_by_content.return_value = [
            {
                'source': 'character_sheet',
                'content': 'Elara is a skilled tactician...',
                'score': 0.95
            }
        ]
        mock_qdrant_service.return_value = mock_service
        
        result = runner.invoke(app, ["inspect-memory", "Elara"])
        assert result.exit_code == 0
        # Note: Rich formatting makes exact string matching difficult
        # Just verify the command executes successfully

    @patch('src.cli.commands.QdrantService')
    def test_inspect_memory_with_options(self, mock_qdrant_service):
        """Test memory inspection with custom options."""
        mock_service = Mock()
        mock_service.get_collection_info.return_value = {'points_count': 50, 'status': 'green'}
        mock_service.search_by_content.return_value = []
        mock_qdrant_service.return_value = mock_service
        
        result = runner.invoke(app, [
            "inspect-memory", "ancient prophecy",
            "--collection", "world_bible",
            "--limit", "3",
            "--similarity-threshold", "0.8"
        ])
        assert result.exit_code == 0
        mock_service.search_by_content.assert_called_once_with(
            query_text="ancient prophecy",
            collection_name="world_bible",
            limit=3
        )


class TestStateInspection:
    """Test state inspection CLI commands."""
    
    def test_inspect_state_help(self):
        """Test inspect-state command help."""
        result = runner.invoke(app, ["inspect-state", "--help"])
        assert result.exit_code == 0
        assert "Inspect current story state" in result.stdout
        assert "--details" in result.stdout
        assert "--story-id" in result.stdout

    @patch('src.cli.commands.StateManager')
    def test_inspect_state_basic(self, mock_state_manager):
        """Test basic state inspection command."""
        mock_manager = Mock()
        mock_manager.get_state_summary.return_value = {
            'current_chapter': 1,
            'story_id': 'test-story-id',
            'active_plot_threads': 2,
            'unresolved_tensions': 1,
            'character_count': 3,
            'knowledge_revelations': 1,
            'last_updated': '2025-01-01T00:00:00Z',
            'narrative_tone': 'dramatic',
            'pacing_state': 'rising'
        }
        mock_state_manager.return_value = mock_manager
        
        result = runner.invoke(app, ["inspect-state"])
        assert result.exit_code == 0
        mock_manager.get_state_summary.assert_called_once()

    @patch('src.cli.commands.StateManager')
    def test_inspect_state_with_details(self, mock_state_manager):
        """Test state inspection with details flag."""
        mock_manager = Mock()
        mock_manager.get_state_summary.return_value = {
            'current_chapter': 1,
            'story_id': 'test-story-id'
        }
        
        # Mock full state for details
        mock_full_state = Mock()
        mock_full_state.active_plot_threads = [
            Mock(id='thread-1', priority=8, description='Main quest')
        ]
        mock_full_state.protagonist_knowledge = [
            Mock(concept='Ancient secret', chapter_discovered=1)
        ]
        mock_manager.load_latest_state.return_value = mock_full_state
        mock_state_manager.return_value = mock_manager
        
        result = runner.invoke(app, ["inspect-state", "--details"])
        assert result.exit_code == 0
        mock_manager.load_latest_state.assert_called_once()


class TestEnhancedWorkflow:
    """Test enhanced workflow CLI commands."""
    
    def test_generate_enhanced_help(self):
        """Test generate-enhanced command help."""
        result = runner.invoke(app, ["generate-enhanced", "--help"])
        assert result.exit_code == 0
        assert "Enhanced story generation" in result.stdout
        assert "STORY_SEED" in result.stdout
        assert "--catalyst" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--interactive" in result.stdout

    def test_generate_enhanced_dry_run(self):
        """Test dry-run mode."""
        result = runner.invoke(app, [
            "generate-enhanced", "Test story seed",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.stdout
        assert "Generation Plan:" in result.stdout
        assert "No LLM calls will be made" in result.stdout

    def test_generate_enhanced_with_catalyst_dry_run(self):
        """Test dry-run with catalyst injection."""
        result = runner.invoke(app, [
            "generate-enhanced", "Test story seed",
            "--catalyst", "Ancient magic awakens",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.stdout
        assert "Catalyst injected: Ancient magic awakens" in result.stdout
        assert "└── Catalyst: Ancient magic awakens" in result.stdout

    def test_generate_enhanced_non_interactive_dry_run(self):
        """Test non-interactive dry-run mode."""
        result = runner.invoke(app, [
            "generate-enhanced", "Test story seed",
            "--dry-run", "--non-interactive"
        ])
        assert result.exit_code == 0
        assert "DRY RUN MODE" in result.stdout
        assert "Run without --dry-run to execute" in result.stdout


class TestCatalystManagement:
    """Test catalyst management CLI commands."""
    
    def test_catalyst_add_help(self):
        """Test catalyst-add command help."""
        result = runner.invoke(app, ["catalyst-add", "--help"])
        assert result.exit_code == 0
        assert "Add a creative catalyst" in result.stdout
        assert "CATALYST" in result.stdout
        assert "--target" in result.stdout
        assert "--priority" in result.stdout

    @patch('src.cli.commands.CatalystManager')
    def test_catalyst_add_basic(self, mock_catalyst_manager):
        """Test basic catalyst addition."""
        mock_manager = Mock()
        mock_manager.add_catalyst.return_value = 'catalyst-id-123'
        mock_catalyst_manager.return_value = mock_manager
        
        result = runner.invoke(app, [
            "catalyst-add", "A mysterious stranger arrives"
        ])
        assert result.exit_code == 0
        assert "✓ Catalyst added" in result.stdout
        assert "catalyst-id" in result.stdout
        assert "A mysterious stranger arrives" in result.stdout
        
        mock_manager.add_catalyst.assert_called_once_with(
            description="A mysterious stranger arrives",
            target="next",
            priority=5
        )

    @patch('src.cli.commands.CatalystManager')
    def test_catalyst_add_with_options(self, mock_catalyst_manager):
        """Test catalyst addition with custom options."""
        mock_manager = Mock()
        mock_manager.add_catalyst.return_value = 'catalyst-id-456'
        mock_catalyst_manager.return_value = mock_manager
        
        result = runner.invoke(app, [
            "catalyst-add", "Epic battle sequence",
            "--target", "story-123",
            "--priority", "9"
        ])
        assert result.exit_code == 0
        
        mock_manager.add_catalyst.assert_called_once_with(
            description="Epic battle sequence",
            target="story-123",
            priority=9
        )

    def test_catalyst_list_help(self):
        """Test catalyst-list command help."""
        result = runner.invoke(app, ["catalyst-list", "--help"])
        assert result.exit_code == 0
        assert "List active catalysts" in result.stdout
        assert "--target" in result.stdout
        assert "--summary" in result.stdout

    @patch('src.cli.commands.CatalystManager')
    def test_catalyst_list_basic(self, mock_catalyst_manager):
        """Test basic catalyst listing."""
        mock_manager = Mock()
        mock_manager.list_catalysts.return_value = [
            {
                'id': 'catalyst-1',
                'description': 'Test catalyst',
                'priority': 7,
                'target': 'next',
                'status': 'active'
            }
        ]
        mock_catalyst_manager.return_value = mock_manager
        
        result = runner.invoke(app, ["catalyst-list"])
        assert result.exit_code == 0
        # Command should execute successfully
        mock_manager.list_catalysts.assert_called_once()

    @patch('src.cli.commands.CatalystManager')
    def test_catalyst_list_with_summary(self, mock_catalyst_manager):
        """Test catalyst listing with summary."""
        mock_manager = Mock()
        mock_manager.list_catalysts.return_value = [
            {'id': 'catalyst-1', 'status': 'active'},
            {'id': 'catalyst-2', 'status': 'active'},
            {'id': 'catalyst-3', 'status': 'used'}
        ]
        mock_catalyst_manager.return_value = mock_manager
        
        result = runner.invoke(app, ["catalyst-list", "--summary"])
        assert result.exit_code == 0
        # Should show summary table
        assert "Total Catalysts" in result.stdout or "Catalyst Summary" in result.stdout


class TestCommandIntegration:
    """Test command integration and error handling."""
    
    def test_all_commands_have_help(self):
        """Test that all Phase 4 commands have help."""
        commands = [
            "inspect-memory",
            "inspect-state", 
            "generate-enhanced",
            "catalyst-add",
            "catalyst-list"
        ]
        
        for cmd in commands:
            result = runner.invoke(app, [cmd, "--help"])
            assert result.exit_code == 0, f"Command {cmd} help failed"

    def test_commands_with_invalid_args(self):
        """Test commands with invalid arguments."""
        # Test inspect-memory without required argument
        result = runner.invoke(app, ["inspect-memory"])
        assert result.exit_code != 0
        assert "Missing argument" in result.stdout

        # Test catalyst-add without required argument
        result = runner.invoke(app, ["catalyst-add"])
        assert result.exit_code != 0
        assert "Missing argument" in result.stdout

    @patch('src.cli.commands.QdrantService')
    def test_memory_inspection_error_handling(self, mock_qdrant_service):
        """Test error handling in memory inspection."""
        # Mock service that raises an exception
        mock_service = Mock()
        mock_service.get_collection_info.side_effect = Exception("Connection failed")
        mock_qdrant_service.return_value = mock_service
        
        result = runner.invoke(app, ["inspect-memory", "test"])
        # Should handle the error gracefully
        assert "Error inspecting memory" in result.stdout or result.exit_code != 0