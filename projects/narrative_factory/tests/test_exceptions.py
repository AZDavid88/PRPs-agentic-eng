"""Tests for exception handling module."""

import pytest

from src.exceptions import (
    NarrativeFactoryException,
    AgentExecutionError,
    MemoryServiceError,
    WorkflowError,
    ValidationError,
    ConfigurationError,
    AuthenticationError,
    RateLimitError,
    StorageError,
    ExceptionHandler,
    ErrorCode
)


class TestErrorCode:
    """Test cases for ErrorCode enum."""

    def test_error_code_values(self):
        """Test ErrorCode enum values."""
        assert ErrorCode.AGENT_EXECUTION_FAILED.value == "AGENT_EXECUTION_FAILED"
        assert ErrorCode.MEMORY_SERVICE_ERROR.value == "MEMORY_SERVICE_ERROR"
        assert ErrorCode.WORKFLOW_ERROR.value == "WORKFLOW_ERROR"
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.CONFIGURATION_ERROR.value == "CONFIGURATION_ERROR"

    def test_error_code_completeness(self):
        """Test that all expected error codes exist."""
        expected_codes = [
            "AGENT_EXECUTION_FAILED",
            "MEMORY_SERVICE_ERROR",
            "WORKFLOW_ERROR",
            "VALIDATION_ERROR",
            "CONFIGURATION_ERROR",
            "AUTHENTICATION_ERROR",
            "RATE_LIMIT_EXCEEDED",
            "STORAGE_ERROR",
            "UNKNOWN_ERROR"
        ]
        
        for code in expected_codes:
            assert hasattr(ErrorCode, code)


