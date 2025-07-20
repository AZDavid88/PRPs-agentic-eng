"""Tests for performance health monitoring module."""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.performance.health import HealthMonitor, HealthSettings, ComponentHealth, HealthStatus


@pytest.fixture
def health_settings():
    """Health settings fixture."""
    return HealthSettings(
        check_interval=5,
        unhealthy_threshold=3,
        timeout=10,
        enable_alerts=True,
        sla_target=99.9
    )


@pytest.fixture
def mock_redis_healthy():
    """Mock healthy Redis connection."""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture
def mock_qdrant_healthy():
    """Mock healthy Qdrant client."""
    qdrant_mock = Mock()
    qdrant_mock.get_collections = Mock(return_value=Mock(collections=[]))
    return qdrant_mock


class TestComponentHealth:
    """Test cases for ComponentHealth."""

    def test_component_health_init(self):
        """Test ComponentHealth initialization."""
        health = ComponentHealth(
            name="test_component",
            status=HealthStatus.HEALTHY,
            last_check=datetime.now(),
            response_time=0.5,
            error_count=0
        )
        
        assert health.name == "test_component"
        assert health.status == HealthStatus.HEALTHY
        assert health.response_time == 0.5
        assert health.error_count == 0

    def test_component_health_is_healthy(self):
        """Test ComponentHealth is_healthy property."""
        healthy = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            last_check=datetime.now(),
            response_time=0.1,
            error_count=0
        )
        assert healthy.is_healthy is True
        
        unhealthy = ComponentHealth(
            name="test",
            status=HealthStatus.UNHEALTHY,
            last_check=datetime.now(),
            response_time=5.0,
            error_count=5
        )
        assert unhealthy.is_healthy is False

    def test_component_health_uptime_calculation(self):
        """Test ComponentHealth uptime calculation."""
        now = datetime.now()
        health = ComponentHealth(
            name="test",
            status=HealthStatus.HEALTHY,
            last_check=now,
            response_time=0.1,
            error_count=0,
            uptime_start=now - timedelta(hours=1)
        )
        
        uptime = health.uptime_hours
        assert 0.9 <= uptime <= 1.1  # Allow for small timing differences


