"""
Streaming Agent Enhancement for Real-time WebSocket Broadcasting.

Provides mixin classes to enhance existing agent personas with WebSocket
streaming capabilities without modifying core agent logic.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Callable, List

from src.logger import get_logger
from src.web.websocket_manager import connection_manager, WebSocketMessage

logger = get_logger(__name__)

class StreamingAgentMixin:
    """
    Mixin to add WebSocket streaming capabilities to existing agents.
    
    This mixin can be combined with any existing agent class to add
    real-time streaming without modifying the original agent logic.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.streaming_enabled = True
        self.agent_name = getattr(self, 'agent_type', self.__class__.__name__.lower())
        
    async def stream_update(self, update_type: str, data: Dict[str, Any]):
        """
        Stream update to WebSocket subscribers.
        
        Args:
            update_type: Type of update (execution_started, thinking, completed, etc.)
            data: Update data to broadcast
        """
        if not self.streaming_enabled:
            return
        
        try:
            message = WebSocketMessage(
                type=f"agent_{update_type}",
                timestamp=datetime.now().isoformat(),
                data={
                    "agent_name": self.agent_name,
                    "update_type": update_type,
                    **data
                },
                source=f"agent_{self.agent_name}",
                subscription_type="agents"
            )
            
            await connection_manager.broadcast_to_subscription("agents", message)
            logger.debug(f"Streamed {update_type} update for agent {self.agent_name}")
            
        except Exception as e:
            logger.error(f"Failed to stream agent update: {e}")
            # Don't raise - streaming failure shouldn't break agent execution
    
    async def execute_with_streaming(self, *args, **kwargs):
        """
        Execute agent task with real-time WebSocket streaming.
        
        This method wraps the original execute method to add streaming
        without modifying the core agent logic.
        """
        task_description = str(args[0]) if args else "Unknown task"
        
        try:
            # Stream execution start
            await self.stream_update("execution_started", {
                "task_description": task_description,
                "parameters": self._sanitize_parameters(kwargs),
                "status": "Agent execution beginning"
            })
            
            # Stream thinking process
            await self.stream_update("thinking", {
                "status": f"Analyzing task: {task_description[:100]}...",
                "stage": "analysis"
            })
            
            # Execute original agent logic
            if hasattr(super(), 'execute'):
                result = await super().execute(*args, **kwargs)
            else:
                # Fallback for agents without execute method
                result = await self._default_execute(*args, **kwargs)
            
            # Stream completion
            await self.stream_update("execution_completed", {
                "result_preview": self._create_result_preview(result),
                "success": True,
                "execution_time": "calculated_in_production"
            })
            
            return result
            
        except Exception as e:
            # Stream error
            await self.stream_update("execution_failed", {
                "error": str(e),
                "error_type": type(e).__name__,
                "task_description": task_description
            })
            
            logger.error(f"Agent {self.agent_name} execution failed: {e}")
            raise
    
    def _sanitize_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive information from parameters."""
        sanitized = {}
        sensitive_keys = {'api_key', 'password', 'secret', 'token'}
        
        for key, value in params.items():
            if key.lower() not in sensitive_keys:
                if isinstance(value, str) and len(value) > 500:
                    sanitized[key] = value[:500] + "... [truncated]"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = "[REDACTED]"
        
        return sanitized
    
    def _create_result_preview(self, result: Any) -> str:
        """Create a safe preview of the result for streaming."""
        try:
            if hasattr(result, 'model_dump'):
                # Pydantic model
                preview = str(result.model_dump())
            elif isinstance(result, dict):
                preview = str(result)
            else:
                preview = str(result)
            
            # Truncate long previews
            if len(preview) > 200:
                preview = preview[:200] + "... [truncated]"
            
            return preview
            
        except Exception as e:
            logger.warning(f"Failed to create result preview: {e}")
            return f"[Result of type {type(result).__name__}]"
    
    async def _default_execute(self, *args, **kwargs):
        """Default execute method for agents without their own execute."""
        await asyncio.sleep(1)  # Simulate processing
        return {"status": "completed", "message": "Default execution completed"}

# Enhanced agent classes that combine streaming with existing personas
try:
    from src.agents.personas import (
        DirectorAgent, TacticianAgent, WeaverAgent, CanonistAgent
    )
    
    class StreamingDirectorAgent(StreamingAgentMixin, DirectorAgent):
        """Director agent with WebSocket streaming capabilities."""
        
        def __init__(self):
            super().__init__()
            self.agent_name = "director"
        
        async def execute_with_streaming(self, *args, **kwargs):
            """Override to add director-specific streaming."""
            await self.stream_update("thinking", {
                "status": "Analyzing narrative structure and requirements",
                "stage": "strategic_planning"
            })
            
            return await super().execute_with_streaming(*args, **kwargs)
    
    class StreamingTacticianAgent(StreamingAgentMixin, TacticianAgent):
        """Tactician agent with WebSocket streaming capabilities."""
        
        def __init__(self):
            super().__init__()
            self.agent_name = "tactician"
        
        async def execute_with_streaming(self, *args, **kwargs):
            """Override to add tactician-specific streaming."""
            await self.stream_update("thinking", {
                "status": "Developing tactical implementation plan",
                "stage": "tactical_planning"
            })
            
            return await super().execute_with_streaming(*args, **kwargs)
    
    class StreamingWeaverAgent(StreamingAgentMixin, WeaverAgent):
        """Weaver agent with WebSocket streaming capabilities."""
        
        def __init__(self):
            super().__init__()
            self.agent_name = "weaver"
        
        async def execute_with_streaming(self, *args, **kwargs):
            """Override to add weaver-specific streaming."""
            await self.stream_update("thinking", {
                "status": "Crafting narrative prose and dialogue",
                "stage": "content_creation"
            })
            
            return await super().execute_with_streaming(*args, **kwargs)
    
    class StreamingCanonistAgent(StreamingAgentMixin, CanonistAgent):
        """Canonist agent with WebSocket streaming capabilities."""
        
        def __init__(self):
            super().__init__()
            self.agent_name = "canonist"
        
        async def execute_with_streaming(self, *args, **kwargs):
            """Override to add canonist-specific streaming."""
            await self.stream_update("thinking", {
                "status": "Validating narrative consistency and canon",
                "stage": "validation"
            })
            
            return await super().execute_with_streaming(*args, **kwargs)

except ImportError as e:
    logger.warning(f"Could not import enhanced personas: {e}")
    
    # Fallback implementations for testing
    class StreamingDirectorAgent(StreamingAgentMixin):
        def __init__(self):
            super().__init__()
            self.agent_name = "director"
    
    class StreamingTacticianAgent(StreamingAgentMixin):
        def __init__(self):
            super().__init__()
            self.agent_name = "tactician"
    
    class StreamingWeaverAgent(StreamingAgentMixin):
        def __init__(self):
            super().__init__()
            self.agent_name = "weaver"
    
    class StreamingCanonistAgent(StreamingAgentMixin):
        def __init__(self):
            super().__init__()
            self.agent_name = "canonist"

def streaming_agent_decorator(agent_class):
    """
    Decorator to add streaming capabilities to any agent class.
    
    Usage:
        @streaming_agent_decorator
        class MyAgent:
            async def execute(self, task):
                return "result"
    """
    class StreamingDecoratedAgent(StreamingAgentMixin, agent_class):
        pass
    
    return StreamingDecoratedAgent