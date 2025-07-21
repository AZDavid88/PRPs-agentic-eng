# PRP: Implement Dynamic Content Injection Commands

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** PRP_NF_HUMAN_CONTROL_EXTENSION_PLANNING.md  
**Target Agent:** Claude Code

---

## 1. The Goal (The "What")

Implement dynamic content injection commands (`add-character`, `inject-context`, `story-steering`) that allow mid-story addition of characters, locations, technologies, and plot elements with AI-assisted integration suggestions using the existing agent and memory systems. **ENHANCED**: Add natural language content injection interface enabling conversational requests like "Add a mysterious character who knows about the ancient magic" with intelligent parsing and Director agent collaboration.

---

## 2. The Context Payload (The "With What")

#### Files to Create/Modify:
- **UPDATE:** `src/cli/commands.py` (add content injection commands)
- **CREATE:** `src/services/smart_integration.py` (AI-assisted integration logic)
- **ENHANCE:** `src/chat/content_injection_chat.py` (conversational content injection interface)
- **EXTEND:** Natural language parsing for intuitive content requests

#### Key Dependencies & Imports:
```python
# Already available in existing codebase:
from src.agents.personas import DirectorAgent, CanonistAgent
from src.memory.qdrant import QdrantService
from src.workflows.jobs import JobStore
from src.ingestion.pipeline import MaterialIngestionPipeline
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import typer
import asyncio
import json
from datetime import datetime

# Enhanced for conversational content injection:
from src.chat.conversation import ConversationSession
from typing import Union, Literal
ContentType = Literal["character", "location", "technology", "magic", "plot", "relationship"]
```

#### Existing Integration Patterns:
```python
# From src/ingestion/pipeline.py - PROVEN ingestion pattern:
pipeline = MaterialIngestionPipeline()
response = await pipeline.ingest_materials([
    MaterialIngestionRequest(
        content=content,
        source_path="dynamic_injection",
        genre=genre,
        additional_genres=additional_genres,
        custom_categories=categories,
        story_id=story_id
    )
])

# From src/agents/personas.py - PROVEN agent usage:
director = DirectorAgent()
analysis = await director.execute(
    prompt="Analyze integration of new element",
    context={"existing_content": existing_content}
)

canonist = CanonistAgent()
continuity_check = await canonist.execute(
    prompt="Check for continuity conflicts",
    context={"new_content": new_content, "existing_story": story_state}
)
```

#### Existing Memory Patterns:
```python
# From validated QdrantService usage:
qdrant = QdrantService()

# Search for existing content
existing_characters = await qdrant.search_by_content(
    query_text="character sheet",
    collection_name="world_bible",
    limit=20
)

# Use metadata filtering (from previous PRP)
story_content = await qdrant.search_with_filters(
    filters={"story_id": story_id, "doc_type": content_type},
    collection_name="world_bible",
    limit=50
)
```

#### Content Structure Examples:
```python
# Character sheet format (from lore_examples/):
character_content = """
Name: Zara Nightwhisper
Role: Former Imperial Spy
Background: Once served the crown, now operates in shadows
Abilities: Information gathering, stealth, network of contacts
Motivation: Protecting her younger brother from magical corruption
Key Relationships:
  - Kael: Initial distrust, eventual alliance based on shared goals
  - Imperial Forces: Former employer, now adversary
Personality: Pragmatic, fiercely loyal to family, slow to trust
"""

# Location format:
location_content = """
Location: The Crystal Caverns
Type: Ancient magical site
Description: Vast underground chambers filled with resonant crystals
History: Pre-empire magical testing ground, now abandoned
Magical Properties: Amplifies resonance magic, dangerous to untrained
Access: Hidden entrance in Echoing Peaks, requires guide
Significance: Contains knowledge needed for final confrontation
"""
```

