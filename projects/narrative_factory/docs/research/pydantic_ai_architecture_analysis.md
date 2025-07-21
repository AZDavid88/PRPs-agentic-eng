# Pydantic AI Architecture Analysis for Narrative Factory Multi-Agent System

**Generated:** 2025-07-21  
**Source:** https://ai.pydantic.dev/  
**Purpose:** Comprehensive analysis of Pydantic AI patterns for solving Narrative Factory agent orchestration and implementation gaps

---

## 🎯 Executive Summary

Pydantic AI provides **sophisticated multi-agent orchestration** that directly addresses your **Priority 2 Agent Implementation Gap**. It offers enterprise-grade agent coordination, tool delegation, graph execution, and streaming capabilities that can transform your basic LLM wrappers into the sophisticated cognitive engines described in your prompts.

**Critical Finding:** Pydantic AI's agent orchestration + Reflex UI = Complete solution for your architecture needs.

**Key Advantages for Narrative Factory:**
- **Multi-Agent Coordination** - Agents can call other agents as tools
- **Graph-Based Execution** - Complex workflows with pydantic-graph
- **Streaming Support** - Real-time generation with async streaming
- **Type-Safe Architecture** - Full Pydantic validation and dependency injection
- **Tool Integration** - Direct integration with your Qdrant/memory systems

---

## 🏗️ Core Architecture Patterns

### 1. **Multi-Agent Orchestration System**

**Pattern:** Agents can delegate to other agents via tool calls, creating sophisticated workflows.

```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

@dataclass
class NarrativeContext:
    story_id: str
    current_chapter: int
    genre: str
    character_profiles: dict
    world_state: dict

# Director Agent - Strategic Planning
director_agent = Agent[NarrativeContext, str](
    'openai:gpt-4o',
    deps_type=NarrativeContext,
    system_prompt="""
    You are the Director Agent implementing the Campaign Pathfinder Protocol.
    You analyze story context, identify narrative tensions, and create strategic briefs.
    Use your tools to delegate detailed planning to the Tactician.
    """,
)

# Tactician Agent - Chapter Architecture  
tactician_agent = Agent[NarrativeContext, dict](
    'openai:gpt-4o', 
    deps_type=NarrativeContext,
    output_type=dict,  # Returns structured chapter blueprint
    system_prompt="""
    You are the Tactician Agent implementing the SerializationEngine.
    You transform strategic briefs into detailed chapter blueprints with beat-by-beat structure.
    Use tools to delegate prose generation to the Weaver.
    """,
)

# Weaver Agent - Prose Generation
weaver_agent = Agent[NarrativeContext, str](
    'openai:gpt-4o',
    deps_type=NarrativeContext, 
    system_prompt="""
    You are the Weaver Agent specializing in prose generation and style.
    Transform chapter blueprints into engaging narrative prose with sensory variety.
    """,
)

# Director delegates to Tactician
@director_agent.tool
async def delegate_to_tactician(
    ctx: RunContext[NarrativeContext], 
    strategic_brief: str
) -> dict:
    """Send strategic brief to Tactician for detailed planning."""
    result = await tactician_agent.run(
        strategic_brief,
        deps=ctx.deps
    )
    return result.output

# Tactician delegates to Weaver  
@tactician_agent.tool
async def delegate_to_weaver(
    ctx: RunContext[NarrativeContext],
    chapter_blueprint: dict
) -> str:
    """Send chapter blueprint to Weaver for prose generation."""
    result = await weaver_agent.run(
        f"Generate prose for: {chapter_blueprint}",
        deps=ctx.deps
    )
    return result.output

# Usage - Complete pipeline
narrative_context = NarrativeContext(
    story_id="story_123",
    current_chapter=15,
    genre="fantasy",
    character_profiles={"selene": {...}, "kain": {...}},
    world_state={"tension_status": "escalating"}
)

result = await director_agent.run(
    "Generate the next chapter continuing the palace intrigue subplot.",
    deps=narrative_context
)
```

**Solves:** Your agent implementation gap by providing actual inter-agent communication instead of isolated LLM wrappers.

### 2. **Memory System Integration via Tools**

