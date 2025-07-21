# PRP: Human-in-the-Loop Web Interfaces Implementation

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_PHASE_05_ADVANCED_ORCHESTRATION.md  
**Target Agent:** Claude, GPT-4

---

## 1. The Goal (The "What")

Implement comprehensive Human-in-the-Loop web interfaces including real-time WebSocket chat for agent monitoring, workflow status dashboards, and enhanced approval interfaces to create an intuitive, responsive platform for narrative collaboration.

---

## 2. The Why (The "Why")

**Business Value:**
- **Real-time Collaboration**: Human operators can observe and guide agent decision-making processes
- **Enhanced User Experience**: Rich, interactive interfaces for narrative iteration and refinement
- **Operational Visibility**: Complete transparency into agent workflows and system health
- **Improved Quality Control**: Sophisticated approval workflows with detailed feedback mechanisms

**Technical Benefits:**
- **WebSocket Integration**: Live streaming of agent conversations and workflow updates
- **Dashboard Analytics**: Comprehensive monitoring of agent performance and system metrics
- **Enhanced HITL Workflows**: Rich approval interfaces with context-aware feedback
- **Production Monitoring**: Real-time observability into narrative generation processes

**Problems Solved:**
- **Limited Visibility**: Current CLI-only interface restricts real-time monitoring
- **Basic Approval Flows**: Simple approve/reject lacks nuanced feedback capabilities
- **No Live Monitoring**: Operators can't observe agent decision-making in real-time
- **Operational Blindness**: Limited visibility into system health and performance

---

## 3. The What (Technical Requirements)

### **User-Visible Behavior**
- Real-time chat interface showing live agent conversations and decision-making
- **Conversational Agent Chat Interface**: ChatGPT-style conversation with Director's cognitive engines
- Interactive workflow dashboard with agent status, memory utilization, and performance metrics
- Enhanced approval interfaces with rich feedback, iteration requests, and context injection
- **Natural Language Story Steering**: "Add Zara the spy", "Make this more cyberpunk" commands
- WebSocket-powered live updates for workflow status and agent health monitoring

### **Technical Implementation**
- FastAPI WebSocket endpoints for real-time agent conversation streaming
- **Chat API Integration**: Direct integration with Director's NarrativeStrategyEngine for conversational planning
- React/Vue.js dashboard with interactive workflow monitoring
- Enhanced job store integration with rich approval metadata
- **Natural Language Command Parser**: Translation of conversational commands to agent execution
- Real-time agent health monitoring with performance metrics
- WebSocket connection management with reconnection and state persistence

### **Success Criteria**
- [ ] WebSocket chat interface streaming live agent conversations
- [ ] **Conversational Director Interface**: ChatGPT-style conversation with Director's cognitive engines
- [ ] **Chat Memory Integration**: All conversational insights automatically ingested to Qdrant for agent RAG access
- [ ] Interactive workflow dashboard with real-time status updates
- [ ] Enhanced approval workflows with rich feedback capabilities
- [ ] **Natural Language Commands**: "Add Zara the spy", "This part seems weak, what about X?" workflows
- [ ] Agent health monitoring with performance metrics display
- [ ] **Story Brainstorming Chat**: Natural language planning conversations with Director
- [ ] **Agent RAG Access**: Other agents can retrieve and use conversational insights through memory system
- [ ] WebSocket connection resilience with automatic reconnection
- [ ] Mobile-responsive interface design for multi-device access
- [ ] Integration with existing Prefect workflows and job store
- [ ] Performance target: <100ms WebSocket message latency
- [ ] Security: Authentication and authorization for web interfaces

---

## 4. All Needed Context

### **Documentation & References**

```yaml
MUST_READ_CONTEXT:
  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/docs/research/PHASE1_COMPLETION_STATUS.md"
    why: "Current working state and validated components"
    critical: "FastAPI foundation established, job store workflows operational"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/workflows/generation.py"
    why: "Existing Prefect workflows and job store integration patterns"
    critical: "HITL approval workflows, job creation and state management"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/cli/commands.py"
    why: "Current approval interface patterns to enhance"
    critical: "Review, approve, reject command patterns, Rich console formatting"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/workflows/jobs.py"
    why: "Job store implementation for approval workflow integration"
    critical: "JobStore class, job state management, approval metadata"

  - url: "https://fastapi.tiangolo.com/advanced/websockets/"
    section: "WebSocket implementation patterns"
    critical: "Connection management, message broadcasting, error handling"

  - url: "https://github.com/prefecthq/prefect"
    section: "Prefect Events and Webhooks"
    critical: "Workflow state change notifications for dashboard integration"
```

### **Current Working Patterns to Preserve**

```python
# Existing job store pattern that WORKS ✅
class JobStore:
    def create_job(self, agent: str, input_payload: dict) -> str:
        # This pattern works and should be enhanced with rich metadata
        pass

    def update_job_as_pending(self, job_id: str, result: dict) -> None:
        # Enhance with WebSocket notification capability
        pass

# Existing approval workflow that WORKS ✅
@task
async def human_approval_task(job_id: str) -> str:
    # This pattern should trigger WebSocket notifications
    pass

# Existing FastAPI foundation that WORKS ✅
app = FastAPI(title="Narrative Factory", version="1.0.0")
# This foundation should be extended with WebSocket endpoints
```

### **WebSocket Integration Patterns**

