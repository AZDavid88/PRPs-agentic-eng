# Controlflow Research Summary for Narrative Factory

**Research Date**: 2025-07-20  
**Purpose**: AI agent orchestration integration for multi-agent narrative generation

## Key Findings

### **Controlflow Overview**

**Core Value Proposition**: Open-source Python framework for building structured, controllable AI agent workflows

#### **Built on Prefect 3.0**
- **Foundation**: Leverages Prefect for underlying workflow orchestration
- **Enhancement**: Adds AI agent-specific orchestration patterns
- **Compatibility**: Seamless integration with existing Prefect infrastructure

### **Core Architecture Concepts**

#### **Three Fundamental Components**

1. **Tasks**: Discrete, well-defined objectives with structured results
```python
sentiment_task = cf.Task(
    "Analyze the sentiment of the given text",
    result_type=float,
    instructions="Return a float between -1 (negative) and 1 (positive)"
)
```

2. **Agents**: Intelligent AI workers with configurable tools and instructions
```python
narrative_director = cf.Agent(
    name="NarrativeDirector",
    instructions="You are a master storyteller focusing on strategic narrative planning.",
    tools=[memory_retrieval, character_analysis]
)
```

3. **Flows**: High-level containers orchestrating workflows with shared context
```python
@cf.flow
def narrative_generation_flow(chapter_seed: str):
    strategic_brief = cf.run("Create strategic brief", agents=[director])
    tactical_plan = cf.run("Develop chapter plan", context=dict(brief=strategic_brief))
    return tactical_plan
```

### **Multi-Agent Orchestration Capabilities**

#### **Collaboration Strategies**
- **Round-Robin**: Each agent takes turns in sequence
- **Random**: Agents selected randomly for tasks
- **Moderated**: Designated agent controls turn order
- **Delegation**: Agents can assign tasks to each other

#### **Advanced Coordination Patterns**
```python
# Specialized agents working together
director = cf.Agent(name="Director", instructions="Strategic narrative planning")
tactician = cf.Agent(name="Tactician", instructions="Detailed scene planning")
weaver = cf.Agent(name="Weaver", instructions="Prose generation")

@cf.flow
def collaborative_narrative_flow():
    # Sequential collaboration with shared context
    brief = cf.run("Create strategic brief", agents=[director])
    plan = cf.run("Develop tactical plan", agents=[tactician], context=dict(brief=brief))
    prose = cf.run("Generate chapter text", agents=[weaver], context=dict(plan=plan))
    return prose
```

### **Structured Output & Type Safety**

#### **Pydantic Model Integration**
```python
from pydantic import BaseModel

class StrategicBrief(BaseModel):
    narrative_direction: str
    key_plot_points: list[str]
    character_focus: list[str]
    pacing_notes: str

# Controlflow ensures type-safe agent outputs
brief = cf.run(
    "Create strategic brief for chapter",
    result_type=StrategicBrief,
    agents=[director]
)
```

#### **Validation and Error Handling**
- Automatic result validation against Pydantic schemas
- Type checking for agent outputs
- Structured error handling for invalid responses

### **Integration with Narrative Factory Architecture**

#### **Perfect Fit for Narrative Generation**

**Current Agent Structure Compatibility**:
```python
# Current Narrative Factory agents can be directly adapted
class DirectorAgent(cf.Agent):
    def __init__(self):
        super().__init__(
            name="Director",
            instructions=self._load_persona("director"),
            tools=[memory_service.fetch_context, catalyst_injection]
        )

# Multi-agent collaboration becomes natural
@cf.flow  
def narrative_workflow():
    director_brief = cf.run("Strategic planning", agents=[director])
    tactician_plan = cf.run("Tactical planning", agents=[tactician], 
                           context=dict(brief=director_brief))
    weaver_text = cf.run("Prose generation", agents=[weaver],
                        context=dict(plan=tactician_plan))
    canonist_validation = cf.run("Validation", agents=[canonist],
                                context=dict(text=weaver_text))
    return canonist_validation
```

#### **Human-in-the-Loop Integration**
```python
@cf.flow
def hitl_narrative_flow():
    # AI agent work
    director_output = cf.run("Create brief", agents=[director])
    
    # Human approval checkpoint (handled by Prefect)
    approved_brief = await prefect_approval_task(director_output)
    
    # Continue with approved input
    tactician_output = cf.run("Create plan", agents=[tactician], 
                             context=dict(brief=approved_brief))
```

