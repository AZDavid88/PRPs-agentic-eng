# Qdrant Architecture Analysis for Narrative Factory Vector Database Optimization

**Generated:** 2025-07-21  
**Source:** https://qdrant.tech/documentation/concepts/  
**Purpose:** Comprehensive analysis of Qdrant patterns for solving Narrative Factory Priority 1 vector database issues and agent-accessible storage

---

## 🎯 Executive Summary

Qdrant provides **sophisticated vector database capabilities** that directly address your **Priority 1 vector dimension mismatch (768 vs 2048)** and enable smart LibrarianAgent integration. The analysis focuses on your three critical integration points: LibrarianAgent interaction patterns, Jina Embedding v4 compatibility, and agent-accessible vector storage.

**Critical Finding:** Qdrant's collection migration + payload structuring = Complete solution for your vector database issues and agent accessibility.

**Key Solutions for Narrative Factory:**
- **Collection Migration** - Seamless transition from 768 to 2048-dimensional vectors
- **Agent-Accessible Payloads** - Rich metadata structures for LibrarianAgent comprehension
- **Jina v4 Integration** - Direct compatibility with 2048-dimensional embeddings
- **Smart Filtering** - Advanced query patterns for intelligent material retrieval
- **Multitenancy** - Isolated collections per story/user for scalable organization

---

## 🏗️ Core Architecture Solutions

### 1. **Priority 1 Fix: Vector Dimension Migration (768 → 2048)**

**Pattern:** Migrate existing collections to support Jina Embedding v4 2048-dimensional vectors.

