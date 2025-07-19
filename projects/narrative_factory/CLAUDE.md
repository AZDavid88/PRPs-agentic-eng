# CLAUDE.md - Narrative Factory Project Guide
This file provides guidance to Claude Code when working with the Narrative Factory project.
## Project Overview
The Narrative Factory is an AI-powered storytelling engine with Human-in-the-Loop workflow. It implements a genre-agnostic narrative generation system using four synthetic agent personas connected through a Qdrant vector database with RAG (Retrieval-Augmented Generation) and late chunking techniques.
## Project Structure
narrative_factory/
 src/                    # Main source code
 agents/            # Agent personas and lifecycle management
 cli/               # Command-line interface
 memory/            # Memory and knowledge base management
 models/            # Data models and schemas
 services/          # Business logic services
 workflows/         # Workflow orchestration
 tests/                 # All test files (consolidated structure)
 PRPs/                  # Project Requirements & Patterns
 PRP_NF_PHASE_*.md  # **AUTHORITATIVE** Phase documentation
 archived/mvp/      # Archived MVP documentation
 scripts/               # Development and migration scripts
 outputs/               # Generated content and logs
 memory_bootstrap/      # Bootstrap data for knowledge base
## Authoritative Documentation
**Primary References** (in order of priority):
1. **Phase Documentation**: `PRPs/PRP_NF_PHASE_*.md` - Current implementation guidance
2. **README.md** - User-facing documentation and usage examples
3. **CLI Reference**: `CLI_REFERENCE.md` - Command documentation
4. **This file** - Development patterns and conventions
**Archived/Legacy**:
- `PRPs/archived/mvp/` - Historical MVP documentation (reference only)
- `docs/archive/` - Historical project files
## Development Patterns
### Code Organization
- **Import Structure**: Always use `from src.module import ...` patterns
- **Type Annotations**: All new code must include complete type annotations
- **Error Handling**: Use proper exception chaining with context
- **Configuration**: Use Pydantic models for all configuration
### Testing Strategy
- **Location**: All tests in `/tests/` directory
- **Naming**: `test_*.py` files with descriptive names
- **Structure**: Organized by functional areas (agents, cli, memory, workflows)
- **Fixtures**: Use shared fixtures in `tests/conftest.py`
### Code Quality Standards
- **New Code**: Must pass all linting and type checking
- **Legacy Code**: Existing patterns may not meet current standards
- **Incremental Improvement**: Use gradual enhancement rather than large refactors
## Validation Commands
### Quick Validation
```bash
# Test core functionality
uv run factory --help
# Run specific test suite
uv run pytest tests/test_agents.py -v
# Check types on specific files
uv run mypy src/config.py
### Comprehensive Validation
```bash
# Run all validation scripts
./validate_phase4.sh
./validate_phase3.sh
./validate_tool_standards.sh
# Full test suite
uv run pytest tests/ -v
# Complete type checking
uv run mypy src/
# Code quality check
uv run ruff check src/
### Development Workflow
```bash
# Setup development environment
./scripts/dev_setup.sh
# Run validation before commits
./validate_tool_standards.sh && uv run pytest tests/ -v
## Architecture Overview
### Core Components
1. **Agent System** (`src/agents/`):
   - Four agent personas: Director, Tactician, Weaver, Canonist
   - Lifecycle management with state tracking
   - Performance monitoring and health checks
2. **Memory System** (`src/memory/`):
   - Qdrant vector database integration
   - RAG with late chunking for context preservation
   - Two-tier retrieval (spotlight + ambient echo)
3. **CLI Interface** (`src/cli/`):
   - Typer-based command structure
   - Human-in-the-Loop workflow management
   - Enhanced generation with catalyst injection
4. **Workflow Engine** (`src/workflows/`):
   - Prefect-based orchestration
   - Job state management
   - Approval/rejection workflows

### Technical Deep Dive: RAG & Embedding Architecture

#### RAG (Retrieval-Augmented Generation) Implementation
**What RAG Solves**: Traditional LLMs are limited to their training data and can hallucinate. RAG retrieves relevant information from your knowledge base and feeds it to the LLM for more accurate, context-aware responses.

**The RAG Pipeline**:
1. **Document Ingestion**: Convert documents into searchable vector embeddings
2. **Query Processing**: Convert user queries into vector representations
3. **Similarity Search**: Find most relevant document chunks via vector similarity
4. **Context Injection**: Feed retrieved chunks to LLM alongside the query
5. **Response Generation**: LLM generates response based on both query and context

**Code Pattern**:
```python
# Standard RAG implementation
from FlagEmbedding import FlagModel

