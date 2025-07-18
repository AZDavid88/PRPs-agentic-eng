"""
Agent lifecycle management system for the Narrative Factory.

Provides comprehensive agent state management, performance monitoring,
and lifecycle control for all agent personas.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.config import config
from src.exceptions import (
    BusinessLogicError,
    ResourceError,
    error_handler,
)
from src.health import register_health_check
from src.logger import LogContext, get_logger


logger = get_logger(__name__)


class AgentState(str, Enum):
    """Agent lifecycle states."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVE = "active"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class AgentPerformanceMetrics:
    """Performance metrics for agent monitoring."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_processing_time = 0.0
        self.average_response_time = 0.0
        self.peak_memory_usage = 0.0
        self.last_activity = None
        self.error_rate = 0.0
        self.created_at = time.time()

    def record_request(self, processing_time: float, success: bool, memory_usage: float = 0.0):
        """Record a request completion."""
        self.total_requests += 1
        self.total_processing_time += processing_time
        self.average_response_time = self.total_processing_time / self.total_requests
        self.last_activity = datetime.utcnow()

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.error_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0.0

        if memory_usage > self.peak_memory_usage:
            self.peak_memory_usage = memory_usage

    def get_metrics(self) -> dict[str, Any]:
        """Get current performance metrics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "average_response_time": self.average_response_time,
            "error_rate": self.error_rate,
            "peak_memory_usage": self.peak_memory_usage,
            "uptime_seconds": time.time() - self.created_at,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None
        }


