name: "MVP Phase 2: Agent Core Implementation"
description: "Defines and implements the core Agent classes that form the cognitive engine of the Narrative Factory."

---

## Goal

To create a robust, reusable, and well-defined set of Python classes for the AI agents (Director, Tactician, Weaver, Canonist). This includes a base `Agent` class and specific subclasses that **use and return strongly-typed Pydantic models for all inputs and outputs.**

## Why

- **Abstraction:** A base class prevents code duplication by handling shared logic like LLM client initialization.
- **Clarity & Type Safety:** Using Pydantic models as data contracts makes the data flow between agents explicit, validated, and less prone to runtime errors.
- **Testability:** Encapsulating agent logic within classes that operate on clear data contracts allows for targeted and effective unit testing.

## What

### Success Criteria

- [ ] A new `src/narrative-factory/agents/models.py` file contains the Pydantic models for `StrategicBrief` and `ChapterBlueprint`.
- [ ] A base `Agent` class is created in `src/narrative-factory/agents/personas.py`.
- [ ] Subclasses for `Director`, `Tactician`, `Weaver`, and `Canonist` are created, inheriting from the base `Agent`.
- [ ] The `DirectorAgent.execute` method is updated to return a `StrategicBrief` Pydantic model.
- [ ] The `TacticianAgent.execute` method is updated to accept a `StrategicBrief` model as input and return a `ChapterBlueprint` model.
- [ ] Unit tests are created to verify that agents produce the correct, validated Pydantic models.

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for Pydantic data validation patterns
use context7 for library /pydantic/pydantic topic "BaseModel and Field validation"

# Use Context7 for OpenAI Python SDK
use context7 for library /openai/openai-python topic "client initialization and structured outputs"

# Use Context7 for pytest mocking patterns
use context7 for library /pytest-dev/pytest-mock topic "mocking external dependencies"

# Use Context7 for Google Generative AI SDK
use context7 for library /google/generativeai topic "client setup and model interaction"

# Use Context7 for Pydantic AI integration
use context7 for library /context7/ai_pydantic-dev topic "LLM integration and structured responses"

# Use Context7 for OpenAI structured outputs
use context7 for library /openai/openai-python topic "parse chat completions with Pydantic models"

# Use Context7 for advanced Pydantic validation
use context7 for library /context7/pydantic-dev topic "BaseModel validation and structured outputs"
```

**Why Context7 Enhances This PRP:**
- **Pydantic**: Latest BaseModel patterns, Field specifications, and validation techniques for structured agent outputs
- **OpenAI SDK**: Current client initialization patterns and structured output handling including `client.chat.completions.parse()` method
- **Pytest Mock**: Modern mocking patterns for LLM clients and external dependencies
- **Google GenAI**: Up-to-date client setup and model interaction patterns
- **Pydantic AI**: Advanced LLM integration patterns with structured response validation and streaming support
- **Structured Outputs**: OpenAI's `parse()` method for automatic Pydantic model validation from LLM responses
- **Advanced Validation**: Comprehensive validation patterns including partial validation, error handling, and cyclic reference support

**Critical Context7 Patterns for Agent Core:**
- **Structured LLM Responses**: Use `client.chat.completions.parse(response-format=YourModel)` for automatic validation
- **Validation Error Handling**: Implement try/catch blocks for `ValidationError` with structured error reporting
- **Partial Validation**: Support for `allow-partial=True` during streaming or incomplete responses
- **Custom Validators**: Use `@field-validator` decorators for complex business logic validation
- **Agent Response Models**: Define clear Pydantic models for each agent type (Director, Tactician, Weaver, Canonist)
- **Type Safety**: Leverage `typing.Annotated` and `Field()` for enhanced type hints and validation constraints

## All Needed Context

### Documentation & References

```yaml
- file: /workspaces/PRPs-agentic-eng/.personas/DIRECTOR.txt
  why: Example of a persona file that the Agent class will need to parse.