```python
# TARGET: Real-time agent conversation streaming
from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.agent_subscribers: Dict[str, List[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
        
    async def broadcast_agent_update(self, agent_name: str, message: Dict[str, Any]):
        """Broadcast agent conversation updates to subscribers"""
        if agent_name in self.agent_subscribers:
            for connection in self.agent_subscribers[agent_name]:
                try:
                    await connection.send_text(json.dumps({
                        "type": "agent_update",
                        "agent": agent_name,
                        "timestamp": datetime.now().isoformat(),
                        "data": message
                    }))
                except:
                    # Remove dead connections
                    self.agent_subscribers[agent_name].remove(connection)

manager = ConnectionManager()

# Enhanced agent execution with WebSocket streaming
async def execute_with_streaming(agent: Agent, task_description: str, websocket_manager: ConnectionManager):
    """Execute agent task with live streaming to WebSocket clients"""
    
    # Notify start of agent execution
    await websocket_manager.broadcast_agent_update(agent.name, {
        "status": "started",
        "task": task_description
    })
    
    # Execute agent with progress callbacks
    result = await agent.execute_with_callbacks(
        task_description,
        progress_callback=lambda step, details: asyncio.create_task(
            websocket_manager.broadcast_agent_update(agent.name, {
                "status": "progress", 
                "step": step,
                "details": details
            })
        )
    )
    
    # Notify completion
    await websocket_manager.broadcast_agent_update(agent.name, {
        "status": "completed",
        "result": result.model_dump() if hasattr(result, 'model_dump') else str(result)
    })
    
    return result

# WebSocket endpoint for real-time agent monitoring
@app.websocket("/ws/agents/{agent_name}")
async def websocket_agent_endpoint(websocket: WebSocket, agent_name: str):
    await manager.connect(websocket)
    
    # Subscribe to specific agent updates
    if agent_name not in manager.agent_subscribers:
        manager.agent_subscribers[agent_name] = []
    manager.agent_subscribers[agent_name].append(websocket)
    
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle client messages (steering, feedback, etc.)
            if message.get("type") == "steering":
                # Implement agent steering functionality
                await handle_agent_steering(agent_name, message.get("instruction"))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if agent_name in manager.agent_subscribers:
            manager.agent_subscribers[agent_name].remove(websocket)

# Dashboard data endpoint
@app.get("/api/dashboard/status")
async def get_dashboard_status():
    """Provide comprehensive dashboard data"""
    return {
        "agents": {
            "director": await get_agent_health("director"),
            "tactician": await get_agent_health("tactician"), 
            "weaver": await get_agent_health("weaver"),
            "canonist": await get_agent_health("canonist")
        },
        "workflows": {
            "active_jobs": await get_active_jobs_count(),
            "pending_approvals": await get_pending_approvals_count(),
            "recent_completions": await get_recent_completions()
        },
        "memory": {
            "collections_count": await get_qdrant_collections_count(),
            "total_vectors": await get_total_vector_count(),
            "memory_utilization": await get_memory_utilization()
        },
        "performance": {
            "avg_response_time": await get_avg_response_time(),
            "success_rate": await get_success_rate(),
            "error_rate": await get_error_rate()
        }
    }

# Enhanced approval interface
@app.post("/api/jobs/{job_id}/approve")
async def enhanced_approve_job(job_id: str, approval_data: ApprovalRequest):
    """Enhanced approval with rich feedback and iteration capability"""
    
    job = await job_store.get_job(job_id)
    
    if approval_data.action == "approve":
        await job_store.approve_job(job_id, approval_data.feedback)
        await manager.broadcast_job_update(job_id, {"status": "approved", "feedback": approval_data.feedback})
        
    elif approval_data.action == "request_revision":
        await job_store.request_revision(job_id, approval_data.revision_instructions)
        await manager.broadcast_job_update(job_id, {"status": "revision_requested", "instructions": approval_data.revision_instructions})
        
    elif approval_data.action == "inject_context":
        await job_store.inject_context(job_id, approval_data.context_injection)
        await manager.broadcast_job_update(job_id, {"status": "context_injected", "context": approval_data.context_injection})
        
    return {"status": "success", "job_id": job_id}
```

### **Memory Integration Architecture**

```yaml
chat_memory_integration:
  purpose: "Ensure conversational insights available to all agents via RAG"
  
  ingestion_pipeline:
    trigger: "Every meaningful Director response (>50 chars)"
    process: "Format → Categorize → Vectorize → Store in Qdrant"
    metadata_enrichment: "conversation_type, insight_tags, session_context"
    
  memory_categorization:
    doc_type: "chat_insight"
    conversation_types: ["character_development", "plot_development", "worldbuilding", "writing_craft", "creative_brainstorming"]
    insight_tags: ["revision_request", "character_insight", "plot_guidance", "creative_solution"]
    
  agent_access_patterns:
    tactician: "Can search chat_insights for user feedback on pacing, character arcs"
    weaver: "Can retrieve style guidance and creative direction from conversations"
    canonist: "Can access continuity discussions and world-building insights"
    director: "Can reference previous planning conversations for consistency"
    
  retrieval_optimization:
    search_filters: "Filter by conversation_type, story_id, insight_tags"
    context_fusion: "Combine chat insights with traditional memory context"
    relevance_scoring: "Weight recent conversations higher for current planning"
```

### **Critical Implementation Details**

```yaml
websocket_architecture:
  connection_management:
    purpose: "Manage WebSocket connections with resilience and state"
    features: ["auto_reconnection", "connection_pooling", "heartbeat_monitoring"]
    patterns: ["subscriber_model", "broadcast_channels", "connection_lifecycle"]

  agent_streaming:
    purpose: "Stream live agent conversations and decision-making"
    data_types: ["agent_thoughts", "tool_usage", "decision_points", "progress_updates"] 
    filtering: ["agent_specific", "workflow_specific", "user_permissions"]

  dashboard_integration:
    purpose: "Real-time workflow and system status monitoring"
    metrics: ["agent_health", "workflow_progress", "memory_usage", "performance_stats"]
    update_frequency: "Real-time via WebSocket + 30-second polling fallback"

enhanced_approval_workflows:
  approval_types:
    simple_approval: "Basic approve/reject with comment"
    revision_request: "Request specific changes with detailed instructions"
    context_injection: "Add additional context or constraints to agent execution"
    iterative_refinement: "Multi-round approval with progressive enhancement"

  rich_feedback:
    structured_feedback: "Categorized feedback (plot, character, style, pacing)"
    inline_comments: "Line-by-line feedback on generated content"
    suggestion_mode: "Proposed edits and alternatives"
    approval_workflow: "Multi-stage approval with different reviewer roles"

frontend_architecture:
  technology_stack:
    framework: "React with TypeScript or Vue.js with TypeScript"
    websocket_client: "Native WebSocket API with reconnection logic"
    ui_components: "Material-UI or Vuetify for responsive design"
    state_management: "Redux/Vuex for complex state or Context API for simpler needs"

  responsive_design:
    breakpoints: ["mobile_320px", "tablet_768px", "desktop_1024px", "widescreen_1440px"]
    features: ["adaptive_layouts", "touch_optimized", "keyboard_shortcuts"]
    accessibility: ["screen_reader_support", "keyboard_navigation", "color_contrast"]

security_considerations:
  authentication:
    method: "JWT tokens with refresh capability"
    integration: "Integrate with existing user management system"
    session_management: "Secure session handling with timeout"

  websocket_security:
    authentication: "Token-based authentication for WebSocket connections"
    authorization: "Role-based access to different agent streams"
    rate_limiting: "Prevent WebSocket abuse and flooding"

  data_protection:
    encryption: "TLS/SSL for all WebSocket and API communications"
    data_sanitization: "Sanitize all user inputs before processing"
    audit_logging: "Log all user actions for security and compliance"
```

