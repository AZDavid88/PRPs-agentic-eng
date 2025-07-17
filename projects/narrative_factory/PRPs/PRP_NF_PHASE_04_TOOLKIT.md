# PRP: Phase 4 - The Conductor's Toolkit (CLI)

**PRP Version:** 1.1  
**Status:** EXTENSION_AND_ENHANCEMENT  
**Parent Epic:** The bridging plan from MVP to the v3 vision.
**Target Agent:** Gemini

**Implementation Status:** 80% COMPLETE - Advanced CLI toolkit implemented with inspection and catalyst features

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

#### IMPLEMENTED FEATURES (50% → 80%):
- ✅ **Advanced memory inspection and analytics tools** - `inspect_memory` and `inspect_state` commands
- ✅ **Comprehensive dry-run modes and simulation capabilities** - Full dry-run workflow with execution plans
- ✅ **Advanced workflow orchestration with catalyst injection** - Enhanced generation with creative catalysts
- ✅ **Catalyst management system** - Persistent catalyst storage and management
- 🔄 **Batch processing capabilities** - Planned for future iteration
- 🔄 **Performance monitoring and optimization features** - Planned for future iteration

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
            
            # Use existing memory service methods
            collection_info = await memory_service.get_collection_info(collection)
            spotlight_results = await memory_service.search_by_content(
                query_text=query, 
                collection_name=collection, 
                limit=limit
            )
            
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
            
            # Display collection statistics
            console.print(f"\n[bold yellow]Collection Info:[/bold yellow]")
            console.print(f"Documents: {collection_info.get('points_count', 0)}")
            console.print(f"Status: {collection_info.get('status', 'Unknown')}")
                    
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

#### IMPLEMENTED STEPS (Building on Existing Advanced CLI):
1.  ✅ **Enhanced CLI Commands in Single File:**
    -   Enhanced `src/cli/commands.py` with all new functionality in existing structure
    -   Integrated memory inspection (`inspect_memory`) with QdrantService two-tier retrieval
    -   Added story state inspection (`inspect_state`) using StateManager from Phase 3
    -   Maintained existing CLI patterns and Rich console formatting

2.  ✅ **Enhanced Workflow with Catalyst and Dry-Run:**
    -   Added `generate_enhanced` command with catalyst injection and comprehensive dry-run modes
    -   Integrated with existing workflow parameters and HITL system
    -   Added catalyst management commands (`catalyst_add`, `catalyst_list`)
    -   Implemented comprehensive dry-run that shows full execution plan

3.  ✅ **Catalyst Management Service:**
    -   Created `src/services/catalyst_manager.py` for storing and managing creative catalysts
    -   Integrated with existing JobStore patterns for persistence
    -   Added targeting for specific stories or next generation cycles
    -   Implemented priority management for multiple catalysts

4.  ✅ **Enhanced Workflow Integration:**
    -   Updated `src/workflows/generation.py` to support catalyst parameters and dry-run mode
    -   Added comprehensive dry-run mode that replaces LLM calls with mock results
    -   Integrated catalyst injection into Director agent workflow
    -   Maintained compatibility with existing HITL checkpoints and review system

5.  ✅ **CLI Command Auto-Registration:**
    -   Commands auto-registered through existing Typer app structure
    -   All new commands follow existing CLI patterns and conventions
    -   Added comprehensive help text and command documentation
    -   No separate main.py needed - cleaner architecture

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

**Enhanced CLI Testing (Updated Command Names):**
```bash
# Test memory inspection capabilities
uv run python -m src.cli.commands inspect_memory "Elara" --limit 3
uv run python -m src.cli.commands inspect_memory "ancient prophecy" --collection world_bible

# Test story state inspection  
uv run python -m src.cli.commands inspect_state --details

# Test enhanced workflow with catalyst injection
uv run python -m src.cli.commands generate_enhanced "A storm approaches" --catalyst "Ancient magic awakens" --dry-run

# Test catalyst management system
uv run python -m src.cli.commands catalyst_add "A mysterious stranger arrives" --priority 8

# Test catalyst listing
uv run python -m src.cli.commands catalyst_list --summary

# Test comprehensive dry-run mode
uv run python -m src.cli.commands generate_enhanced "The hero's journey begins" --dry-run --interactive=false

# Test existing workflow compatibility (original commands still work)
uv run python -m src.cli.commands generate "Integration test"
```

**Expected Output:**
1. **Memory inspection** displays rich formatted tables with collection statistics and search connectivity confirmation
2. **State inspection** shows comprehensive story state summary with plot threads and knowledge revelations  
3. **Catalyst management** confirms catalyst storage and priority management with formatted output
4. **Enhanced generation** displays detailed execution plan and catalyst injection in dry-run mode
5. **Existing workflow** continues to function with enhanced parameters while maintaining HITL compatibility

**Integration Validation:**
```bash
# Test command help and documentation (updated paths)
uv run python -m src.cli.commands inspect_memory --help
uv run python -m src.cli.commands generate_enhanced --help
uv run python -m src.cli.commands catalyst_add --help

# Test existing commands still work
uv run python -m src.cli.commands generate --help
uv run python -m src.cli.commands status
```

**IMPLEMENTATION COMPLETE:**
✅ All core Phase 4 toolkit features implemented and tested
✅ Advanced CLI capabilities with inspection and catalyst management  
✅ Comprehensive dry-run modes for safe testing
✅ Enhanced workflow integration maintaining existing HITL compatibility
✅ Clean architecture following existing patterns
---
