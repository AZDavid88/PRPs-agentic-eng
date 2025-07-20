"""
LibrarianAgent: Specialized agent for material ingestion oversight and analysis.

Provides automated material analysis, cross-reference generation, and quality
assessment using concurrent processing with late chunking optimization.
"""

import asyncio
import re
import time
from typing import Any, Optional

from src.agents.personas import Agent
from src.logger import get_logger
from src.memory.embedding_service import EmbeddingService
from src.memory.service import MemoryService
from src.models.librarian_models import (
    CrossReference,
    CrossReferenceGenerationError,
    EmbeddingGenerationError,
    LibrarianError,
    MaterialAnalysisRequest,
    MaterialAnalysisResponse,
    MaterialAnalysisResult,
    MaterialProcessingError,
    MemoryStorageError,
    ProcessingMetrics,
    QualityAssessment,
)
from src.models.material_models import MaterialClassification


logger = get_logger(__name__)


class LibrarianAgent(Agent):
    """
    Specialized agent for material ingestion oversight and analysis.

    Provides:
    - Concurrent material processing with late chunking
    - Cross-reference generation between materials
    - Quality assessment and validation
    - Specialized analysis based on material types
    - Integration with memory service and embedding systems
    """

    def __init__(
        self,
        client_type: str = "openai",
        memory_service: Optional[MemoryService] = None
    ):
        """
        Initialize LibrarianAgent with specialized capabilities.

        Args:
            client_type: LLM client type (openai recommended for embeddings)
            memory_service: Memory service for storage operations
        """
        # Auto-initialize memory service if not provided
        if memory_service is None:
            from src.memory.service import get_memory_service
            memory_service = get_memory_service()

        # Use placeholder persona - will be populated when persona content is created
        super().__init__("librarian", client_type, memory_service)

        # Initialize services
        self.embedding_service = EmbeddingService(provider="jina")

        # Processing configuration
        self.max_concurrent_materials = 20
        self.default_embedding_model = "jina-embeddings-v4"
        self.embedding_dimensions = 2048  # Jina v4 dimensions
        self.similarity_threshold = 0.7

        # Metrics tracking
        self.processing_metrics = ProcessingMetrics()

        logger.info(f"LibrarianAgent initialized with {client_type} client")

    async def analyze_materials(
        self,
        request: MaterialAnalysisRequest
    ) -> MaterialAnalysisResponse:
        """
        Main entry point for material analysis with concurrent processing.

        Args:
            request: Analysis request containing materials and configuration

        Returns:
            Complete analysis response with results and metrics
        """
        logger.info(f"Starting analysis of {len(request.classifications)} materials")

        # Initialize metrics
        metrics = ProcessingMetrics()
        start_time = time.time()

        # Validate concurrent limit
        concurrent_limit = min(request.concurrent_limit, self.max_concurrent_materials)

        # Create smart batches for optimal processing
        batches = self._create_smart_batches(request.classifications, concurrent_limit)

        # Process batches concurrently
        all_results = []
        total_successful = 0
        total_failed = 0

        for batch in batches:
            logger.debug(f"Processing batch of {len(batch)} materials")

            # Process batch with concurrent execution
            batch_results = await self._process_material_batch(batch, request, metrics)

            # Separate successful and failed results
            successful_results = [r for r in batch_results if not isinstance(r, Exception)]
            failed_results = [r for r in batch_results if isinstance(r, Exception)]

            all_results.extend(successful_results)
            total_successful += len(successful_results)
            total_failed += len(failed_results)

            # Log batch completion
            logger.debug(f"Batch completed: {len(successful_results)} successful, {len(failed_results)} failed")

        # Generate cross-references if requested and we have enough materials
        cross_references_generated = 0
        if request.enable_cross_references and len(all_results) > 1:
            try:
                cross_references = await self._generate_cross_references(all_results)
                cross_references_generated = len(cross_references)

                # Add cross-references to results
                self._add_cross_references_to_results(all_results, cross_references)

                logger.info(f"Generated {cross_references_generated} cross-references")
            except Exception as e:
                logger.error(f"Cross-reference generation failed: {e}")

        # Calculate quality issues
        quality_issues_found = sum(
            len(result.quality_assessment.issues_found)
            for result in all_results
            if result.quality_assessment
        )

        # Create response
        processing_time = time.time() - start_time
        response = MaterialAnalysisResponse(
            request_id=f"analysis_{int(time.time() * 1000)}",
            results=all_results,
            successful_count=total_successful,
            failed_count=total_failed,
            processing_time=processing_time,
            cross_references_generated=cross_references_generated,
            quality_issues_found=quality_issues_found,
            metrics=metrics
        )

        logger.info(
            f"Analysis complete: {total_successful}/{total_successful + total_failed} successful "
            f"in {processing_time:.2f}s"
        )

        return response

    def _create_smart_batches(
        self,
        classifications: list[MaterialClassification],
        max_concurrent: int
    ) -> list[list[MaterialClassification]]:
        """
        Create intelligent batches based on content size and processing requirements.

        Args:
            classifications: Materials to batch
            max_concurrent: Maximum concurrent processing limit

        Returns:
            List of material batches optimized for processing
        """
        # Simple batching strategy - can be enhanced based on content size
        batch_size = max(1, max_concurrent // 2)  # Conservative batching

        batches = []
        for i in range(0, len(classifications), batch_size):
            batch = classifications[i:i + batch_size]
            batches.append(batch)

        logger.debug(f"Created {len(batches)} batches with max size {batch_size}")
        return batches

    async def _process_material_batch(
        self,
        batch: list[MaterialClassification],
        request: MaterialAnalysisRequest,
        metrics: ProcessingMetrics
    ) -> list[MaterialAnalysisResult]:
        """
        Process a batch of materials concurrently.

        Args:
            batch: Materials to process
            request: Analysis request configuration
            metrics: Metrics tracking object

        Returns:
            List of analysis results (may include exceptions)
        """
        # Create concurrent tasks for batch
        tasks = [
            self._analyze_single_material_with_retry(material, request, metrics)
            for material in batch
        ]

        # Execute concurrently with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def _analyze_single_material_with_retry(
        self,
        classification: MaterialClassification,
        request: MaterialAnalysisRequest,
        metrics: ProcessingMetrics,
        max_retries: int = 3
    ) -> MaterialAnalysisResult:
        """
        Analyze a single material with retry logic and error handling.

        Args:
            classification: Material to analyze
            request: Analysis request configuration
            metrics: Metrics tracking object
            max_retries: Maximum retry attempts

        Returns:
            Analysis result for the material
        """
        start_time = time.time()

        for attempt in range(max_retries):
            try:
                result = await self._analyze_single_material(classification, request)

                # Record successful processing
                processing_time = time.time() - start_time
                result.processing_time = processing_time
                metrics.record_processing_step("material")

                logger.debug(f"Material {classification.id} analyzed successfully in {processing_time:.2f}s")
                return result

            except EmbeddingGenerationError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Embedding generation failed for {classification.id} after {max_retries} attempts: {e}")
                    raise MaterialProcessingError(f"Embedding generation failed: {e}") from e

                # Exponential backoff for embedding errors
                wait_time = 2 ** attempt
                logger.warning(f"Embedding error for {classification.id}, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

            except MemoryStorageError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Memory storage failed for {classification.id} after {max_retries} attempts: {e}")
                    raise MaterialProcessingError(f"Memory storage failed: {e}") from e

                # Different backoff for storage errors
                wait_time = 1.5 ** attempt
                logger.warning(f"Storage error for {classification.id}, retrying in {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Unexpected error processing {classification.id}: {e}")
                raise MaterialProcessingError(f"Processing failed: {e}") from e

        # Should not reach here due to exception handling above
        raise MaterialProcessingError("Retry logic failed unexpectedly")

    async def _analyze_single_material(
        self,
        classification: MaterialClassification,
        request: MaterialAnalysisRequest
    ) -> MaterialAnalysisResult:
        """
        Analyze a single material with full late chunking treatment.

        Args:
            classification: Material to analyze
            request: Analysis request configuration

        Returns:
            Complete analysis result for the material
        """
        logger.debug(f"Analyzing material {classification.id} ({classification.category})")

        try:
            # Process material with late chunking
            vector_metadata = await self._process_material_with_late_chunking(
                classification.content,
                classification.category,
                classification.id
            )

            # Quality assessment if requested
            quality_assessment = None
            if request.enable_quality_assessment:
                quality_assessment = await self._assess_material_quality(
                    classification, request.analysis_depth
                )

            # Specialized analysis based on material type
            specialized_analysis = await self._perform_specialized_analysis(
                classification, request.analysis_depth
            )

            return MaterialAnalysisResult(
                source_classification=classification,
                vector_storage_metadata=vector_metadata,
                cross_references=[],  # Will be populated later
                quality_assessment=quality_assessment,
                specialized_analysis=specialized_analysis
            )

        except Exception as e:
            logger.error(f"Failed to analyze material {classification.id}: {e}")
            raise MaterialProcessingError(f"Analysis failed for {classification.id}: {e}") from e

    async def _process_material_with_late_chunking(
        self,
        content: str,
        category: str,
        material_id: str
    ) -> dict[str, Any]:
        """
        Process material using late chunking with recursive text splitting.

        Args:
            content: Material content to process
            category: Material category for specialized processing
            material_id: Unique material identifier

        Returns:
            Processing metadata including storage information
        """
        try:
            # Cognitive chunking strategy - leverage LibrarianAgent's LateChunkingCoordinator
            chunking_strategy = await self._determine_optimal_chunking_strategy(
                content, category, material_id
            )
            
            chunks = await self._execute_chunking_strategy(content, category, chunking_strategy)

            # Context-aware embedding generation with Jina v4
            embeddings = await self._generate_context_aware_embeddings(chunks, category, chunking_strategy)

            # Store in memory service with enhanced metadata
            if self.memory_service is None:
                raise ValueError("Memory service not initialized")
            storage_result = await self.memory_service.store_material_embeddings(
                content=content,
                embeddings=embeddings,
                category=category,
                material_id=material_id,
                metadata={
                    "chunks_count": len(chunks),
                    "embedding_model": self.default_embedding_model,
                    "processing_strategy": category,
                    "content_length": len(content)
                }
            )

            return {
                "chunks_count": len(chunks),
                "embeddings_generated": len(embeddings),
                "storage_result": storage_result,
                "processing_strategy": category,
                "primary_embedding": embeddings[0] if embeddings else None  # For cross-references
            }

        except Exception as e:
            logger.error(f"Late chunking processing failed: {e}")
            raise EmbeddingGenerationError(f"Late chunking failed: {e}") from e

    async def _recursive_text_splitting(
        self,
        text: str,
        max_length: int = 1000,
        overlap: int = 200
    ) -> list[str]:
        """
        Recursively split text while preserving semantic boundaries.

        Args:
            text: Text to split
            max_length: Maximum chunk length
            overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]

        # Hierarchical separators for better semantic preservation
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]

        def split_with_separator(text: str, separator: str) -> list[str]:
            if separator not in text:
                return [text]

            parts = text.split(separator)
            chunks = []
            current_chunk = ""

            for part in parts:
                potential_chunk = current_chunk + (separator if current_chunk else "") + part

                if len(potential_chunk) <= max_length:
                    current_chunk = potential_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = part

            if current_chunk:
                chunks.append(current_chunk)

            return chunks

        # Try each separator in order
        for separator in separators:
            chunks = split_with_separator(text, separator)
            if all(len(chunk) <= max_length for chunk in chunks):
                return chunks

        # Fallback: character-level splitting with overlap
        chunks = []
        for i in range(0, len(text), max_length - overlap):
            chunk = text[i:i + max_length]
            chunks.append(chunk)

        return chunks

    async def _specialized_chunking(self, content: str, category: str) -> list[str]:
        """
        Specialized chunking for unique material types.

        Args:
            content: Content to chunk
            category: Material category requiring specialized handling

        Returns:
            Specialized chunks for the material type
        """
        if category == "prose_style_guide":
            # Chunk by style elements and examples
            return self._chunk_prose_style_guide(content)
        elif category == "character_voice_profile":
            # Chunk by character attributes and voice examples
            return self._chunk_character_voice_profile(content)
        else:
            # Fallback to standard chunking
            return await self._recursive_text_splitting(content)

    def _chunk_prose_style_guide(self, content: str) -> list[str]:
        """Chunk prose style guide by style elements."""
        # Look for common style guide patterns
        patterns = [
            r"Style:\s*",
            r"Voice:\s*",
            r"Tone:\s*",
            r"Example:\s*",
            r"Sample:\s*"
        ]

        # Simple pattern-based chunking
        chunks = []
        current_chunk = ""

        lines = content.split('\n')
        for line in lines:
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in patterns):
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += "\n" + line

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [content]

    def _chunk_character_voice_profile(self, content: str) -> list[str]:
        """Chunk character voice profile by character attributes."""
        # Look for character profile patterns
        patterns = [
            r"Personality:\s*",
            r"Speech:\s*",
            r"Dialogue:\s*",
            r"Mannerisms:\s*",
            r"Background:\s*"
        ]

        # Simple pattern-based chunking
        chunks = []
        current_chunk = ""

        lines = content.split('\n')
        for line in lines:
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in patterns):
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += "\n" + line

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [content]

    async def _determine_optimal_chunking_strategy(
        self,
        content: str,
        category: str,
        material_id: str
    ) -> dict[str, Any]:
        """
        Leverage LibrarianAgent's LateChunkingCoordinator to determine optimal strategy.
        
        Uses cognitive analysis to decide chunking approach based on:
        - Content complexity and structure
        - Category requirements  
        - Retrieval optimization needs
        - Genre-specific considerations
        """
        content_length = len(content)
        word_count = len(content.split())
        
        # Cognitive analysis of content structure
        strategy = {
            "method": "recursive",  # default
            "chunk_size": 1000,
            "overlap": 200,
            "preserve_structure": False,
            "use_late_chunking": True,
            "reasoning": []
        }
        
        # Content-based cognitive decisions
        if content_length > 8000:  # Jina v4 context window
            strategy["use_late_chunking"] = True
            strategy["chunk_size"] = 1200  # Larger chunks for late chunking
            strategy["reasoning"].append("Large content benefits from late chunking with Jina v4")
            
        # Category-aware chunking intelligence
        if category in ["prose_style_guide", "character_voice_profile"]:
            strategy["method"] = "specialized"
            strategy["preserve_structure"] = True
            strategy["reasoning"].append(f"Specialized chunking for {category} maintains semantic integrity")
            
        elif category in ["magic_system", "world_building", "technology"]:
            strategy["method"] = "hierarchical"
            strategy["chunk_size"] = 800  # Smaller for detailed systems
            strategy["overlap"] = 150
            strategy["reasoning"].append("System documentation requires hierarchical preservation")
            
        elif category in ["character", "relationship_dynamic"]:
            strategy["method"] = "entity_aware"
            strategy["preserve_structure"] = True
            strategy["reasoning"].append("Character content needs entity-relationship preservation")
            
        elif category in ["plot_element", "narrative_style"]:
            strategy["method"] = "narrative_flow"
            strategy["chunk_size"] = 1400  # Longer for narrative flow
            strategy["reasoning"].append("Narrative content benefits from flow preservation")
            
        # Complexity-based adjustments
        if word_count < 100:
            strategy["method"] = "minimal"
            strategy["chunk_size"] = content_length
            strategy["reasoning"].append("Short content processed as single chunk")
            
        elif word_count > 2000:
            strategy["overlap"] = min(300, strategy["chunk_size"] // 4)
            strategy["reasoning"].append("Long content needs increased overlap for coherence")
            
        logger.debug(f"Chunking strategy for {material_id}: {strategy['method']} - {', '.join(strategy['reasoning'])}")
        return strategy

    async def _execute_chunking_strategy(
        self,
        content: str,
        category: str,
        strategy: dict[str, Any]
    ) -> list[str]:
        """Execute the determined chunking strategy."""
        
        method = strategy["method"]
        
        if method == "minimal":
            return [content]
            
        elif method == "specialized":
            return await self._specialized_chunking(content, category)
            
        elif method == "hierarchical":
            return await self._hierarchical_chunking(content, strategy)
            
        elif method == "entity_aware":
            return await self._entity_aware_chunking(content, strategy)
            
        elif method == "narrative_flow":
            return await self._narrative_flow_chunking(content, strategy)
            
        else:  # recursive (default)
            return await self._recursive_text_splitting(
                content, 
                strategy["chunk_size"], 
                strategy["overlap"]
            )
    
    async def _generate_context_aware_embeddings(
        self,
        chunks: list[str],
        category: str,
        strategy: dict[str, Any]
    ) -> list[list[float]]:
        """Generate embeddings with context awareness and late chunking optimization."""
        
        if strategy["use_late_chunking"] and len(chunks) > 1:
            # Use Jina v4's late chunking capabilities for multi-chunk content
            logger.debug(f"Using late chunking for {len(chunks)} chunks in category {category}")
            
            # For late chunking, we provide the full context to Jina v4
            full_content = "\n\n".join(chunks)
            if len(full_content) <= 8192:  # Within Jina v4 context window
                # Generate single embedding with full context, then extract chunk vectors
                full_embedding = await self.embedding_service.generate_embeddings([full_content])
                
                # For now, replicate the full embedding for each chunk
                # Future enhancement: implement true late chunking vector extraction
                return [full_embedding[0] for _ in chunks]
        
        # Standard embedding generation
        return await self.embedding_service.generate_embeddings(chunks)

    async def _hierarchical_chunking(self, content: str, strategy: dict[str, Any]) -> list[str]:
        """Chunk content preserving hierarchical structure (headers, sections)."""
        import re
        
        # Look for markdown-style headers or section breaks
        header_pattern = r'^#{1,6}\s+.*$|^[A-Z][^a-z]*:?\s*$'
        lines = content.split('\n')
        
        chunks = []
        current_chunk = ""
        chunk_size = strategy["chunk_size"]
        
        for line in lines:
            if re.match(header_pattern, line.strip()) and len(current_chunk) > chunk_size // 2:
                # Start new chunk at header if current chunk is substantial
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += "\n" + line
                
            if len(current_chunk) > chunk_size:
                chunks.append(current_chunk.strip())
                current_chunk = ""
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks if chunks else [content]

    async def _entity_aware_chunking(self, content: str, strategy: dict[str, Any]) -> list[str]:
        """Chunk content preserving entity relationships and character mentions."""
        # Simple entity-aware chunking - can be enhanced with NER
        import re
        
        # Look for character name patterns (capitalized words)
        entity_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        
        sentences = re.split(r'[.!?]+', content)
        chunks = []
        current_chunk = ""
        chunk_size = strategy["chunk_size"]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed chunk size and we have content
            if len(current_chunk + sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks if chunks else [content]

    async def _narrative_flow_chunking(self, content: str, strategy: dict[str, Any]) -> list[str]:
        """Chunk content preserving narrative flow and scene boundaries."""
        import re
        
        # Look for scene breaks, paragraph breaks, dialogue transitions
        scene_break_patterns = [
            r'\n\s*\*\s*\*\s*\*\s*\n',  # *** scene breaks
            r'\n\s*---+\s*\n',           # --- scene breaks  
            r'\n\s*\n\s*\n',             # Double line breaks
        ]
        
        # Split on scene breaks first
        text = content
        for pattern in scene_break_patterns:
            text = re.sub(pattern, '\n[SCENE_BREAK]\n', text)
        
        sections = text.split('[SCENE_BREAK]')
        chunks = []
        current_chunk = ""
        chunk_size = strategy["chunk_size"]
        
        for section in sections:
            section = section.strip()
            if not section:
                continue
                
            if len(current_chunk + section) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                current_chunk += ("\n\n" if current_chunk else "") + section
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks if chunks else [content]

    async def _assess_material_quality(
        self,
        classification: MaterialClassification,
        analysis_depth: str
    ) -> QualityAssessment:
        """
        Assess material quality with simple pass/fail scoring.

        Args:
            classification: Material to assess
            analysis_depth: Depth of analysis to perform

        Returns:
            Quality assessment with score and issues
        """
        issues_found = []
        recommendations = []

        # Basic quality checks
        content = classification.content

        # Length check
        if len(content) < 50:
            issues_found.append("Content too short for meaningful analysis")

        # Content density check
        word_count = len(content.split())
        if word_count < 10:
            issues_found.append("Content lacks sufficient detail")

        # Category consistency check
        if classification.confidence_score < 0.7:
            issues_found.append(f"Low classification confidence: {classification.confidence_score:.2f}")
            recommendations.append("Review material category assignment")

        # Calculate quality score
        base_score = 1.0

        # Deduct for issues
        penalty_per_issue = 0.2
        quality_score = max(0.0, base_score - (len(issues_found) * penalty_per_issue))

        # Determine if acceptable
        is_acceptable = quality_score >= 0.6 and len(issues_found) <= 2

        return QualityAssessment(
            is_acceptable=is_acceptable,
            quality_score=quality_score,
            issues_found=issues_found,
            recommendations=recommendations
        )

    async def _perform_specialized_analysis(
        self,
        classification: MaterialClassification,
        analysis_depth: str
    ) -> dict[str, Any]:
        """
        Perform specialized analysis based on material type.

        Args:
            classification: Material to analyze
            analysis_depth: Depth of analysis

        Returns:
            Specialized analysis results
        """
        base_analysis = {
            "analysis_type": classification.category,
            "analysis_depth": analysis_depth,
            "content_length": len(classification.content),
            "word_count": len(classification.content.split()),
            "confidence_score": classification.confidence_score
        }

        # Category-specific analysis
        if classification.category == "prose_style_guide":
            return {**base_analysis, **await self._analyze_prose_style_guide(classification)}
        elif classification.category == "character_voice_profile":
            return {**base_analysis, **await self._analyze_character_profile(classification)}
        elif classification.category == "character":
            return {**base_analysis, **await self._analyze_character_material(classification)}
        elif classification.category == "setting":
            return {**base_analysis, **await self._analyze_setting_material(classification)}
        elif classification.category == "plot_element":
            return {**base_analysis, **await self._analyze_plot_material(classification)}
        else:
            return {**base_analysis, **await self._analyze_generic_material(classification)}

    async def _analyze_prose_style_guide(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze prose style guide materials."""
        content = classification.content.lower()

        # Extract style elements
        style_indicators = {
            "formal": len([w for w in ["formal", "proper", "elegant", "refined"] if w in content]),
            "casual": len([w for w in ["casual", "informal", "relaxed", "conversational"] if w in content]),
            "descriptive": len([w for w in ["vivid", "detailed", "rich", "descriptive"] if w in content]),
            "dialogue_heavy": len([w for w in ["dialogue", "conversation", "speech", "talking"] if w in content])
        }

        return {
            "style_indicators": style_indicators,
            "dominant_style": max(style_indicators, key=lambda x: style_indicators[x]),
            "has_examples": "example" in content or "sample" in content
        }

    async def _analyze_character_profile(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze character voice profile materials."""
        content = classification.content.lower()

        # Extract character elements
        personality_indicators = {
            "introverted": len([w for w in ["quiet", "reserved", "introspective", "shy"] if w in content]),
            "extroverted": len([w for w in ["outgoing", "social", "talkative", "energetic"] if w in content]),
            "confident": len([w for w in ["confident", "assertive", "bold", "strong"] if w in content]),
            "cautious": len([w for w in ["careful", "cautious", "hesitant", "wary"] if w in content])
        }

        return {
            "personality_indicators": personality_indicators,
            "dominant_trait": max(personality_indicators, key=lambda x: personality_indicators[x]),
            "has_dialogue_examples": "says" in content or "\"" in classification.content
        }

    async def _analyze_character_material(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze general character materials."""
        content = classification.content

        return {
            "mentions_appearance": any(word in content.lower() for word in ["looks", "appearance", "eyes", "hair", "tall", "short"]),
            "mentions_personality": any(word in content.lower() for word in ["personality", "trait", "character", "nature"]),
            "mentions_background": any(word in content.lower() for word in ["background", "history", "past", "origin"]),
            "has_dialogue": "\"" in content or "says" in content.lower()
        }

    async def _analyze_setting_material(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze setting materials."""
        content = classification.content.lower()

        return {
            "location_type": self._identify_location_type(content),
            "time_period": self._identify_time_period(content),
            "atmosphere": self._identify_atmosphere(content),
            "has_sensory_details": any(word in content for word in ["smell", "sound", "texture", "taste", "sight"])
        }

    async def _analyze_plot_material(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze plot element materials."""
        content = classification.content.lower()

        return {
            "plot_type": self._identify_plot_type(content),
            "conflict_type": self._identify_conflict_type(content),
            "has_action": any(word in content for word in ["action", "fight", "chase", "battle", "struggle"]),
            "has_resolution": any(word in content for word in ["resolve", "solution", "end", "conclusion"])
        }

    async def _analyze_generic_material(self, classification: MaterialClassification) -> dict[str, Any]:
        """Analyze materials that don't fit specific categories."""
        content = classification.content

        return {
            "content_type": "generic",
            "has_narrative_elements": any(word in content.lower() for word in ["story", "narrative", "plot", "character"]),
            "descriptive_ratio": len([w for w in content.split() if len(w) > 6]) / len(content.split()) if content.split() else 0
        }

    def _identify_location_type(self, content: str) -> str:
        """Identify the type of location from content."""
        if any(word in content for word in ["city", "town", "urban", "street"]):
            return "urban"
        elif any(word in content for word in ["forest", "mountain", "rural", "countryside"]):
            return "rural"
        elif any(word in content for word in ["castle", "palace", "kingdom", "medieval"]):
            return "medieval"
        elif any(word in content for word in ["space", "planet", "galaxy", "alien"]):
            return "sci-fi"
        else:
            return "unknown"

    def _identify_time_period(self, content: str) -> str:
        """Identify time period from content."""
        if any(word in content for word in ["medieval", "knight", "castle", "sword"]):
            return "medieval"
        elif any(word in content for word in ["modern", "contemporary", "today", "current"]):
            return "modern"
        elif any(word in content for word in ["future", "futuristic", "sci-fi", "technology"]):
            return "future"
        elif any(word in content for word in ["past", "historical", "ancient", "old"]):
            return "historical"
        else:
            return "unknown"

    def _identify_atmosphere(self, content: str) -> str:
        """Identify atmosphere from content."""
        if any(word in content for word in ["dark", "ominous", "threatening", "scary"]):
            return "dark"
        elif any(word in content for word in ["bright", "cheerful", "happy", "joyful"]):
            return "bright"
        elif any(word in content for word in ["mysterious", "strange", "unknown", "hidden"]):
            return "mysterious"
        elif any(word in content for word in ["peaceful", "calm", "serene", "quiet"]):
            return "peaceful"
        else:
            return "neutral"

    def _identify_plot_type(self, content: str) -> str:
        """Identify plot type from content."""
        if any(word in content for word in ["adventure", "quest", "journey", "travel"]):
            return "adventure"
        elif any(word in content for word in ["romance", "love", "relationship", "romantic"]):
            return "romance"
        elif any(word in content for word in ["mystery", "puzzle", "investigation", "solve"]):
            return "mystery"
        elif any(word in content for word in ["conflict", "war", "battle", "fight"]):
            return "conflict"
        else:
            return "general"

    def _identify_conflict_type(self, content: str) -> str:
        """Identify conflict type from content."""
        if any(word in content for word in ["internal", "personal", "self", "mind"]):
            return "internal"
        elif any(word in content for word in ["external", "enemy", "opponent", "against"]):
            return "external"
        elif any(word in content for word in ["society", "social", "cultural", "system"]):
            return "societal"
        else:
            return "unknown"

    async def _generate_cross_references(
        self,
        analysis_results: list[MaterialAnalysisResult]
    ) -> list[CrossReference]:
        """
        Generate cross-references using embedding similarity.

        Args:
            analysis_results: Results to generate cross-references for

        Returns:
            List of cross-references between materials
        """
        try:
            cross_refs: list[CrossReference] = []

            # Extract materials with embeddings
            materials_with_embeddings = [
                (result.source_classification, result.vector_storage_metadata.get("primary_embedding"))
                for result in analysis_results
                if result.vector_storage_metadata.get("primary_embedding")
            ]

            if len(materials_with_embeddings) < 2:
                logger.debug("Not enough materials with embeddings for cross-reference generation")
                return cross_refs

            # Compute pairwise similarities
            for i, (source_material, source_embedding) in enumerate(materials_with_embeddings):
                for _j, (target_material, target_embedding) in enumerate(materials_with_embeddings[i+1:], i+1):

                    # Calculate cosine similarity  
                    if source_embedding is None or target_embedding is None:
                        continue
                    if not isinstance(source_embedding, list) or not isinstance(target_embedding, list):
                        continue
                    similarity = self._cosine_similarity(source_embedding, target_embedding)

                    if similarity > self.similarity_threshold:
                        # Determine relationship type
                        relationship_type = self._determine_relationship_type(
                            source_material, target_material, similarity
                        )

                        cross_refs.append(CrossReference(
                            source_material_id=source_material.id,
                            target_material_id=target_material.id,
                            relationship_type=relationship_type,
                            confidence=similarity,
                            context=f"Similar content detected (similarity: {similarity:.3f})"
                        ))

            logger.debug(f"Generated {len(cross_refs)} cross-references")
            return cross_refs

        except Exception as e:
            logger.error(f"Cross-reference generation failed: {e}")
            raise CrossReferenceGenerationError(f"Failed to generate cross-references: {e}") from e

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))

        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def _determine_relationship_type(
        self,
        source_material: MaterialClassification,
        target_material: MaterialClassification,
        similarity: float
    ) -> str:
        """Determine the type of relationship between materials."""
        # Same category suggests direct similarity
        if source_material.category == target_material.category:
            if similarity > 0.9:
                return "similar"
            else:
                return "references"

        # Different categories suggest expansion or reference
        if similarity > 0.85:
            return "expands"
        else:
            return "references"

    def _add_cross_references_to_results(
        self,
        results: list[MaterialAnalysisResult],
        cross_references: list[CrossReference]
    ) -> None:
        """Add cross-references to analysis results."""
        # Create lookup map
        result_map = {result.source_classification.id: result for result in results}

        # Add cross-references to relevant results
        for cross_ref in cross_references:
            if cross_ref.source_material_id in result_map:
                result_map[cross_ref.source_material_id].cross_references.append(cross_ref)

            # Add reverse reference
            if cross_ref.target_material_id in result_map:
                reverse_ref = CrossReference(
                    source_material_id=cross_ref.target_material_id,
                    target_material_id=cross_ref.source_material_id,
                    relationship_type=cross_ref.relationship_type,
                    confidence=cross_ref.confidence,
                    context=f"Referenced by {cross_ref.source_material_id}"
                )
                result_map[cross_ref.target_material_id].cross_references.append(reverse_ref)

    async def execute(self, *args: Any, **kwargs: Any) -> MaterialAnalysisResponse:
        """
        Execute the LibrarianAgent's primary function: material analysis.

        This method provides the standard Agent interface while delegating
        to the specialized analyze_materials method.

        Args:
            *args: Positional arguments, expected to contain MaterialClassification list
            **kwargs: Keyword arguments for analysis configuration

        Returns:
            MaterialAnalysisResponse with analysis results

        Raises:
            ValueError: If invalid arguments provided
            LibrarianError: If analysis fails
        """
        # Parse arguments to extract materials and configuration
        if args and isinstance(args[0], list):
            materials = args[0]
        elif 'materials' in kwargs:
            materials = kwargs.pop('materials')
        else:
            raise ValueError("LibrarianAgent.execute requires materials list as first argument or 'materials' keyword")

        # Create analysis request from arguments
        try:
            request = MaterialAnalysisRequest(
                classifications=materials,
                **kwargs
            )

            return await self.analyze_materials(request)

        except Exception as e:
            logger.error(f"LibrarianAgent.execute failed: {e}")
            raise LibrarianError(f"Execution failed: {e}") from e

    async def close(self) -> None:
        """Clean up LibrarianAgent resources."""
        try:
            if self.embedding_service:
                await self.embedding_service.close()
            if self.memory_service:
                await self.memory_service.close()
            logger.info("LibrarianAgent resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up LibrarianAgent: {e}")


# Convenience functions for direct usage
async def analyze_materials_direct(
    materials: list[MaterialClassification],
    analysis_depth: str = "standard",
    enable_cross_references: bool = True,
    enable_quality_assessment: bool = True
) -> MaterialAnalysisResponse:
    """
    Direct function for analyzing materials without creating LibrarianAgent instance.

    Args:
        materials: Materials to analyze
        analysis_depth: Depth of analysis
        enable_cross_references: Whether to generate cross-references
        enable_quality_assessment: Whether to perform quality assessment

    Returns:
        Analysis response
    """
    librarian = LibrarianAgent()

    try:
        request = MaterialAnalysisRequest(
            classifications=materials,
            analysis_depth=analysis_depth,
            enable_cross_references=enable_cross_references,
            enable_quality_assessment=enable_quality_assessment
        )

        return await librarian.analyze_materials(request)

    finally:
        await librarian.close()


logger.info("LibrarianAgent module loaded successfully")