#### Conversational Content Injection Patterns:
```python
# Natural language content injection examples:
conversational_examples = {
    "character_request": {
        "user_input": "Add a mysterious character who knows about the ancient magic",
        "parsed_content": {
            "type": "character",
            "description": "mysterious character with ancient magic knowledge",
            "role": "sage/mentor",
            "relationship_hints": ["connection to protagonist", "knowledge provider"],
            "story_function": "revelation catalyst"
        },
        "agent_response": "I'll create a mysterious sage character with deep knowledge of ancient magic. Let me analyze how to introduce them naturally into your story..."
    },
    
    "location_request": {
        "user_input": "I need a dangerous place where the characters can be trapped",
        "parsed_content": {
            "type": "location",
            "description": "dangerous trap location",
            "atmosphere": "threatening, claustrophobic",
            "story_function": "tension escalation",
            "mechanics": ["physical danger", "limited escape options"]
        },
        "agent_response": "Perfect! I'll design a perilous location that creates natural tension and forces character development. Let me suggest several dangerous environments..."
    },
    
    "technology_request": {
        "user_input": "The story needs some advanced tech that could change everything",
        "parsed_content": {
            "type": "technology",
            "description": "game-changing advanced technology",
            "impact_level": "high",
            "story_function": "plot catalyst",
            "integration_considerations": ["power balance shift", "character access", "consequences"]
        },
        "agent_response": "Excellent! Game-changing technology can dramatically shift narrative dynamics. I'll analyze how to introduce this tech while maintaining story balance..."
    }
}
```

---

## 3. The Implementation Blueprint (The "How")

### Step 1: Create Smart Integration Service

Create `src/services/smart_integration.py`:

```python
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
```

### Step 2: Create Conversational Content Injection Interface

Add `src/chat/content_injection_chat.py`:

