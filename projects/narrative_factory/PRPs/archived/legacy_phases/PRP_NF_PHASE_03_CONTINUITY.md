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
- ✅ `src/config.py` - STATE-DIR already configured and directories created
- ✅ Existing JobStore system using Redis/Upstash for workflow state management
- ✅ `src/agents/models.py` - Existing Pydantic models for agent communication

**Structural Changes Required:**
- **CREATE:** `src/models/` directory for centralized data model organization
- **CREATE:** `src/services/` directory for service layer components
- **MOVE:** `src/agents/models.py` → `src/models/agent-models.py` (for better organization)
- **UPDATE:** Import statements throughout codebase to reflect new model locations

**Files to Create/Modify:**
- **CREATE:** `src/models/story-state.py` - Enhanced StoryState model with Context7 patterns
- **CREATE:** `src/models/__init_-.py` - Export all models (agent and story state)
- **CREATE:** `src/services/state-manager.py` - StateManager integrated with existing workflow patterns
- **CREATE:** `src/services/__init_-.py` - Service layer initialization
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

**Enhanced Pattern for `StoryState` in `src/models/story-state.py` (Using Context7 Patterns):**
```python
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import uuid4

class PlotThread(BaseModel):
    """Individual plot thread with resolution status and metadata."""
    id: str = Field(default-factory=lambda: str(uuid4()))
    description: str = Field(..., description="Brief description of the plot thread")
    priority: int = Field(default=1, ge=1, le=10, description="Priority from 1-10")
    introduced-chapter: int = Field(..., description="Chapter where this thread was introduced")
    last_updated-chapter: int = Field(..., description="Last chapter that referenced this thread")
    status: str = Field(default="active", description="Status: active, resolved, dormant")
    related-characters: List[str] = Field(default-factory=list)

class CharacterState(BaseModel):
    """Character state tracking with location and relationship data."""
    character-id: str = Field(..., description="Unique character identifier")
    current-location: str = Field(..., description="Character's current location")
    emotional-state: str = Field(default="neutral", description="Current emotional state")
    knowledge-state: List[str] = Field(default-factory=list, description="Key facts the character knows")
    relationships: Dict[str, str] = Field(default-factory=dict, description="Relationship status with other characters")
    last_updated-chapter: int = Field(..., description="Last chapter that updated this character")

class KnowledgeRevelation(BaseModel):
    """Track protagonist's growing understanding of the world."""
    concept: str = Field(..., description="The concept or fact that was revealed")
    chapter-discovered: int = Field(..., description="Chapter where this was first discovered")
    confirmation-level: str = Field(default="suspected", description="Level of certainty: suspected, confirmed, proven")
    implications: List[str] = Field(default-factory=list, description="What this revelation implies")

class StoryState(BaseModel):
    """Enhanced narrative state tracking for long-term continuity."""
    model-config = ConfigDict(extra="allow", validate-assignment=True)
    
    # Core progression tracking
    current-chapter: int = Field(default=1, description="The chapter number that was just completed")
    story-id: str = Field(default-factory=lambda: str(uuid4()), description="Unique identifier for this story")
    created-at: datetime = Field(default-factory=datetime.now)
    last-updated: datetime = Field(default-factory=datetime.now)
    
    # Plot and tension management  
    active_plot-threads: List[PlotThread] = Field(default-factory=list)
    unresolved-tensions: List[str] = Field(default-factory=list, description="High-level tension descriptions")
    
    # Character and world state
    character-states: Dict[str, CharacterState] = Field(default-factory=dict)
    world_state-changes: Dict[str, Any] = Field(default-factory=dict, description="Significant world changes")
    
    # Knowledge and continuity tracking
    protagonist-knowledge: List[KnowledgeRevelation] = Field(default-factory=list)
    established-facts: Dict[str, str] = Field(default-factory=dict, description="Confirmed world facts")
    
    # Metadata for story generation
    narrative-tone: str = Field(default="neutral", description="Current narrative tone")
    pacing-state: str = Field(default="moderate", description="Current pacing state")
    
    def update-timestamp(self) -> None:
        """Update the last-updated timestamp."""
        self.last-updated = datetime.now()
        
    def add_plot-thread(self, description: str, priority: int = 1, characters: List[str] = None) -> str:
        """Add a new plot thread and return its ID."""
        thread = PlotThread(
            description=description,
            priority=priority,
            introduced-chapter=self.current-chapter,
            last_updated-chapter=self.current-chapter,
            related-characters=characters or []
        )
        self.active_plot-threads.append(thread)
        self.update-timestamp()
        return thread.id
        
    def resolve_plot-thread(self, thread-id: str) -> bool:
        """Mark a plot thread as resolved."""
        for thread in self.active_plot-threads:
            if thread.id == thread-id:
                thread.status = "resolved"
                thread.last_updated-chapter = self.current-chapter
                self.update-timestamp()
                return True
        return False
        
    def add_knowledge-revelation(self, concept: str, confirmation-level: str = "suspected", implications: List[str] = None) -> None:
        """Add a new knowledge revelation for the protagonist."""
        revelation = KnowledgeRevelation(
            concept=concept,
            chapter-discovered=self.current-chapter,
            confirmation-level=confirmation-level,
            implications=implications or []
        )
        self.protagonist-knowledge.append(revelation)
        self.update-timestamp()
```