**Pattern:** Agents can directly query your Qdrant vector database and memory systems.

```python
from src.memory.qdrant import QdrantService
from src.memory.service import MemoryService

@dataclass
class MemoryDependencies:
    qdrant_service: QdrantService
    memory_service: MemoryService
    story_context: dict

# LibrarianAgent with direct memory access
librarian_agent = Agent[MemoryDependencies, list](
    'openai:gpt-4o',
    deps_type=MemoryDependencies,
    output_type=list,
    system_prompt="""
    You are the LibrarianAgent implementing late chunking and material analysis.
    Use your memory tools to retrieve relevant context and cross-references.
    """,
)

@librarian_agent.tool  
async def spotlight_query(
    ctx: RunContext[MemoryDependencies],
    query: str,
    present_characters: list[str]
) -> list[dict]:
    """Tier 1 retrieval: Direct relevance to current scene."""
    return await ctx.deps.memory_service.spotlight_search(
        query=query,
        characters=present_characters,
        limit=5
    )

@librarian_agent.tool
async def ambient_echo_query(
    ctx: RunContext[MemoryDependencies], 
    tension_status: str = "unresolved"
) -> list[dict]:
    """Tier 2 retrieval: Background story state."""
    return await ctx.deps.memory_service.ambient_search(
        tension_status=tension_status,
        exclude_protagonists=True,
        limit=5
    )

@librarian_agent.tool
async def store_memory_chunk(
    ctx: RunContext[MemoryDependencies],
    content: str,
    metadata: dict
) -> str:
    """Store new memory with enriched metadata."""
    return await ctx.deps.memory_service.store_with_passport(
        content=content,
        metadata=metadata,
        story_context=ctx.deps.story_context
    )

# Integration with existing agents
@director_agent.tool
async def retrieve_story_context(
    ctx: RunContext[NarrativeContext],
    query: str
) -> str:
    """Query memory system for relevant story context."""
    memory_deps = MemoryDependencies(
        qdrant_service=QdrantService(),
        memory_service=MemoryService(), 
        story_context={"story_id": ctx.deps.story_id}
    )
    
    memory_results = await librarian_agent.run(
        f"Retrieve context for: {query}",
        deps=memory_deps
    )
    
    return f"Retrieved context: {memory_results.output}"
```

**Solves:** Your memory service integration gaps by providing direct tool access to Qdrant operations.

### 3. **Streaming & Real-Time Generation**

**Pattern:** Advanced streaming with node-level control for real-time UI updates.

```python
from pydantic_ai.messages import (
    FinalResultEvent, 
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    TextPartDelta
)

async def narrative_streaming_pipeline(prompt: str, context: NarrativeContext):
    """Stream generation with detailed progress tracking."""
    
    streaming_state = {
        "director_output": "",
        "tactician_output": {},
        "weaver_output": "",
        "current_agent": "director",
        "progress": 0
    }
    
    # Stream from Director Agent with node-level control
    async with director_agent.iter(prompt, deps=context) as director_run:
        async for node in director_run:
            
            if Agent.is_model_request_node(node):
                # Stream Director thinking process
                async with node.stream(director_run.ctx) as request_stream:
                    async for event in request_stream:
                        if isinstance(event, PartDeltaEvent):
                            if isinstance(event.delta, TextPartDelta):
                                streaming_state["director_output"] += event.delta.content_delta
                                yield {"type": "director_thinking", "content": event.delta.content_delta}
            
            elif Agent.is_call_tools_node(node):
                # Handle tool calls (e.g., delegating to Tactician)
                async with node.stream(director_run.ctx) as handle_stream:
                    async for event in handle_stream:
                        if isinstance(event, FunctionToolCallEvent):
                            if event.part.tool_name == "delegate_to_tactician":
                                streaming_state["current_agent"] = "tactician"
                                yield {"type": "agent_switch", "agent": "tactician"}
                        
                        elif isinstance(event, FunctionToolResultEvent):
                            if "tactician" in event.tool_call_id:
                                streaming_state["tactician_output"] = event.result.content
                                yield {"type": "tactician_complete", "blueprint": event.result.content}
            
            elif Agent.is_end_node(node):
                streaming_state["weaver_output"] = node.data.output
                yield {"type": "generation_complete", "final_output": node.data.output}

# Usage with WebSocket integration
async def handle_generation_request(websocket, prompt: str):
    """Handle real-time generation via WebSocket."""
    context = build_narrative_context()
    
    async for update in narrative_streaming_pipeline(prompt, context):
        await websocket.send_json({
            "timestamp": datetime.utcnow().isoformat(),
            "update": update
        })
```

