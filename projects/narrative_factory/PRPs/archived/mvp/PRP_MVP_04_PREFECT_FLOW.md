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

- [ ] A `generation-flow` is defined as a Prefect `@flow` in `src/narrative-factory/workflows/generation.py`.
- [ ] The execution of each agent (`Director`, `Tactician`, etc.) is defined as a Prefect `@task`.
- [ ] Agent tasks interact with the `JobStore` to create and update jobs in Redis.
- [ ] The flow correctly creates jobs with a `pending-approval` status after the Director and Tactician tasks, and then pauses.
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
use context7 for library /prefecthq/prefect topic "wait-for and future handling"

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
- **State Dependencies**: Advanced `wait-for` patterns for coordinating task execution and managing dependencies
- **Task Recovery**: Comprehensive retry logic, failure handling, and workflow resilience patterns
- **Result Persistence**: Best practices for result storage, caching, and data persistence across flow runs

**Critical Context7 Patterns for Prefect Flow:**
- **Task Dependencies**: Use `wait-for=[task-a, task-b]` to ensure proper execution ordering for HITL checkpoints
- **Future Handling**: Implement `task.submit()` for concurrent execution and `future.result()` for blocking waits
- **Error Recovery**: Use `@task(retries=3, retry_delay-seconds=5)` for resilient task execution
- **State Management**: Leverage Prefect's built-in state tracking for pausable and resumable workflows
- **Result Caching**: Implement `cache-policy=INPUTS` for efficient task result reuse
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

- file: /workspaces/PRPs-agentic-eng/projects/narrative-factory/PRPs/PRP_MVP_02_AGENT_CORE.md
  why: Defines the agent Pydantic models that will be passed between tasks.

- file: /workspaces/PRPs-agentic-eng/projects/narrative-factory/PRPs/PRP_MVP_05_CLI.md
  why: Defines the CLI commands that will trigger and interact with this flow.
```

## Implementation Blueprint: Prefect + Redis HITL Workflow

Based on Context7 Prefect patterns, implement the stateful workflow:

### 1. JobStore Service for Redis State Management

```python
# In src/narrative-factory/workflows/jobs.py
import redis
import json
from typing import Optional, List
from narrative-factory.agents.models import JobState

class JobStore:
    def __init_-(self):
        self.redis-client = redis.Redis(
            host=os.getenv("REDIS-HOST", "localhost"),
            port=int(os.getenv("REDIS-PORT", 6379)),
            decode-responses=True
        )
    
    def create-job(self, agent: str, input-payload: dict) -> str:
        """Create new job in Redis and return job-id."""
        job = JobState(
            agent=agent,
            status="processing", 
            input-payload=input-payload
        )
        self.redis-client.set(f"job:{job.job-id}", job.model_dump-json())
        return job.job-id
    
    def update_job_as-pending(self, job-id: str, output-payload: dict):
        """Update job with output and set status to pending-approval."""
        job-data = self.redis-client.get(f"job:{job-id}")
        if job-data:
            job = JobState.model_validate-json(job-data)
            job.status = "pending-approval"
            job.output-payload = output-payload
            job.updated-at = datetime.now()
            self.redis-client.set(f"job:{job-id}", job.model_dump-json())
    
    def approve-job(self, job-id: str) -> Optional[dict]:
        """Approve job and return output payload."""
        job-data = self.redis-client.get(f"job:{job-id}")
        if job-data:
            job = JobState.model_validate-json(job-data)
            job.status = "approved"
            self.redis-client.set(f"job:{job-id}", job.model_dump-json())
            return job.output-payload
        return None
    
    def get_pending-jobs(self) -> List[JobState]:
        """Get all jobs with pending-approval status."""
        jobs = []
        for key in self.redis-client.scan-iter(match="job:*"):
            job-data = self.redis-client.get(key)
            job = JobState.model_validate-json(job-data)
            if job.status == "pending-approval":
                jobs.append(job)
        return jobs
```

### 2. Agent Tasks with Dependencies

```python
# In src/narrative-factory/workflows/generation.py
from prefect import flow, task
from narrative-factory.agents.personas import DirectorAgent, TacticianAgent, WeaverAgent, CanonistAgent
from narrative-factory.workflows.jobs import JobStore
from narrative-factory.memory.qdrant import QdrantService

job-store = JobStore()
memory-service = QdrantService()

@task(retries=3, retry_delay-seconds=5)
def director-task(chapter-seed: str, active-characters: list = None) -> str:
    """Execute Director agent and save result to JobStore."""
    if active-characters is None:
        active-characters = ["char-protagonist"]
    
    # Create job in JobStore
    job-id = job-store.create-job(
        agent="Director",
        input-payload={"chapter-seed": chapter-seed, "active-characters": active-characters}
    )
    
    # Get context from memory service
    context = memory-service.fetch_context_for-director(chapter-seed, active-characters)
    
    # Execute Director agent
    director = DirectorAgent()
    strategic-brief = director.execute(chapter-seed, context)
    
    # Save output and mark as pending approval
    job-store.update_job_as-pending(job-id, strategic-brief.model-dump())
    
    return job-id

