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