```python
"""
Conversational interface for dynamic content injection.
Enables natural language content requests with intelligent parsing.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from dataclasses import dataclass

from src.agents.personas import DirectorAgent, CanonistAgent
from src.services.smart_integration import SmartIntegrationService
from src.memory.qdrant import QdrantService

@dataclass
class ContentRequest:
    """Structured content request parsed from natural language."""
    content_type: str
    description: str
    story_function: str
    integration_timing: Optional[str] = None
    relationship_hints: List[str] = None
    special_properties: List[str] = None
    impact_level: str = "medium"

class ContentInjectionChatInterface:
    """Conversational interface for dynamic story content injection."""
    
    def __init__(self):
        self.director = DirectorAgent()
        self.canonist = CanonistAgent()
        self.integration_service = SmartIntegrationService()
        self.qdrant = QdrantService()
        self.conversation_context = {}
    
    async def create_injection_session(self, story_id: str, user_id: str = "human") -> str:
        """Start conversational content injection session."""
        
        session_id = f"inject_{story_id}_{int(datetime.now().timestamp())}"
        
        # Get story context for intelligent suggestions
        story_context = await self._get_story_context(story_id)
        
        self.conversation_context[session_id] = {
            "story_id": story_id,
            "user_id": user_id,
            "story_context": story_context,
            "injection_history": [],
            "pending_requests": [],
            "conversation_flow": "greeting"
        }
        
        return session_id
    
    async def process_injection_request(self, session_id: str, user_message: str) -> str:
        """Process natural language content injection request."""
        
        if session_id not in self.conversation_context:
            return "❌ Injection session not found. Please start a new content injection session."
        
        context = self.conversation_context[session_id]
        
        # Parse content request from natural language
        content_request = await self._parse_content_request(user_message, context)
        
        if not content_request:
            return await self._handle_clarification_needed(user_message, context)
        
        # Generate integration analysis and suggestions
        response = await self._handle_content_injection(content_request, context)
        
        # Update conversation history
        context["injection_history"].append({
            "timestamp": datetime.now(),
            "user_message": user_message,
            "content_request": content_request,
            "agent_response": response
        })
        
        return response
    
    async def _parse_content_request(self, message: str, context: Dict[str, Any]) -> Optional[ContentRequest]:
        """Parse natural language into structured content request."""
        
        story_context = context["story_context"]
        
        # Use Director's cognitive engines for intelligent parsing
        parsing_prompt = f"""
        Parse this natural language content injection request:
        
        User Request: "{message}"
        
        Story Context:
        - Existing Characters: {self._format_characters(story_context)}
        - Existing Locations: {self._format_locations(story_context)}
        - Plot Status: {self._format_plot_status(story_context)}
        
        Extract:
        1. Content type (character, location, technology, magic, plot, relationship)
        2. Description and key attributes
        3. Story function (tension, revelation, conflict, support, etc.)
        4. Integration timing hints
        5. Relationship implications
        6. Special properties or capabilities
        7. Impact level (low, medium, high)
        
        If the request is unclear or incomplete, indicate what clarification is needed.
        Return structured analysis.
        """
        
        director_analysis = await self.director.execute(parsing_prompt, context)
        
        # Extract structured content request
        # (Simplified parsing - production would use more sophisticated NLP)
        message_lower = message.lower()
        
        # Determine content type
        content_type = None
        if any(word in message_lower for word in ["character", "person", "someone", "ally", "enemy", "npc"]):
            content_type = "character"
        elif any(word in message_lower for word in ["place", "location", "room", "area", "building", "city"]):
            content_type = "location"
        elif any(word in message_lower for word in ["tech", "technology", "device", "machine", "tool", "gadget"]):
            content_type = "technology"
        elif any(word in message_lower for word in ["magic", "spell", "power", "ability", "enchantment"]):
            content_type = "magic"
        elif any(word in message_lower for word in ["plot", "story", "twist", "event", "happening"]):
            content_type = "plot"
        elif any(word in message_lower for word in ["relationship", "connection", "bond", "alliance", "rivalry"]):
            content_type = "relationship"
        
        if not content_type:
            return None  # Need clarification
        
        # Extract story function
        story_function = "support"  # default
        if any(word in message_lower for word in ["dangerous", "threat", "enemy", "conflict"]):
            story_function = "conflict"
        elif any(word in message_lower for word in ["reveal", "secret", "knowledge", "truth"]):
            story_function = "revelation"
        elif any(word in message_lower for word in ["tension", "drama", "intensity", "pressure"]):
            story_function = "tension"
        elif any(word in message_lower for word in ["help", "aid", "support", "ally"]):
            story_function = "support"
        
        # Extract impact level
        impact_level = "medium"  # default
        if any(word in message_lower for word in ["major", "huge", "game-changing", "everything"]):
            impact_level = "high"
        elif any(word in message_lower for word in ["minor", "small", "subtle", "little"]):
            impact_level = "low"
        
        return ContentRequest(
            content_type=content_type,
            description=message,
            story_function=story_function,
            impact_level=impact_level,
            relationship_hints=[],
            special_properties=[]
        )
    
    async def _handle_content_injection(self, content_request: ContentRequest, context: Dict[str, Any]) -> str:
        """Handle the content injection with AI analysis."""
        
        story_id = context["story_id"]
        
        # Generate detailed content using Director's creative capabilities
        content_generation_prompt = f"""
        Create detailed {content_request.content_type} content based on this request:
        
        Request: {content_request.description}
        Story Function: {content_request.story_function}
        Impact Level: {content_request.impact_level}
        
        Story Context:
        {self._format_full_story_context(context["story_context"])}
        
        Generate:
        1. Detailed description and attributes
        2. Integration approach and timing
        3. Relationship dynamics with existing elements
        4. Potential story complications and opportunities
        5. Specific implementation suggestions
        """
        
        generated_content = await self.director.execute(content_generation_prompt, context)
        
        # Get integration analysis
        if content_request.content_type == "character":
            integration_suggestion = await self.integration_service.suggest_character_integration(
                content_request.description.split()[0],  # Simple name extraction
                content_request.description,
                story_id=story_id
            )
        else:
            integration_suggestion = await self.integration_service.suggest_context_integration(
                content_request.description,
                content_request.content_type,
                story_id=story_id
            )
        
        # Format comprehensive response
        response = f"""✨ **Content Creation Analysis**

**{content_request.content_type.title()} Request:** {content_request.description}

**Generated Content:**
{self._format_generated_content(generated_content, content_request.content_type)}

**Integration Strategy:**
• **Approach:** {integration_suggestion.integration_approach}
• **Story Function:** {content_request.story_function} with {content_request.impact_level} impact
• **Timing:** {integration_suggestion.optimal_introduction_chapter or 'Flexible based on narrative flow'}

**Relationship Dynamics:**
"""
        
        for impact in integration_suggestion.relationship_impacts:
            response += f"• {impact}\n"
        
        response += f"""
**Implementation Recommendations:**
"""
        
        for suggestion in integration_suggestion.suggestions:
            response += f"• {suggestion}\n"
        
        if integration_suggestion.continuity_risks:
            response += f"""
**⚠️ Continuity Considerations:**
"""
            for risk in integration_suggestion.continuity_risks:
                response += f"• {risk}\n"
        
        response += f"""
**Next Steps:**
• Review the generated content and integration approach
• Request modifications if needed ("make this character more mysterious")
• Approve integration to add to story memory
• Generate alternatives for comparison

Would you like me to proceed with integration, modify the approach, or explore alternative versions?"""
        
        # Store pending request for approval
        context["pending_requests"].append({
            "content_request": content_request,
            "generated_content": generated_content,
            "integration_suggestion": integration_suggestion
        })
        
        return response
    
    async def _handle_clarification_needed(self, user_message: str, context: Dict[str, Any]) -> str:
        """Handle cases where the request needs clarification."""
        
        # Use Director to ask intelligent follow-up questions
        clarification_prompt = f"""
        The user made this content request that needs clarification: "{user_message}"
        
        Story Context: {self._format_story_context_summary(context["story_context"])}
        
        Generate helpful follow-up questions to clarify:
        1. What type of content they want (character, location, etc.)
        2. How it should fit into the story
        3. What function it should serve
        4. Any specific attributes or requirements
        
        Be conversational and helpful, offering suggestions based on story context.
        """
        
        clarification_response = await self.director.execute(clarification_prompt, context)
        
        response = f"""🤔 **Let me help clarify your content request!**

I'd like to understand better what you're looking for. Here are some questions to help:

**Content Type:** Are you thinking of adding:
• A new character (ally, enemy, mentor, etc.)?
• A location (safe haven, dangerous area, meeting place)?
• Technology or magical elements?
• A plot development or story event?
• Character relationships or connections?

**Story Function:** How should this content serve your story?
• Create tension or conflict?
• Provide revelations or knowledge?
• Support character development?
• Advance the main plot?

**Integration:** When or how should this appear?
• Immediately in current chapter?
• Background presence that becomes important later?
• Dramatic introduction at crucial moment?

Based on your story context, I can suggest some specific options that might work well. What type of content interests you most?"""
        
        return response
    
    async def _get_story_context(self, story_id: str) -> Dict[str, Any]:
        """Get comprehensive story context for content suggestions."""
        
        if not story_id:
            return {"characters": [], "locations": [], "plot_threads": []}
        
        try:
            characters = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "character_sheet"},
                collection_name="world_bible",
                limit=10
            )
            
            locations = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "location"},
                collection_name="world_bible",
                limit=8
            )
            
            plot_threads = await self.qdrant.search_with_filters(
                filters={"story_id": story_id, "doc_type": "plot_thread"},
                collection_name="world_bible",
                limit=5
            )
            
            return {
                "characters": characters,
                "locations": locations,
                "plot_threads": plot_threads
            }
            
        except Exception:
            return {"characters": [], "locations": [], "plot_threads": []}
    
    def _format_characters(self, story_context: Dict[str, Any]) -> str:
        """Format character context for prompt consumption."""
        if not story_context.get("characters"):
            return "No existing characters found"
        
        char_list = []
        for char in story_context["characters"][:5]:
            char_list.append(char.get("content", "")[:100] + "...")
        return "; ".join(char_list)
    
    def _format_locations(self, story_context: Dict[str, Any]) -> str:
        """Format location context for prompt consumption."""
        if not story_context.get("locations"):
            return "No existing locations found"
        
        loc_list = []
        for loc in story_context["locations"][:4]:
            loc_list.append(loc.get("content", "")[:80] + "...")
        return "; ".join(loc_list)
    
    def _format_plot_status(self, story_context: Dict[str, Any]) -> str:
        """Format plot context for prompt consumption."""
        if not story_context.get("plot_threads"):
            return "No plot threads tracked"
        
        plot_list = []
        for plot in story_context["plot_threads"][:3]:
            plot_list.append(plot.get("content", "")[:60] + "...")
        return "; ".join(plot_list)
    
    def _format_full_story_context(self, story_context: Dict[str, Any]) -> str:
        """Format complete story context for detailed analysis."""
        return f"""
Characters: {self._format_characters(story_context)}

Locations: {self._format_locations(story_context)}

Plot Threads: {self._format_plot_status(story_context)}
"""
    
    def _format_story_context_summary(self, story_context: Dict[str, Any]) -> str:
        """Brief story context summary."""
        char_count = len(story_context.get("characters", []))
        loc_count = len(story_context.get("locations", []))
        plot_count = len(story_context.get("plot_threads", []))
        
        return f"{char_count} characters, {loc_count} locations, {plot_count} plot threads"
    
    def _format_generated_content(self, content: str, content_type: str) -> str:
        """Format generated content based on type."""
        # In practice, would parse and format the Director's generated content
        return f"**{content_type.title()} Details:** {content[:300]}..."
```