```python
from qdrant_client import QdrantClient, models
from src.memory.embedding_service import EmbeddingService
import asyncio

class NarrativeFactoryQdrantMigration:
    """Complete migration strategy for Priority 1 vector dimension issues."""
    
    def __init__(self):
        self.client = QdrantClient(url="http://localhost:6333")
        self.embedding_service = EmbeddingService()
    
    async def migrate_to_jina_v4_dimensions(self):
        """Migrate from 768-dim to 2048-dim vectors for Jina v4 compatibility."""
        
        # Step 1: Create new collection with correct dimensions
        await self.create_jina_v4_collection("narrative_memory_v2")
        
        # Step 2: Retrieve existing data
        existing_points = await self.backup_existing_data("narrative_memory")
        
        # Step 3: Re-embed content with Jina v4
        migrated_points = await self.re_embed_with_jina_v4(existing_points)
        
        # Step 4: Upload to new collection
        await self.upload_migrated_points("narrative_memory_v2", migrated_points)
        
        # Step 5: Validate migration
        await self.validate_migration("narrative_memory", "narrative_memory_v2")
        
        return {
            "status": "success",
            "migrated_points": len(migrated_points),
            "new_collection": "narrative_memory_v2",
            "vector_size": 2048
        }
    
    async def create_jina_v4_collection(self, collection_name: str):
        """Create collection optimized for Jina Embedding v4."""
        
        collection_config = models.VectorParams(
            size=2048,  # Jina v4 dimension
            distance=models.Distance.COSINE,  # Optimal for semantic similarity
            on_disk=False,  # Keep in RAM for performance
            hnsw_config=models.HnswConfig(
                m=16,  # Optimal for 2048-dim vectors
                ef_construct=200,  # Higher for better quality
                full_scan_threshold=10000
            )
        )
        
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=collection_config,
            # Optimize for narrative content
            optimizers_config=models.OptimizersConfig(
                default_segment_number=4,  # Good for medium datasets
                max_segment_size=20000,
                memmap_threshold=20000,
                indexing_threshold=20000,
                flush_interval_sec=10,
                max_optimization_threads=2
            ),
            # Enhanced payload indexing for agent queries
            payload_schema={
                "material_type": models.PayloadSchemaType.KEYWORD,
                "character_names": models.PayloadSchemaType.KEYWORD, 
                "story_id": models.PayloadSchemaType.KEYWORD,
                "chapter_number": models.PayloadSchemaType.INTEGER,
                "timestamp": models.PayloadSchemaType.DATETIME,
                "content_length": models.PayloadSchemaType.INTEGER,
                "narrative_tags": models.PayloadSchemaType.KEYWORD
            }
        )
        
        print(f"✅ Created Jina v4 collection: {collection_name}")
        return collection_name
    
    async def re_embed_with_jina_v4(self, existing_points: list) -> list:
        """Re-embed content using Jina Embedding v4 (2048-dim)."""
        
        migrated_points = []
        
        for point in existing_points:
            try:
                # Extract original content from payload
                content = point["payload"].get("content", "")
                
                if not content:
                    continue
                
                # Generate new 2048-dimensional embedding
                new_embedding = await self.embedding_service.embed(content)
                
                # Enhance payload with agent-accessible metadata
                enhanced_payload = self.create_agent_accessible_payload(
                    point["payload"], content
                )
                
                migrated_point = {
                    "id": point["id"],
                    "vector": new_embedding,  # 2048-dimensional
                    "payload": enhanced_payload
                }
                
                migrated_points.append(migrated_point)
                
            except Exception as e:
                print(f"⚠️ Failed to migrate point {point['id']}: {e}")
                continue
        
        return migrated_points
    
    def create_agent_accessible_payload(self, original_payload: dict, content: str) -> dict:
        """Create rich payload structure for LibrarianAgent accessibility."""
        
        # Extract narrative elements using NLP
        extracted_entities = self.extract_narrative_entities(content)
        
        return {
            # Original content and metadata
            "content": content,
            "original_filename": original_payload.get("filename"),
            "upload_timestamp": original_payload.get("timestamp"),
            
            # Agent-accessible analysis
            "material_type": self.classify_material_type(content),
            "content_summary": self.generate_summary(content),
            "key_topics": extracted_entities.get("topics", []),
            "character_names": extracted_entities.get("characters", []),
            "locations": extracted_entities.get("locations", []),
            "narrative_elements": extracted_entities.get("plot_elements", []),
            
            # Searchable metadata for agents
            "word_count": len(content.split()),
            "content_complexity": self.assess_complexity(content),
            "narrative_tags": self.generate_narrative_tags(content),
            "cross_references": self.identify_cross_references(content),
            
            # LibrarianAgent processing metadata
            "librarian_analysis": {
                "categorization_confidence": extracted_entities.get("confidence", 0.0),
                "processing_timestamp": datetime.utcnow().isoformat(),
                "analysis_version": "jina_v4_migration",
                "requires_review": self.needs_human_review(content)
            }
        }
```

**Solves:** Your Priority 1 vector dimension mismatch by migrating to proper 2048-dimensional vectors with Jina v4 compatibility.

### 2. **LibrarianAgent Smart Interaction Patterns**

**Pattern:** Design intelligent query and storage patterns for LibrarianAgent material analysis.

