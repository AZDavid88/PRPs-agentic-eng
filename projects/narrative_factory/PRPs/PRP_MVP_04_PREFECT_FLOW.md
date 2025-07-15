name: "MVP Phase 4: Prefect Workflow Orchestration"
description: "Orchestrates the individual AI agents into a single, coherent narrative generation pipeline using Prefect."

---

## Goal

To define a Prefect flow that orchestrates a **stateful, pausable** four-agent assembly line that incorporates **Human-in-the-Loop (HITL) review checkpoints**. This flow will manage the entire lifecycle of a chapter's generation, from initial seed to final text, using a Redis-based job store to manage state.

## Why

- **Orchestration:** A simple Python script is not robust enough. Prefect provides observability and reliability for our workflow. The addition of a Redis job store gives it the statefulness required for a HITL process.
- **Dataflow Management:** Prefect makes it explicit how data flows between agents. The HITL checkpoints ensure the quality of this data at critical stages.
- **Resilience:** The new design allows for iterative correction. A "rejected" step is no longer a failure, but a planned loop in the workflow, preventing wasted work by downstream agents.

## What

### Success Criteria

- [ ] A `generation_flow` is defined as a Prefect `@flow` in `src/narrative_factory/workflows/generation.py`.
- [ ] The execution of each of the four agents is defined as a Prefect `@task`.
- [ ] The flow correctly creates jobs in the Redis job store with a `pending_approval` status after the Director and Tactician tasks.
- [ ] The flow can be paused and then resumed or re-run based on external events triggered by the CLI.
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

# Use Context7 for Prefect state dependencies
use context7 for library /prefecthq/prefect topic "wait_for and future handling"

# Use Context7 for Prefect error handling
use context7 for library /prefecthq/prefect topic "retries and task recovery patterns"

# Use Context7 for Prefect result persistence
use context7 for library /prefecthq/prefect topic "result storage and caching"
```

**Why Context7 Enhances This PRP:**
- **Prefect Flows**: Latest flow and task patterns, decorators, and data dependency management
- **Async Workflows**: Current approaches for async task execution and parallel agent processing
- **Testing Workflows**: Advanced patterns for testing flows and tasks with mocked agent dependencies
- **Error Handling**: Modern retry strategies, caching patterns, and workflow resilience techniques
- **State Dependencies**: Advanced `wait_for` patterns for coordinating task execution and managing dependencies
- **Task Recovery**: Comprehensive retry logic, failure handling, and workflow resilience patterns
- **Result Persistence**: Best practices for result storage, caching, and data persistence across flow runs

**Critical Context7 Patterns for Prefect Flow:**
- **Task Dependencies**: Use `wait_for=[task_a, task_b]` to ensure proper execution ordering for HITL checkpoints
- **Future Handling**: Implement `task.submit()` for concurrent execution and `future.result()` for blocking waits
- **Error Recovery**: Use `@task(retries=3, retry_delay_seconds=5)` for resilient task execution
- **State Management**: Leverage Prefect's built-in state tracking for pausable and resumable workflows
- **Result Caching**: Implement `cache_policy=INPUTS` for efficient task result reuse
- **Flow Composition**: Use nested flows and subflows for complex workflow organization
- **Event-Driven Patterns**: Integrate with external systems (Redis) for HITL workflow state management
- **Concurrent Processing**: Use `task.map()` for parallel execution when processing multiple inputs

## All Needed Context

### Documentation & References

```yaml
- doc: https://docs.prefect.io/latest/concepts/flows/
  why: Core documentation on how to define a Prefect flow.

- doc: https://docs.prefect.io/latest/concepts/tasks/
  why: Core documentation on how to define Prefect tasks, including retries and caching.
```

## Implementation Blueprint

## Implementation Blueprint: Event-Driven, Pausable Workflow

The Prefect flow is no longer a simple linear sequence. It is now an event-driven state machine orchestrated by Prefect and managed via the Redis job store.

1.  **MODIFY** `src/narrative_factory/workflows/generation.py`.
2.  **IMPORT** the `JobStore` service from `jobs.py`.
3.  **DEFINE** agent tasks (`director_task`, `tactician_task`, etc.) as before. However, they now interact with the `JobStore`.
4.  **REDEFINE** the main `@flow` named `generation_flow`.
    -   The flow is triggered with an initial `chapter_seed`.
    -   **Step 1: Director's Turn**
        -   The `director_task` runs.
        -   On completion, it **does not** return its result to the flow directly. Instead, it calls `job_store.create_job(...)`, saving the output and setting the status to `pending_approval`.
        -   The flow then **pauses**, logging a message that user review is required.
    -   **Step 2: Human-in-the-Loop**
        -   The user interacts with the CLI (`approve` or `reject`).
        -   The CLI command updates the job status in Redis.
        -   The `approve` command will trigger a **Prefect event** or a new flow run, passing the `job_id` of the approved job.
    -   **Step 3: Tactician's Turn**
        -   A new flow or sub-flow is triggered by the approval event.
        -   It fetches the approved data from the `JobStore` using the `job_id`.
        -   The `tactician_task` runs with this data.
        -   Like the Director, it saves its output to a new job with `status: 'pending_approval'` and the flow pauses again.
    -   **Step 4: Final Automated Run**
        -   Once the Tactician's output is approved via the CLI, the final part of the flow is triggered.
        -   The `weaver_task` and `canonist_task` run sequentially **without pausing**, as their inputs are now considered validated.
        -   The final output is saved and the process is marked as `complete`.

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
