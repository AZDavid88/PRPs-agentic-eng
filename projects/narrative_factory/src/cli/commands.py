import asyncio
import json
import time
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

# Import orchestration for agent mode
from src.agents.orchestration import get_orchestration_service


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
    DEPRECATED: Use 'factory ingest-materials' for new material ingestion.

    Legacy command for bootstrap data ingestion.
    """
    console.print("⚠️ This command is deprecated", style="bold yellow")
    console.print("💡 Use [bold]factory ingest-materials[/bold] for new material ingestion")
    console.print("📚 Use [bold]factory ingest-materials --help[/bold] for usage information")


# === PHASE 1B: MATERIAL INGESTION PIPELINE ===

@app.command(name="ingest-materials")
def ingest_materials(
    files: list[str] = typer.Argument(..., help="Material files or directories to ingest"),
    genre: str = typer.Option("unknown", "--genre", "-g", help="Primary genre context for classification"),
    additional_genres: str = typer.Option("", "--additional-genres", help="Comma-separated additional genres"),
    custom_categories: str = typer.Option("", "--custom-categories", help="Comma-separated custom categories"),
    processing_mode: str = typer.Option("pipeline", "--mode", "-m", help="Processing mode: pipeline, agent, or hybrid"),
    batch_size: int = typer.Option(10, "--batch-size", "-b", help="Batch size for processing (1-100)"),
    confidence_threshold: float = typer.Option(0.7, "--confidence", "-c", help="Minimum confidence threshold (0.0-1.0)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate inputs without processing"),
    async_mode: bool = typer.Option(True, "--async/--sync", help="Run in background (async) or foreground (sync)"),
    output_format: str = typer.Option("table", "--output", "-o", help="Output format: table, json, or stream"),
    story_id: Optional[str] = typer.Option(None, "--story-id", help="Associate with specific story"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing materials with same content hash")
):
    """
    Ingest materials using the Material Ingestion Pipeline.

    Processes text files through LLM classification, embedding generation,
    and storage in Qdrant with temporal gating and cross-reference detection.

    Examples:
        factory ingest-materials story.txt --genre fantasy
        factory ingest-materials *.txt --genre romance --mode agent
        factory ingest-materials lore/ --batch-size 20 --async
    """
    try:
        # Validate parameters
        if batch_size < 1 or batch_size > 100:
            console.print("❌ Batch size must be between 1 and 100", style="bold red")
            raise typer.Exit(1)

        if confidence_threshold < 0.0 or confidence_threshold > 1.0:
            console.print("❌ Confidence threshold must be between 0.0 and 1.0", style="bold red")
            raise typer.Exit(1)

        if processing_mode not in ["pipeline", "agent", "hybrid"]:
            console.print("❌ Processing mode must be: pipeline, agent, or hybrid", style="bold red")
            raise typer.Exit(1)

        if output_format not in ["table", "json", "stream"]:
            console.print("❌ Output format must be: table, json, or stream", style="bold red")
            raise typer.Exit(1)

        # Parse additional parameters
        additional_genres_list = [g.strip() for g in additional_genres.split(",") if g.strip()]
        custom_categories_list = [c.strip() for c in custom_categories.split(",") if c.strip()]

        # Run ingestion
        if async_mode and not dry_run:
            asyncio.run(_run_async_ingestion(
                files, genre, additional_genres_list, custom_categories_list,
                processing_mode, batch_size, confidence_threshold,
                output_format, story_id, overwrite
            ))
        else:
            asyncio.run(_run_sync_ingestion(
                files, genre, additional_genres_list, custom_categories_list,
                processing_mode, batch_size, confidence_threshold,
                dry_run, output_format, story_id, overwrite
            ))

    except KeyboardInterrupt:
        console.print("\n❌ Operation cancelled by user", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Ingestion failed: {e}", style="bold red")
        raise typer.Exit(1)


@app.command(name="ingest-status")
def ingest_status(
    job_id: Optional[str] = typer.Argument(None, help="Specific job ID to check"),
    show_all: bool = typer.Option(False, "--all", help="Show all ingestion jobs"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch job progress in real-time"),
    refresh_interval: int = typer.Option(2, "--interval", help="Refresh interval for watch mode (seconds)")
):
    """
    Check the status of material ingestion jobs.

    Examples:
        factory ingest-status                    # Show pending ingestion jobs
        factory ingest-status job123             # Check specific job
        factory ingest-status --all              # Show all jobs
        factory ingest-status job123 --watch     # Monitor job progress
    """
    try:
        asyncio.run(_run_ingestion_status(job_id, show_all, watch, refresh_interval))
    except KeyboardInterrupt:
        console.print("\n❌ Status monitoring cancelled", style="bold red")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ Status check failed: {e}", style="bold red")
        raise typer.Exit(1)


@app.command(name="ingest-validate")
def ingest_validate(
    files: list[str] = typer.Argument(..., help="Files or directories to validate"),
    genre: str = typer.Option("unknown", "--genre", "-g", help="Genre context for validation"),
    check_duplicates: bool = typer.Option(True, "--check-duplicates", help="Check for duplicate content"),
    estimate_cost: bool = typer.Option(True, "--estimate-cost", help="Estimate processing costs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed validation results")
):
    """
    Validate materials before ingestion without processing.

    Checks file formats, content structure, estimates costs,
    and identifies potential issues before expensive LLM processing.

    Examples:
        factory ingest-validate story.txt
        factory ingest-validate *.txt --verbose
        factory ingest-validate lore/ --check-duplicates
    """
    try:
        asyncio.run(_run_ingestion_validation(
            files, genre, check_duplicates, estimate_cost, verbose
        ))
    except Exception as e:
        console.print(f"❌ Validation failed: {e}", style="bold red")
        raise typer.Exit(1)


@app.command(name="ingest-config")
def ingest_config(
    test_connections: bool = typer.Option(True, "--test-connections", help="Test service connections"),
    setup_wizard: bool = typer.Option(False, "--setup", help="Run interactive setup wizard"),
    show_config: bool = typer.Option(False, "--show", help="Show current configuration"),
    validate_keys: bool = typer.Option(True, "--validate-keys", help="Validate API keys")
):
    """
    Configure and test the material ingestion pipeline.

    Tests connections to required services, validates API keys,
    and provides setup assistance for new installations.

    Examples:
        factory ingest-config                    # Test current setup
        factory ingest-config --setup            # Run setup wizard
        factory ingest-config --show             # Show configuration
    """
    try:
        asyncio.run(_run_ingestion_config(
            test_connections, setup_wizard, show_config, validate_keys
        ))
    except Exception as e:
        console.print(f"❌ Configuration check failed: {e}", style="bold red")
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


# === PHASE 1B: MATERIAL INGESTION IMPLEMENTATION ===

async def _run_async_ingestion(
    files: list[str],
    genre: str,
    additional_genres: list[str],
    custom_categories: list[str],
    processing_mode: str,
    batch_size: int,
    confidence_threshold: float,
    output_format: str,
    story_id: Optional[str],
    overwrite: bool
):
    """Run material ingestion in async mode with job tracking."""
    import uuid
    from pathlib import Path

    from src.ingestion.pipeline import MaterialIngestionPipeline, PipelineConfig
    from src.models.material_models import MaterialIngestionRequest

    # Validate and collect files
    material_files = []
    for file_pattern in files:
        if Path(file_pattern).is_dir():
            # Process directory
            dir_path = Path(file_pattern)
            text_files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md"))
            material_files.extend([str(f) for f in text_files])
        elif "*" in file_pattern:
            # Handle glob patterns
            import glob
            material_files.extend(glob.glob(file_pattern))
        else:
            # Single file
            material_files.append(file_pattern)

    if not material_files:
        console.print("❌ No valid files found", style="bold red")
        return

    # Read file contents
    materials = []
    for file_path in material_files:
        try:
            with open(file_path, encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    materials.append(content)
        except Exception as e:
            console.print(f"⚠️ Failed to read {file_path}: {e}", style="yellow")

    if not materials:
        console.print("❌ No readable content found in files", style="bold red")
        return

    # Create ingestion request
    request = MaterialIngestionRequest(
        materials=materials,
        genre_context=genre,
        additional_genres=additional_genres,
        custom_categories=custom_categories if custom_categories else None,
        processing_mode=processing_mode,
        batch_size=batch_size,
        min_confidence_threshold=confidence_threshold,
        story_id=story_id
    )

    # Generate job ID
    job_id = f"ingest_{uuid.uuid4().hex[:8]}"

    console.print(f"🚀 Starting async ingestion job: [bold cyan]{job_id}[/bold cyan]")
    console.print(f"📁 Processing {len(materials)} materials from {len(material_files)} files")
    console.print(f"🎭 Genre: [bold]{genre}[/bold]")
    if additional_genres:
        console.print(f"🎨 Additional genres: {', '.join(additional_genres)}")
    console.print(f"⚙️ Mode: [bold]{processing_mode}[/bold], Batch size: {batch_size}")

    # Store job info (simplified - in production would use JobStore)
    # job_info = {
    #     "job_id": job_id,
    #     "status": "running",
    #     "started_at": time.time(),
    #     "files_count": len(material_files),
    #     "materials_count": len(materials),
    #     "genre": genre,
    #     "mode": processing_mode
    # }

    try:
        # Initialize pipeline
        pipeline_config = PipelineConfig(
            default_processing_mode=processing_mode,
            batch_size=batch_size,
            min_confidence_threshold=confidence_threshold,
            enable_cost_monitoring=True
        )

        pipeline = MaterialIngestionPipeline(pipeline_config)

        # Process materials
        with console.status(f"[bold green]Processing {len(materials)} materials..."):
            response = await pipeline.process_materials(request)

        # Display results based on output format
        if output_format == "json":
            import json
            result_data = {
                "job_id": job_id,
                "status": response.status,
                "materials_processed": response.materials_processed,
                "processing_time": response.processing_time,
                "cost_estimate": response.cost_estimate,
                "average_confidence": response.average_confidence,
                "category_distribution": response.category_distribution
            }
            console.print(json.dumps(result_data, indent=2))
        else:
            # Rich table format
            console.print(f"\n✅ Ingestion completed: [bold cyan]{job_id}[/bold cyan]")

            # Summary table
            summary_table = Table(title="Ingestion Summary")
            summary_table.add_column("Metric", style="cyan")
            summary_table.add_column("Value", style="white")

            summary_table.add_row("Job ID", job_id)
            summary_table.add_row("Status", response.status)
            summary_table.add_row("Materials Processed", str(response.materials_processed))
            summary_table.add_row("Processing Time", f"{response.processing_time:.2f}s")
            summary_table.add_row("Cost Estimate", f"${response.cost_estimate:.4f}")
            summary_table.add_row("Average Confidence", f"{response.average_confidence:.2f}")

            console.print(summary_table)

            # Category distribution
            if response.category_distribution:
                console.print("\n📊 Category Distribution:")
                cat_table = Table()
                cat_table.add_column("Category", style="magenta")
                cat_table.add_column("Count", style="green")

                for category, count in response.category_distribution.items():
                    cat_table.add_row(category, str(count))

                console.print(cat_table)

        # Success message
        console.print(f"\n🎉 Ingestion job [bold]{job_id}[/bold] completed successfully!")
        console.print(f"📊 Use [bold]factory ingest-status {job_id}[/bold] to view detailed results")

    except Exception as e:
        console.print(f"\n❌ Ingestion job [bold]{job_id}[/bold] failed: {e}", style="bold red")
        if "rate limit" in str(e).lower():
            console.print("💡 Try reducing batch size or wait before retrying", style="yellow")
        raise


async def _run_sync_ingestion(
    files: list[str],
    genre: str,
    additional_genres: list[str],
    custom_categories: list[str],
    processing_mode: str,
    batch_size: int,
    confidence_threshold: float,
    dry_run: bool,
    output_format: str,
    story_id: Optional[str],
    overwrite: bool
):
    """Run material ingestion in sync mode with progress feedback."""
    from pathlib import Path

    # Validate and collect files (same as async)
    material_files = []
    for file_pattern in files:
        if Path(file_pattern).is_dir():
            dir_path = Path(file_pattern)
            text_files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md"))
            material_files.extend([str(f) for f in text_files])
        elif "*" in file_pattern:
            import glob
            material_files.extend(glob.glob(file_pattern))
        else:
            material_files.append(file_pattern)

    if not material_files:
        console.print("❌ No valid files found", style="bold red")
        return

    # Show dry-run information
    if dry_run:
        console.print("🔍 [bold yellow]DRY RUN MODE[/bold yellow] - No actual processing")
        console.print(f"📁 Would process {len(material_files)} files")
        console.print(f"🎭 Genre: [bold]{genre}[/bold]")
        if additional_genres:
            console.print(f"🎨 Additional genres: {', '.join(additional_genres)}")
        console.print(f"⚙️ Mode: [bold]{processing_mode}[/bold], Batch size: {batch_size}")
        console.print(f"🎯 Confidence threshold: {confidence_threshold}")

        # Show file list
        file_table = Table(title="Files to Process")
        file_table.add_column("File", style="cyan")
        file_table.add_column("Size", style="green")

        total_size = 0
        for file_path in material_files[:10]:  # Show first 10
            try:
                size = Path(file_path).stat().st_size
                total_size += size
                file_table.add_row(file_path, f"{size:,} bytes")
            except Exception:
                file_table.add_row(file_path, "Error reading")

        if len(material_files) > 10:
            file_table.add_row(f"... and {len(material_files) - 10} more", "")

        console.print(file_table)
        console.print(f"📊 Total estimated size: {total_size:,} bytes")
        console.print("✅ Dry run complete - run without --dry-run to process")
        return

    # Run actual sync processing (similar to async but with progress bars)
    await _run_async_ingestion(
        files, genre, additional_genres, custom_categories,
        processing_mode, batch_size, confidence_threshold,
        output_format, story_id, overwrite
    )


async def _run_ingestion_status(
    job_id: Optional[str],
    show_all: bool,
    watch: bool,
    refresh_interval: int
):
    """Show ingestion job status."""
    # Simplified implementation - in production would query JobStore
    if job_id:
        console.print(f"📊 Status for job: [bold cyan]{job_id}[/bold cyan]")
        console.print("💡 Job tracking integration with JobStore pending in Phase 1B")
        console.print("⚠️ Use existing job commands for now: [bold]factory status[/bold]")
    else:
        console.print("📋 Ingestion Job Status")
        console.print("💡 Integration with existing JobStore pending")
        console.print("📊 Use [bold]factory status[/bold] to see all pending jobs")


async def _run_ingestion_validation(
    files: list[str],
    genre: str,
    check_duplicates: bool,
    estimate_cost: bool,
    verbose: bool
):
    """Validate materials before ingestion."""
    import hashlib
    from pathlib import Path

    # Collect files
    material_files = []
    for file_pattern in files:
        if Path(file_pattern).is_dir():
            dir_path = Path(file_pattern)
            text_files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md"))
            material_files.extend([str(f) for f in text_files])
        elif "*" in file_pattern:
            import glob
            material_files.extend(glob.glob(file_pattern))
        else:
            material_files.append(file_pattern)

    if not material_files:
        console.print("❌ No valid files found", style="bold red")
        return

    console.print(f"🔍 Validating {len(material_files)} files...")

    # Validation results
    valid_files = []
    invalid_files = []
    total_size = 0
    content_hashes = {}
    duplicates = []

    # Validate each file
    for file_path in material_files:
        try:
            path = Path(file_path)
            if not path.exists():
                invalid_files.append((file_path, "File not found"))
                continue

            if not path.is_file():
                invalid_files.append((file_path, "Not a regular file"))
                continue

            size = path.stat().st_size
            if size == 0:
                invalid_files.append((file_path, "Empty file"))
                continue

            if size > 10 * 1024 * 1024:  # 10MB limit
                invalid_files.append((file_path, "File too large (>10MB)"))
                continue

            # Read and check content
            with open(file_path, encoding='utf-8') as f:
                content = f.read()

            if len(content.strip()) < 10:
                invalid_files.append((file_path, "Content too short"))
                continue

            # Check for duplicates
            if check_duplicates:
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                if content_hash in content_hashes:
                    duplicates.append((file_path, content_hashes[content_hash]))
                else:
                    content_hashes[content_hash] = file_path

            valid_files.append(file_path)
            total_size += size

        except UnicodeDecodeError:
            invalid_files.append((file_path, "Not valid UTF-8 text"))
        except Exception as e:
            invalid_files.append((file_path, str(e)))

    # Display results
    validation_table = Table(title="Validation Results")
    validation_table.add_column("Metric", style="cyan")
    validation_table.add_column("Value", style="white")

    validation_table.add_row("Total Files", str(len(material_files)))
    validation_table.add_row("Valid Files", str(len(valid_files)))
    validation_table.add_row("Invalid Files", str(len(invalid_files)))
    validation_table.add_row("Total Size", f"{total_size:,} bytes")

    if duplicates:
        validation_table.add_row("Duplicates Found", str(len(duplicates)))

    console.print(validation_table)

    # Show invalid files
    if invalid_files:
        console.print("\n❌ Invalid Files:")
        invalid_table = Table()
        invalid_table.add_column("File", style="red")
        invalid_table.add_column("Issue", style="yellow")

        for file_path, issue in invalid_files:
            invalid_table.add_row(file_path, issue)

        console.print(invalid_table)

    # Show duplicates
    if duplicates:
        console.print("\n🔄 Duplicate Content:")
        dup_table = Table()
        dup_table.add_column("File 1", style="yellow")
        dup_table.add_column("File 2", style="yellow")

        for file1, file2 in duplicates:
            dup_table.add_row(file1, file2)

        console.print(dup_table)

    # Cost estimation
    if estimate_cost and valid_files:
        estimated_tokens = total_size // 4  # Rough estimate: 4 chars per token
        estimated_cost = (estimated_tokens / 1000) * 0.01  # $0.01 per 1K tokens

        console.print("\n💰 Cost Estimate:")
        console.print(f"📊 Estimated tokens: {estimated_tokens:,}")
        console.print(f"💵 Estimated cost: ${estimated_cost:.4f}")

    # Summary
    if len(valid_files) == len(material_files):
        console.print("\n✅ All files are valid for ingestion", style="bold green")
    elif valid_files:
        console.print(f"\n⚠️ {len(valid_files)}/{len(material_files)} files are valid", style="yellow")
    else:
        console.print("\n❌ No valid files found", style="bold red")


async def _run_ingestion_config(
    test_connections: bool,
    setup_wizard: bool,
    show_config: bool,
    validate_keys: bool
):
    """Configure and test material ingestion pipeline."""
    from src.config import config

    if show_config:
        console.print("⚙️ Current Configuration:")

        config_table = Table(title="Material Ingestion Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")

        # Show relevant config
        config_table.add_row("Embedding Provider", config.models.embedding_provider)
        config_table.add_row("Qdrant URL", config.qdrant.url or "Not configured")
        config_table.add_row("OpenAI API Key", "✅ Set" if config.models.openai_api_key else "❌ Not set")
        config_table.add_row("Gemini API Key", "✅ Set" if config.models.gemini_api_key else "❌ Not set")

        console.print(config_table)

    if test_connections:
        console.print("\n🔍 Testing service connections...")

        # Test embedding service
        try:
            from src.memory.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
            test_embedding = await embedding_service.generate_embedding("test")
            if test_embedding and len(test_embedding) > 0:
                console.print("✅ Embedding service: OK", style="bold green")
            else:
                console.print("❌ Embedding service: Failed", style="bold red")
        except Exception as e:
            console.print(f"❌ Embedding service: {e}", style="bold red")

        # Test Qdrant
        try:
            from src.ingestion.storage import MaterialStorage
            storage_service = MaterialStorage()
            health_check = await storage_service.health_check()
            if health_check["storage_service_healthy"]:
                console.print("✅ Qdrant storage: OK", style="bold green")
            else:
                console.print(f"❌ Qdrant storage: {health_check['errors']}", style="bold red")
        except Exception as e:
            console.print(f"❌ Qdrant storage: {e}", style="bold red")

        # Test LLM providers
        if validate_keys:
            try:
                from src.ingestion.classifier import MaterialClassifier
                classifier = MaterialClassifier()
                health_check = await classifier.health_check()
                if health_check["classifier_ready"]:
                    console.print("✅ LLM classifier: OK", style="bold green")
                else:
                    console.print(f"❌ LLM classifier: {health_check['errors']}", style="bold red")
            except Exception as e:
                console.print(f"❌ LLM classifier: {e}", style="bold red")

    if setup_wizard:
        console.print("\n🧙 Setup Wizard:")
        console.print("💡 Interactive setup wizard to be implemented")
        console.print("📚 For now, ensure environment variables are set:")
        console.print("   - OPENAI_API_KEY or GEMINI_API_KEY")
        console.print("   - QDRANT_URL and QDRANT_API_KEY")
        console.print("   - Check .env file in project root")

    console.print("\n✅ Configuration check complete")


# === LIBRARIAN AGENT CLI COMMANDS ===

@app.command(name="analyze-materials")
def analyze_materials(
    job_id: str = typer.Argument(..., help="Ingestion job ID to analyze"),
    depth: str = typer.Option("standard", help="Analysis depth: quick, standard, comprehensive"),
    cross_references: bool = typer.Option(True, help="Generate cross-references"),
    output: str = typer.Option("table", help="Output format: table, json, summary"),
    save_report: bool = typer.Option(False, help="Save detailed analysis report"),
    concurrent_limit: int = typer.Option(10, help="Max concurrent processing (1-20)")
):
    """Analyze ingested materials using LibrarianAgent."""

    async def run_analysis():
        try:
            # Validation
            if concurrent_limit < 1 or concurrent_limit > 20:
                console.print("[red]Error: Concurrent limit must be between 1 and 20[/red]")
                raise typer.Exit(1)

            # Get materials from ingestion job
            job = job_store.get_job(job_id)
            if not job or job.agent != "MaterialIngestion":
                console.print(f"[red]Error: Job {job_id} not found or not a material ingestion job[/red]")
                raise typer.Exit(1)

            console.print(f"🔍 Analyzing materials from job: [bold cyan]{job_id}[/bold cyan]")
            console.print(f"📊 Analysis depth: {depth}, Cross-references: {cross_references}")

            # Extract classifications from job output
            job_output = job.output_payload
            if "response" in job_output and "classifications" in job_output["response"]:
                classifications_data = job_output["response"]["classifications"]
            else:
                console.print("[red]Error: No material classifications found in job output[/red]")
                raise typer.Exit(1)

            # Convert to MaterialClassification objects
            from src.agents.librarian import LibrarianAgent
            from src.models.librarian_models import MaterialAnalysisRequest
            from src.models.material_models import MaterialClassification

            classifications = [
                MaterialClassification.model_validate(item) for item in classifications_data
            ]

            console.print(f"📋 Found {len(classifications)} materials to analyze")

            # Create LibrarianAgent and analyze
            with console.status("[bold green]Running material analysis..."):
                librarian = LibrarianAgent()

                try:
                    # Create analysis request
                    request = MaterialAnalysisRequest(
                        classifications=classifications,
                        analysis_depth=depth,
                        enable_cross_references=cross_references,
                        enable_quality_assessment=True,
                        concurrent_limit=concurrent_limit
                    )

                    # Execute analysis
                    result = await librarian.analyze_materials(request)

                    # Display results based on output format
                    if output == "json":
                        console.print_json(result.model_dump_json())
                    elif output == "summary":
                        _display_analysis_summary(result)
                    else:
                        _display_analysis_results_table(result)

                    # Save report if requested
                    if save_report:
                        report_file = f"analysis_report_{job_id}_{int(time.time())}.json"
                        with open(report_file, 'w') as f:
                            f.write(result.model_dump_json(indent=2))
                        console.print(f"📄 Report saved to: [bold cyan]{report_file}[/bold cyan]")

                finally:
                    await librarian.close()

        except Exception as e:
            console.print(f"[red]Error analyzing materials: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_analysis())


@app.command(name="validate-content")
def validate_content(
    job_id: str = typer.Argument(..., help="Ingestion job ID to validate"),
    quality_threshold: float = typer.Option(0.8, help="Quality threshold (0.0-1.0)"),
    check_consistency: bool = typer.Option(True, help="Check content consistency"),
    output: str = typer.Option("table", help="Output format: table, json"),
    fix_issues: bool = typer.Option(False, help="Attempt to fix identified issues")
):
    """Validate content quality using LibrarianAgent."""

    async def run_validation():
        try:
            # Validation
            if quality_threshold < 0.0 or quality_threshold > 1.0:
                console.print("[red]Error: Quality threshold must be between 0.0 and 1.0[/red]")
                raise typer.Exit(1)

            # Get materials from ingestion job
            job = job_store.get_job(job_id)
            if not job or job.agent != "MaterialIngestion":
                console.print(f"[red]Error: Job {job_id} not found or not a material ingestion job[/red]")
                raise typer.Exit(1)

            console.print(f"✅ Validating content from job: [bold cyan]{job_id}[/bold cyan]")
            console.print(f"🎯 Quality threshold: {quality_threshold}")

            # Extract classifications
            job_output = job.output_payload
            if "response" in job_output and "classifications" in job_output["response"]:
                classifications_data = job_output["response"]["classifications"]
            else:
                console.print("[red]Error: No material classifications found in job output[/red]")
                raise typer.Exit(1)

            # Convert to MaterialClassification objects
            from src.agents.librarian import LibrarianAgent
            from src.models.librarian_models import MaterialAnalysisRequest
            from src.models.material_models import MaterialClassification

            classifications = [
                MaterialClassification.model_validate(item) for item in classifications_data
            ]

            console.print(f"📋 Validating {len(classifications)} materials")

            # Create LibrarianAgent and validate
            with console.status("[bold green]Running content validation..."):
                librarian = LibrarianAgent()

                try:
                    # Create analysis request focused on quality
                    request = MaterialAnalysisRequest(
                        classifications=classifications,
                        analysis_depth="standard",
                        enable_cross_references=False,  # Focus on quality only
                        enable_quality_assessment=True,
                        concurrent_limit=10
                    )

                    # Execute analysis
                    result = await librarian.analyze_materials(request)

                    # Filter results by quality threshold
                    quality_results = []
                    passed_count = 0
                    failed_count = 0

                    for analysis_result in result.results:
                        if analysis_result.quality_assessment:
                            qa = analysis_result.quality_assessment
                            if qa.quality_score >= quality_threshold:
                                passed_count += 1
                            else:
                                failed_count += 1
                                quality_results.append((analysis_result, qa))

                    # Display validation results
                    if output == "json":
                        validation_data = {
                            "quality_threshold": quality_threshold,
                            "total_materials": len(classifications),
                            "passed": passed_count,
                            "failed": failed_count,
                            "failed_materials": [
                                {
                                    "material_id": result[0].source_classification.id,
                                    "quality_score": result[1].quality_score,
                                    "issues": result[1].issues_found,
                                    "recommendations": result[1].recommendations
                                }
                                for result in quality_results
                            ]
                        }
                        console.print_json(json.dumps(validation_data, indent=2))
                    else:
                        _display_validation_results_table(quality_results, passed_count, failed_count, quality_threshold)

                    # Attempt fixes if requested
                    if fix_issues and quality_results:
                        console.print(f"\n🔧 Fix suggestions for {len(quality_results)} failed materials:")
                        for analysis_result, qa in quality_results:
                            console.print(f"\n📝 Material: [bold]{analysis_result.source_classification.id}[/bold]")
                            for rec in qa.recommendations:
                                console.print(f"   💡 {rec}")

                finally:
                    await librarian.close()

        except Exception as e:
            console.print(f"[red]Error validating content: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_validation())


@app.command(name="agent-analyze")
def agent_analyze_materials(
    job_id: str = typer.Argument(..., help="Material ingestion job ID to analyze"),
    session_id: Optional[str] = typer.Option(None, "--session", help="Session ID for agent tracking"),
    analysis_depth: str = typer.Option("standard", "--depth", help="Analysis depth: quick, standard, comprehensive"),
    interactive: bool = typer.Option(True, "--interactive/--non-interactive", help="Enable interactive agent mode"),
    client_type: str = typer.Option("openai", "--client", help="LLM client type: openai, gemini"),
    timeout: int = typer.Option(300, "--timeout", help="Agent execution timeout in seconds"),
    output_format: str = typer.Option("table", help="Output format: table, json"),
    save_session: bool = typer.Option(False, "--save-session", help="Save agent session for replay")
):
    """
    Analyze materials using LibrarianAgent in full agent orchestration mode.

    This command creates a proper agent session, uses agent communication protocols,
    and provides full lifecycle management for material analysis.

    Examples:
        factory agent-analyze job_12345 --depth comprehensive
        factory agent-analyze job_12345 --session story_1 --interactive
        factory agent-analyze job_12345 --client gemini --save-session
    """
    async def run_agent_analysis():
        try:
            # Initialize orchestration service
            orchestration = get_orchestration_service()
            # communication = get_communication_service()  # Reserved for future message-based features

            # Generate session ID if not provided
            session_id_var = session_id
            if not session_id_var:
                import uuid
                session_id_var = f"analysis_{uuid.uuid4().hex[:8]}"

            console.print("🤖 Starting agent-mode analysis")
            console.print(f"📋 Job ID: [bold cyan]{job_id}[/bold cyan]")
            console.print(f"🔗 Session: [bold yellow]{session_id_var}[/bold yellow]")
            console.print(f"🧠 Client: [bold green]{client_type}[/bold green]")

            # Get materials from job
            job = job_store.get_job(job_id)
            if not job:
                console.print(f"[red]Error: Job {job_id} not found[/red]")
                raise typer.Exit(1)

            # Extract classifications
            output_data = job.output_payload.get("response", {})
            classifications_data = output_data.get("classifications", [])

            if not classifications_data:
                console.print("[red]Error: No material classifications found in job output[/red]")
                raise typer.Exit(1)

            # Convert to MaterialClassification objects
            from src.models.material_models import MaterialClassification

            classifications = [MaterialClassification(**data) for data in classifications_data]

            console.print(f"📚 Found {len(classifications)} materials to analyze")

            # Initialize LibrarianAgent through orchestration
            console.print("\n🚀 Initializing LibrarianAgent...")
            with console.status("[bold blue]Creating agent session..."):
                librarian_id = await orchestration.initialize_agent(
                    agent_type="librarian",
                    client_type=client_type,
                    session_id=session_id_var
                )

            console.print(f"✅ LibrarianAgent initialized: [bold cyan]{librarian_id}[/bold cyan]")

            # Prepare analysis request
            analysis_config = {
                "analysis_depth": analysis_depth,
                "enable_cross_references": True,
                "enable_quality_assessment": True,
                "concurrent_limit": 10
            }

            request_data = {
                "materials": classifications,
                "analysis_config": analysis_config
            }

            # Interactive confirmation if enabled
            if interactive:
                console.print("\n📋 Analysis Configuration:")
                config_table = Table()
                config_table.add_column("Setting", style="cyan")
                config_table.add_column("Value", style="white")

                config_table.add_row("Analysis Depth", analysis_depth)
                config_table.add_row("Cross References", "Enabled")
                config_table.add_row("Quality Assessment", "Enabled")
                config_table.add_row("Materials Count", str(len(classifications)))
                config_table.add_row("Estimated Time", f"{len(classifications) * 2}s")

                console.print(config_table)

                if not typer.confirm("\nProceed with analysis?"):
                    await orchestration.shutdown_agent(librarian_id)
                    console.print("❌ Analysis cancelled")
                    raise typer.Exit(0)

            # Execute analysis through orchestration
            console.print("\n🔍 Running analysis...")
            with console.status(f"[bold green]Analyzing {len(classifications)} materials...") as status:
                start_time = time.time()

                result = await orchestration.execute_agent(
                    agent_id=librarian_id,
                    request_data=request_data,
                    context={"analysis_mode": "interactive", "session_id": session_id_var},
                    user_id="cli_user"
                )

                processing_time = time.time() - start_time

            console.print(f"✅ Analysis completed in {processing_time:.2f}s")

            # Display results
            if output_format == "json":
                console.print(JSON(result.model_dump_json()))
            else:
                _display_agent_analysis_results(result, processing_time)

            # Save session if requested
            if save_session:
                session_file = f"agent_session_{session_id_var}.json"
                session_data = {
                    "session_id": session_id_var,
                    "agent_id": librarian_id,
                    "job_id": job_id,
                    "analysis_config": analysis_config,
                    "result": result.model_dump(),
                    "processing_time": processing_time,
                    "timestamp": time.time()
                }

                with open(session_file, 'w') as f:
                    json.dump(session_data, f, indent=2, default=str)

                console.print(f"💾 Session saved to: [bold blue]{session_file}[/bold blue]")

            # Get orchestration status
            if interactive:
                status = await orchestration.get_orchestration_status()
                console.print(f"\n📊 Active agents: {sum(len(agents) for agents in status['active_agents'].values())}")
                console.print(f"📈 Session duration: {processing_time:.2f}s")

            # Clean up
            await orchestration.shutdown_agent(librarian_id)
            console.print(f"🧹 Agent {librarian_id} shutdown completed")

        except Exception as e:
            console.print(f"[red]Error in agent analysis: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_agent_analysis())


def _display_agent_analysis_results(result, processing_time: float):
    """Display agent analysis results in formatted tables."""
    # Summary table
    summary_table = Table(title="Agent Analysis Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Materials Processed", f"{result.successful_count}/{result.successful_count + result.failed_count}")
    summary_table.add_row("Success Rate", f"{result.get_success_rate():.1f}%")
    summary_table.add_row("Cross References", str(result.cross_references_generated))
    summary_table.add_row("Quality Issues", str(result.quality_issues_found))
    summary_table.add_row("Processing Time", f"{processing_time:.2f}s")

    console.print(summary_table)

    # Results details
    if result.results:
        console.print("\n📋 Material Analysis Results:")

        results_table = Table()
        results_table.add_column("Material ID", style="cyan")
        results_table.add_column("Category", style="green")
        results_table.add_column("Quality", style="yellow")
        results_table.add_column("Cross Refs", style="blue")
        results_table.add_column("Processing", style="white")

        for analysis_result in result.results[:10]:  # Show first 10
            material = analysis_result.source_classification
            quality = analysis_result.quality_assessment
            quality_text = "✅ Pass" if quality and quality.is_acceptable else "❌ Issues"
            cross_refs = len(analysis_result.cross_references)
            processing_text = f"{getattr(analysis_result, 'processing_time', 0):.1f}s"

            results_table.add_row(
                material.material_id,
                material.primary_category,
                quality_text,
                str(cross_refs),
                processing_text
            )

        console.print(results_table)

        if len(result.results) > 10:
            console.print(f"... and {len(result.results) - 10} more results")

    # Show quality issues if any
    if result.quality_issues_found > 0:
        console.print(f"\n⚠️ Found {result.quality_issues_found} quality issues")
        console.print("Use [bold]factory validate-content[/bold] for detailed quality analysis")


@app.command(name="agent-session")
def agent_session_management(
    action: str = typer.Argument(..., help="Action: list, status, shutdown, replay"),
    session_id: Optional[str] = typer.Option(None, help="Session ID for specific operations"),
    all_sessions: bool = typer.Option(False, "--all", help="Apply to all active sessions")
):
    """
    Manage agent sessions and orchestration.

    Examples:
        factory agent-session list
        factory agent-session status --session story_1
        factory agent-session shutdown --session story_1
        factory agent-session shutdown --all
    """
    async def run_session_management():
        try:
            orchestration = get_orchestration_service()

            if action == "list":
                status = await orchestration.get_orchestration_status()

                console.print("🤖 Agent Orchestration Status")

                # Active agents summary
                agents_table = Table(title="Active Agents by Type")
                agents_table.add_column("Agent Type", style="cyan")
                agents_table.add_column("Active Count", style="white")
                agents_table.add_column("Agent IDs", style="green")

                for agent_type, agents in status['active_agents'].items():
                    if agents:
                        agent_ids = ', '.join(agents[:3])
                        if len(agents) > 3:
                            agent_ids += f" (+{len(agents) - 3} more)"
                        agents_table.add_row(agent_type.title(), str(len(agents)), agent_ids)

                console.print(agents_table)

                # Active sessions
                if status['session_details']:
                    console.print("\n📋 Active Sessions:")
                    sessions_table = Table()
                    sessions_table.add_column("Session ID", style="cyan")
                    sessions_table.add_column("Agents", style="white")
                    sessions_table.add_column("Duration", style="green")
                    sessions_table.add_column("Steps", style="yellow")

                    for session_id, details in status['session_details'].items():
                        duration = f"{details['duration']:.1f}s"
                        steps = ', '.join(details['pipeline_steps']) if details['pipeline_steps'] else "None"
                        sessions_table.add_row(
                            session_id,
                            str(details['agents']),
                            duration,
                            steps
                        )

                    console.print(sessions_table)
                else:
                    console.print("\n📭 No active sessions")

            elif action == "status":
                if not session_id:
                    console.print("[red]Error: --session required for status action[/red]")
                    raise typer.Exit(1)

                status = await orchestration.get_orchestration_status()
                session_details = status['session_details'].get(session_id)

                if not session_details:
                    console.print(f"[red]Session {session_id} not found[/red]")
                    raise typer.Exit(1)

                console.print(f"📋 Session Status: [bold cyan]{session_id}[/bold cyan]")

                status_table = Table()
                status_table.add_column("Property", style="cyan")
                status_table.add_column("Value", style="white")

                status_table.add_row("Active Agents", str(session_details['agents']))
                status_table.add_row("Duration", f"{session_details['duration']:.1f}s")
                status_table.add_row("Pipeline Steps", ', '.join(session_details['pipeline_steps']))

                console.print(status_table)

            elif action == "shutdown":
                if all_sessions:
                    status = await orchestration.get_orchestration_status()
                    session_ids = list(status['session_details'].keys())

                    if not session_ids:
                        console.print("📭 No active sessions to shutdown")
                        return

                    console.print(f"🛑 Shutting down {len(session_ids)} sessions...")
                    for sid in session_ids:
                        await orchestration.shutdown_session(sid)
                        console.print(f"✅ Session {sid} shutdown")

                elif session_id:
                    console.print(f"🛑 Shutting down session: [bold cyan]{session_id}[/bold cyan]")
                    await orchestration.shutdown_session(session_id)
                    console.print("✅ Session shutdown completed")
                else:
                    console.print("[red]Error: Either --session or --all required for shutdown[/red]")
                    raise typer.Exit(1)

            elif action == "replay":
                if not session_id:
                    console.print("[red]Error: --session required for replay action[/red]")
                    raise typer.Exit(1)

                session_file = f"agent_session_{session_id}.json"
                try:
                    with open(session_file) as f:
                        session_data = json.load(f)

                    console.print(f"📼 Replaying session: [bold cyan]{session_id}[/bold cyan]")
                    console.print(JSON(json.dumps(session_data, indent=2)))

                except FileNotFoundError:
                    console.print(f"[red]Session file {session_file} not found[/red]")
                    raise typer.Exit(1)

            else:
                console.print(f"[red]Unknown action: {action}[/red]")
                console.print("Valid actions: list, status, shutdown, replay")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Error in session management: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_session_management())


@app.command(name="material-stats")
def material_stats(
    show_details: bool = typer.Option(False, "--details", help="Show detailed statistics"),
    collection: Optional[str] = typer.Option(None, help="Filter by material collection"),
    export_csv: bool = typer.Option(False, help="Export statistics to CSV")
):
    """Show material analysis statistics."""

    async def run_stats():
        try:
            from src.memory.service import get_memory_service

            console.print("📊 Material Analysis Statistics")

            with console.status("[bold green]Gathering statistics..."):
                memory_service = get_memory_service()
                await memory_service.initialize()

                try:
                    # Get material statistics
                    stats = await memory_service.get_material_statistics()

                    if "error" in stats:
                        console.print(f"[red]Error gathering statistics: {stats['error']}[/red]")
                        return

                    # Basic statistics table
                    stats_table = Table(title="Material Storage Overview")
                    stats_table.add_column("Metric", style="cyan")
                    stats_table.add_column("Value", style="white")

                    stats_table.add_row("Total Materials", f"{stats['total_materials']:,}")
                    stats_table.add_row("Collections", f"{len(stats['collections'])}")
                    stats_table.add_row("Categories", f"{len(stats['categories'])}")

                    console.print(stats_table)

                    # Category breakdown
                    if stats['categories']:
                        category_table = Table(title="Materials by Category")
                        category_table.add_column("Category", style="cyan")
                        category_table.add_column("Count", style="green")
                        category_table.add_column("Percentage", style="yellow")

                        total = stats['total_materials']
                        for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
                            percentage = (count / total * 100) if total > 0 else 0
                            category_table.add_row(category, f"{count:,}", f"{percentage:.1f}%")

                        console.print(category_table)

                    # Detailed collection info
                    if show_details and stats['collections']:
                        collection_table = Table(title="Collection Details")
                        collection_table.add_column("Collection", style="cyan")
                        collection_table.add_column("Points", style="green")

                        for coll, count in sorted(stats['collections'].items(), key=lambda x: x[1], reverse=True):
                            if collection is None or collection in coll:
                                collection_table.add_row(coll, f"{count:,}")

                        console.print(collection_table)

                    # Export to CSV if requested
                    if export_csv:
                        import csv
                        import time

                        csv_file = f"material_stats_{int(time.time())}.csv"
                        with open(csv_file, 'w', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow(["Category", "Count", "Collection"])

                            for category, count in stats['categories'].items():
                                collection_name = f"materials_{category}"
                                writer.writerow([category, count, collection_name])

                        console.print(f"📄 Statistics exported to: [bold cyan]{csv_file}[/bold cyan]")

                finally:
                    await memory_service.close()

        except Exception as e:
            console.print(f"[red]Error gathering statistics: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(run_stats())


def _display_analysis_results_table(result):
    """Display analysis results in a rich table format."""

    # Summary table
    summary_table = Table(title="Material Analysis Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Request ID", result.request_id)
    summary_table.add_row("Total Materials", str(result.successful_count + result.failed_count))
    summary_table.add_row("Successful", f"[green]{result.successful_count}[/green]")
    summary_table.add_row("Failed", f"[red]{result.failed_count}[/red]" if result.failed_count > 0 else "0")
    summary_table.add_row("Success Rate", f"{result.get_success_rate():.1f}%")
    summary_table.add_row("Processing Time", f"{result.processing_time:.2f}s")
    summary_table.add_row("Cross-References", str(result.cross_references_generated))
    summary_table.add_row("Quality Issues", str(result.quality_issues_found))

    console.print(summary_table)

    # Material details table
    if result.results:
        details_table = Table(title="Material Analysis Details")
        details_table.add_column("Material ID", style="cyan")
        details_table.add_column("Category", style="green")
        details_table.add_column("Quality Score", style="yellow")
        details_table.add_column("Cross-Refs", style="blue")
        details_table.add_column("Processing Time", style="white")

        for analysis_result in result.results[:10]:  # Show first 10
            material = analysis_result.source_classification
            quality_score = analysis_result.quality_assessment.quality_score if analysis_result.quality_assessment else 0.0
            cross_ref_count = len(analysis_result.cross_references)

            # Color code quality score
            if quality_score >= 0.8:
                quality_display = f"[green]{quality_score:.2f}[/green]"
            elif quality_score >= 0.6:
                quality_display = f"[yellow]{quality_score:.2f}[/yellow]"
            else:
                quality_display = f"[red]{quality_score:.2f}[/red]"

            details_table.add_row(
                material.id,
                material.category,
                quality_display,
                str(cross_ref_count),
                f"{analysis_result.processing_time:.2f}s"
            )

        if len(result.results) > 10:
            details_table.add_row("...", f"and {len(result.results) - 10} more", "", "", "")

        console.print(details_table)


def _display_analysis_summary(result):
    """Display analysis results in summary format."""
    console.print(f"📊 Analysis Summary for [bold cyan]{result.request_id}[/bold cyan]")
    console.print(f"✅ Processed: {result.successful_count}/{result.successful_count + result.failed_count} materials")
    console.print(f"⏱️ Time: {result.processing_time:.2f} seconds")
    console.print(f"🔗 Cross-references: {result.cross_references_generated}")
    console.print(f"⚠️ Quality issues: {result.quality_issues_found}")

    if result.failed_count > 0:
        console.print(f"❌ Failed materials: {result.failed_count}")


def _display_validation_results_table(quality_results, passed_count, failed_count, threshold):
    """Display validation results in table format."""
    # Summary
    total = passed_count + failed_count
    console.print(f"\n📊 Validation Summary (threshold: {threshold})")
    console.print(f"✅ Passed: [green]{passed_count}[/green]/{total}")
    console.print(f"❌ Failed: [red]{failed_count}[/red]/{total}")
    console.print(f"📈 Pass rate: {(passed_count/total*100):.1f}%" if total > 0 else "N/A")

    # Failed materials table
    if quality_results:
        failed_table = Table(title="Failed Quality Validation")
        failed_table.add_column("Material ID", style="cyan")
        failed_table.add_column("Score", style="red")
        failed_table.add_column("Issues", style="yellow")

        for analysis_result, qa in quality_results[:10]:  # Show first 10
            material_id = analysis_result.source_classification.id
            score = f"{qa.quality_score:.2f}"
            issues = ", ".join(qa.issues_found[:2])  # Show first 2 issues
            if len(qa.issues_found) > 2:
                issues += f", +{len(qa.issues_found) - 2} more"

            failed_table.add_row(material_id, score, issues)

        if len(quality_results) > 10:
            failed_table.add_row("...", f"and {len(quality_results) - 10} more", "")

        console.print(failed_table)


# === MEMORY MANAGEMENT COMMANDS ===

@app.command(name="memory-list")
def memory_list(
    story_id: str = typer.Option(None, "--story-id", help="Filter by story ID"),
    content_type: str = typer.Option("all", "--type", help="Filter by type: character_sheet, location, etc."),
    search: str = typer.Option("", "--search", help="Search content by keywords"),
    limit: int = typer.Option(50, "--limit", help="Maximum results to show"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json")
):
    """
    List content stored in memory/vector database.
    
    Examples:
        factory memory-list --story-id "my_serial" --type "character_sheet"
        factory memory-list --search "Kael" --format json
        factory memory-list --type "location" --limit 10
    """
    try:
        # Validation (follow existing pattern)
        if limit < 1 or limit > 200:
            console.print("❌ Limit must be between 1 and 200", style="bold red")
            raise typer.Exit(1)
        
        if output_format not in ["table", "json"]:
            console.print("❌ Output format must be: table or json", style="bold red")
            raise typer.Exit(1)
        
        # Execute (follow existing async pattern)
        asyncio.run(_run_memory_list(story_id, content_type, search, limit, output_format))
        
    except Exception as e:
        console.print(f"❌ Memory list failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="memory-remove")
def memory_remove(
    doc_id: str = typer.Argument(..., help="Document ID to remove"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
    collection: str = typer.Option("world_bible", "--collection", help="Collection to remove from")
):
    """
    Remove content from memory/vector database.
    
    Examples:
        factory memory-remove doc_abc123 --confirm
        factory memory-remove doc_abc123 --collection story_so_far
    """
    try:
        # Safety confirmation (follow existing patterns)
        if not confirm:
            if not typer.confirm(f"Remove document {doc_id} from {collection}?"):
                console.print("❌ Removal cancelled", style="bold yellow")
                return
        
        # Execute removal
        asyncio.run(_run_memory_remove(doc_id, collection))
        
    except Exception as e:
        console.print(f"❌ Memory removal failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="memory-update")
def memory_update(
    doc_id: str = typer.Argument(..., help="Document ID to update"),
    content_file: str = typer.Option(None, "--file", help="File with new content"),
    inline_content: str = typer.Option("", "--content", help="Inline content update"),
    collection: str = typer.Option("world_bible", "--collection", help="Collection to update"),
    merge_metadata: bool = typer.Option(True, "--merge-metadata", help="Preserve existing metadata")
):
    """
    Update existing content in memory/vector database.
    
    Examples:
        factory memory-update doc_abc123 --file updated_kael.txt
        factory memory-update doc_abc123 --content "Kael now has fire magic"
    """
    try:
        # Validation (follow existing patterns)
        if not content_file and not inline_content:
            console.print("❌ Must provide either --file or --content", style="bold red")
            raise typer.Exit(1)
        
        if content_file and inline_content:
            console.print("❌ Cannot use both --file and --content", style="bold red")
            raise typer.Exit(1)
        
        # Execute update
        asyncio.run(_run_memory_update(doc_id, content_file, inline_content, collection, merge_metadata))
        
    except Exception as e:
        console.print(f"❌ Memory update failed: {e}", style="bold red")
        raise typer.Exit(1)

# === PHASE 3: WEB INTERFACE COMMANDS ===

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind the web server"),
    port: int = typer.Option(8000, help="Port to bind the web server"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
    workers: int = typer.Option(1, help="Number of worker processes"),
):
    """Start the web interface for material ingestion."""
    console.print("🏭 [bold blue]Starting Narrative Factory Web Interface...[/bold blue]")
    console.print(f"📡 Server: http://{host}:{port}")
    console.print(f"📚 API Docs: http://{host}:{port}/api/docs")
    console.print(f"🔧 Admin: http://{host}:{port}/health")
    
    try:
        import uvicorn
        from src.web.app import app as web_app
        
        # Configure uvicorn
        config = {
            "app": "src.web.app:app",
            "host": host,
            "port": port,
            "log_level": "info",
        }
        
        if reload:
            config["reload"] = True
            console.print("🔄 [yellow]Auto-reload enabled (development mode)[/yellow]")
        
        if workers > 1 and not reload:
            config["workers"] = workers
            console.print(f"👥 Using {workers} worker processes")
        
        console.print("\n🚀 [bold green]Web interface starting...[/bold green]")
        console.print("   Use Ctrl+C to stop the server")
        
        uvicorn.run(**config)
        
    except ImportError:
        console.print("❌ [bold red]Error:[/bold red] uvicorn not installed")
        console.print("   Run: uv add uvicorn[standard]")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Web interface stopped[/yellow]")
    except Exception as e:
        console.print(f"❌ [bold red]Failed to start web server:[/bold red] {e}")
        raise typer.Exit(1)

@app.command() 
def web_status():
    """Check the status of web interface components."""
    console.print("🔍 [bold blue]Checking Web Interface Status...[/bold blue]\n")
    
    try:
        # Test web app imports
        try:
            from src.web.app import app as web_app
            from src.web.routes.ingestion import router
            console.print("✅ Web application: [green]Ready[/green]")
            console.print(f"   Routes: {len(web_app.routes)} endpoints configured")
        except Exception as e:
            console.print(f"❌ Web application: [red]Failed[/red] - {e}")
            return
        
        # Test dependencies
        try:
            import fastapi, uvicorn
            console.print("✅ Dependencies: [green]Available[/green]")
            console.print(f"   FastAPI: {fastapi.__version__}")
            console.print(f"   Uvicorn: {uvicorn.__version__}")
        except ImportError as e:
            console.print(f"❌ Dependencies: [red]Missing[/red] - {e}")
        
        # Test pipeline integration
        try:
            from src.ingestion.pipeline import MaterialIngestionPipeline
            pipeline = MaterialIngestionPipeline()
            console.print("✅ Pipeline integration: [green]Ready[/green]")
        except Exception as e:
            console.print(f"❌ Pipeline integration: [red]Failed[/red] - {e}")
        
        # Test static files
        from pathlib import Path
        static_dir = Path("src/web/static")
        templates_dir = Path("src/web/templates")
        
        if static_dir.exists():
            console.print("✅ Static files: [green]Available[/green]")
        else:
            console.print("⚠️ Static files: [yellow]Missing[/yellow]")
            
        if templates_dir.exists():
            console.print("✅ Templates: [green]Available[/green]")
        else:
            console.print("⚠️ Templates: [yellow]Missing[/yellow]")
        
        console.print("\n🌐 [bold green]Web interface is ready![/bold green]")
        console.print("   Run 'factory serve' to start the web server")
        
    except Exception as e:
        console.print(f"❌ [bold red]Status check failed:[/bold red] {e}")
        raise typer.Exit(1)


# === MEMORY MANAGEMENT IMPLEMENTATION FUNCTIONS ===

async def _run_memory_list(story_id, content_type, search, limit, output_format):
    """Implementation for memory-list command."""
    from datetime import datetime
    
    console.print("🔍 Searching memory database...")
    
    # Use extended QdrantService
    qdrant = QdrantService()
    
    # Build filters
    filters = {}
    if story_id:
        filters["story_id"] = story_id
    if content_type != "all":
        filters["doc_type"] = content_type
    
    # Search using new method
    if filters:
        results = await qdrant.search_with_filters(filters, "world_bible", limit)
    elif search:
        # Use existing search method for text search
        results = await qdrant.search_by_content(search, "world_bible", limit)
        # Convert to consistent format
        results = [
            {
                "doc_id": result.get("doc_id", result.get("id", "unknown")),
                "content": result.get("content", ""),
                "doc_type": result.get("doc_type", "unknown"),
                "story_id": result.get("story_id", None),
                "metadata": result
            }
            for result in results
        ]
    else:
        # Get all documents (use filter with no conditions)
        results = await qdrant.search_with_filters({}, "world_bible", limit)
    
    # Display results (follow existing Rich patterns)
    if output_format == "table":
        table = Table(title=f"Memory Database Contents ({len(results)} results)")
        table.add_column("Doc ID", style="cyan", width=15)
        table.add_column("Type", style="magenta", width=15)
        table.add_column("Content Preview", style="white", width=50)
        table.add_column("Story ID", style="green", width=15)
        
        for result in results:
            doc_id = result.get("doc_id", "unknown")[:12] + "..."
            doc_type = result.get("doc_type", "unknown")
            content = result.get("content", "")[:47] + "..." if len(result.get("content", "")) > 50 else result.get("content", "")
            story = result.get("story_id") or "none"
            table.add_row(doc_id, doc_type, content, story)
        
        console.print(table)
        console.print(f"💡 Use [bold cyan]factory memory-remove <doc_id>[/bold cyan] to remove content")
    else:
        # JSON output
        from rich.syntax import Syntax
        json_output = json.dumps(results, indent=2)
        syntax = Syntax(json_output, "json", theme="monokai", line_numbers=False)
        console.print(syntax)

async def _run_memory_remove(doc_id, collection):
    """Implementation for memory-remove command."""
    console.print(f"🗑️  Removing document: [bold cyan]{doc_id}[/bold cyan] from [bold magenta]{collection}[/bold magenta]")
    
    # Use extended QdrantService
    qdrant = QdrantService()
    
    # Remove using new method
    success = await qdrant.delete_document(doc_id, collection)
    
    if success:
        console.print("✅ Document removed successfully", style="bold green")
    else:
        console.print("❌ Document removal failed", style="bold red")
        raise typer.Exit(1)

async def _run_memory_update(doc_id, content_file, inline_content, collection, merge_metadata):
    """Implementation for memory-update command."""
    from datetime import datetime
    
    # Get content from file or inline
    if content_file:
        try:
            with open(content_file, 'r', encoding='utf-8') as f:
                new_content = f.read()
            console.print(f"📄 Read content from [bold cyan]{content_file}[/bold cyan]")
        except Exception as e:
            console.print(f"❌ Failed to read file {content_file}: {e}", style="bold red")
            raise typer.Exit(1)
    else:
        new_content = inline_content
    
    console.print(f"🔄 Updating document: [bold cyan]{doc_id}[/bold cyan] in [bold magenta]{collection}[/bold magenta]")
    
    # Use extended QdrantService
    qdrant = QdrantService()
    
    # Update using new method (preserves metadata if merge_metadata=True)
    metadata = {"updated_at": datetime.now().isoformat()} if merge_metadata else None
    success = await qdrant.update_document(doc_id, new_content, collection, metadata)
    
    if success:
        console.print("✅ Document updated successfully", style="bold green")
        console.print(f"💡 Use [bold cyan]factory memory-list --search {doc_id[:8]}[/bold cyan] to verify")
    else:
        console.print("❌ Document update failed", style="bold red")
        raise typer.Exit(1)


# === INTERACTIVE JOB REVIEW COMMANDS ===

@app.command(name="review-interactive")
def review_interactive(
    job_id: str = typer.Argument(..., help="Job ID to review interactively")
):
    """
    Interactive review of agent output with edit options.
    
    Examples:
        factory review-interactive job_abc123
    """
    try:
        # Get job details
        job = job_store.get_job(job_id)
        if not job:
            console.print(f"❌ Job {job_id} not found", style="bold red")
            raise typer.Exit(1)
        
        # Display job information
        console.print(Panel(
            f"Agent: [bold magenta]{job.agent}[/bold magenta]\n"
            f"Status: [bold yellow]{job.status}[/bold yellow]\n"
            f"Created: {job.created_at}",
            title=f"📋 Job {job_id[:8]}...",
            border_style="blue"
        ))
        
        if not job.output_payload:
            console.print("⚠️ No output available yet", style="bold yellow")
            return
        
        # Display output with syntax highlighting
        console.print("\n📄 Agent Output:")
        output_json = json.dumps(job.output_payload, indent=2)
        from rich.syntax import Syntax
        syntax = Syntax(output_json, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="Output", border_style="green"))
        
        # Interactive options
        console.print("\n🎛️  What would you like to do?")
        choices = [
            "approve: Approve and continue workflow",
            "reject: Reject with feedback", 
            "revise: Request specific revisions",
            "alternatives: Generate alternative versions",
            "exit: Exit without action"
        ]
        
        for i, choice in enumerate(choices, 1):
            console.print(f"  {i}. {choice}")
        
        from rich.prompt import Prompt
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="1")
        
        if choice == "1":
            # Approve (use existing method)
            approved_output = job_store.approve_job(job_id)
            if approved_output:
                console.print("✅ Job approved successfully", style="bold green")
            else:
                console.print("❌ Approval failed", style="bold red")
        
        elif choice == "2":
            # Reject with feedback
            feedback = Prompt.ask("Enter rejection feedback")
            result = job_store.reject_job(job_id, feedback)
            if result:
                console.print("❌ Job rejected with feedback", style="bold red")
            else:
                console.print("❌ Rejection failed", style="bold red")
        
        elif choice == "3":
            # Request revision
            _handle_revision_request(job_id, job.agent)
        
        elif choice == "4":
            # Generate alternatives
            _handle_alternatives_request(job_id)
        
        else:
            console.print("👋 Exiting without action")
        
    except Exception as e:
        console.print(f"❌ Interactive review failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def revise(
    job_id: str = typer.Argument(..., help="Job ID to request revision"),
    feedback: str = typer.Option(..., "--feedback", help="Specific revision request"),
    section: str = typer.Option("all", "--section", help="Section to revise: all, emotional_arc, key_events, etc.")
):
    """
    Request specific revisions to agent output.
    
    Examples:
        factory revise job_abc123 --feedback "Make the romance more subtle"
        factory revise job_abc123 --feedback "Add more action" --section "key_events"
        factory revise job_abc123 --feedback "Slow down pacing" --section "emotional_turning_point"
    """
    try:
        console.print(f"🔄 Requesting revision for job: [bold cyan]{job_id}[/bold cyan]")
        console.print(f"📝 Feedback: [italic]{feedback}[/italic]")
        console.print(f"🎯 Section: [bold yellow]{section}[/bold yellow]")
        
        # Request revision using extended JobStore
        revision_job_id = job_store.request_revision(job_id, feedback, section)
        
        if revision_job_id:
            console.print(f"✅ Revision requested successfully", style="bold green")
            console.print(f"🆔 New revision job: [bold cyan]{revision_job_id}[/bold cyan]")
            console.print(f"💡 Use [bold cyan]factory status[/bold cyan] to monitor revision progress")
        else:
            console.print("❌ Revision request failed", style="bold red")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"❌ Revision request failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command()
def alternatives(
    job_id: str = typer.Argument(..., help="Job ID to generate alternatives for"),
    count: int = typer.Option(3, "--count", help="Number of alternatives to generate")
):
    """
    Generate alternative versions of agent output.
    
    Examples:
        factory alternatives job_abc123
        factory alternatives job_abc123 --count 5
    """
    try:
        console.print(f"🎲 Generating {count} alternatives for job: [bold cyan]{job_id}[/bold cyan]")
        
        alternative_jobs = []
        
        # Generate multiple alternatives
        for i in range(count):
            alt_job_id = job_store.create_alternative_job(job_id)
            if alt_job_id:
                alternative_jobs.append(alt_job_id)
                console.print(f"  📋 Alternative {i+1}: [bold cyan]{alt_job_id}[/bold cyan]")
            else:
                console.print(f"  ❌ Failed to create alternative {i+1}", style="bold red")
        
        if alternative_jobs:
            console.print(f"✅ Generated {len(alternative_jobs)} alternatives", style="bold green")
            console.print(f"💡 Use [bold cyan]factory status[/bold cyan] to monitor generation progress")
            console.print(f"💡 Use [bold cyan]factory review-interactive <job_id>[/bold cyan] to compare options")
        else:
            console.print("❌ No alternatives generated", style="bold red")
            raise typer.Exit(1)
        
    except Exception as e:
        console.print(f"❌ Alternative generation failed: {e}", style="bold red")
        raise typer.Exit(1)

# === HELPER FUNCTIONS ===

def _handle_revision_request(job_id: str, agent: str):
    """Handle interactive revision request flow."""
    from rich.prompt import Prompt
    console.print(f"\n🔄 Requesting revision for {agent} output")
    
    # Agent-specific revision options
    if agent == "Director":
        sections = ["all", "key_events", "emotional_turning_point", "cliffhanger_concept", "goal"]
    elif agent == "Tactician":
        sections = ["all", "chapter_beats", "title_suggestions", "chapter_metadata"]
    elif agent == "Weaver":
        sections = ["all", "prose_style", "dialogue", "pacing", "descriptions"]
    elif agent == "Canonist":
        sections = ["all", "character_updates", "plot_updates", "tension_state"]
    else:
        sections = ["all"]
    
    console.print("🎯 Which section needs revision?")
    for i, section in enumerate(sections, 1):
        console.print(f"  {i}. {section}")
    
    section_choice = Prompt.ask("Choose section", choices=[str(i) for i in range(1, len(sections)+1)], default="1")
    selected_section = sections[int(section_choice) - 1]
    
    feedback = Prompt.ask("Enter specific revision feedback")
    
    # Request revision
    revision_job_id = job_store.request_revision(job_id, feedback, selected_section)
    
    if revision_job_id:
        console.print(f"✅ Revision requested for section: [bold yellow]{selected_section}[/bold yellow]", style="bold green")
        console.print(f"🆔 New revision job: [bold cyan]{revision_job_id}[/bold cyan]")
    else:
        console.print("❌ Revision request failed", style="bold red")

def _handle_alternatives_request(job_id: str):
    """Handle interactive alternatives generation."""
    from rich.prompt import Prompt
    console.print("\n🎲 How many alternatives would you like?")
    count = Prompt.ask("Number of alternatives", default="3")
    
    try:
        count = int(count)
        if count < 1 or count > 10:
            console.print("❌ Count must be between 1 and 10", style="bold red")
            return
        
        alternative_jobs = []
        
        with console.status(f"[bold green]Generating {count} alternatives..."):
            for i in range(count):
                alt_job_id = job_store.create_alternative_job(job_id)
                if alt_job_id:
                    alternative_jobs.append(alt_job_id)
        
        if alternative_jobs:
            console.print(f"✅ Generated {len(alternative_jobs)} alternatives:", style="bold green")
            for i, alt_id in enumerate(alternative_jobs, 1):
                console.print(f"  📋 Alternative {i}: [bold cyan]{alt_id}[/bold cyan]")
        else:
            console.print("❌ No alternatives generated", style="bold red")
            
    except ValueError:
        console.print("❌ Invalid count specified", style="bold red")


# === DYNAMIC CONTENT INJECTION COMMANDS ===

@app.command(name="inject-chat")
def inject_chat(
    story_id: str = typer.Option(None, "--story-id", help="Story context for content injection"),
    session_name: str = typer.Option("default", "--session", help="Chat session name")
):
    """
    Start conversational content injection session.
    
    Examples:
        factory inject-chat --story-id "my_serial"
        factory inject-chat --session "character_planning"
    """
    try:
        console.print("🤖 Starting conversational content injection session...")
        console.print(f"📖 Story context: {story_id or 'general'}")
        console.print(f"💬 Session: {session_name}")
        
        # Run conversational session
        asyncio.run(_run_conversational_injection(story_id, session_name))
        
    except Exception as e:
        console.print(f"❌ Conversational injection failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="add-character")
def add_character(
    name: str = typer.Argument(..., help="Character name"),
    description: str = typer.Option(..., "--description", help="Character description and background"),
    chapter: int = typer.Option(None, "--at-chapter", help="Target introduction chapter"),
    role: str = typer.Option("supporting", "--role", help="Character role: protagonist, antagonist, supporting"),
    story_id: str = typer.Option(None, "--story-id", help="Story to integrate with")
):
    """
    Add new character with AI-assisted integration analysis.
    
    Examples:
        factory add-character "Zara" --description "Former spy turned ally" --at-chapter 45
        factory add-character "Marcus" --role "antagonist" --description "Corrupt imperial commander"
        factory add-character "Elena" --description "Healer with secret knowledge" --story-id "my_serial"
    """
    try:
        console.print(f"🧙 Adding character: [bold magenta]{name}[/bold magenta]")
        console.print(f"📋 Description: [italic]{description}[/italic]")
        
        if chapter:
            console.print(f"📍 Target introduction: Chapter {chapter}")
        if story_id:
            console.print(f"📖 Story context: {story_id}")
        
        # Run integration analysis
        asyncio.run(_run_character_integration(name, description, chapter, role, story_id))
        
    except Exception as e:
        console.print(f"❌ Character addition failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="inject-context")
def inject_context(
    content: str = typer.Argument(..., help="Context content to inject"),
    context_type: str = typer.Option("general", "--type", help="Type: character, location, tech, magic, plot"),
    chapter: int = typer.Option(None, "--from-chapter", help="Chapter to introduce from"),
    story_id: str = typer.Option(None, "--story-id", help="Story to update"),
    auto_integrate: bool = typer.Option(False, "--auto", help="Auto-integrate without confirmation")
):
    """
    Inject new context with AI-assisted integration analysis.
    
    Examples:
        factory inject-context "Neural implants are common in the eastern districts" --type "tech" --from-chapter 50
        factory inject-context "The Crystal Caverns hold ancient secrets" --type "location"  
        factory inject-context "Magic corruption spreads through bloodlines" --type "magic" --story-id "my_serial"
    """
    try:
        console.print(f"💫 Injecting {context_type} context:")
        console.print(Panel(content, title="New Context", border_style="blue"))
        
        if chapter:
            console.print(f"📍 From chapter: {chapter}")
        if story_id:
            console.print(f"📖 Story context: {story_id}")
        
        # Run context integration analysis
        asyncio.run(_run_context_integration(content, context_type, chapter, story_id, auto_integrate))
        
    except Exception as e:
        console.print(f"❌ Context injection failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="story-steering")
def story_steering(
    direction: str = typer.Argument(..., help="Story direction or theme to introduce"),
    intensity: str = typer.Option("medium", "--intensity", help="Intensity: subtle, medium, major"),
    from_chapter: int = typer.Option(None, "--from-chapter", help="Chapter to begin steering"),
    story_id: str = typer.Option(None, "--story-id", help="Story to steer")
):
    """
    Guide story direction with AI analysis of narrative impact.
    
    Examples:
        factory story-steering "Add more romantic tension" --intensity "subtle"
        factory story-steering "Introduce cyberpunk elements" --intensity "major" --from-chapter 50
        factory story-steering "Increase political intrigue" --from-chapter 30
    """
    try:
        console.print(f"🎭 Steering story direction: [bold yellow]{direction}[/bold yellow]")
        console.print(f"⚡ Intensity: [bold cyan]{intensity}[/bold cyan]")
        
        if from_chapter:
            console.print(f"📍 Starting from chapter: {from_chapter}")
        
        # Run story steering analysis
        asyncio.run(_run_story_steering(direction, intensity, from_chapter, story_id))
        
    except Exception as e:
        console.print(f"❌ Story steering failed: {e}", style="bold red")
        raise typer.Exit(1)

# === IMPLEMENTATION FUNCTIONS ===

async def _run_conversational_injection(story_id: Optional[str], session_name: str):
    """Run conversational content injection session."""
    from src.chat.content_injection_chat import ContentInjectionChatInterface
    from rich.prompt import Prompt
    
    console.print("🎯 Conversational Content Injection")
    console.print("Type natural language requests like:")
    console.print("  • 'Add a mysterious character who knows about the ancient magic'")
    console.print("  • 'I need a dangerous place where characters can be trapped'")
    console.print("  • 'The story needs some advanced tech that could change everything'")
    console.print("  • Type 'quit' to exit")
    console.print()
    
    # Create chat session
    chat_interface = ContentInjectionChatInterface()
    session_id = await chat_interface.create_injection_session(story_id or "general", "cli_user")
    
    console.print(f"✅ Started session: {session_id}")
    console.print("🗣️ What content would you like to add to your story?")
    
    while True:
        # Get user input
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
            
            if user_input.lower() in ['quit', 'exit', 'done']:
                console.print("👋 Ending conversational injection session")
                break
            
            # Process request
            console.print("🤔 [italic]Analyzing request...[/italic]")
            response = await chat_interface.process_injection_request(session_id, user_input)
            
            # Display response
            console.print(f"\n[bold cyan]Director[/bold cyan]: {response}")
            
        except KeyboardInterrupt:
            console.print("\n👋 Session interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ Error processing request: {e}", style="bold red")

async def _run_character_integration(name: str, description: str, chapter: Optional[int], role: str, story_id: Optional[str]):
    """Implementation for character integration."""
    from src.services.smart_integration import SmartIntegrationService
    from rich.prompt import Confirm
    
    console.print("🔍 Analyzing character integration...")
    
    # Get AI-assisted integration analysis
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_character_integration(
        name, description, chapter, story_id
    )
    
    # Display analysis results
    console.print("\n🤖 AI Integration Analysis:")
    
    if suggestion.optimal_introduction_chapter:
        console.print(f"📍 Optimal introduction: Chapter {suggestion.optimal_introduction_chapter}")
    
    console.print(f"🎯 Integration approach: {suggestion.integration_approach}")
    
    if suggestion.relationship_impacts:
        console.print("\n👥 Relationship impacts:")
        for impact in suggestion.relationship_impacts:
            console.print(f"  • {impact}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Plot considerations:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.continuity_risks:
        console.print("\n⚠️ Continuity risks:")
        for risk in suggestion.continuity_risks:
            console.print(f"  • {risk}", style="yellow")
    
    if suggestion.suggestions:
        console.print("\n💡 AI suggestions:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    # Confirm integration
    if Confirm.ask("\n🚀 Proceed with character integration?"):
        # Create character sheet content
        character_content = f"""