- file: /workspaces/PRPs-agentic-eng/projects/narrative-factory/PRPs/PRP_MVP_01_SCAFFOLD.md
  why: Defines the location of the new `models.py` file.

- doc: https://pydantic-docs.helpmanual.io/
  why: Pydantic models are mandatory for all structured inputs and outputs from agents to ensure type safety and validation.
```

## Implementation Blueprint

### Data models and structure

The following Pydantic models **must be created** in `src/narrative-factory/agents/models.py`. They are the official data contracts for the Director and Tactician agents.

```python
# In: src/narrative-factory/agents/models.py

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import datetime
from uuid import UUID, uuid4

# MVP Simplified Models based on actual persona requirements

class StrategicBrief(BaseModel):
    """
    The official mission brief from the Director to the Tactician.
    Based on Director persona PROTOCOL 1: PROPULSION PROTOCOL output format.
    """
    # Header fields
    title: str = Field(description="A working title for the chapter/sequence")
    scope: Literal["SINGLE-CHAPTER", "MULTI_CHAPTER-ARC", "SAGA-GENESIS"] = Field(description="Strategic scope determination")
    estimated-chapters: str = Field(description="Director's estimate, e.g., '2-4' or '1'")
    pov_character-id: str = Field(description="Character name for POV")
    
    # Body fields  
    goal: str = Field(description="Clear, one-sentence objective for the scene/sequence")
    key-events: List[str] = Field(description="Essential plot points framed as event descriptors")
    emotional_turning-point: str = Field(description="Core emotional shift directive")
    cliffhanger-concept: str = Field(description="One-sentence concept for chapter's final hook")

class ChapterBeatStructure(BaseModel):
    """
    Based on Tactician persona MANDATORY BEAT STRUCTURE from PROTOCOL 0.
    Each beat provides the Weaver with everything needed for compelling prose.
    """
    moment-anchor: str = Field(description="1-2 sentence present-tense physical action and sensory detail")
    internal-shift: str = Field(description="Character's from->to emotional/cognitive journey within this beat")
    micro-conflict: str = Field(description="Specific point of friction, resistance, or complication")
    narrative-payoff: Optional[str] = Field(None, description="System message, discovery, or key reveal for this beat")
    pacing-density: Literal["Expansive", "Moderate", "Compressed", "Crescendo", "Decrescendo"] = Field(
        default="Moderate", description="Pacing directive from Tactician appendix"
    )

class ChapterMetadata(BaseModel):
    """
    Based on Tactician persona step 7: Generate Chapter Metadata.
    """
    chapter-goal: str = Field(description="Core narrative objective in single sentence")
    hook-concept: str = Field(description="Core concept of final HOOK beat in single sentence") 
    discovery-log: List[str] = Field(description="Key conceptual revelations protagonist makes")

class ChapterBlueprint(BaseModel):
    """
    The detailed, beat-by-beat blueprint from the Tactician to the Weaver.
    Based on Tactician persona PROTOCOL 0 final output structure.
    """
    # Section 1: Metadata
    metadata: ChapterMetadata = Field(description="Chapter goal, hook, and discovery log")
    
    # Section 2: Title suggestions  
    title-suggestions: List[str] = Field(description="3-5 potential chapter titles from ChapterTitlingModule")
    
    # Section 3: Beat list
    beats: List[ChapterBeatStructure] = Field(description="3-7 granular scene beats as choreographic instructions")
    
    # Traceability
    brief-id: str = Field(description="ID of source StrategicBrief for traceability")

