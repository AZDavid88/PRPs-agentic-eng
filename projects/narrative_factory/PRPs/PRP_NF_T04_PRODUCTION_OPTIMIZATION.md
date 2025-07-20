# PRP: Production Deployment & Optimization Implementation

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_PHASE_05_ADVANCED_ORCHESTRATION.md  
**Target Agent:** Claude, GPT-4

---

## 1. The Goal (The "What")

Implement comprehensive production deployment infrastructure with performance optimization, monitoring, alerting, and scaling capabilities to transform the Narrative Factory into a production-ready, enterprise-grade AI narrative generation platform.

---

## 2. The Why (The "Why")

**Business Value:**
- **Production Readiness**: Reliable, scalable deployment for enterprise use
- **Operational Excellence**: Comprehensive monitoring, alerting, and observability
- **Performance Optimization**: Sub-2-second response times for agent workflows
- **Cost Efficiency**: Resource optimization and intelligent scaling strategies

**Technical Benefits:**
- **Container Orchestration**: Docker and Kubernetes deployment with auto-scaling
- **Performance Monitoring**: Real-time metrics, profiling, and optimization
- **Reliability Engineering**: Circuit breakers, retry logic, and graceful degradation
- **DevOps Integration**: CI/CD pipelines with automated testing and deployment

**Problems Solved:**
- **Development-Only Architecture**: Current system lacks production deployment strategy
- **Performance Unknowns**: No benchmarking or optimization framework
- **Operational Blindness**: Limited monitoring and alerting capabilities
- **Scaling Challenges**: No strategy for handling increased load

---

## 3. The What (Technical Requirements)

### **User-Visible Behavior**
- Consistent sub-2-second response times for agent workflows under production load
- 99.9% uptime with automatic failover and recovery mechanisms
- Horizontal scaling based on demand with automatic resource management
- Comprehensive health monitoring with proactive alerting

### **Technical Implementation**
- Docker containers with multi-stage builds and security scanning
- Kubernetes deployment with Helm charts and GitOps workflows
- Performance profiling and optimization with caching strategies
- Monitoring stack with Prometheus, Grafana, and distributed tracing
- CI/CD pipelines with automated testing, security scanning, and deployment

### **Success Criteria**
- [ ] Docker containers with optimized builds and security compliance
- [ ] Kubernetes deployment with auto-scaling and load balancing
- [ ] Performance benchmarks meeting <2 second agent response targets
- [ ] Monitoring dashboard with SLA tracking and alerting
- [ ] CI/CD pipeline with automated testing and deployment
- [ ] Security scanning and vulnerability management
- [ ] Load testing validation for 100+ concurrent users
- [ ] Disaster recovery and backup strategies implemented
- [ ] Cost optimization with resource usage monitoring

---

## 4. All Needed Context

### **Documentation & References**

```yaml
MUST_READ_CONTEXT:
  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/docs/research/PHASE1_COMPLETION_STATUS.md"
    why: "Current architecture and validated components"
    critical: "Working Prefect workflows, Qdrant integration, FastAPI foundation"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/config.py"
    why: "Configuration patterns for production environment management"
    critical: "Pydantic settings, environment variables, service connections"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/pyproject.toml"
    why: "Dependency management and project configuration"
    critical: "Package dependencies, development tools, version constraints"

  - file: "/workspaces/PRPs-agentic-eng/projects/narrative_factory/src/workflows/generation.py"
    why: "Core workflow patterns for performance optimization"
    critical: "Async patterns, error handling, job store integration"

  - url: "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/"
    section: "Deployment strategies and scaling"
    critical: "Rolling updates, replica management, resource limits"

  - url: "https://prometheus.io/docs/introduction/overview/"
    section: "Monitoring and alerting patterns"
    critical: "Metrics collection, alerting rules, service discovery"
```

### **Current Architecture to Optimize**

