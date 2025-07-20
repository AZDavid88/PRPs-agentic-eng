"""
Performance monitoring with Prometheus integration
CodeFarm T04 Production Optimization Implementation
"""
import asyncio
import logging
import time
import psutil
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from contextlib import asynccontextmanager
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import redis.asyncio as redis
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class MonitoringSettings(BaseSettings):
    """Monitoring configuration settings"""
    enabled: bool = True
    metrics_namespace: str = "narrative_factory"
    collect_system_metrics: bool = True
    redis_metrics_enabled: bool = True
    agent_metrics_enabled: bool = True
    
    class Config:
        env_prefix = "MONITORING_"


@dataclass
class MetricDefinition:
    """Definition for a Prometheus metric"""
    name: str
    description: str
    metric_type: str  # counter, histogram, gauge
    labels: List[str] = None
    buckets: List[float] = None  # For histograms


class PerformanceMonitor:
    """Centralized performance monitoring with Prometheus metrics"""
    
    def __init__(self, settings: Optional[MonitoringSettings] = None, registry: Optional[CollectorRegistry] = None):
        self.settings = settings or MonitoringSettings()
        self.registry = registry or CollectorRegistry()
        self._metrics: Dict[str, Any] = {}
        self._initialized = False
        
        # Initialize core metrics if enabled
        if self.settings.enabled:
            self._initialize_metrics()
    
    def _initialize_metrics(self):
        """Initialize all Prometheus metrics"""
        
        # Request metrics
        self._metrics['request_count'] = Counter(
            f"{self.settings.metrics_namespace}_requests_total",
            "Total number of requests",
            ["method", "endpoint", "status"],
            registry=self.registry
        )
        
        self._metrics['request_duration'] = Histogram(
            f"{self.settings.metrics_namespace}_request_duration_seconds",
            "Request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
            registry=self.registry
        )
        
        # Agent execution metrics
        if self.settings.agent_metrics_enabled:
            self._metrics['agent_execution_time'] = Histogram(
                f"{self.settings.metrics_namespace}_agent_execution_seconds",
                "Agent execution time in seconds",
                ["agent_type"],
                buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
                registry=self.registry
            )
            
            self._metrics['agent_execution_count'] = Counter(
                f"{self.settings.metrics_namespace}_agent_execution_total",
                "Total agent executions",
                ["agent_type", "status"],
                registry=self.registry
            )
        
        # WebSocket metrics
        self._metrics['active_connections'] = Gauge(
            f"{self.settings.metrics_namespace}_active_connections",
            "Number of active WebSocket connections",
            registry=self.registry
        )
        
        self._metrics['websocket_disconnections'] = Counter(
            f"{self.settings.metrics_namespace}_websocket_disconnections_total",
            "Total WebSocket disconnections",
            ["reason"],
            registry=self.registry
        )
        
        # Cache metrics
        self._metrics['cache_hits'] = Counter(
            f"{self.settings.metrics_namespace}_cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=self.registry
        )
        
        self._metrics['cache_misses'] = Counter(
            f"{self.settings.metrics_namespace}_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=self.registry
        )
        
        # Memory retrieval metrics
        self._metrics['memory_retrieval_duration'] = Histogram(
            f"{self.settings.metrics_namespace}_memory_retrieval_duration_seconds",
            "Memory retrieval duration in seconds",
            ["retrieval_type"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry
        )
        
        # System metrics
        if self.settings.collect_system_metrics:
            self._metrics['memory_usage'] = Gauge(
                f"{self.settings.metrics_namespace}_memory_usage_bytes",
                "Memory usage in bytes",
                registry=self.registry
            )
            
            self._metrics['cpu_usage'] = Gauge(
                f"{self.settings.metrics_namespace}_cpu_usage_percent",
                "CPU usage percentage",
                registry=self.registry
            )
            
        self._initialized = True
        logger.info("Performance monitoring metrics initialized")
    
    def record_request(self, method: str, endpoint: str, status: str, duration: float):
        """Record HTTP request metrics"""
        if not self._initialized:
            return
            
        self._metrics['request_count'].labels(
            method=method,
            endpoint=endpoint, 
            status=status
        ).inc()
        
        self._metrics['request_duration'].labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_agent_execution(self, agent_type: str, duration: float, status: str = "success"):
        """Record agent execution metrics"""
        if not self._initialized or not self.settings.agent_metrics_enabled:
            return
            
        self._metrics['agent_execution_time'].labels(
            agent_type=agent_type
        ).observe(duration)
        
        self._metrics['agent_execution_count'].labels(
            agent_type=agent_type,
            status=status
        ).inc()
    
    def record_cache_hit(self, cache_type: str = "default"):
        """Record cache hit"""
        if not self._initialized:
            return
        self._metrics['cache_hits'].labels(cache_type=cache_type).inc()
    
    def record_cache_miss(self, cache_type: str = "default"):
        """Record cache miss"""
        if not self._initialized:
            return
        self._metrics['cache_misses'].labels(cache_type=cache_type).inc()
    
    def record_memory_retrieval(self, retrieval_type: str, duration: float):
        """Record memory retrieval duration"""
        if not self._initialized:
            return
        self._metrics['memory_retrieval_duration'].labels(
            retrieval_type=retrieval_type
        ).observe(duration)
    
    def update_websocket_connections(self, count: int):
        """Update active WebSocket connection count"""
        if not self._initialized:
            return
        self._metrics['active_connections'].set(count)
    
    def record_websocket_disconnection(self, reason: str = "unknown"):
        """Record WebSocket disconnection"""
        if not self._initialized:
            return
        self._metrics['websocket_disconnections'].labels(reason=reason).inc()
    
    async def update_system_metrics(self):
        """Update system resource metrics"""
        if not self._initialized or not self.settings.collect_system_metrics:
            return
            
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            self._metrics['memory_usage'].set(memory.used)
            
            # CPU usage (non-blocking)
            cpu_percent = psutil.cpu_percent(interval=None)
            self._metrics['cpu_usage'].set(cpu_percent)
            
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    @asynccontextmanager
    async def time_operation(self, operation_name: str, labels: Dict[str, str] = None):
        """Context manager for timing operations"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            
            # Log the operation duration
            logger.debug(f"Operation '{operation_name}' took {duration:.3f}s")
            
            # Record custom metric if available
            if operation_name in self._metrics:
                metric = self._metrics[operation_name]
                if hasattr(metric, 'observe'):  # Histogram
                    if labels:
                        metric.labels(**labels).observe(duration)
                    else:
                        metric.observe(duration)
    
    def get_metrics_data(self) -> bytes:
        """Get Prometheus metrics in text format"""
        if not self._initialized:
            return b""
        return generate_latest(self.registry)
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary with key metrics"""
        if not self._initialized:
            return {}
        
        try:
            summary = {
                "monitoring_enabled": True,
                "metrics_collected": len(self._metrics),
                "registry_name": self.settings.metrics_namespace
            }
            
            # Add system metrics if available
            if self.settings.collect_system_metrics:
                memory = psutil.virtual_memory()
                summary.update({
                    "system_memory": {
                        "total": memory.total,
                        "used": memory.used,
                        "percent": memory.percent
                    },
                    "cpu_percent": psutil.cpu_percent(interval=None)
                })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {"error": str(e)}
    
    def create_custom_metric(self, definition: MetricDefinition) -> Any:
        """Create a custom metric dynamically"""
        if not self._initialized:
            return None
            
        full_name = f"{self.settings.metrics_namespace}_{definition.name}"
        
        if definition.metric_type == "counter":
            metric = Counter(
                full_name,
                definition.description,
                definition.labels or [],
                registry=self.registry
            )
        elif definition.metric_type == "histogram":
            metric = Histogram(
                full_name,
                definition.description,
                definition.labels or [],
                buckets=definition.buckets or [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
                registry=self.registry
            )
        elif definition.metric_type == "gauge":
            metric = Gauge(
                full_name,
                definition.description,
                definition.labels or [],
                registry=self.registry
            )
        else:
            logger.error(f"Unknown metric type: {definition.metric_type}")
            return None
        
        self._metrics[definition.name] = metric
        logger.info(f"Created custom metric: {full_name}")
        return metric
    
    async def start_background_collection(self, interval: float = 30.0):
        """Start background system metrics collection"""
        if not self.settings.collect_system_metrics:
            return
            
        logger.info(f"Starting background metrics collection (interval: {interval}s)")
        
        while True:
            try:
                await self.update_system_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("Background metrics collection cancelled")
                break
            except Exception as e:
                logger.error(f"Background metrics collection error: {e}")
                await asyncio.sleep(interval)


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


async def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# Decorator for timing function executions
def monitor_execution(operation_name: str, agent_type: str = None):
    """Decorator for monitoring function execution time"""
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                monitor = await get_performance_monitor()
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    if agent_type:
                        monitor.record_agent_execution(agent_type, time.time() - start_time, "success")
                    return result
                except Exception as e:
                    if agent_type:
                        monitor.record_agent_execution(agent_type, time.time() - start_time, "error")
                    raise
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # For sync functions, we can't easily get the monitor async
                # So we'll just log the timing
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time
                    logger.debug(f"Function '{operation_name}' executed in {duration:.3f}s")
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    logger.debug(f"Function '{operation_name}' failed after {duration:.3f}s: {e}")
                    raise
            return sync_wrapper
    return decorator