### Step 3: Add Conversational Interface CLI Command

Add this command to `src/cli/commands.py`:

```python
@app.command(name="inject-chat")
def inject_chat(
    story_id: str = typer.Option(None, "--story-id", help="Story context for content injection"),
    session_name: str = typer.Option("default", "--session", help="Chat session name")
):
    """
    Start conversational content injection session.
    
    Examples:
        factory inject-chat --story-id "my_serial"
        factory inject-chat --session "character_planning"
    """
    try:
        console.print("🤖 Starting conversational content injection session...")
        console.print(f"📖 Story context: {story_id or 'general'}")
        console.print(f"💬 Session: {session_name}")
        
        # Run conversational session
        asyncio.run(_run_conversational_injection(story_id, session_name))
        
    except Exception as e:
        console.print(f"❌ Conversational injection failed: {e}", style="bold red")
        raise typer.Exit(1)

async def _run_conversational_injection(story_id: Optional[str], session_name: str):
    """Run conversational content injection session."""
    from src.chat.content_injection_chat import ContentInjectionChatInterface
    
    console.print("🎯 Conversational Content Injection")
    console.print("Type natural language requests like:")
    console.print("  • 'Add a mysterious character who knows about the ancient magic'")
    console.print("  • 'I need a dangerous place where characters can be trapped'")
    console.print("  • 'The story needs some advanced tech that could change everything'")
    console.print("  • Type 'quit' to exit")
    console.print()
    
    # Create chat session
    chat_interface = ContentInjectionChatInterface()
    session_id = await chat_interface.create_injection_session(story_id or "general", "cli_user")
    
    console.print(f"✅ Started session: {session_id}")
    console.print("🗣️ What content would you like to add to your story?")
    
    while True:
        # Get user input
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
            
            if user_input.lower() in ['quit', 'exit', 'done']:
                console.print("👋 Ending conversational injection session")
                break
            
            # Process request
            console.print("🤔 [italic]Analyzing request...[/italic]")
            response = await chat_interface.process_injection_request(session_id, user_input)
            
            # Display response
            console.print(f"\n[bold cyan]Director[/bold cyan]: {response}")
            
        except KeyboardInterrupt:
            console.print("\n👋 Session interrupted. Goodbye!")
            break
        except Exception as e:
            console.print(f"❌ Error processing request: {e}", style="bold red")
```