---

## 5. Implementation Blueprint

### **Step 1: WebSocket Foundation (Day 1-2)**

```python
# File: src/web/websocket_manager.py
"""
WebSocket connection management for real-time updates
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class WebSocketMessage(BaseModel):
    type: str
    timestamp: datetime
    data: Dict[str, Any]
    source: Optional[str] = None

class ConnectionManager:
    """Centralized WebSocket connection management"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {
            "agents": [],
            "workflows": [],
            "system": []
        }
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, subscription_type: str, client_id: str = None):
        """Accept WebSocket connection and manage subscriptions"""
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            
            if subscription_type in self.subscriptions:
                self.subscriptions[subscription_type].append(websocket)
                
            self.connection_metadata[websocket] = {
                "client_id": client_id,
                "subscription_type": subscription_type,
                "connected_at": datetime.now(),
                "last_heartbeat": datetime.now()
            }
            
            logger.info(f"WebSocket connected: {client_id} subscribed to {subscription_type}")
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise
            
    def disconnect(self, websocket: WebSocket):
        """Clean up WebSocket connection"""
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                
            # Remove from all subscriptions
            for subscription_list in self.subscriptions.values():
                if websocket in subscription_list:
                    subscription_list.remove(websocket)
                    
            # Clean up metadata
            if websocket in self.connection_metadata:
                client_info = self.connection_metadata.pop(websocket)
                logger.info(f"WebSocket disconnected: {client_info.get('client_id')}")
                
        except Exception as e:
            logger.error(f"WebSocket disconnect cleanup failed: {e}")
            
    async def broadcast_to_subscription(self, subscription_type: str, message: WebSocketMessage):
        """Broadcast message to all subscribers of a specific type"""
        if subscription_type not in self.subscriptions:
            return
            
        dead_connections = []
        message_json = message.model_dump_json()
        
        for websocket in self.subscriptions[subscription_type]:
            try:
                await websocket.send_text(message_json)
                # Update heartbeat
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]["last_heartbeat"] = datetime.now()
                    
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                dead_connections.append(websocket)
                
        # Clean up dead connections
        for dead_connection in dead_connections:
            self.disconnect(dead_connection)
            
    async def send_personal_message(self, websocket: WebSocket, message: WebSocketMessage):
        """Send message to specific WebSocket connection"""
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to send personal WebSocket message: {e}")
            self.disconnect(websocket)

# Global connection manager instance
connection_manager = ConnectionManager()
```

### **Step 2: Agent Streaming Integration (Day 2-3)**

```python
# File: src/agents/streaming_agents.py
"""
Enhanced agent execution with WebSocket streaming capabilities
"""
import asyncio
from typing import Callable, Optional, Any, Dict
from datetime import datetime
from ..web.websocket_manager import connection_manager, WebSocketMessage
from .personas import Agent

class StreamingAgentMixin:
    """Mixin to add WebSocket streaming to existing agents"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming_enabled = True
        self.progress_callbacks: List[Callable] = []
        
    async def stream_update(self, update_type: str, data: Dict[str, Any]):
        """Stream update to WebSocket subscribers"""
        if not self.streaming_enabled:
            return
            
        message = WebSocketMessage(
            type=f"agent_{update_type}",
            timestamp=datetime.now(),
            data={
                "agent_name": getattr(self, 'agent_type', 'unknown'),
                "update_type": update_type,
                **data
            },
            source=f"agent_{getattr(self, 'agent_type', 'unknown')}"
        )
        
        await connection_manager.broadcast_to_subscription("agents", message)
        
    async def execute_with_streaming(self, *args, **kwargs):
        """Execute agent task with live streaming"""
        
        # Stream start notification
        await self.stream_update("execution_started", {
            "task_description": str(args[0]) if args else "Unknown task",
            "parameters": kwargs
        })
        
        try:
            # Stream thinking process
            await self.stream_update("thinking", {
                "status": "Analyzing task requirements and context"
            })
            
            # Call original execute method
            result = await self.execute(*args, **kwargs)
            
            # Stream completion
            await self.stream_update("execution_completed", {
                "result_type": type(result).__name__,
                "success": True
            })
            
            return result
            
        except Exception as e:
            # Stream error
            await self.stream_update("execution_failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise

# Enhanced agent classes with streaming
class StreamingDirectorAgent(StreamingAgentMixin, DirectorAgent):
    """Director agent with WebSocket streaming"""
    pass

class StreamingTacticianAgent(StreamingAgentMixin, TacticianAgent):
    """Tactician agent with WebSocket streaming"""
    pass

class StreamingWeaverAgent(StreamingAgentMixin, WeaverAgent):
    """Weaver agent with WebSocket streaming"""
    pass

class StreamingCanonistAgent(StreamingAgentMixin, CanonistAgent):
    """Canonist agent with WebSocket streaming"""
    pass
```

### **Step 3: Dashboard API Endpoints (Day 3-4)**