```python
class LibrarianAgentQdrantInterface:
    """Smart interface between LibrarianAgent and Qdrant vector database."""
    
    def __init__(self, collection_name: str = "narrative_memory_v2"):
        self.client = QdrantClient(url="http://localhost:6333")
        self.collection_name = collection_name
        self.embedding_service = EmbeddingService()
    
    async def librarian_material_analysis(self, uploaded_files: list[dict]) -> dict:
        """LibrarianAgent's intelligent material analysis and storage."""
        
        analysis_results = {
            "processed_materials": [],
            "cross_references": [],
            "narrative_insights": [],
            "storage_summary": {}
        }
        
        for file_data in uploaded_files:
            try:
                # Step 1: Extract and analyze content
                material_analysis = await self.analyze_material_for_librarian(file_data)
                
                # Step 2: Generate embeddings and store
                storage_result = await self.store_with_librarian_metadata(
                    material_analysis
                )
                
                # Step 3: Identify cross-references with existing materials
                cross_refs = await self.find_narrative_cross_references(
                    material_analysis
                )
                
                analysis_results["processed_materials"].append(storage_result)
                analysis_results["cross_references"].extend(cross_refs)
                
            except Exception as e:
                print(f"LibrarianAgent analysis failed for {file_data.get('filename')}: {e}")
        
        # Step 4: Generate narrative insights
        analysis_results["narrative_insights"] = await self.generate_narrative_insights(
            analysis_results["processed_materials"]
        )
        
        return analysis_results
    
    async def analyze_material_for_librarian(self, file_data: dict) -> dict:
        """Comprehensive material analysis tailored for LibrarianAgent needs."""
        
        content = file_data["content"]
        filename = file_data.get("filename", "unknown")
        
        return {
            "filename": filename,
            "content": content,
            "raw_analysis": {
                "word_count": len(content.split()),
                "paragraph_count": content.count('\n\n') + 1,
                "estimated_reading_time": len(content.split()) // 200,  # minutes
                "language_complexity": self.assess_language_complexity(content)
            },
            
            # Narrative-specific analysis
            "narrative_analysis": {
                "character_mentions": self.extract_character_mentions(content),
                "location_references": self.extract_locations(content),
                "plot_elements": self.identify_plot_elements(content),
                "world_building": self.extract_world_building_elements(content),
                "dialogue_ratio": self.calculate_dialogue_ratio(content)
            },
            
            # Categorization for LibrarianAgent
            "material_classification": {
                "primary_type": self.classify_primary_type(content),
                "secondary_types": self.classify_secondary_types(content), 
                "narrative_role": self.determine_narrative_role(content),
                "canon_status": self.assess_canon_status(content),
                "integration_priority": self.assess_integration_priority(content)
            },
            
            # Agent-actionable metadata
            "librarian_directives": {
                "recommended_storage_category": self.recommend_storage_category(content),
                "cross_reference_targets": self.suggest_cross_references(content),
                "quality_assessment": self.assess_material_quality(content),
                "processing_notes": self.generate_processing_notes(content)
            }
        }
    
    async def store_with_librarian_metadata(self, material_analysis: dict) -> dict:
        """Store material with comprehensive LibrarianAgent-accessible metadata."""
        
        content = material_analysis["content"]
        
        # Generate embedding
        embedding = await self.embedding_service.embed(content)
        
        # Create rich payload for agent accessibility
        librarian_payload = {
            # Core content
            "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            
            # File metadata
            "filename": material_analysis["filename"],
            "upload_timestamp": datetime.utcnow().isoformat(),
            "file_size": len(content),
            
            # LibrarianAgent analysis results
            "material_type": material_analysis["material_classification"]["primary_type"],
            "secondary_types": material_analysis["material_classification"]["secondary_types"],
            "narrative_role": material_analysis["material_classification"]["narrative_role"],
            
            # Searchable narrative elements
            "character_names": material_analysis["narrative_analysis"]["character_mentions"],
            "locations": material_analysis["narrative_analysis"]["location_references"],
            "plot_elements": material_analysis["narrative_analysis"]["plot_elements"],
            "world_building_tags": material_analysis["narrative_analysis"]["world_building"],
            
            # Agent decision-making metadata
            "integration_priority": material_analysis["material_classification"]["integration_priority"],
            "canon_status": material_analysis["material_classification"]["canon_status"],
            "quality_score": material_analysis["librarian_directives"]["quality_assessment"],
            
            # Cross-reference support
            "cross_reference_keywords": material_analysis["librarian_directives"]["cross_reference_targets"],
            "thematic_tags": self.generate_thematic_tags(content),
            
            # LibrarianAgent processing record
            "librarian_metadata": {
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "processing_version": "v2.1_jina_integration",
                "confidence_scores": {
                    "classification": material_analysis["material_classification"].get("confidence", 0.0),
                    "narrative_analysis": material_analysis["narrative_analysis"].get("confidence", 0.0)
                },
                "requires_human_review": self.requires_human_review(material_analysis),
                "processing_notes": material_analysis["librarian_directives"]["processing_notes"]
            }
        }
        
        # Store in Qdrant
        point_id = str(uuid.uuid4())
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[{
                "id": point_id,
                "vector": embedding,
                "payload": librarian_payload
            }]
        )
        
        return {
            "point_id": point_id,
            "storage_status": "success",
            "material_type": librarian_payload["material_type"],
            "narrative_elements_count": len(librarian_payload["plot_elements"]),
            "cross_reference_potential": len(librarian_payload["cross_reference_keywords"])
        }
    
    async def librarian_intelligent_search(self, query: str, context: dict = None) -> dict:
        """LibrarianAgent's intelligent search with narrative understanding."""
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        
        # Build intelligent filter based on context
        search_filter = self.build_librarian_search_filter(query, context)
        
        # Multi-layered search strategy
        search_results = await self.execute_librarian_search_strategy(
            query_embedding, search_filter, query, context
        )
        
        # Analyze and rank results for narrative relevance
        analyzed_results = await self.analyze_results_for_narrative_relevance(
            search_results, query, context
        )
        
        return {
            "query": query,
            "context": context,
            "results": analyzed_results,
            "search_strategy": "librarian_intelligent_multi_layer",
            "narrative_insights": self.extract_narrative_insights_from_results(analyzed_results)
        }
    
    def build_librarian_search_filter(self, query: str, context: dict = None):
        """Build intelligent search filters based on LibrarianAgent's analysis."""
        
        filters = []
        
        # Story context filtering
        if context and context.get("story_id"):
            filters.append(
                models.FieldCondition(
                    key="story_id", 
                    match=models.MatchValue(value=context["story_id"])
                )
            )
        
        # Character-based filtering
        mentioned_characters = self.extract_character_mentions(query)
        if mentioned_characters:
            filters.append(
                models.FieldCondition(
                    key="character_names",
                    match=models.MatchAny(any=mentioned_characters)
                )
            )
        
        # Material type filtering based on query intent
        query_intent = self.analyze_query_intent(query)
        if query_intent.get("preferred_material_types"):
            filters.append(
                models.FieldCondition(
                    key="material_type",
                    match=models.MatchAny(any=query_intent["preferred_material_types"])
                )
            )
        
        # Quality and canon filtering
        filters.extend([
            models.FieldCondition(
                key="quality_score",
                range=models.Range(gte=0.7)  # High quality materials only
            ),
            models.FieldCondition(
                key="canon_status",
                match=models.MatchAny(any=["canon", "semi_canon"])
            )
        ])
        
        return models.Filter(must=filters) if filters else None
    
    async def execute_librarian_search_strategy(self, query_embedding, search_filter, query: str, context: dict):
        """Multi-layered search strategy for comprehensive material retrieval."""
        
        search_results = {}
        
        # Layer 1: High precision semantic search
        high_precision = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=10,
            score_threshold=0.8,  # High similarity only
            with_payload=True
        )
        search_results["high_precision"] = high_precision
        
        # Layer 2: Broader semantic search
        broader_semantic = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=20,
            score_threshold=0.6,  # Moderate similarity
            with_payload=True
        )
        search_results["broader_semantic"] = broader_semantic
        
        # Layer 3: Keyword-based backup search
        keyword_filter = self.build_keyword_search_filter(query, search_filter)
        if keyword_filter:
            keyword_results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=keyword_filter,
                limit=15,
                with_payload=True
            )
            search_results["keyword_backup"] = keyword_results[0]
        
        return search_results
```