@task(retries=3, retry_delay-seconds=5) 
def tactician-task(director_job-id: str) -> str:
    """Execute Tactician agent using approved Director output."""
    # Get approved Director output
    director-output = job-store.approve-job(director_job-id)
    if not director-output:
        raise ValueError(f"Director job {director_job-id} not approved")
    
    # Create new job for Tactician
    job-id = job-store.create-job(
        agent="Tactician",
        input-payload={"strategic-brief": director-output}
    )
    
    # Execute Tactician agent
    tactician = TacticianAgent()
    chapter-blueprint = tactician.execute(director-output)
    
    # Save output and mark as pending approval
    job-store.update_job_as-pending(job-id, chapter-blueprint.model-dump())
    
    return job-id

@task
def weaver-task(tactician_job-id: str) -> str:
    """Execute Weaver agent (no approval needed)."""
    tactician-output = job-store.approve-job(tactician_job-id)
    if not tactician-output:
        raise ValueError(f"Tactician job {tactician_job-id} not approved")
    
    weaver = WeaverAgent()
    chapter-text = weaver.execute(tactician-output)
    
    # Save final output
    job-id = job-store.create-job(
        agent="Weaver", 
        input-payload={"chapter-blueprint": tactician-output}
    )
    job-store.update_job_as-pending(job-id, {"chapter-text": chapter-text})
    
    return chapter-text

@flow(log-prints=True)
def initial_generation-flow(chapter-seed: str, active-characters: list = None):
    """Initial flow: Director task only, then pause for approval."""
    print(f"Starting generation flow with seed: {chapter-seed}")
    
    director_job-id = director-task(chapter-seed, active-characters)
    
    print(f"Director task complete. Job ID: {director_job-id}")
    print("Use CLI to review and approve: factory.py review {director_job-id}")
    
    return director_job-id

@flow(log-prints=True) 
def continue_generation-flow(director_job-id: str):
    """Continue flow: Tactician task, then pause for approval."""
    print(f"Continuing generation with approved Director job: {director_job-id}")
    
    tactician_job-id = tactician-task(director_job-id)
    
    print(f"Tactician task complete. Job ID: {tactician_job-id}")
    print("Use CLI to review and approve: factory.py review {tactician_job-id}")
    
    return tactician_job-id

@flow(log-prints=True)
def finalize_generation-flow(tactician_job-id: str):
    """Final flow: Weaver and Canonist tasks (automated)."""
    print(f"Finalizing generation with approved Tactician job: {tactician_job-id}")
    
    chapter-text = weaver-task(tactician_job-id)
    
    print("Chapter generation complete!")
    print(f"Generated {len(chapter-text.split())} words")
    
    return chapter-text
```

### 3. Task Dependencies and State Management

The workflow uses Prefect's task dependency system with `wait-for` parameter and external Redis state:

- **Step 1**: `initial_generation-flow` → Director task → Pause for approval
- **Step 2**: `continue_generation-flow` → Tactician task → Pause for approval  
- **Step 3**: `finalize_generation-flow` → Weaver + Canonist tasks → Complete

### List of tasks to be completed

1. **CREATE** `src/narrative-factory/workflows/jobs.py` with Redis-based JobStore service
2. **CREATE** `src/narrative-factory/workflows/generation.py` with three pausable flows
3. **IMPLEMENT** task retry logic and error handling using `@task(retries=3)`
4. **INTEGRATE** agent execution within Prefect tasks with proper dependency management
5. **SETUP** Redis connection management with environment variable configuration
6. **IMPLEMENT** job state transitions: processing → pending-approval → approved → complete

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff check src/narrative-factory/workflows/ --fix
uv run mypy src/narrative-factory/workflows/

# Expected: No errors.
```

### Level 2: Workflow Logic Test (Mocked)

This test will validate the interaction between the tasks and a mocked `JobStore`.

```python
# In a new file: tests/test-workflows.py

from narrative-factory.workflows.generation import generation-flow
from narrative-factory.agents.models import StrategicBrief

def test_generation_flow_creates_pending-job(mocker):
    """
    Tests that the initial flow runs the director task and creates a pending job in the job store.
    """
    # Mock the agent execution itself
    mocker.patch(
        'narrative-factory.agents.personas.DirectorAgent.execute',
        return-value=StrategicBrief(...) # Populate with valid data
    )
    # Mock the JobStore
    mock_job-store = mocker.patch('narrative-factory.workflows.generation.JobStore')

    # Run the initial flow
    generation-flow("A test seed.")

    # Assert that a job was created and then updated to pending
    mock_job-store.create-job.assert_called-once()
    mock_job-store.update_job_as-pending.assert_called-once()
```

```bash
# Run and iterate until passing:
uv run pytest tests/test-workflows.py -v
```

### Level 3: Prefect UI Validation

```bash
# In a temporary script or a Jupyter notebook
from narrative-factory.workflows.generation import generation-flow

if __name_- == "__main_-":
    # This will run the first part of the flow
    generation-flow("A test seed to run in the UI.")
    print("Generation flow initiated. Check Prefect UI and then use the CLI to approve the job.")
```

```bash
# Run the script
python temp-script.py

# Open the Prefect UI (typically http://127.0.0.1:4200/)
# Expected: A successful flow run for "generation-flow" should be visible.
# Then, use the (yet to be built) CLI to approve the job and trigger the next flow run, which should also appear in the UI.
```