```python
# File: src/web/dashboard_api.py
"""
Dashboard API endpoints for real-time monitoring
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ..memory.qdrant import QdrantService
from ..workflows.jobs import JobStore
from ..agents.health import AgentHealthMonitor

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

class DashboardStatus(BaseModel):
    agents: Dict[str, Any]
    workflows: Dict[str, Any]
    memory: Dict[str, Any]
    performance: Dict[str, Any]
    timestamp: datetime

class AgentHealth(BaseModel):
    name: str
    status: str  # "healthy", "warning", "error", "offline"
    last_activity: Optional[datetime]
    response_time_avg: Optional[float]
    success_rate: Optional[float]
    active_tasks: int

# Dependency injection
async def get_qdrant_service() -> QdrantService:
    return QdrantService()

async def get_job_store() -> JobStore:
    return JobStore()

async def get_health_monitor() -> AgentHealthMonitor:
    return AgentHealthMonitor()

@router.get("/status", response_model=DashboardStatus)
async def get_dashboard_status(
    qdrant: QdrantService = Depends(get_qdrant_service),
    job_store: JobStore = Depends(get_job_store),
    health_monitor: AgentHealthMonitor = Depends(get_health_monitor)
):
    """Get comprehensive dashboard status"""
    
    try:
        # Gather all status information concurrently
        agents_task = get_agents_status(health_monitor)
        workflows_task = get_workflows_status(job_store)
        memory_task = get_memory_status(qdrant)
        performance_task = get_performance_status()
        
        agents, workflows, memory, performance = await asyncio.gather(
            agents_task, workflows_task, memory_task, performance_task
        )
        
        return DashboardStatus(
            agents=agents,
            workflows=workflows,
            memory=memory,
            performance=performance,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard status: {str(e)}")

async def get_agents_status(health_monitor: AgentHealthMonitor) -> Dict[str, Any]:
    """Get status for all agents"""
    agents = ["director", "tactician", "weaver", "canonist"]
    agent_status = {}
    
    for agent_name in agents:
        health = await health_monitor.get_agent_health(agent_name)
        agent_status[agent_name] = {
            "status": health.status,
            "last_activity": health.last_activity,
            "response_time": health.avg_response_time,
            "success_rate": health.success_rate,
            "active_tasks": health.active_tasks,
            "health_score": health.calculate_health_score()
        }
    
    return agent_status

async def get_workflows_status(job_store: JobStore) -> Dict[str, Any]:
    """Get workflow status information"""
    return {
        "active_jobs": await job_store.get_active_jobs_count(),
        "pending_approvals": await job_store.get_pending_approvals_count(),
        "completed_today": await job_store.get_completed_jobs_count(since=datetime.now() - timedelta(days=1)),
        "failed_jobs": await job_store.get_failed_jobs_count(since=datetime.now() - timedelta(hours=24)),
        "average_completion_time": await job_store.get_average_completion_time()
    }

async def get_memory_status(qdrant: QdrantService) -> Dict[str, Any]:
    """Get memory system status"""
    collections = await qdrant.list_collections()
    total_vectors = 0
    
    for collection in collections:
        try:
            info = await qdrant.get_collection_info(collection)
            total_vectors += info.vectors_count
        except:
            pass  # Skip if collection info fails
    
    return {
        "collections_count": len(collections),
        "total_vectors": total_vectors,
        "memory_utilization": await calculate_memory_utilization(),
        "index_health": await check_index_health(qdrant)
    }

async def get_performance_status() -> Dict[str, Any]:
    """Get system performance metrics"""
    # This would integrate with actual performance monitoring
    return {
        "avg_response_time": 1.2,  # seconds
        "requests_per_minute": 45,
        "success_rate": 0.97,
        "error_rate": 0.03,
        "cpu_usage": 0.65,
        "memory_usage": 0.72
    }

@router.get("/agents/{agent_name}/health")
async def get_agent_health(
    agent_name: str,
    health_monitor: AgentHealthMonitor = Depends(get_health_monitor)
):
    """Get detailed health information for specific agent"""
    
    if agent_name not in ["director", "tactician", "weaver", "canonist"]:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    health = await health_monitor.get_agent_health(agent_name)
    
    return {
        "agent_name": agent_name,
        "status": health.status,
        "health_score": health.calculate_health_score(),
        "metrics": {
            "last_activity": health.last_activity,
            "response_time_avg": health.avg_response_time,
            "response_time_p95": health.p95_response_time,
            "success_rate": health.success_rate,
            "error_rate": health.error_rate,
            "active_tasks": health.active_tasks,
            "completed_tasks": health.completed_tasks
        },
        "recent_errors": health.recent_errors[-5:] if health.recent_errors else []
    }

@router.websocket("/ws/realtime")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await connection_manager.connect(websocket, "system", "dashboard")
    
    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.now().isoformat()}))
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
```

### **Step 4: Conversational Agent Chat Interface (Day 4-5)**

