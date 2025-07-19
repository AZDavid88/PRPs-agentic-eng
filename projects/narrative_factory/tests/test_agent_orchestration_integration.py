"""
Comprehensive integration tests for Phase 2B Agent Orchestration.

Tests the complete agent orchestration system including:
- Agent lifecycle management
- Communication protocols
- CLI agent mode
- Workflow integration
- Session management
"""

import asyncio
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.communication import (
    AgentCommunicationService,
    MaterialAnalysisRequestMessage,
    MessageMetadata,
    MessageType,
)
from src.agents.orchestration import AgentOrchestrationService
from src.models.librarian_models import MaterialAnalysisRequest, MaterialAnalysisResponse
from src.models.material_models import MaterialClassification
from src.workflows.generation import agent_orchestration_flow, agent_orchestration_task


class TestAgentOrchestrationIntegration:
    """Integration tests for the complete agent orchestration system."""

    @pytest.fixture
    async def orchestration_service(self):
        """Create orchestration service with mocked dependencies."""
        with patch('src.agents.orchestration.get_memory_service') as mock_memory:
            mock_memory.return_value = AsyncMock()
            service = AgentOrchestrationService()
            yield service
            await service.close()

    @pytest.fixture
    async def communication_service(self):
        """Create communication service for testing."""
        service = AgentCommunicationService()
        yield service
        await service.close()

    @pytest.fixture
    def sample_materials(self):
        """Sample material classifications for testing."""
        return [
            MaterialClassification(
                material_id="test_char_01",
                primary_category="character",
                secondary_categories=["plot_element"],
                category_confidence={"character": 0.95, "plot_element": 0.7},
                genre_context="fantasy",
                additional_genres=[],
                complexity_level="medium",
                spoiler_risk="low",
                content_hash="a" * 64,  # Valid SHA256 hex string
                extracted_entities=["Ren", "geomancer"],
                original_content="Character: Ren, a skilled geomancer...",
                processed_chunks=["Character: Ren, a skilled geomancer..."],
                cross_references=[],
                quality_score=0.85,
                processing_notes="Test material for integration testing"
            ),
            MaterialClassification(
                material_id="test_loc_01",
                primary_category="setting",
                secondary_categories=[],
                category_confidence={"setting": 0.9},
                genre_context="fantasy",
                additional_genres=[],
                complexity_level="simple",
                spoiler_risk="low",
                content_hash="b" * 64,  # Valid SHA256 hex string
                extracted_entities=["Ashfall Wastes"],
                original_content="Location: The Ashfall Wastes stretch...",
                processed_chunks=["Location: The Ashfall Wastes stretch..."],
                cross_references=[],
                quality_score=0.9,
                processing_notes="Test location material"
            )
        ]

    @pytest.mark.asyncio
    async def test_agent_lifecycle_integration(self, orchestration_service):
        """Test complete agent lifecycle through orchestration service."""
        # Initialize LibrarianAgent
        agent_id = await orchestration_service.initialize_agent(
            agent_type="librarian",
            client_type="openai",
            session_id="test_session_001"
        )
        
        assert agent_id is not None
        assert agent_id.startswith("librarian_")
        
        # Verify agent is tracked
        status = await orchestration_service.get_orchestration_status()
        assert "librarian" in status["active_agents"]
        assert agent_id in status["active_agents"]["librarian"]
        
        # Shutdown agent
        await orchestration_service.shutdown_agent(agent_id)
        
        # Verify cleanup
        status = await orchestration_service.get_orchestration_status()
        assert agent_id not in status["active_agents"]["librarian"]

    @pytest.mark.asyncio
    async def test_agent_execution_integration(self, orchestration_service, sample_materials):
        """Test agent execution through orchestration service."""
        # Initialize agent
        agent_id = await orchestration_service.initialize_agent(
            agent_type="librarian",
            client_type="openai"
        )
        
        # Mock the agent execution
        with patch.object(orchestration_service, '_create_agent_instance') as mock_create:
            mock_agent = AsyncMock()
            mock_agent.execute.return_value = MaterialAnalysisResponse(
                request_id="test_req_001",
                analysis_results=[],
                successful_count=2,
                failed_count=0,
                processing_time=1.5,
                cross_references_generated=0,
                quality_issues_found=0
            )
            mock_create.return_value = mock_agent
            
            # Execute agent
            result = await orchestration_service.execute_agent(
                agent_id=agent_id,
                request_data={
                    "materials": [mat.model_dump() for mat in sample_materials],
                    "analysis_config": {
                        "analysis_depth": "standard",
                        "enable_cross_references": True,
                        "enable_quality_assessment": True
                    }
                },
                context={"test": "context"}
            )
            
            assert result is not None
            assert isinstance(result, MaterialAnalysisResponse)
            assert result.successful_count == 2
            assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_session_management_integration(self, orchestration_service):
        """Test session management and tracking."""
        session_id = "test_session_002"
        
        # Initialize multiple agents in the same session
        agent1_id = await orchestration_service.initialize_agent(
            agent_type="librarian",
            session_id=session_id
        )
        
        agent2_id = await orchestration_service.initialize_agent(
            agent_type="director",
            session_id=session_id
        )
        
        # Verify session tracking
        status = await orchestration_service.get_orchestration_status()
        session_info = status["session_details"][session_id]
        assert session_info["agents"] == 2
        
        # Shutdown entire session
        await orchestration_service.shutdown_session(session_id)
        
        # Verify session cleanup
        status = await orchestration_service.get_orchestration_status()
        assert session_id not in status["session_details"]

    @pytest.mark.asyncio
    async def test_communication_protocol_integration(self, communication_service, sample_materials):
        """Test agent communication protocol integration."""
        # Create material analysis request message
        analysis_request = MaterialAnalysisRequest(
            classifications=sample_materials,
            analysis_depth="standard",
            enable_cross_references=True,
            enable_quality_assessment=True
        )
        
        metadata = MessageMetadata(
            sender_id="test_sender",
            recipient_id="test_recipient",
            session_id="test_session_003"
        )
        
        # Create message
        message = await communication_service.create_material_analysis_request_message(
            analysis_request=analysis_request,
            sender_id="test_sender",
            recipient_id="test_recipient",
            session_id="test_session_003"
        )
        
        assert message.message_type == MessageType.MATERIAL_ANALYSIS_REQUEST
        assert message.analysis_request == analysis_request
        assert message.metadata.sender_id == "test_sender"
        
        # Send message
        success = await communication_service.send_message(message)
        assert success is True
        
        # Receive message
        received_message = await communication_service.receive_message(timeout=1.0)
        assert received_message is not None
        assert received_message.message_type == MessageType.MATERIAL_ANALYSIS_REQUEST

    @pytest.mark.asyncio
    async def test_workflow_integration(self):
        """Test Prefect workflow integration for agent orchestration."""
        job_id = "test_job_001"
        
        # Mock JobStore
        with patch('src.workflows.generation.JobStore') as mock_job_store_class:
            mock_job_store = MagicMock()
            mock_job_store_class.return_value = mock_job_store
            
            # Mock source job
            mock_job_store.get_job.return_value = {
                "data": {
                    "materials": ["material1", "material2"]
                }
            }
            
            # Mock orchestration service
            with patch('src.agents.orchestration.get_orchestration_service') as mock_orch_service:
                mock_orchestration = AsyncMock()
                mock_orch_service.return_value = mock_orchestration
                
                mock_orchestration.initialize_agent.return_value = "test_agent_001"
                mock_orchestration.execute_agent.return_value = {"result": "success"}
                mock_orchestration.get_orchestration_status.return_value = {
                    "active_agents": {"librarian": []},
                    "active_sessions": 0
                }
                
                # Execute workflow task
                result_job_id = await agent_orchestration_task(
                    job_id=job_id,
                    agent_type="librarian",
                    analysis_depth="standard",
                    session_id="test_session_004",
                    client_type="openai",
                    dry_run=False
                )
                
                assert result_job_id.startswith("agent_orch_")
                
                # Verify orchestration service calls
                mock_orchestration.initialize_agent.assert_called_once()
                mock_orchestration.execute_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_dry_run_workflow_integration(self):
        """Test dry run mode for workflow integration."""
        job_id = "test_job_002"
        
        with patch('src.workflows.generation.JobStore') as mock_job_store_class:
            mock_job_store = MagicMock()
            mock_job_store_class.return_value = mock_job_store
            
            # Mock source job exists
            mock_job_store.get_job.return_value = {"data": {"materials": ["test"]}}
            
            # Execute dry run
            result_job_id = await agent_orchestration_task(
                job_id=job_id,
                agent_type="librarian",
                dry_run=True
            )
            
            assert result_job_id.startswith("agent_orch_")
            
            # Verify job was marked as pending
            mock_job_store.update_job_as_pending.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_flow_integration(self):
        """Test complete agent orchestration flow."""
        job_id = "test_job_003"
        
        with patch('src.workflows.generation.agent_orchestration_task') as mock_task:
            mock_task.return_value = "orch_job_123"
            
            # Execute flow
            result = await agent_orchestration_flow(
                job_id=job_id,
                agent_type="librarian",
                analysis_depth="comprehensive",
                session_id="test_session_005",
                client_type="gemini",
                timeout_minutes=10,
                save_session=True,
                dry_run=False
            )
            
            assert result == "orch_job_123"
            
            # Verify task was called with correct parameters
            mock_task.assert_called_once_with(
                job_id=job_id,
                agent_type="librarian",
                analysis_depth="comprehensive",
                session_id="test_session_005",
                client_type="gemini",
                timeout_minutes=10,
                save_session=True,
                dry_run=False
            )

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, orchestration_service):
        """Test error handling throughout the orchestration system."""
        # Test agent initialization error
        with patch.object(orchestration_service, '_create_agent_instance') as mock_create:
            mock_create.side_effect = Exception("Agent creation failed")
            
            with pytest.raises(Exception) as exc_info:
                await orchestration_service.initialize_agent(
                    agent_type="invalid_agent",
                    client_type="openai"
                )
            
            assert "Agent creation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_agent_cleanup_on_failure(self, orchestration_service):
        """Test agent cleanup when execution fails."""
        # Initialize agent
        agent_id = await orchestration_service.initialize_agent(
            agent_type="librarian",
            client_type="openai"
        )
        
        # Mock execution failure
        with patch.object(orchestration_service, '_create_agent_instance') as mock_create:
            mock_agent = AsyncMock()
            mock_agent.execute.side_effect = Exception("Execution failed")
            mock_create.return_value = mock_agent
            
            # Attempt execution
            with pytest.raises(Exception):
                await orchestration_service.execute_agent(
                    agent_id=agent_id,
                    request_data={"test": "data"}
                )
            
            # Agent should still be tracked (cleanup is manual)
            status = await orchestration_service.get_orchestration_status()
            assert agent_id in status["active_agents"]["librarian"]

    @pytest.mark.asyncio
    async def test_concurrent_agent_management(self, orchestration_service):
        """Test managing multiple agents concurrently."""
        agent_ids = []
        
        # Initialize multiple agents concurrently
        tasks = [
            orchestration_service.initialize_agent(
                agent_type="librarian",
                agent_id=f"test_agent_{i}",
                client_type="openai"
            )
            for i in range(3)
        ]
        
        agent_ids = await asyncio.gather(*tasks)
        
        # Verify all agents were created
        assert len(agent_ids) == 3
        assert all(agent_id.startswith("test_agent_") for agent_id in agent_ids)
        
        # Verify tracking
        status = await orchestration_service.get_orchestration_status()
        for agent_id in agent_ids:
            assert agent_id in status["active_agents"]["librarian"]
        
        # Cleanup all agents
        cleanup_tasks = [
            orchestration_service.shutdown_agent(agent_id)
            for agent_id in agent_ids
        ]
        
        await asyncio.gather(*cleanup_tasks)

    @pytest.mark.asyncio
    async def test_message_validation_integration(self, communication_service):
        """Test message validation in communication service."""
        # Test invalid message (missing required fields)
        metadata = MessageMetadata(
            sender_id="",  # Invalid: empty sender_id
            recipient_id="test_recipient"
        )
        
        # Create analysis request
        analysis_request = MaterialAnalysisRequest(
            classifications=[],
            analysis_depth="standard"
        )
        
        # This should fail validation
        with pytest.raises(Exception):
            message = MaterialAnalysisRequestMessage(
                analysis_request=analysis_request,
                metadata=metadata
            )
            await communication_service.send_message(message)

    @pytest.mark.asyncio
    async def test_orchestration_status_reporting(self, orchestration_service):
        """Test comprehensive status reporting."""
        session_id = "status_test_session"
        
        # Initialize agents in different states
        agent1 = await orchestration_service.initialize_agent(
            agent_type="librarian",
            session_id=session_id
        )
        
        agent2 = await orchestration_service.initialize_agent(
            agent_type="director",
            session_id=session_id
        )
        
        # Get status
        status = await orchestration_service.get_orchestration_status()
        
        # Verify comprehensive status
        assert "active_agents" in status
        assert "active_sessions" in status
        assert "session_details" in status
        assert "registry_stats" in status
        assert "memory_service" in status
        
        # Verify session details
        assert session_id in status["session_details"]
        session_info = status["session_details"][session_id]
        assert session_info["agents"] == 2
        assert "duration" in session_info