class TestHealthMonitor:
    """Test cases for HealthMonitor."""

    def test_health_monitor_init_default(self):
        """Test HealthMonitor initialization with defaults."""
        monitor = HealthMonitor()
        assert monitor.settings is not None
        assert monitor.settings.check_interval == 30
        assert monitor.settings.unhealthy_threshold == 3

    def test_health_monitor_init_custom_settings(self, health_settings):
        """Test HealthMonitor initialization with custom settings."""
        monitor = HealthMonitor(health_settings)
        assert monitor.settings == health_settings
        assert monitor.settings.check_interval == 5

    @pytest.mark.asyncio
    async def test_health_monitor_check_redis_healthy(self, mock_redis_healthy):
        """Test Redis health check when healthy."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.redis.from_url', return_value=mock_redis_healthy):
            health = await monitor.check_redis_health()
            
            assert health.name == "redis"
            assert health.status == HealthStatus.HEALTHY
            assert health.response_time > 0
            assert health.error_count == 0

    @pytest.mark.asyncio
    async def test_health_monitor_check_redis_unhealthy(self):
        """Test Redis health check when unhealthy."""
        monitor = HealthMonitor()
        
        redis_mock = AsyncMock()
        redis_mock.ping.side_effect = Exception("Connection failed")
        
        with patch('src.performance.health.redis.from_url', return_value=redis_mock):
            health = await monitor.check_redis_health()
            
            assert health.name == "redis"
            assert health.status == HealthStatus.UNHEALTHY
            assert health.error_count > 0

    @pytest.mark.asyncio
    async def test_health_monitor_check_qdrant_healthy(self, mock_qdrant_healthy):
        """Test Qdrant health check when healthy."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.QdrantClient', return_value=mock_qdrant_healthy):
            health = await monitor.check_qdrant_health()
            
            assert health.name == "qdrant"
            assert health.status == HealthStatus.HEALTHY
            assert health.response_time > 0
            assert health.error_count == 0

    @pytest.mark.asyncio
    async def test_health_monitor_check_qdrant_unhealthy(self):
        """Test Qdrant health check when unhealthy."""
        monitor = HealthMonitor()
        
        qdrant_mock = Mock()
        qdrant_mock.get_collections.side_effect = Exception("Connection failed")
        
        with patch('src.performance.health.QdrantClient', return_value=qdrant_mock):
            health = await monitor.check_qdrant_health()
            
            assert health.name == "qdrant"
            assert health.status == HealthStatus.UNHEALTHY
            assert health.error_count > 0

    @pytest.mark.asyncio
    async def test_health_monitor_check_agents_health(self):
        """Test agents health check."""
        monitor = HealthMonitor()
        
        # Mock successful agent execution
        with patch('src.performance.health.DirectorAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.execute = AsyncMock(return_value="test response")
            mock_agent_class.return_value = mock_agent
            
            health = await monitor.check_agents_health()
            
            assert health.name == "agents"
            assert health.status == HealthStatus.HEALTHY
            assert health.response_time > 0

    @pytest.mark.asyncio
    async def test_health_monitor_check_agents_unhealthy(self):
        """Test agents health check when unhealthy."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.DirectorAgent') as mock_agent_class:
            mock_agent = Mock()
            mock_agent.execute = AsyncMock(side_effect=Exception("Agent failed"))
            mock_agent_class.return_value = mock_agent
            
            health = await monitor.check_agents_health()
            
            assert health.name == "agents"
            assert health.status == HealthStatus.UNHEALTHY

    def test_health_monitor_check_system_resources(self):
        """Test system resources health check."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.psutil') as mock_psutil:
            mock_psutil.cpu_percent.return_value = 45.0
            mock_psutil.virtual_memory.return_value.percent = 60.0
            mock_psutil.disk_usage.return_value.percent = 70.0
            
            health = monitor.check_system_resources()
            
            assert health.name == "system_resources"
            assert health.status == HealthStatus.HEALTHY
            assert health.response_time > 0

    def test_health_monitor_check_system_resources_unhealthy(self):
        """Test system resources health check when unhealthy."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.psutil') as mock_psutil:
            # High resource usage
            mock_psutil.cpu_percent.return_value = 95.0
            mock_psutil.virtual_memory.return_value.percent = 98.0
            mock_psutil.disk_usage.return_value.percent = 99.0
            
            health = monitor.check_system_resources()
            
            assert health.name == "system_resources"
            assert health.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_health_monitor_check_all_components(self):
        """Test checking all components."""
        monitor = HealthMonitor()
        
        # Mock all health checks to be healthy
        with patch.object(monitor, 'check_redis_health') as mock_redis, \
             patch.object(monitor, 'check_qdrant_health') as mock_qdrant, \
             patch.object(monitor, 'check_agents_health') as mock_agents, \
             patch.object(monitor, 'check_system_resources') as mock_system:
            
            mock_redis.return_value = ComponentHealth(
                name="redis", status=HealthStatus.HEALTHY, 
                last_check=datetime.now(), response_time=0.1, error_count=0
            )
            mock_qdrant.return_value = ComponentHealth(
                name="qdrant", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.2, error_count=0
            )
            mock_agents.return_value = ComponentHealth(
                name="agents", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.5, error_count=0
            )
            mock_system.return_value = ComponentHealth(
                name="system_resources", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.01, error_count=0
            )
            
            results = await monitor.check_all_components()
            
            assert len(results) == 4
            assert all(health.is_healthy for health in results.values())

    def test_health_monitor_get_overall_status_healthy(self):
        """Test overall status when all components are healthy."""
        monitor = HealthMonitor()
        
        monitor.component_health = {
            "redis": ComponentHealth(
                name="redis", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.1, error_count=0
            ),
            "qdrant": ComponentHealth(
                name="qdrant", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.2, error_count=0
            )
        }
        
        status = monitor.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_health_monitor_get_overall_status_unhealthy(self):
        """Test overall status when any component is unhealthy."""
        monitor = HealthMonitor()
        
        monitor.component_health = {
            "redis": ComponentHealth(
                name="redis", status=HealthStatus.HEALTHY,
                last_check=datetime.now(), response_time=0.1, error_count=0
            ),
            "qdrant": ComponentHealth(
                name="qdrant", status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(), response_time=5.0, error_count=3
            )
        }
        
        status = monitor.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_health_monitor_get_health_summary(self):
        """Test health summary generation."""
        monitor = HealthMonitor()
        
        now = datetime.now()
        monitor.component_health = {
            "redis": ComponentHealth(
                name="redis", status=HealthStatus.HEALTHY,
                last_check=now, response_time=0.1, error_count=0,
                uptime_start=now - timedelta(hours=1)
            ),
            "qdrant": ComponentHealth(
                name="qdrant", status=HealthStatus.DEGRADED,
                last_check=now, response_time=2.0, error_count=1,
                uptime_start=now - timedelta(hours=2)
            )
        }
        
        summary = monitor.get_health_summary()
        
        assert summary['overall_status'] == 'DEGRADED'
        assert summary['total_components'] == 2
        assert summary['healthy_components'] == 1
        assert summary['unhealthy_components'] == 0
        assert summary['degraded_components'] == 1
        assert 'components' in summary
        assert len(summary['components']) == 2

    def test_health_monitor_calculate_sla_compliance(self):
        """Test SLA compliance calculation."""
        monitor = HealthMonitor()
        
        # Mock uptime data
        total_time = 100
        downtime = 0.1  # 0.1% downtime = 99.9% uptime
        
        with patch.object(monitor, '_get_uptime_data', return_value=(total_time, downtime)):
            compliance = monitor.calculate_sla_compliance()
            
            assert compliance >= 99.9

    @pytest.mark.asyncio
    async def test_health_monitor_start_monitoring(self):
        """Test starting health monitoring."""
        monitor = HealthMonitor()
        
        with patch('src.performance.health.asyncio.create_task') as mock_create_task:
            await monitor.start_monitoring()
            
            mock_create_task.assert_called_once()
            assert monitor._monitoring_task is not None

    @pytest.mark.asyncio
    async def test_health_monitor_stop_monitoring(self):
        """Test stopping health monitoring."""
        monitor = HealthMonitor()
        
        # Mock running task
        mock_task = Mock()
        mock_task.cancel = Mock()
        monitor._monitoring_task = mock_task
        
        await monitor.stop_monitoring()
        
        mock_task.cancel.assert_called_once()
        assert monitor._monitoring_task is None

    def test_health_monitor_record_component_metric(self):
        """Test recording component metrics."""
        monitor = HealthMonitor()
        
        monitor.record_component_metric("test_component", "response_time", 0.5)
        monitor.record_component_metric("test_component", "error_count", 1)
        
        assert "test_component" in monitor._metrics
        assert monitor._metrics["test_component"]["response_time"][-1] == 0.5
        assert monitor._metrics["test_component"]["error_count"][-1] == 1

    def test_health_monitor_get_component_metrics(self):
        """Test getting component metrics."""
        monitor = HealthMonitor()
        
        # Record some metrics
        for i in range(5):
            monitor.record_component_metric("test_component", "response_time", i * 0.1)
        
        metrics = monitor.get_component_metrics("test_component")
        
        assert "response_time" in metrics
        assert len(metrics["response_time"]) == 5
        assert metrics["response_time"][-1] == 0.4

    @pytest.mark.asyncio
    async def test_health_monitor_alert_generation(self):
        """Test alert generation for unhealthy components."""
        settings = HealthSettings(enable_alerts=True)
        monitor = HealthMonitor(settings)
        
        alerts = []
        
        def mock_send_alert(component, status, message):
            alerts.append({"component": component, "status": status, "message": message})
        
        with patch.object(monitor, '_send_alert', side_effect=mock_send_alert):
            unhealthy_component = ComponentHealth(
                name="test_component",
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=10.0,
                error_count=5
            )
            
            await monitor._handle_unhealthy_component(unhealthy_component)
            
            assert len(alerts) == 1
            assert alerts[0]["component"] == "test_component"
            assert alerts[0]["status"] == HealthStatus.UNHEALTHY

    def test_health_monitor_health_history(self):
        """Test health history tracking."""
        monitor = HealthMonitor()
        
        # Add some health records
        for i in range(3):
            health = ComponentHealth(
                name="test_component",
                status=HealthStatus.HEALTHY,
                last_check=datetime.now() - timedelta(minutes=i),
                response_time=0.1 + i * 0.1,
                error_count=i
            )
            monitor._add_to_history(health)
        
        history = monitor.get_health_history("test_component")
        
        assert len(history) == 3
        assert all(h.name == "test_component" for h in history)


def test_health_settings_validation():
    """Test HealthSettings validation."""
    # Valid settings
    settings = HealthSettings(
        check_interval=10,
        unhealthy_threshold=5,
        timeout=20,
        enable_alerts=False,
        sla_target=99.5
    )
    assert settings.check_interval == 10
    assert settings.unhealthy_threshold == 5
    assert settings.timeout == 20
    assert settings.enable_alerts is False
    assert settings.sla_target == 99.5
    
    # Test default values
    default_settings = HealthSettings()
    assert default_settings.check_interval == 30
    assert default_settings.unhealthy_threshold == 3
    assert default_settings.timeout == 10
    assert default_settings.enable_alerts is True
    assert default_settings.sla_target == 99.9


def test_health_status_enum():
    """Test HealthStatus enum values."""
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNHEALTHY.value == "unhealthy"
    assert HealthStatus.UNKNOWN.value == "unknown"