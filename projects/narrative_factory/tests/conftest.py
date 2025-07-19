"""Test configuration and fixtures for Narrative Factory."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, Optional


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_memory_service():
    """Create a mock memory service for testing."""
    mock = AsyncMock()
    mock.fetch_context_for_director = AsyncMock(return_value=MagicMock())
    return mock


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager for testing."""
    mock = AsyncMock()
    mock.load_latest_state = AsyncMock()
    mock.save_state = AsyncMock()
    mock.get_state_summary = AsyncMock(return_value={
        "current_chapter": 1,
        "story_id": "test-story",
        "active_plot_threads": 0
    })
    return mock


@pytest.fixture
def mock_catalyst_manager():
    """Create a mock catalyst manager for testing."""
    mock = AsyncMock()
    mock.add_catalyst = AsyncMock(return_value="test-catalyst-id")
    mock.get_catalysts_for_target = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_qdrant_service():
    """Create a mock Qdrant service for testing."""
    mock = MagicMock()
    mock.get_collection_info = MagicMock(return_value={
        'points_count': 100,
        'status': 'green'
    })
    mock.search_by_content = MagicMock(return_value=[
        {
            'source': 'character_sheet',
            'content': 'Test character information...',
            'score': 0.95
        }
    ])
    return mock