"""Tests for performance monitoring module."""

import time
from unittest.mock import Mock, patch

import pytest

from src.performance.monitoring import PerformanceMonitor, MetricsSettings


@pytest.fixture
def metrics_settings():
    """Metrics settings fixture."""
    return MetricsSettings(
        enable_prometheus=True,
        enable_system_metrics=True,
        collection_interval=10,
        registry_port=9090
    )


@pytest.fixture
def mock_prometheus_registry():
    """Mock Prometheus registry."""
    with patch('src.performance.monitoring.CollectorRegistry') as mock_registry:
        yield mock_registry.return_value


@pytest.fixture
def mock_prometheus_metrics():
    """Mock Prometheus metrics."""
    with patch('src.performance.monitoring.Counter') as mock_counter, \
         patch('src.performance.monitoring.Histogram') as mock_histogram, \
         patch('src.performance.monitoring.Gauge') as mock_gauge:
        
        mock_counter_instance = Mock()
        mock_histogram_instance = Mock()
        mock_gauge_instance = Mock()
        
        mock_counter.return_value = mock_counter_instance
        mock_histogram.return_value = mock_histogram_instance
        mock_gauge.return_value = mock_gauge_instance
        
        yield {
            'counter': mock_counter_instance,
            'histogram': mock_histogram_instance,
            'gauge': mock_gauge_instance
        }


def test_performance_monitor_init_default():
    """Test PerformanceMonitor initialization with defaults."""
    monitor = PerformanceMonitor()
    assert monitor.settings is not None
    assert monitor.settings.enable_prometheus is True
    assert monitor.settings.collection_interval == 15


def test_performance_monitor_init_custom_settings(metrics_settings):
    """Test PerformanceMonitor initialization with custom settings."""
    monitor = PerformanceMonitor(metrics_settings)
    assert monitor.settings == metrics_settings
    assert monitor.settings.collection_interval == 10


@patch('src.performance.monitoring.start_http_server')
def test_performance_monitor_start_metrics_server(mock_start_server, mock_prometheus_registry):
    """Test starting Prometheus metrics server."""
    monitor = PerformanceMonitor()
    monitor.start_metrics_server()
    
    mock_start_server.assert_called_once_with(8000, registry=mock_prometheus_registry)


def test_performance_monitor_record_request(mock_prometheus_metrics):
    """Test recording HTTP request metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Record a request
        monitor.record_request('GET', '/api/test', 200, 0.5)
        
        # Verify counter was incremented
        mock_prometheus_metrics['counter'].inc.assert_called()
        
        # Verify histogram was observed
        mock_prometheus_metrics['histogram'].observe.assert_called_with(0.5)


def test_performance_monitor_record_agent_execution(mock_prometheus_metrics):
    """Test recording agent execution metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Record agent execution
        monitor.record_agent_execution('DirectorAgent', 'completed', 2.5)
        
        # Verify metrics were recorded
        mock_prometheus_metrics['counter'].inc.assert_called()
        mock_prometheus_metrics['histogram'].observe.assert_called_with(2.5)


def test_performance_monitor_record_websocket_connection(mock_prometheus_metrics):
    """Test recording WebSocket connection metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Record WebSocket connection
        monitor.record_websocket_connection('connect')
        mock_prometheus_metrics['counter'].inc.assert_called()
        
        # Record WebSocket disconnection
        monitor.record_websocket_connection('disconnect')
        mock_prometheus_metrics['counter'].inc.assert_called()


def test_performance_monitor_record_cache_operation(mock_prometheus_metrics):
    """Test recording cache operation metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Record cache hit
        monitor.record_cache_operation('hit', 0.01)
        mock_prometheus_metrics['counter'].inc.assert_called()
        mock_prometheus_metrics['histogram'].observe.assert_called_with(0.01)
        
        # Record cache miss
        monitor.record_cache_operation('miss', 0.05)
        mock_prometheus_metrics['counter'].inc.assert_called()
        mock_prometheus_metrics['histogram'].observe.assert_called_with(0.05)


def test_performance_monitor_record_memory_operation(mock_prometheus_metrics):
    """Test recording memory operation metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Record memory search
        monitor.record_memory_operation('search', 1.2)
        mock_prometheus_metrics['counter'].inc.assert_called()
        mock_prometheus_metrics['histogram'].observe.assert_called_with(1.2)
        
        # Record memory store
        monitor.record_memory_operation('store', 0.8)
        mock_prometheus_metrics['counter'].inc.assert_called()
        mock_prometheus_metrics['histogram'].observe.assert_called_with(0.8)


@patch('src.performance.monitoring.psutil')
def test_performance_monitor_update_system_metrics(mock_psutil, mock_prometheus_metrics):
    """Test updating system metrics."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        # Mock psutil responses
        mock_psutil.cpu_percent.return_value = 45.5
        mock_psutil.virtual_memory.return_value.percent = 67.3
        mock_psutil.disk_usage.return_value.percent = 23.1
        
        monitor = PerformanceMonitor()
        monitor.update_system_metrics()
        
        # Verify system metrics were recorded
        assert mock_prometheus_metrics['gauge'].set.call_count >= 3