### Step 4: Add Dynamic Content Injection Commands

Add these commands to `src/cli/commands.py`:

```python
# === DYNAMIC CONTENT INJECTION COMMANDS ===

@app.command(name="add-character")
def add_character(
    name: str = typer.Argument(..., help="Character name"),
    description: str = typer.Option(..., "--description", help="Character description and background"),
    chapter: int = typer.Option(None, "--at-chapter", help="Target introduction chapter"),
    role: str = typer.Option("supporting", "--role", help="Character role: protagonist, antagonist, supporting"),
    story_id: str = typer.Option(None, "--story-id", help="Story to integrate with")
):
    """
    Add new character with AI-assisted integration analysis.
    
    Examples:
        factory add-character "Zara" --description "Former spy turned ally" --at-chapter 45
        factory add-character "Marcus" --role "antagonist" --description "Corrupt imperial commander"
        factory add-character "Elena" --description "Healer with secret knowledge" --story-id "my_serial"
    """
    try:
        console.print(f"🧙 Adding character: [bold magenta]{name}[/bold magenta]")
        console.print(f"📋 Description: [italic]{description}[/italic]")
        
        if chapter:
            console.print(f"📍 Target introduction: Chapter {chapter}")
        if story_id:
            console.print(f"📖 Story context: {story_id}")
        
        # Run integration analysis
        asyncio.run(_run_character_integration(name, description, chapter, role, story_id))
        
    except Exception as e:
        console.print(f"❌ Character addition failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="inject-context")
def inject_context(
    content: str = typer.Argument(..., help="Context content to inject"),
    context_type: str = typer.Option("general", "--type", help="Type: character, location, tech, magic, plot"),
    chapter: int = typer.Option(None, "--from-chapter", help="Chapter to introduce from"),
    story_id: str = typer.Option(None, "--story-id", help="Story to update"),
    auto_integrate: bool = typer.Option(False, "--auto", help="Auto-integrate without confirmation")
):
    """
    Inject new context with AI-assisted integration analysis.
    
    Examples:
        factory inject-context "Neural implants are common in the eastern districts" --type "tech" --from-chapter 50
        factory inject-context "The Crystal Caverns hold ancient secrets" --type "location"  
        factory inject-context "Magic corruption spreads through bloodlines" --type "magic" --story-id "my_serial"
    """
    try:
        console.print(f"💫 Injecting {context_type} context:")
        console.print(Panel(content, title="New Context", border_style="blue"))
        
        if chapter:
            console.print(f"📍 From chapter: {chapter}")
        if story_id:
            console.print(f"📖 Story context: {story_id}")
        
        # Run context integration analysis
        asyncio.run(_run_context_integration(content, context_type, chapter, story_id, auto_integrate))
        
    except Exception as e:
        console.print(f"❌ Context injection failed: {e}", style="bold red")
        raise typer.Exit(1)

@app.command(name="story-steering")
def story_steering(
    direction: str = typer.Argument(..., help="Story direction or theme to introduce"),
    intensity: str = typer.Option("medium", "--intensity", help="Intensity: subtle, medium, major"),
    from_chapter: int = typer.Option(None, "--from-chapter", help="Chapter to begin steering"),
    story_id: str = typer.Option(None, "--story-id", help="Story to steer")
):
    """
    Guide story direction with AI analysis of narrative impact.
    
    Examples:
        factory story-steering "Add more romantic tension" --intensity "subtle"
        factory story-steering "Introduce cyberpunk elements" --intensity "major" --from-chapter 50
        factory story-steering "Increase political intrigue" --from-chapter 30
    """
    try:
        console.print(f"🎭 Steering story direction: [bold yellow]{direction}[/bold yellow]")
        console.print(f"⚡ Intensity: [bold cyan]{intensity}[/bold cyan]")
        
        if from_chapter:
            console.print(f"📍 Starting from chapter: {from_chapter}")
        
        # Run story steering analysis
        asyncio.run(_run_story_steering(direction, intensity, from_chapter, story_id))
        
    except Exception as e:
        console.print(f"❌ Story steering failed: {e}", style="bold red")
        raise typer.Exit(1)

# === IMPLEMENTATION FUNCTIONS ===

async def _run_character_integration(name: str, description: str, chapter: Optional[int], role: str, story_id: Optional[str]):
    """Implementation for character integration."""
    from src.services.smart_integration import SmartIntegrationService
    
    console.print("🔍 Analyzing character integration...")
    
    # Get AI-assisted integration analysis
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_character_integration(
        name, description, chapter, story_id
    )
    
    # Display analysis results
    console.print("\n🤖 AI Integration Analysis:")
    
    if suggestion.optimal_introduction_chapter:
        console.print(f"📍 Optimal introduction: Chapter {suggestion.optimal_introduction_chapter}")
    
    console.print(f"🎯 Integration approach: {suggestion.integration_approach}")
    
    if suggestion.relationship_impacts:
        console.print("\n👥 Relationship impacts:")
        for impact in suggestion.relationship_impacts:
            console.print(f"  • {impact}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Plot considerations:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.continuity_risks:
        console.print("\n⚠️ Continuity risks:")
        for risk in suggestion.continuity_risks:
            console.print(f"  • {risk}", style="yellow")
    
    if suggestion.suggestions:
        console.print("\n💡 AI suggestions:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    # Confirm integration
    if Confirm.ask("\n🚀 Proceed with character integration?"):
        # Create character sheet content
        character_content = f"""
Name: {name}
Role: {role}
Description: {description}
Introduction Context: {suggestion.integration_approach}
Planned Chapter: {chapter or suggestion.optimal_introduction_chapter or 'TBD'}
AI Analysis: {', '.join(suggestion.suggestions)}
"""
        
        # Execute integration using existing pipeline
        success = await integration_service.execute_integration(
            character_content,
            "character_sheet",
            story_id,
            {"character_name": name, "role": role, "integration_analysis": suggestion.suggestions}
        )
        
        if success:
            console.print("✅ Character integrated successfully!", style="bold green")
            console.print(f"💡 Use [bold cyan]factory memory-list --search \"{name}\"[/bold cyan] to verify")
        else:
            console.print("❌ Character integration failed", style="bold red")
    else:
        console.print("👋 Character integration cancelled")

async def _run_context_integration(content: str, context_type: str, chapter: Optional[int], story_id: Optional[str], auto_integrate: bool):
    """Implementation for context injection."""
    from src.services.smart_integration import SmartIntegrationService
    
    console.print("🔍 Analyzing context integration...")
    
    # Get AI analysis
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_context_integration(
        content, context_type, chapter, story_id
    )
    
    # Display analysis
    console.print(f"\n🤖 AI Analysis for {context_type} integration:")
    console.print(f"🎯 Approach: {suggestion.integration_approach}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Plot impact:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.continuity_risks:
        console.print("\n⚠️ Continuity considerations:")
        for risk in suggestion.continuity_risks:
            console.print(f"  • {risk}", style="yellow")
    
    if suggestion.suggestions:
        console.print("\n💡 AI recommendations:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    # Confirm integration
    proceed = auto_integrate or Confirm.ask("\n🚀 Proceed with context integration?")
    
    if proceed:
        # Format content with metadata
        formatted_content = f"""
Type: {context_type}
Content: {content}
Introduction: Chapter {chapter or 'TBD'}
Integration Notes: {suggestion.integration_approach}
AI Recommendations: {', '.join(suggestion.suggestions)}
"""
        
        # Execute integration
        success = await integration_service.execute_integration(
            formatted_content,
            context_type,
            story_id,
            {"context_type": context_type, "introduction_chapter": chapter}
        )
        
        if success:
            console.print("✅ Context integrated successfully!", style="bold green")
            console.print(f"💡 Use [bold cyan]factory memory-list --type \"{context_type}\"[/bold cyan] to verify")
        else:
            console.print("❌ Context integration failed", style="bold red")
    else:
        console.print("👋 Context integration cancelled")

async def _run_story_steering(direction: str, intensity: str, from_chapter: Optional[int], story_id: Optional[str]):
    """Implementation for story steering."""
    from src.services.smart_integration import SmartIntegrationService
    
    console.print("🔍 Analyzing story steering impact...")
    
    # Analyze steering direction as context injection
    integration_service = SmartIntegrationService()
    suggestion = await integration_service.suggest_context_integration(
        f"Story direction: {direction} (intensity: {intensity})",
        "plot_direction",
        from_chapter,
        story_id
    )
    
    # Display steering analysis
    console.print(f"\n🎭 Story Steering Analysis:")
    console.print(f"🎯 Implementation approach: {suggestion.integration_approach}")
    
    if suggestion.plot_considerations:
        console.print("\n📚 Narrative impact:")
        for consideration in suggestion.plot_considerations:
            console.print(f"  • {consideration}")
    
    if suggestion.suggestions:
        console.print("\n💡 Steering recommendations:")
        for sug in suggestion.suggestions:
            console.print(f"  • {sug}", style="green")
    
    console.print(f"\n📝 Next steps:")
    console.print(f"  1. Use [bold cyan]factory inject-context[/bold cyan] to add specific story elements")
    console.print(f"  2. Use [bold cyan]factory add-character[/bold cyan] to introduce characters supporting this direction")
    console.print(f"  3. Monitor agent outputs for natural incorporation of steering guidance")
```

