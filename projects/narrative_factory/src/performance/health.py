"""
Health monitoring system with comprehensive SLA tracking
CodeFarm T04 Production Optimization Implementation
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import redis.asyncio as redis
from qdrant_client import AsyncQdrantClient
import httpx
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Component type enumeration"""
    DATABASE = "database"
    CACHE = "cache"
    API = "api"
    AGENT = "agent"
    SERVICE = "service"
    SYSTEM = "system"


@dataclass
class ComponentHealth:
    """Component health status data model"""
    name: str
    component_type: ComponentType
    status: HealthStatus
    last_check: datetime
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    check_count: int = 0
    error_count: int = 0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.check_count == 0:
            return 0.0
        return ((self.check_count - self.error_count) / self.check_count) * 100
    
    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy"""
        return self.status == HealthStatus.HEALTHY
    
    def update_status(self, status: HealthStatus, response_time: Optional[float] = None, error_message: Optional[str] = None):
        """Update component health status"""
        self.status = status
        self.last_check = datetime.now()
        self.response_time = response_time
        self.error_message = error_message
        self.check_count += 1
        
        if status != HealthStatus.HEALTHY:
            self.error_count += 1


@dataclass
class SLAMetrics:
    """SLA tracking metrics"""
    availability_target: float = 99.9  # 99.9% uptime
    response_time_target: float = 2.0  # 2 seconds max
    error_rate_target: float = 0.1     # 0.1% error rate max
    
    # Current metrics
    current_availability: float = 100.0
    current_response_time: float = 0.0
    current_error_rate: float = 0.0
    
    @property
    def availability_sla_met(self) -> bool:
        return self.current_availability >= self.availability_target
    
    @property
    def response_time_sla_met(self) -> bool:
        return self.current_response_time <= self.response_time_target
    
    @property
    def error_rate_sla_met(self) -> bool:
        return self.current_error_rate <= self.error_rate_target
    
    @property
    def overall_sla_met(self) -> bool:
        return all([
            self.availability_sla_met,
            self.response_time_sla_met, 
            self.error_rate_sla_met
        ])


class HealthMonitorSettings(BaseSettings):
    """Health monitoring configuration"""
    enabled: bool = True
    check_interval: int = 30  # seconds
    timeout: float = 10.0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # SLA settings
    availability_target: float = 99.9
    response_time_target: float = 2.0
    error_rate_target: float = 0.1
    
    # Component-specific settings
    redis_enabled: bool = True
    qdrant_enabled: bool = True
    agents_enabled: bool = True
    
    class Config:
        env_prefix = "HEALTH_"


class HealthCheck:
    """Base health check class"""
    
    def __init__(self, name: str, component_type: ComponentType):
        self.name = name
        self.component_type = component_type
    
    async def check(self) -> ComponentHealth:
        """Perform health check - to be implemented by subclasses"""
        raise NotImplementedError


class RedisHealthCheck(HealthCheck):
    """Redis health check implementation"""
    
    def __init__(self, redis_client: redis.Redis, name: str = "redis"):
        super().__init__(name, ComponentType.CACHE)
        self.redis_client = redis_client
    
    async def check(self) -> ComponentHealth:
        """Check Redis health"""
        start_time = time.time()
        
        try:
            await self.redis_client.ping()
            response_time = time.time() - start_time
            
            # Get additional metadata
            info = await self.redis_client.info()
            metadata = {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
            
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata=metadata
            )
            
            return health
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=str(e)
            )
            return health


class QdrantHealthCheck(HealthCheck):
    """Qdrant health check implementation"""
    
    def __init__(self, qdrant_client: AsyncQdrantClient, name: str = "qdrant"):
        super().__init__(name, ComponentType.DATABASE)
        self.qdrant_client = qdrant_client
    
    async def check(self) -> ComponentHealth:
        """Check Qdrant health"""
        start_time = time.time()
        
        try:
            collections = await self.qdrant_client.get_collections()
            response_time = time.time() - start_time
            
            metadata = {
                "collections_count": len(collections.collections),
                "collections": [col.name for col in collections.collections]
            }
            
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                metadata=metadata
            )
            
            return health
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=str(e)
            )
            return health


class AgentHealthCheck(HealthCheck):
    """Agent health check implementation"""
    
    def __init__(self, agent_name: str, health_callback: Optional[Callable] = None):
        super().__init__(agent_name, ComponentType.AGENT)
        self.health_callback = health_callback
    
    async def check(self) -> ComponentHealth:
        """Check agent health"""
        start_time = time.time()
        
        try:
            if self.health_callback:
                if asyncio.iscoroutinefunction(self.health_callback):
                    result = await self.health_callback()
                else:
                    result = self.health_callback()
                
                response_time = time.time() - start_time
                
                if result:
                    health = ComponentHealth(
                        name=self.name,
                        component_type=self.component_type,
                        status=HealthStatus.HEALTHY,
                        last_check=datetime.now(),
                        response_time=response_time,
                        metadata={"callback_result": result}
                    )
                else:
                    health = ComponentHealth(
                        name=self.name,
                        component_type=self.component_type,
                        status=HealthStatus.DEGRADED,
                        last_check=datetime.now(),
                        response_time=response_time,
                        error_message="Health callback returned False"
                    )
            else:
                # Default: assume healthy if no callback
                health = ComponentHealth(
                    name=self.name,
                    component_type=self.component_type,
                    status=HealthStatus.HEALTHY,
                    last_check=datetime.now(),
                    response_time=0.0,
                    metadata={"default_check": True}
                )
            
            return health
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=str(e)
            )
            return health


class SystemHealthCheck(HealthCheck):
    """System health check implementation"""
    
    def __init__(self, name: str = "system"):
        super().__init__(name, ComponentType.SYSTEM)
    
    async def check(self) -> ComponentHealth:
        """Check system health"""
        start_time = time.time()
        
        try:
            import psutil
            
            # Get system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            disk = psutil.disk_usage('/')
            
            metadata = {
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "cpu_percent": cpu_percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free": disk.free
            }
            
            # Determine health based on resource usage
            status = HealthStatus.HEALTHY
            if memory.percent > 90 or cpu_percent > 90:
                status = HealthStatus.DEGRADED
            if memory.percent > 95 or cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
            
            response_time = time.time() - start_time
            
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=status,
                last_check=datetime.now(),
                response_time=response_time,
                metadata=metadata
            )
            
            return health
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=self.name,
                component_type=self.component_type,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_message=str(e)
            )
            return health


class HealthMonitor:
    """Comprehensive health monitoring system with SLA tracking"""
    
    def __init__(self, settings: Optional[HealthMonitorSettings] = None):
        self.settings = settings or HealthMonitorSettings()
        self.health_checks: Dict[str, HealthCheck] = {}
        self.component_health: Dict[str, ComponentHealth] = {}
        self.sla_metrics = SLAMetrics(
            availability_target=self.settings.availability_target,
            response_time_target=self.settings.response_time_target,
            error_rate_target=self.settings.error_rate_target
        )
        self.monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
    def register_health_check(self, health_check: HealthCheck):
        """Register a health check"""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Registered health check: {health_check.name} ({health_check.component_type.value})")
    
    def register_redis_check(self, redis_client: redis.Redis, name: str = "redis"):
        """Register Redis health check"""
        if self.settings.redis_enabled:
            check = RedisHealthCheck(redis_client, name)
            self.register_health_check(check)
    
    def register_qdrant_check(self, qdrant_client: AsyncQdrantClient, name: str = "qdrant"):
        """Register Qdrant health check"""
        if self.settings.qdrant_enabled:
            check = QdrantHealthCheck(qdrant_client, name)
            self.register_health_check(check)
    
    def register_agent_check(self, agent_name: str, health_callback: Optional[Callable] = None):
        """Register agent health check"""
        if self.settings.agents_enabled:
            check = AgentHealthCheck(agent_name, health_callback)
            self.register_health_check(check)
    
    def register_system_check(self, name: str = "system"):
        """Register system health check"""
        check = SystemHealthCheck(name)
        self.register_health_check(check)
    
    async def run_health_check(self, name: str) -> Optional[ComponentHealth]:
        """Run a specific health check"""
        if name not in self.health_checks:
            logger.warning(f"Health check '{name}' not found")
            return None
        
        try:
            health = await self.health_checks[name].check()
            self.component_health[name] = health
            logger.debug(f"Health check '{name}': {health.status.value} ({health.response_time:.3f}s)")
            return health
        except Exception as e:
            logger.error(f"Health check '{name}' failed: {e}")
            # Create error health status
            health = ComponentHealth(
                name=name,
                component_type=self.health_checks[name].component_type,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                error_message=str(e)
            )
            self.component_health[name] = health
            return health
    
    async def run_all_health_checks(self) -> Dict[str, ComponentHealth]:
        """Run all registered health checks"""
        results = {}
        
        for name in self.health_checks:
            health = await self.run_health_check(name)
            if health:
                results[name] = health
        
        # Update SLA metrics
        await self._update_sla_metrics()
        
        return results
    
    async def _update_sla_metrics(self):
        """Update SLA metrics based on current health status"""
        if not self.component_health:
            return
        
        # Calculate availability
        healthy_components = sum(
            1 for health in self.component_health.values() 
            if health.status == HealthStatus.HEALTHY
        )
        total_components = len(self.component_health)
        self.sla_metrics.current_availability = (healthy_components / total_components) * 100
        
        # Calculate average response time
        response_times = [
            health.response_time for health in self.component_health.values()
            if health.response_time is not None
        ]
        if response_times:
            self.sla_metrics.current_response_time = sum(response_times) / len(response_times)
        
        # Calculate error rate
        total_checks = sum(health.check_count for health in self.component_health.values())
        total_errors = sum(health.error_count for health in self.component_health.values())
        if total_checks > 0:
            self.sla_metrics.current_error_rate = (total_errors / total_checks) * 100
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        if not self.component_health:
            await self.run_all_health_checks()
        
        healthy_count = sum(
            1 for health in self.component_health.values()
            if health.status == HealthStatus.HEALTHY
        )
        degraded_count = sum(
            1 for health in self.component_health.values()
            if health.status == HealthStatus.DEGRADED
        )
        unhealthy_count = sum(
            1 for health in self.component_health.values()
            if health.status == HealthStatus.UNHEALTHY
        )
        
        total_components = len(self.component_health)
        
        # Determine overall status
        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            "overall_status": overall_status.value,
            "components": {
                "total": total_components,
                "healthy": healthy_count,
                "degraded": degraded_count,
                "unhealthy": unhealthy_count
            },
            "sla_metrics": {
                "availability": {
                    "current": self.sla_metrics.current_availability,
                    "target": self.sla_metrics.availability_target,
                    "met": self.sla_metrics.availability_sla_met
                },
                "response_time": {
                    "current": self.sla_metrics.current_response_time,
                    "target": self.sla_metrics.response_time_target,
                    "met": self.sla_metrics.response_time_sla_met
                },
                "error_rate": {
                    "current": self.sla_metrics.current_error_rate,
                    "target": self.sla_metrics.error_rate_target,
                    "met": self.sla_metrics.error_rate_sla_met
                },
                "overall_sla_met": self.sla_metrics.overall_sla_met
            },
            "last_check": max(
                (health.last_check for health in self.component_health.values()),
                default=datetime.now()
            ).isoformat()
        }
    
    async def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """Get health status for specific component"""
        return self.component_health.get(name)
    
    async def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """Get health status for all components"""
        return self.component_health.copy()
    
    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if not self.settings.enabled or self._running:
            return
        
        self._running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Health monitoring started (interval: {self.settings.check_interval}s)")
    
    async def stop_monitoring(self):
        """Stop continuous health monitoring"""
        self._running = False
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self):
        """Continuous monitoring loop"""
        while self._running:
            try:
                await self.run_all_health_checks()
                await asyncio.sleep(self.settings.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                await asyncio.sleep(self.settings.check_interval)


# Global health monitor instance
_health_monitor: Optional[HealthMonitor] = None


async def get_health_monitor() -> HealthMonitor:
    """Get global health monitor instance"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor