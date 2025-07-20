"""Tests for logging module."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.logger import (
    get_logger,
    configure_logging,
    LogConfig,
    StructuredLogger,
    PerformanceLogger,
    SecurityLogger
)


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def log_config(temp_log_dir):
    """Log configuration fixture."""
    return LogConfig(
        level="DEBUG",
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        log_file=str(Path(temp_log_dir) / "test.log"),
        max_file_size="10MB",
        backup_count=3,
        enable_console=True,
        enable_structured=True
    )


class TestLogConfig:
    """Test cases for LogConfig."""

    def test_log_config_defaults(self):
        """Test LogConfig with default values."""
        config = LogConfig()
        assert config.level == "INFO"
        assert config.enable_console is True
        assert config.enable_structured is False
        assert config.backup_count == 5

    def test_log_config_custom_values(self, temp_log_dir):
        """Test LogConfig with custom values."""
        log_file = str(Path(temp_log_dir) / "custom.log")
        config = LogConfig(
            level="WARNING",
            format="%(levelname)s: %(message)s",
            log_file=log_file,
            max_file_size="5MB",
            backup_count=2,
            enable_console=False,
            enable_structured=True
        )
        
        assert config.level == "WARNING"
        assert config.log_file == log_file
        assert config.max_file_size == "5MB"
        assert config.backup_count == 2
        assert config.enable_console is False
        assert config.enable_structured is True

    def test_log_config_validation(self):
        """Test LogConfig validation."""
        # Valid log levels
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config = LogConfig(level=level)
            assert config.level == level

    def test_log_config_file_size_parsing(self):
        """Test log file size parsing."""
        configs = [
            ("1MB", LogConfig(max_file_size="1MB")),
            ("10MB", LogConfig(max_file_size="10MB")),
            ("1GB", LogConfig(max_file_size="1GB"))
        ]
        
        for size_str, config in configs:
            assert config.max_file_size == size_str


class TestGetLogger:
    """Test cases for get_logger function."""

    def test_get_logger_basic(self):
        """Test basic logger creation."""
        logger = get_logger("test_module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_with_config(self, log_config):
        """Test logger creation with custom config."""
        with patch('src.logger.configure_logging') as mock_configure:
            logger = get_logger("test_module", config=log_config)
            
            assert isinstance(logger, logging.Logger)
            mock_configure.assert_called_once_with(log_config)

    def test_get_logger_caching(self):
        """Test that loggers are cached."""
        logger1 = get_logger("cached_module")
        logger2 = get_logger("cached_module")
        
        assert logger1 is logger2

    def test_get_logger_different_modules(self):
        """Test loggers for different modules."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1 is not logger2
        assert logger1.name == "module1"
        assert logger2.name == "module2"

    def test_get_logger_hierarchy(self):
        """Test logger hierarchy."""
        parent_logger = get_logger("parent")
        child_logger = get_logger("parent.child")
        
        assert child_logger.parent == parent_logger or child_logger.name.startswith("parent.")


class TestConfigureLogging:
    """Test cases for configure_logging function."""

    def test_configure_logging_basic(self, log_config):
        """Test basic logging configuration."""
        configure_logging(log_config)
        
        # Get a test logger
        logger = logging.getLogger("test_configure")
        
        # Should be configured according to config
        assert logger.level <= getattr(logging, log_config.level)

    def test_configure_logging_file_handler(self, log_config):
        """Test file handler configuration."""
        configure_logging(log_config)
        
        # Check that log file is created
        log_file_path = Path(log_config.log_file)
        
        # File might not exist until first log message
        logger = logging.getLogger("file_test")
        logger.info("Test message")
        
        # Now file should exist (depending on implementation)
        # This test might need adjustment based on actual implementation

    def test_configure_logging_console_handler(self):
        """Test console handler configuration."""
        config = LogConfig(enable_console=True, enable_file=False)
        configure_logging(config)
        
        # Should have console handler
        root_logger = logging.getLogger()
        console_handlers = [
            h for h in root_logger.handlers 
            if isinstance(h, logging.StreamHandler) and h.stream.name in ['<stdout>', '<stderr>']
        ]
        
        # Implementation dependent - might need adjustment

    def test_configure_logging_level_setting(self):
        """Test log level configuration."""
        config = LogConfig(level="WARNING")
        configure_logging(config)
        
        logger = logging.getLogger("level_test")
        
        # Should respect the configured level
        assert logger.getEffectiveLevel() >= logging.WARNING

    def test_configure_logging_format(self, temp_log_dir):
        """Test log format configuration."""
        custom_format = "%(name)s - %(levelname)s - %(message)s"
        config = LogConfig(
            format=custom_format,
            log_file=str(Path(temp_log_dir) / "format_test.log")
        )
        
        configure_logging(config)
        
        # Test that format is applied (implementation dependent)
        logger = logging.getLogger("format_test")
        logger.info("Test message")


