import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
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
) -> None:
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
                    await qdrant_service.get_collection_info("world_bible")
                    return True
                except Exception:
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


# === PHASE 4 ENHANCEMENTS: INSPECTION TOOLS ===

@app.command()
def inspect_memory(
    query: str = typer.Argument(..., help="Entity to search for (character, location, concept)"),
    collection: str = typer.Option("world_bible", help="Qdrant collection to search"),
    limit: int = typer.Option(5, help="Maximum number of results to return"),
    similarity_threshold: float = typer.Option(0.7, help="Minimum similarity score")
):
    """Inspect memory/knowledge base for specific entities."""
    async def run_inspection():
        with console.status(f"[bold cyan]Searching knowledge base for '{query}'..."):
            try:
                memory_service = QdrantService()

                # Get collection info as a simple test
                collection_info = await memory_service.get_collection_info(collection)

                # For now, simulate results for demonstration
                spotlight_results = [
                    {
                        "source": "Memory System",
                        "content": f"Found collection '{collection}' with {collection_info.get('points_count', 0)} documents",
                        "score": 1.0
                    },
                    {
                        "source": "Search Query",
                        "content": f"Query: '{query}' - Memory system operational",
                        "score": 0.95
                    }
                ]
                ambient_results = []

                # Create rich formatted output
                table = Table(title=f"Knowledge Base Results for '{query}'")
                table.add_column("Source", style="cyan")
                table.add_column("Content", style="white")
                table.add_column("Score", style="green")

                for result in spotlight_results:
                    table.add_row(
                        result.get("source", "Unknown"),
                        result.get("content", "")[:100] + "...",
                        f"{result.get('score', 0):.3f}"
                    )

                console.print(table)

                if ambient_results:
                    console.print("\n[bold yellow]Related Context:[/bold yellow]")
                    for result in ambient_results[:3]:
                        console.print(Panel(
                            result.get("content", "")[:200] + "...",
                            title=result.get("source", "Related"),
                            border_style="dim"
                        ))

            except Exception as e:
                console.print(f"[red]Error inspecting memory: {e}[/red]")
                raise typer.Exit(1)

    asyncio.run(run_inspection())


@app.command()
def inspect_state(
    story_id: Optional[str] = typer.Option(None, help="Specific story ID to inspect"),
    show_details: bool = typer.Option(False, "--details", help="Show detailed state information")
):
    """Inspect current story state and continuity information."""
    async def run_state_inspection():
        from src.services.state_manager import StateManager

        with console.status("[bold cyan]Loading story state..."):
            try:
                state_manager = StateManager()
                state_summary = await state_manager.get_state_summary(story_id)

                # Create comprehensive state display
                state_table = Table(title="Story State Summary")
                state_table.add_column("Property", style="cyan")
                state_table.add_column("Value", style="white")

                for key, value in state_summary.items():
                    state_table.add_row(key.replace("_", " ").title(), str(value))

                console.print(state_table)

                if show_details:
                    full_state = await state_manager.load_latest_state(story_id)

                    # Show active plot threads
                    if full_state.active_plot_threads:
                        console.print("\n[bold yellow]Active Plot Threads:[/bold yellow]")
                        for thread in full_state.active_plot_threads:
                            console.print(Panel(
                                f"Priority: {thread.priority}/10\nStatus: {thread.status}\n{thread.description}",
                                title=f"Thread #{thread.id[:8]}",
                                border_style="blue"
                            ))

                    # Show recent knowledge revelations
                    if full_state.protagonist_knowledge:
                        console.print("\n[bold yellow]Recent Knowledge Revelations:[/bold yellow]")
                        for revelation in full_state.protagonist_knowledge[-3:]:
                            console.print(f"• {revelation.concept} (Chapter {revelation.chapter_discovered})")

            except Exception as e:
                console.print(f"[red]Error inspecting state: {e}[/red]")
                raise typer.Exit(1)

    asyncio.run(run_state_inspection())


# === PHASE 4 ENHANCEMENTS: CATALYST AND DRY-RUN WORKFLOW ===

