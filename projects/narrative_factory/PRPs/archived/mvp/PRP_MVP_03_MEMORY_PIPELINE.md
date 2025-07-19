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

- [ ] A Qdrant client is initialized in `src/narrative-factory/memory/qdrant.py`.
- [ ] The client can connect to a local Qdrant instance.
- [ ] An `ingest-data` function is created that can take text documents, embed them, and upsert them into Qdrant collections (`world-bible`, `story_so-far`).
- [ ] The `fetch_context_for-director` function is implemented, performing the two-tiered "Spotlight" and "Ambient Echo" queries.
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

# Use Context7 for advanced Qdrant filtering
use context7 for library /qdrant/qdrant-client topic "Filter and FieldCondition patterns"

# Use Context7 for async Qdrant operations
use context7 for library /qdrant/qdrant-client topic "AsyncQdrantClient and concurrent operations"

# Use Context7 for collection management
use context7 for library /qdrant/qdrant-client topic "collection creation and vector configuration"
```

**Why Context7 Enhances This PRP:**
- **Qdrant Client**: Latest filtering syntax, collection management, and performance optimization techniques
- **FastEmbed**: Current embedding generation patterns and integration with Qdrant
- **Async Operations**: Modern patterns for async database operations and concurrent vector processing
- **Testing Patterns**: Advanced mocking strategies for vector database operations and retrieval testing
- **Advanced Filtering**: Comprehensive `Filter`, `FieldCondition`, and `Range` patterns for complex queries
- **Async Client**: `AsyncQdrantClient` patterns for non-blocking database operations and concurrent processing
- **Collection Management**: Best practices for collection creation, vector configuration, and schema management

**Critical Context7 Patterns for Memory Pipeline:**
- **Two-Tiered Filtering**: Use `Filter(must=[FieldCondition(key='present-characters', match=...)])` for Spotlight queries
- **Async Upsert Operations**: Implement `await client.upsert()` for efficient bulk data insertion
- **Collection Configuration**: Use `VectorParams(size=embedding-size, distance=Distance.COSINE)` for optimal search
- **Error Handling**: Implement proper exception handling for connection failures and timeout scenarios
- **Batch Processing**: Use `client.upload-collection()` for efficient bulk operations
- **Search Optimization**: Leverage `limit` and `offset` parameters for paginated retrieval
- **Metadata Filtering**: Combine vector similarity with metadata filters for precise context retrieval
- **Connection Management**: Use context managers for proper resource cleanup in async operations

## All Needed Context

### Documentation & References

```yaml
- doc: https://qdrant.tech/documentation/concepts/filtering/
  why: Essential for implementing the "Spotlight" and "Ambient Echo" queries, which rely heavily on metadata filtering.

- file: /workspaces/PRPs-agentic-eng/projects/narrative-factory/Narrative factory project.txt
  section: "3.4.2. Retrieval Architecture: Two-Tiered Context Retrieval"
  why: This is the primary specification for the retrieval logic that must be implemented.
```

## Implementation Blueprint

### MVP Simplified Implementation

Based on Context7 documentation patterns, implement these core components:

1. **QdrantService with Two-Tiered Retrieval**
```python
# In src/narrative-factory/memory/qdrant.py
from qdrant-client import QdrantClient
from qdrant-client.models import Filter, FieldCondition, VectorParams, Distance, PointStruct
from typing import List, Dict, Any
import os

class QdrantService:
    def __init_-(self, url: Optional[str] = None, api-key: Optional[str] = None):
        self.url = url or os.getenv("QDRANT-URL")
        self.api-key = api-key or os.getenv("QDRANT_API-KEY")
        self.client = AsyncQdrantClient(url=self.url, api-key=self.api-key)
        
    async def create-collections(self):
        """Create world-bible and story_so-far collections with Jina v4 2048-dim vectors."""
        collections = ["world-bible", "story_so-far"] 
        for collection-name in collections:
            if not await self.client.collection-exists(collection-name):
                await self.client.create-collection(
                    collection-name=collection-name,
                    vectors-config=VectorParams(size=2048, distance=Distance.COSINE)
                )
    
    async def fetch_context_for-director(
        self, 
        chapter-seed: str, 
        active-characters: List[str], 
        max_results_per-tier: int = 5
    ) -> Dict[str, List[Dict]]:
        """Two-tiered context retrieval: Spotlight + Ambient Echo"""
        
        # Generate embedding for chapter seed (simplified - use sentence-transformers locally)
        query-vector = await self._embed-text(chapter-seed)
        
        # Tier 1: Spotlight Query - filtered by present-characters
        spotlight-results = await self.client.search(
            collection-name="world-bible",
            query-vector=query-vector,
            query-filter=Filter(
                must=[FieldCondition(
                    key='present-characters',
                    match=active-characters  # Filter for active characters
                )]
            ),
            limit=max_results_per-tier
        )
        
        # Tier 2: Ambient Echo Query - tension reports with unresolved status  
        ambient-results = await self.client.search(
            collection-name="story_so-far", 
            query-vector=query-vector,
            query-filter=Filter(
                must=[
                    FieldCondition(key='doc-type', match='tension-report'),
                    FieldCondition(key='status', match=['unresolved', 'escalating'])
                ]
            ),
            limit=max_results_per-tier
        )
        
        return {
            "spotlight-context": [hit.payload for hit in spotlight-results],
            "ambient-echo": [hit.payload for hit in ambient-results]
        }
    
    async def _embed-text(self, text: str) -> List[float]:
        """Use EmbeddingService with Jina AI v4 for production embeddings"""
        from .embedding-service import EmbeddingService
        embedding-service = EmbeddingService(provider="jina")  # 2048 dimensions
        return await embedding-service.generate-embedding(text)