# Initialize embedding model
model = FlagModel('BAAI/bge-base-en-v1.5',
                  query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
                  use_fp16=True)

# Generate embeddings for corpus and query
corpus_embeddings = model.encode(corpus)
query_embedding = model.encode(query)

# Compute similarity and retrieve top results
scores = query_embedding @ corpus_embeddings.T
top_indices = scores.argsort()[-k:][::-1]
relevant_chunks = [corpus[i] for i in top_indices]
```

#### Late Chunking vs Standard Chunking
**The Lost Context Problem**: Standard RAG chunks documents first, then embeds each chunk independently. This loses contextual relationships between chunks.

**Standard Chunking Issues**:
```
Document: "Berlin is the capital of Germany. Its population is 3.7 million. The city is one of Germany's states."
Chunks: ["Berlin is the capital of Germany.", "Its population is 3.7 million.", "The city is one of Germany's states."]
```
- Only first chunk mentions "Berlin"
- "Its" and "The city" lose reference to Berlin
- Embeddings are contextually incomplete

**Late Chunking Solution**:
1. **Embed First**: Send entire document to long-context embedding model
2. **Chunk Second**: Apply chunking strategy to get segments  
3. **Extract Vectors**: Map chunk boundaries to corresponding token vectors
4. **Pool Vectors**: Average token vectors within each chunk

**Why It Works**: All token embeddings are created with full document context, preserving relationships even after chunking.

**Performance Impact**: 
- 35% reduction in retrieval failure rates
- 67% improvement when combined with reranking
- Requires long-context embedding models (8K+ tokens)

#### Jina v4 Embedding Selection Rationale
**Why Jina v4 Over Alternatives**:
- **Long Context Window**: 8,192 tokens (vs 512 for older models)
- **Late Chunking Support**: Native API flag for late chunking
- **Cost Efficiency**: Optimized pricing for bulk operations
- **Retrieval Optimization**: Specialized for search/retrieval tasks

**Implementation**:
```python
# Jina v4 with late chunking
response = requests.post(
    'https://api.jina.ai/v1/embeddings',
    headers={'Authorization': f'Bearer {api_key}'},
    json={
        'model': 'jina-embeddings-v4',
        'input': chunks,  # Multiple chunks in single request
        'late_chunking': True,  # Enable context preservation
        'dimensions': 1024
    }
)
```

#### Recursive Text Splitting Algorithm
**The Challenge**: Need to split documents while preserving semantic boundaries and maintaining consistent chunk sizes.

**Algorithm Steps**:
1. **Primary Split**: Split on paragraph boundaries (`\n\n`)
2. **Secondary Split**: If chunk too large, split on sentence boundaries
3. **Tertiary Split**: If still too large, split on word boundaries
4. **Overlap Strategy**: Add sliding window overlap between chunks
5. **Size Validation**: Ensure chunks fit within model context limits

**Implementation Pattern**:
```python
def recursive_split(text, max_length=1000, overlap=200):
    separators = ["\n\n", "\n", ".", " "]
    
    def split_text(text, separators, max_length):
        if len(text) <= max_length:
            return [text]
        
        for separator in separators:
            if separator in text:
                parts = text.split(separator)
                chunks = []
                current_chunk = ""
                
                for part in parts:
                    if len(current_chunk + separator + part) <= max_length:
                        current_chunk += (separator if current_chunk else "") + part
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part
                
                if current_chunk:
                    chunks.append(current_chunk)
                    
                return chunks
        
        # Fallback: character-level splitting
        return [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    return split_text(text, separators, max_length)
```

#### Qdrant Vector Database Operations
**Why Qdrant**: High-performance vector similarity search with advanced filtering capabilities.

**Key Operations**:
```python
# Collection creation with metadata filtering
client.create_collection(
    collection_name="narrative_memory",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE)
)

# Insert with rich metadata
points = [
    PointStruct(
        id=1,
        vector=embedding,
        payload={
            "doc_type": "character_sheet",
            "character_id": "char_selene",
            "thread_id": "thread_palace_intrigue",
            "chapter_index": 15,
            "tension_status": "escalating"
        }
    )
]
client.upsert(collection_name="narrative_memory", points=points)