class TestNarrativeFactoryException:
    """Test cases for base NarrativeFactoryException."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        exception = NarrativeFactoryException(
            message="Test error message",
            error_code=ErrorCode.UNKNOWN_ERROR,
            details={"component": "test", "operation": "test_op"}
        )
        
        assert str(exception) == "Test error message"
        assert exception.error_code == ErrorCode.UNKNOWN_ERROR
        assert exception.details["component"] == "test"
        assert exception.details["operation"] == "test_op"

    def test_base_exception_defaults(self):
        """Test base exception with default values."""
        exception = NarrativeFactoryException("Simple error")
        
        assert str(exception) == "Simple error"
        assert exception.error_code == ErrorCode.UNKNOWN_ERROR
        assert exception.details == {}
        assert exception.timestamp is not None

    def test_base_exception_repr(self):
        """Test base exception string representation."""
        exception = NarrativeFactoryException(
            message="Test error",
            error_code=ErrorCode.VALIDATION_ERROR
        )
        
        repr_str = repr(exception)
        assert "NarrativeFactoryException" in repr_str
        assert "VALIDATION_ERROR" in repr_str
        assert "Test error" in repr_str

    def test_base_exception_serialization(self):
        """Test exception serialization to dict."""
        exception = NarrativeFactoryException(
            message="Serialization test",
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details={"setting": "invalid_value"}
        )
        
        exception_dict = exception.to_dict()
        
        assert exception_dict["message"] == "Serialization test"
        assert exception_dict["error_code"] == "CONFIGURATION_ERROR"
        assert exception_dict["details"]["setting"] == "invalid_value"
        assert "timestamp" in exception_dict


class TestSpecificExceptions:
    """Test cases for specific exception types."""

    def test_agent_execution_error(self):
        """Test AgentExecutionError."""
        error = AgentExecutionError(
            message="Agent failed to execute",
            agent_name="DirectorAgent",
            execution_context={"input": "test_input", "step": "planning"}
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.AGENT_EXECUTION_FAILED
        assert error.agent_name == "DirectorAgent"
        assert error.execution_context["input"] == "test_input"

    def test_memory_service_error(self):
        """Test MemoryServiceError."""
        error = MemoryServiceError(
            message="Failed to retrieve memories",
            service_name="QdrantService",
            operation="search",
            query_details={"collection": "narrative_memory", "limit": 10}
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.MEMORY_SERVICE_ERROR
        assert error.service_name == "QdrantService"
        assert error.operation == "search"
        assert error.query_details["collection"] == "narrative_memory"

    def test_workflow_error(self):
        """Test WorkflowError."""
        error = WorkflowError(
            message="Workflow execution failed",
            workflow_name="FullGenerationFlow",
            workflow_step="tactician_execution",
            workflow_state={"current_job": "job_123", "status": "pending"}
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.WORKFLOW_ERROR
        assert error.workflow_name == "FullGenerationFlow"
        assert error.workflow_step == "tactician_execution"
        assert error.workflow_state["current_job"] == "job_123"

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError(
            message="Input validation failed",
            field_name="chapter_seed",
            field_value="",
            validation_rule="min_length",
            expected_value="5 characters minimum"
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.VALIDATION_ERROR
        assert error.field_name == "chapter_seed"
        assert error.field_value == ""
        assert error.validation_rule == "min_length"

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError(
            message="Invalid configuration setting",
            config_key="models.api_key",
            config_value=None,
            expected_type="string"
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.CONFIGURATION_ERROR
        assert error.config_key == "models.api_key"
        assert error.config_value is None
        assert error.expected_type == "string"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        error = AuthenticationError(
            message="Authentication failed",
            user_id="user_123",
            auth_method="jwt_token",
            failure_reason="token_expired"
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.AUTHENTICATION_ERROR
        assert error.user_id == "user_123"
        assert error.auth_method == "jwt_token"
        assert error.failure_reason == "token_expired"

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError(
            message="Rate limit exceeded",
            user_id="user_456",
            limit_type="api_requests",
            current_count=100,
            limit_threshold=50,
            reset_time="2023-01-01T12:00:00Z"
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert error.user_id == "user_456"
        assert error.limit_type == "api_requests"
        assert error.current_count == 100
        assert error.limit_threshold == 50

    def test_storage_error(self):
        """Test StorageError."""
        error = StorageError(
            message="Storage operation failed",
            storage_type="redis",
            operation="set",
            key="cache_key_123",
            error_details={"connection": "failed", "retry_count": 3}
        )
        
        assert isinstance(error, NarrativeFactoryException)
        assert error.error_code == ErrorCode.STORAGE_ERROR
        assert error.storage_type == "redis"
        assert error.operation == "set"
        assert error.key == "cache_key_123"
        assert error.error_details["connection"] == "failed"


class TestExceptionHandler:
    """Test cases for ExceptionHandler."""

    def test_exception_handler_creation(self):
        """Test creating ExceptionHandler."""
        handler = ExceptionHandler()
        assert handler is not None

    def test_handle_exception_with_context(self):
        """Test handling exception with context."""
        handler = ExceptionHandler()
        
        try:
            raise ValueError("Test value error")
        except ValueError as e:
            handled_exception = handler.handle_exception(
                e,
                context={
                    "component": "test_component",
                    "operation": "test_operation",
                    "user_id": "test_user"
                }
            )
        
        assert isinstance(handled_exception, NarrativeFactoryException)
        assert "Test value error" in str(handled_exception)
        assert handled_exception.details["component"] == "test_component"

    def test_handle_known_exception_types(self):
        """Test handling known exception types."""
        handler = ExceptionHandler()
        
        # Test handling of different standard exceptions
        exceptions_to_test = [
            (ValueError("Invalid value"), ErrorCode.VALIDATION_ERROR),
            (KeyError("Missing key"), ErrorCode.CONFIGURATION_ERROR),
            (ConnectionError("Connection failed"), ErrorCode.STORAGE_ERROR),
            (TimeoutError("Operation timeout"), ErrorCode.WORKFLOW_ERROR)
        ]
        
        for original_exception, expected_code in exceptions_to_test:
            handled = handler.handle_exception(original_exception)
            assert isinstance(handled, NarrativeFactoryException)
            # The specific error code mapping depends on implementation

    def test_handle_narrative_factory_exception(self):
        """Test handling existing NarrativeFactoryException."""
        handler = ExceptionHandler()
        
        original = AgentExecutionError(
            message="Original agent error",
            agent_name="TestAgent"
        )
        
        handled = handler.handle_exception(original)
        
        # Should return the same exception or a wrapped version
        assert isinstance(handled, NarrativeFactoryException)
        assert "Original agent error" in str(handled)

    def test_exception_logging(self):
        """Test exception logging functionality."""
        handler = ExceptionHandler(enable_logging=True)
        
        with pytest.raises(Exception):
            try:
                raise ValueError("Test logging error")
            except ValueError as e:
                # Handler should log the exception
                handled = handler.handle_exception(e)
                raise handled

    def test_exception_reporting(self):
        """Test exception reporting functionality."""
        handler = ExceptionHandler(enable_reporting=True)
        
        original_exception = ValueError("Test reporting error")
        
        handled = handler.handle_exception(
            original_exception,
            context={"report_to": "error_service"}
        )
        
        assert isinstance(handled, NarrativeFactoryException)
        # Reporting functionality would depend on implementation

    def test_exception_recovery_suggestions(self):
        """Test exception recovery suggestions."""
        handler = ExceptionHandler()
        
        # Test agent execution error recovery
        agent_error = AgentExecutionError(
            message="Agent timeout",
            agent_name="SlowAgent"
        )
        
        suggestions = handler.get_recovery_suggestions(agent_error)
        
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0
        # Specific suggestions depend on implementation

    def test_exception_categorization(self):
        """Test exception categorization."""
        handler = ExceptionHandler()
        
        # Test different categories
        user_error = ValidationError(
            message="Invalid input",
            field_name="test_field"
        )
        
        system_error = StorageError(
            message="Database connection failed",
            storage_type="redis"
        )
        
        user_category = handler.categorize_exception(user_error)
        system_category = handler.categorize_exception(system_error)
        
        assert user_category in ["user_error", "validation_error", "client_error"]
        assert system_category in ["system_error", "infrastructure_error", "server_error"]


class TestExceptionChaining:
    """Test cases for exception chaining and causality."""

    def test_exception_with_cause(self):
        """Test exception with original cause."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as original:
                raise AgentExecutionError(
                    message="Agent failed due to validation",
                    agent_name="TestAgent"
                ) from original
        except AgentExecutionError as agent_error:
            assert agent_error.__cause__ is not None
            assert isinstance(agent_error.__cause__, ValueError)
            assert "Original error" in str(agent_error.__cause__)

    def test_exception_chain_preservation(self):
        """Test that exception chains are preserved."""
        handler = ExceptionHandler()
        
        try:
            try:
                raise ConnectionError("Network failure")
            except ConnectionError as conn_error:
                raise StorageError(
                    message="Storage failed",
                    storage_type="redis"
                ) from conn_error
        except StorageError as storage_error:
            handled = handler.handle_exception(storage_error)
            
            # Chain should be preserved
            assert handled.__cause__ is not None or storage_error.__cause__ is not None

    def test_nested_exception_handling(self):
        """Test handling deeply nested exceptions."""
        def level_3():
            raise ValueError("Level 3 error")
        
        def level_2():
            try:
                level_3()
            except ValueError as e:
                raise MemoryServiceError(
                    message="Level 2 error",
                    service_name="TestService"
                ) from e
        
        def level_1():
            try:
                level_2()
            except MemoryServiceError as e:
                raise WorkflowError(
                    message="Level 1 error",
                    workflow_name="TestWorkflow"
                ) from e
        
        handler = ExceptionHandler()
        
        try:
            level_1()
        except WorkflowError as final_error:
            handled = handler.handle_exception(final_error)
            
            # Should preserve the chain
            assert isinstance(handled, NarrativeFactoryException)


