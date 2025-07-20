# T04 Production Deployment Patterns Research

**Research Date:** 2025-07-20  
**Context:** T04 Production Optimization Implementation  
**Status:** Research complete - ready for implementation  
**Sources:** Context7 analysis of production deployment libraries

## FastAPI Production Deployment Best Practices

### Production Configuration Patterns

Based on FastAPI best practices analysis:

```python
# Environment-driven configuration with Pydantic
from pydantic_settings import BaseSettings
from typing import Optional

class ProductionConfig(BaseSettings):
    # Security
    DEBUG: bool = False
    SECRET_KEY: str
    SECURE_COOKIES: bool = True
    
    # Performance  
    MAX_WORKERS: int = 4
    WORKER_TIMEOUT: int = 60
    KEEP_ALIVE: int = 5
    
    # Resources
    MAX_CONNECTIONS_PER_USER: int = 5
    REDIS_MAX_CONNECTIONS: int = 10
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Hide docs in production
    OPENAPI_URL: Optional[str] = None  # Set to None in production
    
    class Config:
        env_file = ".env"

# Conditional docs hiding
ENVIRONMENT = config("ENVIRONMENT")
SHOW_DOCS_ENVIRONMENT = ("local", "staging")

app_configs = {"title": "Narrative Factory API"}
if ENVIRONMENT not in SHOW_DOCS_ENVIRONMENT:
    app_configs["openapi_url"] = None

app = FastAPI(**app_configs)
```

### Gunicorn Production Deployment

```bash
# Production startup optimized for performance
gunicorn src.web.app:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile -
```

**Key Production Patterns:**
- **Worker Class**: `uvicorn.workers.UvicornWorker` for async support
- **Worker Count**: Formula: `(2 x CPU cores) + 1` for I/O bound applications
- **Timeout**: 60 seconds for LLM operations
- **Keep-Alive**: 5 seconds for connection reuse

## Prometheus Monitoring for FastAPI

### Core Metrics Implementation

```python
from prometheus_client import Counter, Histogram, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

# Application metrics
REQUEST_COUNT = Counter(
    'narrative_factory_requests_total', 
    'Total requests', 
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'narrative_factory_request_duration_seconds', 
    'Request duration', 
    ['method', 'endpoint']
)

AGENT_EXECUTION_TIME = Histogram(
    'narrative_factory_agent_execution_seconds', 
    'Agent execution time', 
    ['agent_type']
)

# WebSocket metrics
ACTIVE_CONNECTIONS = Gauge(
    'narrative_factory_active_connections', 
    'Active WebSocket connections'
)

# System metrics
MEMORY_USAGE = Gauge('narrative_factory_memory_usage_bytes', 'Memory usage')
CPU_USAGE = Gauge('narrative_factory_cpu_usage_percent', 'CPU usage')
```

### Multi-Process Monitoring Setup

**Critical for Gunicorn Workers:**

```bash
# Set environment variable for multi-process mode
export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus-multiproc

# Clean and prepare directory
rm -rf "$PROMETHEUS_MULTIPROC_DIR"
mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

# Start with Gunicorn
gunicorn main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### Instrumentator Configuration

```python
from prometheus_fastapi_instrumentator import Instrumentator, metrics

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=[".*admin.*", "/metrics"],
    env_var_name="PROMETHEUS_ENABLED",
    custom_labels={"service": "narrative-factory"}
)

# Add custom metrics
instrumentator.add(metrics.latency(buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0)))
instrumentator.add(metrics.request_size())
instrumentator.add(metrics.response_size())

# Instrument and expose
@app.on_event("startup")
async def startup():
    instrumentator.instrument(app).expose(app)
```

## Redis Async Caching Patterns

### Connection Pool Configuration

Based on Coredis best practices:

```python
import coredis
from typing import Optional, Any, Callable
import asyncio
import json
import hashlib

class OptimizedCacheManager:
    """Production-ready Redis cache manager with connection pooling"""
    
    def __init__(self, redis_url: str, max_connections: int = 10):
        # Use blocking connection pool for production reliability
        self.redis = coredis.Redis(
            connection_pool_cls=coredis.BlockingConnectionPool,
            max_connections=max_connections,
            socket_keepalive=True,
            socket_keepalive_options={},
            retry_on_timeout=True,
            health_check_interval=30
        )
        self.default_ttl = 3600  # 1 hour
        
    async def get_or_set(self, key: str, factory: Callable, ttl: Optional[int] = None) -> Any:
        """Get from cache or compute and cache with connection handling"""
        try:
            # Try cache first
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
                
            # Compute and cache
            computed_value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            await self.redis.setex(key, ttl or self.default_ttl, json.dumps(computed_value, default=str))
            return computed_value
            
        except Exception as e:
            logger.error(f"Cache operation failed: {e}")
            # Fallback to direct computation
            return await factory() if asyncio.iscoroutinefunction(factory) else factory()

# Caching decorator for expensive operations
def cache_result(ttl: int = 3600, key_prefix: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate deterministic cache key
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args)
            if kwargs:
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Use cache manager
            cache_manager = get_cache_manager()
            return await cache_manager.get_or_set(
                cache_key, 
                lambda: func(*args, **kwargs), 
                ttl
            )
        return wrapper
    return decorator