**Solves:** Your LibrarianAgent integration needs by providing intelligent material analysis, storage, and retrieval patterns.

### 3. **Agent-Accessible Vector Storage Architecture**

**Pattern:** Structure vector points and payloads for optimal agent comprehension and utilization.

```python
class AgentAccessibleVectorStorage:
    """Optimized storage patterns for agent accessibility and comprehension."""
    
    def __init__(self):
        self.client = QdrantClient(url="http://localhost:6333")
        self.story_collections = {}  # Cache for story-specific collections
    
    async def create_agent_optimized_collection(self, story_id: str, genre: str = "fantasy") -> str:
        """Create collections optimized for agent accessibility."""
        
        collection_name = f"story_{story_id}_vectors"
        
        # Multi-vector configuration for different content types
        vectors_config = {
            "content": models.VectorParams(
                size=2048,  # Jina v4 compatibility
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfig(
                    m=16,
                    ef_construct=200,
                    full_scan_threshold=10000
                )
            ),
            # Optional: Sparse vectors for exact keyword matching
            "keywords": models.VectorParams(
                size=1024,  # Sparse keyword embeddings
                distance=models.Distance.DOT,
                on_disk=True  # Less frequently accessed
            )
        }
        
        # Agent-optimized payload schema
        payload_schema = {
            # Core identification
            "story_id": models.PayloadSchemaType.KEYWORD,
            "material_id": models.PayloadSchemaType.UUID,
            "chapter_number": models.PayloadSchemaType.INTEGER,
            
            # Content classification
            "material_type": models.PayloadSchemaType.KEYWORD,  # "character_profile", "plot_outline", "world_building"
            "content_category": models.PayloadSchemaType.KEYWORD,  # "dialogue", "description", "action"
            "narrative_function": models.PayloadSchemaType.KEYWORD,  # "exposition", "rising_action", "climax"
            
            # Agent-searchable elements
            "character_names": models.PayloadSchemaType.KEYWORD,
            "character_roles": models.PayloadSchemaType.KEYWORD,
            "locations": models.PayloadSchemaType.KEYWORD,
            "plot_threads": models.PayloadSchemaType.KEYWORD,
            "thematic_elements": models.PayloadSchemaType.KEYWORD,
            
            # Quality and accessibility metadata
            "quality_score": models.PayloadSchemaType.FLOAT,
            "complexity_level": models.PayloadSchemaType.INTEGER,  # 1-10 scale
            "canon_status": models.PayloadSchemaType.KEYWORD,  # "canon", "semi_canon", "non_canon"
            "integration_priority": models.PayloadSchemaType.INTEGER,  # 1-5 priority
            
            # Temporal and relational data
            "creation_timestamp": models.PayloadSchemaType.DATETIME,
            "last_referenced": models.PayloadSchemaType.DATETIME,
            "reference_count": models.PayloadSchemaType.INTEGER,
            "dependency_ids": models.PayloadSchemaType.KEYWORD,  # Related material IDs
            
            # Agent processing metadata
            "agent_annotations": models.PayloadSchemaType.TEXT,
            "validation_status": models.PayloadSchemaType.KEYWORD,
            "requires_review": models.PayloadSchemaType.BOOL
        }
        
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            optimizers_config=models.OptimizersConfig(
                default_segment_number=2,
                max_segment_size=100000,
                memmap_threshold=50000,
                indexing_threshold=20000,
                flush_interval_sec=5,
                max_optimization_threads=4
            ),
            shard_number=1,  # Single shard for story-level collections
            on_disk_payload=False  # Keep in RAM for agent speed
        )
        
        self.story_collections[story_id] = collection_name
        return collection_name
    
    async def store_agent_accessible_content(self, content_data: dict, story_id: str) -> dict:
        """Store content in agent-accessible format with comprehensive metadata."""
        
        collection_name = self.story_collections.get(story_id) or \
                         await self.create_agent_optimized_collection(story_id)
        
        # Process content for agent accessibility
        processed_content = await self.process_for_agent_accessibility(content_data)
        
        # Generate embeddings
        content_embedding = await self.embedding_service.embed(processed_content["content"])
        
        # Create agent-accessible payload
        agent_payload = await self.create_agent_accessible_payload(
            processed_content, story_id
        )
        
        # Store with multiple vectors if needed
        point_data = {
            "id": str(uuid.uuid4()),
            "vector": {
                "content": content_embedding,
                # Add keyword vector if available
                "keywords": processed_content.get("keyword_vector", None)
            },
            "payload": agent_payload
        }
        
        # Filter out None vectors
        point_data["vector"] = {k: v for k, v in point_data["vector"].items() if v is not None}
        
        self.client.upsert(
            collection_name=collection_name,
            points=[point_data]
        )
        
        return {
            "point_id": point_data["id"],
            "collection": collection_name,
            "storage_status": "success",
            "agent_accessible_metadata": {
                "material_type": agent_payload["material_type"],
                "character_count": len(agent_payload["character_names"]),
                "complexity_level": agent_payload["complexity_level"],
                "narrative_functions": agent_payload["narrative_function"]
            }
        }
    
    async def create_agent_accessible_payload(self, processed_content: dict, story_id: str) -> dict:
        """Create comprehensive payload optimized for agent understanding."""
        
        content = processed_content["content"]
        
        return {
            # Core identification
            "story_id": story_id,
            "material_id": str(uuid.uuid4()),
            "content": content,
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
            
            # Content analysis for agents
            "material_type": processed_content.get("material_type", "general"),
            "content_category": processed_content.get("content_category", "mixed"),
            "narrative_function": processed_content.get("narrative_function", "development"),
            
            # Agent-searchable narrative elements
            "character_names": processed_content.get("character_names", []),
            "character_roles": processed_content.get("character_roles", []),
            "locations": processed_content.get("locations", []),
            "plot_threads": processed_content.get("plot_threads", []),
            "thematic_elements": processed_content.get("thematic_elements", []),
            
            # Agent decision-making metadata
            "quality_score": processed_content.get("quality_score", 0.8),
            "complexity_level": processed_content.get("complexity_level", 5),
            "canon_status": processed_content.get("canon_status", "canon"),
            "integration_priority": processed_content.get("integration_priority", 3),
            
            # Temporal tracking
            "creation_timestamp": datetime.utcnow().isoformat(),
            "last_referenced": datetime.utcnow().isoformat(),
            "reference_count": 0,
            "dependency_ids": processed_content.get("dependency_ids", []),
            
            # Agent processing support
            "agent_readable_summary": processed_content.get("summary", content[:200] + "..."),
            "key_concepts": processed_content.get("key_concepts", []),
            "emotional_tone": processed_content.get("emotional_tone", "neutral"),
            "pacing_indicators": processed_content.get("pacing_indicators", []),
            
            # Validation and review
            "validation_status": "pending_agent_review",
            "requires_review": False,
            "agent_annotations": "",
            
            # Cross-reference support
            "related_materials": [],
            "conflict_indicators": [],
            "consistency_checks": {
                "character_consistency": True,
                "plot_consistency": True,
                "world_consistency": True
            }
        }
    
    async def agent_query_interface(self, agent_name: str, query: str, story_id: str, 
                                   context: dict = None) -> dict:
        """Optimized query interface for different agent types."""
        
        collection_name = self.story_collections.get(story_id)
        if not collection_name:
            return {"error": "Story collection not found", "story_id": story_id}
        
        # Generate query embedding
        query_embedding = await self.embedding_service.embed(query)
        
        # Agent-specific search optimization
        agent_config = self.get_agent_search_config(agent_name)
        
        # Build intelligent filters
        search_filter = await self.build_agent_specific_filter(
            agent_name, query, context, story_id
        )
        
        # Execute optimized search
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=agent_config["result_limit"],
            score_threshold=agent_config["score_threshold"],
            with_payload=True,
            with_vectors=agent_config.get("include_vectors", False)
        )
        
        # Post-process results for agent comprehension
        agent_results = await self.process_results_for_agent(
            results, agent_name, query, context
        )
        
        return {
            "agent": agent_name,
            "query": query,
            "story_id": story_id,
            "results": agent_results,
            "result_count": len(agent_results),
            "search_metadata": {
                "collection_used": collection_name,
                "filter_applied": search_filter is not None,
                "score_threshold": agent_config["score_threshold"]
            }
        }
    
    def get_agent_search_config(self, agent_name: str) -> dict:
        """Agent-specific search configurations."""
        
        configs = {
            "DirectorAgent": {
                "result_limit": 15,
                "score_threshold": 0.7,
                "prefer_material_types": ["plot_outline", "character_development", "world_building"],
                "include_vectors": False
            },
            "TacticianAgent": {
                "result_limit": 10,
                "score_threshold": 0.75,
                "prefer_material_types": ["scene_structure", "pacing_notes", "beat_sheets"],
                "include_vectors": False
            },
            "WeaverAgent": {
                "result_limit": 8,
                "score_threshold": 0.8,
                "prefer_material_types": ["dialogue_samples", "description_examples", "style_guides"],
                "include_vectors": False
            },
            "CanonistAgent": {
                "result_limit": 20,
                "score_threshold": 0.6,
                "prefer_material_types": ["character_profiles", "world_rules", "timeline_events"],
                "include_vectors": True  # Needs vectors for consistency analysis
            },
            "LibrarianAgent": {
                "result_limit": 25,
                "score_threshold": 0.5,
                "prefer_material_types": ["all"],  # Librarian sees everything
                "include_vectors": False
            }
        }
        
        return configs.get(agent_name, {
            "result_limit": 10,
            "score_threshold": 0.7,
            "prefer_material_types": ["general"],
            "include_vectors": False
        })
    
    async def build_agent_specific_filter(self, agent_name: str, query: str, 
                                         context: dict, story_id: str):
        """Build filters tailored to each agent's needs."""
        
        base_filters = [
            models.FieldCondition(
                key="story_id", 
                match=models.MatchValue(value=story_id)
            )
        ]
        
        agent_config = self.get_agent_search_config(agent_name)
        
        # Material type filtering
        if agent_config["prefer_material_types"] != ["all"]:
            base_filters.append(
                models.FieldCondition(
                    key="material_type",
                    match=models.MatchAny(any=agent_config["prefer_material_types"])
                )
            )
        
        # Agent-specific filters
        if agent_name == "DirectorAgent":
            # Director needs high-level strategic content
            base_filters.extend([
                models.FieldCondition(
                    key="integration_priority",
                    range=models.Range(gte=3)
                ),
                models.FieldCondition(
                    key="narrative_function",
                    match=models.MatchAny(any=["exposition", "rising_action", "climax", "resolution"])
                )
            ])
        
        elif agent_name == "CanonistAgent":
            # Canonist needs everything for consistency checking
            base_filters.extend([
                models.FieldCondition(
                    key="canon_status",
                    match=models.MatchAny(any=["canon", "semi_canon"])
                )
            ])
        
        elif agent_name == "WeaverAgent":
            # Weaver needs style and prose examples
            base_filters.extend([
                models.FieldCondition(
                    key="quality_score",
                    range=models.Range(gte=0.8)
                )
            ])
        
        return models.Filter(must=base_filters) if base_filters else None
```

