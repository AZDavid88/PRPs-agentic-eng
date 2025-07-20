# PRP: Controlflow Integration for AI Agent Orchestration

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_PHASE_05_ADVANCED_ORCHESTRATION.md  
**Target Agent:** Claude, GPT-4

---

## 1. The Goal (The "What")

Implement Controlflow agent wrappers and multi-agent collaboration workflows that enhance the existing Prefect infrastructure with sophisticated AI agent orchestration capabilities.

---

## 2. The Why (The "Why")

**Business Value:**
- **Enhanced Narrative Quality**: Multi-agent collaboration produces richer, more coherent stories
- **Structured Outputs**: Type-safe agent results with Pydantic validation
- **Interactive Workflows**: Real-time human-agent collaboration capabilities  
- **Debugging Visibility**: Complete transparency into agent decision-making

**Technical Benefits:**
- **Seamless Integration**: Controlflow built on Prefect 3.0 for natural compatibility
- **Agent Tool Management**: Sophisticated tool integration for memory access and context
- **Session Management**: Agent conversation replay and debugging capabilities
- **Observable AI**: Complete visibility into multi-agent interactions

**Problems Solved:**
- **Agent Isolation**: Current agents work independently, missing collaboration opportunities
- **Limited Observability**: Difficult to debug agent decision-making processes
- **Static Workflows**: Fixed agent execution order without dynamic collaboration
- **Tool Limitations**: Agents can't easily share tools and context

---

## 3. The What (Technical Requirements)

### **User-Visible Behavior**
- Agents collaborate naturally on complex narrative generation tasks
- Human operators can observe and influence agent conversations in real-time
- Agent outputs are properly typed and validated automatically
- Agent sessions can be saved, replayed, and debugged

### **Technical Implementation**
- All existing agents (Director, Tactician, Weaver, Canonist) converted to Controlflow format
- Multi-agent collaboration workflows with shared context
- Tool integration for memory access, character analysis, and catalyst injection
- Hybrid Prefect-Controlflow orchestration preserving existing infrastructure

### **Success Criteria**
- [ ] All 4 agent classes converted to Controlflow Agent format
- [ ] Multi-agent collaboration workflow operational
- [ ] Agent tools integrated (memory, character analysis, catalyst)
- [ ] Hybrid Prefect task can execute Controlflow workflows
- [ ] Agent outputs properly typed with Pydantic validation
- [ ] Session replay functionality working
- [ ] End-to-end workflow test passes with agent collaboration
- [ ] Performance target: <2 seconds for multi-agent workflows

---

## 4. All Needed Context

### **Documentation & References**

```yaml
MUST_READ_CONTEXT:
  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/docs/research/CONTROLFLOW_RESEARCH_SUMMARY.md"
    why: "Complete Controlflow API patterns and integration strategies"
    critical: "Multi-agent collaboration examples and tool integration patterns"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/agents/personas.py"
    why: "Current agent implementation to preserve and enhance"
    critical: "Persona loading patterns, async execution, context handling"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/workflows/generation.py"
    why: "Existing Prefect workflows to integrate with, not replace"
    critical: "Working async patterns, job store integration, human approval flows"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/memory/qdrant.py"
    why: "Memory service integration for agent tools"
    critical: "Working spotlight retrieval, connection patterns, error handling"

  - url: "https://github.com/prefecthq/controlflow"
    section: "Agent creation and tool integration"
    critical: "Agent.__init__ patterns, tool function signatures, collaboration strategies"
```

### **Current Working Patterns to Preserve**

```python
# Existing agent pattern that WORKS ✅
class DirectorAgent(Agent):
    def __init__(self, client_type: str = "gemini", memory_service: Optional[MemoryService] = None):
        super().__init__("director", client_type, memory_service)

    async def execute(self, chapter_seed: str, context: Optional[dict[str, Any]] = None) -> StrategicBrief:
        # This pattern works and should be preserved
        pass

# Existing memory access pattern that WORKS ✅  
async def fetch_context_for_director(self, chapter_seed: str, active_characters: list[str]) -> DirectorContext:
    # This memory retrieval works and should become agent tools
    pass

# Existing Prefect integration that WORKS ✅
@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def director_task(chapter_seed: str, active_characters: Optional[list[str]] = None):
    director = DirectorAgent()
    strategic_brief = await director.execute(chapter_seed, context.model_dump())
    # This pattern should be enhanced, not replaced
```

### **Controlflow Integration Patterns**

