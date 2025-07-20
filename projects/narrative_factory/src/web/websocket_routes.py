"""
FastAPI WebSocket Routes for Narrative Factory T03 HITL Interfaces.

Provides WebSocket endpoints for real-time agent monitoring, workflow updates,
and dashboard functionality with proper authentication and error handling.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.routing import APIRouter

from src.logger import get_logger
from src.web.websocket_manager import connection_manager, WebSocketMessage
from src.web.auth import verify_websocket_token, check_permission
from src.agents.streaming_agents import (
    StreamingDirectorAgent, StreamingTacticianAgent, 
    StreamingWeaverAgent, StreamingCanonistAgent
)

logger = get_logger(__name__)

# Create router for WebSocket routes
websocket_router = APIRouter()

@websocket_router.websocket("/ws/narrative")
async def websocket_narrative_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for narrative factory real-time communication.
    
    Handles authentication, subscription management, and message routing
    for all narrative factory WebSocket communications.
    """
    user_id = None
    
    try:
        # Wait for authentication message
        await websocket.accept()
        
        # Receive initial authentication message
        auth_data = await websocket.receive_text()
        auth_message = json.loads(auth_data)
        
        if auth_message.get("type") != "authenticate":
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        # Verify JWT token
        token = auth_message.get("token")
        if not token:
            await websocket.close(code=1008, reason="Token required")
            return
        
        try:
            user_id = await verify_websocket_token(token)
        except HTTPException:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Connect to connection manager
        if not await connection_manager.connect(websocket, user_id):
            return  # Connection was rejected
        
        # Send authentication success
        auth_response = WebSocketMessage(
            type="authenticate",
            timestamp=datetime.now().isoformat(),
            data={"status": "authenticated", "user_id": user_id}
        )
        await connection_manager.send_personal_message(websocket, auth_response)
        
        # Handle ongoing messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_websocket_message(websocket, user_id, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                error_response = WebSocketMessage(
                    type="error",
                    timestamp=datetime.now().isoformat(),
                    data={"error": "Invalid JSON format"}
                )
                await connection_manager.send_personal_message(websocket, error_response)
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                error_response = WebSocketMessage(
                    type="error",
                    timestamp=datetime.now().isoformat(),
                    data={"error": "Message processing failed"}
                )
                await connection_manager.send_personal_message(websocket, error_response)
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if websocket in connection_manager.connections:
            connection_manager.disconnect(websocket)

async def handle_websocket_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle incoming WebSocket messages from clients."""
    
    message_type = message.get("type")
    
    if message_type == "subscribe":
        await handle_subscribe_message(websocket, user_id, message)
    elif message_type == "unsubscribe":
        await handle_unsubscribe_message(websocket, user_id, message)
    elif message_type == "ping":
        await handle_ping_message(websocket, user_id, message)
    elif message_type == "execute_agent":
        await handle_execute_agent_message(websocket, user_id, message)
    elif message_type == "get_stats":
        await handle_get_stats_message(websocket, user_id, message)
    else:
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": f"Unknown message type: {message_type}"}
        )
        await connection_manager.send_personal_message(websocket, error_response)

async def handle_subscribe_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle subscription requests."""
    
    subscription_type = message.get("subscription")
    if not subscription_type:
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": "Subscription type required"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    # Check permissions
    required_permission = f"read_{subscription_type}"
    if not check_permission(user_id, required_permission):
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": f"Permission denied for {subscription_type}"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    # Subscribe
    success = await connection_manager.subscribe(websocket, subscription_type)
    
    response = WebSocketMessage(
        type="subscribe",
        timestamp=datetime.now().isoformat(),
        data={
            "subscription": subscription_type,
            "status": "subscribed" if success else "failed"
        }
    )
    await connection_manager.send_personal_message(websocket, response)

async def handle_unsubscribe_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle unsubscription requests."""
    
    subscription_type = message.get("subscription")
    if not subscription_type:
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": "Subscription type required"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    success = await connection_manager.unsubscribe(websocket, subscription_type)
    
    response = WebSocketMessage(
        type="unsubscribe",
        timestamp=datetime.now().isoformat(),
        data={
            "subscription": subscription_type,
            "status": "unsubscribed" if success else "failed"
        }
    )
    await connection_manager.send_personal_message(websocket, response)

async def handle_ping_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle ping messages for connection keepalive."""
    
    pong_response = WebSocketMessage(
        type="pong",
        timestamp=datetime.now().isoformat(),
        data={"message": "pong"}
    )
    await connection_manager.send_personal_message(websocket, pong_response)

async def handle_execute_agent_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle agent execution requests (demo functionality)."""
    
    # Check permissions
    if not check_permission(user_id, "write_agents"):
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": "Permission denied for agent execution"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    agent_name = message.get("agent")
    task_description = message.get("task", "Demo task")
    
    # Create appropriate streaming agent
    agent_classes = {
        "director": StreamingDirectorAgent,
        "tactician": StreamingTacticianAgent,
        "weaver": StreamingWeaverAgent,
        "canonist": StreamingCanonistAgent
    }
    
    if agent_name not in agent_classes:
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": f"Unknown agent: {agent_name}"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    try:
        # Execute agent with streaming
        agent = agent_classes[agent_name]()
        
        # Run agent execution in background task to avoid blocking WebSocket
        asyncio.create_task(agent.execute_with_streaming(task_description))
        
        # Send immediate response
        response = WebSocketMessage(
            type="execute_agent",
            timestamp=datetime.now().isoformat(),
            data={
                "agent": agent_name,
                "task": task_description,
                "status": "execution_started"
            }
        )
        await connection_manager.send_personal_message(websocket, response)
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": f"Agent execution failed: {str(e)}"}
        )
        await connection_manager.send_personal_message(websocket, error_response)

async def handle_get_stats_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """Handle stats requests."""
    
    if not check_permission(user_id, "system_admin"):
        error_response = WebSocketMessage(
            type="error",
            timestamp=datetime.now().isoformat(),
            data={"error": "Permission denied for system stats"}
        )
        await connection_manager.send_personal_message(websocket, error_response)
        return
    
    stats = connection_manager.get_stats()
    
    response = WebSocketMessage(
        type="get_stats",
        timestamp=datetime.now().isoformat(),
        data={"stats": stats}
    )
    await connection_manager.send_personal_message(websocket, response)

# Additional WebSocket endpoint for dashboard-specific functionality
@websocket_router.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    """
    Dedicated WebSocket endpoint for dashboard real-time updates.
    
    Provides system metrics, agent health, and workflow status updates
    specifically designed for dashboard interfaces.
    """
    # Implementation similar to main endpoint but focused on dashboard data
    # This could include more frequent system metrics updates
    pass