"""
Multi-agent collaborative narrative generation using Controlflow.

Implements structured workflows where multiple AI agents collaborate
to create strategic briefs, tactical plans, and prose generation with
shared narrative context and tool integration.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import controlflow as cf
from pydantic import BaseModel

from src.agents.enhanced_personas import (
    NarrativeDirectorAgent,
    NarrativeTacticianAgent,
    NarrativeWeaverAgent,
    NarrativeCanonistAgent,
    create_full_agent_team,
    load_environment
)
from src.logger import get_logger
from src.models import StrategicBrief, ChapterBlueprint


logger = get_logger(__name__)


# Load environment variables for API access
load_environment()


class CollaborativeGenerationRequest(BaseModel):
    """Request model for collaborative narrative generation."""
    chapter_seed: str
    active_characters: List[str] = []
    narrative_context: Optional[str] = None
    genre_context: str = "fantasy"
    target_length: str = "medium"  # short, medium, long
    approval_required: bool = False


class CollaborativeGenerationResult(BaseModel):
    """Result model for collaborative narrative generation."""
    strategic_brief: StrategicBrief
    chapter_blueprint: ChapterBlueprint
    generated_prose: str
    validation_report: Dict[str, Any]
    collaboration_metadata: Dict[str, Any]


@cf.flow
def narrative_collaboration_flow(
    chapter_seed: str,
    active_characters: Optional[List[str]] = None,
    narrative_context: Optional[str] = None
) -> CollaborativeGenerationResult:
    """
    Main collaborative narrative generation flow.
    
    Orchestrates Director → Tactician → Weaver → Canonist collaboration
    with shared context and tool integration.
    
    Args:
        chapter_seed: Seed concept for the chapter
        active_characters: List of active character IDs
        narrative_context: Optional narrative context
        
    Returns:
        Complete collaborative generation result
    """
    logger.info(f"Starting collaborative narrative generation for: {chapter_seed}")
    
    # Create agent team
    agents = create_full_agent_team()
    director = agents["director"]
    tactician = agents["tactician"] 
    weaver = agents["weaver"]
    canonist = agents["canonist"]
    
    # Shared context for all agents
    context_data = {
        "chapter_seed": chapter_seed,
        "active_characters": active_characters or [],
        "narrative_context": narrative_context or "No additional context provided"
    }
    
    # Phase 1: Strategic Brief Creation (Director)
    logger.info("Phase 1: Director creating strategic brief...")
    strategic_brief = cf.run(
        f"Create a strategic brief for chapter with seed: '{chapter_seed}'. "
        f"Focus on narrative direction, key plot points, character focus, and pacing. "
        f"Active characters: {', '.join(active_characters or [])}",
        result_type=StrategicBrief,
        agents=[director],
        context=context_data
    )
    
    # Phase 2: Tactical Planning (Tactician) 
    logger.info("Phase 2: Tactician creating tactical plan...")
    tactical_context = {**context_data, "strategic_brief": strategic_brief}
    
    chapter_blueprint = cf.run(
        f"Create a detailed chapter blueprint based on the strategic brief. "
        f"Include scene structure, dialogue points, and narrative flow. "
        f"Ensure alignment with the strategic direction provided.",
        result_type=ChapterBlueprint,
        agents=[tactician],
        context=tactical_context
    )
    
    # Phase 3: Prose Generation (Weaver)
    logger.info("Phase 3: Weaver generating prose...")
    prose_context = {
        **context_data, 
        "strategic_brief": strategic_brief,
        "chapter_blueprint": chapter_blueprint
    }
    
    generated_prose = cf.run(
        f"Generate compelling prose based on the strategic brief and chapter blueprint. "
        f"Maintain narrative voice, character consistency, and story flow. "
        f"Target length: approximately 800-1200 words.",
        result_type=str,
        agents=[weaver],
        context=prose_context
    )
    
    # Phase 4: Validation & Consistency Check (Canonist)
    logger.info("Phase 4: Canonist validating output...")
    validation_context = {
        **context_data,
        "strategic_brief": strategic_brief,
        "chapter_blueprint": chapter_blueprint,
        "generated_prose": generated_prose
    }
    
    validation_report = cf.run(
        f"Validate the generated content for narrative consistency, character continuity, "
        f"and adherence to the strategic brief. Identify any issues and provide "
        f"recommendations for improvement.",
        result_type=dict,
        agents=[canonist],
        context=validation_context
    )
    
    # Compile final result
    result = CollaborativeGenerationResult(
        strategic_brief=strategic_brief,
        chapter_blueprint=chapter_blueprint,
        generated_prose=generated_prose,
        validation_report=validation_report,
        collaboration_metadata={
            "agents_used": ["director", "tactician", "weaver", "canonist"],
            "chapter_seed": chapter_seed,
            "active_characters": active_characters or [],
            "generation_flow": "sequential_collaboration"
        }
    )
    
    logger.info("Collaborative narrative generation completed successfully")
    return result


@cf.flow
def interactive_narrative_collaboration(
    chapter_seed: str,
    active_characters: Optional[List[str]] = None,
    enable_human_review: bool = True
) -> CollaborativeGenerationResult:
    """
    Interactive collaborative flow with human review checkpoints.
    
    Args:
        chapter_seed: Seed concept for the chapter
        active_characters: List of active character IDs
        enable_human_review: Whether to enable human review checkpoints
        
    Returns:
        Complete collaborative generation result with human input
    """
    logger.info(f"Starting interactive collaborative generation: {chapter_seed}")
    
    # Create agent team
    agents = create_full_agent_team()
    director = agents["director"]
    tactician = agents["tactician"]
    weaver = agents["weaver"]
    canonist = agents["canonist"]
    
    # Phase 1: Director Strategic Brief
    strategic_brief = cf.run(
        f"Create strategic brief for: {chapter_seed}",
        result_type=StrategicBrief,
        agents=[director],
        interactive=enable_human_review  # Allow human input during execution
    )
    
    # Human checkpoint: Review strategic brief
    if enable_human_review:
        logger.info("Human review checkpoint: Strategic brief ready for review")
        # In a real implementation, this would integrate with a web interface
        # For now, we'll continue with the generated brief
    
    # Phase 2: Tactician Planning
    chapter_blueprint = cf.run(
        f"Create tactical plan based on strategic brief",
        result_type=ChapterBlueprint,
        agents=[tactician],
        context={"strategic_brief": strategic_brief},
        interactive=enable_human_review
    )
    
    # Phase 3: Weaver Prose Generation
    generated_prose = cf.run(
        f"Generate prose from blueprint",
        result_type=str,
        agents=[weaver],
        context={
            "strategic_brief": strategic_brief,
            "chapter_blueprint": chapter_blueprint
        }
    )
    
    # Phase 4: Canonist Validation
    validation_report = cf.run(
        f"Validate generated content",
        result_type=dict,
        agents=[canonist],
        context={
            "strategic_brief": strategic_brief,
            "chapter_blueprint": chapter_blueprint, 
            "generated_prose": generated_prose
        }
    )
    
    return CollaborativeGenerationResult(
        strategic_brief=strategic_brief,
        chapter_blueprint=chapter_blueprint,
        generated_prose=generated_prose,
        validation_report=validation_report,
        collaboration_metadata={
            "agents_used": ["director", "tactician", "weaver", "canonist"],
            "chapter_seed": chapter_seed,
            "active_characters": active_characters or [],
            "generation_flow": "interactive_collaboration",
            "human_review_enabled": enable_human_review
        }
    )


@cf.flow
def parallel_agent_analysis(
    content_to_analyze: str,
    analysis_type: str = "comprehensive"
) -> Dict[str, Any]:
    """
    Parallel analysis flow where multiple agents analyze content simultaneously.
    
    Args:
        content_to_analyze: Content for multi-agent analysis
        analysis_type: Type of analysis (comprehensive, quick, focused)
        
    Returns:
        Combined analysis results from all agents
    """
    logger.info(f"Starting parallel agent analysis: {analysis_type}")
    
    # Create agent team
    agents = create_full_agent_team()
    
    # Define parallel analysis tasks
    director_analysis = cf.run(
        f"Analyze this content from a strategic narrative perspective: {content_to_analyze}",
        agents=[agents["director"]],
        result_type=dict
    )
    
    tactician_analysis = cf.run(
        f"Analyze this content from a tactical scene structure perspective: {content_to_analyze}",
        agents=[agents["tactician"]],
        result_type=dict
    )
    
    weaver_analysis = cf.run(
        f"Analyze this content from a prose and writing craft perspective: {content_to_analyze}",
        agents=[agents["weaver"]],
        result_type=dict
    )
    
    canonist_analysis = cf.run(
        f"Analyze this content for consistency and continuity issues: {content_to_analyze}",
        agents=[agents["canonist"]],
        result_type=dict
    )
    
    # Combine results
    combined_analysis = {
        "director_analysis": director_analysis,
        "tactician_analysis": tactician_analysis,
        "weaver_analysis": weaver_analysis,
        "canonist_analysis": canonist_analysis,
        "analysis_metadata": {
            "content_length": len(content_to_analyze),
            "analysis_type": analysis_type,
            "agents_count": 4
        }
    }
    
    logger.info("Parallel agent analysis completed")
    return combined_analysis


# Convenience functions for direct usage
async def generate_chapter_collaboratively(
    chapter_seed: str,
    active_characters: Optional[List[str]] = None,
    narrative_context: Optional[str] = None
) -> CollaborativeGenerationResult:
    """
    Convenience function for collaborative chapter generation.
    
    Args:
        chapter_seed: Seed concept for the chapter
        active_characters: List of active character IDs
        narrative_context: Optional narrative context
        
    Returns:
        Complete collaborative generation result
    """
    return narrative_collaboration_flow(
        chapter_seed=chapter_seed,
        active_characters=active_characters,
        narrative_context=narrative_context
    )


def test_collaborative_workflow():
    """Test function for the collaborative workflow."""
    logger.info("Testing collaborative narrative workflow...")
    
    try:
        # Test basic collaboration
        result = narrative_collaboration_flow(
            chapter_seed="Ren discovers a hidden magical ability during a palace intrigue",
            active_characters=["ren", "palace_guard", "mysterious_advisor"],
            narrative_context="Fantasy palace setting with political tensions"
        )
        
        logger.info("✅ Basic collaborative workflow test successful")
        logger.info(f"Generated strategic brief: {result.strategic_brief.narrative_direction[:100]}...")
        logger.info(f"Generated prose length: {len(result.generated_prose)} characters")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Collaborative workflow test failed: {e}")
        return False


if __name__ == "__main__":
    """Test the collaborative workflows when run directly."""
    print("Testing collaborative narrative generation workflows...")
    
    # Run test
    success = test_collaborative_workflow()
    
    if success:
        print("✅ Collaborative workflow testing completed successfully!")
    else:
        print("❌ Collaborative workflow testing failed!")
        
    print("Collaborative generation testing complete!")