---

## 4. Validation Gate (The "Contract")

The implementation is complete when ALL of these commands pass:

### Level 1: Syntax & Import Validation
```bash
cd /workspaces/PRPs-agentic-eng/projects/narrative_factory
uv run python -c "from src.cli.commands import add_character, inject_context, story_steering; print('✅ Injection commands imported')"
uv run python -c "from src.services.smart_integration import SmartIntegrationService; print('✅ Smart integration service loads')"
```

### Level 2: CLI Command Registration
```bash
uv run factory --help | grep -E "(add-character|inject-context|story-steering)"
# Must show all three commands in help output

# Test conversational interface command
uv run factory --help | grep "inject-chat"
# Must show new conversational injection command
```

### Level 3: Character Addition Workflow
```bash
# Test character addition with AI analysis
uv run factory add-character "Zara" --description "Former spy turned ally" --at-chapter 45 --story-id "test_story"
# Must show AI integration analysis and offer to proceed
```

### Level 4: Context Injection
```bash
# Test context injection
uv run factory inject-context "Neural implants are common in eastern districts" --type "tech" --from-chapter 50
# Must show AI analysis of integration impact

# Test location injection
uv run factory inject-context "The Crystal Caverns hold ancient secrets" --type "location"
# Must provide location-specific integration analysis
```