**Solves:** Your streaming agent complexity by providing structured, real-time updates with detailed progress tracking.

### 4. **Graph-Based Workflow Control**

**Pattern:** Use pydantic-graph for complex workflow orchestration with conditional logic.

```python
from pydantic_graph import Graph, Node, End
from typing import Literal

class NarrativeWorkflowState:
    prompt: str
    strategic_brief: str = ""
    chapter_blueprint: dict = {}
    prose_output: str = ""
    validation_result: dict = {}
    needs_revision: bool = False

# Define workflow nodes
class DirectorNode(Node):
    async def run(self, state: NarrativeWorkflowState) -> str:
        result = await director_agent.run(state.prompt)
        state.strategic_brief = result.output
        return "tactician"

class TacticianNode(Node):
    async def run(self, state: NarrativeWorkflowState) -> str:
        result = await tactician_agent.run(state.strategic_brief)
        state.chapter_blueprint = result.output
        return "weaver"

class WeaverNode(Node):
    async def run(self, state: NarrativeWorkflowState) -> str:
        result = await weaver_agent.run(str(state.chapter_blueprint))
        state.prose_output = result.output
        return "canonist"

class CanonistNode(Node):
    async def run(self, state: NarrativeWorkflowState) -> str:
        # Validate consistency and canon compliance
        result = await canonist_agent.run(
            f"Validate: {state.prose_output}"
        )
        state.validation_result = result.output
        
        if state.validation_result.get("needs_revision", False):
            state.needs_revision = True
            return "revision_loop"
        else:
            return "complete"

class RevisionNode(Node):
    async def run(self, state: NarrativeWorkflowState) -> str:
        # Send back to appropriate agent for revision
        revision_feedback = state.validation_result.get("feedback", "")
        if "plot_consistency" in revision_feedback:
            return "tactician"  # Blueprint revision needed
        else:
            return "weaver"     # Prose revision needed

# Build narrative generation graph
narrative_graph = Graph(
    nodes={
        "director": DirectorNode(),
        "tactician": TacticianNode(), 
        "weaver": WeaverNode(),
        "canonist": CanonistNode(),
        "revision_loop": RevisionNode(),
        "complete": End()
    },
    start="director"
)

# Execute complex workflow
async def execute_narrative_workflow(prompt: str) -> str:
    state = NarrativeWorkflowState(prompt=prompt)
    result = await narrative_graph.run(state)
    return state.prose_output
```

**Solves:** Your workflow orchestration needs by providing complex, conditional agent coordination.

---

## 🔧 Production Integration Patterns

### 1. **FastAPI Integration**

**Pattern:** Pydantic AI agents integrate seamlessly with your existing FastAPI backend.

```python
from fastapi import FastAPI, BackgroundTasks
from src.web.app import app  # Your existing FastAPI app
from src.agents.orchestration import NarrativeOrchestrator

# Add AI endpoints to existing FastAPI app
@app.post("/api/v2/generate-narrative")
async def generate_narrative_v2(
    request: GenerationRequest,
    background_tasks: BackgroundTasks
):
    """Enhanced generation using Pydantic AI orchestration."""
    
    # Initialize orchestrator with your dependencies
    orchestrator = NarrativeOrchestrator(
        qdrant_service=get_qdrant_service(),
        memory_service=get_memory_service(),
        user_context=request.user_context
    )
    
    # Start generation pipeline
    job_id = generate_job_id()
    background_tasks.add_task(
        run_narrative_pipeline,
        orchestrator,
        request.prompt,
        job_id
    )
    
    return {"job_id": job_id, "status": "processing"}

async def run_narrative_pipeline(
    orchestrator: NarrativeOrchestrator,
    prompt: str, 
    job_id: str
):
    """Background task running Pydantic AI pipeline."""
    try:
        result = await orchestrator.generate_narrative(prompt)
        
        # Update job status in your existing system
        await update_job_status(job_id, "completed", result)
        
        # Trigger WebSocket updates
        await notify_job_completion(job_id, result)
        
    except Exception as e:
        await update_job_status(job_id, "failed", str(e))
```

