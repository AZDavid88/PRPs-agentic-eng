"""Collaborative generation routes for web interface."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from src.workflows.collaborative_generation import (
    narrative_collaboration_flow,
    interactive_narrative_collaboration,
    parallel_agent_analysis,
    CollaborativeGenerationRequest,
    CollaborativeGenerationResult
)
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/generate", response_model=CollaborativeGenerationResult)
async def generate_collaborative_chapter(
    request: CollaborativeGenerationRequest
) -> CollaborativeGenerationResult:
    """
    Generate chapter using collaborative multi-agent workflow.
    
    This endpoint uses Controlflow for direct agent-to-agent collaboration
    without Human-in-the-Loop pause points.
    """
    logger.info(f"Starting collaborative generation for seed: {request.chapter_seed}")
    
    try:
        result = narrative_collaboration_flow(
            chapter_seed=request.chapter_seed,
            active_characters=request.active_characters,
            narrative_context=request.narrative_context
        )
        
        logger.info("Collaborative generation completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Collaborative generation failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Collaborative generation failed: {str(e)}"
        )


@router.post("/interactive", response_model=CollaborativeGenerationResult)
async def generate_interactive_collaborative(
    request: CollaborativeGenerationRequest
) -> CollaborativeGenerationResult:
    """
    Generate chapter using interactive collaborative workflow with human review checkpoints.
    
    This endpoint enables human review during the collaborative process.
    """
    logger.info(f"Starting interactive collaborative generation for seed: {request.chapter_seed}")
    
    try:
        result = interactive_narrative_collaboration(
            chapter_seed=request.chapter_seed,
            active_characters=request.active_characters,
            enable_human_review=request.approval_required
        )
        
        logger.info("Interactive collaborative generation completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Interactive collaborative generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Interactive collaborative generation failed: {str(e)}"
        )


class AnalysisRequest(BaseModel):
    """Request model for parallel agent analysis."""
    content_to_analyze: str
    analysis_type: str = "comprehensive"


@router.post("/analyze")
async def analyze_content_collaboratively(
    request: AnalysisRequest
) -> Dict[str, Any]:
    """
    Analyze content using parallel multi-agent analysis.
    
    All four agents (Director, Tactician, Weaver, Canonist) analyze 
    the provided content simultaneously from their respective perspectives.
    """
    logger.info(f"Starting parallel agent analysis: {request.analysis_type}")
    
    try:
        result = parallel_agent_analysis(
            content_to_analyze=request.content_to_analyze,
            analysis_type=request.analysis_type
        )
        
        logger.info("Parallel agent analysis completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Parallel agent analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Parallel agent analysis failed: {str(e)}"
        )


@router.get("/status")
async def collaborative_status() -> Dict[str, Any]:
    """
    Get status information for collaborative generation system.
    """
    try:
        # Test if collaborative workflows are accessible
        from src.agents.enhanced_personas import create_full_agent_team
        
        # Validate agent team creation
        agents = create_full_agent_team()
        
        return {
            "status": "operational",
            "workflow_type": "controlflow_collaborative", 
            "available_agents": list(agents.keys()),
            "available_workflows": [
                "narrative_collaboration_flow",
                "interactive_narrative_collaboration", 
                "parallel_agent_analysis"
            ],
            "features": {
                "multi_agent_collaboration": True,
                "human_review_checkpoints": True,
                "parallel_analysis": True,
                "controlflow_integration": True
            }
        }
        
    except Exception as e:
        logger.error(f"Collaborative status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Collaborative system status check failed: {str(e)}"
        )