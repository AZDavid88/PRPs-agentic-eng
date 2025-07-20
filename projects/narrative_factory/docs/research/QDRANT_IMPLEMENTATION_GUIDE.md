# Qdrant Implementation Guide for Narrative Factory

**Research Date**: 2025-07-20  
**Purpose**: Production-ready vector database patterns for narrative memory architecture

## Current Implementation Status

### **Phase 1 Completed ✅**
- Collections created with proper vector configuration
- Payload indexes implemented for character filtering
- Connection pooling and error handling established
- `list_collections()` method added to service

### **Validated Patterns**

#### **Collection Management**
```python
# List all collections
collections = await client.get_collections()
collection_names = [collection.name for collection in collections.collections]

# Check collection existence and status
exists = await client.collection_exists("narrative_memories")
info = await client.get_collection("narrative_memories")
# Status: green (ready), yellow (optimizing), grey (pending), red (error)
```

#### **Payload Index Creation**
```python
from qdrant_client.models import PayloadSchemaType

# Create keyword indexes for narrative filtering
await client.create_payload_index(
    collection_name="narrative_memories",
    field_name="present_characters",
    field_schema=PayloadSchemaType.KEYWORD
)

# Required indexes for Narrative Factory:
required_indexes = {
    "present_characters": PayloadSchemaType.KEYWORD,  # Character arrays
    "doc_type": PayloadSchemaType.KEYWORD,           # Memory types  
    "thread_id": PayloadSchemaType.KEYWORD,          # Story threads
    "tension_status": PayloadSchemaType.KEYWORD,     # Narrative tension
    "character_name": PayloadSchemaType.KEYWORD,     # Individual characters
    "status": PayloadSchemaType.KEYWORD              # General status fields
}
```

## Two-Tier Memory Architecture

### **Architecture Overview**

The Narrative Factory implements a sophisticated two-tier retrieval system to prevent "protagonist tunnel vision" and maintain narrative continuity across complex multi-threaded stories.

#### **Tier 1: Spotlight Query** (Immediate Relevance)
- **Purpose**: High-relevance context for current scene
- **Filter**: `present_characters` matching current point-of-view
- **Threshold**: High relevance (0.7-0.8) for immediate context
- **Limit**: 5-10 results for focused attention

#### **Tier 2: Ambient Echo Query** (Background Context)  
- **Purpose**: Background story state and off-screen developments
- **Filter**: `tension_status` for unresolved/escalating tensions
- **Threshold**: Lower relevance (0.3-0.5) for broader context
- **Limit**: 10-20 results for comprehensive background

### **Implementation Patterns**

#### **Spotlight Retrieval Implementation**
```python
async def spotlight_retrieval(self, query_embedding: List[float], 
                             active_characters: List[str], 
                             thread_id: str) -> List[ScoredPoint]:
    """High-priority narrative memories (Spotlight tier)"""
    spotlight_filter = Filter(
        must=[
            FieldCondition(
                key="present_characters",
                match=MatchAny(any=active_characters)
            ),
            FieldCondition(
                key="thread_id", 
                match=MatchValue(value=thread_id)
            ),
            FieldCondition(
                key="doc_type",
                match=MatchAny(any=["character_interaction", "scene_context", "dialogue"])
            )
        ]
    )
    
    return await self.client.search(
        collection_name="narrative_memories",
        query_vector=query_embedding,
        query_filter=spotlight_filter,
        limit=5,
        score_threshold=0.7,  # High relevance threshold
        with_payload=True,
        with_vector=False  # Save memory when only payload needed
    )
```

#### **Ambient Echo Retrieval Implementation**
```python
async def ambient_echo_retrieval(self, query_embedding: List[float],
                                all_characters: List[str],
                                exclude_spotlight_ids: List[int]) -> List[ScoredPoint]:
    """Background context memories (Ambient Echo tier)"""
    ambient_filter = Filter(
        must=[
            FieldCondition(
                key="doc_type",
                match=MatchAny(any=["tension_report", "world_state", "subplot_development"])
            ),
            FieldCondition(
                key="tension_status",
                match=MatchAny(any=["unresolved", "escalating", "brewing"])
            )
        ],
        should=[  # At least one should match for character relevance
            FieldCondition(
                key="present_characters",
                match=MatchAny(any=all_characters)
            )
        ],
        must_not=[  # Avoid duplicates from spotlight
            FieldCondition(
                key="id",
                match=MatchAny(any=exclude_spotlight_ids)
            )
        ]
    )
    
    return await self.client.search(
        collection_name="narrative_memories", 
        query_vector=query_embedding,
        query_filter=ambient_filter,
        limit=15,
        score_threshold=0.3,  # Lower threshold for background context
        with_payload=True,
        with_vector=False
    )
```