```python
# Current working patterns that need production optimization
# File: src/config.py - Environment management
class AppSettings(BaseSettings):
    # Current development-focused config needs production enhancement
    debug: bool = True  # Must be False in production
    log_level: str = "INFO"  # Needs structured logging
    # Add: resource limits, scaling parameters, monitoring config

# File: src/workflows/generation.py - Workflow optimization
@flow(name="Initial Generation Flow", log_prints=True)
async def initial_generation_flow(chapter_seed: str, dry_run: bool = False) -> str:
    # Current pattern needs: connection pooling, caching, performance monitoring
    pass

# File: src/memory/qdrant.py - Database optimization  
class QdrantService:
    # Current pattern needs: connection pooling, query optimization, caching
    def __init__(self):
        # Add: pool size configuration, health monitoring, retry logic
        pass
```

### **Production Deployment Patterns**

```yaml
containerization_strategy:
  base_image: "python:3.12-slim"
  optimization_techniques:
    - multi_stage_builds: "Development and production stages"
    - layer_caching: "Optimize Docker layer reuse"
    - security_scanning: "Trivy and Snyk integration"
    - minimal_runtime: "Distroless or Alpine for production"

kubernetes_architecture:
  deployment_strategy:
    type: "RollingUpdate"
    max_surge: "25%"
    max_unavailable: "25%"
  
  scaling_strategy:
    hpa_enabled: true
    min_replicas: 2
    max_replicas: 10
    cpu_threshold: 70
    memory_threshold: 80
  
  resource_management:
    requests:
      cpu: "200m"
      memory: "512Mi"
    limits:
      cpu: "1000m" 
      memory: "2Gi"

monitoring_architecture:
  metrics_collection:
    prometheus: "Application and infrastructure metrics"
    custom_metrics: "Agent performance, workflow success rates"
    business_metrics: "Narrative generation quality, user satisfaction"
  
  alerting_strategy:
    sla_monitoring: "Response time, availability, error rates"
    predictive_alerts: "Resource exhaustion, performance degradation"
    escalation_policies: "On-call rotation, severity-based routing"
  
  observability_stack:
    logging: "Structured logging with correlation IDs"
    tracing: "Distributed tracing for request flows"
    profiling: "Application performance profiling"

performance_optimization:
  caching_strategy:
    redis_cache: "Agent personas, embeddings, frequent queries"
    application_cache: "Memory contexts, model responses"
    cdn_integration: "Static assets and public content"
  
  database_optimization:
    connection_pooling: "Qdrant and Redis connection management"
    query_optimization: "Efficient vector similarity search"
    index_tuning: "Payload index optimization"
  
  application_optimization:
    async_patterns: "Non-blocking I/O throughout"
    batch_processing: "Efficient bulk operations"
    resource_pooling: "Model loading and inference optimization"
```

---

## 5. Implementation Blueprint

### **Step 1: Container Optimization (Day 1-2)**

```dockerfile
# File: Dockerfile
# Multi-stage Docker build for production optimization
FROM python:3.12-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
WORKDIR /home/app

# Install UV for fast Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Development stage
FROM base as development
USER app
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --dev
COPY --chown=app:app . .
CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production
USER app

# Copy dependencies and install production packages only
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY --chown=app:app src/ ./src/
COPY --chown=app:app scripts/ ./scripts/

# Security: Remove package manager and build tools
USER root
RUN apt-get purge -y build-essential git && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Production startup with optimized settings
CMD ["uv", "run", "gunicorn", "src.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--keep-alive", "5"]

# Multi-platform builds
FROM production as production-arm64
# ARM64-specific optimizations if needed

FROM production as production-amd64  
# AMD64-specific optimizations if needed
```

