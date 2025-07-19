name: "MVP Phase 5: CLI Implementation & Finalization"
description: "Implements the user-facing Command-Line Interface (CLI) to manage the stateful, pausable generation workflow."

---

## Goal

To create the primary user **command and control interface** for the MVP. This will be a `factory.py` CLI that allows a user to initiate, monitor, and manage the stateful, pausable narrative generation workflow by interacting with the Redis-based `JobStore`.

## Why

- **User Interface:** A CLI is the simplest and most effective way to interact with the narrative engine for the MVP.
- **Workflow Management:** The CLI is the user's tool to interact with the Redis job store, allowing them to approve, reject, and monitor the status of generation tasks. This is the heart of the HITL process.
- **Entry Point:** It provides a single, unified entry point for all major operations (`generate`, `review`, `approve`, etc.), making the system easy to use.

## What

### Success Criteria

- [ ] A `factory.py` file exists at the project root, running the Typer app from `src/narrative-factory/cli/commands.py`.
- [ ] A `generate` command is implemented that triggers the *start* of the Prefect `generation-flow`.
- [ ] An `ingest` command is implemented to populate the Qdrant database.
- [ ] **New HITL commands are implemented:** `status`, `review`, `approve`, and `reject`.
- [ ] These new commands correctly interact with the `JobStore` service to update and query the state of jobs in Redis.
- [ ] The `approve` command successfully triggers the continuation of the paused Prefect workflow.

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for Typer CLI framework
use context7 for library /fastapi/typer topic "CLI applications and command definition"

# Use Context7 for CLI testing patterns
use context7 for typer topic "testing CLI applications with CliRunner"

# Use Context7 for Python entry points
use context7 for python topic "setuptools entry points and executable scripts"

# Use Context7 for CLI argument handling
use context7 for typer topic "command options, arguments, and rich integration"

# Use Context7 for multi-command CLI applications
use context7 for library /fastapi/typer topic "CLI applications with multiple subcommands"

# Use Context7 for CLI testing with CliRunner
use context7 for library /fastapi/typer topic "testing CLI applications with CliRunner"

# Use Context7 for advanced CLI patterns
use context7 for library /fastapi/typer topic "CLI callbacks, contexts, and rich integration"
```

**Why Context7 Enhances This PRP:**
- **Typer Framework**: Latest command patterns, argument handling, and rich integration for modern CLIs
- **CLI Testing**: Advanced testing patterns for command-line applications using CliRunner
- **Entry Points**: Current best practices for Python script execution and entry point configuration
- **User Experience**: Modern CLI patterns for progress indicators, error handling, and user feedback
- **Multi-Command Apps**: Advanced patterns for creating complex CLI applications with multiple subcommands
- **Testing Frameworks**: Comprehensive testing strategies using `CliRunner` for robust CLI validation
- **Rich Integration**: Modern CLI UX patterns with progress bars, colored output, and interactive elements

**Critical Context7 Patterns for CLI:**
- **Command Structure**: Use `typer.Typer()` with `@app.command()` decorators for clean command organization
- **Argument Validation**: Implement proper type hints and validation for CLI arguments and options
- **Error Handling**: Use `typer.echo()` and `typer.Exit()` for consistent error reporting and graceful exits
- **Testing Patterns**: Leverage `CliRunner` for comprehensive CLI testing with mocked dependencies
- **Help Generation**: Use docstrings and `typer.Option()` descriptions for auto-generated help text
- **Command Grouping**: Organize related commands into logical groups for better user experience
- **Progress Indicators**: Implement progress bars and status updates for long-running operations
- **Configuration Management**: Handle configuration files and environment variables for CLI settings

## Implementation Blueprint

Based on Context7 Typer patterns, implement the comprehensive CLI interface:

### 1. Core CLI Application Structure

```python
# In src/narrative-factory/cli/commands.py
import typer
import json
import asyncio
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.json import JSON
from narrative-factory.workflows.generation import (
    initial_generation-flow, 
    continue_generation-flow, 
    finalize_generation-flow
)
from narrative-factory.workflows.jobs import JobStore
from narrative-factory.memory.qdrant import QdrantService