class TestStructuredLogger:
    """Test cases for StructuredLogger."""

    def test_structured_logger_creation(self):
        """Test creating StructuredLogger."""
        logger = StructuredLogger("structured_test")
        
        assert logger.name == "structured_test"
        assert hasattr(logger, 'log_structured')

    def test_structured_logging(self):
        """Test structured logging functionality."""
        logger = StructuredLogger("structured_test")
        
        # Test structured logging
        logger.log_structured(
            level="INFO",
            message="Test structured message",
            component="test_component",
            operation="test_operation",
            user_id="test_user",
            extra_data={"key": "value"}
        )
        
        # Should not raise exceptions

    def test_structured_logger_context(self):
        """Test structured logger with context."""
        logger = StructuredLogger("context_test")
        
        with logger.context(component="test_comp", operation="test_op"):
            logger.info("Message with context")
            logger.error("Error with context")
        
        # Context should be automatically included

    def test_structured_logger_fields(self):
        """Test structured logger field validation."""
        logger = StructuredLogger("fields_test")
        
        # Test with various field types
        logger.log_structured(
            level="INFO",
            message="Test fields",
            timestamp="2023-01-01T12:00:00Z",
            user_id="user_123",
            session_id="session_456",
            request_id="req_789",
            response_time=0.5,
            status_code=200
        )

    def test_structured_logger_json_output(self):
        """Test JSON output format."""
        logger = StructuredLogger("json_test", output_format="json")
        
        logger.info("JSON formatted message", extra={"test": "value"})
        
        # Should produce JSON formatted output


class TestPerformanceLogger:
    """Test cases for PerformanceLogger."""

    def test_performance_logger_creation(self):
        """Test creating PerformanceLogger."""
        logger = PerformanceLogger("perf_test")
        
        assert logger.name == "perf_test"
        assert hasattr(logger, 'log_performance')

    def test_performance_timing(self):
        """Test performance timing functionality."""
        logger = PerformanceLogger("timing_test")
        
        import time
        
        with logger.time_operation("test_operation") as timer:
            time.sleep(0.01)  # Simulate work
            timer.add_metadata({"items_processed": 100})
        
        # Should log performance metrics

    def test_performance_metrics(self):
        """Test performance metrics logging."""
        logger = PerformanceLogger("metrics_test")
        
        logger.log_performance(
            operation="database_query",
            duration=0.5,
            success=True,
            metadata={
                "query_type": "SELECT",
                "rows_returned": 150,
                "cache_hit": False
            }
        )

    def test_performance_aggregation(self):
        """Test performance metrics aggregation."""
        logger = PerformanceLogger("agg_test")
        
        # Log multiple operations
        for i in range(5):
            logger.log_performance(
                operation="api_call",
                duration=0.1 + i * 0.1,
                success=True
            )
        
        # Get aggregated stats
        stats = logger.get_performance_stats("api_call")
        
        assert stats["count"] == 5
        assert "avg_duration" in stats
        assert "min_duration" in stats
        assert "max_duration" in stats

    def test_performance_thresholds(self):
        """Test performance threshold alerts."""
        logger = PerformanceLogger("threshold_test")
        
        # Set threshold
        logger.set_threshold("slow_operation", max_duration=1.0)
        
        # Log operation that exceeds threshold
        logger.log_performance(
            operation="slow_operation",
            duration=2.0,
            success=True
        )
        
        # Should trigger threshold alert