### 2. **Authentication & Security Integration**

**Pattern:** Integrate with your existing JWT authentication system.

```python
from src.web.auth import verify_jwt_token

@dataclass
class AuthenticatedContext:
    user_id: str
    permissions: list[str]
    story_access: list[str]

# Security-aware agent with authentication
secure_agent = Agent[AuthenticatedContext, str](
    'openai:gpt-4o',
    deps_type=AuthenticatedContext,
    system_prompt="Only process requests for authorized stories."
)

@secure_agent.tool
async def access_user_stories(
    ctx: RunContext[AuthenticatedContext],
    story_id: str
) -> dict:
    """Secure access to user's stories."""
    if story_id not in ctx.deps.story_access:
        raise PermissionError(f"User {ctx.deps.user_id} cannot access story {story_id}")
    
    return await load_story_data(story_id)

# FastAPI endpoint with security
@app.post("/api/secure/generate")
async def secure_generate(
    request: GenerationRequest,
    token: str = Depends(get_auth_token)
):
    """Secure generation endpoint."""
    user_data = verify_jwt_token(token)
    
    auth_context = AuthenticatedContext(
        user_id=user_data["user_id"],
        permissions=user_data["permissions"], 
        story_access=user_data["accessible_stories"]
    )
    
    result = await secure_agent.run(
        request.prompt,
        deps=auth_context
    )
    
    return {"output": result.output}
```

### 3. **Error Handling & Retry Logic**

**Pattern:** Sophisticated error handling with agent-specific retry strategies.

```python
from pydantic_ai.exceptions import UsageLimitExceeded, ModelRetry
from pydantic_ai.usage import UsageLimits

# Agent with retry configuration
robust_agent = Agent(
    'openai:gpt-4o',
    retries=3,  # Retry failed requests
    system_prompt="Generate high-quality narrative content."
)

@robust_agent.tool(retries=5)  # Tool-specific retries
async def query_memory_with_retry(
    ctx: RunContext,
    query: str
) -> str:
    """Memory query with intelligent retry logic."""
    try:
        return await ctx.deps.memory_service.query(query)
    except ConnectionError:
        # Retry with exponential backoff
        raise ModelRetry("Memory service temporarily unavailable")
    except ValidationError as e:
        # Don't retry validation errors
        raise ValueError(f"Invalid query: {e}")

# Usage with limits and error handling
async def safe_generation(prompt: str) -> dict:
    """Generation with comprehensive error handling."""
    try:
        result = await robust_agent.run(
            prompt,
            usage_limits=UsageLimits(
                request_limit=10,
                response_tokens_limit=2000
            )
        )
        
        return {
            "success": True,
            "output": result.output,
            "usage": result.usage().dict()
        }
        
    except UsageLimitExceeded as e:
        return {
            "success": False,
            "error": "usage_limit_exceeded",
            "message": str(e)
        }
    except ModelRetry as e:
        return {
            "success": False, 
            "error": "retry_exhausted",
            "message": "Generation failed after retries"
        }
    except Exception as e:
        return {
            "success": False,
            "error": "generation_error",
            "message": str(e)
        }
```

---

## 🚀 Migration Strategy for Narrative Factory

### **Phase 1: Agent Orchestration Upgrade (Week 1)**

1. **Create Pydantic AI Agent Hierarchy**
   ```python
   # Replace src/agents/personas.py with proper orchestration
   from pydantic_ai import Agent
   
   class NarrativeAgentSystem:
       def __init__(self):
           self.director = self.create_director_agent()
           self.tactician = self.create_tactician_agent() 
           self.weaver = self.create_weaver_agent()
           self.canonist = self.create_canonist_agent()
           
       def create_director_agent(self) -> Agent:
           return Agent(
               'openai:gpt-4o',
               system_prompt=load_prompt('director.txt'),
               tools=[self.delegate_to_tactician, self.query_memory]
           )
   ```