```yaml
# File: docker-compose.production.yml
# Production Docker Compose with full service stack
version: '3.8'

services:
  narrative-factory:
    build:
      context: .
      dockerfile: Dockerfile
      target: production
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - REDIS_URL=redis://redis:6379
      - QDRANT_URL=http://qdrant:6333
      - PROMETHEUS_ENABLED=true
    depends_on:
      - redis
      - qdrant
      - prometheus
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.2'
          memory: 512M
    restart: unless-stopped
    
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 512M
    restart: unless-stopped
    
  qdrant:
    image: qdrant/qdrant:v1.7.4
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 4G
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=15d'
      - '--web.enable-lifecycle'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
      - GF_USERS_ALLOW_SIGN_UP=false
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
    depends_on:
      - narrative-factory
    restart: unless-stopped

volumes:
  redis_data:
  qdrant_data:
  prometheus_data:
  grafana_data:

networks:
  default:
    driver: bridge
```

### **Step 2: Kubernetes Deployment (Day 2-3)**

```yaml
# File: k8s/deployment.yaml
# Kubernetes deployment with auto-scaling and monitoring
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
      containers:
      - name: narrative-factory
        image: narrative-factory:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: LOG_LEVEL
          value: "INFO"
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: narrative-factory-secrets
              key: redis-url
        - name: QDRANT_URL
          valueFrom:
            configMapKeyRef:
              name: narrative-factory-config
              key: qdrant-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "200m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
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
        volumeMounts:
        - name: config
          mountPath: /home/app/config
          readOnly: true
      volumes:
      - name: config
        configMap:
          name: narrative-factory-config
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
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

---
apiVersion: v1
kind: Service
metadata:
  name: narrative-factory-service
  labels:
    app: narrative-factory
spec:
  selector:
    app: narrative-factory
  ports:
  - name: http
    port: 80
    targetPort: 8000
  type: ClusterIP

---
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
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: narrative-factory-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - narrative-factory.example.com
    secretName: narrative-factory-tls
  rules:
  - host: narrative-factory.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: narrative-factory-service
            port:
              number: 80
```

### **Step 3: Performance Optimization (Day 3-4)**

