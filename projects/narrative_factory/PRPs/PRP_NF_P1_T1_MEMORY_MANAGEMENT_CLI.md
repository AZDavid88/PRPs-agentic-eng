# PRP: Implement Memory Management CLI Commands

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_HUMAN_CONTROL_EXTENSION_PLANNING.md  
**Target Agent:** Claude Code

---

## 1. The Goal (The "What")

Implement memory management CLI commands (`memory-list`, `memory-remove`, `memory-update`) that extend the existing CLI framework to provide human control over vector database content without rebuilding any existing infrastructure.

---

## 2. The Context Payload (The "With What")

#### Files to Create/Modify:
- **UPDATE:** `src/cli/commands.py` (extend existing command structure)
- **UPDATE:** `src/memory/qdrant.py` (add delete/update methods)

#### Key Dependencies & Imports:
```python
# Already available in existing codebase:
from src.memory.qdrant import QdrantService
from src.config import config
from src.logger import get_logger
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import typer
import asyncio
import json
```

#### Existing Pattern to Follow:
```python
# From src/cli/commands.py - EXACT pattern to extend:
@app.command(name="ingest-materials")
def ingest_materials(
    files: list[str] = typer.Argument(..., help="Material files or directories to ingest"),
    genre: str = typer.Option("unknown", "--genre", "-g", help="Primary genre context"),
    # ... other options
):
    """Docstring explaining the command."""
    try:
        # Validation
        if some_condition:
            console.print("❌ Error message", style="bold red")
            raise typer.Exit(1)
        
        # Async execution
        asyncio.run(_run_async_function(params))
    except Exception as e:
        console.print(f"❌ Operation failed: {e}", style="bold red")
        raise typer.Exit(1)

async def _run_async_function(params):
    """Implementation function."""
    # Use existing services
    service = ExistingService()
    result = await service.existing_method(params)
    
    # Display with rich formatting
    console.print("✅ Success message", style="bold green")
```

#### Existing QdrantService Methods to Extend:
```python
# From src/memory/qdrant.py - PROVEN patterns:
async def ingest_document(self, doc_id: str, content: str, collection_name: str, metadata: dict = None):
    """Existing method that works - follow this pattern"""

async def search_by_content(self, query_text: str, collection_name: str, limit: int = 20):
    """Existing search method that works - extend for filtering"""

# Use existing connection pool pattern:
async with self.connection_pool.get_connection() as client:
    # Qdrant operations here
```

#### Configuration Context:
```python
# Use existing config patterns from src/config.py:
config.qdrant.world_bible_collection  # "world_bible"
config.qdrant.story_so_far_collection  # "story_so_far"
```

---

## 3. The Implementation Blueprint (The "How")

### Step 1: Extend QdrantService with Missing Methods

Add these methods to `src/memory/qdrant.py` following existing patterns:

```python
async def delete_document(self, doc_id: str, collection_name: str) -> bool:
    """
    Delete document from Qdrant collection.
    
    Args:
        doc_id: Document ID to delete
        collection_name: Target collection
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with self.connection_pool.get_connection() as client:
            # Use qdrant_client models (already imported in existing code)
            from qdrant_client import models
            
            await client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=[doc_id])
            )
        
        logger.info(f"Document {doc_id} deleted from {collection_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return False

async def update_document(self, doc_id: str, new_content: str, collection_name: str, metadata: dict = None) -> bool:
    """
    Update existing document in Qdrant collection.
    
    Args:
        doc_id: Document ID to update
        new_content: New content for the document
        collection_name: Target collection
        metadata: Optional metadata to update
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # First delete old version
        await self.delete_document(doc_id, collection_name)
        
        # Then ingest new version (use existing method)
        await self.ingest_document(doc_id, new_content, collection_name, metadata)
        
        logger.info(f"Document {doc_id} updated in {collection_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update document {doc_id}: {e}")
        return False

async def search_with_filters(self, filters: dict, collection_name: str, limit: int = 50) -> list:
    """
    Search documents with metadata filters.
    
    Args:
        filters: Metadata filters (e.g., {"story_id": "my_serial", "doc_type": "character_sheet"})
        collection_name: Target collection
        limit: Maximum results
        
    Returns:
        list: Matching documents with metadata
    """
    try:
        async with self.connection_pool.get_connection() as client:
            from qdrant_client import models
            
            # Build filter conditions
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
            
            filter_query = models.Filter(must=conditions) if conditions else None
            
            # Search with dummy vector (we want metadata filtering)
            dummy_vector = [0.0] * 1024  # Jina v4 dimension
            
            results = await client.search(
                collection_name=collection_name,
                query_vector=dummy_vector,
                query_filter=filter_query,
                limit=limit,
                with_payload=True
            )
            
            # Extract documents with metadata
            documents = []
            for result in results:
                documents.append({
                    "doc_id": str(result.id),
                    "content": result.payload.get("content", ""),
                    "doc_type": result.payload.get("doc_type", "unknown"),
                    "story_id": result.payload.get("story_id", None),
                    "metadata": result.payload
                })
            
            logger.info(f"Found {len(documents)} documents with filters {filters}")
            return documents
            
    except Exception as e:
        logger.error(f"Search with filters failed: {e}")
        return []
```

