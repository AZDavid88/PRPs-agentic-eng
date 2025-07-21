"""
Centralized configuration for the Narrative Factory application.

This file defines settings, paths, and model configurations using advanced Pydantic patterns
for validation, environment management, and production-ready configuration handling.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load environment variables from .env file
load_dotenv()


class LogLevel(str, Enum):
    """Valid logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


# --- Project Structure ---
# Defines the layout of the project directory.
# Using Path objects for OS-agnostic compatibility.
PROJECT_ROOT = Path(__file__).parent.parent
SRC_ROOT = Path(__file__).parent
MEMORY_BOOTSTRAP_DIR = PROJECT_ROOT / "memory_bootstrap"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
CHAPTERS_DIR = OUTPUTS_DIR / "chapters"
LOGS_DIR = OUTPUTS_DIR / "logs"
STATE_DIR = OUTPUTS_DIR / "state"
PERSONAS_DIR = SRC_ROOT / "agents" / "prompts"

# Create directories if they don't exist
for path in [OUTPUTS_DIR, CHAPTERS_DIR, LOGS_DIR, STATE_DIR]:
    path.mkdir(exist_ok=True, parents=True)


class ModelSettings(BaseSettings):
    """Configuration for AI models with validation and fallbacks."""

    generation_model: str = Field(
        default="gemini-2.5-flash",
        description="Primary model for story generation"
    )
    canonist_model: str = Field(
        default="gemini-2.5-flash",
        description="Model for canonist agent operations"
    )
    embedding_provider: str = Field(
        default="jina",
        description="Provider for embeddings"
    )
    embedding_model: str = Field(
        default="jina-embeddings-v2-base-en",
        description="Specific embedding model"
    )

    # API Keys with secure handling
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Gemini API key for Google models"
    )
    jina_api_key: Optional[str] = Field(
        default=None,
        description="Jina API key for embeddings"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )

    # Model configuration
    max_tokens: int = Field(
        default=4096,
        ge=1,
        le=8192,
        description="Maximum tokens for generation"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for generation"
    )
    timeout_seconds: int = Field(
        default=60,
        ge=5,
        le=300,
        description="API call timeout in seconds"
    )

    @field_validator('gemini_api_key', mode='before')
    @classmethod
    def validate_gemini_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate Gemini API key format."""
        if v and not v.startswith('AIza'):
            logging.warning("Gemini API key should start with 'AIza'")
        return v

    @field_validator('openai_api_key', mode='before')
    @classmethod
    def validate_openai_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate OpenAI API key format."""
        if v and not v.startswith('sk-'):
            logging.warning("OpenAI API key should start with 'sk-'")
        return v

    def has_required_keys(self) -> bool:
        """Check if required API keys are present."""
        return bool(self.gemini_api_key or self.openai_api_key)

    model_config = SettingsConfigDict(
        env_prefix="MODEL_",
        case_sensitive=False
    )


class QdrantSettings(BaseSettings):
    """Configuration for Qdrant vector database with connection validation."""

    url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key for authentication"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Connection timeout in seconds"
    )
    retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of retry attempts"
    )

    # Collection names
    world_bible_collection: str = Field(
        default="world_bible",
        description="Collection for world building documents"
    )
    story_so_far_collection: str = Field(
        default="story_so_far",
        description="Collection for story progress tracking"
    )

    # Vector configuration
    vector_size: int = Field(
        default=768,
        ge=100,
        le=2048,
        description="Vector embedding dimension"
    )
    distance_metric: str = Field(
        default="cosine",
        description="Distance metric for similarity search"
    )

    @property
    def collection_mappings(self) -> dict[str, str]:
        """Dynamic collection mappings."""
        return {
            "character_sheets": self.world_bible_collection,
            "lore_documents": self.world_bible_collection,
            "style_guides": self.world_bible_collection,
            "tension_reports": self.story_so_far_collection,
            "chapter_summaries": self.story_so_far_collection,
        }

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate Qdrant URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator('distance_metric')
    @classmethod
    def validate_distance_metric(cls, v: str) -> str:
        """Validate distance metric."""
        valid_metrics = ['cosine', 'dot', 'euclidean']
        if v not in valid_metrics:
            raise ValueError(f"Distance metric must be one of: {valid_metrics}")
        return v

    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        case_sensitive=False
    )


class AppSettings(BaseSettings):
    """General application settings with environment management."""

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    log_file: Path = Field(
        default=LOGS_DIR / "narrative_factory.log",
        description="Log file path"
    )
    log_rotation: bool = Field(
        default=True,
        description="Enable log file rotation"
    )
    log_max_size: str = Field(
        default="10MB",
        description="Maximum log file size before rotation"
    )
    log_backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of log backup files to keep"
    )

    # Performance settings
    max_concurrent_tasks: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent async tasks"
    )
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="HTTP request timeout in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Default retry attempts for operations"
    )

    # Health check settings
    health_check_interval: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Health check interval in seconds"
    )

    @model_validator(mode='before')
    def validate_environment_settings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate environment-specific settings."""
        env = values.get('environment')

        if env == Environment.PRODUCTION:
            # Production-specific validations
            if values.get('debug', False):
                values['debug'] = False
                logging.warning("Debug mode disabled in production")

            if values.get('log_level') == LogLevel.DEBUG:
                values['log_level'] = LogLevel.INFO
                logging.warning("Log level changed from DEBUG to INFO in production")

        elif env == Environment.DEVELOPMENT:
            # Development-specific settings
            values['debug'] = True

        return values

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        case_sensitive=False
    )


class ConfigManager:
    """Centralized configuration manager with validation and health checks."""

    def __init__(self) -> None:
        """Initialize configuration manager."""
        self.models = ModelSettings()
        self.qdrant = QdrantSettings()
        self.app = AppSettings()
        self._validated = False

    def validate_all(self) -> list[str]:
        """Validate all configuration settings and return any issues."""
        issues = []

        # Validate model settings
        if not self.models.has_required_keys():
            issues.append("No valid API keys found for AI models")

        # Validate paths
        required_paths = [
            PROJECT_ROOT,
            SRC_ROOT,
            MEMORY_BOOTSTRAP_DIR,
            OUTPUTS_DIR,
            PERSONAS_DIR
        ]

        for path in required_paths:
            if not path.exists():
                issues.append(f"Required path does not exist: {path}")

        # Environment-specific validations
        if self.app.is_production:
            if self.app.debug:
                issues.append("Debug mode should not be enabled in production")

            if not self.qdrant.api_key and self.qdrant.url.startswith('http://'):
                issues.append("Production should use HTTPS and API key for Qdrant")

        self._validated = len(issues) == 0
        return issues

    def get_health_status(self) -> dict[str, Any]:
        """Get comprehensive health status of configuration."""
        return {
            "validated": self._validated,
            "environment": self.app.environment.value,
            "debug_mode": self.app.debug,
            "log_level": self.app.log_level.value,
            "model_keys_available": {
                "gemini": bool(self.models.gemini_api_key),
                "openai": bool(self.models.openai_api_key),
                "jina": bool(self.models.jina_api_key),
            },
            "qdrant_configured": bool(self.qdrant.url),
            "paths_exist": all(
                path.exists() for path in [
                    PROJECT_ROOT, SRC_ROOT, MEMORY_BOOTSTRAP_DIR,
                    OUTPUTS_DIR, PERSONAS_DIR
                ]
            ),
        }


# --- Global configuration instance ---
config = ConfigManager()

# --- Legacy compatibility (to be deprecated) ---
models = config.models
qdrant = config.qdrant
app = config.app