```python
# File: src/performance/cache.py
"""
Caching strategies for performance optimization
"""
import asyncio
import json
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
import redis.asyncio as redis
from functools import wraps

class CacheManager:
    """Centralized cache management with Redis backend"""
    
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = 3600  # 1 hour
        
    async def get(self, key: str) -> Optional[Any]:
        """Get cached value"""
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
        return None
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set cached value with TTL"""
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
            
    async def delete(self, key: str) -> bool:
        """Delete cached value"""
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
            
    async def get_or_set(self, key: str, factory: Callable, ttl: Optional[int] = None) -> Any:
        """Get from cache or compute and cache"""
        value = await self.get(key)
        if value is not None:
            return value
            
        # Compute value
        computed_value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        await self.set(key, computed_value, ttl)
        return computed_value

def cache_result(ttl: int = 3600, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args)
            if kwargs:
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            
            cache_key = hashlib.md5(":".join(key_parts).encode()).hexdigest()
            
            # Try to get from cache
            cache_manager = get_cache_manager()
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
                
            # Compute and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            return result
            
        return wrapper
    return decorator

# File: src/performance/monitoring.py
"""
Performance monitoring and metrics collection
"""
import time
import psutil
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from functools import wraps

# Prometheus metrics
REQUEST_COUNT = Counter('narrative_factory_requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('narrative_factory_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('narrative_factory_active_connections', 'Active WebSocket connections')
AGENT_EXECUTION_TIME = Histogram('narrative_factory_agent_execution_seconds', 'Agent execution time', ['agent_type'])
MEMORY_USAGE = Gauge('narrative_factory_memory_usage_bytes', 'Memory usage in bytes')
CPU_USAGE = Gauge('narrative_factory_cpu_usage_percent', 'CPU usage percentage')

class PerformanceMonitor:
    """Performance monitoring and metrics collection"""
    
    def __init__(self):
        self.start_time = time.time()
        
    def track_request(self, method: str, endpoint: str):
        """Decorator to track HTTP request metrics"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                status = "success"
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = "error"
                    raise
                finally:
                    duration = time.time() - start_time
                    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
                    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
                    
            return wrapper
        return decorator
        
    def track_agent_execution(self, agent_type: str):
        """Decorator to track agent execution metrics"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    AGENT_EXECUTION_TIME.labels(agent_type=agent_type).observe(duration)
                    
            return wrapper
        return decorator
        
    async def collect_system_metrics(self):
        """Collect system-level metrics"""
        # Memory usage
        memory_info = psutil.virtual_memory()
        MEMORY_USAGE.set(memory_info.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        CPU_USAGE.set(cpu_percent)
        
        return {
            "memory_used": memory_info.used,
            "memory_percent": memory_info.percent,
            "cpu_percent": cpu_percent,
            "uptime": time.time() - self.start_time
        }

# File: src/performance/optimization.py
"""
Application performance optimizations
"""
import asyncio
from typing import List, Any, Callable
from concurrent.futures import ThreadPoolExecutor

class ConnectionPool:
    """Connection pool for external services"""
    
    def __init__(self, create_connection: Callable, pool_size: int = 10):
        self.create_connection = create_connection
        self.pool_size = pool_size
        self.connections = asyncio.Queue(maxsize=pool_size)
        self.initialized = False
        
    async def initialize(self):
        """Initialize connection pool"""
        if self.initialized:
            return
            
        for _ in range(self.pool_size):
            connection = await self.create_connection()
            await self.connections.put(connection)
            
        self.initialized = True
        
    async def get_connection(self):
        """Get connection from pool"""
        if not self.initialized:
            await self.initialize()
        return await self.connections.get()
        
    async def return_connection(self, connection):
        """Return connection to pool"""
        await self.connections.put(connection)
        
    async def __aenter__(self):
        self.connection = await self.get_connection()
        return self.connection
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.return_connection(self.connection)

class BatchProcessor:
    """Batch processing for improved throughput"""
    
    def __init__(self, batch_size: int = 10, timeout: float = 1.0):
        self.batch_size = batch_size
        self.timeout = timeout
        self.pending_items = []
        self.pending_futures = []
        self.last_batch_time = time.time()
        
    async def add_item(self, item: Any) -> Any:
        """Add item to batch and get result"""
        future = asyncio.Future()
        self.pending_items.append(item)
        self.pending_futures.append(future)
        
        # Process batch if conditions met
        if (len(self.pending_items) >= self.batch_size or 
            time.time() - self.last_batch_time > self.timeout):
            await self._process_batch()
            
        return await future
        
    async def _process_batch(self):
        """Process accumulated batch"""
        if not self.pending_items:
            return
            
        items = self.pending_items[:]
        futures = self.pending_futures[:]
        
        self.pending_items.clear()
        self.pending_futures.clear()
        self.last_batch_time = time.time()
        
        try:
            results = await self.process_batch(items)
            for future, result in zip(futures, results):
                future.set_result(result)
        except Exception as e:
            for future in futures:
                future.set_exception(e)
                
    async def process_batch(self, items: List[Any]) -> List[Any]:
        """Override this method to implement batch processing logic"""
        raise NotImplementedError

# Enhanced Qdrant service with performance optimizations
class OptimizedQdrantService(QdrantService):
    """Qdrant service with connection pooling and caching"""
    
    def __init__(self):
        super().__init__()
        self.connection_pool = None
        self.cache_manager = None
        
    async def initialize_optimizations(self):
        """Initialize performance optimizations"""
        # Connection pooling
        self.connection_pool = ConnectionPool(
            create_connection=self._create_qdrant_connection,
            pool_size=10
        )
        
        # Cache manager
        self.cache_manager = get_cache_manager()
        
    @cache_result(ttl=300, key_prefix="qdrant:search")
    async def optimized_search(self, collection_name: str, query_vector: list, **kwargs):
        """Cached vector search"""
        async with self.connection_pool as client:
            return await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                **kwargs
            )
```

### **Step 4: Monitoring & Alerting (Day 4-5)**