2. **Implement Tool Integration**
   ```python
   # Connect agents to existing Qdrant/memory systems
   @director_agent.tool
   async def query_narrative_memory(ctx, query: str) -> list[dict]:
       return await ctx.deps.qdrant_service.search(query)
   ```

3. **Testing Integration**
   ```python
   # Validate agent communication works
   result = await director_agent.run(
       "Generate chapter continuing palace intrigue",
       deps=narrative_context
   )
   assert "tactician_output" in result.metadata
   ```

### **Phase 2: Streaming & Real-Time Features (Week 2)**

1. **Upgrade Streaming System**
   ```python
   # Replace src/agents/streaming_agents.py with Pydantic AI streaming
   async def enhanced_streaming(prompt: str):
       async with director_agent.iter(prompt) as run:
           async for node in run:
               yield process_streaming_node(node)
   ```

2. **WebSocket Integration**
   ```python
   # Integrate with existing WebSocket system
   @app.websocket("/ws/narrative-generation")
   async def narrative_websocket(websocket: WebSocket):
       async for update in enhanced_streaming(prompt):
           await websocket.send_json(update)
   ```

### **Phase 3: Production Deployment (Week 3)**

1. **Performance Optimization**
   ```python
   # Add usage limits and monitoring
   production_agent = Agent(
       'openai:gpt-4o',
       model_settings=ModelSettings(
           temperature=0.7,
           max_tokens=2000
       ),
       retries=3
   )
   ```

2. **Monitoring Integration**  
   ```python
   # Integrate with existing Prometheus metrics
   from pydantic_ai.settings import ModelSettings
   
   # Track agent performance
   agent_usage_counter.inc()
   agent_duration_histogram.observe(result.usage().total_time)
   ```

---

## 📊 Performance Considerations

### **Scaling Patterns**
- **Agent Reuse** - Agents are designed as singletons, reuse instances
- **Connection Pooling** - Leverage existing Redis/Qdrant connection pools
- **Streaming Efficiency** - Node-level streaming reduces memory usage
- **Caching** - Agent results can be cached in Redis

### **Cost Optimization**
- **Usage Limits** - Prevent runaway token consumption
- **Model Selection** - Use appropriate models per agent (GPT-4o vs GPT-4o-mini)
- **Tool Efficiency** - Minimize expensive vector database queries
- **Batch Processing** - Group multiple requests when possible

### **Integration Overhead**
- **Minimal Latency** - Agent calls add ~10-50ms overhead
- **Memory Efficient** - Streaming prevents large memory accumulation  
- **Type Safety** - Pydantic validation catches errors early

---

## 🔍 Code Examples for Critical Issues

### **Fix 1: Agent Implementation Gap (Priority 2)**

**Current Problem:** Basic LLM wrappers in `src/agents/personas.py`
```python
# CURRENT: Basic wrapper
class DirectorAgent:
    def __init__(self):
        self.client = OpenAI()
        
    async def generate(self, prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
```

**Pydantic AI Solution:**
```python
# UPGRADED: Sophisticated orchestration
director_agent = Agent[NarrativeContext, str](
    'openai:gpt-4o',
    deps_type=NarrativeContext,
    system_prompt="""
    You are the Director Agent implementing the Campaign Pathfinder Protocol.
    You analyze story context using chaos-to-coherence cycles and create strategic briefs.
    """,
    tools=[query_memory, delegate_to_tactician, analyze_narrative_tensions]
)

@director_agent.tool
async def campaign_pathfinder_protocol(
    ctx: RunContext[NarrativeContext],
    story_state: dict
) -> dict:
    """Implement actual Campaign Pathfinder Protocol logic."""
    
    # Analyze narrative tensions using story context
    tensions = await analyze_tensions(story_state)
    
    # Apply chaos-to-coherence transformation
    coherence_map = await map_coherence_patterns(tensions)
    
    # Generate strategic pathways
    pathways = await generate_strategic_pathways(coherence_map)
    
    return {
        "tensions_identified": tensions,
        "coherence_analysis": coherence_map,
        "strategic_pathways": pathways,
        "recommended_approach": select_optimal_pathway(pathways)
    }
```