#### **Combined Context Fusion**
```python
async def fetch_narrative_context(self, chapter_seed: str, 
                                 active_characters: List[str],
                                 thread_id: str) -> NarrativeContext:
    """Combine spotlight and ambient echo for complete context"""
    
    # Generate query embedding from chapter seed
    query_embedding = await self._embed_text(chapter_seed)
    
    # Tier 1: Spotlight retrieval
    spotlight_memories = await self.spotlight_retrieval(
        query_embedding, active_characters, thread_id
    )
    
    # Extract IDs to avoid duplicates
    spotlight_ids = [point.id for point in spotlight_memories]
    
    # Tier 2: Ambient echo retrieval  
    ambient_memories = await self.ambient_echo_retrieval(
        query_embedding, active_characters, spotlight_ids
    )
    
    # Combine and structure for agent consumption
    return NarrativeContext(
        spotlight_context=self._format_memories(spotlight_memories),
        ambient_context=self._format_memories(ambient_memories),
        active_characters=active_characters,
        thread_id=thread_id,
        context_depth=len(spotlight_memories) + len(ambient_memories)
    )
```

### **Memory Passport System**

#### **Required Metadata for All Memory Chunks**
```python
memory_metadata = {
    # Core identification
    "doc_id": "unique_identifier",
    "doc_type": "character_interaction|scene_context|tension_report|world_state",
    
    # Temporal positioning  
    "chapter_index": 15,
    "timestamp": "2024-01-15T10:30:00Z",
    
    # Character tracking
    "present_characters": ["char_protagonist", "char_mentor"],
    "character_focus": "char_protagonist",  # Primary POV
    
    # Thread management
    "thread_id": "thread_main_story_arc",
    "subplot_ids": ["subplot_mentor_secret", "subplot_political_intrigue"],
    
    # Narrative state
    "tension_status": "escalating|unresolved|resolved",
    "emotional_tone": "tense|hopeful|mysterious",
    "narrative_weight": "major|minor|background",
    
    # Context enrichment
    "location": "throne_room_palace",
    "time_of_day": "midnight",
    "weather": "thunderstorm"
}
```

#### **Advanced Filtering Patterns**
```python
# Multi-thread narrative search
multi_thread_filter = Filter(
    must=[
        FieldCondition(
            key="thread_id",
            match=MatchAny(any=["main_story", "subplot_romance", "subplot_mystery"])
        )
    ],
    should=[
        FieldCondition(
            key="tension_status",
            match=MatchValue(value="escalating")
        ),
        FieldCondition(
            key="narrative_weight", 
            match=MatchValue(value="major")
        )
    ]
)

# Character relationship queries
relationship_filter = Filter(
    must=[
        FieldCondition(
            key="doc_type",
            match=MatchValue(value="character_interaction")
        ),
        FieldCondition(
            key="present_characters",
            match=MatchAny(any=["char_protagonist", "char_love_interest"])
        )
    ]
)
```

## Production Optimization Patterns

### **Performance Optimization**

#### **Batch Operations for Efficiency**
```python
# Batch memory storage for better performance
async def store_memory_batch(self, memories: List[MemoryChunk]) -> bool:
    points = []
    for memory in memories:
        points.append(PointStruct(
            id=memory.doc_id,
            vector=await self._embed_text(memory.content),
            payload=memory.metadata
        ))
    
    return await self.client.upsert(
        collection_name="narrative_memories",
        points=points,
        wait=False  # Don't wait for completion for better throughput
    )
```

#### **Connection Pool Management**
```python
class QdrantConnectionPool:
    def __init__(self, max_connections: int = 5):
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.max_connections = max_connections
        
    async def get_connection(self) -> AsyncQdrantClient:
        try:
            return await asyncio.wait_for(self.pool.get(), timeout=10)
        except asyncio.TimeoutError:
            if self.pool.qsize() < self.max_connections:
                return AsyncQdrantClient(url=self.url, api_key=self.api_key)
            raise
```

