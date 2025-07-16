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
- **Two-Tiered Filtering**: Use `Filter(must=[FieldCondition(key='present_characters', match=...)])` for Spotlight queries
- **Async Upsert Operations**: Implement `await client.upsert()` for efficient bulk data insertion
- **Collection Configuration**: Use `VectorParams(size=embedding_size, distance=Distance.COSINE)` for optimal search
- **Error Handling**: Implement proper exception handling for connection failures and timeout scenarios
- **Batch Processing**: Use `client.upload_collection()` for efficient bulk operations
- **Search Optimization**: Leverage `limit` and `offset` parameters for paginated retrieval
- **Metadata Filtering**: Combine vector similarity with metadata filters for precise context retrieval
- **Connection Management**: Use context managers for proper resource cleanup in async operations

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

### MVP Simplified Implementation

Based on Context7 documentation patterns, implement these core components:

1. **QdrantService with Two-Tiered Retrieval**
```python
# In src/narrative_factory/memory/qdrant.py
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, VectorParams, Distance, PointStruct
from typing import List, Dict, Any
import os

class QdrantService:
    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        self.url = url or os.getenv("QDRANT_URL")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.client = AsyncQdrantClient(url=self.url, api_key=self.api_key)
        
    async def create_collections(self):
        """Create world_bible and story_so_far collections with Jina v4 2048-dim vectors."""
        collections = ["world_bible", "story_so_far"] 
        for collection_name in collections:
            if not await self.client.collection_exists(collection_name):
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=2048, distance=Distance.COSINE)
                )
    
    async def fetch_context_for_director(
        self, 
        chapter_seed: str, 
        active_characters: List[str], 
        max_results_per_tier: int = 5
    ) -> Dict[str, List[Dict]]:
        """Two-tiered context retrieval: Spotlight + Ambient Echo"""
        
        # Generate embedding for chapter seed (simplified - use sentence-transformers locally)
        query_vector = await self._embed_text(chapter_seed)
        
        # Tier 1: Spotlight Query - filtered by present_characters
        spotlight_results = await self.client.search(
            collection_name="world_bible",
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(
                    key='present_characters',
                    match=active_characters  # Filter for active characters
                )]
            ),
            limit=max_results_per_tier
        )
        
        # Tier 2: Ambient Echo Query - tension reports with unresolved status  
        ambient_results = await self.client.search(
            collection_name="story_so_far", 
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key='doc_type', match='tension_report'),
                    FieldCondition(key='status', match=['unresolved', 'escalating'])
                ]
            ),
            limit=max_results_per_tier
        )
        
        return {
            "spotlight_context": [hit.payload for hit in spotlight_results],
            "ambient_echo": [hit.payload for hit in ambient_results]
        }
    
    async def _embed_text(self, text: str) -> List[float]:
        """Use EmbeddingService with Jina AI v4 for production embeddings"""
        from .embedding_service import EmbeddingService
        embedding_service = EmbeddingService(provider="jina")  # 2048 dimensions
        return await embedding_service.generate_embedding(text)
```

2. **Simplified Ingestion Pipeline**
```python
# In scripts/ingest.py  
import json
import asyncio
from pathlib import Path
from narrative_factory.memory.qdrant import QdrantService

async def ingest_bootstrap_data():
    """Ingest sample data from memory_bootstrap directory."""
    service = QdrantService()
    await service.create_collections()
    
    bootstrap_dir = Path("memory_bootstrap")
    
    # Process each document type
    for doc_type_dir in bootstrap_dir.iterdir():
        if doc_type_dir.is_dir():
            collection = "world_bible"  # MVP: everything goes to world_bible
            
            for json_file in doc_type_dir.glob("*.json"):
                with open(json_file) as f:
                    doc_data = json.load(f)
                
                # Generate embedding and create point
                content = json.dumps(doc_data)  # Simple content extraction
                embedding = await service._embed_text(content)
                
                point = PointStruct(
                    id=doc_data.get("id", json_file.stem),
                    vector=embedding,
                    payload={
                        **doc_data,
                        "doc_type": doc_type_dir.name.rstrip('s'),  # character_sheets -> character_sheet
                        "present_characters": doc_data.get("relationships", [])
                    }
                )
                
                await service.client.upsert(
                    collection_name=collection,
                    points=[point]
                )
                
                print(f"Ingested {json_file.name} into {collection}")

if __name__ == "__main__":
    asyncio.run(ingest_bootstrap_data())
```

### List of tasks to be completed

