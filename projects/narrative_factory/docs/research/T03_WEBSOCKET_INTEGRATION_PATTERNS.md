# T03 WebSocket Integration Patterns Research

**Research Date:** 2025-07-20  
**Context:** T03 HITL Web Interfaces Implementation - COMPLETED ✅  
**Status:** Implementation complete - patterns validated in production code  
**Sources:** Context7 analysis of production WebSocket libraries

## FastAPI WebSocket RPC Foundation

### Core Architecture Pattern

Based on `fastapi_websocket_rpc` (Trust Score: 9.4), production WebSocket integration follows these patterns:

```python
# Server-side WebSocket RPC endpoint
from fastapi import FastAPI
from fastapi_websocket_rpc import RpcMethodsBase, WebsocketRPCEndpoint

class NarrativeAgentServer(RpcMethodsBase):
    async def stream_agent_update(self, agent_name="", update_type="", data={}):
        """Broadcast agent execution updates to connected clients"""
        return {"status": "broadcast", "agent": agent_name, "data": data}
    
    async def get_dashboard_status(self):
        """Return real-time dashboard metrics"""
        return await self._collect_system_metrics()

# FastAPI app integration
app = FastAPI()
endpoint = WebsocketRPCEndpoint(NarrativeAgentServer())
endpoint.register_route(app, "/ws/agents")
```

**Key Benefits:**
- **Structured RPC Protocol** - Type-safe method calls over WebSocket
- **Built-in Connection Management** - Automatic reconnection and error handling
- **FastAPI Integration** - Native ASGI support with dependency injection

### Connection Management Best Practices

```python
# Connection lifecycle with proper cleanup
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, List[WebSocket]] = {
            "agents": [],
            "workflows": [], 
            "system": []
        }
        
    async def connect(self, websocket: WebSocket, subscription_type: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[subscription_type].append(websocket)
        
    async def broadcast_to_subscription(self, subscription_type: str, message: dict):
        """Broadcast with automatic dead connection cleanup"""
        dead_connections = []
        for websocket in self.subscriptions[subscription_type]:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for dead_connection in dead_connections:
            self.disconnect(dead_connection)
```

## React Frontend WebSocket Integration

### Real-time Dashboard Pattern

Based on `react-use-websocket` (Trust Score: 8.7), frontend WebSocket integration uses:

```javascript
// Dashboard component with WebSocket integration
import useWebSocket, { ReadyState } from 'react-use-websocket';

export const NarrativeDashboard = () => {
  const [socketUrl] = useState('ws://localhost:8000/ws/dashboard');
  const [agentStatus, setAgentStatus] = useState({});
  const [messageHistory, setMessageHistory] = useState([]);

  const { sendMessage, lastMessage, readyState } = useWebSocket(socketUrl, {
    onOpen: () => console.log('Dashboard connected'),
    shouldReconnect: (closeEvent) => true,
    reconnectAttempts: 10,
    reconnectInterval: (attemptNumber) => 
      Math.min(Math.pow(2, attemptNumber) * 1000, 10000), // Exponential backoff
    heartbeat: {
      message: 'ping',
      returnMessage: 'pong', 
      timeout: 60000,
      interval: 25000
    }
  });

  useEffect(() => {
    if (lastMessage !== null) {
      const data = JSON.parse(lastMessage.data);
      
      if (data.type === 'agent_update') {
        setAgentStatus(prev => ({
          ...prev,
          [data.agent]: data.data
        }));
      }
      
      setMessageHistory(prev => prev.concat(lastMessage));
    }
  }, [lastMessage]);

  const connectionStatus = {
    [ReadyState.CONNECTING]: 'Connecting',
    [ReadyState.OPEN]: 'Open', 
    [ReadyState.CLOSING]: 'Closing',
    [ReadyState.CLOSED]: 'Closed',
    [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
  }[readyState];

  return (
    <div className="dashboard">
      <div className="connection-status">
        WebSocket: {connectionStatus}
      </div>
      
      <div className="agent-grid">
        {Object.entries(agentStatus).map(([agent, status]) => (
          <AgentCard key={agent} agent={agent} status={status} />
        ))}
      </div>
      
      <div className="message-stream">
        {messageHistory.slice(-10).map((msg, idx) => (
          <MessageItem key={idx} message={msg} />
        ))}
      </div>
    </div>
  );
};
```

### Connection Resilience Patterns

```javascript
// Advanced reconnection with exponential backoff
const useResilientWebSocket = (url, options = {}) => {
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const didUnmount = useRef(false);
  
  const wsOptions = {
    shouldReconnect: (closeEvent) => {
      // Don't reconnect if component unmounted
      return didUnmount.current === false;
    },
    reconnectAttempts: 10,
    reconnectInterval: (attemptNumber) => {
      setReconnectAttempts(attemptNumber);
      // Exponential backoff: 1s, 2s, 4s, 8s, max 10s
      return Math.min(Math.pow(2, attemptNumber) * 1000, 10000);
    },
    onReconnectStop: (numAttempted) => {
      console.warn(`Failed to reconnect after ${numAttempted} attempts`);
    },
    ...options
  };
  
  useEffect(() => {
    return () => {
      didUnmount.current = true;
    };
  }, []);
  
  return useWebSocket(url, wsOptions);
};
```

