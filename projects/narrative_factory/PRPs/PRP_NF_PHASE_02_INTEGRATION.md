# PRP: Phase 2 - Persona & Knowledge Integration

**PRP Version:** 1.1  
**Status:** IMPLEMENTATION_AND_INTEGRATION  
**Parent Epic:** The bridging plan from MVP to the v3 vision.
**Target Agent:** Gemini

**Implementation Status:** 40% COMPLETE - Basic models exist, need PersonaManager and agent integration

---

## 1. The Goal (The "What")

> A single, concise sentence starting with a verb. What is the observable outcome of this task?

Implement PersonaManager for dynamic prompt loading and enhance agent integration with memory services to create a unified agent orchestration system with comprehensive knowledge base capabilities.

---

## 2. The Context Payload (The "With What")

> This section contains ALL information the AI needs. No external lookups allowed.

#### Current Implementation Status:
**IMPLEMENTED (40% Complete):**
- ✅ `src/agents/models.py` - Pydantic models for agent communication (StrategicBrief, ChapterBlueprint, etc.)
- ✅ `src/agents/personas.py` - Basic agent personas with hardcoded prompts
- ✅ `src/agents/prompts/` - Persona prompt files (director.txt, tactician.txt, weaver.txt, canonist.txt)
- ✅ `src/memory/qdrant.py` - Basic QdrantService class
- ✅ `src/workflows/generation.py` - Prefect workflow with basic HITL checkpoints
- ✅ Basic agent-to-agent communication via Pydantic models

#### Implementation Tasks Needed (40% → 75%):
- **BUILD:** PersonaManager class for dynamic prompt loading and caching
- **IMPLEMENT:** Enhanced agent orchestration with memory service integration
- **CREATE:** Agent lifecycle management and state tracking systems
- **ADD:** Agent communication protocols and error handling

#### Key Dependencies & Imports:
- `qdrant_client`: To interact with Qdrant from the `KnowledgeBase`.
- `src.config`: The `PersonaManager` and `KnowledgeBase` will be configured using our centralized settings.
- `src.logger`: For logging within these new modules.

#### Required Patterns & Code Snippets:

**Pattern for `PersonaManager` in `src/narrative_factory/personas.py`:**
```python
from pathlib import Path
from src.config import PERSONAS_DIR
from src.logger import get_logger

logger = get_logger(__name__)

class PersonaManager:
    def __init__(self, persona_dir: Path = PERSONAS_DIR):
        self.persona_dir = persona_dir
        self._cache = {}

    def get_system_prompt(self, persona_name: str) -> str:
        if persona_name in self._cache:
            return self._cache[persona_name]

        try:
            file_path = self.persona_dir / f"{persona_name}.txt"
            with open(file_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            self._cache[persona_name] = prompt
            return prompt
        except FileNotFoundError:
            logger.error(f"Persona file not found: {file_path}")
            # Return a generic, safe default
            return "You are a helpful assistant."
```

**Pattern for `KnowledgeBase` in `src/narrative_factory/knowledge.py`:**
```python
from qdrant_client import QdrantClient
from src.config import qdrant as qdrant_settings
from src.logger import get_logger

logger = get_logger(__name__)

class KnowledgeBase:
    def __init__(self):
        self.qdrant_client = QdrantClient(
            url=qdrant_settings.URL, 
            api_key=qdrant_settings.API_KEY
        )

    def get_prose_style_guide(self) -> str:
        # High-level method. Implementation will involve a specific
        # query to Qdrant to find the document tagged as 'style_guide'.
        # For now, can return a placeholder.
        logger.info("Fetching prose style guide...")
        return "This is a placeholder for the prose style guide."

    def find_relevant_lore(self, topic: str) -> list[str]:
        # This method will contain the RAG logic (vector search).
        logger.info(f"Searching for lore related to: {topic}")
        # Placeholder implementation
        return [f"Placeholder lore about {topic}."]
```

---

## 3. The Implementation Blueprint (The "How")

> The detailed, step-by-step logic and structure.

#### Implementation and Integration Steps:
1.  **Build PersonaManager System:**
    -   Create PersonaManager class for dynamic prompt loading from `src/agents/prompts/`
    -   Implement prompt caching and fallback mechanisms
    -   Add persona validation and error handling
    -   Create persona lifecycle management

2.  **Enhance Agent Orchestration:**
    -   Integrate PersonaManager into existing agent classes
    -   Add memory service integration to all agent types
    -   Implement agent state tracking and lifecycle management
    -   Create agent communication protocols and error handling

3.  **Expand Memory Service Integration:**
    -   Enhance QdrantService with two-tier retrieval (Spotlight + Ambient Echo)
    -   Add character profile retrieval and lore searching capabilities
    -   Implement knowledge base utility methods
    -   Create memory persistence and state management

4.  **Agent Communication Enhancement:**
    -   Expand Pydantic models for comprehensive agent-to-agent communication
    -   Add structured data validation and transformation
    -   Implement agent coordination protocols
    -   Create error handling and retry mechanisms

5.  **Workflow Integration:**
    -   Enhance Prefect workflow with improved agent orchestration
    -   Add comprehensive HITL checkpoints and decision points
    -   Implement workflow state management and recovery
    -   Create performance monitoring and optimization

---

## 4. The Validation Gate (The "Definition of Done")

> **This is the contract.** The task is complete ONLY when all commands in this section execute successfully without error.

#### L1: Static Analysis (Syntax, Style, Types)
```bash
# Ensure the new code is clean.
ruff check src/narrative_factory/
mypy src/narrative_factory/ --strict
```

#### L2: Functional Correctness (Validate Advanced Integration)

**Advanced Agent Integration Test:**
```bash
# Test sophisticated agent instantiation and persona loading
uv run python -c "
from src.agents.director import DirectorAgent
from src.agents.tactician import TacticianAgent  
from src.agents.weaver import WeaverAgent
from src.agents.canonist import CanonicistAgent
from src.memory.service import QdrantService

# Test agent instantiation with persona loading
memory_service = QdrantService()
director = DirectorAgent(memory_service=memory_service)
tactician = TacticianAgent(memory_service=memory_service)
weaver = WeaverAgent(memory_service=memory_service)
canonist = CanonicistAgent(memory_service=memory_service)

print('All advanced agents instantiated successfully')
print(f'Director persona loaded: {len(director.persona) > 100}')
print(f'Memory service operational: {memory_service is not None}')
"

# Test workflow orchestration system
uv run python -c "
from src.workflows.generation import narrative_generation_workflow
print('Workflow system imports successfully')
"

# Validate existing test suite
uv run pytest tests/test_agents.py -v --tb=short
```

**Expected Output:**
All tests should pass, confirming:
- Advanced agent system with sophisticated personas is operational
- Memory service integration works correctly
- Workflow orchestration system is functional
- Existing test suite validates the advanced implementation

**Integration Workflow Test:**
```bash
# Test the complete HITL workflow system
uv run python src/cli/main.py workflow generate --story-seed "Integration test" --dry-run --interactive=false
```
---