def test_performance_monitor_timing_context_manager():
    """Test timing context manager."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        with patch.object(monitor, 'record_request') as mock_record:
            with monitor.time_request('GET', '/api/test') as timer:
                time.sleep(0.01)  # Simulate some work
                timer.set_status(200)
            
            # Verify request was recorded with timing
            mock_record.assert_called_once()
            args = mock_record.call_args[0]
            assert args[0] == 'GET'
            assert args[1] == '/api/test'
            assert args[2] == 200
            assert args[3] > 0  # Duration should be positive


def test_performance_monitor_timing_context_manager_with_exception():
    """Test timing context manager with exception."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        with patch.object(monitor, 'record_request') as mock_record:
            try:
                with monitor.time_request('POST', '/api/error') as timer:
                    timer.set_status(500)
                    raise ValueError("Test error")
            except ValueError:
                pass
            
            # Verify request was still recorded
            mock_record.assert_called_once()
            args = mock_record.call_args[0]
            assert args[2] == 500  # Status should be 500


def test_performance_monitor_get_metrics_summary(mock_prometheus_metrics):
    """Test getting metrics summary."""
    with patch('src.performance.monitoring.CollectorRegistry') as mock_registry:
        # Mock registry sample collection
        mock_sample = Mock()
        mock_sample.name = 'test_metric'
        mock_sample.value = 42.0
        mock_registry.return_value.collect.return_value = [
            Mock(samples=[mock_sample])
        ]
        
        monitor = PerformanceMonitor()
        summary = monitor.get_metrics_summary()
        
        assert isinstance(summary, dict)
        assert 'test_metric' in summary
        assert summary['test_metric'] == 42.0


@patch('src.performance.monitoring.psutil')
def test_performance_monitor_get_system_info(mock_psutil):
    """Test getting system information."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        # Mock psutil responses
        mock_psutil.cpu_count.return_value = 8
        mock_psutil.virtual_memory.return_value.total = 16 * 1024 * 1024 * 1024  # 16GB
        mock_psutil.disk_usage.return_value.total = 500 * 1024 * 1024 * 1024  # 500GB
        
        monitor = PerformanceMonitor()
        system_info = monitor.get_system_info()
        
        assert isinstance(system_info, dict)
        assert 'cpu_count' in system_info
        assert 'total_memory_gb' in system_info
        assert 'total_disk_gb' in system_info
        assert system_info['cpu_count'] == 8
        assert system_info['total_memory_gb'] == 16.0


def test_performance_monitor_disabled_prometheus():
    """Test performance monitor with Prometheus disabled."""
    settings = MetricsSettings(enable_prometheus=False)
    monitor = PerformanceMonitor(settings)
    
    # Should not raise errors when recording metrics
    monitor.record_request('GET', '/test', 200, 0.1)
    monitor.record_agent_execution('TestAgent', 'completed', 1.0)
    
    # start_metrics_server should not start server
    with patch('src.performance.monitoring.start_http_server') as mock_start:
        monitor.start_metrics_server()
        mock_start.assert_not_called()


def test_performance_monitor_error_handling():
    """Test error handling in performance monitor."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Mock a metric that raises an exception
        with patch.object(monitor, '_request_duration_histogram', side_effect=Exception("Metric error")):
            # Should not raise exception, should handle gracefully
            monitor.record_request('GET', '/test', 200, 0.1)


def test_metrics_settings_validation():
    """Test MetricsSettings validation."""
    # Valid settings
    settings = MetricsSettings(
        enable_prometheus=True,
        enable_system_metrics=False,
        collection_interval=30,
        registry_port=9091
    )
    assert settings.enable_prometheus is True
    assert settings.enable_system_metrics is False
    assert settings.collection_interval == 30
    assert settings.registry_port == 9091
    
    # Test default values
    default_settings = MetricsSettings()
    assert default_settings.enable_prometheus is True
    assert default_settings.enable_system_metrics is True
    assert default_settings.collection_interval == 15
    assert default_settings.registry_port == 8000


@patch('src.performance.monitoring.threading.Thread')
def test_performance_monitor_background_collection(mock_thread):
    """Test background metrics collection."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        settings = MetricsSettings(enable_system_metrics=True, collection_interval=5)
        monitor = PerformanceMonitor(settings)
        
        monitor.start_background_collection()
        
        # Verify background thread was started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()


def test_performance_monitor_stop_background_collection():
    """Test stopping background metrics collection."""
    with patch('src.performance.monitoring.CollectorRegistry'):
        monitor = PerformanceMonitor()
        
        # Mock running thread
        mock_thread = Mock()
        monitor._collection_thread = mock_thread
        monitor._stop_collection = Mock()
        
        monitor.stop_background_collection()
        
        monitor._stop_collection.set.assert_called_once()
        mock_thread.join.assert_called_once()