### **Error Handling and Resilience**

#### **Robust Search with Retry Logic**
```python
async def robust_search_with_retry(self, collection_name: str, 
                                  query_vector: List[float],
                                  query_filter: Filter = None,
                                  retries: int = 3) -> List[ScoredPoint]:
    """Search with automatic retry logic and graceful degradation"""
    for attempt in range(retries):
        try:
            return await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=10,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Search attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                # Graceful degradation: return empty results rather than crash
                logger.error(f"All search attempts failed, returning empty results")
                return []
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

#### **Health Monitoring**
```python
async def check_collection_health(self, collection_name: str) -> Dict[str, Any]:
    """Monitor collection health and performance"""
    try:
        info = await self.client.get_collection(collection_name)
        return {
            "status": info.status,  # green, yellow, grey, red
            "healthy": info.status == "green",
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "disk_usage": info.config.params.vectors.size * info.vectors_count,
            "last_checked": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "healthy": False, 
            "error": str(e),
            "last_checked": datetime.utcnow().isoformat()
        }
```

## Integration with Jina v4 Embeddings

### **Late Chunking Implementation**
```python
async def embed_with_late_chunking(self, content: str, 
                                  chunk_size: int = 1000) -> List[float]:
    """Use Jina v4 with late chunking for context preservation"""
    
    # Single request with late chunking enabled
    response = await httpx.AsyncClient().post(
        'https://api.jina.ai/v1/embeddings',
        headers={'Authorization': f'Bearer {self.jina_api_key}'},
        json={
            'model': 'jina-embeddings-v4',
            'input': [content],  # Full content for context
            'late_chunking': True,  # Enable context preservation
            'dimensions': 1024,
            'chunk_size': chunk_size
        }
    )
    
    return response.json()['data'][0]['embedding']
```

### **Recursive Text Splitting for Narrative Content**
```python
def recursive_narrative_split(self, text: str, max_length: int = 1000, 
                             overlap: int = 200) -> List[str]:
    """Split narrative content preserving scene and dialogue boundaries"""
    
    # Narrative-aware separators (order matters)
    separators = [
        "\n\n---\n\n",  # Scene breaks
        "\n\n",         # Paragraph breaks  
        "\n\"",         # Dialogue starts
        ". ",           # Sentence boundaries
        " "             # Word boundaries
    ]
    
    def split_text(text: str, separators: List[str]) -> List[str]:
        if len(text) <= max_length:
            return [text]
            
        for separator in separators:
            if separator in text:
                parts = text.split(separator)
                chunks = []
                current_chunk = ""
                
                for part in parts:
                    potential_chunk = current_chunk + (separator if current_chunk else "") + part
                    
                    if len(potential_chunk) <= max_length:
                        current_chunk = potential_chunk
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = part
                        
                if current_chunk:
                    chunks.append(current_chunk)
                    
                return chunks
        
        # Fallback: character-level splitting
        return [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    chunks = split_text(text, separators)
    
    # Add overlap for context preservation
    overlapped_chunks = []
    for i, chunk in enumerate(chunks):
        if i > 0 and len(chunks[i-1]) > overlap:
            # Add overlap from previous chunk
            overlap_text = chunks[i-1][-overlap:]
            chunk = overlap_text + " " + chunk
        overlapped_chunks.append(chunk)
    
    return overlapped_chunks
```

## Conclusion

The Qdrant implementation provides a robust foundation for the Narrative Factory's advanced memory architecture. The two-tier retrieval system (Spotlight + Ambient Echo) addresses the critical challenge of maintaining narrative continuity while preventing protagonist tunnel vision.

**Key Implementation Strengths**:
- ✅ **Production-Ready**: Proper error handling, connection pooling, health monitoring
- ✅ **Narrative-Optimized**: Two-tier retrieval prevents tunnel vision  
- ✅ **Context-Preserving**: Late chunking with Jina v4 maintains semantic relationships
- ✅ **Scalable**: Batch operations and performance optimization for large story collections
- ✅ **Observable**: Complete health monitoring and performance metrics

The architecture is ready for Phase 2 advanced memory features and multi-threaded narrative support.