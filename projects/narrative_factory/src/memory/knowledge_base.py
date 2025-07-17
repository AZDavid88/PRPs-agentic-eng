"""
Knowledge base service for the Narrative Factory.

Provides comprehensive knowledge retrieval, character profile management,
and lore searching capabilities with two-tier retrieval system.
"""

import asyncio
from typing import Any, Dict, List, Optional

from src.agents.models import ContextRetrievalResult
from src.exceptions import BusinessLogicError
from src.logger import get_logger
from src.memory.service import MemoryService, get_memory_service

logger = get_logger(__name__)


class KnowledgeBaseService:
    """
    Advanced knowledge base service with two-tier retrieval system.
    
    Provides:
    - Spotlight Query: High-relevance context filtered by active elements
    - Ambient Echo: Background information and unresolved tensions
    - Character profile management
    - Lore searching and context assembly
    """

    def __init__(self, memory_service: Optional[MemoryService] = None):
        """
        Initialize the knowledge base service.
        
        Args:
            memory_service: Optional memory service instance
        """
        self.memory_service = memory_service or get_memory_service()
        self.qdrant_service = self.memory_service.qdrant_service

        # Cache for frequently accessed data
        self._character_cache: Dict[str, Dict[str, Any]] = {}
        self._lore_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_ttl = 300  # 5 minutes

        logger.info("Knowledge base service initialized")

    async def get_character_profile(self, character_id: str) -> Dict[str, Any]:
        """
        Get comprehensive character profile from knowledge base.
        
        Args:
            character_id: Character identifier
            
        Returns:
            Character profile dictionary
        """
        try:
            # Check cache first
            if character_id in self._character_cache:
                logger.debug(f"Retrieved cached character profile: {character_id}")
                return self._character_cache[character_id]

            # Search for character in world bible
            character_results = await self.qdrant_service.search_by_content(
                query_text=f"character profile {character_id}",
                collection_name="world_bible",
                limit=5
            )

            # Compile character profile
            character_profile = {
                "character_id": character_id,
                "name": character_id.title(),
                "description": "",
                "personality": [],
                "background": [],
                "relationships": [],
                "skills": [],
                "current_status": "active",
                "source_documents": []
            }

            # Process search results
            for result in character_results:
                doc_type = result.get("doc_type", "")
                content = result.get("content", "")

                if doc_type == "character_sheet":
                    character_profile["description"] = content
                elif doc_type == "character_background":
                    character_profile["background"].append(content)
                elif doc_type == "character_personality":
                    character_profile["personality"].append(content)
                elif doc_type == "character_relationships":
                    character_profile["relationships"].append(content)
                elif doc_type == "character_skills":
                    character_profile["skills"].append(content)

                character_profile["source_documents"].append({
                    "id": result.get("id"),
                    "type": doc_type,
                    "score": result.get("score", 0.0)
                })

            # Cache the result
            self._character_cache[character_id] = character_profile

            logger.info(f"Retrieved character profile for {character_id}")
            return character_profile

        except Exception as e:
            logger.error(f"Failed to get character profile for {character_id}: {e}")
            raise BusinessLogicError(f"Failed to get character profile: {e}") from e

    async def search_lore(self, topic: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for lore related to a specific topic.
        
        Args:
            topic: Topic to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of lore entries
        """
        try:
            # Check cache first
            cache_key = f"{topic}_{max_results}"
            if cache_key in self._lore_cache:
                logger.debug(f"Retrieved cached lore search: {topic}")
                return self._lore_cache[cache_key]

            # Search world bible for lore
            lore_results = await self.qdrant_service.search_by_content(
                query_text=f"lore {topic}",
                collection_name="world_bible",
                limit=max_results
            )

            # Process and format results
            lore_entries = []
            for result in lore_results:
                lore_entry = {
                    "id": result.get("id"),
                    "topic": topic,
                    "content": result.get("content", ""),
                    "doc_type": result.get("doc_type", "lore"),
                    "relevance_score": result.get("score", 0.0),
                    "tags": result.get("tags", []),
                    "category": result.get("category", "general"),
                    "last_updated": result.get("last_updated")
                }
                lore_entries.append(lore_entry)

            # Cache the result
            self._lore_cache[cache_key] = lore_entries

            logger.info(f"Retrieved {len(lore_entries)} lore entries for topic: {topic}")
            return lore_entries

        except Exception as e:
            logger.error(f"Failed to search lore for topic {topic}: {e}")
            raise BusinessLogicError(f"Failed to search lore: {e}") from e

    async def get_enhanced_context_for_director(
        self,
        chapter_seed: str,
        active_characters: List[str],
        story_context: Optional[Dict[str, Any]] = None,
        max_results_per_tier: int = 5
    ) -> ContextRetrievalResult:
        """
        Enhanced two-tier context retrieval for Director agent with character profiles.
        
        Args:
            chapter_seed: Narrative seed for context
            active_characters: List of active character IDs
            story_context: Optional story context information
            max_results_per_tier: Maximum results per tier
            
        Returns:
            Enhanced context retrieval result
        """
        try:
            # Get base context from QdrantService
            base_context = await self.qdrant_service.fetch_context_for_director(
                chapter_seed=chapter_seed,
                active_characters=active_characters,
                max_results_per_tier=max_results_per_tier
            )

            # Enhance with character profiles
            enhanced_spotlight = []
            for item in base_context.spotlight_context:
                enhanced_item = dict(item)

                # Add character profile information
                if "character_name" in item:
                    character_profile = await self.get_character_profile(item["character_name"])
                    enhanced_item["character_profile"] = character_profile

                enhanced_spotlight.append(enhanced_item)

            # Enhance ambient echo with lore context
            enhanced_ambient = []
            for item in base_context.ambient_echo:
                enhanced_item = dict(item)

                # Extract topics from content for lore enhancement
                content = item.get("content", "")
                if len(content) > 50:  # Only enhance substantial content
                    # Simple topic extraction - can be enhanced with NLP
                    topic_keywords = ["conflict", "tension", "mystery", "prophecy", "ancient"]
                    for keyword in topic_keywords:
                        if keyword in content.lower():
                            try:
                                related_lore = await self.search_lore(keyword, max_results=2)
                                if related_lore:
                                    enhanced_item["related_lore"] = related_lore
                                    break
                            except Exception as e:
                                logger.warning(f"Failed to get related lore for {keyword}: {e}")

                enhanced_ambient.append(enhanced_item)

            # Add story context if provided
            if story_context:
                enhanced_spotlight.append({
                    "content": f"Current story context: {story_context}",
                    "doc_type": "story_context",
                    "score": 1.0,
                    "id": "story_context_current"
                })

            enhanced_result = ContextRetrievalResult(
                spotlight_context=enhanced_spotlight,
                ambient_echo=enhanced_ambient
            )

            logger.info(f"Enhanced context retrieval completed: {len(enhanced_spotlight)} spotlight, {len(enhanced_ambient)} ambient")
            return enhanced_result

        except Exception as e:
            logger.error(f"Failed to get enhanced context for director: {e}")
            raise BusinessLogicError(f"Failed to get enhanced context: {e}") from e

    async def get_prose_style_guide(self) -> Dict[str, Any]:
        """
        Get the prose style guide from the knowledge base.
        
        Returns:
            Prose style guide dictionary
        """
        try:
            # Search for style guide documents
            style_results = await self.qdrant_service.search_by_content(
                query_text="prose style guide writing guidelines",
                collection_name="world_bible",
                limit=5
            )

            style_guide = {
                "general_guidelines": [],
                "voice_and_tone": [],
                "formatting_rules": [],
                "character_voice": [],
                "dialogue_style": [],
                "narrative_perspective": "third_person",
                "tense": "present",
                "source_documents": []
            }

            # Process style guide results
            for result in style_results:
                doc_type = result.get("doc_type", "")
                content = result.get("content", "")

                if "style" in doc_type or "guide" in doc_type:
                    if "voice" in content.lower() or "tone" in content.lower():
                        style_guide["voice_and_tone"].append(content)
                    elif "dialogue" in content.lower():
                        style_guide["dialogue_style"].append(content)
                    elif "format" in content.lower():
                        style_guide["formatting_rules"].append(content)
                    else:
                        style_guide["general_guidelines"].append(content)

                style_guide["source_documents"].append({
                    "id": result.get("id"),
                    "type": doc_type,
                    "score": result.get("score", 0.0)
                })

            # Add default guidelines if none found
            if not style_guide["general_guidelines"]:
                style_guide["general_guidelines"].append(
                    "Write in vivid, engaging prose with strong character voice and emotional depth."
                )

            logger.info("Retrieved prose style guide")
            return style_guide

        except Exception as e:
            logger.error(f"Failed to get prose style guide: {e}")
            raise BusinessLogicError(f"Failed to get prose style guide: {e}") from e

    async def get_world_state_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of the current world state.
        
        Returns:
            World state summary dictionary
        """
        try:
            # Search for world state documents
            world_results = await self.qdrant_service.search_by_content(
                query_text="world state current events politics geography",
                collection_name="world_bible",
                limit=10
            )

            world_state = {
                "political_situation": [],
                "geographical_features": [],
                "current_events": [],
                "economic_status": [],
                "cultural_aspects": [],
                "magical_systems": [],
                "technology_level": [],
                "active_conflicts": [],
                "recent_changes": [],
                "source_documents": []
            }

            # Process world state results
            for result in world_results:
                doc_type = result.get("doc_type", "")
                content = result.get("content", "")

                if "political" in doc_type or "politics" in content.lower():
                    world_state["political_situation"].append(content)
                elif "geography" in doc_type or "location" in doc_type:
                    world_state["geographical_features"].append(content)
                elif "event" in doc_type or "current" in doc_type:
                    world_state["current_events"].append(content)
                elif "economic" in doc_type or "economy" in content.lower():
                    world_state["economic_status"].append(content)
                elif "culture" in doc_type or "cultural" in content.lower():
                    world_state["cultural_aspects"].append(content)
                elif "magic" in doc_type or "magical" in content.lower():
                    world_state["magical_systems"].append(content)
                elif "technology" in doc_type or "tech" in content.lower():
                    world_state["technology_level"].append(content)
                elif "conflict" in doc_type or "tension" in doc_type:
                    world_state["active_conflicts"].append(content)
                else:
                    world_state["recent_changes"].append(content)

                world_state["source_documents"].append({
                    "id": result.get("id"),
                    "type": doc_type,
                    "score": result.get("score", 0.0)
                })

            logger.info("Retrieved world state summary")
            return world_state

        except Exception as e:
            logger.error(f"Failed to get world state summary: {e}")
            raise BusinessLogicError(f"Failed to get world state summary: {e}") from e

    async def store_narrative_memory(
        self,
        content: str,
        doc_type: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Store narrative memory in the knowledge base.
        
        Args:
            content: Content to store
            doc_type: Type of document
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        try:
            # Generate unique document ID (use UUID for Qdrant compatibility)
            import uuid
            doc_id = str(uuid.uuid4())

            # Prepare document for ingestion
            doc_metadata = {
                "doc_type": doc_type,
                "timestamp": asyncio.get_event_loop().time(),
                **metadata
            }

            # Store in appropriate collection
            collection_name = "story_so_far" if doc_type in ["chapter", "scene", "event"] else "world_bible"

            await self.qdrant_service.ingest_document(
                doc_id=doc_id,
                content=content,
                collection_name=collection_name,
                metadata=doc_metadata
            )

            logger.info(f"Stored narrative memory: {doc_id}")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to store narrative memory: {e}")
            raise BusinessLogicError(f"Failed to store narrative memory: {e}") from e

    async def clear_cache(self) -> None:
        """Clear all cached data."""
        self._character_cache.clear()
        self._lore_cache.clear()
        logger.info("Knowledge base cache cleared")

    async def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics."""
        return {
            "cached_characters": len(self._character_cache),
            "cached_lore_searches": len(self._lore_cache),
            "cache_ttl": self._cache_ttl,
            "memory_service_stats": self.memory_service.qdrant_service.get_service_stats()
        }

    async def close(self) -> None:
        """Close the knowledge base service."""
        await self.clear_cache()
        await self.memory_service.close()
        logger.info("Knowledge base service closed")


# Global knowledge base service instance
_knowledge_base_service: Optional[KnowledgeBaseService] = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Get the global knowledge base service instance."""
    global _knowledge_base_service
    if _knowledge_base_service is None:
        _knowledge_base_service = KnowledgeBaseService()
    return _knowledge_base_service


async def initialize_knowledge_base_service(memory_service: Optional[MemoryService] = None) -> KnowledgeBaseService:
    """Initialize the global knowledge base service."""
    global _knowledge_base_service
    _knowledge_base_service = KnowledgeBaseService(memory_service)
    return _knowledge_base_service


logger.info("Knowledge base service module initialized")