@dataclass
class AgentContext:
    """Context information for agent operations."""
    agent_id: str
    agent_type: str
    request_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_log_context(self) -> dict[str, Any]:
        """Convert to logging context."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            **self.metadata
        }


class AgentLifecycleManager:
    """Manages agent lifecycle, state, and performance."""

    def __init__(self, agent_id: str, agent_type: str):
        """Initialize agent lifecycle manager."""
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.state = AgentState.INITIALIZING
        self.metrics = AgentPerformanceMetrics()
        self.context_stack: list[AgentContext] = []
        self.shutdown_callbacks: list[Callable] = []
        self.health_callbacks: list[Callable] = []
        self.created_at = datetime.utcnow()
        self.last_state_change = datetime.utcnow()
        self.active_requests = 0
        self.max_concurrent_requests = config.app.max_concurrent_tasks

        # Register health check
        register_health_check(f"agent_{agent_id}", self._health_check)

        logger.info(f"Agent lifecycle manager initialized for {agent_type}:{agent_id}")

    async def _health_check(self, include_detailed: bool = False) -> dict[str, Any]:
        """Health check for the agent."""
        try:
            # Check if agent is in a healthy state
            if self.state == AgentState.ERROR:
                return {
                    "status": "unhealthy",
                    "message": f"Agent {self.agent_id} is in error state",
                    "details": self.get_status() if include_detailed else None
                }
            elif self.state == AgentState.SHUTDOWN:
                return {
                    "status": "unhealthy",
                    "message": f"Agent {self.agent_id} is shut down",
                    "details": self.get_status() if include_detailed else None
                }
            elif self.active_requests >= self.max_concurrent_requests:
                return {
                    "status": "degraded",
                    "message": f"Agent {self.agent_id} at maximum capacity",
                    "details": self.get_status() if include_detailed else None
                }
            else:
                return {
                    "status": "healthy",
                    "message": f"Agent {self.agent_id} operational",
                    "details": self.get_status() if include_detailed else None
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Agent {self.agent_id} health check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    def transition_state(self, new_state: AgentState, reason: str = "") -> None:
        """Transition agent to new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = datetime.utcnow()

        logger.info(
            f"Agent {self.agent_id} state transition: {old_state.value} -> {new_state.value}",
            extra={
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "reason": reason
            }
        )

    async def initialize(self) -> None:
        """Initialize the agent."""
        try:
            self.transition_state(AgentState.IDLE, "Initialization complete")
            logger.info(f"Agent {self.agent_id} initialized successfully")
        except Exception as e:
            self.transition_state(AgentState.ERROR, f"Initialization failed: {str(e)}")
            error_handler.handle_error(e, {"agent_id": self.agent_id})
            raise

    async def shutdown(self) -> None:
        """Shutdown the agent gracefully."""
        try:
            self.transition_state(AgentState.SHUTDOWN, "Graceful shutdown initiated")

            # Wait for active requests to complete
            timeout = 30  # 30 second timeout
            start_time = time.time()

            while self.active_requests > 0 and (time.time() - start_time) < timeout:
                logger.info(f"Waiting for {self.active_requests} active requests to complete...")
                await asyncio.sleep(1)

            if self.active_requests > 0:
                logger.warning(f"Shutdown timeout: {self.active_requests} requests still active")

            # Execute shutdown callbacks
            for callback in self.shutdown_callbacks:
                try:
                    await callback()
                except Exception as e:
                    logger.error(f"Shutdown callback error: {e}")

            logger.info(f"Agent {self.agent_id} shutdown complete")
        except Exception as e:
            error_handler.handle_error(e, {"agent_id": self.agent_id})
            raise

    def register_shutdown_callback(self, callback: Callable) -> None:
        """Register a shutdown callback."""
        self.shutdown_callbacks.append(callback)

    def register_health_callback(self, callback: Callable) -> None:
        """Register a health check callback."""
        self.health_callbacks.append(callback)

    @asynccontextmanager
    async def request_context(self, context: AgentContext):
        """Context manager for handling requests."""
        if self.state == AgentState.SHUTDOWN:
            raise ResourceError(f"Agent {self.agent_id} is shut down")

        if self.active_requests >= self.max_concurrent_requests:
            raise ResourceError(f"Agent {self.agent_id} at maximum capacity")

        start_time = time.time()
        success = False
        memory_usage = 0.0

        try:
            # Track active request
            self.active_requests += 1
            self.context_stack.append(context)

            # Set state based on activity
            if self.active_requests == 1:
                self.transition_state(AgentState.ACTIVE, "Processing request")
            elif self.active_requests > 1:
                self.transition_state(AgentState.BUSY, "Processing multiple requests")

            # Set up logging context
            with LogContext(**context.to_log_context()):
                logger.info(f"Starting request processing for agent {self.agent_id}")

                # Get memory usage if available
                try:
                    import psutil
                    process = psutil.Process()
                    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
                except ImportError:
                    pass

                yield context
                success = True

        except Exception as e:
            error_handler.handle_error(e, context.to_log_context())
            self.transition_state(AgentState.ERROR, f"Request failed: {str(e)}")
            raise

        finally:
            # Clean up
            self.active_requests -= 1
            if self.context_stack:
                self.context_stack.pop()

            # Update metrics
            processing_time = time.time() - start_time
            self.metrics.record_request(processing_time, success, memory_usage)

            # Update state
            if self.active_requests == 0:
                self.transition_state(AgentState.IDLE, "Request processing complete")
            elif self.active_requests == 1:
                self.transition_state(AgentState.ACTIVE, "Reduced to single request")

            logger.info(
                f"Request completed for agent {self.agent_id}",
                extra={
                    "processing_time": processing_time,
                    "success": success,
                    "memory_usage_mb": memory_usage
                }
            )

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive agent status."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state.value,
            "active_requests": self.active_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "context_stack_depth": len(self.context_stack),
            "created_at": self.created_at.isoformat(),
            "last_state_change": self.last_state_change.isoformat(),
            "metrics": self.metrics.get_metrics()
        }

    def is_available(self) -> bool:
        """Check if agent is available for new requests."""
        return (
            self.state in [AgentState.IDLE, AgentState.ACTIVE, AgentState.BUSY] and
            self.active_requests < self.max_concurrent_requests
        )


