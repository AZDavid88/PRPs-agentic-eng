name: "MVP Phase 2: Agent Core Implementation"
description: "Defines and implements the core Agent classes that form the cognitive engine of the Narrative Factory."

---

## Goal

To create a robust, reusable, and well-defined set of Python classes for the AI agents (Director, Tactician, Weaver, Canonist). This includes a base `Agent` class that handles common functionality and specific subclasses for each role.

## Why

- **Abstraction:** A base class prevents code duplication by handling shared logic like LLM client initialization and persona loading.
- **Clarity:** Separating each agent's logic into its own class makes the system easier to understand, debug, and extend.
- **Testability:** Encapsulating agent logic within classes allows for targeted and effective unit testing.

## What

### Success Criteria

- [ ] A base `Agent` class is created in `src/narrative_factory/agents/personas.py`.
- [ ] The base class can load a persona file from the `/.personas/` directory and initialize an LLM client.
- [ ] Subclasses for `Director`, `Tactician`, `Weaver`, and `Canonist` are created, inheriting from the base `Agent`.
- [ ] Each subclass has a unique `execute` method that takes a context string and returns a structured output (e.g., a Pydantic model).
- [ ] Unit tests are created to verify that agents can be initialized and can execute their core logic.

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
```

**Why Context7 Enhances This PRP:**
- **Pydantic**: Latest BaseModel patterns, Field specifications, and validation techniques for structured agent outputs
- **OpenAI SDK**: Current client initialization patterns and structured output handling
- **Pytest Mock**: Modern mocking patterns for LLM clients and external dependencies
- **Google GenAI**: Up-to-date client setup and model interaction patterns

## All Needed Context

### Documentation & References

```yaml
- file: /workspaces/PRPs-agentic-eng/.personas/NOVA.txt
  why: Example of a persona file that the Agent class will need to parse.

- file: /workspaces/PRPs-agentic-eng/projects/narrative_factory/contracts/director.json
  why: Example of a contract that a specific agent (Director) will use to structure its prompts.

- doc: https://pydantic-docs.helpmanual.io/
  why: Pydantic models should be used for all structured outputs from agents to ensure type safety and validation.
```

## Implementation Blueprint

### Data models and structure

```python
# In a new file: src/narrative_factory/agents/models.py

from pydantic import BaseModel, Field
from typing import List

class StrategicBrief(BaseModel):
    """Output from the Director Agent."""
    chapter_goal: str = Field(description="The primary narrative goal of this chapter.")
    scene_blueprints: List[str] = Field(description="A list of high-level scenes to be written.")
    tension_points: List[str] = Field(description="Key tensions to escalate or resolve.")

class ChapterBlueprint(BaseModel):
    """Output from the Tactician Agent."""
    beats: List[str] = Field(description="A detailed, beat-by-beat outline of the chapter.")

# ... other models for Weaver and Canonist outputs
```

### List of tasks to be completed

1.  **CREATE** `src/narrative_factory/agents/models.py` and define the Pydantic models for agent outputs.
2.  **MODIFY** `src/narrative_factory/agents/personas.py`.
3.  **IMPLEMENT** a base `Agent` class in `personas.py`:
    -   `__init__(self, persona_name: str)`: Takes the name of the persona (e.g., "DIRECTOR").
    -   `_load_persona(self)`: Private method to load the corresponding `.txt` file.
    -   `_initialize_client(self)`: Private method to set up the `google-generativeai` client.
    -   `execute(self, context: str) -> BaseModel`: Public method to be overridden by subclasses.
4.  **IMPLEMENT** subclasses `DirectorAgent`, `TacticianAgent`, `WeaverAgent`, `CanonistAgent` in `personas.py`.
    -   Each subclass should inherit from `Agent`.
    -   Each should override the `execute` method to perform its specific role, using its persona and contracts to generate a prompt.
    -   The `execute` method for each agent MUST return its corresponding Pydantic model (e.g., `DirectorAgent` returns `StrategicBrief`).

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
ruff check src/narrative_factory/agents/ --fix
mypy src/narrative_factory/agents/

# Expected: No errors.
```

### Level 2: Unit Tests

```python
# In tests/test_agents.py

import pytest
from narrative_factory.agents.personas import DirectorAgent

def test_director_agent_initialization():
    """Tests that the Director agent can be initialized and loads its persona."""
    agent = DirectorAgent() # Assuming a default or direct name
    assert agent.persona_name == "DIRECTOR"
    assert "Strategic Planner" in agent.persona_content # Check for a keyword from the persona file

def test_director_agent_execution_mocked(mocker):
    """Tests the execute method with a mocked LLM call."""
    # Mock the LLM client's generate_content method
    mock_llm_client = mocker.patch('google.generativeai.GenerativeModel.generate_content')
    mock_llm_client.return_value.text = '{"chapter_goal": "Test Goal", "scene_blueprints": ["Scene 1"], "tension_points": ["Tension 1"]}'

    agent = DirectorAgent()
    result = agent.execute("Test chapter seed.")

    # Assert that the output is a valid Pydantic model
    from narrative_factory.agents.models import StrategicBrief
    assert isinstance(result, StrategicBrief)
    assert result.chapter_goal == "Test Goal"

```

```bash
# Run and iterate until passing:
uv run pytest tests/test_agents.py -v
```
