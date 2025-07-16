name: "MVP Phase 4: Prefect Workflow Orchestration"
description: "Orchestrates the individual AI agents into a single, coherent, and **stateful** narrative generation pipeline using Prefect and Redis."

---

## Goal

To define a Prefect flow that orchestrates a **stateful, pausable** four-agent assembly line that incorporates **Human-in-the-Loop (HITL) review checkpoints**. This flow will manage the entire lifecycle of a chapter's generation, from initial seed to final text, using a Redis-based job store to manage state.

## Why

- **Orchestration & Reliability:** Prefect provides observability, retries, and logging for the complex agent workflow.
- **Stateful HITL:** A Redis-based `JobStore` gives the workflow a persistent memory, allowing it to pause and wait for human approval. This is critical for quality control.
- **Iterative Refinement:** A "rejected" step is no longer a failure, but a planned loop in the workflow. This prevents wasted work by downstream agents and allows for iterative correction with feedback.

## What

### Success Criteria

- [ ] A `generation_flow` is defined as a Prefect `@flow` in `src/narrative_factory/workflows/generation.py`.
- [ ] The execution of each agent (`Director`, `Tactician`, etc.) is defined as a Prefect `@task`.
- [ ] Agent tasks interact with the `JobStore` to create and update jobs in Redis.
- [ ] The flow correctly creates jobs with a `pending_approval` status after the Director and Tactician tasks, and then pauses.
- [ ] The flow can be resumed or re-run based on external events (triggered by the CLI) that modify the job state in Redis.
- [ ] The entire process can be observed in the local Prefect UI.

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
  why: Core documentation on how to define Prefect tasks.

- file: /workspaces/PRPs-agentic-eng/projects/narrative_factory/PRPs/PRP_MVP_02_AGENT_CORE.md
  why: Defines the agent Pydantic models that will be passed between tasks.

- file: /workspaces/PRPs-agentic-eng/projects/narrative_factory/PRPs/PRP_MVP_05_CLI.md
  why: Defines the CLI commands that will trigger and interact with this flow.
```

## Implementation Blueprint: Prefect + Redis HITL Workflow

Based on Context7 Prefect patterns, implement the stateful workflow:

### 1. JobStore Service for Redis State Management

```python
# In src/narrative_factory/workflows/jobs.py
import redis
import json
from typing import Optional, List
from narrative_factory.agents.models import JobState

class JobStore:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )
    
    def create_job(self, agent: str, input_payload: dict) -> str:
        """Create new job in Redis and return job_id."""
        job = JobState(
            agent=agent,
            status="processing", 
            input_payload=input_payload
        )
        self.redis_client.set(f"job:{job.job_id}", job.model_dump_json())
        return job.job_id
    
    def update_job_as_pending(self, job_id: str, output_payload: dict):
        """Update job with output and set status to pending_approval."""
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            job = JobState.model_validate_json(job_data)
            job.status = "pending_approval"
            job.output_payload = output_payload
            job.updated_at = datetime.now()
            self.redis_client.set(f"job:{job_id}", job.model_dump_json())
    
    def approve_job(self, job_id: str) -> Optional[dict]:
        """Approve job and return output payload."""
        job_data = self.redis_client.get(f"job:{job_id}")
        if job_data:
            job = JobState.model_validate_json(job_data)
            job.status = "approved"
            self.redis_client.set(f"job:{job_id}", job.model_dump_json())
            return job.output_payload
        return None
    
    def get_pending_jobs(self) -> List[JobState]:
        """Get all jobs with pending_approval status."""
        jobs = []
        for key in self.redis_client.scan_iter(match="job:*"):
            job_data = self.redis_client.get(key)
            job = JobState.model_validate_json(job_data)
            if job.status == "pending_approval":
                jobs.append(job)
        return jobs
```

### 2. Agent Tasks with Dependencies

```python
# In src/narrative_factory/workflows/generation.py
from prefect import flow, task
from narrative_factory.agents.personas import DirectorAgent, TacticianAgent, WeaverAgent, CanonistAgent
from narrative_factory.workflows.jobs import JobStore
from narrative_factory.memory.qdrant import QdrantService

job_store = JobStore()
memory_service = QdrantService()

@task(retries=3, retry_delay_seconds=5)
def director_task(chapter_seed: str, active_characters: list = None) -> str:
    """Execute Director agent and save result to JobStore."""
    if active_characters is None:
        active_characters = ["char_protagonist"]
    
    # Create job in JobStore
    job_id = job_store.create_job(
        agent="Director",
        input_payload={"chapter_seed": chapter_seed, "active_characters": active_characters}
    )
    
    # Get context from memory service
    context = memory_service.fetch_context_for_director(chapter_seed, active_characters)
    
    # Execute Director agent
    director = DirectorAgent()
    strategic_brief = director.execute(chapter_seed, context)
    
    # Save output and mark as pending approval
    job_store.update_job_as_pending(job_id, strategic_brief.model_dump())
    
    return job_id