# Two-tier retrieval with filtering
# Tier 1: Spotlight search (current characters)
spotlight_results = client.search(
    collection_name="narrative_memory",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(
                key="present_characters",
                match=MatchAny(any=["char_selene", "char_kain"])
            )
        ]
    ),
    limit=5
)

# Tier 2: Ambient echo search (unresolved tensions)
ambient_results = client.search(
    collection_name="narrative_memory",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="doc_type", match="tension_report"),
            FieldCondition(
                key="tension_status",
                match=MatchAny(any=["unresolved", "escalating"])
            )
        ]
    ),
    limit=5
)
```
### Key Design Patterns
- **Configuration-Driven**: All behavior configurable via Pydantic models
- **Async-First**: Asynchronous operations throughout
- **Type-Safe**: Complete type annotations for new code
- **Modular**: Clear separation of concerns
- **Testable**: Comprehensive test coverage with mocking

### Advanced Memory Architecture: Multi-Threaded Context Weaving

#### The Problem: Narrative Tunnel Vision
AI agents tend to focus only on immediately relevant information, missing broader story context and "off-screen" developments.

#### Solution: Two-Tier Context Retrieval
**Tier 1 - Spotlight Query**: Direct relevance to current scene
- Filters by `present_characters` for current point-of-view
- High relevance threshold for immediate context
- Represents what active characters *know* and *experience*

**Tier 2 - Ambient Echo Query**: Background story state
- Searches for `tension_report` documents with `unresolved` or `escalating` status
- May exclude protagonist to find "off-screen" events
- Represents the "background radiation" of story state

#### Implementation: Memory Passport System
**All memory chunks must include**:
- `doc_id`: Unique identifier
- `doc_type`: Memory category (chapter_summary, tension_report, etc.)
- `chapter_index`: Temporal positioning
- `present_characters`: Character IDs directly involved
- `thread_id`: Persistent subplot identifier (e.g., "thread_plague_cure_research")
- `tension_status`: Current state (unresolved/escalating/resolved)

**Multi-Threading Pattern**:
```python
# Thread-aware memory storage
def store_memory_chunk(content, metadata):
    # Enrich with thread tracking
    enriched_metadata = {
        **metadata,
        "thread_id": identify_narrative_threads(content),
        "present_characters": extract_character_ids(content),
        "tension_status": analyze_tension_state(content)
    }
    
    # Store with full metadata passport
    vector_db.upsert({
        "id": generate_id(),
        "vector": embed_with_context(content),
        "payload": enriched_metadata
    })
```

#### Context Weaving Protocol
1. **Director Query**: Request context for new chapter
2. **Spotlight Retrieval**: Get immediate scene-relevant memories
3. **Ambient Retrieval**: Get broader story-state context
4. **Context Synthesis**: Combine both tiers with clear demarcation
5. **Agent Processing**: Director receives complete contextual picture
6. **Memory Update**: Canonist updates thread states and adds new memories

This ensures the narrative maintains awareness of both foreground action and background developments, preventing the "protagonist tunnel vision" problem common in AI storytelling.
## Common Tasks
### Adding New Features
1. Check `PRPs/PRP_NF_PHASE_*.md` for current architecture
2. Follow existing patterns in similar modules
3. Add comprehensive type annotations
4. Include unit tests with appropriate mocking
5. Run validation commands before completion
### Debugging Issues
1. Check logs in `outputs/logs/`
2. Use `uv run factory test-connection` to verify services
3. Review validation scripts for specific component testing
4. Check test mocks in `tests/mock_reference.py`
### Extending CLI
1. Add commands in `src/cli/commands.py`
2. Follow Typer patterns used in existing commands
3. Add corresponding tests in `tests/test_cli*.py`
4. Update CLI_REFERENCE.md documentation
## Important Notes
- **Phase Documentation is Authoritative**: When in doubt, reference the Phase docs
- **Test Consolidation**: All tests are in `/tests/` (not `src/tests/`)
- **MyPy Configuration**: Uses surgical precision - doesn't ignore real issues
- **Dependency Management**: Uses `uv` for all Python operations
- **Validation**: Multiple validation scripts ensure component integrity
## Phase Implementation Status
- **Phase 1**: Foundation - Core architecture established
- **Phase 2**: Integration - Agent communication and workflow
- **Phase 3**: Continuity - Memory management and context preservation
- **Phase 4**: Toolkit - Enhanced CLI and catalyst system
Refer to individual Phase documentation for specific implementation details and current status.