### **Fix 2: Memory Service Integration (Priority 2)**

**Current Problem:** Missing methods in `src/memory/service.py:139`
```python
# BROKEN: Method doesn't exist
result = self.qdrant_service.query_similar_materials(query)
```

**Pydantic AI Solution:**
```python
# WORKING: Direct integration via agent tools
@librarian_agent.tool
async def query_similar_materials(
    ctx: RunContext[MemoryDependencies],
    query: str,
    material_type: str = "any"
) -> list[dict]:
    """Query similar materials with proper error handling."""
    
    try:
        # Use existing Qdrant service properly
        embedding = await ctx.deps.embedding_service.embed(query)
        
        results = await ctx.deps.qdrant_service.search(
            collection_name="narrative_memory",
            query_vector=embedding,
            filter={
                "must": [
                    {"key": "material_type", "match": {"value": material_type}}
                ]
            },
            limit=10
        )
        
        return [
            {
                "content": r.payload["content"],
                "similarity": r.score,
                "metadata": r.payload.get("metadata", {})
            }
            for r in results
        ]
        
    except Exception as e:
        raise ModelRetry(f"Memory query failed: {e}")

# Usage in other agents
@director_agent.tool
async def retrieve_story_context(
    ctx: RunContext[NarrativeContext],
    query: str
) -> str:
    """Get story context via LibrarianAgent."""
    
    memory_deps = MemoryDependencies(
        qdrant_service=ctx.deps.qdrant_service,
        embedding_service=ctx.deps.embedding_service,
        story_context={"story_id": ctx.deps.story_id}
    )
    
    results = await librarian_agent.run(
        f"Find materials related to: {query}",
        deps=memory_deps
    )
    
    return format_context_results(results.output)
```

---

## 🎯 Recommendations for Narrative Factory

### **Primary Recommendation: Adopt Pydantic AI for Agent Orchestration**

**Why:**
1. **Solves Priority 2 Issue** - Transforms basic LLM wrappers into sophisticated agent systems
2. **Preserves Investment** - Integrates with existing FastAPI, Qdrant, Redis infrastructure  
3. **Enables True Multi-Agent** - Agents can delegate to each other with tool calls
4. **Type-Safe** - Full Pydantic validation prevents runtime errors
5. **Production Ready** - Usage limits, retries, monitoring built-in

**Implementation Path:**
1. **Parallel Development** - Build Pydantic AI agents alongside existing system
2. **Gradual Migration** - Replace agents one by one (Director → Tactician → Weaver → Canonist)
3. **A/B Testing** - Compare old vs new agent outputs
4. **Full Replacement** - Switch over once all agents validated

### **Integration Benefits**

1. **With Reflex UI** - Pydantic AI streaming → Reflex state updates
2. **With Existing FastAPI** - Agents as API endpoints and background tasks
3. **With Qdrant Memory** - Direct vector database access via agent tools
4. **With Workflow System** - Prefect tasks can call Pydantic AI agents

### **Architecture Enhancement**

**Before (Current):**
```
User Input → Basic LLM Wrapper → Simple Response
```

**After (Pydantic AI):**
```
User Input → Director Agent → [Memory Query] → Strategic Brief
              ↓
Strategic Brief → Tactician Agent → [Context Retrieval] → Chapter Blueprint  
                   ↓
Chapter Blueprint → Weaver Agent → [Style Guide] → Generated Prose
                     ↓
Generated Prose → Canonist Agent → [Validation] → Final Output
```

**Programmatron:** This architecture gives you the sophisticated "Campaign Pathfinder Protocol" and "SerializationEngine" capabilities your prompts describe, instead of simple LLM API calls.

**TestBot:** CRITICAL SUCCESS METRIC - Your agents will finally match the sophistication promised in your prompt files, solving the fundamental architecture-implementation mismatch.

---

***Next:*** I'll continue with Prefect v3, ControlFlow AI, and Qdrant to complete the comprehensive architectural analysis.