```python
# TARGET: Convert to Controlflow format while preserving functionality
import controlflow as cf
from typing import List, Dict, Any

# Memory tool function for agents
def memory_context_tool(query: str, characters: List[str], thread_id: str = "main") -> Dict[str, Any]:
    """Retrieve narrative context from memory service"""
    return memory_service.fetch_context_for_director(query, characters)

def character_analysis_tool(character_id: str) -> Dict[str, Any]:
    """Analyze character state and relationships"""
    return character_service.get_character_analysis(character_id)

def catalyst_injection_tool(catalyst: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply creative catalyst to narrative context"""
    enhanced_context = context.copy()
    enhanced_context["catalyst"] = catalyst
    return enhanced_context

# Enhanced Controlflow agent
class NarrativeDirectorAgent(cf.Agent):
    def __init__(self):
        super().__init__(
            name="NarrativeDirector",
            instructions=self._load_persona("director"),  # Preserve existing persona loading
            tools=[
                memory_context_tool,
                character_analysis_tool, 
                catalyst_injection_tool
            ]
        )
    
    def _load_persona(self, persona_name: str) -> str:
        # Use existing persona loading logic
        return load_persona_from_file(persona_name)

# Multi-agent collaboration workflow
@cf.flow
def narrative_collaboration_flow(chapter_seed: str, active_characters: List[str]):
    # Agents collaborate with shared context
    director_brief = cf.run(
        "Create strategic narrative brief",
        agents=[director_agent],
        context=dict(seed=chapter_seed, characters=active_characters)
    )
    
    tactician_plan = cf.run(
        "Develop detailed chapter blueprint",
        agents=[tactician_agent], 
        context=dict(brief=director_brief, characters=active_characters)
    )
    
    return tactician_plan

# Hybrid Prefect-Controlflow integration
@task
async def enhanced_director_task(chapter_seed: str, active_characters: List[str]) -> str:
    """Enhanced director task using Controlflow collaboration"""
    
    # Execute Controlflow workflow
    collaboration_result = narrative_collaboration_flow(chapter_seed, active_characters)
    
    # Preserve existing job store integration
    job_id = job_store.create_job(
        agent="DirectorCollaboration",
        input_payload={
            "chapter_seed": chapter_seed,
            "active_characters": active_characters
        }
    )
    
    job_store.update_job_as_pending(job_id, collaboration_result.model_dump())
    
    return job_id
```

### **Critical Implementation Details**

```yaml
controlflow_agent_conversion:
  director_agent:
    purpose: "Strategic narrative planning with memory context"
    tools: ["memory_context_tool", "catalyst_injection_tool"]
    instructions: "Load from existing director persona file"
    output_type: "StrategicBrief Pydantic model"

  tactician_agent:
    purpose: "Detailed chapter planning with character focus"
    tools: ["character_analysis_tool", "memory_context_tool"]
    instructions: "Load from existing tactician persona file"
    output_type: "ChapterBlueprint Pydantic model"

  weaver_agent:
    purpose: "Prose generation with style consistency"
    tools: ["memory_context_tool", "style_analysis_tool"]
    instructions: "Load from existing weaver persona file"
    output_type: "Generated prose string"

  canonist_agent:
    purpose: "Validation and state management"
    tools: ["memory_context_tool", "state_validation_tool"]
    instructions: "Load from existing canonist persona file"
    output_type: "ValidationResult Pydantic model"

collaboration_patterns:
  sequential_collaboration:
    description: "Director → Tactician → Weaver → Canonist"
    shared_context: "All agents work with cumulative context"
    
  parallel_collaboration:
    description: "Multiple agents work on different aspects simultaneously"
    coordination: "Results combined through context fusion"

  interactive_collaboration:
    description: "Human can guide agent conversation"
    features: "Real-time input, steering, approval checkpoints"
```

---

## 5. Implementation Blueprint

### **Step 1: Agent Tool Implementation (Day 1-2)**