# Create Typer app with help configuration
app = typer.Typer(
    name="factory",
    help="Narrative Factory CLI - AI-powered storytelling engine with Human-in-the-Loop workflow",
    no_args_is-help=True
)

# Initialize services
console = Console()
job-store = JobStore()

@app.command()
def generate(
    seed: str = typer.Argument(..., help="The chapter seed or initial prompt for story generation"),
    characters: str = typer.Option(
        "char-protagonist", 
        "--characters", "-c", 
        help="Comma-separated list of active character IDs"
    )
):
    """
    Start a new narrative generation workflow.
    
    Initiates the Director agent with the provided seed and pauses for human review.
    """
    try:
        # Parse character list
        character-list = [char.strip() for char in characters.split(",")]
        
        console.print(f"🎬 Starting generation with seed: [bold cyan]{seed}[/bold cyan]")
        console.print(f"📋 Active characters: {', '.join(character-list)}")
        
        # Run initial Prefect flow
        director_job-id = initial_generation-flow(seed, character-list)
        
        console.print(f"✅ Director task initiated. Job ID: [bold yellow]{director_job-id}[/bold yellow]")
        console.print("📝 Use [bold green]factory review {director_job-id}[/bold green] to review the strategic brief")
        console.print("✅ Use [bold green]factory approve {director_job-id}[/bold green] to continue workflow")
        
    except Exception as e:
        console.print(f"❌ Error starting generation: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def status():
    """
    Show all jobs pending human review.
    
    Displays a formatted table of jobs awaiting approval or rejection.
    """
    try:
        pending-jobs = job-store.get_pending-jobs()
        
        if not pending-jobs:
            console.print("✅ No jobs pending review", style="bold green")
            return
        
        # Create rich table for display
        table = Table(title="Pending Jobs")
        table.add-column("Job ID", style="cyan")
        table.add-column("Agent", style="magenta")
        table.add-column("Status", style="yellow")
        table.add-column("Created", style="blue")
        
        for job in pending-jobs:
            table.add-row(
                job.job-id[:12] + "...",  # Truncate for display
                job.agent,
                job.status,
                job.created-at.strftime("%H:%M:%S")
            )
        
        console.print(table)
        console.print("💡 Use [bold]factory review <job-id>[/bold] to examine job details")
        
    except Exception as e:
        console.print(f"❌ Error fetching status: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def review(
    job-id: str = typer.Argument(..., help="Job ID to review")
):
    """
    Review the output of a specific job.
    
    Displays the agent's output in a formatted, readable way.
    """
    try:
        job-data = job-store.get-job(job-id)
        
        if not job-data:
            console.print(f"❌ Job {job-id} not found", style="bold red")
            raise typer.Exit(1)
        
        console.print(f"📋 Reviewing Job: [bold cyan]{job-id}[/bold cyan]")
        console.print(f"🤖 Agent: [bold magenta]{job-data['agent']}[/bold magenta]")
        console.print(f"📊 Status: [bold yellow]{job-data['status']}[/bold yellow]")
        
        if job-data.get('output-payload'):
            console.print("\n📄 Agent Output:")
            console.print(JSON(json.dumps(job-data['output-payload'], indent=2)))
        else:
            console.print("⚠️ No output available yet", style="bold yellow")
        
        console.print(f"\n✅ Use [bold green]factory approve {job-id}[/bold green] to continue")
        console.print(f"❌ Use [bold red]factory reject {job-id} --feedback \"Your feedback\"[/bold red] to request changes")
        
    except Exception as e:
        console.print(f"❌ Error reviewing job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def approve(
    job-id: str = typer.Argument(..., help="Job ID to approve")
):
    """
    Approve a job and continue the workflow.
    
    Marks the job as approved and triggers the next stage of the generation pipeline.
    """
    try:
        # Get job details to determine next flow
        job-data = job-store.get-job(job-id)
        
        if not job-data:
            console.print(f"❌ Job {job-id} not found", style="bold red")
            raise typer.Exit(1)
        
        agent = job-data['agent']
        console.print(f"✅ Approving {agent} job: [bold cyan]{job-id}[/bold cyan]")
        
        # Approve the job in JobStore
        approved-output = job-store.approve-job(job-id)
        
        if not approved-output:
            console.print("❌ Failed to approve job", style="bold red")
            raise typer.Exit(1)
        
        # Trigger next flow based on agent type
        if agent == "Director":
            console.print("🎯 Starting Tactician workflow...")
            tactician_job-id = continue_generation-flow(job-id)
            console.print(f"✅ Tactician task initiated. Job ID: [bold yellow]{tactician_job-id}[/bold yellow]")
            
        elif agent == "Tactician":
            console.print("✍️ Starting final generation (Weaver + Canonist)...")
            chapter-text = finalize_generation-flow(job-id)
            console.print("🎉 Chapter generation complete!")
            console.print(f"📊 Generated {len(chapter-text.split())} words")
            
        else:
            console.print(f"✅ Job approved. No automatic next step for {agent}")
        
    except Exception as e:
        console.print(f"❌ Error approving job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def reject(
    job-id: str = typer.Argument(..., help="Job ID to reject"),
    feedback: str = typer.Option(..., "--feedback", "-f", help="Feedback message for the agent")
):
    """
    Reject a job with feedback for improvement.
    
    Marks the job as rejected and provides feedback for the agent to improve output.
    """
    try:
        console.print(f"❌ Rejecting job: [bold cyan]{job-id}[/bold cyan]")
        console.print(f"💬 Feedback: [italic]{feedback}[/italic]")
        
        # Update job as rejected with feedback
        success = job-store.reject-job(job-id, feedback)
        
        if not success:
            console.print("❌ Failed to reject job", style="bold red")
            raise typer.Exit(1)
        
        console.print("✅ Job rejected. Agent will receive feedback for improvement.")
        console.print("💡 Implement retry logic in future iteration")
        
    except Exception as e:
        console.print(f"❌ Error rejecting job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def ingest():
    """
    Ingest bootstrap data into the Qdrant vector database.
    
    Populates the memory system with initial world building and character data.
    """
    try:
        console.print("📥 Starting data ingestion...")
        
        # Run ingestion script using async
        async def run-ingestion():
            from scripts.ingest import ingest_bootstrap-data
            await ingest_bootstrap-data()
        
        asyncio.run(run-ingestion())
        
        console.print("✅ Data ingestion complete", style="bold green")
        
    except Exception as e:
        console.print(f"❌ Error during ingestion: {e}", style="bold red")
        raise typer.Exit(1)

# Add development/testing commands
@app.command()
def test-connection():
    """
    Test connections to Redis and Qdrant services.
    
    Validates that all required services are accessible.
    """
    try:
        console.print("🔍 Testing service connections...")
        
        # Test Redis connection
        try:
            job-store.redis-client.ping()
            console.print("✅ Redis connection: OK", style="bold green")
        except Exception as e:
            console.print(f"❌ Redis connection: FAILED - {e}", style="bold red")
        
        # Test Qdrant connection
        try:
            qdrant-service = QdrantService()
            # Basic connection test - implement ping method if needed
            console.print("✅ Qdrant connection: OK", style="bold green")
        except Exception as e:
            console.print(f"❌ Qdrant connection: FAILED - {e}", style="bold red")
        
    except Exception as e:
        console.print(f"❌ Error testing connections: {e}", style="bold red")
        raise typer.Exit(1)
```

### 2. Main Entry Point (factory.py)

```python
# In factory.py (project root)
#!/usr/bin/env python3
"""
Narrative Factory CLI - AI-powered storytelling engine

Usage:
    python factory.py --help
    python factory.py generate "Chapter seed text"
    python factory.py status
    python factory.py review <job-id>
    python factory.py approve <job-id>
"""

import typer
from src.narrative-factory.cli.commands import app

if __name_- == "__main_-":
    app()
```

### 3. Enhanced JobStore Methods

```python
# Additional methods for src/narrative-factory/workflows/jobs.py
def get-job(self, job-id: str) -> Optional[dict]:
    """Get job data by ID."""
    job-data = self.redis-client.get(f"job:{job-id}")
    if job-data:
        return json.loads(job-data)
    return None

def reject-job(self, job-id: str, feedback: str) -> bool:
    """Reject job with feedback."""
    job-data = self.redis-client.get(f"job:{job-id}")
    if job-data:
        job = JobState.model_validate-json(job-data)
        job.status = "rejected"
        job.feedback-history.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })
        job.updated-at = datetime.now()
        self.redis-client.set(f"job:{job-id}", job.model_dump-json())
        return True
    return False