```yaml
# File: monitoring/prometheus.yml
# Prometheus configuration for comprehensive monitoring
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'narrative-factory'
    static_configs:
      - targets: ['narrative-factory:8000']
    metrics_path: '/metrics'
    scrape_interval: 10s
    
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
      
  - job_name: 'qdrant'
    static_configs:
      - targets: ['qdrant:6333']
      
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

---
# File: monitoring/alert_rules.yml
# Alerting rules for SLA monitoring
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
        
    - alert: MemoryUsageHigh
      expr: narrative_factory_memory_usage_bytes / (1024*1024*1024) > 1.5
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage"
        description: "Memory usage is {{ $value | humanize }}GB"
        
    - alert: ServiceDown
      expr: up{job="narrative-factory"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Narrative Factory service is down"
        description: "Service has been down for more than 1 minute"
```

```python
# File: src/monitoring/health.py
"""
Health monitoring and reporting
"""
import asyncio
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class ComponentHealth(BaseModel):
    name: str
    status: HealthStatus
    last_check: datetime
    response_time: float
    details: Dict[str, Any] = {}
    errors: List[str] = []

class HealthMonitor:
    """Comprehensive health monitoring"""
    
    def __init__(self):
        self.components = {}
        self.check_interval = 30  # seconds
        self.running = False
        
    async def start_monitoring(self):
        """Start health monitoring loop"""
        self.running = True
        while self.running:
            await self.check_all_components()
            await asyncio.sleep(self.check_interval)
            
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.running = False
        
    async def check_all_components(self):
        """Check health of all registered components"""
        tasks = []
        for component_name, check_func in self.components.items():
            task = asyncio.create_task(self._check_component(component_name, check_func))
            tasks.append(task)
            
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def _check_component(self, name: str, check_func) -> ComponentHealth:
        """Check individual component health"""
        start_time = time.time()
        
        try:
            result = await check_func()
            response_time = time.time() - start_time
            
            health = ComponentHealth(
                name=name,
                status=HealthStatus.HEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                details=result if isinstance(result, dict) else {"result": result}
            )
            
        except Exception as e:
            response_time = time.time() - start_time
            health = ComponentHealth(
                name=name,
                status=HealthStatus.CRITICAL,
                last_check=datetime.now(),
                response_time=response_time,
                errors=[str(e)]
            )
            
        return health
        
    def register_component(self, name: str, check_func):
        """Register component for health monitoring"""
        self.components[name] = check_func
        
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        await self.check_all_components()
        
        all_healthy = all(
            health.status == HealthStatus.HEALTHY 
            for health in self.components.values()
        )
        
        any_critical = any(
            health.status == HealthStatus.CRITICAL 
            for health in self.components.values()
        )
        
        overall_status = HealthStatus.HEALTHY
        if any_critical:
            overall_status = HealthStatus.CRITICAL
        elif not all_healthy:
            overall_status = HealthStatus.WARNING
            
        return {
            "status": overall_status,
            "timestamp": datetime.now(),
            "components": {name: health.model_dump() for name, health in self.components.items()},
            "summary": {
                "total_components": len(self.components),
                "healthy_components": sum(1 for h in self.components.values() if h.status == HealthStatus.HEALTHY),
                "warning_components": sum(1 for h in self.components.values() if h.status == HealthStatus.WARNING),
                "critical_components": sum(1 for h in self.components.values() if h.status == HealthStatus.CRITICAL)
            }
        }

# Health check implementations
async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity and performance"""
    redis_client = get_redis_client()
    start_time = time.time()
    
    # Basic connectivity
    await redis_client.ping()
    
    # Performance test
    test_key = "health_check_test"
    await redis_client.set(test_key, "test_value", ex=10)
    value = await redis_client.get(test_key)
    
    response_time = time.time() - start_time
    
    return {
        "connectivity": "ok",
        "response_time": response_time,
        "test_operation": "success" if value == "test_value" else "failed"
    }

async def check_qdrant_health() -> Dict[str, Any]:
    """Check Qdrant connectivity and performance"""
    qdrant_service = get_qdrant_service()
    start_time = time.time()
    
    # Check collections
    collections = await qdrant_service.list_collections()
    
    # Test search performance
    if collections:
        collection_name = collections[0]
        # Perform a test search
        test_vector = [0.1] * 1024  # Dummy vector
        results = await qdrant_service.search(
            collection_name=collection_name,
            query_vector=test_vector,
            limit=1
        )
        
    response_time = time.time() - start_time
    
    return {
        "connectivity": "ok",
        "collections_count": len(collections),
        "response_time": response_time,
        "test_search": "success"
    }

async def check_agent_health() -> Dict[str, Any]:
    """Check agent system health"""
    # Test agent instantiation
    try:
        from src.agents.personas import DirectorAgent
        agent = DirectorAgent()
        
        # Test dry run execution
        start_time = time.time()
        result = await agent.execute("health check test", dry_run=True)
        response_time = time.time() - start_time
        
        return {
            "agent_instantiation": "ok",
            "dry_run_execution": "ok",
            "response_time": response_time
        }
        
    except Exception as e:
        return {
            "agent_instantiation": "failed",
            "error": str(e)
        }
```