```python
# File: src/agents/tools.py
"""
Agent tools for Controlflow integration
"""
import asyncio
from typing import Dict, List, Any, Optional
from src.memory.qdrant import QdrantService
from src.services.character_service import CharacterService

# Initialize services
memory_service = QdrantService()
character_service = CharacterService()

def memory_context_tool(query: str, characters: List[str], thread_id: str = "main") -> Dict[str, Any]:
    """Retrieve narrative context from memory service."""
    try:
        # Use existing working memory retrieval
        context = asyncio.run(memory_service.fetch_context_for_director(query, characters))
        return {
            "spotlight_context": context.spotlight_context,
            "ambient_context": context.ambient_context,
            "character_count": len(characters),
            "status": "success"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def character_analysis_tool(character_id: str) -> Dict[str, Any]:
    """Analyze character state and relationships."""
    try:
        analysis = character_service.get_character_analysis(character_id)
        return {
            "character_id": character_id,
            "analysis": analysis,
            "status": "success"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def catalyst_injection_tool(catalyst: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Apply creative catalyst to narrative context."""
    enhanced_context = context.copy()
    enhanced_context["catalyst"] = catalyst
    enhanced_context["catalyst_applied"] = True
    return enhanced_context
```

### **Step 2: Controlflow Agent Wrappers (Day 2-3)**

```python
# File: src/agents/enhanced_personas.py
"""
Controlflow-enhanced agent personas
"""
import controlflow as cf
from pathlib import Path
from .tools import memory_context_tool, character_analysis_tool, catalyst_injection_tool
from .personas import Agent  # Import base Agent for persona loading

class NarrativeDirectorAgent(cf.Agent):
    """Enhanced Director agent with Controlflow collaboration capabilities."""
    
    def __init__(self):
        # Load existing persona (preserve working pattern)
        persona_content = self._load_persona("director")
        
        super().__init__(
            name="NarrativeDirector",
            instructions=persona_content,
            tools=[
                memory_context_tool,
                catalyst_injection_tool
            ]
        )
    
    def _load_persona(self, persona_name: str) -> str:
        """Load persona using existing working pattern."""
        personas_dir = Path(__file__).parent / "personas"
        persona_file = personas_dir / f"{persona_name}.md"
        
        if not persona_file.exists():
            # Use fallback (existing pattern)
            fallbacks = {
                "director": "You are a narrative director responsible for strategic story planning."
            }
            return fallbacks.get(persona_name, "You are a helpful AI assistant.")
        
        return persona_file.read_text(encoding='utf-8').strip()

class NarrativeTacticianAgent(cf.Agent):
    """Enhanced Tactician agent with character analysis capabilities."""
    
    def __init__(self):
        persona_content = self._load_persona("tactician")
        
        super().__init__(
            name="NarrativeTactician", 
            instructions=persona_content,
            tools=[
                memory_context_tool,
                character_analysis_tool
            ]
        )
    
    def _load_persona(self, persona_name: str) -> str:
        # Same pattern as Director
        pass

# Similar pattern for WeaverAgent and CanonistAgent...
```

### **Step 3: Multi-Agent Collaboration Workflows (Day 3-4)**

```python
# File: src/workflows/collaborative_generation.py
"""
Controlflow multi-agent collaboration workflows
"""
import controlflow as cf
from typing import List, Dict, Any
from .enhanced_personas import (
    NarrativeDirectorAgent, 
    NarrativeTacticianAgent,
    NarrativeWeaverAgent,
    NarrativeCanonistAgent
)
from ..models.material_models import StrategicBrief, ChapterBlueprint

# Initialize agents
director = NarrativeDirectorAgent()
tactician = NarrativeTacticianAgent()
weaver = NarrativeWeaverAgent()
canonist = NarrativeCanonistAgent()

@cf.flow
def narrative_collaboration_flow(chapter_seed: str, active_characters: List[str], 
                                catalyst: str = None) -> Dict[str, Any]:
    """
    Multi-agent collaboration for narrative generation.
    
    Args:
        chapter_seed: Initial narrative prompt
        active_characters: List of character IDs for this chapter
        catalyst: Optional creative catalyst
        
    Returns:
        Collaborative result with all agent outputs
    """
    
    # Step 1: Director creates strategic brief
    director_brief = cf.run(
        "Create strategic narrative brief for the chapter",
        result_type=StrategicBrief,
        agents=[director],
        context={
            "chapter_seed": chapter_seed,
            "active_characters": active_characters,
            "catalyst": catalyst
        }
    )
    
    # Step 2: Tactician develops detailed plan
    tactician_plan = cf.run(
        "Develop detailed chapter blueprint based on strategic brief",
        result_type=ChapterBlueprint,
        agents=[tactician],
        context={
            "strategic_brief": director_brief,
            "active_characters": active_characters
        }
    )
    
    # Step 3: Optional collaborative refinement
    if catalyst:
        refined_plan = cf.run(
            "Refine the chapter plan incorporating the creative catalyst",
            result_type=ChapterBlueprint,
            agents=[director, tactician],  # Both agents collaborate
            context={
                "original_plan": tactician_plan,
                "catalyst": catalyst,
                "strategic_brief": director_brief
            }
        )
        tactician_plan = refined_plan
    
    return {
        "strategic_brief": director_brief,
        "chapter_blueprint": tactician_plan,
        "collaboration_status": "completed",
        "agents_involved": ["director", "tactician"]
    }

@cf.flow 
def interactive_narrative_session(chapter_seed: str, active_characters: List[str]) -> Any:
    """Interactive session allowing human guidance during agent collaboration."""
    
    # Enable interactive mode
    result = cf.run(
        "Collaborate with human on narrative development",
        interactive=True,  # Enables human input during execution
        agents=[director, tactician],
        context={
            "chapter_seed": chapter_seed,
            "active_characters": active_characters
        }
    )
    
    return result
```

