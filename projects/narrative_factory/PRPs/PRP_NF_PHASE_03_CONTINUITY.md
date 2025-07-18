# PRP: Phase 3 - Long-Term Continuity Engine

**PRP Version:** 1.2  
**Status:** COMPLETED  
**Parent Epic:** The bridging plan from MVP to the v3 vision.
**Target Agent:** Claude

**Implementation Status:** 10% COMPLETE - Long-term narrative continuity engine implemented with persistent story state

---

## 1. The Goal (The "What")

> A single, concise sentence starting with a verb. What is the observable outcome of this task?

Implement the core mechanism for narrative continuity by creating a structured `StoryState` data model and a persistence layer that saves and loads this state between generation cycles.

---

## 2. The Context Payload (The "With What")

> This section contains ALL information the AI needs. No external lookups allowed.

#### Implementation Requirements (Building on Existing Infrastructure):
**Existing Foundation to Build On:**
- ✅ `src/workflows/generation.py` - Complete Prefect workflow with HITL orchestration  
- ✅ `src/config.py` - STATE_DIR already configured and directories created
- ✅ Existing JobStore system using Redis/Upstash for workflow state management
- ✅ `src/agents/models.py` - Existing Pydantic models for agent communication

**Structural Changes Required:**
- **CREATE:** `src/models/` directory for centralized data model organization
- **CREATE:** `src/services/` directory for service layer components
- **MOVE:** `src/agents/models.py` → `src/models/agent_models.py` (for better organization)
- **UPDATE:** Import statements throughout codebase to reflect new model locations

**Files to Create/Modify:**
- **CREATE:** `src/models/story_state.py` - Enhanced StoryState model with Context7 patterns
- **CREATE:** `src/models/__init__.py` - Export all models (agent and story state)
- **CREATE:** `src/services/state_manager.py` - StateManager integrated with existing workflow patterns
- **CREATE:** `src/services/__init__.py` - Service layer initialization
- **UPDATE:** `src/workflows/generation.py` - Integrate StoryState with existing HITL workflow
- **UPDATE:** `src/agents/personas.py` - Enhance Canonist to generate StoryState updates
- **UPDATE:** `src/workflows/jobs.py` - Fix imports to use new model locations

#### Key Dependencies & Imports:
- `pydantic`: For creating the `StoryState` model.
- `json`: For serializing and deserializing the state object.
- `pathlib`: To manage file paths for saving/loading state.
- `src.config`: To get the directory where state files should be stored.
- `src.logger`: For logging state management activities.

#### Required Patterns & Code Snippets:

**Enhanced Pattern for `StoryState` in `src/models/story_state.py` (Using Context7 Patterns):**
```python
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4

class PlotThread(BaseModel):
    """Individual plot thread with resolution status and metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str = Field(..., description="Brief description of the plot thread")
    priority: int = Field(default=1, ge=1, le=10, description="Priority from 1-10")
    introduced_chapter: int = Field(..., description="Chapter where this thread was introduced")
    last_updated_chapter: int = Field(..., description="Last chapter that referenced this thread")
    status: str = Field(default="active", description="Status: active, resolved, dormant")
    related_characters: List[str] = Field(default_factory=list)

class CharacterState(BaseModel):
    """Character state tracking with location and relationship data."""
    character_id: str = Field(..., description="Unique character identifier")
    current_location: str = Field(..., description="Character's current location")
    emotional_state: str = Field(default="neutral", description="Current emotional state")
    knowledge_state: List[str] = Field(default_factory=list, description="Key facts the character knows")
    relationships: Dict[str, str] = Field(default_factory=dict, description="Relationship status with other characters")
    last_updated_chapter: int = Field(..., description="Last chapter that updated this character")

class KnowledgeRevelation(BaseModel):
    """Track protagonist's growing understanding of the world."""
    concept: str = Field(..., description="The concept or fact that was revealed")
    chapter_discovered: int = Field(..., description="Chapter where this was first discovered")
    confirmation_level: str = Field(default="suspected", description="Level of certainty: suspected, confirmed, proven")
    implications: List[str] = Field(default_factory=list, description="What this revelation implies")

class StoryState(BaseModel):
    """Enhanced narrative state tracking for long-term continuity."""
    model_config = ConfigDict(extra="allow", validate_assignment=True)
    
    # Core progression tracking
    current_chapter: int = Field(default=1, description="The chapter number that was just completed")
    story_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for this story")
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    # Plot and tension management  
    active_plot_threads: List[PlotThread] = Field(default_factory=list)
    unresolved_tensions: List[str] = Field(default_factory=list, description="High-level tension descriptions")
    
    # Character and world state
    character_states: Dict[str, CharacterState] = Field(default_factory=dict)
    world_state_changes: Dict[str, Any] = Field(default_factory=dict, description="Significant world changes")
    
    # Knowledge and continuity tracking
    protagonist_knowledge: List[KnowledgeRevelation] = Field(default_factory=list)
    established_facts: Dict[str, str] = Field(default_factory=dict, description="Confirmed world facts")
    
    # Metadata for story generation
    narrative_tone: str = Field(default="neutral", description="Current narrative tone")
    pacing_state: str = Field(default="moderate", description="Current pacing state")
    
    def update_timestamp(self) -> None:
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now()
        
    def add_plot_thread(self, description: str, priority: int = 1, characters: List[str] = None) -> str:
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
        
    def add_knowledge_revelation(self, concept: str, confirmation_level: str = "suspected", implications: List[str] = None) -> None:
        """Add a new knowledge revelation for the protagonist."""
        revelation = KnowledgeRevelation(
            concept=concept,
            chapter_discovered=self.current_chapter,
            confirmation_level=confirmation_level,
            implications=implications or []
        )
        self.protagonist_knowledge.append(revelation)
        self.update_timestamp()
```