```python
# File: src/web/chat_api.py
"""
Conversational chat interface for Direct integration with Director's cognitive engines
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
import json
import asyncio
from ..agents.prompts.director import DirectorAgent
from ..memory.qdrant import QdrantService
from ..web.websocket_manager import connection_manager, WebSocketMessage
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant" 
    content: str
    timestamp: datetime
    message_id: str

class ChatSession(BaseModel):
    session_id: str
    user_id: str
    agent_type: str  # "director", "tactician", etc.
    messages: List[ChatMessage] = []
    context: Dict[str, Any] = {}
    created_at: datetime
    last_activity: datetime

class ChatCommand(BaseModel):
    type: str  # "story_planning", "character_addition", "feedback", "brainstorm"
    content: str
    context: Optional[Dict[str, Any]] = None

class DirectorChatInterface:
    """Chat interface specifically for Director agent conversations"""
    
    def __init__(self):
        self.director_agent = DirectorAgent()
        self.qdrant_service = QdrantService()
        self.active_sessions: Dict[str, ChatSession] = {}
        
    async def create_chat_session(self, user_id: str, initial_context: Dict[str, Any] = None) -> str:
        """Create new chat session with Director"""
        import uuid
        session_id = f"chat_{uuid.uuid4().hex[:8]}"
        
        session = ChatSession(
            session_id=session_id,
            user_id=user_id,
            agent_type="director",
            context=initial_context or {},
            created_at=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.active_sessions[session_id] = session
        
        # Send initial greeting
        greeting = await self.generate_director_greeting(initial_context)
        await self.add_message(session_id, "assistant", greeting)
        
        return session_id
    
    async def process_user_message(self, session_id: str, user_message: str) -> str:
        """Process user message and generate Director response"""
        
        if session_id not in self.active_sessions:
            raise ValueError(f"Chat session {session_id} not found")
            
        session = self.active_sessions[session_id]
        
        # Add user message to session
        await self.add_message(session_id, "user", user_message)
        
        # Parse message for commands or natural conversation
        command = await self.parse_user_intent(user_message, session.context)
        
        # Generate Director response based on cognitive engines
        response = await self.generate_director_response(command, session)
        
        # Add Director response to session
        await self.add_message(session_id, "assistant", response)
        
        # Update session activity
        session.last_activity = datetime.now()
        
        return response
    
    async def parse_user_intent(self, message: str, context: Dict[str, Any]) -> ChatCommand:
        """Parse user message to identify intent and command type"""
        
        message_lower = message.lower()
        
        # Character addition patterns
        if any(phrase in message_lower for phrase in ["add", "create", "introduce"]) and any(phrase in message_lower for phrase in ["character", "person", "spy", "villain"]):
            return ChatCommand(
                type="character_addition",
                content=message,
                context={"action": "add_character", "raw_input": message}
            )
        
        # Story feedback patterns  
        elif any(phrase in message_lower for phrase in ["seems weak", "doesn't work", "what about", "change this"]):
            return ChatCommand(
                type="story_feedback", 
                content=message,
                context={"action": "request_revision", "feedback_type": "improvement"}
            )
        
        # Brainstorming patterns
        elif any(phrase in message_lower for phrase in ["what if", "brainstorm", "ideas", "stuck", "direction"]):
            return ChatCommand(
                type="brainstorm",
                content=message,
                context={"action": "strategic_planning", "mode": "creative"}
            )
        
        # Story steering patterns
        elif any(phrase in message_lower for phrase in ["make", "add", "more", "cyberpunk", "romantic", "darker"]):
            return ChatCommand(
                type="story_steering",
                content=message,
                context={"action": "narrative_adjustment", "style_change": True}
            )
        
        # Default to general planning conversation
        else:
            return ChatCommand(
                type="story_planning",
                content=message,
                context={"action": "general_conversation"}
            )
    
    async def generate_director_response(self, command: ChatCommand, session: ChatSession) -> str:
        """Generate Director response using cognitive engines"""
        
        # Build context for Director's cognitive engines
        director_context = {
            "chat_history": [msg.content for msg in session.messages[-5:]],  # Last 5 messages
            "story_context": session.context,
            "command_type": command.type,
            "user_intent": command.context
        }
        
        if command.type == "character_addition":
            return await self.handle_character_addition(command.content, director_context)
            
        elif command.type == "story_feedback":
            return await self.handle_story_feedback(command.content, director_context)
            
        elif command.type == "brainstorm":
            return await self.handle_brainstorming(command.content, director_context)
            
        elif command.type == "story_steering":
            return await self.handle_story_steering(command.content, director_context)
            
        else:
            return await self.handle_general_conversation(command.content, director_context)
    
    async def handle_character_addition(self, user_input: str, context: Dict[str, Any]) -> str:
        """Handle character addition requests using Director's cognitive engines"""
        
        # Use Director's NarrativeStrategyEngine for character integration analysis
        prompt = f"""
        CONVERSATIONAL DIRECTOR MODE - CHARACTER INTEGRATION
        
        User wants to add: {user_input}
        
        Use your NarrativeStrategyEngine to:
        1. Analyze the character concept for story integration potential
        2. Suggest how this character fits into current narrative threads
        3. Propose integration scenes or story beats
        4. Identify potential conflicts or relationships
        
        Respond conversationally, as if brainstorming with a fellow writer.
        """
        
        # Execute Director's cognitive engines
        response = await self.director_agent.execute_with_cognitive_engines(prompt, context)
        
        return f"Great character idea! {response}\n\nWould you like me to create a formal character integration plan, or shall we explore this concept further?"
    
    async def handle_story_feedback(self, feedback: str, context: Dict[str, Any]) -> str:
        """Handle story feedback and revision suggestions"""
        
        prompt = f"""
        CONVERSATIONAL DIRECTOR MODE - STORY IMPROVEMENT
        
        User feedback: {feedback}
        
        Use your NarrativeStrategyEngine to:
        1. Analyze what might be weak about the current approach
        2. Generate 3-4 alternative approaches 
        3. Consider how changes affect overall story arc
        4. Suggest specific improvements
        
        Respond as a collaborative writing partner offering solutions.
        """
        
        response = await self.director_agent.execute_with_cognitive_engines(prompt, context)
        
        return f"I see what you mean. {response}\n\nWhich direction appeals to you? I can develop any of these further or generate more alternatives."
    
    async def handle_brainstorming(self, query: str, context: Dict[str, Any]) -> str:
        """Handle creative brainstorming sessions"""
        
        prompt = f"""
        CONVERSATIONAL DIRECTOR MODE - CREATIVE BRAINSTORMING
        
        User query: {query}
        
        Use your full NarrativeStrategyEngine cognitive suite:
        1. Cycle1_DivergentIdeation for multiple creative options
        2. Consider psychological warfare and character exploitation angles
        3. Generate plot vectors that escalate tension
        4. Suggest narrative mechanics that create compelling conflicts
        
        Present ideas conversationally, building on the user's creative energy.
        """
        
        response = await self.director_agent.execute_with_cognitive_engines(prompt, context)
        
        return f"Let's explore this! {response}\n\nWhat resonates with you? We can dive deeper into any of these directions."
    
    async def _ingest_chat_content_to_memory(self, session_id: str, message: ChatMessage):
        """
        CRITICAL: Ingest conversational content into Qdrant for agent RAG access.
        
        This ensures that insights from human-agent conversations are available 
        to all agents through the RAG retrieval system.
        """
        try:
            from src.ingestion.pipeline import MaterialIngestionPipeline
            from src.models.material_models import MaterialIngestionRequest
            
            session = self.active_sessions.get(session_id)
            if not session:
                return
            
            # Only ingest meaningful assistant messages (not user messages)
            if message.role != "assistant" or len(message.content) < 50:
                return
            
            # Format content for memory ingestion
            memory_content = f"""
CONVERSATIONAL_INSIGHT - Director Chat Session

Session Context: {session.context.get('story_id', 'general_planning')}
User Query Context: {session.messages[-2].content if len(session.messages) >= 2 else 'N/A'}

Director Response:
{message.content}

Chat Metadata:
- Session ID: {session_id}
- Timestamp: {message.timestamp}
- Message ID: {message.message_id}
- User ID: {session.user_id}
"""
            
            # Create ingestion request
            ingestion_pipeline = MaterialIngestionPipeline()
            
            # Determine conversation type for categorization
            conversation_type = self._classify_conversation_type(message.content)
            
            ingestion_request = MaterialIngestionRequest(
                content=memory_content,
                source_path=f"chat_session_{session_id}",
                genre="narrative_planning",
                additional_genres=[conversation_type],
                custom_categories=["conversational_insight", "director_guidance", "human_ai_collaboration"],
                story_id=session.context.get('story_id'),
                metadata={
                    "doc_type": "chat_insight",
                    "conversation_type": conversation_type,
                    "session_id": session_id,
                    "agent_type": "director",
                    "message_id": message.message_id,
                    "user_id": session.user_id,
                    "timestamp": message.timestamp.isoformat(),
                    "thread_id": f"chat_thread_{session_id}",
                    "insight_tags": self._extract_insight_tags(message.content)
                }
            )
            
            # Ingest into memory system
            response = await ingestion_pipeline.ingest_materials([ingestion_request])
            
            if response.success:
                logger.info(f"Successfully ingested chat content to memory: session={session_id}, message={message.message_id}")
            else:
                logger.error(f"Failed to ingest chat content: {response.error}")
                
        except Exception as e:
            logger.error(f"Chat content ingestion failed: {e}")
    
    def _classify_conversation_type(self, content: str) -> str:
        """Classify conversation type for better categorization."""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ["character", "personality", "motivation", "relationship"]):
            return "character_development"
        elif any(word in content_lower for word in ["plot", "story", "narrative", "arc", "conflict"]):
            return "plot_development"
        elif any(word in content_lower for word in ["world", "setting", "location", "culture", "magic"]):
            return "worldbuilding"
        elif any(word in content_lower for word in ["style", "tone", "pacing", "voice", "prose"]):
            return "writing_craft"
        elif any(word in content_lower for word in ["brainstorm", "idea", "creative", "inspiration"]):
            return "creative_brainstorming"
        else:
            return "general_guidance"
    
    def _extract_insight_tags(self, content: str) -> List[str]:
        """Extract relevant tags for better searchability."""
        tags = []
        content_lower = content.lower()
        
        # Story elements
        tag_patterns = {
            "revision_request": ["revise", "change", "improve", "modify"],
            "character_insight": ["character", "personality", "motivation"],
            "plot_guidance": ["plot", "story", "narrative", "tension"],
            "creative_solution": ["solution", "approach", "strategy", "fix"],
            "world_expansion": ["world", "setting", "culture", "history"],
            "dialogue_craft": ["dialogue", "conversation", "speech"],
            "pacing_advice": ["pacing", "rhythm", "flow", "speed"],
            "conflict_escalation": ["conflict", "tension", "drama", "stakes"]
        }
        
        for tag, keywords in tag_patterns.items():
            if any(keyword in content_lower for keyword in keywords):
                tags.append(tag)
        
        return tags[:5]  # Limit to 5 most relevant tags
    
    async def add_message(self, session_id: str, role: str, content: str):
        """Add message to chat session and broadcast via WebSocket"""
        import uuid
        
        message = ChatMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            message_id=uuid.uuid4().hex[:8]
        )
        
        self.active_sessions[session_id].messages.append(message)
        
        # Broadcast to WebSocket subscribers
        websocket_message = WebSocketMessage(
            type="chat_message",
            timestamp=datetime.now(),
            data={
                "session_id": session_id,
                "message": message.model_dump(),
                "agent_type": "director"
            },
            source="chat_interface"
        )
        
        await connection_manager.broadcast_to_subscription("agents", websocket_message)
        
        # **CRITICAL**: Ingest chat content into Qdrant for agent RAG access
        await self._ingest_chat_content_to_memory(session_id, message)

# Global chat interface instance
director_chat = DirectorChatInterface()

@router.post("/sessions")
async def create_chat_session(
    user_id: str,
    initial_context: Optional[Dict[str, Any]] = None
):
    """Create new chat session with Director"""
    session_id = await director_chat.create_chat_session(user_id, initial_context)
    return {"session_id": session_id, "status": "created"}

@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: str,
    message: str
):
    """Send message to Director and get response"""
    try:
        response = await director_chat.process_user_message(session_id, message)
        return {"response": response, "status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.websocket("/ws/{session_id}")
async def websocket_chat_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat with Director"""
    await connection_manager.connect(websocket, "agents", f"chat_{session_id}")
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "user_message":
                # Process user message and send Director response
                user_message = message_data.get("content", "")
                response = await director_chat.process_user_message(session_id, user_message)
                
                # Response is automatically broadcast via add_message method
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

@router.get("/sessions/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get chat history for session"""
    if session_id not in director_chat.active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = director_chat.active_sessions[session_id]
    return {
        "session_id": session_id,
        "messages": [msg.model_dump() for msg in session.messages],
        "context": session.context,
        "last_activity": session.last_activity
    }
```

### **Step 5: Enhanced Approval Interface (Day 5-6)**

```python
# File: src/web/approval_api.py
"""
Enhanced approval interface with rich feedback capabilities
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from enum import Enum
from ..workflows.jobs import JobStore
from ..web.websocket_manager import connection_manager, WebSocketMessage

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

class ApprovalAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"
    INJECT_CONTEXT = "inject_context"
    REQUEST_ITERATION = "request_iteration"

class FeedbackCategory(str, Enum):
    PLOT = "plot"
    CHARACTER = "character"
    STYLE = "style"
    PACING = "pacing"
    DIALOGUE = "dialogue"
    WORLDBUILDING = "worldbuilding"
    GENERAL = "general"

class StructuredFeedback(BaseModel):
    category: FeedbackCategory
    line_number: Optional[int] = None
    original_text: Optional[str] = None
    feedback: str
    suggested_change: Optional[str] = None
    severity: str = Field(default="medium", pattern="^(low|medium|high|critical)$")

class ApprovalRequest(BaseModel):
    action: ApprovalAction
    general_feedback: Optional[str] = None
    structured_feedback: List[StructuredFeedback] = []
    revision_instructions: Optional[str] = None
    context_injection: Optional[Dict[str, Any]] = None
    iteration_request: Optional[str] = None
    reviewer_id: str
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")

class ApprovalResponse(BaseModel):
    job_id: str
    status: str
    message: str
    next_action: Optional[str] = None
    estimated_completion: Optional[datetime] = None

@router.get("/pending")
async def get_pending_approvals(
    job_store: JobStore = Depends(lambda: JobStore()),
    limit: int = 50,
    offset: int = 0
):
    """Get list of jobs pending approval"""
    
    pending_jobs = await job_store.get_pending_approvals(limit=limit, offset=offset)
    
    enhanced_jobs = []
    for job in pending_jobs:
        # Enhance job data with additional context
        enhanced_job = {
            **job,
            "content_preview": await generate_content_preview(job.get("result", {})),
            "agent_metadata": await get_agent_metadata(job.get("agent", "")),
            "estimated_review_time": estimate_review_time(job.get("result", {})),
            "complexity_score": calculate_complexity_score(job.get("result", {}))
        }
        enhanced_jobs.append(enhanced_job)
    
    return {
        "pending_approvals": enhanced_jobs,
        "total_count": await job_store.get_pending_approvals_count(),
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": len(pending_jobs) == limit
        }
    }

@router.get("/jobs/{job_id}")
async def get_job_details(
    job_id: str,
    job_store: JobStore = Depends(lambda: JobStore())
):
    """Get detailed information about a specific job"""
    
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Enhance with additional context
    enhanced_job = {
        **job,
        "content_analysis": await analyze_content(job.get("result", {})),
        "similar_jobs": await find_similar_jobs(job_id, limit=3),
        "approval_history": await get_approval_history(job_id),
        "agent_performance": await get_agent_performance_context(job.get("agent", ""))
    }
    
    return enhanced_job

@router.post("/jobs/{job_id}/approve", response_model=ApprovalResponse)
async def process_approval(
    job_id: str,
    approval_request: ApprovalRequest,
    job_store: JobStore = Depends(lambda: JobStore())
):
    """Process approval request with enhanced feedback capabilities"""
    
    job = await job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.get("status") != "pending_approval":
        raise HTTPException(status_code=400, detail="Job is not pending approval")
    
    try:
        response = await handle_approval_action(job_id, approval_request, job_store)
        
        # Broadcast update via WebSocket
        await broadcast_approval_update(job_id, approval_request.action, response)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval processing failed: {str(e)}")

async def handle_approval_action(
    job_id: str, 
    approval_request: ApprovalRequest, 
    job_store: JobStore
) -> ApprovalResponse:
    """Handle different types of approval actions"""
    
    action = approval_request.action
    timestamp = datetime.now()
    
    # Create approval metadata
    approval_metadata = {
        "reviewer_id": approval_request.reviewer_id,
        "timestamp": timestamp,
        "action": action,
        "general_feedback": approval_request.general_feedback,
        "structured_feedback": [f.model_dump() for f in approval_request.structured_feedback],
        "priority": approval_request.priority
    }
    
    if action == ApprovalAction.APPROVE:
        await job_store.approve_job(job_id, approval_metadata)
        return ApprovalResponse(
            job_id=job_id,
            status="approved",
            message="Job approved successfully",
            next_action="workflow_continuation"
        )
        
    elif action == ApprovalAction.REJECT:
        await job_store.reject_job(job_id, approval_metadata)
        return ApprovalResponse(
            job_id=job_id,
            status="rejected",
            message="Job rejected",
            next_action="workflow_termination"
        )
        
    elif action == ApprovalAction.REQUEST_REVISION:
        revision_metadata = {
            **approval_metadata,
            "revision_instructions": approval_request.revision_instructions
        }
        await job_store.request_revision(job_id, revision_metadata)
        
        # Estimate completion time based on revision complexity
        estimated_completion = estimate_revision_time(approval_request.structured_feedback)
        
        return ApprovalResponse(
            job_id=job_id,
            status="revision_requested",
            message="Revision requested",
            next_action="agent_revision",
            estimated_completion=estimated_completion
        )
        
    elif action == ApprovalAction.INJECT_CONTEXT:
        context_metadata = {
            **approval_metadata,
            "context_injection": approval_request.context_injection
        }
        await job_store.inject_context(job_id, context_metadata)
        
        return ApprovalResponse(
            job_id=job_id,
            status="context_injected",
            message="Context injected, ready for re-execution",
            next_action="agent_re_execution"
        )
        
    elif action == ApprovalAction.REQUEST_ITERATION:
        iteration_metadata = {
            **approval_metadata,
            "iteration_request": approval_request.iteration_request
        }
        await job_store.request_iteration(job_id, iteration_metadata)
        
        return ApprovalResponse(
            job_id=job_id,
            status="iteration_requested", 
            message="Iteration requested",
            next_action="iterative_improvement"
        )

async def broadcast_approval_update(job_id: str, action: ApprovalAction, response: ApprovalResponse):
    """Broadcast approval updates to WebSocket subscribers"""
    
    message = WebSocketMessage(
        type="approval_update",
        timestamp=datetime.now(),
        data={
            "job_id": job_id,
            "action": action,
            "new_status": response.status,
            "message": response.message,
            "next_action": response.next_action
        },
        source="approval_system"
    )
    
    await connection_manager.broadcast_to_subscription("workflows", message)

# Helper functions for enhanced approval capabilities
async def generate_content_preview(result: Dict[str, Any]) -> Dict[str, Any]:
    """Generate preview of content for approval interface"""
    return {
        "word_count": len(result.get("content", "").split()) if result.get("content") else 0,
        "key_themes": extract_key_themes(result.get("content", "")),
        "character_mentions": extract_character_mentions(result.get("content", "")),
        "tone_analysis": analyze_tone(result.get("content", ""))
    }

async def analyze_content(result: Dict[str, Any]) -> Dict[str, Any]:
    """Perform detailed content analysis for approval context"""
    content = result.get("content", "")
    
    return {
        "readability_score": calculate_readability(content),
        "sentiment_analysis": analyze_sentiment(content),
        "style_consistency": check_style_consistency(content),
        "narrative_elements": identify_narrative_elements(content),
        "potential_issues": identify_potential_issues(content)
    }

def estimate_review_time(result: Dict[str, Any]) -> int:
    """Estimate review time in minutes based on content complexity"""
    content = result.get("content", "")
    word_count = len(content.split())
    
    # Base time: 2 minutes per 100 words, minimum 5 minutes
    base_time = max(5, (word_count / 100) * 2)
    
    # Adjust for complexity
    complexity_multiplier = 1.0
    if "dialogue" in content.lower():
        complexity_multiplier += 0.2
    if "action" in content.lower():
        complexity_multiplier += 0.1
        
    return int(base_time * complexity_multiplier)
```