```

### Performance Optimization Patterns

```python
# Optimized Qdrant service with caching
class OptimizedQdrantService(QdrantService):
    """Qdrant with Redis caching and connection pooling"""
    
    def __init__(self):
        super().__init__()
        self.cache_manager = OptimizedCacheManager(
            redis_url=settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS
        )
        
    @cache_result(ttl=300, key_prefix="qdrant:search")
    async def cached_search(self, collection_name: str, query_vector: list, **kwargs):
        """Vector search with Redis caching"""
        return await self.search(
            collection_name=collection_name,
            query_vector=query_vector,
            **kwargs
        )
        
    async def batch_upsert(self, collection_name: str, points: list):
        """Batch operations for better performance"""
        # Process in chunks for memory efficiency
        chunk_size = 100
        for i in range(0, len(points), chunk_size):
            chunk = points[i:i + chunk_size]
            await self.upsert(collection_name, chunk)
```

## Kubernetes Production Deployment

### Horizontal Pod Autoscaler (HPA) Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: narrative-factory-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: narrative-factory
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 5 minutes
      policies:
      - type: Percent
        value: 10  # Max 10% pods removed per minute
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60  # 1 minute
      policies:
      - type: Percent
        value: 50  # Max 50% increase per minute
        periodSeconds: 60
      - type: Pods
        value: 4  # Max 4 pods added per minute
        periodSeconds: 60
      selectPolicy: Max
```

### Deployment Best Practices

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: narrative-factory
  labels:
    app: narrative-factory
    version: v1.0.0
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
  selector:
    matchLabels:
      app: narrative-factory
  template:
    metadata:
      labels:
        app: narrative-factory
        version: v1.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      # Security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      
      # Anti-affinity for availability
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - narrative-factory
              topologyKey: kubernetes.io/hostname
      
      containers:
      - name: narrative-factory
        image: narrative-factory:latest
        ports:
        - containerPort: 8000
          name: http
        
        # Resource limits and requests
        resources:
          requests:
            memory: "512Mi"
            cpu: "200m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        
        # Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 5
          failureThreshold: 3
        
        # Environment configuration
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: LOG_LEVEL
          value: "INFO"
        - name: PROMETHEUS_ENABLED
          value: "true"
        - name: PROMETHEUS_MULTIPROC_DIR
          value: "/tmp/prometheus-multiproc"
        
        # Volume mounts
        volumeMounts:
        - name: tmp-prometheus
          mountPath: /tmp/prometheus-multiproc
        - name: config
          mountPath: /home/app/config
          readOnly: true
      
      volumes:
      - name: tmp-prometheus
        emptyDir: {}
      - name: config
        configMap:
          name: narrative-factory-config
```

### Monitoring & Alerting Configuration

```yaml
# Prometheus AlertManager rules
groups:
- name: narrative_factory_alerts
  rules:
  - alert: HighResponseTime
    expr: histogram_quantile(0.95, narrative_factory_request_duration_seconds_bucket) > 2
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "High response time detected"
      description: "95th percentile response time is {{ $value }}s"
      
  - alert: HighErrorRate
    expr: rate(narrative_factory_requests_total{status="error"}[5m]) > 0.05
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "High error rate detected"
      description: "Error rate is {{ $value | humanizePercentage }}"
      
  - alert: AgentExecutionTimeout
    expr: histogram_quantile(0.95, narrative_factory_agent_execution_seconds_bucket) > 10
    for: 3m
    labels:
      severity: warning
    annotations:
      summary: "Agent execution taking too long"
      description: "95th percentile agent execution time is {{ $value }}s"
      
  - alert: PodCrashLooping
    expr: rate(kube_pod_container_status_restarts_total[5m]) > 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Pod is crash looping"
      description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} is restarting frequently"
```

## Production Optimization Implementation Priority

### Phase 1: Container & Infrastructure (Days 1-2)
1. **Multi-stage Dockerfile** with security scanning
2. **Docker Compose** production stack
3. **Environment configuration** with secrets management

### Phase 2: Kubernetes Deployment (Days 2-3)
1. **Deployment manifests** with resource limits
2. **HPA configuration** for auto-scaling
3. **Service and Ingress** setup
4. **ConfigMaps and Secrets** management

### Phase 3: Monitoring & Observability (Days 3-4)
1. **Prometheus metrics** implementation
2. **Grafana dashboards** for visualization
3. **Alert rules** for SLA monitoring
4. **Health check endpoints** enhancement

### Phase 4: Performance Optimization (Days 4-5)
1. **Redis caching** implementation
2. **Connection pooling** optimization
3. **Load testing** and benchmarking
4. **Performance tuning** based on metrics

## Security Considerations

### Container Security
- **Non-root user**: Run as UID 1000 
- **Minimal base image**: Use distroless or alpine for production
- **Security scanning**: Trivy/Snyk integration
- **Read-only filesystem**: Where possible

### Kubernetes Security
- **Pod Security Standards**: Restricted mode
- **Network policies**: Limit inter-pod communication
- **RBAC**: Principle of least privilege
- **Secrets management**: External secret operators

### Application Security
- **Environment isolation**: Production configs
- **API documentation**: Hidden in production
- **Rate limiting**: Per-user connection limits
- **Input validation**: Comprehensive sanitization

This research provides the technical foundation for enterprise-grade production deployment of the Narrative Factory system.