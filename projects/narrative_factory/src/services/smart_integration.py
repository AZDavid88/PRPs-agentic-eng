"""
Smart Integration Service for Dynamic Content Injection.

Uses existing DirectorAgent and CanonistAgent to provide intelligent
suggestions for integrating new story elements with existing content.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.agents.personas import DirectorAgent, CanonistAgent, TacticianAgent
from src.memory.qdrant import QdrantService
from src.models.material_models import MaterialIngestionRequest
from src.ingestion.pipeline import MaterialIngestionPipeline
from src.logger import get_logger

logger = get_logger(__name__)

class IntegrationSuggestion:
    """Structured integration suggestion from AI agents."""
    
    def __init__(self, element_type: str, element_name: str):
        self.element_type = element_type
        self.element_name = element_name
        self.optimal_introduction_chapter: Optional[int] = None
        self.integration_approach: str = ""
        self.relationship_impacts: List[str] = []
        self.plot_considerations: List[str] = []
        self.continuity_risks: List[str] = []
        self.suggestions: List[str] = []

class SmartIntegrationService:
    """Provides AI-assisted integration suggestions for new story elements."""
    
    def __init__(self):
        self.director = DirectorAgent()
        self.canonist = CanonistAgent()
        self.tactician = TacticianAgent()
        self.qdrant = QdrantService()
        self.ingestion_pipeline = MaterialIngestionPipeline()
    
    async def suggest_character_integration(
        self, 
        character_name: str, 
        character_description: str,
        target_chapter: Optional[int] = None,
        story_id: Optional[str] = None
    ) -> IntegrationSuggestion:
        """
        Analyze how to integrate new character using Director and Canonist agents.
        
        Args:
            character_name: Name of new character
            character_description: Character background and traits
            target_chapter: Desired introduction chapter (optional)
            story_id: Story context for analysis
            
        Returns:
            IntegrationSuggestion with AI analysis
        """
        logger.info(f"Analyzing integration for character: {character_name}")
        
        # Get existing story context
        story_context = await self._get_story_context(story_id)
        
        # Director analyzes strategic integration
        director_prompt = f"""
        Analyze integrating new character into existing story:
        
        New Character: {character_name}
        Description: {character_description}
        Target Introduction: Chapter {target_chapter or 'TBD'}
        
        Existing Story Context:
        {self._format_story_context(story_context)}
        
        Provide strategic analysis:
        1. Optimal introduction timing and approach
        2. How this character advances the plot
        3. Relationship dynamics with existing characters
        4. Potential story complications and opportunities
        """
        
        director_analysis = await self.director.execute(director_prompt, story_context)
        
        # Canonist checks for continuity issues
        canonist_prompt = f"""
        Check continuity for new character integration:
        
        New Character: {character_name} - {character_description}
        
        Existing Characters and World State:
        {self._format_character_context(story_context)}
        
        Identify:
        1. Potential continuity conflicts
        2. Required background story adjustments
        3. Relationship establishment requirements
        4. World-building consistency checks
        """
        
        canonist_analysis = await self.canonist.execute(canonist_prompt, story_context)
        
        # Compile suggestions
        suggestion = IntegrationSuggestion("character", character_name)
        suggestion = self._parse_integration_analysis(
            suggestion, director_analysis, canonist_analysis
        )
        
        logger.info(f"Integration analysis complete for {character_name}")
        return suggestion
    
    async def suggest_context_integration(
        self,
        content: str,
        context_type: str,  # "location", "technology", "magic", "plot"
        from_chapter: Optional[int] = None,
        story_id: Optional[str] = None
    ) -> IntegrationSuggestion:
        """
        Analyze how to integrate new story context (location, tech, etc.).
        """
        logger.info(f"Analyzing integration for {context_type}: {content[:50]}...")
        
        story_context = await self._get_story_context(story_id)
        
        # Director analyzes strategic value
        director_prompt = f"""
        Analyze integrating new {context_type} into story:
        
        New {context_type.title()}: {content}
        Introduction from: Chapter {from_chapter or 'TBD'}
        
        Current Story State:
        {self._format_story_context(story_context)}
        
        Strategic Analysis:
        1. How this {context_type} enhances the narrative
        2. Optimal introduction and revelation timing  
        3. Impact on existing plot threads
        4. Character interaction opportunities
        """
        
        director_analysis = await self.director.execute(director_prompt, story_context)
        
        # Canonist validates consistency
        canonist_prompt = f"""
        Validate {context_type} integration for continuity:
        
        New Element: {content}
        
        Existing World State:
        {self._format_world_context(story_context)}
        
        Continuity Validation:
        1. Consistency with established world rules
        2. Required backstory or explanation
        3. Impact on existing locations/systems
        4. Timeline and causality considerations
        """
        
        canonist_analysis = await self.canonist.execute(canonist_prompt, story_context)
        
        suggestion = IntegrationSuggestion(context_type, content[:30] + "...")
        suggestion = self._parse_integration_analysis(
            suggestion, director_analysis, canonist_analysis
        )
        
        return suggestion
    
    async def execute_integration(
        self,
        content: str,
        content_type: str,
        story_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Execute the integration by ingesting content through existing pipeline.
        """
        try:
            # Create ingestion request using existing patterns
            ingestion_request = MaterialIngestionRequest(
                content=content,
                source_path="dynamic_injection",
                genre="fantasy",  # Default, should be configurable
                additional_genres=[],
                custom_categories=[content_type],
                story_id=story_id,
                metadata=metadata or {}
            )
            
            # Use existing ingestion pipeline
            response = await self.ingestion_pipeline.ingest_materials([ingestion_request])
            
            if response.success:
                logger.info(f"Successfully integrated {content_type} content")
                return True
            else:
                logger.error(f"Integration failed: {response.error}")
                return False
                
        except Exception as e:
            logger.error(f"Integration execution failed: {e}")
            return False
    
    async def _get_story_context(self, story_id: Optional[str]) -> Dict[str, Any]:
        """Get comprehensive story context for analysis."""
        context = {
            "characters": [],
            "locations": [],
            "plot_threads": [],
            "world_building": []
        }
        
        if not story_id:
            return context
        
        try:
            # Get different content types using existing memory methods
            characters = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "character_sheet"},
                collection_name="world_bible",
                limit=20
            )
            
            locations = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "location"},
                collection_name="world_bible",
                limit=15
            )
            
            plot_threads = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "plot_thread"},
                collection_name="world_bible",
                limit=10
            )
            
            world_building = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "world_building"},
                collection_name="world_bible",
                limit=10
            )
            
            context.update({
                "characters": characters,
                "locations": locations, 
                "plot_threads": plot_threads,
                "world_building": world_building
            })
            
        except Exception as e:
            logger.warning(f"Failed to get story context: {e}")
        
        return context
    
    def _format_story_context(self, context: Dict[str, Any]) -> str:
        """Format story context for agent consumption."""
        formatted = []
        
        if context.get("characters"):
            formatted.append("CHARACTERS:")
            for char in context["characters"][:5]:  # Limit for context size
                formatted.append(f"- {char.get('content', '')[:100]}...")
        
        if context.get("locations"):
            formatted.append("\nLOCATIONS:")
            for loc in context["locations"][:3]:
                formatted.append(f"- {loc.get('content', '')[:100]}...")
        
        if context.get("plot_threads"):
            formatted.append("\nPLOT THREADS:")
            for plot in context["plot_threads"][:3]:
                formatted.append(f"- {plot.get('content', '')[:100]}...")
        
        return "\n".join(formatted) if formatted else "No existing story context found."
    
    def _format_character_context(self, context: Dict[str, Any]) -> str:
        """Format character-specific context."""
        if not context.get("characters"):
            return "No existing characters found."
        
        char_summaries = []
        for char in context["characters"][:8]:
            char_summaries.append(char.get("content", "")[:150] + "...")
        
        return "\n\n".join(char_summaries)
    
    def _format_world_context(self, context: Dict[str, Any]) -> str:
        """Format world-building context."""
        world_elements = []
        
        for category in ["locations", "world_building"]:
            if context.get(category):
                for item in context[category][:5]:
                    world_elements.append(item.get("content", "")[:150] + "...")
        
        return "\n\n".join(world_elements) if world_elements else "No world context found."
    
    def _parse_integration_analysis(
        self, 
        suggestion: IntegrationSuggestion,
        director_analysis: Any,
        canonist_analysis: Any
    ) -> IntegrationSuggestion:
        """Parse agent outputs into structured suggestions."""
        # This would parse the agent outputs and populate the suggestion
        # For now, using placeholder logic - in practice, would parse agent responses
        
        suggestion.integration_approach = "Gradual introduction with relationship development"
        suggestion.optimal_introduction_chapter = None  # Would be parsed from director
        suggestion.relationship_impacts = ["Creates new alliance dynamics", "Shifts power balance"]
        suggestion.plot_considerations = ["Advances main quest", "Adds complexity to character motivations"]
        suggestion.continuity_risks = ["Ensure consistent background", "Verify relationship timeline"]
        suggestion.suggestions = [
            "Introduce through existing character connection",
            "Establish motivation early",
            "Plan relationship development arc"
        ]
        
        return suggestion