Name: {name}
Role: {role}
Description: {description}
Introduction Context: {suggestion.integration_approach}
Planned Chapter: {chapter or suggestion.optimal_introduction_chapter or 'TBD'}
AI Analysis: {', '.join(suggestion.suggestions)}
"""
        
        # Execute integration using existing pipeline
        success = await integration_service.execute_integration(
            character_content,
            "character_sheet",
            story_id,
            {"character_name": name, "role": role, "integration_analysis": suggestion.suggestions}
        )
        
        if success:
            console.print("✅ Character integrated successfully!", style="bold green")
            console.print(f"💡 Use [bold cyan]factory memory-list --search \"{name}\"[/bold cyan] to verify")
        else:
            console.print("❌ Character integration failed", style="bold red")
    else:
        console.print("👋 Character integration cancelled")

async def _run_context_integration(content: str, context_type: str, chapter: Optional[int], story_id: Optional[str], auto_integrate: bool):
    """Implementation for context injection."""
    from src.services.smart_integration import SmartIntegrationService
    from rich.prompt import Confirm
    
    console.print("🔍 Analyzing context integration...")
    
    # Get AI analysis
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_context_integration(
        content, context_type, chapter, story_id
    )
    
    # Display analysis
    console.print(f"\n🤖 AI Analysis for {context_type} integration:")
    console.print(f"🎯 Approach: {suggestion.integration_approach}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Plot impact:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.continuity_risks:
        console.print("\n⚠️ Continuity considerations:")
        for risk in suggestion.continuity_risks:
            console.print(f"  • {risk}", style="yellow")
    
    if suggestion.suggestions:
        console.print("\n💡 AI recommendations:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    # Confirm integration
    proceed = auto_integrate or Confirm.ask("\n🚀 Proceed with context integration?")
    
    if proceed:
        # Format content with metadata
        formatted_content = f"""
