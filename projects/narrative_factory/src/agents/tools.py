"""
Agent tools for Controlflow integration with Narrative Factory systems.

Provides memory access, character analysis, and catalyst injection tools
that enhance agent capabilities while maintaining compatibility with existing
infrastructure.
"""

import asyncio
import json
import os
from typing import Any, Optional

# Load environment variables dynamically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import controlflow as cf
from pydantic import BaseModel, Field

from src.logger import get_logger
from src.memory.qdrant import QdrantService  
from src.services.catalyst_manager import CatalystManager
from src.config import config


logger = get_logger(__name__)


# =============================================================================
# TOOL RESPONSE MODELS
# =============================================================================

class MemoryContext(BaseModel):
    """Structured memory context for agent tools."""
    
    spotlight_memories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Immediately relevant memories for current context"
    )
    ambient_memories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Background story state and unresolved tensions"
    )
    context_summary: str = Field(
        default="",
        description="Human-readable summary of retrieved context"
    )
    retrieval_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the retrieval operation"
    )


class CharacterAnalysis(BaseModel):
    """Character analysis results for narrative agents."""
    
    character_id: str = Field(..., description="Character identifier")
    current_state: str = Field(..., description="Character's current emotional/mental state")
    motivations: list[str] = Field(default_factory=list, description="Active character motivations")
    relationships: dict[str, str] = Field(
        default_factory=dict, 
        description="Relationships with other characters"
    )
    character_arc_status: str = Field(
        default="unknown",
        description="Current position in character development arc"
    )
    available_actions: list[str] = Field(
        default_factory=list,
        description="Actions available to this character in current context"
    )


class CatalystInjection(BaseModel):
    """Catalyst injection results for creative enhancement."""
    
    active_catalysts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Currently active catalysts for this target"
    )
    injection_summary: str = Field(
        default="",
        description="Summary of how catalysts should influence generation"
    )
    priority_catalyst: Optional[dict[str, Any]] = Field(
        None,
        description="Highest priority catalyst if any"
    )


# =============================================================================
# AGENT TOOLS IMPLEMENTATION
# =============================================================================

@cf.tool(include_param_descriptions=False, include_return_description=False)
async def memory_context_tool(
    query: str,
    chapter_context: Optional[str] = None,
    character_focus: Optional[list[str]] = None,
    spotlight_limit: int = 5,
    ambient_limit: int = 3
) -> MemoryContext:
    """Retrieve narrative memory context using two-tier search: spotlight (immediate) and ambient (background)."""
    try:
        logger.info(f"Memory context tool called with query: {query[:100]}...")
        
        # Initialize memory service
        memory_service = QdrantService()
        
        # Use the working two-tier context retrieval method
        context_result = await memory_service.fetch_context_for_director(
            chapter_seed=query,
            active_characters=character_focus or [],
            max_results_per_tier=max(spotlight_limit, ambient_limit)
        )
        
        # Convert context result to our format
        spotlight_results = []
        for item in context_result.spotlight_context:
            spotlight_results.append({
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "score": item.get("score", 0.0)
            })
        
        ambient_results = []
        for item in context_result.ambient_echo:
            ambient_results.append({
                "content": item.get("content", ""),
                "metadata": item.get("metadata", {}),
                "tension_status": item.get("metadata", {}).get("tension_status", "unknown")
            })
        
        # Create context summary
        spotlight_summary = f"Found {len(spotlight_results)} relevant memories"
        ambient_summary = f"Found {len(ambient_results)} background tensions"
        
        context_summary = f"""
Memory Context Retrieved:
- Spotlight: {spotlight_summary}
- Ambient: {ambient_summary}
- Query: {query}
- Focus: {character_focus or 'General narrative context'}
        """.strip()
        
        # Prepare structured response
        memory_context = MemoryContext(
            spotlight_memories=[
                {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "relevance_score": result.get("score", 0.0)
                }
                for result in spotlight_results
            ],
            ambient_memories=[
                {
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                    "tension_status": result.get("metadata", {}).get("tension_status", "unknown")
                }
                for result in ambient_results
            ],
            context_summary=context_summary,
            retrieval_metadata={
                "spotlight_count": len(spotlight_results),
                "ambient_count": len(ambient_results),
                "character_focus": character_focus,
                "chapter_context": chapter_context
            }
        )
        
        logger.info(f"Memory context retrieved: {len(spotlight_results)} spotlight, {len(ambient_results)} ambient")
        return memory_context
        
    except Exception as e:
        logger.error(f"Memory context tool error: {e}")
        # Return empty context rather than failing
        return MemoryContext(
            context_summary=f"Memory retrieval failed: {str(e)}",
            retrieval_metadata={"error": str(e)}
        )