---

## 6. Validation Gate

### **Level 1: WebSocket Tests**
```bash
# Test WebSocket connection management
uv run python -c "
import asyncio
from src.web.websocket_manager import ConnectionManager
manager = ConnectionManager()
print('✅ WebSocket manager created')
"

# Test real-time messaging
uv run python test_websocket_messaging.py
```

### **Level 2: Dashboard API Tests**
```bash
# Test dashboard endpoints
curl -X GET http://localhost:8000/api/dashboard/status
# Expected: JSON with agents, workflows, memory, performance data

# Test agent health endpoint
curl -X GET http://localhost:8000/api/dashboard/agents/director/health
# Expected: Detailed agent health metrics
```

### **Level 3: Enhanced Approval Tests**
```bash
# Test approval workflow
curl -X POST http://localhost:8000/api/approvals/jobs/test-job-id/approve \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "reviewer_id": "test-user", "general_feedback": "Looks good!"}'
# Expected: Approval confirmation with next action
```

### **Level 4: Chat Memory Integration Tests**
```bash
# Test conversational content ingestion to Qdrant
uv run python -c "
import asyncio
from src.web.chat_api import DirectorChatInterface
from src.memory.qdrant import QdrantService

async def test_chat_memory_integration():
    chat = DirectorChatInterface()
    session_id = await chat.create_chat_session('test_user')
    
    # Send test message
    response = await chat.process_user_message(session_id, 'Add a mysterious character who knows magic')
    
    # Verify memory ingestion 
    qdrant = QdrantService()
    search_results = await qdrant.search_by_content(
        'mysterious character magic',
        collection_name='world_bible',
        limit=5
    )
    
    # Should find the ingested conversation
    chat_insights = [r for r in search_results if r.get('doc_type') == 'chat_insight']
    assert len(chat_insights) > 0, 'Chat content not properly ingested to memory'
    print('✅ Chat content successfully ingested and retrievable')

asyncio.run(test_chat_memory_integration())
"
# Expected: Chat content ingested to Qdrant and retrievable by other agents
```

