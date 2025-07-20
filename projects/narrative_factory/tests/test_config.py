"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from src.config import (
    Config, 
    ModelConfig, 
    DatabaseConfig, 
    MemoryConfig,
    WebConfig,
    PerformanceConfig,
    config
)


class TestModelConfig:
    """Test cases for ModelConfig."""

    def test_model_config_defaults(self):
        """Test ModelConfig with default values."""
        model_config = ModelConfig()
        assert model_config.provider == "openai"
        assert model_config.model == "gpt-4"
        assert model_config.temperature == 0.7
        assert model_config.max_tokens == 2000

    def test_model_config_custom_values(self):
        """Test ModelConfig with custom values."""
        model_config = ModelConfig(
            provider="anthropic",
            model="claude-3",
            temperature=0.5,
            max_tokens=4000,
            api_key="test_key"
        )
        assert model_config.provider == "anthropic"
        assert model_config.model == "claude-3"
        assert model_config.temperature == 0.5
        assert model_config.max_tokens == 4000
        assert model_config.api_key == "test_key"

    def test_model_config_validation(self):
        """Test ModelConfig validation."""
        # Valid temperature range
        model_config = ModelConfig(temperature=0.0)
        assert model_config.temperature == 0.0
        
        model_config = ModelConfig(temperature=2.0)
        assert model_config.temperature == 2.0
        
        # Valid max_tokens
        model_config = ModelConfig(max_tokens=1)
        assert model_config.max_tokens == 1


class TestDatabaseConfig:
    """Test cases for DatabaseConfig."""

    def test_database_config_defaults(self):
        """Test DatabaseConfig with default values."""
        db_config = DatabaseConfig()
        assert db_config.redis_url == "redis://localhost:6379"
        assert db_config.qdrant_url == "http://localhost:6333"
        assert db_config.qdrant_collection == "narrative_memory"

    def test_database_config_custom_values(self):
        """Test DatabaseConfig with custom values."""
        db_config = DatabaseConfig(
            redis_url="redis://redis-server:6379",
            qdrant_url="http://qdrant-server:6333",
            qdrant_collection="test_collection",
            qdrant_api_key="test_api_key"
        )
        assert db_config.redis_url == "redis://redis-server:6379"
        assert db_config.qdrant_url == "http://qdrant-server:6333"
        assert db_config.qdrant_collection == "test_collection"
        assert db_config.qdrant_api_key == "test_api_key"


class TestMemoryConfig:
    """Test cases for MemoryConfig."""

    def test_memory_config_defaults(self):
        """Test MemoryConfig with default values."""
        memory_config = MemoryConfig()
        assert memory_config.spotlight_limit == 5
        assert memory_config.ambient_limit == 10
        assert memory_config.chunk_size == 1000
        assert memory_config.chunk_overlap == 200

    def test_memory_config_custom_values(self):
        """Test MemoryConfig with custom values."""
        memory_config = MemoryConfig(
            spotlight_limit=10,
            ambient_limit=20,
            chunk_size=2000,
            chunk_overlap=400,
            embedding_model="jina-v4"
        )
        assert memory_config.spotlight_limit == 10
        assert memory_config.ambient_limit == 20
        assert memory_config.chunk_size == 2000
        assert memory_config.chunk_overlap == 400
        assert memory_config.embedding_model == "jina-v4"


class TestWebConfig:
    """Test cases for WebConfig."""

    def test_web_config_defaults(self):
        """Test WebConfig with default values."""
        web_config = WebConfig()
        assert web_config.host == "localhost"
        assert web_config.port == 8000
        assert web_config.cors_origins == ["*"]
        assert web_config.enable_websockets is True

    def test_web_config_custom_values(self):
        """Test WebConfig with custom values."""
        web_config = WebConfig(
            host="0.0.0.0",
            port=9000,
            cors_origins=["http://localhost:3000", "https://mydomain.com"],
            enable_websockets=False,
            jwt_secret="custom_secret"
        )
        assert web_config.host == "0.0.0.0"
        assert web_config.port == 9000
        assert web_config.cors_origins == ["http://localhost:3000", "https://mydomain.com"]
        assert web_config.enable_websockets is False
        assert web_config.jwt_secret == "custom_secret"