@cf.tool(include_param_descriptions=False, include_return_description=False)
async def character_analysis_tool(
    character_id: str,
    current_scene_context: Optional[str] = None,
    include_relationships: bool = True
) -> CharacterAnalysis:
    """Analyze character state, motivations, relationships and available actions from memory."""
    try:
        logger.info(f"Character analysis tool called for: {character_id}")
        
        # Initialize memory service
        memory_service = QdrantService()
        
        # Use existing context retrieval to get character info
        context_result = await memory_service.fetch_context_for_director(
            chapter_seed=f"character {character_id} current state motivation",
            active_characters=[character_id],
            max_results_per_tier=10
        )
        
        # Combine spotlight and ambient for character analysis
        character_memories = context_result.spotlight_context + context_result.ambient_echo
        
        # Extract character state from memories
        current_state = "unknown"
        motivations = []
        relationships = {}
        available_actions = []
        
        for memory in character_memories:
            metadata = memory.get("metadata", {})
            content = memory.get("content", "")
            
            # Extract state information (this would be more sophisticated in production)
            if "emotional_state" in metadata:
                current_state = metadata["emotional_state"]
            
            if "motivations" in metadata:
                motivations.extend(metadata.get("motivations", []))
            
            if include_relationships and "relationships" in metadata:
                relationships.update(metadata.get("relationships", {}))
            
            # Analyze available actions based on context
            if current_scene_context and current_scene_context.lower() in content.lower():
                # Extract potential actions from scene context
                available_actions.append(f"React to current scene: {current_scene_context}")
        
        # Determine character arc status
        arc_status = "developing"
        if len(character_memories) > 5:
            arc_status = "established"
        
        character_analysis = CharacterAnalysis(
            character_id=character_id,
            current_state=current_state,
            motivations=list(set(motivations)),  # Remove duplicates
            relationships=relationships,
            character_arc_status=arc_status,
            available_actions=available_actions
        )
        
        logger.info(f"Character analysis completed for {character_id}")
        return character_analysis
        
    except Exception as e:
        logger.error(f"Character analysis tool error: {e}")
        # Return minimal analysis rather than failing
        return CharacterAnalysis(
            character_id=character_id,
            current_state=f"Error analyzing character: {str(e)}",
            available_actions=["Unable to determine available actions due to analysis error"]
        )


@cf.tool(include_param_descriptions=False, include_return_description=False)
async def catalyst_injection_tool(
    target: str = "next",
    include_used: bool = False
) -> CatalystInjection:
    """Retrieve active creative catalysts to influence narrative generation direction."""
    try:
        logger.info(f"Catalyst injection tool called for target: {target}")
        
        # Initialize catalyst manager
        catalyst_manager = CatalystManager()
        
        # Retrieve active catalysts using the correct method
        active_catalysts = await catalyst_manager.get_catalysts_for_target(target=target)
        
        if include_used:
            # For used catalysts, we'd need to access the internal _load_catalysts method
            # For now, skip used catalysts in this implementation
            pass
        
        # Convert catalysts to dictionaries for tool response
        catalyst_dicts = []
        priority_catalyst = None
        highest_priority = 0
        
        for catalyst in active_catalysts:
            catalyst_dict = {
                "id": catalyst.id,
                "description": catalyst.description,
                "priority": catalyst.priority,
                "target": catalyst.target,
                "status": catalyst.status,
                "created_at": catalyst.created_at.isoformat(),
                "metadata": catalyst.metadata
            }
            catalyst_dicts.append(catalyst_dict)
            
            # Track highest priority catalyst
            if catalyst.priority > highest_priority:
                highest_priority = catalyst.priority
                priority_catalyst = catalyst_dict
        
        # Create injection summary
        if catalyst_dicts:
            injection_summary = f"""
Active catalysts for {target}:
- {len(catalyst_dicts)} catalysts available
- Priority range: {min(c['priority'] for c in catalyst_dicts)} to {max(c['priority'] for c in catalyst_dicts)}
- Highest priority: {priority_catalyst['description'] if priority_catalyst else 'None'}

These catalysts should be woven into the narrative generation to enhance creativity and direction.
            """.strip()
        else:
            injection_summary = f"No active catalysts found for target: {target}"
        
        catalyst_injection = CatalystInjection(
            active_catalysts=catalyst_dicts,
            injection_summary=injection_summary,
            priority_catalyst=priority_catalyst
        )
        
        logger.info(f"Catalyst injection prepared: {len(catalyst_dicts)} catalysts")
        return catalyst_injection
        
    except Exception as e:
        logger.error(f"Catalyst injection tool error: {e}")
        # Return empty injection rather than failing
        return CatalystInjection(
            injection_summary=f"Catalyst injection failed: {str(e)}",
            active_catalysts=[]
        )


# =============================================================================
# TOOL REGISTRY AND UTILITIES
# =============================================================================

# Standard tool set for narrative agents
NARRATIVE_TOOLS = [
    memory_context_tool,
    character_analysis_tool,
    catalyst_injection_tool
]


def get_agent_tools(
    include_memory: bool = True,
    include_character_analysis: bool = True,
    include_catalyst: bool = True,
    custom_tools: Optional[list] = None
) -> list:
    """
    Get a customized set of tools for agent configuration.
    
    Args:
        include_memory: Include memory context tool
        include_character_analysis: Include character analysis tool
        include_catalyst: Include catalyst injection tool
        custom_tools: Additional custom tools to include
        
    Returns:
        List of tools for agent configuration
    """
    tools = []
    
    if include_memory:
        tools.append(memory_context_tool)
    
    if include_character_analysis:
        tools.append(character_analysis_tool)
    
    if include_catalyst:
        tools.append(catalyst_injection_tool)
    
    if custom_tools:
        tools.extend(custom_tools)
    
    return tools


# Async initialization function for tool setup
async def initialize_agent_tools() -> bool:
    """
    Initialize and validate all agent tools.
    
    Returns:
        True if all tools initialized successfully
    """
    try:
        logger.info("Initializing agent tools...")
        
        # Test memory service connection
        memory_service = QdrantService()
        # Test with a simple fetch operation
        test_result = await memory_service.fetch_context_for_director(
            chapter_seed="test",
            active_characters=[],
            max_results_per_tier=1
        )
        logger.info("✅ Memory service initialized")
        
        # Test catalyst manager
        catalyst_manager = CatalystManager()
        # Test with get_catalysts_for_target method
        test_catalysts = await catalyst_manager.get_catalysts_for_target("test")
        logger.info("✅ Catalyst manager initialized")
        logger.info("✅ Catalyst manager initialized")
        
        logger.info("✅ All agent tools initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Agent tools initialization failed: {e}")
        return False


if __name__ == "__main__":
    async def test_tools():
        """Test tool functionality."""
        print("Testing agent tools...")
        
        # Initialize tools
        success = await initialize_agent_tools()
        if not success:
            print("❌ Tool initialization failed")
            return
        
        # Test memory context tool function directly
        try:
            memory_result = await memory_context_tool.fn(
                query="character development and motivation",
                character_focus=["protagonist"],
                spotlight_limit=3
            )
            print(f"✅ Memory tool: {len(memory_result.spotlight_memories)} spotlight memories")
        except Exception as e:
            print(f"❌ Memory tool error: {e}")
        
        # Test character analysis tool function directly
        try:
            character_result = await character_analysis_tool.fn(
                character_id="protagonist",
                current_scene_context="palace intrigue"
            )
            print(f"✅ Character tool: {character_result.character_id} analysis complete")
        except Exception as e:
            print(f"❌ Character tool error: {e}")
        
        # Test catalyst injection tool function directly
        try:
            catalyst_result = await catalyst_injection_tool.fn(target="next")
            print(f"✅ Catalyst tool: {len(catalyst_result.active_catalysts)} catalysts")
        except Exception as e:
            print(f"❌ Catalyst tool error: {e}")
        
        print("Tool testing complete!")
    
    asyncio.run(test_tools())