---

## 6. Validation Gate

### **Level 1: Container Tests**
```bash
# Build and test Docker container
docker build -t narrative-factory:test --target production .
docker run --rm narrative-factory:test python -c "import src.main; print('✅ Container build successful')"

# Test security scanning
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image narrative-factory:test
```

### **Level 2: Performance Tests**
```bash
# Load testing with Artillery
npm install -g artillery
artillery quick --count 100 --num 10 http://localhost:8000/health
# Expected: <2 second response times under load

# Memory and CPU profiling
docker stats narrative-factory-container
# Expected: Memory usage <2GB, CPU usage <80%
```

### **Level 3: Kubernetes Deployment Tests**
```bash
# Deploy to local Kubernetes cluster
kubectl apply -f k8s/
kubectl rollout status deployment/narrative-factory
kubectl get pods -l app=narrative-factory
# Expected: All pods running and ready

# Test auto-scaling
kubectl run -i --tty load-generator --rm --image=busybox --restart=Never -- /bin/sh
# Generate load and verify HPA scaling
```

### **Level 4: End-to-End Production Tests**
```bash
# Production deployment validation
helm test narrative-factory
# Expected: All test hooks pass

# Monitoring and alerting validation
curl http://prometheus:9090/api/v1/alerts
# Expected: No critical alerts firing

# Performance benchmark
uv run python benchmark_production.py
# Expected: All SLA targets met
```

---

## 7. Gotchas and Edge Cases

### **Container Security**
- **Issue**: Running as root in containers creates security vulnerabilities
- **Solution**: Use non-root user and minimal base images with security scanning

### **Resource Management**
- **Issue**: Memory leaks and resource exhaustion under load
- **Solution**: Implement proper connection pooling, caching limits, and resource monitoring

### **Database Connections**
- **Issue**: Connection pool exhaustion under high concurrency
- **Solution**: Implement circuit breakers and adaptive connection pool sizing

### **Monitoring Overhead**
- **Issue**: Excessive monitoring can impact application performance
- **Solution**: Implement sampling and efficient metrics collection strategies

---

## 8. Success Metrics

- **Performance**: <2 second response times for 95th percentile under production load
- **Scalability**: Support for 100+ concurrent users with auto-scaling
- **Reliability**: 99.9% uptime with automatic failover and recovery
- **Security**: Zero critical vulnerabilities in security scans
- **Observability**: Complete monitoring coverage with SLA tracking
- **Cost Efficiency**: Optimized resource usage with intelligent scaling

---

This PRP provides comprehensive production deployment guidance that transforms the Narrative Factory into an enterprise-ready, scalable, and maintainable AI narrative generation platform.