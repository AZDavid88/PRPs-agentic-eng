"""Tests for state manager service."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.story_state import StoryState, PlotThread, CharacterState, ProtagonistKnowledge
from src.services.state_manager import StateManager, StateSettings


@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def state_settings(temp_state_dir):
    """State manager settings fixture."""
    return StateSettings(
        state_directory=temp_state_dir,
        backup_count=5,
        auto_save=True,
        compression=False
    )


@pytest.fixture
def sample_story_state():
    """Sample story state for testing."""
    return StoryState(
        story_id="test_story_123",
        current_chapter=1,
        created_at=datetime.now(),
        last_updated=datetime.now(),
        active_plot_threads=[
            PlotThread(
                id="thread_001",
                description="Main quest to find the artifact",
                priority=10,
                introduced_chapter=1,
                last_updated_chapter=1,
                status="active",
                related_characters=["char_protagonist", "char_mentor"]
            )
        ],
        unresolved_tensions=[
            "Tension between protagonist and rival",
            "Mystery of the missing artifact"
        ],
        character_states={
            "char_protagonist": CharacterState(
                character_id="char_protagonist",
                current_location="Village Square",
                emotional_state="determined",
                relationships={"char_mentor": "trusted_ally"},
                status="active",
                last_seen_chapter=1
            )
        },
        world_state_changes={
            "village_mood": "hopeful",
            "artifact_status": "missing"
        },
        protagonist_knowledge=[
            ProtagonistKnowledge(
                concept="Ancient artifact exists",
                chapter_discovered=1,
                confirmation_level="confirmed",
                implications=["Might solve village crisis"]
            )
        ],
        established_facts={
            "village_in_crisis": True,
            "protagonist_chosen": True
        },
        narrative_tone="epic_adventure",
        pacing_state="building_momentum"
    )


class TestStateSettings:
    """Test cases for StateSettings."""

    def test_state_settings_defaults(self):
        """Test StateSettings with default values."""
        settings = StateSettings()
        assert settings.backup_count == 10
        assert settings.auto_save is True
        assert settings.compression is True
        assert Path(settings.state_directory).name == "state"

    def test_state_settings_custom_values(self, temp_state_dir):
        """Test StateSettings with custom values."""
        settings = StateSettings(
            state_directory=temp_state_dir,
            backup_count=3,
            auto_save=False,
            compression=False
        )
        assert settings.state_directory == temp_state_dir
        assert settings.backup_count == 3
        assert settings.auto_save is False
        assert settings.compression is False


class TestStateManager:
    """Test cases for StateManager."""

    def test_state_manager_init_default(self):
        """Test StateManager initialization with defaults."""
        manager = StateManager()
        assert manager.settings is not None
        assert isinstance(manager.settings, StateSettings)

    def test_state_manager_init_custom_settings(self, state_settings):
        """Test StateManager initialization with custom settings."""
        manager = StateManager(state_settings)
        assert manager.settings == state_settings

    @pytest.mark.asyncio
    async def test_save_state(self, state_settings, sample_story_state):
        """Test saving story state to file."""
        manager = StateManager(state_settings)
        
        result = await manager.save_state(sample_story_state)
        
        assert result is True
        
        # Verify file was created
        expected_file = Path(state_settings.state_directory) / f"story_state_chapter_{sample_story_state.current_chapter}.json"
        assert expected_file.exists()
        
        # Verify file contents
        with open(expected_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["story_id"] == sample_story_state.story_id
        assert saved_data["current_chapter"] == sample_story_state.current_chapter

    @pytest.mark.asyncio
    async def test_load_state(self, state_settings, sample_story_state):
        """Test loading story state from file."""
        manager = StateManager(state_settings)
        
        # First save a state
        await manager.save_state(sample_story_state)
        
        # Then load it
        loaded_state = await manager.load_state(sample_story_state.story_id, sample_story_state.current_chapter)
        
        assert loaded_state is not None
        assert loaded_state.story_id == sample_story_state.story_id
        assert loaded_state.current_chapter == sample_story_state.current_chapter
        assert len(loaded_state.active_plot_threads) == len(sample_story_state.active_plot_threads)

    @pytest.mark.asyncio
    async def test_load_state_not_found(self, state_settings):
        """Test loading non-existent story state."""
        manager = StateManager(state_settings)
        
        loaded_state = await manager.load_state("non_existent_story", 1)
        
        assert loaded_state is None

    @pytest.mark.asyncio
    async def test_load_latest_state(self, state_settings, sample_story_state):
        """Test loading the latest story state."""
        manager = StateManager(state_settings)
        
        # Save multiple chapters
        for chapter in range(1, 4):
            sample_story_state.current_chapter = chapter
            sample_story_state.last_updated = datetime.now()
            await manager.save_state(sample_story_state)
        
        # Load latest
        latest_state = await manager.load_latest_state(sample_story_state.story_id)
        
        assert latest_state is not None
        assert latest_state.current_chapter == 3  # Should be the highest chapter

    @pytest.mark.asyncio
    async def test_load_latest_state_not_found(self, state_settings):
        """Test loading latest state when no states exist."""
        manager = StateManager(state_settings)
        
        latest_state = await manager.load_latest_state("non_existent_story")
        
        assert latest_state is None

    @pytest.mark.asyncio
    async def test_get_state_history(self, state_settings, sample_story_state):
        """Test getting state history for a story."""
        manager = StateManager(state_settings)
        
        # Save multiple chapters
        for chapter in range(1, 4):
            sample_story_state.current_chapter = chapter
            await manager.save_state(sample_story_state)
        
        history = await manager.get_state_history(sample_story_state.story_id)
        
        assert len(history) == 3
        # Should be sorted by chapter number
        assert history[0].current_chapter == 1
        assert history[1].current_chapter == 2
        assert history[2].current_chapter == 3

    @pytest.mark.asyncio
    async def test_delete_state(self, state_settings, sample_story_state):
        """Test deleting a story state."""
        manager = StateManager(state_settings)
        
        # Save a state
        await manager.save_state(sample_story_state)
        
        # Verify it exists
        loaded_state = await manager.load_state(sample_story_state.story_id, sample_story_state.current_chapter)
        assert loaded_state is not None
        
        # Delete it
        result = await manager.delete_state(sample_story_state.story_id, sample_story_state.current_chapter)
        assert result is True
        
        # Verify it's gone
        loaded_state = await manager.load_state(sample_story_state.story_id, sample_story_state.current_chapter)
        assert loaded_state is None

    @pytest.mark.asyncio
    async def test_delete_all_states(self, state_settings, sample_story_state):
        """Test deleting all states for a story."""
        manager = StateManager(state_settings)
        
        # Save multiple chapters
        for chapter in range(1, 4):
            sample_story_state.current_chapter = chapter
            await manager.save_state(sample_story_state)
        
        # Delete all
        result = await manager.delete_all_states(sample_story_state.story_id)
        assert result is True
        
        # Verify all are gone
        history = await manager.get_state_history(sample_story_state.story_id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_backup_state(self, state_settings, sample_story_state):
        """Test creating state backups."""
        manager = StateManager(state_settings)
        
        # Save original state
        await manager.save_state(sample_story_state)
        
        # Create backup
        backup_path = await manager.backup_state(sample_story_state.story_id, sample_story_state.current_chapter)
        
        assert backup_path is not None
        assert Path(backup_path).exists()
        assert "backup" in str(backup_path)

    @pytest.mark.asyncio
    async def test_restore_state(self, state_settings, sample_story_state):
        """Test restoring state from backup."""
        manager = StateManager(state_settings)
        
        # Save and backup original state
        await manager.save_state(sample_story_state)
        backup_path = await manager.backup_state(sample_story_state.story_id, sample_story_state.current_chapter)
        
        # Modify and save new state
        sample_story_state.current_chapter = 2
        sample_story_state.narrative_tone = "dark_mystery"
        await manager.save_state(sample_story_state)
        
        # Restore from backup
        restored_state = await manager.restore_state(backup_path)
        
        assert restored_state is not None
        assert restored_state.current_chapter == 1  # Original chapter
        assert restored_state.narrative_tone == "epic_adventure"  # Original tone

    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, state_settings, sample_story_state):
        """Test cleaning up old backups."""
        # Set low backup count for testing
        state_settings.backup_count = 2
        manager = StateManager(state_settings)
        
        # Create multiple backups
        await manager.save_state(sample_story_state)
        backups = []
        for i in range(5):
            backup_path = await manager.backup_state(sample_story_state.story_id, sample_story_state.current_chapter)
            backups.append(backup_path)
        
        # Cleanup old backups
        await manager.cleanup_old_backups(sample_story_state.story_id)
        
        # Only the newest backups should remain
        remaining_backups = [b for b in backups if Path(b).exists()]
        assert len(remaining_backups) <= state_settings.backup_count

    @pytest.mark.asyncio
    async def test_validate_state(self, state_settings, sample_story_state):
        """Test state validation."""
        manager = StateManager(state_settings)
        
        # Valid state should pass
        is_valid = await manager.validate_state(sample_story_state)
        assert is_valid is True
        
        # Invalid state should fail
        invalid_state = StoryState(
            story_id="",  # Empty story_id should be invalid
            current_chapter=0,  # Chapter 0 should be invalid
            created_at=datetime.now(),
            last_updated=datetime.now()
        )
        
        is_valid = await manager.validate_state(invalid_state)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_get_state_stats(self, state_settings, sample_story_state):
        """Test getting state statistics."""
        manager = StateManager(state_settings)
        
        # Save multiple chapters
        for chapter in range(1, 4):
            sample_story_state.current_chapter = chapter
            await manager.save_state(sample_story_state)
        
        stats = await manager.get_state_stats(sample_story_state.story_id)
        
        assert stats["total_chapters"] == 3
        assert stats["latest_chapter"] == 3
        assert "total_size" in stats
        assert "creation_date" in stats

    def test_get_state_file_path(self, state_settings):
        """Test state file path generation."""
        manager = StateManager(state_settings)
        
        file_path = manager._get_state_file_path("test_story", 5)
        
        expected_path = Path(state_settings.state_directory) / "story_state_chapter_5.json"
        assert file_path == expected_path

    def test_get_backup_file_path(self, state_settings):
        """Test backup file path generation."""
        manager = StateManager(state_settings)
        
        backup_path = manager._get_backup_file_path("test_story", 3)
        
        assert "backup" in str(backup_path)
        assert "test_story" in str(backup_path)
        assert "chapter_3" in str(backup_path)

    @pytest.mark.asyncio
    async def test_auto_save_disabled(self, temp_state_dir, sample_story_state):
        """Test behavior when auto-save is disabled."""
        settings = StateSettings(state_directory=temp_state_dir, auto_save=False)
        manager = StateManager(settings)
        
        # Auto-save should be disabled but manual save should still work
        result = await manager.save_state(sample_story_state)
        assert result is True

    @pytest.mark.asyncio
    async def test_compression_enabled(self, temp_state_dir, sample_story_state):
        """Test state saving with compression."""
        settings = StateSettings(state_directory=temp_state_dir, compression=True)
        manager = StateManager(settings)
        
        result = await manager.save_state(sample_story_state)
        assert result is True
        
        # File should exist (implementation detail: might be .gz file)
        state_files = list(Path(temp_state_dir).glob("story_state_*"))
        assert len(state_files) > 0

    @pytest.mark.asyncio
    async def test_concurrent_access(self, state_settings, sample_story_state):
        """Test concurrent state operations."""
        import asyncio
        
        manager = StateManager(state_settings)
        
        # Simulate concurrent save operations
        tasks = []
        for i in range(5):
            state_copy = sample_story_state.model_copy()
            state_copy.current_chapter = i + 1
            tasks.append(manager.save_state(state_copy))
        
        results = await asyncio.gather(*tasks)
        
        # All saves should succeed
        assert all(results)

    @pytest.mark.asyncio
    async def test_error_handling(self, state_settings):
        """Test error handling in state operations."""
        manager = StateManager(state_settings)
        
        # Test with invalid directory permissions
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            result = await manager.save_state(StoryState(
                story_id="test",
                current_chapter=1,
                created_at=datetime.now(),
                last_updated=datetime.now()
            ))
            assert result is False

    @pytest.mark.asyncio
    async def test_migration_support(self, state_settings):
        """Test state format migration support."""
        manager = StateManager(state_settings)
        
        # This would test migrating from older state formats
        # Implementation depends on actual migration logic
        pass

    @pytest.mark.asyncio
    async def test_state_locking(self, state_settings, sample_story_state):
        """Test state file locking for concurrent access."""
        manager = StateManager(state_settings)
        
        # Test that concurrent operations on the same state are handled properly
        # This depends on the actual locking implementation
        pass