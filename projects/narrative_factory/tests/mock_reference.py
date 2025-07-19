"""Mock Configuration Reference for Narrative Factory Tests.

This module provides the correct import paths for mocking services
and components in the Narrative Factory test suite.

Usage:
    from tests.mock_reference import MOCK_PATHS
    
    @patch(MOCK_PATHS['StateManager'])
    def test_something(self, mock_state_manager):
        # Test implementation
        pass
"""

# Correct import paths for mocking services
MOCK_PATHS = {
    # State Management
    'StateManager': 'src.services.state_manager.StateManager',
    
    # Catalyst Management
    'CatalystManager': 'src.services.catalyst_manager.CatalystManager',
    
    # Memory Services
    'QdrantService': 'src.memory.qdrant.QdrantService',
    'MemoryService': 'src.memory.service.MemoryService',
    
    # Agent Classes
    'DirectorAgent': 'src.agents.personas.DirectorAgent',
    'TacticianAgent': 'src.agents.personas.TacticianAgent',
    'WeaverAgent': 'src.agents.personas.WeaverAgent',
    'CanonistAgent': 'src.agents.personas.CanonistAgent',
    
    # Workflow Components
    'JobStore': 'src.workflows.jobs.JobStore',
    'GenerationFlow': 'src.workflows.generation.GenerationFlow',
}

# Common mock patterns for different service types
MOCK_PATTERNS = {
    'async_service': {
        'type': 'AsyncMock',
        'methods': ['async_method_name'],
        'return_values': {}
    },
    'sync_service': {
        'type': 'MagicMock',
        'methods': ['sync_method_name'],
        'return_values': {}
    },
    'state_manager': {
        'type': 'AsyncMock',
        'methods': ['get_state_summary', 'load_latest_state', 'save_state'],
        'return_values': {
            'get_state_summary': {
                'current_chapter': 1,
                'story_id': 'test-story',
                'active_plot_threads': 0
            }
        }
    },
    'catalyst_manager': {
        'type': 'AsyncMock',
        'methods': ['add_catalyst', 'get_catalysts_for_target'],
        'return_values': {
            'add_catalyst': 'test-catalyst-id',
            'get_catalysts_for_target': []
        }
    },
    'qdrant_service': {
        'type': 'MagicMock',
        'methods': ['get_collection_info', 'search_by_content'],
        'return_values': {
            'get_collection_info': {'points_count': 100, 'status': 'green'},
            'search_by_content': [{'source': 'test', 'content': 'test', 'score': 0.95}]
        }
    }
}