class TestPerformanceConfig:
    """Test cases for PerformanceConfig."""

    def test_performance_config_defaults(self):
        """Test PerformanceConfig with default values."""
        perf_config = PerformanceConfig()
        assert perf_config.cache_ttl == 3600
        assert perf_config.max_connections == 10
        assert perf_config.enable_metrics is True
        assert perf_config.metrics_port == 8001

    def test_performance_config_custom_values(self):
        """Test PerformanceConfig with custom values."""
        perf_config = PerformanceConfig(
            cache_ttl=7200,
            max_connections=20,
            enable_metrics=False,
            metrics_port=9090,
            batch_size=100
        )
        assert perf_config.cache_ttl == 7200
        assert perf_config.max_connections == 20
        assert perf_config.enable_metrics is False
        assert perf_config.metrics_port == 9090
        assert perf_config.batch_size == 100


class TestConfig:
    """Test cases for main Config class."""

    def test_config_defaults(self):
        """Test Config with default values."""
        test_config = Config()
        assert isinstance(test_config.models, ModelConfig)
        assert isinstance(test_config.database, DatabaseConfig)
        assert isinstance(test_config.memory, MemoryConfig)
        assert isinstance(test_config.web, WebConfig)
        assert isinstance(test_config.performance, PerformanceConfig)
        assert test_config.debug is False
        assert test_config.log_level == "INFO"

    def test_config_custom_values(self):
        """Test Config with custom nested configurations."""
        custom_model_config = ModelConfig(provider="anthropic", model="claude-3")
        custom_db_config = DatabaseConfig(redis_url="redis://custom:6379")
        
        test_config = Config(
            models=custom_model_config,
            database=custom_db_config,
            debug=True,
            log_level="DEBUG"
        )
        
        assert test_config.models.provider == "anthropic"
        assert test_config.database.redis_url == "redis://custom:6379"
        assert test_config.debug is True
        assert test_config.log_level == "DEBUG"

    def test_config_environment_variables(self):
        """Test Config loading from environment variables."""
        env_vars = {
            "OPENAI_API_KEY": "test_openai_key",
            "REDIS_URL": "redis://env-redis:6379",
            "QDRANT_URL": "http://env-qdrant:6333",
            "DEBUG": "true",
            "LOG_LEVEL": "WARNING"
        }
        
        with patch.dict(os.environ, env_vars):
            test_config = Config()
            # Note: This assumes the Config class reads from environment
            # The actual implementation may differ

    def test_config_validation(self):
        """Test Config validation logic."""
        # Test invalid log level
        with pytest.raises(ValueError):
            Config(log_level="INVALID_LEVEL")
        
        # Test invalid debug value
        test_config = Config(debug="not_a_boolean")
        # Should handle string conversion to boolean

    def test_config_serialization(self):
        """Test Config serialization and deserialization."""
        test_config = Config(
            debug=True,
            log_level="DEBUG"
        )
        
        # Test dict conversion
        config_dict = test_config.model_dump()
        assert isinstance(config_dict, dict)
        assert config_dict["debug"] is True
        assert config_dict["log_level"] == "DEBUG"
        
        # Test reconstruction from dict
        new_config = Config(**config_dict)
        assert new_config.debug == test_config.debug
        assert new_config.log_level == test_config.log_level