@task(retries=3, retry_delay_seconds=5) 
def tactician_task(director_job_id: str) -> str:
    """Execute Tactician agent using approved Director output."""
    # Get approved Director output
    director_output = job_store.approve_job(director_job_id)
    if not director_output:
        raise ValueError(f"Director job {director_job_id} not approved")
    
    # Create new job for Tactician
    job_id = job_store.create_job(
        agent="Tactician",
        input_payload={"strategic_brief": director_output}
    )
    
    # Execute Tactician agent
    tactician = TacticianAgent()
    chapter_blueprint = tactician.execute(director_output)
    
    # Save output and mark as pending approval
    job_store.update_job_as_pending(job_id, chapter_blueprint.model_dump())
    
    return job_id

@task
def weaver_task(tactician_job_id: str) -> str:
    """Execute Weaver agent (no approval needed)."""
    tactician_output = job_store.approve_job(tactician_job_id)
    if not tactician_output:
        raise ValueError(f"Tactician job {tactician_job_id} not approved")
    
    weaver = WeaverAgent()
    chapter_text = weaver.execute(tactician_output)
    
    # Save final output
    job_id = job_store.create_job(
        agent="Weaver", 
        input_payload={"chapter_blueprint": tactician_output}
    )
    job_store.update_job_as_pending(job_id, {"chapter_text": chapter_text})
    
    return chapter_text

@flow(log_prints=True)
def initial_generation_flow(chapter_seed: str, active_characters: list = None):
    """Initial flow: Director task only, then pause for approval."""
    print(f"Starting generation flow with seed: {chapter_seed}")
    
    director_job_id = director_task(chapter_seed, active_characters)
    
    print(f"Director task complete. Job ID: {director_job_id}")
    print("Use CLI to review and approve: factory.py review {director_job_id}")
    
    return director_job_id

@flow(log_prints=True) 
def continue_generation_flow(director_job_id: str):
    """Continue flow: Tactician task, then pause for approval."""
    print(f"Continuing generation with approved Director job: {director_job_id}")
    
    tactician_job_id = tactician_task(director_job_id)
    
    print(f"Tactician task complete. Job ID: {tactician_job_id}")
    print("Use CLI to review and approve: factory.py review {tactician_job_id}")
    
    return tactician_job_id

@flow(log_prints=True)
def finalize_generation_flow(tactician_job_id: str):
    """Final flow: Weaver and Canonist tasks (automated)."""
    print(f"Finalizing generation with approved Tactician job: {tactician_job_id}")
    
    chapter_text = weaver_task(tactician_job_id)
    
    print("Chapter generation complete!")
    print(f"Generated {len(chapter_text.split())} words")
    
    return chapter_text
```

### 3. Task Dependencies and State Management

The workflow uses Prefect's task dependency system with `wait_for` parameter and external Redis state:

- **Step 1**: `initial_generation_flow` → Director task → Pause for approval
- **Step 2**: `continue_generation_flow` → Tactician task → Pause for approval  
- **Step 3**: `finalize_generation_flow` → Weaver + Canonist tasks → Complete

### List of tasks to be completed

1. **CREATE** `src/narrative_factory/workflows/jobs.py` with Redis-based JobStore service
2. **CREATE** `src/narrative_factory/workflows/generation.py` with three pausable flows
3. **IMPLEMENT** task retry logic and error handling using `@task(retries=3)`
4. **INTEGRATE** agent execution within Prefect tasks with proper dependency management
5. **SETUP** Redis connection management with environment variable configuration
6. **IMPLEMENT** job state transitions: processing → pending_approval → approved → complete

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
ruff check src/narrative_factory/workflows/ --fix
mypy src/narrative_factory/workflows/

# Expected: No errors.
```

### Level 2: Workflow Logic Test (Mocked)

This test will validate the interaction between the tasks and a mocked `JobStore`.

```python
# In a new file: tests/test_workflows.py

from narrative_factory.workflows.generation import generation_flow
from narrative_factory.agents.models import StrategicBrief

def test_generation_flow_creates_pending_job(mocker):
    """
    Tests that the initial flow runs the director task and creates a pending job in the job store.
    """
    # Mock the agent execution itself
    mocker.patch(
        'narrative_factory.agents.personas.DirectorAgent.execute',
        return_value=StrategicBrief(...) # Populate with valid data
    )
    # Mock the JobStore
    mock_job_store = mocker.patch('narrative_factory.workflows.generation.JobStore')

    # Run the initial flow
    generation_flow("A test seed.")

    # Assert that a job was created and then updated to pending
    mock_job_store.create_job.assert_called_once()
    mock_job_store.update_job_as_pending.assert_called_once()
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
    # This will run the first part of the flow
    generation_flow("A test seed to run in the UI.")
    print("Generation flow initiated. Check Prefect UI and then use the CLI to approve the job.")
```

```bash
# Run the script
python temp_script.py

# Open the Prefect UI (typically http://127.0.0.1:4200/)
# Expected: A successful flow run for "generation-flow" should be visible.
# Then, use the (yet to be built) CLI to approve the job and trigger the next flow run, which should also appear in the UI.
```

