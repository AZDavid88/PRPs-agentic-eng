"""
Health check and monitoring system for the Narrative Factory application.

Provides comprehensive health monitoring, system validation, and performance metrics
for all application components.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from src.config import config
from src.exceptions import (
    error_handler,
)
from src.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Individual health check result."""
    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    checks: List[HealthCheck]
    timestamp: datetime
    uptime_seconds: float
    version: str = "0.1.0"


class HealthMonitor:
    """Centralized health monitoring system."""

    def __init__(self):
        """Initialize health monitor."""
        self.start_time = time.time()
        self.check_registry: Dict[str, Callable] = {}
        self.last_health_check: Optional[SystemHealth] = None
        self.health_history: List[SystemHealth] = []
        self.max_history = 100

        # Register built-in health checks
        self._register_builtin_checks()

    def _register_builtin_checks(self):
        """Register built-in health checks."""
        self.register_check("configuration", self._check_configuration)
        self.register_check("database", self._check_database)
        self.register_check("ai_models", self._check_ai_models)
        self.register_check("file_system", self._check_file_system)
        self.register_check("memory", self._check_memory)
        self.register_check("error_rates", self._check_error_rates)

    def register_check(self, name: str, check_func: Callable) -> None:
        """Register a health check function."""
        self.check_registry[name] = check_func
        logger.debug(f"Registered health check: {name}")

    async def perform_health_check(self, include_detailed: bool = False) -> SystemHealth:
        """Perform comprehensive health check."""
        checks = []
        start_time = time.time()

        # Run all registered checks
        for name, check_func in self.check_registry.items():
            try:
                check_start = time.time()
                result = await self._run_check(check_func, name, include_detailed)
                check_duration = (time.time() - check_start) * 1000

                checks.append(HealthCheck(
                    name=name,
                    status=result.get("status", HealthStatus.UNKNOWN),
                    message=result.get("message", "No message"),
                    duration_ms=check_duration,
                    timestamp=datetime.utcnow(),
                    details=result.get("details") if include_detailed else None
                ))

            except Exception as e:
                error_handler.handle_error(e, {"health_check": name})
                checks.append(HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(e)}",
                    duration_ms=(time.time() - start_time) * 1000,
                    timestamp=datetime.utcnow(),
                    details={"error": str(e)} if include_detailed else None
                ))

        # Determine overall status
        overall_status = self._determine_overall_status(checks)

        # Create system health object
        system_health = SystemHealth(
            status=overall_status,
            checks=checks,
            timestamp=datetime.utcnow(),
            uptime_seconds=time.time() - self.start_time
        )

        # Update history
        self.last_health_check = system_health
        self.health_history.append(system_health)
        if len(self.health_history) > self.max_history:
            self.health_history.pop(0)

        logger.info(f"Health check completed: {overall_status.value}")
        return system_health

    async def _run_check(self, check_func: Callable, name: str, include_detailed: bool) -> Dict[str, Any]:
        """Run a single health check with timeout."""
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await asyncio.wait_for(
                    check_func(include_detailed),
                    timeout=config.app.request_timeout
                )
            else:
                result = check_func(include_detailed)

            return result
        except asyncio.TimeoutError:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Health check {name} timed out",
                "details": {"timeout_seconds": config.app.request_timeout}
            }

    def _determine_overall_status(self, checks: List[HealthCheck]) -> HealthStatus:
        """Determine overall system health from individual checks."""
        if not checks:
            return HealthStatus.UNKNOWN

        unhealthy_count = sum(1 for check in checks if check.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for check in checks if check.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            return HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    async def _check_configuration(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            issues = config.validate_all()

            if issues:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"Configuration issues found: {len(issues)}",
                    "details": {"issues": issues} if include_detailed else None
                }
            else:
                return {
                    "status": HealthStatus.HEALTHY,
                    "message": "Configuration is valid",
                    "details": config.get_health_status() if include_detailed else None
                }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Configuration check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _check_database(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check database connectivity and health."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.exceptions import UnexpectedResponse

            client = QdrantClient(
                url=config.qdrant.url,
                api_key=config.qdrant.api_key,
                timeout=config.qdrant.timeout
            )

            # Test connection
            collections = client.get_collections()

            details = {}
            if include_detailed:
                details = {
                    "collections_count": len(collections.collections),
                    "url": config.qdrant.url,
                    "timeout": config.qdrant.timeout
                }

            return {
                "status": HealthStatus.HEALTHY,
                "message": "Database connection healthy",
                "details": details
            }

        except UnexpectedResponse as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Database connection failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }
        except Exception as e:
            return {
                "status": HealthStatus.DEGRADED,
                "message": f"Database check error: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _check_ai_models(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check AI model availability and configuration."""
        try:
            issues = []

            # Check API keys
            if not config.models.has_required_keys():
                issues.append("No valid API keys found")

            # Check model configurations
            if not config.models.generation_model:
                issues.append("No generation model configured")

            if issues:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"AI model issues: {'; '.join(issues)}",
                    "details": {"issues": issues} if include_detailed else None
                }

            details = {}
            if include_detailed:
                details = {
                    "generation_model": config.models.generation_model,
                    "embedding_model": config.models.embedding_model,
                    "keys_available": {
                        "gemini": bool(config.models.gemini_api_key),
                        "openai": bool(config.models.openai_api_key),
                        "jina": bool(config.models.jina_api_key)
                    }
                }

            return {
                "status": HealthStatus.HEALTHY,
                "message": "AI models configured correctly",
                "details": details
            }

        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"AI model check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _check_file_system(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check file system accessibility."""
        try:
            from src.config import (
                LOGS_DIR,
                MEMORY_BOOTSTRAP_DIR,
                OUTPUTS_DIR,
                PERSONAS_DIR,
                PROJECT_ROOT,
                SRC_ROOT,
            )

            paths_to_check = [
                ("PROJECT_ROOT", PROJECT_ROOT),
                ("SRC_ROOT", SRC_ROOT),
                ("MEMORY_BOOTSTRAP_DIR", MEMORY_BOOTSTRAP_DIR),
                ("OUTPUTS_DIR", OUTPUTS_DIR),
                ("PERSONAS_DIR", PERSONAS_DIR),
                ("LOGS_DIR", LOGS_DIR)
            ]

            missing_paths = []
            path_details = {}

            for name, path in paths_to_check:
                if not path.exists():
                    missing_paths.append(f"{name}: {path}")
                elif include_detailed:
                    path_details[name] = {
                        "path": str(path),
                        "exists": True,
                        "is_directory": path.is_dir(),
                        "readable": path.is_file() and path.stat().st_size > 0 if path.is_file() else True
                    }

            if missing_paths:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "message": f"Missing paths: {'; '.join(missing_paths)}",
                    "details": {"missing_paths": missing_paths} if include_detailed else None
                }

            return {
                "status": HealthStatus.HEALTHY,
                "message": "File system accessible",
                "details": path_details if include_detailed else None
            }

        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"File system check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _check_memory(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check memory usage and availability."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Check memory usage
            memory_usage_percent = memory.percent
            disk_usage_percent = disk.percent

            status = HealthStatus.HEALTHY
            issues = []

            if memory_usage_percent > 90:
                status = HealthStatus.UNHEALTHY
                issues.append("High memory usage")
            elif memory_usage_percent > 80:
                status = HealthStatus.DEGRADED
                issues.append("Elevated memory usage")

            if disk_usage_percent > 95:
                status = HealthStatus.UNHEALTHY
                issues.append("High disk usage")
            elif disk_usage_percent > 85:
                status = HealthStatus.DEGRADED
                issues.append("Elevated disk usage")

            message = "Memory and disk usage normal"
            if issues:
                message = f"Resource issues: {'; '.join(issues)}"

            details = {}
            if include_detailed:
                details = {
                    "memory_usage_percent": memory_usage_percent,
                    "memory_total_gb": round(memory.total / (1024**3), 2),
                    "memory_available_gb": round(memory.available / (1024**3), 2),
                    "disk_usage_percent": disk_usage_percent,
                    "disk_total_gb": round(disk.total / (1024**3), 2),
                    "disk_free_gb": round(disk.free / (1024**3), 2)
                }

            return {
                "status": status,
                "message": message,
                "details": details
            }

        except ImportError:
            return {
                "status": HealthStatus.UNKNOWN,
                "message": "psutil not available for memory monitoring",
                "details": None
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Memory check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    async def _check_error_rates(self, include_detailed: bool = False) -> Dict[str, Any]:
        """Check error rates and patterns."""
        try:
            error_stats = error_handler.get_error_stats()
            total_errors = error_stats.get("total_errors", 0)

            # Simple error rate check
            if total_errors > 100:
                status = HealthStatus.UNHEALTHY
                message = f"High error count: {total_errors}"
            elif total_errors > 50:
                status = HealthStatus.DEGRADED
                message = f"Elevated error count: {total_errors}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Error count normal: {total_errors}"

            details = {}
            if include_detailed:
                details = error_stats

            return {
                "status": status,
                "message": message,
                "details": details
            }

        except Exception as e:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Error rate check failed: {str(e)}",
                "details": {"error": str(e)} if include_detailed else None
            }

    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of recent health checks."""
        if not self.last_health_check:
            return {"status": "no_checks_performed"}

        recent_checks = self.health_history[-10:] if len(self.health_history) > 10 else self.health_history

        return {
            "current_status": self.last_health_check.status.value,
            "uptime_seconds": self.last_health_check.uptime_seconds,
            "last_check": self.last_health_check.timestamp.isoformat(),
            "recent_history": [
                {
                    "timestamp": check.timestamp.isoformat(),
                    "status": check.status.value,
                    "check_count": len(check.checks)
                }
                for check in recent_checks
            ]
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert health monitor state to dictionary."""
        return {
            "start_time": self.start_time,
            "uptime_seconds": time.time() - self.start_time,
            "registered_checks": list(self.check_registry.keys()),
            "health_history_count": len(self.health_history),
            "last_health_check": self.last_health_check.status.value if self.last_health_check else None
        }


# Global health monitor instance
health_monitor = HealthMonitor()


async def get_health_status(include_detailed: bool = False) -> SystemHealth:
    """Get current system health status."""
    return await health_monitor.perform_health_check(include_detailed)


def get_health_summary() -> Dict[str, Any]:
    """Get health summary for monitoring."""
    return health_monitor.get_health_summary()


def register_health_check(name: str, check_func: Callable) -> None:
    """Register a custom health check."""
    health_monitor.register_check(name, check_func)


logger.info("Health monitoring system initialized")