### **Level 5: Integration Tests**
```bash
# Test end-to-end workflow with web interface
uv run factory generate --seed "Test web interface integration" --mode interactive
# Expected: WebSocket updates during execution, approval interface available

# Test WebSocket reconnection
uv run python test_websocket_resilience.py
# Expected: Automatic reconnection after network interruption

# Test agent RAG access to chat insights
uv run python -c "
import asyncio
from src.agents.personas import TacticianAgent
from src.memory.qdrant import QdrantService

async def test_agent_chat_access():
    qdrant = QdrantService()
    tactician = TacticianAgent()
    
    # Search for chat insights
    chat_memories = await qdrant.search_with_filters(
        filters={'doc_type': 'chat_insight'},
        collection_name='world_bible',
        limit=10
    )
    
    if chat_memories:
        print(f'✅ Found {len(chat_memories)} chat insights available to agents')
        
        # Test agent can access chat context
        context = {'chat_insights': chat_memories[:3]}
        result = await tactician.execute('Plan chapter incorporating user feedback', context)
        print('✅ Agent successfully used chat insights in planning')
    else:
        print('⚠️ No chat insights found - may need to run chat test first')

asyncio.run(test_agent_chat_access())
"
# Expected: Agents can access and use conversational insights through RAG
```

---

## 7. Gotchas and Edge Cases

### **WebSocket Connection Management**
- **Issue**: Connections can be dropped without proper cleanup
- **Solution**: Implement heartbeat mechanism and connection health monitoring

### **Real-time Performance**
- **Issue**: High-frequency updates can overwhelm WebSocket clients
- **Solution**: Implement message throttling and batching for performance

### **State Synchronization**
- **Issue**: WebSocket state can become out of sync with backend
- **Solution**: Implement periodic state reconciliation and client refresh

### **Security Considerations**
- **Issue**: WebSocket connections need proper authentication
- **Solution**: Token-based authentication with role-based access control

---

## 8. Success Metrics

- **Functional**: WebSocket connections stable with <100ms latency
- **User Experience**: Interactive dashboard with real-time updates
- **Integration**: Seamless integration with existing Prefect workflows
- **Memory Integration**: 100% of conversational insights ingested to Qdrant and accessible via agent RAG
- **Performance**: Support for 50+ concurrent WebSocket connections
- **Security**: Authenticated access with proper authorization
- **Reliability**: 99.9% WebSocket uptime with automatic reconnection
- **Agent Collaboration**: All agents can access and utilize conversational insights for better narrative generation

---

This PRP provides complete implementation guidance for sophisticated Human-in-the-Loop web interfaces that transform the Narrative Factory into a fully interactive, observable platform for AI-powered narrative generation.