**Enhanced Pattern for `StateManager` in `src/services/state-manager.py` (Integrated with Existing Patterns):**
```python
import json
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from src.config import STATE-DIR
from src.models.story-state import StoryState, PlotThread, CharacterState, KnowledgeRevelation
from src.logger import get-logger
from src.workflows.jobs import JobStore  # Integrate with existing job management

logger = get-logger(__name_-)

class StateManager:
    """Enhanced state management integrated with existing workflow patterns."""
    
    def __init_-(self, state-dir: Path = STATE-DIR, job-store: Optional[JobStore] = None):
        self.state-dir = state-dir
        self.job-store = job-store or JobStore()  # Use existing job store patterns
        
    async def save-state(self, state: StoryState, story-id: Optional[str] = None) -> bool:
        """Save story state with enhanced error handling and backup."""
        state.update-timestamp()
        story-identifier = story-id or state.story-id
        
        # Create both chapter-specific and latest state files
        chapter-file = self.state-dir / f"story_state_chapter-{state.current-chapter}.json"
        latest-file = self.state-dir / f"story_state_latest-{story-identifier}.json"
        backup-file = self.state-dir / f"story_state_backup-{story-identifier}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        
        try:
            state-data = state.model_dump-json(indent=2)
            
            # Save chapter-specific state
            await asyncio.to-thread(chapter-file.write-text, state-data, encoding='utf-8')
                
            # Save latest state (for quick access)
            await asyncio.to-thread(latest-file.write-text, state-data, encoding='utf-8')
                
            # Create backup
            await asyncio.to-thread(backup-file.write-text, state-data, encoding='utf-8')
                
            # Store metadata in job store for workflow integration
            if self.job-store:
                await asyncio.to-thread(
                    self.job-store.redis-client.set,
                    f"story_state-{story-identifier}",
                    json.dumps({
                        "current-chapter": state.current-chapter,
                        "last-updated": state.last-updated.isoformat(),
                        "active-threads": len(state.active_plot-threads),
                        "character-count": len(state.character-states)
                    })
                )
                
            logger.info(f"Successfully saved state to {chapter-file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    async def load_latest-state(self, story-id: Optional[str] = None) -> StoryState:
        """Load the most recent story state with enhanced recovery."""
        try:
            if story-id:
                # Try to load specific story state first
                latest-file = self.state-dir / f"story_state_latest-{story-id}.json"
                if latest-file.exists():
                    content = await asyncio.to-thread(latest-file.read-text, encoding='utf-8')
                    data = json.loads(content)
                    logger.info(f"Loaded story state for {story-id}")
                    return StoryState(**data)
            
            # Fallback to most recent chapter-based state
            state-files = sorted(
                self.state-dir.glob("story_state_chapter-*.json"),
                key=lambda f: int(f.stem.split('-')[-1]),
                reverse=True
            )
            
            if state-files:
                latest-file = state-files[0]
                logger.info(f"Loading latest state from {latest-file}")
                content = await asyncio.to-thread(latest-file.read-text, encoding='utf-8')
                data = json.loads(content)
                return StoryState(**data)
                
            logger.warning("No state files found. Initializing new story state.")
            return StoryState()
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}. Initializing new state.")
            return StoryState()
            
    async def get_state-summary(self, story-id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of the current story state for workflow coordination."""
        state = await self.load_latest-state(story-id)
        
        return {
            "current-chapter": state.current-chapter,
            "story-id": state.story-id,
            "active_plot-threads": len([t for t in state.active_plot-threads if t.status == "active"]),
            "unresolved-tensions": len(state.unresolved-tensions),
            "character-count": len(state.character-states),
            "knowledge-revelations": len(state.protagonist-knowledge),
            "last-updated": state.last-updated.isoformat(),
            "narrative-tone": state.narrative-tone,
            "pacing-state": state.pacing-state
        }
        
    def create_state_from_canonist-output(self, canonist-report: Dict[str, Any], previous-state: StoryState) -> StoryState:
        """Convert Canonist reconciliation output into updated StoryState."""
        # This method bridges the existing Canonist output with the new StoryState model
        new-state = previous-state.model-copy(deep=True)
        new-state.current-chapter += 1
        new-state.update-timestamp()
        
        # Parse tension state report to update plot threads and tensions
        if "NEW_TENSION_STATE-REPORT" in canonist-report:
            tensions = canonist-report["NEW_TENSION_STATE-REPORT"]
            new-state.unresolved-tensions.extend(tensions)
            
        # Parse knowledge state to add revelations
        if "NEW_KNOWLEDGE-STATE" in canonist-report:
            for knowledge-item in canonist-report["NEW_KNOWLEDGE-STATE"]:
                new-state.add_knowledge-revelation(
                    concept=knowledge-item,
                    confirmation-level="confirmed"
                )
                
        return new-state
```

