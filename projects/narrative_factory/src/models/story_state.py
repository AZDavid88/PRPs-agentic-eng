from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class PlotThread(BaseModel):
    """Individual plot thread with resolution status and metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str = Field(..., description="Brief description of the plot thread")
    priority: int = Field(default=1, ge=1, le=10, description="Priority from 1-10")
    introduced_chapter: int = Field(..., description="Chapter where this thread was introduced")
    last_updated_chapter: int = Field(..., description="Last chapter that referenced this thread")
    status: str = Field(default="active", description="Status: active, resolved, dormant")
    related_characters: list[str] = Field(default_factory=list)

class CharacterState(BaseModel):
    """Character state tracking with location and relationship data."""
    character_id: str = Field(..., description="Unique character identifier")
    current_location: str = Field(..., description="Character's current location")
    emotional_state: str = Field(default="neutral", description="Current emotional state")
    knowledge_state: list[str] = Field(default_factory=list, description="Key facts the character knows")
    relationships: dict[str, str] = Field(default_factory=dict, description="Relationship status with other characters")
    last_updated_chapter: int = Field(..., description="Last chapter that updated this character")

class KnowledgeRevelation(BaseModel):
    """Track protagonist's growing understanding of the world."""
    concept: str = Field(..., description="The concept or fact that was revealed")
    chapter_discovered: int = Field(..., description="Chapter where this was first discovered")
    confirmation_level: str = Field(default="suspected", description="Level of certainty: suspected, confirmed, proven")
    implications: list[str] = Field(default_factory=list, description="What this revelation implies")

class StoryState(BaseModel):
    """Enhanced narrative state tracking for long-term continuity."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)

    # Core progression tracking
    current_chapter: int = Field(default=1, description="The chapter number that was just completed")
    story_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for this story")
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)

    # Plot and tension management
    active_plot_threads: list[PlotThread] = Field(default_factory=list)
    unresolved_tensions: list[str] = Field(default_factory=list, description="High-level tension descriptions")

    # Character and world state
    character_states: dict[str, CharacterState] = Field(default_factory=dict)
    world_state_changes: dict[str, Any] = Field(default_factory=dict, description="Significant world changes")

    # Knowledge and continuity tracking
    protagonist_knowledge: list[KnowledgeRevelation] = Field(default_factory=list)
    established_facts: dict[str, str] = Field(default_factory=dict, description="Confirmed world facts")

    # Metadata for story generation
    narrative_tone: str = Field(default="neutral", description="Current narrative tone")
    pacing_state: str = Field(default="moderate", description="Current pacing state")

    def update_timestamp(self) -> None:
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now()

    def add_plot_thread(self, description: str, priority: int = 1, characters: list[str] = None) -> str:
        """Add a new plot thread and return its ID."""
        thread = PlotThread(
            description=description,
            priority=priority,
            introduced_chapter=self.current_chapter,
            last_updated_chapter=self.current_chapter,
            related_characters=characters or []
        )
        self.active_plot_threads.append(thread)
        self.update_timestamp()
        return thread.id

    def resolve_plot_thread(self, thread_id: str) -> bool:
        """Mark a plot thread as resolved."""
        for thread in self.active_plot_threads:
            if thread.id == thread_id:
                thread.status = "resolved"
                thread.last_updated_chapter = self.current_chapter
                self.update_timestamp()
                return True
        return False

    def add_knowledge_revelation(self, concept: str, confirmation_level: str = "suspected", implications: list[str] = None) -> None:
        """Add a new knowledge revelation for the protagonist."""
        revelation = KnowledgeRevelation(
            concept=concept,
            chapter_discovered=self.current_chapter,
            confirmation_level=confirmation_level,
            implications=implications or []
        )
        self.protagonist_knowledge.append(revelation)
        self.update_timestamp()