class AgentRegistry:
    """Registry for managing multiple agents."""

    def __init__(self):
        """Initialize agent registry."""
        self._agents: dict[str, AgentLifecycleManager] = {}
        self._agent_types: dict[str, list[str]] = {}

        # Register health check
        register_health_check("agent_registry", self._health_check)

        logger.info("Agent registry initialized")

    async def _health_check(self, include_detailed: bool = False) -> dict[str, Any]:
        """Health check for the agent registry."""
        try:
            total_agents = len(self._agents)
            healthy_agents = sum(1 for agent in self._agents.values() if agent.is_available())

            status = "healthy" if healthy_agents == total_agents else "degraded"
            if healthy_agents == 0 and total_agents > 0:
                status = "unhealthy"

            details = {}
            if include_detailed:
                details = {
                    "total_agents": total_agents,
                    "healthy_agents": healthy_agents,
                    "agent_types": dict(self._agent_types),
                    "agents": {
                        agent_id: agent.get_status()
                        for agent_id, agent in self._agents.items()
                    }
                }

            return {
                "status": status,
                "message": f"Agent registry: {healthy_agents}/{total_agents} agents healthy",
                "details": details
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Agent registry health check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    def register_agent(self, agent_id: str, agent_type: str) -> AgentLifecycleManager:
        """Register a new agent."""
        if agent_id in self._agents:
            raise BusinessLogicError(f"Agent {agent_id} already registered")

        lifecycle_manager = AgentLifecycleManager(agent_id, agent_type)
        self._agents[agent_id] = lifecycle_manager

        # Track by type
        if agent_type not in self._agent_types:
            self._agent_types[agent_type] = []
        self._agent_types[agent_type].append(agent_id)

        logger.info(f"Agent registered: {agent_type}:{agent_id}")
        return lifecycle_manager

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        if agent_id not in self._agents:
            raise BusinessLogicError(f"Agent {agent_id} not found")

        agent = self._agents[agent_id]
        await agent.shutdown()

        # Remove from type tracking
        if agent.agent_type in self._agent_types:
            self._agent_types[agent.agent_type].remove(agent_id)
            if not self._agent_types[agent.agent_type]:
                del self._agent_types[agent.agent_type]

        del self._agents[agent_id]
        logger.info(f"Agent unregistered: {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[AgentLifecycleManager]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> list[AgentLifecycleManager]:
        """Get all agents of a specific type."""
        agent_ids = self._agent_types.get(agent_type, [])
        return [self._agents[agent_id] for agent_id in agent_ids]

    def get_available_agent(self, agent_type: str) -> Optional[AgentLifecycleManager]:
        """Get an available agent of the specified type."""
        agents = self.get_agents_by_type(agent_type)
        for agent in agents:
            if agent.is_available():
                return agent
        return None

    def get_registry_stats(self) -> dict[str, Any]:
        """Get comprehensive registry statistics."""
        return {
            "total_agents": len(self._agents),
            "agent_types": dict(self._agent_types),
            "agents_by_state": {
                state.value: len([
                    agent for agent in self._agents.values()
                    if agent.state == state
                ])
                for state in AgentState
            },
            "available_agents": len([
                agent for agent in self._agents.values()
                if agent.is_available()
            ])
        }

    async def shutdown_all(self) -> None:
        """Shutdown all registered agents."""
        logger.info("Shutting down all agents...")

        shutdown_tasks = []
        for agent in self._agents.values():
            shutdown_tasks.append(agent.shutdown())

        await asyncio.gather(*shutdown_tasks, return_exceptions=True)

        self._agents.clear()
        self._agent_types.clear()

        logger.info("All agents shut down")


# Global agent registry
agent_registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry."""
    return agent_registry


def register_agent(agent_id: str, agent_type: str) -> AgentLifecycleManager:
    """Register a new agent."""
    return agent_registry.register_agent(agent_id, agent_type)


async def unregister_agent(agent_id: str) -> None:
    """Unregister an agent."""
    await agent_registry.unregister_agent(agent_id)


def get_agent(agent_id: str) -> Optional[AgentLifecycleManager]:
    """Get agent by ID."""
    return agent_registry.get_agent(agent_id)


def get_available_agent(agent_type: str) -> Optional[AgentLifecycleManager]:
    """Get an available agent of the specified type."""
    return agent_registry.get_available_agent(agent_type)


logger.info("Agent lifecycle management system initialized")
