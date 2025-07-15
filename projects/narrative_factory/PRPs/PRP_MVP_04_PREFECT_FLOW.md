name: "MVP Phase 4: Prefect Workflow Orchestration"
description: "Orchestrates the individual AI agents into a single, coherent narrative generation pipeline using Prefect."

---

## Goal

To define a Prefect flow that sequences the execution of the four AI agents (Director, Tactician, Weaver, Canonist), manages data dependencies between them, and provides the observability and reliability features of a modern workflow orchestrator.

## Why

- **Orchestration:** A simple Python script is not robust enough. Prefect provides automatic retries, logging, caching, and a UI for monitoring, which are essential for a complex, multi-step process.
- **Dataflow Management:** Prefect makes it easy and explicit how the output of one agent becomes the input for the next, preventing bugs and making the pipeline easier to reason about.
- **Scalability:** While the MVP will run locally, using Prefect from the start means the workflow can be easily deployed to a cloud environment with a Prefect server and workers for scalable execution.

## What

### Success Criteria

- [ ] A `generation_flow` is defined as a Prefect `@flow` in `src/narrative_factory/workflows/generation.py`.
- [ ] The execution of each of the four agents is defined as a Prefect `@task`.
- [ ] The flow correctly passes data between the tasks (e.g., the `StrategicBrief` from the Director task is passed to the Tactician task).
- [ ] The flow can be triggered successfully from a Python script (which will later be the CLI).
- [ ] The flow run can be observed in the local Prefect UI.

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for Prefect workflow orchestration
use context7 for library /prefecthq/prefect topic "flows and tasks with data dependencies"

# Use Context7 for async workflow patterns
use context7 for prefect topic "async task execution and parallel processing"

# Use Context7 for testing Prefect workflows
use context7 for pytest topic "testing workflow execution and task mocking"

# Use Context7 for workflow error handling
use context7 for prefect topic "retries, caching, and error handling patterns"
```

**Why Context7 Enhances This PRP:**
- **Prefect Flows**: Latest flow and task patterns, decorators, and data dependency management
- **Async Workflows**: Current approaches for async task execution and parallel agent processing
- **Testing Workflows**: Advanced patterns for testing flows and tasks with mocked agent dependencies
- **Error Handling**: Modern retry strategies, caching patterns, and workflow resilience techniques

## All Needed Context

### Documentation & References

```yaml
- doc: https://docs.prefect.io/latest/concepts/flows/
  why: Core documentation on how to define a Prefect flow.

- doc: https://docs.prefect.io/latest/concepts/tasks/
  why: Core documentation on how to define Prefect tasks, including retries and caching.
```

## Implementation Blueprint

### List of tasks to be completed

1.  **MODIFY** `src/narrative_factory/workflows/generation.py`.
2.  **IMPORT** the agent classes (`DirectorAgent`, etc.) and the memory service (`QdrantService`).
3.  **DEFINE** a `@task` for each agent's operation. Each task should:
    -   Accept the necessary inputs (e.g., the `director_task` takes a `chapter_seed`).
    -   Instantiate the corresponding agent.
    -   Call the agent's `execute` method.
    -   Return the result (the Pydantic model).
    -   Example: `def director_task(chapter_seed: str) -> StrategicBrief:`
4.  **DEFINE** a `@task` for context retrieval.
    -   `def retrieve_context_task(chapter_seed: str, active_characters: list) -> dict:`
    -   This task will use the `QdrantService` to perform the two-tiered search.
5.  **DEFINE** the main `@flow` named `generation_flow`.
    -   The flow should accept the initial `chapter_seed`.
    -   It should call the tasks in the correct sequence:
        1.  `retrieve_context_task`
        2.  `director_task` (receives seed and context from previous task)
        3.  `tactician_task` (receives output from director)
        4.  `weaver_task` (receives output from tactician)
        5.  `canonist_task` (receives output from weaver)
    -   The flow should return the final generated chapter text.

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
ruff check src/narrative_factory/workflows/ --fix
mypy src/narrative_factory/workflows/

# Expected: No errors.
```

### Level 2: Flow Execution Test

This test will run the flow in-process, but with the actual agent `execute` methods mocked to avoid making real LLM calls. This validates the flow's structure and data passing.

```python
# In a new file: tests/test_workflows.py

from narrative_factory.workflows.generation import generation_flow
from narrative_factory.agents.models import StrategicBrief, ChapterBlueprint # etc.

def test_generation_flow_data_passing(mocker):
    """
    Tests that the Prefect flow passes data correctly between mocked tasks.
    """
    # Mock the agent execution at a low level
    mocker.patch(
        'narrative_factory.agents.personas.DirectorAgent.execute',
        return_value=StrategicBrief(chapter_goal="mock goal", scene_blueprints=[], tension_points=[])
    )
    mocker.patch(
        'narrative_factory.agents.personas.TacticianAgent.execute',
        return_value=ChapterBlueprint(beats=["mock beat"])
    )
    # ... mock other agents

    # Mock the memory retrieval
    mocker.patch(
        'narrative_factory.memory.qdrant.QdrantService.fetch_context_for_director',
        return_value={"spotlight_context": [], "ambient_echo": []}
    )

    # Run the flow
    result = generation_flow("A test seed.")

    # Assert the final result is what you expect from the last (mocked) agent
    assert "Final chapter text" in result # Or whatever the Canonist returns
```

```bash
# Run and iterate until passing:
uv run pytest tests/test_workflows.py -v
```

### Level 3: Prefect UI Validation

```bash
# In a temporary script or a Jupyter notebook

from narrative_factory.workflows.generation import generation_flow

if __name__ == "__main__":
    generation_flow("A test seed to run in the UI.")
```

```bash
# Run the script
python temp_script.py

# Open the Prefect UI (typically http://127.0.0.1:4200/)
# Expected: A successful flow run for "generation-flow" should be visible in the UI, with all tasks showing a 'COMPLETED' state.
```
