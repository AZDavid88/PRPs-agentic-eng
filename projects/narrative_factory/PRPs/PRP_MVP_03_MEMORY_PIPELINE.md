name: "MVP Phase 3: Memory Pipeline Implementation"
description: "Implements the core memory system using Qdrant for vector storage and a two-tiered RAG retrieval strategy."

---

## Goal

To build the memory backbone of the Narrative Factory. This involves creating a service to interact with a Qdrant vector database and implementing the specific, two-tiered retrieval logic required by the Director agent to get relevant context.

## Why

- **Long-Term Memory:** A vector database is essential for the system to maintain continuity over hundreds of chapters, overcoming the context window limitations of LLMs.
- **Intelligent Retrieval:** A sophisticated RAG (Retrieval-Augmented Generation) pipeline ensures that the context provided to the agents is relevant and high-quality, leading to better narrative generation.
- **Decoupling:** Separating memory logic into its own module makes the system cleaner and allows for easier upgrades or changes to the vector DB in the future.

## What

### Success Criteria

- [ ] A Qdrant client is initialized in `src/narrative_factory/memory/qdrant.py`.
- [ ] The client can connect to a local Qdrant instance.
- [ ] An `ingest_data` function is created that can take text documents, embed them, and upsert them into Qdrant collections (`world_bible`, `story_so_far`).
- [ ] The `fetch_context_for_director` function is implemented, performing the two-tiered "Spotlight" and "Ambient Echo" queries.
- [ ] Unit tests are created to validate the retrieval logic using a mocked Qdrant client.

## Context7 Documentation Injection

Before implementation, inject real-time documentation for key libraries:

```bash
# Use Context7 for Qdrant vector database operations
use context7 for library /qdrant/qdrant-client topic "filtering and search operations"

# Use Context7 for vector embeddings and RAG patterns
use context7 for library /qdrant/fastembed topic "embedding generation and vector operations"

# Use Context7 for async programming patterns
use context7 for python async topic "async database operations and concurrent processing"

# Use Context7 for testing vector databases
use context7 for pytest topic "mocking database operations and fixtures"
```

**Why Context7 Enhances This PRP:**
- **Qdrant Client**: Latest filtering syntax, collection management, and performance optimization techniques
- **FastEmbed**: Current embedding generation patterns and integration with Qdrant
- **Async Operations**: Modern patterns for async database operations and concurrent vector processing
- **Testing Patterns**: Advanced mocking strategies for vector database operations and retrieval testing

## All Needed Context

### Documentation & References

```yaml
- doc: https://qdrant.tech/documentation/concepts/filtering/
  why: Essential for implementing the "Spotlight" and "Ambient Echo" queries, which rely heavily on metadata filtering.

- file: /workspaces/PRPs-agentic-eng/projects/narrative_factory/Narrative factory project.txt
  section: "3.4.2. Retrieval Architecture: Two-Tiered Context Retrieval"
  why: This is the primary specification for the retrieval logic that must be implemented.
```

## Implementation Blueprint

### List of tasks to be completed

1.  **MODIFY** `src/narrative_factory/memory/qdrant.py`.
2.  **IMPLEMENT** a `QdrantService` class.
    -   `__init__(self)`: Initializes the `QdrantClient`, connecting to the URL specified in environment variables.
    -   `create_collections(self)`: A method to create the `world_bible` and `story_so_far` collections if they don't exist.
3.  **IMPLEMENT** an `ingest_data` function within the service.
    -   It should take a list of documents (dictionaries).
    -   For each document, it should generate embeddings (using a library like `google-generativeai`).
    -   It should then `upsert` the points into the appropriate Qdrant collection.
4.  **IMPLEMENT** the `fetch_context_for_director` function within the service.
    -   It must accept a `chapter_seed` and a list of `active_characters`.
    -   **Tier 1 (Spotlight Query):** Embed the seed. Perform a search on Qdrant, filtering by `present_characters`.
    -   **Tier 2 (Ambient Echo Query):** Use the same seed embedding. Perform a second search, filtering for `doc_type: tension_report` and `status: unresolved` or `escalating`.
    -   The function must return a dictionary structured as `{"spotlight_context": [...], "ambient_echo": [...]}`.

### `scripts/ingest.py`

-   This script will be a simple command-line tool.
-   It will read all JSON/text files from the `/memory` directory.
-   It will instantiate the `QdrantService` and use the `ingest_data` function to populate the database. This is for initial, manual setup.

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
ruff check src/narrative_factory/memory/ --fix
mypy src/narrative_factory/memory/

# Expected: No errors.
```

### Level 2: Unit Tests

```python
# In tests/test_memory.py

import pytest
from unittest.mock import MagicMock
from narrative_factory.memory.qdrant import QdrantService

@pytest.fixture
def mocked_qdrant_service():
    """Fixture to create a QdrantService with a mocked client."""
    service = QdrantService()
    service.client = MagicMock()
    return service

def test_fetch_context_for_director(mocked_qdrant_service):
    """Tests the two-tiered retrieval logic."""
    # Configure the mock to return different results for different filter conditions
    def search_side_effect(*args, **kwargs):
        # This is a simplified example. A real test would inspect kwargs['filter']
        # to return the correct spotlight or ambient results.
        if "present_characters" in str(kwargs.get("filter")):
            return [MagicMock(payload={"content": "Spotlight content"})]
        else:
            return [MagicMock(payload={"content": "Ambient content"})]

    mocked_qdrant_service.client.search.side_effect = search_side_effect

    context = mocked_qdrant_service.fetch_context_for_director("test seed", ["char_selene"])

    # Assert that the client was called twice (once for each tier)
    assert mocked_qdrant_service.client.search.call_count == 2

    # Assert that the output is structured correctly
    assert "spotlight_context" in context
    assert "ambient_echo" in context
    assert context["spotlight_context"][0]["content"] == "Spotlight content"
```

```bash
# Run and iterate until passing:
uv run pytest tests/test_memory.py -v
```