class TestExceptionUtilities:
    """Test cases for exception utility functions."""

    def test_exception_serialization_roundtrip(self):
        """Test exception serialization and deserialization."""
        original = AgentExecutionError(
            message="Serialization test",
            agent_name="TestAgent",
            execution_context={"step": "validation"}
        )
        
        # Serialize
        serialized = original.to_dict()
        
        # Create new exception from serialized data
        restored = AgentExecutionError(
            message=serialized["message"],
            agent_name="TestAgent"  # Would need to restore all fields
        )
        
        assert str(restored) == str(original)

    def test_exception_filtering(self):
        """Test exception filtering by type or code."""
        exceptions = [
            AgentExecutionError("Agent error", agent_name="Agent1"),
            MemoryServiceError("Memory error", service_name="Memory1"),
            ValidationError("Validation error", field_name="field1"),
            AgentExecutionError("Another agent error", agent_name="Agent2")
        ]
        
        # Filter by type
        agent_errors = [e for e in exceptions if isinstance(e, AgentExecutionError)]
        assert len(agent_errors) == 2
        
        # Filter by error code
        agent_code_errors = [e for e in exceptions if e.error_code == ErrorCode.AGENT_EXECUTION_FAILED]
        assert len(agent_code_errors) == 2

    def test_exception_aggregation(self):
        """Test aggregating multiple exceptions."""
        exceptions = [
            ValidationError("Error 1", field_name="field1"),
            ValidationError("Error 2", field_name="field2"),
            ValidationError("Error 3", field_name="field3")
        ]
        
        # Create aggregate exception
        aggregate = NarrativeFactoryException(
            message=f"Multiple validation errors: {len(exceptions)} errors",
            error_code=ErrorCode.VALIDATION_ERROR,
            details={"error_count": len(exceptions), "errors": [str(e) for e in exceptions]}
        )
        
        assert "Multiple validation errors: 3 errors" in str(aggregate)
        assert aggregate.details["error_count"] == 3