### Level 5: Story Steering Analysis
```bash
# Test story steering guidance
uv run factory story-steering "Add more romantic tension" --intensity "subtle"
# Must provide narrative impact analysis and next step recommendations
```

### Level 5.5: Conversational Content Injection
```bash
# Test natural language content injection
uv run factory inject-chat --story-id "test_story"
# Should start conversational session, then test with natural language like:
# "Add a mysterious character who knows about the ancient magic"
# "I need a dangerous place where characters can be trapped"
# Must parse intent and provide AI analysis
```

### Level 6: Integration with Memory System
```bash
# After successful integration, verify content appears in memory
uv run factory memory-list --search "Zara"
# Should show the integrated character

uv run factory memory-list --type "tech" --search "neural"
# Should show integrated technology context
```

### Level 7: Agent System Integration
```bash
# Verify that injected content is available for agent retrieval
uv run factory generate "Test chapter with new character Zara"
# Agent should have access to injected character information
```

---

## 5. Integration Notes

#### AI-Assisted Integration:
- Uses existing DirectorAgent for strategic analysis of how new elements fit story
- Uses existing CanonistAgent for continuity validation and conflict detection
- Provides structured suggestions rather than requiring manual integration planning
- Offers specific recommendations for introduction timing and relationship development

#### Conversational Enhancement:
- Natural language parsing enables intuitive content requests
- Director's cognitive engines understand story context and user intent
- Intelligent follow-up questions guide users toward clear content specifications
- Real-time feedback and iteration without complex command syntax

#### Content Pipeline Integration:
- Uses existing MaterialIngestionPipeline for content storage
- Follows existing metadata and categorization patterns
- Integrates with existing memory search and retrieval systems
- Maintains compatibility with existing agent context retrieval

#### Workflow Enhancement:
- Character addition provides relationship impact analysis
- Context injection considers plot advancement and world-building consistency
- Story steering provides actionable next steps for implementing direction changes
- All commands offer confirmation before making changes

#### Testing with Existing Content:
- Use existing `lore_examples/` content as baseline for integration testing
- Test character integration against existing characters (Kael, Selene)
- Test location integration with existing locations (Echoing Peaks)
- Verify that new content enhances rather than conflicts with established lore

This implementation provides sophisticated mid-story content injection while leveraging the proven agent analysis and memory systems.