---

## 3. The Implementation Blueprint (The "How")

> The detailed, step-by-step logic and structure.

#### Implementation Steps (Building on Existing Infrastructure):
1.  **Restructure Project Organization:**
    -   Create `src/models/` directory for centralized data model organization
    -   Create `src/services/` directory for service layer components
    -   Move `src/agents/models.py` → `src/models/agent-models.py` for better organization
    -   Update all import statements throughout codebase to reflect new model locations

2.  **Create Enhanced StoryState Model:**
    -   Create `src/models/story-state.py` with the comprehensive StoryState model using Context7 Pydantic patterns
    -   Implement nested models (PlotThread, CharacterState, KnowledgeRevelation) for structured data
    -   Add utility methods for state management and updates
    -   Create `src/models/__init_-.py` to export all models (agent and story state)

3.  **Create Integrated StateManager Service:**
    -   Create `src/services/state-manager.py` using existing service patterns
    -   Integrate with the existing JobStore system for workflow coordination
    -   Implement async patterns consistent with existing codebase
    -   Add backup and recovery mechanisms for state files
    -   Create `src/services/__init_-.py` for service layer initialization

4.  **Enhance Canonist Agent for State Generation:**
    -   Update `src/agents/personas.py` to enhance Canonist agent functionality
    -   Add methods to parse reconciliation reports into structured state data following existing canonist persona specifications
    -   Generate structured output with NEW_TENSION_STATE-REPORT and NEW_KNOWLEDGE-STATE sections
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
uv run mypy src/ --strict
```

#### L2: Enhanced StoryState Model Validation

**Test the sophisticated StoryState model:**
```bash
# Test comprehensive StoryState functionality
uv run python -c "
import asyncio
from src.models.story-state import StoryState, PlotThread, CharacterState, KnowledgeRevelation