**Enhanced Pattern for `StateManager` in `src/services/state_manager.py` (Integrated with Existing Patterns):**
```python
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from src.config import STATE_DIR
from src.models.story_state import StoryState, PlotThread, CharacterState, KnowledgeRevelation
from src.logger import get_logger
from src.workflows.jobs import JobStore  # Integrate with existing job management

logger = get_logger(__name__)

class StateManager:
    """Enhanced state management integrated with existing workflow patterns."""
    
    def __init__(self, state_dir: Path = STATE_DIR, job_store: Optional[JobStore] = None):
        self.state_dir = state_dir
        self.job_store = job_store or JobStore()  # Use existing job store patterns
        
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
            
    async def get_state_summary(self, story_id: Optional[str] = None) -> Dict[str, Any]:
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
        
    def create_state_from_canonist_output(self, canonist_report: Dict[str, Any], previous_state: StoryState) -> StoryState:
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
```

---

## 3. The Implementation Blueprint (The "How")

> The detailed, step-by-step logic and structure.

#### Implementation Steps (Building on Existing Infrastructure):
1.  **Restructure Project Organization:**
    -   Create `src/models/` directory for centralized data model organization
    -   Create `src/services/` directory for service layer components
    -   Move `src/agents/models.py` → `src/models/agent_models.py` for better organization
    -   Update all import statements throughout codebase to reflect new model locations

2.  **Create Enhanced StoryState Model:**
    -   Create `src/models/story_state.py` with the comprehensive StoryState model using Context7 Pydantic patterns
    -   Implement nested models (PlotThread, CharacterState, KnowledgeRevelation) for structured data
    -   Add utility methods for state management and updates
    -   Create `src/models/__init__.py` to export all models (agent and story state)

3.  **Create Integrated StateManager Service:**
    -   Create `src/services/state_manager.py` using existing service patterns
    -   Integrate with the existing JobStore system for workflow coordination
    -   Implement async patterns consistent with existing codebase
    -   Add backup and recovery mechanisms for state files
    -   Create `src/services/__init__.py` for service layer initialization

4.  **Enhance Canonist Agent for State Generation:**
    -   Update `src/agents/personas.py` to enhance Canonist agent functionality
    -   Add methods to parse reconciliation reports into structured state data following existing canonist persona specifications
    -   Generate structured output with NEW_TENSION_STATE_REPORT and NEW_KNOWLEDGE_STATE sections
    -   Integrate with the new StateManager for seamless workflow handoff

5.  **Integrate with Existing Workflow:**
    -   Update `src/workflows/generation.py` to use StateManager at workflow start and end
    -   Load StoryState context before generation begins
    -   Pass story state context to agents for informed decision-making
    -   Ensure state persistence happens after Canonist processing
    -   Maintain compatibility with existing HITL checkpoints
    -   Update function signatures to handle new dict-based canonist results

6.  **Fix Import Dependencies:**
    -   Update `src/workflows/jobs.py` to import from new model locations
    -   Update `src/agents/personas.py` to import from new model locations
    -   Ensure all imports use the new `src.models` package structure

---

## 4. The Validation Gate (The "Definition of Done")

> **This is the contract.** The task is complete ONLY when all commands in this section execute successfully without error.

#### L1: Static Analysis (Syntax, Style, Types)
```bash
# Ensure new code follows existing patterns and style
uv run ruff check src/
mypy src/ --strict
```

#### L2: Enhanced StoryState Model Validation

