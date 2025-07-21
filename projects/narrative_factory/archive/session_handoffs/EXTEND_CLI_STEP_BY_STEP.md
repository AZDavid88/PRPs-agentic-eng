# Step-by-Step CLI Extension Plan

## EXTEND Phase 1.1: Memory Management Commands

### Add to `src/cli/commands.py` (Following existing patterns):

```python
# === MEMORY MANAGEMENT COMMANDS (NEW) ===

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
        asyncio.run(_run_memory_list(story_id, content_type, search, limit, output_format))
    except Exception as e:
        console.print(f"❌ Memory list failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="memory-remove")
def memory_remove(
    doc_id: str = typer.Argument(..., help="Document ID to remove"),
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt"),
    backup: bool = typer.Option(True, "--backup", help="Backup before removal")
):
    """
    Remove content from memory/vector database.
    
    Examples:
        factory memory-remove doc_abc123 --confirm
        factory memory-remove doc_abc123 --no-backup
    """
    try:
        asyncio.run(_run_memory_remove(doc_id, confirm, backup))
    except Exception as e:
        console.print(f"❌ Memory removal failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="memory-update")
def memory_update(
    doc_id: str = typer.Argument(..., help="Document ID to update"),
    content_file: str = typer.Option(None, "--file", help="File with new content"),
    inline_content: str = typer.Option("", "--content", help="Inline content update"),
    merge_mode: str = typer.Option("replace", "--merge", help="Merge mode: replace, append, or smart")
):
    """
    Update existing content in memory/vector database.
    
    Examples:
        factory memory-update doc_abc123 --file updated_kael.txt
        factory memory-update doc_abc123 --content "Kael now has fire magic"
        factory memory-update doc_abc123 --file new_traits.txt --merge smart
    """
    try:
        asyncio.run(_run_memory_update(doc_id, content_file, inline_content, merge_mode))
    except Exception as e:
        console.print(f"❌ Memory update failed: {e}", style="bold red")
        raise typer.Exit(1)
```

### Implementation Functions (Add to same file):

```python
# === MEMORY MANAGEMENT IMPLEMENTATIONS ===

async def _run_memory_list(story_id, content_type, search, limit, output_format):
    """Implementation for memory-list command."""
    from src.memory.qdrant import QdrantService
    
    console.print("🔍 Searching memory database...")
    
    # Use existing QdrantService
    qdrant = QdrantService()
    
    # Build search filters using existing patterns
    filters = {}
    if story_id:
        filters["story_id"] = story_id
    if content_type != "all":
        filters["doc_type"] = content_type
    
    # Use existing search method
    results = await qdrant.search_by_content(
        query_text=search if search else "*",
        collection_name="world_bible",  # Use existing collection
        limit=limit
    )
    
    # Display using existing console patterns
    if output_format == "table":
        table = Table(title="Memory Database Contents")
        table.add_column("Doc ID", style="cyan")
        table.add_column("Type", style="magenta") 
        table.add_column("Content Preview", style="white")
        table.add_column("Story ID", style="green")
        
        for result in results:
            doc_id = result.get("doc_id", "unknown")[:12] + "..."
            doc_type = result.get("doc_type", "unknown")
            content = result.get("content", "")[:50] + "..."
            story = result.get("story_id", "none")
            table.add_row(doc_id, doc_type, content, story)
        
        console.print(table)
    else:
        console.print(JSON(json.dumps(results, indent=2)))

async def _run_memory_remove(doc_id, confirm, backup):
    """Implementation for memory-remove command."""
    from src.memory.qdrant import QdrantService
    
    if not confirm:
        if not typer.confirm(f"Remove document {doc_id} from memory?"):
            console.print("❌ Removal cancelled")
            return
    
    console.print(f"🗑️  Removing document: {doc_id}")
    
    # Use existing QdrantService - ADD DELETE METHOD
    qdrant = QdrantService()
    
    # This method needs to be added to QdrantService
    success = await qdrant.delete_document(doc_id, "world_bible")
    
    if success:
        console.print("✅ Document removed successfully")
    else:
        console.print("❌ Document removal failed")
        raise typer.Exit(1)

async def _run_memory_update(doc_id, content_file, inline_content, merge_mode):
    """Implementation for memory-update command."""
    # Similar pattern - extend existing QdrantService
    pass
```

## EXTEND Phase 1.2: Enhanced Job Review

### Add to existing job commands:

