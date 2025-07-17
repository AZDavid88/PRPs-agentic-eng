# PRP: Phase 4 - The Conductor's Toolkit (CLI)

**PRP Version:** 1.1  
**Status:** EXTENSION_AND_ENHANCEMENT  
**Parent Epic:** The bridging plan from MVP to the v3 vision.
**Target Agent:** Gemini

**Implementation Status:** 50% COMPLETE - Functional CLI exists, needs advanced features

---

## 1. The Goal (The "What")

> A single, concise sentence starting with a verb. What is the observable outcome of this task?

Extend the existing functional CLI with advanced features including memory inspection tools, batch processing capabilities, performance monitoring, and comprehensive dry-run modes to create a production-ready toolkit.

---

## 2. The Context Payload (The "With What")

> This section contains ALL information the AI needs. No external lookups allowed.

#### Current CLI Implementation Status:
**IMPLEMENTED (50% Complete):**
- ✅ `src/cli/commands.py` - Basic Typer CLI with generate, status, review, approve, reject commands
- ✅ Rich console formatting and basic progress indicators
- ✅ Basic workflow integration with Prefect HITL system
- ✅ Simple command structure with error handling
- ✅ Basic memory service integration (ingest, test-connection)

#### Extension Tasks Needed (50% → 80%):
- **BUILD:** Advanced memory inspection and analytics tools
- **CREATE:** Batch processing capabilities for multiple story generation
- **IMPLEMENT:** Performance monitoring and optimization features
- **ADD:** Comprehensive dry-run modes and simulation capabilities
- **EXTEND:** Advanced workflow orchestration and management tools

#### Key Dependencies & Imports:
- `typer`: To define the new CLI commands and options.
- `rich`: For pretty-printing the output of the `inspect` command.

#### Required Patterns & Code Snippets:

**Enhanced Pattern for `inspect` command in `src/cli/commands/inspect.py` (Building on Existing Patterns):**
```python
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.memory.service import QdrantService
from src.utils.logging import get_logger
from src.cli.utils.formatting import format_results, create_status_panel

app = typer.Typer(name="inspect", help="Inspect knowledge base and story state")
console = Console()
logger = get_logger(__name__)

@app.command("memory")
def inspect_memory(
    query: str = typer.Argument(..., help="Entity to search for (character, location, concept)"),
    collection: str = typer.Option("world_bible", help="Qdrant collection to search"),
    limit: int = typer.Option(5, help="Maximum number of results to return"),
    similarity_threshold: float = typer.Option(0.7, help="Minimum similarity score")
):
    """Inspect memory/knowledge base for specific entities."""
    with console.status(f"[bold cyan]Searching knowledge base for '{query}'..."):
        try:
            memory_service = QdrantService()
            
            # Use existing two-tier retrieval system
            spotlight_results = memory_service.retrieve_spotlight_context(query, collection, limit)
            ambient_results = memory_service.retrieve_ambient_context(query, collection, limit)
            
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
            logger.error(f"Memory inspection failed: {e}")
            console.print(f"[red]Error inspecting memory: {e}[/red]")

@app.command("state")
def inspect_state(
    story_id: Optional[str] = typer.Option(None, help="Specific story ID to inspect"),
    show_details: bool = typer.Option(False, "--details", help="Show detailed state information")
):
    """Inspect current story state and continuity information."""
    from src.services.state_manager import StateManager
    
    with console.status("[bold cyan]Loading story state..."):
        try:
            state_manager = StateManager()
            state_summary = state_manager.get_state_summary(story_id)
            
            # Create comprehensive state display
            state_table = Table(title="Story State Summary")
            state_table.add_column("Property", style="cyan")
            state_table.add_column("Value", style="white")
            
            for key, value in state_summary.items():
                state_table.add_row(key.replace("_", " ").title(), str(value))
                
            console.print(state_table)
            
            if show_details:
                full_state = state_manager.load_latest_state(story_id)
                
                # Show active plot threads
                if full_state.active_plot_threads:
                    console.print("\n[bold yellow]Active Plot Threads:[/bold yellow]")
                    for thread in full_state.active_plot_threads:
                        console.print(Panel(
                            f"Priority: {thread.priority}/10\n{thread.description}",
                            title=f"Thread #{thread.id[:8]}",
                            border_style="blue"
                        ))
                        
                # Show recent knowledge revelations
                if full_state.protagonist_knowledge:
                    console.print("\n[bold yellow]Recent Knowledge Revelations:[/bold yellow]")
                    for revelation in full_state.protagonist_knowledge[-3:]:
                        console.print(f"• {revelation.concept} (Chapter {revelation.chapter_discovered})")
                        
        except Exception as e:
            logger.error(f"State inspection failed: {e}")
            console.print(f"[red]Error inspecting state: {e}[/red]")
```

