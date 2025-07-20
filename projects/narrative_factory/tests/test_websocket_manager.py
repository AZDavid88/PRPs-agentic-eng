"""Tests for WebSocket manager module."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from src.web.websocket_manager import ConnectionManager, WebSocketSettings


@pytest.fixture
def ws_settings():
    """WebSocket settings fixture."""
    return WebSocketSettings(
        max_connections=100,
        heartbeat_interval=30,
        message_queue_size=1000,
        rate_limit_per_minute=60,
        enable_compression=True
    )


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.send_bytes = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.close = AsyncMock()
    websocket.client = Mock()
    websocket.client.host = "127.0.0.1"
    websocket.client.port = 8000
    return websocket


@pytest.fixture
def connection_manager():
    """Connection manager fixture."""
    return ConnectionManager()


class TestConnectionManager:
    """Test cases for ConnectionManager."""

    def test_connection_manager_init_default(self):
        """Test ConnectionManager initialization with defaults."""
        manager = ConnectionManager()
        assert manager.settings is not None
        assert manager.settings.max_connections == 50
        assert len(manager.active_connections) == 0
        assert len(manager.connection_metadata) == 0

    def test_connection_manager_init_custom_settings(self, ws_settings):
        """Test ConnectionManager initialization with custom settings."""
        manager = ConnectionManager(ws_settings)
        assert manager.settings == ws_settings
        assert manager.settings.max_connections == 100

    @pytest.mark.asyncio
    async def test_connection_manager_connect(self, connection_manager, mock_websocket):
        """Test connecting a WebSocket."""
        user_id = "test_user"
        
        await connection_manager.connect(mock_websocket, user_id)
        
        mock_websocket.accept.assert_called_once()
        assert mock_websocket in connection_manager.active_connections
        assert user_id in connection_manager.connection_metadata
        assert connection_manager.connection_metadata[user_id]["websocket"] == mock_websocket

    @pytest.mark.asyncio
    async def test_connection_manager_connect_with_auth(self, connection_manager, mock_websocket):
        """Test connecting a WebSocket with authentication."""
        user_id = "test_user"
        user_roles = ["admin", "user"]
        
        await connection_manager.connect(mock_websocket, user_id, user_roles)
        
        assert connection_manager.connection_metadata[user_id]["roles"] == user_roles

    @pytest.mark.asyncio
    async def test_connection_manager_disconnect(self, connection_manager, mock_websocket):
        """Test disconnecting a WebSocket."""
        user_id = "test_user"
        
        # First connect
        await connection_manager.connect(mock_websocket, user_id)
        assert len(connection_manager.active_connections) == 1
        
        # Then disconnect
        connection_manager.disconnect(mock_websocket)
        
        assert len(connection_manager.active_connections) == 0
        assert user_id not in connection_manager.connection_metadata

    @pytest.mark.asyncio
    async def test_connection_manager_send_personal_message(self, connection_manager, mock_websocket):
        """Test sending a personal message to a specific user."""
        user_id = "test_user"
        message = "Hello, user!"
        
        await connection_manager.connect(mock_websocket, user_id)
        await connection_manager.send_personal_message(message, user_id)
        
        mock_websocket.send_text.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_connection_manager_send_personal_message_not_connected(self, connection_manager):
        """Test sending a personal message to non-connected user."""
        result = await connection_manager.send_personal_message("Hello", "non_existent_user")
        assert result is False

    @pytest.mark.asyncio
    async def test_connection_manager_send_json_message(self, connection_manager, mock_websocket):
        """Test sending a JSON message."""
        user_id = "test_user"
        data = {"type": "notification", "message": "Hello!"}
        
        await connection_manager.connect(mock_websocket, user_id)
        await connection_manager.send_json_message(data, user_id)
        
        mock_websocket.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self, connection_manager):
        """Test broadcasting a message to all connections."""
        # Setup multiple connections
        websockets = []
        for i in range(3):
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            ws.client = Mock()
            ws.client.host = "127.0.0.1"
            websockets.append(ws)
            await connection_manager.connect(ws, f"user_{i}")
        
        message = "Broadcast message"
        await connection_manager.broadcast(message)
        
        # All connections should receive the message
        for ws in websockets:
            ws.send_text.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_json(self, connection_manager):
        """Test broadcasting a JSON message to all connections."""
        # Setup multiple connections
        websockets = []
        for i in range(3):
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            ws.client = Mock()
            ws.client.host = "127.0.0.1"
            websockets.append(ws)
            await connection_manager.connect(ws, f"user_{i}")
        
        data = {"type": "broadcast", "message": "Hello everyone!"}
        await connection_manager.broadcast_json(data)
        
        # All connections should receive the JSON message
        for ws in websockets:
            ws.send_json.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_to_roles(self, connection_manager):
        """Test broadcasting to specific roles only."""
        # Setup connections with different roles
        admin_ws = Mock(spec=WebSocket)
        admin_ws.accept = AsyncMock()
        admin_ws.send_text = AsyncMock()
        admin_ws.client = Mock()
        admin_ws.client.host = "127.0.0.1"
        
        user_ws = Mock(spec=WebSocket)
        user_ws.accept = AsyncMock()
        user_ws.send_text = AsyncMock()
        user_ws.client = Mock()
        user_ws.client.host = "127.0.0.1"
        
        await connection_manager.connect(admin_ws, "admin_user", ["admin"])
        await connection_manager.connect(user_ws, "regular_user", ["user"])
        
        # Broadcast to admin only
        await connection_manager.broadcast_to_roles("Admin message", ["admin"])
        
        admin_ws.send_text.assert_called_once_with("Admin message")
        user_ws.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_manager_send_error_handling(self, connection_manager, mock_websocket):
        """Test error handling when sending messages."""
        user_id = "test_user"
        
        await connection_manager.connect(mock_websocket, user_id)
        
        # Mock send_text to raise an exception
        mock_websocket.send_text.side_effect = Exception("Connection error")
        
        result = await connection_manager.send_personal_message("Test message", user_id)
        
        # Should handle error gracefully and return False
        assert result is False
        # Connection should be removed after error
        assert len(connection_manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_connection_manager_max_connections_limit(self, connection_manager):
        """Test maximum connections limit."""
        # Set a low max connections limit
        connection_manager.settings.max_connections = 2
        
        # Connect up to the limit
        for i in range(2):
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.client = Mock()
            ws.client.host = "127.0.0.1"
            await connection_manager.connect(ws, f"user_{i}")
        
        # Try to connect one more (should be rejected)
        extra_ws = Mock(spec=WebSocket)
        extra_ws.accept = AsyncMock()
        extra_ws.close = AsyncMock()
        extra_ws.client = Mock()
        extra_ws.client.host = "127.0.0.1"
        
        with pytest.raises(Exception):  # Should raise connection limit error
            await connection_manager.connect(extra_ws, "extra_user")

    def test_connection_manager_get_connection_count(self, connection_manager):
        """Test getting connection count."""
        assert connection_manager.get_connection_count() == 0
        
        # Add some mock connections
        for i in range(3):
            connection_manager.active_connections.append(Mock())
            connection_manager.connection_metadata[f"user_{i}"] = {"websocket": Mock()}
        
        assert connection_manager.get_connection_count() == 3

    def test_connection_manager_get_connected_users(self, connection_manager):
        """Test getting list of connected users."""
        # Add some mock connections
        for i in range(3):
            connection_manager.connection_metadata[f"user_{i}"] = {
                "websocket": Mock(),
                "roles": ["user"],
                "connected_at": "2023-01-01T00:00:00"
            }
        
        users = connection_manager.get_connected_users()
        assert len(users) == 3
        assert "user_0" in users
        assert "user_1" in users
        assert "user_2" in users

    def test_connection_manager_get_user_by_websocket(self, connection_manager, mock_websocket):
        """Test getting user ID by WebSocket connection."""
        user_id = "test_user"
        connection_manager.connection_metadata[user_id] = {
            "websocket": mock_websocket,
            "roles": ["user"]
        }
        connection_manager.active_connections.append(mock_websocket)
        
        found_user = connection_manager.get_user_by_websocket(mock_websocket)
        assert found_user == user_id

    def test_connection_manager_get_user_by_websocket_not_found(self, connection_manager):
        """Test getting user ID by WebSocket when not found."""
        unknown_ws = Mock()
        found_user = connection_manager.get_user_by_websocket(unknown_ws)
        assert found_user is None

    @pytest.mark.asyncio
    async def test_connection_manager_heartbeat(self, connection_manager, mock_websocket):
        """Test heartbeat functionality."""
        user_id = "test_user"
        
        await connection_manager.connect(mock_websocket, user_id)
        
        # Send heartbeat
        await connection_manager.send_heartbeat(user_id)
        
        # Should send heartbeat message
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "heartbeat"

    @pytest.mark.asyncio
    async def test_connection_manager_start_heartbeat_task(self, connection_manager):
        """Test starting heartbeat task."""
        with patch('asyncio.create_task') as mock_create_task:
            connection_manager.start_heartbeat_task()
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_manager_stop_heartbeat_task(self, connection_manager):
        """Test stopping heartbeat task."""
        # Mock running task
        mock_task = Mock()
        mock_task.cancel = Mock()
        connection_manager._heartbeat_task = mock_task
        
        connection_manager.stop_heartbeat_task()
        mock_task.cancel.assert_called_once()

    def test_connection_manager_rate_limiting(self, connection_manager, mock_websocket):
        """Test rate limiting functionality."""
        user_id = "test_user"
        
        # Initialize rate limit tracking
        connection_manager._init_rate_limiting(user_id)
        
        # Check if user is rate limited (should start as False)
        assert not connection_manager.is_rate_limited(user_id)
        
        # Simulate many messages
        for _ in range(connection_manager.settings.rate_limit_per_minute + 1):
            connection_manager._record_message(user_id)
        
        # Should now be rate limited
        assert connection_manager.is_rate_limited(user_id)

    def test_connection_manager_get_connection_stats(self, connection_manager):
        """Test getting connection statistics."""
        # Add some mock connections
        for i in range(3):
            connection_manager.connection_metadata[f"user_{i}"] = {
                "websocket": Mock(),
                "roles": ["user"],
                "connected_at": "2023-01-01T00:00:00",
                "messages_sent": i * 10,
                "messages_received": i * 5
            }
            connection_manager.active_connections.append(Mock())
        
        stats = connection_manager.get_connection_stats()
        
        assert stats["total_connections"] == 3
        assert stats["active_connections"] == 3
        assert "uptime" in stats
        assert "total_messages_sent" in stats
        assert "total_messages_received" in stats

    @pytest.mark.asyncio
    async def test_connection_manager_cleanup_stale_connections(self, connection_manager):
        """Test cleaning up stale connections."""
        # Add some mock stale connections
        stale_ws = Mock(spec=WebSocket)
        stale_ws.client_state = Mock()
        stale_ws.client_state.value = 3  # DISCONNECTED state
        
        connection_manager.active_connections.append(stale_ws)
        connection_manager.connection_metadata["stale_user"] = {
            "websocket": stale_ws,
            "roles": ["user"]
        }
        
        await connection_manager.cleanup_stale_connections()
        
        # Stale connection should be removed
        assert len(connection_manager.active_connections) == 0
        assert "stale_user" not in connection_manager.connection_metadata


def test_websocket_settings_validation():
    """Test WebSocketSettings validation."""
    # Valid settings
    settings = WebSocketSettings(
        max_connections=200,
        heartbeat_interval=60,
        message_queue_size=2000,
        rate_limit_per_minute=120,
        enable_compression=False
    )
    assert settings.max_connections == 200
    assert settings.heartbeat_interval == 60
    assert settings.message_queue_size == 2000
    assert settings.rate_limit_per_minute == 120
    assert settings.enable_compression is False
    
    # Test default values
    default_settings = WebSocketSettings()
    assert default_settings.max_connections == 50
    assert default_settings.heartbeat_interval == 30
    assert default_settings.message_queue_size == 1000
    assert default_settings.rate_limit_per_minute == 60
    assert default_settings.enable_compression is True


@pytest.mark.asyncio
async def test_connection_manager_integration_scenario(connection_manager):
    """Test a complete integration scenario."""
    # Create multiple mock WebSocket connections
    users = []
    websockets = []
    
    for i in range(3):
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        ws.client = Mock()
        ws.client.host = "127.0.0.1"
        
        user_id = f"user_{i}"
        roles = ["admin"] if i == 0 else ["user"]
        
        websockets.append(ws)
        users.append(user_id)
        
        await connection_manager.connect(ws, user_id, roles)
    
    # Test broadcast to all
    await connection_manager.broadcast("Hello everyone!")
    for ws in websockets:
        ws.send_text.assert_called_with("Hello everyone!")
    
    # Test role-based broadcast
    for ws in websockets:
        ws.send_text.reset_mock()
    
    await connection_manager.broadcast_to_roles("Admin only", ["admin"])
    websockets[0].send_text.assert_called_once_with("Admin only")
    websockets[1].send_text.assert_not_called()
    websockets[2].send_text.assert_not_called()
    
    # Test personal message
    await connection_manager.send_personal_message("Personal message", "user_1")
    websockets[1].send_text.assert_called_once_with("Personal message")
    
    # Test disconnection
    connection_manager.disconnect(websockets[0])
    assert len(connection_manager.active_connections) == 2
    assert "user_0" not in connection_manager.connection_metadata
    
    # Verify stats
    stats = connection_manager.get_connection_stats()
    assert stats["total_connections"] == 2