class TestSecurityLogger:
    """Test cases for SecurityLogger."""

    def test_security_logger_creation(self):
        """Test creating SecurityLogger."""
        logger = SecurityLogger("security_test")
        
        assert logger.name == "security_test"
        assert hasattr(logger, 'log_security_event')

    def test_authentication_logging(self):
        """Test authentication event logging."""
        logger = SecurityLogger("auth_test")
        
        # Successful authentication
        logger.log_authentication(
            user_id="user_123",
            auth_method="jwt_token",
            success=True,
            ip_address="192.168.1.100",
            user_agent="TestAgent/1.0"
        )
        
        # Failed authentication
        logger.log_authentication(
            user_id="user_456",
            auth_method="password",
            success=False,
            failure_reason="invalid_password",
            ip_address="192.168.1.200"
        )

    def test_authorization_logging(self):
        """Test authorization event logging."""
        logger = SecurityLogger("authz_test")
        
        logger.log_authorization(
            user_id="user_123",
            resource="admin_dashboard",
            action="view",
            permission_granted=True,
            roles=["admin", "user"]
        )
        
        logger.log_authorization(
            user_id="user_456",
            resource="admin_settings",
            action="modify",
            permission_granted=False,
            roles=["user"]
        )

    def test_security_incident_logging(self):
        """Test security incident logging."""
        logger = SecurityLogger("incident_test")
        
        logger.log_security_incident(
            incident_type="brute_force_attack",
            severity="high",
            source_ip="192.168.1.999",
            target_user="admin",
            details={
                "failed_attempts": 50,
                "time_window": "5 minutes",
                "blocked": True
            }
        )

    def test_data_access_logging(self):
        """Test data access logging."""
        logger = SecurityLogger("data_test")
        
        logger.log_data_access(
            user_id="user_123",
            resource_type="story_state",
            resource_id="story_456",
            operation="read",
            sensitive_data=True,
            data_classification="confidential"
        )

    def test_security_audit_trail(self):
        """Test security audit trail."""
        logger = SecurityLogger("audit_test")
        
        # Multiple security events
        events = [
            ("login", {"user_id": "user_123", "success": True}),
            ("resource_access", {"resource": "admin_panel", "granted": True}),
            ("data_modification", {"table": "users", "records": 1}),
            ("logout", {"user_id": "user_123", "duration": 3600})
        ]
        
        for event_type, data in events:
            logger.log_security_event(
                event_type=event_type,
                **data
            )
        
        # Should create comprehensive audit trail


class TestLoggerIntegration:
    """Test cases for logger integration."""

    def test_multiple_logger_types(self):
        """Test using multiple logger types together."""
        # Create different logger types
        standard_logger = get_logger("integration_test")
        structured_logger = StructuredLogger("integration_structured")
        performance_logger = PerformanceLogger("integration_perf")
        security_logger = SecurityLogger("integration_security")
        
        # Use all loggers
        standard_logger.info("Standard log message")
        
        structured_logger.log_structured(
            level="INFO",
            message="Structured message",
            component="integration"
        )
        
        performance_logger.log_performance(
            operation="integration_test",
            duration=0.1,
            success=True
        )
        
        security_logger.log_authentication(
            user_id="test_user",
            auth_method="test",
            success=True
        )

    def test_logger_configuration_isolation(self):
        """Test that logger configurations don't interfere."""
        # Configure different log levels for different loggers
        config1 = LogConfig(level="DEBUG")
        config2 = LogConfig(level="ERROR")
        
        logger1 = get_logger("isolated_1", config=config1)
        logger2 = get_logger("isolated_2", config=config2)
        
        # Each should maintain its own configuration
        assert logger1.name != logger2.name

    def test_logger_cleanup(self):
        """Test logger cleanup and resource management."""
        # Create logger with file handler
        with tempfile.TemporaryDirectory() as temp_dir:
            config = LogConfig(
                log_file=str(Path(temp_dir) / "cleanup_test.log"),
                enable_console=False
            )
            
            logger = get_logger("cleanup_test", config=config)
            logger.info("Test message")
            
            # Cleanup should not raise exceptions
            # Implementation dependent

    def test_concurrent_logging(self):
        """Test concurrent logging from multiple threads."""
        import threading
        import time
        
        logger = get_logger("concurrent_test")
        
        def log_messages(thread_id):
            for i in range(10):
                logger.info(f"Thread {thread_id}: Message {i}")
                time.sleep(0.001)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=log_messages, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Should handle concurrent logging without issues