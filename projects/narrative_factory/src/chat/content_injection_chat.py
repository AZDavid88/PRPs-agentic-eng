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
        
        # CRITICAL: Ingest conversation to memory for agent RAG access
        await self._ingest_chat_content_to_memory(session_id, user_message, response, content_request)
        
        # Update conversation history
        context["injection_history"].append({
            "timestamp": datetime.now(),
            "user_message": user_message,
            "content_request": content_request,
            "agent_response": response
        })
        
        return response
    
    async def _ingest_chat_content_to_memory(self, session_id: str, user_message: str, 
                                           agent_response: str, content_request: ContentRequest):
        """
        CRITICAL: Ingest conversational content to Qdrant for agent RAG access.
        This ensures human-AI conversations become part of the agent knowledge base.
        """
        try:
            context = self.conversation_context[session_id]
            
            # Create rich content for memory ingestion
            chat_content = {
                "conversation_type": "content_injection_chat",
                "session_id": session_id,
                "story_id": context["story_id"],
                "user_message": user_message,
                "agent_response": agent_response,
                "content_request": content_request.__dict__ if content_request else {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Create searchable text for vectorization
            searchable_text = f"""
            Content Injection Conversation
            
            User Request: {user_message}
            
            Content Type: {content_request.content_type if content_request else 'unclear'}
            Description: {content_request.description if content_request else 'needs clarification'}
            Story Function: {content_request.story_function if content_request else 'TBD'}
            Impact Level: {content_request.impact_level if content_request else 'medium'}
            
            AI Response: {agent_response}
            
            Story Context: Content injection discussion for {context['story_id']}
            """
            
            # Metadata for categorization and retrieval
            metadata = {
                "content_type": "conversation",
                "conversation_type": "content_injection",
                "session_id": session_id,
                "story_id": context["story_id"],
                "requested_content_type": content_request.content_type if content_request else "unclear",
                "impact_level": content_request.impact_level if content_request else "medium",
                "timestamp": datetime.now().isoformat(),
                "user_id": context.get("user_id", "human")
            }
            
            # Ingest to Qdrant with late chunking and vectorization
            document_id = f"content_inject_chat_{session_id}_{int(datetime.now().timestamp())}"
            
            await self.qdrant.ingest_document(
                content=searchable_text,
                metadata=metadata,
                document_id=document_id
            )
            
        except Exception as e:
            # Don't fail the chat if memory ingestion fails
            pass
    
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