# Job State Models for Redis-based HITL workflow
class JobState(BaseModel):
    """
    Job state contract for Redis-based Human-in-the-Loop workflow.
    """
    job-id: str = Field(default-factory=lambda: str(uuid4()), description="Unique job identifier")
    agent: Literal["Director", "Tactician", "Weaver", "Canonist"] = Field(description="Agent responsible")
    status: Literal["processing", "pending-approval", "approved", "rejected", "complete"] = Field(description="Current job status")
    input-payload: Dict = Field(description="Input data for the job")
    output-payload: Optional[Dict] = Field(None, description="Agent output data")
    feedback-history: List[Dict] = Field(default-factory=list, description="Human feedback iterations")
    created-at: datetime = Field(default-factory=datetime.now, description="Job creation timestamp")
    updated-at: datetime = Field(default-factory=datetime.now, description="Last update timestamp")

# Memory/Context Models for MVP simplified two-tiered retrieval
class MemoryDocument(BaseModel):
    """
    Simplified document model for MVP Qdrant storage.
    """
    id: str = Field(description="Document identifier")
    content: str = Field(description="Document text content") 
    doc-type: Literal["character-sheet", "style-guide", "lore-document", "tension-report"] = Field(description="Document classification")
    present-characters: List[str] = Field(default-factory=list, description="Character IDs for spotlight filtering")
    metadata: Dict = Field(default-factory=dict, description="Additional document metadata")

class ContextRetrievalResult(BaseModel):
    """
    Two-tiered context retrieval result from memory pipeline.
    """
    spotlight-context: List[Dict] = Field(description="High-relevance context for current POV/scene")
    ambient-echo: List[Dict] = Field(description="Background tension and unresolved conflicts")
```

### List of tasks to be completed

1.  **CREATE** `src/narrative-factory/agents/models.py` and define the Pydantic models as specified above.
2.  **MODIFY** `src/narrative-factory/agents/personas.py`.
3.  **IMPLEMENT** a base `Agent` class in `personas.py`.
    -   `__init_-(self, persona-name: str)`
    -   `_load-persona(self)`
    -   `_initialize-client(self)`
4.  **IMPLEMENT** subclasses `DirectorAgent`, `TacticianAgent`, `WeaverAgent`, `CanonistAgent` in `personas.py`.
    -   Each subclass should inherit from `Agent`.
    -   The `DirectorAgent.execute` method MUST return a `StrategicBrief` model.
    -   The `TacticianAgent.execute` method MUST accept a `StrategicBrief` model as input and return a `ChapterBlueprint` model.
    -   The `WeaverAgent` and `CanonistAgent` can have placeholder implementations for now.

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff check src/narrative-factory/agents/ --fix
uv run mypy src/narrative-factory/agents/

# Expected: No errors.
```

### Level 2: Unit Tests

The unit tests must be updated to reflect the new Pydantic model outputs.

```python
# In tests/test-agents.py

import pytest
import json
from narrative-factory.agents.personas import DirectorAgent
from narrative-factory.agents.models import StrategicBrief

def test_director_agent_execution-mocked(mocker):
    """Tests the execute method with a mocked LLM call to ensure it returns a valid Pydantic model."""
    # Mock the LLM client's response
    mock-response = mocker.MagicMock()
    # The mock must return a JSON string that matches the StrategicBrief schema
    mock_brief-dict = {
        "chapter-title": "Test Title",
        "narrative-goal": "Test Goal",
        "key_plot-points": ["Point 1"],
        "character-focus": [{
            "character-id": "char-test",
            "objective": "Test objective",
            "emotional-arc": "Test arc"
        }],
        "tension-dynamics": "Test tension"
    }
    mock-response.text = json.dumps(mock_brief-dict)
    
    mock_llm-client = mocker.patch('google.generativeai.GenerativeModel.generate-content')
    mock_llm-client.return-value = mock-response

    agent = DirectorAgent()
    result = agent.execute("Test chapter seed.")

    # Assert that the output is a valid Pydantic model
    assert isinstance(result, StrategicBrief)
    assert result.chapter-title == "Test Title"
    assert result.character-focus[0].character-id == "char-test"

```

```bash
# Run and iterate until passing:
uv run pytest tests/test-agents.py -v
```
