import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.config import STATE_DIR
from src.logger import get_logger
from src.models.story_state import StoryState
from src.workflows.jobs import JobStore


logger = get_logger(__name__)

class StateManager:
    """Enhanced state management integrated with existing workflow patterns."""

    def __init__(self, state_dir: Path = STATE_DIR, job_store: Optional[JobStore] = None):
        self.state_dir = state_dir
        self.job_store = job_store or JobStore()

    async def save_state(self, state: StoryState, story_id: Optional[str] = None) -> bool:
        """Save story state with enhanced error handling and backup."""
        state.update_timestamp()
        story_identifier = story_id or state.story_id

        # Create both chapter-specific and latest state files
        chapter_file = self.state_dir / f"story_state_chapter_{state.current_chapter}.json"
        latest_file = self.state_dir / f"story_state_latest_{story_identifier}.json"
        backup_file = self.state_dir / f"story_state_backup_{story_identifier}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            state_data = state.model_dump_json(indent=2)

            # Save chapter-specific state
            await asyncio.to_thread(chapter_file.write_text, state_data, encoding='utf-8')

            # Save latest state (for quick access)
            await asyncio.to_thread(latest_file.write_text, state_data, encoding='utf-8')

            # Create backup
            await asyncio.to_thread(backup_file.write_text, state_data, encoding='utf-8')

            # Store metadata in job store for workflow integration
            if self.job_store:
                await asyncio.to_thread(
                    self.job_store.redis_client.set,
                    f"story_state_{story_identifier}",
                    json.dumps({
                        "current_chapter": state.current_chapter,
                        "last_updated": state.last_updated.isoformat(),
                        "active_threads": len(state.active_plot_threads),
                        "character_count": len(state.character_states)
                    })
                )

            logger.info(f"Successfully saved state to {chapter_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    async def load_latest_state(self, story_id: Optional[str] = None) -> StoryState:
        """Load the most recent story state with enhanced recovery."""
        try:
            if story_id:
                # Try to load specific story state first
                latest_file = self.state_dir / f"story_state_latest_{story_id}.json"
                if latest_file.exists():
                    content = await asyncio.to_thread(latest_file.read_text, encoding='utf-8')
                    data = json.loads(content)
                    logger.info(f"Loaded story state for {story_id}")
                    return StoryState(**data)

            # Fallback to most recent chapter-based state
            state_files = sorted(
                self.state_dir.glob("story_state_chapter_*.json"),
                key=lambda f: int(f.stem.split('_')[-1]),
                reverse=True
            )

            if state_files:
                latest_file = state_files[0]
                logger.info(f"Loading latest state from {latest_file}")
                content = await asyncio.to_thread(latest_file.read_text, encoding='utf-8')
                data = json.loads(content)
                return StoryState(**data)

            logger.warning("No state files found. Initializing new story state.")
            return StoryState()

        except Exception as e:
            logger.error(f"Failed to load state: {e}. Initializing new state.")
            return StoryState()

    async def get_state_summary(self, story_id: Optional[str] = None) -> dict[str, Any]:
        """Get a summary of the current story state for workflow coordination."""
        state = await self.load_latest_state(story_id)

        return {
            "current_chapter": state.current_chapter,
            "story_id": state.story_id,
            "active_plot_threads": len([t for t in state.active_plot_threads if t.status == "active"]),
            "unresolved_tensions": len(state.unresolved_tensions),
            "character_count": len(state.character_states),
            "knowledge_revelations": len(state.protagonist_knowledge),
            "last_updated": state.last_updated.isoformat(),
            "narrative_tone": state.narrative_tone,
            "pacing_state": state.pacing_state
        }

    def create_state_from_canonist_output(self, canonist_report: dict[str, Any], previous_state: StoryState) -> StoryState:
        """Convert Canonist reconciliation output into updated StoryState."""
        # This method bridges the existing Canonist output with the new StoryState model
        new_state = previous_state.model_copy(deep=True)
        new_state.current_chapter += 1
        new_state.update_timestamp()

        # Parse tension state report to update plot threads and tensions
        if "NEW_TENSION_STATE_REPORT" in canonist_report:
            tensions = canonist_report["NEW_TENSION_STATE_REPORT"]
            new_state.unresolved_tensions.extend(tensions)

        # Parse knowledge state to add revelations
        if "NEW_KNOWLEDGE_STATE" in canonist_report:
            for knowledge_item in canonist_report["NEW_KNOWLEDGE_STATE"]:
                new_state.add_knowledge_revelation(
                    concept=knowledge_item,
                    confirmation_level="confirmed"
                )

        return new_state
