"""
Agent orchestration service for the Narrative Factory.

Provides comprehensive agent lifecycle management, memory service integration,
and coordinated execution of narrative generation workflows.
"""

import asyncio
import uuid
from typing import Any, Optional, Union

from src.agents.lifecycle import (
    AgentContext,
    get_agent_registry,
)
from src.agents.personas import (
    CanonistAgent,
    DirectorAgent,
    TacticianAgent,
    WeaverAgent,
    get_persona_manager,
)
from src.exceptions import BusinessLogicError, ResourceError
from src.logger import get_logger
from src.memory.service import MemoryService, get_memory_service

logger = get_logger(__name__)


class AgentOrchestrationService:
    """
    Orchestrates agent lifecycle, memory service integration, and narrative workflows.
    Provides centralized management of all agent operations with production-ready patterns.
    """

    def __init__(self, memory_service: Optional[MemoryService] = None):
        """
        Initialize the agent orchestration service.

        Args:
            memory_service: Optional memory service instance
        """
        self.memory_service = memory_service or get_memory_service()
        self.agent_registry = get_agent_registry()
        self.persona_manager = get_persona_manager()

        # Track active agents by type
        self._active_agents: dict[str, list[str]] = {
            "director": [],
            "tactician": [],
            "weaver": [],
            "canonist": []
        }

        # Session tracking
        self._active_sessions: dict[str, dict[str, Any]] = {}

        logger.info("Agent orchestration service initialized")

    async def initialize_agent(
        self,
        agent_type: str,
        agent_id: Optional[str] = None,
        client_type: str = "gemini",
        session_id: Optional[str] = None
    ) -> str:
        """
        Initialize and register a new agent with lifecycle management.

        Args:
            agent_type: Type of agent (director, tactician, weaver, canonist)
            agent_id: Optional custom agent ID
            client_type: LLM client type (gemini, openai)
            session_id: Optional session ID for tracking

        Returns:
            Agent ID for reference
        """
        try:
            # Generate unique agent ID if not provided
            if not agent_id:
                agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"

            # Register agent with lifecycle manager
            lifecycle_manager = self.agent_registry.register_agent(agent_id, agent_type)

            # Initialize the agent instance based on type
            agent_instance = await self._create_agent_instance(
                agent_type, client_type, self.memory_service
            )

            # Store agent instance in lifecycle manager
            lifecycle_manager.agent_instance = agent_instance

            # Track active agent
            self._active_agents[agent_type].append(agent_id)

            # Initialize lifecycle manager
            await lifecycle_manager.initialize()

            # Track session if provided
            if session_id:
                if session_id not in self._active_sessions:
                    self._active_sessions[session_id] = {"agents": []}
                self._active_sessions[session_id]["agents"].append(agent_id)

            logger.info(f"Agent {agent_type}:{agent_id} initialized successfully")
            return agent_id

        except Exception as e:
            logger.error(f"Failed to initialize agent {agent_type}:{agent_id}: {e}")
            raise BusinessLogicError(f"Failed to initialize agent {agent_type}: {e}") from e

    async def _create_agent_instance(
        self,
        agent_type: str,
        client_type: str,
        memory_service: MemoryService
    ) -> Union[DirectorAgent, TacticianAgent, WeaverAgent, CanonistAgent]:
        """Create agent instance based on type."""
        agent_classes = {
            "director": DirectorAgent,
            "tactician": TacticianAgent,
            "weaver": WeaverAgent,
            "canonist": CanonistAgent
        }

        if agent_type not in agent_classes:
            raise BusinessLogicError(f"Unknown agent type: {agent_type}")

        agent_class = agent_classes[agent_type]
        return agent_class(client_type=client_type, memory_service=memory_service)

    async def execute_agent(
        self,
        agent_id: str,
        request_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Any:
        """
        Execute an agent with proper lifecycle management and context tracking.

        Args:
            agent_id: ID of the agent to execute
            request_data: Data to pass to the agent
            context: Optional context dictionary
            user_id: Optional user ID for tracking

        Returns:
            Agent execution result
        """
        try:
            # Get agent lifecycle manager
            lifecycle_manager = self.agent_registry.get_agent(agent_id)
            if not lifecycle_manager:
                raise BusinessLogicError(f"Agent {agent_id} not found")

            # Check if agent is available
            if not lifecycle_manager.is_available():
                raise ResourceError(f"Agent {agent_id} is not available")

            # Create agent context
            agent_context = AgentContext(
                agent_id=agent_id,
                agent_type=lifecycle_manager.agent_type,
                request_id=str(uuid.uuid4()),
                user_id=user_id,
                metadata=context or {}
            )

            # Execute with lifecycle management
            async with lifecycle_manager.request_context(agent_context):
                agent_instance = lifecycle_manager.agent_instance

                # Execute agent based on type
                if lifecycle_manager.agent_type == "director":
                    result = await agent_instance.execute(
                        chapter_seed=request_data.get("chapter_seed", ""),
                        context=context
                    )
                elif lifecycle_manager.agent_type == "tactician":
                    result = await agent_instance.execute(
                        strategic_brief=request_data.get("strategic_brief"),
                        context=context
                    )
                elif lifecycle_manager.agent_type == "weaver":
                    result = await agent_instance.execute(
                        chapter_blueprint=request_data.get("chapter_blueprint"),
                        context=context
                    )
                elif lifecycle_manager.agent_type == "canonist":
                    result = await agent_instance.execute(
                        content=request_data.get("content", ""),
                        context=context
                    )
                else:
                    raise BusinessLogicError(f"Unknown agent type: {lifecycle_manager.agent_type}")

                logger.info(f"Agent {agent_id} executed successfully")
                return result

        except Exception as e:
            logger.error(f"Agent {agent_id} execution failed: {e}")
            raise

    async def execute_narrative_pipeline(
        self,
        chapter_seed: str,
        context: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Execute the complete narrative generation pipeline with agent orchestration.

        Args:
            chapter_seed: Initial narrative seed
            context: Optional context dictionary
            session_id: Optional session ID
            user_id: Optional user ID

        Returns:
            Complete narrative generation result
        """
        try:
            # Initialize session if provided
            if session_id:
                self._active_sessions[session_id] = {
                    "agents": [],
                    "pipeline_steps": [],
                    "start_time": asyncio.get_event_loop().time()
                }

            # Step 1: Initialize Director agent
            director_id = await self.initialize_agent(
                agent_type="director",
                session_id=session_id
            )

            # Step 2: Execute Director for strategic brief
            strategic_brief = await self.execute_agent(
                agent_id=director_id,
                request_data={"chapter_seed": chapter_seed},
                context=context,
                user_id=user_id
            )

            if session_id:
                self._active_sessions[session_id]["pipeline_steps"].append("director_complete")

            # Step 3: Initialize Tactician agent
            tactician_id = await self.initialize_agent(
                agent_type="tactician",
                session_id=session_id
            )

            # Step 4: Execute Tactician for chapter blueprint
            chapter_blueprint = await self.execute_agent(
                agent_id=tactician_id,
                request_data={"strategic_brief": strategic_brief},
                context=context,
                user_id=user_id
            )

            if session_id:
                self._active_sessions[session_id]["pipeline_steps"].append("tactician_complete")

            # Step 5: Initialize Weaver agent
            weaver_id = await self.initialize_agent(
                agent_type="weaver",
                session_id=session_id
            )

            # Step 6: Execute Weaver for prose generation
            prose_content = await self.execute_agent(
                agent_id=weaver_id,
                request_data={"chapter_blueprint": chapter_blueprint},
                context=context,
                user_id=user_id
            )

            if session_id:
                self._active_sessions[session_id]["pipeline_steps"].append("weaver_complete")

            # Step 7: Initialize Canonist agent
            canonist_id = await self.initialize_agent(
                agent_type="canonist",
                session_id=session_id
            )

            # Step 8: Execute Canonist for continuity validation
            validation_result = await self.execute_agent(
                agent_id=canonist_id,
                request_data={"content": prose_content},
                context=context,
                user_id=user_id
            )

            if session_id:
                self._active_sessions[session_id]["pipeline_steps"].append("canonist_complete")

            # Compile final result
            result = {
                "chapter_seed": chapter_seed,
                "strategic_brief": strategic_brief,
                "chapter_blueprint": chapter_blueprint,
                "prose_content": prose_content,
                "validation_result": validation_result,
                "agents_used": [director_id, tactician_id, weaver_id, canonist_id],
                "session_id": session_id
            }

            logger.info(f"Narrative pipeline completed successfully for session {session_id}")
            return result

        except Exception as e:
            logger.error(f"Narrative pipeline failed for session {session_id}: {e}")
            raise

    async def shutdown_agent(self, agent_id: str) -> None:
        """
        Gracefully shutdown an agent and clean up resources.

        Args:
            agent_id: ID of the agent to shutdown
        """
        try:
            # Get agent lifecycle manager
            lifecycle_manager = self.agent_registry.get_agent(agent_id)
            if not lifecycle_manager:
                logger.warning(f"Agent {agent_id} not found for shutdown")
                return

            # Remove from active tracking
            agent_type = lifecycle_manager.agent_type
            if agent_id in self._active_agents.get(agent_type, []):
                self._active_agents[agent_type].remove(agent_id)

            # Unregister agent
            await self.agent_registry.unregister_agent(agent_id)

            logger.info(f"Agent {agent_id} shutdown successfully")

        except Exception as e:
            logger.error(f"Failed to shutdown agent {agent_id}: {e}")
            raise

    async def shutdown_session(self, session_id: str) -> None:
        """
        Shutdown all agents in a session.

        Args:
            session_id: ID of the session to shutdown
        """
        try:
            if session_id not in self._active_sessions:
                logger.warning(f"Session {session_id} not found")
                return

            session_info = self._active_sessions[session_id]
            agent_ids = session_info.get("agents", [])

            # Shutdown all agents in the session
            for agent_id in agent_ids:
                await self.shutdown_agent(agent_id)

            # Clean up session
            del self._active_sessions[session_id]

            logger.info(f"Session {session_id} shutdown successfully")

        except Exception as e:
            logger.error(f"Failed to shutdown session {session_id}: {e}")
            raise

    async def get_orchestration_status(self) -> dict[str, Any]:
        """Get comprehensive orchestration service status."""
        return {
            "active_agents": self._active_agents,
            "active_sessions": len(self._active_sessions),
            "session_details": {
                session_id: {
                    "agents": len(session_info.get("agents", [])),
                    "pipeline_steps": session_info.get("pipeline_steps", []),
                    "duration": asyncio.get_event_loop().time() - session_info.get("start_time", 0)
                }
                for session_id, session_info in self._active_sessions.items()
            },
            "registry_stats": self.agent_registry.get_registry_stats(),
            "memory_service": self.memory_service is not None
        }

    async def close(self) -> None:
        """Close the orchestration service and clean up resources."""
        try:
            # Shutdown all active sessions
            session_ids = list(self._active_sessions.keys())
            for session_id in session_ids:
                await self.shutdown_session(session_id)

            # Shutdown all agents
            await self.agent_registry.shutdown_all()

            # Close memory service
            if self.memory_service:
                await self.memory_service.close()

            logger.info("Agent orchestration service closed")

        except Exception as e:
            logger.error(f"Error closing orchestration service: {e}")
            raise


# Global orchestration service instance
_orchestration_service: Optional[AgentOrchestrationService] = None


def get_orchestration_service() -> AgentOrchestrationService:
    """Get the global orchestration service instance."""
    global _orchestration_service
    if _orchestration_service is None:
        _orchestration_service = AgentOrchestrationService()
    return _orchestration_service


async def initialize_orchestration_service(memory_service: Optional[MemoryService] = None) -> AgentOrchestrationService:
    """Initialize the global orchestration service."""
    global _orchestration_service
    _orchestration_service = AgentOrchestrationService(memory_service)
    return _orchestration_service


logger.info("Agent orchestration service module initialized")
