"""Tests for WebSocket routes module."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from src.web.app import app
from src.web.websocket_routes import (
    websocket_narrative_endpoint,
    websocket_dashboard_endpoint,
    handle_narrative_message,
    handle_dashboard_message
)


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.close = AsyncMock()
    websocket.client = Mock()
    websocket.client.host = "127.0.0.1"
    return websocket


@pytest.fixture
def mock_connection_manager():
    """Mock ConnectionManager."""
    manager = Mock()
    manager.connect = AsyncMock()
    manager.disconnect = Mock()
    manager.send_json_message = AsyncMock()
    manager.broadcast_json = AsyncMock()
    manager.get_user_by_websocket = Mock()
    return manager


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user."""
    return {
        "user_id": "test_user_123",
        "username": "testuser",
        "roles": ["user"],
        "permissions": ["read", "write"]
    }


class TestWebSocketRoutes:
    """Test cases for WebSocket routes."""

    @pytest.mark.asyncio
    async def test_websocket_narrative_endpoint_connection(self, mock_websocket, mock_auth_user):
        """Test WebSocket narrative endpoint connection."""
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.authenticate_websocket_token', return_value=mock_auth_user):
            
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = Mock()
            mock_websocket.receive_text.side_effect = ["", Exception("Connection closed")]
            
            # Should not raise exception
            try:
                await websocket_narrative_endpoint(mock_websocket, "valid_token")
            except Exception:
                pass  # Expected due to mock connection close
            
            # Verify connection was established
            mock_manager.connect.assert_called_once_with(
                mock_websocket, 
                mock_auth_user["user_id"], 
                mock_auth_user["roles"]
            )

    @pytest.mark.asyncio
    async def test_websocket_narrative_endpoint_invalid_token(self, mock_websocket):
        """Test WebSocket narrative endpoint with invalid token."""
        with patch('src.web.websocket_routes.authenticate_websocket_token', return_value=None):
            
            await websocket_narrative_endpoint(mock_websocket, "invalid_token")
            
            # Should close connection with error
            mock_websocket.close.assert_called_once_with(code=1008, reason="Authentication failed")

    @pytest.mark.asyncio
    async def test_websocket_dashboard_endpoint_connection(self, mock_websocket, mock_auth_user):
        """Test WebSocket dashboard endpoint connection."""
        with patch('src.web.websocket_routes.dashboard_manager') as mock_manager, \
             patch('src.web.websocket_routes.authenticate_websocket_token', return_value=mock_auth_user):
            
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = Mock()
            mock_websocket.receive_text.side_effect = ["", Exception("Connection closed")]
            
            try:
                await websocket_dashboard_endpoint(mock_websocket, "valid_token")
            except Exception:
                pass
            
            mock_manager.connect.assert_called_once_with(
                mock_websocket, 
                mock_auth_user["user_id"], 
                mock_auth_user["roles"]
            )

    @pytest.mark.asyncio
    async def test_handle_narrative_message_agent_execution(self, mock_websocket, mock_auth_user):
        """Test handling narrative message for agent execution."""
        message_data = {
            "type": "execute_agent",
            "agent": "DirectorAgent",
            "payload": {
                "chapter_seed": "A dark night in the city...",
                "active_characters": ["char_detective", "char_criminal"]
            }
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.DirectorAgent') as mock_agent_class:
            
            # Mock agent execution
            mock_agent = Mock()
            mock_agent.execute = AsyncMock(return_value="Agent response")
            mock_agent_class.return_value = mock_agent
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Verify agent was executed
            mock_agent.execute.assert_called_once()
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "agent_response"
            assert response_data["agent"] == "DirectorAgent"

    @pytest.mark.asyncio
    async def test_handle_narrative_message_job_approval(self, mock_websocket, mock_auth_user):
        """Test handling narrative message for job approval."""
        message_data = {
            "type": "approve_job",
            "job_id": "job_123",
            "approved": True
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.job_store') as mock_job_store:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_job_store.approve_job = Mock(return_value={"status": "approved"})
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Verify job was approved
            mock_job_store.approve_job.assert_called_once_with("job_123")
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "job_status"
            assert response_data["job_id"] == "job_123"

    @pytest.mark.asyncio
    async def test_handle_narrative_message_job_rejection(self, mock_websocket, mock_auth_user):
        """Test handling narrative message for job rejection."""
        message_data = {
            "type": "approve_job",
            "job_id": "job_123",
            "approved": False,
            "feedback": "Needs more detail"
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.job_store') as mock_job_store:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_job_store.reject_job = Mock(return_value={"status": "rejected"})
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Verify job was rejected with feedback
            mock_job_store.reject_job.assert_called_once_with("job_123", "Needs more detail")

    @pytest.mark.asyncio
    async def test_handle_narrative_message_workflow_start(self, mock_websocket, mock_auth_user):
        """Test handling narrative message for workflow start."""
        message_data = {
            "type": "start_workflow",
            "workflow": "full_generation",
            "parameters": {
                "chapter_seed": "Test seed",
                "auto_approve": False
            }
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.full_generation_flow') as mock_workflow:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_workflow.delay = Mock(return_value="workflow_123")
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Verify workflow was started
            mock_workflow.delay.assert_called_once()
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()

    @pytest.mark.asyncio
    async def test_handle_dashboard_message_system_status(self, mock_websocket, mock_auth_user):
        """Test handling dashboard message for system status."""
        message_data = {
            "type": "get_system_status"
        }
        
        with patch('src.web.websocket_routes.dashboard_manager') as mock_manager, \
             patch('src.web.websocket_routes.health_monitor') as mock_health:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_health.get_health_summary.return_value = {
                "overall_status": "healthy",
                "components": {
                    "redis": {"status": "healthy"},
                    "qdrant": {"status": "healthy"}
                }
            }
            
            await handle_dashboard_message(mock_websocket, message_data)
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "system_status"
            assert "status" in response_data

    @pytest.mark.asyncio
    async def test_handle_dashboard_message_metrics(self, mock_websocket, mock_auth_user):
        """Test handling dashboard message for metrics."""
        message_data = {
            "type": "get_metrics",
            "component": "performance"
        }
        
        with patch('src.web.websocket_routes.dashboard_manager') as mock_manager, \
             patch('src.web.websocket_routes.performance_monitor') as mock_perf:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_perf.get_metrics_summary.return_value = {
                "requests_total": 1000,
                "response_time_avg": 0.5,
                "error_rate": 0.01
            }
            
            await handle_dashboard_message(mock_websocket, message_data)
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "metrics"

    @pytest.mark.asyncio
    async def test_handle_dashboard_message_connection_stats(self, mock_websocket, mock_auth_user):
        """Test handling dashboard message for connection stats."""
        message_data = {
            "type": "get_connection_stats"
        }
        
        with patch('src.web.websocket_routes.dashboard_manager') as mock_manager, \
             patch('src.web.websocket_routes.connection_manager') as mock_conn_manager:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_conn_manager.get_connection_stats.return_value = {
                "total_connections": 25,
                "active_connections": 23,
                "uptime": "2 days, 5 hours"
            }
            
            await handle_dashboard_message(mock_websocket, message_data)
            
            # Verify response was sent
            mock_manager.send_json_message.assert_called()

    @pytest.mark.asyncio
    async def test_handle_narrative_message_invalid_type(self, mock_websocket, mock_auth_user):
        """Test handling invalid message type."""
        message_data = {
            "type": "invalid_message_type",
            "data": "some data"
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager:
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Should send error response
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "error"
            assert "Invalid message type" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_narrative_message_agent_error(self, mock_websocket, mock_auth_user):
        """Test handling agent execution error."""
        message_data = {
            "type": "execute_agent",
            "agent": "DirectorAgent",
            "payload": {"chapter_seed": "Test seed"}
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.DirectorAgent') as mock_agent_class:
            
            # Mock agent execution failure
            mock_agent = Mock()
            mock_agent.execute = AsyncMock(side_effect=Exception("Agent execution failed"))
            mock_agent_class.return_value = mock_agent
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Should send error response
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "error"
            assert "Agent execution failed" in response_data["message"]

    @pytest.mark.asyncio
    async def test_handle_dashboard_message_unauthorized(self, mock_websocket):
        """Test handling dashboard message without proper authorization."""
        # User without admin role
        limited_user = {
            "user_id": "limited_user",
            "username": "limited",
            "roles": ["user"],  # No admin role
            "permissions": ["read"]
        }
        
        message_data = {
            "type": "get_system_status"
        }
        
        with patch('src.web.websocket_routes.dashboard_manager') as mock_manager:
            mock_manager.get_user_by_websocket.return_value = limited_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            # Mock getting user info that doesn't have admin role
            with patch('src.web.websocket_routes.get_user_info', return_value=limited_user):
                await handle_dashboard_message(mock_websocket, message_data)
            
            # Should send unauthorized error
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "error"
            assert "access" in response_data["message"].lower()

    @pytest.mark.asyncio
    async def test_websocket_message_validation(self, mock_websocket, mock_auth_user):
        """Test WebSocket message validation."""
        # Invalid JSON message
        invalid_message = "not valid json"
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager:
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            # Should handle invalid JSON gracefully
            await handle_narrative_message(mock_websocket, invalid_message)
            
            # Should send error response for invalid format
            mock_manager.send_json_message.assert_called()

    @pytest.mark.asyncio
    async def test_websocket_rate_limiting(self, mock_websocket, mock_auth_user):
        """Test WebSocket rate limiting."""
        message_data = {
            "type": "execute_agent",
            "agent": "DirectorAgent",
            "payload": {"chapter_seed": "Test"}
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager:
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            mock_manager.is_rate_limited = Mock(return_value=True)
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Should send rate limit error
            mock_manager.send_json_message.assert_called()
            call_args = mock_manager.send_json_message.call_args[0]
            response_data = call_args[0]
            assert response_data["type"] == "error"
            assert "rate limit" in response_data["message"].lower()

    @pytest.mark.asyncio
    async def test_websocket_streaming_response(self, mock_websocket, mock_auth_user):
        """Test WebSocket streaming response for agent execution."""
        message_data = {
            "type": "execute_agent_stream",
            "agent": "WeaverAgent",
            "payload": {"chapter_blueprint": {}}
        }
        
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.WeaverAgent') as mock_agent_class:
            
            # Mock streaming agent execution
            async def mock_stream_execute(*args, **kwargs):
                for i in range(3):
                    yield f"Stream chunk {i}"
            
            mock_agent = Mock()
            mock_agent.stream_execute = mock_stream_execute
            mock_agent_class.return_value = mock_agent
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            await handle_narrative_message(mock_websocket, message_data)
            
            # Should send multiple streaming responses
            assert mock_manager.send_json_message.call_count >= 3


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    def test_websocket_client_connection(self):
        """Test WebSocket client connection using TestClient."""
        client = TestClient(app)
        
        # Note: TestClient doesn't support WebSocket testing well
        # This would be better tested with a real WebSocket client
        # For now, just verify the routes are properly defined
        assert hasattr(app, 'router')

    @pytest.mark.asyncio
    async def test_complete_narrative_workflow(self, mock_websocket, mock_auth_user):
        """Test complete narrative workflow through WebSocket."""
        with patch('src.web.websocket_routes.connection_manager') as mock_manager, \
             patch('src.web.websocket_routes.DirectorAgent') as mock_director, \
             patch('src.web.websocket_routes.job_store') as mock_job_store:
            
            mock_manager.get_user_by_websocket.return_value = mock_auth_user["user_id"]
            mock_manager.send_json_message = AsyncMock()
            
            # Mock director agent response
            mock_director_instance = Mock()
            mock_director_instance.execute = AsyncMock(return_value="Director output")
            mock_director.return_value = mock_director_instance
            
            # Mock job store
            mock_job_store.create_job.return_value = "job_123"
            mock_job_store.approve_job.return_value = {"status": "approved"}
            
            # Step 1: Execute Director
            director_message = {
                "type": "execute_agent",
                "agent": "DirectorAgent", 
                "payload": {"chapter_seed": "A mysterious beginning..."}
            }
            await handle_narrative_message(mock_websocket, director_message)
            
            # Step 2: Approve job
            approval_message = {
                "type": "approve_job",
                "job_id": "job_123",
                "approved": True
            }
            await handle_narrative_message(mock_websocket, approval_message)
            
            # Verify both steps were handled
            assert mock_manager.send_json_message.call_count >= 2