### Step 2: Add CLI Commands to src/cli/commands.py

Add these commands following the exact existing pattern:

```python
# === MEMORY MANAGEMENT COMMANDS (ADD TO EXISTING FILE) ===

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

# === IMPLEMENTATION FUNCTIONS (ADD TO EXISTING FILE) ===

async def _run_memory_list(story_id, content_type, search, limit, output_format):
    """Implementation for memory-list command."""
    from src.memory.qdrant import QdrantService
    
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
                "doc_id": result.get("doc_id", "unknown"),
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
    from src.memory.qdrant import QdrantService
    
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
    from src.memory.qdrant import QdrantService
    
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
```

---

## 4. Validation Gate (The "Contract")

The implementation is complete when ALL of these commands pass:

### Level 1: Syntax & Import Validation
```bash
cd /workspaces/PRPs-agentic-eng/projects/narrative_factory
uv run python -c "from src.cli.commands import memory_list, memory_remove, memory_update; print('✅ Commands imported successfully')"
uv run python -c "from src.memory.qdrant import QdrantService; qs = QdrantService(); print('✅ QdrantService with new methods loads')"
```

### Level 2: CLI Command Registration  
```bash
uv run factory --help | grep -E "(memory-list|memory-remove|memory-update)"
# Must show all three commands in help output
```

### Level 3: Memory Management Operations
```bash
# Test with existing lore_examples content
uv run factory memory-list --limit 10
# Must show table output with existing content

uv run factory memory-list --format json --limit 5  
# Must show JSON output

uv run factory memory-list --type "character_sheet" --limit 5
# Must filter by document type
```

### Level 4: Integration with Existing System
```bash
# Verify existing commands still work
uv run factory status
uv run factory ingest-materials --help

# Test memory operations don't break existing functionality
uv run factory test-connection
```

### Level 5: Error Handling Validation
```bash
# Test validation
uv run factory memory-list --limit 300  # Should fail with validation error
uv run factory memory-remove nonexistent-id  # Should prompt for confirmation
uv run factory memory-update doc123  # Should fail without content
```

---

## 5. Integration Notes

#### Testing with Existing Content:
- Use `/workspaces/PRPs-agentic-eng/projects/narrative_factory/lore_examples/` for testing
- Commands should work with content previously ingested via `factory ingest-materials`
- Verify that memory operations preserve existing metadata structure

#### Backward Compatibility:
- All existing CLI commands must continue working unchanged
- QdrantService extensions must not break existing `ingest_document` or `search_by_content` methods
- Job approval workflow (`factory status`, `factory approve`, etc.) must remain functional

#### Extension Pattern:
- Follow exact patterns from existing commands (validation, async execution, error handling)
- Use existing Rich console styling and table formatting
- Maintain consistent help text and command naming conventions
- Preserve existing logging patterns and error messages

This implementation provides immediate human control over memory content while building on the proven CLI foundation.