```

2. **Simplified Ingestion Pipeline**
```python
# In scripts/ingest.py  
import json
import asyncio
from pathlib import Path
from narrative-factory.memory.qdrant import QdrantService

async def ingest_bootstrap-data():
    """Ingest sample data from memory-bootstrap directory."""
    service = QdrantService()
    await service.create-collections()
    
    bootstrap-dir = Path("memory-bootstrap")
    
    # Process each document type
    for doc_type-dir in bootstrap-dir.iterdir():
        if doc_type-dir.is-dir():
            collection = "world-bible"  # MVP: everything goes to world-bible
            
            for json-file in doc_type-dir.glob("*.json"):
                with open(json-file) as f:
                    doc-data = json.load(f)
                
                # Generate embedding and create point
                content = json.dumps(doc-data)  # Simple content extraction
                embedding = await service._embed-text(content)
                
                point = PointStruct(
                    id=doc-data.get("id", json-file.stem),
                    vector=embedding,
                    payload={
                        **doc-data,
                        "doc-type": doc_type-dir.name.rstrip('s'),  # character-sheets -> character-sheet
                        "present-characters": doc-data.get("relationships", [])
                    }
                )
                
                await service.client.upsert(
                    collection-name=collection,
                    points=[point]
                )
                
                print(f"Ingested {json-file.name} into {collection}")

if __name_- == "__main_-":
    asyncio.run(ingest_bootstrap-data())
```

### List of tasks to be completed

1.  **CREATE** `src/narrative-factory/memory/qdrant.py` with the `QdrantService` class above.
2.  **CREATE** `scripts/ingest.py` with the bootstrap data ingestion pipeline.
3.  **IMPLEMENT** basic two-tiered retrieval using Qdrant Filter and FieldCondition patterns.
4.  **INTEGRATE** sentence-transformers for local embedding generation (no external API required for MVP).
5.  **CREATE** collection initialization method that sets up world-bible and story_so-far collections.
6.  **IMPLEMENT** the `fetch_context_for-director` method with exact signature required by agents.

### Environment Configuration for MVP

```bash
# Add to .env.template
QDRANT-URL=http://localhost:6333

# For local development, no API keys needed with sentence-transformers
# JINA_API-KEY=your_key-here  # Optional for future enhancement
# OPENAI_API-KEY=your_key-here  # Optional for future enhancement
```

### Jina AI Integration Implementation

```python
# In src/narrative-factory/memory/embedding-service.py
import os
import httpx
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel
from tenacity import retry, stop_after-attempt, wait-exponential

class JinaEmbeddingRequest(BaseModel):
    """Jina AI embedding request model."""
    model: str = "jina-embeddings-v4"
    task: str = "text-matching"
    input: List[Dict[str, str]]

class JinaEmbeddingResponse(BaseModel):
    """Jina AI embedding response model."""
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, int]