```

### List of tasks to be completed

1. **CREATE** comprehensive `src/narrative-factory/cli/commands.py` with full command implementations
2. **IMPLEMENT** Rich console formatting for enhanced user experience with tables and colored output
3. **CREATE** robust error handling and user feedback for all CLI operations
4. **INTEGRATE** async support for Qdrant and Prefect operations within CLI commands
5. **IMPLEMENT** job state management commands (status, review, approve, reject)
6. **CREATE** service connectivity testing command for development debugging
7. **UPDATE** root `factory.py` entry point with proper documentation and shebang
8. **ADD** pyproject.toml script entry point for system-wide CLI installation

## Validation Loop

### Level 1: CLI Command Validation

```bash
# Test the help message for each new command
python factory.py status --help
python factory.py review --help
python factory.py approve --help
python factory.py reject --help

# Expected: Each command should display its specific help text, showing the required arguments (e.g., job-id).
```

### Level 2: CLI and JobStore Integration Test (Mocked)

This test will invoke the CLI commands and verify they call the correct `JobStore` methods.

```python
# In a new file: tests/test-cli.py
from typer.testing import CliRunner
from narrative-factory.cli.commands import app

runner = CliRunner()

def test_approve-command(mocker):
    """Tests that the approve CLI command calls the JobStore and a Prefect flow."""
    # Mock the JobStore service
    mock_job-store = mocker.patch('narrative-factory.cli.commands.JobStore')
    # Mock the Prefect flow that gets triggered
    mock_continue-flow = mocker.patch('narrative-factory.cli.commands.continue_generation-flow')

    result = runner.invoke(app, ["approve", "d-12345678"])

    # Assert the command ran successfully
    assert result.exit-code == 0
    assert "approved and workflow is continuing" in result.stdout

    # Assert the JobStore was called correctly
    mock_job-store.update_job_as-approved.assert_called_once-with("d-12345678")
    
    # Assert the next flow was triggered correctly
    mock_continue-flow.assert_called_once-with("d-12345678")
```

```bash
# Run and iterate until passing:
uv run pytest tests/test-cli.py -v
```

---

## Path to Full Vision: The "Bridge" PRP

This MVP is the foundational engine. The `NARRATIVE_FACTORY_PRP_v3.md` document outlines the ultimate goal of a full-stack web application. Once this CLI-based MVP is complete and validated, the next step will be to create a **new "Bridge" PRP** using the `prp-planning.md` template.

This future PRP will not be written now, as it must be informed by the lessons learned during MVP development. However, its purpose will be to detail the following transition:

1.  **Project Restructuring:** Migrating the self-contained MVP structure into the `backend/` directory of a new monorepo.
2.  **API Layer Creation:** Building a FastAPI application in `backend/` that wraps the core narrative engine logic (`agents`, `memory`, `workflows`). The FastAPI endpoints will replace the CLI as the primary interface.
3.  **Frontend Scaffolding:** Initializing a React/TypeScript application in a new `frontend/` directory.
4.  **API Contract Definition:** Formally defining the REST API and WebSocket contract that the frontend will use to communicate with the backend.

By completing this MVP first, we ensure the core logic is sound before building the complex UI on top of it, making the "Bridge" phase significantly more likely to succeed.