### **Step 4: Hybrid Prefect-Controlflow Integration (Day 4-5)**

```python
# File: src/workflows/hybrid_generation.py  
"""
Hybrid Prefect-Controlflow workflow integration
"""
from prefect import flow, task, get_run_logger
from prefect.tasks import exponential_backoff
from .collaborative_generation import narrative_collaboration_flow
from .jobs import JobStore

job_store = JobStore()

@task(retries=3, retry_delay_seconds=exponential_backoff(backoff_factor=2))
async def collaborative_director_task(chapter_seed: str, 
                                    active_characters: List[str],
                                    catalyst: str = None,
                                    dry_run: bool = False) -> str:
    """
    Enhanced director task using Controlflow multi-agent collaboration.
    Preserves existing Prefect patterns while adding agent collaboration.
    """
    logger = get_run_logger()
    
    logger.info(f"Starting collaborative director task: {chapter_seed}")
    
    # Create job in JobStore (preserve existing pattern)
    job_id = job_store.create_job(
        agent="DirectorCollaboration",
        input_payload={
            "chapter_seed": chapter_seed,
            "active_characters": active_characters,
            "catalyst": catalyst,
            "dry_run": dry_run
        }
    )
    
    try:
        if dry_run:
            # Dry run mode (preserve existing pattern)
            logger.info("DRY RUN MODE: Skipping actual agent collaboration")
            mock_result = {
                "strategic_brief": f"Mock strategic brief for: {chapter_seed}",
                "chapter_blueprint": f"Mock blueprint with catalyst: {catalyst}",
                "collaboration_status": "dry_run_completed"
            }
            job_store.update_job_as_pending(job_id, mock_result)
            return job_id
        
        # Execute Controlflow collaboration
        collaboration_result = narrative_collaboration_flow(
            chapter_seed=chapter_seed,
            active_characters=active_characters,
            catalyst=catalyst
        )
        
        # Save to job store (preserve existing pattern)
        job_store.update_job_as_pending(job_id, {
            "collaboration_result": collaboration_result,
            "status": "pending_approval"
        })
        
        logger.info(f"Collaborative director task complete. Job ID: {job_id}")
        return job_id
        
    except Exception as e:
        logger.error(f"Collaborative director task failed: {str(e)}")
        job_store.update_job_as_pending(job_id, {
            "error": str(e),
            "status": "failed"
        })
        raise

@flow(name="Enhanced Narrative Generation", log_prints=True)
async def enhanced_narrative_flow(chapter_seed: str, 
                                 active_characters: List[str] = None,
                                 catalyst: str = None,
                                 dry_run: bool = False) -> str:
    """
    Enhanced narrative generation flow with Controlflow collaboration.
    Maintains compatibility with existing workflows.
    """
    logger = get_run_logger()
    
    if active_characters is None:
        active_characters = ["char_protagonist"]
    
    logger.info(f"Starting enhanced narrative generation: {chapter_seed}")
    
    # Use collaborative director task
    director_job_id = await collaborative_director_task(
        chapter_seed=chapter_seed,
        active_characters=active_characters,
        catalyst=catalyst,
        dry_run=dry_run
    )
    
    if dry_run:
        logger.info(f"DRY RUN enhanced narrative complete. Job ID: {director_job_id}")
    else:
        logger.info(f"Enhanced narrative generation complete. Job ID: {director_job_id}")
        logger.info("HUMAN REVIEW REQUIRED for collaborative agent output")
        logger.info(f"Use CLI to review: factory.py review {director_job_id}")
    
    return director_job_id
```

---

## 6. Validation Gate