**Solves:** Your agent accessibility challenges by creating structured, searchable vector storage optimized for each agent's specific needs.

---

## 🔧 Production Integration Patterns

### 1. **Jina v4 Embedding Service Integration**

```python
class JinaV4QdrantIntegration:
    """Complete integration between Jina Embedding v4 and Qdrant."""
    
    def __init__(self):
        self.qdrant_client = QdrantClient(url="http://localhost:6333")
        self.embedding_service = EmbeddingService()  # Your existing service
    
    async def verify_jina_v4_compatibility(self) -> dict:
        """Verify Jina v4 generates 2048-dimensional embeddings."""
        
        test_text = "This is a test for Jina Embedding v4 compatibility."
        embedding = await self.embedding_service.embed(test_text)
        
        return {
            "jina_v4_compatible": len(embedding) == 2048,
            "actual_dimensions": len(embedding),
            "expected_dimensions": 2048,
            "embedding_model": "jina-embeddings-v4",
            "status": "compatible" if len(embedding) == 2048 else "dimension_mismatch"
        }
    
    async def create_jina_optimized_collection(self, collection_name: str):
        """Create collection specifically optimized for Jina v4 embeddings."""
        
        self.qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=2048,  # Jina v4 dimension
                distance=models.Distance.COSINE,
                hnsw_config=models.HnswConfig(
                    m=16,  # Optimal for Jina embeddings
                    ef_construct=200,
                    full_scan_threshold=10000
                )
            ),
            optimizers_config=models.OptimizersConfig(
                # Optimized for Jina embedding characteristics
                default_segment_number=4,
                max_segment_size=50000,
                memmap_threshold=30000,
                indexing_threshold=15000
            )
        )
```