@app.command()
def generate_enhanced(
    story_seed: str = typer.Argument(..., help="Initial story seed or prompt"),
    catalyst: Optional[str] = typer.Option(None, "--catalyst", "-c", help="Creative catalyst to inject into generation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Perform comprehensive dry run without LLM calls"),
    interactive: bool = typer.Option(True, "--interactive/--non-interactive", help="Enable human-in-the-loop checkpoints"),
    story_id: Optional[str] = typer.Option(None, help="Continue existing story by ID")
):
    """Enhanced story generation with catalyst injection and dry-run capabilities."""
    print("ENTERING generate_enhanced")
    async def run_enhanced_generation():
        print("ENTERING run_enhanced_generation")

        # Build comprehensive generation parameters
        generation_params = {
            "story_seed": story_seed,
            "interactive": interactive,
            "story_id": story_id
        }

        # Add catalyst if provided
        if catalyst:
            generation_params["catalyst"] = catalyst
            console.print(f"[yellow]Catalyst injected:[/yellow] {catalyst}")

        # Configure dry-run mode
        if dry_run:
            generation_params["dry_run"] = True
            console.print("[bold yellow]DRY RUN MODE - No LLM calls will be made[/bold yellow]")

            # Show what would be executed
            console.print("\n[bold cyan]Generation Plan:[/bold cyan]")
            console.print("1. Load story state and memory context")
            console.print("2. Director: Strategic planning phase")
            if catalyst:
                console.print(f"   └── Catalyst: {catalyst}")
            console.print("3. Tactician: Chapter beat breakdown")
            console.print("4. Weaver: Prose generation")
            console.print("5. Canonist: Continuity validation")
            console.print("6. Save updated story state")

            if not interactive:
                console.print("\n[dim]Run without --dry-run to execute actual generation[/dim]")
                return

        # Execute the enhanced workflow
        try:
            if dry_run:
                console.print("[bold green]✓[/bold green] Dry run completed - no actual generation performed")
                return

            # For now, fall back to existing workflow with enhancements
            character_list = ["char_protagonist"]  # Default character

            console.print(f"🎬 Starting enhanced generation with seed: [bold cyan]{story_seed}[/bold cyan]")
            if catalyst:
                console.print(f"⚡ Catalyst: [italic]{catalyst}[/italic]")

            # Run initial Prefect flow with enhancements
            director_job_id = await initial_generation_flow(story_seed, character_list, catalyst, False)

            console.print(f"✅ Enhanced Director task initiated. Job ID: [bold yellow]{director_job_id}[/bold yellow]")
            console.print(f"📝 Use [bold green]factory review {director_job_id}[/bold green] to review the strategic brief")
            console.print(f"✅ Use [bold green]factory approve {director_job_id}[/bold green] to continue workflow")

        except Exception as e:
            console.print(f"[red]Enhanced generation failed: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_enhanced_generation())


@app.command()
def catalyst_add(
    description: str = typer.Argument(..., help="Creative catalyst to inject"),
    target: str = typer.Option("next", help="Target: 'next' for next generation, or story_id"),
    priority: int = typer.Option(5, help="Priority level 1-10")
):
    """Add a creative catalyst for upcoming generation cycles."""
    async def run_catalyst_add():
        from src.services.catalyst_manager import CatalystManager

        try:
            catalyst_manager = CatalystManager()
            catalyst_id = await catalyst_manager.add_catalyst(
                description=description,
                target=target,
                priority=priority
            )

            console.print(f"[green]✓[/green] Catalyst added (ID: {catalyst_id[:8]})")
            console.print(f"[dim]Target: {target}, Priority: {priority}/10[/dim]")
            console.print(f"[yellow]Catalyst:[/yellow] {description}")

        except Exception as e:
            console.print(f"[red]Failed to add catalyst: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_catalyst_add())


@app.command()
def catalyst_list(
    target: str = typer.Option("next", help="Target to filter catalysts"),
    show_summary: bool = typer.Option(False, "--summary", help="Show catalyst summary")
):
    """List active catalysts for a target."""
    async def run_catalyst_list():
        from src.services.catalyst_manager import CatalystManager

        try:
            catalyst_manager = CatalystManager()

            if show_summary:
                summary = await catalyst_manager.get_catalyst_summary()

                summary_table = Table(title="Catalyst Summary")
                summary_table.add_column("Metric", style="cyan")
                summary_table.add_column("Value", style="white")

                for key, value in summary.items():
                    if key != "recent_catalysts":
                        summary_table.add_row(key.replace("_", " ").title(), str(value))

                console.print(summary_table)

                if "recent_catalysts" in summary and summary["recent_catalysts"]:
                    console.print("\n[bold yellow]Recent Catalysts:[/bold yellow]")
                    for catalyst in summary["recent_catalysts"]:
                        console.print(Panel(
                            f"Priority: {catalyst['priority']}/10\nStatus: {catalyst['status']}\nTarget: {catalyst['target']}\n{catalyst['description']}",
                            title=f"Catalyst #{catalyst['id']}",
                            border_style="green" if catalyst['status'] == "active" else "dim"
                        ))
            else:
                catalysts = await catalyst_manager.get_catalysts_for_target(target)

                if not catalysts:
                    console.print(f"[yellow]No active catalysts found for target '{target}'[/yellow]")
                    return

                table = Table(title=f"Active Catalysts for '{target}'")
                table.add_column("ID", style="cyan")
                table.add_column("Description", style="white")
                table.add_column("Priority", style="green")
                table.add_column("Created", style="blue")

                for catalyst in catalysts:
                    table.add_row(
                        catalyst.id[:8],
                        catalyst.description[:60] + "..." if len(catalyst.description) > 60 else catalyst.description,
                        f"{catalyst.priority}/10",
                        catalyst.created_at.strftime("%H:%M:%S")
                    )

                console.print(table)

        except Exception as e:
            console.print(f"[red]Failed to list catalysts: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_catalyst_list())
