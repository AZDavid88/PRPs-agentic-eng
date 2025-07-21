"""Prefect workflow orchestration for Narrative Factory.

This module contains:
- JobStore: Redis-based state management for HITL workflows  
- Generation flows: Orchestrated agent pipelines with pause points
- Collaborative flows: Multi-agent Controlflow-based workflows
- Enhanced flows: Sophisticated agent workflows with advanced capabilities
"""

# Import collaborative workflows for easy access
from .collaborative_generation import (
    narrative_collaboration_flow,
    interactive_narrative_collaboration,
    parallel_agent_analysis,
    generate_chapter_collaboratively
)

__all__ = [
    "narrative_collaboration_flow",
    "interactive_narrative_collaboration", 
    "parallel_agent_analysis",
    "generate_chapter_collaboratively"
]