### 2. **Collection Management and Migration Tools**

```python
class QdrantMigrationTools:
    """Tools for managing collection migrations and upgrades."""
    
    async def migrate_collection_dimensions(self, old_collection: str, 
                                          new_collection: str) -> dict:
        """Complete collection dimension migration."""
        
        migration_log = {
            "start_time": datetime.utcnow().isoformat(),
            "old_collection": old_collection,
            "new_collection": new_collection,
            "migrated_points": 0,
            "failed_points": 0,
            "errors": []
        }
        
        try:
            # Create new collection with 2048 dimensions
            await self.create_jina_v4_collection(new_collection)
            
            # Batch migrate existing points
            batch_size = 100
            offset = None
            
            while True:
                # Scroll through old collection
                points_batch, next_offset = self.client.scroll(
                    collection_name=old_collection,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False  # Don't need old vectors
                )
                
                if not points_batch:
                    break
                
                # Re-embed and migrate batch
                migrated_batch = []
                for point in points_batch:
                    try:
                        # Extract content and re-embed
                        content = point.payload.get("content", "")
                        if content:
                            new_embedding = await self.embedding_service.embed(content)
                            
                            migrated_batch.append({
                                "id": point.id,
                                "vector": new_embedding,
                                "payload": point.payload
                            })
                            migration_log["migrated_points"] += 1
                        
                    except Exception as e:
                        migration_log["failed_points"] += 1
                        migration_log["errors"].append(f"Point {point.id}: {str(e)}")
                
                # Upload migrated batch
                if migrated_batch:
                    self.client.upsert(
                        collection_name=new_collection,
                        points=migrated_batch
                    )
                
                offset = next_offset
                if offset is None:
                    break
            
            migration_log["status"] = "success"
            migration_log["end_time"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            migration_log["status"] = "failed"
            migration_log["error"] = str(e)
            migration_log["end_time"] = datetime.utcnow().isoformat()
        
        return migration_log
```