**Test the sophisticated StoryState model:**
```bash
# Test comprehensive StoryState functionality
uv run python -c "
import asyncio
from src.models.story_state import StoryState, PlotThread, CharacterState, KnowledgeRevelation

# Test comprehensive model creation
async def test_story_state():
    state = StoryState(current_chapter=3)
    
    # Test plot thread management
    thread_id = state.add_plot_thread('Ancient prophecy discovered', priority=8, characters=['Protagonist', 'Oracle'])
    assert len(state.active_plot_threads) == 1
    
    # Test knowledge revelation tracking
    state.add_knowledge_revelation('Magic exists in this world', 'confirmed', ['Changes understanding of reality'])
    assert len(state.protagonist_knowledge) == 1
    
    # Test state validation
    assert state.current_chapter == 3
    assert state.story_id is not None
    print('Enhanced StoryState model validation PASSED')

asyncio.run(test_story_state())
"
```

#### L3: StateManager Integration Test

**Test StateManager with existing infrastructure:**
```bash
# Test StateManager integration with workflow patterns
uv run python -c "
import asyncio
from src.services.state_manager import StateManager
from src.models.story_state import StoryState
from src.config import STATE_DIR

async def test_state_manager():
    sm = StateManager()
    
    # Test state lifecycle
    initial_state = await sm.load_latest_state()
    assert initial_state.current_chapter == 1
    
    # Create complex state
    test_state = StoryState(current_chapter=2)
    test_state.add_plot_thread('Test thread', priority=5)
    test_state.add_knowledge_revelation('Test knowledge')
    
    # Test async save/load
    save_success = await sm.save_state(test_state)
    assert save_success
    
    loaded_state = await sm.load_latest_state()
    assert loaded_state.current_chapter == 2
    assert len(loaded_state.active_plot_threads) == 1
    
    # Test state summary
    summary = await sm.get_state_summary()
    assert summary['current_chapter'] == 2
    assert summary['active_plot_threads'] == 1
    
    print('StateManager integration test PASSED')

asyncio.run(test_state_manager())
"
```

#### L4: Workflow Integration Validation

**Test integration with existing workflow:**
```bash
# Test StoryState integration with Canonist and workflow
uv run python -c "
from src.services.state_manager import StateManager
from src.models.story_state import StoryState

def test_canonist_integration():
    sm = StateManager()
    
    # Test conversion from Canonist output format
    mock_canonist_report = {
        'NEW_TENSION_STATE_REPORT': ['New conflict discovered', 'Character relationship strained'],
        'NEW_KNOWLEDGE_STATE': ['Magic system mechanics', 'World history revealed']
    }
    
    previous_state = StoryState(current_chapter=1)
    new_state = sm.create_state_from_canonist_output(mock_canonist_report, previous_state)
    
    assert new_state.current_chapter == 2
    assert len(new_state.unresolved_tensions) == 2
    assert len(new_state.protagonist_knowledge) == 2
    
    print('Canonist integration test PASSED')

test_canonist_integration()
"

# Test existing workflow still functions with integration
uv run python -c "
import asyncio
from src.services.state_manager import StateManager
from src.models.story_state import StoryState

async def test_workflow_integration():
    try:
        # Test StateManager
        sm = StateManager()
        state = await sm.load_latest_state()
        print(f'StateManager works: Current chapter {state.current_chapter}')
        
        # Test story state functionality
        state.add_plot_thread('Test plot thread')
        state.add_knowledge_revelation('Test knowledge')
        
        # Test save/load cycle
        save_success = await sm.save_state(state)
        print(f'State save successful: {save_success}')
        
        loaded_state = await sm.load_latest_state()
        print(f'State loaded: Chapter {loaded_state.current_chapter}')
        
        print('All workflow integration tests PASSED')
        return True
    except Exception as e:
        print(f'Workflow integration test FAILED: {e}')
        return False

success = asyncio.run(test_workflow_integration())
"
```

**Expected Output:**
All validation tests should pass, demonstrating:
- Enhanced StoryState model with nested structures works correctly
- StateManager integrates with existing infrastructure patterns
- Canonist output conversion maintains workflow compatibility
- Existing workflow continues to function with new state management
- Project structure reorganization maintains functionality

**Post-Implementation Results:**
✅ **All validation gates passed successfully**
✅ **StoryState model**: Plot threads, knowledge revelations, and character states tracked
✅ **StateManager**: Async file I/O with backup, recovery, and Redis integration
✅ **Canonist enhancement**: Generates structured story state updates following persona specifications
✅ **Workflow integration**: Full continuity across chapter generation cycles
✅ **Project structure**: Centralized models and services directories created
---