Type: {context_type}
Content: {content}
Introduction: Chapter {chapter or 'TBD'}
Integration Notes: {suggestion.integration_approach}
AI Recommendations: {', '.join(suggestion.suggestions)}
"""
        
        # Execute integration
        success = await integration_service.execute_integration(
            formatted_content,
            context_type,
            story_id,
            {"context_type": context_type, "introduction_chapter": chapter}
        )
        
        if success:
            console.print("✅ Context integrated successfully!", style="bold green")
            console.print(f"💡 Use [bold cyan]factory memory-list --type \"{context_type}\"[/bold cyan] to verify")
        else:
            console.print("❌ Context integration failed", style="bold red")
    else:
        console.print("👋 Context integration cancelled")

async def _run_story_steering(direction: str, intensity: str, from_chapter: Optional[int], story_id: Optional[str]):
    """Implementation for story steering."""
    from src.services.smart_integration import SmartIntegrationService
    
    console.print("🔍 Analyzing story steering impact...")
    
    # Analyze steering direction as context injection
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_context_integration(
        f"Story direction: {direction} (intensity: {intensity})",
        "plot_direction",
        from_chapter,
        story_id
    )
    
    # Display steering analysis
    console.print(f"\n🎭 Story Steering Analysis:")
    console.print(f"🎯 Implementation approach: {suggestion.integration_approach}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Narrative impact:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.suggestions:
        console.print("\n💡 Steering recommendations:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    console.print(f"\n📝 Next steps:")
    console.print(f"  1. Use [bold cyan]factory inject-context[/bold cyan] to add specific story elements")
    console.print(f"  2. Use [bold cyan]factory add-character[/bold cyan] to introduce characters supporting this direction")
    console.print(f"  3. Monitor agent outputs for natural incorporation of steering guidance")