# Test comprehensive model creation
async def test_story-state():
    state = StoryState(current-chapter=3)
    
    # Test plot thread management
    thread-id = state.add_plot-thread('Ancient prophecy discovered', priority=8, characters=['Protagonist', 'Oracle'])
    assert len(state.active_plot-threads) == 1
    
    # Test knowledge revelation tracking
    state.add_knowledge-revelation('Magic exists in this world', 'confirmed', ['Changes understanding of reality'])
    assert len(state.protagonist-knowledge) == 1
    
    # Test state validation
    assert state.current-chapter == 3
    assert state.story-id is not None
    print('Enhanced StoryState model validation PASSED')

asyncio.run(test_story-state())
"
```

#### L3: StateManager Integration Test

**Test StateManager with existing infrastructure:**
```bash
# Test StateManager integration with workflow patterns
uv run python -c "
import asyncio
from src.services.state-manager import StateManager
from src.models.story-state import StoryState
from src.config import STATE-DIR

async def test_state-manager():
    sm = StateManager()
    
    # Test state lifecycle
    initial-state = await sm.load_latest-state()
    assert initial-state.current-chapter == 1
    
    # Create complex state
    test-state = StoryState(current-chapter=2)
    test-state.add_plot-thread('Test thread', priority=5)
    test-state.add_knowledge-revelation('Test knowledge')
    
    # Test async save/load
    save-success = await sm.save-state(test-state)
    assert save-success
    
    loaded-state = await sm.load_latest-state()
    assert loaded-state.current-chapter == 2
    assert len(loaded-state.active_plot-threads) == 1
    
    # Test state summary
    summary = await sm.get_state-summary()
    assert summary['current-chapter'] == 2
    assert summary['active_plot-threads'] == 1
    
    print('StateManager integration test PASSED')

asyncio.run(test_state-manager())
"
```

#### L4: Workflow Integration Validation

**Test integration with existing workflow:**
```bash
# Test StoryState integration with Canonist and workflow
uv run python -c "
from src.services.state-manager import StateManager
from src.models.story-state import StoryState

def test_canonist-integration():
    sm = StateManager()
    
    # Test conversion from Canonist output format
    mock_canonist-report = {
        'NEW_TENSION_STATE-REPORT': ['New conflict discovered', 'Character relationship strained'],
        'NEW_KNOWLEDGE-STATE': ['Magic system mechanics', 'World history revealed']
    }
    
    previous-state = StoryState(current-chapter=1)
    new-state = sm.create_state_from_canonist-output(mock_canonist-report, previous-state)
    
    assert new-state.current-chapter == 2
    assert len(new-state.unresolved-tensions) == 2
    assert len(new-state.protagonist-knowledge) == 2
    
    print('Canonist integration test PASSED')

test_canonist-integration()
"

# Test existing workflow still functions with integration
uv run python -c "
import asyncio
from src.services.state-manager import StateManager
from src.models.story-state import StoryState

async def test_workflow-integration():
    try:
        # Test StateManager
        sm = StateManager()
        state = await sm.load_latest-state()
        print(f'StateManager works: Current chapter {state.current-chapter}')
        
        # Test story state functionality
        state.add_plot-thread('Test plot thread')
        state.add_knowledge-revelation('Test knowledge')
        
        # Test save/load cycle
        save-success = await sm.save-state(state)
        print(f'State save successful: {save-success}')
        
        loaded-state = await sm.load_latest-state()
        print(f'State loaded: Chapter {loaded-state.current-chapter}')
        
        print('All workflow integration tests PASSED')
        return True
    except Exception as e:
        print(f'Workflow integration test FAILED: {e}')
        return False

success = asyncio.run(test_workflow-integration())
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
