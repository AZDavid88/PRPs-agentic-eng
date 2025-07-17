"""
Agent communication protocols and error handling for the Narrative Factory.

Provides structured communication between agents, error handling patterns,
and comprehensive validation for agent interactions.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.agents.models import ChapterBlueprint, StrategicBrief
from src.exceptions import ValidationError as CustomValidationError
from src.logger import get_logger

logger = get_logger(__name__)


class MessageType(str, Enum):
    """Types of messages that can be sent between agents."""
    STRATEGIC_BRIEF = "strategic_brief"
    CHAPTER_BLUEPRINT = "chapter_blueprint"
    PROSE_CONTENT = "prose_content"
    VALIDATION_RESULT = "validation_result"
    CONTEXT_REQUEST = "context_request"
    CONTEXT_RESPONSE = "context_response"
    ERROR_REPORT = "error_report"
    STATUS_UPDATE = "status_update"
    HEALTH_CHECK = "health_check"


class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class MessageMetadata:
    """Metadata for agent messages."""
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: f"msg_{int(time.time() * 1000)}")
    correlation_id: Optional[str] = None
    sender_id: str = ""
    recipient_id: str = ""
    session_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 30
    priority: MessagePriority = MessagePriority.NORMAL


class AgentMessage(BaseModel):
    """Base class for agent-to-agent communication."""
    message_type: MessageType
    payload: Dict[str, Any]
    metadata: MessageMetadata

    class Config:
        arbitrary_types_allowed = True


class StrategicBriefMessage(AgentMessage):
    """Message containing strategic brief from Director."""
    message_type: MessageType = MessageType.STRATEGIC_BRIEF
    strategic_brief: StrategicBrief

    def __init__(self, strategic_brief: StrategicBrief, metadata: MessageMetadata, **kwargs):
        super().__init__(
            message_type=MessageType.STRATEGIC_BRIEF,
            payload={"strategic_brief": strategic_brief.dict()},
            metadata=metadata,
            strategic_brief=strategic_brief,
            **kwargs
        )


class ChapterBlueprintMessage(AgentMessage):
    """Message containing chapter blueprint from Tactician."""
    message_type: MessageType = MessageType.CHAPTER_BLUEPRINT
    chapter_blueprint: ChapterBlueprint

    def __init__(self, chapter_blueprint: ChapterBlueprint, metadata: MessageMetadata, **kwargs):
        super().__init__(
            message_type=MessageType.CHAPTER_BLUEPRINT,
            payload={"chapter_blueprint": chapter_blueprint.dict()},
            metadata=metadata,
            chapter_blueprint=chapter_blueprint,
            **kwargs
        )


class ProseContentMessage(AgentMessage):
    """Message containing prose content from Weaver."""
    message_type: MessageType = MessageType.PROSE_CONTENT
    prose_content: str

    def __init__(self, prose_content: str, metadata: MessageMetadata, **kwargs):
        super().__init__(
            message_type=MessageType.PROSE_CONTENT,
            payload={"prose_content": prose_content},
            metadata=metadata,
            prose_content=prose_content,
            **kwargs
        )


class ValidationResultMessage(AgentMessage):
    """Message containing validation result from Canonist."""
    message_type: MessageType = MessageType.VALIDATION_RESULT
    validation_result: Dict[str, Any]

    def __init__(self, validation_result: Dict[str, Any], metadata: MessageMetadata, **kwargs):
        super().__init__(
            message_type=MessageType.VALIDATION_RESULT,
            payload={"validation_result": validation_result},
            metadata=metadata,
            validation_result=validation_result,
            **kwargs
        )


class ErrorReportMessage(AgentMessage):
    """Message containing error information."""
    message_type: MessageType = MessageType.ERROR_REPORT
    error_type: str
    error_message: str
    error_details: Dict[str, Any]

    def __init__(self, error_type: str, error_message: str, error_details: Dict[str, Any], metadata: MessageMetadata, **kwargs):
        super().__init__(
            message_type=MessageType.ERROR_REPORT,
            payload={
                "error_type": error_type,
                "error_message": error_message,
                "error_details": error_details
            },
            metadata=metadata,
            error_type=error_type,
            error_message=error_message,
            error_details=error_details,
            **kwargs
        )


class AgentCommunicationService:
    """
    Service for managing agent-to-agent communication with error handling and validation.
    """

    def __init__(self):
        """Initialize the communication service."""
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.message_history: List[AgentMessage] = []
        self.error_handlers: Dict[str, callable] = {}
        self.message_handlers: Dict[MessageType, callable] = {}
        self.active_conversations: Dict[str, Dict[str, Any]] = {}

        # Register default error handlers
        self._register_default_error_handlers()

        logger.info("Agent communication service initialized")

    def _register_default_error_handlers(self):
        """Register default error handlers."""
        self.error_handlers["ValidationError"] = self._handle_validation_error
        self.error_handlers["BusinessLogicError"] = self._handle_business_logic_error
        self.error_handlers["TimeoutError"] = self._handle_timeout_error
        self.error_handlers["ConnectionError"] = self._handle_connection_error

    async def _handle_validation_error(self, error: Exception, message: AgentMessage) -> Dict[str, Any]:
        """Handle validation errors."""
        logger.error(f"Validation error in message {message.metadata.message_id}: {error}")

        return {
            "error_handled": True,
            "recovery_action": "request_revalidation",
            "error_type": "validation",
            "message": str(error)
        }

    async def _handle_business_logic_error(self, error: Exception, message: AgentMessage) -> Dict[str, Any]:
        """Handle business logic errors."""
        logger.error(f"Business logic error in message {message.metadata.message_id}: {error}")

        return {
            "error_handled": True,
            "recovery_action": "escalate_to_supervisor",
            "error_type": "business_logic",
            "message": str(error)
        }

    async def _handle_timeout_error(self, error: Exception, message: AgentMessage) -> Dict[str, Any]:
        """Handle timeout errors."""
        logger.error(f"Timeout error in message {message.metadata.message_id}: {error}")

        # Retry logic
        if message.metadata.retry_count < message.metadata.max_retries:
            message.metadata.retry_count += 1
            await self.send_message(message)

            return {
                "error_handled": True,
                "recovery_action": "retry_attempted",
                "error_type": "timeout",
                "retry_count": message.metadata.retry_count
            }
        else:
            return {
                "error_handled": False,
                "recovery_action": "max_retries_exceeded",
                "error_type": "timeout",
                "message": "Maximum retries exceeded"
            }

    async def _handle_connection_error(self, error: Exception, message: AgentMessage) -> Dict[str, Any]:
        """Handle connection errors."""
        logger.error(f"Connection error in message {message.metadata.message_id}: {error}")

        return {
            "error_handled": True,
            "recovery_action": "reconnect_and_retry",
            "error_type": "connection",
            "message": str(error)
        }

    async def send_message(self, message: AgentMessage) -> bool:
        """
        Send a message through the communication system.
        
        Args:
            message: The message to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            # Validate message
            await self._validate_message(message)

            # Add to message history
            self.message_history.append(message)

            # Add to queue for processing
            await self.message_queue.put(message)

            # Track conversation
            if message.metadata.session_id:
                await self._track_conversation(message)

            logger.info(f"Message sent: {message.metadata.message_id} ({message.message_type})")
            return True

        except Exception as e:
            logger.error(f"Failed to send message {message.metadata.message_id}: {e}")

            # Handle error
            error_type = type(e).__name__
            if error_type in self.error_handlers:
                await self.error_handlers[error_type](e, message)

            return False

    async def _validate_message(self, message: AgentMessage) -> None:
        """Validate a message before sending."""
        try:
            # Basic validation
            if not message.metadata.sender_id:
                raise CustomValidationError("Sender ID is required")

            if not message.metadata.recipient_id:
                raise CustomValidationError("Recipient ID is required")

            # Type-specific validation
            if message.message_type == MessageType.STRATEGIC_BRIEF:
                if not isinstance(message, StrategicBriefMessage):
                    raise CustomValidationError("Strategic brief message must be StrategicBriefMessage type")

            elif message.message_type == MessageType.CHAPTER_BLUEPRINT:
                if not isinstance(message, ChapterBlueprintMessage):
                    raise CustomValidationError("Chapter blueprint message must be ChapterBlueprintMessage type")

            elif message.message_type == MessageType.PROSE_CONTENT:
                if not isinstance(message, ProseContentMessage):
                    raise CustomValidationError("Prose content message must be ProseContentMessage type")

            elif message.message_type == MessageType.VALIDATION_RESULT:
                if not isinstance(message, ValidationResultMessage):
                    raise CustomValidationError("Validation result message must be ValidationResultMessage type")

            logger.debug(f"Message validation passed: {message.metadata.message_id}")

        except Exception as e:
            logger.error(f"Message validation failed: {e}")
            raise CustomValidationError(f"Message validation failed: {e}") from e

    async def _track_conversation(self, message: AgentMessage) -> None:
        """Track conversation flow."""
        session_id = message.metadata.session_id

        if session_id not in self.active_conversations:
            self.active_conversations[session_id] = {
                "messages": [],
                "participants": set(),
                "start_time": time.time(),
                "last_activity": time.time()
            }

        conversation = self.active_conversations[session_id]
        conversation["messages"].append(message.metadata.message_id)
        conversation["participants"].add(message.metadata.sender_id)
        conversation["participants"].add(message.metadata.recipient_id)
        conversation["last_activity"] = time.time()

    async def receive_message(self, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """
        Receive a message from the communication system.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Received message or None if timeout
        """
        try:
            if timeout:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=timeout)
            else:
                message = await self.message_queue.get()

            logger.info(f"Message received: {message.metadata.message_id} ({message.message_type})")
            return message

        except asyncio.TimeoutError:
            logger.debug("Message receive timeout")
            return None
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None

    async def create_strategic_brief_message(
        self,
        strategic_brief: StrategicBrief,
        sender_id: str,
        recipient_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> StrategicBriefMessage:
        """Create a strategic brief message."""
        metadata = MessageMetadata(
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=session_id,
            correlation_id=correlation_id
        )

        return StrategicBriefMessage(
            strategic_brief=strategic_brief,
            metadata=metadata
        )

    async def create_chapter_blueprint_message(
        self,
        chapter_blueprint: ChapterBlueprint,
        sender_id: str,
        recipient_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ChapterBlueprintMessage:
        """Create a chapter blueprint message."""
        metadata = MessageMetadata(
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=session_id,
            correlation_id=correlation_id
        )

        return ChapterBlueprintMessage(
            chapter_blueprint=chapter_blueprint,
            metadata=metadata
        )

    async def create_prose_content_message(
        self,
        prose_content: str,
        sender_id: str,
        recipient_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ProseContentMessage:
        """Create a prose content message."""
        metadata = MessageMetadata(
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=session_id,
            correlation_id=correlation_id
        )

        return ProseContentMessage(
            prose_content=prose_content,
            metadata=metadata
        )

    async def create_validation_result_message(
        self,
        validation_result: Dict[str, Any],
        sender_id: str,
        recipient_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ValidationResultMessage:
        """Create a validation result message."""
        metadata = MessageMetadata(
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=session_id,
            correlation_id=correlation_id
        )

        return ValidationResultMessage(
            validation_result=validation_result,
            metadata=metadata
        )

    async def create_error_report_message(
        self,
        error_type: str,
        error_message: str,
        error_details: Dict[str, Any],
        sender_id: str,
        recipient_id: str,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> ErrorReportMessage:
        """Create an error report message."""
        metadata = MessageMetadata(
            sender_id=sender_id,
            recipient_id=recipient_id,
            session_id=session_id,
            correlation_id=correlation_id,
            priority=MessagePriority.HIGH
        )

        return ErrorReportMessage(
            error_type=error_type,
            error_message=error_message,
            error_details=error_details,
            metadata=metadata
        )

    async def get_conversation_history(self, session_id: str) -> List[str]:
        """Get conversation history for a session."""
        if session_id in self.active_conversations:
            return self.active_conversations[session_id]["messages"]
        return []

    async def get_message_history(self, limit: int = 100) -> List[AgentMessage]:
        """Get recent message history."""
        return self.message_history[-limit:]

    async def get_communication_stats(self) -> Dict[str, Any]:
        """Get communication statistics."""
        return {
            "total_messages": len(self.message_history),
            "active_conversations": len(self.active_conversations),
            "queue_size": self.message_queue.qsize(),
            "message_types": {
                msg_type.value: sum(1 for msg in self.message_history if msg.message_type == msg_type)
                for msg_type in MessageType
            },
            "error_handlers": list(self.error_handlers.keys())
        }

    async def close(self) -> None:
        """Close the communication service."""
        # Clear queues and histories
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.message_history.clear()
        self.active_conversations.clear()

        logger.info("Agent communication service closed")


# Global communication service instance
_communication_service: Optional[AgentCommunicationService] = None


def get_communication_service() -> AgentCommunicationService:
    """Get the global communication service instance."""
    global _communication_service
    if _communication_service is None:
        _communication_service = AgentCommunicationService()
    return _communication_service


async def initialize_communication_service() -> AgentCommunicationService:
    """Initialize the global communication service."""
    global _communication_service
    _communication_service = AgentCommunicationService()
    return _communication_service


logger.info("Agent communication service module initialized")