## Security Considerations

### Authentication & Authorization

```python
# JWT-based WebSocket authentication
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_websocket_token(token: str = Depends(security)):
    """Verify JWT token for WebSocket connections"""
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

@app.websocket("/ws/agents")
async def websocket_agent_endpoint(
    websocket: WebSocket,
    current_user: str = Depends(verify_websocket_token)
):
    await connection_manager.connect(websocket, "agents", current_user)
```

### Rate Limiting & Connection Management

```python
# Connection rate limiting
class RateLimitedConnectionManager(ConnectionManager):
    def __init__(self):
        super().__init__()
        self.connection_counts: Dict[str, int] = {}
        self.max_connections_per_user = 5
        
    async def connect(self, websocket: WebSocket, subscription_type: str, user_id: str):
        # Check connection limits
        user_connections = self.connection_counts.get(user_id, 0)
        if user_connections >= self.max_connections_per_user:
            await websocket.close(code=1008, reason="Connection limit exceeded")
            return False
            
        await super().connect(websocket, subscription_type)
        self.connection_counts[user_id] = user_connections + 1
        return True
```

## Performance Optimization

### Message Batching & Throttling

```python
# Batch messages to prevent WebSocket flooding
class ThrottledBroadcaster:
    def __init__(self, batch_size=10, flush_interval=100):  # 100ms
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.message_queues: Dict[str, List[dict]] = {}
        
    async def queue_message(self, subscription_type: str, message: dict):
        if subscription_type not in self.message_queues:
            self.message_queues[subscription_type] = []
            
        self.message_queues[subscription_type].append(message)
        
        # Flush if batch size reached
        if len(self.message_queues[subscription_type]) >= self.batch_size:
            await self._flush_queue(subscription_type)
            
    async def _flush_queue(self, subscription_type: str):
        """Flush queued messages as batch"""
        if not self.message_queues.get(subscription_type):
            return
            
        batch = self.message_queues[subscription_type]
        self.message_queues[subscription_type] = []
        
        await connection_manager.broadcast_to_subscription(
            subscription_type, 
            {"type": "batch", "messages": batch}
        )
```

## Integration with Existing Narrative Factory

### Enhance Existing Agents with Streaming

```python
# Extend existing agent personas with WebSocket streaming
from src.agents.enhanced_personas import DirectorAgent
from src.web.websocket_manager import connection_manager

class StreamingDirectorAgent(DirectorAgent):
    async def execute_with_streaming(self, task_description: str, **kwargs):
        """Execute with real-time progress streaming"""
        
        # Notify execution start
        await connection_manager.broadcast_to_subscription("agents", {
            "type": "agent_execution_started",
            "agent": "director",
            "task": task_description,
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            # Stream thinking process
            await connection_manager.broadcast_to_subscription("agents", {
                "type": "agent_thinking", 
                "agent": "director",
                "status": "Analyzing narrative requirements..."
            })
            
            # Execute original logic
            result = await super().execute(task_description, **kwargs)
            
            # Stream completion
            await connection_manager.broadcast_to_subscription("agents", {
                "type": "agent_execution_completed",
                "agent": "director",
                "result_preview": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            })
            
            return result
            
        except Exception as e:
            # Stream error
            await connection_manager.broadcast_to_subscription("agents", {
                "type": "agent_execution_failed",
                "agent": "director", 
                "error": str(e)
            })
            raise
```

### JobStore Integration for Approval Workflows

```python
# Enhance existing JobStore with WebSocket notifications
from src.workflows.jobs import JobStore

class StreamingJobStore(JobStore):
    async def create_job(self, agent: str, input_payload: dict) -> str:
        """Create job with WebSocket notification"""
        job_id = await super().create_job(agent, input_payload)
        
        await connection_manager.broadcast_to_subscription("workflows", {
            "type": "job_created",
            "job_id": job_id,
            "agent": agent,
            "status": "pending"
        })
        
        return job_id
        
    async def update_job_as_pending(self, job_id: str, result: dict) -> None:
        """Update job with WebSocket notification"""
        await super().update_job_as_pending(job_id, result)
        
        await connection_manager.broadcast_to_subscription("workflows", {
            "type": "job_pending_approval",
            "job_id": job_id,
            "result_preview": self._generate_approval_preview(result)
        })
```

## Implementation Priority

1. **WebSocket Foundation** (Day 1-2)
   - Connection manager with subscription model
   - Basic FastAPI WebSocket endpoints
   - Authentication integration

2. **Agent Streaming** (Day 2-3) 
   - Extend existing agent personas
   - Real-time execution broadcasting
   - Progress and status updates

3. **Dashboard API** (Day 3-4)
   - React dashboard with real-time updates
   - Agent health monitoring
   - System metrics display

4. **Enhanced Approvals** (Day 4-5)
   - Rich approval interface
   - Structured feedback system
   - Integration with existing JobStore

This research provides the technical foundation for production-ready WebSocket integration with the Narrative Factory's existing architecture.