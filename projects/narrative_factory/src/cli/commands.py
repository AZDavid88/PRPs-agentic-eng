import asyncio
import json

import typer
from rich.console import Console
from rich.json import JSON
from rich.table import Table

from src.memory.qdrant import QdrantService
from src.workflows.generation import (
    continue_generation_flow,
    finalize_generation_flow,
    initial_generation_flow,
)
from src.workflows.jobs import JobStore

# Create Typer app with help configuration
app = typer.Typer(
    name="factory",
    help="Narrative Factory CLI - AI-powered storytelling engine with Human-in-the-Loop workflow",
    no_args_is_help=True
)

# Initialize services
console = Console()
job_store = JobStore()

@app.command()
def generate(
    seed: str = typer.Argument(..., help="The chapter seed or initial prompt for story generation"),
    characters: str = typer.Option(
        "char_protagonist",
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
        character_list = [char.strip() for char in characters.split(",")]

        console.print(f"🎬 Starting generation with seed: [bold cyan]{seed}[/bold cyan]")
        console.print(f"📋 Active characters: {', '.join(character_list)}")

        # Run initial Prefect flow
        director_job_id = asyncio.run(initial_generation_flow(seed, character_list))

        console.print(f"✅ Director task initiated. Job ID: [bold yellow]{director_job_id}[/bold yellow]")
        console.print(f"📝 Use [bold green]factory review {director_job_id}[/bold green] to review the strategic brief")
        console.print(f"✅ Use [bold green]factory approve {director_job_id}[/bold green] to continue workflow")

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
        pending_jobs = job_store.get_pending_jobs()

        if not pending_jobs:
            console.print("✅ No jobs pending review", style="bold green")
            return

        # Create rich table for display
        table = Table(title="Pending Jobs")
        table.add_column("Job ID", style="cyan")
        table.add_column("Agent", style="magenta")
        table.add_column("Status", style="yellow")
        table.add_column("Created", style="blue")

        for job in pending_jobs:
            table.add_row(
                job.job_id[:12] + "...",  # Truncate for display
                job.agent,
                job.status,
                job.created_at.strftime("%H:%M:%S")
            )

        console.print(table)
        console.print("💡 Use [bold]factory review <job_id>[/bold] to examine job details")

    except Exception as e:
        console.print(f"❌ Error fetching status: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def review(
    job_id: str = typer.Argument(..., help="Job ID to review")
):
    """
    Review the output of a specific job.
    
    Displays the agent's output in a formatted, readable way.
    """
    try:
        job = job_store.get_job(job_id)

        if not job:
            console.print(f"❌ Job {job_id} not found", style="bold red")
            raise typer.Exit(1)

        console.print(f"📋 Reviewing Job: [bold cyan]{job_id}[/bold cyan]")
        console.print(f"🤖 Agent: [bold magenta]{job.agent}[/bold magenta]")
        console.print(f"📊 Status: [bold yellow]{job.status}[/bold yellow]")

        if job.output_payload:
            console.print("\n📄 Agent Output:")
            console.print(JSON(json.dumps(job.output_payload, indent=2)))
        else:
            console.print("⚠️ No output available yet", style="bold yellow")

        console.print(f"\n✅ Use [bold green]factory approve {job_id}[/bold green] to continue")
        console.print(f"❌ Use [bold red]factory reject {job_id} --feedback \"Your feedback\"[/bold red] to request changes")

    except Exception as e:
        console.print(f"❌ Error reviewing job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def approve(
    job_id: str = typer.Argument(..., help="Job ID to approve")
):
    """
    Approve a job and continue the workflow.
    
    Marks the job as approved and triggers the next stage of the generation pipeline.
    """
    try:
        # Get job details to determine next flow
        job = job_store.get_job(job_id)

        if not job:
            console.print(f"❌ Job {job_id} not found", style="bold red")
            raise typer.Exit(1)

        agent = job.agent
        console.print(f"✅ Approving {agent} job: [bold cyan]{job_id}[/bold cyan]")

        # Approve the job in JobStore
        approved_output = job_store.approve_job(job_id)

        if not approved_output:
            console.print("❌ Failed to approve job", style="bold red")
            raise typer.Exit(1)

        # Trigger next flow based on agent type
        if agent == "Director":
            console.print("🎯 Starting Tactician workflow...")
            tactician_job_id = continue_generation_flow(job_id)
            console.print(f"✅ Tactician task initiated. Job ID: [bold yellow]{tactician_job_id}[/bold yellow]")

        elif agent == "Tactician":
            console.print("✍️ Starting final generation (Weaver + Canonist)...")
            chapter_text = finalize_generation_flow(job_id)
            console.print("🎉 Chapter generation complete!")
            console.print(f"📊 Generated {len(chapter_text.split())} words")

        else:
            console.print(f"✅ Job approved. No automatic next step for {agent}")

    except Exception as e:
        console.print(f"❌ Error approving job: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def reject(
    job_id: str = typer.Argument(..., help="Job ID to reject"),
    feedback: str = typer.Option(..., "--feedback", "-f", help="Feedback message for the agent")
):
    """
    Reject a job with feedback for improvement.
    
    Marks the job as rejected and provides feedback for the agent to improve output.
    """
    try:
        console.print(f"❌ Rejecting job: [bold cyan]{job_id}[/bold cyan]")
        console.print(f"💬 Feedback: [italic]{feedback}[/italic]")

        # Update job as rejected with feedback
        result = job_store.reject_job(job_id, feedback)

        if not result:
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
        async def run_ingestion():
            from scripts.ingest import ingest_bootstrap_data
            await ingest_bootstrap_data()

        asyncio.run(run_ingestion())

        console.print("✅ Data ingestion complete", style="bold green")

    except Exception as e:
        console.print(f"❌ Error during ingestion: {e}", style="bold red")
        raise typer.Exit(1)

# Add development/testing commands
@app.command()
def test_connection():
    """
    Test connections to Redis and Qdrant services.
    
    Validates that all required services are accessible.
    """
    try:
        console.print("🔍 Testing service connections...")

        # Test Redis connection
        try:
            if job_store.health_check():
                console.print("✅ Redis connection: OK", style="bold green")
            else:
                console.print("❌ Redis connection: FAILED", style="bold red")
        except Exception as e:
            console.print(f"❌ Redis connection: FAILED - {e}", style="bold red")

        # Test Qdrant connection
        try:
            qdrant_service = QdrantService()
            # Basic connection test - use async
            async def test_qdrant():
                try:
                    info = await qdrant_service.get_collection_info("world_bible")
                    return True
                except:
                    return False

            if asyncio.run(test_qdrant()):
                console.print("✅ Qdrant connection: OK", style="bold green")
            else:
                console.print("⚠️ Qdrant connection: No collections found (run 'factory ingest' first)", style="bold yellow")
        except Exception as e:
            console.print(f"❌ Qdrant connection: FAILED - {e}", style="bold red")

    except Exception as e:
        console.print(f"❌ Error testing connections: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def test():
    """Test that the CLI is working correctly."""
    console.print("✅ Narrative Factory CLI is working!")
    console.print("🎭 MVP Phase 5: CLI Implementation complete")
    console.print("📝 Run 'factory --help' to see all available commands")