### **Tool Integration & Memory Access**

#### **Custom Tools for Narrative Factory**
```python
def memory_retrieval_tool(query: str, characters: list[str]) -> dict:
    """Retrieve relevant narrative context from Qdrant."""
    return memory_service.spotlight_retrieval(query, characters)

def character_analysis_tool(character_id: str) -> dict:
    """Analyze character state and relationships."""
    return character_service.get_character_analysis(character_id)

# Agents equipped with narrative-specific tools
director = cf.Agent(
    name="Director",
    tools=[memory_retrieval_tool, character_analysis_tool, catalyst_injection]
)
```

#### **Memory Context Sharing**
```python
@cf.flow
def context_aware_flow(chapter_seed: str, active_characters: list[str]):
    # Shared memory context across all agents
    memory_context = memory_service.fetch_context_for_director(
        chapter_seed, active_characters
    )
    
    # All agents work with shared context
    with cf.instructions(f"Narrative context: {memory_context}"):
        brief = cf.run("Strategic brief", agents=[director])
        plan = cf.run("Tactical plan", agents=[tactician])
        text = cf.run("Generate prose", agents=[weaver])
```

### **Interactive and Real-Time Capabilities**

#### **Interactive Agent Sessions**
```python
# Enable real-time human interaction
interactive_session = cf.run(
    "Collaborate with human on story direction",
    interactive=True,  # Enables human input during execution
    agents=[director, tactician]
)
```

#### **Streaming and Real-Time Updates**
```python
# Stream agent interactions for monitoring
for event, snapshot, delta in cf.run("Narrative planning", stream=True):
    if event.event == "agent-content":
        # Real-time display of agent reasoning
        websocket.send_json({"agent_output": snapshot})
```

### **Performance and Scalability**

#### **Concurrent Agent Execution**
- Multiple agents can work in parallel on different tasks
- Efficient resource utilization for complex workflows
- Automatic load balancing across available compute

#### **Session Management**
```python
# Save agent sessions for replay and analysis
session_id = cf.run(
    "Complex narrative planning",
    agents=[director, tactician, weaver],
    save_session=True
)

# Replay sessions for debugging or iteration
cf.replay_session(session_id)
```

### **Integration Strategy for Narrative Factory**

#### **Phase 2 Implementation Approach**

1. **Agent Wrapper Creation** (Week 1-2)
   - Convert existing agents to Controlflow format
   - Maintain existing persona loading patterns
   - Add tool integration for memory access

2. **Multi-Agent Orchestration** (Week 3-4)
   - Implement collaborative workflows
   - Add human approval checkpoints
   - Create agent communication patterns

3. **Advanced Features** (Week 5-6)
   - Interactive sessions for real-time collaboration
   - Session replay for narrative iteration
   - Performance optimization and monitoring

#### **Hybrid Architecture Benefits**

**Controlflow Handles**:
- AI agent collaboration and decision-making
- Structured output validation
- Agent tool management
- Interactive human-agent sessions

**Prefect Continues Handling**:
- Infrastructure orchestration
- Resource allocation and scaling  
- Monitoring and observability
- Deployment and lifecycle management

### **Development and Testing Patterns**

#### **Testing Multi-Agent Workflows**
```python
def test_narrative_collaboration():
    with cf.instructions("Use test personas and mock data"):
        result = narrative_generation_flow("Test chapter seed")
        assert isinstance(result.strategic_brief, StrategicBrief)
        assert len(result.tactical_plan.scenes) > 0
```

#### **Debugging and Introspection**
- Complete agent conversation logs
- Task dependency visualization
- Performance metrics per agent
- Error tracing across agent interactions

## Conclusion

Controlflow is the perfect complement to the Narrative Factory's existing Prefect infrastructure. It provides sophisticated AI agent orchestration while leveraging Prefect's proven workflow management capabilities.

**Key Integration Benefits**:
- **Seamless**: Built on Prefect 3.0, direct compatibility
- **Structured**: Type-safe agent outputs with Pydantic validation
- **Collaborative**: Natural multi-agent workflow patterns
- **Interactive**: Real-time human-agent collaboration
- **Observable**: Complete visibility into agent decision-making

The combination creates a powerful hybrid system: **Prefect for infrastructure, Controlflow for intelligence**.