**Enhanced Pattern for workflow command in `src/cli/commands/workflow.py` (Extending Existing):**
```python
# Enhancement to existing workflow generate command
@app.command("generate")  
def generate_with_enhancements(
    story_seed: str = typer.Argument(..., help="Initial story seed or prompt"),
    catalyst: Optional[str] = typer.Option(None, "--catalyst", "-c", help="Creative catalyst to inject into generation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Perform comprehensive dry run without LLM calls"),
    interactive: bool = typer.Option(True, "--interactive/--non-interactive", help="Enable human-in-the-loop checkpoints"),
    output_format: str = typer.Option("console", help="Output format: console, json, or stream-json"),
    story_id: Optional[str] = typer.Option(None, help="Continue existing story by ID")
):
    """Enhanced story generation with catalyst injection and dry-run capabilities."""
    
    # Build comprehensive generation parameters
    generation_params = {
        "story_seed": story_seed,
        "interactive": interactive,
        "output_format": output_format,
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
        from src.workflows.generation import narrative_generation_workflow
        
        with console.status("[bold green]Executing narrative generation workflow..."):
            result = narrative_generation_workflow.with_options(
                parameters=generation_params
            )()
            
        if result.is_completed():
            console.print("[bold green]✓[/bold green] Generation completed successfully!")
            if hasattr(result, 'result') and result.result():
                console.print(f"Chapter generated: {result.result().get('chapter_file', 'Unknown')}")
        else:
            console.print(f"[yellow]Generation status:[/yellow] {result.name}")
            
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        console.print(f"[red]Generation failed: {e}[/red]")
        raise typer.Exit(1)

@app.command("catalyst")
def inject_catalyst(
    catalyst: str = typer.Argument(..., help="Creative catalyst to inject"),
    target: str = typer.Option("next", help="Target: 'next' for next generation, or story_id"),
    priority: int = typer.Option(5, help="Priority level 1-10")
):
    """Inject a creative catalyst for upcoming generation cycles."""
    
    # Store catalyst for next generation
    from src.services.catalyst_manager import CatalystManager
    
    catalyst_manager = CatalystManager()
    catalyst_id = catalyst_manager.add_catalyst(
        description=catalyst,
        target=target,
        priority=priority
    )
    
    console.print(f"[green]✓[/green] Catalyst injected (ID: {catalyst_id[:8]})")
    console.print(f"[dim]Target: {target}, Priority: {priority}/10[/dim]")
    console.print(f"[yellow]Catalyst:[/yellow] {catalyst}")
```

---

## 3. The Implementation Blueprint (The "How")

> The detailed, step-by-step logic and structure.

#### Enhancement Steps (Building on Existing Advanced CLI):
1.  **Create Memory Inspection Commands:**
    -   Create `src/cli/commands/inspect.py` with comprehensive memory and state inspection capabilities
    -   Integrate with existing QdrantService two-tier retrieval system (Spotlight + Ambient Echo)
    -   Add rich formatted output using existing console patterns
    -   Include story state inspection using the new StateManager from Phase 3

2.  **Enhance Workflow Commands with Catalyst and Dry-Run:**
    -   Update `src/cli/commands/workflow.py` to add catalyst injection and comprehensive dry-run modes
    -   Integrate with existing workflow parameters and HITL system
    -   Add catalyst storage and management system for persistent injection
    -   Implement comprehensive dry-run that shows the full execution plan

3.  **Add Catalyst Management Service:**
    -   Create `src/services/catalyst_manager.py` for storing and managing creative catalysts
    -   Integrate with existing job store patterns for persistence
    -   Allow targeting specific stories or next generation cycles
    -   Add priority management for multiple catalysts

4.  **Enhance Workflow Integration:**
    -   Update `src/workflows/generation.py` to support catalyst parameters
    -   Add comprehensive dry-run mode that replaces LLM calls with detailed logging
    -   Integrate catalyst injection into Director agent prompt construction
    -   Maintain compatibility with existing HITL checkpoints and review system

5.  **Add CLI Command Registration:**
    -   Update `src/cli/main.py` to register new inspect commands
    -   Ensure new commands follow existing CLI patterns and conventions
    -   Add comprehensive help text and command documentation

---

## 4. The Validation Gate (The "Definition of Done")

> **This is the contract.** The task is complete ONLY when all commands in this section execute successfully without error.

#### L1: Static Analysis (Syntax, Style, Types)
```bash
# Ensure the new and modified code is clean.
ruff check src/
mypy src/ --strict
```

#### L2: Functional Correctness (Do the commands work?)

**Enhanced CLI Testing:**
```bash
# Test memory inspection capabilities
uv run python src/cli/main.py inspect memory "Elara" --limit 3
uv run python src/cli/main.py inspect memory "ancient prophecy" --collection world_bible

# Test story state inspection  
uv run python src/cli/main.py inspect state --details

# Test enhanced workflow with catalyst injection
uv run python src/cli/main.py workflow generate "A storm approaches" --catalyst "Ancient magic awakens" --dry-run

# Test catalyst management system
uv run python src/cli/main.py workflow catalyst "A mysterious stranger arrives" --priority 8

# Test comprehensive dry-run mode
uv run python src/cli/main.py workflow generate "The hero's journey begins" --dry-run --interactive=false

# Test existing workflow compatibility
uv run python src/cli/main.py workflow generate "Integration test" --dry-run
```

**Expected Output:**
1. **Memory inspection** displays rich formatted tables with knowledge base results and related context
2. **State inspection** shows comprehensive story state summary with plot threads and knowledge revelations
3. **Catalyst injection** confirms catalyst storage and shows injection in dry-run workflow plans
4. **Dry-run mode** displays detailed execution plan without making LLM calls, showing all workflow steps
5. **Existing workflow** continues to function with enhanced parameters while maintaining HITL compatibility

**Integration Validation:**
```bash
# Verify enhanced commands work with existing infrastructure
uv run pytest tests/test_cli_enhancements.py -v

# Test command help and documentation
uv run python src/cli/main.py inspect --help
uv run python src/cli/main.py workflow generate --help
```
---