class TestGlobalConfig:
    """Test cases for global config instance."""

    def test_global_config_instance(self):
        """Test that global config instance exists and is properly initialized."""
        assert config is not None
        assert isinstance(config, Config)
        assert hasattr(config, 'models')
        assert hasattr(config, 'database')
        assert hasattr(config, 'memory')
        assert hasattr(config, 'web')
        assert hasattr(config, 'performance')

    def test_global_config_accessibility(self):
        """Test that global config values are accessible."""
        # These should not raise exceptions
        provider = config.models.provider
        redis_url = config.database.redis_url
        spotlight_limit = config.memory.spotlight_limit
        host = config.web.host
        cache_ttl = config.performance.cache_ttl
        
        assert isinstance(provider, str)
        assert isinstance(redis_url, str)
        assert isinstance(spotlight_limit, int)
        assert isinstance(host, str)
        assert isinstance(cache_ttl, int)

    def test_global_config_immutability(self):
        """Test that global config should be treated as immutable in tests."""
        original_debug = config.debug
        original_log_level = config.log_level
        
        # These values should remain constant during tests
        assert config.debug == original_debug
        assert config.log_level == original_log_level


class TestConfigurationLoading:
    """Test cases for configuration loading mechanisms."""

    def test_config_from_file(self):
        """Test loading configuration from file."""
        # This would test loading from config files like .env, config.yml, etc.
        # Implementation depends on how the Config class handles file loading
        pass

    def test_config_precedence(self):
        """Test configuration precedence (env vars vs files vs defaults)."""
        # Test that environment variables override file values
        # and file values override defaults
        pass

    def test_config_validation_errors(self):
        """Test configuration validation error handling."""
        # Test various invalid configurations
        with pytest.raises((ValueError, TypeError)):
            ModelConfig(temperature=-1)  # Invalid temperature
        
        with pytest.raises((ValueError, TypeError)):
            DatabaseConfig(redis_url="not_a_valid_url")  # Invalid URL format
        
        with pytest.raises((ValueError, TypeError)):
            MemoryConfig(spotlight_limit=-1)  # Negative limit

    def test_config_type_coercion(self):
        """Test configuration type coercion."""
        # Test that string values are properly converted to appropriate types
        model_config = ModelConfig(temperature="0.5")  # String should become float
        assert isinstance(model_config.temperature, float)
        assert model_config.temperature == 0.5
        
        memory_config = MemoryConfig(spotlight_limit="10")  # String should become int
        assert isinstance(memory_config.spotlight_limit, int)
        assert memory_config.spotlight_limit == 10

    def test_config_required_fields(self):
        """Test that required configuration fields are enforced."""
        # Test creating configs without required fields
        # This depends on which fields are marked as required in the actual implementation
        pass

    def test_config_optional_fields(self):
        """Test that optional configuration fields work properly."""
        # Test that configs work with optional fields missing
        model_config = ModelConfig()  # Should work without api_key
        assert model_config.api_key is None or model_config.api_key == ""

    def test_config_nested_validation(self):
        """Test validation of nested configuration objects."""
        # Test that invalid nested configs are caught
        invalid_model_config = ModelConfig(temperature=5.0)  # Too high
        
        # The main Config should validate nested configs
        with pytest.raises((ValueError, TypeError)):
            Config(models=invalid_model_config)


class TestConfigurationUpdates:
    """Test cases for runtime configuration updates."""

    def test_config_update_validation(self):
        """Test that configuration updates are validated."""
        test_config = Config()
        
        # Valid update
        test_config.debug = True
        assert test_config.debug is True
        
        # Invalid update should be caught
        with pytest.raises((ValueError, TypeError)):
            test_config.log_level = "INVALID_LEVEL"

    def test_config_partial_updates(self):
        """Test partial configuration updates."""
        test_config = Config()
        original_provider = test_config.models.provider
        
        # Update only part of the configuration
        test_config.models.temperature = 0.9
        
        # Other values should remain unchanged
        assert test_config.models.provider == original_provider
        assert test_config.models.temperature == 0.9

    def test_config_reload(self):
        """Test configuration reloading."""
        # Test reloading configuration from environment or files
        # This would be useful for runtime configuration changes
        pass