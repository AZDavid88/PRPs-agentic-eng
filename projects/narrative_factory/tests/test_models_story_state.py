"""Tests for story state models."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.models.story_state import (
    StoryState,
    PlotThread,
    CharacterState,
    ProtagonistKnowledge,
    WorldStateChange,
    NarrativeMilestone
)


class TestPlotThread:
    """Test cases for PlotThread model."""

    def test_plot_thread_creation(self):
        """Test creating a PlotThread."""
        plot_thread = PlotThread(
            id="thread_001",
            description="Quest to find the ancient artifact",
            priority=10,
            introduced_chapter=1,
            last_updated_chapter=3,
            status="active",
            related_characters=["char_hero", "char_mentor"]
        )
        
        assert plot_thread.id == "thread_001"
        assert plot_thread.description == "Quest to find the ancient artifact"
        assert plot_thread.priority == 10
        assert plot_thread.status == "active"
        assert len(plot_thread.related_characters) == 2

    def test_plot_thread_validation(self):
        """Test PlotThread validation."""
        # Valid thread
        valid_thread = PlotThread(
            id="valid_001",
            description="Valid plot thread",
            priority=5,
            introduced_chapter=1,
            last_updated_chapter=1,
            status="active"
        )
        assert valid_thread.priority == 5
        
        # Test default values
        default_thread = PlotThread(
            id="default_001",
            description="Default thread",
            introduced_chapter=1,
            last_updated_chapter=1
        )
        assert default_thread.status == "active"
        assert default_thread.priority == 5
        assert default_thread.related_characters == []

    def test_plot_thread_status_values(self):
        """Test valid plot thread status values."""
        valid_statuses = ["active", "paused", "resolved", "abandoned"]
        
        for status in valid_statuses:
            thread = PlotThread(
                id=f"thread_{status}",
                description=f"Thread with {status} status",
                introduced_chapter=1,
                last_updated_chapter=1,
                status=status
            )
            assert thread.status == status

    def test_plot_thread_priority_range(self):
        """Test plot thread priority range."""
        # Test various priority values
        for priority in [1, 5, 10]:
            thread = PlotThread(
                id=f"thread_p{priority}",
                description="Test thread",
                priority=priority,
                introduced_chapter=1,
                last_updated_chapter=1
            )
            assert thread.priority == priority


class TestCharacterState:
    """Test cases for CharacterState model."""

    def test_character_state_creation(self):
        """Test creating a CharacterState."""
        character_state = CharacterState(
            character_id="char_hero",
            current_location="Village Square",
            emotional_state="determined",
            relationships={"char_mentor": "trusted_ally", "char_rival": "antagonistic"},
            status="active",
            last_seen_chapter=3,
            notes="Recently learned about the artifact"
        )
        
        assert character_state.character_id == "char_hero"
        assert character_state.current_location == "Village Square"
        assert character_state.emotional_state == "determined"
        assert len(character_state.relationships) == 2
        assert character_state.status == "active"
        assert character_state.last_seen_chapter == 3

    def test_character_state_defaults(self):
        """Test CharacterState default values."""
        character_state = CharacterState(
            character_id="char_simple",
            last_seen_chapter=1
        )
        
        assert character_state.current_location == "unknown"
        assert character_state.emotional_state == "neutral"
        assert character_state.relationships == {}
        assert character_state.status == "active"
        assert character_state.notes == ""

    def test_character_state_relationships(self):
        """Test character relationship handling."""
        character_state = CharacterState(
            character_id="char_complex",
            last_seen_chapter=1,
            relationships={
                "char_love_interest": "romantic",
                "char_parent": "family",
                "char_enemy": "hostile",
                "char_friend": "friendship"
            }
        )
        
        assert character_state.relationships["char_love_interest"] == "romantic"
        assert character_state.relationships["char_parent"] == "family"
        assert len(character_state.relationships) == 4


class TestProtagonistKnowledge:
    """Test cases for ProtagonistKnowledge model."""

    def test_protagonist_knowledge_creation(self):
        """Test creating ProtagonistKnowledge."""
        knowledge = ProtagonistKnowledge(
            concept="The artifact can control time",
            chapter_discovered=2,
            confirmation_level="suspected",
            implications=["Could prevent the catastrophe", "Dangerous if misused"],
            source="Ancient tome in the library"
        )
        
        assert knowledge.concept == "The artifact can control time"
        assert knowledge.chapter_discovered == 2
        assert knowledge.confirmation_level == "suspected"
        assert len(knowledge.implications) == 2
        assert knowledge.source == "Ancient tome in the library"

    def test_protagonist_knowledge_confirmation_levels(self):
        """Test valid confirmation levels."""
        valid_levels = ["rumored", "suspected", "likely", "confirmed"]
        
        for level in valid_levels:
            knowledge = ProtagonistKnowledge(
                concept=f"Knowledge at {level} level",
                chapter_discovered=1,
                confirmation_level=level
            )
            assert knowledge.confirmation_level == level

    def test_protagonist_knowledge_defaults(self):
        """Test ProtagonistKnowledge default values."""
        knowledge = ProtagonistKnowledge(
            concept="Basic knowledge",
            chapter_discovered=1
        )
        
        assert knowledge.confirmation_level == "suspected"
        assert knowledge.implications == []
        assert knowledge.source == ""


class TestWorldStateChange:
    """Test cases for WorldStateChange model."""

    def test_world_state_change_creation(self):
        """Test creating WorldStateChange."""
        change = WorldStateChange(
            aspect="village_population",
            previous_value="1000 people",
            current_value="800 people",
            change_reason="Evacuation due to monster attacks",
            chapter_changed=3,
            impact_scope="local"
        )
        
        assert change.aspect == "village_population"
        assert change.previous_value == "1000 people"
        assert change.current_value == "800 people"
        assert change.change_reason == "Evacuation due to monster attacks"
        assert change.chapter_changed == 3
        assert change.impact_scope == "local"

    def test_world_state_change_scopes(self):
        """Test valid impact scopes."""
        valid_scopes = ["local", "regional", "global", "cosmic"]
        
        for scope in valid_scopes:
            change = WorldStateChange(
                aspect=f"change_{scope}",
                previous_value="before",
                current_value="after",
                chapter_changed=1,
                impact_scope=scope
            )
            assert change.impact_scope == scope


class TestNarrativeMilestone:
    """Test cases for NarrativeMilestone model."""

    def test_narrative_milestone_creation(self):
        """Test creating NarrativeMilestone."""
        milestone = NarrativeMilestone(
            title="First encounter with the villain",
            description="The hero meets their primary antagonist",
            chapter=3,
            milestone_type="character_introduction",
            significance="high",
            emotional_impact="tension"
        )
        
        assert milestone.title == "First encounter with the villain"
        assert milestone.chapter == 3
        assert milestone.milestone_type == "character_introduction"
        assert milestone.significance == "high"
        assert milestone.emotional_impact == "tension"

    def test_narrative_milestone_types(self):
        """Test valid milestone types."""
        valid_types = [
            "character_introduction", "plot_twist", "revelation",
            "conflict_escalation", "resolution", "world_building"
        ]
        
        for milestone_type in valid_types:
            milestone = NarrativeMilestone(
                title=f"Milestone of type {milestone_type}",
                chapter=1,
                milestone_type=milestone_type
            )
            assert milestone.milestone_type == milestone_type


class TestStoryState:
    """Test cases for StoryState model."""

    def test_story_state_creation(self):
        """Test creating a complete StoryState."""
        now = datetime.now()
        
        story_state = StoryState(
            story_id="epic_fantasy_001",
            current_chapter=5,
            created_at=now,
            last_updated=now,
            active_plot_threads=[
                PlotThread(
                    id="main_quest",
                    description="Find the Crystal of Power",
                    priority=10,
                    introduced_chapter=1,
                    last_updated_chapter=5,
                    status="active"
                )
            ],
            unresolved_tensions=[
                "Hero's secret identity at risk",
                "Alliance between kingdoms is fragile"
            ],
            character_states={
                "hero": CharacterState(
                    character_id="hero",
                    current_location="Mystic Forest",
                    emotional_state="determined",
                    last_seen_chapter=5
                )
            },
            world_state_changes={
                "magic_level": "increasing",
                "political_stability": "declining"
            },
            protagonist_knowledge=[
                ProtagonistKnowledge(
                    concept="Crystal location is in the Forbidden Mountain",
                    chapter_discovered=4,
                    confirmation_level="confirmed"
                )
            ],
            established_facts={
                "magic_exists": True,
                "kingdoms_at_war": False
            },
            narrative_tone="epic_adventure",
            pacing_state="building_tension"
        )
        
        assert story_state.story_id == "epic_fantasy_001"
        assert story_state.current_chapter == 5
        assert len(story_state.active_plot_threads) == 1
        assert len(story_state.unresolved_tensions) == 2
        assert len(story_state.character_states) == 1
        assert len(story_state.protagonist_knowledge) == 1
        assert story_state.narrative_tone == "epic_adventure"

    def test_story_state_defaults(self):
        """Test StoryState default values."""
        now = datetime.now()
        
        story_state = StoryState(
            story_id="minimal_story",
            current_chapter=1,
            created_at=now,
            last_updated=now
        )
        
        assert story_state.active_plot_threads == []
        assert story_state.unresolved_tensions == []
        assert story_state.character_states == {}
        assert story_state.world_state_changes == {}
        assert story_state.protagonist_knowledge == []
        assert story_state.established_facts == {}
        assert story_state.narrative_tone == "neutral"
        assert story_state.pacing_state == "steady"

    def test_story_state_methods(self):
        """Test StoryState utility methods."""
        now = datetime.now()
        
        story_state = StoryState(
            story_id="test_story",
            current_chapter=3,
            created_at=now,
            last_updated=now,
            active_plot_threads=[
                PlotThread(
                    id="thread1",
                    description="First thread",
                    priority=10,
                    introduced_chapter=1,
                    last_updated_chapter=3,
                    status="active"
                ),
                PlotThread(
                    id="thread2",
                    description="Second thread",
                    priority=5,
                    introduced_chapter=2,
                    last_updated_chapter=3,
                    status="paused"
                )
            ],
            character_states={
                "char1": CharacterState(
                    character_id="char1",
                    status="active",
                    last_seen_chapter=3
                ),
                "char2": CharacterState(
                    character_id="char2",
                    status="inactive",
                    last_seen_chapter=1
                )
            }
        )
        
        # Test get_active_plot_threads method if it exists
        if hasattr(story_state, 'get_active_plot_threads'):
            active_threads = story_state.get_active_plot_threads()
            assert len(active_threads) == 1
            assert active_threads[0].id == "thread1"
        
        # Test get_active_characters method if it exists
        if hasattr(story_state, 'get_active_characters'):
            active_chars = story_state.get_active_characters()
            assert len(active_chars) == 1
            assert "char1" in active_chars

    def test_story_state_validation(self):
        """Test StoryState validation."""
        now = datetime.now()
        
        # Valid story state
        valid_state = StoryState(
            story_id="valid_story",
            current_chapter=1,
            created_at=now,
            last_updated=now
        )
        assert valid_state.story_id == "valid_story"
        
        # Test with invalid chapter number
        with pytest.raises((ValueError, TypeError)):
            StoryState(
                story_id="invalid_story",
                current_chapter=0,  # Chapter should be >= 1
                created_at=now,
                last_updated=now
            )

    def test_story_state_serialization(self):
        """Test StoryState serialization and deserialization."""
        now = datetime.now()
        
        original_state = StoryState(
            story_id="serialization_test",
            current_chapter=2,
            created_at=now,
            last_updated=now,
            active_plot_threads=[
                PlotThread(
                    id="test_thread",
                    description="Test thread",
                    introduced_chapter=1,
                    last_updated_chapter=2
                )
            ],
            narrative_tone="mystery"
        )
        
        # Serialize to dict
        state_dict = original_state.model_dump()
        assert isinstance(state_dict, dict)
        assert state_dict["story_id"] == "serialization_test"
        assert state_dict["current_chapter"] == 2
        
        # Deserialize from dict
        restored_state = StoryState(**state_dict)
        assert restored_state.story_id == original_state.story_id
        assert restored_state.current_chapter == original_state.current_chapter
        assert len(restored_state.active_plot_threads) == 1

    def test_story_state_complex_relationships(self):
        """Test complex character relationships in story state."""
        now = datetime.now()
        
        story_state = StoryState(
            story_id="complex_story",
            current_chapter=5,
            created_at=now,
            last_updated=now,
            character_states={
                "hero": CharacterState(
                    character_id="hero",
                    relationships={
                        "mentor": "respected_teacher",
                        "love_interest": "romantic",
                        "rival": "competitive"
                    },
                    last_seen_chapter=5
                ),
                "mentor": CharacterState(
                    character_id="mentor",
                    relationships={
                        "hero": "promising_student",
                        "villain": "old_enemy"
                    },
                    last_seen_chapter=4
                )
            }
        )
        
        hero_state = story_state.character_states["hero"]
        mentor_state = story_state.character_states["mentor"]
        
        assert hero_state.relationships["mentor"] == "respected_teacher"
        assert mentor_state.relationships["hero"] == "promising_student"
        assert len(hero_state.relationships) == 3
        assert len(mentor_state.relationships) == 2

    def test_story_state_knowledge_progression(self):
        """Test protagonist knowledge progression tracking."""
        now = datetime.now()
        
        story_state = StoryState(
            story_id="knowledge_story",
            current_chapter=4,
            created_at=now,
            last_updated=now,
            protagonist_knowledge=[
                ProtagonistKnowledge(
                    concept="Magic exists",
                    chapter_discovered=1,
                    confirmation_level="confirmed"
                ),
                ProtagonistKnowledge(
                    concept="Villain is the missing prince",
                    chapter_discovered=3,
                    confirmation_level="suspected"
                ),
                ProtagonistKnowledge(
                    concept="Artifact is cursed",
                    chapter_discovered=4,
                    confirmation_level="rumored"
                )
            ]
        )
        
        knowledge_list = story_state.protagonist_knowledge
        assert len(knowledge_list) == 3
        
        # Test knowledge at different confirmation levels
        confirmed_knowledge = [k for k in knowledge_list if k.confirmation_level == "confirmed"]
        suspected_knowledge = [k for k in knowledge_list if k.confirmation_level == "suspected"]
        rumored_knowledge = [k for k in knowledge_list if k.confirmation_level == "rumored"]
        
        assert len(confirmed_knowledge) == 1
        assert len(suspected_knowledge) == 1
        assert len(rumored_knowledge) == 1