class TestPhase2BValidation:
    """Validation tests for Phase 2B completion criteria."""

    @pytest.mark.asyncio
    async def test_librarian_agent_registration(self):
        """Test that LibrarianAgent is properly registered in orchestration."""
        with patch('src.agents.orchestration.get_memory_service') as mock_memory:
            mock_memory.return_value = AsyncMock()
            service = AgentOrchestrationService()
            
            # Verify LibrarianAgent is in tracking
            assert "librarian" in service._active_agents
            
            # Test agent creation
            with patch.object(service, '_create_agent_instance') as mock_create:
                mock_create.return_value = AsyncMock()
                
                agent_id = await service.initialize_agent(
                    agent_type="librarian",
                    client_type="openai"
                )
                
                # Verify creation was called correctly
                mock_create.assert_called_once_with(
                    "librarian", "openai", service.memory_service
                )

    def test_communication_message_types_available(self):
        """Test that all required message types are available."""
        # Verify new message types exist
        assert hasattr(MessageType, 'MATERIAL_ANALYSIS_REQUEST')
        assert hasattr(MessageType, 'MATERIAL_ANALYSIS_RESPONSE') 
        assert hasattr(MessageType, 'LIBRARIAN_QUERY')
        
        # Test message type values
        assert MessageType.MATERIAL_ANALYSIS_REQUEST == "material_analysis_request"
        assert MessageType.MATERIAL_ANALYSIS_RESPONSE == "material_analysis_response"
        assert MessageType.LIBRARIAN_QUERY == "librarian_query"

    @pytest.mark.asyncio
    async def test_workflow_integration_available(self):
        """Test that workflow integration functions are available."""
        # Test imports work
        from src.workflows.generation import agent_orchestration_task, agent_orchestration_flow
        
        # Verify functions are callable
        assert callable(agent_orchestration_task)
        assert callable(agent_orchestration_flow)

    def test_cli_commands_integration(self):
        """Test that CLI commands are properly integrated."""
        import inspect
        import src.cli.commands
        
        # Get all functions in the CLI module
        all_functions = inspect.getmembers(src.cli.commands, inspect.isfunction)
        function_names = [name for name, _ in all_functions]
        
        # Verify agent commands exist
        assert "agent_analyze_materials" in function_names
        assert "agent_session_management" in function_names

    @pytest.mark.asyncio
    async def test_phase_2b_integration_completeness(self):
        """Comprehensive test that Phase 2B integration is complete."""
        # Test orchestration service
        with patch('src.agents.orchestration.get_memory_service') as mock_memory:
            mock_memory.return_value = AsyncMock()
            orchestration = AgentOrchestrationService()
            
            # Test communication service
            communication = AgentCommunicationService()
            
            # Test workflow integration
            from src.workflows.generation import agent_orchestration_flow
            
            # All components should be importable and functional
            assert orchestration is not None
            assert communication is not None
            assert agent_orchestration_flow is not None
            
            # Cleanup
            await orchestration.close()
            await communication.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])