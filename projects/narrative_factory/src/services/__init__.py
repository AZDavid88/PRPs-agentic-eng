"""
Service layer initialization for Narrative Factory.

Provides centralized access to all service components including:
- StateManager for story state persistence
- CatalystManager for creative catalyst management
"""

from .catalyst_manager import Catalyst, CatalystManager
from .state_manager import StateManager

__all__ = [
    "StateManager",
    "CatalystManager",
    "Catalyst"
]
