"""
Enhanced agent personas using Controlflow integration.

Provides Controlflow-based agent wrappers that preserve existing persona loading
patterns while adding multi-agent collaboration capabilities and tool integration.
"""

import os
from pathlib import Path
from typing import Optional

import controlflow as cf

from src.agents.personas import get_persona_manager
from src.agents.tools import NARRATIVE_TOOLS
from src.logger import get_logger


logger = get_logger(__name__)


def load_environment() -> None:
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent.parent / ".env"
    
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
        logger.info("Environment variables loaded from .env file")
        logger.info(f"OpenAI API Key loaded: {bool(os.environ.get('OPENAI_API_KEY'))}")
        logger.info(f"Google API Key loaded: {bool(os.environ.get('GOOGLE_API_KEY'))}")
    else:
        logger.warning(f"Environment file not found: {env_file}")


# Load environment variables on module import
load_environment()

# Configure Controlflow default model to eliminate warnings
try:
    import controlflow as cf
    # Set default model to match our agent configuration
    cf.defaults.model = "google/gemini-2.5-flash"
    logger.info("Controlflow default model set to google/gemini-2.5-flash")
except Exception as e:
    logger.warning(f"Could not set Controlflow default model: {e}")


class NarrativeDirectorAgent(cf.Agent):
    """
    Strategic narrative planning agent using Controlflow.
    
    Focuses on high-level story direction, pacing, and character development arcs.
    Uses Google Gemini 2.5 Flash for strategic reasoning and planning precision.
    """
    
    def __init__(self, memory_service: Optional[object] = None):
        """Initialize the Director agent with persona and tools."""
        persona_manager = get_persona_manager()
        director_instructions = persona_manager.get_persona("director")
        
        super().__init__(
            name="NarrativeDirector",
            instructions=director_instructions,
            tools=NARRATIVE_TOOLS,
            model="google/gemini-2.5-flash"  # Google Gemini 2.5 Flash for strategic planning
        )
        
        logger.info("NarrativeDirectorAgent initialized with Google Gemini 2.5 Flash")


class NarrativeTacticianAgent(cf.Agent):
    """
    Detailed scene planning agent using Controlflow.
    
    Focuses on scene-by-scene tactical planning, dialogue structure, and pacing.
    Uses Google Gemini 2.5 Flash for detailed tactical planning with long context.
    """
    
    def __init__(self, memory_service: Optional[object] = None):
        """Initialize the Tactician agent with persona and tools."""
        persona_manager = get_persona_manager()
        tactician_instructions = persona_manager.get_persona("tactician")
        
        super().__init__(
            name="NarrativeTactician", 
            instructions=tactician_instructions,
            tools=NARRATIVE_TOOLS,
            model="google/gemini-2.5-flash"  # Google Gemini 2.5 Flash for tactical planning
        )
        
        logger.info("NarrativeTacticianAgent initialized with Google Gemini 2.5 Flash")


class NarrativeWeaverAgent(cf.Agent):
    """
    Prose generation agent using Controlflow.
    
    Focuses on crafting compelling prose, dialogue, and narrative voice.
    Uses Google Gemini 2.5 Flash for superior prose quality and creative output.
    """
    
    def __init__(self, memory_service: Optional[object] = None):
        """Initialize the Weaver agent with persona and tools."""
        persona_manager = get_persona_manager()
        weaver_instructions = persona_manager.get_persona("weaver")
        
        super().__init__(
            name="NarrativeWeaver",
            instructions=weaver_instructions, 
            tools=NARRATIVE_TOOLS,
            model="google/gemini-2.5-flash"  # Google Gemini 2.5 Flash for prose generation
        )
        
        logger.info("NarrativeWeaverAgent initialized with Google Gemini 2.5 Flash")


class NarrativeCanonistAgent(cf.Agent):
    """
    Continuity and consistency validation agent using Controlflow.
    
    Focuses on maintaining narrative consistency, character continuity, and lore accuracy.
    Uses Google Gemini 2.5 Flash for long-context analysis and continuity checking.
    """
    
    def __init__(self, memory_service: Optional[object] = None):
        """Initialize the Canonist agent with persona and tools."""
        persona_manager = get_persona_manager()
        canonist_instructions = persona_manager.get_persona("canonist")
        
        super().__init__(
            name="NarrativeCanonist",
            instructions=canonist_instructions,
            tools=NARRATIVE_TOOLS, 
            model="google/gemini-2.5-flash"  # Google Gemini 2.5 Flash for validation analysis
        )
        
        logger.info("NarrativeCanonistAgent initialized with Google Gemini 2.5 Flash")


# Agent registry for easy access
NARRATIVE_AGENTS = {
    "director": NarrativeDirectorAgent,
    "tactician": NarrativeTacticianAgent, 
    "weaver": NarrativeWeaverAgent,
    "canonist": NarrativeCanonistAgent
}


def create_agent(agent_type: str, memory_service: Optional[object] = None) -> cf.Agent:
    """
    Factory function to create narrative agents.
    
    Args:
        agent_type: Type of agent (director, tactician, weaver, canonist)
        memory_service: Optional memory service for context retrieval
        
    Returns:
        Configured Controlflow agent
        
    Raises:
        ValueError: If agent_type is not recognized
    """
    if agent_type not in NARRATIVE_AGENTS:
        raise ValueError(f"Unknown agent type: {agent_type}. Available: {list(NARRATIVE_AGENTS.keys())}")
    
    agent_class = NARRATIVE_AGENTS[agent_type]
    return agent_class(memory_service=memory_service)


def create_full_agent_team(memory_service: Optional[object] = None) -> dict[str, cf.Agent]:
    """
    Create a complete team of narrative agents.
    
    Args:
        memory_service: Optional memory service for context retrieval
        
    Returns:
        Dictionary of agent_name -> agent_instance
    """
    team = {}
    for agent_type in NARRATIVE_AGENTS.keys():
        team[agent_type] = create_agent(agent_type, memory_service)
        
    logger.info(f"Created full narrative agent team: {list(team.keys())}")
    return team


# Health check function
def validate_agents() -> dict[str, bool]:
    """
    Validate that all agent types can be instantiated.
    
    Returns:
        Dictionary of agent_type -> success_status
    """
    validation_results = {}
    
    for agent_type in NARRATIVE_AGENTS.keys():
        try:
            agent = create_agent(agent_type)
            validation_results[agent_type] = True
            logger.debug(f"✅ {agent_type} agent validation successful")
        except Exception as e:
            validation_results[agent_type] = False
            logger.error(f"❌ {agent_type} agent validation failed: {e}")
    
    success_count = sum(validation_results.values())
    total_count = len(validation_results)
    
    logger.info(f"Agent validation complete: {success_count}/{total_count} successful")
    return validation_results


if __name__ == "__main__":
    """Test the enhanced personas when run directly."""
    print("Testing enhanced narrative agents...")
    
    # Validate all agents
    results = validate_agents()
    
    # Create sample team
    try:
        team = create_full_agent_team()
        print(f"✅ Full agent team created successfully: {list(team.keys())}")
        
        # Test individual agent access
        director = team["director"]
        print(f"✅ Director agent: {director.name} with model {director.model}")
        
    except Exception as e:
        print(f"❌ Agent team creation failed: {e}")
        
    print("Enhanced personas testing complete!")