class EmbeddingService:
    """Service for generating text embeddings using various providers."""
    
    def __init_-(self, provider: str = "jina"):
        # Get your Jina AI API key for free: https://jina.ai/?sui=apikey
        self.provider = provider
        self.api-key = self._get_api-key()
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api-key}",
                "Accept": "application/json"
            }
        )
        
    def _get_api-key(self) -> str:
        """Get API key based on provider."""
        if self.provider == "jina":
            return os.getenv("JINA_API-KEY", "")
        elif self.provider == "openai":
            return os.getenv("OPENAI_API-KEY", "")
        raise ValueError(f"Unknown provider: {self.provider}")
    
    def get_embedding-dimension(self) -> int:
        """Return embedding dimension for collection configuration."""
        if self.provider == "jina":
            return 2048  # jina-embeddings-v4 full dimension
        elif self.provider == "openai":
            return 3072  # text-embedding-3-large dimension
        return 1536  # default fallback
    
    @retry(
        stop=stop_after-attempt(3),
        wait=wait-exponential(multiplier=1, min=1, max=10)
    )
    async def generate-embeddings(
        self, 
        texts: List[str], 
        task: str = "text-matching"
    ) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        # Input validation
        if not texts:
            raise ValueError("Input texts cannot be empty")
        if not all(isinstance(text, str) for text in texts):
            raise ValueError("All inputs must be strings")
        
        if self.provider == "jina":
            return await self._generate_jina-embeddings(texts, task)
        elif self.provider == "openai":
            return await self._generate_openai-embeddings(texts)
        raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _generate_jina-embeddings(
        self, 
        texts: List[str], 
        task: str = "text-matching"
    ) -> List[List[float]]:
        """Generate embeddings using Jina AI API."""
        request-data = JinaEmbeddingRequest(
            model=os.getenv("JINA-MODEL", "jina-embeddings-v4"),
            task=task,
            input=[{"text": text} for text in texts]
        )
        
        try:
            response = await self.client.post(
                "https://api.jina.ai/v1/embeddings",
                json=request-data.model-dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for-status()
            
            response-data = JinaEmbeddingResponse(**response.json())
            return [item["embedding"] for item in response-data.data]
        except httpx.HTTPError as e:
            raise RuntimeError(f"Jina API request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    async def _generate_openai-embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        # Implementation for OpenAI embeddings
        pass
    
    async def _batch-process(
        self, 
        texts: List[str], 
        batch-size: int = 100
    ) -> List[List[float]]:
        """Process texts in batches to handle rate limits."""
        all-embeddings = []
        
        for i in range(0, len(texts), batch-size):
            batch = texts[i:i + batch-size]
            batch-embeddings = await self.generate-embeddings(batch)
            all-embeddings.extend(batch-embeddings)
            
            # Rate limiting delay based on Jina AI limits (500 RPM = 8.33 requests/second)
            if i + batch-size < len(texts):
                await asyncio.sleep(0.12)  # ~8 requests/second to stay under 500 RPM
        
        return all-embeddings
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
```

### `scripts/ingest.py`

-   This script will be a comprehensive data ingestion tool.
-   **Document Discovery:**
    - Scan `/memory` directory for JSON/text files
    - Parse and validate documents against `NarrativeDocument` schema
    - Extract metadata and prepare for embedding
-   **Embedding Generation:**
    - Use `EmbeddingService` to generate embeddings for all documents
    - Handle batch processing with progress indicators
    - Implement retry logic for failed embeddings
-   **Qdrant Population:**
    - Instantiate the `QdrantService`
    - Use the `ingest-data` function to populate the database
    - Provide detailed logging and error reporting
-   **Configuration Options:**
    - Support multiple embedding providers (Jina AI, OpenAI, etc.)
    - Configurable batch sizes and retry settings
    - Dry-run mode for validation without actual ingestion

### Environment Configuration

```bash
# In .env.template
# Qdrant Cloud Configuration (Production)
QDRANT-URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API-KEY=your_qdrant_cloud_api-key

# Embedding Service Configuration
EMBEDDING-PROVIDER=jina  # Options: jina, openai, local

# Jina AI v4 Configuration (Production embeddings - 2048 dimensions)
JINA_API-KEY=your_jina_api_key-here
JINA-EMAIL=your-email@example.com  # Optional: for account identification
JINA-MODEL=jina-embeddings-v4
JINA-TASK=text-matching
JINA-DIMENSIONS=2048  # jina-embeddings-v4 output size

# OpenAI Configuration (alternative)
OPENAI_API-KEY=your-openai-key
OPENAI_EMBEDDING-MODEL=text-embedding-3-large

# Batch Processing Settings
EMBEDDING_BATCH-SIZE=100
EMBEDDING_RETRY-ATTEMPTS=3
EMBEDDING_RETRY-DELAY=1.0
```

## Validation Loop

### Level 1: Syntax & Style

```bash
# Run these FIRST - fix any errors before proceeding
uv run ruff check src/narrative-factory/memory/ --fix
uv run mypy src/narrative-factory/memory/

# Expected: No errors.
```

### Level 2: Unit Tests

```python
# In tests/test-memory.py

import pytest
from unittest.mock import MagicMock
from narrative-factory.memory.qdrant import QdrantService

@pytest.fixture
def mocked_qdrant-service():
    """Fixture to create a QdrantService with a mocked client."""
    service = QdrantService()
    service.client = MagicMock()
    return service

def test_fetch_context_for-director(mocked_qdrant-service):
    """Tests the two-tiered retrieval logic."""
    # Configure the mock to return different results for different filter conditions
    def search_side-effect(*args, **kwargs):
        # This is a simplified example. A real test would inspect kwargs['filter']
        # to return the correct spotlight or ambient results.
        if "present-characters" in str(kwargs.get("filter")):
            return [MagicMock(payload={"content": "Spotlight content"})]
        else:
            return [MagicMock(payload={"content": "Ambient content"})]

    mocked_qdrant-service.client.search.side-effect = search_side-effect

    context = mocked_qdrant-service.fetch_context_for-director("test seed", ["char-selene"])

    # Assert that the client was called twice (once for each tier)
    assert mocked_qdrant-service.client.search.call-count == 2

    # Assert that the output is structured correctly
    assert "spotlight-context" in context
    assert "ambient-echo" in context
    assert context["spotlight-context"][0]["content"] == "Spotlight content"
```

```bash
# Run and iterate until passing:
uv run pytest tests/test-memory.py -v
```