```python
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
        asyncio.run(_run_interactive_review(job_id))
    except Exception as e:
        console.print(f"❌ Interactive review failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="revise")
def revise_job(
    job_id: str = typer.Argument(..., help="Job ID to request revision"),
    feedback: str = typer.Option(..., "--feedback", help="Specific revision request"),
    section: str = typer.Option("all", "--section", help="Section to revise: all, emotional_arc, key_events, etc.")
):
    """
    Request specific revisions to agent output.
    
    Examples:
        factory revise job_abc123 --feedback "Make the romance more subtle"
        factory revise job_abc123 --feedback "Add more action" --section "key_events"
    """
    try:
        asyncio.run(_run_job_revision(job_id, feedback, section))
    except Exception as e:
        console.print(f"❌ Job revision failed: {e}", style="bold red")
        raise typer.Exit(1)
```

## EXTEND Phase 1.3: Smart Content Injection

### Add content injection commands:

```python
@app.command(name="add-character")
def add_character(
    name: str = typer.Argument(..., help="Character name"),
    description: str = typer.Option(..., "--description", help="Character description"),
    chapter: int = typer.Option(None, "--at-chapter", help="Introduction chapter number"),
    role: str = typer.Option("supporting", "--role", help="Character role: protagonist, antagonist, supporting"),
    relationships: str = typer.Option("", "--relationships", help="Relationships with existing characters"),
    story_id: str = typer.Option(None, "--story-id", help="Associate with story")
):
    """
    Add new character with smart integration suggestions.
    
    Examples:
        factory add-character "Zara" --description "Former spy turned ally" --at-chapter 45
        factory add-character "Marcus" --role "antagonist" --relationships "rival of Kael"
    """
    try:
        asyncio.run(_run_smart_character_addition(name, description, chapter, role, relationships, story_id))
    except Exception as e:
        console.print(f"❌ Character addition failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="inject-context")
def inject_context(
    content: str = typer.Argument(..., help="Context to inject"),
    context_type: str = typer.Option("general", "--type", help="Type: character, location, tech, magic, plot"),
    chapter: int = typer.Option(None, "--from-chapter", help="Chapter to apply from"),
    story_id: str = typer.Option(None, "--story-id", help="Story to update")
):
    """
    Inject new context with timeline management.
    
    Examples:
        factory inject-context "Neural implants are common" --type "tech" --from-chapter 50
        factory inject-context "The Crystal Caverns hold ancient magic" --type "location"
    """
    try:
        asyncio.run(_run_context_injection(content, context_type, chapter, story_id))
    except Exception as e:
        console.print(f"❌ Context injection failed: {e}", style="bold red")
        raise typer.Exit(1)
```

## What You Need to Extend in Backend

### 1. Add to QdrantService (`src/memory/qdrant.py`):

```python
async def delete_document(self, doc_id: str, collection_name: str) -> bool:
    """Delete document from Qdrant."""
    try:
        async with self.connection_pool.get_connection() as client:
            await client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(
                    points=[doc_id]
                )
            )
        logger.info(f"Document {doc_id} deleted from {collection_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return False

async def update_document(self, doc_id: str, new_content: str, collection_name: str, metadata: dict = None) -> bool:
    """Update existing document in Qdrant."""
    # Implementation similar to ingest_document but with update logic
    pass

async def search_with_filters(self, filters: dict, collection_name: str, limit: int = 50) -> list:
    """Enhanced search with metadata filters."""
    # Implementation using existing search patterns
    pass
```

### 2. Add Smart Integration Service (`src/services/smart_integration.py`):

```python
class SmartIntegrationService:
    """Provides intelligent suggestions for new content integration."""
    
    async def suggest_character_integration(self, character_name: str, description: str, target_chapter: int):
        """Use Director agent to suggest how new character fits existing story."""
        # Use existing DirectorAgent to analyze integration
        pass
    
    async def analyze_context_impact(self, new_context: str, context_type: str):
        """Use Canonist to check for conflicts with existing content."""
        # Use existing CanonistAgent to validate consistency
        pass
```

## Implementation Steps:

1. **Week 1**: Add memory management commands (extend existing CLI pattern)
2. **Week 2**: Add enhanced job review (extend existing job system)  
3. **Week 3**: Add smart content injection (use existing agent system)
4. **Week 4**: Test and refine based on usage

## Key: Build on Existing Foundation

- **Use existing QdrantService** - just add delete/update methods
- **Use existing job system** - just add revision workflows
- **Use existing agents** - leverage them for smart suggestions
- **Use existing CLI patterns** - follow same structure and console styling
- **Use existing error handling** - maintain consistency

This extends your proven architecture without rebuilding anything foundational.