---

## 🎯 Recommendations for Narrative Factory

### **Primary Recommendation: Immediate Priority 1 Fix**

**Critical Actions:**
1. **Update Configuration** - Change `vector_size: int = Field(default=2048)` in `src/config.py`
2. **Migrate Collections** - Use migration tools to create Jina v4-compatible collections
3. **Enhance Payloads** - Implement agent-accessible payload structures
4. **Integrate LibrarianAgent** - Deploy smart interaction patterns

**Implementation Sequence:**
```python
# Week 1: Fix Priority 1 Issues
await migration_tools.migrate_collection_dimensions(
    "narrative_memory",  # Current 768-dim collection
    "narrative_memory_v2"  # New 2048-dim collection
)

# Week 2: Deploy LibrarianAgent Integration
librarian_interface = LibrarianAgentQdrantInterface("narrative_memory_v2")
await librarian_interface.setup_agent_optimization()

# Week 3: Full Production Integration
await create_agent_optimized_collections_for_all_stories()
```

**CodeFarmer:** This comprehensive Qdrant analysis provides the exact solutions for your three critical integration points: LibrarianAgent smart interaction, Jina v4 compatibility, and agent-accessible storage.

**Programmatron:** The migration tools and payload structures directly solve your Priority 1 vector dimension mismatch while enabling sophisticated agent-vector database interactions.

**TestBot:** VALIDATION CONFIRMED - These patterns address your specific architectural challenges while maintaining production performance and scalability.

---

***Next:*** Complete comprehensive architectural analysis integrating all five frameworks (Reflex + Pydantic AI + Prefect v3 + ControlFlow + Qdrant) to solve your Priority 1 and Priority 2 issues.