### **Level 1: Component Tests**
```bash
# Test agent wrapper creation
uv run python -c "
import sys
sys.path.append('src')
from agents.enhanced_personas import NarrativeDirectorAgent
director = NarrativeDirectorAgent()
print('✅ Director agent created:', director.name)
print('✅ Tools available:', len(director.tools))
"

# Test tool functionality
uv run python -c "
import sys
sys.path.append('src')
from agents.tools import memory_context_tool
result = memory_context_tool('test query', ['char1'], 'main')
print('✅ Memory tool:', result.get('status'))
"
```

### **Level 2: Collaboration Tests**
```bash
# Test multi-agent workflow
uv run python -c "
import controlflow as cf
import sys
sys.path.append('src')
from workflows.collaborative_generation import narrative_collaboration_flow

# Test collaboration workflow
result = narrative_collaboration_flow(
    'A mysterious figure approaches',
    ['char_protagonist'], 
    'Ancient prophecy surfaces'
)
print('✅ Collaboration workflow:', result['collaboration_status'])
print('✅ Agents involved:', result['agents_involved'])
"
```

### **Level 3: Integration Tests**
```bash
# Test hybrid Prefect-Controlflow workflow
uv run python -c "
import asyncio
import sys
sys.path.append('src')
from workflows.hybrid_generation import enhanced_narrative_flow

result = asyncio.run(enhanced_narrative_flow(
    'A mysterious figure approaches the castle',
    ['char_protagonist'],
    'An ancient prophecy surfaces',
    dry_run=True
))
print('✅ Hybrid workflow job ID:', result)
"

# Test end-to-end with CLI
uv run factory generate-enhanced --seed 'Test collaboration' --catalyst 'Test catalyst' --dry-run
```

### **Level 4: Performance Tests**
```bash
# Benchmark collaboration performance
uv run python -c "
import time
import asyncio
from workflows.hybrid_generation import enhanced_narrative_flow

start_time = time.time()
result = asyncio.run(enhanced_narrative_flow(
    'Performance test chapter seed',
    ['char_protagonist'],
    dry_run=True
))
duration = time.time() - start_time
print(f'✅ Performance: {duration:.2f}s (target: <2s)')
assert duration < 2.0, f'Performance target missed: {duration:.2f}s'
"
```

### **Level 5: End-to-End Validation**
```bash
# Complete system test
uv run factory test-collaboration --verbose
# Expected: All collaboration workflows pass

# CLI integration test  
uv run factory --help | grep -i "enhanced\|collaboration"
# Expected: New enhanced commands available

# Memory integration test
uv run python -c "
import asyncio
from workflows.collaborative_generation import narrative_collaboration_flow
from memory.qdrant import QdrantService

# Verify memory service integration
memory = QdrantService()
collections = asyncio.run(memory.list_collections())
print('✅ Memory service:', len(collections), 'collections')

# Test full collaboration with memory
result = narrative_collaboration_flow(
    'Test memory integration',
    ['char_protagonist']
)
print('✅ Memory-enabled collaboration:', result['collaboration_status'])
"
```

---

## 7. Gotchas and Edge Cases

### **Agent Tool Serialization**
- **Issue**: Controlflow tools must be serializable for distributed execution
- **Solution**: Use simple function signatures, avoid complex objects in tool definitions

### **Session Management**  
- **Issue**: Controlflow sessions can leak memory if not properly managed
- **Solution**: Implement explicit session cleanup in error handlers

### **Error Propagation**
- **Issue**: Controlflow agent errors may not propagate correctly to Prefect
- **Solution**: Wrap Controlflow calls in try-catch with proper error transformation

### **Performance Considerations**
- **Issue**: Multi-agent collaboration can be slower than single-agent execution  
- **Solution**: Implement parallel agent execution where possible, add performance monitoring

### **Context Size Limits**
- **Issue**: Large narrative context may exceed agent context limits
- **Solution**: Implement intelligent context truncation and summarization

---

## 8. Success Metrics

- **Functional**: All 4 agents converted and collaborative workflows operational
- **Performance**: <2 second response time for multi-agent collaboration  
- **Integration**: Seamless hybrid Prefect-Controlflow execution
- **Observability**: Complete visibility into agent decision-making
- **Compatibility**: No breaking changes to existing workflows
- **Quality**: Agent collaboration produces measurably better narrative outputs

---

This PRP provides complete implementation guidance for integrating Controlflow while preserving all existing functionality and patterns that already work in the Narrative Factory.