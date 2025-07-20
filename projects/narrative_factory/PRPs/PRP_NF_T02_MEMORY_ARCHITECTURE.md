# PRP: Two-Tier Memory Architecture Implementation

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_PHASE_05_ADVANCED_ORCHESTRATION.md  
**Target Agent:** Claude, GPT-4

## Goal
Implement sophisticated two-tier memory architecture with Spotlight (immediate relevance) and Ambient Echo (background context) retrieval to prevent protagonist tunnel vision in narrative generation.

## Why
- **Narrative Continuity**: Maintain awareness of off-screen developments and multi-threaded stories
- **Context Richness**: Provide agents with both immediate and background narrative context
- **Performance**: Optimized queries with proper filtering and caching

## What
- Enhanced memory service with spotlight/ambient tier separation
- Context fusion engine combining both tiers intelligently  
- Memory passport system with rich metadata tracking
- Performance optimization with parallel queries and caching

## Success Criteria
- [ ] Spotlight retrieval (high relevance, active characters) functional
- [ ] Ambient Echo retrieval (background context, tensions) functional  
- [ ] Context fusion provides comprehensive narrative awareness
- [ ] Performance target: <500ms for combined retrieval
- [ ] Memory passport metadata tracking operational
- [ ] Integration with existing Qdrant service maintained

## Key Implementation Points

### Spotlight Tier Pattern:
```python
async def spotlight_retrieval(self, query_embedding, active_characters, thread_id):
    filter = Filter(must=[
        FieldCondition(key="present_characters", match=MatchAny(any=active_characters)),
        FieldCondition(key="thread_id", match=MatchValue(value=thread_id))
    ])
    return await self.client.search(
        query_vector=query_embedding,
        query_filter=filter,
        limit=5,
        score_threshold=0.7
    )
```

### Ambient Echo Pattern:
```python
async def ambient_echo_retrieval(self, query_embedding, exclude_ids):
    filter = Filter(must=[
        FieldCondition(key="tension_status", match=MatchAny(any=["unresolved", "escalating"]))
    ], must_not=[
        FieldCondition(key="id", match=MatchAny(any=exclude_ids))
    ])
    return await self.client.search(
        query_vector=query_embedding,
        query_filter=filter,
        limit=15,
        score_threshold=0.3
    )
```

## Validation Commands
```bash
# Test two-tier retrieval
uv run python -c "
import asyncio
from src.memory.enhanced_qdrant import TwoTierMemoryService
service = TwoTierMemoryService()
context = asyncio.run(service.fetch_narrative_context('Test query', ['char1']))
print('✅ Spotlight results:', len(context.spotlight_context))
print('✅ Ambient results:', len(context.ambient_context))
"
```

**Implementation Details**: See `/workspaces/PRPs-agentic-eng/projects/narrative_factory/docs/research/QDRANT_IMPLEMENTATION_GUIDE.md` for complete patterns and code examples.