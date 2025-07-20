"""
WebSocket Connection Management for Narrative Factory T03 HITL Interfaces.

Provides centralized WebSocket connection management with subscription-based routing,
authentication, rate limiting, and automatic cleanup of dead connections.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from collections import defaultdict, deque

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, validator

from src.logger import get_logger

logger = get_logger(__name__)

class WebSocketMessage(BaseModel):
    """Standardized WebSocket message format with validation."""
    
    type: str
    timestamp: str
    data: Dict[str, Any]
    source: Optional[str] = None
    subscription_type: Optional[str] = None
    
    @validator('type')
    def validate_message_type(cls, v):
        allowed_types = {
            'agent_update', 'workflow_update', 'system_status', 'error',
            'agent_execution_started', 'agent_thinking', 'agent_execution_completed',
            'agent_execution_failed', 'job_created', 'job_pending_approval',
            'authenticate', 'subscribe', 'unsubscribe', 'ping', 'pong'
        }
        if v not in allowed_types:
            raise ValueError(f"Invalid message type: {v}")
        return v
    
    @validator('data')
    def sanitize_data(cls, v):
        """Remove sensitive information from data payload."""
        if isinstance(v, dict):
            # Remove sensitive keys
            sensitive_keys = {'api_key', 'password', 'secret', 'token', 'private_key'}
            cleaned = {}
            for key, value in v.items():
                if key.lower() not in sensitive_keys:
                    if isinstance(value, str) and len(value) > 10000:  # Truncate large strings
                        cleaned[key] = value[:10000] + "... [truncated]"
                    else:
                        cleaned[key] = value
            return cleaned
        return v

@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    websocket: WebSocket
    user_id: str
    subscription_types: Set[str]
    connected_at: datetime
    last_heartbeat: datetime
    message_count: int = 0
    
class RateLimiter:
    """Rate limiting for WebSocket connections."""
    
    def __init__(self, max_messages: int = 100, time_window: int = 60):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_messages: Dict[str, deque] = defaultdict(deque)
    
    def is_rate_limited(self, user_id: str) -> bool:
        """Check if user is rate limited."""
        now = datetime.now()
        user_queue = self.user_messages[user_id]
        
        # Remove old messages outside time window
        while user_queue and (now - user_queue[0]).total_seconds() > self.time_window:
            user_queue.popleft()
        
        # Check if user exceeds rate limit
        if len(user_queue) >= self.max_messages:
            return True
        
        # Add current message
        user_queue.append(now)
        return False

class ConnectionManager:
    """Centralized WebSocket connection management with security and performance features."""
    
    def __init__(self):
        self.connections: Dict[WebSocket, ConnectionInfo] = {}
        self.subscriptions: Dict[str, List[WebSocket]] = defaultdict(list)
        self.user_connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self.message_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.rate_limiter = RateLimiter()
        self.max_connections_per_user = 5
        self.heartbeat_interval = 30  # seconds
        self._cleanup_task_handle = None
        
        logger.info("WebSocket ConnectionManager initialized")
    
    async def start_cleanup_task(self):
        """Start the background cleanup task if not already running."""
        if self._cleanup_task_handle is None or self._cleanup_task_handle.done():
            try:
                self._cleanup_task_handle = asyncio.create_task(self._cleanup_task())
                logger.info("WebSocket cleanup task started")
            except Exception as e:
                logger.error(f"Failed to start cleanup task: {e}")
    
    async def connect(self, websocket: WebSocket, user_id: str) -> bool:
        """
        Accept WebSocket connection with user authentication and limits.
        
        Args:
            websocket: FastAPI WebSocket instance
            user_id: Authenticated user identifier
            
        Returns:
            bool: True if connection accepted, False if rejected
        """
        try:
            # Check connection limits
            if len(self.user_connections[user_id]) >= self.max_connections_per_user:
                await websocket.close(code=1008, reason="Connection limit exceeded")
                logger.warning(f"Connection limit exceeded for user {user_id}")
                return False
            
            await websocket.accept()
            
            # Create connection info
            connection_info = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
                subscription_types=set(),
                connected_at=datetime.now(),
                last_heartbeat=datetime.now()
            )
            
            # Register connection
            self.connections[websocket] = connection_info
            self.user_connections[user_id].append(websocket)
            
            # Start cleanup task on first connection
            if len(self.connections) == 1:
                await self.start_cleanup_task()
            
            logger.info(f"WebSocket connected: user={user_id}, total_connections={len(self.connections)}")
            
            # Send any queued messages
            await self._send_queued_messages(user_id, websocket)
            
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed for user {user_id}: {e}")
            return False
    
    def disconnect(self, websocket: WebSocket):
        """Clean up WebSocket connection and all associated data."""
        try:
            if websocket not in self.connections:
                return
            
            connection_info = self.connections[websocket]
            user_id = connection_info.user_id
            
            # Remove from all subscriptions
            for subscription_type in connection_info.subscription_types:
                if websocket in self.subscriptions[subscription_type]:
                    self.subscriptions[subscription_type].remove(websocket)
            
            # Remove from user connections
            if websocket in self.user_connections[user_id]:
                self.user_connections[user_id].remove(websocket)
            
            # Remove connection info
            del self.connections[websocket]
            
            logger.info(f"WebSocket disconnected: user={user_id}, remaining_connections={len(self.connections)}")
            
        except Exception as e:
            logger.error(f"WebSocket disconnect cleanup failed: {e}")
    
    async def subscribe(self, websocket: WebSocket, subscription_type: str) -> bool:
        """Subscribe WebSocket to specific message type."""
        try:
            if websocket not in self.connections:
                return False
            
            connection_info = self.connections[websocket]
            
            # Add to subscription
            if websocket not in self.subscriptions[subscription_type]:
                self.subscriptions[subscription_type].append(websocket)
                connection_info.subscription_types.add(subscription_type)
            
            logger.debug(f"User {connection_info.user_id} subscribed to {subscription_type}")
            return True
            
        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return False
    
    async def unsubscribe(self, websocket: WebSocket, subscription_type: str) -> bool:
        """Unsubscribe WebSocket from specific message type."""
        try:
            if websocket not in self.connections:
                return False
            
            connection_info = self.connections[websocket]
            
            # Remove from subscription
            if websocket in self.subscriptions[subscription_type]:
                self.subscriptions[subscription_type].remove(websocket)
                connection_info.subscription_types.discard(subscription_type)
            
            logger.debug(f"User {connection_info.user_id} unsubscribed from {subscription_type}")
            return True
            
        except Exception as e:
            logger.error(f"Unsubscription failed: {e}")
            return False
    
    async def broadcast_to_subscription(self, subscription_type: str, message: WebSocketMessage):
        """Broadcast message to all subscribers with automatic cleanup of dead connections."""
        if subscription_type not in self.subscriptions:
            return
        
        dead_connections = []
        message_json = message.json()
        subscribers = self.subscriptions[subscription_type].copy()  # Avoid modification during iteration
        
        for websocket in subscribers:
            try:
                if websocket in self.connections:
                    connection_info = self.connections[websocket]
                    
                    # Check rate limiting
                    if self.rate_limiter.is_rate_limited(connection_info.user_id):
                        logger.warning(f"Rate limited user {connection_info.user_id}")
                        continue
                    
                    await websocket.send_text(message_json)
                    connection_info.last_heartbeat = datetime.now()
                    connection_info.message_count += 1
                    
            except (WebSocketDisconnect, ConnectionError, RuntimeError) as e:
                logger.debug(f"Dead connection detected during broadcast: {e}")
                dead_connections.append(websocket)
            except Exception as e:
                logger.error(f"Unexpected error during broadcast: {e}")
                dead_connections.append(websocket)
        
        # Clean up dead connections
        for dead_connection in dead_connections:
            self.disconnect(dead_connection)
        
        if dead_connections:
            logger.info(f"Cleaned up {len(dead_connections)} dead connections")
    
    async def send_personal_message(self, websocket: WebSocket, message: WebSocketMessage):
        """Send message to specific WebSocket connection."""
        try:
            if websocket in self.connections:
                await websocket.send_text(message.json())
                self.connections[websocket].last_heartbeat = datetime.now()
                self.connections[websocket].message_count += 1
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)
    
    async def queue_message_for_user(self, user_id: str, message: WebSocketMessage):
        """Queue message for user if they're disconnected."""
        self.message_queues[user_id].append(message)
        logger.debug(f"Queued message for user {user_id}, queue size: {len(self.message_queues[user_id])}")
    
    async def _send_queued_messages(self, user_id: str, websocket: WebSocket):
        """Send queued messages to reconnected user."""
        queue = self.message_queues[user_id]
        while queue:
            try:
                message = queue.popleft()
                await websocket.send_text(message.json())
            except Exception as e:
                logger.error(f"Failed to send queued message: {e}")
                break
    
    async def _cleanup_task(self):
        """Background task to clean up stale connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                stale_connections = []
                now = datetime.now()
                stale_threshold = timedelta(seconds=self.heartbeat_interval * 3)
                
                for websocket, connection_info in self.connections.items():
                    if now - connection_info.last_heartbeat > stale_threshold:
                        stale_connections.append(websocket)
                
                for stale_connection in stale_connections:
                    logger.info("Cleaning up stale connection")
                    self.disconnect(stale_connection)
                    
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "subscriptions": {k: len(v) for k, v in self.subscriptions.items()},
            "users_connected": len([ucs for ucs in self.user_connections.values() if ucs]),
            "message_queues": {k: len(v) for k, v in self.message_queues.items() if v}
        }

# Global connection manager instance
connection_manager = ConnectionManager()