1.  **CREATE** `src/narrative_factory/memory/qdrant.py` with the `QdrantService` class above.
2.  **CREATE** `scripts/ingest.py` with the bootstrap data ingestion pipeline.
3.  **IMPLEMENT** basic two-tiered retrieval using Qdrant Filter and FieldCondition patterns.
4.  **INTEGRATE** sentence-transformers for local embedding generation (no external API required for MVP).
5.  **CREATE** collection initialization method that sets up world_bible and story_so_far collections.
6.  **IMPLEMENT** the `fetch_context_for_director` method with exact signature required by agents.

### Environment Configuration for MVP

```bash
# Add to .env.template
QDRANT_URL=http://localhost:6333

# For local development, no API keys needed with sentence-transformers
# JINA_API_KEY=your_key_here  # Optional for future enhancement
# OPENAI_API_KEY=your_key_here  # Optional for future enhancement
```

### Jina AI Integration Implementation

```python
# In src/narrative_factory/memory/embedding_service.py
import os
import httpx
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

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
    
    def __init__(self, provider: str = "jina"):
        # Get your Jina AI API key for free: https://jina.ai/?sui=apikey
        self.provider = provider
        self.api_key = self._get_api_key()
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
        )
        
    def _get_api_key(self) -> str:
        """Get API key based on provider."""
        if self.provider == "jina":
            return os.getenv("JINA_API_KEY", "")
        elif self.provider == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        raise ValueError(f"Unknown provider: {self.provider}")
    
    def get_embedding_dimension(self) -> int:
        """Return embedding dimension for collection configuration."""
        if self.provider == "jina":
            return 2048  # jina-embeddings-v4 full dimension
        elif self.provider == "openai":
            return 3072  # text-embedding-3-large dimension
        return 1536  # default fallback
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def generate_embeddings(
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
            return await self._generate_jina_embeddings(texts, task)
        elif self.provider == "openai":
            return await self._generate_openai_embeddings(texts)
        raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _generate_jina_embeddings(
        self, 
        texts: List[str], 
        task: str = "text-matching"
    ) -> List[List[float]]:
        """Generate embeddings using Jina AI API."""
        request_data = JinaEmbeddingRequest(
            model=os.getenv("JINA_MODEL", "jina-embeddings-v4"),
            task=task,
            input=[{"text": text} for text in texts]
        )
        
        try:
            response = await self.client.post(
                "https://api.jina.ai/v1/embeddings",
                json=request_data.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            response_data = JinaEmbeddingResponse(**response.json())
            return [item["embedding"] for item in response_data.data]
        except httpx.HTTPError as e:
            raise RuntimeError(f"Jina API request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Embedding generation failed: {e}")
    
    async def _generate_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        # Implementation for OpenAI embeddings
        pass
    
    async def _batch_process(
        self, 
        texts: List[str], 
        batch_size: int = 100
    ) -> List[List[float]]:
        """Process texts in batches to handle rate limits."""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self.generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)
            
            # Rate limiting delay based on Jina AI limits (500 RPM = 8.33 requests/second)
            if i + batch_size < len(texts):
                await asyncio.sleep(0.12)  # ~8 requests/second to stay under 500 RPM
        
        return all_embeddings
    
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
    - Use the `ingest_data` function to populate the database
    - Provide detailed logging and error reporting
-   **Configuration Options:**
    - Support multiple embedding providers (Jina AI, OpenAI, etc.)
    - Configurable batch sizes and retry settings
    - Dry-run mode for validation without actual ingestion

### Environment Configuration

```bash
# In .env.template
# Qdrant Cloud Configuration (Production)
QDRANT_URL=https://your-cluster-id.us-east4-0.gcp.cloud.qdrant.io:6333
QDRANT_API_KEY=your_qdrant_cloud_api_key

# Embedding Service Configuration
EMBEDDING_PROVIDER=jina  # Options: jina, openai, local

# Jina AI v4 Configuration (Production embeddings - 2048 dimensions)
JINA_API_KEY=your_jina_api_key_here
JINA_EMAIL=your_email@example.com  # Optional: for account identification
JINA_MODEL=jina-embeddings-v4
JINA_TASK=text-matching
JINA_DIMENSIONS=2048  # jina-embeddings-v4 output size

# OpenAI Configuration (alternative)
OPENAI_API_KEY=your-openai-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-large

# Batch Processing Settings
EMBEDDING_BATCH_SIZE=100
EMBEDDING_RETRY_ATTEMPTS=3
EMBEDDING_RETRY_DELAY=1.0
```

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
